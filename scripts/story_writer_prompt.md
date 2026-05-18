# Story Writer Prompt — AI Stories (storyboard-first)

Read by Claude during the `/morning` workflow when producing SY_NN_* shorts. The
scaffold from `scripts/story_script_writer.py` provides the 7-beat structure,
voice settings, and sub-genre-specific defaults. Your job is to fill in beat
text + visual brief + sound brief per beat, then run the validator.

This prompt is sub-genre-aware. Read `script_config.json` first — the `subgenre`
field tells you which template's rules apply.

---

## Non-negotiable rules

1. **No verbatim copying from any Reddit source.** If `Notes` in the queue file links a source URL, treat it as TONE reference only. Rewrite the story completely: different word choices, restructured narrative, anonymized names + locations, paraphrased dialogue. Verbatim risks a YouTube strike.
2. **Hook follows the sub-genre formula** from `hook_template` in `script_config.json`. Lead with the violation / wrong-detail / threat. Never start with "The…/A…/An…/In…/So I…/Hey…".
3. **7 beats. ~50s total spoken.** Per-beat `target_seconds` and `max_seconds` are in the scaffold. Don't blow past them.
4. **Every beat gets a `visual_brief` AND a `sound_brief`.** Empty briefs fail validation and stall the render. See schemas below.
5. **Horror = original micro-fiction only.** No Slenderman, SCP, Backrooms, Mr. Wisepuff, etc. Tropes are fine (haunted house, doppelganger); specific IP is not.
6. **Voice must match POV gender.** If the protagonist/narrator is female (first-person, e.g. "my husband", "my wife noticed"), set `Narrator gender: F` in the queue file BEFORE scaffolding — or override directly with `Voice: <name>`. The scaffold picks the sub-genre-appropriate female voice from `VOICE_MENU` (Nicole for horror, Rachel for reddit, Domi for survival). The default for every sub-genre is a male voice, so silence here = male narrator. Mismatched-gender narration is the single biggest immersion-killer in AI shorts.

---

## Beat-text rules

- Active voice, present tense for tension.
- Concrete nouns over abstractions ("the deadbolt" beats "the lock"; "her hands" beats "everything").
- Numbers spelled out for TTS ("twelve" not "12"; "two-thirty AM" not "2:30 AM").
- Avoid filler: "I'm telling you", "you won't believe", "like, seriously".
- Mid-anchor beat (beats[3]) MUST land at 28-33s and carry a numeric stat OR contradiction marker ("but", "actually", "however", "except"). The validator enforces this.

---

## Visual brief schema (per beat — fill into beats[i].visual_brief)

```json
{
  "mood": "dread, claustrophobic",
  "subject": "weathered wooden door, deadbolt facing camera",
  "framing": "medium close-up, eye-level, centered",
  "lens": "35mm, shallow DOF",
  "lighting": "single warm bulb overhead, hard shadow underneath",
  "color": "near-monochrome, blue-black shadows, warm bulb highlight",
  "props": ["deadbolt", "wood grain", "scratched paint"],
  "exclude": ["people", "creatures", "faces", "modern hardware", "yellow", "cartoon"],
  "stock_keywords": ["wooden door", "deadbolt closeup", "basement door"]
}
```

### Visual brief field guide

- `mood` — 1-3 adjectives. Drives the emotional tone. Examples: "dread, claustrophobic", "tense, isolated", "confiding, slightly indignant".
- `subject` — concrete noun phrase. **This is the single most important field** — it displaces creature priors in Flux/Pika's latent space and prevents the "Pokemon bug" hallucination. Write what the camera literally shows. "Weathered wooden door, deadbolt facing camera" — not "atmospheric scene" or "the threat".
- `framing` — shot type + angle + position. "Medium close-up, eye-level, centered", "wide low-angle, off-center", "POV looking down at hands".
- `lens` — focal length + DOF cues. "35mm, shallow DOF", "85mm portrait, sharp", "wide 24mm, deep focus".
- `lighting` — light source + direction + quality. "Single warm bulb overhead, hard shadow", "daylight through dirty window, soft shadow", "phone screen glow on face".
- `color` — palette description. "Near-monochrome, blue-black shadows", "warm domestic tones, mid-saturation", "muted earth tones, desaturated".
- `props` — list of concrete objects in frame. Helps Flux nail the scene.
- `exclude` — pre-seeded by the scaffold with creature/face/cartoon baselines. **Append** sub-genre-specific exclusions. Example: a 1950s setting → add `["modern cars", "smartphones", "LED lights"]`.
- `stock_keywords` — 2-6 short tone-matched search terms for Pexels/Pixabay fallback. "Derelict cabin interior" beats "cabin" by a mile.

### Visual brief worked example — Horror mid_anchor beat

```json
"visual_brief": {
  "mood": "frozen dread, breath-held",
  "subject": "shadow stretching across hardwood floor toward a closed door",
  "framing": "low-angle wide, floor-level, door centered in upper third",
  "lens": "24mm wide, deep focus",
  "lighting": "single light source from off-screen left, harsh shadow elongating right",
  "color": "deep blue-black, single warm highlight on door frame, no other color",
  "props": ["hardwood floor", "shadow", "door frame", "doorknob"],
  "exclude": ["people", "creatures", "faces", "cartoon", "fantasy", "smiling", "ghost imagery"],
  "stock_keywords": ["dark hallway shadow", "closed door night", "hardwood shadow"]
}
```

