# Release schedule — 4-phase strategy (May 19 – June 16, 2026)

> **TL;DR** — The pipeline produces 8 videos/day on a strict 28-day learning curve. Phase 1 explores 6 verticals, Phase 2 narrows to the top 2-3, Phase 3 locks the winning format, Phase 4 scales toward YPP eligibility. Every phase ends with a mechanical decision rule, not a vibe check.

---

## Why 4 phases and not "just post more"

For a 0-sub channel with no production data on the new format, the right strategy isn't "post as many videos as possible" — it's "post enough videos to learn which vertical resonates, then double down." Each phase has a specific hypothesis it's testing:

| Phase | Hypothesis | Decision at end |
|---|---|---|
| 1 Saturation | "Which of our 6 verticals has any algorithmic traction?" | Drop verticals with median <30% avg view % |
| 2 Narrowing | "Among the survivors, which one actually wins?" | Pick the single highest-confidence winner |
| 3 Optimization | "Within the winner, which hook × voice × length combination is best?" | Lock the winning cell as canonical |
| 4 Compound | "Can we sustain growth at proven format toward YPP?" | Apply for YPP when ≥500 subs + 3M Shorts views in 90d |

---

## Schedule overview

- **Cron:** `7 7,12,18,21 * * *` — fires at 7:07 AM, 12:07 PM, 6:07 PM, 9:07 PM Eastern (with ~9.6 min jitter). Times picked to hit the four peak YouTube Shorts windows: morning commute (7-9 AM), lunch break (11 AM-1 PM), after-work dinner scroll (5-7 PM), and prime-time evening (8-10 PM, the highest-traffic window).
- **Per-fire production cap:** 2 videos
- **Per-day output:** 8 videos
- **Upload behavior:** immediate (each video goes public within minutes of production)
- **Phase state:** read from `output/.channel_phase.json` at fire-time; updated manually at phase transitions

---

## Phase 1 — Saturation week (Days 1–7)

**Pool:** games, movies, mythology, mysteries, topx, finance (6 verticals)
**Total expected output:** ~56 videos
**Per-vertical n:** 9-10 videos each
**Cases vertical:** EXCLUDED in Phase 1 (already have 6 live in old format; conserve EL budget for new verticals)

### Daily routine

| Time (ET) | Verticals produced | Cumulative day | Algorithm window |
|---|---|---|---|
| 7:07 AM | A, B | 2 | Morning commute |
| 12:07 PM | C, D | 4 | Lunch break |
| 6:07 PM | E, F | 6 | After-work dinner scroll |
| 9:07 PM | G, H | 8 | Prime-time evening (PEAK) |

Where A→H rotates through 6 verticals on a wrap: games → movies → mythology → mysteries → topx → finance → games → movies (Day 1, 8 slots). The two slots per fire are always DIFFERENT verticals in Phase 1. Over 7 days × 8 slots = 56 production slots / 6 verticals ≈ 9-10 videos per vertical.

### Day 7 decision

```
For each vertical v in {games, movies, mythology, mysteries, topx, finance}:
  median_view_pct = median(avg_view_pct for v's last 6-7 videos at 48-72h)
  sub_conv_max    = max(subs_gained per 1k views for v's videos)

  If median_view_pct >= 40%:        KEEP v
  If median_view_pct < 30%:         DROP v
  If 30% <= median_view_pct < 40%:
    If sub_conv_max >= 3:           PROBATION → KEEP v
    Else:                           DROP v
```

Output the result to `output/analytics/phase_1_report.md`, hand-approve, then update `output/.channel_phase.json` with `phase: 2` and the new `kept_verticals` list.

---

## Phase 2 — Narrowing (Days 8–14)

**Pool:** top 2-3 from Phase 1
**Total expected output:** ~56 videos
**Per-vertical n:** 19-28 videos each (cumulative with Phase 1)

### Daily routine

Same cadence as Phase 1, but the rotation pool is smaller. When pool size = 2, both fire slots may be the same vertical. Within each vertical, vary the hook formula across the 5 canonical options: `stat-shock`, `curiosity-gap`, `contradiction`, `authority`, `list`.

### Day 14 decision

```
For each kept vertical:
  weighted_score = 0.6 * median_avg_view_pct + 0.4 * normalized_sub_conv

Winner = argmax(weighted_score)

Within winner:
  top_hook_formula_1, top_hook_formula_2 = top 2 hook formulas by retention
  retention_cliff_at_seconds = where the curve drops most steeply
```

Output `output/analytics/phase_2_report.md`. If retention cliff is at 30-50%, the mid_anchor isn't doing its job — flag for review of the writer's beat-4 generation logic.

Update `.channel_phase.json` to phase 3 with `kept_verticals: [winner]` and `hook_formula_rotation: [top_hook_formula_1, top_hook_formula_2]`.

---

## Phase 3 — Format optimization (Days 15–28)

**Pool:** winner vertical only
**Total expected output:** ~112 videos
**Test grid:** 2 hooks × 3 voices × 2 lengths = 12 cells × ~9-10 videos = 112 videos

### The grid

| Dimension | Values |
|---|---|
| Hook formula | top_hook_formula_1, top_hook_formula_2 |
| Voice (varies by vertical) | Adam / Charlie / Brian (or vertical-canonical 3) |
| Length | ~45s (short) vs ~60s (long) |

The routine cycles through cells deterministically: cell index = `(day_index * 8 + slot_in_day) % 12`. Each cell gets ~9-10 videos by Day 28.

