"""Camera-relative movement and lazy camera on a savestate (default: Echo Base, play.st).

    M64CPU=0 python3 t_move.py <rom> [state]

Pushes the stick up/right/down/left/diagonal and prints Dash's facing, the patch's target
heading, the lazy camera angle and the real camera forward vector. Expect facing to reach
`tgt` within a few frames and `lazy` to drift toward facing while running.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms
from game import CAM, facing
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'play.st')
PHASES = [(30, 150, 0, 80, 'up'), (180, 330, 80, 0, 'right'), (360, 520, 0, -80, 'down'),
          (550, 700, -80, 0, 'left'), (730, 880, 57, 57, 'upright'), (900, 1000, 0, 0, 'idle')]
st_hang = []
start = {}


def wrap(a): return (a + 180) % 360 - 180


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
    for a, b, sx, sy, l in PHASES:
        if not (sx or sy) or not pl: continue
        if k == a: start[l] = (e.rf(pl + 0x50), e.rf(pl + 0x54))
        if k == b - 1:
            err = wrap(facing(e, pl) - (e.rf(S['g_target_yaw']) + 90))
            moved = math.hypot(e.rf(pl + 0x50) - start[l][0], e.rf(pl + 0x54) - start[l][1])
            check(f'{l}: facing on the target heading, moving', abs(err) < 8 and moved > 10,
                  f'err {err:.1f}, moved {moved:.1f}')
    if k % 15 == 0 and pl:
        cam = e.r32(CAM)
        camfwd = math.degrees(math.atan2(e.rf(cam + 0x28), e.rf(cam + 0x24))) if cam else 0
        print(f"{k:4d} {lab:8s} act={e.r32(S['g_active']) >> 24} facing={facing(e, pl):7.1f}"
              f" tgt={e.rf(S['g_target_yaw']) + 90:7.1f} lazy={e.rf(S['g_cam_facing']):7.1f} camfwd={camfwd:7.1f}"
              f" pos=({e.rf(pl + 0x50):7.1f},{e.rf(pl + 0x54):7.1f})", flush=True)
    if k % 50 == 0: e.shot()
    if 'g_hang_state' in S and e.r32(S['g_hang_state']): st_hang.append(k)
    if k == 1000:
        if 'g_hang_state' in S: check('no ledge grabs during the walk', not st_hang, f'{len(st_hang)} frames')
        if 'g_edge_stops' in S: print('ledge guard stops:', e.r32(S['g_edge_stops']))
        e.stop()


e.run(script)
sys.exit(report())
