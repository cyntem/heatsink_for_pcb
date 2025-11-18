"""Simple solid builder for heatsinks based on a selected face/sketch shape.

Создаёт обычный Part::Feature "Heatsink" с готовой формой радиатора.
Параметры управляются через Task Panel (Face/Sketch Mode).

Особенности:
- для скетча: внешний контур = самая большая петля; остальные петли
  используются как отверстия и вырезаются из основания и рёбер;
- для выбранной грани: используем саму грань (она уже включает отверстия);
- у созданного объекта назначается ViewProviderHeatsink, который по
  двойному клику открывает то же GUI-окно (Heatsink from Face/Sketch).
"""

from __future__ import annotations

from typing import Dict, Optional, List, Tuple

try:
    import FreeCAD as App  # type: ignore
    import Part  # type: ignore
except Exception:  # pragma: no cover
    App = None  # type: ignore
    Part = None  # type: ignore

try:
    import FreeCADGui as Gui  # type: ignore
except Exception:  # pragma: no cover
    Gui = None  # type: ignore


# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    prefix = "[HSD] "
    if App is not None:
        App.Console.PrintMessage(prefix + msg + "\n")
    else:
        print(prefix + msg)


def _log_err(msg: str) -> None:
    prefix = "[HSD-ERR] "
    if App is not None:
        App.Console.PrintError(prefix + msg + "\n")
    else:
        print(prefix + msg)


# ---------- выбор базовой грани и отверстий ---------------------------------


def _largest_face_from_list(faces) -> Optional["Part.Face"]:
    """Вернуть грань с максимальной площадью из списка faces."""
    best = None
    best_area = 0.0
    for f in faces:
        try:
            a = abs(f.Area)
        except Exception:
            continue
        if not f.isNull() and a > best_area:
            best = f
            best_area = a
    return best


def _outer_and_hole_wires_from_shape(
    shape,
) -> Tuple[Optional["Part.Wire"], List["Part.Wire"]]:
    """Определить внешний контур (наибольший wire) и остальные как отверстия."""
    if Part is None:
        return None, []

    try:
        wires = list(getattr(shape, "Wires", []))
        _log(f" _outer_and_hole_wires_from_shape: shape has {len(wires)} wires")
    except Exception as exc:
        _log_err(f" _outer_and_hole_wires_from_shape: cannot get Wires: {exc}")
        return None, []

    if not wires:
        return None, []

    areas: List[Tuple[float, "Part.Wire"]] = []
    for w in wires:
        try:
            f = Part.Face(w)
            areas.append((abs(f.Area), w))
        except Exception:
            continue

    if not areas:
        return None, []

    areas.sort(key=lambda t: t[0], reverse=True)
    outer_wire = areas[0][1]
    hole_wires = [w for _, w in areas[1:]]
    _log(
        f" _outer_and_hole_wires_from_shape: outer area={areas[0][0]:.3f}, "
        f"holes={len(hole_wires)}"
    )
    return outer_wire, hole_wires


def _make_base_face_and_holes(shape):
    """Сделать базовую грань и список отверстий.

    Возвращает кортеж (base_face, hole_wires):

    - при выборе грани: (face, []) — отверстия уже в самой грани;
    - при выборе скетча:
        * base_face строится по внешнему контуру (наибольший wire),
        * список hole_wires возвращается отдельно для вырезания.
    """
    if Part is None:
        _log_err("make_base_face_and_holes: Part is None")
        return None, []

    _log("make_base_face_and_holes: start")

    # 1) если shape уже содержит грани
    try:
        faces = list(getattr(shape, "Faces", []))
        _log(f" make_base_face_and_holes: shape has {len(faces)} faces")
    except Exception as exc:
        _log_err(f" make_base_face_and_holes: cannot get Faces: {exc}")
        faces = []

    if faces:
        best = _largest_face_from_list(faces)
        if best is not None:
            _log(
                " make_base_face_and_holes: using largest existing face, "
                f"Area={best.Area:.3f}"
            )
            # При выборе грани отверстия уже присутствуют в самой грани
            return best, []

    # 2) скетч / набор wires: outer = наибольший контур, остальные = отверстия
    outer_wire, hole_wires = _outer_and_hole_wires_from_shape(shape)
    if outer_wire is not None:
        try:
            base_face = Part.Face(outer_wire)
        except Exception as exc:
            _log_err(f" make_base_face_and_holes: Part.Face(outer_wire) failed: {exc}")
            base_face = None
        if base_face is not None and not base_face.isNull():
            _log(
                " make_base_face_and_holes: built base_face from outer wire "
                f"(holes={len(hole_wires)})"
            )
            return base_face, hole_wires

    # 3) fallback — плоскость по bbox без отверстий
    bb = shape.BoundBox
    _log(
        " make_base_face_and_holes: falling back to plane from bbox "
        f"Lx={bb.XLength:.3f} Ly={bb.YLength:.3f} at "
        f"({bb.XMin:.3f},{bb.YMin:.3f},{bb.ZMin:.3f})"
    )
    p = App.Vector(bb.XMin, bb.YMin, bb.ZMin)
    n = App.Vector(0, 0, 1)
    try:
        base_face = Part.makePlane(bb.XLength, bb.YLength, p, n)
        return base_face, []
    except Exception as exc:
        _log_err(f" make_base_face_and_holes: Part.makePlane failed: {exc}")
        try:
            box = Part.makeBox(bb.XLength, bb.YLength, 0.1, p)
            _log(" make_base_face_and_holes: fallback Part.makeBox -> first face")
            return box.Faces[0], []
        except Exception as exc2:
            _log_err(
                f" make_base_face_and_holes: Part.makeBox fallback failed: {exc2}"
            )
            return None, []


