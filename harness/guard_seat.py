"""The Look's seat: open edges of the on-foot player's drawn meshes (the Look row's Guard / Luke) and rays through them.

    cd harness && ../.venv/bin/python3 guard_seat.py <ram dump> <player humn hex> [-v]   rays from the dump's camera
    ... --sweep                    rays from 8 units around the pelvis's bottom (below, below+-y, low+-y)
    ... --guard [--near]           the real red guard (the first kind-0 Trop) in the dump instead of the player
Dumps: tests/t_melee.py look with LIE_RAM=<prefix> (the combo's lying moment, LIE_SHOT=1 a still of the same moment;
the lying camera sits at his feet), or any palace.st RDRAM dump with the Look on. Expected with the pelvis cap
(guard_asset.py cap_bottom): the lying view INNER 0 and head drawn 0; every sweep head drawn 0; the lying `below`
sweep keeps ~38 INNER rays through the belt skirt's own rings (mesh loops 1 -> 2 of the belt on the pelvis bone) onto
the chest's outer face, not through the pelvis (measured 2026-11-09, the same before the cap).

Reads the drawn tree from RAM (model_walk nodes; triangles with shoulder_gap.mesh_tris). Per mesh node: its trot bone,
its triangle count and its open edges (an edge used by one triangle; vertices merged by their exact s16 position within
the bone frame), chained into boundary loops, each loop's centre and size in the pelvis bone's frame (world units,
rows normalised). Rays: from the active camera (0x800D08A4: eye +0x44, rows +0x14 right, +0x24 forward, +0x34 up;
fovy 77, 4:3) through a pixel grid (1280x960, STEP px) over the figure; per ray the first hit triangle, and the first
front-facing one (the winding sign taken from the majority of first hits). A ray is a "hole ray" when its first hit is
a back face (the inside seen) or its first front-facing hit is on the head bone (1) while a pelvis/thigh mesh's back
face lies before it. Each hole ray is named by the boundary loop it passes through (the loop's best-fit plane, the
crossing inside the loop's polygon)."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'guri'))
import numpy as np
from model_walk import Ram, m3, tr, ptr, trot_nodes
from shoulder_gap import mesh_tris

ACTIVE, FOVY, ASPECT, W_PX, H_PX = 0x800D08A4, 77.0, 4 / 3, 1280, 960
STEP = int(os.environ.get('STEP', 2))
VARIANT = None                     # a variant group: None its drawn one (+0x14), else that child (0 the near one)
CLASS_TROP = 0x80112D78            # the Trop class record: +0x10 the pool (0x120 each), +8 the count; kind +0x74
G2D = {15: 17, 14: 17, 13: 9, 6: 1, 5: 13, 4: 12, 3: 11, 2: 16, 1: 15, 0: 14, 12: 8, 11: 7, 10: 6, 9: 5, 8: 4, 7: 3}
NAMES = {17: 'pelvis', 16: 'L thigh?', 15: 'L shin?', 14: 'L foot?', 13: 'R thigh?', 12: 'R shin?', 11: 'R foot?',
         10: 'spine', 9: 'chest', 1: 'head', 18: 'model'}


def mesh_tris_raw(r, m, out, depth=0):
    """As shoulder_gap.mesh_tris but the raw s16 positions (exact keys)."""
    t = r.u32(m) >> 28
    if t == 5:
        v = r.u32(r.u32(m + 0x10) + 4 * VARIANT) if VARIANT is not None else r.u32(m + 0x14)
        if ptr(v) and depth < 4: mesh_tris_raw(r, v, out, depth + 1)
        return
    if t != 3: return
    for q in range(min(r.u32(m + 0x0C), 16)):
        sub = r.u32(r.u32(m + 0x10) + 4 * q)
        if not ptr(sub): continue
        a, slot, n = r.u32(sub + 0x28), {}, 0
        mat = r.u32(sub + 0x24)        # the material: its word bit 0x10 = drawn two-sided (the mesh draw 0x800BBBF8
        two = bool(ptr(mat) and r.u32(mat) & 0x10)   # sets G_CULL_BACK 0x2000 unless it)
        while ptr(a) and r.u32(a) >> 24 != 0xB8 and n < 4000:
            w0, w1 = r.u32(a), r.u32(a + 4); c = w0 >> 24
            if c == 0x04:
                for j in range((w0 & 0xFFFF) >> 9):
                    slot[j] = tuple(r.s16(w1 + 16 * j + o) for o in (0, 2, 4))
            elif c in (0xBF, 0xB5):
                ix = [(w1 >> sh & 0xFF) // 5 for sh in ((16, 8, 0) if c == 0xBF else (24, 16, 8, 0))]
                for t3 in ([ix] if c == 0xBF else [ix[:3], [ix[0], ix[2], ix[3]]]):
                    if all(j in slot for j in t3): out.append((two, tuple(slot[j] for j in t3)))
            a += 8; n += 1


def figure(r, top, bone_of):
    """[(bone, mesh node, world 4x4, [(sub, raw tri)])] for every mesh under top; bone_of: node -> bone id."""
    out = []
    def walk(nd, W, d, bone):
        L = np.eye(4); L[:3, :3] = m3(r, nd); L[3, :3] = tr(r, nd); Wn = L @ W
        b = bone_of.get(nd, bone)
        for j in range(min(r.u32(nd + 0x0C), 24)):
            c = r.u32(r.u32(nd + 0x10) + 4 * j)
            if not ptr(c): continue
            if r.u32(c) >> 28 == 0xD and d < 30: walk(c, Wn, d + 1, b)
            else:
                ts = []; mesh_tris_raw(r, c, ts)
                if ts: out.append((b, c, Wn, ts))
    walk(top, np.eye(4), 0, None)
    return out


def loops(tris):
    """Open edges (used once) of raw tris, chained into loops of vertex keys."""
    cnt = {}
    for _, t in tris:
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            if a == b: continue
            k = (min(a, b), max(a, b)); cnt[k] = cnt.get(k, 0) + 1
    edges = [k for k, v in cnt.items() if v == 1]
    adj = {}
    for a, b in edges: adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for a, b in edges:
        if (a, b) in seen: continue
        loop = [a]; prev, cur = a, b; seen.add((a, b))
        while cur != a and len(loop) < 500:
            loop.append(cur)
            nxt = [x for x in adj[cur] if x != prev and (min(cur, x), max(cur, x)) not in seen]
            if not nxt: break
            k = (min(cur, nxt[0]), max(cur, nxt[0])); seen.add(k); prev, cur = cur, nxt[0]
        out.append(loop)
    return out, len(edges)


def world(keys, Wn): return (np.c_[np.array(keys, float) / 8, np.ones(len(keys))] @ Wn)[:, :3]


def frame_of(Wn):
    R = Wn[:3, :3] / np.linalg.norm(Wn[:3, :3], axis=1)[:, None]
    return lambda X: (X - Wn[3, :3]) @ np.linalg.inv(R)


def cam(r):
    c = r.u32(ACTIVE)
    v = lambda o: np.array([r.f(c + o + 4 * a) for a in range(3)])
    return v(0x44), v(0x14), v(0x24), v(0x34)


def raycast(O, D, T):
    """Möller–Trumbore: O (3), D (N x 3), T (M x 3 x 3) -> t (N x M), inf where missed."""
    e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    p = np.cross(D[:, None, :], e2[None])
    det = np.einsum('nmk,mk->nm', p, e1)
    inv = np.where(np.abs(det) > 1e-12, 1 / np.where(det == 0, 1, det), 0)
    s = O - T[:, 0]
    u = np.einsum('nmk,mk->nm', p, s) * inv
    q = np.cross(s, e1)
    v = np.einsum('nk,mk->nm', D, q) * inv
    t = np.einsum('mk,mk->m', e2, q)[None] * inv
    ok = (np.abs(det) > 1e-12) & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4)
    return np.where(ok, t, np.inf)


def in_poly(P2, poly):
    x, y = P2; inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: inside = not inside
    return inside


def analyse(r, fig, pelvis_W, eye, rows, label, rays=None, verbose=False):
    to_p = frame_of(pelvis_W)
    T, owner, LP, TWO = [], [], [], []
    print(f'== {label}: {len(fig)} meshes')
    for mi, (b, m, Wn, ts) in enumerate(fig):
        ls, ne = loops(ts)
        quiet = label.startswith('sweep') and not verbose
        Wt = [world(t, Wn) for _, t in ts]
        T += Wt; owner += [mi] * len(Wt); TWO.extend(tw for tw, _ in ts)
        allp = to_p(np.concatenate(Wt))
        nt = sum(tw for tw, _ in ts)
        if not quiet: print(f'  mesh {mi:2d} two-sided tris {nt} bone {b} ({NAMES.get(b, "")}) node {m:08x} tris {len(ts)} open edges {ne} loops {len(ls)}'
              f'  pelvis-frame box x {allp[:,0].min():+.2f}..{allp[:,0].max():+.2f} y {allp[:,1].min():+.2f}..'
              f'{allp[:,1].max():+.2f} z {allp[:,2].min():+.2f}..{allp[:,2].max():+.2f}')
        for li, lp in enumerate(ls):
            if len(lp) < 3: continue
            P = world(lp, Wn); c = to_p(P).mean(0); ext = np.ptp(to_p(P), 0)
            LP.append((mi, li, P))
            if (verbose or b in (17, 16, 13, 10)) and not quiet:
                print(f'      loop {li}: {len(lp)} verts, centre (pelvis frame) {c[0]:+.2f} {c[1]:+.2f} {c[2]:+.2f}, '
                      f'size {ext[0]:.2f} {ext[1]:.2f} {ext[2]:.2f}')
    T = np.array(T); owner = np.array(owner); TWO = np.array(TWO, bool)
    if rays is None:
        C = T.reshape(-1, 3); rel = C - eye
        z = rel @ rows[1]; ty = np.tan(np.radians(FOVY / 2))
        sx = W_PX / 2 * (1 + (rel @ rows[0]) / (z * ty * ASPECT)); sy = H_PX / 2 * (1 - (rel @ rows[2]) / (z * ty))
        x0, x1, y0, y1 = int(sx.min()) - 2, int(sx.max()) + 2, int(sy.min()) - 2, int(sy.max()) + 2
        print(f'  figure on screen: x {x0}..{x1}, y {y0}..{y1} (1280x960)')
        px = [(x, y) for y in range(y0, y1, STEP) for x in range(x0, x1, STEP)]
        ty = np.tan(np.radians(FOVY / 2))
        D = np.array([rows[1] + (2 * x / W_PX - 1) * ty * ASPECT * rows[0] + (1 - 2 * y / H_PX) * ty * rows[2] for x, y in px])
        O = eye
    else:
        O, D, px = rays
    D = D / np.linalg.norm(D, axis=1)[:, None]
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    hits, res = 0, []
    for k in range(0, len(D), 400):
        t = raycast(O, D[k:k + 400], T)
        for i in range(t.shape[0]):
            order = np.argsort(t[i]); order = order[np.isfinite(t[i][order])]
            if len(order): res.append((k + i, order, t[i][order]))
    closed = {mi for mi, (b, m, Wn, ts) in enumerate(fig) if loops(ts)[1] == 0}
    first = np.array([np.sign(n[o[0]] @ D[i]) for i, o, _ in res if owner[o[0]] in closed])
    front = -1.0 if (first < 0).sum() >= (first > 0).sum() else 1.0   # front faces: n . d has this sign
    print(f'  rays {len(D)}, hitting the figure {len(res)}; first hits n.d<0 {(first < 0).sum()}, >0 {(first > 0).sum()}'
          f' -> front = n.d {"<" if front < 0 else ">"} 0')
    def crossed(i, upto):
        """Loops (mesh, loop) the ray i passes through before distance upto, nearest first."""
        names = []
        for mi, li, P in LP:
            c = P.mean(0); _, _, vt = np.linalg.svd(P - c); nn = vt[2]
            den = D[i] @ nn
            if abs(den) < 1e-6: continue
            s = ((c - O) @ nn) / den
            if s <= 0 or s > upto: continue
            X = O + s * D[i]; b1, b2 = vt[0], vt[1]
            if in_poly(((X - c) @ b1, (X - c) @ b2), [((p - c) @ b1, (p - c) @ b2) for p in P]): names.append((s, mi, li))
        return [(m, l) for _, m, l in sorted(names)]
    hole, by, head_any, backs, inner = [], {}, [], 0, []
    for i, o, ts in res:
        fb = (np.sign(n[o] @ D[i]) == front) | TWO[o]
        if not fb.any(): continue
        k = int(np.argmax(fb)); hit = o[k]; mf = owner[hit]; bone = fig[mf][0]
        back = not (np.sign(n[hit] @ D[i]) == front)
        backs += back
        if bone == 1: head_any.append(i)
        nm = crossed(i, ts[k] + 1e-4)
        seat = any(fig[m][0] == 17 for m, _ in nm)
        if seat and bone in (1, 9, 10): inner.append(i)
        if seat and (bone in (1, 9, 10) or back):
            hole.append(i)
            key = (bone, mf, back, tuple(nm[:3])); by[key] = by.get(key, 0) + 1
    print(f'  drawn surface a two-sided back face (an armour piece inside): {backs} rays; head drawn: {len(head_any)} rays')
    print(f'  INNER rays {len(inner)} (through a pelvis-bone loop, drawn: the head, chest or spine)')
    print(f'  SEAT HOLE rays {len(hole)} (through a pelvis-bone loop, drawn: the head, chest or spine, or a back face)')
    for (bone, mf, back, nm), c in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f'    {c:4d} rays: drawn mesh {mf} (bone {bone}) {"back face" if back else "front"}, through loops {list(nm)}')
    if rays is None:
        for nmx, ids in (('seat hole', hole), ('head drawn', head_any)):
            if ids:
                xs = [px[i] for i in ids]
                print(f'  {nmx} pixels: x {min(p[0] for p in xs)}..{max(p[0] for p in xs)}, '
                      f'y {min(p[1] for p in xs)}..{max(p[1] for p in xs)} (grid step {STEP})')
    return hole


def player(r, humn):
    nodes = trot_nodes(r, humn)
    bone_of = {nd: i for i, nd in enumerate(nodes)}
    fig = figure(r, r.u32(humn + 0x24C), bone_of)
    pel = [Wn for b, m, Wn, ts in fig if b == 17]
    # the pelvis bone's world: its node's world (a mesh's parent matrix)
    return fig, pel[0]


def trop_fig(r):
    """The real red guard (the first kind-0 Trop): its meshes, bones named by the Dash bone they map to (G2D)."""
    tr_ = r.u32(CLASS_TROP + 0x10)
    g = next(tr_ + j * 0x120 for j in range(64) if r.u32(tr_ + j * 0x120 + 0x74) == 0)
    root = r.u32(r.u32(g + 0x70) + 0x84)
    order = []
    def walk(nd):
        if not ptr(nd) or r.u32(nd) >> 28 != 0xD: return
        order.append(nd)
        for j in range(r.u32(nd + 0x0C)): walk(r.u32(r.u32(nd + 0x10) + 4 * j))
    walk(root)
    bone_of = {order[18 - i]: G2D.get(i, 100 + i) for i in range(17) if 18 - i < len(order)}
    fig = figure(r, root, bone_of)
    pel = [Wn for b, m, Wn, ts in fig if b == 17]
    print(f'real guard Trop {g:08x}')
    return fig, pel[0]


def sweep_rays(pW, centre, dirs, half=0.7, step=0.02):
    """Rays from eyes 8 units from `centre` (pelvis frame) along each of `dirs` (pelvis frame), aimed through a square
    grid +-half around it: (eye, directions) per dir, world."""
    R = pW[:3, :3] / np.linalg.norm(pW[:3, :3], axis=1)[:, None]; o = pW[3, :3]
    w = lambda X: np.asarray(X) @ R + o
    out = []
    for d in dirs:
        d = np.array(d, float); d /= np.linalg.norm(d)
        a = np.cross(d, [1, 0, 0]) if abs(d[0]) < 0.9 else np.cross(d, [0, 1, 0]); a /= np.linalg.norm(a); b = np.cross(d, a)
        E = centre + 8 * d
        g = np.arange(-half, half + 1e-9, step)
        T = np.array([centre + u * a + v * b for u in g for v in g])
        out.append((w(E), w(T) - w(E)))
    return out


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('-')]
    r = Ram.load(a[0])
    humn = int(a[1], 16)
    eye, *rows = cam(r)
    print(f'camera eye {eye.round(2)}, fwd {rows[1].round(3)}')
    VARIANT = 0 if '--near' in sys.argv else None
    fig, pW = (trop_fig(r) if '--guard' in sys.argv else player(r, humn))
    R = pW[:3, :3] / np.linalg.norm(pW[:3, :3], axis=1)[:, None]
    print('camera forward in the pelvis frame', (rows[1] @ np.linalg.inv(R)).round(3),
          'eye', ((eye - pW[3, :3]) @ np.linalg.inv(R)).round(2))
    if '--sweep' not in sys.argv:
        analyse(r, fig, pW, eye, rows, 'player', verbose='-v' in sys.argv)
    else:
        c = np.array([0.0, 0.0, -0.5])     # the pelvis mesh's lower loop, about
        dirs = {'below': (0, 0, -1), 'below+y': (0, 0.7, -0.7), 'below-y': (0, -0.7, -0.7),
                'low+y': (0, 0.95, -0.3), 'low-y': (0, -0.95, -0.3)}
        for (nm, d), (E, Dv) in zip(dirs.items(), sweep_rays(pW, c, dirs.values())):
            analyse(r, fig, pW, E, None, f'sweep {nm}', rays=(E, Dv, None))
