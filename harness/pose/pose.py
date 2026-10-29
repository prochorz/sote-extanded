"""Pose tool: Dash's skeleton from a RAM dump, inverse kinematics for an arm, stick-figure drawing."""
import json, numpy as np
from scipy.optimize import least_squares
from PIL import Image, ImageDraw
from skel import *
from ram import Ram
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
DUMP = os.environ.get('DUMP', os.path.join(paths.GAME, 'hang.bin'))         # RAM dump made by dump_hang.py while he hangs
PL = int(os.environ.get('PLAYER', '0x801a7b50'), 16)   # dump_hang.py prints it
r = Ram(DUMP); BLK = r.u32(PL + 0x1A0)            # the current animation: our "hang"
SK = Skel(DUMP, BLK)
def find_block(tag):
    b = r.u32(PL + 0x19C)
    while b:
        if r.tag(b + 0x1C) == tag: return b
        b = r.u32(b + 0x14)
def read_pose(dump, block, frame_idx=None):
    rr = Ram(dump); P = {}
    for i in range(19):
        e = block + 0x38 + 0xA0 * i; row = []
        for o in SLOTS:
            p = rr.u32(e + o)
            if 0x80000000 <= p < 0x80800000: row.append(rr.f(p + 4 * frame_idx) if frame_idx is not None else rr.f(e + 0x10 + 4 * SLOTS.index(o)))
            else: row.append(None)
        P[i] = row
    return P
HANG = read_pose(DUMP, BLK, 0)
def copy(P): return {i: list(v) for i, v in P.items()}
def solve_arm(P, side, target, elbow_dir, w_reg=0.02):
    """Move shoulder+forearm(+hand z) so the hand node reaches target; elbow pushed toward elbow_dir."""
    sh, fo, ha = (5, 4, 3) if side == 'l' else (8, 7, 6)
    x0 = np.array(P[sh][:3] + P[fo][:3])
    def f(x):
        Q = copy(P); Q[sh][:3] = list(x[:3]); Q[fo][:3] = list(x[3:6])
        W = SK.world(Q)
        e = pos(W, ha) - target
        el = pos(W, fo) - pos(W, sh); el /= np.linalg.norm(el) + 1e-9
        return np.concatenate([e, 8 * (el - elbow_dir) , w_reg * (x - x0)])
    x = least_squares(f, x0).x
    Q = copy(P); Q[sh][:3] = list(x[:3]); Q[fo][:3] = list(x[3:6])
    return Q
def draw(P, path, title=''):
    W = SK.world(P); img = Image.new('RGB', (520, 300), 'white'); d = ImageDraw.Draw(img)
    for view, ox in ((0, 130), (1, 390)):     # 0: from behind (x, z), 1: side (y, z), wall at -y
        def pt(i):
            p = pos(W, i); h = p[0] if view == 0 else p[1]
            return (ox + h * 1.8, 150 - p[2] * 1.8)
        for c, par in PARENT.items():
            if par == 18: continue
            col = 'red' if c in (3,4,5) else 'blue' if c in (6,7,8) else 'green' if c in (11,12,13) else 'orange' if c in (14,15,16) else 'black'
            d.line([pt(par), pt(c)], fill=col, width=3)
        hx, hy = pt(1); d.ellipse([hx-5, hy-5, hx+5, hy+5], outline='black')
    d.line([(390 - 30*1.8, 0), (390 - 30*1.8, 300)], fill='gray')
    d.text((5, 5), title, fill='black'); d.text((300, 5), 'side: wall at left', fill='gray')
    img.save(path)
def hands(P): W = SK.world(P); return pos(W, 3), pos(W, 6)
