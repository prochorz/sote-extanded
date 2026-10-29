"""Fight the Echo Base AT-ST with Z-targeting (states/echo_atst.st: arena, cutscene over).

    M64CPU=0 python3 t_boss.py <rom> [frames]

Holds Z, circle-strafes and fires. Prints the lock, Dash's health, the boss position and
whether the boss object still exists; screenshots every 200 frames.
Checked (default run): the AT-ST is locked from the Z press on and Dash keeps facing it.
Dash's health is kept full: dying respawns him in the doorway, behind the wall, where the
lock rightly drops (out of sight for ~1 s).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import pool_objects, LEVEL_ID, HUMN_HP, HUMN_YAW
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 2400
st = {'locks': set(), 'err': []}


def boss(e):
    for r, ob in pool_objects(e):
        if tag(e.r32(ob)) == 'Boss':
            return ob, e.r16(r + 0x68)
    return 0, 0


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_atst.st'))
    if n == 62:
        inject(e)
        if os.environ.get('NOLOS'): e.w32(S['g_test_skip_los'], 1)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + HUMN_HP, 100.0)
    lk = e.r32(S['g_lock'])
    b = BTN['Z'] if k >= 10 and (lk or k % 60 >= 6) else 0   # re-press Z until it locks
    if os.environ.get('WALL'):                       # step out of the doorway behind the wall first
        if k < 60:
            e.pad(0, int(os.environ['WALL']), 0); return
        if k < 75:                                   # turn to face the boss (camera-relative stick)
            pl = e.r32(S['g_player']); ob, _ = boss(e)
            bearing = math.degrees(math.atan2(e.rf(ob + 0x54) - e.rf(pl + 0x54), e.rf(ob + 0x50) - e.rf(pl + 0x50)))
            r = math.radians(bearing - e.rf(S['g_cam_facing']))
            e.pad(0, int(-math.sin(r) * 30), int(math.cos(r) * 30)); return
        b = BTN['Z'] if k % 60 >= 6 else 0
        if k % 20 == 10:
            pl = e.r32(S['g_player']); ob, _ = boss(e)
            bearing = math.degrees(math.atan2(e.rf(ob + 0x54) - e.rf(pl + 0x54), e.rf(ob + 0x50) - e.rf(pl + 0x50)))
            print(f"{k:5d} WALL lock={tag(e.r32(lk)) if lk else '-'} dash=({e.rf(pl + 0x50):.0f},{e.rf(pl + 0x54):.0f})"
                  f" facing={(e.rf(pl + HUMN_YAW) + 270) % 360 - 180:.0f} bearing={bearing:.0f}"
                  f" boss state={e.rf(ob + 0x60):.2f}", flush=True)
            if k % 100 == 10: e.shot()
        e.pad(b, 0, 0)
        if k >= 300:
            check('locks the AT-ST after stepping out of the doorway', lk and tag(e.r32(lk)) == 'Boss'); e.stop()
        return
    if k >= 40: st['locks'].add(tag(e.r32(lk)) if lk else '-')
    if k >= 30 and (k // 8) % 2 == 0: b |= BTN['B']
    x = 60 if (k // 300) % 2 == 0 else -60
    e.pad(b, x if k >= 30 else 0, 0)
    if k % 100 == 50:                                    # mid-press, Z held
        ob, fl = boss(e)
        lk = e.r32(S['g_lock'])
        if ob and pl:
            dx, dy = e.rf(ob + 0x50) - e.rf(pl + 0x50), e.rf(ob + 0x54) - e.rf(pl + 0x54)
            st['err'].append(((e.rf(pl + HUMN_YAW) + 90) - math.degrees(math.atan2(dy, dx)) + 180) % 360 - 180)
            print(f"      dist={math.hypot(dx, dy):.0f} bearing={math.degrees(math.atan2(dy, dx)):.0f}"
                  f" facing={(e.rf(pl + HUMN_YAW) + 270) % 360 - 180:.0f} boss h={e.rf(ob + 0xAC):.1f} hp60={e.rf(ob + 0x60):.2f} tf={e.r16(ob + 6):x}", flush=True)
        print(f"{k:5d} lock={tag(e.r32(lk)) if lk else '-'} dash_hp={e.rf(pl + HUMN_HP) if pl else 0:.0f}"
              f" boss={'(%.0f,%.0f) fl=%x +80=%x' % (e.rf(ob + 0x50), e.rf(ob + 0x54), fl, e.r32(ob + 0x80)) if ob else 'gone'}"
              f" level={e.r16(LEVEL_ID):x}", flush=True)
    if k % 200 == 50: e.shot()
    if k >= FRAMES:
        err = max(map(abs, st['err'])) if st['err'] else float('nan')
        check('the AT-ST stays locked while Z is held', st['locks'] == {'Boss'}, ', '.join(sorted(st['locks'])))
        check('Dash faces the AT-ST', err < 3, f'max |facing - bearing| {err:.1f}')
        e.stop()


e.run(script)
sys.exit(report())
