"""Ledge hang over a floor, and where it must not catch.

    M64CPU=0 python3 t_hang_more.py <rom> [floor|lowjump|nofloor ...]

floor:   Gall hangar upper floor (states/gall_tp1.st, Dash put at (21.4, 19.6) facing yaw 180, 17 above the
         floor below): walking off catches the edge; letting go drops him in the jump pose onto the
         floor below, where the game's own animation takes over within 20 frames of landing
         (it used to keep the fall pose until DROP_T).
lowjump: Echo Base stairs (states/echo_stairs.st), 45 degrees, A at frame 14: the 7-unit block
         ahead is not caught in the jump (hanging there his feet were on the floor; since
         2026-10-06 a jump catch needs 1.5 under his feet and a sheer face).
nofloor: Gall canyon (states/gall_tp5.st) at 330 degrees: the rim beside a big rock with floor
         3 under it; no catch there (he used to hang with his body in that floor).

floor kills the troopers ('Trop') within 20 units of Dash's spot (health +0x60 written 0 every frame, as t_crate.py
does): one walks over the hangar floor and where he is depends on how the state was made. Dash used to be put at
(18.2, 13.3) walking at 0 degrees: the trooper stood 0.9 from him and his overlap pushed Dash to (21.4, 19.6) and on
toward the edge as he walked (without him the walk at 0 goes to a wall at y 2). Put where that push ended, walking
at 300 (the push's run, +x -y; 300..330 all catch), he catches the edge with no one there.
A jump catch is t_hang_dirs.py's: the one here (Gall canyon, gall_tp5) held only while a trooper by the rim pushed
Dash against the face, and without him no angle or A frame catches in the jump.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from testlib import check, report
from game import pool_objects

S = syms()
e = Emu(sys.argv[1])
MODES = sys.argv[2:] or ['floor', 'lowjump', 'nofloor']
H = S['g_hang']
TRIALS = {
    'floor': ('gall_tp1.st', (21.43, 19.56, 294.5), 300, -1),
    'lowjump': ('echo_stairs.st', None, 45, 14),
    'nofloor': ('gall_tp5.st', None, 330, -1),
}
KILL_AT = {'floor': (21.43, 19.56)}    # troopers within 20 of these are killed
st = {'i': 0, 'k0': None}


def ctrl_anim():
    c = e.r32(S['g_game_anim_ctrl'])
    d = e.r32(c + 4) if c else 0
    return e.r32(d) if d else -1


def finish(mode, t, pl, z):
    if mode == 'floor':
        check('floor: caught the edge', t['grab'] is not None)
        check('floor: let go in the jump pose (jmpF down)', t.get('anim') == 0x0D, f"anim {t.get('anim')}")
        check('floor: landed on the floor below', t.get('land') is not None and abs(z - 277.5) < 0.6, f'z {z:.1f}')
        check('floor: the game picked his animation soon after landing', t.get('anim_k') is not None
              and t['anim_k'] - t['land'] <= 20, f"landed {t.get('land')} anim {t.get('anim_k')}")
    elif mode == 'lowjump':
        check('lowjump: no catch on the low block', t['grab'] is None)
    else:
        check('nofloor: no catch beside the rock', t['grab'] is None)


def script(e, n):
    if n < 60: return
    if st['k0'] is None:
        if st['i'] >= len(MODES): e.stop(); return
        sname = TRIALS[MODES[st['i']]][0]
        e.load_state(os.path.join(paths.STATES, sname)); st.update(k0=n, t={'grab': None}); return
    k = n - st['k0']
    mode = MODES[st['i']]
    _, setpos, a, jump = TRIALS[mode]
    t = st['t']
    if k == 2: inject(e)
    if k < 4: e.pad(0); return
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)
    if k == 4 and mode in KILL_AT:
        cx, cy = KILL_AT[mode]
        t['gone'] = [o for _, o in pool_objects(e) if tag(e.r32(o)) == 'Trop'
                     and math.hypot(e.rf(o + 0x50) - cx, e.rf(o + 0x54) - cy) < 20]
        print(f"{mode}: troopers killed {len(t['gone'])}", flush=True)
    for o in t.get('gone', ()): e.wf(o + 0x60, 0.0)
    if setpos and k < 8:
        for i, v in enumerate(setpos):
            e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)
        e.wf(pl + 0x8C, 180.0); e.wf(pl + 0x14, 180.0)
    settle = 30 if setpos else 6        # standing still longer turns the camera (camera-relative stick)
    if k < settle: e.pad(0); return
    k -= settle
    z = e.rf(pl + 0x58)
    hang, drop = e.r32(S['g_hang_state']), e.r32(S['g_hang_drop'])
    if hang and t['grab'] is None:
        t.update(grab=k, jumped=e.r32(H + 16), rim=e.rf(H + 104))
        print(f"{mode}: catch at k{k} z {z:.1f} rim {t['rim']:.1f} jumped {t['jumped']} gap {e.rf(S['g_hang_gap']):.2f}", flush=True)
    g = t['grab']
    if os.environ.get('TRACE') and k % 10 == 0: print(mode, k, round(e.rf(pl + 0x50), 1), round(e.rf(pl + 0x54), 1), round(z, 1), hex(e.r32(pl + 0x74)), e.r32(S['g_hang_why']), flush=True)
    if g is None:
        b = BTN['A'] if 0 <= jump <= k < jump + 5 else 0
        e.pad(b, int(math.sin(math.radians(a)) * 80), int(math.cos(math.radians(a)) * 80))
        if k >= 200:
            finish(mode, t, pl, z); st['i'] += 1; st['k0'] = None
        return
    if k < g + 50: e.pad(0); return
    if k < g + 60:
        e.pad(0, 0, -80)
        if mode == 'floor' and drop and 'anim' not in t: t['anim'] = ctrl_anim()
        return
    e.pad(0)
    if mode == 'floor':
        if t.get('land') is None and not drop and z < 280: t['land'] = k
        if t.get('land') is not None and t.get('anim_k') is None and ctrl_anim() not in (0x0D, 0x19, 0x7F): t['anim_k'] = k
    if k >= g + 200:
        print(f"{mode}: end z {z:.1f} land {t.get('land')} anim at {t.get('anim_k')}", flush=True)
        finish(mode, t, pl, z); st['i'] += 1; st['k0'] = None


e.unlimit()
e.run(script)
sys.exit(report())
