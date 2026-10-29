"""No ledge catch while flying the jetpack (user's video, 2026-10-06: he caught the air beside a
Gall cliff mid-flight).

    M64CPU=0 python3 t_hang_jet.py <rom>
    env: DIRS=0,45,...  SHOTS=<dir>

Gall canyon (states/gall_tp5.st); Cheats -> Get all stuff gives the jetpack (the pause is then
cleared in memory). Per direction: jump, C-left, hold A (the jetpack fires: Humn flags 0x300,
fuel at +0xBC) with the stick at full tilt for ~3 s, then let it fall. FAIL: any catch while
the jetpack was used in that flight.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
DIRS = [int(v) for v in os.environ.get('DIRS', ','.join(str(a) for a in range(0, 360, 45))).split(',')]
HOLDS = [int(v) for v in os.environ.get('HOLDS', '30,60,100').split(',')]
STATES = os.environ.get('STATES', 'gall_tp5.st,gall_tp6.st').split(',')
TRIALS = [(sn, a, h) for sn in STATES for h in HOLDS for a in DIRS]
MENU = [(10, 'START'), (50, 'D_D'), (58, 'D_D'), (66, 'D_D'), (74, 'A'),   # Cheats
        (104, 'D_D'), (112, 'D_D'), (120, 'D_D'), (128, 'A')]            # row 3: Get all stuff
st = {'i': 0, 'k0': None, 'bad': 0, 'jet': 0, 'hjet': 0, 'flew': 0}


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS):
            check('jetpack fired', st['jet'] == len(TRIALS), f"{st['jet']}/{len(TRIALS)}")
            check('the patch noticed every jetpack flight (H.jet)', st['hjet'] == st['flew'], f"{st['hjet']}/{st['flew']}")
            check('no catch in a jetpack flight', st['bad'] == 0, f"{st['bad']}")
            e.stop(); return
        e.load_state(os.path.join(paths.STATES, TRIALS[st['i']][0])); st.update(k0=n, t={}); return
    k = n - st['k0']
    t = st['t']
    if k == 2: inject(e)
    if k < 6: return
    k -= 6
    b, sx, sy = 0, 0, 0
    for f, name in MENU:
        if f <= k < f + 6: b |= BTN[name]
    if k == 150:
        e.w32(0x800DD2BC, 0); e.w32(S['g_cheats_open'], 0); e.w32(S['g_cheats_sel'], 0)
    j = k - 200
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + 0xB4, 100.0)
    if j >= 0:
        sn, a, hold = TRIALS[st['i']]
        b = (BTN['A'] if j < 3 or 14 <= j < 14 + hold else 0) | (BTN['CL'] if 8 <= j < 11 else 0)
        sx, sy = int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80)
        if e.r32(pl + 0x74) & 0x300: t['jet'] = 1
        if e.r32(S['g_hang'] + 172): t['hjet'] = 1     # H.jet: the patch saw it
        if j > 0 and e.r32(S['g_hang_state']) and 'grab' not in t:
            t['grab'] = j; t['grab_jet'] = t.get('jet', 0); e.shot()
            print(f"{sn} dir {a} hold {hold}: CATCH at j{j} z {e.rf(pl + 0x58):.1f} jet {t.get('jet', 0)}", flush=True)
        if j >= 220 or (k > 0 and pl and e.rf(pl + 0x58) < 150):
            print(f"{sn} dir {a} hold {hold}: jet {t.get('jet', 0)} grab {t.get('grab')} z {e.rf(pl + 0x58):.1f}", flush=True)
            flew = t.get('jet', 0) and 'grab' not in t          # a walk-off catch before the jump: not a flight
            st['jet'] += t.get('jet', 0); st['flew'] += flew; st['hjet'] += flew and t.get('hjet', 0); st['bad'] += t.get('grab_jet', 0)
            st['i'] += 1; st['k0'] = None
    e.pad(b, sx, sy)


e.unlimit()
e.run(script)
sys.exit(report())
