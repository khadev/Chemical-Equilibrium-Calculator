"""
ui/dialogs/tool_dialog.py
============================
Generic tool dialog: renders inputs from a :class:`ToolSpec`, runs its
``compute()`` function, and displays the resulting rows (plus an
optional matplotlib line chart). No per-tool UI code is required —
adding a new tool to ``core/analysis_tools.py`` is enough for it to
appear, fully functional, in the Tools menu.
"""
from __future__ import annotations

from typing import Dict, Optional

import customtkinter as ctk

from core.analysis_tools import ToolOutput, ToolSpec
from core.theme_manager import ThemeManager
from models.cea_result import CEAResult
from models.formulation import Formulation
from tools.numeric_utils import safe_float
from ui.dialogs.base_dialog import BaseDialog

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class ToolDialog(BaseDialog):
    """Generic dialog driven entirely by a :class:`ToolSpec`."""

    def __init__(
            self, parent: ctk.CTk, spec: ToolSpec,
            result: Optional[CEAResult], formulation: Optional[Formulation],
    ) -> None:
        self._spec = spec
        self._result = result
        self._formulation = formulation
        self._input_vars: Dict[str, ctk.Variable] = {}
        self._plot_canvas = None  # see note in results_panel.py re: _canvas

        super().__init__(parent, title=f"{spec.category}  ›  {spec.name}",
                         width=680, height=620)
        self._build()

    def _build(self) -> None:
        colors = ThemeManager().get_colors()

        ctk.CTkLabel(
            self.body, text=self._spec.name,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w")
        ctk.CTkLabel(
            self.body, text=self._spec.description,
            font=ctk.CTkFont(size=10), text_color=colors["text_secondary"],
            wraplength=560, justify="left"
        ).pack(anchor="w", pady=(2, 10))

        if self._spec.needs_result and (self._result is None or not self._result.success):
            ctk.CTkLabel(
                self.body, text="⚠  This tool requires a successful "
                                "calculation. Run Calculate first, then "
                                "reopen this tool.",
                text_color=colors["warning"], wraplength=560, justify="left"
            ).pack(anchor="w", pady=(0, 10))

        button_row = ctk.CTkFrame(self.body, fg_color="transparent")
        button_row.pack(fill="x", pady=(8, 0), side="bottom")
        ctk.CTkButton(
            button_row, text="▶  Calculate", height=38,
            command=self._run_compute
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(
            button_row, text="Close", height=38,
            fg_color=colors["surface"], text_color=colors["text"],
            border_width=1, border_color=colors["border"],
            hover_color=colors["border"], command=self.on_close
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        body_row = ctk.CTkFrame(self.body, fg_color="transparent")
        body_row.pack(fill="both", expand=True)

        left = ctk.CTkScrollableFrame(
            body_row, fg_color=colors["surface"], corner_radius=8, width=240)
        left.pack(side="left", fill="y", padx=(0, 8))
        self._build_inputs(left)

        right = ctk.CTkFrame(body_row, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self._output_scroll = ctk.CTkScrollableFrame(
            right, fg_color=colors["surface"])
        self._output_scroll.pack(fill="both", expand=True)

        self._chart_container = ctk.CTkFrame(right, fg_color="transparent",
                                             height=220)

        if not self._spec.inputs:
            self._run_compute()

    def _build_inputs(self, parent: ctk.CTkFrame) -> None:
        colors = ThemeManager().get_colors()
        if not self._spec.inputs:
            ctk.CTkLabel(
                parent, text="No inputs required.\nClick Calculate.",
                text_color=colors["text_secondary"]
            ).pack(padx=10, pady=20)
            return

        ctk.CTkLabel(
            parent, text="Inputs", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(10, 6))

        for field in self._spec.inputs:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=4)
            label_text = field.label
            if field.unit:
                label_text += f" ({field.unit})"
            ctk.CTkLabel(row, text=label_text, anchor="w",
                        font=ctk.CTkFont(size=10), wraplength=180,
                        justify="left").pack(anchor="w")
            if field.is_dropdown:
                var = ctk.StringVar(value=field.options[0] if field.options else "")
                ctk.CTkOptionMenu(row, variable=var, values=field.options,
                                 width=190).pack(anchor="w", pady=(2, 0))
            else:
                var = ctk.StringVar(value=str(self._resolve_default(field)))
                ctk.CTkEntry(row, textvariable=var, width=190).pack(
                    anchor="w", pady=(2, 0))
            self._input_vars[field.key] = var

    def _resolve_default(self, field) -> float:
        """Pull a live default from the active result when sensible."""
        if self._result and self._result.success:
            live_map = {
                "chamber_temp_k": self._result.t_chamber_k,
                "gamma": self._result.gamma,
                "gamma_products": self._result.gamma,
                "molecular_weight": self._result.molecular_weight,
                "cstar_m_s": self._result.cstar_m_s,
                "chamber_pressure_bar": self._result.p_chamber_bar,
                "isp_s": self._result.isp_vacuum_s,
            }
            if field.key in live_map and live_map[field.key]:
                return live_map[field.key]
        return field.default

    def _run_compute(self) -> None:
        values: Dict[str, float] = {}
        for key, var in self._input_vars.items():
            if key.startswith("_"):
                values[key] = var.get()
            else:
                values[key] = safe_float(var.get())

        try:
            output: ToolOutput = self._spec.compute(
                self._result, self._formulation, values)
        except Exception as exc:
            output = ToolOutput(rows=[("Error", str(exc), "")])

        self._render_output(output)

    def _render_output(self, output: ToolOutput) -> None:
        colors = ThemeManager().get_colors()
        for child in self._output_scroll.winfo_children():
            child.destroy()

        is_text_block = (len(output.rows) == 1
                         and output.rows[0][1] == "(see notes below)")
        if is_text_block:
            textbox = ctk.CTkTextbox(
                self._output_scroll, fg_color=colors["console_bg"],
                font=ctk.CTkFont(family="Courier", size=10), height=300)
            textbox.pack(fill="both", expand=True, padx=4, pady=4)
            textbox.insert("end", output.notes)
        else:
            header = ctk.CTkFrame(self._output_scroll, fg_color=colors["accent"],
                                  corner_radius=4)
            header.pack(fill="x", pady=(0, 2))
            for text, width in [("Parameter", 180), ("Value", 110), ("Unit", 0)]:
                ctk.CTkLabel(
                    header, text=text, width=width if width else 0,
                    anchor="w", font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=colors["text_on_accent"]
                ).pack(side="left", padx=(10 if width else 4, 4), pady=5,
                      fill="x" if not width else None, expand=(not width))

            for i, row in enumerate(output.rows):
                param, value, unit = row[0], row[1], row[2]
                row_bg = colors["table_alt"] if i % 2 == 1 else colors["surface"]
                line = ctk.CTkFrame(self._output_scroll, fg_color=row_bg,
                                   corner_radius=4)
                line.pack(fill="x", pady=1)
                ctk.CTkLabel(line, text=param, anchor="w", width=180,
                            font=ctk.CTkFont(size=10, weight="bold")
                            ).pack(side="left", padx=(10, 4), pady=4)
                ctk.CTkLabel(line, text=value, anchor="e", width=110,
                            font=ctk.CTkFont(family="Courier", size=10,
                                            weight="bold"),
                            text_color=colors["accent"]).pack(side="left", pady=4)
                ctk.CTkLabel(line, text=unit, anchor="w",
                            text_color=colors["text_secondary"],
                            font=ctk.CTkFont(size=9)
                            ).pack(side="left", padx=4, pady=4, fill="x", expand=True)

            if output.notes:
                note_card = ctk.CTkFrame(self._output_scroll, fg_color=colors["surface_alt"],
                                        corner_radius=6)
                note_card.pack(fill="x", pady=(10, 4))
                ctk.CTkLabel(
                    note_card, text="ℹ  " + output.notes,
                    font=ctk.CTkFont(size=10), text_color=colors["text_secondary"],
                    wraplength=330, justify="left"
                ).pack(anchor="w", padx=8, pady=6)

        if output.chart_x and output.chart_y and MATPLOTLIB_AVAILABLE:
            self._render_chart(output)
        else:
            self._chart_container.pack_forget()

    def _render_chart(self, output: ToolOutput) -> None:
        for child in self._chart_container.winfo_children():
            child.destroy()
        self._chart_container.pack(fill="x", pady=(6, 0))

        fig = Figure(figsize=(5.5, 2.4), dpi=88, facecolor="#FAFAFA")
        ax = fig.add_subplot(111)
        ax.plot(output.chart_x, output.chart_y, "o-", color="#3F51B5",
               linewidth=2, markersize=5)
        ax.set_xlabel(output.chart_xlabel, fontsize=8)
        ax.set_ylabel(output.chart_ylabel, fontsize=8)
        ax.set_title(output.chart_title, fontsize=9)
        ax.grid(True, color="#E0E0E0", linewidth=0.5, linestyle="--")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self._chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="x")
        self._plot_canvas = canvas
