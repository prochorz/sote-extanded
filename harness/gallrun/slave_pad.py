"""Slave I's pad from Gall 6b (sub-level 15, states/gall_6b.st) at the end of the Gall Run's stage 2.

In Gall 6b Boba Fett waits on a round shaft in the cliffs: rock walls round it (one-sided, facing in) from its
floor (z 393) up to its rim (690 at the low notch, 787 at the highest), a gantry in the middle (top 652), Slave I
standing on its tail inside the gantry (36 units tall; here lifted onto its top: SLAVE_UP) and Boba by it (z ~516). Copied here (mesh_image.build_image,
Gall's own textures), scaled K (Slave I to the Falcon as in the films: ~22 against ~36 world units) and put at
PLACE, north of the finish (off the route), the rim RIM_UNDER under the route's height there. cliffs.footprint()
opens a round clearing (clear()) so the cliffs stand round the shaft's walls.

    at = place(path)                       # where it goes (world): centre, yaw, anchor
    path = path[:len(path) - 4 + 1] + extend(path, at)   # the route on into it
    discs = [clear(at)]                    # for cliffs.footprint()
    blob, h = mesh(E6b, base, at, to_level)   # its parts; to_level(world xyz) -> the stage's level units
"""
import math, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mesh_image import build_image
import level_map

PAD = [0x80214B9C, 0x80214BB4, 0x80214BCC, 0x80214BE4]   # the shaft: walls, floor, gantry
SLAVE = [0x80213B34 + 0x18 * i for i in range(8)]         # Slave I (the boss 'slav''s model), under its node
SLAVE_GUNS = 0x80213B4C             # its twin guns (SLAVE[1]): their bone (the boss's +0xD0) is at 0 while parked, the
SLAVE_GUNS_OFF = (0.0, 5.6, -12.2)  # guns inside the hull; in flight the boss's animation moves them (0x8003FDB8). Put
                                    # on its front face low down, the barrels out ~4 (Gall units; the user's pick, 2026-10-18)
K = 0.62                  # Gall units -> world units (Slave I 36 tall -> ~22; the Falcon ~36 long)
CENTRE = (-150.5, 226.5)  # the shaft's middle in Gall (its walls' box), x y
RIM = 787.0               # its highest rim (Gall z): the whole shaft under the route
RADIUS = 240.0            # its walls' farthest from the middle (Gall units)
PLACE = (6060.0, 7910.0)  # the shaft's middle (world): north of the finish, off the route (the user's pick on the map,
                          # 2026-10-12: over stage 2's last tile, S2 500,300)
RIM_UNDER = 20.0          # the rim this far under the route there (lower at its notch)
GANTRY = (-189.6, 271.3)  # the gantry's (Slave I's) middle in Gall
SLAVE_UP = 0.0            # Slave I lifted this much (Gall z): it stands inside the gantry (498..534, hidden) till the
                          # scene lifts it off (CINE_RISE_W)


def part_tris(E, p):
    """A part's triangles (Gall world units: the shaft's meshes hang under no turn or move)."""
    from collide import tri_ids
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    a, buf, out = R(p + 0x28), {}, []
    while R(a) >> 24 != 0xB8:
        w0, w1 = R(a), R(a + 4)
        if w0 >> 24 == 0x04:
            for j in range((w0 & 0xFFFF) >> 9):
                buf[((w0 >> 16) & 0xFF) // 2 + j] = tuple(v / 8 for v in struct.unpack_from('>hhh', E, (w1 + 16 * j) & 0x7FFFFF))
        else:
            for ids in tri_ids(w0, w1):
                if all(k in buf for k in ids): out.append([buf[k] for k in ids])
        a += 8
    return np.array(out, np.float64).reshape(-1, 3, 3)


KEEP_WALL = False             # the shaft's far wall kept (True) or all four gone (its face filled the view as the
                          # Falcon went round: the user, the Outrider unseen)
FLOOR_Z = 396.0           # the pad's floor (Gall z): the pillar's top but behind the wall kept


def walls(E, at):
    """The shaft's walls (parts: steep, far out, tall; four, a sector each) as {part: bins it covers}, and the one
    kept: the farthest from where the Falcon comes (the user: open the shaft so the pad and Slave I lifting off are
    in view; maybe one wall left behind)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    out, best, kept = {}, -2.0, None
    for m in PAD:
        for i in range(R(m + 0xC)):
            p = R(R(m + 0x10) + 4 * i)
            T = part_tris(E, p)
            if not len(T): continue
            n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); A = np.linalg.norm(n, axis=1)
            steep = (A * (np.abs(n[:, 2]) < 0.3 * A)).sum() / max(A.sum(), 1e-9)
            d = T.reshape(-1, 3)[:, :2] - CENTRE
            if steep < 0.9 or np.hypot(*d.T).max() < 180 or T[:, :, 2].max() < 700: continue
            b = ((np.arctan2(d[:, 1], d[:, 0]) + math.pi) / (2 * math.pi) * MESA_BINS).astype(int) % MESA_BINS
            u = sorted(set(b.tolist()))                            # the bearings between its ends (vertices
            gaps = [(u[(j + 1) % len(u)] - u[j]) % MESA_BINS for j in range(len(u))]   # only at its corners)
            j = int(np.argmax(gaps)); lo = u[(j + 1) % len(u)]; span = (u[j] - lo) % MESA_BINS
            out[p] = {(lo + q) % MESA_BINS for q in range(span + 1)}
            mean = math.atan2(*np.average(T.mean(1)[:, :2] - CENTRE, axis=0, weights=A)[::-1]) + at['yaw']
            score = math.cos(mean - at['back'])
            if score > best: best, kept = score, p
    return out, kept


def place(path):
    """{'node', 'xy', 'z', 'yaw'}: the shaft at PLACE (world), its rim RIM_UNDER under the route's height at the
    nearest node, turned so the gantry faces that node (the finish)."""
    P = np.asarray(path)
    xy = np.array(PLACE, float)
    k = int(np.argmin(np.hypot(*(P[:-4, :2] - xy).T)))
    to = math.atan2(P[k, 1] - xy[1], P[k, 0] - xy[0])
    g = math.atan2(GANTRY[1] - CENTRE[1], GANTRY[0] - CENTRE[0])   # the gantry's bearing from the middle (Gall)
    e = len(P) - 4
    back = math.atan2(xy[1] - P[e, 1], xy[0] - P[e, 0])          # from the route's end to the shaft: its far side
    return dict(node=k, xy=xy, z=float(P[k, 2]) - RIM_UNDER, yaw=to - g, back=back)


EXT_STEP = 50.0           # extend(): route nodes this far apart (world; stage 2's run ~50)
EXT_TURN = 520.0          # the curve's handles: on along the old end's heading, back from the shaft
EXT_BY = 45.0             # the route passes this far to the right of the shaft's middle (the gantry ~80 to its left)
EXT_PAST = -800.0         # and ends this far past the middle (before it: the scene at the end slows the Falcon to it)
EXT_WIDE = 85.0           # the canyon to the shaft: at least this much room either side (cliffs.footprint wide)


def extend(path, at):
    """New route nodes after the old end (the finish): a smooth curve from its heading on into the shaft's
    clearing, over the shaft beside the gantry, EXT_PAST beyond its middle, at the old end's height. The old end's
    last 4 nodes are where the spline ran out (gall_asset end = len - 4): the curve starts at its end node."""
    P = np.asarray(path)
    e = len(P) - 4
    p0, h0 = P[e, :2], P[e, :2] - P[e - 2, :2]
    h0 = h0 / np.hypot(*h0)
    c = np.asarray(at['xy'], float)
    d = c - p0; d /= np.hypot(*d)                      # the way in: from the old end to the shaft
    right = np.array([d[1], -d[0]])
    p3 = c + right * EXT_BY + d * EXT_PAST
    hl = min(EXT_TURN, 0.4 * float(np.hypot(*(p3 - p0))))         # (handles: on along the old heading, back from the
    p1, p2 = p0 + h0 * hl, p3 - d * hl                             # end toward the shaft; EXT_TURN + EXT_PAST < 0 had
    # turned the last one round: the route ended in a hook, heading away from the shaft, the Falcon U-turned at speed)
    t = np.linspace(0, 1, 400)[:, None]
    B = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
    L = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(B, axis=0).T))])
    z = float(P[e, 2])
    out = [(float(np.interp(s, L, B[:, 0])), float(np.interp(s, L, B[:, 1])), z)
           for s in np.arange(EXT_STEP, L[-1] + 1e-3, EXT_STEP)]
    return out + [(x + (out[-1][0] - out[-2][0]) * k, y + (out[-1][1] - out[-2][1]) * k, z)
                  for k, (x, y, _) in zip(range(1, 5), [out[-1]] * 4)]     # (the spline reads ahead)


PILLAR = True             # the shaft stands on a rock pillar of its own outline, free in open haze (the user: as if on
                          # a pillar, free in space); False: a hole in a round plateau MESA_R wide (it looked walled in)
MESA_R = 560.0            # (plateau) its radius, world
OPEN_R = 560.0            # open haze round the shaft's middle about this far (world): the cliffs stand back, free
OPEN_ROUGH = 0.22         # approach; its edge in and out by up to this share (the user: smaller, not a circle)
MESA_BINS = 64            # bearings round the plateau
MESA_ROUGH = 0.06         # its edge in and out by up to this share of MESA_R (smooth noise)
TOWER_OUT = 1.0           # the plateau's top starts this far outside the shaft's wall (world)
TOWER_SMOOTH = 5         # bearings the shaft's outline at one is the farthest / highest of (sparse vertices)


def floor_edge(E, ang):
    """The pad's floor (its flat textured parts at the floor's height, the light ring round the gantry): the
    distance from CENTRE to its outline (the farthest floor edge) along each bearing in ang (Gall units)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    placed = {m: t for m, Rm, t in level_map.meshes_of(E)}
    P = []
    for m in PAD:
        for i in range(R(m + 0xC)):
            p = R(R(m + 0x10) + 4 * i)
            T = part_tris(E, p)
            if not R(p + 0x24) or not len(T) or T[:, :, 2].max() > FLOOR_Z + 4: continue
            n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
            if (np.abs(n[:, 2]) > 0.9 * np.linalg.norm(n, axis=1)).all():
                P += [t[:, :2] + np.asarray(placed[m])[:2] for t in T]
    P = np.array(P) - CENTRE
    edges = [(t[j], t[(j + 1) % 3]) for t in P for j in range(3)]
    out = []
    for a in ang:                                                   # ray from the middle to each hull edge
        d, best = np.array([math.cos(a), math.sin(a)]), 0.0
        for q0, q1 in edges:
            e_ = q1 - q0; den = d[0] * e_[1] - d[1] * e_[0]
            if abs(den) < 1e-9: continue
            t = (q0[0] * e_[1] - q0[1] * e_[0]) / den; u = (q0[0] * d[1] - q0[1] * d[0]) / den
            if t > 0 and -1e-6 <= u <= 1 + 1e-6: best = max(best, t)
        out.append(best)
    return np.array(out)


