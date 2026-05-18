# Morning workflow — `/morning`

The daily production workflow for the story vertical. One command chain. ~20 minutes of attended work, ~$6/day in API spend, 4 stories shipped to TikTok + queued for YouTube.

This replaces the deleted `~/.claude/scheduled-tasks/daily-shorts-pipeline/` cron routine. The morning workflow is **human-triggered with confirmation gates** — by design. Auto-cron production proved hard to course-correct mid-batch; this version lets you pause/abort at high-risk transitions.

---

## TL;DR

```
/morning
```

That's it. The skill chains 6 sub-skills in order, with two pauses for your review.

---

## The 6 steps

| # | Skill | Script | What it does |
|---|---|---|---|
| 0 | `/cleanup` | `scripts/morning_cleanup.py` | Archive stale picks/reports, prune leaked temp files |
| 1 | `/analytics` | `scripts/analyze_performance.py` | Pull yesterday's YouTube Analytics |
| 2a | `/suggest-tweaks` | `scripts/suggest_tweaks.py` | Compute per-voice/sub-genre medians → `suggested_tweaks_<date>.md` |
| 2b | `/pick-today` | `scripts/pick_today.py` | Rank queue + apply skews → `picks_<date>.json` (4 case_ids) |
| 3 | `/render-batch` | `scripts/render_story.py` | Render all 4 end-to-end (~$6 total) |
| 4 | `/schedule-uploads` | `scripts/schedule_uploads.py` | TikTok now + YouTube at next 4 prime slots |
| 5 | `/research-stories` | `scripts/research_reddit_stories.py` | Top up the queue from Reddit |

Each is also independently runnable — if step 3 dies on case 3-of-4, fix and re-invoke `/render-batch` (idempotent: skips the cases that already succeeded).

---

## Daily flow (what you actually do)

### Before 8 AM ET

**Make sure the day's picks have their briefs filled.** Step 3 (`/render-batch`) will refuse to render any stub whose `script_config.json` still has `_FILL_IN: true` in its visual_brief or sound_brief. The writer step happens in conversation with Claude, *not* inside `/morning`.

Two ways to get the writer done:
1. **Yesterday evening:** ask Claude to fill briefs for the next 4 highest-scoring queue stubs (per `scripts/story_writer_prompt.md`). This means `/morning` runs cleanly.
2. **At 8 AM:** run `/pick-today --dry-run` first to see which cases would be picked, then have Claude fill those briefs, then run `/morning`.

### Run `/morning`

Open Claude Code in this repo, type `/morning`. Expected timeline:

```
T+0s    Step 0  cleanup (~0s output)
T+1s    Step 1  analytics — pulls yesterday's data
T+30s   Step 2a suggest_tweaks — writes today's tweaks file
        ⏸ pause: open suggested_tweaks_<date>.md in your editor, skim, close it
T+0s    Step 2b pick_today — proposes 4 picks, asks you to type 'y'
        ⏸ pause: review the 4 picks
T+10m   Step 3  render_batch — 4 videos rendered (~$6 spend)
T+11m   Step 4  schedule_uploads — TikTok lives, YouTube scheduled
T+12m   Step 5  research-stories — queue topped up
done
```

The two `⏸ pause` gates are deliberate. They're the points where you can abort cheaply if today's data tells you to wait or pivot.

### Skip the render (light-touch mode)

```
/morning --skip-render
```

Runs steps 0-2b (analytics + tweaks + pick), then stops. Useful when you want to see today's recommendation without committing to spend.

---

## Setup (one time)

### Required `.env` keys

| Key | Used by | Where to get |
|---|---|---|
| `ELEVENLABS_API_KEY` | Step 3 (TTS) | https://elevenlabs.io → profile |
| `REPLICATE_API_TOKEN` | Step 3 (Flux + Pika) | https://replicate.com/account/api-tokens |
| `PEXELS_API_KEY` | Step 3 (stock fallback) | https://www.pexels.com/api/ |
| `FREESOUND_API_TOKEN` | Step 3 (ambient + SFX) | https://freesound.org/apiv2/apply |
| `POSTFAST_API_KEY` | Step 4 (TikTok) | https://postfa.st dashboard |
| `POSTFAST_TIKTOK_CHANNEL_ID` | Step 4 (TikTok) | PostFast dashboard → connected accounts |
| (YouTube OAuth) | Step 4 (YouTube) | `python scripts/youtube_oauth_setup.py` → `token.json` |

### Optional `.env` keys

