"""
ui/widgets/input_panel.py — Input Panel with working dropdowns
"""
from __future__ import annotations
from typing import List, Dict
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox,
    QPushButton, QDoubleSpinBox, QCheckBox,
    QScrollArea, QSizePolicy, QCompleter
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from models.data_layer import SpeciesDatabase, Formulation


class SearchableComboBox(QComboBox):
    """QComboBox with search/filter - Preserves native arrows"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(20)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(180)
        self.setMinimumHeight(32)

        # Create completer for search functionality
        self._completer = QCompleter(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompleter(self._completer)

    def populate(self, items: List[str]) -> None:
        """Populate from a list; preserves selection."""
        self.blockSignals(True)
        current = self.currentText()
        self.clear()
        self.addItem("— select species —")
        for item in items:
            self.addItem(item)
        # Restore selection if still valid
        idx = self.findText(current)
        self.setCurrentIndex(max(idx, 0))
        # Update completer model
        model = QStandardItemModel(self)
        for item in items:
            model.appendRow(QStandardItem(item))
        self._completer.setModel(model)
        self.blockSignals(False)

    def selected_name(self) -> str:
        txt = self.currentText()
        return "" if txt.startswith("—") else txt


class InputPanel(QScrollArea):
    calculate_requested = Signal(object)
    validate_requested = Signal(object)
    save_inp_requested = Signal(object)
    load_inp_requested = Signal()
    clear_requested = Signal()
    udr_add_requested = Signal(object)

    def __init__(self, db: SpeciesDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._udr_data: List[Dict] = []
        self._build()
        self._populate_dropdowns()

    def _build(self) -> None:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # Oxidizer Group
        ox_grp = QGroupBox("Oxidizer")
        ox_form = QFormLayout(ox_grp)
        ox_form.setHorizontalSpacing(12)
        ox_form.setVerticalSpacing(10)
        ox_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._ox_combo = SearchableComboBox()
        ox_form.addRow("Species:", self._ox_combo)

        self._ox_temp = QDoubleSpinBox()
        self._ox_temp.setRange(1.0, 6000.0)
        self._ox_temp.setValue(298.0)
        self._ox_temp.setSuffix(" K")
        self._ox_temp.setDecimals(1)
        ox_form.addRow("Temperature:", self._ox_temp)

        self._ox_wt = QDoubleSpinBox()
        self._ox_wt.setRange(0.0, 9999.0)
        self._ox_wt.setValue(68.0)
        self._ox_wt.setDecimals(2)
        ox_form.addRow("Weight (wt):", self._ox_wt)
        root.addWidget(ox_grp)

        # Fuel Group
        fu_grp = QGroupBox("Fuel")
        fu_form = QFormLayout(fu_grp)
        fu_form.setHorizontalSpacing(12)
        fu_form.setVerticalSpacing(10)
        fu_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._fu_combo = SearchableComboBox()
        fu_form.addRow("Species:", self._fu_combo)

        self._fu_temp = QDoubleSpinBox()
        self._fu_temp.setRange(1.0, 6000.0)
        self._fu_temp.setValue(298.0)
        self._fu_temp.setSuffix(" K")
        self._fu_temp.setDecimals(1)
        fu_form.addRow("Temperature:", self._fu_temp)

        self._fu_wt = QDoubleSpinBox()
        self._fu_wt.setRange(0.0, 9999.0)
        self._fu_wt.setValue(18.0)
        self._fu_wt.setDecimals(2)
        fu_form.addRow("Weight (wt):", self._fu_wt)
        root.addWidget(fu_grp)

        # User-Defined Reactants Group
        udr_grp = QGroupBox("User-Defined Reactants (HTPB, MCCN…)")
        udr_lay = QVBoxLayout(udr_grp)
        udr_lay.setSpacing(4)

        note = QLabel("Generates: name=HTPB wt=14 t,k=298 h,kj/mol=-58 C 7.075 H 10.650 O 0.063 N 0.223")
        note.setStyleSheet("color:#757575; font-size:9px;")
        note.setWordWrap(True)
        udr_lay.addWidget(note)

        # Dropdown for saved UDRs
        dropdown_label = QLabel("Saved User-Defined Reactants:")
        dropdown_label.setStyleSheet("font-weight:bold; font-size:10px; margin-top:5px;")
        udr_lay.addWidget(dropdown_label)

        self._saved_udr_combo = QComboBox()
        self._saved_udr_combo.addItem("— select saved reactant —")
        self._saved_udr_combo.currentIndexChanged.connect(self._on_saved_udr_selected)
        udr_lay.addWidget(self._saved_udr_combo)

        self._udr_container = QWidget()
        self._udr_vlay = QVBoxLayout(self._udr_container)
        self._udr_vlay.setContentsMargins(0, 0, 0, 0)
        self._udr_vlay.setSpacing(3)
        udr_lay.addWidget(self._udr_container)

        add_btn = QPushButton("+ Add New User-Defined Reactant")
        add_btn.setObjectName("btn_secondary")
        add_btn.setMinimumHeight(34)
        add_btn.clicked.connect(lambda: self.udr_add_requested.emit(None))
        udr_lay.addWidget(add_btn)
        root.addWidget(udr_grp)

        # Operating Conditions Group
        cond_grp = QGroupBox("Operating Conditions")
        cond_form = QFormLayout(cond_grp)
        cond_form.setHorizontalSpacing(12)
        cond_form.setVerticalSpacing(10)
        cond_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._pc = QDoubleSpinBox()
        self._pc.setRange(1.0, 1000.0)
        self._pc.setValue(50.0)
        self._pc.setSuffix(" bar")
        self._pc.setDecimals(2)
        cond_form.addRow("Chamber Pressure:", self._pc)

        self._of = QDoubleSpinBox()
        self._of.setRange(0.1, 30.0)
        self._of.setValue(2.5)
        self._of.setDecimals(4)
        cond_form.addRow("O/F Ratio:", self._of)

        self._pe = QDoubleSpinBox()
        self._pe.setRange(0.001, 200.0)
        self._pe.setValue(1.0)
        self._pe.setSuffix(" bar")
        self._pe.setDecimals(3)
        cond_form.addRow("Exit Pressure:", self._pe)

        self._ar = QDoubleSpinBox()
        self._ar.setRange(1.0, 500.0)
        self._ar.setValue(10.0)
        self._ar.setDecimals(2)
        cond_form.addRow("Area Ratio Ae/At:", self._ar)

        self._tcest = QDoubleSpinBox()
        self._tcest.setRange(500, 6000)
        self._tcest.setValue(3800)
        self._tcest.setSuffix(" K")
        self._tcest.setDecimals(0)
        cond_form.addRow("Temp Estimate:", self._tcest)

        self._frozen = QCheckBox("Frozen chemistry")
        cond_form.addRow("", self._frozen)
        root.addWidget(cond_grp)

        # Formulation Name Group
        name_grp = QGroupBox("Formulation Name")
        name_form = QFormLayout(name_grp)
        name_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._name = QLineEdit("Formulation 1")
        self._name.setMinimumHeight(30)
        name_form.addRow("Name:", self._name)
        root.addWidget(name_grp)

        # Validation Label
        self._val_lbl = QLabel("")
        self._val_lbl.setWordWrap(True)
        self._val_lbl.setObjectName("status_ok")
        root.addWidget(self._val_lbl)

        # Actions Group
        act_grp = QGroupBox("Actions")
        act_lay = QVBoxLayout(act_grp)
        act_lay.setSpacing(8)

        self._calc_btn = QPushButton("Calculate")
        self._calc_btn.setObjectName("btn_run")
        self._calc_btn.setMinimumHeight(42)
        self._calc_btn.clicked.connect(lambda: self.calculate_requested.emit(self.get_formulation()))
        act_lay.addWidget(self._calc_btn)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        val_btn = QPushButton("Validate")
        val_btn.setObjectName("btn_secondary")
        val_btn.setMinimumHeight(32)
        val_btn.clicked.connect(lambda: self.validate_requested.emit(self.get_formulation()))
        row1.addWidget(val_btn)

        clr_btn = QPushButton("Clear")
        clr_btn.setObjectName("btn_danger")
        clr_btn.setMinimumHeight(32)
        clr_btn.clicked.connect(self.clear_requested)
        row1.addWidget(clr_btn)
        act_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        load_btn = QPushButton("Load .inp")
        load_btn.setObjectName("btn_secondary")
        load_btn.setMinimumHeight(32)
        load_btn.clicked.connect(self.load_inp_requested)
        row2.addWidget(load_btn)

        save_btn = QPushButton("Save .inp")
        save_btn.setObjectName("btn_secondary")
        save_btn.setMinimumHeight(32)
        save_btn.clicked.connect(lambda: self.save_inp_requested.emit(self.get_formulation()))
        row2.addWidget(save_btn)
        act_lay.addLayout(row2)
        root.addWidget(act_grp)
        root.addStretch()

    def _populate_dropdowns(self) -> None:
        self._ox_combo.populate(self._db.all_oxidizers())
        self._fu_combo.populate(self._db.all_fuels())

    def refresh_fuel_list(self) -> None:
        self._fu_combo.populate(self._db.all_fuels())

    def refresh_saved_udr_list(self, udr_list: List[dict]) -> None:
        self._saved_udr_combo.blockSignals(True)
        self._saved_udr_combo.clear()
        self._saved_udr_combo.addItem("— select saved reactant —")
        for udr in udr_list:
            self._saved_udr_combo.addItem(udr.get("name", "Unknown"), udr)
        self._saved_udr_combo.blockSignals(False)

    def _on_saved_udr_selected(self, index: int) -> None:
        if index > 0:
            udr_dict = self._saved_udr_combo.itemData(index)
            if udr_dict:
                self.udr_add_requested.emit(udr_dict)
            self._saved_udr_combo.setCurrentIndex(0)

    def get_formulation(self) -> Formulation:
        f = Formulation()
        f.name = self._name.text().strip() or "Formulation 1"
        f.oxidizer_name = self._ox_combo.selected_name()
        f.oxidizer_temp = self._ox_temp.value()
        f.oxidizer_wt = self._ox_wt.value()
        f.fuel_name = self._fu_combo.selected_name()
        f.fuel_temp = self._fu_temp.value()
        f.fuel_wt = self._fu_wt.value()
        f.chamber_pressure = self._pc.value()
        f.of_ratio = self._of.value()
        f.exit_pressure = self._pe.value()
        f.area_ratio = self._ar.value()
        f.tcest = int(self._tcest.value())
        f.frozen = self._frozen.isChecked()
        f.user_reactants = self._udr_data.copy()
        return f

    def load_formulation(self, f: Formulation) -> None:
        widgets = [self._ox_combo, self._fu_combo, self._ox_temp, self._ox_wt,
                   self._fu_temp, self._fu_wt, self._pc, self._of, self._pe,
                   self._ar, self._tcest, self._frozen, self._name]
        for w in widgets:
            w.blockSignals(True)

        self._name.setText(f.name)
        
        idx = self._ox_combo.findText(f.oxidizer_name)
        self._ox_combo.setCurrentIndex(max(idx, 0))
        self._ox_temp.setValue(f.oxidizer_temp)
        self._ox_wt.setValue(f.oxidizer_wt)
        
        idx = self._fu_combo.findText(f.fuel_name)
        self._fu_combo.setCurrentIndex(max(idx, 0))
        self._fu_temp.setValue(f.fuel_temp)
        self._fu_wt.setValue(f.fuel_wt)
        
        self._pc.setValue(f.chamber_pressure)
        self._of.setValue(f.of_ratio)
        self._pe.setValue(f.exit_pressure)
        self._ar.setValue(f.area_ratio)
        self._tcest.setValue(float(f.tcest))
        self._frozen.setChecked(f.frozen)
        
        while self._udr_vlay.count():
            item = self._udr_vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._udr_data.clear()
        
        for udr_dict in f.user_reactants:
            name = udr_dict.get("name", "")
            wt = udr_dict.get("wt", 100.0)
            temp = udr_dict.get("temp_k", 298.0)
            enth = udr_dict.get("enthalpy_kj", 0.0)
            comp = udr_dict.get("composition", {})
            
            parts = [f"name={name}"]
            if wt not in (0.0, 100.0):
                parts.append(f"wt={wt:.4g}")
            parts.append(f"t,k={temp:.1f}")
            if enth != 0.0:
                parts.append(f"h,kj/mol={enth:.4g}")
            for el, amt in comp.items():
                parts.append(f"{el} {amt:.3f}")
            udr_text = " ".join(parts)
            
            self._udr_data.append(udr_dict)
            self._add_udr_row_widget(udr_text, udr_dict)

        for w in widgets:
            w.blockSignals(False)

    def show_validation(self, passed: bool, errors: list, warnings: list) -> None:
        lines = [f"✗ {e}" for e in errors] + [f"⚠ {w}" for w in warnings]
        if passed and not errors:
            self._val_lbl.setText("✓ Validation passed.")
            self._val_lbl.setObjectName("status_ok")
        else:
            self._val_lbl.setText("\n".join(lines))
            self._val_lbl.setObjectName("status_error")

    def add_udr_row(self, udr_text: str, udr_dict: dict, on_remove) -> None:
        self._udr_data.append(udr_dict)
        self._add_udr_row_widget(udr_text, udr_dict, on_remove)

    def _add_udr_row_widget(self, udr_text: str, udr_dict: dict, on_remove=None) -> None:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(udr_text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size:9px; color:#1A237E; font-family: monospace;")
        lay.addWidget(lbl, 1)
        rem = QPushButton("✖ Remove")
        rem.setObjectName("btn_danger")
        rem.setFixedHeight(26)
        rem.setFixedWidth(70)
        
        row_index = len(self._udr_data) - 1
        rem.clicked.connect(lambda: self._remove_udr_row(row, row_index, on_remove))
        lay.addWidget(rem)
        self._udr_vlay.addWidget(row)

    def _remove_udr_row(self, row: QWidget, index: int, on_remove) -> None:
        if 0 <= index < len(self._udr_data):
            del self._udr_data[index]
        self._udr_vlay.removeWidget(row)
        row.deleteLater()
        if on_remove:
            on_remove(row)

    def remove_udr_row(self, row: QWidget) -> None:
        for i in range(self._udr_vlay.count()):
            item = self._udr_vlay.itemAt(i)
            if item and item.widget() == row:
                if i < len(self._udr_data):
                    del self._udr_data[i]
                break
        self._udr_vlay.removeWidget(row)
        row.deleteLater()

    def clear_ui(self) -> None:
        self.blockSignals(True)
        self._ox_combo.setCurrentIndex(0)
        self._fu_combo.setCurrentIndex(0)
        self._ox_temp.setValue(298.0)
        self._fu_temp.setValue(298.0)
        self._ox_wt.setValue(68.0)
        self._fu_wt.setValue(18.0)
        self._pc.setValue(50.0)
        self._of.setValue(2.5)
        self._pe.setValue(1.0)
        self._ar.setValue(10.0)
        self._tcest.setValue(3800.0)
        self._frozen.setChecked(False)
        self._name.setText("Formulation 1")
        self._val_lbl.setText("")
        
        while self._udr_vlay.count():
            item = self._udr_vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._udr_data.clear()
        self.blockSignals(False)