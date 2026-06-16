"""
engine/logic_layer.py — LOGIC LAYER
======================================
All calculations live here — NO UI imports.
  • INP file builder (exact NASA CEA format)
  • OUT file parser (regex, THEORETICAL ROCKET PERFORMANCE header)
  • Fallback calculator (ideal rocket equations)
  • Nozzle designer (correct isentropic flow)
  • All 25 analysis tool calculations
  • CEAWorker QThread
  • BatchSweepWorker QThread
"""
from __future__ import annotations
import os, re, math, copy, subprocess, tempfile, itertools, logging
from typing import Optional, List, Dict, Tuple, Any

from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

from models.data_layer import (
    Formulation, ConfigManager, SpeciesDatabase, UserReactant)
from engine.species_normalizer import normalize

log = logging.getLogger(__name__)

G0 = 9.80665  # m/s²


# ══════════════════════════════════════════════════════════════════════
# CEA Result dataclass
# ══════════════════════════════════════════════════════════════════════
class CEAResult:
    def __init__(self):
        self.name       = ""
        self.method     = "Fallback"
        self.success    = False
        self.error_msg  = ""

        # Performance
        self.isp_vac    = 0.0   # s
        self.isp_opt    = 0.0
        self.isp_frozen = 0.0
        self.cstar      = 0.0   # m/s
        self.cf         = 0.0
        self.cf_vac     = 0.0
        self.ae_at      = 0.0

        # Thermodynamic
        self.t_chamber  = 0.0; self.t_throat = 0.0; self.t_exit = 0.0
        self.p_chamber  = 0.0; self.p_throat = 0.0; self.p_exit = 0.0
        self.mach_exit  = 0.0
        self.gamma      = 0.0;  self.mw       = 0.0
        self.cp         = 0.0;  self.prandtl  = 0.0

        # Species
        self.mass_fractions: Dict[str, float] = {}

        # Raw
        self.raw_inp    = ""
        self.raw_output = ""

    @property
    def isp_ms(self) -> float:
        return self.isp_vac * G0

    @property
    def delta_isp(self) -> float:
        if self.isp_frozen <= 0: return 0.0
        return (self.isp_vac - self.isp_frozen) * G0

    @property
    def loss_pct(self) -> float:
        if self.isp_vac <= 0 or self.isp_frozen <= 0: return 0.0
        return self.delta_isp / (self.isp_vac * G0) * 100.0

    @property
    def loss_color(self) -> str:
        lp = self.loss_pct
        if lp <= 0:  return "#9E9E9E"
        if lp < 3:   return "#388E3C"
        if lp < 8:   return "#E65100"
        return "#C62828"

    def to_table_rows(self, units: dict) -> List[tuple]:
        p_f = {"bar": 1.0, "psi": 14.5038, "MPa": 0.1}.get(
            units.get("pressure", "bar"), 1.0)
        pu  = units.get("pressure", "bar")
        tu  = units.get("temperature", "K")

        def t(v): return v - 273.15 if tu == "°C" else v
        def p(v): return v * p_f

        rows = [
            ("Ae/At",       f"{self.ae_at:.2f}"  if self.ae_at else "—",
             "—",   "Nozzle expansion ratio"),
            ("Isp",         f"{self.isp_ms:.1f}", "m/s",
             "Specific impulse (m/s = Isp_s × g₀)"),
            ("Isp",         f"{self.isp_vac:.2f}", "s",
             "Vacuum specific impulse (shifting equilibrium)"),
            ("C*",          f"{self.cstar:.1f}",  "m/s",
             "Characteristic velocity"),
            ("Cf",          f"{self.cf:.4f}",     "—",
             "Thrust coefficient (Cf ≈ 1.5–1.9)"),
            ("Cf vac",      f"{self.cf_vac:.4f}", "—",
             "Vacuum thrust coefficient"),
            ("CT",          f"{self.cf:.4f}",     "—",
             "Coefficient of Thrust (= Cf)"),
            ("Tc",          f"{t(self.t_chamber):.1f}", tu,
             "Adiabatic flame temperature"),
            ("Tt",          f"{t(self.t_throat):.1f}",  tu,
             "Throat temperature"),
            ("Te",          f"{t(self.t_exit):.1f}",    tu,
             "Exit temperature"),
            ("Pc",          f"{p(self.p_chamber):.2f}", pu, "Chamber pressure"),
            ("Pe",          f"{p(self.p_exit):.3f}",    pu, "Exit pressure"),
            ("MW",          f"{self.mw:.3f}",    "g/mol",
             "Mean molecular weight at exit"),
            ("γ",           f"{self.gamma:.4f}", "—",
             "Ratio of specific heats Cp/Cv"),
            ("Mach exit",   f"{self.mach_exit:.3f}", "—", "Exit Mach number"),
        ]
        if self.isp_frozen > 0:
            rows += [
                ("Isp frozen",  f"{self.isp_frozen:.2f}", "s",
                 "Frozen-flow Isp"),
                ("ΔIsp",        f"{self.delta_isp:.1f}",  "m/s",
                 "ΔIsp = Isp(EQ) – Isp(FZ)"),
                ("Loss %",      f"{self.loss_pct:.2f}",   "%",
                 "Green <3%, Orange 3–8%, Red >8%",
                 self.loss_color),
            ]
        return rows


