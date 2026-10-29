"""One-handed hang: on the left hand only, the body hanging under it, the right arm down; two
sway extremes (blended in the game), a catch reaching with the left hand, and the right hand
going up to the rim before the climb. Prints the tables for src/hang.c (hang1_keys, catch_keys).

    python3 onehand.py [out.png]
"""
from pose import *
from gen_keys import table
import sys
U = 16.0                                     # model units per world unit
B = copy(HANG); B[3][0] = 55.0; B[6][0] = -55.0      # hang_pose: hands bent over the rim
L0, R0 = hands(B)                            # the left hand stays here (on the rim)
SH_L, FO_L, HA_L, SH_R, FO_R, HA_R = 5, 4, 3, 8, 7, 6
def nrm(v): v = np.array(v, float); return v / np.linalg.norm(v)
def wrap(d): return (np.asarray(d) + 180.0) % 360.0 - 180.0
def solve_arm2(P, side, target, elbow_dir, ref=None, tries=24):
    """solve_arm from several starting angles. Of the fits that reach the target, the one
    nearest the reference angles wins (ref, default P), unwrapped onto them, so blends
    between poses made this way don't swing an arm round the long way."""
    from scipy.optimize import least_squares
    sh, fo, ha = (5, 4, 3) if side == 'l' else (8, 7, 6)
    ref = P if ref is None else ref
    xr = np.array(ref[sh][:3] + ref[fo][:3])
    rng = np.random.default_rng(1)
    def f(x, Q0):
        Q = copy(Q0); Q[sh][:3] = list(x[:3]); Q[fo][:3] = list(x[3:6]); W = SK.world(Q)
        el = pos(W, fo) - pos(W, sh); el /= np.linalg.norm(el) + 1e-9
        return np.concatenate([pos(W, ha) - target, 4 * (el - elbow_dir), 0.01 * wrap(x - xr)])
    fits = []
    for i in range(tries):
        x0 = xr.copy() if i == 0 else xr + rng.uniform(-90, 90, 6)
        r = least_squares(f, x0, args=(P,))
        x = xr + wrap(r.x - xr)
        Q = copy(P); Q[sh][:3] = list(x[:3]); Q[fo][:3] = list(x[3:6])
        err = np.linalg.norm(pos(SK.world(Q), ha) - target)
        fits.append((err > 0.05 * U, np.abs(wrap(x - xr)).sum(), err, Q))
    fits.sort(key=lambda t: (t[0], t[1] if not t[0] else t[2]))
    return fits[0][3]
def arm_len(P, side):
    sh, fo, ha = (5, 4, 3) if side == 'l' else (8, 7, 6)
    W = SK.world(P)
    return np.linalg.norm(pos(W, fo) - pos(W, sh)) + np.linalg.norm(pos(W, ha) - pos(W, fo))

def one_hand(roll, yaw, drop=None):
    """Hips and legs straight down, the spine and chest leaning away from the hand (the hips
    hang under it), the body turned side-on (yaw) so the left shoulder is nearer the wall; the
    left arm straight up to the rim. drop (model units, + = body lower): solved when None so the
    arm is 0.97 of its full length. Returns pose, drop."""
    P = copy(B)
    P[17][0] += yaw
    P[10][2] = (P[10][2] or 0) + roll * 0.6
    P[9][2] = (P[9][2] or 0) + roll * 0.4
    W = SK.world(P); s = pos(W, SH_L)
    tx, ty = pos(W, 17)[0] + 0.15 * U, L0[1]
    if drop is None:
        reach = arm_len(B, 'l') * 0.97
        dz = np.sqrt(max(reach ** 2 - (tx - s[0]) ** 2 - (ty - s[1]) ** 2, 0))
        drop = s[2] + dz - L0[2]
    for _ in range(8):                       # lower the body until the hand reaches the rim
        t = np.array([tx, ty, L0[2] + drop])
        Q = solve_arm2(P, 'l', t, nrm(nrm(t - s) + [0.12, 0.05, 0]))
        err = L0[2] + drop - pos(SK.world(Q), HA_L)[2]
        if abs(err) < 0.01 * U: break
        drop -= err
    P = Q
    W = SK.world(P); s = pos(W, SH_R)
    P = solve_arm2(P, 'r', s + np.array([-0.2, -0.1, -1.9]) * U, nrm([-0.1, 0.3, -1.0]))
    P[HA_R][0] = 0.0
    P[16][1] -= 15; P[15][0] += 22           # one knee a little bent
    return P, drop

HANG1A, DROP = one_hand(-12.0, -22.0)
HANG1B, DROP_B = one_hand(-9.0, -30.0)

