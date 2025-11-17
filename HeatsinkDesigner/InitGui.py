"""GUI workbench registration for HeatsinkDesigner."""
from __future__ import annotations

import os
import FreeCADGui as Gui  # FreeCAD GUI API


class HeatsinkDesignerWorkbench(Gui.Workbench):
    """FreeCAD GUI workbench for parametric heatsink generation."""

    # Текст в выпадающем списке воркбенчей
    MenuText = "HeatsinkDesigner"
    # Подсказка в статусной строке
    ToolTip = "Generate CNC-friendly heatsinks"

    def __init__(self):
        super().__init__()

        # Надёжное вычисление пути к иконке прямо здесь, без внешних функций
        try:
            base_dir = os.path.dirname(__file__)
        except NameError:
            # На всякий случай, если FreeCAD уберёт __file__
            base_dir = os.getcwd()

        self.Icon = os.path.join(base_dir, "icons", "heatsink.svg")

        # сюда позже добавишь свои команды, когда они появятся
        self.list = []  # например: ["HSD_CreateHeatsink"]

    def Initialize(self):
        """Регистрация команд в FreeCAD.

        FreeCAD вызывает этот метод, когда пользователь впервые переключается
        на этот воркбенч.
        """
        for cmd in self.list:
            Gui.addCommand(cmd, None)

    def GetClassName(self):  # noqa: N802
        # Для чисто питонового воркбенча нужно вернуть именно эту строку
        return "Gui::PythonWorkbench"


# РЕГИСТРАЦИЯ ВОРКБЕНЧА В GUI:
Gui.addWorkbench(HeatsinkDesignerWorkbench())
