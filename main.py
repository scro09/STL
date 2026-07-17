from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ring_schema import normalize_parameters
from vision.vision_client import analyze_image, analyze_multiview


PROJECT_ROOT = Path(__file__).resolve().parent
ORCHESTRATOR_FILE = Path(__file__).resolve()
BLENDER_SCRIPT = PROJECT_ROOT / "blender" / "generate_ring.py"
RING_SCHEMA_FILE = PROJECT_ROOT / "ring_schema.py"
FALLBACK_VIEW_IDS = ("000", "005", "008", "016", "024")
FINAL_OUTPUT_NAMES = {"chain1_parameters.json", "final.stl", "preview.png"}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_parameters(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid parameter file: {path}") from exc
    return normalize_parameters(data)


def _cleanup_output_directory(output_dir: Path, keep_names: set[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if child.name in keep_names:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _is_rgb_view(path: Path) -> bool:
    stem = path.stem.lower()
    return path.suffix.lower() in {".png", ".jpg", ".jpeg"} and not (
        stem.endswith("_depth") or stem.endswith("_normal")
    )


def load_object_views(object_dir: Path) -> tuple[list[str], list[Path], Path | None]:
    manifest_path = object_dir / "selected_views.json"
    camera_path: Path | None = None

    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid view manifest: {manifest_path}") from exc
        selected = manifest.get("selected_view_ids")
        if not isinstance(selected, list) or not selected:
            raise RuntimeError(f"selected_view_ids is missing or empty in {manifest_path}")
        view_ids = [Path(str(value)).stem for value in selected]
        camera_candidate = object_dir / str(manifest.get("camera_file", "cameras.npz"))
        camera_path = camera_candidate if camera_candidate.exists() else None
    else:
        view_ids = list(FALLBACK_VIEW_IDS)
        camera_candidate = object_dir / "cameras.npz"
        camera_path = camera_candidate if camera_candidate.exists() else None

    normalized_ids: list[str] = []
    image_paths: list[Path] = []
    for view_id in view_ids:
        candidates = [object_dir / f"{view_id}{suffix}" for suffix in (".png", ".jpg", ".jpeg")]
        image_path = next((path for path in candidates if path.exists() and _is_rgb_view(path)), None)
        if image_path is None:
            raise FileNotFoundError(f"RGB view {view_id} was not found in {object_dir}")
        normalized_ids.append(image_path.stem)
        image_paths.append(image_path)

    return normalized_ids, image_paths, camera_path


def run_blender(
    json_path: Path,
    stl_path: Path,
    preview_path: Path,
    camera_path: Path | None,
    view_ids: Sequence[str],
    resolution: int,
) -> None:
    blender_bin = os.getenv("BLENDER_BIN", "").strip()
    if not blender_bin:
        raise RuntimeError("BLENDER_BIN is required in .env.")
    command = [
        blender_bin,
        "--background",
        "--python-exit-code",
        "1",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--input-json",
        str(json_path.resolve()),
        "--output-stl",
        str(stl_path.resolve()),
        "--preview",
        str(preview_path.resolve()),
        "--resolution",
        str(resolution),
    ]
    if camera_path is not None:
        command.extend(["--camera-npz", str(camera_path.resolve())])
    if view_ids:
        command.extend(["--view-ids-json", json.dumps(list(view_ids))])

    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Blender was not found at '{blender_bin}'. Set BLENDER_BIN in .env."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Blender failed with exit code {exc.returncode}.") from exc


def _elapsed(started: float) -> str:
    return f"{time.perf_counter() - started:.1f}s"


def _final_preview_view(view_ids: Sequence[str]) -> str:
    if not view_ids:
        return "preview"
    if "024" in view_ids:
        return "024"
    return view_ids[len(view_ids) // 2]


def _blender_outputs_are_current(
    chain1_path: Path,
    final_stl_path: Path,
    final_preview_path: Path,
) -> bool:
    if not final_stl_path.exists() or not final_preview_path.exists():
        return False
    required_timestamp = max(
        chain1_path.stat().st_mtime,
        ORCHESTRATOR_FILE.stat().st_mtime,
        BLENDER_SCRIPT.stat().st_mtime,
        RING_SCHEMA_FILE.stat().st_mtime,
    )
    return min(final_stl_path.stat().st_mtime, final_preview_path.stat().st_mtime) >= required_timestamp


def process_object(object_dir: Path, output_root: Path, resolution: int, force: bool) -> bool:
    object_dir = object_dir.resolve()
    object_name = object_dir.name
    output_dir = output_root / object_name
    output_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_output_directory(output_dir, FINAL_OUTPUT_NAMES)

    chain1_path = output_dir / "chain1_parameters.json"
    final_stl_path = output_dir / "final.stl"
    final_preview_path = output_dir / "preview.png"

    try:
        reusable_parameters: dict[str, Any] | None = None
        if not force and chain1_path.exists():
            try:
                reusable_parameters = _load_parameters(chain1_path)
            except (RuntimeError, ValueError) as exc:
                print(f"[{object_name}] Existing Chain 1 is incompatible and will be regenerated: {exc}")

        if reusable_parameters is not None and _blender_outputs_are_current(
            chain1_path,
            final_stl_path,
            final_preview_path,
        ):
            _write_json(chain1_path, reusable_parameters)
            print(f"[{object_name}] Already complete; use --force to regenerate.")
            return True

        if force or reusable_parameters is None:
            for path in (chain1_path, final_stl_path, final_preview_path):
                if path.exists():
                    path.unlink()

        view_ids, image_paths, camera_path = load_object_views(object_dir)
        print(f"[{object_name}] RGB views: {', '.join(path.name for path in image_paths)}")

        if reusable_parameters is None or force:
            print(f"[{object_name}] Chain 1/2: Ollama multi-view -> JSON...")
            started = time.perf_counter()
            parameters = normalize_parameters(analyze_multiview(image_paths, view_ids))
            _write_json(chain1_path, parameters)
            print(f"[{object_name}] Chain 1 completed in {_elapsed(started)}")
        else:
            parameters = reusable_parameters
            _write_json(chain1_path, parameters)
            print(f"[{object_name}] Reusing valid Chain 1 parameters; regenerating Blender geometry.")

        print(f"[{object_name}] Chain 2/2: Blender -> STL + preview...")
        started = time.perf_counter()
        run_blender(
            chain1_path,
            final_stl_path,
            final_preview_path,
            camera_path,
            [_final_preview_view(view_ids)],
            resolution,
        )
        print(f"[{object_name}] Chain 2 completed in {_elapsed(started)}")

        missing = [
            path.name
            for path in (chain1_path, final_stl_path, final_preview_path)
            if not path.exists()
        ]
        if missing:
            raise RuntimeError(f"Missing final outputs: {', '.join(missing)}")
        _cleanup_output_directory(output_dir, FINAL_OUTPUT_NAMES)
        print(f"[{object_name}] Done: {output_dir}")
        return True
    except Exception as exc:
        for path in (final_stl_path, final_preview_path):
            if path.exists():
                path.unlink()
        _cleanup_output_directory(output_dir, FINAL_OUTPUT_NAMES)
        print(f"[{object_name}] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False


def process_image(image_path: Path, output_root: Path, resolution: int, force: bool) -> bool:
    image_path = image_path.resolve()
    image_name = image_path.stem
    output_dir = output_root / image_name
    output_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_output_directory(output_dir, FINAL_OUTPUT_NAMES)

    chain1_path = output_dir / "chain1_parameters.json"
    final_stl_path = output_dir / "final.stl"
    final_preview_path = output_dir / "preview.png"

    try:
        if not image_path.exists() or not _is_rgb_view(image_path):
            raise FileNotFoundError(f"Single-view RGB image not found: {image_path}")

        reusable_parameters: dict[str, Any] | None = None
        if not force and chain1_path.exists():
            try:
                reusable_parameters = _load_parameters(chain1_path)
            except (RuntimeError, ValueError) as exc:
                print(f"[{image_name}] Existing Chain 1 is incompatible and will be regenerated: {exc}")

        if reusable_parameters is not None and _blender_outputs_are_current(
            chain1_path,
            final_stl_path,
            final_preview_path,
        ):
            _write_json(chain1_path, reusable_parameters)
            print(f"[{image_name}] Already complete; use --force to regenerate.")
            return True

        if force or reusable_parameters is None:
            for path in (chain1_path, final_stl_path, final_preview_path):
                if path.exists():
                    path.unlink()

        print(f"[{image_name}] Single RGB image: {image_path.name}")
        if reusable_parameters is None or force:
            print(f"[{image_name}] Chain 1/2: one image -> one Ollama request -> JSON...")
            started = time.perf_counter()
            parameters = normalize_parameters(analyze_image(image_path))
            _write_json(chain1_path, parameters)
            print(f"[{image_name}] Chain 1 completed in {_elapsed(started)}")
        else:
            parameters = reusable_parameters
            _write_json(chain1_path, parameters)
            print(f"[{image_name}] Reusing valid Chain 1 parameters; regenerating Blender geometry.")

        print(f"[{image_name}] Chain 2/2: one Blender execution -> STL + preview...")
        started = time.perf_counter()
        run_blender(
            chain1_path,
            final_stl_path,
            final_preview_path,
            None,
            (),
            resolution,
        )
        print(f"[{image_name}] Chain 2 completed in {_elapsed(started)}")

        missing = [
            path.name
            for path in (chain1_path, final_stl_path, final_preview_path)
            if not path.exists()
        ]
        if missing:
            raise RuntimeError(f"Missing final outputs: {', '.join(missing)}")
        _cleanup_output_directory(output_dir, FINAL_OUTPUT_NAMES)
        print(f"[{image_name}] Done: {output_dir}")
        return True
    except Exception as exc:
        for path in (final_stl_path, final_preview_path):
            if path.exists():
                path.unlink()
        _cleanup_output_directory(output_dir, FINAL_OUTPUT_NAMES)
        print(f"[{image_name}] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False


def _object_sort_key(path: Path) -> tuple[int, str]:
    suffix = path.name.removeprefix("ring_")
    return (int(suffix) if suffix.isdigit() else sys.maxsize, path.name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Two-chain ring generation with Ollama and Blender")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--object-dir", type=Path, help="One dataset object directory")
    source.add_argument("--dataset-dir", type=Path, help="Directory containing ring_* objects")
    source.add_argument("--image", type=Path, help="One RGB photograph for single-view generation")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--force", action="store_true", help="Ignore reusable results and regenerate everything")
    return parser.parse_args()


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    output_root = args.output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    resolution = max(256, min(2048, args.resolution))

    if args.image is not None:
        if not process_image(args.image, output_root, resolution, args.force):
            raise SystemExit(1)
        return

    if args.object_dir is not None:
        if not process_object(args.object_dir, output_root, resolution, args.force):
            raise SystemExit(1)
        return

    dataset_dir = args.dataset_dir.resolve()
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    object_dirs = sorted(
        (path for path in dataset_dir.glob("ring_*") if path.is_dir()),
        key=_object_sort_key,
    )
    if not object_dirs:
        raise RuntimeError(f"No ring_* object directories found in {dataset_dir}")

    failures = sum(
        not process_object(object_dir, output_root, resolution, args.force)
        for object_dir in object_dirs
    )
    if failures:
        print(f"Finished with {failures} failed object(s) out of {len(object_dirs)}.", file=sys.stderr)
        raise SystemExit(1)
    print(f"Completed all {len(object_dirs)} objects.")


if __name__ == "__main__":
    main()
