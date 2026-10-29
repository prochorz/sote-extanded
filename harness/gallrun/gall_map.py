"""Gall Run level map: both stages top down in world units (the level's own geometry shaded by height), the
route (stage 1 blue, stage 2 orange, the opening shot white), events with their time along the route at
cruise (300/s), time dots every 15 s, a legend and a scale bar. Skill: .claude/skills/level-map.

    M64CPU=0 harness/.venv/bin/python3 harness/gallrun/gall_map.py <rom> <out.png>
Always with every tile the image has outlined (stage 1 yellow "x,y", stage 2 green "S2 x,y": centres in each
level's units), none hidden: an outline with no ground in it means something is wrong.
The two RAM dumps it needs (stage 1's and stage 2's sources) are cached in local/run/gall_map_ram.pkl (delete it
after a change to the states). Event markers are placed by route node in the code below (slits, pillars,
stone ring, TIEs, Dash leaving, the switch, the cutting): move them when the level's layout changes.
"""
import os, sys, pickle, math
import numpy as np
from scipy import ndimage
G = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, G); sys.path.insert(0, os.path.dirname(G))
import paths
import gall_asset as A
import stage2_route as T
from stage1_geom import Geom, X0, Y0, STEP
from PIL import Image, ImageDraw, ImageFont

CACHE = os.path.join(paths.RUN, 'gall_map_ram.pkl')
if not os.path.exists(CACHE):
    pickle.dump(A.dump_ram(sys.argv[1], ['src_stage1.st', 'src_stage2.st']), open(CACHE, 'wb'))
E1, E2 = pickle.load(open(CACHE, 'rb'))

import layout
r1, r2 = pickle.load(open(A.ROUTE1, 'rb')), pickle.load(open(A.ROUTE2, 'rb'))
r1, END1, TAIL = layout.route(r1, A.STAGE1_END)      # stage 1's tiles rearranged, as gall_asset does
s1, s2 = r1['nodes'][:END1], r2['nodes']
(c, s, t), s2w = A.place(s1, s2, min(r1['bottom'][END1 - 6:END1 + 5]), r2['ground'], r2['anchor'])
ORIG = r1['orig']
new_of = lambda o: [k for k, i in enumerate(ORIG) if i == o]   # where an original route node now is
path = np.array(s1 + s2w[1:])
nsw = len(s1)
cor = r1['corridor'][:END1] + r2['corridor'][1:]
groove = [i for i, q in enumerate(cor) if i >= nsw and q[0] + q[1] < 12]
slit = next(i for i, q in enumerate(cor) if q[0] + q[1] < 12)
end = len(path) - 4

# stage 1 heights (level units, x 6 = world), the canyon's tiles only
g = Geom(E1)
# the dead-end wall across the canyon south of the start is left out of the image (gall_asset DEAD_END)
g.tris = [tr for tr in g.tris if not (tr[3] == 0x801A7A10 and max(abs(v[1] - tr[4][0][1]) for v in tr[4]) < 0.05
                                     and abs(tr[4][0][0] - 1700) < 50 and abs(tr[4][0][1] + 300) < 60)]
H1, L1, C1 = g.maps()
H1 = np.where(H1 > -1e8, H1, np.nan)
# stage 2 heights (its level units x 6 * STAGE2, turned and moved by place())
tiles2 = T.terrain_tiles(E2)
L2, H2, C2, x02, y02 = T.heightmap(E2, tiles2, r2['sink'])
H2 = np.where(H2 > -1e8, H2, np.nan)
S1, S2 = A.SCALE, A.SCALE * T.STAGE2
SZ1, SZ2 = A.SCALE_Z, A.SCALE_Z * T.STAGE2

PX = 9.0                                   # world units a pixel
pts = [path[:, :2]]
xs = np.arange(H1.shape[0]) * STEP + X0; ys = np.arange(H1.shape[1]) * STEP + Y0
pts.append(np.array([[xs[0] * S1, ys[0] * S1], [xs[-1] * S1, ys[-1] * S1]]))
corners = np.array([[x02, y02], [x02 + H2.shape[0] * T.STEP, y02 + H2.shape[1] * T.STEP]])
for a in corners[:, 0]:
    for b in corners[:, 1]:
        p = np.array([a, b]) * S2
        pts.append(np.array([[c * p[0] - s * p[1] + t[0], s * p[0] + c * p[1] + t[1]]]))
