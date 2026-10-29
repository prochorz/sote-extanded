"""Z-targeting on a savestate with a stormtrooper nearby (default: Suprosa, sup.st).

    M64CPU=0 python3 t_lock.py <rom> [state] [--los] [--behind]

Presses Z, circle-strafes right then left while firing, backs off, releases, runs.
Line of sight is skipped unless --los (the nearest troopers in sup.st stand behind a wall).
Prints the lock, target health, distance and bearing; facing should equal bearing.
--behind (sup.st): turns Dash's back to the trooper ~12 units away before Z; it should still lock
and Dash should turn around.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import facing
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
args = [a for a in sys.argv[2:] if not a.startswith('--')]
state = os.path.join(paths.STATES, args[0] if args else 'sup.st')
PHASES = [(20, 30, 0, 0, 'Zpress'), (30, 200, 80, 0, 'Zright'), (200, 330, -80, 0, 'Zleft'),
          (330, 430, 0, -60, 'Zback'), (430, 470, 0, 0, 'release'), (470, 560, 0, 80, 'run')]
st = {'locks': set(), 'err': [], 'after': 0}


def script(e, n):
    if n == 60: e.load_state(state)
    if n == 62:
        inject(e)
        if '--los' not in sys.argv: e.w32(S['g_test_skip_los'], 1)
    if n < 70: return
    k = n - 70
    x = y = b = 0; lab = '-'
    for a, c, sx, sy, l in PHASES:
        if a <= k < c:
            x, y, lab = sx, sy, l
            if l.startswith('Z'): b = BTN['Z']
    if lab in ('Zright', 'Zleft', 'Zback') and (k // 6) % 2 == 0: b |= BTN['B']
    if '--behind' in sys.argv and k < 16:
        x, y = -65, -47            # camera-relative: run away from the trooper so he ends up behind
    e.pad(b, x, y)
    pl, lk = e.r32(S['g_player']), e.r32(S['g_lock'])
    if k % 10 == 0 and pl:
        px, py = e.rf(pl + 0x50), e.rf(pl + 0x54)
        s = ''
        if lk:
            tx, ty = e.rf(lk + 0x50), e.rf(lk + 0x54)
            bearing = math.degrees(math.atan2(ty - py, tx - px))
            s = (f" lock={tag(e.r32(lk))} hp={e.rf(lk + 0x60):.2f} dist={math.hypot(tx - px, ty - py):.1f}"
                 f" bearing={bearing:.1f}")
            if 40 <= k < 430: st['err'].append((facing(e, pl) - bearing + 180) % 360 - 180)
        print(f"{k:4d} {lab:8s} facing={facing(e, pl):7.1f} bars={e.rf(S['g_bar_h']):4.1f}{s}", flush=True)
    if 30 <= k < 430: st['locks'].add(lk)
    if k >= 450 and lk: st['after'] += 1
    if k % 30 == 0: e.shot()
    if k == 560:
        held = st['locks'] - {0}
        err = max(map(abs, st['err'])) if st['err'] else float('nan')
        check('Z locks one target and keeps it while held', len(held) == 1 and 0 not in st['locks'],
              ', '.join(tag(e.r32(o)) for o in held) or 'no lock')
        check('Dash faces the locked target while strafing', err < 8, f'max |facing - bearing| {err:.1f}')
        check('releasing Z drops the lock', st['after'] == 0)
        e.stop()


e.run(script)
sys.exit(report())
