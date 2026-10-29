"""The Gall Run's chase in space (the user, 2026-10-13: up out of the atmosphere): the Star Destroyer by the rail's end
(the base level's own, states/src_base.st) and the battle's ships (an X-Wing from the space level, states/src_space.st). Their parts
are the last of stage 2's (drawn by its node: the vertices in its frame); gallrun.c shows them from AST_SHOW up, with
the base level's belt backdrop. (Space rocks along the rail were dropped: they flew at the Falcon, the user.)

    blob, parts, at, heading, battle_mid = star_destroyer(Ea, rail, base, to_level)
    blob, h = fighter(E, mesh, base)
"""
import math, os, struct
import paths
import numpy as np
from mesh_image import build_image


SD_MESH = 0x801A3B74          # the base level's Imperial Star Destroyer (32 parts, ~5100 long along its +y, nose +y)
SD_SCALE = 0.4                # (~2000 long: the Falcon is ~36)
SD_AT = 0.6                   # (the user, 2026-10-15: the rail crosses it over its middle) its middle under the rail's
SD_ANGLE = math.radians(90)   # space part this share along, its long axis this far off the rail there, its highest
SD_OVER = 150.0               # vertex this far under the rail
SD_HALF_W = 620.0             # (its half width, ~0.6 of its length)
DASH_NEAR = 1200.0            # story: Dash quits when the rail comes this near its near side (it looms under them)
SLAVE_PAST = 900.0            # Slave I jumps this far (along the rail) past its far side
BATTLE_ALONG = 0.0            # the battle right over its middle (the user, 2026-10-18; was 1000 along its long axis, off the rail)
BATTLE_CLEAR = 0.0            # the battle's middle on the rail's height, over the hull on Slave I's line (the user, 2026-10-19;
BATTLE_LOW = 0.0              # were 250 and 150: the rail under the fight); gall_ties.c BATTLE_DZ keeps the rings off the hull
                              # (gall_ties.c battle_pose(): 90 * (pair - 1) + 60 * sin, pair 0)


def star_destroyer(Ea, rail, base, to_level, space_from, share=True):
    """The Star Destroyer across the rail in space, the Falcon flying over its middle: (blob, its parts' addresses, its
    middle, heading, the battle's middle (world), the story's rail nodes (Dash quits, closing in, Slave I jumps))."""
    P = np.asarray(rail, float)
    L = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(P[:, :2], axis=0).T))])
    s0 = L[space_from]; sp = s0 + (L[-1] - s0) * SD_AT
    kp = int(np.searchsorted(L, sp))
    d = (P[kp + 1] - P[kp - 1])[:2]; d /= np.hypot(*d)
    a = math.atan2(d[1], d[0]) + SD_ANGLE
    ax = np.array([math.cos(a), math.sin(a)])                      # its long axis (its nose along it)
    h = a - math.pi / 2                                            # (its +y, its nose, along ax)
    M = np.array([[math.cos(h), -math.sin(h), 0], [math.sin(h), math.cos(h), 0], [0, 0, 1]]) * SD_SCALE
    zs = []                                                        # its highest vertex over its middle (a dry run;
    _, h0 = build_image(Ea, [SD_MESH], base, xf=lambda x, y, z: zs.append((M @ np.array([x, y, z]))[2]) or (x, y, z),
                        untextured=False, share=False)
    zs = zs[:-8 * h0['parts']]                                     # xf's last calls: each part's box, 8 corners)
    at = np.array([P[kp, 0], P[kp, 1], P[kp, 2] - SD_OVER - max(zs)])
    blob, hh = build_image(Ea, [SD_MESH], base, xf=lambda x, y, z: to_level(*(M @ np.array([x, y, z]) + at)),
                           untextured=False, share=share)   # (share=False: a copy not kept in the image)
    lst = hh['list'] - base
    parts = [int.from_bytes(blob[lst + 4 * i:lst + 4 * i + 4], 'big') for i in range(hh['parts'])]
    across = (P[:, :2] - at[:2]) @ np.array([-ax[1], ax[0]])      # the rail's way across it (+ past it)
    across *= 1 if across[-1] > across[space_from] else -1
    k_dash = next((k for k in range(space_from, kp) if across[k] > -(SD_HALF_W + DASH_NEAR)), space_from)
    k_close = int(np.argmin(np.abs(across[space_from:]))) + space_from   # (over its long axis)
    k_slave = next((k for k in range(k_close, len(P)) if across[k] > SD_HALF_W + SLAVE_PAST), len(P) - 8)
    up = max(zs) + SD_OVER + BATTLE_CLEAR + BATTLE_LOW            # (over its middle: the rail's height + the clearance)
    mid = at + np.array([ax[0] * BATTLE_ALONG, ax[1] * BATTLE_ALONG, up])
    print('Star Destroyer: middle', at.round(), 'top', round(max(zs)), 'rail at the closing node', P[k_close].round(), 'battle', mid.round(),
          flush=True)
    return blob, parts, at, a, mid, (k_dash, k_close, k_slave)


