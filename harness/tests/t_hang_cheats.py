"""Cheats while Dash hangs on a ledge (echo_crevasse.st): does the hang survive a Teleport / level load?

    M64CPU=0 python3 t_hang_cheats.py <rom> tp|level

Walks off the crevasse edge (stick 80,0), waits for the grab, then through the pause menu:
Cheats -> Teleport (row 10) or This Level (row 12). Expect Dash to leave the hang: the teleport
moves him, the level load restarts the sub-level, and he stays where the game put him.
"""
import os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMN_HP, DLG_GATE
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
MODE = sys.argv[2]
ROW = {'tp': 10, 'level': 12}[MODE]
st = {'grab': None, 'log': []}


def plan(g):
    t, seq = g + 40, []
    def press(name, gap):
        nonlocal t
        seq.append((t, name)); t += gap
    press('START', 40)
    for _ in range(3): press('D_D', 8)
    press('A', 30)
    for _ in range(ROW): press('D_D', 8)
    press('A', 4)
    return seq, t


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_crevasse.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + HUMN_HP, 100.0)
    hang = e.r32(S['g_hang_state'])
    pos = (e.rf(pl + 0x50), e.rf(pl + 0x54), e.rf(pl + 0x58)) if pl else (0, 0, 0)
    if hang and st['grab'] is None:
        st['grab'] = k; st['hangpos'] = pos
        st['seq'], st['act'] = plan(k)
        print(f'{k:4d} GRAB at {pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f}', flush=True); e.shot()
    g = st['grab']
    if g is None:
        e.pad(0, 80 if k >= 6 else 0, 0)
    else:
        b = 0
        for f, name in st['seq']:
            if f <= k < f + 4: b |= BTN[name]
        act = st['act']
        if k > act + 30 and e.rf(DLG_GATE) > 0 and (k - act) % 90 < 4: b |= BTN['START']   # level intro messages
        e.pad(b)
        END = act + (200 if MODE == 'tp' else 1500)
        if k == act - 6: e.shot()
        if k in (act + 2, act + 10, act + 30, act + 60, act + 120, act + 200) or (k > act and (k - act) % 150 == 0) or k == END:
            dx = pos[0] - st['hangpos'][0]; dy = pos[1] - st['hangpos'][1]
            st['log'].append((k - act, hang, pos, (dx * dx + dy * dy) ** .5, pl))
            print(f'act+{k - act:3d} hang={hang} drop={e.r32(S["g_hang_drop"])} player={pl:08x} '
                  f'ctl_lag={e.r32(S["g_ov_frames"]) - e.r32(S["g_decode_ov"])} gate={e.rf(DLG_GATE):.1f} pos=({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f}) from hang point {st["log"][-1][3]:.1f}', flush=True)
            e.shot()
        if k == END:
            last = st['log'][-1]
            check('grabbed the edge', g is not None)
            check(f'{MODE}: hang ended', last[1] == 0, f'g_hang_state {last[1]}')
            check(f'{MODE}: Dash not held at the old hang point', last[3] > 5, f'{last[3]:.1f} units from it')
            e.stop()
    if k > 3000: print('timeout'); e.stop()


e.run(script)
sys.exit(report())
