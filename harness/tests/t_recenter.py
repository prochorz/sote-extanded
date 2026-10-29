"""Idle camera recenter (default: Echo Base, play.st).

    M64CPU=0 python3 t_recenter.py <rom> [state]

Runs toward the camera (stick down), then lets go. While running the camera must stay put
(Dash faces it, |facing-lazy| ~180); ~1.5 s after letting go it eases round behind him
(|facing-lazy| -> 0 within ~2 s more). A stick tap in between restarts the delay.
"""
import os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms
from game import facing
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'play.st')
PHASES = [(30, 160, 0, -80, 'down'), (160, 400, 0, 0, 'idle'), (400, 420, 80, 0, 'tapR'),
          (420, 660, 0, 0, 'idle2')]   # (to 660: the ease after the tap ends ~20 frames later since 7ebf2da: game dt
                                         # is counted from the CPU and a cheaper patch makes each frame less game time)
diffs = {}


def script(e, n):
    if n == 60: e.load_state(state)
    if n == 62: inject(e)
    if n < 70: return
    k = n - 70
    x = y = 0; lab = '-'
    for a, b, sx, sy, l in PHASES:
        if a <= k < b: x, y, lab = sx, sy, l
    e.pad(0, x, y)
    pl = e.r32(S['g_player'])
    if k % 10 == 0 and pl:
        f = facing(e, pl)
        lazy = e.rf(S['g_cam_facing'])
        d = diffs[k] = (f - lazy + 180) % 360 - 180
        print(f"{k:4d} {lab:6s} facing={f:7.1f} lazy={lazy:7.1f} diff={d:7.1f}", flush=True)
    if k in (150, 250, 330, 590): e.shot()
    if k == 660:
        check('camera stays put while running at it', min(abs(diffs[t]) for t in range(60, 160, 10)) > 170)
        check('no recenter in the first ~1.3 s idle', abs(diffs[240]) > 170, f'diff {diffs[240]:.1f}')
        check('recentred behind Dash ~4 s after stopping', abs(diffs[390]) < 10, f'diff {diffs[390]:.1f}')
        check('a stick tap restarts the delay', abs(diffs[510] - diffs[430]) < 3, f'{diffs[430]:.1f} -> {diffs[510]:.1f}')
        check('recentred again after the tap', abs(diffs[650]) < 10, f'diff {diffs[650]:.1f}')
        e.stop()


e.run(script)
sys.exit(report())
