"""The final battle's respawn: from a native-flight state (run/bf61_native.st),
barrel rolls (A + full stick x, ROLL_F frames) before and after the game's own death (health 0), and per frame the
camera (index, active entry, its eye's distance to the ship, Trak 0's distance / target / height, entries 4 and 5's
words, VIEW_MODE, the blend's from/to), the pad as it reaches the game (raw after gallrun_pad(), the decoded held word,
stick), the ship (health, state, roll +0x1C, the steering's smoothed roll rate 0x8018E8B8) and g_native / g_away_t.

    M64CPU=2 SHOTS=rsp python3 gallrun/respawn_probe.py <build>/sote-patch.z64 [STATE=run/bf61_native.st] [--shots]
    python3 gallrun/respawn_probe.py --idx-after <--timers log> [...]   (no run, was idx_after.py: the camera index from
        a respawn on: its changes, VIEW_MODE, the eye-to-ship distance at the respawn and 60 VIs on)

Knobs (env): ROLLS_BEFORE (2), ROLLS_AFTER (4), DEATHS (1), ROLL_F (60 frames), GAP (120 frames between rolls),
ROLL_BTN (A; or CL for C-left), X (80: stick x), VIEWS=n (the view key VIEW_BTN (L) pressed n times after each
phase's rolls, 60 frames apart), HOLD_A=1 (A held but in the rolls), FIRE=1 (B tapped), PAD_ALL=1 log every frame (else the rolls' frames, the respawn's and
every 10th), DUMP_ENT=k,.. (camera entries 4-6 and Trak 0 dumped at those frames), CODE_POKE=addr=word,.. (hex; a research knob on the payload's code, with M64CPU=0). Lines: F (a frame), ROLL (one roll: the ship's total turn about its nose, degrees), DIE, RESPAWN, SUM.
Shots (--shots): 30 frames before each death, and RESPAWN + SHOTS_R (40,120) (the camera's distance), SHOTS_D=k,.. VIs after
each death (the explosion). VM=4|5 writes
VIEW_MODE (the gunner's chosen view) at the start; the shot frames are always logged.

STATE=run/bf63_free.st works too.
  --timers    from each death to TAIL (60) VIs after the respawn a T line per VI: the Stft state +0x230, its state seconds
              +0x234 (+0x238: state 5's length, s), RESPAWN_T, the screen fade (0x800D0804 r g b a), the game frame
              time (double 0x8018E998), the ship's place +0x50 / +0x08 and its distance from the death place, its speed,
              the camera (index, active entry, the drawn eye: the blend's 0x80111788 +0x30 at index -1), eye-to-ship,
              eye-to-battle (IMG_BATTLE), the view's forward against the battle (cos) and the battle's screen place, the
              game's burst objects (class record 0x80112E80, +0x60 s16 live) near the death place (count, mean, max
              distance); TSUM at the respawn: VIs and state seconds of 5 and 6. DIE_HP=n: the death by the game's own
              hits (health set to n, the towers' fire finishes it: hp_guard() keeps 15 % of each loss) instead of 0.
  --crash head|glance  (the sd_crash.py passes, folded in) the ship put OFF (2500) off the Star Destroyer's side (IMG_SD:
              its middle, DZ (0) up) and flown into it, its rows written each VI till state 5: head = square to the
              side, glance = GLANCE (60) degrees off that toward the hull's nose (sd_touch(): over 45 degrees off the
              surface is a crash, else a slide and a scrape: health set to GLANCE_HP (15) so a scrape kills). A CR line
              per VI from the hit (the first VI of state 5; its place = the hit point) to 120 VIs after the respawn:
              state, the place +0x50 / +0x08 and their distance from the hit point, the burst objects' (count, mean,
              max distance from the hit, the furthest one's place), the eye-to-hit; CRSUM: the largest distances in
              state 5 and 6. With --timers the T lines too. Shots (with --shots): 3, 60, 179 VIs after the hit.
  --dot X,Y   at each shot frame (with --shots) a DOT line per object on screen (every class record's pool, +0x50
              place: tag, index, screen x y of 320x240, distance from the eye, its distance to X,Y on screen), sorted
              by that; DOT_N (12) lines a frame. DOT_AT=k,.. VIs after the respawn (default SHOTS_R) for the shots.
Where the towers' bolts leave the muzzle (LOS_SKIP / LOS_MUZZLE):
  --muzzle    TOWER lines at the start: each gun tower (PRBT pool, IMG_TOWERS) its place +0x50, shot down or not, the
              Star Destroyer's hull (IMG_SD_COLL, the drawn side's triangles) straight under / over it (the nearest
              triangle's height on the vertical through +0x50 and its normal z); then per VI a MUZ line per new tower
              bolt (Blst, owner a tower, speed^2 >= 1, first seen or moved back toward its tower): its distance from the
              tower's +0x50, the offset's height (z) and level part, its speed x the frame time (the way of one game
              frame), its heading against the tower-to-Falcon line (deg); MUZSUM: min / median / max. Use with
              DEATHS=0 DIE_AT=<VIs to run>.
The towers' line of sight:
  --los under|over  the Falcon held each VI (place +0x08 / +0x50 written, Invincibility on) by tower LOS_TOWER (default:
              the first standing): under = on the hull's far side from it (across the hull's middle line to LOS_SIDE (300)
              past the tower's own distance, LOS_DOWN (400) under the tower's +0x50), over = LOS_SIDE out from the hull
              on its own side, LOS_UP_AT (300) over it. Per VI each bolt of that tower (Blst, owner, moving, not parked)
              against the muzzle (+0x50 + (0, 0, 100)): a new one (first seen or back at the muzzle) counted, one further
              than LOS_MUZZLE (50) from it counted once (OUT); the build's g_los_tests / g_los_parked; the game frame
              time; seg_hit()'s cell walk replayed on the segment (the list entries it visits, the triangles among them). LOSSUM after LOS_SECS
              (10) s of game time: new / out bolts, per 10 s, parked, tests, entries per test (max), frame time mean /
              min / max (s) and its spread. Use with DEATHS=0 DIE_AT=<VIs, past LOS_SECS>.
The Falcon rammed into a tower:
  --ram       after the start's held line the Falcon put RAM_OFF (400) off standing tower RAM_TOWER (default: the first
              standing) on the side away from the hull's middle, RAM_DZ (50) over its +0x50, its nose RAM_ANG (0) degrees
              off the line to the tower's axis (level), A held, Invincibility off (RAM_INV=1: on), its rows written each VI till RAM_N
              (2) passes are done (a pass: through the axis and RAM_OFF out the other side, then put back). A RAMTW line
              (the tower's +0x60 / +0x68 / +0x6C, health, +0x140, +0x188), per VI near the tower a RAMV line (distance to
              the axis segment +0x50 .. +100 (with --shots: a shot SHOTS_RAM (20) VIs after each put, the tower ahead), the tool's f = |nose . normal|, the build's g_rams / g_ram_f / g_ram_hp, the
              tower's health, the Falcon's health), a RAM line at each g_rams step (expected tower health -2 x D x f x RAM_SCALE (env, 0.2 as gall_space.c; 1 before bf78),
              Falcon -f x 50, the frame's game time since the last ram on that tower; the Falcon's place and the PRBT pool's
              slot nearest it: a ram on the next towers along the way counts too), RAMP lines (the Falcon's place every 10
              VIs for 80 after a ram); RAMSUM. The tower's place is the one at the start (a blown-up tower moves). RAMTW's touch: the Stft's
              own cost of touching a PRBT (float 0x800EC9F8: 50000 stock, 0 in the native flight).
  --check     a CHECK line PASS / FAIL (exit 1 on a FAIL): with --timers (STATE=run/<build>_free.st) each death 2.8..3.2 s
              to the respawn, its bursts born over >= 1.3 s, no black fade after the respawn; with --ram (RAM_N=5) each
              ram on RAM_TOWER takes 2 x D x f x RAM_SCALE (within 0.05) and the Falcon f x 50, the tower blown up."""
