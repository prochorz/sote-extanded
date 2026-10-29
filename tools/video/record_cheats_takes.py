#!/usr/bin/env python3
"""Record the takes of the Cheats / overlay showcase (pause-menu Cheats, Go to level,
lock-on reticle, Invincibility under fire).

    cd harness && RES=960x720 SHOTS=ch_menu M64CPU=0 python3 ../tools/video/record_cheats_takes.py <rom> menu ch_menu.json
    takes: menu   (play.st)       pause -> Cheats, Invincibility, Fog off, Jump Power, vertFOV, light, Reset
           level  (play.st)       Go to level: browse the sub-level names, load 1. Battle on Hoth
           lock   (om_drones.st)  Z lock on a drone: bars + four-pointer reticle, B fires
           god    (echo_stairs.st) troopers shoot from above; Invincibility on, health stops dropping

Frames: local/run/shots/<SHOTS>/ every 2nd video frame (30 fps), skipped while a level loads.
JSON: one entry per saved frame {t, x, y, b, label, lock} for compose_takes.py; b letters:
A B Z, L R, S = START, U / D = D-pad up / down. Uses GLideN64 (local/bin).
"""
import json, os, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, HERE, BTN
from inject import inject, syms
from game import find_player

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
TAKE, OUT = sys.argv[2], sys.argv[3]
STATE = {'menu': 'play.st', 'level': 'play.st', 'lock': 'om_drones.st', 'god': 'echo_stairs.st'}[TAKE]
KEY = {'A': 'A', 'B': 'B', 'Z': 'Z', 'L': 'L', 'R': 'R', 'S': 'START', 'U': 'U_D', 'D': 'D_D'}

# Script: (frame, letter or '', label). A press lasts 4 frames; a label holds until the next one.
ev, t = [], 0
FIRST = {'menu': 'Echo Base, mid-game', 'level': 'Echo Base, sub-level 4', 'lock': 'Ord Mantell: drones fly in',
         'god': 'Troopers shoot from above: health drops'}


def press(k, label=None, gap=12):
    global t
    ev.append((t, k, label)); t += gap


def wait(n, label=None):
    global t
    ev.append((t, '', label)); t += n


ev.append((0, '', None)); t = 30                  # settle; labels below start at frame 0 (FIRST)
SKIP = None                                       # (from, to): frames not recorded (loading)
if TAKE == 'menu':
    wait(40, 'Echo Base, mid-game')
    press('S', 'START pauses', 40)
    for _ in range(3): press('D', 'Cheats: a new last entry of the pause list', 16)
    wait(40)
    press('A', 'A opens the cheats list', 50)
    press('D', None, 14); wait(10, 'Invincibility')
    press('A', 'A: Invincibility ON', 50)
    for _ in range(13): press('D', 'Down scrolls the list', 8)
    wait(16, 'Fog')
    press('A', 'A: Fog OFF (the level behind the menu clears)', 70)
    for _ in range(4): press('U', None, 10)
    wait(10, 'Jump Power')
    for _ in range(6): press('R', 'R raises Jump Power, L lowers it', 14)
    wait(30)
    for _ in range(7): press('D', None, 10)
    wait(10, 'vertFOV')
    for _ in range(14): press('R', 'R: wider field of view behind the menu', 8)
    wait(40)
    for _ in range(14): press('D', None, 8)
    wait(10, 'Dir Light Vec')
    for _ in range(8): press('R', 'L/R turn the light direction', 10)
    wait(30)
    for _ in range(2): press('D', None, 12)
    wait(20, 'Reset cheats: shows how many settings changed')
    press('A', 'A: Reset cheats undoes every setting', 70)
    press('B', 'B: back to the pause list', 40)
    press('D', 'Down wraps to Resume', 30)
    press('A', 'Resume', 40)
    wait(60, 'Back in the game')
elif TAKE == 'level':
    wait(30, 'Echo Base, sub-level 4')
    press('S', 'START, then Cheats', 30)
    for _ in range(3): press('D', None, 10)
    press('A', None, 30)
    for _ in range(7): press('D', None, 10)
    wait(30, 'Go to level: the name of the chosen sub-level shows below')
    for _ in range(4): press('R', 'R / L browse all 32 sub-levels by name', 30)
    for _ in range(5): press('L', 'R / L browse all 32 sub-levels by name', 30)
    wait(40, '3: 1. Battle on Hoth')
    press('A', 'A loads it', 20)
    SKIP = (t, t + 980)
    t += 980
    wait(240, 'Battle on Hoth')
elif TAKE == 'lock':
    wait(30, 'Ord Mantell: drones fly in')
    ev.append((t, 'Zh', 'Z: lock on, bars slide in, the reticle flies in')); t += 120
    ev.append((t, 'ZB', 'B fires at the locked drone')); t += 600
elif TAKE == 'god':
    wait(200, 'Troopers shoot from above: health drops')
    press('S', 'Pause, Cheats, Invincibility', 30)
    for _ in range(3): press('D', None, 10)
    press('A', None, 30)
    press('D', None, 14)
    press('A', 'A: Invincibility ON', 40)
    press('B', None, 20)
    press('D', None, 14)
    press('A', 'Resume', 20)
    wait(420, '')
END = t
log, st = [], {'pending': None, 'files': 0}


def buttons(k):
    b, held = 0, ''
    for f, keys, _ in ev:
        if keys == 'Zh' and k >= f: b |= BTN['Z']; held += 'Z'
        elif keys == 'ZB' and k >= f:
            b |= BTN['Z']; held += 'Z'
            if (k // 6) % 2 == 0: b |= BTN['B']; held += 'B'
        elif keys and keys not in ('Zh', 'ZB') and f <= k < f + 4:
            b |= BTN[KEY[keys]]; held += keys
    return b, held


def label(k):
    lab = FIRST[TAKE]
    for f, _, l in ev:
        if f <= k and l is not None: lab = l
    return lab


def script(e, n):
    if n == 1: e.unlimit(False)           # real time: full speed drops screenshots
    if n == 60: e.load_state(os.path.join(paths.STATES, STATE))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    p = find_player(e)
    if TAKE == 'lock' and p: e.wf(p + 0xC0, 100.0)      # the train: keep Dash alive
    b, held = buttons(k)
    e.pad(b)
    if SKIP and SKIP[0] <= k < SKIP[1]: return
    if k % 2 == 0:
        lab = label(k)
        if TAKE == 'god' and p and lab in ('', 'Troopers shoot from above: health drops'):
            hp = e.rf(p + 0xB4)
            lab = (lab + f'  (health {hp:.0f})') if lab else f'Invincibility on: health stays {hp:.0f}'
        # A request on a frame the game does not redraw (the pause screen redraws less often) is
        # dropped by the core: log an entry only once its file has appeared.
        n_files = len(os.listdir(e.shot_dir))
        if st['pending'] is not None and n_files > st['files']: log.append(st['pending'])
        st['files'] = n_files
        e.shot()
        st['pending'] = dict(t=k, x=0, y=0, b=held, label=lab, lock=bool(e.r32(S['g_lock'])))
    if TAKE == 'lock':                                 # end 1.5 s after the lock is gone
        if e.r32(S['g_lock']): st['locked'] = k
        elif st.get('locked') and k - st['locked'] == 90: st['end'] = k
    if k >= st.get('end', END):
        json.dump(log, open(OUT, 'w'))
        print('frames', len(log), flush=True)
        e.stop()


e.run(script)
