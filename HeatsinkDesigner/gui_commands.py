"""FreeCAD GUI commands for HeatsinkDesigner Workbench."""
from __future__ import annotations

from importlib import import_module, util
from typing import Protocol


class _Command(Protocol):
    """Protocol for FreeCAD command objects."""

    def GetResources(self) -> dict:  # noqa: N802
        ...

    def Activated(self):  # noqa: N802
        ...

    def IsActive(self) -> bool:  # noqa: N802
        ...


def _load_gui_module():
    """Return FreeCADGui module when available."""

    spec = util.find_spec("FreeCADGui")
    if spec is None:
        raise ImportError("FreeCADGui module is not available")
    return import_module("FreeCADGui")


def _load_qt_widgets():
    """Return QtWidgets module from PySide6/PySide2."""

    for candidate in ("PySide6", "PySide2"):
        if util.find_spec(candidate) is not None:
            return import_module(f"{candidate}.QtWidgets")
    raise ImportError("Neither PySide6 nor PySide2 is available for GUI")


def _build_placeholder_panel(title: str, description: str):
    """Return a simple QWidget with a couple of action buttons.

    The buttons are placeholders and only show status messages so that
    the Workbench exposes visible controls in the Task Panel even
    without a fully featured GUI implementation.
    """

    QtWidgets = _load_qt_widgets()

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)

    header = QtWidgets.QLabel(f"<b>{title}</b>")
    header.setWordWrap(True)
    layout.addWidget(header)

    hint = QtWidgets.QLabel(description)
    hint.setWordWrap(True)
    layout.addWidget(hint)

    button_row = QtWidgets.QHBoxLayout()

    generate_btn = QtWidgets.QPushButton("Сгенерировать 3D-модель")
    heat_btn = QtWidgets.QPushButton("Рассчитать тепло")
    chart_btn = QtWidgets.QPushButton("График (T, RH)")

    for btn in (generate_btn, heat_btn, chart_btn):
        btn.setToolTip("Заглушка кнопки: подключите позже к логике контроллеров")
        button_row.addWidget(btn)

    layout.addLayout(button_row)

    layout.addStretch(1)
    return widget


class _BaseCommand:
    """Shared helpers for GUI commands."""

    def __init__(self, name: str, tooltip: str, panel_title: str, panel_description: str) -> None:
        self._name = name
        self._tooltip = tooltip
        self._panel_title = panel_title
        self._panel_description = panel_description

    def GetResources(self) -> dict:  # noqa: N802
        return {"MenuText": self._name, "ToolTip": self._tooltip}

    def Activated(self):  # noqa: N802
        Gui = _load_gui_module()
        panel = _build_placeholder_panel(self._panel_title, self._panel_description)
        Gui.Control.showDialog(panel)

    def IsActive(self) -> bool:  # noqa: N802
        try:
            _load_gui_module()
        except ImportError:
            return False
        return True


class HeatsinkFromFaceCommand(_BaseCommand):
    """Command to start face/sketch driven workflow."""

    def __init__(self) -> None:
        super().__init__(
            name="Heatsink from Face/Sketch",
            tooltip="Построить радиатор на выбранной плоской грани или эскизе",
            panel_title="Heatsink по поверхности/эскизу",
            panel_description=(
                "Выберите плоскую грань или эскиз в дереве, затем используйте "
                "кнопки ниже для генерации модели и тепловых расчётов."
            ),
        )


class HeatsinkByDimensionsCommand(_BaseCommand):
    """Command to start dimension-driven workflow."""

    def __init__(self) -> None:
        super().__init__(
            name="Heatsink by Dimensions",
            tooltip="Подбор радиатора по заданным габаритам без предварительного выбора",
            panel_title="Heatsink по габаритам",
            panel_description=(
                "Вводите размеры радиатора в Task Panel и используйте кнопки "
                "для генерации, расчётов и построения графиков."
            ),
        )


COMMANDS: dict[str, _Command] = {
    "HSD_HeatsinkFromFace": HeatsinkFromFaceCommand(),
    "HSD_HeatsinkByDimensions": HeatsinkByDimensionsCommand(),
}
