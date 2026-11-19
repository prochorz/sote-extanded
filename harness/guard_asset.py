"""Build the red palace guard's look for Dash (feature `guard`): the guard's meshes baked onto Dash's bones.

    M64CPU=0 python3 guard_asset.py <rom> [out.bin]     (default local/game/guard.bin)
    python3 guard_asset.py --same <old.bin> <new.bin>  the same look in both images? PASS / FAIL per section (exit 1
                                                        on a FAIL): run after any remake that should not change it

The guard (sub-level 26, the palace: a Trop of kind 0, animation block `trSt`, 17 bones) and Dash (Humn, block `trot`,
19 bones) share a skeleton but the neck (docs/reverse-engineering.md, the sub-level list's paragraph on 26). The level
data is compressed in the ROM, so the meshes are taken from RAM: load states/palace.st, dump RDRAM, copy each guard
mesh with its vertices baked into the matched Dash bone's own frame, and move it to BASE with every pointer fixed, as
falcon_asset.py does for the Falcon. guard.c hangs the meshes on Dash's bone nodes.

The bake works in the bones' local frames (no pose): v' = s * R * v, R the shortest turn of the guard child's local
translation (node +0x38) onto Dash's, scaled by their length ratio along the bone and the torso ratio across; a leaf (hand, foot) takes its parent's; the pelvis, spine,
chest and head no turn, the median limb ratio, fitted to Dash's torso by height (KNOTS). (A bake from the posed world frames froze the pose difference
between Dash's `fall` and the guard's `trSt` into the arms, 2026-11-05.) The two models' local frames agree: in
palace.st Rd^-1 * Rg of the pelvis, spine and chest is within 16 degrees of the identity (the pose), so the look is not
turned (TURN 0). ROLL turns a bone's meshes about its limb.
A limb mesh of the guard is a variant group (w0 0x5065ff00); its near variant (VARIANT) is stored as a plain mesh.

Layout at BASE: header {'GARD', 19, per Dash bone (trot order) 0..18: mesh count, mesh list, then 'LUKE', mesh count,
mesh list, then 'LITN', variant count, part count, per part: Dash bone, its variants' mesh nodes, then 'SABR', mesh
count, mesh list, the swings' table (0: none), the HUD icon's sprite record (harness/luke/saber_icon.py), the arm's
table (harness/luke/saber_moves.py's SAR2, then its PRY3 parry grid: two layers), then 'FACE', Luke's HUD portrait's sprite record (harness/luke/
luke_portrait.py, from local/game/cut13.bin; 0: none, when that dump is missing)}, then the texture block (texels,
palettes, texture DLs), the lists, mesh nodes, parts, materials, texture records, geometry DLs + vertices, then Luke's head.

The texture block: the guard's textures lie in the level's RAM among other palace characters' ones. The span its records
reach (their data, their DLs and the segment-4 DLs those call) is copied as regions, split at every run of it that no DL,
palette or texel load reaches and that is GAP_MIN or longer (palace.st: one, 13 KB of 26.9), each region allocated on
its own so it keeps its offset mod 16; every address moves by its region's delta (a segment base by the region its
references land in, asserted one), no reference changing form.

Luke's head (the Look row's Luke, guard.c: Dash's head bone takes it instead of the helmet): harness/luke/luke_head.gltf
(luke_model.py: one node, the guard's head bone, in its frame), converted as guri_asset.py converts the Guri model (its
texture, tex_dl and batches: unlit parts, vertex colours, CI4 textures) into one mesh node, its vertices baked with the
guard head's transform onto Dash's head bone, as the helmet's are. No glTF there: LUKE with no meshes (value 2 draws as
the guard).

The lightning (LITN: guard.c guard_zap adds one variant at a time to those bones' lists): harness/luke/lightning_model.py's
strips over the box of the image's meshes on each of LITN_BONES (the head: Luke's head's box), one plain mesh node per
part and variant, unlit, vertex colours on the white texture (guri_asset.texture(None)). The lightning's and the
saber's meshes (plain_mesh, parts_mesh) share equal vertex records (shared_dl): the models store a vertex per corner.

The saber (SABR, feature saber): harness/luke/saber_model.py's parts as two mesh nodes on Dash's hand bone frame (no
bake): the hilt (guard.c draws it in the weapon's slot of the right hand's list while the weapon id is the saber's),
then the blade, the light shells outer to inner, each on a translucent texture of its alpha (glow_material: 4 x 4 of
one texel, the UVs 0), and the white core last (saber.c draws it in the game's late subtree, after the level); and the swings'
table (harness/luke/saber_moves.py's SWN2: saber.c's seven blocks' key tracks, the combo, the spin and the combo in
place, made from Dash's own blocks in the dump);
and the arm's (SAR2: 21 tracks a block over his movement blocks while the saber is out, both arms' and the spine's,
per block its tag and keys), then 'PRY3', the parry grid's two layers (1.5 and 2.25 ahead of him).
"""
import ctypes, math, os, struct, sys
import numpy as np
import paths
from m64 import Emu

BASE = 0x80548000
LUKE_GLTF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'luke', 'luke_head.gltf')
LIMIT = 0x80580000                   # the Guri image (local/game/guri.bin) starts there
TEX_MAX = 0x40000
GAP_MIN = 4096                       # an unreached run of the texture span this long or longer is not copied
TAG = lambda s: int.from_bytes(s.encode(), 'big')
# guard bone (trSt order) -> (Dash bone (trot order), guard child, Dash child); children None: a leaf or the torso
MAP = {15: (17, None, None), 14: (17, None, None), 13: (9, None, None), 6: (1, None, None),
       5: (13, 4, 12), 4: (12, 3, 11), 3: (11, None, None), 2: (16, 1, 15), 1: (15, 0, 14), 0: (14, None, None),
       12: (8, 11, 7), 11: (7, 10, 6), 10: (6, None, None), 9: (5, 8, 4), 8: (4, 7, 3), 7: (3, None, None)}
