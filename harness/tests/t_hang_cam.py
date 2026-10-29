"""Camera angle while hanging: catch the Echo Base crevasse edge from several directions and
shoot the hang with the camera turned g_hang_cam_off degrees off the wall normal.

    SHOTS=hangcam M64CPU=0 python3 t_hang_cam.py <rom>
    env: DIRS=0,90,180,270  OFFS=0,45,-45 (forced angles; default: the patch picks the side)  MAG=80

One shot per (direction, offset) 60 frames after the catch; prints the shot order, the side
picked and how far the game camera is (8 = full distance; less = pulled in by a wall).
"""
import math, os, sys
import _path
import paths
import m64
from m64 import Emu, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
state = os.path.join(paths.STATES, 'echo_crevasse.st')
DIRS = [int(v) for v in os.environ.get('DIRS', '0,90,180,270').split(',')]
FORCE = 'OFFS' in os.environ
OFFS = [float(v) for v in os.environ['OFFS'].split(',')] if FORCE else [None]
MAG = int(os.environ.get('MAG', '80'))
TRIALS = [(a, o) for a in DIRS for o in OFFS]
st = {'i': 0, 'k0': None, 'shot': 0}


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS): e.stop(); return
        e.load_state(state); st.update(k0=n, grab=None); return
    k = n - st['k0']
    a, o = TRIALS[st['i']]
    if k == 2: inject(e)
    if k >= 3 and FORCE: e.w32(S['g_hang_cam_force'], 1); e.wf(S['g_hang_cam_off'], o)
    if k < 6: e.pad(0); return
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    if e.r32(S['g_hang_state']) and st['grab'] is None: st['grab'] = k
    if st['grab'] is None:
        e.pad(0, int(math.sin(math.radians(a)) * MAG), int(math.cos(math.radians(a)) * MAG))
    else:
        e.pad(0)
        if k == st['grab'] + 60:
            st['shot'] += 1
            cam = e.r32(0x800D08A4)
            d = [e.rf(cam + 0x44 + 4 * i) - e.rf(pl + 0x50 + 4 * i) for i in range(3)]
            print(f"shot {st['shot']:03d}: dir {a} off {e.rf(S['g_hang_cam_off']):+.0f} cam dist {math.hypot(d[0], d[1]):.1f}"
                  f" up {d[2]:.1f} yaw {math.degrees(math.atan2(d[1], d[0])):.0f}", flush=True); e.shot()
    if k == 260 or (st['grab'] is not None and k > st['grab'] + 62):
        if st['grab'] is None: print(f"dir {a}: no catch", flush=True)
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
