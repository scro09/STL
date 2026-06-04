from llm.analyze_ring import analyze_ring
from cad.ring_generator import generate_ring
from cad.stone import add_stone
from cad.export import export_stl

IMAGE = "input/r3.png"

WIDTH_MAP = {
    "very_narrow": 3,
    "narrow": 4,
    "medium": 6,
    "wide": 8,
    "very_wide": 10
}

THICKNESS_MAP = {
    "thin": 1.5,
    "medium": 2.5,
    "thick": 4
}

print("Analyzing ring...")

data = analyze_ring(IMAGE)
print(data)

band_width = WIDTH_MAP[data["band_width_class"]]
wall_thickness = THICKNESS_MAP[data["thickness_class"]]

finger_radius = 9  
ring = generate_ring(
    finger_radius=finger_radius,
    band_width=band_width,
    wall_thickness=wall_thickness
)

if data["has_stone"]:
    ring = add_stone(ring, data["stone_size_mm"])

export_stl(ring, "output/r3.stl")

print("STL generated.")