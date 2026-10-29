"""Make the savestates the build's assets are made from, from your own ROM, into local/states (paths.STATES).

    python3 bootstrap.py <rom> [--tests] [--only name,...] [--force]

In dependency order, each skipped when present (unless --force); each recipe is one emulator process
(states_make.py, states_dash.py), its output in local/run/bootstrap/<name>.log. Intermediate states (a boot into a
level the teleports start from) stay in local/run/bootstrap/. Each made state is checked: its level id, and the
player's place within 2 units of the one the assets were made from; a miss stops with the numbers.
--tests adds the tests' states (TESTS: places from debug teleport points, Next Level, a written place, a debug-menu
item, a ride; checked against the states the tests were written on); the ones made at an event (a fight, a timed
arrival, the gladiator's second phase, the dianoga woken) are also checked by that event read from their RAM (EVENTS).
"""
import argparse, os, shutil, subprocess, sys
import paths
from states_cmp import ram, player
import math, struct

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(paths.RUN, 'bootstrap')
# boot's first number: the level select carousel's index (game.py)
GALL_BOOT = os.path.join(TMP, 'gall_boot.st')
ECHO_5 = os.path.join(TMP, 'echo_5.st')
XIZ_BOOT = os.path.join(TMP, 'xiz_boot.st')
ECHO_TP5 = os.path.join(TMP, 'echo_tp5.st')
ECHO_5_LATE = os.path.join(TMP, 'echo_5_late.st')
OM_INV = os.path.join(TMP, 'om_inv.st')
SEW_BOOT = os.path.join(TMP, 'sew_boot.st')
SEW_POOL = os.path.join(TMP, 'sew_pool.st')
# name: (recipe argv for states_make.py / a script, M64CPU, needs, level id, place or None). frame=N: saved at the
# game frame (0x8018E9B0) of the state the assets were made from: the player's place (on a moving level), Dash's
# idle and the level's animations follow it (Dash's poses from a gall_tp5 64 frames early: 1732 mesh bytes differ)
RECIPES = {
    'gall_boot': (['boot', 4, GALL_BOOT, 'onward'], 2, [], 14, None),
    'play': (['boot', 1, 'play.st', 'frame=1372'], 2, [], 4, (-356.6, 80.5, 0.0)),
    'lvl0': (['boot', 0, 'lvl0.st', 'frame=723'], 2, [], 3, None),
    'lvl5': (['boot', 5, 'lvl5.st', 'onward', 'frame=199'], 2, [], 17, None),
    'om': (['boot', 3, 'om.st', 'onward', 'frame=105'], 2, [], 8, (-499.8, -398.8, None)),
    'sky': (['boot', 9, 'sky.st', 'onward', 'frame=749'], 2, [], 30, None),
    'ast': (['boot', 2, 'ast.st', 'frame=824'], 2, [], 6, None),
    'gall_tp5': (['teleport', GALL_BOOT, 0, 62.3, 'gall_tp5.st', 'frame=1066'], 2, ['gall_boot'], 14, (62.3, -150.4, 227.9)),
    # Next Level alone lands on the place itself; no teleport: a teleport detour passes other zones, and the game
    # rebases those zones' vertex records (0x800BCD80: x, y relative to the zone base +0x14) to the base current then
    # (0x800E7C48), so the shaft's meshes the assets read would keep another base (whole 100-unit shifts)
    'gall_6b': (['next', GALL_BOOT, 1, 'gall_6b.st', 'frame=449'], 2, ['gall_boot'], 15, (-628.9, -517.6, 113.9)),
    # the intro (sub-level 0) on Leebo's "Sir, we've made contact with the Rebels.": its overlays (gall_asset.py
    # LEEBO_TURN) loaded; 11360 VIs from This Level = the game's frame counter 5680
    'leebo_turn': (['level', 'play.st', 0, 11360, 'leebo_turn.st'], 0, ['play'], 0, None),
    # (the poses' frame counter 0x8018E9B0 as in the states in use: stand 1141 at 150 VIs, jet 1196; the places are
    # the states' own, read without running them)
    'gall_dash_stand': (['states_dash.py', 'stand', 150], 0, ['gall_tp5'], 14, (62.3, -150.4, 227.9)),
    'gall_dash_jet': (['states_dash.py', 'jet'], 0, ['gall_tp5'], 14, (62.1, -150.2, 249.1)),
}

