"""Ship row (cheats.c): picks Skyhook's player ship (the game's secret #2: Outrider / X-Wing /
TIE Fighter) and reads the game's own counter (s16 0x800E1B20).

    M64CPU=0 python3 t_cheat_ship.py <rom> [state]        (default sky.st, Skyhook)

sky.st: opens Cheats, wraps up five rows onto Ship, R (X-Wing), resumes: the Stft draw copies the
counter into the model's variant group (+0x14). Pauses again: R (TIE), L (X-Wing), A (TIE), R wraps
to the Outrider, A (X-Wing). This Level: the ship's init resets the counter, the row shows it (0).
R twice, Reset cheats: the counter is back to its value before the first change. Then 300 frames of
play. Any other state (play.st, Echo Base): R and A on the row leave the counter alone.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
NAME = sys.argv[2] if len(sys.argv) > 2 else 'sky.st'
state = os.path.join(paths.STATES, NAME)
SKY = NAME == 'sky.st'

PAUSED, SHIP = 0x800DD2BC, 0x800E1B20
ROW_SHIP = 36

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


def open_cheats():
    press('START', 40); down(2); down(1); press('A', 30)


def resume():
    press('B', 30); up(3); press('A', 40)


open_cheats(); mark('opened')
up(5); mark('at_ship')
press('R', 20); mark('r1')
if SKY:
    resume(); t += 40; mark('resumed')
    open_cheats(); mark('opened2')
    press('R', 20); mark('r2')
    press('L', 20); mark('l1')
    press('A', 20); mark('a2')
    press('R', 20); mark('wrap0')
    press('A', 20); mark('a1')
    down(17); mark('at_this_level')
    press('A', 20); t += 900; mark('reloaded')
    open_cheats(); mark('opened3')
    down(24); mark('at_ship2')
    press('R', 20); press('R', 20); mark('r2b')
    down(4); press('A', 20); mark('reset')
    resume(); t += 300; mark('played')
else:
    press('A', 20); mark('a_any')
END = t + 10

st = {}


def group():
    a = 0x80112808
    for _ in range(200):
        if e.r32(a) == 0x53746674: break
        a += 0x30
    else:
        return None
    s = e.r32(a + 0x10)
    r = e.r32(s + 0xB4) if s else 0
    c = e.r32(e.r32(r + 0x10)) if r else 0
    return c if c and e.r16(c) == 0x5065 else None


def snap():
    g = group()
    return dict(paused=e.r32(PAUSED), ship=e.r16(SHIP), sel=e.r32(g + 0x14) if g else None,
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
        if marks[k] in ('resumed', 'played', 'reloaded'): e.shot()
    if k == END:
        q = st
        check('cheats screen opens', q['opened']['open'] == 1 and q['opened']['paused'] == 1)
        check('up five times from the top is the Ship row', q['at_ship']['row'] == ROW_SHIP, f"row {q['at_ship']['row']}")
        if SKY:
            check('stock start: Outrider, variant 0', q['start']['ship'] == 0 and q['start']['sel'] == 0, f"{q['start']}")
            check('R: X-Wing (1)', q['r1']['ship'] == 1, f"{q['r1']['ship']}")
            check('resumed: the draw shows variant 1', q['resumed']['paused'] == 0 and q['resumed']['sel'] == 1,
                  f"{q['resumed']}")
            check('R: TIE (2)', q['r2']['ship'] == 2, f"{q['r2']['ship']}")
            check('L: X-Wing (1)', q['l1']['ship'] == 1, f"{q['l1']['ship']}")
            check('A: TIE (2)', q['a2']['ship'] == 2, f"{q['a2']['ship']}")
            check('R wraps to the Outrider (0)', q['wrap0']['ship'] == 0, f"{q['wrap0']['ship']}")
            check('A: X-Wing (1)', q['a1']['ship'] == 1, f"{q['a1']['ship']}")
            check('the This Level row', q['at_this_level']['row'] == 12, f"row {q['at_this_level']['row']}")
            check('This Level: the game resets the ship to the Outrider', q['reloaded']['ship'] == 0
                  and q['reloaded']['paused'] == 0, f"{q['reloaded']}")
            check('back on the Ship row after the reload', q['at_ship2']['row'] == ROW_SHIP, f"row {q['at_ship2']['row']}")
            check('R twice: TIE (2)', q['r2b']['ship'] == 2, f"{q['r2b']['ship']}")
            check('Reset cheats: back to the value before the first change (0)', q['reset']['ship'] == 0,
                  f"{q['reset']['ship']}")
            check('plays on after resume (variant follows the counter)', q['played']['paused'] == 0
                  and q['played']['sel'] == q['played']['ship'], f"{q['played']}")
        else:
            s0 = q['start']['ship']
            check('not Skyhook: no variant group', q['start']['sel'] is None)
            check('not Skyhook: R and A leave the counter alone', q['r1']['ship'] == s0 and q['a_any']['ship'] == s0,
                  f"{s0} {q['r1']['ship']} {q['a_any']['ship']}")
        e.stop()


e.run(script)
sys.exit(report())
