#!/usr/bin/env python3
"""Compose the demo videos: input overlay, 1080p side-by-side cut for YouTube,
title and end cards, and the recorded game audio (left = original, right = patch).

    make_demo_video.py <orig shots> <orig log.json> <orig.wav> <patch shots> <patch log.json> <patch.wav> <out dir>
"""
import json, subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
FPS = 30
OUT_W, OUT_H = 1920, 1080
GW, GH, TOP, PANEL, GAP = 944, 708, 46, 150, 32       # one pane
BTN = dict(A=128, B=64, Z=32, R=4096, START=16)
COLORS = dict(A=(60, 110, 255), B=(40, 190, 70), Z=(200, 200, 200), R=(200, 200, 200), START=(230, 60, 60))
TITLE = 'STAR WARS: SHADOWS OF THE EMPIRE (N64)'
SUBTITLE = 'Lock-on controls patch'
FEATURES = [
    'Camera-relative movement: Dash runs where you push the stick',
    'Lazy follow camera, Z recenters it behind Dash',
    'Z-targeting: lock on, circle-strafe, shots home in',
    'Letterbox bars and lock-on reticle',
    'Native aim (Z) and strafe (R) still work when no enemy is near',
]


def font(path, size):
    return ImageFont.truetype(path, size)


def pane(img, entry, title, accent):
    out = Image.new('RGB', (GW, TOP + GH + PANEL), (18, 18, 22))
    out.paste(img.convert('RGB').resize((GW, GH), Image.Resampling.LANCZOS), (0, TOP))
    d = ImageDraw.Draw(out)
    d.rectangle((0, 0, GW, TOP), fill=accent)
    d.text((16, 8), title, font=font(BOLD, 28), fill=(255, 255, 255))
    y0 = TOP + GH
    cx, cy, r = 86, y0 + PANEL // 2 + 6, 56
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(120, 120, 130), width=3)
    d.line((cx - r, cy, cx + r, cy), fill=(60, 60, 70))
    d.line((cx, cy - r, cx, cy + r), fill=(60, 60, 70))
    sx, sy = cx + entry['x'] / 80 * (r - 10), cy - entry['y'] / 80 * (r - 10)
    d.line((cx, cy, sx, sy), fill=(255, 210, 60), width=4)
    d.ellipse((sx - 12, sy - 12, sx + 12, sy + 12), fill=(255, 210, 60))
    d.text((cx - 20, y0 + 4), 'stick', font=font(FONT, 16), fill=(150, 150, 160))
    bx = 190
    for name in ('A', 'B', 'Z', 'R', 'START'):
        on = entry['b'] & BTN[name]
        w = 72 if name != 'START' else 108
        d.rounded_rectangle((bx, y0 + 22, bx + w, y0 + 80), 12, fill=COLORS[name] if on else (45, 45, 52),
                            outline=(255, 255, 255) if on else (80, 80, 90), width=2)
        tw = d.textlength(name, font=font(BOLD, 24))
        d.text((bx + (w - tw) / 2, y0 + 36), name, font=font(BOLD, 24),
               fill=(15, 15, 15) if on and name in ('Z', 'R') else (255, 255, 255))
        bx += w + 12
    d.text((190, y0 + 88), 'A jump · B fire · Z aim / lock-on · R strafe', font=font(FONT, 16), fill=(140, 140, 150))
    d.text((190, y0 + 112), entry['label'], font=font(BOLD, 24), fill=(255, 230, 120))
    return out


