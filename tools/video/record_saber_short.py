#!/usr/bin/env python3
"""Takes for the vertical saber Short (compose_short.py): one clip per run, game audio with it.

    cd harness && PAYLOAD_BUILD=../local/build/<b> RES=1440x1080 SHOTS=vid_short_<clip> M64CPU=0 \\
        AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib \\
        .venv/bin/python3 ../tools/video/record_saber_short.py <out.json> <clip>

(RES 1440x1080: a 1920x1440 GLideN64 window does not fit this Mac's screen and its shots come out clipped with noise.)

Clips (CLIPS): draw (C-up from the Stunner: the saber on, the hum), cut (one B tap), combo (three taps: sw1 -> sw2 ->
sw3), spin (B held: sw1, then the spin as a hop), deflect (three guards alerted, their own AI firing, held about DEFL_AT ahead
facing Luke: the parry poses, the bolts turned back), run (the stick full forward while three guards held about RUN_AT ahead of
his start fire: the arms parry, the run goes on), jump (two standing jumps with the saber out, two guards held idle
beside him for scale). Runs the build's own ROM (PAYLOAD_BUILD/sote-patch.z64) from palace.st (its held radio line let
go), as record_saber_takes.py starts: the Look on Luke, every weapon given, the drop view (L twice), the saber drawn
by the game's C-up cycle (all but draw before the take), the other guards held idle in their places, Luke's health
held. Debug Display written off (this Short's clean frame). The drop camera's eye: the start place + the clip's
cam (out, deg from his facing, up), or for the run and the swings his place + cam every VI (it tracks him: his steps forward
would take him into a fixed eye). The take starts PRE s of
game time after the draw (deflect, run: after the first bolt is turned, the guards then firing) and lasts the clip's dur s (game clock); a shot every 2nd VI (30 fps at the console's 60 VIs)
and per shot {t, b, label, clip, m (g_saber_move), defl (g_saber_deflects), w (g_saber_parry_w), z (his height over
the start), sx (his chest across the screen, -1..1, through the active camera), aud (audio_dump_frames)}; audio in <out>.wav. CAM=out,deg,up overrides the clip's eye; PROBE=1 cycles the
eye's angle through 0..315 every 60 VIs (framing stills).

Knobs for the second cut (saber_short_v2, `compose_short.py <out> short2`):
  STATE=<file>  the savestate in local/states (default palace.st; short2: play.st, the Echo Base hangar, bright, its
                snowtroopers are Trops of kind 0 that fire Blst bolts: the same staging as the palace guards; outside
                the palace the guards are the kind-0 Trops nearest him: the pool's first ones stand in far sectors
                and, moved to him, never fired; six of them (GUARDS6) and a walking one (state 2: the walk ends in a
                shot only from its own sector) written back to state 1, stand and aim: play.st with TURN=60 measured
                three of the six firing, ~3 bolts/s; TURN=0 one, ~1/s).
  TURN=<deg>    his start yaw turned by this (play.st: 60, facing +x into the hangar, where the moved guards fire).
  ORBIT=<deg>   the camera orbits in front of him: over the clip's arc window (the composed window, ORB[clip]['arc'],
                game time) the eye travels from -ORBIT to +ORBIT deg off his start facing through his front (cosine
                eased), the sign alternating clip to clip (draw left->right, cut right->left, ...); the eye at ORB's r
                out, up over the floor, around his current place (the start place for the still clips and the jump);
                ORB's dur replaces the clip's. The look point is the game's own (entry 9 looks at the player's +0x108,
                his head, 5.5 over his feet): its z offset (entry 9 +0x74) is written LOOK_DZ (his chest), and in the
                jump so that the aim stays at ORB's aim over the floor (the eye's height fixed: the rise reads). The
                jump's two scale guards stand behind his shoulders (SIDE2) so the arc does not pass behind them.
  ORBR=<x>      ORB's r scaled by x, the jump's by 1 + (x - 1) / 2 (short3, saber_short_v3: 1.3, the camera farther: the
                blade's swings left v2's frame).
"""
import ctypes as C, json, math, os, struct, sys, wave
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
import inject as inj
from m64 import Emu, BTN
from inject import inject, syms

