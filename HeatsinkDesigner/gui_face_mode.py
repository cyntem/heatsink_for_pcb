"""Task panel logic for face/sketch driven mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .geometry_builder import BaseDimensions, GeometryDetails, build_geometry
from .heatsink_types import SUPPORTED_TYPES


@dataclass
class FaceSelection:
    """Represents a simplified face/sketch selection."""

    length_mm: float
    width_mm: float
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)

    def base_dimensions(self, base_thickness_mm: float) -> BaseDimensions:
        return BaseDimensions(
            length_mm=self.length_mm,
            width_mm=self.width_mm,
            base_thickness_mm=base_thickness_mm,
        )


class FaceSketchController:
    """Encapsulates validation and generation logic for mode 1."""

    def __init__(self) -> None:
        self.selection: Optional[FaceSelection] = None

    def validate_selection(self) -> None:
        if self.selection is None:
            raise ValueError("Не выбрана плоская грань или эскиз")
        if self.selection.length_mm <= 0 or self.selection.width_mm <= 0:
            raise ValueError("Размеры плоскости должны быть положительными")

    def prepare_geometry(
        self,
        heatsink_type: str,
        params: Dict[str, float],
        base_thickness_mm: float,
    ) -> GeometryDetails:
        self.validate_selection()
        if heatsink_type not in SUPPORTED_TYPES:
            raise ValueError("Неизвестный тип радиатора")
        base_dims = self.selection.base_dimensions(base_thickness_mm)
        return build_geometry(heatsink_type, (base_dims.length_mm, base_dims.width_mm, base_dims.base_thickness_mm), params)
