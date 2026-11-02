"""
core/research_report_exporter.py
====================================
Research-grade, 8-sheet Excel export built with pandas + xlsxwriter.

Unlike core/excel_exporter.py (a quick multi-session comparison
workbook with an embedded static dashboard image), this module
produces a deep, single-session report with native Excel charts
(editable in Excel, not pictures), conditional formatting, literature
validation against a matching historical reference engine, and a
sensitivity-analysis sheet that auto-populates from any other sessions
sharing the same propellant pair.

All physics reuses this app's own already-validated functions
(IsentropicFlow's Newton-Raphson area-Mach solver) rather than adding
a scipy dependency for the same well-conditioned equation — relevant
both for dependency hygiene and for keeping a future PyInstaller
build smaller and simpler.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.fallback_calculator import IsentropicFlow
from core.molecular_weights import molecular_weight
from core.reference_engines import ReferenceEngine, match_reference_engine
from models.cea_result import CEAResult, G0
from models.formulation import Formulation

log = logging.getLogger(__name__)

# ── Style constants ──────────────────────────────────────────────────
_HEADER_BG = "#1a3a5c"
_HEADER_FG = "#FFFFFF"
_ALT_ROW_BG = "#e8f0fe"
_GREEN_BG, _GREEN_FG = "#C6EFCE", "#006100"
_YELLOW_BG, _YELLOW_FG = "#FFEB9C", "#9C6500"
_RED_BG, _RED_FG = "#FFC7CE", "#9C0006"

# Representative bulk propellant density (kg/m³), used for density
# impulse — a simplified engineering estimate, not a precise
# volumetric calculation from real component densities/wt%.
_BULK_DENSITY: Dict[str, float] = {
    "lox_rp1": 1000.0, "lox_lh2": 360.0, "lox_ch4": 828.0,
    "n2o4_mmh": 1200.0, "solid": 1800.0, "default": 1000.0,
}


def _round_sig_figs(value: float, sig_figs: int = 4) -> Tuple[float, int]:
    """
    Round ``value`` to ``sig_figs`` significant figures.

    Returns:
        Tuple of (rounded value, number of decimal places used) — the
        decimal count is reused to build a matching Excel number
        format so the displayed precision matches the rounding.
    """
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value) or value == 0:
        return 0.0, 0
    magnitude = math.floor(math.log10(abs(value)))
    decimals = max(sig_figs - magnitude - 1, 0)
    return round(value, decimals), decimals


def _num_format(decimals: int) -> str:
    """Build an Excel number-format string with thousands separators."""
    return "#,##0" + ("." + "0" * decimals if decimals > 0 else "")


def _match_propellant_key(formulation: Formulation) -> str:
    """Re-use the same propellant-class heuristic as FallbackCalculator."""
    oxidizer = (formulation.oxidizer_name or "").lower()
    fuel = (formulation.fuel_name or "").lower()
    if "nh4" in oxidizer or "clo4" in oxidizer:
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


@dataclass
class SessionRecord:
    """One session's formulation + result, used for the Sensitivity sheet."""

    name: str
    formulation: Formulation
    result: CEAResult


