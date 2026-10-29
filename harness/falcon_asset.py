"""Build the Millennium Falcon model image for the controls patch (feature `falcon`).

    M64CPU=0 python3 falcon_asset.py <rom> [out.bin]     (default local/game/falcon.bin)

The Falcon exists only as scenery in the ship-model source (an `Anim` that flies it out of the hangar). The
level data is compressed in the ROM, so the model is taken from RAM: load states/src_model.st (Echo
Base, sub-level 4), dump RDRAM, collect the mesh (docs/reverse-engineering.md, "Mesh node") and
move it to BASE with every pointer fixed. The vertices are scaled and turned so the ship fits
the Outrider's place in the base level: both fly along +y of the model once the Falcon is turned
180 degrees (its mandibles are at -y, the Outrider flies toward +y). Drawn lit, as the Outrider: its
part materials' +0 / +0xC set 0xE and outward vertex normals written over the white vertex colours (normals()).

Layout at BASE: header {'FALC', part count, part list, bounding box, turret x, y, top z,
bottom z (floats: where falcon.c puts the Outrider's two gun pivots, on the Falcon's turret
domes), a ready mesh node of the Falcon (the Gall Run level's ship model points at it:
gallrun/level_edit.py)}, then the geometry (vertices + geometry DLs), the texture blocks (palette, texels,
texture DL), the records.
"""
import ctypes, math, os, struct, sys
import paths
from m64 import Emu, HERE

BASE = 0x80500000
MESH = 0x801FCACC          # Falcon mesh node in the ship-model source (via Anim -> Dfob #33 +0x84 -> root -> ...)
SCALE, YAW = 0.6, math.radians(180)
TURRET = 3                 # part: the turret rings, top and bottom (decagons, centre (0, 4.6), z +-4.3)
HEADER = 48
LIT = 0xE                  # a part material's +0 / +0xC when lit (the Outrider hull's; the ship-model source's Falcon: 0xC, 0)


def dump_ram(rom):
    out = {}
    e = Emu(rom)

    def script(e, n):
        if n == 60: e.load_state(os.path.join(paths.STATES, 'src_model.st'))
        if n == 70:
            raw = ctypes.string_at(e.rdram(), 0x800000)      # host-endian words
            out['ram'] = b''.join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4))
            e.stop()
    e.run(script)
    return out['ram']


