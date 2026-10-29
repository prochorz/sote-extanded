"""Stage 1's Outrider pace check (gall_story.c outrider()): per game frame of
stage 1 (from a state on) the Outrider's drawn place and its step, g_or_f, the gap to the Falcon (route nodes: g_or_f -
Chor's node + 1 + t, and world units to g_fly_pos), g_or_rate, g_or_dz and its clamp bounds (lo -FLY_LOW, hi corridor(k,
3) - OR_R), the rock push (the drawn place - the spline place + g_or_dz, recomputed from the route in RAM), the frame's
dt, and its screen place (the active camera's rows and fovy). Jerks: a step over 3x the run's median step, or a screen
jump (the change of its screen velocity) over 6 px; each one with the terms that moved.

    M64CPU=2 SHOTS=orp_s .venv/bin/python3 gallrun/or_pace.py <build>/sote-patch.z64 --make run/<build>_echo.st
    M64CPU=2 SHOTS=orp_s .venv/bin/python3 gallrun/or_pace.py <build>/sote-patch.z64 --from s [--dz D] [--look L]
        [--a hold|none|pulse] [--follow] [--frames N] [--shots k,k,...] [--csv out.csv]

  --make BASE  from BASE (run/<build>_echo.st: debug This Level -> Cut 05, its holds let go with A) stage 1 flown by the
               pilot (work/chain_take.py's); saves run/<build>_or_s.st (the Falcon flown, ~MAKE_S nodes in) and
               run/<build>_or_m.st (half way to the switch), then stops
  --from s|m   the state to start from (s: near stage 1's start, m: mid-stage)
  --dz D       the pilot flies D units off its usual height (the route's - 10)
  --look L     the pilot heads at route node + L (default 6; more cuts the bends)
  --a          A held (default: FLY_BOOST), none (cruise drops to FLY_MIN), pulse (on 1 s of every 2)
  --follow     the pilot heads at the Outrider (the route's height): a catch-up attempt
  --shots      a shot at these k (game VI frames from the state); a contact sheet run/<build>_orp_<tag>.png
  --cam        the camera too: per game frame the active camera's eye and g_fly_on (the route
               camera, gall_cam.c, reads the corridor's up only while not flown); a summary: frames not flown, the eye's
               height over the Falcon, eye jumps (the change of the eye's velocity in a game frame over EYE_TH u/s,
               default 250); the csv gets eye, fz, flyon
Prints JERK lines and a summary (the least gap, where, frames under 2 nodes)."""
import os, sys, math, subprocess, argparse, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
ap = argparse.ArgumentParser()
ap.add_argument('rom'); ap.add_argument('--make', default=''); ap.add_argument('--from', dest='frm', default='s')
ap.add_argument('--dz', type=float, default=0); ap.add_argument('--look', type=int, default=6)
ap.add_argument('--a', default='hold'); ap.add_argument('--follow', action='store_true')
ap.add_argument('--frames', type=int, default=0); ap.add_argument('--shots', default='')   # frames: 90 s, --make 30000
ap.add_argument('--csv', default=''); ap.add_argument('--quiet', action='store_true')
ap.add_argument('--cam', action='store_true')
A = ap.parse_args()
A.frames = A.frames or (30000 if A.make else 60 * 90)
ROM = os.path.abspath(A.rom)
BUILD = os.path.basename(os.path.dirname(ROM))
TAG = A.make and 'make' or f'{A.frm}_dz{A.dz:g}_l{A.look}_{A.a}{"_f" if A.follow else ""}'
os.environ.setdefault('SHOTS', f'orp_{BUILD}_{TAG}')
import struct
import paths
import m64
from m64 import Emu, BTN, HERE
from debugmenu import set_debug, set_cursor