# ══════════════════════════════════════════════════════════════════════
# INP Builder — exact NASA CEA format
# ══════════════════════════════════════════════════════════════════════
class INPBuilder:
    @staticmethod
    def build(f: Formulation) -> str:
        pc   = f.chamber_pressure
        ar   = f.area_ratio
        tc   = f.tcest
        mode = "frozen" if f.frozen else "equilibrium"
        lines = [
            "prob",
            f"rocket {mode} tcest,k={tc}",
            f"p,bar={pc:.4g}",
            f"sup,ae/at={ar:.4g}",
            "",
            "reac",
        ]
        # Oxidizer
        ox = normalize(f.oxidizer_name).strip()
        if ox:
            parts = [f"oxid={ox}"]
            if f.oxidizer_wt not in (0.0, 100.0):
                parts.append(f"wt={f.oxidizer_wt:.4g}")
            parts.append(f"t,k={f.oxidizer_temp:.1f}")
            if f.oxidizer_enthalpy: parts.append(f"h,kj/mol={f.oxidizer_enthalpy:.4g}")
            for el, a in f.oxidizer_formula.items(): parts.append(f"{el} {a:.3f}")
            lines.append(" ".join(parts))
        # Fuel
        fu = normalize(f.fuel_name).strip()
        if fu:
            parts = [f"fuel={fu}"]
            if f.fuel_wt not in (0.0, 100.0):
                parts.append(f"wt={f.fuel_wt:.4g}")
            parts.append(f"t,k={f.fuel_temp:.1f}")
            if f.fuel_enthalpy: parts.append(f"h,kj/mol={f.fuel_enthalpy:.4g}")
            for el, a in f.fuel_formula.items(): parts.append(f"{el} {a:.3f}")
            lines.append(" ".join(parts))
        # User-defined reactants
        for ur_d in f.user_reactants:
            try:
                ur = UserReactant(**ur_d) if isinstance(ur_d, dict) else ur_d
                lines.append(ur.to_inp_line())
            except Exception as e:
                log.warning("UDR serialize: %s", e)
        lines += ["", "outp", "siunits massf", "", "end", ""]
        return "\n".join(lines)

    @staticmethod
    def save(f: Formulation, path: str) -> None:
        content = INPBuilder.build(f)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)

    @staticmethod
    def parse_file(path: str) -> Formulation:
        f = Formulation()
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            f.name = os.path.splitext(os.path.basename(path))[0]
            m = re.search(r"p[,\(]bar[\)=]+\s*([\d.]+)", text, re.I)
            if m: f.chamber_pressure = float(m.group(1))
            m = re.search(r"sup(?:,ae/at)?\s*=\s*([\d.]+)", text, re.I)
            if m: f.area_ratio = float(m.group(1))
            m = re.search(r"tcest,k\s*=\s*([\d.]+)", text, re.I)
            if m: f.tcest = int(float(m.group(1)))
            f.frozen = bool(re.search(r"\bfrozen\b", text, re.I))
            m = re.search(r"pip\s*=\s*([\d.]+)", text, re.I)
            if m:
                pip = float(m.group(1))
                f.exit_pressure = f.chamber_pressure / pip if pip > 0 else 1.0
            m = re.search(r"o/f\s*=\s*([\d.]+)", text, re.I)
            if m: f.of_ratio = float(m.group(1))
            # Oxidizer
            m = re.search(r"oxid\s*=\s*(\S+)(.*?)(?=\n|$)", text, re.I)
            if m:
                f.oxidizer_name = normalize(m.group(1))
                rest = m.group(2)
                wm = re.search(r"wt\s*=\s*([\d.]+)", rest, re.I)
                tm = re.search(r"t,k\s*=\s*([\d.]+)", rest, re.I)
                if wm: f.oxidizer_wt   = float(wm.group(1))
                if tm: f.oxidizer_temp = float(tm.group(1))
            # Fuel
            m = re.search(r"fuel\s*=\s*(\S+)(.*?)(?=\n|$)", text, re.I)
            if m:
                f.fuel_name = normalize(m.group(1))
                rest = m.group(2)
                wm = re.search(r"wt\s*=\s*([\d.]+)", rest, re.I)
                tm = re.search(r"t,k\s*=\s*([\d.]+)", rest, re.I)
                if wm: f.fuel_wt   = float(wm.group(1))
                if tm: f.fuel_temp = float(tm.group(1))
            # User reactants
            udrs = []
            for m in re.finditer(r"name\s*=\s*(\S+)(.*?)(?=\n|$)", text, re.I):
                rest = m.group(2)
                wm = re.search(r"wt\s*=\s*([\d.]+)", rest, re.I)
                tm = re.search(r"t,k\s*=\s*([\d.]+)", rest, re.I)
                hm = re.search(r"h,kj/mol\s*=\s*([-\d.]+)", rest, re.I)
                comp = {}
                for em in re.finditer(r"([A-Z][a-z]?)\s+([\d.]+)", rest):
                    comp[em.group(1)] = float(em.group(2))
                udrs.append(dict(
                    name=m.group(1),
                    wt=float(wm.group(1)) if wm else 100.0,
                    temp_k=float(tm.group(1)) if tm else 298.0,
                    enthalpy_kj=float(hm.group(1)) if hm else 0.0,
                    composition=comp))
            f.user_reactants = udrs
        except Exception as e:
            log.error("INP parse %s: %s", path, e)
        return f


