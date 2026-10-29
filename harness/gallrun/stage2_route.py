"""Gall Run stage 2: the landscape of stage 2's source (sub-level 8), flown low along the
source's track backwards.

    ../.venv/bin/python3 stage2_route.py <om ram.be> [out.pkl]    (default stage2_route.pkl, + .png preview)

The ram dump is states/src_stage2.st as big-endian words (gall_asset.dump_ram). Like stage 1's source the
landscape is 100x100 tiles under transform nodes (the root's largest group), and its track runs along
a route struct of the same form as Station Chase's (pointer 0x800D2600; an open route, node 0 has no
previous node). Each tile holds (by child path): (0,0,0) the terrain mesh, (0,0,1) rails, (1,) the
track bed, (0,1) fences and poles, (2,) junk and buildings. Only the terrain mesh is used, and of
it only the parts textured as landscape (LANDSCAPE); tiles left with less than COVER of it get
the flattest fully covered one (filler()). A few start
tiles exist in two or three versions at one position (the yard as the level begins and as it
goes on); the one with the highest node id is in every state and is kept.

Route (level units): the source's route walked from node 0, a Catmull-Rom spline through it, reversed,
clipped to the longest stretch over landscape (holes up to GAP bridged), started at START in the
valley north of it (link()), stray nodes dropped (straighten()), moved off the rocks
next to it (avoid(): sideways within BAND), at most MAX_LEN long; height FLY over the highest surface
under the hull (HULL around the line, HULL_LEN along it: whatever is there is flown over),
reached on ramps no steeper than SLOPE, smoothed without dipping more than DIP; nodes every NODE_STEP, scaled by SCALE / SCALE_Z, in the source level's own frame (gall_asset.py places them
in the world after stage 1). It starts over level ground (stage 1 ends low over the canyon floor).
Per node also a corridor entry (as gallrun/stage1_route.py's): wide, but 0 in GROOVE.
Stage 2 starts in GROOVE (the user's pick: a narrow cutting, east to west, where stage 1 ends on
its straight before turning north): flown along its floor's middle, low (GROOVE_FLY), on edge
(gallrun.c KNIFE_W: its corridor entries are 0 wide); its walls are kept (left out of sink() and
avoid()), and its rock is not flown over.
Rock standing in the way of the low route is pressed down towards the ground along the line
(sink(): every vertex by the same smooth function of its position, so the rock stays whole, no
holes); only what still stands is flown over (NEAR).
Output: {'nodes': [(x, y, z)], 'corridor': [(left, right, 0, 0)], 'ground': floor z under node 0,
'low': per node the lowest z it may fly at, 'sink': sink()'s field (warp() makes it a function)}.
"""
import heapq, math, os, pickle, struct, sys
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE2 = 1.5                       # stage 2 is drawn this much larger than stage 1 (gall_asset.py)
SCALE, SCALE_Z = 6.0 * STAGE2, 9.0 * STAGE2
ROUTE_PTR, NODE, NODE_POS = 0x800D2600, 0x54, 0x38
TERRAIN = (0, 0, 0)
# Texture records (in states/src_stage2.st) of the landscape: moss and the rock/scrap heaps the hills are
# made of, the walls of the deep cuttings the line runs in through the hills (0x801D5B20), and
# grey ground (gallrun/tex_atlas.py). The terrain meshes also hold walls, gates,
# grilles, fences, crates and pipes: every other texture is left out. The grey one is mostly
# concrete (posts, slabs, a sunken tunnel): of it only flat parts at ground level (box z within
# GROUND, height under FLAT).
LANDSCAPE = {0x801D5A00, 0x801D5960, 0x801D5970, 0x801D5980, 0x801D5A20, 0x801D5B20}
GREY, GROUND, FLAT = 0x801D59A0, (-1.0, 8.0), 1.0
FLY, HULL, HULL_LEN, DIP = 4.0, 4.0, 9, 0.5
GAP = 120                          # holes in the terrain under the track up to GAP steps
OBST, BAND, CLEAR, LEAN, SMOOTH = 7.0, 30, 20.0, 0.04, 15.0   # avoid()
SLOPE = 0.2                        # climbs and descents at most this steep (level units: x9 / x6 in the world)
START, START_DIR, LEAD_IN, JOIN = (484, -295), (-1, 0), 60, 40   # link()
SINK_A, SINK_R, SINK_K = 1.5, 4.0, 0.3   # sink(): rock height kept near the line, out to, more per unit beyond
NEAR = 2.0                         # rock nearer than this (level units) to the line is flown over
# The narrow cutting stage 2 starts in: x from its east mouth to its west end, the band of y its
# floor lies in; the ship flies GROOVE_FLY over its floor there.
GROOVE, GROOVE_FLY = (598.0, 300.0, -412.0, -390.0), 5.0
# GROOVE from its east end (598) to here is the way in (COPY's tile): flown over its floor, not on
# edge; stage 2 is placed by its first node past here (the cutting's east mouth, as before the way in)
KNIFE_EAST = 552.0
GROOVE_PAD, GROOVE_KEEP = 12.0, 200.0   # sink(): round GROOVE this far, rock kept up to this high
# Among the four rocks north of the column (the user's line, 2026-10-08): up left of them, round the
# north-east rock, down the middle, round the south-west rock, out north; the rocks kept whole (out of
# sink() and avoid(), like GROOVE) in ROCKS_BOX (x0, x1, y0, y1).
ROCKS_WAY = [(58, 131), (72, 154), (127, 168), (122, 219), (90, 228), (67, 210), (49, 173), (40, 136),
             (37, 76), (12, 67), (-25, 90), (-25, 127), (-6, 136), (26, 154), (30, 182), (12, 219), (-2, 235)]
