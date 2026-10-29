#!/usr/bin/env python3
"""Compose recorded takes into one captioned 1280x720 video (game left, panel right).

    compose_takes.py <out.mp4> <title> <subtitle> <take dir>:<take json>:<take title> [...]

Panel: take title, stick widget, A/B/Z lit while in entry['b'] (plus L/R/START/D-pad, letters
L R S U D, in takes that use them), a green badge while entry['hang']
(HANGING) or entry['lock'] (LOCKED ON) is set, caption = entry['label']. Title card 2.5 s, a card
per take, end card. All on-screen text in English. If <take json> has a .wav next to it (and the
entries carry 'aud'), the take's game audio is retimed to its frames; cards are silent.
"""
import json, glob, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_demo_video import aligned_audio

BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
REG = '/System/Library/Fonts/Supplemental/Arial.ttf'
W, H = 1280, 720
# Second button row, drawn only in takes that press them ('b' letters: L, R, S = START, U/D = D-pad).
EXTRA = (('L', 'L'), ('R', 'R'), ('S', 'START'), ('U', 'D-up'), ('D', 'D-dn'))


def main():
    out_mp4, title, subtitle = sys.argv[1:4]
    takes = [a.split(':', 2) for a in sys.argv[4:]]
    tmp = tempfile.mkdtemp(prefix='compose_')
    idx = [0]
    audio = []                                     # (start frame, mono samples, rate)

    def save(im, n=1):
        for _ in range(n):
            im.save(f'{tmp}/{idx[0]:05d}.png'); idx[0] += 1

    def card(lines):
        im = Image.new('RGB', (W, H), (10, 10, 14)); d = ImageDraw.Draw(im); y = H // 2 - len(lines) * 35
        for t, sz, c in lines:
            f = ImageFont.truetype(BOLD if sz >= 40 else REG, sz)
            d.text(((W - d.textlength(t, font=f)) / 2, y), t, font=f, fill=c); y += int(sz * 1.6)
        return im

    save(card([(title, 44, (255, 232, 31)), (subtitle, 34, (255, 255, 255))]), 75)
    for shots, logf, ttl in takes:
        save(card([(ttl, 52, (255, 232, 31))]), 36)
        log = json.load(open(logf)); files = sorted(glob.glob(f'{shots}/*.png'))
        extra = any(c in ent.get('b', '') for ent in log for c, _ in EXTRA)
        n = min(len(log), len(files)); wavf = logf[:-5] + '.wav'
        if os.path.exists(wavf):
            a, rate = aligned_audio(wavf, log, n); audio.append((idx[0], a, rate))
        im = None
        for ent, fn in zip(log, files):
            g = Image.open(fn).convert('RGB').resize((960, 720), Image.Resampling.LANCZOS)
            im = Image.new('RGB', (W, H), (14, 14, 18)); im.paste(g, (0, 0)); d = ImageDraw.Draw(im)
            x0 = 980; sz = 26
            while d.textlength(ttl, font=ImageFont.truetype(BOLD, sz)) > 285: sz -= 1
            d.text((x0, 30), ttl, font=ImageFont.truetype(BOLD, sz), fill=(255, 232, 31))
            cx, cy, r = 1130, 250, 90
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(120, 120, 130), width=4)
            d.line((cx - r, cy, cx + r, cy), fill=(60, 60, 70), width=2); d.line((cx, cy - r, cx, cy + r), fill=(60, 60, 70), width=2)
            sx, sy = cx + ent['x'] / 80 * (r - 16), cy - ent['y'] / 80 * (r - 16)
            d.line((cx, cy, sx, sy), fill=(255, 210, 60), width=6); d.ellipse((sx - 16, sy - 16, sx + 16, sy + 16), fill=(255, 210, 60))
            d.text((cx - 24, cy + r + 8), 'stick', font=ImageFont.truetype(REG, 20), fill=(150, 150, 160))
            for i, bn in enumerate(('A', 'B', 'Z')):       # buttons: lit while pressed
                bx, by = 1060 + i * 70, 400; on = bn in ent.get('b', '')
                col = {'A': (60, 110, 230), 'B': (40, 160, 70), 'Z': (150, 150, 160)}[bn] if on else (45, 45, 55)
                d.ellipse((bx - 24, by - 24, bx + 24, by + 24), fill=col, outline=(120, 120, 130), width=2)
                fb = ImageFont.truetype(BOLD, 24); d.text((bx - d.textlength(bn, font=fb) / 2, by - 14), bn, font=fb, fill=(255, 255, 255) if on else (130, 130, 140))
            if extra:                                     # menu takes: L, R, START, D-pad up/down
                for i, (bn, lab) in enumerate(EXTRA):
                    bx, by = 1010 + i * 58, 470; on = bn in ent.get('b', '')
                    d.rounded_rectangle((bx - 25, by - 18, bx + 25, by + 18), 8, fill=(170, 120, 40) if on else (45, 45, 55),
                                        outline=(120, 120, 130), width=2)
                    fb = ImageFont.truetype(BOLD, 15); d.text((bx - d.textlength(lab, font=fb) / 2, by - 9), lab, font=fb,
                                                             fill=(255, 255, 255) if on else (130, 130, 140))
            badge = 'HANGING' if ent.get('hang') else 'LOCKED ON' if ent.get('lock') else ''
            if badge:
                d.rounded_rectangle((x0, 440, 1260, 490), 10, fill=(40, 120, 70) if ent.get('hang') else (150, 40, 40))
                d.text((x0 + 14, 450), badge, font=ImageFont.truetype(BOLD, 26), fill=(255, 255, 255))
            f = ImageFont.truetype(BOLD, 28); words = ent.get('label', '').split(); lines, cur = [], ''
            for w_ in words:
                if d.textlength((cur + ' ' + w_).strip(), font=f) > 270: lines.append(cur); cur = w_
                else: cur = (cur + ' ' + w_).strip()
            if cur: lines.append(cur)
            for i, l in enumerate(lines): d.text((x0, 520 + i * 38), l, font=f, fill=(255, 230, 120))
            save(im)
        if im: save(im, 20)
    save(card([(title, 46, (255, 232, 31)), (subtitle, 26, (235, 235, 240))]), 120)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', f'{tmp}/%05d.png']
    if audio:
        rate = audio[0][2]; track = np.zeros(int(idx[0] * rate / 30) + rate, np.float32)
        for f0, a, _ in audio:
            s0 = int(f0 * rate / 30); a = a[:len(track) - s0]
            fade = min(len(a), rate // 20); a[:fade] *= np.linspace(0, 1, fade); a[len(a) - fade:] *= np.linspace(1, 0, fade)
            track[s0:s0 + len(a)] += a
        track = (track / (np.abs(track).max() or 1) * 0.9 * 32767).astype('<i2')
        w = wave.open(f'{tmp}/audio.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(track.tobytes()); w.close()
        cmd += ['-i', f'{tmp}/audio.wav', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest']
    subprocess.run(cmd + ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow',
                          '-movflags', '+faststart', out_mp4], check=True)
    print(out_mp4, idx[0] / 30, 's')


if __name__ == '__main__':
    main()