def mesa(E, at, deep):
    """The plateau the shaft is sunk in: its top, a ring from the shaft's wall outline (per bearing the farthest
    and highest point of its walls, TOWER_OUT outside; the walls are one-sided, facing in) out to the plateau's
    edge (MESA_R, rough) at the rim's height, and its sheer side from there down to `deep` (world z, the cliffs'
    bottom), shaded and textured as cliffs.faces() does. Returns quads (world), counter-clockwise from the drawn
    side (the top up, the side out)."""
    import cliffs
    from scipy import ndimage
    placed = {m: (m, Rm, t) for m, Rm, t in level_map.meshes_of(E)}
    T = np.array(level_map.mesh_tris(E, [placed[m] for m in PAD]), np.float64)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    V = T[np.abs(n[:, 2]) < 0.3].reshape(-1, 3)
    d = V[:, :2] - CENTRE; r = np.hypot(*d.T)
    V, d, r = V[r > 120], d[r > 120], r[r > 120]                    # the walls, not the gantry
    nb = MESA_BINS
    b = ((np.arctan2(d[:, 1], d[:, 0]) + math.pi) / (2 * math.pi) * nb).astype(int) % nb
    rr, zz = np.zeros(nb), np.full(nb, -1e9)
    np.maximum.at(rr, b, r); np.maximum.at(zz, b, V[:, 2])
    ok = rr > 0
    rr[~ok], zz[~ok] = rr[ok].mean(), zz[ok].mean()                 # (a bearing with no wall: the mean)
    rr = ndimage.maximum_filter1d(rr, TOWER_SMOOTH, mode='wrap')
    zz = ndimage.maximum_filter1d(zz, TOWER_SMOOTH, mode='wrap')
    out_ = TOWER_OUT / K
    if PILLAR and not KEEP_WALL:                                    # no walls: the pillar's edge is the pad floor's
        rr, out_ = floor_edge(E, (np.arange(nb) + 0.5) / nb * 2 * math.pi - math.pi), 0.0   # outline (the floor
    ws, kept = walls(E, at)                                        # ended short of the walls' one: haze seen
                                                                    # through, the user); open: up to the floor, but
    behind = ws.get(kept, set()) if KEEP_WALL else set()          # behind the wall kept (its back is not drawn:
                                                                    # the pillar's is)
    zz = np.array([zz[k] if k in behind else FLOOR_Z for k in range(nb)])
    w = to_world(at)
    ang = (np.arange(nb) + 0.5) / nb * 2 * math.pi - math.pi
    inner = [np.array(w(CENTRE[0] + math.cos(a) * (rr[k] + out_), CENTRE[1] + math.sin(a) * (rr[k] + out_), zz[k]))
             for k, a in enumerate(ang)]
    cx, cy = w(CENTRE[0], CENTRE[1], RIM)[:2]
    if PILLAR:                                                      # the pillar: the shaft's outline down to the haze
        outer = inner
    rough = 1 + MESA_ROUGH * (2 * cliffs.noise1(np.arange(nb) * 2 * math.pi * MESA_R / nb, 7, 300.0) - 1)
    top = at['z']                                                   # the plateau at the rim's height
    yaw = at['yaw']
    if not PILLAR:
        outer = [np.array((cx + math.cos(a + yaw) * MESA_R * rough[k], cy + math.sin(a + yaw) * MESA_R * rough[k], top))
                 for k, a in enumerate(ang)]
    L = np.array(cliffs.LIGHT) / np.linalg.norm(cliffs.LIGHT)
    up = int(cliffs.SHADE[0] + (cliffs.SHADE[1] - cliffs.SHADE[0]) * max(0.0, float(L[2])))
    quads, s0 = [], 0.0
    tile = lambda v: 64 * math.floor(v / 64)
    for k in range(nb):
        k1 = (k + 1) % nb
        a, a1, o, o1 = inner[k], inner[k1], outer[k], outer[k1]
        pts = [a, o, o1, a1]                                        # the top: up, counter-clockwise from above
        s_ = [p[0] * cliffs.TEX_S for p in pts]; t_ = [p[1] * cliffs.TEX_S for p in pts]
        ds, dt = tile(min(s_)), tile(min(t_))
        if not PILLAR:
            quads.append(([tuple(p) for p in pts], [(x - ds, y - dt) for x, y in zip(s_, t_)], [(up,) * 3] * 4))
        dd = o1[:2] - o[:2]; ln = float(np.hypot(*dd))              # the side: out, from the haze up to the top
        nrm = np.array([dd[1], -dd[0], 0]) / ln
        g = cliffs.SHADE[0] + (cliffs.SHADE[1] - cliffs.SHADE[0]) * max(0.0, float(nrm @ L)) / math.hypot(L[0], L[1])
        ts = s0 * cliffs.TEX_S % 64; s1 = ts + ln * cliffs.TEX_S; s0 += ln
        tm = 64 * round((deep + o[2]) / 2 * cliffs.TEX_T / 64)
        vs = [(o[0], o[1], deep), (o1[0], o1[1], deep), tuple(o1), tuple(o)]
        st = [(ts, tm - deep * cliffs.TEX_T), (s1, tm - deep * cliffs.TEX_T), (s1, tm - o1[2] * cliffs.TEX_T), (ts, tm - o[2] * cliffs.TEX_T)]
        quads.append((vs, st, [(int(g * cliffs.DEEP_SHADE),) * 3] * 2 + [(int(g),) * 3] * 2))
    return quads


def clear(at):
    return (float(at['xy'][0]), float(at['xy'][1]), OPEN_R, OPEN_ROUGH)


def to_world(at):
    c, s = math.cos(at['yaw']), math.sin(at['yaw'])
    def f(x, y, z):
        x, y, z = (x - CENTRE[0]) * K, (y - CENTRE[1]) * K, (z - RIM) * K
        return (at['xy'][0] + c * x - s * y, at['xy'][1] + s * x + c * y, at['z'] + z)
    return f


def mesh(E, base, at, to_level):
    """The shaft and Slave I as one mesh image at base: (bytes, {parts, list, box, lo, hi})."""
    placed = {m: (Rm, t) for m, Rm, t in level_map.meshes_of(E)}
    voff = {}
    for m in PAD:
        assert m in placed, f'{m:08x} not in the level (is this states/gall_6b.st?)'
        Rm, t = placed[m]
        assert np.allclose(Rm, np.eye(3), atol=1e-3), f'{m:08x} is turned: build_image only moves'
        voff[m] = tuple(float(v) for v in t)
    w = to_world(at)
    ws, kept = walls(E, at)
    return build_image(E, PAD, base, xf=lambda x, y, z: to_level(*w(x, y, z)), voff=voff, untextured=False,
                       keep=lambda p: p not in ws or (KEEP_WALL and p == kept))


HANGAR = 0x80215D84       # a Gall 6b hangar (states/gall_6b.st, sector 78 seen from (-45, 551)): its floor, ceiling
                          # and ribs (its walls are the cliff's rock there), the mouth on its +y side
HANGAR_AT = (70.0,)       # its bearing from the shaft's middle (degrees off the way to the finish), the mouth to the
                          # shaft (the user, 2026-10-19: in the cliffs; 2026-10-21: only the one the chase TIEs come
                          # out of, the other gone with its hollow)
HANGAR_AT_OLD = (70.0, -70.0)   # the two hangars' bearings before D8 (bf56): the plan cliffs.faces(old=) keeps the
                          # walls' tops and shades from
HANGAR_K = 2 * K          # its scale (Gall -> world): twice the shaft's, a hangar the Falcon would fit in (the user)
HANGAR_WALL = 12.0        # hangar_rock(): its front's rock on past the mouth's sides (world: over the cliff's edge)
HANGAR_SEEK = 40          # hangar_frames(): bearings this far (degrees) off HANGAR_AT tried for rock deep enough
HANGAR_THICK = 60.0       # ... the hangar's depth and this much behind it all rock (world)
HANGAR_FLAT = 40.0        # hangar_carve(): the wall made straight this far past the mouth's sides (the user: the
HANGAR_FRONT = 60.0       # mouth along the wall), rock in front of that line this far out cut away
HANGAR_NARROW = 1.5       # hangar_carve(): the hollow this much narrower than the hangar each side (its floor and
                          # ceiling end inside the rock, not short of it)


def hangar_frames(E, at, plan, bearings=HANGAR_AT):
    """[{'m', 'o', 'z', 'lo', 'hi'}] per HANGAR_AT bearing: its mouth's middle m (world xy, on the cliff's edge: plan,
    cliffs.footprint), o the way it faces (to the shaft), z its floor (the shaft floor's height), lo/hi its box in
    Gall. The hangar is in the rock, only its mouth out (the user)."""
    placed = {m: (m, Rm, t) for m, Rm, t in level_map.meshes_of(E)}
    assert HANGAR in placed, f'{HANGAR:08x} not in the level (is this states/gall_6b.st?)'
    A = np.array(level_map.mesh_tris(E, [placed[HANGAR]])).reshape(-1, 3)
    lo, hi = A.min(0), A.max(0)
    to = at['yaw'] + math.atan2(GANTRY[1] - CENTRE[1], GANTRY[0] - CENTRE[0])   # (place(): the way to the finish)
    c = np.array(to_world(at)(CENTRE[0], CENTRE[1], FLOOR_Z))
    rock, x0, y0, cell = plan['rock'], plan['x0'], plan['y0'], plan['cell']
    out = []
    depth = (hi[1] - lo[1]) * HANGAR_K
    hw = (hi[0] - lo[0]) / 2 * HANGAR_K

    def is_rock(p):
        i, j = int((p[0] - x0) / cell), int((p[1] - y0) / cell)
        return not (0 <= i < rock.shape[0] and 0 <= j < rock.shape[1]) or rock[i, j]
    for b0 in bearings:
        for db in sorted(range(-HANGAR_SEEK, HANGAR_SEEK + 1, 5), key=abs):   # the nearest bearing with rock behind
            u = np.array([math.cos(to + math.radians(b0 + db)), math.sin(to + math.radians(b0 + db))])
            r = RADIUS * K
            while r < OPEN_R * 2 and not is_rock(c[:2] + u * r): r += cell / 2
            w = np.array([u[1], -u[0]])
            if all(all(is_rock(c[:2] + u * (r + t) + w * a_) for t in np.arange(cell, depth + HANGAR_THICK, cell))
                   for a_ in (-hw, 0.0, hw)):                       # (the user: not through to the canyon behind)
                break
        else: raise AssertionError(f'no rock deep enough for a hangar near bearing {b0}')
        e = c[:2] + u * r                                          # the edge there: its rock cells next to open
        span = (hi[0] - lo[0]) / 2 * HANGAR_K + HANGAR_WALL         # ones, across the mouth's width, fitted by a
        i0, j0 = int((e[0] - x0) / cell), int((e[1] - y0) / cell)   # line (the user: the mouth along the wall)
        n = int(span / cell) + 2
        sub = rock[max(i0 - n, 0):i0 + n + 1, max(j0 - n, 0):j0 + n + 1]
        edge = sub & ~(np.roll(sub, 1, 0) & np.roll(sub, -1, 0) & np.roll(sub, 1, 1) & np.roll(sub, -1, 1))
        ii, jj = np.nonzero(edge)
        pts = np.stack([x0 + (ii + max(i0 - n, 0) + 0.5) * cell, y0 + (jj + max(j0 - n, 0) + 0.5) * cell], 1)
        pts = pts[np.hypot(*(pts - e).T) <= span]
        o = -u
        if len(pts) >= 4:
            q = pts - pts.mean(0)
            d = np.linalg.svd(q, full_matrices=False)[2][0]          # the wall's way
            nrm = np.array([-d[1], d[0]])
            o = nrm if nrm @ u < 0 else -nrm                          # out of the rock (to the shaft's side)
            e = e + o * ((pts.mean(0) - e) @ o)                       # the mouth on the fitted line
        out.append(dict(m=e, o=o, z=float(c[2]), lo=lo, hi=hi))
    return out


