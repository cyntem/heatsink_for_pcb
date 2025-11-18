## Specification: FreeCAD Workbench for generating and thermally evaluating CNC-friendly heatsinks

### 1. Purpose

Create a FreeCAD (1.0+) Python Workbench with a GUI that supports:

1. Parametric generation of a CNC-manufacturable heatsink 3D model (milled aluminum/copper).
2. Estimation of how much heat that heatsink can dissipate with:
   * Ambient temperature of 25 °C.
   * Typical relative humidity of 50 % at 1 atm.
3. Plotting how dissipated power changes with:
   * Ambient temperature.
   * Relative humidity.

All calculations are approximate engineering estimates, not CFD.

---

### 2. Technology requirements

* Environment: FreeCAD 1.0+, Python 3.x (the interpreter bundled with FreeCAD). ([Wikipedia][1])
* Deliver the functionality as a separate **Workbench** (e.g., `HeatsinkDesigner`).
* Implementation language: Python.
* GUI: Qt through FreeCAD (PySide2 or PySide6, whichever is available in the build).
* Third-party libraries (import normally; when missing, present clear error messages to the user):
  * `ht` — Heat Transfer library from ChEDL for convection coefficients and thermal regimes. ([forum.freecad.org][2])
  * `fluids` (ChEDL) — air properties (density, viscosity, etc.). ([PyPI][3])
  * `numpy` — calculations.
  * `matplotlib` — plotting.
* Units:
  * GUI: dimensions in **mm**, power in **W**.
  * Calculations: convert to **SI units (meters, Kelvin, Pascal)**.

---

### 3. Supported heatsink types in the first release

Implement at least four heatsink types that can realistically be milled on a CNC:

1. **Solid plate** — a plain plate (no fins).
2. **Straight milled fins** — parallel fins:
   * Fins along the long side.
   * Parameters: fin height, fin thickness, fin pitch, base thickness.
3. **Crosscut (grid)** — orthogonal fins along X and Y forming square pins:
   * Parameters: pin height, grid pitch, groove width (thus pin size).
4. **Pin-fin (square pins)** — an array of square pins:
   * Parameters: pin cross-section (square), pin pitch, pin height, base thickness.

**Architecture requirement:** the heatsink type must be expressed via an abstraction/class/dictionary so new types (e.g., channel/water blocks) can be added without rewriting the Workbench core.

---

### 4. CNC constraints and default parameters

Provide **default values** aligned with typical desktop CNC capabilities:

Common parameters (all types):

* `default_tool_diam_mm = 3.0` — minimum tool diameter.
* `min_fin_thickness_mm = 2.0` — fin thickness ≥ 2/3 of tool diameter.
* `min_fin_gap_mm = 3.0` — minimum gap for tool clearance.
* Corner radii should be ≥ `tool_diam/2`.

Example defaults:

1. **Straight milled fins**
   * Fin thickness: 2.0 mm.
   * Fin gap: 3.0 mm.
   * Base thickness: 5.0 mm.
   * Fin height: 20.0 mm (user-adjustable).

2. **Crosscut**
   * Groove width: 3.0 mm.
   * Square pin size: 3.0 mm.
   * Pin height: 15.0 mm.
   * Base thickness: 5.0 mm.

3. **Pin-fin**
   * Pin cross-section: 5×5 mm.
   * Pitch on both axes: 8 mm.
   * Pin height: 20.0 mm.
   * Base thickness: 5.0 mm.

4. **Solid plate**
   * Plate thickness defined by the user; default 10 mm.

Keep all defaults in one place (e.g., dictionary `DEFAULT_CNC_PARAMS`) so users can adjust them.

---

### 5. Modes of operation (two primary modes)

Provide a GUI toggle (radio/combo):

1. **Mode 1: Surface/Sketch Mode**
2. **Mode 2: Dimension Mode**

#### 5.1. Mode 1 — working from a face or sketch

Flow:

1. The user selects in FreeCAD either:
   * a planar face of a 3D body; or
   * a 2D sketch with a closed contour (rectangle or any planar loop).
2. They click **"Heatsink from Face/Sketch"** (toolbar button in the Workbench).
3. A Task Panel opens with parameters:
   * **Heatsink type selection** (combobox): Solid plate, Straight milled fins, Crosscut, Pin-fin.
   * **Heatsink parameters** (dependent on type; fields prefilled with CNC defaults):
     * Height (mm).
     * Fin/pin thickness (mm).
     * Pitch/number of fins or pins.
     * Base thickness (mm).
     * Fin orientation (along X or Y for straight fins).
     * Flag “use CNC defaults”.
   * **Thermal parameters:**
     * Component power `P_load` (W) — optional. If omitted, only the maximum dissipated power at the specified ΔT is computed (see section 6).
     * Ambient temperature `T_amb` (°C), default 25.
     * Relative humidity `RH` (%), default 50.
   * **Buttons:**
     * `Generate 3D model` — creates a solid heatsink object constrained to the selected face/sketch.
     * `Thermal calculation` — performs the calculation (section 6) and outputs:
       * maximum dissipated power at the specified ΔT; and
       * if `P_load` is provided, an estimate of heatsink temperature.
     * `Chart (T, RH)` — plots dissipated power versus T and RH (section 7).
