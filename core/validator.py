
"""
core/validator.py
===================
Pre-flight validation for a :class:`Formulation` before it is sent to
the CEA engine. Blocks calculation when validation fails.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from models.formulation import Formulation
from models.species_database import SpeciesDatabase, normalize_species_name


@dataclass
class ValidationResult:
    """Outcome of a pre-flight validation pass."""
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PreFlightValidator:
    """Validates formulations against species database and numeric ranges."""

    # Valid binder names (user-defined reactants)
    VALID_BINDERS = {
        "HTPB", "MCCN", "OCN", "NCS", "NPS", "NCT", "GAP", "PEG",
        "PBAN", "CTPB", "HTPE", "Desmophen", "NC"
    }

    def __init__(self) -> None:
        self._db = SpeciesDatabase()

    def _normalize_and_validate_species(self, formulation: Formulation) -> None:
        """Normalize species names and validate they exist in the database."""
        # Normalize oxidizer name
        if formulation.oxidizer_name:
            normalized_ox = normalize_species_name(formulation.oxidizer_name)
            if normalized_ox != formulation.oxidizer_name:
                formulation.oxidizer_name = normalized_ox

        # Normalize fuel name
        if formulation.fuel_name:
            normalized_fuel = normalize_species_name(formulation.fuel_name)
            if normalized_fuel != formulation.fuel_name:
                formulation.fuel_name = normalized_fuel

    def validate(
            self, formulation: Formulation, check_cea_path: bool = True,
            cea_available: bool = False
    ) -> ValidationResult:
        """
        Validate a formulation.

        Args:
            formulation: Formulation to check.
            check_cea_path: If True, emit a warning when FCEA2.exe is
                not configured.
            cea_available: Whether FCEA2.exe is currently configured.

        Returns:
            :class:`ValidationResult` with ``passed`` set to False if
            any error was found.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # First, try to normalize species names
        self._normalize_and_validate_species(formulation)

        # Validate oxidizer
        if not formulation.oxidizer_name:
            errors.append("Oxidizer species not selected.")
        elif not self._db.is_oxidizer(formulation.oxidizer_name):
            # Try case-insensitive match as a last resort
            all_oxidizers = self._db.all_oxidizers()
            matching = [ox for ox in all_oxidizers if ox.lower() == formulation.oxidizer_name.lower()]
            if matching:
                formulation.oxidizer_name = matching[0]
            else:
                errors.append(
                    f"'{formulation.oxidizer_name}' is not a recognised "
                    "oxidizer species. Try selecting it from the species picker.")

        # Validate fuel
        if not formulation.fuel_name:
            errors.append("Fuel species not selected.")
        elif not self._db.is_fuel(formulation.fuel_name):
            # Check if it's a valid binder (user-defined reactant)
            if formulation.fuel_name in self.VALID_BINDERS:
                # It's a binder, which is fine - it will be handled as a user reactant
                pass
            else:
                # Try case-insensitive match
                all_fuels = self._db.all_fuels()
                matching = [fuel for fuel in all_fuels if fuel.lower() == formulation.fuel_name.lower()]
                if matching:
                    formulation.fuel_name = matching[0]
                else:
                    errors.append(
                        f"'{formulation.fuel_name}' is not a recognised fuel "
                        "species. Try selecting it from the species picker.")

        # Validate user reactants (binders)
        for reactant_dict in formulation.user_reactants:
            name = reactant_dict.get("name", "")
            composition = reactant_dict.get("composition", {})
            if not composition and name not in self.VALID_BINDERS:
                errors.append(
                    f"User-defined reactant '{name}' has no atomic "
                    "composition.")

        # Validate numeric ranges
        if not 1.0 <= formulation.chamber_pressure_bar <= 1000.0:
            errors.append(
                f"Chamber pressure {formulation.chamber_pressure_bar} bar "
                "is outside the valid range [1, 1000].")

        if not 0.1 <= formulation.of_ratio <= 30.0:
            errors.append(
                f"O/F ratio {formulation.of_ratio} is outside the valid "
                "range [0.1, 30].")

        if not 1.0 <= formulation.area_ratio <= 500.0:
            errors.append(
                f"Area ratio {formulation.area_ratio} is outside the "
                "valid range [1, 500].")

        if not 0.01 <= formulation.exit_pressure_bar <= 100.0:
            errors.append(
                f"Exit pressure {formulation.exit_pressure_bar} bar is "
                "outside the valid range [0.01, 100].")

        if check_cea_path and not cea_available:
            warnings.append(
                "FCEA2.exe is not configured — the fallback ideal-rocket "
                "calculator will be used.")

        return ValidationResult(passed=not errors, errors=errors, warnings=warnings)
