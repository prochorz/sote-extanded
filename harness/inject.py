"""Put the freshly built payload into a running game (after load_state).

PAYLOAD_BUILD: directory with payload.elf / payload.bin (default: the controls patch build).
Savestates hold the payload of whatever build they were made with. inject() copies
payload.bin to 0x807C0000, zeroes its .bss (not in payload.bin), copies cheats.c's code, the Falcon model
and the Gall Run image (features cheats, falcon, gallrun) and replays the hook table, so a state saved once
keeps working across rebuilds. Requires M64CPU=0: the dynarec and cached interpreter
don't notice code written through the debugger memory pointer.
A state saved with more features than the current build still has their hooks written into the
game code; inject() first puts the game's own instructions back at every known hook address
(from local/work/main.bin), so building --without a feature works on any state.
inject(e, payload=False) only does that restore: the unpatched game on any state, whatever
build it was saved with (the payload left in RAM is never reached).
"""
import os, re, struct, subprocess, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

BUILD = Path(os.environ.get('PAYLOAD_BUILD') or Path(paths.BUILD) / 'sote-patch')
ASSETS = Path(paths.GAME)
LLVM = Path('/opt/homebrew/opt/llvm/bin')
HOOKS_S = Path(__file__).resolve().parent.parent / 'sote-patch' / 'src' / 'hooks.S'
PAYLOAD_VRAM = 0x807C0000
PAYLOAD_MAX = 0x807E0000              # tests put fake objects here (FAKE in testlib.py)
MAIN_VRAM = 0x80001EC0
FALCON_VRAM = 0x80500000            # build.py FALCON_VRAM
CHEATS_CODE = 0x80540000            # build.py CHEATS_VRAM (link.ld .cheats)
GALL_CODE = 0x80600040                # build.py GALL_CODE
GALL_VRAM = 0x80628000              # build.py GALL_VRAM


def all_hooks():
    """Every game address any build of the patch overwrites: all hook_table entries in hooks.S,
    whatever FEATURE_* #if they sit under."""
    src = HOOKS_S.read_text()
    table = src[src.index('hook_table:'):]
    table = table[:table.index('.word 0, 0')]
    return [int(a, 16) for a in re.findall(r'^\s*\.word\s+(0x8[0-9A-Fa-f]{7})', table, re.M)]


def syms():
    """Payload symbol -> address (g_player, g_lock, g_test_skip_los, ...)."""
    out = subprocess.run([str(LLVM / 'llvm-nm'), str(BUILD / 'payload.elf')],
                         capture_output=True, text=True, check=True).stdout
    return {p[2]: int(p[0], 16) for p in (l.split() for l in out.splitlines()) if len(p) == 3}


def _restore_game_code(e, required):
    main = Path(paths.WORK) / 'main.bin'
    if not main.exists():
        if required: raise FileNotFoundError(f'{main} (see disasm.py for how to make it)')
        print('[inject] no local/work/main.bin: hooks of features missing from this build stay in RAM',
              file=sys.stderr, flush=True)
        return
    code = main.read_bytes()
    for a in all_hooks():
        e.w32(a, struct.unpack_from('>I', code, a - MAIN_VRAM)[0])


