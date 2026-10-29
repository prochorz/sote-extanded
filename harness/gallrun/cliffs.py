"""Both stages of the Gall Run as Gall's cliffs: the walls (stage 1: stage 1's source's rock, gallrun/layout.py's
layout; stage 2: stage 2's terrain over the source's track) stand as tall sheer rock faces that come up out of the haze and go up out of sight, as in Gall
(sub-level 14), with no floor and no sky: the old geometry only gives the walls' plan.

    plan = footprint(T, N, nodes, corridor, wide)   # which cells of a world grid are rock
    loops = outlines(plan)                       # its outlines, world xy, rock on the left
    quads = faces(loops, nodes)                  # the cliff faces: (4 vertices xyz, 4 uv, 4 rgb)
    one, two = by_stage(quads, at, ahead)           # stage 1's and stage 2's (stage 2's then moved into its frame)
    img, h = mesh(img, base, quads, Eg)          # appended to the image as parts (level units)
    tops = caps(plan, quads2, rail)              # stage 2's rock closed from above round the rail (render-only)

T, N: both stages' old triangles in world units (stage 2 turned and placed) and their drawn-side normals
(gallrun/collide.py world()), nodes: the whole route, wide: per node the least room either side (stage 1's
winding grooves). One plan for both stages, so the walls go on whole across the switch. The faces are flat-shaded like Gall's (a grey per face by its heading to the
light), drawn with Gall's rock texture (GALL_ROCK in states/gall_tp5.st) stretched up the face.
"""
import math, struct
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
import mesh_image

CELL = 3.0            # world units: the plan's grid
BAND = 25.0           # footprint(): rock this far over the route next to it is a wall
FLAT = 0.95           # ... unless a flat top (a cap over a groove)
CARVE = (10.0, 30.0)  # footprint(): the route's open strip, half width (the corridor's room, within these; 4 left
                      # slits 4-7 from the route on one side: the Falcon on edge, drawn onto the route, caught the lip;
                      # 8 still caught one where the route comes in at a slant; the Falcon flat is 30 wide)
WIDE = 100.0          # ... and at least this where the route winds (the S-shaped grooves: walls pushed apart, the user)
WIND = (0.6, 1.2)     # winding: the heading turns this much (radians) over +-8 nodes: from none to full WIDE
SIMPLIFY = 3.0        # outline points may be dropped this far off the line kept (world units)
SEG_MAX = 70.0        # no outline segment longer (world units): the faces' shades and tops vary along a wall
SMOOTH = 0.0          # footprint(): the rock's plan closed and opened by a disc this wide (world units), 0: not
                      # (18 with ISLAND 13500, SIMPLIFY 8, SEG_MAX 120 smoothed the map, 3915 faces -> ~1900, but the
                      # user saw more holes in the walls: rolled back, 2026-10-13)
SMOOTH_KEEP = 40.0    # ... but within this of the route it only takes rock away (the closing narrowed a slit
                      # 19 -> 10: the user)
MOUTH_REACH = 1.6     # discs: the route this far (share of the clearing's radius) from its middle has an open
MOUTH_R = 110.0       # strip this wide either side (a wide mouth into it: the end scene's ships flew into its
MOUTH_THIN = 15.0     # corners), and rock thinner than twice this there is cut (a wedge was left, the user)
ISLAND = 15000.0      # ... and rocks standing alone smaller than this (square world units) left out (pillars by the route: the narrow loops round them looked open, too tight to fly, the user)
OPEN_MAX = 200.0      # footprint(): no open air further than this off the route (the discs aside), but within
OPEN_START = 2500.0   # this of its first node (the opening shot's camera stands ~430 behind it and first looks
                      # back down the canyon: shut in rock, the walls round the fly-by were gone; at 700 a wall
                      # stood 270 in front of it, the user)
