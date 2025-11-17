"""Workbench registration placeholder for FreeCAD."""
from __future__ import annotations

import os
import sys
from importlib import util as importlib_util

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


def _module_dir() -> str:
    """Return the directory containing this module.

    Some FreeCAD initialization contexts remove ``__file__``. Fall back to
    ``__spec__.origin`` when that happens to keep icon resolution robust.

    We avoid depending on a global ``Path`` symbol because certain FreeCAD
    startup configurations clear module globals, which previously resulted in
    a ``NameError`` during initialization. The lightweight ``os.path`` helpers
    remain available even in those constrained environments.
    """

    try:
        from pathlib import Path
    except Exception:
        Path = None  # type: ignore

    if Path is not None:
        try:
            return str(Path(__file__).parent)
        except NameError:
            spec = globals().get("__spec__")
            if spec and spec.origin:
                return str(Path(spec.origin).parent)
            return str(Path.cwd())

    if "__file__" in globals():
        return os.path.dirname(os.path.abspath(__file__))

    spec = globals().get("__spec__")
    if spec and getattr(spec, "origin", None):
        return os.path.dirname(os.path.abspath(spec.origin))

    return os.getcwd()


FREECAD_AVAILABLE = _has_freecad_gui()

ICON_PATH = os.path.join(_module_dir(), "icons", "heatsink.svg")

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
