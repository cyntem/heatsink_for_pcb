"""Geometry helpers for heatsink area estimation and FreeCAD solid creation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# Вместо относительных импортов — абсолютные + fallback
try:
    from HeatsinkDesigner.cnc_defaults import DEFAULT_CNC_PARAMS
except ImportError:
    from cnc_defaults import DEFAULT_CNC_PARAMS  # type: ignore[no-redef]

try:
    from HeatsinkDesigner.thermal_model import (
        GeometrySummary,
        convert_mm_to_m,
        effective_area_with_fins,
        estimate_fin_efficiency,
    )
except ImportError:
    from thermal_model import (  # type: ignore[no-redef]
        GeometrySummary,
        convert_mm_to_m,
        effective_area_with_fins,
        estimate_fin_efficiency,
    )

# ---------------------------------------------------------------------------
# Аналитическая геометрия (для тепловых расчётов)
# ---------------------------------------------------------------------------


@dataclass
class BaseDimensions:
    """Base plate dimensions in millimeters."""

    length_mm: float
    width_mm: float
    base_thickness_mm: float


@dataclass
class GeometryDetails:
    """Detailed breakdown of generated geometry."""

    geometry: GeometrySummary
    notes: List[str] = field(default_factory=list)
    fin_count: int | None = None
    fin_area_m2: float | None = None


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _base_area(base: BaseDimensions) -> float:
    return convert_mm_to_m(base.length_mm) * convert_mm_to_m(base.width_mm)


def _characteristic_length(base: BaseDimensions) -> float:
    return max(convert_mm_to_m(base.length_mm), convert_mm_to_m(base.width_mm))


def build_solid_plate(base: BaseDimensions) -> GeometryDetails:
    """Return geometry summary for a solid plate heatsink."""

    _validate_positive(base.base_thickness_mm, "base_thickness_mm")
    area = _base_area(base)
    geometry = GeometrySummary(
        base_area_m2=area,
        effective_area_m2=area,
        characteristic_length_m=_characteristic_length(base),
    )
    return GeometryDetails(geometry=geometry, notes=["Solid plate geometry"])


def build_straight_fins(
    base: BaseDimensions,
    fin_height_mm: float,
    fin_thickness_mm: float,
    fin_gap_mm: float,
) -> GeometryDetails:
    """Approximate straight fin layout and effective area."""

    for value, name in [
        (fin_height_mm, "fin_height_mm"),
        (fin_thickness_mm, "fin_thickness_mm"),
        (fin_gap_mm, "fin_gap_mm"),
    ]:
        _validate_positive(value, name)

    pitch_mm = fin_thickness_mm + fin_gap_mm
    usable_width_mm = base.width_mm - fin_gap_mm
    if pitch_mm <= 0 or usable_width_mm <= 0:
        raise ValueError("Invalid fin pitch or width for straight fins")

    fin_count = int(usable_width_mm // pitch_mm) + 1
    fin_area_m2 = fin_count * 2 * convert_mm_to_m(fin_height_mm) * convert_mm_to_m(
        base.length_mm
    )
    base_area = _base_area(base)
    fin_eff = estimate_fin_efficiency(fin_thickness_mm, fin_height_mm)
    effective_area = effective_area_with_fins(base_area, fin_area_m2, fin_eff)

    geometry = GeometrySummary(
        base_area_m2=base_area,
        effective_area_m2=effective_area,
        characteristic_length_m=_characteristic_length(base),
    )
    notes = [
        f"Straight fins: {fin_count} pcs, efficiency {fin_eff:.2f}",
    ]
    return GeometryDetails(
        geometry=geometry,
        notes=notes,
        fin_count=fin_count,
        fin_area_m2=fin_area_m2,
    )


def build_crosscut(
    base: BaseDimensions,
    pin_height_mm: float,
    pin_size_mm: float,
    groove_width_mm: float,
) -> GeometryDetails:
    """Approximate grid (crosscut) geometry."""

    for value, name in [
        (pin_height_mm, "pin_height_mm"),
        (pin_size_mm, "pin_size_mm"),
        (groove_width_mm, "groove_width_mm"),
    ]:
        _validate_positive(value, name)

    pitch_mm = pin_size_mm + groove_width_mm
    if pitch_mm <= 0:
        raise ValueError("Invalid pitch in crosscut geometry")

    count_x = int((base.length_mm + groove_width_mm) // pitch_mm)
    count_y = int((base.width_mm + groove_width_mm) // pitch_mm)
    pin_count = max(count_x, 1) * max(count_y, 1)
    pin_side_m = convert_mm_to_m(pin_size_mm)
    pin_area_m2 = pin_count * 4 * pin_side_m * convert_mm_to_m(pin_height_mm)
    base_area = _base_area(base)
    fin_eff = estimate_fin_efficiency(pin_size_mm, pin_height_mm)
    effective_area = effective_area_with_fins(base_area, pin_area_m2, fin_eff)

    geometry = GeometrySummary(
        base_area_m2=base_area,
        effective_area_m2=effective_area,
        characteristic_length_m=_characteristic_length(base),
    )
    notes = [
        f"Crosscut pins: {pin_count} pcs at pitch {pitch_mm:.1f} mm",
    ]
    return GeometryDetails(
        geometry=geometry,
        notes=notes,
        fin_count=pin_count,
        fin_area_m2=pin_area_m2,
    )


def build_pin_fin(
    base: BaseDimensions,
    pin_height_mm: float,
    pin_size_mm: float,
    pitch_mm: float,
) -> GeometryDetails:
    """Approximate pin-fin array."""

    for value, name in [
        (pin_height_mm, "pin_height_mm"),
        (pin_size_mm, "pin_size_mm"),
        (pitch_mm, "pitch_mm"),
    ]:
        _validate_positive(value, name)

    count_x = int((base.length_mm + pitch_mm - pin_size_mm) // pitch_mm)
    count_y = int((base.width_mm + pitch_mm - pin_size_mm) // pitch_mm)
    pin_count = max(count_x, 1) * max(count_y, 1)
    pin_area_m2 = pin_count * 4 * convert_mm_to_m(pin_size_mm) * convert_mm_to_m(
        pin_height_mm
    )
    base_area = _base_area(base)
    fin_eff = estimate_fin_efficiency(pin_size_mm, pin_height_mm)
    effective_area = effective_area_with_fins(base_area, pin_area_m2, fin_eff)

    geometry = GeometrySummary(
        base_area_m2=base_area,
        effective_area_m2=effective_area,
        characteristic_length_m=_characteristic_length(base),
    )
    notes = [f"Pin-fin count: {pin_count} at pitch {pitch_mm:.1f} mm"]
    return GeometryDetails(
        geometry=geometry,
        notes=notes,
        fin_count=pin_count,
        fin_area_m2=pin_area_m2,
    )


def build_geometry(
    heatsink_type: str,
    base_dimensions: Tuple[float, float, float],
    params: Dict[str, float] | None = None,
) -> GeometryDetails:
    """Dispatch geometry creation based on heatsink type key."""

    params = params or {}
    base = BaseDimensions(
        length_mm=base_dimensions[0],
        width_mm=base_dimensions[1],
        base_thickness_mm=base_dimensions[2],
    )
    defaults = DEFAULT_CNC_PARAMS.get(heatsink_type, {})
    merged = {**defaults, **params}

    if heatsink_type == "solid_plate":
        return build_solid_plate(base)
    if heatsink_type == "straight_fins":
        return build_straight_fins(
            base,
            fin_height_mm=merged["fin_height_mm"],
            fin_thickness_mm=merged["fin_thickness_mm"],
            fin_gap_mm=merged["fin_gap_mm"],
        )
    if heatsink_type == "crosscut":
        return build_crosscut(
            base,
            pin_height_mm=merged["pin_height_mm"],
            pin_size_mm=merged["pin_size_mm"],
            groove_width_mm=merged["groove_width_mm"],
        )
    if heatsink_type == "pin_fin":
        return build_pin_fin(
            base,
            pin_height_mm=merged["pin_height_mm"],
            pin_size_mm=merged["pin_size_mm"],
            pitch_mm=merged["pitch_mm"],
        )
    raise ValueError(f"Unknown heatsink type: {heatsink_type}")


# ---------------------------------------------------------------------------
# 3D-геометрия в FreeCAD: построение по прямоугольнику или произвольному
# контуру (face/sketch)
# ---------------------------------------------------------------------------


def _profile_to_face(profile_shape, base: BaseDimensions):
    """Преобразовать выбранный профиль (face/sketch) в Part.Face.

    Если что-то пошло не так, возвращаем прямоугольную плоскость L×W.
    """
    try:
        import Part  # type: ignore
    except Exception as exc:  # pragma: no cover - используется только в FreeCAD
        raise RuntimeError("Модуль Part недоступен") from exc

    if profile_shape is None:
        return Part.makePlane(base.length_mm, base.width_mm)

    shape = profile_shape
    # Если это объект документа (Sketch и т.п.)
    if hasattr(shape, "Shape"):
        shape = shape.Shape  # type: ignore[assignment]

    # Если есть список граней — берём первую
    try:
        if hasattr(shape, "Faces") and shape.Faces:  # type: ignore[attr-defined]
            return shape.Faces[0]  # type: ignore[index]
    except Exception:
        pass

    # Если есть внешняя проволока (OuterWire)
    try:
        if hasattr(shape, "OuterWire"):  # type: ignore[attr-defined]
            return Part.Face(shape.OuterWire)  # type: ignore[arg-type]
    except Exception:
        pass

    # Последний шанс — пытаемся сделать Face прямо из shape
    try:
        return Part.Face(shape)  # type: ignore[arg-type]
    except Exception:
        # Совсем fallback: простая плоскость
        return Part.makePlane(base.length_mm, base.width_mm)


def _create_fins_solid(
    Part, App, heatsink_type: str, base: BaseDimensions, params: Dict[str, float], bb
) -> Tuple[Optional[object], float]:
    """Создать объединённый solid всех рёбер/пинов и вернуть (solid, высота_ребра_мм).

    Если рёбра не нужны (solid plate) — вернуть (None, 0.0).
    """
    x0 = bb.XMin
    y0 = bb.YMin
    L = bb.XLength
    W = bb.YLength
    z_base = base.base_thickness_mm

    solids: List[object] = []
    max_height = 0.0

    if heatsink_type == "straight_fins":
        fin_t = float(params["fin_thickness_mm"])
        fin_gap = float(params["fin_gap_mm"])
        fin_h = float(params["fin_height_mm"])
        pitch = fin_t + fin_gap
        usable_width = W - fin_gap
        if pitch <= 0 or usable_width <= 0:
            return None, 0.0
        fin_count = int(usable_width // pitch) + 1
        for i in range(fin_count):
            y = y0 + fin_gap + i * pitch
            box = Part.makeBox(L, fin_t, fin_h)
            box.Placement.Base = App.Vector(x0, y, z_base)
            solids.append(box)
        max_height = fin_h

    elif heatsink_type == "crosscut":
        groove = float(params["groove_width_mm"])
        pin_size = float(params["pin_size_mm"])
        pin_h = float(params["pin_height_mm"])
        pitch = groove + pin_size
        if pitch <= 0:
            return None, 0.0
        count_x = int((L + groove) // pitch)
        count_y = int((W + groove) // pitch)
        count_x = max(count_x, 1)
        count_y = max(count_y, 1)
        for ix in range(count_x):
            for iy in range(count_y):
                x = x0 + groove + ix * pitch
                y = y0 + groove + iy * pitch
                box = Part.makeBox(pin_size, pin_size, pin_h)
                box.Placement.Base = App.Vector(x, y, z_base)
                solids.append(box)
        max_height = pin_h

    elif heatsink_type == "pin_fin":
        pin_size = float(params["pin_size_mm"])
        pitch = float(params["pitch_mm"])
        pin_h = float(params["pin_height_mm"])
        if pitch <= 0:
            return None, 0.0
        count_x = int((L + pitch - pin_size) // pitch)
        count_y = int((W + pitch - pin_size) // pitch)
        count_x = max(count_x, 1)
        count_y = max(count_y, 1)
        for ix in range(count_x):
            for iy in range(count_y):
                x = x0 + ix * pitch
                y = y0 + iy * pitch
                box = Part.makeBox(pin_size, pin_size, pin_h)
                box.Placement.Base = App.Vector(x, y, z_base)
                solids.append(box)
        max_height = pin_h

    else:
        return None, 0.0

    if not solids:
        return None, 0.0

    fins_solid = solids[0]
    for s in solids[1:]:
        fins_solid = fins_solid.fuse(s)
    return fins_solid, max_height


def create_heatsink_solid(
    heatsink_type: str,
    base: BaseDimensions,
    params: Dict[str, float],
    doc=None,
    profile_shape=None,
):
    """Создать 3D-модель радиатора в FreeCAD.

    - Если profile_shape задан (face/sketch), основание и рёбра обрезаются
      по произвольному контуру.
    - Если profile_shape = None, используется прямоугольник длиной/шириной
      BaseDimensions.
    """
    try:
        import FreeCAD as App  # type: ignore
        import Part  # type: ignore
    except Exception as exc:  # pragma: no cover - выполняется только в FreeCAD
        raise RuntimeError(
            "Создание 3D-геометрии возможно только внутри FreeCAD"
        ) from exc

    if doc is None:
        doc = App.ActiveDocument or App.newDocument("HeatsinkDesigner")

    base_face = _profile_to_face(profile_shape, base)
    normal = App.Vector(0, 0, 1)

    # Основание
    base_solid = base_face.extrude(normal * base.base_thickness_mm)

    # Просто пластина
    if heatsink_type == "solid_plate":
        obj = doc.addObject("Part::Feature", "Heatsink_SolidPlate")
        obj.Label = "Heatsink solid plate"
        obj.Shape = base_solid
        doc.recompute()
        return obj

    # Рёбра/пины
    fins_solid, fin_height_mm = _create_fins_solid(
        Part, App, heatsink_type, base, params, base_face.BoundBox
    )
    if fins_solid is None or fin_height_mm <= 0:
        obj = doc.addObject("Part::Feature", "Heatsink_BaseOnly")
        obj.Label = "Heatsink base only"
        obj.Shape = base_solid
        doc.recompute()
        return obj

    # Призма по контуру для обрезки рёбер по произвольному контуру
    total_height = base.base_thickness_mm + fin_height_mm
    contour_prism = base_face.extrude(normal * total_height)

    fins_trimmed = fins_solid.common(contour_prism)
    result_solid = base_solid.fuse(fins_trimmed)

    name_prefix = {
        "straight_fins": "Heatsink_StraightFins",
        "crosscut": "Heatsink_Crosscut",
        "pin_fin": "Heatsink_PinFin",
    }.get(heatsink_type, "Heatsink")

    obj = doc.addObject("Part::Feature", name_prefix)
    obj.Label = name_prefix
    obj.Shape = result_solid
    doc.recompute()
    return obj
