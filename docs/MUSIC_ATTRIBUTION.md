# Music attribution (CC-BY 4.0 — Incompetech / Kevin MacLeod)

All background music tracks in `assets/music/<vertical>/` are licensed under
**Creative Commons Attribution 4.0 International (CC-BY 4.0)**.

Source: [incompetech.com](https://incompetech.com) by Kevin MacLeod.

The license requires that each YouTube video using these tracks includes an
attribution line in its description. Without it, the license is technically
violated (YouTube does not enforce this — but it's still required).

## The required boilerplate

Drop these two lines into every new video's description block, just before
the hashtags:

```
🎵 Music: Kevin MacLeod (incompetech.com) — Licensed under CC-BY 4.0
    https://creativecommons.org/licenses/by/4.0/
```

That's it. One line of credit + the license URL.

## Where it's auto-injected

- ✅ `scripts/game_orchestrator.py` — the `description_parts` block adds it
  to every `output/game_videos/*.description.md` it writes (per the May 18
  edit).

## Where you (or Claude during the routine) need to add it manually

The 5 non-game orchestrators are queue managers, not description writers —
descriptions for those verticals are written by Claude when the daily-shorts
routine fires. Until the SKILL.md template is updated, paste the attribution
line manually when generating sidecars for:

- `output/movie_videos/*.description.md`
- `output/mythology_videos/*.description.md`
- `output/mystery_videos/*.description.md`
- `output/topx_videos/*.description.md`
- `output/finance_videos/*.description.md`

To make this automatic across all verticals, add the attribution boilerplate
to the description-sidecar step inside `scripts/render_story.py` (or whichever
description-sidecar producer the `/morning` workflow uses for each vertical).

## Where it does NOT apply

- The 18 live videos uploaded before May 18, 2026 — they don't have
  Incompetech music in them (audio mixer was added after they shipped).
  Don't retroactively add the attribution to their descriptions; YouTube
  treats description edits as a churn signal.

## What happens if a track gets Content ID-flagged anyway

Some Incompetech tracks occasionally trip YouTube's Content ID system
because third parties have uploaded the same music to commercial
distributors. When that happens:

1. YouTube emails you about the claim
2. Open the video in YouTube Studio → Content → click the ⚠️ icon on the
   claimed video → Dispute → select "Creative Commons License" → paste the
   incompetech track URL + the CC-BY license URL as proof
3. YouTube resolves within 24h, claim is cleared

Estimated frequency: ~10-15% of Incompetech tracks have at least one
historical Content ID claim. The dispute process is reliable; no penalty
attached.

## Track inventory (May 18, 2026 — 22 tracks across 6 verticals)

| Vertical | Tracks |
|---|---|
| `games` | The Show Must Be Go, Bit Quest, Pinball Spring |
| `movies` | Wallpaper, Hitman, Long Note Four |
| `cases` | Sneaky Snitch, Investigations, Dark Times, Anguish |
| `mysteries` | Spy Glass, Mysterioso March, The Descent, The Builder |
| `mythology` | Five Armies, Tabuk, Eastern Thought, Long Note Two |
| `finance` | Cold Funk, Kool Kats, Inspired, Smooth Lovin |

All sourced from `https://incompetech.com/music/royalty-free/mp3-royaltyfree/<Title>.mp3`.
The build_audio_track.py mixer picks one at random per render.

To add more, just drop additional `.mp3` files into the right vertical
subfolder — no code changes needed.
