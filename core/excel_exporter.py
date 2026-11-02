"""
core/excel_exporter.py
=========================
Builds a professionally formatted ``.xlsx`` workbook from one or more
session results: a Summary sheet comparing all sessions side-by-side,
plus one sheet per session containing its embedded performance
dashboard image and styled data tables.

Pure I/O/formatting logic — takes already-rendered PNG bytes (built by
the UI layer, which owns matplotlib) and already-computed result data
(built by the Logic layer) and writes them out. No chart-drawing code
lives here.
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from models.cea_result import CEAResult

log = logging.getLogger(__name__)

# ── Style constants — single source of truth for the whole workbook ────
_HEADER_FILL = PatternFill(start_color="3F51B5", end_color="3F51B5", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11, name="Calibri")
_TITLE_FONT = Font(color="1A237E", bold=True, size=14, name="Calibri")
_SUBTITLE_FONT = Font(color="616161", italic=True, size=10, name="Calibri")
_BEST_FILL = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
_BEST_FONT = Font(color="2E7D32", bold=True, size=10, name="Calibri")
_VALUE_FONT = Font(color="1A237E", bold=True, size=10, name="Calibri")
_LABEL_FONT = Font(color="212121", bold=True, size=10, name="Calibri")
_NOTE_FONT = Font(color="E65100", italic=True, size=9, name="Calibri")
_NORMAL_FONT = Font(color="212121", size=10, name="Calibri")
_ALT_ROW_FILL = PatternFill(start_color="F3F4FC", end_color="F3F4FC", fill_type="solid")
_THIN_BORDER = Border(*([Side(style="thin", color="C5CAE9")] * 4))


@dataclass
class SessionExport:
    """One session's data, ready to be written to its own worksheet."""

    name: str
    result: CEAResult
    units: Dict[str, str]
    dashboard_png: Optional[bytes] = None