m64.GLN_INT.update(AspectRatio=1, MultiSampling=0, FXAA=0, EnableN64DepthCompare=0, bilinearMode=1,
                   EnableFBEmulation=1, txFilterMode=0, txEnhancementMode=0, EnableHWLighting=0,
                   UseNativeResolutionFactor=0, ThreadedVideo=0, ShowFPS=0, ShowVIS=0, ShowPercent=0)
S = syms()
OUT, CLIP = os.path.abspath(sys.argv[1]), sys.argv[2]
RAW = OUT[:-5] + '.raw'
AUD = C.CDLL(os.environ['AUDIOPLUGIN']) if os.environ.get('AUDIOPLUGIN') else None
if AUD: AUD.audio_dump_frames.restype = C.c_long
PROBE = bool(os.environ.get('PROBE'))
DEFL_AT, RUN_MAX = 40.0, 92.0        # the run's guards: kept DEFL_AT ahead of him, at most RUN_MAX from the start (the far wall)
# dur (s), cam (out, deg, up), taps (s), B held (from, to), A taps (s), run from (s)
CLIPS = {
    'draw':    dict(dur=4.5, cam=(8.5, 35.0, 1.6), cu=(1.2,)),
    'cut':     dict(dur=3.8, cam=(8.5, 35.0, 1.6), taps=(0.5, 2.1), track=True),
    'combo':   dict(dur=5.4, cam=(8.5, 35.0, 1.6), taps=(0.5, 0.8, 1.18, 2.9, 3.2, 3.58), track=True),
    'spin':    dict(dur=7.4, cam=(10.0, 35.0, 2.0), held=((0.5, 1.3), (2.8, 3.6), (5.1, 5.9)), track=True),
    'deflect': dict(dur=13.0, cam=(9.0, 30.0, 2.0), guards=((DEFL_AT, -8.0), (DEFL_AT - 4, 0.0), (DEFL_AT + 4, 8.0)),
                    wait=True),
    'run':     dict(dur=5.5, cam=(10.0, 50.0, 2.2), guards=((DEFL_AT, -8.0), (DEFL_AT - 4, 0.0), (DEFL_AT + 4, 8.0)), run=0.4,
                    track=True, wait=True, ahead=RUN_MAX),
    'jump':    dict(dur=9.8, cam=(14.0, 0.0, 7.0), jumps=(0.7, 3.0, 5.3, 7.6), side=((0.0, -4.5), (0.0, 4.5))),
}
CL = dict(CLIPS[CLIP])
STATE = os.environ.get('STATE', 'palace.st')
ORBIT = float(os.environ.get('ORBIT', 0))
LOOK_DZ = -1.3                          # the look point from his head (+0x108) to his chest
ORB = {   # r out, up over the floor, arc window (s, game time), the clip's dur
    'draw':    dict(r=8.0, up=4.0, arc=(0.3, 5.0), dur=5.0),
    'cut':     dict(r=8.0, up=4.0, arc=(0.2, 4.2), dur=4.2),
    'combo':   dict(r=8.0, up=4.0, arc=(0.2, 5.6), dur=5.6),
    'spin':    dict(r=9.5, up=4.5, arc=(0.2, 7.4), dur=7.4),
    'deflect': dict(r=8.5, up=4.0, arc=(0.0, 12.0), dur=12.6),
    'run':     dict(r=9.5, up=4.5, arc=(0.0, 3.85), dur=4.2),   # on play.st he meets the guards' cap (RUN_MAX) at 3.9 s
    'jump':    dict(r=13.0, up=6.0, aim=8.0, arc=(0.3, 9.8), dur=9.8),
}
ORBR = float(os.environ.get('ORBR', 1))   # ORB's r scaled (short3: 1.3, the blade's swings left v2's frame); the jump's by half as much
for k, o in ORB.items(): o['r'] *= ORBR if k != 'jump' else 1 + (ORBR - 1) / 2
SIDE2 = ((-3.0, -5.0), (-3.0, 5.0))
TURN = float(os.environ.get('TURN', 0))
GUARDS6 = tuple((DEFL_AT + (i % 3 - 1) * 4, (i - 3) * 7.0) for i in range(6))
if ORBIT:
    CL['dur'] = ORB[CLIP]['dur']
    if CLIP == 'jump': CL['side'] = SIDE2
