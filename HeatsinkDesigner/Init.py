"""FreeCAD console entry point for HeatsinkDesigner workbench."""
from __future__ import annotations


def _load_dependency_status():
    """Вернуть функцию dependency_status из thermal_model.

    Работает и когда HeatsinkDesigner установлен как пакет (относительный импорт),
    и когда FreeCAD просто исполняет Init.py как обычный скрипт (absolute import).
    """

    # 1) Нормальный случай: пакет установлен, работает относительный импорт
    try:
        from .thermal_model import dependency_status as loader
        return loader
    except Exception:
        # 2) FreeCAD запускает модуль без пакета: пробуем абсолютный импорт
        try:
            from importlib import import_module
        except Exception:
            # Даже importlib недоступен – возвращаем заглушку
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
            # thermal_model не найден – возвращаем заглушку
            def _fallback_dependency_status():
                class _DummyStatus:
                    def warning_messages(self):
                        return ["thermal_model module not found"]

                return _DummyStatus()

            return _fallback_dependency_status


# Привязываем функцию dependency_status один раз при загрузке модуля
dependency_status = _load_dependency_status()


def Initialize() -> str:
    """Краткое сообщение; FreeCAD вызывает это при загрузке модуля (консоль)."""

    status = dependency_status()
    warnings = status.warning_messages()
    if warnings:
        return " | ".join(warnings)
    return "HeatsinkDesigner initialized"


def FreeCADInit() -> None:  # pragma: no cover - entry point for FreeCAD
    """Точка входа для FreeCAD (общая инициализация)."""
    Initialize()
