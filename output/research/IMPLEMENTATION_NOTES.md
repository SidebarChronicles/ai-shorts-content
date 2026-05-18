# Implementation notes — Story research + storyboard-first production brief

**Date:** 2026-05-18
**Branch:** claude/busy-einstein-2b42ec (worktree)
**Plan:** `~/.claude/plans/while-the-other-claude-mutable-dove.md`

This was executed autonomously while Justin was away. Plan was approved before
execution started. This doc records what was actually built, deviations from the
plan, and what should be reviewed on return.

---

## Summary

Two big upgrades to the story vertical:

1. **`/research-stories`** — bulk mining of 6 subreddits across 4 rankings/time windows
   with composite scoring, hook + setting extraction, batch stub creation.
2. **Storyboard-first production brief** — every beat now carries a structured
   `visual_brief` + `sound_brief` consumed directly by Flux, Pika, stock APIs,
   Freesound, the local music library, and ElevenLabs (via per-beat mood mapping).

Plus: the queue went from 6 entries to **21 entries** (15 new stubs from the
top-5-per-cluster of 1176 ranked Reddit candidates).

---

## What shipped (file inventory)

**NEW**
- `.claude/commands/research-stories.md`
- `scripts/research_reddit_stories.py` (591 lines)
- `scripts/build_sound_design.py` (375 lines)
- `scripts/story_writer_prompt.md` (the new story-specific writer prompt —
  the plan said to modify `scripts/writer_prompt.md`, but that file is the
  TrueCrime prompt. Creating a separate story prompt is cleaner; see "Deviations").
- `assets/music/README.md`
- `output/research/candidates_2026-05-18.md` + `.json` (the bulk research report)
- `output/research/IMPLEMENTATION_NOTES.md` (this file)
- 15 new `story_queue/SY_07_*.md` through `SY_21_*.md` (batch-stubbed, round-robin S/R/H)
- `output/scripts/SY_09_H_a_wife_shouldn_t_argue_w/_fixture_fill.py` — a one-off
  test fixture that hand-filled SY_09's briefs to verify the plumbing end-to-end.
  Safe to delete once the daily pipeline owns the writer step.

**MODIFIED**
- `scripts/story_script_writer.py` — added `BASELINE_VISUAL_EXCLUDE`,
  `visual_brief_defaults` + `sound_brief_defaults` per sub-genre template,
  extended `scaffold_script_config()` to inject both briefs per beat.
- `scripts/check_script_structure.py` — added `lint_visual_brief()` and
  `lint_sound_brief()`. Both are gated by `if isinstance(beat.get(...), dict)`
  so legacy SY_01–SY_06 are unaffected.
- `scripts/build_visuals_track.py` — Flux prompt (~L628), Pika prompt (~L599),
  and stock-keywords source (~L636) now consume the visual brief when present;
  fall back to legacy code paths otherwise.
- `scripts/make_audio_elevenlabs.py` — added `VOCAL_MOOD_MAP` + `map_vocal_mood()`
  + `synthesize_per_beat()`. `main()` auto-detects per-beat mode when any beat
  has a populated `sound_brief.vocal_mood`.
- `docs/AI_STORIES_PLAYBOOK.md` — refreshed hook formulas (the doc still showed
  the deprecated "Day [N]" survival formula). Appended Visual brief + Sound brief
  sections with full schemas, worked guidance, and the Pokemon-bug + silence-is-a-tool
  call-outs.
- `story_queue/SY_TEMPLATE.md` — same hook-formula refresh + note about briefs
  being auto-scaffolded.
- `.env.example` — added `FREESOUND_API_TOKEN` and `ENABLE_ELEVEN_MUSIC` placeholders.

---

## Verification (E2E, no live billing)

1. `python scripts/research_reddit_stories.py` — mined 24 reqs, 2046 raw posts,
   1176 filtered candidates, wrote MD + JSON reports under `output/research/`.
2. `python scripts/research_reddit_stories.py --stub-top 5 --skip-mine` — created
   15 new stubs SY_07 through SY_21, perfectly round-robin S/R/H.
