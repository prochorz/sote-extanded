#!/usr/bin/env python3
"""Takes of Luke's saber swings (saber.c) from a fixed camera: each swing alone, then the combo.

    cd harness && PAYLOAD_BUILD=../local/build/<b> RES=960x720 SHOTS=<dir> M64CPU=0 \\
        .venv/bin/python3 ../tools/video/record_saber_takes.py <out.json> side|front

Runs the build's own ROM (PAYLOAD_BUILD/sote-patch.z64) from palace.st (its held radio line let go), as t_saber.py's
flow case starts: the Look on Luke, the drop view (L twice), the saber drawn by the game's C-up cycle, the guards
held idle in their places, Debug Display on. Clips (CLIPS), each from Luke held still at the start place for SETTLE s
of game time: one tap (sw1); taps for sw1 -> sw2; for sw1 -> sw2 -> sw3; B held (sw1, then the spin); the combo then
the spin. The drop camera's eye is held at the start place + VIEWS[view] (out, deg from his facing, up), so his step
shows against the room. A shot every 2nd VI while a clip plays; the JSON per shot {t, b, label, clip, m (the playing
move, g_saber_move)}. Compose with compose_saber.py.
"""
import json, math, os, struct, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
import inject as inj
from m64 import Emu, BTN
from inject import inject, syms

S = syms()
OUT, VIEW_NAME = os.path.abspath(sys.argv[1]), sys.argv[2]
VIEWS = {'side': (8.0, 80.0, 2.5), 'front': (10.0, 20.0, 3.0)}
CAM = VIEWS[VIEW_NAME]
e = Emu(str(inj.BUILD / 'sote-patch.z64'), video=m64.GLN)
VIEW, EYE = 0x800E0EEC, 0x8018DD98       # the on-foot view (4: drop); the drop camera's eye
DEBUG_DISPLAY = 0x800DA6D0
TROP_HP, TROP_STATE, TROP_TIMER = 0x7C, 0x78, 0x80
SETTLE = 0.8
NAMES = {0: 'Cut 1: right to left', 1: 'Cut 2: left to right', 2: 'Cut 3: overhead', 3: 'Spin'}
# name, taps (s after the first), B held (from, to) s or None, the clip's length (s)
CLIPS = (('sw1', (0.0,), None, 1.25), ('sw2', (0.0, 0.30), None, 1.5), ('sw3', (0.0, 0.30, 0.68), None, 2.1),
         ('spin', (), (0.0, 0.8), 1.75), ('combo', (0.0, 0.30, 0.68), (1.05, 1.85), 2.9))
st = {'k0': None, 'ci': -1, 'log': []}


def r32(a): return e.r32(a)
def s32(v): return struct.unpack('<i', struct.pack('<I', v))[0]
def V(o, a): return [e.rf(o + a + 4 * i) for i in range(3)]
def clock(): return struct.unpack('>d', struct.pack('>II', r32(0x8018E9A8), r32(0x8018E9AC)))[0]


def trops():
    p = r32(0x80112830)
    for i in range(80):
        rec = r32(p + 4 * i)
        if not rec: break
        if r32(rec) == 0x54726F70:
            return [r32(rec + 0x10) + j * r32(rec + 0x0C) for j in range(r32(rec + 8))]
    return []


def put(o, p, yaw):
    for a in range(3): e.wf(o + 0x08 + 4 * a, p[a]); e.wf(o + 0x50 + 4 * a, p[a])
    e.wf(o + 0x14, yaw)


def take(k, h):
    if k == 9:
        e.w32(S['g_guard_on'], 2)
        e.w32(h + 0xB8, (r32(h + 0xB8) & 0xFFFF) | (4 << 16))      # the Stunner: C-up draws the saber
        st['p0'] = V(h, 0x50); st['yaw0'] = (e.rf(h + 0x14), e.rf(h + 0x8C))
        fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = math.hypot(*fw)
        f = math.atan2(fw[1] / l, fw[0] / l) + math.radians(CAM[1])
        st['eye'] = [st['p0'][0] + CAM[0] * math.cos(f), st['p0'][1] + CAM[0] * math.sin(f), st['p0'][2] + CAM[2]]
        st['tp'] = {o: V(o, 0x50) for o in trops() if not r32(o + 0x74) & 0xF}
    if k < 9: return 0
    e.w32(DEBUG_DISPLAY, (r32(DEBUG_DISPLAY) & 0xFFFF) | (2 << 16))
    if e.r16(VIEW) == 4:
        for a in range(3): e.wf(EYE + 4 * a, st['eye'][a])
    if 10 <= k < 14 or 40 <= k < 44: return BTN['L']   # follow -> first person -> drop
    if 60 <= k < 64: return BTN['CU']                  # the Stunner -> the saber
    if k < 90: return 0
    for o, q in st['tp'].items():
        put(o, q, e.rf(o + 0x14)); e.w32(o + TROP_STATE, 0); e.wf(o + TROP_TIMER, 100.0); e.wf(o + TROP_HP, 100.0)
    now = clock()
    if st['ci'] < 0 or ('t0' in st and now - st['t0'] >= CLIPS[st['ci']][3]):
        st['ci'] += 1; st.pop('t0', None); st['start'] = now
        if st['ci'] >= len(CLIPS):
            json.dump(st['log'], open(OUT, 'w')); print('log', OUT, len(st['log']), 'shots', flush=True); e.stop(); return 0
    name, taps, held, dur = CLIPS[st['ci']]
    if now - st['start'] < SETTLE:
        p0 = st['p0']
        for a in range(3): e.wf(h + 0x08 + 4 * a, p0[a]); e.wf(h + 0x50 + 4 * a, p0[a]); e.wf(h + 0x98 + 4 * a, 0.0)
        e.wf(h + 0x14, st['yaw0'][0]); e.wf(h + 0x8C, st['yaw0'][1])
        return 0
    if 't0' not in st: st['t0'] = now; st['vi0'] = k
    u = now - st['t0']
    b = 0
    if any(t <= u < t + 0.07 for t in taps): b = BTN['B']
    if held and held[0] <= u < held[1]: b = BTN['B']
    if (k - st['vi0']) % 2 == 0:
        m = s32(r32(S['g_saber_move']))
        e.shot()
        st['log'].append({'t': round(u, 3), 'b': 'B' if b else '', 'label': NAMES.get(m, ''), 'clip': name, 'm': m})
    return b


def script(e_, n):
    if n == 1: e.unlimit()
    if n < 60: return
    if st['k0'] is None:
        e.load_state(os.path.join(paths.STATES, 'palace.st')); st['k0'] = n; return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 4: return
    if e.r16(0x800DD2D0): e.w32(0x800DD2D0, e.r32(0x800DD2D0) & 0xFFFF); e.wf(0x800D07FC, 0)   # the held line
    h = r32(S['g_player'])
    if not h: e.pad(0); return
    e.wf(h + 0xB4, 100.0)
    if k == 8:
        for i in range(6): e.wf(h + 0xC0 + 4 * i, 50.0)
        e.w32(h + 0x74, r32(h + 0x74) | 0x3E000)
    e.pad(take(k, h))


e.run(script)
