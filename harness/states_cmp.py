"""Compare savestates without running them: level id, game frame, the player's place, and how many RAM words differ.

    python3 states_cmp.py <made.st> [<reference.st>]

One line per state (level id 0x8013CE0E, frame counter 0x8018E9B0, the player found as game.find_player does), then,
with two, the count of differing 32-bit words of RDRAM and their span, and the level zones whose vertex base differs
(reverse-engineering.md *Level zones*: a debug teleport detour leaves zones on other bases).
"""
import gzip, struct, sys

RDRAM = 0x1BC                      # mupen64plus M64+SAVE: RDRAM (8 MB, little-endian words) at this offset


def ram(path):
    d = open(path, 'rb').read()
    d = gzip.decompress(d) if d[:2] == b'\x1f\x8b' else d
    raw = d[RDRAM:RDRAM + 0x800000]
    return b''.join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4))      # big-endian, as the console sees it


def player(E):
    for t in (b'Humn', b'HumT'):
        i = E.find(t)
        while i >= 0:
            if i % 4 == 0 and i > 0x150000 and struct.unpack_from('>I', E, i + 4)[0] in (7, 0x47):
                x = struct.unpack_from('>f', E, i + 0x50)[0]
                if 1 < abs(x) < 5000:
                    return t.decode(), struct.unpack_from('>3f', E, i + 0x50)
            i = E.find(t, i + 1)
    return None, None


ZONES = 0x800D2400                 # -> the first level zone record; the next at +0xB8, its vertex base s16 (x, y) at +0x14


def zones(E):
    """The level's zone records in list order: [(address, (base x, base y))]."""
    out, z = [], struct.unpack_from('>I', E, ZONES & 0xFFFFFF)[0]
    while z and len(out) < 1000:
        out.append((z, struct.unpack_from('>2h', E, (z & 0xFFFFFF) + 0x14)))
        z = struct.unpack_from('>I', E, (z & 0xFFFFFF) + 0xB8)[0]
    return out


def line(path, E):
    lvl, = struct.unpack_from('>H', E, 0x13CE0E); gf, = struct.unpack_from('>I', E, 0x18E9B0)
    cls, p = player(E)
    where = '%s (%.1f, %.1f, %.1f)' % (cls, *p) if p else 'no player'
    print(f'{path}: level {lvl} frame {gf} {where}')


if __name__ == '__main__':
    Es = [ram(p) for p in sys.argv[1:3]]
    for p, E in zip(sys.argv[1:3], Es): line(p, E)
    if len(Es) == 2:
        a, b = Es
        diff = [i for i in range(0, len(a), 4) if a[i:i + 4] != b[i:i + 4]]
        print(f'RAM words differing: {len(diff)}' + (f' ({0x80000000 + diff[0]:#x}..{0x80000000 + diff[-1]:#x})' if diff else ''))
        za, zb = zones(a), zones(b)
        off = [(i, ba, bb) for i, ((_, ba), (_, bb)) in enumerate(zip(za, zb)) if ba != bb]
        print(f'zones {len(za)} / {len(zb)}, vertex base differing: {len(off)}'
              + ''.join(f' #{i} {ba}/{bb}' for i, ba, bb in off[:8]) + (' ...' if len(off) > 8 else ''))
