"""
ui/widgets/results_tabs.py — UI LAYER
QTabWidget with tabs: Performance, Compare, Plots, Console.
Responsive plots with scrollbar support.
"""
from __future__ import annotations
from typing import List, Optional, Dict
import logging

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QTextEdit, QPushButton, QSizePolicy,
    QAbstractItemView, QApplication, QScrollArea
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
    logging.getLogger(__name__).warning("matplotlib not installed")

from engine.calculation_engine import CEAResult

log = logging.getLogger(__name__)

PALETTE = [
    "#3F51B5", "#00ACC1", "#43A047", "#FB8C00",
    "#E53935", "#8E24AA", "#00897B", "#F4511E",
]


class ResultsTabs(QWidget):
    copy_done = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: List[CEAResult] = []
        self._sessions: List[str] = []
        self._canvas: Optional[FigureCanvas] = None
        self._toolbar: Optional[NavToolbar] = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._tabs)

        self._perf_tab = self._mk_perf_tab()
        self._compare_tab = self._mk_compare_tab()
        self._plots_tab = self._mk_plots_tab()
        self._console_tab = self._mk_console_tab()

        self._tabs.addTab(self._perf_tab, "📋 Performance")
        self._tabs.addTab(self._compare_tab, "🔬 Compare")
        self._tabs.addTab(self._plots_tab, "📈 Plots")
        self._tabs.addTab(self._console_tab, "📟 Console")

    def _mk_perf_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.addStretch()
        copy_btn = QPushButton("📋 Copy Table")
        copy_btn.setObjectName("btn_secondary")
        copy_btn.setFixedHeight(28)
        copy_btn.clicked.connect(self._copy_perf)
        top.addWidget(copy_btn)
        lay.addLayout(top)

        self._perf_table = QTableWidget()
        self._perf_table.setColumnCount(4)
        self._perf_table.setHorizontalHeaderLabels(["Parameter", "Value", "Unit", "Description"])
        self._perf_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._perf_table.horizontalHeader().resizeSection(0, 140)
        self._perf_table.horizontalHeader().resizeSection(1, 110)
        self._perf_table.horizontalHeader().resizeSection(2, 65)
        self._perf_table.verticalHeader().setVisible(False)
        self._perf_table.setAlternatingRowColors(True)
        self._perf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._perf_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self._perf_table, 2)

        sp_lbl = QLabel("Exit Plane Composition")
        sp_lbl.setObjectName("lbl_header")
        lay.addWidget(sp_lbl)

        self._sp_table = QTableWidget()
        self._sp_table.setColumnCount(3)
        self._sp_table.setHorizontalHeaderLabels(["Species", "Mass Fraction", "%"])
        self._sp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._sp_table.verticalHeader().setVisible(False)
        self._sp_table.setAlternatingRowColors(True)
        self._sp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sp_table.setMaximumHeight(160)
        lay.addWidget(self._sp_table, 1)
        return w

    def _mk_compare_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)

        top = QHBoxLayout()
        top.addStretch()
        cp2 = QPushButton("📋 Copy Compare Table")
        cp2.setObjectName("btn_secondary")
        cp2.setFixedHeight(28)
        cp2.clicked.connect(self._copy_compare)
        top.addWidget(cp2)
        lay.addLayout(top)

        self._cmp_table = QTableWidget()
        self._cmp_table.setAlternatingRowColors(True)
        self._cmp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._cmp_table.verticalHeader().setVisible(False)
        self._cmp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._cmp_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self._cmp_table)
        return w

    def _mk_plots_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plots_scroll = QScrollArea()
        self._plots_scroll.setWidgetResizable(True)
        self._plots_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._plots_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._plots_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #FAFAFA;
            }
            QScrollBar:vertical {
                background: #F0F0F0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #C0C0C0;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3F51B5;
            }
            QScrollBar:horizontal {
                background: #F0F0F0;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #C0C0C0;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #3F51B5;
            }
        """)
        
        self._plots_container = QWidget()
        self._plots_container.setStyleSheet("background: #FAFAFA;")
        self._plots_container_layout = QVBoxLayout(self._plots_container)
        self._plots_container_layout.setContentsMargins(10, 10, 10, 10)
        self._plots_container_layout.setSpacing(10)
        
        self._plots_scroll.setWidget(self._plots_container)
        layout.addWidget(self._plots_scroll)

        if MPL:
            self._plots_placeholder = QLabel(
                "📈  Plots appear here after a successful calculation.\n"
                "    All graphs are responsive and scrollable.")
            self._plots_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._plots_placeholder.setStyleSheet("color:#9E9E9E; font-size:14px; padding:40px;")
            self._plots_container_layout.addWidget(self._plots_placeholder)
        else:
            self._plots_container_layout.addWidget(QLabel("matplotlib not installed — pip install matplotlib"))
        
        self._plots_container_layout.addStretch()
        return w

    def _mk_console_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        self._console = QTextEdit()
        self._console.setReadOnly(True)
        self._console.setFont(QFont("Courier New", 10))
        self._console.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._console.append("Chemical Equilibrium Calculator — Console\n" + "─"*50)
        lay.addWidget(self._console)
        return w

    def show_result(self, result: CEAResult, session_name: str = "", units: dict = None) -> None:
        units = units or {"pressure": "bar", "temperature": "K", "isp": "m/s"}
        if result not in self._results:
            self._results.append(result)
        if session_name and session_name not in self._sessions:
            self._sessions.append(session_name)
        self._update_perf_table(result, units)
        self._update_compare()

    def update_plots(self, results: List[CEAResult], colors: List[str] = None, form_dicts: List[dict] = None) -> None:
        if not MPL:
            return
        ok = [r for r in results if r and r.success and r.cstar > 0]
        if not ok:
            return
        colors = colors or [PALETTE[i % len(PALETTE)] for i in range(len(ok))]
        form_dicts = form_dicts or [{}] * len(ok)

        # Clear old plots container
        for i in range(self._plots_container_layout.count() - 1, -1, -1):
            item = self._plots_container_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        # Create figure with proper title positioning
        fig = self._build_figure(ok, colors, form_dicts)
        canvas = FigureCanvas(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas.setMinimumHeight(850)
        
        toolbar = NavToolbar(canvas, self)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #F0F0F0;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        
        self._plots_container_layout.addWidget(toolbar)
        self._plots_container_layout.addWidget(canvas)
        self._plots_container_layout.addStretch()
        
        canvas.draw()
        self._canvas = canvas
        self._toolbar = toolbar
        self._tabs.setCurrentWidget(self._plots_tab)
        log.debug("Plots rebuilt for %d sessions", len(ok))

    def _build_figure(self, results, colors, form_dicts) -> Figure:
        names = [r.name or f"Run{i+1}" for i, r in enumerate(results)]
        isp_ms = [r.isp_ms for r in results]
        cstar = [r.cstar for r in results]
        cf = [r.cf for r in results]
        tc = [r.t_chamber for r in results]
        mw = [r.mw for r in results]
        gamma = [r.gamma for r in results]
        of_v = [d.get("of_ratio", 2.5) for d in form_dicts]

        # Create figure with proper size
        fig = Figure(figsize=(15, 13), dpi=100, facecolor="#FAFAFA")
        
        # Adjust layout to make room for title
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.07, right=0.97, hspace=0.5, wspace=0.45)
        
        # Add title at the top
        fig.suptitle("Propellant Performance Analysis", fontsize=18, fontweight="bold", 
                     color="#1A237E", y=0.98)

        style = {
            "axes.facecolor": "#FFFFFF",
            "axes.edgecolor": "#9FA8DA",
            "axes.labelcolor": "#424242",
            "text.color": "#212121",
            "grid.color": "#E0E0E0",
            "legend.facecolor": "#FFFFFF",
            "legend.edgecolor": "#9FA8DA",
        }

        # Create 2x3 grid for bar charts (rows 0-1), then row 2 for pie, Isp/O/F, radar
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.5, wspace=0.45)
        
        # First row (3 bar charts)
        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[0, 1])
        ax3 = fig.add_subplot(gs[0, 2])
        
        # Second row (3 bar charts)
        ax4 = fig.add_subplot(gs[1, 0])
        ax5 = fig.add_subplot(gs[1, 1])
        ax6 = fig.add_subplot(gs[1, 2])
        
        # Third row
        pie_ax = fig.add_subplot(gs[2, 0])
        of_ax = fig.add_subplot(gs[2, 1])
        radar_ax = fig.add_subplot(gs[2, 2], polar=True)

        axes = [ax1, ax2, ax3, ax4, ax5, ax6]

        datasets = [
            (isp_ms, "Specific Impulse Isp (m/s)", True, False),
            (cstar, "Characteristic Velocity C* (m/s)", True, False),
            (cf, "Thrust Coefficient Cf", True, False),
            (tc, "Chamber Temperature Tc (K)", False, False),
            (mw, "Molecular Weight (g/mol)", False, True),
            (gamma, "Specific Heat Ratio γ", False, False),
        ]
        
        for ax, (vals, title, higher, lower_better) in zip(axes, datasets):
            self._bar(ax, names, vals, colors, title, style, higher, lower_better)

        self._pie(pie_ax, results[0], names[0], style)
        self._isp_of(of_ax, results, of_v, form_dicts, colors, style)
        self._radar(radar_ax, results, colors, names, style)

        return fig

    def _bar(self, ax, names, vals, colors, title, style, higher=True, lower_better=False) -> None:
        if not vals or all(v == 0 for v in vals):
            ax.text(0.5, 0.5, "No data available", transform=ax.transAxes, 
                    ha="center", va="center", color=style["text.color"])
            ax.set_title(title, color=style["text.color"], fontsize=11, pad=10, fontweight="bold")
            ax.set_facecolor(style["axes.facecolor"])
            return
        
        x = np.arange(len(names))
        bars = ax.bar(x, vals, color=colors, edgecolor=style["axes.edgecolor"], 
                     linewidth=0.8, zorder=3)
        
        mx = max(vals)
        mn = min(vals)
        best_idx = (vals.index(min(vals)) if lower_better else vals.index(max(vals))) if len(vals) > 1 else -1
        
        for i, (bar, v) in enumerate(zip(bars, vals)):
            is_best = i == best_idx and len(vals) > 1
            # Add value labels on top of bars
            ax.annotate(f"{v:.1f}", 
                       xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                       xytext=(0, 5), textcoords="offset points", 
                       ha="center", va="bottom", fontsize=8,
                       fontweight="bold" if is_best else "normal", 
                       color=style["text.color"])
            if is_best and mx > 0:
                ax.annotate("★", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height() + mx * 0.06),
                           ha="center", fontsize=14, color=colors[i])
        
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8, color=style["text.color"])
        ax.set_title(title, color=style["text.color"], fontsize=11, pad=10, fontweight="bold")
        ax.set_xlim(-0.6, len(names) - 0.4)
        y_min = mn * 0.9 if mn > 0 else mn * 1.1
        y_max = mx * 1.15
        ax.set_ylim(y_min, y_max)
        ax.grid(True, axis='y', linestyle='--', alpha=0.3, linewidth=0.5)
        self._style_ax(ax, style)

    def _pie(self, ax, result, name, style) -> None:
        mf = result.mass_fractions if result else {}
        if not mf:
            ax.text(0.5, 0.5, "Species data\nnot available", ha="center", va="center",
                    color=style["text.color"], fontsize=10, transform=ax.transAxes)
            ax.set_title(f"Exit Composition\n({name})", color=style["text.color"], fontsize=11, pad=10, fontweight="bold")
            return
        
        sorted_sp = sorted(mf.items(), key=lambda x: -x[1])[:8]
        sp_n = [s[0] for s in sorted_sp]
        sp_v = [s[1] for s in sorted_sp]
        other = max(0.0, 1.0 - sum(sp_v))
        if other > 0.001:
            sp_n.append("Other")
            sp_v.append(other)
        
        wedges, texts, ats = ax.pie(sp_v, labels=sp_n, autopct="%1.1f%%",
                                    colors=plt.cm.tab10.colors[:len(sp_v)],
                                    textprops={"color": style["text.color"], "fontsize": 7},
                                    wedgeprops={"linewidth": 0.8, "edgecolor": style["axes.edgecolor"]},
                                    startangle=90, pctdistance=0.75)
        
        for at in ats:
            at.set_fontsize(6.5)
            at.set_bbox(dict(boxstyle="round,pad=0.2", facecolor="#FAFAFA", edgecolor="none", alpha=0.7))
        
        ax.set_title(f"Exit Composition\n({name})", color=style["text.color"], fontsize=11, pad=10, fontweight="bold")

    def _isp_of(self, ax, results, of_vals, form_dicts, colors, style) -> None:
        ax.set_xlabel("Oxidizer/Fuel Ratio (O/F)", fontsize=10, fontweight="bold", labelpad=8)
        ax.set_ylabel("Specific Impulse Isp (m/s)", fontsize=10, fontweight="bold", labelpad=8)
        ax.set_title("Isp vs O/F Ratio", fontsize=12, fontweight="bold", pad=12)
        self._style_ax(ax, style)
        
        if not results:
            ax.text(0.5, 0.5, "No data available", transform=ax.transAxes, 
                    ha="center", va="center", color=style["text.color"])
            return

        groups: Dict = {}
        for r, of, fd, col in zip(results, of_vals, form_dicts, colors):
            pc = round(fd.get("chamber_pressure", 50), 1)
            groups.setdefault(pc, []).append((of, r.isp_ms, r, col))

        all_of, all_isp = [], []
        
        for gi, (pc, pts) in enumerate(sorted(groups.items())):
            pts_s = sorted(pts, key=lambda p: p[0])
            of_x = [p[0] for p in pts_s]
            isp_y = [p[1] for p in pts_s]
            col = PALETTE[gi % len(PALETTE)]
            label = f"Pc = {pc:.0f} bar" if len(groups) > 1 else None
            
            ax.plot(of_x, isp_y, "o-", color=col, linewidth=2, markersize=8,
                   markerfacecolor="white", markeredgecolor=col, 
                   markeredgewidth=1.5, label=label, zorder=3)
            
            for of_v, isp_v, r, rcol in pts_s:
                ax.annotate(r.name, xy=(of_v, isp_v), xytext=(5, 5), 
                           textcoords="offset points", fontsize=7, color=rcol,
                           bbox=dict(boxstyle="round,pad=0.2", facecolor="#FAFAFA",
                                    edgecolor=rcol, alpha=0.7, linewidth=0.5))
            all_of.extend(of_x)
            all_isp.extend(isp_y)

        if all_isp:
            bi = all_isp.index(max(all_isp))
            ax.scatter([all_of[bi]], [all_isp[bi]], color="#FFB300", s=150, zorder=6,
                      marker="o", edgecolors='black', linewidth=1.5)
            ax.annotate(f"Best: {all_isp[bi]:.0f} m/s", 
                       xy=(all_of[bi], all_isp[bi]), xytext=(12, 12),
                       textcoords="offset points", fontsize=8, color="#E65100", 
                       fontweight="bold",
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFF8E1", 
                                edgecolor="#FFB300", alpha=0.9))
        
        if len(groups) > 1:
            ax.legend(fontsize=8, facecolor=style["legend.facecolor"], 
                     edgecolor=style["legend.edgecolor"], loc="best")

    def _radar(self, ax, results, colors, names, style) -> None:
        CATS = ["Isp", "C*", "Cf", "Tc", "1/MW", "γ"]
        N = len(CATS)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles_c = angles + angles[:1]
        
        ax.set_facecolor(style["axes.facecolor"])
        ax.spines["polar"].set_color(style["axes.edgecolor"])
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=7, color=style["text.color"])
        ax.set_xticks(angles)
        ax.set_xticklabels([])
        
        for angle, cat in zip(angles, CATS):
            deg = np.degrees(angle) % 360
            ha = "center"
            if deg < 5 or deg > 355:
                ha = "center"
            elif 5 <= deg < 175:
                ha = "left"
            elif 175 <= deg < 185:
                ha = "center"
            else:
                ha = "right"
            va = "bottom" if deg < 5 or deg > 355 else "center"
            ax.text(angle, 1.35, cat, ha=ha, va=va, fontsize=9, fontweight="bold", 
                   color=style["text.color"])

        def _norm(vals):
            mn, mx = min(vals), max(vals)
            if mx == mn:
                return [0.5] * len(vals)
            return [(v - mn) / (mx - mn) for v in vals]

        isp_n = _norm([r.isp_ms for r in results])
        cs_n = _norm([r.cstar for r in results])
        cf_n = _norm([r.cf for r in results])
        tc_n = _norm([r.t_chamber for r in results])
        mw_n = _norm([1 / max(r.mw, 0.001) for r in results])
        gm_n = _norm([r.gamma for r in results])

        for i, (r, col, name) in enumerate(zip(results, colors, names)):
            vals = [isp_n[i], cs_n[i], cf_n[i], tc_n[i], mw_n[i], gm_n[i]]
            vals_c = vals + vals[:1]
            ax.plot(angles_c, vals_c, "o-", color=col, linewidth=2, markersize=5, label=name)
            ax.fill(angles_c, vals_c, alpha=0.1, color=col)
            
            for angle, v, raw in zip(angles, vals, 
                [r.isp_ms, r.cstar, r.cf, r.t_chamber, r.mw, r.gamma]):
                ax.annotate(f"{raw:.1f}", xy=(angle, v), xytext=(0, 7), 
                           textcoords="offset points", ha="center", fontsize=6, color=col,
                           bbox=dict(boxstyle="round,pad=0.15", facecolor="#FAFAFA", 
                                    edgecolor=col, alpha=0.75, linewidth=0.4))
        
        ax.legend(loc="upper right", bbox_to_anchor=(1.5, 1.2), fontsize=7,
                 facecolor=style["legend.facecolor"], edgecolor=style["legend.edgecolor"], 
                 framealpha=0.9)
        ax.set_title("Performance Radar", color=style["text.color"], fontsize=12, 
                    pad=30, fontweight="bold")

    def _style_ax(self, ax, style) -> None:
        ax.set_facecolor(style["axes.facecolor"])
        for spine in ax.spines.values():
            spine.set_edgecolor(style["axes.edgecolor"])
            spine.set_linewidth(0.8)
        ax.tick_params(colors=style["text.color"], labelsize=8, length=4, width=0.8)
        ax.yaxis.label.set_color(style["axes.labelcolor"])
        ax.xaxis.label.set_color(style["axes.labelcolor"])
        ax.grid(True, color=style["grid.color"], alpha=0.4, linewidth=0.6, linestyle="--")

    def _update_perf_table(self, result: CEAResult, units: dict) -> None:
        rows = result.to_table_rows(units)
        self._perf_table.setRowCount(len(rows))
        for i, row_data in enumerate(rows):
            param, val, unit = row_data[0], row_data[1], row_data[2]
            tip = row_data[3] if len(row_data) > 3 else ""
            color = row_data[4] if len(row_data) > 4 else ""
            items = [QTableWidgetItem(param), QTableWidgetItem(val), QTableWidgetItem(unit), QTableWidgetItem(tip)]
            items[0].setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            items[1].setFont(QFont("Segoe UI", 10))
            if color:
                items[1].setForeground(QColor(color))
            for j, item in enumerate(items):
                self._perf_table.setItem(i, j, item)
        self._perf_table.resizeRowsToContents()

        mf = result.mass_fractions
        sp_sorted = sorted(mf.items(), key=lambda x: -x[1])
        self._sp_table.setRowCount(len(sp_sorted))
        for i, (sp, frac) in enumerate(sp_sorted):
            self._sp_table.setItem(i, 0, QTableWidgetItem(sp))
            self._sp_table.setItem(i, 1, QTableWidgetItem(f"{frac:.6f}"))
            pct = QTableWidgetItem(f"{frac * 100:.2f}%")
            pct.setForeground(QColor("#3F51B5"))
            self._sp_table.setItem(i, 2, pct)

    def _update_compare(self) -> None:
        if not self._results:
            return
        PARAMS = [
            ("Isp (m/s)", lambda r: r.isp_ms, "{:.1f}"),
            ("Isp (s)", lambda r: r.isp_vac, "{:.2f}"),
            ("C* (m/s)", lambda r: r.cstar, "{:.1f}"),
            ("Cf", lambda r: r.cf, "{:.4f}"),
            ("Cf vac", lambda r: r.cf_vac, "{:.4f}"),
            ("Ae/At", lambda r: r.ae_at, "{:.2f}"),
            ("Tc (K)", lambda r: r.t_chamber, "{:.0f}"),
            ("MW (g/mol)", lambda r: r.mw, "{:.3f}"),
            ("γ", lambda r: r.gamma, "{:.4f}"),
            ("Mach exit", lambda r: r.mach_exit, "{:.3f}"),
            ("Method", lambda r: r.method, "{}"),
        ]
        n = len(self._results)
        self._cmp_table.setRowCount(len(PARAMS))
        self._cmp_table.setColumnCount(n + 1)
        hdrs = ["Parameter"] + [r.name or f"Run{i+1}" for i, r in enumerate(self._results)]
        self._cmp_table.setHorizontalHeaderLabels(hdrs)
        for i, (pname, extractor, fmt) in enumerate(PARAMS):
            self._cmp_table.setItem(i, 0, QTableWidgetItem(pname))
            vals = []
            for r in self._results:
                try:
                    vals.append(float(str(extractor(r)).replace("%", "")))
                except:
                    vals.append(0.0)
            best = max(vals) if vals else 0
            for j, (r, v) in enumerate(zip(self._results, vals)):
                try:
                    s = fmt.format(extractor(r))
                except:
                    s = "—"
                item = QTableWidgetItem(s)
                item.setFont(QFont("Segoe UI", 9))
                is_best = v == best and n > 1 and v > 0
                if is_best:
                    item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    item.setForeground(QColor(PALETTE[j % len(PALETTE)]))
                self._cmp_table.setItem(i, j + 1, item)
        self._cmp_table.resizeColumnsToContents()

    def log(self, msg: str) -> None:
        self._console.append(msg)
        sb = self._console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _copy_table(self, table: QTableWidget) -> None:
        rows = table.rowCount()
        cols = table.columnCount()
        hdrs = [table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else "" for c in range(cols)]
        lines = ["\t".join(hdrs)]
        for r in range(rows):
            lines.append("\t".join((table.item(r, c).text() if table.item(r, c) else "") for c in range(cols)))
        QApplication.clipboard().setText("\n".join(lines))
        self.copy_done.emit("Text Copied!")

    def _copy_perf(self) -> None:
        self._copy_table(self._perf_table)

    def _copy_compare(self) -> None:
        self._copy_table(self._cmp_table)

    def clear(self) -> None:
        self._results.clear()
        self._sessions.clear()
        self._perf_table.setRowCount(0)
        self._sp_table.setRowCount(0)
        self._cmp_table.setRowCount(0)