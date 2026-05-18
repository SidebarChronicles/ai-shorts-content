# AI Stories Playbook

The DROP channel's 7th vertical: AI-generated narrative shorts. Three sub-genres rotate inside this vertical, sharing the production pipeline but with distinct writing rules, voices, and visual signatures.

**Daily production workflow:** see [docs/MORNING_WORKFLOW.md](MORNING_WORKFLOW.md) for the `/morning` chained-skills routine that runs analytics → pick → render → schedule → research in ~20 minutes a day.

---

## Why this vertical exists

Research (May 2026) shows AI-narrative Shorts retain at **65-75% APV** versus 50-60% for our other categories. Top channels in the space — Mr. Creeps (1M), Chilling Tales for Dark Nights (445K), rSpace (117K) — combine AI-generated visuals with cliffhanger storytelling. We're entering this category as an experiment in Phase 1, then doubling down if it wins by Day 7.

---

## Three sub-genres

### Numbered survival/POV (SY_NN_S_*)

**Hook formula (current, TikTok-first violation-first):** `[Threat/violation in 4-5 words]. [Context after.]`
Good: `"Footprints. Inside my cabin. While I slept."`
Bad (deprecated May 18 2026 — buries the violation): `"Day 1 of being snowed in. I'm not alone out here."`

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

**Hook formula (current, violation-first then AITA):** `"My [relation] [outrageous action in 5 words]. AITA?"`
Good: `"My neighbor destroyed my daughter's garden. So I fenced him out. AITA?"`
Bad (deprecated — question-first buries the violation): `"AITA for putting up a fence after my neighbor mowed my lawn?"`

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

**Hook formula (current, wrong-detail-first):** `"[Wrong detail in 4-5 words]. [Mundane context after.]"`
Good: `"The lock is on the wrong side. From the basement, you can't get out."`
Bad (deprecated — buries the wrongness): `"The basement door has a lock. The lock is on the wrong side."`

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

## Visual brief (per beat — added May 2026)

Every beat in a new SY script carries a structured `visual_brief` that the rendering pipeline consumes directly. The brief replaced the earlier "truncate first 4 words of beat text and hope" approach. The full schema and field guide live in [`scripts/story_writer_prompt.md`](../scripts/story_writer_prompt.md); the highlights:

```json
"visual_brief": {
  "mood":            "dread, claustrophobic",
  "subject":         "weathered wooden door, deadbolt facing camera",
  "framing":         "medium close-up, eye-level, centered",
  "lens":            "35mm, shallow DOF",
  "lighting":        "single warm bulb overhead, hard shadow underneath",
  "color":           "near-monochrome, blue-black shadows",
  "props":           ["deadbolt", "wood grain"],
  "exclude":         ["people", "creatures", "faces", "cartoon"],
  "stock_keywords":  ["wooden door", "deadbolt closeup", "basement door"]
}
```

**Why `exclude` matters (the Pokemon bug fix):** the original Pika hero generation hallucinated yellow cartoon creatures on SY_01 because narrative beat text leaked words like "they" and "watching" into the prompt. The current implementation strips narrative text from Pika prompts and *always* attaches the brief's `exclude` list as a negative prompt, plus auto-appends `["people","creatures","faces","characters"]` even if the writer forgot. Combined with concrete `subject` framing (which displaces creature priors in latent space), this drops hallucinations toward zero. The keyword-only fallback at `build_visuals_track.py:599` is kept for legacy SY_01-SY_06 only.

**Stock-API derivation:** `stock_keywords` is the *only* field that hits Pexels/Pixabay. Separating "human search terms" from "AI visual brief" means stock fallbacks get tone-matched results ("derelict cabin interior") instead of generic ones ("cabin").

---

## Sound brief (per beat — added May 2026)

The story pipeline used to render TTS over silent clips. Now every beat carries a `sound_brief` that drives ambient bed + SFX hits + music cue + per-beat vocal mood. New scripts pipeline:

```
beat.text          → make_audio_elevenlabs.py        (per-beat TTS, mood-mapped voice_settings)
beat.visual_brief  → build_visuals_track.py          (Flux/Pika/stock)
beat.sound_brief   → build_sound_design.py           (ambient + SFX + music layers)
                  → final mux (VO + sound_design + visuals)
```

```json
"sound_brief": {
  "ambient_bed":           "low wind through pine, distant snowmelt drip",
  "sfx": [
    {"at_sec": 0.0,  "name": "door creak slow",      "gain_db": -8},
    {"at_sec": 2.5,  "name": "match strike + flame", "gain_db": -10}
  ],
  "music_cue":             "low drone, ascending tension over 3s",
  "music_intensity":       0.35,
  "vocal_mood":            "tight whisper, slow tempo, breath audible",
  "vocal_pause_after_sec": 0.4,
  "mix_note":              "ambient -18db under VO, sfx ducks VO -4db on hits",
  "freesound_keywords":    ["pine wind", "snow drip", "door creak"]
}
```

**Why sound design matters:**
- **Silence is a tool, especially in horror.** The mid_anchor reveal beat should drop `music_intensity` to 0.0 for half a second; the absence-of-music IS the impact.
- **Sidechain ducking keeps narration clear.** Ambient sits -18db under the VO; SFX hits duck the VO -3db so they read; music sidechains to the VO envelope so it gets out of the way during words.
- **Per-beat vocal_mood reshapes TTS.** ElevenLabs `stability`/`style`/`speed` go from default (0.5/0.5/1.0) to "tight whisper" (0.75/0.85/0.88) per beat. The mapping is in `scripts/make_audio_elevenlabs.py:VOCAL_MOOD_MAP` — one-line tweak for tuning after the first SY render.

**Recommended intensity profile per sub-genre:** see [`scripts/story_writer_prompt.md`](../scripts/story_writer_prompt.md) — short version: Horror is silence-dominant with a single music spike on mid_anchor; Survival builds steadily; Reddit stays near-naked with one swell on the verdict reveal.

**Sourcing chain (mirrors visuals):**
1. **Freesound API** (free, CC0/CC-BY) — needs `FREESOUND_API_TOKEN` in `.env`
2. **Pixabay sound effects** (no auth) — fallback (limited; Pixabay's public SFX search is sparse)
3. **Silence** — final fallback, never blocks the render

For hero-beat music: small CC0 library at `assets/music/` (manually seeded — see `assets/music/README.md`). Optional `ENABLE_ELEVEN_MUSIC=1` flips on the paid ElevenLabs Music API as backup.

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
| `scripts/build_visuals_track.py` | Wires the full chain. **Story vertical is AI-first**: Flux → Pexels → Pixabay (stock as safety net). Hero beats (mid_anchor + payoff) additionally try Pika 2.0 for real video clips. Other verticals stay stock-first. |
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
