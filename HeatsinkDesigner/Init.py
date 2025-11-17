"""FreeCAD entry point stub for HeatsinkDesigner workbench."""
from __future__ import annotations

import importlib


def _load_dependency_status():
    """Import ``dependency_status`` whether or not the module is a package.

    When FreeCAD executes this file directly (for example during manual
    installation), ``__package__`` may be unset, making relative imports
    fail with ``attempted relative import with no known parent package``.
    Falling back to an absolute import keeps the module working in both
    contexts.
    """

    try:
        from .thermal_model import dependency_status as loader
        return loader
    except ImportError:
        # ``thermal_model`` sits next to this file, so absolute import works
        # even when Python does not treat it as a package yet.
        return importlib.import_module("thermal_model").dependency_status


dependency_status = _load_dependency_status()


def Initialize() -> str:
    """Return a short message; FreeCAD calls this when loading the module."""

    status = dependency_status()
    warnings = status.warning_messages()
    if warnings:
        return " | ".join(warnings)
    return "HeatsinkDesigner initialized"


def FreeCADInit() -> None:  # pragma: no cover - entry point for FreeCAD
    Initialize()
