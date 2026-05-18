---
description: Schedule today's batch uploads — TikTok via PostFast (immediate) + YouTube --publish-at next prime slot (8:00/12:30/18:30/21:30 ET).
argument-hint: optional --platforms tt|yt|both (default both) | --dry-run
---

You are running inside Claude Code on Justin's Mac.

For each video in today's batch (output/daily/picks_YYYY-MM-DD.json), push to TikTok via PostFast and queue a YouTube scheduled upload at the next available prime slot.

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
TODAY=$(date -u +%F)
python scripts/schedule_uploads.py --batch "output/daily/picks_${TODAY}.json" $ARGUMENTS
```

After it runs, report back:
- Per-case TikTok post status (live URL when PostFast confirms posted, or fail reason)
- Per-case YouTube scheduled publish time (e.g. "Mon 2026-05-19 12:30 ET")
- Any cases skipped because their mp4 is missing (means /render-batch didn't run or failed for that case)

**TikTok timing:** PostFast doesn't expose scheduled-publish — posts go live ~30s after the API call. The "prime time" for TikTok is therefore *when you run `/morning`*, typically 8 AM ET.

**YouTube timing:** Spread across the next 4 prime slots starting at least 24h ahead (YouTube API requirement). With 4 picks/day this fills slots morning/lunch/dinner/pre-bed for the next 1–2 calendar days.

**Idempotency:** Both uploaders track posted state. Re-runs skip already-posted cases (no double-posts). Safe to re-invoke if a case fails mid-batch.

**If TikTok fails:** check `python scripts/post_via_scheduler.py --check-auth` — most failures are stale POSTFAST_API_KEY or expired channel connection.
**If YouTube fails:** check `token.json` exists and isn't revoked; re-run `python scripts/youtube_oauth_setup.py` if needed.
