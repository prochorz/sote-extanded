"""Gall Run stage 1 route through the canyon: the source's track backwards, from its end
to the canyon's exit before the town, low over the floor, with the corridor the player may steer the Falcon in.

    ../.venv/bin/python3 stage1_route.py <lvl5 ram.be> [out.pkl]    (default stage1_route.pkl, + .png preview)

The ram dump is states/src_stage1.st as big-endian words (gall_asset.dump_ram). Steps (level units):
1. channel: sand cells (stage1_geom FLOOR, the track) plus cells whose lowest surface is below
   LOW (the narrow slots between tiles), closed by 2 cells, less the pillars standing in it (rock
   at flight height round a small hole: blocked());
2. A* from the end of the source's race to the canyon exit through WAYPOINTS (keeps the order of
   the canyon loop), cost 1 + K / clearance to the edge of the sand track, + WALL in cells with rock at
   flight height (a wall across the canyon is crossed at its slit): the centre line;
3. Gaussian smoothing (SIGMA); height = FLY over the highest sand under the hull (HULL around the
   line, HULL_LEN along it: dunes), under an arch (a ceiling more than ARCH above the floor) half
   way up its opening, at most the ceiling minus HEAD; smoothed without dipping more than DIP below that;
4. nodes every NODE_STEP from the dead end to the town, scaled by SCALE (x, y) and SCALE_Z
   (gall_asset.py joins stage 2 and the lead nodes), and per node the corridor (corridor_of).
Output: {'nodes': [(x, y, z)], 'corridor': [(left, right, down, up)], 'ground': floor z under the
last node, 'floor': floor z under every node (the highest sand under the hull), 'bottom': the lowest
surface under every node}, world units.
"""
import heapq, math, os, pickle, sys
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from stage1_geom import Geom, X0, Y0, STEP, FLOOR

SCALE, SCALE_Z = 6.0, 9.0          # same as gall_asset.py
LOW, K, SIGMA = 10.0, 20.0, 3.0
FLY, HEAD, ARCH = 4.0, 5.0, 12.0
SIDE, FLOOR_GAP, UP_MAX = 2.5, 3.0, 12.0   # corridor: hull half width, above the floor, climb
BLOCK = (1.5, 12.0)                # rock between these heights over the floor: an obstacle
SLOPE = 0.25                       # climbs at most this steep (level units)
PILLAR = 400                       # holes in rock smaller than this (cells): a pillar's inside
WALL_TOP = 10.0                    # sand higher than this over the floor around: a wall's top
WALL = 20.0                        # A* cost of a cell with rock (a wall across is crossed at its slit)
SLIT = (25.0, 6.0, 4)              # corridor_of(): a slit (canyon width, gap, at most nodes long)
HULL, HULL_LEN, DIP = 4.0, 9, 0.5   # hull half width, length in path steps (level units); allowed dip
CLEAR, CENTRE_SIGMA, CENTRE_PASSES = 6.5, 4.0, 3   # centre(): room wanted on each side (level units)
OVER_GAP = 1.5                     # corridor up: this far under any rock over the line
OVERS = [(1500, -89, 15.0), (1500, -123, 15.0)]   # walls right across the canyon (no slit): over them at z
OVER_R = 4.0
NODE_STEP = 6.0
# GATES: (x, y, z) the route goes through exactly: the small stone ring standing across the slot
# after the hut (an opening ~8 across, its middle 19 up).
GATES = [(1699, -105, 20.0)]   # (the ship is drawn 10 world units = ~1.1 below its route)
GATE_R, GATE_ROOM = 6.0, 6.0       # height eased in over this distance; corridor there (world units)
# end of the race (south dead end of the east canyon) -> north (through the stone ring) -> west ->
# the S-bend tiles -> the
# south loop -> the canyon's last stretch before the town (the town is left out)
WAYPOINTS = [(1700, -320), (1699, -105), (1700, 470), (1500, 800), (1300, 370), (1300, 100), (1500, 110),
             (1500, -90), (1400, -290), (1290, -170), (1100, -70), (1080, 110), (960, 110)]


