"""The whole Gall Run on one map, top down, from the built image (local/game/gall_run.bin): the rock (the
collision mesh, both stages and Slave I's pad, shaded by height), the route (stage 1 blue, stage 2 orange), the end
scene at Slave I's pad (the Falcon's and Slave I's ways), the chase on the rail up into space (purple), the story's
nodes on it, the Star Destroyer, the battle and the free flight round it. Labels in English.

    harness/.venv/bin/python3 harness/gallrun/mission_map.py [image.bin] out.png

Nothing runs the emulator: everything comes from the image's header (gall_asset.py) and gallrun.c's #defines.
"""
import math, os, re, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(H, '..', '..')
sys.path.insert(0, os.path.dirname(H))
import paths
img_path = sys.argv[1] if len(sys.argv) > 2 else os.path.join(paths.GAME, 'gall_run.bin')
out = sys.argv[-1]
B = open(img_path, 'rb').read()
BASE = 0x80628000
u32 = lambda o: struct.unpack_from('>I', B, o)[0]
f32 = lambda o: struct.unpack_from('>f', B, o)[0]
at = lambda a: a - BASE
import glob   # (the mission's #defines live across gallrun.c, gall_*.c and gall.h)
SRC = ''.join(open(f).read() for f in sorted(glob.glob(os.path.join(ROOT, 'sote-patch', 'src', 'gall*.[ch]'))))
def define(name):
    return float(re.search(r'#define\s+%s\s+\(?(-?[\d.]+)' % name, SRC).group(1))

# --- the image's header
n_route, route = u32(16), at(u32(20))
END, SWITCH = u32(28), u32(48)
COR = at(u32(72))
N_LINES, LINES = u32(80), at(u32(84))
COLL = at(u32(108))
N_CINE, CINE = u32(128), at(u32(132))
R0, RN = u32(164), u32(168)
SD = [f32(212 + 4 * i) for i in range(4)]
MID = [f32(228 + 4 * i) for i in range(3)]
SC_DASH, SC_CLOSE, SC_SLAVE = u32(252), u32(256), u32(260)
NODE, POS = 0x54, 0x38
nodes = np.array([[f32(route + k * NODE + POS + 4 * j) for j in range(3)] for k in range(n_route)])
corr = [struct.unpack_from('>4h', B, COR + 8 * k) for k in range(END + 1)]
rail = nodes[R0:R0 + RN]
lead = nodes[n_route - 2:]                     # (the lead before node 0, gallrun.c LEAD_FROM)

# --- the rock: the collision mesh's triangles, highest per cell
nt, a_tris = u32(COLL), at(u32(COLL + 4))
T = np.array([struct.unpack_from('>12h', B, a_tris + 24 * k) for k in range(nt)], float)
tri = T[:, :9].reshape(-1, 3, 3)

# --- the end scene (cine keys, 32 floats: t, eye, look, Falcon xyz, heading, roll, Slave I xyz, heading, Dash
# xyz, heading, pose, Outrider xyz, ...)
keys = np.array([struct.unpack_from('>32f', B, CINE + 128 * k) for k in range(N_CINE)])
cine_falcon, cine_slave, cine_dash = keys[:, 7:10], keys[:, 12:15], keys[:, 16:19]

# --- extents: everything but the far rail's empty space
P = np.concatenate([nodes[:END + 1, :2], rail[:, :2], tri[:, :, :2].reshape(-1, 2), [SD[:2], MID[:2]]])
lo = P.min(0) - 900; hi = P.max(0) + 900
PX = max((hi[0] - lo[0]) / 2400, (hi[1] - lo[1]) / 3000)
W, Hh = int((hi[0] - lo[0]) / PX), int((hi[1] - lo[1]) / PX)
P2 = lambda p: ((p[0] - lo[0]) / PX, (hi[1] - p[1]) / PX)