### Day 28 decision

```
For each cell (hook, voice, length):
  cell_score = median_avg_view_pct + 0.3 * median_sub_conv_per_1k

Winning cell = argmax(cell_score)
```

Output `output/analytics/phase_3_report.md`. Update `SKILL.md` voice/length defaults to the winning cell. Update `.channel_phase.json` to phase 4.

### Channel KPI check at Day 28

| Metric | Target | If miss |
|---|---|---|
| Subscribers gained (Days 1-28) | ≥50 | Diagnose: hook quality (manual review 5 lowest-retention videos), upload timing (was the Mac awake?), content quality (re-run linter) |
| Cumulative Shorts views | ≥10k | Investigate: is the algorithm showing videos at all? Check Studio for impressions vs views. |

---

## Phase 4 — Compound + scale (Day 29+)

**Pool:** winner vertical (primary) + #2 from Phase 2 (diversification)
**Cadence:** unchanged 6/day, OR ramp to 8/day if EL budget upgraded to Creator
**Experimentation budget:** 1 in every 5 videos = A/B variant (different music tempo, new color grade, alt-title format)

### YPP eligibility tracking

Run `python3 scripts/analyze_performance.py` weekly. Two thresholds matter:
- **Early Access:** 500 subs + 3M Shorts views in any 90-day window → opt-in monetization for selected videos
- **Full YPP:** 1k subs + 10M Shorts views in 90d → standard monetization

The `analyze_performance.py --ypp` flag computes both. Apply when either threshold is comfortably crossed (10% buffer minimum to avoid de-qualification).

---

## How phase state actually works

The single source of truth is `output/.channel_phase.json`. The routine reads it at every fire:

```json
{
  "phase": 1,
  "start_date": "2026-05-19",
  "day_index": 1,
  "kept_verticals": ["games", "movies", "mythology", "mysteries", "topx", "finance"],
  "hook_formula_rotation": ["stat-shock", "curiosity-gap", "contradiction", "authority", "list", "personal-stakes"],
  "videos_per_fire": 2,
  "el_budget_softcap_chars": 25000,
  "el_tier": "starter"
}
```

To transition between phases (e.g. Phase 1 → 2):

1. Wait for Day 7 (or whenever the human is ready to commit)
2. Generate `phase_1_report.md` via `python3 scripts/analyze_performance.py --phase 1 --report`
3. Review the recommended `kept_verticals` list
4. Edit `.channel_phase.json`: bump `phase` to 2, replace `kept_verticals`, update `end_date_planned`
5. Optionally also update `hook_formula_rotation` if focusing on certain formulas

Auto-advance is OFF by default (`auto_advance: false`). This is intentional — a human always confirms the phase transition.

---

## Daily morning ritual (under 5 minutes)

Every morning during Phases 1-3:

1. **Check fire success.** Did the 4 fires actually run (7:07 AM / 12:07 PM / 6:07 PM / 9:07 PM)? `ls -lt output/scripts/ | head -10` should show new directories from the last 24h. If not, the Mac was asleep — wake it up + check the cron with `python3 scripts/analyze_performance.py --since 12h`.
2. **Check budget.** `cat output/elevenlabs_usage.json | grep -A1 $(date +%Y-%m)`. Creator cap is 100k chars/mo, soft-cap 90k. At 8/day × ~290 chars × 30 days ≈ 70k chars projected — comfortable. If projected to exceed 90k, drop to 6/day by reducing fires_per_day in .channel_phase.json.
3. **Check blocked log.** `cat output/_blocked.log` for linter failures + budget skips. If >10 blocks in 24h, something's wrong with the writer or the linter; investigate.
4. **Check view counts on yesterday's drops.** Bottom 2 retention videos: any common failure mode (weak hook? wrong music? wrong vertical?)? Top 2: anything to amplify?

That's it. Don't add more steps — the routine should be hands-off most of the time.

---

## What if it's not working?

If by Day 7 the median view % across ALL verticals is <20%, something is broken at the **pipeline** level, not the strategy level. Diagnose:

1. **Linter pass rate** — is every new script passing the structure check? If not, the writer (Claude in the routine) is misinterpreting the 7-beat rules.
2. **Audio mix** — open a fresh video in QuickTime. Can you hear the music behind the narration? Are the SFX at every cut? If not, the audio mixer is silently failing.
3. **Hook timing** — measure the first beat with a stopwatch. Is it landing under 3 seconds? Are the first 8 words the payoff?
4. **Vertical color grade** — does each vertical's videos look visually distinct from the others?

If all four are correct, the issue is content quality — the writer is generating weak scripts that pass structurally but don't grab attention. That's a writer-tuning problem, not a pipeline problem. Drop cadence to 3/day, have a human review each script, identify the failure mode, and retrain the writer.

---

## Critical files for the schedule

| File | Purpose |
|---|---|
| `output/.channel_phase.json` | Current phase state, kept_verticals, soft-cap, etc |
| `output/elevenlabs_usage.json` | Month-to-date char + USD consumption |
| `output/_blocked.log` | Skipped cases (linter fail, budget exceed) |
| `output/analytics/phase_N_report.md` | Auto-generated end-of-phase summary |
| `~/.claude/scheduled-tasks/daily-shorts-pipeline/SKILL.md` | The routine's brain — STEP 3 reads phase state |
| `scripts/analyze_performance.py` | Run with `--phase N --report` to generate phase summaries |
| `scripts/check_script_structure.py` | Pre-render linter gate |
