# Visual Style Guide — Game Shorts

## Core concept

Background = real trailer clips (not static PNG scenes).
Text = FFmpeg `drawtext` for game title + beat labels.
Captions = ASS subtitle file (same format as truecrime pipeline).

The goal is "premium gaming editorial" — clean, high-contrast, reads well in portrait.
Not RGB chaos. Not clickbait neon. Think: Epic Games Store aesthetic.

---

## Color palette

| Role | Hex | RGB | Usage |
|---|---|---|---|
| Accent primary | `#8B5CF6` | (139, 92, 246) | Game title text, beat labels |
| Accent secondary | `#06B6D4` | (6, 182, 212) | CTA text, highlights |
| Primary text | `#FFFFFF` | (255, 255, 255) | Caption narration |
| Clip overlay tint | `rgba(0,0,0,0.45)` | 45% black | Over every clip for readability |
| Background fallback | `#0D0D0D` | (13, 13, 13) | Used if clip aspect fails |

---

## Portrait clip handling

Game trailers are 16:9. We center-crop to 9:16 (1080×1920):

```bash
ffmpeg -i clip_NN.mp4 \
  -vf "scale=1920:1080,scale=iw*1920/ih:1920,crop=1080:1920" \
  clip_NN_portrait_raw.mp4
```

Then apply dark overlay to ensure text readability:
```bash
ffmpeg -i clip_NN_portrait_raw.mp4 \
  -vf "colorchannelmixer=rr=0.55:gg=0.55:bb=0.55" \
  clip_NN_portrait.mp4
```
(colorchannelmixer at 0.55 = ~45% darkened — equivalent to 45% black overlay)

Avoid:
- Clips with talking heads or developer interviews (use gameplay / CGI footage only)
- Very dark trailers where the overlay makes scenes unreadable — pick brighter segments

---

## Text overlay (via FFmpeg drawtext)

### Game title — first clip only
```
fontfile=/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf
text='GAME TITLE'
fontsize=72
fontcolor=0x8B5CF6
x=(w-text_w)/2
y=200
box=1
boxcolor=black@0.7
boxborderw=24
```

### Platform + release label — first clip only
```
fontsize=44
fontcolor=0x06B6D4
y=310
```
Example: `PC / PS5 / XBOX  •  OUT NOW`

---

## Caption styling (ASS)

```
[Script Info]
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Name=Default,Fontname=Poppins Bold,Fontsize=72,PrimaryColour=&H00FFFFFF,
OutlineColour=&H00000000,Outline=4,Shadow=0,Alignment=2,
MarginV=240
```

- 2–3 words per flash (same chunking as truecrime)
- All-caps for emphasis words, mixed case otherwise
- Position: lower third (~y=1650 from top in 1920px canvas), centered

---

## Clip selection guide

4 clips for 4 beats:

| Beat | Clip selection criteria |
|---|---|
| Hook | The most visually spectacular moment in the first 30% of trailer |
| Gameplay | Clear gameplay footage — player character visible, action happening |
| Standout | The scene that makes the game look unique — could be a mechanic reveal or set-piece |
| CTA | Either a title card from the trailer, or a cinematic shot. Avoid cluttered UI. |

Each clip: 8–14 seconds long. Total clips runtime should exceed audio duration by 2–4s
so there's no visual stutter at the end.
