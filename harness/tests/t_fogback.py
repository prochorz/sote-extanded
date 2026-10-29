"""Lock on a target behind the camera, in fog (default echo_catwalk.st): Dash runs toward the camera, presses Z.

    M64CPU=0 python3 t_fogback.py <rom> [state]

A fake target is kept d units behind Dash's back as seen from the camera, i.e. past the camera.
Its view depth is negative so it looks fog-free, but once locked the camera turns round and it
sits deep in fog. Expected: no lock at all where the locked fog would exceed the lock threshold,
and a lock that is kept where it doesn't. `locked fog` is the amount after the camera turns.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import CAM
from testlib import FAKE, make_fake, place_fake, fog_expected, check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'echo_catwalk.st')
LOCK_FOG = 0.9                   # src/lock.c: no new lock on a target fogged more than this once locked
DISTS = [30, 50, 70, 90, 110]
seen = {}


def setup(e):
    inject(e); e.w32(S['g_test_skip_los'], 1)
    make_fake(e)
    e.w32(S['g_test_target'], FAKE)


def script(e, n):
    if n < 60: return
    k = n - 60
    i, ph = k // 120, k % 120
    if i >= len(DISTS): e.stop(); return
    if ph == 0: e.load_state(state); return
    if ph == 2: setup(e)
    if ph < 5: return
    d = DISTS[i]
    pl, cam = e.r32(S['g_player']), e.r32(CAM)
    if not pl or not cam: e.pad(0); return
    p = [e.rf(pl + 0x50 + 4 * j) for j in range(3)]
    eye = [e.rf(cam + 0x44 + 4 * j) for j in range(3)]
    bx, by = eye[0] - p[0], eye[1] - p[1]
    back = math.hypot(bx, by)
    if ph < 70:   # keep the target past the camera until the camera has turned
        place_fake(e, p[0] + bx / back * d, p[1] + by / back * d, p[2])
    # 5-30: run toward the camera; 30-100: hold Z (stick still); 100+: release
    e.pad(BTN['Z'] if 30 <= ph < 100 else 0, 0, -80 if ph < 30 else 0)
    lk = e.r32(S['g_lock']) == FAKE
    if ph == 34: seen['early'] = lk; seen['fog'] = fog_expected(e, d + back)
    if ph == 98:
        print(f"d={d:4d} locked fog={seen['fog']:.2f} at Z: {'lock' if seen['early'] else 'none'}"
              f"  after turn: {'kept' if lk else 'none'}", flush=True)
        fog = seen['fog']
        if abs(fog - LOCK_FOG) > 0.05:
            want = fog < LOCK_FOG
            check(f'd={d}: {"lock, kept after the turn" if want else "no lock"} at locked fog {fog:.2f}',
                  seen['early'] == want and lk == want)


e.run(script)
sys.exit(report())
