"""Creature Cam row (cheats.c): what the profile name " Wampa  Stompa" gives, picked from the row,
without the name and without its buttons (they exist only in the Traditional preset; every case
here writes the Standard preset, 0, to s16 0x800D252C each frame and holds no combo).

    M64CPU=0 python3 t_wampa.py <rom> cave|trooper|hoth|hoth_off

On foot the values are Dash / Wampa / Trooper: the row clears the creature object u32 0x800E5EF4
and sends 'Wmp?' / 'Bls?' to class Trop as the on-foot code does on the name's buttons; the Trop
handler puts the answering object there and the camera follows it. Where the level has both ATST
and Spdr (Battle of Hoth) the values are Speeder / AT-ST: the AT-ST mode u32 0x800DECE0 and the
D-pad of the current preset given as in Traditional (binding slots +0x08..+0x16 of 0x800E6808 +
preset * 0x60). Elsewhere the row reads "(none)" and does nothing.

cave (states/echo_cave.st, Dash's health held at 100: the cave's wampa would kill him): the row
starts at Dash (object 0). Cheats, up three rows (wraps past Reset cheats and Friendly Wampas onto Creature Cam), R:
Wampa; within 10 VIs of resume the object is a Trop with +0x74 & 0xF == 2, still it 120 VIs later
with nothing held, and the camera's eye (*0x800D08A4 + 0x44) nearer to it than to Dash (shot then).
The D-pad drives it: within 2 VIs of the take (the object set) preset 0's slots +0x08..+0x16 are
Traditional's; 140 VIs after resume D-left held 120 VIs turns the wampa (+0x14, degrees) by >= 90
(~214) while Dash moves < 0.5, then D-up held 120 VIs: its state +0x78 is 2 (walking). Cheats, L:
Dash, the object 0 within 2 VIs, the 8 slots the ones before 2 VIs after that, still 0 100 VIs
after resume. Before that menu trip the stick and B drive it (cheats_pad, the raw pad turned into that D-pad
before the game decodes it): stick y +60 held 120 VIs: state 2 on >= 100 frames; stick x +60 held 120 VIs: +0x14
turns >= 90 degrees; B held 60 VIs: state 3 on >= 1 frame and the decoded held word 0x801130AC has no B bit
(0x4000) on any of them; Dash moves < 0.5 over the three.

trooper (states/echo_cave.st, its pool has non-wampa Trops that answer 'Bls?'): L from Dash:
Trooper, a Trop with kind != 2, still it 120 VIs after resume; D-left held 120 VIs turns it (+0x14)
by >= 30 degrees ("trooper turns": ~244, its code checks it is the followed object at 0x800B4F84
and turns on +0x0C / +0x0E); stick y +60 held 120 VIs: state 2 on >= 100 frames; B held 60 VIs: state 3 on
>= 1 frame. Then A steps forward: Dash (0),
A: Wampa (kind 2); Reset cheats puts Dash back (0).

hoth (states/lvl0.st, Battle of Hoth): the wave's alive count 0x800E1818 zeroed (wave 1, 2 ATST,
starts); at VI 30, before the wave, Cheats, up three rows, A: AT-ST; preset 0's slots +0x08/+0x0A/
+0x0C/+0x0E are 0x0800/0x0400/0x0200/0x0100 (Traditional's D-pad) and +0x10..+0x16 0, the mode 1.
Nothing on the D-pad then: while ATST 0 sleeps (+0x1C4 0) Trak 0's target (*0x80112F20 + 0x8C) is
the speeder every frame; within 2 VIs of ATST 0 waking it is ATST 0 with +0x98 55.0 (the game's behind view),
and so every frame for 300 VIs; shot 60 VIs after the wake (in wave 1's opening shot) and 120 VIs
after the speeder flies again (the behind view on it). D-left held 240 VIs turns ATST 0 (heading from
+0x19C/+0x1A0) by >= 90 degrees (stock, name + Traditional: ~180) and leaves the speeder's view
u32 0x800E1834 alone (the stick centred: it stands meanwhile); D-up held 120 VIs keeps Trak 0 on ATST 0.
Then the stick and B (cheats.c atst_pad; position +8, the pivot: +0x158 is a point that circles it as it turns):
centre 120 VIs: it moves < 0.5; y +72 (STICK_FULL) 120 VIs: >= 25 (~27; 240 VIs ~54); y +48 240 VIs: 30..70 % of the
full push over 240 VIs (~57 %); y +72 120 VIs then centre: it walks on to the stance and stops (the walk bit set)
within 110 VIs, the walk clock's time (*(+0x108 + 0x14) + 4) mod 20 within 5.0 +- 0.5 there (~4.9..5.2), then moves
< 0.5 over 60 VIs (shot of the stop: both feet down); x +60, y centre 240 VIs: heading turns >= 330 (~372: the
game's 2 a frame plus cheats.c's TURN_EXTRA x the push; the game's alone ~206) and it moves < 0.5; the eye behind it (cheats.c atst_eye, Dash's
swing rule round the head point, ATST 0 +0x50..+0x58 with 55 up; the camera's eye +0x44): on the
ground the angle between (head point - eye) and the facing <= 45 all through that turn and <= 10 30 VIs after the
stick lets go, <= 10 over the 120 VIs of y +72 before the stance; the eye sqrt(120^2 + 45^2) = 128.2 +- 3 from the
head point (CAM_BACK behind, CAM_RISE up) over those and the stand and B phases (B's start too, where the think
zeroes Trak 0's aim offsets +0x90 / +0x94: cheats.c places the rig after Trak's update, atst_trak); the view pitch
(the active camera's forward row +0x24, its z at +0x2C) 15 +- 2 degrees down in every one of those phases; the feet
(ATST 0 +0x58) and the head point projected through the active camera (forward / up rows, the fovy at 0x80192F14,
240 lines) standing, walking and with B held: the feet at screen y <= 232, the head point 133..149 (shots standing
and firing); atst_trak's placement counter g_atst_trak moves every game frame (never 3 VIs without); the aim (ATST
translation + +0x90..+0x98) against the eye + forward x the leash +0x60 only logged; B 120 VIs,
stick centre: the fire timer +0x100 rises >= 2 times (the D-up branch shoots at 0x8005635c and sets it to 0.25 / 0.5;
+0x1CC counts only state 4's own fire), the decoded held word has no B and the target +0x16C is 0 on every frame (no
auto-aim); 120 VIs of the stick x -/+60 steering it to 101 degrees right of its heading at the turn's start (toward wave 1's probe droids and other AT-ST, behind it there), then Z + B 120 VIs: +0x16C non-zero on >= 1 frame and its tag only PRBT / ATST / ATAT (Z locks an enemy, never
the speeder or a rbgn; the head's cos to it +0x174 printed at the pick and 30 VIs later, shot there); the walk bit (+0x108 bit 31) set when the
menu opens. From 2 VIs after the wake while the row is on AT-ST (>= 900 VIs): the speeder (+8) within 1.0 of
where it was (0.000), its health +0x204 not below it (110), the lives 0x800E0EB0 kept. The speeder does not fly
on its own while held, so the stick phases start 800 VIs after the wake (stock: it flew again ~798 VIs after it, at
the opening shot's end). Cheats, A: Speeder; it flies >= 20 in 120 VIs (~148); the walk bit clear within 2 VIs of resume; the 8 slots
are the saved ones again, the 5 tags at 0x800DED08 the game's again, the mode 0, Trak 0's target the speeder (the one it was before), still
60 VIs after resume (shot). 120 VIs after resume, on again by writing g_atst_on and the mode: Trak 0 back on ATST 0, then
ATST 0's +6 |= 0x20 (destroyed): Trak 0 on the speeder within 2 VIs. Then states/sky.st (Skyhook,
neither class nor Dash): A on the row changes nothing (not recorded for Reset cheats, the mode and
the object untouched; shot of the menu, the row reads "(none)").

hoth_off: the same run and menu trip with the row left on Speeder; only the shot 60 VIs after the
wake, to compare with hoth's (the opening shot is not Trak 0's, so the two look the same).
"""
import os, sys, struct, math
import _path
import paths
from m64 import Emu, BTN, HERE
from inject import inject, syms
from testlib import check, report

