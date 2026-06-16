
<div align="center">
<img src="Screenshots/startwin.png" alt="Chemical Equilibrium Calculator Banner" width="250">
  <br>
# 🌡️ Chemical Equilibrium Calculator

### Professional Thermodynamic Analysis Software

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-41CD52.svg?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![License](https://img.shields.io/badge/License-GPLv3-3F51B5.svg?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.0-2E7D32.svg?style=for-the-badge)]()

</div>

---

## 📸 Screenshots

<details open>
<summary><b>📱 Click to expand/collapse screenshots</b></summary>
<br>

### Main Application Interface

<div align="center">

![Chemical Equilibrium Calculator](Screenshots/main.png)

*Main application window showing the formulation panel, session management, and results display*

</div>

### Additional Screenshots

<details>
<summary><b>➕ Add Reactant Dialog</b></summary>
<br>
<div align="center">

![Add Reactant](Screenshots/add-react.png)

</div>
</details>

<details>
<summary><b>🚀 Nozzle Designer</b></summary>
<br>
<div align="center">

![Nozzle Designer](Screenshots/nozzle.png)

</div>
</details>

<details>
<summary><b>📊 Performance Analysis</b></summary>
<br>
<div align="center">

![Performance Analysis](Screenshots/performance.png)

</div>
</details>

<details>
<summary><b>📈 Plots & Visualization</b></summary>
<br>
<div align="center">

![Plots Visualization](Screenshots/plots.png)

</div>
</details>

<details>
<summary><b>⚙️ Settings Dialog</b></summary>
<br>
<div align="center">

![Settings Dialog](Screenshots/settings.png)

</div>
</details>

</details>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Screenshots](#-screenshots)
- [Features](#-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage Guide](#-usage-guide)
- [NASA CEA2 Integration](#-nasa-cea2-integration)
- [Configuration](#-configuration)
- [Project Structure](#-project-structure)
- [Requirements](#-requirements)
- [License](#-license)

---

## 🔬 Overview

**Chemical Equilibrium Calculator** is a professional-grade desktop application for thermodynamic equilibrium calculations in chemical systems. Built with a modular MVC architecture, it provides precise equilibrium composition analysis, thermodynamic property calculations, and comprehensive performance evaluation.

The software integrates with **NASA's CEA2** for high-precision calculations while maintaining a robust fallback ideal gas calculator.

---

## ✨ Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Equilibrium Calculations** | Complex multi-species chemical equilibrium analysis |
| **Thermodynamic Properties** | Temperature, pressure, enthalpy, entropy computations |
| **Nozzle Design** | Isentropic flow analysis and geometric optimization |
| **Batch Processing** | Parametric sweeps and sensitivity analysis |
| **Visualization** | Interactive plots, radar charts, and performance graphs |

### User Interface

| Feature | Description |
|---------|-------------|
| **Searchable Species Database** | 129 oxidizers + 397 fuels with auto-completion |
| **Real-time Validation** | Pre-flight checks before calculation |
| **Export Capabilities** | CSV and Excel export with formatted results |
| **Multi-language** | English and French interfaces |

### Analysis Tools (25+)

| Category | Tools |
|----------|-------|
| **Nozzle & Geometry** | Nozzle Designer, Chamber Sizer, Contraction Ratio |
| **Thermal & Cooling** | Heat Transfer, Regenerative Cooling, Instability Predictor |
| **Mission & Performance** | Delta-V Calculator, Orbit Insertion, Staging Optimiser |
| **Advanced Analysis** | Sensitivity Analysis, DOE, Composition Tracking |
| **Export & Scripting** | LaTeX Generator, Python Script, Unit Converter |

---

## 🚀 Installation

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Step 1: Clone Repository

```bash
git clone https://github.com/khadev/Chemical-Equilibrium-Calculator.git
cd Chemical-Equilibrium-Calculator
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run Application

```bash
python main.py
```

---

## 🎯 Quick Start

### Basic Calculation Workflow

```
1. Select Oxidizer    →  Choose from dropdown (e.g., NH₄ClO₄)
2. Select Fuel       →  Choose from dropdown (e.g., HTPB)
3. Set Conditions    →  Adjust Pc, O/F ratio, Ae/At
4. Run Calculation   →  Click "Calculate" or press Ctrl+R
5. Analyze Results   →  Review performance metrics and plots
```

### Example Formulation

| Parameter | Value |
|-----------|-------|
| **Oxidizer** | NH₄ClO₄(I) |
| **Oxidizer Temp** | 298.0 K |
| **Oxidizer Wt** | 72.0 % |
| **Fuel** | HTPB |
| **Fuel Temp** | 298.0 K |
| **Fuel Wt** | 18.0 % |
| **Chamber Pressure** | 50.0 bar |
| **O/F Ratio** | 2.5 |
| **Area Ratio** | 10.0 |

### Expected Results

| Metric | Value |
|--------|-------|
| Specific Impulse (Isp) | ~250 s (2450 m/s) |
| Characteristic Velocity (C*) | ~1580 m/s |
| Thrust Coefficient (Cf) | 1.55-1.65 |
| Chamber Temperature (Tc) | ~3300 K |

---

## 🚀 NASA CEA2 Integration

This application integrates with **NASA's Chemical Equilibrium with Applications (CEA2)** software for high-precision calculations.

### About NASA CEA2

> CEA computes the equilibrium composition of mixtures via free-energy minimization, and uses the resulting product concentrations to determine thermodynamic and transport properties.

**Source Code:** [github.com/nasa/cea](https://github.com/nasa/cea)  
**Documentation:** [nasa.github.io/cea](https://nasa.github.io/cea/)

### Installation of NASA CEA2 (Optional)

```bash
# Install via pip (recommended)
python -m pip install cea

# Or clone from source
git clone https://github.com/nasa/cea.git
cd cea
mkdir build && cd build
cmake ..
cmake --build .
cmake --install .
```

### Configuration in the Application

1. Open **Settings** (`Ctrl+,`)
2. Set paths to:
   - `FCEA2.exe` (or `cea` executable)
   - `thermo.lib` (thermodynamic database)
   - `trans.lib` (transport properties database)
3. Click **Save**

---

## ⚙️ Configuration

### Unit Preferences

| Unit Type | Options |
|-----------|---------|
| **Pressure** | bar, psi, MPa |
| **Temperature** | K, °C |

### Language Selection

- English (`Settings → English`)
- Français (`Settings → Français`)

### Keyboard Shortcuts

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

## 📁 Project Structure
 
```
Chemical-Equilibrium-Calculator/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── Screenshots/            # Application screenshots
│   ├── add-react.png
│   ├── main.png
│   ├── nozzle.png
│   ├── performance.png
│   ├── plots.png
│   ├── settings.png
│   └── startwin.png
├── config/                 # Configuration files
├── database/               # Species database
├── engine/                 # Calculation logic
├── models/                 # Data layer
└── ui/                     # User interface
    ├── widgets/            # UI components
    └── dialogs/            # Popup dialogs
```

---

## 📦 Requirements

```txt
PySide6>=6.6.0      # Qt6 Python bindings
matplotlib>=3.7.0   # Plotting library
numpy>=1.24.0       # Numerical operations
pandas>=2.0.0       # Data export
qtawesome>=1.3.0    # Icons
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| **ModuleNotFoundError** | Run `pip install -r requirements.txt` |
| **No species in dropdown** | Verify `databasecea.txt` exists in `database/` folder |
| **Plots not displaying** | Install matplotlib: `pip install matplotlib` |
| **FCEA2 execution error** | Configure CEA2 paths in Settings |
| **CEA2 not found** | Install via `pip install cea` or build from [source](https://github.com/nasa/cea) |

---

## 📄 License

```
Chemical Equilibrium Calculator
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

## 🙏 Acknowledgments

- **NASA** - For the CEA2 software and thermodynamic databases
- **NASA Glenn Research Center** - Original CEA development
- **Qt Company** - PySide6 framework

---

## 👨‍💻 Author

**Oukil Khaled Ibn Elwalid**

---

<div align="center">

**🌡️ Made for the scientific community**

[Report Bug](https://github.com/khadev/Chemical-Equilibrium-Calculator/issues) · [Request Feature](https://github.com/khadev/Chemical-Equilibrium-Calculator/issues) · [NASA CEA Repository](https://github.com/nasa/cea)

</div>

