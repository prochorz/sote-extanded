"""The Falcon's icon for the ship HUD (feature gallrun): HUD sprite slot 25 (the
Outrider seen from above, 64x41, grey indices the game tints by the ship's health) drawn again from the Falcon's model.

    cd harness && .venv/bin/python3 gallrun/hud_icon.py preview ../local/demo/hud_falcon.png [state.st]

preview: the Falcon's icon next to the Outrider's (from a state of the running mission, default
run/dedup_native.st), grey and in the HUD's green, 5x.

The drawing (falcon_indices()): the model's triangles (local/game/falcon.bin, flying along +y) seen from above, nose to
the right (model +y -> the sprite's +x, model +x, the starboard side, -> its +y: down), fitted to the sprite with
MARGIN px round it, SUPER x supersampled with a z-buffer; a dark body shaded by the light (BODY_LO..BODY_HI) under a
light rim (RIM) at the silhouette and a lighter line (EDGE) where the height jumps, as the Outrider's is drawn.
Index 0 is transparent.
"""
import os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import paths
from collide import extract

FALCON = os.path.join(paths.GAME, 'falcon.bin')
FALCON_BASE = 0x80500000
W, H = 64, 41                 # slot 25's size (the base level)
MARGIN, SUPER = 0, 4
LIGHT = np.array([-0.35, -0.35, 0.87])   # from above, the sprite's top left
BODY_LO, BODY_HI = 1, 6       # the body's indices, dark to light
RIM, EDGE, CREASE = 15, 12, 9 # the silhouette's rim, a height jump, a fold between panels
EDGE_Z = 0.8                  # model units: a jump this high between neighbours is drawn as a line
CREASE_COS = 0.93             # neighbours' normals further apart than this (~22 degrees): a fold
RING, SPOKE, DOME = 0.62, 9, 13   # the hull's ring (share of its radius round the turret), the spokes' and the
DOME_R = 0.17                 # turret dome's indices, the dome's radius (share of the hull's)
SPOKES = (90, 135, 180, 225, 270)   # degrees from the nose: the spokes from the ring to the rim (none forward)


def falcon_tris(path=FALCON):
    """(triangles, turret (x, y)): the model's and its turret's middle (falcon.bin's header +16)."""
    img = open(path, 'rb').read()
    n, lst = struct.unpack_from('>II', img, 4)
    return np.array(extract(img, FALCON_BASE, n, lst), np.float64), struct.unpack_from('>ff', img, 16)


