"""FastAPI app — guided UI for the video pipeline.

State machine per project (persisted to projects/<slug>/state.json):
    idle -> ideating -> picked -> images -> videos -> assembling -> done
"""
from __future__ import annotations

import io as io_mod
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .. import config, image_client, text_client
from ..pipeline import assemble, images, metadata, scene_pack, story

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("viralshorts")

app = FastAPI(title="AI Viral Shorts Generator")


# Public deploys (HF Spaces) need a password gate so strangers can't drain the free Gemini quota.
# Local dev: leave APP_PASSWORD unset and middleware no-ops.
_AUTH_EXEMPT_PATHS = {"/", "/api/health", "/api/auth", "/favicon.ico"}
_AUTH_EXEMPT_PREFIXES = ("/static/",)


class PasswordGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not config.APP_PASSWORD:
            return await call_next(request)
        path = request.url.path
        if path in _AUTH_EXEMPT_PATHS or any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
            return await call_next(request)
        provided = request.headers.get("X-App-Password", "")
        if provided != config.APP_PASSWORD:
            return JSONResponse({"error": "auth required"}, status_code=401)
        return await call_next(request)


app.add_middleware(PasswordGateMiddleware)


@app.exception_handler(Exception)
async def all_errors(_req: Request, exc: Exception) -> JSONResponse:
    """Surface real error messages to the UI instead of opaque 500s."""
    if isinstance(exc, HTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    log.error("Unhandled exception:\n%s", traceback.format_exc())
    return JSONResponse(
        {"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]},
        status_code=500,
    )


@app.get("/favicon.ico")
def _no_favicon() -> Response:
    return Response(status_code=204)


# Demo assets — fixture stash from the parent folder, used for the hero gallery + landing visuals.
# Folders may have been renamed by the user, so we accept multiple candidates per kind.
# In a deployed Docker container (HF Spaces) the parent folder won't have these — falls back to
# a bundled subset under src/web/static/demo/ shipped with the repo.
_PARENT = config.ROOT.parent  # ".../ai video creation/"
_BUNDLED_DEMO = Path(__file__).resolve().parent / "static" / "demo"

_DEMO_CANDIDATES = {
    "image": [_PARENT / "AI photos (scenes)", _PARENT / "AI photos", _BUNDLED_DEMO / "images"],
    "video": [_PARENT / "AI videos (scenes)", _PARENT / "AI videos", _BUNDLED_DEMO / "videos"],
    "final": [_PARENT / "AI_completed_Videos", _PARENT / "AI_video_1_ready", _BUNDLED_DEMO / "finals"],
}


_DEMO_EXTS = {
    "image": (".png", ".jpg", ".jpeg", ".webp"),
    "video": (".mp4", ".webm", ".mov"),
    "final": (".mp4", ".webm", ".mov"),
}


def _resolve_demo_root(kind: str) -> Path | None:
    """Return the first existing candidate folder for a given demo kind, or None."""
    for c in _DEMO_CANDIDATES.get(kind, []):
        if c.exists() and any(c.iterdir()):
            return c
    return None


def _collect_demo_files(root: Path, exts: tuple[str, ...]) -> list[Path]:
    """Recursively gather demo files (folders may contain subfolders per scene-batch)."""
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            out.append(p)
    return out


def _rel_id(root: Path, p: Path) -> str:
    """URL-safe relative id within a demo root (slashes replaced for path parameter use)."""
    return p.relative_to(root).as_posix().replace("/", "::")


@app.get("/api/demo")
def demo_manifest() -> dict:
    """List available demo assets for the hero gallery."""
    img_root = _resolve_demo_root("image")
    vid_root = _resolve_demo_root("video")
    fin_root = _resolve_demo_root("final")
    images = _collect_demo_files(img_root, _DEMO_EXTS["image"]) if img_root else []
    videos = _collect_demo_files(vid_root, _DEMO_EXTS["video"]) if vid_root else []
    finals = _collect_demo_files(fin_root, _DEMO_EXTS["final"]) if fin_root else []
    return {
        "images": [f"/demo/image/{_rel_id(img_root, p)}" for p in images] if img_root else [],
        "scene_videos": [f"/demo/video/{_rel_id(vid_root, p)}" for p in videos] if vid_root else [],
        "finals": [f"/demo/final/{_rel_id(fin_root, p)}" for p in finals] if fin_root else [],
    }


@app.get("/demo/{kind}/{name:path}")
def demo_file(kind: str, name: str) -> FileResponse:
    if kind not in _DEMO_CANDIDATES or ".." in name:
        raise HTTPException(404)
    root = _resolve_demo_root(kind)
    if not root:
        raise HTTPException(404)
    rel = name.replace("::", "/")
    p = (root / rel).resolve()
    # Guard against path traversal — must stay inside the resolved root
    try:
        p.relative_to(root.resolve())
    except ValueError:
        raise HTTPException(404)
    if not p.exists() or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Background-job tracking: { slug: { stage, progress, status, error? } }
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _job_set(slug: str, **kwargs: Any) -> None:
    with JOBS_LOCK:
        JOBS.setdefault(slug, {})
        JOBS[slug].update(kwargs)


def _job_get(slug: str) -> dict[str, Any]:
    with JOBS_LOCK:
        return dict(JOBS.get(slug, {}))


def _state_path(slug: str) -> Path:
    return config.PROJECTS_DIR / slug / "state.json"


def _save_state(slug: str, state: dict) -> None:
    _state_path(slug).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_state(slug: str) -> dict:
    p = _state_path(slug)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    """Return which providers are configured. UI shows this as a status banner."""
    return {
        "text_provider": text_client.active_provider(),
        "image_provider": f"gemini ({image_client.active_model()})" if config.GEMINI_API_KEY else "none — set GEMINI_API_KEY",
        "groq_configured": bool(config.GROQ_API_KEY),
        "gemini_configured": bool(config.GEMINI_API_KEY),
        "password_required": bool(config.APP_PASSWORD),
    }


@app.post("/api/auth")
def auth_check(payload: dict) -> dict:
    """Verify a password against APP_PASSWORD. Used by the frontend gate."""
    if not config.APP_PASSWORD:
        return {"ok": True, "required": False}
    if payload.get("password") == config.APP_PASSWORD:
        return {"ok": True, "required": True}
    raise HTTPException(401, "wrong password")


@app.get("/api/styles")
def list_styles() -> dict:
    return config.load_style_presets()


@app.get("/api/themes")
def list_themes() -> dict:
    p = config.PROMPTS_DIR / "themes.json"
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/music")
def list_music() -> list[str]:
    return sorted(p.name for p in config.MUSIC_DIR.glob("*") if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a"})


@app.get("/api/projects")
def list_projects() -> list[dict]:
    out = []
    for d in sorted(config.PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        st = _load_state(d.name)
        out.append({"slug": d.name, "title": st.get("title", d.name), "stage": st.get("stage", "unknown")})
    return out


@app.post("/api/ideas")
def make_ideas(payload: dict) -> dict:
    style = payload.get("style", "fruit_head")
    theme = (payload.get("theme") or "").strip() or None
    theme_hint = (payload.get("theme_hint") or "").strip() or None
    runtime = int(payload.get("runtime_seconds", 25))
    scene_count = int(payload.get("scene_count", 8))
    ideas = story.generate_ideas(
        style_key=style,
        theme=theme,
        theme_hint=theme_hint,
        runtime_seconds=runtime,
        scene_count=scene_count,
    )
    return {"ideas": ideas, "style": style, "theme": theme, "runtime_seconds": runtime, "scene_count": scene_count}


@app.post("/api/scene_pack")
def make_scene_pack(payload: dict) -> dict:
    chosen = payload["idea"]
    style = payload.get("style", "fruit_head")
    runtime = int(payload.get("runtime_seconds", 25))
    scene_count = int(payload.get("scene_count", 8))
    pack = scene_pack.generate_scene_pack(
        chosen, style_key=style, runtime_seconds=runtime, scene_count=scene_count,
    )
    slug = config.slugify(pack["title"])
    proj = config.project_dir(slug)
    scene_pack.save_scene_pack(pack, proj)
    state = {
        "slug": slug,
        "title": pack["title"],
        "logline": pack.get("logline", ""),
        "style": style,
        "scene_count": scene_count,
        "stage": "scene_pack",
        "videos_done": [],
    }
    _save_state(slug, state)
    return {"slug": slug, "pack": pack, "state": state}


def _images_worker(slug: str) -> None:
    proj = config.project_dir(slug)
    pack = json.loads((proj / "scene_pack.json").read_text(encoding="utf-8"))
    try:
        _job_set(slug, stage="images", progress=0, total=len(pack["scenes"]), status="starting")

        def progress(i: int, n: int, status: str) -> None:
            _job_set(slug, stage="images", progress=i, total=n, status=status)

        images.generate_all_images(pack, proj, progress=progress)
        _job_set(slug, stage="images", status="done", error=None)
        state = _load_state(slug)
        state["stage"] = "videos"
        _save_state(slug, state)
    except Exception as e:
        _job_set(slug, stage="images", status="error", error=str(e))


@app.post("/api/images/start")
def start_images(payload: dict) -> dict:
    slug = payload["slug"]
    threading.Thread(target=_images_worker, args=(slug,), daemon=True).start()
    return {"started": True, "slug": slug}


@app.get("/api/job/{slug}")
def job_status(slug: str) -> dict:
    return _job_get(slug)


@app.get("/api/scene_pack/{slug}")
def get_scene_pack(slug: str) -> dict:
    proj = config.project_dir(slug)
    pack_path = proj / "scene_pack.json"
    if not pack_path.exists():
        raise HTTPException(404, "Scene pack not found")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    state = _load_state(slug)
    n = int(pack.get("scene_count") or state.get("scene_count") or len(pack.get("scenes") or []) or 8)
    img_paths = [
        f"/files/{slug}/images/scene_{i}.png" if (proj / "images" / f"scene_{i}.png").exists() else None
        for i in range(1, n + 1)
    ]
    vid_paths = [
        f"/files/{slug}/videos/scene_{i}.mp4" if (proj / "videos" / f"scene_{i}.mp4").exists() else None
        for i in range(1, n + 1)
    ]
    # Add the ready-to-paste combined Veo prompt for each scene
    for s in pack["scenes"]:
        s["combined_veo_prompt"] = scene_pack.combined_video_prompt(s)
    return {
        "slug": slug, "pack": pack, "state": state,
        "images": img_paths, "videos": vid_paths,
    }


@app.get("/files/{slug}/{kind}/{name}")
def serve_file(slug: str, kind: str, name: str) -> FileResponse:
    if kind not in {"images", "videos"} or "/" in name or "\\" in name:
        raise HTTPException(400, "Bad path")
    p = config.PROJECTS_DIR / slug / kind / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/files/{slug}/final.mp4")
def serve_final(slug: str) -> FileResponse:
    p = config.PROJECTS_DIR / slug / "final.mp4"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/download_zip/{slug}")
def download_zip(slug: str, kind: str = "images") -> StreamingResponse:
    """Bundle all images (or videos) for a project into a single zip download."""
    if kind not in {"images", "videos"}:
        raise HTTPException(400, "kind must be images or videos")
    folder = config.PROJECTS_DIR / slug / kind
    if not folder.exists():
        raise HTTPException(404, f"No {kind} folder for {slug}")

    buf = io_mod.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(folder.glob("*")):
            if f.is_file():
                zf.write(f, arcname=f.name)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={slug}-{kind}.zip"
        },
    )


@app.post("/api/open_folder")
def open_folder(payload: dict) -> dict:
    """Open the project folder in Windows Explorer / Finder / xdg-open."""
    slug = payload["slug"]
    proj = config.PROJECTS_DIR / slug
    if not proj.exists():
        raise HTTPException(404)
    try:
        if sys.platform == "win32":
            os.startfile(str(proj))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(proj)])
        else:
            subprocess.Popen(["xdg-open", str(proj)])
        return {"ok": True, "path": str(proj)}
    except Exception as e:
        raise HTTPException(500, f"Could not open folder: {e}")


