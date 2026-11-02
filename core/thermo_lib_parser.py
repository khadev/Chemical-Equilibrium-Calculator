

"""
core/thermo_lib_parser.py
============================
Best-effort structural parser for NASA's ``thermo.lib`` (a.k.a.
``thermo.inp``) species database file.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

log = logging.getLogger(__name__)

_SKIP_LINES = {"thermo", "end products", "end reactants", "end"}
_CONDENSED_SUFFIX_RE = re.compile(r"\((cr|l|a|b|c|g|s|i|ii|iii|iv)\)$", re.IGNORECASE)


class ThermoLibParseError(Exception):
    """Raised when a file does not appear to be a valid thermo.lib."""


@dataclass
class ImportedSpecies:
    """A single species record extracted from an imported thermo.lib."""
    name: str
    phase: str  # "gas" or "condensed"
    source_line: int


class ThermoLibParser:
    """Parses a NASA CEA ``thermo.lib``/``thermo.inp`` file."""

    def parse(self, path: str) -> List[ImportedSpecies]:
        """
        Parse ``path`` and return all species records found.
        """
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            raise ThermoLibParseError(f"Could not read file: {exc}") from exc

        species: List[ImportedSpecies] = []
        expecting_data = False

        for line_no, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                expecting_data = False
                continue

            stripped_lower = raw_line.strip().lower()
            if stripped_lower in _SKIP_LINES:
                expecting_data = False
                continue

            is_indented = raw_line[0].isspace()
            first_token = raw_line.split()[0] if raw_line.split() else ""

            if is_indented:
                continue

            if first_token and first_token[0].isdigit():
                continue

            # Looks like a species header card
            name = first_token
            
            # Clean the name - remove any trailing garbage
            # thermo.lib sometimes has comments like "g12/97" after the name
            name_parts = name.split()
            if name_parts:
                name = name_parts[0]
            
            # Remove asterisks
            name = name.replace('*', '').strip()
            
            # Skip if name is too short or invalid
            if not name or len(name) < 2:
                continue
            if not name[0].isalpha():
                continue
            if len(name) > 24:
                continue
                
            phase = ("condensed" if _CONDENSED_SUFFIX_RE.search(name) else "gas")
            species.append(ImportedSpecies(name=name, phase=phase, source_line=line_no))
            expecting_data = True

        if len(species) < 3:
            raise ThermoLibParseError(
                "This does not look like a valid thermo.lib file — "
                f"only {len(species)} plausible species header(s) found.")

        log.info("Parsed %d species from %s", len(species), path)
        return species