def inject(e, payload=True):
    _restore_game_code(e, required=not payload)
    if not payload: return
    blob = (BUILD / 'payload.bin').read_bytes()
    assert PAYLOAD_VRAM + len(blob) <= PAYLOAD_MAX, f'payload is {len(blob):#x} bytes, overlaps {PAYLOAD_MAX:#x}'
    blob += bytes(-len(blob) % 4)
    for i in range(0, len(blob), 4):
        e.w32(PAYLOAD_VRAM + i, struct.unpack_from('>I', blob, i)[0])
    s = syms()
    assert s['_bss_end'] <= PAYLOAD_MAX, f".bss ends at {s['_bss_end']:#x}, overlaps {PAYLOAD_MAX:#x}"
    for i in range(s['_bss_start'], s['_bss_end'], 4):    # what _start does on boot
        e.w32(i, 0)
    if 'cheats_frame' in s:               # _start copies cheats.c's code (link.ld .cheats) at boot
        code = (BUILD / 'cheatscode.bin').read_bytes()
        code += bytes(-len(code) % 4)
        for i in range(0, len(code), 4):
            e.w32(CHEATS_CODE + i, struct.unpack_from('>I', code, i)[0])
    if 'falcon_frame' in s:               # the Falcon model
        img = (ASSETS / 'falcon.bin').read_bytes()
        img += bytes(-len(img) % 4)
        for i in range(0, len(img), 4):
            e.w32(FALCON_VRAM + i, struct.unpack_from('>I', img, i)[0])
    if 'gallrun_frame' in s:              # and the Gall Run's code (link.ld .gall) and its image
        code = (BUILD / 'gallcode.bin').read_bytes()
        code += bytes(-len(code) % 4)
        for i in range(0, len(code), 4):
            e.w32(GALL_CODE + i, struct.unpack_from('>I', code, i)[0])
        img = bytearray((ASSETS / 'gall_run.bin').read_bytes())
        img += bytes(-len(img) % 4)
        fix = struct.unpack_from('>I', img, 96)[0] if len(img) > 100 else 0
        rom = BUILD / 'sote-patch.z64'     # build.py makes that word a ROM address (Chewie's sample):
        if fix and rom.exists():              # sounds only play when the emulator runs this ROM
            at = rom.read_bytes().find(bytes(img[:256]))
            struct.pack_into('>I', img, fix, struct.unpack_from('>I', img, fix)[0] + max(at, 0))
        for i in range(0, len(img), 4):
            e.w32(GALL_VRAM + i, struct.unpack_from('>I', img, i)[0])
    if 'gallrun_boot' in s:               # _start's gallrun_boot(): the sub-level tables' stock 32 entries into
        L, X = s['g_levels'], s['g_level_index']   # g_levels (33: the Gall Run is 32), the level-index bytes too
        for i in range(16): e.w32(L + 4 * i, e.r32(0x80001330 + 4 * i))
        for i in range(32):
            e.w32(L + 0x40 + 4 * i, e.r32(0x80001370 + 4 * i))
            e.w32(L + 0xC4 + 4 * i, e.r32(0x800013F0 + 4 * i))
            for k in range(16): e.w32(L + 0x148 + 64 * i + 4 * k, e.r32(0x80001470 + 64 * i + 4 * k))
        for i in range(0, 32, 4): e.w32(X + i, e.r32(0x800DD77C + i))
    a = s['hook_table']                   # (address, instruction) pairs, 0-terminated
    while (addr := e.r32(a)):
        e.w32(addr, e.r32(a + 4))
        a += 8


LEVEL_ROMS, LEVEL_PACKS, LEVEL_RUN = 0x80001370, 0x800013F0, 6   # gallrun.c level_table()


def gall_level(e, rom):
    """(Builds before bf49: the mission ran as sub-level 6. Since then it is sub-level 32:
    load 32, no table change.) Point sub-level 6's level-table entries at the Gall Run level in the ROM the emulator runs
    (rom: its path, a gallrun build's sote-patch.z64), as gallrun_start() does in the game. A take
    that sets g_gallrun itself and loads the level without this gets the stock base level (the
    player ship then is the Outrider)."""
    lv = (ASSETS / 'gall_level.bin').read_bytes()
    at = Path(rom).read_bytes().find(lv[:4096])
    assert at > 0, f'{rom} has no Gall Run level: run a gallrun build ROM'
    e.w32(LEVEL_ROMS + 4 * LEVEL_RUN, at)
    e.w32(LEVEL_PACKS + 4 * LEVEL_RUN, len(lv))      # flag byte 0: uncompressed

