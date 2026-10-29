"""A level's floors by height, one top-down panel per band (multi-level places such as Gall's ledges).

    M64CPU=0 harness/.venv/bin/python3 harness/gallrun/level_layers.py <rom> <state> <out.png> [band edges...]

Walkable floors are the drawn faces turned up (normal z > 0.6, level_map.py's triangles in world units). Each
panel fills the floors whose middle lies in its band (shaded by height within it); the walls (steep faces)
that reach into the band are drawn dark; the rest of the level is a pale outline for orientation. The
default bands are for Gall (gall_tp5.st, sub-level 14). MARK="name:x,y,z;..." puts markers on the map: filled
in the panel whose band holds z, a ring in the others.
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
G = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, G); sys.path.insert(0, os.path.dirname(G))
import level_map as L

BANDS = [-1e9, 0, 190, 262, 350, 500, 1e9]


def main():
    rom, state, out = sys.argv[1:4]
    edges = [float(x) for x in sys.argv[4:]] or BANDS
    E = L.dump_ram(rom, state)
    T = np.array(L.mesh_tris(E, L.meshes_of(E)), np.float64)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); l = np.linalg.norm(n, axis=1)
    T, n = T[l > 1e-6], n[l > 1e-6] / l[l > 1e-6, None]
    up, steep = n[:, 2] > 0.6, np.abs(n[:, 2]) < 0.5
    zm = T[:, :, 2].mean(1); zlo, zhi = T[:, :, 2].min(1), T[:, :, 2].max(1)
    lo, hi = T[:, :, :2].reshape(-1, 2).min(0) - 60, T[:, :, :2].reshape(-1, 2).max(0) + 60
    W = 820; sc = W / (hi[0] - lo[0]); H = int((hi[1] - lo[1]) * sc)
    P = lambda p: ((p[0] - lo[0]) * sc, (hi[1] - p[1]) * sc + 70)
    try:
        F = lambda s: ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', s)
        FR = lambda s: ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', s)
    except Exception:
        F = FR = lambda s: ImageFont.load_default()
    panels = []
    order = np.argsort(zm)                             # low first: higher floors drawn over lower
    L_ = np.array([-0.5, 0.6, 0.62]); L_ /= np.linalg.norm(L_)
    for b0, b1 in zip(edges[:-1], edges[1:]):
        im = Image.new('RGB', (W, H + 70), (22, 24, 30)); d = ImageDraw.Draw(im)
        for k in order:                                 # the level as a pale outline
            if up[k]: d.polygon([P(v) for v in T[k]], fill=(48, 52, 62))
        sel = [k for k in order if up[k] and b0 <= zm[k] < b1]
        if sel:
            za, zb = np.percentile(zm[sel], 2), np.percentile(zm[sel], 98)
        for k in sel:
            t = 0 if zb - za < 1 else np.clip((zm[k] - za) / (zb - za), 0, 1)
            c = np.array([150, 112, 72.]) * (1 - t) + np.array([245, 222, 175.]) * t
            c = np.clip(c * (0.6 + 0.5 * max(0.0, float(n[k] @ L_))), 0, 255)
            d.polygon([P(v) for v in T[k]], fill=tuple(int(x) for x in c))
        for k in np.where(steep & (zhi > max(b0, -1e8)) & (zlo < min(b1, 1e8)))[0]:   # walls in the band
            a, b = sorted(T[k], key=lambda v: v[2])[:2]
            d.line([P(a), P(b)], fill=(10, 10, 12), width=2)
        for m in filter(None, os.environ.get('MARK', '').split(';')):
            name, xyz = m.split(':'); x, y, z = (float(v) for v in xyz.split(','))
            cx, cy = P((x, y)); here = b0 <= z < b1
            d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=(230, 40, 40) if here else None, outline=(255, 90, 90), width=3)
            if here: d.text((cx + 13, cy - 11), name, font=F(20), fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
        lbl = (f'below {b1:g}' if b0 < -1e8 else f'{b0:g} and up' if b1 > 1e8 else f'{b0:g} .. {b1:g}')
        d.text((16, 14), f'Floors {lbl}', font=F(30), fill=(255, 220, 90))
        d.text((16, 48), f'{len(sel)} floor faces', font=FR(16), fill=(200, 200, 200))
        panels.append(im)
    cols = 3; rows = (len(panels) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * W + (cols - 1) * 8, rows * (H + 70) + (rows - 1) * 8 + 90), (10, 11, 14))
    ds = ImageDraw.Draw(sheet)
    ds.text((16, 16), f'{os.path.splitext(os.path.basename(state))[0].upper()} - floors by height', font=F(40), fill=(255, 255, 255))
    ds.text((16, 62), 'top down, world units; dark lines: walls in that band; grey: the rest of the level', font=FR(18), fill=(190, 190, 190))
    for i, im in enumerate(panels):
        sheet.paste(im, ((i % cols) * (W + 8), 90 + (i // cols) * (H + 78)))
    step = 500.0                                       # scale bar
    ds.rectangle([16, sheet.height - 26, 16 + step * sc, sheet.height - 18], fill=(255, 255, 255))
    ds.text((16 + step * sc + 10, sheet.height - 34), f'{step:g} world units', font=FR(18), fill=(255, 255, 255))
    sheet.save(out)
    print('panels', len(panels), 'size', sheet.size)


if __name__ == '__main__':
    main()
