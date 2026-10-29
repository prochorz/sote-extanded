"""Clearing a gap with the ledge hang on: landing on the far side must never catch the near edge.

    M64CPU=0 python3 t_hang_gap.py <rom>
    env: DIRS=22,44

echo_catwalk.st, full tilt toward each direction (camera-relative): he runs off the catwalk end,
clears the gap and lands on the next block. The frame he touched down on the far rim used to
catch the edge of the floor he had left (its last floor point was still the near side) and
pull him back across the gap. Check: a catch after the landing holds a rim no closer to the
start than where he landed (catching the block he landed on, or its far side, is fine).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
DIRS = [int(v) for v in os.environ.get('DIRS', '22,44').split(',')]
st = {'i': 0, 'k0': None}
GROUND, AIR = 0x04000000, 0x08000000


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(DIRS): e.stop(); return
        e.load_state(os.path.join(paths.STATES, 'echo_catwalk.st'))
        st.update(k0=n, air=0, land=None, grab=None, p0=None); return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 6: e.pad(0); return
    a = DIRS[st['i']]
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    x, y, z = e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58)
    fl = e.r32(pl + 0x74)
    if st['p0'] is None: st['p0'] = (x, y)
    if fl & AIR: st['air'] = 1
    elif st['air'] and fl & GROUND and st['land'] is None and st['grab'] is None: st['land'] = (x, y, z)
    if e.r32(S['g_hang_state']) and st['grab'] is None:
        h = S['g_hang']
        st['grab'] = (e.rf(h + 52), e.rf(h + 56), e.rf(h + 60))
    if st['grab'] is None and k < 140:
        e.pad(0, int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80))
    else:
        e.pad(0)
    if k == 170:
        x0, y0 = st['p0']
        dist = lambda p: math.hypot(p[0] - x0, p[1] - y0)
        land, grab = st['land'], st['grab']
        fmt = lambda p: f'({p[0]:.1f},{p[1]:.1f},{p[2]:.1f})' if p else 'none'
        print(f'dir {a}: landed {fmt(land)}, caught rim {fmt(grab)}', flush=True)
        check(f'dir {a}: clears the gap and lands', land is not None)
        check(f'dir {a}: no catch back on the near side after landing',
              not (land and grab) or dist(grab) >= dist(land) - 1.0,
              f'rim {dist(grab):.1f} vs landing {dist(land):.1f} from the start' if land and grab else '')
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
sys.exit(report())
