"""The drawn figure from RAM: every vertex used by a triangle of every mesh under a model node, in world space.

A reader is anything with u32(a) / f(a) / s16(a) on RDRAM addresses: `Ram.of(emu)` (a snapshot of a live Emu),
`Ram.load(path)` (an RDRAM dump, little-endian words, as Emu.dump writes it).

    from model_walk import Ram, drawn, height
    r = Ram.of(e); lo, hi, ht = height(r, r.u32(humn + 0x24C), r.f(humn + 0x10))

Nodes: w0 >> 28 == 0xD a bone / placement node (3x3 rows +0x14..+0x34, translation +0x38..+0x40, child count +0x0C,
child list +0x10); 3 a mesh (its sub-meshes' display lists +0x28: G_VTX 0x04 loads, G_TRI1 0xBF / G_TRI2 0xB5 use the
slots, vertex s16 / 8); 5 a variant group (its drawn one +0x14). The world of a node is its matrix after its parent's;
the top node's parent is the identity (the placement node holds the world placement). Floor: the object's +0x10
(Humn / Trop), so `height(...)[0]` is the lowest drawn vertex above the floor (the soles standing)."""
import ctypes as C
import struct
import numpy as np

RDRAM = 0x800000


class Ram:
    def __init__(s, b): s.b = b
    @classmethod
    def of(cls, emu): return cls(C.string_at(emu.rdram(), RDRAM))
    @classmethod
    def load(cls, path): return cls(open(path, 'rb').read())
    def u32(s, a): return struct.unpack_from('<I', s.b, a & 0x7FFFFC)[0]
    def f(s, a): return struct.unpack('<f', struct.pack('<I', s.u32(a)))[0]
    def s16(s, a):
        w = s.u32(a & ~3); v = (w >> 16) & 0xFFFF if (a & 2) == 0 else w & 0xFFFF
        return v - 0x10000 if v & 0x8000 else v


def ptr(v): return 0x80000400 <= v < 0x80800000
def m3(r, n): return np.array([[r.f(n + 0x14 + 4 * (3 * a + b)) for b in range(3)] for a in range(3)])
def tr(r, n): return np.array([r.f(n + 0x38 + 4 * k) for k in range(3)])


def mesh_pts(r, m, out, depth=0):
    """Model-space vertices used by the triangles of mesh node m, appended to out."""
    t = r.u32(m) >> 28
    if t == 5:
        v = r.u32(m + 0x14)
        if ptr(v) and depth < 4: mesh_pts(r, v, out, depth + 1)
        return
    if t != 3: return
    for q in range(min(r.u32(m + 0x0C), 16)):
        sub = r.u32(r.u32(m + 0x10) + 4 * q)
        if not ptr(sub): continue
        a, slot, n = r.u32(sub + 0x28), {}, 0
        while ptr(a) and r.u32(a) >> 24 != 0xB8 and n < 4000:
            w0, w1 = r.u32(a), r.u32(a + 4); c = w0 >> 24
            if c == 0x04:
                for j in range((w0 & 0xFFFF) >> 9): slot[j] = [r.s16(w1 + 16 * j + o) / 8 for o in (0, 2, 4)]
            elif c in (0xBF, 0xB5):
                for sh in ((16, 8, 0) if c == 0xBF else (24, 16, 8, 0)):
                    j = (w1 >> sh & 0xFF) // 5
                    if j in slot: out.append(slot[j])
            a += 8; n += 1


def drawn(r, top, skip=()):
    """World points (N x 3) of every mesh under node `top`, its own matrix included; children in `skip` left out."""
    pts = []
    def walk(nd, W, d):
        L = np.eye(4); L[:3, :3] = m3(r, nd); L[3, :3] = tr(r, nd); Wn = L @ W
        for j in range(min(r.u32(nd + 0x0C), 24)):
            c = r.u32(r.u32(nd + 0x10) + 4 * j)
            if not ptr(c) or c in skip: continue
            if r.u32(c) >> 28 == 0xD and d < 30: walk(c, Wn, d + 1)
            else:
                p = []; mesh_pts(r, c, p)
                if p: pts.append(np.c_[np.array(p), np.ones(len(p))] @ Wn)
    walk(top, np.eye(4), 0)
    return np.concatenate(pts)[:, :3] if pts else np.zeros((0, 3))


def height(r, top, floor, skip=()):
    """(lowest, highest drawn vertex above `floor`, their difference), world z."""
    P = drawn(r, top, skip)
    if not len(P): return float('nan'), float('nan'), float('nan')
    lo, hi = P[:, 2].min() - floor, P[:, 2].max() - floor
    return lo, hi, hi - lo


def trot_nodes(r, humn, bones=19):
    """The on-foot player's (Humn) bone nodes of his `trot` block (bone 18 the model bone), or None."""
    b = r.u32(humn + 0x19C)
    for _ in range(40):
        if not ptr(b): return None
        if r.u32(b + 0x1C) == 0x74726F74: return [r.u32(b + 0x38 + 0xA0 * i + 8) for i in range(bones)]
        b = r.u32(b + 0x14)
    return None


def tilt(r, node):
    """How upright a bone node's local up axis is in its parent frame: z / |row| of its third row (+0x2C..+0x34).
    For the model bone (trot bone 18) ~1 standing, ~0 lying; guard.c's drop is LOOK_DROP times it, clamped to 0..1."""
    v = [r.f(node + 0x2C + 4 * k) for k in range(3)]; l = (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5
    return v[2] / l if l else 1.0
