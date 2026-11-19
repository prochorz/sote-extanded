#!/usr/bin/env python3
"""Compose the saber Short (record_saber_short.py takes) into a vertical 1080x1920 30 fps MP4 with the game's audio.

    harness/.venv/bin/python3 tools/video/compose_short.py <out.mp4> [<cut> [<takes dir> <shots root>]]

<cut>: short (default, saber_short.mp4: the palace, fixed eyes) or short2 (saber_short_v2.mp4: the Echo Base hangar,
the orbit, record_saber_short.py with STATE=play.st ORBIT=70). Defaults: takes (the JSON logs and WAVs) in
local/run/video/<cut>/, shots in local/run/shots/vid_<cut>_<clip>/. Per clip (CUTS[cut], in order) a window of its game time t (from, to) and the caption shown big at the top in a dark band. The game
picture (RES 1440x1080) is cropped to a 9:16 column (608x1080) centred at the clip's x (Luke: the drop camera puts him
a little right of the picture's centre) and scaled to 1080x1920, filling the frame. Real speed: each clip is put on its
sound clock (the 'aud' marks: the game's own audio, 22047 Hz, runs with its game clock, while the harness VI tick does
not: 557..740 samples a shot against 735 at real time), so output frame j shows the last shot whose mark is <= the
clip's first mark + j / 30 s, and the clip's sound is the WAV's samples between its first and last marks, as dumped.
Hard cuts with 20 ms sound fades, the sound normalised to 0.9 peak; an end card (END s): "SotE Extended" and the mod's line. H.264 yuv420p CRF 19,
AAC 192k 48 kHz, +faststart; frames piped to ffmpeg raw (no PNGs). Prints each clip's length and the total.
"""
import json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
LOCAL = os.environ.get('SOTE_LOCAL', os.path.join(ROOT, 'local'))
BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
REG = '/System/Library/Fonts/Supplemental/Arial.ttf'
W, H, FPS = 1080, 1920, 30
COL = 608                                   # 9:16 of the game's 1080 rows
END = 2.5
# clip, caption, game time window (s), column centre x in the 1440 picture
CUTS = {}
CUTS['short'] = (('draw', 'Lightsaber', (0.3, 4.5), 760),
         ('cut', 'Cut', (0.2, 3.8), 750),
         ('combo', '3-hit combo', (0.2, 5.4), 750),
         ('spin', 'Spin jump', (0.2, 7.4), 760),
         ('deflect', 'Deflect', (0.0, 11.4), 760),
         ('run', 'Deflect on the run', (0.0, 4.1), 735),
         ('jump', 'Force jump', (0.3, 9.8), 720))
CUTS['short2'] = (('draw', 'Lightsaber', (0.3, 5.0), 720),     # the windows = record_saber_short.py's ORB arcs
                  ('cut', 'Cut', (0.2, 4.2), 720),
                  ('combo', '3-hit combo', (0.2, 5.6), 720),
                  ('spin', 'Spin jump', (0.2, 7.4), 720),
                  ('deflect', 'Deflect', (0.0, 12.0), 720),
                  ('run', 'Deflect on the run', (0.0, 3.85), 720),
                  ('jump', 'Force jump', (0.3, 9.8), 720))
CUTS['short3'] = CUTS['short2']    # saber_short_v3.mp4: v2 re-recorded with ORBR=1.3 (the camera farther)
CUTS['short4'] = CUTS['short2']    # saber_short_v4.mp4: v3's staging on a later build (the swings' wrists held natural)
CUTS['short5'] = CUTS['short2']    # saber_short_v5.mp4: v4's staging on a later build (sw3 a diagonal cut, the spin's hand lower)
CUTS['short7'] = (('draw', 'Lightsaber', (0.0, 5.0), 720),) + CUTS['short2'][1:]   # saber_short_v7.mp4: v6's staging
# on a later build (the turned bolt grows out of the blade), its first clip from the take's start (the hook's question
# ~1.4 s before the ignition) with the hook's captions (HOOK)
# the hook: per cut, the first clip's captions by its weapon id (the log's 'wid': 6 the saber lit): before the
# ignition the question, from it for HOOK_ANSWER s the answer, then the clip's own caption
HOOK = {'short7': ('A STAR WARS GAME\nWITHOUT LIGHTSABERS?', 'NOT ANYMORE.')}
HOOK['short8'] = HOOK['short7']
HOOK_ANSWER = 1.5
HOOK_HOLD = 1.0                    # s the hook's first frame is held before the clip runs (the question read in ~2.4 s)
CUTS['short8'] = CUTS['short7']    # saber_short_v8.mp4: v7 on a later build (no holster click on the ignition)
CUTS['short6'] = CUTS['short2']    # saber_short_v6.mp4: v5's staging on a later build (the spin one-handed, the round tip, the parry grid and its flash)


def font(path, size): return ImageFont.truetype(path, size)


