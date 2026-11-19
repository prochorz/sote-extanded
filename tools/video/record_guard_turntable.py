#!/usr/bin/env python3
"""Turntable takes for comparing the real red palace guard with Dash in the Look: Guard (cheats Look row, guard.c).

    cd harness && PAYLOAD_BUILD=../local/build/guard RES=960x720 SHOTS=<dir> M64CPU=0 \\
        python3 ../tools/video/record_guard_turntable.py <rom> <out.json> real|dash|luke|guri [VIs]

From palace.st (sub-level 26, its held radio line let go). The camera is the creature camera on a droid (Trop 1, its
model hidden: its root node's child count 0) held at CAM facing +y; the subject stands DIST ahead of it and turns
once round in VIs (default 360) frames: `real` the red guard (Trop 0: position +0x08 / +0x50, heading +0x14, rows
+0x20 / +0x30 written each frame), `dash` Dash with g_guard_on 1 (position, heading +0x14), `luke` the same with
g_guard_on 2 (Luke's head instead of the helmet; at the end `luke: ...` prints Dash's head bone list against the
image's LUKE list). The other one is parked
behind the camera. A shot every 2nd VI; JSON {t, angle}. Heading h faces (-sin h, cos h) (Dash, measured).
MOVE=1: in motion: the guard walks (its AI state +0x78 held at 2, its place held), Dash runs (stick up, his place held, the
run's descriptor written into his animation controller: held, the game took him for blocked and stalled). With the
patch the Creature Cam row takes the stick while a creature is followed, so MOVE runs the stock ROM (no inject) and
puts local/game/guard.bin at 0x80548000 and onto Dash's `trot` bone nodes as guard.c does (the weapon last).
`guri`: the red guard (Trop 0) dressed as Guri on the stock ROM (no inject): the image GURI_BIN (default
local/game/guri.bin, harness/guri/guri_asset.py) written at 0x80580000 and each of Trop 0's 17 bone nodes given the
list "its bone children + the image's meshes for that bone" (its own meshes, the rifle too, left out). Its bones: the
tree from Dfob (+0x70) +0x84, its bone nodes (w0 >> 28 == 0xD) depth first in child-list order; trSt index i is
node 18 - i (the first two are the root and its one child). Otherwise as `real` (MOVE=1 walks).
GURI_PATCH=1 (with `guri`): the patch's own way instead: the build (PAYLOAD_BUILD; <rom> its sote-patch.z64) injected
and g_guri_trop set to Trop 0 (guri.c dresses it); at the end it prints `guri: ...` with Trop 0's pelvis list (ours:
the image's meshes in it) and how many other Trops' bone lists changed over the take (0: the other guards keep their
look; Trop 1, the camera's droid, left out: its model is hidden).
CAM_DZ=z: the camera's droid moved up (+) or down (-) by z (a closer DIST with the whole figure in the frame).
SETTLE=n: VIs before the turn (default 150). STILLS=n: only n shots, evenly round the turn (e.g. 12 for a still every 30 degrees).
`pair` (patch build injected): two figures side by side for a size comparison, no turn. Dash (stand, key 0 of his idle)
at SEP / 2 left of the camera's line, Trop 0 dressed as Guri (g_guri_trop) SEP / 2 right of it, both DIST ahead (the
same depth: the same floor row on screen), both at each heading of VIEWS (default "90,0": side, front). Per view a still
with g_guard_on 2 (Luke; LOOK=1: Guard) and one with 0 (Dash's own look); last an empty one (both parked: the background for a mask),
each WAIT VIs (default 60) after the change; with each shot the RDRAM (<out>_<i>.ram, little-endian words) and in the
JSON {i, view, look, kind, eye, R, F, U (the game camera's rows), h, g (positions), floor (Humn +0x10)}.
"""
import json, math, os, sys
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths, struct
import m64
from m64 import Emu
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
OUT, WHO = os.path.abspath(sys.argv[2]), sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 360
CAM = (-73.5, -101.0, 5.0)              # the red guard's own spot in the hall: open floor along +y
CAM_H = float(os.environ.get('CAM_H', 0))     # the droid's heading: a Trop at 0 faces +y (the Creature Cam take)
DIST = float(os.environ.get('DIST', 8.0))
CAM_DZ = float(os.environ.get('CAM_DZ', 0))  # the droid (so the camera) this far up or down; the subject stays on the floor
MOVE = bool(os.environ.get('MOVE'))
ANIM_CTL, RUN_DESC = 0x800E1328, int(os.environ.get('RUN_DESC', '0x800e0fc8'), 16)   # Dash's controller, the run (free run, palace.st)
SETTLE = int(os.environ.get('SETTLE', 150))   # VIs for the creature camera to ease onto the droid before the turn
HOLD, HOLD_T = 0x800DD2D0, 0x800D07FC
GURI = WHO == 'guri'
GURI_PATCH = GURI and bool(os.environ.get('GURI_PATCH'))
GURI_RAM, GURI_BIN = 0x80580000, os.environ.get('GURI_BIN') or os.path.join(paths.GAME, 'guri.bin')
STILLS = int(os.environ.get('STILLS', 0))
PAIR = WHO == 'pair'
SEP = float(os.environ.get('SEP', 3.0))
VIEWS = [float(v) for v in os.environ.get('VIEWS', '90,0').split(',')]
WAIT = int(os.environ.get('WAIT', 60))
PAIR_LOOK = int(os.environ.get('LOOK', 2))   # `pair`: the Look the 'luke' stills use (1 Guard, 2 Luke)
log, st = [], {}