def hangar_slot(frames):
    """The image's hangar records (gall_asset.py +364; gall_ties.c hangar_launch()): per hangar its mouth's
    middle at half its height (x, y, z, world) and its outward unit (x, y), 5 big-endian floats."""
    out = b''
    for fr in frames:
        h = (fr['hi'][2] - fr['lo'][2]) * HANGAR_K
        out += struct.pack('>5f', float(fr['m'][0]), float(fr['m'][1]), float(fr['z'] + h / 2),
                           float(fr['o'][0]), float(fr['o'][1]))
    return out


def hangar_carve(plan, frames):
    """The hollow each hangar stands in, cut out of the plan's rock (before cliffs.outlines()): its walls are the
    cliff's faces, as in Gall."""
    rock, x0, y0, cell = plan['rock'], plan['x0'], plan['y0'], plan['cell']
    gx, gy = np.meshgrid(x0 + (np.arange(rock.shape[0]) + 0.5) * cell, y0 + (np.arange(rock.shape[1]) + 0.5) * cell,
                         indexing='ij')
    for fr in frames:
        o = fr['o']; r = np.array([o[1], -o[0]])
        hw, dp = (fr['hi'][0] - fr['lo'][0]) / 2 * HANGAR_K - HANGAR_NARROW, (fr['hi'][1] - fr['lo'][1]) * HANGAR_K
        dx, dy = gx - fr['m'][0], gy - fr['m'][1]
        a, v = dx * r[0] + dy * r[1], dx * o[0] + dy * o[1]
        flat = np.abs(a) <= hw + HANGAR_NARROW + HANGAR_FLAT          # the wall straight along the mouth: rock
        rock[flat & (v > 0) & (v <= HANGAR_FRONT)] = False             # in front of it out, hollows behind it filled
        rock[flat & (v <= 0) & (v >= -dp)] = True
        rock[(np.abs(a) <= hw) & (v >= -dp) & (v <= 2 * cell)] = False


def hangar_mesh(E, base, fr, to_level):
    """One hangar (HANGAR) at frame fr (hangar_frames()): (bytes, {parts, list, box, lo, hi})."""
    placed = {m: (Rm, t) for m, Rm, t in level_map.meshes_of(E)}
    Rm, t = placed[HANGAR]
    assert np.allclose(Rm, np.eye(3), atol=1e-3), f'{HANGAR:08x} is turned: build_image only moves'
    lo, hi, o = fr['lo'], fr['hi'], fr['o']
    r = np.array([o[1], -o[0]])
    cx = (lo[0] + hi[0]) / 2

    def xf(x, y, z):
        p = fr['m'] + (x - cx) * HANGAR_K * r + (y - hi[1]) * HANGAR_K * o
        return to_level(float(p[0]), float(p[1]), fr['z'] + (z - lo[2]) * HANGAR_K)
    return build_image(E, [HANGAR], base, xf=xf, voff={HANGAR: tuple(float(v) for v in t)}, untextured=False)


def hangar_rock(fr, deep, faces):
    """The rock that closes a hangar's hollow (hangar_carve(): open from the haze to the sky) but for its mouth: its
    front under the mouth from `deep` (world z) and over it up to the cliff's top there (the faces' tops by the
    mouth: `faces`, cliffs.faces()), and a lid on it at that height. Quads (world) as cliffs.faces() makes them."""
    import cliffs
    lo, hi, o = fr['lo'], fr['hi'], fr['o']
    r = np.array([o[1], -o[0]])
    hw, dp, h = (hi[0] - lo[0]) / 2 * HANGAR_K, (hi[1] - lo[1]) * HANGAR_K, (hi[2] - lo[2]) * HANGAR_K
    ow = hw + HANGAR_WALL
    z0, z1 = fr['z'], fr['z'] + h
    P = lambda u, v: fr['m'] + u * r + v * o
    near = [(vs, cs) for vs, _, cs in faces if min(np.hypot(p[0] - fr['m'][0], p[1] - fr['m'][1]) for p in vs) < ow + dp]
    top = float(np.median([p[2] for vs, _ in near for p in vs[2:]])) if near else z1 + 200.0
    grey = float(np.median([cs[2][0] for _, cs in near])) if near else None   # (the cliff's shade there: no patch)
    L = np.array(cliffs.LIGHT) / np.linalg.norm(cliffs.LIGHT)
    quads = []

    def wall(a, b, za, zb):                                        # a to b: drawn on its right (cliffs.faces)
        d = b - a; ln = float(np.hypot(*d))
        nrm = np.array([d[1], -d[0], 0]) / ln
        g = grey if grey is not None else \
            cliffs.SHADE[0] + (cliffs.SHADE[1] - cliffs.SHADE[0]) * max(0.0, float(nrm @ L)) / math.hypot(L[0], L[1])
        s0 = (a[0] + a[1]) * cliffs.TEX_S % 64; s1 = s0 + ln * cliffs.TEX_S
        tm = 64 * round((za + zb) / 2 * cliffs.TEX_T / 64)
        lo_g = g * (cliffs.DEEP_SHADE if za <= deep + 1 else 1)
        quads.append(([(a[0], a[1], za), (b[0], b[1], za), (b[0], b[1], zb), (a[0], a[1], zb)],
                      [(s0, tm - za * cliffs.TEX_T), (s1, tm - za * cliffs.TEX_T), (s1, tm - zb * cliffs.TEX_T), (s0, tm - zb * cliffs.TEX_T)],
                      [(int(lo_g),) * 3] * 2 + [(int(g),) * 3] * 2))
    wall(P(ow, 0), P(-ow, 0), deep, z0)                           # the front, out: under the mouth and over it
    wall(P(ow, 0), P(-ow, 0), z1, top)
    up = int(cliffs.SHADE[0] + (cliffs.SHADE[1] - cliffs.SHADE[0]) * max(0.0, float(L[2])))
    pts = [P(-ow, -dp - HANGAR_WALL), P(ow, -dp - HANGAR_WALL), P(ow, 0), P(-ow, 0)]   # the lid: up, counter-clockwise
    s_ = [p[0] * cliffs.TEX_S for p in pts]; t_ = [p[1] * cliffs.TEX_S for p in pts]   # from above
    ds, dt = 64 * math.floor(min(s_) / 64), 64 * math.floor(min(t_) / 64)
    quads.append(([(p[0], p[1], top) for p in pts], [(x - ds, y - dt) for x, y in zip(s_, t_)], [(up,) * 3] * 4))
    return quads


def slave_mesh(E, base):
    """Slave I alone, for its own node (gallrun.c slave()): world units (scaled K) about its node's origin, its
    nose +y, up +z (it stands on its tail and flies so). The node turns it (heading) and puts it."""
    placed = {m: (Rm, t) for m, Rm, t in level_map.meshes_of(E)}
    ref = np.array(placed[SLAVE[0]][1])
    voff = {m: tuple(float(v) + (SLAVE_GUNS_OFF[j] if m == SLAVE_GUNS else 0) for j, v in enumerate(np.array(placed[m][1]) - ref))
            for m in SLAVE}
    img, h = build_image(E, SLAVE, base, xf=lambda x, y, z: (x * K, y * K, z * K), voff=voff, untextured=False)
    return glow(E, img, h, base)


SLAVE_GLOW = (0x80201F88, 0x80201F98)   # texture records of Slave I's engine glows: its two nozzles and the bar over
                                        # them, at its back (white in Gall; dark in our light: the user, they glow)


def emissive(img, h, base, which, rgba=b'\xff' * 4, both=False):
    """Parts lit by nothing (their colour whatever the light): the vertices of parts `which` (indices into h's list)
    set to rgba, their geometry drawn with lighting off (G_CLEARGEOMETRYMODE G_LIGHTING, the part's list as a
    sub-list, set again) and, both: from either side (G_CULL_BACK cleared and set again too)."""
    img = bytearray(img)
    get = lambda a: struct.unpack_from('>I', img, a - base)[0]
    mode = 0x00020000 | (0x00002000 if both else 0)
    for i in which:
        new = get(h['list'] + 4 * i); g = get(new + 0x28); a = g
        while get(a) >> 24 != 0xB8:
            if get(a) >> 24 == 0x04:
                v = get(a + 4)
                for k in range((get(a) & 0xFFFF) >> 9): img[v - base + 16 * k + 12:v - base + 16 * k + 16] = rgba
            a += 8
        img += bytes(-len(img) % 16)
        dl = base + len(img)
        img += struct.pack('>8I', 0xB6000000, mode, 0x06000000, g, 0xB7000000, mode, 0xB8000000, 0)
        struct.pack_into('>I', img, new + 0x28 - base, dl)
    return bytes(img)