import math, os, sys, subprocess, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
if '--idx-after' in sys.argv:                                    # (offline: --timers logs, was gallrun/idx_after.py)
    import re
    for path in sys.argv[sys.argv.index('--idx-after') + 1:]:
        L = open(path).read().splitlines()
        F = [(int(m.group(1)), m) for l in L for m in [re.match(r'F (\d+) .*?idx (-?\d+) act (-?\d+).*?eye_d ([\d.]+).*?vm (-?\d+)', l)] if m]
        die = next((int(re.match(r'DIE k (\d+)', l).group(1)) for l in L if l.startswith('DIE k')), None)
        rsp = next((int(re.match(r'RESPAWN k (\d+)', l).group(1)) for l in L if l.startswith('RESPAWN k')), None)
        if rsp is None: print(path, 'no respawn'); continue
        before = [m for k, m in F if die is not None and k < die]
        at_death = before[-1].group(2) if before else '?'
        seq = [(k, int(m.group(2)), float(m.group(4)), m.group(5)) for k, m in F if k >= rsp - 1]
        ch = [(seq[i][0], seq[i - 1][1], seq[i][1]) for i in range(1, len(seq)) if seq[i][1] != seq[i - 1][1]]
        after = [c for c in ch if c[0] >= rsp]
        e0 = next((s_[2] for s_ in seq if s_[0] >= rsp), None); e60 = next((s_[2] for s_ in seq if s_[0] >= rsp + 60), None)
        print(f'IDX {path}: index at the death {at_death}, at the respawn VI-1 {seq[0][1]}, changes from the respawn on {len(after)}: {after};'
              f' VIEW_MODE {seq[-1][3]}; eye_d respawn {e0} +60 {e60}; last index {seq[-1][1]} (VI {seq[-1][0]})')
    sys.exit(0)
ROM = os.path.abspath(sys.argv[1]); SHOTS_ON = '--shots' in sys.argv
def opt(name):                                                   # --name value
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else None
TIMERS, CRASH = '--timers' in sys.argv, opt('--crash')
DOT = [float(v) for v in opt('--dot').split(',')] if opt('--dot') else None
MUZZLE = '--muzzle' in sys.argv
LOS = opt('--los'); RAM = '--ram' in sys.argv; CHECK = '--check' in sys.argv
CHECKS = []
def check(name, ok, why):                                        # --check: a CHECK line per guarded behaviour
    CHECKS.append(ok); print(f'CHECK ({name})', 'PASS' if ok else 'FAIL', why, flush=True)
os.environ.setdefault('SHOTS', 'rsp_' + os.path.basename(os.path.dirname(ROM)))
import paths
import m64
from m64 import Emu, BTN, HERE

ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
STATE = os.environ.get('STATE', os.path.join(paths.RUN, 'bf61_native.st'))
NB, NA, ND = int(os.environ.get('ROLLS_BEFORE', 2)), int(os.environ.get('ROLLS_AFTER', 4)), int(os.environ.get('DEATHS', 1))
ROLL_F, GAP, X = int(os.environ.get('ROLL_F', 60)), int(os.environ.get('GAP', 120)), int(os.environ.get('X', 80))
RBTN = BTN[os.environ.get('ROLL_BTN', 'A')]
VIEWS, VBTN = int(os.environ.get('VIEWS', 0)), BTN[os.environ.get('VIEW_BTN', 'L')]
HOLD_A, FIRE = os.environ.get('HOLD_A'), os.environ.get('FIRE')
SHOTS_R = [int(x) for x in os.environ.get('SHOTS_R', '40,120').split(',')]
SHOTS_D = [int(x) for x in os.environ.get('SHOTS_D', '').split(',') if x]   # shots these VIs after a death
VM = os.environ.get('VM')
ENTRIES, ACTIVE, INDEX, VIEW_MODE, BLEND = 0x800D08A0, 0x800D08A4, 0x800D08A8, 0x8018E462, 0x80111764
PAD_INDEX, PAD_RAW, HELD, STICK = 0x80113060, 0x80113080, 0x801130AC, 0x80113098
ROLLRATE, HOLD, TRAK = 0x8018E8B8, 0x800DD2D0, 0x80112EF8
DOT_AT = [int(x) for x in os.environ['DOT_AT'].split(',')] if os.environ.get('DOT_AT') else None
if DOT and DOT_AT: SHOTS_R = DOT_AT
DIE_HP = int(os.environ.get('DIE_HP', 0))
TAIL = int(os.environ.get('TAIL', 60))                          # (--timers: VIs logged after the respawn)
GALL_VRAM, IMG_SD, IMG_BATTLE = 0x80628000, 212, 228
BURST, BLEND_VIEW, FADE, FRAME_DT, RESPAWN_T, PERSP = 0x80112E68, 0x80111788, 0x800D0804, 0x8018E998, 0x800E1B6C, 0x80192F14
e = Emu(ROM, video=m64.GLN)


def s32(v): return v - (1 << 32) if v >> 31 else v
def s16(v): return v - (1 << 16) if v >> 15 else v
def rec(tag):
    a = 0x80112808
    for _ in range(200):
        if e.r32(a) == tag: return a
        a += 0x30
    return 0
def v3(a): return [e.rf(a + 4 * j) for j in range(3)]
def dist(a, b): return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))
def dot(a, b): return sum(a[i] * b[i] for i in range(3))
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

def rd(a): return struct.unpack('>d', struct.pack('>II', e.r32(a), e.r32(a + 4)))[0]
def view():                                                      # the drawn view: the active entry's, or the blend's
    if s32(e.r32(INDEX)) == -1: b = BLEND_VIEW
    else:
        c = e.r32(ACTIVE)
        if not 0x80000000 <= c < 0x80800000: return None
        b = c + 0x14
    return v3(b), v3(b + 0x10), v3(b + 0x20), v3(b + 0x30)
