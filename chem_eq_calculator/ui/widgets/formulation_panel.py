"""
ui/widgets/formulation_panel.py  v3
=====================================
NASA_CEA_PROFESSIONAL_STANDARD — View Layer
Light theme, manual Calculate button only (no auto-calculate).
Adds "User Defined Reactants" section under the fuel group.
Toast notifications on clipboard copy.
"""
from __future__ import annotations
from typing import List, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QGroupBox, QScrollArea, QDoubleSpinBox,
    QFrame, QSizePolicy, QListWidget, QListWidgetItem
)
from models.config_manager import tr
from models.species_db import SpeciesDatabase
from engine.inp_builder import UserDefinedReactant


class SpeciesRow(QWidget):
    """Species name + temperature + pick button."""
    pick_requested = Signal(str)

    def __init__(self, role: str, parent=None) -> None:
        super().__init__(parent)
        self._role  = role
        self._name  = ""
        self._enth  = 0.0
        self._comp: Dict[str, float] = {}
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._name_lbl = QLabel("— not selected —")
        self._name_lbl.setStyleSheet(
            "font-family:'Courier New'; font-size:11px;"
            " padding:4px 8px; border:1px solid #9FA8DA;"
            " border-radius:4px; background:#FFFFFF;")
        self._name_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self._name_lbl, 1)

        self._temp_spin = QDoubleSpinBox()
        self._temp_spin.setRange(1.0, 6000.0)
        self._temp_spin.setValue(298.0)
        self._temp_spin.setSuffix(" K")
        self._temp_spin.setDecimals(1)
        self._temp_spin.setFixedWidth(100)
        lay.addWidget(self._temp_spin)

        self._wt_spin = QDoubleSpinBox()
        self._wt_spin.setRange(0.0, 9999.0)
        self._wt_spin.setValue(50.0)
        self._wt_spin.setDecimals(2)
        self._wt_spin.setFixedWidth(80)
        self._wt_spin.setToolTip("Weight (wt) for .inp file")
        lay.addWidget(self._wt_spin)

        icon = "⚗" if self._role == "oxidizer" else "🔥"
        pick_btn = QPushButton(f"{icon} Select")
        pick_btn.setFixedHeight(32)
        pick_btn.setMinimumWidth(72)
        pick_btn.setToolTip(f"Browse {self._role} species database")
        pick_btn.clicked.connect(lambda: self.pick_requested.emit(self._role))
        lay.addWidget(pick_btn)

    def set_species(self, name: str, temp: float,
                    enth: float, comp: Dict[str, float],
                    wt: float = 50.0) -> None:
        self._name = name
        self._enth = enth
        self._comp = comp
        self._name_lbl.setText(name or "— not selected —")
        self._temp_spin.setValue(temp)
        self._wt_spin.setValue(wt)

    def mark_invalid(self, invalid: bool) -> None:
        ok  = ("font-family:'Courier New'; font-size:11px;"
               " padding:4px 8px; border:1px solid #9FA8DA;"
               " border-radius:4px; background:#FFFFFF;")
        err = ("font-family:'Courier New'; font-size:11px;"
               " padding:4px 8px; border:2px solid #E53935;"
               " border-radius:4px; background:#FFF3F3;")
        self._name_lbl.setStyleSheet(err if invalid else ok)

    def to_dict(self) -> dict:
        return {
            "name":     self._name,
            "temp":     self._temp_spin.value(),
            "wt":       self._wt_spin.value(),
            "enthalpy": self._enth,
            "formula":  self._comp,
        }

    def name(self) -> str:
        return self._name


class UserDefinedReactantRow(QWidget):
    """One row in the User Defined Reactants list."""
    edit_requested   = Signal(int)   # row index
    remove_requested = Signal(int)

    def __init__(self, udr: UserDefinedReactant,
                 index: int, parent=None) -> None:
        super().__init__(parent)
        self._udr   = udr
        self._index = index
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        # Name + preview
        comp_str = "  ".join(
            f"{el}={v:.3f}"
            for el, v in self._udr.composition.items())
        lbl = QLabel(
            f"<b>{self._udr.name}</b>  "
            f"wt={self._udr.wt}  T={self._udr.temp_k}K  "
            f"h={self._udr.enthalpy_kj}kJ/mol  "
            f"<span style='color:#3F51B5'>{comp_str}</span>")
        lbl.setStyleSheet("font-size:10px;")
        lbl.setWordWrap(True)
        lay.addWidget(lbl, 1)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(42, 26)
        edit_btn.setStyleSheet(
            "background:#E8EAF6; border:1px solid #9FA8DA;"
            " border-radius:3px; font-size:9px;")
        edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self._index))
        lay.addWidget(edit_btn)

        rem_btn = QPushButton("Remove")
        rem_btn.setFixedSize(56, 26)
        rem_btn.setObjectName("btn_danger")
        rem_btn.setStyleSheet(
            "background:#E53935; color:#fff; border-radius:3px;"
            " font-size:9px; border:none;")
        rem_btn.clicked.connect(
            lambda: self.remove_requested.emit(self._index))
        lay.addWidget(rem_btn)

    def get_udr(self) -> UserDefinedReactant:
        return self._udr


