---
name: sote-test
description: Run the SotE controls patch's harness tests for the feature being worked on and report PASS/FAIL. Use after a change to sote-patch/src (pass the changed module or test names as args), or when the user asks to run tests ("run the tests", "run tests", "all tests").
model: haiku
effort: low
allowed-tools: Bash(python3 harness/run_all.py*), Bash(cd sote-patch && python3 build.py*), Read
---

Args: changed modules (`hang.c`, `lock.c`, ...), test names/patterns (`hang_*`), or `all`.

1. Pick the tests (the user's rule: only the feature's tests; the whole suite only when the user
   asked for it in so many words, e.g. "all tests" / "the whole suite" — never by default, never
   before a release):

   | changed | tests |
   |---|---|
   | `hang.c` | `edge` `stairs` `"hang_*"` `off_hang` `off_mid` |
   | `lock.c` | `lock` `crate` `orbit` `fog` `fogback` `holdz` `switch` `boss` `ig88` `ig88near` `weapons` `sight` `lockpitch` `trainwall` `glad` `glad_fly` `swimlock` `swimcycle` |
   | `core.c` | `move` `orbit` `recenter` `stairs` `stairs_orig` `holdz` `edge` `swimlock` `off_controls` `off_lock` `off_mid` |
   | `train.c` | `train_jump` `train_lock` `trainturn` `trainz` `traindroid` |
   | `cheats.c` | `cheats` `fuel` `leebo` `ship` `ship_other` `wampa_cave` `wampa_trooper` `wampa_hoth` `wampa_hoth_off` `friendly` `friendly_off` `hang_cheat_tp` `hang_cheat_lvl` `off_mid`; when the build layout, `_start` or `link.ld` changed: `M64CPU=2 .venv/bin/python3 ../local/work/boot_cheats.py <build>/sote-patch.z64` (the built ROM from power-on, no inject; CHECK lines) |
   | `gallrun.c`, `gall_*.c`, `falcon.c`, Gall Run assets | the `--check` runs of `harness/gallrun/` tools, run from `harness/` (each listed here: tool, knob, start state): `peel_check.py <rom> --check` from `../local/run/<build>_peel.st` (stage 1's Outrider break-off; also `--side 150`, `--side -150`), `peel_check.py <rom> --make ../local/run/<build>_c05_f8.st --lines --check` (stage 1's radio lines: the `~h` ones held, the others not, `or_pt` 0 on "Sorry!" (said before the break-off), no hit tint under a hold, "Missiles: n" hidden), `hang_hit.py <rom> --clear --check` from `../local/run/<build>_end.st` (the end scene's first held line: the TIEs fly off under it, no target panel, no missile count), `falcon_look.py <rom> --check ../local/run/<build>_c05_f3.st ../local/run/<build>_fin_ours.st ../local/run/<build>_peel.st ../local/run/<build>_free.st` (falcon.bin unlit in Cut 05 and the last scene, lit in the mission), `hang_hit.py <rom> --from ../local/run/<build>_free.st --battle --check` (the final battle's TIEs near the Falcon), `hang_hit.py <rom> --from ../local/run/<build>_free.st --stick 80 --check` and `--stick 0 --check` (the free flight's first start: the stick free from the first frame, the turn over by `START_MAX`), `hang_hit.py <rom> --from ../local/run/<build>_dash.st --cam --frames 600 --check` (Slave I's shot eased in from the view on screen; Lando's "Dash, you coward!" said once as the gunner's view comes back after Dash's jump), `hang_hit.py <rom> --from ../local/run/<build>_rail.st --view 4 --window --frames 1600 --check` (no turret window over Dash's shot from the inside view), `hang_hit.py <rom> --from ../local/run/<build>_free.st --fade --fade-luke --frames 600 --check` (no hit tint frozen under a held line), `hang_hit.py <rom> --from ../local/run/<build>_free.st --save-at jump --hull --check` (the fly-away over the hull, Lando's line not held; use a scratch build dir name: it saves `../local/run/<build>_jump.st`), `hang_hit.py <rom> --from ../local/run/<build>_jump.st --trail --frames 120 --check` (the Falcon's jump: its trail drawn on >= 90 % of the jump's frames, the Falcon on screen every frame till the flash; `../local/run/<build>_jump.st` from the `--hull` run above), `STATE=../local/run/<build>_free.st respawn_probe.py <rom> --timers --check` (the death: ~3 s to the respawn, the explosion seen), `STATE=../local/run/<build>_free.st RAM_N=5 respawn_probe.py <rom> --ram --check` (a tower's ram damage, the 4th head-on ram downs it), `fin_check.py <rom> --from ours --falcon --check` (the last scene's camera kept out of the Falcon); all `M64CPU=2` |
   | `hooks.S`, `common.h`, `game.h`, `build.py` | ask whether to run the whole suite |

2. If `sote-patch/src` changed since the last build, build first:
   `cd sote-patch && python3 build.py "../local/rom/Star Wars - Shadows of the Empire (USA) (Rev 2).z64"`
   (tests inject `local/build/sote-patch/payload.bin`; don't build while tests run).

3. One Bash call from the repo root, timeout 1200000:
   `python3 harness/run_all.py --rom local/build/sote-patch/sote-patch.z64 <tests>`
   (runs 4 at a time; quote patterns: `"hang_*"`).

4. Reply in Ukrainian, short: which tests ran, `N/M passed`, wall time. For each FAIL: the test,
   its `- ...` check lines from the output, and the log path `local/run/reg/<name>.log`. Don't
   read the logs or the code, don't try to fix anything: the caller does that.
