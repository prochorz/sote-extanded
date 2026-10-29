"""Circle strafe around a fixed fake target in the open Echo Base hangar (play.st).

    M64CPU=0 python3 t_orbit.py <rom> [stick x] [radius]

Locks a fake target `radius` units in front of Dash, holds Z + stick x, and prints the
distance to the target and Dash's angle around it. A real orbit keeps the distance flat while
the angle advances steadily. With the defaults a parked snowspeeder stops him after about half a
circle (k ~180); the checks cover the orbit before that.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMN_YAW
from testlib import FAKE, make_fake, place_fake, check, report

S = syms()
e = Emu(sys.argv[1])
SX = int(sys.argv[2]) if len(sys.argv) > 2 else 80
R = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
st = {'samples': []}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'play.st'))
    if n == 62:
        inject(e); e.w32(S['g_test_skip_los'], 1)
        make_fake(e)
    if n < 70: return
    k = n - 70
    pl = e.r32(S['g_player'])
    if not pl: e.pad(0); return
    px, py = e.rf(pl + 0x50), e.rf(pl + 0x54)
    if 'c' not in st:
        f = math.radians(e.rf(pl + HUMN_YAW) + 90)
        st['c'] = (px + R * math.cos(f), py + R * math.sin(f))
        place_fake(e, *st['c'], e.rf(pl + 0x58))
    if k >= 2: e.w32(S['g_lock'], FAKE)
    e.pad(BTN['Z'], SX if k >= 10 else 0, 0)
    cx, cy = st['c']
    if k % 20 == 0:
        ang = math.degrees(math.atan2(py - cy, px - cx))
        d, ferr = math.hypot(px - cx, py - cy), ((e.rf(pl + HUMN_YAW) + 90) - (ang + 180) + 540) % 360 - 180
        print(f"{k:4d} dist={d:6.2f} angle={ang:7.1f} facing_err={ferr:6.1f}", flush=True)
        if k <= 160: st['samples'].append((ang, d, ferr))
    if k % 60 == 0: e.shot()
    if k == 600:
        a = [x[0] for x in st['samples']]
        swept = sum(abs((b - c + 180) % 360 - 180) for b, c in zip(a[1:], a))
        dev = max(abs(x[1] - R) for x in st['samples'])
        fe = max(abs(x[2]) for x in st['samples'])
        # (> 140 with the defaults: the game's frame time is counted from the CPU, so a cheaper patch makes 160 frames
        # less game time: 157 deg before 7ebf2da's cheaper ledge probe, 150 after, game dt 1.1 % smaller)
        check('orbits around the target', swept > (140 if (SX, R) == (80, 15.0) else 20), f'{swept:.0f} deg in 160 frames')
        check('radius stays flat', dev < 0.04 * R, f'max deviation {dev:.2f}')
        check('faces the target while orbiting', fe < 6, f'max facing error {fe:.1f}')
        e.stop()


e.run(script)
sys.exit(report())
