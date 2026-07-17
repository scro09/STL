from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .ollama_client import analyze_multiview_with_ollama, analyze_single_image_with_ollama


def _require_ollama_provider() -> None:
    provider = os.getenv("VISION_PROVIDER", "ollama").lower().strip()
    if provider != "ollama":
        raise ValueError(f"Unsupported VISION_PROVIDER: {provider}. This pipeline requires Ollama.")


def analyze_multiview(image_paths: Sequence[Path], view_ids: Sequence[str]) -> dict[str, Any]:
    _require_ollama_provider()
    return analyze_multiview_with_ollama(image_paths, view_ids)


def analyze_image(image_path: str | Path) -> dict[str, Any]:
    _require_ollama_provider()
    path = Path(image_path)
    return analyze_single_image_with_ollama(path)
