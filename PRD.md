# AI Viral Shorts Generator — PRD

> Local-first automation tool that takes a story idea and produces a finished, captioned, vertical short-form video in the "Pixar 3D object-head character drama" style. Free-tier first, paid-API later.

---

## 1. Overview

A Python CLI + lightweight local web UI that automates every step of the viral-AI-reel pipeline that *can* be automated for free, and makes the steps that *can't* (Google Flow's web UI, Gemini's image generator UI) as fast and frictionless as possible.

End state of Phase 1: a session that today takes ~2 hours of copy-paste should take ~20 minutes of guided clicks plus the unavoidable Veo render waits.

---

## 2. Problem

Producing one viral 30-second AI character video today requires:
- Hand-composing a ~2000-word master prompt
- Pasting it into Gemini, then copy-pasting 8 image prompts one by one
- Pasting each image + animation + voice prompt into Google Flow one at a time
- Downloading, naming, and organizing 16 files (8 images + 8 videos)
- Manually stitching in CapCut, balancing audio, generating captions, picking music, timing it

Result: 1.5–3 hours per video. Repetitive, error-prone, and the bottleneck for scaling to multiple videos per day.

No commercial SaaS does the full loop for this style. Closest tools (Crayo, AutoShorts, Revid, Pictory) only produce stock-footage-with-voiceover shorts, not multi-scene character drama. Real gap.

---

## 3. Goal

**Primary**: Cut active human time per video from ~2 hr to ≤ 20 min while staying on free tools.

**Secondary**: Build the pipeline as a clean DAG so that when budget allows, the manual paste steps swap directly to Veo/Gemini APIs and the same tool becomes fully unattended → ready to wrap as a SaaS.

---

## 4. Target Users (priority order)

1. **You (Kfir)** — primary operator, full focus, posting from a fresh account.
2. (Phase 3) **Fiverr clients** — pay $25–50 for a custom one-off reel.
3. (Phase 4) **SaaS subscribers** — pay $20–30/mo for N videos/month.

---

## 5. Scope — Phased

### Phase 0 — Manual baseline ✅
Already complete. One video shipped (`AI_video_1_ready/0506 (1).mp4`). Validates the pipeline works end-to-end.

### Phase 1 — Local CLI + UI (free tier) — **build now**
- Generate 10 story ideas via free Gemini API
- Generate full per-scene prompt pack for chosen story
- Guided UI: copy prompt → paste in Gemini/Flow → drop returned file → next
- Auto-stitch all 8 clips with ffmpeg
- Auto-caption with faster-whisper (word-level, burned-in styled subtitles)
- Background music mix at correct ratio (-20 dB music, +5 dB voices)
- Output: 1080×1920 mp4 ready for upload
- Auto-generate title, description, hashtags for posting

### Phase 2 — Content validation (parallel to Phase 1)
- Open fresh TikTok + Instagram accounts (kept separate from your personal account, as you noted)
- Post 5–10 videos over 2 weeks, measure views/follows/engagement
- List a $25/video Fiverr gig — see if 3 paying buyers materialize within 2 weeks
- Decision gate: continue to Phase 3 only if at least one of (>10K views on a video) OR (1 paying customer) hits

### Phase 3 — Paid-API full automation (only after Phase 2 traction)
- Replace manual Google Flow with Kie.ai Veo 3 Fast API (~$0.30 per 8s clip)
- Replace manual Gemini image gen with Nano Banana Pro batch API (~$0.067/image)
- Pipeline becomes unattended: type story → 10 min later → mp4
- Realistic cost: ~$1.50–$3.50 per finished video

### Phase 4 — SaaS wrap (only if Phase 3 economics work)
- Next.js + Supabase auth + Stripe
- Free hosting tiers (Vercel + Supabase free) until first 100 users
- Charge $20–30/mo for X videos/month

---

## 6. Features (Phase 1 detail)

