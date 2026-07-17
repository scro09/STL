from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


TEMPLATES = ("simple_band", "pave_band", "solitaire")
CROSS_SECTIONS = ("round", "half_round", "flat")
STONE_SHAPES = ("round", "oval", "square", "none")
SETTING_TYPES = ("none", "prong", "basket", "bezel", "channel")
PATTERN_TYPES = ("none", "striations", "grooves", "dotted_ridges", "beaded_edges")
PATTERN_MODES = ("engraved", "raised")
PATTERN_PLACEMENTS = ("outer_center", "outer_edges", "full_outer_band")

TEMPLATE_ALIASES = {"band": "simple_band", "plain_band": "simple_band", "solitaire_ring": "solitaire"}
CROSS_SECTION_ALIASES = {
    "halfround": "half_round",
    "d_shape": "half_round",
    "d_shaped": "half_round",
    "comfort_fit": "half_round",
    "rounded": "half_round",
    "domed": "half_round",
    "dome": "half_round",
    "semicircular": "half_round",
    "semi_round": "half_round",
    "rectangular": "flat",
    "rectangle": "flat",
    "square": "flat",
    "circular": "round",
}
STONE_SHAPE_ALIASES = {"circular": "round", "rectangle": "square", "rectangular": "square"}
SETTING_TYPE_ALIASES = {"claw": "prong", "claws": "prong", "prongs": "prong"}
PATTERN_TYPE_ALIASES = {
    "beaded": "beaded_edges",
    "beads": "beaded_edges",
    "dotted": "dotted_ridges",
    "ridges": "dotted_ridges",
    "ribbed": "striations",
}
PATTERN_MODE_ALIASES = {"embossed": "raised", "carved": "engraved", "etched": "engraved"}
PATTERN_PLACEMENT_ALIASES = {
    "outer_circumference": "full_outer_band",
    "outer_band": "full_outer_band",
    "center": "outer_center",
    "edges": "outer_edges",
}

MIN_INNER_RADIUS_MM = 7.5
MIN_BAND_WIDTH_MM = 1.2
MIN_BAND_THICKNESS_MM = 1.2
MIN_PRONG_DIAMETER_MM = 0.8


PATTERN_LAYER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "type": {"type": "string", "enum": list(PATTERN_TYPES)},
        "mode": {"type": "string", "enum": list(PATTERN_MODES)},
        "count": {"type": "integer", "minimum": 1, "maximum": 160},
        "element_width_mm": {"type": "number", "minimum": 0.05, "maximum": 3.0},
        "element_height_mm": {"type": "number", "minimum": 0.02, "maximum": 4.0},
        "depth_mm": {"type": "number", "minimum": 0.01, "maximum": 2.0},
        "spacing_mm": {"type": "number", "minimum": 0.0, "maximum": 3.0},
        "start_angle_deg": {"type": "number", "minimum": -180.0, "maximum": 360.0},
        "end_angle_deg": {"type": "number", "minimum": -180.0, "maximum": 360.0},
        "axial_offset_ratio": {"type": "number", "minimum": -1.0, "maximum": 1.0},
    },
    "required": [
        "name",
        "type",
        "mode",
        "count",
        "element_width_mm",
        "element_height_mm",
        "depth_mm",
        "spacing_mm",
        "start_angle_deg",
        "end_angle_deg",
        "axial_offset_ratio",
    ],
}


