"""The last scene (sub-level 31) check: the stock scene and ours (gall_chain.c final_scene(), g_chain_fin 1, entered at
its hyperspace tunnel). Lines held are let go by A after HOLD_A frames (as final_state.py). Prints per change: the music
track (s16 0x800D075E), its level volume (0x800D0760), the 0..1 factor (0x800D0764), the gate 0x800D06F0, the line hold,
the sub-level; with --sounds every sound request, logged by gallrun/sndlog.py (the game's sound calls and the queue 0x80007128
under them: the caller's return address, id, channel, pitch, volume, pan, loop; see there).

    M64CPU=2 .venv/bin/python3 gallrun/fin_check.py <build>/sote-patch.z64 --make        # the two start states
    M64CPU=0 .venv/bin/python3 gallrun/fin_check.py <build>/sote-patch.z64 --from stock|ours [--sounds] [--to K]
        [--shots K1,K2,..] [--quiet-ids ID,..]

  --make     from run/<build>_echo.st (a state of the build) debug This Level 31 -> run/<build>_fin_stock.st (the scene's
             first frame, g_chain_fin 0) and run/<build>_fin_ours.st (the next frame, g_chain_fin 1: the chain's way in,
             as chain_finale() sets it)
  --from     start from one of them (k 0 = the scene's first frame)
  --sounds   the call log (needs M64CPU=0: the stub is code written into RAM)
  --to K     stop K frames (VIs) after the start (default: the sub-level after 31 reached + 60, or 8000)
  --shots    a shot at these k (SHOTS dir: fin_<build>_<from>)
  --audio K0,K1  the sound from k K0 to K1 -> run/fin_<build>_<from>.wav, and its level (RMS, dBFS) per half second
  --sound ID,..  at the start: these sounds' wave tables in the level's bank (*0x800EEB04 +0xC: the instrument, as
             0x8000686c reads it): ROM base, length in bytes, type, loop; with the playing time at 22 kHz (VADPCM 9 B/16)
  --dma      (with --sounds and --sound) the sample DMA callback 0x800063E4 logged too: per 30 VIs the furthest offset
             read in each --sound's wave (bytes from its base, and seconds at 11 kHz: pitch 0.5 of the 22 kHz output):
             where in the sample the sound is playing
  --reload K at k K debug This Level 31 again (does a playing sound live through a load of the scene: --dma shows
             whether its offset goes on or starts over)
  --falcon   per frame the tunnel's node 0x80199AC0 (our Falcon under it) drawn (+2 high byte 0xFF) and its place
             inside the screen through the active camera (as gall_chain.c D8 tests it): its on-screen spans at the end;
             per frame a FALD line: the eye (active camera +0x44) to the Falcon's middle (the
             image copy's y -14.7..22.5 through FIN_OR's rows x FIN_K = 6.5 / 37.2) and to its long axis, the Falcon's
             half length in the world (18.6 x FIN_K x |FIN_OR row|), their ratio, on screen; FALDSUM: the least ratio, the
             frames (and k spans) with the eye inside the half length (FIN_K=x overrides the scale, as a smaller
             FIN_FALCON_LEN would draw it: the Outrider's path is the same; without it the scale and the offset are read from
             our node g_fin_node under FIN_OR: its row length and +0x38, taken through FIN_OR's rows); --check: PASS / FAIL
             on the eye kept out of the hull (least ratio >= 1, no frame inside) and the Falcon on screen over k 20..760
  (with --sound: each one's wave words (base, length, loop start / end) printed at the start and on each sub-level change;
   with --audio: the largest step between two samples in the first half second, as a share of full scale: a click)
  --look     a LOOK line (gallrun/falcon_look.py: falcon.bin lit / unlit) at each change of the
             sub-level or the look
  --load     start from run/<build>_echo.st and load 31 by debug This Level with g_chain_fin 1 (and g_fin_t / holds /
             tail 0) from the press on: the chain's way in through a load (k 0 = the press; the scene's own first frames,
             when its music starts, are in the run)
  --hold-a N  a held line let go by A after N VIs of hold (default 50)
  --again N[:L]  A pressed once more N VIs after each held line is let go (only after line L, 1..4, if given): a double
              tap
  --mash N    A pressed 4 VIs out of every N, held line or not (a player mashing A), in place of --hold-a
  --wave-base HEX  (with --dma) offsets from this ROM base instead of the table's at the start (it may be changed then)
  --quiet-ids  ids whose repeated per-frame calls are summarised (first/last k, count) instead of printed each time
Ends with a summary: each (caller, id, channel) with its first/last k and count; the track's spans."""
import os, sys, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
ap = argparse.ArgumentParser()
ap.add_argument('rom'); ap.add_argument('--make', action='store_true'); ap.add_argument('--from', dest='frm', default='')
ap.add_argument('--sounds', action='store_true'); ap.add_argument('--to', type=int, default=8000)
ap.add_argument('--shots', default=''); ap.add_argument('--audio', default=''); ap.add_argument('--sound', default=''); ap.add_argument('--dma', action='store_true'); ap.add_argument('--reload', type=int, default=-1); ap.add_argument('--quiet-ids', default=''); ap.add_argument('--falcon', action='store_true'); ap.add_argument('--look', action='store_true'); ap.add_argument('--load', action='store_true'); ap.add_argument('--wave-base', default='')
ap.add_argument('--check', action='store_true'); ap.add_argument('--hold-a', type=int, default=50); ap.add_argument('--mash', type=int, default=0); ap.add_argument('--again', default='')
A = ap.parse_args()
ROM = os.path.abspath(A.rom)
BUILD = os.path.basename(os.path.dirname(ROM))
os.environ.setdefault('SHOTS', f'fin_{BUILD}_{A.frm or "make"}')
import paths
import m64
from m64 import Emu, BTN, HERE
from debugmenu import set_debug, set_cursor

