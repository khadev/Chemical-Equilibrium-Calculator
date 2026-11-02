"""
core/theme_manager.py
=====================
Theme engine — Singleton pattern.
Holds the active color palette and applies it recursively to any widget tree.
Only Light theme is active per project specification.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import customtkinter as ctk

log = logging.getLogger(__name__)


# ── Color palettes ─────────────────────────────────────────────────────
_PALETTES: Dict[str, Dict[str, str]] = {
    "Light": {
        # Backgrounds
        "bg":           "#F5F5F5",
        "surface":      "#FFFFFF",
        "surface_alt":  "#F0F4FF",
        "sidebar":      "#E8EAF6",
        # Accent
        "accent":       "#3F51B5",
        "accent_hover": "#5C6BC0",
        "accent_press": "#1A237E",
        # Text
        "text":         "#212121",
        "text_secondary":"#757575",
        "text_on_accent":"#FFFFFF",
        # Status
        "success":      "#2E7D32",
        "warning":      "#E65100",
        "error":        "#C62828",
        "info":         "#01579B",
        # Borders & misc
        "border":       "#C5CAE9",
        "separator":    "#E0E0E0",
        "table_alt":    "#F3F4FC",
        "button_danger":"#E53935",
        "button_ok":    "#388E3C",
        # Console
        "console_bg":   "#FAFAFA",
        "console_text": "#212121",
    },
}


class ThemeManager:
    """
    Singleton theme engine.

    Usage:
        tm = ThemeManager()
        colors = tm.get_colors()
        tm.apply(widget)

    All UI modules call ``ThemeManager()`` to get a shared instance —
    never instantiate color dicts directly in widget code.
    """

    _instance: Optional["ThemeManager"] = None

    def __new__(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._theme = "Light"
            cls._instance._colors = dict(_PALETTES["Light"])
            ctk.set_appearance_mode("light")
            ctk.set_default_color_theme("blue")
            log.debug("ThemeManager initialised (Light)")
        return cls._instance

    # ── Public API ────────────────────────────────────────────────────
    def get_colors(self) -> Dict[str, str]:
        """Return a copy of the current color palette."""
        return dict(self._colors)

    def current_theme(self) -> str:
        """Return the active theme name."""
        return self._theme

    def apply(self, widget: ctk.CTkBaseClass) -> None:
        """
        Recursively apply the current palette to ``widget`` and all its
        children.  Safe to call at any time; ignores unknown widget types.

        Args:
            widget: Root widget to style.
        """
        self._apply_recursive(widget, self._colors)

    # ── Internals ─────────────────────────────────────────────────────
    def _apply_recursive(
            self,
            widget: ctk.CTkBaseClass,
            c: Dict[str, str]) -> None:
        """Recursively configure widget colours.

        Args:
            widget: The widget to configure.
            c: Colour palette dictionary.
        """
        try:
            if isinstance(widget, (ctk.CTkFrame, ctk.CTkScrollableFrame)):
                widget.configure(fg_color=c["surface"])
            elif isinstance(widget, ctk.CTkLabel):
                widget.configure(text_color=c["text"])
            elif isinstance(widget, ctk.CTkButton):
                widget.configure(
                    fg_color=c["accent"],
                    hover_color=c["accent_hover"],
                    text_color=c["text_on_accent"])
            elif isinstance(widget, (ctk.CTkEntry, ctk.CTkComboBox)):
                widget.configure(
                    fg_color=c["surface"],
                    border_color=c["border"],
                    text_color=c["text"])
            elif isinstance(widget, ctk.CTkTextbox):
                widget.configure(
                    fg_color=c["console_bg"],
                    text_color=c["console_text"],
                    border_color=c["border"])
            elif isinstance(widget, ctk.CTkCheckBox):
                widget.configure(
                    text_color=c["text"],
                    fg_color=c["accent"],
                    hover_color=c["accent_hover"],
                    border_color=c["border"])
            elif isinstance(widget, ctk.CTkTabview):
                widget.configure(
                    fg_color=c["surface"],
                    segmented_button_fg_color=c["sidebar"],
                    segmented_button_selected_color=c["accent"],
                    segmented_button_selected_hover_color=c["accent_hover"],
                    segmented_button_unselected_color=c["sidebar"],
                    segmented_button_unselected_hover_color=c["border"],
                    text_color=c["text_on_accent"],
                    text_color_disabled=c["text_secondary"])
            elif isinstance(widget, ctk.CTkSegmentedButton):
                widget.configure(
                    fg_color=c["sidebar"],
                    selected_color=c["accent"],
                    selected_hover_color=c["accent_hover"],
                    unselected_color=c["sidebar"],
                    unselected_hover_color=c["border"],
                    text_color=c["text"])
            elif isinstance(widget, ctk.CTkSlider):
                widget.configure(
                    button_color=c["accent"],
                    button_hover_color=c["accent_hover"],
                    progress_color=c["accent"])
            elif isinstance(widget, ctk.CTkProgressBar):
                widget.configure(
                    fg_color=c["border"],
                    progress_color=c["accent"])
            elif isinstance(widget, ctk.CTkSwitch):
                widget.configure(
                    text_color=c["text"],
                    progress_color=c["accent"],
                    button_color=c["accent_hover"])
        except Exception:
            pass   # Widget may not support certain options — silently ignore

        # Recurse into children
        try:
            for child in widget.winfo_children():
                self._apply_recursive(child, c)
        except Exception:
            pass
