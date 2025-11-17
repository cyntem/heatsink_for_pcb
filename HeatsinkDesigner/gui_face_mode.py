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

# какой параметр считать "высотой" для каждого типа
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
        """Построить GeometryDetails и масштабировать тепловые площади по реальной площади контура."""
        self.validate_selection()
        if heatsink_type not in SUPPORTED_TYPES:
            raise ValueError("Неизвестный тип радиатора")
        base_dims = self.selection.base_dimensions(base_thickness_mm)
        details = build_geometry(
            heatsink_type,
            (base_dims.length_mm, base_dims.width_mm, base_dims.base_thickness_mm),
            params,
        )

        # Масштабирование по реальной площади face/sketch
        sel = self.selection
        if sel is not None and sel.area_mm2 > 0:
            bbox_area_mm2 = sel.length_mm * sel.width_mm
            if bbox_area_mm2 > 0:
                scale = sel.area_mm2 / bbox_area_mm2
                details.geometry.base_area_m2 *= scale
                details.geometry.effective_area_m2 *= scale
                details.notes.append(
                    f"Thermal area scaled by factor {scale:.2f} to match real face/sketch area"
                )
        return details


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

        self._height_param_name: Optional[str] = None

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
            "Выберите плоскую грань или эскиз в 3D-виде.\n"
            "Параметры и результат пересчитываются автоматически.\n"
            "Кнопка генерирует 3D-модель в документе."
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

        # Параметры радиатора (кроме высоты)
        self.params_group = QtWidgets.QGroupBox("Геометрические параметры (мм)")
        self.params_layout = QtWidgets.QFormLayout(self.params_group)
        self._param_widgets: Dict[str, "QtWidgets.QDoubleSpinBox"] = {}
        layout.addWidget(self.params_group)

        # Тепловые параметры
        therm_group = QtWidgets.QGroupBox("Тепловые параметры")
        self.therm_layout = QtWidgets.QFormLayout(therm_group)

        # 1) ΔT
        self.delta_t_spin = QtWidgets.QDoubleSpinBox()
        self.delta_t_spin.setRange(1.0, 200.0)
        self.delta_t_spin.setValue(40.0)
        self.delta_t_spin.setSuffix(" °C")
        self.therm_layout.addRow("Допустимый перегрев ΔT:", self.delta_t_spin)

        # 2) режим анализа
        self.analysis_mode_combo = QtWidgets.QComboBox()
        self.analysis_mode_combo.addItem("Рассчитать P_load по высоте", userData="h_to_q")
        self.analysis_mode_combo.addItem("Рассчитать высоту по P_load", userData="q_to_h")
        self.therm_layout.addRow("Режим анализа:", self.analysis_mode_combo)

        # 3a) P_load
        self.power_label = QtWidgets.QLabel("P_load:")
        self.power_spin = QtWidgets.QDoubleSpinBox()
        self.power_spin.setRange(0.0, 1e6)
        self.power_spin.setDecimals(1)
        self.power_spin.setSuffix(" Вт")
        self.therm_layout.addRow(self.power_label, self.power_spin)

        # 3b) Высота (контролирующий параметр)
        self.height_label = QtWidgets.QLabel("Высота:")
        self.height_spin = QtWidgets.QDoubleSpinBox()
        self.height_spin.setRange(1.0, 1e6)
        self.height_spin.setDecimals(2)
        self.height_spin.setSuffix(" мм")
        self.therm_layout.addRow(self.height_label, self.height_spin)

        layout.addWidget(therm_group)

        # Результат
        self.result_label = QtWidgets.QLabel("Результат ещё не вычислен.")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # Кнопки действий
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_generate = QtWidgets.QPushButton("Сгенерировать 3D-модель")
        self.btn_chart = QtWidgets.QPushButton("График Q_max(h) (текущий тип)")

        self.btn_generate.clicked.connect(self._on_generate_clicked)
        self.btn_chart.clicked.connect(self._on_chart_clicked)

        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_chart)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        # Сигналы для пересчёта "на лету"
        self.delta_t_spin.valueChanged.connect(self._update_result_label)
        self.power_spin.valueChanged.connect(self._update_result_label)
        self.height_spin.valueChanged.connect(self._update_result_label)
        self.analysis_mode_combo.currentIndexChanged.connect(self._on_analysis_mode_changed)

        # Инициализировать параметры для первого типа
        self._on_type_changed(self.type_combo.currentIndex())

    # ----------------------------------------------------------- helpers -----
    def _on_analysis_mode_changed(self, index: int) -> None:
        mode = self.analysis_mode_combo.currentData()
        # режим 1: по высоте → считаем P_load → показываем высоту
        if mode == "h_to_q":
            self.power_label.setVisible(False)
            self.power_spin.setVisible(False)
            self.height_label.setVisible(True)
            self.height_spin.setVisible(True)
        # режим 2: по мощности → считаем высоту → показываем P_load
        else:
            self.power_label.setVisible(True)
            self.power_spin.setVisible(True)
            self.height_label.setVisible(False)
            self.height_spin.setVisible(False)
        self._update_result_label()

    def _on_type_changed(self, index: int) -> None:
        """Rebuild parameter controls when heatsink type changes."""

        QtWidgets = self._QtWidgets
        key = self.type_combo.itemData(index)
        if not key:
            key = self._type_keys[0]
        self._current_type_key: str = key

        hs_type = SUPPORTED_TYPES[key]
        defaults = hs_type.default_parameters()
        self._height_param_name = HEIGHT_PARAM_MAP.get(key)

        # очистка формы
        while self.params_layout.rowCount():
            self.params_layout.removeRow(0)
        self._param_widgets.clear()

        height_default = 10.0
        height_min = 1.0

        for param in hs_type.parameters:
            if param.name == self._height_param_name:
                height_default = defaults.get(param.name, max(param.min_value, 1.0))
                height_min = max(param.min_value, 0.1)
                continue

            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setRange(param.min_value, 1e6)
            spin.setValue(defaults.get(param.name, max(param.min_value, 0.0)))
            spin.setSuffix(" " + param.unit)
            self.params_layout.addRow(param.description + ":", spin)
            self._param_widgets[param.name] = spin
            spin.valueChanged.connect(self._update_result_label)

        # Настроить высоту
        self.height_spin.blockSignals(True)
        self.height_spin.setRange(height_min, 1e6)
        self.height_spin.setValue(height_default)
        self.height_spin.blockSignals(False)

        self._on_analysis_mode_changed(self.analysis_mode_combo.currentIndex())

    def _update_selection(self) -> bool:
        """Read current face/sketch selection from FreeCAD."""
        try:
            import FreeCADGui as Gui  # type: ignore[import]
        except ImportError:
            self.result_label.setText("FreeCADGui недоступен.")
            return False

        sel_ex = Gui.Selection.getSelectionEx()
        if not sel_ex:
            self.result_label.setText("Не выбрана плоская грань или эскиз.")
            return False

        sel_obj = sel_ex[0]
        shape = None
        if getattr(sel_obj, "SubObjects", None):
            if sel_obj.SubObjects:
                shape = sel_obj.SubObjects[0]
        if shape is None and hasattr(sel_obj.Object, "Shape"):
            shape = sel_obj.Object.Shape

        if shape is None or not hasattr(shape, "BoundBox"):
            self.result_label.setText("Не удалось получить габариты выделенного объекта.")
            return False

        bb = shape.BoundBox
        length_mm = float(bb.XLength)
        width_mm = float(bb.YLength)

        # Реальная площадь контура (если доступна)
        area_mm2 = 0.0
        if hasattr(shape, "Area"):
            try:
                area_mm2 = float(shape.Area)
            except Exception:
                area_mm2 = 0.0
        if area_mm2 <= 0.0:
            area_mm2 = float(bb.XLength * bb.YLength)

        self.controller.selection = FaceSelection(
            length_mm=length_mm, width_mm=width_mm, area_mm2=area_mm2
        )
        return True

    def _build_geometry_details(self) -> Optional[GeometryDetails]:
        """Prepare GeometryDetails based on current UI state and selection."""
        if not self._update_selection():
            return None

        params: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }
        if self._height_param_name:
            params[self._height_param_name] = float(self.height_spin.value())

        base_thickness_mm = float(params.get("base_thickness_mm", 0.0))
        if base_thickness_mm <= 0:
            self.result_label.setText("Толщина основания должна быть больше нуля.")
            return None

        try:
            details = self.controller.prepare_geometry(
                self._current_type_key, params, base_thickness_mm
            )
            return details
        except Exception as exc:  # pragma: no cover - GUI only
            self.result_label.setText(f"Ошибка генерации геометрии: {exc}")
            return None

    def _update_result_label(self) -> None:
        """Пересчитать результат в зависимости от режима анализа и обновить label."""
        details = self._build_geometry_details()
        if details is None:
            return

        env = Environment()  # T_amb и RH — как в модели по умолчанию
        delta_t = float(self.delta_t_spin.value())
        mode = self.analysis_mode_combo.currentData()

        # ----- режим: по высоте → P_load (Q_max) -----
        if mode == "h_to_q":
            try:
                res = estimate_heat_dissipation(
                    details.geometry,
                    env,
                    power_input_w=None,
                    target_overtemp_c=delta_t,
                )
            except Exception as exc:
                self.result_label.setText(f"Ошибка теплового расчёта: {exc}")
                return

            self.result_label.setText(
                f"Режим: P_load по высоте\n"
                f"Макс. допустимая мощность P_load_max ≈ {res.heat_dissipation_w:.1f} Вт\n"
                f"при ΔT = {delta_t:.1f} °C."
            )
            return

        # ----- режим: по мощности → высоту -----
        p_req = float(self.power_spin.value())
        if p_req <= 0.0:
            self.result_label.setText(
                "Режим: высота по P_load\n"
                "Задайте P_load > 0 Вт."
            )
            return

        if self._current_type_key == "solid_plate":
            self.result_label.setText(
                "Режим 'по мощности → высоту' для сплошной пластины сводится к подбору толщины.\n"
                "Используйте тип с ребрами/пинами для более осмысленного подбора."
            )
            return

        height_param = HEIGHT_PARAM_MAP.get(self._current_type_key)
        if not height_param:
            self.result_label.setText("Для данного типа не найден параметр высоты.")
            return

        if self.controller.selection is None:
            self.result_label.setText("Нет выбранной поверхности/эскиза.")
            return

        sel = self.controller.selection
        base_dims = sel.base_dimensions(float(self._param_widgets.get("base_thickness_mm", self.height_spin).value()))

        params: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }

        # Поиск минимальной высоты, при которой Q_max >= P_load
        h_current = float(self.height_spin.value())
        h_min = 1.0
        h_max = max(h_current, h_min + 1.0)
        steps = 25

        best_h: Optional[float] = None

        for i in range(steps):
            h = h_min + (h_max - h_min) * i / (steps - 1)
            p = dict(params)
            p[height_param] = h
            d = build_geometry(
                self._current_type_key,
                (base_dims.length_mm, base_dims.width_mm, base_dims.base_thickness_mm),
                p,
            )
            res = estimate_heat_dissipation(
                d.geometry, env, power_input_w=None, target_overtemp_c=delta_t
            )
            if res.heat_dissipation_w >= p_req:
                best_h = h
                break

        if best_h is None:
            self.result_label.setText(
                "Требуемая мощность недостижима при текущем диапазоне высоты.\n"
                "Увеличьте высоту ребра и попробуйте снова."
            )
            return

        # Округляем до 1 мм и записываем обратно
        h_round = max(1.0, round(best_h))
        self.height_spin.blockSignals(True)
        self.height_spin.setValue(h_round)
        self.height_spin.blockSignals(False)

        # Пересчёт уже с округлённой высотой
        params2 = dict(params)
        params2[height_param] = h_round
        d2 = build_geometry(
            self._current_type_key,
            (base_dims.length_mm, base_dims.width_mm, base_dims.base_thickness_mm),
            params2,
        )
        res2 = estimate_heat_dissipation(
            d2.geometry, env, power_input_w=None, target_overtemp_c=delta_t
        )

        self.result_label.setText(
            "Режим: высота по P_load\n"
            f"Необходимая высота ≈ {h_round:.0f} мм\n"
            f"для P_load = {p_req:.1f} Вт и ΔT = {delta_t:.1f} °C.\n"
            f"Q_max при этой высоте ≈ {res2.heat_dissipation_w:.1f} Вт."
        )

    # ----------------------------------------------------------- callbacks ---
    def _on_generate_clicked(self) -> None:
        """Сгенерировать 3D-модель радиатора в текущем документе FreeCAD."""
        QtWidgets = self._QtWidgets

        if not self._update_selection():
            return

        params: Dict[str, float] = {
            name: widget.value() for name, widget in self._param_widgets.items()
        }
        if self._height_param_name:
            params[self._height_param_name] = float(self.height_spin.value())

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

        # после генерации просто обновим текст результата
        self._update_result_label()

    def _on_chart_clicked(self) -> None:
        """Построить график Q_max(h) для текущего типа."""
        QtWidgets = self._QtWidgets

        if self._current_type_key == "solid_plate":
            QtWidgets.QMessageBox.information(
                self.form,
                "График Q_max(h)",
                "Для сплошной пластины высоты ребра нет — график не строится.",
            )
            return

        height_param = HEIGHT_PARAM_MAP.get(self._current_type_key)
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

        env = Environment()
        delta_t = float(self.delta_t_spin.value())

        h_current = float(self.height_spin.value())
        h_min = 1.0
        h_max = max(h_current, h_min + 1.0)
        steps = 10

        heights: List[float] = [
            h_min + (h_max - h_min) * i / (steps - 1) for i in range(steps)
        ]
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
                details.geometry, env, power_input_w=None, target_overtemp_c=delta_t
            )
            q_values.append(res.heat_dissipation_w)

        plt.plot(heights, q_values, marker="o")
        plt.xlabel("Высота, мм")
        plt.ylabel(f"Q_max при ΔT = {delta_t:.1f} °C, Вт")
        plt.title("Зависимость Q_max от высоты (текущий тип)")
        plt.grid(True)
        plt.show()

        self._update_result_label()
