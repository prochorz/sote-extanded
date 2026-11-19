"""Luke's lightsaber for the Look on Luke (feature `saber`, saber.c / guard.c): one mesh on Dash's right hand bone (trot
bone 6), in that bone's frame (local units = vertex units / 8), for harness/guard_asset.py (it puts it into guard.bin as
the SABR list; guard.c draws it in the weapon's slot of the hand's list while the weapon id is the saber's).

    python3 luke/saber_model.py [--sheet out.png]     the parts' counts and spans (and a shaded close drawing of the
                                                      hilt and the blade's foot, seen across AXIS from the plate's side)

Parts, all unlit (the game's vertex colours as they are):
- the hilt (the user's reference photo of a replica of Luke's second saber), eight-sided along AXIS, bottom to top:
  a faceted silver pommel a little wider than the body with a thin wire D-ring hung off its side, the silver lower body
  with the control box (a raised gold plate with dark stripes on one face, a green and a red dot on the next face), a
  black band, the black grip with seven silver ribs (a zigzag profile: the faces looking up the blade silver, the
  ones looking down black), a bronze collar, the silver emitter (a neck flaring into a crown with a lip). Its sides
  are shaded by a fixed light so it does not read flat; kept under 400 triangles (HILT_TRIS);
- the core: a thin six-sided prism from the emitter out to a round end (a hemisphere: DOME), pure white (CORE);
- the light round it: four six-sided shells (SHELLS), each wider and fainter than the one inside, green from light to
  deep, on the game's translucent texture type (2: G_RM_XLU_SURF; its combine takes the alpha from the texel alone, so
  guard_asset.py makes one texture per shell, of the shell's alpha).
The hilt is the hand's mesh (kind 'opaque'). The shells and the core are a second mesh (kinds ('glow', alpha) and
'core'), drawn by saber.c in the game's late subtree, after the level (a translucent part blends over what is already
drawn and writes no depth: in the hand it was drawn before the walls, which then covered it): the shells outer to
inner, then the core, opaque, over them, so the middle stays white.
Every part is wound counter-clockwise seen from outside (the game culls back faces).

The hand frame (palace.st, Dash's blaster in it): its barrel runs along -x from x -1.9 to -7.8, its grip along +y
(x -2.76 .. -1.19, y -0.96 .. 1.61, z -0.4 .. 0.32): the fist closes round the grip's axis. The hilt takes the grip's
place (centre GRIP, the fist on the ribs), the blade comes out of the fist's thumb side, along AXIS (from -y, the
barrel's side of the grip, turned up the forearm: the idle pose's hand hangs, and the blade should read held up).
"""
import math, sys
import numpy as np

SIDES = 6                                # the blade's prisms
HSIDES = 8                               # the hilt's
GRIP = np.array([-1.97, 0.3, -0.04])     # the fist's centre on the grip axis (the blaster grip's box centre)
AXIS = np.array([0.80, -0.45, -0.40])    # the blade's direction in the hand frame: out of the thumb side (-y), turned
                                         # up the forearm (+x) so that standing, the arm down, it points up and a
                                         # little forward (palace.st still: hand x up, y left-back, z back-right)
HILT_BACK = 2.2                          # the pommel this far behind GRIP (against AXIS)
HILT_FRONT = 3.3                         # the emitter this far ahead of GRIP
HILT_R = 0.55                            # the body's radius (to the octagon's corners)
HILT_TRIS = 400                          # the hilt's triangle budget
PLATE_ANG = 0.0                          # the control plate's face (angle round AXIS from u, a multiple of 45 degrees)
BLADE = 16.0                             # the blade's length from the emitter (local units; the forearm is 5.9):
                                         # about 51% of his height, as the films' (18 read too long: 57%, the user,
                                         # 2026-11-15)
CORE_R = 0.40
TIP = 0.9                                # the core's round end reaches this far past BLADE; every blade mesh ends
                                         # in a hemisphere round one centre, TIP - CORE_R past BLADE (parts)
DOME = (30, 60)                          # the round end's rings (degrees up from its equator), then its point
CORE = (1.0, 1.0, 1.0, 1.0)
SHELLS = [(1.9, 0x30, (0.05, 0.70, 0.12)),   # (radius, alpha 0..255: its texture's, colour), outer to inner:
          (1.4, 0x48, (0.20, 0.90, 0.25)),   # each wider and fainter than the one inside, green from light to deep
          (1.0, 0x70, (0.45, 1.00, 0.45)),
          (0.7, 0xA0, (0.75, 1.00, 0.75))]
