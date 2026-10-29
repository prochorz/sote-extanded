"""IG-88 right next to Dash keeps the lock (states/om_ig88.st).

    M64CPU=0 python3 t_ig88near.py <rom>

Z locks IG-88, then he is stepped (1 unit a frame, position written) to 3 units in front of
Dash. That close his +0x60 flips from 2.5 to -2.5 while he is alive (the state he charges in);
the lock used to read it as health and drop him as he closed in. Checked: +0x60 went negative,
he is not dead (flag 0x20 at +6 clear) and the lock stays on him.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import pool_objects, set_health
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
R = 3.0
st = {'boss': 0, 'neg': 0, 'lost': 0}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'om_ig88.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    set_health(e, pl)
    if not st['boss']:
        st['boss'] = next(o for r, o in pool_objects(e) if tag(e.r32(o)) == 'Boss')
    ob = st['boss']
    e.wf(ob + 0x5C4, 750.0)
    lk = e.r32(S['g_lock'])
    e.pad(BTN['Z'] if (lk or k % 30 >= 6) else 0)
    if k >= 60:
        f = math.radians(e.rf(pl + 0x8C) + 90)
        t = (e.rf(pl + 0x50) + math.cos(f) * R, e.rf(pl + 0x54) + math.sin(f) * R, e.rf(pl + 0x58))
        p = [e.rf(ob + 0x50), e.rf(ob + 0x54), e.rf(ob + 0x58)]
        dd = math.dist(p, t)
        if dd > 0.05: p = [a + (b - a) * min(1.0, dd) / dd for a, b in zip(p, t)]
        for off in (0x50, 0x08):
            for i in range(3): e.wf(ob + off + 4 * i, p[i])
        if e.rf(ob + 0x60) < 0: st['neg'] += 1
        if lk != ob: st['lost'] += 1
    if k % 30 == 0:
        print(f'{k:4d} lock={tag(e.r32(lk)) if lk else "-"} +60={e.rf(ob + 0x60):.2f} tf={e.r16(ob + 6):#x}', flush=True)
    if k == 300:
        check('IG-88 close by flips +0x60 negative', st['neg'] > 0, f'{st["neg"]} frames')
        check('he is alive', not e.r16(ob + 6) & 0x20, f'tf {e.r16(ob + 6):#x}')
        check('the lock stays on him', st['lost'] == 0, f'{st["lost"]} frames unlocked')
        e.stop()


e.run(script)
sys.exit(report())
