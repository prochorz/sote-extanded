"""Friendly Wampas: the game's secret #4 (a wampa whose target is Dash calms down, 0x800B04B8(wampa, 0)).
The game gives it only for beating Jedi; the secret check 0x800359F0(n) opens name codes only for n < 4.

    M64CPU=0 python3 t_friendly.py <rom> [row|row_off|off|stock]        (default row)

states/echo_cave.st with the current build injected. Dash (Humn +0x50/+0x08) is written 8 units on the -x side
(toward the second wampa) of the first wampa of the game's target pool (a Trop with +0x74 & 0xF == 2), velocity
zeroed, nothing held, 600 VIs. Env knobs: DIST (x offset, default -8), WI (which wampa), KEEP=1, RUN, AWAKE=1.
On the +x side the wampa never leaves state 0 (no hit in 900 VIs); on the -x side it walks (state 2) at VI ~69,
attacks (3) at ~205 and Dash loses ~46 health at ~253. Away from the wampas (KEEP=1) something else in the cave
takes ~10 health every ~38 VIs. Per VI: the wampa's target +0x9C (tag), its state +0x78 (3 = attack) and Dash's health (Humn +0xB4).

row:     Cheats, up two rows (wraps past Reset cheats onto Friendly Wampas, row 39), A: ON (shot of the menu),
         resume; Dash placed at the first unpaused VI: no health lost and no attack state while the target is
         Humn, as stock. Then Cheats again (the row kept), down one row onto Reset cheats, A: g_friendly_on 0.
row_off: the same trip with A twice (ON, then OFF; shot of the menu): Dash loses health, as off.
off:     the game's instructions unchanged: the wampa targets Humn and Dash loses health.
stock:   the game's own answer written into the three secret-4 call sites (jal 0x800359F0, delay slot a0 = 4):
         0x800B0680, 0x800B2B90, 0x800B3374 -> addiu v0, zero, 1; Dash loses no health (the reference).
"""
import os, sys
import _path
import paths
from m64 import Emu, HERE, BTN, tag
from inject import inject, syms
from game import pool_objects
from testlib import check, report

MODE = sys.argv[2] if len(sys.argv) > 2 else 'row'
if MODE not in ('row', 'row_off', 'off', 'stock'):
    print(f'mode {MODE!r}: row, row_off, off or stock', flush=True)
    sys.exit(2)
ROW_MODE = MODE.startswith('row')

S = syms()
e = Emu(sys.argv[1])
SITES = (0x800B0680, 0x800B2B90, 0x800B3374)
ADDIU_V0_1 = 0x24020001
HUMN = 0x48756D6E
TROP = 0x54726F70
HP = 0xB4
DIST = float(os.environ.get('DIST', -8.0))       # x offset from the wampa (env knobs for probing other start points)
RUN = int(os.environ.get('RUN', 600))
WI = int(os.environ.get('WI', 0))                  # which wampa of the pool (0 = the first)
PAUSED = 0x800DD2BC
ROW = 39                                           # Friendly Wampas: after Creature Cam (38), before Reset cheats (40)
st = dict(first=None, attack=0, attack_humn=0, states={}, tgt=None, mark={})
seq, marks = [], {}
t = 0


def press(name, gap=10):
    global t
    seq.append((t, name)); t += gap


def mark(name): marks[t] = name
def up(n): [press('U_D', 8) for _ in range(n)]
def down(n): [press('D_D', 8) for _ in range(n)]
def open_cheats(): press('START', 40); down(2); down(1); press('A', 30)
def resume(): press('B', 30); up(3); press('A', 40)
def buttons(m): return sum(BTN[name] for f, name in seq if f <= m < f + 4)


def menu(m):                                       # m: VIs since the menu trip's start; True once resumed
    if m in marks:
        s = dict(row=e.r32(S['g_cheats_row']), on=e.r32(S['g_friendly_on']), paused=e.r32(PAUSED))
        st['mark'][marks[m]] = s
        print(f'{m:5d} {marks[m]:8s} {s}', flush=True)
        if marks[m] in ('on', 'off'): e.shot()
    e.pad(buttons(m))
    return m > st['resume_after'] and e.r32(PAUSED) == 0


def reset_trip():                                  # Cheats again (the row kept), down onto Reset cheats, A
    global t
    seq.clear(); marks.clear(); t = 0
    open_cheats(); mark('reopened'); down(1); mark('at_reset'); press('A', 30); mark('reset')
    return t + 5


