"""
ui/dialogs/nozzle_dialog.py
==============================
Nozzle Designer tool dialog. Uses :class:`IsentropicFlow` from the
Logic Layer for all geometry calculations — renders a contour profile
and Mach-number distribution via embedded matplotlib.
"""
from __future__ import annotations

import math
from typing import Optional

import customtkinter as ctk

from core.fallback_calculator import IsentropicFlow
from core.theme_manager import ThemeManager
from models.cea_result import CEAResult, G0
from tools.numeric_utils import safe_float
from ui.dialogs.base_dialog import BaseDialog

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg, NavigationToolbar2Tk)
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class NozzleDesignerDialog(BaseDialog):
    """Nozzle Designer — isentropic flow geometry and Mach profile."""

    def __init__(self, parent: ctk.CTk, result: Optional[CEAResult] = None) -> None:
        self._result = result
        super().__init__(parent, title="🚀  Nozzle Designer", width=920, height=680)
        self._build()
        if result and result.success:
            self._calculate()

    def _build(self) -> None:
        colors = ThemeManager().get_colors()

        header = ctk.CTkLabel(
            self.body, text="Nozzle Designer — Isentropic Flow Analysis",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=colors["accent"])
        header.pack(anchor="w", pady=(0, 8))

        content = ctk.CTkFrame(self.body, fg_color="transparent")
        content.pack(fill="both", expand=True)

        left = ctk.CTkFrame(content, fg_color=colors["surface"], width=280, corner_radius=8)
        left.pack(side="left", fill="y", padx=(0, 8))

        ctk.CTkLabel(
            left, text="Design Parameters", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(10, 6))

        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text="Design Thrust (kN):", width=140, anchor="w").pack(side="left")
        self._thrust_var = ctk.StringVar(value="10.0")
        ctk.CTkEntry(row, textvariable=self._thrust_var, width=80).pack(side="left")

        info_frame = ctk.CTkFrame(left, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=(8, 4))
        self._info_labels = {}
        for key, label in [
            ("gamma", "γ (from CEA):"), ("cstar", "C* (m/s):"),
            ("pc", "Pc (bar):"), ("ae_at", "Ae/At:"),
        ]:
            r = ctk.CTkFrame(info_frame, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=label, width=110, anchor="w").pack(side="left")
            value_label = ctk.CTkLabel(r, text="—", anchor="e")
            value_label.pack(side="left")
            self._info_labels[key] = value_label

        if self._result and self._result.success:
            self._info_labels["gamma"].configure(text=f"{self._result.gamma:.4f}")
            self._info_labels["cstar"].configure(text=f"{self._result.cstar_m_s:.1f}")
            self._info_labels["pc"].configure(text=f"{self._result.p_chamber_bar:.2f}")
            self._info_labels["ae_at"].configure(text=f"{self._result.area_ratio:.2f}")

        ctk.CTkButton(
            left, text="▶  Calculate Nozzle", height=40,
            command=self._calculate
        ).pack(fill="x", padx=10, pady=(10, 6))

        ctk.CTkLabel(
            left, text="Geometry & Performance", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 4))

        self._results_scroll = ctk.CTkScrollableFrame(left, fg_color=colors["surface_alt"])
        self._results_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        right = ctk.CTkFrame(content, fg_color=colors["surface"], corner_radius=8)
        right.pack(side="left", fill="both", expand=True)
        self._plot_container = right
        if MATPLOTLIB_AVAILABLE:
            self._plot_placeholder = ctk.CTkLabel(
                right, text="📈  Run Calculate to see nozzle contour and Mach profile",
                text_color=colors["text_secondary"])
            self._plot_placeholder.pack(expand=True)
        else:
            ctk.CTkLabel(right, text="matplotlib not installed").pack(expand=True)

        close_btn = ctk.CTkButton(
            self.body, text="Close", height=36,
            fg_color=colors["surface"], text_color=colors["text"],
            border_width=1, border_color=colors["border"],
            hover_color=colors["border"],
            command=self.on_close)
        close_btn.pack(fill="x", pady=(8, 0))

    def _calculate(self) -> None:
        if not self._result or not self._result.success:
            self._render_error("Run a CEA calculation first.")
            return

        gamma = self._result.gamma or 1.22
        cstar = self._result.cstar_m_s or 1800.0
        pc_pa = self._result.p_chamber_bar * 1e5
        area_ratio = self._result.area_ratio or 10.0
        isp_s = self._result.isp_vacuum_s
        thrust_kn = safe_float(self._thrust_var.get(), 10.0)

        thrust_n = thrust_kn * 1000.0
        exhaust_velocity = isp_s * G0
        mass_flow = thrust_n / max(exhaust_velocity, 1e-6)
        throat_area = mass_flow * cstar / pc_pa
        throat_radius = math.sqrt(throat_area / math.pi)
        exit_area = throat_area * area_ratio
        exit_radius = math.sqrt(exit_area / math.pi)

        mach_exit = IsentropicFlow.mach_from_area_ratio(area_ratio, gamma)
        exit_temp = self._result.t_chamber_k * IsentropicFlow.temperature_ratio(
            mach_exit, gamma)
        exit_pressure_pa = pc_pa * IsentropicFlow.pressure_ratio(mach_exit, gamma)
        cf = IsentropicFlow.thrust_coefficient(
            gamma, exit_pressure_pa / pc_pa, area_ratio)

        half_angle_deg = 15.0
        cone_length = (exit_radius - throat_radius) / math.tan(
            math.radians(half_angle_deg))
        bell_length = 0.80 * cone_length

        contraction_ratio = 5.0
        chamber_area = throat_area * contraction_ratio
        chamber_radius = math.sqrt(chamber_area / math.pi)
        l_star = 1.2
        chamber_length = l_star * throat_area / chamber_area

        rows = [
            ("Mass flow ṁ", f"{mass_flow:.4f}", "kg/s"),
            ("Throat diameter Dt", f"{throat_radius * 2000:.2f}", "mm"),
            ("Throat area At", f"{throat_area * 1e4:.4f}", "cm²"),
            ("Exit diameter De", f"{exit_radius * 2000:.2f}", "mm"),
            ("Exit area Ae", f"{exit_area * 1e4:.4f}", "cm²"),
            ("Exit Mach Me", f"{mach_exit:.4f}", "—"),
            ("Exit temp Te", f"{exit_temp:.1f}", "K"),
            ("Exit pressure Pe", f"{exit_pressure_pa / 1e5:.4f}", "bar"),
            ("Thrust coeff Cf", f"{cf:.4f}", "—"),
            ("Chamber diam Dc", f"{chamber_radius * 2000:.1f}", "mm"),
            ("Chamber length Lc", f"{chamber_length * 1000:.1f}", "mm"),
            ("Bell length (80%)", f"{bell_length * 1000:.1f}", "mm"),
            ("Exhaust velocity Ve", f"{exhaust_velocity:.1f}", "m/s"),
        ]
        self._render_rows(rows)

        if MATPLOTLIB_AVAILABLE:
            x_norm, area_ratios, mach_values = IsentropicFlow.nozzle_profile(
                area_ratio, gamma, 120)
            x_mm = [x * bell_length * 1000 for x in x_norm]
            r_mm = [throat_radius * 1000 * math.sqrt(ar) for ar in area_ratios]
            self._render_plots(x_mm, r_mm, mach_values, throat_radius * 2000,
                              exit_radius * 2000, mach_exit)

    def _render_error(self, message: str) -> None:
        colors = ThemeManager().get_colors()
        for child in self._results_scroll.winfo_children():
            child.destroy()
        ctk.CTkLabel(self._results_scroll, text=message,
                    text_color=colors["error"]).pack(pady=10)

    def _render_rows(self, rows: list) -> None:
        colors = ThemeManager().get_colors()
        for child in self._results_scroll.winfo_children():
            child.destroy()
        for param, value, unit in rows:
            row = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=param, anchor="w",
                        font=ctk.CTkFont(size=10)).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(row, text=f"{value} {unit}", anchor="e",
                        font=ctk.CTkFont(family="Courier", size=10, weight="bold"),
                        text_color=colors["accent"]).pack(side="right")

    def _render_plots(self, x_mm, r_mm, mach_values, dt_mm, de_mm, m_exit) -> None:
        for child in self._plot_container.winfo_children():
            child.destroy()

        fig = Figure(figsize=(6, 6), dpi=92, facecolor="#FAFAFA")
        fig.suptitle("Nozzle Design — Isentropic Flow",
                     fontsize=12, fontweight="bold", color="#1A237E")

        ax1 = fig.add_subplot(2, 1, 1)
        ax1.plot(x_mm, r_mm, "b-", linewidth=2.2, label="Nozzle wall")
        ax1.plot(x_mm, [-r for r in r_mm], "b-", linewidth=2.2)
        ax1.fill_between(x_mm, r_mm, [-r for r in r_mm], alpha=0.08, color="#3F51B5")
        ax1.axvline(x=0, color="#E53935", linewidth=1.2, linestyle="--", label="Throat")
        ax1.annotate(f"Dt={dt_mm:.1f}mm", xy=(0, r_mm[0]),
                    xytext=(max(x_mm) * 0.08, r_mm[0] * 1.5),
                    fontsize=7, color="#E53935",
                    arrowprops=dict(arrowstyle="->", color="#E53935"))
        ax1.annotate(f"De={de_mm:.1f}mm", xy=(max(x_mm), r_mm[-1]),
                    xytext=(max(x_mm) * 0.65, r_mm[-1] * 1.2),
                    fontsize=7, color="#2E7D32",
                    arrowprops=dict(arrowstyle="->", color="#2E7D32"))
        ax1.set_xlabel("x (mm)", fontsize=8)
        ax1.set_ylabel("r (mm)", fontsize=8)
        ax1.set_title("Nozzle Contour Profile", fontsize=9)
        ax1.legend(fontsize=7, loc="upper left")
        ax1.grid(True, color="#E0E0E0", linewidth=0.4, linestyle="--")
        ax1.set_aspect("equal", adjustable="datalim")

        ax2 = fig.add_subplot(2, 1, 2)
        ax2.plot(x_mm, mach_values, "r-", linewidth=2.2, label="Mach number")
        ax2.axhline(y=1.0, color="#757575", linewidth=1.0, linestyle=":", label="M=1")
        ax2.fill_between(x_mm, 1.0, mach_values,
                         where=[m >= 1 for m in mach_values],
                         alpha=0.1, color="#E53935")
        ax2.annotate(f"Me={m_exit:.3f}", xy=(max(x_mm), mach_values[-1]),
                    xytext=(max(x_mm) * 0.6, mach_values[-1] * 0.8),
                    fontsize=8, color="#1A237E", fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#1A237E"))
        ax2.set_xlabel("x (mm)", fontsize=8)
        ax2.set_ylabel("Mach number M", fontsize=8)
        ax2.set_title("Mach Number Distribution", fontsize=9)
        ax2.legend(fontsize=7, loc="upper left")
        ax2.grid(True, color="#E0E0E0", linewidth=0.4, linestyle="--")

        fig.tight_layout(rect=(0, 0, 1, 0.94))

        canvas = FigureCanvasTkAgg(fig, master=self._plot_container)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, self._plot_container, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="top", fill="x")
        canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
