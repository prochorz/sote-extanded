#!/usr/bin/env python3
"""Compose the YouTube showcase (1920x1080, 30 fps) from the recorded take manifests B and C.

    harness/.venv/bin/python3 tools/video/compose_showcase.py [--analyze] [--jobs N] [--only SECTION,...]

Inputs: local/run/video/manifest_B.json (boss lock-on, original vs patch side by side, cheats, the
Gall-on-foot finale) and manifest_C.json (the Gall Run story and its highlights).
Order: title card, Controls (side by side), Z lock-on (ordinary enemies: manifest_B 1.x if there, the gladiator, the AT-ST, IG-88 whose death runs
without a card into the Gall Run story from Cut 05 to Cut 06), Cheats, ledge hang on Gall, Catching the edge
(normal, then the catch again at half speed), Gall Run highlights, end card. Single takes: game 1440x1080 on the left, a 480 px side panel
(section, take title, caption, stick and buttons, LOCKED ON / HANGING badge, the log's live label).
Side by side: make_demo_video.pane() for each side, take title and caption above, stereo audio
(left = original, right = patch).

Editing:
- boss takes: lock-0 stretches longer than 0.5 s are dropped (not the first second of a sub-take, not
  the boss's death); cut=1 log entries, sub-take changes and drops get a 6-frame cross-fade on the
  picture and a short audio fade.
- dead time: black runs and static runs are capped (longer caps for the story's dialog pictures).
- C frames (1440x1080) carry an 88 px black band at the top: the picture is cropped to rows 84..1070
  and centred.
- timing: a run whose sound has < 0.9 of a real VI's samples (22047/60) per logged tick (Cut 05, the mission,
  the end scenes, the cheats menus) is laid on its AUDIO timeline (a shot shown from its entry's 'aud' on, smoothed over
  ~0.5 s; 30 fps out by dropping or repeating shots) and its sound plays unstretched: the harness's VI tick is not
  real time (Cut 05 gave 93 samples a tick at 22047 Hz, a real VI is ~367). In the chain parts (Cut 05, the
  hyperspace scene, Cut 06) a still picture shorter than 3 s is held to 3 s, silence padded in the sound.
  Runs at or above it (the bosses, Gall on foot: ~525 a tick) stay on the tick timeline, the sound stretched to the
  frames (run_audio), as do the edge catch's slow replay (nrep 2) and the side-by-side takes.
Audio: each contiguous run's sound cut from its dump at the run's 'aud' marks, then assembled.
Rendering: chunks of the timeline rendered in parallel (raw RGB piped to ffmpeg), concatenated,
muxed with the audio. Output demo/sote_showcase_youtube.mp4 (CRF 18), a 1280x720 CRF 28 phone copy and an
854x480 preview under 28 MB (sote_showcase_preview.mp4).
"""
import argparse, glob, json, os, subprocess, sys, tempfile, wave
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_demo_video import aligned_audio, pane, GW, BTN, FPS

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
VID = os.path.join(ROOT, 'local', 'run', 'video')
OUT = os.path.join(ROOT, 'local', 'demo', 'sote_showcase_youtube.mp4')
PHONE = os.path.join(ROOT, 'local', 'demo', 'sote_showcase_phone.mp4')
PREVIEW = os.path.join(ROOT, 'local', 'demo', 'sote_showcase_preview.mp4')
BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
REG = '/System/Library/Fonts/Supplemental/Arial.ttf'
W, H = 1920, 1080
GAME_W = 1440
PX = GAME_W + 30                                   # panel text x
PW = W - PX - 26                                   # panel text width
BG = (12, 12, 16)
YEL, WHITE, GREY, LAB = (255, 232, 31), (240, 240, 245), (150, 150, 160), (255, 225, 130)
TITLE = 'SotE Extended'
SUBTITLE = ('Star Wars: Shadows of the Empire (N64) —',
            'new controls, Z lock-on, ledge hang, cheats and the Gall Run bonus mission')
XFADE = 6                                          # frames of picture cross-fade at a cut
EXTRA = (('L', 'L'), ('R', 'R'), ('c', 'C'), ('S', 'START'), ('U', 'D-up'), ('D', 'D-dn'))
_F = {}


def font(path, size):
    k = (path, size)
    if k not in _F: _F[k] = ImageFont.truetype(path, size)
    return _F[k]


def wrap(d, text, f, width):
    lines, cur = [], ''
    for w_ in text.split():
        t = (cur + ' ' + w_).strip()
        if d.textlength(t, font=f) > width and cur: lines.append(cur); cur = w_
        else: cur = t
    if cur: lines.append(cur)
    return lines


def rp(p):                                          # manifest paths: absolute or repo-relative
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(ROOT, p))


# ---------------------------------------------------------------- frame analysis (cached)

