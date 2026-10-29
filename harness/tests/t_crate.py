"""Crates hide targets (echo_cave.st: the corridor west of the sentry turret, a stack of big
Echo Base crates, class Boxx, between Dash and the door at its end).

    M64CPU=0 python3 t_crate.py <rom>

Dash is stepped (position writes) to (-235, 11), facing north up the corridor. A fake target
(g_test_target) behind the crates must not lock on a Z press (it did: rays stopping on a
crate were let through); one in front of the crates must.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import set_health
from testlib import FAKE, make_fake, check, report

S = syms()
e = Emu(sys.argv[1])
TROOPER = 0x801c5ad4
PATH = [(-130, 25), (-165, 45), (-197, 60), (-213, 60), (-213, 45), (-213, 30), (-230, 30), (-235, 10)]
FAKES = [('behind the crates', (-235, 75, -51), False), ('in front of the crates', (-235, 22, -51), True)]
st = {'i': 0, 't': 0, 'f': 0, 'ft': 0, 'res': []}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_cave.st'))
    if n == 62: inject(e)
    if n < 70: return
    pl = e.r32(S['g_player'])
    if not pl: e.pad(0, 0, 0); return
    set_health(e, pl)
    e.wf(TROOPER + 0x60, 0.0)
    px, py = e.rf(pl + 0x50), e.rf(pl + 0x54)
    if st['i'] < len(PATH):                     # 2 units a frame: the game keeps each step
        tx, ty = PATH[st['i']]
        d = math.hypot(tx - px, ty - py)
        st['t'] += 1
        if d < 2.5 or st['t'] > 120: st['i'] += 1; st['t'] = 0
        else:
            for b in (0x08, 0x50):
                e.wf(pl + b, px + (tx - px) / d * 2); e.wf(pl + b + 4, py + (ty - py) / d * 2)
        e.pad(0, 0, 0)
        return
    if st['f'] >= len(FAKES):
        print(f"Dash at ({px:.1f},{py:.1f})", flush=True)
        for (name, pos, want), got in zip(FAKES, st['res']):
            check(f"target {name} {'locks' if want else 'does not lock'}", got == want, f"locked {got}")
        e.stop(); return
    t = st['ft']; st['ft'] += 1
    name, pos, want = FAKES[st['f']]
    if t < 40:
        e.wf(pl + 0x8C, 0.0); e.wf(pl + 0x14, 0.0)  # facing north
        if t == 0:
            make_fake(e, pos)
            e.w32(S['g_test_target'], FAKE)
        e.pad(0, 0, 0)
        return
    e.pad(BTN['Z'] if 45 <= t < 75 else 0, 0, 0)
    if t == 70:
        st['res'].append(e.r32(S['g_lock']) == FAKE)
        e.shot()
    if t == 80: st['f'] += 1; st['ft'] = 0


e.run(script)
sys.exit(report())