NECK = 40.0           # footprint(): open gaps narrower than twice this (off the route's strip) closed
DEEP = -1400.0        # the faces go down to this far under the route (into the haze)
TOP = (420.0, 820.0)  # their tops this far over the route (smooth noise along the wall between these)
TEX_S = 64 / 140.0    # texels a world unit along the wall (Gall's rock, 64 x 64)
TEX_T = 64 / 260.0    # texels a world unit up the face (stretched: Gall's own faces are)
LIGHT = (-0.55, 0.65, 0.52)   # where the light comes from (shades the faces)
SHADE = (95, 255)     # grey of a face turned away from it, full in it
DEEP_SHADE = 0.45     # a face's bottom this dark (the haze takes over)
CAP_R = 4000.0        # caps(): the rock closed from above within this of the rail's nodes (world units)
CAP_STEP = 250.0      # ... with points inside the rock this far apart (besides the faces' tops)
GALL_ROCK = 0x801E1B28        # Gall's tan rock (texture record, states/gall_tp5.st): its cliffs'
GALL_ROCK_PART = 0x801FCDC4   # a part of Gall's own cliffs (its material is copied)


def raster(T, cell, pad=200.0):
    """Per cell of a grid over T: the highest rock (H), the highest down-facing rock (Hd); -1e9 = none."""
    x0, y0 = T[:, :, 0].min() - pad, T[:, :, 1].min() - pad
    nx, ny = int((T[:, :, 0].max() + pad - x0) / cell) + 1, int((T[:, :, 1].max() + pad - y0) / cell) + 1
    return x0, y0, nx, ny


