"""
ui/dialogs/nozzle_dialog.py — Nozzle Designer
===============================================
Uses IsentropicFlow from logic_layer — all formulas are correct.
Shows nozzle contour + Mach number profile in a responsive matplotlib canvas.
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QWidget, QAbstractItemView, QSplitter,
    QApplication
)
from PySide6.QtGui import QFont

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import (
        FigureCanvasQTAgg as FigureCanvas,
        NavigationToolbar2QT as NavToolbar,
    )
    MPL = True
except ImportError:
    MPL = False

from engine.logic_layer import CEAResult, NozzleCalculator


class NozzleDesignerDialog(QDialog):
    """
    Nozzle Designer with proper isentropic calculations.
    • Calculate button triggers NozzleCalculator (Logic Layer)
    • Shows nozzle contour profile
    • Shows Mach number distribution along nozzle
    • All responsive — no fixed sizes
    """

    def __init__(self, result: Optional[CEAResult] = None, parent=None):
        super().__init__(parent)
        self._result = result
        self._calc   = NozzleCalculator()
        self._data   = None

        self.setWindowTitle("🚀  Nozzle Designer — Isentropic Flow")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(1000, 700)
        self.resize(1100, 760)
        self._build()
        if result and result.success:
            self._run_calc()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet("background:#1A237E;")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16,12,16,12)
        t = QLabel("  🚀  Nozzle Designer — Isentropic Flow Analysis")
        t.setStyleSheet("color:#FFF; font-size:15px; font-weight:bold;")
        hdr_lay.addWidget(t)
        hdr_lay.addStretch()
        note = QLabel("All calculations use correct isentropic flow relations")
        note.setStyleSheet("color:#B0BEC5; font-size:10px;")
        hdr_lay.addWidget(note)
        root.addWidget(hdr)

        # Body splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # Left: inputs + results table
        left = self._build_left()
        left.setMinimumWidth(300)
        left.setMaximumWidth(380)
        splitter.addWidget(left)

        # Right: plots
        self._plot_area = self._build_plots()
        splitter.addWidget(self._plot_area)
        splitter.setSizes([340, 720])
        root.addWidget(splitter, 1)

        # Bottom close
        btm = QWidget()
        btm_lay = QHBoxLayout(btm)
        btm_lay.setContentsMargins(12,8,12,8)
        copy_btn = QPushButton("📋  Copy Results")
        copy_btn.setObjectName("btn_secondary")
        copy_btn.clicked.connect(self._copy)
        btm_lay.addWidget(copy_btn)
        btm_lay.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.accept)
        btm_lay.addWidget(close_btn)
        root.addWidget(btm)

    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        inp_grp = QGroupBox("Design Parameters")
        inp_form = QFormLayout(inp_grp)
        inp_form.setHorizontalSpacing(12)
        inp_form.setVerticalSpacing(10)
        inp_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._thrust_spin = QDoubleSpinBox()
        self._thrust_spin.setRange(0.01, 10000.0)
        self._thrust_spin.setValue(10.0)
        self._thrust_spin.setSuffix(" kN")
        self._thrust_spin.setDecimals(3)
        inp_form.addRow("Design Thrust:", self._thrust_spin)

        # Read-only info from CEA
        self._gamma_lbl = QLabel("—")
        inp_form.addRow("γ (from CEA):", self._gamma_lbl)
        self._cstar_lbl = QLabel("—")
        inp_form.addRow("C* m/s:", self._cstar_lbl)
        self._pc_lbl = QLabel("—")
        inp_form.addRow("Pc (bar):", self._pc_lbl)
        self._ae_at_lbl = QLabel("—")
        inp_form.addRow("Ae/At:", self._ae_at_lbl)
        lay.addWidget(inp_grp)

        if self._result and self._result.success:
            self._gamma_lbl.setText(f"{self._result.gamma:.4f}")
            self._cstar_lbl.setText(f"{self._result.cstar:.1f}")
            self._pc_lbl.setText(f"{self._result.p_chamber:.2f}")
            self._ae_at_lbl.setText(f"{self._result.ae_at:.2f}")

        calc_btn = QPushButton("▶  Calculate Nozzle")
        calc_btn.setObjectName("btn_run")
        calc_btn.setMinimumHeight(40)
        calc_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Fixed)
        calc_btn.clicked.connect(self._run_calc)
        lay.addWidget(calc_btn)

        # Results table
        res_grp = QGroupBox("Nozzle Geometry & Performance")
        res_lay = QVBoxLayout(res_grp)
        self._res_table = QTableWidget()
        self._res_table.setColumnCount(3)
        self._res_table.setHorizontalHeaderLabels(["Parameter","Value","Unit"])
        self._res_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._res_table.verticalHeader().setVisible(False)
        self._res_table.setAlternatingRowColors(True)
        self._res_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self._res_table.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Expanding)
        res_lay.addWidget(self._res_table)
        lay.addWidget(res_grp, 1)
        return w

    def _build_plots(self) -> QWidget:
        w = QWidget()
        self._plot_root = QVBoxLayout(w)
        self._plot_root.setContentsMargins(0, 0, 0, 0)
        if MPL:
            self._ph = QLabel(
                "📈  Run Calculate to see nozzle contour and Mach profile")
            self._ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ph.setStyleSheet("color:#9E9E9E; font-size:13px; padding:40px;")
            self._plot_root.addWidget(self._ph)
        return w

    def _run_calc(self) -> None:
        if not self._result or not self._result.success:
            self._res_table.setRowCount(1)
            self._res_table.setItem(
                0,0, QTableWidgetItem("Error"))
            self._res_table.setItem(
                0,1, QTableWidgetItem("Run CEA first"))
            return

        data = self._calc.calculate(
            self._result, self._thrust_spin.value())
        self._data = data

        if "error" in data:
            self._res_table.setRowCount(1)
            self._res_table.setItem(0,0, QTableWidgetItem("Error"))
            self._res_table.setItem(0,1, QTableWidgetItem(data["error"]))
            return

        # Populate table
        rows = data.get("rows", [])
        self._res_table.setRowCount(len(rows))
        for i, (p, v, u) in enumerate(rows):
            self._res_table.setItem(i, 0, QTableWidgetItem(p))
            vi = QTableWidgetItem(v)
            vi.setFont(QFont("Courier New",10,QFont.Weight.Bold))
            vi.setForeground(__import__("PySide6.QtGui",fromlist=["QColor"]).QColor("#1A237E"))
            self._res_table.setItem(i, 1, vi)
            self._res_table.setItem(i, 2, QTableWidgetItem(u))

        # Build plots
        if MPL:
            self._build_nozzle_plots(data)

    def _build_nozzle_plots(self, data: dict) -> None:
        # Clear
        for i in range(self._plot_root.count()-1,-1,-1):
            item = self._plot_root.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        fig = Figure(figsize=(9,7), dpi=95, facecolor="#FAFAFA")
        fig.suptitle("Nozzle Design — Isentropic Flow",
                     fontsize=13, fontweight="bold", color="#1A237E")

        x_mm   = data.get("profile_x", [])
        r_mm   = data.get("profile_r", [])
        m_vals = data.get("mach_vals", [])
        params = data.get("params", {})

        # ── Plot 1: Nozzle contour ────────────────────────────────────
        ax1 = fig.add_subplot(2, 1, 1)
        if x_mm and r_mm:
            ax1.plot(x_mm, r_mm, "b-", linewidth=2.5, label="Nozzle wall")
            ax1.plot(x_mm, [-r for r in r_mm], "b-", linewidth=2.5)
            ax1.fill_between(x_mm, r_mm, [-r for r in r_mm],
                             alpha=0.08, color="#3F51B5")
            # Throat annotation
            rt_mm = params.get("rt_m",0)*1000
            ax1.axvline(x=0, color="#E53935", linewidth=1.5,
                        linestyle="--", label="Throat")
            ax1.annotate(
                f"Throat\nDt={params.get('dt_mm',0):.1f}mm",
                xy=(0, rt_mm),
                xytext=(max(x_mm)*0.1, rt_mm*1.4),
                textcoords="data", fontsize=8, color="#E53935",
                arrowprops=dict(arrowstyle="->", color="#E53935"),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFF",
                          edgecolor="#E53935", alpha=0.9))
            # Exit annotation
            de_mm = params.get("de_mm",0)
            re_mm = params.get("re_m",0)*1000
            ax1.annotate(
                f"Exit\nDe={de_mm:.1f}mm",
                xy=(max(x_mm), re_mm),
                xytext=(max(x_mm)*0.75, re_mm*1.3),
                textcoords="data", fontsize=8, color="#2E7D32",
                arrowprops=dict(arrowstyle="->", color="#2E7D32"),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFF",
                          edgecolor="#2E7D32", alpha=0.9))
        ax1.set_xlabel("Axial Position  x  (mm)", fontsize=9)
        ax1.set_ylabel("Radius  r  (mm)", fontsize=9)
        ax1.set_title("Nozzle Contour Profile", fontsize=10)
        ax1.legend(fontsize=8, loc="upper left")
        ax1.set_facecolor("#FAFAFA")
        ax1.grid(True, color="#E0E0E0", linewidth=0.5, linestyle="--")
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        ax1.set_aspect("equal", adjustable="datalim")

        # ── Plot 2: Mach number distribution ─────────────────────────
        ax2 = fig.add_subplot(2, 1, 2)
        if x_mm and m_vals:
            ax2.plot(x_mm, m_vals, "r-", linewidth=2.5, label="Mach number")
            ax2.axhline(y=1.0, color="#757575", linewidth=1.2,
                        linestyle=":", label="M=1 (throat)")
            ax2.fill_between(x_mm, 1.0, m_vals, where=[m>=1 for m in m_vals],
                             alpha=0.1, color="#E53935",
                             label="Supersonic region")
            M_exit = params.get("M_exit", 0)
            if M_exit > 1:
                ax2.annotate(
                    f"Me = {M_exit:.3f}",
                    xy=(max(x_mm), M_exit),
                    xytext=(max(x_mm)*0.7, M_exit*0.85),
                    textcoords="data", fontsize=9, color="#1A237E",
                    fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#1A237E"),
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="#E8EAF6",
                              edgecolor="#3F51B5", alpha=0.9))
        ax2.set_xlabel("Axial Position  x  (mm)", fontsize=9)
        ax2.set_ylabel("Mach Number  M", fontsize=9)
        ax2.set_title("Mach Number Distribution", fontsize=10)
        ax2.legend(fontsize=8, loc="upper left")
        ax2.set_facecolor("#FAFAFA")
        ax2.grid(True, color="#E0E0E0", linewidth=0.5, linestyle="--")
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

        fig.tight_layout(rect=[0,0,1,0.96])

        canvas  = FigureCanvas(fig)
        toolbar = NavToolbar(canvas, self)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Expanding)
        self._plot_root.addWidget(toolbar)
        self._plot_root.addWidget(canvas, 1)
        canvas.draw()

    def _copy(self) -> None:
        if not self._data:
            return
        rows = self._data.get("rows", [])
        lines = ["\t".join(["Parameter","Value","Unit"])]
        lines += ["\t".join([p,v,u]) for p,v,u in rows]
        QApplication.clipboard().setText("\n".join(lines))