def glow(E, img, h, base):
    """Slave I's engine glows lit by nothing (white whatever the light)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    src = [R(R(m + 0x10) + 4 * i) for m in SLAVE for i in range(R(m + 0xC))]
    src = [p for p in src if R(p + 0x24)]                          # (build_image's order: textured parts)
    which = [i for i, p in enumerate(src) if R(R(p + 0x24) + 8) in SLAVE_GLOW]
    assert len(which) == 3, f'{len(which)} glow parts (two nozzles and the bar expected)'
    return emissive(img, h, base, which), h


# Flames from the Outrider's engine glow (the base level, states/src_base.st: one flat quad across its stern, x +-5.8,
# z +-1.45, at y -11.4): copies of it turned and stretched, lit by nothing, seen from either side, two crossed ones
# (a plane each) so they show from all round.
OR_GLOW = 0x801A3C64
JET_TOP, JET_LEN, JET_W = (0.0, -0.45, 3.9), 1.9, 0.6   # Dash's jetpack flame (Gall units about his feet, his back
JET_RGBA = bytes((255, 150, 50, 255))                   # -y): from under the pack (part 15) down, this long and wide
BOLT_LEN, BOLT_W, BOLT_GAP = 30.0, 0.7, 2.2             # Slave I's shots (world): two side by side along +y (its barrels 2.2 apart)
BOLT_RGBA = bytes((255, 60, 40, 255))


def flames(Ea, base, quads, share_tag=''):
    """Copies of the glow quad, quads: [(f(x along it -5.8..5.8, w across it -1.45..1.45) -> xyz)]: (bytes, parts:
    their addresses), lit by nothing, both sides. share_tag: build_image's (its texture shared only with that tag's)."""
    out, parts = bytearray(), []
    for f, rgba in quads:
        img, h = build_image(Ea, [OR_GLOW], base + len(out), xf=lambda x, y, z, f=f: f(x, z), untextured=False,
                             share_tag=share_tag)
        img = emissive(img, h, base + len(out), range(h['parts']), rgba, both=True)
        lst = h['list'] - (base + len(out))
        parts += [int.from_bytes(img[lst + 4 * i:lst + 4 * i + 4], 'big') for i in range(h['parts'])]
        out += img; out += bytes(-len(out) % 16)
    return bytes(out), parts


def jet_flame(Ea, base):
    """Dash's jetpack flame, in his mesh's units (dash_mesh: DASH_FINE ths of a Gall unit about his feet)."""
    x0, y0, z0 = JET_TOP; k = DASH_FINE
    down = lambda u: z0 - (u + 5.8) / 11.6 * JET_LEN
    return flames(Ea, base, [(lambda u, w: ((x0 + w / 2.9 * JET_W) * k, y0 * k, down(u) * k), JET_RGBA),
                             (lambda u, w: (x0 * k, (y0 + w / 2.9 * JET_W) * k, down(u) * k), JET_RGBA)])


def bolts(Ea, base):
    """Slave I's two shots, about the node's origin, along +y (world units): a mesh (bytes, {parts, list, box})."""
    qs = []
    for dx in (-BOLT_GAP / 2, BOLT_GAP / 2):
        qs += [(lambda u, w, dx=dx: (dx + w / 2.9 * BOLT_W, u / 11.6 * BOLT_LEN, 0.0), BOLT_RGBA),
               (lambda u, w, dx=dx: (dx, u / 11.6 * BOLT_LEN, w / 2.9 * BOLT_W), BOLT_RGBA)]
    blob, parts = flames(Ea, base, qs)
    blob = bytearray(blob); blob += bytes(-len(blob) % 16)
    lst = base + len(blob); blob += b''.join(struct.pack('>I', p) for p in parts)
    m = BOLT_LEN; s16 = lambda v: int(round(v * 8))                # (a cube round the origin: Dash's lesson)
    box = base + len(blob)
    blob += b''.join(struct.pack('>hhhhhhhh', s16(x), s16(y), s16(z), 0, 0, 0, 0, 0)
                     for x in (-m, m) for y in (-m, m) for z in (-m, m))
    return bytes(blob), dict(parts=len(parts), list=lst, box=box)


# The white trail of a jump to lightspeed (gallrun.c trail(); the user, 2026-10-17): two crossed quads along +y from 0
# (its tail) to TRAIL_LEN (its head), TRAIL_W wide at the head, TRAIL_TAIL of that at the tail; the node scales them.
TRAIL_LEN, TRAIL_W, TRAIL_TAIL = 100.0, 16.0, 0.15      # (gallrun.c TRAIL_UNIT, TRAIL_MESH_W)
TRAIL_RGBA = b'\xff' * 4


def white_tlut(img, base, parts):
    """The palettes of these parts' textures made white (the glow quad's is pale cyan: white x it was not white)."""
    img = bytearray(img)
    get = lambda a: struct.unpack_from('>I', img, a - base)[0]
    for p in parts:
        a = get(get(get(p + 0x24) + 8) + 8); seg = tl = None
        while get(a) >> 24 != 0xB8:
            w0, w1 = get(a), get(a + 4)
            if w0 == 0xBC001006: seg = w1
            elif w0 >> 16 == 0xFD10: tl = 0x80000000 | (seg + (w1 & 0xFFFFFF))
            elif w0 >> 24 == 0xF0 and tl is not None:
                struct.pack_into('>%dH' % (((w1 >> 14) & 0x3FF) + 1), img, tl - base, *[0xFFFF] * (((w1 >> 14) & 0x3FF) + 1))
                tl = None
            a += 8
    return bytes(img)


def trail(Ea, base):
    """The jump's trail (mesh units): a mesh (bytes, {parts, list, box})."""
    half = lambda u, w: w / 2.9 * TRAIL_W * (TRAIL_TAIL + (1 - TRAIL_TAIL) * (u + 5.8) / 11.6)
    along = lambda u: (u + 5.8) / 11.6 * TRAIL_LEN
    blob, parts = flames(Ea, base, [(lambda u, w: (half(u, w), along(u), 0.0), TRAIL_RGBA),
                                    (lambda u, w: (0.0, along(u), half(u, w)), TRAIL_RGBA)], share_tag='white')
    blob = bytearray(white_tlut(blob, base, parts)); blob += bytes(-len(blob) % 16)
    lst = base + len(blob); blob += b''.join(struct.pack('>I', p) for p in parts)
    m = TRAIL_LEN; s16 = lambda v: int(round(v * 8))               # (a cube round the origin, as the shots')
    box = base + len(blob)
    blob += b''.join(struct.pack('>hhhhhhhh', s16(x), s16(y), s16(z), 0, 0, 0, 0, 0)
                     for x in (-m, m) for y in (-m, m) for z in (-m, m))
    return bytes(blob), dict(parts=len(parts), list=lst, box=box)


# The scene at the route's end (gallrun.c cine(); the user, 2026-10-12): the Falcon slows down and hovers by the pad
# ("Looks like we're here"), Dash jets up out of the tower onto its wall ("Hi, folks! ..."), Leia sends Leebo; Slave I
# rises behind Dash, fires and flies over the camera, front first, and away (no line of Fett's: the user),
# the Falcon goes round the tower after it, past the Outrider picking Dash up ("He's running! After him, Chewie!").
# Seen from the Falcon. Keys every CINE_STEP s as laid out (every CINE_KEY_EVERY-th written), played quicker (cine_time()) (CINE_FLOATS floats): t, eye, look, the Falcon (xyz, heading, roll), Slave I
# (xyz, heading), Dash (xyz, heading, pose: 0 none, 1 standing, 2 jetpack), the Outrider (xyz, heading, shown,
# roll), the view's zoom, Slave I's route node, camera shake -- world units, radians. The lines are LINES' ('end'),
# timed to these (CINE_LINES).
CINE_STEP = 0.05
CINE_KEY_EVERY = 2            # every 2nd laid-out key kept (0.1 s; cine_at() interpolates by time)
CINE_DENSE = ((14.4, 14.95), (22.4, 22.8))   # but every key (s as played) round Slave I's shots' shake (it starts and
                              # ends on the same key as with every key) and the Falcon's sharp turn (2.45 % of the
                              # screen off with every 2nd)
CINE_FLOATS = 32
CINE_HOVER = 54.0             # the Falcon slows down this far from the gantry's axis (as close as it goes: Dash seen),
CINE_HOVER_UP = 10.0          # this high over Dash's ledge (the camera looks down on him)
CINE_DRIFT = 1.7              # then goes slowly round the tower this far (radians) till it runs (the user: round it)
CINE_DRIFT_YAW = 0.25         # its nose turned this much off the tower, the way it drifts
OR_BACK, OR_SIDE, OR_UP = 80.0, 45.0, -6.0    # then after Slave I: this far behind it along its way, this far to its
                              # right, this much over it (gallrun.c ORC_*: the free flight)
SKY_TAN = 0.4                 # Slave I's climb: up this much a unit on (~22 degrees; straight up at 68 it looked like
                              # a rocket: the user) (gallrun.c SKY_TAN)
SKY_TOP = 3000.0              # it levels off this far over the route's end (gallrun.c SKY_TOP)
SKY_EASE = 0.5                # its climb there at most (SKY_TOP - its height) x this a second (gallrun.c SKY_EASE)
SKY_V = 300.0                 # (its speed as SKY is laid out: the same climb in time)
SKY_Q = 260.0                 # it is this far along its way 1.2 s after the pass
SKY_DS, SKY_LEN = 5.0, 20000.0
RAIL_STEP = 54.0              # the rail's nodes this far apart along it (level; stage 2's ~54)
OR_JOIN = 2.6                 # s: from its hover by Dash to the chase
OR_BEYOND, OR_ASIDE, OR_OVER = 30.0, 22.0, 6.0   # the Outrider hovers this far from Dash toward the Falcon, this far
                              # aside, this high over him
CINE_BACK, CINE_SIDE, CINE_UP = 6.0, 26.0, 8.0   # the camera: on the line from what it looks at past a point
                              # CINE_SIDE beside the Falcon's middle and CINE_UP over it, CINE_BACK beyond that point (the
                              # Falcon side on in the frame, beside what it looks at: not in front of it, the user)
CINE_LOOP_R = 120.0           # the Falcon's loop round the tower: this far out at its middle
CINE_PASS_UP = 24.0           # Slave I passes this far over the camera, upright (as it flies), its front (+y, the
                              # cockpit's side) along its way (the user: as the Falcon over the camera in the opening
                              # shot; turned to the camera it went sideways)
CINE_GAP = 200.0              # and is this far ahead of it along its way when the chase begins (380: too far, the user)
FLEE_UP = 20.0                # (over the route: gallrun.c flee())
LOOM_W = 1.0                  # as Slave I flies at the camera the view turns this far onto it (from what it held),
LOOP_MIN = 0.6                # the loop after Slave I turns the Falcon at least this far (radians) round the tower
                              # (pi: with the arc it went once more round the tower than needed, the user)
ARRIVE_WIDE = 1.0             # (its way out of the route's heading: a wide turn, not a sharp one at speed)
ARRIVE_K = 2.6                # the arrival takes this times its length / (300 + the arc's speed) s (2: a constant
                              # brake; it braked to a stop before, the user: too hard; more: eased out)
T_LOOP_AFTER = 0.3            # the Falcon's loop starts this long before Slave I is over it (still till then: Slave I
                              # comes straight at the camera, front on, not across it)