def footprint(T, N, nodes, corridor, wide, cell=CELL, discs=()):
    """{x0, y0, cell, rock (nx x ny bool), zr (route height next to each cell)}. A cell is rock if its highest
    rock stands more than BAND over the route next to it, but not under a cap: a flat top (normal up more than
    FLAT, drawn only from above) closing a groove over ground that is no higher than BAND over the route (the
    groove's floor: the canyon, flown under the cap). Rock with ground under it that is not flat on top (a
    ridge over the level's ground plane) stays rock; nor under an arch (rock facing down over that ground). No
    face (past the tiles) is rock too: the walls stand whole where the widened grooves reach a tile's edge. Along the route a strip as wide as its corridor (the room to either side, between
    CARVE) is open whatever (slits, the stone ring), and at least wide[k] (per node) to either side; so is each
    of `discs` (x, y, r, rough: a clearing, e.g. for Slave I's pad, its edge in and out by up to rough of r by
    bearing: smooth, as a natural hollow, not a circle)."""
    x0, y0, nx, ny = raster(T, cell)
    nodes = np.asarray(nodes)
    gx, gy = np.meshgrid(x0 + (np.arange(nx) + 0.5) * cell, y0 + (np.arange(ny) + 0.5) * cell, indexing='ij')
    dist, near = cKDTree(nodes[:, :2]).query(np.stack([gx.ravel(), gy.ravel()], 1))
    zr = nodes[near, 2].reshape(nx, ny)
    H = np.full((nx, ny), -1e9); Hd = np.full((nx, ny), -1e9); L = np.full((nx, ny), 1e9); top = np.zeros((nx, ny))
    samples = []
    for (a, b, c), n in zip(T, N):
        l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)); k = max(2, int(l / (cell / 2)) + 1)
        i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing='ij'); m = (i + j) <= k
        u, v = (i[m] / k)[:, None], (j[m] / k)[:, None]; p = a + (b - a) * u + (c - a) * v
        at = (((p[:, 0] - x0) / cell).astype(int), ((p[:, 1] - y0) / cell).astype(int))
        if n[2] < -0.3:
            np.maximum.at(Hd, at, p[:, 2]); continue
        np.maximum.at(H, at, p[:, 2])
        if n[2] > 0.3: np.minimum.at(L, at, p[:, 2])
        samples.append((at, p[:, 2], n[2]))
    for at, z, nz in samples:                       # the normal of the highest face in each cell
        hit = z >= H[at] - 1e-6
        top[at[0][hit], at[1][hit]] = nz
    cap = (L < zr + BAND) & ((top > FLAT) | (Hd > zr + BAND))
    rock = ((H > zr + BAND) | (H < -1e8)) & ~cap      # (no face: past the level's tiles, rock too)
    rock = np.pad(rock, 2, constant_values=True)        # (off the grid: rock, so the edge is not eaten away)
    rock = ndimage.binary_opening(ndimage.binary_closing(rock, iterations=1), iterations=1)[2:-2, 2:-2]   # specks, seams
    rock |= H < -1e8
    r = max(int(round(SMOOTH / cell)), 1); disc = np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r + 0.3
    g = np.pad(rock, r + 1, constant_values=True)       # (off the grid: rock)
    smooth = ndimage.binary_opening(ndimage.binary_closing(g, disc), disc)[r + 1:-r - 1, r + 1:-r - 1]
    keep = dist.reshape(nx, ny) < SMOOTH_KEEP           # (by the route no rock added: the slits stay as wide)
    if SMOOTH > 0: rock = np.where(keep, smooth & rock, smooth)
    if NECK > 0:                                        # narrow necks and slivers of open air off the route: rock (the
        r = int(round(NECK / cell)); disc = np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r + 0.3   # user: a gap seen
        g = np.pad(rock, r + 1, constant_values=True)   # through, but walls too close for the ship: "gaps you can't
        rock = ndimage.binary_closing(g, disc)[r + 1:-r - 1, r + 1:-r - 1]   # fly"; only rock added: the route's
    for k in range(len(nodes) - 1):                    # the route's strip (slits) is carved after
        r = max(float(np.clip(min(corridor[k][0], corridor[k][1]), *CARVE)), float(wide[k]))
        a, b = nodes[k, :2], nodes[k + 1, :2]
        for t in np.linspace(0, 1, max(2, int(np.hypot(*(b - a)) / cell) + 1)):
            x, y = a + (b - a) * t
            i0, i1 = int((x - r - x0) / cell), int((x + r - x0) / cell) + 1
            j0, j1 = int((y - r - y0) / cell), int((y + r - y0) / cell) + 1
            ci, cj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing='ij')
            inside = np.hypot(x0 + (ci + 0.5) * cell - x, y0 + (cj + 0.5) * cell - y) <= r
            rock[ci[inside], cj[inside]] = False
    if OPEN_MAX > 0:                                    # open air further off the route than the ship may go (gallrun.c
        rock |= (dist.reshape(nx, ny) > OPEN_MAX) & (np.hypot(gx - nodes[0, 0], gy - nodes[0, 1]) > OPEN_START)   # FLY_LEASH): rock (the user: gaps seen, side pockets and loops
                                                        # round pillars, the Falcon could not get to: walls or the leash)
    lab, _ = ndimage.label(~rock)                       # open pockets cut off from the route: rock
    seeds = {lab[int((x - x0) / cell), int((y - y0) / cell)] for x, y, _ in nodes} - {0}
    rock = ~np.isin(lab, list(seeds))
    lab, _ = ndimage.label(rock); size = np.bincount(lab.ravel()) * cell * cell   # small rocks on their own: out
    if ISLAND > 0: rock &= ~(np.isin(lab, np.nonzero(size < ISLAND)[0]) & (lab > 0))
    gx0, gy0 = x0 + (np.arange(rock.shape[0]) + 0.5) * cell, y0 + (np.arange(rock.shape[1]) + 0.5) * cell
    for x, y, r, rough in discs:                        # (after the pockets: a clearing may stand on its own)
        dx, dy = np.meshgrid(gx0 - x, gy0 - y, indexing='ij'); a = np.arctan2(dy, dx)
        rng = np.random.default_rng(int(x * 7 + y) % 2 ** 31)   # (its bearings' noise: a few slow waves)
        w = sum(rng.uniform(0.5, 1) / k * np.cos(k * a + rng.uniform(0, 2 * np.pi)) for k in range(2, 7))
        rock &= np.hypot(dx, dy) > r * (1 + rough * w / 1.45)
        for q in nodes[np.hypot(nodes[:, 0] - x, nodes[:, 1] - y) < r * MOUTH_REACH]:   # the route into it: a wide
            rock &= np.hypot(*np.meshgrid(gx0 - q[0], gy0 - q[1], indexing='ij')) > MOUTH_R   # mouth
        near = np.hypot(dx, dy) < r * MOUTH_REACH                    # thin wedges left between it and the route's
        k = int(round(MOUTH_THIN / cell)); disc_ = np.hypot(*np.mgrid[-k:k + 1, -k:k + 1]) <= k + 0.3   # strip: out
        rock = np.where(near, ndimage.binary_opening(np.pad(rock, k + 1, constant_values=True), disc_)[k + 1:-k - 1, k + 1:-k - 1], rock)
    return dict(x0=x0, y0=y0, cell=cell, rock=rock, zr=zr, H=H, L=L, top=top)


