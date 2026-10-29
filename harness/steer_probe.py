"""Probe (not a SUITE test): the ship steering's second scheme (0x8009A30C, Stft, every space level), which the game gives
only to the profile name " Wolfy" (s16 0x800DD770, read at 0x8009A394 lui / 0x8009A398 lh, then bnez).

    M64CPU=0 python3 steer_probe.py <rom> off|stock

states/sky.st (Skyhook) with the current build injected, preset 0 written to s16 0x800D252C every VI. Phases of
60 VIs each from the first VI after the inject: stick X +80, released, D-left, stick Y +80. Per phase: the
Stft's yaw/pitch/roll (+0x14/+0x18/+0x1C, degrees, summed per-VI wrapped steps) and its position +0x08: the
whole step and its parts along the ship's right (+0x20) / forward (+0x30) / up (+0x40) rows taken at the
phase's start. One shot at the end of stick X (VI 59).

Measured (2026-10-26): the normal scheme turns on stick X (yaw -63, bank +21, 162 units right); the second
scheme rolls in place (roll +96, yaw 0, no sideways step). The second scheme's buttons are binding slots
+0x08/+0x0A (pitch) and +0x0C/+0x0E (sideways, 0x8009A8A8..0x8009AA04): unbound in preset 0 (its D-pad sits
in +0x10..+0x16), so D-left there does nothing; PRESET=2 binds them (D-left: 158 units left, roll -0.8).

off:   the game's instructions unchanged (the normal scheme).
stock: the game's own answer written into the read: 0x8009A398 -> addiu t9, zero, 1 (the second scheme).
No Cheats row for it: the second scheme is not a no-bank steering (stick X rolls in place, stick Y turns),
and its D-pad slots are bound only in Traditional.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # harness/
import paths
from m64 import Emu, BTN, HERE
from inject import inject
from testlib import check, report

MODE = sys.argv[2] if len(sys.argv) > 2 else 'off'
if MODE not in ('off', 'stock'):
    print(f'mode {MODE!r}: off or stock', flush=True)
    sys.exit(2)

e = Emu(sys.argv[1])
READ = 0x8009A398
ADDIU_T9_1 = 0x24190001
WOLFY, PRESET, BINDS = 0x800DD770, 0x800D252C, 0x800E6808
CLASSES, STFT = 0x80112808, 0x53746674
PH = 60
PRE = int(os.environ.get('PRESET', 0))           # the control preset written every VI (knob: 2 binds the D-pad in +0x08..+0x0E)
PHASES = [('stickX', 0, 80, 0), ('release', 0, 0, 0), ('Dleft', BTN['L_D'], 0, 0), ('stickY', 0, 0, 80)]
st = dict(ph={})


def w16(a, v):
    w = e.r32(a & ~3)
    e.w32(a & ~3, (w & 0xFFFF) | (v << 16) if (a & 2) == 0 else (w & 0xFFFF0000) | v)


def ship():
    a = CLASSES
    for _ in range(200):
        if e.r32(a) == STFT: return e.r32(a + 0x10)
        a += 0x30
    return 0


def vec(o, off): return [e.rf(o + off + 4 * i) for i in range(3)]
def ang(o): return [e.rf(o + 0x14 + 4 * i) for i in range(3)]
def wrap(d): return (d + 180) % 360 - 180


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(os.path.join(paths.STATES, 'sky.st'))
    if n == 62:
        inject(e)
        if MODE == 'stock': e.w32(READ, ADDIU_T9_1)
    if n < 66: return
    w16(PRESET, PRE)
    k = n - 66
    i, j = divmod(k, PH)
    if i >= len(PHASES):
        e.pad(0); e.stop(); return
    name, b, x, y = PHASES[i]
    s = st.get('s') or ship()
    if k == 0:
        st['s'] = s
        print(f"mode {MODE}: Stft {s:08x} preset was {e.r16(PRESET)} wolfy {e.r16(WOLFY)} read {e.r32(READ):08x} "
              f"preset {PRE} slots +0x08..+0x16 {[hex(e.r16(BINDS + PRE * 0x60 + 8 + 2 * q)) for q in range(8)]}", flush=True)
    if j == 0:
        st['ph'][name] = dict(a0=ang(s), sum=[0.0] * 3, p0=vec(s, 0x08),
                              rows=[vec(s, 0x20), vec(s, 0x30), vec(s, 0x40)])
        st['prev'] = ang(s)
    else:
        a = ang(s)
        p = st['ph'][name]
        p['sum'] = [p['sum'][q] + wrap(a[q] - st['prev'][q]) for q in range(3)]
        st['prev'] = a
        if j == PH - 1:
            d = [u - v for u, v in zip(vec(s, 0x08), p['p0'])]
            p['d'] = d
            p['dr'] = [sum(u * v for u, v in zip(d, r)) for r in p['rows']]
            p['end_roll'] = a[2]
            print(f"{name:8s} yaw {p['sum'][0]:8.2f} pitch {p['sum'][1]:8.2f} roll {p['sum'][2]:8.2f} (roll at end "
                  f"{a[2]:7.2f})  move {math.sqrt(sum(v * v for v in d)):7.2f}  right {p['dr'][0]:7.2f} "
                  f"fwd {p['dr'][1]:7.2f} up {p['dr'][2]:7.2f}", flush=True)
            if name == 'stickX': e.shot()
    e.pad(b, x, y)


e.run(script)
ph = st['ph']
print('SUMMARY mode=%s preset=%d ' % (MODE, PRE) + ' '.join(
    f"{n}:yaw={ph[n]['sum'][0]:.2f},pitch={ph[n]['sum'][1]:.2f},roll={ph[n]['sum'][2]:.2f},"
    f"right={ph[n]['dr'][0]:.2f},fwd={ph[n]['dr'][1]:.2f},up={ph[n]['dr'][2]:.2f}" for n, *_ in PHASES if 'dr' in ph[n]),
    flush=True)
check('the Stft found and all four phases measured', st.get('s') and all('dr' in ph.get(n, {}) for n, *_ in PHASES))
sys.exit(report())