SPACE_AT = 2600.0              # straighten(): from this far over the route's end (space: the sky black, gallrun.c SKY_TO)
SPACE_TURN = 0.9              # the rail on in one gentle bend (radians in all, eased in and out), not the canyon's bends
                              # below it (the user, 2026-10-14: in space no guide; its end by the Star Destroyer)


def straighten(rail, end_z):
    """The rail in space: up to SPACE_AT over the route's end as it is (up the canyon, its bends), then on from there
    in one gentle bend at its own height, as many nodes as far apart."""
    P = np.asarray(rail, float)
    ks = next((k for k in range(len(P)) if P[k, 2] - end_z >= SPACE_AT), None)
    if ks is None or ks < 3 or ks >= len(P) - 2: return rail
    d = P[ks, :2] - P[ks - 3, :2]; h0 = math.atan2(d[1], d[0])
    steps = np.hypot(*np.diff(P[ks:, :2], axis=0).T)
    L = float(steps.sum()); out = [tuple(p) for p in P[:ks + 1]]; q = P[ks, :2].copy(); s = 0.0
    for k, st in enumerate(steps):
        u = (s + st / 2) / L; yaw = h0 + SPACE_TURN * (u * u * (3 - 2 * u))
        q = q + st * np.array([math.cos(yaw), math.sin(yaw)]); s += st
        out.append((float(q[0]), float(q[1]), float(P[ks + 1 + k, 2])))
    return out


XWING_MESH = 0x801A5918       # the space level's X-Wing (the player ship's variant 1, states/src_space.st: 29 parts, ~28 x 35, nose +y)


def fighter(E, mesh, base):
    """A ship's mesh copied as it is (its own units, about its node): (blob, {parts, list, box})."""
    return build_image(E, [mesh], base, untextured=False)


FALCON_RAM = 0x80500000      # falcon.bin's place (_start copies it there before any level; falcon_asset.py BASE)
FALCON_BIN = os.path.join(paths.GAME, 'falcon.bin')
FALCON_GREY = (122, 255)      # the grey baked into falcon.bin's vertex bytes in Cut 05 and the last scene, belly to top, by
                              # the vertex's height (the game's way for Cut 05's Outrider: unlit, its shade baked into its
                              # vertex colours 122..255; one model since)


def falcon_vertices(F):
    """falcon.bin's vertices (RAM addresses) in the order falcon.c walks them: its parts in list order, each part's
    geometry DL, each G_VTX block in it (the blocks do not overlap)."""
    R = lambda a: struct.unpack_from('>I', F, a - FALCON_RAM)[0]
    assert F[:4] == b'FALC', 'not falcon.bin'
    n, lst = R(FALCON_RAM + 4), R(FALCON_RAM + 8)
    out = []
    for i in range(n):
        a = R(R(lst + 4 * i) + 0x28)
        while R(a) >> 24 != 0xB8:
            if R(a) >> 24 == 0x04: out += range(R(a + 4), R(a + 4) + ((R(a) & 0xFFFF) >> 9) * 16, 16)
            a += 8
    assert len(out) == len(set(out)), 'G_VTX blocks overlap'
    return out


