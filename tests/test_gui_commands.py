"""Tests for GUI command helpers."""

from types import SimpleNamespace

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
