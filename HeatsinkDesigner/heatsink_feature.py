"""Simple solid builder for heatsinks based on a selected face/sketch shape.

Creates a standard Part::Feature "Heatsink" with a ready heatsink solid.
Parameters are controlled through the Task Panel (Face/Sketch Mode).

Notes:
- For a sketch: the outer loop = the largest wire; other loops
  are treated as holes and cut from the base and fins;
- For a selected face: use the face itself (it already includes holes);
- The created object gets ViewProviderHeatsink, which on
  double click opens the same GUI window (Heatsink from Face/Sketch).
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


# ---------- shape helpers ---------------------------------------------------


def _shape_solids(shape) -> List["Part.Shape"]:
    """Return a list of non-null solids from a shape or fall back to [shape]."""
    solids: List["Part.Shape"] = []
    try:
        solids = [s for s in getattr(shape, "Solids", []) if not s.isNull()]
    except Exception:
        solids = []
    if solids:
        return solids
    try:
        if shape is not None and hasattr(shape, "isNull") and not shape.isNull():
            return [shape]
    except Exception:
        pass
    return []


def _refine_shape(shape):
    """Try to merge splitter faces/edges to keep a single solid when possible."""
    if shape is None:
        return None
    try:
        refined = shape.removeSplitter()
        if hasattr(refined, "isNull") and not refined.isNull():
            return refined
    except Exception as exc:
        _log_err(f" _refine_shape: removeSplitter failed: {exc}")
    return shape


def _fuse_shapes(shapes: List["Part.Shape"]):
    """Fuse a list of shapes into one and refine it."""
    fused = None
    for idx, shp in enumerate(shapes):
        try:
            if shp is None or shp.isNull():
                continue
        except Exception:
            continue
        fused = shp if fused is None else fused.fuse(shp)
    fused = _refine_shape(fused)

    # If the fuse still returns multiple solids (e.g. touching faces only),
    # try to merge them explicitly to keep a single exportable part.
    extra_solids: List["Part.Shape"] = []
    try:
        extra_solids = getattr(fused, "Solids", [])
    except Exception:
        extra_solids = []
    if fused is not None and len(extra_solids) > 1:
        merged = extra_solids[0]
        for s in extra_solids[1:]:
            try:
                merged = merged.fuse(s)
            except Exception as exc:
                _log_err(f" _fuse_shapes: secondary fuse failed: {exc}")
        fused = _refine_shape(merged)

    return fused


# ---------- selecting base face and holes ---------------------------------


def _largest_face_from_list(faces) -> Optional["Part.Face"]:
    """Return the face with the maximum area from the faces list."""
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
    """Find the outer contour (largest wire) and treat the rest as holes."""
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
    """Build the base face and collect hole wires.

    Returns a tuple (base_face, hole_wires):

    - for a selected face: (face, []) — the holes are already in the face;
    - for a selected sketch:
        * base_face is built from the outer contour (largest wire),
        * hole_wires are returned separately for cutting.
    """
    if Part is None:
        _log_err("make_base_face_and_holes: Part is None")
        return None, []

    _log("make_base_face_and_holes: start")

    # 1) if shape already contains faces
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
            # For a selected face the holes are already present
            return best, []

    # 2) sketch / set of wires: outer = largest contour, others = holes
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

    # 3) fallback — plane from bbox without holes
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


# ---------- fin/pin generation -------------------------------------------


def _create_straight_fins(
    base_face, base_thickness_mm: float, params: Dict[str, float]
):
    """Create straight fins along X (by length)."""
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
    """Create a pin grid (crosscut)."""
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
    """Create square pins on a grid (pin_fin)."""
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
    """Dispatcher for fin/pin creation."""
    _log(f" create_fins_solid: type={heatsink_type}")
    if heatsink_type == "straight_fins":
        return _create_straight_fins(base_face, base_thickness_mm, params)
    if heatsink_type == "crosscut":
        return _create_crosscut_pins(base_face, base_thickness_mm, params)
    if heatsink_type == "pin_fin":
        return _create_pin_fin(base_face, base_thickness_mm, params)
    _log(" create_fins_solid: no fins for this type (likely solid_plate)")
    return None, 0.0


# ---------- ViewProvider for double-click ----------------------------------


class ViewProviderHeatsink:
    """View provider: double-click opens the Face/Sketch Task Panel."""

    def __init__(self, vobj):
        self.Object = vobj.Object
        vobj.Proxy = self

    def doubleClicked(self, vobj) -> bool:  # pragma: no cover - GUI only
        _log("ViewProviderHeatsink.doubleClicked")
        if Gui is None:
            _log_err(" ViewProviderHeatsink.doubleClicked: Gui is None")
            return False
        try:
            # act as if the user selected the object manually
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(self.Object.Document, self.Object.Name)
        except Exception as exc:
            _log_err(
                f" ViewProviderHeatsink.doubleClicked: selection failed: {exc}"
            )
            return False

        try:
            # run the same command as from the toolbar
            Gui.runCommand("HSD_HeatsinkFromFace")
            return True
        except Exception as exc:
            _log_err(
                f" ViewProviderHeatsink.doubleClicked: runCommand failed: {exc}"
            )
            return False

    # Icon (optional). If something goes wrong, return an empty string.
    def getIcon(self) -> str:  # pragma: no cover - GUI only
        try:
            import os
            import HeatsinkDesigner  # type: ignore

            base_dir = os.path.dirname(HeatsinkDesigner.__file__)
            return os.path.join(base_dir, "icons", "heatsink.svg")
        except Exception:
            return ""


# ---------- main factory -------------------------------------------------


def create_heatsink_feature(
    heatsink_type: str,
    source_shape,
    base_thickness_mm: float,
    params: Dict[str, float],
    material_key: Optional[str] = None,  # reserved for future use
    doc=None,
):
    """Create a standard Part::Feature with heatsink geometry based on shape.

    - Outer contour: largest face / wire.
    - Inner contours (for a sketch): cut out from the base and fins.
    - Assign ViewProviderHeatsink to handle double-click.
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

    # Base (without holes for now)
    base_solid = base_face.extrude(normal * base_thickness_mm)
    _log(
        " create_heatsink_feature: base_solid built; "
        f"Volume={getattr(base_solid, 'Volume', 'N/A')}"
    )

    # Cut holes in the base (sketch only: hole_wires != [])
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

    # Solid plate only
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

            # Cut holes from fins as well (using the same hole_wires,
            # but extruded to the full height)
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
                fin_solids = _shape_solids(fins_trimmed)
                if not fin_solids:
                    _log(
                        " create_heatsink_feature: fins_trimmed produced no solids, "
                        "using base_solid only"
                    )
                    result_solid = base_solid
                else:
                    result_solid = _fuse_shapes([base_solid] + fin_solids)
                    if result_solid is None:
                        _log_err(
                            " create_heatsink_feature: fusion failed, "
                            "falling back to base_solid"
                        )
                        result_solid = base_solid
                    else:
                        solid_count = len(getattr(result_solid, "Solids", []))
                        _log(
                            " create_heatsink_feature: fused base with fins; "
                            f"Solids={solid_count}, "
                            f"Volume={getattr(result_solid, 'Volume', 'N/A')}"
                        )
            except Exception as exc:
                _log_err(f" create_heatsink_feature: fusion failed: {exc}")
                result_solid = base_solid

    # Create a regular Part::Feature
    obj = doc.addObject("Part::Feature", "Heatsink")
    obj.Shape = _refine_shape(result_solid)

    # Store small reference info in properties
    try:
        obj.addProperty(
            "App::PropertyString",
            "HeatsinkType",
            "Heatsink",
            "Heatsink type (for reference)",
        )
        obj.HeatsinkType = heatsink_type

        obj.addProperty(
            "App::PropertyFloat",
            "BaseThickness",
            "Heatsink",
            "Base thickness (mm, reference)",
        )
        obj.BaseThickness = float(base_thickness_mm)

        for k, v in params.items():
            pname = f"Param_{k}"
            try:
                obj.addProperty(
                    "App::PropertyFloat",
                    pname,
                    "Heatsink",
                    f"Parameter {k} (mm, reference)",
                )
                setattr(obj, pname, float(v))
            except Exception:
                pass
    except Exception as exc:
        _log_err(f" create_heatsink_feature: adding properties failed: {exc}")

    # Display settings
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

    # Assign view provider so double-click opens the Task Panel
    try:
        if Gui is not None and hasattr(obj, "ViewObject"):
            ViewProviderHeatsink(obj.ViewObject)
    except Exception as exc:
        _log_err(f" create_heatsink_feature: ViewProviderHeatsink failed: {exc}")

    doc.recompute()
    _log(
        "create_heatsink_feature: document recomputed; "
        f"final Volume={getattr(obj.Shape, 'Volume', 'N/A')}, "
        f"Solids={len(getattr(obj.Shape, 'Solids', []))}"
    )

    if Gui is not None:
        try:
            if Gui.ActiveDocument and Gui.ActiveDocument.ActiveView:
                Gui.ActiveDocument.ActiveView.fitAll()
                _log("create_heatsink_feature: ActiveView.fitAll() called")
        except Exception as exc:
            _log_err(f" create_heatsink_feature: fitAll failed: {exc}")

    return obj
