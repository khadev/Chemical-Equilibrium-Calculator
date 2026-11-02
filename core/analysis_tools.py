"""
core/analysis_tools.py
=========================
Registry of analysis tools, organized by category, exposed through the
Tools menu. Each :class:`ToolSpec` is a self-contained Command object:
declarative inputs + a pure ``compute()`` function returning a
:class:`ToolOutput`. The UI (``ui/dialogs/tool_dialog.py``) renders any
tool generically from its spec — no per-tool UI code is needed.

All formulas are real, standard aerospace-engineering relations
(isentropic flow, Rankine-Hugoniot shock relations, Tsiolkovsky rocket
equation, vis-viva/Hohmann transfer, Sutton-Graves stagnation heating,
Bartz heat-transfer correlation, etc.) Where a formula is a simplified
or heuristic engineering estimate rather than an exact physical law
(e.g. erosion rate, combustion instability mode frequencies), this is
stated explicitly in the tool's description/notes so results are never
mistaken for validated, certification-grade figures.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from models.cea_result import CEAResult, G0
from models.formulation import Formulation

EARTH_MU_KM3_S2 = 398600.4418  # standard gravitational parameter, km^3/s^2


@dataclass
class ToolInput:
    """One declarative input field for a tool dialog."""

    key: str
    label: str
    default: float
    unit: str = ""
    is_dropdown: bool = False
    options: List[str] = field(default_factory=list)


@dataclass
class ToolOutput:
    """Result of running a tool: display rows plus optional chart data."""

    rows: List[Tuple[str, str, str]] = field(default_factory=list)
    notes: str = ""
    chart_x: Optional[List[float]] = None
    chart_y: Optional[List[float]] = None
    chart_xlabel: str = ""
    chart_ylabel: str = ""
    chart_title: str = ""


@dataclass
class ToolSpec:
    """A single analysis tool: inputs + compute function."""

    key: str
    name: str
    category: str
    description: str
    inputs: List[ToolInput]
    compute: Callable[[Optional[CEAResult], Optional[Formulation], Dict[str, float]], ToolOutput]
    needs_result: bool = False


# ══════════════════════════════════════════════════════════════════════
# 🚀 Nozzle & Geometry
# ══════════════════════════════════════════════════════════════════════
def _compute_chamber_sizer(result, formulation, v) -> ToolOutput:
    dt_mm = v["throat_diam_mm"]
    cr = v["contraction_ratio"]
    l_star_m = v["l_star_m"]
    at_m2 = math.pi * (dt_mm / 2000.0) ** 2
    ac_m2 = at_m2 * cr
    dc_mm = 2000.0 * math.sqrt(ac_m2 / math.pi)
    vol_m3 = l_star_m * at_m2
    length_mm = (vol_m3 / ac_m2) * 1000.0
    return ToolOutput(rows=[
        ("Throat area At", f"{at_m2 * 1e4:.4f}", "cm²"),
        ("Chamber area Ac", f"{ac_m2 * 1e4:.4f}", "cm²"),
        ("Chamber diameter Dc", f"{dc_mm:.1f}", "mm"),
        ("Chamber volume Vc", f"{vol_m3 * 1e6:.1f}", "cm³"),
        ("Chamber length Lc", f"{length_mm:.1f}", "mm"),
    ], notes="Vc = L* × At  (characteristic length method).")


def _compute_contraction_ratio(result, formulation, v) -> ToolOutput:
    dt_mm = v["throat_diam_mm"]
    dt_in = dt_mm / 25.4
    cr = 8.0 / max(dt_in, 0.05) ** 0.6 + 1.25
    cr = max(1.3, min(cr, 10.0))
    at_m2 = math.pi * (dt_mm / 2000.0) ** 2
    dc_mm = dt_mm * math.sqrt(cr)
    return ToolOutput(rows=[
        ("Recommended Cr", f"{cr:.2f}", "—"),
        ("Resulting Dc", f"{dc_mm:.1f}", "mm"),
        ("Throat area At", f"{at_m2 * 1e4:.4f}", "cm²"),
    ], notes=("Empirical engineering correlation (Sutton-style curve fit): "
             "smaller throats need a higher contraction ratio for stable "
             "injector mixing. Treat as a starting point, not a hard rule."))


def _compute_bell_length(result, formulation, v) -> ToolOutput:
    area_ratio = v["area_ratio"]
    dt_mm = v["throat_diam_mm"]
    half_angle_deg = v["conical_half_angle_deg"]
    rt_mm = dt_mm / 2.0
    re_mm = rt_mm * math.sqrt(area_ratio)
    l_conical = (re_mm - rt_mm) / math.tan(math.radians(half_angle_deg))
    rows = [("100% Conical reference", f"{l_conical:.1f}", "mm")]
    for pct in (60, 70, 80, 90, 100):
        rows.append((f"{pct}% Bell (Rao approx.)",
                    f"{l_conical * pct / 100.0:.1f}", "mm"))
    return ToolOutput(rows=rows, notes=(
        "Rao parabolic bell nozzles achieve comparable performance to a "
        "15° conical nozzle at a fraction of the length. 80% bell is the "
        "common industry default."))


# ══════════════════════════════════════════════════════════════════════
# 🔥 Thermal & Cooling
# ══════════════════════════════════════════════════════════════════════
def _compute_bartz(result, formulation, v) -> ToolOutput:
    dt_m = v["throat_diam_mm"] / 1000.0
    pc_pa = v["chamber_pressure_bar"] * 1e5
    cstar = v["cstar_m_s"]
    mu = v["gas_viscosity_pa_s"]
    cp = v["gas_cp_j_kgk"]
    pr = v["prandtl_number"]
    rc_m = v["throat_curvature_radius_mm"] / 1000.0
    sigma = v["correction_factor_sigma"]
    area_ratio_local = v["local_area_ratio"]

    hg = ((0.026 / dt_m ** 0.2)
         * (mu ** 0.2 * cp / pr ** 0.6)
         * (pc_pa / cstar) ** 0.8
         * (dt_m / rc_m) ** 0.1
         * (1.0 / area_ratio_local) ** 0.9
         * sigma)
    return ToolOutput(rows=[
        ("Heat transfer coeff hg", f"{hg:.1f}", "W/(m²·K)"),
        ("hg (per cm²)", f"{hg / 1e4:.4f}", "W/(cm²·K)"),
    ], notes=("Bartz correlation. If chamber gas viscosity/Prandtl were "
             "not measured by FCEA2, representative defaults were used — "
             "import trans.lib for species-specific values."))


def _compute_regen_cooling(result, formulation, v) -> ToolOutput:
    q_mw_m2 = v["heat_flux_mw_m2"]
    area_m2 = v["wall_area_m2"]
    cp = v["coolant_cp_j_kgk"]
    dt_allowed = v["allowed_temp_rise_k"]
    q_total_w = q_mw_m2 * 1e6 * area_m2
    mdot_coolant = q_total_w / (cp * dt_allowed)
    return ToolOutput(rows=[
        ("Total heat load Q", f"{q_total_w / 1000.0:.2f}", "kW"),
        ("Required coolant ṅ", f"{mdot_coolant:.4f}", "kg/s"),
    ], notes=("First-order sizing estimate: ṅ = Q / (cp·ΔT). Real channel "
             "design also needs pressure-drop and critical-heat-flux "
             "margin analysis."))


def _compute_instability(result, formulation, v) -> ToolOutput:
    tc_k = v["chamber_temp_k"]
    gamma = v["gamma"]
    mw = v["molecular_weight"]
    diam_mm = v["chamber_diam_mm"]
    length_mm = v["chamber_length_mm"]

    r_specific = 8314.5 / max(mw, 1e-6)
    sound_speed = math.sqrt(gamma * r_specific * tc_k)
    diam_m = diam_mm / 1000.0
    length_m = length_mm / 1000.0

    f_long1 = sound_speed / (2.0 * length_m)
    f_tang1 = 0.59 * sound_speed / diam_m

    def classify(f: float) -> str:
        if f < 100:
            return "Chugging range"
        if f < 1000:
            return "Buzzing range"
        return "Screech range"

    return ToolOutput(rows=[
        ("Speed of sound a", f"{sound_speed:.1f}", "m/s"),
        ("1st Longitudinal mode", f"{f_long1:.1f}", "Hz"),
        ("  → regime", classify(f_long1), ""),
        ("1st Tangential mode", f"{f_tang1:.1f}", "Hz"),
        ("  → regime", classify(f_tang1), ""),
    ], notes=("Approximate acoustic mode estimates for an empty cylindrical "
             "chamber (a/2L and ≈0.59·a/D). Real instability behaviour "
             "depends heavily on injector pattern and damping devices."))


def _compute_reentry_heating(result, formulation, v) -> ToolOutput:
    velocity = v["velocity_km_s"] * 1000.0
    density = v["atmospheric_density_kg_m3"]
    nose_radius = v["nose_radius_m"]
    k = 1.7415e-4
    q_w_cm2 = k * math.sqrt(density / max(nose_radius, 1e-6)) * velocity ** 3
    return ToolOutput(rows=[
        ("Stagnation heat flux", f"{q_w_cm2:.2f}", "W/cm²"),
        ("Stagnation heat flux", f"{q_w_cm2 * 1e4:.1f}", "W/m²"),
    ], notes="Sutton-Graves correlation: q = k·√(ρ/Rn)·V³, k=1.7415×10⁻⁴.")


# ══════════════════════════════════════════════════════════════════════
# 🌍 Mission & Performance
# ══════════════════════════════════════════════════════════════════════
def _compute_delta_v(result, formulation, v) -> ToolOutput:
    isp_s = v["isp_s"]
    m0 = v["wet_mass_kg"]
    mf = v["dry_mass_kg"]
    if mf <= 0 or m0 <= mf:
        return ToolOutput(rows=[("Error", "dry mass must be < wet mass", "")])
    dv = isp_s * G0 * math.log(m0 / mf)
    return ToolOutput(rows=[
        ("ΔV", f"{dv:.1f}", "m/s"),
        ("ΔV", f"{dv / 1000.0:.3f}", "km/s"),
        ("Propellant mass", f"{m0 - mf:.1f}", "kg"),
        ("Mass ratio m0/mf", f"{m0 / mf:.3f}", "—"),
    ], notes="Tsiolkovsky rocket equation: ΔV = Isp·g₀·ln(m₀/mf).")


def _compute_hohmann(result, formulation, v) -> ToolOutput:
    r1 = v["initial_orbit_radius_km"]
    r2 = v["final_orbit_radius_km"]
    mu = EARTH_MU_KM3_S2
    v1 = math.sqrt(mu / r1)
    v2 = math.sqrt(mu / r2)
    a_t = (r1 + r2) / 2.0
    v_p = math.sqrt(mu * (2.0 / r1 - 1.0 / a_t))
    v_a = math.sqrt(mu * (2.0 / r2 - 1.0 / a_t))
    dv1 = abs(v_p - v1)
    dv2 = abs(v2 - v_a)
    return ToolOutput(rows=[
        ("v1 (initial circular)", f"{v1:.3f}", "km/s"),
        ("v2 (final circular)", f"{v2:.3f}", "km/s"),
        ("ΔV1 (departure burn)", f"{dv1:.3f}", "km/s"),
        ("ΔV2 (arrival burn)", f"{dv2:.3f}", "km/s"),
        ("Total ΔV", f"{dv1 + dv2:.3f}", "km/s"),
        ("Transfer time", f"{math.pi * math.sqrt(a_t ** 3 / mu) / 3600:.2f}", "hours"),
    ], notes="Classic two-burn Hohmann transfer (vis-viva equation).")


def _compute_staging(result, formulation, v) -> ToolOutput:
    target_dv = v["target_dv_km_s"] * 1000.0
    isp1 = v["isp1_s"]
    isp2 = v["isp2_s"]

    dv_equal_1 = target_dv / 2.0
    dv_equal_2 = target_dv / 2.0

    weight1 = isp1 / (isp1 + isp2)
    dv_weighted_1 = target_dv * weight1
    dv_weighted_2 = target_dv - dv_weighted_1

    mr1_eq = math.exp(dv_equal_1 / (isp1 * G0))
    mr2_eq = math.exp(dv_equal_2 / (isp2 * G0))
    mr1_w = math.exp(dv_weighted_1 / (isp1 * G0))
    mr2_w = math.exp(dv_weighted_2 / (isp2 * G0))

    return ToolOutput(rows=[
        ("Equal split  ΔV1 / ΔV2", f"{dv_equal_1:.0f} / {dv_equal_2:.0f}", "m/s"),
        ("  Mass ratios R1 / R2", f"{mr1_eq:.3f} / {mr2_eq:.3f}", "—"),
        ("Isp-weighted ΔV1 / ΔV2", f"{dv_weighted_1:.0f} / {dv_weighted_2:.0f}", "m/s"),
        ("  Mass ratios R1 / R2", f"{mr1_w:.3f} / {mr2_w:.3f}", "—"),
    ], notes=("Two simplified 2-stage split strategies for comparison. True "
             "Lagrange-optimal staging also weighs structural mass "
             "fractions per stage — treat both as starting estimates."))


def _compute_twr(result, formulation, v) -> ToolOutput:
    thrust_kn = v["thrust_kn"]
    vehicle_mass = v["vehicle_mass_kg"]
    propellant_mass = v["propellant_mass_kg"]
    mdot = v["mass_flow_kg_s"]
    twr = (thrust_kn * 1000.0) / (vehicle_mass * G0)
    burn_time = propellant_mass / max(mdot, 1e-9)
    return ToolOutput(rows=[
        ("Thrust-to-Weight ratio", f"{twr:.3f}", "—"),
        ("Burn time", f"{burn_time:.1f}", "s"),
    ], notes="T/W = F / (m·g₀);  burn time = mp / ṅ.")


# ══════════════════════════════════════════════════════════════════════
# 📊 Advanced Analysis
# ══════════════════════════════════════════════════════════════════════
def _compute_cj_detonation(result, formulation, v) -> ToolOutput:
    q_kj_kg = v["heat_release_kj_kg"]
    gamma = v["gamma_products"]
    q_j_kg = q_kj_kg * 1000.0
    try:
        d_cj = math.sqrt(2.0 * (gamma ** 2 - 1.0) * q_j_kg)
    except ValueError:
        d_cj = 0.0
    return ToolOutput(rows=[
        ("CJ detonation velocity (approx.)", f"{d_cj:.1f}", "m/s"),
    ], notes=("Simplified Chapman-Jouguet approximation D≈√(2(γ²-1)q). For "
             "design-grade values use a full chemical-equilibrium "
             "detonation code."))


def _compute_shock(result, formulation, v) -> ToolOutput:
    m1 = v["mach_upstream"]
    gamma = v["gamma"]
    if m1 <= 1.0:
        return ToolOutput(rows=[("Error", "M1 must be > 1 (supersonic)", "")])
    m2_sq = (1 + (gamma - 1) / 2 * m1 ** 2) / (gamma * m1 ** 2 - (gamma - 1) / 2)
    m2 = math.sqrt(m2_sq)
    p_ratio = (2 * gamma * m1 ** 2 - (gamma - 1)) / (gamma + 1)
    t_ratio = ((2 * gamma * m1 ** 2 - (gamma - 1))
              * ((gamma - 1) * m1 ** 2 + 2) / ((gamma + 1) ** 2 * m1 ** 2))
    rho_ratio = p_ratio / t_ratio
    return ToolOutput(rows=[
        ("M2 (downstream)", f"{m2:.4f}", "—"),
        ("P2/P1", f"{p_ratio:.4f}", "—"),
        ("T2/T1", f"{t_ratio:.4f}", "—"),
        ("ρ2/ρ1", f"{rho_ratio:.4f}", "—"),
    ], notes="Exact normal-shock (Rankine-Hugoniot) relations.")


def _compute_equivalence_ratio(result, formulation, v) -> ToolOutput:
    c_atoms = v["fuel_carbon_atoms"]
    h_atoms = v["fuel_hydrogen_atoms"]
    of_actual = v["actual_of_ratio"]
    o2_per_mole_fuel = c_atoms + h_atoms / 4.0
    fuel_mw = 12.011 * c_atoms + 1.008 * h_atoms
    of_stoich = (o2_per_mole_fuel * 31.998) / max(fuel_mw, 1e-9)
    phi = of_stoich / max(of_actual, 1e-9)
    regime = "Fuel-rich" if phi > 1.05 else "Fuel-lean" if phi < 0.95 else "Stoichiometric"
    return ToolOutput(rows=[
        ("Stoichiometric O/F", f"{of_stoich:.3f}", "—"),
        ("Equivalence ratio φ", f"{phi:.3f}", "—"),
        ("Regime", regime, ""),
    ], notes=("φ = (O/F)stoich / (O/F)actual, for a CxHy hydrocarbon + O2 "
             "reaction. For non-hydrocarbon propellants, treat as "
             "illustrative only."))


def _compute_sensitivity(result, formulation, v) -> ToolOutput:
    from core.fallback_calculator import FallbackCalculator
    if formulation is None:
        return ToolOutput(rows=[("Error", "No active formulation", "")])

    param = v["_param_choice"]
    pct_range = v["range_pct"]
    steps = int(v["steps"])
    calc = FallbackCalculator()

    base_value = getattr(formulation, param)
    deltas = [base_value * (1 + pct_range / 100.0 * (i / (steps // 2) - 1))
             for i in range(steps)] if steps > 1 else [base_value]

    rows = []
    x_vals, y_vals = [], []
    for delta in deltas:
        import copy as _copy
        trial = _copy.deepcopy(formulation)
        setattr(trial, param, delta)
        trial_result = calc.calculate(trial)
        rows.append((f"{param} = {delta:.3g}",
                    f"{trial_result.isp_m_s:.1f}", "m/s Isp"))
        x_vals.append(delta)
        y_vals.append(trial_result.isp_m_s)

    return ToolOutput(
        rows=rows,
        notes=(f"Sweeping '{param}' ±{pct_range:.0f}% using the fast "
              "fallback calculator (always, regardless of engine mode) "
              "for instant interactive feedback."),
        chart_x=x_vals, chart_y=y_vals,
        chart_xlabel=param, chart_ylabel="Isp (m/s)",
        chart_title=f"Isp sensitivity to {param}")


def _compute_autoignition(result, formulation, v) -> ToolOutput:
    notes_table = [
        ("RP-1 / LOX", "Not hypergolic", "Autoignition ≈ 480 °C; requires igniter"),
        ("N2H4 / N2O4", "Hypergolic", "Ignites on contact"),
        ("MMH / N2O4", "Hypergolic", "Ignites on contact"),
        ("UDMH / N2O4", "Hypergolic", "Ignites on contact (Aerozine-50 base)"),
        ("LH2 / LOX", "Not hypergolic", "Requires igniter; wide flammability range"),
        ("CH4 / LOX", "Not hypergolic", "Requires igniter"),
        ("H2O2 (high conc.)", "Catalytic decomposition", "Decomposes on Ag/MnO2 catalyst bed"),
    ]
    return ToolOutput(
        rows=[(pair, behavior, note) for pair, behavior, note in notes_table],
        notes="Reference table of common propellant ignition behaviour.")


def _compute_mixture_optimization(result, formulation, v) -> ToolOutput:
    from core.fallback_calculator import FallbackCalculator
    import copy as _copy
    if formulation is None:
        return ToolOutput(rows=[("Error", "No active formulation", "")])

    of_min = v["of_min"]
    of_max = v["of_max"]
    steps = max(int(v["steps"]), 3)
    calc = FallbackCalculator()

    of_values = [of_min + (of_max - of_min) * i / (steps - 1) for i in range(steps)]
    isp_values = []
    for of_value in of_values:
        trial = _copy.deepcopy(formulation)
        trial.of_ratio = of_value
        isp_values.append(calc.calculate(trial).isp_m_s)

    best_idx = isp_values.index(max(isp_values))
    rows = [(f"O/F = {of:.3f}", f"{isp:.1f}", "m/s Isp")
            for of, isp in zip(of_values, isp_values)]
    rows.append(("★ Optimum found", f"O/F = {of_values[best_idx]:.3f}",
                f"Isp = {isp_values[best_idx]:.1f} m/s"))
    return ToolOutput(
        rows=rows,
        notes=("Sweeps O/F across the requested range using the fallback "
              "calculator's mixture-efficiency model (a parabolic "
              "approximation centred on each propellant's published "
              "peak-Isp ratio) — always uses the fallback model regardless "
              "of the current Engine mode, for instant feedback."),
        chart_x=of_values, chart_y=isp_values,
        chart_xlabel="O/F Ratio", chart_ylabel="Isp (m/s)",
        chart_title="Mixture Ratio Optimization")


def _compute_frozen_vs_equilibrium(result, formulation, v) -> ToolOutput:
    isp_eq = v["isp_equilibrium_s"]
    loss_pct = v["estimated_kinetic_loss_pct"]
    isp_frozen = isp_eq * (1.0 - loss_pct / 100.0)
    delta_isp_ms = (isp_eq - isp_frozen) * G0
    return ToolOutput(rows=[
        ("Isp (equilibrium)", f"{isp_eq:.2f}", "s"),
        ("Isp (frozen, estimated)", f"{isp_frozen:.2f}", "s"),
        ("ΔIsp", f"{delta_isp_ms:.1f}", "m/s"),
        ("Kinetic loss", f"{loss_pct:.2f}", "%"),
    ], notes=(
        "Equilibrium flow lets chemistry continuously re-equilibrate as "
        "the gas expands (slightly higher Isp); frozen flow holds chamber "
        "composition fixed through the nozzle (slightly lower Isp, but "
        "easier/faster to compute). Real FCEA2 output reports both "
        "directly — this estimate applies a user-specified kinetic-loss "
        "percentage to illustrate the relationship. Small engines/short "
        "nozzles tend toward equilibrium; large/fast-expanding nozzles "
        "tend toward frozen."))


def _compute_doe_two_factor(result, formulation, v) -> ToolOutput:
    from core.fallback_calculator import FallbackCalculator
    import copy as _copy
    if formulation is None:
        return ToolOutput(rows=[("Error", "No active formulation", "")])

    pc_low, pc_high = v["pc_low_bar"], v["pc_high_bar"]
    ar_low, ar_high = v["area_ratio_low"], v["area_ratio_high"]
    calc = FallbackCalculator()

    corners = [
        ("Pc-low / AR-low", pc_low, ar_low),
        ("Pc-low / AR-high", pc_low, ar_high),
        ("Pc-high / AR-low", pc_high, ar_low),
        ("Pc-high / AR-high", pc_high, ar_high),
    ]
    rows = []
    isp_values = []
    for label, pc, ar in corners:
        trial = _copy.deepcopy(formulation)
        trial.chamber_pressure_bar = pc
        trial.area_ratio = ar
        trial_result = calc.calculate(trial)
        rows.append((label, f"{trial_result.isp_m_s:.1f}",
                    f"Pc={pc:.0f}bar  Ae/At={ar:.1f}"))
        isp_values.append(trial_result.isp_m_s)

    best_idx = isp_values.index(max(isp_values))
    rows.append(("★ Best corner", corners[best_idx][0],
                f"Isp = {isp_values[best_idx]:.1f} m/s"))
    return ToolOutput(rows=rows, notes=(
        "2-factor, 2-level (2²) design of experiments over chamber "
        "pressure and area ratio — a quick way to see which factor "
        "dominates Isp before running a full sweep."))


# ══════════════════════════════════════════════════════════════════════
# 🧊 Materials & Safety
# ══════════════════════════════════════════════════════════════════════
def _compute_material_selector(result, formulation, v) -> ToolOutput:
    chamber_temp = v["chamber_temp_k"]
    materials = [
        ("Copper alloy (GRCop-42)", 1200, 8900, "Active regen. cooling required"),
        ("Inconel 718", 1250, 8190, "Good high-temp strength, moderate cost"),
        ("Niobium C-103", 1650, 8860, "Used uncooled on many upper-stage nozzles"),
        ("Rhenium / Ir-coated", 2200, 21000, "Excellent but very expensive"),
        ("Carbon-Carbon composite", 3000, 1800, "Low density, ablates slowly"),
        ("Graphite (inert atm.)", 3300, 2200, "Oxidizes readily if O2 present"),
    ]
    rows = []
    for name, max_temp, density, note in materials:
        suitable = "✓ Suitable" if max_temp >= chamber_temp else "✗ Too low"
        rows.append((name, f"max {max_temp} K  ({density} kg/m³)",
                    f"{suitable} — {note}"))
    return ToolOutput(rows=rows, notes=(
        "Representative reference figures for comparison only — verify "
        "against manufacturer data sheets before any real design use."))


def _compute_erosion(result, formulation, v) -> ToolOutput:
    loading_pct = v["particle_loading_pct"]
    velocity = v["exit_velocity_m_s"]
    burn_time = v["burn_time_s"]
    k = 0.001
    rate_mm_s = k * (loading_pct / 100.0) * (velocity / 1000.0) ** 2
    total_mm = rate_mm_s * burn_time
    return ToolOutput(rows=[
        ("Erosion rate (heuristic)", f"{rate_mm_s:.5f}", "mm/s"),
        ("Total erosion over burn", f"{total_mm:.3f}", "mm"),
    ], notes=("⚠ Illustrative relative-comparison heuristic ONLY — not a "
             "validated erosion model. Real throat erosion depends on "
             "material, particle size/shape, and chemistry; use test "
             "data or a dedicated erosion code for actual design work."))


def _compute_toxicity(result, formulation, v) -> ToolOutput:
    if result is None or not result.success:
        return ToolOutput(rows=[("Error", "Run a calculation first", "")])
    if not result.mass_fractions:
        return ToolOutput(rows=[(
            "No species data available", "—",
            "The Fallback calculator doesn't model exhaust chemistry — "
            "switch Engine mode to 'FCEA2 Only' or 'Auto' with FCEA2.exe "
            "configured to get real species mass fractions to scan.")])
    hazard_db = {
        "HCl": "Corrosive; respiratory/eye irritant at ground level",
        "Cl2": "Toxic, corrosive gas",
        "HF": "Highly toxic and corrosive",
        "NO": "Respiratory irritant, contributes to NOx",
        "NO2": "Toxic, reddish-brown; respiratory hazard",
        "CO": "Toxic, odorless asphyxiant",
        "Al2O3(a)": "Particulate; inhalation hazard in high concentration",
        "Al2O3(L)": "Particulate; inhalation hazard in high concentration",
        "SO2": "Respiratory irritant",
        "HCN": "Highly toxic",
    }
    rows = []
    for species, fraction in sorted(result.mass_fractions.items(), key=lambda x: -x[1]):
        if species in hazard_db:
            rows.append((species, f"{fraction * 100:.2f}%", hazard_db[species]))
    if not rows:
        rows.append(("None flagged", "—", "No commonly-tracked hazardous "
                                          "species found above threshold"))
    notes = ("Flags commonly-tracked exhaust hazards from public environmental/"
            "safety references. Not a substitute for a full environmental "
            "impact or industrial-hygiene assessment.")
    if result.method.startswith("Fallback"):
        notes += (" ⚠ These percentages are representative literature values "
                  "for this propellant class (Fallback mode has no chemical-"
                  "equilibrium solver) — not computed for your exact inputs.")
    return ToolOutput(rows=rows, notes=notes)


# ══════════════════════════════════════════════════════════════════════
# 📝 Export & Scripting
# ══════════════════════════════════════════════════════════════════════
def _compute_latex_table(result, formulation, v) -> ToolOutput:
    if result is None:
        return ToolOutput(rows=[("Error", "Run a calculation first", "")])
    units = {"pressure": "bar", "temperature": "K"}
    lines = [
        r"\begin{tabular}{|l|r|l|}",
        r"\hline",
        r"Parameter & Value & Unit \\",
        r"\hline",
    ]
    for row in result.to_table_rows(units):
        param, value, unit = row[0], row[1], row[2]
        param_escaped = param.replace("γ", r"$\gamma$").replace("%", r"\%")
        lines.append(f"{param_escaped} & {value} & {unit} \\\\")
    lines += [r"\hline", r"\end{tabular}"]
    latex = "\n".join(lines)
    return ToolOutput(rows=[("LaTeX source", "(see notes below)", "")],
                      notes=latex)


def _compute_python_script(result, formulation, v) -> ToolOutput:
    if formulation is None:
        return ToolOutput(rows=[("Error", "No active formulation", "")])
    script = f'''"""