# The tests' states (--tests): the same fields; places and frames those of the states the tests were written on.
# `place` (states_make.py) only where the place is no teleport point (a written place holds on static ground).
TESTS = {
    # Sub-level 4: the catwalk is debug Teleport point 5. Reached by the teleports (points 1-4 on the way), the
    # level's zones keep the vertex bases those points left, and the troopers near the bridge are where they are when
    # the player arrives ~70 frames before the save; a place written from the level's start and held there ~24 s
    # brought two troopers onto the crevasse spot's paths (5 catches fewer in t_hang_spots on its 48 walks)
    'echo_catwalk': (['teleport', 'play.st', 0, 136.1, 'echo_catwalk.st', 'frame=1999'], 2, ['play'],
                     4, (136.1, -105.5, 2.0)),
    'echo_tp5': (['teleport', 'play.st', 0, 136.1, ECHO_TP5, 'frame=1985'], 2, ['play'], 4, None),
    'echo_crevasse': (['place', ECHO_TP5, 131.97, -39.03, 2.0, 0.0, 'echo_crevasse.st', 'frame=2087'], 2, ['echo_tp5'],
                      4, (132.0, -39.0, 2.0)),
    # the gap block stays written from the level's start: from Teleport point 5 its walks caught 26 of 48 (31 on the
    # state the tests were written on, 29-31 this way); its narrow block makes the paths split on small differences
    'echo_gapblock': (['place', 'play.st', 150.78, -94.30, 1.0, 296.65, 'echo_gapblock.st', 'frame=2062'], 2,
                      ['play'], 4, (150.8, -94.3, 1.0)),
    'echo_5': (['next', 'play.st', 1, ECHO_5], 2, ['play'], 5, None),
    'echo_cave': (['place', ECHO_5, -99.09, 25.31, -51.0, 90.0, 'echo_cave.st', 'frame=798'], 2, ['echo_5'],
                  5, (-99.1, 25.3, -51.0)),
    # the stairs (Teleport point 4) reached ~65 frames before the save: arrived from sub-level 5's start at once,
    # Dash stood there ~10 s, the troopers above went to their attack state (+0x78 3) and one stood on the top step,
    # blocking the stairs t_stairs runs up (and the frames cost more: Dash ran ~40 % further in 60 VIs)
    'echo_5_late': (['wait', ECHO_5, 30, ECHO_5_LATE, 'frame=440'], 2, ['echo_5'], 5, None),
    'echo_stairs': (['teleport', ECHO_5_LATE, 0, 263.7, 'echo_stairs.st', 'frame=948'], 2, ['echo_5_late'],
                    5, (263.7, 24.7, -78.3)),
    # teleport detours leave Gall's zones on other vertex bases (see gall_6b): the hang tests read the geometry by
    # collision, not raw records. A trooper walks over the hangar floor where t_hang_more floor puts Dash and where
    # he is depends on the arrival frame (6.8 from the spot here, 0.9 on the older state): the test kills the
    # troopers near the spot rather than any recipe picking his place
    'gall_tp1': (['teleport', GALL_BOOT, 0, 33.0, 'gall_tp1.st', 'frame=666'], 2, ['gall_boot'], 14, (33.0, 35.0, 277.5)),
    'gall_tp6': (['teleport', GALL_BOOT, 0, -590.6, 'gall_tp6.st', 'frame=1166'], 2, ['gall_boot'],
                 14, (-590.6, 326.6, 185.1)),
    'sup': (['boot', 6, 'sup.st', 'frame=1010'], 2, [], 20, (-6.6, 11.5, 0.0)),
    'xiz_boot': (['boot', 8, XIZ_BOOT], 2, [], 26, None),
    'xiz_glad': (['teleport', XIZ_BOOT, 1, 16.3, 'xiz_glad.st', 'frame=388'], 2, ['xiz_boot'],
                 27, (16.3, -44.1, 78.9)),
    'om_ig88': (['next', 'om.st', 1, 'om_ig88.st', 'frame=898'], 2, ['om'], 10, (-9.8, -23.7, -1.5)),
    # the AT-ST fight: Teleport point 5 of sub-level 5 is the arena; by the save the cutscene is over (EVENTS). Saved
    # at frame 880, not the older state's 632: arriving this way his fight starts later (at 632 he is still by his
    # spawn, at 560 in the cutscene); at 880 he walks where he stood on the older state (-253, -344), and t_boss
    # passes from 760 to 940 (at 730 and before, its circle strafe takes Dash into the doorway, out of sight)
    'echo_atst': (['teleport', ECHO_5, 0, -264.0, 'echo_atst.st', 'frame=880'], 2, ['echo_5'], 5, (-264.0, -288.5, 0.0)),
    # Get all stuff 10 frames after it (the older state: 50): t_weapons walks up to 22 units of the walking AT-ST
    # within ~240 frames of its 400 (fired at 246 here as on the older state; saved at 950 and later: 276..290, past)
    'echo_atst_arms': (['menu', 'echo_atst.st', 'get_all', 'echo_atst_arms.st', 'wait=20', 'frame=890'], 2,
                       ['echo_atst'], 5, (-264.0, -288.5, 0.0)),
    # the train's drones: Invincibility first (with no input and none, Dash is knocked off the cars at ~frame 557 and
    # starts again), then the ride with no input to the older state's frame: a TGun comes within ~8 units
    'om_inv': (['menu', 'om.st', 'invincible', OM_INV], 2, ['om'], 8, None),
    'om_drones': (['ride', OM_INV, 60, 'om_drones.st', 'frame=1961'], 2, ['om_inv'], 8, (-496.0, 193.1, None)),
    # one Teleport from om_drones: the point rides with the train (x -297.3 never comes within 2; -295.6 is the older
    # state's own reading); saved at the older state's frame (200 VIs on, the train has carried Dash 40 units off)
    'om_ttrp': (['teleport', 'om_drones.st', 0, -295.6, 'om_ttrp.st', 'frame=2063'], 2, ['om_drones'], 8, (-296.0, -160.0, None)),
    # the gladiator's flying phase, Dash back on the maze wall after a death (states_make.py glad2)
    'xiz_glad2': (['glad2', 'xiz_glad.st', 'xiz_glad2.st'], 2, ['xiz_glad'], 27, (31.0, -34.0, 123.4)),
    # the dianoga's pool: Teleport point (672.0, -7.6, 101) of sub-level 25 (the third from its start), then Dash
    # swims 18 units off the eye and the dianoga is woken by its parts' bit 0x400 (states_make.py dianoga)
    'sew_boot': (['boot', 7, SEW_BOOT, 'onward'], 2, [], 25, None),
    'sew_pool': (['teleport', SEW_BOOT, 0, 672.0, SEW_POOL], 2, ['sew_boot'], 25, (672.0, -7.6, None)),
    'sew_dianoga': (['dianoga', SEW_POOL, 'sew_dianoga.st'], 2, ['sew_pool'], 25, (690.0, -8.0, 58.6)),
    # sew_428 is not made: Dash swims there and a written place does not enter the swim state (he stands under the
    # surface, 3.3 below it); no test uses it
}
RECIPES.update(TESTS)
# The asset builders' sources, saved also under these names (a copy of the made state): the Gall Run tools load
# these, the tests keep the names above
SRC = {'lvl5': 'src_stage1.st', 'om': 'src_stage2.st', 'ast': 'src_base.st', 'sky': 'src_space.st',
       'play': 'src_model.st', 'lvl0': 'src_portrait.st', 'leebo_turn': 'src_intro.st'}
