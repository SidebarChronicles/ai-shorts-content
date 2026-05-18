#!/usr/bin/env python3
"""YOLOv8 subject-tracking crop for Shorts trailers.

Detects the dominant subject per sampled frame (person, vehicle, animal) and
repositions a 9:16 crop window centered on it. Smooths the crop trajectory
with a low-pass filter so the result feels like a slow camera pan, not a
jittery follow-cam. Useful for gameplay / chase / car-chase trailers where
the action drifts left/right and pillarbox blur leaves dead bands.

Strategy:
  1. Open source clip with OpenCV.
  2. Every Nth frame (default 5 fps), run YOLOv8n and pick the highest-
     confidence bounding box from {person, car, motorcycle, airplane,
     bus, train, boat}.
  3. Interpolate x_center across in-between frames (linear).
  4. Smooth with a 1-second moving-average window so crops glide, not snap.
  5. Second pass: read each frame, crop a 9:16 window centered on the
     smoothed x at that frame, scale to 1080x1920, write to output.

Output is a self-contained 1080x1920 MP4 that downstream FFmpeg passes
(karaoke + top-title + audio mux) consume as if it were a pre-cropped
pillarbox clip. The pillarbox / center_crop strategies in
render_game_video.py are unaffected.

Usage:
    python scripts/smart_crop_yolo.py --input clips_portrait/clip_01.mp4 \\
                                       --output clips_portrait/clip_01.mp4
    python scripts/smart_crop_yolo.py --input clip.mp4 --output out.mp4 \\
                                       --sample-fps 4 --smooth-window 1.2

Requires: ultralytics, opencv-python, torch (auto-installed via pip).
Model: yolov8n.pt (~6 MB) downloaded automatically on first run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# YOLO weights cache — keep model file in assets/models/ instead of CWD
MODELS_DIR = PROJECT_ROOT / "assets" / "models"
MODEL_NAME = "yolov8n.pt"

# Output portrait dimensions (must match render_game_video.W/H)
OUT_W = 1080
OUT_H = 1920

# YOLO classes we care about (COCO indices)
# 0=person, 1=bicycle, 2=car, 3=motorcycle, 4=airplane, 5=bus, 6=train,
# 7=truck, 8=boat, 14=bird, 15=cat, 16=dog, 17=horse, 18=sheep, 19=cow
SUBJECT_CLASSES = (0, 1, 2, 3, 4, 5, 6, 7, 8, 14, 15, 16, 17, 18, 19)


def _moving_average(arr: np.ndarray, window: int) -> np.ndarray:
    """Symmetric moving average; handles short windows + boundaries gracefully."""
    if window <= 1 or len(arr) < 3:
        return arr.astype(float)
    pad = window // 2
    padded = np.pad(arr.astype(float), (pad, pad), mode="edge")
    kernel = np.ones(window) / window
    return np.convolve(padded, kernel, mode="valid")[: len(arr)]


def smart_crop(input_path: Path, output_path: Path, sample_fps: float = 5.0,
               smooth_window_seconds: float = 1.0, verbose: bool = False) -> None:
    """Run smart-crop on a single video and write the cropped result."""

    # Lazy import — only when this script is actually invoked
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        sys.exit("ERROR: ultralytics not installed. Run: "
                 ".venv-upload/bin/pip install ultralytics opencv-python")

    if not input_path.exists():
        sys.exit(f"ERROR: input not found: {input_path}")

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        sys.exit(f"ERROR: cannot open {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w_in = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h_in = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if n_frames < 5:
        sys.exit(f"ERROR: {input_path.name} has only {n_frames} frames")

    # 9:16 crop window from a (presumably) 16:9 source: full height, narrow width
    crop_w = int(round(h_in * 9 / 16))
    crop_h = h_in
    if crop_w > w_in:
        # Source is already portrait-ish; just use the full width and crop height
        crop_w = w_in
        crop_h = int(round(w_in * 16 / 9))

    sample_every = max(1, int(round(fps / sample_fps)))
    smooth_window = max(1, int(round(smooth_window_seconds * fps)))

    # ---- Pass 1: detect dominant subject every Nth frame ----
    # Stash the weights in assets/models/ so they don't pollute the project root.
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / MODEL_NAME
    # ultralytics auto-downloads to CWD by default; pass an absolute path to
    # the cache location so the weights live with other regeneratable assets.
    model = YOLO(str(model_path) if model_path.exists() else MODEL_NAME)
    if not model_path.exists():
        # ultralytics put it in CWD; move it
        cwd_pt = Path.cwd() / MODEL_NAME
        if cwd_pt.exists():
            cwd_pt.rename(model_path)

    detected_idx: list[int] = []
    detected_x: list[float] = []

    if verbose:
        print(f"  smart_crop pass 1/2: detect ({w_in}x{h_in}@{fps:.1f}fps, "
              f"sampling 1/{sample_every}, smooth {smooth_window_seconds}s)…")

    frame_idx = 0
    last_x = w_in / 2  # fallback to center if no detection
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_every == 0:
            # Predict on this single frame; suppress YOLO console spam
            results = model(frame, classes=list(SUBJECT_CLASSES),
                            verbose=False, conf=0.25)
            # results is a list of length 1 (single image)
            r = results[0]
            best = None
            best_score = 0.0
            if r.boxes is not None and len(r.boxes) > 0:
                # XYXY normalized to image dims; conf and cls are tensors
                xyxy = r.boxes.xyxy.cpu().numpy()
                conf = r.boxes.conf.cpu().numpy()
                area = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
                # Score = confidence × sqrt(relative area) — prefer big, clear subjects
                score = conf * np.sqrt(area / (w_in * h_in))
                idx = int(np.argmax(score))
                if score[idx] > best_score:
                    best = xyxy[idx]
                    best_score = score[idx]
            if best is not None:
                x_center = (best[0] + best[2]) / 2
                # Hold onto the last detection for the next interpolation gap
                last_x = float(x_center)
                detected_idx.append(frame_idx)
                detected_x.append(float(x_center))
            else:
                # No subject this sample — record last known to keep interp stable
                detected_idx.append(frame_idx)
                detected_x.append(last_x)
        frame_idx += 1

    cap.release()

    if not detected_idx:
        sys.exit(f"ERROR: no detections at all from {input_path.name} — "
                 f"fall back to pillarbox_blur instead")

    # ---- Interpolate per-frame x_center ----
    sample_indices = np.array(detected_idx)
    sample_x = np.array(detected_x)
    all_frames = np.arange(n_frames)
    per_frame_x = np.interp(all_frames, sample_indices, sample_x)

    # ---- Smooth so the camera glides, doesn't snap ----
    per_frame_x = _moving_average(per_frame_x, smooth_window)

    # Clamp the crop window so we never read outside the frame
    half_w = crop_w / 2
    per_frame_x = np.clip(per_frame_x, half_w, w_in - half_w)

    # ---- Pass 2: read frames again, crop with smoothed x, write 1080x1920 ----
    if verbose:
        print(f"  smart_crop pass 2/2: render → {output_path.name}…")

    cap = cv2.VideoCapture(str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # mp4v works on macOS; downstream FFmpeg passes will re-encode anyway
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (OUT_W, OUT_H))
    if not writer.isOpened():
        sys.exit(f"ERROR: cannot open writer for {output_path}")

    # Vertical crop center: just use the source center (subjects rarely top-bottom drift)
    cy = h_in / 2
    half_h = crop_h / 2
    y0 = int(round(max(0, cy - half_h)))
    y1 = int(round(min(h_in, cy + half_h)))

    for i in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break
        cx = float(per_frame_x[i])
        x0 = int(round(max(0, cx - half_w)))
        x1 = int(round(min(w_in, cx + half_w)))
        # Guard against off-by-one rounding
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        cropped = frame[y0:y1, x0:x1]
        if cropped.shape[1] != OUT_W or cropped.shape[0] != OUT_H:
            cropped = cv2.resize(cropped, (OUT_W, OUT_H), interpolation=cv2.INTER_AREA)
        writer.write(cropped)

    cap.release()
    writer.release()

    if verbose:
        print(f"  ✓ {output_path.relative_to(PROJECT_ROOT) if output_path.is_relative_to(PROJECT_ROOT) else output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Source clip (any 16:9 video)")
    parser.add_argument("--output", required=True, type=Path, help="Output 1080x1920 MP4 path")
    parser.add_argument("--sample-fps", type=float, default=5.0,
                        help="YOLO detection sampling rate (default 5 fps)")
    parser.add_argument("--smooth-window", type=float, default=1.0,
                        help="Moving-average smoothing window in seconds (default 1.0)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    smart_crop(args.input.resolve(), args.output.resolve(),
               sample_fps=args.sample_fps,
               smooth_window_seconds=args.smooth_window,
               verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
