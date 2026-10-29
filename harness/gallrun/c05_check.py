"""Cut 05 check (the chain's Cut 05, gall_chain.c): plays it the way take B does (no presses but A every second once a
line's arrow is up), prints a short summary per frame, saves a state at each frame's first frame, and makes a contact
sheet if asked. Starting from a saved frame state skips the ~2 minutes before it.

    M64CPU=2 .venv/bin/python3 gallrun/c05_check.py <build>/sote-patch.z64 [--from F] [--to F] [--sheet SEC] [--frames A,B]

  --from F    start at frame F's first frame from run/<build>_c05_f<F>.st (made by a run from frame 1 of the same build);
              default 1: from run/<build>_echo.st (made with mkstate.py if missing) by debug This Level 11
  --to F      stop at frame F's first frame (default: the mission reached, 60 frames into it)
  --trace A,B per VI between scene clocks A and B: frame, clock, the hold, ARROW_T, shot k (a shot each)
  --sheet SEC a shot every SEC seconds in the frames of --frames (default 3,5: the 3D scenes) and a contact sheet
              run/<build>_c05_sheet.png (labels: frame, seconds into it, scene clock)

  --look      a LOOK line (gallrun/falcon_look.py: falcon.bin lit / unlit, its materials and vertex
              bytes) at each change of the sub-level or the look (read on a sub-level change and every 120 VIs)
  --falcon-bin  (no-op: the scenes draw falcon.bin's parts, IMG_FALCON is 0) the Falcon in Cut 05 from falcon.bin's parts (0x80500000: header +4 count, +8 list, +0xC box) in place
              of the image's (IMG_FALCON, GALL +328, written every frame); the
              sheet is then run/<build>_c05_fbin_sheet.png

  --sounds    every sound request (gallrun/sndlog.py: the game's sound calls, caller, id, args; needs M64CPU=0) and a
              summary per (call, caller, id)
  --seqoff    g_c05_seq 0 from the load: Cut 05 the game's own (its own flight, for the stock scene's sounds)
  --ships     in frames 3 and 5 per ship (X-Wings 0..2, the Falcon 3, the Outrider 4) its distance to the eye each frame:
              summary per ship and frame: the least distance, its k / scene clock / screen x, the depth (along the view)
              before and after (from behind: negative before), and when its depth turns positive

  --steps A,B per VI between scene clocks A and B: STEP k, the overlay frame counter (g_ov_frames), the VI origin (the frame on screen), the clock,
              FRAME_DT, the Outrider's place, the eye, X-Wing 0's and the Falcon's node places (their steps a shown
              frame tell the scene's own motion from ours)

  --dump P    the RDRAM (Emu.dump: little-endian words) written to P as the run stops 60 frames into the mission
              (a RAM read of the mission's sub-level entered the chain's way)

Printed: per frame its start (VI k), length in seconds, scene clock in and out (frame 5: scene 2's s too), the holds the
game raised in it; Leebo's head phases in frame 6 (game frames from the frame's start); the sub-levels after Cut 05 and
whether the mission's image is in (GALL tag). Seconds are VIs / 60 (real time on the phone).
States are per build (RAM holds the build's code): a new build needs a run from frame 1 first."""
import os, sys, subprocess, argparse, struct, ctypes as C
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
ap = argparse.ArgumentParser()
ap.add_argument('rom'); ap.add_argument('--from', dest='frm', type=int, default=1); ap.add_argument('--to', type=int, default=0)
ap.add_argument('--sheet', type=float, default=0); ap.add_argument('--trace', default=''); ap.add_argument('--steps', default=''); ap.add_argument('--frames', default='3,5')
ap.add_argument('--sounds', action='store_true'); ap.add_argument('--seqoff', action='store_true'); ap.add_argument('--ships', action='store_true')
ap.add_argument('--falcon-bin', dest='fbin', action='store_true'); ap.add_argument('--look', action='store_true')
ap.add_argument('--dump', default='')   # RDRAM written here when the run stops in the mission
A = ap.parse_args()
ROM = os.path.abspath(A.rom)
BUILD = os.path.basename(os.path.dirname(ROM))
os.environ.setdefault('SHOTS', f'c05chk_{BUILD}')
import paths
import m64
from m64 import Emu, BTN, HERE
from debugmenu import set_debug, set_cursor

RUN = paths.RUN
ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
MLV = 32 if 'g_levels' in SYM else 6           # the mission's sub-level (32 from bf49)
LEVEL, HOLD, GALL, TAG_GALL = 0x8013CE0E, 0x800DD2D0, 0x80628000, 0x47414C4C
SHEET_FR = {int(x) for x in A.frames.split(',') if x}


def st_path(f): return os.path.join(RUN, f'{BUILD}_c05_f{f}.st')