TOL = {'om_drones': 5, 'om_ttrp': 5, 'sew_dianoga': 5}  # places that move (the train, the swim): within 5 units


def _boss_fighting(E):
    """The level's Boss (model +0x78) past its cutscene: +0x60 -0.01 (+0.01 dormant), not destroyed (+6 bit 0x20)."""
    i = E.find(b'Boss', 0x100000)
    while i >= 0:
        if i % 4 == 0 and E[i + 0x78:i + 0x7C] == b'ATST':
            st, = struct.unpack_from('>f', E, i + 0x60); fl, = struct.unpack_from('>H', E, i + 6)
            return st < 0 and not fl & 0x20, f'AT-ST state {st:.2f}, flags {fl:#x}'
        i = E.find(b'Boss', i + 1)
    return False, 'no AT-ST'


def _get_all(E):
    ok, txt = _boss_fighting(E)
    n, = struct.unpack_from('>h', E, 0x0E1B54)            # Get all stuff's own write (reverse-engineering.md)
    return ok and n == 1000, f'{txt}, 0x800E1B54 {n}'


def _u32(E, a): return struct.unpack_from('>I', E, a & 0xFFFFFF)[0]
def _f(E, a): return struct.unpack_from('>f', E, a & 0xFFFFFF)[0]


def _invincible(E):
    n = _u32(E, 0x800E1B2C)                               # the debug menu's Invincibility
    return n == 1, f'Invincibility {n}'


