from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from pathlib import Path
from typing import Any

import bmesh
import bpy
from mathutils import Matrix, Vector

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ring_schema import MIN_PRONG_DIAMETER_MM, normalize_parameters


warnings.filterwarnings("ignore", category=DeprecationWarning)


METAL_MATERIAL: bpy.types.Material | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a parametric ring from normalized JSON")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-stl", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--camera-npz")
    parser.add_argument("--view-ids-json", default="[]")
    parser.add_argument("--resolution", type=int, default=512)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(data_collection):
            if block.users == 0:
                data_collection.remove(block)


def create_material(
    name: str,
    color: tuple[float, float, float, float],
    metallic: float,
    roughness: float,
    transmission: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF") if material.node_tree else None
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        transmission_input = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
        if transmission_input is not None:
            transmission_input.default_value = transmission
        ior_input = bsdf.inputs.get("IOR")
        if ior_input is not None:
            ior_input.default_value = 1.45
    return material


def _attach_material(obj: bpy.types.Object, material: bpy.types.Material | None) -> None:
    if material is not None:
        obj.data.materials.append(material)


def shade_smooth(obj: bpy.types.Object) -> None:
    for polygon in obj.data.polygons:
        polygon.use_smooth = True


def _create_annular_band(
    inner_radius: float,
    thickness: float,
    width: float,
    cross_section: str,
) -> bpy.types.Object:
    segments = 192
    outer_radius = inner_radius + thickness
    half_width = width / 2.0
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        vertices.extend(
            [
                (inner_radius * cos_angle, inner_radius * sin_angle, -half_width),
                (inner_radius * cos_angle, inner_radius * sin_angle, half_width),
                (outer_radius * cos_angle, outer_radius * sin_angle, -half_width),
                (outer_radius * cos_angle, outer_radius * sin_angle, half_width),
            ]
        )

    for index in range(segments):
        current = index * 4
        following = ((index + 1) % segments) * 4
        faces.extend(
            [
                (current, current + 1, following + 1, following),
                (current + 2, following + 2, following + 3, current + 3),
                (current + 1, current + 3, following + 3, following + 1),
                (current, following, following + 2, current + 2),
            ]
        )

    mesh = bpy.data.meshes.new("BandMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    ring = bpy.data.objects.new("Generated_Ring_Band", mesh)
    bpy.context.collection.objects.link(ring)

    bevel_width = min(width, thickness) * (0.32 if cross_section == "half_round" else 0.06)
    if bevel_width > 0.01:
        bevel = ring.modifiers.new("Band_Profile", "BEVEL")
        bevel.width = bevel_width
        bevel.segments = 4 if cross_section == "half_round" else 2
        bevel.limit_method = "ANGLE"
        bpy.context.view_layer.objects.active = ring
        ring.select_set(True)
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        ring.select_set(False)
    shade_smooth(ring)
    return ring


def create_simple_band(params: dict[str, Any]) -> bpy.types.Object:
    band = params["band"]
    inner_radius = float(band["inner_radius_mm"])
    thickness = float(band["thickness_mm"])
    width = float(band["width_mm"])
    cross_section = str(band["cross_section"])

    if cross_section == "round":
        bpy.ops.mesh.primitive_torus_add(
            align="WORLD",
            major_segments=192,
            minor_segments=32,
            location=(0.0, 0.0, 0.0),
            major_radius=inner_radius + thickness / 2.0,
            minor_radius=thickness / 2.0,
        )
        ring = bpy.context.object
        ring.name = "Generated_Ring_Band"
        ring.scale.z = width / max(thickness, 0.001)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        shade_smooth(ring)
    else:
        ring = _create_annular_band(inner_radius, thickness, width, cross_section)

    _attach_material(ring, METAL_MATERIAL)
    return ring


def _pattern_row_positions(
    rows: int,
    band_width: float,
    element_height: float,
    spacing: float,
    placement: str,
) -> list[float]:
    if rows <= 1:
        return [0.0]
    edge = max(0.0, band_width / 2.0 - element_height / 2.0)
    if placement == "outer_center":
        requested_step = element_height + spacing
        maximum_step = (edge * 2.0) / max(1, rows - 1)
        step = min(requested_step, maximum_step)
        return [(index - (rows - 1) / 2.0) * step for index in range(rows)]
    if placement == "outer_edges" and rows > 2:
        positions: list[float] = []
        edge_step = min(element_height + spacing, edge / max(1, math.ceil(rows / 2)))
        for index in range(math.ceil(rows / 2)):
            positions.append(-edge + index * edge_step)
        for index in range(rows // 2):
            positions.append(edge - index * edge_step)
        return sorted(positions[:rows])
    return [-edge + 2.0 * edge * index / (rows - 1) for index in range(rows)]


def _create_pattern_element(
    pattern_type: str,
    name: str,
    angle: float,
    radius: float,
    z_value: float,
    tangent_width: float,
    axial_height: float,
    radial_depth: float,
) -> bpy.types.Object:
    location = (radius * math.cos(angle), radius * math.sin(angle), z_value)
    if pattern_type in {"dotted_ridges", "beaded_edges"}:
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=12,
            ring_count=6,
            radius=1.0,
            location=location,
        )
        element = bpy.context.object
        element.scale = (tangent_width / 2.0, radial_depth / 2.0, axial_height / 2.0)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
        element = bpy.context.object
        element.dimensions = (tangent_width, radial_depth, axial_height)
    element.name = name
    element.rotation_euler[2] = angle + math.pi / 2.0
    bpy.context.view_layer.objects.active = element
    element.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    element.select_set(False)
    return element


def _join_mesh_objects(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    if not objects:
        raise ValueError("No mesh objects were provided for joining.")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.object
    joined.name = name
    return joined


def create_surface_pattern(
    params: dict[str, Any],
    band_object: bpy.types.Object,
) -> list[bpy.types.Object]:
    pattern = params["surface_pattern"]
    layers = pattern.get("layers")
    if isinstance(layers, list) and layers:
        generated: list[bpy.types.Object] = []
        for layer in layers:
            if not isinstance(layer, dict) or str(layer.get("type", "none")) == "none":
                continue
            layer_pattern = {
                **pattern,
                "enabled": True,
                "type": layer["type"],
                "mode": layer["mode"],
                "rows": 1,
                "count_per_row": layer["count"],
                "element_width_mm": layer["element_width_mm"],
                "element_height_mm": layer["element_height_mm"],
                "depth_mm": layer["depth_mm"],
                "spacing_mm": layer["spacing_mm"],
                "start_angle_deg": layer["start_angle_deg"],
                "end_angle_deg": layer["end_angle_deg"],
                "placement": "outer_center",
                "axial_offset_ratio": layer["axial_offset_ratio"],
                "layer_name": layer["name"],
                "layers": [],
            }
            layer_params = {**params, "surface_pattern": layer_pattern}
            generated.extend(create_surface_pattern(layer_params, band_object))
        return generated
    if not bool(pattern["enabled"]) or str(pattern["type"]) == "none":
        return []

    band = params["band"]
    pattern_type = str(pattern["type"])
    mode = str(pattern["mode"])
    rows = max(1, int(pattern["rows"]))
    count = max(1, int(pattern["count_per_row"]))
    element_width = float(pattern["element_width_mm"])
    element_height = float(pattern["element_height_mm"])
    depth = float(pattern["depth_mm"])
    spacing = float(pattern["spacing_mm"])
    band_width = float(band["width_mm"])
    outer_radius = float(band["inner_radius_mm"]) + float(band["thickness_mm"])
    if "axial_offset_ratio" in pattern:
        edge = max(0.0, band_width / 2.0 - element_height / 2.0)
        row_positions = [edge * max(-1.0, min(1.0, float(pattern["axial_offset_ratio"])))]
    else:
        row_positions = _pattern_row_positions(
            rows,
            band_width,
            element_height,
            spacing,
            str(pattern["placement"]),
        )
    angles = _angle_values(
        float(pattern["start_angle_deg"]),
        float(pattern["end_angle_deg"]),
        count,
    )
    radial_depth = max(0.06, depth * (2.0 if mode == "engraved" else 1.4))
    radial_center = outer_radius if mode == "engraved" else outer_radius + depth * 0.2
    elements: list[bpy.types.Object] = []
    layer_name = str(pattern.get("layer_name", pattern_type))

    for row_index, z_value in enumerate(row_positions):
        for element_index, angle_degrees in enumerate(angles):
            element = _create_pattern_element(
                pattern_type,
                f"Surface_{layer_name}_{row_index + 1}_{element_index + 1}",
                math.radians(angle_degrees),
                radial_center,
                z_value,
                element_width,
                element_height,
                radial_depth,
            )
            elements.append(element)

    if mode == "raised":
        for element in elements:
            _attach_material(element, METAL_MATERIAL)
            shade_smooth(element)
        return elements

    cutters = _join_mesh_objects(elements, "Surface_Pattern_Cutters")
    boolean = band_object.modifiers.new("Surface_Pattern_Engraving", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    boolean.object = cutters
    bpy.ops.object.select_all(action="DESELECT")
    band_object.select_set(True)
    bpy.context.view_layer.objects.active = band_object
    try:
        bpy.ops.object.modifier_apply(modifier=boolean.name)
    except RuntimeError as exc:
        raise RuntimeError("Could not apply engraved surface pattern.") from exc
    finally:
        if cutters.name in bpy.data.objects:
            bpy.data.objects.remove(cutters, do_unlink=True)
    shade_smooth(band_object)
    return []


def _create_cylinder_between(
    start: Vector,
    end: Vector,
    radius: float,
    name: str,
) -> bpy.types.Object:
    direction = end - start
    length = max(0.05, direction.length)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=radius,
        depth=length,
        location=(start + end) / 2.0,
    )
    cylinder = bpy.context.object
    cylinder.name = name
    cylinder.rotation_mode = "QUATERNION"
    cylinder.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(direction.normalized())
    return cylinder


def _angle_values(start_angle: float, end_angle: float, count: int) -> list[float]:
    if count <= 1:
        return [(start_angle + end_angle) / 2.0]
    span = end_angle - start_angle
    divisor = count if abs(span) >= 359.0 else count - 1
    return [start_angle + span * index / divisor for index in range(count)]


def _setting_axes() -> tuple[Vector, Vector, Vector]:
    radial_axis = Vector((0.0, 1.0, 0.0))
    tangent_axis = Vector((-1.0, 0.0, 0.0))
    axial_axis = Vector((0.0, 0.0, 1.0))
    return radial_axis, tangent_axis, axial_axis


def _outline_coordinates(shape: str, radius: float, angle: float) -> tuple[float, float]:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    if shape == "square":
        scale = 1.0 / max(abs(cosine), abs(sine), 0.001)
        return radius * cosine * scale, radius * sine * scale
    axial_scale = 0.76 if shape == "oval" else 1.0
    return radius * cosine, radius * axial_scale * sine


def _create_hollow_setting_ring(
    name: str,
    shape: str,
    inner_radius: float,
    outer_radius: float,
    center_radius: float,
    radial_depth: float,
) -> bpy.types.Object:
    radial_axis, tangent_axis, axial_axis = _setting_axes()
    segments = 64
    vertices: list[tuple[float, float, float]] = []
    loops = (
        (outer_radius, center_radius - radial_depth / 2.0),
        (outer_radius, center_radius + radial_depth / 2.0),
        (inner_radius, center_radius - radial_depth / 2.0),
        (inner_radius, center_radius + radial_depth / 2.0),
    )
    for radius, radial_value in loops:
        for index in range(segments):
            angle = 2.0 * math.pi * index / segments
            tangent_value, axial_value = _outline_coordinates(shape, radius, angle)
            point = radial_axis * radial_value + tangent_axis * tangent_value + axial_axis * axial_value
            vertices.append(tuple(point))

    faces: list[tuple[int, int, int, int]] = []
    for index in range(segments):
        following = (index + 1) % segments
        outer_low = index
        outer_high = segments + index
        inner_low = 2 * segments + index
        inner_high = 3 * segments + index
        faces.extend(
            [
                (outer_low, following, segments + following, outer_high),
                (inner_low, inner_high, 3 * segments + following, 2 * segments + following),
                (outer_low, inner_low, 2 * segments + following, following),
                (outer_high, segments + following, 3 * segments + following, inner_high),
            ]
        )

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    ring = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ring)
    _attach_material(ring, METAL_MATERIAL)
    shade_smooth(ring)
    return ring


def _setting_measurements(params: dict[str, Any]) -> dict[str, float | str]:
    band = params["band"]
    reference = params["stone_reference"]
    setting = params["setting"]
    size = max(1.5, float(reference["size_mm"]))
    seat_depth = max(0.5, float(setting["seat_depth_mm"]))
    support_height = max(0.8, float(setting["support_height_mm"]))
    outer_band_radius = float(band["inner_radius_mm"]) + float(band["thickness_mm"])
    seat_width = max(0.5, min(1.0, size * 0.1))
    return {
        "shape": str(reference["shape"]),
        "size": size,
        "seat_depth": seat_depth,
        "support_height": support_height,
        "outer_band_radius": outer_band_radius,
        "seat_radius": outer_band_radius + support_height,
        "seat_inner": max(0.45, size / 2.0 - seat_width),
        "seat_outer": size / 2.0 + seat_width * 0.55,
    }


def create_stone_seat(params: dict[str, Any]) -> list[bpy.types.Object]:
    if not bool(params["setting"]["enabled"]):
        return []
    dimensions = _setting_measurements(params)
    seat = _create_hollow_setting_ring(
        "Setting_Seat",
        str(dimensions["shape"]),
        float(dimensions["seat_inner"]),
        float(dimensions["seat_outer"]),
        float(dimensions["seat_radius"]),
        float(dimensions["seat_depth"]),
    )
    return [seat]


def create_setting_supports(params: dict[str, Any]) -> list[bpy.types.Object]:
    dimensions = _setting_measurements(params)
    band = params["band"]
    radial_axis, tangent_axis, _ = _setting_axes()
    thickness = float(band["thickness_mm"])
    outer_band_radius = float(dimensions["outer_band_radius"])
    seat_radius = float(dimensions["seat_radius"])
    seat_outer = float(dimensions["seat_outer"])
    base_tangent_offset = min(seat_outer * 0.72, outer_band_radius * 0.28)
    base_radius = math.sqrt(max(0.1, (outer_band_radius - thickness * 0.12) ** 2 - base_tangent_offset**2))
    support_radius = max(0.4, min(0.7, thickness * 0.32))
    supports: list[bpy.types.Object] = []
    for index, sign in enumerate((-1.0, 1.0), start=1):
        base = radial_axis * base_radius + tangent_axis * (sign * base_tangent_offset)
        top = radial_axis * (seat_radius - float(dimensions["seat_depth"]) * 0.2) + tangent_axis * (
            sign * seat_outer * 0.68
        )
        support = _create_cylinder_between(base, top, support_radius, f"Setting_Shoulder_{index}")
        _attach_material(support, METAL_MATERIAL)
        shade_smooth(support)
        supports.append(support)
    return supports


def create_prongs(params: dict[str, Any]) -> list[bpy.types.Object]:
    setting = params["setting"]
    if not bool(setting["enabled"]) or str(setting["type"]) not in {"prong", "basket"}:
        return []
    dimensions = _setting_measurements(params)
    radial_axis, tangent_axis, axial_axis = _setting_axes()
    count = max(3, min(8, int(setting["prong_count"])))
    size = float(dimensions["size"])
    seat_radius = float(dimensions["seat_radius"])
    seat_outer = float(dimensions["seat_outer"])
    seat_depth = float(dimensions["seat_depth"])
    prong_radius = max(MIN_PRONG_DIAMETER_MM / 2.0, min(0.65, size * 0.075))
    base_offset = max(0.2, size * 0.3)
    top_offset = size / 2.0 + prong_radius * 0.12
    top_radius = seat_radius + max(0.9, size * 0.34)
    phase = math.pi / 4.0 if str(dimensions["shape"]) == "square" and count == 4 else 0.0
    prongs: list[bpy.types.Object] = []
    for index in range(count):
        angle = phase + 2.0 * math.pi * index / count
        lateral_base = tangent_axis * (base_offset * math.cos(angle)) + axial_axis * (
            base_offset * math.sin(angle)
        )
        lateral_top = tangent_axis * (top_offset * math.cos(angle)) + axial_axis * (
            top_offset * math.sin(angle)
        )
        base = radial_axis * (seat_radius - seat_depth * 0.15) + lateral_base
        top = radial_axis * top_radius + lateral_top
        prong = _create_cylinder_between(base, top, prong_radius, f"Setting_Prong_{index + 1}")
        _attach_material(prong, METAL_MATERIAL)
        shade_smooth(prong)
        prongs.append(prong)
    return prongs


def create_basket(params: dict[str, Any]) -> list[bpy.types.Object]:
    if str(params["setting"]["type"]) != "basket":
        return []
    dimensions = _setting_measurements(params)
    radial_axis, tangent_axis, axial_axis = _setting_axes()
    seat_radius = float(dimensions["seat_radius"])
    seat_outer = float(dimensions["seat_outer"])
    lower_radius = float(dimensions["outer_band_radius"]) + float(dimensions["support_height"]) * 0.48
    lower_outer = max(0.8, seat_outer * 0.72)
    lower_inner = max(0.35, lower_outer - 0.55)
    basket: list[bpy.types.Object] = [
        _create_hollow_setting_ring(
            "Setting_Basket_Lower_Rail",
            str(dimensions["shape"]),
            lower_inner,
            lower_outer,
            lower_radius,
            0.65,
        )
    ]
    strut_radius = 0.4
    for index in range(4):
        angle = math.pi / 4.0 + math.pi * index / 2.0
        lower = radial_axis * lower_radius + tangent_axis * (lower_outer * math.cos(angle)) + axial_axis * (
            lower_outer * math.sin(angle)
        )
        upper = radial_axis * seat_radius + tangent_axis * (seat_outer * 0.9 * math.cos(angle)) + axial_axis * (
            seat_outer * 0.9 * math.sin(angle)
        )
        strut = _create_cylinder_between(lower, upper, strut_radius, f"Setting_Basket_Strut_{index + 1}")
        _attach_material(strut, METAL_MATERIAL)
        shade_smooth(strut)
        basket.append(strut)
    return basket


def create_bezel(params: dict[str, Any]) -> list[bpy.types.Object]:
    if str(params["setting"]["type"]) != "bezel":
        return []
    dimensions = _setting_measurements(params)
    size = float(dimensions["size"])
    wall_thickness = max(0.55, min(0.9, size * 0.1))
    wall_height = max(1.0, size * 0.28)
    inner_radius = size / 2.0 + 0.1
    bezel = _create_hollow_setting_ring(
        "Setting_Bezel",
        str(dimensions["shape"]),
        inner_radius,
        inner_radius + wall_thickness,
        float(dimensions["seat_radius"]) + wall_height / 2.0 - 0.15,
        wall_height,
    )
    return [bezel]


def create_side_channels(params: dict[str, Any]) -> list[bpy.types.Object]:
    if str(params["setting"]["type"]) != "channel":
        return []
    dimensions = _setting_measurements(params)
    radial_axis, tangent_axis, axial_axis = _setting_axes()
    seat_radius = float(dimensions["seat_radius"])
    seat_outer = float(dimensions["seat_outer"])
    outer_band_radius = float(dimensions["outer_band_radius"])
    rail_radius = 0.45
    rails: list[bpy.types.Object] = []
    for index, sign in enumerate((-1.0, 1.0), start=1):
        start = radial_axis * (outer_band_radius - 0.1) + axial_axis * (sign * seat_outer * 0.72)
        end = radial_axis * (seat_radius + 0.35) + axial_axis * (sign * seat_outer * 0.72)
        rail = _create_cylinder_between(start, end, rail_radius, f"Setting_Channel_Rail_{index}")
        _attach_material(rail, METAL_MATERIAL)
        shade_smooth(rail)
        rails.append(rail)
    return rails


def create_metal_setting(params: dict[str, Any]) -> list[bpy.types.Object]:
    if not bool(params["setting"]["enabled"]):
        return []
    objects = [*create_stone_seat(params), *create_setting_supports(params)]
    setting_type = str(params["setting"]["type"])
    if setting_type == "prong":
        objects.extend(create_prongs(params))
    elif setting_type == "basket":
        objects.extend(create_basket(params))
        objects.extend(create_prongs(params))
    elif setting_type == "bezel":
        objects.extend(create_bezel(params))
    elif setting_type == "channel":
        objects.extend(create_side_channels(params))
    return objects


def create_ring(params: dict[str, Any]) -> list[bpy.types.Object]:
    band = create_simple_band(params)
    objects: list[bpy.types.Object] = [band]
    objects.extend(create_surface_pattern(params, band))
    objects.extend(create_metal_setting(params))
    return objects


def orient_ring_for_dataset(objects: list[bpy.types.Object]) -> None:
    dataset_rotation = Matrix.Rotation(math.radians(90.0), 4, "X")
    for obj in objects:
        obj.matrix_world = dataset_rotation @ obj.matrix_world


def _object_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, float]:
    corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    if not corners:
        return Vector((0.0, 0.0, 0.0)), 10.0
    minimum = Vector((min(point.x for point in corners), min(point.y for point in corners), min(point.z for point in corners)))
    maximum = Vector((max(point.x for point in corners), max(point.y for point in corners), max(point.z for point in corners)))
    center = (minimum + maximum) / 2.0
    radius = max(1.0, (maximum - minimum).length / 2.0)
    return center, radius


def _look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _add_area_light(name: str, location: Vector, target: Vector, energy: float, size: float) -> None:
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = size
    _look_at(light, target)


def setup_camera_and_lights(center: Vector, radius: float) -> bpy.types.Object:
    world = bpy.context.scene.world or bpy.data.worlds.new("Preview_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background") if world.node_tree else None
    if background is not None:
        background.inputs["Color"].default_value = (0.58, 0.61, 0.66, 1.0)
        background.inputs["Strength"].default_value = 0.8

    light_distance = radius * 2.6
    _add_area_light(
        "Key_Light",
        center + Vector((light_distance, -light_distance, light_distance * 1.25)),
        center,
        1100.0,
        radius * 1.4,
    )
    _add_area_light(
        "Fill_Light",
        center + Vector((-light_distance, -light_distance * 0.5, light_distance * 0.55)),
        center,
        650.0,
        radius * 1.8,
    )
    _add_area_light(
        "Rim_Light",
        center + Vector((0.0, light_distance, light_distance * 1.5)),
        center,
        900.0,
        radius * 1.2,
    )

    bpy.ops.object.camera_add(location=center + Vector((0.0, -radius * 3.2, radius * 1.1)))
    camera = bpy.context.object
    camera.name = "Preview_Camera"
    camera.data.lens = 52.0
    camera.data.sensor_width = 36.0
    camera.data.clip_start = 0.05
    camera.data.clip_end = radius * 20.0
    _look_at(camera, center)
    bpy.context.scene.camera = camera
    return camera


def _camera_directions_from_npz(camera_path: Path, view_ids: list[str]) -> list[Vector] | None:
    try:
        import numpy as np

        with np.load(camera_path, allow_pickle=False) as archive:
            if "cam_poses" not in archive:
                return None
            poses = archive["cam_poses"]
            if poses.ndim != 3 or poses.shape[1:] != (3, 4):
                return None
            directions: list[Vector] = []
            for view_id in view_ids:
                pose_index = int(view_id)
                if pose_index < 0 or pose_index >= poses.shape[0]:
                    return None
                pose = poses[pose_index]
                location = Vector(tuple(float(value) for value in pose[:, 3]))
                local_z = Vector(tuple(float(value) for value in pose[:, 2]))
                if location.length < 0.001 or local_z.length < 0.001:
                    return None
                if location.normalized().dot(local_z.normalized()) < 0.5:
                    return None
                directions.append(location.normalized())
            return directions
    except (ImportError, OSError, ValueError, TypeError, KeyError):
        return None


def _fallback_camera_directions(count: int) -> list[Vector]:
    count = max(1, count)
    directions: list[Vector] = []
    for index in range(count):
        angle = 2.0 * math.pi * index / count
        directions.append(Vector((math.cos(angle), math.sin(angle), 0.5)).normalized())
    return directions


def _configure_render(resolution: int) -> None:
    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass


def render_preview(
    objects: list[bpy.types.Object],
    preview_path: Path,
    view_ids: list[str],
    camera_path: Path | None,
    resolution: int,
) -> str:
    center, radius = _object_bounds(objects)
    camera = setup_camera_and_lights(center, radius)
    _configure_render(resolution)

    effective_view_ids = [view_ids[0] if view_ids else "preview"]

    directions = None
    camera_source = "fallback_uniform_5"
    if camera_path is not None and camera_path.exists():
        directions = _camera_directions_from_npz(camera_path, effective_view_ids)
        if directions is not None:
            camera_source = "cameras.npz:cam_poses"
    if directions is None:
        directions = _fallback_camera_directions(1)

    distance = radius * 3.25
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    camera.location = center + directions[0] * distance
    _look_at(camera, center)
    bpy.context.scene.render.filepath = str(preview_path)
    bpy.ops.render.render(write_still=True)
    return camera_source


def _component_vertex_sets(obj: bpy.types.Object) -> list[set[int]]:
    adjacency: list[list[int]] = [[] for _ in obj.data.vertices]
    for edge in obj.data.edges:
        first, second = edge.vertices
        adjacency[first].append(second)
        adjacency[second].append(first)
    unvisited = set(range(len(adjacency)))
    components: list[set[int]] = []
    while unvisited:
        start = unvisited.pop()
        component = {start}
        stack = [start]
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def count_mesh_components(obj: bpy.types.Object) -> int:
    return len(_component_vertex_sets(obj)) if len(obj.data.vertices) else 0


def count_non_manifold_edges(obj: bpy.types.Object) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    count = sum(1 for edge in bm.edges if not edge.is_manifold)
    bm.free()
    return count


def validate_metal_object_names(objects: list[bpy.types.Object]) -> None:
    forbidden_names = {"stone", "gem", "pave_stone"}
    invalid = [
        obj.name
        for obj in objects
        if any(forbidden in obj.name.lower() for forbidden in forbidden_names)
    ]
    if invalid:
        raise RuntimeError(f"Non-metal objects are forbidden: {', '.join(invalid)}")


def validate_printable_mesh(obj: bpy.types.Object) -> tuple[int, int]:
    component_count = count_mesh_components(obj)
    non_manifold_edges = count_non_manifold_edges(obj)
    if component_count != 1:
        raise RuntimeError(f"Printable mesh must contain one connected body, found {component_count}.")
    if non_manifold_edges:
        raise RuntimeError(f"Printable mesh is not manifold: {non_manifold_edges} invalid edges.")
    if not obj.data.polygons:
        raise RuntimeError("Printable mesh contains no faces.")
    return component_count, non_manifold_edges


def _voxel_remesh(obj: bpy.types.Object, voxel_size: float) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        obj.data.remesh_voxel_size = voxel_size
        obj.data.remesh_voxel_adaptivity = 0.0
        bpy.ops.object.voxel_remesh()
    except (AttributeError, RuntimeError):
        modifier = obj.modifiers.new("Voxel_Union", "REMESH")
        modifier.mode = "VOXEL"
        modifier.voxel_size = voxel_size
        modifier.use_smooth_shade = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def _clean_mesh(obj: bpy.types.Object, merge_distance: float) -> None:
    mesh = obj.data
    mesh.validate(clean_customdata=True)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if bm.verts:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_distance)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _keep_largest_component(obj: bpy.types.Object) -> None:
    components = _component_vertex_sets(obj)
    if len(components) <= 1:
        return
    largest = max(components, key=len)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    remove = [vertex for vertex in bm.verts if vertex.index not in largest]
    if remove:
        bmesh.ops.delete(bm, geom=remove, context="VERTS")
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def create_export_mesh(objects: list[bpy.types.Object]) -> tuple[bpy.types.Object, float, int, int]:
    if not objects:
        raise RuntimeError("No metal geometry was generated.")
    validate_metal_object_names(objects)
    duplicates: list[bpy.types.Object] = []
    for source in objects:
        duplicate = source.copy()
        duplicate.data = source.data.copy()
        duplicate.animation_data_clear()
        bpy.context.collection.objects.link(duplicate)
        duplicate.hide_render = True
        duplicates.append(duplicate)

    bpy.ops.object.select_all(action="DESELECT")
    for duplicate in duplicates:
        duplicate.select_set(True)
    bpy.context.view_layer.objects.active = duplicates[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    export_object = bpy.context.object
    export_object.name = "Printable_Ring_Mesh"

    dimensions = [dimension for dimension in export_object.dimensions if dimension > 0.0]
    smallest_dimension = min(dimensions) if dimensions else 1.0
    voxel_size = max(0.07, min(0.22, smallest_dimension / 36.0))
    for multiplier in (1.0, 1.35, 1.8):
        _voxel_remesh(export_object, voxel_size * multiplier)
        _clean_mesh(export_object, voxel_size * multiplier * 0.08)
        if count_mesh_components(export_object) <= 1 and count_non_manifold_edges(export_object) == 0:
            voxel_size *= multiplier
            break
    if count_mesh_components(export_object) > 1:
        _keep_largest_component(export_object)
        _voxel_remesh(export_object, voxel_size)
        _clean_mesh(export_object, voxel_size * 0.08)
    component_count, non_manifold_edges = validate_printable_mesh(export_object)
    return export_object, voxel_size, component_count, non_manifold_edges


def export_stl(export_object: bpy.types.Object, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    export_object.hide_set(False)
    export_object.select_set(True)
    bpy.context.view_layer.objects.active = export_object
    try:
        bpy.ops.wm.stl_export(filepath=str(output_path), export_selected_objects=True)
        return
    except (AttributeError, RuntimeError, TypeError):
        pass
    try:
        bpy.ops.export_mesh.stl(filepath=str(output_path), use_selection=True)
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError("Could not export STL with this Blender installation.") from exc


def _load_view_ids(raw_json: str) -> list[str]:
    try:
        values = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("--view-ids-json must contain a JSON list") from exc
    if not isinstance(values, list):
        raise ValueError("--view-ids-json must contain a JSON list")
    return [str(value) for value in values]


def main() -> None:
    global METAL_MATERIAL
    args = parse_args()
    input_json = Path(args.input_json)
    output_stl = Path(args.output_stl)
    preview_path = Path(args.preview)
    camera_path = Path(args.camera_npz) if args.camera_npz else None
    view_ids = _load_view_ids(args.view_ids_json)

    try:
        params = normalize_parameters(json.loads(input_json.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load parameter JSON: {input_json}") from exc

    clear_scene()
    METAL_MATERIAL = create_material(
        "Silver_Metal",
        (0.22, 0.27, 0.34, 1.0),
        metallic=0.88,
        roughness=0.24,
    )
    display_objects = create_ring(params)
    orient_ring_for_dataset(display_objects)
    camera_source = render_preview(
        display_objects,
        preview_path,
        view_ids,
        camera_path,
        max(256, min(2048, int(args.resolution))),
    )
    export_object, voxel_size, component_count, non_manifold_edges = create_export_mesh(display_objects)
    export_stl(export_object, output_stl)

    metadata = {
        "camera_source": camera_source,
        "preview_file": str(preview_path),
        "mesh_component_count": component_count,
        "non_manifold_edges": non_manifold_edges,
        "metal_only": True,
        "voxel_size_mm": round(voxel_size, 4),
        "stl_path": str(output_stl),
    }
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
