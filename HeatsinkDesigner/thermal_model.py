"""Thermal estimation helpers for the Heatsink Designer workbench."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

HT_AVAILABLE = importlib.util.find_spec("ht") is not None
FLUIDS_AVAILABLE = importlib.util.find_spec("fluids") is not None

if HT_AVAILABLE:
    import ht  # type: ignore
else:
    ht = None  # type: ignore

if FLUIDS_AVAILABLE:
    import fluids  # type: ignore
else:
    fluids = None  # type: ignore

DEFAULT_T_AMB_C = 25.0
DEFAULT_REL_HUMIDITY = 50.0
DEFAULT_DELTA_T = 40.0
AIR_THERMAL_CONDUCTIVITY = 0.026  # W/(m*K) at ~300 K
AIR_PRANDTL = 0.71
AIR_DENSITY = 1.184  # kg/m^3 at 25 C
AIR_VISCOSITY = 1.85e-5  # Pa*s


@dataclass
class DependencyStatus:
    """Holds dependency availability information."""

    ht_available: bool
    fluids_available: bool

    def warning_messages(self) -> List[str]:
        messages: List[str] = []
        if not self.ht_available:
            messages.append(
                "Не установлена библиотека ht. Установите через pip: pip install ht"
            )
        if not self.fluids_available:
            messages.append(
                "Не установлена библиотека fluids. Установите через pip: pip install fluids"
            )
        return messages


@dataclass
class Environment:
    """Ambient environment description."""

    temperature_c: float = DEFAULT_T_AMB_C
    relative_humidity: float = DEFAULT_REL_HUMIDITY


@dataclass
class GeometrySummary:
    """Minimal geometry data for thermal estimation."""

    base_area_m2: float
    effective_area_m2: float
    characteristic_length_m: float


@dataclass
class ThermalResult:
    """Result of heat dissipation estimation."""

    convection_coefficient: float
    heat_dissipation_w: float
    surface_temperature_c: float




def dependency_status() -> DependencyStatus:
    """Return availability flags for optional dependencies."""

    return DependencyStatus(ht_available=HT_AVAILABLE, fluids_available=FLUIDS_AVAILABLE)


def convert_mm_to_m(value_mm: float) -> float:
    """Convert millimeters to meters."""

    return value_mm / 1000.0


def _saturation_pressure_pa(temp_c: float) -> float:
    """Approximate saturation vapor pressure for water using Tetens formula."""

    temp_k = temp_c + 273.15
    return 610.94 * np.exp((17.625 * temp_c) / (temp_c + 243.04))


def compute_air_properties(temp_c: float, relative_humidity: float) -> Dict[str, float]:
    """Return simplified air properties.

    Uses fluids when available; otherwise falls back to engineering constants
    sufficient for heat transfer estimation.
    """

    if FLUIDS_AVAILABLE and fluids is not None:
        saturation_pressure = _saturation_pressure_pa(temp_c)
        partial_vapor_pressure = relative_humidity / 100.0 * saturation_pressure
        gas_constant_air = 287.058
        density = (101325 - partial_vapor_pressure) / (gas_constant_air * (temp_c + 273.15))
    else:
        density = AIR_DENSITY

    return {
        "density": density,
        "thermal_conductivity": AIR_THERMAL_CONDUCTIVITY,
        "prandtl": AIR_PRANDTL,
        "viscosity": AIR_VISCOSITY,
    }


def convection_coefficient_natural(geometry: GeometrySummary, delta_t: float) -> float:
    """Estimate natural convection coefficient using laminar plate correlation."""

    properties = compute_air_properties(DEFAULT_T_AMB_C, DEFAULT_REL_HUMIDITY)
    beta = 1.0 / (DEFAULT_T_AMB_C + 273.15)
    g = 9.81
    grashof = (
        g
        * beta
        * (delta_t)
        * geometry.characteristic_length_m ** 3
        * properties["density"] ** 2
        / (properties["viscosity"] ** 2)
    )
    rayleigh = grashof * properties["prandtl"]
    nu = 0.68 + (0.67 * rayleigh ** 0.25) / (
        (1 + (0.492 / properties["prandtl"]) ** (9.0 / 16.0)) ** (4.0 / 9.0)
    )
    h = nu * properties["thermal_conductivity"] / geometry.characteristic_length_m
    return max(h, 3.0)


def convection_coefficient_forced(velocity_m_per_s: float) -> float:
    """Estimate forced convection coefficient for moderate airflow."""

    return 10.45 - velocity_m_per_s + 10.0 * velocity_m_per_s ** 0.5


def effective_area_with_fins(
    base_area_m2: float,
    fin_area_m2: float,
    fin_efficiency: float,
) -> float:
    """Combine base and fin areas into effective area."""

    return base_area_m2 + fin_efficiency * fin_area_m2


def estimate_fin_efficiency(
    fin_thickness_mm: float,
    fin_height_mm: float,
    material_conductivity_w_mk: float = 205.0,
    convection_coeff_w_m2k: float = 8.0,
) -> float:
    """Estimate fin efficiency for straight plate fins."""

    thickness_m = convert_mm_to_m(fin_thickness_mm)
    height_m = convert_mm_to_m(fin_height_mm)
    if thickness_m <= 0 or height_m <= 0:
        return 0.0
    m = (2.0 * convection_coeff_w_m2k / (material_conductivity_w_mk * thickness_m)) ** 0.5
    eta = np.tanh(m * height_m) / (m * height_m)
    return float(np.clip(eta, 0.0, 1.0))


def estimate_heat_dissipation(
    geometry: GeometrySummary,
    environment: Environment,
    power_input_w: float | None = None,
    target_overtemp_c: float = DEFAULT_DELTA_T,
) -> ThermalResult:
    """Compute convection coefficient and resulting heat transfer capability."""

    h = convection_coefficient_natural(geometry, target_overtemp_c)
    heat_w = h * geometry.effective_area_m2 * target_overtemp_c

    surface_temp_c = environment.temperature_c + heat_w / (h * geometry.effective_area_m2)
    if power_input_w is not None and geometry.effective_area_m2 > 0:
        surface_temp_c = environment.temperature_c + power_input_w / (
            h * geometry.effective_area_m2
        )
        heat_w = power_input_w

    return ThermalResult(
        convection_coefficient=h,
        heat_dissipation_w=heat_w,
        surface_temperature_c=surface_temp_c,
    )


def generate_performance_curve(
    geometry: GeometrySummary,
    humidity_points: Tuple[float, ...] = (30.0, 60.0, 90.0),
    temp_range_c: Tuple[int, int, int] = (0, 81, 5),
    delta_t_c: float = DEFAULT_DELTA_T,
) -> Dict[str, List[Tuple[float, float]]]:
    """Generate Q_max vs ambient temperature curves for several humidity levels."""

    t_min, t_max, t_step = temp_range_c
    temps = list(np.arange(t_min, t_max, t_step))
    curves: Dict[str, List[Tuple[float, float]]] = {}
    for rh in humidity_points:
        data: List[Tuple[float, float]] = []
        for temp in temps:
            env = Environment(temperature_c=temp, relative_humidity=rh)
            result = estimate_heat_dissipation(geometry, env, target_overtemp_c=delta_t_c)
            data.append((temp, result.heat_dissipation_w))
        curves[f"RH {rh:.0f}%"] = data
    return curves
