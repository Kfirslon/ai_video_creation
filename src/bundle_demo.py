"""One-shot script: compress source demo PNGs into small WebPs bundled in the repo.

Run once when you want to refresh the deployed Space's hero/marquee/gallery visuals.
Skipped during normal app operation. Output: src/web/static/demo/images/*.webp
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT.parent / "AI photos (scenes)" / "Camera - photos",
    ROOT.parent / "AI photos (scenes)" / "Pen - photos",
]
OUT = ROOT / "src" / "web" / "static" / "demo" / "images"
OUT.mkdir(parents=True, exist_ok=True)

MAX_W = 720          # vertical-9:16 friendly; UI displays much smaller anyway
WEBP_QUALITY = 72    # visually clean, ~150-250 KB per image
TAKE_PER_SOURCE = 4  # cap to keep the repo lean


def main() -> None:
    out_idx = 0
    for src_dir in SOURCES:
        if not src_dir.exists():
            print(f"skip: {src_dir} (missing)")
            continue
        pngs = sorted(p for p in src_dir.glob("*.png"))[:TAKE_PER_SOURCE]
        for p in pngs:
            out_idx += 1
            dst = OUT / f"demo_{out_idx:02d}.webp"
            with Image.open(p) as im:
                im = im.convert("RGB")
                w, h = im.size
                if w > MAX_W:
                    new_h = round(h * MAX_W / w)
                    im = im.resize((MAX_W, new_h), Image.LANCZOS)
                im.save(dst, "WEBP", quality=WEBP_QUALITY, method=6)
            kb = dst.stat().st_size / 1024
            print(f"{dst.relative_to(ROOT)}  {kb:.0f} KB")


if __name__ == "__main__":
    main()