ROCKS_BOX = (-50.0, 150.0, 40.0, 250.0)
# waypath(): from the west end of GROOVE (the cutting itself is groove_line()) -> the corridor south
# of the valley -> north up the (moved) column -> the square of hills -> up the west side of the
# (moved) west part -> across its top to the finish
# The user's line for the end (2026-10-09, drawn on the map: up the west side, over the top with a dip
# between its middle tiles, a hook west into the east side, a swing west round the south-west hills and
# east again, on to the finish further east), every 10 units; A* between them.
USER_LINE = [
             (11, 402), (7, 411), (3, 420), (-1, 429), (-4, 439), (-6, 448), (-7, 458), (-7, 468), (-5,
             478), (-3, 488), (-2, 498), (-3, 508), (-5, 518), (-7, 528), (-9, 538), (-10, 547), (-11, 557),
             (-8, 567), (-3, 575), (4, 583), (11, 590), (18, 597), (26, 603), (35, 607), (45, 610), (54,
             613), (64, 615), (74, 615), (83, 612), (91, 605), (98, 598), (106, 591), (113, 585), (122,
             580), (132, 580), (141, 584), (148, 590), (156, 596), (163, 604), (170, 610), (179, 615), (218,
             515), (208, 515), (198, 513), (189, 508), (182, 502), (175, 494), (174, 485), (180, 476), (187,
             469), (194, 462), (175, 408), (165, 408), (155, 407), (145, 406), (135, 404), (126, 401), (117,
             396), (109, 390), (102, 383), (95, 376), (90, 367), (87, 358), (87, 348), (88, 338), (89, 328),
             (91, 318), (96, 309), (102, 302), (110, 295), (118, 291), (128, 289), (138, 291), (148, 294),
             (157, 298), (166, 302), (175, 307), (184, 310), (194, 313), (203, 316), (213, 318), (223, 318),
             (233, 319), (243, 318), (253, 317), (263, 315), (272, 312), (282, 308), (363, 306), (373, 307),
             (383, 306), (393, 306), (403, 306), (413, 306), (423, 306), (433, 306), (443, 306), (453, 306),
             (463, 307), (473, 307), (483, 307)]
WAYS = [(300, -400), (150, -385), (90, -330), (100, -200), (100, 0)] + ROCKS_WAY + USER_LINE
MAX_LEN = 5000                     # stage 2 length at most (level units): the route ends at the last of WAYS
START_MAX, SIDE = 300, 2.5         # start over level ground within this; corridor: hull half width
NODE_STEP = 6.0
DONOR = {}                         # donors(): place -> (source, quarter turns); none for now
# The north-west piece (every tile at y >= SHIFT_FROM) moved by SHIFT, so that the bottom of its
# column sits right on the tile north of the lower valley (100, -300): one piece again.
SHIFT_FROM, SHIFT = -200, (200, 0)
# Then pieces moved within it (after SHIFT; place -> (from, quarter turns)): the two tiles at the
# north-east end of its top row, turned 180 degrees, fill the gap under its west part.
MOVE = {(-200, 0): ((200, 300), 2), (-100, 0): ((100, 300), 2),
        # east of the old finish (the user's picks): the stub west of the column, turned 90 degrees
        # anticlockwise (its rock edge the north side), then the two tiles over the cutting, turned 180
        # degrees, their hollow open west; stage 2 goes on east along them
        (300, 300): ((0, -200), 1), (500, 300): ((300, -300), 2), (400, 300): ((400, -300), 2)}
