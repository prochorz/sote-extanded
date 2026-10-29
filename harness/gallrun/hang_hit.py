"""The hangar TIEs under fire (gall_ties.c hangar_launch() / pursuit() / chaser()): per game frame from
the launch (g_hang_t 0) each chase slot's TIE (object index, health +0x60, state +0xA8, place, its seconds since its own
launch s = g_hang_t - slot x HANGAR_GAP, distance to its hangar's mouth), the Falcon's bolts near it, a line when a TIE's
health changes. In free flight the bot (work/chain_take.py's chase pilot) aims and fires at a chase TIE instead of
Slave I; on the rail (g_cine 2) it fires B, the gun centred; HANG lines give each slot's nearest pass of the player's
bolts (owner Chor, a bolt's last 130 of way, as free_lasers()) over the last 6 frames (-1: none) and its distance to Chor.

    M64CPU=2 SHOTS=pt7r_hang .venv/bin/python3 gallrun/hang_hit.py <build>/sote-patch.z64 [--make BASE] [--kill T] [--aim SLOT]
    .venv/bin/python3 gallrun/hang_hit.py <cam log> --turn native0->1|jump [--turn-n N]

  --make BASE  make run/<build>_end.st first: from BASE (e.g. run/<build>_peel.st, gallrun/peel_check.py), stage 1 flown
               by the take's pilot, stage 2 firing, saved at the end scene's first frame; the run goes on (a first trace)
  --kill T     at g_hang_t T write health 0 into slot --aim's TIE (what our code does with a dead one) instead of firing
  --aim SLOT   the chase slot aimed at / killed (default 0)
  --plant D    on the rail (g_cine 2) slot --aim's TIE put D units ahead of the player's newest live bolt, on its line,
               each VI (does the game's laser hit test take its health?)
  --cine C     the phase fired in / planted in (default 2: the rail; 1: the end scene)
  --watch A,B  per game frame with g_hang_t in [A, B]: each slot's place and state, Chor's and the Falcon's (Stft) place
  --secs S     stop S seconds after the launch (default 14)
  --vel        with --watch: every VI, WVEL lines per chase TIE: place, its heading TIE_VEL (+0x74), the step since the
               last VI split into along the heading / towards Chor's place, its distance to Chor; and g_tie_aim's
               distance to Chor's place (who moves them in: the game's AI along the heading, or pursuit())
  --clear      a CLEAR summary: in the end scene (g_cine 1) per chase slot, from its launch, the least
               x, y distance to Chor's place and the largest turn of the drawn nose (node row 1) between samples (rad), the
               samples over 0.3 rad and the largest jump of the drawn node's place; bursts in the scene;
               at the chase's start (g_cine 2) the slots filled and, per slot, the first g_hang_t within 600 of Chor's place
               and the end scene's first held line (held 90 VIs before A): per VI the TIEs in play by distance to the drawn
               Falcon (model root +0x38), those drawn (node show 0xFF) within 1000, HUD 37 / 51 x, TIE bolts within 1000;
               ENDCLEAR lines and summary
  --chase S    with --clear: the drawn-nose turns (FLIP lines, CLEAR chase lines) also for the chase's first S seconds
               (set --secs past the chase's start + S, e.g. 12)
  --lead A,B   per VI with g_hang_t in [A, B]: LEAD lines per chase TIE: its formation leader (+0xBC, the
               game's update copies the leader's heading +0x30 into +0x74 and puts it at the leader's place + right x +0xC0
               + heading x +0xC4, z + +0xC8), the matrix's forward +0x30 (what the draw puts in the node), +0x74, the node's
               row 1, the distance to g_tie_aim and the place's error to the leader's offset; a LEADSUM per object at the end
  --all       (with --shots a shot at g_hang_t 0.5, 1.0, 3.5, 5.0) every TieF object at each 0.5 s of the end scene (g_cine_t, before the launch) and of
               g_hang_t 0..6: index, place, distance to Chor and to the Falcon (Stft), what it is (chase slot / chaser()
               not in a slot / wave / battle / parked), health, state, drawn (node +2 high byte 0xFF); ALL lines, an ALLSUM
               of the objects within 300 (and 1000) of the Falcon at the launch and after
  --from ST    start from this state instead of run/<build>_end.st (e.g. run/<build>_dash.st, _free.st)
  --save-at L  any of rail,dash,slave,free,jump: save run/<build>_rail.st at g_cine -> 2, _dash.st at g_sc -> 1,
               _slave.st at g_sc -> 4 (Slave I's shot before its jump),
               _free.st at g_sc -> 5 (the first VI each is seen); the run stops --after S s past the last one;
               jump: in the native flight (g_native 1) all towers written shot down (+0x140 bit 0x10,
               once), so the fly-away, Lando's line (A) and the jump follow: _jump.st at the first VI with g_fj_t >= 0,
               _prejump.st at Lando's line held (g_won_said, MSG_HOLD: the jump starts on its let-go; --cam from there)
  --after S    with --save-at: seconds of game frames past the last state (default 3)
  --frames N   stop N game frames after the load (g_ov_frames steps)
  --cam        (with --shots: a shot every 3 game frames of the jump, g_fj_t >= 0) per game frame a CAM line: g_cine, g_cine_t, g_sc, g_shot, MSG_HOLD, the active entry and index, the blend
               (from, to, s, length), eye (+0x44; in a blend, index -1, the blend's view 0x80111788 +0x30),
               forward (+0x24), the eye's step, g_ik, g_cam_seen, g_ship_off, the
               drawn Falcon (model root node +0x38) and its step, eye-to-Falcon distance (and entry 3's: e3-fal), its screen place (320x240) and
               step; CAMEV lines at each event (end scene start, the held line's rise, g_cine -> 2, g_sc -> 1, g_sc -> 5,
               a blend's start / end, the index changing): per quantity the step at the event's frame and the next 2
               against the mean of the 5 before (ratio); the carries' shares and a CARRYSUM per
               carry (start, share < 5 %, eye steps, Falcon off screen); ORDER lines at g_sc -> 1 (g_cam_seen against the eye the VI
               before and this VI: which frame's view it holds); also g_fj_t, g_away_t, the Stft's place
               (+0x50) and its step (d_sp), its health hp (+0x240), its forward (+0x30) and its turn since the frame before (d_sfw, deg), the sky
               entry's (6) pointer +8 (sky8: trak / fjcam / other); CAMEV events native0->1, away (g_away_t >= 0), jump
               (g_fj_t >= 0) with d_sp, d_sfw too; at the jump a JUMPVIEW line: the view drawn the frame before against the
               copy g_fj_cam holds (eye and forward differences) and against Trak 0's matrix
  --bolts      in the native flight B held; on the rail and in it, per new player bolt (Blst, owner the Stft or Chor) a BOLT line: its first
               place and direction, the ship's place, the two domes' places (falcon.c HDR_TURRET on the model root's
               rows), the distance to each dome and to the bolt's line from each, its place in the ship's frame; the
               gun nodes' (falcon.c g_gun) forward row against the ship's (angle, deg) and against the bolt's; BOLTSUM
  --sight      per game frame of the native flight a SIGHT line: Chor's three CHOR_SIGHT (0x14C) pointers (real / decoy),
               the real nodes' show word (high byte 0xFF: drawn), their place (+0x38) and screen place, Chor's distance to
               the Falcon; SIGHTSUM
  --count      (was work/hang_n.py) the hangar launch's count: from the start state to the free flight
               (g_free 1; --secs S past the launch, default 300), A on a held line only (no firing), per game frame every
               TieF: DRAWN (first frame drawn at the mouth), OUT (first frame placed within 300 of hangar record 0 after
               g_hang_t 0: object, g_hang_t, slot), NEAR (drawn or placed within 1000 of the Falcon before the free flight),
               RAIL (per 0.5 s on the rail: g_chase filled), SUM lines: out of the mouth and their gaps, the others within
               1000 (and per object its frames near, near and drawn), per launched TIE its 1.5 s out (frames, drawn, drawn > 50
               off its place, the largest), the rail's slots; APPROACH lines per slot 0-3 from s >= HANGAR_OUT
               (D4 builds, g_hang_ap in the map: 1.0 s, till within 60 of its approach point g_hang_ap; else 1.5, 150 of the
               drawn Falcon, model root +0x38): frames, the distance's rises (over 5), frames on screen, g_hang_near's bit,
               the distance after (its chase slot)
  --hp N       the Stft's health (+0x240, and g_hp_kept) written N on the first game frame (the jump's
               start from a ship under 295: fly_jump()'s 495 is then a rise over RESPAWN_HP)
  --fire       (with --count) on the rail (g_cine 2) B tapped, the gun centred (no line held); --kill T with
               --count: at g_hang_t T + slot x 1.0 each of the four slots' TIEs written health 0 (a downed one, as a hit);
               DOWN lines: a TIE of the four slots from its first health <= 0 on, each 0.5 s its health, place's distance
               to the Falcon, drawn; DOWNSUM per object: frames after its fall, the largest health, the least distance to
               the Falcon, frames drawn, frames within 1000, frames back > 0 (a relaunch seen)
  --turn EV    (no run; was gallrun/cam_turn.py) <rom> is a --cam log: from its CAMEV EV (native0->1 or jump) on --turn-n
               (300) game frames: the Stft's place step d_sp at the event against the 5 before, the largest forward turn
               d_sfw a frame (deg), the frames over 3.0, the frame the turn is under 0.2, the frames with the Falcon off
               screen (onscr 0), the screen step d_scr at the event / next against the frame before, the largest eye step
  --light OUT  (was gallrun/falcon_light.py) the Falcon's shading on screen: from --from STATE, a
               GLideN64 shot at each of the VIs --light-at (60,240) after the load, then the same moment again with the
               Falcon (the Stft's model root +0xB4, its show byte) hidden every VI (drawing only: the same course); the
               pixels that differ (the largest patch) are the Falcon's. A LIGHT line per moment: its pixels, luminance
               (Rec. 601) mean, sd (the spread), p10 / p90; LIGHTSUM. The visible shot copied to OUT_<vi>.png, the mask to
               OUT_<vi>_mask.png; the shots stay in run/shots/<SHOTS>/
  --light-hide or  (with --light) the Outrider measured instead: its meshes (0x801A3C64/7C/94, +2's byte) hidden
  --fade       per game frame of the mission a FADE line when the screen fade (0x800D0804 s16 r, g,
               b, a), MSG_HOLD, the Stft's health (+0x240) or state (+0x230) changes (else every 30): those, g_native,
               g_rogue, g_fj_t, the frame's game time; FADESUM: the frames with a fade up (a > 0) while MSG_HOLD is
               set, the longest run of an unchanged fade under a held line, the fade colours seen
  --fade-luke  (with --fade) at the first hit in the native flight (the Stft's health falls) g_rogue written 0 once: Luke's
               held line (LINE_LUKE, finale()) comes up the next frame if the Falcon is within LUKE_NEAR of the battle;
               held lines then let go by A only after 120 VIs (else 30); no hit by VI FADE_FORCE_K (hits are rare: bf88
               had one in 1800 VIs): the game's hit tint written and g_rogue 0 then ("forced" in the check)
  --light-hide fbin  (with --light) falcon.bin's Falcon (0x80500000: +4 count, +8 part list; drawn in
               the mission and, since D9, in Cut 05 and the last scene) hidden: each of its parts' geometry DLs ended at
               its first command (0xB8; the image's copy, IMG_FALCON, is gone)
  --light-hide c05or  (with --light) Cut 05's own Outrider (its mesh 0x80198DA4, +2's byte) hidden; in the stock last
               scene (sub-level 31 without the chain) the Outrider's mesh under 0x80199AC0 the same way
  --light-hide slave  (with --light) Slave I (IMG_SLAVE, GALL +116) hidden the same way
  --look      a LOOK line (gallrun/falcon_look.py: falcon.bin lit / unlit) at each change of the
               sub-level or the look (e.g. --save-at jump: the mission -> the last scene)
  --light-box X0,Y0,X1,Y1  (with --light) the differing pixels taken only inside this box (screen fractions 0..1): the ship
               measured when another one (the Falcon) also differs between the two passes
               LIGHT lines also give the shading across the hull: the mean luma of the mask's outer thirds
               (its box split in three), |left - right|, |top - bottom|, their sum; and the masked mean hue / saturation
               (PIL HSV, 0..255)
  --view N    on the rail before Dash's shot (g_cine 2, g_sc 0) the view key (L, 4 VIs every 30) pressed
               till VIEW_MODE (0x8018E462) is N (4: the inside view), in place of the firing
  --window    per game frame a WIN line when any of these changes: g_sc, g_shot, VIEW_MODE, the
               camera index and the active entry's index, the guns on (Stft +0x70), the show byte of the Stft's nodes +0xB0
               and +0xB4 (0xFF drawn), the HUD x of elements 0 and 20-23 (the sight, the turret's window; -1000 hidden);
               with --shots a shot every 6 game frames of g_shot; WINSUM: g_shot's frames, those with VIEW_MODE 4, index
               4, +0xB4 hidden, the window placed (any of 20-23 x != -1000), and the frames after the shot with VIEW_MODE 4
  --trail     per game frame of the Falcon's jump (g_fj_t >= 0) a TRAIL line: whose trail
               (g_tr_who: 3 the Falcon's), Dash's node (the trail's: count, show byte), its tail (+0x38) and head (+ row 1 x
               100), length, width, the head's distance to the Falcon (Stft +0x50), the tail's to g_fj_from, the head's and
               the Falcon's screen place, eye-to-Falcon; TRAILSUM: the jump's frames (g_fj_t <= FJ_T 2.4), the trail drawn
               (who 3, count 1, show 0xFF, length > 0), its head within 50 of the Falcon, the Falcon on screen, the frames
               it is on screen and further each frame before the flash (g_fj_t < 1.9) and their seconds, the frames before the flash and of them on screen;
               TRAIL's tail scr / scr len (the trail's length on screen), TRAILSUM's largest move of the Falcon's screen
               place from its first by g_fj_t 1.2 and the trail's screen length at the first drawn frame with g_fj_t >= 1.0
  --hull      per game frame of the fly-away (g_away_t >= 0, the jump not begun) a HULL line: the
               Falcon's screen place, the Star Destroyer's hull vertices (IMG_SD_COLL's triangles) on screen and of those
               below the Falcon (screen y greater), MSG_HOLD; with --shots a shot every 15 game frames; HULLSUM: the
               fly-away's frames, those with hull on screen below the Falcon, MSG_HOLD's frames while Lando's line is up,
               frames over the hull, the Stft's health first / least (no hull touch); HULL lines add along / lat
  --away-put DX,DY,DZ  (with --save-at jump) as the towers are written down the Falcon (Stft +0x50, +0x08, its rows) put at
               the battle's middle (IMG_BATTLE) + this, facing the middle, level (as when the last tower was just shot);
               the towers are written only with no held line up (else the fly-away waits under it)
  --reach N   (was scene_reach.py) a REACH line at each sub-level change (and every 300 VIs), A tapped on
               held lines; stops 600 VIs into sub-level 31 (the last scene) or N VIs in; END k31 <the VI of 31 or None>:
               the mission played into the last scene without a hang (e.g. --from run/<build>_jump.st --reach 3000)
  --battle    from --from (_free) the final battle's TIEs near the Falcon by kind (BATTLE / BATTLESUM)
  --stick X   from --from (_free): in the native flight the stick x held at X (A on held lines, nothing
               else); --die S (3) seconds (VIs / 60) after the native flight's first frame the Stft's health written 0 (the
               game's death and respawn). STICK lines every 6 game frames (t, g_start_turn, state, hp, heading); STICKSUM
               per event (start, respawn: the first frame after the death with the state not 5 / 6): the heading's change
               from 1.0 to 2.0 s after it (deg), the time g_start_turn went 0
  (--window / --cam) a LINE row when a line said by the code (say_last(), g_said_last) shows: its index from the table's end,
               the text the game was given (the table entry's), g_sc, g_shot; a SHOTOFF row when g_shot goes 0 after Dash's jump
               (g_sc 2 / 3); with --shots a shot 20 VIs after each LINE
  --check     a CHECK line PASS / FAIL (exit 1 on a FAIL) per summary of the knobs given:
               --battle (from _free): every sample chase <= 2 (FINAL_TIES), bomber <= 1, other <= 8, >= 30 samples;
               --clear (from _end): the first line held > 30 VIs and let go, no TIE drawn within 300 of the Falcon after
               its 30th VI (the fly-off runs under it), HUD 37 and 51 at -1000 through it (no guns, no missiles);
               --stick 80 (from _free): the heading change 1 -> 2 s after the start within 15 % of the one after the
               respawn; --stick 0: g_start_turn 0 by 2.5 s of game time (START_MAX);
               --cam (from _dash, --frames 600): each g_dash_carry start after the load's first frame (Slave I's shot)
               with no eye step over 1.5x the one before and the Falcon on screen;
               --fade --fade-luke (from _free, --frames 600): a hit's tint seen, Luke's line raised at it, <= 2 frames of
               a fade up under a held line;
               --window or --cam (from _dash, or any run that sees the view's return): Lando's "Dash, you coward!" (LINE_COWARD 8) said once, within 0.2 s (12 VIs)
               of g_shot going 0 after Dash's jump (the gunner's view back);
               --view 4 --window (from _rail, --frames 1600): >= 100 shot frames, all VIEW_MODE 4, the window placed <= 2;
               --save-at jump --hull (from _free): >= 150 fly-away frames, the hull below the Falcon >= 80 %, MSG_HOLD 0
               (Lando's line not held), the nose's pitch <= 16 deg;
               --trail (from _jump, --frames 120): >= 60 jump frames, the Falcon's trail drawn on >= 90 % of them (the first
               ~4 are within TRAIL_CAM_GAP of the held eye), the Falcon on screen every frame before the flash (g_fj_t < 1.9)
Prints HANG lines (every 6 game frames), HP lines (a health change), a summary per object."""
import os, sys, math, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
ap = argparse.ArgumentParser()
ap.add_argument('rom'); ap.add_argument('--make', default=''); ap.add_argument('--kill', type=float, default=-1)
ap.add_argument('--aim', type=int, default=0); ap.add_argument('--secs', type=float, default=14); ap.add_argument('--shots', action='store_true')
ap.add_argument('--plant', type=float, default=0); ap.add_argument('--watch', default=''); ap.add_argument('--cine', type=int, default=2)
ap.add_argument('--vel', action='store_true'); ap.add_argument('--clear', action='store_true'); ap.add_argument('--lead', default='')
ap.add_argument('--chase', type=float, default=0); ap.add_argument('--all', action='store_true')
ap.add_argument('--from', dest='frm', default=''); ap.add_argument('--save-at', dest='save_at', default='')
ap.add_argument('--after', type=float, default=3); ap.add_argument('--frames', type=int, default=0)
ap.add_argument('--battle', action='store_true'); ap.add_argument('--stick', type=int, default=None); ap.add_argument('--die', type=float, default=3); ap.add_argument('--count', action='store_true'); ap.add_argument('--fire', action='store_true'); ap.add_argument('--hp', type=int, default=-1); ap.add_argument('--appr-trace', dest='appr_trace', type=int, default=-1); ap.add_argument('--cam', action='store_true'); ap.add_argument('--bolts', action='store_true'); ap.add_argument('--sight', action='store_true'); ap.add_argument('--fade', action='store_true'); ap.add_argument('--fade-luke', dest='fade_luke', action='store_true')
ap.add_argument('--turn', default=''); ap.add_argument('--turn-n', dest='turn_n', type=int, default=300)
ap.add_argument('--look', action='store_true'); ap.add_argument('--light', default=''); ap.add_argument('--light-at', dest='light_at', default='60,240')
ap.add_argument('--view', type=int, default=-1); ap.add_argument('--window', action='store_true'); ap.add_argument('--reach', type=int, default=0)
ap.add_argument('--trail', action='store_true'); ap.add_argument('--hull', action='store_true'); ap.add_argument('--away-put', dest='away_put', default='')
ap.add_argument('--check', action='store_true'); ap.add_argument('--light-box', dest='light_box', default=''); ap.add_argument('--light-hide', dest='light_hide', default='falcon', choices=['falcon', 'or', 'fbin', 'slave', 'c05or'])
A = ap.parse_args()
CHECKS = []


