"""Where the ledge hang puts Dash: walk off edges from several states in many directions and
check every catch against the cliff it hangs on.

    M64CPU=0 python3 t_hang_spots.py <rom>
    env: STATES=echo_crevasse.st,echo_catwalk.st,echo_gapblock.st  DIRS=0,15,...  MAGS=80,50

Per catch: gap = the cliff face from the hang point toward the wall, 1 under the rim
(g_hang_gap; should be about HANG_OUT 1.55; -1 = none, a thin floor such as a bridge deck),
moved = how far he is carried from where he was when the catch started (horizontal).
A shot is taken 40 frames after each catch (SHOTS=<dir>). FAIL when the gap is off by more
than 0.5 or he is carried more than 6 units; also FAIL with fewer than MIN_CATCHES (55) catches.
The count moves with frame timing (55-61 seen): a slightly different path walks off next to
girders or a shaft, where the catch is refused on purpose.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
STATES = os.environ.get('STATES', 'echo_crevasse.st,echo_catwalk.st,echo_gapblock.st').split(',')
DIRS = [int(v) for v in os.environ.get('DIRS', ','.join(str(a) for a in range(0, 360, 15))).split(',')]
MAGS = [int(v) for v in os.environ.get('MAGS', '80,50').split(',')]
TRIALS = [(s, a, m) for s in STATES for m in MAGS for a in DIRS]
H = S['g_hang']          # struct hang_state: pos +32, face +52, edge +104
st = {'i': 0, 'k0': None, 'fail': 0, 'n': 0}


def hf(off): return e.rf(H + off)


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS):
            print(f"catches {st['n']}, FAIL {st['fail']}", flush=True)
            check('enough catches', st['n'] >= int(os.environ.get('MIN_CATCHES', '55')), f"{st['n']}")
            e.stop(); return
        e.load_state(os.path.join(paths.STATES, TRIALS[st['i']][0])); st.update(k0=n, grab=None); return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 6: e.pad(0); return
    sname, a, m = TRIALS[st['i']]
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    x, y, z = e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58)
    # k >= 12: the state load is done (the previous trial ended while hanging)
    if k >= 12 and e.r32(S['g_hang_state']) and st['grab'] is None:
        st['grab'] = k
        gap = e.rf(S['g_hang_gap']); moved = math.hypot(hf(32) - x, hf(36) - y)
        bad = (gap >= 0 and abs(gap - 1.55) > 0.5) or moved > 6
        st['n'] += 1; st['fail'] += bad
        check(f"{sname} dir {a} stick {m}: on the cliff, near where he went over", not bad,
              f"at ({x:.1f},{y:.1f},{z:.1f}) rim ({hf(52):.1f},{hf(56):.1f},{hf(104):.1f}) hang ({hf(32):.1f},{hf(36):.1f})"
              f" gap {gap:.2f} moved {moved:.1f}")
    if st['grab'] is not None:
        e.pad(0)
        if k == st['grab'] + 40: e.shot()
    else:
        e.pad(0, int(math.sin(math.radians(a)) * m), int(math.cos(math.radians(a)) * m))
    if k >= (st['grab'] + 42 if st['grab'] is not None else 220):
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
sys.exit(report())
