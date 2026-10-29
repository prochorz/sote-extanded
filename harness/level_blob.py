"""A sub-level's unpacked blob (docs/reverse-engineering.md, "Sub-level data"), as the game unpacks it.

    M64CPU=0 .venv/bin/python3 level_blob.py <rom> <id> <out.bin>

From states/src_model.st the sub-level is loaded with debug This Level; a RAM patch on the epilogue of
0x80019234 (right after the unpacker 0x80019B14 returns, before the level's code runs) jumps to a
stub at 0x80600000 that copies the blob from 0x80196950 to 0x80400000 and sets a mark. The blob
can go back into a ROM uncompressed: its table entry's flag byte 0 and length = its size.
"""
import os, sys, ctypes as C, struct
import paths
import m64
from m64 import Emu, BTN, HERE
from debugmenu import set_debug, set_cursor
ROM, ID, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
rom = open(ROM, 'rb').read()
P = lambda a: a - 0x80000400 + 0x1000
blob = struct.unpack_from('>I', rom, P(0x80001370 + 4 * ID))[0]
flag = struct.unpack_from('>I', rom, P(0x800013F0 + 4 * ID))[0]
SIZE = struct.unpack_from('>I', rom, blob)[0] if flag >> 24 else flag & 0xFFFFFF
STUB, DST, MARK = 0x80600000, 0x80400000, 0x80600100
J = lambda t: 0x08000000 | ((t >> 2) & 0x03FFFFFF)
code = [0x3C088019, 0x35086950,                          # t0 = 0x80196950
        0x3C098040,                                      # t1 = 0x80400000
        0x3C0A0000 | (SIZE >> 16), 0x354A0000 | (SIZE & 0xFFFF),   # t2 = size
        0x8D0B0000, 0xAD2B0000, 0x25080004, 0x25290004, 0x254AFFFC, 0x1D40FFFA, 0x00000000,  # copy loop
        0x3C088060, 0x240B0001, 0xAD0B0100,              # *MARK = 1
        0x8FBFFFFC, 0x03E00008, 0x00000000]             # lw ra,-4(sp) (sp already +0x20); jr ra
e = Emu(ROM)
st = {'k': None}
def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'src_model.st'))
    if n == 62:
        for i, w in enumerate(code): e.w32(STUB + 4 * i, w)
        e.w32(MARK, 0)
        assert e.r32(0x80019284) == 0x8FBF001C and e.r32(0x80019288) == 0x27BD0020, hex(e.r32(0x80019284))
        e.w32(0x80019284, J(STUB))
    if n < 64: return
    k = n - 64
    if k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | ID)
    if k < 130:
        set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 5 else 0)
    if e.r32(MARK) and st['k'] is None:
        st['k'] = k
        raw = C.string_at(e.rdram() + (DST & 0x7FFFFF), (SIZE + 3) & ~3)
        open(OUT, 'wb').write(b''.join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4))[:SIZE])
        print('DUMPED', hex(SIZE), 'frame', k, 'level', e.r16(0x8013CE0E), flush=True)
    if (st['k'] is not None and k > st['k'] + 200) or k > 700:
        e.shot(); print('end level', e.r16(0x8013CE0E), flush=True); e.stop()
e.run(script)