def check(name, ok, why):                                        # --check: a CHECK line per guarded behaviour
    CHECKS.append(ok); print(f'CHECK ({name})', 'PASS' if ok else 'FAIL', why, flush=True)
if A.turn:                                                       # (offline: a --cam log's switch / jump)
    import re
    L = open(A.rom).read().splitlines(); ev = A.turn
    k0 = next(int(re.search(r' k (\d+)', l).group(1)) for l in L if l.startswith(f'CAMEV {ev} '))
    num = lambda l, key: (lambda m: None if not m or m.group(1) == 'None' else float(m.group(1)))(re.search(rf' {key} (-?[\d.]+|None)', l))
    C = [(int(l.split()[0]), l) for l in L if re.match(r'\d+ CAM ', l)]
    before = [l for k, l in C if k < k0][-6:]; after = [l for k, l in C if k >= k0][:A.turn_n]
    sp_b = [num(l, 'd_sp') for l in before[1:] if num(l, 'd_sp') is not None]
    scr_b = num(before[-1], 'd_scr') if before else None
    turns = [num(l, 'd_sfw') or 0 for l in after]
    off = sum(1 for l in after if ' onscr 0' in l)
    done = next((i for i, t in enumerate(turns[1:], 1) if t < 0.2 and max(turns[i:i + 10] or [0]) < 0.2), None)
    eyes = [num(l, 'd_eye') or 0 for l in after]
    print(f'TURN {ev} at k {k0}: d_sp at it {num(after[0], "d_sp")} / next {num(after[1], "d_sp")} vs before {sp_b} (max {max(sp_b) if sp_b else None});'
          f' d_scr at it {num(after[0], "d_scr")} next {num(after[1], "d_scr")} frame before {scr_b}; forward turn max {max(turns):.2f} deg a frame,'
          f' {sum(1 for t in turns if t > 3.0)} frames over 3.0 (first frames {[round(t, 2) for t in turns[:8]]}), under 0.2 from frame {done};'
          f' Falcon off screen {off} of {len(after)} frames; eye step max {max(eyes):.1f}; hp first/last {num(after[0], "hp")}/{num(after[-1], "hp")}')
    scr60 = [(num(l, 'd_scr') or 0, num(l, 'd_eye') or 0, k) for k, l in C if k >= k0][:61]
    scr5 = [num(l, 'd_scr') or 0 for l in before[1:]]
    big = max(scr60)
    print(f'SCR60 {ev}: d_scr before {[round(x, 2) for x in scr5]} (max {max(scr5 or [0]):.2f}); at it + 60 frames max {big[0]:.2f} at k {big[2]}'
          f' (eye step there {big[1]:.1f}); first {[round(x[0], 2) for x in scr60[:12]]}')
    sys.exit(0 if all(CHECKS) else 1)
if A.secs == 14 and (A.save_at or A.frames or A.reach): A.secs = 1e9         # (these stop on their own)
ROM = os.path.abspath(A.rom)
BUILD = os.path.basename(os.path.dirname(ROM))
os.environ.setdefault('SHOTS', f'pt7r_hang_{BUILD}')
import paths
import m64
from m64 import Emu, BTN, HERE

RUN = paths.RUN
ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
MLV = 32 if 'g_levels' in SYM else 6           # the mission's sub-level (32 from bf49)
LEVEL, HOLD, GALL, TIEF = 0x8013CE0E, 0x800DD2D0, 0x80628000, 0x80112D48
HANGAR_GAP = 0.8
STATE = os.path.join(RUN, f'{BUILD}_end.st')
start = A.make or (os.path.join(HERE, A.frm) if A.frm and not os.path.isabs(A.frm) else A.frm) or STATE
if not os.path.exists(start): sys.exit(f'no {start}: make it with --make <state in the mission>')
e = Emu(ROM, video=m64.GLN); f32 = e.rf
if A.frames:                         # --frames counts game frames, which stop under a held line or after finish():
    os.environ.setdefault('M64MAXVI', str(600 + 6 * A.frames))   # a VI bound too (m64.py M64MAXVI; ~3x a frame's 2 VIs)
if A.reach: os.environ.setdefault('M64MAXVI', str(A.reach + 1200))
RCH = {'lv': None, 'k31': None}


def light_run(state, out, at_list):                              # --light (was falcon_light.py)
    import shutil
    import numpy as np
    from PIL import Image
    SD = e.shot_dir; plan = []; L_ = {'i': 0, 'ph': 'load'}

    def root():
        sf = e.r32(0x80112CB8 + 0x10) if e.r32(0x80112CB8 + 8) else 0
        rt = e.r32(sf + 0xB4) if sf else 0
        return rt if 0x80000000 <= rt < 0x80800000 else 0

    def lscript(e, n):                                           # per moment: load, run to it, the visible shot; load
        if n == 1: e.unlimit()                                   # again, run with the Falcon hidden every VI, a shot
        if n < 60: return
        if L_['i'] >= len(at_list):
            L_['end'] = L_.get('end', n + 15)
            if n >= L_['end']: e.stop()
            return
        at = at_list[L_['i']]
        if L_['ph'] in ('load', 'load2'): e.load_state(state); L_['ph'] = 'run' if L_['ph'] == 'load' else 'hid'; L_['b'] = n + 1; return
        k = n - L_['b']
        if L_['ph'] == 'run' and k == at: e.shot(); plan.append((at, 'vis', 0)); L_['ph'] = 'gap'; L_['g'] = n + 10; return
        if L_['ph'] == 'gap':
            if n >= L_['g']: L_['ph'] = 'load2'
            return
        if L_['ph'] == 'hid':
            if A.light_hide == 'or':                                 # the Outrider's meshes (glows, hull): +2 not drawn
                for mn in (0x801A3C64, 0x801A3C7C, 0x801A3C94): e.w32(mn, e.r32(mn) & 0xFFFF00FF)
            elif A.light_hide == 'c05or':                            # Cut 05's Outrider / the stock last scene's
                for mn in (0x80198DA4, e.r32(e.r32(0x80199AC0 + 0x10)) if e.r16(0x8013CE0E) == 31 else 0):
                    if 0x80000000 <= mn < 0x80800000: e.w32(mn, e.r32(mn) & 0xFFFF00FF)
            elif A.light_hide in ('fbin', 'slave'):                  # falcon.bin / Slave I: its geometry DLs end at once
                b_ = 0x80500004 if A.light_hide == 'fbin' else 0x80628000 + 116
                n_, l_ = e.r32(b_), e.r32(b_ + 4)
                for i in range(n_ if 0 < n_ < 64 else 0):
                    g_ = e.r32(e.r32(l_ + 4 * i) + 0x28); e.w32(g_, 0xB8000000); e.w32(g_ + 4, 0)
            else:
                rt = root()
                if rt: e.w32(rt, e.r32(rt) & 0xFF00FFFF)             # (+2's high byte: not drawn)
            if k == at: e.shot(); plan.append((at, 'hid', 0))
            if k == at + 10: L_['i'] += 1; L_['ph'] = 'load'
    e.run(lscript)
    files = sorted((f for f in os.listdir(SD) if f.endswith('.png')), key=lambda f: os.path.getmtime(os.path.join(SD, f)))
    assert len(files) >= len(plan), f'{len(files)} shots for {len(plan)} asked'
    files = files[-len(plan):]
    lum = lambda a: 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    res = []
    for at in at_list:
        vis = [files[i] for i, p in enumerate(plan) if p[0] == at and p[1] == 'vis']
        hid = [files[i] for i, p in enumerate(plan) if p[0] == at and p[1] == 'hid']
        if not vis or not hid: print('LIGHT', at, 'missing shots', flush=True); continue
        img = np.asarray(Image.open(os.path.join(SD, vis[0])).convert('RGB')).astype(float)
        B = np.asarray(Image.open(os.path.join(SD, hid[0])).convert('RGB')).astype(float)
        m = np.abs(img - B).max(axis=2) > 24
        if A.light_box:                                          # (only inside the box: another ship's patch left out)
            bx = [float(x) for x in A.light_box.split(',')]; H_, W_ = m.shape
            bm = np.zeros_like(m); bm[int(bx[1] * H_):int(bx[3] * H_), int(bx[0] * W_):int(bx[2] * W_)] = True; m = m & bm
        from scipy import ndimage                                # (the Falcon: the largest patch; TIEs and the Outrider
        lab, nl = ndimage.label(ndimage.binary_closing(m, iterations=2))   # fly a little apart in the second pass)
        if nl: m = m & (lab == 1 + int(np.argmax(ndimage.sum(np.ones_like(lab), lab, range(1, nl + 1)))))
        Lm = lum(img)[m]
        if Lm.size < 50: print('LIGHT', at, 'falcon pixels', int(Lm.size), '(too few)', flush=True); continue
        r = (at, int(Lm.size), Lm.mean(), Lm.std(), np.percentile(Lm, 10), np.percentile(Lm, 90))
        Lf = lum(img); ys, xs = np.nonzero(m); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        X = np.arange(Lf.shape[1])[None, :]; Y = np.arange(Lf.shape[0])[:, None]
        th = lambda sel: Lf[m & sel].mean()                      # (outer thirds of the mask's box: D4's shading)
        dlr = abs(th(X < x0 + (x1 - x0) / 3) - th(X >= x1 - (x1 - x0) / 3))
        dtb = abs(th(Y < y0 + (y1 - y0) / 3) - th(Y >= y1 - (y1 - y0) / 3))
        hsv = np.asarray(Image.open(os.path.join(SD, vis[0])).convert('RGB').convert('HSV')).astype(float)
        r = r + (dlr, dtb, hsv[..., 0][m].mean(), hsv[..., 1][m].mean(), *img[m].mean(axis=0))
        res.append(r)
        shutil.copy(os.path.join(SD, vis[0]), f'{out}_{at}.png')
        Image.fromarray((m * 255).astype(np.uint8)).save(f'{out}_{at}_mask.png')
        print(f'LIGHT vi {at} falcon pixels {r[1]} luma mean {r[2]:.1f} sd {r[3]:.1f} p10 {r[4]:.1f} p90 {r[5]:.1f} '
              f'thirds |L-R| {r[6]:.1f} |T-B| {r[7]:.1f} sum {r[6] + r[7]:.1f} hue {r[8]:.1f} sat {r[9]:.1f} '
              f'rgb {r[10]:.1f} {r[11]:.1f} {r[12]:.1f} (r/g {r[10] / max(r[11], 1):.3f} b/g {r[12] / max(r[11], 1):.3f}) -> {out}_{at}.png', flush=True)
    print('LIGHTSUM', ' | '.join(f'vi {r[0]} px {r[1]} sd {r[3]:.1f} p90-p10 {r[5] - r[4]:.1f} thirds {r[6] + r[7]:.1f} hue {r[8]:.1f}' for r in res), flush=True)


if A.light:
    light_run(start, os.path.abspath(A.light), [int(x) for x in A.light_at.split(',')])
    sys.exit(0 if all(CHECKS) else 1)
