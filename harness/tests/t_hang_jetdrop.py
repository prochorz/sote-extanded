"""Letting go of a ledge, then the jetpack: control comes back at once (user, 2026-10-11: after
letting go and firing the jetpack the stick did nothing for a while).

    M64CPU=0 python3 t_hang_jetdrop.py <rom> [hang]

hang: the jetpack fires while he still hangs, no let-go (user, 2026-10-11: it ran and he kept
hanging); the same checks, the hang must end within 3 frames of it.

Gall hangar upper floor (states/gall_tp1.st, Dash put at the edge as in t_hang_more.py floor);
Cheats -> Get all stuff gives the jetpack (the pause is then cleared in memory). Walks off and
catches the edge, lets go (stick down), then C-left and A held with the stick at full tilt.
Expect: the let-go fall (g_hang_drop) ends within a few frames of the jetpack firing, the
jetpack holds him up (the floor he hung from is a ceiling there), and the stick flies him off
(not held under the edge).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
WALK = 55                     # a walk: at a run (over 18/s) only an abyss is caught (RUN_SPEED)
e = Emu(sys.argv[1])
HANG = len(sys.argv) > 2 and sys.argv[2] == 'hang'
POS = (18.2, 13.3, 294.5)
MENU = [(10, 'START'), (50, 'D_D'), (58, 'D_D'), (66, 'D_D'), (74, 'A'),   # Cheats
        (104, 'D_D'), (112, 'D_D'), (120, 'D_D'), (128, 'A')]            # row 3: Get all stuff
st = {'grab': None, 'let': None, 'jet': None, 'free': None, 'log': []}


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'gall_tp1.st'))
    if n < 60: return
    k = n - 60
    if k == 2: inject(e)
    if k < 6: return
    k -= 6
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + 0xB4, 100.0)
    b, sx, sy = 0, 0, 0
    for f, name in MENU:
        if f <= k < f + 6: b |= BTN[name]
    if k == 150:
        e.w32(0x800DD2BC, 0); e.w32(S['g_cheats_open'], 0); e.w32(S['g_cheats_sel'], 0)
    if 160 <= k < 170:
        for i, v in enumerate(POS):
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
    j = k - 190
    if j >= 0:
        hang, drop = e.r32(S['g_hang_state']), e.r32(S['g_hang_drop'])
        x, y, z = (e.rf(pl + 0x50 + 4 * i) for i in range(3))
        fl = e.r32(pl + 0x74)
        if hang and st['grab'] is None: st['grab'] = j; st['zh'] = z
        g = st['grab']
        if g is None:                                     # walk off the edge where t_hang_more floor does
            want = math.degrees(math.atan2(18.0 - y, 25.5 - x)) if x < 24.5 else 0.0
            a = math.radians(want - e.rf(S['g_cam_facing']))
            sx, sy = int(-math.sin(a) * WALK), int(math.cos(a) * WALK)
        elif j < g + 40: pass
        elif j < g + 46 and not HANG: sy = -80            # let go
        else:
            if st['let'] is None and (drop or HANG): st['let'] = j; st['p0'] = (x, y)
            t = j - (st['let'] if st['let'] is not None else j)
            if 4 <= t < 7: b |= BTN['CL']
            if t >= 10: b |= BTN['A']; sx = 80
            if fl & 0x300 and st['jet'] is None: st['jet'] = j
            if st['jet'] is not None and st['free'] is None and not drop and not hang: st['free'] = j
        if j % 6 == 0:
            print(f"j{j} hang {hang} drop {drop} fl {fl:08x} pos ({x:.1f},{y:.1f},{z:.1f})", flush=True)
        st['log'].append((j, x, y, z))
        if j >= 400 or (g is not None and j >= g + 160):
            g, jt, fr = st['grab'], st['jet'], st['free']
            check('caught the edge and let go', g is not None and st['let'] is not None, f"grab {g} let {st['let']}")
            check('the jetpack fired', jt is not None, f'{jt}')
            check('the let-go fall ends as the jetpack fires', jt is not None and fr is not None and fr - jt <= 3,
                  f'jet {jt} free {fr}')
            if jt is not None and 'zh' in st:
                after = [p for p in st['log'] if p[0] >= jt]
                zj, zmin = after[0][3], min(p[3] for p in after)
                side = max(math.hypot(p[1] - st['p0'][0], p[2] - st['p0'][1]) for p in after)
                # Under the floor he hung from he can't rise; the floor below is ~16 lower.
                check('the jetpack holds him up (no fall to the floor below)', zmin > zj - 3,
                      f'z {zj:.1f} at the jet, min {zmin:.1f}')
                check('the stick flies him off', side > 8, f'{side:.1f} units')
            e.stop()
    e.pad(b, sx, sy)


e.unlimit()
e.run(script)
sys.exit(report())
