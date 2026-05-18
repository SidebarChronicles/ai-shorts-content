---
description: Daily hygiene — archive stale picks/candidates/reports + prune leaked .part files and EL temp dirs. Dry-run by default; use --apply to act.
argument-hint: optional --apply  (without it = dry-run preview)
---

You are running inside Claude Code on Justin's Mac.

Run the cleanup pass. Default is dry-run (prints what would change without modifying anything). Pass `--apply` to actually move/delete.

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/morning_cleanup.py $ARGUMENTS
```

After it runs, report back:
- One-line summary (archive count + remove count + bytes freed)
- If anything notable was archived/removed (e.g. a delivered case dir)
- Whether `--apply` was used or if this was a dry-run

**Safety:** This script NEVER deletes pipeline-critical state. It only archives dated files (to `<dir>/archive/`) and removes leaked temp files (`*.part`, `/var/folders/.../el_perbeat_*`). Final mp4 files in `output/story_videos/` are never touched.

**If it shows lots of items to archive:** that's normal after a long stretch without cleanup. Re-run with `--apply` to act.

**If the script crashes:** check the latest stderr — most likely a permissions issue on `/var/folders/`. Safe to ignore the temp-dir prune and re-run.
