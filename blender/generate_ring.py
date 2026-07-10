import argparse
import json
import math
from pathlib import Path

import bpy


def parse_args():
    parser = argparse.ArgumentParser(description="Generate ring STL from JSON parameters")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-stl", required=True)
    parser.add_argument("--preview", required=True)

    import sys
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []

    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def create_material(name, color, metallic=0.0, roughness=0.3):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness

    return mat


def shade_smooth(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    obj.select_set(False)


def create_ring_band(params, metal_mat):
    band = params["band"]

    outer_radius = float(band["outer_radius_mm"])
    inner_radius = float(band["inner_radius_mm"])
    band_width = float(band["band_width_mm"])

  
    major_radius = (outer_radius + inner_radius) / 2.0
    minor_radius = max(0.5, (outer_radius - inner_radius) / 2.0)

    bpy.ops.mesh.primitive_torus_add(
        major_segments=160,
        minor_segments=24,
        major_radius=major_radius,
        minor_radius=minor_radius,
        location=(0, 0, 0)
    )

    ring = bpy.context.object
    ring.name = "Generated_Ring_Band"
    ring.data.materials.append(metal_mat)

    target_z = max(1.0, band_width)
    current_z = max(0.001, minor_radius * 2.0)
    ring.scale.z = target_z / current_z

    bpy.context.view_layer.objects.active = ring
    ring.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ring.select_set(False)

    shade_smooth(ring)

    return ring


def create_main_stone(params, gem_mat):
    stone = params["stone"]

    if not stone["has_stone"]:
        return None

    band = params["band"]
    outer_radius = float(band["outer_radius_mm"])

    size = max(1.0, float(stone["size_mm"]))
    height = max(1.0, float(stone["height_mm"]))
    shape = stone["shape"]

    x = 0
    y = outer_radius
    z = float(band["band_width_mm"]) / 2.0 + height / 2.0

    if shape == "square":
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(x, y, z)
        )
        gem = bpy.context.object
        gem.name = "Main_Square_Stone"
        gem.dimensions = (size, size, height)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    else:
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=48,
            ring_count=24,
            radius=1,
            location=(x, y, z)
        )
        gem = bpy.context.object
        gem.name = "Main_Round_Stone"

        if shape == "oval":
            gem.scale = (size / 2.0, size / 3.0, height / 2.0)
        else:
            gem.scale = (size / 2.0, size / 2.0, height / 2.0)

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        shade_smooth(gem)

    gem.data.materials.append(gem_mat)
    return gem


def create_side_stones(params, gem_mat):
    decorations = params["decorations"]

    if not decorations["has_side_stones"]:
        return []

    count = int(decorations["side_stone_count"])
    count = max(0, min(count, 24))

    if count == 0:
        return []

    band = params["band"]
    outer_radius = float(band["outer_radius_mm"])
    z = float(band["band_width_mm"]) / 2.0 + 0.6

    stones = []

    start_angle = 55
    end_angle = 125

    if count == 1:
        angles = [90]
    else:
        angles = [
            start_angle + i * (end_angle - start_angle) / (count - 1)
            for i in range(count)
        ]

    for idx, angle_deg in enumerate(angles):
        angle = math.radians(angle_deg)
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)

        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24,
            ring_count=12,
            radius=0.65,
            location=(x, y, z)
        )

        stone = bpy.context.object
        stone.name = f"Side_Stone_{idx + 1}"
        stone.data.materials.append(gem_mat)
        shade_smooth(stone)
        stones.append(stone)

    return stones


def create_simple_engraving_markers(params, metal_mat):
    decorations = params["decorations"]

    if not decorations["has_engraving"]:
        return []

    band = params["band"]
    outer_radius = float(band["outer_radius_mm"])

    markers = []

    for idx, angle_deg in enumerate([210, 230, 250, 270, 290, 310, 330]):
        angle = math.radians(angle_deg)
        x = outer_radius * math.cos(angle)
        y = outer_radius * math.sin(angle)

        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(x, y, 0)
        )

        marker = bpy.context.object
        marker.name = f"Engraving_Marker_{idx + 1}"
        marker.dimensions = (0.35, 1.2, 0.2)
        marker.rotation_euler[2] = angle
        marker.data.materials.append(metal_mat)

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        markers.append(marker)

    return markers


def join_meshes():
    bpy.ops.object.select_all(action="DESELECT")

    mesh_objects = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH"
    ]

    if not mesh_objects:
        return None

    for obj in mesh_objects:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = mesh_objects[0]

    try:
        bpy.ops.object.join()
        joined = bpy.context.object
        joined.name = "Generated_Ring_Model"
        return joined
    except Exception:
        return mesh_objects[0]


def setup_camera_and_light():
    bpy.ops.object.light_add(type="AREA", location=(0, -30, 35))
    light = bpy.context.object
    light.name = "Key_Light"
    light.data.energy = 500
    light.data.size = 6

    bpy.ops.object.camera_add(
        location=(0, -45, 25),
        rotation=(math.radians(60), 0, 0)
    )

    camera = bpy.context.object
    bpy.context.scene.camera = camera

    return camera


def export_stl(output_path: Path):
    bpy.ops.object.select_all(action="DESELECT")

    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            obj.select_set(True)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        bpy.ops.wm.stl_export(filepath=str(output_path))
        return
    except Exception:
        pass

    try:
        bpy.ops.export_mesh.stl(filepath=str(output_path), use_selection=True)
        return
    except Exception as exc:
        raise RuntimeError(
            "Could not export STL. In Blender 3.x, make sure the STL export addon is enabled."
        ) from exc


def render_preview(preview_path: Path):
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    bpy.context.scene.render.filepath = str(preview_path)

    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        try:
            bpy.context.scene.render.engine = "BLENDER_EEVEE"
        except Exception:
            pass

    bpy.ops.render.render(write_still=True)


def main():
    args = parse_args()

    input_json = Path(args.input_json)
    output_stl = Path(args.output_stl)
    preview_path = Path(args.preview)

    with open(input_json, "r", encoding="utf-8") as f:
        params = json.load(f)

    clear_scene()

    metal_mat = create_material(
        name="Silver_Metal",
        color=(0.75, 0.72, 0.68, 1.0),
        metallic=1.0,
        roughness=0.22
    )

    gem_mat = create_material(
        name="Gemstone",
        color=(0.2, 0.55, 1.0, 1.0),
        metallic=0.0,
        roughness=0.05
    )

    create_ring_band(params, metal_mat)
    create_main_stone(params, gem_mat)
    create_side_stones(params, gem_mat)
    create_simple_engraving_markers(params, metal_mat)

    join_meshes()
    setup_camera_and_light()

    export_stl(output_stl)
    render_preview(preview_path)

    print(f"Exported STL to: {output_stl}")
    print(f"Rendered preview to: {preview_path}")


if __name__ == "__main__":
    main()