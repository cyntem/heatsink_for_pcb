"""GUI workbench registration for HeatsinkDesigner."""
from __future__ import annotations

import os

import FreeCADGui as Gui  # FreeCAD GUI API


class HeatsinkDesignerWorkbench(Gui.Workbench):
    """FreeCAD GUI workbench for parametric heatsink generation."""

    MenuText = "HeatsinkDesigner"
    ToolTip = "Generate CNC-friendly heatsinks"

    def __init__(self):
        super().__init__()

        # Надёжное вычисление пути к иконке
        try:
            base_dir = os.path.dirname(__file__)
        except NameError:
            base_dir = os.getcwd()

        self.Icon = os.path.join(base_dir, "icons", "heatsink.svg")

        # Команды будут загружены в Initialize()
        self._commands = {}
        self._cmd_names = []

    # --- внутренний загрузчик команд ----------------------------------------
    def _load_commands(self):
        """Попытаться импортировать gui_commands несколькими способами."""

        last_exc = None

        # 1) Относительный импорт — нормальный случай (пакет HeatsinkDesigner)
        try:
            from . import gui_commands as gc  # type: ignore[attr-defined]
            return gc.COMMANDS  # type: ignore[attr-defined]
        except Exception as exc:
            last_exc = exc

        # 2) Импорт как пакета HeatsinkDesigner.gui_commands
        try:
            import HeatsinkDesigner.gui_commands as gc  # type: ignore[attr-defined]
            return gc.COMMANDS  # type: ignore[attr-defined]
        except Exception as exc:
            last_exc = exc

        # 3) Фоллбек: gui_commands как верхнеуровневый модуль
        try:
            import gui_commands as gc  # type: ignore[attr-defined]
            return gc.COMMANDS  # type: ignore[attr-defined]
        except Exception as exc:
            last_exc = exc

        # Ни один вариант не сработал — печатаем в Report view
        # Формируем валидный Python-код: print("...", <repr(exc)>)
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

    # --- инициализация воркбенча --------------------------------------------
    def Initialize(self):
        """Регистрация команд в FreeCAD.

        FreeCAD вызывает этот метод, когда пользователь впервые
        переключается на этот воркбенч.
        """
        self._commands = self._load_commands()
        self._cmd_names = list(self._commands.keys())

        # Регистрируем команды
        for name, handler in self._commands.items():
            Gui.addCommand(name, handler)

        # Панель инструментов и меню, только если команды есть
        if self._cmd_names:
            self.appendToolbar("HeatsinkDesigner", self._cmd_names)
            self.appendMenu("&HeatsinkDesigner", self._cmd_names)

    def GetClassName(self):  # noqa: N802
        # Для чисто питонового воркбенча нужно вернуть именно эту строку
        return "Gui::PythonWorkbench"


# Регистрация воркбенча в GUI
Gui.addWorkbench(HeatsinkDesignerWorkbench())