S = syms()
e = Emu(sys.argv[1])
CASE = sys.argv[2] if len(sys.argv) > 2 else 'cave'
PAUSED, PRESET, OBJ, ATST = 0x800DD2BC, 0x800D252C, 0x800E5EF4, 0x800DECE0
BINDS = 0x800E6808
CAM = 0x800D08A4                    # u32 camera, eye at +0x44
SPDR_VIEW = 0x800E1834
TRAK0 = 0x80112F20
ATST_REC, SPDR_REC = 0x80112DD8, 0x80112C88   # class records, first object at +0x10
WAVE_ALIVE = 0x800E1818
HP = 0xB4                           # Humn health (float)
ROW = 38
TROP = 0x54726F70
TRAD = [0x0800, 0x0400, 0x0200, 0x0100, 0, 0, 0, 0]


def w16(a, v):
    w = e.r32(a & ~3)
    w = (w & 0xFFFF) | (v << 16) if (a & 2) == 0 else (w & 0xFFFF0000) | v
    e.w32(a & ~3, w)


def r8(a): return (e.r32(a & ~3) >> (8 * (3 - (a & 3)))) & 0xFF
def keys(): return [e.r16(BINDS + 8 + 2 * i) for i in range(8)]     # preset 0
def kind(o): return e.r32(o + 0x74) & 0xF if o >= 0x80000000 else None
def trak_tgt(): return e.r32(e.r32(TRAK0) + 0x8C)
def pos(o): return [e.rf(o + 8 + 4 * i) for i in range(3)]
def eye(): return [e.rf(e.r32(CAM) + 0x44 + 4 * i) for i in range(3)]
def dist(a, b): return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


seq, marks, st = [], {}, dict(mark={})
t = 0


def press(name, gap=10):
    global t
    seq.append((t, name)); t += gap


def mark(name): marks[t] = name


def up(n):
    for _ in range(n): press('U_D', 8)


def down(n):
    for _ in range(n): press('D_D', 8)


def open_cheats(): press('START', 40); down(2); down(1); press('A', 30)
def resume(): press('B', 30); up(3); press('A', 40)


def snap():
    o = e.r32(OBJ)
    return dict(paused=e.r32(PAUSED), row=e.r32(S['g_cheats_row']), atst_on=e.r32(S['g_atst_on']), obj=o,
                tag=e.r32(o) if o >= 0x80000000 else 0, kind=kind(o), mode=e.r32(ATST), keys=keys(),
                saved=r8(S['g_saved'] + ROW))


def buttons(k):
    b = 0
    for f, name in seq:
        if f <= k < f + 4: b |= BTN[name]
    return b


def marks_at(k):
    if k in marks:
        s = snap(); st['mark'][marks[k]] = s
        print(f'{k:5d} {marks[k]:10s} {s}', flush=True)


def unpaused(k, key):               # first frame unpaused after the menu's resume
    if st.get(key) is None and k > st.get(key + '_after', 1 << 30) and e.r32(PAUSED) == 0:
        st[key] = k
        print(k, key, flush=True)


DRIVE, WALK = (140, 260), (270, 390)                # VIs after the first resume: the D-pad,
S_WALK, S_TURN, S_B, MENU2 = (400, 520), (530, 650), (660, 720), 730   # then the stick and B (cheats_pad)
HELD = 0x801130AC                   # the game's decoded held-buttons word (the bindings' bits)
STICK = 60


