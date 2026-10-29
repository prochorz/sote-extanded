"""Stage 2's gunner check: from a state at stage 2's start, a fixed pad
script (stick right / left / up, B held, the view key C-right three times, R, L) and per frame the camera index, the
active entry, the view key's s16 VIEW_MODE, the sector record *0x800D2400, g_sky_on / g_native / g_rail / g_shot /
g_view_on, the Stft's guns-on +0x70, the guns' matrix (entry 5 +8: its forward row's yaw and pitch against the ship's)
and the camera's forward row; each new bolt of the player's (Blst owner Chor or the Stft) with its first place against
the guns' matrix place and the ship. Summary lines at the end (the yaw's range, the indexes seen, bolt offsets).

    M64CPU=2 SHOTS=s2g_<build> python3 gallrun/s2_gun.py <build>/sote-patch.z64 [--make BASE] [--shots]

  --make BASE  first make run/<build>_s2.st: from BASE (a state in Cut 05 or stage 1 of the build, e.g.
               run/<build>_peel.st), held lines let go with A, stage 1 flown by the take's pilot (work/chain_take.py),
               saved once Chor is IMG_SWITCH + 2 nodes on with no line held; the check then runs on from there
  --poke A=V,..  16-bit writes (hex) every frame of the check (e.g. 800E1B20=1: the Ship row's X-Wing)
  --pause K    START at k K (4 frames), A (Resume) 60 frames later, the script then starts K + 100 on
  --make-pause K  with --make: START at its frame K (stage 1), A (Resume) 60 frames later
  --shots      a shot at the script's marks (k 60, 130, 250, 330, 390, 450)
(k < 0: the pause's frames.) Lines: F (every 4th frame and each change), BOLT (a new bolt), SUM.

Stage 2's TIEs: with --rock and/or --panel the pad script is replaced by the bot of hang_hit.py
(lines let go with A, B fired k % 6 < 3, the gun centred) from the state to the end scene (g_cine 1) or --secs:
  --rock     per game frame every TieF object: its place and drawn node's place, the depth of the node's place in rock
             (signed distance to the nearest IMG_COLL face, < 0 behind its drawn side; peel_check.py's), shown (node
             +2 high byte), in view (in the camera's frustum, tan |x| < 0.75, |y| < 0.56, nearer than 3000), g_tie_down;
             a BACK line at each put-back (a jump > 150 in one VI: 'down' = g_tie_down went back to -1, rocky or not,
             'far' = it was TIE_FAR off the chase's point, else 'jump') with its new place and depth; a ROCK line each
             frame a TIE shown and in view is deeper than 0, with its last BACK; RSUM lines at the end
  --panel    per game frame RADAR_COUNT and each record (tag, +4, place, the TieF object it matches by place, its kind:
             fighter / bomber 10-13 / bomb 14 / battle / wave), the target panels shown (HUD 35..39 x != -1000; 37
             fighter, 39 bomber), the pick (the record in front nearest the view's middle); a PANEL line each frame
             39 is up or the pick is not a fighter; PSUM at the end
  --secs S   stop S seconds (VIs / 60) after the state (default 120)"""
import os, sys, math, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
ap = argparse.ArgumentParser()
ap.add_argument('rom'); ap.add_argument('--make', default=''); ap.add_argument('--shots', action='store_true')
ap.add_argument('--state', default=''); ap.add_argument('--poke', default=''); ap.add_argument('--pause', type=int, default=-1); ap.add_argument('--make-pause', type=int, default=-1)
ap.add_argument('--rock', action='store_true'); ap.add_argument('--panel', action='store_true'); ap.add_argument('--secs', type=float, default=120)
A = ap.parse_args()
ROM = os.path.abspath(A.rom)
BUILD = os.path.basename(os.path.dirname(ROM))
os.environ.setdefault('SHOTS', f's2g_{BUILD}')
import paths
import m64
from m64 import Emu, BTN, HERE