LOOM_BACK, LOOM_SIDE = 18.0, 0.5   # the camera this much further back, its side this share, as Slave I flies at it
                              # (the Falcon low in the frame, Slave I over it: the user)
LOOM_LEVEL, LOOM_HOP = 6.0, 0.7   # it comes this far over the camera's level, pulling up to CINE_PASS_UP over the
                              # last of its way from this share of it (the camera was in its hull at 8: the user)
LOOM_END = 0.3               # its speed over the camera: this share of its mean on the way in
LOOM_HOLD = 0.25              # and holds this long (s) before it passes over: it comes on, filling the frame
CINE_SHAKE = 4.0              # the camera shakes this much as Slave I fires
FOVY = 77.8                   # the game's vertical field of view here (degrees)
IN_FRAME = 0.78               # the Falcon's middle kept this share of the half view off the frame's middle at most
CAM_OVER = 15.0               # (unless this far over the gantry's top: the shaft's walls are gone, the user: the
                              # Falcon looked far off)
CAM_CLEAR = 115.0             # the camera at least this far from the tower's axis (world)
GLANCE_BACK = 90.0            # (the camera this much further back for it)
GLANCE = 0.85                 # how far the camera turns from behind the Falcon to Dash's jump into the Outrider
CINE_ZOOM = 0.42              # the field of view narrowed to this share while the camera is on Dash
CINE_CAM_EASE = 0.25          # s: the camera's eye and look eased over this
CINE_POI_EASE = 0.6           # s: the camera's point of interest eased over this
CINE_RISE_W = 150.0           # Slave I rises this far (world) out of the gantry (clear of its top)
DECK_Z = (688.0, 692.0)      # where Dash stands: right on the top of the tower's wall (Gall z 690), the point of it
                              # nearest the Falcon (a point at a set distance from the axis missed the wall: he stood
                              # in the air, the user)
DECK_IN = 0.0                 # (no inset: the wall's top is narrow)
DASH_FROM = 25.0              # Dash's take-off: this far (world) over Slave I's place inside the tower (out of its top)
DASH_UP = 125.0               # the climb's handle over the take-off (world: he starts ~85 under the top), and over the
DASH_DOWN = 12.0              # landing: a low arc over the rim (the user: he flew up too high)
DASH_AHEAD = 0.8              # Dash lands this far (radians) round the tower ahead of the Falcon then
DASH_LIFT = 1.5               # Dash this much over it (Gall units): his feet sank into the wall's top (the user)
VIEW_BACK, VIEW_UP, SHIP_DROP = 70.0, 22.0, 10.0   # gallrun.c: the flown camera
# Slave I rises out of the tower right behind Dash (the user: so it is seen), then the Outrider picks him up
T_ARRIVE, T_DASH, T_LAND, T_LEIA, T_RISE = 4.5, 4.4, 8.0, 10.8, 13.8
# then Slave I fires and flies at the camera and away (the user, 2026-10-13: the Falcon chases Slave I, not the other
# way round); the Falcon goes once round the tower, the Outrider picks Dash up behind it, then the Falcon goes after
T_FIRE, T_FLEE, T_PASS, T_OR_IN, T_JUMP, T_OR_OUT, T_RUN, T_END = 17.0, 17.6, 19.6, 19.2, 21.6, 22.4, 24.5, 28.5
CINE_SPEED = 0.85             # the scene played this much faster till the run (the user: a little quicker), then
CINE_SPEED_EASE = 1.0         # at its own pace again (the hand-over to free flight): eased over +-this (s)


def cine_time(t):
    """A time of the scene as laid out (the T_ above) -> as played (CINE_SPEED: quicker till T_RUN)."""
    a, b = T_RUN - CINE_SPEED_EASE, T_RUN + CINE_SPEED_EASE
    ts = np.linspace(0, max(t, 0), max(int(max(t, 0) / 0.01), 2))
    rate = CINE_SPEED + (1 - CINE_SPEED) * np.clip((ts - a) / (b - a), 0, 1)
    return float(np.trapezoid(rate, ts))


# when each line comes (s from the scene's start, as laid out; gall_asset LINES takes the gaps of these as
# played: CINE_LINES)
CINE_LINES_AT = [0.5, 10.0, 11.0, 13.2, 20.2, 20.6]   # Dash at his close-up's end, Lando after T_PASS
CINE_LINES = [cine_time(t) for t in CINE_LINES_AT]


DASH_SCREEN = (0.27, 0.70)    # where Dash should be seen while he stands (share of the frame from its top left):
                              # low on the left, clear of the radio lines' portrait and text (the user: he stood
                              # under them, at the tower's far corner)


def dash_spot(K_, spots):
    """Of the places on the tower's wall top (world), the one the scene's camera (keys K_) sees nearest DASH_SCREEN
    while Dash stands there and it is on him (T_LAND .. T_RISE), and in the frame."""
    rows = [k for k in K_ if T_LAND + 0.3 <= k[0] <= T_RISE]
    def at_screen(k, p):
        e = k[1:4]; l = k[4:7] - e; l /= np.linalg.norm(l); r = np.cross(l, [0, 0, 1]); r /= np.linalg.norm(r)
        u = np.cross(r, l); v = p - e; z = v @ l; tv = math.tan(math.radians(FOVY * k[27] / 2))
        return (0.5 + 0.5 * (v @ r) / z / (tv * 4 / 3), 0.5 - 0.5 * (v @ u) / z / tv) if z > 5 else (9.0, 9.0)
    def cost(p):
        xy = np.array([at_screen(k, p) for k in rows])
        out = np.clip(np.abs(xy - 0.5) - 0.42, 0, None).sum()     # (off the frame: out)
        return float(np.linalg.norm(xy - DASH_SCREEN, axis=1).mean() + 10 * out)
    return min(spots, key=cost)


def deck_spots(E):
    """Every place Dash can stand on the top of the tower's wall (Gall xyz): points on its up-facing faces between
    DECK_Z near the tower, DASH_LIFT over them."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    out, G = [], np.array(GANTRY)
    for m in PAD:
        for i in range(R(m + 0xC)):
            p = R(R(m + 0x10) + 4 * i)
            if not R(p + 0x24): continue
            for t in part_tris(E, p):
                n = np.cross(t[1] - t[0], t[2] - t[0])
                if n[2] <= 0.9 * np.linalg.norm(n) or not all(DECK_Z[0] <= v[2] <= DECK_Z[1] for v in t): continue
                c = t.mean(0)
                out += [q + np.array([0, 0, DASH_LIFT]) for q in [c] + [v + (c - v) * 0.25 for v in t] if np.hypot(*(q[:2] - G)) < 90]
    assert out, 'no wall top found round the gantry'
    return out


def deck_spot(E, toward):
    """Where Dash stands (Gall xyz): on the gantry's deck, the point of it farthest toward `toward` (a Gall
    direction: the Falcon's side), DECK_IN in from its edge."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    best, spot = -1e9, None
    G = np.array(GANTRY)
    for m in PAD:
        for i in range(R(m + 0xC)):
            p = R(R(m + 0x10) + 4 * i)
            if not R(p + 0x24): continue
            for t in part_tris(E, p):
                n = np.cross(t[1] - t[0], t[2] - t[0])
                if n[2] <= 0.9 * np.linalg.norm(n) or not all(DECK_Z[0] <= v[2] <= DECK_Z[1] for v in t): continue
                c = t.mean(0)
                for q in [c] + [v + (c - v) * 0.25 for v in t]:            # points on it
                    sc = float((q[:2] - G) @ toward)
                    if sc > best and np.hypot(*(q[:2] - G)) < 90: best, spot = sc, q
    assert spot is not None, 'no deck found round the gantry'
    to_axis = G - spot[:2]; to_axis /= np.hypot(*to_axis)
    return np.array([*(spot[:2] + to_axis * DECK_IN), spot[2] + DASH_LIFT])