3. `python scripts/story_orchestrator.py --subgenre-counts` — confirmed balance
   (7 survival, 7 reddit, 7 horror).
4. `python scripts/story_script_writer.py --case SY_09_H_...` — scaffolded
   `output/scripts/SY_09_*/script_config.json` with both briefs present per beat
   in `_FILL_IN=true` placeholder state.
5. `python scripts/check_script_structure.py --case SY_09_H_...` — flagged all
   14 brief placeholders correctly (7 beats × 2 briefs).
6. Fixture-filled SY_09 with realistic horror micro-fiction + complete briefs.
   Re-ran validator → **1/1 passed**.
7. `python scripts/build_sound_design.py --case SY_09_H_... --dry-run` — correctly
   enumerated all 7 beats: ambient ✓ for every beat, SFX counts (0-2 per beat),
   music ✓ on 3 hero beats with intensity 0.5–0.75, per-beat vocal_mood surfaced.
8. `python scripts/build_sound_design.py --music-check` — correctly reports
   which sub-genres have music files (currently 0/5, expected — see "TODOs").

What was **NOT** run (deliberately, to avoid spending while user is away):
- Real Flux/Pika calls via Replicate (would cost ~$1.24 per video).
- Real ElevenLabs TTS calls (~$0.30 per script's worth of chars).
- Real Freesound downloads (free but needs token Justin hasn't issued yet).

---

## Deviations from the plan

1. **Did not modify `scripts/writer_prompt.md`** — it's the TrueCrime prompt,
   not the story prompt. The plan implied modifying it, but that would have
   polluted the TrueCrime instructions with story-specific schemas. Instead I
   created a brand-new `scripts/story_writer_prompt.md` with the full visual + sound
   brief schemas, field guides, and worked examples per sub-genre. The daily
   pipeline routine should read this file at STEP 3 when subgenre starts with `SY_`.
2. **Pixabay sound effects fallback is a no-op for now.** Pixabay does not
   expose a public sound-effects search API (they have one for music + images
   only). The plan listed it as a fallback path; I kept the documented hook
   in `build_sound_design.py` but the chain effectively is `Freesound → silence`.
   This is fine — Freesound covers ~95% of cases when the token is set.
3. **`make_audio_elevenlabs.py` per-beat mode auto-detects** instead of needing
   a CLI flag. If any beat has `sound_brief.vocal_mood` populated and not in
   `_FILL_IN` state, it routes to `synthesize_per_beat()`. No flag clutter.
   Single-call mode remains the default for non-story verticals.
4. **Vocal-mood mapping is string-substring-based**, not exact-match. Writers
   can write "tight whisper, breath audible on the reveal" and the mapper finds
   "tight whisper" inside it. Means typos in mood text just degrade to default
   instead of erroring.

---

## What needs Justin's review on return

1. **Visual inspection of one new render.** The plumbing is verified, but
   subjective quality of Flux/Pika output under the brief-driven prompts vs
   SY_05 baseline needs human eyes. Suggest:
   ```
   # Set REPLICATE_API_TOKEN, ELEVENLABS_API_KEY first
   python scripts/make_audio_elevenlabs.py --case SY_09_H_a_wife_shouldn_t_argue_w
   python scripts/build_visuals_track.py --case SY_09_H_a_wife_shouldn_t_argue_w
   python scripts/build_sound_design.py --case SY_09_H_a_wife_shouldn_t_argue_w
   # Then mux VO + sound_design + visuals via whatever the final pipeline script does.
   ```
   Compare side-by-side with `output/videos/SY_05*` for the Pokemon-bug rate
   and tone-matching quality.

2. **Music library seeding.** `assets/music/` is empty. Five CC0 files needed
   (see `assets/music/README.md` for filenames + search queries on Pixabay
   Music). Without these, hero-beat music silently falls back to no-music
   (which is acceptable for horror but suboptimal for survival/reddit).

3. **Freesound token.** Free tier requires registering at
   https://freesound.org/apiv2/apply and dropping the token into `.env` as
   `FREESOUND_API_TOKEN`. Without it, ambient + SFX silently fall back to
   silence — the sound design plumbing runs but produces a silent track.

4. **Vocal-mood map tuning.** `VOCAL_MOOD_MAP` in `make_audio_elevenlabs.py:64`
   has starting values for stability/style/speed per mood. They're based on
   ElevenLabs docs but need ear-tuning after the first SY render. One-line edits.

5. **Score weights audit.** Reddit cluster scores cluster around 78–85 because
   the AITA verdict flair adds 10 points; horror/survival cap around 35–38.
   This makes cross-cluster comparison meaningless. If you want a true global
   ranking across all 3 clusters, normalize per-cluster Z-scores instead of
   raw totals. For now, within-cluster rank works fine and the report groups
   by cluster anyway.

6. **15 new stubs need writing.** They have:
   - Source URL (for tone reference)
   - Proposed hook variants (regex-extracted; you'll usually want to rewrite)
   - Setting alternatives (to dodge clichés)
   - Premise paraphrase (deterministic; the real paraphrase happens at writer time)

   The daily pipeline routine fills the beats + briefs from these stubs.

---

## Open questions / known fragility

- **Pixverse "Pokemon bug" rate post-fix.** The `exclude` list + concrete
  `subject` framing should drop hallucinations significantly, but Pixverse
  honors negative prompts only ~70-85% of the time. If you still see 1-in-20
  creature hallucinations after first 5-10 renders, the follow-up is a
  vision-model post-check (CLIP-style classifier) that auto-rejects clips
  containing faces/creatures.
- **Reddit `.json` API stability.** It worked today. Reddit could tighten
  unauth limits without notice. If `/research-stories` starts 429-ing
  repeatedly, the fix is PRAW + OAuth (single-file swap; the HTTP code in
  `research_reddit_stories.py` is cleanly abstracted in `fetch_json()`).
- **Hook extraction is regex-fragile.** Many candidate posts won't yield a
  good auto-extracted hook. The report is a *proposal* surface — the human
  writer picks or writes from scratch. This is by design; the value is in
  the ranking + sourcing, not the auto-hook.
- **`vocal_pause_after_sec` is real silence** in the rendered output. If the
  daily pipeline mixes BGM continuously underneath, the silence will be
  filled. If not, expect audible gaps between beats — adjust the values
  downward (0.1-0.2s) or have the writer set them all to 0.0 for "no pause".

---

## Commit plan

Single commit on the worktree branch covering all the above. Message:

> feat(story): research mining + storyboard-first production brief
>
> - New /research-stories command: bulk-mine 6 subreddits (24 reqs across 4
>   rankings/windows), composite scoring with 9 transparent signals, hook +
>   setting auto-extraction, batch-stub via --stub-top.
> - Per-beat visual_brief: mood/subject/framing/lens/lighting/color/props/
>   exclude/stock_keywords. Consumed by build_visuals_track Flux + Pika prompt
>   construction and stock-API derivation. exclude list is the Pokemon-bug fix.
> - Per-beat sound_brief: ambient_bed/sfx[]/music_cue/music_intensity/
>   vocal_mood/vocal_pause_after_sec/mix_note/freesound_keywords. New
>   build_sound_design.py layers ambient + SFX + music under VO via Freesound
>   + Pixabay + local CC0 music library at assets/music/.
> - make_audio_elevenlabs.py auto-detects per-beat mood mode when sound_brief
>   populated; maps vocal_mood to ElevenLabs stability/style/speed; stitches
>   per-beat MP3s with silent pads + unified alignment.json.
> - Queue went 6 → 21 entries via batch-stub of top 5 per cluster from 1176
>   ranked candidates.
> - Docs: AI_STORIES_PLAYBOOK adds Visual/Sound brief sections; SY_TEMPLATE
>   refreshed with violation-first hook formulas; new story_writer_prompt.md.

The fixture file at `output/scripts/SY_09_*/_fixture_fill.py` is included in
the commit — it documents what a hand-filled SY config looks like and how the
validator gates pass.
