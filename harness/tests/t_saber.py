"""Luke's lightsaber (saber.c; the blade in guard.c; the ammo text in cheats.c): the weapon slot and the sounds.

    M64CPU=0 python3 t_saber.py <rom> <case>     cases: cycle, snd, combo, spin, deflect, boss, melee, hold, flow, parry,
                                                 saber_fix, bugs (a probe: per-VI numbers, no checks)
    env STILL=<png>  (cycle) one GLideN64 still of Luke holding the lit blade, copied to <png>; DUMP=<file> the RAM then;
                     (combo) one mid-swing at VI STILL_K (33: sw1 near its cut); (hold) one still per phase,
                     <png stem>_<phase>.png, and the four on one contact image at <png>; SABER_DBG=1 / 2 per-VI prints
                     (boss: every 2nd VI / every VI, with the controller, the press latch, his flags; SABER_M=<hex> saber.c's
                     M record's address from the build's nm (its cur, next, t); deflect: 1 the bolts near him when he is
                     hurt, 2 the bolts within 45 and area shots within 15 of him on the VI before and the VI he is hurt;
                     DEFL_T=<VIs> a longer phase; TAIL_DBG=1 each followed turned bolt's tail - contact, head
                     offset, length and speed a VI); (flow) the d stills on two contact images, <png stem>_free.png
                     and <png stem>_guard.png; SABER_DBG=1 a line per VI

Runs the build's own ROM (PAYLOAD_BUILD/sote-patch.z64; <rom> only when that is missing: the sounds play from its
ROM blob) from palace.st (its held radio line let go), every weapon given (ammo 50 in +0xC0..+0xD4, the pickup bits
0x3E000 in +0x74), Dash's health held at 100.
  cycle: with the Look on Luke (g_guard_on 2), from the laser, C-up 8 times: the ids 2 1 3 5 4 6 0 2 (the saber right
         after the Stunner, then the laser); on 6 the HUD's ammo text (element 0x19's colour, 0x80111250 + 4 * 0x19)
         has alpha 0, on the Stunner not; on 6 the level's HUD sprite slot 6 (*0x8013CE2C + 24) holds the image's icon
         record (SABR +16) and the HUD placed it (its x, y and element 6's position 0x80111110 + 24: 215, 185), on the
         Stunner slot 6 empty and element 6 at -1000; on 6 the hand's list of ours (g_ours bone 6) holds the image's SABR mesh and
         not Dash's weapon, on the Stunner the weapon; then the Look to Dash with the saber out: the id the laser
         within 3 frames; then with the Look on Dash from the laser, C-up 7 times: 2 1 3 5 4 0 2 (never 6).
  snd:   the bank's instrument is saber.c's copy (*0x800EEB04 + 0xC = g_inst, 140 sounds); from the Stunner, C-up to the
         saber: 'on' (id 0x83) queued within 5 frames, the hum (0x84, loop 1) in a queue slot on every check for 2 s;
         C-up away: 'off' (0x8B) queued within 5 frames, the hum not asked any more (its slot's frame stamp stands),
         and its slot freed (state -1) or silent (volume 0) within 1.0 s (printed: when its volume reached 0 and when
         the slot was freed); the game's switch click (0x15) in no queue slot on the 10 VIs from the press to the
         saber (printed per VI), queued within 10 VIs of the press away.
  combo: Luke, the saber out; two guards (kind 0) held idle (AI state 0, its timer held) at health 1000: one 7.5 ahead,
         one 3 ahead and 7.5 to his left (>= 6 off every hit point); B tapped every 8 VIs until sw3 starts (a tap
         from a swing's cut queues the next, which starts at the swing's link time): the moves sw1, sw2, sw3 in order
         (g_saber_move), then none; the near guard loses 170 a swing, the other nothing; each swing's step <= 2.0 units,
         sw1's > 0.5 (sw2 and sw3 may end on the near guard's body); each hit point forward 2.6..4.4, |right| <= 1.2,
         up 3.0..5.0 from his feet; cut to cut (game time) 0.367 and 0.40 +- 0.1 s. Printed: each hit point and its
         distance to each guard.
  spin:  B held from VI 20 to 120: sw1 at once, then (0.6 s of game time after the press) the spin, blended in from
         where sw1 is; it plays 0.77 +- 0.08 s; guards (health 1000) 6 ahead, 5.5 behind, 10 to his right: the one behind loses 250
         (the spin cuts all round; the one ahead 170 + 250), the one 10 off nothing.
  deflect: one guard (kind 0) alerted (+0x74 | 0x20), its AI left to fire, held 40 ahead facing Luke, health 1000;
         Luke's damage summed (his health refilled each VI). DEFL_T (600) VIs facing it: >= 2 bolts turned
         (g_saber_deflects), its health down, Luke's damage 0; a flash for each turned bolt (g_saber_flashes); at the
         first, an Expl object of his (sender +0x88), kind 4, flags 0x2122, damage 0, RGBA 0xC8FFC8FF within FLASH_OFF
         (0.06) of g_saber_flash, that place within 6.0 of him across and 0..7 above his feet, its slot's state 0 within 0.5 s
         (its scale printed from 0.4 up); each turned bolt grows out of the blade: over TAIL_VIS (10) VIs from its flash
         its tail +0x50 never more than TAIL_SLACK (0.05) behind the flash's place along its flight (+0x78), the least
         printed; then DEFL_T VIs turned round (his yaw written every VI; palace.st has a wall
         at his back): his damage > 0, none turned, no flash. STILL=<png>: FLASH_VIS stills, one a VI, from each of
         the first three flashes, <png stem>_flash<n>_<VI>.png, in the drop view (L twice, as hold) with its eye written every VI of phase A
         at his place + DEFL_CAM
         (in front of him, to his side: the drop view's own eye behind him has his head over the blade).
  boss:  om_ig88.st, IG-88 (class Boss) held BOSS_AT (5.5) in front of Luke at Luke's floor height every frame (his
         own z on that state is a raised floor 7.5 up: BOSS_Z=own keeps it, and the shot's height span misses him);
         the presses follow the swings the game plays: one tap starts sw1, then B is held from the playing swing's
         cut time (the block played: Dash's controller 0x800E1328 on our descriptor, id 0x70 + move (+ 4: its in-place block), its time +0; the
         cut from the image's SWN2 table, +12: saber.c queues a press from there) until the next swing starts, until
         sw3: every swing (sw1, sw2, sw3 among them) takes
         his health +0x5C4 down by 170 x his own scale, at most the boss update's cap per hit (~0x80046634: 50 / 45 / 30 on
         difficulty 1 / 2 / 3; IG-88 on 2: 45); the hit sound (0x89) queued after
         at least one hit, or else every slot of the game's 8-slot sound queue busy at each hit (the VI its health drop is seen and
         the next: saber.c asks for the sound in the overlay after the game's update that took it) (his own sounds fill
         it near him: a lost hit sound is the game's, reported so); then held BOSS_FAR (9.5, >= 6 from each hit point):
         a second combo takes nothing. (Closer than his own +0x5E0 6.0, about 5.1 flat, IG-88 takes nothing by the
         game's rule: his radius +0x60 made negative and the touch damage on the player instead; BOSS_AT=5.0 shows it.)
  melee: palace.st, t_melee's setup (Luke 6 ahead of Trop 0 facing her, the other Trops held idle), the saber out,
         g_melee_on: from her grab the hilt leaves the hand within 5 frames and its slot stays empty through the hold
         (no blaster either), 'off' (0x8B) queued within 5 frames, the hum's slot freed or silent within 1.0 s of game
         time and not asked again in the hold, the weapon id 6 throughout; when the phase leaves the get-up, 'on'
         (0x83) queued and the hilt back within 5 frames.
  hold:  Luke from the Stunner, the saber drawn standing by the game's C-up cycle; the camera switched to the drop view
         (L twice, 30 VIs apart: follow, first person, drop) and its eye written every VI at his place + HOLD_CAM (10
         out along his facing turned 35 deg, 3 up): his front and hands. Five phases of 60 VIs: standing right after
         the draw, walking (stick half, straight ahead: core.c's stick follows its lazy camera, not the drop one),
         running (full), Z held with a lock on a fake target 15 ahead strafing (stick x full; the drop view pressed
         back, Z leaves it), standing after that. Per phase from its VI 30 (stop: 45, the blend into Sstn): the weapon
         6, no swing playing (g_saber_move -1), the swings' last block followed by our first arm copy g_mv[0] tagged
         Sstn, and the block his animation state plays (+0x18C: +0x14 current, +0x18 blended to) one of our arm
         copies (g_mv) with the phase's tag: Sstn, mosy, trot, shfl or shfr, Sstn. Printed: the blocks seen per phase.
  flow:  one swing's timing, step and end (palace.st, as hold starts: the drop view, the saber drawn by the game's
         cycle; the guards held idle in their places, out of reach); eleven phases, each from Luke held SETTLE s at the
         start place, times from the swing's start (g_saber_move 0): a, one tap: sw1 plays 0.70 +- 0.08 s, its cut
         (g_saber_cuts + 1) at 0.25 +- 0.07 s, his displacement along his facing 1.5 +- 0.3, on each frame of the step
         (the controller's time within the table's step window) within 0.6 of the table's linear step at that time,
         within 0.3 on the first frame past it, the controller on the stand (descriptor id 0) within 0.2 s of the swing's
         end and at the phase's end;
         d_free / d_guard, one tap each, the second with a guard FLOW_GUARD ahead (his step meets its body): d_free
         plays the block 'sw1 ' (the controller's descriptor's tag) and moves him 1.5 +- 0.3, d_guard plays 'swp1' (the
         in-place block, saber.c blocked()) and moves him < 0.3; eight stills of sw1 each at FLOW_STILLS (STILL only); b_run, the stick full forward from 0.45 s: the swing over by
         0.55 s, his block trot within 0.3 s more; b_z, Z held from 0.45 s, no stick: the swing plays its 0.70 s;
         c_same, a second tap at 0.60 s (past link + CHAIN_LATE: sw1 again, the same block): starts 0, 0, the second at
         0.70 +- 0.08 s with the block's frame below 3; c_chain, a second tap at 0.30 s: sw2 at 0.433 +- 0.07 s with the
         state blending (mode 3) on that frame. The stick during a swing (core.c zeroes its move and holds his turn to
         SWING_TURN until the link): e_fwd / e_right / e_back, one tap as a with the stick full (forward, right, back)
         from the tap's VI to sw1's link, then released; a2, phase a again (the spread, printed); each measured over
         the code's own window, the swing's first update (g_saber_move 0) to the last update before the link (the B
         press's update before it, the player's last move, and the updates past the link feed the stick as normal):
         his displacement (world x, y), his facing's turn, drift = |displacement - a's|; e_fwd |displacement| - a's
         <= 0.35; e_right / e_back his turn <= 32 deg (SWING_TURN 30 + 2) and |displacement| within 0.35 of a's (the
         step only, turned; a vs a2 alone spread 0.2). Before the fix the drift was 1.66 / 3.18 / 3.72 and the turn
         0 / 124 / 152 deg.
  parry: the parry (saber.c parry_frame, saber_blst's look-ahead; exported g_parry, g_saber_parry_v / _w), palace.st,
         the drop view as hold, the saber out, one guard alerted, its own AI firing (health held); phases (PARRY_PH):
         [stills: STILL only, each variant forced at w 1 through g_parry, a still each], near (held 40 ahead), jump (A
         every 60 VIs, the guard at 40; over once two bolts are turned mid-jump), far (held 77 ahead), run1 (back at the
         start, the stick full forward, the guard held still 60 ahead along his first facing; STILL: a still at the
         first w >= 0.9), quiet, run0 (the same run, the guard held idle). Checks: every bolt turned on the ground has a
         parry started for it (g_parry.bolt, its in > 0) no later than its turn's VI; w >= 0.9 within 2 VIs after each
         (4 for a bolt first seen in the frame it is turned: point blank, one game frame of PARRY_IN);
         the far guard: a parry starts >= 0.1 s before its turn; w back to 0 within PARRY_IN + HOLD + OUT + 0.1 s after
         the last turn; run1's speed over 2 s >= 90% of run0's, w > 0.5 seen in run1; mid-jump: bolts turned, no parry
         started; every bolt turned on the ground (any phase, any crossing) within BLADE_MAX of the blade at its flash or
         the two VIs after; run1's turns printed with the parry's fd (g_parry's, the distance ahead it was blended at). STILL=<png>: <stem>_<variant>.png, <stem>_running.png and the contact image at <png>.
  saber_fix: the playtest's items 1-4 fixed (saber.c), on bugs' setups, one palace.st load per run (env FIX=<runs> a
         subset; FIX_Q=1 the sound queue's slots on each die_swing row): die_swing (killed by the game's damage while
         sw1 plays): diea played or blended to within 4 VIs and for >= 150 VIs, the blade's light chain off the world
         root within 4 VIs (its 'off' is not checked: the game's death sounds fill the 8-slot queue that frame), after the respawn the light back and 'on' (0x83) queued;
         run_swing (the stick full, a B tap every 4 VIs / every 40, 3 s) and spin_run (B held through the spin, the
         stick from its link): no VI with block trtg, no VI with the tip behind him (back: pointing back, the tip
         > 0.3 behind him below 7 up; sw1's wind-up leans the blade back with the tip in front; the spin's sweep exempt); free (60 s against a guard): the spine node's translation
         z within 0.5 of 1.136 on every VI.
  bugs:  a probe for the playtest's saber items (no checks: prints 'BUG' rows, a 'BUGS' summary): as hold starts (the
         drop view, the eye at HOLD_CAM, the saber drawn by the cycle), then from VI 90, by env BUGS:
         die_stand / die_swing / die_laser: health 1, an alerted guard held 40 ahead, his back to it (killed by the game's
         own damage 0x800732D4, which asks diea, id 23, below 1); standing with the saber, mid-combo (B every 8 VIs), or
         with the laser (the reference); run_swing: the stick full forward, B every BUG_EVERY (8) VIs; spin_run: B held to
         the spin, the stick from its M.t BUG_STICK (link / start / mid), BUG_HOLD=1 B kept held after; free: 60 s of
         600-VI rounds (runs with taps, a tap, the spin, jumps, the saber away and drawn again), BUG_GUARD=1 with an
         alerted guard held 30 ahead of him (parries). Per VI: the block his state plays and blends to (+0x18C +0x14 /
         +0x18; suffix m an arm copy, s a swing, g the game's), the controller's descriptor id and time, g_saber_move and
         saber.c's M.t (its 'M' in .saber), the parry's w, the blade in his frame (forward component bf, foot, tip:
         back=1 pointing back with the tip 0.3 behind him below 7, inbody=1 any point in BUG_BODY), and the upper body:
         bones 10 9 8 5 1's child count, list (g_ours) and row scale, the head's place through the chain (bad=[...] when
         off; then the chain's node translations). STILL=<png>: up to BUG_SHOTS stills of flagged VIs (BUG_SHOT_BAD=1:
         the bad ones only), BUG_SHOTW=a,b one every 2nd VI in [a, b); BUG_WIN=a,b prints every VI there and the playing
         block's spine entry; BUG_ENTRIES=1 at the end every block in his chain with an entry's translation offset
         (+0x1C..+0x24) beyond 100. Stills lag the RAM rows by 2..4 VIs.
"""
import os, shutil, struct, sys
import _path
import paths
import m64
import inject as inj
from m64 import Emu, BTN
from inject import inject, syms
from testlib import check, report, make_fake, place_fake, FAKE

S = syms()
CASE = sys.argv[2] if len(sys.argv) > 2 else 'cycle'
STILL = os.environ.get('STILL')
ROM = inj.BUILD / 'sote-patch.z64'
e = Emu(str(ROM) if ROM.exists() else sys.argv[1], **({'video': m64.GLN} if STILL else {}))
STATE = os.environ.get('SABER_STATE', 'om_ig88.st' if CASE == 'boss' else 'palace.st')
WEAPON, FLAGS, AMMO, HP = 0xB8, 0x74, 0xC0, 0xB4
BOSS_CAP = {1: 50.0, 2: 45.0, 3: 30.0}      # the boss update's per-hit cap by difficulty (~0x80046634)
PICKUPS = 0x3E000
HUD_COL, HUD_AMMO = 0x80111250, 0x19
Q = 0x80110FE8                           # the sound queue: 8 x 0x20 (+0 state, +4 id, +8 loop, +0xC stamp, +0x18 vol)
ID_ON, ID_HUM, ID_HIT, ID_OFF = 0x83, 0x84, 0x89, 0x8B
ID_SWITCH = 0x15                         # the game's weapon switch click (its set-weapon 0x8006E608)
OURS, ROW = S['g_ours'], 9 * 4           # guard.c: 19 lists of 9 words
GUARD = inj.GUARD_VRAM
st = {'k0': None, 'ids': [], 'log': []}


