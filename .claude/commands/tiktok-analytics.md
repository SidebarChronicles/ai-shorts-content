---
description: Pull TikTok analytics for cross-posted cases via PostFast and write a markdown report to output/analytics/. Use after videos have been live ~24h+.
argument-hint: optional --case <id> or --days <N>
---

You are running inside Claude Code on Justin's Mac.

Run the TikTok analytics fetcher. The optional argument `$ARGUMENTS` can be empty (pulls all TT-posted cases, 30-day window) or specify a case (`--case SY_01_S_lakecabin`) or a window (`--days 7`).

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python3 scripts/analyze_tiktok_performance.py $ARGUMENTS
```

After it runs, report back:
- How many tracked cases were matched to PostFast posts
- How many of those matched posts have populated metrics
- Path to the generated `.md` report (under `output/analytics/`)
- One-line summary of the channel rollup (total impressions, total likes) if metrics exist
- The strongest performer by impressions (if any)
- Any unmatched PostFast posts (could indicate manual posts or tracker drift)

**If it fails:**
- `POSTFAST_API_KEY missing` → confirm `.env` has the key; run `python3 scripts/post_via_scheduler.py --check-auth` to debug
- `HTTP 401` → PostFast key revoked or expired; regenerate in the PostFast dashboard
- `HTTP 403` on `/social-posts/analytics` → workspace may be on Starter tier without analytics access; check PostFast plan
- `No TT-posted cases in tracker` → expected if nothing has been cross-posted yet

**If it succeeds but every metric is empty:**
- Posts are too new — PostFast typically refreshes TT metrics every few hours, and TikTok itself can take ~24h to populate. Retry tomorrow.
- If still empty after 48h, this is a strong signal the PostFast plan tier doesn't include TT analytics — see `docs/TIKTOK_ANALYTICS.md` for next steps.

**Background:** see `docs/TIKTOK_ANALYTICS.md` for why PostFast (not the TikTok Display API) is the chosen source and what this report does NOT cover (retention %, follower count).
