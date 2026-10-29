#!/usr/bin/env python3
"""Build the controls patch for Star Wars: Shadows of the Empire (USA Rev 2).

Outputs (in local/build/sote-patch/, or --out):
  sote-patch.z64  patched ROM
  sote-patch.bps  BPS patch against the original ROM
"""
import argparse, hashlib, os, struct, subprocess, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
# local/ (git-ignored, env SOTE_LOCAL moves it, as harness/paths.py): the game's assets made from your own ROM, builds
LOCAL = Path(os.environ.get('SOTE_LOCAL') or HERE.parent / 'local').resolve()
GAME = LOCAL / 'game'
LLVM = Path('/opt/homebrew/opt/llvm/bin')
LLD = Path('/opt/homebrew/opt/lld/bin/ld.lld')
EXPECTED_SHA256 = 'e7085e013123537f34e0edec8801318016da4dbac424172d6dc5f3b67d98642c'

PAYLOAD_VRAM = 0x807C0000
PAYLOAD_ROM = 0xC00000           # appended right after the 12 MB retail image
PAYLOAD_SPACE = 0x10000          # fixed DMA size: the first 1 MB (and the header CRC) never change;
                                 # the ROM's last 8 bytes are the MD5 nonce (see --md5-prefix)
FALCON_ASSET = GAME / 'falcon.bin'   # made by harness/falcon_asset.py (feature falcon)
FALCON_VRAM = 0x80500000         # where _start copies it; the pointers inside are set for this
CHEATS_VRAM = 0x80540000         # cheats.c's code and data (link.ld .cheats), out of the payload: after the Falcon model
CHEATS_ROM = PAYLOAD_ROM + PAYLOAD_SPACE   # a fixed slot, there in every build (zeros --without cheats), so the ROM
CHEATS_SPACE = 0x8000            # layout is known before compiling; _start DMAs all of it
FALCON_ROM = CHEATS_ROM + CHEATS_SPACE
GALL_ASSET = GAME / 'gall_run.bin'   # made by harness/gallrun/gall_asset.py (feature gallrun)
GALL_VRAM = 0x80628000           # canyon/landscape meshes + route (pointers inside are set for this); clear of
                                 # the two 0xFFFFFFFF words every level keeps at 0x80600000 (purpose unknown)
GALL_LEVEL = GAME / 'gall_level.bin'   # the base level's unpacked sub-level blob (harness/level_blob.py <rom> 6):
                                 # loaded uncompressed in its place while the mission runs (gallrun.c level_table())
GALL_CODE = 0x80600040           # the Gall Run's code (link.ld .gall), before the image: one DMA loads both (past
                                 # the two words at 0x80600000: ~160 KB; 32 KB at 0x80608000 ran out, 2026-10-13,
                                 # 64 KB at 0x80610000 2026-10-16, 96 KB at 0x80618000 2026-10-20)
PAYLOAD_RAM_END = 0x807E0000      # payload + its .bss (NOLOAD, zeroed by _start) stay below this
BOOT_STUB_ROM = 0x1014           # 15 free words (nops) at RAM 0x80000414
BOOT_STUB_VRAM = 0x80000414
BOOT_CALL_ROM = 0x1F14           # RAM 0x80001314: jal 0x80017B60 (game main)
BOOT_CALL_ORIG = 0x0C005ED8
CIC6102_SEED = 0xF8CA4DDC

CFLAGS = ['--target=mips-elf', '-mabi=32', '-mfp32', '-mhard-float',
          '-mno-odd-spreg', '-mno-abicalls', '-fno-pic', '-G0', '-O2', '-ffreestanding', '-fno-builtin',
          '-nostdlib', '-fno-stack-protector', '-Wall', '-Werror']


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def jal(addr):
    return 0x0C000000 | ((addr >> 2) & 0x03FFFFFF)


# Always built: the on-foot controller hooks, lock-on with its overlay.
SOURCES = ['src/hooks.S', 'src/core.c', 'src/lock.c']
# Optional features: name -> sources. Each also gets -DFEATURE_<NAME>=0/1 everywhere, so
# its hooks (hooks.S) and its calls from the core (stubs in common.h) go away with it.
FEATURES = {
    'hang': ['src/hang.c'],      # ledge hang (docs/ledge-falls.md)
    'train': ['src/train.c'],    # the train level: HumT controls, drones, car alignment
    'cheats': ['src/cheats.c'],  # the game's debug list as a pause-menu entry
    'falcon': ['src/falcon.c'],  # the Gall Run's ship: Millennium Falcon model swap, local/game/falcon.bin
    'gallrun': ['src/gallrun.c', 'src/gall_scene.c', 'src/gall_fly.c', 'src/gall_story.c',   # Gall Run bonus mission in the base level
                'src/gall_space.c', 'src/gall_native.c', 'src/gall_gun.c',
                'src/gall_ties.c', 'src/gall_cam.c', 'src/gall_chain.c'],   # Field (needs falcon), local/game/gall_run.bin
}
# Built for size (PAYLOAD_SPACE is 64 KB; cheats.c is small, it no longer has to fit the payload): source -> flag.
# The rest is -O2. Not core.c: -Oz there
# (-1.9 KB, math out of line) slowed the per-frame code enough to change the game's frame time,
# and with it ledge catches (t_hang_spots 67/68 vs 69/69).
SIZE_OPT = {'src/cheats.c': '-Oz', 'src/hang.c': '-Os', **{src: '-Oz' for src in FEATURES['gallrun']}}


