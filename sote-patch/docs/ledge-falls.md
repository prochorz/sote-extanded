# Falling off ledges: two approaches

The user kept falling into the crevasse past the girder bridge on Escape from Echo Base
(`local/states/echo_crevasse.st`, the side openings at the far end drop to z −125). With
camera-relative controls Dash turns in an arc, and on a phone the virtual stick sits at full
tilt, so he walks off edges he didn't mean to. Two fixes were built; the second one shipped.

Game facts used here (velocity, flags, animation system, matrices, hook points) are in
[`../../docs/reverse-engineering.md`](../../docs/reverse-engineering.md).

## 1. Ledge guard (built, rolled back)

Dash stops at a drop instead of walking off it.

**How it worked** (inside the stick decode, both for normal movement and for Z-lock movement,
probing along the move direction: facing for forward/back, perpendicular for strafing):

1. Skip while airborne (flag `0x08000000` for Humn).
2. Speed estimate from the position change since the previous decode (ignore jumps > 5 units:
   respawn/teleport).
3. Probe distance = 2.5 units + 10 updates of the current speed (he slides on after the stick
   lets go, so the probe has to lead).
4. Probe along the intended move and, when moving, along the actual drift as well.
5. Each probe: first a horizontal ray at knee height (z + 1.5) from Dash to the probe point. A hit
   means a wall is in the way, so there is no ledge on that side. Otherwise a vertical ray from
   z + 3 down to z − 10: no hit means a drop deeper than 10 units, so Dash is held back (the forward
   intent and strafe intents zeroed for that frame).

**How it evolved:**

| Version | Change | Result on the crevasse / flat ground |
|---|---|---|
| a | lookahead 2.5, full stick tilt exempt (to allow walking off on purpose) | useless on a phone: the touch stick is always at full tilt |
| b | applies at any tilt; jump (A) meant as the way to drop on purpose | half tilt safe, full tilt still fell in 4 of 8 directions (inertia) |
| c | speed-scaled lookahead + drift probe | no falls, but 54 false stops in the Echo Base hangar and 210 in Suprosa: the long probe ended behind walls, outside the level |
| d | knee-height wall check before the floor probe | no falls, 0 false stops; bridges still crossable (slight slowdown near the rails) |

**Why it was rolled back.** Zeroing the forward intent at the edge also killed the run-up, so a jump
from the edge went straight up: there was no way to jump across a gap or down on purpose. The
user also felt it makes the game too easy. To bring it back, the jump problem has to be solved
first, e.g. keep the forward intent when the jump button is pressed, or disable the guard for a
moment after A.

## 2. Ledge hang (current)

