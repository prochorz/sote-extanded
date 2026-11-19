"""Convert the Guri model (guri.gltf, made by guri_model.py or exported back from Blender) into the game's mesh
structures: local/game/guri.bin, loaded at BASE (feature `guri`, sote-patch/src/guri.c).

    M64CPU=0 python3 guri/guri_asset.py <rom> [in.gltf] [out.bin]   (defaults guri/guri.gltf, local/game/guri.bin)
    GURI_RAM=<file>   a palace.st RAM dump instead of the emulator run (guri_model.py's)

The glTF's skeleton must be the palace guard's (Trop 0's `trSt` block, read from palace.st) with her shoulders
(guri_model.her_skeleton): one node `bone_NN` per bone, translation = the bone node's +0x38 (within 0.01; the upper
arms 12, 9 moved in by guri_moves_trop.GURI_SHOULDER_IN, the thighs 5, 2 out by GURI_HIP_OUT), no rotation or scale; a bone's meshes are in its local frame
(a mesh node under a bone has its TRS baked into the vertices). Units: local units; vertices are stored x 8 (the
game's vertex units).

Formats (the guard's, palace.st): a mesh node 0x18 {w0 0x3064FF00 (a plain mesh), 0xC, 0 (the wrapper DL the draw
builds), part count, part list, box: 8 F3D vertices}; a part 0x2C {min, max (floats, local units), 0x00030005, 0, 0,
material, geometry DL}; a material {0xC, 0, texture record, 0xC} (unlit: the shade is in the vertex colours); a
texture record {(W*4) << 16 | H*4, 0x00060000, texture DL, data (an 8-byte header, the texels, the palette)}. The
texture DL is the guard's: segment 4 set to the block (BC001006), the texture scale (BB000001, W*512 / H*512), a
16-entry RGBA5551 palette (TLUT) and CI4 texels loaded as 16-bit (LOADBLOCK), the render tile CI4 (line W/16) and its
size. Vertex s, t = u, v * 4096 (with that scale: 1.0 = the texture's width / height). Geometry DLs: G_VTX
0x04 00 (n << 9 | 16n - 1) from slot 0, n <= 16; a triangle 0xBF, w1 0x02 then the three indices x 5; end 0xB8.
A material with a texture: CI4 W x H (powers of two, <= 16 colours); without one: a 16 x 16 white texture (CI4's
line is at least one 8-byte TMEM word: 16 texels), the colour from the vertex colours.

Layout at BASE: header {'GURI', 17, per bone (trSt order) 0..16: mesh count, mesh list}, then the lists, mesh nodes
and their boxes, parts, materials, texture records, texture DLs, texture data, geometry DLs + vertices; then Dash's
blaster (blaster()), the last entry of her right hand's list (bone HAND): guri.c hides it by that list's count.

The blaster: the game's own mesh BLASTER (palace.st's RAM, the same dump) copied with its vertices (and its boxes)
x BLASTER_SCALE, no turn, no offset: in the hand bone's frame that puts it in her fist, barrel forward (stills of a
moved copy listed straight in her hand node, 2026-11-10; a placement node of ours under a Trop's bone draws but its
matrix is ignored). Its texture records' blocks (the data and its texture DL, segment 4 relative inside) are copied
whole, the segment base moved with them; its parts and materials keep the game's words.
"""
import io, math, os, struct, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import gltf, paths
from guri_model import BONES, dump_ram, guard_skeleton, her_skeleton

BASE = 0x80580000
LIMIT = 0x80600000                    # the Gall Run's code starts there
MAX = 0x20000                         # melee.bin starts at 0x805A0000 (build.py MELEE_VRAM)
MAGIC = b'GURI'
MESH_W0, MESH_W1 = 0x3064FF00, 0x0000000C
PART_W18 = 0x00030005                 # as the guard's parts (+0x18; meaning unknown)
MAT_FLAGS = 0xC                       # unlit
TEXREC_W1 = 0x00060000                # as the guard's CI4 records
VTX_MAX = 16
HAND = 10                             # her right hand (trSt 10, tree node 8): the blaster's bone
BLASTER = 0x801FAA60                  # Dash's blaster mesh on palace.st (w0 0x3064FFC0, 2 parts)
BLASTER_W0 = 0x3064FFC0
BLASTER_SCALE = 3.4                   # its size in her fist (x3.4 of the game's)
GEO_CMDS = (0x04, 0xBF, 0xB5, 0xBE)   # G_VTX, a triangle, a quad (two triangles), a cull test


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def trs(n):
    M = np.eye(4)
    if n.get('matrix'): return np.array(n['matrix']).reshape(4, 4).T
    S = np.diag(n['scale']) if n.get('scale') else np.eye(3)
    Rm = quat_mat(n['rotation']) if n.get('rotation') else np.eye(3)
    M[:3, :3] = Rm @ S
    if n.get('translation'): M[:3, 3] = n['translation']
    return M


