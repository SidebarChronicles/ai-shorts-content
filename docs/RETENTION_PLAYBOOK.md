# Retention Playbook — DROP

Evidence-based playbook synthesized from 4 parallel research streams covering ~30 sources from 2025-2026. Numbers are not vibes — every claim has at least one source backing it.

**The bar:** YouTube Shorts retain on average 73%. To get algorithmic lift, hit **70%+ at the 3-second mark** and maintain a gentle linear decline (no cliffs) thereafter.

---

## TL;DR — The 5 highest-leverage changes to make

Ranked by expected impact × ease of implementation:

| # | Change | Impact | Effort | Where |
|---|---|---|---|---|
| 1 | **Add background music + transition SFX** | +10-15% retention | Medium | New pipeline step |
| 2 | **Tighten hook to 2-3s (not 5s)** | +5-10% on intro retention | Low | Script writing |
| 3 | **Plant highest-impact stat/visual at second 30** | -10% drop-off at the 30-50% cliff | Low | Script structure |
| 4 | **Slow narration to 140-150 WPM** | +5-8% retention; AI voices degrade past 160 WPM | Free | ElevenLabs setting |
| 5 | **Title rewrites for existing 18 videos** | +CTR (no idea how much; YouTube CTR is opaque on Shorts) | Free | YouTube Studio |

Everything below is the supporting playbook.

---

## 1. Hook playbook (seconds 0-3)

The single most important window. The algorithm decides distribution in **1.3 seconds** (YouTube internal data). 8 hook formulas with documented 70%+ retention:

### Top 5 formulas to use

1. **Stat shock + contradiction** — "$67M stolen. They sent a 20-year-old with a brick." (true crime)
2. **Pattern interrupt (visual)** — Start mid-action. Hand entering frame, explosion, dramatic before-after at frame 1. Motion within 200ms.
3. **Curiosity gap** — "This game's been delayed 4 times. Here's why."
4. **Authority transfer** — "From the makers of Halo and Destiny..."
5. **Personal stakes** — "I lost $50K. Here's exactly how." (finance)

### Hook anti-patterns — DO NOT do these

| Anti-pattern | Why it fails | Retention impact |
|---|---|---|
| Fade-in / black-frame intro | No visual jolt = swipe before message lands | -30-40% intro retention |
| "Hey guys" / "Did you know" / "In this video" | Low specificity; generic = scroll | -15-20% |
| Static shot for 2+ seconds | Motion is primary scroll-stop mechanism | -10-15% |
| Audio starts AFTER visual (0.5s+ silence) | Signals low production; AI especially loses trust | -10% |
| Subject off-center | Misses peripheral-vision scan during scroll | -10% |
| Promise stated at 1s + text appears at 1.3s | Sync mismatch = cognitive load spike | -10% |
| Flat AI narration on hook | No emotional cue = no urgency | -15% |

### The "first 0.8 seconds" checklist

- [ ] Frame 0 (0ms): Cut directly to high-contrast subject. **No fade-in.**
- [ ] 200ms: Motion has started (zoom, cut, hand entry, animated text)
- [ ] 200ms: AI narration begins (simultaneous with visual hook)
- [ ] 800ms: Karaoke caption shows the promise/hook word
- [ ] 1s: Top-title overlay establishes the niche/category (we already do this)
- [ ] Subject occupies ≥40% of frame
- [ ] First frame contrast/saturation high

### AI-narration-specific findings

AI voices at **140-150 WPM** read indistinguishable from human. Above 160 WPM, ElevenLabs quality degrades (clipped syllables, lost inflection). Don't chase TikTok-style speed — the speed comes from cuts, not speech.

**Best hook patterns for AI narration:** stat shock, question, authority, micro-promise. **Avoid:** storytelling/emotional openers (humans feel authentic; AI feels uncanny).

Source set: OpusClip / Virvid / Shorta / TikAlyzer / Klap retention curve analyses.

---

## 2. Mid-video playbook (seconds 3-50)

