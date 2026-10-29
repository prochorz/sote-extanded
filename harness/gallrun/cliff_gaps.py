"""Holes in the Gall Run's cliffs (gallrun/cliffs.py): from route nodes, rays to the sides (SIDE degrees off the
heading) at the ship's height; a ray that meets no cliff face (from its drawn side: the back of a face is not
drawn) within REACH world units looks out through the rock into the haze.

    cd harness && .venv/bin/python3 gallrun/cliff_gaps.py [image] [out.png]

Faces are read from the image as the game draws them (both stages' parts, stage 2 turned and placed by its
pose). Prints the holes per stretch of nodes and draws them on a map (faces grey, holes red)."""
import math, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from m64 import HERE
import paths
import collide

BASE = 0x80628000
REACH = float(os.environ.get("REACH", 3000))
SIDE = range(int(os.environ.get("SIDE0", 40)), 181 - int(os.environ.get("SIDE0", 40)), 10)
EYE = 30.0
STEP = 2


def walls(T):
    """A part made of faces()'s wall quads only (stage 2's list also holds the pad, the hangar and the wall tops)."""
    if len(T) == 0 or len(T) % 2: return False
    Q0, Q1 = T[0::2], T[1::2]
    return (np.allclose(Q1[:, 0], Q0[:, 0]) and np.allclose(Q1[:, 1], Q0[:, 2])
            and np.allclose(Q0[:, 1, :2], Q0[:, 2, :2]) and np.allclose(Q0[:, 0, :2], Q1[:, 2, :2]))


def faces(img):
    h = struct.unpack_from('>4sIIIIIfIfIIIIfffffIfIIIIIIIII', img, 0)
    sc, scz, n2, l2, sw, c, s, tx, ty, tz, k2 = h[6], h[8], h[9], h[10], h[12], h[13], h[14], h[15], h[16], h[17], h[19]
    T1 = np.array(collide.extract(img, BASE, h[1], h[2])) * [sc, sc, scz]
    T2 = np.concatenate([q for q in (np.array(collide.extract(img, BASE, 1, l2 + 4 * i)).reshape(-1, 3, 3)
                                     for i in range(n2)) if walls(q)]) * [sc * k2, sc * k2, scz * k2]
    x, y = T2[..., 0].copy(), T2[..., 1].copy()
    T2[..., 0], T2[..., 1], T2[..., 2] = c * x - s * y + tx, s * x + c * y + ty, T2[..., 2] + tz
    rt = h[5]
    nodes = np.array([struct.unpack_from('>3f', img, rt - BASE + i * 0x54 + 0x38) for i in range(h[7])])
    return np.concatenate([T1, T2]), nodes, sw


def segments(T):
    """The quads (two triangles each, in order: a-bottom b-bottom b-top, a-bottom b-top a-top): the segment
    a->b, the z span both ends cover, its normal (out of the rock)."""
    Q0, Q1 = T[0::2], T[1::2]
    a, b, bt, at = Q0[:, 0], Q0[:, 1], Q0[:, 2], Q1[:, 2]
    assert np.allclose(Q1[:, 0], a) and np.allclose(Q1[:, 1], bt), 'not quads'
    d = b[:, :2] - a[:, :2]; L = np.hypot(*d.T)
    n = np.stack([d[:, 1], -d[:, 0]], 1) / L[:, None]
    return a[:, :2], b[:, :2], np.maximum(a[:, 2], b[:, 2]), np.minimum(at[:, 2], bt[:, 2]), n


def main():
    img = open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(paths.GAME, 'gall_run.bin'), 'rb').read()
    T, nodes, sw = faces(img)
    A, B, zlo, zhi, N = segments(T)
    print(f'{len(A)} faces, {len(nodes)} nodes')
    holes = []
    for k in range(2, len(nodes) - 6, STEP):
        p = nodes[k]; hd = nodes[min(k + 2, len(nodes) - 1)][:2] - nodes[max(k - 2, 0)][:2]
        h = math.atan2(hd[1], hd[0]); z = p[2] + EYE
        for sgn in (1, -1):
            for deg in SIDE:
                a_ = h + sgn * math.radians(deg); d = np.array([math.cos(a_), math.sin(a_)])
                e = B - A; w = A - p[:2]
                den = d[0] * e[:, 1] - d[1] * e[:, 0]
                with np.errstate(divide='ignore', invalid='ignore'):
                    tr = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / den      # along the ray
                    u = (w[:, 0] * d[1] - w[:, 1] * d[0]) / den             # along the face
                front = N @ d < 0
                hit = front & (tr > 0) & (tr < REACH) & (u >= 0) & (u <= 1) & (zlo <= z) & (zhi >= z)
                if not hit.any(): holes.append((k, sgn * deg, p[0], p[1], a_))
    ks = sorted({x[0] for x in holes})
    print(f'{len(holes)} rays out through the rock, at {len(ks)} of {len(range(2, len(nodes) - 6, STEP))} nodes')
    if ks:
        grp = np.split(np.array(ks), np.where(np.diff(ks) > STEP)[0] + 1)
        for g in grp:
            n_ = sum(1 for x in holes if g[0] <= x[0] <= g[-1])
            print(f'  nodes {g[0]}-{g[-1]} ({"stage 1" if g[0] < sw else "stage 2"}): {n_} rays')
    if len(sys.argv) > 2:
        from PIL import Image, ImageDraw
        x0, y0 = min(A[:, 0].min(), nodes[:, 0].min()) - 300, min(A[:, 1].min(), nodes[:, 1].min()) - 300
        x1, y1 = max(A[:, 0].max(), nodes[:, 0].max()) + 300, max(A[:, 1].max(), nodes[:, 1].max()) + 300
        sc = 1400 / max(x1 - x0, y1 - y0)
        im = Image.new('RGB', (int((x1 - x0) * sc), int((y1 - y0) * sc)), (0, 0, 0)); dr = ImageDraw.Draw(im)
        f = lambda x, y: ((x - x0) * sc, (y1 - y) * sc)
        for a, b in zip(A, B): dr.line([f(*a), f(*b)], fill=(150, 150, 150))
        dr.line([f(x, y) for x, y, _ in nodes], fill=(0, 160, 255))
        for k, _, x, y, a_ in holes:
            dr.line([f(x, y), f(x + math.cos(a_) * REACH, y + math.sin(a_) * REACH)], fill=(255, 0, 0))
        im.save(sys.argv[2])


if __name__ == '__main__':
    main()
