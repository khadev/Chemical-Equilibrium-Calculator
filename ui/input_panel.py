"""
ui/input_panel.py
====================
Formulation input panel. Pure View component: emits callbacks to the
controller (MainWindow) and never touches the calculation engine
directly.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from core.theme_manager import ThemeManager
from models.formulation import Formulation, UserReactant
from tools.numeric_utils import safe_float, safe_int
from tools.settings_manager import SettingsManager
from ui.dialogs.species_picker_dialog import SpeciesPickerDialog
from ui.dialogs.user_reactant_dialog import UserReactantDialog

log = logging.getLogger(__name__)


class InputPanel(ctk.CTkScrollableFrame):
    """
    Scrollable formulation input panel.

    Callbacks (set by the owner after construction):
        on_calculate(Formulation)
        on_validate(Formulation)
        on_save_inp(Formulation)
        on_load_inp()
        on_clear()
    """

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        colors = ThemeManager().get_colors()
        super().__init__(master, fg_color=colors["bg"], label_text="")
        self._settings = SettingsManager()
        self._user_reactants: List[UserReactant] = []

        self.on_calculate: Optional[Callable[[Formulation], None]] = None
        self.on_validate: Optional[Callable[[Formulation], None]] = None
        self.on_save_inp: Optional[Callable[[Formulation], None]] = None
        self.on_load_inp: Optional[Callable[[], None]] = None
        self.on_clear: Optional[Callable[[], None]] = None

        self._build()

    # ── Build ─────────────────────────────────────────────────────────
    def _build(self) -> None:
        colors = ThemeManager().get_colors()
        tr = self._settings.tr

        self._oxidizer_group = self._make_species_group(
            tr("oxidizer"), "oxidizer")
        self._fuel_group = self._make_species_group(tr("fuel"), "fuel")
        self._make_user_reactant_group()
        self._make_conditions_group()
        self._make_name_group()

        self._validation_label = ctk.CTkLabel(
            self, text="", justify="left", wraplength=300,
            text_color=colors["success"])
        self._validation_label.pack(fill="x", padx=6, pady=(4, 8))

        self._make_action_buttons()

    def _make_species_group(self, label: str, role: str) -> ctk.CTkFrame:
        colors = ThemeManager().get_colors()
        frame = ctk.CTkFrame(self, fg_color=colors["surface"], corner_radius=8)
        frame.pack(fill="x", padx=4, pady=6)

        ctk.CTkLabel(
            frame, text=label, font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 2))

        select_row = ctk.CTkFrame(frame, fg_color="transparent")
        select_row.pack(fill="x", padx=10, pady=2)
        name_label = ctk.CTkLabel(
            select_row, text="— not selected —", anchor="w",
            font=ctk.CTkFont(family="Courier", size=12),
            fg_color=colors["surface_alt"], corner_radius=4,
            text_color=colors["text"])
        name_label.pack(side="left", fill="x", expand=True, padx=(0, 6),
                        pady=2, ipady=4)
        select_btn = ctk.CTkButton(
            select_row, text="Select…", width=80, height=30,
            command=lambda: self._open_picker(role))
        select_btn.pack(side="left")

        temp_row = ctk.CTkFrame(frame, fg_color="transparent")
        temp_row.pack(fill="x", padx=10, pady=(4, 2))
        ctk.CTkLabel(temp_row, text="Temperature (K):", width=130,
                    anchor="w").pack(side="left")
        temp_var = ctk.StringVar(value="298.0")
        ctk.CTkEntry(temp_row, textvariable=temp_var, width=90).pack(side="left")

        weight_row = ctk.CTkFrame(frame, fg_color="transparent")
        weight_row.pack(fill="x", padx=10, pady=(2, 10))
        ctk.CTkLabel(weight_row, text="Weight (wt%):", width=130,
                    anchor="w").pack(side="left")
        weight_var = ctk.StringVar(value="68.0" if role == "oxidizer" else "18.0")
        ctk.CTkEntry(weight_row, textvariable=weight_var, width=90).pack(side="left")

        setattr(self, f"_{role}_name_label", name_label)
        setattr(self, f"_{role}_name_var", ctk.StringVar(value=""))
        setattr(self, f"_{role}_temp_var", temp_var)
        setattr(self, f"_{role}_weight_var", weight_var)
        return frame

    def _make_user_reactant_group(self) -> None:
        colors = ThemeManager().get_colors()
        frame = ctk.CTkFrame(self, fg_color=colors["surface"], corner_radius=8)
        frame.pack(fill="x", padx=4, pady=6)

        ctk.CTkLabel(
            frame, text="User-Defined Reactants  (HTPB, MCCN…)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            frame,
            text="Generates: name=X wt=Y t,k=Z h,kj/mol=W  El amt…",
            font=ctk.CTkFont(size=9), text_color=colors["text_secondary"],
            wraplength=280, justify="left"
        ).pack(anchor="w", padx=10)

        self._reactant_list_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._reactant_list_frame.pack(fill="x", padx=10, pady=4)

        ctk.CTkButton(
            frame, text="＋  Add User-Defined Reactant", height=32,
            fg_color=colors["surface_alt"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._open_reactant_dialog
        ).pack(fill="x", padx=10, pady=(2, 10))

    def _make_conditions_group(self) -> None:
        colors = ThemeManager().get_colors()
        frame = ctk.CTkFrame(self, fg_color=colors["surface"], corner_radius=8)
        frame.pack(fill="x", padx=4, pady=6)

        ctk.CTkLabel(
            frame, text="Operating Conditions",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 6))

        self._pc_var = self._labeled_entry(frame, "Chamber Pressure (bar):", 50.0)
        self._of_var = self._labeled_entry(frame, "O/F Ratio:", 2.5)
        self._pe_var = self._labeled_entry(frame, "Exit Pressure (bar):", 1.0)
        self._ar_var = self._labeled_entry(frame, "Area Ratio Ae/At:", 10.0)
        self._tcest_var = self._labeled_entry(frame, "Temp Estimate (K):", 3800)

        self._frozen_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame, text="Frozen chemistry", variable=self._frozen_var
        ).pack(anchor="w", padx=10, pady=(2, 10))

    def _make_name_group(self) -> None:
        colors = ThemeManager().get_colors()
        frame = ctk.CTkFrame(self, fg_color=colors["surface"], corner_radius=8)
        frame.pack(fill="x", padx=4, pady=6)
        ctk.CTkLabel(
            frame, text="Formulation Name",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 4))
        self._name_var = ctk.StringVar(value="Formulation 1")
        ctk.CTkEntry(frame, textvariable=self._name_var).pack(
            fill="x", padx=10, pady=(0, 10))

    def _labeled_entry(
            self, parent: ctk.CTkFrame, label: str, default: float
    ) -> ctk.StringVar:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text=label, width=170, anchor="w").pack(side="left")
        var = ctk.StringVar(value=str(default))
        ctk.CTkEntry(row, textvariable=var, width=90).pack(side="left")
        return var

    def _make_action_buttons(self) -> None:
        colors = ThemeManager().get_colors()
        frame = ctk.CTkFrame(self, fg_color=colors["surface"], corner_radius=8)
        frame.pack(fill="x", padx=4, pady=(6, 12))

        ctk.CTkLabel(
            frame, text="Actions", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 6))

        self._calculate_btn = ctk.CTkButton(
            frame, text="▶  Calculate", height=42,
            fg_color=colors["button_ok"], hover_color="#43A047",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._fire_calculate)
        self._calculate_btn.pack(fill="x", padx=10, pady=(0, 6))

        row1 = ctk.CTkFrame(frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(
            row1, text="✓  Validate", height=32,
            fg_color=colors["surface_alt"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._fire_validate
        ).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(
            row1, text="Clear", height=32,
            fg_color=colors["button_danger"], hover_color="#EF5350",
            command=self._fire_clear
        ).pack(side="left", expand=True, fill="x", padx=(3, 0))

        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(2, 10))
        ctk.CTkButton(
            row2, text="📂 Load .inp", height=30,
            fg_color=colors["surface_alt"], text_color=colors["text"],
            hover_color=colors["border"],
            command=self._fire_load
        ).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(
            row2, text="💾 Save .inp", height=30,
            fg_color=colors["surface_alt"], text_color=colors["text"],
            hover_color=colors["border"],
            command=self._fire_save
        ).pack(side="left", expand=True, fill="x", padx=(3, 0))

    # ── Species picker / reactant dialog ─────────────────────────────
    def _open_picker(self, role: str) -> None:
        current = getattr(self, f"_{role}_name_var").get()
        SpeciesPickerDialog(
            self.winfo_toplevel(), mode=role, current_name=current,
            on_select=lambda name: self._set_species(role, name))

    def _set_species(self, role: str, name: str) -> None:
        getattr(self, f"_{role}_name_var").set(name)
        label = getattr(self, f"_{role}_name_label")
        label.configure(text=name)

    def _open_reactant_dialog(self) -> None:
        UserReactantDialog(
            self.winfo_toplevel(), on_confirm=self._add_user_reactant)

    def _add_user_reactant(self, reactant: UserReactant) -> None:
        self._user_reactants.append(reactant)
        self._render_reactant_list()

    def _render_reactant_list(self) -> None:
        colors = ThemeManager().get_colors()
        for child in self._reactant_list_frame.winfo_children():
            child.destroy()
        for i, reactant in enumerate(self._user_reactants):
            row = ctk.CTkFrame(self._reactant_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row, text=reactant.to_inp_line(), anchor="w",
                font=ctk.CTkFont(size=9), text_color=colors["accent"],
                wraplength=220, justify="left"
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="✕", width=24, height=24,
                fg_color=colors["button_danger"], hover_color="#EF5350",
                command=lambda idx=i: self._remove_reactant(idx)
            ).pack(side="left", padx=(4, 0))

    def _remove_reactant(self, index: int) -> None:
        if 0 <= index < len(self._user_reactants):
            del self._user_reactants[index]
            self._render_reactant_list()

    # ── Build/load Formulation ───────────────────────────────────────
    def get_formulation(self) -> Formulation:
        """Read all input widgets into a fresh :class:`Formulation`."""
        f = Formulation()
        f.name = self._name_var.get().strip() or "Formulation 1"
        f.oxidizer_name = self._oxidizer_name_var.get()
        f.oxidizer_temperature_k = safe_float(self._oxidizer_temp_var.get(), 298.0)
        f.oxidizer_weight_pct = safe_float(self._oxidizer_weight_var.get(), 68.0)
        f.fuel_name = self._fuel_name_var.get()
        f.fuel_temperature_k = safe_float(self._fuel_temp_var.get(), 298.0)
        f.fuel_weight_pct = safe_float(self._fuel_weight_var.get(), 18.0)
        f.chamber_pressure_bar = safe_float(self._pc_var.get(), 50.0)
        f.of_ratio = safe_float(self._of_var.get(), 2.5)
        f.exit_pressure_bar = safe_float(self._pe_var.get(), 1.0)
        f.area_ratio = safe_float(self._ar_var.get(), 10.0)
        f.tcest_k = safe_int(self._tcest_var.get(), 3800)
        f.frozen = bool(self._frozen_var.get())
        f.user_reactants = [r.__dict__.copy() for r in self._user_reactants]
        for r_dict in f.user_reactants:
            r_dict["composition"] = dict(r_dict["composition"])
        return f

    def load_formulation(self, f: Formulation) -> None:
        """Populate all input widgets from ``f`` without firing callbacks."""
        self._name_var.set(f.name)
        self._set_species("oxidizer", f.oxidizer_name)
        self._oxidizer_temp_var.set(str(f.oxidizer_temperature_k))
        self._oxidizer_weight_var.set(str(f.oxidizer_weight_pct))
        self._set_species("fuel", f.fuel_name)
        self._fuel_temp_var.set(str(f.fuel_temperature_k))
        self._fuel_weight_var.set(str(f.fuel_weight_pct))
        self._pc_var.set(str(f.chamber_pressure_bar))
        self._of_var.set(str(f.of_ratio))
        self._pe_var.set(str(f.exit_pressure_bar))
        self._ar_var.set(str(f.area_ratio))
        self._tcest_var.set(str(f.tcest_k))
        self._frozen_var.set(f.frozen)
        self._user_reactants = [UserReactant(**d) for d in f.user_reactants]
        self._render_reactant_list()

    def clear(self) -> None:
        """Reset the panel to a blank formulation."""
        self.load_formulation(Formulation())
        self._validation_label.configure(text="")

    def show_validation(self, passed: bool, errors: List[str],
                        warnings: List[str]) -> None:
        """Display validation feedback in the panel."""
        colors = ThemeManager().get_colors()
        lines = [f"✗  {e}" for e in errors] + [f"⚠  {w}" for w in warnings]
        if passed and not errors:
            self._validation_label.configure(
                text="✓  Validation passed.", text_color=colors["success"])
        else:
            self._validation_label.configure(
                text="\n".join(lines), text_color=colors["error"])

    def set_calculate_enabled(self, enabled: bool) -> None:
        """Enable or disable the Calculate button (e.g. while a run is active)."""
        self._calculate_btn.configure(
            state="normal" if enabled else "disabled")

    # ── Callback firing ───────────────────────────────────────────────
    def _fire_calculate(self) -> None:
        if self.on_calculate:
            self.on_calculate(self.get_formulation())

    def _fire_validate(self) -> None:
        if self.on_validate:
            self.on_validate(self.get_formulation())

    def _fire_save(self) -> None:
        if self.on_save_inp:
            self.on_save_inp(self.get_formulation())

    def _fire_load(self) -> None:
        if self.on_load_inp:
            self.on_load_inp()

    def _fire_clear(self) -> None:
        self.clear()
        if self.on_clear:
            self.on_clear()
