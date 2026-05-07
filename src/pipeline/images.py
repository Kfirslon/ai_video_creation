"""Image generation for each scene.

Strategy: Scene 1 is generated cold. Scenes 2-8 are generated with Scene 1's
PNG passed back as a reference image to keep characters consistent across shots.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .. import image_client


def image_path(project_path: Path, scene_number: int) -> Path:
    return project_path / "images" / f"scene_{scene_number}.png"


def generate_all_images(
    pack: dict,
    project_path: Path,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[Path]:
    """Generate one image per scene, saving to <project>/images/scene_N.png.

    `progress(current, total, status)` is called after each image.
    Existing PNGs are skipped so the run can resume after a rate-limit pause.
    """
    scenes = pack["scenes"]
    total = len(scenes)
    paths: list[Path] = []
    reference: Path | None = None

    for i, scene in enumerate(scenes, start=1):
        out = image_path(project_path, scene["scene_number"])
        if out.exists():
            paths.append(out)
            if reference is None:
                reference = out
            if progress:
                progress(i, total, f"scene {i} (already on disk, skipped)")
            continue

        refs = [reference] if reference else None
        img = image_client.generate_image(scene["image_prompt"], reference_images=refs)
        img.save(out, format="PNG")
        paths.append(out)
        if reference is None:
            reference = out
        if progress:
            progress(i, total, f"scene {i} generated")

    return paths
