---
name: sote-bot
description: Drive Star Wars Shadows of the Empire automatically in the mupen64plus harness - boot to any level, use the game's debug menu (teleport, next sub-level), make savestates at specific places, steer Dash with original or patched controls, run the hunter/route bots, and test features (lock-on, ledge hang, fog, bosses). Use when a test needs Dash somewhere in a level, needs enemies or a boss, or needs scripted play.
---

# Playing SotE from a script

Harness basics are in `docs/harness.md`; game structures in `docs/reverse-engineering.md`.
Scripts: `harness/` (tests `t_*.py`, helpers `game.py`, `debugmenu.py`, `tpstate.py`), bots in
`harness/bots/`.

## Getting Dash where you need him

1. **Existing savestates** (`local/states/`, load with `e.load_state()`, which fixes the ROM
   MD5 itself): `play.st` Echo Base start, `sup.st` Suprosa troopers, `om.st` Ord Mantell train, `om_drones.st` train with drones arriving, `echo_catwalk.st` /
   `echo_crevasse.st` / `echo_gapblock.st` Echo Base bridge, crevasse and gap, `echo_cave.st`,
   `echo_stairs.st`, `echo_atst.st` AT-ST fight running, `om_ig88.st` IG-88 arena, `lvl*.st`.
   The table with notes is in `docs/harness.md`; on a fresh clone `tools/setup.sh <rom> --tests` makes them
   (the event states too — AT-ST fight, drones, dianoga, the gladiator's second phase — by `states_make.py`'s
   `menu`, `ride`, `glad2` and `dianoga` recipes).
2. **Boot from power-on**: `mkstate.py <rom> <carousel index>` (`game.boot_events`, levels
   unlocked in RAM). Carousel: 0 Hoth, 1 Echo Base, 2 Asteroids, 3 Ord Mantell, 4 Gall,
   5 Mos Eisley, 6 Suprosa, 7 Sewers, 8 Xizor's Palace, 9 Skyhook.
   - **No Dash on vehicle levels**: 0 Hoth (snowspeeder), 2 Asteroids, 9 Skyhook are flown;
     `find_player()` returns 0 there. To test on-foot controls from power-on boot to **1 Echo Base**.
   - **Every level starts with a message box** that freezes input (`game.DLG_GATE` float > 0;
     g_ov_frames - g_decode_ov grows). Dismiss it with START (`BTN['START']` = 16, not 0x1000)
     every ~90 frames while the gate is up (as `bots/hunt.py` does) before expecting Dash to move.
