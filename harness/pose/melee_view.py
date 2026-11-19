"""Preview the melee blocks (melee.py) in RAM on the stock ROM: palace.st, Guri on Trop 0 in her model, Dash beside her.

    cd harness && M64CPU=0 .venv/bin/python3 pose/melee_view.py --check [--flat]
    cd harness && RES=960x720 SHOTS=<dir> M64CPU=0 .venv/bin/python3 pose/melee_view.py \\
        --stills 'guGr:0,6,11;guPu:0,3,5,7' [--views 90,45] [--sheet out.jpg]
    cd harness && RES=960x720 SHOTS=<dir> M64CPU=0 .venv/bin/python3 pose/melee_view.py \\
        --video 'guGr:1;guPu:2;guSh:1;guLf:1;guTh:1;plUp:1' [--views 90,45] [--look-dash]   (video.json + shots; played
        from melee.bin's STAG / EVNT tables, the throw flown by the game)
    cd harness && M64CPU=0 .venv/bin/python3 pose/melee_view.py --dump <out.bin>     (melee.py's DUMP)

From palace.st (its held radio line let go): the image (melee.py's, built on the fly; --flat its format check) written
at MELEE_RAM; Guri's model put on Trop 0 (local/game/guri.bin at 0x80580000, each of her 17 bone nodes given its bone
children + the image's meshes, as record_guard_turntable.py WHO=guri does); per object and block an instance, a block
header and bone instances built at INST (Trop 0's nodes in trSt order: her bone tree from Dfob +0x84, bones only
(w0 >> 28 == 0xD) depth first, trSt bone i = node 18 - i; Dash's from his trot entries), linked at the end of the
object's chain and started the way the game's play 0x80017344 cuts to a block (state: mode 1, current and blended-to
= it; instance speed and frame; each bone instance's +0x24 = -1000), here written from the harness. Every Trop held
idle (AI state +0x78 0, timer +0x80 held), so Guri's AI re-picks nothing.

--check: per block, the sampled angles (bone instances +0x10..18) at 3 keys against the table (max error, degrees),
the posed nodes against melee.py's forward kinematics (max of the 3x3 and the translation), the root motion of one
play at speed (her Trop's move along her facing against the table's), and the generator's IK and limit numbers.
--stills: per block the given keys parked (frame = key + 1, speed 0), the camera the creature camera on the droid
Trop 1 (its model hidden) CAM_DZ lower, DIST short of the pair's centre PC along the view (the turntable's close
camera); the pair placed the same for every view (HV: Guri faces world +x, the floor open 25 units that way for the
throw) and the camera turned round it: 90 side on, 45 three-quarter front, 135 three-quarter back. Dash held facing
her (his heading +0x14 and yaw +0x8C both: the game rebuilds his drawn matrix +0x208 from them; +0x14 alone is put
back from +0x8C), his place and block per her key (his_state): the grab's hold point (melee.PLAYER_AT) pulled in with
the grip, his stand or plDb on the punches (melee.reaction), plDb with the shove's push (melee.SHOVE) and parked on
melee.DB_PARK, carried by her hands through guLf and guTh (melee.carry) and turned round by guLf (melee.his_yaw),
after guTh's release plFa on a ballistic estimate; Guri moved by her block's root motion of that key.
From guLf's start to his landing (stills and video) the controller's current descriptor (CTL + 4) points at one of
ours (hold_desc, at DESC: next -1, kind 7) for plCa, then plFa: off the ground the game's own descriptor re-asks jmpF
every update and his block would not pose him.
--video and --stills draw the player in the guard look by default (guard.bin on his nodes, as in the mission's duel);
--look-dash draws Dash's own meshes.
The player's blocks are built on Dash's chain (his trot nodes) the same way. In the video see run_video.
A still of one of the player's blocks (plDb, plUp) shows Dash alone (Guri parked away), view 90 his side, 0 his front;
--guard 'plUp:16:90' adds one such still in the guard look (guard.bin on his trot nodes, the turntable's MOVE=1 install:
the stock ROM has no g_guard_on). --check also compares plUp's key 0 with plFa's last frame and its last key with SFid
in RAM (sampled angles, the placement height).
--sheet: one contact sheet of the stills (labelled).
DUMP_RAM=1 (--stills; pose.py's DUMP is the hang dump's path): the RDRAM written with each of Guri's stills, next to its shot (still_<i>_<tag>_<key>_<view>.ram).
"""
import json, math, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import numpy as np
import paths, m64
from m64 import Emu
from skel import PARENT as DPARENT

ARGS = sys.argv[1:]
def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default
DUMP_OUT = arg('--dump')
CHECK = '--check' in ARGS
FLAT = '--flat' in ARGS
STILLS = [(b.split(':')[0], [int(x) for x in b.split(':')[1].split(',')]) for b in arg('--stills', '').split(';') if b]
VIEWS = [float(v) for v in arg('--views', '90,45').split(',')]
SHEET = arg('--sheet')
GUARD = arg('--guard')                      # 'plUp:16:90': one more still, Dash in the guard look (guard.bin on his nodes)
STILL_DUMP = bool(os.environ.get('DUMP_RAM'))   # --stills: DUMP_RAM=1 also writes the RDRAM with each of Guri's stills
                                            # (<shots>/still_<i>_<tag>_<key>_<view>.ram, guri/shoulder_gap.py reads it)
VIDEO = arg('--video')                      # 'guGr:1;guPu:3': the blocks played in turn (times each), per view
LOOK_GUARD = '--look-dash' not in ARGS     # --video / --stills: the player drawn in the guard look (guard.bin on his
                                            # nodes), as he fights Guri in the mission; --look-dash: Dash's own meshes
if VIDEO: STILLS = []
if not DUMP_OUT:
    import melee
    MOVES, REPORT, ERRS = melee.build(FLAT)
    IMG = melee.image(MOVES, force=FLAT)
    assert melee.MELEE_RAM + len(IMG) <= 0x80700000, len(IMG)

HOLD, HOLD_T = 0x800DD2D0, 0x800D07FC
CAM = (-73.5, -101.0, 5.0)                  # the red guard's own spot in the hall: open floor along +y
CAM_DZ = float(os.environ.get('CAM_DZ', -2.4))
DIST = float(os.environ.get('DIST', 1.3))
GURI_RAM, GURI_BIN = 0x80580000, os.environ.get('GURI_BIN') or os.path.join(paths.GAME, 'guri.bin')   # GURI_BIN=<file>: another image
DASH_TURN = float(os.environ.get('DASH_TURN', 180.0))   # his heading = hers + this: facing her
LISTS, INST = 0x80700000, 0x80740000       # Guri's bone child lists, the block instances
GLISTS = 0x80720000                         # Dash's in the guard look (--guard)
TAGV = lambda s: int.from_bytes(s.encode(), 'big')
CTL = 0x800E1328                            # Dash's animation controller: +0 its time, +4 its current descriptor
DESC = 0x807F0000                           # our descriptors (0x24 each), past the image and the instances
DESC_ID = {'plCa': 99, 'plFa': 100}
e = Emu(paths.ROM, video=m64.GLN) if STILLS or VIDEO else Emu(paths.ROM)
st = {}


def tag(v): return struct.pack('>I', v).decode('latin1')
def objs():
    p, out = e.r32(0x80112830), {}
    for i in range(80):
        x = e.r32(p + 4 * i)
        if not x: break
        out[tag(e.r32(x))] = x
    return out
def trops():
    t = objs()['Trop']
    return [e.r32(t + 0x10) + j * e.r32(t + 0x0C) for j in range(e.r32(t + 8))]
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
        if n not in kids: e.w32(n + 0x0C, 0)
def trop_tree(o):
    ok = lambda v: 0x80000400 <= v < 0x80800000
    tree = []
    def walk(nd):
        if not ok(nd) or e.r32(nd) >> 28 != 0xD: return
        tree.append(nd)
        for j in range(e.r32(nd + 0x0C)): walk(e.r32(e.r32(nd + 0x10) + 4 * j))
    walk(e.r32(e.r32(o + 0x70) + 0x84))
    assert len(tree) == 19, len(tree)
    return tree
def install_guri(o):
    img = open(GURI_BIN, 'rb').read()
    assert img[:4] == b'GURI' and struct.unpack_from('>I', img, 4)[0] == 17, GURI_BIN
    for a in range(0, len(img), 4): e.w32(GURI_RAM + a, struct.unpack_from('>I', img, a)[0])
    tree = trop_tree(o); bones, free = set(tree), LISTS
    for i in range(17):
        nd = tree[18 - i]
        kids = [e.r32(e.r32(nd + 0x10) + 4 * j) for j in range(e.r32(nd + 0x0C))]
        cnt, lp = struct.unpack_from('>II', img, 8 + 8 * i)
        lst = [k for k in kids if k in bones] + [struct.unpack_from('>I', img, lp - GURI_RAM + 4 * j)[0] for j in range(cnt)]
        for j, v in enumerate(lst): e.w32(free + 4 * j, v)
        e.w32(nd + 0x0C, len(lst)); e.w32(nd + 0x10, free); free += 4 * len(lst) + 16
def write_image():
    for a in range(0, len(IMG), 4): e.w32(melee.MELEE_RAM + a, struct.unpack_from('>I', IMG + bytes(4), a)[0])
def image_blocks():
    n = e.r32(melee.MELEE_RAM + 4); out = []
    for j in range(n):
        a = melee.MELEE_RAM + 8 + 0x14 * j
        w1, w3 = e.r32(a + 4), e.r32(a + 12)
        out.append(dict(tag=tag(e.r32(a)), skel=w1 >> 16, keys=w1 & 0xFFFF, speed=e.rf(a + 8),
                        clamp=w3, hdrs=melee.MELEE_RAM + e.r32(a + 16)))
    return out
