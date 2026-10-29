"""Disassemble game code by RAM address.

    python3 disasm.py <addr hex> [length hex] [--ram dump.bin]

Code source, in order:
  * --ram: an RDRAM dump made with Emu.dump() (little-endian words; includes level overlays
    and any patch hooks that were applied);
  * 0x80000400-0x80001EC0: the uncompressed boot segment straight from the ROM;
  * everything else: local/work/main.bin, the main executable's code part loaded at 0x80001EC0 (up to
    0x800D06E8; its data part is read from a RAM dump). Made by make_main.py (tools/setup.sh).
"""
import os, struct, sys
import capstone
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
ROM = os.environ.get('SOTE_ROM', paths.ROM)
MAIN_VRAM = 0x80001EC0


def mem(addr, n, ram=None):
    if ram is not None:
        o = addr & 0x7FFFFF
        words = struct.unpack_from('<%dI' % (n // 4), ram, o)
        return struct.pack('>%dI' % len(words), *words)
    if 0x80000400 <= addr < MAIN_VRAM:
        o = addr - 0x80000400 + 0x1000
        return open(ROM, 'rb').read()[o:o + n]
    main = open(os.path.join(paths.WORK, 'main.bin'), 'rb').read()
    return main[addr - MAIN_VRAM:addr - MAIN_VRAM + n]


def main():
    args = sys.argv[1:]
    ram = None
    if '--ram' in args:
        i = args.index('--ram'); ram = open(args[i + 1], 'rb').read(); del args[i:i + 2]
    a = int(args[0], 16)
    n = int(args[1], 16) if len(args) > 1 else 0x100
    code = mem(a, n & ~3, ram)
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 + capstone.CS_MODE_BIG_ENDIAN)
    for i in range(0, len(code), 4):
        w = code[i:i + 4]
        ins = list(md.disasm(w, a + i))
        print(f"{a + i:08X}: {w.hex()}  " + (f"{ins[0].mnemonic} {ins[0].op_str}" if ins else ".word"))


if __name__ == '__main__':
    main()