def card(lines, sizes, colors):
    im = Image.new('RGB', (OUT_W, OUT_H), (10, 10, 14))
    d = ImageDraw.Draw(im)
    total = sum(s * 1.6 for s in sizes)
    y = (OUT_H - total) / 2
    for text, size, color in zip(lines, sizes, colors):
        f = font(BOLD if size >= 40 else FONT, size)
        d.text(((OUT_W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=color)
        y += size * 1.6
    return im


def load_run(shots, log):
    files = sorted(Path(shots).glob('*.png'))
    entries = [e for e in json.loads(Path(log).read_text()) if e['shot']]
    n = min(len(files), len(entries))
    return files[:n], entries[:n]


def aligned_audio(wav_path, entries, n_frames):
    """Mono track where each video frame gets the audio the game produced during it.

    The emulator hands the game uneven amounts of audio time per frame, so the
    stream is retimed with windowed overlap-add grains: tempo follows the
    per-frame mapping while pitch stays at the game's DAC rate."""
    w = wave.open(str(wav_path))
    rate = w.getframerate()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(np.float32).mean(1)
    end = entries[n_frames].get('aud', len(a)) if len(entries) > n_frames else len(a)
    marks = np.array([e.get('aud', 0) for e in entries[:n_frames]] + [end], dtype=np.float64)
    marks = np.minimum(np.maximum.accumulate(marks), len(a))
    k = FPS // 2                                   # smooth the mapping over ~1 s
    if len(marks) > 2 * k:
        pad = np.concatenate([np.repeat(marks[:1], k), marks, np.repeat(marks[-1:], k)])
        marks = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode='valid')
    grain = 1024
    hop = grain // 2
    win = np.hanning(grain).astype(np.float32)
    n_out = int(n_frames * rate / FPS)
    out = np.zeros(n_out + grain, np.float32)
    padded = np.concatenate([np.zeros(grain, np.float32), a, np.zeros(grain, np.float32)])
    for pos in range(0, n_out, hop):
        frame = pos * FPS / rate
        src = int(np.interp(frame, np.arange(len(marks)), marks)) + grain - grain // 2
        out[pos:pos + grain] += padded[src:src + grain] * win
    return out[:n_out], rate


def main():
    o_shots, o_log, o_wav, p_shots, p_log, p_wav, out = sys.argv[1:8]
    out = Path(out)
    fr = out / 'frames'
    fr.mkdir(parents=True, exist_ok=True)
    of, oe = load_run(o_shots, o_log)
    pf, pe = load_run(p_shots, p_log)
    n = max(len(of), len(pf))
    intro, outro = 3 * FPS, 5 * FPS
    title = card([TITLE, SUBTITLE, '', 'Left: original controls        Right: patched'],
                 [54, 44, 20, 30], [(255, 232, 31), (255, 255, 255), (0, 0, 0), (170, 170, 180)])
    end = card(['What the patch does'] + FEATURES + ['', 'N64 emulators (Expansion Pak required) · built for M64Plus FZ'],
               [46] + [30] * len(FEATURES) + [20, 24],
               [(255, 232, 31)] + [(235, 235, 240)] * len(FEATURES) + [(0, 0, 0), (150, 150, 160)])
    idx = 0
    for _ in range(intro):
        title.save(fr / f'{idx:05d}.png'); idx += 1
    for i in range(n):
        a = pane(Image.open(of[min(i, len(of) - 1)]), oe[min(i, len(oe) - 1)], 'ORIGINAL', (90, 90, 100))
        b = pane(Image.open(pf[min(i, len(pf) - 1)]), pe[min(i, len(pe) - 1)], 'PATCH: new controls', (40, 120, 70))
        s = Image.new('RGB', (OUT_W, OUT_H), (10, 10, 14))
        d = ImageDraw.Draw(s)
        t = f'{TITLE}  ·  {SUBTITLE}'
        d.text(((OUT_W - d.textlength(t, font=font(BOLD, 30))) / 2, 22), t, font=font(BOLD, 30), fill=(255, 232, 31))
        y = 76
        s.paste(a, (0, y))
        s.paste(b, (GW + GAP, y))
        s.save(fr / f'{idx:05d}.png'); idx += 1
    for _ in range(outro):
        end.save(fr / f'{idx:05d}.png'); idx += 1

    left, rate = aligned_audio(o_wav, oe, len(of))
    right, _ = aligned_audio(p_wav, pe, len(pf))
    total = int(idx * rate / FPS)
    track = np.zeros((total, 2), np.float32)
    s0 = int(intro * rate / FPS)
    track[s0:s0 + len(left), 0] = left[:total - s0]
    track[s0:s0 + len(right), 1] = right[:total - s0]
    peak = np.abs(track).max() or 1
    track = (track / peak * 0.9 * 32767).astype('<i2')
    wav = out / 'audio.wav'
    w = wave.open(str(wav), 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(track.tobytes()); w.close()
    mp4 = out / 'SotE_controls_demo_1080p.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(fr / '%05d.png'),
                    '-i', str(wav), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', str(mp4)],
                   check=True)
    print(mp4, idx / FPS, 's')


if __name__ == '__main__':
    main()
