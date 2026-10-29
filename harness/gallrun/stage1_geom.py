"""Stage 1's source (sub-level 17) geometry for the Gall Run: triangles per tile, floor and height maps.

    from gallrun.stage1_geom import Geom
    g = Geom(ram_be)            # tiles from gall_asset.level_tiles
    g.tris                      # [(tile, cmd, sub, texture, ((x,y,z) x3))] in level units
    g.floor()                   # sand cells (the source's track), lowest and highest sand
    g.maps()                    # top-down maps: top, bottom, ceiling

Tiles are 100x100 meshes turned by multiples of 90 degrees.
The source's track floor is sand: textures FLOOR. The canyon is a groove ~45 wide and ~27 deep;
in the square tiles it winds in S-bends ~12 wide whose rims are covered by large rock tops. Seen
from above those tops close the groove; from inside it they are back faces (level geometry is
one-sided), so a ship flying in the groove sees an open winding canyon.
"""
import os, struct, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from gall_asset import level_tiles

FLOOR = {0x801a7810, 0x801a7b40}       # sand: the track (and the town's streets)
X0, Y0, STEP, X1, Y1 = -860.0, -470.0, 2.0, 1870.0, 870.0


class Geom:
    def __init__(self, E):
        self.E = E
        R = self.R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
        self.tiles = level_tiles(E)
        self.tris = []
        for ti, (mesh, m, t) in enumerate(self.tiles):
            xf = lambda v: tuple(v[0] * m[0 + j] + v[1] * m[3 + j] + v[2] * m[6 + j] + t[j] for j in range(3))
            lst = R(mesh + 0x10)
            for i in range(R(mesh + 0xC)):
                p = R(lst + 4 * i)
                mat = R(p + 0x24); tex = R(mat + 8) if mat else 0
                a, buf, n = R(p + 0x28), {}, 0
                while R(a) >> 24 != 0xB8 and n < 5000:
                    w0, w1 = R(a), R(a + 4); op = w0 >> 24
                    if op == 0x04:
                        cnt, v0 = (w0 & 0xFFFF) >> 9, ((w0 >> 16) & 0xFF) // 2
                        for j in range(cnt):
                            buf[v0 + j] = xf([c / 8 for c in struct.unpack_from('>hhh', E, (w1 + 16 * j) & 0x7FFFFF)])
                    else:
                        for sub, ids in enumerate(tri_ids(w0, w1)):
                            vs = [buf.get(k) for k in ids]
                            if all(vs): self.tris.append((ti, a, sub, tex, tuple(vs)))
                    a += 8; n += 1

    def _raster(self, keep):
        """Sample every kept triangle; yields (ix, iy, z, tri index) arrays."""
        out = []
        for k, (_, _, _, _, t) in enumerate(self.tris):
            if not keep(k): continue
            a, b, c = (np.array(v, np.float32) for v in t)
            l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)); n = max(2, int(l / 1.0) + 1)
            i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij'); mm = (i + j) <= n
            u = (i[mm] / n)[:, None]; v = (j[mm] / n)[:, None]; p = a + (b - a) * u + (c - a) * v
            out.append((((p[:, 0] - X0) / STEP).astype(int), ((p[:, 1] - Y0) / STEP).astype(int), p[:, 2], np.full(len(p), k)))
        return [np.concatenate(x) for x in zip(*out)]

    def shape(self):
        return int((X1 - X0) / STEP), int((Y1 - Y0) / STEP)

    def floor(self):
        """(mask, low, top): cells with an upward sand triangle, the lowest and the highest sand
        z there (dunes: the top matters for a hull that must not sink into them)."""
        nx, ny = self.shape()
        Fm = np.zeros((nx, ny), bool); Fz = np.full((nx, ny), 1e9, np.float32)
        Ft = np.full((nx, ny), -1e9, np.float32)
        def keep(k):
            t = self.tris[k]
            if t[3] not in FLOOR: return False
            a, b, c = (np.array(v) for v in t[4]); n = np.cross(b - a, c - a); l = np.linalg.norm(n)
            return l > 0 and n[2] / l > 0.5
        ix, iy, z, _ = self._raster(keep)
        Fm[ix, iy] = True; np.minimum.at(Fz, (ix, iy), z); np.maximum.at(Ft, (ix, iy), z)
        return Fm, Fz, Ft

    def maps(self):
        """Top-down maps: H top, L bottom, C ceiling (lowest surface more than 6 above L, 1e9 if
        none: arches and the rock tops over the S-bends)."""
        nx, ny = self.shape()
        ix, iy, z, _ = self._raster(lambda k: True)
        H = np.full((nx, ny), -1e9, np.float32); L = np.full((nx, ny), 1e9, np.float32)
        np.maximum.at(H, (ix, iy), z); np.minimum.at(L, (ix, iy), z)
        C = np.full((nx, ny), 1e9, np.float32)
        hi = z > L[ix, iy] + 6
        np.minimum.at(C, (ix[hi], iy[hi]), z[hi])
        return H, L, C


def tri_ids(w0, w1):
    """Vertex buffer indices of the triangles of one DL command (TRI1 0xBF, TRI2 0xB1, QUAD 0xB5)."""
    op = w0 >> 24
    b = lambda w, s: ((w >> s) & 0xFF) // 5
    if op == 0xBF: return [[b(w1, 16), b(w1, 8), b(w1, 0)]]
    if op == 0xB1: return [[b(w0, 16), b(w0, 8), b(w0, 0)], [b(w1, 16), b(w1, 8), b(w1, 0)]]
    if op == 0xB5:
        q = [b(w1, s) for s in (24, 16, 8, 0)]
        return [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
    return []
