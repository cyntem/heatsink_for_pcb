"""FreeCAD GUI commands for HeatsinkDesigner Workbench."""
from __future__ import annotations

from typing import Protocol
import importlib


class _Command(Protocol):
    """Protocol for FreeCAD command objects."""

    def GetResources(self) -> dict:  # noqa: N802
        ...

    def Activated(self):  # noqa: N802
        ...

    def IsActive(self) -> bool:  # noqa: N802
        ...


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
        # Переопределяется в наследниках
        pass

    def IsActive(self) -> bool:  # noqa: N802
        # Внутри GUI FreeCAD команды всегда активны
        return True


def _import_face_panel():
    """Загрузить FaceModeTaskPanel независимо от того, как подключён модуль."""
    last_exc = None

    # 1) Пакет HeatsinkDesigner
    try:
        module = importlib.import_module("HeatsinkDesigner.gui_face_mode")
        return module.FaceModeTaskPanel
    except Exception as exc:
        last_exc = exc

    # 2) Модуль gui_face_mode в той же папке (FreeCAD добавил её в sys.path)
    try:
        module = importlib.import_module("gui_face_mode")
        return module.FaceModeTaskPanel
    except Exception as exc:
        last_exc = exc

    # Если совсем не получилось — кидаем то, что есть
    raise ImportError(f"Cannot import FaceModeTaskPanel: {last_exc}")


def _import_dim_panel():
    """Загрузить DimensionModeTaskPanel независимо от способа импорта."""
    last_exc = None

    # 1) Пакет HeatsinkDesigner
    try:
        module = importlib.import_module("HeatsinkDesigner.gui_dim_mode")
        return module.DimensionModeTaskPanel
    except Exception as exc:
        last_exc = exc

    # 2) Модуль gui_dim_mode в той же папке
    try:
        module = importlib.import_module("gui_dim_mode")
        return module.DimensionModeTaskPanel
    except Exception as exc:
        last_exc = exc

    raise ImportError(f"Cannot import DimensionModeTaskPanel: {last_exc}")


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

    def Activated(self):  # noqa: N802
        import FreeCADGui as Gui  # type: ignore[import]

        try:
            FaceModeTaskPanel = _import_face_panel()
        except ImportError as exc:
            Gui.doCommand(
                'print("HeatsinkDesigner: cannot import FaceModeTaskPanel:", %r)' % (exc,)
            )
            return

        panel = FaceModeTaskPanel()
        Gui.Control.showDialog(panel)


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

    def Activated(self):  # noqa: N802
        import FreeCADGui as Gui  # type: ignore[import]

        try:
            DimensionModeTaskPanel = _import_dim_panel()
        except ImportError as exc:
            Gui.doCommand(
                'print("HeatsinkDesigner: cannot import DimensionModeTaskPanel:", %r)' % (exc,)
            )
            return

        panel = DimensionModeTaskPanel()
        Gui.Control.showDialog(panel)


COMMANDS: dict[str, _Command] = {
    "HSD_HeatsinkFromFace": HeatsinkFromFaceCommand(),
    "HSD_HeatsinkByDimensions": HeatsinkByDimensionsCommand(),
}
