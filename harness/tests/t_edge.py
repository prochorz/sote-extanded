"""Edge test: walk toward the crevasse edges (default states/echo_crevasse.st) in 8 directions.

    M64CPU=0 python3 t_edge.py <rom> [state]

Each trial reloads the state and holds the stick for 150 frames at half and full tilt
(camera-relative). A big drop in z means Dash fell. `stops` counts g_edge_stops if a build
has a ledge guard (an experiment that was rolled back: it also killed jumping off edges).
With the ledge hang no trial may fall into the crevasse: half tilt doesn't leave the floor, full
tilt ends hanging ~5.4 below the floor (checked: lowest z above -10).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms
from game import HUMN_HP
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'echo_crevasse.st')
TRIALS = [(a, m) for m in (40, 80) for a in range(0, 360, 45)]
st = {'i': 0, 'k0': None}


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS): e.stop(); return
        e.load_state(state); st['k0'] = n; return
    k = n - st['k0']
    if k == 2:
        inject(e)
        if 'g_edge_stops' in S: e.w32(S['g_edge_stops'], 0)
    if k < 6: e.pad(0); return
    a, m = TRIALS[st['i']]
    pl = e.r32(S['g_player'])
    e.wf(pl + HUMN_HP, 100.0)                    # troopers shoot at this spot
    if k == 6: st['p0'] = (e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58)); st['zmin'] = 1e9
    e.pad(0, int(math.sin(math.radians(a)) * m), int(math.cos(math.radians(a)) * m))
    st['zmin'] = min(st['zmin'], e.rf(pl + 0x58))
    if k == 156:
        x0, y0, z0 = st['p0']
        print(f"dir {a:3d} stick {m}: moved {math.hypot(e.rf(pl + 0x50) - x0, e.rf(pl + 0x54) - y0):5.1f}"
              f" z {z0:.1f} -> min {st['zmin']:.1f}  stops {e.r32(S['g_edge_stops']) if 'g_edge_stops' in S else '-'}", flush=True)
        if 'g_hang_state' in S:
            check(f'dir {a} stick {m}: no fall into the crevasse', st['zmin'] > z0 - 12, f'lowest z {st["zmin"]:.1f}')
        e.shot(); st["i"] += 1; st["k0"] = None


e.run(script)
sys.exit(report())
