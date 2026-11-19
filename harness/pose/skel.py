"""Dash's skeleton: bone hierarchy, angle convention (z, x, y), forward kinematics."""
import numpy as np, math
from ram import Ram
NAMES = {0:'root',1:'head',2:'neck',3:'lhand',4:'lfore',5:'lshoul',6:'rhand',7:'rfore',8:'rshoul',9:'chest',10:'spine',11:'foot2',12:'shin2',13:'thigh2',14:'foot1',15:'shin1',16:'thigh1',17:'pelvis',18:'model'}
PARENT = {17:18, 16:17, 15:16, 14:15, 13:17, 12:13, 11:12, 10:17, 9:10, 8:9, 7:8, 6:7, 5:9, 4:5, 3:4, 2:9, 1:2}
SLOTS = (0x70, 0x74, 0x78, 0x88, 0x8C, 0x90)
def R(ax, d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    if ax == 0: return np.array([[1,0,0],[0,c,-s],[0,s,c]])
    if ax == 1: return np.array([[c,0,s],[0,1,0],[-s,0,c]])
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])
def rot(a):   # angles (z, x, y) -> node matrix (row-vector convention)
    return (R(2, a[0]) @ R(0, a[1]) @ R(1, a[2])).T
class Skel:
    """rests=False (the ledge tools' tables were made so): every bone's rotation is rot(angles), the model bone (18)
    the dump's posed node. rests=True (the game's FK, 0x80016E28): every bone's is its bone header's rest 3x3 x
    rot(angles), the model bone's too (its rest a 2.906 scale, its angles the pose's), so the pelvis's 0.952 rest scale
    shrinks everything below it as the game draws it; `rest` holds the 3x3s (set_world / turn invert them)."""
    def __init__(s, dump, block, rests=False):
        r = Ram(dump); s.t = {}; s.has = {}; s.scale = None; s.root_t = None; s.rests = rests
        for i in range(19):
            e = block + 0x38 + 0xA0 * i; n = r.u32(e + 8)
            s.t[i] = np.array([r.f(n + 0x38 + 4*k) for k in range(3)])
            s.has[i] = [0x80000000 <= r.u32(e + o) < 0x80800000 for o in SLOTS]
            if i == 18: s.M18 = np.array([[r.f(n+0x14+4*(3*a+b)) for b in range(3)] for a in range(3)])
            if i == 18: s.t18 = s.t[i]
        if rests:
            s.rest = {}
            for i in range(19):
                h = r.u32(block + 0x38 + 0xA0 * i)
                s.rest[i] = np.array([[r.f(h + 4 + 4 * (4 * a + b)) for b in range(3)] for a in range(3)])
    def world(s, pose):
        """pose: {bone: [6 values or None]} -> world 4x4 per bone (model space, row vectors)."""
        W = {}
        def get(i):
            if i in W: return W[i]
            p = pose.get(i, [None]*6)
            if i == 18 and s.rests: Rm, t = s.rest[18] @ rot([v or 0.0 for v in p[0:3]]), s.t18.copy()
            elif i == 18: Rm, t = s.M18, s.t18.copy()
            elif i == 0: Rm, t = np.eye(3), np.array([v or 0 for v in p[3:6]])
            else:
                Rm = rot([v or 0.0 for v in p[0:3]]); t = s.t[i]
                if s.rests: Rm = s.rest[i] @ Rm
            L = np.eye(4); L[:3,:3] = Rm; L[3,:3] = t
            W[i] = L @ get(PARENT[i]) if i in PARENT else L
            return W[i]
        for i in range(19): get(i)
        return W
def pos(W, i, local=(0,0,0)): return (np.array([*local, 1.0]) @ W[i])[:3]
DASH_ARMS = {'l': (5, 4, 3), 'r': (8, 7, 6)}          # shoulder, forearm, hand
DASH_LEGS = {'l': (16, 15, 14), 'r': (13, 12, 11)}    # thigh, shin, foot (thigh1's foot is on the left hand's side)
Skel.ARMS, Skel.LEGS, Skel.NAMES, Skel.PARENT, Skel.N = DASH_ARMS, DASH_LEGS, NAMES, PARENT, 19

# ---- The palace guard's skeleton (17 bones, in its trSt block's order) ----
GUARD_NAMES = {16:'root', 15:'pelvis', 14:'spine', 13:'chest', 12:'rshoul', 11:'rfore', 10:'rhand', 9:'lshoul',
               8:'lfore', 7:'lhand', 6:'head', 5:'rthigh', 4:'rshin', 3:'rfoot', 2:'lthigh', 1:'lshin', 0:'lfoot'}
GUARD_PARENT = {15:16, 14:15, 13:14, 12:13, 11:12, 10:11, 9:13, 8:9, 7:8, 6:13, 5:15, 4:5, 3:4, 2:15, 1:2, 0:1}
GUARD_ARMS = {'l': (9, 8, 7), 'r': (12, 11, 10)}       # right = the model's -x side (the rifle hand)
GUARD_LEGS = {'l': (2, 1, 0), 'r': (5, 4, 3)}

