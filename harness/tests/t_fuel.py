"""Infinite jetpack fuel (cheats.c): the "Jetpack Fuel" row (below Invincibility) keeps the
tank full, like Invincibility does for health, and marks it the way Invincibility marks the
health number: while the cheat is on the fuel percentage in the HUD is drawn blue.

    M64CPU=0 python3 t_fuel.py <rom>

Gall canyon (states/gall_tp5.st). Cheats -> Get all stuff gives the jetpack; the fuel is the
float at Humn +0xBC, burned while the jetpack fires (Humn flags 0x300) and clamped to the game's
max (100) inside the control function, so it drains at ~0.14 a frame (a full tank lasts ~12 s).

Off (the default): jump, C-left, hold A 4 s -> the fuel drops well below the max.
On: same, held 15 s -> the fuel stays at the max and the jetpack is still firing at the end,
long after an unpatched tank would have run dry.

The gauge: HUD text elements take their colour from 0x80111250 + id*4 (r, g, b, a in the word's
bytes) and their place from 0x80111110 + id*4. The fuel percentage is element 23, the health
element 21. Invincibility gives the health 0x8080FF80 (0x8006AA08); this cheat gives the fuel
the same word. The slot is shared: element 23 is only the fuel where its updater puts it
(243, 15), so a ship level (states/ast.st), which uses the slot elsewhere, must stay untouched.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
FUEL, FLAGS, HP, Z = 0xBC, 0x74, 0xB4, 0x58
HUD_POS, HUD_COL = 0x80111110, 0x80111250
FUEL_E, HP_E = 0x17, 0x15
BLUE = 0x8080FF80                       # the blue Invincibility gives the health number
AT = (243 << 16) | 15                   # the fuel gauge's own place in the element table
CASES = [dict(on=0, hold=240), dict(on=1, hold=900), dict(ship=1)]      # 4 s drains; 15 s would empty a plain tank
MENU = [(10, 'START'), (50, 'D_D'), (58, 'D_D'), (66, 'D_D'), (74, 'A'),      # open Cheats
        (104, 'D_D'), (112, 'D_D'), (120, 'D_D'), (128, 'A')]                 # row 3: Get all stuff
TOGGLE = [(160, 'D_D'), (168, 'D_D'), (176, 'A')]                             # row 5: Jetpack Fuel
st = {'i': 0, 'k0': None, 'min': 1e9, 'fired': 0, 'end': 0}
out = []


def green(c):                           # the game's own colour for a healthy number
    return c >> 24 < 40 and (c >> 16) & 0xFF > 200 and (c >> 8) & 0xFF < 40


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(CASES):
            e.stop(); return
        e.load_state(os.path.join(paths.STATES, 'ast.st' if CASES[st['i']].get('ship') else 'gall_tp5.st'))
        st.update(k0=n, min=1e9, fired=0, end=0)
        return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 6: return
    k -= 6
    c = CASES[st['i']]
    if c.get('ship'):                   # a ship level: no on-foot player, no menu, force the cheat
        if k == 2: e.w32(S['g_fuel_on'], 1)
        if k == 100:
            st['pos'], st['col'] = e.r32(HUD_POS + FUEL_E * 4), e.r32(HUD_COL + FUEL_E * 4)
        if k > 140:
            out.append(dict(ship=1, pos=st['pos'], col=st['col']))
            print(f"ship: elem23 pos {st['pos']:08X} colour {st['col']:08X}", flush=True)
            st['i'] += 1; st['k0'] = None
        e.pad(0)
        return
    menu = MENU + (TOGGLE if c['on'] else [])
    b = 0
    for f, name in menu:
        if f <= k < f + 6: b |= BTN[name]
    if k == 200:
        e.w32(0x800DD2BC, 0); e.w32(S['g_cheats_open'], 0); e.w32(S['g_cheats_sel'], 0)
        st['row'] = e.r32(S['g_fuel_on'])
    j = k - 220
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + HP, 100.0)
    if j >= 0 and pl:
        hold = c['hold']
        b = (BTN['A'] if j < 3 or 14 <= j < 14 + hold else 0) | (BTN['CL'] if 8 <= j < 11 else 0)
        firing = 1 if e.r32(pl + FLAGS) & 0x300 else 0
        st['min'] = min(st['min'], e.rf(pl + FUEL))
        st['fired'] += firing
        if 14 + hold - 20 <= j < 14 + hold: st['end'] += firing
        if j == 100:                    # mid-flight: the gauge is on screen
            st['col'], st['hp'] = e.r32(HUD_COL + FUEL_E * 4), e.r32(HUD_COL + HP_E * 4)
        if j >= 14 + hold + 30:
            out.append(dict(on=c['on'], row=st['row'], z=e.rf(pl + Z), min=st['min'],
                            fired=st['fired'], end=st['end'], col=st['col'], hp=st['hp']))
            print(f"case {'on' if c['on'] else 'off'}: row {st['row']} fuel_min {st['min']:.2f} "
                  f"firing {st['fired']} still_firing_at_end {st['end']} z {e.rf(pl + Z):.0f} "
                  f"fuel_colour {st['col']:08X} health_colour {st['hp']:08X}", flush=True)
            st['i'] += 1; st['k0'] = None
    e.pad(b)


e.unlimit()
e.run(script)

off, on, ship = out[0], out[1], out[2]
check('the row is off by default', off['row'] == 0, f"{off['row']}")
check('the row turns the cheat on', on['row'] == 1, f"{on['row']}")
check('off: the tank drains over 4 s (the game still burns it)', off['min'] < 95, f"{off['min']:.2f}")
check('on: the fuel stays at the max', on['min'] > 99, f"{on['min']:.2f}")
check('on: the jetpack fires for 15 s and is still firing at the end',
      on['end'] > 0 and on['fired'] > 700, f"{on['fired']} fired, {on['end']} at the end")
check('the cheat does not move Dash by itself', abs(on['z'] - off['z']) < 4000,
      f"off z {off['z']:.0f}, on z {on['z']:.0f}")
check("off: the fuel number is the game's own green", green(off['col']), f"{off['col']:08X}")
check("on: the fuel number is blue, like Invincibility's health", on['col'] == BLUE,
      f"{on['col']:08X}, expected {BLUE:08X}")
check('on: only the fuel is tinted (the health keeps its green)',
      on['hp'] == off['hp'] and green(on['hp']), f"{on['hp']:08X} vs {off['hp']:08X}")
check('a ship level keeps the shared element slot untouched',
      ship['col'] != BLUE and ship['pos'] != AT, f"pos {ship['pos']:08X} colour {ship['col']:08X}")
sys.exit(report())
