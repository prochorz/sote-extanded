#!/usr/bin/env python3
"""Record the crate takes: Z lock-on and the crates in the Echo Base part 2 corridor
(states/echo_cave.st, the corridor west of the sentry turret).

    cd harness && RES=960x720 SHOTS=crateA M64CPU=0 python3 ../tools/video/record_crate_takes.py <rom> A crateA.json
    take A: a trooper stands behind the crate stack; Dash walks up the corridor and holds Z: no lock
    take B: the same trooper in front of the crates: Z locks him

Dash is moved to the corridor by position writes (2 units a frame, unrecorded), the trooper next
to him at the start of the state is pinned at the take's spot every frame. JSON entries
{t, x, y, b, label, lock} for compose_takes.py.
"""
import json, math, os, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, HERE, BTN
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
TAKE = sys.argv[2]
TROOPER = 0x801c5ad4
SPOT = {'A': (-233.0, 42.0), 'B': (-228.0, 22.0)}[TAKE]
PATH = [(-130, 25), (-165, 45), (-197, 60), (-213, 60), (-213, 45), (-213, 30), (-230, 30), (-234, 6)]
log, st = [], {'i': 0, 'w': 0, 't0': None}


def pin(o, x, y):
    for b in (0x08, 0x50): e.wf(o + b, x); e.wf(o + b + 4, y)


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_cave.st'))
    if n == 62: inject(e)
    if n < 66: return
    pl = e.r32(S['g_player'])
    if not pl: e.pad(0); return
    e.wf(pl + 0xB4, 100.0); e.wf(pl + 0xE4, 1000.0)   # invincibility timer: no hit flashes
    pin(TROOPER, *SPOT); e.wf(TROOPER + 0x58, -51.0)
    px, py = e.rf(pl + 0x50), e.rf(pl + 0x54)
    if st['i'] < len(PATH):
        tx, ty = PATH[st['i']]
        d = math.hypot(tx - px, ty - py); st['w'] += 1
        if d < 2.5 or st['w'] > 120: st['i'] += 1; st['w'] = 0
        else: pin(pl, px + (tx - px) / d * 2, py + (ty - py) / d * 2)
        e.pad(0); return
    if st['t0'] is None:
        st['t0'] = n
        e.wf(pl + 0x8C, 0.0); e.wf(pl + 0x14, 0.0)          # facing north, up the corridor
    k = n - st['t0']
    if k < 120: e.pad(0); return                           # camera settles behind him
    t = k - 120
    x = y = 0; b = ''
    cam = e.rf(S['g_cam_facing'])
    if t < 14:
        a = math.radians(90 - cam); x, y = int(-math.sin(a) * 80), int(math.cos(a) * 80)
        lab = 'Up the corridor, toward the crates' if TAKE == 'A' else 'Up the corridor'
    elif t < 50: lab = 'Trooper hidden behind the crates' if TAKE == 'A' else 'Trooper in plain sight'
    elif t < 150:
        b = 'Z'
        lab = 'Z: no lock through the crates' if TAKE == 'A' else 'Z: locked on'
    else: lab = 'Z released'
    e.pad(BTN['Z'] if b else 0, x, y)
    lock = e.r32(S['g_lock'])
    if t % 2 == 0:
        e.shot(); log.append(dict(t=t, x=x, y=y, b=b, label=lab, lock=1 if lock else 0))
    if t == 100: print('lock', hex(lock), 'dash', round(px, 1), round(py, 1), flush=True)
    if t >= 180:
        json.dump(log, open(sys.argv[3], 'w')); print('frames', len(log)); e.stop()


e.run(script)
