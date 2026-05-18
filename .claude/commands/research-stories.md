---
description: Mine r/nosleep, r/shortscarystories, r/AmItheAsshole, r/relationships, r/letsnotmeet, r/creepyencounters for ranked story candidates. Default = bulk mode (large base across multiple time windows). Use --stub-top N to batch-create queue stubs.
argument-hint: optional [--cluster horror|reddit|survival] [--limit N] [--stub <id>] [--stub-top N] [--windows week,month,year,hot] [--dry-run]
---

You are running inside Claude Code on Justin's Mac.

Run the Reddit story-candidate research. Default mode mines a large candidate base (~24 requests across 4 rankings × 6 subreddits, ~40s wall-clock) and writes a ranked report under `output/research/candidates_YYYY-MM-DD.md`. Use `--stub-top N` to materialize the top N per cluster as `story_queue/SY_NN_*.md` stubs in one shot.

```bash
cd "/Users/justinlee/Documents/Claude/Projects/Youtube Shorts Autonomous Channel"
source .venv-upload/bin/activate 2>/dev/null || true
python scripts/research_reddit_stories.py $ARGUMENTS
```

After it runs, report back:
- How many candidates were surfaced per cluster (horror / reddit / survival)
- Path to the generated `.md` and `.json` reports
- The top-1 candidate per cluster with its composite score
- Whether any new stubs were created (only if `--stub` or `--stub-top` was used)

**Common follow-up flows:**
- "Show me the top 5 horror": `python scripts/research_reddit_stories.py --cluster horror --limit 5`
- "Stub the top 5 per cluster (15 new stubs)": `python scripts/research_reddit_stories.py --stub-top 5`
- "Just one stub from the report": `python scripts/research_reddit_stories.py --stub <candidate_id>`
- "Mark a candidate as rejected so it never resurfaces": append the id to `output/research/_rejected.json`

**Anti-plagiarism reminder:** every candidate's `selftext` is COPYRIGHTED by its Reddit author. The candidate report collapses selftext in `<details>` blocks specifically to deter copy-paste. The stub generator writes a STRUCTURAL PARAPHRASE to Premise, never the post's prose. At production time the writer reads the source URL from Notes and applies the playbook's rewrite rule. Surface a warning if you spot any verbatim Reddit sentence leaking into a queue file.

**If it fails:**
- `429 Too Many Requests` from Reddit → wait 10 minutes, then retry. The script paces requests but Reddit's unauth limit can tighten without notice. If persistent, swap to PRAW + OAuth (top-of-file constant to enable).
- `Network unreachable` → check connection; the script needs HTTPS to reddit.com.
- `Empty candidate report` → all candidates fell below the hard filters (selftext < 200 chars, removed/deleted, etc). Check that the subreddits in the top-of-file map are still active.