start = os.path.join(RUN, f'{BUILD}_echo.st') if A.frm == 1 else st_path(A.frm)
if not os.path.exists(start):
    if A.frm != 1: sys.exit(f'no {start}: run from frame 1 first (it saves the frame states)')
    print('making', start, flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, 'mkstate.py'), ROM, '1', start], check=True,
                   env=dict(os.environ, M64CPU='2'), stdout=open(start + '.log', 'w'), stderr=subprocess.STDOUT)

e = Emu(ROM, video=m64.GLN)
import math
from sndlog import SndLog
L = SndLog(e, out=lambda t: print(t, flush=True)) if A.sounds else None
SHIPN = ('X-Wing 0', 'X-Wing 1', 'X-Wing 2', 'Falcon', 'Outrider')
SH = {}                                         # (frame, ship) -> {'min': (d, k, clk, sx, z), 'cross': k, 'z0', 'z1'}


def v3(a): return [e.rf(a + 4 * j) for j in range(3)]


def ships_log(k, fr):
    cam = e.r32(0x800D08A4)
    if not cam: return
    eye, R, F, U = v3(cam + 0x44), v3(cam + 0x14), v3(cam + 0x24), v3(cam + 0x34)
    fovy = e.rf(0x80192F14); asp = e.rf(0x80192F18) or 4 / 3
    px = (1 / math.tan(math.radians(fovy) / 2) if 1 < fovy < 179 else 1.0) / asp
    near = fr == 5 and e.r32(SYM['g_near_set'])
    nd = SYM['g_near_node']; nn = v3(nd + 0x38); N = [v3(nd + 0x14 + 12 * i) for i in range(3)]
    tn = SYM['g_tnode']; clk = e.rf(SYM['g_c05_clk'])
    for i, a in enumerate([tn + 0x48 * j for j in range(4)] + [0x80198D00]):
        l = v3(a + 0x38)
        q = [nn[j] + sum(l[m] * N[m][j] for m in range(3)) for j in range(3)] if near else l
        d = [q[j] - eye[j] for j in range(3)]
        x, z = sum(d[j] * R[j] for j in range(3)), sum(d[j] * F[j] for j in range(3))
        dist = math.dist(d, (0, 0, 0)); sx = round(160 * (1 + px * x / z)) if z > 1 else None
        r = SH.setdefault((fr, i), {'min': None, 'cross': None, 'z0': z, 'k0': k})
        if r['min'] is None or dist < r['min'][0]: r['min'] = (round(dist, 1), k, round(clk, 1), sx, round(z, 1))
        if r['cross'] is None and r['z0'] < 0 and z > 0: r['cross'] = (k, round(clk, 1), round(dist, 1))
        r['z1'] = z; r['k1'] = k
S = {'fr': None, 'frames': {}, 'lv': [], 'h': 0, 'shots': [], 'last': -1e9, 'end': None}


def frame_state(k, fr, lvl, hold):
    clk = e.rf(SYM['g_c05_clk'])
    d = S['frames'].get(fr)
    if d is None:
        d = S['frames'][fr] = {'k0': k, 'clk0': clk, 'holds': [], 'leebo': []}
        if fr > A.frm and fr >= 2 and not (A.sounds or A.seqoff or A.fbin): e.save_state(st_path(fr))   # (no stub / stock scene in them)   # (a later start saves the frames after it)
    d['k1'], d['clk1'] = k, clk
    if fr == 5 and e.r32(SYM['g_near_set']): d['s'] = clk - e.rf(SYM['g_s2_clk0'])
    if hold and (not d['holds'] or d['holds'][-1][1] != hold) and S['ph'] != hold: d['holds'].append((round((k - d['k0']) / 60, 1), hold))
    if fr == 6 and 'g_leebo_t' in SYM:
        t = e.r32(SYM['g_leebo_t'])
        if t and (not d['leebo'] or d['leebo'][-1] != t - 1) and t in (1, 41, 45, 49, 53, 57, 61, 65): d['leebo'].append(t - 1)
    if A.sheet and fr in SHEET_FR and k - S['last'] >= A.sheet * 60:
        S['last'] = k; e.shot(); S['shots'].append(f'f{fr} {(k - d["k0"]) / 60:.0f}s clk {clk:.0f}' + (f' s {d["s"]:.0f}' if 's' in d else ''))