def objects(r):
    """The game's object class records by tag (from a Ram)."""
    p, out = r.u32(0x80112830), {}
    for i in range(80):
        x = r.u32(p + 4 * i)
        if not x: break
        out[r.tag(x)] = x
    return out
def chain_block(r, first, tag):
    """The block with this tag in an animation chain (instance +0x00 -> header, +0x14 next)."""
    b = first
    while b:
        if r.tag(r.u32(b)) == tag: return b
        b = r.u32(b + 0x14)
def bone_values(r, block, k, n):
    """Key k of every bone of a block as [3 angles + 3 translations], the way the game samples it (0x80016824):
    a track if the header's flag (0x01 rotations, 0x02 translations) is set and the track is not null, else the
    header's constant."""
    P, ent = {}, block + 0x38
    for i in range(n):
        hd = r.u32(ent); fl = (r.u32(hd) >> 16) & 0xFF; row = []
        for base, cst, bit in ((0x48, 0x54, 0x01), (0x60, 0x6C, 0x02)):
            for a in range(3):
                t = r.u32(hd + base + 4 * a)
                row.append(r.f(t + 4 * k) if (fl & bit) and 0x80000000 <= t < 0x80800000 else r.f(hd + cst + 4 * a))
        P[i] = row; ent = r.u32(ent + 0x0C)
    return P

class GuardSkel:
    """The palace guard's skeleton from a RAM dump (Trop `trop`'s own trSt block and bone tree). Model frame: world
    units, the Trop's own axes (forward -y, up +z, origin at the Trop's position on the floor).
    A node = the bone header's rest matrix (+0x04) with its translation row + the sampled translation x the
    instance's factor (+0x0C, 4.0), times rot(angles) (0x80016E28; rest x rot on every bone, the root's rest is a
    0.2 scale). Above the root: the tree's second node (a 0.25 scale) then the Trop's placement (not in the model
    frame). The root's translation is root motion: the game moves the Trop by the change of its sampled x, y
    (1 world unit per unit) and leaves the node's x, y 0; its z (x factor x 0.25) is the height in world units. So
    here the root's x, y are taken as a displacement of the whole figure in the model frame, 1:1."""
    ARMS, LEGS, NAMES, PARENT, N = GUARD_ARMS, GUARD_LEGS, GUARD_NAMES, GUARD_PARENT, 17
    def __init__(s, dump, trop):
        r = Ram(dump); s.r = r
        s.block = chain_block(r, r.u32(trop + 0xC8), 'trSt')
        s.factor = r.f(s.block + 0x0C)
        s.hdr, s.rest, s.node = {}, {}, {}
        ent = s.block + 0x38
        for i in range(17):
            s.hdr[i] = r.u32(ent); s.node[i] = r.u32(ent + 8)
            s.rest[i] = np.array([[r.f(s.hdr[i] + 4 + 4 * (4 * a + b)) for b in range(4)] for a in range(4)])
            ent = r.u32(ent + 0x0C)
        tree, par = [], {}
        def walk(nd, pa):
            if not (0x80000400 <= nd < 0x80800000) or r.u32(nd) >> 28 != 0xD: return
            tree.append(nd); par[nd] = pa
            for j in range(r.u32(nd + 0x0C)): walk(r.u32(r.u32(nd + 0x10) + 4 * j), nd)
        walk(r.u32(r.u32(trop + 0x70) + 0x84), None)
        assert len(tree) == 19 and all(tree[18 - i] == s.node[i] for i in range(17)), 'tree rule: trSt bone i = node 18 - i'
        idx = {tree[18 - i]: i for i in range(17)}
        assert {i: idx[par[s.node[i]]] for i in range(16)} == GUARD_PARENT, 'guard bone parents'
        s.top = np.eye(4); s.top[:3, :3] = np.array([[r.f(tree[1] + 0x14 + 4 * (3 * a + b)) for b in range(3)] for a in range(3)])
    def local(s, i, p):
        L = s.rest[i].copy()
        L[3, :3] += np.array(p[3:6]) * s.factor
        if i == 16: L[3, :2] = 0.0
        L[:3, :3] = L[:3, :3] @ rot(p[0:3])
        return L
    def world(s, pose):
        """pose: {bone: [3 angles, 3 translations]} (every bone) -> model-frame 4x4 per bone (row vectors)."""
        W = {}
        def get(i):
            if i in W: return W[i]
            if i == 16:
                M = s.local(16, pose[16]) @ s.top
                M[3, :2] += pose[16][3:5]
            else: M = s.local(i, pose[i]) @ get(GUARD_PARENT[i])
            W[i] = M; return M
        for i in range(17): get(i)
        return W