# Tiles copied (place -> (source, quarter turns, scale across), the source stays): a stretch of the
# canyon up the column (2:00 into the run), turned to run west (its wide end to stage 1, its narrow
# end to the cutting) and drawn half size across (its height as it is: the canyon as wide as the
# cutting), as the way into the cutting between the stages (the user's pick, 2026-10-08: a smoother join)
COPY = {(575, -400): ((100, -100), 1, 0.5)}
# Ground beside it, out to the cutting tiles' sides (it is half as wide: through its wide end the void
# and the sky showed): filler()'s flat tile drawn this size (centre -> x, y scale)
FILL = {(575, -437.5): (0.5, 0.25), (575, -362.5): (0.5, 0.25)}
GONE = {(0, 300)}                  # after SHIFT: left out (a stub of the top row over the hills)
WEST_TO, WEST = -100, (300, 300)    # last: the west part (x <= WEST_TO) moved by WEST, on top of the square
DROP = {(-400, -100), (-300, -100), (-200, -100), (-400, -200), (-300, -200), (-400, -300), (-300, -300),
        (-300, 0), (-200, 0), (-400, 0),
        (0, 200), (0, 100), (0, 0), (0, -100), (0, -200), (0, -300),
        (-200, -300), (-100, -300), (-200, -400), (-100, -400), (500, -300)}
FLAT_TILE = None                   # filler()'s flat tile (mesh, rotation, translation)
COVER = 0.5                        # tiles less covered by landscape than this: filler()
STEP = 2.0


def _R(E): return lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
def _F(E): return lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]


def landscape(E):
    """keep(part) for mesh_image.build_tiles: parts textured as landscape."""
    R, F = _R(E), _F(E)

    def keep(p):
        t = R(R(p + 0x24) + 8) if R(p + 0x24) else 0
        return t in LANDSCAPE or (t == GREY and GROUND[0] <= F(p + 8) and F(p + 0x14) <= GROUND[1]
                                  and F(p + 0x14) - F(p + 8) < FLAT)          # part box z: +8 .. +0x14
    return keep


def terrain_tiles(E):
    """[(mesh, rotation, translation)] of the terrain mesh of every tile."""
    R, F = _R(E), _F(E)
    assert R(0x8013CE0C) & 0xFFFF == 8, 'not the stage 2 source (sub-level 8)'
    root = R(0x8013CE24)
    kids = lambda g: [R(R(g + 0x10) + 4 * i) for i in range(R(g + 0xC))]
    group = max((g for g in kids(root) if R(g) >> 28 == 5), key=lambda g: R(g + 0xC))
    best = {}
    for t in kids(group):
        if R(t) >> 28 != 0xD: continue
        a = t
        for i in TERRAIN:
            if i >= R(a + 0xC): a = 0; break
            a = R(R(a + 0x10) + 4 * i)
        if not a or R(a) >> 28 != 3: continue
        pos = (round(F(t + 0x38)), round(F(t + 0x3C)))
        if pos not in best or R(t + 0x44) > best[pos][0]:
            best[pos] = (R(t + 0x44), (a, [F(t + 0x14 + 4 * j) for j in range(9)], [F(t + 0x38 + 4 * j) for j in range(3)]))
    return donors(filler(E, [v[1] for v in best.values()]))


def donors(tiles):
    """Tiles rebuilt from others (DONOR: place -> (source, turned)): the track's tunnel stretch (a
    cutting's portal at each end, filler between) from the valley tiles by the end of the line (north
    of it and along it, where stage 2 no longer flies), turned 90 degrees so their valley runs along it; the station yard (filler) from a 2x2 block of hills."""
    at = {(round(t[0]), round(t[1])): (mesh, m, t) for mesh, m, t in tiles}
    out = [x for x in tiles if (round(x[2][0]), round(x[2][1])) not in DONOR and
           (round(x[2][0]), round(x[2][1])) not in DROP]
    out = [(mesh, m, [t[0] + SHIFT[0], t[1] + SHIFT[1], t[2]] if t[1] >= SHIFT_FROM - 1 else t)
           for mesh, m, t in out]
    at = {(round(t[0]), round(t[1])): (mesh, m, t) for mesh, m, t in out}
    moved = []
    for (x, y), (src, turns) in MOVE.items():
        mesh, m, t = at[src]
        for _ in range(turns % 4): m = [m[3], m[4], m[5], -m[0], -m[1], -m[2], m[6], m[7], m[8]]
        moved.append((mesh, m, [x, y, t[2]]))
    gone = {src for src, _ in MOVE.values()} | GONE
    out = [x for x in out if (round(x[2][0]), round(x[2][1])) not in gone] + moved
    out = [(mesh, m, [t[0] + WEST[0], t[1] + WEST[1], t[2]] if t[1] >= SHIFT_FROM - 1 and t[0] <= WEST_TO + 1
            else t) for mesh, m, t in out]
    for (x, y), (src, turned) in DONOR.items():
        mesh, m, t = at[src]
        for _ in range(turned % 4):                                  # quarter turns: x' = y, y' = -x
            m = [m[3], m[4], m[5], -m[0], -m[1], -m[2], m[6], m[7], m[8]]
        out.append((mesh, m, [x, y, t[2]]))
    for (x, y), (src, turns, k) in COPY.items():
        mesh, m, t = at[src]
        for _ in range(turns % 4): m = [m[3], m[4], m[5], -m[0], -m[1], -m[2], m[6], m[7], m[8]]
        m = [v * k if j % 3 < 2 else v for j, v in enumerate(m)]    # x, y out scaled, z as it is
        out.append((mesh, m, [x, y, t[2]]))
    for (x, y), (kx, ky) in FILL.items():
        mesh, m, t = FLAT_TILE
        m = [v * (kx, ky, 1)[j % 3] for j, v in enumerate(m)]
        out.append((mesh, m, [x, y, t[2]]))
    return out