class FormulationPanel(QScrollArea):
    """
    Left-panel formulation input.
    Manual Calculate button only — no auto-calculate triggers.
    Includes User Defined Reactants section.
    """
    formulation_changed   = Signal(dict)
    run_requested         = Signal(dict)
    validate_requested    = Signal(dict)
    save_inp_requested    = Signal(dict)
    load_inp_requested    = Signal()
    species_pick_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._udrs: List[UserDefinedReactant] = []
        self._build()

    def _build(self) -> None:
        container = QWidget()
        self.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ── Oxidizer ──────────────────────────────────────────────────
        ox_grp = QGroupBox("Oxidizer")
        ox_lay = QFormLayout(ox_grp)
        ox_lay.setHorizontalSpacing(10)
        ox_lay.setVerticalSpacing(8)
        ox_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._ox_row = SpeciesRow("oxidizer")
        self._ox_row.pick_requested.connect(self.species_pick_requested)
        ox_lay.addRow("Species:", self._ox_row)
        root.addWidget(ox_grp)

        # ── Fuel ──────────────────────────────────────────────────────
        fu_grp = QGroupBox("Fuel")
        fu_lay = QFormLayout(fu_grp)
        fu_lay.setHorizontalSpacing(10)
        fu_lay.setVerticalSpacing(8)
        fu_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._fu_row = SpeciesRow("fuel")
        self._fu_row.pick_requested.connect(self.species_pick_requested)
        fu_lay.addRow("Species:", self._fu_row)
        root.addWidget(fu_grp)

        # ── User Defined Reactants ────────────────────────────────────
        udr_grp = QGroupBox("User Defined Reactants  (HTPB, MCCN, etc.)")
        udr_lay = QVBoxLayout(udr_grp)
        udr_lay.setSpacing(4)

        udr_note = QLabel(
            "These appear as  name=X wt=Y t,k=Z h,kj/mol=W El amt…  "
            "in the .inp file.")
        udr_note.setStyleSheet("color:#757575; font-size:9px;")
        udr_note.setWordWrap(True)
        udr_lay.addWidget(udr_note)

        self._udr_list_widget = QWidget()
        self._udr_list_lay    = QVBoxLayout(self._udr_list_widget)
        self._udr_list_lay.setContentsMargins(0, 0, 0, 0)
        self._udr_list_lay.setSpacing(3)
        udr_lay.addWidget(self._udr_list_widget)

        add_udr_btn = QPushButton("Add User-Defined Reactant…")
        add_udr_btn.setStyleSheet(
            "background:#E8EAF6; border:1px dashed #9FA8DA;"
            " border-radius:4px; color:#3F51B5; font-size:11px;"
            " padding:6px;")
        add_udr_btn.clicked.connect(self._add_udr)
        udr_lay.addWidget(add_udr_btn)
        root.addWidget(udr_grp)

        # ── Conditions ────────────────────────────────────────────────
        cond_grp = QGroupBox("Operating Conditions")
        cond_form = QFormLayout(cond_grp)
        cond_form.setHorizontalSpacing(10)
        cond_form.setVerticalSpacing(10)
        cond_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._pc_spin = QDoubleSpinBox()
        self._pc_spin.setRange(1.0, 1000.0)
        self._pc_spin.setValue(50.0)
        self._pc_spin.setSuffix(" bar")
        self._pc_spin.setDecimals(2)
        cond_form.addRow("Chamber pressure:", self._pc_spin)

        self._of_spin = QDoubleSpinBox()
        self._of_spin.setRange(0.1, 30.0)
        self._of_spin.setValue(2.5)
        self._of_spin.setDecimals(4)
        cond_form.addRow("O/F ratio:", self._of_spin)

        self._pe_spin = QDoubleSpinBox()
        self._pe_spin.setRange(0.001, 200.0)
        self._pe_spin.setValue(1.0)
        self._pe_spin.setSuffix(" bar")
        self._pe_spin.setDecimals(3)
        cond_form.addRow("Exit pressure:", self._pe_spin)

        self._ar_spin = QDoubleSpinBox()
        self._ar_spin.setRange(1.0, 500.0)
        self._ar_spin.setValue(10.0)
        self._ar_spin.setDecimals(2)
        cond_form.addRow("Area ratio Ae/At:", self._ar_spin)

        self._tcest_spin = QDoubleSpinBox()
        self._tcest_spin.setRange(500, 6000)
        self._tcest_spin.setValue(3800)
        self._tcest_spin.setSuffix(" K")
        self._tcest_spin.setDecimals(0)
        self._tcest_spin.setToolTip("Temperature estimate for CEA solver (tcest,k)")
        cond_form.addRow("Temp. estimate:", self._tcest_spin)

        self._frozen_chk = QCheckBox("Frozen chemistry")
        cond_form.addRow("", self._frozen_chk)
        root.addWidget(cond_grp)

        # ── Name ──────────────────────────────────────────────────────
        name_grp = QGroupBox("Formulation Name")
        name_form = QFormLayout(name_grp)
        name_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._name_edit = QLineEdit("Formulation 1")
        name_form.addRow("Name:", self._name_edit)
        root.addWidget(name_grp)

        # ── Validation result ─────────────────────────────────────────
        self._val_lbl = QLabel("")
        self._val_lbl.setWordWrap(True)
        self._val_lbl.setObjectName("status_ok")
        root.addWidget(self._val_lbl)

        # ── Actions (manual buttons only — no auto-triggers) ──────────
        act_grp = QGroupBox("Actions")
        act_lay = QVBoxLayout(act_grp)
        act_lay.setSpacing(6)

        # Row 1: Validate + Calculate
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self._validate_btn = QPushButton("✓  Validate")
        self._validate_btn.setMinimumHeight(34)
        self._validate_btn.setObjectName("btn_secondary")
        self._validate_btn.setToolTip("Check species and numeric ranges (Ctrl+Shift+V)")
        self._validate_btn.clicked.connect(
            lambda: self.validate_requested.emit(self.get_formulation()))
        row1.addWidget(self._validate_btn, 1)

        self._calc_btn = QPushButton("▶  Calculate")
        self._calc_btn.setMinimumHeight(34)
        self._calc_btn.setToolTip("Run CEA for this formulation (Ctrl+R)")
        self._calc_btn.clicked.connect(
            lambda: self.run_requested.emit(self.get_formulation()))
        row1.addWidget(self._calc_btn, 1)
        act_lay.addLayout(row1)

        # Row 2: Load + Save
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self._load_btn = QPushButton("📂  Load .inp")
        self._load_btn.setMinimumHeight(30)
        self._load_btn.setObjectName("btn_secondary")
        self._load_btn.clicked.connect(self.load_inp_requested)
        row2.addWidget(self._load_btn, 1)

        self._save_btn = QPushButton("💾  Save .inp")
        self._save_btn.setMinimumHeight(30)
        self._save_btn.setObjectName("btn_secondary")
        self._save_btn.clicked.connect(
            lambda: self.save_inp_requested.emit(self.get_formulation()))
        row2.addWidget(self._save_btn, 1)
        act_lay.addLayout(row2)

        # Row 3: Clear (full width)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setMinimumHeight(30)
        self._clear_btn.setObjectName("btn_danger")
        self._clear_btn.clicked.connect(self._clear)
        act_lay.addWidget(self._clear_btn)

        root.addWidget(act_grp)
        root.addStretch()

    # ── User Defined Reactants ─────────────────────────────────────────
    def _add_udr(self, existing: Optional[UserDefinedReactant] = None,
                 edit_index: int = -1) -> None:
        from ui.dialogs.user_defined_reactant_dialog import (
            UserDefinedReactantDialog)
        dlg = UserDefinedReactantDialog(
            existing=existing,
            parent=self.window())
        if dlg.exec():
            udr = dlg.get_reactant()
            if udr:
                if edit_index >= 0:
                    self._udrs[edit_index] = udr
                else:
                    self._udrs.append(udr)
                self._rebuild_udr_list()

    def _edit_udr(self, index: int) -> None:
        if 0 <= index < len(self._udrs):
            self._add_udr(existing=self._udrs[index], edit_index=index)

    def _remove_udr(self, index: int) -> None:
        if 0 <= index < len(self._udrs):
            del self._udrs[index]
            self._rebuild_udr_list()

    def _rebuild_udr_list(self) -> None:
        # Clear all widgets
        while self._udr_list_lay.count():
            item = self._udr_list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Re-add
        for i, udr in enumerate(self._udrs):
            row = UserDefinedReactantRow(udr, i)
            row.edit_requested.connect(self._edit_udr)
            row.remove_requested.connect(self._remove_udr)
            self._udr_list_lay.addWidget(row)

    # ── Public API ─────────────────────────────────────────────────────
    def get_formulation(self) -> dict:
        ox = self._ox_row.to_dict()
        fu = self._fu_row.to_dict()
        return {
            "formulation_name":     self._name_edit.text().strip(),
            "oxidizer_name":        ox["name"],
            "oxidizer_temp":        ox["temp"],
            "oxidizer_wt":          ox["wt"],
            "oxidizer_enthalpy":    ox["enthalpy"],
            "oxidizer_formula":     ox["formula"],
            "fuel_name":            fu["name"],
            "fuel_temp":            fu["temp"],
            "fuel_wt":              fu["wt"],
            "fuel_enthalpy":        fu["enthalpy"],
            "fuel_formula":         fu["formula"],
            "chamber_pressure":     self._pc_spin.value(),
            "of_ratio":             self._of_spin.value(),
            "exit_pressure":        self._pe_spin.value(),
            "area_ratio":           self._ar_spin.value(),
            "tcest":                int(self._tcest_spin.value()),
            "frozen":               self._frozen_chk.isChecked(),
            "user_defined_reactants": [u.to_dict() for u in self._udrs],
        }

    def load_formulation(self, f: dict) -> None:
        if not f:
            return
        self._name_edit.setText(f.get("formulation_name", "Formulation"))
        self._ox_row.set_species(
            f.get("oxidizer_name",""),
            float(f.get("oxidizer_temp", 298)),
            float(f.get("oxidizer_enthalpy", 0)),
            f.get("oxidizer_formula", {}),
            float(f.get("oxidizer_wt", 68)))
        self._fu_row.set_species(
            f.get("fuel_name",""),
            float(f.get("fuel_temp", 298)),
            float(f.get("fuel_enthalpy", 0)),
            f.get("fuel_formula", {}),
            float(f.get("fuel_wt", 18)))
        self._pc_spin.setValue(float(f.get("chamber_pressure", 50)))
        self._of_spin.setValue(float(f.get("of_ratio", 2.5)))
        self._pe_spin.setValue(float(f.get("exit_pressure", 1.0)))
        self._ar_spin.setValue(float(f.get("area_ratio", 10.0)))
        self._tcest_spin.setValue(float(f.get("tcest", 3800)))
        self._frozen_chk.setChecked(bool(f.get("frozen", False)))
        self._udrs = [
            UserDefinedReactant.from_dict(d)
            for d in f.get("user_defined_reactants", [])
        ]
        self._rebuild_udr_list()

    def set_oxidizer(self, name, temp, enth, comp) -> None:
        self._ox_row.set_species(name, temp, enth, comp)

    def set_fuel(self, name, temp, enth, comp) -> None:
        self._fu_row.set_species(name, temp, enth, comp)

    def show_validation(self, passed, errors, warnings) -> None:
        lines = []
        for e in errors:
            lines.append(f"✗  {e}")
            if "oxidizer" in e.lower(): self._ox_row.mark_invalid(True)
            if "fuel"     in e.lower(): self._fu_row.mark_invalid(True)
        for w in warnings:
            lines.append(f"⚠  {w}")
        if passed and not errors:
            self._val_lbl.setText("✓  Validation passed — ready to calculate.")
            self._val_lbl.setObjectName("status_ok")
            self._ox_row.mark_invalid(False)
            self._fu_row.mark_invalid(False)
        else:
            self._val_lbl.setText("\n".join(lines))
            self._val_lbl.setObjectName("status_error")
        self._val_lbl.setStyle(self._val_lbl.style())

    def _clear(self) -> None:
        self._ox_row.set_species("", 298, 0, {})
        self._fu_row.set_species("", 298, 0, {})
        self._pc_spin.setValue(50.0)
        self._of_spin.setValue(2.5)
        self._pe_spin.setValue(1.0)
        self._ar_spin.setValue(10.0)
        self._tcest_spin.setValue(3800)
        self._frozen_chk.setChecked(False)
        self._name_edit.setText("Formulation 1")
        self._val_lbl.setText("")
        self._udrs.clear()
        self._rebuild_udr_list()
        self._ox_row.mark_invalid(False)
        self._fu_row.mark_invalid(False)