def onfoot(k):
    global t
    b = 0
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + HP, 100.0)
    o = e.r32(OBJ)
    if k == 0:
        st['start'] = snap()
        t = 140
        open_cheats(); up(3); mark('at_row')
        st['pick'] = t
        if CASE == 'cave': press('R', 20); mark('picked')
        else: press('L', 20); mark('picked')
        st['u1_after'] = t
        resume()
    if st.get('pick') is not None and k >= st['pick'] and st.get('take') is None and o:
        st['take'] = k; print(k, 'taken: object %08x' % o, flush=True)
    if st.get('take') is not None and st.get('k_trad') is None and keys() == TRAD:
        st['k_trad'] = k - st['take']; print(k, 'D-pad slots Traditional,', st['k_trad'], 'VIs after the take', flush=True)
    unpaused(k, 'u1')
    u1 = st.get('u1')
    if u1 is not None:
        j = k - u1
        if j == 10: st['at10'] = snap()
        if 10 <= j <= 130 and o != st['at10']['obj']: st['lost'] = st.get('lost') or (j, o)
        if j == 130:
            st['held'] = snap()
            if CASE == 'cave':
                ey, dp = eye(), pos(pl)
                st['eye'] = (dist(ey, pos(o)) if o >= 0x80000000 else -1, dist(ey, dp))
                print('eye', ['%.1f' % x for x in ey], 'creature', ['%.1f' % x for x in pos(o)] if o else '-',
                      'dash', ['%.1f' % x for x in dp], 'dists %.1f %.1f' % st['eye'], flush=True)
                e.shot()
        if DRIVE[0] <= j < DRIVE[1]:    # D-left: the followed creature turns, Dash stays put
            b |= BTN['L_D']
            y = e.rf(o + 0x14) if o >= 0x80000000 else 0.0
            if j == DRIVE[0]: st['yaw'] = [y, 0.0]; st['dash0'] = pos(pl)
            st['yaw'] = [y, st['yaw'][1] + (y - st['yaw'][0] + 180) % 360 - 180]
            st['drift'] = dist(pos(pl), st['dash0'])
            if j % 30 == 0: print(k, 'D-left yaw %.1f turned %.1f dash drift %.2f' % (y, st['yaw'][1], st['drift']), flush=True)
        if CASE == 'cave' and WALK[0] <= j < WALK[1]:     # D-up: the wampa walks (state 2)
            b |= BTN['U_D']
            if j == WALK[0]: st['walk'] = 0; st['dash1'] = pos(pl)
            st['walk'] += e.r32(o + 0x78) == 2
            st['drift_up'] = dist(pos(pl), st['dash1'])
        x = y = 0
        if S_WALK[0] <= j < S_WALK[1]:  # stick up: the creature walks (state 2)
            y = STICK
            if j == S_WALK[0]: st['s_walk'] = 0; st['dash2'] = pos(pl)
            st['s_walk'] += e.r32(o + 0x78) == 2
        if CASE == 'cave' and S_TURN[0] <= j < S_TURN[1]:   # stick right: it turns
            x = STICK
            yw = e.rf(o + 0x14)
            if j == S_TURN[0]: st['s_yaw'] = [yw, 0.0]
            st['s_yaw'] = [yw, st['s_yaw'][1] + (yw - st['s_yaw'][0] + 180) % 360 - 180]
        if S_B[0] <= j < S_B[1]:        # B: it attacks (state 3), the game sees no B
            b |= BTN['B']
            if j == S_B[0]: st['s_att'] = 0; st['s_bbit'] = 0; st['held_w'] = set()
            st['s_att'] += e.r32(o + 0x78) == 3
            hw = e.r32(HELD); st['held_w'].add(hw)
            st['s_bbit'] += (hw & 0x4000 or (hw >> 16) & 0x4000) != 0
        if S_WALK[0] <= j < S_B[1]: st['s_drift'] = dist(pos(pl), st['dash2'])
        if j in (S_WALK[0] + 60, S_TURN[0] + 60, S_B[0] + 30):
            print(k, 'stick %d %d state %d yaw %.1f held %08x dash drift %.2f' % (x, y, e.r32(o + 0x78), e.rf(o + 0x14),
                  e.r32(HELD), dist(pos(pl), st['dash2'])), flush=True)
        if j == MENU2:
            t = k + 1
            open_cheats()
            if CASE == 'cave':
                mark('opened2'); st['pressL'] = t; press('L', 20); mark('dash')
            else:
                press('A', 20); mark('a_dash'); press('A', 20); mark('a_wampa')
                down(2); press('A', 20); mark('reset')
            st['u2_after'] = t
            resume()
    if st.get('pressL') is not None and k >= st['pressL'] and st.get('l0') is None and o == 0:
        st['l0'] = k - st['pressL']; print(k, 'object 0,', st['l0'], 'VIs after the L press', flush=True)
    unpaused(k, 'u2')
    if st.get('u2') is not None and k == st['u2'] + 100:
        st['final'] = snap(); return True
    if st.get('l0') is not None and st.get('k_back') is None and keys() == st['start']['keys']:
        st['k_back'] = k - st['pressL'] - st['l0']; print(k, 'D-pad slots back,', st['k_back'], 'VIs after the object 0', flush=True)
    marks_at(k)
    if u1 is None: x = y = 0
    e.pad(b | buttons(k), x, y)
    return k > 4000


def heading(a): return math.degrees(math.atan2(e.rf(a + 0x1A0), e.rf(a + 0x19C)))


# The stick on ATST 0 (cheats.c atst_pad): VIs after the speeder flies again, each (start, end, stick x, y).
ANIM, FROZEN = 0x108, 0x80000000    # its animation player's word 0; bit 31 stands the walk (the root motion)
FULL, HALF = 72, 48                 # STICK_FULL; (48 - 24) / (72 - 24) = half the frames walk
A_STAND, A_FULL, A_HALF = (530, 650), (660, 900), (910, 1150)
A_STANCE, A_LET = (1160, 1280), (1280, 1450)   # y +72, then let go: it walks on to the stance and stops there
A_TURN, A_STILL, A_FIRE, A_AIM, A_FIREZ, AT_MENU = (1460, 1700), (1700, 1760), (1770, 1890), (1890, 2010), (2010, 2130), 2150
                                    # A_AIM: the stick (x -/+60, 0 within AIM_TOL) turns it to AIM_REL off its heading at
                                    # A_TURN's start, toward wave 1's probe droids and AT-ST (~150 off its facing there,
                                    # outside the pick's cone, cos 0.5), so Z has an enemy to take; steered to a heading,
                                    # not timed, so it does not hang on the stick's turn rate
AIM_REL, AIM_TOL = -101.0, 4.0      # the heading x +60 240 VIs then x -60 120 VIs gave at the game's own turn rate
TURN_MIN = 330                      # x +60 240 VIs: the game's 2 a frame + cheats.c TURN_EXTRA x 60 / 72 (~372; alone ~206)
STANCE_T, STOP_IN = 5.0, 110        # cheats.c STANCE_T: the walk clock's time mod 20 with both feet down
SP_HP, LIVES = 0x204, 0x800E0EB0    # the speeder's health (float); the lives (u32)
FIRE_T = 0x100                      # the think's fire timer: the D-up branch shoots (0x8005635c) when it is below 0 and
                                    # sets it to 0.25 or 0.5, so a rise is a shot (+0x1CC counts only state 4's own fire)
TARGET, HEAD_COS = 0x16C, 0x174     # ATST 0's target (the head aims at it, 0x80055F34) and the head's cos to it there
TARGETS = 0x800DED08                # the pick's tag list (5 tags + 0): cheats.c rewrites it while the AT-ST drives
ENEMY_TAGS = {b'PRBT', b'ATST', b'ATAT'}
def tag(o): return e.r32(o).to_bytes(4, 'big') if o >= 0x80000000 else None
def tgt_list(): return [e.r32(TARGETS + 4 * i) for i in range(5)]


