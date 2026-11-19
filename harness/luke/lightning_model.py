"""Lightning over Luke (the duel: Guri's Disruptor burst, guard.c guard_zap): per body part, VARIANTS variants of
STRIPS jagged strips crawling over it, for harness/guard_asset.py (it puts them into guard.bin as the LITN list).

    python3 luke/lightning_model.py [--sheet out.png]   the triangle counts for a sample part (and a drawing of its
                                                        three variants, top and side)

A part is the box of the Look's meshes on one of Dash's bones (its local frame, local units): the strips run over the
ellipsoid of that box grown by GROW (outside the armour), each a polyline of SEGS segments that turns by up to TURN
degrees at every joint (the jag), as a ribbon of three rows (edge, core, edge), WIDTH of the part's mean half-size
wide: the edges blue (EDGE), the core white (CORE), unlit (the game's vertex colours). The ribbon faces outward
(wound counter-clockwise seen from outside: the game culls back faces). Each variant a different random draw (SEED +
the part's and the variant's numbers), so cycling them flickers. 4 triangles a segment: STRIPS x SEGS x 4 <= TRI_MAX.
"""
import math, os, sys
import numpy as np

VARIANTS = 3
STRIPS = 7                  # 6..8 a variant
SEGS = 4
TRI_MAX = 120
GROW = 1.2                  # the ellipsoid's radii: the box's half-sizes x this (the armour's corners stay inside)
WIDTH = 0.07                # the ribbon's width / the part's mean half-size
STEP = 0.32                 # a segment's length / the part's mean half-size
TURN = 55.0                 # deg: the most a segment turns from the one before
LIFT = 0.04                 # the core raised over the edges (/ the mean half-size): the bolt's ridge
EDGE = (0x60 / 255, 0xA0 / 255, 1.0, 1.0)     # 0x60A0FFFF
CORE = (1.0, 1.0, 1.0, 1.0)
SEED = 4242


def ellipsoid(c, r):
    """(point(u), normal(u)) on the ellipsoid of centre c, radii r, u a unit direction."""
    def point(u): return c + r * u
    def normal(u):
        n = u / r
        return n / np.linalg.norm(n)
    return point, normal


def strips(lo, hi, rng):
    """One variant over the box lo..hi: (positions (N, 3), colours (N, 4), triangles (M, 3))."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    c, h = (lo + hi) / 2, np.maximum((hi - lo) / 2, 1e-3)
    r = h * GROW; m = float(np.mean(h))
    point, normal = ellipsoid(c, r)
    pos, col, tri = [], [], []
    for s in range(STRIPS):
        u = rng.normal(size=3); u /= np.linalg.norm(u)
        n = normal(u)
        d = np.cross(n, rng.normal(size=3)); d /= np.linalg.norm(d)      # a direction along the surface
        path = [u]
        for k in range(SEGS):
            n = normal(path[-1])
            t = math.radians(rng.uniform(-TURN, TURN))
            side = np.cross(n, d)
            d = math.cos(t) * d + math.sin(t) * side                     # the jag: a turn about the normal
            d -= n * (d @ n); d /= np.linalg.norm(d)
            q = point(path[-1]) + d * STEP * m                           # a step along it, back onto the ellipsoid
            v = (q - c) / r; v /= np.linalg.norm(v)
            path.append(v)
        base = len(pos)
        P = [point(v) for v in path]
        for k, v in enumerate(path):
            n = normal(v)
            a = P[min(k + 1, SEGS)] - P[max(k - 1, 0)]
            w = np.cross(a, n); w /= np.linalg.norm(w)                   # across the ribbon, in the surface
            half = WIDTH * m * (0.5 if k in (0, SEGS) else 1.0) / 2      # the ends taper
            for off, cc, up in ((-half, EDGE, 0.0), (0.0, CORE, LIFT * m), (half, EDGE, 0.0)):
                pos.append(P[k] + w * off + n * up); col.append(cc)
        for k in range(SEGS):
            a, b = base + 3 * k, base + 3 * (k + 1)
            for i in range(2):                                           # edge-core and core-edge quads
                p0, p1, p2, p3 = a + i, a + i + 1, b + i + 1, b + i
                for t3 in ((p0, p1, p2), (p0, p2, p3)):
                    e1, e2 = pos[t3[1]] - pos[t3[0]], pos[t3[2]] - pos[t3[0]]
                    out = normal(path[k])
                    tri.append(t3 if np.cross(e1, e2) @ out > 0 else (t3[0], t3[2], t3[1]))
    assert len(tri) <= TRI_MAX, len(tri)
    return np.array(pos), np.array(col), np.array(tri)


def variants(lo, hi, part):
    """The part's VARIANTS variants: [(positions, colours, triangles)]."""
    return [strips(lo, hi, np.random.default_rng(SEED + 10 * part + v)) for v in range(VARIANTS)]


if __name__ == '__main__':
    lo, hi = (-6.97, -9.06, -1.0), (7.53, 9.43, 17.72)   # Luke's head box (luke_model.py, HEAD_SCALE), local units
    vs = variants(lo, hi, 0)
    for i, (p, c, t) in enumerate(vs):
        print(f'variant {i}: {len(p)} vertices, {len(t)} triangles, span {np.round(p.min(0), 2)} .. {np.round(p.max(0), 2)}')
    if '--sheet' in sys.argv:
        from PIL import Image, ImageDraw
        out = sys.argv[sys.argv.index('--sheet') + 1]
        S, im = 300, Image.new('RGB', (300 * VARIANTS, 600), (20, 20, 30))
        dr = ImageDraw.Draw(im)
        for i, (p, c, t) in enumerate(vs):
            for row, (ax, ay) in enumerate(((0, 1), (0, 2))):
                f = lambda q: (i * S + S / 2 + q[ax] * 10, row * S + S / 2 - q[ay] * 10 + (60 if ay == 2 else 0))
                for t3 in t:
                    dr.polygon([f(p[j]) for j in t3], fill=tuple(int(255 * x) for x in c[t3[1]][:3]))
        im.save(out); print('wrote', out)
