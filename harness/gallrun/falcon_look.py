"""falcon.bin's look in RAM (one Falcon model, lit in the mission and every other level, unlit in Cut 05 (11) and the last
scene (31) as the scenes' own Outrider is: falcon.c falcon_look()).

  falcon_look.py <rom> [--check] STATE...   each state's RAM 10 frames after its load: a LOOK line (below); --check:
      PASS / FAIL per state: unlit in Cut 05 (11) and the last scene (31), lit elsewhere, IMG_FALCON's words 0
  import: look(r32, r16) -> dict, line(d) -> str (c05_check.py / fin_check.py --look print it per change)

LOOK: the level, the part materials' (+0, +0xC) words seen, the vertices whose bytes +12..+14 equal the image's colour
table (IMG_FALCON_COL, GALL +412) and those equal to falcon.bin's own (its normals as built, local/game/falcon.bin), of the
table's count; the image's old Falcon slot (IMG_FALCON, GALL +328..+336) words; 'unlit' / 'lit' / 'MIXED'."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import paths
FALCON_RAM, GALL, IMG_FALCON_COL, IMG_FALCON, LEVEL = 0x80500000, 0x80628000, 412, 328, 0x8013CE0E
ASSET = open(os.path.join(paths.GAME, 'falcon.bin'), 'rb').read()


def look(r32, r16):
    r8 = lambda a: (r32(a & ~3) >> (8 * (3 - (a & 3)))) & 0xFF
    n, lst, col = r32(FALCON_RAM + 4), r32(FALCON_RAM + 8), r32(GALL + IMG_FALCON_COL)
    nv = r32(col) if 0x80000000 <= col < 0x80800000 else 0
    mats, k, tab, own = set(), 0, 0, 0
    for i in range(n if 0 < n <= 32 else 0):
        p = r32(lst + 4 * i); m = r32(p + 0x24); mats.add((r32(m), r32(m + 0xC)))
        a = r32(p + 0x28)
        while r32(a) >> 24 != 0xB8:
            if r32(a) >> 24 == 0x04:
                for j in range((r32(a) & 0xFFFF) >> 9):
                    v = r32(a + 4) + 16 * j + 12
                    b = [r8(v + t) for t in range(3)]
                    if k < nv and b == [r8(col + 4 + 3 * k + t) for t in range(3)]: tab += 1
                    if b == list(ASSET[v - FALCON_RAM:v - FALCON_RAM + 3]): own += 1
                    k += 1
            a += 8
    kind = ('unlit' if mats == {(0xC, 0)} and tab == k else 'lit' if mats == {(0xE, 0xE)} and own == k else 'MIXED')
    return dict(lvl=r16(LEVEL), mats=sorted(mats), vtx=k, nv=nv, tab=tab, own=own,
                old=[r32(GALL + IMG_FALCON + 4 * i) for i in range(3)], kind=kind)


def line(d):
    return (f"LOOK lvl {d['lvl']} {d['kind']} mats {[(hex(a), hex(b)) for a, b in d['mats']]} vertices {d['vtx']} "
            f"(table {d['nv']}): = table {d['tab']}, = falcon.bin {d['own']}; IMG_FALCON {[hex(x) for x in d['old']]}")


if __name__ == '__main__':
    from gallrun.gall_asset import dump_ram
    chk = '--check' in sys.argv; args = [a for a in sys.argv[1:] if a != '--check']
    rom, states = args[0], [os.path.abspath(s) for s in args[1:]]
    bad = 0
    for st, E in zip(states, dump_ram(rom, states)):
        R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFC)[0]
        H = lambda a: struct.unpack_from('>H', E, a & 0x7FFFFE)[0]
        d = look(R, H); print(os.path.basename(st), line(d), flush=True)
        if chk:
            ok = d['kind'] == ('unlit' if d['lvl'] in (11, 31) else 'lit') and not any(d['old'])
            bad += not ok; print(f"CHECK (look {os.path.basename(st)})", 'PASS' if ok else 'FAIL', f"level {d['lvl']} {d['kind']}", flush=True)
    sys.exit(1 if bad else 0)