def stance(j, a):
    """y +72, then let go: the first frozen VI (the stop), the clock there, the drift over the next 60 VIs."""
    m = st.setdefault('stance', {})
    if j == A_LET[0]: m['p0'] = pos(a)
    if j >= A_LET[0] and m.get('stop') is None and e.r32(a + ANIM) & FROZEN:
        t = e.rf(e.r32(a + ANIM + 0x14) + 4)
        m.update(stop=j - A_LET[0], t=t, tm=t % 20, ps=pos(a)); e.shot()
        print(j, 'stance: stopped %d VIs after the let-go, clock %.2f (mod 20 %.2f)' % (m['stop'], t, t % 20), flush=True)
    if m.get('stop') is not None and j == A_LET[0] + m['stop'] + 60: m['d60'] = dist(pos(a), m['ps'])


def stick_phase(j, a):
    """Drives and measures the stick phases; returns this frame's stick (x, y) and buttons (B in 'fire')."""
    if A_STANCE[0] <= j < A_LET[1]:
        stance(j, a)
        return (0, FULL if j < A_STANCE[1] else 0, 0)
    if j == A_TURN[0]: st['turn_h0'] = heading(a)
    for name, (s0, s1), xy in (('stand', A_STAND, (0, 0)), ('full', A_FULL, (0, FULL)), ('half', A_HALF, (0, HALF)),
                               ('turn', A_TURN, (60, 0)), ('fire', A_FIRE, (0, 0)), ('aim', A_AIM, (-60, 0)),
                               ('firez', A_FIREZ, (0, 0))):
        if not s0 <= j < s1: continue
        if j == s0: st[name + '_p0'] = pos(a); st[name] = dict(h=[heading(a), 0.0], fires=0, f0=e.rf(a + FIRE_T), bbit=0)
        m = st[name]
        m['d'] = dist(pos(a), st[name + '_p0'])
        if j - s0 == 119: m['d120'] = m['d']
        h = heading(a); m['h'] = [h, m['h'][1] + (h - m['h'][0] + 180) % 360 - 180]
        f = e.rf(a + FIRE_T); m['fires'] += f > m['f0']; m['f0'] = f
        hw = e.r32(HELD); m['bbit'] += (hw & 0x4000 or (hw >> 16) & 0x4000) != 0
        tg = e.r32(a + TARGET); m.setdefault('tags', set()); m['nz'] = m.get('nz', 0) + (tg != 0)
        if tg:
            m['tags'].add(tag(tg))
            if m.get('t_first') is None: m['t_first'] = j - s0; m['cos0'] = e.rf(a + HEAD_COS)
            if j - s0 == m['t_first'] + 30: m['cos30'] = e.rf(a + HEAD_COS); e.shot()
        if name == 'aim':
            dh = (st['turn_h0'] + AIM_REL - h + 180) % 360 - 180
            xy = (-60 if dh > AIM_TOL else 60 if dh < -AIM_TOL else 0, 0)
        if (j - s0) % 60 == 0:
            print(j, name, 'stick', xy, 'moved %.2f turned %.1f anim %08x shots %d state %d' % (m['d'], m['h'][1],
                  e.r32(a + ANIM), m['fires'], e.r32(a + 0x1C4)), flush=True)
        return xy + ((BTN['B'],) if name == 'fire' else (BTN['B'] | BTN['Z'],) if name == 'firez' else (0,))
    return 0, 0, 0


# The eye behind it (cheats.c atst_eye, Dash's swing rule round the head point: ATST 0 +0x50..+0x58, Trak 0 +0x98 up):
# on the ground the angle between (head point - eye) and its facing, the eye's 3D distance from the head point, the
# view's pitch (the active camera's forward row), the screen y (0 top .. 240 bottom) of the feet and the head point,
# Trak 0's aim (ATST translation + +0x90..+0x98) against the eye + the view's forward x the leash +0x60.
B_TURN_MAX, B_SETTLE, B_WALK_MAX = 45.0, 10.0, 10.0
B_DIST, B_PITCH = (math.hypot(120, 45) - 3, math.hypot(120, 45) + 3), (13.0, 17.0)
B_FEET_MAX, B_HEAD = 232, (133, 149)   # screen y of 240 (expected ~220 and ~141)
B_GAP = 3                           # a game frame takes 2 VIs (3 when the patch's cost slows the game)
HEAD_UP = 55.0                      # the head point over ATST 0's translation (the bind's cockpit distance)
FOVY = 0x80192F14                   # float, the perspective's vertical angle (degrees)
UP = 0x34                           # the active camera's up row
B_SETTLE_AT = A_STILL[0] + 30       # 30 VIs after the turn's stick lets go
SWING = 0x800E0EF4                  # Dash's rule: rate, max, slow (floats, read for the log)
FWD = 0x24                          # the active camera's forward row (x, y, z)