def r32(a): return e.r32(a)
def s16(v): return v - 0x10000 if v & 0x8000 else v
def wid(h): return s16(e.r16(h + WEAPON))
def set_wid(h, v): e.w32(h + WEAPON, (r32(h + WEAPON) & 0xFFFF) | ((v & 0xFFFF) << 16))
def alpha(): return r32(HUD_COL + 4 * HUD_AMMO) & 0xFF
def hand(): return [r32(OURS + 6 * ROW + 4 * i) for i in range(9)]
def slots(): return [(r32(Q + 0x20 * i), r32(Q + 0x20 * i + 4), r32(Q + 0x20 * i + 8), r32(Q + 0x20 * i + 0xC),
                      r32(Q + 0x20 * i + 0x18)) for i in range(8)]
def queued(sid, loop=None): return [s for s in slots() if s[0] != 0xFFFFFFFF and s[1] == sid and (loop is None or s[2] == loop)]


def sabr():
    """The image's SABR mesh (guard_asset.py: after LITN's parts)"""
    litn = GUARD + 8 + 8 * 19 + 12
    at = litn + 12 + 4 * (1 + r32(litn + 4)) * r32(litn + 8)
    return r32(r32(at + 8)) if r32(at) == 0x53414252 else 0


def icon():
    """The image's HUD icon record (SABR +16) and the level's sprite slot 6 (*0x8013CE2C + 24)"""
    litn = GUARD + 8 + 8 * 19 + 12
    at = litn + 12 + 4 * (1 + r32(litn + 4)) * r32(litn + 8)
    return (r32(at + 16) if r32(at) == 0x53414252 else 0), r32(r32(0x8013CE2C) + 24)


def setup(h):
    for i in range(6): e.wf(h + AMMO + 4 * i, 50.0)
    e.w32(h + FLAGS, r32(h + FLAGS) | PICKUPS)


def press(k, at, every=20):
    """C-up held 4 frames at at, at + every, ..."""
    return BTN['CU'] if k >= at and (k - at) % every < 4 else 0


def cycle(k, h):
    b = 0
    if k == 9: e.w32(S["g_guard_on"], 2); set_wid(h, 0)
    A = 20                                           # Luke: 8 presses from k 20
    b |= press(k, A) if A <= k < A + 8 * 20 else 0
    if A <= k < A + 8 * 20 and (k - A) % 20 == 14:
        st['ids'].append(wid(h))
        if wid(h) == 6:
            st['alpha6'] = alpha(); st['hand6'] = hand(); rec, sl = icon()
            st['icon6'] = (rec, sl, e.r16(rec) if rec else 0, e.r16(rec + 2) if rec else 0, s16(e.r16(0x80111110 + 24)),
                           s16(e.r16(0x80111112 + 24)), e.r16(rec + 0x10) if rec else 0)
            if STILL and 'shot' not in st: st['shot'] = k
        if wid(h) == 4: st['alpha4'] = alpha(); st['hand4'] = hand(); st['icon4'] = icon() + (s16(e.r16(0x80111110 + 24)),)
    if 'shot' in st and k == st['shot'] + 1:
        e.shot()
        if os.environ.get('DUMP'): e.dump(os.environ['DUMP'])
    B = A + 8 * 20 + 20                              # back to 6, then the Look to Dash
    if k == B: set_wid(h, 4)
    b |= press(k, B) if B <= k < B + 4 else 0
    if k == B + 14: st['six'] = wid(h); e.w32(S['g_guard_on'], 0)
    if k == B + 17: st['after_look'] = wid(h)
    C = B + 40                                       # Dash: 7 presses from the laser
    if k == C - 4: set_wid(h, 0)
    b |= press(k, C) if C <= k < C + 7 * 20 else 0
    if C <= k < C + 7 * 20 and (k - C) % 20 == 14: st.setdefault('dash', []).append(wid(h))
    if k == C + 7 * 20 + 10: finish_cycle(); e.stop()
    return b


def finish_cycle():
    check('Luke: C-up from the laser gives 2 1 3 5 4 6 0 2', st['ids'] == [2, 1, 3, 5, 4, 6, 0, 2], f"ids {st['ids']}")
    check('on 6 the ammo text has alpha 0', st.get('alpha6') == 0, f"alpha {st.get('alpha6')}")
    check('on the Stunner the ammo text is drawn', st.get('alpha4', 0) > 0, f"alpha {st.get('alpha4')}")
    m = sabr()
    weapon = [c for c in st.get('hand4', []) if 0x80000400 <= c < 0x80800000 and not GUARD <= c < GUARD + 0x38000]
    check('on 6 the hand holds the SABR mesh, not the weapon', m and m in st.get('hand6', []) and weapon
          and not set(weapon) & set(st.get('hand6', [])), f"sabr {m:#x} weapon {[hex(c) for c in weapon]} "
          f"hand {[hex(c) for c in st.get('hand6', [])[:5]]}")
    check('on the Stunner the hand holds the weapon', weapon and m not in st.get('hand4', [m]),
          f"hand {[hex(c) for c in st.get('hand4', [])[:5]]}")
    i6 = st.get('icon6', (0,) * 7)
    check("on 6 the HUD draws the image's icon in sprite slot 6 at (215, 185)", i6[0] and i6[1] == i6[0] and i6[2:6] == (215, 185, 215, 185),
          f"record {i6[0]:#x} slot {i6[1]:#x} its place ({i6[2]}, {i6[3]}) element 6 at ({i6[4]}, {i6[5]}) attr {i6[6]:#x}")
    i4 = st.get('icon4', (0, 1, 0))
    check('on the Stunner slot 6 is empty again, element 6 hidden', i4[1] == 0 and i4[2] == -1000, f"slot {i4[1]:#x} element 6 x {i4[2]}")
    check('the Look to Dash with the saber out: the laser within 3 frames', st.get('six') == 6 and st.get('after_look') == 0,
          f"before {st.get('six')} after {st.get('after_look')}")
    check('Dash: C-up never gives 6', st.get('dash') == [2, 1, 3, 5, 4, 0, 2], f"ids {st.get('dash')}")
    if STILL and 'shot' in st:
        import glob
        shots = sorted(glob.glob(os.path.join(e.shot_dir, '*.png')), key=os.path.getmtime)
        if shots: shutil.copy(shots[-1], STILL); print('still', STILL, flush=True)


def snd(k, h):
    b = 0
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 4)
        bk = r32(0x800EEB04); inst = r32(bk + 0xC)
        st['inst'] = inst; st['count'] = s16(e.r16(inst + 0xE))
    A = 20
    b |= press(k, A) if A <= k < A + 4 else 0
    if A <= k <= A + 5 and queued(ID_ON): st.setdefault('on_at', k - A)
    if A <= k < A + 10:                 # the ignition: the game's switch click (0x15) freed, 'on' alone
        st.setdefault('click_on', []).append(bool(queued(ID_SWITCH)))
        print(f'VI +{k - A} (on): 0x15 {bool(queued(ID_SWITCH))} on {bool(queued(ID_ON))}', flush=True)
    if A + 10 <= k <= A + 130 and k % 10 == 0:
        st.setdefault('hum', []).append(bool(queued(ID_HUM, 1)))
    B = A + 140
    b |= press(k, B) if B <= k < B + 4 else 0
    if k == B - 1: st['id_before'] = wid(h)
    if B <= k <= B + 5 and queued(ID_OFF): st.setdefault('off_at', k - B)
    if B <= k < B + 10:                 # put away: the click kept, with 'off'
        if queued(ID_SWITCH): st.setdefault('click_off', k - B)
        print(f'VI +{k - B} (off): 0x15 {bool(queued(ID_SWITCH))} off {bool(queued(ID_OFF))}', flush=True)
    if k == B + 8:
        st['id_after'] = wid(h)
        hs = queued(ID_HUM, 1); st['hum_slot'] = slots().index(hs[0]) if hs else None
        st['stamp0'] = hs[0][3] if hs else None
    if B + 8 < k <= B + 240 and st.get('hum_slot') is not None:
        i = st['hum_slot']; s = slots()[i]
        mine = s[1] == ID_HUM
        if k == B + 30: st['stamp1'] = s[3] if mine else None
        if (not mine or s[4] == 0) and 'silent_at' not in st: st['silent_at'] = k - B
        if (not mine or s[0] == 0xFFFFFFFF) and 'free_at' not in st: st['free_at'] = k - B
        if k % 20 == 0: print(f'VI +{k - B}: hum slot {i} state {s[0]:#x} id {s[1]:#x} vol {s[4]} stamp {s[3]}', flush=True)
    if k == B + 250: finish_snd(); e.stop()
    return b


def finish_snd():
    check("the bank's instrument is saber.c's copy with 140 sounds", st['inst'] == S['g_inst'] and st['count'] == 140,
          f"inst {st['inst']:#x} (g_inst {S['g_inst']:#x}) count {st['count']}")
    check("C-up to the saber: 'on' queued within 5 frames", st.get('on_at') is not None, f"at {st.get('on_at')}")
    co = st.get('click_on', [])
    check("C-up to the saber: the switch click (0x15) in no queue slot for 10 VIs", len(co) == 10 and not any(co),
          f"VIs with it {sum(co)}/{len(co)}")
    check("C-up away: the switch click (0x15) queued within 10 VIs, 'off' too",
          st.get('click_off') is not None and st.get('off_at') is not None,
          f"click at {st.get('click_off')} off at {st.get('off_at')}")
    check('the hum is in a queue slot on every check for 2 s', st.get('hum') and all(st['hum']),
          f"{sum(st.get('hum', []))}/{len(st.get('hum', []))}")
    check("C-up away: 'off' queued within 5 frames", st.get('off_at') is not None and st.get('id_before') == 6
          and st.get('id_after') == 0, f"at {st.get('off_at')} ids {st.get('id_before')} -> {st.get('id_after')}")
    check('the hum is not asked any more (its stamp stands)', st.get('stamp0') is not None and st.get('stamp1') in
          (st.get('stamp0'), None), f"stamp {st.get('stamp0')} -> {st.get('stamp1')}")
    sil, fr = st.get('silent_at'), st.get('free_at')
    check('the hum slot silent or freed within 1.0 s', min(x for x in (sil, fr, 1e9) if x is not None) <= 60,
          f"volume 0 at VI +{sil}, freed at VI +{fr} (60 VIs = 1 s)")


# ---- the swings ----
TROP_HP, TROP_STATE, TROP_TIMER = 0x7C, 0x78, 0x80


def trops():
    p = r32(0x80112830)
    for i in range(80):
        rec = r32(p + 4 * i)
        if not rec: break
        if r32(rec) == 0x54726F70:
            return [r32(rec + 0x10) + j * r32(rec + 0x0C) for j in range(r32(rec + 8))]
    return []


def V(o, a): return [e.rf(o + a + 4 * i) for i in range(3)]


def put(o, p, yaw):
    for a in range(3): e.wf(o + 0x08 + 4 * a, p[a]); e.wf(o + 0x50 + 4 * a, p[a])
    e.wf(o + 0x14, yaw)


def hold_trops(h):
    for o, (f, s_, yaw) in st['tp'].items():
        p0, fw = st['p0'], st['fw']; rt = (fw[1], -fw[0])
        put(o, [p0[0] + f * fw[0] + s_ * rt[0], p0[1] + f * fw[1] + s_ * rt[1], p0[2]], yaw)
        if e.rf(o + TROP_HP) <= 0: continue   # fallen: its own death plays
        e.w32(o + TROP_STATE, 0); e.wf(o + TROP_TIMER, 100.0)


def swings(k, h, places, presses, kind=0, hp=1000.0):
    """places: [(forward, right)] of troopers from Luke's start (facing him); presses(k, move) -> B pressed; kind the
    Trop kind (+0x74 & 0xF: 0 guard, 2 wampa); hp their health at the start (None: their own; 1000: above any combo's
    drops)"""
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 6)
        st['p0'] = V(h, 0x50); fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = (fw[0] ** 2 + fw[1] ** 2) ** 0.5
        st['fw'] = [fw[0] / l, fw[1] / l]
        yaw_to = lambda f, s_: (e.rf(h + 0x8C) + 180.0) % 360.0
        T = [o for o in trops() if e.rf(o + TROP_HP) > 0 and r32(o + 0x74) & 0xF == kind][:len(places)]
        st['tp'] = {o: (f, s_, yaw_to(f, s_)) for o, (f, s_) in zip(T, places)}
        for o in T:
            if hp is not None: e.wf(o + TROP_HP, hp)
        st['moves'], st['hp_at'], st['pos_at'], st['hits'] = [], [], [], []
    if k < 9: return 0
    hold_trops(h)
    m = s16(r32(S['g_saber_move']) >> 16) if 0 else struct.unpack('<i', struct.pack('<I', r32(S['g_saber_move'])))[0]
    if not st['moves'] or st['moves'][-1] != m:
        st['moves'].append(m); st['hp_at'].append([e.rf(o + TROP_HP) for o in st['tp']]); st['pos_at'].append(V(h, 0x50))
        st.setdefault('t_at', []).append(clock())
        if os.environ.get('SABER_DBG'): print(f'k {k} move {m} hp {st["hp_at"][-1]} pos {[round(x, 2) for x in V(h, 0x50)]} trop state/flags {[(r32(o + TROP_STATE), hex(r32(o + 0x74))) for o in st["tp"]]}', flush=True)
    if queued(ID_HIT): st['snd'] = st.get('snd', 0) + 1
    ht = [e.rf(S['g_saber_hit'] + 4 * i) for i in range(4)]
    if ht != st.get('lasthit') and any(ht):
        st['lasthit'] = ht; p = V(h, 0x50); fw = st['fw']; d = [ht[0] - p[0], ht[1] - p[1]]
        st['hits'].append((k, round(d[0] * fw[0] + d[1] * fw[1], 2), round(d[0] * fw[1] - d[1] * fw[0], 2), round(ht[2] - p[2], 2), ht[3],
                           [round(((V(o, 0x50)[0] - ht[0]) ** 2 + (V(o, 0x50)[1] - ht[1]) ** 2) ** 0.5, 2) for o in st['tp']],
                           [round(e.rf(o + 0x60), 2) for o in st['tp']], round(clock(), 3)))
    if os.environ.get('SABER_DBG') == '2' and st['hits'] and k - st['hits'][-1][0] < 12:
        xp = r32(0x80112E68 + 0x10); xs = r32(0x80112E68 + 0xC)
        ex = [(hex(x), hex(r32(x + 0x60)), round(e.rf(x + 0x8C), 3), round(e.rf(x + 0xD8), 3), r32(x + 0xDC), round(e.rf(x + 0x84), 1))
              for x in (xp + xs * i for i in range(r32(0x80112E68 + 8))) if r32(x + 0x88) == h and r32(x + 0x60) >> 16]
        print(f'  k {k} hp {[round(e.rf(o + TROP_HP), 1) for o in st["tp"]]} expl {ex} clock {e.rf(h + 0xD8):.3f}', flush=True)
    return BTN['B'] if presses(k, m) else 0


def combo(k, h):
    if STILL and k == int(os.environ.get('STILL_K', 33)):
        e.shot(); st['shot'] = k
    if STILL and k == int(os.environ.get('STILL_K', 33)) + 3:
        import glob
        shots = sorted(glob.glob(os.path.join(e.shot_dir, '*.png')), key=os.path.getmtime)
        if shots: shutil.copy(shots[-1], STILL); print('still', STILL, flush=True)
    b = swings(k, h, [(7.5, 0.0), (3.0, -7.5)], lambda k, m: 20 <= k and (k - 20) % 8 < 4 and st['moves'].count(2) == 0 and k < 400)
    if k == 420: finish_combo(); e.stop()
    return b


def finish_combo():
    seq = [m for m in st['moves'] if m >= 0]
    check('three presses play sw1, sw2, sw3 in order', seq[:3] == [0, 1, 2] and st['moves'][-1] == -1, f"moves {st['moves']}")
    hp = st['hp_at']; ends = [i for i, m in enumerate(st['moves']) if i > 0]
    near = [hp[0][0]] + [hp[i][0] for i in ends]; far = [hp[0][1]] + [hp[i][1] for i in ends]
    drops = [round(a - b, 1) for a, b in zip(near, near[1:]) if a - b > 0.01]
    check('the near trooper loses 170 a swing', drops == [170.0, 170.0, 170.0], f"health {near}")
    check('the far trooper loses nothing', all(abs(x - far[0]) < 0.01 for x in far), f"health {far}")
    P = st['pos_at']; steps = [round(((P[i + 1][0] - P[i][0]) ** 2 + (P[i + 1][1] - P[i][1]) ** 2) ** 0.5, 2) for i in range(len(P) - 1)]
    sw = steps[1:4]
    check('each swing steps him <= 2.0 units forward, sw1 > 0.5', len(sw) == 3 and max(sw) <= 2.0 and sw[0] > 0.5,
          f"steps sw1..sw3 {sw} (sw2, sw3 may end on the near trooper's body: no crossing)")
    H = st['hits'][:3]
    check('hit points forward 2.6..4.4, |right| <= 1.2, up 3.0..5.0 from his feet', len(H) == 3 and all(
          2.6 <= x[1] <= 4.4 and abs(x[2]) <= 1.2 and 3.0 <= x[3] <= 5.0 for x in H), f"{[x[1:4] for x in H]}")
    cc = [round(b[-1] - a[-1], 3) for a, b in zip(H, H[1:])]
    check('cut to cut 0.367 and 0.40 +- 0.1 s', len(cc) == 2 and abs(cc[0] - 0.367) <= 0.1 and abs(cc[1] - 0.40) <= 0.1, f"{cc}")
    hs = [h_ for h_ in st['hits']]
    far = st['far_at'] if 'far_at' in st else None
    print('hits (VI, forward, right, up from his feet, reach):', st['hits'], 'VIs with the hit sound queued:', st.get('snd', 0), flush=True)


