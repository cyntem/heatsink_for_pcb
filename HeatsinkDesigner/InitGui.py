"""Workbench registration placeholder for FreeCAD."""
from __future__ import annotations

import importlib.util
from pathlib import Path

FREECAD_AVAILABLE = importlib.util.find_spec("FreeCADGui") is not None

ICON_PATH = str(Path(__file__).parent / "icons" / "heatsink.svg")

if FREECAD_AVAILABLE:
    import FreeCADGui  # type: ignore

    class HeatsinkDesignerWorkbench(FreeCADGui.Workbench):  # pragma: no cover
        MenuText = "HeatsinkDesigner"
        ToolTip = "Generate CNC-friendly heatsinks"
        Icon = ICON_PATH

        def Initialize(self) -> None:
            """Register commands; omitted in headless environment."""
            self.list = []
            for cmd in self.list:
                FreeCADGui.addCommand(cmd, None)

        def GetClassName(self) -> str:  # noqa: N802
            return "Gui::PythonWorkbench"

    def Initialize():  # pragma: no cover
        FreeCADGui.addWorkbench(HeatsinkDesignerWorkbench())
else:
    def Initialize() -> str:
        return "FreeCADGui not available; running in headless mode"
