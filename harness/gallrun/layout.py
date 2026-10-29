"""Stage 1's tiles rearranged (the user's edit, 2026-10-09): the stone ring tile moved, two pieces of the canyon
copied into its place. Applied to the tiles (gall_asset.py: what the image draws, and so the collision) and
to stage 1's route from gallrun/stage1_route.py (its nodes, corridor, floor and bottom per node, cut by tile).

Tiles are named by their centre in level units (100 x 100). The route goes, by tile: the start S, the ring R
(1700,-100), N from (1700,0) to (1500,100), the tail T from (1500,0) on. New order along the route (all tiles
keep their own turn):
  S | piece 1: (1300,200), (1300,300) at (1700,-100), (1700,0), mirrored east-west (flown north: its route
  reversed; mirrored so its walls meet its neighbours', seams.py) |
  piece 2: (1700,500), (1700,600) at (1700,100), (1700,200) | N moved up 300 | R at (1500,300) (flown south:
  reversed) | T moved up 200.
"""
import numpy as np
from scipy import ndimage

SCALE = 6.0
RING = (1700, -100)
PIECES = [((1300, 200), (1700, -100), True), ((1300, 300), (1700, 0), True), ((1700, 500), (1700, 100), False),
          ((1700, 600), (1700, 200), False)]   # (source, place, mirrored east-west: piece 1, its walls then meet
                                               # the start's and piece 2's, seams.py: was a crack the user saw)
RING_TO = (1500, 300)
N_UP, T_UP = 300, 200
S_TILES = {(1700, -300), (1700, -200), (1700, -400), (1700, -500), (1700, -600)}
T_FROM = (1500, 0)                     # the first tile of the tail along the route
JOIN = 8                               # nodes smoothed on each side of a join
WALL_UP = 1.5                          # stage 1 drawn this much taller (its rock, the route's height, the corridor):
                                       # the walls higher, so the Falcon cannot look over them (the user)


def tile_of(x, y):
    return int(round(x / 100)) * 100, int(round(y / 100)) * 100


def tiles(tiles1, route_tiles_t):
    """tiles1: [(mesh, m, t)] (t: level units). route_tiles_t: the tail's tiles (set). Returns the new list."""
    out = []
    by = {}
    for mesh, m, t in tiles1:
        k = tile_of(t[0], t[1]); by.setdefault(k, (mesh, m, t))
        if k in S_TILES: out.append((mesh, m, t))
        elif k == RING: out.append((mesh, m, [RING_TO[0] + t[0] - k[0], RING_TO[1] + t[1] - k[1], t[2]]))
        elif k in route_tiles_t: out.append((mesh, m, [t[0], t[1] + T_UP, t[2]]))
        else: out.append((mesh, m, [t[0], t[1] + N_UP, t[2]]))
    for src, dst, mx in PIECES:
        mesh, m, t = by[src]
        if mx: m = [-m[0], m[1], m[2], -m[3], m[4], m[5], -m[6], m[7], m[8]]   # world x negated about the tile
        out.append((mesh, m, [dst[0] - (t[0] - src[0]) if mx else dst[0] + t[0] - src[0], dst[1] + t[1] - src[1], t[2]]))
    return out


def route(r1, end):
    """r1: stage1_route.pkl's dict (world units). Returns (new dict, new end index, tail tiles)."""
    P = np.array(r1['nodes']); n = len(P)
    tl = [tile_of(x / SCALE, y / SCALE) for x, y, _ in P]
    seg = lambda keys: [i for i in range(n) if tl[i] in keys]
    first_N = next(i for i in range(n) if tl[i] == (1700, 0))
    first_T = next(i for i in range(n) if tl[i] == T_FROM)
    S = list(range(0, next(i for i in range(n) if tl[i] == RING)))
    R = [i for i in range(len(S), first_N) if tl[i] == RING][::-1]
    N = list(range(first_N, first_T)); T = list(range(first_T, n))
    p1 = [i for i in range(n) if tl[i] in ((1300, 200), (1300, 300)) and first_N <= i < first_T][::-1]
    p2 = [i for i in range(n) if tl[i] in ((1700, 500), (1700, 600)) and first_N <= i < first_T]
    W = lambda dx, dy: np.array([dx * SCALE, dy * SCALE, 0.0])
    parts = [(S, W(0, 0), False), (p1, W(400, -300), 'mirror'), (p2, W(0, -400), False), (N, W(0, N_UP), False),
             (R, W(RING_TO[0] - RING[0], RING_TO[1] - RING[1]), True), (T, W(0, T_UP), False)]
    nodes, cor, floor, bottom, orig, joins = [], [], [], [], [], []
    for idx, off, rev in parts:
        if nodes: joins.append(len(nodes))
        for i in idx:
            q = P[i] + off
            if rev == 'mirror': q[0] = 2 * round(q[0] / SCALE / 100) * 100 * SCALE - q[0]   # (flown back and mirrored:
            nodes.append(q)                                                                  # its sides as they were)
            c = list(r1['corridor'][i]); cor.append((c[1], c[0], c[2], c[3]) if rev is True else tuple(c))
            floor.append(r1['floor'][i]); bottom.append(r1['bottom'][i]); orig.append(i)
    nodes = np.array(nodes)
    sm = ndimage.gaussian_filter1d(nodes, 2.0, axis=0, mode='nearest')   # the joins eased
    w = np.zeros(len(nodes))
    for j in joins: w[max(j - JOIN, 0):j + JOIN] = 1
    w = ndimage.gaussian_filter1d(w, 2.0)[:, None]
    nodes = nodes * (1 - w) + sm * w
    new_end = next(k for k, i in enumerate(orig) if i >= end and k >= len(nodes) - len(T))
    nodes[:, 2] *= WALL_UP
    cor = [(c[0], c[1], c[2] * WALL_UP, c[3] * WALL_UP) for c in cor]
    floor = [f * WALL_UP for f in floor]; bottom = [b_ * WALL_UP for b_ in bottom]
    out = dict(r1); out.update(nodes=[tuple(float(v) for v in p) for p in nodes], corridor=cor, floor=floor, bottom=bottom, orig=orig)
    return out, new_end, {tl[i] for i in T}


def tile_map(centres, tail):
    """{new tile centre: the original tile drawn there} for the original tiles' centres (as tiles())."""
    out = {}
    for k in centres:
        if k in S_TILES: out[k] = k
        elif k == RING: out[RING_TO] = k
        elif k in tail: out[(k[0], k[1] + T_UP)] = k
        else: out[(k[0], k[1] + N_UP)] = k
    for src, dst, _ in PIECES: out[dst] = src
    return out
