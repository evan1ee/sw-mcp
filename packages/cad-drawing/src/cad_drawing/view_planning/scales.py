"""ISO 5455 preferred scales and scale selection logic (spec 11.2, 11.4)."""

from typing import Final

EXPECTED_SCALE_PARTS: Final[int] = 2

# ISO 5455 preferred scales ordered from largest to smallest
ISO_SCALES: Final[tuple[tuple[int, int], ...]] = (
    (50, 1),
    (20, 1),
    (10, 1),
    (5, 1),
    (2, 1),
    (1, 1),
    (1, 2),
    (1, 5),
    (1, 10),
    (1, 20),
    (1, 50),
    (1, 100),
    (1, 200),
    (1, 500),
)


def parse_scale_string(scale_str: str) -> tuple[int, int]:
    """Parse an ISO scale string like '1:2' or '5:1' into (numerator, denominator)."""
    parts = scale_str.strip().split(":")
    if len(parts) != EXPECTED_SCALE_PARTS:
        msg = f"Invalid scale string '{scale_str}' (expected 'num:den')"
        raise ValueError(msg)
    num = int(parts[0])
    den = int(parts[1])
    if num <= 0 or den <= 0:
        msg = f"Scale components must be positive integers, got {num}:{den}"
        raise ValueError(msg)
    return num, den


def format_scale_string(numerator: int, denominator: int) -> str:
    """Format scale numerator and denominator as 'num:den'."""
    return f"{numerator}:{denominator}"


def select_iso_scale(  # noqa: PLR0913, PLR0917
    part_width_mm: float,
    part_height_mm: float,
    part_depth_mm: float,
    usable_width_mm: float,
    usable_height_mm: float,
    spacing_mm: float = 25.0,
) -> tuple[int, int]:
    """Select the largest ISO 5455 preferred scale that fits within usable sheet dimensions.

    Evaluates standard orthographic arrangement:
    Total width: (Front view width + Right view width) * scale + spacing
    Total height: (Front view height + Top view height) * scale + spacing
    """
    for num, den in ISO_SCALES:
        scale_val = num / den
        req_width = (part_width_mm + part_depth_mm) * scale_val + spacing_mm
        req_height = (part_height_mm + part_depth_mm) * scale_val + spacing_mm

        if req_width <= usable_width_mm and req_height <= usable_height_mm:
            return num, den

    # Fallback to the smallest standard scale
    return ISO_SCALES[-1]