def spin(k, h):
    b = swings(k, h, [(6.0, 0.0), (-5.5, 0.0), (0.0, 10.0)], lambda k, m: 20 <= k < 120)
    if k == 300: finish_spin(); e.stop()
    return b


def finish_spin():
    seq = [m for m in st['moves'] if m >= 0]
    check('B held 0.6 s after the press plays the spin', seq[:2] == [0, 3] and 3 in seq, f"moves {st['moves']}")
    hp0, hp1 = st['hp_at'][0], [e.rf(o + TROP_HP) for o in st['tp']]
    d = [round(a - b, 1) for a, b in zip(hp0, hp1)]
    check('the trooper behind him loses 250 (the spin cuts all round)', d[1] == 250.0, f"drops {d}")
    check('the trooper ahead loses 170 + 250 (sw1 and the spin)', d[0] == 420.0, f"drops {d}")
    check('the trooper 10 units off loses nothing', d[2] == 0.0, f"drops {d}")
    i = st['moves'].index(3) if 3 in st['moves'] else -1
    ln = st['t_at'][i + 1] - st['t_at'][i] if 0 <= i < len(st['t_at']) - 1 else None
    check('the spin plays 0.77 +- 0.08 s', ln is not None and abs(ln - 0.77) <= 0.08, f"{ln}")
    print('drops (ahead 6: sw1 + spin, behind 5.5, side 10):', d, 'hits:', st['hits'], flush=True)


DEFL_T = int(os.environ.get('DEFL_T', 600))         # VIs per phase


def deflect_case(k, h):
    """one alerted guard (kind 0) held 40 ahead (A), then 40 behind (B), facing Luke, its own AI firing"""
    import math
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 6)
        st['p0'] = V(h, 0x50); fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = (fw[0] ** 2 + fw[1] ** 2) ** 0.5
        st['fw'] = [fw[0] / l, fw[1] / l]
        st['g'] = [o for o in trops() if e.rf(o + TROP_HP) > 0 and not r32(o + 0x74) & 0xF][0]
        e.wf(st['g'] + TROP_HP, 1000.0); e.w32(st['g'] + 0x74, r32(st['g'] + 0x74) | 0x20)
        st['dmg'] = {'A': 0.0, 'B': 0.0}; st['defl'] = {}; st['ghp'] = {}; st['fl'] = {}; st['fshots'] = 0
        st['shots0'] = set(os.listdir(e.shot_dir)) if STILL else set()
    if k < 9: return 0
    ph = 'A' if k < 20 + DEFL_T else 'B'
    if ph not in st['defl']:
        st['defl'][ph] = r32(S['g_saber_deflects']); st['ghp'][ph] = e.rf(st['g'] + TROP_HP)
        st['fl'][ph] = st['flprev'] = r32(S['g_saber_flashes'])
    flash_watch(h, ph)
    turn_watch(h, ph)
    blade_track(h, ph)
    hold_watch(ph)
    if STILL and ph == 'A' and e.r16(VIEW) == 4:   # the eye in front of him, to his side (DEFL_CAM)
        p = V(h, 0x50); a_ = math.atan2(st['fw'][1], st['fw'][0]) + math.radians(DEFL_CAM[1])
        for a in range(3): e.wf(EYE + 4 * a, p[a] + (DEFL_CAM[0] * math.cos(a_), DEFL_CAM[0] * math.sin(a_), DEFL_CAM[2])[a])
    f = 40.0
    if ph == 'B':                   # Luke turned round (yaw written every frame); palace.st has a wall at his back
        st.setdefault('yawB', (e.rf(h + 0x8C) + 180.0) % 360.0); e.wf(h + 0x8C, st['yawB']); e.wf(h + 0x14, st['yawB'])
    g, p0, fw = st['g'], st['p0'], st['fw']
    gp = [p0[0] + f * fw[0], p0[1] + f * fw[1], p0[2]]
    u = [p0[0] - gp[0], p0[1] - gp[1]]; l = math.hypot(*u); u = [u[0] / l, u[1] / l]
    yaw = math.degrees(math.atan2(-u[0], u[1])) % 360
    put(g, gp, yaw)
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    for a, v in enumerate((c, s_, 0)): e.wf(g + 0x20 + 4 * a, v)
    for a, v in enumerate((-s_, c, 0)): e.wf(g + 0x30 + 4 * a, v)
    d = 100.0 - e.rf(h + HP)
    if d > 0.01: st['dmg'][ph] += d
    if os.environ.get('SABER_DBG') == '2' and ph == 'A':   # every VI: the bolts and area shots near him, printed when hurt
        pool, hp_, now = r32(0x80112E60), V(h, 0x50), []
        for i in range(40):
            bo = pool + 0xB8 * i
            q = V(bo, 0x50)
            if r32(bo + 0x60) & 0x10000 and ((q[0] - hp_[0]) ** 2 + (q[1] - hp_[1]) ** 2) ** 0.5 < 45:
                now.append(('Blst', i, hex(r32(bo + 0x60)), [round(x - y, 2) for x, y in zip(q, hp_)],
                            [round(e.rf(bo + 0xA0 + 4 * j), 3) for j in range(3)], round(e.rf(bo + 0x70), 1), round(e.rf(bo + 0xB4), 2),
                            'him' if r32(bo + 0x64) == h else hex(r32(bo + 0x64))))
        xr = 0x80112E68
        for i in range(r32(xr + 8)):
            x = r32(xr + 0x10) + r32(xr + 0xC) * i
            q = V(x, 0x50)
            if r32(x + 0x60) >> 16 and ((q[0] - hp_[0]) ** 2 + (q[1] - hp_[1]) ** 2) ** 0.5 < 15:
                now.append(('Expl', i, hex(r32(x + 0x60)), [round(a - b_, 2) for a, b_ in zip(q, hp_)], 'kind', r32(x + 0x64) >> 16,
                            'dmg', round(e.rf(x + 0x84), 1), 'scale', round(e.rf(x + 0xD4), 2), 'sender', hex(r32(x + 0x88))))
        if d > 0.01:
            print(f'  k {k} HURT {d:.1f} facing {[round(e.rf(h + 0x30 + 4 * j), 3) for j in range(3)]} dt {e.rf(0x8018E998) if 0 else struct.unpack(">d", struct.pack(">II", r32(0x8018E998), r32(0x8018E99C)))[0]:.4f} move {r32(S["g_saber_move"]):#x} deflects {r32(S["g_saber_deflects"])}', flush=True)
            for x in st.get('prev', []): print('    before', x, flush=True)
            for x in now: print('    now   ', x, flush=True)
        st['prev'] = now
    if d > 0.01 and os.environ.get('SABER_DBG') == '1' and ph == 'A':
        pool = r32(0x80112E60); hp_ = V(h, 0x50)
        near = []
        for i in range(40):
            bo = pool + 0xB8 * i
            if not r32(bo + 0x60) & 0x10000: continue
            q = V(bo, 0x50); ow = r32(bo + 0x64)
            dd = ((q[0] - hp_[0]) ** 2 + (q[1] - hp_[1]) ** 2) ** 0.5
            if dd < 40:
                fwd = [e.rf(h + 0x30), e.rf(h + 0x34)]; op = V(ow, 0x50) if ow else hp_
                u = [op[0] - hp_[0], op[1] - hp_[1]]; lu = max(1e-6, (u[0] ** 2 + u[1] ** 2) ** 0.5); lf = max(1e-6, (fwd[0] ** 2 + fwd[1] ** 2) ** 0.5)
                ang = math.degrees(math.acos(max(-1, min(1, (u[0] * fwd[0] + u[1] * fwd[1]) / lu / lf))))
                near.append((hex(ow), 'guard' if ow == g else ('him' if ow == h else hex(r32(ow)) if ow else '-'), round(dd, 1),
                             f'shooter {lu:.1f} off at {ang:.0f} deg from his facing, dz {op[2] - hp_[2]:.1f}'))
        print(f'  k {k} damage {d:.1f} bolts {near} deflects {r32(S["g_saber_deflects"])} move {r32(S["g_saber_move"]):#x}', flush=True)
    e.wf(h + HP, 100.0)
    if k == 20 + 2 * DEFL_T:
        nd = {x: (st['defl'].get('B', 0) if x == 'A' else r32(S['g_saber_deflects'])) - st['defl'][x] for x in 'AB'}
        gl = {'A': st['ghp']['A'] - st['ghp']['B'], 'B': st['ghp']['B'] - e.rf(g + TROP_HP)}
        check('facing it: its bolts are turned back and hurt it', nd['A'] >= 2 and gl['A'] > 0,
              f"turned {nd['A']}, its health lost {gl['A']:.1f}")
        check("facing it: Luke's health unchanged", st['dmg']['A'] == 0, f"damage {st['dmg']['A']:.1f}")
        check('his back to it: its bolts hit him, none turned', st['dmg']['B'] > 0 and nd['B'] == 0,
              f"damage {st['dmg']['B']:.1f}, turned {nd['B']}, its health lost {gl['B']:.1f}")
        finish_flash(h, nd)
        tw = st.get('tw', [])
        check(f'facing it: each turned bolt grows out of the blade (tail - contact along it >= {-TAIL_SLACK} over {TAIL_VIS} VIs)',
              len(tw) == nd['A'] and all(t['least'] >= -TAIL_SLACK for t in tw),
              f"bolts {len(tw)} of {nd['A']}, least {[round(t['least'], 3) for t in tw]} "
              f"(overall {min((t['least'] for t in tw), default=None)}), VIs seen {[t['seen'] for t in tw]}")
        bt = blade_turns('A'); dd = [x[2] for x in bt]
        check(f'facing it: each turn at the blade (within {BLADE_MAX:.3f} at its flash or the two VIs after)',
              bt and all(x is not None and x <= BLADE_MAX for x in dd),
              f"distances {[None if x is None else round(x, 3) for x in dd]}, holds {r32(S['g_saber_holds'])} "
              f"(s {[round(x, 3) for x in st.get('holds', {}).values()]})")
        print('B facing', [round(e.rf(h + 0x30), 2), round(e.rf(h + 0x34), 2)], 'start facing', [round(x, 2) for x in fw], flush=True)
        e.stop()
    if STILL and (10 <= k < 14 or 40 <= k < 44): return BTN['L']   # the camera binding: follow -> first person -> drop
    return 0


EXPL = 0x80112E68                       # the Expl class record: +8 count, +0xC size, +0x10 head
FLASH = (4, 0x2122, 0xC8FFC8FF)         # saber.c's flash: kind, flags, RGBA
FLASH_OFF = 0.06                        # its object from g_saber_flash, at most: the game's Expl placement (0x80063E4C)
                                        # puts it 0.05 (0x800EB414) toward the eye (measured 0.035 on its largest axis)
DEFL_CAM = (9.0, 60.0, 4.5)             # STILL: the eye: out, deg from his facing, up
FLASH_VIS = 5                           # STILL: stills a flash, one a VI from the one it is counted on (it lives ~4)


ARM_PATH = (18, 17, 10, 9, 8, 7, 6)     # saber.c hand_world's chain: model, pelvis, spine, chest, shoulder, forearm, hand
BLADE_VIS = 8                           # VIs a flash's blade distance is followed from the one it is counted on


def hand_world(h):
    """saber.c hand_world in the harness: his right hand's world matrix (rows x, y, z, translation; 12 floats) or None"""
    blk = S['g_blk']
    pn, m = r32(h + 0x24C), r32(blk + 0x38 + 0xA0 * 18 + 8)
    ok = lambda a: 0x80000000 <= a < 0x80800000
    if not ok(pn) or not ok(m) or r32(pn + 0xC) > 8: return None
    x = 0
    for i in range(r32(pn + 0xC)):
        c = r32(r32(pn + 0x10) + 4 * i)
        if not ok(c) or r32(c) >> 28 != 0xD or r32(c + 0xC) > 8: continue
        if any(r32(r32(c + 0x10) + 4 * j) == m for j in range(r32(c + 0xC))): x = c
    if not x: return None
    nodes = [pn, x] + [r32(blk + 0x38 + 0xA0 * b + 8) for b in ARM_PATH]
    w = [1.0 if (i % 4 == 0 and i < 9) else 0.0 for i in range(12)]
    for n in nodes:
        if not ok(n): return None
        L = [e.rf(n + 0x14 + 4 * i) for i in range(9)]; t = [e.rf(n + 0x38 + 4 * i) for i in range(3)]
        r = [L[3 * i] * w[j] + L[3 * i + 1] * w[3 + j] + L[3 * i + 2] * w[6 + j] for i in range(3) for j in range(3)]
        r += [t[0] * w[j] + t[1] * w[3 + j] + t[2] * w[6 + j] + w[9 + j] for j in range(3)]
        w = r
    return w


def blade_seg(h):
    """the blade's foot (the emitter) and tip in the world (saber_model's hand-frame points through hand_world)"""
    w = hand_world(h)
    if w is None: return None
    lk = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'luke')
    if lk not in sys.path: sys.path.insert(0, lk)
    import saber_model as sm_
    a = sm_.AXIS / (sum(x * x for x in sm_.AXIS) ** 0.5)
    pts = [sm_.GRIP + a * sm_.HILT_FRONT, sm_.tip_point()[0]]
    return [[q[0] * w[j] + q[1] * w[3 + j] + q[2] * w[6 + j] + w[9 + j] for j in range(3)] for q in pts]


def blade_dist(h, c):
    """(distance of c from the blade's segment, its place along the blade 0 foot .. 1 tip) or (None, None)"""
    sg = blade_seg(h)
    if not sg: return None, None
    F, T = sg; d = [T[j] - F[j] for j in range(3)]; dd = sum(x * x for x in d)
    u = max(0.0, min(1.0, sum((c[j] - F[j]) * d[j] for j in range(3)) / dd)) if dd > 0 else 0.0
    return sum((c[j] - F[j] - d[j] * u) ** 2 for j in range(3)) ** 0.5, u


def blade_track(h, tag):
    """each new flash (g_saber_flashes up): the crossing (g_saber_flash), then per VI for BLADE_VIS VIs the parry's
    weight and the crossing's distance from the blade (and its place along it); printed per flash: 'BLADE ...'"""
    fl = r32(S['g_saber_flashes'])
    tr = st.setdefault('btrack', {'n': fl, 'open': []})
    if fl > tr['n']:
        c = [e.rf(S['g_saber_flash'] + 4 * j) for j in range(3)]
        hp_, f_ = V(h, 0x50), [e.rf(h + 0x30), e.rf(h + 0x34)]
        fwd = (c[0] - hp_[0]) * f_[0] + (c[1] - hp_[1]) * f_[1]     # the crossing ahead of him (the grid's plane: 2.25)
        tr['open'].append({'c': c, 'v': s32(r32(S['g_saber_parry_v'])), 'rows': [], 'tag': tag, 'n': fl, 't': clock(), 'fwd': fwd})
        sg = blade_seg(h)
        if sg and 'blade_len' not in st:
            st['blade_len'] = sum((sg[1][j] - sg[0][j]) ** 2 for j in range(3)) ** 0.5
            print(f"BLADE length (emitter to tip, world) {st['blade_len']:.2f}", flush=True)
    tr['n'] = fl
    hist = st.setdefault('phist', []); hist.append(V(h, 0x50)); del hist[:-4]
    if tr['open'] and not tr['open'][-1]['rows'] and os.environ.get('BLADE_MOVED'):
        o = tr['open'][-1]      # BLADE_MOVED=1: the crossing carried along his own move over the last 1..3 VIs
        hp_, f_ = hist[-1], [e.rf(h + 0x30), e.rf(h + 0x34)]
        rel = lambda q: [round((q[0] - hp_[0]) * f_[0] + (q[1] - hp_[1]) * f_[1], 2),
                         round((q[0] - hp_[0]) * f_[1] - (q[1] - hp_[1]) * f_[0], 2), round(q[2] - hp_[2], 2)]
        o['rel'] = (rel(o['c']), [rel(q) for q in (blade_seg(h) or [])])   # (forward, right, up): the crossing, the blade
        o['moved'] = [(round(((hist[-1][0] - q[0]) ** 2 + (hist[-1][1] - q[1]) ** 2) ** 0.5, 2),
                       round(float(blade_dist(h, [o['c'][j] + hist[-1][j] - q[j] for j in range(3)])[0] or -1), 2))
                      for q in hist[-2::-1]]
    for o in list(tr['open']):
        d, u = blade_dist(h, o['c'])
        o['rows'].append((round(e.rf(S['g_saber_parry_w']), 2), None if d is None else round(float(d), 2), None if u is None else round(float(u), 2)))
        if len(o['rows']) >= BLADE_VIS:
            hp_ = V(h, 0x50)
            print(f"BLADE {o['tag']} flash {o['n']} v {o['v']} crossing up {o['c'][2] - hp_[2]:.2f}: (w, dist, along) "
                  f"{o['rows']}" + (f" moved (step, dist) {o['moved']} crossing / blade foot, tip (fwd, right, up) {o['rel']}" if 'moved' in o else ''), flush=True)
            st.setdefault('bdone', []).append(o); tr['open'].remove(o)