class ResearchReportExporter:
    """
    Builds the full 8-sheet research-grade workbook.

    Usage:
        exporter = ResearchReportExporter()
        exporter.export(result, formulation, all_sessions, "report.xlsx")
    """

    def export(
            self, result: CEAResult, formulation: Formulation,
            all_sessions: List[SessionRecord], path: str,
            software_version: str = "1.0.0",
    ) -> None:
        """
        Write the complete workbook to ``path``.

        Args:
            result: The active session's calculated result.
            formulation: The active session's formulation.
            all_sessions: Every session in the app (used to
                auto-populate the Sensitivity Analysis sheet when
                other sessions share the same propellant pair).
            path: Destination ``.xlsx`` file path.
            software_version: Displayed on the Metadata sheet.
        """
        propellant_key = _match_propellant_key(formulation)
        reference = match_reference_engine(
            formulation.oxidizer_name, formulation.fuel_name)

        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            workbook = writer.book
            fmt = self._build_formats(workbook)

            self._write_dashboard(workbook, fmt, result, formulation, reference)
            self._write_performance_parameters(
                writer, fmt, result, formulation, reference, propellant_key)
            self._write_exit_composition(writer, fmt, result)
            self._write_expansion_data(writer, fmt, result)
            self._write_thermodynamic_properties(writer, fmt, result)
            self._write_sensitivity_analysis(
                writer, fmt, result, formulation, all_sessions)
            self._write_session_metadata(
                workbook, fmt, result, formulation, software_version)
            self._write_validation_references(
                writer, fmt, result, formulation, reference)

        log.info("Research report exported: %s", path)

    # ── Shared formats ──────────────────────────────────────────────
    def _build_formats(self, workbook) -> Dict[str, object]:
        base = {"font_name": "Calibri", "font_size": 10}
        return {
            "title": workbook.add_format({
                **base, "font_size": 18, "bold": True, "font_color": _HEADER_BG}),
            "subtitle": workbook.add_format({
                **base, "font_size": 10, "italic": True, "font_color": "#616161"}),
            "header": workbook.add_format({
                **base, "bold": True, "font_color": _HEADER_FG, "bg_color": _HEADER_BG,
                "align": "center", "valign": "vcenter", "border": 1, "text_wrap": True}),
            "label": workbook.add_format({**base, "bold": True}),
            "label_alt": workbook.add_format({**base, "bold": True, "bg_color": _ALT_ROW_BG}),
            "value": workbook.add_format({**base, "align": "right"}),
            "value_alt": workbook.add_format({
                **base, "align": "right", "bg_color": _ALT_ROW_BG}),
            "cell": workbook.add_format({**base}),
            "cell_alt": workbook.add_format({**base, "bg_color": _ALT_ROW_BG}),
            "na": workbook.add_format({**base, "font_color": "#C00000", "italic": True}),
            "green": workbook.add_format({
                **base, "bg_color": _GREEN_BG, "font_color": _GREEN_FG, "bold": True,
                "align": "center", "border": 1}),
            "yellow": workbook.add_format({
                **base, "bg_color": _YELLOW_BG, "font_color": _YELLOW_FG, "bold": True,
                "align": "center", "border": 1}),
            "red": workbook.add_format({
                **base, "bg_color": _RED_BG, "font_color": _RED_FG, "bold": True,
                "align": "center", "border": 1}),
            "card_title": workbook.add_format({
                **base, "bold": True, "font_size": 10, "font_color": "#FFFFFF",
                "bg_color": _HEADER_BG, "align": "center", "valign": "vcenter",
                "border": 1}),
            "card_value": workbook.add_format({
                **base, "bold": True, "font_size": 16, "font_color": _HEADER_BG,
                "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#F5F7FA"}),
            "section": workbook.add_format({
                **base, "bold": True, "font_size": 13, "font_color": "#FFFFFF",
                "bg_color": _HEADER_BG, "align": "left", "valign": "vcenter"}),
            "note": workbook.add_format({
                **base, "italic": True, "font_color": "#E65100", "text_wrap": True}),
        }

    # ── Sheet 1: Dashboard ─────────────────────────────────────────────
    def _write_dashboard(self, workbook, fmt, result: CEAResult,
                         formulation: Formulation, reference: ReferenceEngine) -> None:
        sheet = workbook.add_worksheet("Dashboard")
        sheet.hide_gridlines(2)
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)

        sheet.merge_range("A1:H1", "CEA Performance Summary", fmt["title"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.merge_range("A2:H2", f"Generated: {timestamp}", fmt["subtitle"])

        deviation_pct = (
            abs(result.isp_m_s - reference.isp_m_s) / reference.isp_m_s * 100
            if reference.isp_m_s else 0.0)
        if deviation_pct < 1.0:
            status_fmt, status_text = fmt["green"], "✓ Data Valid"
        elif deviation_pct < 5.0:
            status_fmt, status_text = fmt["yellow"], "⚠ Check Errors"
        else:
            status_fmt, status_text = fmt["red"], "⚠ Check Errors"
        sheet.merge_range("A3:H3", status_text, status_fmt)
        sheet.set_row(2, 22)

        cards = [
            ("Specific Impulse (Isp)", f"{result.isp_m_s:,.1f} m/s | {result.isp_vacuum_s:,.2f} s"),
            ("Thrust Coefficient (Cf)", f"{result.cf:.4f} (sea) | {result.cf_vacuum:.4f} (vac)"),
            ("Characteristic Velocity (C*)", f"{result.cstar_m_s:,.1f} m/s"),
            ("Chamber Temperature (Tc)", f"{result.t_chamber_k:,.0f} K"),
            ("Chamber Pressure (Pc)", f"{result.p_chamber_bar:,.2f} bar"),
            ("Exit Pressure (Pe)", f"{result.p_exit_bar:,.4f} bar"),
            ("Area Ratio (Ae/At)", f"{result.area_ratio:.2f}"),
            ("O/F Ratio (wt%)", f"{formulation.oxidizer_weight_pct:.1f} / {formulation.fuel_weight_pct:.1f}"),
        ]
        row = 4
        col = 0
        for title, value in cards:
            sheet.merge_range(row, col, row, col + 1, title, fmt["card_title"])
            sheet.merge_range(row + 1, col, row + 1, col + 1, value, fmt["card_value"])
            col += 2
            if col >= 8:
                col = 0
                row += 3
        sheet.set_row(4, 22)

        summary_row = row + 3 if col == 0 else row + 3
        sheet.merge_range(
            summary_row, 0, summary_row, 7,
            f"{formulation.oxidizer_name} / {formulation.fuel_name} propellant at "
            f"{result.p_chamber_bar:.1f} bar, Ae/At = {result.area_ratio:.1f}",
            fmt["subtitle"])
        sheet.merge_range(
            summary_row + 1, 0, summary_row + 1, 7,
            f"Validation reference: {reference.label} "
            f"(Isp deviation: {deviation_pct:.2f}%)",
            fmt["subtitle"])

        for c in range(8):
            sheet.set_column(c, c, 16)

    # ── Sheet 2: Performance Parameters ────────────────────────────────
    def _write_performance_parameters(
            self, writer, fmt, result: CEAResult, formulation: Formulation,
            reference: ReferenceEngine, propellant_key: str) -> None:
        of_actual = (formulation.oxidizer_weight_pct / formulation.fuel_weight_pct
                    if formulation.fuel_weight_pct else 0.0)
        equivalence_ratio = (
            reference.stoich_of_ratio / of_actual
            if reference.stoich_of_ratio and of_actual else None)
        density = _BULK_DENSITY.get(propellant_key, _BULK_DENSITY["default"])
        density_impulse = result.isp_vacuum_s * density

        # (parameter, value, unit, literature_value_or_None, source)
        rows: List[Tuple[str, Optional[float], str, Optional[float]]] = [
            ("Isp (vacuum)", result.isp_m_s, "m/s", reference.isp_m_s),
            ("Isp (vacuum)", result.isp_vacuum_s, "s", reference.isp_s),
            ("Thrust Coefficient Cf", result.cf, "—", reference.cf),
            ("Thrust Coefficient Cf (vac)", result.cf_vacuum, "—", None),
            ("Characteristic Velocity C*", result.cstar_m_s, "m/s", None),
            ("Chamber Temperature Tc", result.t_chamber_k, "K", reference.t_chamber_k),
            ("Throat Temperature Tt", result.t_throat_k, "K", None),
            ("Exit Temperature Te", result.t_exit_k, "K", None),
            ("Chamber Pressure Pc", result.p_chamber_bar, "bar", reference.p_chamber_bar),
            ("Exit Pressure Pe", result.p_exit_bar, "bar", reference.p_exit_bar),
            ("Area Ratio Ae/At", result.area_ratio, "—", None),
            ("Exit Mach Number", result.mach_exit, "—", None),
            ("Molecular Weight", result.molecular_weight, "g/mol", None),
            ("Gamma γ", result.gamma, "—", None),
            ("O/F Ratio (wt%)", of_actual, "—", None),
            ("Equivalence Ratio φ", equivalence_ratio, "—", None),
            ("Density Impulse (Isp×ρ)", density_impulse, "s·kg/m³", None),
            ("C* Efficiency (ideal)", 100.0, "%", None),
            ("Isp Efficiency (ideal)", 100.0, "%", None),
        ]

        records = []
        for label, value, unit, literature in rows:
            if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
                records.append({"Parameter": label, "Value": None, "Unit": unit,
                               "Literature Value": literature, "Deviation (%)": None,
                               "Status": "N/A"})
                continue
            rounded_value, _ = _round_sig_figs(float(value))
            if literature:
                deviation = abs(rounded_value - literature) / literature * 100
                status = ("PASS" if deviation < 1 else
                          "CHECK" if deviation < 5 else "FAIL")
            else:
                deviation = None
                status = "—"
            records.append({"Parameter": label, "Value": rounded_value, "Unit": unit,
                           "Literature Value": literature,
                           "Deviation (%)": round(deviation, 2) if deviation is not None else None,
                           "Status": status})

        df = pd.DataFrame(records)
        sheet_name = "Performance Parameters"
        df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)
        sheet = writer.sheets[sheet_name]
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.freeze_panes(1, 0)

        for col_idx, col_name in enumerate(df.columns):
            sheet.write(0, col_idx, col_name, fmt["header"])

        for row_idx, record in enumerate(records, start=1):
            is_alt = row_idx % 2 == 0
            cell_fmt = fmt["cell_alt"] if is_alt else fmt["cell"]
            label_fmt = fmt["label_alt"] if is_alt else fmt["label"]
            sheet.write(row_idx, 0, record["Parameter"], label_fmt)
            if record["Value"] is None:
                sheet.write(row_idx, 1, "N/A", fmt["na"])
            else:
                sheet.write_number(row_idx, 1, record["Value"], cell_fmt)
            sheet.write(row_idx, 2, record["Unit"], cell_fmt)
            sheet.write(row_idx, 3,
                       record["Literature Value"] if record["Literature Value"] else "N/A",
                       cell_fmt if record["Literature Value"] else fmt["na"])
            sheet.write(row_idx, 4,
                       record["Deviation (%)"] if record["Deviation (%)"] is not None else "—",
                       cell_fmt)
            status_fmt = (fmt["green"] if record["Status"] == "PASS" else
                         fmt["yellow"] if record["Status"] == "CHECK" else
                         fmt["red"] if record["Status"] == "FAIL" else cell_fmt)
            sheet.write(row_idx, 5, record["Status"], status_fmt)

        sheet.add_table(0, 0, len(records), 5, {
            "columns": [{"header": c} for c in df.columns],
            "style": "Table Style Medium 9", "header_row": True})
        sheet.set_column(0, 0, 26)
        sheet.set_column(1, 1, 14)
        sheet.set_column(2, 2, 12)
        sheet.set_column(3, 3, 16)
        sheet.set_column(4, 4, 14)
        sheet.set_column(5, 5, 10)

    # ── Sheet 3: Exit Composition ───────────────────────────────────────
    def _write_exit_composition(self, writer, fmt, result: CEAResult) -> None:
        sheet_name = "Exit Composition"
        mass_fractions = result.mass_fractions or {}

        if not mass_fractions:
            df = pd.DataFrame([{"Species": "No species data available", "Mass Fraction": "N/A"}])
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            sheet = writer.sheets[sheet_name]
            sheet.write(2, 0, "Run with FCEA2 configured (Auto/FCEA2 Only engine "
                              "mode) to populate exit composition.", fmt["note"])
            return

        mole_raw: Dict[str, Optional[float]] = {}
        for species, mass_frac in mass_fractions.items():
            mw = molecular_weight(species)
            mole_raw[species] = (mass_frac / mw) if mw else None
        mole_total = sum(v for v in mole_raw.values() if v is not None) or 1.0

        records = []
        for species, mass_frac in sorted(mass_fractions.items(), key=lambda x: -x[1]):
            mw = molecular_weight(species)
            mole_frac = (mole_raw[species] / mole_total) if mole_raw[species] is not None else None
            records.append({
                "Species": species,
                "Mass Fraction": round(mass_frac, 6),
                "Mass %": round(mass_frac * 100, 2),
                "Mole Fraction": round(mole_frac, 6) if mole_frac is not None else None,
                "Mole %": round(mole_frac * 100, 2) if mole_frac is not None else None,
                "Molecular Weight (g/mol)": round(mw, 3) if mw else None,
            })

        df = pd.DataFrame(records)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet = writer.sheets[sheet_name]
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.freeze_panes(1, 0)

        for col_idx, col_name in enumerate(df.columns):
            sheet.write(0, col_idx, col_name, fmt["header"])
        for row_idx, record in enumerate(records, start=1):
            is_alt = row_idx % 2 == 0
            cell_fmt = fmt["cell_alt"] if is_alt else fmt["cell"]
            sheet.write(row_idx, 0, record["Species"], cell_fmt)
            sheet.write_number(row_idx, 1, record["Mass Fraction"], cell_fmt)
            sheet.write_number(row_idx, 2, record["Mass %"], cell_fmt)
            for col, key in [(3, "Mole Fraction"), (4, "Mole %"), (5, "Molecular Weight (g/mol)")]:
                value = record[key]
                if value is None:
                    sheet.write(row_idx, col, "N/A", fmt["na"])
                else:
                    sheet.write_number(row_idx, col, value, cell_fmt)

        last_row = len(records)
        sheet.add_table(0, 0, last_row, 5, {
            "columns": [{"header": c} for c in df.columns],
            "style": "Table Style Medium 9"})
        sheet.set_column(0, 0, 16)
        for c in range(1, 6):
            sheet.set_column(c, c, 16)

        if result.method.startswith("Fallback"):
            sheet.write(last_row + 2, 0,
                       "⚠ Representative values for this propellant class — "
                       "not a chemical-equilibrium calculation.", fmt["note"])
        else:
            sheet.write(last_row + 2, 0,
                       "✓ Computed by FCEA2 chemical equilibrium.", fmt["cell"])

        chart = writer.book.add_chart({"type": "column"})
        chart.add_series({
            "name": "Mass %",
            "categories": [sheet_name, 1, 0, last_row, 0],
            "values": [sheet_name, 1, 2, last_row, 2],
        })
        chart.add_series({
            "name": "Mole %",
            "categories": [sheet_name, 1, 0, last_row, 0],
            "values": [sheet_name, 1, 4, last_row, 4],
        })
        chart.set_title({"name": "Exit Composition — Mass % vs Mole %"})
        chart.set_x_axis({"name": "Species"})
        chart.set_y_axis({"name": "Percent (%)"})
        chart.set_size({"width": 640, "height": 380})
        sheet.insert_chart(1, 7, chart)

    # ── Sheet 4: Expansion Data (For Graphing) ──────────────────────────
    def _write_expansion_data(self, writer, fmt, result: CEAResult) -> None:
        sheet_name = "Expansion Data"
        gamma = result.gamma or 1.22
        t_chamber = result.t_chamber_k or 3200.0
        p_chamber = result.p_chamber_bar or 50.0
        cstar = result.cstar_m_s or 1750.0

        area_ratios = [round(1.0 + 0.5 * i, 1) for i in range(int((20.0 - 1.0) / 0.5) + 1)]
        records = []
        for ar in area_ratios:
            # Newton-Raphson solve (this app's own validated solver) —
            # mathematically equivalent to scipy.optimize.fsolve on the
            # same A/A* = f(M, γ) equation, with no extra dependency.
            mach = IsentropicFlow.mach_from_area_ratio(ar, gamma)
            t_ratio = IsentropicFlow.temperature_ratio(mach, gamma)
            p_ratio = IsentropicFlow.pressure_ratio(mach, gamma)
            t_exit = t_chamber * t_ratio
            p_exit = p_chamber * p_ratio
            pe_pc = p_exit / max(p_chamber, 1e-9)
            cf = IsentropicFlow.thrust_coefficient(gamma, pe_pc, ar)
            isp_ms = cstar * cf
            isp_s = isp_ms / G0
            records.append({
                "Area Ratio": ar, "Mach": round(mach, 4),
                "P/Pc": round(p_ratio, 4), "T/Tc": round(t_ratio, 4),
                "P_exit (bar)": round(p_exit, 2), "T_exit (K)": round(t_exit, 2),
                "Isp (m/s)": round(isp_ms, 1), "Isp (s)": round(isp_s, 2),
                "Cf": round(cf, 4),
            })

        df = pd.DataFrame(records)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet = writer.sheets[sheet_name]
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.freeze_panes(1, 0)

        for col_idx, col_name in enumerate(df.columns):
            sheet.write(0, col_idx, col_name, fmt["header"])
        for row_idx, record in enumerate(records, start=1):
            is_alt = row_idx % 2 == 0
            cell_fmt = fmt["cell_alt"] if is_alt else fmt["cell"]
            for col_idx, col_name in enumerate(df.columns):
                sheet.write_number(row_idx, col_idx, record[col_name], cell_fmt)

        last_row = len(records)
        sheet.add_table(0, 0, last_row, len(df.columns) - 1, {
            "columns": [{"header": c} for c in df.columns],
            "style": "Table Style Medium 9"})
        sheet.set_column(0, len(df.columns) - 1, 13)
        sheet.write(last_row + 2, 0,
                   "Mach solved via Newton-Raphson on A/A* = f(M,γ) — "
                   "mathematically equivalent to scipy.optimize.fsolve "
                   "on the same equation.", fmt["note"])

        isp_chart = writer.book.add_chart({"type": "scatter", "subtype": "smooth"})
        isp_chart.add_series({
            "name": "Isp vs Area Ratio",
            "categories": [sheet_name, 1, 0, last_row, 0],
            "values": [sheet_name, 1, 6, last_row, 6],
        })
        isp_chart.set_title({"name": "Isp vs Area Ratio"})
        isp_chart.set_x_axis({"name": "Area Ratio Ae/At"})
        isp_chart.set_y_axis({"name": "Isp (m/s)"})
        isp_chart.set_size({"width": 480, "height": 320})
        sheet.insert_chart(1, len(df.columns) + 1, isp_chart)

        cf_chart = writer.book.add_chart({"type": "scatter", "subtype": "smooth"})
        cf_chart.add_series({
            "name": "Cf vs Area Ratio",
            "categories": [sheet_name, 1, 0, last_row, 0],
            "values": [sheet_name, 1, 8, last_row, 8],
        })
        cf_chart.set_title({"name": "Cf vs Area Ratio"})
        cf_chart.set_x_axis({"name": "Area Ratio Ae/At"})
        cf_chart.set_y_axis({"name": "Thrust Coefficient Cf"})
        cf_chart.set_size({"width": 480, "height": 320})
        sheet.insert_chart(18, len(df.columns) + 1, cf_chart)

    # ── Sheet 5: Thermodynamic Properties ───────────────────────────────
    def _write_thermodynamic_properties(self, writer, fmt, result: CEAResult) -> None:
        sheet_name = "Thermodynamic Properties"
        gamma = result.gamma or 1.22
        mw = result.molecular_weight or 22.0
        r_specific = 8314.0 / mw

        def sonic(t: float) -> float:
            return math.sqrt(gamma * r_specific * t) if t > 0 else 0.0

        def cp(g: float) -> float:
            return g * r_specific / (g - 1.0) if g != 1.0 else 0.0

        stations = [
            {"Station": 1, "Location": "Chamber", "T (K)": result.t_chamber_k,
             "P (bar)": result.p_chamber_bar, "Mach": 0.0},
            {"Station": 2, "Location": "Throat", "T (K)": result.t_throat_k,
             "P (bar)": result.p_throat_bar, "Mach": 1.0},
            {"Station": 3, "Location": "Exit", "T (K)": result.t_exit_k,
             "P (bar)": result.p_exit_bar, "Mach": result.mach_exit},
        ]
        records = []
        for s in stations:
            sonic_v = sonic(s["T (K)"])
            velocity = s["Mach"] * sonic_v
            records.append({
                "Station": s["Station"], "Location": s["Location"],
                "T (K)": round(s["T (K)"], 2), "P (bar)": round(s["P (bar)"], 4),
                "Mach": round(s["Mach"], 4), "Velocity (m/s)": round(velocity, 2),
                "Gamma": round(gamma, 4), "Cp (J/kg·K)": round(cp(gamma), 2),
                "Sonic Velocity (m/s)": round(sonic_v, 2),
            })

        df = pd.DataFrame(records)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet = writer.sheets[sheet_name]
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.freeze_panes(1, 0)

        for col_idx, col_name in enumerate(df.columns):
            sheet.write(0, col_idx, col_name, fmt["header"])
        for row_idx, record in enumerate(records, start=1):
            is_alt = row_idx % 2 == 0
            cell_fmt = fmt["cell_alt"] if is_alt else fmt["cell"]
            for col_idx, col_name in enumerate(df.columns):
                value = record[col_name]
                if isinstance(value, str):
                    sheet.write(row_idx, col_idx, value, cell_fmt)
                else:
                    sheet.write_number(row_idx, col_idx, value, cell_fmt)

        last_row = len(records)
        sheet.add_table(0, 0, last_row, len(df.columns) - 1, {
            "columns": [{"header": c} for c in df.columns],
            "style": "Table Style Medium 9"})
        sheet.set_column(0, len(df.columns) - 1, 16)

        t_chart = writer.book.add_chart({"type": "line"})
        t_chart.add_series({
            "name": "Temperature (K)",
            "categories": [sheet_name, 1, 1, last_row, 1],
            "values": [sheet_name, 1, 2, last_row, 2],
        })
        t_chart.set_title({"name": "Temperature vs Station"})
        t_chart.set_x_axis({"name": "Station"})
        t_chart.set_y_axis({"name": "Temperature (K)"})
        t_chart.set_size({"width": 480, "height": 320})
        sheet.insert_chart(1, len(df.columns) + 1, t_chart)

        p_chart = writer.book.add_chart({"type": "line"})
        p_chart.add_series({
            "name": "Pressure (bar)",
            "categories": [sheet_name, 1, 1, last_row, 1],
            "values": [sheet_name, 1, 3, last_row, 3],
        })
        p_chart.set_title({"name": "Pressure vs Station"})
        p_chart.set_x_axis({"name": "Station"})
        p_chart.set_y_axis({"name": "Pressure (bar)"})
        p_chart.set_size({"width": 480, "height": 320})
        sheet.insert_chart(18, len(df.columns) + 1, p_chart)

    # ── Sheet 6: Sensitivity Analysis ───────────────────────────────────
    def _write_sensitivity_analysis(
            self, writer, fmt, result: CEAResult, formulation: Formulation,
            all_sessions: List[SessionRecord]) -> None:
        sheet_name = "Sensitivity Analysis"
        of_actual = (formulation.oxidizer_weight_pct / formulation.fuel_weight_pct
                    if formulation.fuel_weight_pct else 0.0)

        # Auto-populate from any OTHER successful sessions sharing this
        # exact oxidizer/fuel pair — a value-add beyond a placeholder,
        # using real data already in the app instead of asking the user
        # to re-enter it.
        matching = [
            sr for sr in all_sessions
            if sr.result.success
            and sr.formulation.oxidizer_name == formulation.oxidizer_name
            and sr.formulation.fuel_name == formulation.fuel_name
        ]
        auto_populated = len(matching) > 1

        if auto_populated:
            records = []
            for sr in sorted(matching, key=lambda s: (
                    s.formulation.oxidizer_weight_pct / s.formulation.fuel_weight_pct
                    if s.formulation.fuel_weight_pct else 0.0)):
                of_ratio = (sr.formulation.oxidizer_weight_pct / sr.formulation.fuel_weight_pct
                           if sr.formulation.fuel_weight_pct else 0.0)
                records.append({
                    "O/F Ratio": round(of_ratio, 3),
                    "Isp (s)": round(sr.result.isp_vacuum_s, 2),
                    "Isp (m/s)": round(sr.result.isp_m_s, 1),
                    "Cf": round(sr.result.cf, 4),
                    "C* (m/s)": round(sr.result.cstar_m_s, 1),
                    "Tc (K)": round(sr.result.t_chamber_k, 1),
                })
        else:
            records = [{
                "O/F Ratio": round(of_actual, 3),
                "Isp (s)": round(result.isp_vacuum_s, 2),
                "Isp (m/s)": round(result.isp_m_s, 1),
                "Cf": round(result.cf, 4),
                "C* (m/s)": round(result.cstar_m_s, 1),
                "Tc (K)": round(result.t_chamber_k, 1),
            }]

        df = pd.DataFrame(records)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet = writer.sheets[sheet_name]
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.freeze_panes(1, 0)

        for col_idx, col_name in enumerate(df.columns):
            sheet.write(0, col_idx, col_name, fmt["header"])
        for row_idx, record in enumerate(records, start=1):
            is_alt = row_idx % 2 == 0
            cell_fmt = fmt["cell_alt"] if is_alt else fmt["cell"]
            for col_idx, col_name in enumerate(df.columns):
                sheet.write_number(row_idx, col_idx, record[col_name], cell_fmt)

        last_row = len(records)
        sheet.add_table(0, 0, last_row, len(df.columns) - 1, {
            "columns": [{"header": c} for c in df.columns],
            "style": "Table Style Medium 9"})
        sheet.set_column(0, len(df.columns) - 1, 14)

        note_row = last_row + 2
        if auto_populated:
            sheet.write(note_row, 0,
                       f"✓ Auto-populated from {len(matching)} sessions in this "
                       "app sharing this oxidizer/fuel pair.", fmt["cell"])
        else:
            sheet.write(note_row, 0,
                       "Run multiple CEA sessions at different O/F ratios "
                       "(same oxidizer/fuel pair) to auto-populate this table.",
                       fmt["note"])

        if last_row >= 2:
            chart = writer.book.add_chart({"type": "scatter", "subtype": "straight_with_markers"})
            chart.add_series({
                "name": "Isp vs O/F",
                "categories": [sheet_name, 1, 0, last_row, 0],
                "values": [sheet_name, 1, 1, last_row, 1],
            })
            chart.set_title({"name": "Isp vs O/F Ratio"})
            chart.set_x_axis({"name": "O/F Ratio"})
            chart.set_y_axis({"name": "Isp (s)"})
            chart.set_size({"width": 520, "height": 340})
            sheet.insert_chart(1, len(df.columns) + 1, chart)
        else:
            sheet.write(1, len(df.columns) + 1,
                       "(Plot will appear once 2+ sessions with this "
                       "propellant pair exist)", fmt["note"])

    # ── Sheet 7: Session Metadata ───────────────────────────────────────
    def _write_session_metadata(self, workbook, fmt, result: CEAResult,
                                formulation: Formulation, software_version: str) -> None:
        sheet = workbook.add_worksheet("Session Metadata")
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.merge_range("A1:C1", "Session Metadata", fmt["section"])
        sheet.set_row(0, 22)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            ("Software", f"CEA Calculator Pro v{software_version}"),
            ("Method", result.method),
            ("Export Date/Time", timestamp),
            ("Propellant", f"{formulation.oxidizer_name} / {formulation.fuel_name}"),
            ("Oxidizer", f"{formulation.oxidizer_name} at "
                        f"{formulation.oxidizer_temperature_k:.1f} K, "
                        f"{formulation.oxidizer_weight_pct:.1f} wt%"),
            ("Fuel", f"{formulation.fuel_name} at "
                    f"{formulation.fuel_temperature_k:.1f} K, "
                    f"{formulation.fuel_weight_pct:.1f} wt%"),
            ("Chamber Pressure", f"{formulation.chamber_pressure_bar:.2f} bar"),
            ("Area Ratio", f"{formulation.area_ratio:.2f}"),
            ("Convergence Criteria", "N/A" if result.method.startswith("Fallback")
                                    else "Per FCEA2 default tolerances"),
            ("Reference Source", "NASA CEA / published historical engine specs"),
            ("User Comments", ""),
            ("Limitations", "Representative composition, ideal-rocket assumption"
                            if result.method.startswith("Fallback")
                            else "Chemical-equilibrium CEA output"),
        ]
        for i, (label, value) in enumerate(rows, start=2):
            is_alt = i % 2 == 0
            sheet.write(i, 0, label, fmt["label_alt"] if is_alt else fmt["label"])
            sheet.write(i, 1, value if value else "(blank for annotations)",
                       fmt["cell_alt"] if is_alt else fmt["cell"])
        sheet.set_column(0, 0, 22)
        sheet.set_column(1, 1, 55)

    # ── Sheet 8: Validation & References ────────────────────────────────
    def _write_validation_references(
            self, writer, fmt, result: CEAResult, formulation: Formulation,
            reference: ReferenceEngine) -> None:
        sheet_name = "Validation & References"

        def pct_diff(actual: float, lit: float) -> float:
            return abs(actual - lit) / lit * 100 if lit else 0.0

        rows = [
            ("Isp (s)", result.isp_vacuum_s, reference.isp_s, reference.source),
            ("Isp (m/s)", result.isp_m_s, reference.isp_m_s, reference.source),
            ("Tc (K)", result.t_chamber_k, reference.t_chamber_k, "NASA SP-8100"
             if reference.label == "Saturn V F-1" else reference.source),
            ("Pc (bar)", result.p_chamber_bar, reference.p_chamber_bar, reference.source),
            ("Pe (bar)", result.p_exit_bar, reference.p_exit_bar, "Calculated"),
            ("Cf", result.cf, reference.cf, "Ideal Rocket"),
        ]
        records = []
        all_pass = True
        for label, actual, literature, source in rows:
            diff = pct_diff(actual, literature)
            if diff > 5.0:
                all_pass = False
            records.append({
                "Parameter": label, "CEA Output": round(actual, 4),
                "Literature Value": literature, "Source": source,
                "% Difference": round(diff, 2),
            })

        df = pd.DataFrame(records)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet = writer.sheets[sheet_name]
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.freeze_panes(1, 0)

        for col_idx, col_name in enumerate(df.columns):
            sheet.write(0, col_idx, col_name, fmt["header"])
        for row_idx, record in enumerate(records, start=1):
            is_alt = row_idx % 2 == 0
            cell_fmt = fmt["cell_alt"] if is_alt else fmt["cell"]
            sheet.write(row_idx, 0, record["Parameter"], cell_fmt)
            sheet.write_number(row_idx, 1, record["CEA Output"], cell_fmt)
            sheet.write_number(row_idx, 2, record["Literature Value"], cell_fmt)
            sheet.write(row_idx, 3, record["Source"], cell_fmt)
            diff_fmt = (fmt["green"] if record["% Difference"] < 1 else
                       fmt["yellow"] if record["% Difference"] < 5 else fmt["red"])
            sheet.write_number(row_idx, 4, record["% Difference"], diff_fmt)

        last_row = len(records)
        sheet.add_table(0, 0, last_row, 4, {
            "columns": [{"header": c} for c in df.columns],
            "style": "Table Style Medium 9"})
        sheet.set_column(0, 0, 16)
        sheet.set_column(1, 2, 16)
        sheet.set_column(3, 3, 22)
        sheet.set_column(4, 4, 14)

        status_text = ("✓ Verification Status: PASS (all within 5%)" if all_pass
                       else "⚠ Verification Status: FAIL (one or more parameters "
                            "exceed 5% deviation)")
        status_fmt = fmt["green"] if all_pass else fmt["red"]
        sheet.merge_range(last_row + 2, 0, last_row + 2, 4, status_text, status_fmt)
        sheet.write(last_row + 4, 0,
                   f"Reference engine: {reference.label}  ({reference.source})",
                   fmt["subtitle"])
