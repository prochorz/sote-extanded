"""Xizor's palace gladiator droid: Z locks him in both phases.

    M64CPU=0 python3 t_glad.py <rom> walk|fly

walk: states/xiz_glad.st, the gladiator dormant on the rooftop arena; his fight is started by
      writing his AI state (+0x584 = 3; nothing else in the harness starts it). Z locks him, the
      aim is his body shell (+18 over his feet, not the 4.5 of his height field: his shins),
      and the locked laser takes his health (+0x5C4) down. Checked for ~12 s: later his hits knock
      Dash off the roof.
fly:  states/xiz_glad2.st, the second phase (after "Jetpack Malfunction"): Dash on a wall of the
      maze, the gladiator flying ~60 units off, troopers below. Every Z press locks the
      gladiator (it used to lock the nearest trooper under Dash).
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
MODE = sys.argv[2] if len(sys.argv) > 2 else 'walk'
G = 0x8019F4C4
st = {'tries': 0, 'boss': 0, 'aim': []}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'xiz_glad.st' if MODE == 'walk' else 'xiz_glad2.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0); e.w32(0x800E1B2C, 1)
    if MODE == 'walk':
        if k < 30:
            for off in (0x50, 0x08):
                for i, v in enumerate((-5.0, 0.0, 124.0)): e.wf(pl + off + 4 * i, v)
        if k == 40: e.w32(G + 0x584, 3)
        if k == 360: st['hp0'] = e.rf(G + 0x5C4)
        lk = e.r32(S['g_lock'])
        b = BTN['Z'] if k >= 330 and (lk or k % 30 >= 6) else 0
        if lk and k % 8 < 3: b |= BTN['B']
        e.pad(b)
        if 360 <= k <= 720 and k % 30 == 0:
            st['tries'] += 1
            if lk == G: st['boss'] += 1
            print(f'{k:4d} lock={tag(e.r32(lk)) if lk else "-"} hp={e.rf(G + 0x5C4):.0f}', flush=True)
        if k == 720:
            check('Z locks the gladiator', st['boss'] == st['tries'], f'{st["boss"]}/{st["tries"]}')
            check('the locked laser hurts him', e.rf(G + 0x5C4) < st['hp0'] - 50, f'{st["hp0"]:.0f} -> {e.rf(G + 0x5C4):.0f}')
            e.stop()
    else:
        e.pad(BTN['Z'] if 4 <= k % 30 < 20 else 0)
        if k % 30 == 14:
            lk = e.r32(S['g_lock'])
            st['tries'] += 1
            if lk == G: st['boss'] += 1
            print(f'{k:4d} lock={tag(e.r32(lk)) if lk else "-"}', flush=True)
        if k == 300:
            check('every Z press locks the flying gladiator', st['boss'] == st['tries'], f'{st["boss"]}/{st["tries"]}')
            e.stop()


e.run(script)
sys.exit(report())