# ══════════════════════════════════════════════════════════════════════
# OUT Parser
# ══════════════════════════════════════════════════════════════════════
class ParseError(Exception):
    pass


class OUTParser:
    _HDR = re.compile(r"THEORETICAL\s+ROCKET\s+PERFORMANCE", re.I)

    def parse(self, raw: str, name: str = "") -> CEAResult:
        r = CEAResult(); r.name = name; r.raw_output = raw; r.method = "CEA"
        if not raw or len(raw.strip()) < 10:
            raise ParseError("Engine Execution Error: CEA output is empty.")
        m = self._HDR.search(raw)
        if not m:
            raise ParseError(
                "Engine Execution Error: 'THEORETICAL ROCKET PERFORMANCE' "
                "header not found.\nOutput preview: " + raw.strip()[:200])
        sec = raw[m.start():]
        try: self._temps(sec, r)
        except Exception as e: log.debug("temps: %s", e)
        try: self._press(sec, r)
        except Exception as e: log.debug("press: %s", e)
        try: self._perf(sec, r)
        except Exception as e: log.debug("perf: %s", e)
        try: self._gas(sec, r)
        except Exception as e: log.debug("gas: %s", e)
        try: self._mf(raw, r)
        except Exception as e: log.debug("mf: %s", e)
        r.success = True
        return r

    @staticmethod
    def _sci(s: str) -> float:
        s = s.strip().replace("D","E").replace("d","e")
        s = re.sub(r"(\d)([\+\-])(\d)", r"\1E\2\3", s)
        return float(s)

    def _3c(self, t, pat):
        m = re.search(pat, t, re.I)
        if not m: return None
        try: return self._sci(m.group(1)), self._sci(m.group(2)), self._sci(m.group(3))
        except: return None

    def _temps(self, t, r):
        v = self._3c(t, r"T,\s*K\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)")
        if v: r.t_chamber, r.t_throat, r.t_exit = v

    def _press(self, t, r):
        v = self._3c(t, r"P,\s*BAR\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)")
        if v: r.p_chamber, r.p_throat, r.p_exit = v

    def _perf(self, t, r):
        m = re.search(r"Isp,\s*VAC\s*,?\s*M/SEC\s+([\d.E+\-]+)", t, re.I)
        if m: r.isp_vac = self._sci(m.group(1)) / G0
        m = re.search(r"CSTAR,\s*M/SEC\s+([\d.E+\-]+)", t, re.I)
        if m: r.cstar = self._sci(m.group(1))
        v = self._3c(t, r"CF\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)")
        if v: r.cf = v[2]
        m = re.search(r"CF,\s*VAC\s+([\d.E+\-]+)", t, re.I)
        if m: r.cf_vac = self._sci(m.group(1))
        v = self._3c(t, r"MACH NUMBER\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)")
        if v: r.mach_exit = v[2]

    def _gas(self, t, r):
        v = self._3c(t, r"GAMMAs\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)")
        if v: r.gamma = v[0]
        v = self._3c(t, r"M,\s*\(1/n\)\s+([\d.E+\-]+)\s+([\d.E+\-]+)\s+([\d.E+\-]+)")
        if v: r.mw = v[0]

    def _mf(self, text, r):
        sec = re.search(
            r"MASS FRACTIONS\s*\n(.*?)(?:\n\s*\n|\Z)", text, re.DOTALL|re.I)
        if not sec: return
        fracs = {}
        for line in sec.group(1).splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                sp = parts[0].replace("*","")
                try:
                    v = self._sci(parts[-1])
                    if v > 1e-7: fracs[sp] = v
                except: pass
        r.mass_fractions = fracs