S = {'h': 0, 'saved': not A.make, 'hp': {}, 'objs': {}, 'end': None, 'killed': None}


def v3(a): return [f32(a + 4 * i) for i in range(3)]


def rpos(k):
    rt = e.r32(GALL + 20) + 0x38
    return [f32(rt + k * 0x54 + 4 * i) for i in range(3)]


def pilot(node):                                         # work/chain_take.py's
    if not e.r32(SYM['g_fly_on']): return 0, 0, 0
    pos = v3(SYM['g_fly_pos']); tp = rpos(node + 6); yaw = f32(SYM['g_fly_yaw'])
    err = (math.atan2(tp[1] - pos[1], tp[0] - pos[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
    return BTN['A'], max(-80, min(80, int(-err * 160))), max(-80, min(80, int(-(tp[2] - 10 - pos[2]) * 2)))


def chase_at(tgt):                                       # chain_take.py chase(), at tgt
    pos = v3(SYM['g_fly_pos']); yaw, pitch = f32(SYM['g_fly_yaw']), f32(SYM['g_fly_pitch']); v = [tgt[j] - pos[j] for j in range(3)]
    ey = (math.atan2(v[1], v[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
    tp = -math.atan2(v[2], math.hypot(v[0], v[1]))
    return (BTN['A'] | (BTN['B'] if abs(ey) < 0.3 and e.r32(SYM['g_ov_frames']) % 6 < 3 else 0),
            max(-80, min(80, int(-ey * 700))), max(-80, min(80, int((tp - pitch) / 0.8 * 80)))), ey


def idx(t): return (t - e.r32(TIEF + 0x10)) // e.r32(TIEF + 0xC)


def all_ties(k, tag, ht, chase):                         # --all: every TieF object
    tf, sz, n = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), e.r32(TIEF + 8)
    chor = e.r32(0x80112A78 + 0x10); sf = e.r32(0x80112CB8 + 0x10)
    c = v3(chor + 0x50) if chor else [0, 0, 0]; fp = v3(sf + 0x50) if sf else c
    nat = e.r32(SYM['g_native']); flz = f32(SYM['g_fly_pos'] + 8)
    out = []
    for i in range(min(n, 24)):
        t = tf + i * sz; q = v3(t + 0x50); hp = f32(t + 0x60); ty = e.r32(t + 0x70) & 0xFF
        st_ = e.r16(t + 0xA8); st_ -= 65536 if st_ > 32767 else 0
        nd = e.r32(t + 0x94); dr = 0x80000000 <= nd < 0x80800000 and (e.r16(nd + 2) >> 8) == 0xFF
        dq = v3(nd + 0x38) if 0x80000000 <= nd < 0x80800000 else q
        battle = n >= 13 and i + 7 >= n; wave = ty != 1 and not battle
        parked = q[2] < -4000 and (not nat or q[2] < flz - 1500)
        what = ('slot%d' % chase.index(t)) if t in chase else 'battle' if battle else 'wave' if wave else \
               'parked' if parked else 'dead' if not hp > 0 else 'chaser-noslot'
        ld = e.r32(t + 0xBC); li = (ld - tf) // sz if sz and tf <= ld < tf + 32 * sz else None
        out.append(dict(i=i, what=what, lead=li, hp=round(hp, 1), st=st_, drawn=dr, pos=[round(x) for x in q], node=[round(x) for x in dq],
                        chor_d=round(math.dist(q, c)), falcon_d=round(math.dist(q, fp)), node_falcon_d=round(math.dist(dq, fp))))
    print(k, 'ALL', tag, 'g_hang_t', round(ht, 2), 'g_cine', e.r32(SYM['g_cine']), 'g_cine_t', round(f32(SYM['g_cine_t']), 2),
          'chor', [round(x) for x in c], 'falcon', [round(x) for x in fp], 'n', n, flush=True)
    for o in out: print('   ', o, flush=True)
    S.setdefault('all', []).append((tag, ht, out))


# --count (was work/hang_n.py): from the start state to the free flight, no firing


PERSP, ACTIVE_CAMERA, CAMERA_INDEX, VIEW_BLEND, MSG_HOLD = 0x80192F14, 0x800D08A4, 0x800D08A8, 0x80111760, 0x800DD2D0
HUD_POS = 0x80111110                                      # the HUD elements' places (s16 x, y; -1000 hidden)
CLASS_STFT, CHOR_SIGHT, FALCON_RAM, HDR_TURRET = 0x80112CB8, 0x14C, 0x80500000, 16
P = {'ov': None, 'n': 0, 'prev': None, 'hist': [], 'ev': [], 'saved': {}, 'last_save': None, 'bolt': {}, 'bolts': [],
     'sight': [], 'vi_eye': None, 'twd': False}
SAVE_AT = [x for x in A.save_at.split(',') if x]


def s32(a): x = e.r32(a); return x - (1 << 32) if x >> 31 else x


def r8(a): return e.r32(a & ~3) >> (24 - 8 * (a & 3)) & 0xFF


def s16(a): x = e.r16(a); return x - 65536 if x > 32767 else x


def stft_root():
    sf = e.r32(CLASS_STFT + 0x10) if e.r32(CLASS_STFT + 8) else 0
    rt = e.r32(sf + 0xB4) if sf else 0
    return sf, (rt if 0x80000000 <= rt < 0x80800000 else 0)


BLEND_VIEW = 0x80111788                                  # the view drawn while a blend runs (index -1): 0x80009838 lerps
                                                         # the two entries into it (rows +0, +0x10, +0x20, eye +0x30)


def view():                                              # the drawn view: the active entry's, or the blend's
    if s32(CAMERA_INDEX) == -1: b = BLEND_VIEW
    else:
        c = e.r32(ACTIVE_CAMERA)
        if not 0x80000000 <= c < 0x80800000: return None
        b = c + 0x14
    return v3(b), v3(b + 0x10), v3(b + 0x20), v3(b + 0x30)


def screen(p):                                           # through the drawn view (or_pace.py's)
    vw = view()
    if not vw: return None
    R, F, U, E = vw
    v = [p[i] - E[i] for i in range(3)]; z = sum(F[i] * v[i] for i in range(3))
    if z < 1: return None
    th = math.tan(math.radians(f32(PERSP)) / 2); asp = f32(PERSP + 4) or 4 / 3
    return (round(160 + 160 * sum(R[i] * v[i] for i in range(3)) / z / (th * asp), 1),
            round(120 - 120 * sum(U[i] * v[i] for i in range(3)) / z / th, 1))


def nrm(v): l = math.hypot(*v); return [x / l for x in v] if l > 1e-9 else v


# --count (moved after screen(): the approach summary uses it)
# --battle: from _free, the final battle's TIEs: every 30 game frames for --secs (20) of the native
# flight, the TieF objects alive and drawn within 2000 of the Falcon by kind (chase: in g_chase[], bomber: 10-13, other),
# and each one's put-backs (health <= 0 -> > 0). B tapped (the guns), no line held.
if A.battle:
    STFT = 0x80112CB8; BS = 20 if A.secs == 14 else A.secs
    B_ = {'t0': None, 'last': {}, 'back': {}, 'rows': [], 'ov': None, 'end': None, 'down': {}}

    def bframe(k):
        if not e.r32(SYM['g_native']): return
        if B_['t0'] is None: B_['t0'] = k
        t_ = (k - B_['t0']) / 60
        if t_ > BS: B_['end'] = f'{BS} s'; e.stop(); return
        sf = e.r32(STFT + 0x10); fp = v3(sf + 0x50) if sf else [0, 0, 0]
        tf, sz, n = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), e.r32(TIEF + 8)
        chase = [e.r32(SYM['g_chase'] + 4 * i) for i in range(6)]
        cnt = {'chase': 0, 'bomber': 0, 'other': 0}; ids = []
        for i in range(min(n, 32)):
            t = tf + i * sz; hp = f32(t + 0x60); nd = e.r32(t + 0x94)
            drawn = 0x80000000 <= nd < 0x80800000 and (e.r16(nd + 2) >> 8) == 0xFF
            was = B_['last'].get(i)
            if was is not None and not was > 0 and hp > 0: B_['back'][i] = B_['back'].get(i, 0) + 1; print(k, 'BACK obj', i, 'at', round(t_, 2), 's', flush=True)
            if was is not None and was > 0 and not hp > 0: B_['down'][i] = B_['down'].get(i, 0) + 1
            B_['last'][i] = hp
            if hp > 0 and drawn and math.dist(v3(t + 0x50), fp) < 2000:
                kind = 'chase' if t in chase else 'bomber' if 10 <= i <= 13 else 'other'
                cnt[kind] += 1; ids.append(i)
        if not B_['rows'] or k - B_['rows'][-1][0] >= 30:
            B_['rows'].append((k, round(t_, 1), dict(cnt), ids))
            print(k, 'BATTLE t', round(t_, 1), 's', cnt, 'objs', ids, 'TieF n', n, flush=True)

    def bscript(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(start)
        if n < 64: return
        k = n - 64; ov = e.r32(SYM['g_ov_frames'])
        if ov != B_['ov']: B_['ov'] = ov; bframe(k)
        e.pad(BTN['A'] if e.r16(HOLD) and k % 60 < 5 else BTN['B'] if k % 6 < 3 else 0, 0, 0)
        if k > 60 * 60 * 3: B_['end'] = 'timeout'; e.stop()

    os.environ.setdefault('M64MAXVI', str(int(BS * 60 * 3 + 3000)))
    e.run(bscript)
    R_ = B_['rows']; tot = [sum(r[2].values()) for r in R_]
    print(f'BATTLESUM build {BUILD}: {B_["end"]}; samples {len(R_)}; near & drawn total max {max(tot or [0])} mean {sum(tot) / max(len(tot), 1):.1f};',
          'by kind max', {kd: max((r[2][kd] for r in R_), default=0) for kd in ('chase', 'bomber', 'other')},
          'objects seen', sorted({i for r in R_ for i in r[3]}), 'downs', B_['down'], 'put-backs', B_['back'])
    if A.check:
        mx = {kd: max((r[2][kd] for r in R_), default=0) for kd in ('chase', 'bomber', 'other')}
        check('battle', len(R_) >= 30 and mx['chase'] <= 2 and mx['bomber'] <= 1 and mx['other'] <= 8,
              f"samples {len(R_)} (>= 30), max chase {mx['chase']} (<= 2), bomber {mx['bomber']} (<= 1), other {mx['other']} (<= 8)")
    sys.exit(0 if all(CHECKS) else 1)
# --stick: the stick held from the native flight's first frame, then a death and the respawn: the
# heading's change a second at 1 s after each.
if A.stick is not None:
    STFT = 0x80112CB8
    K_ = {'t0': None, 'ov': None, 'died': None, 'dead': False, 'ev': {}, 'hd': [], 'st0': None, 'end': None}

    def heading(sf):
        return math.degrees(math.atan2(f32(sf + 0x34), f32(sf + 0x30)))

    def kframe(k):
        if not e.r32(SYM['g_native']): return
        held = e.r16(HOLD) != 0                                  # (time: unheld VIs / 60 since the first native frame;
        if K_['t0'] is None: K_['t0'] = k; K_['lk'] = k; K_['ut'] = 0.0   # a held line stops the game's world)
        if not held: K_['ut'] += (k - K_['lk']) / 60
        import struct
        dt_ = struct.unpack('>d', struct.pack('>II', e.r32(0x8018E998), e.r32(0x8018E99C)))[0]   # (the game's frame time,
        dt_ = 1 / 30 if not dt_ > 0.001 else min(dt_, 0.1)       # as common.h frame_dt())
        if not held and K_['t0'] != k: K_['gt'] = K_.get('gt', 0.0) + dt_
        K_['lk'] = k; t_ = K_['ut']
        if not held and 'start' not in K_['ev']: K_['ev']['start'] = t_
        sf = e.r32(STFT + 0x10)
        if not sf: return
        st, hp, gst = e.r32(sf + 0x230), e.r32(sf + 0x240), e.r32(SYM['g_start_turn'])
        hp = hp - (1 << 32) if hp > 0x7FFFFFFF else hp
        if K_['died'] is None and t_ >= A.die: e.w32(sf + 0x240, 0); K_['died'] = k; print(k, 'DIE written at', round(t_, 2), 's', flush=True)
        if st in (5, 6): K_['dead'] = True
        elif K_['dead'] and 'respawn' not in K_['ev']: K_['ev']['respawn'] = t_; print(k, 'RESPAWN at', round(t_, 2), 's hp', hp, flush=True)
        if K_['st0'] is None and not gst: K_['st0'] = (round(t_, 3), round(K_.get('gt', 0.0), 3))
        K_['hd'].append((t_, heading(sf)))
        if len(K_['hd']) % 6 == 1:
            print(k, 'STICK t', round(t_, 2), 'held', int(held), 'start_turn', gst, 'st', st, 'hp', hp, 'heading', round(heading(sf), 2), flush=True)
        if 'respawn' in K_['ev'] and t_ - K_['ev']['respawn'] > 2.5: K_['end'] = 'respawn + 2.5 s'; e.stop()

    def kscript(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(start)
        if n < 64: return
        k = n - 64; ov = e.r32(SYM['g_ov_frames'])
        if ov != K_['ov']: K_['ov'] = ov; kframe(k)
        nat = e.r32(SYM['g_native'])
        e.pad(BTN['A'] if e.r16(HOLD) and k % 60 < 5 else 0, A.stick if nat else 0, 0)
        if k > 60 * 60 * 2: K_['end'] = 'timeout'; e.stop()

    os.environ.setdefault('M64MAXVI', str(int((A.die + 12) * 60 + 3000)))
    e.run(kscript)

    def at(t0, dt):                                              # the heading nearest t0 + dt s (unheld)
        return min(K_['hd'], key=lambda x: abs(x[0] - (t0 + dt)))

    for ev, t0 in K_['ev'].items():
        a, b = at(t0, 1.0), at(t0, 2.0)
        d = (b[1] - a[1] + 180) % 360 - 180
        print(f'STICKSUM {ev} at {t0:.2f} s: heading change 1.0 -> 2.0 s {d:.2f} deg (t {a[0]:.2f} -> {b[0]:.2f})', flush=True)
        K_.setdefault('d', {})[ev] = d
    print(f'STICKSUM build {BUILD} stick {A.stick}: {K_["end"]}; g_start_turn 0 at (VI s, game-time s) {K_["st0"]} unheld from the native start; died at k {K_["died"]}')
    if A.check and A.stick:
        ds, dr = K_.get('d', {}).get('start'), K_.get('d', {}).get('respawn')
        ok = ds is not None and dr and abs(ds - dr) / abs(dr) <= 0.15
        check('stick', ok, f'heading change 1 -> 2 s: start {ds}, respawn {dr} deg' +
              (f' ({100 * abs(ds - dr) / abs(dr):.1f} % apart, <= 15)' if ok is not None and ds is not None and dr else ''))
    elif A.check:
        g = K_['st0'][1] if K_['st0'] else None
        check('stick 0', g is not None and g <= 2.5, f'g_start_turn 0 at {g} s of game time (<= 2.5)')
    sys.exit(0 if all(CHECKS) else 1)
if A.count:
    STFT, MOUTH_R = 0x80112CB8, 300
    CSECS = 300 if A.secs == 14 else A.secs
    D4 = 'g_hang_ap' in SYM                                 # (HANGAR_OUT 1.0, the approach to
    APPR_NEAR, H_OUT = (60, 1.0) if D4 else (150, 1.5)      # g_hang_ap, its point in the frame, within 60; D2: 1.5, 150 of the Falcon)
    C = {'appr': {}, 'h': 0, 'ov': None, 'out': {}, 'launch': {}, 'drawn': {}, 'near': {}, 'rail': [], 'end': None, 't0': None}

    def count_frame(k):
        ht, cine, free = f32(SYM['g_hang_t']), e.r32(SYM['g_cine']), e.r32(SYM['g_free'])
        if free: C['end'] = f'free flight at k {k}'; e.stop(); return
        if ht < 0: return
        if C['t0'] is None: C['t0'] = k
        if (k - C['t0']) / 60 > CSECS: C['end'] = f'{CSECS} s'; e.stop(); return
        tf, sz, n = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), e.r32(TIEF + 8)
        chase = [e.r32(SYM['g_chase'] + 4 * i) for i in range(6)]
        h = e.r32(GALL + 368); mouth = v3(h)                     # IMG_HANGARS record HANGAR_ONE (0)
        sf = e.r32(STFT + 0x10); fp = v3(sf + 0x50) if sf else [0, 0, 0]
        if A.kill >= 0:                                          # (--kill with --count: the four slots downed in turn)
            for sl in range(4):
                t = chase[sl]
                if t and sl not in C.setdefault('killed', set()) and ht >= A.kill + sl and f32(t + 0x60) > 0:
                    e.wf(t + 0x60, 0.0); C['killed'].add(sl); print(k, 'KILL slot', sl, 'obj', idx(t), 'g_hang_t', round(ht, 2), flush=True)
        for sl in range(4):                                      # (the four slots' TIEs: their fall)
            t = chase[sl]
            if t and f32(t + 0x60) > 0: C.setdefault('four', set()).add(idx(t))
        for i in range(min(n, 24)):
            t = tf + i * sz; nd = e.r32(t + 0x94); q = v3(t + 0x50)
            ok = 0x80000000 <= nd < 0x80800000
            drawn = ok and (e.r16(nd + 2) >> 8) == 0xFF; dq = v3(nd + 0x38) if ok else q
            if i in C.get('four', ()) and (i in C.setdefault('down', {}) or not f32(t + 0x60) > 0):
                D_ = C['down'].setdefault(i, {'n': 0, 'hp': -1e9, 'd': 1e9, 'drawn': 0, 'near': 0, 'back': 0, 't0': round(ht, 2), 'lt': -1})
                dd = math.dist(q, fp); D_['n'] += 1; D_['hp'] = max(D_['hp'], f32(t + 0x60)); D_['d'] = min(D_['d'], dd)
                D_['drawn'] += drawn; D_['near'] += dd < 1000; D_['back'] += f32(t + 0x60) > 0
                if D_['n'] == 1: print(k, 'DOWN obj', i, 'fell at g_hang_t', round(ht, 2), 'at', [round(x) for x in q], 'dist', round(dd), flush=True)
                if ht - D_['lt'] >= 0.5:
                    D_['lt'] = ht; print(k, 'DOWN obj', i, 'g_hang_t', round(ht, 2), 'hp', round(f32(t + 0x60), 2), 'dist', round(dd), 'drawn', drawn,
                                         'place', [round(x) for x in q], flush=True)
            if i not in C['out'] and math.dist(q, mouth) < MOUTH_R:
                C['out'][i] = (round(ht, 3), chase.index(t) if t in chase else -1)
                print(k, 'OUT obj', i, 'g_hang_t', round(ht, 3), 'slot', C['out'][i][1], 'place', [round(x) for x in q], flush=True)
            if drawn and math.dist(dq, mouth) < MOUTH_R and i not in C['drawn']:
                C['drawn'][i] = round(ht, 3); print(k, 'DRAWN obj', i, 'g_hang_t', round(ht, 3), 'at the mouth', flush=True)
            if t in chase[:4] and 0 < ht - chase.index(t) * 0.8 <= H_OUT:   # its own launch (HANGAR_OUT): drawn node against its place
                sl = chase.index(t); L = C['launch'].setdefault(i, {'n': 0, 'drawn': 0, 'off': 0, 'max': 0})
                dd = math.dist(dq, q); L['n'] += 1; L['drawn'] += drawn; L['off'] += drawn and dd > 50; L['max'] = max(L['max'], round(dd) if drawn else 0)
            d = min(math.dist(q, fp), math.dist(dq, fp) if drawn else 1e9)
            if d < 1000 and (drawn or f32(t + 0x60) > 0):           # per object: frames near, near and drawn, first / last
                N = C.setdefault('nearn', {}).setdefault(i, [0, 0, None, None]); N[0] += 1; N[1] += drawn
                N[2] = N[2] if N[2] is not None else round(ht, 2); N[3] = round(ht, 2)
            if i in C['near']: continue
            if d < 1000 and (drawn or f32(t + 0x60) > 0):
                C['near'][i] = (round(ht, 3), cine, round(d), drawn)
                print(k, 'NEAR obj', i, 'g_hang_t', round(ht, 3), 'cine', cine, 'dist', round(d), 'drawn', drawn, 'hp', f32(t + 0x60),
                      'slot', chase.index(t) if t in chase else -1, flush=True)
        for sl in range(4):                                      # the approach: from s >= HANGAR_OUT
            s_ = ht - sl * HANGAR_GAP; t = chase[sl]              # each launched slot's distance to the Falcon per game
            if s_ <= 0 or not t: continue                         # frame till within APPR_NEAR, on screen or not
            P_ = C['appr'].setdefault(sl, {'obj': idx(t), 'd': [], 'scr': 0, 'done': None, 'bit': None, 'after': [], 'ld': [], 'lscr': 0})
            _, rt_ = stft_root(); fd = v3(rt_ + 0x38) if rt_ else fp   # the drawn Falcon (in the end scene Chor + g_ship_off,
            dd = math.dist(v3(t + 0x50), fd)                             # not the Stft's place)
            if D4 and s_ >= H_OUT: P_.setdefault('fd', []).append(dd); dd = math.dist(v3(t + 0x50), v3(SYM['g_hang_ap'] + 12 * sl))
            if s_ < H_OUT:                                          # its 1.5 s out of the mouth (HANGAR_OUT): the same numbers
                sc = screen(v3(t + 0x50)); P_['ld'].append(dd); P_['lscr'] += bool(sc and 0 <= sc[0] <= 320 and 0 <= sc[1] <= 240)
                continue
            nb = e.r32(SYM['g_hang_near']) >> sl & 1 if 'g_hang_near' in SYM else 0
            if nb and P_['bit'] is None: P_['bit'] = (round(s_, 2), round(dd))
            if A.appr_trace == sl and P_['done'] is None and D4:   # per game frame: s, d to its point, the point's step, cine, TIE
                ap_ = v3(SYM['g_hang_ap'] + 12 * sl); print(k, 'APTRACE slot', sl, 's', round(s_, 3), 'cine', cine, 'd', round(dd, 1),
                      'pt step', round(math.dist(ap_, P_.get('pap', ap_)), 1), 'tie step', round(math.dist(v3(t + 0x50), P_.get('ptie', v3(t + 0x50))), 1),
                      'pt', [round(x) for x in ap_], 'tie', [round(x) for x in v3(t + 0x50)], 'fal', [round(x) for x in fd], flush=True)
                P_['pap'] = ap_; P_['ptie'] = v3(t + 0x50)
            if P_['done'] is None and nb and D4: P_['done'] = round(s_, 2)   # (APPROACH_MAX: over without near)
            if P_['done'] is None:
                P_['d'].append(dd); sc = screen(v3(t + 0x50)); P_['scr'] += bool(sc and 0 <= sc[0] <= 320 and 0 <= sc[1] <= 240)
                if dd < APPR_NEAR: P_['done'] = round(s_, 2)
            elif len(P_['after']) < 400: P_['after'].append(round(P_['fd'][-1] if D4 else dd))   # (its chase slot: to the drawn Falcon)
        if cine == 2 and (not C['rail'] or ht - C['rail'][-1][0] >= 0.5):
            C['rail'].append((round(ht, 2), sum(1 for t in chase if t)))
            print(k, 'RAIL g_hang_t', round(ht, 2), 'chase filled', C['rail'][-1][1], [((t - tf) // sz if t else None) for t in chase], flush=True)

    def count_script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(start)
        if n < 64: return
        k = n - 64
        hold = e.r16(HOLD); C['h'] = C['h'] + 1 if hold else 0
        ov = e.r32(SYM['g_ov_frames'])
        if ov != C['ov']: C['ov'] = ov; count_frame(k)
        fire = A.fire and not hold and e.r32(SYM['g_cine']) == 2 and k % 6 < 3
        e.pad(BTN['A'] if C['h'] >= 30 and C['h'] % 60 < 5 else BTN['B'] if fire else 0, 0, 0)
        if k > 60 * 60 * 5: C['end'] = 'timeout'; e.stop()

    e.run(count_script)
    o = sorted(C['out'].items(), key=lambda x: x[1][0])
    print(f'SUM build {BUILD}: {C["end"]}; out of the mouth {len(o)}:', [(i, t, sl) for i, (t, sl) in o],
          'gaps', [round(b[1][0] - a[1][0], 3) for a, b in zip(o, o[1:])])
    print('SUM first drawn at the mouth (obj: g_hang_t)', C['drawn'])
    oth = {i: v for i, v in C['near'].items() if i not in C['out']}
    print('SUM others (not out of the mouth) within 1000 of the Falcon before the free flight:', len(oth), oth)
    print('SUM near frames (obj: game frames within 1000, of them drawn, first / last g_hang_t)',
          {i: tuple(v) for i, v in sorted(C.get('nearn', {}).items())})
    print('SUM launch (obj: game frames of its 1.5 s out, drawn, drawn > 50 off its place, largest such)',
          {i: (L['n'], L['drawn'], L['off'], L['max']) for i, L in sorted(C['launch'].items())})
    r = [c for _, c in C['rail']]
    for sl, P_ in sorted(C['appr'].items()):
        d = P_['d']; st = [b - a for a, b in zip(d, d[1:])]; rises = [x for x in st if x > 0]
        af = P_['after']
        print('APPROACH slot', sl, 'obj', P_['obj'], 'frames', len(d), 'first d', round(d[0]) if d else None, 'within', APPR_NEAR, 'at s', P_['done'],
              'rises', len(rises), 'over 5', sum(1 for x in rises if x > 5), 'largest rise', round(max(rises), 1) if rises else 0,
              'on screen', P_['scr'], f'({100 * P_["scr"] / max(len(d), 1):.0f} %)', 'g_hang_near set at (s, d)', P_['bit'],
              'after: d min/median/max', (min(af), sorted(af)[len(af) // 2], max(af)) if af else None,
              '| to the drawn Falcon first/last', (round(P_['fd'][0]), round(P_['fd'][len(d) - 1])) if P_.get('fd') and d else None,
              '| launch + approach on screen', f'{100 * (P_["scr"] + P_["lscr"]) / max(len(d) + len(P_["ld"]), 1):.0f} %', flush=True)
        ld = P_['ld']; lst = [b - a for a, b in zip(ld, ld[1:])]
        print('APPROACH slot', sl, f'launch (s 0..{H_OUT:g}): frames', len(ld), 'd first/last/min', (round(ld[0]), round(ld[-1]), round(min(ld))) if ld else None,
              'rises over 5', sum(1 for x in lst if x > 5), 'on screen', P_['lscr'], f'({100 * P_["lscr"] / max(len(ld), 1):.0f} %)', flush=True)
    for i, D_ in sorted(C.get('down', {}).items()):
        print('DOWNSUM obj', i, 'fell at g_hang_t', D_['t0'], 'frames after', D_['n'], 'largest hp', round(D_['hp'], 2), 'least dist to the Falcon',
              round(D_['d']), 'drawn', D_['drawn'], 'within 1000', D_['near'], 'back > 0', D_['back'], flush=True)
    print('SUM rail chase filled min/max', (min(r), max(r)) if r else None, 'samples', len(r))
    sys.exit(0 if all(CHECKS) else 1)


def ang(a, b):
    a, b = nrm(a), nrm(b)
    return round(math.degrees(math.acos(max(-1, min(1, sum(a[i] * b[i] for i in range(3)))))), 2)


def rows(nd): return [v3(nd + 0x14 + 12 * r) for r in range(3)]


def to_world(R, o, q): return [o[j] + sum(q[r] * R[r][j] for r in range(3)) for j in range(3)]


def to_local(R, o, p):                                   # rows normalised (a scaled root)
    d = [p[j] - o[j] for j in range(3)]
    return [round(sum(d[j] * x for j, x in enumerate(nrm(R[r]))) / max(math.hypot(*R[r]), 1e-9), 2) for r in range(3)]


def cam_frame(k, cine, hold):                            # --cam: one game frame
    c = e.r32(ACTIVE_CAMERA); ok = 0x80000000 <= c < 0x80800000
    vw = view(); eye = vw[3] if vw else [0, 0, 0]; fw = vw[1] if vw else [0, 0, 0]   # (the drawn view: the blend's in a blend)
    sf, rt = stft_root(); fal = v3(rt + 0x38) if rt else (v3(sf + 0x50) if sf else [0, 0, 0])
    sc = screen(fal)
    r = dict(k=k, ov=P['ov'], cine=cine, ct=round(f32(SYM['g_cine_t']), 3), sc=s32(SYM['g_sc']), shot=s32(SYM['g_shot']),
             hold=s16(MSG_HOLD), idx=s32(CAMERA_INDEX), ent=(c - e.r32(0x800D08A0)) // 0x80 if ok and c >= e.r32(0x800D08A0) and c - e.r32(0x800D08A0) < 0x80 * 16 else hex(c),
             bl=(s16(VIEW_BLEND + 4), s16(VIEW_BLEND + 6), round(f32(VIEW_BLEND + 0x20), 3), round(f32(VIEW_BLEND + 0x24), 3)),
             eye=eye, fw=fw, ik=[f32(SYM['g_ik'] + 4 * i) for i in range(6)], seen=[f32(SYM['g_cam_seen'] + 4 * i) for i in range(6)],
             off=v3(SYM['g_ship_off']), fal=fal, scr=sc, nat=e.r32(SYM['g_native']), rail=e.r32(SYM['g_rail']),
             cs={n: round(f32(SYM[n] + 24), 3) for n in CARRIES if n in SYM})
    r['fj'] = round(f32(SYM['g_fj_t']), 3) if 'g_fj_t' in SYM else -1
    r['away'] = round(f32(SYM['g_away_t']), 3) if 'g_away_t' in SYM else -1
    r['sp'] = v3(sf + 0x50) if sf else [0, 0, 0]; r['sfw'] = v3(sf + 0x30) if sf else [0, 1, 0]
    e6 = e.r32(0x800D08A0) + 6 * 0x80; p8 = e.r32(e6 + 8) if 0x80000000 <= e6 < 0x80800000 else 0
    r['hp'] = s32(sf + 0x240) if sf else None                  # (the Stft's health, int, 495 full)
    r['sky8'] = 'fjcam' if 'g_fj_cam' in SYM and p8 == SYM['g_fj_cam'] else hex(p8)
    pv = P['prev']
    r['d_sp'] = round(math.dist(r['sp'], pv['sp']), 2) if pv else None
    r['d_sfw'] = ang(r['sfw'], pv['sfw']) if pv and math.hypot(*r['sfw']) > 1e-6 and math.hypot(*pv['sfw']) > 1e-6 else None
    r['d_eye'] = round(math.dist(eye, pv['eye']), 2) if pv else None
    r['d_off'] = round(math.dist(r['off'], pv['off']), 2) if pv else None
    r['d_fal'] = round(math.dist(fal, pv['fal']), 2) if pv else None
    r['d_scr'] = round(math.dist(sc, pv['scr']), 2) if pv and sc and pv['scr'] else None
    r['d_eyefal'] = round(math.dist(eye, fal), 1)
    r['d_ik'] = round(math.dist(r['ik'][:3], pv['ik'][:3]), 2) if pv else None
    ev = []
    if pv:
        if cine == 1 and pv['cine'] != 1: ev.append('cine->1')
        if cine == 2 and pv['cine'] != 2: ev.append('cine->2')
        if r['hold'] and not pv['hold']: ev.append('hold-rise')
        if not r['hold'] and pv['hold']: ev.append('hold-fall')
        if r['sc'] != pv['sc']: ev.append('sc%d->%d' % (pv['sc'], r['sc']))
        if r['shot'] != pv['shot']: ev.append('shot%d->%d' % (pv['shot'], r['shot']))
        if r['idx'] != pv['idx']: ev.append('idx%d->%d' % (pv['idx'], r['idx']))
        if r['nat'] != pv['nat']: ev.append('native%d->%d' % (pv['nat'], r['nat']))
        if r['away'] >= 0 > pv['away']: ev.append('away')
        if r['fj'] >= 0 > pv['fj']: ev.append('jump')
    r['ev'] = ev
    print(k, 'CAM', 'ov', r['ov'], 'cine', cine, 'ct', r['ct'], 'sc', r['sc'], 'shot', r['shot'], 'hold', r['hold'], 'nat', r['nat'],
          'ent', r['ent'], 'idx', r['idx'], 'blend', r['bl'], 'eye', [round(x, 1) for x in eye], 'd_eye', r['d_eye'],
          'fw', [round(x, 3) for x in fw], 'ik', [round(x, 1) for x in r['ik']], 'd_ik', r['d_ik'], 'seen', [round(x, 1) for x in r['seen']],
          'off', [round(x, 1) for x in r['off']], 'd_off', r['d_off'], 'fal', [round(x, 1) for x in fal], 'd_fal', r['d_fal'],
          'carry', r['cs'], 'onscr', int(bool(sc) and 0 <= sc[0] <= 320 and 0 <= sc[1] <= 240),
          'fj', r['fj'], 'away', r['away'], 'sp', [round(x, 1) for x in r['sp']], 'd_sp', r['d_sp'], 'sfw', [round(x, 3) for x in r['sfw']],
          'd_sfw', r['d_sfw'], 'sky8', r['sky8'], 'hp', r['hp'], 'eye-fal', r['d_eyefal'], 'e3-fal', round(math.dist(v3(e.r32(0x800D08A0) + 3 * 0x80 + 0x44), fal), 1), 'scr', sc, 'd_scr', r['d_scr'], 'EV' if ev else '', ev if ev else '', flush=True)
    if 'sc0->1' in ev:                                   # D2's order: what g_cam_seen holds as the shot begins
        print(k, 'ORDER g_sc 0->1: g_cam_seen eye', [round(x, 1) for x in r['seen'][:3]], 'eye the frame before', [round(x, 1) for x in pv['eye']],
              'diff', round(math.dist(r['seen'][:3], pv['eye']), 2), '| g_cam_seen the frame before', [round(x, 1) for x in pv['seen'][:3]],
              'diff to the eye 2 frames before', round(math.dist(pv['seen'][:3], P['hist'][-2]['eye']), 2) if len(P['hist']) > 1 else None,
              '| this eye', [round(x, 1) for x in eye], 'g_ik eye', [round(x, 1) for x in r['ik'][:3]], 'eye-g_ik', round(math.dist(eye, r['ik'][:3]), 2),
              '| shot eye - g_cam_seen', round(math.dist(r['ik'][:3], r['seen'][:3]), 1), flush=True)
    if 'jump' in ev:                                     # the view drawn the frame before vs the held copy
        cp = [f32(SYM['g_fj_cam'] + 4 * i) for i in range(16)] if 'g_fj_cam' in SYM else None
        tk = e.r32(0x80112EF8 + 0x10); tm = [f32(tk + 0x20 + 4 * i) for i in range(16)]   # (Trak 0's matrix now)
        print(k, 'JUMPVIEW before: idx', pv['idx'], 'ent', pv['ent'], 'eye', [round(x, 1) for x in pv['eye']], 'fw', [round(x, 3) for x in pv['fw']],
              '| g_fj_cam eye', [round(x, 1) for x in cp[12:15]] if cp else None, 'fw', [round(x, 3) for x in cp[4:7]] if cp else None,
              'eye diff', round(math.dist(cp[12:15], pv['eye']), 1) if cp else None, 'fw diff deg', ang(cp[4:7], pv['fw']) if cp else None,
              '| Trak 0 eye', [round(x, 1) for x in tm[12:15]], 'vs before eye diff', round(math.dist(tm[12:15], pv['eye']), 1),
              'fw diff deg', ang(tm[4:7], pv['fw']), '| now idx', r['idx'], 'ent', r['ent'], 'eye', [round(x, 1) for x in eye], 'fw', [round(x, 3) for x in fw], flush=True)
    P['hist'].append(r)
    for x in ev: P['ev'].append((len(P['hist']) - 1, x))
    P['prev'] = r


CARRIES = ('cine.carry', 'g_dash_carry', 'g_sky_carry', 'g_gun_carry')   # (carry_t, share at +24)


def carry_summary():                                     # --cam: CARRYSUM per carry that started in the run
    H = P['hist']
    for n in CARRIES:
        cs = [h['cs'].get(n, 0) for h in H]               # each start: the share up from 0 (or back up: a new carry)
        for i0 in [i for i in range(len(H)) if cs[i] > 0 and (i == 0 or cs[i] > max(cs[i - 1], 0) * 1.5 + 1e-6)]:
            carry_one(n, H, i0)


def inner(sc): return bool(sc) and 48 <= sc[0] <= 272 and 36 <= sc[1] <= 204   # the inner 70 %


def carry_one(n, H, i0):
        i5 = next((i for i in range(i0, len(H)) if H[i]['cs'].get(n, 0) < 0.05), None)
        span = H[i0:i5 if i5 is not None else len(H)]
        before = [h['d_eye'] for h in H[max(0, i0 - 5):i0] if h['d_eye'] is not None]
        mb = sum(before) / len(before) if before else None
        st = [h['d_eye'] for h in span if h['d_eye'] is not None]
        rel = [round(span[j]['d_eye'] / span[j - 1]['d_eye'], 2) if span[j - 1]['d_eye'] else None for j in range(1, len(span))]
        fb = [h['d_fal'] for h in H[max(0, i0 - 5):i0] if h['d_fal'] is not None]
        so = [h['d_off'] for h in span if h['d_off'] is not None]
        P.setdefault('carries', []).append((n, H[i0]['k'], sum(1 for j in range(1, len(span)) if rel[j - 1] and rel[j - 1] > 1.5),
                                            sum(1 for h in span if not (h['scr'] and 0 <= h['scr'][0] <= 320 and 0 <= h['scr'][1] <= 240)), len(span)))
        print('CARRYSUM', n, 'start k', H[i0]['k'], 'share<0.05 at k', H[i5]['k'] if i5 is not None else None,
              's', round((H[i5]['k'] - H[i0]['k']) / 60, 2) if i5 is not None else None,
              '| eye step: mean5 before', round(mb, 2) if mb else mb, 'first 3', st[:3], 'max', max(st, default=None),
              'max/mean5', round(max(st) / mb, 2) if mb and st else None,
              'steps > 1.5x the step before (step, ratio)', [(span[j]['d_eye'], rel[j - 1]) for j in range(1, len(span)) if rel[j - 1] and rel[j - 1] > 1.5][:8],
              '| off step max', max(so, default=None), 'Falcon step mean5 before', round(sum(fb) / len(fb), 2) if fb else None,
              '| frames off screen', sum(1 for h in span if not (h['scr'] and 0 <= h['scr'][0] <= 320 and 0 <= h['scr'][1] <= 240)), 'of', len(span),
              '| outside the inner 70 %', sum(1 for h in span if not inner(h['scr'])),
              '| screen step first 3', [h['d_scr'] for h in span[:3]], 'max', max((h['d_scr'] for h in span if h['d_scr'] is not None), default=None),
              'max after the first 2', max((h['d_scr'] for h in span[2:] if h['d_scr'] is not None), default=None), flush=True)


def cam_summary():
    carry_summary()
    H = P['hist']
    for i, x in P['ev']:
        out = []
        for q in ('d_eye', 'd_off', 'd_fal', 'd_scr', 'd_ik', 'd_sp', 'd_sfw'):
            before = [h[q] for h in H[max(0, i - 5):i] if h[q] is not None]
            at = [H[j][q] for j in range(i, min(len(H), i + 3))]
            mb = sum(before) / len(before) if before else None
            mx = max([a for a in at if a is not None], default=None)
            out.append('%s at %s before(mean5) %s ratio %s' % (q, at, round(mb, 2) if mb is not None else None,
                                                             round(mx / mb, 1) if mb and mx is not None else ('inf' if mx else None)))
        print('CAMEV', x, 'k', H[i]['k'], 'cine', H[i]['cine'], 'ct', H[i]['ct'], 'sc', H[i]['sc'], 'idx', H[i]['idx'], '|', ' | '.join(out))


def bolt_frame(k):                                       # --bolts
    sf, rt = stft_root()
    rec = S.get('blst')
    if rec is None: rec = S['blst'] = next((a for a in range(0x80112808, 0x80113400, 0x30) if e.r32(a) == 0x426C7374), 0)
    if not (sf and rt and rec): return
    chor = e.r32(0x80112A78 + 0x10)
    R = rows(rt); o = v3(rt + 0x38); t = FALCON_RAM + HDR_TURRET
    tx, ty, tt, tb = (f32(t + 4 * i) for i in range(4))
    domes = [to_world(R, o, [tx, ty, tt]), to_world(R, o, [tx, ty, tb])]
    ng = e.r32(SYM['g_ngun']); guns = []
    for i in range(min(ng, 4)):
        g = e.r32(SYM['g_gun'] + 4 * i)
        if 0x80000000 <= g < 0x80800000:
            GR = rows(g); gfw = [sum(GR[1][r] * R[r][j] for r in range(3)) for j in range(3)]   # its forward row in world
            guns.append((i, r8(SYM['g_gun_top'] + i), gfw, ang(gfw, R[1]), ang(GR[1], [0, 1, 0])))
    shipF = R[1]
    for i, b0 in P.pop('bolt_next', {}).items():             # (the game frame after: was it moved onto a dome?)
        b = e.r32(rec + 0x10) + i * e.r32(rec + 0xC); bp = v3(b + 0x50)
        if P['bolts'] and P['bolts'][b0]['i'] == i: P['bolts'][b0]['local2'] = to_local(R, o, bp)
    for i in range(min(e.r32(rec + 8), 64)):
        b = e.r32(rec + 0x10) + i * e.r32(rec + 0xC)
        ow = e.r32(b + 0x64); bp = v3(b + 0x50); live = ow in (sf, chor) and bp[2] > -20000
        old = P['bolt'].get(i)
        new = live and (old is None or math.dist(old, bp) > 400)
        P['bolt'][i] = bp if live else None
        if not new: continue
        bd = v3(b + 0xA0)
        dd = [round(math.dist(bp, d), 1) for d in domes]
        ln = []
        for d in domes:                                    # the dome's distance from the bolt's line (and how far back)
            w = [d[j] - bp[j] for j in range(3)]; u = nrm(bd); a_ = sum(w[j] * u[j] for j in range(3))
            ln.append((round(math.sqrt(max(0, sum(x * x for x in w) - a_ * a_)), 1), round(a_, 1)))
        rec_ = dict(k=k, i=i, owner='stft' if ow == sf else 'chor', pos=bp, dir=bd, ship=o, domes=domes, d_dome=dd, line=ln,
                    local=to_local(R, o, bp), a_ship=ang(bd, shipF), guns=[(g[0], g[1], g[3], g[4], ang(bd, g[2])) for g in guns])
        P['bolts'].append(rec_); P.setdefault('bolt_next', {})[i] = len(P['bolts']) - 1
        print(k, 'BOLT slot', i, 'owner', rec_['owner'], 'pos', [round(x, 1) for x in bp], 'dir', [round(x, 3) for x in bd],
              'ship', [round(x, 1) for x in o], 'domes', [[round(x, 1) for x in d] for d in domes], 'dist to domes', dd,
              'dome off the bolt line (perp, along)', ln, 'in ship frame', rec_['local'], 'bolt vs ship fwd deg', rec_['a_ship'],
              'guns (i, top, gun fwd vs ship fwd deg, local row1 vs y deg, bolt vs gun fwd deg)', rec_['guns'], flush=True)


def sight_frame(k):                                      # --sight
    chor = e.r32(0x80112A78 + 0x10)
    if not chor: return
    sf, rt = stft_root(); fal = v3(rt + 0x38) if rt else [0, 0, 0]
    out = []
    for i in range(3):
        p = e.r32(chor + CHOR_SIGHT + 4 * i); dec = SYM['g_sight_decoy'] + i * 0x48; real = e.r32(SYM['g_sight_real'] + 4 * i)
        nd = real if p == dec else p
        ok = 0x80000000 <= nd < 0x80800000
        sh = e.r16(nd + 2) if ok else None; q = v3(nd + 0x38) if ok else None
        out.append(dict(i=i, decoy=p == dec, node=hex(nd), show=hex(sh) if sh is not None else None, drawn=sh is not None and sh >> 8 == 0xFF,
                        pos=[round(x, 1) for x in q] if q else None, scr=screen(q) if q else None, fal_d=round(math.dist(q, fal), 1) if q else None))
    cd = round(math.dist(v3(chor + 0x50), fal), 1)
    P['sight'].append((k, out, cd))
    print(k, 'SIGHT chor-falcon', cd, 'falcon scr', screen(fal), out, flush=True)


FADE_FORCE_K = 200                                      # --fade-luke: no hit by this VI (and no line held): one forced
def fade_frame(k, hold, nat, fj):                       # --fade
    fd = tuple(s16(0x800D0804 + 2 * i) for i in range(4))
    sf = e.r32(0x80112CB8 + 0x10) if e.r32(0x80112CB8 + 8) else 0
    hp, st = (e.r32(sf + 0x240), e.r32(sf + 0x230)) if sf else (None, None)
    cur = (fd, hold, hp, st); F_ = P.setdefault('fade', {'last': None, 'n': 0, 'held_up': 0, 'run': 0, 'best': 0, 'cols': {}})
    if A.fade_luke and nat and not F_.get('luke') and hp is not None and F_['last'] and F_['last'][2] is not None and hp < F_['last'][2]:
        e.w32(SYM['g_rogue'], 0); F_['luke'] = k; print(k, 'FADE-LUKE g_rogue 0 at the hit, hp', F_['last'][2], '->', hp, flush=True)
    elif A.fade_luke and nat and not F_.get('luke') and not hold and k >= FADE_FORCE_K:
        # (no hit by then: the battle's hits are rare, bf88 had one in 1800 frames; the game's hit tint written as a
        # hit sets it, and Luke's held line raised over it, so what is checked is ours: the tint off under the line)
        e.w32(0x800D0804, (255 << 16) | 128); e.w32(0x800D0808, (0 << 16) | 241)   # (r, g; b, alpha: s16 each)
        e.w32(SYM['g_rogue'], 0); F_['luke'] = k; F_['forced'] = k; print(k, 'FADE-LUKE forced: hit tint written, g_rogue 0', flush=True)
    if fd[3] > 0: F_['cols'][fd[:3]] = F_['cols'].get(fd[:3], 0) + 1
    if hold and fd[3] > 0:
        F_['held_up'] += 1
        F_['run'] = F_['run'] + 1 if F_['last'] and F_['last'][0] == fd else 1; F_['best'] = max(F_['best'], F_['run'])
    else: F_['run'] = 0
    F_['n'] += 1
    if cur != F_['last'] or F_['n'] % 30 == 0:
        print(k, 'FADE', 'rgba', fd, 'hold', hold, 'hp', hp, 'st', st, 'native', nat, 'rogue', e.r32(SYM['g_rogue']), 'fj', round(fj, 2),
              'dt', round(e.rf(SYM['g_dt']) if 'g_dt' in SYM else -1, 4), flush=True)
    F_['last'] = cur


def probe(k, cine, hold):                                # every VI; the knobs once per game frame
    ov = e.r32(SYM['g_ov_frames'])
    if ov == P['ov']: return
    P['ov'] = ov; P['n'] += 1
    if A.hp >= 0 and P['n'] == 1:
        sf_ = e.r32(0x80112CB8 + 0x10)
        if sf_: e.w32(sf_ + 0x240, A.hp); e.w32(SYM['g_hp_kept'], A.hp); print(k, 'HP written', A.hp, flush=True)
    sc, nat = s32(SYM['g_sc']), e.r32(SYM['g_native'])
    fj = f32(SYM['g_fj_t']) if 'g_fj_t' in SYM else -1
    if 'jump' in SAVE_AT and 'jump' not in P['saved']:     # the towers down (below), _prejump
        if P['twd'] and 'prejump' not in P['saved'] and e.r32(SYM['g_won_said']) and s16(MSG_HOLD) and fj < 0:
            pth = os.path.join(RUN, f'{BUILD}_prejump.st'); e.save_state(pth); P['saved']['prejump'] = k
            print(k, 'SAVED prejump', pth, '(Lando\'s line held: the jump on its let-go)', flush=True)
    for name, cond in (('rail', cine == 2), ('dash', cine == 2 and sc == 1), ('slave', cine == 2 and sc == 4), ('free', cine == 2 and sc == 5), ('jump', fj >= 0)):
        if name in SAVE_AT and name not in P['saved'] and cond:
            pth = os.path.join(RUN, f'{BUILD}_{name}.st'); e.save_state(pth); P['saved'][name] = k; P['last_save'] = P['n']
            print(k, 'SAVED', name, pth, 'g_cine', cine, 'g_sc', sc, 'g_native', nat, 'node', e.r32(e.r32(0x80112A78 + 0x10) + 0x6C), flush=True)
    if 'jump' in SAVE_AT and nat and not P['twd'] and ('free' not in SAVE_AT or ('free' in P['saved'] and P['n'] > P['last_save'] + 30)) \
            and not s16(MSG_HOLD) and e.r32(GALL + 304) and e.r32(0x80112C28 + 0x10) == e.r32(GALL + 304 + 12):   # (not under a held line: the fly-away would wait under it)   # (30 game frames after _free's save: the core writes it later, it stays clean)
        pool = e.r32(GALL + 304 + 12)
        for i in range(e.r32(GALL + 304)): e.w32(pool + i * 0x214 + 0x140, e.r32(pool + i * 0x214 + 0x140) | 0x10)
        P['twd'] = True; print(k, 'TOWERS written down', e.r32(GALL + 304), flush=True)
        if A.away_put:                                   # (--away-put) the Falcon put there, facing the battle, level
            sf_ = e.r32(CLASS_STFT + 0x10); mid = v3(GALL + 228); off = [float(x) for x in A.away_put.split(',')]
            p_ = [mid[i] + off[i] for i in range(3)]; f_ = nrm([-off[0], -off[1], 0]); r_ = [f_[1], -f_[0], 0]
            for i in range(3):
                e.wf(sf_ + 0x50 + 4 * i, p_[i]); e.wf(sf_ + 0x08 + 4 * i, p_[i])
                e.wf(sf_ + 0x20 + 4 * i, r_[i]); e.wf(sf_ + 0x30 + 4 * i, f_[i]); e.wf(sf_ + 0x40 + 4 * i, [0, 0, 1][i])
            e.w32(SYM['g_rogue'], 1)                     # (Luke's line said on the way in, as in play: not now, held)
            print(k, 'AWAYPUT the Falcon at', [round(x, 1) for x in p_], 'facing', [round(x, 3) for x in f_], flush=True)
    if A.cam: cam_frame(k, cine, hold)
    if A.cam and A.shots and fj >= 0 and P['n'] % 3 == 1: e.shot(); print(k, 'SHOT jump g_fj_t', round(fj, 3), flush=True)
    if A.window or A.cam: line_frame(k, sc)
    if A.window: win_frame(k, cine, sc)
    if A.trail and fj >= 0: trail_frame(k, fj)
    if A.hull and nat: hull_frame(k, fj)
    if A.fade: fade_frame(k, hold, nat, fj)
    if A.bolts and cine == 2: bolt_frame(k)                # (the rail's too: the gunner's aim against its bolts)
    if A.sight and nat: sight_frame(k)
    if A.frames and P['n'] >= A.frames: S['end'] = f'{A.frames} game frames'; e.stop(); return 'stop'
    if SAVE_AT and len([x for x in P['saved'] if x in SAVE_AT]) == len(SAVE_AT) and P['n'] - P['last_save'] >= A.after * 30:
        S['end'] = f'all states saved, {A.after} s on'; e.stop(); return 'stop'


T_ = {'n': 0, 'pre': 0, 'pre_on': 0, 'drawn': 0, 'near': 0, 'onscr': 0, 'off_s': 0, 'off_t': 0.0, 'last_d': None, 'last_fj': 0.0, 'fal0': None, 'moved': 0.0, 'len1': None}
def trail_frame(k, fj):                            # --trail: the Falcon's white trail in its jump
    sf, _ = stft_root(); fal = v3(sf + 0x50) if sf else [0, 0, 0]
    n = e.r32(SYM['g_dh_node']); ok = 0x80000000 <= n < 0x80800000
    cnt, show = (e.r32(n + 0x0C), e.r16(n + 2) >> 8) if ok else (None, None)
    tail = v3(n + 0x38) if ok else [0, 0, 0]; r1 = v3(n + 0x14 + 12) if ok else [0, 0, 0]
    ln = math.hypot(*r1) * 100; head = [tail[i] + r1[i] * 100 for i in range(3)]
    who = s32(SYM['g_tr_who']); frm = v3(SYM['g_fj_from'])
    drawn = who == 3 and cnt == 1 and show == 0xFF and ln > 0
    vw = view(); eye = vw[3] if vw else [0, 0, 0]; d_ef = math.dist(eye, fal)
    sf_scr = screen(fal); on = bool(sf_scr) and 0 <= sf_scr[0] <= 320 and 0 <= sf_scr[1] <= 240
    hs, ts = screen(head), screen(tail)          # (the trail's length on screen, unclipped)
    scr_len = round(math.dist(hs, ts), 1) if hs and ts else None
    print(k, 'TRAIL fj', round(fj, 3), 'who', who, 'count', cnt, 'show', show, 'tail', [round(x, 1) for x in tail], 'head',
          [round(x, 1) for x in head], 'len', round(ln, 1), 'w', round(f32(SYM['g_tr_w']), 1), 'head-fal', round(math.dist(head, fal), 1),
          'tail-from', round(math.dist(tail, frm), 1), 'head scr', screen(head), 'fal scr', sf_scr, 'eye-fal', round(d_ef, 1),
          'tail scr', screen(tail), 'scr len', scr_len, flush=True)
    if sf_scr and T_['fal0'] is None: T_['fal0'] = sf_scr
    if sf_scr and fj <= 1.2 and T_['fal0']: T_['moved'] = max(T_['moved'], math.dist(sf_scr, T_['fal0']))
    if drawn and scr_len is not None and T_['len1'] is None and fj >= 1.0: T_['len1'] = (round(fj, 3), scr_len)
    if fj <= 2.4:
        T_['n'] += 1; T_['pre'] += fj < 1.9; T_['pre_on'] += fj < 1.9 and on; T_['drawn'] += drawn; T_['near'] += drawn and math.dist(head, fal) < 50; T_['onscr'] += on
        if on and fj < 1.9 and T_['last_d'] is not None and d_ef > T_['last_d']: T_['off_s'] += 1; T_['off_t'] += fj - T_['last_fj']
    T_['last_d'] = d_ef; T_['last_fj'] = fj


H_ = {'n': 0, 'below': 0, 'hold': 0, 'v': None, 'hp0': None, 'hpmin': None, 'over': 0, 'pmax': None}
def hull_axis(sf, fal):                           # along / lat of the hull's axis line, its top under, hp
    if 'g_sd_mid' not in SYM: return ()
    ax, ay, mx, my = f32(SYM['g_sd_axis']), f32(SYM['g_sd_axis'] + 4), f32(SYM['g_sd_mid']), f32(SYM['g_sd_mid'] + 4)
    dx, dy = fal[0] - mx, fal[1] - my; lat = -dx * ay + dy * ax
    hp = s32(sf + 0x240) if sf else None
    if hp is not None:
        H_['hp0'] = hp if H_['hp0'] is None else H_['hp0']; H_['hpmin'] = hp if H_['hpmin'] is None else min(H_['hpmin'], hp)
    under = [v for v in H_['v'] if (v[0] - fal[0]) ** 2 + (v[1] - fal[1]) ** 2 <= 200 ** 2]
    H_['over'] += bool(under)
    return ('along', round(dx * ax + dy * ay), 'lat', round(lat), 'under top', round(f32(SYM['g_away_under'])),
            'z over under', round(fal[2] - f32(SYM['g_away_under'])), 'vertices under', len(under), 'hp', hp)


def hull_frame(k, fj):                             # --hull: the hull under the Falcon in the fly-away
    away = f32(SYM['g_away_t'])
    if away < 0 or fj >= 0: return
    if H_['v'] is None:
        c = e.r32(GALL + 268); H_['v'] = []
        nt = e.r32(c) if c else 0; tris = e.r32(c + 4) if c else 0
        if 0 < nt < 200000:
            for t in range(nt):
                a = tris + 24 * t
                for q in range(3): H_['v'].append([s16(a + 6 * q + 2 * m) for m in range(3)])
        H_['v'] = [list(x) for x in {tuple(x) for x in H_['v']}]
        print(k, 'HULL vertices', len(H_['v']), 'triangles', nt, flush=True)
    sf, rt = stft_root(); fal = v3(rt + 0x38) if rt else (v3(sf + 0x50) if sf else [0, 0, 0])
    fs = screen(fal); hold = s16(MSG_HOLD)
    on = [p for p in (screen(v) for v in H_['v']) if p and 0 <= p[0] <= 320 and 0 <= p[1] <= 240]
    below = [p for p in on if fs and p[1] > fs[1]]
    H_['n'] += 1; H_['below'] += bool(below and fs); H_['hold'] += bool(hold)
    vw = view(); sd = v3(GALL + 212)
    if vw:                                       # the view's pitch, the hull's middle (IMG_SD) below the view's axis, half FOV
        R, F, U, E = vw; dv = nrm([sd[i] - E[i] for i in range(3)])
        below_deg = round(math.degrees(math.asin(max(-1, min(1, -sum(U[i] * dv[i] for i in range(3)))))), 1)
        pitch = round(math.degrees(math.asin(max(-1, min(1, F[2])))), 1); hf = round(f32(PERSP) / 2, 1)
        sfw = v3(sf + 0x30) if sf else [0, 1, 0]; npitch = round(math.degrees(math.asin(max(-1, min(1, sfw[2])))), 1)
    else: below_deg = pitch = hf = npitch = None
    if npitch is not None: H_['pmax'] = abs(npitch) if H_['pmax'] is None else max(H_['pmax'], abs(npitch))
    print(k, 'HULL away', round(away, 3), 'fal scr', fs, 'hull on screen', len(on), 'below the Falcon', len(below), 'hold', hold,
          'view pitch', pitch, 'nose pitch', npitch, 'SD middle below the view axis deg', below_deg, 'half fov', hf,
          'fal z over SD', round(fal[2] - sd[2], 1), *hull_axis(sf, fal), flush=True)
    if A.shots and H_['n'] % 15 == 1: e.shot(); print(k, 'SHOT away', round(away, 3), flush=True)


LINE_COWARD, IMG_LINES, LINE_SIZE = 8, 80, 16           # (gall_story.c, gall.h)
SL_ = {'last': None, 'said': [], 'shot': None, 'off': None}
def line_frame(k, sc):                             # --window / --cam: the code-said lines (say_last()) and the view's return
    i, shot = s32(SYM['g_said_last']), e.r32(SYM['g_shot'])
    if SL_['last'] is None: SL_['last'] = i                      # (the value the state was saved with)
    elif i != SL_['last']:
        SL_['last'] = i
        ent = e.r32(GALL + IMG_LINES + 4) + (e.r32(GALL + IMG_LINES) - 1 - i) * LINE_SIZE; tp = e.r32(ent + 8)
        txt = bytes(r8(tp + j) for j in range(80)).split(b'\0')[0].decode('latin-1') if tp else None
        SL_['said'].append((k, i)); print(k, 'LINE said_last', i, 'text', repr(txt), 'g_sc', sc, 'g_shot', shot, flush=True)
        SL_['shot_k'] = k + 20
    if SL_['shot'] == 1 and shot == 0 and sc in (2, 3) and SL_['off'] is None:
        SL_['off'] = k; print(k, 'SHOTOFF g_sc', sc, '(the gunner\'s view back)', flush=True)
    if A.shots and SL_.get('shot_k') is not None and k >= SL_['shot_k']:   # (--shots: one 20 VIs after each LINE)
        SL_['shot_k'] = None; e.shot(); print(k, 'SHOT line', SL_['last'], flush=True)
    SL_['shot'] = shot


W_ = {'last': None, 'n': 0, 'vm4': 0, 'ix4': 0, 'b4hid': 0, 'win': 0, 'after4': 0, 'after': 0, 'was': 0}
def win_frame(k, cine, sc):                        # --window: the inside view's window in Dash's shot
    sf = e.r32(CLASS_STFT + 0x10) if e.r32(CLASS_STFT + 8) else 0
    shot, vm, ix = e.r32(SYM['g_shot']), s16(0x8018E462), s32(CAMERA_INDEX)
    ac, ents = e.r32(ACTIVE_CAMERA), e.r32(0x800D08A0)
    ai = (ac - ents) // 0x80 if 0x80000000 <= ents <= ac < ents + 16 * 0x80 else None
    guns = e.r32(sf + 0x70) if sf else None
    nd = lambda o: (lambda p: (e.r16(p + 2) >> 8) if 0x80000000 <= p < 0x80800000 else None)(e.r32(sf + o)) if sf else None
    b0, b4 = nd(0xB0), nd(0xB4)
    hx = [s16(0x80111110 + 4 * i) for i in (0, 20, 21, 22, 23)]
    win = any(x != -1000 for x in hx[1:])
    cur = (sc, shot, vm, ix, ai, guns, b0, b4, tuple(hx))
    if cur != W_['last']:
        print(k, 'WIN g_cine', cine, 'g_sc', sc, 'g_shot', shot, 'VIEW_MODE', vm, 'index', ix, 'active entry', ai, 'guns', guns,
              'node B0', b0, 'B4', b4, 'hud x 0,20-23', hx, 'window', int(win), flush=True)
    W_['last'] = cur
    if shot:
        W_['n'] += 1; W_['was'] = 1; W_['vm4'] += vm == 4; W_['ix4'] += ix == 4; W_['b4hid'] += b4 is not None and b4 != 0xFF; W_['win'] += win
        if A.shots and W_['n'] % 6 == 1: e.shot(); print(k, 'SHOT win', W_['n'], flush=True)
    elif W_['was']:
        W_['after'] += 1; W_['after4'] += vm == 4


LK = {'last': None, 'lvl': None, 'k': 0}
def look_tick(e, k, lvl):                          # --look: falcon.bin's look per change (read every
    if lvl != LK['lvl']: LK['lvl'], LK['k'] = lvl, k   # VI for 20 VIs after a sub-level change, else every 120)
    if k - LK['k'] > 20 and k % 120: return
    from gallrun.falcon_look import look, line
    d = look(e.r32, e.r16); key = (lvl, d['kind'])
    if key != LK['last']: print('k', k, line(d), flush=True)
    LK['last'] = key


def end_clear(k, cine, hold):                       # --clear: the end scene's first held line (nothing of stage 2 hangs)
    E = S.setdefault('ec', {'hv': 0, 'done': False, 'rows': [], 'blst': None})
    if E['done'] or cine != 1: return
    if not hold:
        if E['hv']: E['done'] = True; print(k, 'ENDCLEAR let-go after', E['hv'], 'hold VIs', flush=True)
        return
    E['hv'] += 1; hv = E['hv']
    sf = e.r32(CLASS_STFT + 0x10) if e.r32(CLASS_STFT + 8) else 0; rt = e.r32(sf + 0xB4) if sf else 0
    fp = v3(rt + 0x38) if 0x80000000 <= rt < 0x80800000 else v3(sf + 0x50) if sf else [0, 0, 0]   # (the drawn Falcon)
    tf, sz, n_ = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), e.r32(TIEF + 8)
    play, drawn = [], []
    for i in range(min(n_, 32)):
        t = tf + i * sz; nd = e.r32(t + 0x94)
        if f32(t + 0x58) < -4000 or not 0x80000000 <= nd < 0x80800000: continue   # (parked / put away under the ground)
        d = math.dist(v3(nd + 0x38), fp); play.append((round(d), i))
        if (e.r16(nd + 2) >> 8) == 0xFF and d < 1000: drawn.append((round(d), i))
    if E['blst'] is None: E['blst'] = next((a for a in range(0x80112808, 0x80113400, 0x30) if e.r32(a) == 0x426C7374), 0)
    rec, tb = E['blst'], 0
    for j in range(min(e.r32(rec + 8), 64) if rec else 0):        # TIE bolts (Blst owned by a TieF) within 1000
        b = e.r32(rec + 0x10) + j * e.r32(rec + 0xC); ow = e.r32(b + 0x64)
        if f32(b + 0x58) > -20000 and sz and tf <= ow < tf + n_ * sz and math.dist(v3(b + 0x50), fp) < 1000: tb += 1
    h37, h51 = s16(HUD_POS + 4 * 37), s16(HUD_POS + 4 * 51)
    E['rows'].append((hv, min(play, default=None), sorted(drawn), h37, h51, tb))
    if hv <= 2 or hv % 10 == 0:
        print(k, 'ENDCLEAR hold vi', hv, 'nearest in play (d, i)', min(play, default=None), 'drawn within 1000', sorted(drawn),
              'hud37 x', h37, 'hud51 x', h51, 'TIE bolts within 1000', tb, flush=True)


def end_clear_summary():
    E = S.get('ec')
    if not E or not E['rows']: print('ENDCLEAR no held line seen in the end scene'); check('end clear', False, 'no hold') if A.check else None; return
    R = E['rows']; late = [d for hv, _, dr, *_ in R if hv > 30 for d, _ in dr]
    near = {hv: nr for hv, nr, *_ in R if hv in (1, 10, 20, 30, 45, 60, 90) or hv == R[-1][0]}
    x37, x51 = sorted({r[3] for r in R}), sorted({r[4] for r in R})
    print('ENDCLEAR hold VIs', len(R), 'let-go', E['done'], '| nearest TIE in play by hold VI (d, i)', near,
          '| least drawn within 1000 after VI 30', min(late, default=None), '| HUD 37 x seen', x37, 'HUD 51 x seen', x51,
          '| TIE bolts within 1000 max', max(r[5] for r in R))
    if A.check:
        check('end clear', E['done'] and len(R) > 30 and min(late, default=1e9) >= 300 and x37 == [-1000] and x51 == [-1000],
              f'hold VIs {len(R)} (> 30, let go), least drawn TIE after VI 30 {min(late, default=None)} (>= 300), '
              f'HUD 37 x {x37} ([-1000]), HUD 51 x {x51} ([-1000])')


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(start)
    if n < 64: return
    k = n - 64
    lvl, hold = e.r16(LEVEL), e.r16(HOLD)
    if A.reach:                                                  # --reach (was scene_reach.py)
        if lvl != RCH['lv'] or k % 300 == 0: print(k, 'REACH level', lvl, 'hold', hold, flush=True); RCH['lv'] = lvl
        if lvl == 31 and RCH['k31'] is None: RCH['k31'] = k
        if (RCH['k31'] is not None and k > RCH['k31'] + 600) or k > A.reach: e.stop(); return
    if A.look: look_tick(e, k, lvl)
    S['h'] = S['h'] + 1 if hold else 0
    hw = 120 if A.fade_luke else 90 if A.clear and not S.get('ec', {}).get('done') else 30   # (--clear: the end scene's first line held 1.5 s)
    pad = (BTN['A'] if S['h'] >= hw and S['h'] % 60 < 5 else 0, 0, 0)
    if lvl != MLV or not e.r32(SYM['g_gallrun']):
        if 'jump' in P['saved'] and 'jump' in SAVE_AT:
            S.setdefault('left', k)                              # (on till another sub-level, at most 20 s: native_off())
            if lvl != MLV: S.setdefault('other', k)
            if k - S.get('other', 1e9) >= 30 or k - S['left'] > 1200:
                S['end'] = (f'the mission left after the jump (g_gallrun 0 at k {S["left"]}, level {lvl} from k {S.get("other")}, read at k {k}; the Stft\'s PRBT'
                            f' touch 0x800EC9F8 {e.rf(0x800EC9F8):.1f}: 50000 stock, native_off() puts it back)'); e.stop(); return
        e.pad(*pad); return
    cine = e.r32(SYM['g_cine'])
    if not S['saved'] and cine == 1:
        e.save_state(STATE); S['saved'] = True; print(k, 'saved', STATE, flush=True)
    if probe(k, cine, hold) == 'stop': return
    if A.clear: end_clear(k, cine, hold)
    ht = f32(SYM['g_hang_t'])
    chase = [e.r32(SYM['g_chase'] + 4 * i) for i in range(6)]
    nh, hr = e.r32(GALL + 364), e.r32(GALL + 368)
    if not hold:
        chor = e.r32(0x80112A78 + 0x10); node = e.r32(chor + 0x6C) if chor else 0; sw = e.r32(GALL + 48)
        if e.r32(SYM['g_free']) and e.r32(SYM['g_fly_on']):
            tg = chase[A.aim] if A.kill < 0 else 0
            if tg and f32(tg + 0x60) > 0: pad, S['ey'] = chase_at(v3(tg + 0x50))
            else: pad = chase_at(v3(SYM['g_sl']))[0]
        elif cine == A.cine and A.kill < 0: pad = (BTN['B'] if k % 6 < 3 else 0, 0, 0)   # (the rail: the gunner fires, gun centred)
        elif cine: pad = (0, 0, 0)
        elif node < sw: pad = pilot(node)
        else: pad = (BTN['B'] if k % 6 < 3 else 0, 0, 0)
        if A.bolts and e.r32(SYM['g_native']): pad = (BTN['B'], 0, 0)   # (--bolts: B held in the native flight)
        if A.view >= 0 and cine == 2 and s32(SYM['g_sc']) == 0 and s16(0x8018E462) != A.view:
            pad = (BTN['L'] if k % 30 < 4 else 0, 0, 0)               # (--view: the view key till VIEW_MODE is N)
    if A.all and S['saved'] and cine >= 1 and k % 2 == 0 and (ht < 0 or ht <= 6.01):   # ghosts: drawn far from its place
        tf, sz, n_ = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), e.r32(TIEF + 8); sf = e.r32(0x80112CB8 + 0x10)
        fp = v3(sf + 0x50) if sf else [0, 0, 0]; G = S.setdefault('ghost', {})
        for i in range(min(n_, 15)):
            t = tf + i * sz; nd = e.r32(t + 0x94)
            if not 0x80000000 <= nd < 0x80800000 or (e.r16(nd + 2) >> 8) != 0xFF: continue
            dq, q = v3(nd + 0x38), v3(t + 0x50)
            if math.dist(dq, fp) < 1000 and math.dist(dq, q) > 1000:
                ld = e.r32(t + 0xBC); li = (ld - tf) // sz if tf <= ld < tf + 32 * sz else None
                g = G.setdefault(i, {'n': 0, 'first': None, 'last': None, 'lead': set(), 'slot': set(), 'near': 1e9})
                tt = ('L%.2f' % ht) if ht >= 0 else ('C%.2f' % f32(SYM['g_cine_t']))
                g['n'] += 1; g['first'] = g['first'] or tt; g['last'] = tt; g['lead'].add(li)
                g['slot'].add(chase.index(t) if t in chase else -1); g['near'] = min(g['near'], round(math.dist(dq, fp)))
    if A.all and S['saved'] and cine >= 1 and k % 2 == 0:
        mark = ('L%.1f' % (int(ht / 0.5) * 0.5)) if ht >= 0 else ('C%.1f' % (int(f32(SYM['g_cine_t']) / 0.5) * 0.5))
        if mark not in S.setdefault('marks', set()) and (ht < 0 or ht <= 6.01):
            S['marks'].add(mark); all_ties(k, mark, ht, chase)
            if A.shots and mark in ('L0.5', 'L1.0', 'L3.5', 'L5.0'): e.shot(); print(k, 'SHOT', mark, flush=True)
    if S['saved'] and ht >= 0:
        S.setdefault('k0', k)
        if A.kill >= 0 and ht >= A.kill and S['killed'] is None and chase[A.aim]:
            S['killed'] = chase[A.aim]; e.wf(chase[A.aim] + 0x60, 0.0)
            print(k, 'KILL slot', A.aim, 'obj', idx(chase[A.aim]), 'at g_hang_t', round(ht, 2), flush=True)
        if S['killed'] and S.setdefault('kn', 0) < 90 and k % 2 == 0:   # the killed one, each game frame for 3 s
            t = S['killed']; nd = e.r32(t + 0x94); st_ = e.r16(t + 0xA8); st_ -= 65536 if st_ > 32767 else 0
            S['kn'] += 1
            print(k, 'KILLED obj', idx(t), 'hp', round(f32(t + 0x60), 1), 'state', st_, 'pos', [round(x) for x in v3(t + 0x50)],
                  'shown', hex(e.r16(nd + 2)) if nd else None, 'slot', chase.index(t) if t in chase else -1, 'g_hang_t', round(ht, 2), 'cine', cine, flush=True)
        rec = S.get('blst')
        if rec is None:
            rec = S['blst'] = next((a for a in range(0x80112808, 0x80113400, 0x30) if e.r32(a) == 0x426C7374), 0)
        chor = e.r32(0x80112A78 + 0x10)
        if rec and chor:                                          # the player's bolts (owner Chor): each slot's nearest pass
            for i in range(min(e.r32(rec + 8), 64)):             # (a bolt's last 130 of way, as free_lasers())
                b = e.r32(rec + 0x10) + i * e.r32(rec + 0xC)
                if e.r32(b + 0x64) != chor or f32(b + 0x58) < -20000: continue
                bp, bd = v3(b + 0x50), v3(b + 0xA0)
                for sl, t in enumerate(chase):
                    if not t: continue
                    w = [f32(t + 0x50 + 4 * j) - bp[j] for j in range(3)]; a_ = sum(w[j] * bd[j] for j in range(3))
                    if a_ > 0 or a_ < -130: continue
                    q = math.sqrt(max(0, sum(x * x for x in w) - a_ * a_))
                    if q < S.setdefault('miss', {}).get(sl, 1e9): S['miss'][sl] = q
        if A.plant and cine == A.cine and rec and chor and chase[A.aim] and f32(chase[A.aim] + 0x60) > 0:
            best = None
            for i in range(min(e.r32(rec + 8), 64)):
                b = e.r32(rec + 0x10) + i * e.r32(rec + 0xC)
                if e.r32(b + 0x64) != chor or f32(b + 0x58) < -20000: continue
                dc = math.dist(v3(b + 0x50), v3(chor + 0x50))
                if best is None or dc < best[0]: best = (dc, b)
            if best and best[0] < 600:
                b = best[1]; q = [f32(b + 0x50 + 4 * j) + f32(b + 0xA0 + 4 * j) * A.plant for j in range(3)]
                for j in range(3): e.wf(chase[A.aim] + 0x50 + 4 * j, q[j])
                S['planted'] = S.get('planted', 0) + 1
        if A.watch and A.vel and chor:
            wa, wb = (float(x) for x in A.watch.split(','))
            if wa <= ht <= wb and 'g_tie_aim' in SYM:
                c = v3(chor + 0x50); aim = v3(SYM['g_tie_aim']); pv = S.setdefault('pv', {})
                print(k, 'WVEL t', round(ht, 3), 'aim-chor', round(math.dist(aim, c)), 'aim', [round(x) for x in aim], flush=True)
                for sl, t in enumerate(chase):
                    if not t: continue
                    q = v3(t + 0x50); h = v3(t + 0x74); st = [0, 0, 0]
                    if t in pv: st = [q[j] - pv[t][j] for j in range(3)]
                    pv[t] = q
                    dc = math.dist(q, c); tc = [(c[j] - q[j]) / max(dc, 1e-3) for j in range(3)]
                    print('   slot', sl, 'obj', idx(t), 'pos', [round(x) for x in q], 'chor_d', round(dc, 1),
                          'vel', [round(x, 2) for x in h], 'step', round(math.hypot(*st), 2),
                          'along_vel', round(sum(st[j] * h[j] for j in range(3)), 2),
                          'to_chor', round(sum(st[j] * tc[j] for j in range(3)), 2),
                          'vel_to_chor', round(sum(h[j] * tc[j] for j in range(3)), 2), flush=True)
        if A.lead and chor:
            la, lb = (float(x) for x in A.lead.split(','))
            if la <= ht <= lb:
                aim = v3(SYM['g_tie_aim']); c = v3(chor + 0x50); L = S.setdefault('lead', {})
                print(k, 'LEADT t', round(ht, 3), 'aim-chor', round(math.dist(aim, c)), 'aim', [round(x) for x in aim], flush=True)
                for sl, t in enumerate(chase):
                    if not t: continue
                    ld = e.r32(t + 0xBC); q = v3(t + 0x50); fw = v3(t + 0x30); hv = v3(t + 0x74); nd = e.r32(t + 0x94)
                    r1 = v3(nd + 0x20) if nd else None
                    err = None
                    if ld:
                        o = [f32(t + 0xC0), f32(t + 0xC4), f32(t + 0xC8)]
                        w = [f32(ld + 0x20 + 4 * j) * o[0] + f32(ld + 0x74 + 4 * j) * o[1] + f32(ld + 0x50 + 4 * j) + (o[2] if j == 2 else 0) for j in range(3)]
                        err = round(math.dist(w, q), 1)
                    ob = idx(t); ent = L.setdefault(ob, {'lead': set(), 'aim': [], 'err': [], 'same': 0, 'n': 0})
                    ent['lead'].add(idx(ld) if ld else None); ent['aim'].append(math.dist(q, aim)); ent['n'] += 1
                    if err is not None: ent['err'].append(err)
                    if r1 and max(abs(r1[j] - fw[j]) for j in range(3)) < 1e-4: ent['same'] += 1
                    print('   slot', sl, 'obj', ob, 'lead', idx(ld) if ld else None, 'off', [round(f32(t + x), 1) for x in (0xC0, 0xC4, 0xC8)],
                          'pos', [round(x) for x in q], 'aim_d', round(math.dist(q, aim), 1), 'fwd30', [round(x, 2) for x in fw],
                          'vel74', [round(x, 2) for x in hv], 'row1', [round(x, 2) for x in r1] if r1 else None, 'lead_err', err,
                          'state', e.r16(t + 0xA8) - (65536 if e.r16(t + 0xA8) > 32767 else 0), 'ac', hex(e.r32(t + 0xAC)), flush=True)
        if A.clear and chor:
            C = S.setdefault('clr', {'xy': {}, 'turn': {}, 'hv': {}, 'start': None, 'near': {}})
            c = v3(chor + 0x50)
            for sl, t in enumerate(chase):
                if not t: continue
                q = v3(t + 0x50)
                inch = cine == 2 and A.chase and C['start'] is not None and ht <= C['start'][0] + A.chase
                if (cine == 1 and ht >= sl * HANGAR_GAP or inch) and q[2] > -1000:
                    dxy = math.hypot(q[0] - c[0], q[1] - c[1])
                    if not inch: C['xy'][sl] = min(C['xy'].get(sl, 1e9), dxy)
                    ob = idx(t); tk, fk = ('turn_c', 'flips_c') if inch else ('turn', 'flips')   # (per object: slots shift when one leaves the chase)
                    nd = e.r32(t + 0x94); h = v3(nd + 0x14 + 12) if nd else v3(t + 0x74); ph = C['hv'].get(ob)   # (the drawn nose: node row 1)
                    if nd and not inch: C.setdefault('npos', {}).setdefault(ob, []).append((round(ht, 3), [round(x) for x in v3(nd + 0x38)]))
                    if ph and h != ph:
                        dd = sum(h[j] * ph[j] for j in range(3)) / max(1e-6, math.hypot(*h) * math.hypot(*ph))
                        a_ = math.acos(max(-1, min(1, dd)))
                        if a_ > C.setdefault(tk, {}).get(ob, (0,))[0]: C[tk][ob] = (round(a_, 3), round(ht, 2))
                        if a_ > 0.3: C.setdefault(fk, {}).setdefault(ob, []).append(round(ht, 2)); print(k, 'FLIP', 'chase' if inch else 'scene', 'obj', ob, 'slot', sl, 'turn', round(a_, 2), 'g_hang_t', round(ht, 3), 'nose', [round(x, 2) for x in h], 'node', [round(x) for x in v3(nd + 0x38)] if nd else None, 'pos', [round(x) for x in q], flush=True)
                    C['hv'][ob] = h
                if cine == 2 and C['start'] is not None and ht <= C['start'][0] + 3 and sl not in C['near'] \
                        and math.dist(q, c) < 600: C['near'][sl] = round(ht, 2)
            if cine == 2 and C['start'] is None:
                C['start'] = (ht, sum(1 for t in chase if t), [idx(t) if t else None for t in chase])
        if A.watch and k % 2 == 0:
            wa, wb = (float(x) for x in A.watch.split(','))
            if wa <= ht <= wb:
                sf = e.r32(0x80112CB8 + 0x10)
                def sst(t): x = e.r16(t + 0xA8); return x - 65536 if x > 32767 else x
                print(k, 'WATCH t', round(ht, 2), 'chor', [round(x) for x in v3(chor + 0x50)] if chor else None,
                      'falcon', [round(x) for x in v3(sf + 0x50)] if sf else None, 'falcon hp', e.r32(sf + 0x240) if sf else None, 'ship_off', [round(x) for x in v3(SYM['g_ship_off'])],
                      'ties', [(idx(t), round(f32(t + 0x60)), sst(t), [round(x) for x in v3(t + 0x50)]) for t in chase if t], flush=True)
        tf, sz, cnt = e.r32(TIEF + 0x10), e.r32(TIEF + 0xC), e.r32(TIEF + 8)
        for i in range(min(cnt, 22)):
            t = tf + i * sz; hp = round(f32(t + 0x60), 1)
            if i in S['hp'] and S['hp'][i] != hp:
                sl = chase.index(t) if t in chase else -1
                print(k, 'HP obj', i, S['hp'][i], '->', hp, 'slot', sl, 'state', e.r16(t + 0xA8) - (65536 if e.r16(t + 0xA8) > 32767 else 0),
                      'g_hang_t', round(ht, 2), 'cine', cine, 'free', e.r32(SYM['g_free']), 'pos', [round(x) for x in v3(t + 0x50)], flush=True)
                S['objs'].setdefault(i, []).append((round(ht, 2), S['hp'][i], hp))
            S['hp'][i] = hp
        if k % 6 == 0:
            out = []
            for sl, t in enumerate(chase):
                if not t: out.append(None); continue
                m = [f32(hr + 20 * (sl % max(nh, 1)) + 4 * j) for j in range(5)] if nh else [0] * 5
                st_ = e.r16(t + 0xA8); st_ -= 65536 if st_ > 32767 else 0
                out.append((idx(t), round(f32(t + 0x60), 1), st_, round(ht - sl * HANGAR_GAP, 2), round(math.dist(v3(t + 0x50), m[:3])),
                            round(math.dist(v3(t + 0x50), v3(chor + 0x50))) if chor else -1, round(S.get('miss', {}).get(sl, -1))))
            S['miss'] = {}
            print(k, 'HANG t', round(ht, 2), 'cine', cine, 'free', e.r32(SYM['g_free']), 'ey', round(S.get('ey', 9), 2),
                  'slots (obj, hp, state, s, mouth dist, Chor dist, nearest bolt pass)', out, flush=True)
            if A.shots and e.r32(SYM['g_free']): e.shot()
        if ht > A.secs: S['end'] = f'{A.secs} s after the launch'; e.stop(); return
    e.pad(*pad)
    if k > 60 * 60 * 8: S['end'] = 'timeout'; e.stop()


e.run(script)
if A.cam: cam_summary()
if A.cam and A.check:
    k0 = P['hist'][0]['k'] if P['hist'] else 0               # (a carry at the load's first frame: no steps before it)
    dc = [c for c in P.get('carries', []) if c[0] == 'g_dash_carry' and c[1] > k0]
    check('shot carry', bool(dc) and all(c[2] == 0 and c[3] == 0 for c in dc),
          f'g_dash_carry starts (k, eye steps > 1.5x the one before, frames off screen, of): {[c[1:] for c in dc]} (each 0, 0)')
if A.fade and 'fade' in P:
    F_ = P['fade']; print('FADESUM frames', F_['n'], 'fade up under a held line', F_['held_up'], 'longest unchanged under it', F_['best'], 'colours', F_['cols'])
    if A.check: check('hit tint', F_.get('luke') is not None and (255, 128, 0) in F_['cols'] and F_['held_up'] <= 2,
                      f"a hit tint seen {(255, 128, 0) in F_['cols']}, Luke's line at the hit k {F_.get('luke')} (forced: {F_.get('forced')}), frames with a fade up under a held line {F_['held_up']} (<= 2)")
if A.window: print('WINSUM shot frames', W_['n'], 'VIEW_MODE 4', W_['vm4'], 'index 4', W_['ix4'], 'B4 hidden', W_['b4hid'],
                   'window placed', W_['win'], '| after the shot: frames', W_['after'], 'VIEW_MODE 4', W_['after4'])
if A.window and A.check: check('window', W_['n'] >= 100 and W_['vm4'] == W_['n'] and W_['win'] <= 2,
                               f"shot frames {W_['n']} (>= 100), of them VIEW_MODE 4 {W_['vm4']} (all), the window placed {W_['win']} (<= 2)")
if (A.window or A.cam) and A.check and (SL_['off'] is not None or '_dash' in os.path.basename(start)):   # (a run that saw the view's return)
    cw = [kk for kk, i in SL_['said'] if i == LINE_COWARD]
    check('coward line', len(cw) == 1 and SL_['off'] is not None and abs(cw[0] - SL_['off']) <= 12,
          f"LINE_COWARD said at VIs {cw} (once), g_shot 0 after the jump at VI {SL_['off']} (within 12 VIs)")
if A.trail: print('TRAILSUM jump frames', T_['n'], 'trail drawn', T_['drawn'], 'head within 50 of the Falcon', T_['near'],
                  'Falcon on screen', T_['onscr'], '| before the flash: on screen and further each frame', T_['off_s'], 'frames, %.2f s of g_fj_t' % T_['off_t'],
                  '| the Falcon\'s screen place moved by g_fj_t 1.2: %.1f px' % T_['moved'], '| the trail on screen at g_fj_t >= 1.0 (fj, px)', T_['len1'],
                  '| before the flash: frames', T_['pre'], 'Falcon on screen', T_['pre_on'])
if A.trail and A.check:                                          # (the jump flies straight away from the held view: a dot by ~0.9 s)
    check('jump trail', T_['n'] >= 60 and T_['drawn'] >= 0.9 * T_['n'] and T_['pre'] > 0 and T_['pre_on'] == T_['pre'],
          f"jump frames {T_['n']} (>= 60), the trail drawn {T_['drawn']} (>= 90 %), the Falcon on screen before the flash {T_['pre_on']} of {T_['pre']} (all)")
if A.hull: print('HULLSUM fly-away frames', H_['n'], 'hull below the Falcon on screen', H_['below'],
                 '(%.0f %%)' % (100 * H_['below'] / H_['n'] if H_['n'] else 0), 'MSG_HOLD frames', H_['hold'],
                 'over the hull (vertices within 200)', H_['over'], 'hp first', H_['hp0'], 'least', H_['hpmin'],
                 'nose pitch max |deg|', H_['pmax'])
if A.hull and A.check:
    pc = 100 * H_['below'] / H_['n'] if H_['n'] else 0
    check('fly-away', H_['n'] >= 150 and pc >= 80 and H_['hold'] == 0 and H_['pmax'] is not None and H_['pmax'] <= 16,
          f"frames {H_['n']} (>= 150), the hull below the Falcon {pc:.0f} % (>= 80), MSG_HOLD frames {H_['hold']} (0), nose pitch max {H_['pmax']} deg (<= 16)")
if A.reach: print('END k31', RCH['k31'])
if SAVE_AT: print('SAVESUM', {x: P['saved'].get(x) for x in SAVE_AT})
if A.bolts:
    B_ = P['bolts']
    print('BOLTSUM bolts', len(B_), 'owners', sorted({b['owner'] for b in B_}))
    if B_:
        for key, f in (('least dist to a dome', lambda b: min(b['d_dome'])), ('least dome off the bolt line', lambda b: min(l[0] for l in b['line'])),
                       ('bolt vs ship fwd deg', lambda b: b['a_ship'])):
            v = sorted(f(b) for b in B_); print('BOLTSUM', key, 'min/median/max', v[0], v[len(v) // 2], v[-1])
        loc = sorted({tuple(round(x) for x in b['local']) for b in B_}); print('BOLTSUM first places in the ship frame (rounded)', loc[:12])
        import collections
        print('BOLTSUM (first place, the game frame after) in the ship frame, rounded: count', sorted(collections.Counter(
            (tuple(round(x) for x in b['local']), tuple(round(x) for x in b.get('local2', ()))) for b in B_).items()))
        g = [x for b in B_ for x in b['guns']]
        if g: print('BOLTSUM gun fwd vs ship fwd deg min/max', min(x[2] for x in g), max(x[2] for x in g), 'bolt vs gun fwd deg min/max', min(x[4] for x in g), max(x[4] for x in g))
if A.sight and P['sight']:
    L = P['sight']; n = len(L)
    print('SIGHTSUM frames', n, 'per ring: drawn frames', [sum(1 for _, o, _ in L if o[i]['drawn']) for i in range(3)],
          'decoy frames', [sum(1 for _, o, _ in L if o[i]['decoy']) for i in range(3)], 'on screen frames',
          [sum(1 for _, o, _ in L if o[i]['scr'] and 0 <= o[i]['scr'][0] <= 320 and 0 <= o[i]['scr'][1] <= 240) for i in range(3)],
          'chor-falcon min/max', min(c for _, _, c in L), max(c for _, _, c in L))
print(f'hangar TIEs check, build {BUILD}, from {os.path.basename(start)}, kill {A.kill}, aim slot {A.aim}, plant {A.plant} ({S.get("planted", 0)} VIs): {S["end"]}')
for i, ch in sorted(S['objs'].items()): print('  obj', i, 'health changes (g_hang_t, from, to)', ch)
for ob, ent in sorted(S.get('lead', {}).items()):
    a = ent['aim']; er = ent['err']
    print('LEADSUM obj', ob, 'leader', sorted(ent['lead'], key=str), 'samples', ent['n'], 'node row1 == +0x30', ent['same'],
          'aim dist min/median/max', round(min(a), 1), round(sorted(a)[len(a) // 2], 1), round(max(a), 1),
          'leader-offset err max', round(max(er), 1) if er else None)
if A.all and S.get('all'):
    for lim in (300, 1000):
        for tag, ht, out in S['all']:
            near = [(o['i'], o['what'], o['falcon_d'], o['drawn']) for o in out if o['falcon_d'] < lim or o['node_falcon_d'] < lim]
            print('ALLSUM within', lim, 'of the Falcon at', tag, 'g_hang_t', round(ht, 2), ':', len(near), near)
if A.all:
    for i, g in sorted(S.get('ghost', {}).items()):
        print('GHOST obj', i, 'drawn within 1000 of the Falcon while its place is > 1000 off its node: frames', g['n'], 'first', g['first'],
              'last', g['last'], 'leaders', sorted(g['lead'], key=str), 'slots', sorted(g['slot']), 'nearest to the Falcon', g['near'])
    if not S.get('ghost'): print('GHOST none')
if A.clear and 'clr' in S:
    C = S['clr']
    print('CLEAR scene: per slot least x,y to Chor', {sl: round(v, 1) for sl, v in sorted(C['xy'].items())})
    print('CLEAR scene: per slot per object largest drawn-nose turn between samples (rad, g_hang_t)', dict(sorted(C['turn'].items())))
    print('CLEAR scene: per object samples with a turn > 0.3 rad (count, first g_hang_t, last)',
          {sl: (len(v), v[0], v[-1]) for sl, v in sorted(C.get('flips', {}).items())})
    if A.chase:
        print('CLEAR chase', A.chase, 's: per object largest drawn-nose turn between samples (rad, g_hang_t)', dict(sorted(C.get('turn_c', {}).items())))
        print('CLEAR chase: per object samples with a turn > 0.3 rad (count, first g_hang_t, last)',
              {sl: (len(v), v[0], v[-1]) for sl, v in sorted(C.get('flips_c', {}).items())})
    jm = {}
    for sl, v in C.get('npos', {}).items():
        for (ta, a), (tb, b) in zip(v, v[1:]):
            d = math.dist(a, b)
            if d > jm.get(sl, (0,))[0]: jm[sl] = (round(d), tb)
    print('CLEAR scene: per object largest jump of the drawn node between samples (units, g_hang_t)', dict(sorted(jm.items())))
    if C['start']: print('CLEAR chase start g_hang_t', round(C['start'][0], 2), 'slots filled', C['start'][1], 'objs', C['start'][2],
                         'first within 600 of Chor (g_hang_t)', dict(sorted(C['near'].items())))
if A.clear: end_clear_summary()
if CHECKS: sys.exit(0 if all(CHECKS) else 1)
