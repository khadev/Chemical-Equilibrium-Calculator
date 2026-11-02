
"""
ui/results_panel.py
======================
Results display: a ``CTkTabview`` with Performance, Compare, Plots,
and Console tabs. Matplotlib is embedded via ``FigureCanvasTkAgg`` in
the dedicated Plots tab — graphs are only built once the result is
confirmed parsed successfully (no race condition with the engine).
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional

import customtkinter as ctk

from core.theme_manager import ThemeManager
from models.cea_result import CEAResult
from tools.settings_manager import SettingsManager

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg, NavigationToolbar2Tk)
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

log = logging.getLogger(__name__)

_PALETTE = ["#3F51B5", "#00ACC1", "#43A047", "#FB8C00",
            "#E53935", "#8E24AA", "#00897B", "#F4511E"]


class ResultsPanel(ctk.CTkFrame):
    """Tabbed results display: Performance / Compare / Plots / Console."""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        colors = ThemeManager().get_colors()
        super().__init__(master, fg_color=colors["bg"])
        self._settings = SettingsManager()
        self._results: List[CEAResult] = []
        self._formulations: List = []
        self._plot_canvas: Optional["FigureCanvasTkAgg"] = None
        self._plot_toolbar: Optional["NavigationToolbar2Tk"] = None
        self._build()

    def _build(self) -> None:
        tr = self._settings.tr
        self._tabview = ctk.CTkTabview(self, fg_color=ThemeManager().get_colors()["surface"])
        self._tabview.pack(fill="both", expand=True, padx=4, pady=4)

        self._tabview.add(tr("performance"))
        self._tabview.add(tr("compare"))
        self._tabview.add(tr("plots"))
        self._tabview.add(tr("console"))

        self._build_performance_tab(self._tabview.tab(tr("performance")))
        self._build_compare_tab(self._tabview.tab(tr("compare")))
        self._build_plots_tab(self._tabview.tab(tr("plots")))
        self._build_console_tab(self._tabview.tab(tr("console")))

    # ── Performance tab ───────────────────────────────────────────────
    def _build_performance_tab(self, tab: ctk.CTkFrame) -> None:
        colors = ThemeManager().get_colors()

        perf_header = ctk.CTkFrame(tab, fg_color=colors["accent"], corner_radius=6)
        perf_header.pack(fill="x", padx=4, pady=(4, 0))
        for text, width, anchor in [("Parameter", 150, "w"), ("Value", 120, "e"),
                                    ("Unit", 70, "w"), ("Description", 0, "w")]:
            ctk.CTkLabel(
                perf_header, text=text,
                width=width if width else 0,
                anchor=anchor, font=ctk.CTkFont(size=11, weight="bold"),
                text_color=colors["text_on_accent"]
            ).pack(side="left", padx=(10 if anchor == "w" else 4, 4),
                  fill="x" if width == 0 else None, expand=(width == 0))

        self._perf_scroll = ctk.CTkScrollableFrame(tab, fg_color=colors["surface"])
        self._perf_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 2))

        species_header_row = ctk.CTkFrame(tab, fg_color="transparent")
        species_header_row.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkLabel(
            species_header_row, text="Exit Plane Composition",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=colors["accent"]
        ).pack(side="left")
        self._species_caveat_label = ctk.CTkLabel(
            species_header_row, text="",
            font=ctk.CTkFont(size=9), text_color=colors["warning"])
        self._species_caveat_label.pack(side="left", padx=(8, 0))

        self._species_scroll = ctk.CTkScrollableFrame(
            tab, fg_color=colors["surface"], height=140)
        self._species_scroll.pack(fill="x", padx=4, pady=(2, 4))

    # ── Compare tab ───────────────────────────────────────────────────
    def _build_compare_tab(self, tab: ctk.CTkFrame) -> None:
        colors = ThemeManager().get_colors()
        self._compare_scroll = ctk.CTkScrollableFrame(
            tab, fg_color=colors["surface"])
        self._compare_scroll.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Plots tab ─────────────────────────────────────────────────────
    def _build_plots_tab(self, tab: ctk.CTkFrame) -> None:
        colors = ThemeManager().get_colors()
        self._plots_container = tab
        self._plots_placeholder = ctk.CTkLabel(
            tab,
            text=("📈  Plots appear here after a successful calculation.\n"
                  "Dashboard: Isp / C* / Cf / Tc / MW / γ bar charts, exit\n"
                  "composition pie chart, Isp-vs-O/F trend, and a cross-\n"
                  "session performance radar — rebuilt only after the\n"
                  "result is fully parsed.") if MATPLOTLIB_AVAILABLE
            else "matplotlib is not installed.",
            text_color=colors["text_secondary"],
            font=ctk.CTkFont(size=13))
        self._plots_placeholder.pack(expand=True, pady=60)

    # ── Console tab ───────────────────────────────────────────────────
    def _build_console_tab(self, tab: ctk.CTkFrame) -> None:
        colors = ThemeManager().get_colors()
        self._console = ctk.CTkTextbox(
            tab, fg_color=colors["console_bg"], text_color=colors["console_text"],
            font=ctk.CTkFont(family="Courier", size=10))
        self._console.pack(fill="both", expand=True, padx=4, pady=4)
        self._console.insert("end", "CEA Calculator Pro — Console\n" + "─" * 60 + "\n")
        self._console.configure(state="disabled")

    def log(self, message: str) -> None:
        """Append a line to the console tab."""
        self._console.configure(state="normal")
        self._console.insert("end", message + "\n")
        self._console.see("end")
        self._console.configure(state="disabled")

    # ── Show a single result ────────────────────────────────────────
    def show_result(self, result: CEAResult, units: Optional[Dict[str, str]] = None) -> None:
        """Display ``result`` in the Performance tab and update Compare."""
        units = units or {"pressure": "bar", "temperature": "K"}
        if result not in self._results:
            self._results.append(result)
        self._render_performance(result, units)
        self._render_compare()

    def _render_performance(self, result: CEAResult, units: Dict[str, str]) -> None:
        colors = ThemeManager().get_colors()
        for child in self._perf_scroll.winfo_children():
            child.destroy()

        for i, row in enumerate(result.to_table_rows(units)):
            param, value, unit = row[0], row[1], row[2]
            description = row[3] if len(row) > 3 else ""
            value_color = row[4] if len(row) > 4 else colors["accent"]
            row_bg = colors["table_alt"] if i % 2 == 1 else colors["surface"]

            line = ctk.CTkFrame(self._perf_scroll, fg_color=row_bg, corner_radius=4)
            line.pack(fill="x", pady=1)
            ctk.CTkLabel(line, text=param, width=150, anchor="w",
                        font=ctk.CTkFont(size=11, weight="bold")
                        ).pack(side="left", padx=(10, 4), pady=4)
            ctk.CTkLabel(line, text=value, width=120, anchor="e",
                        font=ctk.CTkFont(family="Courier", size=11, weight="bold"),
                        text_color=value_color).pack(side="left", padx=4, pady=4)
            ctk.CTkLabel(line, text=unit, width=70, anchor="w",
                        font=ctk.CTkFont(size=10),
                        text_color=colors["text_secondary"]).pack(side="left", padx=4, pady=4)
            if description:
                ctk.CTkLabel(line, text=description, anchor="w",
                            font=ctk.CTkFont(size=9),
                            text_color=colors["text_secondary"]
                            ).pack(side="left", padx=4, pady=4, fill="x", expand=True)

        is_fallback = result.method.startswith("Fallback")
        if is_fallback and result.mass_fractions:
            self._species_caveat_label.configure(
                text="⚠ Representative values for this propellant class "
                     "— not a chemical-equilibrium calculation")
        elif is_fallback:
            self._species_caveat_label.configure(text="")
        else:
            self._species_caveat_label.configure(
                text="✓ Computed by FCEA2 chemical equilibrium",
                text_color=colors["success"])

        for child in self._species_scroll.winfo_children():
            child.destroy()
        sorted_species = sorted(
            result.mass_fractions.items(), key=lambda x: -x[1])
        for i, (species, fraction) in enumerate(sorted_species):
            row_bg = colors["table_alt"] if i % 2 == 1 else colors["surface"]
            row = ctk.CTkFrame(self._species_scroll, fg_color=row_bg, corner_radius=4)
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=species, width=150, anchor="w",
                        font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 4), pady=3)
            ctk.CTkLabel(
                row, text=f"{fraction * 100:.2f}%", anchor="e", width=80,
                text_color=colors["accent"],
                font=ctk.CTkFont(family="Courier", size=11, weight="bold")
            ).pack(side="left", padx=4, pady=3)

    def _render_compare(self) -> None:
        colors = ThemeManager().get_colors()
        for child in self._compare_scroll.winfo_children():
            child.destroy()
        if not self._results:
            return

        params = [
            ("Isp (m/s)", lambda r: r.isp_m_s if hasattr(r, 'isp_m_s') else r.isp_vacuum_s * 9.80665, "{:.1f}"),
            ("C* (m/s)", lambda r: r.cstar_m_s, "{:.1f}"),
            ("Cf", lambda r: r.cf_vacuum if hasattr(r, 'cf_vacuum') and r.cf_vacuum > 0 else r.cf, "{:.4f}"),
            ("Tc (K)", lambda r: r.t_chamber_k, "{:.0f}"),
            ("MW", lambda r: r.molecular_weight, "{:.3f}"),
            ("γ", lambda r: r.gamma, "{:.4f}"),
            ("Method", lambda r: r.method, "{}"),
        ]
        header = ctk.CTkFrame(self._compare_scroll, fg_color=colors["accent"],
                              corner_radius=4)
        header.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(header, text="Parameter", width=130, anchor="w",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=colors["text_on_accent"]
                    ).pack(side="left", padx=(10, 4), pady=6)
        for r in self._results:
            ctk.CTkLabel(header, text=r.name, width=120, anchor="center",
                        font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=colors["text_on_accent"]
                        ).pack(side="left", padx=4, pady=6)

        for i, (label, extractor, fmt) in enumerate(params):
            row_bg = colors["table_alt"] if i % 2 == 1 else colors["surface"]
            row = ctk.CTkFrame(self._compare_scroll, fg_color=row_bg, corner_radius=4)
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=label, width=130, anchor="w",
                        font=ctk.CTkFont(size=11, weight="bold")
                        ).pack(side="left", padx=(10, 4), pady=4)
            for r in self._results:
                try:
                    text = fmt.format(extractor(r))
                except (ValueError, TypeError):
                    text = "—"
                ctk.CTkLabel(row, text=text, width=120, anchor="center",
                            font=ctk.CTkFont(family="Courier", size=10)
                            ).pack(side="left", padx=4, pady=4)

    # ── Plots — called ONLY after the engine confirms the parse succeeded ──
    def update_plots(self, results: List[CEAResult],
                     formulations: Optional[List] = None) -> None:
        """
        Rebuild the Plots tab figure with the full performance dashboard.
        """
        if not MATPLOTLIB_AVAILABLE:
            return
        successful = [r for r in results if r.success and r.cstar_m_s > 0]
        if not successful:
            return
        formulations = formulations or []
        self._formulations = formulations

        for child in self._plots_container.winfo_children():
            child.destroy()

        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(successful))]
        fig = self._build_figure(successful, colors, formulations)
        canvas = FigureCanvasTkAgg(fig, master=self._plots_container)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, self._plots_container, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="top", fill="x")
        canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        self._plot_canvas = canvas
        self._plot_toolbar = toolbar

    def render_dashboard_png(self, results: List[CEAResult],
                             formulations: Optional[List] = None,
                             dpi: int = 130) -> Optional[bytes]:
        """
        Render the same performance dashboard shown in the Plots tab to
        in-memory PNG bytes, without touching any displayed widget.
        """
        if not MATPLOTLIB_AVAILABLE:
            return None
        successful = [r for r in results if r.success and r.cstar_m_s > 0]
        if not successful:
            return None
        formulations = formulations or []
        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(successful))]
        fig = self._build_figure(successful, colors, formulations)
        import io
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight",
                   facecolor="#FAFAFA")
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()

    def _build_figure(self, results: List[CEAResult], colors: List[str],
                      formulations: List) -> "Figure":
        names = [r.name or f"Run {i + 1}" for i, r in enumerate(results)]

        def safe(values: List[float]) -> List[float]:
            return [v if isinstance(v, float) and math.isfinite(v) else 0.0
                    for v in values]

        # Use the correct attributes from CEAResult
        # isp_m_s is now a property that returns isp_vacuum_s * G0
        isp = safe([r.isp_m_s if hasattr(r, 'isp_m_s') else r.isp_vacuum_s * 9.80665 for r in results])
        cstar = safe([r.cstar_m_s for r in results])
        # Use cf_vacuum if available, otherwise fall back to cf
        cf = safe([r.cf_vacuum if hasattr(r, 'cf_vacuum') and r.cf_vacuum > 0 else r.cf for r in results])
        tc = safe([r.t_chamber_k for r in results])
        mw = safe([r.molecular_weight for r in results])
        gamma = safe([r.gamma for r in results])

        fig = Figure(figsize=(11, 9), dpi=92, facecolor="#FAFAFA")
        fig.suptitle("Propellant Performance Analysis",
                     fontsize=14, fontweight="bold", color="#1A237E", y=0.985)
        grid = gridspec.GridSpec(
            3, 3, figure=fig, hspace=0.58, wspace=0.42,
            left=0.07, right=0.97, top=0.93, bottom=0.06)

        bar_specs = [
            (isp, "Isp (m/s)", True, False),
            (cstar, "C* (m/s)", True, False),
            (cf, "Thrust Coeff Cf", True, False),
            (tc, "Chamber Temp Tc (K)", False, False),
            (mw, "Mol Weight MW", False, True),
            (gamma, "Heat Ratio γ", False, False),
        ]
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
        for (row, col), (values, title, higher_better, lower_better) in zip(
                positions, bar_specs):
            ax = fig.add_subplot(grid[row, col])
            self._draw_bar(ax, names, values, colors, title,
                          higher_better, lower_better)

        # Pie chart - use the first result's mass fractions
        pie_ax = fig.add_subplot(grid[2, 0])
        self._draw_pie(pie_ax, results[0], names[0])

        # Isp vs O/F chart
        of_ax = fig.add_subplot(grid[2, 1])
        self._draw_isp_vs_of(of_ax, results, formulations, colors)

        # Radar chart
        radar_ax = fig.add_subplot(grid[2, 2], polar=True)
        self._draw_radar(radar_ax, results, colors, names)

        return fig

    def _draw_bar(self, ax, names, values, colors, title,
                  higher_better: bool = True, lower_better: bool = False) -> None:
        if not values or all(v == 0 for v in values):
            ax.set_title(title, fontsize=9)
            ax.set_facecolor("#FFFFFF")
            return
        x = np.arange(len(names))
        bars = ax.bar(x, values, color=colors, edgecolor="#9FA8DA", linewidth=0.7,
                      zorder=3)
        max_v = max(values) or 1.0
        min_v = min(values)
        best_idx = (-1 if len(values) <= 1 else
                   (values.index(min(values)) if lower_better
                    else values.index(max(values))))
        for i, (bar, value) in enumerate(zip(bars, values)):
            is_best = i == best_idx
            ax.annotate(
                f"{value:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4), textcoords="offset points",
                ha="center", va="bottom", fontsize=6.5,
                fontweight="bold" if is_best else "normal",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#FAFAFA",
                          edgecolor="none", alpha=0.7))
            if is_best:
                ax.annotate("★", xy=(bar.get_x() + bar.get_width() / 2,
                                     bar.get_height() + max_v * 0.06),
                           ha="center", fontsize=9, color=colors[i])
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=22, ha="right", fontsize=7)
        ax.set_title(title, fontsize=9, pad=4)
        ax.set_xlim(-0.6, len(names) - 0.4)
        y_min = min_v * 0.94 if min_v > 0 else min_v * 1.06
        ax.set_ylim(y_min, max_v * 1.2)
        ax.grid(True, color="#E0E0E0", linewidth=0.5, linestyle="--")
        ax.set_facecolor("#FFFFFF")
        for spine in ax.spines.values():
            spine.set_edgecolor("#9FA8DA")

    def _draw_pie(self, ax, result: CEAResult, name: str) -> None:
        mass_fractions = {
            k: v for k, v in result.mass_fractions.items()
            if isinstance(v, float) and math.isfinite(v) and v > 0}
        if not mass_fractions:
            ax.text(0.5, 0.5, "Species data\nnot available",
                   ha="center", va="center", fontsize=9,
                   transform=ax.transAxes)
            ax.set_title(f"Exit Composition\n({name})", fontsize=8)
            return
        is_representative = result.method.startswith("Fallback")
        title_suffix = " [representative]" if is_representative else ""
        sorted_species = sorted(mass_fractions.items(), key=lambda x: -x[1])[:8]
        labels = [s[0] for s in sorted_species]
        values = [s[1] for s in sorted_species]
        other = max(0.0, 1.0 - sum(values))
        if other > 0.001:
            labels.append("Other")
            values.append(other)
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%",
            colors=plt.cm.tab10.colors[:len(values)],
            textprops={"fontsize": 6},
            wedgeprops={"linewidth": 0.6, "edgecolor": "#9FA8DA"},
            startangle=90, pctdistance=0.75)
        for at in autotexts:
            at.set_fontsize(5.5)
            at.set_bbox(dict(boxstyle="round,pad=0.15", facecolor="#FAFAFA",
                            edgecolor="none", alpha=0.7))
        ax.set_title(f"Exit Composition\n({name}){title_suffix}", fontsize=8, pad=3)

    def _draw_isp_vs_of(self, ax, results: List[CEAResult],
                        formulations: List, colors: List[str]) -> None:
        ax.set_xlabel("O/F Ratio", fontsize=8)
        ax.set_ylabel("Isp (m/s)", fontsize=8)
        ax.set_title("Isp  vs  O/F Ratio", fontsize=9, pad=4)
        ax.set_facecolor("#FFFFFF")
        ax.grid(True, color="#E0E0E0", linewidth=0.5, linestyle="--")
        for spine in ax.spines.values():
            spine.set_edgecolor("#9FA8DA")

        if not formulations or len(formulations) != len(results):
            ax.text(0.5, 0.5, "O/F data unavailable\nfor this session set",
                   ha="center", va="center", fontsize=8, transform=ax.transAxes)
            return

        points = []
        for result, formulation, color in zip(results, formulations, colors):
            of_value = getattr(formulation, "of_ratio", None)
            isp_value = result.isp_m_s if hasattr(result, 'isp_m_s') else result.isp_vacuum_s * 9.80665
            if of_value and math.isfinite(isp_value):
                points.append((of_value, isp_value, result.name, color))
        if not points:
            ax.text(0.5, 0.5, "No valid O/F points", ha="center",
                   va="center", fontsize=8, transform=ax.transAxes)
            return

        points.sort(key=lambda p: p[0])
        of_values = [p[0] for p in points]
        isp_values = [p[1] for p in points]
        ax.plot(of_values, isp_values, "o-", color="#3F51B5", linewidth=1.8,
               markersize=6, markerfacecolor="white", markeredgecolor="#3F51B5",
               markeredgewidth=1.5, zorder=3)
        for of_value, isp_value, name, color in points:
            ax.annotate(name, xy=(of_value, isp_value), xytext=(5, 5),
                       textcoords="offset points", fontsize=6, color=color,
                       bbox=dict(boxstyle="round,pad=0.2", facecolor="#FAFAFA",
                                edgecolor=color, alpha=0.7, linewidth=0.5))
        best_idx = isp_values.index(max(isp_values))
        ax.scatter([of_values[best_idx]], [isp_values[best_idx]],
                  color="#FFB300", s=80, zorder=6, marker="*")

    def _draw_radar(self, ax, results: List[CEAResult], colors: List[str],
                    names: List[str]) -> None:
        categories = ["Isp", "C*", "Cf", "Tc", "1/MW", "γ"]
        n = len(categories)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        angles_closed = angles + angles[:1]

        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=5.5)
        ax.set_xticks(angles)
        ax.set_xticklabels([])
        for angle, category in zip(angles, categories):
            degrees = np.degrees(angle) % 360
            ha = ("center" if degrees < 5 or degrees > 355 else
                  "left" if 5 <= degrees < 175 else
                  "center" if 175 <= degrees < 185 else "right")
            ax.text(angle, 1.28, category, ha=ha, fontsize=8, fontweight="bold")

        def normalize(values: List[float]) -> List[float]:
            finite = [v if math.isfinite(v) else 0.0 for v in values]
            lo, hi = min(finite), max(finite)
            return [0.5] * len(finite) if hi == lo else [
                (v - lo) / (hi - lo) for v in finite]

        isp_n = normalize([r.isp_m_s if hasattr(r, 'isp_m_s') else r.isp_vacuum_s * 9.80665 for r in results])
        cstar_n = normalize([r.cstar_m_s for r in results])
        cf_n = normalize([r.cf_vacuum if hasattr(r, 'cf_vacuum') and r.cf_vacuum > 0 else r.cf for r in results])
        tc_n = normalize([r.t_chamber_k for r in results])
        inv_mw_n = normalize([1.0 / max(r.molecular_weight, 0.001) for r in results])
        gamma_n = normalize([r.gamma for r in results])

        for i, (result, color, name) in enumerate(zip(results, colors, names)):
            values = [isp_n[i], cstar_n[i], cf_n[i], tc_n[i], inv_mw_n[i], gamma_n[i]]
            values_closed = values + values[:1]
            ax.plot(angles_closed, values_closed, "o-", color=color,
                   linewidth=1.6, markersize=3.5, label=name)
            ax.fill(angles_closed, values_closed, alpha=0.08, color=color)
        ax.legend(loc="upper right", bbox_to_anchor=(1.5, 1.18), fontsize=6.5,
                 framealpha=0.9)
        ax.set_title("Performance Radar", fontsize=9, pad=22)

    def clear(self) -> None:
        """Clear all displayed results."""
        self._results.clear()
        for child in self._perf_scroll.winfo_children():
            child.destroy()
        for child in self._species_scroll.winfo_children():
            child.destroy()
        for child in self._compare_scroll.winfo_children():
            child.destroy()