RUN = paths.RUN
ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
LEVEL, HOLD, FINAL, HOLD_A = 0x8013CE0E, 0x800DD2D0, 31, A.hold_a
TRACK, MVOL, MFAC, MGATE, GFRAME = 0x800D075C, 0x800D0760, 0x800D0764, 0x800D06F0, 0x8018E9B0
SHOTS = {int(x) for x in A.shots.split(',') if x}
QUIET = {int(x, 0) for x in A.quiet_ids.split(',') if x}


import math
FIN_OR, CAM = 0x80199AC0, 0x800D08A4


def falcon_on():
    cam = e.r32(CAM)
    if not cam or (e.r16(FIN_OR + 2) & 0xFF00) != 0xFF00: return 0
    v3 = lambda a: [e.rf(a + 4 * j) for j in range(3)]
    eye, R, F, U, p = v3(cam + 0x44), v3(cam + 0x14), v3(cam + 0x24), v3(cam + 0x34), v3(FIN_OR + 0x38)
    d = [p[j] - eye[j] for j in range(3)]
    x, y, z = (sum(d[j] * R[j] for j in range(3)), sum(d[j] * U[j] for j in range(3)), sum(d[j] * F[j] for j in range(3)))
    if z < 1: return 0
    fovy = e.rf(0x80192F14); asp = e.rf(0x80192F18) or 4 / 3
    py = 1 / math.tan(math.radians(fovy) / 2) if 10 < fovy < 170 else 1.0; px = py / asp
    return int(0 <= 160 * (1 + px * x / z) < 320 and 0 <= 120 * (1 - py * y / z) < 240)


FIN_K = float(os.environ.get('FIN_K', 6.5 / 37.2)); Y0, Y1 = -14.7, 22.5


def falcon_dist(k):
    cam = e.r32(CAM)
    if not cam or (e.r16(FIN_OR + 2) & 0xFF00) != 0xFF00: return None
    v3 = lambda a: [e.rf(a + 4 * j) for j in range(3)]
    eye, pos = v3(cam + 0x44), v3(FIN_OR + 0x38)
    R = [v3(FIN_OR + 0x14 + 12 * i) for i in range(3)]
    sc = math.sqrt(sum(x * x for x in R[1]))
    fk, off = FIN_K, [0, 0, 0]
    nd = SYM.get('g_fin_node')                                     # (our scale node under it: its scale and offset)
    if nd and 'FIN_K' not in os.environ and e.r32(e.r32(FIN_OR + 0x10)) == nd:
        fk = math.sqrt(sum(e.rf(nd + 0x14 + 4 * j) ** 2 for j in range(3))); off = v3(nd + 0x38)
    pos = [pos[j] + sum(off[i] * R[i][j] for i in range(3)) for j in range(3)]
    if k in (14, 700): print(f'k {k} FALROWS {[[round(x, 3) for x in r] for r in R]} child k {fk:.4f} off {[round(x, 3) for x in off]}', flush=True)
    at = lambda y: [pos[j] + fk * y * R[1][j] for j in range(3)]
    a, b = at(Y0), at(Y1); mid = at((Y0 + Y1) / 2)
    ab = [b[j] - a[j] for j in range(3)]; t = sum((eye[j] - a[j]) * ab[j] for j in range(3)) / max(1e-9, sum(x * x for x in ab))
    q = [a[j] + max(0, min(1, t)) * ab[j] for j in range(3)]
    half = (Y1 - Y0) / 2 * fk * sc
    return math.dist(eye, mid), math.dist(eye, q), half, eye, pos, sc