def _thumb(path):
    im = Image.open(path).convert('RGB').resize((64, 48), Image.Resampling.BILINEAR)
    a = np.asarray(im, np.float32)
    return a.mean(2), a.reshape(-1, 3).mean(0)


def thumbs(paths, cache={}):
    cf = os.path.join(VID, 'showcase_thumbs.npz')
    if not cache and os.path.exists(cf):
        z = np.load(cf, allow_pickle=True); cache.update(z['d'].item())
    todo = [p for p in paths if p not in cache]
    if todo:
        with Pool(8) as pool:
            for p, r in zip(todo, pool.map(_thumb, todo, chunksize=32)): cache[p] = r
        np.savez(cf, d=np.array(cache, dtype=object))
    return [cache[p] for p in paths]


def cap_runs(paths, black_keep, static_keep, static_eps=0.6):
    """Indices kept after capping black runs (mean < 2.5) and static runs (thumbnail max diff < eps)."""
    th = thumbs(paths)
    keep, i, n = [], 0, len(paths)
    while i < n:
        g = th[i][0]
        if g.mean() < 2.5:
            j = i
            while j < n and th[j][0].mean() < 2.5: j += 1
            keep += list(range(i, min(j, i + black_keep))); i = j; continue
        j = i + 1
        while j < n and np.abs(th[j][0] - th[j - 1][0]).max() < static_eps and th[j][0].mean() >= 2.5: j += 1
        keep += list(range(i, min(j, i + max(1, static_keep)))); i = j
    return keep


def orange(paths):
    """Per-frame hit-flash tint (mean R - mean B)."""
    return np.array([t[1][0] - t[1][2] for t in thumbs(paths)])


# ---------------------------------------------------------------- timeline

class TL:
    def __init__(self):
        self.frames, self.audio, self.metas, self.marks = [], [], [], []

    def meta(self, **m):
        self.metas.append(m); return len(self.metas) - 1

    def mark(self, name):
        self.marks.append((name, len(self.frames)))

    def card(self, lines, seconds, fade=8):
        cid = self.meta(card=lines); n = int(seconds * FPS)
        for i in range(n):
            self.frames.append(('card', cid, min(1.0, (i + 1) / fade, (n - i) / fade)))

    def add_audio(self, start, l, r=None):
        self.audio.append((start, l, l if r is None else r))


def run_audio(wavf, ents, i0, i1, nrep=1):
    """Audio for log entries [i0, i1) (end mark: entry i1 if logged), each frame shown nrep times."""
    seg = []
    for k in range(i0, i1):
        a = ents[k]; seg.append(a)
        nxt = ents[k + 1]['aud'] if k + 1 < len(ents) else a['aud']
        for q in range(1, nrep): seg.append({'aud': a['aud'] + (nxt - a['aud']) * q / nrep})
    if i1 < len(ents): seg.append(ents[i1])
    return aligned_audio(wavf, seg, (i1 - i0) * nrep)[0]


def runs_of(idx, breaks=()):
    """Split sorted indices into contiguous runs; also break before any index in `breaks`."""
    out = []
    for i in idx:
        if out and i == out[-1][-1] + 1 and i not in breaks: out[-1].append(i)
        else: out.append([i])
    return out


SLOW_TICK = 0.9                                    # sound clock only where a tick carries < 0.9 of a real VI's sound
HOLD_S, HOLD_MIN_S = 3.0, 0.25                     # a still picture (a line of text) held to 3 s if it is shorter


def read_wav(path, cache={}):
    """(mono float32 samples, rate) of a take's sound dump."""
    if path not in cache:
        w = wave.open(path)
        cache[path] = (np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(np.float32).mean(1),
                       w.getframerate())
    return cache[path]


def shot_times(ents, r, rate):
    """Sample positions of the run's entries plus its end, on the audio timeline: each entry's 'aud' (the samples the
    game had produced by then), made monotone and smoothed over ~0.5 s so the dump's uneven chunks do not jerk."""
    aud = np.array([ents[i].get('aud', 0) for i in r], np.float64)
    nx = r[-1] + 1
    sp = (aud[-1] - aud[0]) / max(1, len(aud) - 1)
    end = ents[nx]['aud'] if nx < len(ents) and ents[nx].get('aud', 0) > aud[-1] else aud[-1] + sp
    if sp <= 0: sp = (end - aud[0]) / len(aud)
    T = np.maximum.accumulate(np.append(aud, end))
    k = int(0.25 * rate / sp) if sp > 0 else 0       # half window: 0.25 s
    if k >= 1 and len(T) > 2:
        pad = np.concatenate([T[0] - sp * np.arange(k, 0, -1), T, T[-1] + sp * np.arange(1, k + 1)])
        T = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode='valid')
        T = np.maximum.accumulate(T)
    return T


