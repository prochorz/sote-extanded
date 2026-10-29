"""Cut 05 (sub-level 11) as the game plays it, read for gall_chain.c's sequence:
the scene's objects (classes Dspt, Anim, Bmap: their pools) at two moments, written back by gall_chain.c to enter the
scene's 3D shots: C05_FLY the flight's first frame (the Outrider's first place in it), C05_SPACE the first frame after
Luke's line (its second hold) is let go, C05_S2 the first frame the flight's clock reaches S2_CLK (480: scene frames
with no hold since the Outrider's node first moved, as gall_chain.c's g_c05_clk; frame 5 runs on from there). Also printed: the HUD elements that come on screen with a held line (the
button) and which table entry the scene draws when. Writes sote-patch/src/gall_c05.h.

    M64CPU=2 .venv/bin/python3 gallrun/c05_state.py <rom built with the Gall Run> <state made with it>

From the state (any level of that ROM: harness/mkstate.py) sub-level 11 is loaded by debug This Level; gall_chain.c's
Cut 05 code is kept off (g_c05_seq 0); a held line is let go by A after HOLD_A frames."""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
import m64
from m64 import Emu, BTN
from debugmenu import set_debug, set_cursor
CUT05 = 11
HOLD = 0x800DD2D0                  # s16 a held line
DRAWN = 0x80115794                 # the line drawn (at the draw)
TABLE = 0x801A1A24                 # the scene's three line pointers
OR = 0x80198D00                    # the Outrider's node (+0x38 place)
HUD_POS = 0x80111110               # s16 x, y per HUD element
RECS = (0x80112868, 0x80112898, 0x801129B8)   # class records Dspt, Anim, Bmap
HOLD_A = 150
DT = float(os.environ.get('DT', '1'))
FRAME_DT = 0x8018E998                # double: the game's frame time
import struct
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sote-patch', 'src', 'gall_c05.h')
ELF = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
e = Emu(sys.argv[1])
st = {'held': 0, 'holds': 0, 'lets': 0, 'cap': {}, 'hud': None, 'was': 0, 'clk': -1, 'last': None, 'ovf': None}
S2_CLK = int(os.environ.get('S2_CLK', 480))


