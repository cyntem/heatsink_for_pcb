"""FreeCAD console entry point for HeatsinkDesigner workbench."""
from __future__ import annotations


def _load_dependency_status():
    """Return dependency_status from thermal_model.

    Works both when HeatsinkDesigner is installed as a package (relative import),
    and when FreeCAD runs Init.py as a plain script (absolute import).
    """

    # 1) Normal case: package installed, relative import works
    try:
        from .thermal_model import dependency_status as loader
        return loader
    except Exception:
        # 2) FreeCAD runs module without package: try absolute import
        try:
            from importlib import import_module
        except Exception:
            # Even importlib is unavailable – return stub
            def _fallback_dependency_status():
                class _DummyStatus:
                    def warning_messages(self):
                        return ["importlib not available; thermal_model not loaded"]

                return _DummyStatus()

            return _fallback_dependency_status

        try:
            module = import_module("thermal_model")
            return module.dependency_status
        except Exception:
            # thermal_model not found – return stub
            def _fallback_dependency_status():
                class _DummyStatus:
                    def warning_messages(self):
                        return ["thermal_model module not found"]

                return _DummyStatus()

            return _fallback_dependency_status


# Bind dependency_status once when module loads
dependency_status = _load_dependency_status()


def Initialize() -> str:
    """Short message; FreeCAD calls this when the module is loaded (console)."""

    status = dependency_status()
    warnings = status.warning_messages()
    if warnings:
        return " | ".join(warnings)
    return "HeatsinkDesigner initialized"


def FreeCADInit() -> None:  # pragma: no cover - entry point for FreeCAD
    """Entry point for FreeCAD (general initialization)."""
    Initialize()
