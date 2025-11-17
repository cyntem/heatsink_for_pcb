#heatsink_types.py
"""Definitions for supported heatsink types and their parameter schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# ---- устойчивый импорт cnc_defaults ----------------------------------------
try:
    from HeatsinkDesigner import cnc_defaults
except ImportError:
    import cnc_defaults


@dataclass
class ParameterSpec:
    """Description of a single parameter expected by a heatsink type."""

    name: str
    unit: str
    description: str
    min_value: float = 0.0


@dataclass
class HeatsinkType:
    """Container describing geometry-specific parameters for a heatsink."""

    key: str
    label: str
    parameters: List[ParameterSpec] = field(default_factory=list)

    def default_parameters(self) -> Dict[str, float]:
        """Return a copy of CNC-friendly defaults for this heatsink type."""
        return dict(cnc_defaults.DEFAULT_CNC_PARAMS.get(self.key, {}))


SUPPORTED_TYPES: Dict[str, HeatsinkType] = {
    "solid_plate": HeatsinkType(
        key="solid_plate",
        label="Solid plate",
        parameters=[
            ParameterSpec(
                name="base_thickness_mm",
                unit="mm",
                description="Толщина плиты",
                min_value=0.1,
            )
        ],
    ),
    "straight_fins": HeatsinkType(
        key="straight_fins",
        label="Straight milled fins",
        parameters=[
            ParameterSpec(
                name="fin_thickness_mm",
                unit="mm",
                description="Толщина ребра",
                min_value=cnc_defaults.MIN_FIN_THICKNESS_MM,
            ),
            ParameterSpec(
                name="fin_gap_mm",
                unit="mm",
                description="Зазор между ребрами",
                min_value=cnc_defaults.MIN_FIN_GAP_MM,
            ),
            ParameterSpec(
                name="fin_height_mm",
                unit="mm",
                description="Высота ребра",
                min_value=1.0,
            ),
            ParameterSpec(
                name="base_thickness_mm",
                unit="mm",
                description="Толщина основания",
                min_value=1.0,
            ),
        ],
    ),
    "crosscut": HeatsinkType(
        key="crosscut",
        label="Crosscut (grid)",
        parameters=[
            ParameterSpec(
                name="groove_width_mm",
                unit="mm",
                description="Ширина канавки",
                min_value=cnc_defaults.MIN_FIN_GAP_MM,
            ),
            ParameterSpec(
                name="pin_size_mm",
                unit="mm",
                description="Сторона квадратного пина",
                min_value=cnc_defaults.MIN_FIN_THICKNESS_MM,
            ),
            ParameterSpec(
                name="pin_height_mm",
                unit="mm",
                description="Высота пинов",
                min_value=1.0,
            ),
            ParameterSpec(
                name="base_thickness_mm",
                unit="mm",
                description="Толщина основания",
                min_value=1.0,
            ),
        ],
    ),
    "pin_fin": HeatsinkType(
        key="pin_fin",
        label="Pin-fin",
        parameters=[
            ParameterSpec(
                name="pin_size_mm",
                unit="mm",
                description="Сечение квадратного пина",
                min_value=cnc_defaults.MIN_FIN_THICKNESS_MM,
            ),
            ParameterSpec(
                name="pitch_mm",
                unit="mm",
                description="Шаг между пинами",
                min_value=cnc_defaults.MIN_FIN_GAP_MM,
            ),
            ParameterSpec(
                name="pin_height_mm",
                unit="mm",
                description="Высота пинов",
                min_value=1.0,
            ),
            ParameterSpec(
                name="base_thickness_mm",
                unit="mm",
                description="Толщина основания",
                min_value=1.0,
            ),
        ],
    ),
}


def list_type_labels() -> List[str]:
    """Return human-readable labels for UI drop-downs."""
    return [heatsink_type.label for heatsink_type in SUPPORTED_TYPES.values()]
