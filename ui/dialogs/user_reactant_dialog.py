"""
ui/dialogs/user_reactant_dialog.py
=====================================
Modal for entering a user-defined reactant with full periodic table support.

Layout fix: buttons are packed with side="bottom" BEFORE the scrollable
body is packed with fill="both" expand=True. This is the canonical pattern
for all overflow dialogs in this project - Tkinter's pack manager allocates
side="bottom" widgets first so they are always visible regardless of how
tall the body content grows.
"""
from __future__ import annotations
from typing import Callable, Dict, List, Optional, Tuple
import customtkinter as ctk
from core.theme_manager import ThemeManager
from models.formulation import UserReactant
from tools.numeric_utils import safe_float
from ui.dialogs.base_dialog import BaseDialog

_ALL_ELEMENTS: List[Tuple[str, int, str]] = [
    ("H",1,"Hydrogen"),("He",2,"Helium"),("Li",3,"Lithium"),
    ("Be",4,"Beryllium"),("B",5,"Boron"),("C",6,"Carbon"),
    ("N",7,"Nitrogen"),("O",8,"Oxygen"),("F",9,"Fluorine"),
    ("Ne",10,"Neon"),("Na",11,"Sodium"),("Mg",12,"Magnesium"),
    ("Al",13,"Aluminium"),("Si",14,"Silicon"),("P",15,"Phosphorus"),
    ("S",16,"Sulfur"),("Cl",17,"Chlorine"),("Ar",18,"Argon"),
    ("K",19,"Potassium"),("Ca",20,"Calcium"),("Sc",21,"Scandium"),
    ("Ti",22,"Titanium"),("V",23,"Vanadium"),("Cr",24,"Chromium"),
    ("Mn",25,"Manganese"),("Fe",26,"Iron"),("Co",27,"Cobalt"),
    ("Ni",28,"Nickel"),("Cu",29,"Copper"),("Zn",30,"Zinc"),
    ("Ga",31,"Gallium"),("Ge",32,"Germanium"),("As",33,"Arsenic"),
    ("Se",34,"Selenium"),("Br",35,"Bromine"),("Kr",36,"Krypton"),
    ("Rb",37,"Rubidium"),("Sr",38,"Strontium"),("Y",39,"Yttrium"),
    ("Zr",40,"Zirconium"),("Nb",41,"Niobium"),("Mo",42,"Molybdenum"),
    ("Tc",43,"Technetium"),("Ru",44,"Ruthenium"),("Rh",45,"Rhodium"),
    ("Pd",46,"Palladium"),("Ag",47,"Silver"),("Cd",48,"Cadmium"),
    ("In",49,"Indium"),("Sn",50,"Tin"),("Sb",51,"Antimony"),
    ("Te",52,"Tellurium"),("I",53,"Iodine"),("Xe",54,"Xenon"),
    ("Cs",55,"Cesium"),("Ba",56,"Barium"),("La",57,"Lanthanum"),
    ("Ce",58,"Cerium"),("Pr",59,"Praseodymium"),("Nd",60,"Neodymium"),
    ("Pm",61,"Promethium"),("Sm",62,"Samarium"),("Eu",63,"Europium"),
    ("Gd",64,"Gadolinium"),("Tb",65,"Terbium"),("Dy",66,"Dysprosium"),
    ("Ho",67,"Holmium"),("Er",68,"Erbium"),("Tm",69,"Thulium"),
    ("Yb",70,"Ytterbium"),("Lu",71,"Lutetium"),("Hf",72,"Hafnium"),
    ("Ta",73,"Tantalum"),("W",74,"Tungsten"),("Re",75,"Rhenium"),
    ("Os",76,"Osmium"),("Ir",77,"Iridium"),("Pt",78,"Platinum"),
    ("Au",79,"Gold"),("Hg",80,"Mercury"),("Tl",81,"Thallium"),
    ("Pb",82,"Lead"),("Bi",83,"Bismuth"),("Po",84,"Polonium"),
    ("At",85,"Astatine"),("Rn",86,"Radon"),("Fr",87,"Francium"),
    ("Ra",88,"Radium"),("Ac",89,"Actinium"),("Th",90,"Thorium"),
    ("Pa",91,"Protactinium"),("U",92,"Uranium"),("Np",93,"Neptunium"),
    ("Pu",94,"Plutonium"),("Am",95,"Americium"),("Cm",96,"Curium"),
    ("Bk",97,"Berkelium"),("Cf",98,"Californium"),("Es",99,"Einsteinium"),
    ("Fm",100,"Fermium"),("Md",101,"Mendelevium"),("No",102,"Nobelium"),
    ("Lr",103,"Lawrencium"),("Rf",104,"Rutherfordium"),("Db",105,"Dubnium"),
    ("Sg",106,"Seaborgium"),("Bh",107,"Bohrium"),("Hs",108,"Hassium"),
    ("Mt",109,"Meitnerium"),("Ds",110,"Darmstadtium"),("Rg",111,"Roentgenium"),
    ("Cn",112,"Copernicium"),("Nh",113,"Nihonium"),("Fl",114,"Flerovium"),
    ("Mc",115,"Moscovium"),("Lv",116,"Livermorium"),("Ts",117,"Tennessine"),
    ("Og",118,"Oganesson"),
]