def behind(j, a):
    ph = 'turn' if A_TURN[0] <= j < A_TURN[1] else 'walk' if A_STANCE[0] <= j < A_STANCE[1] else \
         'settle' if j == B_SETTLE_AT else 'still' if A_TURN[1] <= j < B_SETTLE_AT else \
         'stand' if A_STAND[0] + 30 <= j < A_STAND[1] else 'fire' if A_FIRE[0] <= j < A_FIRE[1] else None
    if ph is None: return
    ex, ey, ez = eye(); tr = e.r32(TRAK0); c = e.r32(CAM)
    ax, ay, az = e.rf(a + 0x50), e.rf(a + 0x54), e.rf(a + 0x58)
    hx, hy, hz = ax, ay, az + HEAD_UP
    vx, vy = hx - ex, hy - ey
    fx, fy = e.rf(a + 0x19C), e.rf(a + 0x1A0)
    ang = math.degrees(math.acos(max(-1, min(1, (vx * fx + vy * fy) / (math.hypot(vx, vy) or 1) / (math.hypot(fx, fy) or 1)))))
    d = math.sqrt(vx * vx + vy * vy + (hz - ez) ** 2)
    f = [e.rf(c + FWD + 4 * i) for i in range(3)]
    pitch = -math.degrees(math.asin(max(-1, min(1, f[2] / (math.sqrt(sum(v * v for v in f)) or 1)))))
    fn = math.sqrt(sum(v * v for v in f)) or 1; lsh = e.rf(tr + 0x60)
    aim = [e.rf(a + 0x50 + 4 * i) + e.rf(tr + 0x90 + 4 * i) for i in range(3)]
    ah = dist(aim, [q + v / fn * lsh for q, v in zip((ex, ey, ez), f)])
    u = [e.rf(c + UP + 4 * i) for i in range(3)]; th = math.tan(math.radians(e.rf(FOVY) / 2))
    def sy(p):                       # screen line of a world point, 0 top .. 240 bottom
        dv = [p[i] - (ex, ey, ez)[i] for i in range(3)]
        dz_ = sum(dv[i] * f[i] for i in range(3)) / fn
        du = sum(dv[i] * u[i] for i in range(3)) / (math.sqrt(sum(v * v for v in u)) or 1)
        return 120 - 120 * du / (dz_ or 1e-6) / th
    yf, yh = sy((ax, ay, az)), sy((hx, hy, hz))
    m = st.setdefault('behind', {}).setdefault(ph, dict(ang=0.0, dmin=1e9, dmax=0.0, pmin=1e9, pmax=-1e9, ah=0.0, n=0,
                                                         yf=[1e9, -1e9], yh=[1e9, -1e9], fovy=e.rf(FOVY)))
    m['yf'] = [min(m['yf'][0], yf), max(m['yf'][1], yf)]; m['yh'] = [min(m['yh'][0], yh), max(m['yh'][1], yh)]
    m['ang'] = max(m['ang'], ang); m['dmin'] = min(m['dmin'], d); m['dmax'] = max(m['dmax'], d); m['n'] += 1
    m['pmin'] = min(m['pmin'], pitch); m['pmax'] = max(m['pmax'], pitch); m['ah'] = max(m['ah'], ah)
    n = e.r32(S['g_atst_trak']); gap = st['trak_gap'] = st.get('trak_gap', 0) + 1 if n == st.get('trak_n') else 0
    m['gap'] = max(m.get('gap', 0), gap); m['moves'] = m.get('moves', 0) + (gap == 0); st['trak_n'] = n
    if not B_DIST[0] <= d <= B_DIST[1] and m.setdefault('dbad', 0) < 5:      # the first few frames off the distance
        m['dbad'] += 1
        print(j, 'behind', ph, 'off the distance: dist %.1f eye %.1f %.1f %.1f head %.1f %.1f %.1f +0x90 %.2f +0x94 %.2f'
              % (d, ex, ey, ez, hx, hy, hz, e.rf(tr + 0x90), e.rf(tr + 0x94)), flush=True)
    if j == A_TURN[0]: print(j, 'swing rate %.3f max %.1f slow %.1f' % tuple(e.rf(SWING + 4 * i) for i in range(3)), flush=True)
    if j in (A_STAND[0] + 90, A_FIRE[0] + 60):
        e.shot(); print(j, 'shot', e.shots, 'standing' if ph == 'stand' else 'firing (B)', flush=True)
    if j % 30 == 0 or ph == 'settle':
        print(j, 'behind', ph, 'angle %.1f dist %.1f pitch %.1f aim off %.2f (+0x90 %.2f +0x94 %.2f +0x98 %.2f) '
              'screen y feet %.0f head %.0f fovy %.2f speed %.2f'
              % (ang, d, pitch, ah, e.rf(tr + 0x90), e.rf(tr + 0x94), e.rf(tr + 0x98), yf, yh, e.rf(FOVY),
                 e.rf(tr + 0x64)), flush=True)


PHASE = ['hoth']
FLY_AT = 800                        # stock: the speeder flies again ~798 VIs after the wake (the opening shot's end)
WAKE_SHOT = 60                      # D3 shot: this many VIs after ATST 0 wakes, during wave 1's opening shot