def objs():
    p, out = e.r32(0x80112830), {}
    for i in range(80):
        r = e.r32(p + 4 * i)
        if not r: break
        out[e.r32(r)] = r
    humn = e.r32(out[0x48756D6E] + 0x10); pool = e.r32(out[0x54726F70] + 0x10)
    return humn, pool, pool + 0x120              # Dash, Trop 0 (the red guard), Trop 1 (the camera's droid)


def put(o, p, h, rows):
    for a in range(3): e.wf(o + 0x08 + 4 * a, p[a]); e.wf(o + 0x50 + 4 * a, p[a])
    e.wf(o + 0x14, h)
    if rows:
        c, s = math.cos(math.radians(h)), math.sin(math.radians(h))
        for a, v in enumerate((c, s, 0)): e.wf(o + 0x20 + 4 * a, v)
        for a, v in enumerate((-s, c, 0)): e.wf(o + 0x30 + 4 * a, v)


def hide(o):
    b = e.r32(o + 0xCC); ent, nodes = b + 0x38, []
    for i in range(40):
        nodes.append(e.r32(ent + 8)); n = e.r32(ent + 0x0C)
        if not (0x80000000 <= n < 0x80800000): break
        ent = n
    kids = {k for n in nodes for k in (e.r32(e.r32(n + 0x10) + 4 * j) for j in range(e.r32(n + 0x0C)))}
    for n in nodes:
        if n not in kids: e.w32(n + 0x0C, 0)          # the root: nothing of the droid is drawn


def install(h):
    img = open(os.path.join(paths.GAME, 'guard.bin'), 'rb').read()
    for o in range(0, len(img), 4): e.w32(0x80548000 + o, struct.unpack_from('>I', img, o)[0])
    b = e.r32(h + 0x19C)
    while e.r32(b + 0x1C) != 0x74726F74: b = e.r32(b + 0x14)
    nodes, ent = [], b + 0x38
    for i in range(19): nodes.append(e.r32(ent + 8)); ent = e.r32(ent + 0x0C)
    free = 0x80700000
    for i, nd in enumerate(nodes):
        kids = [e.r32(e.r32(nd + 0x10) + 4 * j) for j in range(e.r32(nd + 0x0C))]
        cnt, lp = struct.unpack_from('>II', img, 8 + 8 * i)
        weapon = [k for k in kids if i == 6 and e.r32(k) & 0x80]
        lst = [k for k in kids if k in nodes] + [struct.unpack_from('>I', img, lp - 0x80548000 + 4 * j)[0] for j in range(cnt)] + weapon
        for j, v in enumerate(lst): e.w32(free + 4 * j, v)
        e.w32(nd + 0x0C, len(lst)); e.w32(nd + 0x10, free); free += 4 * len(lst) + 16