RUN = paths.RUN
ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
MLV = 32 if 'g_levels' in SYM else 6           # the mission's sub-level (32 from bf49)
LEVEL, HOLD, GALL = 0x8013CE0E, 0x800DD2D0, 0x80628000
ENTRIES, ACTIVE, INDEX, VIEW_MODE, SECTOR = 0x800D08A0, 0x800D08A4, 0x800D08A8, 0x8018E462, 0x800D2400
PEND = 0x8018E464                                      # the game's 'gunner view not taken yet' word (0x800998B8, cleared at 0x80099A74)
STATE = A.state or os.path.join(RUN, f'{BUILD}_s2.st')
start = A.make or STATE
if not os.path.exists(start): sys.exit(f'no {start}: make it with --make <state in Cut 05 or stage 1>')
e = Emu(ROM, video=m64.GLN); f32 = e.rf
S = {'h': 0, 'saved': not A.make, 'k0': None, 'slot': {}, 'last': None, 'rows': [], 'bolts': []}
# the pad script from the stage 2 state: (from k, to k, buttons, stick x, stick y, label)
SCRIPT = [(30, 90, 0, 60, 0, 'stick right'), (100, 160, 0, -60, 0, 'stick left'), (170, 220, 0, 0, 60, 'stick up'),
          (230, 290, 'B', 30, 0, 'B held, stick right'), (300, 304, 'CR', 0, 0, 'C-right'), (330, 360, 0, 60, 0, 'stick right'),
          (370, 374, 'CR', 0, 0, 'C-right'), (400, 430, 'B', -60, 0, 'B held, stick left'), (440, 444, 'CR', 0, 0, 'C-right'),
          (470, 474, 'R', 0, 0, 'R'), (500, 504, 'L', 0, 0, 'L'), (530, 560, 'Z', 0, 0, 'Z held')]
END = 600
SHOT_AT = (60, 130, 250, 330, 390, 450)


def v3(a): return [f32(a + 4 * i) for i in range(3)]


def sym(n, f=False): return (f32 if f else e.r32)(SYM[n]) if n in SYM else None


def cls(tag):
    a = 0x80112808
    for _ in range(80):
        if e.r32(a) == tag: return a
        a += 0x30
    return 0


def rpos(k):
    rt = e.r32(GALL + 20) + 0x38
    return [f32(rt + k * 0x54 + 4 * i) for i in range(3)]