def by_stage(quads, at, ahead, both=40.0):
    """The faces before and after the plane at `at` facing `ahead` (the switch): stage 1's, stage 2's. Faces within
    `both` of it go to both (the two stages' vertices are rounded apart: no crack where they meet)."""
    d = [float((np.mean([v[:2] for v in vs], 0) - at) @ ahead) for vs, _, _ in quads]
    return [q for q, x in zip(quads, d) if x < both], [q for q, x in zip(quads, d) if x > -both]


def winding(nodes):
    """Per route node 0..1: how much the route winds round it (the S-shaped grooves), eased in and out."""
    P = np.asarray(nodes)[:, :2]; n = len(P)
    h = np.unwrap(np.arctan2(*np.gradient(P, axis=0)[:, ::-1].T))
    i = np.arange(n)
    turn = np.abs(h[np.minimum(i + 8, n - 1)] - h[np.maximum(i - 8, 0)])
    turn = ndimage.maximum_filter1d(turn, 25)
    return ndimage.uniform_filter1d(np.clip((turn - WIND[0]) / (WIND[1] - WIND[0]), 0, 1), 15)


def outlines(fp, simplify=SIMPLIFY, seg_max=SEG_MAX):
    """Closed outlines of the rock (marching squares on the cell centres), world xy, each a list of points
    going round with the rock on the left (so a face from p[k] to p[k+1] faces right: out of the rock)."""
    rock, x0, y0, cell = fp['rock'], fp['x0'], fp['y0'], fp['cell']
    g = np.pad(rock, 1, constant_values=True).astype(np.uint8)   # off the grid: rock
    nx, ny = g.shape
    # edges between corners: a point on the edge of square (i, j) (corners (i, j)..(i+1, j+1));
    # each square's segments go with the rock on the left (x right, y up).
    E = {}
    def mid(a, b): return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    for i in range(nx - 1):
        col = g[i], g[i + 1]
        for j in range(ny - 1):
            c = (col[0][j], col[1][j], col[1][j + 1], col[0][j + 1])   # (i,j) (i+1,j) (i+1,j+1) (i,j+1): CCW
            s = c[0] | c[1] << 1 | c[2] << 2 | c[3] << 3
            if s in (0, 15): continue
            P = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            e = [mid(P[0], P[1]), mid(P[1], P[2]), mid(P[2], P[3]), mid(P[3], P[0])]   # bottom, right, top, left
            # (a, b): the outline goes from edge b's point to edge a's (rock on the left); 5 and 10: the two rock corners joined
            segs = {1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)], 5: [(3, 2), (1, 0)], 6: [(0, 2)], 7: [(3, 2)],
                    8: [(2, 3)], 9: [(2, 0)], 10: [(0, 3), (2, 1)], 11: [(2, 1)], 12: [(1, 3)], 13: [(1, 0)], 14: [(0, 3)]}[s]
            for a, b in segs: E[e[b]] = e[a]
    loops = []
    while E:
        p0, p = next(iter(E.items()))
        loop = [p0]; del E[p0]
        while p != p0:
            loop.append(p); p = E.pop(p)
        if len(loop) < 8: continue
        w = np.array([(x0 + (u - 1 + 0.5) * cell, y0 + (v - 1 + 0.5) * cell) for u, v in loop])
        w = dp_loop(w, simplify)
        loops.append(split(w, seg_max))
    return loops


