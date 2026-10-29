#!/usr/bin/env python3
"""Build the ~5 minute YouTube video: title, side-by-side comparison, then
patched gameplay on several levels with an input panel, and an end card.

    make_long_video.py <compare spec json> <levels spec json> <out dir>

compare spec: {"orig": [shots, log, wav], "patch": [shots, log, wav]}
levels spec:  [{"name": ..., "shots": ..., "log": ..., "wav": ...}, ...]
"""
import json, subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from make_demo_video import (BTN, COLORS, FEATURES, FPS, OUT_H, OUT_W, SUBTITLE, TITLE, BOLD, FONT,
                             GAP, GW, aligned_audio, card, font, load_run, pane)

GAME_W, GAME_H = 1280, 960
KEEP_MAX = {'Exploring': 5.0, 'Hunting the next enemy': 12.0, 'Z: lock on': 1.0, 'Turn toward enemy': 2.0}
DROP = {'', 'Skip message'}


def trim(files, entries, max_seconds):
    """Indices of frames worth watching: fights kept, wandering shortened."""
    keep, i = [], 0
    while i < len(entries):
        j = i
        while j < len(entries) and entries[j]['label'] == entries[i]['label']:
            j += 1
        lab = entries[i]['label']
        if lab not in DROP:
            limit = int(KEEP_MAX.get(lab, 1e9) * FPS)
            keep.extend(range(i, min(j, i + limit)))
        i = j
    return keep[:int(max_seconds * FPS)]


def gameplay_frame(img, entry, level):
    s = Image.new('RGB', (OUT_W, OUT_H), (10, 10, 14))
    s.paste(img.convert('RGB').resize((GAME_W, GAME_H), Image.Resampling.LANCZOS), (40, 60))
    d = ImageDraw.Draw(s)
    d.text((40, 14), f'{TITLE}  ·  {SUBTITLE}', font=font(BOLD, 28), fill=(255, 232, 31))
    x0 = 1360
    d.text((x0, 70), 'LEVEL', font=font(FONT, 20), fill=(150, 150, 160))
    y = 98
    for line in level.split('\n'):
        d.text((x0, y), line, font=font(BOLD, 34), fill=(255, 255, 255)); y += 44
    d.rounded_rectangle((x0 - 10, 250, 1890, 330), 12, fill=(40, 120, 70))
    d.text((x0 + 6, 270), 'PATCH: new controls', font=font(BOLD, 28), fill=(255, 255, 255))
    cx, cy, r = x0 + 120, 500, 110
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(120, 120, 130), width=4)
    d.line((cx - r, cy, cx + r, cy), fill=(60, 60, 70), width=2)
    d.line((cx, cy - r, cx, cy + r), fill=(60, 60, 70), width=2)
    sx, sy = cx + entry['x'] / 80 * (r - 18), cy - entry['y'] / 80 * (r - 18)
    d.line((cx, cy, sx, sy), fill=(255, 210, 60), width=6)
    d.ellipse((sx - 20, sy - 20, sx + 20, sy + 20), fill=(255, 210, 60))
    d.text((cx - 26, cy + r + 10), 'stick', font=font(FONT, 20), fill=(150, 150, 160))
    by = 690
    bx = x0
    for name in ('A', 'B', 'Z', 'R', 'START'):
        on = entry['b'] & BTN[name]
        w = 84 if name != 'START' else 160
        if name == 'START':
            bx, by = x0, by + 96
        d.rounded_rectangle((bx, by, bx + w, by + 80), 14, fill=COLORS[name] if on else (45, 45, 52),
                            outline=(255, 255, 255) if on else (80, 80, 90), width=3)
        tw = d.textlength(name, font=font(BOLD, 30))
        d.text((bx + (w - tw) / 2, by + 22), name, font=font(BOLD, 30),
               fill=(15, 15, 15) if on and name in ('Z', 'R') else (255, 255, 255))
        bx += w + 14
    d.text((x0, 880), 'A jump · B fire · Z lock-on · R strafe', font=font(FONT, 20), fill=(140, 140, 150))
    d.text((x0, 940), entry['label'], font=font(BOLD, 28), fill=(255, 230, 120))
    return s


