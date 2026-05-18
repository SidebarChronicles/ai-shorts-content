#!/usr/bin/env python3
"""Full autonomous game short pipeline orchestrator.

Runs the complete loop for one game:
  research (optional) → fetch trailer → select clips → write script →
  generate TTS → render portrait clips + captions → FFmpeg encode → upload

Also supports a weekly autonomous mode that:
  1. Runs research_games.py to find new candidates
  2. Picks the top scored game
  3. Runs the full pipeline end-to-end
  4. Uploads to YouTube
  5. Logs results

Usage:
    # Run full pipeline for a specific game:
    python scripts/game_orchestrator.py --game-id GG_01_subnautica2

    # Run full pipeline for next QUEUED game:
    python scripts/game_orchestrator.py --next

    # Full autonomous mode: research + pick + produce + upload:
    python scripts/game_orchestrator.py --auto

    # Dry-run: show what would happen without API calls:
    python scripts/game_orchestrator.py --game-id GG_01_subnautica2 --dry-run

Prerequisites:
    ELEVENLABS_API_KEY, ANTHROPIC_API_KEY set in .env
    ffmpeg on PATH (brew install ffmpeg)
    pip install yt-dlp anthropic
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_text  # noqa: E402

# Game IDs must be safe for FFmpeg filtergraph syntax (no quotes/colons/etc.)
GAME_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")

GAME_QUEUE_DIR = PROJECT_ROOT / "game_queue"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
GAME_VIDEOS_DIR = PROJECT_ROOT / "output" / "game_videos"

# Load .env once at startup; child subprocesses inherit via the default env.
load_dotenv(PROJECT_ROOT / ".env")
LOG_PATH = PROJECT_ROOT / "output" / "game_pipeline.log"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Game queue helpers
# ---------------------------------------------------------------------------

def load_queue_status() -> dict[str, str]:
    """Return {game_id: status} from all queue files (only safe game_ids)."""
    statuses = {}
    for p in sorted(GAME_QUEUE_DIR.glob("GG_*.md")):
        if p.name.startswith("GG_TEMPLATE"):
            continue
        if not GAME_ID_RE.match(p.stem):
            log(f"  [queue] skipping {p.name}: unsafe game_id for FFmpeg paths")
            continue
        content = p.read_text()
        m = re.search(r"\*\*Status:\*\*\s*([A-Z_]+)", content)
        status = m.group(1) if m else "UNKNOWN"
        statuses[p.stem] = status
    return statuses


def next_queued_game() -> str | None:
    for game_id, status in load_queue_status().items():
        if status == "QUEUED":
            return game_id
    return None


def next_rendered_game() -> str | None:
    for game_id, status in load_queue_status().items():
        if status == "RENDERED":
            return game_id
    return None


def mark_queue_status(game_id: str, status: str) -> None:
    """Atomically rewrite the first `**Status:** X` line in the queue file.

    Uses count=1 so any later occurrence of the same pattern inside prose
    is untouched. atomic_write_text guarantees no partial-write corruption.
    """
    path = GAME_QUEUE_DIR / f"{game_id}.md"
    if not path.exists():
        return
    content = path.read_text()
    new_content = re.sub(
        r"\*\*Status:\*\*\s*[A-Z_]+", f"**Status:** {status}", content, count=1
    )
    atomic_write_text(path, new_content)


def get_youtube_trailer_url(game_id: str) -> str | None:
    path = GAME_QUEUE_DIR / f"{game_id}.md"
    if not path.exists():
        return None
    content = path.read_text()
    m = re.search(r"\*\*YouTube Trailer URL:\*\*\s*(.+)", content)
    if not m:
        return None
    url = m.group(1).strip()
    if url.startswith("http") and "youtube" in url:
        return url
    if url.startswith("search:"):
        return None  # needs manual lookup
    return None


def get_steam_app_id(game_id: str) -> str | None:
    path = GAME_QUEUE_DIR / f"{game_id}.md"
    if not path.exists():
        return None
    content = path.read_text()
    m = re.search(r"\*\*Steam App ID:\*\*\s*(\d+)", content)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Pipeline steps — each returns True on success
# ---------------------------------------------------------------------------

def step_fetch_trailer(game_id: str, dry_run: bool) -> bool:
    trailer_path = SCRIPTS_DIR / game_id / "trailer_raw.mp4"
    if trailer_path.exists():
        log(f"  [fetch] trailer_raw.mp4 already exists, skipping download")
        return True

    steam_id = get_steam_app_id(game_id)
    youtube_url = get_youtube_trailer_url(game_id)

    if steam_id and steam_id != "0":
        cmd = ["python3", "scripts/fetch_trailer.py", "--steam", steam_id, "--game-id", game_id]
    elif youtube_url:
        cmd = ["python3", "scripts/fetch_trailer.py", "--youtube", youtube_url, "--game-id", game_id]
    else:
        log(f"  [fetch] ERROR: No Steam App ID or YouTube URL for {game_id}")
        return False

    if dry_run:
        log(f"  [fetch] dry-run: would run {' '.join(cmd)}")
        return True

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        log(f"  [fetch] ERROR: {result.stderr[-500:]}")
        return False

    log(f"  [fetch] ✓ trailer_raw.mp4 downloaded")
    return True


def step_select_clips(game_id: str, dry_run: bool) -> bool:
    manifest_path = SCRIPTS_DIR / game_id / "clips_manifest.json"
    if manifest_path.exists():
        log(f"  [clips] clips_manifest.json already exists, skipping")
        return True

    cmd = ["python3", "scripts/select_clips.py", "--game-id", game_id, "--auto"]

    if dry_run:
        log(f"  [clips] dry-run: would run auto scene detection")
        return True

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        log(f"  [clips] ERROR: {result.stderr[-500:]}")
        return False

    log(f"  [clips] ✓ clips selected")
    return True


def step_write_script(game_id: str, dry_run: bool) -> bool:
    config_path = SCRIPTS_DIR / game_id / "game_config.json"
    if config_path.exists():
        log(f"  [script] game_config.json already exists, skipping")
        return True

    cmd = ["python3", "scripts/game_script_writer.py", "--game-id", game_id]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        log(f"  [script] ERROR: {result.stderr[-500:]}")
        return False

    log(f"  [script] ✓ script and game_config.json written")
    return True


def step_generate_audio(game_id: str, dry_run: bool) -> bool:
    audio_path = PROJECT_ROOT / "assets" / "audio" / f"narration_{game_id}.mp3"
    if audio_path.exists():
        log(f"  [tts] narration_{game_id}.mp3 already exists, skipping")
        return True

    cmd = ["python3", "scripts/make_audio_elevenlabs.py", "--case", game_id]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                            timeout=120)
    if result.returncode != 0:
        log(f"  [tts] ERROR: {result.stderr[-500:]}\n{result.stdout[-200:]}")
        return False

    log(f"  [tts] ✓ audio generated")
    return True


def step_render(game_id: str, dry_run: bool) -> bool:
    config_path = SCRIPTS_DIR / game_id / "game_config.json"
    if not config_path.exists():
        log(f"  [render] ERROR: game_config.json not found")
        return False

    concat_path = SCRIPTS_DIR / game_id / "bg_clips_concat.txt"

    # Run render_game_video.py
    cmd = ["python3", "skill/game-short/render_game_video.py", str(config_path)]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        log(f"  [render] ERROR: {result.stderr[-500:]}")
        return False

    log(f"  [render] ✓ portrait clips + ASS captions prepared")

    if dry_run:
        return True

    # Now run the FFmpeg encode
    cfg = json.loads(config_path.read_text())
    game_id = cfg["game_id"]
    audio_file = PROJECT_ROOT / cfg["audio_file"]
    ass_path = SCRIPTS_DIR / game_id / "captions.ass"
    out_mp4 = GAME_VIDEOS_DIR / f"{game_id}.mp4"
    GAME_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    if not concat_path.exists():
        log(f"  [render] ERROR: bg_clips_concat.txt not found after render step")
        return False

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-i", str(audio_file),
        "-vf", f"subtitles={ass_path}",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
        str(out_mp4),
    ]

    log(f"  [render] Running FFmpeg encode…")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        log(f"  [render] FFmpeg ERROR: {result.stderr[-1000:]}")
        return False

    size_mb = out_mp4.stat().st_size / (1024 * 1024)
    log(f"  [render] ✓ {out_mp4.relative_to(PROJECT_ROOT)} ({size_mb:.1f} MB)")
    return True


# Genre keyword → hashtag mapping for auto-tagging
GENRE_HASHTAGS = {
    "survival": "#SurvivalGame",
    "exploration": "#ExplorationGame",
    "stealth": "#StealthGame",
    "action": "#ActionAdventure",
    "adventure": "#ActionAdventure",
    "rpg": "#RPG",
    "horror": "#HorrorGame",
    "fps": "#FPS",
    "shooter": "#FPS",
    "sci-fi": "#SciFiGame",
    "open world": "#OpenWorld",
    "open-world": "#OpenWorld",
    "indie": "#IndieGame",
    "puzzle": "#PuzzleGame",
    "strategy": "#Strategy",
    "platformer": "#Platformer",
}

PLATFORM_HASHTAGS = {
    "steam": "#Steam",
    "pc": "#PCGaming",
    "xbox": "#Xbox",
    "ps5": "#PS5",
    "playstation": "#PS5",
    "nintendo": "#NintendoSwitch",
}


def _genre_tags(genre_str: str) -> list[str]:
    """Pick up to 2 genre hashtags from the game's genre field."""
    seen, tags = set(), []
    lower = genre_str.lower()
    for keyword, tag in GENRE_HASHTAGS.items():
        if keyword in lower and tag not in seen:
            seen.add(tag)
            tags.append(tag)
        if len(tags) == 2:
            break
    return tags


