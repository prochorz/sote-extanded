#!/usr/bin/env python3
"""Record the Look take: Dash drawn as the red palace guard (Cheats -> Look: Dash / Guard, guard.c).

    cd harness && PAYLOAD_BUILD=../local/build/guard RES=960x720 SHOTS=guard_take M64CPU=0 \\
        AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib python3 ../tools/video/record_guard_take.py <rom> guard_take.json [look|cam]

From palace.st (sub-level 26, its held radio line let go): Dash runs as himself; START -> Cheats -> Look -> Guard,
resume; he runs, strafes, jumps and fires in the red armour; a cut to a red guard (Dash put TP_D from it (Trop 0, the red guard the asset was made
from; kind-0 Trops of health 30 wear green), facing it,
Villains aren't sleepy on), Z lock-on and B fire beside the real guards; Look back to Dash. Dash's health is
held. Debug Display on. Frames: local/run/shots/<SHOTS>/ every 2nd VI; JSON one entry per frame {t, x, y, b, label,
aud} for compose_takes.py (b letters: A B Z, S = START, U / D = D-pad up / down).
"""
import ctypes as C, json, os, sys, wave
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, BTN
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
OUT = os.path.abspath(sys.argv[2]); RAW = OUT[:-5] + '.raw'
TAKE = sys.argv[3] if len(sys.argv) > 3 else 'look'     # look | cam (Creature Cam on the red guard) | tour (all sides)
AUD = C.CDLL(os.environ['AUDIOPLUGIN']) if os.environ.get('AUDIOPLUGIN') else None
if AUD: AUD.audio_dump_frames.restype = C.c_long
KEY = {'A': 'A', 'B': 'B', 'Z': 'Z', 'S': 'START', 'U': 'U_D', 'D': 'D_D', 'R': 'R', 'L': 'L'}
HUMN_HP, HOLD, HOLD_T, SLEEPY = 0xB4, 0x800DD2D0, 0x800D07FC, 0x800DD2C4
TP_D = 14.0                              # Dash put this far from the first red guard (kind-0 Trop), facing it
                                         # (heading h moves along (-sin h, cos h))

# events: (frame, keys, stick (x, y) or None, label); a key press lasts 4 frames, a stick holds until the next event
ev, t = [], 0


def at(keys='', stick=None, label=None, gap=12):
    global t
    ev.append((t, keys, stick, label, gap)); t += gap


def look_toggle(label, ups):
    at('S', (0, 0), label, 40)
    for _ in range(3): at('D', None, None, 14)
    at('A', None, None, 40)
    for _ in range(ups): at('U', None, None, 16)     # up from row 0 wraps: Reset cheats, then Look (the row is kept)
    at('', None, None, 30)
    at('A', None, None, 50)
    at('B', None, None, 24)
    at('D', None, None, 16)
    at('A', None, 'Resume', 30)


if TAKE == 'look':
    at('', (0, 0), "Xizor's palace: Dash as himself", 40)
    at('', (0, 80), None, 60)
    at('', (0, 0), None, 20)
    look_toggle('Pause -> Cheats -> Look: Guard', 2)
    at('', (0, 0), 'Dash in the red guard armour: his own moves', 20)
    at('', (0, 80), 'Runs where the stick points', 60)
    at('', (-80, 0), None, 40)
    at('', (0, -80), None, 40)
    at('', (80, 0), None, 40)
    at('A', (0, 60), 'Jumps', 40)
    at('', (0, 0), None, 10)
    at('B', None, 'Fires', 12)
    for _ in range(5): at('B', None, None, 12)
    at('', None, None, 30)
    TP_AT = t
    at('', (0, 0), "The palace guards' hall", 40)
    at('Zh', None, 'Z locks on a real guard, B fires', 0)
    at('ZB', None, None, 180)
    at('', (0, 0), None, 30)
    look_toggle('Pause -> Cheats -> Look: Dash', 0)
    at('', (0, 0), 'Back to Dash', 60)
elif TAKE == 'tour':                                  # Look on from the start (g_guard_on), runs every way round
    TP_AT = -1
    at('', (0, 0), 'Look: Guard. Standing', 50)
    at('', (0, 80), 'Runs away from the camera', 50)
    at('', (0, -80), 'Runs toward the camera: the front', 45)
    at('', (0, 0), None, 20)
    at('', (-80, 0), 'Runs to the side: the profile', 45)
    at('', (80, 0), None, 45)
    at('', 'circle', 'Runs round in a circle', 150)
    at('', (0, 0), 'Turns on the spot and fires', 20)
    at('', (-40, -60), None, 12)
    at('', (0, 0), None, 10)
    for _ in range(4): at('B', None, None, 12)
    at('A', (0, -60), 'Jumps toward the camera', 40)
    at('', (0, 0), None, 40)
