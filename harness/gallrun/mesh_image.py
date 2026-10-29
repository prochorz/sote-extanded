"""Copy meshes out of a RAM dump into one relocatable mesh image (render only).

    from mesh_image import build_image
    img, hdr = build_image(ram_be, [mesh, ...], base, xf=None)

ram_be: an RDRAM dump as big-endian bytes (Emu.dump() words byte-swapped). Every part of every
mesh (docs/reverse-engineering.md, "Mesh node") is copied block by block: geometry DL, the
vertex ranges its G_VTX commands load, the texture block (palette + texels + texture DL) and the
part / material / texture records. Pointers are moved with a map of old -> new block addresses:
G_VTX addresses, the texture DL's segment-4 base (MOVEWORD 0xBC001006, checked to cover every
SETTIMG of that DL inside its block), record pointers. The part pointers at +0x1C/+0x20 (level
geometry: collision or visibility data) are cleared. xf(x, y, z) -> (x, y, z), if given,
transforms the vertices and the part boxes (vertices are 16-bit, 8x the part units).
Parts without a material (+0x24 = 0) are faces the game does not draw (collision only):
untextured=False leaves them out. keep(part) -> bool, if given, picks the parts to copy.
Level geometry hangs under a room transform node (e.g. translation (-200, 900, 0) in Gall) and
its vertices are room-local while its part boxes are already in world units: voff = {mesh:
(dx, dy, dz)} adds that translation to the vertices of that mesh (room_offsets() finds it); {mesh: (R, t)}
turns them too (R 3x3, v' = R v + t: a posed model's bones, level_map.meshes_of()).

Layout at base: header {'MESH', part count, part list, bounding box (8 vertices, the union of
the part boxes)}, then the blocks, then the records.

One copy of each texture: while TEX_SHARE is a dict (gall_asset.build() sets
it for the image it assembles), a texture block (palette + texels + texture DL) whose bytes equal one already copied
into that image (tex_key(): its content, the DL's segment base taken relative to the block) is not copied again: the
part's texture record points at the earlier copy. Only for blobs that go into the image at the base they were built
for (a dry run passes share=False). share_tag keeps blocks apart that are changed after the copy (the lightspeed
trail's whitened palette: slave_pad.white_tlut()).
"""
import hashlib, struct

HEADER = 16
TEX_SHARE = None              # {tex_key: the copy's block start (image address)} while an image is assembled


