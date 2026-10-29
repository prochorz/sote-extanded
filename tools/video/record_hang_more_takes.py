#!/usr/bin/env python3
"""Record ledge-hang takes for the 2026-10-06 changes (over a floor, jump catch, canyon, bridge).

    cd harness && RES=960x720 SHOTS=<dir> M64CPU=0 python3 ../tools/video/record_hang_more_takes.py <rom> <take> <out.json>
    F: Gall hangar upper floor (gall_tp1.st, Dash put at (18.2, 13.3)): walk off, hang, let go,
       land on the floor 16 below and stand
    J: Echo Base stairs (echo_stairs.st): run at 45 degrees, jump, catch the block's rim, climb
    C1, C2: Gall canyon (gall_tp5.st 30 degrees, gall_tp6.st 180 degrees): catch a rounded rock
       rim, hang, climb
    B: Echo Base bridge (echo_gapblock.st, 195 degrees): free hang under the bridge's edge, climb

Frames every 2nd video frame (30 fps); JSON {t, x, y, b, label, hang} for compose_takes.py.
"""
import json, math, os, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
TAKE = sys.argv[2]
# state, written position, settle frames, stick direction, jump frame, end action
TAKES = {
    'F': ('gall_tp1.st', (18.2, 13.3, 294.5), 30, 0, -1, 'drop'),
    'J': ('echo_stairs.st', None, 6, 45, 14, 'climb'),
    'C1': ('gall_tp5.st', None, 6, 30, -1, 'climb'),
    'C2': ('gall_tp6.st', None, 6, 180, -1, 'climb'),
    'B': ('echo_gapblock.st', None, 6, 195, -1, 'climb'),
}
STATE, POS, SETTLE, DIR, JUMP, END = TAKES[TAKE]
log, st = [], {'grab': None, 'land': None}


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, STATE))
    if n == 62: inject(e)
    if n < 64: return
    k = n - 64
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    if POS and k < 6:
        for i, v in enumerate(POS):
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
    if k < SETTLE: e.pad(0); return
    t = k - SETTLE
    hang, drop = e.r32(S['g_hang_state']), e.r32(S['g_hang_drop'])
    if hang and st['grab'] is None: st['grab'] = t
    g = st['grab']
    x = y = 0; b = ''; lab = ''
    if g is None:
        x, y = int(math.sin(math.radians(DIR)) * 80), int(math.cos(math.radians(DIR)) * 80)
        if JUMP >= 0:
            lab = 'Run and jump at the block (A)'
            if JUMP <= t < JUMP + 5: b = 'A'
        else:
            lab = 'Walk off the edge (no jump)'
    else:
        h = t - g
        if h < 40: lab = 'Caught the rim in the jump' if JUMP >= 0 else 'Dash catches the edge'
        elif h < 90: lab = 'Hanging' + (' free: no wall under the rim' if TAKE == 'B' else '')
        elif END == 'climb':
            lab = 'Stick up: climb'
            if h < 100: y = 80
        else:
            if h < 100: y = -80
            if st['land'] is None and h >= 100 and not drop and not hang: st['land'] = h
            lab = 'Stick down: let go' if st['land'] is None else 'Lands like a normal jump down'
    e.pad(0x80 if b == 'A' else 0, x, y)
    if t % 2 == 0:
        e.shot(); log.append(dict(t=t, x=x, y=y, b=b, label=lab, hang=hang))
    end = g + (230 if END == 'drop' else 200) if g is not None else 260
    if t >= end:
        json.dump(log, open(sys.argv[3], 'w')); print('frames', len(log), 'grab', g, 'land', st['land']); e.stop()


e.run(script)
