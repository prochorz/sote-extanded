#!/usr/bin/env python3
"""Record a ledge-hang take for a video (example of a scripted take).

    cd harness && RES=960x720 SHOTS=takeA M64CPU=0 python3 ../tools/video/record_hang_takes.py <rom> A takeA.json
    take A: run off the crevasse edge (stick 80,0), hang, fire (no shot), stick up = climb
    take B: the same edge, hang, stick down = let go
    take C: the same edge, hang, shot down by the troopers -> he falls
    take D: run (80,0) and jump off the edge with A -> no catch
    take E: the same edge, hang, L cycles the views: drop camera, then overhead (hands on the rim)
    take F: the same edge, catch on one hand, hang ~3.5 s (sway), stick up = right hand up, climb

Frames: local/run/shots/<SHOTS>/ every 2nd video frame (30 fps). JSON: one entry per
saved frame {t, x, y, b, label, hang} for compose_takes.py (b: 'A'/'B' pressed). Uses GLideN64 (local/bin).
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
SX, SY = (80, 0)                                  # the side with the clearest camera
log, st = [], {'grab': None}


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_crevasse.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    t = k - 150
    g = st['grab']
    if not (TAKE == 'C' and g is not None and t - g >= 60):
        e.wf(pl + 0xB4, 100.0)                   # keep Dash alive (troopers shoot here)
    elif t - g == 60: e.wf(pl + 0xB4, 0.5)       # take C: the next hit kills him
    if k < 150: e.pad(0); return                 # settle before recording
    hang = e.r32(S['g_hang_state'])
    if hang and st['grab'] is None: st['grab'] = g = t
    x = y = 0; b = ''; lab = ''
    if g is None:
        if t >= 20:
            x, y = SX, SY
            lab = 'Jump off the edge (A)' if TAKE == 'D' else 'Run off the edge (no jump)'
            if TAKE == 'D' and 72 <= t < 80: b = 'A'
            if TAKE == 'D' and t >= 90: x = y = 0; lab = 'A jump is never caught'
    else:
        h = t - g
        if TAKE == 'F':
            if h < 40: lab = 'Dash catches the ledge with one hand'
            elif h < 250: lab = 'Hanging on one hand'
            elif h < 262: lab = 'Stick up: the other hand to the rim'; y = 80
            else: lab = 'Pull up, knee on the rim, stand up'
        elif h < 50: lab = 'Dash catches the ledge'
        elif TAKE == 'A':
            if h < 110:
                lab = 'Fire (B): no shooting while hanging'
                if (h - 50) % 16 < 5: b = 'B'
            elif h < 125: lab = 'Stick up: pull up'; y = 80
            else: lab = 'Pull up, knee on the rim, stand up'
        elif TAKE == 'B':
            lab = 'Stick down: let go'
            if 70 <= h < 80: y = -80
        elif TAKE == 'E':
            # L until the wanted view is on (it skips presses that come too soon); label by the view
            view = e.r16(0x800E0EEC)
            want = 1 if h < 60 else 4 if h < 170 else 5
            if view != want and (h - 60) % 12 < 3: b = 'L'
            lab = {1: 'Camera from the open side', 0: 'L: next view', 4: 'L: drop camera, hands on the rim',
                   5: 'L: overhead view, hands on the rim'}.get(view, '')
        elif TAKE == 'C':
            lab = 'Hanging under fire' if not st.get('dead') else 'Shot down: he falls'
            if e.rf(pl + 0xB4) <= 0: st['dead'] = 1
    e.pad({'A': 0x80, 'B': 0x40, 'L': 0x2000}.get(b, 0), x, y)
    if b == 'L': b = ''                          # the panel only shows A/B
    if t % 2 == 0:
        e.shot(); log.append(dict(t=t, x=x, y=y, b=b, label=lab, hang=hang))
    end = {'A': 230, 'B': 160, 'C': 230, 'E': 270, 'F': 370}.get(TAKE, 0) + g if g is not None else 230
    if t >= end:
        json.dump(log, open(sys.argv[3], 'w')); print('frames', len(log), 'grab', g); e.stop()


e.run(script)
