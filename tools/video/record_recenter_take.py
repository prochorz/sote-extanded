#!/usr/bin/env python3
"""Record the idle camera recenter take for a video (Echo Base, states/play.st).

    cd harness && RES=960x720 SHOTS=recenter M64CPU=0 python3 ../tools/video/record_recenter_take.py <rom> recenter.json

Dash runs forward into the open (room behind the camera), turns and runs toward the camera (face visible), stops; ~1.5 s later the camera eases round behind
him. Then a short run to the side, stop, and the same again. Frames every 2nd video frame
(30 fps); JSON entries {t, x, y, b, label} for compose_takes.py.
"""
import json, os, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
# (start, end, x, y) in frames after the settle; labels follow the camera state below
MOVES = [(10, 120, 0, 80), (135, 185, 0, -80), (390, 440, 80, 0)]
END = 640
log, st = [], {'stop': None}


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'play.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    if k < 60: e.pad(0); return
    t = k - 60
    x = y = 0
    for a, b, sx, sy in MOVES:
        if a <= t < b: x, y = sx, sy
    if x or y: st['stop'] = None
    elif st['stop'] is None: st['stop'] = t
    facing = (e.rf(pl + 0x8C) + 270) % 360 - 180
    diff = abs((facing - e.rf(S['g_cam_facing']) + 180) % 360 - 180)
    if x or y:
        lab = {80: 'Run forward', -80: 'Run toward the camera: it stays, you see his face'}.get(y, 'Run sideways: the camera lags behind')
    elif st['stop'] is None or t < 20: lab = 'Stick released'
    else:
        idle = (t - st['stop']) / 60
        if diff < 3: lab = 'Camera behind Dash'
        elif idle < 1.5: lab = f'Standing still {idle:.1f} s'
        else: lab = 'Camera eases round behind him'
    e.pad(0, x, y)
    if t % 2 == 0:
        e.shot(); log.append(dict(t=t, x=x, y=y, b='', label=lab))
    if t >= END:
        json.dump(log, open(sys.argv[2], 'w')); print('frames', len(log)); e.stop()


e.run(script)
