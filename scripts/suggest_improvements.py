#!/usr/bin/env python3
"""Claude-powered writer-prompt improvement suggester.

Reads the latest iteration report + competitive intel, calls Claude API,
and produces 3 specific, data-backed suggestions for improving writer_prompt.md
or visual_style_guide.md. SUGGESTS ONLY — never auto-applies changes.

Usage:
    python scripts/suggest_improvements.py
    python scripts/suggest_improvements.py --dry-run   # print prompt, no API call
    python scripts/suggest_improvements.py --iteration-report 2026-05-17
    python scripts/suggest_improvements.py --competitive-intel 2026-05-17

Prerequisites:
    pip install anthropic
    export ANTHROPIC_API_KEY=your_key

Output:
    output/analytics/suggestions_YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"
WRITER_PROMPT_PATH = PROJECT_ROOT / "skill" / "truecrime-short" / "writer_prompt.md"
VISUAL_GUIDE_PATH = PROJECT_ROOT / "skill" / "truecrime-short" / "visual_style_guide.md"


def load_latest_file(dir_path: Path, pattern: str, date_override: str | None = None) -> tuple[Path, str]:
    """Find the newest file matching pattern, return (path, content)."""
    if date_override:
        # Try to find file with the given date in the name
        candidates = sorted(dir_path.glob(pattern.replace("*", f"*{date_override}*")), reverse=True)
        if not candidates:
            candidates = sorted(dir_path.glob(pattern), reverse=True)
    else:
        candidates = sorted(dir_path.glob(pattern), reverse=True)

    if not candidates:
        raise FileNotFoundError(f"No file matching '{pattern}' in {dir_path}")

    path = candidates[0]
    return path, path.read_text()


def build_user_message(iteration_report: str, competitive_intel: str) -> str:
    return f"""## Analytics Iteration Report

{iteration_report}

---

## Competitive Intelligence (Top Performing Shorts in the Space)

{competitive_intel}

---

## Task

Based on the retention data above and the competitive landscape, produce exactly 3 specific, actionable improvement suggestions for this channel's writer prompt or visual style guide.

Requirements for each suggestion:
1. Reference a specific data point from the iteration report (e.g., "4/6 videos have hook drops >25%")
2. Quote the exact current text from the writer prompt that should change
3. Propose the exact replacement text
4. Estimate the likely impact on avg view percentage (e.g., "+5–10% avg view %")

Format your response as:

## Suggestion 1 — [Category: Hook | Pacing | Visuals | Title | Structure]

**Problem (data-backed):** [specific metric or pattern]
**Current writer prompt text:**
```
[exact quote from the writer prompt]
```
**Proposed replacement:**
```
[exact new text]
```
**Rationale:** [1–2 sentences]
**Expected impact:** [specific estimate]

## Suggestion 2 — [Category]

[same format]

## Suggestion 3 — [Category]

[same format]

## What NOT to change

[1–2 sentences about what's working, backed by data]"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Claude-powered improvement suggestions.")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without calling API")
    parser.add_argument("--iteration-report", metavar="YYYY-MM-DD", help="Specific iteration report date")
    parser.add_argument("--competitive-intel", metavar="YYYY-MM-DD", help="Specific competitive intel date")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not args.dry_run and not api_key:
        sys.exit(
            "ERROR: ANTHROPIC_API_KEY is not set.\n"
            "Add it to .env or: export ANTHROPIC_API_KEY=your_key"
        )

    print("── Improvement Suggester ──")

    # Load inputs
    try:
        iter_path, iteration_report = load_latest_file(
            ANALYTICS_DIR, "iteration_report_*.md", args.iteration_report
        )
        print(f"  Iteration report: {iter_path.name}")
    except FileNotFoundError:
        sys.exit(
            "ERROR: No iteration_report_*.md found in output/analytics/.\n"
            "Run: python scripts/quality_loop.py"
        )

    try:
        intel_path, competitive_intel = load_latest_file(
            ANALYTICS_DIR, "competitive_intel_*.md", args.competitive_intel
        )
        print(f"  Competitive intel: {intel_path.name}")
    except FileNotFoundError:
        print("  ⚠  No competitive_intel_*.md found — suggestions will be based on retention data only.")
        competitive_intel = "(No competitive intel available — run python scripts/research_top_channels.py)"

    if not WRITER_PROMPT_PATH.exists():
        sys.exit(f"ERROR: Writer prompt not found at {WRITER_PROMPT_PATH}")
    writer_prompt_text = WRITER_PROMPT_PATH.read_text()
    print(f"  Writer prompt: {len(writer_prompt_text)} chars")

    user_message = build_user_message(iteration_report, competitive_intel)

    if args.dry_run:
        print("\n  [dry-run] Would send to claude-sonnet-4-6:")
        print("  System prompt: writer_prompt.md (cached)")
        print(f"  User message: {len(user_message)} chars")
        print("\n--- SYSTEM PROMPT (writer_prompt.md) ---")
        print(writer_prompt_text[:500] + "…")
        print("\n--- USER MESSAGE (first 500 chars) ---")
        print(user_message[:500] + "…")
        return

    try:
        import anthropic
    except ImportError:
        sys.exit(
            "ERROR: 'anthropic' package not installed.\n"
            "Run: pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=api_key)

    print("  Calling claude-sonnet-4-6…")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": (
                    "You are an expert YouTube channel strategist specializing in true crime "
                    "short-form content. You have deep knowledge of audience retention mechanics, "
                    "hook psychology, and what makes faceless documentary-style shorts perform well.\n\n"
                    "Below is the current writer prompt used to generate all narration scripts:\n\n"
                    + writer_prompt_text
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
    )

    suggestions = response.content[0].text

    # Write output
    today = date.today().isoformat()
    out_path = ANALYTICS_DIR / f"suggestions_{today}.md"
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    header = (
        f"# Improvement Suggestions — {today}\n\n"
        f"Generated by: claude-sonnet-4-6\n"
        f"Based on: {iter_path.name}"
        + (f", {intel_path.name}" if "intel_path" in dir() else "")
        + "\n\n"
        "**REVIEW ONLY — do not auto-apply.** Review each suggestion in Cowork and "
        "apply the ones you agree with to `skill/truecrime-short/writer_prompt.md`.\n\n"
        "---\n\n"
    )

    out_path.write_text(header + suggestions)
    print(f"  ✓ Wrote {out_path.relative_to(PROJECT_ROOT)}")

    # Show usage if available
    usage = response.usage
    print(f"  Tokens: {usage.input_tokens} in / {usage.output_tokens} out "
          f"(cache read: {getattr(usage, 'cache_read_input_tokens', 'n/a')})")

    print(f"\n  Next: review {out_path.name} in Cowork and apply the suggestions you agree with.")


if __name__ == "__main__":
    main()