if ROW_MODE:
    open_cheats(); up(2); mark('at_row')
    press('A', 30); mark('on' if MODE == 'row' else 'on1')
    if MODE == 'row_off': press('A', 30); mark('off')
    st['resume_after'] = t
    resume()


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_cave.st'))
    if n == 62:
        inject(e)
        if MODE == 'stock':
            for a in SITES: e.w32(a, ADDIU_V0_1)
    if n < 66: return
    if ROW_MODE and 'k0' not in st:                # the menu trip first, then the measured run
        if not menu(n - 66): return
        st['k0'] = n; print(n - 66, 'resumed', flush=True)
    if ROW_MODE and 'reset_at' in st:              # after the run: Cheats again, onto Reset cheats, A
        m = n - st['reset_at']
        if m in marks:
            s = dict(row=e.r32(S['g_cheats_row']), on=e.r32(S['g_friendly_on']))
            st['mark'][marks[m]] = s; print(f'{m:5d} {marks[m]:8s} {s}', flush=True)
        e.pad(buttons(m))
        if m >= st['reset_end']: e.stop()
        return
    k = n - st.get('k0', 66)
    pl = e.r32(S['g_player'])
    e.pad(0)
    if k == 0:
        ws = [o for _, o in pool_objects(e) if e.r32(o) == TROP and e.r32(o + 0x74) & 0xF == 2]
        print('wampas', ' '.join(f'{o:08x}:{e.r32(o + 0x74):x}/{e.r32(o + 0x78)}@{[round(e.rf(o + 0x50 + 4 * i)) for i in range(3)]}' for o in ws),
              'dash', [round(e.rf(pl + 0x50 + 4 * i)) for i in range(3)], flush=True)
        w = ws[WI] if WI < len(ws) else 0
        st['w'] = w; st['ws'] = ws
        print(f'mode {MODE}: wampa {w:08x} +0x08 {[round(e.rf(w + 8 + 4 * i), 1) for i in range(3)]} '
              f'+0x50 {[round(e.rf(w + 0x50 + 4 * i), 1) for i in range(3)]} +0x74 {e.r32(w + 0x74):08x} '
              f'+0x78 {e.r32(w + 0x78)} +0x9C {e.r32(w + 0x9C):08x}; Dash {pl:08x} hp {e.rf(pl + HP):.1f}', flush=True)
        if MODE == 'stock':
            print('sites', ' '.join(f'{a:08x}={e.r32(a):08x}' for a in SITES), flush=True)
        wx, wy, wz = (e.rf(w + 0x50 + 4 * i) for i in range(3))
        for i, v in enumerate((wx + DIST, wy, wz) if not os.environ.get('KEEP') else ()):   # KEEP=1: Dash stays where the state has him
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
        if os.environ.get('AWAKE'): e.w32(w + 0x74, e.r32(w + 0x74) | 0x400)   # probe: the Trop think bit
        st['hp0'] = e.rf(pl + HP)
        return
    w = st['w']
    t = e.r32(w + 0x9C)
    tt = e.r32(t) if 0x80000000 <= t < 0x80800000 else 0
    s = e.r32(w + 0x78)
    st['states'][s] = st['states'].get(s, 0) + 1
    if tt == HUMN and st['first'] is None:
        st['first'] = k; print(k, 'wampa targets Humn, state', s, flush=True)
    if s == 3:
        st['attack'] += 1
        st['attack_humn'] += tt == HUMN
    if (t, s) != st['tgt']:
        st['tgt'] = (t, s)
        print(f'{k:4d} target {t:08x} {tag(tt) if tt else "-"} state {s} hp {e.rf(pl + HP):.1f} '
              f'dist {sum((e.rf(w + 0x50 + 4 * i) - e.rf(pl + 0x50 + 4 * i)) ** 2 for i in range(2)) ** 0.5:.1f}',
              flush=True)
    for o in st['ws']:                              # every wampa's (target, state) changes
        ts = (e.r32(o + 0x9C), e.r32(o + 0x78))
        if ts != st.setdefault('all', {}).get(o):
            st['all'][o] = ts; st['wst'] = st.get('wst', set()) | {ts[1]}
            print(f'{k:4d}   wampa {o:08x} target {ts[0]:08x} state {ts[1]}', flush=True)
    if e.rf(pl + HP) != st.get('hp', st['hp0']):
        print(f'{k:4d} hp {e.rf(pl + HP):.1f} dash {[round(e.rf(pl + 0x50 + 4 * i), 1) for i in range(3)]} wampa state {s}', flush=True)
    st['hp'] = e.rf(pl + HP)
    st['minhp'] = min(st.get('minhp', 1e9), st['hp'])
    if k == RUN:
        if MODE != 'row': e.stop(); return
        st['reset_at'] = n + 1; st['reset_end'] = reset_trip()


e.run(script)
lost = st['hp0'] - st['minhp']
print(f"SUMMARY mode={MODE} first_humn={st['first']} attack_vis={st['attack']} attack_vis_humn={st['attack_humn']} "
      f"hp0={st['hp0']:.1f} hp_end={st['hp']:.1f} hp_lost={lost:.1f} states={dict(sorted(st['states'].items()))} all_wampa_states={sorted(st.get('wst', []))}",
      flush=True)
check('a wampa found in the pool', st['w'] != 0, f"{st['w']:08x}")
if ROW_MODE:
    mk = st['mark']
    check('up twice from the top is the Friendly Wampas row', mk['at_row']['row'] == ROW, f"row {mk['at_row']['row']}")
    check('A turns the row on', mk.get('on', mk.get('on1'))['on'] == 1, f"{mk.get('on', mk.get('on1'))}")
if MODE == 'row':
    check('row on: Dash loses no health (as stock)', lost == 0, f'{lost:.1f}')
    check('row on: no attack state while the target is Humn', st['attack_humn'] == 0, f"{st['attack_humn']} VIs")
    check('Cheats re-opened on the row', mk['reopened']['row'] == ROW, f"row {mk['reopened']['row']}")
    check('Reset cheats turns the row off', mk['at_reset']['row'] == ROW + 1 and mk['reset']['on'] == 0,
          f"{mk['at_reset']} {mk['reset']}")
elif MODE == 'row_off':
    check('A again turns the row off', mk['off']['on'] == 0, f"{mk['off']}")
    check('row off: the wampa targets Humn', st['first'] is not None, f"first VI {st['first']}")
    check('row off: Dash loses health (as off)', lost > 0, f'{lost:.1f}')
elif MODE == 'off':
    check('off: the wampa targets Humn within 600 VIs', st['first'] is not None, f"first VI {st['first']}")
    check('off: Dash loses health', lost > 0, f'{lost:.1f}')
else:
    check('stock (secret 4 forced): Dash loses no health', lost == 0, f'{lost:.1f}')
    check('stock: no attack state while the target is Humn', st['attack_humn'] == 0, f"{st['attack_humn']} VIs")
sys.exit(report())