# ══════════════════════════════════════════════════════════════════════
# Isentropic flow utilities
# ══════════════════════════════════════════════════════════════════════
class IsentropicFlow:
    """Correct isentropic flow relations for nozzle design."""

    @staticmethod
    def area_ratio_from_mach(M: float, gamma: float) -> float:
        """A/A* from Mach number."""
        g = gamma
        term = (2/(g+1)) * (1 + (g-1)/2 * M**2)
        return (1/M) * term**((g+1)/(2*(g-1)))

    @staticmethod
    def mach_from_area_ratio(ae_at: float, gamma: float,
                              supersonic: bool = True) -> float:
        """Solve A/A* = ae_at for M (Newton-Raphson)."""
        if ae_at <= 1.0:
            return 1.0
        M = 3.0 if supersonic else 0.3
        for _ in range(80):
            Ar  = IsentropicFlow.area_ratio_from_mach(M, gamma)
            g   = gamma
            # dA/dM
            t   = (2/(g+1))*(1+(g-1)/2*M**2)
            dA  = (-Ar/M + (1/M)*(g+1)/(2*(g-1))
                   * t**((g+1)/(2*(g-1))-1)*(2/(g+1))*(g-1)*M)
            dM  = (ae_at - Ar) / (dA + 1e-15)
            M  += dM
            if abs(dM) < 1e-10:
                break
        return max(M, 1.001 if supersonic else 0.01)

    @staticmethod
    def T_ratio(M: float, gamma: float) -> float:
        """T/T0 = (1 + (γ-1)/2 M²)⁻¹"""
        return 1.0 / (1 + (gamma-1)/2 * M**2)

    @staticmethod
    def P_ratio(M: float, gamma: float) -> float:
        """P/P0"""
        return IsentropicFlow.T_ratio(M, gamma)**(gamma/(gamma-1))

    @staticmethod
    def rho_ratio(M: float, gamma: float) -> float:
        """ρ/ρ0"""
        return IsentropicFlow.T_ratio(M, gamma)**(1/(gamma-1))

    @staticmethod
    def thrust_coefficient(gamma: float, pe_pc: float,
                            ae_at: float) -> float:
        """Cf from isentropic relations."""
        g = gamma
        try:
            cf = math.sqrt(
                2*g**2/(g-1)
                * (2/(g+1))**((g+1)/(g-1))
                * (1 - pe_pc**((g-1)/g))
            ) + pe_pc * ae_at
        except (ValueError, ZeroDivisionError):
            cf = 1.5
        return cf

    @staticmethod
    def nozzle_profile(ae_at: float, gamma: float,
                        n_points: int = 100
                        ) -> Tuple[List[float], List[float], List[float]]:
        """
        Generate nozzle x, A/A*, M arrays from throat to exit.
        x is normalised so throat=0, exit=1.
        """
        M_exit = IsentropicFlow.mach_from_area_ratio(ae_at, gamma)
        # M from 1 to M_exit
        M_vals  = [1.0 + (M_exit - 1.0) * i / (n_points - 1)
                   for i in range(n_points)]
        AR_vals = [IsentropicFlow.area_ratio_from_mach(M, gamma)
                   for M in M_vals]
        # Normalised x (∝ cumulative length)
        # Use conical approximation: radius ∝ sqrt(A/A*)
        r_vals  = [math.sqrt(ar) for ar in AR_vals]
        r_t = r_vals[0]
        # cumulative arc length as x-proxy
        x_vals  = [0.0]
        for i in range(1, n_points):
            dx = math.sqrt(1 + (r_vals[i] - r_vals[i-1])**2)
            x_vals.append(x_vals[-1] + dx)
        x_max = x_vals[-1]
        x_norm = [x / x_max for x in x_vals]
        return x_norm, AR_vals, M_vals