Standalone reproduction of a CEA Calculator Pro ideal-rocket estimate.
Generated by the Python Script Generator tool — uses the same
isentropic-flow relations as the application's fallback calculator.
"""
import math

G0 = 9.80665

oxidizer_name = {formulation.oxidizer_name!r}
fuel_name = {formulation.fuel_name!r}
chamber_pressure_bar = {formulation.chamber_pressure_bar}
of_ratio = {formulation.of_ratio}
area_ratio = {formulation.area_ratio}

# Representative properties (replace with real CEA output if available)
t_chamber_k = 3200.0
gamma = 1.22
cstar_m_s = 1750.0

def mach_from_area_ratio(ar, g, mach=3.0):
    for _ in range(80):
        term = (2/(g+1)) * (1 + (g-1)/2 * mach**2)
        ar_calc = (1/mach) * term ** ((g+1)/(2*(g-1)))
        d = 1e-6
        ar_d = (1/(mach+d)) * ((2/(g+1))*(1+(g-1)/2*(mach+d)**2)) ** ((g+1)/(2*(g-1)))
        slope = (ar_d - ar_calc) / d
        mach += (ar - ar_calc) / slope
    return mach

mach_exit = mach_from_area_ratio(area_ratio, gamma)
t_exit = t_chamber_k / (1 + (gamma-1)/2 * mach_exit**2)
print(f"Oxidizer: {{oxidizer_name}}  Fuel: {{fuel_name}}")
print(f"Mach exit: {{mach_exit:.3f}}  T exit: {{t_exit:.1f}} K")
'''
    return ToolOutput(rows=[("Python script", "(see notes below)", "")],
                      notes=script)


def _compute_markdown_report(result, formulation, v) -> ToolOutput:
    if result is None or not result.success:
        return ToolOutput(rows=[("Error", "Run a calculation first", "")])
    units = {"pressure": "bar", "temperature": "K"}
    lines = [
        f"# CEA Calculator Pro — Performance Report",
        f"",
        f"**Formulation:** {result.name or 'Unnamed'}  ",
        f"**Method:** {result.method}",
        f"",
        f"## Performance Summary",
        f"",
        f"| Parameter | Value | Unit |",
        f"|---|---|---|",
    ]
    for row in result.to_table_rows(units):
        param, value, unit = row[0], row[1], row[2]
        lines.append(f"| {param} | {value} | {unit} |")
    if result.mass_fractions:
        lines += ["", "## Exit Plane Composition", "",
                  "| Species | Mass Fraction |", "|---|---|"]
        for species, fraction in sorted(result.mass_fractions.items(),
                                        key=lambda x: -x[1]):
            lines.append(f"| {species} | {fraction * 100:.2f}% |")
    markdown = "\n".join(lines)
    return ToolOutput(rows=[("Markdown report", "(see notes below)", "")],
                      notes=markdown)


def _compute_json_export(result, formulation, v) -> ToolOutput:
    import json
    if formulation is None:
        return ToolOutput(rows=[("Error", "No active formulation", "")])
    payload = {"formulation": formulation.to_dict()}
    if result is not None and result.success:
        payload["result"] = {
            "name": result.name, "method": result.method,
            "isp_m_s": round(result.isp_m_s, 2),
            "isp_vacuum_s": round(result.isp_vacuum_s, 3),
            "cstar_m_s": round(result.cstar_m_s, 2),
            "cf": round(result.cf, 4),
            "t_chamber_k": round(result.t_chamber_k, 1),
            "gamma": round(result.gamma, 4),
            "molecular_weight": round(result.molecular_weight, 3),
            "mass_fractions": {k: round(v, 6)
                              for k, v in result.mass_fractions.items()},
        }
    json_text = json.dumps(payload, indent=2)
    return ToolOutput(rows=[("JSON export", "(see notes below)", "")],
                      notes=json_text)


# ══════════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════════
TOOL_REGISTRY: Dict[str, ToolSpec] = {}


def _register(spec: ToolSpec) -> None:
    TOOL_REGISTRY[spec.key] = spec


_register(ToolSpec(
    "chamber_sizer", "Chamber Sizer", "🚀 Nozzle & Geometry",
    "Size combustion chamber volume/length from L* and contraction ratio.",
    [ToolInput("throat_diam_mm", "Throat Diameter", 30.0, "mm"),
     ToolInput("contraction_ratio", "Contraction Ratio Cr", 5.0, "—"),
     ToolInput("l_star_m", "Characteristic Length L*", 1.0, "m")],
    _compute_chamber_sizer))

_register(ToolSpec(
    "contraction_ratio_opt", "Contraction Ratio Optimizer", "🚀 Nozzle & Geometry",
    "Empirical contraction-ratio recommendation from throat size.",
    [ToolInput("throat_diam_mm", "Throat Diameter", 30.0, "mm")],
    _compute_contraction_ratio))

_register(ToolSpec(
    "bell_length", "Bell Nozzle Length Optimizer", "🚀 Nozzle & Geometry",
    "Rao bell-nozzle length vs. equivalent conical nozzle.",
    [ToolInput("area_ratio", "Area Ratio Ae/At", 10.0, "—"),
     ToolInput("throat_diam_mm", "Throat Diameter", 30.0, "mm"),
     ToolInput("conical_half_angle_deg", "Conical Half-Angle", 15.0, "deg")],
    _compute_bell_length))

_register(ToolSpec(
    "heat_transfer", "Heat Transfer (Bartz)", "🔥 Thermal & Cooling",
    "Convective heat transfer coefficient at the throat (Bartz correlation).",
    [ToolInput("throat_diam_mm", "Throat Diameter", 30.0, "mm"),
     ToolInput("chamber_pressure_bar", "Chamber Pressure", 50.0, "bar"),
     ToolInput("cstar_m_s", "C*", 1750.0, "m/s"),
     ToolInput("gas_viscosity_pa_s", "Gas Viscosity μ", 8e-5, "Pa·s"),
     ToolInput("gas_cp_j_kgk", "Gas Cp", 2000.0, "J/(kg·K)"),
     ToolInput("prandtl_number", "Prandtl Number", 0.7, "—"),
     ToolInput("throat_curvature_radius_mm", "Throat Curvature Radius", 22.5, "mm"),
     ToolInput("correction_factor_sigma", "Correction Factor σ", 1.0, "—"),
     ToolInput("local_area_ratio", "Local A/At", 1.0, "—")],
    _compute_bartz, needs_result=True))

_register(ToolSpec(
    "regen_cooling", "Regenerative Cooling Sizing", "🔥 Thermal & Cooling",
    "First-order required coolant flow rate from heat flux.",
    [ToolInput("heat_flux_mw_m2", "Heat Flux", 10.0, "MW/m²"),
     ToolInput("wall_area_m2", "Wetted Wall Area", 0.05, "m²"),
     ToolInput("coolant_cp_j_kgk", "Coolant Cp", 2000.0, "J/(kg·K)"),
     ToolInput("allowed_temp_rise_k", "Allowed ΔT", 200.0, "K")],
    _compute_regen_cooling))

_register(ToolSpec(
    "instability", "Combustion Instability Predictor", "🔥 Thermal & Cooling",
    "Estimated acoustic mode frequencies for a cylindrical chamber.",
    [ToolInput("chamber_temp_k", "Chamber Temperature", 3200.0, "K"),
     ToolInput("gamma", "Gamma γ", 1.22, "—"),
     ToolInput("molecular_weight", "Molecular Weight", 22.0, "g/mol"),
     ToolInput("chamber_diam_mm", "Chamber Diameter", 100.0, "mm"),
     ToolInput("chamber_length_mm", "Chamber Length", 150.0, "mm")],
    _compute_instability, needs_result=True))

_register(ToolSpec(
    "reentry_heating", "Re-entry Heating (Stagnation Point)", "🔥 Thermal & Cooling",
    "Sutton-Graves convective stagnation-point heat flux estimate.",
    [ToolInput("velocity_km_s", "Velocity", 7.8, "km/s"),
     ToolInput("atmospheric_density_kg_m3", "Atmospheric Density", 0.001, "kg/m³"),
     ToolInput("nose_radius_m", "Nose Radius", 0.3, "m")],
    _compute_reentry_heating))

_register(ToolSpec(
    "delta_v", "Delta-V Calculator", "🌍 Mission & Performance",
    "Tsiolkovsky rocket equation.",
    [ToolInput("isp_s", "Specific Impulse", 300.0, "s"),
     ToolInput("wet_mass_kg", "Wet Mass m0", 1000.0, "kg"),
     ToolInput("dry_mass_kg", "Dry Mass mf", 600.0, "kg")],
    _compute_delta_v, needs_result=True))

_register(ToolSpec(
    "hohmann", "Orbit Insertion ΔV (Hohmann)", "🌍 Mission & Performance",
    "Two-burn Hohmann transfer ΔV between two circular orbits.",
    [ToolInput("initial_orbit_radius_km", "Initial Orbit Radius", 6678.0, "km"),
     ToolInput("final_orbit_radius_km", "Final Orbit Radius", 42164.0, "km")],
    _compute_hohmann))

_register(ToolSpec(
    "staging", "Staging Optimizer (2-Stage)", "🌍 Mission & Performance",
    "Compare equal-split vs Isp-weighted ΔV allocation across 2 stages.",
    [ToolInput("target_dv_km_s", "Target Total ΔV", 9.4, "km/s"),
     ToolInput("isp1_s", "Stage 1 Isp", 300.0, "s"),
     ToolInput("isp2_s", "Stage 2 Isp", 340.0, "s")],
    _compute_staging))

_register(ToolSpec(
    "twr", "Thrust-to-Weight & Burn Time", "🌍 Mission & Performance",
    "Vehicle T/W ratio and propellant burn time.",
    [ToolInput("thrust_kn", "Thrust", 10.0, "kN"),
     ToolInput("vehicle_mass_kg", "Vehicle Mass", 500.0, "kg"),
     ToolInput("propellant_mass_kg", "Propellant Mass", 300.0, "kg"),
     ToolInput("mass_flow_kg_s", "Mass Flow Rate", 3.5, "kg/s")],
    _compute_twr))

_register(ToolSpec(
    "cj_detonation", "CJ Detonation Velocity", "📊 Advanced Analysis",
    "Simplified Chapman-Jouguet detonation velocity estimate.",
    [ToolInput("heat_release_kj_kg", "Heat of Reaction", 4500.0, "kJ/kg"),
     ToolInput("gamma_products", "γ (products)", 1.2, "—")],
    _compute_cj_detonation))

_register(ToolSpec(
    "shock_wave", "Normal Shock Wave Analysis", "📊 Advanced Analysis",
    "Exact Rankine-Hugoniot normal-shock relations.",
    [ToolInput("mach_upstream", "Upstream Mach M1", 2.0, "—"),
     ToolInput("gamma", "Gamma γ", 1.4, "—")],
    _compute_shock))

_register(ToolSpec(
    "equivalence_ratio", "Equivalence Ratio Calculator", "📊 Advanced Analysis",
    "Stoichiometric O/F and equivalence ratio for a CxHy hydrocarbon fuel.",
    [ToolInput("fuel_carbon_atoms", "Fuel Carbon Atoms (x)", 1.0, "—"),
     ToolInput("fuel_hydrogen_atoms", "Fuel Hydrogen Atoms (y)", 1.95, "—"),
     ToolInput("actual_of_ratio", "Actual O/F", 2.27, "—")],
    _compute_equivalence_ratio))

_register(ToolSpec(
    "sensitivity", "Sensitivity Analysis", "📊 Advanced Analysis",
    "Sweep a formulation parameter and chart the resulting Isp trend.",
    [ToolInput("_param_choice", "Parameter", 0.0, "", is_dropdown=True,
              options=["chamber_pressure_bar", "of_ratio", "area_ratio"]),
     ToolInput("range_pct", "Sweep Range", 20.0, "%"),
     ToolInput("steps", "Number of Steps", 5.0, "—")],
    _compute_sensitivity, needs_result=True))

_register(ToolSpec(
    "autoignition", "Auto-Ignition Reference", "📊 Advanced Analysis",
    "Reference table of common propellant-pair ignition behaviour.",
    [], _compute_autoignition))

_register(ToolSpec(
    "mixture_optimization", "Mixture Ratio Optimization", "📊 Advanced Analysis",
    "Sweep O/F to find the peak-Isp mixture ratio for the active propellant.",
    [ToolInput("of_min", "O/F Range Start", 1.0, "—"),
     ToolInput("of_max", "O/F Range End", 5.0, "—"),
     ToolInput("steps", "Number of Steps", 9.0, "—")],
    _compute_mixture_optimization, needs_result=True))

_register(ToolSpec(
    "frozen_vs_equilibrium", "Frozen vs Equilibrium Comparison", "📊 Advanced Analysis",
    "Illustrates the Isp difference between frozen and equilibrium flow.",
    [ToolInput("isp_equilibrium_s", "Equilibrium Isp", 350.0, "s"),
     ToolInput("estimated_kinetic_loss_pct", "Estimated Kinetic Loss", 3.0, "%")],
    _compute_frozen_vs_equilibrium, needs_result=True))

_register(ToolSpec(
    "doe_two_factor", "Two-Factor DOE (Pc × Area Ratio)", "📊 Advanced Analysis",
    "2² design of experiments over chamber pressure and area ratio.",
    [ToolInput("pc_low_bar", "Pc Low", 40.0, "bar"),
     ToolInput("pc_high_bar", "Pc High", 100.0, "bar"),
     ToolInput("area_ratio_low", "Area Ratio Low", 8.0, "—"),
     ToolInput("area_ratio_high", "Area Ratio High", 25.0, "—")],
    _compute_doe_two_factor, needs_result=True))

_register(ToolSpec(
    "material_selector", "Nozzle Material Selector", "🧊 Materials & Safety",
    "Compare common nozzle materials against required service temperature.",
    [ToolInput("chamber_temp_k", "Required Service Temp", 3200.0, "K")],
    _compute_material_selector))

_register(ToolSpec(
    "erosion", "Erosion Rate Predictor", "🧊 Materials & Safety",
    "Illustrative heuristic throat-erosion rate from particle loading.",
    [ToolInput("particle_loading_pct", "Particle Loading", 5.0, "%"),
     ToolInput("exit_velocity_m_s", "Exit Velocity", 2000.0, "m/s"),
     ToolInput("burn_time_s", "Burn Time", 60.0, "s")],
    _compute_erosion))

_register(ToolSpec(
    "toxicity", "Exhaust Toxicity Index", "🧊 Materials & Safety",
    "Flag commonly-tracked hazardous species in the exhaust composition.",
    [], _compute_toxicity, needs_result=True))

_register(ToolSpec(
    "latex_table", "LaTeX Table Generator", "📝 Export & Scripting",
    "Export the active result's performance table as a LaTeX tabular block.",
    [], _compute_latex_table, needs_result=True))

_register(ToolSpec(
    "python_script", "Python Script Generator", "📝 Export & Scripting",
    "Generate a standalone Python script reproducing this formulation.",
    [], _compute_python_script))

_register(ToolSpec(
    "markdown_report", "Markdown Report Generator", "📝 Export & Scripting",
    "Export the active result as a formatted Markdown report.",
    [], _compute_markdown_report, needs_result=True))

_register(ToolSpec(
    "json_export", "JSON Export", "📝 Export & Scripting",
    "Export the active formulation and result as structured JSON.",
    [], _compute_json_export))


CATEGORY_ORDER = [
    "🚀 Nozzle & Geometry",
    "🔥 Thermal & Cooling",
    "🌍 Mission & Performance",
    "📊 Advanced Analysis",
    "🧊 Materials & Safety",
    "📝 Export & Scripting",
]


def tools_by_category() -> Dict[str, List[ToolSpec]]:
    """Group all registered tools by category, in display order."""
    grouped: Dict[str, List[ToolSpec]] = {c: [] for c in CATEGORY_ORDER}
    for spec in TOOL_REGISTRY.values():
        grouped.setdefault(spec.category, []).append(spec)
    return {c: grouped[c] for c in CATEGORY_ORDER if grouped.get(c)}
