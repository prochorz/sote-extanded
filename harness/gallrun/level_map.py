"""Any level's geometry, top down (world units, shaded by height), from a savestate.

    M64CPU=0 SURFACE=<top|floor|thick> harness/.venv/bin/python3 harness/gallrun/level_map.py <rom> <state> <out.png>

<state> is a name in local/states (e.g. gall_tp5.st, echo_atst.st, sew_428.st, xiz_glad.st,
om.st, sky.st). The level's meshes are found by walking the world tree from 0x8013CE24, carrying
the accumulated transform (rotation x translation) of the transform nodes above each mesh; every
triangle is then in world units. Each triangle is rasterised top down and shaded by height, like
the Gall Run map (hillshade + height ramp). SURFACE picks what to shade: top = the highest surface
(gall_map.py's H map: roofs and rock, good for outdoor canyons; the default), floor = the lowest
surface (the walkable floor, good for interiors and multi-floor levels), thick = the open height
(top - floor: rooms read as open space, walls and rock as tall). A level with no terrain (a space
battle) comes out nearly empty: correct, there is no ground to draw there.
"""
import os, sys, struct, ctypes
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont

G = os.path.dirname(os.path.abspath(__file__))
H = os.path.dirname(G)
sys.path.insert(0, G); sys.path.insert(0, H)
import paths
from m64 import Emu, HERE
from collide import tri_ids          # (collide has the copy: stage1_geom imports gall_asset, a cycle)

WORLD_ROOT = 0x8013CE24


def dump_ram(rom, state):
    """One state's RDRAM as big-endian bytes (as gall_asset.dump_ram)."""
    out = []
    e = Emu(rom)

    def script(e, n):
        if n < 60:
            return
        if n == 60:
            e.load_state(os.path.join(paths.STATES, state))
        if n == 70:
            raw = ctypes.string_at(e.rdram(), 0x800000)
            out.append(b''.join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4)))
            e.stop()
    e.run(script)
    return out[0]


def valid(a):
    return 0x80000000 <= a < 0x80800000


def meshes_of(E):
    """[(mesh, R, t)]: every mesh node (kind 3) under the world root, with the accumulated world
    transform (world = R @ v + t) of the transform nodes (kind 0xD) above it."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    F = lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]
    root = R(WORLD_ROOT)
    out, seen = [], set()
    if not valid(root):
        return out
    I = np.eye(3, dtype=np.float64)

    def walk(node, Rm, t, depth):
        if depth > 16 or not valid(node):
            return
        w0 = R(node)
        kind = w0 >> 28
        if kind == 3:                                # a mesh: every parent is a separate placement,
            out.append((node, Rm, t))                # so it is NOT deduplicated (tiles share meshes)
            return
        if kind == 0xD:                              # transform node: rotation (9 floats, +0x14)
            m = np.array([F(node + 0x14 + 4 * j) for j in range(9)], np.float64).reshape(3, 3)
            tn = np.array([F(node + 0x38 + 4 * j) for j in range(3)], np.float64)
            # the rows are the local axes in the parent (x' = x*m0 + y*m3 + z*m6: gallrun.c show_stage,
            # mesh_image.build_tiles): v_parent = m.T @ v + tn (m itself turned every rotation the wrong way)
            Rm, t = Rm @ m.T, Rm @ tn + t
        elif kind != 5:
            return
        if node in seen:                             # group/transform visited once (breaks cycles)
            return
        seen.add(node)
        n, lst = R(node + 0xC), R(node + 0x10)
        if not (0 < n < 512 and valid(lst)):
            return
        for i in range(n):
            walk(R(lst + 4 * i), Rm, t, depth + 1)
    walk(root, I, np.zeros(3), 0)
    return out


def mesh_tris(E, placed):
    """Triangles of the placed meshes, vertices moved into world units."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    tris = []
    for m, Rm, t in placed:
        lst = R(m + 0x10)
        for i in range(R(m + 0xC)):
            p = R(lst + 4 * i)
            if not R(p + 0x24):                       # no material: a collision-only face the game
                continue                              # does not draw (mesh_image.py untextured)
            a, buf, n = R(p + 0x28), {}, 0
            while R(a) >> 24 != 0xB8 and n < 5000:
                w0, w1 = R(a), R(a + 4)
                if w0 >> 24 == 0x04:
                    cnt, v0 = (w0 & 0xFFFF) >> 9, ((w0 >> 16) & 0xFF) // 2
                    for j in range(cnt):
                        x, y, z = struct.unpack_from('>hhh', E, (w1 + 16 * j) & 0x7FFFFF)
                        v = Rm @ np.array([x / 8, y / 8, z / 8]) + t
                        buf[v0 + j] = (v[0], v[1], v[2])
                else:
                    for ids in tri_ids(w0, w1):
                        vs = [buf.get(k) for k in ids]
                        if all(v is not None for v in vs):
                            tris.append(vs)
                a += 8; n += 1
    return tris


