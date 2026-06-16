# ⚖️ chem-eq-calculator - Chemical Equilibrium Calculator

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPLv3-3F51B5.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-1.0.0-2E7D32.svg)](https://pypi.org/project/chem-eq-calculator/)

**Professional thermodynamic analysis software with NASA CEA2 integration**

---

## 🚀 Installation

```bash
pip install chem-eq-calculator
```

## Run the application

```bash
chem-eq-calculator
```

Or from Python:

```python
from chem-eq-calculator import CEACalculator

calc = CEACalculator()
calc.set_oxidizer("NH4ClO4(I)", 298.0, 72.0)
calc.set_fuel("HTPB", 298.0, 18.0)
calc.set_conditions(pc=50.0, of_ratio=2.5, ae_at=10.0)
result = calc.run()
print(f"Isp: {result.isp_ms:.0f} m/s")
```

---

## 🔬 Overview

**Chemical Equilibrium Calculator (chem-eq-calculator)** is a professional-grade desktop application for thermodynamic equilibrium calculations in chemical systems. Built with a modular MVC architecture, it provides precise equilibrium composition analysis, thermodynamic property calculations, and comprehensive performance evaluation.

The software integrates with **NASA's CEA2** for high-precision calculations while maintaining a robust fallback ideal gas calculator.

---

## ✨ Features

| Category | Features |
|----------|----------|
| **Equilibrium Calculations** | Complex multi-species chemical equilibrium analysis |
| **Thermodynamic Properties** | Temperature, pressure, enthalpy, entropy computations |
| **Nozzle Design** | Isentropic flow analysis and geometric optimization |
| **Batch Processing** | Parametric sweeps and sensitivity analysis |
| **Visualization** | Interactive plots, radar charts, and performance graphs |
| **User-Defined Reactants** | Custom species with atomic composition |
| **Multi-language** | English and French interfaces |

### Species Database

- **129 Oxidizers** - Complete NASA CEA2 oxidizer list
- **397 Fuels** - Extensive fuel database including hydrocarbons, metals, and hydrides
- **70+ Elements** - Periodic table for custom composition

### Analysis Tools (25+)

- Nozzle Designer, Chamber Sizer, Contraction Ratio
- Heat Transfer (Bartz), Regenerative Cooling, Instability Predictor
- Delta-V Calculator, Orbit Insertion, Staging Optimiser
- Sensitivity Analysis, Design of Experiments, Composition vs T
- LaTeX Generator, Python Script, Unit Converter

---

## 📋 Requirements

- Python 3.11 or higher
- PySide6 >= 6.6.0
- matplotlib >= 3.7.0
- numpy >= 1.24.0
- pandas >= 2.0.0
- qtawesome >= 1.3.0

---

## 🎯 Quick Start

### Basic Calculation Workflow

```bash
# Run the GUI application
chem-eq-calculator
```

### Example Formulation

| Parameter | Value |
|-----------|-------|
| Oxidizer | NH₄ClO₄(I) |
| Oxidizer Temp | 298.0 K |
| Oxidizer Wt | 72.0 % |
| Fuel | HTPB |
| Fuel Temp | 298.0 K |
| Fuel Wt | 18.0 % |
| Chamber Pressure | 50.0 bar |
| O/F Ratio | 2.5 |
| Area Ratio | 10.0 |

### Expected Results

| Metric | Value |
|--------|-------|
| Specific Impulse (Isp) | ~250 s (2450 m/s) |
| Characteristic Velocity (C*) | ~1580 m/s |
| Thrust Coefficient (Cf) | 1.55-1.65 |
| Chamber Temperature (Tc) | ~3300 K |

---

## 🛰️ NASA CEA2 Integration

For high-precision calculations, install NASA CEA2:

```bash
pip install cea
```

Then configure paths in the application **Settings** (`Ctrl+,`).

---

## 📖 Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Calculate | `Ctrl+R` |
| Validate | `Ctrl+Shift+V` |
| Add Session | `Ctrl+T` |
| Load .inp | `Ctrl+O` |
| Save .inp | `Ctrl+S` |
| Export CSV | `Ctrl+E` |
| Open Settings | `Ctrl+,` |

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| ModuleNotFoundError | Run `pip install chem-eq-calculator --force-reinstall` |
| No species in dropdown | Verify databasecea.txt exists |
| Plots not displaying | Install matplotlib: `pip install matplotlib` |
| FCEA2 execution error | Configure CEA2 paths in Settings |

---

## 📄 License

```
chem-eq-calculator - Chemical Equilibrium Calculator
Copyright (C) 2026 Oukil Khaled Ibn Elwalid

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
```

---

## 👨‍💻 Author

**Oukil Khaled Ibn Elwalid**

- GitHub: [@khadev](https://github.com/khadev)
- Email: oukil.khaled@gmail.com

---

<div align="center">

**⚖️ Made for the scientific community**

[GitHub Repository](https://github.com/khadev/Chemical-Equilibrium-Calculator) · [Report Issue](https://github.com/khadev/Chemical-Equilibrium-Calculator/issues)

</div>
