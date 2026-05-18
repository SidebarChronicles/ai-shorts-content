---
description: Read latest analytics + emit suggested production tweaks for today (preferred voices, sub-genre skew, top-retaining hooks). Writes output/analytics/suggested_tweaks_YYYY-MM-DD.md.
argument-hint: optional --date YYYY-MM-DD  (default: today)
---

You are running inside Claude Code on Justin's Mac.

Read previous day's YouTube analytics + cross-post status, surface patterns, and emit a daily tweaks file that `/pick-today` consumes for ranking skews.

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/suggest_tweaks.py $ARGUMENTS
```

After it runs, report back:
- Path to the generated `suggested_tweaks_YYYY-MM-DD.md`
- Whether it has real data or wrote the no-data placeholder
- The single biggest recommendation (e.g. "skew toward horror, prefer Nicole voice")

**If no analytics report exists yet** (≤72h post-launch — current pre-launch state): the script writes a "no data yet — pick by hand" placeholder and exits cleanly. That's the expected behavior for the first ~3-7 days.

**Once data exists:** the file contains per-voice / per-sub-genre / per-hook-formula median AVP tables + the top-retaining hooks verbatim for the writer to study.

**Follow-up:** run `/pick-today` next — it auto-reads this file for ranking skews.