def hoth(k):
    global t
    if k == 2: e.w32(WAVE_ALIVE, 0)
    a0, sp = e.r32(ATST_REC + 0x10), e.r32(SPDR_REC + 0x10)
    state, tr = e.r32(a0 + 0x1C4), trak_tgt()
    cock = tr == a0                 # Trak 0 on ATST 0
    b, x, y = 0, 0, 0
    if k == 0:
        st['pre'] = dict(keys=keys(), trak=tr, sp=sp, a0=a0, mode=e.r32(ATST), tl=tgt_list())
        print('pre', {x: (v if x in ('keys', 'tl') else '%08x' % v) for x, v in st['pre'].items()}, flush=True)
        t = 30
        open_cheats(); up(3); mark('at_row')
        if CASE == 'hoth': press('A', 20)
        else: t += 20               # hoth_off: the same menu trip, the row left on Speeder
        mark('on')
        st['u1_after'] = t
        resume()
    unpaused(k, 'u1')
    if st.get('wake') is None:
        if state == 0:
            if st.get('u1') is not None and tr != sp: st['pre_bad'] = st.get('pre_bad') or (k, tr)
        else:
            st['wake'] = k; print(k, 'ATST 0 awake, state', state, 'trak %08x' % tr, flush=True)
    w = st.get('wake')
    if w is not None and CASE == 'hoth':
        if st.get('cam') is None and cock: st['cam'] = k - w
        if 0 <= k - w - (st.get('cam') or 0) < 300 and st.get('cam') is not None and not cock:
            st['cam_bad'] = st.get('cam_bad') or (k - w, '%08x' % tr, state)
    if w is not None and k == w + WAKE_SHOT:
        st['d3'] = dict(k=k, trak=tr, state=state); e.shot()
        print(k, 'D3 shot (opening shot), trak %08x a0 %08x sp %08x' % (tr, a0, sp), flush=True)
    if CASE == 'hoth_off' and w is not None and k == w + WAKE_SHOT + 10: return True   # the shot written first
    if w is not None and st.get('fly') is None and k > w + 300:
        p = (e.rf(sp + 8), e.rf(sp + 12))
        moved = st.get('prev') is not None and abs(p[0] - st['prev'][0]) + abs(p[1] - st['prev'][1]) > 0.3
        if moved or (CASE == 'hoth' and k == w + FLY_AT):   # held by the AT-ST drive, the speeder does not fly on its own
            st['fly'] = k; print(k, 'speeder flying again' if moved else 'the opening shot over', flush=True)
        st['prev'] = p
    if CASE == 'hoth' and w is not None and st.get('u2') is None:     # the speeder held while the AT-ST is driven (on)
        if k == w + 2: st['sp_ref'] = dict(p=pos(sp), hp=e.rf(sp + SP_HP), lives=e.r32(LIVES), k=k)
        r = st.get('sp_ref')
        if r and k > r['k'] and e.r32(S['g_atst_on']):
            h = st.setdefault('sp_hold', dict(d=0.0, hp=1e9, n=0, lives=r['lives']))
            dd = dist(pos(sp), r['p'])
            h['d'] = max(h['d'], dd); h['hp'] = min(h['hp'], e.rf(sp + SP_HP)); h['n'] += 1
            h['lives'] = e.r32(LIVES)
    if k % 200 == 0: print(k, 'wave', e.r32(0x800E183C), 'ATST0 state', state, 'trak %08x' % tr, flush=True)
    f = st.get('fly')
    if f is not None and st.get('u2_after') is None:
        j = k - f
        if j == 120:
            st['cockpit'] = dict(trak=tr, cock=cock); e.shot()
            print(k, 'cockpit shot, trak %08x' % tr, flush=True)
        if 140 <= j < 380:          # D-left: ATST 0 turns
            b |= BTN['L_D']
            h = heading(a0)
            if j == 140: st['h'] = [h, 0.0]; st['view0'] = e.r32(SPDR_VIEW); st['view_ch'] = 0
            d = (h - st['h'][0] + 180) % 360 - 180
            st['h'] = [h, st['h'][1] + d]
            st['view_ch'] += e.r32(SPDR_VIEW) != st['view0']
            if j % 40 == 0: print(k, 'D-left heading %.1f turned %.1f view %d mode %d' % (h, st['h'][1], e.r32(SPDR_VIEW), e.r32(ATST)), flush=True)
        if 400 <= j < 520:          # D-up: the game's target + fire; the camera stays on it
            b |= BTN['U_D']
            st['up_off'] = st.get('up_off', 0) + (tr != a0)
        if 140 <= j < 380: st['dl_drift'] = dist(pos(a0), st.setdefault('dl_p0', pos(a0)))
        x, y, sb = stick_phase(j, a0); b |= sb
        behind(j, a0)
        if j == AT_MENU:
            st['frozen_at_menu'] = bool(e.r32(a0 + ANIM) & FROZEN)
            t = k + 1
            open_cheats(); mark('opened2'); press('A', 20); mark('off')
            st['u2_after'] = t
            resume()
    unpaused(k, 'u2')
    u2 = st.get('u2')
    if CASE == 'hoth' and u2 is not None and st.get('unfrozen') is None and not e.r32(a0 + ANIM) & FROZEN:
        st['unfrozen'] = k - u2; print(k, 'ATST 0 walk bit clear,', st['unfrozen'], 'VIs after resume', flush=True)
    if CASE == 'hoth' and u2 is not None and k == u2: st['sp_u2'] = pos(sp)
    if CASE == 'hoth' and u2 is not None and k == u2 + 120: st['sp_fly'] = dist(pos(sp), st['sp_u2'])
    if u2 is not None and k == u2 + 60:
        st['after'] = dict(trak=tr, mode=e.r32(ATST), keys=keys(), tl=tgt_list()); e.shot()
        print(k, 'after off', st['after'], flush=True)
    if u2 is not None and k == u2 + 120:    # on again without the menu, for the destroyed check (after the fly check)
        e.w32(S['g_atst_on'], 1); e.w32(ATST, 1); st['re'] = k
    r = st.get('re')
    if r is not None and k > r:
        if st.get('re_cam') is None and tr == a0:
            st['re_cam'] = k - r
            e.w32(a0 + 4, e.r32(a0 + 4) | 0x20); st['kill'] = k     # +6 |= 0x20 (destroyed)
            print(k, 'trak on ATST 0 again; destroyed flag set', flush=True)
        kk = st.get('kill')
        if kk is not None and k > kk:
            if st.get('kill_sp') is None and tr == sp: st['kill_sp'] = k - kk
            if k == kk + 10:
                print(k, 'destroyed: trak %08x' % tr, flush=True); PHASE[0] = 'load'
        if k > r + 60 and kk is None: PHASE[0] = 'load'
    marks_at(k)
    e.pad(b | buttons(k), x, y)
    return k > 8000


def sky(k):
    global t
    if k == 0:
        st['sky0'] = snap()
        t = 20
        open_cheats(); up(3); mark('sky_row'); press('A', 20); mark('sky_a')
        st['sky_shot'] = t + 5
    if k == st.get('sky_shot'): e.shot()
    marks_at(k)
    e.pad(buttons(k))
    return k > st['sky_shot'] + 10


BASE = [66]


def script(e, n):
    global seq, marks, t
    if n == 1: e.unlimit()
    if n == 60: e.load_state(os.path.join(paths.STATES, 'lvl0.st' if CASE.startswith('hoth') else 'echo_cave.st'))
    if n == 62: inject(e)
    if n < BASE[0]: return
    if PHASE[0] == 'load':          # hoth done: Skyhook for "(none)"
        e.pad(0)
        if 'sky_n' not in st:
            st['sky_n'] = n; e.load_state(os.path.join(paths.STATES, 'sky.st'))
        elif n == st['sky_n'] + 2:
            inject(e)
        elif n == st['sky_n'] + 6:
            PHASE[0] = 'sky'; BASE[0] = n + 1; seq, marks, t = [], {}, 0
        return
    k = n - BASE[0]
    w16(PRESET, 0)
    fn = sky if PHASE[0] == 'sky' else hoth if CASE.startswith('hoth') else onfoot
    if fn(k): e.stop()


e.run(script)
m = st['mark']
if CASE == 'hoth_off':
    d3 = st['d3']
    check('Speeder: the D3 shot taken in the opening shot, Trak 0 on the speeder', d3['trak'] == st['pre']['sp']
          and not st.get('pre_bad'), f"VI {d3['k']} (wake {st['wake']}) trak {d3['trak']:08x} state {d3['state']}")