RUN = paths.RUN
ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
MLV = 32 if 'g_levels' in SYM else 6
LEVEL, HOLD, GALL, CHOR_REC, CAM, PERSP, FRAME_DT = 0x8013CE0E, 0x800DD2D0, 0x80628000, 0x80112A78, 0x800D08A4, 0x80192F14, 0x8018E998
IMG_SWITCH, IMG_CORRIDOR = 48, 72
OR_R, SHIP_DROP, FLY_LOW, NODE_UNITS, OR_PEEL = 12.0, 10.0, 400.0, 36.0, 40
MAKE_S = int(os.environ.get('MAKE_S', '12'))
ST = {x: os.path.join(RUN, f'{BUILD}_or_{x}.st') for x in 'sm'}
start = A.make or ST[A.frm]
if not os.path.exists(start): sys.exit(f'no {start}: make it with --make run/{BUILD}_echo.st')
SHOTK = [int(x) for x in A.shots.split(',') if x]
e = Emu(ROM, video=m64.GLN); f32 = e.rf
S = {'lines': [], 'lq': 0, 'slit': 0, 'peel': None, 'h': 0, 'rows': [], 'saved': set(), 'end': None, 'last_f': None, 'fly0': None, 'shots': []}


def v3(a): return [f32(a + 4 * i) for i in range(3)]
def rpos(k): return v3(e.r32(GALL + 20) + 0x38 + k * 0x54)
def corr(k, i): v = e.r16(e.r32(GALL + IMG_CORRIDOR) + k * 8 + 2 * i); return v - 0x10000 if v & 0x8000 else v
def dt_(): w = (e.r32(FRAME_DT) << 32) | e.r32(FRAME_DT + 4); return struct.unpack('>d', struct.pack('>Q', w))[0]


def spline(f, sw):
    f = min(f, sw - 3); k = int(f); fr = f - k
    c0, a, b, c3 = rpos(max(k - 1, 0)), rpos(k), rpos(k + 1), rpos(k + 2); t2, t3 = fr * fr, fr * fr * fr
    return k, [0.5 * (2 * a[i] + (b[i] - c0[i]) * fr + (2 * c0[i] - 5 * a[i] + 4 * b[i] - c3[i]) * t2
                      + (3 * a[i] - c0[i] - 3 * b[i] + c3[i]) * t3) for i in range(3)]


def screen(p):
    c = e.r32(CAM)
    if not c: return None
    R, F, U, E = v3(c + 0x14), v3(c + 0x24), v3(c + 0x34), v3(c + 0x44)
    v = [p[i] - E[i] for i in range(3)]; z = sum(F[i] * v[i] for i in range(3))
    if z < 1: return None
    th = math.tan(math.radians(f32(PERSP)) / 2); asp = f32(PERSP + 4) or 4 / 3
    return (160 + 160 * sum(R[i] * v[i] for i in range(3)) / z / (th * asp), 120 - 120 * sum(U[i] * v[i] for i in range(3)) / z / th)


