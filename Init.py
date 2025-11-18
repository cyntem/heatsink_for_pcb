"""FreeCAD entry point for the HeatsinkDesigner workbench.

This thin wrapper lets FreeCAD's Addon Manager treat the repository
root as the module directory while delegating the real logic to the
`HeatsinkDesigner` package.
"""

from HeatsinkDesigner.Init import FreeCADInit, Initialize, dependency_status

__all__ = ["FreeCADInit", "Initialize", "dependency_status"]
