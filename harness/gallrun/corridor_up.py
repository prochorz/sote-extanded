"""Stage 1's corridor "up" (the image's table, IMG_CORRIDOR [3]: room over the route, read by gall_story.c outrider()'s
height clamp and gall_cam.c's eye) against the drawn rock (IMG_COLL, the image's stage-1 triangles): per node whose up is
<= 5 units, the rock on the vertical line over the route there (non-vertical triangles: an arch or a low bridge would be
one). A 0 with no rock over it is a fault of the table, not an arch.

    .venv/bin/python3 gallrun/corridor_up.py [image, default local/game/gall_run.bin]
"""
import struct, sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import paths
img = open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(paths.GAME, 'gall_run.bin'), 'rb').read()
B = 0x80628000                                       # GALL_VRAM
R = lambda a: struct.unpack_from('>I', img, a - B)[0]
F = lambda a: struct.unpack_from('>f', img, a - B)[0]
route, cor, sw, coll = R(B + 20), R(B + 72), R(B + 48), R(B + 108)   # route, IMG_CORRIDOR, IMG_SWITCH, IMG_COLL
pos = lambda k: [F(route + 0x38 + k * 0x54 + 4 * i) for i in range(3)]
C = lambda k, i: struct.unpack_from('>h', img, cor + k * 8 + 2 * i - B)[0]
n, a_tris, *_ = struct.unpack_from('>IIfffIIII', img, coll - B)
T = np.array(struct.unpack_from('>%dh' % (12 * n), img, a_tris - B), float).reshape(n, 12)
V = T[:, :9].reshape(n, 3, 3)


def over(x, y, z):
    """heights (over the route's z) where the vertical line at x, y meets a triangle"""
    a, b, c = V[:, 0], V[:, 1], V[:, 2]
    d00, d01, d10, d11 = b[:, 0] - a[:, 0], c[:, 0] - a[:, 0], b[:, 1] - a[:, 1], c[:, 1] - a[:, 1]
    det = d00 * d11 - d01 * d10; ok = np.abs(det) > 1e-9; dd = np.where(ok, det, 1)
    px, py = x - a[:, 0], y - a[:, 1]
    u = np.where(ok, (px * d11 - py * d01) / dd, -1); v = np.where(ok, (d00 * py - d10 * px) / dd, -1)
    m = (u >= 0) & (v >= 0) & (u + v <= 1)
    return sorted(np.round(a[m, 2] + u[m] * (b[m, 2] - a[m, 2]) + v[m] * (c[m, 2] - a[m, 2]) - z, 1))


low = [k for k in range(sw) if C(k, 3) <= 5]
lone = [k for k in low if 0 < k < sw - 1 and C(k - 1, 3) > 60 and C(k + 1, 3) > 60]
anyrock = [k for k in range(sw) if over(*pos(k))]
print(f'stage 1: {sw} nodes; up <= 5: {len(low)} ({len(lone)} lone between nodes over 60); nodes with rock over the '
      f'route at all: {len(anyrock)}')
for k in low:
    o = over(*pos(k))
    print(f'  node {k}: up {[C(k + d, 3) for d in (-1, 0, 1)]}  rock over the route: {o if o else "none"}')
