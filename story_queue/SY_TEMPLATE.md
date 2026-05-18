# SY_NN_<S|R|H>_<slug> — <title>

**Status:** QUEUED
**Subgenre:** survival | reddit | horror
**Voice:** Charlie | Brian | Daniel | Rachel | Bella | Domi | Elli | Nicole
**Narrator gender:** M | F
**Model:** eleven_turbo_v2 | eleven_multilingual_v2

> Voice / Narrator-gender notes:
> - First-person female narrator (e.g. "my husband", "my wife noticed") → set `Narrator gender: F`
> - First-person male narrator → set `Narrator gender: M`
> - The scaffold reads these in priority order: explicit `Voice:` > `Narrator gender:` default > sub-genre template default
> - Per-sub-genre menu by gender lives in `scripts/story_script_writer.py:VOICE_MENU`
> - Horror+F default = Nicole (intimate whisper); Horror+M default = Daniel (British formal)
> - Reddit+F default = Rachel; Reddit+M default = Brian
> - Survival+F default = Domi; Survival+M default = Charlie

## Premise
[1-2 sentences. The core story idea — not the script. Claude writes the script at production time using story_script_writer.py templates AND fills in per-beat `visual_brief` + `sound_brief` per scripts/story_writer_prompt.md.]

## Hook angle
[One sentence describing the formula application (current TikTok-first violation/wrongness-first rules):
 - survival: "[Threat/violation in 4-5 words]. [Context after.]"  e.g. "Footprints. Inside my cabin. While I slept."
 - reddit:   "My [relation] [outrageous action in 5 words]. AITA?"  e.g. "My neighbor destroyed my daughter's garden. AITA?"
 - horror:   "[Wrong detail in 4-5 words]. [Mundane context after.]"  e.g. "The lock is on the wrong side. From the basement, you can't get out."

The pre-May-2026 "Day [N] of [scenario]" survival formula is DEPRECATED — it buries the violation. Always lead with the threat/wrongness.]

## Protagonist (survival only)
[Physical + voice description for continuity across episodes. e.g. "tall man late 30s, weathered face, dark hair, faded blue jacket, dirt-smudged."]

## Visual style notes
[Any sub-genre overrides. Defaults inherit from story_script_writer.TEMPLATES.]
- Palette: [optional override]
- Avoid: [e.g. "modern cars" for a period setting]

## Notes
[Anything Claude needs to know — series number for numbered survival, source inspiration (Reddit URL for dramatizations — paraphrase, never quote), specific horror trope being subverted.

NOTE: per-beat `visual_brief` and `sound_brief` are auto-scaffolded by story_script_writer.py and filled in by the writer at production time, not by the human queueing the entry. The queue file only carries premise/hook-angle/protagonist-continuity/source-URL.]
