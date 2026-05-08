"""Kie.ai Veo 3 client — image-to-video generation for auto-mode.

Kie.ai proxies Google's Veo models at lower per-second pricing than Vertex AI
direct. Pricing as of 2026-05: veo3_fast 720p ≈ $0.10/sec → $0.80 per 8s clip.

Reference: https://docs.kie.ai/veo3-api/generate-veo-3-video

Flow:
    1. POST /api/v1/veo/generate  with {prompt, imageUrls, model, aspect_ratio}
       -> returns {data: {taskId}}
    2. Poll GET /api/v1/veo/record-info?taskId=...
       -> returns {data: {status, videoUrl?}} until status terminal
    3. Download videoUrl bytes
"""
from __future__ import annotations

import time
import urllib.request
from typing import Optional

import httpx

from . import config


class KieAiError(RuntimeError):
    """Raised when Kie.ai returns an error or never finishes."""


def is_configured() -> bool:
    return bool(config.KIE_AI_API_KEY)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.KIE_AI_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def submit(prompt: str, image_url: str, aspect_ratio: str = "9:16") -> str:
    """Submit a generation job. Returns the taskId for polling.

    image_url MUST be publicly fetchable from Kie.ai's servers (not localhost).
    """
    if not is_configured():
        raise KieAiError("KIE_AI_API_KEY not set")
    body = {
        "prompt": prompt,
        "imageUrls": [image_url],
        "model": config.KIE_AI_MODEL,
        "aspect_ratio": aspect_ratio,
        "generationType": "REFERENCE_2_VIDEO",
        "enableTranslation": False,
    }
    url = f"{config.KIE_AI_BASE_URL}/api/v1/veo/generate"
    with httpx.Client(timeout=60) as client:
        r = client.post(url, headers=_headers(), json=body)
    if r.status_code >= 400:
        raise KieAiError(f"submit HTTP {r.status_code}: {r.text[:400]}")
    payload = r.json()
    if payload.get("code") not in (200, 0):
        raise KieAiError(f"submit returned code={payload.get('code')} msg={payload.get('msg')}")
    task_id = (payload.get("data") or {}).get("taskId")
    if not task_id:
        raise KieAiError(f"no taskId in response: {payload}")
    return task_id


def poll_until_done(task_id: str, timeout_secs: int = 600, interval_secs: int = 6) -> str:
    """Poll status. Returns the finished video URL. Raises if it errors or times out."""
    if not is_configured():
        raise KieAiError("KIE_AI_API_KEY not set")
    url = f"{config.KIE_AI_BASE_URL}/api/v1/veo/record-info"
    deadline = time.time() + timeout_secs
    last: dict = {}
    with httpx.Client(timeout=30) as client:
        while time.time() < deadline:
            r = client.get(url, headers=_headers(), params={"taskId": task_id})
            if r.status_code >= 400:
                raise KieAiError(f"poll HTTP {r.status_code}: {r.text[:400]}")
            payload = r.json()
            data = payload.get("data") or {}
            last = data
            status = (data.get("status") or "").lower()
            video_url = data.get("videoUrl") or data.get("video_url") or (data.get("response") or {}).get("videoUrl")
            if video_url:
                return video_url
            if status in {"failed", "error", "canceled"}:
                raise KieAiError(f"task {task_id} ended in {status}: {data}")
            time.sleep(interval_secs)
    raise KieAiError(f"timed out after {timeout_secs}s; last status payload: {last}")


def download_to(video_url: str, dst_path) -> None:
    """Stream the finished video to disk."""
    req = urllib.request.Request(video_url, headers={"User-Agent": "ai-video-creation/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst_path, "wb") as f:
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)


def generate_one(prompt: str, image_url: str, dst_path, aspect_ratio: str = "9:16") -> None:
    """End-to-end: submit, poll, download. Convenience wrapper."""
    task_id = submit(prompt, image_url, aspect_ratio=aspect_ratio)
    video_url = poll_until_done(task_id)
    download_to(video_url, dst_path)