def dp(P, eps):
    """Douglas-Peucker on an open polyline."""
    if len(P) < 3: return list(P)
    a, b = P[0], P[-1]; d = b - a; L = np.hypot(*d)
    r = P[1:-1] - a
    dist = np.abs(d[0] * r[:, 1] - d[1] * r[:, 0]) / L if L > 1e-9 else np.hypot(r[:, 0], r[:, 1])
    k = int(np.argmax(dist))
    if dist[k] <= eps: return [a, b]
    return dp(P[:k + 2], eps)[:-1] + dp(P[k + 1:], eps)


def dp_loop(P, eps):
    far = int(np.argmax(np.hypot(*(P - P[0]).T)))
    a = dp(P[:far + 1], eps); b = dp(np.vstack([P[far:], P[:1]]), eps)
    return np.array(a[:-1] + b[:-1])


def split(P, seg_max):
    out = []
    for k in range(len(P)):
        a, b = P[k], P[(k + 1) % len(P)]
        n = max(1, int(math.ceil(np.hypot(*(b - a)) / seg_max)))
        out += [a + (b - a) * t / n for t in range(n)]
    return np.array(out)


def noise1(s, seed, scale):
    """Smooth noise in 0..1 along a wall (s: distance along it)."""
    rng = np.random.default_rng(seed)
    k = np.arange(1, 6); f = rng.uniform(0.5, 1.5, 5) * k / scale; ph = rng.uniform(0, 2 * np.pi, 5); w = 1 / k
    v = (np.sin(np.outer(s, f) + ph) * w).sum(1) / w.sum()
    return 0.5 + 0.5 * v


def noise2(xy, seed, scale):
    """Smooth noise in 0..1 by place (xy: world points, n x 2): noise1()'s waves, each along its own heading."""
    rng = np.random.default_rng(seed)
    k = np.arange(1, 6); f = rng.uniform(0.5, 1.5, 5) * k / scale; ph = rng.uniform(0, 2 * np.pi, 5); w = 1 / k
    a = rng.uniform(0, 2 * np.pi, 5); u = np.stack([np.cos(a), np.sin(a)], 1) * f[:, None]
    v = (np.sin(np.asarray(xy, float) @ u.T + ph) * w).sum(1) / w.sum()
    return 0.5 + 0.5 * v