LEAF = {3: 4, 0: 1, 10: 11, 7: 8}    # leaf -> the limb bone whose turn and scale it takes
TORSO = (15, 14, 13, 6)
# The torso (pelvis, spine, chest, head) is fitted to Dash's by height: a vertex's height above the pelvis on the
# guard (x the torso ratio) is mapped piecewise linearly through the joint heights (pelvis, spine, chest, shoulders, the
# guard's head joint = Dash's neck) onto Dash's, slope 1 past the ends; across, the torso ratio and the joints' offsets. (Moved
# rigidly by the joints' difference, the spine mesh, the guard's grey belt, slid out below the chest as a grey box,
# 2026-11-06.) KNOTS: (guard bones from the pelvis, Dash bones from the pelvis) per knot.
KNOTS = (((14,), (10,)), ((14, 13), (10, 9)), ((14, 13, 12), (10, 9, 8)), ((14, 13, 6), (10, 9, 2)))
# (the shoulder knot: Dash's shoulders sit 0.86 above where the chest fitted by the neck alone put the guard's, and the
# shoulder pads on his shoulder bones stuck up beside the helmet, 2026-11-06)
# The belt and the chest meet at Dash's chest joint (kd[2]): the belt's top squashed down to it, the chest's lower edge
# up to it, so the chest turning on its joint does not cross the belt (2026-11-06: running, the belt's top showed above
# it as a grey wedge and the chest's black edge cut into the belt). SPLIT: guard bone -> (lowest, highest) height above
# Dash's pelvis, relative to that joint.
SPLIT = {14: (None, 0.0), 13: (0.0, None)}
# the spine mesh (the guard's grey belt) rides on Dash's pelvis, not his spine: Dash's run turns his chest on the spine
# more than the guard's, and the chest's black lower edge slid over the belt (2026-11-06; on the chest it hid it)
UP = {15: ((), ()), 14: ((14,), ()), 13: ((14, 13), (10, 9)), 6: ((14, 13, 6), (10, 9, 2, 1))}  # joint chains
# left out: the guard's right hand mesh (10), its rifle, which hung beside Dash's own blaster (2026-11-06); the spine
# mesh (the grey belt) is kept: from the near variant's chest and pelvis it shows as the guard's thin belt
DROP = (10,)
# the right hand gets the guard's left hand (7) mirrored across its limb (local x: the right arm runs along -x, the left
# along +x, the frames are not mirrored): with no mesh before it in the hand's list the draw cleared w0 bit 0x80 on
# Dash's weapon, which hang.c's hide_weapon picks (2026-11-06)
MIRROR = {10: (7, (-1.0, 1.0, 1.0))}
ROLL = {}                            # guard bone -> degrees about its limb (none: 90 / -90 / 180 on the shoulders, 2026-11-06)
# A limb mesh is a variant group of two: 0 the detailed near one, 1 the far one; the drawn index (+0x14) is whichever
# the last guard drawn left (1 in palace.st). The far one on Dash looked crude ("максимально убого", 2026-11-06) and
# was taken for a turned model: the near one matches the real guard seen from behind by the Creature Cam (helmet with a
# grey band, red back with a dark square), unturned (a 180 turn and a front-to-back mirror were tried, both wrong).
VARIANT = 0
CAP = 15                             # the guard bone whose (first) mesh gets its bottom loop closed: the pelvis (cap_bottom)
TURN = 0.0
DASH_BONES = 19
LITN_BONES = (9, 8, 5, 1)            # Dash bones (trot order) the lightning runs over: the chest, the right and left upper
                                     # arms, the head (MAP: the guard's 13, 12, 9, 6)


def dump_ram(rom):
    out = {}
    e = Emu(rom)

    def script(e, n):
        if n == 60: e.load_state(os.path.join(paths.STATES, 'palace.st'))
        if n == 70:
            raw = ctypes.string_at(e.rdram(), 0x800000)      # host-endian words
            out['ram'] = b''.join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4))
            e.stop()
    e.run(script)
    return out['ram']


def luke_head(path, alloc, xf):
    """The glTF's (luke_head.gltf's) node bone_06 as one mesh node in the image (alloc), its vertices through xf (the guard head's
    transform onto Dash's head bone, local units): [the mesh node's address]."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guri'))
    import gltf, guri_asset as ga
    g = gltf.read(path)
    (n,) = [n for n in g['nodes'] if n['name'] == 'bone_06']
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])
    s16 = lambda v: int(max(-32768, min(32767, round(v))))
    mats = {}
    def material(m):
        if m in mats: return mats[m]
        W, H, pal, tx = ga.texture(g['materials'][m]['png'])
        d = alloc(W32(0xB8000000, 0) + tx + b''.join(struct.pack('>H', q) for q in pal))
        tdl = alloc(ga.tex_dl(W, H, d & 0x00FFFFFF, 8 + len(tx), 8))
        rec = alloc(W32((W * 4) << 16 | H * 4, ga.TEXREC_W1, tdl, d))
        mats[m] = alloc(W32(ga.MAT_FLAGS, 0, rec, ga.MAT_FLAGS)); return mats[m]
    parts, allp, tris = [], [], 0
    for p in g['meshes'][n['mesh']]:
        pos = np.array([xf(v) for v in p['pos']])
        uv = p['uv'] if p['uv'] is not None else np.zeros((len(pos), 2))
        dl = bytearray()
        for vs, ts in ga.batches([tuple(int(v) for v in t) for t in p['idx']]):
            vb = bytearray()
            for v in vs:
                r, gg, bl, al = (int(max(0, min(255, round(c * 255)))) for c in p['col'][v])
                vb += struct.pack('>hhhHhhBBBB', *(s16(c * 8) for c in pos[v]), 0, *(s16(c * 4096) for c in uv[v]),
                                  r, gg, bl, al)
            dl += W32(0x04000000 | len(vs) << 9 | (16 * len(vs) - 1), alloc(bytes(vb)))
            for t3 in ts: dl += W32(0xBF000000, 0x02000000 | (t3[0] * 5) << 16 | (t3[1] * 5) << 8 | t3[2] * 5)
            tris += len(ts)
        dl += W32(0xB8000000, 0)
        gdl = alloc(bytes(dl))
        parts.append(alloc(struct.pack('>6f', *pos.min(0), *pos.max(0)) +
                           W32(ga.PART_W18, 0, 0, material(p['material']), gdl)))
        allp.append(pos)
    allp = np.vstack(allp) * 8; lo, hi = allp.min(0), allp.max(0)
    bb = b''.join(struct.pack('>hhhH8x', s16((lo, hi)[x][0]), s16((lo, hi)[y][1]), s16((lo, hi)[z][2]), 0)
                  for x in (0, 1) for y in (0, 1) for z in (0, 1))
    mesh = alloc(W32(ga.MESH_W0, ga.MESH_W1, 0, len(parts), alloc(W32(*parts)), alloc(bb)))
    print(f'luke: {len(parts)} parts, {tris} triangles, {len(mats)} textures, box {np.round(lo / 8, 2)} .. '
          f'{np.round(hi / 8, 2)} (Dash head bone)')
    return [mesh]


def mesh_box(meshes, get):
    """The union of the meshes' parts' boxes (part +0: min, max floats, local units) in the image."""
    f = lambda a: struct.unpack('>f', struct.pack('>I', get(a)))[0]
    lo, hi = np.full(3, 1e9), np.full(3, -1e9)
    for m in meshes:
        for i in range(get(m + 0x0C)):
            p = get(get(m + 0x10) + 4 * i)
            lo = np.minimum(lo, [f(p + 4 * k) for k in range(3)]); hi = np.maximum(hi, [f(p + 12 + 4 * k) for k in range(3)])
    assert (lo < hi).all(), 'no box'
    return lo, hi


def plain_material(alloc):
    """A material on the white 16 x 16 texture (the colour from the vertex colours, unlit), guri_asset's way."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guri'))
    import guri_asset as ga
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])
    W, H, pal, tx = ga.texture(None)
    d = alloc(W32(0xB8000000, 0) + tx + b''.join(struct.pack('>H', q) for q in pal))
    tdl = alloc(ga.tex_dl(W, H, d & 0x00FFFFFF, 8 + len(tx), 8))
    rec = alloc(W32((W * 4) << 16 | H * 4, ga.TEXREC_W1, tdl, d))
    return alloc(W32(ga.MAT_FLAGS, 0, rec, ga.MAT_FLAGS))