def screen(p, vw=None):                                          # (hang_hit.py's)
    vw = vw or view()
    if not vw: return None
    R, F, U, E = vw
    v = [p[i] - E[i] for i in range(3)]; z = dot(F, v)
    if z < 1: return None
    th = math.tan(math.radians(e.rf(PERSP)) / 2); asp = e.rf(PERSP + 4) or 4 / 3
    return (round(160 + 160 * dot(R, v) / z / (th * asp), 1), round(120 - 120 * dot(U, v) / z / th, 1))
def bursts(at):                                                  # the game's bursts (class Expl, 0x80063C70's pool):
    n, sz, pool = e.r32(BURST + 8), e.r32(BURST + 0xC), e.r32(BURST + 0x10)   # the ones born since the last VI (live
    if not (0x80000000 <= pool < 0x80800000) or not sz: return 0, 0.0, 0.0, None   # +0x60, new or moved), their distance
    seen = st.setdefault('expl', {}); born = []                      # from at: count, mean, max, the furthest's place
    for i in range(min(n, 64)):
        b = pool + i * sz; q = v3(b + 0x50); live = e.r16(b + 0x60) != 0
        if live and (i not in seen or dist(seen[i], q) > 30): born.append((dist(q, at), q))
        if live: seen[i] = q
        else: seen.pop(i, None)
    if not born: return 0, 0.0, 0.0, None
    far = max(born)
    return len(born), sum(d for d, _ in born) / len(born), far[0], far[1]
def battle(): return v3(GALL_VRAM + IMG_BATTLE)
def timer_log(k, o, at, tag='T'):
    vw = view(); eye = vw[3] if vw else [0, 0, 0]; F = vw[1] if vw else [0, 1, 0]
    pos, pos8, bt = v3(o + 0x50), v3(o + 0x08), battle()
    tb = [bt[i] - eye[i] for i in range(3)]; lb = math.sqrt(dot(tb, tb)) or 1
    nb, mb, xb, _ = bursts(at) if not CRASH else (0, 0.0, 0.0, None)   # (--crash: its CR line has them)
    if nb and st['dead_k'] is not None: st.setdefault('bk', []).append(k)
    fd = [s16(e.r16(FADE + 2 * i)) for i in range(4)]
    if st['respawn_k'] is not None and k > st['respawn_k'] and fd[:3] == [0, 0, 0] and fd[3] > 0: st['black'] = st.get('black', 0) + 1
    act = e.r32(ACTIVE); ent = e.r32(ENTRIES)
    print(f'{tag} {k} st {e.r32(o + 0x230)} t234 {e.rf(o + 0x234):.3f} t238 {s32(e.r32(o + 0x238))} rt {e.rf(RESPAWN_T):.3f}'
          f' fade {",".join(str(s16(e.r16(FADE + 2 * i))) for i in range(4))} dt {rd(FRAME_DT):.4f} hp {s32(e.r32(o + 0x240))}'
          f' pos {pos[0]:.0f},{pos[1]:.0f},{pos[2]:.0f} pos8-pos {dist(pos, pos8):.1f} from_death {dist(pos, at):.1f} spd {e.rf(o + 0x9C):.1f}'
          f' idx {s32(e.r32(INDEX))} act {(act - ent) // 0x80 if act else -1} eye {eye[0]:.0f},{eye[1]:.0f},{eye[2]:.0f}'
          f' eye_ship {dist(eye, pos):.1f} eye_batt {lb:.0f} look_batt {dot(F, tb) / lb:.3f} batt_scr {screen(bt, vw)}'
          f' burst {nb} {mb:.0f} {xb:.0f} nat {e.r32(SYM["g_native"])}', flush=True)


st = dict(phase='before', rolls=[], deaths=0, respawn_k=None, roll=None, last_up=None, last_hp=None, dead_k=None, plan=[])
# the plan: (k, what) for the part before the first death; after each respawn a new one is made
def plan_from(k0, n_rolls, die):
    p = [(k0 + i * (ROLL_F + GAP), 'roll') for i in range(n_rolls)]
    end = k0 + n_rolls * (ROLL_F + GAP)
    for i in range(VIEWS):                                       # (the view key, VIEW_BTN, 4 frames, 60 apart)
        p.append((end + 60 * i, 'view'))
    end += 60 * VIEWS
    p.append((end, 'die' if die else 'end'))
    return p
st['plan'] = plan_from(int(os.environ.get('DIE_AT', 30)), NB, ND > 0)   # (DIE_AT: the first phase's start, VIs)


def frame_log(k, o, why):
    c = e.r32(PAD_INDEX); raw = e.r32(PAD_RAW + c * 6 & ~3)
    act = e.r32(ACTIVE); eye = v3(act + 0x44) if 0x80000000 <= act < 0x80800000 else [0, 0, 0]
    pos = v3(o + 0x50); fwd = v3(o + 0x30); up = v3(o + 0x40)
    d = eye[:]; d = [eye[i] - pos[i] for i in range(3)]
    behind = -dot(d, fwd); over = dot(d, up)
    t = e.r32(TRAK + 0x10); ent = e.r32(ENTRIES)
    w4 = [round(e.rf(ent + 4 * 0x80 + 0x54 + 4 * i), 1) for i in range(3)]
    w5 = [round(e.rf(ent + 5 * 0x80 + 0x54 + 4 * i), 1) for i in range(3)]
    src = e.r32(act + 8) if act else 0
    print(f'F {k} {why} hp {s32(e.r32(o + 0x240))} st {e.r32(o + 0x230)} idx {s32(e.r32(INDEX))} act {(act - ent) // 0x80 if act else -1}'
          f' src {"trak" if src == t + 0x20 else "stft" if src == o + 0x20 else hex(src)}'
          f' eye_d {dist(eye, pos):.1f} behind {behind:.1f} over {over:.1f} trak_d {e.rf(t + 0x60):.1f} trak_tgt {"stft" if e.r32(t + 0x8C) == o else hex(e.r32(t + 0x8C))}'
          f' trak_off {e.rf(t + 0x98):.1f} trak_eye_d {dist(v3(t + 0x50), pos):.1f} e4 {w4} e5 {w5} vm {e.r16(VIEW_MODE)} blend {e.r16(BLEND)}/{e.r16(BLEND + 2)}'
          f' spd {e.rf(o + 0x9C):.1f} roll {e.rf(o + 0x1C):.1f} rrate {e.rf(ROLLRATE):.1f} upz {up[2]:.3f}'
          f' pad {c} raw {raw:08x} held {e.r32(HELD):08x} stk {s16(e.r16(STICK))},{s16(e.r16(STICK + 2))}'
          f' nat {e.r32(SYM["g_native"])} away {e.rf(SYM["g_away_t"]):.2f} vo {e.r32(SYM["g_view_on"]) if "g_view_on" in SYM else "-"} hold {e.r16(HOLD)}'
          f' paused {e.r32(0x800DD2BC)} gs {e.r32(0x800DD2B0)}', flush=True)