PARAMETERS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "template": {"type": "string", "enum": list(TEMPLATES)},
        "band": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "inner_radius_mm": {"type": "number", "minimum": MIN_INNER_RADIUS_MM, "maximum": 15.0},
                "width_mm": {"type": "number", "minimum": MIN_BAND_WIDTH_MM, "maximum": 12.0},
                "thickness_mm": {
                    "type": "number",
                    "minimum": MIN_BAND_THICKNESS_MM,
                    "maximum": 6.0,
                },
                "cross_section": {"type": "string", "enum": list(CROSS_SECTIONS)},
            },
            "required": ["inner_radius_mm", "width_mm", "thickness_mm", "cross_section"],
        },
        "stone_reference": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "present": {"type": "boolean"},
                "shape": {"type": "string", "enum": list(STONE_SHAPES)},
                "size_mm": {"type": "number", "minimum": 0.0, "maximum": 18.0},
            },
            "required": ["present", "shape", "size_mm"],
        },
        "setting": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean"},
                "type": {"type": "string", "enum": list(SETTING_TYPES)},
                "prong_count": {"type": "integer", "minimum": 0, "maximum": 8},
                "seat_depth_mm": {"type": "number", "minimum": 0.0, "maximum": 3.0},
                "support_height_mm": {"type": "number", "minimum": 0.0, "maximum": 8.0},
            },
            "required": ["enabled", "type", "prong_count", "seat_depth_mm", "support_height_mm"],
        },
        "surface_pattern": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean"},
                "type": {"type": "string", "enum": list(PATTERN_TYPES)},
                "mode": {"type": "string", "enum": list(PATTERN_MODES)},
                "rows": {"type": "integer", "minimum": 0, "maximum": 8},
                "count_per_row": {"type": "integer", "minimum": 0, "maximum": 160},
                "element_width_mm": {"type": "number", "minimum": 0.05, "maximum": 3.0},
                "element_height_mm": {"type": "number", "minimum": 0.02, "maximum": 4.0},
                "depth_mm": {"type": "number", "minimum": 0.01, "maximum": 2.0},
                "spacing_mm": {"type": "number", "minimum": 0.0, "maximum": 3.0},
                "start_angle_deg": {"type": "number", "minimum": -180.0, "maximum": 360.0},
                "end_angle_deg": {"type": "number", "minimum": -180.0, "maximum": 360.0},
                "placement": {"type": "string", "enum": list(PATTERN_PLACEMENTS)},
                "layers": {
                    "type": "array",
                    "maxItems": 8,
                    "items": PATTERN_LAYER_JSON_SCHEMA,
                },
            },
            "required": [
                "enabled",
                "type",
                "mode",
                "rows",
                "count_per_row",
                "element_width_mm",
                "element_height_mm",
                "depth_mm",
                "spacing_mm",
                "start_angle_deg",
                "end_angle_deg",
                "placement",
                "layers",
            ],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["template", "band", "stone_reference", "setting", "surface_pattern", "confidence"],
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(section: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = section.get(name)
        if value is not None:
            return value
    return None


def _normalized_token(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _required_choice(value: Any, allowed: tuple[str, ...], field_name: str) -> str:
    normalized = _normalized_token(value)
    if normalized not in allowed:
        choices = ", ".join(allowed)
        raise ValueError(f"{field_name} must be one of: {choices}")
    return normalized


def _choice_or_default(
    value: Any,
    allowed: tuple[str, ...],
    fallback: str,
    field_name: str,
    aliases: Mapping[str, str] | None = None,
) -> str:
    if value is None or str(value).strip() == "":
        return fallback
    normalized = _normalized_token(value)
    if aliases:
        normalized = aliases.get(normalized, normalized)
    return normalized if normalized in allowed else fallback


def _number(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    return round(max(minimum, min(maximum, number)), 3)


def _integer(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = fallback
    return max(minimum, min(maximum, number))


def _boolean(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return fallback


def _require_fields(section_name: str, section: Mapping[str, Any], required: set[str]) -> None:
    missing = sorted(required.difference(section))
    if missing:
        raise ValueError(f"{section_name} is missing fields: {', '.join(missing)}")


def normalize_parameters(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError("Vision response must be a JSON object.")

    wrapped_ring = data.get("ring")
    if isinstance(wrapped_ring, Mapping):
        data = wrapped_ring

    required_fields = {"template", "band", "stone_reference", "setting", "surface_pattern", "confidence"}
    missing_fields = sorted(required_fields.difference(data))
    if missing_fields:
        raise ValueError(f"Vision response is missing fields: {', '.join(missing_fields)}")

    template = _choice_or_default(
        data.get("template"),
        TEMPLATES,
        "simple_band",
        "template",
        TEMPLATE_ALIASES,
    )
    band_data = _mapping(data.get("band"))
    stone_data = _mapping(data.get("stone_reference"))
    setting_data = _mapping(data.get("setting"))
    raw_surface_pattern = data.get("surface_pattern")
    pattern_data = _mapping(raw_surface_pattern)
    raw_pattern_layers = (
        raw_surface_pattern
        if isinstance(raw_surface_pattern, list)
        else _first(pattern_data, "layers", "segments", "patterns", "striation_layers")
    )

    inner_radius_value = _first(band_data, "inner_radius_mm", "inner_radius", "radius_mm", "radius")
    if inner_radius_value is None:
        diameter_value = _first(
            band_data,
            "inner_diameter_mm",
            "inner_diameter",
            "diameter_mm",
            "diameter",
        )
        try:
            inner_radius_value = float(diameter_value) / 2.0
        except (TypeError, ValueError):
            inner_radius_value = 9.0
    band_inner_radius = _number(inner_radius_value, 9.0, MIN_INNER_RADIUS_MM, 15.0)
    band_width = _number(_first(band_data, "width_mm", "width", "band_width_mm", "band_width"), 3.0, MIN_BAND_WIDTH_MM, 12.0)
    band_thickness = _number(
        _first(band_data, "thickness_mm", "thickness", "band_thickness_mm", "band_thickness"),
        1.8,
        MIN_BAND_THICKNESS_MM,
        6.0,
    )
    band_cross_section = _choice_or_default(
        _first(band_data, "cross_section", "profile", "band_profile"),
        CROSS_SECTIONS,
        "half_round",
        "band.cross_section",
        CROSS_SECTION_ALIASES,
    )

    stone_size = _number(_first(stone_data, "size_mm", "size", "diameter_mm", "diameter"), 0.0, 0.0, 18.0)
    stone_shape = _choice_or_default(
        _first(stone_data, "shape", "stone_shape"),
        STONE_SHAPES,
        "round" if stone_size > 0.0 else "none",
        "stone_reference.shape",
        STONE_SHAPE_ALIASES,
    )
    stone_present = _boolean(
        _first(stone_data, "present", "enabled", "has_stone"),
        bool(stone_data) and (stone_size > 0.0 or stone_shape != "none"),
    )
    setting_type = _choice_or_default(
        _first(setting_data, "type", "setting_type"),
        SETTING_TYPES,
        "none",
        "setting.type",
        SETTING_TYPE_ALIASES,
    )
    setting_enabled = _boolean(
        _first(setting_data, "enabled", "present"),
        stone_present or setting_type != "none",
    )

    if stone_present and stone_shape == "none":
        stone_shape = "round"
    if setting_enabled:
        if setting_type == "none":
            setting_type = "prong"
        if stone_shape == "none":
            stone_shape = "round"
        stone_size = max(1.5, stone_size)
    elif not stone_present:
        stone_shape = "none"
        stone_size = 0.0

    prong_count = _integer(_first(setting_data, "prong_count", "claw_count", "count"), 4, 0, 8)
    seat_depth = _number(_first(setting_data, "seat_depth_mm", "seat_depth", "depth_mm"), 0.8, 0.0, 3.0)
    support_height = _number(
        _first(setting_data, "support_height_mm", "support_height", "height_mm", "height"),
        2.0,
        0.0,
        8.0,
    )
    if setting_enabled:
        seat_depth = max(0.5, seat_depth)
        support_height = max(0.8, support_height)
        seat_depth = min(seat_depth, max(0.8, stone_size * 0.22))
        support_height = min(support_height, max(1.2, stone_size * 0.5))
        if setting_type in {"prong", "basket"}:
            prong_count = max(3, prong_count)
        else:
            prong_count = 0
    else:
        setting_type = "none"
        prong_count = 0
        seat_depth = 0.0
        support_height = 0.0

    pattern_type = _choice_or_default(
        _first(pattern_data, "type", "pattern_type"),
        PATTERN_TYPES,
        "none",
        "surface_pattern.type",
        PATTERN_TYPE_ALIASES,
    )
    pattern_enabled = _boolean(_first(pattern_data, "enabled", "present"), pattern_type != "none")
    pattern_mode = _choice_or_default(
        _first(pattern_data, "mode", "style"),
        PATTERN_MODES,
        "raised",
        "surface_pattern.mode",
        PATTERN_MODE_ALIASES,
    )
    pattern_placement = _choice_or_default(
        _first(pattern_data, "placement", "position"),
        PATTERN_PLACEMENTS,
        "outer_center",
        "surface_pattern.placement",
        PATTERN_PLACEMENT_ALIASES,
    )
    pattern_rows = _integer(_first(pattern_data, "rows", "row_count"), 1, 0, 8)
    pattern_count_value = _first(pattern_data, "count_per_row", "count", "elements_per_row")
    if pattern_count_value is None:
        try:
            angular_interval = abs(float(_first(pattern_data, "angular_interval", "angle_step_deg")))
            pattern_count_value = round(360.0 / angular_interval) if angular_interval > 0.0 else 1
        except (TypeError, ValueError):
            pattern_count_value = 1
    pattern_count = _integer(pattern_count_value, 1, 0, 160)
    if pattern_enabled and pattern_type != "none":
        pattern_rows = max(1, pattern_rows)
        pattern_count = max(1, pattern_count)
    else:
        pattern_enabled = False
        pattern_type = "none"
        pattern_rows = 0
        pattern_count = 0

    element_width = _number(_first(pattern_data, "element_width_mm", "element_width", "width_mm"), 0.3, 0.05, 3.0)
    element_height = _number(_first(pattern_data, "element_height_mm", "element_height", "height_mm"), 0.15, 0.02, 4.0)
    pattern_depth = _number(_first(pattern_data, "depth_mm", "depth"), 0.1, 0.01, 2.0)
    pattern_spacing = _number(_first(pattern_data, "spacing_mm", "spacing"), 0.2, 0.0, 3.0)
    pattern_start = _number(_first(pattern_data, "start_angle_deg", "start_angle"), 0.0, -180.0, 360.0)
    pattern_end = _number(_first(pattern_data, "end_angle_deg", "end_angle"), 360.0, -180.0, 360.0)
    if pattern_enabled:
        element_width = max(0.25, element_width)
        element_height = max(0.25, element_height)
        pattern_depth = max(0.2, pattern_depth)
        if pattern_type == "beaded_edges":
            pattern_rows = max(2, pattern_rows)
            element_width = max(0.4, element_width)
            element_height = max(0.4, element_height)
            pattern_depth = max(0.3, pattern_depth)
            if pattern_placement == "outer_center":
                pattern_placement = "outer_edges"
        if pattern_count <= 1:
            angular_span = abs(pattern_end - pattern_start)
            if angular_span < 1.0:
                angular_span = 360.0
            outer_radius = band_inner_radius + band_thickness
            arc_length = 2.0 * math.pi * outer_radius * min(360.0, angular_span) / 360.0
            pitch = max(0.3, element_width + pattern_spacing)
            pattern_count = max(2, min(160, int(round(arc_length / pitch))))

    def inferred_layer_count(
        requested_count: Any,
        start_angle: float,
        end_angle: float,
        width: float,
        spacing: float,
    ) -> int:
        count = _integer(requested_count, 1, 1, 160)
        if count > 1:
            return count
        angular_span = abs(end_angle - start_angle)
        if angular_span < 1.0:
            angular_span = 360.0
        outer_radius = band_inner_radius + band_thickness
        arc_length = 2.0 * math.pi * outer_radius * min(360.0, angular_span) / 360.0
        return max(2, min(160, int(round(arc_length / max(0.3, width + spacing)))))

    normalized_layers: list[dict[str, Any]] = []
    if isinstance(raw_pattern_layers, list):
        for index, raw_layer in enumerate(raw_pattern_layers[:8]):
            layer = _mapping(raw_layer)
            layer_type = _choice_or_default(
                _first(layer, "type", "pattern_type"),
                PATTERN_TYPES,
                pattern_type,
                f"surface_pattern.layers[{index}].type",
                PATTERN_TYPE_ALIASES,
            )
            if layer_type == "none":
                continue
            layer_mode = _choice_or_default(
                _first(layer, "mode", "style"),
                PATTERN_MODES,
                pattern_mode,
                f"surface_pattern.layers[{index}].mode",
                PATTERN_MODE_ALIASES,
            )
            layer_width = _number(
                _first(layer, "element_width_mm", "element_width", "width_mm"),
                element_width,
                0.25,
                3.0,
            )
            layer_height = _number(
                _first(layer, "element_height_mm", "element_height", "height_mm"),
                element_height,
                0.25,
                4.0,
            )
            layer_depth = _number(_first(layer, "depth_mm", "depth"), pattern_depth, 0.2, 2.0)
            layer_spacing = _number(
                _first(layer, "spacing_mm", "spacing"),
                pattern_spacing,
                0.0,
                3.0,
            )
            layer_start = _number(
                _first(layer, "start_angle_deg", "start_angle"),
                pattern_start,
                -180.0,
                360.0,
            )
            layer_end = _number(
                _first(layer, "end_angle_deg", "end_angle"),
                pattern_end,
                -180.0,
                360.0,
            )
            offset_value = _first(layer, "axial_offset_ratio", "offset_ratio", "row_offset")
            if isinstance(offset_value, str):
                offset_value = {
                    "left": -1.0,
                    "left_edge": -1.0,
                    "center": 0.0,
                    "right": 1.0,
                    "right_edge": 1.0,
                }.get(_normalized_token(offset_value), 0.0)
            layer_offset = _number(offset_value, 0.0, -1.0, 1.0)
            if layer_type == "beaded_edges":
                layer_width = max(0.4, layer_width)
                layer_height = max(0.4, layer_height)
                layer_depth = max(0.3, layer_depth)
            normalized_layers.append(
                {
                    "name": str(_first(layer, "name", "label") or f"layer_{index + 1}"),
                    "type": layer_type,
                    "mode": layer_mode,
                    "count": inferred_layer_count(
                        _first(layer, "count", "count_per_row", "elements"),
                        layer_start,
                        layer_end,
                        layer_width,
                        layer_spacing,
                    ),
                    "element_width_mm": layer_width,
                    "element_height_mm": layer_height,
                    "depth_mm": layer_depth,
                    "spacing_mm": layer_spacing,
                    "start_angle_deg": layer_start,
                    "end_angle_deg": layer_end,
                    "axial_offset_ratio": layer_offset,
                }
            )

    if pattern_enabled and not normalized_layers:
        if pattern_rows <= 1:
            offsets = [0.0]
        elif pattern_placement == "outer_center":
            edge = max(0.1, band_width / 2.0 - element_height / 2.0)
            step_ratio = min(1.0, (element_height + pattern_spacing) / edge)
            offsets = [(index - (pattern_rows - 1) / 2.0) * step_ratio for index in range(pattern_rows)]
        else:
            offsets = [-1.0 + 2.0 * index / (pattern_rows - 1) for index in range(pattern_rows)]
        for index, offset in enumerate(offsets[:8]):
            normalized_layers.append(
                {
                    "name": f"{pattern_type}_{index + 1}",
                    "type": pattern_type,
                    "mode": pattern_mode,
                    "count": pattern_count,
                    "element_width_mm": element_width,
                    "element_height_mm": element_height,
                    "depth_mm": pattern_depth,
                    "spacing_mm": pattern_spacing,
                    "start_angle_deg": pattern_start,
                    "end_angle_deg": pattern_end,
                    "axial_offset_ratio": round(max(-1.0, min(1.0, offset)), 3),
                }
            )

    if template == "pave_band" and setting_enabled and not normalized_layers:
        shoulder_arcs = ((25.0, 72.0, "right"), (108.0, 155.0, "left"))
        for start_angle, end_angle, side in shoulder_arcs:
            normalized_layers.append(
                {
                    "name": f"{side}_raised_tabs",
                    "type": "striations",
                    "mode": "raised",
                    "count": inferred_layer_count(1, start_angle, end_angle, 0.65, 0.3),
                    "element_width_mm": 0.65,
                    "element_height_mm": 0.7,
                    "depth_mm": 0.4,
                    "spacing_mm": 0.3,
                    "start_angle_deg": start_angle,
                    "end_angle_deg": end_angle,
                    "axial_offset_ratio": -0.82,
                }
            )
            normalized_layers.append(
                {
                    "name": f"{side}_seat_holes",
                    "type": "dotted_ridges",
                    "mode": "engraved",
                    "count": inferred_layer_count(1, start_angle + 4.0, end_angle - 4.0, 0.45, 0.35),
                    "element_width_mm": 0.45,
                    "element_height_mm": 0.45,
                    "depth_mm": 0.3,
                    "spacing_mm": 0.35,
                    "start_angle_deg": start_angle + 4.0,
                    "end_angle_deg": end_angle - 4.0,
                    "axial_offset_ratio": 0.72,
                }
            )
        pattern_enabled = True
        pattern_type = "striations"
        pattern_mode = "raised"
        pattern_rows = 2
        pattern_count = max(layer["count"] for layer in normalized_layers)
        element_width = 0.65
        element_height = 0.7
        pattern_depth = 0.4
        pattern_spacing = 0.3
        pattern_start = 25.0
        pattern_end = 155.0
        pattern_placement = "outer_edges"

    if normalized_layers:
        pattern_enabled = True

    return {
        "template": template,
        "band": {
            "inner_radius_mm": band_inner_radius,
            "width_mm": band_width,
            "thickness_mm": band_thickness,
            "cross_section": band_cross_section,
        },
        "stone_reference": {
            "present": stone_present,
            "shape": stone_shape,
            "size_mm": stone_size,
        },
        "setting": {
            "enabled": setting_enabled,
            "type": setting_type,
            "prong_count": prong_count,
            "seat_depth_mm": seat_depth,
            "support_height_mm": support_height,
        },
        "surface_pattern": {
            "enabled": pattern_enabled,
            "type": pattern_type,
            "mode": pattern_mode,
            "rows": pattern_rows,
            "count_per_row": pattern_count,
            "element_width_mm": element_width,
            "element_height_mm": element_height,
            "depth_mm": pattern_depth,
            "spacing_mm": pattern_spacing,
            "start_angle_deg": pattern_start,
            "end_angle_deg": pattern_end,
            "placement": pattern_placement,
            "layers": normalized_layers,
        },
        "confidence": _number(data.get("confidence"), 0.5, 0.0, 1.0),
    }
