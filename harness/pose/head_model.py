"""A head of ours for the palace guard's skeleton (the guard's head bone, trSt 6, its frame: z up, front -y), shared by
the Guri model (harness/guri/guri_model.py) and Luke's head (harness/luke/luke_model.py).

    parts = head(p, T, axis, collar_top)   ->  {bone: [{'pos', 'col', 'uv' or None, 'idx', 'face'}]}, face PNG bytes

p: the head's constants (a namespace: the names below in capitals, as the callers' modules define them); T: the
guard's bone translations (T[6] the head bone over the chest, 13); axis: the collar's axis (x, y) in the chest's frame;
collar_top: the collar's top z in the chest's frame (the chin sits HEAD_AT[1] above it). The parts, each shaded in its
own colours (vertex colours, unlit: one light from above-front baked in):
- the skull: an ellipsoid (HEAD_R, HEAD_TOP, HEAD_JAW: a skull, not an egg, head_point);
- the face: a FACE_TEX texture made from a photo (FACE_SRC) wrapped round its front (face_texture), 'face' True;
- the relief: the photo's features as geometry (FACE_RELIEF, HEAD_DEPTH_NOSE: the nose, brow, chin stand out);
- the hair: a style (HAIR_STYLE): 'long' (parted in the middle, framing the face, a fall down the back on the chest
  bone) or 'short_side' (a short cut parted on the figure's left, the fringe swept to its right);
- the neck: rings (NECK) round the collar's axis from inside the collar up into the head, in NECK_COLOUR;
- the shading: per part a base and its shade (unlit .. lit), the hair also lit from above-behind (HAIR_BACKLIT).
"""
import io, math
import numpy as np
from PIL import Image

X3, Y3, Z3 = np.eye(3)
WHITE = np.array((255.0, 255.0, 255.0))


class Part:
    """Triangles of one material: positions, colours, uvs, normals (for the baked light)."""
    def __init__(s): s.p, s.n, s.uv, s.t, s.ix = [], [], [], [], {}

    def v(s, p, n, uv=(0.0, 0.0)):              # a vertex the same in place, normal and uv is shared (the image's size)
        p, n = np.asarray(p, float), np.asarray(n, float) / (np.linalg.norm(n) or 1)
        key = tuple(np.round(np.concatenate([p, n, uv]), 5))
        if key in s.ix: return s.ix[key]
        s.p.append(p); s.n.append(n); s.uv.append(uv); s.ix[key] = len(s.p) - 1
        return len(s.p) - 1

    def tri(s, a, b, c):
        s.t.append((a, b, c))

    def outward(s, centre):                      # winding CCW seen from outside (the game's front faces, as the guard's)
        for k, (a, b, c) in enumerate(s.t):
            pa, pb, pc = s.p[a], s.p[b], s.p[c]
            if np.cross(pb - pa, pc - pa) @ ((pa + pb + pc) / 3 - centre) < 0: s.t[k] = (a, c, b)


HIDDEN = np.array([0.0, 0.7, -0.7])          # a cap's normal that takes no light (its colour the base): a cap meant to
                                             # sit inside the next segment shows dark, not as a light seam, if a bend
                                             # turns its edge out


def loft(part, rings, caps=(True, True), sides=8, dark=(False, False), phase=None, depth=None):
    """rings: [(centre, e1, e2, r1, r2)], `sides` around each; sides between neighbours, fan caps at the ends (dark:
    that end's cap shaded as unlit). phase: the first point's angle (default half a side: no point on e1's axis);
    depth(ring index, angle): a factor on the point's e2 part (a ring's profile), its normal then the surface's own
    (averaged over the side triangles round it)."""
    if phase is None: phase = math.pi / sides
    ths = [phase + 2 * math.pi * k / sides for k in range(sides)]
    ids = []
    if depth is not None:                        # the profiled surface: its points first, the normals from its faces
        P = [[c + r1 * math.cos(th) * e1 + r2 * math.sin(th) * depth(i, th) * e2 for th in ths]
             for i, (c, e1, e2, r1, r2) in enumerate(rings)]
        N = [[np.zeros(3) for _ in ths] for _ in rings]
        for i in range(len(rings) - 1):
            for k in range(sides):
                k2 = (k + 1) % sides
                for a, b, c_ in (((i, k), (i + 1, k), (i + 1, k2)), ((i, k), (i + 1, k2), (i, k2))):
                    f = np.cross(P[b[0]][b[1]] - P[a[0]][a[1]], P[c_[0]][c_[1]] - P[a[0]][a[1]])
                    if f @ (P[a[0]][a[1]] - rings[a[0]][0]) < 0: f = -f
                    for q in (a, b, c_): N[q[0]][q[1]] += f
        for i in range(len(rings)):
            ids.append([part.v(P[i][k], N[i][k]) for k in range(sides)])
    for c, e1, e2, r1, r2 in (rings if depth is None else []):
        row = []
        for th in ths:
            off = r1 * math.cos(th) * e1 + r2 * math.sin(th) * e2
            nrm = (math.cos(th) / max(r1, 1e-6)) * e1 + (math.sin(th) / max(r2, 1e-6)) * e2
            row.append(part.v(c + off, nrm))
        ids.append(row)
    for a, b in zip(ids, ids[1:]):
        for k in range(sides):
            k2 = (k + 1) % sides
            part.tri(a[k], b[k], b[k2]); part.tri(a[k], b[k2], a[k2])
    for end, on in ((0, caps[0]), (len(rings) - 1, caps[1])):
        if not on: continue
        d = rings[end][0] - rings[1 if end == 0 else -2][0]; d /= np.linalg.norm(d)
        if dark[0 if end == 0 else 1]: d = HIDDEN
        row = [part.v(part.p[i], d) for i in ids[end]]
        for k in range(1, sides - 1): part.tri(row[0], row[k], row[k + 1])
    return np.mean([r[0] for r in rings], 0)


