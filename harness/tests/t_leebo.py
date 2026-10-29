"""Leebo Scanner toggle (cheats.c): switches the top-down view on/off, and the row reads the
real camera state (changing the camera away turns it OFF).

    M64CPU=0 python3 t_leebo.py <rom> [state]        (default play.st, Echo Base start)

Opens the pause menu, goes onto Cheats, wraps up four items (past Reset cheats, Friendly Wampas and Creature Cam) onto Leebo Scanner, turns it on
(camera view 2, the overhead scanner), backs out and resumes, presses Camera (L) which leaves the
scanner view (view back to 1), re-opens Cheats (the row must now read OFF), and presses A to turn
it back on. Values read from the game and the payload.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'play.st')

PAUSED, VIEW = 0x800DD2BC, 0x800E0EEC

seq, marks = [], {}
t = 20


def press(name, gap=10):
    global t
    seq.append((t, name)); t += gap


def mark(name):
    marks[t] = name


def down(n):
    for _ in range(n): press('D_D', 8)


def up(n):
    for _ in range(n): press('U_D', 8)


press('START', 40)                                    # pause
down(2)                                               # Quit
down(1)                                               # Cheats selected
press('A', 30); mark('opened')                        # cheats screen
up(4); mark('at_leebo')                               # wrap up past Reset cheats, Friendly Wampas and Creature Cam: Leebo Scanner
press('A', 20); mark('leebo_on')                      # ON -> view 2
press('B', 30)                                        # back to the pause list
press('U_D', 8); press('U_D', 8); press('U_D', 8)     # Cheats -> Quit -> Options -> Resume
press('A', 40); mark('resumed')                       # resume with the scanner view
press('L', 20); mark('camera')                        # Camera (L): leave the scanner view
press('START', 40)                                    # pause again
down(2)                                               # Quit
down(1)                                               # Cheats selected
press('A', 30); mark('opened2')                       # cheats screen, row kept (Leebo)
press('A', 20); mark('re_on')                         # A: the row is OFF, turn it back on
END = t + 10

st = {}


def snap():
    return dict(paused=e.r32(PAUSED), view=e.r16(VIEW),
                row=e.r32(S['g_cheats_row']), open=e.r32(S['g_cheats_open']))


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(state)
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    b = 0
    for f, name in seq:
        if f <= k < f + 4: b |= BTN[name]
    e.pad(b)
    if k == 0: st['start'] = snap()
    if k in marks:
        s = snap(); st[marks[k]] = s
        print(f'{k:5d} {marks[k]:14s} {s}', flush=True)
        if marks[k] == 'resumed': e.shot()
    if k == END:
        q = st
        check('cheats screen opens', q['opened']['open'] == 1 and q['opened']['paused'] == 1)
        check('up from the top, past Reset, Friendly Wampas and Creature Cam, is the Leebo Scanner row', q['at_leebo']['row'] == 37,
              f"row {q['at_leebo']['row']}")
        check('A turns the scanner on: view goes to 2',
              q['leebo_on']['view'] == 2, f"view {q['leebo_on']['view']}")
        check('resumes with the scanner view on', q['resumed']['paused'] == 0 and q['resumed']['view'] == 2,
              f"paused {q['resumed']['paused']} view {q['resumed']['view']}")
        check('Camera (L) leaves the scanner view', q['camera']['view'] == 1, f"view {q['camera']['view']}")
        check('re-opened Cheats reads the real state (row still on Leebo, OFF)',
              q['opened2']['open'] == 1 and q['opened2']['row'] == 37 and q['opened2']['view'] == 1,
              f"open {q['opened2']['open']} row {q['opened2']['row']} view {q['opened2']['view']}")
        check('A turns it back on from the OFF state', q['re_on']['view'] == 2, f"view {q['re_on']['view']}")
        e.stop()


e.run(script)
sys.exit(report())
