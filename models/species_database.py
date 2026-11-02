
"""
models/species_database.py
============================
Chemical species database loaded from ``database/species.txt`` plus
any user-imported thermo.lib/trans.lib data persisted in
``database/imported_species.json``.

Two access modes are exposed, matching real CEA semantics:

  * **Curated** (``all_oxidizers()`` / ``all_fuels()``) — strictly
    disjoint, hand-picked lists for guided quick-pick. Grouped into
    categories via ``oxidizer_categories()`` / ``fuel_categories()``.
  * **Imported / All Species** (``imported_species()``) — an
    unrestricted pool parsed from a real thermo.lib file. CEA itself
    has no concept of "this species is an oxidizer" — any species can
    be assigned to either role — so imported species are not forced
    into oxidizer/fuel buckets.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict
from typing import Dict, List, Optional

from core.thermo_lib_parser import ImportedSpecies, ThermoLibParser
from core.trans_lib_parser import TransLibParser, TransportSpecies

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_ROOT, "database", "species.txt")
_IMPORTED_PATH = os.path.join(_ROOT, "database", "imported_species.json")


class SpeciesDatabase:
    """Singleton species database — curated lists + optional imported pool."""

    _instance: Optional["SpeciesDatabase"] = None

    def __new__(cls) -> "SpeciesDatabase":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._oxidizers: List[str] = []
            inst._fuels: List[str] = []
            inst._named_fuels: List[str] = []
            inst._oxidizer_categories: Dict[str, List[str]] = {}
            inst._fuel_categories: Dict[str, List[str]] = {}
            inst._ox_set: set = set()
            inst._fuel_set: set = set()
            inst._imported: List[ImportedSpecies] = []
            inst._transport_names: set = set()
            inst._load_curated()
            inst._load_imported()
            cls._instance = inst
        return cls._instance

    # ── Loading: curated ──────────────────────────────────────────────
    def _load_curated(self) -> None:
        """Parse ``database/species.txt`` into curated lists and categories."""
        if not os.path.exists(_DB_PATH):
            log.error("Species database not found: %s", _DB_PATH)
            return

        namespace: Dict = {}
        try:
            with open(_DB_PATH, "r", encoding="utf-8") as fh:
                exec(fh.read(), namespace)  # noqa: S102 — trusted local file
            self._oxidizers = namespace.get("OXIDIZERS", [])
            self._fuels = namespace.get("FUELS", [])
            self._named_fuels = namespace.get("NAMED_FUELS", [])
            self._oxidizer_categories = namespace.get("OXIDIZER_CATEGORIES", {})
            self._fuel_categories = namespace.get("FUEL_CATEGORIES", {})
            self._ox_set = set(self._oxidizers)
            self._fuel_set = set(self._fuels) | set(self._named_fuels)
            log.info(
                "SpeciesDatabase loaded: %d oxidizers, %d fuels (curated)",
                len(self._oxidizers), len(self._fuels) + len(self._named_fuels))
        except Exception as exc:
            log.error("Failed to parse species database: %s", exc)

    # ── Loading: imported pool ────────────────────────────────────────
    def _load_imported(self) -> None:
        """Load any previously imported thermo.lib/trans.lib species."""
        if not os.path.exists(_IMPORTED_PATH):
            return
        try:
            with open(_IMPORTED_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._imported = [
                ImportedSpecies(**item) for item in data.get("species", [])
            ]
            self._transport_names = set(data.get("transport_names", []))
            log.info("Loaded %d previously imported species",
                     len(self._imported))
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            log.error("Failed to load imported species: %s", exc)

    def _save_imported(self) -> None:
        """Persist the imported species pool to disk."""
        os.makedirs(os.path.dirname(_IMPORTED_PATH), exist_ok=True)
        
        # Clean species names before saving
        cleaned_species = []
        for s in self._imported:
            clean_name = self._clean_species_name(s.name)
            if clean_name:
                cleaned_species.append(ImportedSpecies(
                    name=clean_name,
                    phase=s.phase,
                    source_line=s.source_line
                ))
        
        data = {
            "species": [asdict(s) for s in cleaned_species],
            "transport_names": sorted(self._transport_names),
        }
        try:
            with open(_IMPORTED_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            log.error("Failed to save imported species: %s", exc)

    def _clean_species_name(self, name: str) -> str:
        """
        Clean a species name from thermo.lib.
        Removes garbage characters and invalid symbols.
        """
        if not name:
            return ""
        
        # Remove non-printable characters
        name = ''.join(c for c in name if c.isprintable())
        
        # Remove leading/trailing whitespace
        name = name.strip()
        
        # Remove asterisks and other garbage
        name = name.replace('*', '').strip()
        
        # Remove control characters
        name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
        
        # If the name contains spaces, take the first token
        if ' ' in name:
            name = name.split()[0]
        
        # Remove any trailing garbage like "tpis96", "g12/97", etc.
        name = re.sub(r'\s+[a-z0-9/]+$', '', name)
        
        # Remove any special characters that aren't allowed in species names
        name = re.sub(r'[^a-zA-Z0-9()\-,.]', '', name)
        
        # If the name is too short or empty, skip it
        if len(name) < 2:
            return ""
        
        # Check if it's a valid species name (starts with a letter)
        if not name[0].isalpha():
            return ""
        
        return name

    # ── Import operations ──────────────────────────────────────────────
    def import_thermo_lib(self, path: str) -> int:
        """
        Parse and merge species from a thermo.lib file into the
        imported pool, deduplicating by name.
        """
        parsed = ThermoLibParser().parse(path)
        existing_names = {s.name for s in self._imported}
        
        new_species = []
        for s in parsed:
            clean_name = self._clean_species_name(s.name)
            if clean_name and clean_name not in existing_names:
                new_species.append(ImportedSpecies(
                    name=clean_name,
                    phase=s.phase,
                    source_line=s.source_line
                ))
                existing_names.add(clean_name)
        
        self._imported.extend(new_species)
        self._save_imported()
        log.info("Imported %d new species (%d total) from %s",
                 len(new_species), len(self._imported), path)
        return len(new_species)

    def import_trans_lib(self, path: str) -> int:
        """
        Parse a trans.lib file and record which species have
        transport (viscosity/conductivity) data available.
        """
        parsed = TransLibParser().parse(path)
        before = len(self._transport_names)
        
        cleaned_names = set()
        for s in parsed:
            clean_name = self._clean_species_name(s.name)
            if clean_name:
                cleaned_names.add(clean_name)
        
        self._transport_names |= cleaned_names
        self._save_imported()
        added = len(self._transport_names) - before
        log.info("Tagged %d new species with transport data from %s",
                 added, path)
        return added

    def clear_imported(self) -> None:
        """Remove all imported species/transport data (revert to curated only)."""
        self._imported.clear()
        self._transport_names.clear()
        self._save_imported()

    # ── Public accessors: curated ──────────────────────────────────────
    def all_oxidizers(self) -> List[str]:
        """Return the curated, sorted oxidizer species list."""
        return list(self._oxidizers)

    def all_fuels(self) -> List[str]:
        """Return the curated fuel species list (standard + named)."""
        return list(self._fuels) + list(self._named_fuels)

    def oxidizer_categories(self) -> Dict[str, List[str]]:
        """Return curated oxidizers grouped by category."""
        return dict(self._oxidizer_categories)

    def fuel_categories(self) -> Dict[str, List[str]]:
        """Return curated fuels grouped by category."""
        return dict(self._fuel_categories)

    def is_oxidizer(self, name: str) -> bool:
        """Return True if ``name`` is a curated oxidizer species."""
        return name in self._ox_set

    def is_fuel(self, name: str) -> bool:
        """Return True if ``name`` is a curated fuel species."""
        return name in self._fuel_set

    def is_known_species(self, name: str) -> bool:
        """Return True if ``name`` is curated OR imported (any role)."""
        return (name in self._ox_set or name in self._fuel_set
                or name in self.imported_names())

    def search_oxidizers(self, query: str) -> List[str]:
        """Case-insensitive substring search over curated oxidizers."""
        q = query.lower()
        return [s for s in self._oxidizers if q in s.lower()]

    def search_fuels(self, query: str) -> List[str]:
        """Case-insensitive substring search over curated fuels."""
        q = query.lower()
        return [s for s in self.all_fuels() if q in s.lower()]

    # ── Public accessors: imported pool ────────────────────────────────
    def imported_species(self) -> List[ImportedSpecies]:
        """Return all imported thermo.lib species records."""
        return list(self._imported)

    def imported_names(self) -> List[str]:
        """Return just the names of all imported species, sorted."""
        return sorted(s.name for s in self._imported)

    def has_transport_data(self, name: str) -> bool:
        """Return True if ``name`` has imported trans.lib data."""
        return name in self._transport_names

    def all_species_pool(self) -> List[str]:
        """
        Return the unrestricted combined pool: curated oxidizers +
        curated fuels + all imported species, deduplicated.
        """
        pool = set(self._oxidizers) | set(self._fuels) | set(self._named_fuels)
        pool |= set(self.imported_names())
        return sorted(pool)

    def import_summary(self) -> Dict[str, int]:
        """Return counts for the Import Database dialog's status display."""
        return {
            "imported_species": len(self._imported),
            "transport_species": len(self._transport_names),
            "curated_oxidizers": len(self._oxidizers),
            "curated_fuels": len(self._fuels) + len(self._named_fuels),
        }

    def normalize_species(self, name: str) -> str:
        """Normalize a species name using the alias map."""
        return normalize_species_name(name)