@app.post("/api/upload_music")
async def upload_music(file: UploadFile = File(...)) -> dict:
    """Drop an MP3 / WAV / M4A into library/music/ for use as background track."""
    name = (file.filename or "track").replace("/", "_").replace("\\", "_")
    if not name.lower().endswith((".mp3", ".wav", ".m4a")):
        raise HTTPException(400, "Only .mp3, .wav, or .m4a accepted")
    out = config.MUSIC_DIR / name
    with out.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "filename": out.name}


@app.get("/api/music/{name}")
def music_file(name: str) -> FileResponse:
    """Serve a music file for in-browser preview."""
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400)
    p = config.MUSIC_DIR / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/upload_video")
async def upload_video(slug: str = Form(...), scene: int = Form(...), file: UploadFile = File(...)) -> dict:
    state = _load_state(slug)
    expected = int(state.get("scene_count", 8))
    if scene < 1 or scene > expected:
        raise HTTPException(400, f"scene must be 1..{expected}")
    proj = config.project_dir(slug)
    out = proj / "videos" / f"scene_{scene}.mp4"
    with out.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    done = set(state.get("videos_done", []))
    done.add(scene)
    state["videos_done"] = sorted(done)
    if len(done) == expected:
        state["stage"] = "ready_to_assemble"
    _save_state(slug, state)
    return {"ok": True, "videos_done": state["videos_done"], "scene_count": expected}