def image_tables():
    """The combo's tables as written in RAM (melee.py's header doc): the constants, STAG per her block {frames, loops,
    lead, rows [(ahead, left, up, yaw)]}, EVNT as a list of (her tag, loop, frame, kind, a0, a1, a2, a3)."""
    R = melee.MELEE_RAM; n = e.r32(R + 4); k = R + 8 + 0x14 * n
    K = dict(GRAB_KEY=e.rf(k + 8), PLAYER_AT=e.rf(k + 0x0C), FA_LAND=e.r32(k + 0x10), FA_SPEED=e.rf(k + 0x14),
             UP_DELAY=e.rf(k + 0x18), TH_IDLE_BLEND=e.rf(k + 0x1C), PU_BLEND=e.rf(k + 0x20), LAND_DMG=e.r32(k + 0x24))
    so, eo = R + e.r32(k), R + e.r32(k + 4); stag = {}
    assert e.r32(so) == TAGV('STAG') and e.r32(eo) == TAGV('EVNT')
    for j in range(e.r32(so + 4)):
        a = so + 8 + 0x14 * j; nf = e.r32(a + 4) >> 16; ro = R + e.r32(a + 12); nr, per = e.r32(a + 16) >> 16, e.r32(a + 16) & 0xFFFF
        stag[tag(e.r32(a))] = dict(frames=nf, loops=e.r32(a + 4) & 0xFFFF, lead=e.rf(a + 8), per=per,
                                   rows=[[e.rf(ro + 16 * f + 4 * c) for c in range(4)] for f in range(nr)])
    ev = []
    for j in range(e.r32(eo + 4)):
        a = eo + 8 + 0x1C * j; kind = e.r32(a + 4) & 0xFFFF
        ev.append((tag(e.r32(a)), e.r32(a + 4) >> 16, e.rf(a + 8), kind, tag(e.r32(a + 12)) if kind == 2 else e.r32(a + 12),
                   e.rf(a + 16), e.rf(a + 20), e.rf(a + 24)))
    return K, stag, ev
def stag_at(tg, q, wrap_):
    """STAG's row of her block tg at frame q, linear between rows (per rows a key; wrap_: a looped block)."""
    s_ = st['stag'][tg]; rows, per = s_['rows'], s_['per']; n = s_['frames']
    q = 1.0 + (q - 1.0) % (n - 1) if wrap_ else min(max(q, 1.0), float(n))
    x = (q - 1.0) * per; a = min(int(x), len(rows) - 2); u = x - a
    return [rows[a][c] + (rows[a + 1][c] - rows[a][c]) * u for c in range(4)]
EV_HOLD, EV_PLAY, EV_DMG, EV_RELEASE = 1, 2, 3, 4


def build_instance(at, b, nodes, factor):
    """The block instance (0x1C) + its header (0x1C) + one bone instance (0x28) per bone of image block b."""
    h = at + 0x1C; bi = h + 0x1C; n = len(nodes)
    for a in range(0, 0x38 + 0x28 * n, 4): e.w32(at + a, 0)
    e.w32(at, h); e.wf(at + 4, 1.0); e.wf(at + 8, b['speed']); e.wf(at + 0x0C, factor); e.w32(at + 0x10, bi)
    e.w32(h, TAGV(b['tag'])); e.wf(h + 0x0C, 1.0); e.wf(h + 0x10, float(b['keys'])); e.w32(h + 0x14, b['keys'])
    e.w32(h + 0x18, b['clamp'])
    for i, nd in enumerate(nodes):
        x = bi + 0x28 * i
        e.w32(x, b['hdrs'] + 0x78 * i); e.w32(x + 8, nd); e.w32(x + 0x0C, x + 0x28 if i < n - 1 else 0)
    return at + 0x38 + 0x28 * n
def link(state, inst):
    b = e.r32(state + 0x10)
    while e.r32(b + 0x14): b = e.r32(b + 0x14)
    e.w32(b + 0x14, inst)
def play(state, inst, frame, speed):
    """What play 0x80017344 does on a cut (how 2) to a block already in the chain."""
    x = e.r32(inst + 0x10)
    while x:
        if not e.r32(x + 8): e.w32(x + 0x24, 0xC47A0000)
        x = e.r32(x + 0x0C)
    e.wf(inst + 8, speed); e.w32(state, 1); e.w32(state + 0x14, inst); e.w32(state + 0x18, inst)
    e.wf(inst + 4, frame)
    x = e.r32(inst + 0x10)
    while x: e.w32(x + 0x24, 0xC47A0000); x = e.r32(x + 0x0C)
def play_blend(state, inst, frame, blend, speed):
    """What play 0x80017344 does on a blend (how 3): from a steady state (mode 1) mode 3 with the block as the one
    blended to, progress 0, the blend time; while blending, the block blended to so far becomes the one blended
    from. The block's speed and frame set, its bone instances' +0x24 = -1000 (0x80017274)."""
    m = e.r32(state) & 0x7FFFFFFF; cur, to = e.r32(state + 0x14), e.r32(state + 0x18)
    if inst == to: return
    x = e.r32(inst + 0x10)
    while x: e.w32(x + 0x24, 0xC47A0000); x = e.r32(x + 0x0C)
    e.wf(inst + 8, speed); e.wf(inst + 4, frame)
    if m == 3: e.w32(state + 0x14, to)
    e.w32(state, 3); e.w32(state + 0x18, inst); e.wf(state + 8, 0.0); e.wf(state + 0x0C, blend)
def hold_desc(tg, start):
    """Off the ground the game's descriptor 13 (jmpF frame 30, duration 0, next id 13) re-asks jmpF every update
    (docs/reverse-engineering.md, *Off the ground the game holds jmpF on him*): pointing the controller at a descriptor
    of ours for his block (next -1, kind 7, +0x14 and the duration +0x18 100 s; kind 7 also refuses the game's own
    lower-kind requests, the landing's included) keeps that block. Written when the controller is not on it; True then."""
    a = DESC + 0x24 * list(DESC_ID).index(tg)
    if e.r32(CTL + 4) == a: return False
    e.w32(a, DESC_ID[tg]); e.w32(a + 4, TAGV(tg)); e.wf(a + 8, float(start)); e.wf(a + 0x0C, 0.1); e.wf(a + 0x10, 0.0)
    e.wf(a + 0x14, 100.0); e.wf(a + 0x18, 100.0); e.w32(a + 0x1C, 0xFFFFFFFF); e.w32(a + 0x20, 7)
    e.w32(CTL + 4, a); e.wf(CTL, 0.0); return True
def steady(state, inst):
    """The state plays inst alone (mode 1, current and blended-to): Dash's controller can start its own blend to his
    stand, which leaves +0x14 on our block (a still then caught him on the way up to standing)."""
    return e.r32(state + 0x14) == inst and e.r32(state + 0x18) == inst and e.r32(state) & 0x7FFFFFFF == 1
def find_block(state, t):
    b = e.r32(state + 0x10)
    while b:
        if tag(e.r32(e.r32(b))) == t: return b
        b = e.r32(b + 0x14)
def sampled(inst):
    out, x = [], e.r32(inst + 0x10)
    while x: out.append([e.rf(x + 0x10 + 4 * a) for a in range(3)]); x = e.r32(x + 0x0C)
    return out
def node_world(nodes, sk):
    """The posed nodes' model-frame matrices, chained the skeleton's way."""
    def M(n):
        m = np.eye(4); m[:3, :3] = [[e.rf(n + 0x14 + 4 * (3 * a + b)) for b in range(3)] for a in range(3)]
        m[3, :3] = [e.rf(n + 0x38 + 4 * a) for a in range(3)]; return m
    W = {}
    def get(i):
        if i not in W: W[i] = M(nodes[i]) @ (get(sk.PARENT[i]) if i in sk.PARENT else sk.top)
        return W[i]
    for i in range(sk.N): get(i)
    return W
def facing(h): return np.array([-math.sin(math.radians(h)), math.cos(math.radians(h)), 0.0])


def setup(k):
    st['h'] = e.r32(objs()['Humn'] + 0x10); st['T'] = T = trops(); st['g'] = g = T[0]
    hide(T[1]); write_image(); install_guri(g)
    st['nodes'] = [trop_tree(g)[18 - i] for i in range(17)]
    trst = e.r32(g + 0xCC); factor = e.rf(trst + 0x0C)
    st['blocks'] = [b for b in image_blocks() if b['skel'] <= 1]; at = INST; st['inst'] = {}
    if VIDEO: st['K'], st['stag'], st['evnt'] = image_tables()
    hs = st['h'] + 0x18C; trot = find_block(hs, 'trot'); x = trot + 0x38; st['dnodes'] = []
    while x: st['dnodes'].append(e.r32(x + 8)); x = e.r32(x + 0x0C)
    st['dfactor'] = e.rf(trot + 0x0C); st['sfid'] = find_block(hs, 'SFid')
    for b in st['blocks']:                              # Guri's on Trop 0's chain, the player's on Dash's (trot order)
        st['inst'][b['tag']] = at
        if b['skel'] == 0: nxt = build_instance(at, b, st['nodes'], factor); link(g + 0xB8, at)
        else: nxt = build_instance(at, b, st['dnodes'], st['dfactor']); link(hs, at)
        at = (nxt + 15) & ~15
    print('blocks', [(b['tag'], b['keys'], b['speed'], '%08x' % b['clamp'], '%08x' % st['inst'].get(b['tag'], 0)) for b in st['blocks']], flush=True)


def hold_all():
    h, T = st['h'], st['T']
    e.wf(h + 0xB4, 100.0); e.wf(0x800E0DF0, 0.0)
    for o in T: e.w32(o + 0x78, 0); e.wf(o + 0x80, 100.0)