def still_runs(files, r, T, rate, eps=1.5):
    """(p0, p1) position ranges in the run of a still, non-black picture shorter than HOLD_S on the audio timeline."""
    th = thumbs([files[i] for i in r]); out = []; p = 0
    while p < len(r):
        q = p
        while q + 1 < len(r) and np.abs(th[q + 1][0] - th[q][0]).max() < eps: q += 1
        dur = (T[q + 1] - T[p]) / rate
        if q > p and q < len(r) - 1 and th[p][0].mean() >= 10 and HOLD_MIN_S <= dur < HOLD_S:
            out.append((p, q))                         # (not a still cut by the run's end)
        p = q + 1
    return out


def tick_clock_slow(ents, r, rate):
    """True when the run's sound clock is faster than its tick timeline (fewer than SLOW_TICK of a real VI's samples
    per logged tick: the take would play slow on the ticks). Only those runs go on the sound clock; a run whose
    sound runs slower than its ticks (the bosses, Gall on foot: ~525 a tick) stays on the ticks as before."""
    key = 't' if 't' in ents[r[0]] else 'k'
    a, b = r[0], min(r[-1] + 1, len(ents) - 1)
    if b <= a or ents[b][key] <= ents[a][key]: return False
    per_tick = (ents[b].get('aud', 0) - ents[a].get('aud', 0)) / (ents[b][key] - ents[a][key])
    return per_tick < SLOW_TICK * rate / 60


def add_take(tl, mid, files, ents, wavs, keep, breaks=(), nrep=1, crop=False, wav_of=None, hold=False):
    """Put the kept entries on the timeline, run by run (a cross-fade at each new run). Frames are laid on the
    AUDIO timeline: a shot is shown from its entry's 'aud' on (30 fps out: shots dropped or repeated) and the run's
    sound plays unstretched, so the take runs at the game's real speed whatever the harness's VI pacing was.
    nrep > 1 (a slow replay): each shot nrep times, the sound time-stretched to it (run_audio).
    hold: still pictures shorter than HOLD_S held to it (silence padded in the sound, sync kept after them)."""
    runs = runs_of(keep, breaks)
    prev = None
    for r in runs:
        w = wav_of(r[0]) if wav_of else wavs
        seq, auds = [], []                             # output frames: entry index; sound pieces: (frame, samples)
        if w and nrep == 1 and not tick_clock_slow(ents, r, read_wav(w)[1]): nrep_tick = True
        else: nrep_tick = False
        if nrep > 1 or not w or nrep_tick:
            seq = [i for i in r for _ in range(nrep)]
            if w and len(r) > 1: auds.append((0, run_audio(w, ents, r[0], r[-1] + 1, nrep)))
        else:
            a, rate = read_wav(w)
            T = shot_times(ents, r, rate)
            holds = {q: p for p, q in still_runs(files, r, T, rate)} if hold else {}
            step = rate / FPS; t = T[0]; s0 = t; p = 0
            while t < T[-1]:
                while p + 1 < len(r) and T[p + 1] <= t: p += 1
                seq.append(r[p]); t += step
                if p in holds and T[p + 1] <= t:       # the still's last frame: hold it up to HOLD_S
                    extra = int(round((HOLD_S * rate - (T[p + 1] - T[holds[p]])) / step))
                    auds.append((None, (s0, t))); auds.append(('gap', extra))
                    seq += [r[p]] * extra; s0 = t
                    if os.environ.get('TDBG'): print('HOLD', os.path.basename(files[r[p]]), 'was %.2f s' % ((T[p + 1] - T[holds[p]]) / rate), '+', extra, flush=True)
                    del holds[p]
            auds.append((None, (s0, t)))
            # sound pieces on output frames
            fr, pieces = 0, []
            for kind, v in auds:
                if kind == 'gap': fr += v; continue
                a0, a1 = int(v[0]), int(v[1]); n = int(round((a1 - a0) / step))
                if n > 0:                              # (smoothing can put a run's start a little before 0)
                    x = a[max(0, a0):max(0, a0 + int(n * step))]
                    pieces.append((fr, np.concatenate([np.zeros(max(0, -a0), np.float32), x]))); fr += n
            auds = pieces
        start = len(tl.frames)
        for q, i in enumerate(seq):
            e = ents[i]
            small = {k: e.get(k) for k in ('x', 'y', 'b', 'label', 'lock', 'hang') if k in e}
            bl = (prev, 1 - (q + 1) / (XFADE + 1)) if prev and q < XFADE else None
            tl.frames.append(('single', files[i], mid, small, bl, crop))
        if os.environ.get('TDBG'): print('RUN', os.path.basename(os.path.dirname(files[r[0]])), r[0], len(r) * nrep, len(seq), flush=True)
        prev = files[r[-1]]
        for f0, x in auds:
            if len(x): tl.add_audio(start + f0, x)


# ---------------------------------------------------------------- B takes

