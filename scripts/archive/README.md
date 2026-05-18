# scripts/archive — obsolete tooling kept for historical context

Scripts here are no longer referenced by the active pipeline. **Don't run them as-is — they're snapshots, not maintained code.** Git history preserves their full evolution.

## Pre-ElevenLabs narration (macOS `say` era)

| File | What it did | Replaced by |
|---|---|---|
| `make_audio.sh` | Generated narration via macOS `say` (one case) | `scripts/make_audio_elevenlabs.py --case <id>` |
| `make_audio_batch.sh` | Same, batch across cases 02-06 | Same |

macOS `say` had no alignment data for karaoke captions and felt robotic.

## Pre-Phase-1 exploratory tools (May 18 archive)

| File | What it did | Why archived |
|---|---|---|
| `research_games.py` | One-off Steam scraper for picking GG candidates | Cron uses inline Python in SKILL.md STEP 2; this script not called |
| `research_top_channels.py` | Pre-Phase-1 competitive analysis | Findings folded into `docs/RETENTION_PLAYBOOK.md` and `docs/AI_STORIES_PLAYBOOK.md` |
| `suggest_improvements.py` | Analytics-output explorer | Superseded by `analyze_performance.py --break-even` (v2) |
| `quality_loop.py` | Pre-pipeline QA tool | Pipeline-internal QA now handled by `check_script_structure.py` + visual gate in routine |

If any of these become useful again, copy back to `scripts/` and refactor against current code.