def build_map(rom, state, out):
    E = dump_ram(rom, state)
    placed = meshes_of(E)
    if not placed:
        sys.exit(f'no meshes under the world root {WORLD_ROOT:#x} (state {state})')
    tris = mesh_tris(E, placed)
    print(f'{state}: {len(placed)} meshes, {len(tris)} triangles')
    if not tris:
        sys.exit('no triangles (a space level, or the state is not a level with geometry)')

    P = np.array([v for t in tris for v in t], np.float32)
    lo, hi = P[:, :2].min(0), P[:, :2].max(0)
    PX = max(hi - lo) / 500.0                        # coarser, like gall_map.py: smooths thin walls
    lo = lo - 80; hi = hi + 80
    W = max(1, int((hi[0] - lo[0]) / PX)); Hh = max(1, int((hi[1] - lo[1]) / PX))

    Zlo = np.full((Hh, W), 1e9, np.float32)           # (y, x) rows/cols, lowest surface per cell (the floor)
    Zhi = np.full((Hh, W), -1e9, np.float32)          # highest surface per cell (the top)
    for t in tris:
        a, b, c = (np.array(v, np.float32) for v in t)
        l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b))
        n = max(2, int(l / PX) + 1)
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij')
        mm = (i + j) <= n
        u = (i[mm] / n)[:, None]; v = (j[mm] / n)[:, None]
        p = a + (b - a) * u + (c - a) * v
        ix = ((p[:, 0] - lo[0]) / PX).astype(int); iy = ((p[:, 1] - lo[1]) / PX).astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < W) & (iy < Hh)
        if ok.any():
            np.minimum.at(Zlo, (iy[ok], ix[ok]), p[ok, 2])
            np.maximum.at(Zhi, (iy[ok], ix[ok]), p[ok, 2])

    surf = os.environ.get('SURFACE', 'top')           # top: roofs/rock (gall_map.py's H); floor: the
    if surf == 'floor':                               # walkable floor; thick: open height (top - floor)
        z = Zlo
    elif surf == 'thick':
        z = Zhi - Zlo
    else:
        z = Zhi
    zf = np.where((Zlo < 1e8) & (Zhi > -1e8), z, np.nan)
    if not np.isfinite(zf).any():
        sys.exit('no geometry landed in the image bounds')
    zs = ndimage.gaussian_filter(np.where(np.isnan(zf), np.nanmin(zf), zf), 1.0)
    dzx = np.gradient(zs, axis=1) / PX; dzy = -np.gradient(zs, axis=0) / PX
    nrm = np.dstack([-dzx, -dzy, np.ones_like(zs) * 0.6]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    L = np.array([-0.6, 0.6, 0.55]); L /= np.linalg.norm(L)
    shade = np.clip((nrm @ L), 0, 1)
    zlo, zhi = np.nanpercentile(zf, 3), np.nanpercentile(zf, 97)
    zn = np.clip((zs - zlo) / (zhi - zlo + 1e-6), 0, 1)
    low_c = np.array([150, 112, 72.]); high_c = np.array([238, 214, 170.])
    col = low_c * (1 - zn[..., None]) + high_c * zn[..., None]
    col *= (0.45 + 0.75 * shade)[..., None]
    col = np.clip(col, 0, 255)
    bg = np.array([22, 24, 30.])
    col[np.isnan(zf)] = bg
    img = Image.fromarray(col.astype(np.uint8)).convert('RGBA')

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

    name = os.path.splitext(os.path.basename(state))[0].upper()
    box = [img.width - 460, 24, img.width - 24, 24 + 96]
    dr.rounded_rectangle(box, 14, fill=(10, 12, 16, 215))
    dr.text((box[0] + 18, box[1] + 12), name, font=F(40), fill=(255, 220, 90, 255))
    dr.text((box[0] + 20, box[1] + 58), f'{surf} surface, top down', font=FR(20), fill=(225, 225, 225, 255))

    sx = 40; sy = img.height - 50                       # scale bar
    step = 1000.0
    while step / PX * K < 80:
        step *= 2
    dr.rectangle([sx, sy, sx + step / PX * K, sy + 10], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    dr.text((sx, sy - 30), f'{step:g} world units', font=FR(20), fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

    img.convert('RGB').save(out)
    print('size', img.size, 'meshes', len(placed), 'tris', len(tris), 'PX', round(PX, 2), 'lo', lo.round(1).tolist(), 'hi', hi.round(1).tolist(), 'K', K)


if __name__ == '__main__':
    build_map(sys.argv[1], sys.argv[2], sys.argv[3])
