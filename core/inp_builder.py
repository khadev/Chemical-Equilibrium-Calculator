
"""
core/inp_builder.py
=====================
Generates NASA CEA ``.inp`` input files in the EXACT format that FCEA2.exe expects.

CRITICAL FORMAT REQUIREMENTS:
- "prob" NOT "problem"
- "react" NOT "reactt" 
- "output" NOT "outp"
- ALL problem parameters on ONE line: "rocket equilibrium tcest,k=3800 p,bar=70 sup,ae/at=10"
- Element order: C, O, H, N (NOT C, H, O, N!)
- "wt=00" for placeholder reactants (TWO zeros)
- 2 spaces indentation before reactant lines
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

from core.exceptions import INPBuildError
from models.formulation import Formulation, UserReactant
from models.species_database import normalize_species_name

log = logging.getLogger(__name__)


class INPBuilder:
    """Builds and parses NASA CEA ``.inp`` files."""

    @staticmethod
    def build(formulation: Formulation) -> str:
        """
        Build the complete ``.inp`` file content for a formulation.
        Uses EXACTLY the same format as the working GUI.
        """
        if not formulation.oxidizer_name and not formulation.fuel_name:
            raise INPBuildError(
                "Formulation must specify at least an oxidizer or a fuel.")

        mode = "frozen" if formulation.frozen else "equilibrium"
       
        # ===== EXACT format from working GUI =====
        # ALL problem parameters on ONE line
        problem_line = f"rocket {mode} tcest,k={formulation.tcest_k} p,bar={formulation.chamber_pressure_bar:.4g} sup,ae/at={formulation.area_ratio:.4g}"
       
        lines = [
            "prob",
            problem_line,
            "react",
        ]

        # Oxidizer line - EXACT format with 2 spaces indent
        if formulation.oxidizer_name:
            ox_name = formulation.oxidizer_name
            # Ensure correct case
            if "nh4clo4" in ox_name.lower():
                ox_name = "NH4CLO4(I)"  # All caps for CEA2
            parts = [f"  oxid={ox_name}"]
            if formulation.oxidizer_weight_pct not in (0.0, 100.0):
                parts.append(f"wt={formulation.oxidizer_weight_pct:.4g}")
            parts.append(f"t,k={formulation.oxidizer_temperature_k:.1f}")
            lines.append(" ".join(parts).strip())

        # Fuel line - EXACT format with 2 spaces indent
        if formulation.fuel_name:
            fu_name = formulation.fuel_name
            # Ensure correct case
            if "al" in fu_name.lower() and "(cr)" in fu_name.lower():
                fu_name = "AL(cr)"  # All caps for CEA2
            parts = [f"  fuel={fu_name}"]
            if formulation.fuel_weight_pct not in (0.0, 100.0):
                parts.append(f"wt={formulation.fuel_weight_pct:.4g}")
            parts.append(f"t,k={formulation.fuel_temperature_k:.1f}")
            lines.append(" ".join(parts).strip())

        # User reactants - EXACT format
        for reactant_dict in formulation.user_reactants:
            try:
                reactant = UserReactant(**reactant_dict)
                valid, message = reactant.validate()
                if valid:
                    # Skip NC and NCS with wt=0 (they're just placeholders)
                    if reactant.weight_pct == 0 and reactant.name.upper() in ["NC", "NCS"]:
                        continue
                   
                    # Name line - with 2 spaces indent
                    name_parts = [f"  name={reactant.name}"]
                    # Use "wt=00" for placeholder reactants, "wt=XX" for real ones
                    if reactant.weight_pct == 0:
                        name_parts.append("wt=00")
                    elif reactant.weight_pct not in (0.0, 100.0):
                        name_parts.append(f"wt={reactant.weight_pct:.4g}")
                    name_parts.append(f"t,k={reactant.temperature_k:.1f}")
                    lines.append(" ".join(name_parts).strip())
                   
                    # Enthalpy + composition line (indented with 2 spaces)
                    # CRITICAL: Element order is C, O, H, N (NOT C, H, O, N!)
                    h_parts = [f"  h,kj/mol={reactant.enthalpy_kj_mol:.4g}"]
                   
                    # Elements in order: C, O, H, N (matching working GUI)
                    for element in ["C", "O", "H", "N"]:
                        if element in reactant.composition:
                            amount = reactant.composition[element]
                            if amount > 0:
                                h_parts.append(f"{element} {amount:.3f}")
                   
                    # Add any remaining elements
                    for element, amount in reactant.composition.items():
                        if element not in ["C", "O", "H", "N"] and amount > 0:
                            h_parts.append(f"{element} {amount:.3f}")
                   
                    if h_parts:
                        lines.append(" ".join(h_parts).strip())
                else:
                    log.warning(f"Skipping invalid user reactant: {message}")
            except Exception as exc:
                log.error(f"Failed to process user reactant: {exc}")

        # Output section - EXACT format
        lines += [
            "output",
            "     siunits massf",
            "end",
            ""
        ]
       
        # ===== Build the content =====
        content = "\n".join(lines)
       
        # ===== CRITICAL: Fix common typos =====
        content = content.replace("tcost", "tcest")
        content = content.replace("ttest", "tcest")
        content = content.replace("reac", "react")
        content = content.replace("outp", "output")
        content = content.replace("problem", "prob")
       
        # ===== CRITICAL: Fix element order (C, O, H, N) =====
        # The working GUI uses C, O, H, N - NOT C, H, O, N!
        # We need to reorder elements on h,kj/mol lines
        def fix_element_order(line: str) -> str:
            if "h,kj/mol" in line and " C " in line and " H " in line and " O " in line and " N " in line:
                # Extract all element amounts
                c_match = re.search(r"C\s+([\d.]+)", line)
                o_match = re.search(r"O\s+([\d.]+)", line)
                h_match = re.search(r"H\s+([\d.]+)", line)
                n_match = re.search(r"N\s+([\d.]+)", line)
               
                if c_match and o_match and h_match and n_match:
                    c_val = c_match.group(1)
                    o_val = o_match.group(1)
                    h_val = h_match.group(1)
                    n_val = n_match.group(1)
                   
                    # Remove all element patterns from the line
                    line = re.sub(r"\s+[COHN]\s+[\d.]+", "", line)
                   
                    # Add back in order: C, O, H, N
                    line = line + f" C {c_val} O {o_val} H {h_val} N {n_val}"
                   
                    # Clean up extra spaces
                    line = re.sub(r"\s+", " ", line)
           
            return line
       
        # Apply element order fix to all lines
        lines_fixed = []
        for line in content.split("\n"):
            if "h,kj/mol" in line:
                line = fix_element_order(line)
            lines_fixed.append(line)
        content = "\n".join(lines_fixed)
       
        log.debug(f"Generated INP content:\n{content}")
       
        return content

    @staticmethod
    def save(formulation: Formulation, path: str) -> None:
        """
        Write the formulation's ``.inp`` content to disk.
        """
        content = INPBuilder.build(formulation)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
       
        # ===== CRITICAL: Write with NO BOM, LF line endings =====
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        log.info("INP file saved: %s", path)

    @staticmethod
    def parse_file(path: str) -> Formulation:
        """
        Parse an existing ``.inp`` file into a :class:`Formulation`.
        PRESERVES the original format.
        """
        formulation = Formulation()
        formulation.name = os.path.splitext(os.path.basename(path))[0]

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            log.error("Could not read INP file %s: %s", path, exc)
            return formulation

        # Parse problem section - look for the single-line format
        # rocket equilibrium tcest,k=3800 p,bar=70 sup,ae/at=10
        match = re.search(r"rocket\s+(equilibrium|frozen)\s+tcest,k\s*=\s*([\d.]+)\s+p,bar\s*=\s*([\d.]+)\s+sup,ae/at\s*=\s*([\d.]+)", text, re.IGNORECASE)
        if match:
            mode = match.group(1).lower()
            formulation.frozen = mode == "frozen"
            formulation.tcest_k = int(float(match.group(2)))
            formulation.chamber_pressure_bar = float(match.group(3))
            formulation.area_ratio = float(match.group(4))

        # Parse oxidizer
        oxid_match = re.search(r"oxid\s*=\s*(\S+)", text, re.IGNORECASE)
        if oxid_match:
            formulation.oxidizer_name = oxid_match.group(1).strip()
            # Find wt and t,k on the same line
            wt_match = re.search(r"oxid\s*=\s*\S+\s+wt\s*=\s*([\d.]+)", text, re.IGNORECASE)
            if wt_match:
                formulation.oxidizer_weight_pct = float(wt_match.group(1))
            t_match = re.search(r"oxid\s*=\s*\S+\s+t,k\s*=\s*([\d.]+)", text, re.IGNORECASE)
            if t_match:
                formulation.oxidizer_temperature_k = float(t_match.group(1))

        # Parse fuel
        fuel_match = re.search(r"fuel\s*=\s*(\S+)", text, re.IGNORECASE)
        if fuel_match:
            formulation.fuel_name = fuel_match.group(1).strip()
            wt_match = re.search(r"fuel\s*=\s*\S+\s+wt\s*=\s*([\d.]+)", text, re.IGNORECASE)
            if wt_match:
                formulation.fuel_weight_pct = float(wt_match.group(1))
            t_match = re.search(r"fuel\s*=\s*\S+\s+t,k\s*=\s*([\d.]+)", text, re.IGNORECASE)
            if t_match:
                formulation.fuel_temperature_k = float(t_match.group(1))

        # Parse user reactants (name=...)
        user_reactants = []
        lines = text.split('\n')
       
        i = 0
        while i < len(lines):
            line = lines[i].strip()
           
            if line.startswith("name="):
                name_match = re.search(r"name=(\S+)", line)
                if name_match:
                    name = name_match.group(1)
                   
                    wt_match = re.search(r"wt=([\d.]+)", line)
                    t_match = re.search(r"t,k=([\d.]+)", line)
                   
                    # Look at next lines for h,kj/mol
                    h_line = ""
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if "h,kj/mol" in next_line:
                            h_line = next_line
                            i = j
                            break
                        elif next_line.startswith("name=") or next_line.startswith("oxid=") or next_line.startswith("fuel="):
                            break
                        j += 1
                   
                    h_match = re.search(r"h,kj/mol=([-\d.]+)", h_line)
                   
                    composition: Dict[str, float] = {}
                    for em in re.finditer(r"([A-Z][a-z]?)\s+([\d.]+)", h_line):
                        composition[em.group(1)] = float(em.group(2))
                   
                    if composition:
                        user_reactants.append({
                            "name": name,
                            "weight_pct": float(wt_match.group(1)) if wt_match else 0.0,
                            "temperature_k": float(t_match.group(1)) if t_match else 298.0,
                            "enthalpy_kj_mol": float(h_match.group(1)) if h_match else 0.0,
                            "composition": composition,
                        })
            i += 1
       
        if user_reactants:
            formulation.user_reactants = user_reactants

        return formulation
