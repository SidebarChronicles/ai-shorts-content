# Release schedule — v2 TikTok-first strategy (May 19 – Aug 16, 2026)

> **TL;DR** — 8 videos/day across 7 verticals, fanning out to 3 platforms with TikTok as the discovery + monetization frontline, Instagram every video for brand layer, YouTube gated to validated winners only (≥30% TikTok 48h watch-through). Goal: follower growth → TikTok Creator Rewards (Day 30-60) → YouTube YPP (Day 90+). Realistic break-even = 60-90 days.

---

## Schedule overview

| Element | Setting |
|---|---|
| **Cron** | `7 7,12,18,21 * * *` — fires at 7:07 AM / 12:07 PM / 6:07 PM / 9:07 PM ET (with ~9 min jitter) |
| **Per-fire production** | 2 videos |
| **Per-day output** | 8 videos = 56/week |
| **Distribution** | TikTok (every video) + Instagram (every video) + YouTube (gated) |
| **Cost target** | ≤$100/mo until break-even |
| **Phase state** | `output/.channel_phase.json` |

## Distribution model

| Platform | Role | Upload rule |
|---|---|---|
| **TikTok** | Discovery + monetization frontline (Creator Rewards target) | EVERY video, immediately after production |
| **Instagram Reels** | Brand discovery + cross-platform follower funnel | EVERY video (low marginal effort) |
| **YouTube Shorts** | Long-term YPP play. Gated to winners. | **GATED:** only uploaded if `tiktok_gate=="open"` (≥30% TikTok 48h watch-through) |

## The YouTube gate workflow

1. **Production fires** → 2 videos per fire, 4 fires/day. Videos land in `output/<vertical>_videos/`.
2. **Manual cross-post** to TikTok + Instagram from your phone (~3 min/video). See `docs/CROSS_POSTING.md`.
3. **48h after TikTok upload** → check the video's analytics. Note the watch-through %.
4. **Mark the gate:**
   ```bash
   # If ≥30% watch-through:
   python3 scripts/cross_post_status.py --gate SY_05_H_basement open 34.2
   
   # If <30% (video stays on TT+IG only):
   python3 scripts/cross_post_status.py --gate SY_05_H_basement closed 18.7
   ```
5. **Next routine fire's STEP 4** auto-uploads gate-open videos to YouTube.

Manual single-upload (if you want to push to YouTube now):
```bash
python3 scripts/upload_to_youtube.py --case SY_05_H_basement --videos-dir output/story_videos --category 24
# (gate check applies automatically for non-legacy case_ids; --bypass-gate to override)
```

## Phase structure (rebuilt around TikTok signals + follower growth)

### Phase 1 — Saturation (Days 1–7)

**Goal:** Identify which sub-genres retain on TikTok.

- Production: 8/day across all 7 verticals (story, games, movies, mythology, mysteries, topx, finance)
- Story priority: first 12 videos all from story vertical (per `.channel_phase.json` `priority_until_count`)
- After story priority lifts: balanced rotation
- Manual TikTok cross-post + gate decisions per video

**Day 7 decision (mechanical):**

For each sub-genre/vertical:
- Compute median TikTok watch-through % across the week's videos
- **DROP** verticals with median <20% — they're not retaining
- **KEEP** verticals with median ≥30% — they're scaling material
- **PROBATION** for 20-30% — keep if any single video hit ≥40%

### Phase 2 — Winner narrowing (Days 8–14)

**Goal:** Concentrate production on retaining verticals. Cross-post winners to YouTube.

- Production: 8/day in kept verticals only
- Within kept verticals, A/B hook formulas (stat-shock / curiosity-gap / contradiction)
- All gate-open videos from Phase 1 should be on YouTube by Day 10

**Day 14 decision:**

- Pick the single winning sub-genre (highest TT watch-through median + highest follower-gained-per-video)
- Note retention curve shape (if there's a cliff at 30-50%, mid_anchor isn't doing its job)

### Phase 3 — Format optimization (Days 15–28)

**Goal:** Lock the format. Test combinations within the winner.

- Test grid: 2 hooks × 3 voices × 2 lengths = 12 cells × ~7 videos
- Primary metric: TikTok followers gained per video
- Secondary: YouTube gate-open rate

**Day 28 decision:**

- Lock the best-performing cell as canonical
- Channel KPI check: target 5K-10K TikTok followers by Day 28

### Phase 4 — Monetization unlock (Days 29-60)

**Goal:** Reach TikTok Creator Rewards eligibility (10K followers + 100K views/30d).

- Production: continue 8/day in winner vertical with locked format
- Watch for Creator Rewards trigger
- Apply at https://www.tiktok.com/creator-academy/en/creator-rewards-program when eligible
- First payout ~30 days after approval

**By Day 60: first revenue.**

### Phase 5 — YouTube prestige (Days 60+)

**Goal:** YouTube YPP if 500 subs (Early Access) or 1K subs (Full) hit.

- Continue same production cadence
- Apply for YPP via YouTube Studio when eligible
- Higher CPM per view than TikTok ($0.50-$5/1k vs $0.40-1.00/1k qualified)

### Phase 6 — Subscriber model (Days 90+)

**Goal:** Patreon/Ko-fi if 500+ engaged fans surface in comments.

- Stand up Ko-fi page (simpler, no platform fees on basic plan)
- Add tip-jar link to TikTok + Instagram bios
- Don't push hard; let fans discover it

## Daily morning ritual (~5 min/day)

```bash
# 1. Check yesterday's fires actually fired
ls -lt output/scripts/ | head -8

# 2. Eyeball TikTok analytics on the 48h+ videos, then mark gates:
python3 scripts/cross_post_status.py --ready-for-youtube      # see what's ready
python3 scripts/cross_post_status.py --gate <case> open 34.2  # if retained ≥30%
python3 scripts/cross_post_status.py --gate <case> closed 18  # if <30%

# 3. Check budget
python3 scripts/revenue_tracker.py --break-even-check

# 4. Skim TikTok follower count for trajectory toward 10K by Day 30
```

## When monetization unlocks (per Phase)

See `docs/MONETIZATION.md` for the activation steps for each path.

## When to revisit this plan

- **Day 7:** Phase 1 narrowing decision
- **Day 14:** Phase 2 single-winner pick
- **Day 28:** Phase 3 format lock + cost-revenue check
- **Day 30+:** First Creator Rewards eligibility check
- **Day 60:** First revenue, sustained?
- **Day 90+:** YPP application if eligible

## Critical files

| File | Role |
|---|---|
| `output/.channel_phase.json` | Phase state, vertical priorities, EL budget cap |
| `output/cross_post_status.json` | Per-video YT/IG/TT state + TikTok gate |
| `output/revenue_ledger.json` | Manual-entry revenue tracking (Phase 4+) |
| `output/elevenlabs_usage.json` | EL cost tracking (auto) |
| `output/replicate_usage.json` | Replicate cost tracking (auto, populated by parallel session's dashboard) |
| `scripts/cross_post_status.py` | Tracker CLI + gate management |
| `scripts/upload_to_youtube.py` | `--require-gate` flag |
| `scripts/revenue_tracker.py` | Revenue entry CLI |
| `scripts/analyze_performance.py` | YouTube analytics + `--break-even` rollup |
| `docs/CHANNEL_STATUS.md` | Current state summary |
| `docs/CROSS_POSTING.md` | Manual TikTok/IG workflow |
| `docs/AI_STORIES_PLAYBOOK.md` | Sub-genre rules for the story vertical |
| `~/.claude/scheduled-tasks/daily-shorts-pipeline/SKILL.md` | The routine's brain |
