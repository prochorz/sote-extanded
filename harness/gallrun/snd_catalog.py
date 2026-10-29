"""A listening catalog of the game's sounds: each listed id played alone, one WAV of them with a beep before each.

    M64CPU=0 .venv/bin/python3 gallrun/snd_catalog.py [--rom R] [--state S] [--out ../local/demo/x.wav] [--list ID:PITCH:LABEL;..]
                                                     [--sec 2.0]

From one state (default: the Cut 05 picture frame `run/bf45_c05_f3.st` on the patched `bf45` build) both sound options
(effects float 0x800D2524, music 0x800D2528) are set to 0 every frame, so every sound the game requests reaches the
queue at volume 0; each id is then requested alone by a queue write each frame (sndlog.queue_put(): the first slot that
is free or holds that id), at the given pitch (as passed to 0x80007340: 0.25 = the wave at 11 kHz), volume 32000,
pan 64, until --sec seconds of real audio are dumped. A one-shot wave (no loop record in the bank) is requested again
after its length + 0.25 s. After a clip the request stops (the game fades it) and 0.4 s of audio passes before the next.
The audio is the audio_dump.dylib plugin's stream (the default AUDIOPLUGIN); the harness makes only ~1/4 s of audio a
second of frames, so a 2 s clip takes ~8 s of frames; the pitch is real (audio time). The WAV: a 0.12 s 1 kHz beep,
0.15 s silence, the clip, 0.5 s silence, per entry; the text list beside it (same name, .txt) gives each entry's start
second and its RMS level (dBFS), and the entries skipped (real length under 0.3 s, a click)."""
import os, sys, struct, wave, math, argparse, ctypes
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE + '/..'); sys.path.insert(0, HERE)
ROOT = os.path.abspath(HERE + '/../..')
import paths

# The ids the stock levels' objects request, by sub-level (sndlog.py, 2026-10-21, A held, 2400 frames per state), with a pitch they use.
DEFAULT = """1:0.53:Battle of Hoth - player snowspeeder (Spdr), looped, pitch 0.47..0.59
1:0.49:level 30 - other ships (TieF types 4/8), looped, pitch 0.485..0.494
1:0.23:level 30 - other ships (TieF), looped, pitch 0.232
1:0.11:Station Chase level 29 - other ships (TieF), looped, pitch 0.098..0.125
2:0.5:Battle of Hoth (rbgn) at a place; level 30 TieF one-shot 0.49
3:0.5:Battle of Hoth - probe droid code (PRBT) at a place
4:0.25:Battle of Hoth - probe droid code (PRBT) at a place, looped
5:0.5:Battle of Hoth - AT-AT (ATAT) at a place, looped
6:0.5:Battle of Hoth - AT-ST (ATST) at a place, looped
6:0.375:level 5 AT-ST state - at a place, looped
8:0.25:Battle of Hoth - probe droid code (PRBT) at a place
9:0.5:level 6 / level 30 / Chase - player ship code (Spdr area), one-shot
10:0.25:Battle of Hoth (rbgn) at a place, requested every few frames
10:0.5:level 30 / Chase - TieF one-shot, pitch 0.40..0.60
11:0.25:level 5 AT-ST state - at a place
22:0.25:level 6 / Chase (ATST-area code), one-shot
24:0.24:level 6 / level 30 - TieF one-shot
42:0.095:All ship levels - player ship engine (Stft), slow (0.093..0.099)
42:0.19:level 30 - player ship engine (Stft), fast (0.126..0.189)
42:0.25:Station Chase - player ship (Stft, other call 0x80098514), 0.127..0.249
43:0.24:level 6 / level 30 / Chase - TIEs (TieF), looped, 0.223..0.250
57:0.55:level 6 - Spdr-area code, one-shot
63:0.4:level 17 (bikes) - other bikes at a place, looped (0.32..5.5)
63:1.2:level 17 (bikes) - other bikes, higher pitch
72:0.24:level 6 / level 30 / Chase (TxAn), one-shot 0.18..0.30
73:0.3:level 6 / Chase - player ship (Stft), one-shot 0.25..0.37
74:0.21:Station Chase - player ship (Stft), 0.175..0.248
75:0.25:Hoth / level 6 / level 4 - one-shot 0.1..0.54
75:0.5:same, higher pitch
84:0.25:level 17 bikes one-shot; level 6 TieF 0.065..0.095
84:0.08:level 6 - TieF, low pitch
116:0.625:level 6 - at a place, looped (ATST-area code)
123:0.1:level 17 (bikes) - player bike, looped, slow (0.10..0.33)
123:0.3:level 17 (bikes) - player bike, fast
127:0.23:level 17 (bikes) - one-shot 0.22..0.24
0:0.5:level 6 - one-shot (caller 0x80028798)"""

ap = argparse.ArgumentParser()
ap.add_argument('--rom', default=paths.BUILD + '/bf45/sote-patch.z64')
ap.add_argument('--state', default=paths.RUN + '/bf45_c05_f3.st')
ap.add_argument('--out', default=paths.LOCAL + '/demo/ship_sound_catalog.wav')
ap.add_argument('--list', default='')
ap.add_argument('--sec', type=float, default=2.0)
A = ap.parse_args()
ENT = [(int(i), float(p), lab) for i, p, lab in (ln.split(':', 2) for ln in (A.list.split(';') if A.list else DEFAULT.split('\n')) if ln.strip())]
os.environ.setdefault('SHOTS', 'snd_catalog')
import m64
from m64 import Emu
from sndlog import SndLog, QUEUE, GFRAME