def filler(E, tiles):
    """Tiles with too little landscape left (COVER of the tile seen from above: the yard, a
    station, buildings) get the flattest fully covered landscape tile instead, so the ground has
    no holes. Returns the kept tiles plus the fillers."""
    R, F, keep = _R(E), _F(E), landscape(E)
    cov = {}
    for mesh, m, t in tiles:
        if mesh not in cov: cov[mesh] = cover(E, mesh, keep)
    full = [x for x in tiles if cov[x[0]] > 0.95]
    if not full: return tiles
    def bumps(x):
        ps = [R(R(x[0] + 0x10) + 4 * i) for i in range(R(x[0] + 0xC))]
        ps = [p for p in ps if keep(p)]
        return max(F(p + 0x14) for p in ps) - min(F(p + 8) for p in ps)
    flat = min(full, key=bumps)
    global FLAT_TILE
    FLAT_TILE = flat
    return ([x for x in tiles if cov[x[0]] >= COVER]
            + [(flat[0], flat[1], [t[0], t[1], flat[2][2]]) for mesh, m, t in tiles if cov[mesh] < COVER])


def mesh_tris(E, mesh, keep):
    """Triangles (3x3 arrays, mesh units) of the parts keep() picks."""
    R = _R(E)
    sys.path.insert(0, HERE)
    from stage1_geom import tri_ids
    lst = R(mesh + 0x10)
    for i in range(R(mesh + 0xC)):
        p = R(lst + 4 * i); a, buf, n = R(p + 0x28), {}, 0
        if not keep(p): continue
        while R(a) >> 24 != 0xB8 and n < 5000:
            w0, w1 = R(a), R(a + 4)
            if w0 >> 24 == 0x04:
                for j in range((w0 & 0xFFFF) >> 9):
                    buf[((w0 >> 16) & 0xFF) // 2 + j] = [c / 8 for c in struct.unpack_from('>hhh', E, (w1 + 16 * j) & 0x7FFFFF)]
            else:
                for ids in tri_ids(w0, w1):
                    vs = [buf.get(k) for k in ids]
                    if all(vs): yield np.array(vs, np.float32)
            a += 8; n += 1


def cover(E, mesh, keep):
    """Share of the 100x100 tile (2x2 cells) under the parts keep() picks, seen from above."""
    g = np.zeros((50, 50), bool)
    for a, b, c in mesh_tris(E, mesh, keep):
        n = max(2, int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b))) + 1)
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij'); m = (i + j) <= n
        q = a + (b - a) * (i[m] / n)[:, None] + (c - a) * (j[m] / n)[:, None]
        x, y = ((q[:, 0] + 50) // 2).astype(int), ((q[:, 1] + 50) // 2).astype(int)
        ok = (x >= 0) & (x < 50) & (y >= 0) & (y < 50)
        g[x[ok], y[ok]] = True
    return g.mean()


def track(E):
    """The source's route from node 0 (open: ends at a node without a next one)."""
    R, F = _R(E), _F(E)
    p, i, pts, seen = R(ROUTE_PTR), 0, [], set()
    while i not in seen:
        seen.add(i); r = p + i * NODE
        pts.append(tuple(F(r + NODE_POS + 4 * k) for k in range(3)))
        if R(r) == 0: break
        i = R(r + 8)
    return np.array(pts)


def catmull(P, step):
    out = []
    Q = np.vstack([P[0], P, P[-1]])
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        n = max(1, int(np.linalg.norm(p2 - p1) / step))
        for k in range(n):
            t = k / n
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1])
    return np.array(out)


