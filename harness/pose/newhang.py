"""Hang pose with the hands over the rim: wrists just outside the lip, forearms leaning on the
face, hands bent over the top. Prints the arm rows for hang_pose (src/hang.c) and draws it.

    python3 newhang.py [out.png]
HANG_OUT (body to lip, world units) and the rim height (6.4 above the feet) as in src/hang.c.
"""
from pose import *
import sys
U = 16.0                                   # model units per world unit (hang pose, scale 2.91 included)
OUT = 1.55; RIM_Z = pos(SK.world(HANG), 11)[2] + 6.4 * U
WRIST_Y = -(OUT - 0.08) * U                # wall at -y
def nrm(v): v = np.array(v, float); return v / np.linalg.norm(v)
def finger(W, h): return pos(W, h, local=SK.t[h] * 0.45) - pos(W, h)
def make():
    P = copy(HANG)
    L0, R0 = hands(HANG)
    P = solve_arm(P, 'l', np.array([L0[0] + 1.5, WRIST_Y, RIM_Z - 0.5]), nrm([0.55, 0.6, -0.58]))
    P = solve_arm(P, 'r', np.array([R0[0] - 1.5, WRIST_Y, RIM_Z - 0.5]), nrm([-0.55, 0.6, -0.58]))
    # bend the hands over the rim: fingers toward the wall, ~50 degrees off vertical
    best = None
    for a in np.arange(-90, 91, 1.0):
        Q = copy(P); Q[3][0] = a; f = finger(SK.world(Q), 3)
        ang = np.degrees(np.arctan2(-f[1], f[2]))
        if best is None or abs(ang - 50) < abs(best[1] - 50): best = (a, ang)
    P[3][0] = best[0]; P[6][0] = -best[0]
    return P
if __name__ == '__main__':
    P = make(); W = SK.world(P)
    for i in (5, 4, 3, 8, 7, 6): print(NAMES[i], np.round(pos(W, i) / U, 2), 'angles', [None if v is None else round(v, 1) for v in P[i][:3]])
    print('rim z', round(RIM_Z / U, 2), 'lip y', -OUT, 'fingertips', np.round((pos(W, 3) + finger(W, 3)) / U, 2), np.round((pos(W, 6) + finger(W, 6)) / U, 2))
    for i in (3, 4, 5, 6, 7, 8): print(f"    {', '.join(str(round(v * 100)) for v in P[i] if v is not None)},  /* {i} {NAMES[i]} (pose_t: x 100) */")
    draw(P, sys.argv[1] if len(sys.argv) > 1 else 'newhang.png', 'hands over the rim')
