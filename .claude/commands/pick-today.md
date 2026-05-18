---
description: Pick today's 4 story stubs to render. Ranks queue by mined_score + tweaks skew, sub-genre cap 3-of-4. Writes output/daily/picks_YYYY-MM-DD.json.
argument-hint: optional --count N (default 4) | --auto (no confirm prompt) | --dry-run
---

You are running inside Claude Code on Justin's Mac.

Rank the QUEUED stubs in `story_queue/` and select the day's picks for rendering. Interactive by default (prints picks, prompts `y` to write). Pass `--auto` for non-interactive use inside `/morning`.

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/pick_today.py $ARGUMENTS
```

After it runs, report back:
- The 4 picked case_ids with their composite scores + sub-genres
- Whether tweaks skews were applied (e.g. "preferred Nicole voice, +5 per match")
- Queue depth after the pick
- Path to the written picks file (or "dry-run, no file written")

**Ranking inputs:**
- Each stub's `Mined score: X/100` from `/research-stories` stub generator
- `output/analytics/suggested_tweaks_<today>.md` for sub-genre + voice skews
- Hard cap: ≤3 picks from any single sub-genre per day (prevents horror-only batches)

**If the queue is empty or below 4 picks:** the script picks what it can and prints a warning. Run `/research-stories --stub-top 5` to top up.

**Follow-up:** run `/render-batch` to actually produce the videos.