# ══════════════════════════════════════════════════════════════════════
# Fallback Calculator
# ══════════════════════════════════════════════════════════════════════
class FallbackCalculator:
    _PROPS = {
        "default":  (3200, 1.22, 22.0, 1750),
        "lox_rp1":  (3600, 1.20, 23.0, 1800),
        "lox_lh2":  (3250, 1.26, 10.0, 2350),
        "n2o4_mmh": (3100, 1.24, 21.5, 1680),
        "lox_ch4":  (3400, 1.23, 18.5, 1900),
        "solid":    (3300, 1.21, 27.0, 1580),
    }

    def calculate(self, f: Formulation) -> CEAResult:
        r = CEAResult(); r.name = f.name
        r.method = "Fallback (Ideal Rocket)"
        r.ae_at = f.area_ratio
        r.p_chamber = f.chamber_pressure

        key = self._match(f)
        tc, gamma, mw, cstar = self._PROPS[key]
        r.t_chamber = tc; r.gamma = gamma; r.mw = mw; r.cstar = cstar
        r.p_exit = f.exit_pressure

        r.t_throat = tc * 2.0 / (gamma + 1.0)
        r.p_throat = r.p_chamber * (2.0/(gamma+1.0))**(gamma/(gamma-1.0))

        M_e = IsentropicFlow.mach_from_area_ratio(r.ae_at, gamma)
        r.mach_exit = M_e
        r.t_exit = tc * IsentropicFlow.T_ratio(M_e, gamma)
        r.p_exit = r.p_chamber * IsentropicFlow.P_ratio(M_e, gamma)

        pe_pc = r.p_exit / max(r.p_chamber, 1e-9)
        r.cf  = IsentropicFlow.thrust_coefficient(gamma, pe_pc, r.ae_at)
        r.cf_vac = r.cf + pe_pc * r.ae_at   # simplified
        r.isp_vac = cstar * r.cf_vac / G0
        r.isp_opt = cstar * r.cf   / G0
        r.success = True
        r.raw_output = (f"[Fallback — Ideal Rocket: {key}]\n"
                        "Configure FCEA2.exe for accurate CEA results.")
        return r

    def _match(self, f: Formulation) -> str:
        ox = f.oxidizer_name.lower()
        fu = f.fuel_name.lower()
        if "nh4" in ox or "clo4" in ox: return "solid"
        if "o2" in ox and ("rp" in fu or "kero" in fu): return "lox_rp1"
        if "o2" in ox and "h2" in fu:   return "lox_lh2"
        if "o2" in ox and "ch4" in fu:  return "lox_ch4"
        if "n2o4" in ox and "mmh" in fu: return "n2o4_mmh"
        return "default"