def b_files(entry):
    """Shot files and log entries of a single B take, entries matched to files per 'dir'."""
    ents = json.load(open(entry['log']))
    dirs = [os.path.basename(s) for s in entry['shots']]
    byd = {d: sorted(glob.glob(os.path.join(s, '*.png'))) for d, s in zip(dirs, entry['shots'])}
    cnt = {d: 0 for d in dirs}; files, ok = [], []
    for e in ents:
        d = e.get('dir', dirs[0]); k = cnt[d]; cnt[d] += 1
        if k < len(byd[d]): files.append(byd[d][k]); ok.append(e)
    ents = ok
    wav_by_dir = dict(zip(dirs, entry['wav']))
    return files, ents, dirs, wav_by_dir


def boss_keep(ents, dirs):
    """Drop lock-0 stretches > 0.5 s, except a sub-take's first second and the take's end (death)."""
    keep, breaks = [], set()
    n = len(ents); i = 0
    first = {}
    for k, e in enumerate(ents): first.setdefault(e['dir'], k)
    while i < n:
        j = i
        while j < n and ents[j]['lock'] == ents[i]['lock'] and ents[j]['dir'] == ents[i]['dir'] and (j == i or not ents[j].get('cut')): j += 1
        idx = list(range(i, j))
        if ents[i]['lock'] == 0 and j - i > 15:
            d0 = first[ents[i]['dir']]
            idx = [k for k in idx if k - d0 < 30]       # the first second before Z stays
            if j == n: idx = list(range(i, min(j, i + 12)))   # a short tail (e.g. 'Z released')
        keep += idx; i = j
    for k in range(1, n):
        if ents[k].get('cut') or ents[k]['dir'] != ents[k - 1]['dir']: breaks.add(k)
    return keep, breaks


def single_b(tl, entry, section, keep_fn=None):
    files, ents, dirs, wav_by_dir = b_files(entry)
    extra = [c for c, _ in EXTRA if any(c in e.get('b', '') for e in ents)]
    mid = tl.meta(section=section, title=entry['title'], caption=entry['caption'], extra=extra, inputs=True)
    if keep_fn: keep, breaks = keep_fn(files, ents, dirs)
    else:
        keep, breaks = list(range(len(ents))), {k for k in range(1, len(ents)) if ents[k].get('cut') or ents[k]['dir'] != ents[k - 1]['dir']}
    # dead time: black runs and long static stretches (menus while the stick rests)
    capped = set(cap_runs(files, black_keep=6, static_keep=int(2.0 * FPS)))
    jumped = {k for a, b in zip(keep, keep[1:]) if b != a + 1 for k in [b]}
    keep = [k for k in keep if k in capped]
    breaks = set(breaks) | jumped | {b for a, b in zip(keep, keep[1:]) if b != a + 1}
    add_take(tl, mid, files, ents, None, keep, breaks, wav_of=lambda i: wav_by_dir[ents[i]['dir']])
    return len(keep)


def sbs_b(tl, entry, section):
    sides = []
    for s, lg in zip(entry['shots'], entry['log']):
        f = sorted(glob.glob(os.path.join(s, '*.png'))); e = json.load(open(lg)); n = min(len(f), len(e))
        sides.append((f[:n], e[:n]))
    n = max(len(sides[0][0]), len(sides[1][0]))
    mid = tl.meta(section=section, title=entry['title'], caption=entry['caption'], sbs=True)
    start = len(tl.frames)
    for i in range(n):
        (fl, el), (fr, er) = sides
        a, b = min(i, len(fl) - 1), min(i, len(fr) - 1)
        tl.frames.append(('sbs', fl[a], el[a], fr[b], er[b], mid))
    l = aligned_audio(entry['wav'][0], sides[0][1], len(sides[0][0]))[0]
    r = aligned_audio(entry['wav'][1], sides[1][1], len(sides[1][0]))[0]
    tl.add_audio(start, l, r)
    return n


# ---------------------------------------------------------------- C parts

def c_part(log, shots, rng):
    ents = json.load(open(rp(log))); files = sorted(glob.glob(os.path.join(rp(shots), '*.png')))
    n = min(len(ents), len(files)); ents, files = ents[:n], files[:n]
    key = 't' if 't' in ents[0] else 'k'
    lo, hi = rng if rng else (None, None)
    idx = [i for i, e in enumerate(ents) if (lo is None or e[key] >= lo) and (hi is None or e[key] <= hi)]
    return files, ents, idx, key