def caption(im, text):
    """a dark band over the top with the caption (one line, or several: the hook), yellow with a black outline"""
    lines = text.split('\n')
    bh = 250 if len(lines) == 1 else 140 + 130 * len(lines)
    band = Image.new('RGBA', (W, bh), (0, 0, 0, 165))
    im.paste(band, (0, 0), band)
    d = ImageDraw.Draw(im); sz = 120
    while max(d.textlength(t, font=font(BOLD, sz)) for t in lines) > W - 80: sz -= 4
    f = font(BOLD, sz)
    for i, t in enumerate(lines):
        y = bh / 2 + (i - (len(lines) - 1) / 2) * sz * 1.15
        d.text(((W - d.textlength(t, font=f)) / 2, y), t, font=f, fill=(255, 232, 31), anchor='lm', stroke_width=6,
               stroke_fill=(0, 0, 0))
    return im


def end_card():
    im = Image.new('RGB', (W, H), (8, 8, 12)); d = ImageDraw.Draw(im)
    for text, f, y, c in (('SotE Extended', font(BOLD, 132), 860, (255, 232, 31)),
                          ('Star Wars: Shadows of the Empire', font(REG, 50), 1010, (235, 235, 240)),
                          ('N64 mod', font(REG, 50), 1080, (235, 235, 240))):
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=c)
    return im


def main():
    out = sys.argv[1]
    cut = sys.argv[2] if len(sys.argv) > 2 else 'short'
    takes = sys.argv[3] if len(sys.argv) > 3 else os.path.join(LOCAL, 'run', 'video', cut)
    shots = sys.argv[4] if len(sys.argv) > 4 else os.path.join(LOCAL, 'run', 'shots')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '19', '-preset', 'slow',
                           '-r', str(FPS), out + '.video.mp4'], stdin=subprocess.PIPE)
    sound, rate, total = [], None, 0
    for clip, text, (t0, t1), cx in CUTS[cut]:
        log = json.load(open(os.path.join(takes, clip + '.json')))
        d = os.path.join(shots, f'vid_{cut}_{clip}'); files = sorted(f for f in os.listdir(d) if f.endswith('.png'))
        ix = [i for i, ent in enumerate(log[:len(files)]) if t0 <= ent['t'] <= t1]
        w = wave.open(os.path.join(takes, clip + '.wav')); rate = rate or w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(np.float32)
        m0, m1 = log[ix[0]]['aud'], log[ix[-1]]['aud']
        seg = a[m0:m1].copy(); fade = rate // 50
        seg[:fade] *= np.linspace(0, 1, fade)[:, None]; seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
        n = int(round((m1 - m0) / rate * FPS))
        marks = np.array([log[i]['aud'] for i in ix])
        last, cache = None, None
        hook = HOOK.get(cut) if clip == CUTS[cut][0][0] else None
        lit = next((log[i]['t'] for i in ix if log[i].get('wid') == 6), None) if hook else None
        def text_at(i):
            if not hook or lit is None: return text
            t = log[i]['t']
            return hook[0] if t < lit else hook[1] if t < lit + HOOK_ANSWER else text
        for j in range(n):
            s = m0 + j * rate / FPS
            i = ix[max(0, int(np.searchsorted(marks, s, side='right')) - 1)]
            if j == 0 and hook:     # the question held on the clip's first frame, silent
                g = Image.open(os.path.join(d, files[i])).convert('RGB'); gw, gh = g.size
                x0 = min(max(0, cx - COL // 2), gw - COL)
                still = caption(g.crop((x0, 0, x0 + COL, gh)).resize((W, H), Image.Resampling.LANCZOS), hook[0]).tobytes()
                for _ in range(int(HOOK_HOLD * FPS)): ff.stdin.write(still)
                sound.append(np.zeros((int(round(int(HOOK_HOLD * FPS) * rate / FPS)), 2), np.float32)); total += int(HOOK_HOLD * FPS)
            if i != last:
                g = Image.open(os.path.join(d, files[i])).convert('RGB'); gw, gh = g.size
                x0 = min(max(0, cx - COL // 2), gw - COL)
                cache = caption(g.crop((x0, 0, x0 + COL, gh)).resize((W, H), Image.Resampling.LANCZOS), text_at(i)).tobytes()
                last = i
            ff.stdin.write(cache)
        sound.append(seg[:int(round(n * rate / FPS))]); total += n
        print(f'{clip:8s} {text!r:22s} shots {len(ix)} -> {n} frames, {n / FPS:.2f} s', flush=True)
    card = end_card().tobytes()
    for _ in range(int(END * FPS)): ff.stdin.write(card)
    total += int(END * FPS)
    sound.append(np.zeros((int(END * rate), 2), np.float32))
    ff.stdin.close(); ff.wait()
    track = np.concatenate(sound)
    peak = np.abs(track).max() or 1
    track = (track * (0.9 * 32767 / peak)).astype('<i2')
    wav = out + '.audio.wav'
    w = wave.open(wav, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate); w.writeframes(track.tobytes()); w.close()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', out + '.video.mp4', '-i', wav, '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', out],
                   check=True)
    os.remove(out + '.video.mp4'); os.remove(wav)
    print(out, f'{total / FPS:.2f} s', flush=True)


if __name__ == '__main__':
    main()