def tex_key(E, t, tag=''):
    """Texture record t's block in RAM E as a key: (tag, the DL's offset in the block, a hash of the block's bytes with
    the DL's segment-4 base made relative to the block)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    d, blk = R(t + 8), R(t + 0xC)
    end = d
    while R(end) >> 24 != 0xB8: end += 8
    end += 8
    b = bytearray(E[blk & 0x7FFFFF:end & 0x7FFFFF])
    for a in range(d, end, 8):
        if R(a) == 0xBC001006: struct.pack_into('>I', b, a - blk + 4, (R(a + 4) - blk) & 0xFFFFFFFF)
    return (tag, d - blk, hashlib.sha1(bytes(b)).hexdigest())


def build_image(E, meshes, base, xf=None, voff=None, header=HEADER, untextured=True, keep=None, share=True, share_tag=''):
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]

    def dl_end(a):
        n = 0
        while R(a) >> 24 != 0xB8:
            a += 8; n += 1
            assert n < 20000, 'no ENDDL'
        return a + 8

    parts, part_off = [], {}
    for m in meshes:
        assert R(m) >> 28 == 3, f'{m:08x} is not a mesh node'
        lst = R(m + 0x10)
        for i in range(R(m + 0xC)):
            p = R(lst + 4 * i)
            if not untextured and not R(p + 0x24): continue   # no material: invisible (collision) face
            if keep and not keep(p): continue                 # (the caller's pick)
            parts.append(p)
            part_off[p] = (voff or {}).get(m, (0, 0, 0))

    blocks = {}                                     # old start -> old end

    def add(a, b):
        blocks[a] = max(blocks.get(a, a), b)

    reg = TEX_SHARE if share else None
    alias = {}                                      # old texture block start -> (its end, the copy's start or the
    first = {}                                      # block of this build it equals: ('src', old start))
    vtx = []
    for p in parts:
        g = R(p + 0x28); add(g, dl_end(g))
        for a in range(g, dl_end(g) - 8, 8):
            op = R(a) >> 24
            assert op != 0x06, f'nested DL in geometry {a:08x}'
            if op == 0x04:
                v = R(a + 4); vtx.append((v, v + ((R(a) & 0xFFFF) >> 9) * 16, part_off[p]))
        if R(p + 0x24):                              # 0: untextured part (vertex colours)
            t = R(R(p + 0x24) + 8)
            blk, end = R(t + 0xC), dl_end(R(t + 8))
            if reg is not None and blk not in alias:
                k = tex_key(E, t, share_tag)
                if k in reg: alias[blk] = (end, reg[k]); continue
                if first.setdefault(k, blk) != blk: alias[blk] = (end, ('src', first[k])); continue
            if blk in alias: continue
            add(blk, end)
    for v0, v1, _ in vtx: add(v0, v1)
    # Merge overlapping blocks (vertex ranges overlap each other and sometimes a DL).
    merged = []
    for a in sorted(blocks):
        b = blocks[a]
        if merged and a <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], b)
        else: merged.append([a, b])

    img = bytearray(header)                       # caller may want a larger header
    newat = []                                      # (old start, old end, new start)
    for a, b in merged:
        img += bytes(-len(img) % 16)
        newat.append((a, b, base + len(img)))
        img += E[a & 0x7FFFFF:b & 0x7FFFFF]

    def mv(a):
        for s, e_, n in newat:
            if s <= a < e_: return a - s + n
        for s, (e_, n) in alias.items():
            if isinstance(n, tuple): n = mv(n[1])
            if s <= a < e_: return a - s + n
        raise KeyError(f'{a:08x} not in a copied block')

    for s, (e_, _) in alias.items():
        assert not any(a < e_ and s < b for a, b, _ in newat), f'shared texture block {s:08x} overlaps a copied block'

    get = lambda a: struct.unpack_from('>I', img, a - base)[0]
    put = lambda a, v: struct.pack_into('>I', img, a - base, v & 0xFFFFFFFF)
    s16 = lambda v: max(-32768, min(32767, int(round(v))))

    if xf or voff:
        done = {}
        for v0, v1, off in vtx:
            for a in range(v0, v1, 16):
                if a in done:
                    assert done[a] is off or done[a] == off, f'vertex {a:08x} shared by meshes with different room offsets'
                    continue
                done[a] = off
                o = mv(a) - base
                x, y, z = struct.unpack_from('>hhh', img, o)
                if len(off) == 2:                        # (R, t): turned too (a model's bones)
                    X, Y, Z = (sum(off[0][i][j] * (x, y, z)[j] / 8 for j in range(3)) + off[1][i] for i in range(3))
                else:
                    X, Y, Z = x / 8 + off[0], y / 8 + off[1], z / 8 + off[2]
                if xf: X, Y, Z = xf(X, Y, Z)
                struct.pack_into('>hhh', img, o, s16(X * 8), s16(Y * 8), s16(Z * 8))
    fixed = set()
    for p in parts:
        g = R(p + 0x28)
        if g not in fixed:
            fixed.add(g)
            for a in range(mv(g), mv(g) + dl_end(g) - g, 8):
                if get(a) >> 24 == 0x04: put(a + 4, mv(get(a + 4)))
        if not R(p + 0x24): continue
        t = R(R(p + 0x24) + 8)
        d = R(t + 8)
        if d in fixed or R(t + 0xC) in alias: continue
        fixed.add(d)
        seg, imgs = None, []
        for a in range(d, dl_end(d), 8):
            if R(a) == 0xBC001006: seg = R(a + 4)
            elif R(a) >> 24 == 0xFD: imgs.append(R(a + 4))
        delta = mv(R(t + 0xC)) - R(t + 0xC)
        for i in imgs:                              # every image must lie in this texture block
            phys = ((i & 0x00FFFFFF) + seg) & 0xFFFFFFFF if (i >> 24) & 0x0F == 4 else i
            phys |= 0x80000000
            assert R(t + 0xC) <= phys < dl_end(d), f'texture {i:08x} outside its block'
        for a in range(mv(d), mv(d) + dl_end(d) - d, 8):
            if get(a) == 0xBC001006: put(a + 4, get(a + 4) + delta)

    if reg is not None:                             # (the blocks copied here, for later builds)
        for k, blk in first.items():
            if blk not in alias: reg.setdefault(k, mv(blk))

    def alloc(b):
        img.extend(bytes(-len(img) % 16)); a = base + len(img); img.extend(b); return a

    texrec, mat, newparts = {}, {}, []
    lo, hi = [1e9] * 3, [-1e9] * 3
    for p in parts:
        m = R(p + 0x24); t = R(m + 8) if m else 0
        if m and t not in texrec:
            b = bytearray(E[t & 0x7FFFFF:(t & 0x7FFFFF) + 16])
            struct.pack_into('>II', b, 8, mv(R(t + 8)), mv(R(t + 12)))
            texrec[t] = alloc(b)
        if m and m not in mat:
            b = bytearray(E[m & 0x7FFFFF:(m & 0x7FFFFF) + 12]); struct.pack_into('>I', b, 8, texrec[t]); mat[m] = alloc(b)
        b = bytearray(E[p & 0x7FFFFF:(p & 0x7FFFFF) + 0x2C])
        l3, h3 = struct.unpack_from('>3f', b, 0), struct.unpack_from('>3f', b, 12)
        if xf:
            cs = [xf(x, y, z) for x in (l3[0], h3[0]) for y in (l3[1], h3[1]) for z in (l3[2], h3[2])]
            l3 = [min(c[i] for c in cs) for i in range(3)]; h3 = [max(c[i] for c in cs) for i in range(3)]
            struct.pack_into('>6f', b, 0, *l3, *h3)
        for i in range(3): lo[i] = min(lo[i], l3[i]); hi[i] = max(hi[i], h3[i])
        struct.pack_into('>II', b, 0x1C, 0, 0)
        struct.pack_into('>II', b, 0x24, mat[m] if m else 0, mv(R(p + 0x28)))
        newparts.append(alloc(b))
    lst = alloc(b''.join(struct.pack('>I', x) for x in newparts))
    bb = b''.join(struct.pack('>hhhhhhhh', s16(x * 8), s16(y * 8), s16(z * 8), 0, 0, 0, 0, 0)
                  for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2]))
    box = alloc(bb)
    struct.pack_into('>4sIII', img, 0, b'MESH', len(parts), lst, box)
    img.extend(bytes(-len(img) % 16))
    return bytes(img), dict(parts=len(parts), list=lst, box=box, lo=lo, hi=hi)


def room_offsets(E, meshes):
    """{mesh: translation of the nearest transform node above it} (level geometry rooms)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    F = lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]
    parent = {}                                     # child -> parent node, from every child list
    for off in range(0x100000, 0x400000, 4):
        a = 0x80000000 + off; w0 = R(a)
        if (w0 >> 28) not in (5, 0xD) or (w0 >> 16) & 0xFF not in (0x64, 0x65): continue
        n, lst = R(a + 0xC), R(a + 0x10)
        if not (0 < n < 512 and 0x80100000 <= lst < 0x80400000): continue
        for i in range(n): parent.setdefault(R(lst + 4 * i), a)
    out = {}
    for m in meshes:
        p, t = parent.get(m), (0.0, 0.0, 0.0)
        while p:
            if R(p) >> 28 == 0xD:
                t = tuple(F(p + 0x38 + 4 * i) for i in range(3)); break
            p = parent.get(p)
        out[m] = t
    return out