BLADE_MAX = 0.710 + 0.25                # a turn's crossing from the blade, at most: the grid's static meet max over both
                                        # layers (saber_moves --parry's last line, 0.710: the 1.5 layer's) + 0.25 (the
                                        # blend in the game, the bolt's own sweep)
HOLD_LONGEST = 0.1                      # s: saber.c HOLD_MAX, the longest a bolt is held for its parry


def blade_min(o):
    """a flash's blade distance at the turn: the least over the flash's VI and the two after it"""
    d = [r[1] for r in o['rows'][:3] if r[1] is not None]
    return min(d) if d else None


def blade_turns(tags):
    """[(tag, game time, distance at the turn, the crossing ahead of him)] of the flashes followed in the phases tags"""
    tr = st.get('btrack', {'open': []})
    return [(o['tag'], o['t'], blade_min(o), o['fwd']) for o in st.get('bdone', []) + tr['open'] if o['tag'] in tags]




def hold_watch(ph):
    """each hold (g_saber_holds up): its length, g_saber_hold_t's largest value until the next one, and its phase"""
    n, t = r32(S['g_saber_holds']), e.rf(S['g_saber_hold_t'])
    hd = st.setdefault('holds', {})
    if n: hd[n] = max(hd.get(n, 0.0), t); st.setdefault('hold_ph', {}).setdefault(n, ph)


def flash_watch(h, ph):
    """a new flash (g_saber_flashes up): the first one's object found and followed to its end; stills of the first 3"""
    fl = r32(S['g_saber_flashes'])
    if fl > st['flprev'] and ph == 'A':
        if 'first' not in st:
            pl = [e.rf(S['g_saber_flash'] + 4 * j) for j in range(3)]
            obs = []
            for i in range(r32(EXPL + 8)):
                x = r32(EXPL + 0x10) + r32(EXPL + 0xC) * i
                if r32(x + 0x88) == h and e.r16(x + 0x64) == FLASH[0]:
                    obs.append((max(abs(a - b_) for a, b_ in zip(V(x, 0x50), pl)), x))
            x = min(obs)[1] if obs else 0
            hp_ = V(h, 0x50)
            st['first'] = {'pl': pl, 'x': x, 'n': len(obs), 'd': min(obs)[0] if obs else None,
                           'across': ((pl[0] - hp_[0]) ** 2 + (pl[1] - hp_[1]) ** 2) ** 0.5, 'up': pl[2] - hp_[2],
                           'flags': e.r16(x + 0x62) if x else None, 'dmg': e.rf(x + 0x84) if x else None,
                           'rgba': r32(x + 0x124) if x else None, 't0': clock(), 'end': None, 'scales': []}
        if STILL and st['fshots'] < 3: st['fshots'] += 1; st['burst'] = FLASH_VIS
    st['flprev'] = fl
    if st.get('burst'): e.shot(); st['burst'] -= 1
    f = st.get('first')
    if f and f['x'] and f['end'] is None:
        if e.r16(f['x'] + 0x60) == 0: f['end'] = clock() - f['t0']
        else: f['scales'].append(round(e.rf(f['x'] + 0xD4), 2))


BLST_POOL, BLST_N, BLST_SIZE = 0x80112E60, 40, 0xB8   # the Blst objects: the pool's head pointer, count, size
TAIL_VIS = 10                           # VIs a turned bolt's tail is followed from its flash
TAIL_SLACK = 0.05                       # the tail behind the contact, at most


def turn_watch(h, ph):
    """each new flash in phase A: the bolt of his (sender +0x64) nearest it, not followed already, followed TAIL_VIS VIs: the least (tail +0x50 -
    c) . dir (c the flash's place, g_saber_flash; dir +0x78 normalised) while it lives and is his"""
    tw = st.setdefault('tw', [])
    fl = r32(S['g_saber_flashes'])
    if fl > st.get('tw_prev', fl) and ph == 'A':
        c = [e.rf(S['g_saber_flash'] + 4 * j) for j in range(3)]
        busy = {t['b'] for t in tw if t['left'] > 0}
        pool = r32(BLST_POOL)
        his = [(sum((x - y) ** 2 for x, y in zip(V(b, 0x50), c)), b) for b in (pool + BLST_SIZE * i for i in range(BLST_N))
               if r32(b + 0x60) & 0x10000 and r32(b + 0x64) == h and b not in busy]
        if his: tw.append({'b': min(his)[1], 'c': c, 'left': TAIL_VIS, 'least': float('inf'), 'seen': 0})
    st['tw_prev'] = fl
    for t in tw:
        if t['left'] <= 0: continue
        t['left'] -= 1
        b = t['b']
        if not (r32(b + 0x60) & 0x10000 and r32(b + 0x64) == h): t['left'] = 0; continue
        v = V(b, 0x78); n = sum(x * x for x in v) ** 0.5
        if n < 1e-6: continue
        a = sum((x - y) * z / n for x, y, z in zip(V(b, 0x50), t['c'], v))
        t['least'] = min(t['least'], a); t['seen'] += 1
        if os.environ.get('TAIL_DBG'):
            print(f"TAIL bolt {b:#x} VI {TAIL_VIS - t['left']} tail-c {a:.2f} head {sum(x * x for x in V(b, 0x84)) ** 0.5:.2f} "
                  f"len {e.rf(b + 0x70):.1f} speed {e.rf(b + 0x74):.1f}", flush=True)


def finish_flash(h, nd):
    fa = st['fl']['B'] - st['fl']['A']; fb = r32(S['g_saber_flashes']) - st['fl']['B']; f = st.get('first')
    check('facing it: a flash for each turned bolt', fa == nd['A'] and fa > 0, f"flashes {fa}, turned {nd['A']}")
    ok = bool(f and f['x'] and f['d'] is not None and f['d'] <= FLASH_OFF and (f['flags'], f['rgba']) == FLASH[1:] and f['dmg'] == 0)
    check('the first flash: his kind-4 object, flags 0x2122, damage 0, RGBA 0xC8FFC8FF, at g_saber_flash', ok,
          f"objects {f and f['n']}, off {f and f['d']}, flags {f and f['flags'] is not None and hex(f['flags'])}, damage {f and f['dmg']}, "
          f"rgba {f and f['rgba'] is not None and hex(f['rgba'])}")
    check('the first flash by him: within 6.0 across, 0..7 above his feet',
          bool(f) and f['across'] <= 6.0 and 0 <= f['up'] <= 7, f and f"across {f['across']:.2f}, up {f['up']:.2f}, at {[round(x, 2) for x in f['pl']]}")
    check('the first flash ends within 0.5 s', bool(f) and f['end'] is not None and f['end'] <= 0.5,
          f and f"state 0 after {f['end']} s, scales {f['scales']}")
    check('his back to it: no flash', fb == 0, f"flashes {fb}")
    if STILL:
        import glob
        new = sorted((x for x in glob.glob(os.path.join(e.shot_dir, '*.png')) if os.path.basename(x) not in st['shots0']),
                     key=os.path.getmtime)
        for i, x in enumerate(new[:3 * FLASH_VIS]):
            out = os.path.splitext(STILL)[0] + f'_flash{i // FLASH_VIS + 1}_{i % FLASH_VIS}.png'
            shutil.copy(x, out); print('still', out, flush=True)


def boss_case(k, h):
    """om_ig88.st: IG-88 (class Boss) held BOSS_AT (5.5) in front of Luke at his floor height; a three-press combo;
    then held BOSS_FAR (9.5: >= 6 from every hit point) and a second combo"""
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 6)
        p = r32(0x80112830); st['boss'] = 0
        for i in range(80):
            rec = r32(p + 4 * i)
            if not rec: break
            if r32(rec) == 0x426F7373: st['boss'] = r32(rec + 0x10)
        fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = (fw[0] ** 2 + fw[1] ** 2) ** 0.5; st['fw'] = [fw[0] / l, fw[1] / l]
        st['moves'] = {'A': [], 'B': []}; st['hp'] = {'A': [], 'B': []}; st['hits'] = []; st['snd'] = 0
        st['diff'] = e.r16(0x8011282A); st['drops'] = []
    if k < 9 or not st.get('boss'): return 0
    ph = 'A' if k < 280 else 'B'
    b = st['boss']; p = V(h, 0x50); fw = st['fw']
    d = float(os.environ.get('BOSS_AT', 5.5)) if ph == 'A' else float(os.environ.get('BOSS_FAR', 9.5))
    # at his floor height: om_ig88.st has IG-88 at z 5.95 on a raised floor, Luke at -1.52; kept at his own z the
    # shot's height span missed his (the area send tests it): BOSS_Z=own keeps it so
    st.setdefault('bz', e.rf(b + 0x58) if os.environ.get('BOSS_Z') == 'own' else p[2])
    for a, v in enumerate((p[0] + d * fw[0], p[1] + d * fw[1], st['bz'])): e.wf(b + 0x50 + 4 * a, v); e.wf(b + 0x08 + 4 * a, v)
    m = struct.unpack('<i', struct.pack('<I', r32(S['g_saber_move'])))[0]
    mv = st['moves'][ph]
    if not mv or mv[-1] != m: mv.append(m); st['hp'][ph].append(e.rf(b + 0x5C4))
    ht = [e.rf(S['g_saber_hit'] + 4 * i) for i in range(4)]
    if any(ht) and ht != st.get('lh'):
        st['lh'] = ht; st['hits'].append((ph, k, round(((ht[0] - e.rf(b + 0x50)) ** 2 + (ht[1] - e.rf(b + 0x54)) ** 2) ** 0.5, 2)))
    if queued(ID_HIT): st['snd'] += 1
    hp_now, free = e.rf(b + 0x5C4), sum(1 for x in slots() if x[0] == 0xFFFFFFFF)
    if hp_now < st.get('hp_last', hp_now) - 0.01: st['drops'].append([k, free])   # a hit: the queue's free slots then
    elif st['drops'] and k - st['drops'][-1][0] <= 1: st['drops'][-1].append(free)   # saber.c asks in that frame's overlay
    st['hp_last'] = hp_now
    if os.environ.get('SABER_DBG') and (k % 2 == 0 or os.environ.get('SABER_DBG') == '2'): print(f'  k {k} {ph} move {m} hp {e.rf(b + 0x5C4):.1f} +0x748 {e.rf(b + 0x748):.2f} state {r32(b + 0x584)} r {e.rf(b + 0x60):.2f} 6f8 {e.rf(b + 0x6F8):.2f} 5e0 {e.rf(b + 0x5E0):.2f} 5e4 {e.rf(b + 0x5E4):.2f} deb80 {r32(0x800DEB80):#x} q {[hex(x[1]) for x in slots() if x[0] != 0xFFFFFFFF]} luke {[round(x, 2) for x in V(h, 0x50)]} fw {e.rf(h + 0x30):.2f},{e.rf(h + 0x34):.2f} hp {e.rf(h + HP):.1f} ctl {r32(r32(0x800E1328 + 4)):#x} t {e.rf(0x800E1328):.2f} press {r32(S["g_press"]) if "g_press" in S else -1} cur,next {[r32(int(os.environ.get("SABER_M", "0"), 16) + 4 * i) for i in (0, 1)] if os.environ.get("SABER_M") else "-"} mt {e.rf(int(os.environ.get("SABER_M", "0"), 16) + 12) if os.environ.get("SABER_M") else 0:.3f} fl {r32(h + 0x74):#x} defl {r32(S["g_saber_deflects"])}', flush=True)
    if k == 540:
        for x in 'AB': st['hp'][x].append(e.rf(b + 0x5C4))
        hpA = st['hp']['A']; drops = [round(u - w, 1) for u, w in zip(hpA, hpA[1:]) if u - w > 0.01]
        want = round(min(170 * {1: 0.4, 3: 1.4}.get(st['diff'], 0.4), BOSS_CAP.get(st['diff'], 45.0)), 1)
        seqA = [x for x in st['moves']['A'] if x >= 0]
        check('in reach: every swing (sw1, sw2, sw3 among them) takes IG-88 one hit (170 x his scale, capped)',
              all(x in seqA for x in (0, 1, 2)) and drops == [want] * len(seqA),
              f"moves {st['moves']['A']}, health {hpA}, drops {drops} (want {want}, difficulty {st['diff']})")
        hpB = st['hp']['B']
        check('6 units off: a combo takes nothing', len([x for x in st['moves']['B'] if x >= 0]) >= 3 and abs(hpB[0] - hpB[-1]) < 0.01,
              f"moves {st['moves']['B']}, health {hpB[0]:.1f} -> {hpB[-1]:.1f}")
        full = [d for d in st['drops'] if d[0] < 280]
        busy = full and all(max(d[1:]) == 0 for d in full)
        check('his hit plays the hit sound (or the queue is full at each hit)', st['snd'] > 0 or busy,
              f"VIs with it queued {st['snd']}" + ('' if st['snd'] else
              f", every queue slot busy at each hit: {bool(busy)} (VI, free slots then and 1 VI on: {full})"))
        print('hits (phase, VI, distance to IG-88):', st['hits'], 'health drops (VI, free queue slots):', st['drops'], flush=True)
        e.stop()
    k0 = 20 if ph == 'A' else 290
    if not k0 <= k < k0 + 240 or mv.count(2): return 0
    if all(x < 0 for x in mv): return BTN['B'] if (k - k0) % 4 < 2 else 0   # the press that starts sw1
    if m in (0, 1):                 # from the playing swing's cut (saber.c queues a press from there): tapped (2 VIs on, 2
        t = sabr_tab()              # off) until the next starts: one press held from the cut was lost when that VI read him
                                    # (its descriptor the stepping block's or, IG-88 in the step, the in-place one's)
        d = r32(0x800E1328 + 4)     # airborne (+0x74 0x08000000: sw1's step on om_ig88.st's floor, the game time drifting
                                    # with the patch's frame cost; build sp4 2026-11-16)
        return BTN['B'] if r32(d) in (0x70 + m, 0x70 + SW_INPL + m) and e.rf(0x800E1328) >= e.rf(t + 40 + 0x2C * m + 12) and k % 4 < 2 else 0
    return 0


def sabr_tab():
    """The image's SWN2 table (SABR +12): per move at +40 + 0x2C i {tag, keys, keys/s, cut s, reach, damage, step,
    tracks, link s, step from s, step to s}"""
    litn = GUARD + 8 + 8 * 19 + 12
    at = litn + 12 + 4 * (1 + r32(litn + 4)) * r32(litn + 8)
    return r32(at + 12)


# ---- Guri's hold ----
PH_GRAB, PH_UP, PH_COOL = 2, 9, 10       # melee.c's phases (common.h)