LK = {'last': None, 'lvl': None, 'k': 0}
def look_tick(e, k, lvl):                          # --look: falcon.bin's look per change (read every
    if lvl != LK['lvl']: LK['lvl'], LK['k'] = lvl, k   # VI for 20 VIs after a sub-level change, else every 120)
    if k - LK['k'] > 20 and k % 120: return
    from gallrun.falcon_look import look, line
    d = look(e.r32, e.r16); key = (lvl, d['kind'])
    if key != LK['last']: print('k', k, line(d), flush=True)
    LK['last'] = key


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(start)
    if n < 64: return
    k = n - 64
    lvl, hold = e.r16(LEVEL), e.r16(HOLD)
    if A.seqoff: e.w32(SYM['g_c05_seq'], 0)        # (from the load on, as chain_take.py SEQOFF)
    if A.frm == 1:
        if k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | 11)
        if k < 130:
            set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0); return
    if L and 'snd' not in S: S['snd'] = 1; L.install()
    if L: L.read(k)
    if not S['lv'] or S['lv'][-1][1] != lvl: S['lv'].append((k, lvl))
    if A.look: look_tick(e, k, lvl)
    S.setdefault('ph', 0)
    if lvl == 11:
        if A.fbin:
            for j in range(3): e.w32(GALL + 328 + 4 * j, e.r32(0x80500004 + 4 * j))
        fr = e.r32(SYM['g_c05_frame'])
        if fr == A.to and A.to: S['end'] = f'frame {fr} reached'; e.stop(); return
        if fr: frame_state(k, fr, lvl, hold)
        if A.ships and fr in (3, 5): ships_log(k, fr)
        if A.trace:
            a_, b_ = (float(x) for x in A.trace.split(',')); clk = e.rf(SYM['g_c05_clk'])
            if a_ <= clk <= b_: e.shot(); print('TRACE k', k, 'fr', fr, 'clk', round(clk, 1), 'hold', hold, 'arrow_t', round(e.rf(0x800DD2CC), 2), flush=True)
        if A.steps:
            a_, b_ = (float(x) for x in A.steps.split(',')); clk = e.rf(SYM['g_c05_clk'])
            if a_ <= clk <= b_:
                cam, tn = e.r32(0x800D08A4), SYM['g_tnode']
                f = lambda v: ' '.join(f'{x:.2f}' for x in v)
                dt = struct.unpack('>d', struct.pack('>II', e.r32(0x8018E998), e.r32(0x8018E99C)))[0]
                print('STEP', k, e.r32(SYM['g_ov_frames']), hex(C.c_uint32.from_address(m64.core.DebugMemGetPointer(4) + 4).value), f'{clk:.2f}', f'{dt:.5f}', '|', f(v3(0x80198D38)), '|',
                      f(v3(cam + 0x44)) if cam else '-', '|', f(v3(tn + 0x38)), '|', f(v3(tn + 0x48 * 3 + 0x38)), flush=True)
        S['ph'] = hold
    S['h'] = S['h'] + 1 if hold == 10 or (A.seqoff and hold) else 0   # (the stock scene: any hold)
    e.pad(BTN['A'] if S['h'] >= 30 and S['h'] % 60 < 5 else 0)
    if lvl == MLV:
        S.setdefault('k6', k)
        if k >= S['k6'] + 60:
            S['end'] = 'mission' if e.r32(GALL) == TAG_GALL else 'STOCK level 6 (no GALL tag)'
            if A.dump: e.dump(A.dump); print('dumped', A.dump, flush=True)
            e.stop(); return
    if k > 60 * 60 * 6: S['end'] = 'timeout (6 min)'; e.stop()


e.run(script)
print(f'Cut 05 check, build {BUILD}, from frame {A.frm}')
for fr in sorted(S['frames']):
    d = S['frames'][fr]
    s = f'  s {d["s"]:.0f}' if 's' in d else ''
    print(f'  frame {fr}: k {d["k0"]:5d}  {(d["k1"] - d["k0"]) / 60:5.1f} s  clk {d["clk0"]:5.0f} -> {d["clk1"]:5.0f}{s}'
          f'  holds {d["holds"]}' + (f'  leebo {d["leebo"]}' if d['leebo'] else ''))
for (fr, i), r in sorted(SH.items()):
    m = r['min']
    print(f'  ship frame {fr} {SHIPN[i]:9s}: least {m[0]} at k {m[1]} clk {m[2]} screen x {m[3]} depth {m[4]};'
          f' depth k {r["k0"]}: {r["z0"]:.0f} -> k {r["k1"]}: {r["z1"]:.0f}; in front from {r["cross"]}')
if L: L.summary()
print('  levels', ' -> '.join(f'{l} (k {k})' for k, l in S['lv']))
print('  end:', S['end'])
if S['shots']:
    from PIL import Image, ImageDraw
    d = os.path.join(RUN, 'shots', os.environ['SHOTS'])
    files = sorted(f for f in os.listdir(d) if f.endswith('.png'))[-len(S['shots']):]
    W, H, C = 320, 240, 4
    sheet = Image.new('RGB', (W * C, (H + 14) * ((len(files) + C - 1) // C)), 'white')
    for i, (f, lab) in enumerate(zip(files, S['shots'])):
        x, y = W * (i % C), (H + 14) * (i // C)
        sheet.paste(Image.open(os.path.join(d, f)).convert('RGB').resize((W, H)), (x, y + 14))
        ImageDraw.Draw(sheet).text((x + 3, y + 1), lab, fill='black')
    out = os.path.join(RUN, f'{BUILD}_c05{"_fbin" if A.fbin else ""}_sheet.png'); sheet.save(out); print('  sheet', out)
