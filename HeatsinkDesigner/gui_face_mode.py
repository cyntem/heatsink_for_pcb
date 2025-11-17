"""Task panel logic for face/sketch driven mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List

# ---- импорты модулей воркбенча ---------------------------------------------
try:
    from HeatsinkDesigner.geometry_builder import (
        BaseDimensions,
        GeometryDetails,
        build_geometry,
        create_heatsink_solid,
    )
except ImportError:
    from geometry_builder import (  # type: ignore[no-redef]
        BaseDimensions,
        GeometryDetails,
        build_geometry,
        create_heatsink_solid,
    )

try:
    from HeatsinkDesigner.heatsink_types import SUPPORTED_TYPES
except ImportError:
    from heatsink_types import SUPPORTED_TYPES  # type: ignore[no-redef]

try:
    from HeatsinkDesigner.thermal_model import (
        Environment,
        estimate_heat_dissipation,
    )
except ImportError:
    from thermal_model import (  # type: ignore[no-redef]
        Environment,
        estimate_heat_dissipation,
    )


@dataclass
class FaceSelection:
    """Represents a simplified face/sketch selection."""

    length_mm: float
    width_mm: float
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)

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
            raise ValueError("Не выбрана плоская грань или эскиз")
        if self.selection.length_mm <= 0 or self.selection.width_mm <= 0:
            raise ValueError("Размеры плоскости должны быть положительными")

    def prepare_geometry(
        self,
        heatsink_type: str,
        params: Dict[str, float],
        base_thickness_mm: float,
    ) -> GeometryDetails:
        self.validate_selection()
        if heatsink_type not in SUPPORTED_TYPES:
            raise ValueError("Неизвестный тип радиатора")
        base_dims = self.selection.base_dimensions(base_thickness_mm)
        return build_geometry(
            heatsink_type,
            (base_dims.length_mm, base_dims.width_mm, base_dims.base_thickness_mm),
            params,
        )


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


class FaceModeTaskPanel:
    """Qt Task Panel for face/sketch driven mode (mode 1)."""

    def __init__(self) -> None:
        QtWidgets = _load_qt_widgets()
        self._QtWidgets = QtWidgets
        self.controller = FaceSketchController()

        # Root widget expected by FreeCAD TaskPanel
        self.form = QtWidgets.QWidget()
        self._build_ui()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self) -> None:
        QtWidgets = self._QtWidgets

        layout = QtWidgets.QVBoxLayout(self.form)

        header = QtWidgets.QLabel("<b>Heatsink по поверхности/эскизу</b>")
        header.setWordWrap(True)
        layout.addWidget(header)

        hint = QtWidgets.QLabel(
            "Выберите плоскую грань или эскиз в 3D-виде,\n"
            "затем используйте кнопки ниже для расчёта и генерации."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Тип радиатора
        type_row = QtWidgets.QHBoxLayout()
        type_label = QtWidgets.QLabel("Тип радиатора:")
        self.type_combo = QtWidgets.QComboBox()
        self._type_keys: List[str] = list(SUPPORTED_TYPES.keys())
        for key in self._type_keys:
            hs_type = SUPPORTED_TYPES[key]
            self.type_combo.addItem(hs_type.label, userData=key)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(type_label)
        type_row.addWidget(self.type_combo)
        layout.addLayout(type_row)

        # Параметры радиатора
        self.params_group = QtWidgets.QGroupBox("Геометрические параметры (мм)")
        self.params_layout = QtWidgets.QFormLayout(self.params_group)
        self._param_widgets: Dict[str, "QtWidgets.QDoubleSpinBox"] = {}
        layout.addWidget(self.params_group)

        # Тепловые параметры
        therm_group = QtWidgets.QGroupBox("Тепловые параметры")
        therm_layout = QtWidgets.QFormLayout(therm_group)

        self.t_amb_spin = QtWidgets.QDoubleSpinBox()
        self.t_amb_spin.setRange(-50.0, 150.0)
        self.t_amb_spin.setValue(25.0)
        self.t_amb_spin.setSuffix(" °C")
        therm_layout.addRow("T окр. среды:", self.t_amb_spin)

        self.rh_spin = QtWidgets.QDoubleSpinBox()
        self.rh_spin.setRange(0.0, 100.0)
        self.rh_spin.setValue(50.0)
        self.rh_spin.setSuffix(" %")
        therm_layout.addRow("Относительная влажность:", self.rh_spin)

        self.power_spin = QtWidgets.QDoubleSpinBox()
        self.power_spin.setRange(0.0, 1e6)
        self.power_spin.setDecimals(1)
        self.power_spin.setSuffix(" Вт")
        therm_layout.addRow("P_load (опц.):", self.power_spin)

        layout.addWidget(therm_group)

        # Кнопки действий
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_generate = QtWidgets.QPushButton("Сгенерировать 3D-модель")
        self.btn_heat = QtWidgets.QPushButton("Рассчитать тепло")
        self.btn_chart = QtWidgets.QPushButton("График Q_max(h)")

        self.btn_generate.clicked.connect(self._on_generate_clicked)
        self.btn_heat.clicked.connect(self._on_heat_clicked)
        self.btn_chart.clicked.connect(self._on_chart_clicked)

        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_heat)
        btn_row.addWidget(self.btn_chart)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        # Инициализировать параметры для первого типа
        self._on_type_changed(self.type_combo.currentIndex())

    # ----------------------------------------------------------- helpers -----
    def _on_type_changed(self, index: int) -> None:
        """Rebuild parameter controls when heatsink type changes."""

        QtWidgets = self._QtWidgets
        key = self.type_combo.itemData(index)
        if not key:
            key = self._type_keys[0]
        self._current_type_key: str = key

        hs_type = SUPPORTED_TYPES[key]
        defaults = hs_type.default_parameters()

        # очистка формы
        while self.params_layout.rowCount():
            self.params_layout.removeRow(0)
        self._param_widgets.clear()

        for param in hs_type.parameters:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setRange(param.min_value, 1e6)
            spin.setValue(defaults.get(param.name, max(param.min_value, 0.0)))
            spin.setSuffix(" " + param.unit)
            self.params_layout.addRow(param.description + ":", spin)
            self._param_widgets[param.name] = spin

    def _update_selection(self) -> bool:
        """Read current face/sketch selection from FreeCAD."""
        QtWidgets = self._QtWidgets
        try:
            import FreeCADGui as Gui  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form, "HeatsinkDesigner", "FreeCADGui недоступен"
            )
            return False

        sel_ex = Gui.Selection.getSelectionEx()
        if not sel_ex:
            QtWidgets.QMessageBox.warning(
                self.form, "HeatsinkDesigner", "Не выбрана плоская грань или эскиз"
            )
            return False

        sel_obj = sel_ex[0]
        shape = None
        if getattr(sel_obj, "SubObjects", None):
            if sel_obj.SubObjects:
                shape = sel_obj.SubObjects[0]
        if shape is None and hasattr(sel_obj.Object, "Shape"):
            shape = sel_obj.Object.Shape

        if shape is None or not hasattr(shape, "BoundBox"):
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "Не удалось получить габариты выделенного объекта",
            )
            return False

        bb = shape.BoundBox
        length_mm = float(bb.XLength)
        width_mm = float(bb.YLength)

        self.controller.selection = FaceSelection(length_mm=length_mm, width_mm=width_mm)
        return True

    def _build_geometry_details(self) -> Optional[GeometryDetails]:
        """Prepare GeometryDetails based on current UI state and selection."""
        QtWidgets = self._QtWidgets

        if not self._update_selection():
            return None

        params: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }
        base_thickness_mm = float(params.get("base_thickness_mm", 0.0))
        if base_thickness_mm <= 0:
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "Толщина основания должна быть больше нуля",
            )
            return None

        try:
            details = self.controller.prepare_geometry(
                self._current_type_key, params, base_thickness_mm
            )
            return details
        except Exception as exc:  # pragma: no cover - GUI only
            QtWidgets.QMessageBox.critical(
                self.form, "HeatsinkDesigner", f"Ошибка генерации геометрии:\n{exc}"
            )
            return None

    # ----------------------------------------------------------- callbacks ---
    def _on_generate_clicked(self) -> None:
        """Сгенерировать 3D-модель радиатора в текущем документе FreeCAD."""
        QtWidgets = self._QtWidgets

        if not self._update_selection():
            return

        params: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }
        base_thickness_mm = float(params.get("base_thickness_mm", 0.0))
        if base_thickness_mm <= 0:
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "Толщина основания должна быть больше нуля",
            )
            return

        try:
            import FreeCAD as App  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "FreeCAD недоступен для построения 3D-модели",
            )
            return

        self.controller.validate_selection()
        base_dims = self.controller.selection.base_dimensions(base_thickness_mm)

        try:
            obj = create_heatsink_solid(
                self._current_type_key, base_dims, params, doc=App.ActiveDocument
            )
        except Exception as exc:  # pragma: no cover - GUI only
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                f"Ошибка построения 3D-модели:\n{exc}",
            )
            return

        App.Console.PrintMessage(
            f"[HeatsinkDesigner] Создан радиатор: {obj.Name} ({obj.Label})\n"
        )

    def _on_heat_clicked(self) -> None:
        """Run thermal calculation for current geometry."""
        QtWidgets = self._QtWidgets
        details = self._build_geometry_details()
        if details is None:
            return

        env = Environment(
            temperature_c=float(self.t_amb_spin.value()),
            relative_humidity=float(self.rh_spin.value()),
        )
        p_load = float(self.power_spin.value())
        power_input = p_load if p_load > 0.0 else None

        try:
            result = estimate_heat_dissipation(
                details.geometry, env, power_input_w=power_input
            )
        except Exception as exc:  # pragma: no cover - GUI only
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                f"Ошибка теплового расчёта:\n{exc}",
            )
            return

        try:
            import FreeCAD as App  # type: ignore[import]
        except ImportError:
            App = None  # type: ignore[assignment]

        lines = []
        if power_input is None:
            lines.append(
                f"Q_max при ΔT=40 °C: {result.heat_dissipation_w:.1f} Вт "
                f"(Tпов≈{result.surface_temperature_c:.1f} °C)"
            )
        else:
            lines.append(
                "Оценка температуры поверхности при "
                f"P_load={power_input:.1f} Вт: {result.surface_temperature_c:.1f} °C"
            )
        lines.append(
            f"h (естественная конвекция) ≈ {result.convection_coefficient:.2f} Вт/(м²·К)"
        )
        text = "\n".join(lines)

        if App is not None:
            App.Console.PrintMessage("[HeatsinkDesigner] " + text + "\n")
        QtWidgets.QMessageBox.information(
            self.form, "Результат теплового расчёта", text
        )

    def _on_chart_clicked(self) -> None:
        """Построить график Q_max(h) для текущего типа и геометрии."""
        QtWidgets = self._QtWidgets

        # Для сплошной пластины высоты как таковой нет
        if self._current_type_key == "solid_plate":
            QtWidgets.QMessageBox.information(
                self.form,
                "График Q_max(h)",
                "Для сплошной пластины высоты ребра нет — график не строится.",
            )
            return

        height_param_map = {
            "straight_fins": "fin_height_mm",
            "crosscut": "pin_height_mm",
            "pin_fin": "pin_height_mm",
        }
        height_param = height_param_map.get(self._current_type_key)
        if not height_param:
            QtWidgets.QMessageBox.warning(
                self.form,
                "График Q_max(h)",
                "Для данного типа нет параметра высоты.",
            )
            return

        if not self._update_selection():
            return

        params: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }
        base_thickness_mm = float(params.get("base_thickness_mm", 0.0))
        if base_thickness_mm <= 0:
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "Толщина основания должна быть больше нуля",
            )
            return

        self.controller.validate_selection()
        base_dims = self.controller.selection.base_dimensions(base_thickness_mm)

        try:
            import matplotlib.pyplot as plt  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "Библиотека matplotlib не установлена",
            )
            return

        env = Environment(
            temperature_c=float(self.t_amb_spin.value()),
            relative_humidity=float(self.rh_spin.value()),
        )

        h_current = float(params.get(height_param, 10.0))
        h_min = max(1.0, h_current / 5.0)
        h_max = max(h_current, h_min + 1.0)
        steps = 10
        step = (h_max - h_min) / (steps - 1)

        heights: List[float] = [h_min + i * step for i in range(steps)]
        q_values: List[float] = []

        for h in heights:
            p = dict(params)
            p[height_param] = h
            details = build_geometry(
                self._current_type_key,
                (base_dims.length_mm, base_dims.width_mm, base_dims.base_thickness_mm),
                p,
            )
            res = estimate_heat_dissipation(
                details.geometry, env, power_input_w=None, target_overtemp_c=40.0
            )
            q_values.append(res.heat_dissipation_w)

        plt.plot(heights, q_values, marker="o")
        plt.xlabel("Высота, мм")
        plt.ylabel("Q_max при ΔT=40 °C, Вт")
        plt.title("Зависимость Q_max от высоты")
        plt.grid(True)
        plt.show()
