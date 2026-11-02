"""
core/molecular_weights.py
============================
Molecular weight lookup for combustion-product species, used to
convert mass fractions to mole fractions in the Exit Composition
report.

A curated table covers every species that appears in this app's own
representative-composition tables plus the common combustion products
real FCEA2 output typically reports. A best-effort formula parser
handles anything not in that table — it reads the leading element/
count pairs from the species name (the standard CEA naming
convention, e.g. ``"Al2O3(a)"`` → Al:2, O:3) and falls back to
``None`` (never a fabricated number) if the name doesn't parse
cleanly, since a wrong molecular weight is worse than a visibly
missing one.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

# Standard atomic weights (g/mol) for elements that appear in common
# propellant combustion products.
_ATOMIC_WEIGHTS: Dict[str, float] = {
    "H": 1.008, "He": 4.003, "Li": 6.94, "C": 12.011, "N": 14.007,
    "O": 15.999, "F": 18.998, "Na": 22.990, "Al": 26.982, "Si": 28.085,
    "P": 30.974, "S": 32.06, "Cl": 35.45, "K": 39.098, "Ca": 40.078,
    "Ti": 47.867, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845, "Ni": 58.693,
    "Cu": 63.546, "Zn": 65.38, "Br": 79.904, "Zr": 91.224, "I": 126.904,
    "Be": 9.012, "B": 10.811, "Mg": 24.305,
}

# Curated, exact molecular weights for species this app commonly
# produces (its own representative tables, plus standard real-CEA
# combustion product names) — preferred over the generic parser below
# since several CEA names don't parse cleanly with a simple regex
# (ions, electrons, multi-part organic names).
_CURATED_MW: Dict[str, float] = {
    "H2O": 18.015, "CO2": 44.010, "CO": 28.010, "H2": 2.016,
    "N2": 28.013, "O2": 31.998, "OH": 17.007, "H": 1.008, "O": 15.999,
    "NO": 30.006, "NO2": 46.005, "HCl": 36.461, "Cl2": 70.906,
    "HF": 20.006, "Al2O3(a)": 101.961, "Al2O3(L)": 101.961,
    "Al2O3": 101.961, "AlCl3": 133.341, "AlO": 42.981, "HCN": 27.026,
    "CH4": 16.043, "NH3": 17.031, "N2O": 44.013, "SO2": 64.066,
    "C(gr)": 12.011, "Cl": 35.453, "N": 14.007, "F": 18.998,
    "e-": 0.000549,
}


def molecular_weight(species_name: str) -> Optional[float]:
    """
    Look up the molecular weight (g/mol) of a species by its CEA name.

    Args:
        species_name: Species name as it appears in
            :attr:`CEAResult.mass_fractions` (e.g. ``"CO2"``,
            ``"Al2O3(a)"``).

    Returns:
        Molecular weight in g/mol, or ``None`` if it cannot be
        determined reliably (never a guessed/fabricated value).
    """
    if species_name in _CURATED_MW:
        return _CURATED_MW[species_name]

    # Strip any trailing phase/condition annotation, e.g. "(a)", "(L)",
    # and anything after a comma (CEA's "name,note" convention).
    core_name = species_name.split(",")[0]
    core_name = re.sub(r"\([^)]*\)$", "", core_name).strip()
    # Strip a leading/trailing ionic charge marker.
    core_name = core_name.rstrip("+-")

    if core_name in _CURATED_MW:
        return _CURATED_MW[core_name]

    total = 0.0
    matched_any = False
    for element, count_str in re.findall(r"([A-Z][a-z]?)(\d*)", core_name):
        if not element:
            continue
        if element not in _ATOMIC_WEIGHTS:
            return None  # Unknown element — don't guess.
        count = int(count_str) if count_str else 1
        total += _ATOMIC_WEIGHTS[element] * count
        matched_any = True

    return round(total, 3) if matched_any and total > 0 else None
