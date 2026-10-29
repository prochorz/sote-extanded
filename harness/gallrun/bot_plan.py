"""A pilot for the Gall Run's stage 1 that picks its own way (harness tool, not in the game): over stage 1's
collision (gallrun/collide.py, as gallrun.c meets it) a two-layer map of world cells is built: LOW, at the
route's height between the walls (no rock within the ship's reach of that height, ground under it) and HIGH,
over the rock (no rock up to that height); A* from the start of control to the end, with a smooth random
cost field per seed, so each seed goes its own way: round a pillar on either side, through a slit on edge
or over its wall. HIGH is kept near the route (no cutting the whole canyon short).

    ../.venv/bin/python3 gallrun/bot_plan.py <seed> [out.json]   (+ out.png: the map and the way)

Output: {'way': [(x, y, z, layer)] every few cells (world units), 'seed'}.
"""
import heapq, json, math, os, struct, sys
import numpy as np
from scipy import ndimage, spatial
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import paths
import collide

IMG = os.path.join(paths.GAME, 'gall_run.bin')
BASE = 0x80628000
CELL = 10.0                 # world units
REACH = 14.0                # LOW: no rock within this of the route's height (the ship's half height + room)
GROW = 1                    # cells the rock is grown by (the ship's half width, with the cells' own size)
HIGH_UP = (150.0, 240.0)    # HIGH: this far over the route (gallrun.c FLY_TOP 260), clear of rock by 20
NEAR = 90.0                 # HIGH only this near the route
START, END_BACK = 6, 60     # from node START to (switch - END_BACK)
NOISE = (6.0, 1.5)          # random cost field: smoothing (cells), amplitude
CLIMB = 0.3                 # the way's height changes at most this per unit along it
OBSTACLES = [(31, 35), (218, 222), (531, 535)]   # route nodes: the stone ring, the two slits
SKIP = 8                    # a step keeps to route nodes this near (no hop over a wall to the canyon's next loop)
HIGH_COST = 2.2            # x (1 + 0.3 N(0,1)) a seed


def load():
    img = open(IMG, 'rb').read()
    R = lambda a: struct.unpack_from('>I', img, a - BASE)[0]
    T, N = collide.world(collide.extract(img, BASE, R(BASE + 4), R(BASE + 8)), 6, 9)
    rt, sw = R(BASE + 20), R(BASE + 48)
    route = np.array([struct.unpack_from('>3f', img, rt + 0x38 + 0x54 * i - BASE) for i in range(sw)]) - [0, 0, 10.0]
    return T, route, sw


def maps(T, route):
    x0, y0 = T[:, :, 0].min() - 50, T[:, :, 1].min() - 50
    nx, ny = int((T[:, :, 0].max() + 50 - x0) / CELL) + 1, int((T[:, :, 1].max() + 50 - y0) / CELL) + 1
    ix, iy, zz = [], [], []
    for a, b, c in T:                                     # samples over every triangle
        l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)); n = max(2, int(l / (CELL / 2)) + 1)
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij'); m = (i + j) <= n
        u, v = (i[m] / n)[:, None], (j[m] / n)[:, None]; p = a + (b - a) * u + (c - a) * v
        ix.append(((p[:, 0] - x0) / CELL).astype(int)); iy.append(((p[:, 1] - y0) / CELL).astype(int)); zz.append(p[:, 2])
    ix, iy, zz = np.concatenate(ix), np.concatenate(iy), np.concatenate(zz)
    gx, gy = np.meshgrid(x0 + (np.arange(nx) + 0.5) * CELL, y0 + (np.arange(ny) + 0.5) * CELL, indexing='ij')
    tree = spatial.cKDTree(route[:, :2])
    dist, near = tree.query(np.stack([gx.ravel(), gy.ravel()], 1))
    dist, near = dist.reshape(nx, ny), near.reshape(nx, ny)
    zr = route[near, 2]                                   # the route's height near each cell
    top = np.full((nx, ny), -1e9); np.maximum.at(top, (ix, iy), zz)
    low_rock = np.zeros((nx, ny), bool); ground = np.zeros((nx, ny), bool)
    zc = zr[ix, iy]
    low_rock[ix[np.abs(zz - zc) < REACH], iy[np.abs(zz - zc) < REACH]] = True
    ground[ix[zz < zc - REACH], iy[zz < zc - REACH]] = True
    low_rock = ndimage.binary_dilation(low_rock, iterations=GROW)
    low = ~low_rock & ground & (dist < 400)
    for p, q in zip(route, route[1:]):                    # along the route itself the ship passes (on edge
        for u in np.linspace(0, 1, 9):                    # in a slit, gallrun.c's pull by Z)
            i, j = int((p[0] + (q[0] - p[0]) * u - x0) / CELL), int((p[1] + (q[1] - p[1]) * u - y0) / CELL)
            low[i - 1:i + 2, j - 1:j + 2] = True
    hz = np.clip(top + 40, zr + HIGH_UP[0], zr + HIGH_UP[1])   # HIGH flies this high
    high_rock = ndimage.maximum_filter(top, size=2 * GROW + 1) + 20 > hz
    high = ~high_rock & (top > -1e8) & (dist < NEAR)
    return dict(x0=x0, y0=y0, nx=nx, ny=ny, low=low, high=high, hz=hz, zr=zr, near=near, dist=dist)


