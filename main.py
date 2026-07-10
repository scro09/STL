import argparse
import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from vision.vision_client import analyze_image


def run_blender(json_path: Path, stl_path: Path, preview_path: Path) -> None:
    blender_bin = os.getenv("BLENDER_BIN", "blender")
    blender_script = Path("blender/generate_ring.py").resolve()

    command = [
        blender_bin,
        "--background",
        "--python",
        str(blender_script),
        "--",
        "--input-json",
        str(json_path.resolve()),
        "--output-stl",
        str(stl_path.resolve()),
        "--preview",
        str(preview_path.resolve()),
    ]

    print("Running Blender with command:")
    print(command)

    subprocess.run(command, check=True)

def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="2D image to 3D STL using Ollama Vision + Blender")
    parser.add_argument("--image", required=True, help="Path to input image, example: input_images/ring_01.png")
    parser.add_argument("--name", default=None, help="Output base name, example: ring_01")
    args = parser.parse_args()

    image_path = Path(args.image)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    base_name = args.name or image_path.stem

    json_path = output_dir / f"{base_name}.json"
    stl_path = output_dir / f"{base_name}.stl"
    preview_path = output_dir / f"{base_name}_preview.png"

    print("Analyzing image with vision model...")
    params = analyze_image(image_path)

    print("Saving JSON...")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)

    print(f"JSON saved to: {json_path}")

    run_blender(json_path=json_path, stl_path=stl_path, preview_path=preview_path)

    print("Done.")
    print(f"STL: {stl_path}")
    print(f"Preview: {preview_path}")


if __name__ == "__main__":
    main()