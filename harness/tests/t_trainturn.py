"""Ord Mantell train: the lazy camera through the first bend of the track (states/om.st).

    M64CPU=0 python3 t_trainturn.py <rom>            # stand still through the bend
    BACK=1 M64CPU=0 python3 t_trainturn.py <rom>     # run toward the camera in three bursts

Prints angles relative to the axis of the car under Dash. Expect gcam-car and eyedir-car to stay
within a few degrees of 0 while `car` swings 88 -> 123 -> 87, and facing-car to be 180 while
running back (Dash faces the camera); in the 120-frame pause after a burst the camera eases
round behind him (idle recenter, ~1.5 s), so the next burst starts from behind. Dash runs off the back of the car in the second burst and
respawns at ~900: that is the level, not the patch. Standing still, something knocks him about
at ~1080 (the camera swings); the checks cover the bend before that (360-1050).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import CAM, TRAIN_CARS as TRAI, HUMT_YAW
from testlib import check, report
S = syms()
e = Emu(sys.argv[1])
PL = 0x801A7AF4
BACK = os.environ.get('BACK')
rows = []
def car_axis(e):
    n, size, o = e.r32(TRAI + 8), e.r32(TRAI + 12), e.r32(TRAI + 16)
    px, py = e.rf(PL + 0x50), e.rf(PL + 0x54)
    best, ax = 1e9, None
    for i in range(n):
        a = o + i * size
        dx, dy = e.rf(a + 0x50) - px, e.rf(a + 0x54) - py
        if dx*dx + dy*dy < best: best, ax = dx*dx + dy*dy, math.degrees(math.atan2(e.rf(a + 0x34), e.rf(a + 0x30)))
    return ax
def w(a): return (a + 180) % 360 - 180
def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'om.st'))
    if n == 62: inject(e)
    if n < 66: return
    t = n - 66
    sy = -80 if BACK and (450 <= t < 530 or 650 <= t < 730 or 1000 <= t < 1080) else 0
    e.pad(0, 0, sy)
    if t % 30 == 0 and t >= 360:
        c = e.r32(CAM)
        ex, ey = e.rf(c+0x44), e.rf(c+0x48)
        px, py = e.rf(PL+0x50), e.rf(PL+0x54)
        ax = car_axis(e)
        eyedir = math.degrees(math.atan2(py-ey, px-ex))
        gc, ed = w(e.rf(S['g_cam_facing']) - ax), w(eyedir - ax)
        print(f"{t:5d} sy={sy} car={ax:7.1f} facing-car={w((e.rf(PL + HUMT_YAW) + 90) - ax):7.1f} gcam-car={gc:7.1f} eyedir-car={ed:7.1f} fl={e.r32(PL+0x74):08x}", flush=True)
        if t <= 1050: rows.append((ax, gc, ed))
    if t in (480, 520, 700, 1050, 1200): e.shot()
    if t == 1250:
        if not BACK:
            cars = [r[0] for r in rows]
            gmax, emax = max(abs(r[1]) for r in rows), max(abs(r[2]) for r in rows)
            check('the track bends', max(cars) - min(cars) > 25, f'car axis {min(cars):.0f} .. {max(cars):.0f}')
            check('lazy camera turns with the car', gmax < 1, f'max |gcam-car| {gmax:.1f}')
            check('real camera stays behind along the car', emax < 5, f'max |eyedir-car| {emax:.1f}')
        else:
            check('ran through the bursts', len(rows) > 20)
        e.stop()
e.run(script)
sys.exit(report())
