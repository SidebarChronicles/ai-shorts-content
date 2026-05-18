#!/usr/bin/env python3
"""Render scenes + ASS captions for the GothFerrari short.

Run inside the Linux sandbox where PIL + Poppins-Bold are available.
Outputs:
  output/scripts/01_gothferrari/scenes/01_hook.png ... 06_outcome.png
  output/scripts/01_gothferrari/captions.ass
  output/scripts/01_gothferrari/timeline.txt   (ffmpeg concat list)

This is the Tier-2 in-session renderer. The autonomous Tier-4 build will
recreate it in pipeline/composer.py + pipeline/captions.py + scene_planner.py.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import random

# ---- paths ----------------------------------------------------------------
PROJECT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT / "output" / "scripts" / "01_gothferrari"
SCENES_DIR = OUT_DIR / "scenes"
SCENES_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"

# ---- canvas + palette -----------------------------------------------------
W, H = 1080, 1920
BG_TOP = (6, 9, 22)
BG_MID = (16, 22, 44)
BG_BOT = (4, 6, 14)
ACCENT_RED = (220, 38, 38)
ACCENT_YELLOW = (250, 204, 21)
WHITE = (245, 245, 248)
GREY = (140, 145, 165)
DEEP_GREY = (50, 55, 75)


def base_canvas():
    """Dark vertical gradient + scan lines + faint grain."""
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for y in range(H):
        t = y / H
        if t < 0.5:
            u = t / 0.5
            c = tuple(int(BG_TOP[i] + (BG_MID[i] - BG_TOP[i]) * u) for i in range(3))
        else:
            u = (t - 0.5) / 0.5
            c = tuple(int(BG_MID[i] + (BG_BOT[i] - BG_MID[i]) * u) for i in range(3))
        for x in range(W):
            px[x, y] = c

    d = ImageDraw.Draw(img)
    for x in range(0, W, 3):
        d.line([(x, 0), (x, H)], fill=(20, 25, 45), width=1)

    random.seed(11)
    base = img.copy()
    for _ in range(45000):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        v = random.randint(0, 60)
        px[x, y] = (v, v, v)
    img = Image.blend(base, img, 0.18)
    return img


def font(size):
    return ImageFont.truetype(FONT_PATH, size)


def draw_header(d, line1="U.S. DISTRICT COURT  ·  DISTRICT OF COLUMBIA",
                line2="CASE 24CR417  ·  UNITED STATES v. FERRO"):
    d.rectangle([(80, 180), (W - 80, 280)], fill=(0, 0, 0))
    d.rectangle([(80, 180), (W - 80, 280)], outline=ACCENT_YELLOW, width=3)
    d.text((W // 2, 215), line1, font=font(30), anchor="mm", fill=ACCENT_YELLOW)
    d.text((W // 2, 255), line2, font=font(22), anchor="mm", fill=GREY)


def draw_footer(d, text="PUBLIC RECORD  ·  U.S. DEPARTMENT OF JUSTICE"):
    d.text((W // 2, 1820), text, font=font(28), anchor="mm", fill=DEEP_GREY)


def draw_centered_label(d, y, text, size, fill):
    d.text((W // 2, y), text, font=font(size), anchor="mm", fill=fill)


# ---- scene renderers ------------------------------------------------------

def scene_01_hook():
    """Hook: introduce the case identity. Captions handle the spoken hook."""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    draw_header(d)
    draw_centered_label(d, 700, "THE CASE OF", 50, GREY)
    draw_centered_label(d, 880, "GOTHFERRARI", 130, WHITE)
    # Subtitle bars (decorative)
    d.line([(W // 2 - 280, 960), (W // 2 + 280, 960)], fill=ACCENT_RED, width=4)
    draw_centered_label(d, 1030, "MARLON FERRO  ·  AGE 20", 44, ACCENT_YELLOW)
    draw_centered_label(d, 1100, "SANTA ANA, CALIFORNIA", 32, GREY)
    # Glitch hint — small "encrypted" tag
    d.rectangle([(W // 2 - 200, 1400), (W // 2 + 200, 1470)], outline=DEEP_GREY, width=2)
    draw_centered_label(d, 1435, "0x4D 0x46 0x52 0x52 0x4F", 28, DEEP_GREY)
    draw_footer(d)
    return img


def scene_02_setup():
    """Setup: $250M scale + 'instrument of last resort' framing."""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    draw_header(d)
    draw_centered_label(d, 700, "CRYPTOCURRENCY STOLEN", 44, GREY)
    draw_centered_label(d, 950, "$250M", 260, WHITE)
    d.line([(W // 2 - 200, 1130), (W // 2 + 200, 1130)], fill=ACCENT_RED, width=4)
    draw_centered_label(d, 1230, "BY A SOCIAL-ENGINEERING RING", 36, ACCENT_YELLOW)
    draw_centered_label(d, 1290, "LATE 2023  →  EARLY 2025", 30, GREY)
    # Sub-stat boxes
    box_y = 1450
    boxes = [("CA · CT · NY", "BASE"),
             ("FL · ABROAD", "REACH"),
             ("HARDWARE WALLETS", "TARGET")]
    box_w = 280
    spacing = 30
    total_w = box_w * 3 + spacing * 2
    start_x = (W - total_w) // 2
    for i, (top, bottom) in enumerate(boxes):
        x0 = start_x + i * (box_w + spacing)
        d.rectangle([(x0, box_y), (x0 + box_w, box_y + 120)],
                    outline=DEEP_GREY, width=2)
        d.text((x0 + box_w // 2, box_y + 40), top,
               font=font(26), anchor="mm", fill=WHITE)
        d.text((x0 + box_w // 2, box_y + 85), bottom,
               font=font(22), anchor="mm", fill=GREY)
    draw_footer(d)
    return img


def scene_03_heist1():
    """Heist 1: Feb 2024, Winnsboro TX, 100 BTC."""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    draw_header(d)
    draw_centered_label(d, 700, "BREAK-IN #1", 44, ACCENT_RED)
    draw_centered_label(d, 820, "FEB · 2024", 90, WHITE)
    draw_centered_label(d, 920, "WINNSBORO, TEXAS", 44, GREY)

    # Decorative target reticle drawn with lines
    cx, cy, r = W // 2, 1180, 110
    d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=ACCENT_YELLOW, width=4)
    d.line([(cx - r - 30, cy), (cx + r + 30, cy)], fill=ACCENT_YELLOW, width=2)
    d.line([(cx, cy - r - 30), (cx, cy + r + 30)], fill=ACCENT_YELLOW, width=2)
    d.ellipse([(cx - 8, cy - 8), (cx + 8, cy + 8)], fill=ACCENT_RED)

    # Stat block
    draw_centered_label(d, 1430, "STOLEN", 36, GREY)
    draw_centered_label(d, 1530, "100 BTC", 110, WHITE)
    draw_centered_label(d, 1640, "≈ $5,000,000", 50, ACCENT_YELLOW)
    draw_footer(d)
    return img


def scene_04_heist2():
    """Heist 2: July 2024, NM, brick + window + camera."""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    draw_header(d)
    draw_centered_label(d, 700, "BREAK-IN #2", 44, ACCENT_RED)
    draw_centered_label(d, 820, "JUL · 2024", 90, WHITE)
    draw_centered_label(d, 920, "NEW MEXICO", 44, GREY)

    # Three step indicators
    step_y = 1180
    step_w = 280
    steps = [("01", "SURVEIL"), ("02", "BRICK"), ("03", "CAUGHT")]
    spacing = 30
    total_w = step_w * 3 + spacing * 2
    start_x = (W - total_w) // 2
    for i, (num, label) in enumerate(steps):
        x0 = start_x + i * (step_w + spacing)
        # Outline box
        d.rectangle([(x0, step_y), (x0 + step_w, step_y + 280)],
                    outline=DEEP_GREY, width=2)
        # Number
        d.text((x0 + step_w // 2, step_y + 90), num,
               font=font(100), anchor="mm",
               fill=ACCENT_YELLOW if i < 2 else ACCENT_RED)
        # Divider
        d.line([(x0 + 40, step_y + 175), (x0 + step_w - 40, step_y + 175)],
               fill=DEEP_GREY, width=2)
        # Label
        d.text((x0 + step_w // 2, step_y + 230), label,
               font=font(34), anchor="mm", fill=WHITE)

    draw_centered_label(d, 1620, "iCLOUD TRACKED  ·  WINDOW SMASHED", 32, GREY)
    draw_centered_label(d, 1680, "HOME CAMERA RECORDED THE BURGLARY", 32, GREY)
    draw_footer(d)
    return img


def scene_05_rewards():
    """Rewards: lavish spending receipt-style."""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    draw_header(d)
    draw_centered_label(d, 700, "WHERE THE MONEY WENT", 44, GREY)
    # Receipt-like list
    items = [
        ("HERMÈS BIRKIN BAGS", "GIFTS"),
        ("EXOTIC CARS", "UP TO $3.8M"),
        ("NIGHTCLUB NIGHTS", "UP TO $500K"),
        ("PRIVATE JETS", "RENTAL"),
        ("DESIGNER CLOTHING", "$255,000+"),
    ]
    list_x_left = 130
    list_x_right = W - 130
    row_y = 850
    row_height = 145
    for i, (left, right) in enumerate(items):
        y = row_y + i * row_height
        # Bullet square
        d.rectangle([(list_x_left - 10, y - 5), (list_x_left + 10, y + 15)],
                    fill=ACCENT_RED)
        # Left label
        d.text((list_x_left + 40, y), left, font=font(46), anchor="lm", fill=WHITE)
        # Right value
        d.text((list_x_right, y), right, font=font(40), anchor="rm", fill=ACCENT_YELLOW)
        # Dotted divider
        for dx in range(list_x_left, list_x_right, 14):
            d.line([(dx, y + 65), (dx + 6, y + 65)], fill=DEEP_GREY, width=2)
    draw_footer(d)
    return img


def scene_06_outcome():
    """Outcome — already designed (the sample we showed first)."""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    draw_header(d, line2="CASE 24CR417  ·  SENTENCED MAY 6, 2026")
    draw_centered_label(d, 780, "SENTENCED TO", 60, WHITE)
    draw_centered_label(d, 1000, "78", 280, WHITE)
    draw_centered_label(d, 1200, "MONTHS", 60, ACCENT_RED)
    d.line([(W // 2 - 200, 1320), (W // 2 + 200, 1320)], fill=DEEP_GREY, width=2)
    draw_centered_label(d, 1400, "RESTITUTION", 36, GREY)
    draw_centered_label(d, 1470, "$2,500,000", 60, ACCENT_YELLOW)
    draw_footer(d)
    return img


# ---- timing ---------------------------------------------------------------
AUDIO_DURATION = 62.322  # ffprobe-measured

# Segment word counts (must match script.md)
SEG_WORDS = [24, 34, 21, 34, 25, 29]
# Explicit silence pauses inserted by `say` between segments (5 × 500ms)
N_PAUSES = 5
PAUSE_SEC = 0.5
SPEECH_SEC = AUDIO_DURATION - N_PAUSES * PAUSE_SEC  # = 59.82
WORDS_PER_SEC = sum(SEG_WORDS) / SPEECH_SEC  # words per second of speech

# Compute per-segment speech duration
seg_speech = [w / WORDS_PER_SEC for w in SEG_WORDS]

# Cumulative scene start/end times (a scene includes the pause that follows it)
scene_times = []
t = 0.0
for i, sec in enumerate(seg_speech):
    end_speech = t + sec
    pause_after = PAUSE_SEC if i < len(seg_speech) - 1 else 0.0
    scene_end = end_speech + pause_after
    scene_times.append((t, scene_end))
    t = scene_end


# ---- caption chunks per segment ------------------------------------------
SEG_CHUNKS = [
    # Segment 1 — Hook (24 words)
    ["WHEN HACKERS COULDN'T", "TRICK THEIR VICTIMS",
     "INTO HANDING OVER", "THEIR CRYPTO",
     "THEY CALLED", "MARLON FERRO",
     "HE'D BREAK INTO", "YOUR HOUSE", "AND TAKE IT"],
    # Segment 2 — Setup (34 words)
    ["FERRO, 20, WAS", "THE \"INSTRUMENT", "OF LAST RESORT\"",
     "FOR A", "$250 MILLION", "SOCIAL-ENGINEERING RING",
     "WHEN VICTIMS STORED", "THEIR CRYPTO ON", "HARDWARE WALLETS —",
     "DEVICES THAT", "CAN'T BE HACKED", "REMOTELY —",
     "THE ENTERPRISE", "SENT HIM IN"],
    # Segment 3 — Heist 1 (21 words)
    ["FEBRUARY 2024", "WINNSBORO, TEXAS",
     "FERRO BROKE INTO", "A HOME",
     "AND WALKED OUT WITH", "100 BITCOIN",
     "MORE THAN", "FIVE MILLION DOLLARS"],
    # Segment 4 — Heist 2 (34 words)
    ["JULY 2024", "NEW MEXICO",
     "HE STAKED OUT", "THE HOUSE FOR DAYS",
     "WHEN CO-CONSPIRATORS", "TRACKED THE VICTIM'S iCLOUD",
     "AND CONFIRMED", "HE WAS GONE",
     "FERRO SMASHED", "A WINDOW WITH A BRICK",
     "THE HOME CAMERA", "CAUGHT HIM"],
    # Segment 5 — Rewards (25 words)
    ["THE STOLEN MONEY", "BOUGHT HERMÈS",
     "BIRKIN BAGS", "EXOTIC CARS",
     "UP TO $3.8 MILLION", "NIGHTCLUB TABS OF",
     "HALF A MILLION A NIGHT", "AND PRIVATE JETS"],
    # Segment 6 — Outcome (29 words)
    ["FERRO WAS ARRESTED", "WITH TWO FIREARMS",
     "AND A FAKE ID", "THIS MONTH",
     "A FEDERAL JUDGE", "SENTENCED HIM TO",
     "78 MONTHS IN PRISON —", "AND $2.5 MILLION",
     "IN RESTITUTION"],
]


def fmt_ts(seconds):
    """ASS time format: H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def build_ass():
    """Distribute chunks evenly across each segment's *speech* time."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Poppins,84,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2,2,80,80,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = []
    for seg_i, chunks in enumerate(SEG_CHUNKS):
        seg_start, seg_end = scene_times[seg_i]
        # Pause is at the end of the scene window; captions stay within speech window
        pause = PAUSE_SEC if seg_i < len(SEG_CHUNKS) - 1 else 0.0
        speech_end = seg_end - pause
        speech_duration = speech_end - seg_start
        per = speech_duration / len(chunks)
        for ci, chunk in enumerate(chunks):
            start_t = seg_start + ci * per
            end_t = seg_start + (ci + 1) * per - 0.02  # tiny gap
            text = chunk.replace(",", "\\h,").replace("'", "'")  # escape if needed
            lines.append(
                f"Dialogue: 0,{fmt_ts(start_t)},{fmt_ts(end_t)},Default,,0,0,0,,{chunk}"
            )

    return header + "\n".join(lines) + "\n"


def build_timeline():
    """ffmpeg concat list — each scene shown for its full window duration."""
    out = []
    for i, (start, end) in enumerate(scene_times, start=1):
        dur = end - start
        png = SCENES_DIR / f"{i:02d}_{['hook','setup','heist1','heist2','rewards','outcome'][i-1]}.png"
        out.append(f"file '{png}'")
        out.append(f"duration {dur:.3f}")
    # concat demuxer needs the final file repeated without a duration
    last = SCENES_DIR / "06_outcome.png"
    out.append(f"file '{last}'")
    return "\n".join(out) + "\n"


def main():
    renderers = [
        ("01_hook.png", scene_01_hook),
        ("02_setup.png", scene_02_setup),
        ("03_heist1.png", scene_03_heist1),
        ("04_heist2.png", scene_04_heist2),
        ("05_rewards.png", scene_05_rewards),
        ("06_outcome.png", scene_06_outcome),
    ]
    for name, fn in renderers:
        path = SCENES_DIR / name
        fn().save(path, "PNG", optimize=True)
        print(f"  scene  {name}")

    ass_path = OUT_DIR / "captions.ass"
    ass_path.write_text(build_ass())
    print(f"  ass    {ass_path.name}")

    timeline_path = OUT_DIR / "timeline.txt"
    timeline_path.write_text(build_timeline())
    print(f"  timing {timeline_path.name}")

    print()
    print("scene timings:")
    names = ["hook", "setup", "heist1", "heist2", "rewards", "outcome"]
    for i, (s, e) in enumerate(scene_times):
        print(f"  {i+1} {names[i]:>8s}  {s:6.2f}s → {e:6.2f}s  ({e-s:5.2f}s)")
    print(f"  audio total = {AUDIO_DURATION}s")


if __name__ == "__main__":
    main()
