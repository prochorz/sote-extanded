"""Ord Mantell IG-88 (class Boss like the AT-ST, but with a z extent and +0x60 > 0 while alive): Z locks him.

    M64CPU=0 python3 t_ig88.py <rom> [frames]

states/om_ig88.st is om.st after one debug-menu Next Level: the IG-88 arena (level 0xA), Dash
~11 units from him. Dash's health is kept full. Z is re-pressed until it
locks, B fires. His real health is the float at +0x5C4 (750 = the HUD's 100%); it is cut to 3
so a few hits kill him (+0x60 then flips to -2.5, flag 0x20 at +6). Checked: the lock is
IG-88; after the kill the letterbox bars and reticle are gone.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import pool_objects, set_health
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 900
st = {'boss': 0, 'locked': 0}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'om_ig88.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    set_health(e, e.r32(S['g_player']))
    if not st['boss']:
        st['boss'] = next(o for r, o in pool_objects(e) if tag(e.r32(o)) == 'Boss')
    ob, lk = st['boss'], e.r32(S['g_lock'])
    b = BTN['Z'] if lk or k % 60 >= 6 else 0
    if lk and (k // 6) % 2 == 0: b |= BTN['B']
    e.pad(b, 0, 0)
    if k == 150: e.wf(ob + 0x5C4, 3.0)
    if lk == ob and not st['locked']: st['locked'] = k
    if k % 100 == 0:
        print(f"{k:5d} lock={lk:08x} hp={e.rf(ob + 0x60):.2f}", flush=True)
    if k == 120:
        check('Z locks IG-88', st['locked'], f"lock {lk:08x}, boss {ob:08x}")
    if not st.get('dead') and e.r16(ob + 6) & 0x20: st['dead'] = k
    if st.get('dead') and k == st['dead'] + 60:
        check('no lock overlay on the dead IG-88', e.rf(S['g_bar_h']) < 1, f"bars {e.rf(S['g_bar_h']):.1f}")
        e.stop()
    if k == FRAMES:
        check('IG-88 dies', st.get('dead'))
        e.stop()


e.run(script)
sys.exit(report())
