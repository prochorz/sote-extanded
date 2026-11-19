"""Luke's saber swings (feature saber, saber.c): seven animation blocks for Dash's skeleton, sw1 sw2 sw3 (the 3-hit combo:
two horizontal cuts and a diagonal one down from over his right shoulder to his left hip), spin, and swp1 swp2 swp3 (the
combo in place: saber.c plays one instead of its stepping row when a body stands within the step at the swing's start),
as key tracks for harness/guard_asset.py (it puts them into guard.bin as the SABR record's SWN2 table).

    python3 luke/saber_moves.py [--swing] [--sheet out.png] [--arm]   from local/game/palace.bin (a palace.st RAM
                                                       dump, pose/melee_view.py --dump): the keys' numbers;
                                                       --swing: the swings' checks, one line per move, PASS / FAIL;
                                                       --sheet: every key of the seven moves from in front and his
                                                       right side (the step drawn: his place moved by it);
                                                       --arm: the saber arm (below) on every key of its blocks
                                                       (the blade's angles, the body boxes from local/game/guard.bin)
    python3 luke/saber_moves.py --parry [--sheet out.png] [--err out.png]   the parry grid's two layers (FD, below:
                                                       PARRY_GRID_NEAR at 1.5, PARRY_GRID at 2.25), per layer one
                                                       line per node, PASS / FAIL, then the meet (the grid's blend
                                                       against the test points on its plane), then the meet's max
                                                       over both; --sheet draws the nodes, --err the meet's error
                                                       map (one file per layer, out_fd1.5.png, out_fd2.25.png)
    python3 luke/saber_moves.py --grid [--skip TAG]       the hold's right-hand place: every grid point over ARM_BLOCKS'
                                                       graded keys (fists, blade, body boxes with MARGIN), the winner
    python3 luke/saber_moves.py --grid-block TAG          one block's right-hand place over GRID_BELT: of the points that
                                                       hold on its graded keys, the grip nearest the belt (BELT)

Each block is a copy of Dash's `shoo` (saber.c copies it per level, as hang.c copies `flyy`), so its tracks are the ones
shoo has: rotations on bones 1..17, the model bone's z translation (MASK, read from the dump and checked). The body is
the hold (hold_pose: Sstn key 0 with the hold's two arms, what he stands in with the saber out): a swing's first key
(sw1, spin) and every move's last key are that pose, copied, so a swing leaves the hold and comes back to it; sw2 and
sw3 start on the key the one before rests in (CHAIN: they are only started chained). Per move a few control keys give
the right hand's place (right, forward, up of his right shoulder, model units), the blade's direction (the same axes)
and the upper body's turn (+ to his left; TURN_SPLIT over pelvis, spine and chest, the neck and head turned back by
HEAD_BACK so he keeps looking where he faces) and lean (forward, degrees, on spine and chest half each). Between control
keys a Catmull-Rom spline in key time (spline: the hand does not stop at the cut; zero tangents at a move's ends and at
the keys it rests on); at each key the arm is solved by inverse kinematics (solve_key) and the left fist put on the
hilt behind the right (left_key). In the swings both wrists are held near the hold's (WRIST_BEND, WRIST_TWIST: a wrist
bends tens of degrees and the forearm, not the wrist, rolls), so the blade's turn comes from the shoulder, the forearm
and the upper body; without it the hand took the blade's whole turn (sw1's right wrist 86 deg off the hold's, sw3's
left 57 bent and 52 twisted). The combo steps: the right foot leaves the floor, lands forward and the body comes
over it while the game moves him STEP (the step's window, root), the left foot gathers after (leg_key, the crouch on
the model bone's z). The spin holds the arm out to his right and turns the pelvis one full turn to his right (coiled
to his left first), one-handed (its left arm keeps the hold's angles, at the body), as a light hop: dips, turns the full
circle in the air, lands on his stand place (HOP_*: the model bone's z raises him, the legs solved per key). The
in-place rows (INPLACE) are the combo's rows with step 0 and no foot lift: both feet stay on their hold places, the
crouch over the step window as the stepping row's; each chained as its stepping row (CHAIN).

Model frame (Skel, the game's FK with the rest matrices): forward -y, right -x, up +z; 16 model units to a world unit
(the placement's 0.0625 scale). The model bone's z track is his height above his floor point in world units (Skel's FK
leaves it out: fk() lowers the figure by it).

The table (SWN2, guard_asset.py): 'SWN2', count, MASK (19 bytes, 1 pad), the blade's middle in the hand frame (3
floats, local units: saber.c's hit point), then per move 0x2C bytes {tag, keys, keys per second, cut (s from the start:
the hit), reach (the hit's radius, world units), damage, step (world units forward), tracks (absolute: track-major,
`keys` floats each, in MASK's order), link (s: the next move may start, moving cuts the rest short), step from, step to
(s: the window the game moves him in)}.

The arm (SAR2, guard_asset.py; saber.c arms()): his movement blocks (ARM_BLOCKS) with both arms' tracks ours, the
saber held in both hands in front of his belt, blade forward and 45 deg up, centred (ARM_HAND / ARM_HAND_AT, each block's --grid-block winner, and
ARM_BLADE in his facing's frame, solved per key; the left fist on the hilt behind the right), standing (Sstn) and
moving; GRADED: the keys --arm grades (shoo: key 1, the frame the game plays). The body leaned forward with it: every key's
spine (bone 10) turned ARM_LEAN about his right axis before the arms are solved (--arm prints the hold's lean, pelvis to
neck from the vertical, and the ARM_LEAN that makes it 12.0). The table: 'SAR2', count, per block {tag, keys, its 21
tracks (right shoulder, forearm, hand, then the left's, then the spine: z x y each, degrees)}, then 'PRY3' and the
parry grid's layers (PARRY_GRID_NEAR on FD[0] 1.5 ahead, PARRY_GRID on 2.25: NX, NY, NZ, then the first side, the side
step, the first height, the height step, the first distance, the distance step, then NZ x NY x NX poses of 21 floats in
that order, layer-major (the nearest first), each row-major by height; saber.c blends the eight nodes around a bolt's
crossing (its side, height and distance ahead, carried along his own move) and the playing block's seven bones toward
that as the bolt comes in).
"""
import math, os, struct, sys
import numpy as np
from scipy.optimize import least_squares
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'pose')); sys.path.insert(0, os.path.dirname(HERE))
import skel
from skel import Skel, pos, bone_values, chain_block, objects, rot
import saber_model

KEYS_PER_S = 30.0
BASE_KEY = 20                 # shoo: standing, the gun arm forward and down (sw2's let-go left arm)
SLOTS = (0x70, 0x74, 0x78, 0x88, 0x8C, 0x90)
R_ARM = (8, 7, 6)             # shoulder, forearm, hand
H, B = 'H', 'B'               # in a control key: the hold's hand place (ARM_HAND) and blade (ARM_BLADE)
# (tag, keys, cut key, link key, root (from, to) keys or None, reach, damage, step, control keys [(key, hand (right,
# fwd, up), blade dir (right, fwd, up), turn, lean, rest)]). cut: the hit (the blade's fastest key); link: from here
# the next move of the combo may start and moving cuts the return short; root: the keys the game moves him `step`
# over (one speed). A key marked rest gets a zero tangent (the blade settles there: the chained move starts on it).
# Cut to cut sw1 -> sw2 0.367 s, sw2 -> sw3 0.40 s, the finisher's link a beat later (0.567 s); a lone sw1 cuts at
# 0.25 s, is free again at 0.433 s and back in the hold at 0.70 s (the tempo the combo had, now with an end).
MOVES = [
    ('sw1 ', 22, 7.5, 13, (4, 9), 2.0, 170.0, 1.5, [
        (0, H, B, 0, 0, False),                                   # the hold
        (5, (4, 6, -3), (0.8, -0.3, 0.5), -40, 0, False),         # wound up at his right
        (7.5, (-12, 20, -12), (0, 1, 0.2), 5, 8, False),          # the cut, low chest: the hands in front of his middle
                                                                  # with the elbow bent (at chest height and full reach the
                                                                  # wrist limit flipped the forearm 113 deg in a key)
        (11, (-14, 22, -8), (-0.7, 0.3, 0.35), 40, 5, False),     # through to his left, the blade forward-left: pointed
                                                                  # across his body it needs the wrist bent past WRIST_BEND
        (13, (-14, 21, -8), (-0.7, 0.25, 0.4), 40, 4, True),      # rest (link)
        (21, H, B, 0, 0, False)]),                                # the hold
    ('sw2 ', 20, 5.5, 10, (1, 6), 2.0, 170.0, 1.5, [
        (3, (-14, 21, -8), (-0.8, -0.2, 0.4), 45, 0, False),      # coiled a little further (key 0: CHAIN)
        (5.5, (-8, 20, -10), (0.1, 1, 0.25), -5, 8, False),       # the cut, rising, the elbow bent (as sw1's)
        (8, (4, 12, -6), (0.6, 0.5, 0.35), -40, 5, False),        # through to his right, the blade forward-right
        (10, (4, 11, -6), (0.6, 0.45, 0.4), -40, 4, True),        # rest (link)
        (19, H, B, 0, 0, False)]),
    ('sw3 ', 21, 7.5, 17, (4, 9), 2.0, 170.0, 1.5, [
        (3, (2, 5, 10), (0.45, -0.4, 0.8), -15, -4, False),       # rising over his right shoulder (key 0: CHAIN)
        (5, (-1.5, 10, 14.75), (0.3, -0.55, 0.9), -10, -6, False),  # high over the right shoulder, the blade back over it:
                                                                  # the diagonal starts there, the chest turned right
        (7.5, (-8.5, 20.5, -2.5), (-0.25, 0.9, 0.45), 10, 12, False),  # the cut, across his front from right to left
        (10, (-9, 22.75, -13.75), (-0.7, 0.8, -0.45), 40, 9, False),  # down to his left hip, the upper body turned left
                                                                  # with it (more turn or further left brought the
                                                                  # blade into the left thigh), leaned little: no bow
        (13, (-10.5, 21, -16), (-0.3, 0.65, -0.2), 20, 11, True),  # rest: the blade forward-left and down, the tip
                                                                  # above the knee (turned back to 20: the blade off
                                                                  # the thigh)
        (16.5, (-8, 18.75, -12), (-0.4, 1.25, 0.4), 17.5, 4, False),  # the return kept off the belly and the thigh
        (20, H, B, 0, 0, False)]),
    ('spin', 24, 10.5, 17, None, 4.0, 250.0, 0.0, [
        (0, H, B, 0, 0, False),
        (2, (4, 19.5, -8.5), (0.3, 0.85, 0.4), 17.5, 2, False),   # out and forward first, the chest coiled to his left
        (4, (10, 12, -9), (0.65, 0.15, 0.45), 34.5, 1, False),    # wound up (the pelvis still), the hand low at his side
        (8, (8.5, 8.5, -10), (0.95, 0.25, 0.25), -18, 4, False),  # the arm out to his right, the chest turned after it
        (12, (11.5, 10, -7.5), (0.75, 0.65, 0), -12, 4.5, False), # the blade level through the turn
        (15, (11.5, 12.5, -6), (0.4, 0.6, 0.2), 0, 3, False),     # coming round, the upper body square again
        (17, (7, 14.5, -9.5), (0.4, 0.85, 0.25), 6, 4.5, True),   # the turn done
        (19.5, (2, 19, -11), (0.4, 0.65, 0.35), 3, 2, False),     # the settle kept off the chest
        (23, H, B, 0, 0, False)]),
]
# The in-place set (saber.c blocked(): a body within the step at a combo swing's start plays it instead of the
# stepping row, so the planted foot does not slide back while the game holds him there): each row the stepping row's
# (keys, keys/s, cut, link, reach, damage, control keys, step window) with step 0.0 and no foot lift (feet: both feet
# on their hold places, the crouch over the step window as the stepping row's). Indices 4..6 (saber.c INPL).
INPLACE = {'swp1': 'sw1 ', 'swp2': 'sw2 ', 'swp3': 'sw3 '}
MOVES += [(t,) + m[1:7] + (0.0,) + m[8:] for t, src in INPLACE.items() for m in MOVES if m[0] == src]
# A chained move's key 0 is the key the move before rests on (all its track values), so the combo flows; an in-place
# row's the same as its stepping row's (the move before may be either set: at those keys both stand gathered).
CHAIN = {'sw2 ': ('sw1 ', 13), 'sw3 ': ('sw2 ', 10)}
CHAIN.update({t: CHAIN[src] for t, src in INPLACE.items() if src in CHAIN})
# The strike, for --swing: from the wind-up control key to the follow-through one.
STRIKE = {'sw1 ': (5, 11), 'sw2 ': (3, 8), 'sw3 ': (5, 10), 'spin': (6, 16)}
STRIKE.update({t: STRIKE[src] for t, src in INPLACE.items()})
# The blade between control keys: the spline runs on its two angles about the move's pole (the angle around it,
# unwrapped along the control keys, and the angle from its equator), not on the vector: a vector spline over a half
# turn shrinks in the middle, and the blade stalled and then jumped 73 deg in one key. The pole is the axis the sweep
# goes around: up for the flat cuts and the spin, his right for the diagonal cut (with the pole up its high key
# sits on the pole). Axes (right, fwd, up): (pole, the angle's zero, its quarter turn).
POLE = {'sw3 ': ((1, 0, 0), (0, 1, 0), (0, 0, 1))}
POLE.update({t: POLE[src] for t, src in INPLACE.items() if src in POLE})
POLE_UP = ((0, 0, 1), (1, 0, 0), (0, 1, 0))
BLADE_TURN = 80.0             # deg a key at most, the blade
JOINT_STEP = 90.0             # deg a key at most, any joint (the sampler takes the short way up to 180; sw2's left
                              # forearm twists 86 in the cut's fastest key as the left hand crosses under the hilt)