e = Emu(os.path.abspath(A.rom), video=m64.GLN)
aud = ctypes.CDLL(os.environ.get('AUDIOPLUGIN') or os.path.join(paths.BIN, 'audio_dump.dylib'))
aud.audio_dump_frames.restype = ctypes.c_long
raw = os.path.splitext(os.path.abspath(A.out))[0] + '.raw'
S = {'i': 0, 'ph': 'gap', 'mark': 0, 'trig': 0, 'segs': [], 'skip': []}
INFO = {}


def put(sid, pitch):
    """Request sid this frame in the first queue slot free or holding it (as sndlog.queue_put writes slot 7)."""
    for s in range(7, -1, -1):
        a = QUEUE + 32 * s; h, cur = e.r32(a), e.r32(a + 4)
        if h == 0xFFFFFFFF or cur == sid:
            if h == 0xFFFFFFFF: e.w32(a, 0xFFFFFFFE); e.w32(a + 4, sid)
            e.w32(a + 8, 1); e.w32(a + 12, e.r32(GFRAME)); e.w32(a + 16, 7)
            e.w32(a + 20, struct.unpack('>I', struct.pack('>f', pitch * 2))[0]); e.w32(a + 24, 32000)
            e.w32(a + 28, 64 << 16 | (e.r32(a + 28) & 0xFFFF))
            return s
    return -1


def drop(sid):
    for s in range(8):
        a = QUEUE + 32 * s
        if e.r32(a + 4) == sid and e.r32(a) not in (0xFFFFFFFF,): e.w32(a + 12, 0)   # stale stamp: the game fades it


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(os.path.abspath(A.state))
    if n < 64: return
    e.wf(0x800D2524, 0.0); e.wf(0x800D2528, 0.0)
    if n == 64:
        _, cnt, r = SndLog(e, out=lambda s: None).bank()
        for sid, (snd, wt, b0, ln, ls, le, lc) in r.items(): INFO[sid] = (ln / 9 * 16, ls >= 0)   # samples, looped
        aud.audio_dump_start(raw.encode()); S['f'] = aud.audio_dump_freq()
        return
    f = S['f'] or aud.audio_dump_freq(); now = aud.audio_dump_frames()
    if S['i'] >= len(ENT):
        e.stop(); return
    sid, pit, lab = ENT[S['i']]
    smp, looped = INFO.get(sid, (0, False))
    real = smp / (pit * 44100) if pit > 0 else 0
    if S['ph'] == 'gap':
        if now - S['mark'] >= 0.4 * f:
            if not looped and real < 0.3:
                S['skip'].append((sid, pit, lab, real)); S['i'] += 1; S['mark'] = now; return
            S['ph'], S['mark'], S['trig'] = 'play', now, now
    if S['ph'] == 'play':
        if not looped and now - S['trig'] >= (real + 0.25) * f:      # a one-shot again
            for s in range(8):
                a = QUEUE + 32 * s
                if e.r32(a + 4) == sid: e.w32(a, 0xFFFFFFFF)
            S['trig'] = now
        if put(sid, pit) < 0 and 'busy' not in S: S['busy'] = 1; print('no free queue slot for', sid, flush=True)
        if now - S['mark'] >= A.sec * f:
            S['segs'].append((sid, pit, lab, S['mark'], now, looped, real)); S['ph'] = 'tail'; S['mark'] = now
    elif S['ph'] == 'tail':
        drop(sid)
        if now - S['mark'] >= 0.15 * f:
            a, b = S['segs'][-1][3:5]; S['segs'][-1] = S['segs'][-1][:4] + (now,) + S['segs'][-1][5:]
            S['ph'] = 'gap'; S['i'] += 1; S['mark'] = now


e.run(script)
aud.audio_dump_stop()
f = S['f']
pcm = open(raw, 'rb').read()
sm = struct.unpack('<%dh' % (len(pcm) // 2), pcm)     # stereo interleaved


def silence(t): return [0] * (2 * int(t * f))


beep = []
for i in range(int(0.12 * f)):
    v = int(6000 * math.sin(2 * math.pi * 1000 * i / f)); beep += [v, v]
outv, lines = [], []
lines.append(f'Ship sound catalog: each entry is a 0.12 s beep, then the sound alone (~{A.sec:.0f} s), then 0.5 s silence.')
lines.append('The sounds are the stock game bank ids, played by a direct queue request (volume 32000, pan middle);')
lines.append(f'pitch as passed to the game call 0x80007340 (0.25 = the wave at 11 kHz). Recorded in the harness at {f} Hz;')
lines.append('the harness makes ~1/4 s of audio per second of frames, so each clip took ~4x its length in frames; audio is real time.')
lines.append('one-shot sounds (no loop) are re-triggered within the clip.')
lines.append('')
lines.append(f'{"start s":>8}  {"id":>3}  {"pitch":>6}  {"level dBFS":>10}  kind      where it plays')
for sid, pit, lab, a, b, looped, real in S['segs']:
    outv += beep + silence(0.15)
    st = len(outv) / 2 / f
    seg = list(sm[2 * a:2 * b]); outv += seg + silence(0.5)
    rms = math.sqrt(sum(x * x for x in seg) / max(1, len(seg))) if seg else 0
    db = 20 * math.log10(rms / 32768) if rms > 0 else -999
    kind = 'looped' if looped else f'one-shot {real:.2f}s'
    lines.append(f'{st:8.2f}  {sid:3d}  {pit:6.3f}  {db:10.1f}  {kind:<9} {lab}')
if S['skip']:
    lines.append(''); lines.append('Skipped (under 0.3 s at that pitch, clicks):')
    for sid, pit, lab, real in S['skip']: lines.append(f'  id {sid} pitch {pit} ({real:.2f} s): {lab}')
w = wave.open(A.out, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(f)
w.writeframes(struct.pack('<%dh' % len(outv), *outv)); w.close()
os.remove(raw)
open(os.path.splitext(A.out)[0] + '.txt', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