def shared_dl(alloc, pos, col, tri):
    """A geometry DL of triangles tri over vertices pos (local units), colours col (0..1): each vertex packed to its
    16-byte record first and equal records made one (the models store a vertex per triangle corner), then batched over
    those (guri_asset.batches, <= 16 a load), the triangles in their order."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guri'))
    import guri_asset as ga
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])
    s16 = lambda v: int(max(-32768, min(32767, round(v))))
    recs = [struct.pack('>hhhHhhBBBB', *(s16(c * 8) for c in pos[v]), 0, 0, 0,
                        *(int(max(0, min(255, round(c * 255)))) for c in col[v])) for v in range(len(pos))]
    ids = {}
    vid = [ids.setdefault(r, len(ids)) for r in recs]
    uniq = list(ids)
    dl = bytearray()
    for vs, ts in ga.batches([tuple(vid[int(v)] for v in t) for t in tri]):
        dl += W32(0x04000000 | len(vs) << 9 | (16 * len(vs) - 1), alloc(b''.join(uniq[v] for v in vs)))
        for t3 in ts: dl += W32(0xBF000000, 0x02000000 | (t3[0] * 5) << 16 | (t3[1] * 5) << 8 | t3[2] * 5)
    return dl + W32(0xB8000000, 0)


def plain_mesh(alloc, mat, pos, col, tri):
    """One mesh node of one part (material mat), vertices pos (local units), colours col (0..1), triangles tri."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guri'))
    import guri_asset as ga
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])
    s16 = lambda v: int(max(-32768, min(32767, round(v))))
    dl = shared_dl(alloc, pos, col, tri)
    part = alloc(struct.pack('>6f', *pos.min(0), *pos.max(0)) + W32(ga.PART_W18, 0, 0, mat, alloc(bytes(dl))))
    lo, hi = pos.min(0) * 8, pos.max(0) * 8
    bb = b''.join(struct.pack('>hhhH8x', s16((lo, hi)[x][0]), s16((lo, hi)[y][1]), s16((lo, hi)[z][2]), 0)
                  for x in (0, 1) for y in (0, 1) for z in (0, 1))
    return alloc(W32(ga.MESH_W0, ga.MESH_W1, 0, 1, alloc(W32(part)), alloc(bb)))


def glow_material(alloc, a):
    """A material on the game's translucent texture type (2: G_RM_AA_ZB_XLU_SURF; its combine: colour texel x shade,
    alpha the texel's alone, the shade's alpha unused), a white 4 x 4 RGBA32 texture of alpha a (0..255) loaded as
    the game's own type-2 records load theirs (palace.st, record 0x801EC400: the same DL words but the image's place
    and the size: 16 texels, tiles clamped and masked to 4, the record's size word 8 a texel), unlit: the vertex
    colours as they are (the saber's glow). Every texel is the same and the UVs are 0, so 4 x 4 draws as 16 x 16 did."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guri'))
    import guri_asset as ga
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])
    d = alloc(W32(0xB8000000, 0) + bytes([255, 255, 255, a]) * (4 * 4))
    seg = d & 0x00FFFFFF
    tdl = alloc(W32(0xBC001006, seg, 0xBB000001, 0x20002000, 0xFD180000, 0x84000000 | 8, 0xF5180000, 0x07088220,
                    0xE6000000, 0, 0xF3000000, 0x0700F400, 0xE7000000, 0, 0xF5180200, 0x00088220,
                    0xF2000000, 0x0000C00C, 0xB8000000, 0))
    rec = alloc(W32(0x00200020, 0x00020000, tdl, d))
    return alloc(W32(ga.MAT_FLAGS, 0, rec, ga.MAT_FLAGS))


def parts_mesh(alloc, parts, w0=None):
    """One mesh node of several parts [(material, positions (local units), colours 0..1, triangles)]."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guri'))
    import guri_asset as ga
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])
    s16 = lambda v: int(max(-32768, min(32767, round(v))))
    pl, allp = [], []
    for mat, pos, col, tri in parts:
        dl = shared_dl(alloc, pos, col, tri)
        pl.append(alloc(struct.pack('>6f', *pos.min(0), *pos.max(0)) + W32(ga.PART_W18, 0, 0, mat, alloc(bytes(dl)))))
        allp.append(pos)
    P = np.vstack(allp); lo, hi = P.min(0) * 8, P.max(0) * 8
    bb = b''.join(struct.pack('>hhhH8x', s16((lo, hi)[x][0]), s16((lo, hi)[y][1]), s16((lo, hi)[z][2]), 0)
                  for x in (0, 1) for y in (0, 1) for z in (0, 1))
    return alloc(W32(ga.MESH_W0 if w0 is None else w0, ga.MESH_W1, 0, len(pl), alloc(W32(*pl)), alloc(bb)))