OFF_PLANE = {'spin': 4.0}     # the strike's tip off its plane, rms at most (3.0 for the combo)
SPIN = (4, 17, -360.0)        # the spin's pelvis turn: from key, to key (smoothstep), degrees (+ to his left: −360, one turn to his right)
                              # (to his right: the user, 2026-11-15; a wind-up across his chest put the pommel in it)
# The spin is a hop: turned on the floor, the legs went round rigidly with the pelvis (a turntable, the user,
# 2026-11-15); the feet stay planted while the hips coil (<= 23 deg) and leave the floor only for the turn.
HOP_AIR = (6, 15)             # the spin's hop: the keys off the floor (open interval)
HOP_FEET = 10.0               # the feet's peak above the floor (model units)
HOP_TUCK = 4.0                # the knees' bend at the peak: the pelvis rises HOP_FEET - HOP_TUCK
HOP_DIP = 3.0                 # the dip before the push-off and after the landing (model units)
# The upper body's turn over the bones (each turned about the vertical after its parent): the pelvis carries some of
# it (the hips follow the cut, the planted feet stay), spine and chest the rest; the neck and the head turned back by
# half each, so his face stays on where he faces. The spin's pelvis carries its own full turn (SPIN): there the turn
# is on spine and chest half each.
TURN_SPLIT = {17: 0.3, 10: 0.35, 9: 0.35}
SPIN_SPLIT = {10: 0.5, 9: 0.5}
HEAD_BACK = {2: 0.5, 1: 0.5}
LEAN_BONES = (10, 9)          # the lean, half each
ELBOW = np.array([-0.6, 0.0, -0.8])   # the elbow pushed out to his right and down (model frame)
# The swings' wrists held near the hold's (wrist_of: bend and twist of the hand in its forearm's frame against the
# hold's): a real wrist bends tens of degrees about a neutral grip and does not twist of its own (the forearm rolls),
# so past these the solver pays WRIST_W per degree (against the blade term's 6 per unit) and the blade's turn goes to
# the shoulder, the forearm's roll and the upper body. Without it sw3's left wrist bent 57 and twisted 52 deg off the
# hold's, sw1's right bent 86 (the hand took whatever turn the blade needed).
WRIST_BEND = 35.0
WRIST_TWIST = 20.0
WRIST_W = 1.0
RIGHT, FWD, UP = np.array([-1.0, 0, 0]), np.array([0, -1.0, 0]), np.array([0, 0, 1.0])
# The legs (thigh, shin, foot). The step: STEP_UNITS model units per world unit of the move's step (1.5 -> 24); d(k)
# rises linearly over the root's keys (the game moves him at one speed). The right foot leaves one key before the root
# starts and lands two before it ends, forward of its stance place by what is left of the step (then planted while the
# body comes over it), in the air a smoothstep with an arc; the left stays planted (its place goes back by d(k) in his
# frame) and gathers to its stance place over GATHER keys after the root ends. The crouch lowers him while the feet
# are apart (a 24-unit lunge needs the pelvis 5.3 lower with the rear leg at 0.97 of its length).
# In the game his place follows d(k) within 0.05 world units on every frame of sw1's step (t_saber.py flow), so the
# planted foot reads as planted.
R_LEG, L_LEG = (13, 12, 11), (16, 15, 14)
STEP_UNITS = 16.0             # model units per world unit
CROUCH = 5.5                  # model units down while the feet are apart
FOOT_ARC = (4.0, 3.0)         # the right foot's and the left foot's arc in the air (model units up)
GATHER = 4                    # keys the left foot gathers over
REF_PULL = 0.06               # per degree: a swing's free turns pulled to the hold's angles (solve_key, leg_key);
                              # 0.03 let the leaned hold's left arm flip IK solutions in sw2 (sw3's first key stepped 105 deg)
REACH = 0.99                  # a planted leg's hip-to-ankle distance at most this share of thigh + shin, feet apart (Sstn's own: 0.998)


class BE:
    """A big-endian RAM image (guard_asset.py's) read like pose/ram.py's Ram."""
    def __init__(s, b): s.b = b
    def u32(s, a): return struct.unpack_from('>I', s.b, a & 0x7FFFFC)[0]
    def f(s, a): return struct.unpack_from('>f', s.b, a & 0x7FFFFC)[0]
    def u16(s, a): return struct.unpack_from('>H', s.b, a & 0x7FFFFE)[0]
    def tag(s, a): return struct.pack('>I', s.u32(a)).decode('latin1')


def load(r):
    """(Skel with the game's FK, shoo key BASE_KEY's pose, MASK) from a RAM reader r."""
    humn = r.u32(objects(r)['Humn'] + 0x10)
    ch = r.u32(humn + 0x19C)
    trot, shoo = chain_block(r, ch, 'trot'), chain_block(r, ch, 'shoo')
    assert all(r.u32(shoo + 0x38 + 0xA0 * i + 8) == r.u32(trot + 0x38 + 0xA0 * i + 8) for i in range(19)), 'shoo order'
    mask = bytes(sum(1 << k for k, o in enumerate(SLOTS) if 0x80000000 <= r.u32(shoo + 0x38 + 0xA0 * i + o) < 0x80800000)
                 for i in range(19))
    old = skel.Ram; skel.Ram = lambda d: d
    try: S = Skel(r, trot, rests=True)
    finally: skel.Ram = old
    return S, bone_values(r, shoo, BASE_KEY, 19), mask


def ease(u): return u * u * (3 - 2 * u)


def copy(P): return {i: list(v) for i, v in P.items()}


def hold_pose(r, S=None, lean=None):
    """The hold: Sstn key 0 with the hold's two arms and its leaned spine (arm_keys' first key: what he stands in with
    the saber out)."""
    S = load(r)[0] if S is None else S
    P = block_poses(r, 'Sstn')[0]
    ks, _ = arm_keys(S, [P], lean=lean)
    for b, i in zip(R_ARM + L_ARM + (10,), range(0, 21, 3)): P[b][:3] = list(ks[0][i:i + 3])
    return P


def crouch_of(P, hold):
    """How far (model units) the pose's model bone z puts him below the hold."""
    return (hold[18][5] - P[18][5]) * STEP_UNITS


def fk(S, P, hold):
    """S.world(P) lowered by the crouch (the model bone's z, which Skel's FK leaves out)."""
    W = S.world(P); c = crouch_of(P, hold)
    if c:
        for i in W: W[i] = W[i].copy(); W[i][3, :3] -= c * UP
    return W


def spline(ctl, k):
    """The control keys at key k: a Catmull-Rom spline in key time (the tangent at a control key = (next - previous)
    / their key distance; zero at the first, the last and the rest keys). ctl: [(key, values (array), rest)]."""
    t = [c[0] for c in ctl]; p = [np.asarray(c[1], float) for c in ctl]; n = len(ctl)
    m = [np.zeros_like(p[0]) if i in (0, n - 1) or ctl[i][2] else (p[i + 1] - p[i - 1]) / (t[i + 1] - t[i - 1])
         for i in range(n)]
    if k <= t[0]: return p[0]
    if k >= t[-1]: return p[-1]
    i = max(j for j in range(n - 1) if t[j] <= k)
    h = t[i + 1] - t[i]; u = (k - t[i]) / h
    return ((2 * u ** 3 - 3 * u ** 2 + 1) * p[i] + (u ** 3 - 2 * u ** 2 + u) * h * m[i]
            + (-2 * u ** 3 + 3 * u ** 2) * p[i + 1] + (u ** 3 - u ** 2) * h * m[i + 1])


def blade_angles(ctl, tag):
    """The control keys with the blade as its two angles about the move's pole: [(key, 7 values: hand, around, from
    the equator, turn, lean), rest]; the angle around unwrapped the short way from control key to control key."""
    pole, zero, quarter = (np.array(a, float) for a in POLE.get(tag, POLE_UP))
    out, last = [], None
    for k, v, rest in ctl:
        b = v[3:6] / np.linalg.norm(v[3:6])
        ph = math.degrees(math.atan2(b @ quarter, b @ zero)); th = math.degrees(math.asin(np.clip(b @ pole, -1, 1)))
        if last is not None: ph = last + ((ph - last + 180.0) % 360.0 - 180.0)
        last = ph
        out.append((k, np.r_[v[:3], ph, th, v[6:8]], rest))
    return out


def blade_of(tag, ph, th):
    pole, zero, quarter = (np.array(a, float) for a in POLE.get(tag, POLE_UP))
    c = math.cos(math.radians(th))
    return c * math.cos(math.radians(ph)) * zero + c * math.sin(math.radians(ph)) * quarter + math.sin(math.radians(th)) * pole


def controls(mv, moves=None):
    """A move's control keys as [(key, 8 values: hand, blade, turn, lean, rest)], H / B resolved, a chained move's
    key 0 from the key its source rests on."""
    tag, keys = mv[0], mv[8]
    res = lambda v, d: np.array(d if isinstance(v, str) else v, float)
    out = [(k, np.r_[res(h, ARM_HAND), res(b, ARM_BLADE), t, l], rest) for k, h, b, t, l, rest in keys]
    if tag in CHAIN:
        src, at = CHAIN[tag]
        sm = next(m for m in (moves or MOVES) if m[0] == src)
        c = next(c for c in controls(sm, moves) if c[0] == at)
        out = [(0, c[1], True)] + out
    return out


def axis_rot(ax, deg):
    a = np.asarray(ax, float) / np.linalg.norm(ax); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    r = math.radians(deg); return np.eye(3) + math.sin(r) * K + (1 - math.cos(r)) * K @ K


def unit3(M): return M / np.linalg.norm(M, axis=1, keepdims=True)


def world_turn(S, P, bone, R_after, x0=None):
    """The bone's three angles so that its world rotation becomes (its world rotation now) x R_after (row vectors:
    a turn about model axes after it), its parent unchanged."""
    W = S.world(P); target = unit3(W[bone][:3, :3]) @ R_after
    x0 = np.array(P[bone][:3] if x0 is None else x0, float)
    def f(x):
        Q = {i: list(v) for i, v in P.items()}; Q[bone][:3] = list(x)
        return (unit3(S.world(Q)[bone][:3, :3]) - target).ravel()
    P = {i: list(v) for i, v in P.items()}; P[bone][:3] = list(least_squares(f, x0).x)
    return P


def forearm_axis(S, fo, ha, _c={}):
    """The forearm's own axis (its node to the hand's node at the rest pose, every angle 0) in the forearm's frame."""
    k = (id(S), fo, ha)
    if k not in _c:
        W0 = S.world({i: [0.0] * 6 for i in range(19)})
        ax = (pos(W0, ha) - pos(W0, fo)) @ np.linalg.inv(unit3(W0[fo][:3, :3])); _c[k] = ax / np.linalg.norm(ax)
    return _c[k]


def hand_in_forearm(W, fo, ha):
    """The hand's rotation in its forearm's frame (row vectors: hand-local -> forearm-local)."""
    return unit3(W[ha][:3, :3]) @ np.linalg.inv(unit3(W[fo][:3, :3]))


def wrist_parts(L, L0, ax):
    """(bend, twist) deg of the hand-in-forearm rotation L against L0: Rd = inv(L0) L (in the forearm's frame);
    bend: ax against ax turned by Rd; twist: Rd's twist part about ax (swing-twist split: the quaternion's component
    along ax)."""
    Rd = np.linalg.inv(L0) @ L
    bend = math.degrees(math.acos(np.clip((ax @ Rd) @ ax, -1.0, 1.0)))
    M = Rd.T; w = math.sqrt(max(0.0, 1.0 + np.trace(M))) / 2
    v = np.array([M[2, 1] - M[1, 2], M[0, 2] - M[2, 0], M[1, 0] - M[0, 1]])
    if w > 1e-6: v = v / (4 * w)
    else:   # a half turn: the axis from the symmetric part
        e, V = np.linalg.eigh((M + M.T) / 2); v = V[:, int(np.argmax(e))]
    return bend, 2 * math.degrees(math.atan2(abs(v @ ax), abs(w)))


def wrist_of(S, P, hold, fo, ha):
    """The wrist of pose P against the hold's: (bend, twist), degrees (wrist_parts)."""
    return wrist_parts(hand_in_forearm(S.world(P), fo, ha), hand_in_forearm(S.world(hold), fo, ha), forearm_axis(S, fo, ha))