### 6.1 Story generation
- Input: optional theme keyword (e.g. "office betrayal", "sibling rivalry") OR blank for AI-pick
- Output: 10 story ideas, user picks one
- Prompt template loaded from `prompts/master_prompt.md` — editable without touching code

### 6.2 Scene pack generation
- Input: chosen story
- Output: structured JSON with 8 scenes; per scene:
  - `image_prompt` — Pixar-style render description, full character details for cross-scene consistency
  - `animation_prompt` — motion + camera notes for Veo
  - `voiceover_script` — speaker name, emotion direction, dialogue
  - **Anti-music tag** prepended to every voiceover: `[Settings: Dry audio, isolated vocal track, strictly no background music, acapella, speech only]` (this is the prompt-engineering fix you discovered for the music-leakage issue on the last 2 scenes)
- Saved to `projects/<slug>/scene_pack.json` (machine) and `scene_pack.md` (human-readable, ready to copy)

### 6.3 Guided paste UI
- Local web page at `http://localhost:5173`, opens automatically when you start the tool
- Single-page flow:
  1. **Image stage**: shows scene 1's image prompt with big copy button + drop zone → drag returned PNG in → auto-renamed `scene_1.png` → advance to scene 2 → repeat for 8
  2. **Video stage**: per scene, shows image preview + concatenated (animation prompt + voiceover script) ready to one-paste into Flow → drop returned mp4 → advance
  3. **Assemble stage**: pick music from `library/music/` dropdown (or skip) → click "Generate"
- Progress bar across the top
- "Save & resume later" — state lives in `projects/<slug>/state.json`, can quit and pick up

### 6.4 Auto-assembly
- ffmpeg concat with optional 0.3s crossfade transitions between scenes
- faster-whisper extracts word-level timestamps from the assembled audio
- Burned-in subtitles via ffmpeg `drawtext` or `subtitles` filter — large white text, black outline, lower-third position (matches the viral-reel aesthetic you saw)
- Audio mix: dialogue track at original volume +5 dB, music at -20 dB, optional sidechain ducking so music dips automatically when dialogue plays
- Output: `projects/<slug>/final.mp4`, 1080×1920, H.264, ~30s

### 6.5 Project organization
```
projects/
  the-analog-truth/
    scene_pack.json
    scene_pack.md
    state.json              # progress for resume
    images/
      scene_1.png ... scene_8.png
    videos/
      scene_1.mp4 ... scene_8.mp4
    music/
      kamin.mp3
    captions.srt
    final.mp4
    metadata.json           # title, description, hashtags
```

### 6.6 Posting helper
- Generate suggested TikTok/IG title, description, 8–12 hashtags via Gemini
- Saved to `metadata.json`, displayed in UI ready to copy

---

## 7. User Flow (Phase 1)

1. Run `python make_video.py` (or double-click `start.bat`)
2. Browser opens to local UI
3. Click "Generate story ideas" → pick one of 10
4. Wait ~30s for scene pack
5. **Image loop** (8×): copy prompt → paste into Gemini image gen tab → download → drop into UI
6. **Video loop** (8×): copy combined prompt → paste into Google Flow tab → download → drop into UI
7. Pick music → click "Assemble"
8. Wait ~2–5 min (ffmpeg + Whisper run locally on CPU)
9. `final.mp4` opens; metadata panel shows ready-to-paste title/description/hashtags
10. Upload manually to TikTok + IG

---

