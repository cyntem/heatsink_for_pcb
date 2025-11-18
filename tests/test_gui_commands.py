"""Tests for GUI command helpers."""

from types import SimpleNamespace
import importlib

from HeatsinkDesigner import gui_commands


def test_import_taskpanel_prefers_relative(monkeypatch):
    """Relative import should be attempted before absolute names."""

    sentinel = type("DummyPanel", (), {})
    calls: list[tuple[str, str | None]] = []

    def fake_import(name: str, package: str | None = None):
        calls.append((name, package))
        if name == ".gui_dim_mode" and package == "HeatsinkDesigner":
            return SimpleNamespace(DimensionModeTaskPanel=sentinel)
        raise ImportError("not found")

    monkeypatch.setattr(gui_commands, "import_module", fake_import)

    assert gui_commands._import_taskpanel("gui_dim_mode", "DimensionModeTaskPanel") is sentinel
    assert calls[0] == (".gui_dim_mode", "HeatsinkDesigner")


def test_import_taskpanel_loads_neighbor_file(monkeypatch, tmp_path):
    """Fallback loader should import modules next to gui_commands when packaged loosely."""

    panel_src = """
class DimensionModeTaskPanel:
    pass
"""
    neighbor = tmp_path / "gui_dim_mode.py"
    neighbor.write_text(panel_src)

    # Simulate a top-level import where __package__ is None
    monkeypatch.setattr(gui_commands, "__package__", None)
    monkeypatch.setattr(gui_commands, "__file__", str(tmp_path / "gui_commands.py"))

    # Force standard import attempts to fail so the fallback is used
    def fail_import(name: str, package: str | None = None):
        raise ImportError("not available")

    monkeypatch.setattr(gui_commands, "import_module", fail_import)

    PanelClass = gui_commands._import_taskpanel("gui_dim_mode", "DimensionModeTaskPanel")

    assert PanelClass is not None
    assert PanelClass.__name__ == "DimensionModeTaskPanel"
    # Ensure the module was registered in sys.modules for future imports
    assert importlib.import_module("gui_dim_mode").DimensionModeTaskPanel is PanelClass