def falcon_colours(path=FALCON_BIN):
    """IMG_FALCON_COL: the colour table falcon.c writes into falcon.bin's vertex bytes +12..+14 while
    the level is Cut 05 or the last scene (unlit there, as the scenes' own Outrider): {u32 vertex count, then 3 bytes a
    vertex in falcon_vertices() order}, grey FALCON_GREY by the vertex's height over the model's z."""
    F = open(path, 'rb').read()
    vtx = falcon_vertices(F)
    zs = [struct.unpack_from('>h', F, v - FALCON_RAM + 4)[0] for v in vtx]
    z0, z1 = min(zs), max(zs); g0, g1 = FALCON_GREY
    img = bytearray(struct.pack('>I', len(vtx)))
    for z in zs: img += bytes([int(round(g0 + (g1 - g0) * (z - z0) / (z1 - z0)))] * 3)
    img.extend(bytes(-len(img) % 16))
    print(f'Falcon colours (Cut 05, the last scene): {len(vtx)} vertices, grey {g0}..{g1} over z {z0 / 8:.1f}..{z1 / 8:.1f}, '
          f'{len(img)} bytes', flush=True)
    return bytes(img)


GLOW_MESH = 0x801A3CC4        # the Outrider's pulsing engine glow (states/src_base.st: under node 0x801A2958): one quad,
                              # x -7..7.3, z -2.4..2.7, at y -11.4 (falcon.c moves it onto the Falcon's stern)
GLOW_Y0 = -11.4
GLOW_HALF = 5.5               # the glow along the Falcon's round stern (the user: a flat strip, then three pieces
GLOW_ARC = math.radians(58)   # seen): GLOW_PIECES narrow copies of the quad on an arc this long either side of the
GLOW_PIECES = 7               # middle, turned GLOW_ARC forward at its ends, overlapping by GLOW_OVERLAP,
GLOW_OVERLAP = 2.8            # GLOW_OUT out from the hull (it sank into the model)
GLOW_OUT = 0.5
GLOW_DEEP = 1.6              # the arc this much deeper than round (the node stretches it wider than long: falcon.c)
GLOW_THIN = 0.6              # its height (narrower: the user)


OR_SHIP = [0x801A3C64, 0x801A3C7C, 0x801A3C94]   # the Outrider in our level (states/src_base.st): its engine glows and hull
                                                 # (gall_story.c OR_MESHES)


OR_C05_K = 4.47                # Cut 05's Outrider model to our level's (gall_chain.c OR_RUN_K)


def or_glow(E, base):
    """Our level's Outrider's engine glows (OR_SHIP's first two), scaled to Cut 05's model, drawn with its own hull there
    (the user, 2026-10-19: it had no engine lights; our hull showed orange on the phone): (blob, {parts, list, box, lo, hi})."""
    return build_image(E, OR_SHIP[:2], base, xf=lambda x, y, z: (x * OR_C05_K, y * OR_C05_K, z * OR_C05_K), untextured=False)


def glow_bent(E, base):
    """The engine glow round the Falcon's stern: GLOW_PIECES copies of its quad along an arc. (blob, {parts, list,
    box}) at base."""
    blob, parts = b'', []
    R = GLOW_HALF / GLOW_ARC
    k = GLOW_HALF * 2 / GLOW_PIECES * GLOW_OVERLAP / 14.3      # (the quad is 14.3 wide)
    for i in range(GLOW_PIECES):
        th = -GLOW_ARC + (i + 0.5) * 2 * GLOW_ARC / GLOW_PIECES
        tx, ty = math.cos(th), GLOW_DEEP * math.sin(th); tl = math.hypot(tx, ty); tx, ty = tx / tl, ty / tl
        cx = R * math.sin(th) + GLOW_OUT * ty
        cy = GLOW_Y0 + GLOW_DEEP * R * (1 - math.cos(th)) - GLOW_OUT * tx
        def xf(x, y, z, cx=cx, cy=cy, tx=tx, ty=ty):
            u = (x - 0.15) * k
            return (cx + u * tx, cy + u * ty, z * GLOW_THIN)
        b, h = build_image(E, [GLOW_MESH], base + len(blob), xf=xf, untextured=False)
        lst = h['list'] - (base + len(blob))
        parts += [int.from_bytes(b[lst + 4 * i_:lst + 4 * i_ + 4], 'big') for i_ in range(h['parts'])]
        blob += b + bytes(-len(b) % 16)
    lst = base + len(blob)
    blob += b''.join(struct.pack('>I', a) for a in parts) + bytes(-4 * len(parts) % 16)
    box = base + len(blob)
    blob += b''.join(struct.pack('>hhhhhhhh', x, y, z, 0, 0, 0, 0, 0)
                     for x in (-160, 160) for y in (-160, 160) for z in (-60, 60))
    return blob, dict(parts=len(parts), list=lst, box=box)