def build_payload(out, without=(), falcon_len=0, gall_rom=0, gall_len=0, level_rom=0, level_len=0):
    objs = []
    defs = [f'-DFEATURE_{f.upper()}={0 if f in without else 1}' for f in FEATURES]
    defs += [f'-DCHEATS_RAM={CHEATS_VRAM:#x}', f'-DCHEATS_ROM={CHEATS_ROM:#x}', f'-DCHEATS_LEN={CHEATS_SPACE:#x}']
    defs += [f'-DFALCON_RAM={FALCON_VRAM:#x}', f'-DFALCON_ROM={FALCON_ROM:#x}', f'-DFALCON_LEN={falcon_len:#x}',
             f'-DGALL_RAM={GALL_VRAM:#x}', f'-DGALL_LOAD={GALL_CODE:#x}', f'-DGALL_ROM={gall_rom:#x}',
             f'-DGALL_LEN={gall_len:#x}', f'-DGALL_LEVEL_ROM={level_rom:#x}', f'-DGALL_LEVEL_LEN={level_len:#x}']
    defs += os.environ.get('SOTE_DEFS', '').split()     # research builds, e.g. SOTE_DEFS=-DGALL_TRACE_PROBE
    srcs = SOURCES + [s for f, files in FEATURES.items() if f not in without for s in files]
    for src in srcs:
        obj = out / (Path(src).stem + '.o')
        # clang's o32 mips3 C backend crashes; C is built as mips2 (same FPU ops),
        # the assembly as mips3 for the cache instructions.
        isa = '-march=mips3' if src.endswith('.S') else '-march=mips2'
        opt = [SIZE_OPT[src]] if src in SIZE_OPT else []
        run([LLVM / 'clang', *CFLAGS, *opt, *defs, isa, '-c', HERE / src, '-o', obj])
        objs.append(obj)
    elf = out / 'payload.elf'
    run([LLD, '-T', HERE / 'link.ld', '-o', elf, *objs])
    binf, code, cheats = out / 'payload.bin', out / 'gallcode.bin', out / 'cheatscode.bin'
    for f in (code, cheats): f.unlink(missing_ok=True)
    run([LLVM / 'llvm-objcopy', '-O', 'binary', '-R', '.gall', '-R', '.cheats', elf, binf])
    run([LLVM / 'llvm-objcopy', '-O', 'binary', '-j', '.gall', elf, code])
    run([LLVM / 'llvm-objcopy', '-O', 'binary', '-j', '.cheats', elf, cheats])
    syms = subprocess.run([str(LLVM / 'llvm-nm'), str(elf)], capture_output=True, text=True, check=True).stdout
    return (binf.read_bytes(), code.read_bytes() if code.exists() else b'',
            cheats.read_bytes() if cheats.exists() else b'', syms)


def boot_stub(length):
    """Copy the payload from ROM into RDRAM with a PI DMA, then jump to it."""
    assert 0 < length <= 0x10000
    phys = PAYLOAD_VRAM & 0x1FFFFFFF
    cart = 0x10000000 + PAYLOAD_ROM
    words = [
        0x3C08A460,                          # lui   t0, 0xA460        (PI regs)
        0x3C090000 | (phys >> 16),           # lui   t1, phys_hi
        0xAD090000,                          # sw    t1, 0(t0)         PI_DRAM_ADDR
        0x3C090000 | (cart >> 16),           # lui   t1, cart_hi
        0xAD090004,                          # sw    t1, 4(t0)         PI_CART_ADDR
        0x34090000 | (length - 1),           # ori   t1, zero, len-1
        0xAD09000C,                          # sw    t1, 0xC(t0)       PI_WR_LEN (cart -> RAM)
        0x8D0A0010,                          # lw    t2, 0x10(t0)      PI_STATUS
        0x314A0003,                          # andi  t2, t2, 3         DMA/IO busy
        0x1540FFFD,                          # bnez  t2, -3
        0x00000000,                          # nop
        0x3C0B0000 | (PAYLOAD_VRAM >> 16),   # lui   t3, payload_hi
        0x01600008,                          # jr    t3
        0x00000000,                          # nop
    ]
    assert phys & 0xFFFF == 0 and cart & 0xFFFF == 0 and PAYLOAD_VRAM & 0xFFFF == 0
    return b''.join(struct.pack('>I', w) for w in words)


