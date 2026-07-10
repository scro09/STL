import os
from pathlib import Path

from .ollama_client import analyze_image_with_ollama


def analyze_image(image_path: str | Path) -> dict:
    provider = os.getenv("VISION_PROVIDER", "ollama").lower().strip()
    image_path = Path(image_path)

    if provider == "ollama":
        return analyze_image_with_ollama(image_path)

    raise ValueError(f"Unsupported VISION_PROVIDER: {provider}")