def reach_mid():
    """Climb start, half way: the body turning square, the right hand coming up beside the head."""
    P = copy(HANG1A)
    for b in (1, 2, 9, 10, 11, 12, 13, 14, 15, 16, 17):
        P[b] = [None if x is None else x + (y - x) * 0.5 for x, y in zip(HANG1A[b], B[b])]
    W = SK.world(P); s = pos(W, SH_R)
    P = solve_arm2(P, 'r', s + np.array([-0.5, -0.7, 1.2]) * U, nrm([-0.6, -0.4, 0.5]), ref=HANG1A)
    _, _, ha = 5, 4, 3
    t = L0 + [0, 0, DROP * 0.5]
    P = solve_arm2(P, 'l', t, nrm(nrm(t - pos(SK.world(P), SH_L)) + [0.12, 0.05, 0]), ref=HANG1A)
    return P

def make_reach1():
    """Falling, the left hand reaching for the rim, the right arm thrown out."""
    P = copy(HANG1A)
    P[10][1] = (P[10][1] or 0) - 8
    P[16][1] -= 30; P[15][0] += 45; P[13][1] -= 20; P[12][0] -= 35
    P = solve_arm(P, 'l', L0 + [2, -8, -9], nrm([0.8, -0.2, 0.55]))
    W = SK.world(P); s = pos(W, SH_R)
    P = solve_arm(P, 'r', s + np.array([-1.6, -0.3, 0.6]) * U, nrm([-1.0, 0.0, 0.2]))
    return P
def make_grab1():
    """Hand on the rim, arm straight, legs swinging out, the right arm still out."""
    P = copy(HANG1A)
    P[16][1] += 25; P[15][0] += 15; P[13][1] += 20; P[12][0] -= 12
    W = SK.world(P); s = pos(W, SH_R)
    P = solve_arm(P, 'r', s + np.array([-1.3, -0.2, -1.0]) * U, nrm([-1.0, 0.0, -0.3]))
    return P
def make_swing1():
    P = copy(HANG1A)
    P[10][1] = (P[10][1] or 0) + 4
    P[16][1] -= 15; P[15][0] += 20; P[13][1] -= 10; P[12][0] -= 20
    return P

def check(P, name):
    W = SK.world(P); h = pos(W, HA_L) - [0, 0, DROP]
    print(f"{name}: left hand {np.round(h / U, 2)} (rim {np.round(L0 / U, 2)}, body drop {DROP / U:.2f}),"
          f" right hand {np.round(pos(W, HA_R) / U, 2)}, hips {np.round(pos(W, 17) / U, 2)}")

def draw3(poses, path):
    imgs = []
    for P, t in poses:
        draw(P, '/tmp/_p.png', t); imgs.append(Image.open('/tmp/_p.png').copy())
    out = Image.new('RGB', (520, 300 * len(imgs)), 'white')
    for i, im in enumerate(imgs): out.paste(im, (0, 300 * i))
    out.save(path)

def blend_check(a, b, name):
    """Largest distance of a joint at the middle of a linear angle blend from the average of
    its end positions (world units): big = the blend swings round the long way."""
    Wa, Wb = SK.world(a), SK.world(b)
    m = {i: [None if (x is None) else x + (y - x) * 0.5 for x, y in zip(a[i], b[i])] for i in a}
    Wm = SK.world(m)
    worst = max(np.linalg.norm(pos(Wm, i) - (pos(Wa, i) + pos(Wb, i)) / 2) for i in range(18))
    print(f'blend {name}: {worst / U:.2f}')

if __name__ == '__main__':
    for P, n in ((HANG1A, 'sway A'), (HANG1B, 'sway B')): check(P, n)
    print(f'drops (world units, + = lower): A {DROP / U:.3f} B {DROP_B / U:.3f}')
    r, g, w, m = make_reach1(), make_grab1(), make_swing1(), reach_mid()
    for a, b, n in ((r, g, 'reach-grab'), (g, w, 'grab-swing'), (w, HANG1A, 'swing-A'), (HANG1A, HANG1B, 'A-B'),
                    (HANG1A, m, 'A-mid'), (m, B, 'mid-two hands')): blend_check(a, b, n)
    print('/* hang1_keys */'); print(table([HANG1A, HANG1B, m], ['one hand (sway A)', 'one hand (sway B)', 'climb start: the right hand coming up']))
    print('/* catch_keys */'); print(table([r, g, w], ['reaching for the rim with the left hand, the right arm out', 'grabbed it: arm straight, legs swing out', 'swinging back toward the wall']))
    draw3([(HANG1A, 'one hand A'), (HANG1B, 'one hand B'), (m, 'climb: right hand coming up'), (r, 'catch: reach'), (g, 'catch: grab')],
          sys.argv[1] if len(sys.argv) > 1 else 'onehand.png')