3. **Game debug menu** (`debugmenu.py`): flag byte `0x800D098B`, cursor s16 `0x800D0990`.
   Items 6 Teleport (cycles the sub-level's teleport points), 7 Next Level (next *sub-level*).
   - The item under the cursor **already runs when the pause screen opens**: set the cursor
     before pressing START, or every pause with the cursor on Next Level skips a sub-level.
   - Turn the flag off right after; never leave it on in a saved state (menu text on screen).
   - `tpstate.py <rom> <start state> <next levels> <target x> <out>` does Next Level N times,
     then Teleport until Dash's x matches, waits, saves. Echo Base = sub-levels 4 and 5; the
     AT-ST arena is reached by teleport in sub-level 5 (that also plays its cutscene).
4. **Writing the position** (`+0x08` and `+0x50`, with z) works on static ground but skips
   scripted triggers (cutscenes, boss fights) and loses moving platforms (train).

Find the player: `g_player` payload symbol (after `inject`), `game.find_player(e)` (RAM scan,
works without the payload), or Humn at `0x801A7B50` in Echo Base states / HumT at `0x801A7AF4`
on the train. Unpatched game on any state: `inject(e, payload=False)`.

## Steering

- Patched controls (camera-relative): to move toward world angle `want`, with
  `cam = g_cam_facing`: `a = radians(want - cam); x = -sin(a)*80; y = cos(a)*80`.
- Original controls: turn with x proportional to the heading error, push y only when roughly
  facing (see `steer()` in `bots/demo_route.py`).
- Facing = yaw (`+0x8C` Humn, `+0x90` HumT) + 90.
- Jump (A) only works on the ground; pressing it while already falling does nothing.

## Lock-on (Z) in tests

- The lock is taken **on the Z press** only. Holding Z never re-locks; re-press to retry. When
  logging the lock, sample while Z is held (not on release frames).
- `g_test_skip_los = 1` skips line of sight (troopers in `sup.st` stand behind a wall).
- Fake targets: write `g_lock` directly. Never put fake objects in the game's target pool
  (`0x80112838`): the game updates them and freezes.
- Bosses: class `Boss` (AT-ST); lockable only while fighting (`+0x60` < 0) and not destroyed
  (flag `0x20` at `+6`).

## Bots

- `bots/hunt.py <rom> <level> <frames> <tag>`: boots to a level and plays: dismisses messages
  (START while `0x800DEB78` > 0), picks the nearest enemy from the pool, turns, locks with Z,
  circle-strafes and fires; blacklists a target that takes no damage for 5 s; detects being
  stuck (no movement) and turns ±70-120°; treats `g_ov_frames - g_decode_ov > 5` as a
  cutscene (press A, pause audio); gives up after 30 s without control. Logs labels for videos.
- `bots/swim.py <rom> [frames]`: under water in the sewer (local/states/sew_dianoga.st, the dianoga woken):
  Z on its eye (re-pressed every 3 s while on a tentacle), circles, fires, A swims up toward the eye;
  logs lock, eye/tentacle health (+0x7C) and the HUD. Kills the eye in ~36 s.
- `bots/demo_route.py <rom> orig|patch`: fixed Echo Base route and two trooper groups, the same
  for original and patched controls (for side-by-side videos).
- Both run from any directory (they put `harness/` on `sys.path`) and write their logs,
  raw audio and WAV to `local/run/` (`hunt_<tag>.*`, `demo_<mode>.*`).

## Pitfalls seen

- **Hangs: don't wait.** `Emu.run()` exits with code 3 and prints `HANG: no frame for N s after frame F` when
  the game stops rendering for `M64HANG` s (default 90). After a run, `grep HANG` its log; a take that "ends"
  early with no frames is a hang, not slowness. A state saved by an older build plus `inject()` of the new
  payload hangs: make a fresh state with the new build.
- Running off the Ord Mantell cars is fatal; the next car needs a precise jump. Train enemies
  spawn only further along the track (none near the three teleport points): use
  `om_drones.st`. Writing health is not enough on the train (overhead obstacles kill in one
  hit): turn on the debug menu's Invincibility (cursor 1, pause, unpause, flag off).
  The drones (`TGun`) are not in the target pool; they live in their class array.
- `M64CPU=0` whenever the payload is injected. Several emulators at once are fine (one core each),
  each with its own `SHOTS` dir; kill your runs when done.
- After a change, run the tests of the feature you touched (skill `sote-test`, or
  `python3 harness/run_all.py <names>`). The whole suite only when the user asks.
- Echo Base hazards and troopers hit Dash constantly; refill health (`+0xB4`).
- Ledge hang tests: `t_hang.py climb|drop|jump|kill|fire [stick]` on `echo_crevasse.st`; walking
  off at full tilt catches the edge in every direction except straight up the screen (0,80, a
  wall), including 57,-57 (`t_hang_dirs.py`, `WALK_CATCH`); `t_edge.py` checks no direction falls.
  Over a floor / no-catch spots: `t_hang_more.py` (Gall hangar upper floor in `gall_tp1.st`, written
  position; Echo Base stairs block); jump catches: `t_hang_dirs.py`. The stick is camera-relative and standing still ~1.5 s turns
  the camera: start moving within a few frames of loading a state when a direction must repeat.
