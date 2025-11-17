"""Task panel logic for dimension-driven mode."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Tuple, Optional

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
    from HeatsinkDesigner.cnc_defaults import DEFAULT_CNC_PARAMS
except ImportError:
    from cnc_defaults import DEFAULT_CNC_PARAMS  # type: ignore[no-redef]

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
class DimensionInput:
    length_mm: float
    width_mm: float
    base_thickness_mm: float

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.length_mm, self.width_mm, self.base_thickness_mm)


class DimensionModeController:
    """Search simple parameter grids to suggest a heatsink for the target load."""

    def __init__(self, dimension: DimensionInput) -> None:
        self.dimension = dimension

    def _iter_param_grid(self, param_grid: Dict[str, Iterable[float]]):
        keys = list(param_grid.keys())
        for values in product(*param_grid.values()):
            yield dict(zip(keys, values))

    def sweep_candidates(
        self,
        heatsink_type: str,
        param_grid: Dict[str, Iterable[float]],
        target_power_w: float,
        environment: Environment,
        max_candidates: int = 50,
    ) -> List[Tuple[GeometryDetails, float]]:
        """Evaluate a limited grid of parameters and return sorted candidates."""

        candidates: List[Tuple[GeometryDetails, float]] = []
        for idx, params in enumerate(self._iter_param_grid(param_grid)):
            if idx >= max_candidates:
                break
            geometry = build_geometry(heatsink_type, self.dimension.to_tuple(), params)
            result = estimate_heat_dissipation(
                geometry.geometry, environment, target_power_w, target_overtemp_c=40.0
            )
            delta_t = result.surface_temperature_c - environment.temperature_c
            candidates.append((geometry, delta_t))
        candidates.sort(key=lambda item: item[1])
        return candidates

    def best_candidate(
        self,
        heatsink_type: str,
        param_grid: Dict[str, Iterable[float]],
        target_power_w: float,
        environment: Environment,
    ) -> Tuple[GeometryDetails, float]:
        """Pick the candidate with the lowest surface overtemperature."""

        candidates = self.sweep_candidates(
            heatsink_type=heatsink_type,
            param_grid=param_grid,
            target_power_w=target_power_w,
            environment=environment,
        )
        if not candidates:
            raise ValueError("Нет подходящих комбинаций параметров")
        return candidates[0]


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

        header = QtWidgets.QLabel("<b>Heatsink по габаритам</b>")
        header.setWordWrap(True)
        layout.addWidget(header)

        hint = QtWidgets.QLabel(
            "Введите габариты радиатора и целевую мощность (при необходимости).\n"
            "Режим 'Авто' переберёт доступные типы и предложит наиболее эффективный."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Габариты
        dims_group = QtWidgets.QGroupBox("Габариты (мм)")
        dims_layout = QtWidgets.QFormLayout(dims_group)

        self.length_spin = QtWidgets.QDoubleSpinBox()
        self.length_spin.setRange(1.0, 1e6)
        self.length_spin.setValue(100.0)
        self.length_spin.setSuffix(" мм")
        dims_layout.addRow("Длина L:", self.length_spin)

        self.width_spin = QtWidgets.QDoubleSpinBox()
        self.width_spin.setRange(1.0, 1e6)
        self.width_spin.setValue(50.0)
        self.width_spin.setSuffix(" мм")
        dims_layout.addRow("Ширина W:", self.width_spin)

        self.base_thickness_spin = QtWidgets.QDoubleSpinBox()
        self.base_thickness_spin.setRange(0.5, 1e6)
        self.base_thickness_spin.setValue(5.0)
        self.base_thickness_spin.setSuffix(" мм")
        dims_layout.addRow("Толщина основания:", self.base_thickness_spin)

        self.hmax_spin = QtWidgets.QDoubleSpinBox()
        self.hmax_spin.setRange(1.0, 1e6)
        self.hmax_spin.setValue(25.0)
        self.hmax_spin.setSuffix(" мм")
        dims_layout.addRow("Допустимая высота H_max:", self.hmax_spin)

        layout.addWidget(dims_group)

        # Тепловые параметры и мощность
        therm_group = QtWidgets.QGroupBox("Тепловые параметры")
        therm_layout = QtWidgets.QFormLayout(therm_group)

        self.power_spin = QtWidgets.QDoubleSpinBox()
        self.power_spin.setRange(0.0, 1e6)
        self.power_spin.setDecimals(1)
        self.power_spin.setSuffix(" Вт")
        therm_layout.addRow("P_load (для подбора):", self.power_spin)

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

        layout.addWidget(therm_group)

        # Выбор типа
        type_group = QtWidgets.QGroupBox("Тип радиатора")
        type_layout = QtWidgets.QHBoxLayout(type_group)

        type_label = QtWidgets.QLabel("Тип:")
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem("Авто (подбор оптимального)", userData="__auto__")
        self._type_keys: List[str] = list(SUPPORTED_TYPES.keys())
        for key in self._type_keys:
            self.type_combo.addItem(SUPPORTED_TYPES[key].label, userData=key)

        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo)

        layout.addWidget(type_group)

        # Кнопки
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_pick_generate = QtWidgets.QPushButton("Подобрать и сгенерировать")
        self.btn_heat = QtWidgets.QPushButton("Рассчитать тепло")
        self.btn_chart = QtWidgets.QPushButton("График Q_max(h)")

        self.btn_pick_generate.clicked.connect(
            lambda: self._on_solve_clicked(generate=True)
        )
        self.btn_heat.clicked.connect(lambda: self._on_solve_clicked(generate=False))
        self.btn_chart.clicked.connect(self._on_chart_clicked)

        btn_row.addWidget(self.btn_pick_generate)
        btn_row.addWidget(self.btn_heat)
        btn_row.addWidget(self.btn_chart)
        layout.addLayout(btn_row)

        layout.addStretch(1)

    # ----------------------------------------------------------- helpers -----
    def _dimension_input(self) -> Optional[DimensionInput]:
        QtWidgets = self._QtWidgets
        length = float(self.length_spin.value())
        width = float(self.width_spin.value())
        base_t = float(self.base_thickness_spin.value())
        if length <= 0 or width <= 0 or base_t <= 0:
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "Длина, ширина и толщина основания должны быть больше нуля",
            )
            return None
        return DimensionInput(length_mm=length, width_mm=width, base_thickness_mm=base_t)

    def _environment(self) -> Environment:
        return Environment(
            temperature_c=float(self.t_amb_spin.value()),
            relative_humidity=float(self.rh_spin.value()),
        )

    def _default_params_for_type(
        self, type_key: str, dim: DimensionInput, h_max: float
    ) -> Dict[str, float]:
        params = dict(DEFAULT_CNC_PARAMS.get(type_key, {}))
        allowed_height = max(h_max - dim.base_thickness_mm, 1.0)
        for name in ("fin_height_mm", "pin_height_mm"):
            if name in params:
                params[name] = min(params[name], allowed_height)
        return params

    def _build_geometry_for_type(self, type_key: str) -> Optional[GeometryDetails]:
        """Build geometry for given type using defaults, respecting H_max."""
        QtWidgets = self._QtWidgets
        dim = self._dimension_input()
        if dim is None:
            return None

        h_max = float(self.hmax_spin.value())
        if h_max <= dim.base_thickness_mm and type_key != "solid_plate":
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "H_max меньше или равен толщине основания. Увеличьте H_max или уменьшите толщину основания.",
            )
            return None

        params = self._default_params_for_type(type_key, dim, h_max)

        try:
            geometry = build_geometry(type_key, dim.to_tuple(), params)
            return geometry
        except Exception as exc:  # pragma: no cover - GUI only
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                f"Ошибка генерации геометрии для типа {type_key}:\n{exc}",
            )
            return None

    # ----------------------------------------------------- main callbacks ----
    def _on_solve_clicked(self, generate: bool) -> None:
        """Handle both 'Подобрать и сгенерировать' and 'Рассчитать тепло'."""
        QtWidgets = self._QtWidgets

        env = self._environment()
        p_load = float(self.power_spin.value())
        current_data = self.type_combo.currentData()
        auto_mode = current_data == "__auto__"

        if auto_mode and p_load <= 0.0:
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "Для режима 'Авто' необходимо задать P_load (> 0 Вт).",
            )
            return

        dim = self._dimension_input()
        if dim is None:
            return

        best_type_key: Optional[str] = None
        best_details: Optional[GeometryDetails] = None
        best_result = None
        best_delta_t = None
        best_params: Optional[Dict[str, float]] = None

        if auto_mode:
            # Перебираем все типы, используя CNC-дефолты
            for type_key in self._type_keys:
                h_max = float(self.hmax_spin.value())
                params = self._default_params_for_type(type_key, dim, h_max)
                details = self._build_geometry_for_type(type_key)
                if details is None:
                    continue
                try:
                    result = estimate_heat_dissipation(
                        details.geometry,
                        env,
                        power_input_w=p_load,
                        target_overtemp_c=40.0,
                    )
                except Exception:
                    continue
                delta_t = result.surface_temperature_c - env.temperature_c
                if best_delta_t is None or delta_t < best_delta_t:
                    best_delta_t = delta_t
                    best_type_key = type_key
                    best_details = details
                    best_result = result
                    best_params = params

            if best_type_key is None or best_details is None or best_result is None:
                QtWidgets.QMessageBox.warning(
                    self.form,
                    "HeatsinkDesigner",
                    "Не удалось подобрать подходящую конфигурацию радиатора.",
                )
                return

        else:
            # Ручной выбор типа
            if current_data == "__auto__":
                QtWidgets.QMessageBox.warning(
                    self.form,
                    "HeatsinkDesigner",
                    "Выберите тип радиатора или включите режим 'Авто'.",
                )
                return
            type_key = str(current_data)
            h_max = float(self.hmax_spin.value())
            params = self._default_params_for_type(type_key, dim, h_max)
            details = self._build_geometry_for_type(type_key)
            if details is None:
                return
            power_input = p_load if p_load > 0.0 else None
            try:
                result = estimate_heat_dissipation(
                    details.geometry,
                    env,
                    power_input_w=power_input,
                    target_overtemp_c=40.0,
                )
            except Exception as exc:  # pragma: no cover - GUI only
                QtWidgets.QMessageBox.critical(
                    self.form,
                    "HeatsinkDesigner",
                    f"Ошибка теплового расчёта:\n{exc}",
                )
                return
            best_type_key = type_key
            best_details = details
            best_result = result
            best_delta_t = result.surface_temperature_c - env.temperature_c
            best_params = params

        # best_* теперь заполнены
        try:
            import FreeCAD as App  # type: ignore[import]
        except ImportError:
            App = None  # type: ignore[assignment]

        label = SUPPORTED_TYPES[best_type_key].label if best_type_key else "?"
        lines = []
        if best_type_key:
            lines.append(f"Тип радиатора: {label}")
        if p_load > 0.0:
            lines.append(
                f"При P_load={p_load:.1f} Вт перегрев поверхности ≈ {best_delta_t:.1f} °C"
            )
        else:
            lines.append(
                f"Q_max при ΔT=40 °C: {best_result.heat_dissipation_w:.1f} Вт"
            )
        lines.append(
            f"h (естественная конвекция) ≈ {best_result.convection_coefficient:.2f} Вт/(м²·К)"
        )
        lines.append(
            f"A_eff ≈ {best_details.geometry.effective_area_m2:.4f} м²"
        )
        text = "\n".join(lines)

        if App is not None:
            App.Console.PrintMessage("[HeatsinkDesigner] " + text + "\n")

        if generate and best_type_key and best_params is not None:
            # 3D-модель
            base_dims = BaseDimensions(
                length_mm=dim.length_mm,
                width_mm=dim.width_mm,
                base_thickness_mm=dim.base_thickness_mm,
            )
            try:
                obj = create_heatsink_solid(
                    best_type_key, base_dims, best_params, doc=App.ActiveDocument
                )
            except Exception as exc:  # pragma: no cover - GUI only
                QtWidgets.QMessageBox.critical(
                    self.form,
                    "HeatsinkDesigner",
                    f"Ошибка построения 3D-модели:\n{exc}",
                )
                return
            if App is not None:
                App.Console.PrintMessage(
                    f"[HeatsinkDesigner] Создан радиатор: {obj.Name} ({obj.Label})\n"
                )
            QtWidgets.QMessageBox.information(
                self.form,
                "Подбор радиатора",
                text + "\n\n3D-модель радиатора создана в текущем документе.",
            )
        else:
            QtWidgets.QMessageBox.information(
                self.form, "Результаты теплового расчёта", text
            )

    def _on_chart_clicked(self) -> None:
        """Построить Q_max(h) для выбранного (НЕ авто) типа."""
        QtWidgets = self._QtWidgets
        current_data = self.type_combo.currentData()
        if current_data == "__auto__":
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "Для построения графика выберите конкретный тип радиатора (не 'Авто').",
            )
            return
        type_key = str(current_data)

        if type_key == "solid_plate":
            QtWidgets.QMessageBox.information(
                self.form,
                "График Q_max(h)",
                "Для сплошной пластины параметра высоты нет — график не строится.",
            )
            return

        height_param_map = {
            "straight_fins": "fin_height_mm",
            "crosscut": "pin_height_mm",
            "pin_fin": "pin_height_mm",
        }
        height_param = height_param_map.get(type_key)
        if not height_param:
            QtWidgets.QMessageBox.warning(
                self.form,
                "График Q_max(h)",
                "Для данного типа нет параметра высоты.",
            )
            return

        dim = self._dimension_input()
        if dim is None:
            return

        h_max = float(self.hmax_spin.value())
        if h_max <= dim.base_thickness_mm:
            QtWidgets.QMessageBox.warning(
                self.form,
                "HeatsinkDesigner",
                "H_max меньше или равен толщине основания.",
            )
            return

        params_base = self._default_params_for_type(type_key, dim, h_max)

        try:
            import matplotlib.pyplot as plt  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "Библиотека matplotlib не установлена",
            )
            return

        env = self._environment()

        h_min = 1.0
        h_max_eff = max(h_max - dim.base_thickness_mm, h_min + 1.0)
        steps = 10
        step = (h_max_eff - h_min) / (steps - 1)

        heights: List[float] = [h_min + i * step for i in range(steps)]
        q_values: List[float] = []

        for h in heights:
            params = dict(params_base)
            params[height_param] = h
            details = build_geometry(type_key, dim.to_tuple(), params)
            res = estimate_heat_dissipation(
                details.geometry, env, power_input_w=None, target_overtemp_c=40.0
            )
            q_values.append(res.heat_dissipation_w)

        plt.plot(heights, q_values, marker="o")
        plt.xlabel("Высота, мм")
        plt.ylabel("Q_max при ΔT=40 °C, Вт")
        plt.title(f"Зависимость Q_max от высоты ({SUPPORTED_TYPES[type_key].label})")
        plt.grid(True)
        plt.show()