TOWER_MESH = 0x801A5960       # the space level's gun tower (states/src_space.st; class PRBT's model: one part, 95 across, 115 high,
                              # its foot at z 0)
TOWER_MESH_NODE = 0x18        # (its mesh node's size: kind, flags, render record, count, list, box)
TOWER_NODE = 0x801A2D90       # tower 0's node (transform, 0x48 bytes: +0xC count, +0x10 list, +0x14 rows, +0x38 place)
TOWER_GROUP = 0x801A5640      # their group under the world root (0x14 bytes: +0xC count, +0x10 list)
TOWER_OBJ = 0x8019F6B0        # tower 0's object (PRBT, 0x214 bytes): the template (gall_space.c towers_on())
TOWER_SIZE = 0x214
TOWER_ROW = (-0.28, -0.19, -0.10)   # (the user, 2026-10-18, by a model's photos: a row along each side of the
TOWER_CLEAR = 15.0            # superstructure's foot) 3 a side at these shares of its length from its middle (+ to the
TOWER_JUMP = 8.0              # nose); its foot: the last height step over this in 2 units out from its middle line;
TOWER_SLOPE = 0.4             # the tower's edge this much further; under its footprint the deck no steeper than this.
TOWER_SCALE = 0.4             # Squat as the real
TOWER_SCALE_Z = 0.25          # domes (the user: not sticking up): ~38 across, ~29 high; the foot at the footprint's lowest
                              # deck point, so it never floats over the sloping deck
TOWER_MTX_SLOT = 140          # node i's world-matrix slot (+0x44): the draw walk builds each node's matrix into a slot of
                              # the level's buffers (0x80017FB0); the base level uses 0..109 in the battle, the copied
                              # space level's 30 was shared with one of its nodes: the towers drawn elsewhere, unseen
TOWER_NOCULL = 1e5             # (gall_asset.py NOCULL)
TOWER_X_MIN = 2100.0          # the game's tower code works only at |x| > 2000 (the space level's arms: 0x800823F8, 0x800824F4)


def _top(T, x, y):
    """The highest of the triangles T (n, 3, 3) over (x, y), or None."""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(d) > 1e-6
    d = np.where(ok, d, 1)
    u = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
    v = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
    w = 1 - u - v
    hit = ok & (u >= -1e-4) & (v >= -1e-4) & (w >= -1e-4)
    if not hit.any(): return None
    return float((u * a[:, 2] + v * b[:, 2] + w * c[:, 2])[hit].max())


def tower_spots(T, at, heading):
    """The towers' places on the Star Destroyer's top (T: its triangles in world units): [(x, y, z)]. Along its long
    axis from the middle of its length; across from the middle of its width at that slice (rays down: the mesh's middle
    is off its node's)."""
    o = np.asarray(at[:2], float)
    ax = np.array([math.cos(heading), math.sin(heading)]); ac = np.array([-ax[1], ax[0]])
    P = T.reshape(-1, 3); along = (P[:, :2] - o) @ ax
    mid, length = (along.max() + along.min()) / 2, along.max() - along.min()
    r = 47.6 * TOWER_SCALE                                     # (the model's half width)
    top = lambda s, c: _top(T, *(o + ax * s + ac * c))
    feet = lambda s, c: [top(s + ds, c + dc) for ds in (-r, 0, r) for dc in (-r, 0, r)]
    spots = []
    for side in (-1, 1):                                       # (one straight row a side, at its widest foot)
        row = []
        for u in TOWER_ROW:
            s = mid + u * length
            cs = [c for c in np.linspace(-length, length, 801) if top(s, c) is not None]
            centre, half = (cs[-1] + cs[0]) / 2, (cs[-1] - cs[0]) / 2
            cs = np.arange(0, half, 2.0)
            zs = [top(s, centre + side * c) for c in cs]
            row.append((s, centre + side * max(cs[i] for i in range(1, len(cs))   # (the superstructure's foot: its
                        if zs[i] is not None and zs[i - 1] is not None and abs(zs[i] - zs[i - 1]) > TOWER_JUMP)))   # last step)
        line = max(side * c for _, c in row) + r + TOWER_CLEAR
        for s, _ in row:
            c = side * line
            zs = feet(s, c)
            assert all(z is not None for z in zs) and max(zs) - min(zs) < 2 * r * TOWER_SLOPE, \
                f'a tower off the hull or on a step ({s}, {side})'
            p = o + ax * s + ac * c
            spots.append((float(p[0]), float(p[1]), min(zs)))
    assert all(abs(x) > TOWER_X_MIN for x, _, _ in spots), f'a tower at |x| <= {TOWER_X_MIN}: the game would not run it'
    return spots


