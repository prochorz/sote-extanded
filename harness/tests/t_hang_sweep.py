"""Hunt for odd ledge catches: put Dash on a grid of points around a state's start, walk off at
full tilt in several directions, climb (stick up) and report anything odd.

    M64CPU=0 python3 t_hang_sweep.py <rom>
    env: STATES=gall_tp5.st,gall_tp6.st  R=60  STEP=10  DIRS=0,45,...  SHOTS=<dir>
         START=x,y,z (instead of the state's position)  ANYFLOOR=1 (start swimming too)  JUMP=f,... (press A at those frames)

Odd (each printed with the spot, so it can be replayed with R=0 and a start of X,Y):
  moved   the hang was dropped because the game moved him (g_hang_moved_n): looks like a jump
          onto the ledge without the climb
  nostate the hang ended without a climb or a let-go
  again   caught again after the climb with the stick centred (slid off the spot)
  fell    fell more than 3 below where the climb put him (no floor there)
  noclimb stick up did not climb (no spot to stand on up there)
  gap     the face under the rim far from the hang point (> 2.2) or none (free hang)
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1])
STATES = os.environ.get('STATES', 'gall_tp5.st,gall_tp6.st').split(',')
R, STEP = float(os.environ.get('R', '60')), float(os.environ.get('STEP', '10'))
DIRS = [int(v) for v in os.environ.get('DIRS', ','.join(str(a) for a in range(0, 360, 45))).split(',')]
H = S['g_hang']
st = {'i': 0, 'k0': None, 'trials': None, 'odd': 0, 'catches': 0}
starts = {}


def grid(sn):
    x0, y0, z0 = starts[sn]
    n = int(R // STEP)
    return [(sn, x0 + i * STEP, y0 + j * STEP, z0, a) for i in range(-n, n + 1) for j in range(-n, n + 1) for a in DIRS]


def odd(t, why, e, pl):
    sn, x, y, z0, a = t['trial']
    st['odd'] += 1
    print(f"ODD {why}: {sn} at ({x:.0f},{y:.0f}) dir {a} why {e.r32(S['g_hang_why'])} face ({e.rf(H+52):.2f},{e.rf(H+56):.2f},{e.rf(H+60):.2f}) in ({e.rf(H+64):.2f},{e.rf(H+68):.2f}) top ({e.rf(H+72):.2f},{e.rf(H+76):.2f},{e.rf(H+80):.2f}) | " + ' | '.join(t['log']), flush=True)
    e.shot()


def script(e, n):
    if n < 60: return
    if st['trials'] is None:
        if not starts:                       # read each state's start position once
            st['probe'] = st.get('probe', 0)
            if st['probe'] < len(STATES):
                if st.get('pk') is None:
                    e.load_state(os.path.join(paths.STATES, STATES[st['probe']])); st['pk'] = n; return
                if n - st['pk'] == 2: inject(e)
                if n - st['pk'] == 30:
                    pl = e.r32(S['g_player'])
                    st.setdefault('pos', {})[STATES[st['probe']]] = (e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58))
                    st['probe'] += 1; st['pk'] = None
                return
            starts.update(st['pos'])
            if os.environ.get('START'): starts[STATES[0]] = tuple(float(v) for v in os.environ['START'].split(','))
            print('starts', starts, flush=True)
        st['trials'] = [t for sn in STATES for t in grid(sn)]
        print(f"{len(st['trials'])} trials", flush=True)
    if st['k0'] is None:
        if st['i'] >= len(st['trials']):
            print(f"catches {st['catches']}, odd {st['odd']}", flush=True); e.stop(); return
        tr = st['trials'][st['i']]
        e.load_state(os.path.join(paths.STATES, tr[0])); st.update(k0=n, t={'trial': tr, 'log': [], 'prev': 0}); return
    k = n - st['k0']; t = st['t']; sn, x, y, z0, a = t['trial']
    if k == 2: inject(e)
    if k < 4: e.pad(0); return
    pl = e.r32(S['g_player']); e.wf(pl + 0xB4, 100.0)
    if k < 8:
        for i, v in enumerate((x, y, z0 + 5.0)):
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
        t['m0'] = e.r32(S['g_hang_moved_n'])
    if k < 70:                                # let him fall onto whatever is there
        e.pad(0)
        if k == 69:
            fl = e.r32(pl + 0x74)
            if not (fl & 0x04000000 or os.environ.get('ANYFLOOR')) or e.r32(S['g_hang_state']) or e.rf(pl + 0x58) < z0 - 80:
                if os.environ.get('VERBOSE'):
                    print(f"SKIP {sn} at ({x:.0f},{y:.0f}): flags {fl:08x} hang {e.r32(S['g_hang_state'])} z {e.rf(pl + 0x58):.1f}", flush=True)
                st['i'] += 1; st['k0'] = None
        return
    k -= 70
    z = e.rf(pl + 0x58)
    hs = e.r32(S['g_hang_state'])
    if hs != t['prev']:
        s = f"k{k}:{t['prev']}->{hs} z{z:.1f}"
        if hs == 1: s += f" rim({e.rf(H+52):.1f},{e.rf(H+56):.1f},{e.rf(H+104):.1f}) gap {e.rf(S['g_hang_gap']):.2f}"
        t['log'].append(s)
        if t['prev'] == 1 and hs == 0: t['nostate'] = 1
        if t['prev'] == 2 and hs == 0: t['climbed'] = k; t['climb_z'] = z
        if hs == 2: t['up'] = 1
        if hs == 1 and 'climbed' in t: t['again'] = 1
        if hs == 1 and 'g' not in t:
            t['g'] = k; st['catches'] += 1
            gap = e.rf(S['g_hang_gap'])
            if gap < 0 or gap > 2.2: t['gap'] = 1
        t['prev'] = hs
    if e.r32(S['g_hang_moved_n']) != t['m0']: t['moved'] = 1
    if 'climb_z' in t and not hs and z < t['climb_z'] - 3: t['fell'] = 1
    g = t.get('g')
    if os.environ.get('TRACE') and g is None and k % 4 == 0:
        print('T', k, hs, round(e.rf(pl + 0x50), 2), round(e.rf(pl + 0x54), 2), round(z, 2), hex(e.r32(pl + 0x74)), e.r32(S['g_hang_why']), flush=True)
    if g is None:
        jf = [int(v) for v in os.environ.get('JUMP', '').split(',') if v]
        b = BTN['A'] if any(f <= k < f + 4 for f in jf) else 0
        e.pad(b, int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80))
        if k > 90:
            if os.environ.get('VERBOSE'): print(f"NOCATCH {sn} at ({x:.0f},{y:.0f}) dir {a} end ({e.rf(pl+0x50):.1f},{e.rf(pl+0x54):.1f},{z:.1f})", flush=True)
            st['i'] += 1; st['k0'] = None
        return
    if k == g + 25 and t.get('gap'): odd(t, 'gap', e, pl)
    if k < g + 40: e.pad(0)
    elif k < g + 100: e.pad(0, 0, 80)
    else: e.pad(0)                            # stands still: a second catch now is his own
    if os.environ.get('TRACE') and k % 4 == 0:
        print('T', k, hs, round(e.rf(pl + 0x50), 2), round(e.rf(pl + 0x54), 2), round(z, 2), hex(e.r32(pl + 0x74)), flush=True)
    if k >= g + 200:
        if os.environ.get('VERBOSE'):
            print(f"TRIAL {sn} at ({x:.0f},{y:.0f}) dir {a} | " + ' | '.join(t['log']) + f" | end ({e.rf(pl+0x50):.1f},{e.rf(pl+0x54):.1f},{z:.1f})", flush=True)
        if not t.get('up') and not t.get('moved') and not t.get('nostate'): t['noclimb'] = 1
        for why in ('fell', 'moved', 'nostate', 'again', 'noclimb'):
            if t.get(why): odd(t, why, e, pl); break
        st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
