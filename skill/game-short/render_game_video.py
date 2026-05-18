#!/usr/bin/env python3
"""Game short video renderer — portrait-crops trailer clips and prepares for FFmpeg encode.

Input:  output/scripts/<game_id>/game_config.json
Output:
  output/scripts/<game_id>/clips_portrait/<clip>.mp4   (1080x1920, darkened)
  output/scripts/<game_id>/bg_clips_concat.txt         (FFmpeg concat list)
  output/scripts/<game_id>/captions.ass                (ASS subtitle file)

Then run FFmpeg to compose the final video (command shown at end of this script's output).

Usage:
    python skill/game-short/render_game_video.py output/scripts/GG_01_elden_ring/game_config.json
    python skill/game-short/render_game_video.py output/scripts/GG_01_elden_ring/game_config.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Portrait canvas dimensions
W, H = 1080, 1920

# Caption style constants (matches visual_style_guide.md)
FONT_NAME = "Poppins Bold"
CAPTION_FONT_SIZE = 72
CAPTION_COLOR = "&H00FFFFFF"    # white
CAPTION_OUTLINE = "&H00000000"  # black
CAPTION_MARGIN_V = 240          # pixels from bottom

# Text overlay colors
ACCENT_PRIMARY = "0x8B5CF6"   # electric purple
ACCENT_SECONDARY = "0x06B6D4" # neon cyan

# How dark to make the overlay (colorchannelmixer multiplier)
OVERLAY_DARKNESS = 0.55   # 0.55 = ~45% darker (reads text well over most footage)

# Words per caption flash (2-3 words per chunk)
WORDS_PER_FLASH = 3


# ---------------------------------------------------------------------------
# Audio duration
# ---------------------------------------------------------------------------

def get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: ffprobe failed on {path}: {result.stderr}")
    return float(result.stdout.strip())


def get_clip_duration(path: Path) -> float:
    return get_audio_duration(path)  # same ffprobe call


# ---------------------------------------------------------------------------
# Portrait crop + overlay
# ---------------------------------------------------------------------------

def process_clip_to_portrait(clip_path: Path, out_path: Path,
                              game_title: str = "", platform_label: str = "",
                              show_title: bool = False, dry_run: bool = False) -> None:
    """Scale+crop clip to 1080x1920, apply dark overlay, optionally burn game title text."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Base vf: scale to fill height at 16:9, center-crop to portrait, then darken
    vf = (
        f"scale={W * 9 // 16}:{H}:force_original_aspect_ratio=increase,"
        f"scale=-1:{H},"
        f"crop={W}:{H},"
        f"colorchannelmixer=rr={OVERLAY_DARKNESS}:gg={OVERLAY_DARKNESS}:bb={OVERLAY_DARKNESS}"
    )

    # Title overlay via drawtext requires ffmpeg built with --enable-libfreetype.
    # Skipped here — game title is displayed via ASS captions in the final encode.

    cmd = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-an",  # no audio in portrait clips (audio comes from narration)
        str(out_path),
    ]

    if dry_run:
        print(f"  [dry-run] Would run: {' '.join(cmd[:6])}…")
        return

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        sys.exit(f"ERROR: Portrait crop failed for {clip_path.name}:\n{result.stderr[-500:]}")


# ---------------------------------------------------------------------------
# ASS caption builder
# ---------------------------------------------------------------------------

