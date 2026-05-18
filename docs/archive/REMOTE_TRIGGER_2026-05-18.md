# Remote trigger — kicking off the pipeline from your phone

The Claude Code routine `daily-shorts-pipeline` fires **four times per day** on the Mac at peak YouTube Shorts windows: **7:07 AM, 12:07 PM, 6:07 PM, 9:07 PM local** (cron `7 7,12,18,21 * * *` with ~9-min jitter).

Each fire pulls the latest from GitHub before doing anything else — so anything committed to a queue directory from your phone lands in the next run.

## To trigger an ad-hoc run from your phone

1. **From GitHub mobile (or the GitHub web app):**
   - Pick the queue directory for the vertical you want to seed:
     - `game_queue/GG_NN_<slug>.md` — game trailer shorts
     - `movie_queue/MV_NN_<slug>.md` — movie trailer shorts
     - `mythology_queue/MY_NN_<slug>.md` — mythology shorts
     - `mystery_queue/UM_NN_<slug>.md` — unsolved mystery shorts
     - `topx_queue/TX_NN_<slug>.md` — Top X ranked-list shorts
     - `finance_queue/FN_NN_<slug>.md` — finance education shorts
     - `story_queue/SY_NN_<S|R|H>_<slug>.md` — AI narrative shorts (survival / Reddit / horror)
   - Tap "Add file" → "Create new file"
   - **Slug constraint:** must match `^[A-Za-z0-9_]+$` — no spaces, hyphens, or punctuation. The pipeline rejects unsafe IDs.

2. **Use the right template.** Each queue has a `<VERTICAL>_TEMPLATE.md` (e.g. `story_queue/SY_TEMPLATE.md`) showing the minimum required fields. The routine fills the rest via web search or LLM generation.

3. **Commit.** The routine on your Mac picks it up at the next fire window — ≤6 hours.

## Phase-aware production

The routine reads `output/.channel_phase.json` at fire time to decide which verticals get produced. During Phase 1 (saturation week):

- `priority_verticals` claims both fire slots until `priority_until_count` is hit (currently `story` at 12)
- After that, **balanced rotation** across all 7 verticals
- Day 7 → narrow to top 2-3
- Day 14 → lock the single winner
- Day 28 → compound the winner

See `docs/RELEASE_SCHEDULE.md` for the full strategy.

## Local vs remote trigger

| Aspect | Local (daily fire) | Remote (ad-hoc via GitHub) |
|---|---|---|
| Who initiates | Cron fires automatically | You commit a queue entry from GitHub mobile |
| Where it runs | Mac (Claude Code awake) | Mac (same Claude Code app, same routine) |
| Trigger latency | 6-hour cycle (4 fires/day) | ≤6h (next 7 AM / 12 PM / 6 PM / 9 PM fire) |
| Requires Anthropic API | No | No |
| Routine | `daily-shorts-pipeline` | `daily-shorts-pipeline` (same routine, picks up the new entry) |
| Cost | $0 (Claude Code subscription) | $0 (same) |

## Mac sleep — the critical gotcha

**The routine ONLY fires when the Mac is awake.** Scheduled tasks can't trigger through display sleep + system sleep.

Two mitigations (pick one):

1. **`caffeinate`** (free, instant) — open Terminal, run:
   ```bash
   caffeinate -d -i -m -s &
   ```
   Stays alive until reboot or `killall caffeinate`. No sudo needed.

2. **Amphetamine** (free, App Store) — friendlier UI; set a recurring session 7am-10pm daily to cover all 4 fire windows.

**If a fire is missed:** the cron daemon rolls forward to the next slot. You lose that batch's ~2 videos. The routine auto-recovers at the next fire — no manual intervention needed beyond checking `output/scripts/` for new dirs the next morning.

## Failure handling

The pipeline is hardened against partial failures:

- **Pipeline step fails** → retry counter bumps, status resets to QUEUED. After 3 consecutive failures, status moves to `BLOCKED` for human review.
- **Linter fails on a script** → case is skipped, logged to `output/_blocked.log`. Status stays QUEUED. Human reviews.
- **Upload crashes mid-way** → an orphan marker (`_uploading.<case>.json`) is left in the videos dir. Next run will refuse to upload that case until a human checks YouTube Studio and either:
  - Adds the entry to `_posted.json` manually + deletes the marker (if video is live), OR
  - Just deletes the marker (if video isn't on YouTube)
- **OAuth token expires** → clear error message tells you to re-run `python3 scripts/youtube_oauth_setup.py`.
- **Replicate API errors** → soft-failure; falls back to Pexels/Pixabay. Story vertical may produce with weaker visuals but still ships.
- **EL char soft-cap reached** → second slot of fire is skipped. Logs to `output/_blocked.log`. First slot still ships. Production resumes next month or with `--over-budget` override.

## To pause the routine

In Claude Code desktop app → Scheduled → `daily-shorts-pipeline` → Disable.

Or via MCP scheduled-tasks tool: `update_scheduled_task` with `enabled: false`.