def wave_words(tag, k):
    for sid, (b0, ln) in list(L.waves.items()):
        wt = S['wt'][sid]; lp = e.r32(wt + 0xC)
        print(f'  WAVE {tag} k {k} sound {sid} at {wt:#x}: base {e.r32(wt):#x} len {e.r32(wt + 4)} loop {e.r32(lp) if lp else -1}..{e.r32(lp + 4) if lp else -1}', flush=True)


def st_path(w): return os.path.join(RUN, f'{BUILD}_fin_{w}.st')


e = Emu(ROM, video=m64.GLN)
from sndlog import SndLog, f2
L = SndLog(e, dma=A.dma, quiet=QUIET, out=lambda t: print(t, flush=True))
import ctypes as C
AK = [int(x) for x in A.audio.split(',')] if A.audio else None
WAV = os.path.join(RUN, f'fin_{BUILD}_{"load" if A.load else A.frm}.wav')
AUD = C.CDLL(os.path.join(paths.BIN, 'audio_dump.dylib')) if AK else None
if AUD: AUD.audio_dump_frames.restype = C.c_long
AMARK = []
S = {'k0': None, 'h': 0, 'last': {}, 'track': [], 'lv': [], 'made': set(), 'end': ''}


LK = {'last': None, 'lvl': None, 'k': 0}
def look_tick(e, k, lvl):                          # --look: falcon.bin's look per change (read every
    if lvl != LK['lvl']: LK['lvl'], LK['k'] = lvl, k   # VI for 20 VIs after a sub-level change, else every 120)
    if k - LK['k'] > 20 and k % 120: return
    from gallrun.falcon_look import look, line
    d = look(e.r32, e.r16); key = (lvl, d['kind'])
    if key != LK['last']: print('k', k, line(d), flush=True)
    LK['last'] = key