def falcon_indices(T, turret=None):
    """(H, W) uint8 indices 0..15 of the Falcon seen from above."""
    sx, sy = T[..., 1], T[..., 0]                       # sprite x <- model y (nose), sprite y <- model x
    k = min((W - 2 * MARGIN) / np.ptp(sx), (H - 2 * MARGIN) / np.ptp(sy)) * SUPER
    cx, cy = (sx.max() + sx.min()) / 2, (sy.max() + sy.min()) / 2
    X = (sx - cx) * k + W * SUPER / 2; Y = (sy - cy) * k + H * SUPER / 2; Z = T[..., 2]
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-9)[:, None]
    nrm[nrm[:, 2] < 0] *= -1                            # (seen from above: either side)
    shade = 0.25 + 0.75 * np.clip(nrm @ (LIGHT / np.linalg.norm(LIGHT)), 0, 1)
    HS, WS = H * SUPER, W * SUPER
    zb = np.full((HS, WS), -1e9); sb = np.zeros((HS, WS)); tb = np.full((HS, WS), -1)
    for t in range(len(T)):
        x, y, z = X[t], Y[t], Z[t]
        x0, x1 = max(int(np.floor(x.min())), 0), min(int(np.ceil(x.max())), WS - 1)
        y0, y1 = max(int(np.floor(y.min())), 0), min(int(np.ceil(y.max())), HS - 1)
        if x0 > x1 or y0 > y1: continue
        px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9: continue
        a = ((y[1] - y[2]) * (px - x[2]) + (x[2] - x[1]) * (py - y[2])) / d
        b = ((y[2] - y[0]) * (px - x[2]) + (x[0] - x[2]) * (py - y[2])) / d
        c = 1 - a - b
        m = (a >= 0) & (b >= 0) & (c >= 0)
        zz = a * z[0] + b * z[1] + c * z[2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]; up = m & (zz > sub)
        sub[up] = zz[up]; sb[y0:y1 + 1, x0:x1 + 1][up] = shade[t]; tb[y0:y1 + 1, x0:x1 + 1][up] = t
    cov = (zb > -1e9).reshape(H, SUPER, W, SUPER).mean((1, 3))
    zs = np.where(zb > -1e9, zb, np.nan).reshape(H, SUPER, W, SUPER)
    with np.errstate(all='ignore'):
        import warnings; warnings.simplefilter('ignore')
        z = np.nanmean(zs, (1, 3))
    s = sb.reshape(H, SUPER, W, SUPER).sum((1, 3)) / np.maximum((zb > -1e9).reshape(H, SUPER, W, SUPER).sum((1, 3)), 1)
    on = cov >= 0.5
    idx = np.where(on, np.round(BODY_LO + (BODY_HI - BODY_LO) * s), 0).astype(np.uint8)
    pad = np.pad(on, 1)
    rim = on & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    zp = np.pad(np.nan_to_num(z, nan=-1e9), 1, constant_values=-1e9)
    jump = np.zeros_like(on)
    for dy, dx in ((0, 1), (1, 0)):
        nb = zp[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx]
        jump |= on & (nb > -1e8) & (np.abs(nb - z) > EDGE_Z) & (z > nb)   # (the higher side)
    tc = tb.reshape(H, SUPER, W, SUPER)[:, SUPER // 2, :, SUPER // 2]   # (each pixel's middle sample's triangle)
    nc = np.where((tc >= 0)[..., None], nrm[np.maximum(tc, 0)], 0)
    fold = np.zeros_like(on)
    for dy, dx in ((0, 1), (1, 0)):
        a, b = nc[:H - dy, :W - dx], nc[dy:, dx:]
        f = on[:H - dy, :W - dx] & on[dy:, dx:] & ((a * b).sum(-1) < CREASE_COS)
        fold[:H - dy, :W - dx] |= f
    idx[fold] = CREASE; idx[jump] = EDGE
    if turret is not None:                              # the hull's ring, spokes and dome round the turret
        tx, ty = (turret[1] - cx) * k / SUPER + W / 2, (turret[0] - cy) * k / SUPER + H / 2
        yy, xx = np.mgrid[0:H, 0:W] + 0.5
        r, ang = np.hypot(xx - tx, yy - ty), np.degrees(np.arctan2(yy - ty, xx - tx)) % 360
        R = np.percentile(r[rim & (xx < tx)], 50)        # (the round back half's rim)
        idx[on & (np.abs(r - RING * R) < 0.6)] = EDGE
        for a in SPOKES:
            da = np.abs((ang - a + 180) % 360 - 180)
            idx[on & (r > RING * R) & (r < R) & (da * np.pi / 180 * r < 0.6)] = SPOKE
        idx[on & (r < DOME_R * R)] = DOME
        idx[on & (np.abs(r - DOME_R * R) < 0.6)] = RIM
    idx[rim] = RIM
    return idx


def hud_sprite(state):
    """The Outrider's icon (slot 25) as indices from a state of the running mission (RDRAM found by the image's
    'GALL' magic)."""
    import gzip
    d = gzip.open(state).read()
    base = d.find(b'LLAG') - 0x618000
    E = np.frombuffer(d[base:base + 0x800000], '<u4').astype('>u4').tobytes()
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    Hh = lambda a: struct.unpack_from('>h', E, a & 0x7FFFFF)[0]
    a = R(R(0x8013CE2C) + 4 * 25)
    w, h, nb, bm = Hh(a + 4), Hh(a + 6), Hh(a + 0x1C), R(a + 0x24)
    img, y = np.zeros((h, w), np.uint8), 0
    for k in range(nb):
        bw, bh, buf = Hh(bm + 8 * k), Hh(bm + 8 * k + 2), R(bm + 8 * k + 4)
        rb = (bw + 15) // 16 * 8
        raw = bytearray(E[buf & 0x7FFFFF:(buf & 0x7FFFFF) + rb * bh])
        for r in range(1, bh, 2):
            for q in range(r * rb, (r + 1) * rb, 8): raw[q:q + 4], raw[q + 4:q + 8] = raw[q + 4:q + 8], raw[q:q + 4]
        px = np.frombuffer(bytes(raw), np.uint8)
        img[y:y + bh] = np.stack([px >> 4, px & 15], 1).reshape(bh, rb * 2)[:, :bw]; y += bh
    lut = [struct.unpack_from('>H', E, (R(a + 0x18) & 0x7FFFFF) + 2 * k)[0] for k in range(16)]
    grey = np.array([(v >> 11 & 31) * 255 // 31 for v in lut])
    return img, grey, np.array([v & 1 for v in lut])


def preview(out, state):
    from PIL import Image, ImageDraw
    o_idx, o_grey, o_a = hud_sprite(state)
    T, tur = falcon_tris()
    f_idx = falcon_art(T, tur)
    f_grey = np.array([0] + [round(255 * k / 14) for k in range(15)])   # (face_sprite()'s ramp: index 0 transparent)
    def pic(idx, grey, alpha, green):
        g = np.where(alpha[idx] == 1, grey[idx], 0)
        rgb = np.stack([g * 0.25, g, g * 0.25], -1) if green else np.stack([g] * 3, -1)
        return Image.fromarray(rgb.astype(np.uint8)).resize((W * 5, H * 5), Image.NEAREST)
    f_a = np.array([0] + [1] * 15)
    sheet = Image.new('RGB', (2 * W * 5 + 30, 2 * H * 5 + 70), (10, 10, 14)); dr = ImageDraw.Draw(sheet)
    for c, (name, idx, grey, al) in enumerate((('Outrider (now)', o_idx, o_grey, o_a), ('Falcon (new)', f_idx, f_grey, f_a))):
        dr.text((10 + c * (W * 5 + 10), 6), name, fill=(230, 230, 230))
        sheet.paste(pic(idx, grey, al, False), (10 + c * (W * 5 + 10), 24))
        sheet.paste(pic(idx, grey, al, True), (10 + c * (W * 5 + 10), 34 + H * 5))
    sheet.save(out)
    print('falcon indices used', sorted(set(f_idx.ravel().tolist())), 'filled px', int((f_idx > 0).sum()))




# The line-art drawing (the user, 2026-10-17: the shaded raster was far from the Outrider's look): the model's
# silhouette only, then crisp 1-px lines on a black body as the Outrider's icon has them.
ART = dict(body=1, panel=3, rim=15, rim_in=8, ring=11, spoke=7, dome=6, dome_rim=15, gun=15, engine=13, mand=9,
           cockpit=14, dish=12)


def _px(idx, on, pts, v):
    for x, y in pts:
        xi, yi = int(np.floor(x)), int(np.floor(y))
        if 0 <= yi < idx.shape[0] and 0 <= xi < idx.shape[1] and on[yi, xi]: idx[yi, xi] = v


def _line(idx, on, a, b, v):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2) + 1
    _px(idx, on, zip(np.linspace(a[0], b[0], n), np.linspace(a[1], b[1], n)), v)


def _arc(idx, on, c, r, a0, a1, v):
    t = np.radians(np.linspace(a0, a1, max(int(abs(a1 - a0) / 180 * np.pi * r * 3), 8)))
    _px(idx, on, zip(c[0] + r * np.cos(t), c[1] + r * np.sin(t)), v)


def falcon_art(T, turret):
    base = falcon_indices(T, None)
    on = base > 0
    H_, W_ = on.shape
    sx, sy = T[..., 1], T[..., 0]
    k = min((W - 2 * MARGIN) / np.ptp(sx), (H - 2 * MARGIN) / np.ptp(sy))
    cx, cy = (sx.max() + sx.min()) / 2, (sy.max() + sy.min()) / 2
    to = lambda mx, my: ((my - cx) * k + W / 2, (mx - cy) * k + H / 2)   # model (x, y) -> sprite (x, y)
    tx, ty = to(*turret)
    pad = np.pad(on, 1)
    edge = on & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    pad2 = np.pad(on & ~edge, 1)
    edge2 = (on & ~edge) & ~(pad2[:-2, 1:-1] & pad2[2:, 1:-1] & pad2[1:-1, :-2] & pad2[1:-1, 2:])
    yy, xx = np.mgrid[0:H_, 0:W_] + 0.5
    r = np.hypot(xx - tx, yy - ty)
    R = np.percentile(r[edge & (xx < tx)], 50)
    idx = np.where(on, ART['body'], 0).astype(np.uint8)
    idx[on & (r > RING * R) & (xx < tx + R * 0.95)] = ART['panel']          # the outer ring of panels
    idx[edge2] = ART['rim_in']; idx[edge] = ART['rim']
    _arc(idx, on, (tx, ty), RING * R, 0, 360, ART['ring'])
    for a in (60, 100, 140, 180, 220, 260, 300):                          # spokes (none into the mandibles)
        t = np.radians(a)
        _line(idx, on, (tx + RING * R * np.cos(t), ty + RING * R * np.sin(t)),
              (tx + (R - 1.5) * np.cos(t), ty + (R - 1.5) * np.sin(t)), ART['spoke'])
    _arc(idx, on, (tx, ty), R - 1.2, 150, 210, ART['engine'])               # the engine strip at the back
    _arc(idx, on, (tx, ty), R - 2.2, 155, 205, ART['engine'])
    front = on & (xx > tx + R * 0.7)                                          # the mandibles: a line along each
    for side in (-1, 1):
        rows = [y for y in range(H_) if (front[y].any() and (y - ty) * side > 1.5)]
        pts = []
        for y in rows:
            xs = np.nonzero(front[y])[0]
            if len(xs): pts.append((xs.mean(), y + 0.5))
        for p in pts: _px(idx, on & ~edge, [p], ART['mand'])
    d = R * 0.18                                                              # the dome, its guns toward the nose
    _arc(idx, on, (tx, ty), d, 0, 360, ART['dome_rim'])
    idx[on & (r < d - 0.8)] = ART['dome']
    _line(idx, on, (tx, ty - 0.8), (tx + d + 2.5, ty - 0.8), ART['gun'])
    _line(idx, on, (tx, ty + 0.8), (tx + d + 2.5, ty + 0.8), ART['gun'])
    cyx = max(range(H_), key=lambda y: (on[y] & (xx[y] > tx)).sum() * 0 + y if (on[y] & (xx[y] > tx)).any() else -1)
    ccols = np.nonzero(on[cyx] & (xx[cyx] > tx))[0]                          # the cockpit: the starboard side's
    if len(ccols):                                                            # lowest point forward of the middle
        c = (ccols.mean() + 0.5, cyx - 1.5)
        _arc(idx, on, c, 2.0, 0, 360, ART['cockpit'])
        _line(idx, on, (tx + R * 0.45, c[1]), (c[0] - 2, c[1]), ART['cockpit'])
    dsh = (tx + R * 0.35, ty - R * 0.62)                                      # the radar dish, port side
    _arc(idx, on, dsh, 2.2, 0, 360, ART['dish']); _px(idx, on, [dsh], ART['dish'])
    return idx


def falcon_icon(E, t, put):
    """Slot 25's sprite drawn as the Falcon (falcon_art()): template t (the Outrider's icon in RAM E of
    states/src_base.st, 64x41 in full-width CI4 strips) with its 0x30-byte header copied, +0x18 a grey TLUT (index 0
    transparent, 1..15 round(31 k / 14)), +0x24 the new strips (odd rows' 4-byte halves swapped), +0x28..0x2F zeroed,
    as gall_asset.face_sprite(). Copied with put(bytes) -> address; returns the sprite's."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    Hh = lambda a: struct.unpack_from('>h', E, a & 0x7FFFFF)[0]
    Wt, ht, nb, bm = Hh(t + 4), Hh(t + 6), Hh(t + 0x1C), R(t + 0x24)
    assert (Wt, ht) == (W, H), f'slot 25 is {Wt}x{ht}, not the Outrider icon we know'
    idx = falcon_art(*falcon_tris())
    bms, y = bytearray(), 0
    for k in range(nb):
        w, hh = Hh(bm + 8 * k), Hh(bm + 8 * k + 2)
        assert w == W, 'the template icon is not in full-width strips'
        rows = idx[y:y + hh]; y += hh
        raw = bytearray((rows[:, 0::2] << 4 | rows[:, 1::2]).astype(np.uint8).tobytes())
        rb = W // 2
        for r in range(1, hh, 2):
            for q in range(r * rb, (r + 1) * rb, 8): raw[q:q + 4], raw[q + 4:q + 8] = raw[q + 4:q + 8], raw[q:q + 4]
        bms += struct.pack('>hhI', w, hh, put(bytes(raw)))
    assert y == H, 'the strips do not cover the icon'
    lut = bytes(2) + b''.join(struct.pack('>H', (g << 11) | (g << 6) | (g << 1) | 1) for g in (round(31 * k / 14) for k in range(15)))
    sp = bytearray(E[t & 0x7FFFFF:(t & 0x7FFFFF) + 0x30])
    struct.pack_into('>I', sp, 0x18, put(lut))
    struct.pack_into('>I', sp, 0x24, put(bytes(bms)))
    sp[0x28:0x30] = bytes(8)
    return put(bytes(sp))

if __name__ == '__main__':
    if sys.argv[1] == 'preview':
        preview(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.path.join(paths.RUN, 'dedup_native.st'))