# symbol -> (atomic_number, name)  [2-tuple]
_ELEM_INFO: Dict[str, Tuple[int, str]] = {
    sym: (num, name) for sym, num, name in _ALL_ELEMENTS}

_QUICK_ELEMENTS: List[str] = [
    "C","H","O","N","Cl","F","Al","Si","S","B","Be","Mg"]

_PRESETS: Dict[str, Dict] = {
    "HTPB":{"C":7.075,"H":10.650,"O":0.063,"N":0.223,"enthalpy":-58.0,"weight":14.0},
    "GAP": {"C":3.0,"H":5.0,"O":1.0,"N":3.0,"enthalpy":-78.0,"weight":10.0},
    "PEG": {"C":2.0,"H":4.333,"O":1.0,"enthalpy":-256.0,"weight":5.0},
}


class _ElementPickerDialog(ctk.CTkToplevel):
    """Searchable picker for all 118 elements. Calls on_select AFTER destroying self."""

    def __init__(self, parent, on_select: Callable[[str], None]) -> None:
        super().__init__(parent)
        self._on_select = on_select
        self.title("Add Element from Periodic Table")
        self.geometry("500x560")
        self.resizable(True, True)
        self.transient(parent)
        self._build()
        self.after(50, self._finalize)

    def _finalize(self) -> None:
        ThemeManager().apply(self)
        self.lift(); self.focus_force()
        try: self.grab_set()
        except Exception: pass

    def _build(self) -> None:
        colors = ThemeManager().get_colors()
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(frame, text="Select element to add  (all 118 elements)",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=colors["accent"]).pack(anchor="w", pady=(0,6))

        search_row = ctk.CTkFrame(frame, fg_color="transparent")
        search_row.pack(fill="x", pady=(0,6))
        ctk.CTkLabel(search_row, text="Search:", width=56).pack(side="left")
        self._search_var = ctk.StringVar()
        entry = ctk.CTkEntry(search_row, textvariable=self._search_var,
                            placeholder_text="symbol, name, or number...", height=34)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<KeyRelease>", lambda _e: self._refresh())
        entry.focus_set()

        # Button packed BEFORE scroll so it's always visible
        ctk.CTkButton(frame, text="Cancel", height=34,
                     fg_color=colors["surface"], text_color=colors["text"],
                     border_width=1, border_color=colors["border"],
                     hover_color=colors["border"],
                     command=self.destroy).pack(fill="x", pady=(8,0), side="bottom")

        self._count_label = ctk.CTkLabel(frame, text="",
                                          font=ctk.CTkFont(size=10),
                                          text_color=colors["text_secondary"])
        self._count_label.pack(anchor="w", pady=(0,4))

        self._scroll = ctk.CTkScrollableFrame(frame, fg_color=colors["surface"])
        self._scroll.pack(fill="both", expand=True)

        self._refresh()

    def _refresh(self) -> None:
        query = self._search_var.get().strip().lower()
        filtered = [
            (sym, num, name) for sym, num, name in _ALL_ELEMENTS
            if not query or query in sym.lower() or query in name.lower() or query == str(num)
        ]
        colors = ThemeManager().get_colors()
        for child in self._scroll.winfo_children():
            child.destroy()
        for sym, num, name in filtered:
            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkButton(row, text=f"{sym:<4} {num:>3}   {name}",
                         anchor="w", height=30,
                         fg_color="transparent", text_color=colors["text"],
                         hover_color=colors["border"],
                         font=ctk.CTkFont(family="Courier", size=11),
                         command=lambda s=sym: self._pick(s)).pack(fill="x")
        self._count_label.configure(text=f"{len(filtered)} / {len(_ALL_ELEMENTS)} elements")

    def _pick(self, symbol: str) -> None:
        try: self.grab_release()
        except Exception: pass
        cb = self._on_select
        self.destroy()   # destroy first, then callback
        cb(symbol)