---

## Sound brief schema (per beat — fill into beats[i].sound_brief)

```json
{
  "ambient_bed": "low wind through pine, distant snowmelt drip, room tone -24db",
  "sfx": [
    {"at_sec": 0.0,  "name": "door creak slow",       "gain_db": -8},
    {"at_sec": 2.5,  "name": "match strike + flame",  "gain_db": -10}
  ],
  "music_cue": "low drone, no melody, ascending tension over 3s",
  "music_intensity": 0.35,
  "vocal_mood": "tight whisper, slow tempo, breath audible",
  "vocal_pause_after_sec": 0.4,
  "mix_note": "ambient -18db under VO, sfx ducks VO -4db on hits, music sidechained to VO",
  "freesound_keywords": ["pine wind", "snow drip", "door creak", "match strike"]
}
```

### Sound brief field guide

- `ambient_bed` — one continuous low-volume background layer for the beat. Drives place ("kitchen with fridge hum", "forest with wind in pine"). Always present, even if subtle.
- `sfx` — array of discrete hits with timing. `at_sec` is relative to the beat start (0.0 = beat start). `gain_db` is mix level (-30 to 0; default -8). The single most under-used tone tool — a 0.5s match strike on the right word changes everything. Use sparingly: 0-3 hits per beat.
- `music_cue` — natural-language description; renderer uses it as a hint but picks the actual music from `assets/music/<mood>/`.
- `music_intensity` — 0.0 to 1.0. **Hook beat ≤ 0.3 (let the violation line breathe). Hero beats (mid_anchor, payoff) 0.6-0.85.** 0.0 = no music for this beat — silence is a tool, especially on horror reveals.
- `vocal_mood` — direction the TTS engine maps to ElevenLabs voice_settings. Available moods (string-matched, case-insensitive): "whisper-adjacent", "tight whisper", "controlled tension", "confiding narrator", "slight indignation", "urgent", "shocked", "default". Combine in natural prose: "tight whisper, breath audible on the reveal".
- `vocal_pause_after_sec` — silent gap after this beat's narration ends. Lets sound design breathe. 0.3 is a safe default; 0.6+ for dramatic reveals; 0.1 for fast escalation.
- `mix_note` — natural-language mixing direction. Renderer honors hints like "ambient -22db under VO", "sfx ducks VO".
- `freesound_keywords` — 2-6 short search terms for the SFX/ambient library. Separates "AI brief" from "search query" (same pattern as visual `stock_keywords`).

### Sound brief intensity profile (recommended per sub-genre)

**Horror** — silence-dominant:
- Hook: intensity 0.2, ambient low, no music
- Setup/Build: 0.25-0.3, ambient room tone, no music
- mid_anchor: 0.7 with abrupt drop to 0.0 on reveal (the silence IS the impact)
- Expand: 0.4, music returns at low level
- Payoff: 0.6, sustained dread
- CTA: 0.4, match-cut to hook ambient

**Survival** — building tension:
- Hook: 0.2 (threat sound + ambient)
- Setup: 0.25 (environment)
- Build: 0.35 (rising pulse)
- mid_anchor: 0.75 (escalation)
- Expand: 0.5 (sustained)
- Payoff: 0.65 (resolution chord OR cliffhanger sting)
- CTA: 0.4 (loop back to hook ambient)

**Reddit** — naturalistic, music sparse:
- Hook: 0.15 (room tone only — let the violation read)
- Setup/Build: 0.1 (no music; ambient only)
- mid_anchor: 0.6 (the verdict reveal swells)
- Expand: 0.3 (drops back)
- Payoff: 0.5 (resolves)
- CTA: 0.2 (back to room tone)

### Sound brief worked example — Survival mid_anchor beat

```json
"sound_brief": {
  "ambient_bed": "cold wind through pine, distant ice cracking, snow-muted room tone",
  "sfx": [
    {"at_sec": 0.5, "name": "snow crunch single footstep",   "gain_db": -6},
    {"at_sec": 3.2, "name": "branch snap distant",            "gain_db": -10}
  ],
  "music_cue": "rising pulse over 4 seconds, no melody, low brass swell",
  "music_intensity": 0.75,
  "vocal_mood": "controlled tension, slower than baseline, breath on the reveal",
  "vocal_pause_after_sec": 0.6,
  "mix_note": "ambient ducks -6db when sfx hit, music sidechained to VO",
  "freesound_keywords": ["wind pine forest", "snow crunch", "branch snap winter"]
}
```

---

## Output checklist before submitting

- [ ] All 7 beats have `text`, `visual_brief`, `sound_brief` filled in
- [ ] No `_FILL_IN: true` or `[FILL IN]` strings remain
- [ ] Hook beat ≤ 12 words, matches `hook_template`, doesn't start with forbidden filler
- [ ] mid_anchor (beats[3]) has a numeric stat or contradiction marker
- [ ] `stock_keywords` is 2-6 items per beat, each ≤4 words
- [ ] `exclude` list extends the baseline with sub-genre-specific terms
- [ ] `music_intensity` follows the recommended profile for the sub-genre
- [ ] Anti-plagiarism rule applied (Reddit-cluster especially): no verbatim sentences

Then run: `python scripts/check_script_structure.py --case <SY_NN_X_slug> --strict --fail-fast`