def build(E):
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]

    def dl_end(a):
        while R(a) >> 24 != 0xB8: a += 8
        return a + 8

    n, plist, bbox = R(MESH + 0xC), R(MESH + 0x10), R(MESH + 0x14)
    assert R(MESH) >> 28 == 3 and n == 16, 'not the Falcon mesh: is src_model.st sub-level 4?'
    parts = [R(plist + 4 * i) for i in range(n)]
    geo, vtx, tex = [], [], []
    for p in parts:
        g = R(p + 0x28); geo.append((g, dl_end(g)))
        for a in range(g, dl_end(g) - 8, 8):
            op = R(a) >> 24
            assert op != 0x06, 'nested DL in a geometry list'
            if op == 0x04:   # G_VTX: n = (w0 & 0xFFFF) >> 9, 16 bytes each
                vtx.append((R(a + 4), R(a + 4) + ((R(a) & 0xFFFF) >> 9) * 16))
        t = R(R(p + 0x24) + 8)
        tex.append((R(t + 0xC), dl_end(R(t + 8))))
    G = (min(r[0] for r in geo + vtx), max(r[1] for r in geo + vtx))
    T = (min(r[0] for r in tex), max(r[1] for r in tex))

    img = bytearray(HEADER)
    gnew = BASE + len(img); img += E[G[0] & 0x7FFFFF:G[1] & 0x7FFFFF]; dG = gnew - G[0]
    img += bytes(-len(img) % 16)
    tnew = BASE + len(img); img += E[T[0] & 0x7FFFFF:T[1] & 0x7FFFFF]; dT = tnew - T[0]
    img += bytes(-len(img) % 16)
    put = lambda a, v: struct.pack_into('>I', img, a - BASE, v & 0xFFFFFFFF)
    get = lambda a: struct.unpack_from('>I', img, a - BASE)[0]

    def xf(x, y, z):
        c, s = math.cos(YAW), math.sin(YAW)
        return (x * c - y * s) * SCALE, (x * s + y * c) * SCALE, z * SCALE

    s16 = lambda v: max(-32768, min(32767, int(round(v))))
    for a in sorted({a for v0, v1 in vtx for a in range(v0, v1, 16)}):
        o = a + dG - BASE
        img[o:o + 6] = struct.pack('>hhh', *map(s16, xf(*struct.unpack_from('>hhh', img, o))))
    for g0, g1 in geo:
        for a in range(g0 + dG, g1 + dG, 8):
            if get(a) >> 24 == 0x04: put(a + 4, get(a + 4) + dG)
    # Texture DLs (some are shared by parts): the segment 4 base (MOVEWORD 0xBC001006) and
    # any absolute RAM address move with the block; SETTIMGs use segment 4 and stay.
    for a in {R(R(R(p + 0x24) + 8) + 8) + dT for p in parts}:
        while get(a) >> 24 != 0xB8:
            w0, w1 = get(a), get(a + 4)
            if w0 == 0xBC001006 or (w0 >> 24 in (0x06, 0xFD) and 0x80000000 <= w1 < 0x80800000):
                put(a + 4, w1 + dT)
            a += 8

    def alloc(b):
        a = BASE + len(img); img.extend(b); img.extend(bytes(-len(img) % 16)); return a

    texrec, mat, newparts = {}, {}, []
    for p in parts:
        m = R(p + 0x24); t = R(m + 8)
        if t not in texrec:
            b = bytearray(E[t & 0x7FFFFF:(t & 0x7FFFFF) + 16])
            struct.pack_into('>II', b, 8, R(t + 8) + dT, R(t + 12) + dT)
            texrec[t] = alloc(b)
        if m not in mat:              # +0 and +0xC = LIT: the parts drawn lit, as the Outrider hull's
            b = bytearray(E[m & 0x7FFFFF:(m & 0x7FFFFF) + 12]) + bytes(4)
            struct.pack_into('>I', b, 8, texrec[t]); struct.pack_into('>I', b, 0, LIT); struct.pack_into('>I', b, 0xC, LIT)
            mat[m] = alloc(b)
        b = bytearray(E[p & 0x7FFFFF:(p & 0x7FFFFF) + 0x2C])
        lo, hi = struct.unpack_from('>3f', b, 0), struct.unpack_from('>3f', b, 12)
        cs = [xf(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        struct.pack_into('>6f', b, 0, *[min(c[i] for c in cs) for i in range(3)], *[max(c[i] for c in cs) for i in range(3)])
        struct.pack_into('>II', b, 0x24, mat[m], R(p + 0x28) + dG)
        newparts.append(alloc(b))
    lst = alloc(b''.join(struct.pack('>I', x) for x in newparts))
    bb = bytearray(E[bbox & 0x7FFFFF:(bbox & 0x7FFFFF) + 0x80])
    for o in range(0, 0x80, 16):
        bb[o:o + 6] = struct.pack('>hhh', *map(s16, xf(*struct.unpack_from('>hhh', bb, o))))
    box = alloc(bb)
    lo, hi = struct.unpack_from('>3f', E, (parts[TURRET] & 0x7FFFFF)), struct.unpack_from('>3f', E, (parts[TURRET] & 0x7FFFFF) + 12)
    tx, ty, _ = xf((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0)
    node = alloc(struct.pack('>6I', 0x3064FF00, 0xFFFFFFFF, 0, n, lst, box))   # a mesh node (as the Outrider's hull)
    struct.pack_into('>4sIII4fI', img, 0, b'FALC', n, lst, box, tx, ty, hi[2] * SCALE, lo[2] * SCALE, node)
    normals(img, [R(p + 0x28) + dG for p in parts])
    return bytes(img)


def normals(img, geos):
    """Vertex normals in the colour / normal slot (+12..+14, signed bytes, length 127; alpha +15 kept): per vertex the
    mean of the unit normals of the faces that use it, each face's normal turned outward (its sign by the dot with
    vertex - the model's centroid; the source's model is not closed, its winding does not say it). Faces from the
    geometry DLs: G_VTX (0x04) loads from slot 0, triangles 0xBF (w1 bytes 1..3) and quads 0xB5 (w1 bytes 0..3), the
    indices x5 in this microcode. A vertex on no face gets (0, 0, 127)."""
    get = lambda a: struct.unpack_from('>I', img, a - BASE)[0]
    pos = lambda v: struct.unpack_from('>hhh', img, v - BASE)
    faces, used = [], set()
    for g in geos:
        base, a = None, g
        while get(a) >> 24 != 0xB8:
            w0, w1 = get(a), get(a + 4); op = w0 >> 24
            if op == 0x04:
                base = w1
                used.update(range(w1, w1 + ((w0 & 0xFFFF) >> 9) * 16, 16))
            elif op in (0xBF, 0xB5) and base is not None:
                sh = (16, 8, 0) if op == 0xBF else (24, 16, 8, 0)
                faces.append([base + 16 * (((w1 >> k) & 0xFF) // 5) for k in sh])
            a += 8
    on = {v for f in faces for v in f}
    cx = [sum(pos(v)[t] for v in on) / len(on) for t in range(3)]
    acc = {}
    for f in faces:
        a, b, c = (pos(v) for v in f[:3])
        u = [b[t] - a[t] for t in range(3)]; w = [c[t] - a[t] for t in range(3)]
        nn = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        l = math.sqrt(sum(x * x for x in nn))
        if not l: continue
        for v in f:
            out = sum(nn[t] * (pos(v)[t] - cx[t]) for t in range(3))
            sg = 1 if out >= 0 else -1
            s = acc.setdefault(v, [0.0, 0.0, 0.0])
            for t in range(3): s[t] += sg * nn[t] / l
    for v in used:
        s = acc.get(v, [0, 0, 1]); l = math.sqrt(sum(x * x for x in s)) or 1
        if not acc.get(v) or l < 1e-6: s, l = [0, 0, 1], 1
        o = v - BASE + 12
        img[o:o + 3] = struct.pack('>3b', *[max(-127, min(127, int(round(127 * s[t] / l)))) for t in range(3)])
    print(f'falcon: normals on {len(acc)} of {len(used)} vertices, {len(faces)} faces')


if __name__ == '__main__':
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(paths.GAME, 'falcon.bin')
    img = build(dump_ram(sys.argv[1]))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(img)
    print(f'falcon: {len(img)} bytes for {BASE:#x} -> {out}')