def death_watch(k, o, stv, hp):                                  # --timers: states 5 and 6 from the death on
    if stv == 5 and 'k5' not in st:
        st['k5'] = k; st['at'] = v3(o + 0x50); st['t5'] = 0.0; print(f'STATE5 k {k}', flush=True)
    if stv == 5: st['t5'] = max(st.get('t5', 0), e.rf(o + 0x234))
    if stv == 6 and 'at' not in st: st['at'] = v3(o + 0x50)            # (the space level: no state 5)
    if stv == 6 and 'k6' not in st: st['k6'] = k; print(f'STATE6 k {k} ({k - st.get("k5", k)} VIs of 5)', flush=True)
    if stv == 6: st['t6'] = max(st.get('t6', 0), e.rf(o + 0x234))
    at = st.get('at') or st.get('last_at')
    if TIMERS and at and (st['respawn_k'] is None or k - st['respawn_k'] <= TAIL): timer_log(k, o, at)
def tsum(k):
    k5, k6 = st.get('k5'), st.get('k6')
    print(f'TSUM die {st["dead_k"]} state5 {k5} state6 {k6} respawn {k}: VIs death->5 {k5 - st["dead_k"] if k5 is not None else "-"}'
          f' of 5 {k6 - k5 if k5 is not None and k6 is not None else "-"} of 6 {k - k6 if k6 is not None else "-"}'
          f' 5->respawn {k - k5 if k5 is not None else "-"}; state seconds 5 {st.get("t5", 0):.3f} 6 {st.get("t6", 0):.3f}', flush=True)
    bk = st.pop('bk', [])
    st.setdefault('deaths_t', []).append(((k - st['dead_k']) / 60, (bk[-1] - bk[0]) / 60 if bk else 0.0))
    for x in ('k5', 'k6', 't5', 't6'): st.pop(x, None)
    st['last_at'] = st.pop('at', None)


def dot_log(k):                                                  # --dot: every pool's objects on screen against DOT
    vw = view()
    if not vw: return
    rows = []
    for j in range(200):
        r = 0x80112808 + 0x30 * j; tag = e.r32(r)
        if tag == 0 or not (0x20202020 <= tag <= 0x7A7A7A7A): continue
        n, sz, pool = e.r32(r + 8), e.r32(r + 0xC), e.r32(r + 0x10)
        if not (0x80000000 <= pool < 0x80800000) or not (0 < sz < 0x4000) or n > 512: continue
        name = bytes.fromhex(f'{tag:08x}').decode('latin1')
        for i in range(n):
            b = pool + i * sz; q = v3(b + 0x50)
            if not all(abs(c) < 1e6 for c in q): continue
            sp = screen(q, vw)
            if not sp or not (-20 <= sp[0] <= 340 and -20 <= sp[1] <= 260): continue
            rows.append((math.hypot(sp[0] - DOT[0], sp[1] - DOT[1]), name, i, sp, dist(q, vw[3]), q))
    rows.sort()
    print(f'DOTS k {k} on screen {len(rows)} eye {[round(c) for c in vw[3]]}', flush=True)
    for d, name, i, sp, de, q in rows[:int(os.environ.get('DOT_N', 12))]:
        print(f'DOT k {k} {name} {i} scr {sp[0]},{sp[1]} off {d:.1f} eye_d {de:.0f} at {q[0]:.0f},{q[1]:.0f},{q[2]:.0f}', flush=True)


def face(s, f):                                                  # (sd_crash.py's) the ship's rows for a forward f
    l = math.sqrt(dot(f, f)); f = [c / l for c in f]; h = math.hypot(f[0], f[1])
    u = [-f[0] * f[2] / h, -f[1] * f[2] / h, h]
    r = cross(f, u)
    for i in range(3):
        e.wf(s + 0x20 + 4 * i, r[i]); e.wf(s + 0x30 + 4 * i, f[i]); e.wf(s + 0x40 + 4 * i, u[i])
def crash(k, o):                                                 # --crash head|glance
    stv, hp = e.r32(o + 0x230), s32(e.r32(o + 0x240)); pos = v3(o + 0x50)
    sd = [e.rf(GALL_VRAM + IMG_SD + 4 * i) for i in range(4)]
    a = sd[3] if abs(sd[3]) < 7 else math.radians(sd[3])
    side, axis = [-math.sin(a), math.cos(a), 0], [math.cos(a), math.sin(a), 0]
    if k in (0, 1):                                              # (the hull OFF off its side, its middle's height)
        off, dz = float(os.environ.get('OFF', 2500)), float(os.environ.get('DZ', 0))
        q = [sd[0] + side[0] * off, sd[1] + side[1] * off, sd[2] + dz]
        for i in range(3): e.wf(o + 0x08 + 4 * i, q[i]); e.wf(o + 0x50 + 4 * i, q[i])
        if CRASH == 'glance': e.w32(o + 0x240, int(os.environ.get('GLANCE_HP', 15))); e.w32(SYM['g_hp_kept'], int(os.environ.get('GLANCE_HP', 15)))
        if k == 0: print('CRASH', CRASH, 'sd', [round(v, 2) for v in sd], 'put at', [round(v) for v in q], 'native', e.r32(SYM['g_native']), flush=True)
        e.pad(0 if e.r16(HOLD) else BTN['A'], 0, 0); return
    if 'hit' not in st:
        g = math.radians(float(os.environ.get('GLANCE', 60))) if CRASH == 'glance' else 0.0
        face(o, [-side[i] * math.cos(g) + axis[i] * math.sin(g) for i in range(3)])
        if k % 30 == 0: print(f'APPROACH k {k} pos {[round(v) for v in pos]} hp {hp} st {stv} hold {e.r16(HOLD)} spd {e.rf(o + 0x9C):.0f}', flush=True)
        if stv == 5 or hp <= 0:
            st['hit'] = k; st['at'] = pos; st['dead_k'] = k; st['max'] = {5: 0, 6: 0}
            print(f'HIT k {k} at {[round(v, 1) for v in pos]} st {stv} hp {hp}', flush=True)
        elif k > int(os.environ.get('MAXN', 1800)): print('CRSUM no hit'); e.stop(); return
        else: e.pad(0 if e.r16(HOLD) else BTN['A'], 0, 0); return
    dk = k - st['hit']; at = st['at']
    if stv == 6 and 'six' not in st: st['six'] = k; print(f'STATE6 k {k} ({dk} VIs of 5)', flush=True)
    if st.get('six') and stv not in (5, 6) and 'resp' not in st:
        st['resp'] = k; print(f'RESPAWN k {k} ({dk} after the hit) at {[round(v) for v in pos]} from the hit {dist(pos, at):.0f}', flush=True)
    nb, mb, xb, fq = bursts(at)
    vw = view(); eye = vw[3] if vw else [0, 0, 0]
    if stv in (5, 6): st['max'][stv] = max(st['max'][stv], dist(pos, at), xb)
    print(f'CR {dk} st {stv} hp {hp} pos {pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f} d_hit {dist(pos, at):.1f} pos8_hit {dist(v3(o + 8), at):.1f}'
          f' spd {e.rf(o + 0x9C):.1f} burst {nb} mean {mb:.1f} max {xb:.1f}' + (f' far {fq[0]:.0f},{fq[1]:.0f},{fq[2]:.0f}' if fq else '') +
          f' eye_hit {dist(eye, at):.1f} idx {s32(e.r32(INDEX))}', flush=True)
    if TIMERS: timer_log(k, o, at)
    if SHOTS_ON and (dk in (3, 60, 179) or ('resp' in st and k - st['resp'] in SHOTS_R)): e.shot(); print(f'SHOT {dk} #{e.shots}', flush=True)
    e.pad(0 if e.r16(HOLD) else BTN['A'], 0, 0)
    if ('resp' in st and k - st['resp'] > 120) or dk > 1500:
        print(f'CRSUM {CRASH} hit {[round(v) for v in at]} max from the hit: state5 {st["max"][5]:.1f} state6 {st["max"][6]:.1f}'
              f' 5 VIs {st.get("six", k) - st["hit"]} respawn {st.get("resp", "-")}', flush=True); e.stop()


