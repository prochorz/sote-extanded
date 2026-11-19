"""Drawn tops and soles from the render: `pair` stills of tools/video/record_guard_turntable.py (the Look, LOOK, or
Dash's own look left, Guri right, the same depth). Usage: look_tops.py <pair.json> <shots dir>   (one line per still +
a summary per look; the numbers also in <pair>_tops.json)

Mask: |still - the empty still| (the last of the take) > THR, rows 150..560, each figure's columns: its RAM vertices'
screen span (harness/model_walk.py on the still's RDRAM dump) +- PADX. Per figure the top row (first row
with >= MINPIX mask pixels) and the sole row (last such row). A row is turned into world z above the floor on the
figure's vertical line through its RAM top vertex (for the top row) or lowest vertex (the sole row): the camera
looks down, so a row's z depends on the point's depth; Dash is drawn ~2 units from his position through the game
camera's rows (eye, R, F, U from the JSON), screen y = (cy - row) / K, x = (col - 480) / K (K 450 at 960x720: the
RAM columns land on the mask's). cy: fitted per still so Guri's mask top and sole rows land on her RAM top and lowest
vertex on average (she is drawn where RAM says; the residual printed), 360 - ~3."""
import json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness'))
from model_walk import Ram, drawn

THR, MINPIX, K, CX, PADX = 60, 3, 450.0, 480.0, 25


def objs(r):
    p, out = r.u32(0x80112830), {}
    for i in range(80):
        q = r.u32(p + 4 * i)
        if not q: break
        out[r.u32(q)] = q
    return r.u32(out[0x48756D6E] + 0x10), r.u32(out[0x54726F70] + 0x10)


def rows(mask):
    ys = np.where(mask.sum(1) >= MINPIX)[0]
    return (int(ys.min()), int(ys.max())) if len(ys) else (None, None)


def screen_y(c, P):
    d = P - c['eye']; return (d @ c['U']) / (d @ c['F'])


def z_at(c, pos, sy):
    """World z on the vertical line through pos (x, y) whose screen y is sy."""
    d0 = np.array([pos[0], pos[1], 0.0]) - c['eye']
    return -(d0 @ c['U'] - sy * (d0 @ c['F'])) / (c['U'][2] - sy * c['F'][2])


def main():
    js, shots = sys.argv[1], sys.argv[2]
    log = json.load(open(js)); base = os.path.splitext(js)[0]
    img = lambda i: np.asarray(Image.open(f'{shots}/shadow_of_the_empire-{i:03d}.png').convert('RGB')).astype(int)
    bg = img(log[-1]['i']); H, W = bg.shape[:2]
    res = []
    for d in log[:-1]:
        c = {k: np.array(d[k]) for k in ('eye', 'R', 'F', 'U')}
        m = np.abs(img(d['i']) - bg).sum(2) > THR; m[:150] = 0; m[560:] = 0
        r = Ram.load(f'{base}_{d["i"]}.ram'); h, g = objs(r)
        L = drawn(r, r.u32(h + 0x24C)); G = drawn(r, r.u32(r.u32(g + 0x70) + 0x84))
        fl, k = d['floor'], K
        def cols(P):
            q = P - c['eye']; x = CX + K * (q @ c['R']) / (q @ c['F'])
            a = np.zeros(W, bool); a[max(0, int(x.min()) - PADX):int(x.max()) + PADX] = 1; return m & a
        gy = screen_y(c, G); gt, gs = rows(cols(G))
        cy = ((gt + k * gy.max()) + (gs + k * gy.min())) / 2; res_g = ((gt + k * gy.max()) - (gs + k * gy.min())) / 2
        z = lambda P, row, f: z_at(c, P[f(P[:, 2])][:2], (cy - row) / k) - fl
        lt, ls = rows(cols(L))
        ly = screen_y(c, L)
        o = dict(i=d['i'], view=d['view'], look=d['look'], k=k, cy=cy, top_rows=(lt, gt), sole_rows=(ls, gs),
                 L_top=z(L, lt, np.argmax), L_sole=z(L, ls, np.argmin), G_top=z(G, gt, np.argmax), G_sole=z(G, gs, np.argmin), cy_resid=res_g,
                 L_ram_top=L[:, 2].max() - fl, L_ram_lo=L[:, 2].min() - fl, G_ram_top=G[:, 2].max() - fl,
                 G_ram_lo=G[:, 2].min() - fl, L_ram_rows=(cy - k * ly.max(), cy - k * ly.min()))
        o['ratio'] = o['L_top'] / o['G_top']
        res.append(o)
        print(f"still {d['i']} view {d['view']:3.0f} look {d['look']}: cy {cy:.1f} (Guri resid {res_g:+.1f} px) | rows top L {lt} G {gt}, sole L {ls} G {gs}"
              f" | drawn top L {o['L_top']:.3f} G {o['G_top']:.3f} ratio {o['ratio']:.4f} | sole L {o['L_sole']:+.3f} G {o['G_sole']:+.3f}"
              f" | RAM L top {o['L_ram_top']:.3f} lo {o['L_ram_lo']:.3f} (rows {o['L_ram_rows'][0]:.1f} / {o['L_ram_rows'][1]:.1f}) G top {o['G_ram_top']:.3f} lo {o['G_ram_lo']:.3f}")
    json.dump(res, open(base + '_tops.json', 'w'), indent=1)
    for look in (1, 2, 0):
        q = [o for o in res if o['look'] == look]
        if q: print(f"SUMMARY look {look}: top ratio L/G {' '.join(f'{o['ratio']:.4f}' for o in q)}; soles {' '.join(f'{o['L_sole']:+.3f}' for o in q)}"
                    f" (views {' '.join(f'{o['view']:.0f}' for o in q)})")


main()
