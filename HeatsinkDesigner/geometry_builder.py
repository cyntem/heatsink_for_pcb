"""Geometry helpers used to approximate heatsink shapes and build FreeCAD solids."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# Try absolute imports first (as a package), then fallback to local modules
try:
    from HeatsinkDesigner.cnc_defaults import DEFAULT_CNC_PARAMS
except ImportError:  # pragma: no cover
    from cnc_defaults import DEFAULT_CNC_PARAMS  # type: ignore[no-redef]

try:
    from HeatsinkDesigner.thermal_model import (
        GeometrySummary,
        convert_mm_to_m,
        effective_area_with_fins,
        estimate_fin_efficiency,
    )
except ImportError:  # pragma: no cover
    from thermal_model import (  # type: ignore[no-redef]
        GeometrySummary,
        convert_mm_to_m,
        effective_area_with_fins,
        estimate_fin_efficiency,
    )


# ---------------------------------------------------------------------------
# Analytical geometry (for thermal calculations)
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
    fin_count: Optional[int] = None
    fin_area_m2: Optional[float] = None


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _base_area(base: BaseDimensions) -> float:
    return convert_mm_to_m(base.length_mm) * convert_mm_to_m(base.width_mm)


def _characteristic_length(base: BaseDimensions) -> float:
    return max(convert_mm_to_m(base.length_mm), convert_mm_to_m(base.width_mm))


def build_solid_plate(
    base: BaseDimensions,
    material_conductivity_w_mk: float,
) -> GeometryDetails:
    """Return geometry summary for a solid plate heatsink."""
    _validate_positive(base.base_thickness_mm, "base_thickness_mm")
    area = _base_area(base)
    geometry = GeometrySummary(
        base_area_m2=area,
        effective_area_m2=area,
        characteristic_length_m=_characteristic_length(base),
    )
    notes = [
        f"Solid plate geometry; base thickness {base.base_thickness_mm:.1f} mm, "
        f"k ≈ {material_conductivity_w_mk:.1f} W/m·K",
    ]
    return GeometryDetails(geometry=geometry, notes=notes)


def build_straight_fins(
    base: BaseDimensions,
    fin_height_mm: float,
    fin_thickness_mm: float,
    fin_gap_mm: float,
    material_conductivity_w_mk: float,
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
    fin_eff = estimate_fin_efficiency(
        fin_thickness_mm,
        fin_height_mm,
        material_conductivity_w_mk=material_conductivity_w_mk,
    )
    effective_area = effective_area_with_fins(base_area, fin_area_m2, fin_eff)

    geometry = GeometrySummary(
        base_area_m2=base_area,
        effective_area_m2=effective_area,
        characteristic_length_m=_characteristic_length(base),
    )
    notes = [
        f"Straight fins: {fin_count} pcs, efficiency {fin_eff:.2f}, "
        f"material k ≈ {material_conductivity_w_mk:.1f} W/m·K",
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
    material_conductivity_w_mk: float,
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
    fin_eff = estimate_fin_efficiency(
        pin_size_mm,
        pin_height_mm,
        material_conductivity_w_mk=material_conductivity_w_mk,
    )
    effective_area = effective_area_with_fins(base_area, pin_area_m2, fin_eff)

    geometry = GeometrySummary(
        base_area_m2=base_area,
        effective_area_m2=effective_area,
        characteristic_length_m=_characteristic_length(base),
    )
    notes = [
        f"Crosscut pins: {pin_count} pcs at pitch {pitch_mm:.1f} mm, "
        f"material k ≈ {material_conductivity_w_mk:.1f} W/m·K",
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
    material_conductivity_w_mk: float,
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
    fin_eff = estimate_fin_efficiency(
        pin_size_mm,
        pin_height_mm,
        material_conductivity_w_mk=material_conductivity_w_mk,
    )
    effective_area = effective_area_with_fins(base_area, pin_area_m2, fin_eff)

    geometry = GeometrySummary(
        base_area_m2=base_area,
        effective_area_m2=effective_area,
        characteristic_length_m=_characteristic_length(base),
    )
    notes = [
        f"Pin-fin count: {pin_count} at pitch {pitch_mm:.1f} mm, "
        f"material k ≈ {material_conductivity_w_mk:.1f} W/m·K",
    ]
    return GeometryDetails(
        geometry=geometry,
        notes=notes,
        fin_count=pin_count,
        fin_area_m2=pin_area_m2,
    )


def build_geometry(
    heatsink_type: str,
    base_dimensions: Tuple[float, float, float],
    params: Optional[Dict[str, float]] = None,
) -> GeometryDetails:
    """Dispatch geometry creation based on heatsink type key.

    params may include key "material_conductivity_w_mk".
    """
    params = dict(params) if params is not None else {}
    base = BaseDimensions(
        length_mm=base_dimensions[0],
        width_mm=base_dimensions[1],
        base_thickness_mm=base_dimensions[2],
    )
    defaults = DEFAULT_CNC_PARAMS.get(heatsink_type, {})
    merged = {**defaults, **params}

    material_k = float(merged.pop("material_conductivity_w_mk", 205.0))

    if heatsink_type == "solid_plate":
        return build_solid_plate(base, material_k)
    if heatsink_type == "straight_fins":
        return build_straight_fins(
            base,
            fin_height_mm=merged["fin_height_mm"],
            fin_thickness_mm=merged["fin_thickness_mm"],
            fin_gap_mm=merged["fin_gap_mm"],
            material_conductivity_w_mk=material_k,
        )
    if heatsink_type == "crosscut":
        return build_crosscut(
            base,
            pin_height_mm=merged["pin_height_mm"],
            pin_size_mm=merged["pin_size_mm"],
            groove_width_mm=merged["groove_width_mm"],
            material_conductivity_w_mk=material_k,
        )
    if heatsink_type == "pin_fin":
        return build_pin_fin(
            base,
            pin_height_mm=merged["pin_height_mm"],
            pin_size_mm=merged["pin_size_mm"],
            pitch_mm=merged["pitch_mm"],
            material_conductivity_w_mk=material_k,
        )
    raise ValueError(f"Unknown heatsink type: {heatsink_type}")


# ---------------------------------------------------------------------------
# 3D geometry in FreeCAD (arbitrary outline)
# ---------------------------------------------------------------------------

def _profile_to_face(profile_shape, base: BaseDimensions):
    """Convert the selected profile (face/sketch) to Part.Face.

    Preserve holes when possible (use Wires).
    On error return a rectangular L×W face.
    """
    try:
        import Part  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Part module is unavailable") from exc

    if profile_shape is None:
        return Part.makePlane(base.length_mm, base.width_mm)

    shape = profile_shape
    if hasattr(shape, "Shape"):
        shape = shape.Shape  # type: ignore[assignment]

    # If faces already exist – use the first (often with holes)
    try:
        if hasattr(shape, "Faces") and shape.Faces:  # type: ignore[attr-defined]
            return shape.Faces[0]  # type: ignore[index]
    except Exception:
        pass

    # If there is a set of wires (outer + inner) – build face with holes
    try:
        if hasattr(shape, "Wires") and shape.Wires:  # type: ignore[attr-defined]
            return Part.Face(shape.Wires)  # type: ignore[arg-type]
    except Exception:
        pass

    # Fallback: outer contour only
    try:
        if hasattr(shape, "OuterWire"):  # type: ignore[attr-defined]
            return Part.Face(shape.OuterWire)  # type: ignore[arg-type]
    except Exception:
        pass

    # Last resort
    try:
        return Part.Face(shape)  # type: ignore[arg-type]
    except Exception:
        return Part.makePlane(base.length_mm, base.width_mm)


def _create_fins_solid(
    Part,
    App,
    heatsink_type: str,
    base: BaseDimensions,
    params: Dict[str, float],
    bb,
    z_base: float,
):
    """Create a combined solid of all fins/pins.

    z_base – absolute Z coordinate of the base top where fins start.
    """
    x0 = bb.XMin
    y0 = bb.YMin
    L = bb.XLength
    W = bb.YLength

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
    """Create a 3D heatsink model in FreeCAD.

    Fins always start exactly at the top of the base (do not sink into it).
    If boolean operations fail on outlines with holes
    there is a fallback mode without trimming by contour.
    """
    try:
        import FreeCAD as App  # type: ignore
        import Part  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "3D geometry creation is only available inside FreeCAD"
        ) from exc

    if doc is None:
        doc = App.ActiveDocument or App.newDocument("HeatsinkDesigner")

    base_face = _profile_to_face(profile_shape, base)
    bb_face = base_face.BoundBox
    normal = App.Vector(0, 0, 1)  # fixed upward normal for now

    # Base
    base_solid = base_face.extrude(normal * base.base_thickness_mm)

    if heatsink_type == "solid_plate":
        obj = doc.addObject("Part::Feature", "Heatsink_SolidPlate")
        obj.Label = "Heatsink solid plate"
        obj.Shape = base_solid
        doc.recompute()
        return obj

    # Fins start at the top of the base
    z_top_base = bb_face.ZMax + base.base_thickness_mm

    fins_solid, fin_height_mm = _create_fins_solid(
        Part,
        App,
        heatsink_type,
        base,
        params,
        bb_face,
        z_top_base,
    )
    if fins_solid is None or fin_height_mm <= 0:
        obj = doc.addObject("Part::Feature", "Heatsink_BaseOnly")
        obj.Label = "Heatsink base only"
        obj.Shape = base_solid
        doc.recompute()
        return obj

    total_height = base.base_thickness_mm + fin_height_mm
    contour_prism = base_face.extrude(normal * total_height)

    # Attempt to trim fins to the real outline (with holes)
    try:
        fins_trimmed = fins_solid.common(contour_prism)
        result_solid = base_solid.fuse(fins_trimmed)
    except Exception:
        # Fallback: no trimming, fins via bounding box
        result_solid = base_solid.fuse(fins_solid)

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