def solve_key(S, P, hand, blade, x0, arm=R_ARM, axis=None, elbow=ELBOW, at=(0.0, 0.0, 0.0), ref=None, wrist=None):
    """An arm (shoulder, forearm, hand angles; the right one by default) for the hand frame's point `at` (local
    units; the hand's node by default) at `hand` and the hilt's line (`axis` in the hand frame, AXIS by default)
    along `blade` (model). ref: 9 angles the free turns (the fist's roll about the hilt, the forearm's twist) are
    pulled to (REF_PULL; the swings: the hold's, so a swing comes back to the hold's own angles, not a twisted copy).
    wrist: the hold's hand-in-forearm rotation (hand_in_forearm); given, the wrist's bend and twist against it past
    WRIST_BEND / WRIST_TWIST cost WRIST_W per degree."""
    sh, fo, ha = arm
    fax = None if wrist is None else forearm_axis(S, fo, ha)
    a = saber_model.AXIS if axis is None else np.asarray(axis, float); a = a / np.linalg.norm(a)
    d = blade / np.linalg.norm(blade)
    def f(x):
        Q = {i: list(v) for i, v in P.items()}; Q[sh][:3], Q[fo][:3], Q[ha][:3] = list(x[:3]), list(x[3:6]), list(x[6:9])
        W = S.world(Q)
        e = (pos(W, ha, at) - hand) / 10.0
        el = pos(W, fo) - pos(W, sh); el /= np.linalg.norm(el) + 1e-9
        bd = a @ unit3(W[ha][:3, :3])
        r = [] if ref is None else [REF_PULL * ((x - ref + 180.0) % 360.0 - 180.0)]
        if wrist is not None:
            bw, tw = wrist_parts(hand_in_forearm(W, fo, ha), wrist, fax)
            r.append(WRIST_W * np.array([max(0.0, bw - WRIST_BEND), max(0.0, tw - WRIST_TWIST)]))
        return np.concatenate([e * 10, 2.0 * (el - elbow) * 0.3, 6.0 * (bd - d), 0.01 * (x - x0)] + r)
    x = least_squares(f, x0).x
    Q = {i: list(v) for i, v in P.items()}; Q[sh][:3], Q[fo][:3], Q[ha][:3] = list(x[:3]), list(x[3:6]), list(x[6:9])
    return Q, x


def leg_info(S, hold):
    """Per leg (thigh, shin, foot): the hold's ankle (model), its foot's world rotation, the thigh and shin lengths,
    the knee's side (its offset from the hip-ankle line, unit: forward of it)."""
    W = S.world(hold); out = {}
    for leg in (R_LEG, L_LEG):
        h, k, a = (pos(W, b) for b in leg); d = (a - h) / np.linalg.norm(a - h)
        off = (k - h) - ((k - h) @ d) * d
        out[leg] = dict(ankle=a, rot=unit3(W[leg[2]][:3, :3]), thigh=float(np.linalg.norm(k - h)),
                        shin=float(np.linalg.norm(a - k)), knee=off / np.linalg.norm(off))
    return out


def leg_key(S, P, leg, ankle, x0, li, ref=None, rot=None):
    """A leg (thigh, shin, foot angles) for the ankle at the model point `ankle` (Skel's frame), the foot's world
    rotation `rot` (the hold's by default), the knee forward (in the plane of the hip-ankle line and the hold's knee
    side): (pose, the 9 angles)."""
    th, sh, ft = leg
    rot = li['rot'] if rot is None else rot
    W = S.world(P); hip = pos(W, th)
    v = ankle - hip; L = np.linalg.norm(v); d = v / L
    a, b = li['thigh'], li['shin']; L = min(L, a + b - 1e-6)
    s = li['knee'] - (li['knee'] @ d) * d; s /= np.linalg.norm(s)
    ca = (a * a + L * L - b * b) / (2 * a * L); knee = hip + a * (ca * d + math.sqrt(max(0.0, 1 - ca * ca)) * s)
    def f(x):
        Q = {i: list(v) for i, v in P.items()}; Q[th][:3], Q[sh][:3], Q[ft][:3] = list(x[:3]), list(x[3:6]), list(x[6:9])
        Wq = S.world(Q)
        return np.concatenate([pos(Wq, sh) - knee, pos(Wq, ft) - ankle, 6.0 * (unit3(Wq[ft][:3, :3]) - rot).ravel(),
                               0.01 * (x - x0)] + ([] if ref is None else [REF_PULL * ((x - ref + 180.0) % 360.0 - 180.0)]))
    x = least_squares(f, x0).x
    Q = {i: list(v) for i, v in P.items()}; Q[th][:3], Q[sh][:3], Q[ft][:3] = list(x[:3]), list(x[3:6]), list(x[6:9])
    return Q, x


def feet(mv, k, li):
    """The step at key k: (crouch, {leg: (ankle place in his frame (model, the crouch not in it), planted)}).
    d(k) = STEP (k - from) / (to - from), clamped."""
    root, step = mv[4], mv[7]
    if root is None: return 0.0, None
    f0, f1 = root; st = step * STEP_UNITS
    lift = mv[0] not in INPLACE                 # the in-place rows: no foot lift, both feet planted on every key
    arc = FOOT_ARC if lift else (0.0, 0.0)
    d = lambda k: st * min(1.0, max(0.0, (k - f0) / (f1 - f0)))
    off, on, g = f0 - 1, f1 - 2, f1 + GATHER
    ra, la = li[R_LEG]['ankle'], li[L_LEG]['ankle']
    if k <= off: rp, rpl = ra.copy(), True
    elif k >= on: rp, rpl = ra + FWD * (st - d(k)), True
    else:
        t = (k - off) / (on - off); A, Bp = ra, ra + FWD * (st - d(on))
        rp, rpl = A + (Bp - A) * ease(t) + UP * arc[0] * math.sin(math.pi * t), not lift
    if k <= f1: lp, lpl = la - FWD * d(k), True
    elif k >= g: lp, lpl = la.copy(), True
    else:
        t = (k - f1) / (g - f1); A = la - FWD * st
        lp, lpl = A + (la - A) * ease(t) + UP * arc[1] * math.sin(math.pi * t), not lift
    if k <= off or k >= g: c = 0.0
    elif k < on: c = CROUCH * ease((k - off) / (on - off))
    elif k <= f1: c = CROUCH
    else: c = CROUCH * (1 - ease((k - f1) / (g - f1)))
    return c, {R_LEG: (rp, rpl), L_LEG: (lp, lpl)}


def spin_turn(k):
    """The spin's pelvis turn at key k (degrees, SPIN's sign)."""
    f0, f1, deg = SPIN
    return deg * ease(min(1.0, max(0.0, (k - f0) / (f1 - f0))))


def hop(k, li, centre):
    """The spin's hop at key k: (crouch = -p, {leg: (ankle place on the floor (model, the crouch not in it), planted,
    the foot's height f above it, the foot's world rotation)}). p: the pelvis's rise (+ up); the feet turn by psi about
    the vertical through `centre` (the pelvis's place): planted at the hold's places on the floor keys, the pelvis's
    turn in the air, eased in and out over the air window's first and last two keys."""
    a0, a1 = HOP_AIR; air = a1 - a0
    sm = lambda k, x0, x1, v0, v1: v0 + (v1 - v0) * ease(min(1.0, max(0.0, (k - x0) / (x1 - x0))))
    if a0 - 4 <= k <= a0 - 1: p = sm(k, a0 - 4, a0 - 1, 0.0, -HOP_DIP)
    elif a0 - 1 < k <= a0: p = sm(k, a0 - 1, a0, -HOP_DIP, 0.0)
    elif a0 < k < a1: p = (HOP_FEET - HOP_TUCK) * math.sin(math.pi * (k - a0) / air)
    elif a1 <= k <= a1 + 1: p = sm(k, a1, a1 + 1, 0.0, -HOP_DIP)
    elif a1 + 1 < k <= a1 + 4: p = sm(k, a1 + 1, a1 + 4, -HOP_DIP, 0.0)
    else: p = 0.0
    f = HOP_FEET * math.sin(math.pi * (k - a0) / air) if a0 < k < a1 else 0.0
    pel, end = spin_turn(k), SPIN[2]
    if k <= a0: psi = 0.0
    elif k < a0 + 2: psi = sm(k, a0, a0 + 2, 0.0, pel)
    elif k <= a1 - 2: psi = pel
    elif k < a1: psi = sm(k, a1 - 2, a1, pel, end)
    else: psi = end
    R = axis_rot(UP, psi); out = {}
    for leg in (R_LEG, L_LEG):
        place = centre + (li[leg]['ankle'] - centre) @ R
        out[leg] = (place, not (a0 < k < a1), f, li[leg]['rot'] @ R)
    return -p, out


def angles9(P, bones): return np.array(sum((list(P[b][:3]) for b in bones), []), float)


def move_keys(S, hold, shoo, mv, start=None, moves=None, li=None):
    """Every key of a move: (poses, per key info). start: the pose key 0 copies (a chained move's source key; the hold
    by default)."""
    tag, n = mv[0], mv[1]
    ctl = blade_angles(controls(mv, moves), tag); li = leg_info(S, hold) if li is None else li
    lh = left_hold(S); a = saber_model.AXIS / np.linalg.norm(saber_model.AXIS)
    tipL, midL = saber_model.tip_point()
    out, info = [], []
    prev = None
    W0 = S.world(hold)
    wr_r, wr_l = hand_in_forearm(W0, R_ARM[1], R_ARM[2]), hand_in_forearm(W0, L_ARM[1], L_ARM[2])   # the wrists' limit
    for k in range(n):
        v = spline(ctl, k); hand, blade, turn, lean = v[:3], blade_of(tag, v[3], v[4]), float(v[5]), float(v[6])
        c, fp = hop(k, li, pos(W0, 17)) if tag == 'spin' else feet(mv, k, li)
        if k == 0 or k == n - 1:
            P = copy(start if (k == 0 and start is not None) else hold)
            c = crouch_of(P, hold)
        else:
            P = copy(hold)
            if tag == 'spin':
                P = world_turn(S, P, 17, axis_rot(UP, spin_turn(k)), prev[17][:3])
                split = SPIN_SPLIT
            else: split = TURN_SPLIT
            for b, sh in split.items():
                R = axis_rot(UP, turn * sh)
                if b in LEAN_BONES: R = R @ axis_rot(RIGHT, lean / 2)   # + forward (it was -: the swings leaned back)
                P = world_turn(S, P, b, R, prev[b][:3])
            for b, sh in HEAD_BACK.items(): P = world_turn(S, P, b, axis_rot(UP, -turn * sh), prev[b][:3])
            if fp is not None:
                P[18][5] = hold[18][5] - c / STEP_UNITS
                for leg in (R_LEG, L_LEG):
                    tgt = fp[leg][0] + (c + fp[leg][2]) * UP if len(fp[leg]) > 2 else fp[leg][0] + c * UP
                    rot = fp[leg][3] if len(fp[leg]) > 2 else None
                    _, x = leg_key(S, P, leg, tgt, angles9(prev, leg), li[leg], angles9(hold, leg), rot)
                    P, _ = leg_key(S, P, leg, tgt, x, li[leg], rot=rot)
            Wt = S.world(P)
            if tag == 'spin':   # the arm's place turns with the body
                M = np.linalg.inv(unit3(W0[17][:3, :3])) @ unit3(Wt[17][:3, :3])
                hp = pos(Wt, R_ARM[0]) + frame_of(hand) @ M; bd = frame_of(blade) @ M
            else:
                hp = pos(Wt, R_ARM[0]) + frame_of(hand); bd = frame_of(blade)
            Q, x = solve_key(S, P, hp, bd, angles9(prev, R_ARM), ref=angles9(hold, R_ARM), wrist=wr_r)
            P, _ = solve_key(S, P, hp, bd, x, wrist=wr_r)   # then exact from there (the free turns stay near the hold's)
            if tag == 'spin':   # one-handed: the left arm keeps the hold's angles at every key (eased out to shoo's
                                # own it stuck out from the body)
                x = angles9(hold, L_ARM)
                for b, i in zip(L_ARM, range(0, 9, 3)): P[b][:3] = list(x[i:i + 3])
            else:
                _, y, _ = left_key(S, P, angles9(prev, L_ARM), lh, angles9(hold, L_ARM), wr_l)
                P, _, _ = left_key(S, P, y, lh, wrist=wr_l)
        W = fk(S, P, hold); Ws = S.world(P)
        if tag == 'spin':
            M = np.linalg.inv(unit3(W0[17][:3, :3])) @ unit3(Ws[17][:3, :3])
            hp = pos(Ws, R_ARM[0]) + frame_of(hand) @ M; bd = frame_of(blade) @ M
        else: hp = pos(Ws, R_ARM[0]) + frame_of(hand); bd = frame_of(blade)
        tgt = pos(Ws, 6, saber_model.GRIP - LEFT_BACK * a)
        legs = {}
        for leg in (R_LEG, L_LEG):
            an = pos(W, leg[2])
            legs[leg] = dict(ankle=an, reach=float(np.linalg.norm(an - pos(W, leg[0])) / (li[leg]['thigh'] + li[leg]['shin'])),
                             place=None if fp is None or not fp[leg][1] else fp[leg][0],
                             planted=True if fp is None else fp[leg][1])
        info.append(dict(hand_err=float(np.linalg.norm(pos(Ws, 6) - hp)),
                         left_err=float(np.linalg.norm(pos(Ws, 3, lh[0]) - tgt)),
                         blade_err=float(np.degrees(np.arccos(np.clip(a @ unit3(Ws[6][:3, :3]) @ bd, -1, 1)))),
                         tip=pos(W, 6, tipL), mid=pos(W, 6, midL), blade=a @ unit3(W[6][:3, :3]), crouch=c, legs=legs,
                         d=0.0 if mv[4] is None else mv[7] * STEP_UNITS * min(1.0, max(0.0, (k - mv[4][0]) / (mv[4][1] - mv[4][0])))))
        out.append(P); prev = P
    return out, info


def frame_of(v):
    """(right, fwd, up) -> model."""
    return v[0] * RIGHT + v[1] * FWD + v[2] * UP


def tracks(keys, mask):
    """Track-major floats in MASK's order (bone 0..18, the slots' order); angles unwrapped key to key, then wrapped
    to (-180, 180] per key (the game interpolates the short way)."""
    T = []
    for b in range(19):
        for s in range(6):
            if not mask[b] >> s & 1: continue
            v = [keys[k][b][s] if keys[k][b][s] is not None else 0.0 for k in range(len(keys))]
            if s < 3: v = [((x + 180.0) % 360.0) - 180.0 for x in v]
            T.append(v)
    return T


