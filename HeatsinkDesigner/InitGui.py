"""Workbench registration placeholder for FreeCAD."""
from __future__ import annotations

import sys
from importlib import util as importlib_util
from pathlib import Path

def _has_freecad_gui() -> bool:
    """Safely detect FreeCAD GUI availability.

    FreeCAD 1.0.2 sometimes preloads ``FreeCADGui`` with ``__spec__`` set to
    ``None``. ``importlib.util.find_spec`` raises a ``ValueError`` in that
    case, so we fall back to checking ``sys.modules``.
    """

    try:
        spec = importlib_util.find_spec("FreeCADGui")
    except (ValueError, NameError):
        # NameError covers environments that strip importlib during FreeCAD
        # startup; fall back to the modules already loaded.
        return "FreeCADGui" in sys.modules
    return spec is not None


FREECAD_AVAILABLE = _has_freecad_gui()

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
