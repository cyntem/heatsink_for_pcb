"""GUI entry point for the HeatsinkDesigner workbench.

It forwards GUI registration to the package module so that installing
via FreeCAD's Addon Manager works without moving files around.
"""

from HeatsinkDesigner.InitGui import HeatsinkDesignerWorkbench

__all__ = ["HeatsinkDesignerWorkbench"]
