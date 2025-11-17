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


def _module_dir():
    """Return the directory containing this module as a ``Path``.

    Some FreeCAD initialization contexts remove ``__file__``. Fall back to
    ``__spec__.origin`` when that happens to keep icon resolution robust.

    We avoid depending on a global ``Path`` symbol because certain FreeCAD
    startup configurations clear module globals, which previously resulted in
    a ``NameError`` during initialization. The lightweight ``os.path`` helpers
    remain available even in those constrained environments.
    """

    try:
        from pathlib import Path
    except Exception:  # pragma: no cover - extremely defensive
        Path = None  # type: ignore

    if Path is not None:
        try:
            return Path(__file__).parent
        except NameError:
            spec = globals().get("__spec__")
            if spec and spec.origin:
                return Path(spec.origin).parent
            return Path.cwd()

    # ``pathlib`` is unavailable; fall back to ``os.path`` strings and convert
    # through ``Path`` once the module becomes importable again.
    fallback = None
    if "__file__" in globals():
        fallback = os.path.dirname(os.path.abspath(__file__))
    else:
        spec = globals().get("__spec__")
        if spec and getattr(spec, "origin", None):
            fallback = os.path.dirname(os.path.abspath(spec.origin))
    if fallback is None:
        fallback = os.getcwd()

    if Path is None:  # pragma: no cover - see note above
        return fallback
    return Path(fallback)


def _icon_path() -> str:
    """Return the absolute path to the workbench icon."""

    return os.path.join(str(_module_dir()), "icons", "heatsink.svg")


FREECAD_AVAILABLE = _has_freecad_gui()

if FREECAD_AVAILABLE:
    import FreeCADGui  # type: ignore

    class HeatsinkDesignerWorkbench(FreeCADGui.Workbench):  # pragma: no cover
        MenuText = "HeatsinkDesigner"
        ToolTip = "Generate CNC-friendly heatsinks"

        def __init__(self) -> None:
            super().__init__()
            self.Icon = _icon_path()

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