SILVER = (0.80, 0.82, 0.86)
BLACK = (0.10, 0.10, 0.11)
BRONZE = (0.62, 0.47, 0.24)
GOLD = (0.92, 0.72, 0.28)
STRIPE = (0.18, 0.14, 0.08)
RED, GREEN = (0.95, 0.12, 0.10), (0.15, 0.95, 0.30)
LIGHT = np.array([0.3, 0.5, 0.8])        # the hilt's fixed shading light (hand frame)

# The hilt's profile along AXIS (distance from GRIP, radius); each segment takes the colour given with its upper ring.
_RIB0, _RIB1, _RIBS = -0.62, 1.30, 7
PROFILE = ([(-HILT_BACK, 0.62, None),                  # the pommel's foot (capped)
            (-1.85, 0.68, SILVER),                     # its facets, a little wider than the body
            (-1.60, HILT_R, SILVER),                   # its chamfer in
            (-0.80, HILT_R, SILVER),                   # the lower body (the control box on it)
            (_RIB0, 0.48, BLACK)]                      # the black band, down into the grip
           + [p for i in range(_RIBS) for p in (
               (_RIB0 + (_RIB1 - _RIB0) * (2 * i + 1) / (2 * _RIBS), 0.60, SILVER),    # a rib's face looking up
               (_RIB0 + (_RIB1 - _RIB0) * (2 * i + 2) / (2 * _RIBS), 0.48, BLACK))]    # and its back
           + [(1.85, 0.62, BRONZE),                    # the bronze collar
              (2.00, 0.42, SILVER),                    # in to the emitter's neck
              (3.00, 0.80, SILVER),                    # the crown flaring out
              (HILT_FRONT, 0.80, SILVER)])             # its lip (capped)
PLATE = (-1.45, -0.88, 0.14, 7)          # the control plate: from, to (along AXIS), raised by, stripes (odd: gold ends)
DOTS = [(-1.05, GREEN), (-1.25, RED)]    # on the face after the plate's, DOT_H off it
DOT_H = 0.10                             # (the image's vertices are whole 1/8 local units: a lift under ~0.1 rounds away)
DRING = (-1.35, -2.05, 0.38, 0.30, 0.08)  # the D-ring: apex at, foot at (along AXIS), out from the body, half width, wire


def frame():
    """(a, u, v): AXIS and two unit vectors across it."""
    a = AXIS / np.linalg.norm(AXIS)
    u = np.cross(a, [0.0, 0.0, 1.0]) if abs(a[2]) < 0.9 else np.cross(a, [1.0, 0.0, 0.0])
    u /= np.linalg.norm(u)
    return a, u, np.cross(a, u)


class Mesh:
    """Positions, colours, triangles; every face gets vertices of its own (flat shading per face)."""
    def __init__(self):
        self.pos, self.col, self.tri = [], [], []

    def face(self, pts, c, out):
        """A convex polygon of colour c, wound so that its normal points along out."""
        ids = []
        for p in pts:
            self.pos.append(np.asarray(p, float)); self.col.append(c); ids.append(len(self.pos) - 1)
        for i in range(1, len(ids) - 1):
            t3 = (ids[0], ids[i], ids[i + 1])
            e1, e2 = self.pos[t3[1]] - self.pos[t3[0]], self.pos[t3[2]] - self.pos[t3[0]]
            self.tri.append(t3 if np.cross(e1, e2) @ out > 0 else (t3[0], t3[2], t3[1]))

    def arrays(self):
        return np.array(self.pos), np.array(self.col), np.array(self.tri)


def ring_pt(d, r, k, sides, off=0.0):
    a, u, v = frame()
    t = 2 * math.pi * k / sides + off
    return GRIP + a * d + r * (math.cos(t) * u + math.sin(t) * v)


