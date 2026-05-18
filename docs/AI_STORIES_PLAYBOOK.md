# AI Stories Playbook

The DROP channel's 7th vertical: AI-generated narrative shorts. Three sub-genres rotate inside this vertical, sharing the production pipeline but with distinct writing rules, voices, and visual signatures.

---

## Why this vertical exists

Research (May 2026) shows AI-narrative Shorts retain at **65-75% APV** versus 50-60% for our other categories. Top channels in the space — Mr. Creeps (1M), Chilling Tales for Dark Nights (445K), rSpace (117K) — combine AI-generated visuals with cliffhanger storytelling. We're entering this category as an experiment in Phase 1, then doubling down if it wins by Day 7.

---

## Three sub-genres

### Numbered survival/POV (SY_NN_S_*)

**Hook formula:** `"Day [N] of [scenario]. Today I [escalation]."`

| Element | Choice |
|---|---|
| Voice | Charlie (energetic) |
| Voice speed | 0.95 |
| Model | eleven_turbo_v2 |
| Visual palette | muted earth tones, high contrast, slightly desaturated, single light source |
| Character continuity | **same protagonist across episodes** (Flux prompts always include physical description) |
| Series arc length | 5-7 episodes per arc |
| CTA | "Day [N+1] tomorrow" — numbered cliffhanger |

**Production note:** Always check the queue for the next episode in any active arc before starting a new one. If `SY_01_S_lakecabin` through `SY_03_S_lakecabin` are DELIVERED but `SY_04_S_lakecabin` is QUEUED, prefer the in-arc next-episode over starting a new arc.

### Reddit dramatization (SY_NN_R_*)

**Hook formula:** `"AITA for [inflammatory action]? My [relation] [outrageous thing]."`

| Element | Choice |
|---|---|
| Voice | Brian (conversational) |
| Voice speed | 0.92 |
| Model | eleven_multilingual_v2 |
| Visual palette | warm domestic tones, naturalistic lighting, contemporary setting |
| Character continuity | none — rotates per video |
| CTA | "AITA?" / "Was I wrong?" — comment-bait |

**⚠️ ANTI-PLAGIARISM RULE — non-negotiable:**

