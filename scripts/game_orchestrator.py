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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GAME_QUEUE_DIR = PROJECT_ROOT / "game_queue"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
GAME_VIDEOS_DIR = PROJECT_ROOT / "output" / "game_videos"
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
    """Return {game_id: status} from all queue files."""
    statuses = {}
    for p in sorted(GAME_QUEUE_DIR.glob("GG_*.md")):
        if p.name.startswith("GG_TEMPLATE"):
            continue
        content = p.read_text()
        m = re.search(r"\*\*Status:\*\*\s*(\w+)", content)
        status = m.group(1) if m else "UNKNOWN"
        statuses[p.stem] = status
    return statuses


def next_queued_game() -> str | None:
    for game_id, status in load_queue_status().items():
        if status == "QUEUED":
            return game_id
    return None


def mark_queue_status(game_id: str, status: str) -> None:
    path = GAME_QUEUE_DIR / f"{game_id}.md"
    if not path.exists():
        return
    content = path.read_text()
    content = re.sub(r"\*\*Status:\*\*\s*\w+", f"**Status:** {status}", content)
    path.write_text(content)


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

    # Load .env for API key if not already set
    env = os.environ.copy()
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists() and not env.get("ELEVENLABS_API_KEY"):
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                            timeout=120, env=env)
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


def step_write_description(game_id: str) -> bool:
    """Write the YouTube description.md sidecar from game_config.json."""
    config_path = SCRIPTS_DIR / game_id / "game_config.json"
    if not config_path.exists():
        return False

    cfg = json.loads(config_path.read_text())
    game_title = cfg.get("game_title", game_id)
    release_label = cfg.get("release_label", "")
    platform = cfg.get("platform", "PC")
    beats = cfg.get("beats", [])

    hook_text = beats[0]["text"] if beats else ""
    slug = game_id.lower().replace("gg_", "").replace("_", "")

    # Build title: hook-style up to 80 chars + tags
    title = f"{hook_text[:75]} #{slug.replace('_', '').replace(' ', '')} #gaming #shorts"
    if len(title) > 100:
        title = f"{game_title} — {hook_text[:50]} #gaming #shorts"

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
        "",
        f"#{slug} #gaming #shorts #newgame",
    ]

    desc_path = GAME_VIDEOS_DIR / f"{game_id}.description.md"
    GAME_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    desc_path.write_text(
        f"## Title\n\n```\n{title}\n```\n\n"
        f"## DESCRIPTION\n\n```\n{chr(10).join(description_parts)}\n```\n\n"
        f"## Tags\n\n```\n{slug}, gaming, shorts, newgame, {platform.lower().replace(' / ', ', ').replace('/', ',')}\n```\n"
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

    env = os.environ.copy()
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                            timeout=600, env=env)
    log(result.stdout)
    if result.returncode != 0:
        log(f"  [upload] ERROR: {result.stderr[-500:]}")
        return False

    log(f"  [upload] ✓ uploaded to YouTube")
    return True


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(game_id: str, dry_run: bool, skip_upload: bool = False) -> bool:
    log(f"\n{'='*50}")
    log(f"Starting pipeline: {game_id}")
    log(f"{'='*50}")

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

    for name, fn in steps:
        log(f"\n── {name} ──")
        try:
            ok = fn()
        except Exception as e:
            log(f"  ERROR: {e}")
            ok = False

        if not ok:
            log(f"\n✗ Pipeline failed at: {name}")
            mark_queue_status(game_id, "QUEUED")  # reset so it can be retried
            return False

    mark_queue_status(game_id, "DELIVERED")
    log(f"\n✓ Pipeline complete: {game_id}")
    return True


def run_auto(dry_run: bool) -> None:
    """Full autonomous mode: research → pick top game → run pipeline."""
    log("── Auto mode: researching new games ──")

    env = os.environ.copy()
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    cmd = ["python3", "scripts/research_games.py", "--count", "20", "--top", "1"]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                            timeout=120, env=env)
    log(result.stdout)
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
    mode.add_argument("--auto", action="store_true",
                      help="Full auto: research new games + produce + upload")
    mode.add_argument("--list", action="store_true", help="List queue status")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls")
    parser.add_argument("--skip-upload", action="store_true", help="Stop before uploading")
    args = parser.parse_args()

    if args.list:
        statuses = load_queue_status()
        if not statuses:
            print("No games in game_queue/ yet.")
            return
        for game_id, status in statuses.items():
            print(f"  [{status:10s}] {game_id}")
        return

    if args.auto:
        run_auto(args.dry_run)
    elif args.next:
        game_id = next_queued_game()
        if not game_id:
            print("No QUEUED games in game_queue/. Run research_games.py or add a queue entry.")
            return
        run_pipeline(game_id, args.dry_run, args.skip_upload)
    else:
        run_pipeline(args.game_id, args.dry_run, args.skip_upload)


if __name__ == "__main__":
    main()
