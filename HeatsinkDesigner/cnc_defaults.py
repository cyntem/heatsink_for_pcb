"""Default CNC-friendly parameters for heatsink generation."""

DEFAULT_TOOL_DIAM_MM = 3.0
MIN_FIN_THICKNESS_MM = 2.0
MIN_FIN_GAP_MM = 3.0

DEFAULT_CNC_PARAMS = {
    "straight_fins": {
        "fin_thickness_mm": 2.0,
        "fin_gap_mm": 3.0,
        "base_thickness_mm": 5.0,
        "fin_height_mm": 20.0,
    },
    "crosscut": {
        "groove_width_mm": 3.0,
        "pin_size_mm": 3.0,
        "pin_height_mm": 15.0,
        "base_thickness_mm": 5.0,
    },
    "pin_fin": {
        "pin_size_mm": 5.0,
        "pitch_mm": 8.0,
        "pin_height_mm": 20.0,
        "base_thickness_mm": 5.0,
    },
    "solid_plate": {
        "base_thickness_mm": 10.0,
    },
}