# ---------- генерация рёбер/пинов -------------------------------------------


def _create_straight_fins(
    base_face, base_thickness_mm: float, params: Dict[str, float]
):
    """Сделать прямые рёбра вдоль X (по длине)."""
    bb = base_face.BoundBox
    length = bb.XLength
    width = bb.YLength
    x0 = bb.XMin
    y0 = bb.YMin
    z_top = bb.ZMax + base_thickness_mm

    fin_t = params.get("fin_thickness_mm", 2.0)
    gap = params.get("fin_gap_mm", 3.0)
    fin_h = params.get("fin_height_mm", 20.0)

    pitch = fin_t + gap
    y = y0 + gap
    fins = []
    while y + fin_t <= y0 + width - gap + 1e-6:
        fin = Part.makeBox(length, fin_t, fin_h, App.Vector(x0, y, z_top))
        fins.append(fin)
        y += pitch

    _log(
        f" create_straight_fins: count={len(fins)}, "
        f"fin_t={fin_t}, gap={gap}, fin_h={fin_h}"
    )

    if not fins:
        return None, 0.0
    return Part.Compound(fins), fin_h


def _create_crosscut_pins(
    base_face, base_thickness_mm: float, params: Dict[str, float]
):
    """Сделать решётку пинов (crosscut)."""
    bb = base_face.BoundBox
    length = bb.XLength
    width = bb.YLength
    x0 = bb.XMin
    y0 = bb.YMin
    z_top = bb.ZMax + base_thickness_mm

    groove = params.get("groove_width_mm", 3.0)
    pin_size = params.get("pin_size_mm", 3.0)
    pin_h = params.get("pin_height_mm", 15.0)

    pitch = groove + pin_size
    xs = []
    ys = []

    x = x0 + groove
    while x + pin_size <= x0 + length - groove + 1e-6:
        xs.append(x)
        x += pitch

    y = y0 + groove
    while y + pin_size <= y0 + width - groove + 1e-6:
        ys.append(y)
        y += pitch

    fins = []
    for xx in xs:
        for yy in ys:
            pin = Part.makeBox(pin_size, pin_size, pin_h, App.Vector(xx, yy, z_top))
            fins.append(pin)

    _log(
        f" create_crosscut_pins: count={len(fins)}, "
        f"pin_size={pin_size}, groove={groove}, pin_h={pin_h}"
    )

    if not fins:
        return None, 0.0
    return Part.Compound(fins), pin_h


def _create_pin_fin(base_face, base_thickness_mm: float, params: Dict[str, float]):
    """Сделать квадратные пины по сетке (pin_fin)."""
    bb = base_face.BoundBox
    length = bb.XLength
    width = bb.YLength
    x0 = bb.XMin
    y0 = bb.YMin
    z_top = bb.ZMax + base_thickness_mm

    pin_size = params.get("pin_size_mm", 5.0)
    pitch = params.get("pitch_mm", 8.0)
    pin_h = params.get("pin_height_mm", 20.0)

    xs = []
    ys = []
    x = x0
    while x + pin_size <= x0 + length + 1e-6:
        xs.append(x)
        x += pitch

    y = y0
    while y + pin_size <= y0 + width + 1e-6:
        ys.append(y)
        y += pitch

    fins = []
    for xx in xs:
        for yy in ys:
            pin = Part.makeBox(pin_size, pin_size, pin_h, App.Vector(xx, yy, z_top))
            fins.append(pin)

    _log(
        f" create_pin_fin: count={len(fins)}, "
        f"pin_size={pin_size}, pitch={pitch}, pin_h={pin_h}"
    )

    if not fins:
        return None, 0.0
    return Part.Compound(fins), pin_h