def script(e, n):
    if n == 1: e.unlimit(not AK)   # (the sound needs real time: an unthrottled run dumps a quarter of it)
    if n == 60: e.load_state(st_path(A.frm) if A.frm and not A.load else os.path.join(RUN, f'{BUILD}_echo.st'))
    if n < 64: return
    if A.load and n - 64 < 130:
        k_ = n - 64
        if k_ == 0:                                  # (the sub-level word 31 from here: chain_frame() keeps g_chain_fin)
            e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | FINAL)
            for s_ in ('g_chain_fin', 'g_fin_t', 'g_fin_holds', 'g_fin_tail'): e.w32(SYM[s_], 1 if s_ == 'g_chain_fin' else 0)
        set_debug(e, k_ < 10); set_cursor(e, 8 if k_ < 10 else 0); e.pad(BTN['START'] if k_ < 2 else 0)
        if k_ == 0: return
    lvl, hold = e.r16(LEVEL), e.r16(HOLD)
    if A.look: look_tick(e, n - 64, lvl)
    if A.make:
        k = n - 64
        if k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | FINAL)
        if k < 130:
            set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0); return
        if lvl == FINAL and 'stock' not in S['made']:
            e.save_state(st_path('stock')); S['made'].add('stock'); S['wait'] = n; print('saved', st_path('stock'), 'k', k, flush=True); return
        if 'stock' in S['made'] and 'ours' not in S['made'] and n == S['wait'] + 1:   # (one frame later: same place)
            for s in ('g_chain_fin', 'g_fin_t', 'g_fin_holds', 'g_fin_tail'): e.w32(SYM[s], 1 if s == 'g_chain_fin' else 0)
            e.save_state(st_path('ours')); S['made'].add('ours'); print('saved', st_path('ours'), flush=True); return
        if 'ours' in S['made'] and n > S['wait'] + 20: e.stop()
        if k > 3000: S['end'] = 'no level 31'; e.stop()
        return
    if S['k0'] is None:
        S['k0'] = n
        if A.sounds: L.install()
        for sid in (int(x, 0) for x in A.sound.split(',') if x):
            ins = e.r32(e.r32(0x800EEB04) + 0xC); cnt = e.r16(ins + 0xE)
            if sid >= cnt: print('sound', sid, 'not in the bank (count', cnt, ')'); continue
            snd = e.r32(ins + 0x10 + 4 * sid); wt = e.r32(snd + 8)
            ln = e.r32(wt + 4); typ = e.r32(wt + 8) >> 24; loop = e.r32(e.r32(wt + 0xC)) if typ == 0 and e.r32(wt + 0xC) else 0
            L.waves[sid] = (int(A.wave_base, 16) if A.wave_base else e.r32(wt), ln); S.setdefault('wt', {})[sid] = wt
            lp = e.r32(wt + 0xC)
            if lp: print(f'  loop rec: start {e.r32(lp)} end {e.r32(lp + 4)} count {e.r32(lp + 8):#x} (samples; the wave has {ln // 9 * 16})')
            print(f'sound {sid}: sound {snd:#x} wave {wt:#x} base {e.r32(wt):#x} len {ln} type {typ} '
                  f'(~{ln / 9 * 16 / 22050:.1f} s at 22 kHz ADPCM) loop rec {e.r32(wt + 0xC):#x} count {cnt}', flush=True)
        print('start', A.frm, 'level', lvl, 'g_chain_fin', e.r32(SYM['g_chain_fin']), flush=True)
    k = n - S['k0']
    if A.sounds: L.read(k)
    v = (e.r16(TRACK + 2), e.r32(MVOL), round(e.rf(MFAC), 2), e.r32(MGATE), hold, lvl,
         e.r32(SYM['g_fin_holds']) if 'g_fin_holds' in SYM else -1)
    if v != S['last'].get('v'):
        print(f'k {k} track {v[0]} vol {v[1]} fac {v[2]} gate {v[3]} hold {v[4]} lvl {v[5]} fin_holds {v[6]} '
              f'frame {e.r32(GFRAME)}', flush=True)
        if not S['track'] or S['track'][-1][1] != v[0]: S['track'].append((k, v[0]))
        S['last']['v'] = v
    if not S['lv'] or S['lv'][-1][1] != lvl:
        S['lv'].append((k, lvl))
        if S.get('wt'): wave_words('level %d' % lvl, k)
    if k in (2, 30) and S.get('wt'): wave_words('', k)
    if S.get('wt') and len(S['lv']) > 1 and k == S['lv'][-1][0] + 5: wave_words('5 after', k)
    if A.falcon:
        f_ = falcon_on(); sp = S.setdefault('fal', [])
        if f_ and (not sp or sp[-1][1] != k - 1): sp.append([k, k])
        elif f_: sp[-1][1] = k
        fd = falcon_dist(k)
        if fd:
            dm, dl, half, eye, pos, sc = fd; D = S.setdefault('fald', {'min': (9e9, None), 'in': []})
            r = dm / half
            if r < D['min'][0]: D['min'] = (r, k, round(dm, 3), round(dl, 3), round(half, 3))
            if dm < half:
                if D['in'] and D['in'][-1][1] == k - 1: D['in'][-1][1] = k
                else: D['in'].append([k, k])
            print(f'k {k} FALD mid {dm:.3f} axis {dl:.3f} half {half:.3f} ratio {r:.2f} onscr {f_} eye {[round(x, 2) for x in eye]} '
                  f'or {[round(x, 2) for x in pos]} or_scale {sc:.3f}', flush=True)
    if A.reload >= 0 and A.reload <= k < A.reload + 130:
        r = k - A.reload
        if r == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | FINAL)
        set_debug(e, r < 10); set_cursor(e, 8 if r < 10 else 0); e.pad(BTN['START'] if r < 2 else 0); return
    if k in SHOTS: e.shot()
    if AK and k == AK[0]: AUD.audio_dump_start((WAV[:-4] + '.raw').encode())
    if AK and AK[0] <= k <= AK[1] and k % 30 == 0: AMARK.append((k, AUD.audio_dump_frames()))
    if AK and k == AK[1]: AUD.audio_dump_stop()
    S['h'] = S['h'] + 1 if hold else 0
    if A.mash and not (A.load and n - 64 < 130): e.pad(BTN['A'] if k % A.mash < 4 else 0)   # (a player mashing A)
    elif not (A.load and n - 64 < 130):
        if hold: S['rel'] = 0
        elif 'rel' in S: S['rel'] += 1
        ag = [int(x) for x in A.again.split(':')] if A.again else []    # N or N:LINE: A again N VIs after a let-go (of line LINE only)
        fh = e.r32(SYM['g_fin_holds']) if 'g_fin_holds' in SYM else 0
        again = ag and 'rel' in S and ag[0] <= S['rel'] < ag[0] + 4 and (len(ag) < 2 or fh == ag[1])
        e.pad(BTN['A'] if (hold and S['h'] >= HOLD_A and S['h'] % 60 < HOLD_A % 60 + 5) or again else 0)
    if lvl == FINAL: S['in31'] = 1
    if lvl != FINAL and k > 10 and S.get('in31'): S.setdefault('left', k)
    if 'left' in S and k > S['left'] + 60: S['end'] = f'left 31 at k {S["left"]}'; e.stop()
    if k >= A.to: S['end'] = f'k {A.to}'; e.stop()