def pilot(node):                                         # work/chain_take.py's
    if not e.r32(SYM['g_fly_on']): return 0, 0, 0
    pos = v3(SYM['g_fly_pos']); tp = rpos(node + 6); yaw = f32(SYM['g_fly_yaw'])
    err = (math.atan2(tp[1] - pos[1], tp[0] - pos[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
    return BTN['A'], max(-80, min(80, int(-err * 160))), max(-80, min(80, int(-(tp[2] - 10 - pos[2]) * 2)))


def yp(v):
    return math.degrees(math.atan2(v[1], v[0])), math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))


def measure(k, pad_label):
    stft = e.r32(cls(0x53746674) + 0x10); chor = e.r32(0x80112A78 + 0x10)
    ent = e.r32(ENTRIES); act = e.r32(ACTIVE); idx = e.r32(INDEX)
    ai = (act - ent) // 0x80 if ent and act >= ent else -9
    g5 = e.r32(ent + 5 * 0x80 + 8) if ent else 0
    gm = g5 if 0x80000000 <= g5 < 0x80800000 else 0
    gun_f = v3(gm + 0x10) if gm else [0, 0, 0]; gun_p = v3(gm + 0x30) if gm else [0, 0, 0]
    cam_f = v3(act + 0x24) if act else [0, 0, 0]; cam_e = v3(act + 0x44) if act else [0, 0, 0]
    gy, gp = yp(gun_f); cy, cp = yp(cam_f)
    ship = v3(stft + 0x50) if stft else [0, 0, 0]
    row = dict(k=k, pad=pad_label, pend=e.r32(PEND), idx=idx if idx < 0x80000000 else idx - (1 << 32), act=ai, vm=e.r16(VIEW_MODE),
               sec=e.r32(SECTOR), sky=sym('g_sky_on'), nat=sym('g_native'), rail=sym('g_rail'), shot=sym('g_shot'),
               von=sym('g_view_on'), pil=sym('g_pilot'), guns=e.r32(stft + 0x70) if stft else None,
               car=e.r32(stft + 0xAC) if stft else None, gun_yaw=round(gy, 1), gun_pitch=round(gp, 1),
               cam_yaw=round(cy, 1), cam_pitch=round(cp, 1), hold=e.r16(HOLD),
               gun_off=[round(gun_p[i] - ship[i], 1) for i in range(3)],
               cam_off=[round(cam_e[i] - ship[i], 1) for i in range(3)])
    S['rows'].append(row)
    key = (row['pend'], row['idx'], row['act'], row['vm'], row['sec'], row['sky'], row['nat'], row['guns'], row['shot'])
    if k % 4 == 0 or key != S['last']: print('F', row, flush=True)
    S['last'] = key
    rec = cls(0x426C7374)                                         # the player's new bolts
    if rec and 0x80000000 <= e.r32(rec + 0x10) < 0x80800000:
        n, sz, base = e.r32(rec + 8), e.r32(rec + 0xC), e.r32(rec + 0x10); live = set()
        for i in range(min(n, 64)):
            b = base + i * sz; own = e.r32(b + 0x64)
            if own not in (chor, stft): continue
            p = v3(b + 0x50)
            if p[2] < -20000: continue
            last = S['slot'].get(i); live.add(i); S['slot'][i] = p
            if last is not None and math.dist(p, last) < 300: continue
            d = v3(b + 0xA0)
            bo = dict(k=k, slot=i, owner='chor' if own == chor else 'stft', from_gun=[round(p[j] - gun_p[j], 1) for j in range(3)],
                      from_ship=[round(p[j] - ship[j], 1) for j in range(3)], dist_gun=round(math.dist(p, gun_p), 1) if gm else None,
                      dir_yaw=round(yp(d)[0], 1), dir_pitch=round(yp(d)[1], 1), gun_yaw=row['gun_yaw'], cam_yaw=row['cam_yaw'])
            S['bolts'].append(bo); print('BOLT', bo, flush=True)
        for i in list(S['slot']):
            if i not in live: del S['slot'][i]


# ---- stage 2's TIEs (--rock, --panel) ----
TIEF, RADAR_LIST, RADAR_COUNT, HUD_XY = 0x80112D48, 0x8018E468, 0x800E1B30, 0x80111110
SEEN = {'coll': None, 'prev': {}, 'down': {}, 'back': {}, 'rock': [], 'backs': [], 'panel': [], 'pick': {}, 'n': 0, 'p39': 0}
if A.rock or A.panel:
    import ctypes as C
    import numpy as np


def rd(a, n):                                            # bytes as the N64 sees them (RDRAM holds LE words)
    a0 = a & 0x7FFFFC; m = (a - (a & ~3)) + n
    raw = C.string_at(e.rdram() + a0, (m + 3) & ~3)
    return np.frombuffer(raw, '<u4').astype('>u4').tobytes()[a & 3: (a & 3) + n]


def coll():                                              # IMG_COLL (peel_check.py's coll())
    if SEEN['coll']: return SEEN['coll']
    c = e.r32(GALL + 108); n, tris = e.r32(c), e.r32(c + 4)
    x0, y0, cell = f32(c + 8), f32(c + 12), f32(c + 16); nx, ny = e.r32(c + 20), e.r32(c + 24)
    t = np.frombuffer(rd(tris, 24 * n), '>i2').reshape(n, 12).astype(np.float64)
    cells = np.frombuffer(rd(e.r32(c + 28), 4 * (nx * ny + 1)), '>u4')
    lst = np.frombuffer(rd(e.r32(c + 32), 2 * int(cells[-1])), '>u2')
    SEEN['coll'] = (t[:, :9].reshape(n, 3, 3), t[:, 9:] / 32767, x0, y0, cell, nx, ny, cells, lst)
    print('COLL tris', n, 'grid', nx, ny, 'cell', cell, 'from', round(x0), round(y0), 'to', round(x0 + nx * cell), round(y0 + ny * cell), flush=True)
    return SEEN['coll']


def closest(p, T):                                       # (peel_check.py's)
    a, b, c = T[:, 0], T[:, 1], T[:, 2]; ab, ac, ap_ = b - a, c - a, p - a
    d1, d2 = (ab * ap_).sum(1), (ac * ap_).sum(1)
    bp = p - b; d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = p - c; d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    den = va + vb + vc; den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    v, w = vb / den, vc / den; q = a + ab * v[:, None] + ac * w[:, None]
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0); u_ = d1 / np.where(d1 - d3 == 0, 1e-12, d1 - d3); q[m] = (a + ab * u_[:, None])[m]
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0); u_ = d2 / np.where(d2 - d6 == 0, 1e-12, d2 - d6); q[m] = (a + ac * u_[:, None])[m]
    m = (va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0)
    u_ = (d4 - d3) / np.where((d4 - d3) + (d5 - d6) == 0, 1e-12, (d4 - d3) + (d5 - d6)); q[m] = (b + (c - b) * u_[:, None])[m]
    m = (d1 <= 0) & (d2 <= 0); q[m] = a[m]
    m = (d3 >= 0) & (d4 <= d3); q[m] = b[m]
    m = (d6 >= 0) & (d5 <= d6); q[m] = c[m]
    return q