def cine_keys(path, at, E6b, n_ext, over=None, tries=5, dash=None):
    """(keys as bytes, count, rail). path: the route (its end is where the scene starts). over: the camera's way (None:
    laid out once to find it, then again: Slave I passes over it). rail: the route on after the scene (the chase, as
    stage 2: Chor carries the Falcon on after Slave I, the player the gunner; the user, 2026-10-13): from where the
    Falcon is at the scene's end along Slave I's way (SKY), RAIL_STEP apart."""
    P = np.asarray(path); e = len(P) - 4
    E = P[e].copy()
    w = to_world(at)
    placed = {m: (Rm, t) for m, Rm, t in level_map.meshes_of(E6b)}
    st = placed[SLAVE[0]][1]
    rest = np.array(w(st[0], st[1], st[2] + SLAVE_UP))              # Slave I inside the gantry
    gx = np.array(w(GANTRY[0], GANTRY[1], 690.0))                  # the gantry's top, on its axis
    d = gx[:2] - E[:2]; d /= np.hypot(*d); l = np.array([-d[1], d[0]]); r = -l
    up = lambda h: np.array([0, 0, h])
    ease = lambda u: 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0), 1))
    H0 = gx[:2] - d * CINE_HOVER                                   # Dash lands on the side the Falcon has gone round
    Ta0 = max(ARRIVE_K * float(np.hypot(*(H0 - E[:2]))) * 1.1 / 310.0, 2.0)   # to by then (drift() below)
    aL = math.atan2(*(H0 - gx[:2])[::-1]) + CINE_DRIFT * (T_LAND - Ta0) / (T_FLEE - Ta0)
    fw = np.array([math.cos(aL + DASH_AHEAD), math.sin(aL + DASH_AHEAD)])   # (a little ahead of the Falcon round
    # the tower: under it, he was hidden by its hull)
    cy, sy_ = math.cos(-at['yaw']), math.sin(-at['yaw'])          # (that side in Gall's frame)
    FL = np.array([*(gx[:2] + fw * CINE_HOVER), gx[2]])            # (the Falcon then)
    L = min((np.array(w(*q)) for q in deck_spots(E6b)), key=lambda q: float(np.linalg.norm(q - FL)))   # the spot
    # nearest the Falcon (the farthest-out spot toward it was the tower's far rim, seen past its opening: the user)
    Lc = L                                                         # (the camera looks there while he stands; he
    if dash is not None: L = dash                                  # stands where it sees him clear: DASH_SCREEN)
    H = np.array([*(gx[:2] - d * CINE_HOVER), Lc[2] + CINE_HOVER_UP]) # the Falcon's hover
    ease = lambda u: 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0), 1))
    lerp = lambda a, b, u: a + (b - a) * u
    def bez(p0, p1, p2, p3, u):
        return (1 - u) ** 3 * p0 + 3 * (1 - u) ** 2 * u * p1 + 3 * (1 - u) * u ** 2 * p2 + u ** 3 * p3
    head = lambda v: math.atan2(v[1], v[0])
    # the Falcon: in from the route's end, slowing to the hover (its speed 300 at the start), then away
    D = float(np.linalg.norm(H - E)); Ta = max(ARRIVE_K * D * 1.1 / 310.0, 2.0)   # (eased out from 300 to the arc's
    # ~10 along a way ~1.1 times the straight line: no hard stop)
    a0 = head(H[:2] - gx[:2])                                      # then it drifts slowly round the tower (the user:
    Rt = P[e::-1, :3]                                              # (the route from its end backwards: Slave I's way)
    w_d = CINE_DRIFT / (T_FLEE - Ta)                               # (round the tower at this rate: slowly, never still)
    T_LOOP = T_PASS - T_LOOP_AFTER
    a_fl = a0 + w_d * (T_RUN - Ta)                                 # the loop: round the tower till its heading is the
    hr = head(Rt[min(40, len(Rt) - 1)] - Rt[min(10, len(Rt) - 1)])   # route's back (the user: it turns round to go after
    loop = (hr - math.pi / 2 - a_fl) % (2 * math.pi)                # Slave I), at least half way round
    if loop < LOOP_MIN: loop += 2 * math.pi
    def speed_up(x, a=0.45):                                      # 0..1 eased in (over a), not out: the loop goes
        x = min(max(x, 0.0), 1.0)                                  # straight on after Slave I at its end speed (the
        return (x * x / (2 * a) if x < a else x - a / 2) / (1 - a / 2)   # user: it slowed as if waiting there)
    def drift(t):                                                  # not standing still): CINE_DRIFT till Slave I
        u = ease((t - Ta) / (T_FLEE - Ta)) if t > Ta else 0.0      # flees (the user: on slowly round an arc, no
        u2 = speed_up((t - T_LOOP) / (T_RUN - T_LOOP))             # braking), then once round the tower (CINE_LOOP_R
        a = a0 + w_d * max(t - Ta, 0.0) + loop * u2               # out from half way on: no slowing), speeding up
        rr = CINE_HOVER + (CINE_LOOP_R - CINE_HOVER) * ease(2 * u2)
        return np.array([gx[0] + math.cos(a) * rr, gx[1] + math.sin(a) * rr, H[2] + 6 * u]), a
    # Slave I's way after it has flown over the camera (the user, 2026-10-13: the chase goes up into space; straight
    # up it looked like a rocket; down the canyon, climbing): on along the way it came (fd) SKY_Q, over to the route
    # back and along it out of the clearing and down the canyon, its bends all the way, climbing SKY_TAN a unit along
    # it, levelling off at SKY_TOP over the route's end (SKY_EASE): gallrun.c flee()'s law. SKY: its points, LS their
    # distance along it (level: its speed is level)
    S_up = rest + up(CINE_RISE_W)
    iP = int(round(T_PASS / CINE_STEP))
    Pp = (drift(T_PASS)[0] if over is None else over[iP]) + up(LOOM_LEVEL)   # (level with the camera, then up over it)
    fd = Pp[:2] - S_up[:2]; fd /= np.hypot(*fd)
    SK0 = Pp + up(CINE_PASS_UP - LOOM_LEVEL); Q = SK0 + np.array([*(fd * SKY_Q), 10.0])
    top = E[2] + SKY_TOP
    k_s = int(np.argmin(np.linalg.norm(P[:e + 1, :2] - Q[:2], axis=1)))   # (the route node by Q)
    SKY = [SK0 + (Q - SK0) * u for u in np.linspace(0, 1, int(SKY_Q / SKY_DS), endpoint=False)]
    hJ = Q[2] - P[k_s, 2]
    J = P[k_s] + up(hJ)
    SKY += [Q + (J - Q) * u for u in np.linspace(0, 1, max(int(np.hypot(*(J - Q)[:2]) / SKY_DS), 1), endpoint=False)]
    SRF = [-1.0] * len(SKY)                                        # (the route node it is at: -1 off the route)
    f, h = float(k_s), hJ
    while len(SKY) * SKY_DS < SKY_LEN and f > 1:                   # down the canyon, climbing, its bends all the way
        k = int(f); fr = f - k
        a_, b_ = P[k], P[k + 1]; seg = float(np.hypot(*(b_ - a_)[:2])) or 1.0
        p_ = a_ + (b_ - a_) * fr
        SKY.append(p_ + up(h)); SRF.append(f)
        f -= SKY_DS / seg; h += min(SKY_TAN, (top - p_[2] - h) * SKY_EASE / SKY_V) * SKY_DS
    SKY = np.array(SKY); SRF = np.array(SRF)
    LS = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(SKY[:, :2], axis=0).T))])
    for _ in range(3):                                             # the loop ends on the heading of the route where
        Hend, aend = drift(T_RUN)                                  # the Falcon joins it (k_f, a little on along its
        Tg = np.array([math.cos(aend + math.pi / 2), math.sin(aend + math.pi / 2)])   # way): no turn back after it
        k_f = int(np.argmin(np.linalg.norm(SKY[:, :2] - (Hend[:2] + Tg * 220), axis=1)))
        hr = head(SKY[min(k_f + 8, len(SKY) - 1)][:2] - Hend[:2])   # (at where it joins Slave I's way up; at the
        # route's own heading there it made an S on the way to it)
        loop = (hr - math.pi / 2 - a_fl) % (2 * math.pi)
        if loop < LOOP_MIN: loop += 2 * math.pi
    Hend, aend = drift(T_RUN)
    Tg = np.array([math.cos(aend + math.pi / 2), math.sin(aend + math.pi / 2)])
    k_f = int(np.argmin(np.linalg.norm(SKY[:, :2] - (Hend[:2] + Tg * 220), axis=1)))
    esc = [Hend, Hend + np.array([*(Tg * 110), 25])] + [SKY[k] for k in range(k_f, len(SKY), 8)]   # (up after it; a
    # level second point made the way dip, nose down, before it climbed)
    H0 = H                                                         # (the arrival ends where the drift starts, at its
    dE = np.array([*(P[e + 1, :2] - P[e - 1, :2]), 0.0]); dE /= max(np.linalg.norm(dE), 1e-6)   # speed): its way a
    vH = (drift(Ta + 0.05)[0] - drift(Ta)[0]) / 0.05; v1 = float(np.linalg.norm(vH))   # curve from the route's
    ch = float(np.linalg.norm(H0 - E))                             # heading into the arc's, gone along it slowing
    uu = np.linspace(0, 1, 300)[:, None]                           # from 300 to the arc's speed (a cubic in time:
    Ap = ((2 * uu ** 3 - 3 * uu ** 2 + 1) * E + (uu ** 3 - 2 * uu ** 2 + uu) * ARRIVE_WIDE * ch * dE   # no stop, no
          + (-2 * uu ** 3 + 3 * uu ** 2) * H0 + (uu ** 3 - uu ** 2) * ch * vH / max(v1, 1e-6))   # speeding up)
    La = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Ap, axis=0), axis=1))])
    ab = np.linalg.solve([[Ta ** 2, Ta ** 3], [2 * Ta, 3 * Ta ** 2]], [La[-1] - 300.0 * Ta, v1 - 300.0])
    W = [esc[0] - (esc[1] - esc[0])] + esc + [esc[-1] + (esc[-1] - esc[-2])]
    def cr(p0, p1, p2, p3, u):
        return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
    pts = np.array([cr(W[i - 1], W[i], W[i + 1], W[i + 2], u) for i in range(1, len(W) - 2) for u in np.linspace(0, 1, 60, endpoint=False)])
    Ls = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    ts = np.arange(0, T_END + 1e-6, CINE_STEP)
    v_loop = float(np.linalg.norm(drift(T_RUN)[0] - drift(T_RUN - CINE_STEP)[0])) / CINE_STEP   # (the loop's end speed:
    run_s = np.cumsum([0] + [CINE_STEP * (v_loop + (260 - v_loop) * min((t - T_RUN) / 1.5, 1)) * (t > T_RUN)
                             for t in ts[1:]])                     # the run goes on from it, up to 260)
    fal, fyaw = [], []
    for i, t in enumerate(ts):
        if t < Ta:                                                 # slowing (from 300 along the route) into the arc
            sa = 300.0 * t + ab[0] * t * t + ab[1] * t ** 3
            p = np.array([np.interp(sa, La, Ap[:, k]) for k in range(3)])
            q = np.array([np.interp(sa + 4, La, Ap[:, k]) for k in range(3)])
            y = head(q - p)                                        # (its nose along its way: it went sideways, the user)
        elif t < T_RUN:
            p, a = drift(t); p = p + up(1.5 * math.sin((t - Ta) * 1.7))
            y = head(drift(t + 0.05)[0] - drift(t)[0])             # along its way round (anticlockwise: the tower on
            # its left; the camera beside it sees it side on; by its way: the loop widens, a + pi/2 went sideways)
        else:
            sv = run_s[i]
            p = np.array([np.interp(sv, Ls, pts[:, k]) for k in range(3)])
            q = np.array([np.interp(sv + 6, Ls, pts[:, k]) for k in range(3)])
            y = head(q - p) if sv > 1 else aend + math.pi / 2
        fal.append(p); fyaw.append(y)
    from scipy.ndimage import gaussian_filter1d
    fyaw = gaussian_filter1d(np.unwrap(fyaw), 0.12 / CINE_STEP, mode='nearest')   # (no kinks in its turn; more lagged
    # its nose behind its way: sideways at speed in a bend)
    froll = np.clip(-np.gradient(fyaw, CINE_STEP) * 0.45, -0.8, 0.8)
    fv = np.gradient(np.array(fal), CINE_STEP, axis=0)            # its pitch (nose down +) by its way, from the run on
    fpitch = -np.arctan2(fv[:, 2], np.hypot(fv[:, 0], fv[:, 1]) + 1e-6) * np.array([ease((t - T_RUN + 1.0) / 1.0) for t in ts])
    fpitch = gaussian_filter1d(fpitch, 0.15 / CINE_STEP, mode='nearest')
    # Dash: in on the jetpack from the left, high, down onto the rim; then over to the Outrider
    # Dash takes off from inside the tower, where Slave I stands (the user), straight up out of its top on the
    # jetpack and over onto the wall's top
    S0 = rest + up(DASH_FROM)
    fJ = fal[int(T_JUMP / CINE_STEP)]                               # the Outrider comes in from the far side of the
    ux = L[:2] - fJ[:2]; ux /= np.hypot(*ux); sx = np.array([-ux[1], ux[0]])   # tower, at the Falcon, and hovers
    O_h = L + np.array([*(ux * OR_BEYOND + sx * OR_ASIDE), OR_OVER])   # beyond Dash as the Falcon sees him (from behind
    # the Falcon it flew in close by it, as if they would hit: the user; the shaft's wall that hid that side is gone)
    O_in = O_h + np.array([*(ux * 260 + sx * 300), 120])             # (inside the clearing: OPEN_R)
    # Slave I: rises out of the tower, turns to the Falcon, fires (T_FIRE), flies at the camera and over the Falcon
    # (T_PASS), then up along SKY, ahead of the Falcon by CINE_GAP when the free flight begins
    T_Q = T_PASS + 1.2
    sF = LS[int(np.argmin(np.linalg.norm(SKY - fal[-1], axis=1)))]   # the Falcon's place along SKY at the end
    v_s = max((sF + CINE_GAP - SKY_Q) / (T_END - T_Q), 60.0)
    B_in = (S_up, S_up + np.array([*(fd * 40), 15]), Pp - np.array([*(fd * 120), 0]), Pp)   # (its way in, by
    ub = np.linspace(0, 1, 400); Bp = np.array([bez(*B_in, u) for u in ub])                  # length)
    Lb = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Bp, axis=0), axis=1))]); D_in = Lb[-1]
    v_end = D_in * LOOM_END / (T_PASS - T_FLEE)
    T2 = T_Q - T_PASS                                              # (off the pass: SKY_Q along SKY by T_Q, at v_s then)
    qa = np.linalg.solve([[T2 ** 2, T2 ** 3], [2 * T2, 3 * T2 ** 2]], [SKY_Q - v_end * T2, v_s - v_end])
    def sky_at(sv):
        return np.array([np.interp(sv, LS, SKY[:, k]) for k in range(3)])
    def sky_node(sv):                                              # (the route node there, -1 off the route)
        i = int(np.clip(np.searchsorted(LS, sv), 1, len(LS) - 1))
        if SRF[i - 1] < 0 or SRF[i] < 0: return -1.0
        return float(np.interp(sv, LS[i - 1:i + 1], SRF[i - 1:i + 1]))
    def slave_s(t):                                                # (its place along SKY from T_PASS on)
        if t < T_Q: y = max(t - T_PASS, 0.0); return v_end * y + qa[0] * y * y + qa[1] * y ** 3
        return SKY_Q + (t - T_Q) * v_s
    def slave_at(t):
        """(xyz, route node it is at or -1)"""
        if t < T_FLEE: return rest + up(CINE_RISE_W) * ease((t - T_RISE) / 3.0), -1.0
        if t < T_PASS:                                             # quick off the tower, then slow as it comes
            x = (t - T_FLEE) / (T_PASS - T_FLEE)                   # over the camera (the user: it looms, huge)
            sd = D_in * ((1 - LOOM_END) * x * (2 - x) + LOOM_END * x)
            drift_ = 0 if over is None else over[min(int(round(t / CINE_STEP)), len(over) - 1)] - over[iP]
            hop = up(CINE_PASS_UP - LOOM_LEVEL) * ease((sd / D_in - LOOM_HOP) / (1 - LOOM_HOP))   # (pulls up over it)
            return bez(*B_in, float(np.interp(sd, Lb, ub))) + drift_ * (sd / D_in) ** 2 + hop, -1.0   # (at the camera as it
            # moves on round: it comes straight at it, front on)
        return sky_at(slave_s(t)), (sky_node(slave_s(t)) if t >= T_Q else -1.0)   # then away and up
    SL = [slave_at(t) for t in ts]
    def or_chase(t):                                               # the Outrider after Slave I too (the user): along
        sv = slave_s(t) - OR_BACK                                  # SKY OR_BACK behind it, OR_SIDE to its right, OR_UP
        assert sv >= 0, 'the Outrider joins Slave I before it is far enough up its way'   # over (gallrun.c or_cine())
        return sky_at(sv) + np.array([fd[1] * OR_SIDE, -fd[0] * OR_SIDE, OR_UP]), head(fd)
    T_J = max(T_OR_OUT + OR_JOIN, next(t for t in ts if t > T_PASS and slave_s(t) > OR_BACK + 30))   # it joins the chase
    J1 = or_chase(T_J)[0]; vJ = (or_chase(T_J + 0.05)[0] - or_chase(T_J - 0.05)[0]) / 0.1
    OP, OY = [], []
    for t in ts:
        oin = head(O_h - O_in)
        if t < T_OR_IN: op, oy = O_in, oin
        elif t < T_OR_OUT:
            u = 1 - (1 - min((t - T_OR_IN) / (T_JUMP - T_OR_IN), 1)) ** 2; op, oy = lerp(O_in, O_h, u), oin
        elif t < T_J:
            DJ = T_J - T_OR_OUT; u = (t - T_OR_OUT) / DJ; op = bez(O_h, O_h + up(4), J1 - vJ * DJ / 3, J1, u)
            nx = bez(O_h, O_h + up(4), J1 - vJ * DJ / 3, J1, min(u + 0.02, 1))
            oy = oin + (((head(nx - op) - oin) + math.pi) % (2 * math.pi) - math.pi) * ease((t - T_OR_OUT) / 1.0)
        else: op, oy = or_chase(t)
        OP.append(op); OY.append(oy)
    OY = gaussian_filter1d(np.unwrap(OY), 0.25 / CINE_STEP, mode='nearest')
    ov = np.gradient(np.array(OP), CINE_STEP, axis=0)             # its pitch (nose down +) by its way, once it goes
    OPITCH = gaussian_filter1d(-np.arctan2(ov[:, 2], np.hypot(ov[:, 0], ov[:, 1]) + 1e-6)
                               * np.array([ease((t - T_OR_OUT) / 0.6) for t in ts]), 0.15 / CINE_STEP, mode='nearest')
    OR_ROLL = np.clip(-np.gradient(OY, CINE_STEP) * 0.35, -0.6, 0.6) * [1 - ease((t - T_END + 2.0) / 1.0) for t in ts]
    from scipy.ndimage import gaussian_filter1d
    SP = gaussian_filter1d(np.array([p for p, _ in SL]), 0.3 / CINE_STEP, axis=0, mode='nearest')   # (no kinks: the
    sy0 = at['yaw'] + math.pi / 2                                  # user, it twitched)
    lv = head(fd)                                                  # its heading: as it stands while it rises, turned
    SY = []                                                        # to the way it will leave before it goes, then
    for i, t in enumerate(ts):                                     # along its flight
        if t < T_FLEE: y = sy0 + ((((lv - sy0) + math.pi) % (2 * math.pi)) - math.pi) * ease((t - T_RISE - 1.5) / 1.8)
        else:
            v = SP[min(i + 1, len(SP) - 1)] - SP[max(i - 1, 0)]
            y = head(v) if np.hypot(*v[:2]) > 0.5 else SY[-1]
        SY.append(y)
    SY = gaussian_filter1d(np.unwrap(SY), 0.5 / CINE_STEP, mode='nearest')
    keys, pois, places = [], [], []
    for i, t in enumerate(ts):
        fp, fy = fal[i], fyaw[i]
        # Dash
        if t < T_DASH: dp, dpose = S0, 0
        elif t < T_LAND:
            u = (t - T_DASH) / (T_LAND - T_DASH); u = 1 - (1 - u) ** 1.6
            dp = bez(S0, S0 + up(DASH_UP), L + up(DASH_DOWN), L, u); dpose = 2
        elif t < T_JUMP: dp, dpose = L, 1
        elif t < T_OR_OUT - 0.3:
            u = ease((t - T_JUMP) / (T_OR_OUT - 0.3 - T_JUMP)); dp = bez(L, L + up(12), O_h + up(16), O_h + up(5), u); dpose = 2
        else: dp, dpose = O_h, 0
        if T_DASH <= t < T_LAND - 0.2:
            nx = bez(S0, S0 + up(DASH_UP), L + up(DASH_DOWN), L, min(1, 1 - (1 - (t + 0.1 - T_DASH) / (T_LAND - T_DASH)) ** 1.6))
            dy = head(nx - dp) if np.hypot(*(nx - dp)[:2]) > 0.05 else head(-d)
        elif t < T_JUMP:
            dy = head(fp - L)                                       # faces the Falcon as it goes round
        else:
            dy = head(O_h - L)
        # the Outrider
        op, oy, osh, oroll = OP[i], OY[i], float(t >= T_OR_IN), float(OR_ROLL[i])
        # Slave I
        S, sroute, sy = SP[i], SL[i][1], SY[i]
        shake = CINE_SHAKE if any(0 <= t - f0 < 0.15 for f0 in (T_FIRE, T_FIRE + 0.35)) else 0.0
        # what the camera looks at (the camera rides behind the Falcon: from its side of things, the user)
        if t < T_DASH: poi = gx
        elif t < T_RISE: poi = dp + up(2) + (Lc - L) * ease((t - T_DASH) / (T_LAND - T_DASH))   # (on to Lc)
        elif t < T_FLEE: poi = lerp(Lc + up(2), S + up(4), 0.6 * ease((t - T_RISE) / 1.5))
        elif t < T_PASS + 0.4:                                     # Slave I flies at the camera: the view on it,
            Sc = SP[int(round(min(t, T_PASS - LOOM_HOLD) / CINE_STEP))]   # then held as it comes on, huge, and over
            poi = lerp(Lc + up(2), Sc + up(4), 0.6 + (LOOM_W - 0.6) * ease((t - T_FLEE) / 0.8))   # (the user)
            places.append(lerp(Lc + up(2), S_up + up(4), 0.6))     # (the camera placed as for the held view: Slave
            # I aims at it, it must not follow Slave I)
        else: poi = lerp(dp, O_h, 0.35) + up(3)                    # the Outrider picks Dash up
        eye = look = fp
        pois.append(poi)
        if len(places) < len(pois): places.append(poi)
        keys.append([t, *eye, *look, *(fp - up(SHIP_DROP)), fy, float(froll[i]), *S, sy, *dp, dy, float(dpose),
                     *op, oy, float(osh), oroll, 1.0, sroute, shake, float(fpitch[i]), float(OPITCH[i])])
    K_ = np.array(keys)
    from scipy.ndimage import gaussian_filter1d                    # the camera: behind the Falcon, turned to look
    F, FY = K_[:, 7:10] + np.array([0, 0, SHIP_DROP]), K_[:, 10]   # past it at the point of interest (eased)
    poi = gaussian_filter1d(np.array(pois), CINE_POI_EASE / CINE_STEP, axis=0, mode='nearest')
    place = gaussian_filter1d(np.array(places), CINE_POI_EASE / CINE_STEP, axis=0, mode='nearest')
    blend = []
    for i, t in enumerate(ts):
        fp = F[i]; hd = np.array([math.cos(FY[i]), math.sin(FY[i])])
        ce = np.array([*(fp[:2] - hd * VIEW_BACK), fp[2] + VIEW_UP]); cl = ce + np.array([*(hd * VIEW_BACK * 2), -VIEW_UP])
        to = place[i][:2] - fp[:2]; to /= max(np.hypot(*to), 1e-6)
        side = np.array([-to[1], to[0]])                         # the line of sight to what it looks at passes
        lw = ease((t - T_FLEE) / 0.8) * (1 - ease((t - T_PASS) / 0.8))   # (Slave I flying at it: behind the Falcon)
        q = np.array([*(fp[:2] + side * CINE_SIDE * (1 - (1 - LOOM_SIDE) * lw)), fp[2] + CINE_UP])   # CINE_SIDE beside the Falcon's middle (clear of
        v = q - place[i]; v /= np.linalg.norm(v)                   # its hull: it is seen side on, low beside it) and
        gl = GLANCE * ease((t - T_JUMP + 1.4) / 0.9) * (1 - ease((t - T_OR_OUT - 0.2) / 0.9))   # a glance from the loop
        # at Dash jumping into the Outrider (the user: it must be caught)
        pe = q + v * (CINE_BACK + LOOM_BACK * lw + GLANCE_BACK * gl / GLANCE); pl = poi[i]   # (the camera on that line: further back for
        # the glance, so the Falcon and the pickup both fit)
        w = max(ease((t - Ta + 0.5) / 2.0) * (1 - ease((t - T_PASS - 0.3) / 2.2)), gl)   # chase -> looking past it -> chase (once
        # Slave I has passed: the loop is the Falcon turning round after it, seen from behind; the user)
        K_[i, 1:4] = lerp(ce, pe, w)                               # the look blended by its heading and pitch (a
        dc, dp_ = cl - ce, pl - pe                                 # lerp of the look points swung the view round
        blend.append((math.atan2(dc[1], dc[0]), math.atan2(dp_[1], dp_[0]),   # through the eye: the user, jerky)
                      math.atan2(dc[2], np.hypot(*dc[:2])), math.atan2(dp_[2], np.hypot(*dp_[:2])), w))
        z = ease((t - T_DASH + 0.3) / 1.2) * (1 - ease((t - T_PASS + LOOM_HOLD) / 1.0))   # zoomed in on Dash (he is ~3.5 tall:
        K_[i, 27] = 1 - (1 - CINE_ZOOM) * max(z * w, gl)          # tiny from the Falcon), held as Slave I rises
        # (the user: not zoomed out then) and as it flies at the camera, till it is over it
    yc, yp, pc, pp, wb = (np.array(v) for v in zip(*blend))
    dy = np.unwrap(yp) - np.unwrap(yc)                             # (continuous: the way round never flips mid-turn)
    dy -= 2 * math.pi * np.round(dy[np.argmax(wb)] / (2 * math.pi))
    yy, pq = np.unwrap(yc) + dy * wb, pc + (pp - pc) * wb
    K_[:, 4:7] = K_[:, 1:4] + 100 * np.stack([np.cos(pq) * np.cos(yy), np.cos(pq) * np.sin(yy), np.sin(pq)], -1)
    if over is not None:                                           # its nose on the camera as it comes (its way
        for i, t in enumerate(ts):                                 # is at it: so it is not seen sideways)
            b = ease((t - T_FLEE - 0.2) / 0.6) * (1 - ease((t - T_PASS + 0.35) / 0.3))
            if b > 0:
                fc = head(K_[i, 1:4] - K_[i, 12:15])
                K_[i, 15] += (((fc - K_[i, 15]) + math.pi) % (2 * math.pi) - math.pi) * b
    def keep_falcon(ease_zoom):
        # The Falcon always in the frame (the user: we still fly the Falcon): if it falls out of the view, the view is
        # widened (zoom out) so it and what the camera looks at both fit, and turned toward it to the frame's edge
        for i in range(len(K_)):
            ey = K_[i, 1:4]; u = K_[i, 4:7] - ey; u /= np.linalg.norm(u)
            f = K_[i, 7:10] + np.array([0, 0, SHIP_DROP]) - ey; fl = np.linalg.norm(f)
            if fl < 1e-3: continue
            f /= fl
            sep = math.acos(float(np.clip(u @ f, -1, 1)))
            lim = lambda z: math.radians(FOVY * z / 2) * IN_FRAME
            z = K_[i, 27]
            if sep > lim(z): z = min(max(z, sep * 0.6 / lim(1.0)), 1.0)
            K_[i, 27] = z
            if sep > lim(z):
                k = (sep - lim(z)) / sep                                 # turned toward it, along the great circle
                v = np.sin((1 - k) * sep) * u + np.sin(k * sep) * f; v /= np.linalg.norm(v)
                K_[i, 4:7] = ey + 100 * v
        if ease_zoom: K_[:, 27] = gaussian_filter1d(K_[:, 27], CINE_CAM_EASE / CINE_STEP, mode='nearest')
    for i in range(len(K_)):                                       # the camera never inside the tower's rock (behind
        r_ = K_[i, 1:3] - gx[:2]; rl = float(np.hypot(*r_))        # the kept wall the pillar goes up to the rim: a
        bk = np.array([math.cos(at['back']), math.sin(at['back'])])   # view of rock only, the user; the kept wall is
        if rl < CAM_CLEAR and r_ @ bk > -20 and K_[i, 3] < gx[2] + CAM_OVER:   # (over the tower's top: free)                       # the one on the far side from the approach)
            sh = r_ / max(rl, 1e-6) * (CAM_CLEAR - rl)
            K_[i, 1:3] += sh; K_[i, 4:6] += sh
    keep_falcon(True)
    for c in range(1, 7):                                          # the camera eased (the user: jerky)
        K_[:, c] = gaussian_filter1d(K_[:, c], CINE_CAM_EASE / CINE_STEP, mode='nearest')
    keep_falcon(False)                                             # (again: the easing moved it off a little)
    for c in (15, 19, 24): K_[:, c] = np.unwrap(K_[:, c])
    assert K_.shape[1] == CINE_FLOATS
    rail = [fal[-1]] + [sky_at(sF + RAIL_STEP * k) for k in range(1, int((LS[-1] - sF) / RAIL_STEP) - 2)]
    eye = K_[:, 1:4].copy()                                        # again, Slave I flying at the camera's way
    if dash is None and over is not None:                          # Dash's spot: where the camera (as it is now)
        dash = dash_spot(K_, [np.array(to_world(at)(*q)) for q in deck_spots(E6b)])   # sees him clear of the lines
        return cine_keys(path, at, E6b, n_ext, eye, tries, dash)
    if tries and (over is None or np.abs(eye - over).max() > 2):    # (a few times over, if need be)
        return cine_keys(path, at, E6b, n_ext, eye, tries - 1, dash)
    K_[:, 0] = [cine_time(t) for t in K_[:, 0]]                    # (played quicker: CINE_SPEED)
    keep = [i for i in range(len(K_)) if i % CINE_KEY_EVERY == 0   # (sparser: CINE_KEY_EVERY, but CINE_DENSE;
            or any(lo <= K_[i, 0] <= hi for lo, hi in CINE_DENSE)]  # the last key kept)
    if keep[-1] != len(K_) - 1: keep.append(len(K_) - 1)
    K_ = K_[keep]
    return b''.join(struct.pack('>%df' % CINE_FLOATS, *k) for k in K_), len(K_), rail