def melee_case(k, h):
    """palace.st, t_melee's setup: Luke 6 ahead of Trop 0 facing her, the saber out, g_melee_on; the others held idle"""
    if k == 9: e.w32(S['g_guard_on'], 2); set_wid(h, 6)
    if k == 30:
        g = trops()[0]; st['g'] = g
        p = V(g, 0x50); fw = (e.rf(g + 0x30), e.rf(g + 0x34))
        import math
        yaw = math.degrees(math.atan2(fw[0], -fw[1]))
        q = (p[0] + 6.0 * fw[0], p[1] + 6.0 * fw[1], p[2])
        for a in range(3): e.wf(h + 0x08 + 4 * a, q[a]); e.wf(h + 0x50 + 4 * a, q[a])
        e.wf(h + 0x14, yaw); e.wf(h + 0x8C, yaw)
        e.w32(S['g_melee_on'], 1)
    if k <= 30: return 0
    for o in trops():
        if o != st['g'] and r32(o) == 0x54726F70: e.w32(o + TROP_STATE, 0); e.wf(o + TROP_TIMER, 100.0)
    ph, m = r32(S['g_melee_phase']), sabr()
    t = struct.unpack('>d', struct.pack('>II', r32(0x8018E9A8), r32(0x8018E9AC)))[0]   # the game clock
    hd = hand(); lit = m in hd
    if lit and 'slot' not in st: st['slot'] = hd.index(m)   # the weapon's slot in the hand's list of ours
    hum = [s_ for s_ in queued(ID_HUM, 1) if s_[4] > 0]
    st.setdefault('wid', set()).add(wid(h))
    if 'grab' not in st and PH_GRAB <= ph <= PH_UP: st['grab'] = (k, t)
    if 'grab' in st and 'up_end' not in st and not (PH_GRAB <= ph <= PH_UP): st['up_end'] = k
    if 'grab' in st and 'up_end' not in st:
        g0 = st['grab'][0]
        if k - g0 <= 5 and queued(ID_OFF): st.setdefault('off_at', k - g0)
        if not lit and 'dark_at' not in st: st['dark_at'] = k - g0
        if k - g0 >= 5: st['lit_in_hold'] = st.get('lit_in_hold', 0) + lit
        if k - g0 >= 5 and hd[st.get('slot', 0)]: st['filled'] = hd[st.get('slot', 0)]   # the slot empty: no blaster either
        if not hum and 'hum_gone' not in st: st['hum_gone'] = t - st['grab'][1]
        if hum and 'hum_gone' in st: st['hum_back_in_hold'] = 1
    if 'up_end' in st:
        d = k - st['up_end']
        if d <= 5 and queued(ID_ON): st.setdefault('on_at', d)
        if lit: st.setdefault('lit_at', d)
        if d == 30:
            check('the grab: the blade leaves the hand within 5 frames, stays out through the hold',
                  st.get('dark_at', 99) <= 5 and not st.get('lit_in_hold'), f"dark at +{st.get('dark_at')} lit frames {st.get('lit_in_hold', 0)}")
            check('in the hold the slot is empty (no blaster either)', 'slot' in st and 'filled' not in st,
                  f"slot {st.get('slot')} filled with {st.get('filled', 0):#x}")
            check("the grab: 'off' queued within 5 frames", st.get('off_at') is not None, f"+{st.get('off_at')}")
            check("the hum's slot freed or silent <= 1.0 s after the grab, not asked again in the hold",
                  st.get('hum_gone', 9) <= 1.0 and not st.get('hum_back_in_hold'), f"{st.get('hum_gone')} s")
            check('the weapon id stays 6', st['wid'] == {6}, f"ids {sorted(st['wid'])}")
            check("the get-up's end: 'on' queued and the blade back within 5 frames", st.get('on_at') is not None
                  and st.get('lit_at', 99) <= 5, f"on +{st.get('on_at')} lit +{st.get('lit_at')}")
            e.stop()
    if k > 3000: check('the combo ran to its end', False, f"phase {ph}"); e.stop()
    return 0


# ---- the two-handed hold ----
HOLD_PHASES = (('stand', 0, 0, 0, ('Sstn',)), ('walk', 0, 40, 0, ('mosy',)), ('run', 0, 80, 0, ('trot',)),
               ('strafe', BTN['Z'], 0, 80, ('shfl', 'shfr')), ('stop', 0, 0, 0, ('Sstn',)))
# name, buttons, stick toward the camera, stick x, tags (stand: right after the draw; stop: standing after the strafe)
HOLD_T, HOLD_A = 60, 30                  # VIs a phase; the checks from its VI HOLD_A on
HOLD_CAM = (10.0, 35.0, 3.0)             # the eye: out, deg from his facing, up
VIEW, EYE = 0x800E0EEC, 0x8018DD98       # the on-foot view (4: drop); the drop camera's eye (entry 9's matrix +0x30)
ARM_BLK = 0xC18                          # saber.c BLOCK_SIZE: one g_mv copy
SW_BLOCKS = 7                            # saber.c MOVES: g_blk's blocks (sw1 sw2 sw3 spin, swp1 swp2 swp3), the last the
                                         # chain's tail the arm copies hang from
SW_INPL = 4                              # saber.c INPL: the first in-place block


def tag(b): return struct.pack('>I', r32(b)).decode('latin-1') if b else '-'


def hold_case(k, h):
    import math
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 4)
        f = math.atan2(e.rf(h + 0x34), e.rf(h + 0x30)) + math.radians(HOLD_CAM[1])
        st['off'] = (HOLD_CAM[0] * math.cos(f), HOLD_CAM[0] * math.sin(f), HOLD_CAM[2]); st['ph'] = {}
    if k < 9: return 0
    if os.environ.get('SABER_DBG') and k % 5 == 0:
        print(f"k {k} view {e.r16(VIEW)} id {wid(h)} pos {[round(x, 2) for x in V(h, 0x50)]} n {r32(S['g_mvn'])} "
              f"cur {tag(r32(h + 0x18C + 0x14) + 0x1C)} to {tag(r32(h + 0x18C + 0x18) + 0x1C)} flags {r32(h + 0x74):#x}", flush=True)
    i = (k - 90) // HOLD_T; j = (k - 90) % HOLD_T
    name = HOLD_PHASES[i][0] if 0 <= i < len(HOLD_PHASES) else ''
    if name == 'strafe':            # Z with a lock: a fake target 15 ahead of him at the phase's start
        if j == 0:
            make_fake(e); fw = (e.rf(h + 0x30), e.rf(h + 0x34)); p = V(h, 0x50)
            place_fake(e, p[0] + 15 * fw[0], p[1] + 15 * fw[1], p[2]); e.w32(S['g_test_skip_los'], 1)
        e.w32(S['g_lock'], FAKE)
    elif name == 'stop' and j == 0: e.w32(S['g_lock'], 0)
    if 10 <= k < 14 or 40 <= k < 44: return BTN['L']   # the camera binding: follow -> first person -> drop
    if 60 <= k < 64: return BTN['CU']                  # the Stunner -> the saber by the game's cycle
    if name in ('strafe', 'stop') and (2 <= j < 6 or 34 <= j < 38) and e.r16(VIEW) != 4:   # the drop view again (Z leaves it)
        return HOLD_PHASES[i][1] | BTN['L'], 0, 0
    if e.r16(VIEW) == 4:            # the eye out along his facing turned HOLD_CAM[1]: his front and hands
        p = V(h, 0x50); f = math.atan2(e.rf(h + 0x34), e.rf(h + 0x30)) + math.radians(HOLD_CAM[1])
        st['off'] = (HOLD_CAM[0] * math.cos(f), HOLD_CAM[0] * math.sin(f), HOLD_CAM[2])
        for a in range(3): e.wf(EYE + 4 * a, p[a] + st['off'][a])
    if k < 90: return 0
    if i >= len(HOLD_PHASES): finish_hold(); e.stop(); return 0
    name, btn, toward, sx, want = HOLD_PHASES[i]
    if j >= (45 if name == 'stop' else HOLD_A):
        mv0, n = S['g_mv'], r32(S['g_mvn'])
        cur, to = r32(h + 0x18C + 0x14), r32(h + 0x18C + 0x18)
        ph = st['ph'].setdefault(name, {'tags': set(), 'bad': [], 'ok': 0, 'n': 0})
        ok_blk = lambda b: mv0 <= b < mv0 + n * ARM_BLK and (b - mv0) % ARM_BLK == 0
        head = r32(S['g_blk'] + (SW_BLOCKS - 1) * ARM_BLK + 0x14)
        good = (wid(h) == 6 and struct.unpack('<i', struct.pack('<I', r32(S['g_saber_move'])))[0] == -1
                and head == mv0 and tag(mv0 + 0x1C) == 'Sstn' and ok_blk(cur) and tag(cur + 0x1C) in want)
        ph['tags'].add((tag(cur + 0x1C) if cur else '-', 'ours' if ok_blk(cur) else 'game', tag(to + 0x1C) if to else '-'))
        ph['n'] += 1; ph['ok'] += good
        if not good and len(ph['bad']) < 3:
            ph['bad'].append(f"VI {j}: id {wid(h)} move {r32(S['g_saber_move']):#x} head {head:#x} (g_mv {mv0:#x} {tag(mv0 + 0x1C)}) "
                             f"cur {cur:#x} {tag(cur + 0x1C) if cur else '-'} n {n}")
        if j == 50:
            fw = (e.rf(h + 0x30), e.rf(h + 0x34)); o = st['off']
            ph['facing'] = round(math.degrees(math.atan2(fw[0] * o[1] - fw[1] * o[0], fw[0] * o[0] + fw[1] * o[1])), 1)
            ph['view'] = e.r16(VIEW)
        if STILL and j == 50: e.shot(); st.setdefault('shots', []).append((k, name))
        if STILL and j == 53: hold_still(name)
    return btn, sx, toward          # straight ahead along core.c's lazy camera facing: palace.st's open side


def hold_still(name):
    import glob
    shots = sorted(glob.glob(os.path.join(e.shot_dir, '*.png')), key=os.path.getmtime)
    if shots:
        out = os.path.splitext(STILL)[0] + f'_{name}.png'; shutil.copy(shots[-1], out); st.setdefault('stills', []).append(out)