def texture(png, W=None, H=None):
    """(W, H, palette 16 x u16, texels CI4 bytes) of a PNG (<= 16 colours, else quantized), or the plain white one."""
    if png is None:
        W = H = 16
        return W, H, [0xFFFF] + [0] * 15, bytes(W * H // 2)
    im = Image.open(io.BytesIO(png)).convert('RGB'); W, H = im.size
    assert W in (16, 32, 64) and H in (16, 32, 64) and W * H <= 4096, f'texture {W}x{H}'
    cols = im.getcolors(16)
    if cols is None: im = im.quantize(16).convert('RGB'); cols = im.getcolors(16)
    pal = [c for _, c in sorted(cols, key=lambda c: -c[0])]
    ix = {c: i for i, c in enumerate(pal)}
    px = list(im.getdata()) if not hasattr(im, 'get_flattened_data') else list(im.get_flattened_data())
    t = bytearray(W * H // 2)
    for i in range(0, W * H, 2): t[i // 2] = ix[px[i]] << 4 | ix[px[i + 1]]
    p16 = [(r >> 3) << 11 | (g >> 3) << 6 | (b >> 3) << 1 | 1 for r, g, b in pal] + [0] * (16 - len(pal))
    return W, H, p16, bytes(t)


def tex_dl(W, H, seg_base, pal_off, tex_off):
    lg = lambda v: int(math.log2(v))
    mask = lg(H) << 14 | lg(W) << 4
    words = [(0xBC001006, seg_base), (0xBB000001, (W * 512) << 16 | (H * 512)),
             (0xFD100000, 0x84000000 | pal_off), (0xE8000000, 0), (0xF5000100, 0x07000000), (0xE6000000, 0),
             (0xF0000000, 0x0703C000), (0xE7000000, 0),
             (0xFD500000, 0x84000000 | tex_off), (0xF5500000, 0x07000000 | mask), (0xE6000000, 0),
             (0xF3000000, 0x07000000 | (W * H // 4 - 1) << 12 | (2048 + W // 16 - 1) // (W // 16)), (0xE7000000, 0),
             (0xF5400000 | (W // 16) << 9, mask), (0xF2000000, ((W - 1) << 2) << 12 | (H - 1) << 2), (0xB8000000, 0)]
    return b''.join(struct.pack('>II', a, b) for a, b in words)


def collect(g, T):
    """Per bone: [(positions (N,3), colours (N,4), uvs (N,2), triangles (M,3), material)] in the bone's frame."""
    names = {n['name']: i for i, n in enumerate(g['nodes'])}
    bone = {}
    for i in range(BONES):
        k = names.get(f'bone_{i:02d}')
        assert k is not None, f'no node bone_{i:02d}'
        n = g['nodes'][k]; bone[k] = i
        t = np.array(n['translation'] or (0, 0, 0), float)
        assert np.abs(t - T[i]).max() <= 0.01, f'bone_{i:02d} translation {t} is not hers {T[i]}'
        assert n.get('matrix') is None and (n.get('scale') is None or np.allclose(n['scale'], 1)) and \
            (n.get('rotation') is None or np.allclose(n['rotation'], (0, 0, 0, 1))), f'bone_{i:02d} has a rotation / scale'
    out = {i: [] for i in range(BONES)}

    def add(b, k, M):
        n = g['nodes'][k]
        if n['mesh'] is not None:
            for p in g['meshes'][n['mesh']]:
                pos = (M[:3, :3] @ p['pos'].T).T + M[:3, 3]
                idx = p['idx'] if np.linalg.det(M[:3, :3]) > 0 else p['idx'][:, ::-1]
                uv = p['uv'] if p['uv'] is not None else np.zeros((len(pos), 2))
                out[b].append((pos, p['col'], uv, idx, p['material']))
        for c in n['children']:
            if c not in bone: add(b, c, M @ trs(g['nodes'][c]))     # a mesh node under the bone: its TRS baked
    for k, b in bone.items(): add(b, k, np.eye(4))
    return out


def batches(tris):
    """Split triangles into loads of <= 16 vertices: [(vertex ids, [(a, b, c) cache slots])]."""
    out, cur, slot = [], [], {}
    for t in tris:
        new = [v for v in dict.fromkeys(t) if v not in slot]
        if len(slot) + len(new) > VTX_MAX:
            out.append((cur_v, cur)); cur, slot = [], {}
            new = list(dict.fromkeys(t))
        if not slot: cur_v = []
        for v in new: slot[v] = len(cur_v); cur_v.append(v)
        cur.append(tuple(slot[v] for v in t))
    if cur: out.append((cur_v, cur))
    return out


def blaster(E, at, xf=None):
    """Dash's blaster mesh from the RAM dump E, copied to `at` (16-aligned): (bytes, the mesh node's address,
    triangles). Vertices and boxes x BLASTER_SCALE, then through xf (local units -> local units; None: as they are;
    moves_style._barrel passes a collector to read the vertices); every pointer moved into the copy."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])
    s16 = lambda v: int(max(-32768, min(32767, round(v))))
    m = BLASTER
    assert R(m) == BLASTER_W0, f'{m:#x} is not the blaster mesh ({R(m):#x}): is the dump palace.st?'
    out = bytearray()
    def alloc(n):
        a = at + len(out); out.extend(bytes(n + -n % 16)); return a
    def put(a, b): out[a - at:a - at + len(b)] = b
    def dl_len(a):
        n = 0
        while R(a + 8 * n) >> 24 != 0xB8:
            n += 1; assert n < 1000, hex(a)
        return 8 * (n + 1)
    npart = R(m + 0xC); parts = [R(R(m + 0x10) + 4 * q) for q in range(npart)]
    mesh = alloc(0x18); box = alloc(0x80); plist = alloc(4 * npart); pa = [alloc(0x2C) for _ in parts]
    X = (lambda v: np.asarray(v, float) * BLASTER_SCALE) if xf is None else \
        (lambda v: np.asarray(xf(np.asarray(v, float) * BLASTER_SCALE / 8), float) * 8)   # s16 vertex units in and out
    def aabb(pts): P = np.array([X(p) for p in pts]); return P.min(0), P.max(0)
    ob = R(m + 0x14); bb = bytearray()
    corners = [struct.unpack_from('>hhhH', E, (ob + 16 * c) & 0x7FFFFF) for c in range(8)]
    lo8, hi8 = aabb([c[:3] for c in corners])
    for x, y, z, w in corners:   # each corner the new box's low / high on the axes where it was the old box's
        q = [(lo8 if v == min(cc[k] for cc in corners) else hi8)[k] for k, v in enumerate((x, y, z))]
        bb += struct.pack('>hhhH8x', *(s16(v) for v in q), w)
    put(box, bytes(bb))
    put(mesh, W32(R(m), R(m + 4), 0, npart, plist, box))      # +8: the wrapper DL, built by the draw
    put(plist, W32(*pa))
    mats, vtx, tris = {}, {}, 0
    for p, a in zip(parts, pa):
        mt = R(p + 0x24)
        if mt not in mats:
            rec, nm, nr = R(mt + 8), alloc(16), alloc(16)
            tdl, data = R(rec + 8), R(rec + 12)
            end = tdl + dl_len(tdl)
            assert data < tdl and end - data < 0x4000, (hex(data), hex(tdl))
            blk = bytearray(E[data & 0x7FFFFF:end & 0x7FFFFF]); nb = alloc(len(blk)); delta = nb - data
            seg = None
            for k in range(tdl - data, len(blk), 8):          # the texture DL: its segment base moved
                w0, w1 = struct.unpack_from('>II', blk, k)
                if w0 == 0xBC001006: seg = w1; struct.pack_into('>I', blk, k + 4, (w1 + delta) & 0xFFFFFFFF)
                if w0 >> 24 in (0x06, 0xFD):                  # the loads and calls: segment 4, inside the block
                    ph = (seg + (w1 & 0xFFFFFF)) & 0xFFFFFF
                    assert w1 >> 24 == 0x84 and data & 0xFFFFFF <= ph < end & 0xFFFFFF, (hex(w0), hex(w1))
                    if w0 >> 24 == 0x06:                      # the called DL: its loads segment 4 too
                        c = ph - (data & 0xFFFFFF)
                        while (x := struct.unpack_from('>II', blk, c))[0] >> 24 != 0xB8:
                            assert x[0] >> 24 not in (0x06, 0xFD) or x[1] >> 24 == 0x84, hex(x[1]); c += 8
            put(nb, bytes(blk))
            put(nr, W32(R(rec), R(rec + 4), tdl + delta, nb))
            put(nm, W32(R(mt), R(mt + 4), nr, R(mt + 12)))
            mats[mt] = nm
        g0 = R(p + 0x28); n = dl_len(g0); gd = alloc(n); dl = bytearray(E[g0 & 0x7FFFFF:(g0 + n) & 0x7FFFFF])
        for k in range(0, n - 8, 8):
            w0, w1 = struct.unpack_from('>II', dl, k)
            assert w0 >> 24 in GEO_CMDS, f'command {w0:#x} in the blaster geometry DL'
            if w0 >> 24 == 0x04:
                c = (w0 & 0xFFFF) >> 9
                if w1 not in vtx:
                    va = alloc(16 * c); vb = bytearray(E[w1 & 0x7FFFFF:(w1 + 16 * c) & 0x7FFFFF])
                    for i in range(c):
                        xyz = struct.unpack_from('>hhh', vb, 16 * i)
                        struct.pack_into('>hhh', vb, 16 * i, *(s16(v) for v in X(xyz)))
                    put(va, bytes(vb)); vtx[w1] = (va, c)
                assert vtx[w1][1] >= c
                struct.pack_into('>I', dl, k + 4, vtx[w1][0])
            tris += {0xBF: 1, 0xB5: 2}.get(w0 >> 24, 0)
        put(gd, bytes(dl))
        l0, h0 = struct.unpack_from('>3f', E, p & 0x7FFFFF), struct.unpack_from('>3f', E, (p + 12) & 0x7FFFFF)
        lo, hi = aabb([(a * 8, b * 8, c * 8) for a in (l0[0], h0[0]) for b in (l0[1], h0[1]) for c in (l0[2], h0[2])])
        lo, hi = list(lo / 8), list(hi / 8)
        put(a, struct.pack('>6f', *lo, *hi) + W32(*(R(p + 0x18 + 4 * i) for i in range(3)), mats[mt], gd))
    return bytes(out), mesh, tris


def build(g, T, E=None):
    per_bone = collect(g, T)
    s16 = lambda v: int(max(-32768, min(32767, round(v))))
    # textures: one per material (D: one material per texture)
    tex = {}
    for b, ps in per_bone.items():
        for *_, m in ps:
            if m not in tex: tex[m] = texture(g['materials'][m]['png'] if m is not None else None)

    # sizes first, then addresses section by section
    meshes = [(b, ps) for b, ps in per_bone.items() if ps]
    sec, addr = [], {}
    def reserve(key, size, section):
        sec.append((section, key, size))
    reserve('hdr', 8 + 8 * BONES, 0)
    for b, ps in meshes:
        reserve(('blist', b), 4 * (1 + (E is not None and b == HAND)), 1); reserve(('plist', b), 4 * len(ps), 1)
        reserve(('mesh', b), 0x18, 2); reserve(('mbox', b), 0x80, 2)
        for j in range(len(ps)): reserve(('part', b, j), 0x2C, 3)
    for m in tex: reserve(('mat', m), 16, 4)
    for m in tex: reserve(('rec', m), 16, 5)
    for m in tex: reserve(('tdl', m), 16 * 8, 6)
    for m, (W, H, pal, tx) in tex.items(): reserve(('tdata', m), 8 + len(tx) + 32, 7)
    geo = {}
    for b, ps in meshes:
        for j, (pos, col, uv, idx, mat) in enumerate(ps):
            bt = batches([tuple(int(v) for v in t) for t in idx])
            geo[b, j] = bt
            reserve(('gdl', b, j), 8 * (sum(1 + len(ts) for _, ts in bt) + 1), 8)
            for q, (vs, _) in enumerate(bt): reserve(('vtx', b, j, q), 16 * len(vs), 8)
    a = BASE
    for _, key, size in sorted(sec, key=lambda s: s[0]):
        a += -a % 16 if key != 'hdr' else 0
        addr[key] = a; a += size
    a += -a % 16
    gun, gun_mesh, gun_tris = blaster(E, a) if E is not None else (b'', 0, 0)
    assert E is None or per_bone[HAND], 'no hand mesh for the blaster'
    size = a - BASE + len(gun); size += -size % 16
    img = bytearray(size)
    put = lambda at, b: img.__setitem__(slice(at - BASE, at - BASE + len(b)), b)
    W32 = lambda *v: struct.pack(f'>{len(v)}I', *[x & 0xFFFFFFFF for x in v])

    hdr = bytearray(MAGIC + struct.pack('>I', BONES) + bytes(8 * BONES))
    tdata0 = min(addr[('tdata', m)] for m in tex)
    seg_base = tdata0 & 0x00FFFFFF
    for m, (W, H, pal, tx) in tex.items():
        d = addr[('tdata', m)]
        put(d, W32(0xB8000000, 0) + tx + b''.join(struct.pack('>H', p) for p in pal))
        put(addr[('tdl', m)], tex_dl(W, H, seg_base, d + 8 + len(tx) - tdata0, d + 8 - tdata0))
        put(addr[('rec', m)], W32((W * 4) << 16 | H * 4, TEXREC_W1, addr[('tdl', m)], d))
        put(addr[('mat', m)], W32(MAT_FLAGS, 0, addr[('rec', m)], MAT_FLAGS))
    ntris = 0
    for b, ps in meshes:
        gun_here = bool(gun_mesh) and b == HAND
        struct.pack_into('>II', hdr, 8 + 8 * b, 1 + gun_here, addr[('blist', b)])
        put(addr[('blist', b)], W32(addr[('mesh', b)], *([gun_mesh] if gun_here else [])))
        put(addr[('plist', b)], W32(*[addr[('part', b, j)] for j in range(len(ps))]))
        allp = np.vstack([p[0] for p in ps]) * 8
        lo, hi = allp.min(0), allp.max(0)
        bb = b''.join(struct.pack('>hhhH8x', s16((lo, hi)[x][0]), s16((lo, hi)[y][1]), s16((lo, hi)[z][2]), 0)
                      for x in (0, 1) for y in (0, 1) for z in (0, 1))
        put(addr[('mbox', b)], bb)
        put(addr[('mesh', b)], W32(MESH_W0, MESH_W1, 0, len(ps), addr[('plist', b)], addr[('mbox', b)]))
        for j, (pos, col, uv, idx, mat) in enumerate(ps):
            dl = bytearray()
            for q, (vs, ts) in enumerate(geo[b, j]):
                va = addr[('vtx', b, j, q)]; n = len(vs)
                vb = bytearray()
                for v in vs:
                    x, y, z = (s16(c * 8) for c in pos[v])
                    s, t = (s16(c * 4096) for c in uv[v])
                    r, gg, bl, al = (int(max(0, min(255, round(c * 255)))) for c in col[v])
                    vb += struct.pack('>hhhHhhBBBB', x, y, z, 0, s, t, r, gg, bl, al)
                put(va, bytes(vb))
                dl += W32(0x04000000 | n << 9 | (16 * n - 1), va)
                for t3 in ts:
                    dl += W32(0xBF000000, 0x02000000 | (t3[0] * 5) << 16 | (t3[1] * 5) << 8 | t3[2] * 5)
                    ntris += 1
            dl += W32(0xB8000000, 0)
            put(addr[('gdl', b, j)], bytes(dl))
            lo3, hi3 = pos.min(0), pos.max(0)
            put(addr[('part', b, j)], struct.pack('>6f', *lo3, *hi3) +
                W32(PART_W18, 0, 0, addr[('mat', mat)], addr[('gdl', b, j)]))
    put(BASE, bytes(hdr))
    if gun: put(gun_mesh, gun)
    assert len(img) <= MAX and BASE + len(img) <= LIMIT, f'image {len(img):#x}'
    return bytes(img), ntris + gun_tris


def check(img, gltf_tris):
    """The Validate lines: header GURI / 17; every pointer (lists, meshes, parts, materials, texture records, DLs,
    G_VTX, texture data via segment 4) inside the image; every G_VTX n <= 16; triangles = the glTF's + the blaster's;
    <= MAX."""
    end = BASE + len(img)
    R = lambda a: struct.unpack_from('>I', img, a - BASE)[0]
    def inside(a, n=4, what=''):
        assert BASE <= a and a + n <= end, f'{what} {a:#x} outside the image'
    assert img[:4] == MAGIC and R(BASE + 4) == BONES
    tris = ptrs = 0
    for b in range(BONES):
        cnt, lst = R(BASE + 8 + 8 * b), R(BASE + 12 + 8 * b)
        if not cnt: continue
        inside(lst, 4 * cnt, 'bone list')
        for i in range(cnt):
            m = R(lst + 4 * i); inside(m, 0x18, 'mesh'); assert R(m) in (MESH_W0, BLASTER_W0)
            pl = R(m + 0x10); inside(pl, 4 * R(m + 0xC), 'part list'); inside(R(m + 0x14), 0x80, 'mesh box')
            for k in range(R(m + 0xC)):
                p = R(pl + 4 * k); inside(p, 0x2C, 'part')
                mt = R(p + 0x24); inside(mt, 16, 'material')
                rec = R(mt + 8); inside(rec, 16, 'texture record'); inside(R(rec + 0xC), 8, 'texture data')
                a = R(rec + 8); inside(a, 8, 'texture DL'); seg = None
                while R(a) >> 24 != 0xB8:
                    w0, w1 = R(a), R(a + 4)
                    if w0 == 0xBC001006: seg = w1
                    if w0 >> 24 in (0x06, 0xFD):
                        inside(0x80000000 | ((seg + (w1 & 0xFFFFFF)) & 0xFFFFFF), 8, 'texture data (seg 4)')
                    a += 8; inside(a, 8, 'texture DL')
                a = R(p + 0x28); inside(a, 8, 'geometry DL'); n = 0
                while R(a) >> 24 != 0xB8:
                    w0, w1 = R(a), R(a + 4)
                    if w0 >> 24 == 0x04:
                        n = (w0 & 0xFFFF) >> 9; assert n <= VTX_MAX and (w0 & 0x1FF) == 16 * n - 1, hex(w0)
                        inside(w1, 16 * n, 'G_VTX'); ptrs += 1
                    elif w0 >> 24 == 0xBF:
                        assert w1 >> 24 == 2 and all((w1 >> s & 0xFF) % 5 == 0 and (w1 >> s & 0xFF) // 5 < n
                                                     for s in (16, 8, 0)), hex(w1)
                        tris += 1
                    elif w0 >> 24 == 0xB5 and R(m) == BLASTER_W0:   # the game's quad: four indices x 5
                        assert all((w1 >> s & 0xFF) % 5 == 0 and (w1 >> s & 0xFF) // 5 < n for s in (24, 16, 8, 0)), hex(w1)
                        tris += 2
                    elif w0 >> 24 == 0xBE and R(m) == BLASTER_W0: pass
                    else: raise AssertionError(f'command {w0:#x} in a geometry DL')
                    a += 8; inside(a, 8, 'geometry DL')
    assert tris == gltf_tris, (tris, gltf_tris)
    assert len(img) <= MAX
    print(f'check: GURI 17, all pointers inside [{BASE:#x}, {end:#x}), {ptrs} loads of <= 16, {tris} triangles '
          f'(glTF {gltf_tris}), {len(img)} bytes')


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    src = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'guri.gltf')
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(paths.GAME, 'guri.bin')
    E = dump_ram(sys.argv[1])
    T = her_skeleton(guard_skeleton(E)[0])          # the guard's, her shoulders moved in (guri_model.her_skeleton)
    g = gltf.read(src)
    img, n = build(g, T, E)
    check(img, n)
    assert n - sum(len(p['idx']) for m in g['meshes'] for p in m) > 0, 'no blaster triangles'
    print(f"blaster: {n - sum(len(p['idx']) for m in g['meshes'] for p in m)} triangles on bone {HAND}")
    open(out, 'wb').write(img)
    print('wrote', out, len(img), 'bytes at', hex(BASE))
