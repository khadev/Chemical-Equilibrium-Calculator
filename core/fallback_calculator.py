
"""
core/fallback_calculator.py
=============================
Ideal-rocket-equation calculator used when FCEA2.exe is not configured
or unavailable.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

from models.cea_result import CEAResult, G0
from models.formulation import Formulation


class IsentropicFlow:
    """Static collection of correct isentropic-flow relations."""

    @staticmethod
    def area_ratio_from_mach(mach: float, gamma: float) -> float:
        term = (2.0 / (gamma + 1.0)) * (1.0 + (gamma - 1.0) / 2.0 * mach ** 2)
        return (1.0 / mach) * term ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))

    @staticmethod
    def mach_from_area_ratio(
            area_ratio: float, gamma: float, supersonic: bool = True
    ) -> float:
        if area_ratio <= 1.0:
            return 1.0
        mach = 3.0 if supersonic else 0.3
        for _ in range(80):
            current_ratio = IsentropicFlow.area_ratio_from_mach(mach, gamma)
            t = (2.0 / (gamma + 1.0)) * (1.0 + (gamma - 1.0) / 2.0 * mach ** 2)
            d_ratio = (
                -current_ratio / mach
                + (1.0 / mach) * (gamma + 1.0) / (2.0 * (gamma - 1.0))
                * t ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)) - 1.0)
                * (2.0 / (gamma + 1.0)) * (gamma - 1.0) * mach
            )
            delta = (area_ratio - current_ratio) / (d_ratio + 1e-15)
            mach += delta
            if abs(delta) < 1e-10:
                break
        return max(mach, 1.001 if supersonic else 0.01)

    @staticmethod
    def temperature_ratio(mach: float, gamma: float) -> float:
        return 1.0 / (1.0 + (gamma - 1.0) / 2.0 * mach ** 2)

    @staticmethod
    def pressure_ratio(mach: float, gamma: float) -> float:
        return IsentropicFlow.temperature_ratio(mach, gamma) ** (gamma / (gamma - 1.0))

    @staticmethod
    def thrust_coefficient(gamma: float, exit_to_chamber_pressure: float, area_ratio: float) -> float:
        try:
            return (
                math.sqrt(
                    2.0 * gamma ** 2 / (gamma - 1.0)
                    * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (gamma - 1.0))
                    * (1.0 - exit_to_chamber_pressure ** ((gamma - 1.0) / gamma))
                )
                + exit_to_chamber_pressure * area_ratio
            )
        except (ValueError, ZeroDivisionError):
            return 1.5

    # =====================================================================
    # 👇 RESTORED METHOD: nozzle_profile (required for Nozzle Designer) 👇
    # =====================================================================
    @staticmethod
    def nozzle_profile(
            area_ratio: float, gamma: float, n_points: int = 120
    ) -> Tuple[list, list, list]:
        """
        Generate normalized nozzle geometry from throat to exit.
        
        Returns:
            Tuple of (x_normalized, area_ratio_values, mach_values).
        """
        mach_exit = IsentropicFlow.mach_from_area_ratio(area_ratio, gamma)
        mach_values = [
            1.0 + (mach_exit - 1.0) * i / (n_points - 1)
            for i in range(n_points)
        ]
        area_ratios = [
            IsentropicFlow.area_ratio_from_mach(m, gamma) for m in mach_values
        ]
        radii = [math.sqrt(ar) for ar in area_ratios]
        x_values = [0.0]
        for i in range(1, n_points):
            dx = math.sqrt(1.0 + (radii[i] - radii[i - 1]) ** 2)
            x_values.append(x_values[-1] + dx)
        x_max = x_values[-1] or 1.0
        x_normalized = [x / x_max for x in x_values]
        return x_normalized, area_ratios, mach_values


class FallbackCalculator:
    """
    Computes approximate performance using ideal rocket equations.
    """

    _PROPELLANT_PROPERTIES: Dict[str, Dict[str, float]] = {
        "polysaccharide": {
            "t_chamber_peak": 3403.6,
            "gamma": 1.134,
            "mw": 25.758,
            "cstar_peak": 1583.4,
            "peak_of": 2.125,
        },
        "solid": {
            "t_chamber_peak": 3300.0,
            "gamma": 1.21,
            "mw": 27.0,
            "cstar_peak": 1580.0,
            "peak_of": 4.0,
        },
        "lox_rp1": {
            "t_chamber_peak": 3600.0,
            "gamma": 1.20,
            "mw": 23.0,
            "cstar_peak": 1800.0,
            "peak_of": 2.56,
        },
        "lox_lh2": {
            "t_chamber_peak": 3250.0,
            "gamma": 1.26,
            "mw": 10.0,
            "cstar_peak": 2350.0,
            "peak_of": 4.5,
        },
        "n2o4_mmh": {
            "t_chamber_peak": 3100.0,
            "gamma": 1.24,
            "mw": 21.5,
            "cstar_peak": 1680.0,
            "peak_of": 1.65,
        },
        "lox_ch4": {
            "t_chamber_peak": 3400.0,
            "gamma": 1.23,
            "mw": 18.5,
            "cstar_peak": 1900.0,
            "peak_of": 3.6,
        },
        "default": {
            "t_chamber_peak": 3200.0,
            "gamma": 1.22,
            "mw": 22.0,
            "cstar_peak": 1750.0,
            "peak_of": 2.5,
        },
    }

    _EXIT_COMPOSITION: Dict[str, Dict[str, float]] = {
        "polysaccharide": {
            "Al2O3(L)": 0.30741,
            "Al2O3(a)": 0.33997,
            "CO": 0.26459,
            "HCL": 0.20981,
            "N2": 0.08230,
            "H2O": 0.05626,
            "H2": 0.02615,
            "CO2": 0.01950,
            "CL": 0.00103,
            "OH": 0.00005,
        },
        "solid": {
            "Al2O3(a)": 0.32,
            "HCl": 0.21,
            "CO": 0.20,
            "N2": 0.08,
            "H2": 0.08,
            "H2O": 0.06,
            "CO2": 0.05,
        },
        "lox_rp1": {
            "CO": 0.32,
            "CO2": 0.18,
            "H2O": 0.18,
            "H2": 0.12,
            "OH": 0.08,
            "H": 0.06,
            "O": 0.04,
            "O2": 0.02,
        },
        "lox_lh2": {
            "H2O": 0.62,
            "H2": 0.24,
            "OH": 0.06,
            "O": 0.03,
            "H": 0.03,
            "O2": 0.02,
        },
        "n2o4_mmh": {
            "H2O": 0.27,
            "CO2": 0.22,
            "CO": 0.21,
            "N2": 0.17,
            "H2": 0.07,
            "OH": 0.03,
            "NO": 0.02,
            "H": 0.01,
        },
        "lox_ch4": {
            "H2O": 0.35,
            "CO": 0.25,
            "CO2": 0.18,
            "H2": 0.12,
            "OH": 0.06,
            "O": 0.02,
            "H": 0.02,
        },
        "default": {
            "CO2": 0.30,
            "H2O": 0.25,
            "CO": 0.20,
            "N2": 0.15,
            "H2": 0.10,
        },
    }

    def _match_propellant(self, formulation: Formulation) -> str:
        oxidizer = formulation.oxidizer_name.lower()
        fuel = formulation.fuel_name.lower()
        binder_names = [r.get("name", "").lower() for r in formulation.user_reactants]
        
        if "nc" in binder_names or "ncs" in binder_names:
            if "nh4" in oxidizer or "clo4" in oxidizer:
                return "polysaccharide"
        
        if "nh4" in oxidizer or "clo4" in oxidizer:
            if "al" in fuel or "htpb" in binder_names:
                return "polysaccharide"
            return "solid"
        
        if "o2" in oxidizer and "h2" in fuel:
            return "lox_lh2"
        if "o2" in oxidizer and "ch4" in fuel:
            return "lox_ch4"
        if "o2" in oxidizer and ("rp" in fuel or "kero" in fuel):
            return "lox_rp1"
        if "n2o4" in oxidizer and "mmh" in fuel:
            return "n2o4_mmh"
        
        return "default"

    def calculate(self, formulation: Formulation) -> CEAResult:
        result = CEAResult(name=formulation.name, method="Fallback (Ideal Rocket)")
        
        result.area_ratio = formulation.area_ratio
        result.p_chamber_bar = formulation.chamber_pressure_bar

        key = self._match_propellant(formulation)
        props = self._PROPELLANT_PROPERTIES.get(key, self._PROPELLANT_PROPERTIES["default"])
        
        t_chamber_peak = props["t_chamber_peak"]
        gamma = props["gamma"]
        mw = props["mw"]
        cstar_peak = props["cstar_peak"]
        peak_of = props["peak_of"]

        of_actual = max(formulation.of_ratio, 0.01)
        deviation = (of_actual - peak_of) / peak_of
        mixture_efficiency = max(0.80, 1.0 - 0.35 * deviation ** 2)
        
        pressure_efficiency = 1.0 + 0.005 * math.log(max(formulation.chamber_pressure_bar / 50.0, 0.1))
        pressure_efficiency = max(0.95, min(pressure_efficiency, 1.05))
        
        cstar = cstar_peak * mixture_efficiency * pressure_efficiency
        t_chamber = t_chamber_peak * (0.5 + 0.5 * mixture_efficiency)
        
        result.t_chamber_k = t_chamber
        result.gamma = gamma
        result.molecular_weight = mw
        result.cstar_m_s = cstar

        result.t_throat_k = t_chamber * 2.0 / (gamma + 1.0)
        result.p_throat_bar = result.p_chamber_bar * (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))

        mach_exit = IsentropicFlow.mach_from_area_ratio(result.area_ratio, gamma)
        result.mach_exit = mach_exit
        
        result.t_exit_k = t_chamber * IsentropicFlow.temperature_ratio(mach_exit, gamma)
        result.p_exit_bar = result.p_chamber_bar * IsentropicFlow.pressure_ratio(mach_exit, gamma)

        pe_pc = result.p_exit_bar / max(result.p_chamber_bar, 1e-9)
        result.cf_vacuum = IsentropicFlow.thrust_coefficient(gamma, pe_pc, result.area_ratio)
        result.cf_sea_level = result.cf_vacuum + (1.0 / result.p_chamber_bar) * result.area_ratio
        
        # Set Isp values (vacuum at specified Ae/At)
        result.isp_vacuum_s = cstar * result.cf_vacuum / G0
        result.isp_sea_level_s = cstar * result.cf_sea_level / G0
        result.ivac_m_s = result.isp_vacuum_s * G0
        result.ivac_sea_level_m_s = result.isp_sea_level_s * G0
        
        result.mass_fractions = dict(self._EXIT_COMPOSITION.get(key, {}))
        result.success = True
        
        result.raw_output = (
            f"[Fallback Calculator — Ideal Rocket Equations]\n"
            f"Propellant match key: {key}\n"
            f"Peak-Isp reference O/F: {peak_of:.2f}\n"
            f"Actual O/F: {of_actual:.2f}\n"
            f"Mixture efficiency: {mixture_efficiency * 100:.1f}%\n"
            f"Chamber pressure: {formulation.chamber_pressure_bar:.1f} bar\n"
            f"Area ratio: {formulation.area_ratio:.2f}\n"
            f"Exit Mach: {mach_exit:.3f}\n"
            f"Configure FCEA2.exe in Settings for exact CEA results.\n")
        
        return result
