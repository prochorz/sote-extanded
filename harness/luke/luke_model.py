"""Generate Luke's head (the Look row's Luke: the red guard's armour with this head instead of the helmet) as glTF on
the palace guard's head bone, for harness/guard_asset.py (it bakes it onto Dash's head bone as it does the helmet).

    M64CPU=0 python3 luke/luke_model.py <rom> [out.gltf]      (default harness/luke/luke_head.gltf)
    python3 luke/luke_model.py --face <photo>                 writes harness/luke/face_src.png from the photo, once
    M64CPU=0 python3 luke/luke_model.py --profile <rom>       the head's profile numbers against the figure's
                                                              (PROFILE_TARGETS); exit 1 if one fails
    GURI_RAM=<file>      read a palace.st RAM dump (big-endian, 8 MB) instead of running the emulator

The glTF has one node, `bone_06` (the guard's head bone, trSt 6: translation its node's +0x38 over the chest), its
mesh in that bone's frame (z up, front -y, local units = vertex units / 8). Made by harness/pose/head_model.py with
LUKE's constants:
- the skull a man's: wider at the jaw, a square chin forward under the lips as the figure's (HEAD_JAW; checked by
  --profile), built at the guard helmet's inside, then every part but the neck x HEAD_SCALE about the chin's bottom
  (the chin stays on the collar, the head grows up and out): the head, hair included, x -6.97 .. 7.53, y -9.06 ..
  9.43, z -1.0 .. 17.72 in the head frame, about the helmet's own box (x -8.1 .. 8.8, y -10.3 .. 10.1, z -2.9 .. 15.6;
  its top 2.1 over the helmet's);
- the face from the photo of the figure (face_src.png: its front view cut brow to chin, cheek to cheek, FACE_CROP),
  with its relief (the nose, the brow, the chin, from the side view's profile);
- the hair short, light brown (the photo's mid and shadow tones), parted on his left (a soft two-tone line), the
  fringe swept to his right, its ends ragged all round, over the ears down to the lobes at the sides, low on the nape;
- the neck a black turtleneck from inside the armour's collar (the guard chest's neck ring: centre x 0.5, y -0.63,
  its front's top z 21.25 in the chest frame) up into the head, its top ring a roll under the chin, its rings' half x
  and half y x NECK_SCALE (half x up to 4.2, about 0.56 of the head's half width: a turtleneck's).
<= 600 triangles.
"""
import os, sys, types
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
H = os.path.dirname(HERE)
sys.path.insert(0, H); sys.path.insert(0, os.path.join(H, 'guri')); sys.path.insert(0, os.path.join(H, 'pose'))
import gltf, head_model

FACE_PNG = os.path.join(HERE, 'face_src.png')
# the photo's front view, the face brow to chin, cheek to cheek (its pixels: left, top, right, bottom), cut to 64 x 64
FACE_CROP = (336.5, 175.0, 422.5, 261.0)
FACE_SIZE = 64

