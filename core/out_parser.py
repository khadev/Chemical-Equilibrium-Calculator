"""
core/out_parser.py
====================
Parses NASA CEA ``.out`` output files via regular expressions.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Optional, Tuple

from core.exceptions import ParseError
from models.cea_result import CEAResult, G0

log = logging.getLogger(__name__)

_HEADER_RE = re.compile(r"THEORETICAL\s+ROCKET\s+PERFORMANCE", re.IGNORECASE)
_FORTRAN_EXP_RE = re.compile(r"(\d)([+\-])(\d)")


class OUTParser:
    """
    Parses FCEA2 ``.out`` text into a :class:`CEAResult`.
    """

    def parse(self, raw_text: str, name: str = "") -> CEAResult:
        """
        Parse raw CEA ``.out`` text.
        """
        result = CEAResult(name=name, raw_output=raw_text, method="CEA")

        if not raw_text or len(raw_text.strip()) < 10:
            raise ParseError(
                "Engine Execution Error: CEA output is empty.")

        header_match = _HEADER_RE.search(raw_text)
        if not header_match:
            preview = raw_text.strip()[:300].replace("\n", "  ")
            raise ParseError(
                "Engine Execution Error: 'THEORETICAL ROCKET PERFORMANCE' "
                f"header not found.\nOutput preview: {preview}")

        section = raw_text[header_match.start():]

        self._parse_temperatures(section, result)
        self._parse_pressures(section, result)
        self._parse_performance_simple(section, result)
        self._parse_gas_properties(section, result)
        self._parse_mass_fractions(raw_text, result)

        result.success = True
        return result

    # ── Float sanitization ────────────────────────────────────────────
    @staticmethod
    def _sanitize_float(token: str) -> Optional[float]:
        """Convert a CEA numeric token to float, handling Fortran notation."""
        if not token:
            return None
        token = token.strip()
        if not token or "*" in token or token in ("-", "—", "N/A", "***"):
            return None
        token = token.replace("D", "E").replace("d", "e")
        token = _FORTRAN_EXP_RE.sub(r"\1E\2\3", token)
        try:
            return float(token)
        except ValueError:
            return None

    def _extract_3col(self, text: str, pattern: str) -> Optional[Tuple[float, float, float]]:
        """Extract a (chamber, throat, exit) triple."""
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        values = []
        for i in range(1, 4):
            val = self._sanitize_float(match.group(i))
            if val is None:
                return None
            values.append(val)
        return values[0], values[1], values[2]

    # ── Section parsers ───────────────────────────────────────────────
    def _parse_temperatures(self, text: str, result: CEAResult) -> None:
        patterns = [
            r"T,\s*K\s+([\d.*E+\-]+)\s+([\d.*E+\-]+)\s+([\d.*E+\-]+)",
            r"T,\s*K\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        ]
        for pattern in patterns:
            values = self._extract_3col(text, pattern)
            if values:
                result.t_chamber_k, result.t_throat_k, result.t_exit_k = values
                return

    def _parse_pressures(self, text: str, result: CEAResult) -> None:
        patterns = [
            r"P,\s*BAR\s+([\d.*E+\-]+)\s+([\d.*E+\-]+)\s+([\d.*E+\-]+)",
            r"P,\s*BAR\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        ]
        for pattern in patterns:
            values = self._extract_3col(text, pattern)
            if values:
                result.p_chamber_bar, result.p_throat_bar, result.p_exit_bar = values
                return

    def _parse_performance_simple(self, text: str, result: CEAResult) -> None:
        """
        Parse performance parameters using simple string matching.
        Extracts BOTH sea level (first column) and vacuum (second column) values.
        """
        # Find the PERFORMANCE PARAMETERS section
        start_idx = text.lower().find("performance parameters")
        if start_idx == -1:
            log.warning("PERFORMANCE PARAMETERS section not found")
            return
        
        # Get the section after PERFORMANCE PARAMETERS
        section = text[start_idx + len("performance parameters"):]
        
        # Split into lines
        lines = section.split('\n')
        
        # Parse line by line
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            
            # ===== Parse Ae/At =====
            if "Ae/At" in line_clean:
                numbers = re.findall(r"[\d.]+", line_clean)
                if len(numbers) >= 2:
                    # Second value is the specified Ae/At
                    val = self._sanitize_float(numbers[1])
                    if val is not None:
                        result.area_ratio = val
                        log.debug(f"Ae/At = {val}")
            
            # ===== Parse C* =====
            if "CSTAR" in line_clean.upper():
                numbers = re.findall(r"[\d.]+", line_clean)
                if numbers:
                    val = self._sanitize_float(numbers[0])
                    if val is not None:
                        result.cstar_m_s = val
                        log.debug(f"C* = {val}")
            
            # ===== Parse CF =====
            if "CF" in line_clean and not "CF," in line_clean and not "VAC" in line_clean.upper():
                numbers = re.findall(r"[\d.]+", line_clean)
                if len(numbers) >= 2:
                    # First = sea level, Second = vacuum at Ae/At
                    val1 = self._sanitize_float(numbers[0])  # Sea level
                    val2 = self._sanitize_float(numbers[1])  # Vacuum at Ae/At
                    if val1 is not None:
                        result.cf_sea_level = val1
                        log.debug(f"CF (sea level) = {val1}")
                    if val2 is not None:
                        result.cf_vacuum = val2
                        log.debug(f"CF (vacuum at Ae/At={result.area_ratio}) = {val2}")
            
            # ===== Parse Ivac =====
            if "Ivac" in line_clean:
                numbers = re.findall(r"[\d.]+", line_clean)
                if len(numbers) >= 2:
                    # First = sea level, Second = vacuum at Ae/At
                    val1 = self._sanitize_float(numbers[0])  # Sea level
                    val2 = self._sanitize_float(numbers[1])  # Vacuum at Ae/At
                    if val1 is not None:
                        result.ivac_sea_level_m_s = val1
                        log.debug(f"Ivac (sea level) = {val1} m/s")
                    if val2 is not None and val2 > 0:
                        result.ivac_m_s = val2
                        log.debug(f"Ivac (vacuum at Ae/At={result.area_ratio}) = {val2} m/s")
            
            # ===== Parse Isp =====
            if "Isp" in line_clean and "," in line_clean:
                numbers = re.findall(r"[\d.]+", line_clean)
                if len(numbers) >= 2:
                    # First = sea level, Second = vacuum at Ae/At
                    val1 = self._sanitize_float(numbers[0])  # Sea level
                    val2 = self._sanitize_float(numbers[1])  # Vacuum at Ae/At
                    if val1 is not None and val1 > 0:
                        result.isp_sea_level_s = val1 / G0
                        log.debug(f"Isp (sea level) = {val1} m/s")
                    if val2 is not None and val2 > 0:
                        result.isp_vacuum_s = val2 / G0
                        log.debug(f"Isp (vacuum at Ae/At={result.area_ratio}) = {val2} m/s")

    def _parse_gas_properties(self, text: str, result: CEAResult) -> None:
        """Parse gas properties from the main output."""
        
        # ===== Parse Gamma =====
        gamma_match = re.search(
            r"GAMMAs\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", 
            text, re.IGNORECASE
        )
        if gamma_match:
            val = self._sanitize_float(gamma_match.group(1))
            if val is not None:
                result.gamma = val
        
        # ===== Parse Molecular Weight =====
        mw_match = re.search(
            r"M,\s*\(1/n\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", 
            text, re.IGNORECASE
        )
        if mw_match:
            val = self._sanitize_float(mw_match.group(1))
            if val is not None:
                result.molecular_weight = val
        
        # ===== Parse Mach number =====
        mach_match = re.search(
            r"MACH NUMBER\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", 
            text, re.IGNORECASE
        )
        if mach_match:
            val = self._sanitize_float(mach_match.group(3))
            if val is not None:
                result.mach_exit = val

    def _parse_mass_fractions(self, full_text: str, result: CEAResult) -> None:
        """Parse the MASS FRACTIONS section."""
        section_match = re.search(
            r"MASS FRACTIONS\s*\n(.*?)(?:\n\s*\n|\Z)",
            full_text, re.DOTALL | re.IGNORECASE
        )
        if not section_match:
            return

        fractions: Dict[str, float] = {}
        for line in section_match.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            
            line = line.replace("*", "").strip()
            tokens = line.split()
            if len(tokens) >= 2:
                species = tokens[0].strip()
                if not species or species in ["PRODUCTS", "CONDITIONS"]:
                    continue
                
                for token in reversed(tokens[1:]):
                    val = self._sanitize_float(token)
                    if val is not None and val > 1e-8:
                        fractions[species] = val
                        break
        
        if fractions:
            result.mass_fractions = fractions
