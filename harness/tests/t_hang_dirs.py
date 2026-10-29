"""Ledge hang catches around the Echo Base crevasse: 8 directions x (walk off / tap A at frame j).

    M64CPU=0 python3 t_hang_dirs.py <rom>
    env: DIRS=0,90  JUMPS=n,15,45 (n = no jump)  TAP=1 (frames A is held)  MAG=80

Each trial reloads states/echo_crevasse.st, runs at full tilt (camera-relative), taps A at
frame j, and prints every catch: where he left the floor, the rim found, the hang point.
A shot is taken 40 frames after each catch (SHOTS=<dir> to keep them apart).
Expect: no catch right after a jump (a jump that hit the low cave ceiling and landed counts as
walking off later), the hang point 1.55 out from the lip and 6.4 below the rim.
Checked: that geometry for every catch, and which directions catch when walking off (WALK_CATCH).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMN_HP
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, 'echo_crevasse.st')
DIRS = [int(v) for v in os.environ.get('DIRS', '0,45,90,135,180,225,270,315').split(',')]
JUMPS = [None if v == 'n' else int(v) for v in os.environ.get('JUMPS', 'n,15,30,45,60').split(',')]
TAP = int(os.environ.get('TAP', '1'))
MAG = int(os.environ.get('MAG', '80'))
TRIALS = [(a, j) for a in DIRS for j in JUMPS]
H = S['g_hang']          # struct hang_state: ground +0, pos +32, face +52, edge +104
WALK_CATCH = {0: False, 45: True, 90: True, 135: True, 180: True, 225: True, 270: True, 315: True}
st = {'i': 0, 'k0': None}


def hf(off): return e.rf(H + off)


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS): e.stop(); return
        e.load_state(state); st.update(k0=n, grab=None, air=None, zmin=1e9); return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 6: e.pad(0); return
    a, j = TRIALS[st['i']]
    pl = e.r32(S['g_player'])
    e.wf(pl + HUMN_HP, 100.0)                    # troopers shoot at this spot
    fl = e.r32(pl + 0x74)
    x, y, z = e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58)
    st['zmin'] = min(st['zmin'], z)
    if st['air'] is None and fl & 0x08000000: st['air'] = (k, e.rf(pl + 0xA0))
    if e.r32(S['g_hang_state']) and st['grab'] is None:
        st['grab'] = k
        print(f"dir {a:3d} jump {j}: CATCH k={k} airborne k={st['air'][0]} vz={st['air'][1]:.0f} at ({x:.1f},{y:.1f},{z:.1f})"
              f" floor=({hf(0):.1f},{hf(4):.1f},{hf(8):.1f}) face=({hf(52):.1f},{hf(56):.1f}) rim={hf(104):.1f}"
              f" hang=({hf(32):.1f},{hf(36):.1f},{hf(40):.1f})", flush=True)
        below, out = hf(104) - hf(40), math.hypot(hf(32) - hf(52), hf(36) - hf(56))
        check(f'dir {a} jump {j}: hang 6.4 below the rim, 1.55 out', abs(below - 6.4) < 0.2 and abs(out - 1.55) < 0.2,
              f'{below:.2f} below, {out:.2f} out')
    if st['grab'] is not None:
        e.pad(0)
        if k == st['grab'] + 40: e.shot()
    else:
        b = BTN['A'] if j is not None and j <= k < j + TAP else 0
        e.pad(b, int(math.sin(math.radians(a)) * MAG), int(math.cos(math.radians(a)) * MAG))
    if k == 200:
        if st['grab'] is None: print(f"dir {a:3d} jump {j}: no catch, lowest z {st['zmin']:.1f}", flush=True)
        if j is None and a in WALK_CATCH:
            check(f'dir {a} walking off: {"catch" if WALK_CATCH[a] else "no catch"}', (st['grab'] is not None) == WALK_CATCH[a])
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
sys.exit(report())