def check_plan():
    """(block, phase, key) steps: parked keys, then one play at speed."""
    out = []
    for b in st['blocks']:
        n = b['keys']
        for kk in sorted({0, n // 2, n - 1}): out.append((b, 'key', kk))
        out.append((b, 'play', None))
        if b['tag'] == 'plUp':                  # the game's own keys it starts and ends on
            out += [(b, 'ref', ('plFa', float(melee.FA_KEYS), 0)), (b, 'ref', ('SFid', 1.0, n - 1))]
    return out
def his_sampled():
    """Dash's sampled angles per trot bone (by node) from his current block's bone instances, and his placement
    node's height above his floor point (melee._ptop: palace.st's)."""
    h = st['h']; inst = e.r32(h + 0x1A0); x = e.r32(inst + 0x10); out = {}
    while x:
        nd = e.r32(x + 8)
        if nd in st['dnodes']: out[st['dnodes'].index(nd)] = [e.rf(x + 0x10 + 4 * a) for a in range(3)]
        x = e.r32(x + 0x0C)
    return out, e.rf(melee._ptop + 0x40) - e.rf(h + 0x10)


GAME_TURNS = (9, 2)        # Dash's chest and neck: the game turns them after sampling his block (palace.st: up to 0.098
                           # of the 3x3 off rest x rot with the angles exact; his own turn of the upper body)
def who(b):
    """(object, its animation state, its current-block field) of the block's skeleton: Guri's Trop 0 or Dash."""
    if b['skel'] == 0: return st['g'], st['g'] + 0xB8, st['g'] + 0xCC
    return st['h'], st['h'] + 0x18C, st['h'] + 0x1A0


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(os.path.join(paths.STATES, 'palace.st'))
    if n < 66: return
    k = n - 66
    if e.r16(HOLD): e.w32(HOLD, e.r32(HOLD) & 0xFFFF); e.wf(HOLD_T, 0)
    if DUMP_OUT:
        if k == 30: e.dump(DUMP_OUT); print('dumped', DUMP_OUT, flush=True); e.stop()
        return
    if k == 20: setup(k)
    if k < 20: return
    hold_all(); g = st['g']
    if CHECK: return run_check(k - 20)
    if VIDEO: return run_video(k - 20)
    return run_stills(k - 20)


def run_check(t):
    g = st['g']
    if 'plan' not in st: st['plan'] = check_plan(); st['i'] = 0; st['t0'] = t; st['res'] = {}
    if st['i'] >= len(st['plan']): finish_check(); e.stop(); return
    b, ph, kk = st['plan'][st['i']]; inst = st['inst'][b['tag']]; f = t - st['t0']
    o, state, curf = who(b)
    m = next(m for m in MOVES if m.tag == b['tag'])
    r = st['res'].setdefault(b['tag'], dict(ang=0.0, rot=0.0, tr=0.0, keys=[]))
    if ph == 'key':
        if f == 0:
            if b['skel'] == 0: put(g, CAM, 0.0, True)
            play(state, inst, 1.0 + kk, 0.0)
        steady = e.r32(state + 0x14) == inst and e.r32(state + 0x18) == inst and e.r32(state) & 0x7FFFFFFF == 1
        if f > 0 and not steady:            # the game's own blend can cut in (Dash's controller): played again, read
            play(state, inst, 1.0 + kk, 0.0); r['recut'] = r.get('recut', 0) + 1     # once it stays steady
            st['steady'] = 0
        elif f > 0: st['steady'] = st.get('steady', 0) + 1
        if f >= 6 and (st.get('steady', 0) >= 3 or f >= 60):
            st['steady'] = 0
            if os.environ.get('VDEBUG'): print('key', b['tag'], kk, 'frame %.3f speed %.3f mode %x' % (e.rf(inst + 4), e.rf(inst + 8), e.r32(state)), flush=True)
            got = sampled(inst); want = [P[:3] for _, P in sorted(m.keys[kk].items())]
            r['ang'] = max(r['ang'], max(float(np.abs(melee.wrap(np.array(a) - w)).max()) for a, w in zip(got, want)))
            if b['skel'] == 0:
                W = node_world(st['nodes'], melee.G)
                P = melee.copy(m.keys[kk]); P[16][3] = P[16][4] = 0.0
                F = melee.G.world(P)
                r['rot'] = max(r['rot'], max(float(np.abs(W[i][:3, :3] - F[i][:3, :3]).max()) for i in range(17)))
                r['tr'] = max(r['tr'], max(float(np.abs(W[i][3, :3] - F[i][3, :3]).max()) for i in range(17)))
            else:                                       # Dash: each posed node against rest x rot(table) (local)
                for i, nd in enumerate(st['dnodes']):
                    hd = b['hdrs'] + 0x78 * i
                    rest = np.array([[e.rf(hd + 4 + 4 * (4 * a + c)) for c in range(3)] for a in range(3)])
                    N = np.array([[e.rf(nd + 0x14 + 4 * (3 * a + c)) for c in range(3)] for a in range(3)])
                    d = float(np.abs(N - rest @ melee.rot(m.keys[kk][i][:3])).max())
                    if i in GAME_TURNS: r['game'] = max(r.get('game', 0.0), d); continue
                    if d > r['rot']: r['rot'] = d; r['worst'] = (kk, i, melee.D.NAMES[i])
            r['keys'].append(kk)
            if b['tag'] == 'plUp': r.setdefault('own', {})[kk] = his_sampled()
            st['i'] += 1; st['t0'] = t + 1
    elif ph == 'ref':
        tg, fr, kk = kk; ref_b = find_block(state, tg)
        if f == 0 or (f < 6 and (e.r32(state + 0x14) != ref_b or e.r32(state + 0x18) != ref_b or e.r32(state) & 0x7FFFFFFF != 1)):
            play(state, ref_b, fr, 0.0)
        if f == 6:
            ref, dz = his_sampled(); own, odz = r['own'][kk]
            d = max(float(np.abs(melee.wrap(np.array(own[i]) - ref[i])).max()) for i in ref)
            worst = max(ref, key=lambda i: float(np.abs(melee.wrap(np.array(own[i]) - ref[i])).max()))
            r.setdefault('refs', []).append((tg, fr, kk, d, melee.D.NAMES[worst], len(ref), dz, odz))
            st['i'] += 1; st['t0'] = t + 1
    else:
        dur = int(60 * (b['keys'] - 1) / b['speed']) + 23
        if f == 0: play(state, inst, 1.0, 0.0)
        if f == 3:
            if b['skel'] == 0: put(g, CAM, 0.0, True)
            e.wf(inst + 8, b['speed']); st['p0'] = [e.rf(o + 8 + 4 * a) for a in range(3)]
            st['cur_bad'] = 0
        elif f > 3 and e.r32(curf) != inst: st['cur_bad'] += 1
        if f == dur:
            p1 = [e.rf(o + 8 + 4 * a) for a in range(3)]
            fwd = facing(0.0)
            r['moved'] = float(np.dot(np.array(p1) - st['p0'], fwd)) if b['skel'] == 0 else 0.0
            r['side'] = float(np.linalg.norm(np.array(p1) - st['p0']))
            r['want'] = -(m.keys[-1][16][4] - m.keys[0][16][4]) if b['clamp'] and b['skel'] == 0 else 0.0
            r['frame'] = e.rf(inst + 4); r['cur_bad'] = st['cur_bad']; r['speed'] = e.rf(inst + 8)
            st['i'] += 1; st['t0'] = t + 1


def finish_check():
    ok = True
    for b in st['blocks']:
        r = st['res'].get(b['tag'])
        if not r: continue
        rp = REPORT[b['tag']]
        good = r['ang'] <= 0.01 and r['rot'] <= 1e-3 and r['tr'] <= 1e-3 and abs(r['moved'] - r['want']) <= 0.05 and all(e_ <= melee.ik_lim(mv, nm_, k_) for mv in MOVES if mv.tag == b['tag'] for nm_, k_, e_ in mv.ik) and not r['cur_bad']
        ok &= good
        print(f"{b['tag']}: {b['keys']} keys, speed {r['speed']:.1f}, {'clamp' if b['clamp'] else 'loop'}; sampled vs table at keys "
              f"{r['keys']}: max {r['ang']:.4f} deg; posed nodes vs FK{' (local, rest x rot)' if b['skel'] else ''}: rotation {r['rot']:.5f}, translation {r['tr']:.5f}; "
              f"one play: moved {r['moved']:.3f} along her facing (table {r['want']:.3f}, all {r['side']:.3f}), end frame "
              f"{r['frame']:.2f}, current lost {r['cur_bad']}{'; the chest and neck (the game turns them after the block) off by %.3f' % r['game'] if 'game' in r else ''}; IK max {rp['ik']:.3f}, feet off {rp['feet']:.3f}, "
              f"max turn {rp['jump']:.1f} (strike keys {rp['jump_s']:.1f}), bends " + ', '.join(f'{k} {a:.0f}..{c:.0f}' for k, (a, c) in rp['bend'].items())
              + ('  PASS' if good else '  FAIL'), flush=True)
    for b in st['blocks']:
        for tg, fr, kk, d, nm, nb, dz, odz in st['res'].get(b['tag'], {}).get('refs', []):
            lim = 2.0 if kk == 0 else 5.0; ok &= d <= lim
            print(f"{b['tag']} key {kk} vs {tg} frame {fr:.0f} in RAM (sampled angles of his {nb} bones): max {d:.3f} deg "
                  f"({nm}; limit {lim:.0f}); his placement node {odz:.3f} above his floor point ({tg}: {dz:.3f})"
                  + ('  PASS' if d <= lim else '  FAIL'), flush=True)
    for m in MOVES:
        if m.tag == 'plUp':
            uf = melee.up_feet(m)
            print(f"plUp (table): planted ankles move max l {uf['l'][0]:.3f} r {uf['r'][0]:.3f}, off their floor height max "
                  f"l {uf['l'][1]:.3f} r {uf['r'][1]:.3f}", flush=True)
        if getattr(m, 'hold', None):
            d = max(x[1] for x in m.hold); ok &= d <= melee.HOLD_MAX
            print(f"{m.tag} hold: her left hand vs his right shoulder's grip point (his reaction, melee.reaction) on every key "
                  f"max {d:.3f} (limit {melee.HOLD_MAX}); wrist to his shoulder node {min(x[2] for x in m.hold):.2f}.."
                  f"{max(x[2] for x in m.hold):.2f}; his head node behind her chest front min {min(x[3] for x in m.hold):.2f}; "
                  f"fist on the hit key {m.fist:+.3f} from his stomach height" + ('  PASS' if d <= melee.HOLD_MAX else '  FAIL'), flush=True)
    for m in MOVES:
        if m.tag == 'plDb':
            fp, fs = melee.feet_track(m, 'punch'), melee.feet_track(m, 'shove')
            ok &= max(fp[0], fs[0]) <= melee.STEP_MAX
            print(f"plDb step (D17, the game's blend modelled): his rear ankle from where it stood, punch max {fp[0]:.3f}, shove "
                  f"{fs[0]:.3f} (limit {melee.STEP_MAX}); the front ankle's slide on the floor {max(fp[1], fs[1]):.3f}"
                  + ('  PASS' if max(fp[0], fs[0]) <= melee.STEP_MAX else '  FAIL'), flush=True)
        if m.tag == 'guSh': print(f"guSh: her hands' midpoint on his chest front through the drive (keys {melee.SH_HIT}-{melee.SH_KEYS - 1}) "
                                  f"max {max(d for _, d in m.chest):.3f}; he goes {melee.SHOVE:.3f} back", flush=True)
        if m.tag == 'guLf':
            ok &= max(m.grip) <= melee.GRIP_MAX
            print(f"guLf last key: her left wrist {m.grip[0]:.3f} from his collar point, right {m.grip[1]:.3f} from his belt "
                  f"point (limit {melee.GRIP_MAX})" + ('  PASS' if max(m.grip) <= melee.GRIP_MAX else '  FAIL'), flush=True)
        if m.tag == 'guTh':
            ca_, fa_ = (next(x for x in MOVES if x.tag == t_) for t_ in ('plCa', 'plFa'))
            ct = [c for _, c in next(x for x in MOVES if x.tag == 'guLf').clear_turn]; cl = list(m.clear)
            good = (ca_.seam0 <= 1e-3 and fa_.seam0 <= 1e-3 and abs(ca_.level) <= melee.LEVEL_MAX and min(ct) >= melee.CA_CLEAR
                    and all(c >= melee.clear_lim('guTh', k) for k, c in enumerate(cl)) and m.grip_turn <= melee.GRIP_MAX); ok &= good
            print(f"carried (plCa): seams plCa key 0 vs plDb key {melee.DB_PARK} {ca_.seam0:.4f} deg, plFa key 0 vs plCa's last "
                  f"{fa_.seam0:.4f}; level at guLf's last key {ca_.level:.3f} (limit {melee.LEVEL_MAX}); clearance guLf's turn (keys 5-9 "
                  f"and half keys) {' '.join('%.3f' % c for c in ct)}, guTh keys 0-{melee.RELEASE_KEY}: {' '.join('%.3f' % c for c in cl)} "
                  f"(limit {melee.CA_CLEAR}, guTh key 2 {melee.CLEAR_KEY2}); grip to the release "
                  f"max {m.grip_turn:.3f} (limit {melee.GRIP_MAX})" + ('  PASS' if good else '  FAIL'), flush=True)
    if ERRS: ok = False; print('limits:', ERRS)
    print('CHECK', 'PASS' if ok else 'FAIL', flush=True)


def player_at(tg, key, tau=None):
    """His place ahead of her start: at the grab's hold, pulled in over its last keys, pushed back by a hit tau s ago."""
    if tg == 'guGr': return melee.PLAYER_AT - melee.PULL * melee.pulled(key)
    return melee.PLAYER_HELD + melee.push(tau)
# guPu keys whose reaction is plDb alone (past its blend in, before its blend out): guPu key: (plDb key, time since the hit)
STILL_DB = {k: (k - melee.PU_HIT, melee.pu_tau(k)) for k in range(melee.PU_HIT + 1, melee.PU_KEYS)
            if melee.DB_BLEND_IN <= melee.pu_tau(k) <= melee.DB_HOLD}


def her_world(i, v):
    """Guri's bone i, posed in RAM, in the world: her model frame (world units, forward -y) turned by the view angle v
    about her Trop's place."""
    W = node_world(st['nodes'], melee.G); p = W[i][3, :3]; g = st['T'][0]
    c, s_ = math.cos(math.radians(v)), math.sin(math.radians(v))
    return np.array([e.rf(g + 8) + c * p[0] - s_ * p[1], e.rf(g + 12) + s_ * p[0] + c * p[1], e.rf(g + 16) + p[2]])
def his_world(i, v):
    """Dash's bone i, posed in RAM (his nodes chained as skel.Skel does, the game's own turns of his chest and neck
    included), in the world: x melee.DASH_SCALE, + his placement node's height above his place (the model bone's z
    moves it), turned by his heading + 180 (v + 180 facing her, guLf turns him; v unused)."""
    sk = melee.D; W = {}
    def M(n):
        m = np.eye(4); m[:3, :3] = [[e.rf(n + 0x14 + 4 * (3 * a + b)) for b in range(3)] for a in range(3)]
        m[3, :3] = [e.rf(n + 0x38 + 4 * a) for a in range(3)]; return m
    def get(j):
        if j not in W: W[j] = M(st['dnodes'][j]) @ get(DPARENT[j]) if j in DPARENT else M(st['dnodes'][j])
        return W[j]
    sc, dz = melee.DASH_SCALE, his_sampled()[1]; p = get(i)[3, :3] * sc; h = st['h']; hd = e.rf(h + 0x14)
    c, s_ = math.cos(math.radians(hd + 180)), math.sin(math.radians(hd + 180))
    return np.array([e.rf(h + 8) + c * p[0] - s_ * p[1], e.rf(h + 12) + s_ * p[0] + c * p[1], e.rf(h + 16) + p[2] + dz])


HV = 90.0          # the pair's own turn: Guri always faces world +x (the open floor the throw needs: 25 units clear
                   # east of the pair, a wall 19 south); a view angle turns the camera round the pair instead
PC = np.array([CAM[0], CAM[1] + DIST, CAM[2]])          # the pair's centre: the camera's look point
def cam_put(v, look=None, extra=0.0, dz=0.0):
    """The camera's droid for view v (90 side on, 45 three-quarter front, 135 three-quarter back): DIST + extra short
    of the look point (default the pair's centre) along the view, its heading the view (the creature camera follows
    it from behind), CAM_DZ + dz lower."""
    c = st['T'][1]; a = 90.0 - v; d = np.array([-math.sin(math.radians(a)), math.cos(math.radians(a)), 0.0])
    p = (PC if look is None else np.asarray(look, float)) - d * (DIST + extra)
    put(c, (p[0], p[1], CAM[2] + CAM_DZ + dz), a % 360.0, True)
    e.w32(0x800E5EF4, c); e.wf(0x800E5EF8, 5.6)
def stage(v, disp, at, carry=None, yaw=0.0):
    """Guri at her start + disp along her facing, Dash `at` ahead of her start facing her turned yaw more (melee.his_yaw)
    (+ carry: her start frame, her hands carrying him: x to her left, y back toward her, z up). The pair's turn is HV
    whatever the view (v unused)."""
    v = HV
    h, g, c = st['h'], st['T'][0], st['T'][1]
    fv = np.array([math.sin(math.radians(v)), -math.cos(math.radians(v)), 0.0])      # her facing in the world
    hg = math.degrees(math.atan2(-fv[0], fv[1]))
    g0 = np.array([CAM[0], CAM[1] + DIST, CAM[2]]) - fv * st.get('K', {}).get('PLAYER_AT', melee.PLAYER_AT) / 2
    if disp is not None: put(g, g0 + fv * disp, hg, True)
    hp = g0 + fv * at
    if carry is not None:
        lat = np.array([math.cos(math.radians(v)), math.sin(math.radians(v)), 0.0])     # her model +x in the world
        hp = hp + lat * carry[0] - fv * carry[1] + np.array([0.0, 0.0, carry[2]])
    put(h, hp, (hg + DASH_TURN + yaw) % 360.0, False)
    for a in range(3): e.wf(h + 0x98 + 4 * a, 0.0)
    e.wf(h + 0x8C, (hg + DASH_TURN + yaw) % 360.0)    # his yaw: the control function puts +0x14 back from it each frame
    e.wf(g + 0x60, 0.0); e.wf(c + 0x60, 0.0)     # her and the camera droid's radius 0: else the game pushes the player out
    for a in range(3): e.wf(h + 0x50 + 4 * a, e.rf(h + 0x08 + 4 * a))
    return fv, hg, g0


def his_state(tg, kk):
    """Stills: (his place ahead of her start, carry or None, his block, its frame, label) at key kk of her block tg."""
    if tg == 'guGr': return melee.PLAYER_AT - melee.PULL * melee.pulled(kk), None, 'SFid', 1.0, 'stand'
    if tg == 'guPu':
        db = STILL_DB.get(kk)
        return player_at(tg, kk, db[1] if db else None), None, 'plDb' if db else 'SFid', 1.0 + (db[0] if db else 0), \
            ('plDb key %d' % db[0]) if db else 'stand'
    if tg == 'guSh':
        tau = melee.sh_tau(kk)
        if tau is None: return melee.PLAYER_HELD, None, 'SFid', 1.0, 'stand'
        fr = min(1.0 + melee.SPEED * tau, 1.0 + melee.DB_PARK)
        return melee.PLAYER_HELD + melee.shove(tau), None, 'plDb', fr, 'plDb frame %.1f' % fr
    if tg in ('guLf', 'guTh') and not (tg == 'guTh' and kk > melee.RELEASE_KEY):
        fr = ca_frame(tg, 1.0 + kk)
        return melee.PLAYER_HELD + melee.SHOVE, melee.carry(tg, 1.0 + kk), 'plCa', fr, 'plCa key %d, carried' % (fr - 1)
    dt = (kk - melee.RELEASE_KEY) / melee.SPEED        # guTh after the release: on his way (a ballistic estimate)
    c = melee.carry('guTh', 1.0 + melee.RELEASE_KEY)
    fly = np.array([0.0, -FLY_SPEED * dt, melee.THROW_VZ * dt - 0.5 * FLY_G * dt * dt])
    return melee.PLAYER_HELD + melee.SHOVE, c + fly, 'plFa', 1.0 + melee.FA_SPEED * dt, 'plFa, flying (estimate)'
def ca_frame(tg, fr):
    """plCa's frame at her guLf / guTh frame fr: it runs with her from her guLf start (guTh frame 1 = plCa's
    melee.LF_KEYS)."""
    return fr if tg == 'guLf' else fr + melee.LF_KEYS - 1.0
FLY_SPEED, FLY_G = 15.2, 24.6      # palace.st, Dash thrown at 18 units/s (local/work/melee/p5_throw.py): his ground speed
                                   # over a flight, his fall per s^2 (stills only; the video lets the game fly him)


def run_stills(t):
    h, g = st['h'], st['T'][0]; c = st['T'][1]; hs = h + 0x18C
    if 'plan' not in st:
        st['plan'] = [(v, tg, kk) for v in VIEWS for tg, ks in STILLS for kk in ks]; st['log'] = []
        if GUARD: g_ = GUARD.split(':'); st['plan'].append((float(g_[2]), g_[0], int(g_[1])))
        if LOOK_GUARD and not st.get('guard'): install_guard(); st['guard'] = True
    SETTLE, PER = 150, 40
    i = max(0, t - SETTLE) // PER; f = max(0, t - SETTLE) % PER
    if i >= len(st['plan']):
        json.dump(st['log'], open(os.path.join(e.shot_dir if hasattr(e, 'shot_dir') else '.', 'stills.json'), 'w'))
        e.stop(); return
    v, tg, kk = st['plan'][i]
    m = next(m for m in MOVES if m.tag == tg); inst = st['inst'][tg]
    if m.skel == 1: return still_alone(v, tg, kk, m, inst, f, guard=GUARD and i == len(st['plan']) - 1)
    disp = -m.keys[kk][16][4] if tg in ('guGr', 'guTh') else melee.STEP          # her root motion so far (forward)
    at, car, blk, bfr, who_ = his_state(tg, kk)
    look = None
    yaw = melee.his_yaw(tg, 1.0 + kk)
    if blk == 'plFa':                                    # flying: the camera between the two
        fv_, _, g0_ = stage(v, disp, at, car, yaw); hp = np.array([e.rf(h + 8 + 4 * a) for a in range(3)])
        look = 0.5 * (hp + g0_ + fv_ * disp); look[2] = CAM[2]
    cam_put(v, look, 0.0 if look is None else 2.0, 0.5 * max(car[2], 0.0) if car is not None else 0.0)
    fv, hg, g0 = stage(v, disp, at, car, yaw)
    if f == 0 or e.r32(g + 0xCC) != inst: play(g + 0xB8, inst, 1.0 + kk, 0.0)
    dinst = st['inst'].get(blk) or find_block(hs, blk)
    if blk in DESC_ID: hold_desc(blk, bfr)
    if f > 0 and not steady(hs, dinst): st['recut'] = st.get('recut', 0) + 1
    if f == 0 or not steady(hs, dinst): play(hs, dinst, bfr, 0.0)
    if os.environ.get('VDEBUG') and blk == 'plCa':
        print('  f %d mode %x cur %08x to %08x (plCa %08x) frame %.2f; ' % (f, e.r32(hs), e.r32(hs + 0x14), e.r32(hs + 0x18), dinst,
              e.rf(dinst + 4)) + carried_ram(), flush=True)
    if f == 30:
        hp = np.array([e.rf(h + 8 + 4 * a) for a in range(3)]); gp = np.array([e.rf(g + 8 + 4 * a) for a in range(3)])
        drawn = np.array([e.rf(h + 0x208 + 0x30 + 4 * a) for a in range(2)])
        print('  his drawn place (+0x208) off the staged one by %.3f' % float(np.linalg.norm(drawn - hp[:2])), flush=True)
        print('  player ahead of her %.3f (staged %.3f), his heading %.1f (her %.1f)' % (float(np.dot(hp - gp, fv)), at - disp, e.rf(h + 0x14), hg), flush=True)
        e.shot(); st['log'].append(dict(view=v, block=tg, key=kk, player=who_))
        if STILL_DUMP:
            d_ = e.shot_dir if hasattr(e, 'shot_dir') else '.'
            e.dump(os.path.join(d_, f'still_{len(st["log"]) - 1}_{tg}_{kk}_{int(v)}.ram')); print('  dumped RAM', flush=True)
        if tg == 'guPu':
            want = next(x[2] for x in m.hold if x[0] == kk)
            print('  her left wrist to his right shoulder %.3f in RAM (table %.3f)' % (float(np.linalg.norm(her_world(7, HV) - his_world(8, HV))), want), flush=True)
        if blk == 'plCa': print('  ' + carried_ram(), flush=True)
        if tg == 'guLf' and kk == melee.LF_KEYS - 1:
            print('  her place %s, his %s' % (np.round([e.rf(g + 8 + 4 * a) for a in range(3)], 3).tolist(), np.round(hp, 3).tolist()), flush=True)
            for side, hb, pt in (('right', 10, 'collar back'), ('left', 7, 'belt back')):
                P = his_pts(); print('  guLf last key: her %s wrist to his %s point %.3f in RAM' % (side, pt, float(np.linalg.norm(her_world(hb, HV) - P[pt]))), flush=True)
        print('shot', len(st['log']), 'view', v, tg, 'key', kk, 'frame %.2f' % e.rf(inst + 4), 'player', who_,
              '(his block re-cut %d times so far)' % st.get('recut', 0), flush=True)


def still_alone(v, tg, kk, m, inst, f, guard=False):
    """A still of one of the player's blocks, Dash alone (Guri parked out of sight) at the pair's centre, facing world
    (his front: view 0, his side: 90), the camera lowered with his pelvis; guard: Dash in the guard look, the
    turntable's install (tools/video/record_guard_turntable.py MOVE=1: guard.bin onto his trot bone nodes, as guard.c
    does with g_guard_on)."""
    h, g = st['h'], st['T'][0]; hs = h + 0x18C
    if guard and not st.get('guard'): install_guard(); st['guard'] = True
    put(g, (CAM[0] + 100, CAM[1] - 60, CAM[2]), 0.0, True)
    hg = (HV + DASH_TURN) % 360.0
    put(h, PC, hg, False); e.wf(h + 0x8C, hg)
    for a in range(3): e.wf(h + 0x98 + 4 * a, 0.0)
    e.wf(st['T'][1] + 0x60, 0.0)
    pz = melee.up_world(m.keys[kk], 17)[2] if tg in ('plUp', 'plFa') else melee.P_PELVIS
    cam_put(v, None, 0.0, 0.5 * (pz - melee.P_PELVIS))
    if tg in DESC_ID: hold_desc(tg, 1.0 + kk)
    if f == 0 or not steady(hs, inst): play(hs, inst, 1.0 + kk, 0.0)
    if f == 30:
        hp = np.array([e.rf(h + 8 + 4 * a) for a in range(3)]); drawn = np.array([e.rf(h + 0x208 + 0x30 + 4 * a) for a in range(2)])
        z = e.rf(melee._ptop + 0x40) - e.rf(h + 0x10)
        print('  his drawn place (+0x208) off the staged one by %.3f; placement node %.3f above his floor point (table %.3f)'
              % (float(np.linalg.norm(drawn - hp[:2])), z, m.keys[kk][18][5] + melee.PLACE_DZ), flush=True)
        e.shot(); st['log'].append(dict(view=v, block=tg, key=kk, player='guard look' if guard else 'alone'))
        print('shot', len(st['log']), 'view', v, tg, 'key', kk, 'frame %.2f' % e.rf(inst + 4), 'guard' if guard else '', flush=True)
def install_guard():
    """guard.bin (local/game/guard.bin) at 0x80548000 and its meshes on Dash's trot bone nodes (each node's bone
    children + the image's meshes, the weapon last), the child lists at GLISTS (Guri's are at LISTS)."""
    img = open(os.path.join(paths.GAME, 'guard.bin'), 'rb').read()
    assert 0x80548000 + len(img) <= GURI_RAM, len(img)
    for o in range(0, len(img), 4): e.w32(0x80548000 + o, struct.unpack_from('>I', img + bytes(4), o)[0])
    nodes = st['dnodes']; free = GLISTS
    for i, nd in enumerate(nodes):
        kids = [e.r32(e.r32(nd + 0x10) + 4 * j) for j in range(e.r32(nd + 0x0C))]
        cnt, lp = struct.unpack_from('>II', img, 8 + 8 * i)
        weapon = [k for k in kids if i == 6 and e.r32(k) & 0x80]
        lst = [k for k in kids if k in nodes] + [struct.unpack_from('>I', img, lp - 0x80548000 + 4 * j)[0] for j in range(cnt)] + weapon
        for j, v in enumerate(lst): e.w32(free + 4 * j, v)
        e.w32(nd + 0x0C, len(lst)); e.w32(nd + 0x10, free); free += 4 * len(lst) + 16


def his_pts():
    """His collar and belt points in the world from his posed nodes in RAM (melee.collar / melee.belt's rule)."""
    c, n, p = his_world(9, HV), his_world(2, HV), his_world(17, HV)
    def fwd(i):
        nd = st['dnodes'][i]; M_ = np.eye(3)
        W = {}
        def get(j):
            if j not in W:
                m = np.eye(4); m[:3, :3] = [[e.rf(st['dnodes'][j] + 0x14 + 4 * (3 * a + b)) for b in range(3)] for a in range(3)]
                W[j] = m @ get(DPARENT[j]) if j in DPARENT else m
            return W[j]
        r = -get(i)[1, :3]; r = r / np.linalg.norm(r); a = math.radians(e.rf(st['h'] + 0x14) + 180)
        return np.array([math.cos(a) * r[0] - math.sin(a) * r[1], math.sin(a) * r[0] + math.cos(a) * r[1], r[2]])
    return {'collar': c + 0.75 * (n - c) + fwd(9) * (melee.P_DEPTH - 0.05),
            'collar back': c + 0.75 * (n - c) - fwd(9) * melee.BACK_COLLAR, 'belt': p + fwd(17) * melee.P_FRONT + np.array([0, 0, 0.05]),
            'belt back': p - fwd(17) * melee.BACK_BELT + np.array([0, 0, 0.05])}      # turned round: her hand on his back (melee.grip_pt)


def run_video(t):
    """--video: per view a take: the pair staged as for the stills (Dash held at his place facing her), Guri put at
    her start once and then left to the game (the grab's root motion moves her), the blocks played in turn at their
    speed (a loop played its count of times): the first cut in, the next blended in by the game's way (play how 3,
    the table's PU_BLEND); a shot every 2nd VI; video.json: per shot {take, label}. What he does comes from the
    combo's tables in RAM (melee.py writes them into the image, the patch plays the same): STAG gives his place (ahead
    of her start, to her left, up) and his yaw at her frame + its lead x her frame's last step, written each VI until
    the release; EVNT's events fire when her frame (counted on through a loop) reaches theirs: EV_PLAY plays his block
    by the game's blend (late by tau: as far on and its blend as far along; blend 0 a cut: the shove's plDb parked),
    EV_RELEASE writes his velocity once with the airborne flag, EV_DMG adds up (the harness holds his health), EV_HOLD
    is logged. plCa (carried) follows her timeline frame for frame from its event, our descriptor on him (hold_desc)
    from guLf's start to his landing; the game flies and lands him (plFa raised to its landing frame FA_LAND + 1 if
    it lands early, LAND_DMG); the camera then follows (between her and him, backing off as they part). guTh's end:
    her trSt started with the game's blend (play how 3, the table's TH_IDLE_BLEND), her place and block watched to
    the take's end. 'plUp:1' last in the list: UP_DELAY of game time after landing his plUp is cut in (from plFa's
    end) and kept at the game clock's frame, the camera closing on him; the take ends UP_TAIL VIs after it.
    Lines: per guPu key her left wrist to his right shoulder in RAM vs the table; per push his rear ankle's move (D17);
    the events fired and the damage; the throw's air time, distance and landing (face down: his chest node vs the
    back of his pelvis in RAM), his yaw at the release vs hers; her idle after the throw; the get-up."""
    h, g, c = st['h'], st['T'][0], st['T'][1]; hs = h + 0x18C
    if 'vplan' not in st:
        seq = [(b.split(':')[0], int(b.split(':')[1])) for b in VIDEO.split(';')]
        st['getup'] = any(tg == 'plUp' for tg, _ in seq); seq = [x for x in seq if x[0] != 'plUp']
        segs = []
        for tg, times in seq:
            b = next(x for x in st['blocks'] if x['tag'] == tg)
            dur = int(round(60 * (b['keys'] - 1) / b['speed'])) * times
            segs.append((tg, dur, times))
        st['vplan'] = [(v, segs) for v in VIEWS]; st['vlog'] = []; st['vi'] = 0; st['vt0'] = t
        st['fall'] = st['inst']['plFa']; st['trst'] = find_block(g + 0xB8, 'trSt')
        if LOOK_GUARD and not st.get('guard'): install_guard(); st['guard'] = True
    if st['vi'] >= len(st['vplan']):
        json.dump(st['vlog'], open(os.path.join(e.shot_dir, 'video.json'), 'w'))
        vh = st.get('vhold', [])
        for v_, kk, ph, d, want in vh: print(f'  view {v_:.0f} guPu key {kk} (+{ph:.2f}): her left wrist to his right shoulder {d:.3f} in RAM (table {want:.3f})', flush=True)
        if vh: print('video hold: RAM vs table max %.3f over %d keys' % (max(abs(d - w) for *_, d, w in vh), len(vh)), flush=True)
        for x in st.get('vfeet', []): print('  view %.0f %s at %.2f s: his rear ankle moved max %.3f (front ankle %.3f) in RAM over the push' % x, flush=True)
        for x in st.get('vthrow', []): print('  view %.0f throw: air %.3f s (%d VIs), distance %.2f (%.2f of his body heights), release z +%.2f, peak +%.2f, landed at %.2f %.2f %.2f' % x, flush=True)
        for x in st.get('vcarry', []): print('  view %.0f carry: %d VIs, plCa lost as blended-to %d, our descriptor put back %d, plCa frame '
                                             'off her timeline max %.3f' % (x['v'], x['vis'], x['lost'], x['put'], x['drift']), flush=True)
        for x in st.get('vyaw', []): print('  view %.0f release: his heading %.2f, hers %.2f: %.2f off facing away from her (limit %.0f)  %s' % (*x, melee.YAW_MAX, 'PASS' if x[3] <= melee.YAW_MAX else 'FAIL'), flush=True)
        for x in st.get('vface', []): print('  view %.0f lying (plFa frame %.2f): chest node %.3f above the floor, the back of his pelvis %.3f: %s  %s' % (*x, 'PASS' if x[2] < x[3] else 'FAIL'), flush=True)
        evs = st.get('vev', [])
        for v_ in VIEWS:
            mine = [x for x in evs if x[0] == v_]
            print('  view %.0f events: %s' % (v_, ', '.join('%s/%d f%.0f %s%s (+%.3f s)' % (x[1], x[2], x[3], {1: 'HOLD', 2: 'PLAY ', 3: 'DMG ', 4: 'RELEASE'}[x[4]],
                  x[5] if x[4] in (2, 3) else '', x[6]) for x in mine)), flush=True)
        for v_, d_ in st.get('vdmg', []): print('  view %.0f damage: %d (EVNT and the landing)' % (v_, d_), flush=True)
        for x in st.get('vidle', []): print('  view %.0f her idle: block %s, state mode %d, %d VIs after the blend began; her place moved %.3f since (trSt\'s own sway: its root y 0.13..0.55 and back)  %s' % (*x, 'PASS' if x[1] == 'trSt' and x[2] == 1 else 'FAIL'), flush=True)
        e.stop(); return
    v, segs = st['vplan'][st['vi']]; f = t - st['vt0']; st['vt_now'] = f
    SETTLE, LEAD = 90, 30
    TAIL = 200 if segs[-1][0] == 'guTh' else 40
    spd = lambda tg: next(x for x in st['blocks'] if x['tag'] == tg)['speed']
    b_keys = lambda tg: next(x for x in st['blocks'] if x['tag'] == tg)['keys']
    K = st['K']
    if f < SETTLE:                                       # staged, the first block parked on its first frame
        stage(v, 0.0, stag_at(segs[0][0], 1.0, False)[0]); cam_put(v); st['cam'] = None
        play(g + 0xB8, st['inst'][segs[0][0]], 1.0, 0.0); play(hs, st['sfid'], 1.0, 0.0)
        st.update(pfr=None, kprev=None, thrown=None, feet=None, feet_to=None, fstep=0.0, seg=None, yaw=0.0, idle=None,
                  carried=None)
        label = ''
    else:
        u = f - SETTLE - LEAD; label = 'Stance'; tg = segs[0][0]; row = None
        if u >= 0:                                   # the segments end on her block's own frames (game time runs
            if st.get('seg') is None: st.update(seg=0, segw=0, segacc=0.0, segpf=None, tailw=0, cprev=0.0, base=0.0)
            j = st['seg']; tg, dur, times = segs[j]; w = st['segw']; st['segw'] += 1    # slower than VIs)
            inst = st['inst'][tg]; nk = b_keys(tg) - 1.0
            wrap_ = not next(x for x in st['blocks'] if x['tag'] == tg)['clamp']
            if w == 0:
                feet_end()
                if j == 0: play(g + 0xB8, inst, 1.0, spd(tg))
                else: play_blend(g + 0xB8, inst, 1.0, K['PU_BLEND'], spd(tg))
                st['pfr'] = None; st['cprev'] = 0.0; st['feet_to'] = None
                if os.environ.get('VDEBUG'): print('seg', tg, 'her', [round(e.rf(g + 8 + 4 * a), 3) for a in range(3)], 'him', [round(e.rf(h + 8 + 4 * a), 3) for a in range(3)], flush=True)
            fr = e.rf(inst + 4)
            if st['segpf'] is not None and w > 0:
                d = fr - st['segpf']; st['segacc'] += d + nk if d < -0.5 * nk else d
            st['segpf'] = fr
            if st['pfr'] is not None and fr != st['pfr']: st['fstep'] = (fr - st['pfr']) % nk if wrap_ else fr - st['pfr']
            c = 1.0 + st['segacc']                       # her frame counted on through the loops
            if st.get('feet_to') is not None and c >= st['feet_to']: feet_end(); st['feet_to'] = None
            fire(v, f, tg, nk, c)                        # EVNT: what her frames reached since the last VI start
            st['cprev'] = c; base = st['base']           # (the segment's own: the advance below moves st['base'])
            if st['segacc'] >= nk * times - 1e-6:
                if j < len(segs) - 1: st.update(seg=j + 1, segw=0, segacc=0.0, segpf=None, base=st['base'] + nk * times)
                else:
                    if tg == 'guTh' and st['idle'] is None:     # her stand by the game's blend (D8)
                        play_blend(g + 0xB8, st['trst'], 1.0, K['TH_IDLE_BLEND'], e.rf(st['trst'] + 8))
                        st['idle'] = dict(f=f, p=[e.rf(g + 8 + 4 * a) for a in range(3)])
                    elif tg != 'guTh': e.wf(inst + 8, 0.0)
                    st['tailw'] += 1
                    if os.environ.get('VDEBUG') and st['idle'] and st['tailw'] % 5 == 1:
                        def root(ins): x = e.r32(ins + 0x10); return [round(e.rf(x + 0x1C + 4 * a), 3) for a in range(3)]
                        print('idle', st['tailw'], 'her', [round(e.rf(g + 8 + 4 * a), 3) for a in range(3)], 'mode', e.r32(g + 0xB8),
                              'prog %.2f' % e.rf(g + 0xB8 + 8), 'guTh fr %.2f root' % e.rf(inst + 4), root(inst), 'trSt fr %.2f root' % e.rf(st['trst'] + 4), root(st['trst']), flush=True)
                    done = (st['thrown'] or {}).get('done') if st['getup'] else st['tailw'] >= TAIL
                    if done:
                        idle_end(v); st.setdefault('vdmg', []).append((v, st.get('dmg', 0))); st['dmg'] = 0
                        st['vi'] += 1; st['vt0'] = t + 1; st['seg'] = None; return
            if tg == 'guPu':                             # a guPu key passed: her left wrist vs his right shoulder
                kf = fr - 1.0
                kp = st.get('kprev'); st['kprev'] = kf
                if kp is not None and math.floor(kf) != math.floor(kp) and w > 0:
                    kk = int(math.floor(kf)) % (b_keys(tg) - 1)
                    d = float(np.linalg.norm(her_world(7, HV) - his_world(8, HV)))
                    mm = next(m for m in MOVES if m.tag == 'guPu')
                    want = next(x[2] for x in mm.hold if x[0] == kk)
                    st.setdefault('vhold', []).append((v, kk, kf - math.floor(kf), d, want))
            lead = st['stag'][tg]['lead'] * st.get('fstep', 0.0) if tg in st['stag'] else 0.0
            if tg in st['stag']:                         # STAG: his place and yaw at her frame (+ its lead)
                row = stag_at(tg, fr + lead, wrap_); st['yaw'] = row[3]
            ca = st.get('carried')                       # carried: his block with her timeline, frame for frame
            if ca and st['thrown'] is None:
                blk, start, at_, tg_ = ca
                cw = st.setdefault('cwatch', dict(v=v, put=0, lost=0, vis=0, drift=0.0))
                gc = base + c - 1.0                      # her frame counted from the combo's start
                cw['put'] += hold_desc(tg_, start) and gc > at_; cw['vis'] += 1
                cw['lost'] += e.r32(hs + 0x18) != blk
                want = min(start + gc + lead - at_, float(b_keys(tg_)))
                if gc > at_: cw['drift'] = max(cw['drift'], abs(e.rf(blk + 4) - want))
                if not os.environ.get('CA_FREE'): e.wf(blk + 4, want)
            st['pfr'] = fr
            label = {'guGr': 'Grab', 'guPu': 'Punch', 'guSh': 'Shove', 'guLf': 'Lift', 'guTh': 'Throw'}.get(tg, tg) + \
                (f' {min(int(st["segacc"] // nk) + 1, times)}/{times}' if times > 1 else '')
        if st['thrown'] is None:
            if row is None: row = stag_at(tg, 1.0, False)
            stage(v, None, row[0], (row[1], 0.0, row[2]), row[3])
        else: flight(v, f)
        feet_track(v)
        put(g, [e.rf(g + 8 + 4 * i) for i in range(3)], 270.0, True)
        follow(v)
    if (st.get('thrown') or {}).get('up') is not None: label = 'Get up'
    if f % 2 == 0:
        e.shot(); st['vlog'].append(dict(take=st['vi'], view=v, label=label))


def feet_start(v, kind):
    """D17: from a hit, his rear (right) ankle's largest move from where it stood, and his front (left) ankle's largest
    slide from one VI to the next while it is within 0.05 of its height at the hit (on the floor)."""
    b0 = his_world(14, HV)
    st['feet'] = dict(v=v, kind=kind, t=e.rf(st['h'] + 0xD8), a0=his_world(11, HV), b0=b0, bp=b0, a=0.0, b=0.0)
def feet_track(v):
    ft = st.get('feet')
    if not ft: return
    a, b = his_world(11, HV), his_world(14, HV)
    ft['a'] = max(ft['a'], float(np.linalg.norm(a - ft['a0'])))
    if os.environ.get('VDEBUG'): print('feet', ft['kind'], 'clock %.3f' % (e.rf(st['h'] + 0xD8) - ft['t']), 'rear', (a - ft['a0']).round(3), 'front', (b - ft['b0']).round(3), 'him', [round(e.rf(st['h'] + 8 + 4 * i), 3) for i in range(3)], 'mode', e.r32(st['h'] + 0x18C), 'prog %.3f' % e.rf(st['h'] + 0x18C + 8), flush=True)
    if b[2] - ft['b0'][2] < 0.05 and ft['bp'][2] - ft['b0'][2] < 0.05: ft['b'] = max(ft['b'], float(np.linalg.norm((b - ft['bp'])[:2])))
    ft['bp'] = b
def feet_end():
    ft = st.pop('feet', None)
    if ft: st.setdefault('vfeet', []).append((ft['v'], ft['kind'], ft['t'] - 10000.0, ft['a'], ft['b']))


def fire(v, f, tg, nk, c):
    """EVNT's events of her block tg whose frame (loop x nk + frame) her frame passed since the last VI (cprev < it <= c),
    in the table's order; tau: how late (s of her block's time)."""
    sp = next(x for x in st['blocks'] if x['tag'] == tg)['speed']
    for etg, L, F, kind, a0, a1, a2, a3 in st['evnt']:
        T = L * nk + F
        if etg != tg or not (st['cprev'] < T <= c): continue
        tau = (c - T) / sp
        st.setdefault('vev', []).append((v, etg, L, F, kind, a0, tau))
        if kind == EV_HOLD: st['held'] = f
        elif kind == EV_DMG: st['dmg'] = st.get('dmg', 0) + a0
        elif kind == EV_RELEASE: throw(v, f, a1, a2)
        elif kind == EV_PLAY: his_play(v, tg, a0, a1, a2, a3, tau, st['base'] + T - 1.0, sp)
def his_play(v, tg, t_, start, blend, speed, tau, at_, sp):
    """EV_PLAY: his block t_ from start (late by tau: as far on, its blend as far along) by the game's blend (how 3),
    a cut when blend is 0; one of ours that needs it (DESC_ID) gets our descriptor. at_: the event's frame counted from
    the combo's start (a carried block follows her timeline from there)."""
    hs = st['h'] + 0x18C; blk = st['inst'].get(t_) or find_block(hs, t_)
    if t_ == 'plDb' and speed:
        feet_end(); feet_start(v, 'punch' if tg == 'guPu' else 'shove'); st['feet_to'] = None
    if speed == 0.0: st['feet_to'] = at_ - st['base'] + 1.0 + blend * sp     # his step done once he is back or parked
    if blend > 0.0: play_blend(hs, blk, start + speed * tau, blend, speed); e.wf(hs + 8, tau)
    else: play(hs, blk, start + speed * tau, speed)
    if t_ in DESC_ID: hold_desc(t_, start)
    if t_ == 'plCa': st['carried'] = (blk, start, at_, t_)
    if t_ == 'plFa': st['fall'] = blk; st['fa_speed'] = speed
def throw(v, f, speed, vz):
    """EV_RELEASE: his velocity once (speed along her facing, vz up) with the airborne flag (doc *The 'push'
    messages*); EVNT's next event plays his plFa."""
    h = st['h']
    fv = np.array([math.sin(math.radians(HV)), -math.cos(math.radians(HV)), 0.0])
    e.wf(h + 0x98, fv[0] * speed); e.wf(h + 0x9C, fv[1] * speed); e.wf(h + 0xA0, vz)
    e.w32(h + 0x74, (e.r32(h + 0x74) & ~0x04000000) | 0x08000000)
    st['carried'] = None
    cw = st.pop('cwatch', None)
    if cw: st.setdefault('vcarry', []).append(cw)
    st.setdefault('vyaw', []).append((v, e.rf(h + 0x8C), e.rf(st['T'][0] + 0x14),
                                      abs(float(melee.wrap(e.rf(h + 0x8C) - e.rf(st['T'][0] + 0x14))))))
    p = np.array([e.rf(h + 0x50 + 4 * a) for a in range(3)])
    st['thrown'] = dict(f=f, p0=p, peak=p[2], land=None, v=v, clock=e.rf(h + 0xD8))
    print('throw: released at %.2f %.2f %.2f (floor %.2f), velocity %.1f along her facing, vz %.1f' % (*p, CAM[2], speed, vz), flush=True)
def flight(v, f):
    """After the release: the game flies him; his plFa kept by our descriptor (hold_desc: in the air and on landing the
    game's own requests are refused; a loss of plFa is only counted)."""
    h = st['h']; th = st['thrown']; hs = h + 0x18C; d = st['fall']; nfa = float(melee.FA_KEYS)
    if th['land'] is None:                       # in the air: our descriptor keeps plFa (counted if it had to be put back)
        th['put'] = th.get('put', 0) + hold_desc('plFa', 1.0); th['vis'] = th.get('vis', 0) + 1
        th['lost'] = th.get('lost', 0) + (e.r32(hs + 0x18) != d)
    fr = min(1.0 + st['fa_speed'] * (e.rf(h + 0xD8) - th['clock']), nfa)     # where plFa is by the game's own clock
    if th.get('up') is None and fr >= nfa and th['land'] is not None and not th.get('face'):
        th['face'] = True; st.setdefault('vface', []).append((v, fr, *lying()))
    if th.get('up') is not None:                 # the get-up (plUp, cut in from plFa's end), kept the same way
        u = st['inst']['plUp']; us = next(x for x in st['blocks'] if x['tag'] == 'plUp')['speed']
        ufr = min(1.0 + us * (e.rf(h + 0xD8) - th['up']), float(melee.UP_KEYS))
        if e.r32(hs + 0x18) != u or (e.r32(hs) & 0x7FFFFFFF == 1 and e.r32(hs + 0x14) != u): play(hs, u, ufr, us)
        if ufr >= melee.UP_KEYS:
            th['upend'] = th.get('upend', f)
            if f - th['upend'] == 1:
                print('get-up: plUp over %.3f s of game time, %d VIs; his place moved %.3f since landing' % (
                    e.rf(h + 0xD8) - th['up'], f - th['upf'], float(np.linalg.norm(np.array([e.rf(h + 0x50 + 4 * a) for a in range(3)]) - th['landp']))), flush=True)
            if f - th['upend'] >= UP_TAIL: th['done'] = True
    elif e.r32(hs + 0x18) != d or (e.r32(hs) & 0x7FFFFFFF == 1 and e.r32(hs + 0x14) != d):
        th['recut'] = th.get('recut', 0) + 1      # plFa lost (our descriptor keeps it in the air and on landing: counted)
        if th['land'] is None: th['recut_air'] = th.get('recut_air', 0) + 1
    if (st.get('getup') and th['land'] is not None and th.get('up') is None
            and e.rf(h + 0xD8) - th['land_clock'] >= st['K']['UP_DELAY']):        # UP_DELAY of game time after landing
        th['up'] = e.rf(h + 0xD8); th['upf'] = f
        play(hs, st['inst']['plUp'], 1.0, next(x for x in st['blocks'] if x['tag'] == 'plUp')['speed'])
        print('get-up: plUp cut in %d VIs (%.3f s of game time) after landing (plFa frame %.2f)' % (
            f - th['land'], th['up'] - th['land_clock'], fr), flush=True)
    p = np.array([e.rf(h + 0x50 + 4 * a) for a in range(3)]); th['peak'] = max(th['peak'], p[2])
    if th['land'] is None and f - th['f'] > 6 and e.r32(h + 0x74) & 0x04000000:
        th['land'] = f; air = (f - th['f']) / 60.0; dist = float(np.linalg.norm((p - th['p0'])[:2]))
        st.setdefault('vthrow', []).append((v, air, f - th['f'], dist, dist / melee.BODY, th['p0'][2] - CAM[2], th['peak'] - CAM[2], *p))
        print('landed: air %.3f s (game time %.3f s), distance %.2f, at %.2f %.2f %.2f; plFa frame %.2f (lands on frame %d)' % (
            air, e.rf(h + 0xD8) - th['clock'], dist, *p, fr, st['K']['FA_LAND'] + 1), flush=True)
        th['landp'] = p; th['land_clock'] = e.rf(h + 0xD8); st['dmg'] = st.get('dmg', 0) + st['K']['LAND_DMG']
        if e.rf(d + 4) < st['K']['FA_LAND'] + 1.0:     # a wall can land him early: plFa on to its landing frame
            th['raised'] = e.rf(d + 4); e.wf(d + 4, st['K']['FA_LAND'] + 1.0)
    if th['land'] is not None and f - th['land'] in (30, 120):
        q = np.array([e.rf(h + 0x50 + 4 * a) for a in range(3)])
        print('  %d VIs after landing at %.2f %.2f %.2f, his block %s frame %.2f (plFa lost %d times, %d in the air); controller '
              'descriptor id %d' % (f - th['land'], *q, tag(e.r32(e.r32(e.r32(h + 0x1A0)))), e.rf(e.r32(h + 0x1A0) + 4), th.get('recut', 0),
                                    th.get('recut_air', 0), e.r32(e.r32(CTL + 4))), flush=True)
    if th['land'] is not None and f - th['land'] == 1:
        print('  flight: %d VIs, plFa lost as blended-to %d, our descriptor put back %d, plFa lost in the air %d' % (
            th.get('vis', 0), th.get('lost', 0), th.get('put', 0), th.get('recut_air', 0)), flush=True)
UP_TAIL = 50                   # the take ends this many VIs after the get-up
def lying():
    """(his chest node's height above his floor point, the back of his pelvis's: its node melee.P_FRONT along the pelvis
    bone's back) from his posed nodes in RAM (chained as his_world does, his placement node's real height)."""
    W = {}
    def M(n):
        m = np.eye(4); m[:3, :3] = [[e.rf(n + 0x14 + 4 * (3 * a + b)) for b in range(3)] for a in range(3)]
        m[3, :3] = [e.rf(n + 0x38 + 4 * a) for a in range(3)]; return m
    def get(j):
        if j not in W: W[j] = M(st['dnodes'][j]) @ get(DPARENT[j]) if j in DPARENT else M(st['dnodes'][j])
        return W[j]
    sc, dz = melee.DASH_SCALE, his_sampled()[1]
    c = get(9)[3, 2] * sc + dz; p = get(17)[3, :3] * sc + [0, 0, dz]
    back = get(17)[1, :3] / np.linalg.norm(get(17)[1, :3])          # the bone's +y: his back
    b = (p + back * melee.P_FRONT)[2]
    return float(c), float(b), 'face down' if c < b else 'NOT face down'
def carried_ram():
    """While he is carried: his ground flags (+0x74), the model node's and the pelvis node's 3x3 against rest x
    rot(sampled angles), the heights of his pelvis, chest and ankle nodes above his floor point and each leg's angle
    (hip to ankle) from straight down, from his posed nodes in RAM (chained as lying() does)."""
    h = st['h']; W = {}
    def M(n):
        m = np.eye(4); m[:3, :3] = [[e.rf(n + 0x14 + 4 * (3 * a + b)) for b in range(3)] for a in range(3)]
        m[3, :3] = [e.rf(n + 0x38 + 4 * a) for a in range(3)]; return m
    def get(j):
        if j not in W: W[j] = M(st['dnodes'][j]) @ get(DPARENT[j]) if j in DPARENT else M(st['dnodes'][j])
        return W[j]
    sc, dz = melee.DASH_SCALE, his_sampled()[1]
    p = lambda i: get(i)[3, :3] * sc + [0.0, 0.0, dz]
    smp, _ = his_sampled(); inst = e.r32(h + 0x1A0); x = e.r32(inst + 0x10); hdr = {}
    while x: hdr[e.r32(x + 8)] = e.r32(x); x = e.r32(x + 0x0C)
    off, drawn = {}, {}
    for i in (17, 18):
        nd = st['dnodes'][i]; hd = hdr[nd]
        rest = np.array([[e.rf(hd + 4 + 4 * (4 * a + c)) for c in range(3)] for a in range(3)])
        N = np.array([[e.rf(nd + 0x14 + 4 * (3 * a + c)) for c in range(3)] for a in range(3)])
        off[i] = float(np.abs(N - rest @ melee.rot(smp[i])).max())
        drawn[i] = [round(float(v), 1) for v in melee.angles_of(np.linalg.inv(rest) @ N)]
    legs = []
    for hip, ank in ((16, 14), (13, 11)):
        d = p(ank) - p(hip); legs.append(float(np.degrees(np.arccos(np.clip(-d[2] / np.linalg.norm(d), -1, 1)))))
    z = {n: float(p(i)[2]) for n, i in (('pelvis', 17), ('chest', 9), ('ankle l', 14), ('ankle r', 11))}
    return ('carried in RAM: +0x74 %08x; model node vs rest x rot(sampled %s) %.3f (drawn %s), pelvis node vs rest x '
            'rot(sampled %s) %.3f (drawn %s); heights pelvis %.3f chest %.3f (apart %.3f) ankles %.3f %.3f; legs from straight down %.0f %.0f deg'
            % (e.r32(h + 0x74), [round(v, 1) for v in smp[18]], off[18], drawn[18], [round(v, 1) for v in smp[17]], off[17], drawn[17],
               z['pelvis'], z['chest'], abs(z['chest'] - z['pelvis']), z['ankle l'], z['ankle r'], *legs))
def idle_end(v):
    """Her state at the take's end after the throw: her block, its state's mode, her place's move since the blend to
    trSt began."""
    i = st.get('idle')
    if not i: return
    g = st['T'][0]; p = [e.rf(g + 8 + 4 * a) for a in range(3)]
    cur = e.r32(g + 0xB8 + 0x14)
    st.setdefault('vidle', []).append((v, tag(e.r32(e.r32(cur))), e.r32(g + 0xB8) & 0x7FFFFFFF, i['f'] and (st['vt_now'] - i['f']),
                                       float(np.linalg.norm(np.array(p) - i['p']))))
def follow(v):
    """The camera: the pair's centre until the throw; then between her and him (toward him as they part), backed off."""
    th = st.get('thrown'); h, g = st['h'], st['T'][0]
    if th is None:                                   # up with him while she lifts him
        dz = 0.5 * max(e.rf(h + 0x10) - CAM[2], 0.0); st['cam'] = np.array([PC[0], PC[1], 0.0, dz])
        cam_put(v, None, 0.0, dz); return
    hp = np.array([e.rf(h + 8 + 4 * a) for a in range(3)]); gp = np.array([e.rf(g + 8 + 4 * a) for a in range(3)])
    sep = float(np.linalg.norm((hp - gp)[:2])); wh = 0.5 * min(max(1.0 - (sep - 3.0) / 15.0, 0.0), 1.0)
    look = wh * gp + (1.0 - wh) * hp; look[2] = CAM[2]
    want = np.array([*look[:2], min(max(0.45 * sep, 0.0), 8.0), 0.5 * max(hp[2] - CAM[2], 0.0) + 0.6 * max(hp[2] - CAM[2] - 1.0, 0.0)])
    if th.get('land') is not None and st.get('getup'):   # landed: closer on him for the get-up
        want = np.array([hp[0], hp[1], 2.5, 0.0])
    st['cam'] = want if st.get('cam') is None else st['cam'] + (want - st['cam']) * 0.12
    cl = st['cam']; cam_put(v, (cl[0], cl[1], CAM[2]), cl[2], cl[3])


e.run(script)

if SHEET and STILLS:
    from PIL import Image, ImageDraw
    d = e.shot_dir if hasattr(e, 'shot_dir') else os.path.join(paths.RUN, 'shots', os.environ.get('SHOTS', ''))
    files = sorted(f for f in os.listdir(d) if f.endswith('.png'))
    vname = lambda v: {90: 'side', 45: '3/4 front', 135: '3/4 back', 0: 'his front'}.get(int(v), str(v))
    labels = [f"{tg} key {kk} ({vname(v)})" for v in VIEWS for tg, ks in STILLS for kk in ks]
    if GUARD: g_ = GUARD.split(':'); labels.append(f"{g_[0]} key {g_[1]} ({vname(float(g_[2]))}, Look: Guard)")
    ims = [Image.open(os.path.join(d, f)).convert('RGB') for f in files[:len(labels)]]
    cols = sum(len(ks) for _, ks in STILLS); rows = (len(ims) + cols - 1) // cols
    w, hh = 480, int(480 * ims[0].height / ims[0].width)
    sheet = Image.new('RGB', (w * cols, (hh + 22) * rows), 'white'); dr = ImageDraw.Draw(sheet)
    for j, (im, lb) in enumerate(zip(ims, labels)):
        x, y = (j % cols) * w, (j // cols) * (hh + 22)
        sheet.paste(im.resize((w, hh)), (x, y + 22)); dr.text((x + 6, y + 5), lb, fill='black')
    sheet.save(SHEET, quality=90); print('sheet', SHEET, len(ims), 'stills')