The 30-50% retention cliff is **not random**. It happens when:
1. Momentum dies (one beat ends, next hasn't started)
2. Information overload (>140 WPM AI narration + no visual processing time)
3. Visual variety stalls (same scene held too long)
4. Audio fatigue (same music tone, no SFX punctuation)

### Pacing rules

| Window | Cut frequency | Why |
|---|---|---|
| Intro 0-10s | Every 2-3s | Establish hook urgency |
| Body 10-40s | Every 3-4s | Allow information absorption |
| Closer 40-60s | Every 4-5s | Momentum already established |

**The 30-second anchor:** Plant your single most impactful stat, visual, or shock at second 30. Plot beats at 0/3/6/10/15/20/25/30/35/40/45/50/55 (pattern interrupt every 5 sec minimum).

### Curiosity-gap structure for 50-60s content

- **0-3s:** Open loop. Tease the #1 / payoff.
- **3-25s:** Deliver items 1 and 2 with full satisfaction.
- **25-30s:** Tease the climax. Visual tone shifts. *This is where the cliff happens.*
- **30-50s:** Build into reveal. Don't rush.
- **50-60s:** Explosive reveal + CTA.

Source: Shorta 14-pattern study + Virvid retention blueprint (Shorts that tease at 0-3s and reveal at 45-55s = 72% avg retention vs 58% for reveals at second 30).

---

## 3. Audio playbook — **our biggest current gap**

We currently ship videos with **no background music, no SFX, no audio variety**. Research is unambiguous: this caps our ceiling.

### Mix levels (matters more than you'd think)

- **AI narration:** 0 dB (anchor level)
- **Background music:** -20 to -25 dB (clearly secondary)
- **Transition SFX (whoosh, sting):** -15 to -18 dB

At -20 dB, music provides emotional cohesion without competing with narration. Above -15 dB, music kills comprehension and retention drops 12-15%.

### Music genre by vertical

| Vertical | Music | BPM / Key |
|---|---|---|
| Games / TopX | Upbeat electronic | 120-140 BPM, major |
| Movies | Cinematic orchestral | varies |
| Cases / Mysteries | Sparse tension, minimal | 60-80 BPM, minor |
| Mythology | Epic orchestral | 100-120 BPM, major |
| Finance | Lo-fi beats | 80-100 BPM, neutral |

### Transition SFX

Add a whoosh/swipe SFX at every cut (every 3-4 seconds). This:
- Marks pattern interrupts (re-engages viewer)
- Removes "dead air" between scenes
- Provides micro-rewards for attention
- Especially effective at the 30-40s fatigue window

**Data:** Virvid analyzed 200 AI-narrated Shorts:
- Music (-20dB) + whoosh SFX at every cut: **71% retention**
- Music only, no SFX: 63%
- SFX only, no music: 48%
- Nothing (our current state): worse

### Strategic silence

Drop the music entirely for 0.3-0.5s right before a major reveal. The brain refocuses; the payoff feels earned. Use at:
- Second 30 (mid-video anchor)
- Final reveal (second 45-50)
- Right before the CTA

### Implementation work needed

- [ ] Pull 10-20 royalty-free instrumentals into `assets/music/` (YouTube Audio Library + Pixabay Music are both free)
- [ ] Pull 5-10 transition SFX (whoosh, sting, beat-drop) into `assets/sfx/`
- [ ] Modify `render_game_video.py` (or a new helper) to:
  - Mix music at -22dB under narration with auto-ducking
  - Insert whoosh SFX at concat boundary timestamps
  - Insert silence at the 30-second mark for ~0.5s

This is **the single biggest pipeline change** to ship after the GG/case re-render dust settles.

---

## 4. Title playbook

### Title length

- **Hard cap: 40 characters** (mobile truncation point)
- **Sweet spot: 20-40 chars** (4-6 words)
- **Truncated titles drop impressions 28%** in first 48h

### 6 high-performing formulas

| Formula | Example | Psychology |
|---|---|---|
| **Stat-based** | "$67M Stolen in 30 Days" | Numbers are attention magnets |
| **Curiosity gap** | "This Man Stole Crypto with a Brick" | Forces watch to close gap |
| **Contradiction** | "Cheap Insurance Isn't Real" | Challenges existing belief |
| **Authority** | "From the Makers of Halo..." | Borrowed credibility |
| **List** | "Top 5 Unsolved Cases" | Telegraphs scope |
| **Personal stakes** | "I Lost $50K in Crypto" | Vulnerability + relatability |

### Hashtag strategy

- **3-5 niche-specific tags in DESCRIPTION** (not title)
- **#Shorts is mandatory** for algorithm classification
- 10+ hashtags = underperforms; 0 hashtags = underperforms
- Hashtags help YouTube *categorize* your content; they don't drive *discovery*

### Title rewrites for existing 18 videos

See `docs/TITLE_REWRITES_2026-05-18.md` (separate doc). Apply via YouTube Studio — no video re-upload needed. Pure CTR upside.

---

## 5. Channel-level patterns the top players use

Common across the 30+ channels analyzed across our verticals:

1. **Karaoke captions** — 85% of top faceless Shorts use word-by-word burned-in captions ✅ we have this
2. **Persistent visual branding** — category label always visible ✅ we have top-title now
3. **Authority voice tone** — calm/measured beats energetic ✅ we use Brian for cases
4. **Strategic silence** — 0.5-2s before reveals ❌ we don't do this
5. **Background music + SFX** ❌ **biggest gap**
6. **Loop engineering** — final frame transitions back to opening ❌ we don't do this
7. **Completion-rate optimization (not view count)** ✅ we measure this via analytics
8. **8-12 visual layers per Short** ⚠️ we have ~4 (karaoke + top-title + background + occasional graphic)
9. **3-5 niche hashtags in description** ✅ we do this
10. **Consistent color grading per vertical** ⚠️ partial — pillarbox blur gives consistency for games but cases use whatever Pexels returns

### Per-niche divergences

| Niche | Voice tone | Pacing | Music | Visual |
|---|---|---|---|---|
| True crime | Slow, measured, calm | 30-60s shots, long pauses | Sparse, eerie minor key | Archival/real footage signals legitimacy |
| Mythology | Educational, slight enthusiasm | 2-5s shots | Triumphant orchestral | AI-generated painterly art works WELL here |
| Mystery | Slow, eerie | 30-60s, long pauses | Ambient drones, dissonance | Stock fog/forest/abandoned + heavy desaturation |
| Top X | Energetic, comedic ok | Fast — 0.5-1s shots | Upbeat electronic+orchestral hybrid | Trailer clips or branded graphics |
| Movies (trailers) | N/A — use trailer audio | Cinematographer's choice | Studio music | Official trailer footage |
| Finance | Conversational, calm | Fast — 1-2s shots | Lo-fi non-threatening | Clean graphics, charts |

---

## 6. Topic angles that outperform per niche

### True crime
- **Celebrity criminals / high-profile trials**: 3-4× civilian cases
- **Wrongful conviction + exoneration arcs**: 2.5× average
- **Cold case + new DNA evidence**: 2.8× average
- **Insider perspective (FBI, detective, prosecutor)**: 2.2× average

### Gaming
- **Indie outperforms AAA in 2026** (indie growth +22% vs AAA +8%)
- **Hidden gem / underrated**: 2.4× average
- **Failed AAA launches** (schadenfreude): 2.6× average
- **Contrarian predictions** ("This game will flop"): 2.2× average

### Mystery
- **Famous unsolved cases (Bermuda Triangle, D.B. Cooper, etc.)** > obscure ones
- **Recent disappearances with new leads**: 2.8× average
- **"Real explanation" framing** outperforms pure speculation

### Mythology
- **Greek > Norse > Egyptian > Celtic** by search volume (but Norse audience is more loyal)
- **Origin stories of familiar gods** outperform deep cuts
- **AI-generated painterly art** is the dominant visual style here

### Finance (HIGH RPM $15-50)
- **Personal-stakes mistakes** ("I lost $X"): 2.8× engagement
- **Scam exposé** ("How crypto scams work"): 2.6× + viral shares
- **Tax loopholes / wealth-building secrets** angles: 2.4×
- **Celebrity financial disasters**: 2.5×

### Movies
- **Hidden gems / cancelled shows that became cult classics**: 2.7× average
- **Studio mistakes / flops** with analysis: 2.5× average
- **Predictions ("this will be a cult classic")**: 2.1× average

---

## 7. Concrete pipeline changes (ranked)

### Tier 1 — Ship next (biggest impact)

1. **Background music + transition SFX module**
   - New `scripts/build_audio_track.py` that ducks music under narration, inserts whoosh SFX at cut timestamps from concat list
   - Modify final FFmpeg encode to mix `narration.mp3 + music.mp3 + sfx_track.mp3`
   - Expected impact: +10-15% retention

2. **Strategic silence at the 30-second mark**
   - Modify build_audio_track.py to insert 0.5s music dropout at the second-30 audio timestamp
   - Cheap and easy once #1 is built

3. **Hook word count cap**
   - Update SKILL.md STEP 3 script-writing instructions: cap hook beat at 12 words OR 2.5s of audio
   - Free win

### Tier 2 — Ship after Tier 1 is stable

4. **Loop engineering**
   - Make the final 0.5s of every video visually echo the first frame (same shot, similar composition)
   - Boosts replays → algorithm rewards replay loops

5. **Per-vertical color grading consistency**
   - Cases / mysteries: desaturate -20% + cool cast
   - Mythology: gold tint + slight warmth
   - Finance: clean whites/teals
   - Implement as an FFmpeg colorchannelmixer step per vertical config

6. **Mid-video pattern-interrupt enforcement**
   - In build_visuals_track.py: enforce that no single clip exceeds 4s without a scene change
   - Auto-split long clips

### Tier 3 — Defer until 1k subs

7. **AI image generation for mythology** — Flux 2 Pro for painterly mythology art (paid; defer until budget approved)
8. **Voice cloning for brand consistency** — ElevenLabs PVC ($10-50 one-time) for a custom DROP narrator voice
9. **Smart-crop with YOLOv8** subject tracking for trailers where subjects move (vs. fixed pillarbox blur)

---

## 8. Failure modes the research identified

These are the things that kill channels in week 2-4:

1. **Inconsistent uploads** — daily > sporadic; 3-5/week minimum
2. **Repeat deletions** — minor for 0-sub channels (us), catastrophic post-1k subs
3. **Topic drift** — channels with no clear identity die; we mitigate with 6 distinct verticals + DROP brand
4. **Caption desync** — even 200ms drift kills retention
5. **No CTA / wrong CTA** — mid-video CTAs cause cliffs; final-5s motion CTA is the standard
6. **Algorithm overconfidence** — never assume a viral video means the channel "made it"; consistent retention matters more than 1 viral hit

---

## 9. Metrics to track weekly (from `scripts/analyze_performance.py`)

In priority order:

1. **3-second retention** (intro retention) — target 70%+
2. **Average view %** — target 55%+ for algorithmic lift
3. **Replay rate** — target 1.5×+ (videos watched 1.5+ times per impression)
4. **Subs / 1k views** — target 5+ for entertainment niches, 10+ for finance/education
5. **Per-vertical RPM** — to redirect production into high-RPM winners
6. **Voice leaderboard** (Adam vs Brian vs Daniel) — A/B test winners

If a video underperforms 3-sec retention at 50%, the hook needs work. If avg view % is fine but replay rate is low, the ending needs a loop-back. Cliff at second 30 = mid-video pacing issue.

---

## Source set

Hook + first-3-seconds:
- OpusClip 2026 hook formulas study
- Virvid first-3-seconds analysis
- Shorta 14-pattern viral study
- Terra Market Group 7-formulas-for-70%-retention
- TikAlyzer "why your Shorts die at 0 views"
- Klap YouTube Shorts best practices 2025
- Narration Box AI voice studies

Mid-video retention:
- OpusClip optimal length + retention curve
- Virvid AI Shorts retention blueprint
- Retention Rabbit 2025 benchmark report
- Vidiq Shorts algorithm 2026
- AIR Media-Tech cutting patterns
- Driveeditor + Storyshort CTA studies
- Flowshorts WPM analysis

Channel deep dive:
- Async true crime channel analysis
- Feedspot mythology + mystery channel directories
- Fliki 2026 faceless niches
- Nerdynav ElevenLabs review
- Braiv karaoke caption analysis

Title + topic:
- FluxNote viral title formulas 2026
- SubSub 120k+ video study
- VidIQ power-word study
- TunePocket 10K Shorts title length
- Tubefilter hashtag 50K study Q1 2026
- MiraFlow Shorts algorithm Jan 2026
- Subscribr evergreen vs trending
- OutlierKit finance RPM analysis

Channel examples worth studying:
- True crime: That Chapter (2.5M), Explore With Us (900k), Lazy Masquerade (1.2M)
- Mythology: See U in History/Mythology (2.36M), Mythology Explained (1.2M)
- Mystery: Mysteries Explained (800k), Strange Mysteries Daily (600k)
- Top X: WatchMojo (19.5M), Nuked Top 5 (3.2M)
- Finance: Humphrey Yang (3.4M), Bald Guy Money (1.8M)
- Facts: Today I Found Out (2.1M)