def centreline(ch, rock, sand):
    clr = ndimage.distance_transform_edt(sand) * STEP         # the middle of the sand track
    pick = np.where(ch, clr + 1e-3 * ndimage.distance_transform_edt(ch), -1)   # (or of the channel)

    def cell(p):                              # the clearest channel cell near a waypoint
        i, j, r = int((p[0] - X0) / STEP), int((p[1] - Y0) / STEP), 12
        if any(p == g[:2] for g in GATES): return i, j
        w = pick[i - r:i + r + 1, j - r:j + r + 1]; a, b = np.unravel_index(np.argmax(w), w.shape)
        return i - r + a, j - r + b

    def astar(s, g):
        dist, prev, pq = {s: 0}, {}, [(0, s)]
        nb = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]
        while pq:
            f, u = heapq.heappop(pq)
            if u == g: break
            if f - math.dist(u, g) > dist[u] + 1e-6: continue
            for a, b in nb:
                v = (u[0] + a, u[1] + b)
                if not (0 <= v[0] < ch.shape[0] and 0 <= v[1] < ch.shape[1]) or not ch[v]: continue
                nd = dist[u] + math.hypot(a, b) * (1 + K / max(clr[v], 1) + WALL * rock[v])
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd + math.dist(v, g), v))
        p = [g]
        while p[-1] != s: p.append(prev[p[-1]])
        return p[::-1]

    path = []
    for a, b in zip(WAYPOINTS, WAYPOINTS[1:]):
        leg = astar(cell(a), cell(b)); path += leg if not path else leg[1:]
    return np.array([(X0 + i * STEP + STEP / 2, Y0 + j * STEP + STEP / 2) for i, j in path]), clr


def blocked(g, Fm, Fz, L):
    """Cells with rock at flight height: any non-sand surface from BLOCK[0] to BLOCK[1] over the
    floor (pillars, walls across the canyon with a slit in them, low overhangs)."""
    ix, iy, z, _ = g._raster(lambda k: g.tris[k][3] not in FLOOR)
    F0 = np.where(Fm, Fz, L)
    rock = (z > F0[ix, iy] + BLOCK[0]) & (z < F0[ix, iy] + BLOCK[1])
    out = np.zeros(Fm.shape, bool); out[ix[rock], iy[rock]] = True
    return out


def resample(P, step):
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1))])
    t = np.linspace(0, d[-1], int(d[-1] / step) + 1)
    return np.array([np.interp(t, d, P[:, j]) for j in range(P.shape[1])]).T


