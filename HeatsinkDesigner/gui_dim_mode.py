"""Task panel logic for dimension-driven mode."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Tuple

from .geometry_builder import GeometryDetails, build_geometry
from .thermal_model import Environment, estimate_heat_dissipation


@dataclass
class DimensionInput:
    length_mm: float
    width_mm: float
    base_thickness_mm: float

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.length_mm, self.width_mm, self.base_thickness_mm)


class DimensionModeController:
    """Search simple parameter grids to suggest a heatsink for the target load."""

    def __init__(self, dimension: DimensionInput) -> None:
        self.dimension = dimension

    def _iter_param_grid(self, param_grid: Dict[str, Iterable[float]]):
        keys = list(param_grid.keys())
        for values in product(*param_grid.values()):
            yield dict(zip(keys, values))

    def sweep_candidates(
        self,
        heatsink_type: str,
        param_grid: Dict[str, Iterable[float]],
        target_power_w: float,
        environment: Environment,
        max_candidates: int = 50,
    ) -> List[Tuple[GeometryDetails, float]]:
        """Evaluate a limited grid of parameters and return sorted candidates."""

        candidates: List[Tuple[GeometryDetails, float]] = []
        for idx, params in enumerate(self._iter_param_grid(param_grid)):
            if idx >= max_candidates:
                break
            geometry = build_geometry(heatsink_type, self.dimension.to_tuple(), params)
            result = estimate_heat_dissipation(
                geometry.geometry, environment, target_power_w, target_overtemp_c=40.0
            )
            delta_t = result.surface_temperature_c - environment.temperature_c
            candidates.append((geometry, delta_t))
        candidates.sort(key=lambda item: item[1])
        return candidates

    def best_candidate(
        self,
        heatsink_type: str,
        param_grid: Dict[str, Iterable[float]],
        target_power_w: float,
        environment: Environment,
    ) -> Tuple[GeometryDetails, float]:
        """Pick the candidate with the lowest surface overtemperature."""

        candidates = self.sweep_candidates(
            heatsink_type=heatsink_type,
            param_grid=param_grid,
            target_power_w=target_power_w,
            environment=environment,
        )
        if not candidates:
            raise ValueError("Нет подходящих комбинаций параметров")
        return candidates[0]