def story(tl, part, chain, highlight=None):
    mid = tl.meta(section='Gall Run — a new bonus mission' if not highlight else 'Gall Run highlights',
                  title=part['title'] if not highlight else highlight, caption=part['caption'] if not highlight else '',
                  inputs=False)
    total = 0
    for k, (lg, sh, wv) in enumerate(zip(part['log'], part['shots'], part['wav'])):
        files, ents, idx, key = c_part(lg, sh, (part.get('range') or [None] * 99)[k])
        if not idx: continue
        sub = [files[i] for i in idx]
        rate = read_wav(rp(wv))[1]
        sps = rate * (len(idx) - 1) / max(1, ents[idx[-1]]['aud'] - ents[idx[0]]['aud'])   # shots per second of sound
        # black runs: keep 0.4 s; static: dialog pictures up to 6 s, gameplay 1.5 s (seconds of sound)
        kept = cap_runs(sub, black_keep=max(3, int(0.4 * sps)), static_keep=int((6.0 if chain else 1.5) * sps),
                        static_eps=1.5 if chain else 0.6)        # pictures: twinkling stars change ~1 level
        keep = [idx[j] for j in kept]
        add_take(tl, mid, files, ents, rp(wv), keep, crop=True, hold=chain)
        total += len(keep)
    return total


def highlight(tl, hl, logmap, n, of):
    lg = hl['log']; sh, wv = logmap[lg]
    pad = 45                                          # t units (VIs): 0.75 s either side
    files, ents, idx, key = c_part(lg, sh, (hl['from_t'] - pad, hl['to_t'] + pad))
    mid = tl.meta(section=f'Gall Run highlights  ·  {n} / {of}', title=hl['title'], caption='', inputs=False)
    add_take(tl, mid, files, ents, rp(wv), idx, crop=True)
    return len(idx)


# ---------------------------------------------------------------- rendering

def draw_card(lines):
    im = Image.new('RGB', (W, H), (8, 8, 12)); d = ImageDraw.Draw(im)
    sizes = [s for _, s, _ in lines]; y = (H - sum(int(s * 1.55) for s in sizes)) / 2
    for t, s, c in lines:
        f = font(BOLD if s >= 40 else REG, s)
        d.text(((W - d.textlength(t, font=f)) / 2, y), t, font=f, fill=c); y += int(s * 1.55)
    return im


def panel_base(m):
    """Static part of a single take's frame: panel with section, title, caption."""
    im = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(im)
    d.rectangle((GAME_W, 0, GAME_W + 3, H), fill=(40, 40, 48))
    y = 34
    f = font(BOLD, 20)
    for ln in wrap(d, m['section'].upper(), f, PW): d.text((PX, y), ln, font=f, fill=GREY); y += 28
    y += 14
    f = font(BOLD, 40)
    for ln in wrap(d, m['title'], f, PW): d.text((PX, y), ln, font=f, fill=YEL); y += 50
    y += 12
    if m.get('caption'):
        f = font(REG, 28)
        for ln in wrap(d, m['caption'], f, PW): d.text((PX, y), ln, font=f, fill=WHITE); y += 38
    f = font(REG, 18)
    d.text((PX, H - 40), 'SotE Extended · N64 patch', font=f, fill=(110, 110, 120))
    m['_y'] = y + 24
    return im