def build(E):
    g = Geom(E)
    Fm, Fz, Ft = g.floor()
    H, L, C = g.maps()
    ch = ndimage.binary_closing(Fm | (L < LOW), iterations=2)
    G = ndimage.minimum_filter(np.where(Fm, Fz, 1e9), size=31)   # the canyon floor around
    tall = np.where(L < 1e8, L, -1e9) > G + WALL_TOP                # a wall across: thin and tall
    tall &= ~ndimage.binary_opening(tall, np.ones((11, 11), bool))   # (not a raised stretch of floor)
    rock = (blocked(g, Fm, Fz, L) | tall) & ch
    lab, n = ndimage.label(ndimage.binary_fill_holes(rock) & ~rock)   # the inside of a pillar: small,
    size = ndimage.sum(np.ones_like(lab), lab, np.arange(1, n + 1))    # round (not a stretch of canyon)
    box = [max(b.stop - b.start for b in sl) for sl in ndimage.find_objects(lab)]
    inner = [k + 1 for k in range(n) if size[k] < PILLAR and size[k] > 0.4 * box[k] ** 2]
    pillar = np.isin(lab, inner)
    lab, n = ndimage.label(tall)                                  # and solid ones
    size = ndimage.sum(np.ones_like(lab), lab, np.arange(1, n + 1))
    box = [max(b.stop - b.start for b in sl) for sl in ndimage.find_objects(lab)]
    pillar |= np.isin(lab, [k + 1 for k in range(n) if size[k] < PILLAR and size[k] > 0.4 * box[k] ** 2])
    pillar = ndimage.binary_dilation(pillar, iterations=2) & ch
    ch = ch & ~pillar
    xy, clr = centreline(ch, rock, ndimage.binary_closing(Fm, iterations=2) & ch & ~rock)
    xy = resample(xy, 1.0)
    xy = np.stack([ndimage.gaussian_filter1d(xy[:, j], SIGMA, mode='nearest') for j in range(2)], 1)
    xy = centre(xy, ch)
    idx = lambda p: (int((p[0] - X0) / STEP), int((p[1] - Y0) / STEP))
    r = int(HULL / STEP)                                    # the highest sand under the hull
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    Ft = np.where(ndimage.binary_dilation(rock), -1e9, Ft)  # sand on a wall's top is not the floor
    Fh = ndimage.maximum_filter(Ft, footprint=(xx ** 2 + yy ** 2) <= r * r)
    floor = np.array([Fh[idx(p)] if Fh[idx(p)] > -1e8 else L[idx(p)] for p in xy])
    floor = ndimage.maximum_filter1d(floor, HULL_LEN)        # along the hull too
    C3 = ndimage.minimum_filter(C, 3)
    ceil = np.array([C3[idx(p)] for p in xy])
    ceil = np.where(ceil > floor + ARCH, ceil, 1e9)          # an arch to fly under, not a wall's foot
    z = np.where(ceil < 1e8, (floor + ceil) / 2, floor + FLY)    # under an arch: through its middle
    z = np.maximum(np.minimum(np.maximum(z, floor + FLY), ceil - HEAD), floor + 1)
    for ox, oy, oz in OVERS:                                # over a wall across the canyon
        z = np.where(np.linalg.norm(xy - (ox, oy), axis=1) < OVER_R, np.maximum(z, oz), z)
    ramp = ndimage.grey_dilation(z, structure=-SLOPE * np.abs(np.arange(-200, 201)))   # climbs of SLOPE
    z = np.maximum(np.minimum(ramp, ceil - HEAD), z)                 # (not into an arch)
    low = z - DIP                                           # smoothing must not cut into a crest
    for sigma in (6, 2):
        z = np.maximum(ndimage.gaussian_filter1d(z, sigma, mode='nearest'), low)
    for gx, gy, gz in GATES:                                # through a gate's middle
        w = np.exp(-(np.linalg.norm(xy - (gx, gy), axis=1) / GATE_R) ** 2)
        z = z * (1 - w) + gz * w
    over = np.array([C3[idx(p)] for p in xy])               # any rock over the line (a low bridge too)
    top = np.minimum(np.minimum(ceil - HEAD, over - OVER_GAP), z + UP_MAX)   # how high the player (and
                                                            # gallrun.c's camera) may climb
    Q = resample(np.column_stack([xy, z, floor, top]), NODE_STEP)
    P = Q[:, :3]
    nodes = [(float(x) * SCALE, float(y) * SCALE, float(z) * SCALE_Z) for x, y, z in P]
    corridor = corridor_of(Q, ch, rock, G)
    info = dict(length=float(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1).sum()),
                min_clr=float(min(clr[idx(p)] for p in P)), nodes=len(nodes),
                under_ceiling=int((ceil < 1e8).sum()))
    bottom = [float(L[idx(p)]) * SCALE_Z for p in P]
    return nodes, corridor, ([float(v) * SCALE_Z for v in Q[:, 3]], bottom), P, ch, info


def room(x, y, r, sgn, m):
    """Free run (level units, up to 60) from (x, y) along r * sgn inside the mask m."""
    t = 0.0
    while t < 60:
        q = np.array([x, y]) + r * sgn * (t + 0.5)
        i_, j_ = int((q[0] - X0) / STEP), int((q[1] - Y0) / STEP)
        if not (0 <= i_ < m.shape[0] and 0 <= j_ < m.shape[1]) or not m[i_, j_]: break
        t += 0.5
    return t