4. Geometry:
   * The heatsink base matches the selected face/contour.
   * The heatsink grows **outward** from the face (along the normal), not into the part.

#### 5.2. Mode 2 — dimension-driven (optimal heatsink)

Second tool: **"Heatsink by Dimensions"**.

Flow:

1. The user does not need to select anything.
2. In the Task Panel they enter:
   * Heatsink width `W` (mm).
   * Heatsink length `L` (mm).
   * Allowed height `H_max` (mm).
   * (Optional) dissipated power `P_load` (W).
3. Type selection modes:
   * Toggle:
     * `Type: Auto (choose optimal)`
     * `Type: Manual (pick from list)` — enables the same type list as mode 1.
4. With `Type: Auto`:
   * The code **iterates over all available heatsink types** and for each tests reasonable configurations under:
     * height ≤ `H_max`;
     * gaps/thickness respect `DEFAULT_CNC_PARAMS`.
   * For each candidate it calculates:
     * total effective heat-transfer area;
     * convection coefficient for natural convection;
     * **maximum dissipated power at the specified ΔT** (section 6).
   * It chooses the configuration with **minimum thermal resistance** (or maximum dissipated power).
5. Buttons:
   * `Pick and generate` — creates the 3D model of the chosen “optimal” heatsink.
   * `Thermal calculation` — outputs numeric results.
   * `Chart (T, RH)` — builds the plot.

---

### 6. Thermal calculation

The thermal model uses a simplified 1D chain: heat source → conduction through the base → convection to air. It should:

1. Check whether `ht` and `fluids` are installed. If missing, show clear messages and use built-in approximate coefficients so the module still works without those dependencies.
2. Use thermal conductivity from a material library (e.g., aluminum alloys, copper/brass, stainless steel). Default material: common aluminum alloy suitable for heatsinks.
3. Compute:
   * Convective resistance based on natural convection correlations (`ht/fluids` when available, otherwise simplified correlations).
   * Conduction resistance through the base thickness.
4. Two modes:
   * **Without specified `P_load`:** compute `Q_max` — maximum dissipated power at target over-temperature ΔT (source above ambient).
   * **With specified `P_load`:** compute resulting over-temperature and surface temperature.
5. Ensure numeric stability and avoid crashes on invalid input (negative dimensions, zero areas, missing faces).

---

### 7. Plotting

Use `matplotlib` when available to plot dissipated power versus:

* Ambient temperature `T_amb` at fixed relative humidity.
* Relative humidity `RH` at fixed ambient temperature.

When the library is missing, show a readable error message instead of failing.

---

### 8. Geometry creation strategy

1. Geometry is needed both for a visible 3D model and for approximating effective surface area for thermal calculations.
2. For Task Panel mode 1 (face/sketch):
   * Base outline comes from the selected face or sketch; holes should be preserved where possible.
   * The base thickness follows user input.
   * Fins grow outward from the selected face.
3. For mode 2 (dimension driven):
   * Create a rectangle `L × W` on the chosen base plane (e.g., XY).
   * Build the base and fins similarly.
4. All parameters (height, pitch, etc.) must be **parametric** (stored as FreeCAD object properties) so users can adjust values later and recompute the model.

---

### 9. Suggested project structure

Recommended (not strict):

* Workbench folder, e.g., `HeatsinkDesigner`:
  * `Init.py` — module registration.
  * `InitGui.py` — Workbench registration, icons, commands. ([forum.freecad.org][5])
  * `heatsink_types.py` — descriptions of heatsink types with geometry defaults.
  * `cnc_defaults.py` — recommended CNC parameters.
  * `thermal_model.py` — thermal computations (`ht`, `fluids`, `numpy`).
  * `geometry_builder.py` — FreeCAD geometry builders for each heatsink type.
  * `gui_face_mode.py` — Task Panel logic for mode 1.
  * `gui_dim_mode.py` — Task Panel logic for mode 2.
  * `icons/` — command/Workbench icons.

---

### 10. Non-functional requirements

* Code should be modular (GUI / geometry / calculations).
* Provide comments and docstrings for key functions.
* Error handling:
  * Do not crash when dependencies are missing; present informative messages.
  * Validate inputs: no negative lengths, non-zero dimensions, height > 0, pitch > thickness, etc.
* Tests (minimum):
  * Unit tests for `thermal_model.py` covering simple configurations (e.g., comparing with manual calculation `Q = h*A*ΔT` for a plain plate).
* Performance:
  * When choosing an “optimal heatsink” in mode 2, use a bounded search over parameter combinations so the tool does not hang.

[1]: https://en.wikipedia.org/wiki/FreeCAD
[2]: https://forum.freecad.org/
[3]: https://pypi.org/project/fluids/
[5]: https://forum.freecad.org/