## 8. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Best ecosystem for AI + ffmpeg + Whisper |
| AI text/prompts | `google-generativeai` SDK, free Gemini API key | Free tier: 60 RPM, generous monthly tokens, sufficient for personal use |
| Local UI | FastAPI + single static HTML+vanilla JS page | Zero build step, no npm, runs on any Python install |
| Video stitching | `ffmpeg` (Windows binary, bundled or path-detected) | Free, fast, the standard |
| Captions | `faster-whisper` (CPU `tiny.en` or `base.en`) | Free, local, no API needed; word-level timestamps |
| Audio mix | ffmpeg `amix` + `sidechaincompress` filters | Built into ffmpeg, no extra deps |
| Storage | Local filesystem + SQLite for project index | Zero hosting cost |
| Hosting | None — runs on your Windows machine | Free |
| **Phase 3 add-ons** | Kie.ai Veo 3 Fast, Nano Banana Pro batch | Cheapest credible video + image APIs |
| **Phase 4 add-ons** | Next.js, Supabase free tier, Vercel free tier, Stripe | Standard SaaS starter, free until ~100 users |

---

## 9. Success Metrics

| Phase | Metric | Target |
|---|---|---|
| 1 | Active human time per video | ≤ 20 min (excluding Veo render waits) |
| 1 | Time from "click start" to first finished mp4 (end-to-end) | ≤ 90 min |
| 2 | Engagement | ≥ 1 video > 10K views in 14 days |
| 2 | Validation | ≥ 1 paying Fiverr customer in 14 days |
| 3 | Cost per fully-unattended video | < $3 |
| 4 | First paying SaaS subscriber | within 30 days of launch |

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Google Flow free 1000 credits run out | Plan: switch to Kie.ai Veo 3 Fast API in Phase 3. Tool already has the abstraction. |
| Character drift across 8 scenes | Phase 1: pass Scene 1's PNG back as a reference image when generating Scenes 2–8 (Gemini image gen supports image inputs). Phase 3: same trick via Nano Banana Pro reference parameter. |
| TikTok/IG demoting AI-slop accounts (e.g. @ai.cinema021 was mass-reported) | Post moderate cadence (3–5/day, not 30+). Vary character styles. Don't watermark "AI generated" anywhere. |
| Free Gemini API rate limits | Cache scene packs, batch text generation, fall back to manual paste if hit |
| Browser-automating Google Flow violates TOS | Don't do it. Manual paste is the safe path. |
| Over-investment before validation | Phase 2 gate: don't build paid-API or SaaS code until either traction signal hits |

---

## 11. Out of Scope (for now)

- Mobile app
- Multi-user accounts (until Phase 4)
- Custom-trained character models / LoRAs
- Languages other than English
- Auto-posting to TikTok/IG (their APIs are restrictive and risk bans; manual upload is fine and fast)
- Trend scraping / autonomous topic discovery (could be a Phase 5 agent layer)

---

## 12. Open Questions Before Code

1. **Master prompt source of truth**: do you want me to extract the master prompt you reverse-engineered from the YouTube video into `prompts/master_prompt.md` exactly as-is, or refine it (e.g. make character-style configurable so you can swap "fruit-head" / "retro-tech-head" / "kitchen-appliance-head" with one variable)?
2. **Music library**: where do you want to source background tracks? CapCut has a built-in royalty-free library; for our tool we'd need MP3s in `library/music/`. I can scaffold the folder with a placeholder + instructions, you drop tracks in.
3. **Subtitle style**: the viral-reel default (big white centered text, word-by-word highlight) vs. a static lower-third caption — preference?
4. **Posting account naming**: have you decided on the new TikTok/IG handle yet? If yes, I'll wire the `metadata.json` to address them.

---

## 13. Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-07 | Free-tier-only for Phase 1 | User constraint; defer paid APIs until traction validates |
| 2026-05-07 | Deterministic pipeline, not multi-agent supervisor | Fixed DAG, clear I/O shapes; agents add cost+nondeterminism for zero benefit |
| 2026-05-07 | Python + FastAPI + vanilla JS, no React | Avoid build step; user doesn't care about stack; minimum dependencies |
| 2026-05-07 | Local-only Phase 1, no cloud hosting | Free; faster iteration; defers SaaS infrastructure decisions |
| 2026-05-07 | Manual paste stays for Google Flow | Browser automation violates TOS; risks account ban |