# ── Species name normalization ──────────────────────────────────────────
_ALIAS_MAP: Dict[str, str] = {
    # ===== CRYOGENIC OXIDIZERS =====
    "LOX": "O2(L)",
    "LO2": "O2(L)",
    "GOX": "O2",
    "O2(L)": "O2(L)",
    "O2": "O2",
    "F2(L)": "F2(L)",
    "F2": "F2",
    "O3(L)": "O3(L)",
    "O3": "O3",
    "FLOX(L)": "FLOX(L)",
    "OF2": "OF2",
    
    # ===== STORABLE OXIDIZERS =====
    "NTO": "N2O4(L)",
    "N2O4": "N2O4(L)",
    "N2O4(L)": "N2O4(L)",
    "N2O3(L)": "N2O3(L)",
    "MON10": "MON-10(L)",
    "MON-10": "MON-10(L)",
    "MON10(L)": "MON-10(L)",
    "MON25": "MON-25(L)",
    "MON-25": "MON-25(L)",
    "MON25(L)": "MON-25(L)",
    "RFNA": "RFNA(L)",
    "RFNA(L)": "RFNA(L)",
    "IRFNA": "IRFNA-III(L)",
    "IRFNA-III": "IRFNA-III(L)",
    "IRFNA-III(L)": "IRFNA-III(L)",
    "IRFNA-IV": "IRFNA-IV(L)",
    "IRFNA-IV(L)": "IRFNA-IV(L)",
    "HNO3": "HNO3(L)",
    "HNO3(L)": "HNO3(L)",
    "H2O2": "H2O2(L)",
    "H2O2(L)": "H2O2(L)",
    "CLF3": "ClF3(L)",
    "CLF3(L)": "ClF3(L)",
    "CLF5": "ClF5(L)",
    "CLF5(L)": "ClF5(L)",
    "BRF3": "BrF3",
    "BRF5": "BrF5",
    "IF5": "IF5",
    "N2F4": "N2F4",
    "NF3": "NF3(L)",
    "NF3(L)": "NF3(L)",
    "N2O": "N2O",
    "NO2": "NO2",
    "NO": "NO",
    "ONF3": "ONF3",
    
    # ===== SOLID OXIDIZERS =====
    "AP": "NH4ClO4(I)",
    "NH4CLO4": "NH4ClO4(I)",
    "NH4CLO4(I)": "NH4ClO4(I)",
    "NH4CLO4(L)": "NH4ClO4(I)",
    "NH4CLO4(II)": "NH4ClO4(II)",
    "NH4CLO4(III)": "NH4ClO4(III)",
    "AMMONIUM PERCHLORATE": "NH4ClO4(I)",
    "NH4NO3": "NH4NO3(I)",
    "NH4NO3(I)": "NH4NO3(I)",
    "NH4NO3(II)": "NH4NO3(II)",
    "NH4NO3(III)": "NH4NO3(III)",
    "NH4NO3(IV)": "NH4NO3(IV)",
    "NH4NO3(L)": "NH4NO3(L)",
    "KNO3": "KNO3(a)",
    "KNO3(A)": "KNO3(a)",
    "KNO3(B)": "KNO3(b)",
    "KNO3(L)": "KNO3(L)",
    "NANO3": "NaNO3(a)",
    "NANO3(A)": "NaNO3(a)",
    "NANO3(B)": "NaNO3(b)",
    "NANO3(L)": "NaNO3(L)",
    "LICLO4": "LiClO4(cr)",
    "LICLO4(CR)": "LiClO4(cr)",
    "LICLO4(L)": "LiClO4(L)",
    "KCLO4": "KClO4(cr)",
    "KCLO4(CR)": "KClO4(cr)",
    "NACLO4": "NaClO4(cr)",
    "NACLO4(CR)": "NaClO4(cr)",
    "ADN": "ADN",
    "HAN": "HAN",
    "AN/AC": "AN/AC",
    "DNAN": "DNAN",
    
    # ===== SPECIALTY OXIDIZERS =====
    "AIR": "Air",
    "CO2": "CO2",
    "SO2": "SO2",
    "SO3": "SO3",
    "CL2O7": "Cl2O7",
    "CLO3F": "ClO3F",
    "HCLO4": "HClO4(L)",
    "HCLO4(L)": "HClO4(L)",
    
    # ===== CRYOGENIC FUELS =====
    "LH2": "H2(L)",
    "GH2": "H2",
    "H2(L)": "H2(L)",
    "H2": "H2",
    "LCH4": "CH4(L)",
    "METHANE": "CH4",
    "CH4(L)": "CH4(L)",
    "CH4": "CH4",
    "C2H6(L)": "C2H6(L)",
    "C2H6": "C2H6",
    "C2H4(L)": "C2H4(L)",
    "C2H4": "C2H4",
    "C3H8(L)": "C3H8(L)",
    "C3H8": "C3H8",
    "SLUSH-H2": "Slush-H2",
    "SLUSHH2": "Slush-H2",
    
    # ===== HYDROCARBON FUELS =====
    "RP1": "RP-1",
    "RP-1": "RP-1",
    "RP2": "RP-2",
    "RP-2": "RP-2",
    "RG1": "RG-1",
    "RG-1": "RG-1",
    "KEROSENE": "RP-1",
    "JP4": "JP-4",
    "JP-4": "JP-4",
    "JP5": "JP-5",
    "JP-5": "JP-5",
    "JP7": "JP-7",
    "JP-7": "JP-7",
    "JP8": "JP-8",
    "JP-8": "JP-8",
    "JP10": "JP-10(L)",
    "JP-10": "JP-10(L)",
    "JP-10(L)": "JP-10(L)",
    "JET-A": "Jet-A(L)",
    "JETA": "Jet-A(L)",
    "JET-A(L)": "Jet-A(L)",
    "DIESEL": "Diesel",
    "N-HEPTANE": "n-Heptane",
    "NHEPTANE": "n-Heptane",
    "N-OCTANE": "n-Octane",
    "NOCTANE": "n-Octane",
    "ISOOCTANE": "Isooctane",
    "CYCLOHEXANE": "Cyclohexane",
    "BENZENE": "Benzene",
    "TOLUENE": "Toluene",
    "XYLENE": "Xylene",
    
    # ===== ALCOHOLS =====
    "CH3OH": "CH3OH(L)",
    "CH3OH(L)": "CH3OH(L)",
    "METHANOL": "CH3OH(L)",
    "C2H5OH": "C2H5OH(L)",
    "C2H5OH(L)": "C2H5OH(L)",
    "ETHANOL": "C2H5OH(L)",
    "C3H7OH": "C3H7OH(L)",
    "C3H7OH(L)": "C3H7OH(L)",
    "PROPANOL": "C3H8O,1propanol",
    "N-BUTANOL": "n-Butanol",
    "BUTANOL": "n-Butanol",
    "METHANOL/WATER": "Methanol/Water",
    
    # ===== HYPERGOLIC FUELS =====
    "HYDRAZINE": "N2H4(L)",
    "N2H4": "N2H4(L)",
    "N2H4(L)": "N2H4(L)",
    "MMH": "MMH(L)",
    "MMH(L)": "MMH(L)",
    "MONOMETHYLHYDRAZINE": "MMH(L)",
    "UDMH": "C2H8N2(L),UDMH",
    "UNSYMMETRICAL DIMETHYLHYDRAZINE": "C2H8N2(L),UDMH",
    "C2H8N2(L),UDMH": "C2H8N2(L),UDMH",
    "AEROZINE": "Aerozine-50",
    "AEROZINE-50": "Aerozine-50",
    "N2H4/UDMH": "N2H4/UDMH",
    
    # ===== ESTERS / ETHERS =====
    "CH3OCH3": "CH3OCH3",
    "DME": "CH3OCH3",
    "ETHYLENE OXIDE": "C2H4O,ethylen-o",
    "ACETIC ACID": "CH3COOH",
    "CH3COOH": "CH3COOH",
    "ACETONE": "C3H6O,acetone",
    "C3H6O,ACETONE": "C3H6O,acetone",
    "HCOOH": "HCOOH",
    "FORMIC ACID": "HCOOH",
    "GLUCOSE": "C6H12O6",
    "BIODIESEL": "Biodiesel",
    "TEA-TEB": "TEA-TEB",
    "TRIETHYLALUMINUM": "Triethylaluminum",
    
    # ===== METALS =====
    "AL": "Al(cr)",
    "AL(CR)": "Al(cr)",
    "AL(L)": "Al(cr)",
    "ALUMINUM": "Al(cr)",
    "ALUMINIUM": "Al(cr)",
    "BE": "Be(cr)",
    "BE(CR)": "Be(cr)",
    "BE(L)": "Be(L)",
    "BERYLLIUM": "Be(cr)",
    "B": "B(b)",
    "B(B)": "B(b)",
    "B(L)": "B(L)",
    "BORON": "B(b)",
    "MG": "Mg(cr)",
    "MG(CR)": "Mg(cr)",
    "MG(L)": "Mg(L)",
    "MAGNESIUM": "Mg(cr)",
    "LI": "Li(cr)",
    "LI(CR)": "Li(cr)",
    "LI(L)": "Li(L)",
    "LITHIUM": "Li(cr)",
    "ZR": "Zr(cr)",
    "ZR(CR)": "Zr(cr)",
    "ZIRCONIUM": "Zr(cr)",
    "TI": "Ti(cr)",
    "TI(CR)": "Ti(cr)",
    "TITANIUM": "Ti(cr)",
    "ALH3": "AlH3(cr)",
    "ALH3(CR)": "AlH3(cr)",
    "ALUMINUM HYDRIDE": "AlH3(cr)",
    "ALANE": "AlH3(cr)",
    
    # ===== HYBRID SOLID FUELS =====
    "PARAFFIN": "Paraffin",
    "PARAFFIN WAX": "Paraffin",
    "ABS": "ABS(cr)",
    "ABS(CR)": "ABS(cr)",
    "PE": "PE(cr)",
    "PE(CR)": "PE(cr)",
    "POLYETHYLENE": "PE(cr)",
    "PMMA": "PMMA(cr)",
    "PMMA(CR)": "PMMA(cr)",
    "ACRYLIC": "PMMA(cr)",
    "PVC": "PVC(cr)",
    "PVC(CR)": "PVC(cr)",
    "POLYVINYL CHLORIDE": "PVC(cr)",
    
    # ===== BORANES =====
    "B2H6": "B2H6(L)",
    "B2H6(L)": "B2H6(L)",
    "DIBORANE": "B2H6(L)",
    "B5H9": "B5H9(L)",
    "B5H9(L)": "B5H9(L)",
    "PENTABORANE": "B5H9(L)",
    "B10H14": "B10H14",
    "DECABORANE": "B10H14",
    
    # ===== BINDERS (User-Defined) =====
    "HTPB": "HTPB",
    "HYDROXYL-TERMINATED POLYBUTADIENE": "HTPB",
    "MCCN": "MCCN",
    "OCN": "OCN",
    "NCS": "NCS",
    "NPS": "NCS",  # NPS = Nitrocellulose Plasticized System
    "NCT": "NCT",
    "GAP": "GAP",
    "GLYCIDYL AZIDE POLYMER": "GAP",
    "PEG": "PEG",
    "POLYETHYLENE GLYCOL": "PEG",
    "PBAN": "PBAN",
    "POLYBUTADIENE ACRYLONITRILE": "PBAN",
    "CTPB": "CTPB",
    "CARBOXYL-TERMINATED POLYBUTADIENE": "CTPB",
    "HTPE": "HTPE",
    "DESMOPHEN": "Desmophen",
    
    # ===== NC/NCS BINDERS =====
    "NC": "NC",
    "NITROCELLULOSE": "NC",
    "NCS": "NCS",
    "NPS": "NCS",  # NPS = Nitrocellulose Plasticized System
    "NITROCELLULOSE STABILIZED": "NCS",
    "NITROCELLULOSE PLASTICIZED": "NCS",
}
_STRIP_RE = re.compile(r"[\s_\-]+")


