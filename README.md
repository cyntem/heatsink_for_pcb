# Heatsink Designer Workbench (FreeCAD)

Расширение **HeatsinkDesignerWB** добавляет в FreeCAD инструмент для параметрической генерации радиаторов и оценки их теплоотдачи. Код организован как лёгкий Python-пакет, который можно поместить в папку `Mod` FreeCAD и использовать даже без GUI для предварительных расчётов.

## Возможности

- Четыре CNC-дружественных типа радиаторов: сплошная пластина, прямые фрезерованные рёбра, решётка (crosscut) и штыревые пины.
- Два режима работы (плоскость/эскиз и задание габаритов), пригодные для Task Panel в FreeCAD.
- Упрощённые тепловые расчёты на основе конвекции при естественном охлаждении и учёте эффективности рёбер.
- Генерация графиков зависимости рассеиваемой мощности от температуры окружающей среды и влажности.
- Проверка наличия опциональных библиотек (`ht`, `fluids`) с понятными сообщениями.

## Структура

- `HeatsinkDesigner/Init.py` и `HeatsinkDesigner/InitGui.py` — точки входа Workbench’а, безопасные для окружений без FreeCAD.
- `cnc_defaults.py` — минимальные размеры и рекомендуемые значения под настольный ЧПУ.
- `heatsink_types.py` — описание поддерживаемых типов и параметров.
- `geometry_builder.py` — приближённое построение геометрии и расчёт эффективной площади теплообмена.
- `thermal_model.py` — тепловые расчёты, зависящие от параметров геометрии и среды.
- `gui_face_mode.py` и `gui_dim_mode.py` — логика двух режимов Task Panel без привязки к конкретным UI-элементам.
- `icons/` — иконка Workbench’а.
- `tests/` — минимальные модульные тесты тепловой части и генератора геометрии.

## Требования

- Python 3.x (используется тот, что встроен в FreeCAD 1.0+).
- Рекомендуемые внешние пакеты: `numpy`, `matplotlib`, `ht`, `fluids`. При отсутствии `ht` и `fluids` расчёты используют встроённые приближённые коэффициенты.

`requirements.txt` содержит полный список опциональных зависимостей. Их можно установить через встроенный в FreeCAD интерпретатор Python:

- **Windows:** `"C:\\Program Files\\FreeCAD 1.0\\bin\\python.exe" -m pip install -r requirements.txt`
- **macOS (приложение):** `/Applications/FreeCAD.app/Contents/Resources/bin/python3 -m pip install -r requirements.txt`
- **Linux (классическая установка):** `python3 -m pip install -r requirements.txt`
- **Linux Snap:** `snap run --shell freecad --command python3 -m pip install -r requirements.txt`

## Установка и запуск в FreeCAD

1. Скопируйте папку `HeatsinkDesigner` в каталог `Mod` вашего FreeCAD:
   - для классических установок: `~/.local/share/FreeCAD/Mod` (Linux), `%APPDATA%/FreeCAD/Mod` (Windows), `~/Library/Preferences/FreeCAD/Mod` (macOS);
   - для Snap-пакета FreeCAD 1.0.2: `~/snap/freecad/common/Mod`.
2. Перезапустите FreeCAD. В списке Workbench появится запись **HeatsinkDesigner** с двумя командами: генерация по грани/эскизу и по габаритам.
3. В каждом Task Panel вы увидите параметры выбранного типа радиатора и кнопки для генерации модели, расчёта теплового режима и построения графика.

> Начиная с FreeCAD 1.0.2 модуль корректно инициализируется, даже если `FreeCADGui.__spec__` не задан (типичный случай в Snap-сборке).

## Использование без FreeCAD

Тепловую часть можно использовать как обычный модуль Python:

```python
from HeatsinkDesigner.geometry_builder import build_geometry
from HeatsinkDesigner.thermal_model import Environment, estimate_heat_dissipation

details = build_geometry("straight_fins", (120.0, 80.0, 5.0), {
    "fin_height_mm": 20.0,
    "fin_thickness_mm": 2.0,
    "fin_gap_mm": 3.0,
})
result = estimate_heat_dissipation(details.geometry, Environment(), power_input_w=60)
print(result)
```

## Тестирование

Запустите тесты локально (понадобится `pytest`):

```bash
pytest
```

Команда покрывает базовые проверки тепловых расчётов и генерации геометрии.
