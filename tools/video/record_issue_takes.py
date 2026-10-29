#!/usr/bin/env python3
"""Record takes of the bugs found in the 2026-10-06 review (for a video).

    cd harness && RES=960x720 SHOTS=<dir> M64CPU=0 [PAYLOAD_BUILD=...] python3 ../tools/video/record_issue_takes.py <rom> TP|LVL|GAP <out.json>
    TP:  hang on the crevasse edge, pause -> Cheats -> Teleport (the old build: he stayed on the edge)
    LVL: the same with This Level (the old build: after the reload he hung over the old crevasse)
    RES: play.st, Cheats -> Screen Resolution: every mode stays 320x240
    REV: play.st, Cheats -> Revert Fog and Lights: fovy 77 -> 67.5, a narrower view
    GAP: echo_catwalk.st, full tilt toward 22 degrees (camera-relative): crosses the gap and lands;
         with the ledge hang he is pulled back onto the edge he left (run once with a
         --without hang build via PAYLOAD_BUILD for the reference take)

Frames every 2nd video frame (30 fps); JSON {t, x, y, b, label, hang} for compose_takes.py.
"""
import json, math, os, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, BTN, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
TAKE = sys.argv[2]
HANG = 'g_hang_state' in S
log, st = [], {'grab': None, 'seq': None, 'have': 0}
SHOTDIR = os.path.join(paths.RUN, 'shots', os.environ.get('SHOTS', ''))
LETTER = {'START': 'S', 'D_D': 'D', 'U_D': 'U', 'A': 'A', 'B': 'B'}


def menu(t0, row):
    seq, t = [], t0
    def press(name, gap, lab):
        nonlocal t
        seq.append((t, name, lab)); t += gap
    press('START', 40, 'Pause')
    for _ in range(3): press('D_D', 10, 'Pause menu: down to Cheats')
    press('A', 34, 'Open Cheats')
    name = 'Teleport' if row == 6 else 'This Level'
    for _ in range(row): press('D_D', 10, f'Down to {name}')
    press('A', 4, f'A: {name}')
    return seq, t


def cheat_seq():
    seq, t = [], 60
    def press(name, gap, lab):
        nonlocal t
        seq.append((t, name, lab)); t += gap
    press('START', 40, 'Pause')
    for _ in range(3): press('D_D', 10, 'Pause menu: down to Cheats')
    press('A', 34, 'Open Cheats')
    if TAKE == 'RES':
        for _ in range(16): press('D_D', 8, 'Down to Screen Resolution')
        for i in range(5): press('A', 40, f'A: next mode')
    else:
        for _ in range(2): press('U_D', 14, 'Up to Revert Fog and Lights')
        press('A', 50, 'A: Revert Fog and Lights')
    press('B', 30, 'Back to the pause menu')
    for _ in range(3): press('U_D', 10, 'Up to Resume')
    press('A', 4, 'Resume')
    return seq, t


