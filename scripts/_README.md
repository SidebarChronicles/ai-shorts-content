# scripts/ layout

One-pager describing what each script does and how they relate. See individual file docstrings for full usage.

## The /morning workflow chain

Invoke via slash commands (`.claude/commands/*.md`). Each command shells to one of these:

| Step | Script | Slash command | Purpose |
|---|---|---|---|
| 0 | `morning_cleanup.py` | `/cleanup` | Archive stale picks/reports, prune leaked temp files |
| 1 | `analyze_performance.py` | `/analytics` | Pull YouTube Analytics, write report |
| 2a | `suggest_tweaks.py` | `/suggest-tweaks` | Compute per-voice/sub-genre median AVP, write daily tweaks file |
| 2b | `pick_today.py` | `/pick-today` | Rank queue + apply tweaks skew, output picks_YYYY-MM-DD.json |
| 3 | `render_story.py` | `/render-batch` | Chain the 11-step render pipeline per case (the missing orchestrator) |
| 4 | `schedule_uploads.py` | `/schedule-uploads` | TikTok via PostFast (immediate) + YouTube scheduled at prime slots |
| 5 | `research_reddit_stories.py` | `/research-stories` | Top up the queue from r/nosleep + r/AITA + r/letsnotmeet + 3 more |

`/morning` is the top-level orchestrator at `.claude/commands/morning.md` that chains all 6.

## Per-render building blocks (called by render_story.py)

These are the 11 steps the SY_09 manual flow established. `render_story.py` is the only thing that should call them in sequence — but each is independently invocable for debugging:

| Order | Script | What it produces |
|---|---|---|
| 1 | (validate config) | inline in render_story step_1 |
| 2 | `check_script_structure.py` | exits non-zero on broken script_config |
| 3 | `make_audio_elevenlabs.py` | `assets/audio/narration_<case>.mp3` + `.alignment.json` |
| 4 | `build_visuals_track.py` | `output/scripts/<case>/clips_source/`, `bg_clips_concat.txt`, `clips_manifest.json` |
| 5 | `build_sound_design.py` | `output/audio/<case>/sound_design.wav` |
| 6 | (alignment copy) | inline in render_story step_6 |
| 7 | (config alias add) | inline in render_story step_7 |
| 8 | `build_karaoke_filter.py` + `build_top_title_filter.py` | `karaoke.filter` + `top_title.filter` |
| 9 | `skill/game-short/render_game_video.py` | `hook_overlay.filter`, encode command |
| 10 | (audio mix override) | inline in render_story step_10 — overrides renderer's audio_mixed |
| 11 | (final ffmpeg) | `output/story_videos/<case>.mp4` |
| 12 | `story_orchestrator.py --mark-status` | flips queue stub to RENDERED |

## Per-vertical orchestrators

Each vertical (story / game / movie / mystery / mythology / topx / finance) has its own orchestrator. They share a common shape:

- `--list` — show all queue items with status
- `--next-queued [--subgenre]` — return next QUEUED case id
- `--mark-status <case> <STATUS>` — flip queue status
- `--subgenre-counts` — print per-sub-genre breakdown

These exist:

- `story_orchestrator.py` (S/R/H sub-genres; round-robin balancing)
- `game_orchestrator.py`
- `movie_orchestrator.py`
- `mystery_orchestrator.py`
- `mythology_orchestrator.py`
- `topx_orchestrator.py`
- `finance_orchestrator.py`

**Phase-2 refactor TODO:** unify into one `orchestrator.py --vertical <name>` that reads vertical-specific config from a YAML/JSON registry. Each existing file is ~150 LOC and they share ~80%. Not blocking; revisit when adding the 8th vertical.

## Writer prompts

Per-vertical writer prompts live with their skill:

- Story: `scripts/story_writer_prompt.md` — current location, not under skill/ because stories don't have a dedicated skill dir (they piggyback on game-short's renderer)
- TrueCrime: `skill/truecrime-short/writer_prompt.md`
- Games: `skill/game-short/writer_prompt.md`

## Upload + analytics

- `upload_to_youtube.py` — YouTube Data API v3 upload; `--publish-at` for scheduled publishing
- `post_via_scheduler.py` — TikTok + IG via PostFast (3-step signed-URL upload → social-posts API)
- `cross_post_status.py` — manual status tracker + TikTok-gate management (legacy; PostFast-aware now)
- `analyze_performance.py` — YouTube Analytics rollup
- `suggest_tweaks.py` — derives production hints from the analytics report

## Helpers

- `_env.py` — hardened .env loader (handles BOM, quotes, comments)
- `_atomic.py` — atomic_write_json + atomic_write_text (no torn writes on crash)

## Archive

- `scripts/archive/` — superseded scripts. `suggest_improvements.py` lived here (predecessor to suggest_tweaks.py); `quality_loop.py` likewise.
