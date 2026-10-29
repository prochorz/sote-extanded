#!/usr/bin/env python3
"""Record the Gall Run flight (feature gallrun: two stages on the base level) with game audio, in segments.

    cd harness
    for s in $(seq 0 20); do            # (stop when a segment ends early: the run is over)
      RES=960x720 SHOTS=gallrun_take$s M64CPU=0 AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib PAYLOAD_BUILD=<build> \\
          python3 ../tools/video/record_gallrun_take.py <build>/sote-patch.z64 run/gallrun_take$s.json $s
    done

mupen keeps at most 1000 screenshots per directory, so the ~9 min run is recorded in segments
of SEG frames (a shot every 2nd frame): segment 0 loads states/src_base.st, injects the payload,
starts the mission (g_gallrun, sub-level 32 queued as gallrun_start() does: so the ROM must be the gallrun build's) and
records; every segment saves a state at its end (run/gallrun_take<s>.st) that the next one continues from. The ship's
health is kept full (METRICS=<json>: per game frame the health the game left before that, the stage, node, pad, the
ship's place, the camera, stage 2's fighters in view / downed: harness/gallrun/pilot_metrics.py sums them up).
A stand-in pilot, every stick through smooth() (a low pass and a rate limit: STICK_ALPHA, STICK_RATE, no jerks):
- stage 1 (gallrun.c fly()): pure pursuit of the route (Chor's line) PURSUE_LEN units ahead of the ship's nearest node,
  A off before sharp bends or with the nose far off (SLOW_ERR, SLOW_BEND: the Falcon turns wider than the Outrider; Chor
  keeps the ship's pace), Z on edge in a slit; with WAY=<gallrun/bot_plan.py json> along that way instead;
- stage 2 and the rail after the end scene: gunner() turns the gun (camera entry 5's matrix) at the nearest live fighter,
  GUN_LEAD frames ahead of its motion, and fires B when it is within GUN_FIRE degrees or its size (GUN_SIZE) of the aim
  (GUN_GAIN; GUNNER=0: the old blind sweep);
- the end scene: after Slave I; the final battle (g_native, the game's own flight): tower_run() carries the Falcon along
  passes at each standing tower firing (work/chain_take.py's bot) till all six are down, then hunt() / the fly-away
  and the jump; the take ends when the level changes (the last scene, 31) or FREE_SECS after free flight began.
STOPNODE=<node>: the take ends there (a node in stage 2). STATE0=<path>: segment 0 starts from that savestate of the
mission already running (e.g. local/run/gallrun_1370.st, local/work/cliff_shots.py SAVE=1: the end scene's take).
SKIP_ALT=<units>: segment 0 records nothing till the Falcon is this high over the route's end (g_alt; 2500: space,
gallrun.c SKY_TO). ORBIT=<s>: free flight starts with that many seconds round the Star Destroyer (orbit(): no fire,
the ring and the ship seen), then the hunt. A segment ends early when the run is over (another sub-level).
JSON entries {t, label, aud, node (Chor's), switch (first stage 2 node)} per saved frame; audio
in <out>.wav.
"""
import ctypes as C, json, math, os, struct, sys, wave
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, BTN, HERE
from inject import inject, syms, GALL_VRAM

e = Emu(sys.argv[1], video=m64.GLN)
OUT, SEGI = sys.argv[2], int(sys.argv[3])
RAW = OUT[:-5] + '.raw'
TAKE = os.environ.get('TAKE', 'gallrun_take')   # TAKE=<name>: the segments' states run/<name><i>.st, the pilot's run/<name>_pilot.json
STATE = lambda i: os.path.join(paths.RUN, f'{TAKE}{i}.st')
AUD = C.CDLL(os.environ['AUDIOPLUGIN']) if os.environ.get('AUDIOPLUGIN') else None
if AUD: AUD.audio_dump_frames.restype = C.c_long
SEG = int(os.environ.get('SEG', 1990))   # frames per segment (SEG=1150: the opening shot and a few seconds on)
LEVEL_ID, RUN = 0x8013CE0E, 32               # (the mission is sub-level 32: its own level)
START = int(os.environ.get('START', 130))   # segment 0: frames spent on This Level before recording (START=12: from the fade in)
log = []
st = {'done': False}
SY = syms()