# the chest's collar (the guard chest's neck ring, chest frame) and the turtleneck's top: the chin HEAD_AT[1] above it
COLLAR_AXIS, COLLAR_TOP = (0.5, -0.63), 23.9
SKIN = np.array((235, 196, 165))
HAIR = np.array((130, 106, 74))              # the photo's hair: mid tone (its median over the crown and the back)
HAIR_SHADOW = np.array((96, 73, 48))         # its shadow tone (the back's darkest 15 %), unlit
HAIR_LIT = 1.08                              # lit: the photo's 70th percentile, (139, 114, 81)
TURTLENECK = np.array((34, 30, 30))
# The head's parts (all but the neck) scaled about the chin's bottom on the collar's axis: uniform, so the face, its
# relief and --profile's ratios stay. At 1.0 (sized inside the helmet, half width 6.0) it read too small over the
# armour's shoulder pads in the duel's frames (the user, 2026-11-11)
HEAD_SCALE = 1.2
# The neck rings' half x and half y: at 1.0 (half x 2.9 .. 3.35, 0.6 of the head's half width, a bare neck's ratio) it
# read as a thin stalk in the collar (the user, 2026-11-11); its bottom ring stays inside the collar in the front,
# side and back stills
NECK_SCALE = 1.35
L = types.SimpleNamespace(
    HEAD_AROUND=12, HEAD_BANDS=8,
    HEAD_R=(5.0, 5.9, 6.5, 6.8, 7.4),        # half width, depth to the front, to the back, eyes to crown, to chin
    HEAD_TOP=0.8,
    # (latitude from the crown: x, front depth, back depth factors, y shift): a man's jaw, wide to the chin's corners,
    # the chin square (its x kept wide near the bottom), the back narrowing into the neck. The keys from 135 on bring
    # the lower face forward to the figure's chin (--profile: it sat 0.181 x depth behind the nose, 0.119 ahead of the
    # neck, the photo 0.105 / 0.20; 2026-11-09); 149 holds the chin relief ring's latitude near the chin's front (with
    # 135..157.5 alone it and the chin's corner could not both sit there); a negative y shift moves a ring forward
    HEAD_JAW=[(0.0, 1.0, 1.0, 1.0, 0.3), (60.0, 1.02, 1.0, 1.08, 0.3), (78.0, 1.03, 1.0, 1.06, 0.2),
              (90.0, 1.0, 1.0, 1.03, 0.1), (112.5, 0.99, 0.98, 0.86, 0.0),
              (135.0, 1.0, 1.21, 0.55, -0.3), (149.0, 1.09, 1.45, 0.43, -0.3), (157.5, 1.15, 2.3, 0.35, -0.3),
              (180.0, 3.0, 3.2, 0.3, -0.3)],
    HEAD_AT=(0.4, 0.56),
    HEAD_THS=(15.0, 90.0, 165.0, 195.0, 225.0, 255.0, 263.0, 270.0, 277.0, 285.0, 315.0, 345.0),
    HEAD_DEPTH_NOSE=0.13,
    # rows of face_src.png: the brow, the eyes, the nose's tip, its base, the lips, the ring under them (row 47.24: the
    # 135 latitude, so the lips run straight down to the chin, no dent), the chin's front, its underside
    FACE_RELIEF=[(3.7, [(0.0, 0.25), (1.2, 0.35), (3.3, 0.3), (4.3, 0.0)]),
                 (10.4, [(0.0, 0.4), (0.7, 0.12), (1.2, -0.18), (3.3, -0.12), (4.3, 0.0)]),
                 (25.3, [(0.0, None), (0.6, 0.6), (1.2, 0.1), (2.2, 0.0)]),
                 (28.3, [(0.0, 0.4), (0.6, 0.55), (1.2, 0.4), (2.7, 0.1), (3.7, 0.0)]),
                 (40.2, [(0.0, 0.13), (0.8, 0.12), (2.1, 0.06), (2.9, 0.02), (3.5, 0.0)]),
                 (47.24, [(0.0, 0.4), (0.8, 0.38), (2.0, 0.24), (2.8, 0.1), (3.5, 0.0)]),
                 (55.1, [(0.0, 1.15), (0.9, 1.08), (1.8, 0.83), (2.6, 0.4), (3.4, 0.0)]),
                 (61.5, [(0.0, 1.3), (0.6, 1.25), (1.4, 1.0), (2.0, 0.4), (2.6, 0.0)])],
    FACE_TEX=(64, 64), FACE_SECT=(195.0, 345.0, 45.0),
    FACE_SRC=(FACE_PNG, 32.0, 10.4, 62.5),   # the file, the eyes' centre x, their y, the chin's lowest y (its pixels)
    FACE_LIFT=(1.35, 1.1), FACE_BLEND=2.0, FACE_FLAT=5.0,
    FACE_HAIR=(0, 0, 1.0),                   # none by hue: the photo's hair has the skin's hue and saturation
    FACE_SIDE=(7, 0.5),                      # the hair at the crop's sides: darker than the cheeks (value 0.7 .. 0.85)
    SKIN=SKIN, SKIN_SHADE=(0.6, 1.0), DASH_AMB=0.6,
    NECK=[(z, x * NECK_SCALE, y * NECK_SCALE) for z, x, y in
          [(-5.5, 3.0, 3.0), (-2.3, 3.0, 2.6), (-1.9, 3.35, 2.75), (-1.45, 3.3, 2.65), (-1.15, 2.9, 2.3),
           (2.0, 2.5, 2.0)]],                # (z, half x, half y), head frame: from inside the armour, the roll, in
    # (the top rings' half y narrowed: the neck set back under the chin, 0.24 x depth behind it, the figure 0.20)
    NECK_COLOUR=(TURTLENECK, (0.7, 1.5)),
    HAIR_STYLE='short_side', HAIR=HAIR,
    # the fringe over the forehead, the temples, over the ears down to the lobe at the sides (higher than mid-jaw: the
    # jaw line shows below it, as on the figure), low on the nape
    HAIR_EDGE=[(-180.0, -5.7), (-130.0, -5.0), (-100.0, -3.1), (-85.0, -2.7), (-70.0, -0.6), (-55.0, 0.9),
               (-45.0, 1.1), (-20.0, 1.5), (0.0, 1.8), (25.0, 2.4), (35.0, 2.6), (50.0, 1.9), (58.0, 1.0),
               (70.0, -0.6), (85.0, -2.7), (100.0, -3.1), (130.0, -5.0), (180.0, -5.7)],
    HAIR_COLS_AT=(-180.0, -157.5, -135.0, -115.0, -95.0, -75.0, -55.0, -35.0, -15.0, 0.0, 15.0, 30.0, 40.0, 55.0,
                  75.0, 95.0, 115.0, 135.0, 157.5),
    HAIR_EDGE_JAG=(0.8, 180.0),             # the ends ragged all round (a loose outline, not a cap's)
    HAIR_ROWS=(0.25, 0.5, 0.72, 0.88, 1.0),
    HAIR_THICK=(1.4, 1.3, 0.6),             # the shell's thickness: crown, mid, edge
    HAIR_FRINGE=(-50.0, 30.0, 0.8),          # the fringe: from, to (degrees), its edge's thickness
    HAIR_PART_AT=(35.0, 0.5, 1.0),           # the part: degrees, from this row fraction to the front edge, pressed in
    HAIR_PART_SOFT=True,                     # a two-tone line (one triangle of each quad), not a dark strip
    HAIR_SHADES={})