# Dash in the end scene (the user: he comes in on his jetpack over the pad, lands on the gantry's edge, Leebo picks
# him up in the Outrider): his model as Gall draws it, two poses (states/gall_dash_stand.st, gall_dash_jet.st:
# harness/states_dash.py; loaded and dumped 2 frames on, before the pose moves), each a mesh of its own for
# his node (gallrun.c dash()): world units (K) about his feet, his facing +y, up +z.
DASH_STATES = ('gall_dash_stand.st', 'gall_dash_jet.st')
DASH_BODY = [0x801F3358 + 0x18 * i for i in range(19)]   # his meshes (head, body, limbs, the jetpack, the gun)
DASH_FINE = 2.0           # his vertices in this fraction of a Gall unit (he is ~5 tall: 1/8 of a world unit was coarse;
                          # 8 made his mesh box +-352: the game did not draw him with it, it does with Slave I's +-116)


def humn(E):
    """Dash (class Humn) in RAM E: his place and his heading (degrees; facing = heading + 90)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    F = lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]
    a = 0x80112808
    while R(a) != 0x48756D6E: a += 0x30
    p = R(a + 0x10)
    return np.array([F(p + 0x50 + 4 * i) for i in range(3)]), F(p + 0x8C)


def dash_mesh(E, base):
    """Dash as posed in E: (bytes, {parts, list, box, ...}) at base."""
    placed = {m: (Rm, t) for m, Rm, t in level_map.meshes_of(E)}
    pos, yaw = humn(E)
    c, s = math.cos(math.radians(-yaw)), math.sin(math.radians(-yaw))
    voff = {m: (placed[m][0], placed[m][1]) for m in DASH_BODY}
    def xf(x, y, z):                                              # (Gall) -> about his feet, his facing +y, in
        x, y, z = x - pos[0], y - pos[1], z - pos[2]                # DASH_FINE ths of a Gall unit (his node scales
        return ((c * x - s * y) * DASH_FINE, (s * x + c * y) * DASH_FINE, z * DASH_FINE)   # by K / DASH_FINE)
    return fit_boxes(*build_image(E, DASH_BODY, base, xf=xf, voff=voff, untextured=False), base)


def fit_boxes(img, h, base):
    """Each part's box and the mesh's box from its vertices as copied (model units): a posed model's part boxes
    are its bones' own (build_image moves them by xf only). The mesh's box is a cube round the model's origin:
    the game culled the whole mesh with a box that left the origin out (Dash's from his feet up: never drawn;
    checked: his parts drew with Slave I's box)."""
    import collide
    img = bytearray(img)
    R = lambda a: struct.unpack_from('>I', img, a - base)[0]
    lo_all, hi_all = np.full(3, 1e9), np.full(3, -1e9)
    for i in range(h['parts']):
        p = R(h['list'] + 4 * i)
        fake = bytes(img) + struct.pack('>I', p)
        T = np.array(collide.extract(fake, base, 1, base + len(img))).reshape(-1, 3)
        if not len(T): continue
        lo, hi = T.min(0), T.max(0)
        struct.pack_into('>6f', img, p - base, *lo, *hi)
        lo_all, hi_all = np.minimum(lo_all, lo), np.maximum(hi_all, hi)
    s16 = lambda v: max(-32768, min(32767, int(round(v * 8))))
    m = float(np.abs(np.concatenate([lo_all, hi_all])).max())     # the mesh's box round its origin: one that left the
    bb = b''.join(struct.pack('>hhhhhhhh', s16(x), s16(y), s16(z), 0, 0, 0, 0, 0)   # origin out (Dash's, from his
                  for x in (-m, m) for y in (-m, m) for z in (-m, m))   # feet up) had the whole mesh culled
    img[h['box'] - base:h['box'] - base + len(bb)] = bb
    return bytes(img), dict(h, lo=list(lo_all), hi=list(hi_all))
