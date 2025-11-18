"""GUI workbench registration for HeatsinkDesigner."""
from __future__ import annotations

import os
from pathlib import Path

import FreeCADGui as Gui  # FreeCAD GUI API


def _module_dir() -> Path:
    """Return the folder containing this module.

    Prefers ``__file__`` (normal runtime) and falls back to ``__spec__`` so
    tests can import the module without a filesystem-backed ``__file__``.
    """

    if "__file__" in globals():
        return Path(__file__).parent
    spec = globals().get("__spec__")
    if spec and getattr(spec, "origin", None):
        return Path(spec.origin).parent
    return Path(os.getcwd())


class HeatsinkDesignerWorkbench(Gui.Workbench):
    """FreeCAD GUI workbench for parametric heatsink generation."""

    MenuText = "HeatsinkDesigner"
    ToolTip = "Generate CNC-friendly heatsinks"

    def __init__(self):
        super().__init__()

        # Reliable icon path resolution
        base_dir = _module_dir()

        self.Icon = str(base_dir / "icons" / "heatsink.svg")

        # Commands will be loaded in Initialize()
        self._commands = {}
        self._cmd_names = []

    # --- internal command loader ----------------------------------------
    def _load_commands(self):
        """Try to import gui_commands in several ways."""

        last_exc = None

        # 1) Relative import — normal case when packaged
        try:
            from . import gui_commands as gc  # type: ignore[attr-defined]
            return gc.COMMANDS  # type: ignore[attr-defined]
        except Exception as exc:
            last_exc = exc

        # 2) Import as HeatsinkDesigner.gui_commands package
        try:
            import HeatsinkDesigner.gui_commands as gc  # type: ignore[attr-defined]
            return gc.COMMANDS  # type: ignore[attr-defined]
        except Exception as exc:
            last_exc = exc

        # 3) Fallback: gui_commands as a top-level module
        try:
            import gui_commands as gc  # type: ignore[attr-defined]
            return gc.COMMANDS  # type: ignore[attr-defined]
        except Exception as exc:
            last_exc = exc

        # None of the options worked — print to the Report view
        # Build valid Python code: print("...", <repr(exc)>)
        if last_exc is not None:
            Gui.doCommand(
                'print("HeatsinkDesigner: failed to import gui_commands; last error:", %r)'
                % (last_exc,)
            )
        else:
            Gui.doCommand(
                'print("HeatsinkDesigner: failed to import gui_commands (no details)")'
            )

        return {}

    # --- workbench initialization --------------------------------------------
    def Initialize(self):
        """Register commands in FreeCAD.

        FreeCAD calls this method when the user first
        switches to this workbench.
        """
        self._commands = self._load_commands()
        self._cmd_names = list(self._commands.keys())

        # Register commands
        for name, handler in self._commands.items():
            Gui.addCommand(name, handler)

        # Toolbar and menu only if commands are available
        if self._cmd_names:
            self.appendToolbar("HeatsinkDesigner", self._cmd_names)
            self.appendMenu("&HeatsinkDesigner", self._cmd_names)

    def GetClassName(self):  # noqa: N802
        # Pure Python workbench must return this string
        return "Gui::PythonWorkbench"


# Workbench registration in the GUI
Gui.addWorkbench(HeatsinkDesignerWorkbench())