Reddit posts ARE copyrighted by their authors. The script writer MUST rewrite source material into original prose:
- Different word choices (re-phrase every sentence)
- Restructured narrative arc (don't follow the same order as the source)
- Anonymized names, locations, specific identifying details
- Paraphrased dialogue
- No verbatim quoting

Use Reddit threads as **inspiration**, not script. The "Premise" field in the queue entry should describe the *situation* and the *hook*, not the actual post text.

### Horror micro-fiction (SY_NN_H_*)

**Hook formula:** `"[Mundane setup in 5-7 words]. [Single wrong detail in 4-5 words]."`

| Element | Choice |
|---|---|
| Voice | Daniel (slow, ominous) |
| Voice speed | 0.88 |
| Model | eleven_multilingual_v2 |
| Visual palette | near-monochrome, blue-black shadows, single warm light source, high contrast |
| Character continuity | first-person POV by default; brief external glimpses only |
| CTA | open ending or "Don't [verb] [object]" warning |

**⚠️ ORIGINALITY RULE — non-negotiable:**

No adapting existing creepypasta IP. Specifically forbidden:
- Slenderman, The Thin Man, anything Marble-Hornets adjacent
- SCP Foundation entities (any numbered or named)
- Backrooms / liminal spaces brand-specific (you can use "abandoned office building" but not "the Backrooms")
- Mr. Wisepuff and other named characters with active communities

Every horror story must be **Claude's original micro-fiction**. The premise can borrow tropes (haunted house, doppelganger, deep-sea creature, etc), but the specific entity, setting, and prose must be new.

---

## 7-beat structure (all sub-genres)

| Beat | Window | Purpose |
|---|---|---|
| 1. hook | 0-2.5s | ≤12 words. Sub-genre's hook formula. |
| 2. setup | 3-15s | Frame the situation. |
| 3. build | 15-28s | Add stakes, tee up the mid_anchor. |
| 4. **mid_anchor** | 28-33s | **HERO SHOT (Pika clip).** Discovery / twist / realization. |
| 5. expand | 33-45s | Pay off the anchor. |
| 6. payoff | 45-55s | **HERO SHOT (Pika clip).** Resolution or final escalation. |
| 7. cta | 55-60s | Sub-genre-specific close. |

The two **HERO SHOT** beats (mid_anchor + payoff) trigger Pika 2.0 video generation in `build_visuals_track.py`. All other beats use Flux 2 Pro stills + Ken Burns motion.

---

## Cost model

Per video:
- 8 Flux 2 Pro stills × $0.03 = **$0.24**
- 2 Pika 2.0 hero clips × $0.50 (5 seconds each) = **$1.00**
- **Total: ~$1.24/video**

At 8 videos/day total across 7 verticals, story gets ~1.1/day → **~34 videos/month** → **~$42/mo Replicate spend**.

Soft cap in `.channel_phase.json`: `story_budget_softcap_usd: 130`. Plenty of headroom.

---

## YouTube policy survival (Jan 2026 enforcement context)

YouTube terminated 16 channels (35M combined subs) for template-cloned AI bulk-production. Survival depends on:

**✅ Green signals we project:**
- Original scripts per video (Claude writes, no template-copy)
- 3 sub-genres rotating = production variation
- Cadence ~1.1 story videos/day, well below the bot-volume threshold
- Music attribution + AI-narration disclosure in every description (already automated)
- Human editorial oversight at each phase transition

**❌ Red flags we avoid:**
- No 12+ identical uploads/day
- No template clones (each video has a unique hook + situation)
- No static AI slideshows (Ken Burns motion + Pika hero shots)
- No verbatim Reddit copying (anti-plagiarism rule)

---

## Character consistency strategy

**Numbered survival (S):** same protagonist across an arc. Flux prompts always include the protagonist's physical description from the queue's `Protagonist:` field. No LoRA training in v1; prompt-engineering with consistent physical-description tokens. If retention validates the format by Day 7, evaluate LoRA training as a Phase 2 upgrade (~4h one-time cost per character).

**Reddit (R):** no continuity needed. Rotates per video.

**Horror (H):** first-person POV by default — the "protagonist" is the camera. Brief external glimpses of hands or reflections only. The threat may be partially revealed in mid_anchor and fully shown in payoff; keep its visual design consistent **within** a video.

---

## Pipeline files

| File | Role |
|---|---|
| `story_queue/SY_NN_*.md` | Premise + hook angle queue (one entry per video) |
| `scripts/story_orchestrator.py` | Queue state machine (QUEUED → RENDERED → DELIVERED) |
| `scripts/story_script_writer.py` | Sub-genre templates + scaffold generator for `script_config.json` |
| `scripts/replicate_flux.py` | Flux 2 Pro wrapper (still images) |
| `scripts/replicate_pika.py` | Pika 2.0 wrapper (hero clips) |
| `scripts/build_visuals_track.py` | Wires the full chain: Pexels → Pixabay → Flux → Pika (hero shots) |
| `scripts/make_audio_elevenlabs.py` | Reads voice_speed + voice_id from sub-genre template |
| `scripts/check_script_structure.py` | Pre-render lint: hook ≤12 words, mid_anchor at 28-33s |
| `output/scripts/SY_NN_*/audio_mixed.mp3` | Final mixed audio (gitignored) |
| `output/scripts/SY_NN_*/visuals_raw/` | Per-beat Flux PNGs + Pika MP4s (gitignored) |
| `output/scripts/SY_NN_*/clips_portrait/` | 1080×1920 portrait clips for concat (gitignored) |
| `output/ai_cache/flux/` + `output/ai_cache/pika/` | Idempotency caches; re-prompts don't re-bill |

---

## Content ID dispute (if a Pika clip ever gets flagged)

Pika outputs are AI-generated and not copyrightable by anyone else (Pika's TOS grants commercial use to the user). If a video gets a Content ID claim citing the Pika output:
1. Open the claim in YouTube Studio
2. Click Dispute → "I generated this content with AI tools (Pika Labs)"
3. Reference Pika's commercial-use license: https://pika.art/legal/terms-of-service

For Flux outputs: same path — Replicate's Flux 2 Pro terms grant commercial use.

For Kevin MacLeod music: see `docs/MUSIC_ATTRIBUTION.md` — disputes filed via the existing CC-BY 4.0 process.
