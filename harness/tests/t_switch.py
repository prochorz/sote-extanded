"""Lock hand-over: hold Z and fire; when the locked enemy dies the lock should move on.

    M64CPU=0 python3 t_switch.py <rom> <state> [frames]

Dash is kept alive. Prints every change of the locked object and its health.
Checked on om_drones.st (drones arrive one or two at a time): kills, and at least one direct
hand-over from a dead drone to the next one.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import set_health
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2])
FRAMES = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
st = {'lock': None, 'kills': 0, 'handover': 0}


def script(e, n):
    if n == 60: e.load_state(state)
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    if pl: set_health(e, pl)
    lk = e.r32(S['g_lock'])
    b = BTN['Z'] if k >= 10 else 0                    # Z held the whole time after one press
    if k >= 20 and (k // 6) % 2 == 0: b |= BTN['B']
    e.pad(b, 0, 0)
    if lk != st['lock']:
        prev = st['lock']
        died = bool(prev) and not e.rf(prev + 0x60) > 0
        st['kills'] += died
        st['handover'] += died and bool(lk)
        print(f"{k:5d} lock {hex(prev) if prev else '-'} -> {(tag(e.r32(lk)) + '@' + hex(lk)) if lk else '-'}"
              f"{'  (previous died)' if died else ''}", flush=True)
        st['lock'] = lk
        e.shot()
    if k >= FRAMES:
        print('kills', st['kills'])
        check('locked enemies die', st['kills'] >= 2, f'{st["kills"]} kills')
        check('the lock moves on to the next enemy after a kill', st['handover'] >= 1, f'{st["handover"]} hand-overs')
        e.stop()


e.run(script)
sys.exit(report())