IMG_TOWERS, IMG_SD_COLL, COLL_TRI = 304, 268, 24
def hull_at(x, y, z0):                                           # --muzzle: the hull's triangles on the vertical (x, y)
    c = e.r32(GALL_VRAM + IMG_SD_COLL)
    if not c: return []
    x0, y0, cell = e.rf(c + 8), e.rf(c + 12), e.rf(c + 16); nx, ny = e.r32(c + 20), e.r32(c + 24)
    tris, cells, lst = e.r32(c + 4), e.r32(c + 28), e.r32(c + 32)
    i, j = int((x - x0) / cell), int((y - y0) / cell)
    if not (0 <= i < nx and 0 <= j < ny): return []
    a, b = e.r32(cells + 4 * (j * nx + i)), e.r32(cells + 4 * (j * nx + i) + 4); out = []
    for k in range(a, b):
        t = tris + COLL_TRI * e.r16(lst + 2 * k)
        v = [[s16(e.r16(t + 6 * q + 2 * m)) for m in range(3)] for q in range(3)]
        nz = s16(e.r16(t + 18 + 4)) / 32767
        d = [[v[1][m] - v[0][m] for m in range(2)], [v[2][m] - v[0][m] for m in range(2)]]   # barycentric in xy
        den = d[0][0] * d[1][1] - d[0][1] * d[1][0]
        if abs(den) < 1e-6: continue
        px, py = x - v[0][0], y - v[0][1]
        u = (px * d[1][1] - py * d[1][0]) / den; w = (d[0][0] * py - d[0][1] * px) / den
        if u < 0 or w < 0 or u + w > 1: continue
        out.append((v[0][2] + u * (v[1][2] - v[0][2]) + w * (v[2][2] - v[0][2]) - z0, nz))
    return sorted(out, key=lambda q: abs(q[0]))
def muzzle(k, o):
    n, pool = e.r32(GALL_VRAM + IMG_TOWERS), e.r32(GALL_VRAM + IMG_TOWERS + 12)
    if not n or e.r32(0x80112C28 + 0x10) != pool: return
    tw = {pool + i * 0x214: i for i in range(n)}
    if k == 0:
        for t, i in tw.items():
            p = v3(t + 0x50); h = hull_at(p[0], p[1], p[2])
            print(f'TOWER {i} at {p[0]:.0f},{p[1]:.0f},{p[2]:.0f} down {e.r32(t + 0x140) >> 4 & 1} hull dz (nearest first, nz) '
                  + ' '.join(f'{dz:.1f}/{nz:.2f}' for dz, nz in h[:4]), flush=True)
    r = blst()
    if not r: return
    nb, sz, bp = e.r32(r + 8), e.r32(r + 0xC), e.r32(r + 0x10); last = st.setdefault('muz', {}); fal = v3(o + 0x50)
    for i in range(min(nb, 64)):
        b = bp + i * sz; ow = e.r32(b + 0x64)
        if ow not in tw: continue
        q, v = v3(b + 0x50), v3(b + 0x78); tp = v3(ow + 0x50); d = dist(q, tp); v2 = dot(v, v)
        was = last.get(i); last[i] = (ow, d, q[2] > -20000)
        if v2 < 1 or q[2] <= -20000: continue
        if was and was[0] == ow and was[2] and d >= was[1] - 20: continue
        off = [q[m] - tp[m] for m in range(3)]; tf = [fal[m] - tp[m] for m in range(3)]
        ang = math.degrees(math.acos(max(-1, min(1, dot(v, tf) / math.sqrt(v2 * dot(tf, tf)))))) if dot(tf, tf) else 0
        step = math.sqrt(v2) * rd(FRAME_DT)
        st.setdefault('muz_d', []).append((d, off[2], step))
        print(f'MUZ k {k} tower {tw[ow]} bolt {i} d {d:.1f} dz {off[2]:.1f} level {math.hypot(off[0], off[1]):.1f} step {step:.1f}'
              f' spd {math.sqrt(v2):.0f} to_falcon_deg {ang:.1f} falcon_d {math.sqrt(dot(tf, tf)):.0f}', flush=True)