def build(r, moves=None, quiet=False):
    """[{tag, keys, cut s, reach, damage, step, tracks, info, link s, step from s, step to s, poses}] and MASK, from a
    RAM reader (moves: MOVES by default)."""
    moves = MOVES if moves is None else moves
    S, shoo, mask = load(r); hold = hold_pose(r, S); li = leg_info(S, hold)
    out, poses = [], {}
    for mv in moves:
        tag, n, cut, link, root, reach, dmg, step, _ = mv
        start = poses[CHAIN[tag][0]][CHAIN[tag][1]] if tag in CHAIN else None
        ks, info = move_keys(S, hold, shoo, mv, start, moves, li)
        poses[tag] = ks
        he = max(i['hand_err'] for i in info); be = max(i['blade_err'] for i in info)
        le = max(i['left_err'] for i in info)
        if not quiet:
            print(f'{tag}: {n} keys, hand error max {he:.2f}, ' + (f'left fist error max {le:.2f}, ' if tag != 'spin' else '')
                  + f'blade angle error max {be:.1f} deg, cut key {cut}, link key {link}' + (f', root {root[0]}..{root[1]}' if root else ''))
        out.append(dict(tag=tag, n=n, cut=cut / KEYS_PER_S, reach=reach, dmg=dmg, step=step, T=tracks(ks, mask), info=info,
                        link=link / KEYS_PER_S, step_from=root[0] / KEYS_PER_S if root else 0.0,
                        step_to=root[1] / KEYS_PER_S if root else 0.0, poses=ks))
    return out, mask


def pack(moves, mask, alloc):
    """The SWN2 table into the image (alloc: bytes -> address); returns its address."""
    hdr = bytearray(b'SWN2' + struct.pack('>I', len(moves)) + mask + b'\0' + struct.pack('>3f', *saber_model.tip_point()[1]))
    for m in moves:
        a = alloc(b''.join(struct.pack(f'>{len(t)}f', *t) for t in m['T']))
        hdr += struct.pack('>4sIfffffIfff', m['tag'].encode(), m['n'], KEYS_PER_S, m['cut'], m['reach'], m['dmg'], m['step'],
                           a, m['link'], m['step_from'], m['step_to'])
    return alloc(bytes(hdr))


# ---- The saber arm in his movement blocks (saber.c arms()) ----
# While the saber is out on Luke (no swing playing), copies of these blocks of Dash's are linked into his chain before
# the game's own (found first by tag, so the game's own requests play them): every track as the game's but the right
# shoulder's, forearm's and hand's rotation tracks, ours: per key the arm solved (solve_key) for the hand at ARM_HAND
# from his right shoulder and the blade along ARM_BLADE, both in his frame, so the blade is held forward and up in
# front of him whatever the block does with his body (one constant arm read -58 deg in shoo and -48 .. -8 in
# jmpF against trot's -37 .. -32, 2026-11-15). Both hands: the left arm's tracks are ours too (left_key: the left fist
# on the hilt under the right). Sstn (the stand) is copied too. Not flyy (the ledge hang copies it by tag: hang.c),
# nor the death blocks. The hand's place: --grid (D3's rule: both fists reach, the blade held, no fist and no point of
# the hilt's back half in a body box on any key; then the hilt's middle nearest his midline, then the least forward).
ARM_BLOCKS = ('Sstn', 'mosy', 'trot', 'shoo', 'jmpF', 'trnl', 'trnr', 'shfl', 'shfr')
ARM_HAND = (-9.0, 14.0, -17.0)        # the right hand from his right shoulder (right, fwd, up; model units): the grip at
#                                       the belt (BELT): 17.1 up at (-6, 16, -8) read as the chest (the user, 2026-11-15);
#                                       --grid-block Sstn
# Each block's own belt place (--grid-block: one place for all failed, the run's left arm short, the jump's hilt in the
# thighs); every block but Sstn listed (Sstn, and the swings' H, take ARM_HAND).
ARM_HAND_AT = {'shoo': (-10.0, 21.0, -14.0), 'mosy': (-11.0, 24.0, -16.0), 'trot': (-10.0, 21.0, -13.0),
               'jmpF': (-10.0, 22.0, -13.0), 'trnl': (-10.0, 14.0, -14.0), 'trnr': (-10.0, 14.0, -14.0),
               'shfl': (-5.0, 14.0, -14.0), 'shfr': (-12.0, 25.0, -13.0)}
BELT = 1.0                            # the belt: this far (model units) above the block's pelvis bone, per key
ARM_BLADE = (0.0, 1.0, 1.0)           # the blade's direction (right, fwd, up): forward, centred, 45 up
# The body leaned forward with the saber out: every key's spine (bone 10, which the game does not turn again after the
# block is sampled; the chest and the neck it does) turned this much about his right axis (+ forward, world_turn), so the
# hold stands with pelvis to neck LEAN_TARGET deg forward of the vertical (Sstn's own 4.3); --arm prints the value
# that gives it (find_lean).
ARM_LEAN = 8.70
LEAN_TARGET = 12.0
# Per block where the game turns his body on its own over the block's keys (measured in the game, palace.st): a jump's
# landing (jmpF) pitches him down to -20 deg, so its blade starts 51 up, not 45.
ARM_BLADE_AT = {'jmpF': (0.0, 1.0, 1.249)}
ARM_TARGET = (0.0, 30.0, 35.0, 55.0)  # held: from his facing between these (deg), elevation between these (deg)
# Z held (shoo): the game plays shoo frozen on its frame 1 (its descriptors at 0x800E0F14, ids 3, 20, 27: frame 1,
# fps 0), so only that key is graded (its other keys are a table of poses the game never starts: solved and packed, not
# checked). The chest turn seen with Z held is the game's own on the chest node; both arms hang under it, so the whole
# hold turns with the chest by itself.
GRADED = {'shoo': (1,)}
MARGIN = 0.3                          # the fists and the hilt's back half at least this far outside every body box
BODY = (17, 10, 9, 16, 15, 14, 13, 12, 11)   # pelvis, spine, chest, the legs: the blade stays out of their boxes
# The left fist on the hilt under the right one (toward the pommel): its centre on the hilt's line LEFT_BACK behind the
# right fist's (GRIP), closing on the hilt as the right fist does (its fist centre and the hilt's line in its frame:
# the right hand's GRIP and AXIS mirrored across his midline at the rest pose, left_hold), the elbow out to his left
# and down. LEFT_BACK is the right fist's box (the Look's meshes on bone 6, guard.bin) along AXIS, 4.27 (2026-11-15),
# capped at HILT_BACK - 0.3 so the left fist stays on the hilt (it then overlaps the right one).
L_ARM = (5, 4, 3)                     # left shoulder, forearm, hand
L_ELBOW = np.array([0.6, 0.0, -0.8])  # ELBOW's mirror
LEFT_BACK = min(4.27, saber_model.HILT_BACK - 0.3)
SWING_TWO = ('sw1 ', 'sw2 ', 'sw3 ')  # the combo held two-handed (the spin one-handed: its left arm the hold's)
# sw2's end carries the right hand 14 out to his right and up, past the left arm's reach (1.84 short at its last key):
# from this key on the left hand lets go, its angles eased from the key before to shoo's own left arm (BASE_KEY) by the
# block's last key; the next swing or the hold brings it back by the game's blend.
LET_GO = {'sw2 ': 9}
GRID = ((-20, 4), (12, 24), (-20, -8), 2)    # --grid: the right hand's place (right, fwd, up ranges; step)
GRID_BELT = ((-12, 0), (12, 26), (-19, -7), 1)    # --grid-block: the same for one block


def left_hold(S):
    """(L_GRIP, L_AXIS): the left fist's centre and the hilt's line in the left hand's frame, the right hand's GRIP
    and AXIS mirrored across his midline (the pelvis's x) at the rest pose (every angle 0)."""
    W = S.world({i: [0.0] * 6 for i in range(19)})
    c = pos(W, 17)[0]
    g = pos(W, 6, saber_model.GRIP); g[0] = 2 * c - g[0]
    lg = (np.r_[g, 1.0] @ np.linalg.inv(W[3]))[:3]
    d = (saber_model.AXIS / np.linalg.norm(saber_model.AXIS)) @ unit3(W[6][:3, :3]) * np.array([-1.0, 1.0, 1.0])
    la = d @ np.linalg.inv(unit3(W[3][:3, :3]))
    return lg, la / np.linalg.norm(la)


def left_key(S, Q, x0, lh, ref=None, wrist=None):
    """The left arm for the right hand's pose Q (the left fist on the hilt, LEFT_BACK behind the right one): (pose,
    the left's 9 angles, its fist error)."""
    W = S.world(Q); a = saber_model.AXIS / np.linalg.norm(saber_model.AXIS)
    tgt = pos(W, 6, saber_model.GRIP - LEFT_BACK * a); d = a @ unit3(W[6][:3, :3])
    if x0 is None: x0 = np.array(Q[5][:3] + Q[4][:3] + Q[3][:3], float)
    Q, x = solve_key(S, Q, tgt, d, x0, L_ARM, lh[1], L_ELBOW, lh[0], ref, wrist)
    return Q, x, float(np.linalg.norm(pos(S.world(Q), 3, lh[0]) - tgt))


def block_poses(r, tag):
    """Every key of Dash's block `tag` as {trot bone: 6 values} (bones mapped by their node: mosy's and Sstn's entry
    order is not trot's)."""
    humn = r.u32(objects(r)['Humn'] + 0x10)
    ch = r.u32(humn + 0x19C)
    trot, b = chain_block(r, ch, 'trot'), chain_block(r, ch, tag)
    tn = [r.u32(trot + 0x38 + 0xA0 * i + 8) for i in range(19)]
    order, e = [], b + 0x38
    while e and len(order) < 19:
        order.append(tn.index(r.u32(e + 8)) if r.u32(e + 8) in tn else -1); e = r.u32(e + 0x0C)
    out = []
    for k in range(r.u32(r.u32(b) + 0x14)):
        P = bone_values(r, b, k, len(order))
        out.append({order[i]: v for i, v in P.items() if order[i] >= 0})
    return out


def lean_of(S, P):
    """The upper body's lean: pelvis (17) to neck (2) from the vertical, degrees, + forward (the model frame)."""
    W = S.world(P); v = pos(W, 2) - pos(W, 17)
    return math.degrees(math.atan2(v @ FWD, v @ UP))


def leaned(S, poses, lean=None):
    """The poses with the spine (10) turned `lean` (ARM_LEAN by default) about his right axis, + forward."""
    lean = ARM_LEAN if lean is None else lean
    return [P if not lean else world_turn(S, P, 10, axis_rot(RIGHT, lean)) for P in poses]


def find_lean(r, S, target=LEAN_TARGET):
    """The spine turn that leans the hold (Sstn key 0) `target` deg forward: bisection."""
    P = block_poses(r, 'Sstn')[0]; lo, hi = -10.0, 40.0
    for _ in range(40):
        m = (lo + hi) / 2
        if lean_of(S, leaned(S, [P], m)[0]) < target: lo = m
        else: hi = m
    return (lo + hi) / 2


def arm_keys(S, poses, blade=None, hand=None, lh=None, lean=None):
    """Both arms' and the spine's 21 angles per key of a block (right shoulder, forearm, hand, then the left's, then
    the spine leaned by `lean`, ARM_LEAN by default: z x y each), wrapped to (-180, 180]; and per key the right hand's
    and the left fist's errors."""
    blade = ARM_BLADE if blade is None else blade
    hand = ARM_HAND if hand is None else hand
    lh = left_hold(S) if lh is None else lh
    out, errs, x0, y0 = [], [], None, None
    for P in leaned(S, poses, lean):
        W = S.world(P)
        if x0 is None: x0 = np.array(P[8][:3] + P[7][:3] + P[6][:3], float)
        hp = pos(W, R_ARM[0]) + frame_of(np.array(hand, float))
        Q, x0 = solve_key(S, P, hp, frame_of(np.array(blade, float)), x0)
        er = float(np.linalg.norm(pos(S.world(Q), 6) - hp))
        Q, y0, el = left_key(S, Q, y0, lh)
        out.append([((v + 180.0) % 360.0) - 180.0 for v in list(x0) + list(y0) + list(P[10][:3])]); errs.append((er, el))
    return out, errs


def arm_build(r, errs=False):
    """[(tag, keys, both arms' angles per key)] for ARM_BLOCKS (errs: and per key the two fists' errors)."""
    S, _, _ = load(r); lh = left_hold(S); out = []
    for tag in ARM_BLOCKS:
        ps = block_poses(r, tag); ks, es = arm_keys(S, ps, ARM_BLADE_AT.get(tag), ARM_HAND_AT.get(tag, ARM_HAND), lh=lh)
        out.append((tag, len(ps), ks) + ((es,) if errs else ()))
    return out


