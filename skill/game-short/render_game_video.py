#!/usr/bin/env python3
"""Game short video renderer — portrait-crops trailer clips and prepares for FFmpeg encode.

Input:  output/scripts/<game_id>/game_config.json
Output:
  output/scripts/<game_id>/clips_portrait/<clip>.mp4   (1080x1920, darkened)
  output/scripts/<game_id>/bg_clips_concat.txt         (FFmpeg concat list)
  output/scripts/<game_id>/karaoke.filter              (FFmpeg drawtext chain — word-by-word captions)

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

# Make scripts/ importable for build_karaoke_filter
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_karaoke_filter import build_chain as build_karaoke_chain  # noqa: E402
from build_top_title_filter import (  # noqa: E402
    build_singular_chain as build_singular_top_title,
    build_topx_chain as build_topx_top_title,
    DEFAULT_FONT as TOP_TITLE_FONT,
)

# Portrait canvas dimensions
W, H = 1080, 1920

# How dark to make the overlay (colorchannelmixer multiplier)
OVERLAY_DARKNESS = 0.55          # for center_crop: 0.55 = ~45% darker
PILLARBOX_BG_DARKNESS = 0.75     # for pillarbox blur background: lighter so seam isn't stark

# Crop strategy for converting 16:9 source to 9:16 portrait.
#  - "pillarbox_blur": full 16:9 frame fits centered, blurred copy fills top/bottom (no content lost — recommended)
#  - "center_crop":    legacy behavior; scales to fill and center-crops (loses left+right ~33% each)
DEFAULT_CROP_STRATEGY = "pillarbox_blur"


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
                              show_title: bool = False, dry_run: bool = False,
                              crop_strategy: str = DEFAULT_CROP_STRATEGY) -> None:
    """Convert source clip to 1080x1920 portrait. Strategy controls how 16:9 fits 9:16.

    - pillarbox_blur: full source frame centered in middle band, blurred copy fills top/bottom
    - center_crop:    scale to fill height, center-crop (loses ~33% left + ~33% right of frame)
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if crop_strategy == "pillarbox_blur":
        # Filter graph:
        #   [0:v] splits into [bg] and [fg]
        #   [bg] scales-up to fill 1080x1920, heavy blur, light darkening
        #   [fg] scales to 1080 wide preserving aspect, overlays centered
        filter_complex = (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"boxblur=30:8,"
            f"colorchannelmixer=rr={PILLARBOX_BG_DARKNESS}:gg={PILLARBOX_BG_DARKNESS}:bb={PILLARBOX_BG_DARKNESS}[blurbg];"
            f"[fg]scale={W}:-2:force_original_aspect_ratio=decrease[fgscaled];"
            f"[blurbg][fgscaled]overlay=0:(H-h)/2"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-filter_complex", filter_complex,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-an",
            str(out_path),
        ]
    elif crop_strategy == "center_crop":
        vf = (
            f"scale={W * 9 // 16}:{H}:force_original_aspect_ratio=increase,"
            f"scale=-1:{H},"
            f"crop={W}:{H},"
            f"colorchannelmixer=rr={OVERLAY_DARKNESS}:gg={OVERLAY_DARKNESS}:bb={OVERLAY_DARKNESS}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-an",
            str(out_path),
        ]
    else:
        sys.exit(f"ERROR: unknown crop_strategy '{crop_strategy}' — use 'pillarbox_blur' or 'center_crop'")

    if dry_run:
        print(f"  [dry-run] Would run: ffmpeg -i ... ({crop_strategy})")
        return

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        sys.exit(f"ERROR: Portrait crop failed for {clip_path.name} ({crop_strategy}):\n{result.stderr[-500:]}")


# ---------------------------------------------------------------------------
# Karaoke caption builder
# ---------------------------------------------------------------------------