def _ttrp_near(E):
    """A live TTrp (the train's troopers: class table 0x80112FB8, count +8, size +12, pool +16) within 15 units."""
    ok, txt = _invincible(E)
    _, p = player(E)
    cls = 0x80112FB8
    cnt, size, o = _u32(E, cls + 8), _u32(E, cls + 12), _u32(E, cls + 16)
    ds = sorted(math.hypot(_f(E, a + 0x50) - p[0], _f(E, a + 0x54) - p[1]) for a in (o + i * size for i in range(min(cnt, 200)))
                if _u32(E, a) == _u32(E, cls) and _f(E, a + 0x60) > 0)
    return ok and bool(ds) and ds[0] < 15, f'{txt}, nearest live TTrp {ds[0] if ds else -1:.1f}'


def _glad_flying(E):
    ok, txt = _invincible(E)
    ai = _u32(E, 0x8019F4C4 + 0x584)                      # the gladiator's AI state: 5 flying (t_glad.py)
    return ok and ai == 5, f'{txt}, gladiator AI state {ai}'


def _dianoga_woken(E):
    ok, txt = _invincible(E)
    parts = [0x801BE098, 0x801BE1B8, 0x801BE2D8, 0x801BE3F8, 0x801BE518]
    _, p = player(E)
    d = math.hypot(_f(E, parts[0] + 0x50) - p[0], _f(E, parts[0] + 0x54) - p[1])
    bits = [_u32(E, a + 0x74) for a in parts]
    return (ok and all(b & 0x400 for b in bits) and abs(d - 18) <= 3,
            f'{txt}, parts +0x74 {",".join(hex(b) for b in bits)}, {d:.1f} from the eye')


# The event each state is made at, read from its RAM: (ok, text).
EVENTS = {'echo_atst': _boss_fighting, 'echo_atst_arms': _get_all, 'om_drones': _invincible, 'om_ttrp': _ttrp_near,
          'xiz_glad2': _glad_flying, 'sew_dianoga': _dianoga_woken}


def _out(argv):
    return max(i for i, a in enumerate(argv) if isinstance(a, str) and a.endswith('.st'))


def path_of(name):
    argv = RECIPES[name][0]
    out = argv[_out(argv)] if argv[0] != 'states_dash.py' else name + '.st'
    return out if os.path.isabs(out) else os.path.join(paths.STATES, out)