def fitted_offsets(E, meshes):
    """{mesh: room translation} from the data itself: each part's box is in world units, its
    vertices are room-local (x8), so offset = box min - vertex min / 8 (median over parts).
    Works for meshes whose room node room_offsets() cannot find."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    out = {}
    for m in meshes:
        lst, cand = R(m + 0x10), []
        for i in range(R(m + 0xC)):
            p = R(lst + 4 * i); g = R(p + 0x28); a = g; vs = []
            for _ in range(5000):
                w0 = R(a)
                if w0 >> 24 == 0xB8: break
                if w0 >> 24 == 0x04:
                    v = R(a + 4)
                    vs += [struct.unpack_from('>hhh', E, (v + 16 * j) & 0x7FFFFF) for j in range((w0 & 0xFFFF) >> 9)]
                a += 8
            if not vs: continue
            box = struct.unpack_from('>3f', E, p & 0x7FFFFF)
            cand.append(tuple(round(box[k] - min(v[k] for v in vs) / 8) for k in range(3)))
        if cand:
            cand.sort(); out[m] = cand[len(cand) // 2]
        else:
            out[m] = (0, 0, 0)
    return out


def build_tiles(sets, base, header=HEADER, cell=0):
    """Like build_image for tiled levels (stage 1's and stage 2's sources). sets = [(E,
    tiles)], [(E, tiles, keep)] or [(E, tiles, keep, (Es, retex))], E a RAM dump (as for
    build_image), tiles = [(mesh, m, t)] (the same mesh may repeat), keep(part, tile translation) -> bool picks the
    parts to copy (default: all), retex = {texture record: texture record in the dump Es}: those
    parts drawn with another level's texture (its block copied too; the vertices' texture
    coordinates stay, so its size sets how often it repeats); (Es, retex, flat): the parts with
    a texture record in `flat` are also flattened to the tile's z 0. A fifth item warp(x, y, z) -> z moves every
    vertex's world z (the part boxes stay as they were: warp may only lower). Each tile gets its own copy of the geometry DLs and vertices, moved into world units
    (v' = v * m + t, m the 3x3 rotation of the tile's transform node, rows in order, t its
    translation; a mirroring m gets its triangles' winding reversed). Texture blocks and records are shared within a set. Vertex colours are prelit
    (no normals). cell=N joins the parts of a tile that share a material and an NxN cell (by the
    centre of their boxes, tile units) into one part (their geometry DLs one after the other):
    far fewer parts, and every part costs the game a few display list commands per frame. The
    cells keep parts small: the game drops a whole part (a tile's floor, merged into one) from
    the view as one piece. Returns the image and one {parts, list, box, lo, hi} per set."""
    img = bytearray(header)
    get = lambda a: struct.unpack_from('>I', img, a - base)[0]
    putw = lambda a, v: struct.pack_into('>I', img, a - base, v & 0xFFFFFFFF)
    s16 = lambda v: max(-32768, min(32767, int(round(v))))

    def merge(blocks):
        out = []
        for a in sorted(blocks):
            b = blocks[a]
            if out and a <= out[-1][1]: out[-1][1] = max(out[-1][1], b)
            else: out.append([a, b])
        return out

    def alloc(b):
        img.extend(bytes(-len(img) % 16)); a = base + len(img); img.extend(b); return a

    out = []
    for E, tiles, *rest in sets:
        keep = rest[0] if rest else (lambda p, t: True)
        Es, retex, *fl = rest[1] if len(rest) > 1 else (None, {})
        flat = fl[0] if fl else set()               # texture records whose parts are flattened to z 0
        warp = rest[2] if len(rest) > 2 else None
        R = lambda a, E=E: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]

        def dl_end(a):
            n = 0
            while R(a) >> 24 != 0xB8:
                a += 8; n += 1
                assert n < 20000, 'no ENDDL'
            return a + 8

        def put_block(a, b, E=E):
            return alloc(E[a & 0x7FFFFF:b & 0x7FFFFF])

        tex = {}                                    # texture blocks, shared within the set
        for mesh, _m, tt in tiles:
            lst = R(mesh + 0x10)
            for i in range(R(mesh + 0xC)):
                p = R(lst + 4 * i)
                if R(p + 0x24) and keep(p, tt):
                    t = R(R(p + 0x24) + 8)
                    tex[R(t + 0xC)] = max(tex.get(R(t + 0xC), 0), dl_end(R(t + 8)))
        shared = [(a, b, put_block(a, b)) for a, b in merge(tex)]

        swap = {}                                   # old texture record -> new record in the image
        for old, new in retex.items():
            Rs = lambda a: struct.unpack_from('>I', Es, a & 0x7FFFFF)[0]
            d, blk = Rs(new + 8), Rs(new + 0xC)
            n, e_ = 0, d
            while Rs(e_) >> 24 != 0xB8: e_ += 8; n += 1; assert n < 2000
            at = put_block(blk, e_ + 8, Es)
            for a in range(at + d - blk, at + e_ + 8 - blk, 8):
                if get(a) == 0xBC001006: putw(a + 4, get(a + 4) + at - blk)
            b = bytearray(Es[new & 0x7FFFFF:(new & 0x7FFFFF) + 16])
            struct.pack_into('>II', b, 8, at + d - blk, at)
            swap[old] = alloc(b)

        def mv(a, local=()):
            for s_, e_, n in list(local) + shared:
                if s_ <= a < e_: return a - s_ + n
            raise KeyError(f'{a:08x} not in a copied block')

        fixed_tex, texrec, mat = set(), {}, {}
        newparts = []
        lo, hi = [1e9] * 3, [-1e9] * 3
        def flip_winding(a):
            """Reverse the triangles' vertex order in the command at a (a mirrored tile would face away)."""
            w0, w1 = get(a), get(a + 4); op = w0 >> 24
            b = lambda w, k: (w >> (8 * k)) & 0xFF
            if op == 0xBF: putw(a + 4, (b(w1, 3) << 24) | (b(w1, 2) << 16) | (b(w1, 0) << 8) | b(w1, 1))
            elif op == 0xB1:
                putw(a, (w0 & 0xFF000000) | (b(w0, 2) << 16) | (b(w0, 0) << 8) | b(w0, 1))
                putw(a + 4, (b(w1, 3) << 24) | (b(w1, 2) << 16) | (b(w1, 0) << 8) | b(w1, 1))
            elif op == 0xB5: putw(a + 4, (b(w1, 3) << 24) | (b(w1, 0) << 16) | (b(w1, 1) << 8) | b(w1, 2))

        for mesh, m, t in tiles:
            mirrored = (m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6])
                        + m[2] * (m[3] * m[7] - m[4] * m[6])) < 0
            xf = lambda x, y, z, m=m, t=t: tuple(x * m[0 + j] + y * m[3 + j] + z * m[6 + j] + t[j] for j in range(3))
            lst = R(mesh + 0x10)
            parts = [p for p in (R(lst + 4 * i) for i in range(R(mesh + 0xC))) if keep(p, t)]
            if not parts: continue
            blocks, vtx = {}, []
            for p in parts:
                g = R(p + 0x28); blocks[g] = max(blocks.get(g, g), dl_end(g))
                fz = R(p + 0x24) and R(R(p + 0x24) + 8) in flat
                for a in range(g, dl_end(g) - 8, 8):
                    assert R(a) >> 24 != 0x06, f'nested DL in geometry {a:08x}'
                    if R(a) >> 24 == 0x04:
                        v = R(a + 4); e_ = v + ((R(a) & 0xFFFF) >> 9) * 16
                        vtx.append((v, e_, fz)); blocks[v] = max(blocks.get(v, v), e_)
            local = [(a, b, put_block(a, b)) for a, b in merge(blocks)]
            done = set()
            for v0, v1, fz in vtx:
                for a in range(v0, v1, 16):
                    if a in done: continue
                    done.add(a)
                    o = mv(a, local) - base
                    x, y, z = struct.unpack_from('>hhh', img, o)
                    X, Y, Z = xf(x / 8, y / 8, 0 if fz else z / 8)
                    if warp: Z = float(warp(X, Y, Z))
                    struct.pack_into('>hhh', img, o, s16(X * 8), s16(Y * 8), s16(Z * 8))
            dls, recs = set(), []
            for p in parts:
                g = R(p + 0x28)
                if g not in dls:
                    dls.add(g)
                    for a in range(mv(g, local), mv(g, local) + dl_end(g) - g, 8):
                        if get(a) >> 24 == 0x04: putw(a + 4, mv(get(a + 4), local))
                        elif mirrored: flip_winding(a)
                mt = R(p + 0x24); tr = R(mt + 8) if mt else 0
                if mt and tr not in texrec:
                    d = R(tr + 8); delta = mv(R(tr + 0xC)) - R(tr + 0xC)
                    if d not in fixed_tex:
                        fixed_tex.add(d)
                        for a in range(mv(d), mv(d) + dl_end(d) - d, 8):
                            if get(a) == 0xBC001006: putw(a + 4, get(a + 4) + delta)
                    b = bytearray(E[tr & 0x7FFFFF:(tr & 0x7FFFFF) + 16])
                    struct.pack_into('>II', b, 8, mv(R(tr + 8)), mv(R(tr + 12)))
                    texrec[tr] = alloc(b)
                if mt and mt not in mat:
                    b = bytearray(E[mt & 0x7FFFFF:(mt & 0x7FFFFF) + 12]); struct.pack_into('>I', b, 8, swap.get(tr, texrec[tr])); mat[mt] = alloc(b)
                b = bytearray(E[p & 0x7FFFFF:(p & 0x7FFFFF) + 0x2C])
                l3, h3 = struct.unpack_from('>3f', b, 0), struct.unpack_from('>3f', b, 12)
                # part boxes of tiled meshes are tile-local like the vertices
                cs = [xf(x, y, z) for x in (l3[0], h3[0]) for y in (l3[1], h3[1]) for z in (l3[2], h3[2])]
                l3 = [min(c[i] for c in cs) for i in range(3)]; h3 = [max(c[i] for c in cs) for i in range(3)]
                struct.pack_into('>6f', b, 0, *l3, *h3)
                for i in range(3): lo[i] = min(lo[i], l3[i]); hi[i] = max(hi[i], h3[i])
                struct.pack_into('>II', b, 0x1C, 0, 0)
                struct.pack_into('>II', b, 0x24, mat[mt] if mt else 0, mv(g, local))
                c = [(l0 + h0) / 2 for l0, h0 in zip(struct.unpack_from('>3f', E, p & 0x7FFFFF),
                                                     struct.unpack_from('>3f', E, (p & 0x7FFFFF) + 12))]
                recs.append(((mt, int(c[0] // cell), int(c[1] // cell)) if cell else None, b, mv(g, local), dl_end(g) - g))
            groups = {}
            for r in recs: groups.setdefault(r[0] if cell else id(r), []).append(r)
            for grp in groups.values():
                b = grp[0][1]
                if len(grp) > 1:
                    dl = b''.join(bytes(img[g - base:g - base + n - 8]) for _, _, g, n in grp) + struct.pack('>II', 0xB8000000, 0)
                    l3 = [min(struct.unpack_from('>3f', r[1], 0)[i] for r in grp) for i in range(3)]
                    h3 = [max(struct.unpack_from('>3f', r[1], 12)[i] for r in grp) for i in range(3)]
                    struct.pack_into('>6f', b, 0, *l3, *h3)
                    struct.pack_into('>I', b, 0x28, alloc(dl))
                newparts.append(alloc(b))
        lst = alloc(b''.join(struct.pack('>I', x) for x in newparts))
        bb = b''.join(struct.pack('>hhhhhhhh', s16(x * 8), s16(y * 8), s16(z * 8), 0, 0, 0, 0, 0)
                      for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2]))
        out.append(dict(parts=len(newparts), list=lst, box=alloc(bb), lo=lo, hi=hi))
    struct.pack_into('>4sIII', img, 0, b'MESH', out[0]['parts'], out[0]['list'], out[0]['box'])
    img.extend(bytes(-len(img) % 16))
    return bytes(img), out
