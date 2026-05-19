#!/usr/bin/env python3
"""Generalized scene + caption renderer for the truecrime-short skill.

Usage:
    python3 render_video.py <case_config.json>

Reads the case config, renders six stylized scenes (one per narration segment)
using template functions, bakes captions into per-chunk PNGs, and writes a
ffmpeg-concat timeline file. The actual encode is a separate ffmpeg step.

Outputs (relative to the project root):
    output/scripts/<case_id>/scenes/01..06_<segname>.png
    output/scripts/<case_id>/frames/f_NNN.png        (per-chunk caption frames)
    output/scripts/<case_id>/timeline_baked.txt      (concat list)

Then run ffmpeg:
    ffmpeg -y -f concat -safe 0 -i timeline_baked.txt \\
        -i assets/audio/narration_NN.aiff \\
        -vf "scale=720:1280,format=yuv420p" \\
        -c:v libx264 -preset ultrafast -crf 28 -g 60 \\
        -c:a aac -b:a 96k -shortest -movflags +faststart \\
        output/videos/<case_id>.mp4
"""

from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import json
import subprocess
import sys
import numpy as np

# -----------------------------------------------------------------------------
# Style constants — see skill/truecrime-short/visual_style_guide.md
# -----------------------------------------------------------------------------
W, H = 1080, 1920
BG_TOP = (6, 9, 22)
BG_MID = (16, 22, 44)
BG_BOT = (4, 6, 14)
ACCENT_RED = (220, 38, 38)
ACCENT_YELLOW = (250, 204, 21)
WHITE = (245, 245, 248)
GREY = (140, 145, 165)
DEEP_GREY = (50, 55, 75)

FONT_PATH = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PAUSE_SEC = 0.5

COLOR_MAP = {"red": ACCENT_RED, "yellow": ACCENT_YELLOW, "white": WHITE, "grey": GREY}


# -----------------------------------------------------------------------------
# Base canvas / chrome
# -----------------------------------------------------------------------------

def _resolve_font_path() -> str | None:
    """Resolve a usable bold font path, falling back through:
       1) FONT_PATH (Linux Google Fonts install — common on CI/cron hosts)
       2) assets/fonts/*Bold*.ttf (project-bundled fallback)
       3) None (caller switches to ImageFont.load_default())
    """
    if Path(FONT_PATH).exists():
        return FONT_PATH
    bundled = PROJECT_ROOT / "assets" / "fonts"
    if bundled.exists():
        for candidate in sorted(bundled.glob("*Bold*.ttf")):
            return str(candidate)
        for candidate in sorted(bundled.glob("*.ttf")):
            return str(candidate)
    return None


_RESOLVED_FONT_PATH: str | None = None


def font(size: int) -> ImageFont.FreeTypeFont:
    global _RESOLVED_FONT_PATH
    if _RESOLVED_FONT_PATH is None:
        _RESOLVED_FONT_PATH = _resolve_font_path()
        if _RESOLVED_FONT_PATH is None:
            print(
                f"  [warn] no usable font found at {FONT_PATH} or {PROJECT_ROOT}/assets/fonts/ — "
                f"falling back to PIL default font (renders will look unstyled)",
                file=sys.stderr,
            )
        elif _RESOLVED_FONT_PATH != FONT_PATH:
            print(
                f"  [info] using fallback font: {_RESOLVED_FONT_PATH}",
                file=sys.stderr,
            )
    if _RESOLVED_FONT_PATH is None:
        # PIL's load_default returns a bitmap font with a fixed size; size arg ignored.
        return ImageFont.load_default()
    return ImageFont.truetype(_RESOLVED_FONT_PATH, size)


_BASE_CACHE: Image.Image | None = None

def base_canvas() -> Image.Image:
    """Vertical gradient + scan lines. Cached at module level — gradient compute
    is vectorized via numpy (sub-second) and the result is reused for every
    scene in a single Python process via .copy()."""
    global _BASE_CACHE
    if _BASE_CACHE is not None:
        return _BASE_CACHE.copy()

    # Vectorized vertical gradient (top→mid→bot)
    y = np.arange(H, dtype=np.float32) / H
    u_top = np.clip(y / 0.5, 0.0, 1.0)
    u_bot = np.clip((y - 0.5) / 0.5, 0.0, 1.0)
    is_top = (y < 0.5).astype(np.float32)
    bg_top = np.array(BG_TOP, dtype=np.float32)
    bg_mid = np.array(BG_MID, dtype=np.float32)
    bg_bot = np.array(BG_BOT, dtype=np.float32)
    # row colors: shape (H, 3)
    rows = (
        is_top[:, None] * (bg_top + (bg_mid - bg_top) * u_top[:, None])
        + (1 - is_top[:, None]) * (bg_mid + (bg_bot - bg_mid) * u_bot[:, None])
    )
    arr = np.broadcast_to(rows[:, None, :], (H, W, 3)).astype(np.uint8)
    img = Image.fromarray(arr.copy(), "RGB")
    # Scan lines every 3px
    d = ImageDraw.Draw(img)
    for x in range(0, W, 3):
        d.line([(x, 0), (x, H)], fill=(20, 25, 45), width=1)
    _BASE_CACHE = img
    return img.copy()