def _platform_tags(platform_str: str) -> list[str]:
    """Pick up to 2 platform hashtags (only accurate ones)."""
    seen, tags = set(), []
    lower = platform_str.lower()
    for keyword, tag in PLATFORM_HASHTAGS.items():
        if keyword in lower and tag not in seen:
            seen.add(tag)
            tags.append(tag)
        if len(tags) == 2:
            break
    return tags


def step_write_description(game_id: str) -> bool:
    """Write the YouTube description.md sidecar from game_config.json."""
    config_path = SCRIPTS_DIR / game_id / "game_config.json"
    if not config_path.exists():
        return False

    # Also read genre/platform from game_queue entry for hashtag selection
    queue_path = GAME_QUEUE_DIR / f"{game_id}.md"
    genre_str, platform_from_queue = "", ""
    if queue_path.exists():
        content = queue_path.read_text()
        m = re.search(r"\*\*Genre:\*\*\s*(.+)", content)
        genre_str = m.group(1).strip() if m else ""
        m = re.search(r"\*\*Platform\(s\):\*\*\s*(.+)", content)
        platform_from_queue = m.group(1).strip() if m else ""

    cfg = json.loads(config_path.read_text())
    game_title = cfg.get("game_title", game_id)
    release_label = cfg.get("release_label", "")
    platform = platform_from_queue or cfg.get("platform", "PC")
    beats = cfg.get("beats", [])

    hook_text = beats[0]["text"] if beats else ""

    # Title: clean hook sentence only — no hashtags in title
    title = hook_text[:100].rstrip(".")
    if len(title) > 90:
        # Trim to last complete word under 90 chars
        title = title[:90].rsplit(" ", 1)[0]

    # Build hashtags: #Shorts #GameTrailer #GameSlug [genre x2] [platform x1-2] #NewGame
    game_slug = re.sub(r"[^a-zA-Z0-9]", "", game_title.title())  # e.g. "Subnautica2"
    hashtags = ["#Shorts", "#GameTrailer", f"#{game_slug}"]
    hashtags += _genre_tags(genre_str)
    hashtags += _platform_tags(platform)
    if "early access" in release_label.lower():
        hashtags.append("#EarlyAccess")
    else:
        hashtags.append("#NewGame")
    hashtag_line = " ".join(hashtags[:8])  # cap at 8

    description_parts = [hook_text, ""]
    for beat in beats[1:]:
        description_parts.append(beat["text"])
    description_parts += [
        "",
        f"🎮 {game_title}",
        f"📅 {release_label}",
        f"🖥  Available on: {platform}",
        "",
        "⚠ Narration in this video is AI-generated (ElevenLabs).",
        "🎵 Music: Kevin MacLeod (incompetech.com) — Licensed under CC-BY 4.0",
        "    https://creativecommons.org/licenses/by/4.0/",
        "",
        hashtag_line,
    ]

    # Tags field: plain keywords for YouTube tags API
    tag_keywords = [game_slug, "gaming", "shorts", "game trailer"]
    tag_keywords += [h.lstrip("#").lower() for h in hashtags[3:]]
    tags_line = ", ".join(tag_keywords)

    desc_path = GAME_VIDEOS_DIR / f"{game_id}.description.md"
    GAME_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    desc_path.write_text(
        f"## Title\n\n```\n{title}\n```\n\n"
        f"## DESCRIPTION\n\n```\n{chr(10).join(description_parts)}\n```\n\n"
        f"## Tags\n\n```\n{tags_line}\n```\n"
    )
    log(f"  [desc] ✓ {desc_path.relative_to(PROJECT_ROOT)}")
    return True