def pools(e):
    out = []
    for R in RECS:
        a, n_ = e.r32(R + 0x10), e.r32(R + 8) * e.r32(R + 0xC)
        out.append((R, a, [e.r32(a + 4 * j) for j in range(n_ // 4)]))
    return out


def hud(e):                         # the HUD elements' places and the level's sprites' (header +0 x, +2 y)
    tb = e.r32(0x8013CE2C)
    sp = [e.r32(tb + 4 * i) for i in range(64)] if 0x80000000 <= tb < 0x80800000 else [0] * 64
    return [(e.r16(HUD_POS + 4 * i), e.r16(HUD_POS + 4 * i + 2)) for i in range(64)] + \
           [(e.r16(p), e.r16(p + 2)) if 0x80000000 <= p < 0x80800000 else (0, 0) for p in sp]


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(sys.argv[2])
    if n < 64: return
    k = n - 64
    e.w32(SYM['g_c05_seq'], 0)
    if k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | CUT05)
    if k < 130:
        set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0); return
    if e.r16(0x8013CE0E) != CUT05:
        print('left Cut 05 at', k, 'for', e.r16(0x8013CE0E), flush=True); finish(); return
    if DT != 1.0:                                                # (the stock scene at DT x the game's frame time)
        hi, lo = e.r32(FRAME_DT), e.r32(FRAME_DT + 4)
        d = struct.unpack('>d', struct.pack('>II', hi, lo))[0] * DT
        hi, lo = struct.unpack('>II', struct.pack('>d', d)); e.w32(FRAME_DT, hi); e.w32(FRAME_DT + 4, lo)
    hold = e.r16(HOLD)
    if hold and not st['was']:
        bm = RECS[2]; pl, n_, sz = e.r32(bm + 0x10), e.r32(bm + 8), e.r32(bm + 0xC)
        up = [e.r16(pl + i * sz + 0xA) for i in range(min(n_, 32)) if not e.r16(pl + i * sz + 8) & 0x20]
        print('HOLD rises at', k, 'bmap ids up', up, 'text x', [e.r16(HUD_POS + 4 * (5 + j)) for j in range(3)], flush=True)
    if hold and not st['was'] and 'HOLD1' not in st['cap']: st['cap']['HOLD1'] = pools(e); print('captured HOLD1 at', k, flush=True)
    if hold and not st['was']:
        st['holds'] += 1; st['hud_before'] = st['hud']; st['hud_k'] = k + 4
    if not hold and st['was']:
        st['lets'] += 1
        if st['lets'] == 2: st['cap']['SPACE'] = pools(e); print('captured SPACE at', k, flush=True)
    st['was'] = hold
    if st.get('hud_k') == k:
        now = hud(e)
        print('hold', st['holds'], 'HUD elements changed:', [(i, a, b) for i, (a, b) in enumerate(zip(st['hud_before'], now)) if a != b], flush=True)
    st['hud'] = hud(e)
    ovf = e.r32(SYM['g_ov_frames'])                              # the flight's clock, a game frame each (pt6_d3.py)
    if ovf != st['ovf']:
        st['ovf'] = ovf
        p = tuple(e.rf(OR + 0x38 + 4 * j) for j in range(3))
        if st['clk'] < 0 and st['last'] is not None and p != st['last'] and st['last'][1] != 0:
            st['clk'] = 0; print('Outrider sets off at', k, flush=True)
        st['last'] = p
        if not hold and st['clk'] >= 0: st['clk'] += 1
        if st['clk'] == S2_CLK and 'S2' not in st['cap']:
            st['cap']['S2'] = pools(e); print('captured S2 at', k, 'clock', st['clk'], 'Outrider', [round(v, 2) for v in p], flush=True)
            if 'HOLD1' in st['cap']: finish(); return
    y = e.rf(OR + 0x3C)
    if k % 30 == 29: st['y'] = y
    if 'FLY' not in st['cap'] and y < 500:
        st['cap']['FLY'] = pools(e); print('captured FLY at', k, 'Outrider y', round(y, 1), flush=True)
    if k % 30 == 0:
        d = e.r32(DRAWN); tb = [e.r32(TABLE + 4 * i) for i in range(3)]
        print(k, 'OR way a frame', round(abs(y - st.get('y', y)), 2), end=' ', flush=True)
        print(k, 'hold', hold, 'drawn entry', tb.index(d) if d in tb else hex(d), 'OR y', round(y, 1), flush=True)
    st['held'] = st['held'] + 1 if hold else 0
    e.pad(BTN['A'] if hold and st['held'] >= HOLD_A and (st['held'] - HOLD_A) % 60 < 5 else 0)


def finish():
    if 'HOLD1' in st['cap']:
        with open(OUT, 'w') as f:
            f.write('/* Made by harness/gallrun/c05_state.py: Cut 05 (sub-level 11) as the game plays it: the pools of Dspt, Anim,\n'
                    ' * Bmap at its first hold (C05_HOLD1: a line up) and at the flight\'s clock 480 (C05_S2: frame 5 runs on from there);\n * gall_chain.c writes\n'
                    ' * them back to enter those shots. */\n')
            for name in ('HOLD1', 'S2'):
                if name not in st['cap']: continue
                for i, (R, a, ws) in enumerate(st['cap'][name]):
                    f.write(f'#define C05_{name}_POOL{i} {a:#x}   /* class record {R:#x} */\n')
                    f.write(f'static const uint32_t C05_{name}_WORDS{i}[{len(ws)}] = {{\n')
                    for j in range(0, len(ws), 8): f.write('    ' + ', '.join(f'{w:#010x}' for w in ws[j:j + 8]) + ',\n')
                    f.write('};\n')
        print('wrote', OUT, flush=True)
    else:
        print('captures missing:', list(st['cap']), flush=True)
    e.stop()


e.run(script)
