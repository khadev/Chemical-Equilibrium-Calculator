"""
ui/widgets/plots_widget.py  v3
================================
NASA_CEA_PROFESSIONAL_STANDARD — View Layer
FigureCanvasQTAgg integration.
update_plots() is called ONLY from data_parsed signal — no race conditions.
Fixes:
  • Radar chart: OO polar axes, labels placed along spokes (no overlap)
  • Annotations: ax.annotate with bbox for readability
  • Exit composition: never called before parse completes
  • Bar chart: annotate with offset bbox, star for best value
"""
from __future__ import annotations
from typing import List, Optional, Dict
import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSizePolicy
)

try:
    import matplotlib
    matplotlib.use("QtAgg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import (
        FigureCanvasQTAgg as FigureCanvas,
        NavigationToolbar2QT as NavToolbar,
    )
    import numpy as np
    MPL = True
except ImportError:
    MPL = False

from models.cea_result import CEAResult
from models.config_manager import ConfigManager

log = logging.getLogger(__name__)

PALETTE = [
    "#3F51B5","#00ACC1","#43A047","#FB8C00",
    "#E53935","#8E24AA","#00897B","#F4511E",
    "#039BE5","#7CB342","#FFB300","#6D4C41",
]


class PlotsWidget(QWidget):
    """
    Embeds matplotlib via FigureCanvasQTAgg.
    IMPORTANT: update_plots() must be called from data_parsed signal,
    never from result_ready — ensures species data is always available.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cfg    = ConfigManager()
        self._canvas: Optional[FigureCanvas] = None
        self._toolbar: Optional[NavToolbar]  = None
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(4, 4, 4, 4)
        self._root.setSpacing(4)

        if MPL:
            self._placeholder = QLabel(
                "📈  Plots appear here after a successful calculation.\n"
                "    (Triggered by data_parsed signal — no race condition)")
            self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._placeholder.setStyleSheet(
                "color:#9E9E9E; font-size:13px; padding:20px;")
            self._root.addWidget(self._placeholder)
        else:
            lbl = QLabel("matplotlib is not installed.\n"
                         "  pip install matplotlib")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#FF9800; font-size:14px;")
            self._root.addWidget(lbl)

    # ── Called ONLY from data_parsed signal ──────────────────────────
    def update_plots(self, results: List[CEAResult],
                     session_colors: Optional[List[str]] = None,
                     formulation_dicts: Optional[List[dict]] = None) -> None:
        if not MPL:
            return
        completed = [r for r in results if r and r.success and r.cstar > 0]
        if not completed:
            return

        colors    = session_colors or [
            PALETTE[i % len(PALETTE)] for i in range(len(completed))]
        form_list = formulation_dicts or [{}] * len(completed)

        self._clear_canvas()

        theme = self._cfg.get("theme") or "light"
        style = self._style(theme)
        for k, v in style.items():
            try:
                plt.rcParams[k] = v
            except Exception:
                pass

        fig = self._build_figure(completed, colors, form_list, style)

        self._canvas  = FigureCanvas(fig)
        self._toolbar = NavToolbar(self._canvas, self)
        self._root.addWidget(self._toolbar)
        self._root.addWidget(self._canvas, 1)
        self._canvas.draw()
        log.debug("Plots rebuilt for %d sessions", len(completed))

    # ── Figure construction ───────────────────────────────────────────
    def _build_figure(self, results, colors, form_dicts, style) -> Figure:
        n      = len(results)
        names  = [r.formulation_name or f"Run {i+1}"
                  for i, r in enumerate(results)]
        isp_ms = [r.isp_ms     for r in results]
        cstar  = [r.cstar      for r in results]
        tc     = [r.t_chamber  for r in results]
        cf     = [r.cf         for r in results]
        mw     = [r.mw         for r in results]
        gamma  = [r.gamma      for r in results]
        of_vals = [fd.get("of_ratio", 2.5) for fd in form_dicts]

        lw       = int(self._cfg.get("display", "line_thickness") or 2)
        show_pts = bool(self._cfg.get("display", "show_data_points"))
        show_pk  = bool(self._cfg.get("display", "show_peak_markers"))
        show_leg = bool(self._cfg.get("display", "show_legend"))

        fig = Figure(figsize=(12, 9.5), dpi=96,
                     facecolor=style["figure.facecolor"])
        fig.suptitle("Propellant Performance Analysis",
                     fontsize=14, fontweight="bold",
                     color=style["text.color"], y=0.987)

        gs = gridspec.GridSpec(3, 3, figure=fig,
                               hspace=0.58, wspace=0.44,
                               left=0.07, right=0.97,
                               top=0.94, bottom=0.07)

        ax_isp   = fig.add_subplot(gs[0, 0])
        ax_cstar = fig.add_subplot(gs[0, 1])
        ax_cf    = fig.add_subplot(gs[0, 2])
        ax_tc    = fig.add_subplot(gs[1, 0])
        ax_mw    = fig.add_subplot(gs[1, 1])
        ax_gam   = fig.add_subplot(gs[1, 2])
        ax_pie   = fig.add_subplot(gs[2, 0])
        ax_of    = fig.add_subplot(gs[2, 1])
        ax_radar = fig.add_subplot(gs[2, 2], polar=True)

        # Bar charts
        self._bar(ax_isp,   names, isp_ms, colors,
                  "Isp  (m/s)", style, lw, show_pk)
        self._bar(ax_cstar, names, cstar,  colors,
                  "C*  (m/s)",  style, lw, show_pk)
        self._bar(ax_cf,    names, cf,     colors,
                  "Thrust Coeff  Cf", style, lw, show_pk)
        self._bar(ax_tc,    names, tc,     colors,
                  "Chamber Temp  Tc (K)", style, lw, show_pk,
                  higher=False)
        self._bar(ax_mw,    names, mw,     colors,
                  "Mol. Weight  MW (g/mol)", style, lw, show_pk,
                  higher=False, lower_better=True)
        self._bar(ax_gam,   names, gamma,  colors,
                  "Heat Ratio  γ", style, lw, show_pk, higher=False)

        # Exit composition pie
        self._pie(ax_pie, results[0], names[0], style)

        # Isp vs O/F
        self._isp_vs_of(ax_of, results, of_vals, form_dicts,
                         colors, style, show_pts, lw, show_leg)

        # Radar
        self._radar(ax_radar, results, colors, names, style, show_leg)

        return fig

    # ── Bar chart with annotated values + bbox ────────────────────────
    def _bar(self, ax, names, vals, colors, title, style,
             lw=2, show_peak=True, higher=True,
             lower_better=False) -> None:
        if not vals or all(v == 0 for v in vals):
            ax.set_title(title, color=style["text.color"], fontsize=8.5)
            self._style_ax(ax, style)
            return

        x = np.arange(len(names))
        bars = ax.bar(x, vals, color=colors,
                      edgecolor=style["axes.edgecolor"],
                      linewidth=0.7, zorder=3)

        mx   = max(vals)
        mn_v = min(vals)
        if len(vals) > 1:
            best_i = (vals.index(min(vals)) if lower_better
                      else vals.index(max(vals)))
        else:
            best_i = -1

        for i, (bar, v) in enumerate(zip(bars, vals)):
            is_best = (i == best_i and len(vals) > 1)
            # Value annotation with bbox for readability
            ax.annotate(
                f"{v:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2,
                    bar.get_height()),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center", va="bottom",
                fontsize=6.5,
                fontweight="bold" if is_best else "normal",
                color=style["text.color"],
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor=style["figure.facecolor"],
                    edgecolor="none", alpha=0.7))
            if is_best and show_peak:
                ax.annotate(
                    "★",
                    xy=(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + mx * 0.07),
                    ha="center", va="bottom",
                    fontsize=10, color=colors[i])

        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=22, ha="right",
                            fontsize=6.5, color=style["text.color"])
        ax.set_title(title, color=style["text.color"],
                      fontsize=8.5, pad=4)
        ax.set_xlim(-0.6, len(names) - 0.4)
        y_min = mn_v * 0.95 if mn_v > 0 else mn_v * 1.05
        ax.set_ylim(y_min, mx * 1.18)
        self._style_ax(ax, style)

    # ── Pie chart ─────────────────────────────────────────────────────
    def _pie(self, ax, result: CEAResult, name: str,
              style: dict) -> None:
        mf = result.mass_fractions if result else {}

        if not mf:
            ax.text(0.5, 0.5,
                    "Species data\nnot available",
                    ha="center", va="center",
                    color=style["text.color"],
                    fontsize=9, transform=ax.transAxes)
            ax.set_title(f"Exit Composition\n({name})",
                          color=style["text.color"], fontsize=8)
            # No error — species data is legitimately absent for fallback runs
            return

        sorted_sp = sorted(mf.items(), key=lambda x: -x[1])[:7]
        sp_names  = [s[0] for s in sorted_sp]
        sp_vals   = [s[1] for s in sorted_sp]
        other     = max(0.0, 1.0 - sum(sp_vals))
        if other > 0.001:
            sp_names.append("Other")
            sp_vals.append(other)

        wedges, texts, autotexts = ax.pie(
            sp_vals, labels=sp_names, autopct="%1.1f%%",
            colors=plt.cm.tab10.colors[:len(sp_vals)],
            textprops={"color": style["text.color"], "fontsize": 6},
            wedgeprops={"linewidth": 0.6,
                        "edgecolor": style["axes.edgecolor"]},
            startangle=90, pctdistance=0.76)
        for at in autotexts:
            at.set_fontsize(5.5)
            at.set_bbox(dict(facecolor=style["figure.facecolor"],
                             alpha=0.6, edgecolor="none", pad=1))
        ax.set_title(f"Exit Composition\n({name})",
                      color=style["text.color"], fontsize=8, pad=4)

    # ── Isp vs O/F — sorted, bbox-annotated ──────────────────────────
    def _isp_vs_of(self, ax, results, of_vals, form_dicts,
                   colors, style, show_pts, lw, show_leg) -> None:
        ax.set_xlabel("O/F Ratio",
                       color=style["axes.labelcolor"], fontsize=8)
        ax.set_ylabel("Isp  (m/s)",
                       color=style["axes.labelcolor"], fontsize=8)
        ax.set_title("Isp  vs  O/F Ratio",
                      color=style["text.color"], fontsize=9, pad=4)
        self._style_ax(ax, style)

        if not results:
            return

        # Group by Pc for separate lines
        groups: Dict = {}
        for r, of, fd, col in zip(results, of_vals, form_dicts, colors):
            pc_key = round(fd.get("chamber_pressure", 0), 1)
            groups.setdefault(pc_key, []).append((of, r.isp_ms, r, col))

        cc = plt.cm.tab10.colors
        all_of, all_isp = [], []

        for gi, (pc_val, pts) in enumerate(sorted(groups.items())):
            # Sort by O/F — guarantees continuous non-empty line
            pts_s = sorted(pts, key=lambda p: p[0])
            of_x  = [p[0] for p in pts_s]
            isp_y = [p[1] for p in pts_s]
            col   = cc[gi % len(cc)]
            lbl   = f"Pc={pc_val:.0f} bar" if len(groups) > 1 else None

            ax.plot(of_x, isp_y,
                    "o-" if show_pts else "-",
                    color=col, linewidth=lw,
                    markersize=5 if show_pts else 0,
                    markerfacecolor="white",
                    markeredgecolor=col, markeredgewidth=1.4,
                    label=lbl, zorder=3)

            # Annotate each point with bbox
            for of_v, isp_v, r, rcol in pts_s:
                ax.annotate(
                    r.formulation_name,
                    xy=(of_v, isp_v),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=5.5, color=rcol,
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        facecolor=style["figure.facecolor"],
                        edgecolor=rcol, alpha=0.7, linewidth=0.5))

            all_of  += of_x
            all_isp += isp_y

        # Best point
        if all_isp:
            bi = all_isp.index(max(all_isp))
            ax.scatter([all_of[bi]], [all_isp[bi]],
                       color="#FFD600", s=80, zorder=6, marker="*")
            ax.annotate(
                f"★ {all_isp[bi]:.0f} m/s",
                xy=(all_of[bi], all_isp[bi]),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=7, color="#FFD600",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor=style["figure.facecolor"],
                          edgecolor="#FFD600", alpha=0.8))

        if len(groups) > 1 and show_leg:
            ax.legend(fontsize=6,
                       facecolor=style["legend.facecolor"],
                       edgecolor=style["legend.edgecolor"],
                       labelcolor=style["text.color"], loc="best")

    # ── Radar chart — OO polar, no label overlap ─────────────────────
    def _radar(self, ax, results, colors, names,
               style, show_leg) -> None:
        CATS   = ["Isp", "C*", "Cf", "Tc", "1/MW", "γ"]
        N      = len(CATS)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles_closed = angles + angles[:1]

        # Style polar axes
        ax.set_facecolor(style["axes.facecolor"])
        ax.spines["polar"].set_color(style["axes.edgecolor"])
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["25%","50%","75%","100%"],
                            fontsize=5.5,
                            color=style["text.color"])
        ax.set_ylim(0, 1.0)

        # Hide default tick labels; draw custom angled labels
        ax.set_xticks(angles)
        ax.set_xticklabels([])  # hide defaults

        # Draw spoke labels with angle-aware ha/va (prevents overlap)
        for angle_rad, cat in zip(angles, CATS):
            deg = np.degrees(angle_rad) % 360
            # Horizontal alignment
            if deg < 5 or deg > 355:
                ha, va = "center", "bottom"
            elif 5 <= deg < 90:
                ha, va = "left", "bottom"
            elif 85 <= deg < 95:
                ha, va = "left", "center"
            elif 95 <= deg < 175:
                ha, va = "left", "top"
            elif 175 <= deg < 185:
                ha, va = "center", "top"
            elif 185 <= deg < 265:
                ha, va = "right", "top"
            elif 265 <= deg < 275:
                ha, va = "right", "center"
            else:
                ha, va = "right", "bottom"

            ax.text(
                angle_rad, 1.28, cat,
                ha=ha, va=va,
                fontsize=8.5, fontweight="bold",
                color=style["text.color"])

        # Normalise metrics across sessions
        def _norm(vals):
            mn, mx = min(vals), max(vals)
            if mx == mn:
                return [0.5] * len(vals)
            return [(v - mn) / (mx - mn) for v in vals]

        isp_n = _norm([r.isp_ms     for r in results])
        cs_n  = _norm([r.cstar      for r in results])
        cf_n  = _norm([r.cf         for r in results])
        tc_n  = _norm([r.t_chamber  for r in results])
        mw_n  = _norm([1 / max(r.mw, 0.001) for r in results])
        gm_n  = _norm([r.gamma      for r in results])

        for i, (r, col, name) in enumerate(zip(results, colors, names)):
            vals = [isp_n[i], cs_n[i], cf_n[i],
                    tc_n[i],  mw_n[i], gm_n[i]]
            vals_closed = vals + vals[:1]

            ax.plot(angles_closed, vals_closed,
                    "o-", color=col, linewidth=1.8,
                    markersize=5, label=name, zorder=3)
            ax.fill(angles_closed, vals_closed,
                    alpha=0.08, color=col)

            # Annotate each vertex with its normalised value
            for angle, v, raw_v in zip(
                    angles,
                    vals,
                    [r.isp_ms, r.cstar, r.cf,
                     r.t_chamber, r.mw, r.gamma]):
                ax.annotate(
                    f"{raw_v:.1f}",
                    xy=(angle, v),
                    xytext=(0, 6),
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=5.5, color=col,
                    bbox=dict(
                        boxstyle="round,pad=0.15",
                        facecolor=style["figure.facecolor"],
                        edgecolor=col, alpha=0.75, linewidth=0.4))

        # Legend outside the polar area to avoid overlap
        if show_leg:
            ax.legend(
                loc="upper right",
                bbox_to_anchor=(1.50, 1.22),
                fontsize=7,
                facecolor=style["legend.facecolor"],
                edgecolor=style["legend.edgecolor"],
                labelcolor=style["text.color"],
                framealpha=0.9)

        ax.set_title("Performance Radar",
                      color=style["text.color"],
                      fontsize=9, pad=26)

    # ── Axis styling ──────────────────────────────────────────────────
    def _style_ax(self, ax, style: dict) -> None:
        ax.set_facecolor(style["axes.facecolor"])
        for spine in ax.spines.values():
            spine.set_edgecolor(style["axes.edgecolor"])
        ax.tick_params(colors=style["text.color"],
                        labelsize=6.5, length=3)
        ax.yaxis.label.set_color(style["axes.labelcolor"])
        ax.xaxis.label.set_color(style["axes.labelcolor"])
        ax.grid(True, color=style["grid.color"],
                 alpha=0.3, linewidth=0.5, linestyle="--")

    def _clear_canvas(self) -> None:
        if self._canvas:
            self._root.removeWidget(self._canvas)
            self._canvas.setParent(None)
            self._canvas = None
        if self._toolbar:
            self._root.removeWidget(self._toolbar)
            self._toolbar.setParent(None)
            self._toolbar = None
        if hasattr(self, "_placeholder") and self._placeholder:
            try:
                self._root.removeWidget(self._placeholder)
                self._placeholder.setParent(None)
                self._placeholder = None
            except Exception:
                pass

    # ── Style dict ────────────────────────────────────────────────────
    @staticmethod
    def _style(theme: str = "light") -> dict:
        if theme == "dark":
            return {
                "figure.facecolor": "#1a1a2e",
                "axes.facecolor":   "#0d0d1a",
                "axes.edgecolor":   "#3F51B5",
                "axes.labelcolor":  "#B0BEC5",
                "text.color":       "#E0E0E0",
                "xtick.color":      "#E0E0E0",
                "ytick.color":      "#E0E0E0",
                "grid.color":       "#1e1e3a",
                "legend.facecolor": "#16213e",
                "legend.edgecolor": "#3F51B5",
                "lines.linewidth":  2,
            }
        # Light (default)
        return {
            "figure.facecolor": "#FAFAFA",
            "axes.facecolor":   "#FFFFFF",
            "axes.edgecolor":   "#9FA8DA",
            "axes.labelcolor":  "#424242",
            "text.color":       "#212121",
            "xtick.color":      "#212121",
            "ytick.color":      "#212121",
            "grid.color":       "#E0E0E0",
            "legend.facecolor": "#FFFFFF",
            "legend.edgecolor": "#9FA8DA",
            "lines.linewidth":  2,
        }
