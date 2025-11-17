"""FreeCAD GUI commands for HeatsinkDesigner Workbench."""
from __future__ import annotations

from importlib import import_module
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
    try:
        return import_module("FreeCADGui")
    except Exception as exc:  # pragma: no cover - GUI only
        raise ImportError("FreeCADGui module is not available") from exc


def _load_qt_widgets():
    """Return QtWidgets module from PySide6/PySide2."""
    for candidate in ("PySide6", "PySide2"):
        try:
            return import_module(f"{candidate}.QtWidgets")
        except ImportError:
            continue
    raise ImportError("Neither PySide6 nor PySide2 is available for GUI")


def _build_placeholder_panel(title: str, description: str):
    """Простой QWidget-заглушка на случай, если не удалось загрузить TaskPanel."""

    QtWidgets = _load_qt_widgets()

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)

    header = QtWidgets.QLabel(f"<b>{title}</b>")
    header.setWordWrap(True)
    layout.addWidget(header)

    hint = QtWidgets.QLabel(description)
    hint.setWordWrap(True)
    layout.addWidget(hint)

    layout.addStretch(1)
    return widget


def _import_taskpanel(module_name: str, class_name: str):
    """Попробовать загрузить TaskPanel класс из пакета или локального модуля.

    1) Пытаемся импортировать HeatsinkDesigner.<module_name>.
    2) Если не получилось — просто <module_name>.
    При ошибке пишем сообщение в консоль FreeCAD и возвращаем None.
    """
    last_exc: Exception | None = None
    try:
        import FreeCAD as App  # type: ignore[import]
    except Exception:
        App = None  # type: ignore[assignment]

    for modname in (f"HeatsinkDesigner.{module_name}", module_name):
        try:
            module = import_module(modname)
            cls = getattr(module, class_name)
            return cls
        except Exception as exc:
            last_exc = exc

    msg = f"Cannot import {class_name}: {last_exc}"
    if App is not None:
        try:
            App.Console.PrintError(f"HeatsinkDesigner: {msg}\n")
        except Exception:
            pass
    return None


class _BaseCommand:
    """Базовый класс для GUI-команд."""

    def __init__(self, name: str, tooltip: str) -> None:
        self._name = name
        self._tooltip = tooltip

    def GetResources(self) -> dict:  # noqa: N802
        return {"MenuText": self._name, "ToolTip": self._tooltip}

    def IsActive(self) -> bool:  # noqa: N802
        try:
            _load_gui_module()
        except ImportError:
            return False
        return True


class HeatsinkFromFaceCommand(_BaseCommand):
    """Команда для режима по поверхности/эскизу."""

    def __init__(self) -> None:
        super().__init__(
            name="Heatsink from Face/Sketch",
            tooltip="Построить радиатор на выбранной плоской грани или эскизе",
        )

    def Activated(self):  # noqa: N802
        Gui = _load_gui_module()
        PanelClass = _import_taskpanel("gui_face_mode", "FaceModeTaskPanel")

        if PanelClass is None:
            panel = _build_placeholder_panel(
                "Heatsink по поверхности/эскизу",
                "Не удалось загрузить GUI (FaceModeTaskPanel).\n"
                "Проверьте файлы gui_face_mode.py и установку HeatsinkDesigner.",
            )
        else:
            panel = PanelClass()

        Gui.Control.showDialog(panel)


class HeatsinkByDimensionsCommand(_BaseCommand):
    """Команда для режима по габаритам."""

    def __init__(self) -> None:
        super().__init__(
            name="Heatsink by Dimensions",
            tooltip="Подбор радиатора по заданным габаритам без предварительного выбора",
        )

    def Activated(self):  # noqa: N802
        Gui = _load_gui_module()
        PanelClass = _import_taskpanel("gui_dim_mode", "DimensionModeTaskPanel")

        if PanelClass is None:
            panel = _build_placeholder_panel(
                "Heatsink по габаритам",
                "Не удалось загрузить GUI (DimensionModeTaskPanel).\n"
                "Проверьте файлы gui_dim_mode.py и установку HeatsinkDesigner.",
            )
        else:
            panel = PanelClass()

        Gui.Control.showDialog(panel)


COMMANDS: dict[str, _Command] = {
    "HSD_HeatsinkFromFace": HeatsinkFromFaceCommand(),
    "HSD_HeatsinkByDimensions": HeatsinkByDimensionsCommand(),
}