def faces(loops, nodes, seed=1, old=None):
    """One quad a segment, from deep in the haze to its top, shaded by its heading (darker down): [(xyz x4, st x4
    texels, rgb x4)].
    Corners in order a-bottom, b-bottom, b-top, a-top: counter-clockwise seen from the canyon.
    old (faces() of another plan, e.g. with a hollow more): a top whose (x, y) is a top corner there
    keeps that height, a face whose two ends are a face there keeps its shade and texture s; the rest take a noise by
    their place (noise2(), the same amplitude) and a shade by their place, not by the order along the outline."""
    nodes = np.asarray(nodes); tree = cKDTree(nodes[:, :2])
    L = np.array(LIGHT) / np.linalg.norm(LIGHT)
    out = []
    if old is not None:
        old_top = {}; old_face = {}
        for vs, st, cs in old:
            old_top[vs[3][:2]] = vs[3][2]; old_top[vs[2][:2]] = vs[2][2]
            old_face[(vs[0][:2], vs[1][:2])] = (st[0][0], st[1][0], cs)
        kept = [0, 0, 0]
    for li, P in enumerate(loops):
        n = len(P)
        seg = np.hypot(*(np.roll(P, -1, 0) - P).T); s = np.concatenate([[0], np.cumsum(seg)])
        _, near = tree.query(P); zr = nodes[near, 2]
        zr = ndimage.uniform_filter1d(zr, 9, mode='wrap')
        if old is None:
            top = zr + TOP[0] + (TOP[1] - TOP[0]) * noise1(s[:n], seed + li, 260.0) ** 1.5
            rng = np.random.default_rng(seed * 1000 + li)
        else:
            top = zr + TOP[0] + (TOP[1] - TOP[0]) * noise2(P, seed, 260.0) ** 1.5
            for k in range(n):
                z = old_top.get((P[k][0], P[k][1]))
                if z is not None: top[k] = z; kept[0] += 1
        for k in range(n):
            k1 = (k + 1) % n
            a, b = P[k], P[k1]
            d = b - a; ln = np.hypot(*d)
            if ln < 1e-6: continue
            nrm = np.array([d[1], -d[0], 0]) / ln          # out of the rock (it is on the left)
            lit = max(0.0, float(nrm @ L)) / math.hypot(L[0], L[1])
            g = SHADE[0] + (SHADE[1] - SHADE[0]) * lit
            if old is None: rng_k = rng
            else: rng_k = np.random.default_rng([int(round(a[0] * 16)) % 2 ** 31, int(round(a[1] * 16)) % 2 ** 31])
            g = min(255, max(0, g * rng_k.uniform(0.88, 1.08)))
            s0 = s[k] * TEX_S; s0 -= 64 * math.floor(s0 / 64); s1 = s0 + ln * TEX_S
            cs = [(int(c),) * 3 for c in (g * DEEP_SHADE, g * DEEP_SHADE, g, g)]
            if old is not None:
                f = old_face.get(((a[0], a[1]), (b[0], b[1])))
                if f is not None: s0, s1, cs = f; kept[1] += 1
                else: kept[2] += 1
            zb, zt = (zr[k] + DEEP, zr[k1] + DEEP), (top[k], top[k1])
            tm = 64 * round(((zb[0] + zt[0]) / 2) * TEX_T / 64)
            vs = [(a[0], a[1], zb[0]), (b[0], b[1], zb[1]), (b[0], b[1], zt[1]), (a[0], a[1], zt[0])]
            st = [(s0, tm - zb[0] * TEX_T), (s1, tm - zb[1] * TEX_T), (s1, tm - zt[1] * TEX_T), (s0, tm - zt[0] * TEX_T)]
            out.append((vs, st, cs))
    if old is not None:
        print(f'cliff faces (D9): {kept[0]} tops and {kept[1]} faces as the old plan\'s, {kept[2]} faces new')
    return out