zmap = np.full((Hh, W), np.nan)
for t in tri:                                   # (sample each triangle on a grid of its own size)
    a, b, c = t
    l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b))
    k = max(2, int(l / PX) + 1)
    i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing='ij'); m = (i + j) <= k
    u, v = (i[m] / k)[:, None], (j[m] / k)[:, None]
    p = a + (b - a) * u + (c - a) * v
    x = ((p[:, 0] - lo[0]) / PX).astype(int); y = ((hi[1] - p[:, 1]) / PX).astype(int)
    ok = (x >= 0) & (y >= 0) & (x < W) & (y < Hh)
    x, y, z = x[ok], y[ok], p[ok, 2]
    cur = zmap[y, x]
    zmap[y, x] = np.where(np.isnan(cur) | (z > cur), z, cur)
has = ~np.isnan(zmap)
zf = np.where(has, zmap, np.nanmin(zmap))
gy, gx = np.gradient(zf)
nrm = np.dstack([-gx / PX, gy / PX, np.ones_like(zf) * 0.5]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
Ld = np.array([-0.6, 0.6, 0.55]); Ld /= np.linalg.norm(Ld)
shade = np.clip(nrm @ Ld, 0, 1)
lo_z, hi_z = np.nanpercentile(zmap, 3), np.nanpercentile(zmap, 97)
zn = np.clip((zf - lo_z) / (hi_z - lo_z + 1e-6), 0, 1)
col = np.array([150, 112, 72.]) * (1 - zn[..., None]) + np.array([238, 214, 170.]) * zn[..., None]
col *= (0.45 + 0.75 * shade)[..., None]
col = np.where(has[..., None], np.clip(col, 0, 255), np.array([16, 18, 26.]))
im = Image.fromarray(col.astype(np.uint8)).convert('RGBA')
K = 2
im = im.resize((W * K, Hh * K), Image.BILINEAR)
dr = ImageDraw.Draw(im, 'RGBA')
Q = lambda p: tuple(K * v for v in P2(p))
F = lambda n: ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', n)
FR = lambda n: ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', n)

def line(pts, colr, w=6, dash=False):
    xy = [Q(p) for p in pts]
    if dash:
        for k in range(0, len(xy) - 1, 2): dr.line(xy[k:k + 2], fill=colr, width=w)
        return
    dr.line(xy, fill=(0, 0, 0, 200), width=w + 5, joint='curve')
    dr.line(xy, fill=colr, width=w, joint='curve')

def mark(p, text, colr, dx=18, dy=-14, r=12, size=22):
    x, y = Q(p)
    dr.ellipse([x - r, y - r, x + r, y + r], fill=colr, outline=(0, 0, 0, 255), width=3)
    if text:
        dr.multiline_text((x + dx, y + dy), text, font=F(size), fill=(255, 255, 255, 255), stroke_width=4,
                          stroke_fill=(0, 0, 0, 255), spacing=2)

# --- space: the Star Destroyer (a wedge, SD_L either way, its nose a point), the battle's rings, Luke's reach
h = SD[3]; c, s = math.cos(h), math.sin(h)
SD_HALF_W = float(re.search(r'^SD_HALF_W\s*=\s*([\d.]+)', open(os.path.join(ROOT, 'harness', 'gallrun', 'space.py')).read(), re.M).group(1))
SD_W, SD_L = SD_HALF_W, SD_HALF_W / 0.6 / 2                # (space.py: its half width ~0.6 of its length)
L_, Wd = SD_L * 1.07, SD_W * 1.15                          # (a little over the hull box: the hull is a touch bigger)
fwd, side = np.array([c, s]), np.array([-s, c])
ctr = np.array(SD[:2])
wedge = [ctr + fwd * L_, ctr - fwd * L_ + side * Wd, ctr - fwd * L_ - side * Wd]
dr.polygon([Q(p) for p in wedge], fill=(170, 175, 190, 255), outline=(0, 0, 0, 255), width=4)
mid = np.array(MID[:2])
for pair in range(4):
    R = define('BATTLE_R') + define('BATTLE_DR') * min(pair, 3)
    pts = [mid + fwd * (R * define('BATTLE_LONG') * math.cos(a)) + side * (R * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 60)]
    dr.line([Q(p) for p in pts], fill=(255, 90, 90, 200), width=3)
wr = define('LUKE_NEAR')
x0, y0 = Q(mid - wr); x1, y1 = Q(mid + wr)
dr.ellipse([x0, y1, x1, y0], outline=(120, 255, 160, 220), width=4)

# --- the route
s1 = nodes[:SWITCH + 1]; s2 = nodes[SWITCH:END + 1]
line(np.concatenate([lead[::-1], nodes[:1]]), (255, 255, 255, 230), 5, dash=True)
line(s1, (70, 210, 255, 255)); line(s2, (255, 150, 40, 255))
slits = [k for k in range(SWITCH) if corr[k][0] + corr[k][1] < 12]
groups = []
for k in slits:
    if groups and k - groups[-1][-1] <= 3: groups[-1].append(k)
    else: groups.append([k])
# --- the end scene and the rail
line(cine_falcon, (255, 255, 255, 255), 4)
line(cine_slave, (120, 120, 120, 255), 4)
line(rail, (190, 110, 255, 255), 6)
end_z = nodes[END, 2]
k_space = next((k for k in range(RN) if rail[k, 2] - end_z >= define('SKY_TO')), RN - 1)
k_sky = next((k for k in range(RN) if rail[k, 2] - end_z >= define('SKY_FROM')), 0)
k_end = RN - 1 - int(define('RAIL_OFF'))

# --- timing at cruise (stages 1-2 only: 300 a second, as the old map)
dist = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(nodes[:END + 1, :2], axis=0), axis=1))])
mm = lambda k: '%d:%02d' % divmod(int(dist[k] / 300), 60)
for ts in range(30, int(dist[-1] / 300), 30):
    k = int(np.searchsorted(dist, ts * 300)); x, y = Q(nodes[k])
    dr.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)
    dr.text((x + 9, y - 10), '%d:%02d' % divmod(ts, 60), font=F(18), fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

# --- the marks
mark(lead[-1], 'Opening shot\n"Here we go, boys" (held)', (255, 255, 255, 255), dx=-330, dy=-20)
mark(nodes[0], 'START: you fly the Falcon\nafter Dash\'s Outrider', (80, 230, 120, 255))
for g_ in groups:
    k = g_[len(g_) // 2]
    mark(nodes[k], 'Slit (%s): Z on edge' % mm(k), (255, 80, 80, 255), r=10, size=20)
tie_k = SWITCH - int(define('TIES_IN'))
mark(nodes[tie_k], 'TIEs come (%s), hold fire\nDash: "Nobody said anything\nabout TIEs!"' % mm(tie_k), (255, 230, 80, 255), dy=-30)
mark(nodes[SWITCH - 50], 'Dash leaves (%s)' % mm(SWITCH - 50), (255, 230, 80, 255), dy=4)
mark(nodes[SWITCH], 'STAGE 2 (%s): you are the gunner\n"Hang on, Chewie!" (held)\n1 TIE fires at a time' % mm(SWITCH), (255, 150, 40, 255), dy=4)
mark(nodes[END], 'Slave I\'s pad (%s): end scene,\n4 held lines (Lando, Dash, Leia, Leebo),\nthen Lando: "He\'s running!"' % mm(END), (230, 60, 230, 255), dx=40, dy=-150)
mark(cine_slave[-1], '', (120, 120, 120, 255), r=8)
mark(rail[0], 'STAGE 3: the chase on rails\nafter Slave I; the gunner;\nhitting Slave I: its bar\n(15%), Leia: "Don\'t shoot!";\n0%: mission failed', (190, 110, 255, 255), dx=40, dy=30)
mark(rail[k_sky], 'Sky darkens', (90, 90, 140, 255), r=9, size=20)
mark(rail[k_space], 'Space (black sky,\ncanyon gone)', (40, 40, 60, 255), r=10, size=20)
mark(rail[SC_DASH], 'Dash sees the Star Destroyer:\n"Sorry, Lando..." (held),\njumps to lightspeed', (255, 230, 80, 255), dy=-40)
mark(rail[SC_CLOSE], 'Closing in on Slave I', (190, 110, 255, 255), r=10, size=20)
mark(rail[SC_SLAVE], 'Slave I jumps to lightspeed:\n"No...! He\'s gone"', (255, 80, 80, 255), dy=-10)
mark(rail[k_end], 'Rail ends: FREE FLIGHT\n(as the space level: stick rolls/pitches,\nA thrust, Z lasers)', (120, 255, 160, 255), dy=-10)
mark(ctr, 'Star Destroyer', (170, 175, 190, 255), dx=-80, dy=-50, r=0)
mark(mid, 'Battle: X-Wings vs TIEs, bombers;\nLuke asks for the guns:\ntake down the 6 towers', (255, 90, 90, 255), dx=28, dy=40)
n_tw, a_tw = u32(304), at(u32(308))             # (gall_space.c IMG_TOWERS: count, records {node, x, y, z, yaw})
towers = [[f32(a_tw + 20 * k + 4 + 4 * j) for j in range(3)] for k in range(n_tw)]
for k, p in enumerate(towers): mark(p, '', (255, 60, 60, 255), r=9)
if towers: mark(np.mean(towers, 0), '%d gun towers: all down ->\nLando\'s line (held), the Falcon\nflies off and jumps -> last scene' % n_tw,
                (255, 60, 60, 255), dx=40, dy=-90, r=0)
n_hg, a_hg = u32(364), at(u32(368))             # (gall.h IMG_HANGARS: count, records {x, y, z, out x, out y})
for k in range(n_hg):
    hp_ = [f32(a_hg + 20 * k + 4 * j) for j in range(5)]
    mark(hp_[:2], 'Hangar: the chase TIEs come out\n19 s into the end scene', (255, 230, 80, 255), dx=-420, dy=-10, r=10, size=20)
    q0 = np.array(hp_[:2]); line([q0, q0 + np.array(hp_[3:5]) * 300], (255, 230, 80, 255), 4)

# --- legend, scale
pad = 24; bw = 760
bx = im.width - bw - pad
dr.rounded_rectangle([bx, pad, bx + bw, pad + 330], 14, fill=(10, 12, 16, 220))
dr.text((bx + 20, pad + 12), 'GALL RUN', font=F(46), fill=(255, 220, 90, 255))
dr.text((bx + 22, pad + 64), 'The whole mission, top down', font=FR(22), fill=(225, 225, 225, 255))
yy = pad + 100
for colr, txt in (((70, 210, 255, 255), 'Stage 1  Gall\'s cliffs: you fly the Falcon after Dash'),
                  ((255, 150, 40, 255), 'Stage 2  the gunner, TIEs on the tail'),
                  ((255, 255, 255, 255), 'End scene at Slave I\'s pad: the Falcon (white), Slave I (grey)'),
                  ((190, 110, 255, 255), 'Stage 3  the chase on rails up into space'),
                  ((255, 90, 90, 200), 'The battle\'s rings over the Star Destroyer; red dots: its gun towers'),
                  ((120, 255, 160, 220), 'Luke\'s reach; free flight anywhere')):
    dr.line([(bx + 22, yy + 12), (bx + 70, yy + 12)], fill=colr, width=7)
    dr.text((bx + 82, yy), txt, font=FR(21), fill=(235, 235, 235, 255)); yy += 32
dr.text((bx + 22, yy + 6), 'Times: stages 1-2 at cruise (300/s), held lines not counted', font=FR(19), fill=(190, 190, 190, 255))
sx, sy = 40, im.height - 50
Lb = 2000 / PX * K
dr.rectangle([sx, sy, sx + Lb, sy + 10], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
dr.text((sx, sy - 30), '2000 world units', font=FR(20), fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
im.convert('RGB').save(out)
print('size', im.size, 'px/unit', round(PX, 2), 'route', n_route, 'end', END, 'switch', SWITCH, 'rail', R0, RN,
      'story', SC_DASH, SC_CLOSE, SC_SLAVE, 'space at rail', k_space, 'cine keys', N_CINE)