def centre(xy, ch):
    """The line (1 unit steps) moved sideways off the near wall of the channel ch: where the room
    on one side is under CLEAR, towards the middle (as far as the other side allows), smoothed
    (CENTRE_SIGMA), CENTRE_PASSES times. The smoothed line cuts the inside of tight bends."""
    for _ in range(CENTRE_PASSES):
        d = np.gradient(xy, axis=0); d /= np.maximum(np.linalg.norm(d, axis=1), 1e-6)[:, None]
        n = np.stack([d[:, 1], -d[:, 0]], 1)                     # right
        o = np.zeros(len(xy))
        for i, (x, y) in enumerate(xy):
            lt, rt = room(x, y, n[i], -1, ch), room(x, y, n[i], 1, ch)
            if min(lt, rt) < CLEAR: o[i] = np.clip((rt - lt) / 2, -(CLEAR - rt), CLEAR - lt) if lt + rt >= 2 * CLEAR else (rt - lt) / 2
        o = ndimage.gaussian_filter1d(o, CENTRE_SIGMA, mode='nearest')
        xy = resample(xy + n * o[:, None], 1.0)
    return xy


def corridor_of(Q, ch, rock, G):
    """Per node, room for the player to steer the ship off the route (world units): left and right
    along the horizontal normal of the route to the edge of the channel, down to the floor, up to
    an arch or UP_MAX; less the hull's half width (SIDE) or FLOOR_GAP. In a slit (a wall across a
    canyon wider than SLIT[0] with rock closer than SLIT[1] on both sides, for at most SLIT[2]
    nodes) left and right are 0:
    gallrun.c puts the ships on edge there."""
    out, slit = [], []
    for i, (x, y, z, fl, top) in enumerate(Q):
        a, b = Q[max(i - 2, 0), :2], Q[min(i + 2, len(Q) - 1), :2]
        d = (b - a) / max(np.linalg.norm(b - a), 1e-6); r = np.array([d[1], -d[0]])
        side = [max(room(x, y, r, sgn, ch) - SIDE, 0) * SCALE for sgn in (-1, 1)]   # left, right
        gi = G[int((x - X0) / STEP), int((y - Y0) / STEP)]       # low, at the canyon's floor
        slit.append(z - fl < FLY + 2 and fl - gi < 3 and sum(room(x, y, r, sgn, ch) for sgn in (-1, 1)) > SLIT[0] and
                    sum(room(x, y, r, sgn, ch & ~rock) for sgn in (-1, 1)) < SLIT[1])
        out.append((side[0], side[1], max(z - fl - FLOOR_GAP, 0) * SCALE_Z, max(top - z, 0) * SCALE_Z))
    for k, (x, y, z, fl, top) in enumerate(Q):                # in a gate: hardly any room to steer
        if any(math.dist((x, y), g[:2]) < GATE_R for g in GATES):
            out[k] = (GATE_ROOM, GATE_ROOM, GATE_ROOM, GATE_ROOM)
    lab, n = ndimage.label(slit)                              # a wall is thin: a few nodes
    for k, sl in enumerate(ndimage.find_objects(lab)):
        if sl[0].stop - sl[0].start <= SLIT[2]:
            for i in range(sl[0].start, sl[0].stop): out[i] = (0.0, 0.0) + out[i][2:]
    return out


if __name__ == '__main__':
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'stage1_route.pkl')
    nodes, corridor, (floor, bottom), P, ch, info = build(open(sys.argv[1], 'rb').read())
    pickle.dump(dict(nodes=nodes, corridor=corridor, ground=floor[-1], floor=floor, bottom=bottom), open(out, 'wb'))
    print(info, 'corridor median l/r/d/u', [round(float(np.median([c[k] for c in corridor]))) for k in range(4)])
    from PIL import Image
    i0 = int((860 - X0) / STEP)
    img = np.zeros(ch.shape[::-1] + (3,), np.uint8); img[..., 1] = ch.T * 90
    for x, y, z in P:
        img[int((y - Y0) / STEP), int((x - X0) / STEP)] = (255, 255, int(np.clip(z * 6, 0, 255)))
    Image.fromarray(img[::-1, i0 - 150:]).save(out + '.png')
