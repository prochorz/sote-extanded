"""Cheats toggles that switch the patch's features off (g_off: 1 New Controls, 2 Z Lock-On, 4 Ledge Hang).

    M64CPU=0 python3 t_off.py <rom> controls|lock|hang|mid

controls: play.st, the same stick and Z inputs twice: the unpatched game, then the patch with
          New Controls off. Dash's path and the camera eye must match (off = the game's own).
lock:     sup.st (line of sight skipped), Z held all along with the stick: unpatched vs the patch
          with Z Lock-On off. Never a lock, and Dash moves as in the game (Z is the game's aim).
hang:     echo_crevasse.st, Ledge Hang off, walking off the edge (stick 80,0): no grab, he falls.
mid:      switched off while in use: locked in sup.st -> New Controls off drops the lock and the
          bars; hanging on the crevasse -> Ledge Hang off lets go and he falls.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import CAM, HUMN_HP, find_player
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
MODE = sys.argv[2]
OFF_CONTROLS, OFF_LOCK, OFF_HANG = 1, 2, 4


def stick_controls(k):
    for a, b, x, y, z in [(0, 50, 0, 80, 0), (50, 100, 80, 0, 0), (100, 150, 57, -57, 0), (150, 170, 0, 0, 1),
                          (170, 230, -80, 30, 1), (230, 260, 0, 0, 0), (260, 320, 0, -80, 0)]:
        if a <= k < b: return (BTN['Z'] if z else 0), x, y
    return 0, 0, 0


def stick_lock(k):
    for a, b, x, y in [(0, 60, 80, 0), (60, 120, 0, 80), (120, 180, -80, -40), (180, 240, 0, -80)]:
        if a <= k < b: return BTN['Z'] | (BTN['B'] if (k // 6) % 2 == 0 else 0), x, y
    return BTN['Z'], 0, 0


# (state, payload, g_off, skip los, frames, inputs)
if MODE == 'controls':
    # Ledge Hang off as well: switched on it still looks for an edge under him (a ray every other
    # frame while he walks), which makes the frame longer, and the game's moves scale with it.
    TRIALS = [('play.st', False, 0, 0, 330, stick_controls),
              ('play.st', True, OFF_CONTROLS | OFF_HANG, 0, 330, stick_controls)]
elif MODE == 'base':        # frame cost: the unpatched game, then the patch with each g_off in OFFS (default 1);
                            # prints the mean frame dt (ms) and the path difference
    TRIALS = [('play.st', False, 0, 0, 330, stick_controls)] + [
              ('play.st', True, int(o), 0, 330, stick_controls) for o in os.environ.get('OFFS', '1').split(',')]
elif MODE == 'lock':
    TRIALS = [('sup.st', False, 0, 1, 250, stick_lock), ('sup.st', True, OFF_LOCK | OFF_HANG, 1, 250, stick_lock)]
elif MODE == 'hang':
    TRIALS = [('echo_crevasse.st', True, OFF_HANG, 0, 200, lambda k: (0, 80 if k >= 6 else 0, 0))]
else:
    TRIALS = [('sup.st', True, 0, 1, 120, lambda k: (BTN['Z'], 0, 0)),
              ('echo_crevasse.st', True, 0, 0, 260, lambda k: (0, 80 if k >= 6 else 0, 0))]
st = {'i': 0, 'k0': None, 'runs': []}


def finish():
    r = st['runs']
    if MODE == 'base':
        for j in range(1, len(r)):
            dd = [i for i in range(len(r[0]['dt'])) if r[0]['dt'][i] != r[j]['dt'][i]]
            pd = [i for i in range(len(r[0]['pos'])) if math.dist(r[0]['pos'][i], r[j]['pos'][i]) > 0.01]
            print('dt differs on', len(dd), 'frames, first', dd[:5], '; pos first diverges', pd[:3])
            import struct
            f = lambda t: struct.unpack('>d', struct.pack('>II', *t))[0]
            print('dt0', [round(f(t) * 1000, 3) for t in r[0]['dt'][:12]])
            print('dt%d' % j, [round(f(t) * 1000, 3) for t in r[j]['dt'][:12]])
            print('mean', sum(map(f, r[0]['dt'])) / len(r[0]['dt']) * 1000, sum(map(f, r[j]['dt'])) / len(r[j]['dt']) * 1000)
            print('stock vs run', j, max(math.dist(r[0]['pos'][i], r[j]['pos'][i]) for i in range(len(r[0]['pos']))))
    elif MODE in ('controls', 'lock'):
        a, b = r
        n = min(len(a['pos']), len(b['pos']))
        dp = max(math.dist(a['pos'][i], b['pos'][i]) for i in range(n))
        dy = max(abs((a['yaw'][i] - b['yaw'][i] + 180) % 360 - 180) for i in range(n))
        turned = max(abs((v - a['yaw'][0] + 180) % 360 - 180) for v in a['yaw'])
        moved = max(math.dist(a['pos'][0], p) for p in a['pos'])
        # The payload's own cost still shifts the frame times a little: ~1 unit and a few degrees
        # mid-turn over 330 frames (with the patch's own controls: 20 units). In sup.st the game's
        # Z aim neither moves nor turns him.
        check('Dash moves and turns as in the game', dp < 1.5 and dy < 6 and (MODE == 'lock' or moved > 20),
              f'max diff {dp:.2f}, yaw diff {dy:.1f}, moved {moved:.1f}, turned {turned:.0f}')
        if MODE == 'controls':
            dc = max(math.dist(a['eye'][i], b['eye'][i]) for i in range(n))
            check('the camera is the game\'s own', dc < 3, f'max eye diff {dc:.2f}')
        check('no lock', b['locks'] == 0, f"{b['locks']} frames")
    elif MODE == 'hang':
        a = r[0]
        check('no grab with Ledge Hang off', a['hang'] == 0, f"{a['hang']} frames")
        check('he falls into the crevasse', a['pos'][-1][2] < a['pos'][0][2] - 20,
              f"z {a['pos'][0][2]:.1f} -> {a['pos'][-1][2]:.1f}")
    else:
        lk, hg = r
        check('locked before the switch', lk['lock_before'], '')
        check('New Controls off drops the lock and the bars', lk['lock_after'] == 0 and lk['bars'] < 1,
              f"lock frames {lk['lock_after']}, bars {lk['bars']:.1f}")
        check('hanging before the switch', hg['grab'] is not None, '')
        check('Ledge Hang off lets go: no hang, he falls', hg['hang_after'] == 0
              and hg['pos'][-1][2] < hg['zgrab'] - 20,
              f"hang frames {hg['hang_after']}, z {hg['zgrab']:.1f} -> {hg['pos'][-1][2]:.1f}")
    e.stop()


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(TRIALS): finish(); return
        e.load_state(os.path.join(paths.STATES, TRIALS[st['i']][0]))
        st.update(k0=n, pl=0, run=dict(pos=[], eye=[], locks=0, hang=0, grab=None, lock_before=0,
                                        lock_after=0, bars=0.0, hang_after=0, zgrab=0.0))
        return
    state, payload, off, los, frames, inputs = TRIALS[st['i']]
    k = n - st['k0']
    run = st['run']
    if k == 2:
        inject(e, payload=payload)
        if payload:
            e.w32(S['g_off'], off)
            if los: e.w32(S['g_test_skip_los'], 1)
    if k < 6: return
    k -= 6
    if not st['pl']: st['pl'] = find_player(e)
    pl = st['pl']
    b, x, y = inputs(k)
    e.pad(b, x, y)
    e.wf(pl + HUMN_HP, 100.0)
    run.setdefault('yaw', []).append(e.rf(pl + 0x8C))
    run.setdefault('dt', []).append((e.r32(0x8018E998), e.r32(0x8018E99C)))
    run['pos'].append((e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58)))
    cam = e.r32(CAM)
    run['eye'].append(tuple(e.rf(cam + 0x44 + 4 * i) for i in range(3)) if cam else (0, 0, 0))
    if payload:
        lk = e.r32(S['g_lock'])
        hang = e.r32(S['g_hang_state']) if 'g_hang_state' in S else 0
        run['locks'] += lk != 0
        run['hang'] += hang != 0
        if MODE == 'mid' and st['i'] == 0:
            if k == 40: run['lock_before'] = lk != 0; e.w32(S['g_off'], OFF_CONTROLS)
            if k > 42 and lk: run['lock_after'] += 1
            if k == frames - 1: run['bars'] = e.rf(S['g_bar_h'])
        if MODE == 'mid' and st['i'] == 1:
            if hang and run['grab'] is None:
                run['grab'] = k; run['zgrab'] = run['pos'][-1][2]
            if run['grab'] is not None and k == run['grab'] + 40: e.w32(S['g_off'], OFF_HANG)
            if run['grab'] is not None and k > run['grab'] + 42 and hang: run['hang_after'] += 1
    if k % 30 == 0:
        print(f"{st['i']} {k:4d} pos=({run['pos'][-1][0]:.1f},{run['pos'][-1][1]:.1f},{run['pos'][-1][2]:.1f})"
              f" eye={tuple(round(v, 1) for v in run['eye'][-1])}", flush=True)
    if k == frames - 1:
        st['runs'].append(run); st['i'] += 1; st['k0'] = None


e.run(script)
sys.exit(report())
