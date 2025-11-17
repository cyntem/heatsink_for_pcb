from pathlib import Path

import HeatsinkDesigner.InitGui as initgui

def test_module_dir_prefers_file():
    assert initgui._module_dir() == Path(initgui.__file__).parent


def test_module_dir_fallbacks_to_spec_origin(monkeypatch):
    original_file = initgui.__dict__.pop("__file__", None)
    monkeypatch.setattr(initgui, "__spec__", initgui.__spec__)
    try:
        result = initgui._module_dir()
    finally:
        if original_file is not None:
            initgui.__dict__["__file__"] = original_file
    assert result == Path(initgui.__spec__.origin).parent
