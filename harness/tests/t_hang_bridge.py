"""Ledge hang on the Echo Base truss bridge (user's video, 2026-10-06: he hung among the girders,
hid behind them, caught a thin pipe, the camera ended under the deck).

    M64CPU=0 python3 t_hang_bridge.py <rom>
    env: YS=-96,-88,-80,-72  DIRS=0,30,...  SHOTS=<dir>

Dash is put on the deck (x 136, the bridge runs along y) and walks off at full tilt. Every catch
is printed with g_hang_gap (-1 = a free hang under the deck) and a shot 40 frames later; every
miss with g_hang_why. FAIL: a free hang (gap -1) on the bridge.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
YS = [float(v) for v in os.environ.get('YS', '-96,-88,-80,-72').split(',')]
DIRS = [int(v) for v in os.environ.get('DIRS', ','.join(str(a) for a in range(0, 360, 30))).split(',')]
TRIALS = [(y, a) for y in YS for a in DIRS]
H = S['g_hang']
st = {'i': 0, 'k0': None, 'free': 0, 'n': 0}


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS):
            print(f"catches {st['n']}, free hangs {st['free']}", flush=True)
            check('no free hang on the bridge', st['free'] == 0, f"{st['free']}")
            e.stop(); return
        e.load_state(os.path.join(paths.STATES, 'echo_catwalk.st')); st.update(k0=n, grab=None); return
    k = n - st['k0']
    y0, a = TRIALS[st['i']]
    if k == 2: inject(e)
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    if k < 8:
        for i, v in enumerate((136.0, y0, 4.0)):
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
    if k < 30: e.pad(0); return
    if e.r32(S['g_hang_state']) and st['grab'] is None:
        st['grab'] = k; gap = e.rf(S['g_hang_gap'])
        st['n'] += 1; st['free'] += gap < 0
        print(f"y {y0} dir {a}: CATCH gap {gap:.2f} rim ({e.rf(H+52):.1f},{e.rf(H+56):.1f},{e.rf(H+104):.1f}) in ({e.rf(H+64):.2f},{e.rf(H+68):.2f}) hang ({e.rf(H+32):.1f},{e.rf(H+36):.1f},{e.rf(H+40):.1f})", flush=True)
    if st['grab'] is not None:
        e.pad(0)
        if k == st['grab'] + 40: e.shot()
        if k >= st['grab'] + 42: st['i'] += 1; st['k0'] = None
        return
    e.pad(0, int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80))
    if k >= 150:
        print(f"y {y0} dir {a}: no catch, why {e.r32(S['g_hang_why'])} z {e.rf(pl+0x58):.1f}", flush=True)
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
sys.exit(report())