def pack_arm(arms, alloc, parries=None):
    """The arm table into the image: 'SAR2', block count, per block {tag, keys, its 21 tracks (track-major: right
    shoulder z x y, forearm, hand, then left shoulder, forearm, hand, then the spine; `keys` floats each)}; then, after
    the records, 'PRY3' and the parry grid's layers (parries: one parry_build list per FD): NX (len(SD)), NY (len(CZ)),
    NZ (len(FD)) (u32), SD[0], the side step, CZ[0], the height step, FD[0], the distance step (floats), then the nodes'
    poses (21 floats each, SAR2's track order; layer-major, the nearest first, each row-major by height)."""
    rec = b''
    for tag, n, ks, *_ in arms:
        rec += tag.encode() + struct.pack('>II', n, alloc(b''.join(struct.pack(f'>{n}f', *[ks[k][j] for k in range(n)])
                                                                  for j in range(21))))
    if parries:
        assert len(parries) == len(FD) and all(len(l) == len(SD) * len(CZ) for l in parries)
        rec += (b'PRY3' + struct.pack('>III6f', len(SD), len(CZ), len(FD), SD[0], SD[1] - SD[0], CZ[0], CZ[1] - CZ[0],
                                      FD[0], FD[1] - FD[0])
                + b''.join(struct.pack('>21f', *p['angles']) for l in parries for p in l))
    return alloc(b'SAR2' + struct.pack('>I', len(arms)) + rec)


# ---- The parries (saber.c saber_pose): the blade snapped into a bolt's path ----
# A grid of poses of the arms and the spine (the seven bones of SAR2), one per node on the plane the game tests a bolt
# on: sides SD (world units, + his right, as saber.c cross()'s sd) x heights CZ (world units over his feet),
# PARRY_PLANE ahead of his place; PARRY_GRID row-major by height then side. saber.c blends the four nodes around the
# bolt's crossing (grid_blend: bilinear, per angle the short way from the first node) and the playing block's own
# angles toward that as the bolt comes, holds it and eases back. Each node solved on the hold's body (hold_pose: Sstn
# key 0, the hold's lean) by node_pose: the spine turned about the vertical by `turn` (+ to his left, as MOVES), the
# blade along `blade` (right, fwd, up) and through the node: the node lies on the blade `at` of its length from the
# emitter, the grip that far back along the blade, the left fist on the hilt (left_key). (blade, turn, at) per node: a
# random search from the start values (per row the blade out to the node's side, x 0 in the centre column, the +-1.0
# columns half their neighbours'; turns +12.5, +6.25, 0, -6.25, -12.5 from his left; `at` 0.85 on the low row, 0.6 on
# the others) minimising the meet's max error under the per-node rules (parry_check), each blade component within 0.4
# of its start, the turn within 25, `at` within 0.35..0.95.
PARRY_PLANE = 2.25        # world units ahead of his place: the plane the game tests a bolt on (the Humn's +0x60)
# The layers: a grid on each of these planes ahead of him (world units; PARRY_GRID_NEAR on the first, PARRY_GRID on
# PARRY_PLANE). saber.c blends between them by the crossing's distance ahead carried along his own move (a bolt met
# on the run crosses nearer than the 2.25 plane by the time the blade gets there: 0.65..1.43 off with one layer).
FD = (1.5, PARRY_PLANE)
SD = (-2.0, -1.0, 0.0, 1.0, 2.0)   # the grid's sides (world units, + his right)
CZ = (0.9, 2.4, 3.9, 5.4)  # the grid's heights (world units over his feet)
PARRY_GRID = [            # (blade (right, fwd, up), turn, at) per node: CZ 0.9 (sd -2 .. +2), then 2.4, 3.9, 5.4
    ((-0.682, 0.451, -1.1), -12.5, 0.95), ((-0.255, 0.43, -1.006), 10.7, 0.893), ((0.052, 0.281, -0.732), -23.4, 0.89), ((0.481, 0.242, -1.049), -5.3, 0.85), ((0.65, 0.252, -1.061), 4.6, 0.949),
    ((-0.548, 0.238, -0.41), -12.5, 0.615), ((-0.265, 0.501, -0.6), -1.2, 0.48), ((0.033, 0.262, -0.448), -2.4, 0.4), ((0.252, 0.117, -0.528), -7.7, 0.402), ((0.639, 0.172, -0.332), 9.3, 0.771),
    ((-1.0, 0.338, 0.2), 2.4, 0.534), ((-0.7, 0.541, 0.2), 29.9, 0.35), ((0.4, 0.373, 0.229), -23.9, 0.35), ((0.64, 0.347, 0.2), -18.9, 0.417), ((0.936, 0.368, 0.2), 7.2, 0.459),
    ((-0.815, 0.576, 0.884), -2.7, 0.552), ((-0.119, 0.367, 0.618), 2.6, 0.378), ((-0.239, 0.203, 0.74), 24.2, 0.418), ((0.492, 0.156, 0.751), -13.7, 0.504), ((0.606, 0.333, 0.45), -14.2, 0.753),
]
PARRY_GRID_NEAR = [       # the layer at FD[0] 1.5 ahead, as PARRY_GRID: tune_parry.py --plane 1.5 (phase 1 40, phase 2
                          # 300, seed 3, from PARRY_GRID's values) passed 19 of 20 nodes; cz 3.9 sd 0 failed its blends
                          # (shfl key 14 w 0.5 at -0.27) at the box's edges, so that node alone was searched again in a
                          # wider box (NODES=12 BOX_B=0.6 BOX_T=40 AT_LO=0.30, RESTARTS 400, phase 1 400, phase 2 300,
                          # seed 9) and passes (blends 0.04, clearance 2.51); every node PASS, the meet max 0.710, mean
                          # 0.133: this layer's limit MEET_MAX_NEAR
    ((-0.543, 0.212, -1.083), -12.5, 0.908), ((-0.196, 0.085, -0.93), 11.3, 0.875), ((0.262, 0.14, -0.613), -23.8, 0.862), ((0.612, 0.05, -0.948), -13.0, 0.921), ((0.683, 0.106, -1.069), 5.8, 0.942),
    ((-0.525, 0.233, -0.583), -12.5, 0.513), ((-0.034, 0.171, -0.483), 6.0, 0.43), ((0.171, 0.079, -0.411), -7.0, 0.38), ((0.427, 0.148, -0.591), -8.3, 0.506), ((0.879, 0.05, -0.438), 10.5, 0.763),
    ((-0.948, -0.014, 0.2), 6.5, 0.458), ((-0.7, -0.029, 0.2), 31.2, 0.35), ((0.411, 0.185, 0.272), -34.3, 0.3), ((0.694, 0.04, 0.247), -24.3, 0.433), ((0.967, 0.014, 0.2), 9.7, 0.478),
    ((-0.85, 0.15, 0.974), 10.4, 0.53), ((-0.045, 0.098, 0.671), 7.5, 0.411), ((-0.168, -0.1, 1.013), 25.0, 0.512), ((0.372, 0.022, 0.493), -7.2, 0.642), ((0.671, 0.148, 0.45), -35.5, 0.786),
]
PARRY_GRIDS = (PARRY_GRID_NEAR, PARRY_GRID)   # per FD
MEET_SD = np.round(np.arange(-2.25, 2.2501, 0.25), 2)   # --parry's meet: the test grid (world units), the blend posed at
MEET_CZ = np.round(np.arange(0.9, 5.4001, 0.25), 2)     # each point and the point's distance from the blade taken
MEET_MAX, MEET_MEAN = 0.5, 0.25   # the meet passes at max <= MEET_MAX and mean <= MEET_MEAN (world units)
MEET_MAX_NEAR = 0.75     # the 1.5 layer's max: its nodes reach no lower than 0.71 (sd -1 cz 2.9) under the node rules
MEET_MAXES = (MEET_MAX_NEAR, MEET_MAX)   # per FD
PARRY_BLEND = (0.25, 0.5, 0.75)   # --parry: the blends from every ARM_BLOCKS key checked for clearance (MARGIN - 0.3)
# but jmpF's: no parry starts in the air (saber.c), and its landing keys (23..27, the thighs up) put three variants'
# blended blade through the thighs whatever the hand's place
PARRY_SKIP = ('jmpF',)


def parry_pose(S, hold, lh, hand, blade, turn):
    """One parry on the hold's body: (pose, its 21 angles (SAR2's order, wrapped), right fist error, left fist error)."""
    P = world_turn(S, copy(hold), 10, axis_rot(UP, turn), hold[10][:3]) if turn else copy(hold)
    W = S.world(P)
    hp = pos(W, R_ARM[0]) + frame_of(np.array(hand, float)); bd = frame_of(np.array(blade, float))
    _, x = solve_key(S, P, hp, bd, angles9(hold, R_ARM), ref=angles9(hold, R_ARM))
    P, _ = solve_key(S, P, hp, bd, x)
    er = float(np.linalg.norm(pos(S.world(P), 6) - hp))
    _, y, _ = left_key(S, P, angles9(hold, L_ARM), lh, angles9(hold, L_ARM))
    P, _, el = left_key(S, P, y, lh)
    ang = [((v + 180.0) % 360.0) - 180.0 for v in list(angles9(P, R_ARM)) + list(angles9(P, L_ARM)) + list(P[10][:3])]
    return P, ang, er, el


def node_target(floor, sd, cz, plane=PARRY_PLANE):
    """The point (sd, cz) of the parry plane `plane` ahead (world units) in the model frame (floor: floor_line's height)."""
    return STEP_UNITS * (sd * RIGHT + plane * FWD) + (floor + cz * STEP_UNITS) * UP


def blade_ends():
    """The blade's emitter and tip (hand frame, local units)."""
    a = saber_model.AXIS / np.linalg.norm(saber_model.AXIS)
    return saber_model.GRIP + a * saber_model.HILT_FRONT, saber_model.tip_point()[0]


def blade_miss(W, tgt):
    """The point tgt's distance from the blade's segment (emitter to tip) in the posed W (model units)."""
    e, t = (pos(W, 6, p) for p in blade_ends()); v = t - e
    u = min(1.0, max(0.0, float((tgt - e) @ v / (v @ v))))
    return float(np.linalg.norm(e + v * u - tgt))


def node_pose(S, hold, lh, floor, at, sd, cz, blade, turn, rounds=3, plane=PARRY_PLANE):
    """A grid node's parry (the PARRY_GRID comment): the grip placed `at` of the blade (from the emitter) back from the
    node's target along `blade`, turned into parry_pose's hand place (the hand's node from his right shoulder, after
    the turn) through the hand's own frame (the grip's offset from the hand's node, from the last solve). (pose, 21
    angles, right fist error, left fist error, hand place, the target's distance from the blade (world units))."""
    tgt = node_target(floor, sd, cz, plane); d = frame_of(np.array(blade, float)); d = d / np.linalg.norm(d)
    W0 = S.world(hold); e, t = blade_ends()
    g = tgt - d * float(np.linalg.norm(pos(W0, 6, e + (t - e) * at) - pos(W0, 6, saber_model.GRIP)))
    Pt = world_turn(S, copy(hold), 10, axis_rot(UP, turn), hold[10][:3]) if turn else copy(hold)
    sh = pos(S.world(Pt), R_ARM[0])
    off = pos(W0, 6, saber_model.GRIP) - pos(W0, 6)
    for _ in range(rounds):
        v = g - off - sh; hand = (float(v @ RIGHT), float(v @ FWD), float(v @ UP))
        P, ang, er, el = parry_pose(S, hold, lh, hand, blade, turn)
        W = S.world(P); off = pos(W, 6, saber_model.GRIP) - pos(W, 6)
    return P, ang, er, el, hand, blade_miss(W, tgt) / STEP_UNITS


def grid_blend(A, sd, cz):
    """saber.c's pose at a crossing (sd, cz): the four nodes around it (A: [len(CZ)][len(SD)][21] angles; the place
    clamped to the grid) blended bilinearly, per angle from the first node by wrap180 differences."""
    A = np.asarray(A, float); nx, ny = len(SD), len(CZ)
    fx = min(max((sd - SD[0]) / (SD[1] - SD[0]), 0.0), nx - 1.0); i = min(int(fx), nx - 2); fx -= i
    fy = min(max((cz - CZ[0]) / (CZ[1] - CZ[0]), 0.0), ny - 1.0); j = min(int(fy), ny - 2); fy -= j
    a = A[j, i]; w = lambda b: ((b - a) + 180.0) % 360.0 - 180.0
    return a + (1 - fy) * fx * w(A[j, i + 1]) + fy * (1 - fx) * w(A[j + 1, i]) + fx * fy * w(A[j + 1, i + 1])


def parry_meet(S, hold, floor, A, plane=PARRY_PLANE):
    """The meet map: per test point (MEET_CZ x MEET_SD) on the plane `plane` ahead the grid's blend posed on the
    hold's body and the point's distance from the blade's segment (world units)."""
    A = np.asarray(A, float).reshape(len(CZ), len(SD), 21)
    return np.array([[blade_miss(S.world(with21(hold, grid_blend(A, sd, cz))), node_target(floor, sd, cz, plane)) / STEP_UNITS
                      for sd in MEET_SD] for cz in MEET_CZ])


def with21(P, a):
    """The pose P with the 21 SAR2 angles a on the arms and the spine."""
    Q = copy(P)
    for b, i in zip(R_ARM + L_ARM + (10,), range(0, 21, 3)): Q[b][:3] = list(a[i:i + 3])
    return Q


def blend21(base, pose, w):
    """saber_pose's blend: per angle base + wrap180(pose - base) x w."""
    b = np.asarray(base, float); return b + (((np.asarray(pose, float) - b) + 180.0) % 360.0 - 180.0) * w


def parry_clear(S, P, boxes, lh, pts):
    return min(outside(np.r_[saber_model.GRIP[None, :], pts], S.world(P), boxes, 6),
               outside(lh[0][None, :], S.world(P), boxes, 3))