elif CASE == 'hoth':
    pre, on, off, af, d3 = st['pre'], m['on'], m['off'], st['after'], st['d3']
    check('up three times from the top is the Creature Cam row', m['at_row']['row'] == ROW, f"row {m['at_row']['row']}")
    check('before: the AT-ST mode off, preset 0 has no D-pad in +0x08..+0x0E', pre['mode'] == 0
          and pre['keys'][:4] == [0, 0, 0, 0], f"{pre}")
    check('AT-ST: Traditional D-pad in preset 0, +0x10..+0x16 0, the mode 1', on['keys'] == TRAD and on['mode'] == 1
          and on['atst_on'] == 1, f"{on}")
    check('before the wave (ATST 0 state 0): Trak 0 on the speeder every frame', pre['trak'] == pre['sp']
          and not st.get('pre_bad'), f"first bad {st.get('pre_bad')}")
    check('ATST 0 awake: Trak 0 on it within 2 VIs, nothing held', st.get('cam') is not None
          and st['cam'] <= 2, f"after {st.get('cam')} VIs (wake at {st['wake']})")
    check('and on it every frame for the next 300 VIs', not st.get('cam_bad'), f"first bad {st.get('cam_bad')}")
    print('D3 shot at VI', d3['k'], 'wake', st['wake'], flush=True)
    check('behind-view shot 120 VIs after the speeder flies again: Trak 0 on ATST 0', st['cockpit']['cock'],
          f"{st['cockpit']}")
    check('D-left 240 VIs turns ATST 0 by >= 90 degrees', abs(st['h'][1]) >= 90, f"{st['h'][1]:.1f}")
    check("D-left leaves the speeder's view alone", st['view_ch'] == 0, f"{st['view_ch']} frames changed, view {st['view0']}")
    check("D-up keeps Trak 0 on ATST 0", st.get('up_off', 1) == 0, f"{st.get('up_off')} of 120 frames off it")
    print('D-left (stick centred): ATST 0 moved %.2f' % st['dl_drift'], flush=True)
    sd, fu, ha, tu, fi = (st[n] for n in ('stand', 'full', 'half', 'turn', 'fire'))
    check('stick centre 120 VIs: ATST 0 stands (moves < 0.5)', sd['d'] < 0.5, f"{sd['d']:.2f}")
    check(f'stick y +{FULL} 120 VIs: it walks >= 25', fu['d120'] >= 25, f"{fu['d120']:.1f} (240 VIs: {fu['d']:.1f})")
    r = ha['d'] / fu['d'] if fu['d'] else 0
    check(f'stick y +{HALF} 240 VIs: 30..70 % of the full push over 240 VIs', 0.3 <= r <= 0.7,
          f"{ha['d']:.1f} / {fu['d']:.1f} = {100 * r:.0f} %")
    check(f'stick x +60, y centre 240 VIs: it turns >= {TURN_MIN} degrees and stands (moves < 0.5)',
          abs(tu['h'][1]) >= TURN_MIN and tu['d'] < 0.5, f"turned {tu['h'][1]:.1f}, moved {tu['d']:.2f}")
    check('B 120 VIs, stick centre: it fires (the timer +0x100 reset >= 2 times) and the held word has no B',
          fi['fires'] >= 2 and fi['bbit'] == 0, f"{fi['fires']} shots, B on {fi['bbit']} frames, moved {fi['d']:.2f}")
    check('B without Z: no target (+0x16C 0 on every frame)', fi['nz'] == 0, f"{fi['nz']} of 120 frames with a target")
    fz = st['firez']
    check('Z + B 120 VIs: a target on >= 1 frame, only PRBT / ATST / ATAT (never the speeder or a rbgn)',
          fz['nz'] >= 1 and fz['tags'] <= ENEMY_TAGS, f"{fz['nz']} of 120 frames, tags {sorted(fz['tags'])}, "
          f"{fz['fires']} shots, first at {fz.get('t_first')} VIs, head cos {fz.get('cos0', 0):.3f} -> 30 VIs {fz.get('cos30', 0):.3f}")
    bh = st['behind']; bd = [min(m['dmin'] for m in bh.values()), max(m['dmax'] for m in bh.values())]
    for ph, q in bh.items():        # (q: m is the marks)
        print('behind %-6s angle <= %.1f dist %.1f..%.1f pitch %.1f..%.1f aim off <= %.2f screen y feet %.0f..%.0f '
              'head %.0f..%.0f fovy %.2f (%d VIs)' % (ph, q['ang'], q['dmin'], q['dmax'], q['pmin'], q['pmax'], q['ah'],
              *q['yf'], *q['yh'], q['fovy'], q['n']), flush=True)
    check(f'the eye behind: stick x +60 240 VIs in place, the angle (ATST - eye) to the facing <= {B_TURN_MAX:.0f} all along',
          bh['turn']['ang'] <= B_TURN_MAX, f"worst {bh['turn']['ang']:.1f} over {bh['turn']['n']} VIs")
    check(f'and <= {B_SETTLE:.0f} 30 VIs after the stick lets go', bh['settle']['ang'] <= B_SETTLE,
          f"{bh['settle']['ang']:.1f} (still before it: worst {bh['still']['ang']:.1f})")
    check(f'walking 120 VIs (y +{FULL}): the angle <= {B_WALK_MAX:.0f}', bh['walk']['ang'] <= B_WALK_MAX,
          f"worst {bh['walk']['ang']:.1f} over {bh['walk']['n']} VIs")
    check(f'the eye {B_DIST[0]:.1f}..{B_DIST[1]:.1f} from the head point all along (turn, still, walk, stand, B)',
          B_DIST[0] <= bd[0] and bd[1] <= B_DIST[1], f"{bd[0]:.1f}..{bd[1]:.1f}")
    pm = [min(m['pmin'] for m in bh.values()), max(m['pmax'] for m in bh.values())]
    check(f'view pitch {B_PITCH[0]:.0f}..{B_PITCH[1]:.0f} degrees down all along (turn, still, walk, stand, B)',
          B_PITCH[0] <= pm[0] and pm[1] <= B_PITCH[1], f"{pm[0]:.1f}..{pm[1]:.1f}")
    check(f'the rig placed after Trak 0\'s update every game frame (g_atst_trak moves, never {B_GAP} VIs in a row without)',
          max(m['gap'] for m in bh.values()) < B_GAP,
          ', '.join(f"{ph} {m['moves']} of {m['n']} VIs, gap {m['gap']}" for ph, m in bh.items()))
    for ph, what in (('stand', 'standing'), ('walk', f'walking (y +{FULL})'), ('fire', 'B held 120 VIs')):
        p = bh[ph]
        check(f'the feet at screen y <= {B_FEET_MAX}, the head point {B_HEAD[0]}..{B_HEAD[1]} (of 240), {what}',
              0 <= p['yf'][0] and p['yf'][1] <= B_FEET_MAX and B_HEAD[0] <= p['yh'][0] and p['yh'][1] <= B_HEAD[1],
              f"feet {p['yf'][0]:.0f}..{p['yf'][1]:.0f}, head {p['yh'][0]:.0f}..{p['yh'][1]:.0f}, fovy {p['fovy']:.2f}")
    ref, hold = st['sp_ref'], st['sp_hold']
    check('the speeder held while the AT-ST is driven (>= 900 VIs): within 1.0 of its place, health kept, lives kept',
          hold['n'] >= 900 and hold['d'] <= 1.0 and hold['hp'] >= ref['hp'] and hold['lives'] == ref['lives'],
          f"{hold['n']} VIs, moved {hold['d']:.3f}, health {ref['hp']:.1f} -> min {hold['hp']:.1f}, lives {ref['lives']} -> {hold['lives']}")
    sn = st['stance']
    check(f'let go after y +{FULL}: it stops within {STOP_IN} VIs, the clock mod 20 at {STANCE_T} +- 0.5, then moves < 0.5 over 60 VIs',
          sn.get('stop') is not None and sn['stop'] <= STOP_IN and abs(sn['tm'] - STANCE_T) <= 0.5 and sn.get('d60', 9) < 0.5,
          f"stop {sn.get('stop')} VIs, clock {sn.get('t', 0):.2f} (mod 20 {sn.get('tm', 0):.2f}), moved {sn.get('d60', -1):.3f}")
    check('Speeder chosen again: it flies (moves >= 20 in 120 VIs)', st.get('sp_fly', 0) >= 20, f"{st.get('sp_fly', 0):.1f}")
    check('Speeder: the walk bit (+0x108 bit 31) clear within 2 VIs of resume', st['frozen_at_menu']
          and st.get('unfrozen') is not None and st['unfrozen'] <= 2,
          f"set at the menu {st['frozen_at_menu']}, clear {st.get('unfrozen')} VIs after resume")
    check('Speeder: the 8 slots are the saved ones, the mode 0', off['keys'] == pre['keys'] and off['mode'] == 0
          and off['atst_on'] == 0, f"{off}")
    check('Speeder: the target list (0x800DED08, 20 bytes) is the game\'s again', af['tl'] == pre['tl'],
          ' '.join('%08x' % v for v in af['tl']))
    check('Speeder: Trak 0 back on the speeder (its target before) 60 VIs after resume',
          af['trak'] == pre['sp'] == pre['trak'] and af['mode'] == 0 and af['keys'] == pre['keys'],
          f"{af['trak']:08x} speeder {pre['sp']:08x} before {pre['trak']:08x}")
    check('on again: Trak 0 on ATST 0; destroyed (+6 |= 0x20): back on the speeder within 2 VIs',
          st.get('re_cam') is not None and st.get('kill_sp') is not None and st['kill_sp'] <= 2,
          f"on after {st.get('re_cam')} VIs, speeder {st.get('kill_sp')} VIs after the flag")
    s0, sa = st['sky0'], m['sky_a']
    check('Skyhook: A on the row changes nothing (reads "(none)")', sa['row'] == ROW and sa['saved'] == 0
          and sa['atst_on'] == 0 and sa['mode'] == s0['mode'] and sa['obj'] == s0['obj'], f"{s0} -> {sa}")