def lathe(m, rings, sides, col_of, off=0.0, cap_start=True, cap_end=True, point=None, dome=None):
    """A sides-sided tube through rings [(d, r, segment colour)] into m: each segment between two rings outward,
    capped at the start, and at the end by a flat cap, a point at distance `point`, or (dome=(c, r)) a hemisphere of
    radius r centred at distance c: rings at c + r sin(t) of radius r cos(t) for t in DOME, closed by the point at
    c + r. col_of(colour, normal, d)."""
    a, _, _ = frame()
    if dome is not None:
        c, r = dome; col = rings[-1][2]
        rings = list(rings) + [(c + r * math.sin(math.radians(t)), r * math.cos(math.radians(t)), col) for t in DOME]
        point = c + r
    for (d0, r0, _), (d1, r1, c) in zip(rings, rings[1:]):
        for k in range(sides):
            q = [ring_pt(d0, r0, k, sides, off), ring_pt(d0, r0, k + 1, sides, off),
                 ring_pt(d1, r1, k + 1, sides, off), ring_pt(d1, r1, k, sides, off)]
            n = np.cross(q[1] - q[0], q[3] - q[0]); n /= np.linalg.norm(n)
            if (sum(q) / 4 - (GRIP + a * ((d0 + d1) / 2))) @ n < 0: n = -n
            m.face(q, col_of(c, n, (d0 + d1) / 2), n)
    d0, r0, _ = rings[0]
    if cap_start:
        m.face([ring_pt(d0, r0, k, sides, off) for k in range(sides)], col_of(rings[1][2], -a, d0), -a)
    d1, r1, c = rings[-1]
    if point is not None:
        tip = GRIP + a * point
        for k in range(sides):
            q = [ring_pt(d1, r1, k, sides, off), ring_pt(d1, r1, k + 1, sides, off), tip]
            n = np.cross(q[1] - q[0], q[2] - q[0]); n /= np.linalg.norm(n)
            if (sum(q) / 3 - (GRIP + a * d1)) @ n < 0: n = -n
            m.face(q, col_of(c, n, point), n)
    elif cap_end:
        m.face([ring_pt(d1, r1, k, sides, off) for k in range(sides)], col_of(c, a, d1), a)


def shade(c, n):
    L = LIGHT / np.linalg.norm(LIGHT)
    k = 0.5 + 0.55 * max(0.0, float(n @ L))
    return (min(1.0, c[0] * k), min(1.0, c[1] * k), min(1.0, c[2] * k), 1.0)


def hilt():
    a, u, v = frame()
    m = Mesh()
    off = math.pi / HSIDES                              # faces centred on 0, 45, 90 .. degrees from u
    lathe(m, PROFILE, HSIDES, lambda c, n, d: shade(c, n), off)
    apo = HILT_R * math.cos(math.pi / HSIDES)           # the body face's distance from the axis
    half = HILT_R * math.sin(math.pi / HSIDES) * 0.92   # and a little under its half width

    def on_face(ang, d, s, h):                          # a point on the body face at angle ang: along, across, out
        n = math.cos(ang) * u + math.sin(ang) * v
        w = -math.sin(ang) * u + math.cos(ang) * v
        return GRIP + a * d + n * (apo + h) + w * s, n

    d0, d1, h, ns = PLATE                               # the control plate: its top in stripes, three sides (its foot,
                                                        # left out for the budget)
    for i in range(ns):
        da, db = d0 + (d1 - d0) * i / ns, d0 + (d1 - d0) * (i + 1) / ns
        q = [on_face(PLATE_ANG, da, -half, h)[0], on_face(PLATE_ANG, da, half, h)[0],
             on_face(PLATE_ANG, db, half, h)[0], on_face(PLATE_ANG, db, -half, h)[0]]
        n = on_face(PLATE_ANG, 0, 0, 0)[1]
        m.face(q, shade(GOLD if i % 2 == 0 else STRIPE, n), n)
    for (pa, pb) in (((d0, -half), (d1, -half)), ((d1, -half), (d1, half)), ((d1, half), (d0, half))):
        q = [on_face(PLATE_ANG, pa[0], pa[1], 0)[0], on_face(PLATE_ANG, pb[0], pb[1], 0)[0],
             on_face(PLATE_ANG, pb[0], pb[1], h)[0], on_face(PLATE_ANG, pa[0], pa[1], h)[0]]
        c = sum(q) / 4
        mid = on_face(PLATE_ANG, (d0 + d1) / 2, 0, h / 2)[0]
        n = c - mid; n -= (n @ on_face(PLATE_ANG, 0, 0, 0)[1]) * on_face(PLATE_ANG, 0, 0, 0)[1]; n /= np.linalg.norm(n)
        m.face(q, shade(GOLD, n), n)
    ang = PLATE_ANG + 2 * math.pi / HSIDES               # the dots on the next face
    for d, c in DOTS:
        s = 0.07
        q = [on_face(ang, d - s, -s, DOT_H)[0], on_face(ang, d - s, s, DOT_H)[0],
             on_face(ang, d + s, s, DOT_H)[0], on_face(ang, d + s, -s, DOT_H)[0]]
        m.face(q, c + (1.0,), on_face(ang, d, 0, 0)[1])
    da, df, out, hw, wire = DRING                       # the D-ring: a wire triangle off the face before the plate's,
    ang = PLATE_ANG - 2 * math.pi / HSIDES               # three flat ribbons seen from both sides
    apex = on_face(ang, da, 0, 0)[0]
    fl, fr = on_face(ang, df, -hw, out)[0], on_face(ang, df, hw, out)[0]
    nrm = np.cross(fl - apex, fr - apex); nrm /= np.linalg.norm(nrm)
    for p0, p1 in ((apex, fl), (fl, fr), (fr, apex)):
        e = (p1 - p0) / np.linalg.norm(p1 - p0); s = np.cross(nrm, e) * wire
        q = [p0 - s, p1 - s, p1 + s, p0 + s]
        for side in (nrm, -nrm):
            m.face(q, shade(SILVER, side), side)
    return m.arrays()