def install_guri(o):
    img = open(GURI_BIN, 'rb').read()
    assert img[:4] == b'GURI' and struct.unpack_from('>I', img, 4)[0] == 17, GURI_BIN
    for a in range(0, len(img), 4): e.w32(GURI_RAM + a, struct.unpack_from('>I', img, a)[0])
    ok = lambda v: 0x80000400 <= v < 0x80800000
    tree = []
    def walk(nd):
        if not ok(nd) or e.r32(nd) >> 28 != 0xD: return
        tree.append(nd)
        for j in range(e.r32(nd + 0x0C)): walk(e.r32(e.r32(nd + 0x10) + 4 * j))
    walk(e.r32(e.r32(o + 0x70) + 0x84))
    assert len(tree) == 19, len(tree)
    bones, free = set(tree), 0x80700000
    for i in range(17):
        nd = tree[18 - i]
        kids = [e.r32(e.r32(nd + 0x10) + 4 * j) for j in range(e.r32(nd + 0x0C))]
        cnt, lp = struct.unpack_from('>II', img, 8 + 8 * i)
        lst = [k for k in kids if k in bones] + [struct.unpack_from('>I', img, lp - GURI_RAM + 4 * j)[0] for j in range(cnt)]
        for j, v in enumerate(lst): e.w32(free + 4 * j, v)
        e.w32(nd + 0x0C, len(lst)); e.w32(nd + 0x10, free); free += 4 * len(lst) + 16


def pool_trops():
    p = e.r32(0x80112830)
    rec = next(e.r32(p + 4 * i) for i in range(80) if e.r32(e.r32(p + 4 * i)) == 0x54726F70)
    return [e.r32(rec + 0x10) + j * e.r32(rec + 0x0C) for j in range(e.r32(rec + 8))]


def trop_lists(o):
    """A Trop's 19 tree nodes (trSt order: tree node 18 - i, then the root's child and the root) as (count, children), or None."""
    ok = lambda v: 0x80000400 <= v < 0x80800000
    tree = []
    def walk(nd):
        if not ok(nd) or e.r32(nd) >> 28 != 0xD or len(tree) > 19: return
        tree.append(nd)
        for j in range(min(e.r32(nd + 0x0C), 16)): walk(e.r32(e.r32(nd + 0x10) + 4 * j))
    d = e.r32(o + 0x70)
    if ok(d): walk(e.r32(d + 0x84))
    if len(tree) != 19: return None
    return [(e.r32(nd + 0x0C), tuple(e.r32(e.r32(nd + 0x10) + 4 * j) for j in range(min(e.r32(nd + 0x0C), 16))))
            for nd in reversed(tree)]


def cam_rows():
    cam = e.r32(0x800D08A4)
    return {nm: [e.rf(cam + o + 4 * i) for i in range(3)] for nm, o in (('eye', 0x44), ('R', 0x14), ('F', 0x24), ('U', 0x34))}