def heightmap(E, tiles, sink=None):
    """(L, H, C, x0, y0): per STEP cell the lowest and the highest landscape surface and the lowest
    one more than 6 above L (a ceiling), 1e9 / -1e9 where there is none. sink: sink()'s field,
    the landscape as warp() presses it down."""
    keep, pts = landscape(E), []
    for mesh, m, t in tiles:
        M, T0 = np.array(m, np.float32).reshape(3, 3), np.array(t, np.float32)
        pts += [tri @ M + T0 for tri in mesh_tris(E, mesh, keep)]
    T = np.array(pts, np.float32)
    if sink is not None: T[:, :, 2] = warp(sink)(T[:, :, 0], T[:, :, 1], T[:, :, 2])
    x0, y0 = T[:, :, 0].min() - 10, T[:, :, 1].min() - 10
    nx, ny = int((T[:, :, 0].max() + 10 - x0) / STEP), int((T[:, :, 1].max() + 10 - y0) / STEP)
    P = []
    for a, b, c in T:
        l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)); n = max(2, int(l) + 1)
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij'); mm = (i + j) <= n
        u = (i[mm] / n)[:, None]; v = (j[mm] / n)[:, None]; P.append(a + (b - a) * u + (c - a) * v)
    P = np.concatenate(P)
    ix, iy, z = ((P[:, 0] - x0) / STEP).astype(int), ((P[:, 1] - y0) / STEP).astype(int), P[:, 2]
    L = np.full((nx, ny), 1e9, np.float32); np.minimum.at(L, (ix, iy), z)
    H = np.full((nx, ny), -1e9, np.float32); np.maximum.at(H, (ix, iy), z)
    C = np.full((nx, ny), 1e9, np.float32); hi = z > L[ix, iy] + 6
    np.minimum.at(C, (ix[hi], iy[hi]), z[hi])
    return L, H, C, x0, y0


def straighten(T, sharp=75.0):
    """Drop route nodes the line turns at by more than `sharp` degrees (stray nodes off the track,
    a siding), one at a time."""
    T = list(T)
    while True:
        ang = []
        for i in range(1, len(T) - 1):
            u, v = np.subtract(T[i][:2], T[i - 1][:2]), np.subtract(T[i + 1][:2], T[i][:2])
            c = np.dot(u, v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-6)
            ang.append((math.degrees(math.acos(max(-1.0, min(1.0, c)))), i))
        worst = max(ang)
        if worst[0] <= sharp: return np.array(T)
        del T[worst[1]]


def link(xy, L, H, x0, y0):
    """Stage 2 starts at START (the user's pick: a flat valley north of the end of the line),
    flies LEAD_IN straight along START_DIR (stage 1 ends heading the same way, gall_asset.place)
    and joins the line (not before JOIN units past its point nearest to START) where the cheapest
    way meets it: Dijkstra through the clearest cells (cost 1 + 20 / clearance to rock)."""
    G = ndimage.minimum_filter(L, size=31)
    clr = ndimage.distance_transform_edt(~((L > 1e8) | (H > G + OBST))) * STEP
    cost = 1 + 20 / np.maximum(clr, 0.5)
    cell = lambda p: (int((p[0] - x0) / STEP), int((p[1] - y0) / STEP))
    s = np.array(START, float); lead = s + np.array(START_DIR) * LEAD_IN
    k0 = int(np.argmin(np.linalg.norm(xy - s, axis=1))) + JOIN
    goal = {}
    for k in range(k0, len(xy)):
        goal.setdefault(cell(xy[k]), k)
    a = cell(lead)
    dist, prev, pq, g = {a: 0}, {}, [(0, a)], None
    while pq:                                                  # to the nearest point of the line
        f, u = heapq.heappop(pq)
        if u in goal: g = u; break
        if f > dist[u] + 1e-6: continue
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                v = (u[0] + da, u[1] + db)
                if (da or db) and 0 <= v[0] < L.shape[0] and 0 <= v[1] < L.shape[1]:
                    nd = dist[u] + math.hypot(da, db) * cost[v]
                    if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
    j = goal[g]
    path = [g]
    while path[-1] != a: path.append(prev[path[-1]])
    P = np.array([s, lead] + [(x0 + i * STEP + STEP / 2, y0 + j_ * STEP + STEP / 2) for i, j_ in path[::-1][1:]]
                 + list(xy[j + 1:]))
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    P = np.array([np.interp(np.arange(0, d[-1], 1.0), d, P[:, k]) for k in range(2)]).T
    return np.stack([ndimage.gaussian_filter1d(P[:, k], 10, mode='nearest') for k in range(2)], 1)


def in_groove(xy):
    """Which points (level units) lie in GROOVE."""
    xy = np.asarray(xy)
    return ((xy[..., 0] <= GROOVE[0] + 1) & (xy[..., 0] >= GROOVE[1] - 1)
            & (xy[..., 1] >= GROOVE[2]) & (xy[..., 1] <= GROOVE[3]))


def in_rocks(xy):
    """Which points (level units) lie in ROCKS_BOX."""
    xy = np.asarray(xy)
    return ((xy[..., 0] >= ROCKS_BOX[0]) & (xy[..., 0] <= ROCKS_BOX[1])
            & (xy[..., 1] >= ROCKS_BOX[2]) & (xy[..., 1] <= ROCKS_BOX[3]))


