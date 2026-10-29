#!/usr/bin/env python3
"""Record the Ord Mantell train takes (Z camera, droid lock-on, Z without turning Dash).

    cd harness && RES=960x720 SHOTS=trainA M64CPU=0 python3 ../tools/video/record_train_takes.py <rom> A trainA.json
    take A (om.st): run toward the camera, step aside, Z: the camera swings round to his back
    take B (om_ttrp.st): face a droid riding the cars (TTrp), Z locks it, B kills it, the lock moves on
    take C (om.st): turn Dash across the car, Z: he keeps his facing (runs off the car after: not used)

Frames every 2nd video frame (30 fps) into local/run/shots/<SHOTS>/; JSON entries
{t, x, y, b, label, lock} for compose_takes.py. GLideN64 (local/bin).
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
PL = 0x801A7AF4
TTRP = 0x80112FB8
STATE = {'A': 'om.st', 'B': 'om_ttrp.st', 'C': 'om.st'}[TAKE]
START, END = {'A': (280, 560), 'B': (40, 300), 'C': (280, 520)}[TAKE]
log = []
st = {'droid': 0}


def nearest_droid(e):
    px, py = e.rf(PL + 0x50), e.rf(PL + 0x54)
    cnt, size, o = e.r32(TTRP + 8), e.r32(TTRP + 12), e.r32(TTRP + 16)
    live = [o + i * size for i in range(cnt) if e.r32(o + i * size) == e.r32(TTRP) and e.rf(o + i * size + 0x60) > 0]
    return min(live, key=lambda a: math.hypot(e.rf(a + 0x50) - px, e.rf(a + 0x54) - py))


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, STATE))
    if n == 62: inject(e)
    if n < 66: return
    t = n - 66
    e.wf(PL + 0xC0, 100.0)
    e.w32(0x800E1B2C, 0)                          # the states carry debug Invincibility: hide its icon
    x = y = 0; b = ''; lab = ''
    if TAKE == 'A':
        if 300 <= t < 360: y = -80; lab = 'Run toward the camera (to the rear of the train)'
        elif t < 380: lab = 'Dash faces the camera'
        elif t < 392: x = -80; lab = 'A few steps aside'
        elif t < 432: b = 'Z'; lab = 'Z: the camera swings round behind him'
        else: lab = 'Dash keeps his facing (no auto-turn); he stays in view'
    elif TAKE == 'B':
        if t == 5:
            d = nearest_droid(e)
            px, py = e.rf(PL + 0x50), e.rf(PL + 0x54)
            e.wf(PL + 0x90, math.degrees(math.atan2(e.rf(d + 0x54) - py, e.rf(d + 0x50) - px)) - 90)
            st['droid'] = d
        if t < 100: lab = 'A droid stands on the car ahead'
        else:
            b = 'Z'
            if 130 <= t < 280 and (t // 6) % 2 == 0: b = 'ZB'
            lk = e.r32(S['g_lock'])
            what = {0x5447756E: 'a drone', 0x54547270: 'a droid on the car ahead', 0x54546172: 'a target'}.get(e.r32(lk) if lk else 0, '')
            lab = ('Z: locked on ' + what) if what else 'Z'
            if t >= 130: lab += ', fire (B)'
            if not e.rf(st['droid'] + 0x60) > 0: lab = 'Droid down. ' + lab
    elif TAKE == 'C':
        if 300 <= t < 312: x = 80; lab = 'Turn Dash across the car'
        elif t < 360: lab = 'Dash faces the side of the car'
        elif t < 400: b = 'Z'; lab = 'Z: Dash keeps his facing, the camera goes behind'
        elif t < 470: y = 80; lab = 'Stick forward: run where he faces'
        else: lab = ''
    btn = (BTN['Z'] if 'Z' in b else 0) | (BTN['B'] if 'B' in b else 0)
    e.pad(btn, x, y)
    if START <= t and t % 2 == 0:
        e.shot(); log.append(dict(t=t, x=x, y=y, b=b, label=lab, lock=1 if e.r32(S['g_lock']) else 0))
    if t >= END:
        json.dump(log, open(sys.argv[3], 'w')); print('frames', len(log)); e.stop()


e.run(script)
