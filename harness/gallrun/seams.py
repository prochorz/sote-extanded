"""Stage 1's tile seams checked (harness tool): along every edge two drawn tiles share, the height of the top of
the rock just either side (from the image's stage 1 triangles, world units); a stretch where they differ by more
than JUMP shows a crack in a wall or a step (the user saw sky through a wall at a seam, 2026-10-09).

    ../.venv/bin/python3 gallrun/seams.py        (reads local/game/gall_run.bin, local/run/gall_tiles.json)
"""
import json, os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import paths
import collide
BASE, CELL, OFF, JUMP = 0x80628000, 3.0, 4.0, 40.0


def tops():
    img = open(os.path.join(paths.GAME, 'gall_run.bin'), 'rb').read()
    R = lambda a: struct.unpack_from('>I', img, a - BASE)[0]
    T, N = collide.world(collide.extract(img, BASE, R(BASE + 4), R(BASE + 8)), 6, 9)
    x0, y0 = T[:, :, 0].min(), T[:, :, 1].min()
    nx, ny = int((T[:, :, 0].max() - x0) / CELL) + 2, int((T[:, :, 1].max() - y0) / CELL) + 2
    top = np.full((nx, ny), np.nan)
    for a, b, c in T:
        l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)); n = max(2, int(l / (CELL / 2)) + 1)
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij'); m = (i + j) <= n
        u, v = (i[m] / n)[:, None], (j[m] / n)[:, None]; p = a + (b - a) * u + (c - a) * v
        ix, iy = ((p[:, 0] - x0) / CELL).astype(int), ((p[:, 1] - y0) / CELL).astype(int)
        cur = top[ix, iy]; top[ix, iy] = np.where(np.isnan(cur), p[:, 2], np.maximum(cur, p[:, 2]))
    return top, x0, y0


if __name__ == '__main__':
    top, x0, y0 = tops()
    at = lambda x, y: top[int((x - x0) / CELL), int((y - y0) / CELL)] if 0 <= int((x - x0) / CELL) < top.shape[0] and 0 <= int((y - y0) / CELL) < top.shape[1] else np.nan
    tiles = {tuple(int(v) for v in t[:2]) for t in json.load(open(os.path.join(paths.RUN, 'gall_tiles.json')))['stage1']}
    for (cx, cy) in sorted(tiles):
        for dx, dy in ((100, 0), (0, 100)):
            if (cx + dx, cy + dy) not in tiles: continue
            bad = []
            for s in np.arange(-48, 48, 1.0):                 # along the edge (level units)
                if dx: ex, ey, ax = (cx + 50) * 6, (cy + s) * 6, (OFF, 0)
                else: ex, ey, ax = (cx + s) * 6, (cy + 50) * 6, (0, OFF)
                a, b = at(ex - ax[0], ey - ax[1]), at(ex + ax[0], ey + ax[1])
                if np.isnan(a) or np.isnan(b) or abs(a - b) > JUMP: bad.append(s)
            if len(bad) > 4:
                print(f'seam {cx},{cy} | {cx + dx},{cy + dy}: {len(bad)} of 96 units off ({min(bad):.0f}..{max(bad):.0f})')