def parts():
    """[(kind, positions (N, 3), colours (N, 4), triangles (M, 3))], kind 'opaque' (the hilt: the hand's mesh), then
    ('glow', alpha 0..255) per shell outer to inner and 'core' (the late mesh, in that order)."""
    e = HILT_FRONT
    C = e + BLADE + TIP - CORE_R                       # the round ends' centre: the core's end stays at BLADE + TIP
    core = Mesh()
    lathe(core, [(e, CORE_R, CORE), (C, CORE_R, CORE)], SIDES, lambda c, n, d: CORE, cap_start=False,
          dome=(C, CORE_R))
    out = [('opaque', *hilt())]
    for r, alpha, c in SHELLS:
        sh = Mesh()
        col = c + (alpha / 255,)
        lathe(sh, [(e, min(0.7, r), col), (e + 0.5 * r, r, col), (C, r, col)], SIDES, lambda c, n, d: col,
              dome=(C, r))
        out.append((('glow', alpha), *sh.arrays()))
    out.append(('core', *core.arrays()))
    return out


def tip_point():
    """The blade's tip and its middle (hand frame, local units): saber.c's hit point is the middle."""
    a, _, _ = frame()
    return GRIP + a * (HILT_FRONT + BLADE + TIP), GRIP + a * (HILT_FRONT + BLADE / 2)


def sheet(out, scale=110):
    """A shaded close drawing (painter's order, the shells blended): the hilt and the blade's foot, seen across AXIS
    from the plate's side, the blade up."""
    from PIL import Image, ImageDraw
    a, u, v = frame()
    view = math.cos(PLATE_ANG + 0.5) * u + math.sin(PLATE_ANG + 0.5) * v    # towards the eye (a little off the plate)
    side = np.cross(a, view)
    W, H = 520, 1000
    im = Image.new('RGBA', (W, H), (24, 24, 32, 255))
    tris = []
    for kind, p, c, t in parts():
        for t3 in t:
            q = p[list(t3)]
            n = np.cross(q[1] - q[0], q[2] - q[0])
            if n @ view <= 0: continue                  # the game culls back faces
            tris.append((float((q.mean(0) - GRIP) @ view), kind, q, c[t3[0]]))
    order = {('glow', s[1]): 1 + i for i, s in enumerate(SHELLS)}     # the hilt far to near, each shell, the core
    order['opaque'], order['core'] = 0, len(SHELLS) + 1
    tris.sort(key=lambda x: (order[x[1]], x[0]))
    f = lambda q: (W / 2 + float((q - GRIP) @ side) * scale, H - 60 - float((q - GRIP) @ a + HILT_BACK) * scale)
    for _, kind, q, c in tris:
        layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon([f(x) for x in q], fill=tuple(int(255 * x) for x in c[:3])
                                      + (kind[1] if kind[0] == 'glow' else 255,))
        im = Image.alpha_composite(im, layer)
    im.convert('RGB').save(out)
    print('wrote', out)


if __name__ == '__main__':
    ps = parts()
    for kind, p, c, t in ps:
        print(f'{str(kind):12s} {len(p):4d} vertices {len(t):4d} triangles, span {np.round(p.min(0), 2)} .. {np.round(p.max(0), 2)}')
    assert len(ps[0][3]) <= HILT_TRIS, f'hilt {len(ps[0][3])} triangles past {HILT_TRIS}'
    print('tip, middle', [np.round(x, 2) for x in tip_point()])
    if '--sheet' in sys.argv:
        sheet(sys.argv[sys.argv.index('--sheet') + 1])
