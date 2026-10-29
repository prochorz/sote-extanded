"""No ledge hang on a mover (Gall hangar hover platform). Riding along was tried and dropped
(user's video 2026-10-07: on Suprosa's machinery it dragged him through walls); left behind, he
hung in the air where it had been (video 2026-10-06). He may catch its rim, but lets go as
soon as it moves.

    M64CPU=0 python3 t_hang_plat.py <rom>
    env: DIRS=0,45,...  SHOTS=<dir>

gall_tp5.st; the platform is the object at PLAT (class tag at +0, position at +0x50, flying
along y at z 277.3). Dash is put on it and walks off at full tilt in each direction: no hang
on it may last more than 5 frames, and at least one must have ended by its move (why 11).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
WALK = 55                     # a walk: at a run (over 18/s) only an abyss is caught (RUN_SPEED)
e = Emu(sys.argv[1])
PLAT = 0x801b6850
DIRS = [int(v) for v in os.environ.get('DIRS', ','.join(str(a) for a in range(0, 360, 45))).split(',')]
H = S['g_hang']
st = {'i': 0, 'k0': None, 'rides': 0, 'bad': 0}


def ppos(): return [e.rf(PLAT + 0x50 + 4 * i) for i in range(3)]


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(DIRS):
            check('no lasting hang on the platform', st['bad'] == 0, f"{st['bad']} lasted")
            check('let go as it moved', st['rides'] > 0, f"{st['rides']} walk-offs with why 11")
            e.stop(); return
        e.load_state(os.path.join(paths.STATES, 'gall_tp5.st')); st.update(k0=n, t={}); return
    k = n - st['k0']; t = st['t']; a = DIRS[st['i']]
    if k == 2: inject(e)
    if k < 4: e.pad(0); return
    pl = e.r32(S['g_player']); e.wf(pl + 0xB4, 100.0)
    if k < 10:
        p = ppos()
        for i, v in enumerate((p[0], p[1], p[2] + 1.5)):
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
        e.pad(0); return
    if k < 20:
        e.pad(0); e.w32(S['g_hang_why'], 0); return
    k -= 20
    if e.r32(S['g_hang_state']) and e.r32(H + 176) == PLAT:
        t['h'] = t.get('h', 0) + 1
        if t['h'] == 6:
            t['g'] = 1; st['bad'] += 1; e.shot()
            print(f"dir {a}: HANG rim ({e.rf(H+52):.1f},{e.rf(H+56):.1f},{e.rf(H+60):.1f})", flush=True)
    else: t['h'] = 0
    if e.r32(S['g_hang_why']) == 11: t['m'] = 1
    e.pad(0, int(math.sin(math.radians(a)) * WALK), int(math.cos(math.radians(a)) * WALK))
    if k > 90:
        z = e.rf(pl + 0x58)
        print(f"dir {a}: {'hung on it' if 'g' in t else 'no hang on it'}, let go as it moved {bool(t.get('m'))}, end z {z:.1f}", flush=True)
        st['rides'] += bool(t.get('m')); st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
sys.exit(report())
