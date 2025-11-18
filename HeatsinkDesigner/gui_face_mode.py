"""Task panel logic for face/sketch driven mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List

# ---------- logger -----------------------------------------------------------

try:
    import FreeCAD as App  # type: ignore
except Exception:  # pragma: no cover
    App = None  # type: ignore


def _log(msg: str) -> None:
    prefix = "[HSD] "
    if App is not None:
        App.Console.PrintMessage(prefix + msg + "\n")
    else:  # pragma: no cover
        print(prefix + msg)


def _log_err(msg: str) -> None:
    prefix = "[HSD-ERR] "
    if App is not None:
        App.Console.PrintError(prefix + msg + "\n")
    else:  # pragma: no cover
        print(prefix + msg)


# ---------- workbench module imports ---------------------------------------
try:
    from HeatsinkDesigner.geometry_builder import (
        BaseDimensions,
        GeometryDetails,
        build_geometry,
    )
except Exception:  # pragma: no cover
    from geometry_builder import (  # type: ignore[no-redef]
        BaseDimensions,
        GeometryDetails,
        build_geometry,
    )

try:
    from HeatsinkDesigner.heatsink_types import SUPPORTED_TYPES
except Exception:  # pragma: no cover
    from heatsink_types import SUPPORTED_TYPES  # type: ignore[no-redef]

try:
    from HeatsinkDesigner.thermal_model import (
        Environment,
        estimate_heat_dissipation,
        MATERIALS,
        DEFAULT_MATERIAL_KEY,
    )
except Exception:  # pragma: no cover
    from thermal_model import (  # type: ignore[no-redef]
        Environment,
        estimate_heat_dissipation,
        MATERIALS,
        DEFAULT_MATERIAL_KEY,
    )

try:
    from HeatsinkDesigner.heatsink_feature import create_heatsink_feature
except Exception:  # pragma: no cover
    from heatsink_feature import create_heatsink_feature  # type: ignore[no-redef]


# which parameter counts as "height" for each type
HEIGHT_PARAM_MAP: Dict[str, str] = {
    "solid_plate": "base_thickness_mm",
    "straight_fins": "fin_height_mm",
    "crosscut": "pin_height_mm",
    "pin_fin": "pin_height_mm",
}


@dataclass
class FaceSelection:
    """Represents a simplified face/sketch selection."""

    length_mm: float
    width_mm: float
    area_mm2: float
    shape: object  # TopoShape

    def base_dimensions(self, base_thickness_mm: float) -> BaseDimensions:
        return BaseDimensions(
            length_mm=self.length_mm,
            width_mm=self.width_mm,
            base_thickness_mm=base_thickness_mm,
        )


class FaceSketchController:
    """Encapsulates validation and generation logic for mode 1."""

    def __init__(self) -> None:
        self.selection: Optional[FaceSelection] = None

    def validate_selection(self) -> None:
        if self.selection is None:
            raise ValueError("No planar face or sketch is selected")
        if self.selection.length_mm <= 0 or self.selection.width_mm <= 0:
            raise ValueError("Face dimensions must be positive")

    def prepare_geometry(
        self,
        heatsink_type: str,
        params: Dict[str, float],
        base_thickness_mm: float,
        material_k: float,
    ) -> GeometryDetails:
        """Build GeometryDetails and scale areas to match the real face/sketch area."""
        self.validate_selection()
        if heatsink_type not in SUPPORTED_TYPES:
            raise ValueError("Unknown heatsink type")

        sel = self.selection
        if sel is None:
            raise ValueError("No face or sketch is selected")

        base_dims = sel.base_dimensions(base_thickness_mm)

        merged_params = dict(params)
        merged_params["material_conductivity_w_mk"] = material_k

        _log(
            f"prepare_geometry: type={heatsink_type}, base_dims=({base_dims.length_mm}, "
            f"{base_dims.width_mm}, {base_dims.base_thickness_mm}), params={merged_params}"
        )

        details = build_geometry(
            heatsink_type,
            (base_dims.length_mm, base_dims.width_mm, base_dims.base_thickness_mm),
            merged_params,
        )

        if sel.area_mm2 > 0:
            bbox_area_mm2 = sel.length_mm * sel.width_mm
            if bbox_area_mm2 > 0:
                scale = sel.area_mm2 / bbox_area_mm2
                details.geometry.base_area_m2 *= scale
                details.geometry.effective_area_m2 *= scale
                details.notes.append(
                    f"Thermal area scaled by factor {scale:.2f} "
                    f"to match real face/sketch area"
                )
                _log(f" prepare_geometry: scaled areas by factor {scale:.3f}")

        return details


# ---------- Qt Task Panel implementation ------------------------------------


def _load_qt_widgets():
    """Return QtWidgets module from PySide6/PySide2."""
    for name in ("PySide6", "PySide2"):
        try:
            module = __import__(name + ".QtWidgets", fromlist=["QtWidgets"])
            _log(f"Qt loaded from {name}")
            return module
        except ImportError:
            continue
    raise ImportError("Neither PySide6 nor PySide2 is available")


class FaceModeTaskPanel:
    """Qt Task Panel for face/sketch driven mode (mode 1)."""

    def __init__(self) -> None:
        QtWidgets = _load_qt_widgets()
        self._QtWidgets = QtWidgets
        self.controller = FaceSketchController()

        self._height_param_name: Optional[str] = None
        self._current_type_key: str = "straight_fins"  # default

        self.form = QtWidgets.QWidget()
        self._build_ui()
        _log("FaceModeTaskPanel initialized")

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self) -> None:
        QtWidgets = self._QtWidgets

        layout = QtWidgets.QVBoxLayout(self.form)

        header = QtWidgets.QLabel("<b>Heatsink from face/sketch</b>")
        header.setWordWrap(True)
        layout.addWidget(header)

        hint = QtWidgets.QLabel(
            "Select a planar face or sketch in the 3D view.\n"
            "Parameters and results are recalculated automatically.\n"
            "The button generates a parametric heatsink object along the outline."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Heatsink type
        type_row = QtWidgets.QHBoxLayout()
        type_label = QtWidgets.QLabel("Heatsink type:")
        self.type_combo = QtWidgets.QComboBox()
        self._type_keys: List[str] = list(SUPPORTED_TYPES.keys())
        for key in self._type_keys:
            hs_type = SUPPORTED_TYPES[key]
            self.type_combo.addItem(hs_type.label, userData=key)
        type_row.addWidget(type_label)
        type_row.addWidget(self.type_combo)
        layout.addLayout(type_row)

        # Heatsink parameters (except height)
        self.params_group = QtWidgets.QGroupBox("Geometric parameters (mm)")
        self.params_layout = QtWidgets.QFormLayout(self.params_group)
        self._param_widgets: Dict[str, "QtWidgets.QDoubleSpinBox"] = {}
        layout.addWidget(self.params_group)

        # Thermal parameters
        therm_group = QtWidgets.QGroupBox("Thermal parameters")
        self.therm_layout = QtWidgets.QFormLayout(therm_group)

        # 1) ΔT
        self.delta_t_spin = QtWidgets.QDoubleSpinBox()
        self.delta_t_spin.setRange(1.0, 200.0)
        self.delta_t_spin.setValue(40.0)
        self.delta_t_spin.setSuffix(" °C")
        self.therm_layout.addRow("Allowed over-temperature ΔT:", self.delta_t_spin)

        # Heatsink material
        self.material_combo = QtWidgets.QComboBox()
        self._material_keys = list(MATERIALS.keys())
        for key in self._material_keys:
            mat = MATERIALS[key]
            self.material_combo.addItem(mat.label, userData=key)
        if DEFAULT_MATERIAL_KEY in self._material_keys:
            idx = self._material_keys.index(DEFAULT_MATERIAL_KEY)
            self.material_combo.setCurrentIndex(idx)
        self.therm_layout.addRow("Heatsink material:", self.material_combo)

        # 2) analysis mode
        self.analysis_mode_combo = QtWidgets.QComboBox()
        self.analysis_mode_combo.addItem("Compute P_load from height", userData="h_to_q")
        self.analysis_mode_combo.addItem("Compute height from P_load", userData="q_to_h")
        self.therm_layout.addRow("Analysis mode:", self.analysis_mode_combo)

        # 3a) P_load
        self.power_label = QtWidgets.QLabel("P_load:")
        self.power_spin = QtWidgets.QDoubleSpinBox()
        self.power_spin.setRange(0.0, 1e6)
        self.power_spin.setDecimals(1)
        self.power_spin.setSuffix(" W")
        self.therm_layout.addRow(self.power_label, self.power_spin)

        # 3b) Height
        self.height_label = QtWidgets.QLabel("Height:")
        self.height_spin = QtWidgets.QDoubleSpinBox()
        self.height_spin.setRange(1.0, 1e6)
        self.height_spin.setDecimals(2)
        self.height_spin.setSingleStep(0.1)
        self.height_spin.setValue(20.0)
        self.height_spin.setSuffix(" mm")
        self.therm_layout.addRow(self.height_label, self.height_spin)

        layout.addWidget(therm_group)

        # Result
        self.result_label = QtWidgets.QLabel("Result has not been computed yet.")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_generate = QtWidgets.QPushButton("Generate a parametric 3D model")
        self.btn_chart = QtWidgets.QPushButton("Q_max(h) chart (current type)")

        self.btn_generate.clicked.connect(self._on_generate_clicked)
        self.btn_chart.clicked.connect(self._on_chart_clicked)

        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_chart)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        # Auto recalculation
        self.delta_t_spin.valueChanged.connect(self._update_result_label)
        self.power_spin.valueChanged.connect(self._update_result_label)
        self.height_spin.valueChanged.connect(self._update_result_label)
        self.material_combo.currentIndexChanged.connect(self._update_result_label)
        self.analysis_mode_combo.currentIndexChanged.connect(self._on_analysis_mode_changed)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        # Default type – Straight milled fins
        if "straight_fins" in self._type_keys:
            idx = self._type_keys.index("straight_fins")
            self.type_combo.setCurrentIndex(idx)
            self._current_type_key = "straight_fins"
        else:
            self._current_type_key = self.type_combo.itemData(
                self.type_combo.currentIndex()
            )

        self._on_type_changed(self.type_combo.currentIndex())
        _log("FaceModeTaskPanel UI built")

    # ----------------------------------------------------------- helpers -----
    def _current_material(self):
        key = self.material_combo.currentData()
        if not key:
            key = DEFAULT_MATERIAL_KEY
        mat = MATERIALS.get(key)
        if mat is None:
            mat = MATERIALS[DEFAULT_MATERIAL_KEY]
        return mat

    def _current_material_key(self) -> str:
        key = self.material_combo.currentData()
        if not key:
            key = DEFAULT_MATERIAL_KEY
        return str(key)

    def _on_analysis_mode_changed(self, index: int) -> None:
        mode = self.analysis_mode_combo.currentData()
        _log(f"_on_analysis_mode_changed: mode={mode}")
        if mode == "h_to_q":
            self.power_label.setVisible(False)
            self.power_spin.setVisible(False)
            self.height_label.setVisible(True)
            self.height_spin.setVisible(True)
        else:
            self.power_label.setVisible(True)
            self.power_spin.setVisible(True)
            self.height_label.setVisible(False)
            self.height_spin.setVisible(False)
        self._update_result_label()

    def _on_type_changed(self, index: int) -> None:
        QtWidgets = self._QtWidgets
        key = self.type_combo.itemData(index)
        if not key:
            key = self._type_keys[0]
        self._current_type_key = key
        _log(f"_on_type_changed: type={key}")

        hs_type = SUPPORTED_TYPES[key]
        defaults = hs_type.default_parameters()
        self._height_param_name = HEIGHT_PARAM_MAP.get(key)

        while self.params_layout.rowCount():
            self.params_layout.removeRow(0)
        self._param_widgets.clear()

        height_default = 20.0
        height_min = 1.0

        for param in hs_type.parameters:
            if param.name == self._height_param_name:
                height_default = defaults.get(param.name, max(param.min_value, 1.0))
                height_min = max(param.min_value, 0.1)
                continue

            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setSingleStep(0.1)
            spin.setRange(param.min_value, 1e6)
            spin.setValue(defaults.get(param.name, max(param.min_value, 0.0)))
            spin.setSuffix(" " + param.unit)
            self.params_layout.addRow(param.description + ":", spin)
            self._param_widgets[param.name] = spin
            spin.valueChanged.connect(self._update_result_label)
            _log(
                f" _on_type_changed: param widget {param.name} "
                f"default={spin.value()}"
            )

        self.height_spin.blockSignals(True)
        self.height_spin.setRange(height_min, 1e6)
        self.height_spin.setValue(height_default)
        self.height_spin.blockSignals(False)
        _log(
            f" _on_type_changed: height_param={self._height_param_name}, "
            f"height_default={height_default}"
        )

        self._on_analysis_mode_changed(self.analysis_mode_combo.currentIndex())

    def _update_selection(self) -> bool:
        try:
            import FreeCADGui as Gui  # type: ignore[import]
        except ImportError:
            self.result_label.setText("FreeCADGui is not available.")
            _log_err("_update_selection: FreeCADGui not available")
            return False

        sel_ex = Gui.Selection.getSelectionEx()
        if not sel_ex:
            self.result_label.setText("No planar face or sketch is selected.")
            _log("_update_selection: no selection")
            return False

        sel_obj = sel_ex[0]
        shape = None
        if getattr(sel_obj, "SubObjects", None):
            if sel_obj.SubObjects:
                shape = sel_obj.SubObjects[0]
                _log("_update_selection: using first SubObject")
        if shape is None and hasattr(sel_obj.Object, "Shape"):
            shape = sel_obj.Object.Shape
            _log("_update_selection: using Object.Shape")

        if shape is None or not hasattr(shape, "BoundBox"):
            self.result_label.setText("Failed to extract dimensions of the selected object.")
            _log_err("_update_selection: shape is None or has no BoundBox")
            return False

        bb = shape.BoundBox
        length_mm = float(bb.XLength)
        width_mm = float(bb.YLength)

        area_mm2 = 0.0
        if hasattr(shape, "Area"):
            try:
                area_mm2 = float(shape.Area)
            except Exception as exc:
                _log_err(f"_update_selection: cannot get Area: {exc}")
                area_mm2 = 0.0
        if area_mm2 <= 0.0:
            area_mm2 = float(bb.XLength * bb.YLength)

        _log(
            "_update_selection: "
            f"Lx={length_mm:.3f} Ly={width_mm:.3f} area={area_mm2:.3f}"
        )

        self.controller.selection = FaceSelection(
            length_mm=length_mm,
            width_mm=width_mm,
            area_mm2=area_mm2,
            shape=shape,
        )
        return True

    # ------------------------------------------------------ core compute -----
    def _update_result_label(self) -> None:
        if not self._update_selection():
            return
        if self.controller.selection is None:
            self.result_label.setText("No face or sketch is selected.")
            return

        env = Environment()
        delta_t = float(self.delta_t_spin.value())
        mode = self.analysis_mode_combo.currentData()
        heatsink_type = self._current_type_key
        mat = self._current_material()

        params_common: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }

        _log(
            f"_update_result_label: mode={mode}, type={heatsink_type}, "
            f"params_common={params_common}"
        )

        if heatsink_type == "solid_plate":
            base_thickness_mm = float(self.height_spin.value())
        else:
            base_thickness_mm = float(params_common.get("base_thickness_mm", 5.0))
            if base_thickness_mm <= 0:
                base_thickness_mm = 5.0

        base_thickness_m = base_thickness_mm / 1000.0

        if mode == "h_to_q":
            params = dict(params_common)
            if heatsink_type == "solid_plate":
                base_thickness_mm = float(self.height_spin.value())
                base_thickness_m = base_thickness_mm / 1000.0

            if self._height_param_name:
                params[self._height_param_name] = float(self.height_spin.value())

            try:
                details = self.controller.prepare_geometry(
                    heatsink_type,
                    params,
                    base_thickness_mm,
                    material_k=mat.thermal_conductivity_w_mk,
                )
                res = estimate_heat_dissipation(
                    details.geometry,
                    env,
                    power_input_w=None,
                    target_overtemp_c=delta_t,
                    base_thickness_m=base_thickness_m,
                    material_conductivity_w_mk=mat.thermal_conductivity_w_mk,
                    base_contact_area_m2=details.geometry.base_area_m2,
                )
            except Exception as exc:
                self.result_label.setText(f"Thermal calculation error: {exc}")
                _log_err(f"_update_result_label h_to_q: {exc}")
                return

            self.result_label.setText(
                f"Mode: P_load from height\n"
                f"Heatsink type: {SUPPORTED_TYPES[heatsink_type].label}\n"
                f"Material: {mat.label}\n"
                f"Max allowable power P_load_max ≈ {res.heat_dissipation_w:.1f} W\n"
                f"at ΔT = {delta_t:.1f} °C."
            )
            return

        # mode: height from P_load
        p_req = float(self.power_spin.value())
        if p_req <= 0.0:
            self.result_label.setText(
                "Mode: height from P_load\n"
                "Provide P_load > 0 W."
            )
            return

        height_param = HEIGHT_PARAM_MAP.get(heatsink_type)
        if not height_param:
            self.result_label.setText("No height parameter is defined for this type.")
            return

        def q_for_height(h_mm: float) -> float:
            params = dict(params_common)
            if heatsink_type == "solid_plate":
                base_t_local_mm = h_mm
                base_t_local_m = base_t_local_mm / 1000.0
                params[height_param] = h_mm
            else:
                base_t_local_mm = base_thickness_mm
                base_t_local_m = base_t_local_mm / 1000.0
                params[height_param] = h_mm

            details = self.controller.prepare_geometry(
                heatsink_type,
                params,
                base_t_local_mm,
                material_k=mat.thermal_conductivity_w_mk,
            )
            res = estimate_heat_dissipation(
                details.geometry,
                env,
                power_input_w=None,
                target_overtemp_c=delta_t,
                base_thickness_m=base_t_local_m,
                material_conductivity_w_mk=mat.thermal_conductivity_w_mk,
                base_contact_area_m2=details.geometry.base_area_m2,
            )
            return res.heat_dissipation_w

        H_CAP = 1000.0
        h_min = 1.0
        q_min = q_for_height(h_min)
        _log(f"_update_result_label q_to_h: p_req={p_req}, q_min@1mm={q_min}")

        if q_min >= p_req:
            best_h = h_min
        else:
            h_low = h_min
            h_high = 2.0 * h_min
            best_h = None
            while h_high <= H_CAP:
                q_high = q_for_height(h_high)
                _log(f"  range expand: h_high={h_high}, q_high={q_high}")
                if q_high >= p_req:
                    for _ in range(20):
                        h_mid = 0.5 * (h_low + h_high)
                        q_mid = q_for_height(h_mid)
                        if q_mid >= p_req:
                            h_high = h_mid
                        else:
                            h_low = h_mid
                    best_h = h_high
                    break
                h_low = h_high
                h_high *= 2.0

        if best_h is None:
            self.result_label.setText(
                "Even with a height up to 1000 mm the required power is not reached.\n"
                "Reduce P_load or increase the base area."
            )
            _log("_update_result_label q_to_h: best_h is None")
            return

        h_round = max(1.0, round(best_h))
        self.height_spin.blockSignals(True)
        self.height_spin.setValue(h_round)
        self.height_spin.blockSignals(False)

        q_round = q_for_height(h_round)
        _log(
            f"_update_result_label q_to_h: best_h={best_h}, "
            f"h_round={h_round}, q_round={q_round}"
        )

        self.result_label.setText(
            "Mode: height from P_load\n"
            f"Heatsink type: {SUPPORTED_TYPES[heatsink_type].label}\n"
            f"Material: {mat.label}\n"
            f"Required height ≈ {h_round:.0f} mm\n"
            f"for P_load = {p_req:.1f} W and ΔT = {delta_t:.1f} °C.\n"
            f"Q_max at this height ≈ {q_round:.1f} W."
        )

    # ----------------------------------------------------------- callbacks ---
    def _on_generate_clicked(self) -> None:
        QtWidgets = self._QtWidgets

        _log("_on_generate_clicked: pressed")

        if not self._update_selection():
            return
        if self.controller.selection is None:
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "No face or sketch selected",
            )
            return

        params_common: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }

        heatsink_type = self._current_type_key
        if heatsink_type == "solid_plate":
            base_thickness_mm = float(self.height_spin.value())
        else:
            base_thickness_mm = float(params_common.get("base_thickness_mm", 5.0))
            if base_thickness_mm <= 0:
                base_thickness_mm = 5.0

        params = dict(params_common)
        if self._height_param_name:
            params[self._height_param_name] = float(self.height_spin.value())

        _log(
            f"_on_generate_clicked: type={heatsink_type}, "
            f"base_thickness={base_thickness_mm}, params={params}"
        )

        try:
            import FreeCAD as AppLocal  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "FreeCAD is not available for 3D model construction",
            )
            _log_err("_on_generate_clicked: FreeCAD import failed")
            return

        self.controller.validate_selection()
        sel = self.controller.selection

        try:
            obj = create_heatsink_feature(
                heatsink_type=heatsink_type,
                source_shape=sel.shape,
                base_thickness_mm=base_thickness_mm,
                params=params,
                material_key=self._current_material_key(),
                doc=AppLocal.ActiveDocument,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                f"3D model construction error:\n{exc}",
            )
            _log_err(f"_on_generate_clicked: create_heatsink_feature failed: {exc}")
            return

        AppLocal.Console.PrintMessage(
            f"[HeatsinkDesigner] Created parametric heatsink: {obj.Name} ({obj.Label})\n"
        )
        _log("_on_generate_clicked: object created successfully")

        self._update_result_label()

    def _on_chart_clicked(self) -> None:
        # logging is not critical here; leave as-is without extra noise
        QtWidgets = self._QtWidgets

        heatsink_type = self._current_type_key
        height_param = HEIGHT_PARAM_MAP.get(heatsink_type)
        if not height_param:
            QtWidgets.QMessageBox.warning(
                self.form,
                "Q_max(h) chart",
                "No height parameter is available for this type.",
            )
            return

        if not self._update_selection():
            return
        if self.controller.selection is None:
            return

        params_common: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }
        heatsink_type = self._current_type_key
        mat = self._current_material()
        env = Environment()
        delta_t = float(self.delta_t_spin.value())

        if heatsink_type == "solid_plate":
            base_thickness_mm0 = float(self.height_spin.value())
        else:
            base_thickness_mm0 = float(params_common.get("base_thickness_mm", 5.0))
            if base_thickness_mm0 <= 0:
                base_thickness_mm0 = 5.0

        try:
            import matplotlib.pyplot as plt  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "matplotlib library is not installed",
            )
            return

        h_center = float(self.height_spin.value())
        h_min = 1.0
        h_max = max(h_center * 2.0, h_center + 10.0, 10.0)
        steps = 12
        heights: List[float] = [
            h_min + (h_max - h_min) * i / (steps - 1) for i in range(steps)
        ]
        q_values: List[float] = []

        for h in heights:
            params = dict(params_common)
            if heatsink_type == "solid_plate":
                base_t_local_mm = h
                base_t_local_m = base_t_local_mm / 1000.0
                params[height_param] = h
            else:
                base_t_local_mm = base_thickness_mm0
                base_t_local_m = base_t_local_mm / 1000.0
                params[height_param] = h

            details = self.controller.prepare_geometry(
                heatsink_type,
                params,
                base_t_local_mm,
                material_k=mat.thermal_conductivity_w_mk,
            )
            res = estimate_heat_dissipation(
                details.geometry,
                env,
                power_input_w=None,
                target_overtemp_c=delta_t,
                base_thickness_m=base_t_local_m,
                material_conductivity_w_mk=mat.thermal_conductivity_w_mk,
                base_contact_area_m2=details.geometry.base_area_m2,
            )
            q_values.append(res.heat_dissipation_w)

        import matplotlib.pyplot as plt  # type: ignore

        plt.plot(heights, q_values, marker="o")
        plt.xlabel("Height, mm")
        plt.ylabel(f"Q_max at ΔT = {delta_t:.1f} °C, W")
        plt.title(f"Q_max(h) for type: {SUPPORTED_TYPES[heatsink_type].label}")
        plt.grid(True)
        plt.show()

        self._update_result_label()
