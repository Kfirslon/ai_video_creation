---
title: AI Video Creation
emoji: 🎬
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# AI Viral Shorts Generator

Tool that takes a story idea and produces a finished, captioned, vertical short-form video in the "Pixar 3D object-head character drama" style. Free-tier first.

Runs locally **and** as a public website on Hugging Face Spaces (auto-deploys from this repo).

Full spec: see [PRD.md](PRD.md). Build plan: see `~/.claude/plans/tranquil-wishing-wadler.md`.

## What it does

1. You pick a character style (fruit-head, retro-tech-head, etc.) and theme.
2. Tool generates 10 story ideas via the free Gemini API. You pick one.
3. Tool generates an 8-scene script + image prompts + animation prompts + voiceover scripts.
4. Tool auto-generates the 8 character-consistent images via the free Gemini image API (Nano Banana).
5. You paste each (image + animation + voiceover) prompt into Google Flow / Veo and drop the returned mp4 back into the tool. (This step stays manual until Phase 3 — Veo has no free API.)
6. You pick a background music track from `library/music/`.
7. Tool stitches the 8 clips with ffmpeg, adds word-by-word burned-in captions via faster-whisper, mixes audio (dialogue +5 dB, music -20 dB with auto-ducking), and outputs `final.mp4` ready for TikTok/IG.
8. Tool generates a suggested title, description, and hashtags.

Active human time per video: target ≤ 20 minutes (excluding Veo render waits).

## Quick start

### Prerequisites (one-time)

1. **Python 3.11+** — check with `python --version`. If missing: install from python.org.
2. **ffmpeg** — needed for stitching/captions/audio mix.
   - Easiest: open PowerShell as admin, run `winget install ffmpeg`
   - Or download from gyan.dev/ffmpeg/builds, extract, add `bin/` to PATH.
   - Verify: `ffmpeg -version`
3. **Free Gemini API key** — generate at https://aistudio.google.com/app/apikey (no credit card needed). Required for image generation.
4. **Free Groq API key** (recommended) — https://console.groq.com/keys. Used for all text generation (story ideas, scene packs, post metadata). Saves your Gemini quota for what only Gemini can do — images. If you skip this, the tool falls back to Gemini for text too.

Add both keys to `.env`:
```
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

### Install + run

Double-click `start.bat`. On first run it will:
- Create a Python virtual environment in `.venv/`
- Install dependencies from `requirements.txt`
- Prompt for your Gemini API key and save to `.env`
- Launch the local web UI at http://localhost:5173

After first run: just double-click `start.bat` again — it skips the install and launches straight to the UI.

### Music library

Drop `.mp3` files into `library/music/`. They'll appear in the UI dropdown when assembling a video.

Suggested sources for free, viral-style tracks:
- TikTok's Commercial Music Library (login required, free for non-commercial)
- YouTube Audio Library
- Pixabay Music

Avoid copyrighted songs unless you have rights — TikTok will mute the video.

## Project structure

```
Ai video creation - idea/
├── PRD.md                    Full product spec
├── README.md                 This file
├── start.bat                 Double-click to launch
├── requirements.txt          Python deps
├── .env.example              Copy to .env, add your Gemini key
├── src/                      Pipeline + web UI source
│   ├── config.py
│   ├── text_client.py        Groq (primary) + Gemini (fallback) for text
│   ├── image_client.py       Gemini Nano Banana for images
│   ├── smoke.py              CLI test runner
│   ├── pipeline/             Story → scene_pack → images → captions → assemble
│   └── web/                  FastAPI app + static files
├── prompts/                  Master prompt template + style presets
├── library/music/            Drop your .mp3 background tracks here
└── projects/                 Auto-created folders, one per video
```

## CLI smoke test (skip the UI)

```
.venv\Scripts\activate
python -m src.smoke "office betrayal"
```

Generates a project under `projects/<slug>/` with story + scene pack + 8 images. Uses the existing fixture videos from `../AI videos/` to test the assembly stage end-to-end without you having to manually generate new Veo clips.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg: command not found` | Install ffmpeg (see Prerequisites) and restart your terminal |
| `429 RESOURCE_EXHAUSTED` from Gemini | You hit the free-tier rate limit. Wait 1 minute and rerun — the tool will resume from where it stopped. |
| Images come out wildly inconsistent across scenes | Make sure the Scene-1 reference image is being passed in (check `state.json`); regenerate with a different theme if a specific style isn't cooperating |
| Captions are out of sync | First run downloads the faster-whisper model (~150 MB). Subsequent runs are faster. If sync is off, check that the assembled audio plays correctly before captions are burned in. |
| Final mp4 has the music too loud over the dialogue | Edit the volume constants in `src/pipeline/assemble.py` — `MUSIC_DB` and `DIALOGUE_DB` |

## Deploy as a public website (Hugging Face Spaces)

The repo includes a `Dockerfile` and HF-Spaces YAML frontmatter at the top of this README — that's everything the platform needs to host this app for free.

One-time setup:

1. Go to https://huggingface.co/new-space — name it `ai-video-creation`, SDK = **Docker**, hardware = **CPU basic (free)**.
2. In the new Space → **Settings → Variables and secrets**, add:
   - `GEMINI_API_KEY` (required)
   - `GROQ_API_KEY` (optional — saves Gemini quota for image gen)
   - `APP_PASSWORD` (required for public deploys — gates access so strangers don't drain your free Gemini quota)
3. In **Settings → Repository → Link to a GitHub repo**, pick `Kfirslon/ai_video_creation`. Now every `git push` to this repo auto-deploys.

The Space will be live at `https://huggingface.co/spaces/Kfirslon/ai-video-creation` after the first build (~3 min).

> Note: Vercel was the obvious first choice but its free-tier serverless functions can't run `ffmpeg` (~80 MB binary) or `faster-whisper` (~145 MB model), and have a 10 s timeout vs. the minutes-long image-gen + assembly jobs this app needs. HF Spaces is purpose-built for Python apps with these dependencies.

## Roadmap

- **Phase 1 (this codebase)**: free-tier local tool. Manual Veo paste step.
- **Phase 2**: post 5–10 videos to fresh TikTok/IG, list a Fiverr gig at $25/video.
- **Phase 3**: swap manual Veo paste for Kie.ai Veo 3 Fast API ($0.30/8s clip). Pipeline becomes unattended.
- **Phase 4**: wrap as SaaS (Next.js + Supabase + Stripe).

Decision gates and full plan: see `~/.claude/plans/tranquil-wishing-wadler.md`.
