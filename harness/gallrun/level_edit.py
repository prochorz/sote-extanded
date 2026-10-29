"""The Gall Run level: the base level's sub-level blob (feature `gallrun`) with our changes in its data,
instead of overriding them every frame (docs/reverse-engineering.md, "Objects in a sub-level blob").

    python3 gallrun/level_edit.py      (../local/game/gall_level_stock.bin + falcon.bin -> gall_level.bin)

gall_level_stock.bin is the unchanged blob (harness/level_blob.py <rom> 6 <out>). The blob's code and
model data are linked for its load address (absolute words), its object data is relocated at load.
Changes:
1. The player ship (Stft, model root = node 74) is the Millennium Falcon: the model's group
   (GROUP: two engine glow meshes, the hull, the two gun nodes, the pulsing glow node) gets the
   Falcon's mesh node (falcon.bin header +32, at FALCON_RAM) in the hull's place and loses the two
   glows; the guns and the pulsing glow stay (falcon.c puts them on the Falcon every frame, the game
   builds their matrices). The Outrider's own meshes stay in the blob, out of the ship's model:
   gallrun.c draws Dash's ship with them (OR_MESHES).
2. No space rocks or debris but the five space rocks gallrun.c draws through (POOLS).
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import paths
ASSETS = paths.GAME
LOAD = 0x80196950
GROUP = 0x801A3AB8                 # the player model's group (under root 0x801A2880)
GROUP_KIDS = (0x801A3C64, 0x801A3C7C, 0x801A3C94, 0x801A28C8, 0x801A2910, 0x801A2958)
# Class pools (header: tag, a word, count, size, pool offset): space rocks down to the five whose nodes gallrun.c
# draws through (the Outrider, stage 1, stage 2, Slave I, Dash: OUTRIDER_ASTR, CANYON_ASTR, LAND_ASTR, SLAVE_ASTR, DASH_ASTR), the debris that flies
# round the ship (AstF) gone. A red and a black rock showed over the canyon (the user, 2026-10-09).
POOLS = [(0x8019A038, b'Astr', 10, 5), (0x8019A8F8, b'AstF', 1, 0)]
HULL = 0x801A3C94                  # glows 0x801A3C64, 0x801A3C7C; guns 0x801A28C8/2910; pulse 0x801A2958


def edit(blob, falcon):
    b = bytearray(blob)
    R = lambda a: struct.unpack_from('>I', b, a - LOAD)[0]
    W = lambda a, v: struct.pack_into('>I', b, a - LOAD, v)
    assert b[:4] == b'LStb' and R(LOAD + 4) == LOAD, 'not a sub-level blob'
    assert falcon[:4] == b'FALC'
    node = struct.unpack_from('>I', falcon, 32)[0]
    n, lst = R(GROUP + 12), R(GROUP + 16)
    assert n == 6 and tuple(R(lst + 4 * i) for i in range(6)) == GROUP_KIDS, 'not the stock ship model'
    kids = [node, 0x801A28C8, 0x801A2910, 0x801A2958]
    for i in range(6): W(lst + 4 * i, kids[i] if i < len(kids) else 0)
    W(GROUP + 12, len(kids))
    for hdr, tag, n0, n1 in POOLS:              # space's rocks out of the level: pool counts cut
        assert b[hdr - LOAD:hdr - LOAD + 4] == tag and R(hdr + 8) == n0, f'not the stock {tag} pool'
        W(hdr + 8, n1)
    return bytes(b)


if __name__ == '__main__':
    blob = open(os.path.join(ASSETS, 'gall_level_stock.bin'), 'rb').read()
    falcon = open(os.path.join(ASSETS, 'falcon.bin'), 'rb').read()
    out = os.path.join(ASSETS, 'gall_level.bin')
    open(out, 'wb').write(edit(blob, falcon))
    print('gall level:', os.path.relpath(out), len(blob), 'bytes')