def groove_line(L, H, x0, y0):
    """GROOVE's floor, east to west in 1 unit steps: per x the middle of the lowest cells of the
    band, smoothed."""
    ys = np.arange(GROOVE[2], GROOVE[3], STEP)
    xs = np.arange(GROOVE[0], GROOVE[1] - 1e-6, -1.0)
    mid = []
    for x in xs:
        i = int((x - x0) / STEP)
        h = np.array([H[i, int((y - y0) / STEP)] if H[i, int((y - y0) / STEP)] > -1e8 else 1e9 for y in ys])
        low = ys[h <= h.min() + 1.0]
        mid.append(low.mean())
    y = ndimage.gaussian_filter1d(np.array(mid), 12, mode='nearest')
    return np.column_stack([xs, y])


def waypath(L, H, x0, y0):
    """The stage 2 line without the track (its tunnel and yards are gone): GROOVE's floor
    (groove_line()), then the cheapest way through WAYS (level units), A* with cost 1 + 20 / clearance to rock reaching flight
    height, no ground impassable. 1 unit steps, smoothed."""
    G = ndimage.minimum_filter(L, size=31)
    clr = ndimage.distance_transform_edt(~((L > 1e8) | (H > G + OBST))) * STEP
    cost = np.where(L < 1e8, 1 + 20 / np.maximum(clr, 0.5), np.inf)
    cell = lambda p: (int((p[0] - x0) / STEP), int((p[1] - y0) / STEP))
    path = []
    for a, g in zip(map(cell, WAYS), map(cell, WAYS[1:])):
        dist, prev, pq = {a: 0}, {}, [(0, a)]
        while pq:
            f, u = heapq.heappop(pq)
            if u == g: break
            if f - math.dist(u, g) > dist[u] + 1e-6: continue
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    v = (u[0] + da, u[1] + db)
                    if (da or db) and 0 <= v[0] < L.shape[0] and 0 <= v[1] < L.shape[1] and np.isfinite(cost[v]):
                        nd = dist[u] + math.hypot(da, db) * cost[v]
                        if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd + math.dist(v, g), v))
        leg = [g]
        while leg[-1] != a: leg.append(prev[leg[-1]])
        path += leg[::-1] if not path else leg[::-1][1:]
    g = groove_line(L, H, x0, y0)
    P = np.array(list(g) + [(x0 + i * STEP + STEP / 2, y0 + j * STEP + STEP / 2) for i, j in path[1:]], float)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    P = np.array([np.interp(np.arange(0, d[-1], 1.0), d, P[:, k]) for k in range(2)]).T
    S = np.stack([ndimage.gaussian_filter1d(P[:, k], 8, mode='nearest') for k in range(2)], 1)
    S[:len(g) - 8] = P[:len(g) - 8]                 # the cutting's floor as it is
    return S


def avoid(xy, L, H, x0, y0):
    """The track's line (1 unit steps) moved sideways off the rocks next to it: at every point the
    offset along the line's normal, within BAND, with the most clearance to the nearest obstacle
    (a cell higher than OBST over the lowest ground around it, or no ground; counted up to
    CLEAR, less LEAN per unit of offset), smoothed (SMOOTH points); not in GROOVE."""
    G = ndimage.minimum_filter(L, size=31)
    obst = (L > 1e8) | (H > G + OBST)
    clr = ndimage.distance_transform_edt(~obst) * STEP
    d = np.gradient(xy, axis=0); d /= np.linalg.norm(d, axis=1)[:, None]
    nrm = np.stack([d[:, 1], -d[:, 0]], 1)
    offs = np.arange(-BAND, BAND + 1, 1.0)
    Q = xy[:, None, :] + nrm[:, None, :] * offs[None, :, None]
    i = np.clip(((Q[..., 0] - x0) / STEP).astype(int), 0, L.shape[0] - 1)
    j = np.clip(((Q[..., 1] - y0) / STEP).astype(int), 0, L.shape[1] - 1)
    score = np.minimum(clr[i, j], CLEAR) - LEAN * np.abs(offs)[None, :]
    o = offs[np.argmax(score, axis=1)]
    g = in_groove(xy) | in_rocks(xy)
    o[g] = 0                                  # the cutting, the rocks: the line as it is
    o = ndimage.gaussian_filter1d(o, SMOOTH, mode='nearest')
    o = ndimage.gaussian_filter1d(o, SMOOTH, mode='nearest')
    o[g] = 0
    P, keep = xy + nrm * o[:, None], [0]
    for i in range(1, len(P)):                # an offset inside a tight bend would turn back: drop it
        if np.dot(P[i] - P[keep[-1]], d[i]) > 0.5: keep.append(i)
    P = P[keep]
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    t = np.arange(0, s[-1], 1.0)              # 1 unit steps again
    P = np.array([np.interp(t, s, P[:, j]) for j in range(2)]).T
    P = np.stack([ndimage.gaussian_filter1d(P[:, j], 12, mode='nearest') for j in range(2)], 1)
    return P, clr, obst


