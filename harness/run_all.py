"""Run the test suite against the current payload build and print PASS/FAIL per test.

    python3 run_all.py [--rom <rom>] [-j N] [name ...]   # names: a subset, e.g. move 'hang_*'

Each test (tests/t_*.py) runs in its own process (M64CPU=0, SHOTS=reg_<name>), N at a time (-j, default 4: the
Mac has 8 cores; the longest tests start first); its full output goes to local/run/reg/<name>.log and
the checks it printed decide the verdict (testlib.report()). A test running longer than
--timeout (600 s) is killed and fails (t_orbit once hung for 49 minutes).
The ROM only boots the core: every test loads a savestate and injects the payload from
PAYLOAD_BUILD (default local/build/sote-patch), so the original ROM is fine.
Exit code 1 if any test failed.
"""
import argparse, fnmatch, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
ROM = paths.ROM
SUITE = [
    ('move', 't_move.py'),
    ('lock', 't_lock.py'),
    ('crate', 't_crate.py'),
    ('orbit', 't_orbit.py'),
    ('fog', 't_fog.py'),
    ('fogback', 't_fogback.py'),
    ('holdz', 't_holdz.py'),
    ('recenter', 't_recenter.py'),
    ('stairs', 't_stairs.py'),
    ('stairs_orig', 't_stairs.py', 'orig'),
    ('hang_climb', 't_hang.py', 'climb'),
    ('hang_drop', 't_hang.py', 'drop'),
    ('hang_jump', 't_hang.py', 'jump'),
    ('hang_kill', 't_hang.py', 'kill'),
    ('hang_fire', 't_hang.py', 'fire'),
    ('hang_dirs', 't_hang_dirs.py'),
    ('hang_spots', 't_hang_spots.py'),
    ('hang_more', 't_hang_more.py'),
    ('hang_gap', 't_hang_gap.py'),
    ('hang_bridge', 't_hang_bridge.py'),
    ('hang_jetdrop', 't_hang_jetdrop.py'),
    ('hang_jethang', 't_hang_jetdrop.py', 'hang'),
    ('hang_jet', 't_hang_jet.py'),
    ('hang_jumpcatch', 't_hang_jumpcatch.py'),
    ('hang_plat', 't_hang_plat.py'),
    ('hang_cheat_tp', 't_hang_cheats.py', 'tp'),
    ('hang_cheat_lvl', 't_hang_cheats.py', 'level'),
    ('edge', 't_edge.py'),
    ('train_jump', 't_train.py', 'jump'),
    ('train_lock', 't_train.py', 'lock'),
    ('trainturn', 't_trainturn.py'),
    ('trainz', 't_trainz.py'),
    ('traindroid', 't_traindroid.py'),
    ('switch', 't_switch.py', 'om_drones.st', '900'),
    ('boss', 't_boss.py', '1200'),
    ('ig88', 't_ig88.py'),
    ('ig88near', 't_ig88near.py'),
    ('weapons', 't_weapons.py'),
    ('lockpitch', 't_lockpitch.py'),
    ('trainwall', 't_trainwall.py'),
    ('glad', 't_glad.py', 'walk'),
    ('glad_fly', 't_glad.py', 'fly'),
    ('swimlock', 't_swimlock.py'),
    ('swimcycle', 't_swimlock.py', 'cycle'),
    ('sight', 't_sight.py'),
    ('cheats', 't_cheats.py'),
    ('fuel', 't_fuel.py'),
    ('leebo', 't_leebo.py'),
    ('ship', 't_cheat_ship.py'),
    ('ship_other', 't_cheat_ship.py', 'play.st'),
    ('wampa_cave', 't_wampa.py', 'cave'),
    ('wampa_trooper', 't_wampa.py', 'trooper'),
    ('wampa_hoth', 't_wampa.py', 'hoth'),
    ('wampa_hoth_off', 't_wampa.py', 'hoth_off'),
    ('friendly', 't_friendly.py'),
    ('friendly_off', 't_friendly.py', 'row_off'),
    ('off_controls', 't_off.py', 'controls'),
    ('off_lock', 't_off.py', 'lock'),
    ('off_hang', 't_off.py', 'hang'),
    ('off_mid', 't_off.py', 'mid'),
]
# Seconds each took (2026-10-06), to start the long ones first; others count as 15.
SLOW = {'hang_spots': 168, 'hang_jet': 117, 'hang_jumpcatch': 70, 'hang_dirs': 59, 'hang_bridge': 59,
        'edge': 25, 'hang_cheat_lvl': 18}


