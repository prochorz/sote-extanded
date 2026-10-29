# n64

- `sote-patch/` — controls patch (camera-relative movement, Z lock-on) for Star Wars: Shadows of the Empire (USA Rev 2). See `sote-patch/README.md`.
- Skills (`.claude/skills/`): `sote-bot` (scripted play, debug-menu teleports, savestates, bots) and
  `sote-video` (recording takes, audio, composing showcase videos), `sote-release` (fresh ROM),
  `sote-test` (runs the touched feature's tests; haiku, low effort), `level-map` (draws and sends any level's map, `harness/gallrun/level_map.py`; the Gall Run mission map is `gall_map.py`; sonnet, low effort), `commit` (splits uncommitted changes
  into per-feature commits), `plan` (decision-complete implementation plan before any multi-module change, new hook, feature, test or asset; audits `plans/` plans). Video tools in `tools/video/`.
- `docs/` — game-level knowledge, independent of any one patch:
  - `docs/reverse-engineering.md` — memory layout, running custom code in the game, known hook points,
    player classes (`Humn` / `HumT`) and their fields, game structures, how to find new addresses.
  - `docs/harness.md` + `harness/` — scripted mupen64plus test bench (savestates, payload injection,
    example tests, disassembler). Verify every code change there.
- `local/docs/` (git-ignored: local only, never in the public repo; the Gall Run's own docs, read here in the user's
  sessions; public files never point at them and never name what the mission is built from):
  - `local/docs/gall-run.md` — Gall Run bonus mission (in the release since 2026-10-24, the user): design, the mission
    start to end, run time, the camera, design history and dead ends, open work. Its game facts are in
    `local/docs/gall-facts.md` and `docs/reverse-engineering.md`, its image pipeline and tools in `local/docs/gallrun-tools.md`.
  - `local/docs/gall-chain.md` — the Gall Run in the story: Cut 05 reworked (lines, ships, Luke's picture),
    the end by the towers and the Falcon's jump, the last scene's hyperspace part (the Falcon, Leia's lines, Lando and
    Leia's picture), then Cut 06 (`gall_chain.c`).
  - `local/docs/own-level.md` — the mission as a sub-level of its own (id 32, the game's tables grown to 33 entries).
  - `local/docs/cut05-frames.md` — Cut 05 as seven fixed frames (pictures with the button after 8 s, the scene's
    flight and space shots entered by writing its objects back: `harness/gallrun/c05_state.py` → `gall_c05.h`).
  - `local/docs/decisions.md` — frozen archive of the plans closed before 2026-10-24 (why, the numbers
    measured, what was refuted), a `### <plan name>` each; the bare `Dn` ids left in older code comments are its entries.
    Nothing new goes there.
- `plans/` (git-ignored) — working files: the current plans and the playtest intake list (`plans/intake.md`, only what no plan has taken). A closed plan is folded
  (its checks into the harness, its reasons into code comments, its dead ends into the feature doc) and deleted
  (skill `implementation-planner`, *Closing a plan*).
- Patch code: `sote-patch/src/` modules `core.c`, `lock.c` (lock-on + its overlay) + optional features
  `hang.c`, `train.c`, `cheats.c` (pause-menu Cheats screen = the game's debug list, + a Leebo Scanner
  toggle: secret #1, the top-down view, switched straight on/off, + a Jetpack Fuel toggle: off by
  default, refills the on-foot player's fuel `+0xBC` every frame and draws the fuel number blue,
  like Invincibility does the health, + a Ship row: Skyhook's ship, Outrider / X-Wing / TIE Fighter, the game's secret #2, + a Creature
  Cam row: what the profile name " Wampa  Stompa" gives, picked from the row in any preset: on foot Dash / Wampa /
  Trooper (the camera follows a creature), on Hoth Speeder / AT-ST (the first AT-ST on the D-pad), + a Friendly Wampas row: the game's secret #4
  (a wampa that targets Dash calms down; the game gives it only for Jedi), its three checks answered yes; Reset cheats is the last row);
  - the Gall Run: `gallrun.c` (+ `gall_scene.c`, `gall_fly.c`, `gall_story.c`, `gall_gun.c`, `gall_space.c`, `gall_native.c`, `gall_ties.c`, `gall_cam.c`, `gall_chain.c` (the story chain; `gall_final.h` made by `harness/gallrun/final_state.py`), internal header `gall.h`) + `falcon.c` (default features, in the release since 2026-10-24, the user; left out only by `build.py --without gallrun`, which drops `falcon` too; Cheats: Go to level 32, the Gall Run bonus mission; the Millennium Falcon model `local/game/falcon.bin`, made from the ship-model source's RAM by `harness/falcon_asset.py`, appended to the ROM after the payload and the cheats slot and copied to `0x80500000` by `_start`, is the player ship in the mission's level data; `falcon.c` (built with it) places its guns and engine glow:
  the base level rebuilt as the Falcon's canyon run — stage 1 a canyon (the player flies the Falcon in the canyon's corridor after Dash; TIEs come in at the end, Dash leaves), stage 2 open
  terrain (player shoots), an opening shot, radio lines; image `local/game/gall_run.bin` from `harness/gallrun/gall_asset.py`
  at `0x80628000`, the mission's own code (`gallrun.c`, `gall_*.c`) at `0x80600040` outside the payload; the mission's level: the base level's sub-level blob
  `local/game/gall_level.bin` (`harness/level_blob.py` → `gall_level_stock.bin`, changed by `harness/gallrun/level_edit.py`), played as a sub-level of its own, id 32 (`LEVEL_GALL`; the game's sub-level tables moved to 33 entries in `gallrun.c`, the base level's own id never touched: `local/docs/own-level.md`); see `local/docs/gall-run.md`)
  (`build.py --without hang|train|cheats`; see the README's code section). Payload limit is 64 KB
  (`PAYLOAD_SPACE`, code + data; `.bss` is NOLOAD after it, zeroed by `_start` and by `inject()`); `cheats.c` is not in it: its code and data are a section of their own (`.cheats`, `link.ld`) at `0x80540000`, in a fixed 32 KB ROM slot right after the payload's 64 KB (`CHEATS_SPACE`, zeros `--without cheats`), loaded by `_start` and copied by `inject()`; its `.bss` stays in the payload's. It is still built with `-Oz` and calls the game through absolute symbols (`GAME()` in it).
- `sote-patch/docs/ledge-falls.md` — ledge guard (rolled back) and ledge hang (current): design, tuning, tests.
- Build: `cd sote-patch && python3 build.py "../local/rom/Star Wars - Shadows of the Empire (USA) (Rev 2).z64"`.
  Release builds add `--md5-prefix 7DC1ECE7`: the ROM's MD5 then keeps starting with those digits, so
  the user's save (`Shadow of the Empire-7DC1ECE7.eep`) survives updates. Copy `local/build/sote-patch/sote-patch.z64`
  to `local/rom/... [SotE Extended].z64`. `tools/release.sh` does all of that in one step
  (skill `sote-release`: build + send the ROM). A fresh clone (no game data in git) first runs
  `tools/setup.sh <your rom.z64>`: the ROM into `local/rom/`, the harness dylibs, the build's savestates
  (`harness/bootstrap.py`), `local/work/main.bin` (`harness/make_main.py`) and the assets in `local/game/`, each
  skipped when present; `SOTE_LOCAL` moves `local/` (setup, `release.sh`, the harness). Made from scratch, the
  release differs from the shipped one only in `gall_run.bin`: Dash's two pose blocks (`harness/states_dash.py`), the
  gun towers' turn (39 bytes) and a 2-byte header pair in each of the 11 face sprites; the Gall Run checks and
  shots are the same (2026-10-28).
- Git (`main`): code, docs, our own assets (pictures, portraits, sounds, routes). Everything local lives in the
  git-ignored `local/` (`harness/paths.py`; env `SOTE_LOCAL` moves it): `rom/` (the stock ROM, the `[SotE Extended]`
  ROM, the PC ISO), `states/` (savestates), `work/` (`main.bin`, one-off probes), `game/` (assets made from the ROM:
  `falcon.bin`, `gall_run.bin`, `gall_level*.bin`, `hang.bin`), `build/` (`sote-patch/` the default build, other
  `--out` dirs), `run/` (harness outputs), `bin/` (GLideN64, our dylibs), `demo/` (videos). Also ignored: `plans/`,
  `.venv`, `.deepcode/` (`.gitignore`).
- Harness musts: `M64CPU=0` when injecting; parallel runs OK (own `SHOTS` dir each, no rebuild while
  they run; `run_all.py -j 4` is the default); write long runs to a file instead
  of piping through grep; set every GLideN64 option a run depends on.
- Tests (user's rule): while working on a feature run only that feature's tests (skill `sote-test`:
  module → tests table; `harness/run_all.py <names>`, e.g. `hang_*` + `edge` for `hang.c`; PASS/FAIL per test, logs in
  `local/run/reg/`). The whole suite only when the user asks for it — not before a release.
- User plays on Android M64Plus FZ. Chat in Ukrainian; anything meant for sharing (videos, captions) in English. All `.md` files are written in English only.
- User's standing rules (kept here, not in an outside memory):
  - "Remember this" means: write it into the owning doc in this repo (this file, `docs/…`, a README, a module's header comment; the
    Gall Run's own docs: `local/docs/…`) and say which file.
  - No names from other games anywhere in the project (file and function names, docs, comments, captions): describe a feature by what it does.
  - Never delete the SotE Extended showcase video (`local/demo/sote_showcase_*.mp4`) or its takes (`local/run/shots/vid_*`,
    `local/run/video/`); how it was made: skill `sote-video`, *The SotE Extended showcase* (the user, 2026-10-28).
  - Anything shared (videos, captions, descriptions, posts, thumbnails) and every tracked file never says what the Gall
    Run is built from: the levels it takes from are named by role ("stage 1's source", "stage 2's source", "the base
    level", "the space level", "the ship-model source", "the portrait source"), their names only in `local/docs/`;
    stages are "the canyon run" and "the gunner" (the user, 2026-10-28, 2026-10-29). No other projects either (one
    thanks line in `sote-patch/README.md`). `tools/public_check.py` checks the tracked files: run it before a push.
  - No videos unless asked, and then ask first what goes in them; a yes covers that one video (re-recording needs asking again). Verify with harness numbers and screenshots.
  - Reuse the game's own mechanisms before inventing new ones ("не вигадувати нове, а забрати те що є"). Do not
    re-implement logic the game already has (its line holds, the arrow, A/B, timers, START skips, movement, AI):
    drive the game's own functions and states and hook into its events; code of ours only adds what the game lacks.
    Own counters, input eating or a parallel state machine beside the game's is a last resort, named in the plan with
    why the game's own cannot do it (the user, 2026-10-20: Cut 05's own 8 s counter and A/B eating fought the game's
    hold on the phone).
  - Before a harness research or execution run (a subagent, a long probe), name the steps and the estimated token cost and wait for the go (skill `implementation-planner`).
  - "Імплементація" (implementation) means the skill `implementation-planner`: write the plan only, no code, until the user approves the plan and says go for named steps.
  - Before doing anything that changes the project (a fix, a feature, a tweak, even a small one proposed in chat), first run the skill `implementation-planner` for it and wait for the plan's approval and the go; a "так" to a proposal in chat is not a go to skip the plan (the user, 2026-10-19).
  - Approvals and choices are asked with the question window (`AskUserQuestion`: options, the recommended one first),
    not as a question at the end of a text reply: a plan's approval and the go for its steps (with the token cost in the
    option), a choice between fixes, a design question (the user, 2026-10-20).
  - The planner rule above is for the game's code and data (the patch, the mission, assets, the level blob). Tooling
    (the harness, its scripts, agents, skills, project config) is changed directly, without a plan (the user,
    2026-10-20: "це ж не код гри а харнес").
  - An approved plan is executed by a subagent with a clean context (Claude cannot run `/compact` itself): it gets only
    the plan file in `plans/`, the step numbers and the go, and reports back briefly; the main
    session relays the result (the user, 2026-10-19). The subagent is `.claude/agents/plan-executor.md`.
- `local/rom/ShadowsoftheEmpire.ISO` — **PC version** of SotE (1997, DirectX). UDF disc; mount with
  `hdiutil attach -readonly -nobrowse -mountpoint <dir> local/rom/ShadowsoftheEmpire.ISO` (bsdtar only sees the ISO9660 stub README).

## PC ISO — what it's useful for (ranked)

1. **Reverse-engineering reference (most valuable).** Same engine as N64. `SOTE.EXE` (launcher) and
   `SDATA/SHADOWS.EXE` (game, PE32 x86, ~35k strings: camera modes `Camera Forward/Back`, `Exterior Camera`,
   `Drop Camera`, `Seeker Camera`, `View Lock ON`, ASSERTs, menu text, sound names). Load in Ghidra to locate
   camera / targeting / Dash movement logic and map it onto N64 functions.
   `SDATA/DATA12–27.DLL` are per-level DLLs with code (level logic, AI, bosses), not plain asset archives.
2. **Voice acting** (N64 dialogue is text-only): `ILB*.WAV` (Leebo, 16-bit 22 kHz), `ILU*.WAV` (likely Luke),
   `IR1xx/2xx/3xx.WAV` (radio chatter, 8-bit 11 kHz). Adding to N64 needs ROM expansion (12 → 32/64 MB),
   VADPCM conversion, and a hook on dialogue display — big project.
3. **SFX** — some WAVs higher quality than N64 samples; replacing in the ROM sound bank is low value / high effort.
4. **FMV `.SAN`** (SMUSH, ~350 MB total) — not feasible for N64 (size, no video player).
5. **Textures** — inside the level DLLs, byte-identical to the N64 ones (verified). No HD source (the shelved HD pack is kept outside this repository).