def _create_fins_solid(
    heatsink_type: str, base_face, base_thickness_mm: float, params: Dict[str, float]
):
    """Диспетчер создания рёбер / пинов."""
    _log(f" create_fins_solid: type={heatsink_type}")
    if heatsink_type == "straight_fins":
        return _create_straight_fins(base_face, base_thickness_mm, params)
    if heatsink_type == "crosscut":
        return _create_crosscut_pins(base_face, base_thickness_mm, params)
    if heatsink_type == "pin_fin":
        return _create_pin_fin(base_face, base_thickness_mm, params)
    _log(" create_fins_solid: no fins for this type (likely solid_plate)")
    return None, 0.0


# ---------- ViewProvider для двойного клика ----------------------------------


class ViewProviderHeatsink:
    """View provider: по двойному клику открывает Face/Sketch Task Panel."""

    def __init__(self, vobj):
        self.Object = vobj.Object
        vobj.Proxy = self

    def doubleClicked(self, vobj) -> bool:  # pragma: no cover - GUI only
        _log("ViewProviderHeatsink.doubleClicked")
        if Gui is None:
            _log_err(" ViewProviderHeatsink.doubleClicked: Gui is None")
            return False
        try:
            # делаем так, как если бы пользователь вручную выделил объект
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(self.Object.Document, self.Object.Name)
        except Exception as exc:
            _log_err(
                f" ViewProviderHeatsink.doubleClicked: selection failed: {exc}"
            )
            return False

        try:
            # запускаем ту же команду, что и из тулбара
            Gui.runCommand("HSD_HeatsinkFromFace")
            return True
        except Exception as exc:
            _log_err(
                f" ViewProviderHeatsink.doubleClicked: runCommand failed: {exc}"
            )
            return False

    # Иконка (опционально). Если что-то пойдёт не так — вернём пустую строку.
    def getIcon(self) -> str:  # pragma: no cover - GUI only
        try:
            import os
            import HeatsinkDesigner  # type: ignore

            base_dir = os.path.dirname(HeatsinkDesigner.__file__)
            return os.path.join(base_dir, "icons", "heatsink.svg")
        except Exception:
            return ""


# ---------- основная фабрика -------------------------------------------------


