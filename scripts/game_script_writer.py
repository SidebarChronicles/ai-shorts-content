#!/usr/bin/env python3
"""Claude-powered 4-beat script generator for game shorts.

Reads a game_queue/GG_*.md entry, calls Claude API, and produces:
  output/scripts/<game_id>/script.md      (human-readable with title options)
  output/scripts/<game_id>/game_config.json  (drives the renderer)

Usage:
    python scripts/game_script_writer.py --game-id GG_01_subnautica2
    python scripts/game_script_writer.py --game-id GG_01_subnautica2 --dry-run

Prerequisites:
    ANTHROPIC_API_KEY set in .env or environment
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GAME_QUEUE_DIR = PROJECT_ROOT / "game_queue"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
WRITER_PROMPT_PATH = PROJECT_ROOT / "skill" / "game-short" / "writer_prompt.md"


# ---------------------------------------------------------------------------
# Queue entry parsing
# ---------------------------------------------------------------------------

def find_queue_entry(game_id: str) -> Path:
    # Direct match
    direct = GAME_QUEUE_DIR / f"{game_id}.md"
    if direct.exists():
        return direct
    # Prefix match
    for p in GAME_QUEUE_DIR.glob(f"{game_id}*.md"):
        return p
    # Partial match
    for p in GAME_QUEUE_DIR.glob("GG_*.md"):
        if game_id.lower() in p.name.lower():
            return p
    sys.exit(f"ERROR: No game_queue entry found for '{game_id}'")


def parse_queue_entry(path: Path) -> dict:
    content = path.read_text()

    def field(name: str) -> str:
        m = re.search(rf"\*\*{re.escape(name)}:\*\*\s*(.+)", content)
        return m.group(1).strip() if m else ""

    def section(name: str) -> str:
        m = re.search(rf"## {re.escape(name)}\n(.+?)(?=\n## |\Z)", content, re.DOTALL)
        return m.group(1).strip() if m else ""

    game_name = re.search(r"# GG_\S+ — (.+)", content)
    game_name = game_name.group(1).strip() if game_name else path.stem

    # Parse 4-beat arc
    arc_section = section("4-beat arc")
    arc = {}
    for beat in ["What is it", "Gameplay loop", "Standout", "CTA"]:
        m = re.search(rf"\*\*{re.escape(beat)}:\*\*\s*(.+)", arc_section)
        arc[beat.lower().replace(" ", "_")] = m.group(1).strip() if m else ""

    return {
        "game_id": path.stem,
        "game_name": game_name,
        "hook": section("Hook"),
        "arc": arc,
        "platform": field("Platform(s)"),
        "release": field("Release"),
        "developer": field("Developer"),
        "genre": field("Genre"),
        "steam_app_id": field("Steam App ID"),
    }


# ---------------------------------------------------------------------------
# Claude script generation
# ---------------------------------------------------------------------------

def generate_script(game_info: dict, writer_prompt: str, api_key: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""Generate a game short narration script for this game:

**Game:** {game_info['game_name']}
**Genre:** {game_info['genre']}
**Platform:** {game_info['platform']}
**Release:** {game_info['release']}
**Developer:** {game_info['developer']}

**Hook (use this or strengthen it):**
{game_info['hook']}

**4-beat arc (expand each into full sentences):**
- What is it: {game_info['arc'].get('what_is_it', '')}
- Gameplay loop: {game_info['arc'].get('gameplay_loop', '')}
- Standout: {game_info['arc'].get('standout', '')}
- CTA: {game_info['arc'].get('cta', '')}

Follow the writer prompt rules exactly. Output JSON only."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=[
            {
                "type": "text",
                "text": writer_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```[^\n]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            result = json.loads(m.group(0))
        else:
            sys.exit(f"ERROR: Claude returned invalid JSON:\n{raw[:500]}")

    return result


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def write_script_md(game_id: str, game_name: str, script_data: dict) -> Path:
    out_dir = SCRIPTS_DIR / game_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "script.md"

    title = script_data.get("title_suggestion", "")
    spoken = script_data.get("script_spoken", "")
    arc = script_data.get("beat_breakdown", {})

    content = f"""# Script — {game_id}

