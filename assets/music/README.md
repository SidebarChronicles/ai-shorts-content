# assets/music — Story hero-beat music library

Small CC0 / royalty-free music library that `scripts/build_sound_design.py` selects
from when a beat's `sound_brief.music_intensity >= 0.5` (hero beats).

The library is **manually seeded** — no script auto-downloads. This is intentional:
licensing on free-music sites is fluid, and a human-curated library prevents
accidental attribution-required clips from sneaking in.

## Required files (drop these in, ~30s each)

| Filename                       | Mood              | Used by sub-genre           |
| ------------------------------ | ----------------- | --------------------------- |
| `dread_drone_a.mp3`            | Low drone, dread  | Horror (H) hero beats       |
| `dread_drone_b.mp3`            | Variant of above  | Horror — rotation           |
| `tension_pulse_a.mp3`          | Rising pulse      | Survival (S) hero beats     |
| `tension_pulse_b.mp3`          | Variant           | Survival — rotation         |
| `social_curiosity_a.mp3`       | Curious, neutral  | Reddit (R) hero beats       |

## Where to source (NO ATTRIBUTION REQUIRED)

Use these search queries on **Pixabay Music** (https://pixabay.com/music/):
- Horror drones: search `"horror drone"`, `"dark ambient"`, `"suspense pad"` → CC0 by default
- Tension pulse: search `"cinematic tension"`, `"suspense pulse"`, `"rising tension"` → CC0
- Social/curiosity: search `"corporate curious"`, `"thoughtful piano"`, `"narration bed"` → CC0

**Pixabay Music license**: https://pixabay.com/service/license-summary/ — free for commercial use,
no attribution required. Verify the specific clip page shows the "Pixabay License" tag
(not Creative Commons, which sometimes requires attribution).

## Anti-patterns

- Do NOT use YouTube Audio Library tracks — many require channel attribution.
- Do NOT use CC-BY clips — they require artist credit in the video description, which
  the upload script currently doesn't enforce.
- Do NOT pull from Epidemic Sound or Artlist — those require subscriptions and per-channel
  registration.
- If a clip has a YouTube monetization claim attached, drop it (causes Content ID claims
  even on Shorts).

## Adding files

1. Download the .mp3 from Pixabay Music.
2. Trim to ~30s using `ffmpeg -ss 0 -t 30 -i raw.mp3 -c copy out.mp3` (or in any DAW).
3. Save with the exact filename above.
4. Test: `python scripts/build_sound_design.py --case <case_id> --music-check`

If `assets/music/` is empty or missing the required file for a sub-genre, the renderer
falls back to: ElevenLabs Music API (if `ENABLE_ELEVEN_MUSIC=1`) → no music (the hero
beat plays with just VO + ambient + SFX, which often still works for horror).