if STATE != 'palace.st' and 'guards' in CL: CL['guards'] = GUARDS6
SIGN = 1 if list(CLIPS).index(CLIP) % 2 == 0 else -1
CAM = tuple(float(x) for x in os.environ['CAM'].split(',')) if os.environ.get('CAM') else CL['cam']
PRE = 1.2 if CLIP == 'deflect' else 0.6          # s from the draw to the take (deflect: the guard's first shots)
e = Emu(str(inj.BUILD / 'sote-patch.z64'), video=m64.GLN)
VIEW, EYE = 0x800E0EEC, 0x8018DD98       # the on-foot view (4: drop); the drop camera's eye
DEBUG_DISPLAY = 0x800DA6D0
TROP_HP, TROP_STATE, TROP_TIMER = 0x7C, 0x78, 0x80
NAMES = {0: 'Cut 1', 1: 'Cut 2', 2: 'Cut 3', 3: 'Spin'}
st = {'k0': None, 'log': []}


def r32(a): return e.r32(a)
def s32(v): return struct.unpack('<i', struct.pack('<I', v))[0]
def V(o, a): return [e.rf(o + a + 4 * i) for i in range(3)]
def clock(): return struct.unpack('>d', struct.pack('>II', r32(0x8018E9A8), r32(0x8018E9AC)))[0]


def trops():
    p = r32(0x80112830)
    for i in range(80):
        rec = r32(p + 4 * i)
        if not rec: break
        if r32(rec) == 0x54726F70:
            return [r32(rec + 0x10) + j * r32(rec + 0x0C) for j in range(r32(rec + 8))]
    return []


def put(o, p, yaw):
    for a in range(3): e.wf(o + 0x08 + 4 * a, p[a]); e.wf(o + 0x50 + 4 * a, p[a])
    e.wf(o + 0x14, yaw)
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    for a, v in enumerate((c, s_, 0)): e.wf(o + 0x20 + 4 * a, v)
    for a, v in enumerate((-s_, c, 0)): e.wf(o + 0x30 + 4 * a, v)


def orbit(u, p):
    """the orbit's eye at take time u (s): -ORBIT .. +ORBIT deg (times SIGN) off his start facing, cosine eased"""
    o = ORB[CLIP]; a, b = o['arc']
    f = min(1.0, max(0.0, (u - a) / (b - a)))
    deg = SIGN * ORBIT * -math.cos(math.pi * f)
    q = eye_at(p, (o['r'], deg, 0.0)); q[2] = st['p0'][2] + o['up']
    return q


def eye_at(p, cam):
    f = math.atan2(st['fw'][1], st['fw'][0]) + math.radians(cam[1])
    return [p[0] + cam[0] * math.cos(f), p[1] + cam[0] * math.sin(f), p[2] + cam[2]]


def rel(q):
    """a place as (forward, right, up) from the start place along his first facing"""
    p0, fw = st['p0'], st['fw']; d = [q[0] - p0[0], q[1] - p0[1]]
    return [round(d[0] * fw[0] + d[1] * fw[1], 2), round(d[0] * fw[1] - d[1] * fw[0], 2), round(q[2] - p0[2], 2)]


def sx(p):
    """Luke's chest (his place + 2.5 up) across the screen through the active camera: -1 left .. 1 right"""
    cam = r32(0x800D08A4)
    if not cam: return 0.0
    eye, R, F = V(cam, 0x44), V(cam, 0x14), V(cam, 0x24)
    fovy = e.rf(0x80192F14); asp = e.rf(0x80192F18) or 4 / 3
    px = (1 / math.tan(math.radians(fovy) / 2) if 1 < fovy < 179 else 1.0) / asp
    d = [p[0] - eye[0], p[1] - eye[1], p[2] + 2.5 - eye[2]]
    x, z = sum(d[j] * R[j] for j in range(3)), sum(d[j] * F[j] for j in range(3))
    return round(px * x / z, 4) if z > 0.5 else 0.0


