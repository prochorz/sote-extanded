"""Ledge hang on the Echo Base crevasse (states/echo_crevasse.st).

    M64CPU=0 python3 t_hang.py <rom> climb|drop|jump|kill|fire [stick x,y]

Walks off the edge (default stick 80,0 from the far end of the bridge, no jump). Expect a grab (g_hang_state 1) a few
units below the edge, hanging still for 90 frames, then:
  climb: stick up -> Dash stands on the ledge again (z back at the edge height, on the ground)
  drop:  stick down -> he falls on and is not caught again
  jump:  the same run but jumping off with A -> no grab at all
  kill:  health 0 while he hangs (as if shot dead; the troopers' aim depends on frame timing and
         missed for 250 frames once the patch got lighter) -> he lets go (g_hang_drop) and falls
  fire:  B held while hanging -> no shot (flag 0x800 never set)
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMN_HP
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
MODE = sys.argv[2]
SX, SY = (int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else '80,0').split(','))
st = {'grab': None, 'zmin': 1e9, 'fired': 0, 'drop': 0, 'regrab': 0}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_crevasse.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    g = st['grab']
    if MODE == 'kill' and g is not None and n - 66 >= g + 30:
        if n - 66 == g + 30: e.wf(pl + HUMN_HP, 0.0)
    else: e.wf(pl + HUMN_HP, 100.0)
    st['drop'] |= e.r32(S['g_hang_drop'])
    hang = e.r32(S['g_hang_state'])
    z = e.rf(pl + 0x58)
    st['zmin'] = min(st['zmin'], z)
    if k == 6: st['z0'] = z
    if st['grab'] is not None and k > st['grab'] + 110 and hang == 1: st['regrab'] += 1
    if hang and st['grab'] is None:
        st['grab'] = k
        print(f"{k:4d} GRAB at ({e.rf(pl + 0x50):.1f},{e.rf(pl + 0x54):.1f},{z:.2f})", flush=True); e.shot()
    g = st['grab']
    if g is None:
        b = BTN["A"] if MODE == "jump" and 52 <= k < 58 else 0       # jump while still running (58+ is already on the rim: too late in old builds too)
        e.pad(b, SX if k >= 6 else 0, SY if k >= 6 else 0)
    elif MODE in ('kill', 'fire'):
        e.pad(BTN['B'] if MODE == 'fire' and (k - g) % 8 < 4 else 0)
        if MODE == 'fire' and hang and e.r32(pl + 0x74) & 0x800: st['fired'] += 1
    elif k < g + 90:
        e.pad(0, 0, 0)
    elif k < g + 100:
        e.pad(0, 0, 80 if MODE == 'climb' else -80)
    else:
        e.pad(0)
    if k % 20 == 0:
        print(f"{k:4d} hang={hang} pos=({e.rf(pl + 0x50):.1f},{e.rf(pl + 0x54):.1f},{z:.2f}) flags={e.r32(pl + 0x74):08x}"
              f" anim={e.r32(pl + 0x1A0):08x}", flush=True)
    if k % 40 == 0 and g is not None: e.shot()
    if k >= (g + 200 if g is not None else 300):
        print('result: grabbed' if g is not None else 'result: no grab', f'zmin {st["zmin"]:.1f}', f'final z {z:.2f}',
              f'let go {bool(st["drop"])}' if MODE == 'kill' else '', f'shots while hanging {st["fired"]}' if MODE == 'fire' else '')
        z0, fell = st['z0'], z < st['z0'] - 15
        if MODE == 'jump':
            check('jumping off: no grab', g is None)
        else:
            check('walking off: grabbed below the edge', g is not None and st['zmin'] < z0 - 2, f'zmin {st["zmin"]:.1f}')
        if MODE == 'climb':
            check('climbed back onto the ledge', g is not None and abs(z - z0) < 0.5 and not hang, f'z {z:.2f} vs {z0:.2f}')
        if MODE == 'drop':
            check('let go and fell, not caught again', g is not None and fell and not st['regrab'], f'final z {z:.1f}')
        if MODE == 'kill':
            check('shot while hanging: let go and fell', g is not None and st['drop'] and fell, f'final z {z:.1f}')
        if MODE == 'fire':
            check('no shots while hanging', g is not None and st['fired'] == 0, f'{st["fired"]} shots')
        e.stop()


e.run(script)
sys.exit(report())
