from PIL import Image
import numpy as np
from stl import mesh

IMAGE_PATH = "ring2.webp"
STL_NAME = "ring2.stl"

MAX_HEIGHT = 10.0      
BASE_THICKNESS = 2.0   
XY_SCALE = 1.0         

img = Image.open(IMAGE_PATH).convert("L")  
img = img.transpose(Image.FLIP_TOP_BOTTOM)

height_map = np.array(img) / 255.0
height_map = BASE_THICKNESS + height_map * MAX_HEIGHT

rows, cols = height_map.shape

vertices = []

for y in range(rows):
    for x in range(cols):
        z = height_map[y, x]
        vertices.append([x * XY_SCALE, y * XY_SCALE, z])

vertices = np.array(vertices)

faces = []

def vertex_index(x, y):
    return y * cols + x

for y in range(rows - 1):
    for x in range(cols - 1):

        v1 = vertex_index(x, y)
        v2 = vertex_index(x + 1, y)
        v3 = vertex_index(x, y + 1)
        v4 = vertex_index(x + 1, y + 1)

        faces.append([v1, v2, v3])

        faces.append([v2, v4, v3])

faces = np.array(faces)

surface = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))

for i, face in enumerate(faces):
    for j in range(3):
        surface.vectors[i][j] = vertices[face[j], :]

surface.save(STL_NAME)

print(f"STL saved as {STL_NAME}")