def n64_crc(rom, seed=CIC6102_SEED):
    m = 0xFFFFFFFF
    t1 = t2 = t3 = t4 = t5 = t6 = seed
    for i in range(0x1000, 0x101000, 4):
        d = struct.unpack_from('>I', rom, i)[0]
        if (t6 + d) & m < t6:
            t4 = (t4 + 1) & m
        t6 = (t6 + d) & m
        t3 ^= d
        r = ((d << (d & 0x1F)) | (d >> (32 - (d & 0x1F)))) & m if d & 0x1F else d
        t5 = (t5 + r) & m
        t2 = t2 ^ r if t2 > d else t2 ^ t6 ^ d
        t1 = (t1 + (t5 ^ d)) & m
    return t6 ^ t4 ^ t3, t5 ^ t2 ^ t1


def bps(source, target):
    """Minimal BPS encoder: SourceRead for unchanged runs, TargetRead otherwise."""
    def num(v):
        out = bytearray()
        while True:
            x = v & 0x7F
            v >>= 7
            if v == 0:
                out.append(0x80 | x)
                return bytes(out)
            out.append(x)
            v -= 1
    out = bytearray(b'BPS1') + num(len(source)) + num(len(target)) + num(0)
    i, n = 0, len(target)
    while i < n:
        same = i < len(source) and source[i] == target[i]
        j = i
        while j < n and (j < len(source) and source[j] == target[j]) == same:
            j += 1
        out += num(((j - i - 1) << 2) | (0 if same else 1))
        if not same:
            out += target[i:j]
        i = j
    out += struct.pack('<I', zlib.crc32(source)) + struct.pack('<I', zlib.crc32(target))
    out += struct.pack('<I', zlib.crc32(out))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom', type=Path)
    ap.add_argument('-o', '--out', type=Path, default=LOCAL / 'build' / 'sote-patch')
    ap.add_argument('--md5-prefix', metavar='HEX8',
                    help='brute-force the nonce so the ROM MD5 starts with these 8 hex digits '
                         '(keeps the .eep save name; ~1-3 min)')
    ap.add_argument('--without', action='append', default=[], choices=sorted(FEATURES),
                    help='leave an optional feature out (repeatable)')
    args = ap.parse_args()
    if 'gallrun' in args.without: args.without.append('falcon')   # the Falcon is the Gall Run's ship
    args.out.mkdir(parents=True, exist_ok=True)

    src = args.rom.read_bytes()
    if hashlib.sha256(src).hexdigest() != EXPECTED_SHA256:
        raise SystemExit('ROM must be Star Wars - Shadows of the Empire (USA) (Rev 2), big-endian .z64')
    if n64_crc(src) != struct.unpack_from('>II', src, 0x10):
        raise SystemExit('CRC self-check failed (unexpected CIC)')

    falcon = b''
    if 'falcon' not in args.without:
        if not FALCON_ASSET.exists():
            raise SystemExit(f'{FALCON_ASSET} missing: run harness/falcon_asset.py <rom>')
        falcon = FALCON_ASSET.read_bytes()
        falcon += bytes(-len(falcon) % 16)
        assert falcon[:4] == b'FALC' and FALCON_VRAM + len(falcon) <= CHEATS_VRAM
    gall = b''
    if 'gallrun' not in args.without:
        if 'falcon' in args.without:
            raise SystemExit('gallrun needs falcon (build --without gallrun too)')
        if not GALL_ASSET.exists():
            raise SystemExit(f'{GALL_ASSET} missing: run harness/gallrun/gall_asset.py <rom> '
                             '(or build --without gallrun)')
        gall = GALL_ASSET.read_bytes()
        gall += bytes(-len(gall) % 16)
        assert gall[:4] == b'GALL' and GALL_VRAM >= 0x80600008 and GALL_VRAM + len(gall) <= PAYLOAD_VRAM
    gall_rom = FALCON_ROM + len(falcon) if gall else 0   # ROM: the Gall Run's code, padded to GALL_VRAM, the image
    if gall and len(gall) > 100 and struct.unpack_from('>I', gall, 96)[0]:   # a word of the image that holds an
        gall = bytearray(gall); at = struct.unpack_from('>I', gall, 96)[0]   # offset in it: made its ROM address
        struct.pack_into('>I', gall, at, struct.unpack_from('>I', gall, at)[0] + gall_rom + GALL_VRAM - GALL_CODE)
        gall = bytes(gall)                                                    # (Chewie's sample)
    level = b''
    if gall:
        if not GALL_LEVEL.exists():
            raise SystemExit(f'{GALL_LEVEL} missing: run harness/level_blob.py <rom> 6 {GALL_LEVEL}')
        level = GALL_LEVEL.read_bytes()
        assert level[:8] == b'LStb\x80\x19\x69\x50' and struct.unpack_from('>I', level, 8)[0] == 0x80196950 + len(level)
        level += bytes(-len(level) % 16)
    level_rom = gall_rom + GALL_VRAM - GALL_CODE + len(gall) if gall else 0
    payload, code, cheats, syms = build_payload(args.out, args.without, len(falcon), gall_rom,
                                        GALL_VRAM - GALL_CODE + len(gall) if gall else 0,
                                        level_rom, len(level))
    if gall:
        assert len(code) <= GALL_VRAM - GALL_CODE, f'Gall Run code is {len(code)} bytes, past {GALL_VRAM:#x}'
        gall = code + bytes(GALL_VRAM - GALL_CODE - len(code)) + gall
    rom = bytearray(src)
    assert rom[BOOT_STUB_ROM:BOOT_STUB_ROM + 56] == bytes(56), 'boot stub area is not free'
    assert struct.unpack_from('>I', rom, BOOT_CALL_ROM)[0] == BOOT_CALL_ORIG
    assert len(payload) <= PAYLOAD_SPACE - 8, 'payload outgrew PAYLOAD_SPACE'
    bss_end = int(next(l.split()[0] for l in syms.splitlines() if l.endswith(' _bss_end')), 16)
    assert bss_end <= PAYLOAD_RAM_END, f'.bss ends at {bss_end:#x}, past {PAYLOAD_RAM_END:#x}'
    rom[BOOT_STUB_ROM:BOOT_STUB_ROM + 56] = boot_stub(PAYLOAD_SPACE)
    struct.pack_into('>I', rom, BOOT_CALL_ROM, jal(BOOT_STUB_VRAM))
    rom += payload + bytes(PAYLOAD_SPACE - len(payload))
    # the cheats slot; when nothing follows it, its last 8 bytes are the ROM's MD5 nonce
    assert len(cheats) <= CHEATS_SPACE - (0 if falcon else 8), f'.cheats is {len(cheats)} bytes, past CHEATS_SPACE'
    assert len(rom) == CHEATS_ROM
    rom += cheats + bytes(CHEATS_SPACE - len(cheats))
    if falcon:
        rom += falcon + gall
        assert not level or len(rom) == level_rom
        rom += level
        rom += bytes(8 + (-(len(rom) + 8) % 64))   # nonce (last 8 bytes), length a multiple of 64
    struct.pack_into('>II', rom, 0x10, *n64_crc(rom))

    out_rom = args.out / 'sote-patch.z64'
    out_rom.write_bytes(rom)
    if args.md5_prefix:
        # Emulators on mupen64plus name the EEPROM save "<name>-<first 8 hex of MD5>.eep";
        # pinning those digits keeps the player's save across patch updates.
        tool = args.out / 'md5prefix'
        run([LLVM / 'clang', '-O3', HERE / 'tools' / 'md5prefix.c', '-o', tool])
        run([tool, out_rom, args.md5_prefix])
        rom = bytearray(out_rom.read_bytes())
    (args.out / 'sote-patch.bps').write_bytes(bps(src, bytes(rom)))
    print('features:', ', '.join(f for f in FEATURES if f not in args.without) or 'none')
    print(f'payload {len(payload)} bytes at {PAYLOAD_VRAM:#x}; cheats {len(cheats)} bytes at ROM {CHEATS_ROM:#x} '
          f'-> {CHEATS_VRAM:#x} (slot {CHEATS_SPACE:#x})')
    if falcon:
        print(f'falcon model {len(falcon)} bytes at ROM {FALCON_ROM:#x} -> {FALCON_VRAM:#x}')
    if gall:
        print(f'gall run: code {len(code)} bytes at {GALL_CODE:#x}, with the image {len(gall)} bytes at ROM {gall_rom:#x}, '
              f'level blob {len(level)} bytes at ROM {level_rom:#x}')
    for line in syms.splitlines():
        if ' T ' in line or ' t ' in line:
            print('  ', line)
    print('md5', hashlib.md5(rom).hexdigest())
    print('wrote', args.out / 'sote-patch.z64', 'and', args.out / 'sote-patch.bps')


if __name__ == '__main__':
    main()
