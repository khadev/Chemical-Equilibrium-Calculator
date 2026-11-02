"""
models/formulation.py
=======================
``Formulation`` dataclass — the single source of truth for a propellant
formulation's state. Holds oxidizer/fuel selection, operating
conditions, and user-defined reactants. Pure data — no UI, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


@dataclass
class UserReactant:
    """
    A user-defined reactant requiring explicit atomic composition
    (e.g. HTPB binder).

    Serializes to the NASA CEA ``.inp`` line format:

        name=HTPB wt=14 t,k=298
        h,kj/mol=-58 C 7.075 H 10.650 O 0.063 N 0.223

    NOTE: The "name=..." line and the "h,kj/mol=..." line are on
    SEPARATE lines in the .inp file. This is critical for CEA2 to
    parse correctly.
    """

    name: str = ""
    weight_pct: float = 14.0
    temperature_k: float = 298.0
    enthalpy_kj_mol: float = 0.0
    composition: Dict[str, float] = field(default_factory=dict)

    def to_inp_line(self) -> str:
        """
        Render this reactant as a single NASA CEA ``.inp`` line.
        
        CRITICAL: The line must NOT have trailing spaces, and the
        elements must be in the correct order for CEA2.
        """
        parts = [f"name={self.name}"]
        
        # Weight percentage (0.0 means use the reactant's own stoichiometry)
        if self.weight_pct not in (0.0, 100.0):
            parts.append(f"wt={self.weight_pct:.4g}")
        
        parts.append(f"t,k={self.temperature_k:.1f}")
        
        return " ".join(parts)

    def to_enthalpy_line(self) -> str:
        """
        Render the enthalpy and composition as a separate line.
        
        CEA2 expects the enthalpy and composition on a SEPARATE line
        from the name line. This is critical for parsing!
        """
        parts = []
        
        # Enthalpy (required for non-standard reactants)
        if self.enthalpy_kj_mol != 0.0:
            parts.append(f"h,kj/mol={self.enthalpy_kj_mol:.4g}")
        
        # Elements - CEA2 expects them in a specific order
        # Usually: C, H, N, O, then others alphabetically
        # This matches the NASA CEA standard format
        for element in ["C", "H", "N", "O"]:
            if element in self.composition:
                amount = self.composition[element]
                if amount > 0:
                    parts.append(f"{element} {amount:.3f}")
        
        # Add any remaining elements
        for element, amount in self.composition.items():
            if element not in ["C", "H", "N", "O"] and amount > 0:
                parts.append(f"{element} {amount:.3f}")
        
        return " ".join(parts)

    def validate(self) -> tuple[bool, str]:
        """
        Validate this reactant's fields.

        Returns:
            ``(True, "OK")`` if valid, otherwise ``(False, reason)``.
        """
        if not self.name:
            return False, "Reactant name cannot be empty."
        
        # Allow wt=0 for placeholder reactants (like NC, NCS with wt=0)
        # But still require composition if weight > 0
        if self.weight_pct > 0 and not self.composition:
            return False, f"'{self.name}' requires an atomic composition."
        
        # If weight is 0, composition is optional (it's a placeholder)
        if self.weight_pct == 0:
            return True, "OK"
        
        for element, amount in self.composition.items():
            if amount <= 0:
                return False, f"Amount for '{element}' must be positive."
        
        return True, "OK"


@dataclass
class Formulation:
    """
    Complete propellant formulation state.

    Attributes:
        name: User-facing formulation/session name.
        oxidizer_name: Canonical oxidizer species name.
        oxidizer_temperature_k: Oxidizer storage/injection temperature.
        oxidizer_weight_pct: Oxidizer mass fraction (wt%).
        fuel_name: Canonical fuel species name.
        fuel_temperature_k: Fuel storage/injection temperature.
        fuel_weight_pct: Fuel mass fraction (wt%).
        user_reactants: Optional list of :class:`UserReactant`.
        chamber_pressure_bar: Combustion chamber pressure.
        of_ratio: Oxidizer-to-fuel mass ratio.
        exit_pressure_bar: Nozzle exit pressure.
        area_ratio: Nozzle expansion ratio Ae/At.
        tcest_k: Temperature estimate for the CEA equilibrium solver.
        frozen: If True, use frozen-flow chemistry instead of equilibrium.
    """

    # === Basic Information ===
    name: str = "Formulation 1"

    # === Oxidizer ===
    oxidizer_name: str = ""
    oxidizer_temperature_k: float = 298.0
    oxidizer_weight_pct: float = 68.0

    # === Fuel ===
    fuel_name: str = ""
    fuel_temperature_k: float = 298.0
    fuel_weight_pct: float = 18.0

    # === User-Defined Reactants (Binders, etc.) ===
    # Each reactant is stored as a dict with keys:
    #   name, weight_pct, temperature_k, enthalpy_kj_mol, composition
    user_reactants: List[Dict[str, Any]] = field(default_factory=list)

    # === Operating Conditions ===
    chamber_pressure_bar: float = 50.0
    of_ratio: float = 2.5
    exit_pressure_bar: float = 1.0
    area_ratio: float = 10.0
    
    # === CEA Parameters ===
    # CRITICAL: "tcest" is the CORRECT spelling (NOT "tcost", NOT "ttest")
    # This is the temperature estimate for the CEA equilibrium solver
    tcest_k: int = 3800
    pi_over_p: float = 70.0
    
    # === Chemistry Mode ===
    frozen: bool = False

    # ── Serialization ────────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        """Return a plain-dict representation suitable for JSON export."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Formulation":
        """
        Build a :class:`Formulation` from a plain dict, ignoring
        unknown keys.

        Args:
            data: Source dictionary.

        Returns:
            Populated :class:`Formulation` instance.
        """
        f = cls()
        for key, value in data.items():
            if hasattr(f, key):
                setattr(f, key, value)
        return f

    def get_user_reactants(self) -> List[UserReactant]:
        """Return :attr:`user_reactants` as typed :class:`UserReactant` objects."""
        return [UserReactant(**d) for d in self.user_reactants]

    def add_user_reactant(self, reactant: UserReactant) -> None:
        """Append a user-defined reactant to the formulation."""
        self.user_reactants.append(asdict(reactant))

    def clear(self) -> None:
        """Reset all fields to their defaults in place."""
        defaults = Formulation()
        for key, value in asdict(defaults).items():
            setattr(self, key, value)
    
    def get_total_weight_pct(self) -> float:
        """
        Calculate the total weight percentage of all reactants.
        Used for validation and normalization.
        """
        total = 0.0
        if self.oxidizer_weight_pct > 0:
            total += self.oxidizer_weight_pct
        if self.fuel_weight_pct > 0:
            total += self.fuel_weight_pct
        for reactant in self.user_reactants:
            total += reactant.get("weight_pct", 0.0)
        return total
    
    def normalize_weights(self) -> None:
        """
        Normalize all weight percentages to sum to 100%.
        This is useful when loading from files where weights might
        not sum to exactly 100%.
        """
        total = self.get_total_weight_pct()
        if total <= 0:
            return
        
        # Only normalize if the total is close to 100%
        if abs(total - 100.0) > 0.1:
            scale = 100.0 / total
            if self.oxidizer_weight_pct > 0:
                self.oxidizer_weight_pct *= scale
            if self.fuel_weight_pct > 0:
                self.fuel_weight_pct *= scale
            for reactant in self.user_reactants:
                reactant["weight_pct"] *= scale
    
    def get_active_reactants(self) -> List[Dict[str, Any]]:
        """
        Return only the user reactants with weight_pct > 0.
        This filters out placeholder reactants like NC and NCS with wt=0.
        """
        return [r for r in self.user_reactants if r.get("weight_pct", 0.0) > 0]
    
    def has_user_reactants(self) -> bool:
        """Return True if there are any user reactants with weight_pct > 0."""
        return len(self.get_active_reactants()) > 0
