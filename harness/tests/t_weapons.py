"""Locked shots of the other weapons reach the AT-ST's cockpit (states/echo_atst_arms.st: the
fight running, every weapon given by the debug menu's "Get all stuff").

    M64CPU=0 python3 t_weapons.py <rom>

Per weapon: reload the state, C-up to it, lock the AT-ST with Z, fire one shot and follow
the projectile (pulse cannon: class Expl, shooter at +0x88; seeker: class Misl, shooter at
+0xA4). Checked: it passes within a few units of the cockpit (the lock's aim point, 0.9 of
the boss's height) and the AT-ST's health (+0x5C4) drops. NOFIX=1 runs without the
fix: before it both flew at chest height along Dash's facing (the
seeker took no target: the game's auto-aim skips bosses) and hit the legs or the floor.
"""
import math, os, struct, sys
from pathlib import Path
import _path
import paths
from m64 import Emu, BTN, HERE, tag
from inject import inject, syms
from game import pool_objects, HUMN_HP
from testlib import check, report

S = syms()
# NOFIX=1: put the game's own instructions back at these hooks (the shots as before the fix).
FIX_HOOKS = [0x80073D44, 0x800741B8, 0x800741E0, 0x80074208, 0x80074510, 0x80074538, 0x80074838, 0x8007E970, 0x80064604, 0x800646A0]
e = Emu(sys.argv[1])
STATE = os.environ.get('STATE', 'echo_atst_arms.st')
NEAR = 7.0                        # the cockpit's hit shells are ~2-5 units round its centre
FAR_NEAR = 10.0                   # from 55 units a blob bursts on the cockpit's front, ~8 out
# (name, C-up presses, weapon index at Humn +0xB8, projectile class, shooter offset, firing range,
#  shots, how close the first shot must pass the cockpit)
WEAPONS = [('pulse cannon', 2, 1, 'Expl', 0x88, 22.0, 1, NEAR),
           ('pulse cannon far', 2, 1, 'Expl', 0x88, 1e9, 5, FAR_NEAR),
           ('seeker', 3, 3, 'Misl', 0xA4, 1e9, 1, NEAR)]
BOSS_HP = 0x5C4                   # AT-ST health (750 full)
DAMAGE = 15                       # a cockpit hit takes ~60; a seeker on the legs took 3
st = {'w': 0, 'base': 0, 'proj': 0, 'best': 1e9, 'seen': 0, 'fire': 0}


def boss():
    pl = e.r32(S['g_player'])
    bs = [ob for r, ob in pool_objects(e) if tag(e.r32(ob)) == 'Boss']
    if not bs or not pl: return bs[0] if bs else 0
    return min(bs, key=lambda o: math.hypot(e.rf(o + 0x50) - e.rf(pl + 0x50), e.rf(o + 0x54) - e.rf(pl + 0x54)))


def instances(name):
    for c in range(0x80112B08 - 0x30 * 40, 0x80112B08 + 0x30 * 40, 0x30):
        if tag(e.r32(c)) != name: continue
        cnt, size, head = e.r32(c + 8), e.r32(c + 12), e.r32(c + 16)
        return [head + i * size for i in range(cnt)]
    return []


def script(e, n):
    if st['w'] >= len(WEAPONS):
        e.stop(); return
    name, presses, idx, cls, shooter, rng, shots, near = WEAPONS[st['w']]
    if n == st['base'] + 60: e.load_state(os.path.join(paths.STATES, STATE))
    if n == st['base'] + 62:
        inject(e)
        if os.environ.get('NOFIX'):
            code = (Path(paths.WORK) / 'main.bin').read_bytes()
            for a in FIX_HOOKS: e.w32(a, struct.unpack_from('>I', code, a - 0x80001EC0)[0])
    if n < st['base'] + 66: return
    k = n - st['base'] - 66
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + HUMN_HP, 100.0)
    b = BTN['CU'] if k < presses * 20 and k % 20 < 4 else 0
    t0 = presses * 20
    if k >= t0 + 10: b |= BTN['Z']
    y = 0
    if k >= t0 + 40 and not st['fire']:            # walk up to the weapon's range (locked: stick up = toward it)
        ob = boss()
        d = math.hypot(e.rf(ob + 0x50) - e.rf(pl + 0x50), e.rf(ob + 0x54) - e.rf(pl + 0x54))
        if d > rng: y = 60
        else: st['fire'] = k
    f = st['fire'] or 10 ** 9
    if k == t0 + 40:
        lk = e.r32(S['g_lock'])
        check(f'{name}: weapon selected and the AT-ST locked',
              e.r16(pl + 0xB8) == idx and lk and tag(e.r32(lk)) == 'Boss',
              f'weapon {e.r16(pl + 0xB8)} lock {tag(e.r32(lk)) if lk else "-"}')
        st['old'] = {o for o in instances(cls) if e.r32(o + shooter) == pl}
    if k == f:
        st['hp0'] = e.rf(boss() + BOSS_HP)
        print(f'{k:4d} firing from {math.hypot(e.rf(boss() + 0x50) - e.rf(pl + 0x50), e.rf(boss() + 0x54) - e.rf(pl + 0x54)):.0f} units', flush=True)
    if f + 1 <= k < f + 1 + 12 * shots and (k - f - 1) % 12 < 4: b |= BTN['B']
    if k > f + 1:
        ob = boss()
        if not st['proj']:
            for o in instances(cls):
                if e.r32(o + shooter) == pl and o not in st['old'] and e.rf(o + 0x58) > -1000 and e.rf(o + 0x50) != 0:
                    st['proj'] = o
        o = st['proj']
        if o and ob and tag(e.r32(o)) == cls and e.rf(o + 0x58) > -1000:
            st['seen'] += 1
            c = (e.rf(ob + 0x50), e.rf(ob + 0x54), e.rf(ob + 0x58) + e.rf(ob + 0xAC) * 0.9)
            p = (e.rf(o + 0x50), e.rf(o + 0x54), e.rf(o + 0x58))
            st['best'] = min(st['best'], math.dist(p, c))
            if st['seen'] % 6 == 1:
                print(f'{k:4d} {name} at ({p[0]:.1f},{p[1]:.1f},{p[2]:.1f}) cockpit ({c[0]:.1f},{c[1]:.1f},{c[2]:.1f})'
                      f' dist {math.dist(p, c):.1f}', flush=True)
    if k >= f + 160:
        hp = e.rf(boss() + BOSS_HP)
        check(f'{name}: the shot reaches the cockpit', st['seen'] and st['best'] < near,
              f'closest {st["best"]:.1f} units over {st["seen"]} frames')
        check(f'{name}: the AT-ST takes damage', st['hp0'] - hp > DAMAGE, f'health {st["hp0"]:.1f} -> {hp:.1f}')
        st.update(w=st['w'] + 1, base=n, proj=0, best=1e9, seen=0, fire=0)
    if k > t0 + 400: check(f'{name}: got within range', False); st.update(w=st['w'] + 1, base=n, fire=0)
    e.pad(b, 0, y)


e.run(script)
sys.exit(report())
