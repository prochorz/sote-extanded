"""Z still held after the lock ends: Dash keeps his facing and strafes, the gun doesn't pitch.

    M64CPU=0 python3 t_holdz.py <rom> [state]

A fake target (the only candidate, `g_test_target`) stands 30 units in front of Dash. Z locks it,
Dash runs at it, it dies (health 0) with Z still held. Expected while Z stays held: facing stays
put, the stick moves him forward / sideways / back, the aim pitch (`+0x1B4`) stays ~0. Then the
target comes back in front and the lock should pick it up again; after Z is released, a fresh Z
with no target gives the native aim (stick forward pitches the gun).
"""
import math, os, sys
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import FAKE, make_fake, place_fake, check, report

S = syms()
e = Emu(sys.argv[1])
state = os.path.join(paths.STATES, sys.argv[2] if len(sys.argv) > 2 else 'play.st')
PITCH = 0x1B4
# (start, end, Z, stick x, stick y, label)
PHASES = [(0, 10, 0, 0, 0, 'idle'), (10, 40, 1, 0, 80, 'lock+run'), (40, 100, 1, 0, 80, 'hold fwd'),
          (100, 150, 1, 80, 0, 'hold right'), (150, 200, 1, 0, -80, 'hold back'),
          (200, 240, 1, 0, 0, 'revive'), (240, 260, 0, 0, 0, 'release'), (260, 320, 1, 0, 80, 'native')]
st = {'face0': None, 'held': [], 'rel': {}, 'locks': set()}


def script(e, n):
    if n == 60: e.load_state(state)
    if n == 62:
        inject(e); e.w32(S['g_test_skip_los'], 1)
        make_fake(e)
        e.w32(S['g_test_target'], FAKE)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    if not pl: return
    p = [e.rf(pl + 0x50 + 4 * j) for j in range(3)]
    face = e.rf(pl + 0x8C) + 90
    if k == 5:      # put the target in front of Dash
        place_fake(e, p[0] + 30 * math.cos(math.radians(face)), p[1] + 30 * math.sin(math.radians(face)), p[2])
    if k == 40: e.wf(FAKE + 0x60, 0.0)          # killed while Z is still held
    if k == 200:    # back to life, 25 units in front
        place_fake(e, p[0] + 25 * math.cos(math.radians(face)), p[1] + 25 * math.sin(math.radians(face)), p[2])
        e.wf(FAKE + 0x60, 5.0)
    if k == 240: e.wf(FAKE + 0x60, 0.0)         # gone for the native-aim check
    lab = '-'
    for a, b, z, x, y, l in PHASES:
        if a <= k < b:
            e.pad(BTN['Z'] if z else 0, x, y); lab = l
    if e.r32(S['g_lock']) == FAKE: st['locks'].add(k)
    if k == 10: st['face0'] = face
    if 40 <= k < 200: st['held'].append((face - st['face0'], e.rf(pl + PITCH)))
    if k == 300: st['native'] = e.rf(pl + PITCH)
    if k >= 320:
        df = max(abs((d + 180) % 360 - 180) for d, _ in st['held'])
        pm = max(abs(p) for _, p in st['held'])
        check('Z locks the fake target', any(20 <= t < 40 for t in st['locks']))
        check('facing kept while Z stays held after the kill', df < 1, f'max change {df:.1f}')
        check('no gun pitch while Z stays held', pm < 3, f'max |pitch| {pm:.1f}')
        for t, want, name in ((90, 0, 'forward'), (140, -90, 'right'), (190, 180, 'back')):
            r = st['rel'].get(t, float('nan'))
            check(f'stick {name} strafes {name}', abs((r - want + 180) % 360 - 180) < 35, f'dir vs facing {r:.0f}')
        check('the revived target is locked again (Z still held)', any(200 <= t < 240 for t in st['locks']))
        check('native aim after a fresh Z with no target', st['native'] < -20, f'pitch {st["native"]:.1f}')
        e.stop(); return
    if k % 10 == 0:
        if 'p' in st:
            dx, dy = p[0] - st['p'][0], p[1] - st['p'][1]
            mv = math.hypot(dx, dy)
            rel = (math.degrees(math.atan2(dy, dx)) - face + 540) % 360 - 180 if mv > 0.2 else float('nan')
        else: mv, rel = 0, float('nan')
        st['p'] = p; st['rel'][k] = rel
        lk = e.r32(S['g_lock'])
        print(f"{k:4d} {lab:10s} facing={(face + 180) % 360 - 180:7.1f} pitch={e.rf(pl + PITCH):6.1f}"
              f" moved={mv:5.1f} dir_vs_facing={rel:6.0f} lock={'fake' if lk == FAKE else hex(lk) if lk else '-'}", flush=True)


e.run(script)
sys.exit(report())