def step_upload(game_id: str, dry_run: bool) -> bool:
    cmd = [
        "python3", "scripts/upload_to_youtube.py",
        "--case", game_id,
        "--videos-dir", "output/game_videos",
        "--category", "20",
    ]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                            timeout=600)
    # Avoid logging full subprocess stdout — keep only the last 500 chars
    # in case any child ever logs a secret. Errors keep more detail.
    if result.stdout:
        log(result.stdout[-500:].rstrip())
    if result.returncode != 0:
        log(f"  [upload] ERROR: {result.stderr[-500:]}")
        return False

    log(f"  [upload] ✓ uploaded to YouTube")
    return True


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

MAX_RETRIES = 3


def _read_retry_count(game_id: str) -> int:
    path = GAME_QUEUE_DIR / f"{game_id}.md"
    if not path.exists():
        return 0
    m = re.search(r"\*\*Retries:\*\*\s*(\d+)", path.read_text())
    return int(m.group(1)) if m else 0


def _bump_retry_count(game_id: str, value: int) -> None:
    """Append or update **Retries:** N in the queue file (atomic)."""
    path = GAME_QUEUE_DIR / f"{game_id}.md"
    if not path.exists():
        return
    content = path.read_text()
    if re.search(r"\*\*Retries:\*\*", content):
        new_content = re.sub(
            r"\*\*Retries:\*\*\s*\d+", f"**Retries:** {value}", content, count=1
        )
    else:
        # Insert after the Status line
        new_content = re.sub(
            r"(\*\*Status:\*\*[^\n]*\n)",
            rf"\1**Retries:** {value}\n",
            content,
            count=1,
        )
    atomic_write_text(path, new_content)


