"""Stage 1's Outrider break-off check (gall_story.c outrider(): on along the route spline at g_or_f, climbing
OR_PEEL_UP x pt^2 over the route + g_or_dz, hidden after OR_PEEL_T): per game frame of the break-off its time, height
g_or_dz, climb (its height over the route spline + g_or_dz), pitch (deg, its forward row), off (xy distance from the
route spline at g_or_f), push (collide() would move it: the rock push acted), drawn or not, and how deep in rock its
centre and its hull are (the hull: its meshes' part boxes, the face centres and the box corners, in the node's rows;
"in rock" = behind the drawn side of the nearest stage 1 collision triangle, IMG_COLL read from RAM).

    M64CPU=2 SHOTS=pt7r_peel .venv/bin/python3 gallrun/peel_check.py <build>/sote-patch.z64 [--make BASE] [--dz D] [--sheet] [--check]

  --make BASE  make run/<build>_peel.st first: from BASE (a state in Cut 05 or the mission, e.g. run/<build>_c05_f8.st),
               holds let go with A, stage 1 flown by the take's pilot (work/chain_take.py), saved PEEL_LEAD nodes before
               the break-off; the run then goes on into the break-off (a first trace)
  --dz D       the pilot flies D units off its usual height (the route's - 10) from the state on (default 0)
  --follow     from the state on the pilot heads at the Outrider (it stays in the shots)
  --sheet      a shot each game frame of the break-off and a contact sheet run/<build>_peel_dz<D>.png
  --side D     the pilot aims D units to the right of the route (negative: left) from the state on: into a wall
  --hits SEC   stage 1's wall hits (gall_fly.c hit()) for SEC seconds from the state instead of the break-off trace:
               a HIT line at each (g_hit_t back to 0: health, speed share, shake, paused), with --sounds the game's sound
               calls (sndlog.py, needs M64CPU=0); summary: hits, the hit sound's calls (--snd-id, default 0x4B the rock's; was 0x54) per volume, head on / glancing (g_fly_thr cut by HIT_SLOW at the hit or not): vol,
               pitch, channel; the least gap
               between two (s), any while paused
  --weave T    (with --side) the side flips every T seconds (wall to wall: fresh touches)
  --sounds     (with --hits) the sound-call log
  --pause K0:K1  (with --hits) START tapped at k K0 and K1 (the pause screen up between them)
  --check      PASS / FAIL on three: (a) no drawn frame with a hull face or box corner in rock; (b) off <= 5 on every
               drawn frame the push did not act on (the push's frames listed); (c) pitch >= 25 deg by pt 0.5 and, on the
               last drawn frame, the Outrider above the highest rock vertex within 250 of it (xy)
  --lines      the radio lines said in the run (g_line rising): a LINE row each at the end (its index, k, held = the
               image's text starts with ~h, the VIs MSG_HOLD stays set, the largest hit-tint alpha (SCREEN_FADE at
               HIT_TINT's colours) during the hold and after its second VI, or_pt: the break-off's g_or_pt as it is said, 0 before it), a shot at the 20th VI of each hold; with
               --check: every ~h line held >= LINE_HOLD_MIN_F (45), every unmarked line held 0, no tint after a held
               line's second VI, HUD 51 ("Missiles: n") at -1000 under every line said while stage 1 is flown (g_pilot;
               the row's hud51 x: its x over the say's first 60 VIs) (CHECK (lines) PASS / FAIL); with --lines the run goes on past
               the break-off till Chewie's sound row (stage 1's last line, Lando's, let go)
Held lines are let go with A (30 VIs on, every 60 VIs), in the --make run and in the trace.
Prints PEEL lines (one per game frame of the break-off), a summary (CHECK lines with --check)."""
import os, sys, math, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
ap = argparse.ArgumentParser()
ap.add_argument('rom'); ap.add_argument('--make', default=''); ap.add_argument('--dz', type=float, default=0)
ap.add_argument('--sheet', action='store_true'); ap.add_argument('--state', default='')
ap.add_argument('--follow', action='store_true'); ap.add_argument('--side', type=float, default=0)
ap.add_argument('--hits', type=float, default=0); ap.add_argument('--sounds', action='store_true'); ap.add_argument('--pause', default=''); ap.add_argument('--weave', type=float, default=0)
ap.add_argument('--check', action='store_true'); ap.add_argument('--lines', action='store_true')
ap.add_argument('--snd-id', dest='snd_id', type=lambda x: int(x, 0), default=0x4B)
A = ap.parse_args()
ROM = os.path.abspath(A.rom)
BUILD = os.path.basename(os.path.dirname(ROM))
os.environ.setdefault('SHOTS', f'pt7r_peel_{BUILD}')
import ctypes as C
import numpy as np
import paths
import m64
from m64 import Emu, BTN, HERE