| Key | Default | Purpose |
|---|---|---|
| `ELEVENLABS_MONTHLY_BUDGET` | 22.0 | render_story refuses if projected to exceed |
| `ENABLE_ELEVEN_MUSIC` | 0 | If 1, pays for ElevenLabs Music hero-beat clips. Default uses local CC0 library at `assets/music/`. |

### Seed `assets/music/`

For hero-beat music to play, drop 5 CC0 clips per `assets/music/README.md` (Pixabay Music search terms documented there). Without them, hero beats silently skip music — render still produces a valid video.

---

## What each step's output looks like

### `/cleanup`

One line:
```
cleanup [DRY-RUN]: would archive 2, remove 1, free ~3.4MB
  → archive: output/daily/picks_2026-05-12.json
  → archive: output/research/candidates_2026-05-16.md
  → remove:  /var/folders/.../T/el_perbeat_a1b2c3
```

Default is dry-run. Pass `--apply` to actually move/delete. Archives never delete pipeline-critical state — only stale-by-date files. Final mp4s in `output/story_videos/` are never touched.

### `/suggest-tweaks`

Writes `output/analytics/suggested_tweaks_<date>.md`. With data:

```markdown
# Suggested tweaks — 2026-05-22

## Yesterday at a glance
- Videos analyzed: 4 (≥100 views threshold)
- Total channel views (30d): 12,847
- Channel avg view %: 38.2%
- Subs gained (30d): 23

## Patterns (median AVP per dimension)

### By Voice
| Value | Median AVP | N |
|---|---|---|
| `Rachel` | **48.3%** | 3 |
| `Nicole` | **42.1%** | 2 |
| `Daniel` | **31.7%** | 4 |

→ Recommendation: prefer `Rachel` (+16.6 pts over `Daniel`)

## Today's recommended skews
- Prefer voices: `Rachel`, `Nicole`, `Domi`
- Skew today's batch toward `horror` (best-performing sub-genre)

## Top-retaining hooks (verbatim)
- **48.3% AVP** `SY_09_H_a_wife_shouldn_t_argue_w` — "He smiled. The lamp dimmed when I disagreed back."
```

Without data (pre-launch state): writes a "no data yet — pick by hand" placeholder. Non-blocking.

### `/pick-today`

Interactive:
```
── Today's picks (4/4) ──
   skews applied: {'preferred_subgenre': 'horror', 'preferred_voices': ['Rachel', 'Nicole']}
   1. [ 95.0] SY_24_H_there_are_only_two_of_us  (horror, voice=Nicole, gender=F)
      → mined_score=85.0; +10 sub-genre skew (`horror`); +5 voice skew (`Nicole`)
   2. [ 90.4] SY_27_H_the_woods                 (horror, voice=Nicole, gender=F)
      → mined_score=75.4; +10 sub-genre skew (`horror`); +5 voice skew (`Nicole`)
   3. [ 88.0] SY_30_H_the_grim_reaper           (horror, voice=Nicole, gender=F)
      → mined_score=73.0; +10 sub-genre skew (`horror`); +5 voice skew (`Nicole`)
   4. [ 84.4] SY_11_R_aita_if_i_refuse_to_give  (reddit, voice=Brian, gender=M)
      → mined_score=84.4

   Queue depth after pick: 74

Write picks file? [y/N]
```

Sub-genre hard cap at 3-of-4 prevents an all-horror batch even when skew is strong. Type `y` to write `output/daily/picks_<date>.json`.

### `/render-batch`

Per case, ~2 minutes:
```
── Render: SY_24_H_there_are_only_two_of_us ──
  → check_script_structure
  → make_audio_elevenlabs (per-beat mood mode)
  → build_visuals_track (Flux + Pika)
  → build_sound_design (Freesound ambient + SFX)
  → copy alignment for renderer lookup
  → add renderer-required aliases to script_config.json
  → build_karaoke_filter
  → build_top_title_filter
  → render_game_video (builds hook_overlay + concat + renderer audio)
  → audio mix override (narration + sound_design → audio_mixed.mp3)
  → final encode → output/story_videos/SY_24_H_there_are_only_two_of_us.mp4
  → story_orchestrator --mark-status RENDERED

  ✓ SY_24_H_there_are_only_two_of_us rendered in 124s — output/story_videos/SY_24_H_there_are_only_two_of_us.mp4 (13.2MB)
```

Then summary:
```
── render_story summary: 4/4 succeeded, 0 failed
  estimated spend this run: ~$6.00 (4 × ~$1.50)
```

### `/schedule-uploads`

