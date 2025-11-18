from HeatsinkDesigner.geometry_builder import build_geometry


def test_build_solid_plate_area():
    details = build_geometry("solid_plate", (100.0, 50.0, 10.0))
    assert details.geometry.base_area_m2 > 0
    assert details.geometry.effective_area_m2 == details.geometry.base_area_m2


def test_build_straight_fins_effective_area_increases():
    params = {"fin_height_mm": 20.0, "fin_thickness_mm": 2.0, "fin_gap_mm": 3.0}
    base_dims = (120.0, 60.0, 5.0)
    details = build_geometry("straight_fins", base_dims, params)
    assert details.fin_count is not None and details.fin_count > 0
    assert details.geometry.effective_area_m2 > details.geometry.base_area_m2


def test_build_pin_fin_counts():
    params = {"pin_height_mm": 20.0, "pin_size_mm": 5.0, "pitch_mm": 8.0}
    base_dims = (80.0, 80.0, 5.0)
    details = build_geometry("pin_fin", base_dims, params)
    assert details.fin_count is not None and details.fin_count > 0