RUN = paths.RUN
ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
MLV = 32 if 'g_levels' in SYM else 6           # the mission's sub-level (32 from bf49)
LEVEL, HOLD, GALL = 0x8013CE0E, 0x800DD2D0, 0x80628000
FADE, HIT_TINT, LINE_HOLD_MIN_F, IMG_LINES, LINE_SIZE = 0x800D0804, (255, 128, 0), 45, 80, 16   # (gall.h, gallrun.c)
OR_PEEL, OR_PEEL_T, OR_PEEL_ACC, OR_PEEL_UP, OR_R, SHIP_DROP, FLY_V = 40, 1.8, 1.2, 350.0, 12.0, 10.0, 300.0
OR_MESHES = (0x801A3C64, 0x801A3C7C, 0x801A3C94)
PEEL_LEAD = int(os.environ.get('PEEL_LEAD', '45'))       # nodes before the break-off the state is saved
STATE = A.state or os.path.join(RUN, f'{BUILD}_peel.st')
start = A.make or STATE
if not os.path.exists(start): sys.exit(f'no {start}: make it with --make <state in Cut 05 or the mission>')
e = Emu(ROM, video=m64.GLN); f32 = e.rf
S = {'lshots': [], 'h': 0, 'peel': [], 'saved': not A.make, 'pt': None, 'shots': [], 'end': None, 'coll': None}


def v3(a): return [f32(a + 4 * i) for i in range(3)]


def rd(a, n):                                            # bytes as the N64 sees them (RDRAM holds LE words)
    a0 = a & 0x7FFFFC; m = (a - (a & ~3)) + n
    raw = C.string_at(e.rdram() + a0, (m + 3) & ~3)
    return np.frombuffer(raw, '<u4').astype('>u4').tobytes()[a & 3: (a & 3) + n]


def coll():
    """Stage 1's collision triangles (world units) and normals, and the cell grid, from RAM (collide.py's layout)."""
    if S['coll']: return S['coll']
    c = e.r32(GALL + 108); n, tris = e.r32(c), e.r32(c + 4)
    x0, y0, cell = f32(c + 8), f32(c + 12), f32(c + 16); nx, ny = e.r32(c + 20), e.r32(c + 24)
    t = np.frombuffer(rd(tris, 24 * n), '>i2').reshape(n, 12).astype(np.float64)
    cells = np.frombuffer(rd(e.r32(c + 28), 4 * (nx * ny + 1)), '>u4')
    lst = np.frombuffer(rd(e.r32(c + 32), 2 * int(cells[-1])), '>u2')
    S['coll'] = (t[:, :9].reshape(n, 3, 3), t[:, 9:] / 32767, x0, y0, cell, nx, ny, cells, lst)
    return S['coll']


def closest(p, T):
    """Closest points on triangles T (m,3,3) to p (Ericson's region test, vectorised)."""
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


def c_touch(p, r=OR_R):
    """collide()'s verdict for a sphere r at p: a triangle counts only with p in front of its plane, nearer than r."""
    T, N, x0, y0, cell, nx, ny, cells, lst = coll(); p = np.asarray(p, float)
    i0, i1 = max(0, int((p[0] - r - x0) / cell)), min(nx - 1, int((p[0] + r - x0) / cell))
    j0, j1 = max(0, int((p[1] - r - y0) / cell)), min(ny - 1, int((p[1] + r - y0) / cell))
    ids = set()
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1): ids.update(lst[cells[j * nx + i]: cells[j * nx + i + 1]].tolist())
    if not ids: return 0
    ids = np.fromiter(ids, int); fr = (N[ids] * (T[ids, 0] - p)).sum(1) <= 0
    if not fr.any(): return 0
    d = np.linalg.norm(closest(p, T[ids[fr]]) - p, axis=1)
    return int((d < r).any())


def depth(p, reach=160.0):
    """Signed distance of p to the nearest collision surface: < 0 behind its drawn side (in rock); +reach: none near."""
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


def hull_box():
    lo, hi = [1e9] * 3, [-1e9] * 3
    for m in OR_MESHES[1:]:
        for i in range(e.r32(m + 0xC)):
            pp = e.r32(e.r32(m + 0x10) + 4 * i)
            for j in range(3): lo[j] = min(lo[j], f32(pp + 4 * j)); hi[j] = max(hi[j], f32(pp + 12 + 4 * j))
    return lo, hi