def run_pipeline(game_id: str, dry_run: bool, skip_upload: bool = False) -> bool:
    log(f"\n{'='*50}")
    log(f"Starting pipeline: {game_id}")
    log(f"{'='*50}")

    if not GAME_ID_RE.match(game_id):
        log(f"✗ Refusing to run: '{game_id}' contains chars unsafe for FFmpeg paths")
        return False

    # Block runaway retries on a permanently broken queue entry
    retries = _read_retry_count(game_id)
    if retries >= MAX_RETRIES:
        log(f"✗ {game_id} has failed {retries} times — marking BLOCKED for review")
        mark_queue_status(game_id, "BLOCKED")
        return False

    mark_queue_status(game_id, "ACTIVE")

    steps = [
        ("Fetch trailer", lambda: step_fetch_trailer(game_id, dry_run)),
        ("Select clips", lambda: step_select_clips(game_id, dry_run)),
        ("Write script", lambda: step_write_script(game_id, dry_run)),
        ("Generate audio", lambda: step_generate_audio(game_id, dry_run)),
        ("Render video", lambda: step_render(game_id, dry_run)),
        ("Write description", lambda: step_write_description(game_id)),
    ]

    if not skip_upload:
        steps.append(("Upload", lambda: step_upload(game_id, dry_run)))

    failed_step = None
    try:
        for name, fn in steps:
            log(f"\n── {name} ──")
            try:
                ok = fn()
            except Exception as e:
                log(f"  ERROR: {e}")
                ok = False

            if not ok:
                failed_step = name
                log(f"\n✗ Pipeline failed at: {name}")
                break
    finally:
        # ALWAYS update queue status — even on KeyboardInterrupt or unhandled raise.
        if failed_step is not None:
            new_retries = retries + 1
            _bump_retry_count(game_id, new_retries)
            mark_queue_status(game_id, "QUEUED")
            log(f"  Retry count: {new_retries}/{MAX_RETRIES}")

    if failed_step is not None:
        return False

    final_status = "RENDERED" if skip_upload else "DELIVERED"
    mark_queue_status(game_id, final_status)
    log(f"\n✓ Pipeline complete: {game_id} → {final_status}")
    return True