def parry_ctx(r, img):
    """What parry_check needs, built once: S, the hold, the left hold, the body boxes, the blade's points, the floor,
    and the blend bases (every ARM_BLOCKS key but PARRY_SKIP's, shoo's GRADED key, as (tag, key, pose, 21 angles))."""
    S, _, _ = load(r); hold = hold_pose(r, S); arms = arm_build(r)
    bases = []
    for i, tag in enumerate(ARM_BLOCKS):
        if tag in PARRY_SKIP: continue
        for k, P in enumerate(block_poses(r, tag)):
            if k not in GRADED.get(tag, (k,)): continue   # shoo: the key the game plays
            B = with21(P, arms[i][2][k])
            bases.append((tag, k, B, angles9(B, R_ARM).tolist() + angles9(B, L_ARM).tolist() + list(B[10][:3])))
    return dict(S=S, hold=hold, lh=left_hold(S), boxes=body_boxes(img), pts=swing_points(),
                floor=floor_line(S, hold, img), bases=bases)


def node_rules(c, P, ang, er, el, blends=True):
    """A node's rules: (fails, clearance, worst blend clearance, (tag, key, w) of it): the fists (right <= 0.1, left
    <= 0.5), the pose's clearance (the fists, the hilt and the blade's five points MARGIN outside every BODY box), the
    blends from every base at PARRY_BLEND (clearance >= MARGIN - 0.3; skipped with blends False)."""
    S, boxes, lh, pts = c['S'], c['boxes'], c['lh'], c['pts']
    fails = []
    if er > 0.1: fails.append('right fist')
    if el > 0.5: fails.append('left fist')
    mg = parry_clear(S, P, boxes, lh, pts)
    if mg < MARGIN: fails.append('clearance')
    bw, worst = 1e9, (None, None, None)
    if blends:
        for tag, k, B, base in c['bases']:
            for w in PARRY_BLEND:
                m = parry_clear(S, with21(B, blend21(base, ang, w)), boxes, lh, pts)
                if m < bw: bw, worst = m, (tag, k, w)
        if bw < MARGIN - 0.3: fails.append(f'blend {worst[0]} key {worst[1]} w {worst[2]}')
    return fails, mg, bw, worst


def node_name(j): return f'cz {CZ[j // len(SD)]:.1f} sd {SD[j % len(SD)]:+.1f}'


def parry_build(r, grid=None, S=None, c=None, plane=PARRY_PLANE):
    """[{name, row, sd, cz, blade, turn, at, hand, target, pose, angles (21), er, el, miss}] for the layer on `plane`
    (its grid: PARRY_GRIDS's, or `grid`), row-major by height then side."""
    if c is None:
        S = load(r)[0] if S is None else S; hold = hold_pose(r, S)
        import paths   # the floor needs the Look's foot boxes: guard.bin as it is
        img = open(os.path.join(paths.GAME, 'guard.bin'), 'rb').read()
        c = dict(S=S, hold=hold, lh=left_hold(S), floor=floor_line(S, hold, img))
    out = []
    for j, (blade, turn, at) in enumerate(PARRY_GRIDS[FD.index(plane)] if grid is None else grid):
        row, sd, cz = j // len(SD), SD[j % len(SD)], CZ[j // len(SD)]
        P, ang, er, el, hand, miss = node_pose(c['S'], c['hold'], c['lh'], c['floor'], at, sd, cz, blade, turn, plane=plane)
        out.append(dict(name=node_name(j), row=row, sd=sd, cz=cz, blade=tuple(blade), turn=turn, at=at, hand=hand, pose=P,
                        target=node_target(c['floor'], sd, cz, plane), angles=ang, er=er, el=el, miss=miss))
    return out


def parry_layers(r):
    """pack_arm's parries: parry_build per FD layer, the nearest first."""
    S = load(r)[0]
    return [parry_build(r, S=S, plane=fd) for fd in FD]


def parry_check(r, img, grid=None, c=None, plane=PARRY_PLANE):
    """--parry: one layer (on `plane`): per node PASS / FAIL by node_rules (its line: blade, turn, hand, fists,
    clearance, blends, the target's distance from its own blade), then the meet over the test grid (parry_meet: PASS at
    max <= the layer's MEET_MAXES and mean <= MEET_MEAN; its max, mean and worst five points). Returns (all passed, nodes, the meet
    map)."""
    c = parry_ctx(r, img) if c is None else c
    nodes = parry_build(r, grid, c=c, plane=plane); ok_all = True
    for n in nodes:
        fails, mg, bw, worst = node_rules(c, n['pose'], n['angles'], n['er'], n['el'])
        print(f"{n['name']}: {'PASS' if not fails else 'FAIL (' + ', '.join(fails) + ')'}: blade "
              f"({', '.join(f'{x:+.2f}' for x in n['blade'])}), turn {n['turn']:+.1f}, at {n['at']:.2f}, hand "
              f"({', '.join(f'{x:.1f}' for x in n['hand'])}), fists {n['er']:.2f}/{n['el']:.2f}, clearance {mg:.2f}, "
              f"blends {bw:.2f} (worst {worst[0]} key {worst[1]} w {worst[2]}), miss {n['miss']:.3f}")
        ok_all &= not fails
    M = parry_meet(c['S'], c['hold'], c['floor'], [n['angles'] for n in nodes], plane)
    mmax = MEET_MAXES[FD.index(plane)] if plane in FD else MEET_MAX
    mok = M.max() <= mmax and M.mean() <= MEET_MEAN
    worst = sorted(((M[j, i], MEET_SD[i], MEET_CZ[j]) for j in range(len(MEET_CZ)) for i in range(len(MEET_SD))),
                   reverse=True)[:5]
    print(f"meet: {'PASS' if mok else 'FAIL'}: max {M.max():.3f} (<= {mmax}), mean {M.mean():.3f} (<= {MEET_MEAN}) "
          f"over {M.size} points; worst " + ', '.join(f'{d:.3f} at sd {s:+.2f} cz {z:.2f}' for d, s, z in worst))
    return ok_all and mok, nodes, M


def parry_sheet_moves(r, nodes, S=None, plane=PARRY_PLANE):
    """One layer's nodes as sheet() moves: a row per height (the highest first), each node's pose on the hold's body,
    its target marked."""
    S = load(r)[0] if S is None else S
    hold = hold_pose(r, S); nx = len(SD)
    return [dict(tag=f'cz {CZ[row]}', n=nx, cut=-1, info=[dict(d=0.0)] * nx,
                 title=f"fd {plane:g} ahead, cz {CZ[row]} (world units over his feet), sd {', '.join(f'{s:+g}' for s in SD)}: the node's pose, "
                       f"its target red (front / his right side)",
                 poses=[with21(hold, n['angles']) for n in nodes[row * nx:(row + 1) * nx]],
                 marks=[n['target'] for n in nodes[row * nx:(row + 1) * nx]])
            for row in reversed(range(len(CZ)))]


def parry_err_map(M, out, cell=34):
    """The meet map as a picture: a cell per test point (sd across, his left on the left; cz up), coloured green (0)
    to yellow (MEET_MEAN) to red (MEET_MAX and over), the distance written in it (hundredths), the nodes ringed."""
    from PIL import Image, ImageDraw
    nx, ny = len(MEET_SD), len(MEET_CZ); L, T = 46, 24
    im = Image.new('RGB', (L + nx * cell + 10, T + ny * cell + 30), 'white'); d = ImageDraw.Draw(im)
    def col(v):
        if v <= MEET_MEAN: u = v / MEET_MEAN; return (int(60 + 180 * u), int(190 + 40 * u), 60)
        u = min(1.0, (v - MEET_MEAN) / (MEET_MAX - MEET_MEAN)); return (240, int(230 - 190 * u), 60)
    for j in range(ny):
        for i in range(nx):
            x, y = L + i * cell, T + (ny - 1 - j) * cell
            d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=col(M[j, i]), outline='white')
            d.text((x + 6, y + 11), f'{M[j, i] * 100:.0f}', fill='black')
            if any(abs(MEET_SD[i] - s) < 1e-6 for s in SD) and any(abs(MEET_CZ[j] - z) < 1e-6 for z in CZ):
                d.ellipse([x + 2, y + 2, x + cell - 3, y + cell - 3], outline='black', width=2)
        d.text((4, T + (ny - 1 - j) * cell + 11), f'{MEET_CZ[j]:.2f}', fill='black')
    for i in range(0, nx, 2): d.text((L + i * cell + 4, T + ny * cell + 4), f'{MEET_SD[i]:+.2f}', fill='black')
    d.text((4, 4), f'meet: max {M.max():.3f}, mean {M.mean():.3f} (world units x 100 per cell); sd across (+ his right), '
                   f'cz up; nodes ringed', fill='black')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out); print('wrote', out)


def blade_points():
    """The hilt's and the core's vertices (hand frame, local units)."""
    return np.concatenate([p for k, p, c, t in saber_model.parts() if k in ('opaque', 'core')])


def body_boxes(img, base=0x80548000, bones=None):
    """{Dash bone: (lo, hi)}: the Look's meshes' box on each BODY bone (or `bones`; the bone's frame, local units),
    from guard.bin."""
    g = lambda a: struct.unpack_from('>I', img, a - base)[0]
    f = lambda a: struct.unpack_from('>f', img, a - base)[0]
    out = {}
    for d in (BODY if bones is None else bones):
        n, lst = struct.unpack_from('>II', img, 8 + 8 * d)
        lo, hi = np.full(3, 1e9), np.full(3, -1e9)
        for m in (g(lst + 4 * i) for i in range(n)):
            for j in range(g(m + 0x0C)):
                q = g(g(m + 0x10) + 4 * j)
                lo = np.minimum(lo, [f(q + 4 * k) for k in range(3)]); hi = np.maximum(hi, [f(q + 12 + 4 * k) for k in range(3)])
        out[d] = (lo, hi)
    return out


def angles_of(d, fw):
    """(degrees from the facing fw, elevation) of the direction d (both world or both model)."""
    f = np.array([fw[0], fw[1], 0.0]); f /= np.linalg.norm(f); h = math.hypot(d[0], d[1])
    return (math.degrees(math.acos(np.clip((d[0] * f[0] + d[1] * f[1]) / h, -1, 1))) if h > 1e-6 else 0.0,
            math.degrees(math.atan2(d[2], h)))


def inside(pts, W, boxes, bone=6):
    """The bones whose box holds any of pts (rows, the frame of `bone` -> world by W[bone]; W 4x4 per bone, row
    vectors)."""
    hp = np.c_[pts, np.ones(len(pts))] @ W[bone]
    hit = []
    for d, (lo, hi) in boxes.items():
        q = hp @ np.linalg.inv(W[d])
        if (((q[:, :3] > lo) & (q[:, :3] < hi)).all(axis=1)).any(): hit.append(d)
    return hit


def outside(pts, W, boxes, bone=6):
    """How far the nearest of pts is outside the boxes (the box bone's local units; < 0: inside by that much)."""
    hp = np.c_[pts, np.ones(len(pts))] @ W[bone]
    m = 1e9
    for d, (lo, hi) in boxes.items():
        q = (hp @ np.linalg.inv(W[d]))[:, :3]
        m = min(m, float(np.maximum(lo - q, q - hi).max(axis=1).min()))
    return m


def hilt_back():
    """The hilt's vertices on its back half (from the pommel to its middle; hand frame, local units)."""
    h = np.concatenate([p for k, p, c, t in saber_model.parts() if k == 'opaque'])
    a = saber_model.AXIS / np.linalg.norm(saber_model.AXIS)
    return h[(h - saber_model.GRIP) @ a <= (saber_model.HILT_FRONT - saber_model.HILT_BACK) / 2]


def hold_eval(S, poses, blade, hand, lh, boxes, fast=False, keys=None, gz=None):
    """The hold on the graded keys of one block (keys: their indices, None every key; every key is solved, from the
    first, as arm_keys does): the two fists' errors, the blade's angles (from his facing, elevation), the fists' and
    the hilt's back half's box hits and margin (`outside`), the hilt middle's distance from his midline (the pelvis's
    x). fast: at the first key that fails (both fists reach, the blade held by ARM_TARGET, the box margin >= MARGIN),
    the failure's name instead. st['gz'] (and the list gz, when given, also before a fast failure): per graded key the
    grip's height above the belt (BELT)."""
    a = saber_model.AXIS / np.linalg.norm(saber_model.AXIS)
    mid = saber_model.GRIP + a * (saber_model.HILT_FRONT - saber_model.HILT_BACK) / 2
    back = hilt_back(); g = saber_model.GRIP[None, :]
    st = dict(er=0.0, el=0.0, ys=[], es=[], hits={}, margin=1e9, dx=[], gz=[])
    gz = [] if gz is None else gz
    x0 = y0 = None; T = ARM_TARGET
    if keys is not None: poses = poses[:max(keys) + 1]
    for k, P in enumerate(leaned(S, poses)):
        W = S.world(P)
        if x0 is None: x0 = np.array(P[8][:3] + P[7][:3] + P[6][:3], float)
        hp = pos(W, R_ARM[0]) + frame_of(np.array(hand, float))
        Q, x0 = solve_key(S, P, hp, frame_of(np.array(blade, float)), x0)
        if keys is not None and k not in keys:
            Q, y0, el = left_key(S, Q, y0, lh); continue
        W = S.world(Q); er = float(np.linalg.norm(pos(W, 6) - hp))
        gz.append(float(pos(W, 6, saber_model.GRIP)[2] - pos(W, 17)[2] - BELT))
        y, e = angles_of(a @ unit3(W[6][:3, :3]), (0, -1, 0))
        held = T[0] <= y <= T[1] and T[2] <= e <= T[3]
        if fast and er > 0.5: return 'right fist'
        if fast and not held: return 'blade'
        Q, y0, el = left_key(S, Q, y0, lh); W = S.world(Q)
        hit = set(inside(np.r_[g, back], W, boxes, 6)) | set(inside(lh[0][None, :], W, boxes, 3))
        if fast and el > 0.5: return 'left fist'
        if fast and hit: return 'box ' + ','.join(map(str, sorted(hit)))
        m = min(outside(np.r_[g, back], W, boxes, 6), outside(lh[0][None, :], W, boxes, 3))
        if fast and m < MARGIN: return 'margin'
        st['er'] = max(st['er'], er); st['el'] = max(st['el'], el); st['ys'].append(y); st['es'].append(e)
        for d in hit: st['hits'][d] = st['hits'].get(d, 0) + 1
        st['margin'] = min(st['margin'], m)
        st['dx'].append(abs(pos(W, 6, mid)[0] - pos(W, 17)[0]))
    st['gz'] = list(gz)
    return st


