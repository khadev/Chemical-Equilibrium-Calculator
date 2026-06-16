"""
models/data_layer.py -- DATA LAYER

Manages all application state:
    - Species database loaded from databasecea.txt (immutable)
    - User custom species (user_custom.json)
    - Saved User-Defined Reactants (saved_udrs.json)
    - Active formulation state
    - Configuration persistence

Never imports from UI layer.
"""
from __future__ import annotations
import os
import json
import re
import copy
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH     = os.path.join(_ROOT, "database", "databasecea.txt")
_CUSTOM_PATH = os.path.join(_ROOT, "database", "user_custom.json")
_UDR_PATH    = os.path.join(_ROOT, "database", "saved_udrs.json")
_CFG_PATH    = os.path.join(_ROOT, "config",   "config.json")


# Config defaults
_DEFAULTS: Dict[str, Any] = {
    "language": "en",
    "theme":    "light",
    "paths": {
        "fcea2_exe":    "",
        "thermo_lib":   "",
        "trans_lib":    "",
        "cea_work_dir": "",
    },
    "units": {
        "pressure":    "bar",
        "temperature": "K",
        "isp":         "m/s",
        "thrust":      "kN",
    },
    "display": {
        "show_legend":      True,
        "show_data_points": True,
        "line_thickness":   2,
    },
    "window": {"width": 1400, "height": 880},
    "app":    {"name": "CEA Calculator Pro", "version": "1.0.0",
               "author": "Oukil Khaled Ibn Elwalid"},
}


# Formulation dataclass
@dataclass
class UserReactant:
    """A user-defined reactant (HTPB, MCCN...) with explicit composition."""
    name:          str
    wt:            float = 14.0
    temp_k:        float = 298.0
    enthalpy_kj:   float = 0.0
    composition:   Dict[str, float] = field(default_factory=dict)

    def to_inp_line(self) -> str:
        parts = [f"name={self.name}"]
        if self.wt not in (0.0, 100.0):
            parts.append(f"wt={self.wt:.4g}")
        parts.append(f"t,k={self.temp_k:.1f}")
        if self.enthalpy_kj != 0.0:
            parts.append(f"h,kj/mol={self.enthalpy_kj:.4g}")
        for el, amt in self.composition.items():
            parts.append(f"{el} {amt:.3f}")
        return " ".join(parts)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "wt": self.wt,
            "temp_k": self.temp_k,
            "enthalpy_kj": self.enthalpy_kj,
            "composition": self.composition
        }


@dataclass
class Formulation:
    """Complete propellant formulation."""
    name: str = "Formulation 1"

    # Oxidizer
    oxidizer_name:     str   = ""
    oxidizer_temp:     float = 298.0
    oxidizer_wt:       float = 68.0
    oxidizer_enthalpy: float = 0.0
    oxidizer_formula:  Dict[str, float] = field(default_factory=dict)

    # Fuel
    fuel_name:     str   = ""
    fuel_temp:     float = 298.0
    fuel_wt:       float = 18.0
    fuel_enthalpy: float = 0.0
    fuel_formula:  Dict[str, float] = field(default_factory=dict)

    # User-defined reactants
    user_reactants: List[Dict] = field(default_factory=list)

    # Conditions
    chamber_pressure: float = 50.0
    of_ratio:         float = 2.5
    exit_pressure:    float = 1.0
    area_ratio:       float = 10.0
    tcest:            int   = 3800
    frozen:           bool  = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Formulation":
        f = cls()
        for k, v in d.items():
            if hasattr(f, k):
                setattr(f, k, v)
        return f


