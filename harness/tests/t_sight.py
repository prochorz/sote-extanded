"""Lock-on and walls (sup.st: the nearest troopers stand behind a wall).

    M64CPU=0 python3 t_sight.py <rom>

1. Z with line of sight skipped locks the trooper behind the wall; line of sight back on while Z
   is held: the lock drops after ~1 s out of sight (the reticle no longer hangs on a wall).
2. Z released; a fake target (g_test_target) is put behind the wall on the line from the camera
   eye through Dash, as far as the trooper. The chest ray hits the wall; the camera ray ends on
   Dash's own back, which used to count as "visible". A new Z press must not lock it.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import set_health
from testlib import FAKE, make_fake, place_fake, check, report

S = syms()
e = Emu(sys.argv[1])
CAM = 0x800D08A4
st = {'lock0': 0, 'drop': None, 'fake_lock': 0}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'sup.st'))
    if n == 62:
        inject(e)
        e.w32(S['g_test_skip_los'], 1)
    if n < 70: return
    k = n - 70
    pl, lk = e.r32(S['g_player']), e.r32(S['g_lock'])
    if pl: set_health(e, pl)
    b = BTN['Z'] if 10 <= k < 150 or 220 <= k < 260 else 0
    e.pad(b, 0, 0)
    if k == 30:
        st['lock0'] = lk
        e.w32(S['g_test_skip_los'], 0)
    if 30 < k < 150 and not lk and st['drop'] is None: st['drop'] = k - 30
    if k == 200 and st['lock0']:
        # Camera eye -> Dash, extended to the trooper's distance: behind the wall, past Dash.
        cam = e.r32(CAM)
        eye = [e.rf(cam + 0x44 + 4 * i) for i in range(3)]
        p = [e.rf(pl + 0x50 + 4 * i) for i in range(3)]
        p[2] += 3.0
        t = [e.rf(st['lock0'] + 0x50 + 4 * i) for i in range(3)]
        d = [p[i] - eye[i] for i in range(3)]
        dl = math.sqrt(sum(v * v for v in d))
        far = math.hypot(t[0] - p[0], t[1] - p[1])
        q = [p[i] + d[i] / dl * far for i in range(3)]
        make_fake(e, (q[0], q[1], q[2] - 1.0))
        e.w32(S['g_test_target'], FAKE)
        print(f"fake at ({q[0]:.0f},{q[1]:.0f},{q[2]:.0f}), {far:.0f} past Dash; trooper ({t[0]:.0f},{t[1]:.0f})", flush=True)
        e.shot()
    if 225 <= k < 260 and lk == FAKE: st['fake_lock'] = 1
    if k % 10 == 0:
        print(f"{k:4d} lock={tag(e.r32(lk)) if lk else '-'} bars={e.rf(S['g_bar_h']):.1f}", flush=True)
    if k in (30, 100, 240): e.shot()
    if k == 270:
        check('Z locks the trooper with line of sight skipped', st['lock0'] and tag(e.r32(st['lock0'])) != 'Humn')
        check('the lock drops ~1 s after line of sight is back on', st['drop'] is not None and st['drop'] < 80,
              f"after {st['drop']} frames")
        check('no lock through the wall past Dash', not st['fake_lock'])
        e.stop()


e.run(script)
sys.exit(report())
