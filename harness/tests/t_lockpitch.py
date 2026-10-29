"""Z on a target high above (or below) Dash tilts the camera toward it (play.st, a fake target).

    M64CPU=0 python3 t_lockpitch.py <rom>

Per case: reload, a fake target 20 units in front of Dash at height dz, Z held 90 frames.
Checked: the target ends up on screen, inside the view's vertical extent (camera forward/up
basis: |up/forward| < 0.8 tan of half the view); before, the camera kept level and a trooper on
a cliff top was off the top of the screen. Then Z released: the camera levels out again.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMN_YAW, CAM
from testlib import FAKE, make_fake, place_fake, check, report

S = syms()
e = Emu(sys.argv[1])
CASES = [18.0, -8.0]              # target heights above Dash's feet
DIST = 20.0
st = {'i': 0, 'base': 0}


def view(pt):
    cam = e.r32(CAM)
    d = [pt[i] - e.rf(cam + 0x44 + 4 * i) for i in range(3)]
    f = sum(d[i] * e.rf(cam + 0x24 + 4 * i) for i in range(3))
    u = sum(d[i] * e.rf(cam + 0x34 + 4 * i) for i in range(3))
    return f, u


def script(e, n):
    if st['i'] >= len(CASES):
        e.stop(); return
    dz = CASES[st['i']]
    if n == st['base'] + 60: e.load_state(os.path.join(paths.STATES, 'play.st'))
    if n == st['base'] + 62:
        inject(e); e.w32(S['g_test_skip_los'], 1); make_fake(e)
    if n < st['base'] + 66: return
    k = n - st['base'] - 66
    pl = e.r32(S['g_player'])
    if not pl: e.pad(0); return
    e.wf(pl + 0xB4, 100.0)
    if k == 0:
        f = math.radians(e.rf(pl + HUMN_YAW) + 90)
        st['t'] = (e.rf(pl + 0x50) + DIST * math.cos(f), e.rf(pl + 0x54) + DIST * math.sin(f), e.rf(pl + 0x58) + dz)
        place_fake(e, *st['t'])
        e.w32(S['g_test_target'], FAKE)
    c = (st['t'][0], st['t'][1], st['t'][2] + 0.6)
    e.pad(BTN['Z'] if k < 100 else 0)
    if k == 98:
        f, u = view(c)
        r = u / f if f > 0 else 9
        print(f'dz {dz:+.0f}: lock {e.r32(S["g_lock"]) == FAKE} pitch {e.rf(S["g_cam_pitch"]):.1f} up/fwd {r:.2f}', flush=True)
        check(f'target {dz:+.0f} up is on screen while locked', f > 0 and abs(r) < 0.8 * math.tan(math.radians(22)), f'up/forward {r:.2f}')
    if k == 180:
        p = e.rf(S['g_cam_pitch'])
        check(f'{dz:+.0f}: the camera levels out after Z', abs(p) < 1, f'pitch {p:.2f}')
        st.update(i=st['i'] + 1, base=n)


e.run(script)
sys.exit(report())
