"""Under-water bot for the sewer dianoga (patched controls).

    cd harness && M64CPU=0 SHOTS=<dir> python3 bots/swim.py <rom> [frames]

Starts from states/sew_dianoga.st: the dianoga woken (its five Trop parts got +0x74 bit 0x400,
which nothing in the harness sets by itself), Dash swimming 18 units from its centre.
Plays: Z locks (re-pressed whenever there is no lock, and every 3 s while it is not on the eye), stick sideways circles, B fires, A swims
up while the eye is more than 6 units above him. Dash's health is kept full.
Logs every 30 frames: lock (eye / tentacle / other), the eye's and tentacles' health (+0x7C,
the HUD's numbers), Dash and eye positions. A screenshot every 90 frames.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1])
END = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
EYE, TENT = 0x801BE098, [0x801BE1B8, 0x801BE2D8, 0x801BE3F8, 0x801BE518]
st = {'lock': {}, 'eye0': None}


def kind(o):
    if o == EYE: return 'eye'
    if o in TENT: return 'tentacle'
    return tag(e.r32(o)) if o else '-'


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'sew_dianoga.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0); e.w32(0x800E1B2C, 1)
    if st['eye0'] is None: st['eye0'] = e.rf(EYE + 0x7C)
    lk = e.r32(S['g_lock'])
    b = 0; x = y = 0
    if lk and not (lk != EYE and k % 90 < 4): b |= BTN['Z']    # off the eye: re-press every 3 s
    elif not lk and k % 20 >= 4: b |= BTN['Z']  # Z released 4 frames in 20: a fresh press
    if lk:
        x = 80 if (k // 150) % 2 == 0 else -80   # circle, switching sides every 5 s
        if k % 8 < 3: b |= BTN['B']
    if e.rf(EYE + 0x58) - e.rf(pl + 0x58) > 6: b |= BTN['A']
    e.pad(b, x, y)
    if k >= 30:
        kd = kind(lk); st['lock'][kd] = st['lock'].get(kd, 0) + 1
    if k % 30 == 0:
        print(f'{k:5d} lock={kind(lk):8s} eye={e.rf(EYE + 0x7C):5.0f} tent=[{",".join("%.0f" % e.rf(t + 0x7C) for t in TENT)}] '
              f'dash=({e.rf(pl + 0x50):.0f},{e.rf(pl + 0x54):.0f},{e.rf(pl + 0x58):.0f}) eyepos=({e.rf(EYE + 0x50):.0f},{e.rf(EYE + 0x54):.0f},{e.rf(EYE + 0x58):.0f}) '
              f'hud={tag(e.r32(0x8018DDF4)) if e.r32(0x8018DDF4) else "-"} {e.rf(0x8018DDEC) * 100:.0f}%', flush=True)
    if k % 90 == 0: e.shot()
    if k == END:
        tot = sum(st['lock'].values())
        print('lock time:', ', '.join(f'{a} {100 * c / tot:.0f}%' for a, c in sorted(st['lock'].items(), key=lambda t: -t[1])))
        print(f'eye health {st["eye0"]:.0f} -> {e.rf(EYE + 0x7C):.0f}', flush=True)
        e.stop()


e.run(script)
