"""Shared pieces of the t_*.py tests: fake targets, the fog formula, pass/fail checks.

    from testlib import FAKE, make_fake, check, report
    ...
    check('facing reaches the target heading', abs(err) < 5, f'err {err:.1f}')
    ...
    e.run(script)
    sys.exit(report())

check() prints `CHECK PASS|FAIL <name> <detail>` as it goes; report() prints `RESULT: PASS|FAIL`
plus the failed names and returns the exit code (1 if any check failed or none ran), so
run_all.py and the shell can tell a pass from a fail without reading the numbers.
"""
import sys

FAKE = 0x807E0000                 # free Expansion Pak RAM above the payload (inject.PAYLOAD_MAX)
TTRP = 0x54547270                 # 'TTrp' (a trooper class tag)

_checks = []


def make_fake(e, pos=None, hp=5.0):
    """A targetable fake object at FAKE (not in the game's pool: lock it with g_lock or g_test_target)."""
    for i in range(0, 0x100, 4): e.w32(FAKE + i, 0)
    e.w32(FAKE, TTRP)
    e.w32(FAKE + 4, 2)                        # +6: targetable
    e.wf(FAKE + 0x60, hp)                     # health
    e.wf(FAKE + 0x6C, 1.2)                    # height
    if pos: place_fake(e, *pos)


def place_fake(e, x, y, z):
    e.wf(FAKE + 0x50, x); e.wf(FAKE + 0x54, y); e.wf(FAKE + 0x58, z)


def fog_expected(e, d):
    """Fog amount (0..1) at view depth d from the level's fog globals and perspective (as the payload)."""
    lo, hi = e.r16(0x800E7AD8), e.r16(0x800E7ADC)
    n, f = e.rf(0x80192F1C), e.rf(0x80192F20)
    if (e.r32(0x800D2538) >> 24) or hi <= lo or d <= n: return 0.0
    zw = (f + n) / (f - n) - 2 * f * n / ((f - n) * d)
    return min(1.0, max(0.0, ((zw + 1) * 500 - lo) / (hi - lo)))


def check(name, ok, detail=''):
    ok = bool(ok)
    _checks.append((name, ok))
    print(f"CHECK {'PASS' if ok else 'FAIL'} {name}" + (f'  ({detail})' if detail else ''), flush=True)
    return ok


def report():
    failed = [n for n, ok in _checks if not ok]
    if not _checks:
        print('RESULT: FAIL (no checks ran: the run stopped early?)', flush=True)
        return 1
    print(f"RESULT: {'FAIL' if failed else 'PASS'} {len(_checks) - len(failed)}/{len(_checks)}"
          + (''.join(f'\n  failed: {n}' for n in failed)), flush=True)
    sys.stdout.flush()
    return 1 if failed else 0
