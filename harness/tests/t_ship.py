"""Jumping about on the Outrider (Gall, gall_tp5.st; user: "I keep falling into the ship"). Is
it the patch or the original game?

    M64CPU=0 python3 t_ship.py <rom>          # patched
    ORIG=1 M64CPU=0 python3 t_ship.py <rom>   # the unpatched game (inject(payload=False))
    env: DIRS=...  JUMPS=5,20

Dash is dropped on a grid over the ship; spots that land on the hull (z >= 215) are kept. From
each: run at full tilt in DIRS, A at JUMP. After 120 frames: "under" if he ends below 211 at a
spot whose hull top is above him (a cell of the grid that had hull). Prints the count.
Caveat (2026-10-06): such ends were all walks: he jumps off the hull's edge, lands beside it
and walks on under the overhang (TRACE=1 CELLS=x,y shows the path). 9 of 208 without the hang
module too; no trace went through the hull.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1])
ORIG = bool(os.environ.get('ORIG'))
DIRS = [int(v) for v in os.environ.get('DIRS', ','.join(str(a) for a in range(0, 360, 45))).split(',')]
JUMPS = [int(v) for v in os.environ.get('JUMPS', '5,20').split(',')]
GRID = [(x, y) for x in range(-310, -244, 6) for y in range(940, 996, 6)]
if os.environ.get('CELLS'): GRID = [tuple(int(v) for v in c.split(',')) for c in os.environ['CELLS'].split(';')]
st = {'phase': 'probe', 'i': 0, 'k0': None, 'hull': {}, 'under': 0, 'n': 0}


def player():
    if not ORIG: return e.r32(S['g_player'])
    if not st.get('pl'): st['pl'] = __import__('game').find_player(e)    # a RAM scan: once a trial
    return st['pl']


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['phase'] == 'probe' and st['i'] >= len(GRID):
            st['phase'] = 'run'; st['i'] = 0
            st['trials'] = [(c, a, j) for c, z in st['hull'].items() for a in DIRS for j in JUMPS]
            print(f"hull cells {len(st['hull'])}, trials {len(st['trials'])}", flush=True)
        if st['phase'] == 'run' and st['i'] >= len(st['trials']):
            print(f"{'ORIGINAL' if ORIG else 'PATCHED'}: ended under the hull {st['under']} of {st['n']}", flush=True)
            e.stop(); return
        e.load_state(os.path.join(paths.STATES, 'gall_tp5.st')); st['k0'] = n; st['pl'] = 0; return
    k = n - st['k0']
    if k == 2: inject(e, payload=not ORIG)
    if k < 6: e.pad(0); return
    pl = player()
    if not pl: return
    e.wf(pl + 0xB4, 100.0)
    if st['phase'] == 'probe':
        c = GRID[st['i']]
        if k < 10:
            for i, v in enumerate((c[0], c[1], 230.0)):
                e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
        e.pad(0)
        if k == 60:
            z = e.rf(pl + 0x58)
            if z >= 215 and e.r32(pl + 0x74) & 0x04000000: st['hull'][c] = z
            st['i'] += 1; st['k0'] = None
        return
    c, a, j = st['trials'][st['i']]
    if k < 10:
        for i, v in enumerate((c[0], c[1], st['hull'][c] + 1)):
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
        e.pad(0); return
    k -= 10
    b = BTN['A'] if j <= k < j + 4 else 0
    e.pad(b, int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80))
    if os.environ.get('TRACE') and k % 4 == 0:
        print('T', k, [round(e.rf(pl + 0x50 + 4 * i), 1) for i in range(3)], hex(e.r32(pl + 0x74)), flush=True)
    if k == 120:
        x, y, z = (e.rf(pl + 0x50 + 4 * i) for i in range(3))
        cell = (int(round((x + 310) / 6)) * 6 - 310, int(round((y - 940) / 6)) * 6 + 940)
        st['n'] += 1
        if z < 211 and cell in st['hull']:
            st['under'] += 1
            print(f"UNDER from {c} dir {a} A@{j}: end ({x:.1f},{y:.1f},{z:.1f}), hull there at {st['hull'][cell]:.1f}", flush=True)
            e.shot()
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