class ExcelExporter:
    """Writes one or more :class:`SessionExport` records to a styled workbook."""

    def export(self, sessions: List[SessionExport], path: str) -> None:
        """
        Write the full workbook to ``path``.

        Args:
            sessions: One entry per session to include.
            path: Destination ``.xlsx`` file path.
        """
        workbook = Workbook()
        summary_sheet = workbook.active
        summary_sheet.title = "Summary"
        self._write_summary_sheet(summary_sheet, sessions)

        for session in sessions:
            sheet_name = self._safe_sheet_name(session.name, workbook)
            sheet = workbook.create_sheet(sheet_name)
            self._write_session_sheet(sheet, session)

        workbook.save(path)
        log.info("Excel workbook saved: %s (%d session sheet(s))",
                 path, len(sessions))

    # ── Summary sheet ───────────────────────────────────────────────
    def _write_summary_sheet(self, sheet: Worksheet,
                             sessions: List[SessionExport]) -> None:
        sheet["A1"] = "CEA Calculator Pro — Session Comparison"
        sheet["A1"].font = _TITLE_FONT
        sheet.merge_cells("A1:E1")
        sheet["A2"] = f"{len(sessions)} session(s) exported"
        sheet["A2"].font = _SUBTITLE_FONT
        sheet.row_dimensions[1].height = 24

        params = [
            ("Isp (m/s)", lambda r: r.isp_m_s, "{:.1f}", True),
            ("Isp (s)", lambda r: r.isp_vacuum_s, "{:.2f}", True),
            ("C* (m/s)", lambda r: r.cstar_m_s, "{:.1f}", True),
            ("Cf", lambda r: r.cf, "{:.4f}", True),
            ("Area Ratio Ae/At", lambda r: r.area_ratio, "{:.2f}", False),
            ("Chamber Temp Tc (K)", lambda r: r.t_chamber_k, "{:.0f}", False),
            ("Molecular Weight (g/mol)", lambda r: r.molecular_weight, "{:.3f}", False),
            ("Gamma γ", lambda r: r.gamma, "{:.4f}", False),
            ("Method", lambda r: r.method, "{}", False),
        ]

        header_row = 4
        sheet.cell(row=header_row, column=1, value="Parameter")
        for col, session in enumerate(sessions, start=2):
            sheet.cell(row=header_row, column=col, value=session.name)
        for col in range(1, len(sessions) + 2):
            cell = sheet.cell(row=header_row, column=col)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = _THIN_BORDER

        for row_offset, (label, extractor, fmt, higher_is_better) in enumerate(params):
            row = header_row + 1 + row_offset
            sheet.cell(row=row, column=1, value=label).font = _LABEL_FONT
            sheet.cell(row=row, column=1).border = _THIN_BORDER

            numeric_values = []
            for session in sessions:
                try:
                    numeric_values.append(float(extractor(session.result)))
                except (TypeError, ValueError):
                    numeric_values.append(None)
            comparable = [v for v in numeric_values if v is not None]
            best_value = (max(comparable) if higher_is_better and comparable
                         else min(comparable) if comparable else None)

            for col, (session, value) in enumerate(
                    zip(sessions, numeric_values), start=2):
                try:
                    text = fmt.format(extractor(session.result))
                except (TypeError, ValueError):
                    text = "—"
                cell = sheet.cell(row=row, column=col, value=text)
                cell.border = _THIN_BORDER
                cell.alignment = Alignment(horizontal="center")
                is_best = (value is not None and best_value is not None
                          and abs(value - best_value) < 1e-9 and len(sessions) > 1)
                if is_best:
                    cell.font = _BEST_FONT
                    cell.fill = _BEST_FILL
                else:
                    cell.font = _NORMAL_FONT
                    if row_offset % 2 == 1:
                        cell.fill = _ALT_ROW_FILL

        self._autosize_columns(sheet, len(sessions) + 1)

    # ── Per-session sheet ─────────────────────────────────────────────
    def _write_session_sheet(self, sheet: Worksheet,
                             session: SessionExport) -> None:
        sheet["A1"] = session.name
        sheet["A1"].font = _TITLE_FONT
        sheet.merge_cells("A1:D1")
        sheet["A2"] = f"Method: {session.result.method}"
        sheet["A2"].font = _SUBTITLE_FONT
        sheet.row_dimensions[1].height = 24

        next_row = 4
        if session.dashboard_png:
            try:
                image = XLImage(io.BytesIO(session.dashboard_png))
                image.width = 720
                image.height = 500
                sheet.add_image(image, f"A{next_row}")
                next_row += 28  # leave room below the embedded image
            except Exception as exc:
                log.warning("Could not embed dashboard image: %s", exc)
                sheet.cell(row=next_row, column=1,
                          value="(Plot image could not be embedded)").font = _NOTE_FONT
                next_row += 2

        next_row = self._write_performance_table(sheet, session, next_row)
        next_row += 2
        self._write_species_table(sheet, session, next_row)
        self._autosize_columns(sheet, 3)

    def _write_performance_table(self, sheet: Worksheet,
                                 session: SessionExport, start_row: int) -> int:
        sheet.cell(row=start_row, column=1, value="Performance Summary").font = _TITLE_FONT
        header_row = start_row + 1
        for col, label in enumerate(["Parameter", "Value", "Unit"], start=1):
            cell = sheet.cell(row=header_row, column=col, value=label)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
            cell.border = _THIN_BORDER

        rows = session.result.to_table_rows(session.units)
        for i, row_data in enumerate(rows):
            row = header_row + 1 + i
            param, value, unit = row_data[0], row_data[1], row_data[2]
            note_color = row_data[4] if len(row_data) > 4 else None
            cells = [
                sheet.cell(row=row, column=1, value=param),
                sheet.cell(row=row, column=2, value=value),
                sheet.cell(row=row, column=3, value=unit),
            ]
            cells[0].font = _LABEL_FONT
            cells[1].font = _VALUE_FONT
            cells[2].font = _NORMAL_FONT
            for cell in cells:
                cell.border = _THIN_BORDER
                if i % 2 == 1:
                    cell.fill = _ALT_ROW_FILL
            cells[1].alignment = Alignment(horizontal="right")
        return header_row + len(rows)

    def _write_species_table(self, sheet: Worksheet,
                             session: SessionExport, start_row: int) -> int:
        if not session.result.mass_fractions:
            return start_row
        sheet.cell(row=start_row, column=1,
                  value="Exit Plane Composition").font = _TITLE_FONT
        if session.result.method.startswith("Fallback"):
            note_row = start_row + 1
            sheet.cell(row=note_row, column=1,
                      value="⚠ Representative values for this propellant "
                           "class — not a chemical-equilibrium calculation."
                      ).font = _NOTE_FONT
            header_row = note_row + 1
        else:
            header_row = start_row + 1

        for col, label in enumerate(["Species", "Mass Fraction", "%"], start=1):
            cell = sheet.cell(row=header_row, column=col, value=label)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
            cell.border = _THIN_BORDER

        sorted_species = sorted(
            session.result.mass_fractions.items(), key=lambda x: -x[1])
        for i, (species, fraction) in enumerate(sorted_species):
            row = header_row + 1 + i
            cells = [
                sheet.cell(row=row, column=1, value=species),
                sheet.cell(row=row, column=2, value=round(fraction, 6)),
                sheet.cell(row=row, column=3, value=f"{fraction * 100:.2f}%"),
            ]
            cells[0].font = _LABEL_FONT
            cells[1].font = _NORMAL_FONT
            cells[2].font = _VALUE_FONT
            for cell in cells:
                cell.border = _THIN_BORDER
                if i % 2 == 1:
                    cell.fill = _ALT_ROW_FILL
        return header_row + len(sorted_species)

    # ── Helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _safe_sheet_name(name: str, workbook: Workbook) -> str:
        """Sanitize and de-duplicate a session name for use as a sheet title."""
        cleaned = re.sub(r"[\\/*?:\[\]]", "_", name).strip() or "Session"
        cleaned = cleaned[:28]
        candidate = cleaned
        suffix = 2
        existing = {s.title for s in workbook.worksheets}
        while candidate in existing or candidate == "Summary":
            candidate = f"{cleaned[:25]}_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _autosize_columns(sheet: Worksheet, max_col_index: int) -> None:
        """Set reasonable column widths based on the longest cell in each column."""
        for col_idx in range(1, max_col_index + 1):
            letter = get_column_letter(col_idx)
            longest = 10
            for cell in sheet[letter]:
                if cell.value is not None:
                    longest = max(longest, len(str(cell.value)))
            sheet.column_dimensions[letter].width = min(longest + 4, 45)
