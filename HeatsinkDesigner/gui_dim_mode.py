"""Task panel logic for dimension-driven mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

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

        header = QtWidgets.QLabel("<b>Heatsink по габаритам</b>")
        header.setWordWrap(True)
        layout.addWidget(header)

        hint = QtWidgets.QLabel(
            "Введите габариты радиатора. В блоке тепловых параметров:\n"
            "  1) ΔT — допустимый перегрев;\n"
            "  2) режим анализа — P_load по высоте или высота по P_load;\n"
            "  3) в зависимости от режима — либо высота, либо P_load.\n"
            "Результат пересчитывается автоматически, кнопка строит 3D-модель."
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
        self.therm_layout = QtWidgets.QFormLayout(therm_group)

        self.delta_t_spin = QtWidgets.QDoubleSpinBox()
        self.delta_t_spin.setRange(1.0, 200.0)
        self.delta_t_spin.setValue(40.0)
        self.delta_t_spin.setSuffix(" °C")
        self.therm_layout.addRow("Допустимый перегрев ΔT:", self.delta_t_spin)

        self.analysis_mode_combo = QtWidgets.QComboBox()
        self.analysis_mode_combo.addItem("Рассчитать P_load по высоте", userData="h_to_q")
        self.analysis_mode_combo.addItem("Рассчитать высоту по P_load", userData="q_to_h")
        self.therm_layout.addRow("Режим анализа:", self.analysis_mode_combo)

        # динамический параметр: P_load или высота
        self.power_label = QtWidgets.QLabel("P_load:")
        self.power_spin = QtWidgets.QDoubleSpinBox()
        self.power_spin.setRange(0.0, 1e6)
        self.power_spin.setDecimals(1)
        self.power_spin.setSuffix(" Вт")
        self.therm_layout.addRow(self.power_label, self.power_spin)

        self.height_label = QtWidgets.QLabel("Высота (раб.):")
        self.height_spin = QtWidgets.QDoubleSpinBox()
        self.height_spin.setRange(1.0, 1e6)
        self.height_spin.setDecimals(2)
        self.height_spin.setValue(20.0)
        self.height_spin.setSuffix(" мм")
        self.therm_layout.addRow(self.height_label, self.height_spin)

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

        # Результат
        self.result_label = QtWidgets.QLabel("Результат ещё не вычислен.")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # Кнопки
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_pick_generate = QtWidgets.QPushButton("Подобрать и сгенерировать")
        self.btn_chart = QtWidgets.QPushButton("График Q_max(h) (все типы)")

        self.btn_pick_generate.clicked.connect(self._on_generate_clicked)
        self.btn_chart.clicked.connect(self._on_chart_clicked)

        btn_row.addWidget(self.btn_pick_generate)
        btn_row.addWidget(self.btn_chart)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        # Сигналы для авто-пересчёта
        for spin in (
            self.length_spin,
            self.width_spin,
            self.base_thickness_spin,
            self.hmax_spin,
            self.delta_t_spin,
            self.power_spin,
            self.height_spin,
        ):
            spin.valueChanged.connect(self._update_result_label)

        self.type_combo.currentIndexChanged.connect(self._update_result_label)
        self.analysis_mode_combo.currentIndexChanged.connect(self._on_analysis_mode_changed)

        self._on_analysis_mode_changed(self.analysis_mode_combo.currentIndex())
        self._update_result_label()

    # ----------------------------------------------------------- helpers -----
    def _on_analysis_mode_changed(self, index: int) -> None:
        mode = self.analysis_mode_combo.currentData()
        # по высоте → считаем P_load → показываем высоту
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

    def _dimension_input(self) -> Optional[DimensionInput]:
        length = float(self.length_spin.value())
        width = float(self.width_spin.value())
        base_t = float(self.base_thickness_spin.value())
        if length <= 0 or width <= 0 or base_t <= 0:
            self.result_label.setText(
                "Длина, ширина и толщина основания должны быть больше нуля."
            )
            return None
        return DimensionInput(length_mm=length, width_mm=width, base_thickness_mm=base_t)

    def _default_params_for_type(
        self, type_key: str, dim: DimensionInput, h_max: float, use_height_spin: bool
    ) -> Dict[str, float]:
        params = dict(DEFAULT_CNC_PARAMS.get(type_key, {}))
        allowed_height = max(h_max - dim.base_thickness_mm, 1.0)
        hp = HEIGHT_PARAM_MAP.get(type_key)

        for name in ("fin_height_mm", "pin_height_mm", "base_thickness_mm"):
            if name in params:
                params[name] = min(params[name], allowed_height)

        if use_height_spin and hp:
            params[hp] = min(float(self.height_spin.value()), allowed_height)
        return params

    # ----------------------------------------------------- core computation ---
    def _compute_best_config(
        self,
    ) -> Tuple[Optional[str], Optional[Dict[str, float]], Optional[GeometryDetails], str]:
        """Вычислить лучший вариант (по текущему режиму анализа) без генерации 3D."""
        dim = self._dimension_input()
        if dim is None:
            return None, None, None, "Некорректные габариты."

        h_max = float(self.hmax_spin.value())
        if h_max <= dim.base_thickness_mm:
            return (
                None,
                None,
                None,
                "H_max должен быть больше толщины основания.",
            )

        delta_t = float(self.delta_t_spin.value())
        env = Environment()
        mode = self.analysis_mode_combo.currentData()
        current_data = self.type_combo.currentData()
        auto_mode = current_data == "__auto__"
        p_req = float(self.power_spin.value())

        use_height_spin = mode == "h_to_q"

        # ----- режим: по высоте → P_load (Q_max) -----
        if mode == "h_to_q":
            best_type_key: Optional[str] = None
            best_params: Optional[Dict[str, float]] = None
            best_details: Optional[GeometryDetails] = None
            best_q: Optional[float] = None

            type_list = self._type_keys if auto_mode else [str(current_data)]
            for type_key in type_list:
                params = self._default_params_for_type(type_key, dim, h_max, use_height_spin=True)
                try:
                    details = build_geometry(type_key, dim.to_tuple(), params)
                    res = estimate_heat_dissipation(
                        details.geometry,
                        env,
                        power_input_w=None,
                        target_overtemp_c=delta_t,
                    )
                except Exception:
                    continue
                if best_q is None or res.heat_dissipation_w > best_q:
                    best_q = res.heat_dissipation_w
                    best_type_key = type_key
                    best_params = params
                    best_details = details

            if best_type_key is None or best_params is None or best_details is None:
                return None, None, None, "Не удалось подобрать конфигурацию."

            label = SUPPORTED_TYPES[best_type_key].label
            text = (
                "Режим: P_load по высоте\n"
                f"Тип радиатора: {label}\n"
                f"Макс. допустимая мощность P_load_max ≈ {best_q:.1f} Вт\n"
                f"при ΔT = {delta_t:.1f} °C."
            )
            return best_type_key, best_params, best_details, text

        # ----- режим: по мощности → высоту -----
        if p_req <= 0.0:
            return None, None, None, "Режим: высота по P_load. Задайте P_load > 0 Вт."

        def find_height_for_type(type_key: str):
            params_base = self._default_params_for_type(type_key, dim, h_max, use_height_spin=False)
            hp = HEIGHT_PARAM_MAP.get(type_key)
            if not hp:
                return None, None, None
            h_min = 1.0
            h_max_eff = max(h_max - dim.base_thickness_mm, h_min + 1.0)
            steps = 25
            best_h_local: Optional[float] = None
            best_details_local: Optional[GeometryDetails] = None
            for i in range(steps):
                h = h_min + (h_max_eff - h_min) * i / (steps - 1)
                params = dict(params_base)
                params[hp] = h
                details = build_geometry(type_key, dim.to_tuple(), params)
                res = estimate_heat_dissipation(
                    details.geometry,
                    env,
                    power_input_w=None,
                    target_overtemp_c=delta_t,
                )
                if res.heat_dissipation_w >= p_req:
                    best_h_local = h
                    best_details_local = details
                    break
            return best_h_local, params_base, best_details_local

        best_type_key: Optional[str] = None
        best_params: Optional[Dict[str, float]] = None
        best_details: Optional[GeometryDetails] = None
        best_h: Optional[float] = None

        type_list = self._type_keys if auto_mode else [str(current_data)]

        for type_key in type_list:
            h_local, params_base, details_local = find_height_for_type(type_key)
            if h_local is None or params_base is None or details_local is None:
                continue
            if best_h is None or h_local < best_h:
                best_h = h_local
                best_type_key = type_key
                best_params = params_base
                best_details = details_local

        if best_type_key is None or best_params is None or best_details is None or best_h is None:
            return (
                None,
                None,
                None,
                "Не удалось подобрать тип и высоту для заданной мощности.\n"
                "Увеличьте H_max или уменьшите P_load.",
            )

        # Округляем высоту и пересчитываем Q_max
        hp_final = HEIGHT_PARAM_MAP.get(best_type_key)
        if hp_final:
            h_round = max(1.0, round(best_h))
            best_params[hp_final] = h_round
            best_details = build_geometry(best_type_key, dim.to_tuple(), best_params)
            res = estimate_heat_dissipation(
                best_details.geometry,
                env,
                power_input_w=None,
                target_overtemp_c=delta_t,
            )
            # обновим height_spin, чтобы при переключении режима было видно
            self.height_spin.blockSignals(True)
            self.height_spin.setValue(h_round)
            self.height_spin.blockSignals(False)

            label = SUPPORTED_TYPES[best_type_key].label
            text = (
                "Режим: высота по P_load\n"
                f"Тип радиатора: {label}\n"
                f"Необходимая высота ≈ {h_round:.0f} мм\n"
                f"для P_load = {p_req:.1f} Вт и ΔT = {delta_t:.1f} °C.\n"
                f"Q_max при этой высоте ≈ {res.heat_dissipation_w:.1f} Вт."
            )
            return best_type_key, best_params, best_details, text

        return None, None, None, "Не удалось вычислить высоту."

    # ----------------------------------------------------- label + 3D --------
    def _update_result_label(self) -> None:
        """Пересчитать и показать только текст (без генерации 3D)."""
        type_key, params, details, text = self._compute_best_config()
        self.result_label.setText(text)

    def _on_generate_clicked(self) -> None:
        """Подобрать конфигурацию и сгенерировать 3D-модель."""
        QtWidgets = self._QtWidgets
        type_key, params, details, text = self._compute_best_config()
        self.result_label.setText(text)

        if type_key is None or params is None or details is None:
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
                "FreeCAD недоступен для построения 3D-модели",
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
                f"Ошибка построения 3D-модели:\n{exc}",
            )
            return

        App.Console.PrintMessage(
            f"[HeatsinkDesigner] Создан радиатор: {obj.Name} ({obj.Label})\n"
        )

    # ----------------------------------------------------- график Q(h) -------
    def _on_chart_clicked(self) -> None:
        """Построить Q_max(h) для всех типов радиаторов на одном графике."""
        QtWidgets = self._QtWidgets
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

        try:
            import matplotlib.pyplot as plt  # type: ignore[import]
        except ImportError:
            QtWidgets.QMessageBox.critical(
                self.form,
                "HeatsinkDesigner",
                "Библиотека matplotlib не установлена",
            )
            return

        env = Environment()
        delta_t = float(self.delta_t_spin.value())

        h_min = 1.0
        h_max_eff = max(h_max - dim.base_thickness_mm, h_min + 1.0)
        steps = 12
        heights: List[float] = [
            h_min + (h_max_eff - h_min) * i / (steps - 1) for i in range(steps)
        ]

        for type_key in self._type_keys:
            hp = HEIGHT_PARAM_MAP.get(type_key)
            if not hp:
                continue
            params_base = self._default_params_for_type(type_key, dim, h_max, use_height_spin=False)
            q_values: List[float] = []
            for h in heights:
                params = dict(params_base)
                params[hp] = h
                details = build_geometry(type_key, dim.to_tuple(), params)
                res = estimate_heat_dissipation(
                    details.geometry,
                    env,
                    power_input_w=None,
                    target_overtemp_c=delta_t,
                )
                q_values.append(res.heat_dissipation_w)

            label = SUPPORTED_TYPES[type_key].label
            plt.plot(heights, q_values, marker="o", label=label)

        plt.xlabel("Высота, мм")
        plt.ylabel(f"Q_max при ΔT = {delta_t:.1f} °C, Вт")
        plt.title("Q_max(h) для разных типов радиаторов")
        plt.grid(True)
        plt.legend()
        plt.show()