def build(E, luke_path=LUKE_GLTF):
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    F = lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]
    ptr = lambda v: 0x80000400 <= v < 0x80800000

    def dl_end(a):
        while R(a) >> 24 != 0xB8: a += 8
        return a + 8

    def records():
        p, out = R(0x80112830), {}
        for i in range(80):
            r = R(p + 4 * i)
            if not r: break
            out[R(r)] = r
        return out

    def block(first, tag):
        x = first
        for i in range(60):
            if not ptr(x): break
            if R(x + 0x1C) == TAG(tag): return x
            x = R(x + 0x14)
        for o in range(0x100000, 0x400000, 4):              # not on the chain: the block by its tag
            a = 0x80000000 + o - 0x1C
            if R(0x80000000 + o) == TAG(tag) and ptr(R(a)) and ptr(R(a + 0x38 + 8)): return a
        raise SystemExit(f'no animation block {tag}: is palace.st sub-level 26?')

    def bones(b):
        nodes, e = [], b + 0x38
        for i in range(40):
            nodes.append(R(e + 8)); n = R(e + 0x0C)
            if not ptr(n): break
            e = n
        return nodes

    rec = records()
    humn, trop = rec.get(TAG('Humn')), rec.get(TAG('Trop'))
    assert humn and trop, 'no Humn / Trop: is palace.st sub-level 26?'
    pool = R(trop + 0x10)
    guard = next((pool + j * 0x120 for j in range(R(trop + 8)) if R(pool + j * 0x120 + 0x74) == 0), None)
    assert guard, 'no kind-0 Trop (the red guard)'
    gn = bones(block(R(guard + 0xCC), 'trSt'))
    dn = bones(block(R(R(humn + 0x10) + 0x19C), 'trot'))
    assert len(gn) == 17 and len(dn) == DASH_BONES, (len(gn), len(dn))
    gset = set(gn)
    t = lambda n: np.array([F(n + 0x38 + 4 * i) for i in range(3)])
    meshes = lambda n: [R(R(n + 0x10) + 4 * i) for i in range(R(n + 0x0C)) if R(R(n + 0x10) + 4 * i) not in gset]

    def turn(u, v):
        u, v = u / np.linalg.norm(u), v / np.linalg.norm(v); c = np.cross(u, v); d = float(u @ v)
        if np.linalg.norm(c) < 1e-9: return np.eye(3)
        K = np.array([[0, -c[2], c[1]], [c[2], 0, -c[0]], [-c[1], c[0], 0]])
        return np.eye(3) + K + K @ K / (1 + d)

    def about(axis, deg):
        a = axis / np.linalg.norm(axis); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
        r = math.radians(deg); return np.eye(3) + math.sin(r) * K + (1 - math.cos(r)) * K @ K

    M, ratio = {}, {}
    for g, (d, gc, dc) in MAP.items():
        if gc is None: continue
        ratio[g] = float(np.linalg.norm(t(dn[dc])) / np.linalg.norm(t(gn[gc])))
    s0 = float(np.median(list(ratio.values())))
    # a limb is scaled by its length ratio along the bone and by the torso ratio across it (scaled alike every way, the
    # thighs, Dash's short ones at 0.24, came out thin and the legs swam between the hips and the knees, 2026-11-06)
    for g, (d, gc, dc) in MAP.items():
        if gc is None: continue
        ug, ud = t(gn[gc]), t(dn[dc]); u = ug / np.linalg.norm(ug)
        S = ratio[g] * np.outer(u, u) + s0 * (np.eye(3) - np.outer(u, u))
        M[g] = about(ud, ROLL.get(g, 0) + TURN) @ turn(ug, ud) @ S
    for g in LEAF: M[g] = M[LEAF[g]]
    X = {g: (lambda m: lambda v: m @ v)(M[g]) for g in M if g not in TORSO}
    H = lambda bs, nodes: sum((t(nodes[i]) for i in bs), np.zeros(3))
    kg = [0.0] + [s0 * H(gc, gn)[2] for gc, _ in KNOTS]; kd = [0.0] + [H(dc, dn)[2] for _, dc in KNOTS]
    kd[-1] = kd[-2] + (kg[-1] - kg[-2])   # the head as high over the shoulders as on the guard: Dash's neck is short, and
                                          # on it the shoulder pads came up beside the helmet (2026-11-06)
    def zmap(z):
        if z <= kg[0]: return z - kg[0] + kd[0]
        for i in range(1, len(kg)):
            if z <= kg[i]: return kd[i - 1] + (z - kg[i - 1]) * (kd[i] - kd[i - 1]) / (kg[i] - kg[i - 1])
        return z - kg[-1] + kd[-1]
    for g in TORSO:
        pg, pd = s0 * H(UP[g][0], gn), H(UP[g][1], dn)
        rz = about(np.array([0.0, 0.0, 1.0]), TURN)
        lo, hi = SPLIT.get(g, (None, None))
        lo = None if lo is None else kd[2] + lo; hi = None if hi is None else kd[2] + hi
        def f(v, pg=pg, pd=pd, rz=rz, lo=lo, hi=hi):
            w = s0 * (rz @ v) + pg; z = zmap(w[2])
            z = z if lo is None else max(z, lo); z = z if hi is None else min(z, hi)
            return np.array([w[0] - pd[0], w[1] - pd[1], z - pd[2]])
        X[g] = f
    print('torso knots guard', [round(x, 2) for x in kg], 'dash', [round(x, 2) for x in kd])
    print('limb ratios', {g: round(r, 3) for g, r in ratio.items()}, 'torso', round(s0, 3))

    # the meshes: a variant group gives the variant its +0x14 picks
    def plain(m):
        if R(m) >> 28 == 5:
            i = VARIANT; assert i < R(m + 0x0C), hex(m)
            return R(R(m + 0x10) + 4 * i)
        assert R(m) >> 28 == 3, hex(m)
        return m
    per_bone = {g: [plain(m) for m in meshes(gn[g])] if g not in DROP else [] for g in MAP}
    for g, (src, k) in MIRROR.items():
        per_bone[g] = per_bone[src] if g in DROP else per_bone[g]
        X[g] = (lambda m, k: lambda v: m @ (np.array(k) * v))(M[g], k)
    flip = {g for g in MIRROR if np.prod(MIRROR[g][1]) < 0}
    parts = lambda m: [R(R(m + 0x10) + 4 * i) for i in range(R(m + 0x0C))]

    # the texture block: every record's data (+0xC) and DL (+8), and the segment-4 DLs those call; what they reach
    # (the DLs, each load's texels and palettes) and every address in them, with the segment base it goes through
    texrecs = sorted({R(R(p + 0x24) + 8) for ms in per_bone.values() for m in ms for p in parts(m)})
    lo, hi, tdls, reach, refs = [], [], set(), [], {}   # refs: DL word -> (target, the base's BC word or None)

    def walk_tex(a, seg4, base_at):
        tdls.add(a); lo.append(a); hi.append(dl_end(a)); reach.append((a, dl_end(a)))
        timg = None
        while R(a) >> 24 != 0xB8:
            w0, w1 = R(a), R(a + 4); op = w0 >> 24
            if w0 == 0xBC001006: seg4, base_at = w1, a
            if op in (0x06, 0xFD):
                if ptr(w1): tgt, via = w1, None
                else:
                    assert (w1 >> 24) & 0x0F == 0x04 and seg4 is not None, f'texture DL address {w1:#x} at {a:#x}'
                    tgt, via = ((seg4 + (w1 & 0x00FFFFFF)) & 0x7FFFFF) | 0x80000000, base_at   # segment 4: base + offset
                refs[a] = (tgt, via)
                if op == 0x06: walk_tex(tgt, seg4, base_at)
                else: timg = (tgt, (w0 >> 19) & 3)
            assert op != 0xF4, f'load tile at {a:#x}'
            if op == 0xF0: reach.append((timg[0], timg[0] + 2 * (((w1 >> 14) & 0x3FF) + 1)))        # palette
            if op == 0xF3: reach.append((timg[0], timg[0] + ((((w1 >> 12) & 0xFFF) + 1) << timg[1] >> 1)))  # texels
            a += 8
    for r in texrecs:
        lo.append(R(r + 0xC)); reach.append((R(r + 0xC), R(r + 0xC) + 8))   # the data's 8-byte head: the record's
        walk_tex(R(r + 8), None, None)                                       # pointer lands there
    T = (min(lo), max(hi))
    assert T[1] - T[0] <= TEX_MAX, f'texture span {T[1] - T[0]:#x} over {TEX_MAX:#x}'
    # the span copied as regions, split at every run of it nothing reaches of GAP_MIN or more (other palace characters'
    # textures between the guard's), the run's ends rounded inward to 16 so each region keeps its offset mod 16
    cover = np.zeros(T[1] - T[0], bool)
    for a, b in reach: cover[max(a, T[0]) - T[0]:min(b, T[1]) - T[0]] = True
    regions, start, i = [], T[0], 0
    while i < len(cover):
        if cover[i]: i += 1; continue
        j = i
        while j < len(cover) and not cover[j]: j += 1
        g0, g1 = (T[0] + i + 15) & ~15, (T[0] + j) & ~15
        if j - i >= GAP_MIN and g1 > g0: regions.append((start, g0)); start = g1
        i = j
    regions.append((start, T[1]))

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'luke'))
    import lightning_model
    img = bytearray(8 + 8 * DASH_BONES + 12 + 12 + 4 * (1 + lightning_model.VARIANTS) * len(LITN_BONES) + 24 + 8)   # + 'LUKE', 'LITN', 'SABR', 'FACE'
    img += bytes(-len(img) % 16)
    put = lambda a, v: struct.pack_into('>I', img, a - BASE, v & 0xFFFFFFFF)
    get = lambda a: struct.unpack_from('>I', img, a - BASE)[0]

    def alloc(b):
        a = BASE + len(img); img.extend(b); img.extend(bytes(-len(img) % 16)); return a

    deltas = []
    for r0, r1 in regions:
        a0 = r0 & ~15; deltas.append((r0, r1, alloc(E[a0 & 0x7FFFFF:r1 & 0x7FFFFF]) - a0))
    def dT(a):
        (d,) = [d for r0, r1, d in deltas if r0 <= a < r1] or [None]
        assert d is not None, f'{a:#x} in no texture region'
        return d
    # every address moves by its region's delta (falcon_asset.py's relocation, per region): an absolute one by its
    # target's, a segment base by the region its references land in (all of them in one); no reference changes form
    base_d = {}
    for a, (tgt, via) in refs.items():
        if via is None: put(a + dT(a) + 4, R(a + 4) + dT(tgt))
        else: base_d.setdefault(via, set()).add(dT(tgt))
    for via, ds in base_d.items():
        assert len(ds) == 1, f'the segment base at {via:#x} reaches {len(ds)} regions'
        put(via + dT(via) + 4, R(via + 4) + ds.pop())
    newrec, newmat = {}, {}
    for r in texrecs:
        b = bytearray(E[r & 0x7FFFFF:(r & 0x7FFFFF) + 16])
        struct.pack_into('>II', b, 8, R(r + 8) + dT(R(r + 8)), R(r + 0xC) + dT(R(r + 0xC)))
        newrec[r] = alloc(b)

    s16 = lambda v: max(-32768, min(32767, int(round(v))))

    def vtx(a, n, xf):
        b = bytearray(E[a & 0x7FFFFF:(a & 0x7FFFFF) + 16 * n])
        for i in range(n):
            x = np.array(struct.unpack_from('>hhh', b, 16 * i), float)
            struct.pack_into('>hhh', b, 16 * i, *map(s16, 8 * xf(x / 8)))      # vertices in 1/8 units
        return alloc(b)

    def geo(g, xf, rev=False, cap=False):
        b = bytearray(E[g & 0x7FFFFF:dl_end(g) & 0x7FFFFF])
        for o in range(0, len(b), 8):
            w0, w1 = struct.unpack_from('>II', b, o)
            assert w0 >> 24 != 0x06, f'call in a geometry DL at {g + o:#x}'
            if w0 >> 24 == 0x04: struct.pack_into('>I', b, o + 4, vtx(w1, (w0 & 0xFFFF) >> 9, xf))
            if rev and w0 >> 24 == 0xBF: b[o + 6], b[o + 7] = b[o + 7], b[o + 6]     # a mirror turns the winding
            if rev and w0 >> 24 == 0xB5: b[o + 5:o + 8] = bytes(reversed(b[o + 5:o + 8]))
        if cap: b = cap_bottom(b)
        return alloc(b)

    def cap_bottom(b):
        """Close the baked DL's lowest open loop (4 vertices) with a quad, wound against its neighbours (outward).
        The guard's own pelvis mesh is a tube open at the bottom; on the guard its thighs meet under it and hide the slit,
        but on Dash's bones the thighs sit apart, and lying face down seen from the feet the view ran up the slit to the
        inside of the body and the head's face (2026-11-09)."""
        slot, tris, flag, recs = {}, [], None, {}    # slot -> (key: the baked s16 position, its 16-byte record)
        for o in range(0, len(b) - 8, 8):
            w0, w1 = struct.unpack_from('>II', b, o)
            if w0 >> 24 == 0x04:
                for j in range((w0 & 0xFFFF) >> 9):
                    rec = bytes(img[w1 - BASE + 16 * j:w1 - BASE + 16 * j + 16]); slot[j] = (rec[:6], rec); recs[rec[:6]] = rec
            elif w0 >> 24 in (0xBF, 0xB5):
                ix = [(w1 >> sh & 0xFF) // 5 for sh in ((16, 8, 0) if w0 >> 24 == 0xBF else (24, 16, 8, 0))]
                if w0 >> 24 == 0xBF and flag is None: flag = w1 >> 24
                for t3 in ([ix] if w0 >> 24 == 0xBF else [ix[:3], [ix[0], ix[2], ix[3]]]):
                    tris.append([slot[j][0] for j in t3])
        cnt, direct = {}, {}
        for t3 in tris:
            for i in range(3):
                a, c = t3[i], t3[(i + 1) % 3]
                k = (min(a, c), max(a, c)); cnt[k] = cnt.get(k, 0) + 1; direct[(a, c)] = 1
        nxt = {}                                     # open edges, each walked against its triangle: a -> c
        for (a, c) in direct:
            if cnt[(min(a, c), max(a, c))] == 1: nxt[c] = a
        loops, seen = [], set()
        for a in nxt:
            if a in seen: continue
            lp = [a]; seen.add(a)
            while nxt.get(lp[-1]) not in (None, a) and len(lp) < 64: lp.append(nxt[lp[-1]]); seen.add(lp[-1])
            loops.append(lp)
        z = lambda k: struct.unpack('>hhh', k)[2]
        low = min(loops, key=lambda lp: sum(map(z, lp)) / len(lp))
        assert len(low) == 4, f'the pelvis bottom loop has {len(low)} vertices'
        pos = {k: j for j, (k, _) in slot.items()}
        if all(k in pos for k in low): ix, load = [pos[k] for k in low], b''
        else:                                        # not all in the last load: one small load of the four
            ix = [0, 1, 2, 3]
            load = struct.pack('>II', 0x04000000 | 4 << 9 | (16 * 4 - 1), alloc(b''.join(recs[k] for k in low)))
        fl = (flag or 0) << 24
        tri = lambda p, q, r: struct.pack('>II', 0xBF000000, fl | (ix[p] * 5) << 16 | (ix[q] * 5) << 8 | ix[r] * 5)
        P = [np.array(struct.unpack('>hhh', k), float) for k in low]
        print('pelvis cap: loop', [struct.unpack('>hhh', k) for k in low], 'slots', ix, 'own load' if load else '',
              'normal', np.round(np.cross(P[1] - P[0], P[2] - P[0]), 0))
        return b[:-8] + load + tri(0, 1, 2) + tri(0, 2, 3) + b[-8:]

    def box(lo3, hi3, xf):
        cs = [xf(np.array([x, y, z])) for x in (lo3[0], hi3[0]) for y in (lo3[1], hi3[1]) for z in (lo3[2], hi3[2])]
        return [min(c[i] for c in cs) for i in range(3)] + [max(c[i] for c in cs) for i in range(3)]

    def mesh(mn, xf, rev=False, cap=False):
        newparts = []
        assert not cap or len(parts(mn)) == 1, 'the pelvis mesh is one sub-mesh'
        for p in parts(mn):
            mt = R(p + 0x24)
            if mt not in newmat:
                b = bytearray(E[mt & 0x7FFFFF:(mt & 0x7FFFFF) + 16]); struct.pack_into('>I', b, 8, newrec[R(mt + 8)])
                newmat[mt] = alloc(b)
            b = bytearray(E[p & 0x7FFFFF:(p & 0x7FFFFF) + 0x2C])
            struct.pack_into('>6f', b, 0, *box(struct.unpack_from('>3f', b, 0), struct.unpack_from('>3f', b, 12), xf))
            struct.pack_into('>II', b, 0x24, newmat[mt], geo(R(p + 0x28), xf, rev, cap))
            newparts.append(alloc(b))
        lst = alloc(b''.join(struct.pack('>I', x) for x in newparts))
        bb = bytearray(E[R(mn + 0x14) & 0x7FFFFF:(R(mn + 0x14) & 0x7FFFFF) + 0x80])
        for o in range(0, 0x80, 16):
            bb[o:o + 6] = struct.pack('>hhh', *map(s16, 8 * xf(np.array(struct.unpack_from('>hhh', bb, o), float) / 8)))
        hdr = struct.pack('>6I', R(mn), R(mn + 4), 0, len(newparts), lst, alloc(bb))
        return alloc(hdr)

    struct.pack_into('>4sI', img, 0, b'GARD', DASH_BONES)
    lists = {}                                      # per Dash bone: the pelvis and the belt both ride on 17 (one slot
    for g, (d, _, _) in MAP.items():               # written per guard bone lost the pelvis, a hole for a seat, 2026-11-06)
        lists.setdefault(d, []).extend(mesh(mn, X[g], g in flip, g == CAP and k == 0) for k, mn in enumerate(per_bone[g]))
    for d, ms in lists.items():
        struct.pack_into('>II', img, 8 + 8 * d, len(ms), alloc(b''.join(struct.pack('>I', x) for x in ms)))
    luke = luke_head(luke_path, alloc, X[6]) if luke_path and os.path.exists(luke_path) else []
    struct.pack_into('>4sII', img, 8 + 8 * DASH_BONES, b'LUKE', len(luke),
                     alloc(b''.join(struct.pack('>I', x) for x in luke)) if luke else 0)
    litn_at = 8 + 8 * DASH_BONES + 12
    struct.pack_into('>4sII', img, litn_at, b'LITN', lightning_model.VARIANTS, len(LITN_BONES))
    white = None
    for j, d in enumerate(LITN_BONES):
        lo, hi = mesh_box(luke if d == 1 and luke else lists.get(d, []), get)
        if white is None: white = plain_material(alloc)
        ms = [plain_mesh(alloc, white, *v) for v in lightning_model.variants(lo, hi, j)]
        struct.pack_into(f'>{1 + len(ms)}I', img, litn_at + 12 + 4 * (1 + lightning_model.VARIANTS) * j, d, *ms)
        print(f'lightning on bone {d}: box {np.round(lo, 2)} .. {np.round(hi, 2)}, {len(ms)} variants')
    import saber_model
    sabr_at = litn_at + 12 + 4 * (1 + lightning_model.VARIANTS) * len(LITN_BONES)
    glows = {}                                          # one translucent texture per shell alpha (its combine takes
    sp = saber_model.parts()                            # the alpha from the texel alone)
    for k, p, c, t in sp:
        if k[0] == 'glow' and k[1] not in glows: glows[k[1]] = glow_material(alloc, k[1])
    mat = lambda k: glows[k[1]] if k[0] == 'glow' else white
    blade = parts_mesh(alloc, [(white, p, c, t) for k, p, c, t in sp if k == 'opaque'],
                       w0=0x3064FFC0)                   # the blaster's w0 (bit 0x80: hang.c's hide_weapon picks it)
    late = parts_mesh(alloc, [(mat(k), p, c, t) for k, p, c, t in sp if k != 'opaque'],
                      w0=0x3064FF40)                    # the shells and the core: saber.c draws it after the level
    import saber_moves
    moves, mask = saber_moves.build(saber_moves.BE(E))
    swng = saber_moves.pack(moves, mask, alloc)
    import saber_icon
    icon = alloc(bytes(0x730))
    img[icon - BASE:icon - BASE + 0x730] = saber_icon.record(E, icon)
    arm = saber_moves.arm_build(saber_moves.BE(E))
    sarm = saber_moves.pack_arm(arm, alloc, saber_moves.parry_layers(saber_moves.BE(E)))
    struct.pack_into('>4sIIIII', img, sabr_at, b'SABR', 2, alloc(struct.pack('>II', blade, late)), swng, icon, sarm)
    print(f'saber: hilt {blade:#x}, blade {late:#x}, swings {swng:#x}, HUD icon {icon:#x}, arm {sarm:#x} '
          f'({", ".join(f"{t} {n}" for t, n, _ in arm)} keys)')
    import luke_portrait                                # Luke's HUD portrait (guard.c face(): the Look on Luke)
    face = 0
    if os.path.exists(luke_portrait.CUT13_BIN):
        face = alloc(bytes(luke_portrait.SIZE))
        img[face - BASE:face - BASE + luke_portrait.SIZE] = luke_portrait.record(E, luke_portrait.load(luke_portrait.CUT13_BIN), face)
    struct.pack_into('>4sI', img, sabr_at + 24, b'FACE', face)
    print(f'portrait: {face:#x}' if face else f'portrait: none ({luke_portrait.CUT13_BIN} missing)')
    assert BASE + len(img) <= LIMIT, f'image {len(img):#x} past {LIMIT:#x}'
    tb = sum(r1 - (r0 & ~15) for r0, r1 in regions)
    print(f'guard: {sum(len(v) for v in per_bone.values())} meshes, texture block {tb} bytes in {len(regions)} '
          f'regions (span {T[1] - T[0]}, reached {int(cover.sum())}), image {len(img)} bytes at {BASE:#x}')
    return bytes(img)


def sections(img):
    """The image's content without its layout, for --same: [(section name, value)]; per mesh of GARD, LUKE, LITN and
    SABR every part's header words and box, its material's words but the record pointer, the texels each palette and
    texel load of its record's DL reaches (a load whose texels are all one RGBA32 texel: that texel alone, its alpha
    in it), its triangles as triples of 16-byte vertex records; the swings' table, the HUD icon, the arm's table and
    the portrait as their bytes, a word that points into the image taken relative to the section's own start."""
    get = lambda a: struct.unpack_from('>I', img, a - BASE)[0]
    inside = lambda a: BASE <= a < BASE + len(img)
    by = lambda a, n: bytes(img[a - BASE:a - BASE + n])

    def loads(dl):
        raw, timg, tile, size = [], [None], {}, {}      # tile: idx -> (tmem bytes, line bytes, siz); size: idx -> rows
        def walk(a, seg4):
            while get(a) >> 24 != 0xB8:
                w0, w1 = get(a), get(a + 4); op = w0 >> 24
                if w0 == 0xBC001006: seg4 = w1
                if op in (0x06, 0xFD):
                    tgt = w1 if inside(w1) else ((seg4 + (w1 & 0x00FFFFFF)) & 0x7FFFFF) | 0x80000000
                    if op == 0x06: walk(tgt, seg4)
                    else: timg[0] = (tgt, (w0 >> 19) & 3)
                if op == 0xF5: tile[(w1 >> 24) & 7] = ((w0 & 0x1FF) * 8, ((w0 >> 9) & 0x1FF) * 8, (w0 >> 19) & 3)
                if op == 0xF2: size[(w1 >> 24) & 7] = ((w1 & 0xFFF) >> 2) - ((w0 & 0xFFF) >> 2) + 1
                if op == 0xF0: raw.append((op, timg[0][0], 2 * (((w1 >> 14) & 0x3FF) + 1), timg[0][1]))
                if op == 0xF3: raw.append((op, timg[0][0], (((w1 >> 12) & 0xFFF) + 1) << timg[0][1] >> 1, timg[0][1]))
                a += 8
        walk(dl, None)
        # a texel load block counts up to the last byte a drawing tile reads from TMEM (32-bit tiles: both halves): the
        # game's own loads read past their texture (the belt's 1522 bytes for tiles that read 760), over whatever follows
        used = max([t[0] + t[1] * size.get(i, 0) * (2 if t[2] == 3 else 1) - tile.get(7, (0,))[0]
                    for i, t in tile.items() if i != 7] or [1 << 30])
        out = []
        for op, a, n, siz in raw:
            if op == 0xF3: n = min(n, used)
            b = by(a, n)
            out.append(('one texel', b[:4]) if siz == 3 and b == b[:4] * (n // 4) else (hex(op), b))
        return out

    def tris(dl):
        out, slot = [], {}
        while get(dl) >> 24 != 0xB8:
            w0, w1 = get(dl), get(dl + 4); op = w0 >> 24
            if op == 0x04:
                v0 = (w0 >> 16) & 0xFF
                for j in range((w0 & 0xFFFF) >> 9): slot[v0 // 2 + j] = by(w1 + 16 * j, 16)
            elif op in (0xBF, 0xB5):
                ix = [(w1 >> sh & 0xFF) // 5 for sh in ((16, 8, 0) if op == 0xBF else (24, 16, 8, 0))]
                for t3 in ([ix] if op == 0xBF else [ix[:3], [ix[0], ix[2], ix[3]]]): out.append(tuple(slot[j] for j in t3))
            else: out.append(('cmd', w0, w1))
            dl += 8
        return out

    def mesh(m):
        ps = []
        for i in range(get(m + 0x0C)):
            p = get(get(m + 0x10) + 4 * i); mt = get(p + 0x24)
            ps.append((by(p, 0x24), (get(mt), get(mt + 4), get(mt + 0xC)), loads(get(get(mt + 8) + 8)), tris(get(p + 0x28))))
        return (get(m), get(m + 4), by(get(m + 0x14), 0x80), ps)

    def rel(a, n):
        return [w - a if inside(w) else w for w in struct.unpack_from(f'>{n // 4}I', img, a - BASE)]

    out = []
    tag, nb = struct.unpack_from('>4sI', img, 0)
    assert tag == b'GARD', tag
    for d in range(nb):
        n, lst = struct.unpack_from('>II', img, 8 + 8 * d)
        out.append((f'GARD bone {d:2d} ({n} meshes)', [mesh(get(lst + 4 * k)) for k in range(n)]))
    at = 8 + 8 * nb
    tag, n, lst = struct.unpack_from('>4sII', img, at); assert tag == b'LUKE', tag
    out.append((f'LUKE ({n} meshes)', [mesh(get(lst + 4 * k)) for k in range(n)]))
    at += 12
    tag, nv, npart = struct.unpack_from('>4sII', img, at); assert tag == b'LITN', tag
    for j in range(npart):
        w = struct.unpack_from(f'>{1 + nv}I', img, at + 12 + 4 * (1 + nv) * j)
        out.append((f'LITN part {j} (bone {w[0]}, {nv} variants)', [w[0]] + [mesh(m) for m in w[1:]]))
    at += 12 + 4 * (1 + nv) * npart
    tag, n, lst, swng, icon, sarm = struct.unpack_from('>4sIIIII', img, at); assert tag == b'SABR' and n == 2, tag
    hilt, late = get(lst), get(lst + 4)
    out += [('SABR hilt', mesh(hilt)), ('SABR blade', mesh(late))]
    tag, face = struct.unpack_from('>4sI', img, at + 24); assert tag == b'FACE', tag
    s0 = late + 32                                      # the blade's node (24 bytes) is its mesh's last allocation
    assert s0 <= swng < icon <= sarm, (hex(s0), hex(swng), hex(icon), hex(sarm))
    out.append(('SWN2', rel(s0, icon - s0)))
    out.append(('HUD icon', rel(icon, 0x730)))
    assert sarm < lst                                   # the SABR list: allocated after the arm's table
    out.append(('SAR2 + PRY3', rel(icon + 0x730, lst - icon - 0x730)))
    if face:
        import luke_portrait
        out.append(('FACE', rel(face, luke_portrait.SIZE)))
    return out


def same(old, new):
    """--same: one line per section, PASS / FAIL; exit 1 on a FAIL."""
    a, b = sections(open(old, 'rb').read()), sections(open(new, 'rb').read())
    assert [n for n, _ in a] == [n for n, _ in b], 'the images have other sections'
    bad = 0
    for (n, x), (_, y) in zip(a, b):
        ok = x == y; bad += not ok
        glow = ' (glow by texel 0 and alpha)' if 'one texel' in repr(x) else ''
        print(f'{"PASS" if ok else "FAIL"}  {n}{glow}')
    print(f'{os.path.getsize(old)} -> {os.path.getsize(new)} bytes; {len(a) - bad} PASS, {bad} FAIL')
    return 1 if bad else 0


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--same':
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'luke'))
        sys.exit(same(sys.argv[2], sys.argv[3]))
    if len(sys.argv) < 2: sys.exit(__doc__)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(paths.GAME, 'guard.bin')
    img = build(dump_ram(sys.argv[1]))
    open(out, 'wb').write(img)
    print('wrote', out)
