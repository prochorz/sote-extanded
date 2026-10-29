"""Ord Mantell train: Z while Dash faces the camera swings the view round behind him (states/om.st).

    M64CPU=0 python3 t_trainz.py <rom>

Dash runs toward the camera (toward the back of the train), steps sideways, then Z with nothing
to lock swings the lazy camera round to his back (~130 deg here). The train
camera looks at a point one unit ahead of Dash along the facing row of his camera matrix
(HumT +0x11C); the patch must keep that row on the lazy camera's angle. Left on world +y it put
the point behind the eye after the swing: the view faced away from Dash, into the canyon wall,
for seconds. Prints the angle between the view and the eye->Dash line (`off`): expect it back
under a few degrees within ~1 s of the press, and the eye behind Dash's back.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import CAM, HUMT_YAW
from testlib import check, report
S = syms()
e = Emu(sys.argv[1])
PL = 0x801A7AF4
Z_AT = 392
st = {'off': {}}
def w(a): return (a + 180) % 360 - 180
def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'om.st'))
    if n == 62: inject(e)
    if n < 66: return
    t = n - 66
    sy = -80 if 300 <= t < 360 else 0          # turn round and run toward the camera
    sx = -80 if 380 <= t < Z_AT else 0         # a few steps sideways, as in the user's clip
    e.pad(BTN['Z'] if Z_AT <= t < Z_AT + 40 else 0, sx, sy)
    if t >= 290:
        c = e.r32(CAM)
        ex, ey = e.rf(c + 0x44), e.rf(c + 0x48)
        px, py = e.rf(PL + 0x50), e.rf(PL + 0x54)
        to_dash = math.degrees(math.atan2(py - ey, px - ex))
        view = math.degrees(math.atan2(e.rf(c + 0x28), e.rf(c + 0x24)))
        face = e.rf(PL + HUMT_YAW) + 90
        st['off'][t] = w(to_dash - view)
        if t % 10 == 0:
            print(f"{t:4d} face={w(face):7.1f} gcam={e.rf(S['g_cam_facing']):7.1f} eye->dash={to_dash:7.1f}"
                  f" view={view:7.1f} off={st['off'][t]:6.1f}", flush=True)
        if t == 375: st['face0'], st['view0'] = face, view
        if t == 560: st['face1'], st['view1'], st['dash1'] = face, view, to_dash
    if t == 560:
        off = st['off']
        late = max(abs(off[k]) for k in off if k >= Z_AT + 60)
        check('Dash faced the camera before Z', abs(w(st['face0'] - st['view0'])) > 150,
              f"face {w(st['face0']):.0f} view {st['view0']:.0f}")
        check('the view swung round', abs(w(st['view1'] - st['view0'])) > 120,
              f"view {st['view0']:.0f} -> {st['view1']:.0f}")
        check('view stays on Dash during the swing', max(abs(v) for v in off.values()) < 50,
              f'max |off| {max(abs(v) for v in off.values()):.1f}')
        check('view settles on Dash', late < 6, f'max |off| from 1 s after Z {late:.1f}')
        check('camera ends behind his back', abs(w(st['dash1'] - st['face1'])) < 10,
              f"eye->dash {st['dash1']:.0f} face {w(st['face1']):.0f}")
        e.stop()
e.run(script)
sys.exit(report())