def pilot(node, k):
    if not e.r32(SYM['g_fly_on']): return 0, 0, 0
    pos = v3(SYM['g_fly_pos']); tp = rpos(node + A.look); yaw = f32(SYM['g_fly_yaw'])
    run = not A.make
    if run and A.follow and f32(SYM['g_or_f']) > 0:
        o = v3(e.r32(SYM['g_or_node']) + 0x38); tp = [o[0], o[1], tp[2]]
    err = (math.atan2(tp[1] - pos[1], tp[0] - pos[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
    dz = A.dz if run else 0
    a = BTN['A'] if (not run or A.a == 'hold' or (A.a == 'pulse' and k % 120 < 60)) else 0
    return a, max(-80, min(80, int(-err * 160))), max(-80, min(80, int(-(tp[2] - 10 + dz - pos[2]) * 2)))


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(start)
    if n < 64: return
    k = n - 64
    lvl, hold = e.r16(LEVEL), e.r16(HOLD)
    if A.make and k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | 11)
    if A.make and k < 130:
        set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0); return
    S['h'] = S['h'] + 1 if hold else 0
    pad = (BTN['A'] if S['h'] >= 30 and S['h'] % 60 < 5 else 0, 0, 0)
    if any(0 <= s_ - k <= 3 for s_ in SHOTK): e.unlimit(False)
    if k in SHOTK: e.shot(); S['shots'].append(k)
    if any(1 <= k - s_ <= 2 for s_ in SHOTK) and not any(0 <= s_ - k <= 3 for s_ in SHOTK): e.unlimit()
    if lvl == MLV and e.r32(SYM['g_gallrun']) and not hold:
        chor = e.r32(CHOR_REC + 0x10); node = e.r32(chor + 0x6C) if chor else 0; sw = e.r32(GALL + IMG_SWITCH)
        if node < sw: pad = pilot(node, k)
        orf, pt = f32(SYM['g_or_f']), f32(SYM['g_or_pt'])
        if A.make:
            if e.r32(SYM['g_fly_on']) and S['fly0'] is None: S['fly0'] = node; print(k, 'fly on at node', node, 'sw', sw, flush=True)
            for x, at in (('s', (1e9 if S['fly0'] is None else S['fly0']) + MAKE_S), ('m', sw // 2)):
                if x not in S['saved'] and node >= at and pt == 0:
                    e.save_state(ST[x]); S['saved'].add(x); print(k, 'saved', ST[x], 'node', node, 'or_f', round(orf, 1), flush=True)
            if len(S['saved']) == 2:
                S.setdefault('kend', k + 30)
                if k >= S['kend']: S['end'] = 'made'; e.stop(); return
        elif orf != S['last_f'] and orf > 0:
            S['last_f'] = orf
            t = f32(chor + 0x64); fp = node + 1 + t
            nd = e.r32(SYM['g_or_node']); P = v3(nd + 0x38); shown = e.r16(nd + 2) >> 8 == 0xFF
            Pc = [P[0], P[1], P[2] + SHIP_DROP]
            kk, sp = spline(orf, sw); dz = f32(SYM['g_or_dz']); sp[2] += dz
            push = [Pc[i] - sp[i] for i in range(3)]
            hi = corr(kk, 3) - OR_R
            fpos = v3(SYM['g_fly_pos']); fat = v3(SYM['g_ship_at'])
            r = dict(k=k, node=node, fp=fp, f=orf, gap=orf - fp, rate=f32(SYM['g_or_rate']), dz=dz, hi=hi, kk=kk,
                     soz=f32(SYM['g_ship_off'] + 8), push=push, P=P, shown=shown, pt=pt, dt=dt_(),
                     dist=math.dist(fpos, Pc), scr=screen(P), fscr=screen(fat), spd=f32(SYM['g_fly_speed']))
            if A.cam:
                c_ = e.r32(CAM); r.update(eye=v3(c_ + 0x44) if c_ else None, fz=fpos[2], flyon=e.r32(SYM['g_fly_on']))
            S['rows'].append(r)
            lq, sl = f32(SYM['g_lag_quiet']), e.r32(SYM['g_said_slit']) if 'g_said_slit' in SYM else 0
            if lq > S['lq'] + 1: S['lines'].append(('keep up', k, node))
            if sl and not S['slit']: S['lines'].append(('tight squeeze', k, node))
            if pt > 0 and S['peel'] is None: S['peel'] = (k, node, round(orf, 1))
            S['lq'], S['slit'] = lq, sl
            if pt > 0 and r['pt'] > 0.3: S['end'] = 'break-off'; e.stop(); return
    e.pad(*pad)
    if k > A.frames: S['end'] = 'frames'; e.stop()


e.run(script)
print(f'or_pace, build {BUILD}, {TAG}: {S["end"]}')
print('  lines (name, k, node):', S['lines'], '; break-off (k, node, g_or_f):', S['peel'])
R = [r for r in S['rows'] if r['pt'] == 0]
if not R: sys.exit()
for a, b in zip(R, R[1:]):
    b['step'] = math.dist(a['P'], b['P']); b['dk'] = b['k'] - a['k']
    b['df'] = b['f'] - a['f']; b['ddz'] = b['dz'] - a['dz']
    b['dpush'] = [b['push'][i] - a['push'][i] for i in range(3)]
    b['ds'] = None if not (a['scr'] and b['scr']) else (b['scr'][0] - a['scr'][0], b['scr'][1] - a['scr'][1])
    b['dfs'] = None if not (a['fscr'] and b['fscr']) else (b['fscr'][0] - a['fscr'][0], b['fscr'][1] - a['fscr'][1])
R2 = R[1:]
med = statistics.median(r['step'] for r in R2)
for a, b in zip(R2, R2[1:]):
    b['jump'] = None if not (a['ds'] and b['ds']) else math.hypot(b['ds'][0] - a['ds'][0], b['ds'][1] - a['ds'][1])
    b['fjump'] = None if not (a['dfs'] and b['dfs']) else math.hypot(b['dfs'][0] - a['dfs'][0], b['dfs'][1] - a['dfs'][1])


def terms(r):
    t = []
    pl = math.hypot(*r['dpush'])
    if pl > 2: t.append(f'push {pl:.0f} ({",".join("%.0f" % x for x in r["dpush"])})')
    if abs(r['ddz']) > 2: t.append(f'dz {r["ddz"]:+.1f}' + (' (at hi)' if abs(r['dz'] - r['hi']) < 0.05 else ' (at lo)' if r['dz'] <= -FLY_LOW + 0.05 else ''))
    if r['df'] * NODE_UNITS > 3 * med or r['dk'] > 2: t.append(f'route {r["df"]:.3f} nodes in {r["dk"]} VI (dt {r["dt"]:.3f})')
    return ', '.join(t) or 'spline'


jerks = [r for r in R2 if r['step'] > 3 * med or (r.get('jump') or 0) > 6]
print(f'  game frames {len(R)}, median step {med:.2f} u, dt median {statistics.median(r["dt"] for r in R):.4f}')
for r in jerks:
    if not A.quiet or len(jerks) < 40:
        print(f'  JERK k {r["k"]} node {r["node"]} kk {r["kk"]} step {r["step"]:.1f} jump {r.get("jump") or 0:.1f} px '
              f'(falcon {r.get("fjump") or 0:.1f}) gap {r["gap"]:.2f} dz {r["dz"]:.1f} hi {r["hi"]:.0f} soz {r["soz"]:.0f}: {terms(r)}')
at_hi = sum(1 for r in R if abs(r['dz'] - r['hi']) < 0.05)
pushed = [r for r in R if math.hypot(*r['push']) > 1]
print(f'  jerks {len(jerks)} (step>{3 * med:.1f}: {sum(1 for r in R2 if r["step"] > 3 * med)}, jump>6px: '
      f'{sum(1 for r in R2 if (r.get("jump") or 0) > 6)}); dz clamped at hi {at_hi} frames; pushed {len(pushed)} frames, '
      f'most {max((math.hypot(*r["push"]) for r in R), default=0):.1f} u')
g = min(R, key=lambda r: r['gap']); d = min(R, key=lambda r: r['dist'])
print(f'  least gap {g["gap"]:.2f} nodes at k {g["k"]} node {g["node"]} (dist {g["dist"]:.0f} u, rate {g["rate"]:.2f}); '
      f'least dist {d["dist"]:.0f} u at k {d["k"]} node {d["node"]} (gap {d["gap"]:.2f}); frames gap<2: '
      f'{sum(1 for r in R if r["gap"] < 2)}, <1: {sum(1 for r in R if r["gap"] < 1)}, dist<60: {sum(1 for r in R if r["dist"] < 60)}; '
      f'rate max {max(r["rate"] for r in R):.2f}; nodes {R[0]["node"]}..{R[-1]["node"]}')
under = [r for r in R if r['gap'] < 2]
if under:
    runs, cur = [], [under[0]]
    for r in under[1:]:
        if r['k'] - cur[-1]['k'] <= 4: cur.append(r)
        else: runs.append(cur); cur = [r]
    runs.append(cur)
    for c in runs: print(f'  GAP<2 k {c[0]["k"]}..{c[-1]["k"]} nodes {c[0]["node"]}..{c[-1]["node"]} least {min(x["gap"] for x in c):.2f} '
                         f'dist {min(x["dist"] for x in c):.0f} u')

# The jerks as the eye sees them (the screen jump above is noisy: the Falcon's own is 7 px at p90): the change of the
# Outrider's velocity in a game frame (u/s), split into its terms: the spline (route), g_or_dz (the clamp), the push.
def vel(a, b, key):
    if key == 'dz': return [0, 0, (b['dz'] - a['dz']) / b['dt']]
    if key == 'sp': return [((b['P'][i] - b['push'][i] - (a['P'][i] - a['push'][i])) - (i == 2) * (b['dz'] - a['dz'])) / b['dt'] for i in range(3)]
    return [(b[key][i] - a[key][i]) / b['dt'] for i in range(3)]
DV = []
for a, b, c in zip(R, R[1:], R[2:]):
    d = {key: math.dist(vel(a, b, key), vel(b, c, key)) for key in ('P', 'sp', 'dz', 'push')}; d['r'] = c; DV.append(d)
if DV:
    dvs = sorted(x['P'] for x in DV); dmed = dvs[len(dvs) // 2]; TH = float(os.environ.get('DV_TH', 250))
    J = [x for x in DV if x['P'] > TH]; cause = {}
    for x in J:
        m = max(('sp', 'dz', 'push'), key=lambda q: x[q]); cause[m] = cause.get(m, 0) + 1
    print(f'  dv (u/s a frame): median {dmed:.0f} p99 {dvs[int(.99 * len(dvs))]:.0f} max {dvs[-1]:.0f}; jerks dv>{TH:g}: {len(J)} by term {cause}')
    for x in J:
        r = x['r']
        print(f'  DV k {r["k"]} node {r["node"]} kk {r["kk"]} dv {x["P"]:.0f} (spline {x["sp"]:.0f} dz {x["dz"]:.0f} push {x["push"]:.0f}) '
              f'dz {r["dz"]:.1f} hi {r["hi"]:.0f} corr up {r["hi"] + OR_R:.0f} gap {r["gap"]:.2f}')
if A.cam:
    C_ = [r for r in R if r['eye']]
    up = [r['eye'][2] - r['fz'] for r in C_]
    EJ = []
    for a, b, c in zip(C_, C_[1:], C_[2:]):
        v1 = [(b['eye'][i] - a['eye'][i]) / b['dt'] for i in range(3)]; v2 = [(c['eye'][i] - b['eye'][i]) / c['dt'] for i in range(3)]
        EJ.append((math.dist(v1, v2), c))
    ETH = float(os.environ.get('EYE_TH', 250)); ej = [x for x in EJ if x[0] > ETH]
    print(f'  CAM frames {len(C_)}, not flown {sum(1 for r in C_ if not r["flyon"])}; eye over the Falcon median '
          f'{statistics.median(up):.1f} min {min(up):.1f} max {max(up):.1f}; eye dv median {statistics.median(x[0] for x in EJ):.0f} '
          f'max {max(x[0] for x in EJ):.0f}; eye jumps dv>{ETH:g}: {len(ej)}')
    for d_, r in ej: print(f'  EYEJUMP k {r["k"]} node {r["node"]} dv {d_:.0f} flyon {r["flyon"]} eye-z {r["eye"][2] - r["fz"]:.1f}')
if A.csv:
    import csv
    with open(A.csv, 'w', newline='') as fh:
        w = csv.writer(fh); cols = ['k', 'node', 'kk', 'fp', 'f', 'gap', 'rate', 'dz', 'hi', 'soz', 'dt', 'dist', 'spd', 'step', 'jump', 'fjump']
        w.writerow(cols + ['push', 'P', 'scr'] + (['eye', 'fz', 'flyon'] if A.cam else []))
        for r in R: w.writerow([r.get(c) for c in cols] + [r['push'], r['P'], r['scr']] + ([r['eye'], r['fz'], r['flyon']] if A.cam else []))
    print('  csv', A.csv)
if S['shots']:
    from PIL import Image, ImageDraw
    d = os.path.join(RUN, 'shots', os.environ['SHOTS'])
    files = sorted(f for f in os.listdir(d) if f.endswith('.png'))[-len(S['shots']):]
    W, H, Cn = 320, 240, 4
    sheet = Image.new('RGB', (W * Cn, (H + 14) * ((len(files) + Cn - 1) // Cn)), 'white')
    byk = {r['k']: r for r in S['rows']}
    for i, (f, kk_) in enumerate(zip(files, S['shots'])):
        x, y = W * (i % Cn), (H + 14) * (i // Cn); r = byk.get(kk_) or byk.get(kk_ - 1) or {}
        sheet.paste(Image.open(os.path.join(d, f)).convert('RGB').resize((W, H)), (x, y + 14))
        ImageDraw.Draw(sheet).text((x + 3, y + 1), f'k {kk_} gap {r.get("gap", 0):.2f} dz {r.get("dz", 0):.0f}', fill='black')
    out = os.path.join(RUN, f'{BUILD}_orp_{TAG}.png'); sheet.save(out); print('  sheet', out)
