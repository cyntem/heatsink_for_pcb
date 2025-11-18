"""Task panel logic for dimension-driven mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# ---- workbench module imports ---------------------------------------------
try:
    from HeatsinkDesigner.geometry_builder import (
        BaseDimensions,
        GeometryDetails,
        build_geometry,
        create_heatsink_solid,
    )
except ImportError:  # pragma: no cover
    from geometry_builder import (  # type: ignore[no-redef]
        BaseDimensions,
        GeometryDetails,
        build_geometry,
        create_heatsink_solid,
    )

try:
    from HeatsinkDesigner.heatsink_types import SUPPORTED_TYPES
except ImportError:  # pragma: no cover
    from heatsink_types import SUPPORTED_TYPES  # type: ignore[no-redef]

try:
    from HeatsinkDesigner.cnc_defaults import DEFAULT_CNC_PARAMS
except ImportError:  # pragma: no cover
    from cnc_defaults import DEFAULT_CNC_PARAMS  # type: ignore[no-redef]

try:
    from HeatsinkDesigner.thermal_model import (
        Environment,
        estimate_heat_dissipation,
        MATERIALS,
        DEFAULT_MATERIAL_KEY,
    )
except ImportError:  # pragma: no cover
    from thermal_model import (  # type: ignore[no-redef]
        Environment,
        estimate_heat_dissipation,
        MATERIALS,
        DEFAULT_MATERIAL_KEY,
    )


HEIGHT_PARAM_MAP: Dict[str, str] = {
    "solid_plate": "base_thickness_mm",
    "straight_fins": "fin_height_mm",
    "crosscut": "pin_height_mm",
    "pin_fin": "pin_height_mm",
}


@dataclass
class DimensionInput:
    length_mm: float
    width_mm: float
    base_thickness_mm: float

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.length_mm, self.width_mm, self.base_thickness_mm)


# ---------- Qt Task Panel implementation ------------------------------------


def _load_qt_widgets():
    """Return QtWidgets module from PySide6/PySide2."""
    for name in ("PySide6", "PySide2"):
        try:
            module = __import__(name + ".QtWidgets", fromlist=["QtWidgets"])
            return module
        except ImportError:
            continue
    raise ImportError("Neither PySide6 nor PySide2 is available")


class DimensionModeTaskPanel:
    """Qt Task Panel for dimension-driven mode (mode 2)."""

    def __init__(self) -> None:
        QtWidgets = _load_qt_widgets()
        self._QtWidgets = QtWidgets

        self.form = QtWidgets.QWidget()
        self._build_ui()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self) -> None:
        QtWidgets = self._QtWidgets

        layout = QtWidgets.QVBoxLayout(self.form)

        header = QtWidgets.QLabel("<b>Heatsink by dimensions</b>")
        header.setWordWrap(True)
        layout.addWidget(header)

        hint = QtWidgets.QLabel(
            "Enter heatsink dimensions. Thermal parameters:\n"
            "  1) ΔT — allowed over-temperature;\n"
            "  2) analysis mode — P_load from height or height from P_load;\n"
            "  3) depending on the mode either P_load or height is provided.\n"
            "Results are recalculated automatically; the button builds a 3D model."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Dimensions
        dims_group = QtWidgets.QGroupBox("Dimensions (mm)")
        dims_layout = QtWidgets.QFormLayout(dims_group)

        self.length_spin = QtWidgets.QDoubleSpinBox()
        self.length_spin.setRange(1.0, 1e6)
        self.length_spin.setDecimals(2)
        self.length_spin.setSingleStep(0.1)
        self.length_spin.setValue(100.0)
        self.length_spin.setSuffix(" mm")
        dims_layout.addRow("Length L:", self.length_spin)

        self.width_spin = QtWidgets.QDoubleSpinBox()
        self.width_spin.setRange(1.0, 1e6)
        self.width_spin.setDecimals(2)
        self.width_spin.setSingleStep(0.1)
        self.width_spin.setValue(50.0)
        self.width_spin.setSuffix(" mm")
        dims_layout.addRow("Width W:", self.width_spin)

        self.base_thickness_spin = QtWidgets.QDoubleSpinBox()
        self.base_thickness_spin.setRange(0.5, 1e6)
        self.base_thickness_spin.setDecimals(2)
        self.base_thickness_spin.setSingleStep(0.1)
        self.base_thickness_spin.setValue(5.0)
        self.base_thickness_spin.setSuffix(" mm")
        dims_layout.addRow("Base thickness:", self.base_thickness_spin)

        layout.addWidget(dims_group)

        # Thermal parameters
        therm_group = QtWidgets.QGroupBox("Thermal parameters")
        self.therm_layout = QtWidgets.QFormLayout(therm_group)

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

        self.analysis_mode_combo = QtWidgets.QComboBox()
        self.analysis_mode_combo.addItem("Compute P_load from height", userData="h_to_q")
        self.analysis_mode_combo.addItem("Compute height from P_load", userData="q_to_h")
        self.therm_layout.addRow("Analysis mode:", self.analysis_mode_combo)

        # parameter depending on mode
        self.power_label = QtWidgets.QLabel("P_load:")
        self.power_spin = QtWidgets.QDoubleSpinBox()
        self.power_spin.setRange(0.0, 1e6)
        self.power_spin.setDecimals(1)
        self.power_spin.setSuffix(" W")
        self.therm_layout.addRow(self.power_label, self.power_spin)

        self.height_label = QtWidgets.QLabel("Height (working):")
        self.height_spin = QtWidgets.QDoubleSpinBox()
        self.height_spin.setRange(1.0, 1e6)
        self.height_spin.setDecimals(2)
        self.height_spin.setSingleStep(0.1)  # step 0.1 mm
        self.height_spin.setValue(20.0)
        self.height_spin.setSuffix(" mm")
        self.therm_layout.addRow(self.height_label, self.height_spin)

        layout.addWidget(therm_group)

        # Type selection
        type_group = QtWidgets.QGroupBox("Heatsink type")
        type_layout = QtWidgets.QHBoxLayout(type_group)

        type_label = QtWidgets.QLabel("Type:")
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem("Auto (pick optimal)", userData="__auto__")
        self._type_keys: List[str] = list(SUPPORTED_TYPES.keys())
        for key in self._type_keys:
            self.type_combo.addItem(SUPPORTED_TYPES[key].label, userData=key)

        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo)

        layout.addWidget(type_group)

        # Result
        self.result_label = QtWidgets.QLabel("Result has not been computed yet.")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_pick_generate = QtWidgets.QPushButton("Pick and generate")
        self.btn_chart = QtWidgets.QPushButton("Q_max(h) chart (all types)")

        self.btn_pick_generate.clicked.connect(self._on_generate_clicked)
        self.btn_chart.clicked.connect(self._on_chart_clicked)

        btn_row.addWidget(self.btn_pick_generate)
        btn_row.addWidget(self.btn_chart)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        # Auto recalculation
        for spin in (
            self.length_spin,
            self.width_spin,
            self.base_thickness_spin,
            self.delta_t_spin,
            self.power_spin,
            self.height_spin,
        ):
            spin.valueChanged.connect(self._update_result_label)

        self.type_combo.currentIndexChanged.connect(self._update_result_label)
        self.material_combo.currentIndexChanged.connect(self._update_result_label)
        self.analysis_mode_combo.currentIndexChanged.connect(self._on_analysis_mode_changed)

        self._on_analysis_mode_changed(self.analysis_mode_combo.currentIndex())
        self._update_result_label()

    # ----------------------------------------------------------- helpers -----
    def _current_material(self):
        key = self.material_combo.currentData()
        if not key:
            key = DEFAULT_MATERIAL_KEY
        mat = MATERIALS.get(key)
        if mat is None:
            mat = MATERIALS[DEFAULT_MATERIAL_KEY]
        return mat

    def _on_analysis_mode_changed(self, index: int) -> None:
        mode = self.analysis_mode_combo.currentData()
        if mode == "h_to_q":
            # compute P_load from height → height visible
            self.power_label.setVisible(False)
            self.power_spin.setVisible(False)
            self.height_label.setVisible(True)
            self.height_spin.setVisible(True)
        else:
            # compute height from P_load → P_load visible
            self.power_label.setVisible(True)
            self.power_spin.setVisible(True)
            self.height_label.setVisible(False)
            self.height_spin.setVisible(False)
        self._update_result_label()

    def _dimension_input(self) -> Optional[DimensionInput]:
        length = float(self.length_spin.value())
        width = float(self.width_spin.value())
        base_t = float(self.base_thickness_spin.value())
        if length <= 0 or width <= 0 or base_t <= 0:
            self.result_label.setText(
                "Length, width, and base thickness must be greater than zero."
            )
            return None
        return DimensionInput(length_mm=length, width_mm=width, base_thickness_mm=base_t)

    def _default_params_for_type(
        self, type_key: str, dim: DimensionInput, use_height_spin: bool
    ) -> Dict[str, float]:
        params = dict(DEFAULT_CNC_PARAMS.get(type_key, {}))
        hp = HEIGHT_PARAM_MAP.get(type_key)
        if use_height_spin and hp:
            params[hp] = float(self.height_spin.value())
        return params

    # ----------------------------------------------------- core computation ---
    def _find_height_for_type(
        self,
        type_key: str,
        dim: DimensionInput,
        delta_t: float,
        p_req: float,
        material_k: float,
    ) -> Optional[float]:
    """Find height for this type given required power (without H_max)."""
        env = Environment()
        hp = HEIGHT_PARAM_MAP.get(type_key)
        if not hp:
            return None

        params_base = self._default_params_for_type(type_key, dim, use_height_spin=False)
        params_base["material_conductivity_w_mk"] = material_k

        H_CAP = 1000.0  # 1 m

        def q_for_height(h_mm: float) -> float:
            p = dict(params_base)
            if type_key == "solid_plate":
                base_t_local_mm = h_mm
            else:
                base_t_local_mm = dim.base_thickness_mm
            base_t_local_m = base_t_local_mm / 1000.0

            p[hp] = h_mm
            details = build_geometry(type_key, dim.to_tuple(), p)
            res = estimate_heat_dissipation(
                details.geometry,
                env,
                power_input_w=None,
                target_overtemp_c=delta_t,
                base_thickness_m=base_t_local_m,
                material_conductivity_w_mk=material_k,
                base_contact_area_m2=details.geometry.base_area_m2,
            )
            return res.heat_dissipation_w

        # search from 1 mm so the height can also decrease
        h_min = 1.0
        q_min = q_for_height(h_min)
        if q_min >= p_req:
            return h_min

        h_low = h_min
        h_high = 2.0 * h_min

        while h_high <= H_CAP:
            q_high = q_for_height(h_high)
            if q_high >= p_req:
                # binary search
                for _ in range(20):
                    h_mid = 0.5 * (h_low + h_high)
                    q_mid = q_for_height(h_mid)
                    if q_mid >= p_req:
                        h_high = h_mid
                    else:
                        h_low = h_mid
                return h_high
            h_low = h_high
            h_high *= 2.0

        return None

    def _compute_best_config(
        self,
    ) -> Tuple[Optional[str], Optional[Dict[str, float]], Optional[GeometryDetails], str]:
    """Compute the best option for the current analysis mode without generating 3D."""
        dim = self._dimension_input()
        if dim is None:
            return None, None, None, "Invalid dimensions."

        delta_t = float(self.delta_t_spin.value())
        env = Environment()
        mode = self.analysis_mode_combo.currentData()
        current_data = self.type_combo.currentData()
        auto_mode = current_data == "__auto__"
        p_req = float(self.power_spin.value())
        mat = self._current_material()

        base_thickness_m = dim.base_thickness_mm / 1000.0

        # ----- mode: P_load from height -----
        if mode == "h_to_q":
            best_type_key: Optional[str] = None
            best_params: Optional[Dict[str, float]] = None
            best_details: Optional[GeometryDetails] = None
            best_q: Optional[float] = None

            type_list = self._type_keys if auto_mode else [str(current_data)]
            for type_key in type_list:
                params = self._default_params_for_type(
                    type_key,
                    dim,
                    use_height_spin=True,
                )
                params["material_conductivity_w_mk"] = mat.thermal_conductivity_w_mk
                # Base thickness: for plate use height, for others use dim.base_thickness_mm
                if type_key == "solid_plate":
                    base_t_mm = float(self.height_spin.value())
                else:
                    base_t_mm = dim.base_thickness_mm
                base_t_m = base_t_mm / 1000.0

                try:
                    details = build_geometry(type_key, dim.to_tuple(), params)
                    res = estimate_heat_dissipation(
                        details.geometry,
                        env,
                        power_input_w=None,
                        target_overtemp_c=delta_t,
                        base_thickness_m=base_t_m,
                        material_conductivity_w_mk=mat.thermal_conductivity_w_mk,
                        base_contact_area_m2=details.geometry.base_area_m2,
                    )
                except Exception:
                    continue
                if best_q is None or res.heat_dissipation_w > best_q:
                    best_q = res.heat_dissipation_w
                    best_type_key = type_key
                    best_params = params
                    best_details = details

            if best_type_key is None or best_params is None or best_details is None:
                return None, None, None, "Failed to find a configuration."

            label = SUPPORTED_TYPES[best_type_key].label
            text = (
                "Mode: P_load from height\n"
                f"Heatsink type: {label}\n"
                f"Material: {mat.label}\n"
                f"Max allowable power P_load_max ≈ {best_q:.1f} W\n"
                f"at ΔT = {delta_t:.1f} °C."
            )
            return best_type_key, best_params, best_details, text

        # ----- mode: height from P_load -----
        if p_req <= 0.0:
            return None, None, None, "Mode: height from P_load. Provide P_load > 0 W."

        type_list = self._type_keys if auto_mode else [str(current_data)]

        best_type_key: Optional[str] = None
        best_h: Optional[float] = None

        for type_key in type_list:
            h_local = self._find_height_for_type(
                type_key,
                dim,
                delta_t,
                p_req,
                material_k=mat.thermal_conductivity_w_mk,
            )
            if h_local is None:
                continue
            if best_h is None or h_local < best_h:
                best_h = h_local
                best_type_key = type_key

        if best_type_key is None or best_h is None:
            return (
                None,
                None,
                None,
                "Could not pick a type and height for the requested power.\n"
                "Reduce P_load or increase the base area.",
            )

        hp_final = HEIGHT_PARAM_MAP.get(best_type_key)
        params = self._default_params_for_type(
            best_type_key,
            dim,
            use_height_spin=False,
        )
        params["material_conductivity_w_mk"] = mat.thermal_conductivity_w_mk
        if hp_final:
            h_round = max(1.0, round(best_h))
            params[hp_final] = h_round

            # Base thickness
            if best_type_key == "solid_plate":
                base_t_mm_final = h_round
            else:
                base_t_mm_final = dim.base_thickness_mm
            base_t_m_final = base_t_mm_final / 1000.0

            details = build_geometry(best_type_key, dim.to_tuple(), params)
            res = estimate_heat_dissipation(
                details.geometry,
                env,
                power_input_w=None,
                target_overtemp_c=delta_t,
                base_thickness_m=base_t_m_final,
                material_conductivity_w_mk=mat.thermal_conductivity_w_mk,
                base_contact_area_m2=details.geometry.base_area_m2,
            )

            # update height in UI
            self.height_spin.blockSignals(True)
            self.height_spin.setValue(h_round)
            self.height_spin.blockSignals(False)

            label = SUPPORTED_TYPES[best_type_key].label
            text = (
                "Mode: height from P_load\n"
                f"Heatsink type: {label}\n"
                f"Material: {mat.label}\n"
                f"Required height ≈ {h_round:.0f} mm\n"
                f"for P_load = {p_req:.1f} W and ΔT = {delta_t:.1f} °C.\n"
                f"Q_max at this height ≈ {res.heat_dissipation_w:.1f} W."
            )
            return best_type_key, params, details, text

        return None, None, None, "Failed to compute height."

    # ----------------------------------------------------- label + 3D --------
    def _update_result_label(self) -> None:
        type_key, params, details, text = self._compute_best_config()
        self.result_label.setText(text)

    def _on_generate_clicked(self) -> None:
        QtWidgets = self._QtWidgets
        type_key, params, details, text = self._compute_best_config()
        self.result_label.setText(text)

        if type_key is None or params is None:
            return

        dim = self._dimension_input()
        if dim is None:
            return

        base_dims = BaseDimensions(
            length_mm=dim.length_mm,
            width_mm=dim.width_mm,
            base_thickness_mm=dim.base_thickness_mm,
        )

        try:
            import FreeCAD as App  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "FreeCAD is not available for 3D model construction",
            )
            return

        try:
            obj = create_heatsink_solid(
                type_key,
                base_dims,
                params,
                doc=App.ActiveDocument,
            )
        except Exception as exc:  # pragma: no cover - GUI only
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                f"3D model construction error:\n{exc}",
            )
            return

        App.Console.PrintMessage(
            f"[HeatsinkDesigner] Created heatsink: {obj.Name} ({obj.Label})\n"
        )

    # ----------------------------------------------------- Q(h) chart -------
    def _on_chart_clicked(self) -> None:
        """Plot Q_max(h) for all heatsink types on one chart."""
        QtWidgets = self._QtWidgets
        dim = self._dimension_input()
        if dim is None:
            return

        try:
            import matplotlib.pyplot as plt  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "matplotlib library is not installed",
            )
            return

        env = Environment()
        delta_t = float(self.delta_t_spin.value())
        mat = self._current_material()

        H_PLOT_MAX = 100.0  # mm – plotting range
        h_min = 1.0
        h_max = max(float(self.height_spin.value()) * 2.0, H_PLOT_MAX)
        steps = 12
        heights: List[float] = [
            h_min + (h_max - h_min) * i / (steps - 1) for i in range(steps)
        ]

        for type_key in self._type_keys:
            hp = HEIGHT_PARAM_MAP.get(type_key)
            if not hp:
                continue

            params_base = self._default_params_for_type(
                type_key, dim, use_height_spin=False
            )
            params_base["material_conductivity_w_mk"] = mat.thermal_conductivity_w_mk
            q_values: List[float] = []

            for h in heights:
                params = dict(params_base)
                params[hp] = h
                # Base thickness
                if type_key == "solid_plate":
                    base_t_mm = h
                else:
                    base_t_mm = dim.base_thickness_mm
                base_t_m = base_t_mm / 1000.0

                details = build_geometry(type_key, dim.to_tuple(), params)
                res = estimate_heat_dissipation(
                    details.geometry,
                    env,
                    power_input_w=None,
                    target_overtemp_c=delta_t,
                    base_thickness_m=base_t_m,
                    material_conductivity_w_mk=mat.thermal_conductivity_w_mk,
                    base_contact_area_m2=details.geometry.base_area_m2,
                )
                q_values.append(res.heat_dissipation_w)

            label = SUPPORTED_TYPES[type_key].label
            plt.plot(heights, q_values, marker="o", label=label)

        plt.xlabel("Height, mm")
        plt.ylabel(f"Q_max at ΔT = {delta_t:.1f} °C, W")
        plt.title("Q_max(h) for different heatsink types")
        plt.grid(True)
        plt.legend()
        plt.show()
