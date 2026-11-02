"""
ui/dialogs/base_dialog.py
============================
Base class for all tool/settings dialogs. Centers itself on its
parent, applies the active theme, and provides a consistent close
protocol.
"""
from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from core.theme_manager import ThemeManager


class BaseDialog(ctk.CTkToplevel):
    """
    Base class for all modal tool dialogs.

    Subclasses should call ``super().__init__(parent, title=..., ...)``
    then populate ``self.body`` (a :class:`ctk.CTkFrame` provided by
    this base class) with their content.
    """

    def __init__(
            self,
            parent: ctk.CTk,
            title: str = "",
            width: int = 600,
            height: int = 450,
    ) -> None:
        """
        Args:
            parent: Parent window (used for centering and modality).
            title: Dialog window title.
            width: Initial dialog width in pixels.
            height: Initial dialog height in pixels.
        """
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=12, pady=12)

        self.transient(parent)
        self.after(50, self._finalize_open)

    def _finalize_open(self) -> None:
        """Center on parent, apply theme, and grab focus."""
        self.center_on_parent()
        ThemeManager().apply(self)
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:
            pass

    def center_on_parent(self) -> None:
        """Center this dialog over its parent window."""
        self.update_idletasks()
        parent = self.master
        try:
            px, py = parent.winfo_x(), parent.winfo_y()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

    def on_close(self) -> None:
        """Release the modal grab and destroy the dialog."""
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