def build_karaoke(audio_file: Path) -> str:
    """Generate FFmpeg drawtext filter chain from the audio's alignment.json sidecar.

    Returns empty string if alignment file is missing or has too few words —
    caller should treat that as "skip captions, log warning".
    """
    alignment_path = audio_file.parent / f"{audio_file.stem}.alignment.json"
    if not alignment_path.exists():
        return ""
    return build_karaoke_chain(alignment_path)


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
    parser = argparse.ArgumentParser(description="Render portrait clips and karaoke captions for a game short.")
    parser.add_argument("config", help="Path to game_config.json")
    parser.add_argument("--dry-run", action="store_true", help="Show steps without running FFmpeg")
    parser.add_argument("--crop", choices=["pillarbox_blur", "center_crop"],
                        default=DEFAULT_CROP_STRATEGY,
                        help="How to fit 16:9 source into 9:16 portrait (default: pillarbox_blur — keeps full frame visible)")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        sys.exit(f"ERROR: Config not found: {config_path}")

    cfg = json.loads(config_path.read_text())

    game_id = cfg["game_id"]
    # Game IDs feed into FFmpeg filtergraph args (subtitles=, file '...').
    # Reject anything that could break the parser (quotes, colons, etc.).
    if not re.match(r"^[A-Za-z0-9_]+$", game_id):
        sys.exit(f"ERROR: Unsafe game_id '{game_id}' — must match [A-Za-z0-9_]+")
    audio_file = PROJECT_ROOT / cfg["audio_file"]
    clips_manifest_path = PROJECT_ROOT / cfg["clips_manifest"]
    game_title = cfg.get("game_title", "").upper()
    platform_label = cfg.get("platform", "") + ("  •  " + cfg.get("release_label", "") if cfg.get("release_label") else "")

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
    print(f"\n  Processing {len(clip_paths)} clips to portrait (1080×1920, crop={args.crop})…")
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
            crop_strategy=args.crop,
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

    # Step 3a: Build karaoke captions (word-by-word drawtext chain)
    print("  Building karaoke caption chain…")
    karaoke_chain = build_karaoke(audio_file)
    karaoke_path = game_dir / "karaoke.filter"
    if karaoke_chain:
        if not args.dry_run:
            karaoke_path.write_text(karaoke_chain)
            word_count = karaoke_chain.count("drawtext=")
            print(f"  ✓ {karaoke_path.relative_to(PROJECT_ROOT)} ({word_count} words)")
    else:
        print(f"  ⚠  No alignment data — captions will be skipped for this render")

    # Step 3b: Build top-title overlay (singular or per-beat for Top X)
    print("  Building top-title overlay…")
    top_title_path = game_dir / "top_title.filter"
    top_chain = ""
    alignment_path = audio_file.parent / f"{audio_file.stem}.alignment.json"
    try:
        if alignment_path.exists():
            alignment = json.loads(alignment_path.read_text())
            beats_cfg = cfg.get("beats", [])
            # Topx mode if any beat declares top_title
            if any(b.get("top_title") for b in beats_cfg):
                top_chain = build_topx_top_title(beats_cfg, alignment, TOP_TITLE_FONT.resolve())
                mode = "topx"
            else:
                # `title` wins for compact display override; falls back to verticals' canonical fields
                singular_title = cfg.get("title") or cfg.get("game_title") or cfg.get("case_title")
                if singular_title:
                    audio_dur = alignment["character_end_times_seconds"][-1]
                    top_chain = build_singular_top_title(singular_title, audio_dur, TOP_TITLE_FONT.resolve())
                    mode = "singular"
                else:
                    mode = "skipped (no title field in config)"
            if top_chain and not args.dry_run:
                top_title_path.write_text(top_chain)
                print(f"  ✓ {top_title_path.relative_to(PROJECT_ROOT)} (mode={mode})")
            else:
                print(f"  ⚠  Top title: {mode}")
    except Exception as e:
        print(f"  ⚠  Top title generation failed: {e}")

    # Step 4: Print the FFmpeg encode command (chains karaoke + top-title)
    out_mp4 = PROJECT_ROOT / "output" / "game_videos" / f"{game_id}.mp4"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    vf_parts = []
    if karaoke_chain:
        vf_parts.append(f"$(cat {karaoke_path.relative_to(PROJECT_ROOT)})")
    if top_chain:
        vf_parts.append(f"$(cat {top_title_path.relative_to(PROJECT_ROOT)})")
    if vf_parts:
        vf_line = f"  -vf \"{','.join(vf_parts)}\" \\\n"
    else:
        vf_line = ""

    ffmpeg_cmd = (
        f"ffmpeg -y \\\n"
        f"  -f concat -safe 0 -i {concat_path.relative_to(PROJECT_ROOT)} \\\n"
        f"  -i {audio_file.relative_to(PROJECT_ROOT)} \\\n"
        f"{vf_line}"
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
