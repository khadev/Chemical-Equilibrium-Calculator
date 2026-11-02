"""
ui/dialogs/settings_dialog.py
================================
Application settings dialog — FCEA2 path, units, language, display
preferences. Persists via :class:`SettingsManager` (config.json
equivalent: settings.json).
"""
from __future__ import annotations

from tkinter import filedialog
from typing import Callable, Optional

import customtkinter as ctk

from core.theme_manager import ThemeManager
from tools.settings_manager import SettingsManager
from ui.dialogs.base_dialog import BaseDialog


class SettingsDialog(BaseDialog):
    """
    Settings dialog with tabbed sections: Paths, Units, Language.

    Args:
        parent: Parent window.
        on_saved: Callback invoked after settings are saved.
    """

    def __init__(
            self, parent: ctk.CTk, on_saved: Optional[Callable[[], None]] = None
    ) -> None:
        self._on_saved = on_saved
        self._settings = SettingsManager()
        super().__init__(parent, title="Settings", width=560, height=440)
        self._build()

    def _build(self) -> None:
        colors = ThemeManager().get_colors()
        tabview = ctk.CTkTabview(self.body, fg_color=colors["surface"])
        tabview.pack(fill="both", expand=True)
        tabview.add("Paths")
        tabview.add("Units")
        tabview.add("Language")

        self._build_paths_tab(tabview.tab("Paths"))
        self._build_units_tab(tabview.tab("Units"))
        self._build_language_tab(tabview.tab("Language"))

        button_row = ctk.CTkFrame(self.body, fg_color="transparent")
        button_row.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            button_row, text="Cancel", height=36,
            fg_color=colors["surface"], text_color=colors["text"],
            border_width=1, border_color=colors["border"],
            hover_color=colors["border"],
            command=self.on_close
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(
            button_row, text="Save", height=36, command=self._save
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _build_paths_tab(self, tab: ctk.CTkFrame) -> None:
        ctk.CTkLabel(tab, text="FCEA2.exe Path:", anchor="w").pack(
            fill="x", padx=8, pady=(10, 2))
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=8)
        self._exe_var = ctk.StringVar(value=self._settings.fcea2_exe())
        ctk.CTkEntry(row, textvariable=self._exe_var).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            row, text="Browse…", width=80,
            command=self._browse_exe
        ).pack(side="left")

        ctk.CTkLabel(tab, text="Working Directory:", anchor="w").pack(
            fill="x", padx=8, pady=(14, 2))
        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill="x", padx=8)
        self._dir_var = ctk.StringVar(value=self._settings.cea_folder())
        ctk.CTkEntry(row2, textvariable=self._dir_var).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            row2, text="Browse…", width=80,
            command=self._browse_dir
        ).pack(side="left")

        status_text = ("✓ FCEA2 configured" if self._settings.cea_available()
                       else "⚠ Fallback calculator will be used")
        ctk.CTkLabel(
            tab, text=status_text,
            text_color=(ThemeManager().get_colors()["success"]
                       if self._settings.cea_available()
                       else ThemeManager().get_colors()["warning"])
        ).pack(anchor="w", padx=8, pady=(14, 4))

    def _build_units_tab(self, tab: ctk.CTkFrame) -> None:
        self._pressure_unit = ctk.StringVar(
            value=self._settings.get("units", "pressure") or "bar")
        self._temp_unit = ctk.StringVar(
            value=self._settings.get("units", "temperature") or "K")

        ctk.CTkLabel(tab, text="Pressure Unit:", anchor="w").pack(
            fill="x", padx=8, pady=(10, 2))
        ctk.CTkSegmentedButton(
            tab, values=["bar", "psi", "MPa"], variable=self._pressure_unit
        ).pack(fill="x", padx=8)

        ctk.CTkLabel(tab, text="Temperature Unit:", anchor="w").pack(
            fill="x", padx=8, pady=(14, 2))
        ctk.CTkSegmentedButton(
            tab, values=["K", "°C"], variable=self._temp_unit
        ).pack(fill="x", padx=8)

    def _build_language_tab(self, tab: ctk.CTkFrame) -> None:
        self._lang_var = ctk.StringVar(value=self._settings.language())
        ctk.CTkLabel(tab, text="Application Language:", anchor="w").pack(
            fill="x", padx=8, pady=(10, 6))
        ctk.CTkSegmentedButton(
            tab, values=["en", "fr"], variable=self._lang_var
        ).pack(fill="x", padx=8)
        ctk.CTkLabel(
            tab, text="New dialogs use the selected language immediately.",
            text_color=ThemeManager().get_colors()["text_secondary"],
            font=ctk.CTkFont(size=10)
        ).pack(anchor="w", padx=8, pady=(8, 0))

    def _browse_exe(self) -> None:
        path = filedialog.askopenfilename(
            title="Select FCEA2.exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self._exe_var.set(path)

    def _browse_dir(self) -> None:
        path = filedialog.askdirectory(title="Select working directory")
        if path:
            self._dir_var.set(path)

    def _save(self) -> None:
        self._settings.set("paths", "fcea2_exe", value=self._exe_var.get().strip())
        self._settings.set("paths", "cea_folder", value=self._dir_var.get().strip())
        self._settings.set("units", "pressure", value=self._pressure_unit.get())
        self._settings.set("units", "temperature", value=self._temp_unit.get())
        self._settings.set_language(self._lang_var.get())
        self._settings.save()
        if self._on_saved:
            self._on_saved()
        self.on_close()