def create_heatsink_feature(
    heatsink_type: str,
    source_shape,
    base_thickness_mm: float,
    params: Dict[str, float],
    material_key: Optional[str] = None,  # зарезервировано на будущее
    doc=None,
):
    """Создать обычный Part::Feature с формой радиатора на основе shape.

    - Внешний контур: наибольший face / wire.
    - Внутренние контуры (для скетча): вычитаются из основания и рёбер.
    - Установить ViewProviderHeatsink для обработки двойного клика.
    """
    if App is None or Part is None:  # pragma: no cover
        raise RuntimeError("FreeCAD with Part workbench is required")

    if doc is None:
        doc = App.ActiveDocument or App.newDocument("HeatsinkDesigner")

    if source_shape is None:
        raise ValueError("source_shape is None")
    if not hasattr(source_shape, "BoundBox"):
        raise ValueError("source_shape has no BoundBox")

    bb = source_shape.BoundBox
    _log(
        "create_heatsink_feature: start, "
        f"type={heatsink_type}, base_thickness={base_thickness_mm}, "
        f"bbox Lx={bb.XLength:.3f} Ly={bb.YLength:.3f} at "
        f"({bb.XMin:.3f},{bb.YMin:.3f},{bb.ZMin:.3f})"
    )

    base_face, hole_wires = _make_base_face_and_holes(source_shape)
    if base_face is None or base_face.isNull():
        _log_err("create_heatsink_feature: base_face is None or isNull")
        raise ValueError("Could not create base face from selection")

    _log(
        "create_heatsink_feature: base_face created; "
        f"bbox Lx={base_face.BoundBox.XLength:.3f} "
        f"Ly={base_face.BoundBox.YLength:.3f}, "
        f"holes={len(hole_wires)}"
    )

    normal = App.Vector(0, 0, 1)

    # Основание (пока без отверстий)
    base_solid = base_face.extrude(normal * base_thickness_mm)
    _log(
        " create_heatsink_feature: base_solid built; "
        f"Volume={getattr(base_solid, 'Volume', 'N/A')}"
    )

    # Вырезаем отверстия в основании (только для скетча: hole_wires != [])
    if hole_wires:
        for w in hole_wires:
            try:
                hole_face = Part.Face(w)
                hole_prism = hole_face.extrude(normal * base_thickness_mm)
                base_solid = base_solid.cut(hole_prism)
            except Exception as exc:
                _log_err(f" create_heatsink_feature: base hole cut failed: {exc}")
        _log(
            " create_heatsink_feature: base_solid after holes; "
            f"Volume={getattr(base_solid, 'Volume', 'N/A')}"
        )

    # Если просто плита
    if heatsink_type == "solid_plate":
        result_solid = base_solid
        _log(" create_heatsink_feature: type=solid_plate, using base_solid only")
    else:
        fins_solid, fin_height_mm = _create_fins_solid(
            heatsink_type, base_face, base_thickness_mm, params
        )
        if fins_solid is None or fin_height_mm <= 0:
            _log(
                f" create_heatsink_feature: no fins (fins_solid=None or "
                f"fin_height={fin_height_mm}), fallback to base_solid"
            )
            result_solid = base_solid
        else:
            _log(
                " create_heatsink_feature: fins_solid created; "
                f"Volume={getattr(fins_solid, 'Volume', 'N/A')}, "
                f"fin_height={fin_height_mm}"
            )
            total_height = base_thickness_mm + fin_height_mm
            contour_prism = base_face.extrude(normal * total_height)
            _log(
                " create_heatsink_feature: contour_prism built; "
                f"Volume={getattr(contour_prism, 'Volume', 'N/A')}, "
                f"total_height={total_height}"
            )
            try:
                fins_trimmed = fins_solid.common(contour_prism)
                _log(
                    " create_heatsink_feature: fins_trimmed via common; "
                    f"Volume={getattr(fins_trimmed, 'Volume', 'N/A')}"
                )
            except Exception as exc:
                _log_err(f" create_heatsink_feature: fins_solid.common failed: {exc}")
                fins_trimmed = fins_solid

            # Вырезаем отверстия и из рёбер (по тем же hole_wires,
            # но экструдируем на полную высоту)
            if hole_wires:
                for w in hole_wires:
                    try:
                        hole_face = Part.Face(w)
                        hole_prism_full = hole_face.extrude(normal * total_height)
                        fins_trimmed = fins_trimmed.cut(hole_prism_full)
                    except Exception as exc:
                        _log_err(
                            f" create_heatsink_feature: fins hole cut failed: {exc}"
                        )
                _log(
                    " create_heatsink_feature: fins_trimmed after holes; "
                    f"Volume={getattr(fins_trimmed, 'Volume', 'N/A')}"
                )

            try:
                result_solid = Part.Compound([base_solid, fins_trimmed])
                _log(
                    " create_heatsink_feature: result_solid via Part.Compound; "
                    f"Volume={getattr(result_solid, 'Volume', 'N/A')}, "
                    f"Solids={len(getattr(result_solid, 'Solids', []))}"
                )
            except Exception as exc:
                _log_err(f" create_heatsink_feature: Part.Compound failed: {exc}")
                result_solid = base_solid

    # Создаём обычный Part::Feature
    obj = doc.addObject("Part::Feature", "Heatsink")
    obj.Shape = result_solid

    # Небольшая справочная инфа в свойствах
    try:
        obj.addProperty(
            "App::PropertyString",
            "HeatsinkType",
            "Heatsink",
            "Тип радиатора (для информации)",
        )
        obj.HeatsinkType = heatsink_type

        obj.addProperty(
            "App::PropertyFloat",
            "BaseThickness",
            "Heatsink",
            "Толщина основания (мм, справочно)",
        )
        obj.BaseThickness = float(base_thickness_mm)

        for k, v in params.items():
            pname = f"Param_{k}"
            try:
                obj.addProperty(
                    "App::PropertyFloat",
                    pname,
                    "Heatsink",
                    f"Параметр {k} (мм, справочно)",
                )
                setattr(obj, pname, float(v))
            except Exception:
                pass
    except Exception as exc:
        _log_err(f" create_heatsink_feature: adding properties failed: {exc}")

    # Настройки отображения
    try:
        if hasattr(obj, "ViewObject"):
            vo = obj.ViewObject
            vo.Visibility = True
            try:
                vo.ShapeColor = (0.8, 0.3, 0.0)
            except Exception:
                pass
            try:
                vo.LineWidth = 2.0
            except Exception:
                pass
    except Exception as exc:
        _log_err(f" create_heatsink_feature: setting ViewObject failed: {exc}")

    # Назначаем view provider, чтобы по двойному клику открывать Task Panel
    try:
        if Gui is not None and hasattr(obj, "ViewObject"):
            ViewProviderHeatsink(obj.ViewObject)
    except Exception as exc:
        _log_err(f" create_heatsink_feature: ViewProviderHeatsink failed: {exc}")

    doc.recompute()
    _log(
        "create_heatsink_feature: document recomputed; "
        f"final Volume={getattr(obj.Shape, 'Volume', 'N/A')}"
    )

    if Gui is not None:
        try:
            if Gui.ActiveDocument and Gui.ActiveDocument.ActiveView:
                Gui.ActiveDocument.ActiveView.fitAll()
                _log("create_heatsink_feature: ActiveView.fitAll() called")
        except Exception as exc:
            _log_err(f" create_heatsink_feature: fitAll failed: {exc}")

    return obj