def arm_check(r, img, hand=None):
    """The hold on the graded keys of ARM_BLOCKS (every key; shoo's GRADED) (Skel's FK, the model frame: facing -y), per block: the two fists' error
    maxima, the blade's angles, the share held, the keys with a fist or a hilt-back point in a body box, the box
    margin, the hilt middle's distance from his midline."""
    S, _, _ = load(r); lh = left_hold(S)
    boxes = body_boxes(img); hand = ARM_HAND if hand is None else hand
    print(f'  hand {hand}, LEFT_BACK {LEFT_BACK:.2f}, L_GRIP {np.round(lh[0], 3)}, L_AXIS {np.round(lh[1], 3)}')
    print(f'  hold lean {lean_of(S, hold_pose(r, S)):.2f} (ARM_LEAN {ARM_LEAN}; for {LEAN_TARGET}: {find_lean(r, S):.3f})')
    for tag in ARM_BLOCKS:
        ps = block_poses(r, tag); ls = [lean_of(S, P) for P in leaned(S, ps)]
        st = hold_eval(S, ps, ARM_BLADE_AT.get(tag, ARM_BLADE), ARM_HAND_AT.get(tag, hand), lh, boxes,
                       keys=GRADED.get(tag))
        ys, es = st['ys'], st['es']; n = len(ys); T = ARM_TARGET
        held = sum(T[0] <= y <= T[1] and T[2] <= e <= T[3] for y, e in zip(ys, es))
        print(f'  {tag}: {n:2d} keys, fist error right {st["er"]:.2f} left {st["el"]:.2f}, from facing '
              f'{min(ys):4.1f}..{max(ys):4.1f}, elevation {min(es):4.1f}..{max(es):4.1f}, held {100 * held / n:3.0f}%, '
              f'keys in a box {st["hits"] or 0}, box margin {st["margin"]:.2f}, midline {np.mean(st["dx"]):.2f}'
              + f', lean {min(ls):4.1f}..{max(ls):4.1f}, grip to belt {np.mean(st["gz"]):+.2f}'
              + f' (hand {ARM_HAND_AT.get(tag, hand)})' + (f' (graded keys {list(GRADED[tag])})' if tag in GRADED else ''))


_G = {}
def _grid_init():
    import paths
    from ram import Ram
    r = Ram(os.path.join(paths.GAME, 'palace.bin')); S, _, _ = load(r)
    _G.update(S=S, lh=left_hold(S), boxes=body_boxes(open(os.path.join(paths.GAME, 'guard.bin'), 'rb').read()),
              poses={t: block_poses(r, t) for t in ARM_BLOCKS})


def _grid_point(hand, skip=()):
    sts = []
    for tag in (t for t in ARM_BLOCKS if t not in skip):
        st = hold_eval(_G['S'], _G['poses'][tag], ARM_BLADE_AT.get(tag, ARM_BLADE), ARM_HAND_AT.get(tag, hand), _G['lh'],
                       _G['boxes'], fast=True,
                       keys=GRADED.get(tag))
        if isinstance(st, str): return hand, f'{tag} {st}'
        sts.append(st)
    return hand, dict(dx=float(np.mean([d for st in sts for d in st['dx']])), er=max(st['er'] for st in sts),
                      el=max(st['el'] for st in sts), margin=min(st['margin'] for st in sts),
                      y=(min(min(st['ys']) for st in sts), max(max(st['ys']) for st in sts)),
                      e=(min(min(st['es']) for st in sts), max(max(st['es']) for st in sts)))


def grid(skip=()):
    """D3's grid over the right hand's place: of the points that hold on every graded key of every ARM_BLOCKS block, the one
    whose hilt middle is nearest his midline (the mean over the keys), then the smallest fwd. skip: blocks left out
    (a diagnosis: which block empties the grid)."""
    import functools
    import multiprocessing as mp
    (r0, r1), (f0, f1), (u0, u1), step = GRID
    pts = [(float(a), float(b), float(c)) for a in range(r0, r1 + 1, step) for b in range(f0, f1 + 1, step)
           for c in range(u0, u1 + 1, step)]
    with mp.get_context('spawn').Pool(os.cpu_count(), _grid_init) as pool:
        out = list(pool.imap_unordered(functools.partial(_grid_point, skip=skip), pts))
    res = [x for x in out if isinstance(x[1], dict)]
    print(f'grid: {len(pts)} points, {len(res)} hold on every key')
    fails = {}
    for hand, why in out:
        if isinstance(why, str): fails[why] = fails.get(why, 0) + 1
    print('  first failure:', ', '.join(f'{k} {v}' for k, v in sorted(fails.items(), key=lambda x: -x[1])))
    by = {}
    for hand, why in out:
        if isinstance(why, str): by.setdefault(why.split(' ', 1)[1].split(' ')[0], []).append(hand)
    for k, hs in by.items():
        print(f'  {k}: right {min(h[0] for h in hs):.0f}..{max(h[0] for h in hs):.0f}, fwd {min(h[1] for h in hs):.0f}..'
              f'{max(h[1] for h in hs):.0f}, up {min(h[2] for h in hs):.0f}..{max(h[2] for h in hs):.0f}')
    res.sort(key=lambda x: (round(x[1]['dx'], 2), x[0][1]))
    for hand, st in res[:8]:
        print(f'  {hand}: midline {st["dx"]:.2f}, fist error right {st["er"]:.2f} left {st["el"]:.2f}, from facing '
              f'{st["y"][0]:.1f}..{st["y"][1]:.1f}, elevation {st["e"][0]:.1f}..{st["e"][1]:.1f}, box margin {st["margin"]:.2f}')
    if res: print('winner', res[0][0])
    return res

def _grid_block_point(hand, tag):
    gz = []
    st = hold_eval(_G['S'], _G['poses'][tag], ARM_BLADE_AT.get(tag, ARM_BLADE), hand, _G['lh'], _G['boxes'], fast=True,
                   keys=GRADED.get(tag), gz=gz)
    return hand, st if isinstance(st, str) else dict(dx=float(np.mean(st['dx'])), er=st['er'], el=st['el'],
                                                       margin=st['margin'], y=(min(st['ys']), max(st['ys'])),
                                                       e=(min(st['es']), max(st['es']))), float(np.mean(gz))


def grid_block(tag):
    """One block's right-hand place over GRID_BELT: of the points that hold on every graded key of the block (grid's
    rule), the one whose grip height (the mean over the graded keys, minus BELT) is nearest 0; ties (within 0.5) by the
    hilt middle's distance from his midline, then the smaller fwd. Also the first failures of the points at the belt
    (grip within 0.5 of it; for a point that fails, over the keys before the failure)."""
    import functools
    import multiprocessing as mp
    (r0, r1), (f0, f1), (u0, u1), step = GRID_BELT
    pts = [(float(a), float(b), float(c)) for a in range(r0, r1 + 1, step) for b in range(f0, f1 + 1, step)
           for c in range(u0, u1 + 1, step)]
    with mp.get_context('spawn').Pool(os.cpu_count(), _grid_init) as pool:
        out = list(pool.imap_unordered(functools.partial(_grid_block_point, tag=tag), pts, chunksize=8))
    res = [x for x in out if isinstance(x[1], dict)]
    print(f'grid {tag}: {len(pts)} points, {len(res)} hold on every graded key')
    fails, belt = {}, {}
    for hand, why, z in out:
        if isinstance(why, str):
            fails[why] = fails.get(why, 0) + 1
            if abs(z) <= 0.5: belt[why] = belt.get(why, 0) + 1
    print('  first failure:', ', '.join(f'{k} {v}' for k, v in sorted(fails.items(), key=lambda x: -x[1])) or '-')
    print('  at the belt (grip within 0.5):', sum(abs(z) <= 0.5 for _, w, z in res), 'hold; first failure',
          ', '.join(f'{k} {v}' for k, v in sorted(belt.items(), key=lambda x: -x[1])) or '-')
    if not res: print('winner none'); return None
    best = min(abs(z) for _, _, z in res)
    tie = sorted((x for x in res if abs(x[2]) <= best + 0.5), key=lambda x: (round(x[1]['dx'], 2), x[0][1]))
    for hand, st, z in tie[:8]:
        print(f'  {hand}: grip to belt {z:+.2f}, midline {st["dx"]:.2f}, fist error right {st["er"]:.2f} left '
              f'{st["el"]:.2f}, from facing {st["y"][0]:.1f}..{st["y"][1]:.1f}, elevation {st["e"][0]:.1f}..'
              f'{st["e"][1]:.1f}, box margin {st["margin"]:.2f}')
    print(f'winner {tie[0][0]} grip to belt {tie[0][2]:+.2f}')
    return tie[0]


def swing_points():
    """Five points along the hilt and the blade, pommel to tip (hand frame, local units)."""
    a = saber_model.AXIS / np.linalg.norm(saber_model.AXIS); tip = saber_model.tip_point()[0]
    p0 = saber_model.GRIP - saber_model.HILT_BACK * a
    return np.array([p0 + (tip - p0) * t for t in np.linspace(0.0, 1.0, 5)])


def floor_line(S, hold, img):
    """The floor in his frame: the lowest corner of the foot boxes (the Look's meshes on bones 14, 11) in the hold."""
    W = S.world(hold); z = 1e9
    for b, (lo, hi) in body_boxes(img, bones=(14, 11)).items():
        c = np.array([[(lo, hi)[i >> j & 1][j] for j in range(3)] for i in range(8)])
        z = min(z, float(((np.c_[c, np.ones(8)] @ W[b])[:, 2]).min()))
    return z


def wrapd(a, b): return abs(((a - b) + 180.0) % 360.0 - 180.0)