# the opening shot's flight in, before node 0 (along the lead)
d0 = path[0, :2] - path[1, :2]; d0 /= np.linalg.norm(d0)
intro_from = path[0, :2] + d0 * A.INTRO_V * A.INTRO_END * 0.95
pts.append(intro_from[None])
P = np.concatenate(pts)
lo = P.min(0) - 300; hi = P.max(0) + 300
# crop to the route's neighbourhood (the stages' tiles reach far beyond it)
lo = np.maximum(lo, path[:, :2].min(0) - 900); hi = np.minimum(hi, path[:, :2].max(0) + 900)
lo = np.minimum(lo, intro_from - 400); hi = np.maximum(hi, intro_from + 400)
W, Hh = int((hi[0] - lo[0]) / PX), int((hi[1] - lo[1]) / PX)
gx, gy = np.meshgrid(lo[0] + (np.arange(W) + .5) * PX, hi[1] - (np.arange(Hh) + .5) * PX)

def sample(Hm, x0, y0, step, wx, wy):
    i = ((wx - x0) / step).astype(int); j = ((wy - y0) / step).astype(int)
    ok = (i >= 0) & (j >= 0) & (i < Hm.shape[0]) & (j < Hm.shape[1])
    out = np.full(wx.shape, np.nan); out[ok] = Hm[i[ok], j[ok]]
    return out

lx1, ly1 = gx / S1, gy / S1
TMAP = layout.tile_map({(round(tt[2][0]), round(tt[2][1])) for tt in A.level_tiles(E1) if tt[2][0] >= A.X_MIN} | set(A.EXTEND1), TAIL)
tx_, ty_ = np.round(lx1 / 100) * 100, np.round(ly1 / 100) * 100   # each new tile drawn from its source
nlx, nly = np.full(lx1.shape, np.nan), np.full(ly1.shape, np.nan)
for (nx_, ny_), (ox_, oy_) in TMAP.items():
    m_ = (tx_ == nx_) & (ty_ == ny_)
    nlx[m_] = lx1[m_] - nx_ + ox_; nly[m_] = ly1[m_] - ny_ + oy_
lx1, ly1 = nlx, nly
for (ex, ey), ((sx, sy), turns) in A.EXTEND1.items():          # the canyon's copies south of the start
    inside = (np.abs(lx1 - ex) <= 50) & (np.abs(ly1 - ey) <= 50)
    ux, uy = lx1 - ex, ly1 - ey
    if turns: uy = -uy                                              # mirrored north-south
    lx1 = np.where(inside, sx + ux, lx1); ly1 = np.where(inside, sy + uy, ly1)
z1 = sample(H1, X0, Y0, STEP, lx1, ly1) * SZ1 * layout.WALL_UP
z1[gx / S1 < A.X_MIN - 50] = np.nan
# stage 2: world -> its level frame
ux, uy = gx - t[0], gy - t[1]
lx, ly = (c * ux + s * uy) / S2, (-s * ux + c * uy) / S2
z2 = sample(H2, x02, y02, T.STEP, lx, ly) * SZ2 + t[2]
# the stages are cut at the switch (gall_asset: the plane across the route at stage 1's last node)
split = path[nsw - 1, :2]
dirn = path[nsw - 1, :2] - path[nsw - 3, :2]; dirn /= np.linalg.norm(dirn)
ahead = (gx - split[0]) * dirn[0] + (gy - split[1]) * dirn[1] > 0
z1[ahead] = np.nan; z2[~ahead] = np.nan
z = np.where(ahead & ~np.isnan(z2), z2, np.where(~np.isnan(z1), z1, z2))
stage = np.where(ahead & ~np.isnan(z2), 2, np.where(~np.isnan(z1), 1, np.where(~np.isnan(z2), 2, 0)))