def draw_inputs(d, m, e):
    y0 = max(m['_y'], 470)
    cx, cy, r = PX + 80, y0 + 85, 72
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(120, 120, 130), width=4)
    d.line((cx - r, cy, cx + r, cy), fill=(60, 60, 70), width=2); d.line((cx, cy - r, cx, cy + r), fill=(60, 60, 70), width=2)
    sx, sy = cx + e.get('x', 0) / 80 * (r - 14), cy - e.get('y', 0) / 80 * (r - 14)
    d.line((cx, cy, sx, sy), fill=(255, 210, 60), width=6); d.ellipse((sx - 14, sy - 14, sx + 14, sy + 14), fill=(255, 210, 60))
    b = e.get('b', '') or ''
    for i, bn in enumerate(('A', 'B', 'Z')):
        bx, by = PX + 210 + i * 76, cy - 30; on = bn in b
        col = {'A': (60, 110, 230), 'B': (40, 160, 70), 'Z': (170, 170, 180)}[bn] if on else (45, 45, 55)
        d.ellipse((bx - 28, by - 28, bx + 28, by + 28), fill=col, outline=(120, 120, 130), width=2)
        fb = font(BOLD, 26); d.text((bx - d.textlength(bn, font=fb) / 2, by - 15), bn, font=fb, fill=WHITE if on else (130, 130, 140))
    ex = m.get('extra') or []
    for i, c in enumerate(ex):
        lab = dict(EXTRA)[c]; bx, by = PX + 182 + (i % 3) * 82, cy + 32 + (i // 3) * 42; on = c in b
        d.rounded_rectangle((bx, by, bx + 74, by + 34), 8, fill=(170, 120, 40) if on else (45, 45, 55), outline=(120, 120, 130), width=2)
        fb = font(BOLD, 16); d.text((bx + 37 - d.textlength(lab, font=fb) / 2, by + 8), lab, font=fb, fill=WHITE if on else (130, 130, 140))
    y = cy + r + 30 + (16 if len(ex) > 3 else 0)
    badge = 'HANGING' if e.get('hang') else 'LOCKED ON' if e.get('lock') else ''
    if badge:
        d.rounded_rectangle((PX, y, PX + PW, y + 50), 10, fill=(40, 120, 70) if e.get('hang') else (160, 40, 40))
        d.text((PX + 16, y + 10), badge, font=font(BOLD, 28), fill=WHITE)
    y += 70
    f = font(BOLD, 27)
    for ln in wrap(d, e.get('label', ''), f, PW)[:4]: d.text((PX, y), ln, font=f, fill=LAB); y += 36


def game_img(path, crop):
    im = Image.open(path).convert('RGB')
    if crop:                                         # C: 1440x1080 with a black band on top
        g = Image.new('RGB', (GAME_W, H), (0, 0, 0)); c = im.crop((0, 84, 1440, 1070)); g.paste(c, (0, (H - c.height) // 2))
        return g
    return im.resize((GAME_W, H), Image.Resampling.LANCZOS)


def render_chunk(args):
    frames, metas, out, idx = args
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
                          '-preset', 'medium', '-threads', '2', '-r', str(FPS), out], stdin=subprocess.PIPE)
    cache, bases, last = {}, {}, None
    for fr in frames:
        if fr[0] == 'card':
            _, cid, b = fr
            if cid not in cache: cache[cid] = np.asarray(draw_card(metas[cid]['card']), np.float32)
            buf = (cache[cid] * b).astype(np.uint8).tobytes(); last = None
        elif fr[0] == 'single':
            _, path, mid, e, bl, crop = fr
            key = (path, bl, mid, json.dumps(e, sort_keys=True))
            if key == last: p.stdin.write(buf); continue
            m = metas[mid]
            if mid not in bases: bases[mid] = panel_base(m)
            im = bases[mid].copy()
            g = game_img(path, crop)
            if bl: g = Image.blend(g, game_img(bl[0], crop), bl[1])
            im.paste(g, (0, 0)); d = ImageDraw.Draw(im)
            if m.get('inputs'): draw_inputs(d, m, e)
            buf = im.tobytes(); last = key
        else:
            _, pl, el, pr, er, mid = fr; m = metas[mid]
            s = Image.new('RGB', (W, H), (10, 10, 14)); d = ImageDraw.Draw(s)
            t = f"{m['section']}  ·  {m['title']}"
            d.text(((W - d.textlength(t, font=font(BOLD, 38))) / 2, 18), t, font=font(BOLD, 38), fill=YEL)
            d.text(((W - d.textlength(m['caption'], font=font(REG, 28))) / 2, 80), m['caption'], font=font(REG, 28), fill=WHITE)
            conv = lambda e: dict(e, b=sum(v for k, v in (('A', 128), ('B', 64), ('Z', 32), ('R', 4096), ('S', 16)) if k in (e.get('b') or '')))
            s.paste(pane(Image.open(pl), conv(el), 'ORIGINAL', (90, 90, 100)), (0, 170))
            s.paste(pane(Image.open(pr), conv(er), 'PATCH: new controls', (40, 120, 70)), (GW + 32, 170))
            buf = s.tobytes(); last = None
        p.stdin.write(buf)
    p.stdin.close(); p.wait()
    return idx, out


# ---------------------------------------------------------------- main

def ig88_take(tl, entry):
    """IG-88 into Cut 05 (ig88_to_c05): the fight without its drop=1 stretches, then without a cut his death,
    the Level Complete screen and the black before Cut 05's first picture, timed by the audio ('aud'): the
    game draws few frames there. The story's Cut 05 part follows straight on (its first picture)."""
    files, ents, dirs, wav_by_dir = b_files(entry)
    extra = [c for c, _ in EXTRA if any(c in e.get('b', '') for e in ents)]
    mid = tl.meta(section='Z lock-on', title=entry['title'], caption=entry['caption'], extra=extra, inputs=True)
    d0 = next(i for i, e in enumerate(ents) if e['label'].startswith('IG-88 down'))
    keep = [i for i in range(d0) if not ents[i].get('drop')]
    breaks = {k for k in range(1, len(ents)) if ents[k].get('cut') or ents[k]['dir'] != ents[k - 1]['dir']}
    breaks |= {b for a, b in zip(keep, keep[1:]) if b != a + 1}
    add_take(tl, mid, files, ents, None, keep, breaks, wav_of=lambda i: wav_by_dir[ents[i]['dir']])
    fight = len(keep)
    # after his death: up to the last frame before Cut 05's first picture
    c05 = next(i for i, e in enumerate(ents) if e['label'].startswith('Cut 05'))
    th = thumbs(files[c05:c05 + 20])
    d1 = c05 + next((k for k, t in enumerate(th) if t[0].mean() > 10), 0)     # first frame of the picture
    mid2 = tl.meta(section='Z lock-on', title=entry['title'], caption='IG-88 down \u2014 on to the Gall Run', inputs=False)
    rate, aud = 22047, np.array([e['aud'] for e in ents], float)
    n = int((aud[d1] - aud[d0]) * FPS / rate)
    start = len(tl.frames)
    for j in range(n):
        i = d0 + int(np.searchsorted(aud[d0:d1], aud[d0] + j * rate / FPS, side='right')) - 1
        tl.frames.append(('single', files[i], mid2, {'label': ents[i]['label']}, None, False))
    w = wave.open(wav_by_dir[ents[d0]['dir']]); w.setpos(int(aud[d0]))
    x = np.frombuffer(w.readframes(int(aud[d1] - aud[d0])), dtype='<i2').reshape(-1, 2).astype(np.float32).mean(1)
    tl.add_audio(start, x[:int(n * rate / FPS)])
    return fight, n


def build(only=None):
    B = json.load(open(os.path.join(VID, 'manifest_B.json')))
    C = json.load(open(os.path.join(VID, 'manifest_C.json')))
    tl = TL()
    want = lambda s: not only or s in only
    tl.mark('title')
    tl.card([(TITLE, 84, YEL), ('', 16, BG)] + [(x, 34, WHITE) for x in SUBTITLE], 4)
    secs = [('lock', 'Z lock-on', 'Lock on a boss with Z, circle-strafe, every shot goes to the lock'),
            ('controls', 'Controls: original vs patch', 'Same stick input on both sides. Left: original game. Right: the patch'),
            ('cheats', 'Cheats', 'A Cheats screen in the pause menu'),
            ('highlights', 'Gall Run highlights', ''),
            ('finale', 'Ledge hang on Gall', 'Walk off a rim: Dash catches it, hangs and climbs back up'),
            ('catch', 'Catching the edge', "Gall's start: from the post onto the Outrider, catch the edge, climb, take the silver Challenge Point")]
    def card(k):
        _, name, sub = next(x for x in secs if x[0] == k)
        return [(name, 64, YEL)] + ([(sub, 30, (200, 200, 210))] if sub else [])
    byo = {e['order']: e for e in B}

    if want('controls'):
        tl.mark('controls'); tl.card(card('controls'), 3)
        for e in [x for x in B if x['kind'] == 'side_by_side']: sbs_b(tl, e, 'Original vs patch')
    if want('lock'):
        tl.mark('lock'); tl.card(card('lock'), 3)
        # the gladiator: the roof (he is large, the lock-0 stretch dropped) and a little of the flight
        for e in sorted((x for x in B if x['section'] == 'Z lock-on' and 1 < x['order'] < 2), key=lambda x: x['order']):
            single_b(tl, e, 'Z lock-on')               # ordinary enemies first (manifest_B 1.1, 1.2, ... when recorded)
        single_b(tl, byo[2], 'Z lock-on', keep_fn=lambda f, en, d: (
            [k for k in boss_keep(en, d)[0] if k <= 470 or 991 <= k <= 1170], boss_keep(en, d)[1]))
        # AT-ST: one way round, the other way, Z held
        single_b(tl, byo[3], 'Z lock-on', keep_fn=lambda f, en, d: (
            list(range(0, 300)) + list(range(330, 480)) + list(range(630, 712)), set()))
        ig88_take(tl, byo[1])
    if want('story'):
        tl.mark('story')                               # no card: IG-88's end runs straight into Cut 05
        for part in C['story']: story(tl, part, chain=part.get('fps') == 15)
    if want('cheats'):
        tl.mark('cheats'); tl.card(card('cheats'), 3)
        for e in [x for x in B if x['section'] == 'Cheats']: single_b(tl, e, 'Cheats')
    if want('finale'):
        tl.mark('finale'); tl.card(card('finale'), 3)
        fin = [x for x in B if x['section'].startswith('Finale')]
        for e in fin:
            def kf(files, ents, dirs, e=e):
                o = orange(files)
                keep = list(range(len(ents)))
                if e['title'] == 'On the cliffs':           # the same spot as 'Canyon rims': its last cycle only
                    keep = [k for k in keep if ents[k]['t'] >= 1210]
                while keep and o[keep[0]] > 60: keep.pop(0)  # an opening hit flash
                return keep, set()
            single_b(tl, e, 'Ledge hang on Gall', keep_fn=kf)
    if want('catch'):
        tl.mark('catch'); tl.card(card('catch'), 3)
        e = byo[7.1]
        files, ents, dirs, wav_by_dir = b_files(e)
        extra = [c for c, _ in EXTRA if any(c in x.get('b', '') for x in ents)]
        mid = tl.meta(section='Catching the edge', title=e['title'], caption=e['caption'], extra=extra, inputs=True)
        add_take(tl, mid, files, ents, wav_by_dir[dirs[0]], [i for i, x in enumerate(ents) if x['t'] <= 300])   # (the close-up after the pickup cut)
        # the catch again at half speed (each frame twice, audio stretched at the same pitch)
        c = next(i for i, x in enumerate(ents) if x.get('hang'))
        slow = [dict(x, label='Again, slower') for x in ents]
        mid2 = tl.meta(section='Catching the edge', title=e['title'], caption='Again, slower: the jump falls short, '
                       'Dash catches the edge.', extra=extra, inputs=True)
        add_take(tl, mid2, files, slow, wav_by_dir[dirs[0]], list(range(max(0, c - 22), min(len(ents), c + 50))), nrep=2)
    if want('highlights'):
        tl.mark('highlights'); tl.card(card('highlights'), 3)
        logmap = {}
        for part in C['story']:
            for lg, sh, wv in zip(part['log'], part['shots'], part['wav']): logmap[lg] = (sh, wv)
        for k, hl in enumerate(C['highlights']): highlight(tl, hl, logmap, k + 1, len(C['highlights']))
    tl.mark('end')
    tl.card([(TITLE, 72, YEL), ('', 20, BG), ('Thanks for watching', 40, WHITE)], 6)
    tl.mark('_end')
    return tl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analyze', action='store_true'); ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--only', default=''); ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    only = set(filter(None, a.only.split(',')))
    tl = build(only)
    n = len(tl.frames)
    print('frames', n, 'seconds', round(n / FPS, 1))
    for (nm, f0), (_, f1) in zip(tl.marks, tl.marks[1:]): print(f'  {nm:12s} {f0 / FPS:7.1f} s  len {(f1 - f0) / FPS:6.1f} s')
    if a.analyze: return
    tmp = tempfile.mkdtemp(prefix='showcase_', dir=os.path.join(ROOT, 'local', 'run'))
    # audio: stereo, game rate; per-run peaks levelled a little
    rate = 22047
    track = np.zeros((int(n * rate / FPS) + rate, 2), np.float32)
    for start, l, r in tl.audio:
        s0 = int(start * rate / FPS)
        for ch, x in ((0, l), (1, r)):
            x = x[:len(track) - s0].copy(); fd = min(len(x) // 2, rate // 40)
            if fd: x[:fd] *= np.linspace(0, 1, fd); x[len(x) - fd:] *= np.linspace(1, 0, fd)
            track[s0:s0 + len(x), ch] += x
    # level by section: each section's 99.9th percentile to the same mark
    groups = []
    for (nm, f0), (_, f1) in zip(tl.marks, tl.marks[1:]):
        if nm == 'story' and groups and groups[-1][0] == 'lock': groups[-1][2] = f1
        else: groups.append([nm, f0, f1])
    for nm, f0, f1 in groups:
        s0, s1 = int(f0 * rate / FPS), int(f1 * rate / FPS); seg = track[s0:s1]
        if len(seg) and np.abs(seg).max() > 0: track[s0:s1] = seg / max(np.percentile(np.abs(seg), 99.9), 1) * 0.6 * 32767
    track = np.clip(track, -32767, 32767).astype('<i2')
    wf = os.path.join(tmp, 'audio.wav')
    w = wave.open(wf, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate); w.writeframes(track.tobytes()); w.close()
    # video: chunks rendered in parallel
    size = 900
    jobs = [(tl.frames[i:i + size], tl.metas, os.path.join(tmp, f'c{i // size:04d}.mp4'), i // size) for i in range(0, n, size)]
    with Pool(a.jobs) as pool:
        for idx, out in pool.imap_unordered(render_chunk, jobs): print('chunk', idx, 'of', len(jobs), flush=True)
    lst = os.path.join(tmp, 'list.txt')
    open(lst, 'w').write(''.join(f"file '{j[2]}'\n" for j in jobs))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-i', wf, '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', a.out], check=True)
    if a.out == OUT:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', OUT, '-vf', 'scale=1280:720:flags=lanczos', '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p', '-crf', '28', '-preset', 'medium', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000',
                        '-movflags', '+faststart', PHONE], check=True)
        for ps in (1, 2):                              # 854x480 preview under 28 MB: two-pass 140 kbit/s, mono AAC 48k
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', OUT, '-vf', 'scale=854:480:flags=lanczos', '-c:v', 'libx264',
                            '-b:v', '140k', '-pass', str(ps), '-passlogfile', os.path.join(tmp, 'pass'), '-pix_fmt', 'yuv420p',
                            '-preset', 'medium'] + (['-an', '-f', 'mp4', os.devnull] if ps == 1 else
                           ['-c:a', 'aac', '-b:a', '48k', '-ac', '1', '-ar', '48000', '-movflags', '+faststart', PREVIEW]), check=True)
    json.dump([(nm, f0 / FPS) for nm, f0 in tl.marks], open(os.path.join(VID, 'showcase_marks.json'), 'w'))
    print('wrote', a.out, 'tmp', tmp)


if __name__ == '__main__':
    main()