def finish_hold():
    for name, *_r, want in HOLD_PHASES:
        ph = st['ph'].get(name, {'tags': set(), 'bad': ['none sampled'], 'ok': 0, 'n': 0})
        check(f"{name}: the saber out, no swing, his block one of our arm copies ({' or '.join(want)})",
              ph['n'] and ph['ok'] == ph['n'], f"{ph['ok']}/{ph['n']} VIs; blocks (current, ours, blended to) "
              f"{sorted(ph['tags'])}; his facing {ph.get('facing')} deg from the camera's side, view {ph.get('view')} {ph['bad']}")
    if STILL and len(st.get('stills', [])) == len(HOLD_PHASES):
        from PIL import Image, ImageDraw
        ims = [Image.open(x).convert('RGB') for x in st['stills']]
        w, hh = ims[0].size; sheet = Image.new('RGB', (3 * w, 2 * hh))
        for n_, (im, (name, *_r)) in enumerate(zip(ims, HOLD_PHASES)):
            sheet.paste(im, ((n_ % 3) * w, (n_ // 3) * hh)); ImageDraw.Draw(sheet).text(((n_ % 3) * w + 8, (n_ // 3) * hh + 8), name, fill=(255, 255, 0))
        sheet.save(STILL); print('contact', STILL, flush=True)


# ---- the parry: the blade snapped into a bolt's path (saber.c parry_frame / saber_blst) ----
PARRY_END = 0.05 + 0.10 + 0.25 + 0.1     # s: PARRY_IN + PARRY_HOLD + PARRY_OUT + 0.1, the latest w is back to 0 after a turn
PARRY_PH = [('stills', 120), ('near', 600), ('jump', 1800), ('far', 900), ('run1', 210), ('quiet', 60), ('run0', 210)]
PARRY_CORNERS = ((20, 'low left'), (24, 'low right'), (35, 'high left'), (39, 'high right'))   # the PRY3 grid's far layer (5 x 4, 2.25)
FL_AIR = 0x08000000


def parry_ph(k):
    """the phase and its VI (one call per VI from VI 90); the jump phase ends early once two bolts are turned mid-jump"""
    if 'pi' not in st: st['pi'], st['pj'] = (0 if STILL else 1), -1
    st['pj'] += 1
    while st['pi'] < len(PARRY_PH):
        name, n = PARRY_PH[st['pi']]
        done = st['pj'] >= n or (name == 'jump' and st['pj'] >= 200 and sum(t['air'] for t in st['turns']) >= 2)
        if not done: return name, st['pj']
        st['pi'] += 1; st['pj'] = 0
    return None, 0


def pry_node(v):
    """the image's PRY3 node v (21 floats, layer-major; through the SABR record: +20 the SAR2 table, after its
    records), or None"""
    litn = GUARD + 8 + 8 * 19 + 12
    at = litn + 12 + 4 * (1 + r32(litn + 4)) * r32(litn + 8)
    if r32(at) != 0x53414252: return None
    t = r32(at + 20)
    if r32(t) != 0x53415232: return None
    t += 8 + 12 * r32(t + 4)
    if r32(t) != 0x50525933 or not 0 <= v < r32(t + 4) * r32(t + 8) * r32(t + 12): return None
    return [e.rf(t + 40 + 4 * (21 * v + i)) for i in range(21)]


def parry_force(v):
    """a parry forced through the exported g_parry (bolt, v, t, in, w, from, air, wa): held at w 1 (t at its in), its
    pose (g_parry_pose) the image's PRY3 node v"""
    P = S['g_parry']
    for i, a in enumerate(pry_node(v) or ()): e.wf(S['g_parry_pose'] + 4 * i, a)
    e.w32(P, 1); e.w32(P + 4, v); e.wf(P + 8, 0.15); e.wf(P + 12, 0.15); e.w32(P + 20, 0); e.wf(P + 24, -1.0)


def parry_case(k, h):
    import math
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 6)
        st['p0'] = V(h, 0x50); st['yaw0'] = e.rf(h + 0x8C)
        st['g'] = [o for o in trops() if e.rf(o + TROP_HP) > 0 and not r32(o + 0x74) & 0xF][0]
        e.w32(st['g'] + 0x74, r32(st['g'] + 0x74) | 0x20)
        st.update(turns=[], starts={}, wlog=[], runs={}, prev=r32(S['g_saber_deflects']), bolt=r32(S['g_parry']), stills=[])
    if k < 9: return 0
    if 10 <= k < 14 or 40 <= k < 44: return BTN['L']   # the camera binding: follow -> first person -> drop
    if e.r16(VIEW) == 4:            # the eye out along his facing turned HOLD_CAM[1]: his front and hands
        p = V(h, 0x50); f = math.atan2(e.rf(h + 0x34), e.rf(h + 0x30)) + math.radians(HOLD_CAM[1])
        for a in range(3): e.wf(EYE + 4 * a, p[a] + (HOLD_CAM[0] * math.cos(f), HOLD_CAM[0] * math.sin(f), HOLD_CAM[2])[a])
    g = st['g']; e.wf(g + TROP_HP, 1000.0)
    if k < 90: return 0
    name, j = parry_ph(k)
    if name is None: finish_parry(); e.stop(); return 0
    if j == 0 and name in ('run0', 'run1', 'jump'):     # back at the start place, facing as at first
        put(h, st['p0'], st['yaw0']); e.wf(h + 0x8C, st['yaw0'])
    fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = math.hypot(*fw); fw = [fw[0] / l, fw[1] / l]
    if j == 0 and name in ('run0', 'run1'): st['fw_run'] = fw
    p = V(h, 0x50) if name == 'jump' else st['p0']
    f = 77.0 if name == 'far' else 40.0
    if name in ('run0', 'run1'): fw, f = st['fw_run'], 60.0  # held still 60 ahead of the start: 12 ahead after his 2 s run
    gp = [p[0] + f * fw[0], p[1] + f * fw[1], st['p0'][2]]
    yaw = math.degrees(math.atan2(fw[0], -fw[1])) % 360
    put(g, gp, yaw)
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    for a, v in enumerate((c, s_, 0)): e.wf(g + 0x20 + 4 * a, v)
    for a, v in enumerate((-s_, c, 0)): e.wf(g + 0x30 + 4 * a, v)
    if name in ('quiet', 'run0'):   # the last phases: held idle it fires again only late, if at all
        e.w32(g + TROP_STATE, 0); e.wf(g + TROP_TIMER, 100.0)     # held idle: no bolts
    now, air = clock(), bool(r32(h + FLAGS) & FL_AIR)
    pv, pw = s32(r32(S['g_saber_parry_v'])), e.rf(S['g_saber_parry_w'])
    if name == 'stills':            # its own bolts still come (turned as ever): counted out of the checks
        st['prev'] = r32(S['g_saber_deflects']); st['bolt'] = 1
        if j // 30 < 4:
            v, nm = PARRY_CORNERS[j // 30]
            parry_force(v)
            if j % 30 == 20: e.shot()
            if j % 30 == 23: parry_still(nm.replace(' ', '_'))
        return 0
    if 'g_saber_flashes' in S: blade_track(h, name)
    hold_watch(name)
    bolt, d = r32(S['g_parry']), r32(S['g_saber_deflects']) - st['prev']
    st['prev'] += d
    if bolt and bolt != st['bolt'] and e.rf(S['g_parry'] + 12) > 0:   # a parry started (its in > 0) for a new bolt
        st['starts'][bolt] = (k, now, name, air and st.get('air_prev', False))
    st['bolt'] = bolt
    for _ in range(d):
        st['turns'].append(dict(k=k, t=now, ph=name, bolt=bolt, v=pv, own=r32(bolt + 0x64) == h if bolt else False,
                                air=air, start=st['starts'].get(bolt), fd=e.rf(S['g_parry'] + 32)))
    st['wlog'].append((k, now, pw, name))
    st['air_prev'] = air
    if os.environ.get('SABER_DBG') and (d or k % 30 == 0):
        print(f'  k {k} {name} turn {d} parry v {pv} w {pw:.2f} bolt {bolt:#x} air {air} pos {[round(x, 1) for x in V(h, 0x50)]} '
              f'guard state {r32(g + TROP_STATE)} flags {r32(g + 0x74):#x}', flush=True)
    if name in ('run0', 'run1'):
        r = st['runs'].setdefault(name, {})
        if j == 25: r['a'] = (now, V(h, 0x50))
        if 'a' in r and 'b' not in r and now >= r['a'][0] + 2.0: r['b'] = (now, V(h, 0x50))
        if name == 'run1' and STILL and 'shot' not in r and j > 40 and pw >= 0.9: e.shot(); r['shot'] = k
        if name == 'run1' and r.get('shot') == k - 3: parry_still('running')
        return (0, 0, 80) if j >= 15 else 0
    if name == 'jump': return BTN['A'] if j >= 20 and (j - 20) % 60 < 4 else 0   # the near guard firing, A every 60 VIs
    return 0


def parry_still(name):
    import glob
    shots = sorted(glob.glob(os.path.join(e.shot_dir, '*.png')), key=os.path.getmtime)
    if shots and STILL:
        out = os.path.splitext(STILL)[0] + f'_{name}.png'; shutil.copy(shots[-1], out); st['stills'].append((name, out))


def finish_parry():
    import math
    T, W = st['turns'], st['wlog']
    ground = [t for t in T if not t['air']]
    def w_after(k, n=2): return max((w for kk, _, w, _ in W if k <= kk <= k + n), default=0)
    bad1 = [t for t in ground if not (t['start'] and t['own'] and t['start'][0] <= t['k'])]
    check('every bolt turned on the ground has a parry started for it no later than its turn', ground and not bad1,
          f"{len(ground) - len(bad1)}/{len(ground)} (phases {sorted(set(t['ph'] for t in ground))}); "
          f"failing {[(t['k'], t['ph'], t['v'], t['own'], t['start']) for t in bad1[:4]]}")
    # one game frame is 2 VIs: a bolt first seen in the frame it is turned (point blank, within ~32 units: its first
    # update sweeps its 30 of length) starts its parry with in = PARRY_IN 0.05 there, so after one frame w is only
    # 0.75..0.87 and 1.0 after two: such a bolt gets 4 VIs, one seen a frame or more ahead 2
    def win(t): return 4 if t['start'] and t['start'][0] == t['k'] else 2
    low = [(t['k'], win(t), round(w_after(t['k'], win(t)), 2)) for t in ground if w_after(t['k'], win(t)) < 0.9]
    blank = sum(win(t) == 4 for t in ground)
    check('w >= 0.9 within 2 VIs after each turn (4 for a bolt first seen as it is turned)', ground and not low,
          f"min {min((w_after(t['k'], win(t)) for t in ground), default=0):.2f}; point blank {blank}/{len(ground)}; "
          f"min within 2 VIs {min((w_after(t['k']) for t in ground), default=0):.2f}; below {low[:6]}")
    leads = [round(t['t'] - t['start'][1], 3) for t in T if t['ph'] == 'far' and t['start']]
    check('the far guard (77): a parry starts >= 0.1 s before its turn', any(x >= 0.1 for x in leads),
          f"leads (s) {leads}; near ones {[round(t['t'] - t['start'][1], 3) for t in T if t['ph'] == 'near' and t['start']][:12]}")
    last = max((t['t'] for t in T if t['ph'] in ('near', 'far')), default=None)
    zero = next((tt for kk, tt, w, ph in W if last is not None and tt > last and w == 0 and ph in ('far', 'run1')), None)
    check('w back to 0 within PARRY_IN + HOLD + OUT + 0.1 s after the last turn', zero is not None and zero - last <= PARRY_END,
          f"{(zero - last) if zero is not None else None} s (limit {PARRY_END:.2f})")
    sp = {}
    for nm, r in st['runs'].items():
        if 'b' in r: sp[nm] = math.hypot(r['b'][1][0] - r['a'][1][0], r['b'][1][1] - r['a'][1][1]) / (r['b'][0] - r['a'][0])
    wr = max((w for _, _, w, ph in W if ph == 'run1'), default=0)
    nr = len([t for t in T if t['ph'] == 'run1'])
    check('running with the bolts: his speed >= 90% of the run without, a parry runs (w > 0.5)',
          len(sp) == 2 and sp['run1'] >= 0.9 * sp['run0'] and wr > 0.5,
          f"{sp.get('run1', 0):.3f} vs {sp.get('run0', 0):.3f} u/s ({100 * sp.get('run1', 0) / max(sp.get('run0', 1e-6), 1e-6):.1f}%), max w {wr:.2f}, turns {nr}")
    air = [t for t in T if t['air']]
    sa = [b for b, s_ in st['starts'].items() if s_[3]]
    check('in the air: bolts turned, no parry started', air and not sa,
          f"turns mid-jump {len(air)} (their parry v {[t['v'] for t in air][:8]}), parries started mid-jump {len(sa)}")
    bt = {round(x[1], 6): x[2:] for x in blade_turns(('near', 'jump', 'far', 'run1', 'quiet', 'run0'))}
    al = [(t['k'], t['ph']) + tuple(bt.get(round(t['t'], 6), (None, None))) for t in ground]
    gd = [x for x in al if x[3] is not None]
    check(f'each bolt turned on the ground: at the blade (within {BLADE_MAX:.3f} at its flash or the two VIs after)',
          gd and len(gd) == len(al) and all(d is not None and d <= BLADE_MAX for _, _, d, _ in gd),
          f"max {max((d for _, _, d, _ in gd if d is not None), default=None)}; followed {len(gd)} of {len(al)}; over "
          f"{[(k_, ph, round(d, 3)) for k_, ph, d, _ in gd if d is not None and d > BLADE_MAX]}")
    print('blade at the turns (VI, phase, distance, crossing ahead):',
          [(k_, ph, None if d is None else round(d, 3), None if f is None else round(f, 2)) for k_, ph, d, f in al], flush=True)
    print('run1 turns (VI, the parry\'s fd (blended at), distance, crossing ahead at the turn):',
          [(t['k'], round(t['fd'], 2)) + tuple(None if x is None else round(x, 3) for x in bt.get(round(t['t'], 6), (None, None)))
           for t in ground if t['ph'] == 'run1'], flush=True)
    hs = st.get('holds', {}); hn = {'near': list(st.get('hold_ph', {}).values()).count('near')}
    check(f'every hold <= {HOLD_LONGEST} s, one or more in near', hs and max(hs.values()) <= HOLD_LONGEST + 1e-6 and hn['near'] >= 1,
          f"holds {len(hs)} (near {hn['near']}), s {[round(x, 3) for x in hs.values()]}")
    print('turns', [(t['k'], t['ph'], t['v'], round(t['t'] - t['start'][1], 3) if t['start'] else None) for t in T], flush=True)
    if STILL and st['stills']:
        from PIL import Image, ImageDraw
        ims = [(Image.open(x).convert('RGB'), n_) for n_, x in st['stills']]
        w, hh = ims[0][0].size; sheet = Image.new('RGB', (3 * w, 2 * hh))
        for i, (im, n_) in enumerate(ims):
            sheet.paste(im, ((i % 3) * w, (i // 3) * hh)); ImageDraw.Draw(sheet).text(((i % 3) * w + 8, (i // 3) * hh + 8), n_, fill=(255, 255, 0))
        sheet.save(STILL); print('contact', STILL, flush=True)


# ---- one swing's flow: its timing, its step, its end ----
CTL = 0x800E1328                         # Dash's animation controller: +0 time, +4 the current descriptor
STATE_H = 0x18C                          # his animation state: +0 mode (3 blending), +0x14 current, +0x18 blended to
SETTLE = 0.8                             # s of game time a phase holds him at the start place before its first tap
FLOW_GUARD = 5.2                         # d: the guard this far ahead (his step meets its body: the combo's ~5.05)
FLOW_STILLS = (0.03, 0.12, 0.20, 0.25, 0.32, 0.43, 0.55, 0.68)   # d: the controller times of the stills
# name, the second tap (s after the swing's start, None: one tap), the stick from (s), Z from (s), the guard ahead,
# stills, the phase's length after the start
FLOW = (('a', None, None, None, None, False, 1.6), ('d_free', None, None, None, None, True, 1.2),
        ('d_guard', None, None, None, FLOW_GUARD, True, 1.2), ('b_run', None, 0.45, None, None, False, 1.4),
        ('b_z', None, None, 0.45, None, False, 1.4), ('c_same', 0.60, None, None, None, False, 2.0),
        ('c_chain', 0.30, None, None, None, False, 1.8), ('e_fwd', None, None, None, None, False, 1.6),
        ('e_right', None, None, None, None, False, 1.6), ('e_back', None, None, None, None, False, 1.6),
        ('a2', None, None, None, None, False, 1.6))
FLOW_E = {'e_fwd': (0, 80), 'e_right': (80, 0), 'e_back': (0, -80)}   # the stick (x, y) from the tap to the link


def clock(): return struct.unpack('>d', struct.pack('>II', r32(0x8018E9A8), r32(0x8018E9AC)))[0]
def s32(v): return struct.unpack('<i', struct.pack('<I', v))[0]


def flow_case(k, h):
    import math
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 4)
        st['p0'] = V(h, 0x50); st['yaw0'] = (e.rf(h + 0x14), e.rf(h + 0x8C))
        fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = math.hypot(*fw); st['fw'] = [fw[0] / l, fw[1] / l]
        f = math.atan2(st['fw'][1], st['fw'][0]) + math.radians(HOLD_CAM[1])
        st['off'] = (HOLD_CAM[0] * math.cos(f), HOLD_CAM[0] * math.sin(f), HOLD_CAM[2])
        st['tp'] = {o: V(o, 0x50) for o in trops() if not r32(o + 0x74) & 0xF}
        st['near0'] = min((math.hypot(q[0] - st['p0'][0], q[1] - st['p0'][1]) for q in st['tp'].values()), default=0)
        st['fl'] = {}; st['pi'] = -1; st['shots0'] = set(os.listdir(e.shot_dir))
    if k < 9: return 0
    p0, fw = st['p0'], st['fw']
    if e.r16(VIEW) == 4:                # the drop camera's eye out along his start facing turned HOLD_CAM[1]
        p = V(h, 0x50)
        for a in range(3): e.wf(EYE + 4 * a, p[a] + st['off'][a])
    if 10 <= k < 14 or 40 <= k < 44: return BTN['L']   # follow -> first person -> drop
    if 60 <= k < 64: return BTN['CU']                  # the Stunner -> the saber by the game's cycle
    if k < 90: return 0
    now = clock()
    if st['pi'] < 0 or now - st['ph'].get('t0', st['ph']['start'] + SETTLE + 2.0) >= FLOW[st['pi']][6]:   # no swing: on after 2 s
        st['pi'] += 1
        if st['pi'] >= len(FLOW): finish_flow(); e.stop(); return 0
        st['ph'] = st['fl'][FLOW[st['pi']][0]] = {'start': now, 'rows': [], 'taps': 0}
    name, tap2, stick, zat, gf, stills, dur = FLOW[st['pi']]
    ph = st['ph']
    for i, (o, q) in enumerate(st['tp'].items()):   # the guards held idle: in place, or one gf ahead facing him
        if gf and i == 0: q = [p0[0] + gf * fw[0], p0[1] + gf * fw[1], p0[2]]
        put(o, q, (st['yaw0'][1] + 180.0) % 360.0 if gf and i == 0 else e.rf(o + 0x14))
        e.w32(o + TROP_STATE, 0); e.wf(o + TROP_TIMER, 100.0); e.wf(o + TROP_HP, 100.0)
    if now - ph['start'] < SETTLE:      # held at the start place, facing as at the start, still
        for a in range(3): e.wf(h + 0x08 + 4 * a, p0[a]); e.wf(h + 0x50 + 4 * a, p0[a]); e.wf(h + 0x98 + 4 * a, 0.0)
        e.wf(h + 0x14, st['yaw0'][0]); e.wf(h + 0x8C, st['yaw0'][1])
        return 0
    m = s32(r32(S['g_saber_move'])); d = r32(CTL + 4); cid = r32(d) if d else -1
    cur, to = r32(h + STATE_H + 0x14), r32(h + STATE_H + 0x18)
    row = dict(t=now, m=m, cuts=r32(S['g_saber_cuts']), pos=V(h, 0x50), ct=e.rf(CTL), cid=cid, dtag=(dt := tag(d + 4) if d else '-'),
               mode=r32(h + STATE_H) & 0x7FFFFFFF, cur=tag(cur + 0x1C) if cur else '-', to=tag(to + 0x1C) if to else '-',
               fr=e.rf(S['g_blk'] + ARM_BLK * (max(m, 0) + (SW_INPL if dt.startswith('swp') else 0)) + 4), fw=(e.rf(h + 0x30), e.rf(h + 0x34)))
    ph['rows'].append(row)
    if 't0' not in ph and m == 0: ph['t0'] = now
    u = now - ph['t0'] if 't0' in ph else -1
    if stills and m == 0 and 'shot_t' not in ph: ph['shot_t'] = []
    if stills and m == 0 and len(ph['shot_t']) < len(FLOW_STILLS) and row['ct'] >= FLOW_STILLS[len(ph['shot_t'])]:
        e.shot(); ph['shot_t'].append(round(row['ct'], 3)); st.setdefault('still_names', []).append((name, row['ct']))
    btn, sx, sy = 0, 0, 0
    if 't0' not in ph or (tap2 is not None and tap2 <= u < tap2 + 0.07):
        btn |= BTN['B'] if ph['taps'] < 4 or 't0' in ph else 0
        ph['taps'] += 1
    if stick is not None and u >= stick: sy = 80
    if zat is not None and u >= zat: btn |= BTN['Z']
    if name in FLOW_E:                  # the stick from the tap's VI until sw1's link
        if 'link' not in st: st['link'] = e.rf(sabr_tab() + 40 + 32)
        if u < st['link']: sx, sy = FLOW_E[name]
    if os.environ.get('SABER_DBG'):
        print(f"{name} u {u:.3f} m {m} cuts {row['cuts']} ct {row['ct']:.3f} cid {cid:#x} mode {row['mode']} cur {row['cur']} "
              f"to {row['to']} fr {row['fr']:.2f} along {(row['pos'][0] - p0[0]) * fw[0] + (row['pos'][1] - p0[1]) * fw[1]:.3f} "
              f"vel {e.rf(h + 0x98):.2f},{e.rf(h + 0x9C):.2f} yaw {math.degrees(math.atan2(row['fw'][1], row['fw'][0])):.1f} "
              f"stick {sx},{sy} press {r32(S['g_press']) if 'g_press' in S else '-'}", flush=True)
    return btn, sx, sy


def flow_drift(p0):
    """the stick during a swing: per phase a / e_* / a2, from the swing's first update (g_saber_move 0) to the last
    update before sw1's link (the window core.c zeroes the stick's move and holds the turn in), his displacement (x, y)
    and the facing's turn (deg); drift = |displacement - a's|; checks: e_fwd's |displacement| against a's, e_right /
    e_back's turn and |displacement|"""
    import math
    link = st.get('link') or e.rf(sabr_tab() + 40 + 32)
    out = {}
    for nm in ('a', 'e_fwd', 'e_right', 'e_back', 'a2'):
        ph = st['fl'].get(nm, {}); t0 = ph.get('t0')
        win = [r for r in ph.get('rows', []) if t0 is not None and 0 <= r['t'] - t0 < link]
        if len(win) < 2: print(f"drift {nm}: no swing / no window", flush=True); continue
        r0, r = win[0], win[-1]
        turn = math.degrees(math.atan2(r['fw'][1], r['fw'][0]) - math.atan2(r0['fw'][1], r0['fw'][0]))
        out[nm] = ((r['pos'][0] - r0['pos'][0], r['pos'][1] - r0['pos'][1]), (turn + 180) % 360 - 180, r['t'] - t0)
    if 'a' not in out: return
    a = out['a'][0]; na = math.hypot(*a)
    dr = {nm: math.hypot(v[0][0] - a[0], v[0][1] - a[1]) for nm, v in out.items()}
    for nm, (d, turn, tl) in out.items():
        print(f"drift {nm}: displacement over the window (0 .. {tl:.3f} s) {d[0]:.3f},{d[1]:.3f} |{math.hypot(*d):.3f}| "
              f"turn {turn:.1f} deg drift {dr[nm]:.3f}", flush=True)
    print(f"drift a2 spread {dr.get('a2', 0):.3f}", flush=True)
    if 'e_fwd' in out: df = math.hypot(*out['e_fwd'][0]) - na
    check("e_fwd: the stick forward until the link: |displacement| - a's <= 0.35", 'e_fwd' in out and df <= 0.35,
          f"{df:.3f}" if 'e_fwd' in out else 'no swing')
    for nm in ('e_right', 'e_back'):
        if nm not in out: check(f'{nm}: a swing', False, 'no swing'); continue
        d, turn, _ = out[nm]
        check(f'{nm}: his turn before the link <= 32 deg', abs(turn) <= 32, f"{turn:.1f}")
        check(f'{nm}: |displacement| within 0.35 of a\'s', abs(math.hypot(*d) - na) <= 0.35,
              f"{math.hypot(*d):.3f} against {na:.3f}")


def finish_flow():
    import math
    t = sabr_tab(); R = lambda i, o: e.rf(t + 40 + 0x2C * i + o)
    length, cut, link, step, s_from, s_to = (r32(t + 40 + 4) - 1) / R(0, 8), R(0, 12), R(0, 32), R(0, 24), R(0, 36), R(0, 40)
    p0, fw = st['p0'], st['fw']
    along = lambda r: (r['pos'][0] - p0[0]) * fw[0] + (r['pos'][1] - p0[1]) * fw[1]
    print(f"table sw1: length {length:.3f} cut {cut:.3f} link {link:.3f} step {step} from {s_from:.3f} to {s_to:.3f}; "
          f"nearest guard at the start {st['near0']:.1f}", flush=True)

    def starts(rows):                   # (time, move) of every swing start: a new move, or our controller's time reset
        out, prev = [], None
        for r in rows:
            if r['m'] >= 0 and (prev is None or prev['m'] != r['m'] or (r['cid'] == prev['cid'] and r['ct'] < prev['ct'] - 0.1)):
                out.append((r['t'], r['m'], r))
            prev = r
        return out

    def played(rows, t0, mv=0):         # s the move mv played from t0 (until it ends or another starts)
        for r in rows:
            if r['t'] > t0 + 0.02 and r['m'] != mv: return r['t'] - t0
        return None
    a = st['fl'].get('a', {}); rows = a.get('rows', []); t0 = a.get('t0')
    if t0 is not None:
        dur = played(rows, t0)
        cut_r = next((r for r in rows if r['cuts'] > rows[0]['cuts']), None)
        in_mv = [r for r in rows if r['m'] == 0]
        step_rows = [r for r in in_mv if s_from <= r['ct'] <= s_to]
        dd = lambda r: step * min(1.0, max(0.0, (r['ct'] - s_from) / (s_to - s_from)))
        err = max((abs(along(r) - dd(r)) for r in step_rows), default=99)
        end_r = next((r for r in in_mv if r['ct'] > s_to), None)
        last = in_mv[-1] if in_mv else None
        stand = rows[-1]['cid'] == 0
        end_t = next((r['t'] for r in rows if r['t'] > t0 + 0.02 and r['m'] != 0), None)
        st_r = next((r for r in rows if end_t is not None and r['t'] >= end_t and r['cid'] == 0), None)
        check('a: one tap plays sw1 0.70 +- 0.08 s', dur is not None and abs(dur - 0.70) <= 0.08, f"{dur}")
        check('a: the cut 0.25 +- 0.07 s after the start', cut_r and abs(cut_r['t'] - t0 - 0.25) <= 0.07,
              f"{cut_r['t'] - t0:.3f}" if cut_r else 'no cut')
        check('a: his displacement along his facing 1.5 +- 0.3', last and abs(along(rows[-1]) - 1.5) <= 0.3,
              f"{along(rows[-1]):.3f} (at the move's end {along(last):.3f})" if last else '-')
        check('a: on each frame of the step within 0.6 of d at the controller time (D16)', step_rows and err <= 0.6,
              f"max {err:.3f} over {len(step_rows)} VIs; " + ' '.join(f"{r['ct']:.2f}:{along(r):.2f}/{dd(r):.2f}" for r in step_rows[::2]))
        check('a: at its end within 0.3 (D16)', end_r and abs(along(end_r) - step) <= 0.3,
              f"first VI past the step (ct {end_r['ct']:.3f}) {along(end_r):.3f} against {step}" if end_r else '-')
        check('a: the controller back on the stand after', stand, f"descriptor id {rows[-1]['cid']:#x}")
        check('a: the stand (descriptor id 0) within 0.2 s of the swing\'s end', st_r and st_r['t'] - end_t <= 0.2,
              f"{st_r['t'] - end_t:.3f}" if st_r else 'never')
    else: check('a: one tap starts sw1', False, 'no swing')
    b = st['fl'].get('b_run', {}); rows = b.get('rows', []); t0 = b.get('t0')
    if t0 is not None:
        off = next((r for r in rows if r['t'] > t0 and r['m'] < 0), None)
        tr = next((r for r in rows if off and r['t'] >= off['t'] and 'trot' in (r['cur'], r['to'])), None)
        check('b: the stick from 0.45 s: the swing over by 0.55 s (D12)', off and off['t'] - t0 <= 0.55, f"{off['t'] - t0:.3f}" if off else '-')
        check('b: his block trot within 0.3 s more', tr and tr['t'] - off['t'] <= 0.3,
              f"{tr['t'] - off['t']:.3f} ({tr['cur']} -> {tr['to']})" if tr else f"blocks {sorted(set((r['cur'], r['to']) for r in rows[-20:]))}")
    else: check('b: one tap starts sw1', False, 'no swing')
    z = st['fl'].get('b_z', {}); rows = z.get('rows', []); t0 = z.get('t0')
    dz = played(rows, t0) if t0 is not None else None
    check('b: Z held from 0.45 s, no stick: the move plays its 0.70 s', dz is not None and abs(dz - 0.70) <= 0.08,
          f"{dz} blocks {sorted(set((r['cur'], r['to']) for r in rows if r['m'] < 0 and r['t'] > (t0 or 0)))[:4]}")
    c = st['fl'].get('c_same', {}); s = starts(c.get('rows', []))
    check('c: a tap and a second at 0.60 s: moves 0, 0, the second at 0.70 +- 0.08 s, the frame back below 3 (D15)',
          [x[1] for x in s] == [0, 0] and abs(s[1][0] - s[0][0] - 0.70) <= 0.08 and s[1][2]['fr'] < 3,
          f"starts {[(round(x[0] - s[0][0], 3), x[1], round(x[2]['fr'], 2), x[2]['mode']) for x in s]}" if s else 'none')
    c = st['fl'].get('c_chain', {}); s = starts(c.get('rows', []))
    check('c: taps at 0 and 0.30 s: sw2 at 0.433 +- 0.07 s, the state blending (mode 3) on that frame (D15)',
          [x[1] for x in s][:2] == [0, 1] and abs(s[1][0] - s[0][0] - 0.433) <= 0.07 and s[1][2]['mode'] == 3,
          f"starts {[(round(x[0] - s[0][0], 3), x[1], x[2]['mode'], x[2]['cur'], x[2]['to']) for x in s]}" if s else 'none')
    for nm, want, lo, hi in (('d_free', 'sw1 ', 1.2, 1.8), ('d_guard', 'swp1', None, 0.3)):
        ph = st['fl'].get(nm, {}); rows = [r for r in ph.get('rows', []) if 't0' in ph and r['t'] >= ph['t0']]
        dp = along(rows[-1]) if rows else None
        tags = sorted({r['dtag'] for r in rows if r['m'] == 0})
        print(f"{nm}: stills at controller times {ph.get('shot_t')}, displacement {dp if dp is not None else 0:.3f}", flush=True)
        check(f"{nm}: the block played {want!r}, his displacement along his facing " +
              (f"{lo}..{hi}" if lo is not None else f"< {hi}"),
              tags == [want] and dp is not None and (abs(dp) < hi if lo is None else lo <= dp <= hi),
              f"blocks {tags}, displacement {dp if dp is None else round(dp, 3)}")
    flow_drift(p0)
    if STILL and st.get('still_names'):
        flow_sheets()


def flow_sheets():
    """the d stills on two contact images, <STILL stem>_free.png and _guard.png (4 x 2, the controller time on each)"""
    import glob
    from PIL import Image, ImageDraw
    new = sorted((f for f in glob.glob(os.path.join(e.shot_dir, '*.png')) if os.path.basename(f) not in st['shots0']),
                 key=os.path.getmtime)
    if len(new) != len(st['still_names']):
        print(f"stills: {len(new)} files for {len(st['still_names'])} shots", flush=True)
    for nm in ('d_free', 'd_guard'):
        ims = [(Image.open(f).convert('RGB'), ct) for f, (n_, ct) in zip(new, st['still_names']) if n_ == nm]
        if not ims: continue
        w, hh = ims[0][0].size; sheet = Image.new('RGB', (4 * w, 2 * hh))
        for i, (im, ct) in enumerate(ims):
            sheet.paste(im, ((i % 4) * w, (i // 4) * hh))
            ImageDraw.Draw(sheet).text(((i % 4) * w + 8, (i // 4) * hh + 8), f"{nm} sw1 t {ct:.2f} s", fill=(255, 255, 0))
        out = os.path.splitext(STILL)[0] + ('_free.png' if nm == 'd_free' else '_guard.png')
        sheet.save(out); print('contact', out, flush=True)


# ---- bugs: per-VI numbers for the playtest's saber items (death, the blade behind, the upper body gone) ----
BUGS = os.environ.get('BUGS', 'free')
BUG_BONES = (10, 9, 8, 5, 1)             # spine, chest, right shoulder, left shoulder, head
HEAD_PATH = (18, 17, 10, 9, 2, 1)        # model, pelvis, spine, chest, neck, head
BUG_BODY = (1.0, 1.2, 0.0, 6.5)          # his body box: |forward| <= 1.0, |right| <= 1.2, up 0 .. 6.5 from his feet
BUG_SHOTS = 8                            # stills a run, at most
def saber_m():
    """saber.c's static M record (cur, next, hit, t, link, ...): its 'M' in .saber (another module has an M too)"""
    import subprocess
    out = subprocess.run([str(inj.LLVM / 'llvm-nm'), str(inj.BUILD / 'payload.elf')], capture_output=True, text=True).stdout
    return next(int(a, 16) for a, _t, n in (l.split() for l in out.splitlines() if len(l.split()) == 3)
                if n == 'M' and 0x805C0000 <= int(a, 16) < 0x80600000)


SM = saber_m() if CASE in ('bugs', 'saber_fix') else 0
BUG_T = {'die_stand': 500, 'die_swing': 500, 'die_laser': 500, 'run_swing': 400, 'spin_run': 200, 'free': 3600}
WORLD_ROOT = 0x8013CE24                  # -> the world root group (+0x10 its list: saber.c's own while the light is on)


def trot_blk(h):
    """his trot block (its entries' nodes are his bone nodes, by bone index), or 0"""
    b = r32(h + 0x19C)
    for _ in range(60):
        if not 0x80000000 <= b < 0x80800000: return 0
        if r32(b + 0x1C) == 0x74726F74: return b
        b = r32(b + 0x14)
    return 0


def bone_world(h, path):
    """the world matrix of the last bone on path (as hand_world: placement node, its model child, the bones) or None"""
    blk = trot_blk(h)
    if not blk: return None
    pn, m = r32(h + 0x24C), r32(blk + 0x38 + 0xA0 * 18 + 8)
    ok = lambda a: 0x80000000 <= a < 0x80800000
    if not ok(pn) or not ok(m) or r32(pn + 0xC) > 8: return None
    x = 0
    for i in range(r32(pn + 0xC)):
        c = r32(r32(pn + 0x10) + 4 * i)
        if ok(c) and r32(c) >> 28 == 0xD and r32(c + 0xC) <= 8 and any(r32(r32(c + 0x10) + 4 * j) == m for j in range(r32(c + 0xC))): x = c
    if not x: return None
    w = [1.0 if (i % 4 == 0 and i < 9) else 0.0 for i in range(12)]
    for n in [pn, x] + [r32(blk + 0x38 + 0xA0 * b + 8) for b in path]:
        if not ok(n): return None
        L = [e.rf(n + 0x14 + 4 * i) for i in range(9)]; t = [e.rf(n + 0x38 + 4 * i) for i in range(3)]
        r = [L[3 * i] * w[j] + L[3 * i + 1] * w[3 + j] + L[3 * i + 2] * w[6 + j] for i in range(3) for j in range(3)]
        r += [t[0] * w[j] + t[1] * w[3 + j] + t[2] * w[6 + j] + w[9 + j] for j in range(3)]
        w = r
    return w


def his(h, q):
    """q in his frame: (forward, right, up) from his feet"""
    p, f = V(h, 0x50), (e.rf(h + 0x30), e.rf(h + 0x34))
    return ((q[0] - p[0]) * f[0] + (q[1] - p[1]) * f[1], (q[0] - p[0]) * f[1] - (q[1] - p[1]) * f[0], q[2] - p[2])


def bug_row(k, h):
    """one VI's numbers: the animation, the swing, the blade in his frame, the upper body's nodes"""
    import math
    d = r32(CTL + 4); mv0, n = S['g_mv'], r32(S['g_mvn'])
    cur, to = r32(h + STATE_H + 0x14), r32(h + STATE_H + 0x18)
    ours = lambda b: 'm' if mv0 <= b < mv0 + 9 * ARM_BLK else 's' if S['g_blk'] <= b < S['g_blk'] + SW_BLOCKS * ARM_BLK else 'g'
    row = dict(k=k, t=round(clock(), 3), hp=round(e.rf(h + HP), 1), id=wid(h), mv=s32(r32(S['g_saber_move'])),
               mt=round(e.rf(SM + 0xC), 3), cid=(s32(r32(d)) if 0x80000000 <= d < 0x80800000 else -99),
               ct=round(e.rf(CTL), 3), mode=r32(h + STATE_H) & 0x7FFFFFFF,
               cur=(tag(cur + 0x1C) + ours(cur)) if cur else '-', to=(tag(to + 0x1C) + ours(to)) if to else '-',
               fr=round(e.rf(h + STATE_H + 4), 2), fl=r32(h + FLAGS),
               lk=int(r32(S['g_blk'] + (SW_BLOCKS - 1) * ARM_BLK + 0x14) == mv0 and n > 0), dead=int(e.rf(h + HP) <= 0),
               pw=round(e.rf(S['g_saber_parry_w']), 2))
    rl = r32(r32(WORLD_ROOT) + 0x10); row['light'] = int(0x805C0000 <= rl < 0x80600000)   # the blade's light chain linked
    sg = blade_seg(h)
    if sg:
        F, T = [float(x) for x in his(h, sg[0])], [float(x) for x in his(h, sg[1])]; dl = math.dist(sg[0], sg[1]) or 1
        row['bf'] = round((T[0] - F[0]) / dl, 2)                       # the blade's forward component in his frame
        row['foot'] = tuple(round(x, 2) for x in F); row['tip'] = tuple(round(x, 2) for x in T)
        bx = BUG_BODY
        # the blade back through him: pointing backward and its tip behind his front, or any point of it in his box
        inside = any(abs(F[0] + (T[0] - F[0]) * u) <= bx[0] and abs(F[1] + (T[1] - F[1]) * u) <= bx[1]
                     and bx[2] <= F[2] + (T[2] - F[2]) * u <= bx[3] for u in (0.25, 0.5, 0.75, 1.0))
        row['back'] = int(row['bf'] < 0 and T[0] < -0.3 and T[2] < 7.0)   # behind him, not the overhead raise
        row['inbody'] = int(inside)
    bad = []
    tb = trot_blk(h)
    if tb: row['spz'] = round(e.rf(r32(tb + 0x38 + 0xA0 * 10 + 8) + 0x40), 3)   # the spine node's translation z
    for b in BUG_BONES if tb else ():
        nd = r32(tb + 0x38 + 0xA0 * b + 8)
        cnt, lst = r32(nd + 0xC), r32(nd + 0x10)
        sc = min(sum(e.rf(nd + 0x14 + 12 * i + 4 * j) ** 2 for j in range(3)) ** 0.5 for i in range(3))
        if cnt == 0 or lst != OURS + b * ROW or not sc >= 0.5: bad.append((b, cnt, f"{lst:#x}", round(sc, 3)))
    hw = bone_world(h, HEAD_PATH)
    if hw:
        hd = [float(x) for x in his(h, hw[9:12])]; row['head'] = tuple(round(x, 2) for x in hd)
        hsc = min(sum(hw[3 * i + j] ** 2 for j in range(3)) ** 0.5 for i in range(3))
        row['hsc'] = round(hsc, 3)
        if not (2.0 <= hd[2] <= 9.0 and abs(hd[0]) < 3 and abs(hd[1]) < 3 and hsc >= 0.1): bad.append(('head', row['head'], row['hsc']))
    if bad and tb:                  # the chain's nodes: translation and largest row norm (model, pelvis, spine, chest, neck)
        row['nodes'] = [(b, [round(e.rf(r32(tb + 0x38 + 0xA0 * b + 8) + 0x38 + 4 * i), 2) for i in range(3)],
                         round(max(sum(e.rf(r32(tb + 0x38 + 0xA0 * b + 8) + 0x14 + 12 * i + 4 * j) ** 2 for j in range(3)) ** 0.5
                                   for i in range(3)), 2)) for b in (18, 17, 10, 9, 2)]
        row['pl'] = [round(e.rf(r32(h + 0x24C) + 0x38 + 4 * i), 2) for i in range(3)]
    w0, w1 = (int(x) for x in os.environ.get('BUG_WIN', '0,0').split(','))
    if w0 <= k < w1 and tb and cur:  # the playing block's entry for the spine node: its words (BUG_WIN)
        sp = r32(tb + 0x38 + 0xA0 * 10 + 8)
        for i in range(19):
            en = cur + 0x38 + 0xA0 * i
            if r32(en + 8) == sp:
                row['spine_e'] = (i, ' '.join(f"{r32(en + 4 * q):08x}" for q in range(40)))
                row['spine_n'] = ' '.join(f"{r32(sp + 4 * q):08x}" for q in range(18))
        row['view'] = e.r16(VIEW); row['blk'] = (f"{cur:#x}", f"{r32(cur + 4):08x} {r32(cur + 8):08x} {r32(cur + 0xC):08x} {r32(cur + 0x30):08x}")
    row['bad'] = bad
    return row


def bugs_case(k, h):
    import math
    if k == 9:
        e.w32(S['g_guard_on'], 2); set_wid(h, 0 if BUGS == 'die_laser' else 4)
        st['rows'] = []; st['bshots'] = []; st['shots0'] = set(os.listdir(e.shot_dir))
    if k < 9: return 0
    if e.r16(VIEW) == 4:            # the drop camera's eye out along his facing turned HOLD_CAM[1]: his front and hands
        p = V(h, 0x50); f = math.atan2(e.rf(h + 0x34), e.rf(h + 0x30)) + math.radians(HOLD_CAM[1])
        for a, o in enumerate((HOLD_CAM[0] * math.cos(f), HOLD_CAM[0] * math.sin(f), HOLD_CAM[2])): e.wf(EYE + 4 * a, p[a] + o)
    if 10 <= k < 14 or 40 <= k < 44: return BTN['L']   # follow -> first person -> drop
    if 60 <= k < 64 and BUGS != 'die_laser': return BTN['CU']   # the Stunner -> the saber
    if k < 90:
        e.wf(h + HP, 100.0); return 0
    j = k - 90
    if j >= int(os.environ.get('BUG_VIS', BUG_T[BUGS])):
        if CASE == 'saber_fix': return fix_next()
        finish_bugs(); e.stop(); return 0
    if not st.get('died') and (not BUGS.startswith('die') or 'one' not in st): e.wf(h + HP, 100.0)
    btn, sx, sy = 0, 0, 0
    if BUGS.startswith('die'):     # killed by the game's own damage (0x800732D4: below 1 it plays diea, id 23): health 1,
        g = st.get('g')                # an alerted guard held 40 ahead of his start, Luke turned his back to it
        if g is None:
            st['p0'] = V(h, 0x50); fw = [e.rf(h + 0x30), e.rf(h + 0x34)]; l = math.hypot(*fw); st['fw'] = [fw[0] / l, fw[1] / l]
            g = st['g'] = [o for o in trops() if e.rf(o + TROP_HP) > 0 and not r32(o + 0x74) & 0xF][0]
            e.wf(g + TROP_HP, 1000.0); e.w32(g + 0x74, r32(g + 0x74) | 0x20)
            st['yaw'] = (e.rf(h + 0x8C) + 180.0) % 360.0
        p0, fw = st['p0'], st['fw']; gp = [p0[0] + 40 * fw[0], p0[1] + 40 * fw[1], p0[2]]
        yaw = math.degrees(math.atan2(fw[0], -fw[1])) % 360
        put(g, gp, yaw); e.wf(g + TROP_HP, 1000.0)
        c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        for a, v in enumerate((c, s_, 0)): e.wf(g + 0x20 + 4 * a, v)
        for a, v in enumerate((-s_, c, 0)): e.wf(g + 0x30 + 4 * a, v)
        if not st.get('died'):
            e.wf(h + 0x8C, st['yaw']); e.wf(h + 0x14, st['yaw'])
            if BUGS == 'die_swing' and j % 8 < 4: btn = BTN['B']   # the combo on and on
            if j >= 20 and 'one' not in st and (BUGS != 'die_swing' or s32(r32(S['g_saber_move'])) >= 0):
                e.wf(h + HP, 1.0); st['one'] = k
            if e.rf(h + HP) <= 0: st['died'] = k; print(f"DIED k {k} move {s32(r32(S['g_saber_move']))} M.t {e.rf(SM + 0xC):.3f}", flush=True)
    elif BUGS == 'run_swing':      # BUG_EVERY: VIs between taps (8: the combo on and on; longer: a swing, the run again)
        sy = 80
        if j % int(os.environ.get('BUG_EVERY', '8')) < int(os.environ.get('BUG_TAP', '4')): btn = BTN['B']
    elif BUGS == 'spin_run':
        m = s32(r32(S['g_saber_move']))
        if 'spun' not in st and m != 3 or os.environ.get('BUG_HOLD'): btn = BTN['B']   # held until the spin starts
                                                                                      # (BUG_HOLD=1: on and on)
        if m == 3: st['spun'] = st.get('spun', j)
        go = {'link': e.rf(SM + 0x10), 'start': 0.0, 'mid': 0.3}[os.environ.get('BUG_STICK', 'link')]   # the stick from
        if m == 3 and e.rf(SM + 0xC) >= go or ('spun' in st and m != 3): sy = 80                         # the spin's M.t
    else:                           # the free run: a 600-VI round of swings, runs, a spin, jumps, the saber away and back
        if os.environ.get('BUG_GUARD'):   # an alerted guard held 30 ahead of him, facing him: its bolts, his parries
            g = st.get('g')
            if g is None:
                g = st['g'] = [o for o in trops() if e.rf(o + TROP_HP) > 0 and not r32(o + 0x74) & 0xF][0]
                e.w32(g + 0x74, r32(g + 0x74) | 0x20)
            p, fw = V(h, 0x50), (e.rf(h + 0x30), e.rf(h + 0x34)); l = math.hypot(*fw) or 1
            gp = [p[0] + 30 * fw[0] / l, p[1] + 30 * fw[1] / l, p[2]]
            yaw = math.degrees(math.atan2(fw[0], -fw[1])) % 360
            put(g, gp, yaw); e.wf(g + TROP_HP, 1000.0)
            c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            for a, v in enumerate((c, s_, 0)): e.wf(g + 0x20 + 4 * a, v)
            for a, v in enumerate((-s_, c, 0)): e.wf(g + 0x30 + 4 * a, v)
            st['pmax'] = max(st.get('pmax', 0.0), e.rf(S['g_saber_parry_w']))
            if e.rf(S['g_saber_parry_w']) > 0: st['pvis'] = st.get('pvis', 0) + 1
        r = j % 600; turn = (j // 600) % 2
        if 60 <= r < 180: sy = 80; btn = BTN['B'] if r % 12 < 4 else 0
        elif 180 <= r < 220: btn = BTN['B'] if r < 184 else 0
        elif 220 <= r < 300:
            btn = BTN['B'] if r < 270 and s32(r32(S['g_saber_move'])) != 3 else 0
            if s32(r32(S['g_saber_move'])) == 3 or r >= 270: sy = 80
        elif 300 <= r < 380: sy = 80; sx = 60 if turn else -60; btn = BTN['A'] if r % 40 < 4 else 0
        elif 380 <= r < 400: sy = -80
        elif 400 <= r < 404: btn = BTN['CU']                # the saber away (to the laser)
        elif 420 <= r < 460: sy = 80; btn = BTN['B'] if r % 12 < 4 else 0
        elif 460 <= r < 580: btn = press(r, 460, 20) if r < 580 else 0   # six C-ups: laser .. Stunner, the saber
        elif r >= 580: btn = BTN['B'] if r < 584 else 0
    row = bug_row(k, h); st['rows'].append(row)
    if CASE == 'saber_fix': fix_row(row, h)
    flag = row.get('back') or row.get('inbody') or row['bad']
    s0, s1 = (int(x) for x in os.environ.get('BUG_SHOTW', '0,0').split(','))   # a still every 2nd VI in [s0, s1)
    if STILL and s0 <= k < s1 and k % 2 == 0:
        e.shot(); st['bshots'].append((k, 'w' + ('bad' if row['bad'] else 'ok')))
    elif os.environ.get('BUG_SHOT_BAD') and not row['bad']: flag = flag and os.environ.get('SABER_DBG')   # stills of the bad VIs only
    if STILL and flag and len(st['bshots']) < BUG_SHOTS and (not st['bshots'] or k - st['bshots'][-1][0] >= 6):
        e.shot(); st['bshots'].append((k, ('bad' if row['bad'] else 'back' if row.get('back') else 'inbody')))
    w0, w1 = (int(x) for x in os.environ.get('BUG_WIN', '0,0').split(','))
    if os.environ.get('SABER_DBG') or BUGS.startswith('die') or flag or BUGS != 'free' or w0 <= k < w1:
        print('BUG ' + ' '.join(f"{a}={b}" for a, b in row.items() if a != 'bad' or b), flush=True)
    return btn, sx, sy


def finish_bugs():
    import glob
    rows = st['rows']
    h = r32(S['g_player'])
    if os.environ.get('BUG_ENTRIES') and h:   # every block in his chain: entries whose translation offset (+0x1C..+0x24) is far
        b, out = r32(h + 0x19C), []
        for _ in range(60):
            if not 0x80000000 <= b < 0x80800000: break
            far = [(i, [round(e.rf(b + 0x38 + 0xA0 * i + 0x1C + 4 * c), 1) for c in range(3)]) for i in range(19)
                   if max(abs(e.rf(b + 0x38 + 0xA0 * i + 0x1C + 4 * c)) for c in range(3)) > 100]
            out.append(f"{tag(b + 0x1C)}@{b:#x}" + (f" far {far}" if far else ''))
            b = r32(b + 0x14)
        print('BUGS chain: ' + '; '.join(out), flush=True)
    print(f"BUGS {BUGS}: {len(rows)} VIs; back {sum(r.get('back', 0) for r in rows)}, in his box "
          f"{sum(r.get('inbody', 0) for r in rows)}, upper body bad {sum(1 for r in rows if r['bad'])}; parry VIs {st.get('pvis', 0)} "
          f"(w max {st.get('pmax', 0.0):.2f}), deflects {r32(S['g_saber_deflects'])}", flush=True)
    seen = {}
    for r in rows: seen[(r['cur'], r['to'], r['cid'])] = seen.get((r['cur'], r['to'], r['cid']), 0) + 1
    print('BUGS blocks (cur, to, descriptor): VIs ' + str(sorted(seen.items(), key=lambda x: -x[1])[:30]), flush=True)
    if STILL and st['bshots']:
        new = sorted((f for f in glob.glob(os.path.join(e.shot_dir, '*.png')) if os.path.basename(f) not in st['shots0']),
                     key=os.path.getmtime)
        if len(new) != len(st['bshots']): print(f"stills: {len(new)} files for {len(st['bshots'])} shots", flush=True)
        for f, (k, why) in zip(new, st['bshots']):
            out = os.path.splitext(STILL)[0] + f'_{BUGS}_{k}_{why}.png'; shutil.copy(f, out); print('still', out, flush=True)


# ---- saber_fix: the playtest's items 1-4 fixed, checked on bugs' setups (one palace.st load per run) ----
FIX_RUNS = [('die_swing', {}),
            ('run_swing', {'BUG_EVERY': '4', 'BUG_TAP': '2', 'BUG_VIS': '180'}),    # a tap every 4 VIs, 3 s
            ('run_swing', {'BUG_EVERY': '40', 'BUG_VIS': '180'}),                    # a tap from the run (trtg first seen)
            ('spin_run', {'BUG_HOLD': '1', 'BUG_STICK': 'link'}),
            ('free', {'BUG_GUARD': '1'})]
FIX_RUNS = [r for r in FIX_RUNS if r[0] in os.environ.get('FIX', r[0]).split(',')]
FIX_KNOBS = ('BUG_EVERY', 'BUG_TAP', 'BUG_VIS', 'BUG_HOLD', 'BUG_STICK', 'BUG_GUARD')
SPINE_Z = 1.136                          # the spine node's translation z on every block


def fix_start(i):
    global BUGS
    BUGS, env = FIX_RUNS[i]
    for a in FIX_KNOBS: os.environ.pop(a, None)
    os.environ.update(env)
    st.clear(); st.update({'k0': None, 'ids': [], 'log': [], 'fix': i})
    print(f"FIX run {i}: {BUGS} {env}", flush=True)


def fix_row(row, h):
    if BUGS == 'die_swing':
        row['off'] = int(bool(queued(ID_OFF))); row['on'] = int(bool(queued(ID_ON)))
        if os.environ.get('FIX_Q'): row['q'] = [(f"{x[0]:x}", f"{x[1]:x}") for x in slots()]


def fix_next():
    """the run's checks, then the next run (a fresh palace.st load) or the end"""
    rows, name = st['rows'], f"{BUGS}" + (f"/{os.environ['BUG_EVERY']}" if BUGS == 'run_swing' else '')
    if BUGS == 'die_swing':
        d = st.get('died'); hit = [r for r in rows if d and d - 1 <= r['k'] <= d]
        check(f'{name}: killed mid-sw1', any(r['mv'] == 0 for r in hit),
              f"died k {d}, move then {[r['mv'] for r in hit]}, block {[r['cur'] for r in hit]}")
        after = [r for r in rows if d and r['k'] >= d]
        dia = [r for r in after if r['cur'].startswith('diea') or r['to'].startswith('diea')]   # played or blended to
        first = dia[0]['k'] - d if dia else None
        check(f'{name}: diea within 4 VIs of health < 1', first is not None and first <= 4, f"first diea VI +{first}")
        check(f'{name}: diea plays >= 150 VIs', len(dia) >= 150, f"{len(dia)} VIs")
        off = next((r['k'] - d for r in after if not r['light']), None)
        snd = next((r['k'] - d for r in after if r['off']), None)
        # no 'off' check: the game's death sounds take the queue's last free slots that frame (all 8 busy)
        check(f'{name}: the light off within 4 VIs', off is not None and off <= 4, f"light off +{off}, 'off' queued +{snd}")
        rs = next((r for r in after if r['hp'] > 0), None)
        back = [r for r in after if rs and r['k'] >= rs['k']]
        lon = next((r['k'] - rs['k'] for r in back if r['light']), None)
        son = next((r['k'] - rs['k'] for r in back if r['on']), None)
        check(f'{name}: after the respawn the light back, on sound', rs and lon is not None and son is not None,
              f"respawn k {rs and rs['k']} id {rs and rs['id']}; light +{lon}, 'on' queued +{son}")
    elif BUGS in ('run_swing', 'spin_run'):
        tr = [r['k'] for r in rows if r['cur'].startswith('trtg') or r['to'].startswith('trtg')]
        check(f'{name}: no VI plays trtg', not tr, f"{len(tr)} VIs {tr[:8]}")
        # the bug's shape (items 2, 3): pointing back with the tip > 0.3 behind him below 7 up; sw1's wind-up leans the
        # blade back (bf down to -0.31) with the tip still in front, the spin sweeps all round him (exempt)
        bk = [(r['k'], r['bf'], r['mv'], r['tip']) for r in rows if 'bf' in r and r['bf'] < 0]
        bh = [(r['k'], r['bf'], r['mv'], r['tip']) for r in rows if r.get('back') and r['mv'] != 3]
        check(f'{name}: the tip never behind him (back)', not bh,
              f"{sum(1 for r in rows if 'bf' in r)} VIs with a blade, {len(bh)} behind {bh[:6]}; bf < 0 on {len(bk)}")
    else:
        zs = [r['spz'] for r in rows if 'spz' in r]
        badz = [(r['k'], r['spz']) for r in rows if 'spz' in r and abs(r['spz'] - SPINE_Z) > 0.5]
        check(f'{name}: the spine node z within 0.5 of {SPINE_Z} on every VI', zs and not badz,
              f"{len(zs)} VIs, min {min(zs) if zs else None}, max {max(zs) if zs else None}, off {badz[:6]}; "
              f"parry VIs {st.get('pvis', 0)} (w max {st.get('pmax', 0.0):.2f})")
    print(f"FIX {name}: {len(rows)} VIs", flush=True)
    if st['fix'] + 1 < len(FIX_RUNS): fix_start(st['fix'] + 1)
    else: e.stop()
    return 0


if CASE == 'saber_fix': fix_start(0)


def script(e, n):
    if n == 1: e.unlimit()
    if n < 60: return
    if st['k0'] is None:
        e.load_state(os.path.join(paths.STATES, STATE)); st['k0'] = n; return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 4: return
    if e.r16(0x800DD2D0): e.w32(0x800DD2D0, e.r32(0x800DD2D0) & 0xFFFF); e.wf(0x800D07FC, 0)   # the held line
    h = r32(S['g_player'])
    if not h: e.pad(0); return
    if CASE not in ('deflect', 'bugs', 'saber_fix') or k < 9: e.wf(h + HP, 100.0)
    if k == 8: setup(h)
    b = {'cycle': cycle, 'snd': snd, 'combo': combo, 'spin': spin, 'boss': boss_case, 'deflect': deflect_case, 'melee': melee_case, 'hold': hold_case, 'flow': flow_case, 'parry': parry_case, 'bugs': bugs_case, 'saber_fix': bugs_case}[CASE](k, h)
    if os.environ.get('SABER_DBG') and k % 10 == 0:
        print(f'k {k} h {h:#x} id {wid(h)} b {b if isinstance(b, tuple) else hex(b)} gate {e.rf(0x800DEB78):.2f} pad {r32(0x801130AC):#x} '
              f'look {r32(S["g_guard_on"])}', flush=True)
    e.pad(*b) if isinstance(b, tuple) else e.pad(b)


e.run(script)
sys.exit(report())
