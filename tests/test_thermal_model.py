import math

from HeatsinkDesigner.thermal_model import (
    Environment,
    GeometrySummary,
    convert_mm_to_m,
    dependency_status,
    estimate_heat_dissipation,
    generate_performance_curve,
)


def test_dependency_status_has_flags():
    status = dependency_status()
    assert isinstance(status.ht_available, bool)
    assert isinstance(status.fluids_available, bool)


def test_convert_mm_to_m():
    assert math.isclose(convert_mm_to_m(10.0), 0.01)


def test_heat_estimation_surface_temperature():
    geometry = GeometrySummary(base_area_m2=0.04, effective_area_m2=0.08, characteristic_length_m=0.1)
    env = Environment(temperature_c=25.0, relative_humidity=50.0)
    result = estimate_heat_dissipation(geometry, env, power_input_w=40.0, target_overtemp_c=40.0)
    assert result.surface_temperature_c > env.temperature_c
    assert result.heat_dissipation_w == 40.0


def test_performance_curve_shape():
    geometry = GeometrySummary(base_area_m2=0.02, effective_area_m2=0.05, characteristic_length_m=0.08)
    curves = generate_performance_curve(geometry)
    assert "RH 30%" in curves
    assert len(curves["RH 30%"]) > 5
