#!/usr/bin/env python3
"""Record the Xizor's palace gladiator takes (new build only).

    cd harness && RES=960x720 SHOTS=<dir> M64CPU=0 python3 ../tools/video/record_boss_takes.py <rom> A|B <out.json>
    A: walking phase (xiz_glad.st; his fight is started by writing his AI state +0x584 = 3,
       nothing else in the harness starts it): Z locks his body, circle, fire
    B: flying phase (xiz_glad2.st, after "Jetpack Malfunction"): Dash on a wall of the maze,
       troopers below; Z locks the flying gladiator, fire
Frames every 2nd video frame (30 fps); JSON {t, x, y, b, label, lock} per saved frame.
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
TAKE = sys.argv[2]
G = 0x8019F4C4
log = []


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'xiz_glad.st' if TAKE == 'A' else 'xiz_glad2.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0); e.w32(0x800E1B2C, 1)
    if TAKE == 'A':
        if k < 30:
            for off in (0x50, 0x08):
                for i, v in enumerate((-5.0, 0.0, 124.0)): e.wf(pl + off + 4 * i, v)
        if k == 40: e.w32(G + 0x584, 3)
        t = k - 200
    else:
        t = k - 20
    if t < 0: e.pad(0); return
    x = y = 0; b = ''
    if TAKE == 'A':
        if t < 100: lab = 'The gladiator droid comes out'
        elif t < 160: b = 'Z'; lab = 'Z: lock on his body'
        elif t < 260: b = 'Z'; x = 80; lab = 'Stick sideways: circle around him'
        else: b = 'Z'; lab = 'B: the laser flies into the lock'
        end = 400
    else:
        if t < 40: lab = 'Second phase: he flies, troopers below'
        elif t < 120: b = 'Z'; lab = 'Z: lock on him, not the troopers'
        else: b = 'Z'; lab = 'B: the laser flies into the lock'
        end = 300
    if b == 'Z' and t >= (260 if TAKE == 'A' else 120) and t % 8 < 3: b = 'ZB'
    e.pad((0x20 if 'Z' in b else 0) | (0x40 if 'B' in b else 0), x, y)
    if t % 2 == 0:
        lk = e.r32(S['g_lock'])
        e.shot(); log.append(dict(t=t, x=x, y=y, b=b, label=lab, lock=1 if lk == G else 0))
        if t % 30 == 0: print(t, 'lock', hex(lk), 'hp', round(e.rf(G + 0x5C4)), flush=True)
    if t >= end:
        json.dump(log, open(sys.argv[3], 'w')); print('frames', len(log)); e.stop()


e.run(script)
