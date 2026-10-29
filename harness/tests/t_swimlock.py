"""Under water: Z locks the sewer dianoga's eye and the locked laser kills it (states/sew_dianoga.st).

    M64CPU=0 python3 t_swimlock.py <rom> [cycle]

The state has the dianoga woken (its five Trop parts got +0x74 bit 0x400; nothing in the
harness wakes it otherwise) and Dash swimming next to it. Swimming sets Humn flag 0x400, which
the patch once read as "dead" and switched itself off in the water: no lock at all. The eye
(Trop +0x74 bit 0x100, "Dianoga Eye" on the HUD, health +0x7C = 500) ranks before the tentacles
(bit 0x200). The bot from bots/swim.py: Z held, circle, fire, A up toward the eye. Checked over
~20 s: Dash swims, the lock is on the eye nearly all the time, and its health drops below half.
cycle: the dianoga put back to sleep (bit 0x400 cleared: its parts hold still, the four
tentacles at the eye's spot, ranked after it by address). Z locks the eye, then quick second taps (Z let go for 3 frames) step to the next target:
each tap a different one, tentacles included, round to the eye again; a slow press (Z let go
for 1 s) takes the eye, the best target, again.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
EYE = 0x801BE098
PARTS = [EYE, 0x801BE1B8, 0x801BE2D8, 0x801BE3F8, 0x801BE518]
st = {'n': 0, 'eye': 0, 'swim': 0, 'seq': []}
MODE = sys.argv[2] if len(sys.argv) > 2 else 'fight'


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'sew_dianoga.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0); e.w32(0x800E1B2C, 1)
    lk = e.r32(S['g_lock'])
    if MODE == 'cycle':
        if k == 0:                              # put it back to sleep: the parts hold still
            for o in PARTS: e.w32(o + 0x74, e.r32(o + 0x74) & ~0x400)
        # Z from 20; taps: let go 3 frames at 40, 52, ... 100; a slow press: let go 112-142
        z = k >= 20 and not any(t <= k < t + 3 for t in range(40, 101, 12)) and not 112 <= k < 142
        e.pad(BTN['Z'] if z else 0)
        if k in [37 + 12 * i for i in range(7)] + [150]:
            st['seq'].append(lk)
            print(f'{k:4d} lock={"eye" if lk == EYE else hex(lk)} kind={e.r32(lk + 0x74) & 0x300 if lk else 0:#x} eyez={e.rf(EYE + 0x58):.0f}', flush=True)
        if k == 151:
            seq = st['seq']; taps = seq[:-1]
            check('Z locks the eye', taps[0] == EYE, hex(taps[0]))
            check('each quick tap moves to another target', all(a != b and a and b for a, b in zip(taps, taps[1:])),
                  ' '.join(hex(x) for x in taps))
            check('the taps reach a tentacle and come round to the eye', any(e.r32(x + 0x74) & 0x200 for x in taps if x) and EYE in taps[1:])
            check('a slow press takes the eye again', seq[-1] == EYE, hex(seq[-1]))
            e.stop()
        return
    b = BTN['Z'] if lk or k % 20 >= 4 else 0
    x = (80 if (k // 150) % 2 == 0 else -80) if lk else 0
    if lk and k % 8 < 3: b |= BTN['B']
    if e.rf(EYE + 0x58) - e.rf(pl + 0x58) > 6: b |= BTN['A']
    e.pad(b, x, 0)
    if k >= 60:
        st['n'] += 1
        if lk == EYE: st['eye'] += 1
        if e.r32(pl + 0x74) & 0x400: st['swim'] += 1
    if k % 60 == 0:
        print(f'{k:4d} lock={tag(e.r32(lk)) if lk else "-"}{" (eye)" if lk == EYE else ""} eye={e.rf(EYE + 0x7C):.0f}', flush=True)
    if k == 600:
        check('Dash swims (flag 0x400)', st['swim'] > st['n'] * 0.9, f'{st["swim"]}/{st["n"]}')
        check('the lock is on the eye', st['eye'] > st['n'] * 0.9, f'{st["eye"]}/{st["n"]} frames')
        check('the locked laser hurts the eye', e.rf(EYE + 0x7C) < 250, f'500 -> {e.rf(EYE + 0x7C):.0f}')
        e.stop()


e.run(script)
sys.exit(report())