def muzsum():
    m = sorted(st.get('muz_d', []))
    if not m: print('MUZSUM none', flush=True); return
    md = m[len(m) // 2]
    print(f'MUZSUM bolts {len(m)} d min {m[0][0]:.1f} median {md[0]:.1f} max {m[-1][0]:.1f}; dz min {min(x[1] for x in m):.1f}'
          f' max {max(x[1] for x in m):.1f}; step median {sorted(x[2] for x in m)[len(m) // 2]:.1f}', flush=True)
def seg_walk(a, b):                                              # --los: seg_hit()'s cells for a -> b: list entries, triangles
    c = e.r32(GALL_VRAM + IMG_SD_COLL)
    if not c: return 0, 0
    x0, y0, cell = e.rf(c + 8), e.rf(c + 12), e.rf(c + 16); nx, ny = e.r32(c + 20), e.r32(c + 24); cells = e.r32(c + 28)
    d = [b[i] - a[i] for i in range(3)]; n = 0; lst = e.r32(c + 32); seen = set()
    j0, j1 = max(int((min(a[1], b[1]) - y0) / cell), 0), min(int((max(a[1], b[1]) - y0) / cell), ny - 1)
    for j in range(j0, j1 + 1):
        u0, u1 = 0.0, 1.0
        if d[1]:
            r0, r1 = sorted(((y0 + cell * j - a[1]) / d[1], (y0 + cell * (j + 1) - a[1]) / d[1])); u0, u1 = max(r0, 0), min(r1, 1)
        xa, xb = sorted((a[0] + d[0] * u0, a[0] + d[0] * u1))
        for i in range(max(int((xa - x0) / cell), 0), min(int((xb - x0) / cell), nx - 1) + 1):
            c0, c1 = e.r32(cells + 4 * (j * nx + i)), e.r32(cells + 4 * (j * nx + i) + 4)
            n += c1 - c0; seen.update(e.r16(lst + 2 * x) for x in range(c0, c1))
    return n, len(seen)
def los(k, o):
    n, pool = e.r32(GALL_VRAM + IMG_TOWERS), e.r32(GALL_VRAM + IMG_TOWERS + 12)
    if not n or e.r32(0x80112C28 + 0x10) != pool: e.pad(0, 0, 0); return
    L = st.setdefault('los', dict(k0=k, new=0, out=set(), dt=[], walk=[], seen={}, spawn={}))
    if 'tw' not in L:
        up = [i for i in range(n) if not e.r32(pool + i * 0x214 + 0x140) & 0x10]
        L['i'] = int(os.environ.get('LOS_TOWER', up[0] if up else 0)); L['tw'] = pool + L['i'] * 0x214
        sd = [e.rf(GALL_VRAM + IMG_SD + 4 * i) for i in range(4)]
        a = sd[3] if abs(sd[3]) < 7 else math.radians(sd[3])
        side = [-math.sin(a), math.cos(a), 0]; tp = v3(L['tw'] + 0x50)
        s_t = dot([tp[m] - sd[m] for m in range(3)], side); sg = 1 if s_t >= 0 else -1
        ls, ld, lu = float(os.environ.get('LOS_SIDE', 300)), float(os.environ.get('LOS_DOWN', 400)), float(os.environ.get('LOS_UP_AT', 300))
        if LOS == 'under': q = [tp[m] - side[m] * sg * (2 * abs(s_t) + ls) for m in range(2)] + [tp[2] - ld]
        else: q = [tp[m] + side[m] * sg * ls for m in range(2)] + [tp[2] + lu]
        L['at'] = q; L['g0'] = [e.r32(SYM[x]) if x in SYM else 0 for x in ('g_los_tests', 'g_los_parked')]
        print(f'LOS {LOS} tower {L["i"]} at {tp[0]:.0f},{tp[1]:.0f},{tp[2]:.0f} side {s_t:.0f} falcon held at {q[0]:.0f},{q[1]:.0f},{q[2]:.0f}'
              f' hull between (replay entries) {seg_walk([tp[0], tp[1], tp[2] + 100], q)}', flush=True)
    q = L['at']; e.w32(0x800E1B2C, 1)
    for m in range(3): e.wf(o + 0x08 + 4 * m, q[m]); e.wf(o + 0x50 + 4 * m, q[m])
    tw = L['tw']; tp = v3(tw + 0x50); mz = [tp[0], tp[1], tp[2] + 100]
    ov = e.r32(SYM['g_ov_frames'])
    if ov != L.get('ov'): L['ov'] = ov; L['dt'].append(rd(FRAME_DT))   # (once a game frame)
    r = blst()
    if r:
        nb, sz, bp = e.r32(r + 8), e.r32(r + 0xC), e.r32(r + 0x10)
        for i in range(min(nb, 64)):
            b = bp + i * sz
            if e.r32(b + 0x64) != tw: continue
            p, v = v3(b + 0x50), v3(b + 0x78); d = dist(p, mz)
            if dot(v, v) < 1 or p[2] <= -20000: L['seen'].pop(i, None); continue
            was = L['seen'].get(i)
            if was is None or d < was - 20:
                L['new'] += 1; L['spawn'][i] = L['spawn'].get(i, 0) + 1
                print(f'LOSNEW k {k} bolt {i} d {d:.1f}', flush=True)
            L['seen'][i] = d
            if d > 50 and (i, L['spawn'].get(i, 0)) not in L['out']:
                L['out'].add((i, L['spawn'].get(i, 0))); print(f'LOSOUT k {k} bolt {i} d {d:.1f}', flush=True)
    if k % 30 == 0: L['walk'].append(seg_walk(mz, q))
    secs = sum(L['dt'])
    if secs >= float(os.environ.get('LOS_SECS', 10)):
        g = [e.r32(SYM[x]) - L['g0'][j] if x in SYM else -1 for j, x in enumerate(('g_los_tests', 'g_los_parked'))]
        dt = L['dt']; mean = secs / len(dt); sp = math.sqrt(sum((x - mean) ** 2 for x in dt) / len(dt))
        print(f'LOSSUM {LOS} tower {L["i"]} secs {secs:.2f} VIs {k - L["k0"]} new {L["new"]} out {len(L["out"])}'
              f' per10s new {L["new"] * 10 / secs:.1f} out {len(L["out"]) * 10 / secs:.1f} tests {g[0]} parked {g[1]}'
              f' walk entries / triangles max {max(L["walk"]) if L["walk"] else (0, 0)} frames {len(dt)} dt mean {mean:.4f} min {min(dt):.4f}'
              f' max {max(dt):.4f} sd {sp:.4f} Hz {1 / mean:.1f}', flush=True)
        e.stop()
    e.pad(0, 0, 0)


def near_tower(p, n, pool):                                     # (--ram: the PRBT pool's slot nearest p: index, place,
    best = None                                                  # health, +0x140, +0x188)
    for i in range(8):
        t = pool + i * 0x214; q = v3(t + 0x50); dd = math.dist(p, q)
        if best is None or dd < best[0]: best = (round(dd), i, [round(v) for v in q], round(e.rf(t + 0x1A4), 2), hex(e.r32(t + 0x140)), e.r32(t + 0x188))
    return best


def ram(k, o):                                                   # --ram
    n, pool = e.r32(GALL_VRAM + IMG_TOWERS), e.r32(GALL_VRAM + IMG_TOWERS + 12)
    if not n or e.r32(0x80112C28 + 0x10) != pool: e.pad(0, 0, 0); return
    R = st.setdefault('ram', dict(pass_=0, phase='put', last=None, rams=[], lastk={}))
    if 'tw' not in R:
        up = [i for i in range(n) if not e.r32(pool + i * 0x214 + 0x140) & 0x10]
        R['i'] = int(os.environ.get('RAM_TOWER', up[0] if up else 0)); R['tw'] = pool + R['i'] * 0x214
        tw = R['tw']; R['g0'] = e.r32(SYM['g_rams'])
        print(f'RAMTW tower {R["i"]} at {[round(v) for v in v3(tw + 0x50)]} r60 {e.rf(tw + 0x60):.1f} z68 {e.rf(tw + 0x68):.1f} z6c {e.rf(tw + 0x6C):.1f}'
              f' hp {e.rf(tw + 0x1A4):.2f} f140 {e.r32(tw + 0x140):#x} st188 {e.r32(tw + 0x188)} difficulty {e.r16(0x8011282A)}'
              f' touch {e.rf(0x800EC9F8):.1f}', flush=True)
    tw = R['tw']; tp = R.setdefault('tp', v3(tw + 0x50)); e.w32(0x800E1B2C, int(os.environ.get('RAM_INV', 0)))
    sd = [e.rf(GALL_VRAM + IMG_SD + 4 * i) for i in range(4)]
    away = [tp[0] - sd[0], tp[1] - sd[1]]; la = math.hypot(*away); away = [away[0] / la, away[1] / la, 0]
    off, dz, ang = float(os.environ.get('RAM_OFF', 400)), float(os.environ.get('RAM_DZ', 50)), math.radians(float(os.environ.get('RAM_ANG', 0)))
    if R['phase'] == 'put':
        c, s_ = math.cos(ang), math.sin(ang)                      # (the start turned by ang about the axis: the nose
        d0 = [away[0] * c - away[1] * s_, away[0] * s_ + away[1] * c, 0]   # aimed back through the axis' point)
        q = [tp[0] + d0[0] * off, tp[1] + d0[1] * off, tp[2] + dz]
        for m in range(3): e.wf(o + 0x08 + 4 * m, q[m]); e.wf(o + 0x50 + 4 * m, q[m])
        R['fwd'] = [-d0[0], -d0[1], 0]; face(o, R['fwd']); R['phase'] = 'fly'; R['start'] = q; R['putk'] = k
        print(f'RAMPUT pass {R["pass_"]} k {k} at {[round(v) for v in q]} nose {[round(v, 3) for v in R["fwd"]]} hp {s32(e.r32(o + 0x240))}', flush=True)
        e.pad(0 if e.r16(HOLD) else BTN['A'], 0, 0); return
    face(o, R['fwd'])
    if SHOTS_ON and k - R['putk'] in [int(x) for x in os.environ.get('SHOTS_RAM', '20').split(',')]:   # (the tower ahead)
        e.shot(); print(f'SHOT ram pass {R["pass_"]} k {k} #{e.shots}', flush=True)
    p = v3(o + 0x50); zc = min(max(p[2], tp[2]), tp[2] + 100); nr = [p[0] - tp[0], p[1] - tp[1], p[2] - zc]; d = math.sqrt(dot(nr, nr))
    f = abs(dot([c / d for c in nr], v3(o + 0x30))) if d > 1e-3 else 0
    g = e.r32(SYM['g_rams']) - R['g0']; thp = e.rf(tw + 0x1A4); hp = s32(e.r32(o + 0x240))
    if d < 150: print(f'RAMV k {k} pass {R["pass_"]} d {d:.1f} f {f:.3f} rams {g} g_f {e.rf(SYM["g_ram_f"]):.3f} g_hp {e.rf(SYM["g_ram_hp"]):.2f}'
                      f' tower_hp {thp:.2f} f140 {e.r32(tw + 0x140):#x} st188 {e.r32(tw + 0x188)} falcon_hp {hp} st {e.r32(o + 0x230)} dt {rd(FRAME_DT):.4f}'
                      + (f' since {e.rf(SYM["g_ram_since"] + 4 * R["i"]):.3f}' if 'g_ram_since' in SYM else ''), flush=True)
    if R['last'] is not None and g != R['last'][0]:
        D = 10 + 20 * (min(max(e.r16(0x8011282A), 1), 3) - 1); gf = e.rf(SYM['g_ram_f'])
        r = dict(k=k, f=gf, tw_before=R['last'][1], tw_after=thp, fal_before=R['last'][2], fal_after=hp, d=d)
        R['rams'].append(r); r['err'] = abs(thp - (R['last'][1] - 2 * D * gf * float(os.environ.get('RAM_SCALE', 0.2))))
        r['ferr'] = abs(hp - max(R['last'][2] - int(gf * 50 + 0.5), 0)); r['tw'] = near_tower(p, n, pool)[1]   # (the Falcon's health stops at 0)
        print(f'RAM k {k} pass {R["pass_"]} f {gf:.3f} (tool f last VI {R["last"][3]:.3f}) tower {R["last"][1]:.2f} -> {thp:.2f} (expected {R["last"][1] - 2 * D * gf * float(os.environ.get('RAM_SCALE', 0.2)):.2f})'
              f' falcon {R["last"][2]} -> {hp} (expected {R["last"][2] - int(gf * 50 + 0.5)}) f140 {e.r32(tw + 0x140):#x} st188 {e.r32(tw + 0x188)} at d {d:.1f}'
              f' | falcon at {[round(v) for v in p]}; nearest pool tower {near_tower(p, n, pool)}', flush=True)
    R['last'] = (g, thp, hp, f)
    past = dot([p[m] - tp[m] for m in range(2)] + [0], R['fwd'])
    if R['rams'] and k % 10 == 0 and k - R['rams'][-1]['k'] < 80: print(f'RAMP k {k} falcon at {[round(v) for v in p]} hp {hp} st {e.r32(o + 0x230)}', flush=True)
    if past > off or k > 3000:
        print(f'RAMEND pass {R["pass_"]} k {k} past {past:.0f} at {[round(v) for v in p]} d {d:.0f}', flush=True)
        R['pass_'] += 1; R['phase'] = 'put'
        if R['pass_'] >= int(os.environ.get('RAM_N', 2)) or k > 3000:
            print(f'RAMSUM tower {R["i"]} passes {R["pass_"]} rams {len(R["rams"])} ' + ' | '.join(
                f'f {r["f"]:.3f} tower {r["tw_before"]:.2f}->{r["tw_after"]:.2f} falcon {r["fal_before"]}->{r["fal_after"]}' for r in R['rams'])
                + f' tower now hp {thp:.2f} f140 {e.r32(tw + 0x140):#x} st188 {e.r32(tw + 0x188)}', flush=True)
            e.stop(); return
    e.pad(0 if e.r16(HOLD) else BTN['A'], 0, 0)              # (A up on a held line: its let-go needs a press)


def blst():
    a = 0x80112808
    for _ in range(200):
        if e.r32(a) == 0x426C7374: return a
        a += 0x30
    return 0


def script(e, n):
    if n == 1: e.unlimit(); e.load_state(STATE)
    if n < 3: return
    k = n - 3
    if k == 0 and os.environ.get('CODE_POKE'):                    # (research knob: words written into the code, M64CPU=0)
        for kv in os.environ['CODE_POKE'].split(','):
            a_, v_ = (int(x, 16) for x in kv.split('=')); print('POKE', hex(a_), hex(e.r32(a_)), '->', hex(v_), flush=True); e.w32(a_, v_)
    if k == 0 and VM: e.w32(VIEW_MODE & ~3, (e.r32(VIEW_MODE & ~3) & 0xFFFF0000) | (int(VM) & 0xFFFF)); print('VIEW_MODE', e.r16(VIEW_MODE), flush=True)
    if k == 0:
        b = 0x800E6808 + 0x60 * s16(e.r16(0x800D252C))
        print('BIND preset', s16(e.r16(0x800D252C)), 'roll-key +0x58', hex(e.r16(b + 0x58)), '+0x5E', hex(e.r16(b + 0x5E)), 'flags +4', e.r16(b + 4), '+2', e.r16(b + 2), 'yawL/R', hex(e.r16(b + 0xC)), hex(e.r16(b + 0xE)), 'alt 0x800DD770', e.r32(0x800DD770), flush=True)
    sr = rec(0x53746674); o = e.r32(sr + 0x10)
    if e.r16(HOLD) and k % 30 > 26: e.pad(BTN['A'], 0, 0); return      # (a held line: let go)
    if CRASH:                                                    # (from the first VI with no held line: the start's
        if 'c0' not in st and (e.r16(HOLD) or k < 30): e.pad(0, 0, 0); return   # line let go first: A up)
        st.setdefault('c0', k); crash(k - st['c0'], o); return
    if LOS: los(k, o); return
    if RAM:
        if 'r0' not in st and (e.r16(HOLD) or k < 30): e.pad(0, 0, 0); return
        st.setdefault('r0', k); ram(k - st['r0'], o); return
    if str(k) in os.environ.get('DUMP_ENT', '').split(','):        # (entries 4, 5, 6 word by word, and Trak 0's first 0xA0)
        ent = e.r32(ENTRIES); t = e.r32(TRAK + 0x10)
        for i in (4, 5, 6): print(f'ENT{i} k {k}', ' '.join(f'{e.r32(ent + i * 0x80 + 4 * j):08x}' for j in range(32)), flush=True)
        print(f'TRAK0 k {k}', ' '.join(f'{e.r32(t + 4 * j):08x}' for j in range(40)), flush=True)
    hp = s32(e.r32(o + 0x240)); stv = e.r32(o + 0x230)
    up = v3(o + 0x40); fwd = v3(o + 0x30)
    # roll accumulator: the up row's turn about the nose since the last frame, signed
    if st['roll'] is not None and st['last_up'] is not None:
        a = st['last_up']; s_ = dot(cross(a, up), fwd); c_ = dot(a, up)
        st['roll']['deg'] += math.degrees(math.atan2(s_, c_))
    st['last_up'] = up
    btn = 0; x = 0; why = ''
    plan = st['plan']
    act = [w for (kk, w) in plan if kk <= k < kk + (ROLL_F if w == 'roll' else 4 if w == 'view' else 1)]
    if 'roll' in act:
        kk = max(kk for (kk, w) in plan if w == 'roll' and kk <= k)
        if k == kk: st['roll'] = dict(k=k, phase=st['phase'], deg=0.0, rate_max=0.0)
        btn |= RBTN; x = X; why = 'ROLL'
        st['roll']['rate_max'] = max(st['roll']['rate_max'], abs(e.rf(ROLLRATE)))
    elif st['roll'] is not None and k >= st['roll']['k'] + ROLL_F + 20:      # (20 frames after: the rate eases out)
        r = st['roll']; st['rolls'].append(r)
        print(f"ROLL {r['phase']} k {r['k']} turned {r['deg']:.1f} deg  rate_max {r['rate_max']:.1f}", flush=True)
        st['roll'] = None
    if 'view' in act: btn |= VBTN if any(w == 'view' and kk <= k < kk + 4 for (kk, w) in plan) else 0; why = why or 'VIEW'
    if HOLD_A and 'roll' not in act: btn |= BTN['A']
    if FIRE and k % 8 < 4: btn |= BTN['B']
    if 'die' in act and st['dead_k'] is None:
        e.w32(o + 0x240, DIE_HP); st['dead_k'] = k
        if e.r32(SYM['g_native']) == 1: e.w32(SYM['g_hp_kept'], DIE_HP)          # (not on a stock state)
        st['deaths'] += 1; why = 'DIE'
        print(f'DIE k {k} (death {st["deaths"]}) hp {DIE_HP}', flush=True)
    if death_watch(k, o, stv, hp) == 'stop': return
    if MUZZLE: muzzle(k, o)
    if 'end' in act:
        if MUZZLE: muzsum()
        print('SUM rolls', [(r['phase'], round(r['deg'])) for r in st['rolls']], flush=True); e.stop(); return
    if st['dead_k'] is not None and st['last_hp'] is not None and hp > st['last_hp'] + 200:
        print(f'RESPAWN k {k} ({k - st["dead_k"]} after the death)', flush=True)
        tsum(k)
        st['respawn_k'] = k; st['dead_k'] = None; st['phase'] = f'after{st["deaths"]}'; why = 'RESPAWN'
        st['plan'] = plan_from(k + int(os.environ.get('END_AFTER', 120)), NA, st['deaths'] < ND)   # (END_AFTER: VIs to the next phase)
    st['last_hp'] = hp
    shot_now = False
    if SHOTS_ON:
        if any(w == 'die' and k == kk - 30 for (kk, w) in plan) or (st['respawn_k'] is not None and k - st['respawn_k'] in SHOTS_R) \
                or (st['dead_k'] is not None and k - st['dead_k'] in SHOTS_D):
            e.shot(); shot_now = True; print(f'SHOT k {k} #{e.shots}', flush=True)
            if DOT: dot_log(k)
    if k > 6000: print('SUM timeout'); e.stop(); return
    e.pad(btn, x, 0)
    r = st['respawn_k']
    if os.environ.get('PAD_ALL') or shot_now or why or k % 10 == 0 or st['dead_k'] is not None or (r is not None and 0 <= k - r < 60):
        frame_log(k, o, why or ('dead' if st['dead_k'] is not None else ''))


e.run(script)
if CHECK and TIMERS:
    dt_ = st.get('deaths_t', [])
    # (the bursts: >= 1.3 s; bf88 drew 1.40, bf90's states 1.37: the frame's length moves it by a few hundredths)
    check('death', bool(dt_) and all(2.8 <= a <= 3.2 and b >= 1.3 for a, b in dt_) and not st.get('black'),
          f"per death (death -> respawn s, the bursts drawn s): {[(round(a, 2), round(b, 2)) for a, b in dt_]} (2.8..3.2, >= 1.3); "
          f"black fade frames after the respawn {st.get('black', 0)} (0)")
if CHECK and RAM:                                                # the rams on RAM_TOWER (the ones on the next towers along
    R = st.get('ram') or {}                                      # the way are not read against it)
    rams = [r for r in R.get('rams', []) if r['tw'] == R.get('i') and r['tw_before'] > 0]
    down = any(r['tw_after'] <= 0 for r in rams)
    check('ram', bool(rams) and all(r['err'] < 0.05 and r['ferr'] <= 1 for r in rams) and (down or int(os.environ.get('RAM_N', 2)) < 5),
          f"rams on tower {R.get('i')}: {len(rams)}, its health {[round(r['tw_after'], 2) for r in rams]} (each 2 x D x f x RAM_SCALE "
          f"off, within 0.05; the Falcon f x 50), blown up {bool(down)} (by RAM_N >= 5 passes)")
if CHECKS: sys.exit(0 if all(CHECKS) else 1)
