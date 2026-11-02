"""
core/cea_python_executor.py
============================
Wraps the official NASA 'cea' Python package to perform real equilibrium calculations.
"""
from __future__ import annotations
import logging
from typing import Callable, Optional
import numpy as np

from core.exceptions import CEAExecutionError
from models.cea_result import CEAResult, G0
from models.formulation import Formulation

log = logging.getLogger(__name__)

try:
    import cea
    CEA_PYTHON_AVAILABLE = True
except ImportError:
    CEA_PYTHON_AVAILABLE = False
    log.warning("NASA 'cea' Python package not installed.")

class CEAPythonExecutor:
    """Executes CEA calculations using the official NASA Python package."""

    def __init__(self):
        self.available = CEA_PYTHON_AVAILABLE

    def run(self, formulation: Formulation,
            log_callback: Optional[Callable[[str], None]] = None) -> CEAResult:
        if not self.available:
            raise CEAExecutionError("cea package is not installed. Please install it.")

        def _log(msg):
            if log_callback:
                log_callback(msg)
            else:
                log.info(msg)

        _log(f"Running NASA CEA Python engine for '{formulation.name}'")

        # ===== 1. Build reactant mixture =====
        reactant_names = []
        reactant_weights = []
        reactant_temps = []
        
        # Add oxidizer
        if formulation.oxidizer_name and formulation.oxidizer_weight_pct > 0:
            reactant_names.append(formulation.oxidizer_name)
            reactant_weights.append(formulation.oxidizer_weight_pct)
            reactant_temps.append(formulation.oxidizer_temperature_k)
        
        # Add fuel
        if formulation.fuel_name and formulation.fuel_weight_pct > 0:
            reactant_names.append(formulation.fuel_name)
            reactant_weights.append(formulation.fuel_weight_pct)
            reactant_temps.append(formulation.fuel_temperature_k)
        
        # Add user reactants (binders, etc.)
        for r in formulation.user_reactants:
            name = r.get('name', '')
            wt = r.get('weight_pct', 0.0)
            temp = r.get('temperature_k', 298.0)
            if name and wt > 0:
                reactant_names.append(name)
                reactant_weights.append(wt)
                reactant_temps.append(temp)

        # Normalize weights to sum to 1.0
        total_weight = sum(reactant_weights)
        if total_weight <= 0:
            raise CEAExecutionError("No reactants with positive weight.")
        
        weights = np.array([w / total_weight for w in reactant_weights])
        T_reactants = np.array(reactant_temps)

        # ===== 2. Create CEA Mixture objects =====
        try:
            reac = cea.Mixture(reactant_names)
            prod = cea.Mixture(reactant_names, products_from_reactants=True)
        except Exception as e:
            raise CEAExecutionError(f"Failed to create CEA Mixture: {e}")

        # ===== 3. Create and run the Rocket Solver =====
        try:
            solver = cea.RocketSolver(prod, reactants=reac)
            solution = cea.RocketSolution(solver)
            
            pc_bar = formulation.chamber_pressure_bar
            supar = np.array([formulation.area_ratio])
            
            # Calculate chamber enthalpy
            hc = reac.calc_property(cea.ENTHALPY, weights, T_reactants) / cea.R
            
            # Solve the rocket problem
            solver.solve(solution, weights, pc_bar, supar=supar, hc=hc, iac=True)
            
        except Exception as e:
            raise CEAExecutionError(f"cea package failed to solve: {e}")

        # ===== 4. Extract results into our CEAResult object =====
        result = CEAResult()
        result.name = formulation.name
        result.method = "CEA Python (Real Equilibrium)"
        result.success = True
        result.area_ratio = formulation.area_ratio
        result.p_chamber_bar = formulation.chamber_pressure_bar

        # Helper to safely get values from the solution object
        def _get(attr, index=0, default=0.0):
            try:
                val = getattr(solution, attr)
                if isinstance(val, (list, tuple, np.ndarray)):
                    if len(val) > index:
                        return float(val[index])
                    return float(val[-1]) # Use last if index out of bounds
                return float(val)
            except Exception:
                return default

        # Station indices: 0 = Chamber, 1 = Throat, 2 = Exit
        # Mapping directly from the CEA package attributes observed in your console
        result.t_chamber_k = _get('T', 0)
        result.t_throat_k = _get('T', 1)
        result.t_exit_k = _get('T', 2)
        
        result.p_throat_bar = _get('P', 1)
        result.p_exit_bar = _get('P', 2)
        
        result.cstar_m_s = _get('c_star', 0)
        result.cf_vacuum = _get('coefficient_of_thrust', 2)
        result.cf = _get('coefficient_of_thrust', 2)
        
        # FIX: Isp is returned in m/s by the CEA package, convert to seconds
        result.isp_vacuum_s = _get('Isp_vacuum', 2) / G0
        result.isp_sea_level_s = _get('Isp', 2) / G0
        
        result.mach_exit = _get('Mach', 2)
        result.gamma = _get('gammas', 2)
        result.molecular_weight = _get('M', 2)
        
        # FIX: Extract mass fractions at exit (stored as dict of lists)
        try:
            if hasattr(solution, 'mass_fractions'):
                mf = solution.mass_fractions
                if isinstance(mf, dict):
                    result.mass_fractions = {}
                    for k, v in mf.items():
                        if len(v) > 2:
                            frac = float(v[2]) # Exit station
                        elif len(v) > 0:
                            frac = float(v[-1])
                        else:
                            continue
                        
                        if frac > 1e-6:
                            result.mass_fractions[k] = frac
        except Exception as e:
            _log(f"Error parsing mass fractions: {e}")

        result.ivac_m_s = result.isp_vacuum_s * G0
        result.ivac_sea_level_m_s = result.isp_sea_level_s * G0

        _log(f"CEA Python complete: Isp_vac={result.isp_vacuum_s:.2f}s, C*={result.cstar_m_s:.1f}m/s, Cf={result.cf:.4f}, Mach={result.mach_exit:.2f}")
        return result
