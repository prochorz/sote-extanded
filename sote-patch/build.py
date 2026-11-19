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
GUARD_ASSET = GAME / 'guard.bin'     # made by harness/guard_asset.py (feature guard): the guard's meshes on Dash's bones
GUARD_VRAM = 0x80548000          # right after the cheats code's slot; the pointers inside are set for this
GUARD_END = 0x80580000           # the Guri image starts here (guard.bin is ~41 KB)
GURI_ASSET = GAME / 'guri.bin'       # made by harness/guri/guri_asset.py (feature guri): Guri's meshes on a guard's bones
GURI_VRAM = 0x80580000           # after the guard's slot; the pointers inside are set for this
GURI_END = 0x80600000            # the Gall Run's code starts here
MELEE_ASSET = GAME / 'melee.bin'     # made by harness/pose/melee.py (feature melee): the combo's blocks and tables
MELEE_VRAM = 0x805A0000          # past the Guri image; the track pointers inside are set for this
MELEE_END = 0x805B0000           # melee.c's own RAM (block instances, descriptors) starts here
MELEE_RAM_END = 0x805C0000       # melee.c's own RAM ends here (DESC_RAM 0x805BF000 + 4 KB)
SABER_VRAM = 0x805C0000          # saber.c's code and data (link.ld .saber), out of the payload: after melee.c's RAM
SABER_SPACE = 0x8000             # a fixed ROM slot, the ROM's last blob (after the saber's sounds); _start DMAs all of it
SABER_END = 0x80600000           # its .bss (link.ld .saber_bss) follows the slot and stays below the Gall Run's code
SABER_SND = GAME / 'saber_snd.bin'   # the saber's sounds (harness/saber/saber_snd.py, feature saber): the ROM's last blob
DUEL_LEVEL = GAME / 'duel_level.bin'   # sub-level 27's unpacked blob, its arena's flat floor kept (harness/duel/arena_blob.py,
                                 # feature duel): level 33's entry, uncompressed (flag 0, its length), the ROM's last blob
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
    'guard': ['src/guard.c'],    # Cheats' Look row: the player drawn as the red palace guard, local/game/guard.bin
    'guri': ['src/guri.c'],      # a palace guard drawn as Guri (g_guri_trop), local/game/guri.bin
    'melee': ['src/melee.c'],    # Guri's hand-to-hand combo on the player (the duel's), local/game/melee.bin
    'falcon': ['src/falcon.c'],  # the Gall Run's ship: Millennium Falcon model swap, local/game/falcon.bin (in .gall)
    'gallrun': ['src/gallrun.c', 'src/gall_scene.c', 'src/gall_fly.c', 'src/gall_story.c',   # Gall Run bonus mission in the base level
                'src/gall_space.c', 'src/gall_native.c', 'src/gall_gun.c',
                'src/gall_ties.c', 'src/gall_cam.c', 'src/gall_chain.c'],   # Field (needs falcon), local/game/gall_run.bin
    'duel': ['src/duel.c'],      # Go to level 33: Luke against Guri in the palace's rooftop arena (in the Gall code, needs
                                 # gallrun and guri)
    'saber': ['src/saber.c'],    # Luke's lightsaber (the Look on Luke: needs guard), in .saber; local/game/saber_snd.bin
}
# Built for size (PAYLOAD_SPACE is 64 KB; cheats.c is small, it no longer has to fit the payload): source -> flag.
# saber.c (in .saber now) keeps -Os and its minsize functions: that object code is the one whose frame cost was measured.
# The rest is -O2. Not core.c: -Oz there
# (-1.9 KB, math out of line) slowed the per-frame code enough to change the game's frame time,
# and with it ledge catches (t_hang_spots 67/68 vs 69/69).
SIZE_OPT = {'src/cheats.c': '-Oz', 'src/saber.c': '-Os', 'src/guard.c': '-Oz', 'src/guri.c': '-Oz', 'src/melee.c': '-Oz', 'src/hang.c': '-Os',
            'src/duel.c': '-Oz', **{src: '-Oz' for src in FEATURES['gallrun']}}


