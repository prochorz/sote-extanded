"""Stage 1's collision for the Gall Run (gallrun.c fly()): the triangles of the canyon exactly as the image
draws them (stage 1's parts, gallrun/mesh_image.py: level units x 8 in s16), in world units (x SCALE, SCALE_Z),
each with the normal of its drawn (front) side; a grid of world cells listing the triangles over each.

    tris = extract(img, base, parts, plist)       # [(a, b, c)] level units
    blob = pack(tris, scale, scale_z, base_at)     # bytes for the image (layout below)
    edge = edge_nodes(T, N, nodes, w, h, drop)     # per route node: 1 where a flat ship does not fit

Layout (all big-endian): {tri count, tris, grid x0, y0 (float), cell (float), nx, ny, cells, list}, then the
tris (per triangle 12 s16: three vertices x, y, z in world units, then the unit normal of the drawn side x 32767), the
cells (nx*ny+1 u32: index of the cell's first entry in the list), the list (u16 triangle numbers).
"""
import struct, sys, os
import numpy as np


def tri_ids(w0, w1):
    """Vertex buffer indices of the triangles of one DL command (as stage1_geom.tri_ids; a copy: stage1_geom
    imports gall_asset, which imports this)."""
    op = w0 >> 24
    b = lambda w, s: ((w >> s) & 0xFF) // 5
    if op == 0xBF: return [[b(w1, 16), b(w1, 8), b(w1, 0)]]
    if op == 0xB1: return [[b(w0, 16), b(w0, 8), b(w0, 0)], [b(w1, 16), b(w1, 8), b(w1, 0)]]
    if op == 0xB5:
        q = [b(w1, s) for s in (24, 16, 8, 0)]
        return [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
    return []

CELL = 64.0          # world units
RIM_MIN = 80.0        # ceilings(): a ray whose highest rock is lower meets no wall
RIM_PCT = 25         # ceilings(): this percentile of the rims round a node (the very lowest: an opening, everywhere)


def extract(img, base, n, plist):
    R = lambda a: struct.unpack_from('>I', img, a - base)[0]
    out = []
    for i in range(n):
        p = R(plist + 4 * i)
        a, buf = R(p + 0x28), {}
        for _ in range(20000):
            w0, w1 = R(a), R(a + 4); op = w0 >> 24
            if op == 0xB8: break
            if op == 0x06:                       # a DL call (merged parts: geometry DLs one after the other)
                pass
            if op == 0x04:
                cnt, v0 = (w0 & 0xFFFF) >> 9, ((w0 >> 16) & 0xFF) // 2
                for j in range(cnt):
                    buf[v0 + j] = tuple(c / 8 for c in struct.unpack_from('>hhh', img, w1 + 16 * j - base))
            else:
                for ids in tri_ids(w0, w1):
                    vs = [buf.get(k) for k in ids]
                    if all(v is not None for v in vs): out.append(tuple(vs))
            a += 8
    return out


def world(tris, scale, scale_z):
    T = np.array(tris, np.float64) * np.array([scale, scale, scale_z])
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    l = np.linalg.norm(n, axis=1)
    keep = l > 1e-6
    return T[keep], n[keep] / l[keep, None]


def pack(T, N, base_at, flip=1):
    """T, N from world(); flip -1 if the drawn side is the other one. base_at: the address the blob goes to."""
    N = N * flip
    x0, y0 = float(np.floor(T[:, :, 0].min())), float(np.floor(T[:, :, 1].min()))
    nx = int((T[:, :, 0].max() - x0) // CELL) + 1; ny = int((T[:, :, 1].max() - y0) // CELL) + 1
    cells = [[] for _ in range(nx * ny)]
    for k, t in enumerate(T):
        i0, i1 = int((t[:, 0].min() - x0) // CELL), int((t[:, 0].max() - x0) // CELL)
        j0, j1 = int((t[:, 1].min() - y0) // CELL), int((t[:, 1].max() - y0) // CELL)
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1): cells[j * nx + i].append(k)
    assert len(T) < 65536
    hdr = 36
    tris = b''.join(struct.pack('>12h', *[int(round(v)) for v in t.flatten()], *[int(round(v * 32767)) for v in n])
                    for t, n in zip(T, N))
    starts, lst = [], []
    for c in cells: starts.append(len(lst)); lst += c
    starts.append(len(lst))
    a_tris = base_at + hdr
    a_cells = a_tris + len(tris)
    a_list = a_cells + 4 * len(starts)
    blob = struct.pack('>IIfffIIII', len(T), a_tris, x0, y0, CELL, nx, ny, a_cells, a_list) + tris
    blob += b''.join(struct.pack('>I', s) for s in starts) + b''.join(struct.pack('>H', k) for k in lst)
    return blob, dict(tris=len(T), nx=nx, ny=ny, entries=len(lst), bytes=len(blob))


def over(T, x, y):
    """Heights (world z) where the vertical line at x, y meets a triangle of T (world()); vertical ones never."""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    d00, d01, d10, d11 = b[:, 0] - a[:, 0], c[:, 0] - a[:, 0], b[:, 1] - a[:, 1], c[:, 1] - a[:, 1]
    det = d00 * d11 - d01 * d10; ok = np.abs(det) > 1e-9; dd = np.where(ok, det, 1)
    px, py = x - a[:, 0], y - a[:, 1]
    u = np.where(ok, (px * d11 - py * d01) / dd, -1); v = np.where(ok, (d00 * py - d10 * px) / dd, -1)
    m = (u >= 0) & (v >= 0) & (u + v <= 1)
    return np.sort(a[m, 2] + u[m] * (b[m, 2] - a[m, 2]) + v[m] * (c[m, 2] - a[m, 2]))


def ceilings(T, nodes, slit_nodes, top=165.0, low=60.0, eye=42.0, radius=160.0, slit_room=15.0):
    """Per route node the most the ship may fly over the route (world units): the lowest rim (the highest
    rock along a ray out to `radius`, rays to either side of the route's heading) less `eye` (the camera rides
    ~32 over the ship: it must not see over them); at least the slit wall + `slit_room` round a slit (flown over); within low..top, smoothed."""
    from scipy import ndimage
    cell = 6.0
    x0, y0 = T[:, :, 0].min(), T[:, :, 1].min()
    nx, ny = int((T[:, :, 0].max() - x0) / cell) + 2, int((T[:, :, 1].max() - y0) / cell) + 2
    H = np.full((nx, ny), -1e9)
    for a, b, c in T:
        l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)); n = max(2, int(l / (cell / 2)) + 1)
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij'); m = (i + j) <= n
        u, v = (i[m] / n)[:, None], (j[m] / n)[:, None]; p = a + (b - a) * u + (c - a) * v
        np.maximum.at(H, (((p[:, 0] - x0) / cell).astype(int), ((p[:, 1] - y0) / cell).astype(int)), p[:, 2])
    at = lambda x, y: H[int((x - x0) / cell), int((y - y0) / cell)] if 0 <= int((x - x0) / cell) < nx and 0 <= int((y - y0) / cell) < ny else -1e9
    out = []
    for k, (x, y, z) in enumerate(nodes):
        a_, b_ = nodes[max(k - 2, 0)], nodes[min(k + 2, len(nodes) - 1)]
        hd = np.arctan2(b_[1] - a_[1], b_[0] - a_[0])
        rims = []
        for da in np.radians(np.arange(35, 146, 15)):    # to either side, not along the canyon
            for sgn in (1, -1):
                dx, dy = np.cos(hd + sgn * da), np.sin(hd + sgn * da)
                rims.append(max(at(x + dx * d, y + dy * d) for d in np.arange(6, radius, 6)) - z)
        rims = [v for v in rims if v > RIM_MIN]           # (lower: no wall that way, open to more canyon or the floor)
        out.append(np.percentile(rims, RIM_PCT) - eye if rims else top)
    out = np.clip(np.array(out), low, top)
    for k in slit_nodes:                                  # a slit's wall: over it still
        x, y, z = nodes[k]; i, j = int((x - x0) / cell), int((y - y0) / cell)
        wall = H[i - 3:i + 4, j - 3:j + 4].max() - z
        out[max(k - 12, 0):k + 13] = np.maximum(out[max(k - 12, 0):k + 13], wall + slit_room)
    out = ndimage.grey_erosion(out, size=7)               # the lower of a few nodes either way, then eased
    return np.clip(ndimage.gaussian_filter1d(out, 2.0), low, top)


def edge_nodes(T, N, nodes, half_w, half_h, drop):
    """Per route node 1 where a flat ship does not fit (gallrun.c fly(): the slit pull, IMG_EDGE): a triangle
    (T, N from world(): N its drawn side) with the ship's point (the node, `drop` lower) on its drawn side
    cuts the node's cross-section (the vertical plane across the route's heading there) within `half_w`
    across and `half_h` up or down of that point; else 0."""
    out = np.zeros(len(nodes), np.uint8)
    lo, hi = T.min(1), T.max(1)
    for k, (x, y, z) in enumerate(nodes):
        a_, b_ = nodes[max(k - 2, 0)], nodes[min(k + 2, len(nodes) - 1)]
        d = np.array([b_[0] - a_[0], b_[1] - a_[1], 0.0]); d /= np.linalg.norm(d)
        r = np.array([d[1], -d[0], 0.0])
        P = np.array([x, y, z - drop])
        m = np.all((lo[:, :2] <= P[:2] + half_w) & (hi[:, :2] >= P[:2] - half_w), 1) \
            & (lo[:, 2] <= P[2] + half_h) & (hi[:, 2] >= P[2] - half_h) & (np.einsum('ij,ij->i', P - T[:, 0], N) > 0)
        for t in T[m]:
            al, ac, up = (t - P) @ d, (t - P) @ r, t[:, 2] - P[2]
            seg = []                                      # where the triangle's edges cross the plane
            for i, j in ((0, 1), (1, 2), (2, 0)):
                if (al[i] <= 0) != (al[j] <= 0):
                    f = al[i] / (al[i] - al[j])
                    seg.append((ac[i] + (ac[j] - ac[i]) * f, up[i] + (up[j] - up[i]) * f))
            if len(seg) < 2: continue
            (c0, h0), (c1, h1) = seg[:2]
            t0, t1 = 0.0, 1.0                             # the segment clipped to the box (Liang-Barsky)
            for p, q in ((-(c1 - c0), c0 + half_w), (c1 - c0, half_w - c0), (-(h1 - h0), h0 + half_h), (h1 - h0, half_h - h0)):
                if p == 0:
                    if q < 0: t0 = 2.0
                elif p < 0: t0 = max(t0, q / p)
                else: t1 = min(t1, q / p)
            if t0 <= t1:
                out[k] = 1; break
    return out

