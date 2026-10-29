"""Climb keyframes (pull up, mantle, crouch), built from the hang pose."""
from pose import *
L0, R0 = hands(HANG)
def add(P, b, k, d): P[b][k] = (P[b][k] or 0.0) + d
def nrm(v): v = np.array(v, float); return v / np.linalg.norm(v)
def make_p1():
    P = copy(HANG)
    add(P, 10, 1, 5)
    add(P, 16, 1, -15); add(P, 15, 0, 20); add(P, 13, 1, -10); add(P, 12, 0, -15)
    P = solve_arm(P, 'l', L0 - [0, 0, 30], nrm([0.85, 0.1, -0.5]))
    P = solve_arm(P, 'r', R0 - [0, 0, 30], nrm([-0.85, 0.1, -0.5]))
    return P
def make_p2():
    P = copy(HANG)
    add(P, 10, 1, 25); add(P, 9, 1, 10)
    add(P, 16, 1, -95); add(P, 15, 0, 100); add(P, 13, 1, -20); add(P, 12, 0, -30)
    P = solve_arm(P, 'l', L0 + [0, 0, -62], nrm([0.6, 0.3, -0.75]))
    P = solve_arm(P, 'r', R0 + [0, 0, -62], nrm([-0.6, 0.3, -0.75]))
    return P
def make_p3():
    C = read_pose(DUMP, find_block('crou'), 8)
    P = copy(C)
    for b in (3,4,5,6,7,8): P[b] = list(HANG[b])
    W = SK.world(P)
    k1, k2 = pos(W, 15), pos(W, 12)        # knees: hands rest on them
    P = solve_arm(P, 'l', k1 + [0, -4, 6], nrm([0.7, 0.4, -0.6]))
    P = solve_arm(P, 'r', k2 + [0, -4, 6], nrm([-0.7, 0.4, -0.6]))
    return P

# ---- The catch: reaching for the rim, grabbing it (legs swing out), swinging back ----
def make_reach():
    P = copy(HANG)
    add(P, 10, 1, -8)                                   # leaning back a little, falling
    add(P, 16, 1, -30); add(P, 15, 0, 45); add(P, 13, 1, -20); add(P, 12, 0, -35)
    P = solve_arm(P, 'l', L0 + [2, -8, -9], nrm([0.8, -0.2, 0.55]))
    P = solve_arm(P, 'r', R0 + [-2, -8, -9], nrm([-0.8, -0.2, 0.55]))
    return P
def make_grab():
    P = copy(HANG)
    add(P, 16, 1, 25); add(P, 15, 0, 15); add(P, 13, 1, 20); add(P, 12, 0, -12)
    return P
def make_swing():
    P = copy(HANG)
    add(P, 10, 1, 4)
    add(P, 16, 1, -15); add(P, 15, 0, 20); add(P, 13, 1, -10); add(P, 12, 0, -20)
    return P
