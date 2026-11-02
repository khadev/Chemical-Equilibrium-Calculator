
"""
ui/dialogs/species_picker_dialog.py
=====================================
Modal species picker with live search filtering, category grouping,
and a Curated / All Species toggle.

"Curated" mode keeps oxidizer and fuel lists strictly disjoint for
guided quick-pick. "All Species" mode shows the unrestricted pool
(curated + anything imported from a real thermo.lib) for either role,
matching how CEA itself actually works — any species may be assigned
to oxid= or fuel=.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from core.theme_manager import ThemeManager
from models.species_database import SpeciesDatabase
from ui.dialogs.base_dialog import BaseDialog


class SpeciesPickerDialog(BaseDialog):
    """
    Searchable list picker for oxidizer or fuel species.

    Args:
        parent: Parent window.
        mode: Either ``"oxidizer"`` or ``"fuel"`` — determines which
            curated list is shown by default.
        current_name: Pre-selected species name, if any.
        on_select: Callback invoked with the chosen species name.
    """

    def __init__(
            self,
            parent: ctk.CTk,
            mode: str,
            current_name: str = "",
            on_select: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._mode = mode
        self._on_select = on_select
        self._db = SpeciesDatabase()
        self._view = "curated"  # "curated" or "all"

        title = f"Select {'Oxidizer' if mode == 'oxidizer' else 'Fuel'} Species"
        super().__init__(parent, title=title, width=440, height=620)
        self._build(current_name)

    def _is_valid_species_name(self, name: str) -> bool:
        """Check if a species name is valid (not garbage)."""
        if not name or len(name) < 2:
            return False
        # Must start with a letter
        if not name[0].isalpha():
            return False
        # Must contain at least one letter
        if not any(c.isalpha() for c in name):
            return False
        # Filter out common garbage patterns
        import re
        garbage_patterns = [
            r'^[0-9]+$',  # all numbers
            r'^[^a-zA-Z]+$',  # no letters
            r'^[a-z0-9/]+$',  # only lowercase letters/numbers/slashes
        ]
        for pattern in garbage_patterns:
            if re.match(pattern, name):
                return False
        return True

    def _build(self, current_name: str) -> None:
        colors = ThemeManager().get_colors()

        toggle_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        toggle_frame.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(toggle_frame, text="View:", width=40).pack(side="left")
        
        self._view_var = ctk.StringVar(value="Curated")
        has_imported = len(self._db.imported_species()) > 0
        all_species_count = len(self._db.all_species_pool())
        
        segmented = ctk.CTkSegmentedButton(
            toggle_frame,
            values=["Curated", f"All Species ({all_species_count})"],
            variable=self._view_var,
            command=self._on_view_changed)
        segmented.pack(side="left", fill="x", expand=True)
        
        if not has_imported:
            ctk.CTkLabel(
                self.body,
                text="ℹ  Import a thermo.lib file (Tools > Import Database) "
                     "to expand 'All Species'.",
                font=ctk.CTkFont(size=9), text_color=colors["text_secondary"],
                wraplength=400, justify="left"
            ).pack(anchor="w", pady=(0, 6))

        search_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(search_frame, text="🔍",
                    font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 6))
        self._search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            search_frame, textvariable=self._search_var,
            placeholder_text="Type to filter…", height=34)
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.bind("<KeyRelease>", self._on_search_changed)
        search_entry.focus_set()

        self._count_label = ctk.CTkLabel(
            self.body, text="", font=ctk.CTkFont(size=11),
            text_color=colors["text_secondary"])
        self._count_label.pack(anchor="w", pady=(0, 4))

        self._scroll = ctk.CTkScrollableFrame(
            self.body, fg_color=colors["surface"])
        self._scroll.pack(fill="both", expand=True)

        self._current_name = current_name
        self._render_current_view()

        close_btn = ctk.CTkButton(
            self.body, text="Cancel", height=34,
            fg_color=colors["surface"], text_color=colors["text"],
            border_width=1, border_color=colors["border"],
            hover_color=colors["border"], command=self.on_close)
        close_btn.pack(fill="x", pady=(8, 0))

    def _on_view_changed(self, _value: str = "") -> None:
        self._view = "all" if self._view_var.get().startswith("All") else "curated"
        self._search_var.set("")
        self._render_current_view()

    def _render_current_view(self) -> None:
        query = self._search_var.get().strip().lower()
        if self._view == "all":
            items = self._db.all_species_pool()
            # Filter out invalid species names
            items = [s for s in items if self._is_valid_species_name(s)]
            if query:
                items = [s for s in items if query in s.lower()]
            self._render_flat(items)
        else:
            categories = (self._db.oxidizer_categories() if self._mode == "oxidizer"
                         else self._db.fuel_categories())
            # Filter out invalid species names from categories
            filtered_categories = {}
            for cat, names in categories.items():
                valid_names = [s for s in names if self._is_valid_species_name(s)]
                if query:
                    valid_names = [s for s in valid_names if query in s.lower()]
                if valid_names:
                    filtered_categories[cat] = valid_names
            self._render_grouped(filtered_categories)

    def _render_flat(self, items: List[str]) -> None:
        for child in self._scroll.winfo_children():
            child.destroy()
        colors = ThemeManager().get_colors()
        for name in items:
            if self._is_valid_species_name(name):
                self._add_species_button(self._scroll, name, colors)
        self._count_label.configure(text=f"{len(items)} species available")

    def _render_grouped(self, categories: Dict[str, List[str]]) -> None:
        for child in self._scroll.winfo_children():
            child.destroy()
        colors = ThemeManager().get_colors()
        total = 0
        for category, names in categories.items():
            if not names:
                continue
            header = ctk.CTkLabel(
                self._scroll, text=category, anchor="w",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=colors["accent"])
            header.pack(fill="x", pady=(8, 2), padx=2)
            for name in names:
                if self._is_valid_species_name(name):
                    self._add_species_button(self._scroll, name, colors)
                    total += 1
        self._count_label.configure(text=f"{total} species available")

    def _add_species_button(self, parent: ctk.CTkBaseClass, name: str,
                            colors: dict) -> None:
        # Skip invalid names
        if not self._is_valid_species_name(name):
            return
            
        is_current = name == self._current_name
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1, padx=2)
        btn = ctk.CTkButton(
            row, text=name, anchor="w", height=30,
            fg_color=colors["accent"] if is_current else "transparent",
            text_color=(colors["text_on_accent"] if is_current
                       else colors["text"]),
            hover_color=colors["accent_hover"],
            command=lambda n=name: self._select(n))
        btn.pack(side="left", fill="x", expand=True)
        if self._db.has_transport_data(name):
            ctk.CTkLabel(
                row, text="🌡", width=20,
                font=ctk.CTkFont(size=10)
            ).pack(side="left")

    def _on_search_changed(self, _event: object = None) -> None:
        self._render_current_view()

    def _select(self, name: str) -> None:
        if self._on_select:
            self._on_select(name)
        self.on_close()