def route(E, tiles, sink, near_rock, line=None):
    """The stage 2 nodes over the landscape (pressed down by sink); line: the line to take (1 unit
    steps; default the one avoid(waypath()) finds)."""
    L, H, C, x0, y0 = heightmap(E, tiles, sink)
    idx = lambda p: (int((p[0] - x0) / STEP), int((p[1] - y0) / STEP))
    inside = lambda p: 0 <= idx(p)[0] < L.shape[0] and 0 <= idx(p)[1] < L.shape[1]
    xy = catmull(straighten(track(E))[:, :2], 1.0)[::-1]                 # backwards: from the end of the line
    on = ndimage.binary_closing(np.array([inside(p) and L[idx(p)] < 1e8 for p in xy]), np.ones(GAP))
    best, cur, start = (0, 0), 0, 0                           # the longest stretch over terrain
    for i, o in enumerate(on):
        if o:
            if cur == 0: start = i
            cur += 1
            if cur > best[1] - best[0]: best = (start, i + 1)
        else: cur = 0
    xy, clr, obst = avoid(waypath(L, H, x0, y0)[:MAX_LEN] if line is None else line, L, H, x0, y0)
    if line is not None: xy = line
    r = int(HULL / STEP)                                      # the highest surface under the hull
    disc = (lambda yy, xx: (xx ** 2 + yy ** 2) <= r * r)(*np.mgrid[-r:r + 1, -r:r + 1])
    Hh = ndimage.maximum_filter(np.where(obst & (L < 1e8), L, H), footprint=disc)   # (rock beside a cutting: avoid()'s)
    Ha = ndimage.maximum_filter(np.where(L < 1e8, H, -1e9), footprint=disc)   # all of it,
    near = ndimage.distance_transform_edt(~obst) * STEP < near_rock       # where rock is too near to pass
    floor = np.array([(Ha if near[idx(p)] else Hh)[idx(p)] for p in xy])   # by: flown over
    floor = np.interp(np.arange(len(floor)), np.nonzero(floor > -1e8)[0], floor[floor > -1e8])
    floor = ndimage.maximum_filter1d(floor, HULL_LEN)
    gr = in_groove(xy)                                        # in the cutting: over its floor, on edge
    floor[gr] = [L[idx(p)] for p in xy[gr]]
    fly = np.where(gr, GROOVE_FLY, FLY)
    G = ndimage.minimum_filter(L, size=31)                   # start over level ground: stage 1 ends low
    flat = np.nonzero(floor[:START_MAX] <= np.array([G[idx(p)] for p in xy[:START_MAX]]) + 1.5)[0]
    i0 = int(flat[0]) if len(flat) else 0
    xy, floor, fly = xy[i0:], floor[i0:], fly[i0:]
    z = floor + fly
    z = ndimage.grey_dilation(z, structure=-SLOPE * np.abs(np.arange(-400, 401)))   # ramps of SLOPE
    low = z - DIP
    for sigma in (6, 2):
        z = np.maximum(ndimage.gaussian_filter1d(z, sigma, mode='nearest'), low)
    P = np.column_stack([xy, z, floor + fly])
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1))])
    t = np.linspace(0, d[-1], int(d[-1] / NODE_STEP) + 1)
    P = np.array([np.interp(t, d, P[:, j]) for j in range(4)]).T
    low = [float(v) * SCALE_Z for v in P[:, 3]]              # per node: the lowest it may fly
    P = P[:, :3]
    nodes = [(float(x) * SCALE, float(y) * SCALE, float(z) * SCALE_Z) for x, y, z in P]
    corridor = [(0.0, 0.0, 0.0, 0.0) if g and x <= KNIFE_EAST else (999.0, 999.0, 0.0, 0.0)   # on edge only in
                for g, x in zip(in_groove(P[:, :2]), P[:, 0])]                    # the cutting (gallrun.c KNIFE_W)
    info = dict(tiles=len(tiles), start=i0, length=float(d[-1]), nodes=len(nodes), kept=best, of=len(on),
                min_clr=float(min(clr[idx(p)] for p in P)), climb=float(P[:, 2].max() - P[:, 2].min()))
    anchor = int(np.argmax(P[:, 0] <= KNIFE_EAST))           # the cutting's east mouth: stage 2 is placed by it
    info['anchor'] = anchor
    return nodes, corridor, low[0] - GROOVE_FLY * SCALE_Z, low, P, (np.where(L < 1e8, L, -1e9), x0, y0), info


