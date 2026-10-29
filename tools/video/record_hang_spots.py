#!/usr/bin/env python3
"""Record one ledge-hang take for the "hang spots" video: run off an edge from a savestate,
catch it, then L to the overhead view so the hand on the rim shows.

    cd harness && RES=960x720 SHOTS=spot1 M64CPU=0 python3 ../tools/video/record_hang_spots.py <rom> <state> <dir> <stick> out.json

dir: stick direction in degrees (camera-relative, as in t_hang_spots.py), stick: tilt (80 full).
Frames every 2nd video frame (30 fps); JSON entries {t, x, y, b, label, hang} for compose_takes.py.
"""
import json, math, os, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
STATE, A, MAG, OUT = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
SX, SY = int(math.sin(math.radians(A)) * MAG), int(math.cos(math.radians(A)) * MAG)
log, st = [], {'grab': None}


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, STATE))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)                       # keep Dash alive
    if k < 90: e.pad(0); return                  # settle before recording
    t = k - 90
    hang = e.r32(S['g_hang_state'])
    if hang and st['grab'] is None: st['grab'] = t; st['gap'] = e.rf(S['g_hang_gap'])
    g = st['grab']
    x = y = 0; b = 0; lab = ''
    if g is None:
        if t >= 10: x, y = SX, SY; lab = 'Run off the edge (no jump)'
    else:
        h = t - g
        view = e.r16(0x800E0EEC)
        if h < 50: lab = 'Catch: he hangs where he went over'
        else:
            if view != 5 and (h - 50) % 12 < 3: b = 0x2000          # L until the overhead view
            lab = f"Overhead: hand on the rim, wall {st['gap']:.2f} away" if view == 5 else 'L: camera views'
    e.pad(b, x, y)
    if t % 2 == 0:
        e.shot(); log.append(dict(t=t, x=x, y=y, b='', label=lab, hang=hang))
    if (g is not None and t >= g + 150) or (g is None and t >= 260):
        json.dump(log, open(OUT, 'w')); print('frames', len(log), 'grab', g, 'gap', st.get('gap')); e.stop()


e.run(script)
