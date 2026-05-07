"""CLI smoke test that exercises the full pipeline without the web UI.

Usage:
    python -m src.smoke "office betrayal"
    python -m src.smoke "office betrayal" --style retro_tech_head
    python -m src.smoke "office betrayal" --assemble-fixtures   # use existing AI videos/ for assembly test

The --assemble-fixtures flag skips Veo (which has no free API) and stitches
the 8 mp4s already in `../AI videos/` to validate the assembly stage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from .pipeline import assemble, images, metadata, scene_pack, story


FIXTURES_DIR = config.ROOT.parent / "AI videos"


def _print(msg: str) -> None:
    print(f"[smoke] {msg}", flush=True)


def _resolve_fixtures() -> list[Path]:
    if not FIXTURES_DIR.exists():
        raise SystemExit(f"Fixture folder not found: {FIXTURES_DIR}")
    files = sorted(FIXTURES_DIR.glob("*.mp4"))
    if len(files) < 8:
        raise SystemExit(f"Need 8 fixture mp4s in {FIXTURES_DIR}, found {len(files)}")
    return files[:8]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("theme", help="Theme keyword to seed the story ideas")
    parser.add_argument("--style", default="retro_tech_head", help="Style key from style_presets.json")
    parser.add_argument("--idea-index", type=int, default=0, help="Pick the Nth idea (0-9)")
    parser.add_argument("--assemble-fixtures", action="store_true",
                        help="Stitch the 8 existing fixture videos to test assembly end-to-end")
    parser.add_argument("--music", type=str, default=None, help="Path to a background music file")
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip image generation (useful when testing assembly without burning API quota)")
    args = parser.parse_args()

    _print(f"Generating 10 ideas for style={args.style} theme={args.theme!r}")
    ideas = story.generate_ideas(style_key=args.style, theme=args.theme)
    for i, idea in enumerate(ideas):
        _print(f"  [{i}] {idea}")
    chosen = ideas[args.idea_index]
    _print(f"Chose: {chosen}")

    _print("Generating scene pack...")
    pack = scene_pack.generate_scene_pack(chosen, style_key=args.style)
    slug = config.slugify(pack["title"])
    proj = config.project_dir(slug)
    scene_pack.save_scene_pack(pack, proj)
    _print(f"Scene pack saved to {proj}/scene_pack.json")

    if not args.skip_images:
        _print("Generating 8 images via Gemini image API...")
        images.generate_all_images(
            pack, proj,
            progress=lambda i, n, status: _print(f"  ({i}/{n}) {status}"),
        )

    _print("Generating posting metadata...")
    meta = metadata.generate_metadata(pack)
    metadata.save_metadata(meta, proj)
    _print(f"Title:       {meta['title']}")
    _print(f"Description: {meta['description']}")
    _print(f"Hashtags:    {' '.join('#' + h for h in meta['hashtags'])}")

    if args.assemble_fixtures:
        _print("Assembling using fixture videos from ../AI videos/")
        clips = _resolve_fixtures()
        music = Path(args.music) if args.music else None
        out = assemble.assemble_with_captions(clips, proj, music_path=music)
        _print(f"DONE: {out}")
    else:
        _print(f"Scene pack ready. Now paste each scene's combined Veo prompt into Google Flow,")
        _print(f"drop the 8 returned mp4s into {proj}/videos/, then run:")
        _print(f"  python -m src.smoke \"{args.theme}\" --assemble-fixtures --music <path>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
