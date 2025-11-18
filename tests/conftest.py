import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Provide lightweight FreeCAD stubs so modules import without the GUI runtime
if "FreeCADGui" not in sys.modules:
    class _DummyWorkbench:
        def __init__(self, *args, **kwargs):
            pass

        def appendToolbar(self, *args, **kwargs):
            pass

        def appendMenu(self, *args, **kwargs):
            pass

    def _noop(*args, **kwargs):
        return None

    sys.modules["FreeCADGui"] = SimpleNamespace(
        Workbench=_DummyWorkbench,
        addCommand=_noop,
        addWorkbench=_noop,
        doCommand=_noop,
    )
