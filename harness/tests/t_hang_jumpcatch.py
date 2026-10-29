"""Jump catches in the Gall canyon (user's videos, 2026-10-06: he caught rounded rock tops and
slopes in a jump and hung with his feet on the slope below).

    M64CPU=0 python3 t_hang_jumpcatch.py <rom>
    env: STATES=gall_tp5.st,gall_tp6.st  DIRS=0,30,...  JUMPS=5,15,30  SHOTS=<dir>

Runs at full tilt, presses A at frame JUMP, and prints every catch made in the jump with the
face (g_hang_gap) and the floor under his feet; a shot 30 frames after it. FAIL: a jump catch
with no face or with floor within 1.5 under his feet.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
STATES = os.environ.get('STATES', 'gall_tp5.st,gall_tp6.st').split(',')
DIRS = [int(v) for v in os.environ.get('DIRS', ','.join(str(a) for a in range(0, 360, 30))).split(',')]
JUMPS = [int(v) for v in os.environ.get('JUMPS', '5,15,30').split(',')]
TRIALS = [(sn, a, jf) for sn in STATES for jf in JUMPS for a in DIRS]
H = S['g_hang']
st = {'i': 0, 'k0': None, 'n': 0, 'bad': 0}


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS):
            print(f"jump catches {st['n']}, bad {st['bad']}", flush=True)
            check('jump catches only on sheer walls with room under him', st['bad'] == 0, f"{st['bad']} of {st['n']}")
            e.stop(); return
        e.load_state(os.path.join(paths.STATES, TRIALS[st['i']][0])); st.update(k0=n, t={}); return
    k = n - st['k0']
    t = st['t']
    sn, a, jf = TRIALS[st['i']]
    if k == 2: inject(e)
    if k < 6: e.pad(0); return
    k -= 6
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    if e.r32(S['g_hang_state']) and 'grab' not in t:
        t['grab'] = k
        jumped = e.r32(H + 16)
        if jumped:
            gap = e.rf(S['g_hang_gap'])
            st['n'] += 1
            print(f"{sn} dir {a} A@{jf}: JUMP CATCH k{k} gap {gap:.2f} rim ({e.rf(H+52):.1f},{e.rf(H+56):.1f},{e.rf(H+104):.1f})", flush=True)
            t['jc'] = 1
        else:
            print(f"{sn} dir {a} A@{jf}: walk-off catch k{k}", flush=True)
    if 'grab' in t:
        e.pad(0)
        if k == t['grab'] + 30:
            if t.get('jc'): e.shot()
            st['i'] += 1; st['k0'] = None
        return
    b = BTN['A'] if jf <= k < jf + 4 else 0
    e.pad(b, int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80))
    if k >= 90: st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
sys.exit(report())