def run_one(rom, name, script, args, logs, timeout):
    log = os.path.join(logs, name + '.log')
    t0 = time.time()
    env = dict(os.environ, M64CPU='0', SHOTS='reg_' + name)
    with open(log, 'w') as f:
        try:
            rc = subprocess.run([sys.executable, os.path.join('tests', script), rom, *args], cwd=HERE, env=env,
                                stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    out = open(log).read()
    fails = re.findall(r'^CHECK FAIL (.*)$', out, re.M)
    res = re.search(r'^RESULT: (\w+) ?(\S*)', out, re.M)
    ok = rc == 0 and res and res.group(1) == 'PASS'
    verdict = ('PASS ' + res.group(2)) if ok else ('FAIL ' + (res.group(2) if res and rc != 'timeout' else f'({rc}, no result)'))
    return name, ok, verdict, time.time() - t0, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=ROM)
    ap.add_argument('-j', '--jobs', type=int, default=4)
    ap.add_argument('--timeout', type=int, default=600)
    ap.add_argument('names', nargs='*')
    a = ap.parse_args()
    a.rom = os.path.abspath(a.rom)                # the tests run in harness/
    names = [t[0] for t in SUITE]
    want = set()                                 # names or shell-style patterns: 'hang_*'
    for n in a.names:
        hit = fnmatch.filter(names, n)
        if not hit: sys.exit(f'unknown test(s): {n}; known: {", ".join(names)}')
        want.update(hit)
    a.names = want
    logs = os.path.join(paths.RUN, 'reg'); os.makedirs(logs, exist_ok=True)
    todo = [t for t in SUITE if not a.names or t[0] in a.names]
    todo.sort(key=lambda t: -SLOW.get(t[0], 15))
    t0, results = time.time(), []
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        futs = [pool.submit(run_one, a.rom, name, script, args, logs, a.timeout) for name, script, *args in todo]
        for fu in as_completed(futs):
            name, ok, verdict, dt, fails = fu.result()
            print(f'{name:14s} {verdict:14s} {dt:5.0f} s', flush=True)
            for x in fails: print(f'{"":14s}   - {x}')
            results.append((name, ok))
    failed = [n for n, ok in results if not ok]
    # In parallel some runs go bad halfway (garbage reads, no catches; cause not found yet) and
    # pass alone: rerun the failures one at a time and say which ones only failed in parallel.
    flaky = []
    if failed and a.jobs > 1:
        print(f'rerunning {len(failed)} failed one at a time ...', flush=True)
        for name, script, *args in [t for t in todo if t[0] in failed]:
            name, ok, verdict, dt, fails = run_one(a.rom, name, script, args, logs, a.timeout)
            print(f'{name:14s} {verdict:14s} {dt:5.0f} s  (alone)', flush=True)
            for x in fails: print(f'{"":14s}   - {x}')
            if ok: flaky.append(name)
        failed = [n for n in failed if n not in flaky]
    print(f'wall {time.time() - t0:.0f} s' + (f'; failed only in parallel: {" ".join(flaky)}' if flaky else ''), flush=True)
    print(f'\n{len(results) - len(failed)}/{len(results)} passed' + (f'; failed: {" ".join(failed)}' if failed else '')
          + f'\nlogs: {logs}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
