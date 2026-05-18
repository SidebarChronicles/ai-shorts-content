# Testing Protocol — Niche Validation & Experiment Ledger

How we know if a niche is working, what we A/B test, and when to commit vs. cut. Codifies Part G of the niche-portfolio plan.

---

## The 10-video commit rule

For any new niche we launch:

1. **Post 10 videos in the niche over 2-3 weeks**
2. **Check the niche-target table** (below)
3. **Decision rule:**

   | % of targets hit | Action |
   |---|---|
   | ≥80% | **Commit** — schedule the niche permanently, increase output cadence |
   | 50-80% | **Iterate** — change voice/hook/visual style, post 5 more videos, re-check |
   | <50% | **Cut** — pivot the production capacity into a higher-RPM niche |

We never extend a niche past 15 videos without a "commit" call. Sunk-cost discipline matters when production capacity is the binding constraint.

---

## Per-niche target benchmarks (G2 from plan)

A niche **passes** the 10-video gate if it hits ≥80% of these targets:

| Niche | Target Avg View % | Target Views/Video | Target Subs / 1k Views | Sample size |
|---|---|---|---|---|
| Games (current) | 55%+ | 8k+ | 5 | already at 10 — measure now |
| Cases (re-do) | 65%+ | 12k+ | 8 | 10 videos (4 re-do + 6 new) |
| Movies | 55%+ | 10k+ | 6 | 5 videos |
| Finance | 60%+ | 15k+ | 10 | 8 videos |
| Psychology | 70%+ | 20k+ | 15 | 5 videos |
| Mythology | 60%+ | 12k+ | 8 | 4 videos |
| Mysteries | 65%+ | 15k+ | 10 | 4 videos |
| Top X | 55%+ | 25k+ | 5 | 6 videos |
| AI Tools | 50%+ | 8k+ | 8 | 8 videos |

### Why these targets?
- **Avg view % > 55%** is the Shorts algorithm threshold for sustained recommendation (varies by category, 55% is a safe floor; psychology and cases hit higher).
- **Views/video targets** reflect each niche's typical viral floor for a new channel — psychology and mythology punch above channel size due to passive audience interest.
- **Subs/1k views** measures stickiness — finance and psychology audiences subscribe more readily than gaming clip viewers.

---

## A/B experiments (concurrent)

Run **no more than 3 experiments simultaneously per vertical** — too many variables makes signal attribution impossible at our small sample sizes.

### Experiment 1: Voice A/B (channel-wide, ongoing)
- **Variants:** Adam, Charlie, Callum, Brian, Rachel, Daniel
- **Assignment:** queue_number % N (round-robin)
- **Implementation:** `voice_id` field baked into game_config.json at production time
- **Winner criteria:** ≥5 videos per voice in a given vertical, ≥15% lead in avg view %
- **Channel-wide winner:** ≥5 videos × 6 voices = 30 videos minimum
- **Status:** Live (shipped)

### Experiment 2: Hook style (per-vertical, 10-video buckets)
- **Variants:**
  - **Stat hook:** "$50M was lost in this scam"
  - **Question hook:** "Why is this game launching with a Kiss from a Rose cover?"
  - **Contradiction hook:** "Cheap insurance isn't real — here's why"
  - **Authority hook:** "From the team behind Halo and Destiny..."
  - **Curiosity hook:** "This game has been delayed 6 times. What happened?"
- **Assignment:** round-robin within each vertical's first 25 videos
- **Winner criteria:** highest avg view % after 5 videos in each variant → standardize on that for the vertical

### Experiment 3: Caption style
- **Variants:**
  - Word-by-word karaoke (yellow, shipped today)
  - Multi-word phrases (3 words at a time, white)
  - Highlight-only-key-words (full sentence with key words colored)
- **Sample size:** 5 videos per variant
- **Winner criteria:** highest avg view %

### Experiment 4: Aspect-ratio crop strategy (NEW — Week 1)
- **Variants:**
  - **Pillarbox blur** (new default — full 16:9 frame visible with blurred fill)
  - **Center crop** (legacy — fills 9:16 by cropping ~33% each side)
- **Sample size:** 3 game videos × 2 strategies
- **Winner criteria:** higher avg view % wins; if within 5% pick pillarbox (preserves content)

---

## Channel-level monetization milestones

| Milestone | Subs | 90d Shorts views | Action triggered |
|---|---|---|---|
| **M1: Early access tier** | 500 | 3M | Enable Super Thanks, channel memberships |
| **M2: Full YPP ad rev** | 1,000 | 10M | Ads enabled; primary revenue starts |
| **M3: Sponsorship-eligible** | 10,000 | n/a | Sponsor outreach ($500-2k/segment) |
| **M4: Niche-clear winner** | n/a | top niche ≥ 2× others on RPM | Pour 80% of production into winning vertical |
| **M5: Multi-channel split** | 50,000 | n/a | Spin off winning vertical into its own channel |

### Miss-detection rules
- **Miss M1 by 2 weeks** → drop the lowest-performing Tier 3 niche we accidentally started; increase output frequency.
- **Miss M2 by 1 month** → pivot evaluation: maybe gaming + crime aren't viral enough; double down on whichever Tier 1 niche is performing best.

---

## Watch-time amplifiers to test inside niches

These are micro-experiments to layer on TOP of the niche-level experiments:

- **Pattern-interrupt at 5 seconds** — change visual style or angle to re-grab attention
- **Cliffhanger hook in last 5 seconds** — increases comment volume + replays
- **List-format with explicit numbers** ("3 things... here's #1") — proven for retention
- **Visible scroll bar** for ranking videos showing position/total
- **AR-style on-screen text counters** (timer, scoreboard) — passive retention

Track which amplifiers showed up in top-performing videos post-30-day analytics review.

---

## Experiment ledger (running log)

Keep this updated as experiments start and end. Format:

```
## YYYY-MM-DD: <Experiment name>
- Hypothesis: ...
- Variants: A vs B
- Sample size needed: N videos per variant
- Status: running | concluded | aborted
- Result: A won by X%, or No clear winner
- Decision: <commit | iterate | revert>
```

### 2026-05-18: Voice A/B (Adam vs Charlie vs Callum)
- Hypothesis: Different voices retain different audiences
- Variants: Adam (slot 0), Charlie (slot 1), Callum (slot 2) — round-robin via queue_number % 3
- Sample size needed: 5 videos per voice
- Status: running (currently 4 Adam, 3 Charlie, 2 Callum across GG_01–GG_10)
- Decision: pending — re-evaluate at 30 days

### 2026-05-18: Karaoke captions vs no captions
- Hypothesis: Burned-in word-by-word captions lift retention on muted Shorts
- Variants: GG_01-GG_02 (no captions, original upload), GG_03-GG_10 (karaoke)
- Sample size needed: 8 captioned videos already, 2 baseline
- Status: just launched
- Decision: pending — re-evaluate at 7 days post-upload

### 2026-05-18: Aspect-ratio crop (pillarbox vs center)
- Hypothesis: Pillarbox blur preserves full frame and lifts retention
- Variants: pillarbox_blur (new default), center_crop (legacy)
- Sample size needed: 3 videos per variant
- Status: pillarbox implementation shipped; no production videos with it yet
- Decision: pending

---

## Reporting cadence

- **Daily:** `python3 scripts/analyze_performance.py --game` outputs latest channel + per-vertical numbers
- **Weekly:** Review experiment ledger — any conclusions? Update commit/iterate/cut decisions.
- **Monthly:** Review the M1-M5 milestones against actual numbers. Plan next month's experiments.