def finish():
    json.dump(st['log'], open(OUT, 'w'))
    if AUD:
        AUD.audio_dump_stop()
        w = wave.open(OUT[:-5] + '.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2)
        w.setframerate(AUD.audio_dump_freq()); w.writeframes(open(RAW, 'rb').read()); w.close()
        os.remove(RAW)
    print('log', OUT, len(st['log']), 'shots', 'deflects', r32(S['g_saber_deflects']), flush=True); e.stop()


def take(k, h):
    if k == 9:
        e.w32(S['g_guard_on'], 2)
        e.w32(h + 0xB8, (r32(h + 0xB8) & 0xFFFF) | (4 << 16))      # the Stunner: C-up draws the saber
        if TURN:    # his start yaw turned (deg; facing = yaw + 90)
            y = e.rf(h + 0x14) + TURN; e.wf(h + 0x14, y); e.wf(h + 0x8C, y)
            st['p0'] = V(h, 0x50); st['yaw0'] = (y, y)
            st['fw'] = [math.cos(math.radians(y + 90)), math.sin(math.radians(y + 90))]
        else:
            st['p0'] = V(h, 0x50); st['yaw0'] = (e.rf(h + 0x14), e.rf(h + 0x8C))
            fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = math.hypot(*fw); st['fw'] = [fw[0] / l, fw[1] / l]
        st['eye'] = eye_at(st['p0'], CAM)
        kind0 = [o for o in trops() if e.rf(o + TROP_HP) > 0 and not r32(o + 0x74) & 0xF]
        if STATE != 'palace.st':    # the nearest first: a far one's sector does not run its AI (it never fires)
            kind0.sort(key=lambda o: math.dist(V(o, 0x50), st['p0']))
        st['g'] = kind0[:len(CL.get('guards', ()))]
        st['side'] = kind0[len(st['g']):len(st['g']) + len(CL.get('side', ()))]
        st['tp'] = {o: (V(o, 0x50), e.rf(o + 0x14)) for o in trops() if o not in st['g'] and o not in st['side']}
        for g in st['g']: e.w32(g + 0x74, r32(g + 0x74) | 0x20)       # alerted: its own AI fires
    if k < 9: return 0
    e.w32(DEBUG_DISPLAY, r32(DEBUG_DISPLAY) & 0xFFFF)
    p0, fw = st['p0'], st['fw']; rt = (fw[1], -fw[0])
    if e.r16(VIEW) == 4 and ORBIT:
        u = clock() - st['ts'] if 'ts' in st else 0.0
        eye = orbit(u, V(h, 0x50) if CL.get('track') else p0)
        for a in range(3): e.wf(EYE + 4 * a, eye[a])
        ent = r32(0x800D08A0) + 9 * 0x80        # entry 9's look offset z: his chest, or the jump's fixed aim
        dz = LOOK_DZ if 'aim' not in ORB[CLIP] else ORB[CLIP]['aim'] - (e.rf(h + 0x140) - p0[2])
        e.wf(ent + 0x74, dz)
    elif e.r16(VIEW) == 4:
        cam = CAM
        if PROBE: cam = (CAM[0], (k // 60) * 45.0, CAM[2])
        eye = eye_at(V(h, 0x50), cam) if (CL.get('track') or PROBE) else st['eye']
        for a in range(3): e.wf(EYE + 4 * a, eye[a])
    for o, (q, yaw) in st['tp'].items():
        put(o, q, yaw); e.w32(o + TROP_STATE, 0); e.wf(o + TROP_TIMER, 100.0); e.wf(o + TROP_HP, 100.0)
    for o, (f_, s_) in zip(st['side'], CL.get('side', ())):   # jump: two guards beside him for scale, held idle
        put(o, [p0[0] + f_ * fw[0] + s_ * rt[0], p0[1] + f_ * fw[1] + s_ * rt[1], p0[2]], st['yaw0'][0])
        e.w32(o + TROP_STATE, 0); e.wf(o + TROP_TIMER, 100.0); e.wf(o + TROP_HP, 100.0)
    run = 0.0
    if CL.get('ahead'):     # the run: the guards slide ahead with him
        q = V(h, 0x50); run = (q[0] - p0[0]) * fw[0] + (q[1] - p0[1]) * fw[1]
    for g, (f_, s_) in zip(st['g'], CL.get('guards', ())):    # the firing guards: held in place facing back along his facing
        f_ = min(f_ + run, CL['ahead'] + f_ - DEFL_AT) if CL.get('ahead') else f_
        put(g, [p0[0] + f_ * fw[0] + s_ * rt[0], p0[1] + f_ * fw[1] + s_ * rt[1], p0[2]],
            math.degrees(math.atan2(fw[0], -fw[1])) % 360); e.wf(g + TROP_HP, 1000.0)
        if STATE != 'palace.st' and r32(g + TROP_STATE) == 2: e.w32(g + TROP_STATE, 1)   # a walk: back to stand and aim
    if 10 <= k < 14 or 40 <= k < 44: return BTN['L']   # follow -> first person -> drop
    if CLIP != 'draw' and 60 <= k < 64: return BTN['CU']   # the Stunner -> the saber
    if k < 64: return 0
    now = clock()
    if 'ts' not in st:
        st.setdefault('pre', now)
        if now - st['pre'] < PRE or k < 90 or (CL.get('wait') and not r32(S['g_saber_deflects'])):
            if not st['g'] or CL.get('track'):      # held at the start until the take
                for a in range(3): e.wf(h + 0x08 + 4 * a, p0[a]); e.wf(h + 0x50 + 4 * a, p0[a]); e.wf(h + 0x98 + 4 * a, 0.0)
                e.wf(h + 0x14, st['yaw0'][0]); e.wf(h + 0x8C, st['yaw0'][1])
            return 0
        st['ts'] = now; st['vi0'] = k
        if AUD: AUD.audio_dump_start(RAW.encode())
        print('take starts at k', k, 'deflects', r32(S['g_saber_deflects']), flush=True)
    u = now - st['ts']
    if u >= CL['dur'] and (k - st['vi0']) % 2 == 0: finish(); return 0
    b, x, y = 0, 0, 0
    if any(t <= u < t + 0.07 for t in CL.get('taps', ())): b |= BTN['B']
    if any(t <= u < t + 0.07 for t in CL.get('cu', ())): b |= BTN['CU']
    if any(t <= u < t + 0.07 for t in CL.get('jumps', ())): b |= BTN['A']
    if any(a <= u < b_ for a, b_ in CL.get('held', ())): b |= BTN['B']
    if CL.get('run') is not None and u >= CL['run']: y = 80
    if (k - st['vi0']) % 2 == 0:
        m = s32(r32(S['g_saber_move']))
        e.shot()
        st['log'].append({'t': round(u, 3), 'b': ''.join(n for n in ('A', 'B', 'CU') if b & BTN[n]), 'label': NAMES.get(m, ''),
                          'clip': CLIP, 'm': m, 'defl': r32(S['g_saber_deflects']),
                          'w': round(e.rf(S['g_saber_parry_w']), 3), 'z': round(e.rf(h + 0x58) - p0[2], 3),
                          'pos': [round(v, 2) for v in V(h, 0x50)], 'wid': s32(r32(h + 0xB8)) >> 16,
                          'sx': sx(V(h, 0x50)), 'side': [rel(V(o, 0x50)) for o in st['side']],
                          'eye': rel(V(r32(0x800D08A4), 0x44)) if r32(0x800D08A4) else None, 'aud': AUD.audio_dump_frames() if AUD else 0})
    return b, x, y


def script(e_, n):
    if n == 1: e.unlimit(False)            # real time: full speed drops screenshots
    if n < 60: return
    if st['k0'] is None:
        e.load_state(os.path.join(paths.STATES, STATE)); st['k0'] = n; return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 4: return
    if e.r16(0x800DD2D0): e.w32(0x800DD2D0, e.r32(0x800DD2D0) & 0xFFFF); e.wf(0x800D07FC, 0)   # the held line
    h = r32(S['g_player'])
    if not h: e.pad(0); return
    e.wf(h + 0xB4, 100.0)
    if k == 8:
        for i in range(6): e.wf(h + 0xC0 + 4 * i, 50.0)
        e.w32(h + 0x74, r32(h + 0x74) | 0x3E000)
    r = take(k, h)
    e.pad(*r) if isinstance(r, tuple) else e.pad(r)


e.run(script)
