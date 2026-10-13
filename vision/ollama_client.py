from __future__ import annotations

import base64
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import requests

from ring_schema import PARAMETERS_JSON_SCHEMA


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required in .env.")
    return value


def _timeout_seconds() -> float:
    raw_value = _required_environment("OLLAMA_TIMEOUT_SECONDS")
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be a positive number.") from exc
    if timeout <= 0:
        raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be a positive number.")
    return timeout


def encode_image_base64(image_path: Path) -> str:
    try:
        return base64.b64encode(image_path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise RuntimeError(f"Could not read image: {image_path}") from exc


def _parse_json_response(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip().replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace < 0 or last_brace < first_brace:
        raise RuntimeError(f"Ollama did not return a JSON object: {text[:500]}")
    json_text = text[first_brace : last_brace + 1]

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama did not return valid JSON: {json_text[:500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama returned JSON, but the root value is not an object.")
    wrapped_ring = parsed.get("ring")
    if isinstance(wrapped_ring, dict):
        return wrapped_ring
    return parsed




def _request_structured_json(prompt: str, image_paths: Sequence[Path]) -> dict[str, Any]:
    if not image_paths:
        raise ValueError("At least one RGB image is required for Ollama Vision.")

    base_url = _required_environment("OLLAMA_BASE_URL").rstrip("/")
    api_key = _required_environment("OLLAMA_API_KEY")
    model = _required_environment("VISION_MODEL")
    timeout_seconds = _timeout_seconds()
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [encode_image_base64(path) for path in image_paths],
        "format": PARAMETERS_JSON_SCHEMA,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 500,
        },
    }

    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not contact Ollama at {base_url}: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(f"Ollama error {response.status_code}: {response.text[:1000]}")

    result = response.json()
    raw_text = str(result.get("response", "")).strip()
    if not raw_text:
        raise RuntimeError("Ollama returned an empty response.")
    return _parse_json_response(raw_text)


def analyze_multiview_with_ollama(
    image_paths: Sequence[Path],
    view_ids: Sequence[str],
) -> dict[str, Any]:
    ordered_views = ", ".join(f"image {index + 1}={view_id}" for index, view_id in enumerate(view_ids))
    prompt = f"""
You are estimating one parametric ring from multiple RGB views of the same physical object.
The images are ordered as: {ordered_views}.

Analyze every view together before choosing parameters. Use silhouette, visible inner opening,
band profile, visible setting, and perspective changes to avoid treating highlights as geometry.
Estimate proportions jointly: compare the inner opening diameter with band thickness, setting width,
and support height in every view. With no physical scale, use a plausible adult inner radius of
7.5-12 mm rather than shrinking the ring to fit the setting.
The final STL must contain metal only. Record an observed gemstone only in stone_reference so its
shape and size can dimension the empty seat, basket, bezel, channels, supports, and prongs. Never
describe gemstone geometry for export. Estimate setting type, prong count, seat depth, and support
height from the visible metal. Shallow repeated metallic lines, dots, beads, ridges, and grooves
belong to surface_pattern. Determine whether they are engraved or raised, their rows, placement,
spacing, and angular interval. Repeated patterns must have a realistic count_per_row greater than
one. Beaded edges normally use two rows at outer_edges and repeat around the visible/full band.
Use surface_pattern.layers for every visually different row or arc. Each layer has its own type,
mode, count, dimensions, start/end angles, and axial_offset_ratio; never force unlike rows into one
uniform full-circumference pattern. Angular convention: the central setting is 90 degrees, the ring
bottom is 270 degrees, right is 0 degrees, and left is 180 degrees. Use partial arcs when details
appear only on shoulders near the setting.
Estimate one coherent set of physical dimensions in millimeters.
Do not reuse generic values from another ring. Choose exactly one enum value for every enum field.
Return exactly one JSON object, with no markdown, code fences, prose, or explanation. Do not wrap it
inside a ring key. Its mandatory top-level keys are exactly: template, band, stone_reference,
setting, surface_pattern, confidence. Use template values simple_band, pave_band, or solitaire.
The band object must use inner_radius_mm, width_mm, thickness_mm, and cross_section. Never substitute
inner_diameter, width, thickness, or profile. Never return null sections: use complete disabled
stone_reference, setting, and surface_pattern objects when those features are absent. Match the
supplied structured-output schema.
""".strip()
    return _request_structured_json(prompt, image_paths)


def analyze_single_image_with_ollama(image_path: Path) -> dict[str, Any]:
    prompt = """
You are estimating one parametric ring from exactly one RGB photograph.

Analyze only the supplied photograph. Do not assume, synthesize, or request additional views.
Estimate a coherent ring in millimeters from the visible silhouette, inner opening, band profile,
stone setting, and metallic surface details. The final STL must contain metal only. Record the
observed gemstone only in stone_reference to dimension the empty seat and setting; it must never
become generated geometry. Estimate prongs, basket, bezel, supports, channels, seat depth, and
support height from visible metal. Put shallow metallic lines, dots, beads, ridges, and grooves in
surface_pattern. Repeated patterns must have count_per_row greater than one; beaded edges normally
use two rows at outer_edges. Use surface_pattern.layers when visible rows or arcs differ; each layer
must keep independent type, count, dimensions, angular interval, and axial_offset_ratio. Do not
force shoulder-only details around the full circumference. Choose exactly one enum value for every enum field. Return only the JSON matching the
supplied structured-output schema. Return exactly one JSON object, with no markdown, code fences,
prose, or explanation. Do not wrap it inside a ring key. Its mandatory top-level keys are exactly:
template, band, stone_reference, setting, surface_pattern, confidence. Use template values
simple_band, pave_band, or solitaire. The band object must use inner_radius_mm, width_mm,
thickness_mm, and cross_section. Never substitute inner_diameter, width, thickness, or profile.
Never return null sections: use complete disabled stone_reference, setting, and surface_pattern
objects when those features are absent.
""".strip()
    return _request_structured_json(prompt, [image_path])
