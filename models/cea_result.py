"""
models/cea_result.py
======================
``CEAResult`` dataclass — holds the parsed output of a CEA run
(real FCEA2.exe output or the ideal-rocket fallback calculation).
Pure data — no parsing logic, no UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

G0: float = 9.80665  # Standard gravity, m/s²


@dataclass
class CEAResult:
    """
    Result of a single CEA (or fallback) propulsion calculation.

    All numeric fields default to 0.0 / empty so an unsuccessful run
    can still be safely displayed without raising ``AttributeError``.
    """

    name: str = ""
    method: str = "Fallback"
    success: bool = False
    error_message: str = ""

    # Performance - VACUUM values at specified Ae/At (second column)
    isp_vacuum_s: float = 0.0       # Isp vacuum at specified Ae/At
    ivac_m_s: float = 0.0           # Ivac vacuum at specified Ae/At
    cstar_m_s: float = 0.0
    cf_vacuum: float = 0.0          # CF vacuum at specified Ae/At
    area_ratio: float = 0.0

    # Performance - SEA LEVEL values (first column, for reference only - not displayed)
    isp_sea_level_s: float = 0.0
    ivac_sea_level_m_s: float = 0.0
    cf_sea_level: float = 0.0

    # Frozen flow (optional)
    isp_frozen_s: float = 0.0

    # Thermodynamic
    t_chamber_k: float = 0.0
    t_throat_k: float = 0.0
    t_exit_k: float = 0.0
    p_chamber_bar: float = 0.0
    p_throat_bar: float = 0.0
    p_exit_bar: float = 0.0
    mach_exit: float = 0.0
    gamma: float = 0.0
    molecular_weight: float = 0.0
    cp_kj_kgk: float = 0.0
    prandtl: float = 0.0

    # Species mass fractions — values guaranteed to be finite floats
    mass_fractions: Dict[str, float] = field(default_factory=dict)

    # Raw text (for the "Raw CEA Output" view)
    raw_inp: str = ""
    raw_output: str = ""

    # ── Derived properties ────────────────────────────────────────────
    @property
    def isp_m_s(self) -> float:
        """Isp in m/s at specified Ae/At (vacuum value, second column)."""
        return self.isp_vacuum_s * G0

    @property
    def isp_s(self) -> float:
        """Isp in seconds at specified Ae/At (vacuum value, second column)."""
        return self.isp_vacuum_s

    @property
    def ivac_s(self) -> float:
        """Ivac in seconds at specified Ae/At (vacuum value, second column)."""
        return self.ivac_m_s / G0 if self.ivac_m_s > 0 else 0.0

    @property
    def isp_frozen_m_s(self) -> float:
        """Frozen specific impulse in m/s."""
        return self.isp_frozen_s * G0

    @property
    def delta_isp_m_s(self) -> float:
        """ΔIsp = Isp(equilibrium) − Isp(frozen), in m/s."""
        if self.isp_frozen_s <= 0:
            return 0.0
        return (self.isp_vacuum_s - self.isp_frozen_s) * G0

    @property
    def kinetic_loss_pct(self) -> float:
        """Kinetic loss percentage relative to equilibrium Isp."""
        if self.isp_vacuum_s <= 0 or self.isp_frozen_s <= 0:
            return 0.0
        return self.delta_isp_m_s / (self.isp_vacuum_s * G0) * 100.0

    @property
    def loss_color(self) -> str:
        """Traffic-light color for the kinetic loss percentage."""
        loss = self.kinetic_loss_pct
        if loss <= 0:
            return "#9E9E9E"
        if loss < 3:
            return "#388E3C"
        if loss < 8:
            return "#E65100"
        return "#C62828"

    # ── Table formatting ──────────────────────────────────────────────
    def to_table_rows(self, units: Dict[str, str]) -> List[Tuple]:
        """
        Build a list of formatted (parameter, value, unit, description)
        rows suitable for direct display in a results table.
        """
        pressure_unit = units.get("pressure", "bar")
        temperature_unit = units.get("temperature", "K")
        pressure_factor = {
            "bar": 1.0, "psi": 14.5038, "MPa": 0.1
        }.get(pressure_unit, 1.0)

        def conv_t(value: float) -> float:
            return value - 273.15 if temperature_unit == "°C" else value

        rows: List[Tuple] = [
            # Ae/At - shows the actual area ratio used
            ("Ae/At", f"{self.area_ratio:.2f}" if self.area_ratio else "—",
             "—", "Nozzle expansion ratio"),
        ]
        
        # ===== ISP (Vacuum at specified Ae/At, second column) =====
        if self.isp_m_s > 0:
            rows.append(("Isp", f"{self.isp_m_s:.1f}", "m/s", 
                        f"At Ae/At = {self.area_ratio:.2f}"))
            rows.append(("Isp", f"{self.isp_s:.2f}", "s",
                        f"At Ae/At = {self.area_ratio:.2f}"))
        
        # ===== IVAC (Vacuum at specified Ae/At, second column) =====
        if self.ivac_m_s > 0:
            rows.append(("Ivac", f"{self.ivac_m_s:.1f}", "m/s", 
                        f"At Ae/At = {self.area_ratio:.2f}"))
            rows.append(("Ivac", f"{self.ivac_s:.2f}", "s",
                        f"At Ae/At = {self.area_ratio:.2f}"))
        
        # ===== C* =====
        if self.cstar_m_s > 0:
            rows.append(("C*", f"{self.cstar_m_s:.1f}", "m/s",
                        "Characteristic velocity"))
        
        # ===== CF Vacuum (at specified Ae/At) =====
        if self.cf_vacuum > 0:
            rows.append(("Cf", f"{self.cf_vacuum:.4f}", "—",
                        f"Thrust coefficient at Ae/At = {self.area_ratio:.2f}"))
        
        # ===== Thermodynamic properties =====
        if self.t_chamber_k > 0:
            rows.extend([
                ("Tc", f"{conv_t(self.t_chamber_k):.1f}", temperature_unit,
                 "Chamber temperature"),
                ("Tt", f"{conv_t(self.t_throat_k):.1f}", temperature_unit,
                 "Throat temperature"),
                ("Te", f"{conv_t(self.t_exit_k):.1f}", temperature_unit,
                 "Exit temperature"),
            ])
        
        if self.p_chamber_bar > 0:
            rows.extend([
                ("Pc", f"{self.p_chamber_bar * pressure_factor:.2f}",
                 pressure_unit, "Chamber pressure"),
                ("Pe", f"{self.p_exit_bar * pressure_factor:.4f}",
                 pressure_unit, "Exit pressure"),
            ])
        
        if self.molecular_weight > 0:
            rows.append(("MW", f"{self.molecular_weight:.3f}", "g/mol",
                        "Mean molecular weight at exit"))
        
        if self.gamma > 0:
            rows.append(("γ", f"{self.gamma:.4f}", "—", 
                        "Ratio of specific heats"))
        
        if self.mach_exit > 0:
            rows.append(("Mach exit", f"{self.mach_exit:.3f}", "—",
                        "Exit Mach number"))
        
        # ===== Frozen flow info (if available) =====
        if self.isp_frozen_s > 0:
            rows += [
                ("Isp frozen", f"{self.isp_frozen_s:.2f}", "s",
                 "Frozen-flow Isp"),
                ("ΔIsp", f"{self.delta_isp_m_s:.1f}", "m/s",
                 "ΔIsp = Isp(EQ) − Isp(FZ)"),
                ("Loss %", f"{self.kinetic_loss_pct:.2f}", "%",
                 "Kinetic loss", self.loss_color),
            ]
        return rows