def stft_health():
    a = 0x80112808
    while a < 0x80113200 and e.r32(a) != 0x53746674: a += 0x30      # 'Stft'
    if a < 0x80113200 and e.r32(a + 8):
        hp = e.r32(e.r32(a + 0x10) + 0x240); e.w32(e.r32(a + 0x10) + 0x240, 0x1EF)
        return hp                                     # (what the game left, before it is kept full: METRICS)
    return None


def finish(t):
    if st['done']: return
    st['done'] = True
    json.dump(log, open(OUT, 'w'))
    if os.environ.get('METRICS'): json.dump(MET, open(os.environ['METRICS'], 'w'))
    if AUD:
        AUD.audio_dump_stop()
        w = wave.open(OUT[:-5] + '.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2)
        w.setframerate(AUD.audio_dump_freq()); w.writeframes(open(RAW, 'rb').read()); w.close()
        os.remove(RAW)
    print('segment', SEGI, 'frames', len(log), 'level', e.r16(LEVEL_ID), flush=True)


MET = []                                              # METRICS=<path>: one row per game frame (see met_row())
_pad = e.pad
def _padw(b=0, x=0, y=0):
    st['pad'] = (b, x, y); _pad(b, x, y)
e.pad = _padw


def smooth(key, b, x, y, rate=None, alpha=None):
    """The stick through a low-pass (alpha: share of the way to the target per frame) and a rate limit (rate: most the
    stick moves per frame): no jerks on video. Buttons pass."""
    rate = float(os.environ.get('STICK_RATE', 4)) if rate is None else rate
    alpha = float(os.environ.get('STICK_ALPHA', 0.2)) if alpha is None else alpha
    p = pst.setdefault('sm_' + key, [0.0, 0.0])
    for i, v in enumerate((x, y)):
        d = (v - p[i]) * alpha; p[i] += max(-rate, min(rate, d))
    return b, int(round(p[0])), int(round(p[1]))


WAY = json.load(open(os.environ['WAY']))['way'] if os.environ.get('WAY') else None
PILOT = os.path.join(paths.RUN, 'gallrun_pilot.json' if TAKE == 'gallrun_take' else f'{TAKE}_pilot.json')   # the way follower's place, carried across segments
pst = json.load(open(PILOT)) if SEGI and os.path.exists(PILOT) else {'wi': 0}


ROUTE = []


def route_pts():
    """The route's points (Chor's nodes, the ship's flown line is 10 under them), read once."""
    if not ROUTE:
        rt = e.r32(GALL_VRAM + 20) + 0x38
        for i in range(e.r32(GALL_VRAM + 48) + 4): ROUTE.append([e.rf(rt + i * 0x54 + 4 * j) for j in range(3)])
    return ROUTE


def wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


def pilot(node):
    """Stage 1: (buttons, stick x, y). WAY (gallrun/bot_plan.py json): follow that way (Z on edge where it goes low
    through a slit). Else pure pursuit of the route (Chor's, the Outrider's line): the point PURSUE_LEN units along it from
    the ship's nearest node, the stick through smooth() (rate limit + low pass), the height after the route's (-10), Z on
    edge in a slit (the image's edge table). The ship keeps Chor's pace by itself (gallrun.c leash): the pilot only steers."""
    S = syms()
    if not e.r32(S['g_fly_on']) or node > 2000: return smooth('s1', 0, 0, 0)   # (eased off too)
    pos = [e.rf(S['g_fly_pos'] + 4 * i) for i in range(3)]; yaw = e.rf(S['g_fly_yaw'])
    rt = e.r32(GALL_VRAM + 20) + 0x38
    ca = e.r32(GALL_VRAM + 72)
    R = route_pts()
    if WAY:
        wi = pst['wi']
        d = lambda i: math.hypot(WAY[i][0] - pos[0], WAY[i][1] - pos[1])
        while wi + 1 < len(WAY) and d(wi + 1) < d(wi) + 5: wi += 1
        pst['wi'] = wi
        tp = WAY[min(wi + 4, len(WAY) - 1)]; tz = max(tp[2], WAY[min(wi + 8, len(WAY) - 1)][2])
        low = not max(w[3] for w in WAY[wi:wi + 10])
        ri = node
    else:
        ri = pst.get('ri', node); lo, hi = max(ri - 6, 0), min(ri + 40, len(R) - 1)
        ri = min(range(lo, hi + 1), key=lambda i: (R[i][0] - pos[0]) ** 2 + (R[i][1] - pos[1]) ** 2 + 0.5 * (R[i][2] - 10 - pos[2]) ** 2)
        pst['ri'] = ri
        want = float(os.environ.get('PURSUE_LEN', 150)); acc = 0.0; k = ri
        while k + 1 < len(R) and acc < want:                 # (along the route's polyline from the nearest node)
            acc += math.dist(R[k][:2], R[k + 1][:2]); k += 1
        tp = R[k]; tz = R[min(ri + 2, len(R) - 1)][2] - 10; low = True
    err = wrap(math.atan2(tp[1] - pos[1], tp[0] - pos[0]) - yaw)
    slit = min(sum(struct.unpack('>hh', struct.pack('>I', e.r32(ca + (ri + 1 + i) * 8)))) for i in range(10)) < 12
    x = max(-80, min(80, -err * float(os.environ.get('PURSUE_GAIN', 160)))); y = max(-80, min(80, -(tz - pos[2]) * 2))
    # speed: the Falcon's turn (FLY_TURN) at cruise is a ~190 radius, tighter than the route's corners: A (the throttle) off
    # while the nose is far off the pursuit point or a sharp bend is near (the speed eases down to FLY_MIN, the ship
    # lags Chor within the leash, A again on the straight)
    tan = lambda i: math.atan2(R[min(i + 1, len(R) - 1)][1] - R[i][1], R[min(i + 1, len(R) - 1)][0] - R[i][0])
    bend = abs(wrap(tan(min(ri + 6, len(R) - 2)) - tan(min(ri + 1, len(R) - 2))))
    slow = pst.get('slow', 0)
    slow = (abs(err) > float(os.environ.get('SLOW_ERR', 0.4)) or bend > float(os.environ.get('SLOW_BEND', 1.1))) if not slow else \
        (abs(err) > 0.12 or bend > float(os.environ.get('SLOW_BEND', 1.1)) * 0.7)
    pst['slow'] = int(slow)
    return smooth('s1', (BTN['Z'] if slit and low else 0) | (0 if slow else BTN['A']), x, y)


def orbit():
    """Free flight: round the Star Destroyer (IMG_SD) ORBIT_R off it, ORBIT_UP over it, A held, no fire."""
    pos = [e.rf(SY['g_fly_pos'] + 4 * i) for i in range(3)]; yaw = e.rf(SY['g_fly_yaw'])
    sd = [e.rf(GALL_VRAM + 212 + 4 * i) for i in range(3)]
    a = math.atan2(pos[1] - sd[1], pos[0] - sd[0]) + 0.45
    R = float(os.environ.get('ORBIT_R', 1300))
    tg = [sd[0] + R * math.cos(a), sd[1] + R * math.sin(a), sd[2] + float(os.environ.get('ORBIT_UP', 350))]
    err = (math.atan2(tg[1] - pos[1], tg[0] - pos[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
    return BTN['A'], max(-80, min(80, int(-err * 160))), max(-60, min(60, int(-(tg[2] - pos[2]) * 0.3)))


def hunt():
    """Free flight: (buttons, stick x, y) turning the Falcon to the nearest live TIE fighter ahead (the chase's: TieF
    type 1), A held, firing (B) when it is within HUNT_FIRE degrees of the nose."""
    pos = [e.rf(SY['g_fly_pos'] + 4 * i) for i in range(3)]; yaw, pitch = e.rf(SY['g_fly_yaw']), e.rf(SY['g_fly_pitch'])
    hd = [math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), -math.sin(pitch)]
    best = None
    for k in range(6):                                # (the chase's: gallrun.c g_chase)
        o = e.r32(SY['g_chase'] + 4 * k)
        if not o or not e.rf(o + 0x60) > 0: continue
        p = [e.rf(o + 0x50 + 4 * j) for j in range(3)]; v = [p[j] - pos[j] for j in range(3)]; d = math.hypot(*v)
        if 20 < d < 2500:
            c = sum(v[j] * hd[j] for j in range(3)) / d
            sc = d * (2 - c)                          # (near and ahead first)
            if best is None or sc < best[0]: best = (sc, v, d, c)
    if best is None: return BTN['A'], 0, 0
    _, v, d, c = best
    ey = (math.atan2(v[1], v[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
    tp = -math.atan2(v[2], math.hypot(v[0], v[1])) if c > 0.5 else 0.0   # (behind: turn level first)   # (the stick's y sets the nose's pitch: 0.5 rad at full, gallrun.c FLY_PITCH)
    fire = c > math.cos(math.radians(float(os.environ.get('HUNT_FIRE', 20))))
    return BTN['A'] | (BTN['B'] if fire else 0), max(-80, min(80, int(-ey * 700 + (-8 if ey > 0.003 else 8 if ey < -0.003 else 0)))), max(-80, min(80, int(10 * (1 if tp > 0 else -1) + tp / 0.5 * 70)))


TIEF = 0x80112D48
TIE_HP = {}
GPREV = {}


def ties():
    """Stage 2's fighters: [(object, drawn place, live)] (TieF type 1, the first 10 slots; the drawn node's place as
    s2_gun.py reads it)."""
    tf, sz, n = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), min(e.r32(TIEF + 8), 10)
    out = []
    for i in range(n):
        t = tf + i * sz
        if (e.r32(t + 0x70) & 0xFF) != 1: continue
        nd = e.r32(t + 0x94); q = [e.rf(nd + 0x38 + 4 * j) for j in range(3)] if 0x80000000 <= nd < 0x80800000 else [e.rf(t + 0x50 + 4 * j) for j in range(3)]
        shown = (e.r16(nd + 2) >> 8) == 0xFF if 0x80000000 <= nd < 0x80800000 else False
        hp = e.rf(t + 0x60)
        out.append((i, q, hp > 0 and e.r16(t + 0xA8) < 0x8000 and q[2] > -2000 and shown, hp))
    return out


def camv():
    """The active camera: (eye, forward unit, right, up)."""
    act = e.r32(0x800D08A4)
    f = [e.rf(act + 0x24 + 4 * j) for j in range(3)]; eye = [e.rf(act + 0x44 + 4 * j) for j in range(3)]
    l = math.sqrt(sum(x * x for x in f)) or 1; f = [x / l for x in f]
    r = [f[1], -f[0], 0]; rl = math.hypot(r[0], r[1]) or 1; r = [x / rl for x in r]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    return eye, f, r, u


def gunv():
    """The gun's own aim (stage 2: camera entry 5's matrix, s2_gun.py: forward row +0x10, place +0x30; the view's
    forward row has no pitch in it): (place, forward unit, right, up), else the camera's."""
    ent = e.r32(0x800D08A0); g5 = e.r32(ent + 5 * 0x80 + 8) if ent else 0
    if not 0x80000000 <= g5 < 0x80800000: return camv()
    f = [e.rf(g5 + 0x10 + 4 * j) for j in range(3)]; eye = [e.rf(g5 + 0x30 + 4 * j) for j in range(3)]
    l = math.sqrt(sum(x * x for x in f))
    if l < 0.5: return camv()
    f = [x / l for x in f]
    r = [f[1], -f[0], 0]; rl = math.hypot(r[0], r[1]) or 1; r = [x / rl for x in r]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    return eye, f, r, u


def tie_angles(c, q):
    """(yaw error, pitch error) in radians of a place seen from the camera c (positive: to the right, up) and the
    distance along its forward."""
    eye, f, r, u = c; v = [q[j] - eye[j] for j in range(3)]
    z = sum(v[j] * f[j] for j in range(3)); x = sum(v[j] * r[j] for j in range(3)); y = sum(v[j] * u[j] for j in range(3))
    return math.atan2(x, z), math.atan2(y, math.hypot(x, z) if z > 0 else -1), z


def gunner(g):
    """Stage 2: (buttons, stick x, y). Turn the gun to the nearest live fighter in front (the stick moves the aim at
    a rate: GUN_GAIN) and fire B when it is within GUN_FIRE degrees of the crosshair; none: a slow sweep, no fire."""
    c = gunv(); best = None; lead = float(os.environ.get('GUN_LEAD', 6))
    for i, q, live, hp in ties():
        if not live: continue
        pq, pe = GPREV.get(i, (q, c[0])); GPREV[i] = (q, c[0])
        if math.dist(pq, q) < 100:                        # (its motion against the gun's own, `lead` frames on)
            q = [q[j] + ((q[j] - pq[j]) - (c[0][j] - pe[j])) * lead for j in range(3)]
        ay, ap, z = tie_angles(c, q)
        if z < 30 or z > 3500 or abs(ay) > 1.3: continue
        sc = math.hypot(ay, ap) + z / 20000
        if i == pst.get('tgt'): sc *= 0.5                 # (keeps its target: no swapping between two fighters)
        if best is None or sc < best[0]: best = (sc, ay, ap, z, i)
    if best is None: return 0, int(22 * math.sin(g / 120)), int(8 * math.sin(g / 170))
    _, ay, ap, z, pst['tgt'] = best
    gain = float(os.environ.get('GUN_GAIN', 170))
    if os.environ.get('GDBG') and g % 15 == 0: print('GUN', g, 'ay', round(math.degrees(ay), 1), 'ap', round(math.degrees(ap), 1), 'z', round(z), 'stick', st.get('pad'), 'fwd', [round(x, 2) for x in c[1]], flush=True)
    fire = math.hypot(ay, ap) < max(math.radians(float(os.environ.get('GUN_FIRE', 3))), math.atan2(float(os.environ.get('GUN_SIZE', 8)), z))   # (a fighter's size)
    return (BTN['B'] if fire else 0), max(-80, min(80, int(GUN_SX * ay * gain))), max(-80, min(80, int(GUN_SY * ap * gain)))


GUN_SX, GUN_SY = float(os.environ.get('GUN_SX', 1)), float(os.environ.get('GUN_SY', -1))


def met_row(g, stage, node, hp):
    c = camv(); gv = gunv(); pos = [e.rf(SY['g_fly_pos'] + 4 * i) for i in range(3)]
    row = dict(g=g, stage=stage, node=node, hp=hp, pad=st.get('pad', (0, 0, 0)), pos=pos, yaw=e.rf(SY['g_fly_yaw']),
               eye=c[0], fwd=c[1])
    if stage == 2:
        vis = 0; kills = 0; near = 9.0; row['gfwd'] = gv[1]
        for i, q, live, hp_ in ties():
            if TIE_HP.get(i, 0) > 0 and hp_ <= 0: kills += 1
            TIE_HP[i] = hp_
            if live:
                ay, ap, z = tie_angles(c, q)                      # (in view: the camera's; near: the gun's)
                if z > 0 and abs(ay) < 0.55 and abs(ap) < 0.42: vis += 1
                gy, gp, gz = tie_angles(gv, q)
                if gz > 0: near = min(near, math.hypot(gy, gp))
        row.update(vis=vis, kills=kills, near=near)
    MET.append(row)


TW_SIZE = 0x214


def towers():
    """The Star Destroyer's standing towers' places (gall_space.c towers_left(): the image's IMG_TOWERS record, pool
    entries of TW_SIZE, +0x140 bit 0x10 down, place +8), [] before they are on."""
    cnt, recs, tmpl, pool = (e.r32(GALL_VRAM + 304 + 4 * i) for i in range(4))
    if not cnt or e.r32(0x80112C28 + 0x10) != pool: return []
    return [[e.rf(pool + i * TW_SIZE + 8 + 4 * j) for j in range(3)] for i in range(cnt) if not e.r32(pool + i * TW_SIZE + 0x140) & 0x10]


PASS_FROM, PASS_UP, PASS_TO, PASS_LOW = 700.0, 160.0, 95.0, 45.0   # (work/tower_video.py's passes)
SPEED, PASS_SPEED, TURN_OUT, TURN_IN, TURN_RATE, LEAVE_UP = 420.0, 300.0, 450.0, 500.0, 2.4, 260.0
TW = {'t': None, 'seg': None}


def bez(q, u):
    return [(1 - u) ** 3 * q[0][i] + 3 * (1 - u) ** 2 * u * q[1][i] + 3 * (1 - u) * u * u * q[2][i] + u ** 3 * q[3][i] for i in range(3)]


def lerp(a, b, u): return [a[i] + (b[i] - a[i]) * u for i in range(3)]


def tw_plan(p, d, tp, last=False):
    """(work/tower_video.py plan()) up and round to a pass's start, then the pass straight at the tower. last: the last
    tower's pass high (LAST_UP, LAST_TO, LAST_LOW): the game's fly-away (gall_native.c, at most a 15 deg climb) starts
    where the tower falls, and from a low pass it ran the Falcon and the camera into the hull's superstructure."""
    PASS_UP, PASS_TO, PASS_LOW = (float(os.environ.get(k, v)) for k, v in (('LAST_UP', 320), ('LAST_TO', 300), ('LAST_LOW', 240))) \
        if last else (globals()['PASS_UP'], globals()['PASS_TO'], globals()['PASS_LOW'])
    sd = [e.rf(GALL_VRAM + 212 + 4 * i) for i in range(3)]; o = [tp[0] - sd[0], tp[1] - sd[1]]; l = math.hypot(*o) or 1; o = [o[0] / l, o[1] / l, 0]
    start = [tp[0] + o[0] * PASS_FROM, tp[1] + o[1] * PASS_FROM, tp[2] + PASS_UP]
    end = [tp[0] + o[0] * PASS_TO, tp[1] + o[1] * PASS_TO, tp[2] + PASS_LOW]
    inward = [end[i] - start[i] for i in range(3)]; li = math.sqrt(sum(q * q for q in inward)); inward = [q / li for q in inward]
    q = [p, [p[i] + d[i] * TURN_OUT + (LEAVE_UP if i == 2 else 0) for i in range(3)], [start[i] - inward[i] * TURN_IN for i in range(3)], start]
    L = sum(math.dist(q[j], q[j + 1]) for j in range(3))
    return [(q, max(1.5, L / SPEED), 'go'), ([start, lerp(start, end, 1 / 3), lerp(start, end, 2 / 3), end], li / PASS_SPEED, 'pass')]


def sd_top():
    """The Star Destroyer's highest vertex on the flat (its bridge; gall_native.c sd_axis()'s top), read once."""
    if 'top' not in TW:
        c = e.r32(GALL_VRAM + 268); n, tris = e.r32(c), e.r32(c + 4); best = (-1e9, 0, 0)
        s16 = lambda a: e.r16(a) - 65536 if e.r16(a) >= 32768 else e.r16(a)
        for k in range(n * 3):
            v = tris + 24 * (k // 3) + 6 * (k % 3); z = s16(v + 4)
            if z > best[0]: best = (z, s16(v), s16(v + 2))
        TW['top'] = [best[1], best[2]]
    return TW['top']


def tower_run(g):
    """The final battle (g_native: the game's own flight, which a scripted stick did not steer): as work/chain_take.py's
    bot, the Falcon is carried along passes at each standing tower in turn (its place and rows written, turning at most
    TURN_RATE), B fires the game's lasers while it is lined up. Returns the buttons."""
    s = e.r32(0x80112CB8 + 0x10)
    cnt, recs, tmpl, pool = (e.r32(GALL_VRAM + 304 + 4 * i) for i in range(4))
    alive = [i for i in range(cnt) if not e.r32(pool + i * TW_SIZE + 0x140) & 0x10]
    if not s or not alive: return 0
    v3 = lambda a: [e.rf(a + 4 * i) for i in range(3)]
    p = v3(s + 0x50); f = v3(s + 0x30)
    if TW['t'] not in alive or not TW['seg'] or (len(alive) == 1 and not TW.get('last')):   # (the last tower: its high pass)
        if TW['t'] not in alive:                      # (nearest first; the one farthest from the bridge kept for last:
            cand = alive                              # the fly-away runs to the stern past the bridge, from there it
            if len(alive) > 1:                        # has the most room to climb over it)
                far = max(alive, key=lambda i: math.dist(sd_top(), v3(pool + i * TW_SIZE + 8)[:2]))
                cand = [i for i in alive if i != far]
            TW['t'] = min(cand, key=lambda i: math.dist(p, v3(pool + i * TW_SIZE + 8)))
        TW['last'] = len(alive) == 1
        TW['seg'] = tw_plan(TW.get('at', p), TW.get('dir', f), v3(pool + TW['t'] * TW_SIZE + 8), TW['last']); TW['u'] = 0.0
    qq, secs, kind = TW['seg'][0]
    TW['u'] += 1.0 / 60 / max(secs, 1e-3); uu = min(TW['u'], 1.0)
    here = bez(qq, uu); ahead = bez(qq, min(uu + 0.02, 1.0)) if uu < 0.98 else [qq[3][i] + (qq[3][i] - qq[2][i]) for i in range(3)]
    if TW['u'] >= 1.0: TW['seg'].pop(0); TW['u'] = 0.0
    TW['at'] = here
    tp = v3(pool + TW['t'] * TW_SIZE + 8)
    want = [tp[0] - here[0], tp[1] - here[1], tp[2] + 8 - here[2]] if kind == 'pass' else [ahead[i] - here[i] for i in range(3)]
    lw = math.sqrt(sum(q * q for q in want)) or 1; want = [q / lw for q in want]
    cur = TW.get('dir', f); ang = math.acos(max(-1, min(1, sum(cur[i] * want[i] for i in range(3))))); step = TURN_RATE / 60
    if ang > step:
        t_ = step / ang; nd = [cur[i] + (want[i] - cur[i]) * t_ for i in range(3)]; ln = math.sqrt(sum(q * q for q in nd)); nd = [q / ln for q in nd]
    else: nd = want
    TW['dir'] = nd
    hh = math.hypot(nd[0], nd[1]) or 1e-6; up_ = [-nd[0] * nd[2] / hh, -nd[1] * nd[2] / hh, hh]
    rt = [nd[1] * up_[2] - nd[2] * up_[1], nd[2] * up_[0] - nd[0] * up_[2], nd[0] * up_[1] - nd[1] * up_[0]]
    for i in range(3):
        e.wf(s + 8 + 4 * i, here[i]); e.wf(s + 0x50 + 4 * i, here[i])
        e.wf(s + 0x20 + 4 * i, rt[i]); e.wf(s + 0x30 + 4 * i, nd[i]); e.wf(s + 0x40 + 4 * i, up_[i])
    v = [tp[0] - here[0], tp[1] - here[1], tp[2] + 8 - here[2]]; l = math.sqrt(sum(c * c for c in v)) or 1; v = [c / l for c in v]
    ex = sum(v[i] * rt[i] for i in range(3)); ey = sum(v[i] * up_[i] for i in range(3)); ez = sum(v[i] * nd[i] for i in range(3))
    fire = kind == 'pass' and abs(math.atan2(ex, ez)) < 0.12 and abs(math.atan2(ey, ez)) < 0.12
    return BTN['B'] if fire and g % 6 < 3 else 0


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60:
        e.load_state((os.environ.get('STATE0') or os.path.join(paths.STATES, 'src_base.st')) if SEGI == 0 else STATE(SEGI - 1))
    if n == 62 and SEGI == 0 and not os.environ.get('STATE0'):
        inject(e); e.w32(syms()['g_gallrun'], 1)
        e.w32(0x800D2558, (e.r32(0x800D2558) & 0x00FFFFFF) | (2 << 24)); e.w32(0x800D255C, (e.r32(0x800D255C) & 0xFFFF) | (32 << 16))   # gallrun_start(): load 32 queued
    if n < 64: return
    k = n - 64
    if SEGI == 0 and k < START and not os.environ.get('STATE0'):
        e.pad(0); return
    t = k - (START if SEGI == 0 and not os.environ.get('STATE0') else 0)
    if st['done']:
        if t - st.get('skip', 0) >= st['stop']: e.stop()
        return
    if SEGI == 0 and os.environ.get('SKIP_ALT') and not st.get('rec'):   # (not yet in space: played, not recorded)
        if e.r16(0x800DD2D0): e.pad(BTN['A'] if n % 50 > 46 else 0, 0, 0)
        else: e.pad(BTN['B'] if (n // 6) % 2 else 0, 0, 0)
        stft_health(); st['skip'] = k + 1
        if e.rf(SY['g_alt']) >= float(os.environ['SKIP_ALT']): st['rec'] = True
        return
    t -= st.get('skip', 0)
    if t == 0 and AUD: AUD.audio_dump_start(RAW.encode())
    hp_left = stft_health()
    if os.environ.get('DBG'): e.w32(0x800DA6D0, (e.r32(0x800DA6D0) & 0xFFFF) | (2 << 16))   # DBG=1: Debug Display (pos, frame rate)
    chor = e.r32(0x80112A78 + 0x10) if e.r32(0x80112A78 + 8) else 0
    node = e.r32(chor + 0x6C) if chor else 0
    g = t + SEGI * SEG
    if not e.r16(0x800DD2D0): st['hold'] = 0
    if e.r16(0x800DD2D0):                             # a held radio line (~h): read a moment, then A
        st['hold'] = st.get('hold', 0) + 1                        # (HOLD_READ=<frames>: read that long first)
        e.pad(BTN['A'] if st['hold'] >= int(os.environ.get('HOLD_READ', 0)) and st['hold'] % 50 > 46 else 0, 0, 0)
    elif SY.get('g_free') and e.r32(SY['g_free']) and SY.get('g_sl_jump') and e.rf(SY['g_sl_jump']) >= 0:
        pst.setdefault('free0', g)
        e.pad(*smooth('free', *(orbit() if g - pst['free0'] < 60 * float(os.environ.get('ORBIT', 0)) else
                                hunt()), rate=8, alpha=0.4)) if not (e.r32(SY['g_native']) and towers()) else e.pad(tower_run(g))   # (the towers carried, then the TIEs)
        if g - pst['free0'] >= 60 * float(os.environ.get('FREE_SECS', 600)): st['freeover'] = True
        if os.environ.get('TWDBG') and g % 60 == 0:
            cnt_, pool_ = e.r32(GALL_VRAM + 304), e.r32(GALL_VRAM + 316)
            print('TW', g, 'native', e.r32(SY['g_native']), 'towers', len(towers()), 'alive', [i for i in range(cnt_) if pool_ and not e.r32(pool_ + i * TW_SIZE + 0x140) & 0x10],
                  'pool', hex(pool_), hex(e.r32(0x80112C28 + 0x10)), 'tgt', TW['t'], 'last', TW.get('last'), 'seg', TW['seg'] and TW['seg'][0][2], flush=True)
    elif node < e.r32(GALL_VRAM + 48):                # stage 1: fly
        e.pad(*pilot(node))
    elif node > e.r32(GALL_VRAM + 28) + 8 and node < e.r32(GALL_VRAM + 16) - 2:   # the rail after the scene: shoot
        e.pad(*smooth('gun', *gunner(g), rate=6, alpha=0.35))   # (as stage 2)
    elif node >= e.r32(GALL_VRAM + 28) - 1:           # the route's end: the scene (no control), then free flight
        S = syms()                                    # after Slave I (g_sl), A held
        pos = [e.rf(S['g_fly_pos'] + 4 * i) for i in range(3)]; yaw = e.rf(S['g_fly_yaw'])
        tg = [e.rf(S['g_sl'] + 4 * i) for i in range(3)]
        err = (math.atan2(tg[1] - pos[1], tg[0] - pos[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
        e.pad(BTN['A'], max(-80, min(80, int(-err * 160))), max(-80, min(80, int(-(tg[2] - 15 - pos[2]) * 2))))
    else:                                            # stage 2: shoot
        e.pad(*(smooth('gun', *gunner(g), rate=float(os.environ.get('GUN_RATE', 6)), alpha=float(os.environ.get('GUN_ALPHA', 0.35)))
                if os.environ.get('GUNNER', '1') != '0' else (BTN['B'] if (g // 6) % 2 else 0, int(22 * math.sin(g / 120)), int(8 * math.sin(g / 170)))))
    if os.environ.get('METRICS') and SY.get('g_fly_pos'):
        stage = 1 if node < e.r32(GALL_VRAM + 48) else 2 if node < e.r32(GALL_VRAM + 28) - 1 else 3
        met_row(g, stage, node, hp_left)
    st['hf'] = st.get('hf', 0) + 1
    if t % 2 == 0:
        e.shot()
        chor = e.r32(0x80112A78 + 0x10) if e.r32(0x80112A78 + 8) else 0
        free = e.r32(SY['g_free']) and e.rf(SY['g_sl_jump']) >= 0
        log.append(dict(t=t, label='won' if free and e.r32(SY['g_won']) else 'free' if free else '', aud=AUD.audio_dump_frames() if AUD else 0,
                        node=e.r32(chor + 0x6C) if chor else 0, switch=e.r32(GALL_VRAM + 48)))
    over = st.get('freeover') or e.r16(LEVEL_ID) != RUN or (os.environ.get('STOPNODE') and e.r32(GALL_VRAM + 48) < node < 2000
                                      and node >= int(os.environ['STOPNODE']))
    if t >= SEG or over:
        finish(t)
        if not over: e.save_state(STATE(SEGI)); json.dump(pst, open(PILOT, 'w'))
        elif os.environ.get('SAVE_END'): e.save_state(os.path.abspath(os.environ['SAVE_END']))   # (SAVE_END=<path>: a state
                                                      # where the run is over, e.g. the last scene's (31) first frame: work/chain_take.py STATE= NOWARP=1 goes on)
        st['stop'] = t + 10


e.run(script)
