# Test harness

`harness/` runs SotE in mupen64plus (the core M64Plus FZ uses) from Python: a per-frame
callback, a scripted controller, direct RDRAM reads/writes, savestates and screenshots.
Any code payload (see [reverse-engineering.md](reverse-engineering.md)) can be injected into a
running game, so a change is tested in seconds without rebooting the ROM.

## Setup (macOS, Homebrew)

```bash
brew install mupen64plus llvm lld
cd harness && make                      # local/bin/input_script.dylib, local/bin/audio_dump.dylib
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

The tests themselves need only the system `python3`; `.venv` is for `disasm.py` (capstone),
`pose/`, `gallrun/` (numpy, scipy, pillow) and the video tools. (The shelved HD texture pipeline is kept
outside this repository.)

`local/bin/mupen64plus-video-GLideN64.dylib` is a GLideN64 build (needed only for texture work and
nicer screenshots; the default video plugin is rice). To rebuild it:

```bash
git clone https://github.com/gonetz/GLideN64 && cd GLideN64     # tested at 41c7ba27
# src/GLideNHQ/CMakeLists.txt: delete the two "-static" flags (Apple ld can't link them)
mkdir build && cd build && cmake -DMUPENPLUSAPI=On -DCMAKE_BUILD_TYPE=Release ../src && make -j
```

## Files

| File | What |
|---|---|
| `paths.py` | where the local files are (`ROOT`, `LOCAL`, `ROM_DIR`, `ROM`, `STATES`, `WORK`, `GAME`, `RUN`, `BIN`, `BUILD`; env `SOTE_LOCAL` moves `local/`): the harness takes every local path from it |
| `m64.py` | `Emu`: ctypes frontend over libmupen64plus. `pad`, `r32/r16/rf/w32/wf`, `shot`, `save_state`, `load_state`, `dump`, `unlimit`, `stop`. Runs unthrottled unless `M64LIMIT=1` or `e.unlimit(False)` (video takes); audio goes to `audio_dump.dylib` (silent, no real-time sync; `AUDIOPLUGIN` overrides) |
| `input_script.c` | input plugin; Python sets the pad word with `set_input()` |
| `audio_dump.c` | audio plugin that writes the game's sound to raw PCM (`AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib`, see the sote-video skill) |
| `inject.py` | `inject(e)` puts the game's own code back at every hook address any build uses (read from the `hook_table` in `sote-patch/src/hooks.S`, so states saved with more features work with a `--without` build), then writes `payload.bin`, zeroes its `.bss`, copies the sections `_start` loads from outside the payload (`cheatscode.bin` to `0x80540000` when the build has `cheats_frame`, the Falcon model, the Gall Run's code and image) and writes its hook table into RAM; `inject(e, payload=False)` only restores the game code: the unpatched game on any state. `syms()` gives payload symbols. Build dir: `PAYLOAD_BUILD` (e.g. a `build.py -o build/notrain --without train` build) |
| `game.py` | boot-to-level input script, level unlock, target pool, player helpers (`facing`, `set_health`, `find_player`), game addresses (`CAM`, `LEVEL_ID`, `DLG_GATE`, health/yaw offsets) |
| `testlib.py` | for tests: fake target (`FAKE`, `make_fake`, `place_fake`), `fog_expected`, `check()` / `report()` (PASS/FAIL lines, exit code) |
| `run_all.py` | runs the whole suite (or named tests) one after another, logs to `local/run/reg/<name>.log`, prints PASS/FAIL per test |
| `debugmenu.py` | game debug menu: flag on/off, cursor, pause/A input sequence |
| `tpstate.py` | savestate at a debug teleport point (Next Level ×N, then Teleport until x matches) |
| `level_blob.py` | `<rom> <id> <out.bin>`: a sub-level's unpacked blob, copied out the moment the game's unpacker returns (RAM patch on `0x80019284`); goes back into a ROM uncompressed (reverse-engineering.md, "Sub-level data") |
| `mkstate.py` | power-on → carousel level L → savestate |
| `gallrun/` | Gall Run (feature `gallrun`): `gall_asset.py` → `local/game/gall_run.bin` for `0x80628000`, `mesh_image.py` copies level meshes, route tools |
| `falcon_asset.py` | Falcon model from the ship-model source's RAM (`src_model.st`) → `local/game/falcon.bin`, pointers moved to `0x80500000`, scaled/turned for the Outrider's place (feature `falcon`, the Gall Run's ship) |
| `tests/`: `t_move.py`, `t_lock.py`, `t_orbit.py`, `t_fog.py`, `t_fogback.py`, `t_holdz.py`, `t_boss.py`, `t_ig88.py`, `t_ig88near.py`, `t_weapons.py`, `t_lockpitch.py`, `t_trainwall.py`, `t_glad.py`, `t_swimlock.py`, `t_sight.py`, `t_crate.py`, `t_edge.py`, `t_hang.py`, `t_hang_dirs.py`, `t_hang_more.py`, `t_hang_gap.py`, `t_hang_cheats.py`, `t_hang_jetdrop.py`, `t_hang_cam.py`, `t_switch.py`, `t_train.py`, `t_trainturn.py`, `t_trainz.py`, `t_traindroid.py`, `t_recenter.py`, `t_stairs.py`, `t_cheats.py`, `t_fuel.py`, `t_cheat_ship.py`, `t_wampa.py`, `t_friendly.py`, `t_off.py` | tests of the controls payload (`t_cheats.py`: pause-menu Cheats entry, navigation, the feature toggles, settings, Teleport; `t_fuel.py`: the Jetpack Fuel row (Gall canyon, `local/states/gall_tp5.st`): off by default, off a 4 s jetpack flight drains the tank (Humn +0xBC), on the fuel stays at the game's max (~99) through a 15 s flight with the jetpack still firing (a plain tank lasts ~12 s) and the fuel number's colour in the HUD element table (`0x80111250 + 23*4`) is the game's green off / `0x8080FF80`, the blue Invincibility gives the health, on — the health element keeps its own colour, and so does a ship level's use of that slot (`local/states/ast.st`, checked without the menu by writing `g_fuel_on`); `t_cheat_ship.py [state]`: the Ship row on Skyhook (`local/states/sky.st`): R / L / A step the game's counter `0x800E1B20` with wrap, after resume the Stft draw shows that variant (the model's variant group `+0x14`), This Level resets it to the Outrider and the row reads 0, Reset cheats restores it; on any other state (`play.st`) the row leaves the counter alone; `t_wampa.py cave|trooper|hoth|hoth_off`: the Creature Cam row, Standard preset (s16 `0x800D252C` = 0 written every frame), nothing held: cave (`local/states/echo_cave.st`, Dash's health held at 100): R → Wampa, 10 VIs after resume the creature object `0x800E5EF4` is a `Trop` with `+0x74 & 0xF` == 2, still it 120 VIs later and the camera eye (`*0x800D08A4 + 0x44`) nearer it than Dash (shot); the D-pad drives it: preset 0's slots `+0x08..+0x16` Traditional's within 2 VIs of the take, D-left held 120 VIs turns the wampa (`+0x14`) >= 90° with Dash moving < 0.5, D-up held 120 VIs gives state `+0x78` 2; the stick and B drive it (`cheats_pad`): stick y +60 held 120 VIs gives state 2 on >= 100 frames, stick x +60 held 120 VIs turns it >= 90°, B held 60 VIs gives state 3 on >= 1 frame with no B bit (`0x4000`) in the decoded held word `0x801130AC`, Dash moving < 0.5 over the three; L → Dash clears it at once and the slots are the ones before within 2 VIs; trooper (same state): L → Trooper, a non-wampa `Trop`, held 120 VIs, D-left held 120 VIs turns it >= 30° ("trooper turns"), stick y +60 held 120 VIs gives state 2 on >= 100 frames, B held 60 VIs state 3 on >= 1; A steps to Dash, A to Wampa, Reset cheats back to Dash; hoth (`local/states/lvl0.st`, wave alive count `0x800E1818` zeroed): at VI 30, before the wave, A → AT-ST, preset 0 slots `+0x08..+0x16` are Traditional's D-pad and the mode `0x800DECE0` 1; nothing held: Trak 0's `+0x8C` on the speeder every frame while ATST 0 sleeps (`+0x1C4` 0), on ATST 0 with `+0x98` 55.0 within 2 VIs of its waking and every frame for 300 VIs (shots 60 VIs after the wake, in the opening shot, and 120 VIs after the speeder flies again); D-left 240 VIs (stick centred) turns ATST 0 >= 90° with the speeder view `0x800E1834` unchanged; D-up keeps Trak 0 on ATST 0; the stick and B (`atst_pad`, position `+8`): centre 120 VIs moves < 0.5, y +72 120 VIs >= 25, y +48 240 VIs 30..70 % of y +72 over 240 VIs, y +72 120 VIs then centre: the walk bit set within 110 VIs at the walk clock's time mod 20 5.0 ± 0.5, then < 0.5 over 60 VIs (shot of the stance), x +60 240 VIs turns >= 330° (the game's 2 a frame plus `TURN_EXTRA`) moving < 0.5, the eye behind it (`atst_trak` / `atst_eye`, Dash's swing rule round the head point ATST `+0x50..+0x58` + 55; the camera's eye `+0x44` on the ground): the angle (head point − eye) to the facing <= 45° all through that turn and <= 10° 30 VIs after the stick lets go, <= 10° over the 120 VIs of y +72 before the stance, the eye 128.2 ± 3 from the head point and the view pitch (the camera's forward row `+0x24`) 15 ± 2° down over those and the stand and B phases (B's start included), the feet / head point projected through the camera (fovy `0x80192F14`) at screen y <= 232 / 133..149 standing, walking and with B held (shots standing and firing), `g_atst_trak` moving every game frame (never 3 VIs without), the speeder held while on (>= 900 VIs: within 1.0, health `+0x204` and lives `0x800E0EB0` kept; the stick phases start 800 VIs after the wake since the held speeder does not fly), B 120 VIs: the fire timer `+0x100` rises (a shot) >= 2 times with no B in the held word and the target `+0x16C` 0 on every frame (~4 shots); 120 VIs of stick x -/+60 steering it to 101° right of its heading at the turn's start (toward wave 1's probe droids, behind it there; steered, not timed, so the turn rate does not move it), then Z + B 120 VIs: `+0x16C` non-zero on >= 1 frame, its tag only `PRBT` / `ATST` / `ATAT` (~116 frames, `PRBT`; the head's cos `+0x174` printed at the pick and 30 VIs later, shot there); A → Speeder: the 5 tags at `0x800DED08` the game's again; the walk bit (`+0x108` bit 31) set at the menu and clear within 2 VIs of the resume after Speeder; A → Speeder puts back the slots, the mode 0, Trak 0 on the speeder (shot), the speeder flies >= 20 in 120 VIs; 120 VIs after resume on again by writing `g_atst_on` and the mode, then ATST 0 `+6` |= 0x20 (destroyed): Trak 0 on the speeder within 2 VIs; then `local/states/sky.st`: A on the row records nothing (reads "(none)", shot); hoth_off: the same run and menu trip with the row on Speeder, only the shot 60 VIs after the wake (compared with hoth's: the opening shot looks the same); `t_friendly.py [row|row_off|off|stock]`: the Friendly Wampas row (`local/states/echo_cave.st`, Dash written 8 units on the -x side of the first wampa, nothing held, 600 VIs, wampa `+0x9C`/`+0x78` and Dash's health `+0xB4` per VI): row (`friendly`): up two rows, A on (shot), no health lost and no attack state while the target is `Humn`, then Reset cheats gives `g_friendly_on` 0; row_off (`friendly_off`): A twice (shot, OFF), the wampa attacks and Dash loses health; off / stock: the game unchanged / its three secret-4 sites forced to 1 (the reference numbers); `t_off.py controls|lock|hang|mid`: Cheats toggles (`g_off`) give the game's own behaviour, compared with the unpatched game on the same inputs (the payload's own cost shifts frame times: ~1 unit over 330 frames), and switching off mid-lock / mid-hang lets go; `base` with `OFFS=0,2,6` prints the mean frame dt per setting (the patch's frame cost); `t_orbit.py`: circle strafe radius around a fixed fake target; `t_fog.py`: lock dropped by fog at increasing distances; `t_fogback.py`: no lock on a fogged target behind the camera (`g_test_target`); `t_holdz.py`: Z held after the lock ends keeps the facing and strafes, no gun pitch; `t_hang.py`: ledge grab/climb/let go/shot down/no firing on the crevasse; `t_hang_dirs.py`: catches in 8 directions with and without jumps; `t_hang_more.py`: hang over a floor (let go, land; the troopers near the spot killed), no catch on a low block or with a floor under him (Gall states, Echo Base stairs); `t_hang_gap.py`: clearing the catwalk gap never catches the near edge after landing; `t_hang_cheats.py tp|level`: Cheats Teleport / This Level while hanging end the hang; `t_hang_jetdrop.py`: let go of a Gall hangar ledge, then the jetpack: the let-go fall ends at once and the stick flies him (local/states/gall_tp1.st, Cheats Get all stuff); `t_hang_spots.py`: every catch on three Echo Base states, 24 directions × 2 tilts, checked against the cliff face under the rim; `t_hang_cam.py`: camera side picked while hanging, the game camera's distance, `OFFS` forces angles; `t_switch.py`: lock hand-over after a kill; `t_trainturn.py`: the camera turns with the car through a bend, running toward it shows Dash's face; `t_trainz.py`: Z while Dash faces the camera on the train swings the view to his back and keeps him in it; `t_sight.py`: a held lock drops ~1 s after the target goes out of sight, and no lock through a wall on the camera→Dash line (the camera ray ends on Dash's back); `t_crate.py`: no lock through a stack of Echo Base crates (`Boxx`, echo_cave.st), a target in front of them still locks; `t_ig88.py`: Z locks IG-88 (local/states/om_ig88.st) and the overlay is gone once he dies; `t_ig88near.py`: IG-88 stepped to 3 units in front (his +0x60 turns negative) stays locked; `t_weapons.py`: locked pulse cannon (from 22 units, and a burst from 55, past its own ~30-unit range) and seeker shots hit the AT-ST's cockpit (health `+0x5C4` drops; `NOFIX=1` without the fix; `STATE=` another AT-ST state); `t_lockpitch.py`: Z on a fake high above / below tilts the camera so it is on screen, it levels out after Z; `t_trainwall.py`: on the train a fake 2.5 units behind a car wall found round Dash is not locked, 2 units in front of it is (`g_test_ray`: the last sight rays' hit distance and length); `t_glad.py walk|fly`: Xizor's palace gladiator, walk: his fight started by writing `+0x584` = 3, Z locks him and the laser hurts him; fly: second phase, every Z press locks the flying gladiator, not the troopers below (local/states/xiz_glad.st, xiz_glad2.st); `t_swimlock.py`: under water Z locks the sewer dianoga's eye, not a tentacle, and the locked laser hurts it (local/states/sew_dianoga.st; swimming sets Humn flag 0x400, once read as death); `cycle`: quick Z re-taps step eye → tentacles → eye, a slow press takes the eye; `t_traindroid.py`: Z locks a droid riding the cars (`TTrp`, local/states/om_ttrp.st) and the laser kills it; `t_recenter.py`: standing still eases the camera round behind Dash after ~1.5 s; `t_stairs.py`: camera pitch up and down the Echo Base stairs, `orig` for the unpatched numbers): stick → heading/camera on Echo Base, target lock on Suprosa, Ord Mantell train player (`HumT`) jump trajectory and lock on a fake target |
| `bots/` | `hunt.py` (boots to a level and plays: lock, strafe, fire) and `demo_route.py` (fixed Echo Base route, original vs patch); see the sote-bot skill. Output in `local/run/` |
| `pose/` | Dash's skeleton and poses offline: `dump_hang.py` (RAM dump while he hangs → `local/game/hang.bin`), `ram.py` (reads such a dump), `skel.py` (bone hierarchy, angle convention, forward kinematics), `pose.py` (arm inverse kinematics, stick-figure front/side drawings), `keys.py` + `gen_keys.py` (the ledge-climb keyframes → `climb_keys` in `src/hang.c`), `onehand.py` (the one-hand hang, its sway, catch and climb-start keys → `hang1_keys`, `catch_keys`; multi-start arm IK that keeps blends on one Euler branch), `gen_catch.py`, `newhang.py` (earlier variants). Run with `.venv/bin/python3` |
| `disasm.py` | capstone disassembly by RAM address (ROM boot segment, `local/work/main.bin`, or a RAM dump) |
| `decomp.py`, `ghidra/Decompile.java` | pseudo-C of the function that holds a RAM address (Ghidra headless; same code sources as `disasm.py`); see *Decompiling* |
| `local/work/boot_cheats.py <build>/sote-patch.z64` | the built ROM from power-on, no inject (`_start` loads everything): Echo Base, pause, the Cheats screen. CHECK lines (PASS / FAIL, exit 1): the cheats slot at `0x80540000` equals the build's `cheatscode.bin`, the game paused, the Cheats screen open (`g_cheats_open`); shots of the title, the level, the pause list, the Cheats screen (`SHOTS=`). Guards `_start`'s cheats DMA, which `inject()` runs skip |
| `local/work/cheats_intact.py <build>/sote-patch.z64 [--frames N] <state>...` | per state (no inject): runs N frames (default 120; 300 for the 10-state check), compares the 32 KB cheats slot with `cheatscode.bin` (zeros past it), one line each: words changed. Checks that the game never writes there |
| `local/work/gall_row.sh <build dir> [-j N]` | the sote-test skill's Gall Run row for one build: makes the build's ladder of states once (echo → c05_f8 → peel → end → rail / dash / free, fin_ours, each from the one before), then runs the `--check` runs 4 at a time; logs `local/run/<build>_row_<name>.log`, summary `local/run/<build>_row.txt` (PASS / FAIL each) |
| `steer_probe.py <rom> off\|stock` | probe (no SUITE line): Skyhook's ship steering per 60-VI phase (stick X, released, D-left, stick Y; `PRESET=`), the normal scheme or the " Wolfy" one (`0x8009A398` forced to 1): yaw/pitch/roll and the move along the ship's axes |


### Local files (`local/`)

Everything not published lives in the git-ignored `local/` at the repo root (`harness/paths.py`, env `SOTE_LOCAL`):

| Dir | What |
|---|---|
| `local/rom/` | `Star Wars - Shadows of the Empire (USA) (Rev 2).z64` (the stock ROM), `… [SotE Extended].z64` (the release build, `tools/release.sh`), `ShadowsoftheEmpire.ISO` (the PC version) |
| `local/states/` | savestates (see below) |
| `local/work/` | `main.bin` (the main executable's code part, loaded at `0x80001EC0`; `make_main.py`), `ghidra/` (the decompiler's project), the one-off probes |
| `local/game/` | data made from the ROM: `falcon.bin`, `gall_run.bin`, `gall_level.bin`, `gall_level_stock.bin` (read by `build.py` and `inject.py`), `hang.bin` (`pose/`) |
| `local/build/` | patch builds: `sote-patch/` (`build.py`'s default, what tests inject), other dirs from `--out` |
| `local/run/` | harness outputs: shots, logs, `reg/`, `cfg/`, kept EEPROM dirs, probe states |
| `local/bin/` | `mupen64plus-video-GLideN64.dylib` (built from source, see Setup), `input_script.dylib`, `audio_dump.dylib` (`make`) |
| `local/demo/` | videos |

Outputs go to `local/run/` (shots, logs, kept EEPROM dirs). Each process also gets
`local/run/cfg/<pid>/` (core/plugin config, its EEPROM dir, the temp state), deleted when it exits.
A run empties its own `local/run/shots/<SHOTS>/` first (`SHOTS_KEEP=1` keeps the old PNGs), so shots of
repeated runs no longer pile up; record a take before re-running with the same `SHOTS`.
`make clean` removes what killed runs leave behind; `make clean-shots` deletes every screenshot
(video takes included: compose first).

## Typical loop

```bash
# rebuild the payload (build.py), then
python3 run_all.py                       # whole suite (only on request), ~4 min; PASS/FAIL per test
python3 run_all.py edge "hang_*"          # the feature you work on: names or patterns
M64CPU=0 python3 tests/t_move.py <rom>   # one test, full output (run from harness/)
```

The ROM only boots the core: tests load a savestate and inject `PAYLOAD_BUILD`, so any SotE ROM
works (`run_all.py` defaults to the original).

A test script is: load a state at frame 60, `inject(e)` at 62, drive the pad from 70 on, print
game/payload fields every N frames, take screenshots, then `check()` the expected outcome,
`e.stop()`, and `sys.exit(report())` after `e.run()`. Read numbers first and look at screenshots
for what numbers can't show (camera, overlay, falling off things). A check states what the
docstring promises; when a change moves a number on purpose, update both.

## Savestates

The states are git-ignored (they hold the console's RAM, the game's code with it). The ones the build's assets
come from are made by `bootstrap.py <rom>` (run by `tools/setup.sh`): `play`, `lvl0`, `lvl5`, `om`, `sky`, `ast`,
`gall_tp5`, `gall_6b`, `leebo_turn`, `gall_dash_stand`, `gall_dash_jet`, each from a recipe in its table (a boot into
a carousel level, debug Next Level / Teleport / This Level, a wait, or `states_dash.py`), saved at the game frame
(`0x8018E9B0`) of the state the assets were made from and checked against that state's level id and player place;
`--only a,b`, `--force`. `states_cmp.py` compares states without running them (level, frame, place, and the zones'
vertex bases). `bootstrap.py --tests` (`tools/setup.sh <rom> --tests`) adds the tests' states that need no event
(its `TESTS` table): `echo_catwalk` (debug Teleport point 5 of `play`), `echo_crevasse` (a written place after
that teleport), `echo_gapblock` (a written place from `play`: from Teleport point 5 the narrow block's walks split
on small differences and caught fewer), `echo_cave` (a written place in sub-level 5), `echo_stairs` (Teleport point 4,
arriving ~65 frames before the save: arriving at once and standing ~10 s put a trooper on the top step),
`gall_tp1`, `gall_tp6` (Teleport points 1 / 6), `sup` (a boot), `xiz_glad` (Teleport point 2 of sub-level 27),
`om_ig88` (`om` + Next Level); the tests that use them pass on them. A place written and then held long lets the
level's troopers walk elsewhere than on the state a test was written on: the recipes arrive just before the save.
`sew_428` is not made (Dash swims there; a written place does not enter the swim state). The states made at an
event are in `TESTS` too, each checked also by its event read from the state's RAM (`EVENTS`): `echo_atst`
(Teleport point 5 of sub-level 5, saved at frame 880: the AT-ST past his cutscene, fighting; earlier, `t_boss`'s
strafe takes Dash out of sight), `echo_atst_arms` (`menu` Get all stuff), `om_drones` (`menu` Invincibility on `om`,
then `ride` with no input to frame 1961: Invincibility first, else Dash is knocked off the cars at ~frame 557),
`om_ttrp` (one Teleport from it, saved at frame 2063; a live `TTrp` within 15), `xiz_glad2` (`glad2`: the
gladiator's health written 0, Dash let die so the game respawns him on the maze wall, then Invincibility),
`sew_dianoga` (`dianoga`: Teleport point 3 of sub-level 25 into the pool, sunk to 4 over the eye, swum 18 off,
bit `0x400` written into the five parts: nothing the game does in the harness wakes them). The tests on them pass
(2026-10-29, twice); `off_controls` on the made `play.st` too: max eye diff 0.51 (today's 1.40), 0.000 on both with
the game's fixed dt `0x800E6B10` held at 1/30 (what is left is the patch's frame cost, *Gotchas*).
States no test uses are not made and not listed: `chase`, `echo_atst_dead`, `echo_patched`, `imp_bug1`,
`lvl4`, `lvl7`, `lvl8`, `om_mid`, `om_far`, `sup2_298`. Raw mesh vertices in a state depend on the path the player took
(the zone rebase, `reverse-engineering.md` *Level zones*): `gall_6b` is Next Level alone, no teleport detour.
`local/work/main.bin` comes from `make_main.py`: the main executable's code part only (`0x80001EC0`..`0x800D06E8`,
read from `play.st`); its data part changes in RAM from power-on and is not in the file.

| State | Where | Notes |
|---|---|---|
| `play.st` | Escape from Echo Base, on foot, messages dismissed | movement tests |
| `sup.st` | Imperial Freighter Suprosa, troopers ~12 units away | lock tests (they stand behind a wall: use `g_test_skip_los`) |
| `om.st` | Ord Mantell, first frame with control on the train | `HumT`; RAM holds an older payload, always inject |
| `sew_dianoga.st` | Sewers' dianoga pool, the dianoga woken (`+0x74` bit `0x400` written on its five parts), Invincibility on, Dash swimming 18 units from it | `t_swimlock.py`, `bots/swim.py` |
| `xiz_glad.st` | Xizor's Palace sub-level 27, second debug teleport point (16, −44, 79); the gladiator dormant on the rooftop arena at (−31, 27, 125) | `t_glad.py walk`: write `+0x584` = 3 to start his fight |
| `xiz_glad2.st` | the gladiator's second (flying) phase, Dash just respawned on a maze wall at (31, −34, 123) | `t_glad.py fly` |
| `om_ig88.st` | `om.st` after one debug Next Level: the IG-88 arena (level `0xA`), Dash ~11 units from him | `t_ig88.py`; invincibility doesn't stop his hits there (Game Over): keep Dash's health full with `set_health` |
| `om_ttrp.st` | `om_drones.st` after one debug Teleport: a live train droid (`TTrp`) ~12 units from Dash | `t_traindroid.py`; enable Invincibility (`0x800E1B2C` = 1), the droids shoot |
| `om_drones.st` | Ord Mantell train ~60 s in (frame 1961), debug-menu Invincibility on from the start; drones (`TGun`) arrive within ~5 s | train lock-on (hold Z, fire B: one hit kills a drone, the lock moves on); low obstacles still knock Dash off, and he misses the next train ~25 s later |
| `lvl0.st`, `lvl5.st` | starts of Hoth, Mos Eisley (on the swoop) | |
| `sky.st` | Skyhook (sub-level 30), the Outrider flying, ship counter 0 | `t_cheat_ship.py`; `steer_probe.py`; `t_wampa.py hoth` (the Creature Cam row reads "(none)") |
| `ast.st` | a ship level, the Outrider (`Stft`) flying | `t_fuel.py` (a ship level, its fuel slot used elsewhere) |
| `src_stage1.st`, `src_stage2.st`, `src_base.st`, `src_space.st`, `src_model.st`, `src_portrait.st`, `src_intro.st` | copies `bootstrap.py` saves of the states the Gall Run's assets are made from | the asset tools (`gallrun/gall_asset.py`, `falcon_asset.py`, `level_blob.py`, `gallrun/gall_map.py`) and the Gall Run take load these; `src_base.st`, the base level ~20 s in, the Outrider (`Stft`) flying, for Gall Run checks: a gallrun build's ROM, `g_gallrun` = 1, `inject.gall_level(e, rom)`, then This Level (without `gall_level` the stock level loads and the ship is the Outrider) |
| `gall_tp1.st` | Gall hangar, debug Teleport point 1 (33, 35, 277.5); an upper floor at z 293.5–294 around (18, 13) and (62, 37), 16 above, catwalk edges over this floor | ledge hang over a floor (`t_hang_more.py floor`, Dash's position written there) |
| `gall_tp5.st`, `gall_tp6.st` | Gall canyon paths, debug Teleport points 5 and 6 (62, −150, 228) / (−591, 327, 185); deadly drops ~120 below | ledge hang on rounded rock rims (`t_hang_more.py nofloor`) |
| `gall_6b.st` | Gall 6b, the Boba Fett tower, Slave I parked inside the gantry | Slave I and the shaft for the Gall Run image (`gallrun/slave_pad.py`) |
| `gall_dash_stand.st`, `gall_dash_jet.st` | Gall, Dash standing / firing the jetpack (Cheats → Get all stuff), made by `states_dash.py` (from `gall_tp5.st`) | Dash's two poses for the Gall Run image; dumped with `dump_ram(at=2)`, 2 frames after the load, before the pose moves |
| `echo_atst.st` | Echo Base sub-level 5 arena, AT-ST cutscene over, fight running, debug flag off | boss lock/damage (`t_boss.py`). Made with debug Next Level + Teleport only, saved at frame 880 |
| `echo_atst_arms.st` | `echo_atst.st` after the debug menu's "Get all stuff": every weapon, C-up cycles them (index at Humn `+0xB8`: 0 laser, 1 pulse cannon, 3 seeker) | `t_weapons.py` |
| `echo_catwalk.st` | Echo Base part 1, ice ledge before the girder bridge (136, −106, 2) | |
| `echo_crevasse.st` | far end of that bridge (132, −39, 2); side openings drop into a deadly crevasse (z −125) | edge/fall and ledge-hang tests (`t_edge.py`, `t_hang.py`, `t_hang_dirs.py`, `t_hang_cam.py`) |
| `echo_gapblock.st` | standing on the narrow ice block past the ~4 unit gap from `echo_catwalk.st` (150.8, −94.3, 1.0); the near side is 1 unit higher, the far side drops into the crevasse | ledge hang must not catch a gap he clears (both ways) |
| `echo_cave.st` | Echo Base part 2 corridor (−99, 25, −51) | `t_wampa.py cave`, `trooper` (a wampa ahead; non-wampa `Trop`s in the pool); `t_friendly.py` |
| `echo_stairs.st` | Echo Base part 2, foot of the metal stairs after the lift (263.7, 24.7, −78.3); debug Teleport point 4 of sub-level 5 | camera pitch on slopes (`t_stairs.py`); troopers shoot from above, keep health full |

New ones: `python3 mkstate.py <rom> <level> local/states/<name>.st` (dynarec is fine; ~1 min).
To reach later parts of a level, use the game's debug menu (Next Level / Teleport, see
reverse-engineering.md and `debugmenu.py`): set the cursor before opening the pause screen and
switch the debug flag off right after. Writing Dash's position works on static ground but skips
scripted triggers (cutscenes, boss fights).
Carousel indices are listed in `game.py`.

## Gotchas

- **The Gall Run row's `battle` check can fail on freshly made states.** The peel state is saved at a different VI
  from run to run (the same c05_f8 → peel make: VI 9590 / 9618 on two runs), so the ladder after it differs; once a
  row got the battle's chase 4 against the limit 2, while the row from the next re-made states was 17/17 PASS. A lone
  `battle` FAIL on new states: re-make the ladder from a new peel state before calling it a regression.
- **Game time follows the patch's cost.** The game counts its frame time from the CPU, so with the same frames per
  VI a dearer or cheaper patch changes how much game time a frame is (2026-10-24: ~1.1 % less after a cheaper
  ledge probe; the Gall Run's per-frame code ~20 us a frame). A check counted in VIs (degrees in N frames, a delay
  by frame k, where a jump's climb ends) moves with it: give it a margin over that (or count game time), and when
  one fails with the feature working, compare the builds' game dt before hunting a fault (`orbit`, `recenter`,
  `hang_more` all failed this way).
- **A test that rests on a trooper.** Where the level's troopers stand on a state depends on how and when it was made
  (2026-10-28, the bootstrap-made test states): a test whose path a trooper blocks, pushes or holds passes on one
  state and fails on another. `t_hang_more floor` was pushed to its edge by one (now killed, Dash written where the
  push ended; arriving 400 / 440 / 461 frames later only moved the trooper to the other side), its old canyon jump
  catch was held by one (no angle 180..230 / A frame 25..50 caught without him: the mode went), `t_stairs` had one on
  the top step, `t_hang_spots` lost 5 crevasse catches to two that walked onto its paths during a long hold (waits to
  frame 1900..2040 before the place did not help; arriving by Teleport point 5 did). Kill the troopers near the spot
  (health `+0x60` 0 every frame, `game.pool_objects`) rather than tuning a recipe to put him somewhere.
- **Hangs.** A crash in the patch stops the game rendering and the core never returns: `Emu.run()` has a
  watchdog (`M64HANG` seconds without a frame, default 90 (a state of another level loads in ~30), `0` off) that prints `HANG: no frame for N s after
  frame F` (stdout and stderr) and exits with code 3. Chained runs (`a && b`) stop there; check logs for `HANG`
  instead of waiting. `M64PC=1` (with `M64CPU=0`) adds where the CPU is: 200 PC samples, the GPRs, COP0 (BadVAddr,
  Cause, EPC) and an RDRAM dump `local/run/hang_ram_<pid>.bin`. The core has no debugger, but `DebugGetCPUDataPtr` still points
  at the CPU's fields. A game fault leaves the CPU in the idle loop (`0x80017C5C`); the faulted thread's context is in
  the dump (OSThread +0x11C pc, +0x120 cause, +0x124 badvaddr, the GPRs from +0x20 as 64-bit words). Writing a new payload into a savestate's RAM (`inject()` after `load_state()` of a state
  saved by another build) hung like this: make a fresh state with the new build instead.
- **GLideN64 drops a visible triangle now and then.** In the Gall Run's stage 2 cutting, rock near the camera
  vanished for a frame or two (~2–4 % of frames). The same frame from a savestate (runs are frame-exact at
  the same `RES`) drawn by Rice keeps the wall. The triangles were wholly in front of the camera and faced it;
  `EnableN64DepthCompare` 0/1 and the game's near plane changed nothing. Whether the phone's GLideN64 shows
  it is not known.
- **Data put in RAM before `load_state` is gone**: the state's RAM overwrites it. Put a newer image (the Gall
  Run probes' `IMG=`) after the load.
- **`SHOTS` is relative to `local/run/shots/`** (`SHOTS=s21/story` → `local/run/shots/s21/story/`); `SHOTS=../x` puts them in `local/run/x`.
- **Check the probe's own input first.** A probe that pressed L on frames 0–2 looked like the game switching
  views by itself (Gall Run playtest 2, step 15): before reading a "game does X on its own" result, log the pad
  the probe sent on those frames.
- **Write payload variables with their real size.** The compiler may store a file-local (`static`) flag as one
  byte (the Gall Run's `g_won` was, before the split into `gall_*.c` made it a 4-byte global): `w32` to its symbol
  then writes the neighbours too. Check the size (`llvm-nm -S`) before poking.
- **Long image builds need `M64HANG=0`** (`gall_asset.py`: ~100 s of work after the RAM dumps, the emulator idle).
- **Held radio lines.** A line starting `~h` stops the game till A, B or START: bots and recorders tap A
  through them.
- **`M64CPU=0` whenever you inject.** The dynarec and cached interpreter keep translated code;
  writes through the debugger memory pointer don't invalidate it, so hooks silently don't run.
- **State MD5.** The core refuses (only a level-4 log line, `M64V=1` to see it) to load a state
  saved with a ROM of different MD5, and every rebuild changes the MD5. `Emu.load_state`
  rewrites the MD5 in a temp copy, so any state loads on any build.
- `load_state` applies on the next frame. Inject after it, never in the same callback.
- RDRAM is host-endian 32-bit words. `r16` picks the half; byte access needs the same care.
  RAM dumps from `Emu.dump` are little-endian words (`disasm.py --ram` handles it).
- **Decompiling.** `.venv/bin/python3 decomp.py <addr hex> [--ram dump.bin] [-o out.c] [--fresh]` prints the C of
  the function that holds the address (globals as `DAT_800dd2d0`, no symbols). Needs Ghidra: `brew install ghidra`
  (a formula, not a cask; 12.1.4 used, 2026-10-20) or `$GHIDRA_HOME`. The Ghidra project is cached in
  `local/work/ghidra/`, one per image (`main`; `ram_<md5[:8]>` per dump): the first run imports with auto-analysis
  (~30 s), later runs ~4 s; `--fresh` re-imports. An overlay function auto-analysis did not find (in a dump) is
  created at the address given, so give a dump's function by its entry.
- **Runs that wait forever.** A script waiting for a game-frame count can wait for ever: a held line or the Gall Run's
  end (`finish()`) stops the game's frames while the VIs and the picture go on, so `M64HANG` (no rendered frame) never
  fires (2026-10-23: a 68-frame jump check ran 32 min). Every run now has hard limits: `M64MAXVI` VIs (default 36000)
  stop it, `M64MAXSEC` seconds of wall clock (default 1500) exit with 4 (`LIMIT: …`); 0 turns either off (the Gall Run
  image build: `M64HANG=0 M64MAXSEC=0`).
- Mupen screenshot names have 3 digits: **max 1000 shots per `SHOTS` directory**; anything
  past that is lost. Split long recordings across directories.
- GLideN64 writes its settings back into the config. The config dir is per process now, so
  nothing leaks between runs; still set every option a run depends on (`GLN_INT`/`GLN_STR`):
  anything else is the plugin default.
- Runs are not bit-exact: the same test on the same state differs by ~0.1 in a few numbers and
  occasionally more (the stairs descent pitch: -18.8, -22.2, -24.4 on three runs). Checks
  leave margin for that; compare trends, not last digits.
- Piping a long run through `grep` buffers output; if the run is killed by a timeout you get
  nothing. Write to a file and read it. Background shells may be killed silently: check that
  the process is still alive before waiting on it.
- A fresh EEPROM dir per run (default, inside `local/run/cfg/<pid>/`) keeps the menu flow identical for
  `boot_events`. Reusing saves (`SAVES=<name>`) changes the menus.
- Don't put fake objects into the game's target pool (`0x80112838`): the game updates those
  objects itself and freezes. For synthetic lock tests write `g_lock` directly.
- Train riders: world position `+0x50` is recomputed from the car every frame. Teleporting needs
  all copies (`+0x08 +0x50 +0x14C +0x18C +0x204 +0x244`) and the rider still loses the car and
  falls. Hazards (low beams) kill Dash on the train regardless of health writes.
- Several emulators at once are fine: runs share no config or temp files and each takes one
  core (8 on this Mac). `run_all.py -j 4` (the default) runs the suite 4 at a time, longest
  first: 245 s instead of 918 s one by one, the same per-test times and results. Each run needs
  its own `SHOTS` dir (two with the same one mix their screenshots; `run_all` gives each test
  `reg_<name>`). A test hanging past `--timeout` (600 s) is killed and fails. In parallel a long test sometimes goes
  bad halfway (garbage reads, no catches; cause not found: not shared files, not the state load
  racing `inject`), so `run_all` reruns the failures one at a time and lists those that pass alone
  as "failed only in parallel". Don't leave runs
  behind: a forgotten emulator kept a core at 100% for 6 hours. Two sessions working
  at once also share `local/build/sote-patch/`. When one rebuilds while the other's tests run,
  `syms()` (payload.elf) and the injected payload.bin come from different builds and tests read
  zeros (`hang_spots`, `hang_cheat_lvl`). Test your own build with `build.py -o <dir>` and
  `PAYLOAD_BUILD=<dir>` (the Gall Run's assets, `falcon.bin`, `gall_run.bin`, `gall_level.bin`, come from `local/game/` for every build).
