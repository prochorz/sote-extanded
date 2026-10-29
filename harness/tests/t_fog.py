"""Fog-limited lock: a fake target placed ever further along the camera axis (play.st).

    M64CPU=0 python3 t_fog.py <rom> [state]

For each distance the lock is forced onto the fake target; the payload must drop it once the
fog hides more than 97% of it. `fog` is the expected amount from the level's fog globals and
perspective (same formula as the payload).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import CAM
from testlib import FAKE, make_fake, place_fake, fog_expected, check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'play.st')
BREAK = 0.97                     # LOCK_FOG_BREAK in src/lock.c
DISTS = [20, 60, 90, 110, 130, 150, 170, 190]


def script(e, n):
    if n == 60: e.load_state(state)
    if n == 62:
        inject(e); e.w32(S['g_test_skip_los'], 1)
        make_fake(e)
        print('fog depth', e.r16(0x800E7AD8), e.r16(0x800E7ADC), 'persp', [round(e.rf(0x80192F14 + 4 * i), 2) for i in range(4)], flush=True)
    if n < 70: return
    k = n - 70
    i, ph = k // 30, k % 30
    if i >= len(DISTS): e.stop(); return
    cam = e.r32(CAM)
    eye = [e.rf(cam + 0x44 + 4 * j) for j in range(3)]
    fw = [e.rf(cam + 0x24 + 4 * j) for j in range(3)]
    d = DISTS[i]
    # target centre = pos + z 0.6, put it d along the view axis
    place_fake(e, *(eye[j] + fw[j] * d - (0.6 if j == 2 else 0) for j in range(3)))
    e.pad(BTN['Z'])
    if ph == 5: e.w32(S['g_lock'], FAKE)       # after the Z press has been decoded
    if ph == 25:
        pl = e.r32(S['g_player'])
        fog, kept = fog_expected(e, d), bool(e.r32(S['g_lock']))
        print(f"player={tag(e.r32(pl)) if pl else '-'} d={d:4d} fog={fog:.2f} lock={'kept' if kept else 'dropped'}", flush=True)
        if abs(fog - BREAK) > 0.03:
            check(f'd={d}: lock {"kept" if fog < BREAK else "dropped"} at fog {fog:.2f}', kept == (fog < BREAK))


e.run(script)
sys.exit(report())