def _assemble_worker(slug: str, music_filename: str | None) -> None:
    proj = config.project_dir(slug)
    try:
        state = _load_state(slug)
        n = int(state.get("scene_count", 8))
        _job_set(slug, stage="assemble", progress=0, total=3, status="stitching + transcribing")
        clips = [proj / "videos" / f"scene_{i}.mp4" for i in range(1, n + 1)]
        music = (config.MUSIC_DIR / music_filename) if music_filename else None
        if music and not music.exists():
            raise FileNotFoundError(music)

        _job_set(slug, stage="assemble", progress=1, total=3, status="building captions + final mp4")
        out = assemble.assemble_with_captions(clips, proj, music_path=music)

        _job_set(slug, stage="assemble", progress=2, total=3, status="generating metadata")
        pack = json.loads((proj / "scene_pack.json").read_text(encoding="utf-8"))
        meta = metadata.generate_metadata(pack)
        metadata.save_metadata(meta, proj)

        state = _load_state(slug)
        state["stage"] = "done"
        state["final_path"] = str(out.relative_to(config.PROJECTS_DIR))
        _save_state(slug, state)
        _job_set(slug, stage="assemble", progress=3, total=3, status="done", error=None)
    except Exception as e:
        _job_set(slug, stage="assemble", status="error", error=str(e))


@app.post("/api/assemble")
def start_assemble(payload: dict) -> dict:
    slug = payload["slug"]
    music = payload.get("music")
    threading.Thread(target=_assemble_worker, args=(slug, music), daemon=True).start()
    return {"started": True}


@app.get("/api/metadata/{slug}")
def get_metadata(slug: str) -> dict:
    p = config.PROJECTS_DIR / slug / "metadata.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