# the hair's shades: the photo's shadow tone unlit .. its mid tone lit (a little over: the lit top), the inner lip and
# the part darker; the second light from above-behind a little
L.HAIR_BACKLIT = (np.array([0.0, 0.8, 0.6]), 0.15)


def _hair_shades():
    def shade(n, lo, hi):
        Lv = np.array([0.0, -0.6, 0.8]); Lv /= np.linalg.norm(Lv)
        return np.clip(lo + (hi - lo) * max(0.0, float(n @ Lv)), 0, 255)
    def backlit(c, n):
        Lb, k = L.HAIR_BACKLIT
        return np.clip(c + HAIR * k * max(0.0, float(n @ Lb) / np.linalg.norm(Lb)), 0, 255)
    return {'hair2': lambda n: backlit(shade(n, HAIR_SHADOW, HAIR * HAIR_LIT), n),
            'hairin': lambda n: shade(n, HAIR_SHADOW * 0.55, HAIR_SHADOW * 0.75),
            'hairpart': lambda n: shade(n, HAIR_SHADOW * 0.85, HAIR * 0.9)}
L.HAIR_SHADES = _hair_shades()


# from this row down, a pixel darker than FILL_DARK x its row's skin (the median of the middle columns) takes that skin:
# the crop's bottom holds the chin's shadow and the turtleneck at the jaw's corners, drawn under the mouth as a dark patch
FILL_ROW, FILL_DARK, FILL_MID = 46, 0.8, (20, 44)


def write_face(photo):
    """face_src.png: the photo's FACE_CROP resized to FACE_SIZE square, its bottom rows' dark pixels filled with skin."""
    im = Image.open(photo).convert('RGB')
    x0, y0, x1, y1 = FACE_CROP
    a = np.asarray(im.resize((FACE_SIZE, FACE_SIZE), Image.LANCZOS, box=(x0, y0, x1, y1))).copy()
    filled = 0
    for r in range(FILL_ROW, FACE_SIZE):
        mid = a[r, FILL_MID[0]:FILL_MID[1]].astype(float)
        skin = np.median(mid[mid.mean(1) >= np.median(mid.mean(1)) * FILL_DARK], axis=0)
        dark = a[r].astype(float).mean(1) < skin.mean() * FILL_DARK
        a[r, dark] = skin.round().astype(np.uint8); filled += int(dark.sum())
    Image.fromarray(a).save(FACE_PNG)
    print('wrote', FACE_PNG, f'({filled} dark pixels of rows {FILL_ROW}.. filled with skin)')


def pivot(T):
    """The chin's bottom on the collar's axis, head frame (where head_model.head places the chin)."""
    return np.array([COLLAR_AXIS[0] - T[6][0], COLLAR_AXIS[1] - T[6][1] - L.HEAD_AT[0],
                     COLLAR_TOP - T[6][2] + L.HEAD_AT[1]])


def head_parts(T):
    """head_model.head's parts, every part but the neck scaled HEAD_SCALE about pivot(T)."""
    parts, face_png = head_model.head(L, T, COLLAR_AXIS, COLLAR_TOP)
    pv = pivot(T)
    for q, k in zip(parts[6], PART_KINDS):
        if k != 'neck': q['pos'] = pv + (np.asarray(q['pos'], float) - pv) * HEAD_SCALE
    return parts, face_png


