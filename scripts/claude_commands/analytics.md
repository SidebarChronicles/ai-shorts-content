---
description: Pull YouTube Analytics for every posted TrueCrime Short and write a markdown report to output/analytics/. Use after videos have been live ~48-72h.
argument-hint: optional --case <id> or --days <N>
---

You are running inside Claude Code on Justin's Mac.

Run the analytics fetcher. The optional argument `$ARGUMENTS` can be empty (pulls all posted videos, 30-day window) or specify a case (`--case 04`) or a window (`--days 7`).

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/analyze_performance.py $ARGUMENTS
```

After it runs, report back:
- How many videos were analyzed
- Path to the generated `.md` report (under `output/analytics/`)
- One-line summary of the channel rollup (total views, net subs)
- The strongest and weakest performer by avg view %

**If it fails:**
- `No token.json` → tell Justin to re-run `python scripts/youtube_oauth_setup.py`
- `doesn't have the yt-analytics.readonly scope` → re-run OAuth setup; the updated SCOPES list will request the new scope on the consent screen
- `youtubeAnalyticsApiNotEnabled` → Justin needs to enable "YouTube Analytics API" in Google Cloud Console → APIs & Services → Library
- `No data yet` for individual videos → expected for videos published in the last 48 hours; remind Justin to retry in a couple days

**If it succeeds:**
- Suggest bringing the markdown report into Cowork for analysis ("Open the report in Cowork and ask Claude to suggest writer-prompt or visual-template tweaks based on the retention data")
- Highlight any videos with clearly weak hooks (sharp retention drop in first 10%) — those are candidates for re-upload under one of the alternate titles in `output/scripts/title_alternatives.md`
