"""Numbers for the stand-in pilot of tools/video/record_gallrun_take.py (harness tool, METRICS=<json> rows per game frame):

    ../.venv/bin/python3 gallrun/pilot_metrics.py run/pil/<tag>_*.met.json

Per stage: frames, health lost (the game's own loss, read before the take keeps health full) in hits (frames with a loss),
stage 1: the least distance of the ship and of the camera's eye to the drawn rock (collide.py's triangles, sampled) and the
stick's change per frame (mean / 95th percentile / max); stage 2: fighters downed, share of frames with a live fighter in view,
share of those with one within 4 degrees of the crosshair, frames firing.
"""
import json, math, sys, os
import numpy as np
from scipy import spatial
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_plan

rows = []
for f in sorted(sys.argv[1:]): rows += json.load(open(f))
T, route, sw = bot_plan.load()
pts = []
for a, b, c in T:
    l = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)); n = min(40, max(2, int(l / 12) + 1))
    i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij'); m = (i + j) <= n
    u, v = (i[m] / n)[:, None], (j[m] / n)[:, None]; pts.append(a + (b - a) * u + (c - a) * v)
tree = spatial.cKDTree(np.unique(np.round(np.concatenate(pts) / 4), axis=0) * 4.0)
print('run: first g', rows[0]['g'], 'last g', rows[-1]['g'], f"= {(rows[-1]['g'] - rows[0]['g']) / 60:.0f} s of recording")
for stage in (1, 2, 3):
    R = [r for r in rows if r['stage'] == stage]
    if not R: continue
    loss = [max(0, 0x1EF - r['hp']) if r['hp'] is not None and r['hp'] < 0x1EF + 1 else 0 for r in R]
    print(f'stage {stage}: {len(R)} frames ({len(R) / 60:.0f} s), health lost {sum(loss)}, hits {sum(1 for x in loss if x)}')
    ev = [(r['g'], r['node'], l) for r, l in zip(R, loss) if l]
    print('  loss events (g, node, loss):', ev[:12], '...' if len(ev) > 12 else '')
    if stage == 1:
        P = np.array([r['pos'] for r in R]); E = np.array([r['eye'] for r in R])
        dp, de = tree.query(P)[0], tree.query(E)[0]
        pad = np.array([r['pad'][1:] for r in R], float); d = np.abs(np.diff(pad, axis=0)).max(1)
        print(f'  ship to rock: min {dp.min():.1f}, p5 {np.percentile(dp, 5):.1f}; eye to rock: min {de.min():.1f}, p5 {np.percentile(de, 5):.1f}')
        print(f'  stick change/frame: mean {d.mean():.2f}, p95 {np.percentile(d, 95):.1f}, max {d.max():.0f}')
    if stage == 2:
        kills = sum(r['kills'] for r in R); vis = [r for r in R if r['vis'] > 0]
        on = [r for r in vis if r['near'] < math.radians(4)]; fire = sum(1 for r in R if r['pad'][0] & 64)
        print(f'  fighters downed {kills}; live fighter in view {100 * len(vis) / len(R):.0f}% of frames; within 4 deg of crosshair {100 * len(on) / len(R):.0f}%; firing {100 * fire / len(R):.0f}%')
        pad = np.array([r['pad'][1:] for r in R], float); d = np.abs(np.diff(pad, axis=0)).max(1)
        print(f'  stick change/frame: mean {d.mean():.2f}, p95 {np.percentile(d, 95):.1f}, max {d.max():.0f}')
