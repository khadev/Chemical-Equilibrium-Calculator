"""
ui/dialogs/import_database_dialog.py
=======================================
Lets the user import a real NASA ``thermo.lib`` (species) and/or
``trans.lib`` (transport properties) file to expand the species
database's "All Species" pool.
"""
from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk

from core.theme_manager import ThemeManager
from core.thermo_lib_parser import ThermoLibParseError
from core.trans_lib_parser import TransLibParseError
from models.species_database import SpeciesDatabase
from ui.dialogs.base_dialog import BaseDialog


class ImportDatabaseDialog(BaseDialog):
    """Dialog for importing thermo.lib / trans.lib into the species database."""

    def __init__(
            self, parent: ctk.CTk,
            on_imported: Optional[Callable[[], None]] = None
    ) -> None:
        self._db = SpeciesDatabase()
        self._on_imported = on_imported
        super().__init__(parent, title="Import Database", width=540, height=420)
        self._build()

    def _build(self) -> None:
        colors = ThemeManager().get_colors()

        ctk.CTkLabel(
            self.body, text="Import NASA CEA Database Files",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            self.body,
            text=("Importing expands the 'All Species' pool available in "
                  "every species picker. NASA's thermo.lib does not label "
                  "species as oxidizer or fuel — that's a role you assign "
                  "when building a formulation — so imported species "
                  "become selectable for either role."),
            font=ctk.CTkFont(size=10), text_color=colors["text_secondary"],
            wraplength=480, justify="left"
        ).pack(anchor="w", pady=(0, 12))

        thermo_frame = ctk.CTkFrame(self.body, fg_color=colors["surface"],
                                    corner_radius=8)
        thermo_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            thermo_frame, text="thermo.lib  (species database)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 4))
        row1 = ctk.CTkFrame(thermo_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(0, 10))
        self._thermo_path_var = ctk.StringVar(value="")
        ctk.CTkEntry(row1, textvariable=self._thermo_path_var,
                    placeholder_text="No file selected").pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(row1, text="Browse…", width=80,
                     command=self._browse_thermo).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row1, text="Import", width=80,
                     command=self._import_thermo).pack(side="left")

        trans_frame = ctk.CTkFrame(self.body, fg_color=colors["surface"],
                                   corner_radius=8)
        trans_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            trans_frame, text="trans.lib  (transport properties)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(8, 4))
        row2 = ctk.CTkFrame(trans_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(0, 10))
        self._trans_path_var = ctk.StringVar(value="")
        ctk.CTkEntry(row2, textvariable=self._trans_path_var,
                    placeholder_text="No file selected").pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(row2, text="Browse…", width=80,
                     command=self._browse_trans).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row2, text="Import", width=80,
                     command=self._import_trans).pack(side="left")

        self._status_label = ctk.CTkLabel(
            self.body, text="", font=ctk.CTkFont(size=11),
            text_color=colors["success"], wraplength=480, justify="left")
        self._status_label.pack(anchor="w", pady=(4, 8))

        self._refresh_summary()

        bottom = ctk.CTkFrame(self.body, fg_color="transparent")
        bottom.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(
            bottom, text="Clear Imported Data", height=32,
            fg_color=colors["button_danger"], hover_color="#EF5350",
            command=self._clear_imported
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            bottom, text="Close", height=32, command=self.on_close
        ).pack(side="left", expand=True, fill="x")

    def _refresh_summary(self) -> None:
        colors = ThemeManager().get_colors()
        summary = self._db.import_summary()
        text = (f"Imported species: {summary['imported_species']}    |    "
                f"With transport data: {summary['transport_species']}    |    "
                f"Curated oxidizers: {summary['curated_oxidizers']}    |    "
                f"Curated fuels: {summary['curated_fuels']}")
        self._status_label.configure(text=text, text_color=colors["text"])

    def _browse_thermo(self) -> None:
        path = filedialog.askopenfilename(
            title="Select thermo.lib",
            filetypes=[("thermo.lib / thermo.inp", "*.lib *.inp *.txt"),
                      ("All files", "*.*")])
        if path:
            self._thermo_path_var.set(path)

    def _browse_trans(self) -> None:
        path = filedialog.askopenfilename(
            title="Select trans.lib",
            filetypes=[("trans.lib", "*.lib *.inp *.txt"),
                      ("All files", "*.*")])
        if path:
            self._trans_path_var.set(path)

    def _import_thermo(self) -> None:
        path = self._thermo_path_var.get().strip()
        if not path:
            messagebox.showwarning("Import", "Select a thermo.lib file first.")
            return
        try:
            added = self._db.import_thermo_lib(path)
            colors = ThemeManager().get_colors()
            self._status_label.configure(
                text=f"✓  Imported {added} new species from thermo.lib.",
                text_color=colors["success"])
            self._refresh_summary()
            if self._on_imported:
                self._on_imported()
        except ThermoLibParseError as exc:
            messagebox.showerror("Import Error", str(exc))

    def _import_trans(self) -> None:
        path = self._trans_path_var.get().strip()
        if not path:
            messagebox.showwarning("Import", "Select a trans.lib file first.")
            return
        try:
            added = self._db.import_trans_lib(path)
            colors = ThemeManager().get_colors()
            self._status_label.configure(
                text=f"✓  Tagged {added} new species with transport data.",
                text_color=colors["success"])
            self._refresh_summary()
            if self._on_imported:
                self._on_imported()
        except TransLibParseError as exc:
            messagebox.showerror("Import Error", str(exc))

    def _clear_imported(self) -> None:
        if messagebox.askyesno(
                "Clear Imported Data",
                "Remove all imported thermo.lib/trans.lib species? "
                "Curated species are not affected."):
            self._db.clear_imported()
            self._refresh_summary()
            if self._on_imported:
                self._on_imported()