else:
    TP_AT = -1
    at('', (0, 0), "Xizor's palace: a red guard stands in the hall", 40)
    at('S', (0, 0), 'Pause -> Cheats -> Creature Cam: Trooper', 40)
    for _ in range(3): at('D', None, None, 14)
    at('A', None, None, 40)
    for _ in range(4): at('U', None, None, 16)        # up from row 0: Reset cheats, Look, Friendly Wampas, Creature Cam
    at('', None, None, 20)
    at('L', None, None, 30)                           # Dash -> Trooper (back one; Wampa: none here)
    at('', None, None, 30)
    at('B', None, None, 24)
    at('D', None, None, 16)
    at('A', None, 'Resume: the camera follows the guard', 40)
    at('', (0, 0), 'The stick walks and turns the guard', 30)
    at('', (0, 80), None, 90)
    at('', (80, 0), None, 40)
    at('', (0, 80), None, 60)
    at('', (-80, 0), None, 50)
    at('', (0, 80), None, 60)
    at('', (0, 0), 'B: the guard attacks', 10)
    for _ in range(4): at('B', None, None, 24)
    at('', (0, 0), None, 40)
END = t
log, st = [], {}


def state(k):
    keys, held, stick, lab = 0, '', (0, 0), None
    for f, kk, s, l, g in ev:
        if f > k: break
        if s is not None: stick = s
        if l is not None: lab = l
        if kk in ('Zh', 'ZB'):
            if k >= f + g: continue                                   # held for the event's own span
            keys |= BTN['Z']; held += 'Z'
            if kk == 'ZB' and (k // 6) % 2 == 0: keys |= BTN['B']; held += 'B'
        elif kk and f <= k < f + 4:
            keys |= BTN[KEY[kk]]; held += kk
    return keys, held, stick, lab


def humn():
    p = e.r32(0x80112830)                                             # the class records: Humn's pool = Dash
    for i in range(80):
        r = e.r32(p + 4 * i)
        if not r: return 0
        if e.r32(r) == 0x48756D6E: return e.r32(r + 0x10)
    return 0


def guard():
    p = e.r32(0x80112830)
    for i in range(80):
        r = e.r32(p + 4 * i)
        if not r: return 0
        if e.r32(r) == 0x54726F70:
            pool = e.r32(r + 0x10)
            return pool                                                    # Trop 0: the red guard guard_asset.py took
    return 0


def finish():
    json.dump(log, open(OUT, 'w'))
    if AUD:
        AUD.audio_dump_stop()
        w = wave.open(OUT[:-5] + '.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2)
        w.setframerate(AUD.audio_dump_freq()); w.writeframes(open(RAW, 'rb').read()); w.close(); os.remove(RAW)
    print('frames', len(log), flush=True); e.stop()


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'palace.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    if e.r16(HOLD): e.w32(HOLD, e.r32(HOLD) & 0xFFFF); e.wf(HOLD_T, 0)
    if TAKE == 'cam': e.w32(SLEEPY, e.r32(SLEEPY) & ~1)                   # the guards stay put for the camera
    e.w32(0x800DA6D0, (e.r32(0x800DA6D0) & 0xFFFF) | (2 << 16))       # Debug Display
    h = humn()
    if 0x80000000 <= h < 0x80800000: e.wf(h + HUMN_HP, 100.0)
    if k == 0 and AUD: AUD.audio_dump_start(RAW.encode())
    if k == TP_AT and 0x80000000 <= h < 0x80800000:
        g = guard()
        q = [e.rf(g + 0x50), e.rf(g + 0x54) + TP_D, e.rf(g + 0x58)]      # on the guard's +y side, facing -y: 180
        for a in range(3): e.wf(h + 0x08 + 4 * a, q[a]); e.wf(h + 0x50 + 4 * a, q[a])
        e.wf(h + 0x14, 180.0); e.w32(SLEEPY, e.r32(SLEEPY) | 1)
        print('guard at', [round(e.rf(g + 0x50 + 4 * a), 1) for a in range(3)], flush=True)
    keys, held, stick, lab = state(k)
    if stick == 'circle':                                              # the stick turned round once in 150 VIs
        import math
        a = 2 * math.pi * (k % 150) / 150; stick = (int(80 * math.sin(a)), int(80 * math.cos(a)))
    if TAKE == 'tour' and k == 2: e.w32(S['g_guard_on'], 1)
    e.pad(keys, stick[0], stick[1])
    if k % 60 == 0:
        print(k, 'look', e.r32(S['g_guard_on']), 'row', e.r32(S['g_cheats_row']), 'paused', e.r32(0x800DD2BC), 'creature', hex(e.r32(0x800E5EF4)),
              'dash', [round(e.rf(h + 0x50 + 4 * a), 1) for a in range(3)] if h else None, flush=True)
    if k % 2 == 0:
        e.shot()
        log.append(dict(t=k // 2, x=stick[0], y=stick[1], b=held, label=lab or '',
                        aud=AUD.audio_dump_frames() if AUD else 0))
    if k >= END: finish()


e.run(script)
