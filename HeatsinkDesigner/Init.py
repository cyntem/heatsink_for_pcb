"""FreeCAD entry point stub for HeatsinkDesigner workbench."""
from __future__ import annotations

from .thermal_model import dependency_status


def Initialize() -> str:
    """Return a short message; FreeCAD calls this when loading the module."""

    status = dependency_status()
    warnings = status.warning_messages()
    if warnings:
        return " | ".join(warnings)
    return "HeatsinkDesigner initialized"


def FreeCADInit() -> None:  # pragma: no cover - entry point for FreeCAD
    Initialize()