def pair(h, g, t):
    """The `pair` mode's frame: t VIs after the settle. Steps of WAIT VIs: per view Luke, own, empty."""
    steps = [(v, kind) for v in VIEWS for kind in ('luke', 'own')] + [(0.0, 'empty')]   # one background: a Trop parked
    # away and put back is not drawn again (so the empty still is the last)
    i, w = divmod(max(t, 0), WAIT)
    if i >= len(steps):
        json.dump(log, open(OUT, 'w')); print('frames', len(log), flush=True); e.stop(); return
    v, kind = steps[i]
    e.w32(S['g_guard_on'], PAIR_LOOK if kind == 'luke' else 0)
    park = (CAM[0] - 120, CAM[1] - 60, CAM[2])
    a, b = (CAM[0] - SEP / 2, CAM[1] + DIST, CAM[2]), (CAM[0] + SEP / 2, CAM[1] + DIST, CAM[2])
    if kind == 'empty': put(h, park, 0.0, False); put(g, (park[0] + 10, park[1], park[2]), 0.0, True)
    else: put(h, a, 180.0 + v, False); put(g, b, 180.0 + v, True)
    e.pad(0, 0, 0)
    if t >= 0 and w == WAIT - 1:
        n = len(log); e.dump(f'{os.path.splitext(OUT)[0]}_{n}.ram'); e.shot()
        log.append(dict(i=n, view=v, look=PAIR_LOOK if kind == 'luke' else 0, kind=kind, h=[e.rf(h + 8 + 4 * k) for k in range(3)],
                        g=[e.rf(g + 8 + 4 * k) for k in range(3)], floor=e.rf(h + 0x10), **cam_rows()))


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'palace.st'))
    if n == 62 and ((not MOVE and not GURI) or GURI_PATCH or PAIR): inject(e)
    if n < 66: return
    k = n - 66
    if e.r16(HOLD): e.w32(HOLD, e.r32(HOLD) & 0xFFFF); e.wf(HOLD_T, 0)
    if k == 20:
        st['h'], st['g'], st['c'] = objs(); hide(st['c'])
        p = e.r32(0x80112830); st['trop'] = next(e.r32(p + 4 * i) for i in range(80) if e.r32(e.r32(p + 4 * i)) == 0x54726F70)
        if GURI_PATCH or PAIR:
            e.w32(S['g_guri_trop'], st['g'])
            st['others'] = {o: trop_lists(o) for o in pool_trops() if o not in (st['g'], st['c'])}
        elif GURI: install_guri(st['g'])
        elif not MOVE: e.w32(S['g_guard_on'], 2 if WHO == 'luke' else 1 if WHO == 'dash' else 0)
        elif WHO == 'dash': install(st['h'])
    if k < 20: return
    h, g, c = st['h'], st['g'], st['c']
    e.wf(h + 0xB4, 100.0); e.wf(0x800E0DF0, 0.0)          # health held, no hit flash
    for j in range(e.r32(st['trop'] + 8)):                 # every Trop idle (AI state +0x78 = 0): nobody shoots
        o = e.r32(st['trop'] + 0x10) + j * 0x120
        if o not in (c,): e.w32(o + 0x78, 2 if (MOVE and WHO in ('real', 'guri') and o == g) else 0)
    run = False
    put(c, (CAM[0], CAM[1], CAM[2] + CAM_DZ), CAM_H, True)
    if MOVE: e.wf(c + 0x60, 0.0)                         # the droid's radius (3.4) 0: else the walking guard is pushed
                                                         # out of it (to 6 from it) and wanders, its place not held
    e.w32(0x800E5EF4, c); e.wf(0x800E5EF8, 5.6)
    t = k - 20 - SETTLE
    if PAIR: return pair(h, g, t)
    ang = (360.0 * t / N) % 360 if t >= 0 else 0.0
    subj = (CAM[0], CAM[1] + DIST, CAM[2]); park = (CAM[0] - 120, CAM[1] - 60, CAM[2])
    if WHO in ('real', 'guri'): put(g, subj, 180.0 + ang, True); put(h, park, 0.0, False)   # same side as Dash at each angle
    else: put(h, subj, 180.0 + ang, False); put(g, park, 0.0, True)
    e.pad(0, 0, 80 if (MOVE and WHO == 'dash') else 0)
    if MOVE and WHO == 'dash':           # held in place the game takes him for blocked and stalls the run: its descriptor
        if 'run' not in st and k == 19 + SETTLE // 2: pass
        e.w32(ANIM_CTL + 4, RUN_DESC)
    if t >= 0 and (t % max(1, N // STILLS) == 0 and t < N if STILLS else k % 2 == 0):
        e.shot(); log.append(dict(t=t // 2, angle=round(ang, 1)))
    if t >= N:
        if WHO == 'luke':
            b = e.r32(h + 0x19C)
            while e.r32(b + 0x1C) != 0x74726F74: b = e.r32(b + 0x14)
            nd = e.r32(b + 0x38 + 0xA0 + 8)                  # bone 1, the head
            kids = [e.r32(e.r32(nd + 0x10) + 4 * j) for j in range(e.r32(nd + 0x0C))]
            L = 0x80548000 + 8 + 8 * 19
            luke = [e.r32(e.r32(L + 8) + 4 * j) for j in range(e.r32(L + 4))] if e.r32(L) == 0x4C554B45 else []
            print(f"luke: g_guard_on {e.r32(S['g_guard_on'])}; head bone list {[hex(x) for x in kids]}; LUKE "
                  f"{[hex(x) for x in luke]}: {'in it' if luke and all(x in kids for x in luke) else 'NOT in it'}", flush=True)
        if GURI_PATCH:
            pel = trop_lists(g)
            changed = sum(1 for o, ls in st['others'].items() if trop_lists(o) != ls)
            print(f"guri: g_guri_trop {e.r32(S['g_guri_trop']):08x} (Trop 0 {g:08x}); pelvis list "
                  f"{[hex(x) for x in pel[15][1]] if pel else None}; other Trops {len(st['others'])}, lists changed "
                  f"{changed}", flush=True)
        json.dump(log, open(OUT, 'w')); print('frames', len(log), flush=True); e.stop()


e.run(script)
