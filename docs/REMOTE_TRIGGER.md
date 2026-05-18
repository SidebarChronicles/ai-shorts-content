# Remote trigger — kicking off the pipeline from your phone

The Claude Code routine `daily-shorts-pipeline` fires three times per day on the Mac (8:07 AM / 1:07 PM / 6:07 PM local). Each fire pulls the latest from GitHub before doing anything else — so anything committed to `game_queue/` from your phone lands in the next run.

## To trigger an ad-hoc run

1. **From GitHub mobile (or the GitHub web app):**
   - Navigate to [game_queue/](../game_queue/) in the repo
   - Tap "Add file" → "Create new file"
   - Name it `GG_NN_<slug>.md` where `NN` is the next number and `<slug>` is the game name lowercased with underscores (e.g. `GG_03_helldivers3`)
   - **Slug constraint:** must match `^[A-Za-z0-9_]+$` — no spaces, hyphens, or punctuation. The pipeline rejects unsafe IDs.

2. **Minimum fields** (the routine fills the rest via web search):
   ```markdown
   # GG_NN_<slug> — <Game Title>

   **Status:** QUEUED
   **YouTube Trailer URL:** https://www.youtube.com/watch?v=...

   ## Hook
   <optional — leave blank and the routine will research it>
   ```

3. **Commit.** The routine on your Mac picks it up at the next fire window — ≤5 hours.

## Local vs remote trigger

| Aspect | Local (daily fire) | Remote (ad-hoc via GitHub) |
|---|---|---|
| Who initiates | Cron fires automatically | You commit a queue entry from GitHub mobile |
| Where it runs | Mac (Claude Code app open) | Mac (same Claude Code app, same routine) |
| Trigger latency | 24h cycle | ≤5h (next 8 AM / 1 PM / 6 PM fire) |
| Requires Anthropic API | No | No |
| Routine | `daily-shorts-pipeline` | `daily-shorts-pipeline` (same routine, picks up the new entry) |
| Cost | $0 (Claude Code subscription) | $0 (same) |

## Failure handling

The pipeline is now hardened against partial failures:

- **Pipeline step fails** → retry counter bumps, status resets to QUEUED. After 3 consecutive failures, status moves to `BLOCKED` for human review.
- **Upload crashes mid-way** → an orphan marker (`_uploading.<case>.json`) is left in `output/game_videos/`. Next run will refuse to upload that case until a human checks YouTube Studio and either:
  - Adds the entry to `_posted.json` manually and deletes the marker (if video is live), OR
  - Just deletes the marker (if video isn't on YouTube)
- **OAuth token expires** → clear error message tells you to re-run `python3 scripts/youtube_oauth_setup.py`.
- **Steam API returns 5xx** → 3 retries with exponential backoff before giving up.

## To pause the routine

In Claude Code desktop app → Scheduled → `daily-shorts-pipeline` → Disable.