def build(T):
    parts, face_png = head_parts(T)
    assert list(parts) == [6], f'parts off the head bone: {list(parts)}'
    ps = [dict(q, material=1 if q['face'] else 0) for q in parts[6]]
    for q in ps: del q['face']
    return {'generator': 'harness/luke/luke_model.py',
            'nodes': [{'name': 'bone_06', 'translation': T[6].tolist(), 'children': [], 'mesh': 0}],
            'scene': [0], 'meshes': [ps],
            'materials': [{'name': 'PLAIN', 'png': None}, {'name': 'FACE', 'png': face_png}]}


def check(path):
    """One node bone_06 with a mesh, <= 600 triangles, a 64 x 64 face texture; prints the head's box."""
    g = gltf.read(path)
    assert [n['name'] for n in g['nodes']] == ['bone_06'] and g['nodes'][0]['mesh'] == 0
    ps = g['meshes'][0]
    tris = sum(len(p['idx']) for p in ps)
    allp = np.vstack([p['pos'] for p in ps])
    face = Image.open(__import__('io').BytesIO(g['materials'][1]['png']))
    assert tris <= 600, tris
    assert face.size == (64, 64) and face.convert('RGB').getcolors(16) is not None
    print(f'check: bone_06, {tris} triangles, face {face.size[0]}x{face.size[1]} '
          f'{len(face.convert("RGB").getcolors(16))} colours, box {np.round(allp.min(0), 2)} .. {np.round(allp.max(0), 2)}')
    return tris


# The figure's profile (the photo's side view, the middle panel; its pixels, measured from the silhouette against the
# backdrop): the nose's tip x 1316 (y 202), the lips 1309 (y 218), the chin's front 1302 (y 235, half way from the
# lips to its underside), the underside y 252, the turtleneck's front 1275 (y 260, one unit below the chin), the
# back of the hair 1183 (y 198); the eyes y 181. Its ratios to the head's depth (the back of the hair to the nose's
# tip, 133): the chin 0.105 behind the nose's tip, 0.20 ahead of the neck, 0.053 behind the lips; the jaw's corner
# under the ear, the hair ending at its lobe. The targets, (low, high) of the ratio or the distance:
PROFILE_TARGETS = {
    'chin behind nose': (0.08, 0.14),         # x depth
    'chin ahead of neck': (0.18, 0.28),       # x depth
    'chin vs lips': (-0.05, 0.05),            # x depth (+: behind the lips)
    'jaw below hair': (0.6, None),            # units: the jaw's corner below the hair's edge at the side
    'dent lips-chin': (None, 0.02),           # x depth: the mid line's deepest point behind the lips-chin straight line
    'triangles': (None, 600),
}
PART_KINDS = ('skin', 'neck', 'hair2', 'hairpart', 'hairin', 'face')   # head_model.head's parts on bone 6, in order


def _hits(tris, o, d):
    """Möller-Trumbore: the distances along d from o to each triangle hit (inf where missed)."""
    e1, e2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    pv = np.cross(d, e2); det = (e1 * pv).sum(1)
    ok = np.abs(det) > 1e-9; inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    tv = o - tris[:, 0]; u = (tv * pv).sum(1) * inv
    qv = np.cross(tv, e1); v = (qv * d).sum(1) * inv; t = (qv * e2).sum(1) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
    return np.where(hit, t, np.inf)