def plan(M, route, sw, seed):
    rng = np.random.default_rng(seed)
    noise = ndimage.gaussian_filter(rng.standard_normal((M['nx'], M['ny'])), NOISE[0])
    noise = 1 + NOISE[1] * np.clip(noise / (noise.std() + 1e-9), -1.5, 1.5) * 0.3
    hc = max(1.3, HIGH_COST * (1 + 0.3 * rng.standard_normal()))   # this seed's taste for flying high
    under = np.zeros(len(route), bool); over = np.zeros(len(route), bool)   # a coin per narrow place:
    for a_, b_ in OBSTACLES:                              # through it on edge, or over it
        if rng.random() < 0.5: under[max(a_ - 25, 0):b_ + 25] = True
        else: over[max(a_ - 2, 0):b_ + 3] = True
    no_high, no_low = under[M['near']], over[M['near']] & (M['dist'] < 60)
    cell = lambda p: (int((p[0] - M['x0']) / CELL), int((p[1] - M['y0']) / CELL))
    s, g = cell(route[START]), cell(route[sw - END_BACK])
    goal = lambda c: abs(c[0] - g[0]) + abs(c[1] - g[1]) <= 3
    best = {(s, 0): 0.0}; prev = {}; q = [(0.0, 0.0, s, 0)]
    nb = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    end = None
    while q:
        f, d, c, L = heapq.heappop(q)
        if d > best.get((c, L), 1e18): continue
        if goal(c) and L == 0: end = (c, L); break
        for dx, dy in nb:
            n = (c[0] + dx, c[1] + dy)
            if not (0 <= n[0] < M['nx'] and 0 <= n[1] < M['ny']): continue
            if abs(int(M['near'][n]) - int(M['near'][c])) > SKIP: continue   # no jumping to a farther part of the canyon
            for L2 in (0, 1):
                if not (M['low'] if L2 == 0 else M['high'])[n]: continue
                if L2 and no_high[n]: continue
                if not L2 and no_low[n]: continue
                if L2 != L and not (M['low'][n] or M['low'][c]): continue    # change layers over open ground
                step = math.hypot(dx, dy) * noise[n] * (hc if L2 else 1) + (4 if L2 != L else 0)
                nd = d + step
                if nd < best.get((n, L2), 1e18):
                    best[(n, L2)] = nd; prev[(n, L2)] = (c, L)
                    heapq.heappush(q, (nd + 0.9 * math.hypot(n[0] - g[0], n[1] - g[1]), nd, n, L2))
    assert end, 'no way found'
    way = [end]
    while way[-1] in prev: way.append(prev[way[-1]])
    way.reverse()
    pts = [(M['x0'] + (i + 0.5) * CELL, M['y0'] + (j + 0.5) * CELL, float(M['hz'][i, j] if L else M['zr'][i, j]), L) for (i, j), L in way]
    z = np.array([p[2] for p in pts]); dl = np.r_[0, np.hypot(np.diff([p[0] for p in pts]), np.diff([p[1] for p in pts]))]
    s_ = np.cumsum(dl)                                    # the height: what each place needs, eased in over
    zz = z.copy()                                         # CLIMB units of height per unit along (climbs start early)
    for i in np.nonzero(np.array([p[3] for p in pts]))[0]:
        zz = np.maximum(zz, z[i] - CLIMB * np.abs(s_ - s_[i]))
    return [(p[0], p[1], float(h), int(p[3] or h > p[2] + 40)) for p, h in zip(pts, zz)][::3]


if __name__ == '__main__':
    seed = int(sys.argv[1]); out = sys.argv[2] if len(sys.argv) > 2 else f'way{seed}.json'
    T, route, sw = load()
    M = maps(T, route)
    way = plan(M, route, sw, seed)
    json.dump(dict(seed=seed, way=way), open(out, 'w'))
    print('seed', seed, 'points', len(way), 'high', sum(w[3] for w in way))
    from PIL import Image
    im = np.zeros((M['ny'], M['nx'], 3), np.uint8)
    im[M['low'].T] = (90, 70, 50); im[(M['high'] & ~M['low']).T] = (60, 60, 110)
    for (x, y, z, L) in way:
        i, j = int((x - M['x0']) / CELL), int((y - M['y0']) / CELL); im[j, i] = (255, 255, 0) if L else (255, 0, 0)
    for p in route[::2]:
        i, j = int((p[0] - M['x0']) / CELL), int((p[1] - M['y0']) / CELL); im[j, i] = (0, 255, 0)
    Image.fromarray(im[::-1]).save(out[:-5] + '.png')
