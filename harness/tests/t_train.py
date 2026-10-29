"""Ord Mantell train (player class HumT) checks on states/om.st.

    M64CPU=0 python3 t_train.py <rom> jump [frame]   # run forward, jump at `frame`; print flags/z
    M64CPU=0 python3 t_train.py <rom> lock           # Z-lock on a fake target that moves around Dash

For `jump` on the unpatched game set ORIG=1 and STATE to a state made from the original ROM
(`mkstate.py <original rom> 3`; om.st itself has the patch hooks in RAM). The trajectory should
match the patched run. Falling between cars from om.st is normal: the next car needs a precise jump.

`lock` writes g_lock directly: train enemies only spawn further along the track, and putting a
fake object into the game's target pool freezes the game (it updates pool objects itself).
Expect facing to settle on `want` ~10-20 frames after each target move, bars ~16 px, shots firing.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMT_YAW
from testlib import FAKE, make_fake, check, report

S = syms()
e = Emu(sys.argv[1])
MODE = sys.argv[2]
ORIG = bool(os.environ.get('ORIG'))
PL = 0x801A7AF4                # HumT object (same address in every Ord Mantell state seen so far)
st = {'air': [], 'z': [], 'settled': [], 'shots': 0, 'bars': 0.0}


def script(e, n):
    if n == 60: e.load_state(os.environ.get('STATE', os.path.join(paths.STATES, 'om.st')))
    if n == 62 and not ORIG:
        inject(e)
        if MODE == 'lock':
            e.w32(S['g_test_skip_los'], 1); make_fake(e)
    if n < 66: return
    t = n - 66
    fl, z = e.r32(PL + 0x74), e.rf(PL + 0x58)
    if MODE == 'jump':
        jt = int(sys.argv[3]) if len(sys.argv) > 3 else 88
        e.pad(BTN['A'] if jt <= t < jt + 6 else 0, 0, 80)
        if t % 5 == 0 and t < 200:
            print(f"{t:4d} flags={fl:08x} air={(fl >> 10) & 1} fallen={(fl >> 27) & 1}"
                  f" pos=({e.rf(PL + 0x50):.1f},{e.rf(PL + 0x54):.1f},{z:.2f})", flush=True)
        if t >= jt: st['air'].append((fl >> 10) & 1); st['z'].append(z)
        if t == jt: st['z0'] = z
        if t == 200:
            air, up = st['air'], max(st['z']) - st['z0']
            off = air.index(1) if 1 in air else None
            check('A takes off within 12 frames', off is not None and off < 12, f'after {off} frames')
            check('jump height', up > 0.4, f'{up:.2f} above take-off')
            check('lands again', off is not None and 0 in air[off:], 'still airborne' if off is not None else '')
            e.stop()
        return
    off = (2.0, 4.0) if t < 150 else (-4.0, 2.0) if t < 300 else (4.0, -1.0)
    px, py = e.rf(PL + 0x50), e.rf(PL + 0x54)
    e.wf(FAKE + 0x50, px + off[0]); e.wf(FAKE + 0x54, py + off[1]); e.wf(FAKE + 0x58, z)
    b = BTN['Z'] if t >= 20 else 0
    if t >= 21: e.w32(S['g_lock'], FAKE)
    if t >= 380 and (t // 6) % 2 == 0: b |= BTN['B']
    e.pad(b, 0, 0)
    facing = (e.rf(PL + HUMT_YAW) + 270) % 360 - 180
    want = math.degrees(math.atan2(off[1], off[0]))
    if t % 10 == 0:
        print(f"{t:4d} lock={e.r32(S['g_lock']):x} bars={e.rf(S['g_bar_h']):.1f} facing={facing:.1f}"
              f" want={want:.1f} flags={fl:08x}", flush=True)
    if t in (140, 290, 370): st['settled'].append(abs((facing - want + 180) % 360 - 180))
    if t == 100: st['bars'] = e.rf(S['g_bar_h'])
    if t >= 380 and fl & 0x800: st['shots'] += 1
    if t in (40, 180, 400): e.shot()
    if t == 440:
        check('facing settles on the target after each move', max(st['settled']) < 2,
              ', '.join(f'{x:.1f}' for x in st['settled']))
        check('lock bars drawn', 12 < st['bars'] < 20, f'{st["bars"]:.1f} px')
        check('B fires while locked', st['shots'] > 0)
        e.stop()


e.run(script)
sys.exit(report())