# Species database
class SpeciesDatabase:
    """
    Loads and exposes the species lists from databasecea.txt.
    Oxidizers and fuels are kept strictly separate to prevent mixing.
    Thread-safe singleton.
    """
    _inst: Optional["SpeciesDatabase"] = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
            cls._inst._load()
        return cls._inst

    def _load(self) -> None:
        self.oxidizers: List[str]  = []
        self.fuels:     List[str]  = []
        self.named:     List[str]  = []
        self.presets:   List[dict] = []
        self._ox_set:   set        = set()
        self._fu_set:   set        = set()
        self.user_custom: List[dict] = []
        self.saved_udrs: List[dict] = []

        if not os.path.exists(_DB_PATH):
            log.error("databasecea.txt not found at %s", _DB_PATH)
            return

        ns: dict = {}
        try:
            with open(_DB_PATH, "r", encoding="utf-8") as fh:
                exec(fh.read(), ns)
            self.oxidizers = ns.get("ALL_OXIDIZER_SPECIES", [])
            self.fuels     = ns.get("ALL_FUEL_SPECIES",     [])
            self.named     = ns.get("ALL_NAMED_SPECIES",    [])
            self.presets   = ns.get("FUEL_PRESETS",         [])
            self._ox_set   = set(self.oxidizers)
            self._fu_set   = set(self.fuels) | set(self.named)
            log.info("DB: %d oxidizers, %d fuels, %d presets",
                     len(self.oxidizers), len(self.fuels), len(self.presets))
        except Exception as e:
            log.error("DB load failed: %s", e)

        self._load_custom()
        self._load_saved_udrs()

    def _load_custom(self) -> None:
        """Load custom species from JSON file."""
        if not os.path.exists(_CUSTOM_PATH):
            log.info(f"No custom species file at {_CUSTOM_PATH}")
            self.user_custom = []
            return
        try:
            with open(_CUSTOM_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                self.user_custom = data.get("species", [])
            log.info(f"Loaded {len(self.user_custom)} custom species")
        except Exception as e:
            log.warning(f"Custom species load: {e}")
            self.user_custom = []

    def _load_saved_udrs(self) -> None:
        """Load saved user-defined reactants from JSON file."""
        if not os.path.exists(_UDR_PATH):
            log.info(f"No saved UDRs file at {_UDR_PATH}")
            self.saved_udrs = []
            return
        try:
            with open(_UDR_PATH, "r", encoding="utf-8") as fh:
                self.saved_udrs = json.load(fh)
            log.info(f"Loaded {len(self.saved_udrs)} saved UDRs")
        except Exception as e:
            log.warning(f"Saved UDRs load: {e}")
            self.saved_udrs = []

    # Accessors
    def all_oxidizers(self) -> List[str]:
        return list(self.oxidizers)

    def all_fuels(self) -> List[str]:
        """Return all fuel species (built-in + custom)."""
        built_in = list(self.fuels) + list(self.named)
        custom = [c["name"] for c in self.user_custom]
        return built_in + custom

    def is_oxidizer(self, name: str) -> bool:
        return name in self._ox_set

    def is_fuel(self, name: str) -> bool:
        if name in self._fu_set:
            return True
        return any(c["name"] == name for c in self.user_custom)

    def search_oxidizers(self, query: str) -> List[str]:
        q = query.lower()
        return [s for s in self.oxidizers if q in s.lower()]

    def search_fuels(self, query: str) -> List[str]:
        q = query.lower()
        pool = self.all_fuels()
        return [s for s in pool if q in s.lower()]

    def get_preset(self, name: str) -> Optional[dict]:
        for p in self.presets:
            if p["name"] == name:
                return p
        return None

    def add_custom(self, species: dict) -> tuple:
        """Add a custom species to the database."""
        name = species.get("name", "")
        if not name:
            return False, "Name cannot be empty."
        
        if self.is_oxidizer(name) or self.is_fuel(name):
            return False, f"'{name}' already exists."
        
        if not species.get("composition"):
            return False, "Composition required."
        
        custom_entry = {
            "name": name,
            "composition": species.get("composition", {}),
            "enthalpy": species.get("enthalpy", 0.0),
            "type": species.get("type", "fuel"),
            "wt": species.get("wt", 100.0),
            "temp_k": species.get("temp_k", 298.0)
        }
        
        self.user_custom.append(custom_entry)
        self._fu_set.add(name)
        self._save_custom()
        log.info(f"Added custom species: {name}")
        return True, f"'{name}' added successfully."

    def _save_custom(self) -> None:
        """Save custom species to JSON file."""
        os.makedirs(os.path.dirname(_CUSTOM_PATH), exist_ok=True)
        try:
            with open(_CUSTOM_PATH, "w", encoding="utf-8") as fh:
                json.dump({"species": self.user_custom}, fh, indent=2)
            log.info(f"Saved {len(self.user_custom)} custom species")
        except Exception as e:
            log.error(f"Failed to save custom species: {e}")
    
    def get_custom_species(self) -> List[dict]:
        """Return list of custom species."""
        return self.user_custom

    # Saved User-Defined Reactants
    def add_saved_udr(self, udr: dict) -> tuple:
        """Add a user-defined reactant to saved list."""
        name = udr.get("name", "")
        if not name:
            return False, "Name cannot be empty."
        
        # Check if already exists
        for existing in self.saved_udrs:
            if existing.get("name") == name:
                return False, f"'{name}' already exists in saved UDRs."
        
        self.saved_udrs.append(udr)
        self._save_saved_udrs()
        log.info(f"Saved UDR: {name}")
        return True, f"'{name}' saved."

    def get_saved_udrs(self) -> List[dict]:
        """Return list of saved user-defined reactants."""
        return self.saved_udrs

    def _save_saved_udrs(self) -> None:
        """Save user-defined reactants to JSON file."""
        os.makedirs(os.path.dirname(_UDR_PATH), exist_ok=True)
        try:
            with open(_UDR_PATH, "w", encoding="utf-8") as fh:
                json.dump(self.saved_udrs, fh, indent=2)
            log.info(f"Saved {len(self.saved_udrs)} UDRs")
        except Exception as e:
            log.error(f"Failed to save UDRs: {e}")


# Config manager
class ConfigManager:
    _inst: Optional["ConfigManager"] = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
            cls._inst._data = copy.deepcopy(_DEFAULTS)
            cls._inst._load()
        return cls._inst

    def _load(self) -> None:
        if not os.path.exists(_CFG_PATH):
            return
        try:
            with open(_CFG_PATH, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self._deep_merge(self._data, loaded)
        except Exception as e:
            log.warning("Config load: %s", e)

    def save(self) -> None:
        os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
        try:
            with open(_CFG_PATH, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
        except Exception as e:
            log.error("Config save: %s", e)

    def get(self, *keys, default=None):
        node = self._data
        for k in keys:
            if isinstance(node, dict):
                node = node.get(k)
            else:
                return default
        return node if node is not None else default

    def set(self, *keys_and_value) -> None:
        *keys, value = keys_and_value
        node = self._data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value

    def fcea2_exe(self) -> str:
        return self.get("paths", "fcea2_exe") or ""

    def cea_work_dir(self) -> str:
        return self.get("paths", "cea_work_dir") or ""

    def cea_available(self) -> bool:
        exe = self.fcea2_exe()
        return bool(exe and os.path.isfile(exe))

    @staticmethod
    def _deep_merge(base: dict, over: dict) -> None:
        for k, v in over.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                ConfigManager._deep_merge(base[k], v)
            else:
                base[k] = v

    def tr(self, key: str) -> str:
        lang = self._data.get("language", "en")
        _tr_cache = getattr(self, "_tr_cache", None)
        if _tr_cache is None:
            _tr_path = os.path.join(
                os.path.dirname(_CFG_PATH), "translations.json")
            try:
                with open(_tr_path, "r", encoding="utf-8") as fh:
                    self._tr_cache = json.load(fh)
            except Exception:
                self._tr_cache = {}
        d = self._tr_cache
        return d.get(lang, {}).get(key) or d.get("en", {}).get(key, key)