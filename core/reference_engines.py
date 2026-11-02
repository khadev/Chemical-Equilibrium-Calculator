"""
core/reference_engines.py
============================
Published literature reference values for well-known historical
rocket engines, used by the Research Report's Dashboard and
Validation sheets to sanity-check a calculated result against a real,
fully public/declassified engine of the same propellant class.

Deliberately keyed to the exact same propellant pairs offered as
presets in the Welcome tab (see ``config/presets.json``), so picking
"LOX / RP-1 (Saturn V F1)" there and then exporting a Research Report
compares against the Saturn V F1's own published numbers — not a
mismatched reference.

These are comparison constants, not authoritative claims by this
application — edit :data:`REFERENCE_ENGINES` directly if your source
of record differs (e.g. a specific textbook or NASA report edition
that quotes slightly different figures).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ReferenceEngine:
    """Published performance figures for one historical reference engine."""

    label: str
    source: str
    isp_s: float
    isp_m_s: float
    t_chamber_k: float
    p_chamber_bar: float
    p_exit_bar: float
    cf: float
    stoich_of_ratio: Optional[float] = None  # for equivalence-ratio calc


REFERENCE_ENGINES: Dict[str, ReferenceEngine] = {
    "lox_rp1": ReferenceEngine(
        label="Saturn V F-1", source="Saturn V F1 Spec",
        isp_s=370.0, isp_m_s=3630.0, t_chamber_k=3590.0,
        p_chamber_bar=70.0, p_exit_bar=0.48, cf=1.80,
        stoich_of_ratio=2.56),
    "lox_lh2": ReferenceEngine(
        label="SSME (RS-25)", source="NASA SSME Spec",
        isp_s=452.3, isp_m_s=4436.0, t_chamber_k=3588.0,
        p_chamber_bar=204.0, p_exit_bar=0.21, cf=1.92,
        stoich_of_ratio=8.0),
    "lox_ch4": ReferenceEngine(
        label="Raptor-class", source="Published Raptor-class Spec",
        isp_s=327.0, isp_m_s=3207.0, t_chamber_k=3500.0,
        p_chamber_bar=300.0, p_exit_bar=0.5, cf=1.85,
        stoich_of_ratio=4.0),
    "n2o4_mmh": ReferenceEngine(
        label="Titan/Apollo-class hypergolic", source="Apollo SPS Spec",
        isp_s=312.0, isp_m_s=3059.0, t_chamber_k=3070.0,
        p_chamber_bar=10.0, p_exit_bar=0.05, cf=1.75,
        stoich_of_ratio=1.92),
    "solid": ReferenceEngine(
        label="Shuttle SRB-class", source="Published SRB Spec",
        isp_s=269.0, isp_m_s=2638.0, t_chamber_k=3500.0,
        p_chamber_bar=60.0, p_exit_bar=0.9, cf=1.81,
        stoich_of_ratio=None),
    "default": ReferenceEngine(
        label="Generic ideal-rocket reference", source="Ideal Rocket",
        isp_s=300.0, isp_m_s=2942.0, t_chamber_k=3200.0,
        p_chamber_bar=50.0, p_exit_bar=1.0, cf=1.5,
        stoich_of_ratio=None),
}


def match_reference_engine(oxidizer_name: str, fuel_name: str) -> ReferenceEngine:
    """
    Pick the most relevant reference engine for a propellant pair.

    Uses the same simple name-matching heuristic as
    :class:`core.fallback_calculator.FallbackCalculator`, so the same
    formulation always maps to the same reference engine throughout
    the application.

    Args:
        oxidizer_name: Oxidizer species name.
        fuel_name: Fuel species name.

    Returns:
        The matching :class:`ReferenceEngine`, or the generic
        "default" entry if nothing matches.
    """
    oxidizer = (oxidizer_name or "").lower()
    fuel = (fuel_name or "").lower()
    if "nh4" in oxidizer or "clo4" in oxidizer:
        return REFERENCE_ENGINES["solid"]
    if "o2" in oxidizer and "h2" in fuel:
        return REFERENCE_ENGINES["lox_lh2"]
    if "o2" in oxidizer and "ch4" in fuel:
        return REFERENCE_ENGINES["lox_ch4"]
    if "o2" in oxidizer and ("rp" in fuel or "kero" in fuel):
        return REFERENCE_ENGINES["lox_rp1"]
    if "n2o4" in oxidizer and "mmh" in fuel:
        return REFERENCE_ENGINES["n2o4_mmh"]
    return REFERENCE_ENGINES["default"]