def script(e, n):
    if n == 1: e.unlimit(False)
    st0 = {'GAP': 'echo_catwalk.st', 'RES': 'play.st', 'REV': 'play.st'}.get(TAKE, 'echo_crevasse.st')
    if n == 60: e.load_state(os.path.join(paths.STATES, st0))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + 0xB4, 100.0)
    hang = e.r32(S['g_hang_state']) if HANG else 0
    x = y = 0; b = ''; lab = ''; shoot = k % 2 == 0
    if TAKE in ('RES', 'REV'):
        t = k - 20
        if t < 0: e.pad(0); return
        if st['seq'] is None: st['seq'], st['act'] = cheat_seq()
        fov, mode = e.rf(0x80192F14), e.r32(0x800D0A88)
        size = f'{e.r32(0x800D25EC)}x{e.r32(0x800D25F0)}'
        lab = f'Echo Base, frame {size}' if TAKE == 'RES' else f'Field of view (fovy) {fov:g} deg'
        pb = 0
        for f, name, l in st['seq']:
            if f - 6 <= t: lab = l
            if f <= t < f + 4: pb |= BTN[name]; b += LETTER[name]
        if TAKE == 'RES' and lab == 'A: next mode': lab = f'Mode {mode}: the frame stays {size}'
        if TAKE == 'REV' and lab.startswith('A: Revert'): lab = f'Revert: fovy now {fov:g} deg (was 77)'
        if t >= st['act']:
            lab = (f'Back in the game: still {size}, the cheat changes nothing' if TAKE == 'RES'
                   else f'fovy {fov:g}: narrower than the level\'s own 77')
        e.pad(pb, 0, 0)
        end = st['act'] + 100
    elif TAKE == 'GAP':
        if k < 6: e.pad(0); return
        t = k - 6
        if st['grab'] is None and hang:
            st['grab'] = t
            Hs = S['g_hang']
            print(f"GRAB t{t} rim ({e.rf(Hs + 52):.1f},{e.rf(Hs + 56):.1f},{e.rf(Hs + 60):.1f}) landed at {st.get('landpos')}", flush=True)
        if e.r32(pl + 0x74) & 0x08000000 and t > 30: st['air'] = 1
        if st.get('landpos') is None and st.get('air') and e.r32(pl + 0x74) & 0x04000000 and not e.r32(pl + 0x74) & 0x08000000:
            st['landpos'] = (round(e.rf(pl + 0x50), 1), round(e.rf(pl + 0x54), 1), round(e.rf(pl + 0x58), 1))
        if t < 110 and st['grab'] is None:
            x, y = int(math.sin(math.radians(22)) * 80), int(math.cos(math.radians(22)) * 80)
        fl = e.r32(pl + 0x74)
        if st['grab'] is not None: lab = 'Pulled back onto the edge he jumped from'
        elif t < 38: lab = 'Full tilt toward the gap'
        elif fl & 0x04000000 and not fl & 0x08000000 and t > 50: lab = 'Landed on the far block'
        else: lab = 'Over the gap'
        if not HANG and t > 50 and fl & 0x04000000: lab = 'Landed on the far block, runs on'
        if not HANG and t > 86: lab = 'Runs on (off the far side: a drop where a catch is fine)'
        if HANG and st['grab'] is None and t > 50 and fl & 0x04000000 and not fl & 0x08000000: st['landed'] = t
        pb = 0
        if st['grab'] is not None and t - st['grab'] >= 25:
            view = e.r16(0x800E0EEC)
            if view != 5 and (t - st['grab'] - 25) % 12 < 3: pb = 0x2000; b = 'L'
            lab = 'L: overhead view - he hangs on the edge he jumped from' if view == 5 else 'L: switching the view'
        e.pad(pb, x, y)
        end = st['grab'] + 160 if st['grab'] is not None else 150
    else:
        t = k - 20
        if t < 0: e.pad(0); return
        g = st['grab']
        if g is None and hang: st['grab'] = g = t; st['seq'], st['act'] = menu(t + 50, 6 if TAKE == 'TP' else 8)
        pb = 0
        if g is None:
            x = 80 if t >= 10 else 0; lab = 'Run off the edge: Dash catches it'
        else:
            act = st['act']
            lab = 'Hanging on the ledge'
            for f, name, l in st['seq']:
                if f - 6 <= t < f + 4: lab = l
                if f <= t < f + 4: pb |= BTN[name]; b += LETTER[name]
            if t >= act:
                if TAKE == 'TP': lab = ('Teleport ran, but the hang holds him on the same edge' if hang
                                        else 'Teleport: Dash leaves the edge (fixed)')
                else:
                    gate = e.rf(0x800DEB78)
                    lag = e.r32(S['g_ov_frames']) - e.r32(S['g_decode_ov'])
                    if gate > 0.05 and (t - act) % 90 < 4 and t > act + 30: pb |= BTN['START']; b += 'S'
                    if t < act + 40: lab = 'This Level: the level reloads'
                    elif gate > 0.05 or lag > 3:
                        shoot = shoot and (t - act) % 30 == 0          # intro, messages: a glimpse only
                        lab = 'Level intro (shortened)'
                    else:
                        st.setdefault('back', t)
                        lab = ('After the reload: hanging over the old crevasse again, blaster out' if hang
                               else 'After the reload: Dash at the level start (fixed)')
        e.pad(pb, x, y)
        if g is None: end = 400
        elif TAKE == 'TP': end = st['act'] + 150
        else: end = st.get('back', 10 ** 6) + 150
    # A shot requested on a frame that is not redrawn (pause) never gets written: log an entry
    # only once its file exists, so the captions stay on their frames.
    have = len(os.listdir(SHOTDIR)) if os.path.isdir(SHOTDIR) else 0
    if st.get('pending') and have > st['have']: log.append(st['pending']); st['pending'] = None
    st['have'] = have
    if shoot:
        e.shot(); st['pending'] = dict(t=t, x=x, y=y, b=b, label=lab, hang=hang)
    if t >= end or k > 4000:
        json.dump(log, open(sys.argv[3], 'w')); print('frames', len(log), 'grab', st['grab'], 'landed', st.get('landed')); e.stop()


e.run(script)
