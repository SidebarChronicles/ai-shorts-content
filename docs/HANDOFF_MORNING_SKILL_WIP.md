# Handoff — Morning skill WIP (paused 2026-05-18 evening)

User stepped away mid-build. Repo is in a **clean, committable state** — no uncommitted edits, no half-applied refactors. Just unfinished work.

## What's done (committed on branch `claude/busy-einstein-2b42ec`)

Latest 3 commits:
- `d3d84ef chore(cleanup): remove dangling refs to deleted scheduled-tasks routine`
- `17cd5f6 chore(cleanup): drop orphan writer_prompt, delete SY_09 fixture, move impl notes`
- `9d5bf39 Merge remote-tracking branch 'origin/main' into claude/busy-einstein-2b42ec` (brings in `scripts/post_via_scheduler.py` from main's PostFast work)

**State right now:**
- ✅ Pre-flight merge complete — PostFast TikTok upload available at `scripts/post_via_scheduler.py`
- ✅ Cleanup chunk 1: orphan `scripts/writer_prompt.md` deleted, `_fixture_fill.py` deleted, `IMPLEMENTATION_NOTES.md` moved to `docs/STORYBOARD_BRIEFS_IMPL_NOTES_2026-05-18.md`
- ✅ Cleanup chunk 2: dangling routine refs fixed in CHANNEL_STATUS, RELEASE_SCHEDULE, MUSIC_ATTRIBUTION, story_script_writer, story_writer_prompt; REMOTE_TRIGGER.md archived
- ✅ Working tree clean (only `output/audio/` and `audio_mixed.alignment.json` untracked — both gitignored or expected artifacts)

## What's left (in order to pick up)

Approved plan lives at: `/Users/justinlee/.claude/plans/while-the-other-claude-mutable-dove.md` (Plan B section)

Remaining tasks (from task list):

1. **Build `scripts/morning_cleanup.py`** — daily hygiene script (archive old picks/candidates/reports, prune .part files). Plan B Part I.
2. **Build `scripts/render_story.py`** — the MISSING orchestrator. Chains the 11 steps I did manually for SY_09 into one idempotent script. Plan B Part C. **Most important new piece.**
3. **Build `scripts/suggest_tweaks.py`** — analytics → tweaks learner. Plan B Part A.
4. **Build `scripts/pick_today.py`** — 4-pick queue ranker. Plan B Part B.
5. **Build `scripts/schedule_uploads.py`** — TikTok-now + YouTube-prime-slot scheduler. Plan B Part D.
6. **Build 6 slash commands** (`.claude/commands/`): `cleanup.md`, `suggest-tweaks.md`, `pick-today.md`, `render-batch.md`, `schedule-uploads.md`, `morning.md`. Same format as existing `analytics.md`. Plan B Part E.
7. **Update `.gitignore` + write `scripts/_README.md`** — Plan B Part F.
8. **Verify end-to-end** — dry-run `/morning` on one stub. Plan B Part G.

## To resume next session

```bash
# Confirm clean state
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel/.claude/worktrees/busy-einstein-2b42ec"
git status   # should be clean
git log --oneline -5

# Read the plan for the full architecture
less ~/.claude/plans/while-the-other-claude-mutable-dove.md

# Next move: start with scripts/render_story.py because everything else
# depends on it (suggest_tweaks/pick_today/schedule_uploads can run without
# it but the morning loop needs it). My SY_09 manual flow in this session's
# git log is the literal blueprint — every step is documented in commit
# bodies.
```

## Quick orientation

- **Story queue**: 81 stubs (`story_queue/SY_*.md`), 78 QUEUED, 2 RENDERED, 2 DELIVERED.
- **Rendered SY_09** (the test case for the new storyboard-first system) is at `output/story_videos/SY_09_H_a_wife_shouldn_t_argue_w.mp4` — uses Rachel voice + karaoke fix.
- **Spend so far this session**: ~$1.81 on SY_09 (3 EL passes × $0.20 + Flux/Pika $1.21).
- **Branches**: this branch is 5 commits ahead of origin/main. None pushed. PostFast TikTok work is now merged in here.

## Decisions locked from the planning Q&A

- Architecture: **chained commands + thin `/morning` orchestrator**
- Edit depth: **Medium — learner writes `suggested_tweaks.md` for human review, never auto-edits queue**
- Batch size: **fixed 4 videos/morning** (~$7.25/day spend; flagged as 2× the $100/mo target — user accepted)
- TikTok upload: **`scripts/post_via_scheduler.py` from main (PostFast, ~$15/mo)**
- Prime times (v1 fixed): **8:00 / 12:30 / 18:30 / 21:30 ET** for YouTube `--publish-at` slots; TikTok posts at `/morning` invoke time (PostFast doesn't schedule)
