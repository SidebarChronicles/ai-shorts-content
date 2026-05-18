---
description: Render the day's batch end-to-end via render_story.py. Reads picks from output/daily/picks_YYYY-MM-DD.json (from /pick-today). ~$1.50 per case in API spend.
argument-hint: optional --case SY_XX_X_slug (override batch) | --dry-run | --force | --from-step N
---

You are running inside Claude Code on Justin's Mac.

Render every case in today's batch (or a single case via `--case`). Chains the full 11-step pipeline: TTS → Flux/Pika → sound design → mix → captions → encode → mark RENDERED. Idempotent — re-runs skip steps whose outputs already exist.

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
TODAY=$(date -u +%F)
if [ -n "$ARGUMENTS" ]; then
  python scripts/render_story.py $ARGUMENTS
else
  python scripts/render_story.py --batch "output/daily/picks_${TODAY}.json"
fi
```

After it runs, report back:
- How many cases succeeded vs failed
- Per-case path to the final mp4 in `output/story_videos/`
- Estimated total spend (EL + Replicate rollup from script output)
- Any failed cases (with the step they died on)

**Budget guard:** Before any API calls, the script checks projected EL spend against `ELEVENLABS_MONTHLY_BUDGET`. If projected to exceed, exits 3 with no spend. Override with `--skip-budget-check` only when you've verified the projection.

**Batch abort behavior:** If case N fails, the remaining cases are NOT attempted (prevents burning $$ on broken pipeline state). Fix the issue + re-run — idempotent skips kick in for the cases that already succeeded.

**Common failure modes:**
- `writer hasn't filled all briefs/text` → Claude needs to fill beat texts + visual_brief + sound_brief per `scripts/story_writer_prompt.md` BEFORE `/render-batch` is run.
- `make_audio_elevenlabs failed` → check ELEVENLABS_API_KEY + monthly budget
- `build_visuals_track failed` → check REPLICATE_API_TOKEN + PEXELS_API_KEY
- `final encode failed` → typically a missing filter file; check `output/scripts/<case>/` artifacts

**Resume after a fix:** `python scripts/render_story.py --case SY_XX --from-step N` (skip the already-done steps).

**Follow-up:** run `/schedule-uploads` to push to TikTok + queue YouTube prime slots.
