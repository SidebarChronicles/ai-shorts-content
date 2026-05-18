# DROP Channel — Current Status & Key Context

> **For Claude (or any new contributor) starting fresh.** This is the single source of truth for what the channel is, what's running, what's decided, and what's still open. Read this first; the deeper docs are linked throughout.

Last updated: **May 18, 2026, 12:11 PM ET** (just before Phase 1 Day 1's 12:16 fire kicks off).

---

## TL;DR — the channel in 5 bullets

- **DROP** is a faceless, AI-narrated YouTube Shorts channel. 0 subscribers as of today (May 18). 18 live videos uploaded under the OLD format; the new format launched at 12:16 PM today.
- **7 verticals** rotate: Story (AI-narrative — newest), Games, Movies, Mythology, Mysteries, Top X, Finance. Cases (legacy true crime, 6 live) is paused during Phase 1.
- **Cadence:** 8 videos/day across 4 fires (`7 7,12,18,21 * * *` ET = 7:07 AM / 12:07 PM / 6:07 PM / 9:07 PM with ~9-min jitter).
- **Strategy:** 4-phase learning curve over 28 days — saturate, narrow, optimize, compound. Day 7 + Day 14 + Day 28 are mechanical decision points (median view %, sub conversion).
- **Goal:** YouTube Partner Program eligibility (500 subs + 3M Shorts views = Early Access; 1k + 10M = full).

---

## Infrastructure at a glance

| Layer | Tool | Notes |
|---|---|---|
| Narration | ElevenLabs (Creator tier, $22/mo, 100k chars) | Voices: Adam, Charlie, Callum, Brian, Daniel. Speed 0.88-0.95 per vertical. |
| Music | Incompetech (Kevin MacLeod, CC-BY 4.0) | 22 tracks across 6 vertical-themed folders in `assets/music/`. Attribution required in every description. |
| SFX | FFmpeg-synthesized whooshes | `assets/sfx/whoosh_0[12].wav` + `sting_short.wav`. Cap 5 per video, ≥4s apart. |
| Stock visuals | Pexels (primary) + Pixabay (fallback) | Free APIs. Keywords come from per-beat `keywords` in script_config.json. |
| AI visuals | **Flux 2 Pro** (stills, ~$0.03) + **Pixverse v4.5** (5s hero clips, ~$0.40) via Replicate | Story vertical is AI-first (Flux → Pexels → Pixabay). Other verticals stock-first with AI fallback. |
| Smart-crop | YOLOv8 (`ultralytics + opencv-python`) | Optional `--crop smart_crop` flag for trailer footage. Pillarbox blur is default. |
| Color grading | Per-vertical `colorchannelmixer` in FFmpeg | Cases/mysteries cool, mythology warm, finance teal, games saturated, movies untouched. |
| Karaoke captions | FFmpeg drawtext driven by ElevenLabs alignment.json | Word-by-word highlights. Poppins-Bold font. |
| Top-title overlay | FFmpeg drawtext | Persistent top-of-screen title; per-rank for Top X. |

---

## The 4-phase release strategy

**Phase 1 (Days 1–7) — Saturation.** All 7 verticals fire. Story is **priority** (`priority_until_count: 12`, both fire slots → story until 12 stories are in queue/rendered/delivered) — currently 6 queued, so the first ~3 fires are story-exclusive. After 12 hit, balanced rotation resumes.

**Phase 2 (Days 8–14) — Narrowing.** Drop verticals with median <30% avg view %. Keep ≥40%. Probation for 30-40% if sub-conversion ≥3/1k views.

**Phase 3 (Days 15–28) — Format optimization.** Single winning vertical. Test 2 hooks × 3 voices × 2 lengths = 12 cells × ~9-10 videos.

**Phase 4 (Day 29+) — Compound.** Ride winner + #2 from Phase 2. Apply for YPP when thresholds clear.

Detail: `docs/RELEASE_SCHEDULE.md`.

---

## The Story vertical (newest, May 18 launch)

Three sub-genres rotate inside the story vertical:

| Sub-genre | File pattern | Hook formula | Voice | Visual palette |
|---|---|---|---|---|
| Numbered survival/POV | `SY_NN_S_*` | "Day [N] of [scenario]. Today I [escalation]." | Charlie (energetic) | Muted earth tones, high contrast |
| Reddit dramatization | `SY_NN_R_*` | "AITA for [action]? My [relation] [outrageous thing]." | Brian (conversational) | Warm domestic, naturalistic |
| Horror micro-fiction | `SY_NN_H_*` | "[Mundane setup]. [Single wrong detail in 4-5 words]." | Daniel (slow, ominous) | Near-monochrome, deep shadows |

**Non-negotiable rules:**
- Reddit: **paraphrase, never copy verbatim.** Reddit posts are copyrighted by their authors. The "premise" field in queue entries is inspiration; Claude writes original prose for the script.
- Horror: **original micro-fiction only.** No Slenderman, SCP, Backrooms, or other established IP. Borrow tropes (haunted house, doppelganger) but the specific entity + setting must be new.
- Survival: same protagonist physical description across an arc's episodes. Include in every Flux prompt for visual continuity.

Detail: `docs/AI_STORIES_PLAYBOOK.md`.

---

## Pipeline flow (per video)

```
1. Queue entry              story_queue/SY_NN_*.md  (premise + hook angle)
2. Scaffold config          scripts/story_script_writer.py --case <id>
3. Claude writes 7 beats    script_config.json beats[].text + keywords
4. Lint                     scripts/check_script_structure.py --case <id> --fail-fast
5. Narration                scripts/make_audio_elevenlabs.py  → assets/audio/narration_<id>.mp3
6. Visuals                  scripts/build_visuals_track.py    → clips_source/*.mp4 + clips_manifest.json
                            (story vertical: AI-first — Flux + Pixverse hero shots)
7. Audio mix                scripts/build_audio_track.py      → audio_mixed.mp3
                            (narration 0dB + music -22dB + ≤5 SFX -16dB + 0.5s mid-anchor dropout)
8. Render                   skill/game-short/render_game_video.py
                            (karaoke + top-title + color grade + loop tail + final encode)
9. Move + describe          output/story_videos/<id>.mp4 + <id>.description.md
                            (description MUST include "AI narration" + "Kevin MacLeod CC-BY 4.0")
10. Mark RENDERED           scripts/story_orchestrator.py --mark-status <id> RENDERED
11. Upload (next fire)      scripts/upload_to_youtube.py --case <id> --videos-dir output/story_videos --category 24
```

---

## Key decisions made (and locked) by May 18

| Decision | Choice | Rationale |
|---|---|---|
| ElevenLabs tier | Creator ($22/mo) | 100k chars supports 8/day; Starter would've capped at ~3/day |
| Upload timing | Immediate, not peak-scheduled | Maximize signal velocity in Phase 1 |
| Phase 1 cadence | 8/day (4 fires × 2) | Creator budget headroom + better signal at 56 videos/week |
| Quality gate | Velocity-first | Linter pass = ship. Optimize from data, not pre-emption |
| AI image vendor | Flux 2 Pro via Replicate | $0.03/image, native 9:16, best price/quality |
| AI video vendor | Pixverse v4.5 via Replicate | 262k Replicate runs, $0.40/5s clip, 9:16 native. Pika doesn't exist on Replicate. |
| AI-first vs stock-first | AI-first for story only | Other verticals stay stock-first (cost discipline). Revisit at Day 7 if mythology/mysteries underperform. |
| Voice cloning (PVC) | Skipped for now | Defer until ≥1k subs |
| Smart-crop YOLOv8 | Installed, optional flag | Default stays pillarbox_blur. Use for fast-moving trailer footage. |
| Story priority bootstrap | `priority_mode: "exclusive"`, 12 stories | First ~3 fires are story-only, then balanced rotation |

---

## Files Claude should never modify without a strong reason

- `.env` — API tokens. Keep in `.gitignore`. Never log or echo.
- `client_secret.json` + `token.json` — YouTube OAuth credentials.
- `~/.claude/scheduled-tasks/daily-shorts-pipeline/SKILL.md` — the routine's brain. Self-modification is gated by the auto-mode classifier; needs explicit user authorization.
- `output/.channel_phase.json` — phase state. Auto-clears priority when `priority_until_count` is reached, but human approves all phase transitions (1→2, 2→3, 3→4).
- `output/_posted.json` and per-orchestrator `_posted.json` — YouTube upload state. Editing these can cause duplicate uploads.

---

## What's working (verified end-to-end as of 12:11 PM ET, May 18)

- ✅ Cron firing 4×/day, enabled
- ✅ Replicate API authenticated (`sidebarchronicles` account, ~$8 funded)
- ✅ Flux 2 Pro + Pixverse v4.5 smoke-tested with real generations
- ✅ Story orchestrator end-to-end: list / next-queued / sub-genre round-robin / total-count
- ✅ build_visuals_track auto-writes clips_manifest.json + clips_source/ (final pre-fire bug fixed at 12:08 PM)
- ✅ Renderer `already_portrait` path active for non-trailer verticals
- ✅ Anti-cartoon negative prompts in Flux + Pixverse
- ✅ Per-sub-genre music routing (SY_S/H → mysteries, SY_R → cases)
- ✅ Zoom-in consistency for story (no more in/out chaos within a beat)
- ✅ SFX cap (5 max, ≥4s apart)
- ✅ 44/44 pytest passing
- ✅ All commits pushed to `origin/main` (latest: `5d6f41f`)

## Known open issues / TODOs

1. **Mac sleep prevention** — fires only trigger when system is awake. User needs to run `caffeinate -d -i -m -s &` or use Amphetamine. Not a code issue but breaks the schedule if forgotten.
2. **Replicate token rotation** — initial token was pasted in chat; recommended rotation after smoke validation but user hasn't done it yet. Low urgency.
3. **No dedicated `horror` music folder** — both survival and horror sub-genres use `mysteries/` for now. Should pull 3-4 darker tracks (e.g., Incompetech "Lightless Dawn") and create `assets/music/horror/` after Day 7 if horror retains well.
4. **Story description auto-injection** — game_orchestrator.py auto-adds the music attribution; story videos rely on Claude (during the routine) manually adding it per SKILL.md STEP 4 instructions. Risk: Claude forgets. Could be automated.
5. **Linter false-negative risk** — `check_script_structure.py` is strict. If the writer trips it repeatedly, review `output/_blocked.log` and either loosen the linter or fix the writer.
6. **Pre-1k-subs YPP tooling** — `scripts/analyze_performance.py --ypp` computes thresholds but no auto-application logic. User applies manually when thresholds clear.

---

## Where to look for what

| Question | File |
|---|---|
| What's the release schedule + phase logic? | `docs/RELEASE_SCHEDULE.md` |
| What are the story sub-genres + rules? | `docs/AI_STORIES_PLAYBOOK.md` |
| Why is the pipeline designed this way? | `docs/RETENTION_PLAYBOOK.md` (research foundation, ~30 sources) |
| What's the music licensing? | `docs/MUSIC_ATTRIBUTION.md` |
| What's the routine's flow? | `~/.claude/scheduled-tasks/daily-shorts-pipeline/SKILL.md` |
| Current phase state? | `output/.channel_phase.json` |
| EL spend MTD? | `output/elevenlabs_usage.json` |
| Master plan + recent decisions? | `~/.claude/plans/ok-a-few-things-vast-sedgewick.md` |
| Pre-launch title rewrites? | `docs/TITLE_REWRITES_2026-05-18.md` |
| Compliance + monetization? | `docs/MONETIZATION.md` |
| Per-niche topic guidance? | `docs/NICHE_PLAYBOOK.md` |
| 10-video commit rule + KPI gates? | `docs/TESTING_PROTOCOL.md` |
| Old morning handoffs (historical)? | `docs/archive/` |

---

## How a fresh Claude session should orient

1. Read this file (you just did).
2. Skim `docs/AI_STORIES_PLAYBOOK.md` if working on story vertical.
3. Skim `docs/RELEASE_SCHEDULE.md` if working on schedule or routine logic.
4. Check `output/.channel_phase.json` for current state.
5. Check `git log --oneline -20` for the most recent direction.
6. **If working on the pipeline:** check with any other active session before touching `scripts/build_visuals_track.py`, `scripts/build_audio_track.py`, `scripts/replicate_*.py`, `scripts/story_*.py`, or `skill/game-short/render_game_video.py`. Other sessions may be editing in parallel.
7. **Always run pytest** after any code change: `.venv-upload/bin/pytest tests/ -q` (44/44 expected).