def two_sided(outer, inner):                     # a sheet's back side: the same triangles, turned, normals flipped
    base = len(inner.p)
    for p, n in zip(outer.p, outer.n): inner.v(p, -n)
    for a, b_, c in outer.t: inner.tri(base + a, base + c, base + b_)


def head_point(p, th, lam):
    """The head's surface (head-centre frame: the eyes' height z 0) at th degrees round (270 the front, 0 the figure's
    +x) and lam degrees of latitude from the crown (180 the chin): (point, outward normal). An ellipsoid of HEAD_R (half
    width, depth to the front, to the back, up from the eyes to the crown, down to the chin), the rings' radius
    sin(lat) ** HEAD_TOP above the eyes (a flatter-rounded top, the forehead upright), HEAD_JAW's keys (latitude: x,
    front depth, back depth factors, y shift; between the keys linear) shaping the cranium, the jaw and the chin."""
    rx, ryf, ryb, up, down = p.HEAD_R
    J = p.HEAD_JAW
    def at(th, lam):
        fx, fyf, fyb, sy = (float(np.interp(lam, [j[0] for j in J], [j[i] for j in J])) for i in (1, 2, 3, 4))
        t, l = math.radians(th), math.radians(lam)
        ry = (ryf * fyf) if math.sin(t) < 0 else (ryb * fyb)
        r = math.sin(l) ** p.HEAD_TOP if lam < 90 else math.sin(l)
        return np.array([rx * fx * r * math.cos(t), ry * r * math.sin(t), (up if lam <= 90 else down) * math.cos(l) ]) \
            + np.array([0.0, sy, 0.0])
    q = at(th, lam)
    if lam <= 0.0 or lam >= 180.0: return q, np.array([0.0, 0.0, 1.0 if lam <= 0.0 else -1.0])
    e = 0.25                                       # the normal from the surface's own slopes (central differences)
    n = np.cross(at(th + e, lam) - at(th - e, lam), at(th, min(179.9, lam + e)) - at(th, max(0.01, lam - e)))
    n = n if n @ q > 0 else -n
    return q, n / np.linalg.norm(n)


def head_lat(p, z):
    """The latitude (degrees from the crown) of the head's surface at z (head-centre frame)."""
    return math.degrees(math.acos(max(-1.0, min(1.0, z / (p.HEAD_R[3] if z >= 0 else p.HEAD_R[4])))))


