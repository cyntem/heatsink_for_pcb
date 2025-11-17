"""Geometry helpers for heatsink shapes and (опционально) 3D-модели FreeCAD."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# ---- устойчивые импорты других модулей пакета ------------------------------
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

# ---- необязательная зависимость от FreeCAD/Part ----------------------------
try:  # pragma: no cover - в тестах FreeCAD скорее всего недоступен
    import FreeCAD as App  # type: ignore[import]
    import Part  # type: ignore[import]

    FREECAD_AVAILABLE = True
except Exception:  # pragma: no cover
    App = None  # type: ignore[assignment]
    Part = None  # type: ignore[assignment]
    FREECAD_AVAILABLE = False


# ============================================================================
#  Базовые структуры
# ============================================================================


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


# ============================================================================
#  Геометрия для теплового расчёта (без FreeCAD)
# ============================================================================


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


# ============================================================================
#  3D-геометрия FreeCAD
# ============================================================================


def _require_freecad() -> None:
    if not FREECAD_AVAILABLE:
        raise RuntimeError(
            "FreeCAD/Part недоступны. Запустите код внутри FreeCAD или установите FreeCAD Python."
        )


def _make_base_shape(base: BaseDimensions):
    _require_freecad()
    return Part.makeBox(base.length_mm, base.width_mm, base.base_thickness_mm)


def _shape_solid_plate(base: BaseDimensions):
    return _make_base_shape(base)


def _shape_straight_fins(
    base: BaseDimensions,
    fin_height_mm: float,
    fin_thickness_mm: float,
    fin_gap_mm: float,
):
    _require_freecad()
    base_shape = _make_base_shape(base)
    shape = base_shape

    pitch = fin_thickness_mm + fin_gap_mm
    # Кол-во рёбер — чтобы всё более-менее влезло
    fin_count = max(int((base.width_mm + fin_gap_mm) // pitch), 1)

    total_fins_width = fin_count * fin_thickness_mm + (fin_count - 1) * fin_gap_mm
    y0 = (base.width_mm - total_fins_width) / 2.0

    for i in range(fin_count):
        y = y0 + i * (fin_thickness_mm + fin_gap_mm)
        fin_box = Part.makeBox(base.length_mm, fin_thickness_mm, fin_height_mm)
        fin_box.translate(App.Vector(0.0, y, base.base_thickness_mm))
        shape = shape.fuse(fin_box)

    return shape


def _shape_crosscut(
    base: BaseDimensions,
    pin_height_mm: float,
    pin_size_mm: float,
    groove_width_mm: float,
):
    _require_freecad()
    base_shape = _make_base_shape(base)
    shape = base_shape

    pitch = pin_size_mm + groove_width_mm

    count_x = max(int((base.length_mm + groove_width_mm) // pitch), 1)
    count_y = max(int((base.width_mm + groove_width_mm) // pitch), 1)

    total_x = count_x * pin_size_mm + (count_x - 1) * groove_width_mm
    total_y = count_y * pin_size_mm + (count_y - 1) * groove_width_mm

    x0 = (base.length_mm - total_x) / 2.0
    y0 = (base.width_mm - total_y) / 2.0

    for ix in range(count_x):
        for iy in range(count_y):
            x = x0 + ix * (pin_size_mm + groove_width_mm)
            y = y0 + iy * (pin_size_mm + groove_width_mm)
            pin_box = Part.makeBox(pin_size_mm, pin_size_mm, pin_height_mm)
            pin_box.translate(App.Vector(x, y, base.base_thickness_mm))
            shape = shape.fuse(pin_box)

    return shape


def _shape_pin_fin(
    base: BaseDimensions,
    pin_height_mm: float,
    pin_size_mm: float,
    pitch_mm: float,
):
    _require_freecad()
    base_shape = _make_base_shape(base)
    shape = base_shape

    count_x = max(int((base.length_mm + pitch_mm - pin_size_mm) // pitch_mm), 1)
    count_y = max(int((base.width_mm + pitch_mm - pin_size_mm) // pitch_mm), 1)

    total_x = (count_x - 1) * pitch_mm + pin_size_mm
    total_y = (count_y - 1) * pitch_mm + pin_size_mm

    x0 = (base.length_mm - total_x) / 2.0
    y0 = (base.width_mm - total_y) / 2.0

    for ix in range(count_x):
        for iy in range(count_y):
            x = x0 + ix * pitch_mm
            y = y0 + iy * pitch_mm
            pin_box = Part.makeBox(pin_size_mm, pin_size_mm, pin_height_mm)
            pin_box.translate(App.Vector(x, y, base.base_thickness_mm))
            shape = shape.fuse(pin_box)

    return shape


def create_heatsink_solid(
    heatsink_type: str,
    base: BaseDimensions,
    params: Dict[str, float],
    doc=None,
    name_prefix: str = "Heatsink",
):
    """Создать 3D-модель радиатора в FreeCAD.

    Возвращает объект документа (Part::Feature). Работает только если
    FreeCAD/Part доступны, иначе бросает RuntimeError.
    """
    _require_freecad()

    doc = doc or App.ActiveDocument
    if doc is None:
        doc = App.newDocument()

    # Выбор формы по типу
    if heatsink_type == "solid_plate":
        shape = _shape_solid_plate(base)
    elif heatsink_type == "straight_fins":
        shape = _shape_straight_fins(
            base,
            fin_height_mm=float(params["fin_height_mm"]),
            fin_thickness_mm=float(params["fin_thickness_mm"]),
            fin_gap_mm=float(params["fin_gap_mm"]),
        )
    elif heatsink_type == "crosscut":
        shape = _shape_crosscut(
            base,
            pin_height_mm=float(params["pin_height_mm"]),
            pin_size_mm=float(params["pin_size_mm"]),
            groove_width_mm=float(params["groove_width_mm"]),
        )
    elif heatsink_type == "pin_fin":
        shape = _shape_pin_fin(
            base,
            pin_height_mm=float(params["pin_height_mm"]),
            pin_size_mm=float(params["pin_size_mm"]),
            pitch_mm=float(params["pitch_mm"]),
        )
    else:
        raise ValueError(f"Unknown heatsink type: {heatsink_type}")

    obj = doc.addObject("Part::Feature", f"{name_prefix}_{heatsink_type}")
    obj.Label = f"Heatsink ({heatsink_type})"
    obj.Shape = shape
    doc.recompute()
    return obj
