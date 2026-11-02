"""
ui/welcome_panel.py
======================
Empty-state welcome screen shown when no calculation has been run yet.
"""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from core.theme_manager import ThemeManager
from tools.settings_manager import SettingsManager


class WelcomePanel(ctk.CTkFrame):
    """Welcome / empty-state screen with quick-start presets."""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        colors = ThemeManager().get_colors()
        super().__init__(master, fg_color=colors["bg"])
        self.on_preset_selected: Optional[Callable[[dict], None]] = None
        self._build()

    def _build(self) -> None:
        colors = ThemeManager().get_colors()
        settings = SettingsManager()

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(expand=True)

        ctk.CTkLabel(
            center, text="🚀", font=ctk.CTkFont(size=48)
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            center, text="Welcome to CEA Calculator Pro",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=colors["accent"]
        ).pack()

        ctk.CTkLabel(
            center,
            text="Select an oxidizer and fuel, set your operating "
                 "conditions, then click Calculate.\nOr start from a preset:",
            font=ctk.CTkFont(size=12), text_color=colors["text_secondary"],
            justify="center"
        ).pack(pady=(6, 16))

        preset_frame = ctk.CTkFrame(center, fg_color="transparent")
        preset_frame.pack()
        for preset in settings.get_presets():
            ctk.CTkButton(
                preset_frame, text=preset["name"], width=220, height=36,
                fg_color=colors["surface_alt"], text_color=colors["accent"],
                hover_color=colors["border"],
                command=lambda p=preset: self._select_preset(p)
            ).pack(pady=3)

    def _select_preset(self, preset: dict) -> None:
        if self.on_preset_selected:
            self.on_preset_selected(preset)
