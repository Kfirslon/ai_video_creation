"""Auto-mode pipeline: generate all scene videos via Kie.ai Veo 3 Fast.

Replaces the manual Google Flow paste loop. Only used when KIE_AI_API_KEY is
configured AND a public base URL is reachable (so Kie.ai can fetch our images).

Cost note: ~$0.80 per 8s clip on veo3_fast 720p. An 8-scene video ≈ $6.40.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .. import config, video_client


def _public_image_url(slug: str, scene_n: int) -> str:
    base = config.public_base_url()
    if not base:
        raise RuntimeError(
            "PUBLIC_BASE_URL not set and SPACE_ID not detected. "
            "Auto-mode needs a public URL so Kie.ai can fetch the scene images."
        )
    return f"{base}/files/{slug}/images/scene_{scene_n}.png"


def generate_all(
    pack: dict,
    project_dir: Path,
    progress: Callable[[int, int, str], None] | None = None,
    max_parallel: int = 3,
) -> None:
    """Generate every missing scene video in parallel. Idempotent: skips files that already exist."""
    slug = project_dir.name
    videos_dir = project_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    scenes = pack["scenes"]
    n = len(scenes)

    # Build the work list — skip scenes whose video already exists
    todo = []
    for s in scenes:
        i = s["scene_number"]
        out = videos_dir / f"scene_{i}.mp4"
        if out.exists() and out.stat().st_size > 0:
            continue
        # Combined prompt = animation directions + voiceover veo_prompt (already engineered)
        anim = s.get("animation_prompt", "")
        vo = ((s.get("voiceover_script") or {}).get("veo_prompt")) or ""
        prompt = (anim + "\n\n" + vo).strip()
        image_url = _public_image_url(slug, i)
        todo.append((i, prompt, image_url, out))

    total = len(todo)
    done = 0
    if progress:
        progress(0, total, f"submitting {total} scenes")

    if total == 0:
        return

    # Run generations in parallel — each one polls + downloads
    def _one(args):
        i, prompt, image_url, out = args
        video_client.generate_one(prompt, image_url, out)
        return i

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {pool.submit(_one, t): t for t in todo}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                i = fut.result()
                done += 1
                if progress:
                    progress(done, total, f"finished scene {i} ({done}/{total})")
            except Exception as e:
                if progress:
                    progress(done, total, f"scene {t[0]} failed: {e}")
                raise