def caps(fp, quads, rail, seed=2, old=None):
    """The rock closed from above (the user, 2026-10-14: on the rail up out of the canyon the walls stood edge-on with
    no tops) within CAP_R of the rail's nodes: a surface over the faces' top corners (their own heights) and points
    CAP_STEP apart inside the rock (heights from the 6 nearest corners, inverse-distance-weighted), triangulated; a
    triangle kept when its middle is rock in the plan. Flat-shaded by LIGHT, facing up; as faces()'s quads (each
    triangle a quad with its last corner twice). Render-only (not in the collision).
    old (caps() of another plan, e.g. with a hollow more): a triangle whose three corners' (x, y) are
    a triangle's there keeps its shade; the rest take a shade by their place (the same spread), not by Delaunay's
    order."""
    from scipy.spatial import Delaunay
    rock, x0, y0, cell = fp['rock'], fp['x0'], fp['y0'], fp['cell']
    R = np.asarray(rail, float)[:, :2]
    def is_rock(xy):
        i, j = ((xy[:, 0] - x0) / cell).astype(int), ((xy[:, 1] - y0) / cell).astype(int)
        ok = (i >= 0) & (i < rock.shape[0]) & (j >= 0) & (j < rock.shape[1])
        out = np.zeros(len(xy), bool); out[ok] = rock[i[ok], j[ok]]
        return out
    tops = np.array([v for vs, _, _ in quads for v in (vs[2], vs[3])])
    tops = np.unique(np.round(tops, 2), axis=0)
    near = cKDTree(R).query(tops[:, :2])[0] < CAP_R + CAP_STEP
    tops = tops[near]
    gx, gy = np.meshgrid(np.arange(R[:, 0].min() - CAP_R, R[:, 0].max() + CAP_R, CAP_STEP),
                         np.arange(R[:, 1].min() - CAP_R, R[:, 1].max() + CAP_R, CAP_STEP), indexing='ij')
    G = np.stack([gx.ravel(), gy.ravel()], 1)
    G = np.clip(G, [x0 + cell, y0 + cell], [x0 + (rock.shape[0] - 1) * cell, y0 + (rock.shape[1] - 1) * cell])   # (out to
    G = np.unique(G[is_rock(G) & (cKDTree(R).query(G)[0] < CAP_R)], axis=0)   # the plan's edge: no faces there)
    tt = cKDTree(tops[:, :2]); d, k = tt.query(G, 6); w = 1 / np.maximum(d, 1e-3) ** 2
    gz = (tops[k, 2] * w).sum(1) / w.sum(1)
    P = np.concatenate([tops, np.column_stack([G, gz])])
    tri = Delaunay(P[:, :2]).simplices
    keep = is_rock(P[tri, :2].mean(1)) & (cKDTree(R).query(P[tri, :2].mean(1))[0] < CAP_R)
    L = np.array(LIGHT) / np.linalg.norm(LIGHT)
    rng = np.random.default_rng(seed)
    out = []
    tkey = lambda vs: tuple(sorted((round(float(v[0]), 2), round(float(v[1]), 2)) for v in vs[:3]))
    if old is not None:
        old_cs = {tkey(vs): cs for vs, _, cs in old}; kept = [0, 0]
    for t in tri[keep]:
        a, b, c = P[t]
        nrm = np.cross(b - a, c - a)
        if nrm[2] < 0: b, c = c, b; nrm = -nrm                 # (counter-clockwise from above: facing up)
        nrm /= np.linalg.norm(nrm)
        g = SHADE[0] + (SHADE[1] - SHADE[0]) * max(0.0, float(nrm @ L))
        vs = [tuple(a), tuple(b), tuple(c), tuple(c)]
        if old is None:
            cs = [(int(min(255, max(0, g * rng.uniform(0.88, 1.08)))),) * 3] * 4
        else:
            cs = old_cs.get(tkey(vs))
            if cs is not None: kept[0] += 1
            else:
                m = (a + b + c) / 3
                r = np.random.default_rng([int(round(m[0] * 16)) % 2 ** 31, int(round(m[1] * 16)) % 2 ** 31])
                cs = [(int(min(255, max(0, g * r.uniform(0.88, 1.08)))),) * 3] * 4; kept[1] += 1
        st = [(v[0] * TEX_S, v[1] * TEX_S) for v in vs]
        s0, t0 = 64 * math.floor(min(q[0] for q in st) / 64), 64 * math.floor(min(q[1] for q in st) / 64)
        out.append((vs, [(x - s0, y - t0) for x, y in st], cs))
    if old is not None:
        print(f'wall tops (D11): {kept[0]} triangles shaded as the old plan\'s, {kept[1]} new')
    return out


def tris(quads):
    """The faces as triangles (world), for the collision: [(a, b, c)] counter-clockwise from the drawn side."""
    out = []
    for vs, _, _ in quads:
        out += [(vs[0], vs[1], vs[2]), (vs[0], vs[2], vs[3])]
    return np.array(out, np.float64)