class UserReactantDialog(BaseDialog):
    """
    User-defined reactant dialog with full periodic table support.

    Layout: buttons are packed side='bottom' FIRST before the scrollable
    body content, guaranteeing they're always visible at the bottom of the
    dialog regardless of how much body content there is.
    """

    def __init__(self, parent,
                 on_confirm: Optional[Callable[[UserReactant], None]] = None,
                 existing: Optional[UserReactant] = None) -> None:
        self._on_confirm = on_confirm

        # Pre-initialise ALL attrs picker callbacks may touch - BEFORE super().__init__
        self._comp_vars: Dict[str, ctk.StringVar] = {}
        self._active_frame: Optional[ctk.CTkScrollableFrame] = None
        self._active_label: Optional[ctk.CTkLabel] = None
        self._message_label: Optional[ctk.CTkLabel] = None
        self._preview_label: Optional[ctk.CTkLabel] = None
        self._name_var: Optional[ctk.StringVar] = None
        self._weight_var: Optional[ctk.StringVar] = None
        self._temp_var: Optional[ctk.StringVar] = None
        self._enthalpy_var: Optional[ctk.StringVar] = None

        super().__init__(parent, title="User-Defined Reactant", width=560, height=660)
        self._build(existing)

    def _build(self, existing: Optional[UserReactant]) -> None:
        colors = ThemeManager().get_colors()

        # ── STEP 1: Pack buttons at the BOTTOM first ─────────────────
        # This guarantees they're always visible regardless of body height.
        btn_row = ctk.CTkFrame(self.body, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom", pady=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", height=38,
                     fg_color=colors["surface"], text_color=colors["text"],
                     border_width=1, border_color=colors["border"],
                     hover_color=colors["border"], command=self.on_close
                     ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btn_row, text="Confirm  -  Add to Formulation", height=38,
                     command=self._confirm
                     ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Preview and message also packed from bottom, above buttons
        self._message_label = ctk.CTkLabel(
            self.body, text="", text_color=colors["error"])
        self._message_label.pack(fill="x", side="bottom")

        self._preview_label = ctk.CTkLabel(
            self.body, text="",
            font=ctk.CTkFont(family="Courier", size=9),
            text_color=colors["text_secondary"],
            wraplength=500, justify="left")
        self._preview_label.pack(fill="x", side="bottom", pady=(0, 4))

        # ── STEP 2: Scrollable body fills the remaining space ─────────
        body_scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        body_scroll.pack(fill="both", expand=True)

        # All body content goes inside body_scroll from here
        self._build_body(body_scroll, existing, colors)

        # Wire trace callbacks
        for var in self._comp_vars.values():
            var.trace_add("write", lambda *_: self._update_preview())
        if self._name_var:
            self._name_var.trace_add("write", lambda *_: self._update_preview())
        if self._weight_var:
            self._weight_var.trace_add("write", lambda *_: self._update_preview())
        if self._enthalpy_var:
            self._enthalpy_var.trace_add("write", lambda *_: self._update_preview())

        self._refresh_extra_elements_display()
        self._update_preview()

    def _build_body(self, parent, existing: Optional[UserReactant], colors: dict) -> None:
        """Build all the scrollable body content inside parent."""

        # Presets
        ctk.CTkLabel(parent, text="Quick Presets",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=colors["accent"]).pack(anchor="w", pady=(0, 2))
        preset_row = ctk.CTkFrame(parent, fg_color="transparent")
        preset_row.pack(fill="x", pady=(0, 10))
        for pname in _PRESETS:
            ctk.CTkButton(preset_row, text=pname, width=80, height=30,
                         fg_color=colors["surface_alt"], text_color=colors["accent"],
                         hover_color=colors["border"],
                         command=lambda n=pname: self._apply_preset(n)
                         ).pack(side="left", padx=(0, 6))

        # Basic fields
        form = ctk.CTkFrame(parent, fg_color="transparent")
        form.pack(fill="x", pady=(0, 10))
        form.grid_columnconfigure(1, weight=1)
        fields = [
            ("Name:", existing.name if existing else ""),
            ("Weight (wt%):", str(existing.weight_pct if existing else 14.0)),
            ("Temperature (K):", str(existing.temperature_k if existing else 298.0)),
            ("Enthalpy (kJ/mol):", str(existing.enthalpy_kj_mol if existing else -58.0)),
        ]
        field_vars = []
        for i, (label, val) in enumerate(fields):
            ctk.CTkLabel(form, text=label, anchor="e", width=130
                        ).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=4)
            var = ctk.StringVar(value=val)
            field_vars.append(var)
            ctk.CTkEntry(form, textvariable=var).grid(
                row=i, column=1, sticky="ew", padx=(0, 4), pady=4)
        self._name_var, self._weight_var, self._temp_var, self._enthalpy_var = field_vars

        # Composition header with + Add Element button
        comp_hdr = ctk.CTkFrame(parent, fg_color="transparent")
        comp_hdr.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(comp_hdr,
                    text="Atomic Composition  (moles per formula unit)",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=colors["accent"]).pack(side="left")
        ctk.CTkButton(comp_hdr, text="+ Add Element...", height=28, width=140,
                     fg_color=colors["surface_alt"], text_color=colors["accent"],
                     hover_color=colors["border"],
                     command=self._open_element_picker).pack(side="right")

        # Quick-access grid (12 common elements)
        quick_card = ctk.CTkFrame(parent, fg_color=colors["surface"], corner_radius=6)
        quick_card.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(quick_card, text="Common propellant elements  (quick access)",
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color=colors["text_secondary"]
                    ).pack(anchor="w", padx=8, pady=(4, 2))
        grid_frame = ctk.CTkFrame(quick_card, fg_color="transparent")
        grid_frame.pack(fill="x", padx=8, pady=(0, 8))
        existing_comp = existing.composition if existing else {}
        for i, symbol in enumerate(_QUICK_ELEMENTS):
            row_g, col_g = divmod(i, 4)
            cell = ctk.CTkFrame(grid_frame, fg_color="transparent")
            cell.grid(row=row_g, column=col_g, sticky="ew", padx=3, pady=2)
            ctk.CTkLabel(cell, text=symbol,
                        font=ctk.CTkFont(size=11, weight="bold"),
                        width=26, anchor="w").pack(side="left", padx=(2, 2))
            var = self._ensure_comp_var(symbol, existing_comp.get(symbol, 0.0))
            ctk.CTkEntry(cell, textvariable=var, width=72).pack(side="left")
        for c in range(4):
            grid_frame.grid_columnconfigure(c, weight=1)

        # Active extra elements panel
        self._active_label = ctk.CTkLabel(
            parent, text="Active extra elements: (none)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=colors["accent"])
        self._active_label.pack(anchor="w", pady=(8, 2))

        self._active_frame = ctk.CTkScrollableFrame(
            parent, fg_color=colors["surface"], height=100)
        self._active_frame.pack(fill="x", pady=(0, 6))

        # Load extra elements from existing
        if existing:
            for symbol, amount in existing.composition.items():
                if symbol not in _QUICK_ELEMENTS:
                    self._ensure_comp_var(symbol, amount)

    # ── Helpers ────────────────────────────────────────────────────────

    def _ensure_comp_var(self, symbol: str, initial: float = 0.0) -> ctk.StringVar:
        if symbol not in self._comp_vars:
            var = ctk.StringVar(value=str(initial))
            var.trace_add("write", lambda *_: self._update_preview())
            self._comp_vars[symbol] = var
        return self._comp_vars[symbol]

    def _open_element_picker(self) -> None:
        _ElementPickerDialog(self, on_select=self._add_element)

    def _add_element(self, symbol: str) -> None:
        if self._active_frame is None:
            return
        if symbol in self._comp_vars:
            if self._message_label:
                self._message_label.configure(
                    text=f"{symbol} is already in the composition.")
                self.after(2500, lambda: self._message_label.configure(text="")
                           if self._message_label else None)
            return
        self._ensure_comp_var(symbol, 1.0)
        self._refresh_extra_elements_display()
        self._update_preview()
        if self._message_label:
            self._message_label.configure(text="")

    def _remove_element(self, symbol: str) -> None:
        self._comp_vars.pop(symbol, None)
        self._refresh_extra_elements_display()
        self._update_preview()

    def _refresh_extra_elements_display(self) -> None:
        if self._active_frame is None:
            return
        for child in self._active_frame.winfo_children():
            child.destroy()
        colors = ThemeManager().get_colors()
        extra = sorted(s for s in self._comp_vars if s not in _QUICK_ELEMENTS)

        if not extra:
            ctk.CTkLabel(self._active_frame,
                        text='Use "+ Add Element..." to include any element '
                             'beyond the 12-element quick grid above.',
                        font=ctk.CTkFont(size=9),
                        text_color=colors["text_secondary"]
                        ).pack(anchor="w", padx=6, pady=6)
            if self._active_label:
                self._active_label.configure(text="Active extra elements: (none)")
            return

        if self._active_label:
            self._active_label.configure(text=f"Active extra elements: {len(extra)}")

        for symbol in extra:
            info = _ELEM_INFO.get(symbol)       # (atomic_number, name) - 2-tuple
            el_name = info[1] if info else symbol
            row = ctk.CTkFrame(self._active_frame, fg_color="transparent")
            row.pack(fill="x", pady=1, padx=4)
            ctk.CTkLabel(row, text=f"{symbol:<4} {el_name}",
                        font=ctk.CTkFont(family="Courier", size=11),
                        width=180, anchor="w").pack(side="left")
            ctk.CTkEntry(row, textvariable=self._comp_vars[symbol],
                        width=90).pack(side="left", padx=(6, 6))
            ctk.CTkLabel(row, text="mol", font=ctk.CTkFont(size=10),
                        text_color=colors["text_secondary"]).pack(side="left")
            ctk.CTkButton(row, text="Remove", width=72, height=24,
                         fg_color=colors["button_danger"], hover_color="#EF5350",
                         font=ctk.CTkFont(size=9),
                         command=lambda s=symbol: self._remove_element(s)
                         ).pack(side="right")

    def _apply_preset(self, preset_name: str) -> None:
        preset = _PRESETS[preset_name]
        if self._name_var: self._name_var.set(preset_name)
        if self._weight_var: self._weight_var.set(str(preset["weight"]))
        if self._enthalpy_var: self._enthalpy_var.set(str(preset["enthalpy"]))
        for sym in list(self._comp_vars):
            if sym not in _QUICK_ELEMENTS:
                del self._comp_vars[sym]
        for sym in _QUICK_ELEMENTS:
            self._ensure_comp_var(sym, preset.get(sym, 0.0))
            self._comp_vars[sym].set(str(preset.get(sym, 0.0)))
        for key, val in preset.items():
            if key in ("weight", "enthalpy"): continue
            if key not in _QUICK_ELEMENTS:
                self._ensure_comp_var(key, val)
        self._refresh_extra_elements_display()
        self._update_preview()

    def _build_composition(self) -> Dict[str, float]:
        return {sym: safe_float(var.get(), 0.0)
                for sym, var in self._comp_vars.items()
                if safe_float(var.get(), 0.0) > 0.0}

    def _build_reactant(self) -> Optional[UserReactant]:
        name = self._name_var.get().strip() if self._name_var else ""
        if not name: return None
        composition = self._build_composition()
        if not composition: return None
        return UserReactant(
            name=name,
            weight_pct=safe_float(self._weight_var.get() if self._weight_var else "100", 100.0),
            temperature_k=safe_float(self._temp_var.get() if self._temp_var else "298", 298.0),
            enthalpy_kj_mol=safe_float(self._enthalpy_var.get() if self._enthalpy_var else "0", 0.0),
            composition=composition)

    def _update_preview(self) -> None:
        if self._preview_label is None: return
        reactant = self._build_reactant()
        self._preview_label.configure(
            text=reactant.to_inp_line() if reactant
            else "(enter name and at least one element amount > 0)")

    def _confirm(self) -> None:
        reactant = self._build_reactant()
        if not reactant:
            if self._message_label:
                self._message_label.configure(
                    text="Name is required and at least one element must be > 0.")
            return
        valid, message = reactant.validate()
        if not valid:
            if self._message_label:
                self._message_label.configure(text=message)
            return
        if self._on_confirm:
            self._on_confirm(reactant)
        self.on_close()
