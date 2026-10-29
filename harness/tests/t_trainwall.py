"""No lock through a train car's wall (states/om.st, a fake target).

    M64CPU=0 python3 t_trainwall.py <rom>

The sight check let a ray through when it stopped on level geometry less than 4 units short of
the target's aim point: on Ord Mantell an enemy standing right behind a car's wall or crate got
locked and shot at through it. Probe: per direction round Dash (every 30 degrees) the fake is
moved out 6, 8, ... 30 units until the ray from Dash's chest stops on a wall well short of it
(g_test_ray: hit distance and length of the last two sight rays). Then the fake goes 2.5 units
behind that wall (Z must not lock it unless a sight ray got past the wall untouched, e.g. the
camera's over a low wall; one direction may, a ray grazing a corner right at the target: with
the old 4 units 9 of 10 did) and 2 units in front of it (Z must lock it). Each trial
places the fake relative to Dash every frame (the cars move) and presses Z once.
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import HUMT_YAW
from testlib import FAKE, make_fake, place_fake, check, report

S = syms()
e = Emu(sys.argv[1])
PL = 0x801A7AF4
DIRS = list(range(0, 360, 30))
DISTS = list(range(6, 31, 2))
BEHIND, FRONT = 2.5, 2.0
st = {'dir': 0, 'dist': 0, 'phase': 'probe', 'wall': 0, 'base': 0,
      'walls': [], 'behind': [], 'front': []}


def trial_dist():
    if st['phase'] == 'probe': return DISTS[st['dist']]
    return st['wall'] + (BEHIND if st['phase'] == 'behind' else -FRONT)


def next_dir():
    st.update(dir=st['dir'] + 1, dist=0, phase='probe')


def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'om.st'))
    if n == 62: inject(e); make_fake(e)
    if n < 70: return
    if st['dir'] >= len(DIRS):
        print('walls:', ' '.join(f'{a}:{w:.1f}' for a, w in st['walls']), flush=True)
        check('walls found round Dash', len(st['walls']) >= 4, f'{len(st["walls"])}')
        bad = [a for a, ok in st['behind'] if ok]
        check('no lock 2.5 units behind a wall', len(bad) <= 1, f'locked behind the wall at {bad}')
        good = sum(ok for a, ok in st['front'])
        check('lock 2 units in front of it', good >= len(st['front']) * 0.75, f'{good}/{len(st["front"])}')
        e.stop(); return
    e.w32(0x800E1B2C, 1)                                   # invincible
    k = n - 70 - st['base']
    a, d = DIRS[st['dir']], trial_dist()
    f = math.radians(e.rf(PL + HUMT_YAW) + 90 + a)
    place_fake(e, e.rf(PL + 0x50) + d * math.cos(f), e.rf(PL + 0x54) + d * math.sin(f), e.rf(PL + 0x58))
    e.w32(S['g_test_target'], FAKE)
    if k == 0: e.w32(S['g_lock'], 0); e.w32(S['g_test_rays'], 0)
    e.pad(BTN['Z'] if 8 <= k < 12 else 0)
    if k < 14: return
    st['base'] = n - 69
    locked = e.r32(S['g_lock']) == FAKE
    if st['phase'] == 'probe':
        hd, ln = e.rf(S['g_test_ray']), e.rf(S['g_test_ray'] + 4)  # the chest ray goes first
        if e.r32(S['g_test_rays']) >= 1 and 0 < hd < ln - 4:
            st['wall'] = d * hd / ln
            st['walls'].append((a, st['wall']))
            st['phase'] = 'behind'
        elif st['dist'] + 1 < len(DISTS): st['dist'] += 1
        else: next_dir()
    elif st['phase'] == 'behind':
        rays = [e.rf(S['g_test_ray'] + 8 * j) for j in range(min(2, e.r32(S['g_test_rays'])))]
        seen = any(r < 0 for r in rays)                    # e.g. the camera sees over a low wall
        st['behind'].append((a, locked and not seen))
        print(f'dir {a:3d}: wall {st["wall"]:.1f}, behind it {"locked, a ray clear" if locked and seen else "LOCKED" if locked else "no lock"}', flush=True)
        st['phase'] = 'front'
    else:
        st['front'].append((a, locked))
        print(f'dir {a:3d}: in front of it {"locked" if locked else "NO LOCK"}', flush=True)
        next_dir()


e.run(script)
sys.exit(report())