elif CASE == 'cave':
    a10, h = st['at10'], st['held']
    check('the state starts at Dash (no creature object)', st['start']['obj'] == 0, f"{st['start']}")
    check('up three times from the top is the Creature Cam row', m['at_row']['row'] == ROW, f"row {m['at_row']['row']}")
    check('Wampa: 10 VIs after resume the object is a wampa Trop', a10['tag'] == TROP and a10['kind'] == 2,
          f"{a10['obj']:08x} kind {a10['kind']}")
    check('held: still it 120 VIs later, nothing held', h['obj'] == a10['obj'] and not st.get('lost'),
          f"{h['obj']:08x}, lost {st.get('lost')}")
    check('the camera follows it (eye nearer the creature than Dash)', 0 <= st['eye'][0] < st['eye'][1],
          'creature %.1f, Dash %.1f' % st['eye'])
    check('Wampa: preset 0 has Traditional\'s D-pad in +0x08..+0x16 within 2 VIs of the take (the object set)', st.get('k_trad') is not None
          and st['k_trad'] <= 2, f"{st.get('k_trad')} VIs, before {st['start']['keys']}")
    check('D-left 120 VIs turns the wampa (+0x14) by >= 90 degrees', abs(st['yaw'][1]) >= 90, f"{st['yaw'][1]:.1f}")
    check('and Dash stays put (moves < 0.5)', st['drift'] < 0.5, f"{st['drift']:.2f} (D-up: {st['drift_up']:.2f})")
    check('D-up 120 VIs: the wampa walks (state +0x78 2)', st['walk'] >= 1, f"{st['walk']} of 120 frames")
    check('stick up 120 VIs: the wampa walks (state 2 on >= 100 frames)', st['s_walk'] >= 100, f"{st['s_walk']} of 120")
    check('stick right 120 VIs turns the wampa (+0x14) by >= 90 degrees', abs(st['s_yaw'][1]) >= 90,
          f"{st['s_yaw'][1]:.1f}")
    check('B 60 VIs: the wampa attacks (state 3 on >= 1 frame)', st['s_att'] >= 1, f"{st['s_att']} of 60")
    check('and the game\'s held word has no B bit on any of them', st['s_bbit'] == 0,
          f"{st['s_bbit']} frames, words {sorted('%08x' % w for w in st['held_w'])}")
    check('Dash stays put over the stick and B (moves < 0.5)', st['s_drift'] < 0.5, f"{st['s_drift']:.2f}")
    check('Dash: the 8 slots are the ones before within 2 VIs of the object 0', st.get('k_back') is not None
          and st['k_back'] <= 2, f"{st.get('k_back')} VIs")
    check('Dash: L clears the object within 2 VIs of the press reaching the menu', st.get('l0') is not None
          and st['l0'] <= 3, f"{st.get('l0')} VIs after the pad write (1 of them the pad's own latency)")
    check('Dash: still 0 100 VIs after resume', st['final']['obj'] == 0 and st['final']['paused'] == 0, f"{st['final']}")
else:
    a10, h = st['at10'], st['held']
    check('Trooper: 10 VIs after resume the object is a non-wampa Trop', a10['tag'] == TROP
          and a10['kind'] not in (None, 2), f"{a10['obj']:08x} kind {a10['kind']}")
    check('held: still it 120 VIs later', h['obj'] == a10['obj'] and not st.get('lost'), f"{h['obj']:08x}, lost {st.get('lost')}")
    print('trooper: D-left 120 VIs turned it by %.1f degrees, Dash drift %.2f' % (st['yaw'][1], st['drift']), flush=True)
    check('trooper turns (D-left 120 VIs, +0x14 by >= 30 degrees)', abs(st['yaw'][1]) >= 30, f"{st['yaw'][1]:.1f}")
    check('stick up 120 VIs: the trooper walks (state 2 on >= 100 frames)', st['s_walk'] >= 100, f"{st['s_walk']} of 120")
    check('B 60 VIs: the trooper attacks (state 3 on >= 1 frame)', st['s_att'] >= 1, f"{st['s_att']} of 60")
    check('A from Trooper: Dash (0)', m['a_dash']['obj'] == 0, f"{m['a_dash']}")
    check('A from Dash: Wampa', m['a_wampa']['kind'] == 2, f"{m['a_wampa']}")
    check('Reset cheats: back to Dash (the value before the first change)', m['reset']['obj'] == 0
          and st['final']['obj'] == 0, f"{m['reset']} / {st['final']}")
sys.exit(report())