def sink(L, x0, y0, xy):
    """The field warp() presses the rock down by: per STEP cell the ground (the lowest landscape
    around, smoothed) and the most any surface may stand over it there: SINK_A within SINK_R of the
    line xy, SINK_K more per unit further out."""
    G = ndimage.minimum_filter(L, size=31)
    G = ndimage.gaussian_filter(np.where(G < 1e8, G, np.median(G[G < 1e8])), 3)
    on = np.zeros(L.shape, bool)
    for x, y in xy[~(in_groove(xy) | in_rocks(xy))]:   # GROOVE's walls and the rocks stay
        i, j = int((x - x0) / STEP), int((y - y0) / STEP)
        if 0 <= i < L.shape[0] and 0 <= j < L.shape[1]: on[i, j] = True
    D = ndimage.distance_transform_edt(~on) * STEP
    A = SINK_A + SINK_K * np.maximum(D - SINK_R, 0)
    gx = x0 + (np.arange(L.shape[0]) + 0.5) * STEP; gy = y0 + (np.arange(L.shape[1]) + 0.5) * STEP
    box = ((gx[:, None] <= GROOVE[0]) & (gx[:, None] >= GROOVE[1])
           & (gy[None, :] >= GROOVE[2] - GROOVE_PAD) & (gy[None, :] <= GROOVE[3] + GROOVE_PAD))
    w = np.clip(ndimage.gaussian_filter(box.astype(float), GROOVE_PAD / STEP) * 2, 0, 1)
    A = A * (1 - w) + GROOVE_KEEP * w                # GROOVE's walls (and round it) as they are
    box = ((gx[:, None] >= ROCKS_BOX[0]) & (gx[:, None] <= ROCKS_BOX[1])
           & (gy[None, :] >= ROCKS_BOX[2]) & (gy[None, :] <= ROCKS_BOX[3]))
    w = np.clip(ndimage.gaussian_filter(box.astype(float), GROOVE_PAD / STEP) * 2, 0, 1)
    A = A * (1 - w) + GROOVE_KEEP * w                # and the rocks
    return dict(x0=float(x0), y0=float(y0), G=G.astype(np.float32), A=A.astype(np.float32))


def warp(s):
    """z(x, y, z) of the landscape pressed down by sink() field s: the height h over the ground
    becomes A tanh(h / A), so low ground stays as it is and rock is squeezed under A; one smooth
    function of the position, so the parts of a rock stay joined."""
    G, A = s['G'], s['A']
    def at(F, x, y):
        u = np.clip((np.asarray(x, np.float64) - s['x0']) / STEP - 0.5, 0, F.shape[0] - 1.001)
        v = np.clip((np.asarray(y, np.float64) - s['y0']) / STEP - 0.5, 0, F.shape[1] - 1.001)
        i, j = u.astype(int), v.astype(int); a, b = u - i, v - j
        return (F[i, j] * (1 - a) * (1 - b) + F[i + 1, j] * a * (1 - b)
                + F[i, j + 1] * (1 - a) * b + F[i + 1, j + 1] * a * b)
    def f(x, y, z):
        g, a = at(G, x, y), at(A, x, y)
        h = np.asarray(z, np.float64) - g
        return np.where(h > 0, g + a * np.tanh(np.maximum(h, 0) / a), z)
    return f


def build(E):
    """The line on the landscape as it is, the rock along it pressed down (sink()), route() over
    what is left."""
    tiles = terrain_tiles(E)
    L, H, C, x0, y0 = heightmap(E, tiles)
    line = avoid(waypath(L, H, x0, y0)[:MAX_LEN], L, H, x0, y0)[0]
    s = sink(L, x0, y0, line)
    return route(E, tiles, s, NEAR, line) + (s,)


if __name__ == '__main__':
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'stage2_route.pkl')
    nodes, corridor, ground, low, P, (H, x0, y0), info, sk = build(open(sys.argv[1], 'rb').read())
    pickle.dump(dict(nodes=nodes, corridor=corridor, ground=ground, low=low, sink=sk, anchor=info['anchor']), open(out, 'wb'))
    print(info)
    from PIL import Image
    h = np.clip((H.T[::-1] + 40) / 120, 0, 1)
    img = np.zeros(h.shape + (3,), np.uint8)
    img[..., 0] = np.where(H.T[::-1] > -1e8, h * 255, 0); img[..., 1] = np.where(H.T[::-1] > -1e8, h * 200, 0)
    for k, (x, y, z) in enumerate(P):
        img[H.shape[1] - 1 - int((y - y0) / STEP), int((x - x0) / STEP)] = (0, 255, 255) if k else (255, 0, 0)
    Image.fromarray(img).save(out + '.png')