def run_upload_only(game_id: str, dry_run: bool) -> bool:
    """Upload a RENDERED game and mark DELIVERED. Used by the batch upload pass."""
    log(f"\n── Upload-only: {game_id} ──")
    if not GAME_ID_RE.match(game_id):
        log(f"✗ Refusing: '{game_id}' contains chars unsafe for FFmpeg paths")
        return False

    retries = _read_retry_count(game_id)
    if retries >= MAX_RETRIES:
        log(f"✗ {game_id} has failed {retries} times — marking BLOCKED")
        mark_queue_status(game_id, "BLOCKED")
        return False

    ok = False
    try:
        ok = step_upload(game_id, dry_run)
    except Exception as e:
        log(f"  ERROR during upload: {e}")

    if ok:
        mark_queue_status(game_id, "DELIVERED")
        log(f"  ✓ {game_id} → DELIVERED")
    else:
        new_retries = retries + 1
        _bump_retry_count(game_id, new_retries)
        log(f"  ✗ upload failed — retry {new_retries}/{MAX_RETRIES}")
        if new_retries >= MAX_RETRIES:
            mark_queue_status(game_id, "BLOCKED")
        # Leave as RENDERED so next fire retries the upload
    return ok


def run_auto(dry_run: bool) -> None:
    """Full autonomous mode: research → pick top game → run pipeline."""
    log("── Auto mode: researching new games ──")

    cmd = ["python3", "scripts/research_games.py", "--count", "20", "--top", "1"]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                            timeout=120)
    log(result.stdout[-500:].rstrip() if result.stdout else "")
    if result.returncode != 0:
        log(f"Research failed: {result.stderr[-500:]}")
        return

    # Pick the next queued game
    game_id = next_queued_game()
    if not game_id:
        log("No QUEUED games found after research. Done.")
        return

    log(f"Next game: {game_id}")
    run_pipeline(game_id, dry_run)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous game short pipeline orchestrator.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--game-id", help="Run pipeline for a specific game ID")
    mode.add_argument("--next", action="store_true", help="Run pipeline for next QUEUED game")
    mode.add_argument("--next-rendered", action="store_true",
                      help="Upload the next RENDERED game")
    mode.add_argument("--auto", action="store_true",
                      help="Full auto: research new games + produce + upload")
    mode.add_argument("--list", action="store_true", help="List queue status")
    mode.add_argument("--mark-status", nargs=2, metavar=("GAME_ID", "STATUS"),
                      help="Atomically set queue status (e.g. --mark-status GG_03_foo RENDERED)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Stop before uploading; marks RENDERED instead of DELIVERED")
    args = parser.parse_args()

    if args.list:
        statuses = load_queue_status()
        if not statuses:
            print("No games in game_queue/ yet.")
            return
        for game_id, status in statuses.items():
            print(f"  [{status:10s}] {game_id}")
        return

    if args.mark_status:
        game_id, status = args.mark_status
        valid = {"QUEUED", "RENDERED", "DELIVERED", "BLOCKED", "ACTIVE"}
        if status not in valid:
            print(f"ERROR: unknown status '{status}'. Valid: {', '.join(sorted(valid))}")
            raise SystemExit(1)
        mark_queue_status(game_id, status)
        print(f"Marked {game_id} → {status}")
        return

    if args.auto:
        run_auto(args.dry_run)
    elif args.next:
        game_id = next_queued_game()
        if not game_id:
            print("No QUEUED games in game_queue/. Run research_games.py or add a queue entry.")
            return
        run_pipeline(game_id, args.dry_run, args.skip_upload)
    elif args.next_rendered:
        game_id = next_rendered_game()
        if not game_id:
            print("No RENDERED games waiting for upload.")
            return
        run_upload_only(game_id, args.dry_run)
    else:
        run_pipeline(args.game_id, args.dry_run, args.skip_upload)


if __name__ == "__main__":
    main()
