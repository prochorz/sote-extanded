"""Ord Mantell train: Z locks onto a droid riding the cars (class TTrp), and the laser kills it.

    M64CPU=0 python3 t_traindroid.py <rom>

states/om_ttrp.st is om_drones.st after one debug-menu Teleport: a live TTrp stands ~12 units
from Dash. TTrp (like the drones TGun and targets TTar) is not in the game's target pool; only
its class array has it. Dash is turned to face the nearest live droid, then Z (line of sight on)
and B. Invincibility is on (debug cheat flag 0x800E1B2C): the droids shoot back.
"""
import math, os, struct, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMT_YAW
from testlib import check, report
S = syms()
e = Emu(sys.argv[1])
PL = 0x801A7AF4
TTRP = 0x80112FB8                  # class record on the train level
st = {'lock': 0, 'droid': 0}


def droids(e):
    cnt, size, o = e.r32(TTRP + 8), e.r32(TTRP + 12), e.r32(TTRP + 16)
    for i in range(cnt):
        a = o + i * size
        if e.r32(a) == e.r32(TTRP) and e.rf(a + 0x60) > 0: yield a


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'om_ttrp.st'))
    if n == 62: inject(e)
    if n < 66: return
    t = n - 66
    e.w32(0x800E1B2C, 1)
    px, py = e.rf(PL + 0x50), e.rf(PL + 0x54)
    if t == 20:
        d = min(droids(e), key=lambda a: math.hypot(e.rf(a + 0x50) - px, e.rf(a + 0x54) - py))
        st['droid'] = d
        ang = math.degrees(math.atan2(e.rf(d + 0x54) - py, e.rf(d + 0x50) - px))
        e.wf(PL + HUMT_YAW, ang - 90)
        print(f"droid {d:08x} at {math.hypot(e.rf(d + 0x50) - px, e.rf(d + 0x54) - py):.1f}, bearing {ang:.0f}", flush=True)
    b = BTN['Z'] if 30 <= t < 200 else 0
    if 60 <= t < 200 and (t // 6) % 2 == 0: b |= BTN['B']
    e.pad(b, 0, 0)
    d = st['droid']
    if t == 40: st['lock'] = e.r32(S['g_lock'])
    if d and t % 20 == 0:
        print(f"{t:4d} lock={e.r32(S['g_lock']):08x} droid hp={e.rf(d + 0x60):.2f}", flush=True)
    if t == 200:
        check('Z locks the droid', st['lock'] == d, f"lock {st['lock']:08x}, droid {d:08x}")
        check('the laser kills it', not e.rf(d + 0x60) > 0, f"hp {e.rf(d + 0x60):.2f}")
        e.stop()


e.run(script)
sys.exit(report())