def depth(p, reach=160.0):                               # (peel_check.py's): < 0 behind the drawn side
    T, N, x0, y0, cell, nx, ny, cells, lst = coll(); p = np.asarray(p, float)
    i0, i1 = max(0, int((p[0] - reach - x0) // cell)), min(nx - 1, int((p[0] + reach - x0) // cell))
    j0, j1 = max(0, int((p[1] - reach - y0) // cell)), min(ny - 1, int((p[1] + reach - y0) // cell))
    if i0 > i1 or j0 > j1: return reach
    ids = set()
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1): ids.update(lst[cells[j * nx + i]: cells[j * nx + i + 1]].tolist())
    if not ids: return reach
    ids = np.fromiter(ids, int); q = closest(p, T[ids]); d = np.linalg.norm(q - p, axis=1); k = int(np.argmin(d))
    s = float(np.dot(N[ids[k]], p - q[k]))
    return float(d[k]) if s >= 0 else -float(d[k])


def cam():
    act = e.r32(ACTIVE)
    if not (0x80000000 <= act < 0x80800000): return None
    f = v3(act + 0x24); eye = v3(act + 0x44); l = math.hypot(*f) or 1; f = [x / l for x in f]
    r = [f[1], -f[0], 0]; rl = math.hypot(*r) or 1; r = [x / rl for x in r]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    return eye, f, r, u


def view(c, p):                                          # (tan x, tan y, distance along) or None behind
    eye, f, r, u = c; v = [p[j] - eye[j] for j in range(3)]; z = sum(v[j] * f[j] for j in range(3))
    if z <= 1: return None
    return sum(v[j] * r[j] for j in range(3)) / z, sum(v[j] * u[j] for j in range(3)) / z, z


def in_view(t): return t is not None and abs(t[0]) < 0.75 and abs(t[1]) < 0.56 and t[2] < 3000


def kind(i, n, ty):
    if n >= 13 and i + 7 >= n: return 'battle'
    if 10 <= i <= 13: return 'bomber'
    if i == 14: return 'bomb'
    return 'fighter' if ty == 1 else f'wave{ty}'


def stage_frame(k):
    tf, sz, n = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), e.r32(TIEF + 8)
    chor = e.r32(0x80112A78 + 0x10); cp = v3(chor + 0x50) if chor else [0, 0, 0]
    c = cam(); n = min(n, 24); SEEN['n'] += 1
    objs = []
    for i in range(n):
        t = tf + i * sz; q = v3(t + 0x50); nd = e.r32(t + 0x94); dp = v3(nd + 0x38) if 0x80000000 <= nd < 0x80800000 else q
        ty = e.r32(t + 0x70) & 0xFF; objs.append((i, t, q, dp, ty))
    if k % 120 == 0 and c:
        stft = e.r32(cls(0x53746674) + 0x10)
        print('CAM', dict(k=k, eye=[round(x) for x in c[0]], fwd=[round(x, 2) for x in c[1]], chor=[round(x) for x in cp],
                          ship=[round(x) for x in v3(stft + 0x50)] if stft else None, ship_view=view(c, v3(stft + 0x50)) if stft else None,
                          ties=[(i, [round(x) for x in dp], hex(e.r16(e.r32(t + 0x94) + 2)) if 0x80000000 <= e.r32(t + 0x94) < 0x80800000 else None,
                                 None if view(c, dp) is None else [round(x, 2) for x in view(c, dp)]) for i, t, q, dp, ty in objs[:10]]), flush=True)
    if A.rock:
        alt, free = sym('g_alt', True), sym('g_free')
        rocky = not free and alt is not None and alt < 2000
        for i, t, q, dp, ty in objs:
            if i >= 10 and kind(i, n, ty) != 'fighter': continue
            hp = f32(t + 0x60); dn = f32(SYM['g_tie_down'] + 4 * i) if i < 10 else -1
            nd = e.r32(t + 0x94); shown = (e.r16(nd + 2) >> 8) == 0xFF if 0x80000000 <= nd < 0x80800000 else False
            pv = SEEN['prev'].get(i); pdn = SEEN['down'].get(i, -1)
            if pv is not None and math.dist(pv, q) > 150:
                why = 'down/' + ('route' if rocky else 'chor') if pdn >= 0 and dn < 0 else 'far' if math.dist(pv, cp) >= 4500 else 'jump'
                dq = depth(q) if q[2] > -2000 else None
                b = dict(k=k, obj=i, why=why, rocky=rocky, alt=round(alt or 0), frm=[round(x) for x in pv], to=[round(x) for x in q],
                         to_chor=round(math.dist(q, cp)), depth=None if dq is None else round(dq, 1), hp=round(hp, 1))
                nod = e.r32(chor + 0x6C) if chor else 0; rb = rpos(max(nod - 12, 0))   # (the put-back's route point, bare)
                b.update(node=nod, route_back=[round(x) for x in rb], route_back_depth=round(depth(rb), 1),
                         route_back_chor=round(math.dist(rb, cp)), route_back_along=round(sum((rb[j] - cp[j]) * (c[1][j] if c else 0) for j in range(3))),
                         route_node_chor=round(math.dist(rpos(nod), cp)))
                SEEN['back'][i] = b; SEEN['backs'].append(b); print('BACK', b, flush=True)
            SEEN['prev'][i] = q; SEEN['down'][i] = dn
            if dp[2] < -2000 or not c: continue
            d = depth(dp)
            if d < 0:
                tv = view(c, dp); vis = shown and in_view(tv)
                live = hp > 0 and e.r16(t + 0xA8) < 0x8000 and math.dist(dp, c[0]) < 2000   # (drawn if the gun looks there)
                lb = SEEN['back'].get(i); chase = [e.r32(SYM['g_chase'] + 4 * x) for x in range(6)]
                row = dict(k=k, obj=i, slot=chase.index(t) if t in chase else -1, depth=round(d, 1), live=live, shown=shown, view=None if tv is None else [round(tv[0], 2), round(tv[1], 2), round(tv[2])],
                           vis=vis, hp=round(hp, 1), state=e.r16(t + 0xA8), down=round(dn, 2), rocky=rocky, alt=round(alt or 0),
                           pos=[round(x) for x in dp], to_chor=round(math.dist(dp, cp)),
                           last_back=None if not lb else (lb['k'], lb['why'], k - lb['k']))
                SEEN['rock'].append(row)
                if vis or (live and d < -8) or k % 30 == 0: print('ROCK', row, flush=True)
                if vis and A.shots and SEEN.setdefault('nshot', 0) < 16 and k - SEEN.get('lshot', -99) > 20:
                    SEEN['nshot'] += 1; SEEN['lshot'] = k; e.shot(); print('SHOT k', k, 'obj', i, flush=True)
    if A.panel:
        rn = e.r32(RADAR_COUNT); recs = []
        hud = {h: e.r16(HUD_XY + 4 * h) - (0x10000 if e.r16(HUD_XY + 4 * h) & 0x8000 else 0) for h in range(35, 40)}
        up = [h for h, x in hud.items() if x != -1000]
        best = None
        for j in range(min(rn, 32)):
            r = RADAR_LIST + 0x20 * j; p = v3(r + 8); w4 = e.r32(r + 4)
            own = min(objs, key=lambda o: math.dist(o[2], p)) if objs else None
            od = math.dist(own[2], p) if own else 1e9
            oi = own[0] if own and od < 50 else None
            kd = kind(oi, n, own[4]) if oi is not None else 'none'
            byp = next((o[0] for o in objs if o[1] == w4), None)
            tv = view(c, p) if c else None
            recs.append(dict(j=j, tag=e.r32(r).to_bytes(4, 'big').decode('latin1'), w4=hex(w4), obj4=byp, pos=[round(x) for x in p],
                             obj=oi, od=round(od), kind=kd, flags=hex(e.r32(r + 0x1C)), view=None if tv is None else [round(tv[0], 2), round(tv[1], 2), round(tv[2])],
                             dx=round(p[0] - cp[0])))
            if tv and abs(tv[0]) < 1.5 and abs(tv[1]) < 1.2:
                m = math.hypot(tv[0], tv[1])
                if best is None or m < best[0]: best = (m, recs[-1])
        pk = best[1]['kind'] if best else None
        SEEN['pick'][pk] = SEEN['pick'].get(pk, 0) + 1
        if 39 in up: SEEN['p39'] += 1
        hi = e.r32(0x800E1B90); hi -= (1 << 32) if hi & 0x80000000 else 0; ht_ = f32(0x8018E8AC); held = None
        if 0 <= hi < 32:                                 # the HUD's held target (0x80096564: no pick, *0x800E1B90 >= 0 and
            r = RADAR_LIST + 0x20 * hi; p = v3(r + 8)    # *0x8018E8AC > 0 -> that list slot, read past the count too)
            own = min(objs, key=lambda o: math.dist(o[2], p)) if objs else None
            held = dict(idx=hi, past_count=hi >= rn, tag=e.r32(r).to_bytes(4, 'big').decode('latin1'), flags=hex(e.r32(r + 0x1C)),
                        pos=[round(x) for x in p], dx=round(p[0] - cp[0]), obj=own[0] if own and math.dist(own[2], p) < 50 else None,
                        kind=kind(own[0], n, own[4]) if own and math.dist(own[2], p) < 50 else 'none')
        if 39 in up or (pk not in (None, 'fighter')):
            row = dict(k=k, count=rn, up=up, held=held, hold_t=round(ht_, 2), pick=best[1] if best else None, recs=recs)
            SEEN['panel'].append(row); print('PANEL', row, flush=True)
        elif k % 60 == 0: print('RADAR', dict(k=k, count=rn, up=up, pick=pk, kinds=[x['kind'] for x in recs]), flush=True)


def tie_vi(k):                                          # --rock: each VI, a TIEV line when a fighter's health / state changes
    tf, sz = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC); V = SEEN.setdefault('vi', {})   # or it jumps (who revives the downed)
    chor = e.r32(0x80112A78 + 0x10); cp = v3(chor + 0x50) if chor else [0, 0, 0]
    for i in range(10):
        t = tf + i * sz; q = v3(t + 0x50); hp = round(f32(t + 0x60), 1); st_ = e.r16(t + 0xA8); st_ -= 65536 if st_ > 32767 else 0
        o = V.get(i)
        if o and (o[0] != hp or o[1] != st_ or math.dist(o[2], q) > 150):
            c = cam(); tv = view(c, q) if c else None
            print('TIEV', dict(k=k, obj=i, hp=(o[0], hp), state=(o[1], st_), frm=[round(x) for x in o[2]], to=[round(x) for x in q],
                               to_chor=round(math.dist(q, cp)), view=None if tv is None else [round(x, 2) for x in tv],
                               lead=(e.r32(t + 0xBC) - tf) // sz if tf <= e.r32(t + 0xBC) < tf + 32 * sz else None,
                               ticks=hex(e.r32(t + 0xAC)), d=round(depth(q), 1) if q[2] > -2000 else None), flush=True)
        V[i] = (hp, st_, q)


def stage_sum():
    print('RSUM frames', SEEN['n'], 'puts back', len(SEEN['backs']), 'by why', {w: sum(1 for b in SEEN['backs'] if b['why'] == w) for w in sorted({b['why'] for b in SEEN['backs']})})
    if A.rock:
        R = SEEN['rock']; V = [r for r in R if r['vis']]; L = [r for r in R if r['live']]
        print('RSUM frames-objs in rock', len(R), 'of them shown and in view', len(V), 'objects', sorted({r['obj'] for r in V}),
              '| live within 2000 of the eye (seen if the gun looks there)', len(L), 'deeper than 8', sum(1 for r in L if r['depth'] < -8))
        for o in sorted({r['obj'] for r in L}):
            ro = [r for r in L if r['obj'] == o]
            print('RSUM live in rock obj', o, 'frames', len(ro), 'deeper than 8', sum(1 for r in ro if r['depth'] < -8), 'deepest', min(r['depth'] for r in ro),
                  'slots', sorted({r['slot'] for r in ro}), 'rocky', sorted({r['rocky'] for r in ro}), 'shown', sum(1 for r in ro if r['shown']),
                  'k', ro[0]['k'], '..', ro[-1]['k'], 'after put-backs', sorted({r['last_back'][1] for r in ro if r['last_back']}))
        by = {}
        for r in V:
            w = r['last_back'][1] if r['last_back'] else 'no put-back'
            by.setdefault(w, []).append(r)
        for w, rs in by.items():
            print('RSUM vis in rock after', w, 'frames', len(rs), 'deepest', min(x['depth'] for x in rs), 'frames after the put-back',
                  sorted({x['last_back'][2] for x in rs if x['last_back']})[:12], 'k', rs[0]['k'], '..', rs[-1]['k'])
        for b in SEEN['backs']:
            if b['depth'] is not None and b['depth'] < 0: print('RSUM put back into rock', b)
    if A.panel:
        print('PSUM frames', SEEN['n'], 'picks by kind', SEEN['pick'], 'frames with 39 up', SEEN['p39'], 'PANEL lines', len(SEEN['panel']))


POKES = [tuple(int(x, 16) for x in p.split('=')) for p in A.poke.split(',') if p]


def w16(a, v):
    w = e.r32(a & ~3); sh = 16 if (a & 2) == 0 else 0
    e.w32(a & ~3, (w & ~(0xFFFF << sh)) | ((v & 0xFFFF) << sh))


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(start)
    if n < 64: return
    k = n - 64
    lvl, hold = e.r16(LEVEL), e.r16(HOLD)
    if not S['saved']:
        S['h'] = S['h'] + 1 if hold else 0
        pad = (BTN['A'] if S['h'] >= 30 and S['h'] % 60 < 5 else 0, 0, 0)
        if lvl == MLV and e.r32(SYM['g_gallrun']) and not hold:
            chor = e.r32(0x80112A78 + 0x10); node = e.r32(chor + 0x6C) if chor else 0; sw = e.r32(GALL + 48)
            if node < sw: pad = pilot(node)
            elif node >= sw + 2 and not e.r32(SYM['g_pilot']):
                e.save_state(STATE); S['saved'] = True; print(k, 'saved', STATE, 'node', node, 'sw', sw, flush=True)
        mp = A.make_pause
        if mp >= 0 and mp <= k < mp + 4: pad = (BTN['START'], 0, 0)
        elif mp >= 0 and mp + 4 <= k < mp + 60: pad = (0, 0, 0)
        elif mp >= 0 and mp + 60 <= k < mp + 64: pad = (BTN['A'], 0, 0); print(k, 'make: resume A, idx', e.r32(INDEX), 'pend', e.r32(PEND), flush=True)
        e.pad(*pad)
        if k > 60 * 60 * 10: print('timeout'); e.stop()
        return
    if S['k0'] is None: S['k0'] = k; e.unlimit(False)
    for a, v in POKES: w16(a, v)
    j = k - S['k0']
    if A.rock or A.panel:                                    # (R2: the bot to the end scene)
        pad = (BTN['A'] if hold and j % 40 < 4 else BTN['B'] if not hold and j % 6 < 3 else 0, 0, 0)
        e.pad(*pad)
        if A.rock: tie_vi(j)
        if j % 2 == 0: stage_frame(j)
        if (j > 120 and e.r32(SYM['g_cine']) == 1) or j > A.secs * 60 or lvl != MLV:
            print('END k', j, 'cine', e.r32(SYM['g_cine']), 'level', lvl, flush=True); e.stop()
        return
    pad, lab = (0, 0, 0), ''
    if A.pause >= 0:
        if A.pause <= j < A.pause + 4: pad, lab = (BTN['START'], 0, 0), 'START'
        elif A.pause + 60 <= j < A.pause + 64: pad, lab = (BTN['A'], 0, 0), 'A (resume)'
        if j < A.pause + 100:
            e.pad(*pad); measure(j - A.pause - 100, lab); return
        j -= A.pause + 100
    if hold: pad, lab = ((BTN['A'] if j % 40 < 4 else 0), 0, 0), 'line held: A'
    else:
        for a, b, btn, x, y, l in SCRIPT:
            if a <= j < b: pad, lab = ((BTN[btn] if btn else 0), x, y), l
    e.pad(*pad)
    measure(j, lab)
    if A.shots and j in SHOT_AT: e.shot()
    if j >= END: e.stop()


e.run(script)
if A.rock or A.panel: stage_sum()
R = S['rows']
if R:
    def rng(key, sel): v = [r[key] for r in R if sel(r)]; return (min(v), max(v)) if v else None
    print('SUM build', BUILD, 'frames', len(R))
    for a, b, btn, x, y, l in SCRIPT:
        sel = lambda r, a=a, b=b: a <= r['k'] < b + 20
        print('SUM', l, f'k {a}-{b}+20', 'idx', sorted({r['idx'] for r in R if sel(r)}), 'vm', sorted({r['vm'] for r in R if sel(r)}),
              'gun_yaw', rng('gun_yaw', sel), 'cam_yaw', rng('cam_yaw', sel))
    print('SUM sec', sorted({r['sec'] for r in R}), 'sky', sorted({r['sky'] for r in R}), 'nat', sorted({r['nat'] for r in R}), 'pend', sorted({r['pend'] for r in R}),
          'guns', sorted({r['guns'] for r in R}), 'rail', sorted({r['rail'] for r in R}), 'shot', sorted({r['shot'] for r in R}))
    bs = S['bolts']
    if bs:
        dg = [b['dist_gun'] for b in bs if b['dist_gun'] is not None]
        print('SUM bolts', len(bs), 'owners', sorted({b['owner'] for b in bs}), 'dist to guns min/med/max',
              (min(dg), sorted(dg)[len(dg) // 2], max(dg)) if dg else None)
