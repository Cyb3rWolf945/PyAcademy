---
name: pixel-art-video
description: Produce pixel-art animated videos and GIFs for PyArena (trailers, tournament intros/recaps, champion reels, social clips, animated sprites) rendered frame by frame in code at low resolution and upscaled with nearest-neighbour, all inside Docker. Use when the user asks for a video, trailer, GIF, intro/outro, recap or animated loop in the PyArena pixel style.
---

# Pixel-art video (PyArena)

## Principles
- Same original identity as the **pixel-art** skill (theme palettes, fonts, sprites from `frontend/assets/gen_assets.py`). No assets, music or visuals from existing games or copyrighted sources.
- Render at a **native pixel resolution** (e.g. 320×180 for 16:9, 180×320 for 9:16) and upscale by an integer factor (×6 → 1920×1080) with **nearest-neighbour** only. Never blur or bilinear-scale.
- Frame-by-frame, deterministic: everything derives from the frame number and a fixed seed, so a re-render gives identical output.
- 12 or 24 fps for the stepped retro feel (motion in whole pixels); 30 fps only for scrolling text.

## Toolchain (no host installs)
- Python 3.12 + Pillow for drawing frames, run in a throwaway container: `docker run --rm -v "$PWD:/w" -w /w python:3.12-slim sh -c "pip -q install pillow && python tools/video/<script>.py"`.
- Encode with ffmpeg in a pinned container (e.g. `jrottenberg/ffmpeg:6.1-alpine`):
  - MP4: `-vf "scale=iw*6:ih*6:flags=neighbor" -c:v libx264 -pix_fmt yuv420p -crf 18`.
  - GIF: palettegen/paletteuse with `-vf "scale=iw*3:ih*3:flags=neighbor"` and `dither=none` (keep the palette crisp).
- Scripts live in `tools/video/` (not served to students); outputs go to `media/` (gitignored unless the user wants them versioned).
- Optional chiptune audio: synthesize square/triangle/noise waves in Python (`wave` module) from a simple note list, mix to WAV, mux with ffmpeg. Original melodies only.

## Structure of a script
1. `SCENES = [...]` timeline of (start_frame, end_frame, draw_fn).
2. `draw_fn(img, f, t)` draws sprites, text (Press Start 2P / Pixelify Sans from `frontend/vendor/fonts/`, rendered without antialiasing: draw on 1-bit masks or use `fontmode = "1"`), particles (square, palette-only colours).
3. Easing in whole pixels (`round()`), stepped holds for punchy motion.
4. Export PNG frames to a temp dir → ffmpeg → delete the frames.

## Typical deliverables
- **Tournament intro (5–8 s):** logo drop, "Torneio de Programação" title, theme island, the join code.
- **Champion reel (6 s):** podium with gold/bronze/copper medals, confetti, champion name. Generated from tournament data (only names already visible in the class, never public without consent).
- **Social clip 9:16** of the homepage island + leaderboard.
Check the first, middle and last frames as PNGs before encoding; report file sizes and durations.