def check(name):
    E = ram(path_of(name))
    lvl, = struct.unpack_from('>H', E, 0x13CE0E)
    want_lvl, want_at = RECIPES[name][3], RECIPES[name][4]
    _, p = player(E)
    gf, = struct.unpack_from('>I', E, 0x18E9B0)
    where = '(%.1f, %.1f, %.1f)' % p if p else 'no player'
    ok = lvl == want_lvl and (want_at is None or p is not None and
                              all(w is None or abs(a - w) <= TOL.get(name, 2) for a, w in zip(p, want_at)))
    ev = ''
    if name in EVENTS:
        eok, ev = EVENTS[name](E); ok = ok and eok; ev = '; ' + ev
    print(f'{"OK  " if ok else "MISS"} {name}: level {lvl} (want {want_lvl}), frame {gf}, player {where}'
          + (f' (want {want_at})' if want_at else '') + ev, flush=True)
    return ok


def nogall_build(rom):
    """A payload to inject for Dash's poses (g_player, the Cheats screen) before the assets exist: the patch built
    without the Gall Run (needs no asset; its poses equal the full build's)."""
    out = os.path.join(paths.BUILD, 'nogall')
    if not os.path.exists(os.path.join(out, 'payload.elf')):
        log = os.path.join(TMP, 'nogall_build.log')
        with open(log, 'w') as f:
            r = subprocess.run([sys.executable, 'build.py', rom, '--without', 'gallrun', '--out', out],
                               cwd=os.path.join(paths.ROOT, 'sote-patch'), stdout=f, stderr=subprocess.STDOUT)
        if r.returncode: sys.exit(f'the --without gallrun build failed, see {log}')
    return out


def make(name, rom, force, done):
    if name in done: return
    argv, cpu, needs, _, _ = RECIPES[name]
    for d in needs: make(d, rom, False, done)
    done.add(name)
    if os.path.exists(path_of(name)) and not force:
        print(f'have {name}', flush=True); copy_src(name, False); return
    env = dict(os.environ, M64CPU=str(cpu), SHOTS='bootstrap_' + name)
    if argv[0] == 'states_dash.py':
        cmd = [sys.executable, os.path.join(HERE, argv[0]), rom] + [str(a) for a in argv[1:]]
        env['PAYLOAD_BUILD'] = nogall_build(rom)
    else:
        args = [str(a) for a in argv]
        args[_out(argv)] = path_of(name)
        cmd = [sys.executable, os.path.join(HERE, 'states_make.py'), args[0], rom] + args[1:]
    log = os.path.join(TMP, name + '.log')
    print(f'make {name} ({log})', flush=True)
    with open(log, 'w') as f:
        r = subprocess.run(cmd, cwd=HERE, env=env, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode or not os.path.exists(path_of(name)):
        sys.exit(f'{name}: the recipe failed (exit {r.returncode}), see {log}')
    if not check(name):
        sys.exit(f'{name}: not the place the assets were made from, see {log}')
    copy_src(name, True)


def copy_src(name, fresh):
    """The state's copy under its source name (SRC), made when missing or the state was just made."""
    if name not in SRC: return
    dst = os.path.join(paths.STATES, SRC[name])
    if fresh or not os.path.exists(dst):
        shutil.copyfile(path_of(name), dst); print(f'copy {name} -> {SRC[name]}', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    final = [n for n in RECIPES if not path_of(n).startswith(TMP + os.sep)]       # not the intermediate ones
    ap.add_argument('--only', help='comma-separated names: ' + ', '.join(final))
    ap.add_argument('--tests', action='store_true', help="also the tests' states: " + ', '.join(n for n in final if n in TESTS))
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True); os.makedirs(paths.STATES, exist_ok=True)
    rom = os.path.abspath(a.rom)
    names = a.only.split(',') if a.only else [n for n in final if a.tests or n not in TESTS]
    done = set()
    for n in names: make(n, rom, a.force, done)
