"""
engine/species_normalizer.py
============================
NASA species alias normalization map.
Maps common shorthand / alternate formats → canonical CEA library names.
Used before validation so NASA GUI files with slightly different spellings
are accepted without false "species not found" errors.
"""
from __future__ import annotations
import re
from typing import Dict, Optional

# ── Normalization map: alias → canonical ──────────────────────────────
# Keys are upper-case for case-insensitive lookup.
ALIAS_MAP: Dict[str, str] = {
    # Ammonium perchlorate variants
    "NH4CLO4":        "NH4ClO4(I)",
    "NH4CLO4(I)":     "NH4ClO4(I)",
    "NH4CLO4(II)":    "NH4ClO4(II)",
    "AP":             "NH4ClO4(I)",
    "NH4PERCHLORATE": "NH4ClO4(I)",

    # Ammonium nitrate
    "NH4NO3":         "NH4NO3(IV)",
    "AN":             "NH4NO3(IV)",

    # Liquid oxygen
    "LOX":            "O2(L)",
    "LO2":            "O2(L)",
    "O2L":            "O2(L)",

    # Liquid hydrogen
    "LH2":            "H2(L)",
    "LH2L":           "H2(L)",

    # RP-1 variants
    "RP1":            "RP-1",
    "KEROSENE":       "RP-1",
    "RP-1(L)":        "RP-1",

    # NTO / N2O4
    "NTO":            "N2O4(L)",
    "N2O4":           "N2O4(L)",

    # MMH
    "MONOMETHYLHYDRAZINE": "MMH",

    # UDMH
    "UDMH":           "C2H8N2(L),UDMH",
    "C2H8N2":         "C2H8N2(L),UDMH",

    # Hydrazine
    "N2H4":           "N2H4(L)",
    "HYDRAZINE":      "N2H4(L)",

    # Methane
    "LCH4":           "CH4(L)",
    "LNG":            "CH4(L)",
    "METHANE":        "CH4",

    # Ethanol
    "ETHANOL":        "C2H5OH(L)",
    "C2H5OH":         "C2H5OH(L)",

    # Hydrogen peroxide
    "H2O2":           "H2O2(L)",
    "HTP":            "H2O2(L)",

    # Nitric acid
    "RFNA":           "HNO3(L)",
    "WFNA":           "HNO3(L)",
    "HNO3":           "HNO3(L)",

    # Fluorine
    "LF2":            "F2(L)",

    # Nitrogen tetroxide gas
    "N2O4G":          "N2O4",

    # Air
    "AIR":            "Air",

    # Aluminum powder
    "AL":             "Al(cr)",
    "ALUMINUM":       "Al(cr)",
    "ALU":            "Al(cr)",

    # Magnesium
    "MG":             "Mg(cr)",

    # Boron
    "B":              "B(b)",

    # Carbon (graphite)
    "CGRAPHITE":      "C(gr)",
    "C_GRAPHITE":     "C(gr)",

    # HTPB variants
    "HTPB":           "HTPB",

    # JP fuels
    "JP4":            "JP-4",
    "JP5":            "JP-5",
    "JP8":            "Jet-A(L)",
    "JETA":           "Jet-A(L)",

    # Liquid nitrogen
    "LN2":            "N2(L)",

    # Nitrous oxide
    "N2O":            "N2O",

    # Oxygen (gas)
    "O2":             "O2",
    "GOX":            "O2",

    # Hydrogen (gas)
    "H2":             "H2",
    "GH2":            "H2",

    # Methanol
    "METHANOL":       "CH3OH(L)",
    "CH3OH":          "CH3OH(L)",

    # Propane
    "PROPANE":        "C3H8(L)",
    "C3H8":           "C3H8(L)",

    # IPA / isopropanol
    "IPA":            "C3H8O,2propanol",

    # IRFNA
    "IRFNA":          "IRFNA",

    # ClF3
    "CLF3":           "ClF3(L)",
    "CHLORINE_TRIFLUORIDE": "ClF3(L)",
}

# Pattern for stripping whitespace/underscores and uppercasing
_STRIP_RE = re.compile(r"[\s_\-]+")


def normalize(name: str) -> str:
    """
    Return the canonical CEA species name for `name`.
    Steps:
      1. Strip surrounding whitespace
      2. Try direct lookup (case-insensitive) in ALIAS_MAP
      3. Try stripping punctuation variants
      4. Return original if no match found (pass-through)
    """
    if not name:
        return name
    stripped = name.strip()

    # Direct case-insensitive lookup
    key = stripped.upper()
    if key in ALIAS_MAP:
        return ALIAS_MAP[key]

    # Try without inner spaces/hyphens
    simplified = _STRIP_RE.sub("", stripped).upper()
    if simplified in ALIAS_MAP:
        return ALIAS_MAP[simplified]

    # Return original unchanged
    return stripped


def normalize_formulation(formulation: dict) -> dict:
    """
    Normalize oxidizer_name and fuel_name in a formulation dict in-place.
    Returns the same dict (mutated).
    """
    import copy
    f = copy.deepcopy(formulation)
    if f.get("oxidizer_name"):
        f["oxidizer_name"] = normalize(f["oxidizer_name"])
    if f.get("fuel_name"):
        f["fuel_name"] = normalize(f["fuel_name"])
    for add in f.get("additives", []):
        if add.get("name"):
            add["name"] = normalize(add["name"])
    return f