```
── schedule_uploads: 4 case(s), platforms=both
   YouTube prime slots assigned:
     SY_24_H_there_are_only_two_of_us       → Mon 2026-05-23 08:00 EDT
     SY_27_H_the_woods                      → Mon 2026-05-23 12:30 EDT
     SY_30_H_the_grim_reaper                → Mon 2026-05-23 18:30 EDT
     SY_11_R_aita_if_i_refuse_to_give       → Mon 2026-05-23 21:30 EDT

  [1/4] SY_24_H_there_are_only_two_of_us
    → TikTok via PostFast (immediate)
        https://www.tiktok.com/@sidebarchronicles/video/7368...
    → YouTube --publish-at Mon 08:00 ET
        ✓ Scheduled: https://youtu.be/abc123
  ...

── schedule_uploads summary
  TikTok: 4/4 posted
  YouTube: 4/4 scheduled
```

---

## Troubleshooting

### `writer hasn't filled all briefs/text. Placeholders at: ['beats[0].text', 'beats[0].visual_brief']`

The picked stub's `script_config.json` still has `[FILL IN]` or `_FILL_IN: true` markers. Two options:

1. Have Claude fill the briefs now: read `scripts/story_writer_prompt.md`, then ask Claude to fill all 7 beats for the failing case.
2. Drop the failing case from picks and re-run: edit `output/daily/picks_<date>.json` to remove the failing entry, then re-run `/render-batch`.

### `BudgetExceeded: ELEVENLABS_MONTHLY_BUDGET`

Render refuses to start. Either bump the value in `.env` (and acknowledge the EL bill) or wait until next month. To check current spend:

```bash
cat output/elevenlabs_usage.json
```

### `PostFast 401 Unauthorized`

The PostFast API key is stale or revoked. Re-check:

```bash
python scripts/post_via_scheduler.py --check-auth
```

If it lists no connected accounts, log into PostFast → reconnect TikTok.

### `YouTube: token.json missing or revoked`

Re-run the one-time OAuth setup:

```bash
python scripts/youtube_oauth_setup.py
```

### `render_story crashed mid-batch on case 2 of 4`

The batch aborts after the first failure to avoid burning $$ on broken pipeline state. Fix the underlying issue, then re-run:

```bash
python scripts/render_story.py --batch output/daily/picks_<date>.json
```

Idempotent skips kick in for case 1 (already done) — only cases 2-4 attempt fresh work.

To re-do a single step within a case (e.g. re-encode only):

```bash
python scripts/render_story.py --case <case_id> --only-step 11
```

### "Karaoke captions look off"

If timing drifts: confirm `assets/audio/narration_<case>.alignment.json` exists and is from the SAME run that produced the .mp3. Stale alignment files from a previous render cause drift. Delete both and re-run `--from-step 3`.

If two captions stack after a period: this was the bug fixed in commit `6226a9f` (clamp word end to next word's start). If you see it again, check `scripts/build_karaoke_filter.py:extract_words` — the clamping logic should still be in place.

---

## Cost model

Per video: ~$1.50 (Flux 8× + Pika 2× + EL ~600 chars + Freesound free).
At 4 videos/day: ~$6/day = **~$180/month** Replicate + EL.
Plus PostFast: **~$15/month** fixed.
**Total: ~$195/month** during the validation phase.

This is ~2× the original $100/mo target. The decision was made (and recorded in `~/.claude/plans/while-the-other-claude-mutable-dove.md` Plan B Part H) to accept the higher burn during validation, drop to 2/day if cost is uncomfortable at Day 14, and adjust further based on Phase-1 retention data.

---

## Why "prime times" are fixed (for now)

The 4 YouTube slots — 8:00 / 12:30 / 18:30 / 21:30 ET — are hard-coded in `scripts/schedule_uploads.py:PRIME_SLOTS_ET`. They're a defensible default based on YouTube Shorts engagement research, not analytics-tuned to *your* audience.

This will get replaced with an analytics-driven slot picker once you have 30+ posted videos worth of "when did this view *actually* come in" data. Out of scope for v1.

TikTok publishes immediately when `/morning` runs (PostFast has no scheduling API). Run `/morning` at the time you want your TikTok post to land — typically 8 AM ET to catch the morning commute scroll.

---

## Related docs

- `scripts/_README.md` — script layout reference
- `scripts/story_writer_prompt.md` — the writing rules Claude follows when filling beats + briefs
- `docs/AI_STORIES_PLAYBOOK.md` — sub-genre rules + visual/sound brief schemas
- `docs/CROSS_POSTING.md` — PostFast setup (Step 4 of /morning depends on this)
- `docs/RELEASE_SCHEDULE.md` — phase-by-phase strategy and Day-N decision trees
- `~/.claude/plans/while-the-other-claude-mutable-dove.md` — the design plan for this whole workflow