**Status:** PENDING APPROVAL
**Game:** {game_name}

---

## Title suggestion

{title}

---

## Script (spoken — clean, no citations)

> {spoken}

---

## Beat breakdown

| Beat | Text |
|---|---|
| Hook | {arc.get('hook', '')} |
| Gameplay loop | {arc.get('gameplay_loop', '')} |
| Standout | {arc.get('standout', '')} |
| CTA | {arc.get('cta', '')} |

---

## Word count

{len(spoken.split())} words (target: 120–140)
"""
    path.write_text(content)
    return path


def write_game_config(game_id: str, game_info: dict, script_data: dict) -> Path:
    out_dir = SCRIPTS_DIR / game_id
    out_dir.mkdir(parents=True, exist_ok=True)

    arc = script_data.get("beat_breakdown", {})
    beats = [
        {"label": "hook", "text": arc.get("hook", "")},
        {"label": "gameplay", "text": arc.get("gameplay_loop", "")},
        {"label": "standout", "text": arc.get("standout", "")},
        {"label": "cta", "text": arc.get("cta", "")},
    ]

    # Derive platform label
    platform = game_info["platform"]
    release = game_info["release"]
    release_label = "OUT NOW" if "2026" in release and any(
        m in release for m in ["Jan", "Feb", "Mar", "Apr", "May"]
    ) else release.upper() if release != "TBD" else "COMING SOON"

    config = {
        "game_id": game_id,
        "audio_file": f"assets/audio/narration_{game_id}.mp3",
        "clips_manifest": f"output/scripts/{game_id}/clips_manifest.json",
        "game_title": game_info["game_name"].upper(),
        "platform": platform,
        "release_label": release_label,
        "beats": beats,
        "spoken_text": script_data.get("script_spoken", ""),
    }

    path = out_dir / "game_config.json"
    path.write_text(json.dumps(config, indent=2))
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a game short script via Claude.")
    parser.add_argument("--game-id", required=True, help="Game ID (e.g. GG_01_subnautica2)")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing files")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not args.dry_run and not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set.\nAdd it to .env or: export ANTHROPIC_API_KEY=your_key")

    if not WRITER_PROMPT_PATH.exists():
        sys.exit(f"ERROR: Writer prompt not found at {WRITER_PROMPT_PATH}")
    writer_prompt = WRITER_PROMPT_PATH.read_text()

    print(f"── Game Script Writer: {args.game_id} ──")

    queue_path = find_queue_entry(args.game_id)
    game_info = parse_queue_entry(queue_path)
    print(f"  Game: {game_info['game_name']}")
    print(f"  Genre: {game_info['genre']}")

    if args.dry_run:
        print("\n  [dry-run] Would call claude-sonnet-4-6 to generate script.")
        print(f"  Hook: {game_info['hook']}")
        return

    print("  Generating script with Claude…")
    script_data = generate_script(game_info, writer_prompt, api_key)

    spoken = script_data.get("script_spoken", "")
    word_count = len(spoken.split())
    print(f"  Word count: {word_count} (target 120–140)")
    if word_count < 100 or word_count > 160:
        print(f"  ⚠  Word count outside target range")

    print(f"\n  Title: {script_data.get('title_suggestion', '')}")
    print(f"\n  Script preview:")
    print(f"  {spoken[:200]}…")

    script_path = write_script_md(args.game_id, game_info["game_name"], script_data)
    config_path = write_game_config(args.game_id, game_info, script_data)

    print(f"\n  ✓ Script: {script_path.relative_to(PROJECT_ROOT)}")
    print(f"  ✓ Config: {config_path.relative_to(PROJECT_ROOT)}")
    print(f"\n  Next: python scripts/make_audio_elevenlabs.py --case {args.game_id}")


if __name__ == "__main__":
    main()