e.run(script)
if A.make: sys.exit(0 if S['made'] == {'stock', 'ours'} else 1)
print(f'fin check, build {BUILD}, from {A.frm}, end: {S["end"]}')
print('  levels', ' -> '.join(f'{l} (k {k})' for k, l in S['lv']))
print('  track', ' -> '.join(f'{t} (k {k})' for k, t in S['track']))
for (kk, sid), off in sorted(L.dmaoff.items()):
    print(f'  dma k {kk * 30:5d} sound {sid}: offset {off:7d} ({off / 9 * 16 / 11025:5.1f} s at 11 kHz)')
L.summary()
if A.falcon:
    print('  falcon on screen (k spans):', S.get('fal', []))
    D = S.get('fald')
    if D: print(f'FALDSUM FIN_K {FIN_K:.4f} least ratio {D["min"]} (ratio, k, mid, axis, half); eye inside the half length:',
                sum(b - a + 1 for a, b in D['in']), 'frames, k spans', D['in'])
    if A.check:                                                  # the camera kept out of the Falcon's hull (FIN_FALCON_AWAY)
        ok = bool(D) and D['min'][0] >= 1.0 and not D['in'] and any(a <= 20 and b >= 760 for a, b in S.get('fal', []))
        print('CHECK (falcon)', 'PASS' if ok else 'FAIL', f"least eye / half length {D['min'][0] if D else None} (>= 1.0), frames inside "
              f"{sum(b - a + 1 for a, b in D['in']) if D else None} (0), on screen {S.get('fal', [])} (one span over k 20..760)", flush=True)
        if not ok: sys.exit(1)
if AK:
    import wave, struct as _s, math
    raw = open(WAV[:-4] + '.raw', 'rb').read(); fr = AUD.audio_dump_freq()
    w = wave.open(WAV, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(fr); w.writeframes(raw); w.close()
    smp = _s.unpack('<%dh' % (len(raw) // 2), raw)
    print('  audio', WAV, fr, 'Hz;', 'level per 30 VIs (k: dBFS)')
    out = []
    for (k0, a), (k1, b) in zip(AMARK, AMARK[1:]):
        seg = smp[2 * a:2 * b]
        r = math.sqrt(sum(x * x for x in seg) / max(1, len(seg)))
        out.append(f'{k0}:{20 * math.log10(max(r, 1) / 32768):.0f}')
    for i in range(0, len(out), 12): print('   ', ' '.join(out[i:i + 12]))
    h = smp[:2 * fr // 2]
    st_ = max((abs(h[i + 2] - h[i]) for i in range(len(h) - 2)), default=0)
    print(f'  largest sample step in the first 0.5 s: {st_} ({st_ / 32768:.3f} of full scale)')