def hull_pts(n, lo, hi):
    """World points of the hull's box: 6 face centres (nose, tail, right, left, top, bottom) and 8 corners."""
    P = v3(n + 0x38); R = [v3(n + 0x14 + 12 * i) for i in range(3)]; c = [(lo[j] + hi[j]) / 2 for j in range(3)]
    loc = []
    for ax, nm in ((1, 'nose'), (1, 'tail'), (0, 'right'), (0, 'left'), (2, 'top'), (2, 'bottom')):
        q = list(c); q[ax] = hi[ax] if nm in ('nose', 'right', 'top') else lo[ax]; loc.append((nm, q))
    for i in range(8): loc.append(('c%d' % i, [hi[0] if i & 1 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 4 else lo[2]]))
    return [(nm, [P[j] + sum(l[i] * R[i][j] for i in range(3)) for j in range(3)]) for nm, l in loc]


def rpos(k):
    rt = e.r32(GALL + 20) + 0x38
    return [f32(rt + k * 0x54 + 4 * i) for i in range(3)]


def pilot(node):                                         # work/chain_take.py's, + --dz
    if not e.r32(SYM['g_fly_on']): return 0, 0, 0
    pos = v3(SYM['g_fly_pos']); tp = rpos(node + 6); yaw = f32(SYM['g_fly_yaw'])
    if A.follow and S['saved'] and f32(SYM['g_or_f']) > 0:   # (--follow: heading at the Outrider, the route's height)
        o = v3(e.r32(SYM['g_or_node']) + 0x38); tp = [o[0], o[1], tp[2]]
    if A.side and S['saved']:                            # (--side: aimed off the route, to its right)
        q = rpos(node + 5); hx, hy = tp[0] - q[0], tp[1] - q[1]; hl = math.hypot(hx, hy) or 1
        sd = -A.side if A.weave and int(S.get('k', 0) / 60 / A.weave) % 2 else A.side
        tp = [tp[0] + sd * hy / hl, tp[1] - sd * hx / hl, tp[2]]
    err = (math.atan2(tp[1] - pos[1], tp[0] - pos[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
    dz = A.dz if S['saved'] else 0
    return BTN['A'], max(-80, min(80, int(-err * 160))), max(-80, min(80, int(-(tp[2] - 10 + dz - pos[2]) * 2)))


def spline(f, sw):
    """outrider()'s route place at f (Catmull-Rom through the nodes, clamped to sw - 3)."""
    f = min(f, sw - 3); k = int(f); fr = f - k
    c0, a, b, c3 = rpos(max(k - 1, 0)), rpos(k), rpos(k + 1), rpos(k + 2); t2, t3 = fr * fr, fr * fr * fr
    return [0.5 * (2 * a[i] + (b[i] - c0[i]) * fr + (2 * c0[i] - 5 * a[i] + 4 * b[i] - c3[i]) * t2
                   + (3 * a[i] - c0[i] - 3 * b[i] + c3[i]) * t3) for i in range(3)]


def rock_top(p, reach=250.0):
    """The highest collision vertex within reach (xy) of p."""
    T = coll()[0].reshape(-1, 3); m = np.hypot(T[:, 0] - p[0], T[:, 1] - p[1]) <= reach
    return float(T[m, 2].max()) if m.any() else None


L = None
if A.hits:
    from sndlog import SndLog
    L = SndLog(e, quiet=(), out=lambda t: (S.setdefault('snd', []).append(t), print(t, flush=True) if f' id {A.snd_id} ' in t or 'stub' in t else None))
PZ = [int(x) for x in A.pause.split(':')] if A.pause else []
H = {'prev': None, 'hits': [], 'sfx': [], 'head': {}, 'thr': None}


def hits_frame(k):
    """--hits: one frame of the wall-hit log."""
    if k == 0 and A.sounds: L.install()
    if A.sounds:
        n0 = len(S.get('snd', [])); L.read(k)
        for t in S.get('snd', [])[n0:]:
            w = t.split()
            if w[0] == 'SND' and w[3] == 'fx' and w[7] == str(A.snd_id):
                H['sfx'].append((k, int(w[13]), e.r32(0x800DD2BC), float(w[11]), int(w[9]), H['head'].get(k)))
    ht = f32(SYM['g_hit_t']); stft = next((e.r32(0x80112808 + 0x30 * i + 0x10) for i in range(64)
                                           if e.r32(0x80112808 + 0x30 * i) == 0x53746674), 0)   # (the Stft's class record)
    thr = f32(SYM['g_fly_thr'])
    if H['prev'] is not None and ht < H['prev']:
        H['hits'].append(k)
        H['head'][k] = bool(H['thr'] and thr < H['thr'] * 0.85)     # head on: g_fly_thr x HIT_SLOW 0.7 (a slide: not)
        print(f'HIT k {k} hit_t was {H["prev"]:.3f} health {e.r32(stft + 0x240) if stft else -1} thr {f32(SYM["g_fly_thr"]):.2f}'
              f' shake {f32(SYM["g_shake"]):.2f} paused {e.r32(0x800DD2BC)}', flush=True)
    H['prev'] = ht; H['thr'] = thr
    if k % 30 == 0 and e.r32(SYM['g_fly_on']):            # (where the pilot is: node, off the route, nearest rock)
        chor = e.r32(0x80112A78 + 0x10); node = e.r32(chor + 0x6C) if chor else 0; pos = v3(SYM['g_fly_pos'])
        q0, q1 = rpos(node), rpos(node + 1); hx, hy = q1[0] - q0[0], q1[1] - q0[1]; hl = math.hypot(hx, hy) or 1
        off = ((pos[0] - q0[0]) * hy - (pos[1] - q0[1]) * hx) / hl
        print(f'FLY k {k} node {node} sw {e.r32(GALL + 48)} right {off:.1f} dz {pos[2] - q0[2]:.1f} rock {depth(pos):.0f} hold {e.r16(HOLD)} paused {e.r32(0x800DD2BC)}', flush=True)


LN = {'rows': [], 'last': 0}


def lines_frame(k, hold):
    """--lines: one VI of the radio lines' log (a row per g_line step; the hold and the hit tint under it)."""
    g = e.r32(SYM['g_line'])
    if g > LN['last']:
        for i in range(LN['last'], g):
            ent = e.r32(GALL + IMG_LINES + 4) + i * LINE_SIZE; tp = e.r32(ent + 8)
            txt = rd(tp, 64).split(b'\0')[0].decode('latin-1') if tp else None
            r = dict(i=i, k=k, held=bool(txt and txt.startswith('~h')), text=txt, hold=0, tint=0, tint2=0, pilot=e.r32(SYM['g_pilot']), or_pt=round(f32(SYM['g_or_pt']), 3), x51=set())
            LN['rows'].append(r); print('SAY', r, flush=True)
        LN['last'] = g
    if LN['rows'] and k - LN['rows'][-1]['k'] < 60 and LN['rows'][-1]['hold'] < 60:             # HUD 51 "Missiles: n" x (hidden while stage 1 is flown)
        x = e.r16(0x80111110 + 4 * 51); LN['rows'][-1]['x51'].add(x - 0x10000 if x >= 0x8000 else x)
    if not LN['rows'] or not hold: return
    r = LN['rows'][-1]; r['hold'] += 1
    rgb, a = tuple(e.r16(FADE + 2 * j) for j in range(3)), e.r16(FADE + 6)
    a = a - 0x10000 if a >= 0x8000 else a
    if rgb == HIT_TINT and a > 0:
        r['tint'] = max(r['tint'], a)
        if r['hold'] > 2: r['tint2'] = max(r['tint2'], a)
    if r['hold'] == 20: e.shot(); S['lshots'].append(r['i'])


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(start)
    if n < 64: return
    k = n - 64
    S['k'] = k
    if A.hits:
        hits_frame(k)
        if k >= A.hits * 60: S['end'] = f'{A.hits:g} s of hits'; e.stop(); return
        if any(0 <= k - z < 6 for z in PZ): e.pad(BTN['START']); return
        if PZ and PZ[0] <= k < PZ[1]: e.pad(0); return          # (paused: nothing held, A would pick Resume)
    lvl, hold = e.r16(LEVEL), e.r16(HOLD)
    if A.lines and lvl == MLV and e.r32(SYM['g_gallrun']): lines_frame(k, hold)
    S['h'] = S['h'] + 1 if hold else 0
    pad = (BTN['A'] if S['h'] >= 30 and S['h'] % 60 < 5 else 0, 0, 0)
    if lvl == MLV and e.r32(SYM['g_gallrun']) and not hold:
        chor = e.r32(0x80112A78 + 0x10); node = e.r32(chor + 0x6C) if chor else 0; sw = e.r32(GALL + 48)
        if node < sw: pad = pilot(node)
        orf, pt = f32(SYM['g_or_f']), f32(SYM['g_or_pt'])
        if not S['saved'] and orf >= sw - OR_PEEL - PEEL_LEAD and pt == 0:
            e.save_state(STATE); S['saved'] = True; print(k, 'saved', STATE, 'or_f', round(orf, 1), 'sw', sw, flush=True)
        if S['saved'] and pt > 0 and pt != S['pt'] and not A.hits and not S.get('over'):
            if S['pt'] is None:
                S['k0'] = k; S['box'] = hull_box(); e.unlimit(False)
                print('PEEL start k', k, 'or_dz', round(f32(SYM['g_or_dz']), 1), 'ship_off z', round(f32(SYM['g_ship_off'] + 8), 1),
                      'fly_pos z', round(f32(SYM['g_fly_pos'] + 8), 1), 'hull box', [[round(x, 1) for x in b] for b in S['box']], flush=True)
            S['pt'] = pt
            nd = e.r32(SYM['g_or_node']); shown = e.r16(nd + 2) >> 8 == 0xFF; P = v3(nd + 0x38)
            c_d = depth(P) if shown else None
            hp = [(nm, depth(q)) for nm, q in hull_pts(nd, *S['box'])] if shown else []
            worst = min(hp, key=lambda x: x[1]) if hp else ('-', 0)
            face = min((x for x in hp if not x[0].startswith('c')), key=lambda x: x[1]) if hp else ('-', 0)
            dz = f32(SYM['g_or_dz']); sp = spline(f32(SYM['g_or_f']), sw); fw = v3(nd + 0x14 + 12)
            want = [sp[0], sp[1], sp[2] + dz + OR_PEEL_UP * pt * pt - SHIP_DROP]   # where it is unless pushed
            top = rock_top(P) if shown else None
            r = dict(k=k, pt=round(pt, 3), dz=round(dz, 1), climb=round(P[2] + SHIP_DROP - sp[2] - dz, 1),
                     pitch=round(math.degrees(math.atan2(fw[2], math.hypot(fw[0], fw[1]))), 1),
                     off=round(math.hypot(P[0] - sp[0], P[1] - sp[1]), 1), push=c_touch(want), shown=int(shown),
                     pos=[round(x) for x in P], over_top=None if top is None else round(P[2] - top),
                     centre=None if c_d is None else round(c_d), face=(face[0], round(face[1])), corner=(worst[0], round(worst[1])))
            S['peel'].append(r)
            print('PEEL', r, flush=True)
            if A.sheet and shown: e.shot(); S['shots'].append(f'pt {pt:.2f} c {r["centre"]} hull {face[1]:.0f} pitch {r["pitch"]}')
        if S['pt'] is not None and not S.get('over') and (pt > OR_PEEL_T + 0.3 or k > S['k0'] + 200 or e.r32(SYM['g_cine'])):
            S['over'] = k                                    # (--lines: on till stage 1's last line, Lando's, is let go:
        if S.get('over') and (not A.lines or any(r['text'] is None for r in LN['rows']) or k > S['over'] + 1800):   # the row after it is Chewie's sound)
            S['end'] = 'break-off over' + (', stage 1\'s lines said' if A.lines else ''); e.stop(); return
    e.pad(*pad)
    if k > 60 * 60 * 8: S['end'] = 'timeout'; e.stop()


e.run(script)
print(f'peel check, build {BUILD}, dz {A.dz}, side {A.side:g}, from {os.path.basename(start)}: {S["end"]}')
if A.hits:
    print('  hits', len(H['hits']), 'at k', H['hits'])
    if A.sounds:
        sf = H['sfx']; vols = {}
        for x in sf: vols[x[1]] = vols.get(x[1], 0) + 1
        gaps = [(b[0] - a[0]) / 60 for a, b in zip(sf, sf[1:])]
        sf = [x[:5] + (H['head'].get(x[0]),) for x in sf]          # (the hit's frame tagged after its sound was read)
        for tag, want in (('head on', True), ('glancing', False)):
            g = [x for x in sf if x[5] is want]
            if g: print(f'  {tag}: calls', len(g), 'vol min/max', min(x[1] for x in g), max(x[1] for x in g),
                        'pitch min/max', round(min(x[3] for x in g), 3), round(max(x[3] for x in g), 3), 'ch', sorted({x[4] for x in g}))
        print('  not at a hit frame', [(x[0], x[1]) for x in sf if x[5] is None])
        print(f'  sound calls (id {A.snd_id:#x})', len(sf), 'per volume', {hex(v): c for v, c in vols.items()},
              'least gap s', round(min(gaps), 3) if gaps else None, 'while paused', sum(1 for x in sf if x[2]),
              'at a hit frame', sum(1 for x in sf if x[0] in H['hits']))
pe = S['peel']
if pe:
    shown = [r for r in pe if r['shown']]
    print('  start dz', pe[0]['dz'], 'frames drawn', len(shown), 'of', len(pe), 'last drawn pt', shown[-1]['pt'] if shown else None)
    inr = [r for r in shown if r['face'][1] < 0 or r['corner'][1] < 0]
    print('  drawn frames with a hull face or corner in rock:', len(inr), 'first pt', inr[0]['pt'] if inr else None,
          'deepest', min((min(r['face'][1], r['corner'][1]) for r in inr), default=0),
          'centre in rock:', sum(1 for r in shown if r['centre'] < 0))
    free = [r for r in shown if not r['push']]; pushed = [r['pt'] for r in shown if r['push']]
    moff = max((r['off'] for r in free), default=0)
    at5 = next((r for r in shown if r['pt'] >= 0.5), None); last = shown[-1] if shown else None
    print('  max off (push not acting)', moff, '| push frames (pt)', pushed, '| pitch at pt', at5 and at5['pt'], at5 and at5['pitch'],
          '| last drawn: climb', last and last['climb'], 'over the rock top', last and last['over_top'])
    if A.check:
        ok = [not inr, moff <= 5, bool(at5 and at5['pitch'] >= 25 and last['over_top'] is not None and last['over_top'] > 0)]
        for nm, o, why in zip('abc', ok, (f'{len(inr)} drawn frames in rock', f'max off {moff}',
                                          f'pitch {at5 and at5["pitch"]} at pt {at5 and at5["pt"]}, over the top {last and last["over_top"]}')):
            print(f'CHECK ({nm}) {"PASS" if o else "FAIL"}: {why}')
        print('CHECK', 'PASS' if all(ok) else 'FAIL')
if A.lines:
    bad = []
    for r in LN['rows']:
        print(f"LINE {r['i']} k {r['k']} held {int(r['held'])} hold_vi {r['hold']} tint {r['tint']} tint_after2 {r['tint2']} pilot {r['pilot']} or_pt {r['or_pt']} hud51 x {sorted(r['x51'])} {r['text']!r}")
        if r['pilot'] and r['x51'] != {-1000}: bad.append(f"line {r['i']} HUD 51 x {sorted(r['x51'])} in stage 1 (not -1000)")
        if r['held'] and r['hold'] < LINE_HOLD_MIN_F: bad.append(f"line {r['i']} held {r['hold']} < {LINE_HOLD_MIN_F}")
        if not r['held'] and r['hold']: bad.append(f"line {r['i']} unmarked, held {r['hold']}")
        if r['held'] and r['tint2'] > 0: bad.append(f"line {r['i']} tint {r['tint2']} after the second VI")
    if S['lshots']:
        d = os.path.join(RUN, 'shots', os.environ['SHOTS'])
        files = sorted(f for f in os.listdir(d) if f.endswith('.png'))
        print('  line shots', [(i, os.path.join(d, f)) for i, f in zip(S['lshots'], files[:len(S['lshots'])])])
    if A.check: print('CHECK (lines)', 'PASS' if not bad and LN['rows'] else 'FAIL', '; '.join(bad) or f"{len(LN['rows'])} lines")
if S['shots']:
    from PIL import Image, ImageDraw
    d = os.path.join(RUN, 'shots', os.environ['SHOTS'])
    files = sorted(f for f in os.listdir(d) if f.endswith('.png'))[-len(S['shots']):]
    W, H, Cn = 320, 240, 4
    sheet = Image.new('RGB', (W * Cn, (H + 14) * ((len(files) + Cn - 1) // Cn)), 'white')
    for i, (f, lab) in enumerate(zip(files, S['shots'])):
        x, y = W * (i % Cn), (H + 14) * (i // Cn)
        sheet.paste(Image.open(os.path.join(d, f)).convert('RGB').resize((W, H)), (x, y + 14))
        ImageDraw.Draw(sheet).text((x + 3, y + 1), lab, fill='black')
    out = os.path.join(RUN, f'{BUILD}_peel_dz{A.dz:g}{"_f" if A.follow else ""}.png'); sheet.save(out); print('  sheet', out)