def normalize_species_name(name: str) -> str:
    """
    Map a common alias (LOX, RP1, AP, ...) to its canonical CEA name.

    Args:
        name: Raw species name as typed by the user or read from a file.

    Returns:
        The canonical species name, or the original string unchanged
        if no alias matches.
    """
    if not name:
        return name
    
    stripped = name.strip()
    
    # Try exact match first (case-insensitive)
    key = stripped.upper()
    if key in _ALIAS_MAP:
        return _ALIAS_MAP[key]
    
    # Try without spaces, underscores, hyphens
    simplified = _STRIP_RE.sub("", stripped).upper()
    if simplified in _ALIAS_MAP:
        return _ALIAS_MAP[simplified]
    
    # If it contains "(L)" with lowercase L, try replacing with "(I)"
    if "(L)" in stripped and "I" in stripped.replace("(L)", "").upper():
        upper_key = stripped.upper().replace("(L)", "(I)")
        if upper_key in _ALIAS_MAP:
            return _ALIAS_MAP[upper_key]
    
    # Try to find a case-insensitive match in the alias map
    for alias, canonical in _ALIAS_MAP.items():
        if alias.upper() == stripped.upper():
            return canonical
    
    # Return the stripped name (maybe with corrected casing)
    if stripped.upper() == "AL":
        return "Al(cr)"
    if stripped.upper() == "BE":
        return "Be(cr)"
    if stripped.upper() == "MG":
        return "Mg(cr)"
    if stripped.upper() == "LI":
        return "Li(cr)"
    if stripped.upper() == "ZR":
        return "Zr(cr)"
    if stripped.upper() == "TI":
        return "Ti(cr)"
    if stripped.upper() == "B":
        return "B(b)"
    if stripped.upper() == "NH4CLO4":
        return "NH4ClO4(I)"
    
    return stripped