def draw_header(d: ImageDraw.ImageDraw, line1: str, line2: str) -> None:
    d.rectangle([(80, 180), (W - 80, 280)], fill=(0, 0, 0))
    d.rectangle([(80, 180), (W - 80, 280)], outline=ACCENT_YELLOW, width=3)
    d.text((W // 2, 215), line1, font=font(30), anchor="mm", fill=ACCENT_YELLOW)
    d.text((W // 2, 255), line2, font=font(22), anchor="mm", fill=GREY)


def draw_footer(d: ImageDraw.ImageDraw) -> None:
    d.text((W // 2, 1860), "PUBLIC RECORD  ·  U.S. DEPARTMENT OF JUSTICE",
           font=font(26), anchor="mm", fill=DEEP_GREY)


def lbl(d: ImageDraw.ImageDraw, y: int, text: str, size: int, fill: tuple) -> None:
    d.text((W // 2, y), text, font=font(size), anchor="mm", fill=fill)


# -----------------------------------------------------------------------------
# Scene templates
# -----------------------------------------------------------------------------

def render_title(img: Image.Image, c: dict) -> Image.Image:
    d = ImageDraw.Draw(img)
    lbl(d, 700, c.get("label", "THE CASE OF"), 50, GREY)
    lbl(d, 880, c["main"], 130, WHITE)
    d.line([(W // 2 - 280, 960), (W // 2 + 280, 960)], fill=ACCENT_RED, width=4)
    if c.get("subline_top"):
        lbl(d, 1030, c["subline_top"], 44, ACCENT_YELLOW)
    if c.get("subline_bottom"):
        lbl(d, 1100, c["subline_bottom"], 32, GREY)
    if c.get("decorative_bar"):
        d.rectangle([(W // 2 - 200, 1400), (W // 2 + 200, 1470)], outline=DEEP_GREY, width=2)
        lbl(d, 1435, c["decorative_bar"], 28, DEEP_GREY)
    return img


def render_big_stat(img: Image.Image, c: dict) -> Image.Image:
    d = ImageDraw.Draw(img)
    lbl(d, 700, c["label"], 44, GREY)
    value_color = COLOR_MAP.get(c.get("value_color", "white"), WHITE)
    # Auto-shrink very long values
    val = c["value"]
    val_size = 260 if len(val) <= 5 else (200 if len(val) <= 7 else 150)
    lbl(d, 950, val, val_size, value_color)
    d.line([(W // 2 - 200, 1130), (W // 2 + 200, 1130)], fill=ACCENT_RED, width=4)
    if c.get("subline_top"):
        lbl(d, 1230, c["subline_top"], 36, ACCENT_YELLOW)
    if c.get("subline_bottom"):
        lbl(d, 1290, c["subline_bottom"], 30, GREY)
    if c.get("boxes"):
        box_y = 1450
        box_w = 280
        spacing = 30
        total = box_w * 3 + spacing * 2
        start = (W - total) // 2
        for i, (top, bottom) in enumerate(c["boxes"][:3]):
            x0 = start + i * (box_w + spacing)
            d.rectangle([(x0, box_y), (x0 + box_w, box_y + 120)], outline=DEEP_GREY, width=2)
            d.text((x0 + box_w // 2, box_y + 40), top, font=font(26), anchor="mm", fill=WHITE)
            d.text((x0 + box_w // 2, box_y + 85), bottom, font=font(22), anchor="mm", fill=GREY)
    return img


def render_location(img: Image.Image, c: dict) -> Image.Image:
    d = ImageDraw.Draw(img)
    lbl(d, 700, c["beat_label"], 44, ACCENT_RED)
    lbl(d, 820, c["date"], 90, WHITE)
    lbl(d, 920, c["place"], 44, GREY)
    shape = c.get("shape", "bullseye")
    if shape == "bullseye":
        cx, cy, r = W // 2, 1130, 100
        d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=ACCENT_YELLOW, width=4)
        d.line([(cx - r - 30, cy), (cx + r + 30, cy)], fill=ACCENT_YELLOW, width=2)
        d.line([(cx, cy - r - 30), (cx, cy + r + 30)], fill=ACCENT_YELLOW, width=2)
        d.ellipse([(cx - 8, cy - 8), (cx + 8, cy + 8)], fill=ACCENT_RED)
    elif shape == "pin":
        cx, cy = W // 2, 1130
        d.ellipse([(cx - 60, cy - 80), (cx + 60, cy + 40)], outline=ACCENT_RED, width=4)
        d.polygon([(cx - 30, cy + 40), (cx + 30, cy + 40), (cx, cy + 130)], fill=ACCENT_RED)
        d.ellipse([(cx - 15, cy - 30), (cx + 15, cy)], fill=BG_TOP)
    if c.get("stat_label"):
        lbl(d, 1330, c["stat_label"], 36, GREY)
    if c.get("stat_value"):
        sv = c["stat_value"]
        sz = 100 if len(sv) <= 10 else 76
        lbl(d, 1430, sv, sz, WHITE)
    if c.get("stat_sub"):
        lbl(d, 1530, c["stat_sub"], 48, ACCENT_YELLOW)
    return img


def render_three_step(img: Image.Image, c: dict) -> Image.Image:
    d = ImageDraw.Draw(img)
    lbl(d, 700, c["header"], 44, ACCENT_RED)
    step_y = 1130
    step_w = 280
    spacing = 30
    total = step_w * 3 + spacing * 2
    start = (W - total) // 2
    for i, (num, label) in enumerate(c["steps"][:3]):
        x0 = start + i * (step_w + spacing)
        d.rectangle([(x0, step_y), (x0 + step_w, step_y + 280)], outline=DEEP_GREY, width=2)
        d.text((x0 + step_w // 2, step_y + 90), num, font=font(100), anchor="mm",
               fill=ACCENT_YELLOW if i < 2 else ACCENT_RED)
        d.line([(x0 + 40, step_y + 175), (x0 + step_w - 40, step_y + 175)], fill=DEEP_GREY, width=2)
        d.text((x0 + step_w // 2, step_y + 230), label, font=font(34), anchor="mm", fill=WHITE)
    return img


def render_receipt(img: Image.Image, c: dict) -> Image.Image:
    d = ImageDraw.Draw(img)
    lbl(d, 700, c["header"], 44, GREY)
    items = c["items"][:5]
    list_x_left, list_x_right = 130, W - 130
    row_y = 850
    row_height = 145
    for i, (left, right) in enumerate(items):
        y = row_y + i * row_height
        d.rectangle([(list_x_left - 10, y - 5), (list_x_left + 10, y + 15)], fill=ACCENT_RED)
        d.text((list_x_left + 40, y), left, font=font(42), anchor="lm", fill=WHITE)
        d.text((list_x_right, y), right, font=font(38), anchor="rm", fill=ACCENT_YELLOW)
        for dx in range(list_x_left, list_x_right, 14):
            d.line([(dx, y + 65), (dx + 6, y + 65)], fill=DEEP_GREY, width=2)
    return img


def render_outcome(img: Image.Image, c: dict) -> Image.Image:
    d = ImageDraw.Draw(img)
    lbl(d, 780, c.get("header", "SENTENCED TO"), 60, WHITE)
    val = c.get("months", "")
    val_size = 280 if len(val) <= 3 else (200 if len(val) <= 5 else 150)
    lbl(d, 1000, val, val_size, WHITE)
    lbl(d, 1200, c.get("months_unit", "MONTHS"), 60, ACCENT_RED)
    d.line([(W // 2 - 200, 1320), (W // 2 + 200, 1320)], fill=DEEP_GREY, width=2)
    if c.get("restitution_label"):
        lbl(d, 1400, c["restitution_label"], 36, GREY)
    if c.get("restitution_value"):
        rv = c["restitution_value"]
        sz = 60 if len(rv) <= 14 else 44
        lbl(d, 1470, rv, sz, ACCENT_YELLOW)
    return img


SCENE_RENDERERS = {
    "title": render_title,
    "big_stat": render_big_stat,
    "location": render_location,
    "three_step": render_three_step,
    "receipt": render_receipt,
    "outcome": render_outcome,
}


# -----------------------------------------------------------------------------
# Caption baking
# -----------------------------------------------------------------------------

def bake_caption(bg: Image.Image, text: str) -> Image.Image:
    img = bg.copy()
    d = ImageDraw.Draw(img)
    cap_font = font(76)
    bbox = d.textbbox((0, 0), text, font=cap_font)
    text_w = bbox[2] - bbox[0]
    lines = [text]
    if text_w > 0.88 * W:
        words = text.split()
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    y_positions = [1730] if len(lines) == 1 else [1680, 1770]
    for line, y in zip(lines, y_positions):
        for ox, oy in [(-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3), (-3, 3), (3, -3)]:
            d.text((W // 2 + ox, y + oy), line, font=cap_font, anchor="mm", fill=(0, 0, 0))
        d.text((W // 2, y), line, font=cap_font, anchor="mm", fill=WHITE)
    return img


# -----------------------------------------------------------------------------
# Timing
# -----------------------------------------------------------------------------

def ffprobe_duration(audio_path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(audio_path),
    ])
    return float(out.strip())


def compute_scene_times(audio_seconds: float, segments: list[dict]) -> list[tuple[float, float]]:
    seg_words = [s["word_count"] for s in segments]
    n_pauses = len(segments) - 1
    speech = audio_seconds - n_pauses * PAUSE_SEC
    wps = sum(seg_words) / speech
    seg_speech = [w / wps for w in seg_words]
    times = []
    t = 0.0
    for i, sec in enumerate(seg_speech):
        pause_after = PAUSE_SEC if i < len(seg_speech) - 1 else 0.0
        times.append((t, t + sec + pause_after))
        t += sec + pause_after
    return times


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main(config_path: str) -> None:
    cfg = json.loads(Path(config_path).read_text())
    case_id = cfg["case_id"]
    audio_path = PROJECT_ROOT / cfg["audio_file"]
    out_dir = PROJECT_ROOT / "output" / "scripts" / case_id
    scenes_dir = out_dir / "scenes"
    frames_dir = out_dir / "frames"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 1. Render the six scene backgrounds
    scene_imgs = []
    seg_names = [s["name"] for s in cfg["segments"]]
    for i, (scene_def, seg_name) in enumerate(zip(cfg["scenes"], seg_names), start=1):
        img = base_canvas()
        d = ImageDraw.Draw(img)
        draw_header(d, cfg["header_line_1"], cfg["header_line_2"])
        renderer = SCENE_RENDERERS[scene_def["type"]]
        img = renderer(img, scene_def)
        d = ImageDraw.Draw(img)
        draw_footer(d)
        path = scenes_dir / f"{i:02d}_{seg_name}.png"
        img.save(path, "PNG", optimize=True)
        scene_imgs.append(img)
        print(f"  scene {i} ({seg_name}) → {path.name}")

    # 2. Compute scene timing from audio duration
    audio_seconds = ffprobe_duration(audio_path)
    scene_times = compute_scene_times(audio_seconds, cfg["segments"])

    # 3. Bake captions per chunk
    for f in frames_dir.glob("*.png"):
        try:
            f.unlink()
        except PermissionError:
            pass  # leftover handle from prior ffmpeg

    timeline_lines = []
    frame_idx = 0
    for seg_i, seg in enumerate(cfg["segments"]):
        seg_start, seg_end = scene_times[seg_i]
        pause = PAUSE_SEC if seg_i < len(cfg["segments"]) - 1 else 0.0
        speech_end = seg_end - pause
        per_chunk = (speech_end - seg_start) / len(seg["chunks"])
        for ci, chunk in enumerate(seg["chunks"]):
            frame_idx += 1
            baked = bake_caption(scene_imgs[seg_i], chunk)
            path = frames_dir / f"f_{frame_idx:03d}.png"
            baked.save(path, "PNG", compress_level=1)
            dur = per_chunk + (pause if ci == len(seg["chunks"]) - 1 else 0.0)
            timeline_lines.append(f"file '{path.resolve()}'")
            timeline_lines.append(f"duration {dur:.3f}")
    timeline_lines.append(timeline_lines[-2])  # concat demuxer needs last file repeated

    timeline_path = out_dir / "timeline_baked.txt"
    timeline_path.write_text("\n".join(timeline_lines) + "\n")
    print(f"  baked {frame_idx} caption frames over {audio_seconds:.2f}s")
    print(f"  timeline → {timeline_path}")
    print()
    print("Next: ffmpeg encode (see SKILL.md for the command).")


if __name__ == "__main__":
    main(sys.argv[1])