def main():
    comp = json.loads(Path(sys.argv[1]).read_text())
    levels = json.loads(Path(sys.argv[2]).read_text())
    out = Path(sys.argv[3])
    fr = out / 'frames'
    fr.mkdir(parents=True, exist_ok=True)
    idx = 0
    audio = []                                   # list of (start_frame, left, right)

    def put(im, count=1):
        nonlocal idx
        for _ in range(count):
            im.save(fr / f'{idx:05d}.png'); idx += 1

    put(card([TITLE, SUBTITLE, '', 'Camera-relative movement, lazy camera and Z-targeting for Dash Rendar'],
             [58, 46, 20, 28], [(255, 232, 31), (255, 255, 255), (0, 0, 0), (170, 170, 180)]), 4 * FPS)
    put(card(['Original vs patched', 'Same route on Escape from Echo Base', '', 'Left: original    Right: patched'],
             [50, 30, 20, 30], [(255, 232, 31), (235, 235, 240), (0, 0, 0), (170, 170, 180)]), 2 * FPS)
    of, oe = load_run(*comp['orig'][:2])
    pf, pe = load_run(*comp['patch'][:2])
    start = idx
    for i in range(max(len(of), len(pf))):
        a = pane(Image.open(of[min(i, len(of) - 1)]), oe[min(i, len(oe) - 1)], 'ORIGINAL', (90, 90, 100))
        b = pane(Image.open(pf[min(i, len(pf) - 1)]), pe[min(i, len(pe) - 1)], 'PATCH: new controls', (40, 120, 70))
        s = Image.new('RGB', (OUT_W, OUT_H), (10, 10, 14))
        d = ImageDraw.Draw(s)
        t = f'{TITLE}  ·  {SUBTITLE}'
        d.text(((OUT_W - d.textlength(t, font=font(BOLD, 30))) / 2, 22), t, font=font(BOLD, 30), fill=(255, 232, 31))
        s.paste(a, (0, 76)); s.paste(b, (GW + GAP, 76))
        put(s)
    left, rate = aligned_audio(comp['orig'][2], oe, len(of))
    right, _ = aligned_audio(comp['patch'][2], pe, len(pf))
    audio.append((start, left, right))

    put(card(['Gameplay with the patch', '', '4 on-foot levels'], [56, 20, 32],
             [(255, 232, 31), (0, 0, 0), (200, 200, 210)]), 2 * FPS)
    for lv in levels:
        put(card([lv['name'].replace('\n', ' ')], [60], [(255, 255, 255)]), 2 * FPS)
        files, entries = load_run(lv['shots'], lv['log'])
        keep = trim(files, entries, lv.get('max_seconds', 55))
        start = idx
        for i in keep:
            put(gameplay_frame(Image.open(files[i]), entries[i], lv['name']))
        # Audio per contiguous run of kept frames, so cuts don't smear the mapping.
        runs, cur = [], [keep[0]] if keep else []
        for a, b in zip(keep, keep[1:]):
            if b == a + 1: cur.append(b)
            else: runs.append(cur); cur = [b]
        if cur: runs.append(cur)
        pos = start
        for run in runs:
            seg = [entries[i] for i in run] + [entries[min(run[-1] + 1, len(entries) - 1)]]
            mono, _ = aligned_audio(lv['wav'], seg, len(run))
            audio.append((pos, mono, mono))
            pos += len(run)

    put(card(['What the patch does'] + FEATURES + ['', 'N64 emulators (Expansion Pak required) · built for M64Plus FZ'],
             [46] + [30] * len(FEATURES) + [20, 24],
             [(255, 232, 31)] + [(235, 235, 240)] * len(FEATURES) + [(0, 0, 0), (150, 150, 160)]), 6 * FPS)

    total = int(idx * rate / FPS)
    track = np.zeros((total, 2), np.float32)
    for start, l, r in audio:
        s0 = int(start * rate / FPS)
        nl, nr = min(len(l), total - s0), min(len(r), total - s0)
        track[s0:s0 + nl, 0] = l[:nl]
        track[s0:s0 + nr, 1] = r[:nr]
    # Normalise each section's loudness a little so levels don't jump around.
    peak = np.percentile(np.abs(track), 99.9) or 1
    track = np.clip(track / peak * 0.8, -1, 1)
    wav = out / 'audio.wav'
    w = wave.open(str(wav), 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes((track * 32767).astype('<i2').tobytes()); w.close()
    mp4 = out / 'SotE_controls_5min_1080p.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(fr / '%05d.png'),
                    '-i', str(wav), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'medium',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', str(mp4)],
                   check=True)
    print(mp4, round(idx / FPS, 1), 's')


if __name__ == '__main__':
    main()