Agreed rules (2026-10-06, widened from "only over an abyss, never after a jump"): walking or
running off an edge catches it over a drop of **twice his height or more** (`HANG_DEPTH` 13: an
abyss, the Gall hangar's upper floor 16 above the lower one), under a wall or a thin floor. The
edge he **jumped off** is never caught (a jump down stays a jump down), but **in a jump** he
catches the rim of a wall ahead that his hands reach. Stick **up** climbs, stick **down** lets
go. On foot only (`Humn`); the train player (`HumT`) is untouched.

### Changes of 2026-10-06 (user's videos from Gall)
- **Let go over a floor**: he fell in the death-fall pose and lay on the ground in it until
  `DROP_T` (3 s): the game picks an animation only on its own state changes, and the hook kept
  replacing its landing with the fall. Now a floor within `DROP_FLOOR` 60 under him at the let-go
  gives the jump pose (`jmpF` down, id 0x0D) instead of the fall (0x19); on landing the hook stops
  replacing animations and asks for the jump landing (0x0E), and the game goes on from there.
  Landing = on the ground and 1 below the hang, or `DROP_FREE_T` 0.5 s on the ground at the hang
  height (his sphere can rest on something beside him there); he may not rise while dropping.
  Gall hangar upper floor: lands on the floor 16 below, the game's own animation the same frame.
- **Hand on the wall, not the rim**: the walk to the rim allowed 0.6 per 0.25 step (67 degrees),
  so on the canyon's rounded rock tops it ran on down the curve and put the rim ~1 unit under the
  visible lip (22 catches from `gall_tp5/6`: ground point to rim −0.5 … −1.2). `EDGE_SLOPE` 0.25
  (45 degrees): the rim is where the top turns steeper than that; the same catches are now
  −0.1 … −0.8 (the rest is the real slope of the path).
- **Room under him**: a vertical ray at the hang point down to his feet must find no floor (a
  catch beside a big rock in the canyon had a floor 3 under the rim and his body in it). A cliff
  leaning out below the rim is no floor: a second ray 0.5 further out hitting 0.5 or more lower
  (steeper than 45 degrees) lets it pass (`gall_tp6` loses 4 of 11 catches without that).
- **Thin floors** (no face under the rim, or one further in than `FACE_DEEP`): he hangs free
  under the rim (`g_hang_gap` −1), unless something is in the way of his body: rays toward the
  wall at 2.5 and 4.5 under the rim from 0.5 outside him to 1 inside the rim must not hit nearer
  than 0.4 in front of him. The Echo Base bridge then caught on its side (6 of 72 in
  `t_hang_spots`, hand on the lower girder, nothing through the arms); no longer (next item).
- **Free hang only where it is clean** (user's video, later that day, from the Echo Base truss
  bridge: he hung under the deck among the girders, hid behind them, caught a thin pipe, the
  camera ended under the bridge; "it was better before"; the user chose "catch only on clean
  spots"). The truss sides have no collision, so rays don't see them; the bridge deck is only
  5.7 across. `free_hang_clear` (`g_hang_why` 6/7): floor unbroken for `FREE_WIDE` 8 behind the
  rim (1-unit steps, ±0.5 a step), straight in at 0 and ±`FREE_SIDE` 1.5 to the side and turned
  ±40° (left near the bridge's end at a slant, the ice beyond it is straight in); nothing at
  rim + 2 / + 4 across the rim at ±1.5; nothing beside his body (±1.5) or in front of it at
  1.5 / 3.5 / 5.5 under the rim; the camera fits on one of its two sides. `t_hang_bridge.py`
  (`hang_bridge`): Dash on the deck at 4 points × 12 directions: 11 free hangs before, 0 now
  (he falls there as in the unpatched game); the crevasse side catch in `hang_spots` is gone too.
- **Later still (user's Gall videos, 2026-10-06 afternoon)**:
  - **Jetpack**: he caught the air beside a cliff mid-flight. No catch from the frame the
    jetpack fires (Humn flags `FL_JET` 0x300; fuel float at `+0xBC`; it keeps the `jmpF`
    animation, not `flyy`) until he stands again (`H.jet`). In the harness the jetpack comes
    from Cheats → Get all stuff, then jump, C-left, hold A. `t_hang_jet.py` (`hang_jet`).
  - **Jump catch stricter** (the user chose it over removing it): he caught rounded rock tops
    and slopes and hung with his feet on the slope below. Now only a sheer wall: a face 1, 3 and
    5 under the rim within `JUMP_PLUMB` 0.75 of each other, no free hang, `JUMP_CLEAR` 1.5 of
    room under his feet, and a climb spot up there (`g_hang_why` 8/9). The 7-unit block on the
    Echo Base stairs is no longer caught (`hang_more lowjump`); the positive case is now a wall
    in the Gall canyon (`gall_tp5.st`, 210°, A at frame 30). `t_hang_jumpcatch.py`
    (`hang_jumpcatch`): Gall jumps in 12 directions × 3 take-off frames.
  - **Climb spot** (`climb_spot`): a vertical ray from rim + 2 to rim − 1.5 took any hit, so a
    climb could end on a steep slope or a narrow ridge, and he slid off (once into the abyss) or
    slid back and caught the same rim again ("climbs twice, the second time without the
    animation"). Now the spot is 3, 4.5 or 6 in (no 1.5), with floor within `CLIMB_FLOOR` 0.6
    of the rim's height there and 1 unit to all four sides, rising at most `CLIMB_SLOPE` 0.75
    over the next 1.5 in; else the floor he left if 3 or more from the rim; else no climb (he
    keeps hanging, down still lets go). On the Gall jump test an enemy standing on that rock
    ridge pushed him off after the climb: game behaviour, the test checks the height at the
    end of the climb.
  - **Hanging means he can climb** (the user's rule, after "stick up does nothing" on a Gall
    path rising from the rim): `climb_target` takes the best spot above; failing that any floor
    near the rim's height 1.5-6 in, else 2 in at the rim's height. Never "no climb". The good
    spot allows a floor up to `CLIMB_UP` 2 above the rim, needs floor 1 further in (on a narrow
    strip the far edge was picked and he slid off it) and on at least one side.
  - **Evening fixes (user's videos)**: the last climb fallback "2 in at the rim's height" put
    him inside the Outrider's hull and he fell through it: now the floor he last stood on.
    `JUMP_CLEAR` 1.5 → 3: out of a raised cave mouth he jumped onto an 8.5-unit rock by the path
    (`gall_tp5`, around (−451, 40)), hung with his feet 2 over the ground, climbed its slanted
    top and slid back onto the same rim; no jump catch there now. `t_hang_sweep.py` reports
    `fell` (more than 3 below the climb spot afterwards), `JUMP=` frames, `VERBOSE=1`.
  - **Moving platforms** (Gall hangar hover platforms, class tag "Info", position `+0x50`; user's
    video: he caught one's rim and hung in the air after it flew on). The trace's `hit2` is a
    collision record; for a mover its `+0x6C` is the object, whose `+0x64` points back
    (`mover_of`). Standing on a mover, Dash's `+0x70` is that record: `H.gplat` remembers it on
    the ground (no trace), and in the air the floor point he left moves with it until the catch,
    so the edge is searched where the platform is now. At the catch, rays down 0.5-2.5 inside
    the rim find the object (else the one he walked off if the rim is on it) and note its
    position; `plat_moved` lets go (as the let-go drop, `g_hang_why` 11) as soon as it moves
    more than 0.05. Objects are not always movers: the hangar's upper floor is an "Info" too,
    and a canyon trooper ("Trop") stood by the rim of the old `hang_more` jump catch; both stay put and keep the hang.
    Riding along (`ride()`, 2026-10-06) was dropped on 2026-10-07: on Suprosa's machinery
    (user's video) it dragged him through walls. `t_hang_plat.py` (`hang_plat`): put on the
    platform, walk off in 8 directions: no hang on it lasts over 5 frames, and at least one
    ends by its move.
  - **Shafts** (2026-10-08, user's videos: a Sewers hatch that closed over him, a lift shaft in
    Xizor's Palace where the lift came up under him): no catch when a wall is behind him under
    `NARROW` 6 (rays out from the hang point at 1 and 3 under the rim, `g_hang_why` 12).
    `hang_spots` catches 61 instead of 70 (all still checked).
  - **A step under the traced-back rim** (2026-10-10, user's Imperial Garrison save
    `local/states/imp_bug1.st`: run off the high ground at (-476,56), walk off the lower step
    at z 210.6): he flew out over an abyss, the catch traced back to the step's rim, but under
    the hang point the slope is only 8.5 lower and he hung with his feet just over it. Walking
    off, the room-under-him ray now goes `HANG_DEPTH` 13 under the rim (was his feet + 0.6);
    jumps keep `JUMP_CLEAR`. `hang_spots` 57 (in its 55-61 noise).
  - **Running off on purpose** (2026-10-11): the first fix — off the edge faster than `RUN_SPEED`
    18/s only a death fall was caught (no floor within `DROP_FLOOR` 60 under him), a walk caught
    any drop — was removed the same day (the user: the same ledge behaving differently by speed
    felt arbitrary). Now walking or running off an edge deeper than `HANG_DEPTH` catches it, and a
    jump down (A) stays a jump down; to drop on purpose, jump. `hang_plat` and `hang_jetdrop` walk
    off at stick 55.
  - **Jetpack while hanging** (2026-10-11, user: it fired and he kept hanging): the jetpack
    flag (`FL_JET`) while he hangs or climbs ends the hang (let go, then `jet_out`: no held
    fall, no catch until he lands). `t_hang_jetdrop.py hang` (`hang_jethang`).
  - **Moved by the game, not down**: in a slow frame the game's own fall carried him ~12 down
    during the catch, `hang_moved` took it for a teleport and dropped the hang. A move down
    no longer counts (teleports and respawns move him sideways or up).
  - `t_hang_sweep.py`: grid of points around a state's start × directions, walk off, climb,
    stand; reports `moved` (`g_hang_moved_n`), a hang ended without climb or let-go, a second
    catch after the climb with the stick centred, and odd faces. Gall tp5/tp6, 30 × 10 grid,
    4 directions: 40 catches; the one odd case was the "moved" above.
- **Jump catch** (`front_grab`): every airborne frame after a jump, a ray `JUMP_RAY_Z` 2 above
  his feet up to `JUMP_WALL` 2.5 ahead (his flight, else his facing) looks for a wall; a ray down
  0.5 inside it from `JUMP_REACH_HI` + 1.5 finds its top. Caught if that is `JUMP_REACH_LO` 2 to
  `JUMP_REACH_HI` 7.2 above his feet, he will not clear it on the way up (apex + `LAND_UP`), and
  there is floor to stand on 1.5 and 3 inside at its height (a slanted rock top in the canyon: he
  climbed it and slid off). Then the usual edge walk from 1 inside back toward him and all its
  checks. Echo Base stairs (`echo_stairs.st`, 45 degrees, A at frame 14): catches the 7-unit
  block on the way down and climbs onto it. In 40 canyon jumps 1 catch, 0 in 32 on the Gall
  upper floor: only where a wall's top is in reach.
- Climbing ends, when no floor is found 3–6 inside the rim, 2 inside the floor point the edge
  walk started from (was always the floor he walked off: wrong for a far rim or a jump catch).
- Tried and rolled back: pushing him down 0.25 a frame while the game had him standing at the
  hang height after a let-go (the game put him back each frame), an extra 1.5 out at once after
  a free hang, and an "underside" ray for thin floors (it hit under the Gall hangar's upper
  floor too). Under that floor (−7.1, 47.9, 30 degrees) the game still moves him back on top
  after a let-go from a free hang: rare, left as is.

### Trigger
- While on the ground (`0x04000000` set, `0x08000000` clear, not rising) remember the position
  and whether the jump button is down.
- **A jump is also "rising faster than 1 unit/s"** (`JUMP_VZ`). A short tap of A is up again
  while the ground flag is still set on the take-off frame, so the button alone missed it and the
  jump itself was caught (the "hangs somewhere odd after jumping off the bridge" report).
- When airborne without a jump, the catch fires as soon as Dash is below the last floor
  (`HANG_TRIGGER` 0.05, was 0.5 and before that 1.5) and at most 10 units below it, at most 25
  units out from it horizontally, a ray from his feet down to `HANG_DEPTH` (13, was 20) under the
  floor he left finds nothing (not a step down), and the edge below is found (next section).
- **Jetpack after letting go** (user, 2026-10-11): the let-go fall holds him under the edge
  (no rising, stick ignored) for up to `DROP_T`; firing the jetpack in it did nothing for seconds.
  Now the jetpack flag (`FL_JET`) ends the let-go fall at once (`jet_out`, both in the decode and
  in the control-end hook) and counts as a flight (no catch until he lands). `t_hang_jetdrop.py`.
- **Still "standing" on the rim**: his collision sphere holds him on the rim while his centre is
  already over the drop, and the game keeps the ground flag for a frame or two, showing him
  striding out into the air (the user saw ~3 frames of a forward jump in the slow-motion video
  before he started turning to the wall). So a frame with the ground flag set but nothing under
  his centre for `HANG_DEPTH` also tries the catch (no jump held), with the floor point kept from the
  last frame that had floor under him. That ray ran every frame and cost ~8% of the frame
  (2026-10-09, `floor_under`): now none while he stands still on floor it already found, every
  other frame while he walks, and level geometry only unless he stands on a mover. The tests
  saw no lost catches from it; their paths moved with the lighter frame (see `t_hang_more.py`,
  `t_hang_spots.py`). Measured on `echo_crevasse.st` (stick −57,−57, GLideN64):
  the catch now starts 1 game frame after his centre passes the edge (was 3).
- Jumping off the edge is not affected: a sweep of the A press frame (`t_hang.py jump`, k 40–62,
  sticks 80,0 and −57,−57) gives the same last frame that still jumps for the old and the new
  trigger. A jump once his centre is already over the drop was too late before as well. (Undoing
  a rim catch on a late A was tried: at 10–15 game frames/s he has dropped several units by the
  frame the press shows up, so it would pop him back up; removed.)
- **Not over a gap he clears**: running off one ice block toward the next (Echo Base, by the
  girder bridge, `echo_catwalk.st` directions 22–44°: a ~4 unit gap, the far side 1 unit lower)
  he caught the near edge on the 4th frame of the flight, where the unpatched game carries him
  across (reported by the user). Before a catch the flight is now predicted: from his velocity
  (`+0x98`, kept in the air) and gravity (`GRAVITY` 30 units/s², measured: vz −1 → −12 in
  0.37 s), a vertical ray every `LAND_STEP` 0.05 s of the path, from the previous step's height
  down to this one's, looks for a floor until the path is `HANG_DEPTH` below the last floor; a
  floor found and nothing in the way to it (one horizontal ray at that floor's height + 1)
  means he lands: no catch. Made once per flight (rays are costly) and again only when his
  horizontal velocity changes by more than `LAND_DV` 2 (he hit the far side).
- **The far side higher** (the user's second report: back from that block the rim is 1 unit
  above it): hitting the far face fast, the game lifts him onto a rim well above his path
  (+1.1 to +2.4 measured; at 200° from `echo_gapblock.st` he slides along the face from
  z −0.3 up onto 2.2). So the ray starts `LAND_UP` 1.5 above the higher of the path and the
  floor he left, and the "in the way" ray runs at the landing floor's height, not his.
- **Didn't make it**: that lets some flights look like landings that end in the abyss (225°
  from `echo_gapblock.st`: he hits the face, slides down it onto a ledge at −2.6 and off into
  the crevasse). Once he is `LAND_MISS` 1.5 below both the floor he left and the predicted one,
  the prediction is dropped for the rest of the flight and the catch works again.
- **Which rim after a miss**: at first that catch took the edge he ran off, so he was pulled
  ~8 units back across the gap (225°; the user saw it: "he hangs far from the spot"). Now it
  first tries the rim of the floor he flew at: the edge walk starts at the predicted landing
  point and goes toward the floor he left (not toward him: he may have slid down right under
  that point), so he hangs on the face he hit, 1.6 units from where the catch starts (225°;
  235° the same). Only if no rim is found there does he catch the edge he ran off.
- **A narrow strip of floor**: the edge search starts `EDGE_BACK` 3 units back from the last
  floor point; on the ~2.4 unit wide block past that gap the start was over the gap he had just
  cleared, so no edge was found and he fell without a catch off its far side. The start now
  moves nearer (3, 1.5, 0) until it has floor under it.
- After letting go there is no second catch until he touches the ground.
- The game's own "falling to death" flag (`0x10000000`) would also work but comes too late
  (≈20 units down), so it isn't used.
- **Open stairs** (user report, 2026-10-04: running up the Echo Base metal stairs after the
  lift was jerky, seemed to hang, once he fell between the steps): the ray down his centre
  goes through the gap between two steps, so every such frame ran the flight prediction and
  the edge search, up to ~180 rays: game frames of 0.3–0.6 s (normal ~0.04), in which he moved
  up to 14 units and could pass through a step. Now, before those, rays down every
  `STEP_PROBE` 0.75 up to `STEP_REACH` 3 ahead of him (the way he moves, else his facing), from
  `STEP_UP` 3 above his feet to `HANG_DEPTH` below: a floor there is the next step, no catch.
  On `echo_stairs.st` (`t_stairs.py`): at most 3 rays a frame, longest frame 0.118 s (0.107
  without hang, 0.083 unpatched), camera pitch going up −5.5…+1.6°.

### Where he hangs
The rule (the user's, after several "he hangs far from the ledge" reports): from the last point
he stood on, walk along the way he went on the surface until it ends, and put him there.
- **The way he went**: his velocity on the last frame on the floor (`H.gv`), not the line from
  that point to where he is when the catch starts (the air has carried him on, a wall may have
  turned him). Under 1 unit/s: that line; failing that, his heading.
- **The walk**: from the last floor point (from 3 units back, then 1.5, then 0: standing on a
  rim his centre is already past it, held by his collision sphere; on a narrow strip, back there
  is the gap he just cleared) in `EDGE_STEP` 0.25 steps, each a short vertical ray at most
  `EDGE_SLOPE` 0.6 above or below the last height, until the floor ends; 4 bisections refine
  it. The window used to be 2 above / 2.5 below in 0.5 steps: the walk could run on down onto a
  ledge below the rim and put the "edge" there. No floor end found: no catch.
- **Facing**: square to the rim if the edge line (the same walk 1 unit to either side) is within
  ~35° of his way (`EDGE_TURN_COS`), else straight along his way (an odd side point at a corner
  turned him away from where he went over).
- Tried and rolled back (2026-10-05, the user preferred the version before it): always square
  to the rim (side walks 2 to either side, the half nearer his way at a corner), then square to
  the face he sees (three short rays toward the wall under the rim), with the pose turned only
  8°/13° side-on instead of 22°/30°. On the test spots it left him square to every straight
  face (9 of 55 had been 9–52° off), but the user found the previous look better.
- **Not a wall**: a horizontal ray 2 above the rim, from 1.5 out to 1 in, must not hit.
- **A wall under the rim**: from the hang point a ray toward the wall 1 under the rim must hit
  within `HANG_OUT` + `FACE_DEEP` 1 (an undercut up to 1 is fine). No face (a thin floor: the
  girder bridge deck) or a far one (an overhang): no catch, he fell as in the unpatched game
  (since 2026-10-06 a free hang if his body has room, see above). He used to hang there in the
  air, arms through the bridge's girders (the user's video at the bridge). A face nearer than `HANG_OUT` (leaning out below the rim) puts him that much further out.
- **Removed**: the face ray and the lip ray started 4 units *outside* the edge and took the first
  thing they hit as the cliff: next to the bridge that was a girder or the next block, and he was
  put by it, units away from the rim. And the far-rim catch after a missed landing walks from
  the point he flew at back the way he came (see Trigger).
- Body `HANG_OUT` 1.55 out from the rim, feet 6.4 below it (`HANG_BELOW`; tuned by
  eye with the user: 7.0 and 6.0 too low, 5.2 too high, 5.6 and 6.3 close; 6.4 chosen).
- Before (rolled back long ago): a fan of 11 horizontal rays around the way back took the
  nearest wall; he hung on bridge girders, on sheer walls with no edge above, or in the air.
- **Test**: `harness/tests/t_hang_spots.py` (in `run_all.py` as `hang_spots`): the crevasse, the
  catwalk and the gap block, 24 directions at full and part tilt; every catch must have the face
  at 1.55 ± 0.5 from the hang point (`g_hang_gap`) and carry him at most 6 units. 69/69; before the rewrite 4 of 71 hung 4–5.5
  units from the face (the bridge deck). Overhead shots: `tools/video/record_hang_spots.py`.
- `hang.c` is built with `-Os` (`SIZE_OPT` in `build.py`): the payload was at 64.4 of 64 KB.
- Size (hang.o code + data, -Os): 21.9 KB -> 14.3 KB. The math (sin/cos/atan2/wrap180) has one
  out-of-line copy in `hang.c` (inlined from `common.h` it cost ~250 bytes per call: -3.6 KB);
  poses are `int16` x 100 holding only the 54 tracks the skeleton has (`track_mask`), not 19x6
  floats with `NO_TRACK` fillers (-3.4 KB); the report-only skew rays are gone.

### Holding him
- At the start of the decode: zero the movement intents and the stick, mask jump/aim.
- **No shooting**: the fire button is checked in Dash's weapon code (`0x80072324`), which runs
  before the decode hook, so masking the button there let one shot out per press. A hook on that
  branch (`tramp_fire`) takes the "not pressed" path while hanging or falling from a hang.
- **At the end of the control function** (hook `0x8007A104`): write position (both copies),
  velocity 0, yaw (both copies: `+0x8C` and `+0x14`; the game restores `+0x8C` from `+0x14`
  every frame), and the rotation rows of `+0x20`, `+0x148` and **`+0x208`**. Writing earlier in
  the frame does nothing: the game redoes physics, heading and these matrices later in the same
  update. The model is drawn with `+0x208` (passed by the draw method `0x8007A118`). It took a
  while to find. `+0x20`/`+0x148`/yaw alone changed nothing on screen. `+0x108` must not be
  touched, or the camera turns with him.
- **The translation of the drawn matrices too.** The body matrix `+0x148` (copied to `+0x108`)
  normally sits 5.5 above the feet (`BODY_LIFT`) at the same x/y, and `+0x208` keeps the pose
  root's offset from it. While hanging, the body's collision sphere touches the rim and the game
  pushed the drawn body out of it by a different amount on every catch: up to 1.6 units up or
  down and ~1 unit off the wall, so the hand ended on the rim, above it or below it at random
  (reported by the user after 6.4 was chosen). Now `+0x148`/`+0x108`/`+0x208` translations are
  written from the hold position too; `HANG_OUT` went 1.0 → 2.0 to keep the old look (the push
  used to add about 1 unit). From behind 2.0 looked right, but the user switched to the overhead
  and drop views and saw him hanging in the air: the hang pose's hands are only ~1.4 units nearer
  the wall than his body (23 model units, 1/16 scale), so at 2.0 the hands were ~0.6 short of
  the rim, more where the face is undercut. Overhead shots with the rim projected on them
  (0.6 / 1.2 / 2.0): at 1.2 the fingertips reach the rim, at 0.6 the hands lie on the ledge.
  1.0 put the hands on the rim seen from above, but the user then saw his arm go into the ice:
  the hang pose has the wrists 1.41–1.45 and the elbows 1.05 nearer the wall than the body
  (`harness/pose`, model units / 16) with the wrists at rim height, so at 1.0 the forearms were
  inside the face below the rim, and from behind one arm vanished in it (it looked like he held
  on with one hand). Now 1.55: wrists ~0.1 outside the lip, forearms hang along the face, the
  hands stick up over the rim. Measured from the lip: a horizontal ray 0.3 under the rim finds
  it; when it sticks out past the face (an undercut, up to 1 unit; a farther hit is something
  else, e.g. a girder) he hangs that much further out.
- **Hands over the rim**: at 1.55 the user still saw (from above) the hands end just short of
  the rim: the wrists sit at rim height 0.14 outside the lip with the fingers pointing straight
  up. The hands have one rotation track (z): left +55° / right −55° (was ∓17°) bends them toward
  the wall, so the fingers reach ~0.3 over the lip and lie ~0.1–0.2 above the top
  (`harness/pose/newhang.py` prints wrist and fingertip positions; the fingertip is estimated
  as 0.45 × the hand's offset from the forearm, along the hand's axis). An IK move of the wrists
  onto the lip did not reach without moving the torso.
- **Moved by the game** (`hang_moved`): the hold rewrites his position every frame, so a Cheats
  Teleport or This Level / Go to level while he hung put him straight back on the old edge (after
  a level reload: hanging in the air over the old crevasse, the blaster out). Now the decode and
  the control-function end compare his position with the hold point first: more than 5 units off
  means the game put him elsewhere, and the hang is dropped quietly (no `hang_end` animation
  switch: the game's animation controller may belong to the level that is gone, and its own
  animation was never touched while he hung). The fall after letting go checks "moved" (3 units
  off his drop line) before its height clamp, which used to keep the old height after a teleport.
- **Twisted in a fight**: with enemies around, the game turned his neck (~30°) and chest (~24°)
  toward them by rotating those model nodes after the pose was evaluated (the bone angles in the
  block stayed the pose's): seen from above he hung turned, one hand on the rim and one in the
  air. `untwist()` rebuilds the neck and chest node rotations from the pose's angles in every
  hold (`hang_face`), so a fight and a quiet hang give the same nodes.

### Pose
- Dash has no hanging animation. Candidates were compared from behind on the wall. The user chose **#12: the jetpack
  animation `flyy`, frozen on frame 10**: body straight, legs down, one arm up.
- **Our own animation `hang`** (current): flyy frame 10 with the right arm raised as well, so he
  hangs on both hands. It is a copy of Dash's `flyy` animation block (same skeleton and model
  nodes, pointers inside the block relocated) named `hang`, whose tracks point to our own
  two-frame arrays holding `hang_pose` (`src/hang.c`). The right arm (bones 8 → 7 → 6) is the left
  one (5 → 4 → 3) mirrored across the body's x plane: angles (z, x, y) → (−z, x, −y). The copy is
  rebuilt at each catch (blocks and nodes move with every level) and put at the head of Dash's
  animation chain (`+0x19C`) only while he hangs; `hang_end` puts the chain back. If his chain
  has no `flyy` block or the skeleton isn't the expected 19 bones, the old flyy frame is used.
  Animation block format: [reverse-engineering.md](../../docs/reverse-engineering.md).
- **No blaster in his hand** while he hangs or climbs: the right hand's model node lists the hand
  mesh and the weapon mesh (first word bit `0x80`); it is pointed at our own list without the
  weapon, and `hang_end` gives it the game's list back.
- Fed through a hook on `set_anim`'s entry (`0x800175B8`): while hanging, every request for
  Dash's animation state is replaced by our own animation controller and descriptor
  `{hang, start 1, blend 0, frames/s 0, kind 0}` (`{flyy, start 10, ...}` as the fallback). Its "current" pointer is reset before every
  call, so the pose is re-evaluated every frame. Kind 0 keeps the game's next animation from being
  refused afterwards.
- The borrowed frames have the body turned round on the root, so the hang yaw is the wall
  direction + 180°.
- When hanging ends, point the game's controller at our descriptor and call `set_anim` once
  with stand (id 0) after a climb or the death fall (id 0x19) after letting go. The game only picks
  animations on its own state changes and would otherwise keep the hang pose.

- **On one hand** (current, asked for by the user from a reference clip of another game's
  ledge hang): he hangs on the left hand only, the right arm down along the body, and puts the
  right hand on the rim only when he climbs. `hang1_keys` in `src/hang.c`, made with
  `harness/pose/onehand.py`: hips and legs straight down, the spine and chest leaning away from
  the hand (12°, so the hips hang under it), the body turned side-on (22°, left shoulder toward
  the wall), the left arm straight (0.97 of its length) to the same hand point on the rim as
  `hang_pose`; with the arm straight the body hangs `HANG1_DROP` 0.33 lower. He sways between
  two such poses (spine 12° / 9°, turn 22° / 30°) once per `SWAY_T` 2.6 s. The arms are solved
  by IK from many starts, keeping the fit nearest the reference angles: the first version had
  the two sway poses on different Euler branches, and a blend between them would have swung
  the arm round (`blend_check` prints how far a joint leaves its straight path mid-blend).
  The two-handed `hang_pose` is now only the climb's pull-up start.

### Feel
- **Catch pose** (our animation, `catch_keys` in `src/hang.c`, made with
  `harness/pose/onehand.py`; the two-handed one was `gen_catch.py`): reaching for the rim with
  the left hand, the right arm thrown out, knees up (0 s) → the left hand takes it at the bottom
  of the dip, arm straight, legs swinging out (0.20 s) → legs swing back toward the wall
  (0.38 s) → the one-hand hang (0.58 s). Smoothstep blends, written into the `hang` block's tracks
  every frame like the climb.
- **Catch**: over 0.20 s (`HANG_FALL_T`) he swings in from where he was to the hang point
  (ease-out) while dropping to 0.8 below it, then eases up to it in 0.15 s. In the same 0.20 s
  (`HANG_SPIN_T`) he spins round from his run-off heading to face the cliff (ease-out, shortest
  way). With the earlier trigger the turn starts ~0.1 s after he leaves the floor (was a slow
  drift out over the abyss, then a snap round).
- Tried and rolled back (2026-10-04): a misstep with a one-handed catch (left hand, then the
  right), and a version where he hangs on the left hand facing the abyss, looking down, then
  turns to the wall pivoting on that hand. The facing-out spot and the turn put him into the
  cliff (turning one way swung the body 0.4 into the wall), and the user kept this catch.
- **Camera**: swings round to face the wall from 40° off his back (rate 6/s), so the hang and
  the climb show from the side. The side is picked once at the catch: for ±40° the game camera's
  own ray (see `docs/reverse-engineering.md`, follow camera) is traced from the hang point; a hit
  within twice the camera distance would pull the camera in for a close-up. Both sides clear:
  the one the camera turns to least; neither: straight behind him (0°). Kept through the climb
  or the fall. A plain ray from his chest (or with the trace's object flag 1) missed what blocks
  the camera and picked the cramped side. Tested angles: ±30–45° look right; 60° puts him small
  at the edge of the frame; into a blocked side the camera ends 2.7–5 units from him.
  The first frames are close-ups while it swings.
- **Climb (up)**: our own keyframed animation in the same `hang` block (the tracks are rewritten
  every frame with a smoothstep blend of keyframes, `climb_keys` in `src/hang.c`):
  first `CLIMB_REACH_T` 0.30 s the right hand comes up to the rim (from wherever the sway is,
  through `hang1_keys[2]`, the right hand beside his head, into `hang_pose`) while the body
  rises the `HANG1_DROP`; then, counted from there, 0–0.35 s pull up (chin to the rim, elbows out, body +2.1), 0.35–0.65 s mantle (chest over the
  rim, arms pushing down, one knee up, body +4.3), 0.65–0.95 s onto the ledge into a crouch (up
  first so the feet clear the rim, forward after), then the game's stand. The keyframes were
  made offline from the hang pose with `harness/pose/` (Dash's skeleton from a RAM dump, inverse
  kinematics for the arms so the hands stay on the rim while the body rises, stick-figure
  previews; `gen_keys.py` prints the table). Before: 0.30 s up along the wall in the `crou` frame 4
  pose, then 0.15 s forward. The spot is the first point 3–6 units inside the edge with floor at its
  height, else 2 units inside the last floor (icy slopes made him slide back off when it was too
  close). He ends facing inland: yaw = wall − 90 (the standing pose has no 180° root turn), also
  written to the heading copy `+0x14` and to the patch's target heading. Without the copy the
  game put back his run-off heading the moment the hold stopped, so he stood facing the abyss. Afterwards the stick is ignored until it is centred: camera-relative "up" can point back
  over the edge.
- **Let go (down) or shot down**: he falls down the face, back to the camera, in the
  `fall` animation from the first frame (`g_hang_drop`): x/y held, horizontal velocity 0, every
  animation request for him replaced by `fall` (0x19). Left alone, the game pushed him ~12 units
  out from the wall, past the camera, which then looked down at nothing for about a second, and
  showed the jump pose. Ends when the game's own pit camera takes over (`0x10000000`), on
  landing, when the game moves him (respawn) or after 3 s (`DROP_T`).
  Held at the hang point, the fall pose (leaning forward, head first) put his head into the
  wall, so he now eases `DROP_OUT` 3 units out from it over `DROP_OUT_T` 0.4 s while he falls.
- Being shot down sets no flag on Dash: health (`+0xB4`) reaching 0 starts the game's death
  sequence. Before, the hang kept holding him through it (he even respawned hanging). Now health
  ≤ 0 while hanging lets go as above.
- Up/down only count after the stick has been centred once after the catch, or the run-off
  direction would instantly climb or let go.
- No on-screen hint: two arrows (▲ climb, ▼ let go) beside his head were removed at the user's
  request; the pose makes it clear enough.

### Constants (`src/hang.c`)
The whole feature is `src/hang.c` (plus its three hooks in `hooks.S` under `FEATURE_HANG`);
`build.py --without hang` builds the patch without it.

`HANG_TRIGGER 0.05`, `HANG_REACH 10`, `HANG_SLIDE 25`, `HANG_DEPTH 13`, `HANG_BELOW 6.4`,
`HANG_OUT 1.55`, `EDGE_STEP 0.25`, `EDGE_SLOPE 0.25`, `JUMP_WALL 2.5`, `JUMP_RAY_Z 2`, `JUMP_REACH_LO 2`,
`JUMP_REACH_HI 7.2`, `JUMP_PLUMB 0.75`, `JUMP_CLEAR 3`, `CLIMB_FLOOR 0.6`, `CLIMB_UP 2`, `CLIMB_SLOPE 0.75`, `FREE_WIDE 8`, `FREE_SIDE 1.5`, `DROP_FLOOR 60`, `DROP_FREE_T 0.5`, `EDGE_TURN_COS 0.82`, `FACE_DEEP 1`, `BODY_LIFT 5.5`, `HANG_STICK 40`, `HANG_FRAME 10`, `HANG_POSE_TURN 180`, `HANG_SPIN_T 0.20`, `HANG_DIP 0.8`,
`HANG_FALL_T 0.20`, `HANG_CATCH_T 0.15`, `CLIMB_UP_T 0.30`, `CLIMB_FWD_T 0.15`, `EDGE_BACK 3`, `STEP_PROBE 0.75`, `STEP_REACH 3`, `STEP_UP 3`, `JUMP_VZ 1`,
`HANG1_DROP 0.33`, `SWAY_T 2.6`, `CLIMB_REACH_T 0.30`, `DROP_T 3`, `GRAVITY 30`, `LAND_STEP 0.05`, `LAND_DV 2`, `LAND_UP 1.5`, `LAND_MISS 1.5`, `DROP_OUT 3`, `DROP_OUT_T 0.4`, `CAM_HANG 6`, `HANG_CAM_SIDE 40`, `HANG_CAM_DIST 8`, `HANG_CAM_RAY_Z 6.2`.

### Tests
- `harness/tests/t_hang.py <rom> climb|drop|jump|kill|fire [stick x,y]` on `echo_crevasse.st`.
  Directions 80,0, −80,0 and −57,−57 reach the crevasse; 57,−57 doesn't. Jump: no catch. Kill:
  he lets go when shot down (depends on the troopers hitting him: in one run they missed for the
  whole hang, with the previous release too; health set to 0 directly lets go). Fire: no shot while hanging. `t_move.py` reports "ledge grabs
  during the walk" (must be 0 on flat ground).
- `harness/tests/t_hang_dirs.py`: 8 directions × (walk off, tap A at frames 15–60), prints each catch
  (floor point, face, rim, hang point) and a shot 40 frames later. Every catch must be a walk-off:
  a jump that bumps the low cave ceiling and lands still counts as walking off afterwards.
- Gap: `echo_catwalk.st` at full tilt toward 22° and 44° (camera-relative) crosses the gap
  to the next block like the build without hang; at 22° he then runs off that block's far side
  and catches it. **Landing on the far rim**: in the test timing (no video plugin) he touches
  down at 22° with his centre over the gap; on that frame the "standing on the rim" catch still
  had the near side as its last floor and hung him on the edge he jumped from, pulled back
  across the gap (found 2026-10-06). The on-rim catch now needs him standing on the previous
  frame too (`was_ground`); he then slides off that rim and catches the block he landed on.
  `harness/tests/t_hang_gap.py` (22° and 44°): a catch after the landing must hold a rim no closer to
  the start than the landing point (the old build fails it: rim 10.4 vs landing 19.5).
- `harness/tests/t_hang_cheats.py tp|level`: hang on the crevasse, then pause → Cheats → Teleport /
  This Level; the hang must end and he must not be held at the old hang point. Back from that block (`echo_gapblock.st`, made by running there at 22° and
  standing still): 135°–200° cross back onto the higher side like the build without hang,
  225°–270° (the abyss) catch the block's edge.
- `harness/tests/t_edge.py`: falls per direction (all 6 deadly falls end in a catch now).
- `harness/tests/t_hang_more.py floor|lowjump|nofloor`: Gall hangar upper floor (`gall_tp1.st`, Dash put at
  (21.4, 19.6), the troopers near him killed) catch, let go, land on the floor with the game's animation within
  20 frames; no jump catch on the Echo Base stairs block; no catch beside the canyon rock (`gall_tp5.st`,
  330 degrees). Its old Gall canyon jump catch went (2026-10-28): it held only while a trooper by the rim pushed
  Dash against the face; jump catches are `t_hang_dirs.py`'s. `g_hang_why` (tests) says why the last edge search gave up.
- `harness/tests/t_hang_cam.py`: catches in several directions, a shot 60 frames later, the side
  picked and the game camera's distance from him (8 = not pulled in; all 6 catches from
  `echo_crevasse.st` get a side at 8). `OFFS=0,45,-45` forces angles for comparison.
- Video: `tools/video/record_hang_takes.py` + `compose_takes.py` → `local/demo/SotE_controls_ledge_hang.mp4`.

### Open ideas
- While hanging, the game still aims the free arm at a nearby enemy (the other arm rises).
- Snap the camera to its side at the catch instead of swinging.
- The train (`HumT`).
