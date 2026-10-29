"""Dash's two poses on Gall for the Gall Run image (gallrun/slave_pad.py DASH_STATES, dumped 2 frames after the load):
states/gall_dash_stand.st (standing still) and gall_dash_jet.st (firing the jetpack), both from states/gall_tp5.st.

    M64CPU=0 python3 states_dash.py <rom> jet [<j> [<out>]]  # Cheats -> Get all stuff, a jump held into the jetpack,
                                                      # saved <j> frames after the jump (55) as <out>
    M64CPU=0 python3 states_dash.py <rom> stand <frames>  # no input, saved <frames> after the load

The payload is injected (PAYLOAD_BUILD, default local/build/sote-patch): the jet pose opens the pause menu's Cheats
screen and reads g_player. One pose a process (the core starts once a process).
Made from a gall_tp5.st of bootstrap.py (not the one the shipped image came from), the poses are close, not byte-equal:
Dash's bones up to ~1.5 apart (his meshes, place and heading equal), because the idle clip follows the whole game
state at tp5 (the random word 0x8018E9B4, the player's +0xF0.. words): copying the differing player words and the
random word into the state still left 313..2000 of 78864 mesh bytes differing. The image built from them differs in its
two Dash pose blocks (and, from the other made states, the space level's towers' turn and the face sprites' header pair); the
release build is equal in function, not in MD5 (its 7DC1ECE7 prefix kept).
"""
import os, sys
import paths
import m64
from m64 import Emu, BTN
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)     # as the poses in use were made
MODE = sys.argv[2]
IDLE = int(sys.argv[3]) if MODE == 'stand' else 0
JET = int(sys.argv[3]) if MODE == 'jet' and len(sys.argv) > 3 else 55
JET_OUT = sys.argv[4] if MODE == 'jet' and len(sys.argv) > 4 else 'gall_dash_jet.st'
MENU = [(10, 'START'), (50, 'D_D'), (58, 'D_D'), (66, 'D_D'), (74, 'A'), (104, 'D_D'), (112, 'D_D'), (120, 'D_D'), (128, 'A')]
st = {}


def save(name):
    out = os.path.join(paths.STATES, name)
    pl = e.r32(S['g_player'])
    e.save_state(out); e.shot()
    print(name, 'level id', hex(e.r16(0x8013CE0E)), 'pos', [round(e.rf(pl + 0x50 + 4 * i), 2) for i in range(3)],
          'yaw', round(e.rf(pl + 0x8C), 3), 'flags', hex(e.r32(pl + 0x74)), flush=True)


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(os.path.join(paths.STATES, 'gall_tp5.st')); st['k0'] = n; return
    if 'k0' not in st: return
    k = n - st['k0']
    if k == 2: inject(e)
    if MODE == 'stand':
        e.pad(0, 0, 0)
        if k == IDLE: save('gall_dash_stand.st')
        if k > IDLE + 5: e.stop()
        return
    if k < 6: return
    k -= 6; b = 0
    for f, name in MENU:                               # pause -> Cheats -> Get all stuff, the screen closed
        if f <= k < f + 6: b |= BTN[name]
    if k == 150: e.w32(0x800DD2BC, 0); e.w32(S['g_cheats_open'], 0); e.w32(S['g_cheats_sel'], 0)
    pl = e.r32(S['g_player'])
    if pl and k > 150: e.wf(pl + 0xB4, 100.0)
    j = k - 200
    if j >= 0:                                         # jump, C-left, the jump held: the jetpack fires
        b = (BTN['A'] if j < 3 or 14 <= j < 70 else 0) | (BTN['CL'] if 8 <= j < 11 else 0)
        if j == JET: save(JET_OUT)
        if j > JET + 5: e.stop()
    e.pad(b, 0, 0)


e.run(script)