# hillshade
zf = np.where(np.isnan(z), np.nanmin(z), z)
zs = ndimage.gaussian_filter(zf, 1.0)
dzx = np.gradient(zs, axis=1) / PX; dzy = -np.gradient(zs, axis=0) / PX
nrm = np.dstack([-dzx, -dzy, np.ones_like(zs) * 0.6]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
L = np.array([-0.6, 0.6, 0.55]); L /= np.linalg.norm(L)
shade = np.clip((nrm @ L), 0, 1)
zn = np.clip((zs - np.nanpercentile(z, 3)) / (np.nanpercentile(z, 97) - np.nanpercentile(z, 3) + 1e-6), 0, 1)
low_c = np.array([150, 112, 72.]); high_c = np.array([238, 214, 170.])
col = low_c * (1 - zn[..., None]) + high_c * zn[..., None]
col *= (0.45 + 0.75 * shade)[..., None]
col = np.clip(col, 0, 255)
bg = np.array([22, 24, 30.])
col[np.isnan(z)] = bg
img = Image.fromarray(col.astype(np.uint8)).convert('RGBA')

# scale up for crisp lines
K = 2
img = img.resize((W * K, Hh * K), Image.BILINEAR)
dr = ImageDraw.Draw(img, 'RGBA')
def P2(p): return ((p[0] - lo[0]) / PX * K, (hi[1] - p[1]) / PX * K)
try:
    F = lambda n: ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', n)
    FR = lambda n: ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', n)
    F(10)
except Exception:
    F = FR = lambda n: ImageFont.load_default()

# intro flight in (dashed)
a, b = P2(intro_from), P2(path[0])
n = 24
for k in range(n):
    if k % 2 == 0:
        p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
        q = (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)
        dr.line([p, q], fill=(255, 255, 255, 230), width=5)
# route: stage 1 cyan, stage 2 orange, outlined
xy1 = [P2(p) for p in path[:nsw + 1]]; xy2 = [P2(p) for p in path[nsw:end + 1]]
for xy, colr in ((xy1, (70, 210, 255, 255)), (xy2, (255, 150, 40, 255))):
    dr.line(xy, fill=(0, 0, 0, 200), width=11, joint='curve')
    dr.line(xy, fill=colr, width=6, joint='curve')
# time marks every 15 s (world speed 300/s along the route)
seg = np.linalg.norm(np.diff(path[:end + 1, :2], axis=0), axis=1)
dist = np.concatenate([[0], np.cumsum(seg)])
total = dist[-1] / A.INTRO_V
slits = [i for i, q in enumerate(cor[:nsw]) if q[0] + q[1] < 12]; slit2 = next(i for i in slits if i > slit + 20)
ev = [0, new_of(33)[0], slit, slit2, *sum((new_of(o) for o in (252, 382, 564)), []), nsw - 90, nsw - 50, nsw, end]
for ts in range(15, int(total), 15):
    i = int(np.searchsorted(dist, ts * A.INTRO_V))
    if any(abs(dist[i] - dist[j]) < 4 * A.INTRO_V for j in ev): continue
    x, y = P2(path[i])
    dr.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)
    lab = f'{ts // 60}:{ts % 60:02d}'
    dr.text((x + 10, y - 9), lab, font=F(20), fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

def marker(i_or_p, text, colr, dx=16, dy=-14, r=13):
    p = path[i_or_p] if isinstance(i_or_p, (int, np.integer)) else np.array(i_or_p)
    x, y = P2(p)
    dr.ellipse([x - r, y - r, x + r, y + r], fill=colr, outline=(0, 0, 0, 255), width=3)
    dr.multiline_text((x + dx, y + dy), text, font=F(24), fill=(255, 255, 255, 255), stroke_width=4,
                      stroke_fill=(0, 0, 0, 255), spacing=2)
t_of = lambda i: dist[i] / A.INTRO_V
mm = lambda sec: f'{int(sec) // 60}:{int(sec) % 60:02d}'
marker(intro_from, f'Opening shot\n({A.INTRO_END:g} s, fades in)', (255, 255, 255, 255), dx=-230, dy=-30)
marker(0, 'START\n"Here we go, boys"', (80, 230, 120, 255))
marker(new_of(33)[0], 'Stone ring', (255, 80, 80, 255), dx=18, dy=-14)
for i_ in (slit, slit2):
    marker(i_, f'Slit ({mm(t_of(i_))}): Z on edge\nthrough it, or over\nthe wall; Dash: "Tight\nsqueeze" if you\nfollow him in', (255, 80, 80, 255))
for o_ in (252, 382, 564):
    for i_ in new_of(o_):
        marker(i_, 'Pillar: pass\neither side', (120, 200, 255, 255), dx=18, dy=-14, r=10)
marker(nsw - 90, f'TIEs come ({mm(t_of(nsw - 90))})\nDash: "Nobody said\nanything about TIEs!"', (255, 230, 80, 255), dx=18, dy=-30)
for i in (groove[0], groove[-1]):
    pass
xyg = [P2(p) for p in path[groove[0]:groove[-1] + 1]]
dr.line(xyg, fill=(255, 60, 60, 255), width=6)
marker(groove[len(groove) // 2], f'The cutting\n(on edge, {mm(t_of(groove[0]))}-{mm(t_of(groove[-1]))})', (255, 80, 80, 255), dx=-20, dy=22)
marker(nsw - 50, f'Dash leaves ({mm(t_of(nsw - 50))})\n"Sorry! I was paid to guide"', (255, 230, 80, 255), dx=18, dy=-40)
marker(nsw, f'STAGE 2 ({mm(t_of(nsw))})\nLando flies, Chewie\non the guns, TIEs', (255, 150, 40, 255), dx=18, dy=4)
marker(end, f'FINISH ({mm(total)})', (230, 60, 230, 255))
gate = np.array(A.GATES[0][:2] if hasattr(A, 'GATES') else (1699, -105), float)

# title and legend
pad = 24
bx = img.width - 600 - pad
box = [bx, pad, bx + 600, pad + 280]
dr.rounded_rectangle(box, 14, fill=(10, 12, 16, 215))
dr.text((bx + 20, pad + 14), 'GALL RUN', font=F(46), fill=(255, 220, 90, 255))
dr.text((bx + 22, pad + 66), 'Bonus mission map, top down', font=FR(22), fill=(225, 225, 225, 255))
yy = pad + 104
for colr, txt in (((70, 210, 255, 255), "Stage 1  the canyon run: you fly the Falcon after Dash"),
                  ((255, 150, 40, 255), 'Stage 2  the gunner: the player shoots'),
                  ((255, 255, 255, 230), 'Opening shot: Outrider + Falcon fly in')):
    dr.line([(bx + 22, yy + 12), (bx + 70, yy + 12)], fill=colr, width=7)
    dr.text((bx + 82, yy), txt, font=FR(21), fill=(235, 235, 235, 255)); yy += 34
dr.text((bx + 22, yy + 4), f'Line: the route (stage 1: Dash\'s; you fly freely, the rock is solid)', font=FR(19), fill=(190, 190, 190, 255)); yy += 28
dr.text((bx + 22, yy + 4), f'Route {dist[-1] / 1000:.1f}k world units at 300/s = {mm(total)}   |   dots: every 15 s',
        font=FR(19), fill=(190, 190, 190, 255))
# north arrow + scale bar
sx = 40; sy = img.height - 50
L1000 = 1000 / PX * K
dr.rectangle([sx, sy, sx + L1000, sy + 10], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
dr.text((sx, sy - 30), '1000 world units', font=FR(20), fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
if True:                                              # every tile the image has (always: the map is drawn with its tiles) (gall_asset.py writes the list):
    import json                                       # none hidden, a tile with no ground under it is a bug
    TL = json.load(open(A.TILES_OUT))
    def outline(corners, lab, colr):
        xy = [P2(q) for q in corners]
        dr.polygon(xy, outline=colr, width=2)
        tl_ = min(xy, key=lambda q: q[0] + q[1])
        dr.text((tl_[0] + 6, tl_[1] + 4), lab, font=FR(18), fill=colr, stroke_width=3, stroke_fill=(0, 0, 0, 255))
    for cx, cy in TL['stage1']:                        # stage 1 (stage 1's source's units, x6)
        outline([((cx + u) * S1, (cy + v) * S1) for u, v in ((-50, 50), (50, 50), (50, -50), (-50, -50))], f'{cx:g},{cy:g}', (255, 255, 0, 255))
    for cx, cy, kx, ky in TL['stage2']:                # stage 2 (its source level's, x6x1.5, turned and moved)
        hx, hy = 50 * kx, 50 * ky
        cs_ = [((cx + u) * S2, (cy + v) * S2) for u, v in ((-hx, hy), (hx, hy), (hx, -hy), (-hx, -hy))]
        outline([(c * q[0] - s * q[1] + t[0], s * q[0] + c * q[1] + t[1]) for q in cs_], f'S2 {cx:g},{cy:g}', (120, 255, 200, 255))
if os.environ.get('OVERLAY'):                         # stage 2 points (its level units) to check, e.g. a drawn line
    import json
    for lx_, ly_ in json.load(open(os.environ['OVERLAY'])):
        q = (lx_ * S2, ly_ * S2); x_, y_ = P2((c * q[0] - s * q[1] + t[0], s * q[0] + c * q[1] + t[1]))
        dr.ellipse([x_ - 4, y_ - 4, x_ + 4, y_ + 4], fill=(255, 40, 40, 255))
img.convert('RGB').save(sys.argv[2])
print('size', img.size, 'total s', round(total, 1), 'nsw', nsw, 'slit', slit, 'end', end)