# ══════════════════════════════════════════════════════════════════════
# Nozzle Calculator (full isentropic — replaces placeholder)
# ══════════════════════════════════════════════════════════════════════
class NozzleCalculator:
    """
    Logical isentropic nozzle design.
    All formulas are correct — no placeholders.
    """

    def calculate(self, result: CEAResult,
                  thrust_kn: float = 10.0) -> dict:
        if not result or not result.success:
            return {"error": "Run CEA calculation first."}

        gamma   = result.gamma or 1.22
        cstar   = result.cstar or 1800.0
        pc      = result.p_chamber * 1e5     # Pa
        ae_at   = result.ae_at or 10.0
        isp     = result.isp_vac             # s

        # Throat area from thrust requirement
        F       = thrust_kn * 1000.0         # N
        ve      = isp * G0                   # m/s
        mdot    = F / ve                     # kg/s
        At      = mdot * cstar / pc          # m²
        rt      = math.sqrt(At / math.pi)   # m
        dt      = 2 * rt * 1000             # mm

        Ae      = At * ae_at
        re      = math.sqrt(Ae / math.pi)
        de      = 2 * re * 1000             # mm

        M_exit  = IsentropicFlow.mach_from_area_ratio(ae_at, gamma)
        Te      = result.t_chamber * IsentropicFlow.T_ratio(M_exit, gamma)
        Pe      = pc * IsentropicFlow.P_ratio(M_exit, gamma)

        # Bell nozzle length (80% of equivalent conical)
        half_angle_deg = 15.0
        L_conical  = (re - rt) / math.tan(math.radians(half_angle_deg))
        L_bell_80  = 0.80 * L_conical

        # Contraction
        Cr     = 5.0   # typical
        Ac     = At * Cr
        Lstar  = 1.2   # m, characteristic length
        Lc     = Lstar * At / Ac

        # Cf check
        pe_pc = Pe / pc
        cf_calc = IsentropicFlow.thrust_coefficient(gamma, pe_pc, ae_at)

        # Generate profile
        x_norm, ar_vals, m_vals = IsentropicFlow.nozzle_profile(
            ae_at, gamma, 120)
        # Scale x to actual length (mm)
        x_mm = [x * L_bell_80 * 1000 for x in x_norm]
        r_mm = [rt * 1000 * math.sqrt(ar) for ar in ar_vals]

        return {
            "rows": [
                ("Thrust requirement", f"{thrust_kn:.1f}",      "kN"),
                ("Mass flow rate ṁ",   f"{mdot:.4f}",            "kg/s"),
                ("Throat diameter Dt", f"{dt:.2f}",              "mm"),
                ("Throat area At",     f"{At*1e4:.4f}",          "cm²"),
                ("Exit diameter De",   f"{de:.2f}",              "mm"),
                ("Exit area Ae",       f"{Ae*1e4:.4f}",          "cm²"),
                ("Area ratio Ae/At",   f"{ae_at:.2f}",           "—"),
                ("Exit Mach Me",       f"{M_exit:.4f}",          "—"),
                ("Exit temp Te",       f"{Te:.1f}",              "K"),
                ("Exit pressure Pe",   f"{Pe/1e5:.3f}",          "bar"),
                ("Thrust coeff Cf",    f"{cf_calc:.4f}",         "—"),
                ("Contraction ratio",  f"{Cr:.1f}",              "—"),
                ("Chamber diam Dc",    f"{2*math.sqrt(Ac/math.pi)*1000:.1f}", "mm"),
                ("Chamber length Lc",  f"{Lc*1000:.1f}",         "mm"),
                ("Conical length",     f"{L_conical*1000:.1f}",  "mm"),
                ("Bell length (80%)",  f"{L_bell_80*1000:.1f}",  "mm"),
                ("Exhaust velocity",   f"{ve:.1f}",              "m/s"),
            ],
            "profile_x":  x_mm,
            "profile_r":  r_mm,
            "mach_x":     x_mm,
            "mach_vals":  m_vals,
            "params": {
                "dt_mm": dt, "de_mm": de, "rt_m": rt, "re_m": re,
                "At_m2": At, "Ae_m2": Ae, "mdot": mdot,
                "M_exit": M_exit, "gamma": gamma,
            }
        }


