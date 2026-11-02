
"""
ui/dialogs/user_reactant_dialog.py - PROFESSIONAL DESIGN WITH FIXES
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
    """Professional element picker with full scrollable area."""

    def __init__(self, parent, on_select: Callable[[str], None]) -> None:
        super().__init__(parent)
        self._on_select = on_select
        self.title("Select Element")
        self.geometry("500x600")
        self.minsize(450, 500)
        self.resizable(True, True)
        self.transient(parent)
        self.lift()
        self.focus_force()
        self._build()
        self.after(50, self._finalize)

    def _finalize(self) -> None:
        ThemeManager().apply(self)
        self.lift()
        self.focus_force()
        try: 
            self.grab_set()
        except Exception: 
            pass

    def _build(self) -> None:
        colors = ThemeManager().get_colors()
        
        # Main container with grid for footer
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Content (scrollable)
        self.grid_rowconfigure(2, weight=0)  # Footer
        self.grid_columnconfigure(0, weight=1)
        
        # ===== HEADER =====
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15,8))
        header.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(header, text="Select Element",
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=colors["accent"]).grid(row=0, column=0, columnspan=2, sticky="w")
        
        # Search
        ctk.CTkLabel(header, text="Search:", width=55, 
                    font=ctk.CTkFont(size=12)).grid(row=1, column=0, sticky="w", pady=(6,0))
        
        self._search_var = ctk.StringVar()
        entry = ctk.CTkEntry(header, textvariable=self._search_var,
                            placeholder_text="Type symbol or name...", 
                            height=35,
                            font=ctk.CTkFont(size=12))
        entry.grid(row=1, column=1, sticky="ew", padx=(6,0), pady=(6,0))
        entry.bind("<KeyRelease>", lambda _e: self._refresh())
        entry.focus_set()
        
        # Count
        self._count_label = ctk.CTkLabel(header, text="",
                                        font=ctk.CTkFont(size=11),
                                        text_color=colors["text_secondary"])
        self._count_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4,0))
        
        # ===== SCROLLABLE CONTENT (FULL HEIGHT) =====
        self._scroll = ctk.CTkScrollableFrame(
            self, 
            fg_color=colors["surface"]
        )
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(8,8))
        
        # ===== FOOTER =====
        footer = ctk.CTkFrame(self, fg_color=colors["surface"], height=70, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew", padx=0, pady=(0,0))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=1)
        
        # Separator line
        separator = ctk.CTkFrame(footer, fg_color=colors["border"], height=1)
        separator.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(0,12))
        
        # Cancel button
        ctk.CTkButton(footer, text="Cancel", height=38,
                     fg_color="transparent", 
                     text_color=colors["text"],
                     border_width=2, border_color=colors["border"],
                     hover_color=colors["border"],
                     font=ctk.CTkFont(size=12),
                     command=self.destroy
                     ).grid(row=1, column=0, sticky="ew", padx=(15,5), pady=(0,15))
        
        # Select button
        ctk.CTkButton(footer, text="Select Element", height=38,
                     fg_color=colors["accent"], 
                     text_color="white",
                     hover_color=colors["accent_hover"] if "accent_hover" in colors else colors["accent"],
                     font=ctk.CTkFont(size=12, weight="bold"),
                     command=self._select_from_list
                     ).grid(row=1, column=1, sticky="ew", padx=(5,15), pady=(0,15))
        
        self._refresh()

    def _select_from_list(self) -> None:
        """Select the first element in the list."""
        children = self._scroll.winfo_children()
        if children:
            for child in children:
                if isinstance(child, ctk.CTkFrame):
                    for subchild in child.winfo_children():
                        if isinstance(subchild, ctk.CTkButton):
                            text = subchild.cget("text")
                            symbol = text.split()[0]
                            self._pick(symbol)
                            return

    def _refresh(self) -> None:
        query = self._search_var.get().strip().lower()
        filtered = [
            (sym, num, name) for sym, num, name in _ALL_ELEMENTS
            if not query or query in sym.lower() or query in name.lower() or query == str(num)
        ]
        colors = ThemeManager().get_colors()
        
        # Clear
        for child in self._scroll.winfo_children():
            child.destroy()
        
        # Add buttons
        for sym, num, name in filtered:
            btn = ctk.CTkButton(self._scroll, 
                         text=f"{sym}  ({num})  {name}",
                         anchor="w", height=35,
                         fg_color="transparent", 
                         text_color=colors["text"],
                         hover_color=colors["border"],
                         font=ctk.CTkFont(size=12),
                         command=lambda s=sym: self._pick(s))
            btn.pack(fill="x", pady=2)
        
        self._count_label.configure(
            text=f"Showing {len(filtered)} of {len(_ALL_ELEMENTS)} elements")

    def _pick(self, symbol: str) -> None:
        try: 
            self.grab_release()
        except Exception: 
            pass
        cb = self._on_select
        self.destroy()
        cb(symbol)


class UserReactantDialog(BaseDialog):
    """Professional user-defined reactant dialog with footer buttons."""

    def __init__(self, parent,
                 on_confirm: Optional[Callable[[UserReactant], None]] = None,
                 existing: Optional[UserReactant] = None) -> None:
        self._on_confirm = on_confirm

        # Pre-initialise ALL attrs
        self._comp_vars: Dict[str, ctk.StringVar] = {}
        self._active_frame: Optional[ctk.CTkScrollableFrame] = None
        self._active_label: Optional[ctk.CTkLabel] = None
        self._message_label: Optional[ctk.CTkLabel] = None
        self._preview_label: Optional[ctk.CTkLabel] = None
        self._name_var: Optional[ctk.StringVar] = None
        self._weight_var: Optional[ctk.StringVar] = None
        self._temp_var: Optional[ctk.StringVar] = None
        self._enthalpy_var: Optional[ctk.StringVar] = None

        super().__init__(parent, title="Add Reactant", width=600, height=750)
        self._build(existing)

    def _build(self, existing: Optional[UserReactant]) -> None:
        colors = ThemeManager().get_colors()
        
        # Main body with grid for footer
        self.body.grid_rowconfigure(0, weight=1)  # Content
        self.body.grid_rowconfigure(1, weight=0)  # Footer
        self.body.grid_columnconfigure(0, weight=1)
        
        # ===== CONTENT FRAME =====
        content = ctk.CTkFrame(self.body, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=15, pady=(10,0))
        content.grid_columnconfigure(0, weight=1)

        # ===== PRESETS =====
        preset_frame = ctk.CTkFrame(content, fg_color="transparent")
        preset_frame.pack(fill="x", pady=(0,10))
        
        ctk.CTkLabel(preset_frame, text="Quick Presets", 
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=colors["accent"]).pack(side="left", padx=(0,12))
        
        preset_container = ctk.CTkFrame(preset_frame, fg_color="transparent")
        preset_container.pack(side="left")
        
        for pname in _PRESETS:
            ctk.CTkButton(preset_container, text=pname, width=75, height=30,
                         fg_color=colors["surface_alt"], 
                         text_color=colors["accent"],
                         hover_color=colors["border"],
                         font=ctk.CTkFont(size=11),
                         command=lambda n=pname: self._apply_preset(n)
                         ).pack(side="left", padx=(0,6))

        # ===== FIELDS =====
        fields_frame = ctk.CTkFrame(content, fg_color="transparent")
        fields_frame.pack(fill="x", pady=(0,12))
        fields_frame.grid_columnconfigure(1, weight=1)

        field_data = [
            ("Reactant Name", existing.name if existing else "", 0),
            ("Weight %", str(existing.weight_pct if existing else 14.0), 1),
            ("Temperature (K)", str(existing.temperature_k if existing else 298.0), 2),
            ("Enthalpy (kJ/mol)", str(existing.enthalpy_kj_mol if existing else -58.0), 3),
        ]
        
        field_vars = []
        for label, val, row in field_data:
            ctk.CTkLabel(fields_frame, text=label, anchor="w", 
                        font=ctk.CTkFont(size=12),
                        text_color=colors["text_secondary"]).grid(
                        row=row, column=0, sticky="w", padx=(0,8), pady=4)
            var = ctk.StringVar(value=val)
            field_vars.append(var)
            ctk.CTkEntry(fields_frame, textvariable=var, height=34,
                        font=ctk.CTkFont(size=12)).grid(
                        row=row, column=1, sticky="ew", padx=(0,4), pady=4)
        
        self._name_var, self._weight_var, self._temp_var, self._enthalpy_var = field_vars

        # ===== COMPOSITION SECTION =====
        comp_header = ctk.CTkFrame(content, fg_color="transparent")
        comp_header.pack(fill="x", pady=(8,6))
        
        ctk.CTkLabel(comp_header, text="Atomic Composition (moles per formula unit)",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=colors["accent"]).pack(side="left")
        
        ctk.CTkButton(comp_header, text="➕ Add Element", height=30, width=140,
                     fg_color=colors["surface_alt"], 
                     text_color=colors["accent"],
                     hover_color=colors["border"],
                     font=ctk.CTkFont(size=11),
                     command=self._open_element_picker).pack(side="right")

        # ===== QUICK GRID =====
        quick_frame = ctk.CTkFrame(content, fg_color=colors["surface"], 
                                  corner_radius=8)
        quick_frame.pack(fill="x", pady=(4,10))
        
        ctk.CTkLabel(quick_frame, text="⚡ Quick Access Elements",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=colors["text_secondary"]
                    ).pack(anchor="w", padx=12, pady=(8,4))
        
        grid_inner = ctk.CTkFrame(quick_frame, fg_color="transparent")
        grid_inner.pack(fill="x", padx=12, pady=(0,10))
        
        existing_comp = existing.composition if existing else {}
        
        for i, symbol in enumerate(_QUICK_ELEMENTS):
            row, col = divmod(i, 4)
            cell = ctk.CTkFrame(grid_inner, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="ew", padx=4, pady=3)
            
            ctk.CTkLabel(cell, text=symbol,
                        font=ctk.CTkFont(size=13, weight="bold"),
                        width=30, anchor="w").pack(side="left", padx=(2,4))
            
            var = self._ensure_comp_var(symbol, existing_comp.get(symbol, 0.0))
            ctk.CTkEntry(cell, textvariable=var, width=75, height=30,
                        font=ctk.CTkFont(size=12)).pack(side="left")
        
        for c in range(4):
            grid_inner.grid_columnconfigure(c, weight=1)

        # ===== EXTRA ELEMENTS =====
        self._active_label = ctk.CTkLabel(content, text="📦 Extra Elements: (none)",
                                         font=ctk.CTkFont(size=11),
                                         text_color=colors["text_secondary"])
        self._active_label.pack(anchor="w", pady=(4,4))
        
        self._active_frame = ctk.CTkScrollableFrame(
            content, fg_color=colors["surface"], height=80, corner_radius=6)
        self._active_frame.pack(fill="x", pady=(0,8))

        if existing:
            for symbol, amount in existing.composition.items():
                if symbol not in _QUICK_ELEMENTS:
                    self._ensure_comp_var(symbol, amount)

        # ===== PREVIEW =====
        preview_container = ctk.CTkFrame(content, fg_color=colors["surface"], corner_radius=6)
        preview_container.pack(fill="x", pady=(4,4))
        
        ctk.CTkLabel(preview_container, text="📋 Preview",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=colors["text_secondary"]
                    ).pack(anchor="w", padx=10, pady=(6,2))
        
        self._preview_label = ctk.CTkLabel(
            preview_container, text="",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=colors["text_secondary"],
            wraplength=540, justify="left")
        self._preview_label.pack(fill="x", padx=10, pady=(0,8))

        # ===== MESSAGE (ERROR) - MAKE SURE IT'S VISIBLE =====
        self._message_label = ctk.CTkLabel(
            content, text="", 
            text_color=colors["error"], 
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            wraplength=550
        )
        self._message_label.pack(fill="x", pady=(8,4))

        # ===== FOOTER =====
        footer = ctk.CTkFrame(self.body, fg_color=colors["surface"], height=80, corner_radius=0)
        footer.grid(row=1, column=0, sticky="ew", padx=0, pady=(12,0))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=1)
        
        # Separator line
        separator = ctk.CTkFrame(footer, fg_color=colors["border"], height=2)
        separator.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(0,14))
        
        # Cancel button
        ctk.CTkButton(footer, text="✖ Cancel", height=42,
                     fg_color="transparent", 
                     text_color=colors["text"],
                     border_width=2, border_color=colors["border"],
                     hover_color=colors["border"],
                     font=ctk.CTkFont(size=13),
                     command=self.on_close
                     ).grid(row=1, column=0, sticky="ew", padx=(20,8), pady=(0,16))
        
        # Confirm button
        ctk.CTkButton(footer, text="✔ Confirm - Add to Formulation", height=42,
                     fg_color=colors["accent"], 
                     text_color="white",
                     hover_color=colors["accent_hover"] if "accent_hover" in colors else colors["accent"],
                     font=ctk.CTkFont(size=13, weight="bold"),
                     command=self._confirm
                     ).grid(row=1, column=1, sticky="ew", padx=(8,20), pady=(0,16))

        # ===== TRACE =====
        for var in self._comp_vars.values():
            var.trace_add("write", lambda *_: self._update_preview())
        for var in field_vars:
            var.trace_add("write", lambda *_: self._update_preview())

        self._refresh_extra_elements_display()
        self._update_preview()

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
                    text=f"⚠ {symbol} is already in the composition")
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
            if self._active_label:
                self._active_label.configure(text="📦 Extra Elements: (none)")
            return

        if self._active_label:
            self._active_label.configure(text=f"📦 Extra Elements: {len(extra)}")

        for symbol in extra:
            info = _ELEM_INFO.get(symbol)
            el_name = info[1] if info else symbol

            row = ctk.CTkFrame(self._active_frame, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=6)
            
            ctk.CTkLabel(row, text=f"{symbol}  {el_name}",
                        font=ctk.CTkFont(family="Courier", size=11),
                        width=150, anchor="w").pack(side="left")
            
            ctk.CTkEntry(row, textvariable=self._comp_vars[symbol],
                        width=85, height=30,
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=(6,0))
            
            ctk.CTkLabel(row, text="mol", font=ctk.CTkFont(size=11),
                        text_color=colors["text_secondary"]).pack(side="left", padx=(4,0))
            
            ctk.CTkButton(row, text="✖ Remove", width=80, height=28,
                         fg_color=colors["button_danger"], 
                         hover_color="#EF5350",
                         font=ctk.CTkFont(size=10),
                         command=lambda s=symbol: self._remove_element(s)
                         ).pack(side="right", padx=(4,0))

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
            if key in ("weight","enthalpy"): continue
            if key not in _QUICK_ELEMENTS:
                self._ensure_comp_var(key, val)
        
        self._refresh_extra_elements_display()
        self._update_preview()
        if self._message_label:
            self._message_label.configure(text="")

    def _build_composition(self) -> Dict[str, float]:
        return {sym: safe_float(var.get(), 0.0)
                for sym, var in self._comp_vars.items()
                if safe_float(var.get(), 0.0) > 0.0}

    def _build_reactant(self) -> Optional[UserReactant]:
        name = (self._name_var.get().strip() if self._name_var else "")
        if not name: 
            return None
        composition = self._build_composition()
        if not composition: 
            return None
        return UserReactant(
            name=name,
            weight_pct=safe_float(self._weight_var.get() if self._weight_var else "100", 100.0),
            temperature_k=safe_float(self._temp_var.get() if self._temp_var else "298", 298.0),
            enthalpy_kj_mol=safe_float(self._enthalpy_var.get() if self._enthalpy_var else "0", 0.0),
            composition=composition)

    def _update_preview(self) -> None:
        if self._preview_label is None: 
            return
        reactant = self._build_reactant()
        self._preview_label.configure(
            text=reactant.to_inp_line() if reactant
            else "(Enter name and at least one element amount > 0)")
        
        # Clear error messages when user makes changes (except duplicate warnings)
        if self._message_label and self._message_label.cget("text") != "":
            current_msg = self._message_label.cget("text")
            if "already in the composition" not in current_msg:
                self._message_label.configure(text="")

    def _confirm(self) -> None:
        """Confirm button handler with proper validation."""
        
        # Clear previous message
        if self._message_label:
            self._message_label.configure(text="")
        
        # 1. Check if name is empty
        name = self._name_var.get().strip() if self._name_var else ""
        if not name:
            if self._message_label:
                self._message_label.configure(
                    text="❌ ERROR: Please enter a reactant name",
                    text_color="red"
                )
                # Make sure the message is visible
                self._message_label.update_idletasks()
            return
        
        # 2. Check if composition has any elements with values > 0
        composition = self._build_composition()
        if not composition:
            if self._message_label:
                self._message_label.configure(
                    text="❌ ERROR: Please add at least one element with amount > 0",
                    text_color="red"
                )
                self._message_label.update_idletasks()
            return
        
        # 3. Build the reactant
        reactant = self._build_reactant()
        if not reactant:
            if self._message_label:
                self._message_label.configure(
                    text="❌ ERROR: Invalid reactant data",
                    text_color="red"
                )
                self._message_label.update_idletasks()
            return
        
        # 4. Validate the reactant
        valid, message = reactant.validate()
        if not valid:
            if self._message_label:
                self._message_label.configure(
                    text=f"❌ ERROR: {message}",
                    text_color="red"
                )
                self._message_label.update_idletasks()
            return
        
        # 5. All valid - confirm and close
        if self._on_confirm:
            self._on_confirm(reactant)
        self.on_close()
