"""Camera pitch on the Echo Base stairs (echo_stairs.st: foot of the stairs after the lift).

    M64CPU=0 python3 t_stairs.py <rom> [orig]     (orig: the game's own code put back, no payload)

Runs up the stairs, then turns and runs back down toward the camera, and prints the active
camera's pitch every 10 frames plus the min/max per leg. The game pitches Dash's camera matrix
(+0x108) on slopes and the camera follows: the original reaches about +30 deg going up and -34
coming down. With the patch expect about -6..+3 going up and no worse than about -25 coming down.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject
from game import CAM, HUMN_HP
from testlib import check, report

orig = len(sys.argv) > 2 and sys.argv[2] == 'orig'
e = Emu(sys.argv[1])
ROUTE = [(170, 0, 80, 'up'), (40, 0, 0, '-'), (130, 0, -80, 'down')]
O = 0x801B13FC                       # Humn in this state (no g_player without the payload)
pitch = {'up': [], 'down': []}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_stairs.st'))
    if n == 62: inject(e, payload=not orig)
    if n < 70: return
    k = n - 70; t = 0
    for f, x, y, lab in ROUTE:
        if k < t + f: break
        t += f
    else:
        for lab, v in pitch.items(): print(f'{lab}: pitch {min(v):.1f} .. {max(v):.1f}')
        up, down = pitch['up'], pitch['down']
        if orig:
            check('original: camera pitches up the stairs', max(up) > 20, f'max {max(up):.1f}')
            check('original: and down coming back', min(down) < -30, f'min {min(down):.1f}')
        else:
            check('going up: pitch stays near level', -8 < min(up) and max(up) < 6, f'{min(up):.1f} .. {max(up):.1f}')
            check('coming down: less pitch than the original', min(down) > -28, f'min {min(down):.1f}')
        e.stop(); return
    e.pad(0, x, y)
    e.wf(O + HUMN_HP, 100.0)         # troopers shoot from above
    cam = e.r32(CAM)
    p = math.degrees(math.asin(max(-1, min(1, e.rf(cam + 0x2C)))))
    if lab in pitch: pitch[lab].append(p)
    if k % 10 == 0:
        print(f"{k:4d} {lab:5s} pos=({e.rf(O + 0x50):6.1f},{e.rf(O + 0x58):6.1f}) pitch={p:6.1f}", flush=True)


e.run(script)
sys.exit(report())
