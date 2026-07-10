import base64
import json
import os
from pathlib import Path
import requests



def encode_image_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def add_safe_defaults(data: dict) -> dict:
    data.setdefault("object_type", "ring")
    data.setdefault("style", "unknown")

    data.setdefault("band", {})
    data["band"].setdefault("outer_radius_mm", 12.0)
    data["band"].setdefault("inner_radius_mm", 8.0)
    data["band"].setdefault("band_width_mm", 4.0)
    data["band"].setdefault("band_thickness_mm", 2.0)
    data["band"].setdefault("shape", "round")

    if data["band"]["inner_radius_mm"] >= data["band"]["outer_radius_mm"]:
        data["band"]["inner_radius_mm"] = data["band"]["outer_radius_mm"] - 3.0

    data.setdefault("stone", {})
    data["stone"].setdefault("has_stone", False)
    data["stone"].setdefault("shape", "none")
    data["stone"].setdefault("size_mm", 0.0)
    data["stone"].setdefault("height_mm", 0.0)

    data.setdefault("decorations", {})
    data["decorations"].setdefault("has_side_stones", False)
    data["decorations"].setdefault("side_stone_count", 0)
    data["decorations"].setdefault("has_engraving", False)

    data.setdefault("confidence", 0.5)

    return data


def analyze_image_with_ollama(image_path: Path) -> dict:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("VISION_MODEL", "qwen2.5vl:3b")

    image_base64 = encode_image_base64(image_path)

    prompt = """
Analyze this jewelry image.

The object should be a ring. Return ONLY valid JSON.

Use this structure:
{
  "object_type": "ring",
  "style": "simple_band | solitaire | signet | decorative | unknown",
  "band": {
    "outer_radius_mm": number,
    "inner_radius_mm": number,
    "band_width_mm": number,
    "band_thickness_mm": number,
    "shape": "round | flat | unknown"
  },
  "stone": {
    "has_stone": boolean,
    "shape": "round | oval | square | none | unknown",
    "size_mm": number,
    "height_mm": number
  },
  "decorations": {
    "has_side_stones": boolean,
    "side_stone_count": integer,
    "has_engraving": boolean
  },
  "confidence": number
}

Do not write explanations.
Do not write markdown.
Only JSON.
"""

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "options": {
            "temperature": 0
        }
    }

    response = requests.post(
        f"{base_url}/api/generate",
        json=payload,
        timeout=180
    )

    if response.status_code != 200:
        raise RuntimeError(f"Ollama error {response.status_code}: {response.text}")

    result = response.json()
    raw_text = result.get("response", "").strip()

    if not raw_text:
        raise RuntimeError("Ollama returned empty response.")

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        print("Ollama raw response:")
        print(raw_text)
        raise RuntimeError("Ollama did not return valid JSON.")

    return add_safe_defaults(data)