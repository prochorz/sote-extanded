"""Gravity cheat vs the ledge hang's flight prediction (will_land assumes gravity 30).

    M64CPU=0 [PAYLOAD_BUILD=...] python3 t_issue_grav.py <rom>
    env: GRAVS=1,0.5,0.3  DIRS=22,44

echo_catwalk.st: full tilt toward 22/44 degrees crosses the gap to the next block (at gravity 1).
Sets the Gravity multiplier (0x800E0DC4, the cheat's variable), runs, and prints per trial:
caught the edge or not, where he is 150 frames later. Run once with the normal build and once
with a --without hang build: the same trial should end on the same block.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1])
GRAVS = [float(v) for v in os.environ.get('GRAVS', '1,0.5,0.3').split(',')]
DIRS = [int(v) for v in os.environ.get('DIRS', '22,44').split(',')]
TRIALS = [(g, a) for g in GRAVS for a in DIRS]
GRAVITY = 0x800E0DC4
st = {'i': 0, 'k0': None}


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS): e.stop(); return
        e.load_state(os.path.join(paths.STATES, 'echo_catwalk.st')); st.update(k0=n, grab=None, zmin=1e9); return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 6: e.pad(0); return
    g, a = TRIALS[st['i']]
    if k == 6: print(f'default gravity {e.rf(GRAVITY):.3f} jump {e.rf(0x800E0DC0):.3f}', flush=True)
    if g > 0: e.wf(GRAVITY, g)
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    x, y, z = e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58)
    st['zmin'] = min(st['zmin'], z)
    if os.environ.get('TRACE') and 30 <= k <= 75 and k % 3 == 0: print(f'  k{k} ({x:.1f},{y:.1f},{z:.2f}) fl {e.r32(pl + 0x74):08x}', flush=True)
    if k == 6: st['p0'] = (x, y, z)
    if 'g_hang_state' in S and e.r32(S['g_hang_state']) and st['grab'] is None and k > 8:
        st['grab'] = k
        Hs = S['g_hang']; print(f'  GRAB k{k} rim ({e.rf(Hs + 52):.1f},{e.rf(Hs + 56):.1f},{e.rf(Hs + 60):.1f})', flush=True)
        e.shot()
    e.pad(0, int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80)) if k < 140 and st['grab'] is None else e.pad(0)
    if k == 160:
        x0, y0, z0 = st['p0']
        print(f"TRIAL gravity {g:.2f} dir {a:3d}: {'CAUGHT EDGE at k=' + str(st['grab']) if st['grab'] else 'no catch':18s}"
              f" end ({x:.1f},{y:.1f},{z:.1f}) dz {z - z0:+.1f} moved {math.hypot(x - x0, y - y0):.1f} zmin {st['zmin'] - z0:+.1f}", flush=True)
        e.shot()
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
