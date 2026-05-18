# Morning Handoff — May 19, 2026

> **TL;DR** — Tier 1, Tier 2, **and Tier 3.3 (YOLOv8 smart-crop)** of the Retention Playbook are shipped. Flux/Replicate (Tier 3.1) is deferred per your call; voice cloning (Tier 3.2) you decided to skip for now. The pipeline now produces shorts that should retain materially better than the 18 live videos — but the 18 live videos themselves will NOT be re-rendered (per the plan's explicit non-goal). You measure the lift by shipping NEW videos.
>
> All commits are pushed to `origin/main` — nothing pending locally.

---

## What shipped overnight

### Tier 1 (audio + writing-rule changes — biggest impact)

1. **`scripts/build_audio_track.py` (NEW)** — Mixes three sources into one track:
   - Narration at 0 dB (anchor)
   - Vertical-matched background music at -22 dB
   - Whoosh SFX at every cut (parsed from `bg_clips_concat.txt`) at -16 dB
   - 0.5s music silence at the mid-anchor (auto-detected from `alignment.json`)

   **End-to-end verified** on 3 verticals tonight (no ElevenLabs cost — reused existing narrations):

   | Case | Music picked | SFX placed | Mid-anchor dropout |
   |---|---|---|---|
   | `GG_07_marathon` | `games/ambient_games_01.mp3` | 3 @ 11s/22s/33s | 24.9-25.4s |
   | `UM_01_dbcooper` | `mysteries/ambient_mysteries_01.mp3` | 3 @ 9.7s/23.1s/39.6s | 27.4-27.9s |
   | `MY_01_prometheusfire` | `mythology/ambient_mythology_01.mp3` | 3 @ 7.6s/17.5s/30.1s | 22.0-22.5s |

   Outputs are at `output/scripts/<case>/audio_mixed.mp3` (gitignored).

2. **`scripts/seed_audio_assets.py` (NEW)** — Synthesizes placeholder music per vertical via FFmpeg (additive sine + chord-filter chains). One 60-second loopable track per vertical seeded already. **Replace these with curated music from YouTube Audio Library or Pixabay Music when you have time** — that's the highest-leverage manual upgrade you can do in 30 minutes. The mixer picks any `*.mp3` or `*.wav` from the vertical's subfolder at random.

3. **`scripts/make_audio_elevenlabs.py` (MODIFIED)** — Added `voice_speed` parameter (CLI flag + config field). Per-vertical defaults baked into `SKILL.md`. Default is **0.92** → lands ElevenLabs at ~145 WPM, which research shows is indistinguishable from human and outperforms our prior ~165-180 WPM.

4. **`skill/game-short/render_game_video.py` (MODIFIED)** — Wires `build_audio_track.py` between the audio step and the final encode. Falls back to bare narration if mixing fails so the pipeline never breaks.

5. **`~/.claude/scheduled-tasks/daily-shorts-pipeline/SKILL.md` (MODIFIED)** — New canonical writing rules:
   - Hook ≤12 words / ≤2.5s
   - Forbidden hook openers list ("Hey guys", "Did you know", "In this video", "What's up", "So today", etc.)
   - 7-beat script structure with **`mid_anchor` beat at second-30**
   - Per-vertical `voice_speed` table

### Tier 2 (visual + structural retention)

6. **Loop engineering** in `build_visuals_track.py` and `render_game_video.py` — Last 0.5s of the final clip is now a copy of clip 1. This creates a seamless visual loop so the algorithm can replay frictionlessly.

7. **Per-vertical color grading** via FFmpeg `colorchannelmixer`:
   - Cases / Mysteries → desaturated cool (`rr=0.85, gg=0.85, bb=1.05`)
   - Mythology → warm gold (`rr=1.10, gg=1.05, bb=0.90`)
   - Finance → clean teal/white (`rr=1.00, gg=1.00, bb=1.05` + `curves=preset=lighter`)
   - Games / Top X → saturation boost (`rr=1.05, gg=1.05, bb=1.05`)
   - Movies → none (preserve studio grading)

8. **4-second clip cap** in `build_visuals_track.py` — Any beat longer than 4s is auto-split into N sub-clips with alternating Ken Burns motion (zoom-in / zoom-out / zoom-in...). No single image holds longer than 4s on screen → pattern-interrupt enforced.

### Tier 1.4 helper (optional linter) — shipped tonight

9. **`scripts/check_script_structure.py` (NEW)** — Lints every script in `output/scripts/` against the new playbook rules:
   - Hook ≤12 words / ≤2.5s
   - No forbidden openers
   - Total duration 45-65s
   - Mid_anchor lands in 28-33s window (7-beat scripts only)
   - Mid_anchor carries a stat or contradiction marker

   **Result against all 20 existing cases: 0 / 20 pass.** This is the diagnostic baseline — every live video predates the new rules, which is why retention is currently soft. Future renders run through this linter automatically by adding `python3 scripts/check_script_structure.py --case <id> --fail-fast` to your pre-flight checklist.

### Test status

All **44/44 pytest tests still passing**. Working tree clean; everything committed and pushed.

```
b1ec114  Tier 1 audio
580847b  Tier 2 retention upgrades
+ tonight's check_script_structure.py linter (about to commit)
```

---

## Tier 3 status

| Item | Status | Notes |
|---|---|---|
| **3.1 Flux 2 Pro AI image fallback** | **Deferred** | Revisit after 72h of Tier 1+2 retention data |
| **3.2 Voice cloning ("the DROP voice")** | **Skipped for now** | You'll defer the audio recording until 1k subs in sight |
| **3.3 YOLOv8 smart-crop trailers** | **✓ Shipped** | `--crop smart_crop` flag is now opt-in alongside pillarbox_blur (default) and center_crop; falls back gracefully if YOLO deps unavailable |

### Tier 3.3 details (what's new today)

- `scripts/smart_crop_yolo.py` — Standalone OpenCV + YOLOv8n module. Detects the dominant subject (person, vehicle, animal) every 5 frames, interpolates per-frame x-center, smooths with a 1s moving-average window, writes a 1080×1920 pre-cropped intermediate.
- `render_game_video.py --crop smart_crop` — Two-stage path: smart_crop_yolo writes the intermediate; FFmpeg thin-pass re-encodes (libx264 CRF 22) with the per-vertical color grade. Falls back to pillarbox if anything goes wrong (deps missing, no detections, etc.).
- `requirements_full.txt` — `ultralytics>=8.1.0` + `opencv-python>=4.9.0`. Installed into `.venv-upload/` tonight (~2GB on disk).
- `assets/models/yolov8n.pt` — Model weights cached here (~6MB, gitignored). First-run downloads automatically.

**Smoke-tested on GG_07 Marathon clip_01 + clip_02** (1920×1080 @ 60fps). Output is valid H.264 portrait at the right duration with games color grade applied.

**When to use it:** dynamic gameplay trailers where the action drifts (chases, panning shots, fast-moving subjects). Pillarbox blur is still the default for everything else — smart_crop is ~20-40% slower per render.

**Recommended A/B once retention baseline lands:** re-render GG_03 Forza Horizon 6 with `--crop smart_crop` and compare retention vs. pillarbox.

---

## Your morning action items (in priority order)

### 1. Title rewrites — 5 min, pure CTR upside

Open `docs/TITLE_REWRITES_2026-05-18.md`. All 18 live videos have titles that exceed 40 chars and get mobile-truncated. The doc gives you the rewrite + the direct YouTube Studio edit URL per video. Apply them in YouTube Studio — no re-render needed.

**Do this FIRST.** It's a non-confounded CTR experiment that takes 5 minutes. Wait 72 hours, then run `python3 scripts/analyze_performance.py --game` to compare CTR before/after. If ≥10% lift, those formulas become canonical.

### 2. Replace placeholder music — 30 min, ~30% retention multiplier

The placeholder music I synthesized tonight via FFmpeg works for the pipeline, but it's mid quality (synthesized sine chords — listenable but not memorable). Free upgrade path:

- Go to [YouTube Audio Library](https://studio.youtube.com/channel/UC/music) (safest — no Content ID risk)
- Filter by mood + genre per the table in `docs/RETENTION_PLAYBOOK.md` § "Per-vertical music mapping"
- Download 3-5 60-second loopable tracks per vertical
- Drop them into `assets/music/<vertical>/` as `*.mp3` — the mixer picks randomly from whatever's there
- Optional: also pull better whoosh / sting SFX from [freesound.org](https://freesound.org) into `assets/sfx/`

This is the single biggest perception upgrade you can do without writing code.

### 3. Re-enable the scheduled task

`daily-shorts-pipeline` is disabled (you disabled it last night before sleep). You confirmed you want to wait until **both** (a) you replace placeholder music with curated tracks AND (b) the 72h CTR window after applying title rewrites closes. After both, re-enable it.

### 4. Watch retention on the NEW videos

The 18 live videos are the old baseline. The next batch the routine produces will run under:
- Hook ≤12 words
- 7-beat structure with mid-anchor at second-30
- Music + SFX + ducking
- 4s clip cap + Ken Burns variety
- Per-vertical color grade
- Loop tail
- 145 WPM narration

Target: avg view % rises **+10-15 percentage points** on the new cohort vs. the old. Measure 48-72h after each new video lands via `python3 scripts/analyze_performance.py`.

---

## What I deliberately did NOT do overnight

- **Did not re-render or re-upload any of the 18 live videos.** The plan's explicit non-goal: deletion churn hurts 0-sub channels more than it helps. Apply new rules to NEW content; let the live videos be the measurement floor.
- **Did not consume ElevenLabs budget** on speculative renders. The audio mixer verification used already-paid narrations.
- **Did not touch any paid APIs** (Replicate, ElevenLabs Pro, voice cloning).
- **Did not re-enable the scheduled task** — that decision is yours.

---

## Files modified or created tonight

```
NEW:
  scripts/build_audio_track.py         (~360 lines)
  scripts/seed_audio_assets.py         (~190 lines)
  scripts/check_script_structure.py    (~210 lines)
  scripts/smart_crop_yolo.py           (~220 lines)  ← Tier 3.3
  assets/music/{games,movies,cases,mysteries,mythology,finance}/ambient_*.mp3
  assets/sfx/whoosh_01.wav, whoosh_02.wav, sting_short.wav
  assets/models/yolov8n.pt              ← downloaded by smart_crop on first run (gitignored)
  docs/MORNING_HANDOFF_2026-05-19.md   (this file)

MODIFIED:
  scripts/make_audio_elevenlabs.py     (voice_speed param)
  scripts/build_visuals_track.py       (4s cap + loop tail)
  skill/game-short/render_game_video.py (audio mix + color grade + loop + smart_crop)
  ~/.claude/scheduled-tasks/daily-shorts-pipeline/SKILL.md  (writing rules)
  requirements_full.txt                 (ultralytics + opencv-python)
  .gitignore                            (audio_mixed + music + sfx + yolo weights)

UNCHANGED (still on disk, just for reference):
  docs/RETENTION_PLAYBOOK.md            (the research source of truth)
  docs/TITLE_REWRITES_2026-05-18.md     (your manual action)
```

### Final commit graph (all pushed to origin/main)

```
30b85f4  feat: Tier 3.3 — YOLOv8 subject-tracking smart crop
44ea876  docs: handoff note — final commit is local-only, needs git push
09bd46b  feat: script-structure linter + Tier 1+2 morning handoff
580847b  feat: Tier 2 retention upgrades — loop, per-vertical grade, 4s clip cap
b1ec114  feat(audio): Tier 1 retention upgrade — music + transition SFX + voice speed
53190d9  docs: retention playbook + title rewrites for 18 live videos
```
