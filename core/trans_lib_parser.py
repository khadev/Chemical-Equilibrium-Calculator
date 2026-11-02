"""
core/trans_lib_parser.py
============================
Best-effort structural parser for NASA's ``trans.lib`` transport
properties database (viscosity and thermal conductivity coefficient
sets per species). Uses the same header/continuation heuristic as
:class:`core.thermo_lib_parser.ThermoLibParser`, since trans.lib shares
the same general fixed-format card layout.

Importing trans.lib does not change Isp/Cf calculations in this
application (those use the isentropic-flow fallback model or FCEA2's
own output) — it records *which* species have transport data
available, displayed as an informational badge in the species picker,
and is a prerequisite for a future, more detailed Bartz heat-transfer
calculation that uses real per-species viscosity/conductivity data
instead of representative defaults.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

log = logging.getLogger(__name__)

_SKIP_LINES = {"trans", "end"}


class TransLibParseError(Exception):
    """Raised when a file does not appear to be a valid trans.lib."""


@dataclass
class TransportSpecies:
    """A species with transport (viscosity/conductivity) data available."""

    name: str
    source_line: int


class TransLibParser:
    """Parses a NASA CEA ``trans.lib`` file for species names."""

    def parse(self, path: str) -> List[TransportSpecies]:
        """
        Parse ``path`` and return all species with transport data.

        Args:
            path: Path to the ``trans.lib`` file.

        Returns:
            List of :class:`TransportSpecies`, in file order.

        Raises:
            TransLibParseError: If the file cannot be read, or fewer
                than 3 plausible species records are found.
        """
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            raise TransLibParseError(f"Could not read file: {exc}") from exc

        species: List[TransportSpecies] = []

        for line_no, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                continue
            if raw_line.strip().lower() in _SKIP_LINES:
                continue
            if raw_line[0].isspace():
                continue
            first_token = raw_line.split()[0]
            if first_token[0].isdigit():
                continue
            if len(first_token) > 24:
                continue
            species.append(TransportSpecies(name=first_token, source_line=line_no))

        if len(species) < 3:
            raise TransLibParseError(
                "This does not look like a valid trans.lib file — "
                f"only {len(species)} plausible species header(s) found.")

        log.info("Parsed %d species with transport data from %s",
                 len(species), path)
        return species
