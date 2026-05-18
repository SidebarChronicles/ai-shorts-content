# Visual Style Guide — TrueCrime Shorts

Locked in from the GothFerrari run. All scenes share this base aesthetic.

## Palette

| Role | Color | Hex (approx) | RGB |
|---|---|---|---|
| Background top | Deep navy | `#06091610` | (6, 9, 22) |
| Background mid | Mid navy | `#10162C` | (16, 22, 44) |
| Background bottom | Near-black | `#04060E` | (4, 6, 14) |
| Accent red | Alarm red | `#DC2626` | (220, 38, 38) |
| Accent yellow | Evidence-tag yellow | `#FACC15` | (250, 204, 21) |
| Primary text | Near-white | `#F5F5F8` | (245, 245, 248) |
| Secondary text | Cool grey | `#8C91A5` | (140, 145, 165) |
| Deep grey (outlines) | `#32374B` | (50, 55, 75) |

## Typography

- **Single typeface: Poppins Bold** (`/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf`)
- Always uppercase for headers, stats, labels
- Size scale: 22, 30, 36, 44, 60, 76, 90, 100, 130, 280
- Captions: 76px white with 8-direction black outline (4px), centered horizontally

## Canvas

- **1080×1920** (vertical 9:16) — renderer output
- Encode resolution **720×1280** — fits the 45s sandbox budget; YouTube upscales
- Safe text zones:
  - Header strip: y = 180–280
  - Main content: y = 700–1500
  - Caption band: y = 1700–1820 (stays clear of main content + footer)
  - Footer: y = 1860

## Required scene elements (every scene)

- **Vertical gradient background** (top → mid → bottom navy)
- **Faint vertical scan lines** every 3px (atmospheric detail)
- **Header strip** at y=180-280: black box, yellow 3px outline, court name + case caption
- **Footer line** at y=1860: "PUBLIC RECORD · U.S. DEPARTMENT OF JUSTICE" in deep grey

## Scene type templates

The renderer picks one of these per scene based on `case_config.json`:

### `title` — Hook scene
- Label (small, grey) above main
- Main title (large, white, ~130pt)
- Red underline accent
- Subline (yellow, ~44pt) with defendant name + age + city
- Optional decorative bar (e.g. "0x4D 0x46 0x52..." encrypted feel)

### `big_stat` — Single-number focus
- Label (medium, grey) above
- Giant number (white, 260–280pt)
- Color-accented suffix (red or yellow, 60pt)
- Subline (yellow, 30-40pt) for context
- Optional 3 info-boxes below with sub-stats

### `location` — Place + date + key fact
- Beat label (red, 44pt) — e.g. "BREAK-IN #1"
- Big date (white, 90pt) — e.g. "FEB · 2024"
- Place name (grey, 44pt)
- Decorative element (bullseye target, map outline, location pin)
- Stat block below (label / value / sub-value)

### `three_step` — Process visualization
- Beat label
- Three outlined boxes side-by-side: number (large yellow/red) + label
- Subline below if needed
- NO bottom-zone labels (reserved for captions)

### `receipt` — Itemized list
- Header label
- 5 rows with red bullet square, left-aligned label, right-aligned value, dotted divider
- Each row ~145px tall

### `outcome` — Closer card
- "SENTENCED TO" label (white, 60pt)
- Big number (white, 280pt) — months
- "MONTHS" (red, 60pt) below
- Divider line
- Restitution label + amount (yellow, 60pt)

## Caption styling

- All caps
- Poppins Bold 76pt
- White (#F5F5F8) with 8-direction black outline (4px)
- Position: y=1730 (single line) or y=1680 + y=1770 (two-line auto-split when text > 88% width)
- One chunk per ~1 second of speech (~2-3 words per chunk)
- Chunk holds during the inter-segment 500ms pause

## Encoding settings (FFmpeg)

```
-vf "scale=720:1280,format=yuv420p"
-c:v libx264 -preset ultrafast -crf 28 -g 60
-c:a aac -b:a 96k
-shortest -movflags +faststart
```

(`-tune stillimage` was tried but added latency on ARM. Default is fine.)

## What NOT to use

- No AI-generated images of real people (defamation risk)
- No stock footage with recognizable faces
- No copyrighted footage (gameplay, news clips)
- No emoji in scene text (caption emojis are OK)
- No more than 2 accent colors per scene (red + yellow + white only)