def face_texture(p, checker=False):
    """The face from a photo of the figure (FACE_SRC: the file, the eyes' centre x, their y, the chin's lowest y, in its
    pixels) as a FACE_TEX texture wrapped round the head (FACE_SECT: u the angle over (from, to) degrees, v the height
    from the ring at its latitude down to the chin), <= 16 colours (CI4), its border SKIN: PNG bytes. Each texel's
    place on the head's surface, seen from the front, picks the photo's pixel (2 x 2 samples a texel): the eyes at the
    head's middle height, the chin at its chin (one scale). Saturation then contrast lifted by FACE_LIFT, the skin
    matched to SKIN (the cheeks' median), the hair (FACE_HAIR: hue from, to, saturation over) and the dark below the
    chin taken out (and, FACE_SIDE, the darker hair at the crop's sides), MAKEUP's tints (if p has it: (photo rows
    from, to), (|x - the eyes' centre x| from, to), rgb, the share toward it) (rows from .. to, the last excluded) laid on, the crop's border blended over
    FACE_BLEND pixels into SKIN."""
    import colorsys
    from scipy.ndimage import map_coordinates, gaussian_filter, distance_transform_edt
    SKIN = p.SKIN
    path, ex, ey, cy = p.FACE_SRC
    h0, h1, s0 = p.FACE_HAIR
    src = np.asarray(Image.open(path).convert('RGB'), float)
    hsv = np.array([[colorsys.rgb_to_hsv(*(px / 255)) for px in row] for row in src])
    hue, sat, val = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    rows = np.arange(src.shape[0])[:, None] + np.zeros(src.shape[1])
    keep = ~(((hue > h0) & (hue < h1) & (sat > s0)) | ((val < 0.3) & (rows > cy - 6)))   # no hair, no dark below
    side = getattr(p, 'FACE_SIDE', None)          # hair at the crop's sides (columns from each edge, darker than)
    if side:
        cols = np.arange(src.shape[1])[None, :] + np.zeros((src.shape[0], 1))
        keep &= ~(((cols < side[0]) | (cols >= src.shape[1] - side[0])) & (val < side[1]))
    lum = src @ np.array([0.299, 0.587, 0.114])                            # the chin (the eyes' dark kept)
    img = lum[..., None] + (src - lum[..., None]) * p.FACE_LIFT[1]        # saturation lifted
    sh, sw = keep.shape                                                    # the skin: the cheeks' median
    cheek = np.zeros_like(keep); cheek[int(ey + 8):int(ey + 16), int(ex - 12):int(ex - 6)] = True
    cheek[int(ey + 8):int(ey + 16), int(ex + 6):int(ex + 12)] = True
    med = np.median(img[cheek & keep], 0)
    img = img * (SKIN / med)                                               # matched to SKIN
    base = np.stack([gaussian_filter(img[..., c], p.FACE_FLAT) for c in range(3)], -1)
    img = SKIN + (img - base) * p.FACE_LIFT[0] + (base - SKIN) * 0.5       # the details' contrast lifted, the photo's
                                                                           # light from one side halved round SKIN
    img = np.clip(img, 0, None)
    img *= np.minimum(1.0, 250.0 / np.maximum(img.max(-1), 1.0))[..., None]   # highlights scaled, not clipped: no
                                                                           # yellow-white glare
    for (r0, r1), (d0, d1), rgb, k in getattr(p, 'MAKEUP', ()):           # tints over photo bands (rows, |x - eyes'
        band = np.zeros((sh, sw), bool)                                    # centre x|): toward rgb by k
        cols_ = np.abs(np.arange(sw) - ex)
        band[max(0, int(round(r0))):int(round(r1)), :] = True
        band &= ((cols_ >= d0) & (cols_ <= d1))[None, :]
        img[band] = img[band] + (np.array(rgb, float) - img[band]) * k
    pad = np.zeros((sh + 2, sw + 2), bool); pad[1:-1, 1:-1] = keep
    w = np.clip(distance_transform_edt(pad)[1:-1, 1:-1] / p.FACE_BLEND, 0, 1)   # to the crop's border and the hair
    w = gaussian_filter(w, 0.7) * keep
    img = img * w[..., None] + SKIN * (1 - w[..., None])
    W, H = p.FACE_TEX; ss = 2; a0, a1, lat = p.FACE_SECT
    zt, zb = head_point(p, 270.0, lat)[0][2], -p.HEAD_R[4]
    s = p.HEAD_R[4] / (cy - ey)                                            # units per photo pixel
    u = (np.arange(W * ss) + 0.5) / (W * ss); v = (np.arange(H * ss) + 0.5) / (H * ss)
    px, py = np.zeros((H * ss, W * ss)), np.zeros((H * ss, W * ss))
    for j, vv in enumerate(v):
        z = zt + (zb - zt) * vv; lam = head_lat(p, z)
        for i, uu in enumerate(u):
            q = head_point(p, a0 + (a1 - a0) * uu, lam)[0]
            px[j, i], py[j, i] = ex + q[0] / s, ey - q[2] / s
    out = np.stack([map_coordinates(img[..., c], [py, px], order=1, mode='constant', cval=SKIN[c]) for c in range(3)], -1)
    if checker:
        out[((np.arange(W * ss)[None] // (4 * ss) + np.arange(H * ss)[:, None] // (4 * ss)) % 2) == 1] = (200, 40, 160)
    out = out.reshape(H, ss, W, ss, 3).mean((1, 3))
    # 16 colours: SKIN (the border) and 15 by k-means seeded spread over the luminance (the eyes' and lips' dark
    # tones keep colours of their own; a median cut gave them all to the skin's shades)
    from scipy.cluster.vq import kmeans2
    px_ = np.clip(out, 0, 255).reshape(-1, 3)
    order = np.argsort(px_ @ np.array([0.299, 0.587, 0.114]))
    seed = px_[order[np.linspace(0, len(order) - 1, 15).astype(int)]]
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')                                    # an empty cluster: a colour unused
        pal, _ = kmeans2(px_, seed, iter=30, minit='matrix', seed=1)
    pal = np.vstack([SKIN, pal])
    lab = np.argmin(((px_[:, None] - pal[None]) ** 2).sum(-1), 1)
    q = np.round(pal[lab]).reshape(out.shape).astype(np.uint8)
    b = io.BytesIO(); Image.fromarray(q).save(b, 'PNG'); return b.getvalue()


def skull(p, hc, plain, P):
    """The skull with its relief and the face's sectors: (the face's Part (textured), the bare skin's Part)."""
    a0, a1, flat = p.FACE_SECT
    zt, zb = head_point(p, 270.0, flat)[0][2], -p.HEAD_R[4]
    # the relief's rings (FACE_RELIEF: photo rows -> the head's z, as face_texture maps them) and their forward push:
    # per ring, keys (|x| from the nose's line, push forward; between the keys linear, past the last 0; None: the
    # nose's tip, HEAD_DEPTH_NOSE of the head's depth). Pushed straight forward (x and z kept): the face texture's
    # projection stays where it was
    s_ph = p.HEAD_R[4] / (p.FACE_SRC[3] - p.FACE_SRC[2])
    rel = {}
    for row, keys in p.FACE_RELIEF:
        z = -(row - p.FACE_SRC[2]) * s_ph
        keys = [(x, p.HEAD_DEPTH_NOSE * (p.HEAD_R[1] + p.HEAD_R[2]) if d is None else d) for x, d in keys]
        rel[round(head_lat(p, z), 3)] = keys
    ths = list(p.HEAD_THS)
    lats = sorted(set([180.0 * i / p.HEAD_BANDS for i in range(p.HEAD_BANDS + 1)]) | set(rel))
    lats = [l for l in lats if l in rel or all(abs(l - r) > 4.5 for r in rel)]   # a band ring near a relief one goes
    def push(th, lam):
        q = head_point(p, th, lam)[0]
        keys = rel.get(round(lam, 3))
        if keys is None or math.sin(math.radians(th)) >= 0: return 0.0
        ax = abs(q[0])
        return float(np.interp(ax, [k[0] for k in keys], [k[1] for k in keys], right=0.0))
    NT, NL = len(ths), len(lats)
    G = np.array([[head_point(p, th, lam)[0] - np.array([0.0, push(th, lam), 0.0]) for th in ths] for lam in lats])
    Dp = np.array([[push(th, lam) for th in ths] for lam in lats])
    def hvert(th, lam):
        q, n = head_point(p, th, lam)
        uv = ((th - a0) / (a1 - a0), (zt - q[2]) / (zt - zb))
        if lam in (0.0, 180.0) or th not in ths: return hc + q, n, uv
        i, k = lats.index(lam), ths.index(th)
        if Dp[i - 1:i + 2, [(k - 1) % NT, k, (k + 1) % NT]].any():     # near the relief: the normal of the pushed mesh
            dt = G[i, (k + 1) % NT] - G[i, (k - 1) % NT]
            dl = G[i + 1, k] - G[i - 1, k]
            m = np.cross(dl, dt)
            n = m * np.sign(m @ n) if np.linalg.norm(m) > 1e-6 else n
        return hc + G[i, k], n, uv
    face, skin = Part(), P(6, 'skin')
    for k, th in enumerate(ths):
        th2 = ths[(k + 1) % NT] + (360.0 if k == NT - 1 else 0.0)
        th2k = ths[(k + 1) % NT]
        on_face = a0 <= th and th2 <= a1
        for i in range(NL - 1):
            l0, l1 = lats[i], lats[i + 1]
            part = face if on_face and l0 >= flat else skin
            if i == 0: vs = [hvert((th + th2) / 2, 0.0), hvert(th, l1), hvert(th2k, l1)]       # the crown's fan
            elif i == NL - 2: vs = [hvert(th, l0), hvert((th + th2) / 2, 180.0), hvert(th2k, l0)]   # the chin's
            else: vs = None
            if vs:
                ids = [part.v(*q) for q in vs]; part.tri(*ids); continue
            q = [hvert(th, l0), hvert(th, l1), hvert(th2k, l1), hvert(th2k, l0)]
            ids = [part.v(*x) for x in q]
            part.tri(ids[0], ids[1], ids[2]); part.tri(ids[0], ids[2], ids[3])
    face.outward(hc); skin.outward(hc)
    return face, skin


def hair_frame(p, hc):
    """The hair's shell round the head: (centre, radii (across, deep, up)), fitted to the head's top, back and sides
    (HAIR_FIT: the forehead's front taken from the head's vertices this far below the top; the centre this much above
    the eyes' height; the radii widened round, then x this: the polygon's chords cut inside the ellipsoid), the top
    HAIR_TOP over the skull's, HAIR_RX the half width (None: the fit's), HAIR_DEEP the depth x."""
    hp = np.array([hc + head_point(p, 15.0 + 360.0 / p.HEAD_AROUND * k, 180.0 * i / p.HEAD_BANDS)[0]   # the plain
                   for k in range(p.HEAD_AROUND) for i in range(p.HEAD_BANDS + 1)])                 # ellipsoid's grid
    lo3, hi3 = hp.min(0), hp.max(0)
    yf = hp[hp[:, 2] > hi3[2] - p.HAIR_FIT[0], 1].min()       # the forehead's front
    hh = np.array([(lo3[0] + hi3[0]) / 2, (yf + hi3[1]) / 2, hc[2] + p.HAIR_FIT[1]])
    ah = np.array([(hi3[0] - lo3[0]) / 2, (hi3[1] - yf) / 2, hi3[2] - hh[2] + p.HAIR_TOP])
    top = hp[(hp[:, 2] >= hh[2] - 1.0) & (hp[:, 1] >= yf)]
    q = (top - hh) / ah                            # across and deep widened till its top, back and sides are inside
    k = np.sqrt((q[:, 0] ** 2 + q[:, 1] ** 2) / np.maximum(1e-3, 1.0 - q[:, 2] ** 2))
    ah[:2] = ah[:2] * max(1.0, float(k.max())) * p.HAIR_FIT[2]
    ah[0], ah[1] = (p.HAIR_RX if p.HAIR_RX is not None else ah[0]), ah[1] * p.HAIR_DEEP
    return hh, ah


hn = lambda q, c: (q - c) * np.array([1, 1, 0.3])           # the hair's normals: out from its centre, flattened


def hair_long(p, T, hc, plain, P):
    """Guri's: golden, parted in the middle (no fringe), long: a shell over the top fitted round her head, from the
    back as wide as the fall, framing the face (from the part over the temples, down along the cheeks: its edge tucked
    to the skin) and round the head to the nape (head bone), then a shell down the back to the shoulder blades with a
    jagged hem (chest bone). HAIR_COLS: columns from the crown (degrees from the front, mirrored; the two beside the
    front the part's sides: the strip between them darker, pressed in by HAIR_PART), each down the shell through
    latitudes then the face's frame, tucked HAIR_TUCK out from the skin at (degrees from the front, z from the eyes'
    height); HAIR_BACK: the falling columns, down from the shell's widest to the curtain's bottom (HAIR_CURTAIN) and
    the nape (HAIR_NAPE), their ends jagged (HAIR_JAG), the outline wavy (HAIR_WAVE); HAIR_CHEEK: the shell beside the
    face drawn in; HAIR_FALL, FALL_TOP, FALL_ARC, FALL_JAG: the fall on the chest bone (rows z, rx, ry, y shift)."""
    hh, ah = hair_frame(p, hc)
    def quad(part, q, nrm):
        ids = [part.v(x, n) for x, n in zip(q, nrm)]
        part.tri(ids[0], ids[1], ids[2]); part.tri(ids[0], ids[2], ids[3])
    dz = hh[2] - p.HAIR_REF_Z                      # the rows below (nape, fall) move with the shell
    nape_z, nape_r = p.HAIR_NAPE[0] + dz, p.HAIR_NAPE[1]
    # the hair over the head (HAIR_COLS, HAIR_BACK): columns from the crown, each a row of points, the same count
    # (the shorter ones end early: their last point repeated); between two columns quads, where one has ended a
    # closing triangle while the other is still on the shell (never over the face's opening)
    def shell(th, lam, k=1.0):
        t, l = math.radians(th), math.radians(lam)
        return hh + ah * np.array([k * math.sin(l) * math.cos(t), k * math.sin(l) * math.sin(t), math.cos(l)])
    def tuck(d, z):
        q, n = head_point(p, 270.0 + d, head_lat(p, z))
        return hc + q + n * p.HAIR_TUCK
    zc_curt = hc[2] + p.HAIR_CURTAIN
    cols = []                                      # (degrees round, [(point, kind: 's' shell / 't' tucked)])
    for sgn in (1, -1):
        for d, (lams, edge) in p.HAIR_COLS.items():
            col = [(shell(270 + sgn * d, l, p.HAIR_CHEEK[1] if d >= p.HAIR_CHEEK[0] and l >= 60 else 1.0), 's')
                   for l in lams] + [(tuck(sgn * e, z), 't') for e, z in edge]
            cols.append((270 + sgn * d, col))
    for d in p.HAIR_BACK:
        for sgn in ((1, -1) if d < 180 else (1,)):
            th = 270 + sgn * d
            f = (d - p.HAIR_BACK[0]) / (180.0 - p.HAIR_BACK[0])   # 0 the side, 1 the back
            zb_ = zc_curt + (nape_z - zc_curt) * min(1.0, 2.0 * f)
            col = [(shell(th, l), 's') for l in (22.0, 45.0, 67.0, 90.0)]
            eq = shell(th, 90.0)
            for j, fz in enumerate((1 / 3, 2 / 3, 1.0)):
                k = 1.0 + (nape_r[0] - 1.0) * f * fz
                q = hh + (eq - hh) * np.array([k, k * (nape_r[1] / nape_r[0] if f else 1.0), 0.0])
                q[2] = eq[2] + (zb_ - eq[2]) * fz
                col.append((q, 's'))
            cols.append((th, col))
    cols.sort(key=lambda c: c[0] % 360)
    n_rows = max(len(c) for _, c in cols)
    for ci, (th, col) in enumerate(cols):          # the outline: the falling columns' radius alternately wavy, their
        wv = p.HAIR_WAVE[ci % 2]                   # ends alternately jagged
        for j, (q, kind) in enumerate(col):
            if kind == 's' and j >= 3:
                q = hh + (q - hh) * np.array([wv, wv, 1.0]); col[j] = (q, kind)
        if len(col) == n_rows and abs(((th - 270 + 180) % 360) - 180) >= p.HAIR_BACK[0] - 1:
            q = col[-1][0].copy(); q[2] += p.HAIR_JAG[ci % 2]; col[-1] = (q, 's')
        col += [col[-1]] * (n_rows - len(col))
    crown = hh + ah * np.array([0.0, 0.0, 1.0])
    head_hair, head_in = P(6, 'hair2'), P(6, 'hairin', 'cap')
    for ci in range(len(cols)):
        A, B = cols[ci][1], cols[(ci + 1) % len(cols)][1]
        dA, dB = (cols[ci][0] - 270 + 180) % 360 - 180, (cols[(ci + 1) % len(cols)][0] - 270 + 180) % 360 - 180
        part = head_hair
        if abs(dA) < 10 and abs(dB) < 10 and dA * dB < 0:             # the middle part: a darker line, pressed in
            part = P(6, 'hairpart')
        tris = [(crown, A[0][0], B[0][0])]
        for j in range(n_rows - 1):
            a_end, b_end = A[j][0] is A[j + 1][0], B[j][0] is B[j + 1][0]
            if a_end and b_end: continue
            if a_end:
                if B[j][1] == 's': tris.append((A[j][0], B[j + 1][0], B[j][0]))
                continue
            if b_end:
                if A[j][1] == 's': tris.append((A[j][0], A[j + 1][0], B[j][0]))
                continue
            tris += [(A[j][0], A[j + 1][0], B[j + 1][0]), (A[j][0], B[j + 1][0], B[j][0])]
        for t_ in tris:
            if part is not head_hair: t_ = [hh + (q - hh) * p.HAIR_PART for q in t_]
            ids = [part.v(q, hn(q, hh)) for q in t_]; part.tri(*ids)
    plain[6, 'hairpart', ''].outward(hh)
    head_hair.outward(hh + np.array([0, 0, 3.0])); two_sided(head_hair, head_in)
    hc13 = hh + T[6]                               # the hair's centre in the chest's frame (no rotation in the rest pose)
    fc = np.array([hc13[0], hc13[1], 20.0])
    a0, a1, n = p.FALL_ARC
    ths = [math.radians(a0 + (a1 - a0) * j / n) for j in range(n + 1)]
    last = len(p.HAIR_FALL) - 1
    grid = [[np.array([hc13[0] + rx * math.cos(t), hc13[1] + cy + ry * math.sin(t),
                       z + (p.FALL_JAG[j % 2] if i == last else 0.0)]) for j, t in enumerate(ths)]
            for i, (z, rx, ry, cy) in enumerate([(nape_z + T[6][2] + p.FALL_TOP[0], ah[0] * nape_r[0] + p.FALL_TOP[1],
                                                  ah[1] * nape_r[1] + p.FALL_TOP[1], 0.0)] +
                                                [(z + dz, rx, ry, cy) for z, rx, ry, cy in p.HAIR_FALL[1:]])]
    fall = P(13, 'hair2')
    for a, b2 in zip(grid, grid[1:]):
        for j in range(n):
            q = [a[j], b2[j], b2[j + 1], a[j + 1]]
            quad(fall, q, [hn(x, fc) for x in q])
    fall.outward(fc + np.array([0, -2.0, 3.0]))


def hair_short_side(p, T, hc, plain, P):
    """A short cut parted on the figure's left (+x), the fringe swept to its right over the forehead's top: a shell
    laid over the skull (head_point pushed out along its normal), from the crown down to an edge whose height follows
    the angle round (HAIR_EDGE: (degrees from the front, + toward the figure's left, z from the eyes' height), linear
    between): the fringe's line over the forehead, the ears' tops at the sides, the nape at the back. HAIR_COLS_AT: the
    columns (degrees from the front; HAIR_EDGE_JAG: (z, to degrees): within that angle of the front the columns' edge
    alternately this much lower / higher, ragged ends); HAIR_ROWS: the rows from the crown to the edge (fractions of the edge's
    latitude). The shell's thickness HAIR_THICK: (crown, mid, edge) over the rows; the fringe (HAIR_FRINGE: from, to
    degrees, its edge thickness: it stands off the forehead) thicker at its edge. The part (HAIR_PART_AT: degrees,
    from this row fraction down to the front edge, pressed in x): a darker strip between its two columns (HAIR_PART_SOFT:
only one triangle of each of its quads darker, a softer two-tone line). Under the
    edge a lip down to the skin (no gap shows between the hair and the head)."""
    E = p.HAIR_EDGE
    edge_z = lambda d: float(np.interp(d, [e[0] for e in E], [e[1] for e in E]))
    cols = sorted(p.HAIR_COLS_AT)
    rows = list(p.HAIR_ROWS)
    t0, t1, t2 = p.HAIR_THICK
    f0, f1, ft = p.HAIR_FRINGE
    def fringe(d):                                 # 0 .. 1: how much of the fringe's lift a column takes
        if d < f0 - 15 or d > f1 + 15: return 0.0
        return float(np.interp(d, [f0 - 15, f0, f1, f1 + 15], [0.0, 1.0, 1.0, 0.0]))
    def thick(d, r):
        te = t2 + (ft - t2) * fringe(d)
        return float(np.interp(r, [0.0, 0.55, 1.0], [t0, t1, te]))
    pd, pr, pk = p.HAIR_PART_AT
    jag, jag_to = getattr(p, 'HAIR_EDGE_JAG', (0.0, 0.0))
    soft = getattr(p, 'HAIR_PART_SOFT', False)
    grid = {}                                      # (column, row) -> (point, normal)
    for ci, d in enumerate(cols):
        dz = jag * (1 if ci % 2 else -1) if abs(d) <= jag_to else 0.0   # the edge's ends alternately lower / higher
        lat_e = head_lat(p, edge_z(d) + dz)
        def point(r, t, d=d, lat_e=lat_e):
            q, n = head_point(p, 270.0 + d, max(0.0, r * lat_e))
            return hc + q + n * t, n
        for j, r in enumerate(rows):
            grid[d, j] = point(r, thick(d, r))
        grid[d, 'lip'] = point(1.0, 0.03)          # the lip under the edge, on the skin
    crown = hc + head_point(p, 270.0, 0.0)[0] + np.array([0.0, 0.0, t0])
    hair, part_s, lip = P(6, 'hair2'), P(6, 'hairpart'), P(6, 'hairin', 'lip')
    for ci, d in enumerate(cols):
        d2 = cols[(ci + 1) % len(cols)]
        is_part = abs(d - pd) < 6.0 and abs(d2 - pd) < 6.0 and d2 > d
        A = [grid[d, j] for j in range(len(rows))]; B = [grid[d2, j] for j in range(len(rows))]
        def put(part, qs, k=1.0):
            ids = []
            for x, n in qs:
                if k != 1.0: x = hc + (x - hc) * k
                ids.append(part.v(x, n))
            part.tri(*ids)
        put(hair, [(crown, (0.0, 0.0, 1.0)), A[0], B[0]])
        for j in range(len(rows) - 1):
            on = part_s if is_part and rows[j] >= pr - 1e-6 else hair
            k = pk if on is part_s else 1.0
            on2 = hair if soft else on             # soft: one triangle of each quad the part's, a two-tone line
            put(on, [A[j], A[j + 1], B[j + 1]], k); put(on2, [A[j], B[j + 1], B[j]], k)
        a, b = A[-1], B[-1]; la, lb = grid[d, 'lip'], grid[d2, 'lip']
        put(lip, [a, la, lb]); put(lip, [a, lb, b])
    hair.outward(hc); part_s.outward(hc)
    for k, (a, b, c) in enumerate(lip.t):         # the lip faces out and down
        pa, pb, pc = lip.p[a], lip.p[b], lip.p[c]
        m = (pa + pb + pc) / 3 - hc; m[2] -= 2.0
        if np.cross(pb - pa, pc - pa) @ m < 0: lip.t[k] = (a, c, b)


HAIR_STYLES = {'long': hair_long, 'short_side': hair_short_side}


def head(p, T, axis, collar_top, checker=False):
    """The head's parts (see the module's header): ({bone: [{'pos', 'col' (N,4) 0..1, 'uv' or None, 'idx', 'face'}]}
    in the bone's frame, the face texture's PNG bytes). The head over the collar's axis HEAD_AT[0] forward of it, the
    chin HEAD_AT[1] above the collar's top. Parts per bone in the order they were made, the face last."""
    plain = {}
    def P(b, kind, tag=''):
        if (b, kind, tag) not in plain: plain[b, kind, tag] = Part()
        return plain[b, kind, tag]
    nax = np.array([axis[0] - T[6][0], axis[1] - T[6][1]])           # the collar's axis, head frame
    hc = np.array([nax[0], nax[1] - p.HEAD_AT[0], collar_top - T[6][2] + p.HEAD_AT[1] + p.HEAD_R[4]])
    face, _ = skull(p, hc, plain, P)
    nk = Part()                                    # the neck: inside the collar up into the head
    nk.outward(loft(nk, [(np.array([nax[0], nax[1], z]), X3, Y3, rx, ry) for z, rx, ry in p.NECK], (False, False)))
    plain[6, 'neck', ''] = nk
    HAIR_STYLES[p.HAIR_STYLE](p, T, hc, plain, P)

    # vertex colours: one light from above-front (z up in the head's and the chest's frames), each colour shaded
    # unlit .. lit
    def shade(n, base, hi=None, amb=0.0):
        L = Z3 * 0.8 + np.array([0, -0.6, 0]); L /= np.linalg.norm(L)
        k = max(0.0, float(n @ L))
        if hi is None: return np.clip(base * (amb + (1 - amb) * k), 0, 255)
        return np.clip(base + (hi - base) * k, 0, 255)
    def backlit(c, n):                             # the hair's light from above-behind: the back of the hair shades
        Lb, k = p.HAIR_BACKLIT                     # across (bright down the middle), it reads round, not flat
        return np.clip(c + p.HAIR * k * max(0.0, float(n @ Lb) / np.linalg.norm(Lb)), 0, 255)
    HAIR = p.HAIR
    lo, hi = p.SKIN_SHADE
    nb, (nlo, nhi) = p.NECK_COLOUR
    fns = {'skin': lambda n: shade(n, p.SKIN * lo, p.SKIN * hi),
           'neck': lambda n: shade(n, nb * nlo, nb * nhi),
           'hair2': lambda n: backlit(shade(n, HAIR, amb=0.5), n),
           'hairin': lambda n: shade(n, HAIR * 0.45, HAIR * 0.62),
           'hairpart': lambda n: shade(n, HAIR * 0.5, HAIR * 0.68)}
    fns.update(getattr(p, 'HAIR_SHADES', {}))
    def prim(part, fn, uv):
        return {'pos': np.array(part.p), 'col': np.array([list(fn(n) / 255) + [1.0] for n in part.n]),
                'uv': np.array(part.uv, float) if uv else None, 'idx': np.array(part.t), 'face': uv}
    out = {}
    for (b, kind, _), part in plain.items():
        out.setdefault(b, []).append(prim(part, fns[kind], False))
    out.setdefault(6, []).append(prim(face, lambda n: shade(n, WHITE, amb=p.DASH_AMB), True))
    return out, face_texture(p, checker)