def mesh(img, base, quads, Eg, scale, scale_z, per_part=48, nocull=1e5):
    """Append the faces to the image (bytearray at base) as parts drawn with Gall's rock: vertices in level
    units x 8 (the stage's node scales them by scale, scale_z), texture coordinates s10.5 (the texture DL
    halves them: G_TEXTURE 0.5), up to per_part quads a part. Returns {parts, list, box, lo, hi}."""
    R = lambda a: struct.unpack_from('>I', Eg, a & 0x7FFFFF)[0]

    def alloc(b):
        img.extend(bytes(-len(img) % 16)); a = base + len(img); img.extend(b); return a

    def dl_end(a):
        while R(a) >> 24 != 0xB8: a += 8
        return a + 8
    tr = GALL_ROCK
    d, blk = R(tr + 8), R(tr + 0xC)
    reg = mesh_image.TEX_SHARE; key = mesh_image.tex_key(Eg, tr)   # (one copy of Gall's rock in the image:
    if reg is not None and key in reg: at = reg[key]               # mesh_image TEX_SHARE)
    else:
        at = alloc(Eg[blk & 0x7FFFFF:dl_end(d) & 0x7FFFFF])          # palette, texels, texture DL
        for a in range(at + d - blk, at + dl_end(d) - blk, 8):
            if struct.unpack_from('>I', img, a - base)[0] == 0xBC001006:
                struct.pack_into('>I', img, a + 4 - base, (struct.unpack_from(">I", img, a + 4 - base)[0] + at - blk) & 0xFFFFFFFF)
        if reg is not None: reg[key] = at
    rec = bytearray(Eg[tr & 0x7FFFFF:(tr & 0x7FFFFF) + 16]); struct.pack_into('>II', rec, 8, at + d - blk, at)
    texrec = alloc(rec)
    m = R(GALL_ROCK_PART + 0x24)
    mat = bytearray(Eg[m & 0x7FFFFF:(m & 0x7FFFFF) + 12]); struct.pack_into('>I', mat, 8, texrec)
    mat = alloc(mat)
    s16 = lambda v: max(-32768, min(32767, int(round(v))))
    parts = []
    for p0 in range(0, len(quads), per_part):
        grp = quads[p0:p0 + per_part]
        vtx = b''; dl = b''
        for q in range(0, len(grp), 4):                 # 4 quads (16 vertices) a load
            four = grp[q:q + 4]
            dl += struct.pack('>II', 0x04000000 | (len(four) * 4 << 9) | (len(four) * 64 - 1), len(vtx))   # address fixed below
            for vs, st, cs in four:
                for (x, y, z), (s_, t_), (r, g, b) in zip(vs, st, cs):
                    vtx += struct.pack('>hhhHhhBBBB', s16(x / scale * 8), s16(y / scale * 8), s16(z / scale_z * 8), 0,
                                       s16(s_ * 64), s16(t_ * 64), r, g, b, 255)
            for k in range(len(four)):
                i = [4 * k + j for j in range(4)]
                dl += struct.pack('>II', 0xB5000000, (i[0] * 5) << 24 | (i[1] * 5) << 16 | (i[2] * 5) << 8 | (i[3] * 5))
        dl += struct.pack('>II', 0xB8000000, 0)
        va = alloc(vtx); dl = bytearray(dl)
        for o in range(0, len(dl), 8):
            if dl[o] == 0x04: struct.pack_into('>I', dl, o + 4, va + struct.unpack_from('>I', dl, o + 4)[0])
        da = alloc(bytes(dl))
        rec = bytearray(Eg[GALL_ROCK_PART & 0x7FFFFF:(GALL_ROCK_PART & 0x7FFFFF) + 0x2C])
        struct.pack_into('>6f', rec, 0, *(-nocull,) * 3, *(nocull,) * 3)
        struct.pack_into('>IIII', rec, 0x1C, 0, 0, mat, da)
        parts.append(alloc(rec))
    lst = alloc(b''.join(struct.pack('>I', p) for p in parts))
    V = np.array([v for vs, _, _ in quads for v in vs])
    lo, hi = list(V.min(0) / [scale, scale, scale_z]), list(V.max(0) / [scale, scale, scale_z])
    bb = b''.join(struct.pack('>hhhhhhhh', s16(x * 8), s16(y * 8), s16(z * 8), 0, 0, 0, 0, 0)
                  for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2]))
    return dict(parts=len(parts), list=lst, box=alloc(bb), lo=lo, hi=hi)