def profile(T):
    """The head's profile in the head's centre frame (the eyes' height z 0, front -y), measured on the built mesh by
    rays: along the mid line (x 0) the nose's tip, the lips, the chin's front (half way from the lips down to its
    underside) and its underside, the neck's front 1.0 below it, the back of the hair (the depth: it to the nose's
    tip); from each side (+-x) at the side ring's y, the lowest skin (the jaw's corner) and the lowest hair seen first;
    printed against PROFILE_TARGETS. Returns (all pass, the numbers)."""
    parts, _ = head_parts(T)
    assert len(parts[6]) == len(PART_KINDS), len(parts[6])
    pv = pivot(T)                                 # the built mesh, measured in the unscaled head's units: the head's
    hc = pv + np.array([0.0, 0.0, L.HEAD_R[4] * HEAD_SCALE])    # centre scaled as its parts, then all / HEAD_SCALE
    tris, kind = [], []
    for q, k in zip(parts[6], PART_KINDS):
        tris.append((q['pos'][q['idx']] - hc) / HEAD_SCALE); kind += [k] * len(q['idx'])
    tris, kind = np.vstack(tris), np.array(kind)
    ntri = len(tris)
    skull = np.isin(kind, ('skin', 'face')); hair = np.isin(kind, ('hair2', 'hairpart', 'hairin'))
    def first(o, d, mask=None):                    # (distance, kind) of the first hit
        t = _hits(tris, np.asarray(o, float), np.asarray(d, float))
        if mask is not None: t = np.where(mask, t, np.inf)
        i = int(np.argmin(t)); return (t[i], kind[i]) if np.isfinite(t[i]) else (np.inf, None)
    F, BK = 30.0, np.array([0.0, 1.0, 0.0])
    front = lambda z, m=None: first((0.0, -F, z), BK, m)[0] - F          # the first hit's y from the front
    s_ph = L.HEAD_R[4] / (L.FACE_SRC[3] - L.FACE_SRC[2])
    z_lips = -(40.2 - L.FACE_SRC[2]) * s_ph
    zs = np.arange(-0.5, z_lips + 1.0, -0.05)
    y_nose = min(front(z, skull) for z in zs)
    y_lips = front(z_lips, skull)
    ys = np.arange(-8.0, 4.0, 0.05)                # the underside: rays up the mid line, the lowest skull hit
    z_under = min(first((0.0, y, -F), (0.0, 0.0, 1.0), skull)[0] - F for y in ys)
    z_chin = (z_lips + z_under) / 2
    y_chin = front(z_chin, skull)
    zl = np.linspace(z_lips, z_chin, 41)          # the profile from the lips to the chin: no point far behind the chord
    dent = max(front(z, skull) - (y_lips + (y_chin - y_lips) * (z - z_lips) / (z_chin - z_lips)) for z in zl)
    y_neck = front(z_under - 1.0, kind == 'neck')
    y_back = max(F - first((0.0, F, z), -BK, ~(kind == 'neck'))[0] for z in np.arange(8.0, -6.0, -0.1))
    depth = y_back - y_nose
    y_side = head_model.head_point(L, 0.0, 90.0)[0][1]
    jaw, hl = [], []
    for sx in (1.0, -1.0):                        # from each side: down the side ring's column, the first hit's kind
        zk = [(z, first((sx * F, y_side, z), (-sx, 0.0, 0.0))[1]) for z in np.arange(2.0, -10.0, -0.05)]
        jaw.append(min([z for z, k in zk if k in ('skin', 'face')], default=np.nan))
        hl.append(min([z for z, k in zk if k in ('hair2', 'hairpart', 'hairin')], default=np.nan))
    n = {'nose tip y': y_nose, 'lips y': y_lips, 'chin front y': y_chin, 'chin front z': z_chin,
         'chin underside z': z_under, 'neck front y': y_neck, 'back y': y_back, 'depth': depth,
         'jaw corner z (+x, -x)': tuple(jaw), 'hair edge z (+x, -x)': tuple(hl),
         'chin behind nose': (y_chin - y_nose) / depth, 'chin ahead of neck': (y_neck - y_chin) / depth,
         'chin vs lips': (y_chin - y_lips) / depth, 'jaw below hair': min(h - j for h, j in zip(hl, jaw)),
         'dent lips-chin': dent / depth,
         'triangles': ntri}
    ok = True
    for k, v in n.items():
        tg = PROFILE_TARGETS.get(k)
        txt = '(' + ', '.join(f'{x:.2f}' for x in v) + ')' if isinstance(v, tuple) else f'{v:.3f}'
        if tg is None: print(f'  {k:24s} {txt}'); continue
        good = (tg[0] is None or v >= tg[0]) and (tg[1] is None or v <= tg[1]); ok &= good
        print(f'  {k:24s} {txt:>10s}   target {tg[0]} .. {tg[1]}   {"PASS" if good else "FAIL"}')
    print('profile:', 'PASS' if ok else 'FAIL')
    return ok, n


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    if sys.argv[1] == '--face':
        write_face(sys.argv[2]); sys.exit()
    from guri_model import dump_ram, guard_skeleton
    if sys.argv[1] == '--profile':
        T, _, _ = guard_skeleton(dump_ram(sys.argv[2]))
        sys.exit(0 if profile(T)[0] else 1)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'luke_head.gltf')
    T, _, _ = guard_skeleton(dump_ram(sys.argv[1]))
    gltf.write(out, build(T))
    print('wrote', out)
    check(out)
