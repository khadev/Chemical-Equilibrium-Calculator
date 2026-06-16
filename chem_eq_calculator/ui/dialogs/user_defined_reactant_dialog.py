"""
ui/dialogs/user_defined_reactant_dialog.py
Dialog for adding a user-defined reactant with a table for atomic composition.
Saves custom species to database.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDoubleSpinBox, QPushButton, QHBoxLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel
)
from PySide6.QtCore import Qt

from models.data_layer import UserReactant, SpeciesDatabase

# Standard NASA elements (atomic symbols)
STANDARD_ELEMENTS = ["C", "H", "N", "O", "F", "Cl", "Al", "B", "Mg", "Si", "P", "S", "Na", "K", "Li", "Be", "Ti", "Fe", "Cu", "Zn"]


class UserDefinedReactantDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add User-Defined Reactant")
        self.setMinimumWidth(550)
        self.setMinimumHeight(450)
        self._reactant = None
        self._db = SpeciesDatabase()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., HTPB, MCCN, CustomPolymer")
        form.addRow("Name:", self.name_edit)

        # Weight percentage
        self.wt_spin = QDoubleSpinBox()
        self.wt_spin.setRange(0.0, 100.0)
        self.wt_spin.setValue(14.0)
        self.wt_spin.setSuffix(" %")
        self.wt_spin.setDecimals(2)
        form.addRow("Weight (wt):", self.wt_spin)

        # Temperature
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(1.0, 6000.0)
        self.temp_spin.setValue(298.0)
        self.temp_spin.setSuffix(" K")
        self.temp_spin.setDecimals(1)
        form.addRow("Temperature:", self.temp_spin)

        # Enthalpy
        self.enth_spin = QDoubleSpinBox()
        self.enth_spin.setRange(-100000.0, 100000.0)
        self.enth_spin.setValue(0.0)
        self.enth_spin.setSuffix(" kJ/mol")
        self.enth_spin.setDecimals(2)
        form.addRow("Enthalpy (h):", self.enth_spin)

        layout.addLayout(form)

        # Composition table
        comp_label = QLabel("Atomic Composition (NASA standard)")
        comp_label.setStyleSheet("font-weight:bold; margin-top:8px;")
        layout.addWidget(comp_label)

        self.comp_table = QTableWidget()
        self.comp_table.setColumnCount(2)
        self.comp_table.setHorizontalHeaderLabels(["Element", "Atoms / Molecule"])
        self.comp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.comp_table.setMinimumHeight(200)
        # Populate with standard elements
        self.comp_table.setRowCount(len(STANDARD_ELEMENTS))
        for i, elem in enumerate(STANDARD_ELEMENTS):
            self.comp_table.setItem(i, 0, QTableWidgetItem(elem))
            self.comp_table.setItem(i, 1, QTableWidgetItem("0.000"))
            self.comp_table.item(i, 1).setTextAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.comp_table)

        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a reactant name.")
            return

        # Parse composition from table
        composition = {}
        for row in range(self.comp_table.rowCount()):
            elem_item = self.comp_table.item(row, 0)
            val_item = self.comp_table.item(row, 1)
            if not elem_item or not val_item:
                continue
            elem = elem_item.text().strip()
            try:
                amount = float(val_item.text().strip())
            except ValueError:
                amount = 0.0
            if amount != 0.0:
                composition[elem] = amount

        if not composition:
            QMessageBox.warning(
                self,
                "Missing Composition",
                "Please enter at least one element with non‑zero value."
            )
            return

        # Create UserReactant
        self._reactant = UserReactant(
            name=name,
            wt=self.wt_spin.value(),
            temp_k=self.temp_spin.value(),
            enthalpy_kj=self.enth_spin.value(),
            composition=composition
        )

        # Save to custom species database
        success, msg = self._db.add_custom({
            "name": name,
            "composition": composition,
            "enthalpy": self.enth_spin.value(),
            "type": "fuel"
        })
        if not success:
            QMessageBox.warning(self, "Database Error", msg)
            return

        self.accept()

    def get_reactant(self):
        return self._reactant
