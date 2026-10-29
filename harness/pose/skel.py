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
    def __init__(s, dump, block):
        r = Ram(dump); s.t = {}; s.has = {}; s.scale = None; s.root_t = None
        for i in range(19):
            e = block + 0x38 + 0xA0 * i; n = r.u32(e + 8)
            s.t[i] = np.array([r.f(n + 0x38 + 4*k) for k in range(3)])
            s.has[i] = [0x80000000 <= r.u32(e + o) < 0x80800000 for o in SLOTS]
            if i == 18: s.M18 = np.array([[r.f(n+0x14+4*(3*a+b)) for b in range(3)] for a in range(3)])
            if i == 18: s.t18 = s.t[i]
    def world(s, pose):
        """pose: {bone: [6 values or None]} -> world 4x4 per bone (model space, row vectors)."""
        W = {}
        def get(i):
            if i in W: return W[i]
            p = pose.get(i, [None]*6)
            if i == 18: Rm, t = s.M18, s.t18.copy()
            elif i == 0: Rm, t = np.eye(3), np.array([v or 0 for v in p[3:6]])
            else:
                Rm = rot([v or 0.0 for v in p[0:3]]); t = s.t[i]
            L = np.eye(4); L[:3,:3] = Rm; L[3,:3] = t
            W[i] = L @ get(PARENT[i]) if i in PARENT else L
            return W[i]
        for i in range(19): get(i)
        return W
def pos(W, i, local=(0,0,0)): return (np.array([*local, 1.0]) @ W[i])[:3]
