"""The game's last scene (sub-level 31) from its hyperspace part: the scene's
objects (classes Dspt, Anim, Bmap: their pools) as they are as the hyperspace tunnel starts, written back by
gall_chain.c on the scene's first frame, skip its Tatooine part. Writes sote-patch/src/gall_final.h.

    M64CPU=2 .venv/bin/python3 gallrun/final_state.py <rom built with the Gall Run> <state made with it>

From the state (any level of that ROM: harness/mkstate.py) sub-level 31 is loaded by debug This Level; its held lines
are let go by A; at TUNNEL_K frames after the load the pools are read."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
import m64
from m64 import Emu, BTN
from debugmenu import set_debug, set_cursor
FINAL = 31
TUNNEL_K = 4010                     # (frames after the load: line 5 let go, its picture all but faded; 3945: seen fading 1 s, 4030: the scene restarted at Tatooine; probes 2026-10-19)
HOLD_A = 50                         # a held line let go after this many frames
RECS = (0x80112868, 0x80112898, 0x801129B8)   # class records Dspt, Anim, Bmap
OR_NODE = 0x80199AC0                # the Outrider's node in the tunnel: its mesh (part boxes: its size)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sote-patch', 'src', 'gall_final.h')
e = Emu(sys.argv[1])
st = {'held': 0}


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(sys.argv[2])
    if n < 64: return
    k = n - 64
    if k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | FINAL)
    if k < 130:
        set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0); return
    hold = e.r16(0x800DD2D0)
    st['held'] = st['held'] + 1 if hold else 0
    e.pad(BTN['A'] if hold and st['held'] >= HOLD_A and st['held'] % 60 < HOLD_A % 60 + 5 else 0)
    if k == TUNNEL_K:
        assert e.r16(0x8013CE0E) == FINAL
        blocks = []
        for R in RECS:
            a, n_ = e.r32(R + 0x10), e.r32(R + 8) * e.r32(R + 0xC)
            blocks.append((R, a, [e.r32(a + 4 * i) for i in range(n_ // 4)]))
        m = e.r32(e.r32(OR_NODE + 0x10))
        parts = [e.r32(e.r32(m + 0x10) + 4 * i) for i in range(e.r32(m + 0xC))]
        ys = [e.rf(p + 4 * j) for p in parts for j in (1, 4)]
        print('outrider mesh', hex(m), len(parts), 'parts, y', min(ys), max(ys), flush=True)
        with open(OUT, 'w') as f:
            f.write('/* Made by harness/gallrun/final_state.py: sub-level 31 (the last scene) at its hyperspace tunnel:\n'
                    ' * the pools of Dspt, Anim, Bmap (gall_chain.c writes them back on the scene\'s first frame). */\n')
            f.write(f'#define FINAL_OR_LEN {max(ys) - min(ys):.2f}f   /* the Outrider\'s length in the scene\'s mesh units */\n')
            for i, (R, a, ws) in enumerate(blocks):
                f.write(f'#define FINAL_POOL{i} {a:#x}   /* class record {R:#x} */\n')
                f.write(f'static const uint32_t FINAL_WORDS{i}[{len(ws)}] = {{\n')
                for j in range(0, len(ws), 8): f.write('    ' + ', '.join(f'{w:#010x}' for w in ws[j:j + 8]) + ',\n')
                f.write('};\n')
        print('wrote', OUT, [len(b[2]) for b in blocks], flush=True)
        e.stop()


e.run(script)