def build_payload(out, without=(), falcon_len=0, gall_rom=0, gall_len=0, level_rom=0, level_len=0,
                  guard_rom=0, guard_len=0, guri_rom=0, guri_len=0, melee_rom=0, melee_len=0, duel_rom=0, duel_len=0,
                  snd_rom=0, snd_tab=(), snd_pitch=(), saber_rom=0):
    objs = []
    defs = [f'-DFEATURE_{f.upper()}={0 if f in without else 1}' for f in FEATURES]
    defs += [f'-DCHEATS_RAM={CHEATS_VRAM:#x}', f'-DCHEATS_ROM={CHEATS_ROM:#x}', f'-DCHEATS_LEN={CHEATS_SPACE:#x}']
    defs += [f'-DSABER_RAM={SABER_VRAM:#x}', f'-DSABER_ROM={saber_rom:#x}', f'-DSABER_LEN={SABER_SPACE:#x}']
    defs += [f'-DFALCON_RAM={FALCON_VRAM:#x}', f'-DFALCON_ROM={FALCON_ROM:#x}', f'-DFALCON_LEN={falcon_len:#x}',
             f'-DGALL_RAM={GALL_VRAM:#x}', f'-DGALL_LOAD={GALL_CODE:#x}', f'-DGALL_ROM={gall_rom:#x}',
             f'-DGALL_LEN={gall_len:#x}', f'-DGALL_LEVEL_ROM={level_rom:#x}', f'-DGALL_LEVEL_LEN={level_len:#x}']
    defs += [f'-DGUARD_RAM={GUARD_VRAM:#x}', f'-DGUARD_ROM={guard_rom:#x}', f'-DGUARD_LEN={guard_len:#x}']
    defs += [f'-DGURI_RAM={GURI_VRAM:#x}', f'-DGURI_ROM={guri_rom:#x}', f'-DGURI_LEN={guri_len:#x}']
    defs += [f'-DMELEE_RAM={MELEE_VRAM:#x}', f'-DMELEE_ROM={melee_rom:#x}', f'-DMELEE_LEN={melee_len:#x}']
    defs += [f'-DDUEL_LEVEL_ROM={duel_rom:#x}', f'-DDUEL_LEVEL_LEN={duel_len:#x}']
    if snd_rom:                    # the saber's sounds: the blob's ROM offset, (offset, bytes) and pitch per sound
        defs += [f'-DSABER_SND_ROM={snd_rom:#x}', '-DSABER_SND_TAB=' + ','.join(f'{x:#x}' for x in snd_tab),
                 '-DSABER_SND_PITCH=' + ','.join(f'{x:#x}' for x in snd_pitch)]
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
    saber = out / 'sabercode.bin'
    for f in (code, cheats, saber): f.unlink(missing_ok=True)
    run([LLVM / 'llvm-objcopy', '-O', 'binary', '-R', '.gall', '-R', '.cheats', '-R', '.saber', '-R', '.saber_bss',
         elf, binf])
    run([LLVM / 'llvm-objcopy', '-O', 'binary', '-j', '.gall', elf, code])
    run([LLVM / 'llvm-objcopy', '-O', 'binary', '-j', '.cheats', elf, cheats])
    run([LLVM / 'llvm-objcopy', '-O', 'binary', '-j', '.saber', elf, saber])
    syms = subprocess.run([str(LLVM / 'llvm-nm'), str(elf)], capture_output=True, text=True, check=True).stdout
    return (binf.read_bytes(), code.read_bytes() if code.exists() else b'',
            cheats.read_bytes() if cheats.exists() else b'', saber.read_bytes() if saber.exists() else b'', syms)


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
    args.without.append('guri')   # this tree has no Guri, combo or duel sources: always without them (and so melee, duel)
    if 'gallrun' in args.without: args.without.append('falcon')   # the Falcon is the Gall Run's ship
    if 'cheats' in args.without: args.without += ['guard', 'guri']   # the Look is a Cheats row; guri_frame runs
                                                                     # from cheats_frame
    if 'guri' in args.without: args.without.append('melee')    # the combo is Guri's (her look, g_guri_trop)
    if 'gallrun' in args.without or 'guri' in args.without: args.without.append('duel')   # in the Gall code; Guri's
    if 'guard' in args.without or 'hang' in args.without: args.without.append('saber')   # the saber is the Look on
                                                     # Luke's; its swings use hang.c's block copy and set_anim hook
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
    guard = b''
    if 'guard' not in args.without:
        if not GUARD_ASSET.exists():
            raise SystemExit(f'{GUARD_ASSET} missing: run harness/guard_asset.py <rom> (or build --without guard)')
        guard = GUARD_ASSET.read_bytes()
        guard += bytes(-len(guard) % 16)
        assert guard[:4] == b'GARD' and GUARD_VRAM + len(guard) <= GUARD_END
    # ROM: the guard image after the last blob before it (the level blob, the Falcon, or the cheats slot)
    guard_rom = (CHEATS_ROM + CHEATS_SPACE + len(falcon) + (GALL_VRAM - GALL_CODE + len(gall) if gall else 0)
                 + len(level)) if guard else 0
    guri = b''
    if 'guri' not in args.without:
        if not GURI_ASSET.exists():
            raise SystemExit(f'{GURI_ASSET} missing: run harness/guri/guri_asset.py <rom> (or build --without guri)')
        guri = GURI_ASSET.read_bytes()
        guri += bytes(-len(guri) % 16)
        assert guri[:4] == b'GURI' and GURI_VRAM + len(guri) <= GURI_END
    # ROM: the Guri image last, right after the guard image (or what came before it)
    guri_rom = ((guard_rom + len(guard)) if guard else (CHEATS_ROM + CHEATS_SPACE + len(falcon)
                + (GALL_VRAM - GALL_CODE + len(gall) if gall else 0) + len(level))) if guri else 0
    melee = b''
    if 'melee' not in args.without:
        if not MELEE_ASSET.exists():
            raise SystemExit(f'{MELEE_ASSET} missing: run harness/pose/melee.py (needs palace.bin: '
                             'harness/pose/melee_view.py --dump; or build --without melee)')
        melee = MELEE_ASSET.read_bytes()
        melee += bytes(-len(melee) % 16)
        assert melee[:4] == b'MELE' and MELEE_VRAM + len(melee) <= MELEE_END
    # ROM: the combo's image last, right after the Guri image (melee needs guri)
    melee_rom = guri_rom + len(guri) if melee else 0
    duel = b''
    if 'duel' not in args.without:
        if not DUEL_LEVEL.exists():
            raise SystemExit(f'{DUEL_LEVEL} missing: run harness/level_blob.py <rom> 27 local/game/duel27_stock.bin, '
                             'then harness/duel/arena_blob.py (or build --without duel)')
        duel = DUEL_LEVEL.read_bytes()
        assert duel[:8] == b'LStb\x80\x19\x69\x50' and struct.unpack_from('>I', duel, 8)[0] == 0x80196950 + len(duel)
        assert len(duel) < 1 << 24                 # the table's length field
        duel_len = len(duel)
        duel += bytes(-len(duel) % 16)
    # ROM: the duel's level last, after the combo's image (or the Guri image)
    duel_rom = ((melee_rom + len(melee)) if melee else (guri_rom + len(guri))) if duel else 0
    snd, snd_tab, snd_pitch = b'', (), ()
    if 'saber' not in args.without and SABER_SND.exists():   # absent (no sound files: harness/saber/saber_snd.py): silent
        snd = SABER_SND.read_bytes()
        assert snd[:4] == b'SSN2', f'{SABER_SND} is an older format: remake it with harness/saber/saber_snd.py'
        ent = struct.unpack_from(f'>{3 * struct.unpack_from(">I", snd, 4)[0]}I', snd, 8)   # (offset, bytes, rate)
        snd_tab = tuple(x for i in range(0, len(ent), 3) for x in ent[i:i + 2])
        # each sound's pitch: its rate against the synth's 44100 Hz, as float bits (0.5 for 22050 Hz)
        snd_pitch = tuple(struct.unpack('>I', struct.pack('>f', r / 44100))[0] for r in ent[2::3])
        snd += bytes(-len(snd) % 16)
    # ROM: the saber's sounds last, after whatever blob ends the ROM
    tail = max([CHEATS_ROM + CHEATS_SPACE, FALCON_ROM + len(falcon) + (GALL_VRAM - GALL_CODE + len(gall) if gall else 0)
                + len(level)] + [r + len(b) for r, b in ((guard_rom, guard), (guri_rom, guri), (melee_rom, melee),
                                                        (duel_rom, duel)) if b])
    snd_rom = tail if snd else 0
    # ROM: the saber's code slot last, after its sounds (or whatever blob ends the ROM)
    saber_rom = tail + len(snd) if 'saber' not in args.without else 0
    payload, code, cheats, sabercode, syms = build_payload(args.out, args.without, len(falcon), gall_rom,
                                        GALL_VRAM - GALL_CODE + len(gall) if gall else 0,
                                        level_rom, len(level), guard_rom, len(guard), guri_rom, len(guri),
                                        melee_rom, len(melee), duel_rom, duel_len if duel else 0, snd_rom, snd_tab, snd_pitch,
                                        saber_rom)
    if gall:
        assert len(code) <= GALL_VRAM - GALL_CODE, f'Gall Run code is {len(code)} bytes, past {GALL_VRAM:#x}'
        gall = code + bytes(GALL_VRAM - GALL_CODE - len(code)) + gall
    rom = bytearray(src)
    assert rom[BOOT_STUB_ROM:BOOT_STUB_ROM + 56] == bytes(56), 'boot stub area is not free'
    assert struct.unpack_from('>I', rom, BOOT_CALL_ROM)[0] == BOOT_CALL_ORIG
    assert len(payload) <= PAYLOAD_SPACE - 8, 'payload outgrew PAYLOAD_SPACE'
    bss_end = int(next(l.split()[0] for l in syms.splitlines() if l.endswith(' _bss_end')), 16)
    assert bss_end <= PAYLOAD_RAM_END, f'.bss ends at {bss_end:#x}, past {PAYLOAD_RAM_END:#x}'
    if saber_rom:
        sym = lambda n: int(next(l.split()[0] for l in syms.splitlines() if l.endswith(' ' + n)), 16)
        saber_bss, saber_bss_end = sym('_saber_bss_start'), sym('_saber_bss_end')
        assert len(sabercode) <= SABER_SPACE, f'.saber is {len(sabercode)} bytes, past SABER_SPACE'
        assert saber_bss == SABER_VRAM + SABER_SPACE, f'.saber_bss starts at {saber_bss:#x}'
        assert saber_bss_end <= SABER_END, f'.saber_bss ends at {saber_bss_end:#x}, past {SABER_END:#x}'
    rom[BOOT_STUB_ROM:BOOT_STUB_ROM + 56] = boot_stub(PAYLOAD_SPACE)
    struct.pack_into('>I', rom, BOOT_CALL_ROM, jal(BOOT_STUB_VRAM))
    rom += payload + bytes(PAYLOAD_SPACE - len(payload))
    # the cheats slot; when nothing follows it, its last 8 bytes are the ROM's MD5 nonce
    assert len(cheats) <= CHEATS_SPACE - (0 if falcon or guard or guri else 8), f'.cheats is {len(cheats)} bytes, past CHEATS_SPACE'
    assert len(rom) == CHEATS_ROM
    rom += cheats + bytes(CHEATS_SPACE - len(cheats))
    if falcon:
        rom += falcon + gall
        assert not level or len(rom) == level_rom
        rom += level
    if guard:
        assert len(rom) == guard_rom
        rom += guard
    if guri:
        assert len(rom) == guri_rom
        rom += guri
    if melee:
        assert len(rom) == melee_rom
        rom += melee
    if duel:
        assert len(rom) == duel_rom
        rom += duel
    if snd:
        assert len(rom) == snd_rom
        rom += snd
    if saber_rom:
        assert len(rom) == saber_rom
        rom += sabercode + bytes(SABER_SPACE - len(sabercode))
    if falcon or guard or guri or snd or saber_rom:
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
    if guard:
        print(f'guard image {len(guard)} bytes at ROM {guard_rom:#x} -> {GUARD_VRAM:#x}')
    if guri:
        print(f'guri image {len(guri)} bytes at ROM {guri_rom:#x} -> {GURI_VRAM:#x}')
    if melee:
        print(f'melee image {len(melee)} bytes at ROM {melee_rom:#x} -> {MELEE_VRAM:#x}')
    if duel:
        print(f'duel level {duel_len} bytes at ROM {duel_rom:#x} (sub-level 33, uncompressed)')
    if snd:
        print(f'saber sounds {len(snd)} bytes at ROM {snd_rom:#x}')
    if saber_rom:
        print(f'saber code {len(sabercode)} bytes at ROM {saber_rom:#x} -> {SABER_VRAM:#x} (slot {SABER_SPACE:#x}), '
              f'.bss to {saber_bss_end:#x}')
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
