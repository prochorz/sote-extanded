"""Cheats entry in the pause menu (cheats.c): navigation, settings, actions.

    M64CPU=0 python3 t_cheats.py <rom> [state]        (default play.st, Echo Base start)

Pauses, walks the pause list down past Quit onto "Cheats" and around (wrap both ways), opens
the cheats screen, turns the patch's own features off (New Controls, Z Lock-On, Ledge Hang), switches Invincibility on, gives 50 lives, raises Jump Power, turns fog off,
narrows vertFOV (values change with L/R), undoes it all with Reset cheats, backs out with B, re-opens and runs Teleport (which resumes the game). Then
pauses again and checks the game's own list still works (Down -> Options, A opens Options).
Everything is driven by pad input; values are read from the game's variables.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import find_player
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'play.st')

PAUSED, CURSOR, LIST, OPTIONS = 0x800DD2BC, 0x800D0944, 0x800D0948, 0x800DD5E4
seq, marks = [], {}
t = 20


def press(name, gap=10):
    global t
    seq.append((t, name)); t += gap


def mark(name):
    marks[t] = name


def down(n):
    for _ in range(n): press('D_D', 8)


press('START', 40)
down(2); mark('quit')
down(1); mark('on_cheats')
down(1); mark('wrapped_down')
press('U_D', 8); mark('wrapped_up')
press('U_D', 8); mark('back_to_quit')
down(1); press('A', 30); mark('opened')
press('A', 20); mark('ctl_off')                        # row 0 New Controls
press('A', 20); mark('ctl_on')
down(1); press('A', 20); mark('lock_off')              # row 1 Z Lock-On
down(1); press('A', 20); mark('hang_off')              # row 2 Ledge Hang
down(2); press('A', 20); mark('invincible')            # row 4
down(3); press('A', 20); mark('lives')                 # row 7
down(7)                                                # row 14 Jump Power
for _ in range(4): press('R', 8)
mark('jump')
down(4); press('A', 20); mark('fog')                   # row 18
down(2)                                                # row 20 vertFOV
for _ in range(5): press('L', 8)
mark('fov')
down(20); press('A', 20); mark('reset')               # row 40 Reset cheats (last)
for _ in range(20): press('U_D', 8)                   # back to row 20
press('B', 30); mark('closed')
press('A', 30); mark('reopened')                       # row is kept (20)
for _ in range(9): press('U_D', 8)                     # row 11 Go to level
for _ in range(2): press('R', 8)
press('L', 8); mark('level_pick')                       # current + 1, not loaded
press('U_D', 8)                                        # row 10 Teleport
mark('teleport_row')
press('A', 60); mark('teleported')
press('START', 40); mark('paused_again')
down(1); press('A', 40); mark('options')
END = t + 10

st = {}


def snap():
    p = find_player(e)
    return dict(paused=e.r32(PAUSED), cursor=e.r16(CURSOR), list=e.r32(LIST), options=e.r32(OPTIONS),
                sel=e.r32(S['g_cheats_sel']), open=e.r32(S['g_cheats_open']), row=e.r32(S['g_cheats_row']), off=e.r32(S['g_off']),
                inv=e.r32(0x800E1B2C), lives=e.r32(0x800E0EB0), jump=e.rf(0x800E0DC0),
                fogoff=e.r32(0x800D2538) >> 24, timer=e.rf(p + 0xE4) if p else 0, lvl=e.r32(S['g_lvl']) if 'g_lvl' in S else -1, level=e.r16(0x8013CE0E), fov=e.rf(0x80192F14), x=e.rf(p + 0x50) if p else None)


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
        if marks[k] in ('on_cheats', 'fov', 'teleported'): e.shot()
    if k == END:
        q = st
        check('down from Quit selects Cheats', q['quit']['cursor'] == 2 and q['on_cheats']['sel'] == 1,
              f"cursor {q['quit']['cursor']}, sel {q['on_cheats']['sel']}")
        check('down from Cheats wraps to Resume', q['wrapped_down']['cursor'] == 0 and not q['wrapped_down']['sel'])
        check('up from Resume selects Cheats', q['wrapped_up']['sel'] == 1)
        check('up from Cheats goes to Quit', q['back_to_quit']['cursor'] == 2 and not q['back_to_quit']['sel'])
        check('A opens the cheats screen, pause list hidden',
              q['opened']['open'] == 1 and q['opened']['list'] == 0 and q['opened']['paused'] == 1)
        check('New Controls: A turns off and on', q['opened']['off'] == 0 and q['ctl_off']['off'] == 1
              and q['ctl_on']['off'] == 0, f"{q['opened']['off']} {q['ctl_off']['off']} {q['ctl_on']['off']}")
        check('Z Lock-On and Ledge Hang off', q['lock_off']['off'] == 2 and q['hang_off']['off'] == 6,
              f"{q['lock_off']['off']} {q['hang_off']['off']}")
        check('Invincibility on (flag and the player\'s timer)', q['invincible']['inv'] == 1 and q['start']['inv'] == 0
              and q['jump']['timer'] > 1000, f"timer {q['jump']['timer']:.0f}")
        check('50 Lives', q['lives']['lives'] == 50, f"{q['lives']['lives']}")
        check('Jump Power +0.2', abs(q['jump']['jump'] - q['start']['jump'] - 0.2) < 0.01, f"{q['jump']['jump']:.2f}")
        check('Fog off', q['fog']['fogoff'] == 1 and q['start']['fogoff'] == 0)
        check('vertFOV -5', abs(q['fov']['fov'] - q['start']['fov'] + 5) < 0.01, f"{q['fov']['fov']}")
        check('settings stay paused', all(q[m]['paused'] == 1 for m in ('invincible', 'lives', 'jump', 'fog', 'fov')))
        r, s0 = q['reset'], q['start']
        check('Reset restores the settings', r['inv'] == s0['inv'] and abs(r['jump'] - s0['jump']) < 0.001
              and r['fogoff'] == s0['fogoff'] and abs(r['fov'] - s0['fov']) < 0.01 and r['paused'] == 1,
              f"inv {r['inv']} jump {r['jump']:.2f} fogoff {r['fogoff']} fov {r['fov']}")
        check('Reset turns the features back on', r['off'] == 0, f"{r['off']}")
        check('Reset keeps given things (lives)', r['lives'] == 50)
        check('B goes back to the list on Cheats', q['closed']['open'] == 0 and q['closed']['list'] == 1
              and q['closed']['sel'] == 1)
        check('re-open keeps the row', q['reopened']['open'] == 1 and q['reopened']['row'] == 20)
        check('Go to level: L/R pick the sub-level, menu stays', q['level_pick']['lvl'] == q['start']['level'] + 1
              and q['level_pick']['paused'] == 1 and q['level_pick']['level'] == q['start']['level'],
              f"lvl {q['level_pick']['lvl']}, level {q['level_pick']['level']}")
        check('Teleport resumes and moves Dash', q['teleported']['paused'] == 0 and q['teleported']['open'] == 0
              and abs(q['teleported']['x'] - q['start']['x']) > 20,
              f"x {q['start']['x']:.1f} -> {q['teleported']['x']:.1f}")
        check('next pause: game list from Resume', q['paused_again']['paused'] == 1 and q['paused_again']['cursor'] == 0
              and q['paused_again']['sel'] == 0 and q['paused_again']['list'] == 1)
        check('game list still works (Down, A opens Options)', q['options']['options'] == 1)
        e.stop()


e.run(script)
sys.exit(report())