def towers(E, spots, heading, base):
    """The space level's gun towers at spots, for the game's own tower objects (gall_space.c): (blob, {count, recs, template,
    pool, group}). recs: per tower its node, x, y, z, yaw (degrees; the object's +0x14)."""
    blob, h = build_image(E, [TOWER_MESH], base, xf=lambda x, y, z: (x * TOWER_SCALE, y * TOWER_SCALE, z * TOWER_SCALE_Z),
                          untextured=False)
    blob = bytearray(blob)
    for i in range(h['parts']):                    # (no part culled by its box: under stage 2's scaled node the game
        p_ = struct.unpack_from('>I', blob, h['list'] - base + 4 * i)[0] - base   # culled them, as it did the stages'
        struct.pack_into('>6f', blob, p_, *(-TOWER_NOCULL,) * 3, *(TOWER_NOCULL,) * 3)   # parts: gall_asset NOCULL)

    def put(b):
        blob.extend(bytes(-len(blob) % 16)); a = base + len(blob); blob.extend(b); return a
    mesh = bytearray(E[TOWER_MESH & 0x7FFFFF:(TOWER_MESH & 0x7FFFFF) + TOWER_MESH_NODE])
    struct.pack_into('>II', mesh, 4, 0, 0)          # (+4, +8 as our stages' mesh nodes: the space level's 0x2F1 and its render
    struct.pack_into('>III', mesh, 0xC, h['parts'], h['list'], h['box'])   # record drew the towers only when huge)
    mesh = put(mesh)
    kids = put(struct.pack('>I', mesh))
    yaw = math.degrees(heading) % 360
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    nodes = []
    for x, y, z in spots:
        n = bytearray(E[TOWER_NODE & 0x7FFFFF:(TOWER_NODE & 0x7FFFFF) + 0x48])
        n[2] = 0xFF                             # (+2's high byte 0xFF: drawn; the object's draw sets it too, 0x8001040C)
        struct.pack_into('>II', n, 0xC, 1, kids)
        struct.pack_into('>9f', n, 0x14, c, s, 0, -s, c, 0, 0, 0, 1)
        struct.pack_into('>I', n, 0x44, TOWER_MTX_SLOT + len(nodes))   # (its own world-matrix slot: the space level's 30 was taken)
        struct.pack_into('>3f', n, 0x38, x, y, z)
        nodes.append(put(n))
    grp = bytearray(E[TOWER_GROUP & 0x7FFFFF:(TOWER_GROUP & 0x7FFFFF) + 0x14])
    struct.pack_into('>II', grp, 0xC, len(nodes), put(b''.join(struct.pack('>I', a) for a in nodes)))
    group = put(grp)
    t = bytearray(E[TOWER_OBJ & 0x7FFFFF:(TOWER_OBJ & 0x7FFFFF) + TOWER_SIZE])
    assert t[:4] == b'PRBT', 'tower 0 is not a PRBT'
    struct.pack_into('>I', t, 0xF0, 0)
    template = put(t)
    pool = put(bytes(TOWER_SIZE * len(spots)))
    recs = put(b''.join(struct.pack('>Iffff', a, x, y, z, yaw) for a, (x, y, z) in zip(nodes, spots)))
    return bytes(blob), dict(count=len(spots), recs=recs, template=template, pool=pool, group=group)