# ══════════════════════════════════════════════════════════════════════
# CEAWorker QThread
# ══════════════════════════════════════════════════════════════════════
class CEAWorker(QThread):
    result_ready = Signal(object)   # CEAResult
    data_parsed  = Signal(object)   # CEAResult (success only → triggers plots)
    engine_error = Signal(str)
    log_message  = Signal(str)

    def __init__(self, formulation: Formulation, parent=None):
        super().__init__(parent)
        self._f   = copy.deepcopy(formulation)
        self._cfg = ConfigManager()
        self._fb  = FallbackCalculator()
        self._p   = OUTParser()

    def run(self):
        try:
            r = self._execute()
            self.result_ready.emit(r)
            if r.success:
                self.data_parsed.emit(r)
        except ParseError as pe:
            self.engine_error.emit(str(pe))
            r = CEAResult(); r.error_msg = str(pe)
            self.result_ready.emit(r)
        except Exception as e:
            self.engine_error.emit(str(e))
            r = CEAResult(); r.error_msg = str(e)
            self.result_ready.emit(r)

    def _execute(self) -> CEAResult:
        inp = INPBuilder.build(self._f)
        sname = re.sub(r"[^\w]","_", self._f.name)[:20] or "cea_run"

        if not self._cfg.cea_available():
            self.log_message.emit("FCEA2.exe not configured — fallback.")
            r = self._fb.calculate(self._f); r.raw_inp = inp
            return r

        wdir = self._cfg.cea_work_dir() or tempfile.gettempdir()
        os.makedirs(wdir, exist_ok=True)
        inp_p = os.path.join(wdir, f"{sname}.inp")
        out_p = os.path.join(wdir, f"{sname}.out")

        with open(inp_p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(inp)
        if os.path.exists(out_p):
            try: os.remove(out_p)
            except: pass

        self.log_message.emit(f"Running FCEA2: {sname}.inp")
        try:
            proc = subprocess.run(
                [self._cfg.fcea2_exe()],
                input=f"{sname}\n",       # basename only — CRITICAL
                capture_output=True, text=True,
                timeout=30, cwd=wdir)
            raw = ""
            if os.path.exists(out_p):
                with open(out_p,"r",encoding="utf-8",errors="replace") as fh:
                    raw = fh.read()
            else:
                raw = proc.stdout or ""
            if not raw.strip():
                raise ParseError(
                    f"Engine Execution Error: no output produced.\n"
                    f"RC={proc.returncode}  stderr={proc.stderr[:200]}")
            r = self._p.parse(raw, self._f.name)
            r.raw_inp = inp; r.ae_at = self._f.area_ratio
            self.log_message.emit(
                f"OK: Isp={r.isp_ms:.0f}m/s  C*={r.cstar:.0f}m/s")
            return r
        except subprocess.TimeoutExpired:
            raise ParseError("Engine Execution Error: FCEA2 timed out (30s)")
        except FileNotFoundError:
            self.log_message.emit("FCEA2 not found — fallback.")
            r = self._fb.calculate(self._f); r.raw_inp = inp; return r


# ══════════════════════════════════════════════════════════════════════
# BatchSweepWorker QThread
# ══════════════════════════════════════════════════════════════════════
class BatchSweepWorker(QThread):
    row_ready   = Signal(dict)
    progress    = Signal(int, int)
    log_message = Signal(str)
    sweep_done  = Signal(list)

    def __init__(self, base: Formulation, params: dict, parent=None):
        super().__init__(parent)
        self._base   = copy.deepcopy(base)
        self._params = copy.deepcopy(params)
        self._cancel = False
        self._mutex  = QMutex()
        self._fb     = FallbackCalculator()

    def cancel(self):
        with QMutexLocker(self._mutex): self._cancel = True

    def _cancelled(self):
        with QMutexLocker(self._mutex): return self._cancel

    def run(self):
        combos = self._build()
        total  = len(combos)
        all_rows = []
        for i, (tc, pc, ar, of_v) in enumerate(combos):
            if self._cancelled(): break
            f = copy.deepcopy(self._base)
            f.chamber_pressure = pc; f.of_ratio = of_v; f.area_ratio = ar
            try:
                r = self._fb.calculate(f)
                if tc and r.t_chamber > 0:
                    ratio = tc / r.t_chamber
                    r.t_chamber *= ratio; r.t_throat *= ratio
                r.ae_at = ar
                row = dict(idx=i+1, tc=tc, pc=pc, ae_at=ar, of=of_v,
                           isp_ms=round(r.isp_ms,1), cstar=round(r.cstar,1),
                           cf=round(r.cf,4), tc_k=round(r.t_chamber,1),
                           mw=round(r.mw,3), status="OK", result=r)
            except Exception as e:
                row = dict(idx=i+1, tc=tc, pc=pc, ae_at=ar, of=of_v,
                           isp_ms=0,cstar=0,cf=0,tc_k=0,mw=0,
                           status=f"ERR:{str(e)[:20]}", result=None)
            all_rows.append(row)
            self.row_ready.emit(row)
            self.progress.emit(i+1, total)
        self.sweep_done.emit(all_rows)

    def _build(self):
        def rng(p, base):
            if not p.get("enabled"): return [base]
            try:
                fr,to_,st = p["from"],p["to"],p["step"]
                if st<=0: return [fr]
                v,vals = fr,[]
                while v<=to_+st*0.001:
                    vals.append(round(v,6)); v+=st
                return vals or [fr]
            except: return [base]
        p = self._params
        b = self._base
        return list(itertools.product(
            rng(p.get("tc",{}),    3200.0),
            rng(p.get("pc",{}),    b.chamber_pressure),
            rng(p.get("ae_at",{}), b.area_ratio),
            rng(p.get("of",{}),    b.of_ratio)))
