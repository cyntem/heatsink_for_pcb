# Heatsink Designer Workbench (FreeCAD)

The **HeatsinkDesignerWB** extension adds a FreeCAD tool for parametrically generating heatsinks and estimating their heat dissipation. The code is organized as a lightweight Python package that can live in the FreeCAD `Mod` folder and can also be used without the GUI for quick calculations.

## Features

- Four CNC-friendly heatsink types: solid plate, straight milled fins, crosscut grid, and pin-fin array.
- Two operating modes (face/sketch driven and dimension driven) suitable for a FreeCAD Task Panel.
- Simplified thermal calculations based on natural convection and fin efficiency.
- Plot generation for the relationship between dissipated power, ambient temperature, and humidity.
- Dependency checks for optional libraries (`ht`, `fluids`) with clear messages.

## Structure

- `HeatsinkDesigner/Init.py` and `HeatsinkDesigner/InitGui.py` — Workbench entry points that are safe to import even without FreeCAD GUI.
- `cnc_defaults.py` — minimal dimensions and recommended values for desktop CNC milling.
- `heatsink_types.py` — definitions of supported heatsink types and parameters.
- `geometry_builder.py` — approximate geometry construction and effective surface-area calculation.
- `thermal_model.py` — thermal calculations based on geometry and environment parameters.
- `gui_face_mode.py` and `gui_dim_mode.py` — logic for two Task Panel modes without binding to specific UI widgets.
- `icons/` — Workbench icon.
- `tests/` — minimal unit tests for the thermal module and geometry generator.

## Requirements

- Python 3.x (the version bundled with FreeCAD 1.0+).
- Recommended external packages: `numpy`, `matplotlib`, `ht`, `fluids`. If `ht` and `fluids` are missing, built-in approximate coefficients are used.

`requirements.txt` lists all optional dependencies. Install them using the Python interpreter bundled with FreeCAD:

- **Windows:** `"C:\\Program Files\\FreeCAD 1.0\\bin\\python.exe" -m pip install -r requirements.txt`
- **macOS (app bundle):** `/Applications/FreeCAD.app/Contents/Resources/bin/python3 -m pip install -r requirements.txt`
- **Linux (classic install):** `python3 -m pip install -r requirements.txt`
- **Linux Snap:** `snap run --shell freecad --command python3 -m pip install -r requirements.txt`

## Installation and launch in FreeCAD

1. Copy the `HeatsinkDesigner` folder into the `Mod` directory of your FreeCAD installation:
   - Classic installs: `~/.local/share/FreeCAD/Mod` (Linux), `%APPDATA%/FreeCAD/Mod` (Windows), `~/Library/Preferences/FreeCAD/Mod` (macOS);
   - Snap package (FreeCAD 1.0.2): `~/snap/freecad/common/Mod`.
2. Restart FreeCAD. The **HeatsinkDesigner** Workbench appears with two commands: generation from a face/sketch and generation from dimensions.
3. Each Task Panel shows parameters for the selected heatsink type plus buttons for model generation, thermal calculation, and chart creation.

> Starting with FreeCAD 1.0.2 the module initializes correctly even if `FreeCADGui.__spec__` is missing (typical for the Snap build).

## Usage without FreeCAD

The thermal portion can be used as a regular Python module:

```python
from HeatsinkDesigner.geometry_builder import build_geometry
from HeatsinkDesigner.thermal_model import Environment, estimate_heat_dissipation

details = build_geometry("straight_fins", (120.0, 80.0, 5.0), {
    "fin_height_mm": 20.0,
    "fin_thickness_mm": 2.0,
    "fin_gap_mm": 3.0,
})
result = estimate_heat_dissipation(details.geometry, Environment(), power_input_w=60)
print(result)
```

## Testing

Run the tests locally (requires `pytest`):

```bash
pytest
```

The command covers basic checks for the thermal calculations and geometry generation.