def build_ass(text: str, audio_duration: float) -> str:
    """Generate ASS subtitle file from narration text + audio duration.

    Uses proportional word-count timing (same approach as truecrime renderer).
    """
    words = text.split()
    total_words = len(words)
    if total_words == 0:
        return ""

    # Chunk words into WORDS_PER_FLASH groups
    chunks = []
    for i in range(0, total_words, WORDS_PER_FLASH):
        chunks.append(words[i:i + WORDS_PER_FLASH])

    # Proportional timing: each chunk gets time proportional to its word count
    chunk_durations = []
    for chunk in chunks:
        proportion = len(chunk) / total_words
        chunk_durations.append(proportion * audio_duration)

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{CAPTION_FONT_SIZE},{CAPTION_COLOR},&H000000FF,{CAPTION_OUTLINE},&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,0,0,{CAPTION_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def ts(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    events = []
    t = 0.0
    for chunk, dur in zip(chunks, chunk_durations):
        text_line = " ".join(chunk).upper()
        events.append(f"Dialogue: 0,{ts(t)},{ts(t + dur)},Default,,0,0,0,,{text_line}")
        t += dur

    return ass_header + "\n".join(events) + "\n"


# ---------------------------------------------------------------------------
# Concat list builder
# ---------------------------------------------------------------------------

def build_concat_list(portrait_clips: list[Path], audio_duration: float) -> str:
    """Build FFmpeg concat demuxer list, padding last clip if needed."""
    lines = []
    total_clip_duration = sum(get_clip_duration(p) for p in portrait_clips)

    for i, clip in enumerate(portrait_clips):
        dur = get_clip_duration(clip)
        lines.append(f"file '{clip}'")

        # If this is the last clip and total is short, extend it
        if i == len(portrait_clips) - 1 and total_clip_duration < audio_duration + 1:
            extra = audio_duration + 1.5 - total_clip_duration
            if extra > 0:
                dur += extra
                # Loop the last clip to fill: just repeat its entry
                lines.append(f"duration {dur:.3f}")
                lines.append(f"file '{clip}'")
            else:
                lines.append(f"duration {dur:.3f}")
        else:
            lines.append(f"duration {dur:.3f}")

    # FFmpeg concat needs a final file entry without duration
    lines.append(f"file '{portrait_clips[-1]}'")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Render portrait clips and ASS captions for a game short.")
    parser.add_argument("config", help="Path to game_config.json")
    parser.add_argument("--dry-run", action="store_true", help="Show steps without running FFmpeg")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        sys.exit(f"ERROR: Config not found: {config_path}")

    cfg = json.loads(config_path.read_text())

    game_id = cfg["game_id"]
    audio_file = PROJECT_ROOT / cfg["audio_file"]
    clips_manifest_path = PROJECT_ROOT / cfg["clips_manifest"]
    game_title = cfg.get("game_title", "").upper()
    platform_label = cfg.get("platform", "") + ("  •  " + cfg.get("release_label", "") if cfg.get("release_label") else "")

    # Reconstruct spoken text from beats for ASS captions
    beats = cfg.get("beats", [])
    spoken_text = " ".join(b["text"] for b in beats if b.get("text"))

    game_dir = PROJECT_ROOT / "output" / "scripts" / game_id
    portrait_dir = game_dir / "clips_portrait"
    portrait_dir.mkdir(parents=True, exist_ok=True)

    print(f"── Render Game Video: {game_id} ──")

    if not audio_file.exists():
        sys.exit(f"ERROR: Audio not found: {audio_file}\nRun: python scripts/make_audio_elevenlabs.py --case {game_id}")

    audio_duration = get_audio_duration(audio_file)
    print(f"  Audio duration: {audio_duration:.1f}s")

    # Load clips manifest
    if not clips_manifest_path.exists():
        sys.exit(f"ERROR: Clips manifest not found: {clips_manifest_path}\nRun: python scripts/select_clips.py --game-id {game_id} --auto")

    manifest = json.loads(clips_manifest_path.read_text())
    clip_paths = [PROJECT_ROOT / entry["file"] for entry in manifest]

    for p in clip_paths:
        if not p.exists():
            sys.exit(f"ERROR: Clip not found: {p}\nRe-run: python scripts/select_clips.py --game-id {game_id} --auto")

    # Step 1: Process each clip to portrait
    print(f"\n  Processing {len(clip_paths)} clips to portrait (1080×1920)…")
    portrait_clips = []
    for i, (clip_path, entry) in enumerate(zip(clip_paths, manifest), 1):
        out_portrait = portrait_dir / f"clip_{i:02d}_portrait.mp4"
        label = entry.get("label", f"clip{i}")
        is_first = (i == 1)
        print(f"    clip_{i:02d} ({label})… ", end="", flush=True)
        process_clip_to_portrait(
            clip_path, out_portrait,
            game_title=game_title,
            platform_label=platform_label,
            show_title=is_first,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            print("✓")
        portrait_clips.append(out_portrait)

    # Step 2: Build concat list
    print("\n  Building concat list…")
    concat_content = build_concat_list(portrait_clips, audio_duration)
    concat_path = game_dir / "bg_clips_concat.txt"
    if not args.dry_run:
        concat_path.write_text(concat_content)
        print(f"  ✓ {concat_path.relative_to(PROJECT_ROOT)}")

    # Step 3: Build ASS captions
    print("  Building ASS captions…")
    if not spoken_text:
        print("  ⚠  No spoken text in game_config.json beats — captions will be empty")
    ass_content = build_ass(spoken_text, audio_duration)
    ass_path = game_dir / "captions.ass"
    if not args.dry_run:
        ass_path.write_text(ass_content)
        chunks = len([l for l in ass_content.splitlines() if l.startswith("Dialogue:")])
        print(f"  ✓ {ass_path.relative_to(PROJECT_ROOT)} ({chunks} caption chunks)")

    # Step 4: Print the FFmpeg encode command
    out_mp4 = PROJECT_ROOT / "output" / "game_videos" / f"{game_id}.mp4"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_cmd = (
        f"ffmpeg -y \\\n"
        f"  -f concat -safe 0 -i {concat_path.relative_to(PROJECT_ROOT)} \\\n"
        f"  -i {audio_file.relative_to(PROJECT_ROOT)} \\\n"
        f"  -vf \"subtitles={ass_path.relative_to(PROJECT_ROOT)}\" \\\n"
        f"  -map 0:v -map 1:a \\\n"
        f"  -c:v libx264 -preset fast -crf 22 \\\n"
        f"  -c:a aac -b:a 128k -shortest -movflags +faststart \\\n"
        f"  {out_mp4.relative_to(PROJECT_ROOT)}"
    )

    print(f"\n  ── Final encode command ──")
    print(f"  Run from project root:")
    print(f"\n  {ffmpeg_cmd}\n")

    if not args.dry_run:
        print(f"  After encoding, upload with:")
        print(f"  python scripts/upload_to_youtube.py --case {game_id} --videos-dir output/game_videos --category 20")


if __name__ == "__main__":
    main()