def swing_check(r, img, moves=None):
    """The swings' checks, one line per move (PASS / FAIL): both fists on the hilt (sw1-3: right <= 0.1, left <= 0.5);
    the wrists (wrist_of, max over the keys: bend <= WRIST_BEND + 5, twist <= WRIST_TWIST + 5; the spin's left not
    graded); the blade on its line (<= 5 deg on every key); the elbows printed (min / max angle, not graded);
    the ends (key 0 the hold or the chained source's rest key, the last key the hold: all 52 values equal); the strike
    (from STRIKE's wind-up to its follow-through: the tip's speed per key has one maximum, within the cut key +- 1, no
    key turns the blade more than BLADE_TURN, the tip's path off its plane <= 3.0 rms, the spin's OFF_PLANE); joints (no
    angle steps more than JOINT_STEP key to key); feet (a planted ankle within 1.0 of its place, at the stance height +- 0.5, a planted leg's reach
    <= REACH while the feet are apart); clearance (both fists and five points along hilt and blade MARGIN outside every
    BODY box, the tip above the floor line); the spin's pelvis (within 1 deg of its profile, monotonic). Returns
    (all passed, moves)."""
    S, shoo, mask = load(r); hold = hold_pose(r, S); li = leg_info(S, hold)
    built, _ = build(r, moves, quiet=True)
    by = {m['tag']: m for m in built}
    boxes = body_boxes(img); lh = left_hold(S); pts = swing_points()
    floor = floor_line(S, hold, img); hold_T = tracks([hold], mask)
    W0 = S.world(hold); f0 = unit3(W0[17][:3, :3])
    ok_all = True
    for m in built:
        tag, n, info, T, P = m['tag'], m['n'], m['info'], m['T'], m['poses']
        mv = next(x for x in (moves or MOVES) if x[0] == tag)
        fails, parts = [], []
        # both hands
        if tag != 'spin':
            he = max(i['hand_err'] for i in info); le = max(i['left_err'] for i in info)
            if he > 0.1: fails.append('right hand')
            if le > 0.5: fails.append('left fist ' + ','.join(str(k) for k, i in enumerate(info) if i['left_err'] > 0.5))
            parts.append(f'hands {he:.2f}/{le:.2f}')
        # the wrists against the hold's (wrist_of; the spin's left arm is the hold's own: not graded), the blade on
        # its line (the soft wrist limit must not leave it off), the elbows (printed only)
        wr = {arm: [wrist_of(S, Pk, hold, arm[1], arm[2]) for Pk in P] for arm in (R_ARM, L_ARM)}
        wb = {arm: (max(b for b, _ in v), max(t for _, t in v)) for arm, v in wr.items()}
        graded = (R_ARM,) if tag == 'spin' else (R_ARM, L_ARM)
        if any(wb[a][0] > WRIST_BEND + 5 or wb[a][1] > WRIST_TWIST + 5 for a in graded): fails.append('wrist')
        parts.append('wrist R %.0f/%.0f L %.0f/%.0f%s' % (wb[R_ARM] + wb[L_ARM] + (' (L not graded)' if tag == 'spin' else '',)))
        be = max(i['blade_err'] for i in info)
        if be > 5.0: fails.append('blade ' + ','.join(str(k) for k, i in enumerate(info) if i['blade_err'] > 5.0))
        parts.append(f'blade {be:.1f}')
        def elb(Pk, arm):
            Wk = S.world(Pk); u = pos(Wk, arm[1]) - pos(Wk, arm[0]); w = pos(Wk, arm[2]) - pos(Wk, arm[1])
            return math.degrees(math.acos(np.clip(u @ w / np.linalg.norm(u) / np.linalg.norm(w), -1, 1)))
        el = {arm: [elb(Pk, arm) for Pk in P] for arm in graded}
        parts.append('elbow ' + ' '.join(f'{nm} {min(el[a]):.0f}/{max(el[a]):.0f}' for nm, a in (('R', R_ARM), ('L', L_ARM)) if a in el))
        # ends
        first = hold_T if tag not in CHAIN else [[t[CHAIN[tag][1]]] for t in by[CHAIN[tag][0]]['T']]
        e0 = max(abs(t[0] - h[0]) for t, h in zip(T, first)); e1 = max(abs(t[-1] - h[0]) for t, h in zip(T, hold_T))
        if e0 or e1: fails.append('ends')
        parts.append(f'ends {e0:.1f}/{e1:.1f}')
        # the strike
        a0, a1 = STRIKE[tag]; cut = mv[2]
        tips = np.array([i['tip'] for i in info])
        sp = np.linalg.norm(np.diff(tips, axis=0), axis=1) * KEYS_PER_S          # segment j: key j -> j + 1
        seg = list(range(a0, a1)); v = sp[seg]; jm = int(np.argmax(v))
        uni = all(v[j] < v[j + 1] for j in range(jm)) and all(v[j] > v[j + 1] for j in range(jm, len(v) - 1))
        at = seg[jm] + 0.5
        bl = np.array([i['blade'] for i in info])
        turn = [math.degrees(math.acos(np.clip(bl[k] @ bl[k + 1], -1, 1))) for k in range(n - 1)]
        X = tips[a0:a1 + 1]; sv = np.linalg.svd(X - X.mean(0), compute_uv=False); off = sv[2] / math.sqrt(len(X))
        if not uni: fails.append('speed not one maximum')
        if abs(at - cut) > 1: fails.append(f'fastest at {at}')
        if max(turn) > BLADE_TURN: fails.append('blade turn')
        if off > OFF_PLANE.get(tag, 3.0): fails.append('off plane')
        parts.append(f'fastest {at} ({max(v):.0f}/s){"" if uni else " not unimodal"}, blade turn {max(turn):.0f}, off plane {off:.2f}')
        # joints
        js = max(wrapd(P[k + 1][b][s], P[k][b][s]) for k in range(n - 1) for b in range(1, 18) for s in range(3))
        if js > JOINT_STEP: fails.append('joint step')
        parts.append(f'joint step {js:.0f}')
        # feet
        dr = ht = 0.0; rc = 0.0
        for k, i in enumerate(info):
            apart = i['crouch'] > 0 or not all(l['planted'] for l in i['legs'].values())
            for leg, l in i['legs'].items():
                if not l['planted']: continue
                if l['place'] is not None: dr = max(dr, float(np.linalg.norm(l['ankle'] - l['place'])))
                ht = max(ht, abs(float(l['ankle'][2] - li[leg]['ankle'][2])))
                if apart: rc = max(rc, l['reach'])
        if dr > 1.0: fails.append('foot drift')
        if rc > REACH: fails.append('reach')
        if ht > 0.5: fails.append('ankle height')
        parts.append(f'feet drift {dr:.2f} height {ht:.2f} reach {rc:.3f}')
        if tag == 'spin':   # the hop's peak: both feet off the floor at the air window's middle
            mid = sum(HOP_AIR) / 2
            hp = min(float(info[k]['legs'][leg]['ankle'][2] - li[leg]['ankle'][2])
                     for k in sorted({math.floor(mid), math.ceil(mid)}) for leg in (R_LEG, L_LEG))
            if hp < HOP_FEET - 1.0: fails.append('hop')
            parts.append(f'hop {hp:.2f}')
        # clearance
        mg, tz = 1e9, 1e9
        for k, Pk in enumerate(P):
            W = fk(S, Pk, hold)
            mg = min(mg, outside(np.r_[saber_model.GRIP[None, :], pts], W, boxes, 6), outside(lh[0][None, :], W, boxes, 3))
            tz = min(tz, float(info[k]['tip'][2] - floor))
        if mg < MARGIN: fails.append('clearance ' + ','.join(str(k) for k, Pk in enumerate(P) if min(
            outside(np.r_[saber_model.GRIP[None, :], pts], fk(S, Pk, hold), boxes, 6),
            outside(lh[0][None, :], fk(S, Pk, hold), boxes, 3)) < MARGIN))
        if tz <= 0: fails.append('tip below floor')
        lc = '/'.join(f'{lean_of(S, P[k]):.1f}' for k in sorted({math.floor(cut), math.ceil(cut)}))
        parts.append(f'clearance {mg:.2f}, tip above floor {tz:.1f}, lean at the cut {lc} (hold {lean_of(S, hold):.1f})')
        # the spin's pelvis
        if tag == 'spin':
            s0, s1, deg = SPIN; prof, got = [], []
            for k, Pk in enumerate(P):
                R = np.linalg.inv(f0) @ unit3(S.world(Pk)[17][:3, :3])
                fw = FWD @ R; ang = math.degrees(math.atan2(fw @ RIGHT, fw @ FWD))      # + toward his right
                got.append(ang); prof.append(deg * ease(min(1.0, max(0.0, (k - s0) / (s1 - s0)))))
            # unwrap against the profile's direction (+ to his left = his forward turning toward -RIGHT); the profile's
            # sign decides the monotonic test too: increasing for a turn to his left, decreasing for one to his right
            un = [0.0]
            for k in range(1, n): un.append(un[-1] + (((-got[k]) - (-got[k - 1]) + 180) % 360 - 180))
            if abs(prof[-1] - un[-1]) > 180: un = [-x for x in un]
            pe = max(abs(un[k] - prof[k]) for k in range(n)); mono = all((un[k + 1] - un[k]) * math.copysign(1, deg) >= -1e-6 for k in range(n - 1))
            if pe > 1.0: fails.append('pelvis profile')
            if not mono: fails.append('pelvis not monotonic')
            parts.append(f'pelvis {pe:.2f} off its profile{"" if mono else ", not monotonic"}')
        ok_all &= not fails
        print(f'{tag}: {"PASS" if not fails else "FAIL (" + ", ".join(fails) + ")"}: ' + ', '.join(parts))
        if '--keys' in sys.argv:
            print('     tip speed per key', ' '.join(f'{x:.0f}' for x in sp))
            print('     blade turn / key ', ' '.join(f'{x:.0f}' for x in turn))
            print('     left fist error  ', ' '.join(f'{i["left_err"]:.2f}' for i in info))
            print('     lean per key     ', ' '.join(f'{lean_of(S, Pk):.1f}' for Pk in P))
            print('     wrist R b/t      ', ' '.join('%.0f/%.0f' % x for x in wr[R_ARM]))
            print('     wrist L b/t      ', ' '.join('%.0f/%.0f' % x for x in wr[L_ARM]))
            print('     reach r / l      ', ' '.join(f'{i["legs"][R_LEG]["reach"]:.3f}/{i["legs"][L_LEG]["reach"]:.3f}' for i in info))
    return ok_all, built


def sheet(r, img, moves, out, per_row=12):
    """Every key of the four moves, each from in front and from his right side (his place moved forward by the step
    done, so a planted foot stays put; the Look's mesh boxes grey, the bones dark, the right fist red, the left blue, the
    hilt black, the blade green, the floor line)."""
    from PIL import Image, ImageDraw
    S, _, _ = load(r); hold = hold_pose(r, S); lh = left_hold(S); a = saber_model.AXIS / np.linalg.norm(saber_model.AXIS)
    boxes = {d: b for d, b in body_boxes(img, bones=range(19)).items() if b[0][0] < 1e8}
    floor = floor_line(S, hold, img)
    V, Hh, sc = 150, 190, 1.45
    rows = sum((m['n'] + per_row - 1) // per_row for m in moves)
    im = Image.new('RGB', (2 * V * per_row, Hh * rows + 20 * len(moves)), 'white'); d = ImageDraw.Draw(im)
    y = 0
    for m in moves:
        d.text((5, y + 3), m.get('title') or f"{m['tag'].strip()}: {m['n']} keys, cut {m['cut'] * KEYS_PER_S:g}, link "
               f"{m['link'] * KEYS_PER_S:g} (front / his right side per key)", fill='black'); y += 20
        for k, P in enumerate(m['poses']):
            W = fk(S, P, hold); sh = FWD * m['info'][k]['d']
            cx, cy = 2 * V * (k % per_row), y + Hh * (k // per_row)
            for view in range(2):
                def pt(p):
                    p = p + sh
                    h, v = ((p[0], p[2]), (-p[1] - 10, p[2]))[view]
                    return (cx + V * view + V / 2 + h * sc, cy + Hh * 0.62 - v * sc)
                for b, (lo, hi) in boxes.items():
                    c = np.array([[(lo, hi)[i >> j & 1][j] for j in range(3)] for i in range(8)])
                    q = (np.c_[c, np.ones(8)] @ W[b])[:, :3]
                    for e0 in range(8):
                        for j in range(3):
                            if not e0 >> j & 1: d.line([pt(q[e0]), pt(q[e0 | 1 << j])], fill=(215, 215, 215))
                d.line([pt(np.array([60.0, 60.0, floor]) * (1, 1, 1) - sh), pt(np.array([-60.0, -60.0, floor]) - sh)]
                       if view else [pt(np.array([60.0, 0, floor]) - sh), pt(np.array([-60.0, 0, floor]) - sh)], fill=(150, 110, 60))
                for ch, pa in skel.PARENT.items():
                    if pa != 18: d.line([pt(pos(W, ch)), pt(pos(W, pa))], fill=(80, 80, 80), width=2)
                g = saber_model.GRIP
                d.line([pt(pos(W, 6, g + a * saber_model.HILT_FRONT)), pt(pos(W, 6, saber_model.tip_point()[0]))],
                       fill=(40, 200, 60), width=3)
                d.line([pt(pos(W, 6, g - a * saber_model.HILT_BACK)), pt(pos(W, 6, g + a * saber_model.HILT_FRONT))],
                       fill=(20, 20, 20), width=4)
                for p, c in ((pos(W, 6, g), (220, 30, 30)), (pos(W, 3, lh[0]), (30, 60, 230))):
                    x, yy = pt(p); d.ellipse([x - 3, yy - 3, x + 3, yy + 3], outline=c, width=2)
                if m.get('marks') is not None:   # a target (the parry grid's node), a red cross
                    x, yy = pt(m['marks'][k])
                    d.line([x - 5, yy - 5, x + 5, yy + 5], fill=(230, 0, 0), width=2)
                    d.line([x - 5, yy + 5, x + 5, yy - 5], fill=(230, 0, 0), width=2)
            d.rectangle([cx, cy, cx + 2 * V - 1, cy + Hh - 1], outline=(235, 235, 235))
            d.text((cx + 4, cy + 4), f'{k}', fill=(200, 0, 0) if abs(k - m['cut'] * KEYS_PER_S) < 0.6 else 'black')
        y += Hh * ((m['n'] + per_row - 1) // per_row)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out); print('wrote', out)


if __name__ == '__main__':
    import paths
    from ram import Ram
    if '--grid' in sys.argv:
        grid(tuple(sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--skip')); sys.exit()
    if '--grid-block' in sys.argv:
        grid_block(sys.argv[sys.argv.index('--grid-block') + 1]); sys.exit()
    r = Ram(os.path.join(paths.GAME, 'palace.bin'))
    img = open(os.path.join(paths.GAME, 'guard.bin'), 'rb').read()
    ok = True
    if '--swing' in sys.argv:
        ok, moves = swing_check(r, img)
        mask = load(r)[2]
    else:
        moves, mask = build(r)
    print('mask', list(mask), 'tracks', sum(bin(m).count('1') for m in mask))
    if '--arm' in sys.argv:
        arm_check(r, img)
    pok = True
    lay = lambda a, fd: '%s_fd%g%s' % (os.path.splitext(a)[0], fd, os.path.splitext(a)[1])   # one file per layer
    if '--parry' in sys.argv:
        c, mx = parry_ctx(r, img), []
        for fd in FD:   # both layers, the nearest first
            print(f'layer fd {fd:g}:')
            ok1, parries, meet = parry_check(r, img, c=c, plane=fd); pok &= ok1; mx.append(meet.max())
            if '--err' in sys.argv: parry_err_map(meet, lay(sys.argv[sys.argv.index('--err') + 1], fd))
            if '--sheet' in sys.argv:
                sheet(r, img, parry_sheet_moves(r, parries, plane=fd), lay(sys.argv[sys.argv.index('--sheet') + 1], fd),
                      per_row=len(SD))
        print(f"meet max over the layers {max(mx):.3f} (t_saber.py's BLADE_MAX: it + 0.25)")
    elif '--sheet' in sys.argv:
        sheet(r, img, moves, sys.argv[sys.argv.index('--sheet') + 1])
    if '--swing' in sys.argv or '--parry' in sys.argv: sys.exit(0 if ok and pok else 1)
