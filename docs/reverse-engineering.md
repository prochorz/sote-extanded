# SotE (USA Rev 2): reverse engineering and code injection

What we know about the game's code, how to run our own code inside it, and where to hook.

## ROM and memory layout

- ROM: `local/rom/Star Wars - Shadows of the Empire (USA) (Rev 2).z64`, big-endian, 12 MB,
  SHA-256 `e7085e013123537f34e0edec8801318016da4dbac424172d6dc5f3b67d98642c`, CIC 6102.
- `0x80000400–0x80001EC0` boot segment, stored uncompressed at ROM `0x1000`.
- `0x80001EC0…` main executable, **compressed** in ROM. Decompressed copy: `harness/make_main.py` (the code part
  read from a savestate's RAM) → `local/work/main.bin`. Level code/data are loaded at runtime; use a RAM dump for those.
- Expansion Pak RAM (`0x80400000–0x80800000`) is unused by the game where we put the payload
  (`0x807C0000`). Fake objects for tests went to `0x807E0000`. The patch's other parts there: the Falcon model
  `0x80500000` (~122 KB), `cheats.c`'s code and data `0x80540000` (`.cheats`, 32 KB slot), the Look row's guard
  image `0x80548000` (`guard.bin`, up to `0x80580000`), the Guri image `0x80580000` (`guri.bin`, up to `0x80600000`;
  the game left `0x80548000–0x80600000` untouched on `play.st` and `palace.st` through a level load, 2026-11-06), the
  melee image `0x805A0000` (`melee.bin`), `saber.c`'s code and data `0x805C0000` (`.saber`, 32 KB slot) and its
  `.bss` `0x805C8000` (`.saber_bss`, up to `0x80600000`), the Gall Run's code `0x80600040` and its image `0x80628000`.
  The payload's `.bss` follows its code from `0x807C0000` and must end before `0x807E0000`.
- ROM after the retail 12 MB: the payload at `0xC00000` (64 KB, fixed DMA), the cheats slot `0xC10000` (32 KB,
  always there, zeros `--without cheats`; with nothing after it, its last 8 bytes are the MD5 nonce), then the
  Falcon model, the Gall Run's code + image and its level blob, then the guard, Guri and melee images, the duel's
  level, the saber's sounds and the saber slot (32 KB, `.saber`, the ROM's last blob, none `--without saber`; the
  nonce after it).
- The cheats slot `0x80540000–0x80548000` stays untouched by the game: compared word for word with the build's
  `cheatscode.bin` after 300 frames on each of 10 states (`echo` .. `fin_ours`), 0 words
  changed (`local/work/cheats_intact.py`).

## Running custom code in the game

1. The compressed main code can't be edited in ROM, so nothing in it is patched statically.
2. 15 free words (nops) at RAM `0x80000414` (ROM `0x1014`) become a boot stub: PI DMA of the
   payload from ROM `0xC00000` (appended after the retail image) to `0x807C0000`, wait, jump.
3. The boot call `jal 0x80017B60` (game main) at ROM `0x1F14` is redirected to the stub.
   The payload's `_start` zeroes its `.bss` (NOLOAD, right after code + data in RAM, not in the
   ROM image), writes the hook table into the now-decompressed code, flushes caches,
   and jumps to `0x80017B60`.
4. Recompute the CIC 6102 CRC; ship a BPS patch.

Hooks are `(address, instruction)` pairs in a `hook_table` in `.data`, mostly `jal` to a
trampoline that saves the o32 caller-saved set, HI/LO, FPU `f0–f18` (FR=0 pairs) and FCSR,
calls C, restores, and re-executes what the hook overwrote.

Toolchain that works: clang `--target=mips-elf -mabi=32 -mfp32 -mno-odd-spreg -G0`, C as `-march=mips2`
(clang's o32 mips3 C backend crashes), assembly as mips3 (cache ops), `ld.lld` with a linker script placing everything at `0x807C0000`.
`-mno-odd-spreg` is required: the game runs the FPU with FR=0, odd singles don't exist.

## Known hook points

All verified in a working payload (the on-foot controls patch).

| Address | In | Purpose |
|---|---|---|
| `0x800758A8` (`j` + nop at `…AC`) | Humn control `0x80074FA4`, after stick decode | rewrite movement intent / lock-on steering; entered by `j` and left by `j 0x800758B0` because the game keeps a button flag in `ra` across it (*Dash's motion and animation*) |
| `0x800778D0`, `0x800785A8` | Humn, before yaw-rate integration (ground / air) | override turning |
| `0x8006282C`, `0x80062AFC`, `0x80062C8C` | Doly camera modes | change what the follow camera sees (yaw in the player matrix copy) |
| `0x800321FC` | laser bolt creation | redirect shots (dir at bolt `+0xA0`) |
| `0x800BB864` | scene display list close (after HUD) | draw own overlay (fill rects, triangles as rows) |
| `0x800AAFC0` (+nop), `0x800AC9E0` | HumT control `0x800AAADC` | same as the first two, train variant (the hook replaces `lui at,0x800E; lwc1 f10,0x539C(at)`, re-execute it) |
| `0x8007A104` (`jal`) | Humn control, last instruction before the epilogue reloads `ra` | override anything for this frame after the game's physics/heading (re-execute `lw ra, 0x3C(sp)`, continue at `0x8007A10C`) |
| `0x800175B8` (`j` + nop) | `set_anim` entry, shared by every object | swap the requested animation / controller (run `addiu sp,-0x28; sw ra,0x24(sp)` in the trampoline, continue at `0x800175C0`) |
| `0x800153D4` (`jal 0x80026124`) | input function `0x800132AC`, start of the paused branch | pause-menu input before the game's (call the original, it returns the paused flag). Not reached while the debug flag is set |
| `0x80024854` (`jal 0x8001FC90`) | pause screen draw, `a0` = text context (delay slot) | draw on the pause screen after the game |
| `0x80009138` (`j`) | HUD text element colour setter, shared by every HUD: `a0` id, `a1`/`a2`/`a3` r/g/b, alpha on the caller's stack at `+0x10` | recolour a HUD number: the Jetpack Fuel cheat paints the fuel percentage the blue Invincibility gives the health (re-execute `sll t6, a0, 0x10`, continue at `0x8000913C`) |
| `0x8001311C` (`jal 0x800C04D4`, delay slot sets `a0`) | pad update, the raw controller read | take the stick and buttons before the game decodes them (the trampoline runs the read, then `gallrun_pad` (Gall Run) and `cheats_pad` (Creature Cam: the stick and B written as the followed creature's D-pad, the stick, A and B cleared)) |
| `0x80009648` (`j`) | entry of the camera switch `0x80009648(entry)` (firing in a gunner stage switches to the gun's entry 5) | refuse a switch (Gall Run free flight); re-execute `lui a1, 0x800D` / `addiu a1, a1, 0x08A8`, continue at `0x80009650` |
| `0x80099AC8` (`jal`) + nop at `…ACC` | Stft per-frame script, the view keys' `lw t5, 0x2400(t5)` / `bnez t5, 0x80099C18` | open the view keys that need a sector record without one (Gall Run native flight, `g_sky_on`): the trampoline loads `t5` and jumps to `0x80099C18` when it or the flag is nonzero, else returns to `0x80099AD0` (a branch can't sit in a `jal`'s delay slot) |
| `0x8009BF3C` (`jal`) | Stft guns gate, `lw t6, 0x2400(t6)` before `beqz t6, 0x8009C024` (delay slot `0x8009BF40` kept) | open the ship's own guns and missiles without the record (Gall Run native flight): `t6` = the record, or 1 with `g_sky_on`; back at `0x8009BF44` |
| `0x800B1DB4` (`j`) | enemy shot `0x800B1560`, `lh v0, LEVEL_ID` before the damage scale by level (delay slot `0x800B1DB8` `lui t0, 0x8011` kept) | read another id for the scale (Gall Run: 32 as 6, `tramp_dmg_level`); re-execute the `lh`, continue at `0x800B1DBC` |
| `0x800B0680`, `0x800B2B90`, `0x800B3374` (`jal 0x800359F0`, delay slot `a0 = 4` kept) | the wampa code's secret-4 checks (see Game Secrets) | answer secret 4 (friendly wampas) without the Jedi-beaten profile: the Cheats row Friendly Wampas, `cheats_secret4` returns the game's answer OR the row; a plain C call (the sites treat t-registers as clobbered) |
| `0x8009C790`, `0x8009C3F0`, `0x8009C5F8` (`jal 0x8000FE48`) | Stft draw method `0x8009C318`: the matrix copies into the gun nodes, the model root and the engine-glow node | move a node after the game built it (the Falcon's guns, its glow, the drawn ship's offset) |
| `0x8007A134` (`jal 0x8000FE48`, delay slot `0x8007A138` `addiu a1, s0, 0x208` kept) | Humn draw method `0x8007A118` (`s0` the Humn): the copy of his matrix `+0x208` into his placement node `+0x24C`; after it the method reloads all it uses (only `s` and even `f20+` registers live) | move the drawn on-foot figure after the game built it: the Look's drop (`guard.c` `guard_place`, `hooks.S` `tramp_look_place`: node `+0x40` lowered, a write there holds for the draw) |
| `0x800B1EB4` (`jal 0x80031FE0`, delay slot `sw t8, 0x1C(sp)` kept) | the Trop's shot function `0x800B1560`: its one bolt spawn, a0 the direction matrix (its `+0x30` the muzzle), a1 the place, a2 the sector, the owner Trop the 9th argument at `sp + 0x20`; after it nothing caller-saved is read | take one Trop's fire with the game's own cadence, aim, line of sight and side-step kept (the duel: Guri's bolts become Stunner rings / her Disruptor, `tramp_trop_fire`; any other owner, any other level: the game's spawn) |
| `0x800B59E8` (`lw v0, 0x78(s0)`; `0x800B59EC` `addiu at, zero, 5`, no branch target) | the Trop messages method's `'shot'` case, its test for state 5 / 6 / 7 (exit `0x800B62A8`), before the line test and the damage; s0 the receiving Trop | make one Trop take no shot at all (no damage, no stagger, no death) by jumping to the exit (the duel: Guri while shut, `tramp_trop_shut`; scratch `at` only) |
| `0x8007AE70` (`jal 0x800732D4`, delay slot `a3 = 1` kept) | Humn's message handler `0x8007A29C`, case `'shot'`: a0 the Humn, a1 the amount, the message at the caller's `sp + 0x1D4` (`+4` sender, `+8` flags); nothing in t / f0..f19 kept across it, its return unused | act on a hit after the game's damage (the duel: Guri's hit tint blue, `tramp_duel_dmg` → `duel_hit`) |

A hook that replaces a *function entry* takes `j`, not `jal`: `jal` would set `ra` to the
instruction after the hook, and the function's own `jr ra` would then re-enter the trampoline —
the game hangs the first time it calls it. A `jal` hook inside a function is safe only where the game
does not read `ra` before its own next `jal`: the Humn control keeps a flag in it across `0x800758A8`
(a `jal` there changed the follow camera's swing in every build until 2026-10-29).

Without a code patch: a class record's method pointers (table `0x80112808`, `+0x1C` update, `+0x20` draw)
can be swapped for a wrapper that runs the game's method and then writes over its result. The Gall Run does
it for `Trak` and `TieF` while it runs and puts the game's pointers back after. `harness/inject.py`
`all_hooks()` does not know these swaps: whoever makes one puts it back.

## Player classes

Objects start with a 4-char class tag. Class method table at `0x80112B08…`; per-class records
hold method pointers (search the table for a known function address to find a class).

| | `Humn` (on foot) | `HumT` (Ord Mantell train) |
|---|---|---|
| control function | `0x80074FA4` | `0x800AAADC` (class record `0x80112F88`) |
| yaw (deg, facing = yaw + 90) | `+0x8C` (written back from `+0x14` each frame: write both) | `+0x90` |
| yaw rate (deg/s) | `+0xA4` | `+0xA8`, game clamps ±160 |
| world position | `+0x50` | `+0x50` (recomputed from the car each frame) |
| matrix copy | `+0x108` | `+0x11C` |
| flags `+0x74` | `0x400` swimming (no flag on death: health 0) | `0x400` **airborne**, `0x08000000` fallen off |
| health | float `+0xB4` | float `+0xC0` |
| decoded-intent stack slots | `sp+0x15C…0x17E` | same + `0x40` |
| strafe curve constant | `0x800EB9E8` | `0x800ED044` |
| input frozen while | `0x800E0EA0 > 0` or `0x800DEB78 > 0` | `0x800E539C > 0` (death/respawn), `0x800E5838 != 0`, `0x800E57B8 > 0` (~3.3 s level-start freeze) |

Decoded intent (Humn offsets): forward `0x17E`, back `0x17C`, turn `0x17A/0x178`, strafe L/R
`0x172/0x170` (s16 flags), turn magnitude `0x160`, forward magnitude `0x15C` (floats). Rewriting these right after the game fills them
changes movement while keeping all native physics.

How the decoded forward magnitude becomes his ground speed (2026-11-12, `local/work/duel/stun/`, `duel_wl1.st`): no speed
field and no speed constant. Each update on the ground (`0x80077BC4..0x80077E58`) his velocity `+0x98/+0x9C` is
multiplied by the grip `0x800E0DFC` (float, 1.0 normally) × 0.8 (`0x800EBBA8`; standing × 0.9 × 0.8), then, only while
the set_anim result `sp+0x148` is set and |v| after that friction is under 20 (`0x8000D9F0`'s result against 400.0,
`lui 0x4079`), 3.0 × the forward magnitude is added along his facing (`lui at, 0x4008` at `0x80077D98` forward,
`0x80077DFC` back; the strafe the same with `sp+0x160` from `0x80077E58`); the forward magnitude is × 1.25 after the
decode. Full stick decodes 2.05: v' = 0.8 v + 7.68 while 0.8 v < 20, a mean of 24.0 u/s (the < 20 cap bounds the
stock run); below the cap the speed is linear in the magnitude (5 × the accel). The measured ground speed
`0x800E14B8` (= |v|) picks the run (`trot`, > 8) or the walk (`mosy`) and sets their playback rate in proportion
(`0x80079D94..`), so a slower Luke gets the game's own slower step. The grip is set 0 after 0.3 s airborne
(`0x8007989C`), raised back +4/s by the screen-effects update (`0x8006C96C`) and forced to 1.0 inside the control at
`0x80077BA8` whenever the stick is pushed up / down past 0.7 or the D-pad's forward / back are held: it cannot be held
from outside. Turning (`sp+0x160` × 80 °/s with the turn flags), the native aim and the fire `0x800737D8` do not read
the forward magnitude. The Humn has no slow state of its own and no drawn "stunned" look.

To support another player class: find its control function via the class table, find the
call to the stick curve `0x800BA268` (decode) and the yaw-rate integration, diff RAM while
turning to get yaw/rate fields, then hook both places like for `Humn`.

## Dash's motion and animation (Humn)

Found while researching a ledge hang (see the harness notes on recording an object per frame).

- The Humn control `0x80074FA4` keeps a button flag in `$ra`: `0x800754E8 and ra, t9, v1` (binding `+0x0A` & the
  held buttons, "back held"), read at `0x800759C8 beqz ra` and `0x80075B2C beql ra` before its next `jal`
  (`0x80075C6C`). At `0x80075968..0x800759D8` it sets the follow camera's swing factor `0x800E0EF4`: 0.8
  (`0x800EBA24`) at rest, 0.88 (`0x800EBA30`: stick y > 0.3 or binding `+0x08`), 0.6 (`0x800EBA40`: stick y < -0.3
  or the flag); the second read gates `sw zero, 0x800E0E10`. Measured 2026-10-29 (330 frames of `t_off.py controls`'
  inputs: stock 0.8 ×170 / 0.88 ×50 / 0.6 ×110).

- Writes that open the game up (2026-10-26, read from a .bps the user shared; none of it is used): `0x1000` (`b`) at
  `0x80035934`, `0x80035988`, `0x8003599C`, `0x800359B0`, `0x800359C4` opens all levels; the debug byte `0x800D098B` = 1
  (set there while the raw buttons `0x80113064` read Z+R exactly); `0x3F` at `0x80077155`, `0x800771F1`, `0x80077301`:
  the jetpack's fuel never drops.
- Lower RAM without the Expansion Pak (2026-10-25, `local/work/low_free.py`, the 36 stock-loadable savestates): no
  span of 64 KB is zero in all of them; the largest zero in every one are 34.3 KB at `0x8012095C` and `0x80134324`,
  29.0 KB at `0x800F4180`, 24.7 KB at `0x8015EB78`, 17.0 KB at `0x8018EA0C`, all inside the game's own data (likely
  pool tails): candidates only, not shown to stay free on busy moments or on the levels without a state.
- The object updates at 30 Hz (every second video frame). `+0xD8` is its clock in seconds (+10000).
- Velocity in units/second: `+0x98` x, `+0x9C` y, `+0xA0` z (jump starts at vz 15).
- Flags `+0x74`: `0x04000000` on the ground, `0x08000000` airborne, `0x00000004` set from the
  jump on, **`0x10000000` falling to death** (set by the game itself when Dash drops into a
  deadly pit; the `fall` animation starts with it).
- Writing the position copies (`+0x08`, `+0x50`) and zeroing the velocity every frame holds Dash
  in mid-air; the airborne flag then toggles each frame but he stays put.
- The jetpack: flag `0x300` (`FL_JET`) in `+0x74` while A fires it (on a level that gave the
  jetpack), and the float `+0xBC` is its fuel. The control function burns it (~0.14 a frame while
  firing) and clamps it to the max at `0x800E0DD8` (100; a full tank ~12 s). The *Jetpack Fuel*
  cheat row writes `+0xBC` = that max every frame, and gives the fuel percentage in the HUD the
  blue Invincibility gives the health (hook `0x80009138`; see the hook table and the HUD text
  elements below).
- Animation: `+0x1A0` current animation, `+0x1A4` the one being blended to, `+0x18C` 1 steady /
  3 blending, `+0x194` blend progress, `+0x198` blend time (0.2 s; 0.01 s into a jump).
  Each animation is a block with a 4-char name at `+0x1C`, the next block at `+0x14` and the
  playback frame at `+0x04` (15 frames per second). `+0x19C` points to the first block.
  Dash's 17: `fall` (death fall), `diea` (death; frame ~7.8 has both arms raised overhead),
  `trnr`/`trnl` (turn), `shfr`/`shfl` (side-step), `shoo` (shoot), `acta`/`actb`, `flyy`
  (jetpack), `jmpF` (jump/air), `crou` (crouch), `trtg`, `mosy` (walk), `trot` (run), `SFid`
  (idle fidget), `Sstn` (stand).
- Animations are chosen with `set_anim(id, flags, table, obj + 0x18C)` at `0x800175B8`; Dash's
  control function calls it ~25 times (block `0x800761EC…0x80076800`, before the yaw hooks).
  The pose is evaluated inside that call, so writing `+0x1A0` afterwards changes nothing on
  screen. `table` (`0x800E1328` for Dash) has a list pointer at `+8` to 0x24-byte descriptors,
  terminated by id −1: `{id, name tag, start frame, blend time, frames/s (negative: reverse),
  ?, ?, next id, kind}`. Dash's list (`0x800E0F14`): 0 `Sstn`, 1–2 `mosy`, 3 `shoo`, 5–6 `trot`,
  7–8 `trtg`, 9–10 `flyy`, 11–14 `jmpF` (air), 15 `acta`, 16 `actb`, 17–18 `trnl`/`trnr`,
  19 `crou`, 20 `shoo`, 21–22 `shfl`/`shfr`, 23 `diea`, 24 `SFid`, 25 `fall`, 26 `drwn`.
  The kind (the last word) is 0 or 1 on the stands (`Sstn` 0, `shoo` 3 / 20, `acta`, `actb`, `SFid`) and 2 or more on
  everything that moves him (walk, run, strafes, turns, jumps): a cheap "is this request a move" test.
  Standing with no input his control makes no `set_anim` call at all (the stand plays on), so a hook at
  `set_anim`'s entry is not a per-update point: use the stick decode (`0x800758A8`), which runs once every update,
  before every `set_anim` call of the ground path (`0x800761EC..0x800767FC`) and before the friction
  (`0x80077BC4..`). A velocity written there every update moves him by 0.72 of it standing (1.39 × 1.5 units asked
  over 5 keys moved him 1.509; 2026-11-15, `t_saber.py flow`). The play call's `how` 5, seen in a run: on another
  block it blends (state mode 3 on its first frame), on the block already playing it sets the frame back with no
  blend (mode 1).
  A descriptor with frames/s 0 freezes a pose: rewriting the `jmpF` ones to `diea`, start frame
  4–5, speed 0 shows a "reaching up for the ledge" pose in the air (the first ledge-hang look; the
  hang now builds its own poses, `hang.c` + `harness/pose/`, see `sote-patch/docs/ledge-falls.md`).
  A patch should hand `set_anim` its own descriptor/table instead of editing the game's.
- **Animation blocks** (one per animation, 0xC18 bytes each for Dash, in the level heap): `+0x00`
  pointer to the name, `+0x04` current frame, `+0x14` next block, `+0x1C` name tag, `+0x2C` frame
  count (float) and `+0x30` (int), `+0x38` first of the 0xA0-byte bone entries. Bone entry:
  `+0x08` model node, `+0x0C` next entry, `+0x10` the bone's current angles (3 floats, degrees),
  `+0x70/74/78` rotation tracks, `+0x88/8C/90` translation tracks (only the root and the model's
  scale bone; other bones hold non-pointers there). A track is one float per frame, frame f at
  index f − 1. The angles are about z, x, y: node rotation = (Rz(a0)·Rx(a1)·Ry(a2))ᵀ.
  `set_anim` → `0x80017344` → `0x8001700C(name, chain)` finds the block by name along the chain
  from the animation state's `+0x10` (Dash `+0x19C`).
- **Animation format, exactly** (pseudo-C of `0x800170F0`, `0x80016DB8`, `0x800166EC`, `0x80016824`, `0x800165E0`,
  `0x80016E28`, `0x80017344`, `0x800175B8`, `0x80017764`, checked on `palace.st`, 2026-11-07; probes
  `local/work/melee/`). Shared by every animated object (Humn, Trop, ATST, ...).
  - *Animation state* (Dash `+0x18C`, a Trop `+0xB8`): `+0x00` mode (1 steady, 3 blending; bit 31: dt 0 this
    update), `+0x04` (the current header's `+0x08`), `+0x08` blend progress (s), `+0x0C` blend time (s), `+0x10` the
    block chain, `+0x14` current block, `+0x18` the block blended to.
  - *Block* = an instance (0x1C bytes) and its header (0x1C), then the bone entries; in the loaded level the header
    follows its instance (`+0x1C`): `instance +0x00` → header, `+0x04` frame (float, from 1), `+0x08` speed (keys per
    second: `play` stores the descriptor's frames/s), `+0x0C` translation factor (4.0 on the guard), `+0x10` first bone
    entry, `+0x14` next block in the chain, `+0x18` a linked block (`play` keeps the frame when blending to it).
    `header +0x00` tag, `+0x04`/`+0x08` 0, `+0x0C` first frame (1.0), `+0x10` last frame (float, = keys), `+0x14`
    key count (int), `+0x18` s16 below the first frame / `+0x1A` s16 past the last: 0 wrap (loop), 1 clamp (`trDi`,
    `diea`, `acta` `0x00010001`).
  - *Bone entry* (0xA0) = bone instance (0x28) + bone header (0x78). Instance: `+0x00` → its header (entry
    `+0x28`), `+0x04` key cache, `+0x08` model node (0: skipped), `+0x0C` next entry (0 ends), `+0x10..18` the angles
    sampled this update, `+0x1C..24` the translation. Header (entry `+0x28`): flags in byte `+0x01`: `0x01` rotations
    from tracks, `0x02` translations from tracks, `0x08` the three angles as one rotation (the guard and Dash), `0x20`
    uniform keys; `+0x04` the rest matrix (4×4 floats); `+0x44` the key step (float 1.0: key k at frame k + 1) with
    `0x20`, else a pointer to the keys' frame numbers; `+0x48/4C/50` rotation tracks (one float per key, degrees; a
    null track takes the constant), `+0x54/58/5C` constant angles, `+0x60/64/68` translation tracks, `+0x6C/70/74`
    constant translation. The bytes `+0x02..03` and the unused track words hold leftovers, not flags or pointers.
  - *Playing*: the object's update calls `0x800170F0(state)` once: dt = `0x8018E998`; mode 1: `0x80016DB8(block,
    +0x0C)` advances the frame by speed × dt (`0x800166EC`: wrap or clamp by `+0x18`/`+0x1A`), then per bone samples
    the tracks (`0x80016824`: key index (frame − 1) / step, linear; angles the short way round, wrapped to ±180,
    `0x800165E0`) and poses the node (`0x80016E28`: rest matrix, + translation × factor, then the rotation, written by
    `0x8000FE48`). Mode 3 blends (`0x80016AC8`) until the blend time, then mode 1. Two exceptions to the short way
    (2026-11-13, the duel's moves): on an exact key (a clamped block held on its last) `0x800165E0` returns the stored
    angle raw, and the blend mixes the two blocks' angles linearly (from × (1 − t) + to × t, no wrap): a track stored
    ending at 360 spins the bone a full turn back over the blend into the next block (356–391° in 0.2 s measured);
    stored keys wrapped to (−180, 180] play the same and blend clean.
  - *Choosing*: `play 0x80017344(state, tag, how, start frame, blend time, speed)` finds the block by tag in the
    chain (none: nothing happens), sets its speed and frame, and cuts (how 2, or speed < 0) or blends (3, 5) to it.
    With the block already the one blended to (`+0x18`) it returns at once for how 2 / 3 (4 / 5 only set the frame):
    no blend on one instance, a blend is always between two instances (`0x80016AC8` mixes `+0x14`'s samples into
    `+0x18`'s). The sampler `0x80016824(bone instance, frame, keys)` reads the tracks from each bone instance's `+0x00`
    header; the block header (instance `+0x00`) gives only the frames, the key count and wrap / clamp: another
    block's header written into an instance plays nothing new unless its 17 bone instances' `+0x00` are moved too (the
    tag found by `play` is the header's, `0x8001700c`).
    `set_anim 0x800175B8(id, flags, ctl, state)` (Dash) and `0x80017764(id, flags, ctl2, state, list)` (Trops, ATST:
    `ctl2` {time, list index}) pick a descriptor by id and call it.
    `play`'s start frame (2026-11-15, pseudo-C of `0x80017344`, `0x80017274`): a frame number in the block's own units
    (from 1: key k at frame k + 1), any float, given to `0x80017274(block, start)`, which writes it to the instance's
    `+0x04` and −1000.0 to each bone instance's `+0x24`; so a block can be started anywhere inside its keys. Two cases
    replace it: a block already the blended-to one (`+0x18`) with how 4 / 5 has its frame set with no blend, and a
    block whose `+0x18` link is the one playing (`state +0x14`) takes that one's frame (the start ignored). The frame
    wraps or clamps only at the header's first / last frame (`+0x0C` / `+0x10`): nothing stops at a part of a block.
    The blend `0x80016AC8` advances both blocks (`0x800166EC` on each) while it mixes, matches the bone instances by
    model node (`+0x08`), writes the mixed angles and translation into the `+0x14` block's bone instances and poses
    each node from them (`0x80016E28`); a bone whose header flag `0x10` is set on either side takes the blended-to's
    values unmixed. So after an update the angles every node was posed from are in the `state +0x14` block's bone
    instances (`+0x10..18`), whichever mode ran (Dash's arm and spine headers: flags `0x49`).
  - *A Trop's*: state `+0xB8` (chain `+0xC8`, current `+0xCC`, blend-to `+0xD0`), `ctl2` `+0xD4`/`+0xD8`, list
    `0x800E65E4[kind]`. Kind 0 (the guard) `0x800E5F00`: id 0 `trSt` (idle, 2 keys/s), 1 `trTr` (15), 3 / 2 `trSh`,
    4 `trDi` (death, kind 10), 5 `trOu` (15); its AI calls `0x80017764` from the state switch `0x800B04B8` (state 0:
    id 0 and the timer `+0x80` = 1.5), so an idle Trop with its timer held re-picks nothing. Trop 0's chain on
    `palace.st`: `trOu` 21 keys, `trSh` 8, `trTr` 15, `trDi` 23 (clamped), `trSt` 30; the guard's 17 bones in `trSt`
    order: 16 root (translation tracks), 15 pelvis, 14 spine, 13 chest, 12-11-10 right shoulder, forearm, hand (the
    rifle), 9-8-7 the left ones, 6 head, 5-4-3 and 2-1-0 the legs (`harness/guard_asset.py` `MAP`).
  - *A Trop's bone instances, the shared headers* (2026-11-11, sub-level 26's guards under id 33, the Trop at
    `0x801B9730`): each Trop's blocks in its chain (`+0xC8`) are instances of its own (`0x801D7xxx`), their bone
    instances its own, but each instance's `+0x00` points at the bone header shared by every Trop of the level (in the
    level heap, `0x801BAAB0` .. `0x801BD7F0` for the upper arms). Every update re-poses each bone node from its
    header's rest row (`+0x34..0x3C`, the rest matrix's translation; `0x80016E28` → `0x8000FE48`): a node's `+0x38`
    written once is gone 2 VIs later, and over 600 VIs (walk, run, fire, a melee block) the arm nodes never left the
    rest row. So a joint moves only by the rest row of every block the object plays: the shared header moves it on
    every Trop, a block of one object's own (or a level where only it plays the block) on that one. Units: 2.0 node
    units = 0.100 world (the guard's shoulder joints 1.506 apart → 1.306). Nothing in the game reads the arm nodes'
    place: the gun and the fist follow the hand node, a Trop's shot spawns from its place plus fixed offsets
    (`0x800B1560`).
  - *An animation of our own on one Trop* (2026-11-07, no patch code, `local/work/melee/p4_punch.py`, stills
    `local/run/shots/melee_punch/`): a copy of Trop 0's `trSt` block (0x38 + 17 × 0xA0 = 0xAD8 bytes) at
    `0x80700000`, its own pointers fixed (instance → header, bone entries → their headers and the next entry), tag
    `trPu`, 20 keys, speed 15, the left shoulder (bone 9) given new rotation tracks, linked after `trSt` in Trop 0's
    chain and made current (`+0xB8` = 1, `+0xCC` = `+0xD0` = it) plays on Trop 0 only; Trop 4's current block stayed
    its own `trSt`. Left shoulder angles at rest (−2.3, 31.7, 80.5): the third angle down swings the arm forward
    (−5 at the strike), the first down (−45) brings it in front of the chest: a jab; the second angle up raises it
    sideways. Each guard has its own nodes and its own chain, so a block of ours costs 0xAD8 bytes + 4 × keys per
    keyed angle per guard that plays it.
  - *Posing, measured* (2026-11-07/08, `palace.st`, `local/work/melee/fk_check.py`, `p6_diea.py`, `harness/pose/
    melee_view.py --check`): a bone's posed node rotation (node `+0x14`) = the bone header's rest 3×3 × `rot(z, x, y)`
    of the sampled angles, its translation = the rest row + the sampled translation × the instance's factor, on every
    bone of the guard's `trSt` and Dash's blocks (0.0000). The guard's rests are the identity on bones 0–15 and a
    scale on the root; Dash's are the identity except the pelvis (17: a 0.952 scale, so everything below it is 0.952 of
    what an FK without it gives) and the model bone (18: 2.906). A block of ours whose bone headers copy the object's
    own rests, flags (`0x01|0x08|0x20`, `0x02` with translation tracks) and constants plays exactly its angles.
    Dash's chest and neck (9, 2) are turned again by the game after his block is sampled (the spine, 10, is not: a track
    there holds; the angles exact, their 3×3
    up to 0.10 off rest × rot). Where (2026-11-15, `0x8007682C..0x80076A00`, right after the animation update
    `jal 0x800170F0` at `0x80076824`, s0 the Humn): `+0xF0`, `+0xF4`, `+0xFC` clamped to ±30, `+0x100` to ±75; then the
    node at Humn `+0x250` (bone 2, the neck; `0x801F5970` on `palace.st`) is combined (`0x8000E3A4`) with the rotation
    `0x8000F5C8(+0xF0, −+0xF4, +0xF8)` over its own posed matrix (read by `0x8000FEB8`) and written back by
    `0x8000FE48`, and the node at `+0x254` (bone 9, the chest, `0x801F5778`) the same with `+0xFC`, −`+0x100`,
    `+0x104`. That is the game's one place where a bone node is re-posed between the sampling and the draw; the only
    `jal 0x800170F0` in the Humn code is `0x80076824`. The draw method (`0x8007A118`) runs after it: a node written
    there (the placement node at `0x8007A134`) holds for that frame's draw.
    Bone nodes too (2026-11-15, `palace.st`, standing and running): at `0x8007A134` a bone instance's angles
    (`state +0x14` block, entry `+0x38 + 0xA0 k`, angles `+0x10..+0x18` = the block's sampled track values z x y in
    degrees, to 0.000°) changed and its node re-posed by `0x80016E28(entry, the block's +0x0C value as its
    bits)` show in that same frame's picture (the right arm raised over the trot's legs); the update re-samples every
    node each frame, so such a write never compounds (`saber.c` `saber_pose`).
  - *Root translation.* The guard's root x, y are root motion: the Trop moves by the change of the sampled x, y (1:1
    world units, along its draw rotation) and the node's x, y stay 0; its z × factor × 0.25 is the height in world
    units. Dash's model bone (18) is different: its rotation turns his whole figure about the model node's origin
    (`diea`'s end: −89.93 about x, on his back; + about x pitches him forward: +90 face down), its sampled z sets the height of the placement node above his model
    (`+0x38..0x40`, its parent's parent; `0x801F54A8` on `palace.st`) to his floor point + z + 0.2 (`Sstn` 2.941 →
    3.141, `diea`'s end 0.388 → 0.588, every key of a block of ours alike), and its x, y move nothing (the node's
    translation stays 0; held or let go his place stays): his blocks carry no root motion of their own.
  - *Scaling a drawn figure* (2026-11-09, `palace.st`, a build with the Look row and Guri; probes
    `local/work/scale/scale_probe.py` (RAM) and `render_test.py` (the render), logs `local/run/scale/`,
    `local/run/look_scale/d10/`). Measures that walk the node tree in RAM (the vertices of every mesh under a node,
    through each node's 3×3 and translation) are not what is drawn: check a size on a still. Found so far:
    - A bone node's `+0x14` written once is the game's again at the next update (Dash's model node 2.906 → 2.777
      written, 2.906 one VI later; the guard's root 0.2 → 0.22, 0.2): the update writes every bone node from its bone
      header's rest × rot. The headers are per block for Dash (all 18 of his blocks: 2.906) and shared by every Trop of
      a kind (Trop 0's `trSt` root header × 1.1 changed Trop 4's root node too).
    - Above the bones each object has a node the animation never writes, `w0` `0xD064…`: Dash's is the one child of
      his placement node (`0x801F9900` on `palace.st`; 3×3 0.0625, translation 0; children the model node and an empty
      bone node), a Trop's the one child of its Dfob root (3×3 0.25; Trop 0 `0x801F91B0`, Trop 4 `0x801F92D0`). Written,
      it stays as written (300 VIs) and the RAM walk's vertices follow it, but **the drawn figure does not**: Dash's
      node × 0.5 every VI changed nothing on screen, and the Luke look's stills with it × 0.905 were the stills
      unscaled pixel for pixel. The render's traversal does not go through it.
    - The placement node (Humn `+0x24C`, `0x801F54A8` on `palace.st`; translation his floor point + the model bone's
      z + 0.2) does scale the drawn figure (× 0.5 every VI: drawn half size), but the game writes its 3×3 again within
      2 VIs (× 0.5 once: 1.0 two VIs later, the translation untouched). The rewrite is the draw method's copy from
      `+0x208` (`jal 0x8000FE48` at `0x8007A134`, every draw); a write right after that copy holds for the draw (the
      Look's drop moves the drawn soles 0.310 → 0.025 that way). Scaling with it needs that hook too; its pivot (the node's translation, above his feet) and whether the camera and melee.c's
      reads follow it are not measured.
    - Drawn heights from the stills (the turntable's pair mode, `local/work/scale/tops.py`; the drawn top above the
      floor, Look 2 beside Guri at the same depth): front Luke 6.238, Guri 5.871, Dash's own 6.082; the soles (RAM
      lowest vertex, matching the drawn rows within 1 px) Luke 0.310, Guri −0.02, own 0.189. The RAM walk of the same
      poses (standing: Dash `SFid` key 0, a Trop `trSt` key 0) gives Dash's own 0.165–6.093, the guard look
      0.301–6.305, the Luke look 0.301–6.223, Guri 0.016–5.941: the unscaled walk agrees with the draw (Luke 6.223 vs
      6.238); with his `0xD064` node scaled the walk said 5.947 while 6.238 was drawn.
  - *Off the ground the game holds `jmpF` on him: the controller's descriptor chain* (2026-11-08, `palace.st`, probe
    `local/work/melee/r1_trace.py` over `melee_view.py --stills`, logs `local/run/melee/r1a.log`, `r1b.log`). Once he
    is more than 2 above the floor (`+0x84 > 2`, `+0x74` bit `0x04` clear, no jetpack) the Humn control sets bit `0x04`
    and calls `set_anim(13, 1)` (`jal` at `0x80077CC4`). Descriptor 13 (`0x800E10E8`) is `jmpF` start 30
    (its last pose, arms and legs hanging, upright), blend 0.01, fps 0, `+0x14` 0.1, `+0x18` (duration) **0**, next id
    **13** (itself), kind 4. Every update, before the animation update (`0x8007681C`, then `0x800170F0` at
    `0x80076824`), `0x800176F8(ctl, state)` adds dt to the controller's time `ctl +0` and, when it passes the current
    descriptor's `+0x18` with a next id ≥ 0, calls `set_anim(next, 2)`: flags 2 is never ignored as "the same id", so
    13 re-asks itself every update and `play` (how 5) blends to `jmpF` (0.01 s: done in that same update). A block of
    ours cut in from outside is therefore replaced by `jmpF` frame 30 on every update in the air and never sampled
    (a sentinel written into its sampled angles stays; the pelvis node is rewritten to `jmpF`'s each update). On the
    floor his descriptors have next −1 (`Sstn`) or long durations, so a block of ours stays. `+0x74` written to the
    ground value changes nothing (the request comes from the descriptor, not the flags). Same chain: `flyy` 9/10 →
    13 after 0.5 s, `jmpF` 11 → 12 → 13, `fall` 25 and `drwn` 26 re-ask themselves every 100 s, `SFid` 24 → `Sstn` 4
    after 6 s (the "blend of its own" while he stands held), `shoo` 20 → 4 → 0.
    *What shows a block of ours in the air:* the controller's current descriptor (`0x800E1328 + 4`) pointed at a
    descriptor of ours with next id −1 (or a long `+0x18`): {id 99, `plCa`, start 10, blend 0.1, fps 0, `+0x14` 100,
    `+0x18` 100, next −1, kind 7} at `0x807F0000`, controller time 0. Then nothing re-asks `jmpF` (389 of 390 VIs
    current = blended-to = `plCa`, descriptor 99), and while carried (`+0x74` `0x08000044`) every node is posed from
    the block: the model node = rest × rot(sampled) (0.000; pitched 90 on `plCa` key 9) and the pelvis node too
    (0.000); chest and pelvis nodes 0.044 apart in height, legs 72° from straight down. Kind 7 with time below
    `+0x14` also makes `set_anim` refuse the game's own lower-kind requests (the landing's id 14 is kind 5, the
    walk / stand ones 0–2), as `diea` (kind 7, `+0x14` 5 s) does. Measured on a throw (`melee_view.py --video`, a second descriptor for the fall block
    set at the release): through 100 VIs of flight, the landing and 120 VIs lying, the block stayed current with nothing
    re-cutting it. Still: `local/run/melee_r1_carried.jpg`.
  - *Loops and time.* A looped block's last frame equals its first (`0x800166EC` wraps by last − first), so a loop's
    last key repeats its first. Game time (`0x8018E998`, the clock at Dash `+0xD8`) runs ~13 % slower than VIs under
    the harness on `palace.st`: a block's progress is read off its own frame, not counted in VIs.
  - *Dash after a knock-back.* Thrown (his velocity written once with the airborne flag), his controller puts its own
    block back every update in the air (descriptor 13's chain, above) and `Sstn` / `shoo` on landing; to keep `diea` (or a block of ours) playing,
    point the controller at a descriptor of ours (kind 7, next −1: *What shows a block of ours in the air*, above);
    cutting it in again each update at the game clock's frame also works but fights the controller. Thrown at 18 units/s along a facing with vz 19, released
    1.55 above the floor: 1.57–1.63 s in the air, 24.4–24.7 units on, peak 7.3 (the ground speed is capped at 18);
    released 1.47 above it: 88–90 VIs = 1.34–1.35 s of game time, 24.1–24.2 units on (2026-11-08); released 4.76 above it:
    1.49 s of game time, 26.8 units on, peak 10.5 (2026-11-08). Standing held
    with a block of his parked (speed 0), his controller now and then starts a blend of its own (his state's mode
    3): a check that reads his sampled angles plays the block again until the state stays steady (mode 1, current
    and blended-to both the block).
  - *The guard's idle sways* (2026-11-08, `palace.st`): `trSt`'s root track moves, so an idle Trop drifts by root
    motion: y 0.13 at key 0, 0.55 over keys 5–9, back to 0.13 by key 12 (x 0.00–0.18); a block that ends on `trSt`
    key 0's root x, y (0.004, 0.129) blends into it moving her nothing (0.02 over the 0.3 s blend), then the sway is
    the game's.
  - *Staging two objects close* (the preview): the camera's droid (Trop 1, the creature camera's object) and a Trop
    push Dash out of their radius (`+0x60`, ~4 units a frame): radius 0 holds him where written. His drawn matrix
    `+0x208` is rebuilt from `+0x14` / `+0x8C` (0/90/180/270 exact); the tags `guGr guPu guSh guLf guTh plDb plUp`
    are in neither Trop 0's chain (`trOu trSh trTr trDi trSt`) nor Dash's (`fall diea trnr trnl shfr shfl shoo actb
    acta flyy jmpF crou trtg mosy trot SFid Sstn`).
  An entry never sampled yet (a block not played since it was made or copied, the game's frozen `shoo` too) holds the
  translation offset `+0x1C..+0x24` = (0, 0, -1000); `0x80016E28` adds it, so re-posing such a node puts the bone
  1000 below (the saber's parry did: the upper body gone for 7 frames, 2026-11-16).
- **Dash's own animations for a fight** (2026-11-07, `local/work/melee/p3_dash.py`, stills
  `local/run/shots/melee_p3/`): he has no hit, flinch or get-up animation; the damage `0x800732D4` only lowers
  health, sets Humn `+0x74` bit `0x10` (read by no Humn code), flashes and grunts, and plays id 23 `diea` at 0.
  The death starts only there: it asks `diea` once, as health drops below 1 (health written 0 starts none); a request
  refused then (the controller on a descriptor of a higher kind, the saber's swing: kind 7) is lost, nothing asks it
  again (2026-11-16). His
  blocks (keys): `fall` 21, `diea` 25 (clamped; blown off his feet backward, on his back by frame ~12), `trnr` 20,
  `trnl` 21, `shfr`/`shfl` 19, `shoo` 48, `actb` 17 and `acta` 14 (clamped: a hand reaching forward), `flyy` 36,
  `jmpF` 36, `crou` 23, `trtg` 19, `mosy` 20, `trot` 20, `SFid` 30, `Sstn` 1. Descriptor kinds (`+0x20`): stand,
  `shoo`, `acta`/`actb`, `SFid` 0; walks, runs, turns, `crou` 2; `flyy` 3; `jmpF` 4/5; `fall`, `drwn` 6; `diea` 7.
  Held (position `+0x08`/`+0x50` written, velocity 0, every update) with his state `+0x18C` = 1 and `+0x1A0` =
  `+0x1A4` = a block (frame `+0x04`, speed `+0x08` set), the controller left at the stand (`0x800E1328 + 4` =
  `0x800E0F14`), the game asked for nothing in 4 s per animation: any of his blocks plays where he is held. A stick
  input changes his movement state and the game asks for another id: a hold under play must keep the controller's
  descriptor at what the game asks for.
  Model node (0x48 bytes): `+0x0C` child count, `+0x10` child list, `+0x14` 3×3 rotation,
  `+0x38` translation. Dash's skeleton (entry index): 18 model root → 17 pelvis → legs 16→15→14
  and 13→12→11, spine 10 → chest 9 → arms 8→7→6 (right: shoulder, forearm, hand) and 5→4→3
  (left), neck 2 → head 1; 0 is the root translation. Left and right are mirror images in x.
  A node's children are bone nodes and meshes; the right hand (6) has the hand mesh, then the
  held weapon's mesh, which ends up with bit `0x80` in its first word. That bit is no weapon mark: the mesh draw
  `0x800BBBF8` sets or clears it on every drawn mesh (`w0 >> 16 == 0x3064`) from s16 `0x800E7C38`, the render state
  the mesh drawn before left, so it follows draw order (measured on `play.st`, bone 6 w0 low byte: Dash's hand `40`,
  weapon `c0`; weapon first, then another mesh: `40`, `e0`; another mesh, then the weapon: `60`, `c0`; the jetpack on
  the chest, bone 9's second mesh, carries it too). Leaving a mesh out of the list hides it.
- `set_anim`'s third argument is really the object's animation controller `{time, current
  descriptor, list, ...}` (Dash: `0x800E1328`). A request for the current id is ignored; a
  request is also refused while the current descriptor's "kind" (`+0x20`) outranks the new one
  and its time is below `+0x14` — give a borrowed pose kind 0. The game only asks for a new
  animation when its own movement state changes, so after overriding the pose, point the
  controller's current descriptor elsewhere and call `set_anim` once yourself. The current descriptor is `+4`: Dash
  held in place by writing his position while the stick runs him is taken for blocked and his run stalls; writing the
  run's descriptor (`0x800E0FC8` on `palace.st`) into `0x800E1328 + 4` each frame keeps it running
  (`tools/video/record_guard_turntable.py MOVE=1`, 2026-11-06).
- Dash keeps three rotation matrices (rows right/forward/up/translation): `+0x20` (translation =
  position `+0x50`), `+0x108` (the camera follows this one; translation z + 5.5) and `+0x148`
  (what the model is drawn with; translation `+0x178`). The game rewrites yaw, position and
  these matrices late in the control function, so anything that must stick for the frame
  (e.g. holding him in mid-air) goes at its end: the last instruction before the epilogue
  reloads `ra` is at `0x8007A104` (hooked with `jal`, re-executing `lw ra, 0x3C(sp)`).
  The draw method (`0x8007A118`) hands the model `+0x208`, so that is the one that turns him
  on screen (also rebuilt every update; write it at the control function's end). Leave
  `+0x108` alone or the camera turns with him (its rotation; writing its translation is fine).
  On stairs and slopes the game pitches `+0x108` along the slope (forward row z up to ~0.57,
  i.e. ~35°, eased in) and the active camera takes that pitch: it looks at the ceiling running
  up and at the floor running down toward it. The camera object (`0x800D08A4`) holds the Doly
  at `+0x8` (Doly `+0x20`) and `+0x108` at `+0x10`. Flattening only the rotation rows of
  `+0x108` from the Doly update (after Dash's control function) levels the camera; laser bolts
  still follow the slope. The Doly keeps the eye at `+0x50` and the look target (player
  + 6.5 up) at `+0x68`; neither drives the pitch.
  The frozen `flyy` frame used for the ledge hang has the body turned round on its root, so
  the hang yaw is the wall direction + 180.
- Heading has a copy too: `+0x14` (0..360) next to the position copy `+0x08`. The control
  function puts `+0x8C` back from it every frame, so a heading you set must go into both.
- Translations: `+0x148` = `+0x108` = feet + (0, 0, 5.5) in normal play; `+0x208` = that plus
  the current pose's root offset (about −2.7 for the frozen hang frame, bobbing while running).
  When his body touches geometry (e.g. held against a cliff rim) the game pushes `+0x148`/`+0x208`
  away by a varying amount while `+0x50` stays put: if you hold him somewhere, write these
  translations as well, or the model drifts by up to ~1.6 units.
- Hooking `set_anim`'s entry: replace the first two instructions with `j tramp; nop` (a `jal`
  would clobber the caller's `ra`) and run both in the trampoline.

## Other game structures

- Pad: `0x80113098` (s16 x, s16 y, u32 buttons at `+0x14`, standard `OSContPad` bits:
  A `0x8000`, B `0x4000`, Z `0x2000`, START `0x1000`, d-pad `0x0F00`, L `0x20`, R `0x10`, C `0x0F`).
  Raw controller data before the decode: `0x80113080`, 6 bytes a controller (u16 buttons, s8 stick x at `+2`,
  y at `+3`); the controller in use u32 `0x80113060`. Read at `0x8001311C` (*Known hook points*).
- Control presets: index s16 `0x800D252C`, names (pointer table `0x800DD650`): 0/1 Standard,
  2/3 Traditional, 4/5 Alternate, 6/7 Strafe (pairs differ only in slots `0x00–0x04`).
  Binding table `0x800E6808`, 96 bytes per preset, one u16 button mask per action slot.
  On-foot slots: `0x18` fire, `0x1A` jump, `0x1C` Aim/Look, `0x1E` strafe modifier,
  `0x20/0x22` strafe left/right (Strafe preset only). Standard: B fire, A jump, Z aim, R strafe;
  D-pad (read from the table, 2026-10-25): presets 0/1 and 4–7 hold it in slots `0x10..0x16` (up, down, left,
  right: the snowspeeder's view keys, `0x8008F0D8..0x8008F2F4`, view u32 `0x800E1834`) and 0 in `0x08..0x0E`;
  Traditional (2/3) the other way round: `0x08` D-up, `0x0A` D-down, `0x0C` D-left, `0x0E` D-right, `0x10..0x16` 0.
  Traditional/Alternate: A fire, B jump; Strafe: A fire, B jump, C-right aim, Z/R strafe L/R.
  Aim/Look held: Dash stops turning, the stick tilts the aim/view instead. The aim pitch is
  `Humn+0x1B4` (degrees; stick forward takes it to about -62, i.e. aiming down).
  Menu labels are plain strings in main code (`~~Aim/Look` at `0x800D22CC`, `~~Strafe Lf`, ...).
- Fire: Dash's weapon code checks the fire binding (`0x800E6808 + preset*96 + 0x18`) against
  the pad at `0x8007234C`, after `0x80072324: bnez v0, 0x8007235C` (v0: auto-repeat, fires
  without the button). Not firing goes to `0x800723F8`, which clears `+0x74` bit `0x800` (set while
  a shot goes off). It runs before the decode hook (`0x800758A8`) in the same update, so masking
  the button from the decode hook is too late.
- Health (`+0xB4`) reaching 0 starts the death sequence and a respawn ~3 s later; no flag on Dash
  marks it (`0x400` stayed clear when he was shot down in the harness).
- Frame dt (double): `0x8018E998`. The game clock: double `0x8018E9A8` (copies at `0x8018E9A0`, `0x8018E9B8`),
  seconds from power-on, not reset at a level start (57.35 at Echo Base's first controllable VI from a boot), read
  by ~20 sites (`clock * k` into sin/cos `0x8000D4D0`, timers): two states at the same game frame and place with
  other clocks play differently (the follow camera's swing). A fixed frame time: double `0x800E6B10` > 0 makes
  `0x800B8D6C` use it as the frame dt and add it to the clock.
- Camera views (the `~~Camera` binding, L in every preset). On foot: view s16 `0x800E0EEC`
  cycles 1 follow → 0 first person → 4 fixed "drop" camera (no object placed: a HUD tripod icon) → 5 overhead.
  `0x8006A214(player, view, 0)` switches to a view exactly like the button (it also sets
  `0x800D08D0` = 1 and the camera id u32 `0x800D08A8`: 7 follow, 4 first person, 9 drop, 6 overhead).
  View 2 is the Leebo Scanner (secret #1): an overhead camera (id 6) picked by `0x8006A214`'s case 2,
  which first traces straight up (`0x800695CC` → `0x80069404`, 12 units) and falls back to view 1
  (follow) under a low ceiling; the game's trigger (block around `0x80071B50`, gated by `0x800359F0(1)`)
  holds C-right ~5 s then switches the view. The patch's Cheats toggle just calls `0x8006A214(player, 2, 0)`.
  The drop camera (view 4, 2026-10-28, corrected 2026-11-08): `0x8006A214` case 4 calls
  `0x80069648(player, player + 0x118, 20.0, 0)` (places it: traces up to 4 jittered directions from the point, then
  `0x80009370(9, 3, 0x8018DD68, 0)` and `0x80009488(9, player + 0x108, 0)`, or `0x8018DD28` while float
  `0x800DEB78` > 0) and `0x80069B44(player, 1)` (its update), then camera entry 9. No object is placed: the
  camera-on-tripod picture is a HUD icon drawn while entry 9 is the active index (not traced further). Entry 9 is
  type 3 in every level read (sub-level 4, the Gall Run, the palace): `+8` = `0x8018DD68`, the eye's matrix (the eye
  is its translation `0x8018DD98`); `+0x10` the look matrix (`0x8018DD28` at the level start, the player's `+0x108`
  after a placement); `0x8018DD58` is the look matrix's translation (the look point), not the eye. In the Gall Run,
  written straight from the harness (entry 9 on, `+0x10` the Falcon's guns' matrix, `0x8018DD58` the eye) it
  trailed the ship ~68 units behind it, not standing still. The game's standing camera that already works in flight
  is type 2 (entries 7, 8 there: eye from `+8`, looking at `+0x10`).
- Camera entries on foot (2026-11-08, `palace.st`, `local/work/melee/r2_entries.py`). The camera update
  `0x8000A020` runs every frame over entries 0..9 only, each with type s16 `+4` ≠ 0 and flag `+0` set (the active
  entry and a blend's target): place mode s16 `+6` (0 copy the `+8` matrix into the rows `+0x14..+0x53`, 1 / 2 / 3
  other transforms of it), then for types 2, 3, 4 a look at `+0x10` (look mode s16 `+0xC`: 0 a matrix's translation,
  1 a point; plus the offsets `+0x6C..`; type 4 adds the facing row × (1 + 40·|z|)); type 3 with place 0 writes its
  rows back into `*+8`. Type 0 is never updated. `0x80009370(k, type, eye ptr, place)` writes `+4`, `+6`, `+8`;
  `0x80009488(k, look ptr, look mode)` `+0x10`, `+0xC`. In the palace (player `0x801A5E90`):
  - 0: type 1, `+8` `0x801B65A0` (not traced);
  - 1, 2, 3: type 0, all zero: unused on foot. No game call names entry 1 by a constant (`0x80009370`,
    `0x80009488`, `0x80009648`, `0x8000952C`); entry 2 is switched to at `0x8005F014`, entry 3 at `0x8005EC48`,
    `0x8005F100`, `0x800995D4` and set by `0x800A8020`, `0x800AA9DC` (none ran on foot in the palace);
  - 4: type 1, `+8` = the player's `+0x108` (first person, view 0);
  - 5: type 1, `+8` = the player's `+0x20`, offsets (0, 0, 40, 0, −90) (`0x8000A7B0(1)`: the Leebo Scanner, view 2);
  - 6: type 1, `+8` `0x801B8580` (overhead, view 5; `0x800695CC` re-sets it);
  - 7: type 4, `+8` `0x8019F834` (the Doly), `+0x10` the player's `+0x108` (follow, view 1);
  - 8: type 1, `+8` = the player's `+0x20`;
  - 9: type 3, the drop camera (above).
  Each frame the on-foot camera code (`0x800702DC`) copies the active index into s16 `0x8018DDE8` (7 → 1, 4 → 0,
  9 → 4, 6 → 5, 5 → 2, 0 → 3; any other index, −1 during a blend included, leaves it), and `0x8006FFE4` runs the drop
  camera's update `0x80069B44(player, 0)` while it is 4. So entry 9 active on foot is always the drop camera,
  whoever switched to it. `0x80069B44` (when the player's `+0x74` bit 28 is clear) re-places entry 9 by
  `0x80069648` (which writes its `+8` / `+0x10` back to the game's) when:
  - `0x800DEB78` > 0 (a scripted look point), every frame;
  - cooldown float `0x800E1428` ≤ 0 (set 1.0 s by each re-placement) and: the line from the eye `0x8018DD98` to
    the player's `+0x138` (trace `0x800654A0`) blocked over 0.25 s (float `0x800E1424` counts it; `0x800EB600` when
    the floor moved), or the eye farther than 30 (√min(900, (`0x800E0E9C`/4)²)) or nearer than 1.5 (a height
    0..6 above counts 0);
  - `0x8018DD20` ≠ 0 (at the player's `+0x118`, 20);
  - forced by the floor (`0x800E0EE4`, set by `0x8006A13C` when the floor object's `+0x10` bit 22 is set): blocked
    over 0.5 s (or `0x800EB5FC`) → `0x8006A214(player, view, 0)`, the view back.
  Measured (3 s, an orbit of ours R 9 about the player, `+8` / `+0x10` our two identity matrices, blended in with
  the game's 0x8000952C writes): entries 1, 2, 3, 8 made type 3 by those two calls' writes: index k, `0x8018DDE8`
  stays 1, our pointers never replaced, the eye exactly ours (error 0.0000, 84 frames), no HUD icon; the blend back
  to 7 ends on 7. The blend `0x8000952C(k, s)` holds the active index `0x800D08A8` at −1 for its `s` seconds, then
  `0x80009648(k)` sets it (pseudo-C of `0x80009838`). Entry 9 the same way: `0x8018DDE8` = 4 one frame after the blend's end; with `0x8018DD98` also
  written = our eye it was re-placed 0.22 s later (the blocked-line rule) and held the game's pointers 75 of 81 frames.
  The train (`HumT`) has its own: view u32 `0x8018E928` (1 behind, 0 first person, 2 overhead),
  L in the behind view also steps the distance float `0x800E53D4`; code around `0x800A87B0`,
  cameras picked with `0x80009648(id)`. `0x800A7C90(float blend)` switches to the behind view
  (view 1, camera 7), `0x800A7C20` first person, `0x800A7D0C(player)` overhead.
  The train's behind view: Doly placement `0x800611C8` (called at `0x80062AFC`) puts the eye
  (Doly `+0x50`) `0x800E53D4`/10 = 0.8 units behind Dash along the facing row of the matrix it is
  given, closing 20% of the angle error per update, at most 40°. The camera entry (cameras at
  `*0x800D08A0`, 0x80 each, entry `+4` = 4) takes its eye from the Doly and looks (`0x800096C8`,
  no smoothing) at Dash's camera matrix (`+0x10` → `HumT+0x11C`) translation + (0, 0, 0.1) +
  its facing row × (1 + 40·|row z|), i.e. one unit ahead of Dash. If that row and the eye's
  angle disagree by more than ~90°, the point is behind the eye and the view faces away from Dash.
- Active camera pointer `0x800D08A4`: right/forward/up rows `+0x14/+0x24/+0x34`, eye `+0x44`.
  On-foot projection ≈ fovy 77°, 4:3. Doly (dolly camera) `+0x60` → followed object.
- Follow camera placement `0x80061774(doly, matrix)` (on-foot mode, called at `0x8006282C`):
  from the matrix translation + 0.7 up it traces level along −facing to twice the camera
  distance (`0x800E0EF0`, 8 on foot) with object flag 0, and puts the eye at half the hit
  distance (all of it if clear); the result is stored at `0x800E036C`. So a wall up to 16 units
  behind the player pulls the camera in. A second trace then lifts the eye (≈ +6.2 over the
  player's feet in total). While Dash hangs, the matrix translation is 5.5 above his `+0x50`.
  Its swing (decompiled 2026-10-28): the eye's yaw error to behind the facing × float `0x800E0EF4` per update
  (0.797 in Echo Base; 1.000 read on `lvl0.st` during the AT-ST's turn, 2026-10-28), halved while that step is under
  `0x800E0EFC` (15°), clamped to ± `0x800E0EF8` (40°); the strafe keys (`0x800E6826..2A` & pad) stop it. It reads the
  followed object's sector `+0x70` (an on-foot room) and traces at Dash's scale, so it cannot drive a non-Dash rig.
- Class records (the full per-level table is at `0x80112808`, 0x30 each; `0x80112B08` is just its
  entry 16, `Humn`): `+0` tag, `+4` flags, `+8` instance count, `+0xC` instance size, `+0x10` first
  instance (instances back to back), then the method pointers (create/update/draw/free). Some
  enemies are only reachable this way, not through the
  target pool: on the Ord Mantell train the drones `TGun` (`0x80112F58`; one hit kills: `+0x60`
  goes from 0.56/1.41 to −1) and `TTar` (`0x80112CE8`). Train cars are `Trai` (`0x80112F28`, 23
  of them): `+0x50` position, the `+0x30` row (x, y) is the car's axis.
  Cars turn with the track (from om.st the first bend swings the car from 88° to 123° and back
  to 54° within ~25 s) and carry Dash round: his `HumT` yaw `+0x90` is a world angle and follows
  the car while he stands still, so anything kept as a world angle (the lazy camera) must turn with the car.
- Doors/panels are the `Door` class (tag `Door`, entry 14 of the Echo Base class table). Each has
  its position at `+0x50` and an open/close state machine (s16 `+0x8C`: 0 closed, 1 opening, 2 open,
  3 closing) run by the update method `0x80062F88` (pure animation). They open on a message: the
  third method `0x80063178` reacts to `"Nudg"`/`"Nud2"`/`"Isct"` by flipping the state, and the
  collision pass around `0x8000B900` sends those when the player walks into them. The player's
  "Activate" action is binding slot `0x24` (R in the Standard preset); its press is read in the
  Humn control function at `0x80075B64` (`lhu ..., 0x24(v0)`).
- The game's own auto-aim `0x8005B33C(origin, dir, tag, out_z, flags, min_dot, range, collider, out_obj)`
  scans the target pool only: record alive and active, object targetable, health > 0, tag not
  `Boxx`/`Boss`; aims at the origin's height clamped to the object's z range; no line of sight, no
  fog. Dash calls it at `0x8006EFA8` with Humn `+0x138` / `+0x118` (facing row), min dot 0.906
  (±25°), range 150, flag 1 (nearest wins). On the train level the troopers riding the cars,
  `TTrp` (`0x80112FB8`, 13 of them, health 0.5/0.25, z range 0..1.2), are outside the pool too.
- Target pool `0x80112838`: `+8` count, `+12` stride, `+16` base. Record: `+0x68` u16 flags
  (bit 2 active), `+0x84` alive, `+0x98` object pointer. Records are `Dfob` spawn definitions;
  `+0x98` stays 0 until the player is close enough for the enemy to spawn.
  Object: `+6` u16 (bit 2 targetable), `+0x60` health, `+0x68/+0x6C` z min/max, `+0x70` collider.
- Segment trace `0x800654A0` (returns hit distance, <0 clear): line of sight. Pass the
  player's collider (`+0x70`) to ignore it; hits on the target or its collider count as visible. Level geometry hit just short of the target's centre does hide it: an
  allowance of 4 units let an enemy standing right behind an Ord Mantell car wall be locked (1 unit is used now).
  The same call works as a floor probe (vertical ray from just above the feet down N units: hit
  = floor within N) and as a wall probe (horizontal ray; the hit object pointer is 0 for level
  geometry, otherwise the object itself — the target, an `EShd` shell, but also Dash: a ray
  from the camera eye to something behind a wall straight past him ends on his back, and the
  Ord Mantell train cars `Trai` are objects, not level geometry). Rays fanned around a direction find the nearest wall; its direction approximates
  the wall normal.
  It is one-sided: a ray starting below (or inside) a surface doesn't see it. A vertical ray from
  2 units above a floor point down to 2.5 below hits at 2.0. Standing on a rim, Dash's centre
  (`+0x50`) can already be past the floor polygon (his collision sphere holds him), so a probe
  straight under his last ground position misses the floor; start such probes a few units back.
- Every trace costs: a handful per frame on the ground raised the game's frame dt from ≈0.033 to
  ≈0.04 s under the harness interpreter (Dash covered more ground per video frame). Run probes
  only on events (e.g. once when airborne), never every frame. Measured (t_off.py base, play.st,
  interpreter): one trace per frame lengthened the frame from ≈29.5 to ≈32.1 ms; its length
  doesn't matter (2 or 13.5 units cost the same), the last argument does: 0 (level geometry
  only) ≈1.8 ms, 1 (objects too) ≈2.6 ms. The game's moves scale with the frame time, so a
  lighter or heavier patch changes jump arcs and paths (tests tuned to a marginal jump broke).
- Laser pool base pointer `0x80112E60`; new bolt direction at `+0xA0`.
- Dash's fire function `0x800737D8`: weapon = Humn `+0xB8` (0 laser, 1 pulse cannon, 3 seeker;
  C-up cycles), jump table `0x800EB908`. The weapon table `0x800E1338 + 12·id` (pickup bit, HUD icon element, shot
  cost) has an entry 6 (bit −1: always held, icon element 6, cost 0) that no weapon uses; the fire function does nothing
  with id 6 (the cost test fails, the id is past the jump table's 6 entries). The C-up cycle `0x8006E410(humn, 1)`
  (called at `0x80072798`) steps 0, 2, 1, 3, 5, 4, 0, skipping weapons with no ammo or pickup; any other id steps to 0.
  Set-weapon `0x8006E608(humn, id)` sets the icon and plays the switch click (0x15). The id is saved at a level's end
  and set again at the next one's start (`saber.c` puts its id 6 there). The laser is its one `jal 0x80031FE0`, at `0x80073F14` (a0 the direction
  matrix `sp + 0x64`, a1 the place `sp + 0x154`, a2 his sector `+0x70`, a3 5.0, then 200.0, 30.0 (the delay slot's
  `swc1`), the damage, flags 0x60, owner him; the matrix read again after it for the muzzle flash, `0x80073F40`); inside
  that spawn the patch's laser hook (`0x800321FC`, `lock.c` `ctl_laser`) re-aims every bolt of the player at the lock's
  target, so a direction changed at `0x80073F14` is undone there. A Blst bolt (owner `+0x64`, live `+0x60 & 0x10000`,
  place `+0x50`, velocity `+0x78..+0x80` at 200 u/s, the start `+0x94..+0x9C`): a bolt aimed at a Trop 9 units off hits
  it in the frame it appears (the Trop's damage and stagger in the same game frame as the spawn), so moving the
  target after the shot cannot make it miss; a line passing ~3.4 from a palace guard's place misses, ~2.8 still hits. Its flight (the Blst update `0x80033B7C`):
  straight, place += velocity `+0x78` × dt every update, the life `+0x68` counting down; no homing, the direction is
  never changed by it (the homing shots are `Misl`). The update (`local/work/saber/f_80033b7c.c`, 2026-11-16) only moves the bolt and runs its hit test
  (`0x800330F0`); it draws nothing: a bolt whose update is skipped stays drawn where it is, unmoved, its life not
  counted (the saber holds one at the blade that way). A palace guard's bolt (`palace.st`, 2026-11-15,
  `local/work/saber/parry_probe.py`, log `local/run/saber_parry/p1.log`): speed `+0x74` 200, length `+0x70` 30, life
  5.0 s, flags `0x10000`, spawned 3.75 above the shooter's feet and 2.7 ahead of it, its dir z −0.09..0 (it crosses
  0.9..3.75 above the feet of a player 37..77 away). Its place `+0x50` is the tail and its first update sweeps the
  whole length at once, so the head is 30 nearer than the place: from a guard 40 away the hit came 0.04 s after the
  bolt first showed (one or two game frames), from one 77 away 0.23 s. Other shots go along his flat body facing through the
  projectile spawn `0x80064584(kind, pos, ?, vel, flags, collider, shooter)` (class `Expl`, velocity
  `+0x70`, shooter `+0x88`; pulse = kind 6, ~36-46 units/s, lives ~0.7 s ≈ 30 units). Lifetime left
  (seconds) `+0x8C`: stored at `0x80064604` from the kind table (`0x800E0370`, 60 bytes a kind, `+0x18`)
  and again at `0x800646A0` (`+0x1C`) for kinds with flag `0x40` (pulse); when it runs out or the
  shot hits, flags `+0x62` change and it bursts for 0.2 s. Seekers (`Misl`, made by
  `0x8007E3A4`, shooter `+0xA4`) home on `+0x94` = target object + 0x20, `+0x98` above its position,
  picked with the game's auto-aim (which skips bosses). Bosses' real health: `+0x5C4` (750 full);
  hits add to `+0x748`, which the boss update `0x800465E0` takes off it. A pulse burst does less the
  further from the AT-ST's cockpit it goes off (~60 close and steep, ~5 on its front from far).
  IG-88's `+0x60` stayed +2.5 in every run of his AI measured 2026-11-09 (his rush included: it stops 10 units off);
  it was read negative with Dash put 3 units in front of him (`t_ig88near.py`) and at his death; dead = flag `0x20`
  at `+6`.
- **The `Expl` class in detail** (2026-11-10, `palace.st`, Dash's Stunner and Disruptor fired; `local/work/duel/`
  pseudo-C `f_80064584.c`, `f_8006604c.c`, `f_8006687c.c`, `f_80065660.c`): pool `*0x80112E90`, 60 × 300 B, 5 sprite
  types × 12 slots (the next slot of a type: s16 `0x8018DC80[type]`, taken unconditionally); `0x80064584(kind, pos,
  dir, vel, msgflags, sector, shooter)` returns no object (v0 is a colour record on its colour paths only): the
  spawned one is the slot that ring gave, checked by kind `+0x64` and sender `+0x88`. Kind table `0x800E0370` (0x3C a
  kind: `+0` sprite type, `+4` scale → `+0xD4`, `+0x10` drag, `+0x14` growth → `+0x80`, `+0x18` / `+0x1C` life →
  `+0x8C`, `+0x20` damage → `+0x84`, `+0x28` RGBA floats, `+0x38` flags → `+0x62`); the object's own fields are
  copied at the spawn, so one shot can be changed alone (a live shot's velocity `+0x70`, three floats, and its sender
  `+0x88` rewritten: it flies on the new course; a shot whose sender is the Humn bursts by itself (flag 0x40 contact)
  on touching a Trop, ~4.75 from its centre, where a Trop's shot passes through the Humn). Update `0x8006604C`, flags `+0x62`: 1 moves with `+0x70` and
  collides; 2 grows (`+0xD4 += +0xD4 · dt · +0x80`, cap 2000; the burst is the same object, flag 2 set); 0x40 on
  contact / life end switches to the grow phase; 4 sends `'shot'` (sender, message flags `+0x68`, damage) every frame
  to every object within `+0xD4 × 2.5` (≤ 100), 0x80 sends `'frez'` (no cap), 0x800 `'Whit'`; 8 hits the shooter too;
  0x10 needs line of sight; 0x20 faces the camera; 0x100 draws it in the RGBA bytes `+0x124..+0x127` (the colour record
  `+0x98` is one per slot; a tinted Disruptor shot keeps its tint through its burst); 0x4000 hides it. The area test
  `0x80065660`: horizontal distance < the object's radius `+0x60` + R, z inside its span; candidates the sector's
  objects, the Humn always, every `EShd`. Weapon ids (Humn `+0xB8`): 0 laser, 1 pulse, 2 flame, 3 seeker, 4 Stunner,
  The area send (`0x80065880`) reaches only objects linked in the floor-cell lists round the shot (cell `+0x98` its
  first object, object `+0xA0` the next): a dormant Trop with no cell (`+0xA4` 0, the cave's far wampas on
  `echo_cave.st`) takes nothing, even moved into reach. The Trop `'shot'` case (`0x800B58D0`) takes the damage unscaled
  (a wampa's 500 too); flag 0x100 caps it at 30 (2026-11-16).
  5 Disruptor (ammo floats `+0xC0 + 4·id`). The Stunner: kinds 1, 2, 3 (sprite type 4, the blue rings, flat: dir
  `0x800E1460`) at Dash, scales 0.1 / 0.2 / 0.3, growth 5.2/s, life 2.0 s; only kind 1 acts (`'frez'`, no damage).
  A ring's sprite is one quad, its drawn half-width 1.375 × scale. The Disruptor: kind 4 (sprite type 2, scale 0.4,
  flags `0x286D`, damage 20, life 2.2 s, then its sphere grows 2.5 s at 2.7/s to scale ~117; drawn half-width 1.365 ×
  scale) + kind 5 (visual); its speed `0x800EB970` (70). The life end (`0x8006604C` takes dt off `+0x8C`): at ≤ 0 with
  0x40 it clears 0x41, sets 2 and takes the grow phase's life from the kind's `+0x18` (a life written 0 bursts it on
  its next update, where it is); without 0x40 it ends the object (`0x80064C70`, state 0), no burst. `'Whit'` is sent
  only inside the `'shot'` area send: the update calls `0x80065880` only under flag 4, and `0x80065660` sends `'Whit'`
  to an object only on the path that sends it `'shot'`; with 0x800 alone nothing is white. **The white flash** is no sprite: the sphere's `'Whit'` to the
  Humn (`0x8007A364` → `0x8007AB38`) adds 1.85 · dt to the float `0x800E0DF4` (cap 0.9) each frame he is inside;
  `0x8006C758..` draws and decays it, and while ≥ 0.5 it hurts him `((difficulty − 1) · 22.5 + 5) · dt`
  (`0x8006C828`): the stock Disruptor's damage to Dash is all from the white. Humn's `'shot'` (`0x8007AD34`) skips the
  damage when the message flags carry 0x40 (Dash's own shots pass 0x60), else takes the damage × (0.7 + 0.4 ·
  (difficulty − 1)) × a random 0.7..1.0, at least 1 (`0x8007AE58`: even at damage 0). The player's screen effects
  are the hit tint (strength `0x800E0DF0`, colour s16 × 3 `0x8018DCF8`, written by the damage at each hit: flash 1
  orange 255 128 0, 2 green) and the white; nothing draws a hit on a body.
  More (2026-11-16, `f_80064584.c`, `f_8006604c.c`, the saber's flash): the spawn plays no sound; its placement
  (`0x80063E4C`) puts every object 0.05 (`0x800EB414`) from the given point toward the eye. A tinted object (0x100,
  without 0x400 / 0x1000) is drawn in `+0x124..+0x126` with the alpha `+0x127` times a factor from its life. Kind 4
  rewritten to flags 0x2122 (0x2000, tint, faces the camera, grows; nothing that moves, hurts, bursts or whitens),
  scale 0.4, growth 6.0, life 0.12 s: a disc in its tint that grows to 0.5 over ~4 VIs and ends with no burst.
- Display list head `0x80192F28` (next free Gfx); frame closed by `0x800BB630`.
- Perspective floats at `0x80192F14`: fovy (deg), aspect, near, far — 77/1.33/0.6/200 on foot in
  Echo Base, far 250 in Suprosa, 87.75/0.2/500 on the Mos Eisley swoop.
  Asteroid Field: 77.8/1.33/1/2000; Hoth (`lvl0.st`) 58.07/1.3333334/1/9000. Geometry past the far plane is cut off by it (a straight edge
  that moves with the camera), not faded: the fog has to close before it.
  Writing the fovy (`0x80192F14`) alone changes nothing on screen: set it through `0x800BA444` (debug entries
  below). Writing the near plane (`0x80192F1C`) changed nothing either.
- Fog: s16 start/end at `0x800E7AD8` / `0x800E7ADC` on the N64 depth scale 0..1000 (1000 = far
  plane), set by `0x800BAF78(min, max, r, g, b)`, emitted as `gSPFogPosition` at `0x800BADAC`;
  off when byte `0x800D2538` is set or max <= 0. Fog amount of a point at view depth d:
  z/w = (f+n)/(f−n) − 2fn/((f−n)·d), amount = ((z/w+1)·500 − min)/(max − min).
  Echo Base 996..1000 → fog from ~86 units, half at ~120, opaque at 200.
  A far end past the far plane (max 1010) keeps far objects lit: at 1000 a Star Destroyer ~1500 off drew
  black (Asteroid Field, far plane 6000). A start of 998 darkened the ships close by.
- Atmosphere is re-applied every frame (Gall `gall_tp5.st`: fog/ambient garbled in RAM are back
  1–2 frames later, `0x80192F38` = 0). Gall's values live in the level data as many identical
  records (`0x801DCAC8`, `0x801DCBFC`, … ~0x134 apart; likely one per area): bytes fog RGB
  162 162 188, 255 255 255, …, s16 996 (fog min) at +14, …, ambient 100 100 100 at +28, directional
  200 184 188 at +34, light direction floats from +40. 7 callers of the fog setter `0x800BAF78`
  (`0x800190CC` and `0x80092F04`/`0x8006E214` pass −1/−1 = fog off; `0x800A5E94` is a hard-coded
  set (996..1000, RGB 168 127 90) for some other level). Not yet traced which caller reads the records.
- Asteroid Chase's atmosphere is not in its blob: fog is off (max −1), set at load and never again;
  the lights are set every frame by the main program (`0x80092C80`, the ship's scene light: ambient
  50 67 80 as float constants, a flickering white directional) through `0x800BAFB4(1, ambient,
  directional, direction)`, which builds the RSP light struct at `0x800E7A90`. With `0x80192F38` set those calls
  are ignored and the light comes from the s16 values (`AMBIENT_RGB`/`LIGHT_RGB`).
  Checked without the flag: the fog holds, the light goes back to the space one.
  Left set after a custom view is done, `0x80192F38` makes the menus take the fog colour as their background:
  clear it, and put the saved fog and light back, once the custom view stops (only if you set it: the
  Cheats screen uses it too).
- Asteroid Chase's Chor route is in its blob: route struct at `0x801983A0` (+0x20 count 0x4F,
  nodes from +0x38: node 0 = (2000, 0, 0)). No word or lui/addiu pair in the blob points at it: the
  game reaches it some other way (an object/data list parsed at level start?), not traced yet.
  At run time the global `0x800D2600` points at the struct, and a few words in the level heap
  (`0x80190000..0x801A8000`) point at its first node. Which code fills `0x800D2600` at load is not traced.
  Route record (0x54 a node, record i at struct + 0x54·i): u32 next count, prev count, next indices ×4 at
  `+8`, prev indices ×4 at `+0x20`; node i's position (x, y, z floats) at struct + 0x54·i + 0x38, then an up
  vector. The game keeps no node count: the "count 0x4F" read at `+0x20` above is then node 0's prev link, the
  last node of an 80-node loop (inferred from this layout, not checked in RAM). An open route links its end back to node 0.
- Level id u16 `0x8013CE0E`. Profiles `0x8018BBF8` (4 × `0x7A`, level flags at `+0x60`).
- Debug flag: byte `0x800D098B` = 1 (GameShark `800D098B 0001`; the " Wampa  Stompa" name alone
  does nothing). The game's own way in (the pause branch of `0x800132A4`, `0x800159F4..0x80015C1C`; harness
  `local/work/debug_code.py`, 2026-10-25: on at VI ~2050 of the pause): on the pause screen (u32 `0x800DD2BC` 1)
  hold C-up, C-down, C-left, C-right, Z, L, R and D-left and the stick X half way (0.25 < |x| < 0.75); every 5 s
  of it (float `0x800D0930` += dt, ~500 VIs) is a step of u32 `0x800DD778` when the stick points the right way
  (right on an even count, left on an odd one: right, left, right, left), with a menu tick sound; D-up / D-down or
  the stick Y reset it below 4. While it is 4 the name matcher `0x80035530` returns 1 for " Wampa  Stompa" (and
  only then), or the level id is 0, and the pause sets u32 `0x800D0988` = 1 (the flag) and unpauses.
  Beside it, with D-left, C-down, C-right, C-left, L and R held on the pause screen, the stick Y (the accumulator
  float `0x800DD73C` past ±1) steps s16 `0x800E1B20` 0..2: the ship variant (Outrider / X-Wing / TIE, secret #2
  below, the Cheats Ship row's value), picked from the pause without the secret; the ship steering (`0x8009A30C`)
  turns it × 1 / 1.5 / 2 on a level with a sector record (Skyhook). Read from code, not tried. The list lives in the input function `0x800132AC` (block at `0x80013964`, run
  only while the flag is set, gameplay or pause, and then the pause handling is skipped): the
  cursor s16 `0x800D0990` moves with R / D-pad right (+1) and L / Z / D-pad left (−1), A / B /
  START runs the entry under it, **clears the flag** and calls `0x80026010(0)` (unpause). So the
  GameShark code, which rewrites the flag every frame, runs an entry on every jump, shot or pause.
  The current entry's name is drawn at the top (`0x80024860`). Names: pointer table `0x800D0994`
  (34 entries, values written into the strings by `sprintf`). Items: 0 Get all stuff,
  1 Invincibility, 2 Debug Display, 3 50 Lives, 4 Villains aren't sleepy, 5 Kill Dash,
  6 **Teleport** (cycles the sub-level's teleport points), 7 **Next Level** (next *sub-level*),
  8 This Level, 9 Prev Level, then Wall Ghost, Jump Power, Gravity, Texture/Lighting/Fog, vertFOV.
  Gotcha: the item under the cursor already runs when the pause screen opens, so with the
  cursor left on Next Level every pause skips a sub-level. Set the cursor first, and turn the
  flag on only around menu use. `harness/debugmenu.py` wraps this.
- What each debug entry does (jump table `0x800E91C0` for the run, `0x800E9324` for entries
  4..32, which are edited with the stick Y while selected through a shared accumulator
  `0x800D0A84`; `sote-patch/src/cheats.c` calls / writes the same things directly):
  0 `0x80072EB4(0,3)`, `0x800A9588(0,3)`, s16 `0x800E1B54` = 1000; 1 the same calls with 2 plus
  `0x800882CC(0,1)`, toggle u32 `0x800E1B2C`. Invincibility itself is per player object: mode 2
  XORs bit 0x8 of `+0x74` (HUD icon) and sets the float timer `+0xE4` to 100000 s (the pickup: 30;
  counts down at `0x80079990`; Humn and HumT alike), the bike has a global bit 0 at `0x800E18AC`.
  A new level's player object starts without them (the u32 stays set, so it is no state to show).
  Falls kill regardless; 2 s16 `0x800DA6D0` 0↔2; 3 u32 `0x800E0EB0` (lives)
  = 50; 4 u32 `0x800DD2C4`; 5 `0x800732D4(Humn,'It$',1,0)` / `0x800A97E8(HumT,'It$',0)`;
  6 `0x80074CDC(Humn)` / `0x800AAA34(HumT)` / `0x800290B0(Bike)`; 7/8/9 `0x800194DC(level ±1)`;
  10 bit 0 of `0x80112824` (clear = Wall Ghost on); 11/12 floats `0x800E0DC0` / `0x800E0DC4`
  (0.1..3; Jump Power and Gravity, both 1.0 by default. Jump Power scales the on-foot launch vz: x1 vz 15, apex 4.38
  above the floor, 76 VIs in the air; x1.4142 vz 21.2, apex 8.58; x2 vz 30, apex 16.2 (palace.st, a standing jump).
  The game keeps the value through This Level and a death, and a landing from 3.7x the apex costs no health); 13/14/15 bytes `0x800D2530` / `…34` / `…38` (set = off); 16 u32 `0x800D25DC` then
  `0x8001AAF0()`; 17 mode u32 `0x800D0A88` 0..4 → `0x8001AA74(w,h)`; 18/19/21 fovy/aspect/far
  (`0x80192F14/18/20`) via `0x800BA444(fovy, aspect, near, far)` (≤0 keeps a value; it ignores
  calls while u32 `0x80192F38` is set, so clear it around the call and set it after: that flag
  keeps the edited view/fog/light from being reset); 20 s16 `0x800D25BA + 10*s16(0x800D25B0)`;
  22 s16 fog min `0x800E7AD8` (10..996); 23–25 fog RGB s16 `0x80192F30..34` copied to
  `0x800E7AD0..D4`; 26–28 ambient RGB `0x800E7AAC..B0`; 29–31 directional RGB `0x800E7AB4..B8`;
  32 light direction s16 ×3 `0x800E7AC4` (length 120); 33 fovy 67.5, aspect 4/3, `0x80192F38` = 0.
  `0x80026130(tag, 0)` returns the first object of a class.
- Game Secrets: `0x800359F0(n)` says whether secret n is open (n 0: the pause entry; 1 Leebo
  Scanner, C-right 5 s on foot: top-down view with enemies and pickups; 2 C-right 5 s at the
  Skyhook station: fly an X-Wing, 5 s more a TIE Fighter; 3 crouch 15 s: ~30 s invincibility and
  all weapons; 4 friendly wampas: a wampa whose target is Dash (`Humn`) is set calm, `0x800B04B8(wampa, 0)`. Rewards for beating Easy / Medium / Hard / Jedi; callers
  `0x80071B50`, `0x80099C18`, `0x80072424`, `0x800B0680`/`0x800B2B90`/`0x800B3374`). Open for
  n < 4 (`0x80035A08 slti at, a0, 4`) when the profile name is a code (`0x80035530`, names at `0x800EA270`: "R Testers ROCK",
  "Credits", "Wolfy", "Wampa  Stompa", "WIPE ALL DATA") or on level 0; otherwise needs bit 0 of
  the profile byte `+9` (game beaten) and `n <= +7` (profiles `0x8018BBF8`, current one byte
  `+5`). So secret 4 never comes from a name: only from beating Jedi. Its three call sites are all
  `jal 0x800359F0` with `addiu a0, zero, 4` in the delay slot; each goes on (`beqz v0`) to a target-kind 2 check, the
  target `+0x9C` tagged `Humn`, then `0x800B04B8(wampa, 0)` (`0x800B3374` also needs the distance below 36.0,
  `0x8000DBB4`). Measured (`t_friendly.py`, `local/states/echo_cave.st`, Dash 8 units on the -x side of the first wampa
  `0x801C6614`): stock, the wampa walks (state 2) at VI ~69, attacks (3) from ~205 and Dash loses ~46 health at ~253;
  with the three sites answering 1 it is calmed to state 0 at VI ~131 and Dash loses nothing. On the +x side it never
  leaves state 0 in 900 VIs. The Cheats row Friendly Wampas answers yes at these three sites (2026-10-26).
  The pause entry (cursor 3) draws the four hints from `0x800DA6DC` over the list.
- Name-code flags (`0x80035530`, 2026-10-25, read from code): s16 `0x800DD76C` " Credits", `0x800DD770` " Wolfy",
  `0x800DD774` " Wampa  Stompa" (" R Testers ROCK" and " WIPE ALL DATA" set none of them). `0x800DD774` is read only
  by the creature camera (`0x80071A14`, `0x80071A64`) and the Hoth AT-ST mode (`0x8008ECE0`), both below. The matcher
  zeroes all three and re-sets them from the profile name, and every secret check (`0x800359F0`, its call at
  `0x800359F8`) runs it, so a one-shot write of a flag does not last (the Cheats row Creature Cam does the flag's effects
  itself instead).
  - " Credits": starting a game (`0x8003CD58`) loads level 31, the credits roll, instead of the chosen level. The
    roll (`0x8005F548(text, x, y)` per line; page counter s16 `0x800DEEF4`) then keeps the pages it skips otherwise
    (14: "Wampa supervision, training and care provided by Sam and Max", "No Wampas were actually harmed…",
    "Cliff, Wampa Zoologist"; 32..43: one-line gags, "Narf!", "Dry clean only", "Your mileage may vary", "…G'dnight
    Everybody") and adds a gag line under pages 15–18 ("My sister was bitten by a wampa once", "No, really!", "It was
    pining for the fjords!", "Actually they make good pets…"). In a menu (`0x8003771C`) the stick held up-right
    (both axes > 0.5) places HUD element 36 at (16, 40) (not looked at).
  - " Wolfy" (Mark Blattel, "Programmer/Lycanthrope" in the credits, which then adds "-For who could ever learn to
    love a beast?", `0x8005F7E8`): the ship steering `0x8009A30C` (Stft, every space level) takes its second
    scheme; the flag's only gameplay read is `0x8009A394 lui t9, 0x800E` / `0x8009A398 lh t9, -0x2890(t9)`, then
    `bnez t9, 0x8009A7FC` (`0x8009A394` is a branch target). Measured on Skyhook (`local/states/sky.st`, preset 0,
    `harness/steer_probe.py`, the read forced to 1, 60 VIs per phase, 2026-10-26): it is not a no-bank steering.
    Stick X +80 rolls the ship in place (roll +96°, yaw 0, no sideways step; the normal scheme turns: yaw -63°,
    bank +21°, 162 units right); stick Y then turns it in the rolled frame (yaw +75, roll -26; normal: pitch -79).
    Its buttons are binding slots `+0x0E` / `+0x0C` (sideways with a yaw term, `0x8009A8A8` / `0x8009A8F0`) and
    `+0x0A` / `+0x08` (pitch ±100, `0x8009A9C0` / `0x8009A9E4`): bound only in Traditional (preset 2); presets 0/1
    keep the D-pad in `+0x10..+0x16`, so there D-left does nothing under either scheme. With `PRESET=2` D-left
    60 VIs: 158 units left, roll -0.8 (normal scheme: a banked left turn, yaw +68, 165 left). Pad byte
    `0x8011309F` damps the pitch angle. No Cheats row for it (a roll on the stick is not a steering).
- **Creature camera ("Wampa  Stompa" name, traced 2026-10-17)**: not a secret slot. The name-code
  matcher (`0x80035530`) sets s16 `0x800DD774` = 1 for " Wampa  Stompa" (`0x800EA294`). Then on foot
  (`0x800719F8`) the camera binding (`+0x2E`, L / C-right in preset 0) held with binding `+0x0C`
  broadcasts message `'Wmp?'` to class `Trop` (`0x800262FC(class, &msg)`), with `+0x0E` `'Bls?'`;
  both clear u32 `0x800E5EF4` and set float `0x800E5EF8` (7.0 / 5.6, the 5.6 read from `0x800EB7F0`). The answering object (a wampa /
  a snowtrooper, both class `Trop`) is put in `0x800E5EF4` and the camera follows it from behind. Only the follow view
  (view 1; its camera code `0x8000A020` reads `0x800E5EF4`) shows it: the view button steps away (first person, drop,
  overhead sit at Dash) and back to view 1 finds the same creature again (`local/work/creat_views.py`, 2026-10-25,
  eye 8.7 from the wampa in view 1 before and after a full cycle). Who answers (Trop handler
  `0x800B58D0`, only while `0x800E5EF4` is 0, so the first in the pool): `'Wmp?'` a wampa (`+0x74 & 0xF` == 2) whose state
  `+0x78` is not 5/6; `'Bls?'` any other kind with `+0x74` bits `0x100` / `0x200` clear and `+0x78` not 5/6; nobody → it
  stays 0. The camera follows the object without the flag and without the binding held (the flag gates only the
  buttons): sent from the pause, the view stays on it (`t_wampa.py`). `local/states/echo_cave.st`'s pool (20 Trops, 0x120
  each) answers `'Wmp?'` with `0x801C6614` and `'Bls?'` with `0x801C5774` (`local/work/trop_pool.py`). Dash
  stays the player: the stick and the buttons still move and fire him; the creature does not move
  (harness: `local/work/wampa_ctl.py`, `local/states/echo_cave.st`, preset 2 where `+0x0C` / `+0x0E` are
  D-pad left / right; in preset 0 they are unbound). The followed wampa's own code (`0x800B24D4`)
  reads bindings `+0x08` / `+0x0A` / `+0x0C` / `+0x0E` and sets its state with `0x800B04B8(wampa, 2 / 3 /
  0)`, and its float `0x800E5EFC`. Every Trop (wampa or trooper) the camera follows is driven by the class think `0x800B1FA4` (the block after its
  `obj == 0x800E5EF4` test, `0x800B256C..0x800B25BC`, absolute loads `0x800E6810` / `…6814` / `…6816` / `…6812` + preset ×
  0x60): binding `+0x08`, `+0x0C` or `+0x0E` held → state 2 (walk), else `+0x0A` → state 3 (attack; float `0x800E5EFC`
  1..2 s between), else state 0; state 3 of the followed one aims 10 units ahead of it (+3.5 up), not at a target;
  `+0x0C` / `+0x0E` also turn it (`0x800B4FA8`, ±40). Tried on a trooper (kind 0, `echo_cave.st`, `creat_views.py
  WHO=trooper CTL=1`): D-up walks it ~8 units in 120 VIs, D-left / D-right ~63° per 30 VIs, D-down state 3. Tried 2026-10-25 (`local/work/creat_views.py` with `CTL=1`, Traditional preset,
  the wampa picked from Creature Cam): D-up state 2 (walks, ~3.5 units in 120 VIs there), D-left / D-right turn it
  ~55° per 30 VIs (state 2), D-down state 3, nothing held state 0; Dash stays put. A followed trooper's code checks
  `self == 0x800E5EF4` (`0x800B4F84`) and then turns on `+0x0E` / `+0x0C` (`0x800B4FA8`, ±40): D-left held 120 VIs
  turns it ~244° (`t_wampa.py trooper`, 2026-10-26). In presets 0/1, 4–7 the D-pad sits in `+0x10..+0x16`, which on
  foot are Dash's D-pad walk (`0x800716D4..0x8007170C`; on the speeder its view keys), and `+0x08..+0x0E` are 0;
  Traditional has it in `+0x08..+0x0E` and 0 in `+0x10..+0x16`. So the Cheats row Creature Cam gives the current
  preset Traditional's 8 D-pad slots while a creature is followed: the D-pad drives it in every preset, Dash stays
  put (moves 0.00 while the wampa turns ~214° in 120 VIs, `t_wampa.py cave`). The stick and B drive it as well: at
  `0x8001311C`, after the raw read, `cheats_pad` writes a stick push over 24 as D-up / D-left / D-right and B as
  D-down into the raw pad, then clears the stick, A and B (Dash stands; the decoded held word `0x801130AC` shows no
  B): stick up walks the wampa (state 2 on 116 of 120 VIs), stick right turns it ~242° in 120 VIs, B gives state 3
  (56 of 60 VIs); the trooper walks and attacks the same (`t_wampa.py`, 2026-10-26). The code sends only these two messages,
  both to `Trop`: nothing in it lets the player on foot follow or drive the Echo Base AT-ST (`Boss`, `ATST`).
  The game clears `0x800E5EF4` at a level load (`0x800190F4`) and when the on-foot player starts (`0x800704EC`,
  `0x80070904`). The camera binding with the flag on must be held over ~1.3 s (80 VIs; 60 is too short, stock ROM
  and patch alike, `wampa_ctl.py HOLDN=`): released sooner, it switches the camera view (to 0, first person) as
  without the flag, and the creature, still in `0x800E5EF4`, is not seen.
- **Hoth AT-ST mode (the same name flag, traced 2026-10-24, `local/work/hoth_atst.py`, stock ROM)**: in Battle of
  Hoth (sub-level id 3 on `lvl0.st`) the snowspeeder (`0x8008ECC4`) sets u32 `0x800DECE0` = 1 while `0x800DD774` is on and bindings `+0x3A`
  (C-right in every preset) and `+0x0C` are held together (not while the speeder is frozen in a wave's opening shot); nothing in the game clears it (`0x8008ED08` is its only store). Then ATST
  object `+4` == 0 (the first of class `ATST`, record `0x80112DD8`, 4 objects × 0x228) is driven by bindings `+0x0C` /
  `+0x0E` (turn left / right, its move method `0x8005736C` at `0x800576F0`: the walk goal ∓1000 to the side) and
  `+0x08` (its think `0x800566C0` at `0x800567E4`: pick a target, aim the head, fire on its own timer, and point
  Trak 0's `+0x8C` at it, distance `+0x98` 55: the behind view follows it, from behind and above (the cockpit-and-panel frames of the stock
  probe were the speeder's own cockpit view, which the combo's C-right, the speeder's view key `+0x3A`, had picked;
  that view is fixed to the speeder, so Trak 0's target does not show there)). In presets 0/1
  and 4–7 those slots are 0 (unbound); in Traditional (2/3) they are D-left, D-right, D-up, so the stock combo is
  "Wampa  Stompa", Traditional, C-right + D-left. It walks forward all the time (no stop, no speed control); D-up's
  target is the nearest of its own AI's (`0x80055490`), which can be the player's own speeder; the speeder flies on
  straight unattended and can be hit. It does nothing while that ATST is asleep (`+0x1C4` 0): Hoth's waves are the
  table at Spdr `+0x218` (wave 0 4 PRBT + 3 Spdr, wave 1 2 ATST + 3 Spdr, waves 2–3 AT-ATs), index u32 `0x800E183C`,
  alive count `0x800E1818`; zeroed on `lvl0.st`, wave 1 starts ~760 VIs later with a shot of it (the speeder frozen
  another ~800 VIs).
  Driven without the name (2026-10-25, the Cheats row Creature Cam): the mode 1 with Traditional's D-pad written into
  the Standard preset turns ATST 0 ~200° in 240 VIs of D-left, the speeder view untouched. Writing the mode 0 gives it
  back to its AI; Trak 0's `+0x8C` stays on the ATST until it is written back to the speeder (`lvl0.st`: the first
  `Spdr`, `0x801EBA3C`, the target before), which brings the speeder's camera back (`+0x98` left as the ATST wrote it).
  The level start (`0x8008D1CC`) sets that target to `find('Spdr', 1)` (the object with `+4` == 1; `0x80026130`'s
  second argument is that index).
  Its walk is the animation's root motion (move method `0x8005736C`: the step = the root node's change × 2.5), not
  its state: states 1 and 2 walk alike (`local/work/atst_stop.py`, 2026-10-26, ~8 units per 30 VIs either way). Its
  animations (`0x800DEDAC`, 36 bytes each): 0–3 `chkn` walks (11–14 long), 4 `cded` (death), 5 `chkn` length 0; no
  stand. The animation player at ATST `+0x108` (advanced by `0x800170F0`) takes dt 0 while bit 31 of its word 0 is
  set and keeps the bit: set, the AT-ST stands still (0.00 in 240 VIs) with the camera on it; cleared, it walks again.
  Frozen it still turns (binding `+0x0C`/`+0x0E` or the walk goal: ~210° in 240 VIs, its position `+8` unchanged; `+0x158`
  is a point ~4 units off the pivot that circles it as it turns, so it is not the position) and still fires: the D-up
  branch shoots (`0x8005635c`) whenever its fire timer `+0x100` (dt off every frame) is below 0 and sets it to 0.25 or
  0.5 at random (3 shots in 120 VIs held); `+0x1CC` counts only state 4's own fire (the AI's, reset past 8), and the
  branch forces state 2, so it stays 0 under the mode (`t_wampa.py hoth`, 2026-10-26).
  The turn is its yaw `+0x14` (degrees) stepped by 2 a frame toward the walk goal (D-left raises it); the move method
  rebuilds the matrix from `+8` / `+0x14`, so a yaw added before the game's update holds: 2.0 × x / 72 more a frame
  turns it ~372° in 240 VIs of stick x +60 (the game's alone ~206°), still standing (0.00; `local/work/atst_turn.py`,
  2026-10-27).
  The walk's clock (2026-10-26, `local/work/atst_probe2.py`): `d = *(ATST + 0x108 + 0x14)`, float time `d + 4` (~0.2 a
  VI, two steps of 20 each, ~0..40 then back), `d + 8` 20.0, `d + 12` 1.0 (not a rate: 0.5 there walked further, 56.7 vs
  34.1 in 120 VIs). Frozen at time mod 20 ≈ 5 both legs are straight with the feet on the ground (the stance); other
  phases have a knee bent or a foot up. Let go mid-step, walking on at the game's speed until time mod 20 is within
  5.0 ± 0.3 and freezing there stops it in the stance (2..94 VIs after the let-go measured, ~100 at worst at ~0.2 a VI;
  `t_wampa.py hoth`, 2026-10-27).
  Trak 0 is a rig with no angle fields of its own (`0x800A18B8`, decompiled 2026-10-27): each frame it reads its
  position and angles back from its matrix `+0x20` (`0x8000F0C8`), aims at the target's matrix translation +
  `+0x90 / +0x94 / +0x98`, wanted yaw = `0x8000D750(-dx, dy)` (atan2 in degrees) of the direction to that point,
  pitch = asin(dz), roll the target's; angular velocity `+0x80..+0x88` = 4 × (wanted − current); then the matrix is
  rebuilt (`0x8000F624(trak + 0x20, {x, y, z, yaw, pitch, roll})`) and the rig moves along its forward (row 1) at
  speed `+0x64`, kept toward the distance `+0x60` (100, set by the AT-ST's move method every frame). It returns early
  when the direction is shorter than `0x800ECC68` (the rig on the point). On Hoth camera entry 6 (`0x8019A8BC`) has
  source `+8` = Trak 0 + 0x20 and offsets `+0x54..+0x5C` 0, so the eye is the rig's translation: on the AT-ST
  (~1 off) until it walks, then trailing ~85..100 behind; a turn in place leaves it where it is, and turning the rig
  alone swings the view about the eye, not round the AT-ST. Placed each frame before the update at the aim − facing
  × 100, yawed toward the aim, angular velocity 0, the step keeps it there: the angle between (AT-ST − eye) and the
  facing 0.0 and the eye 100.0 from the aim in a turn in place and while walking (`local/work/atst_cam2.py` MODE=3
  D9=1). A rig placed before the update off that leash or not facing the aim is moved by the update: with the eye
  higher and looking ahead of the AT-ST it trailed its aim by 4-6 units in a turn (the update's speed `+0x64` read
  210-299 after the frame although zeroed before it), and at the start of B, where the think zeroes `+0x90 / +0x94`
  after any earlier write (the aim then on the head point, `+0x98` 55), one update threw it 40 units forward (speed
  2158.85) or, with the speed zeroed, to the leash 100 from the head point for 2 frames (2026-10-28). Placed after
  the update instead, nothing moves it: the Creature Cam row swaps Trak's class update method (`0x80112EF8 + 0x1C`)
  for a wrapper (cheats.c `atst_trak`, the Gall Run's way, gall_cam.c `trak_update`) that calls the game's and then
  places the rig, the eye's ground yaw swung behind the facing by Dash's rule (below, *Follow camera placement*;
  2026-10-28, the user: the leash alone did not follow a turn): 120 behind the head point (ATST `+0x50..+0x58`, 55 up)
  and 45 above it, looking 15° down at the point 48 ahead of it (Hoth's fovy `0x80192F14` 58.07: the head point at
  screen y 141 of 240, the feet at 220). Measured (`t_wampa.py hoth`): the eye 128.2 from the head point and the
  pitch 15.0 in every frame, B's start and a 240-VI turn in place included; at most 3.8° off behind it in the turn,
  1.6° 30 VIs after, 0.1° walking. The speeder flown unattended meanwhile (no stick) is shot at and sinks: health `+0x204`
  110 → 86 and height 114 → 93 in 1500 VIs on `lvl0.st`; its health and position `+8` / `+0x50` written back each
  frame keep it whole and in place (0.000 off over 2805 VIs) and it flies on (~148 in 120 VIs) once let go.
  The camera part of the D-up branch (`harness/decomp.py 800566c0`, guards: the mode, ATST `+4` 0, `+6` & 0x20 clear,
  state `+0x1C4` 1..4, binding `+0x08` held) is three Trak 0 writes: `+0x8C` = the ATST, `+0x90` = `+0x94` = 0,
  `+0x98` = 55.0, plus float `0x800DEE28` = 18.0 (no reader of it found in `main.bin`); the call
  `0x80017764(3, 0, obj + 0x1D8, obj + 0x108, 0x800DEDAC)` beside them is an animation-table pick (animation 3 on its
  model), not the camera. Doing those writes without the button (the Creature Cam row, 2026-10-25) puts the behind view on
  ATST 0 1 VI after it wakes; done during wave 1's opening shot it leaves that shot as the game shows it (the shot
  is not Trak 0's).
  What else the flag changes (read from code, 2026-10-25):
  - ATST 0's target pick (`0x80055490`): any of `Spdr PRBT ATST ATAT rbgn` (`0x800DED08`) within 800, not only
    `Spdr`; its bolts (`0x8005635C`) do 10× damage. It runs each frame binding `+0x08` (D-up) is held and in states
    1..4 every 4th frame; `0x80004EA8` walks the list to its first 0 tag and writes the slot (`+0x16C`) only on a
    find (no match keeps the old target), skipping the picker itself. The head aims at `+0x16C` (`0x80055F34`, with
    a `+30` / `+70` height for an ATST / ATAT; `+0x174` the cos to it, `+0x184` the distance) and resets to its own
    forward with it 0. The Creature Cam's AT-ST rewrites the list while it drives (its first tag 0 without Z, `PRBT
    ATST ATAT 0` with Z) and puts it back after; the pick's cone is cos 0.5 off the facing (2026-10-27, wave 1's
    probe droids ~150° off it found nothing until it turned toward them).
  - The `shot` handlers of ATST (`0x80057FA8`), PRBT (`0x800845F8`) and ATAT (`0x800B8610`) take a bolt without bit
    `0x40` (only then: without the flag those bolts are ignored), so AT-ATs die to fire: health `+0x1FC` (1000;
    400 / 1250 by difficulty), a hit on `+0x1E8` full, elsewhere a fifth; ≤ 0 → state 7. The tow cable (`Trip`)
    works as before.
  - The speeder's D-pad bindings (`+0x08..+0x0E`, `0x80090080`, `0x800900DC`, `0x80090504`, `0x80090530`) stop
    steering it; the stick still does.
    One more read of `+0x0C` / `+0x0E` (`0x800902F8`, ungated) is only in the speeder's state `+0x1F0` 5 (its roll
    of +10 a frame, with the stick X too): there they turn it ±4 a frame, as in Traditional.
  - Not changed: the other ATSTs, PRBT and ATAT aim at `Spdr` only (`0x80004C54` with `'Spdr'`), so nothing aims at
    ATST 0. A wave start (`0x8008CDE4`, also at level start `0x8008CFA0`) sends `zzzz` (state 0) to every ATST,
    then `wake` (a spawn record's position, state 2) to the wave's: ATST 0 is put to sleep at wave 2 and is one of
    wave 1's two (its death counts in `0x800E1818`).
  - Where Hoth's code takes `Spdr` for the player (the `'Spdr'` constant outside the speeder's own code, 27 sites,
    2026-10-25). `0x80026130(tag, n)` returns the object of a class whose `+4` is n (`'Spdr'`, 0: the player's
    speeder); `0x800261C4(tag)` a class's count; `0x80004C54(slot, self, pos, tag, range, cos)` picks the nearest of
    one class into `slot` (`0x80004EA8` the same over a tag list):
    - the player by index (`0x80026130('Spdr', 0)`): ATST think `0x8005724C` (its kick `0x800263EC` on the player near
      it), PRBT think `0x80083DB8` (its target), ATAT think `0x800B7E58`;
    - the first speeder (`0x8002620C('Spdr', …)`): ATST move `0x8005760C`, ATST `shot` `0x80058124`, PRBT
      `0x800834A0` and `shot` `0x800848A0`, rbgn `0x80086444`, `0x800864AC`, ATAT `shot` `0x800B8900` (in the `shot`
      handlers: the hit sound when the shooter is the player);
    - a target of class `Spdr` (`0x80004C54`): ATST `0x80055568`, ATAT `0x800B64BC`;
    - `== 'Spdr'` on another object's tag: ATST aim lead `0x80055FB4`, ATST move `0x80057C64`, PRBT `0x80082074`,
      ATAT `0x800B6EAC`, the `plow` (ram) cases ATST `0x80058238`, PRBT `0x80084B0C`, ATAT `0x800B8A14`;
    - `0x8001FCAC` (7 sites, a class switch on `s5`, with `0x800261C4`): not traced (the HUD radar is the guess);
    - `0x80091F48`: the speeder's own message handler.
- **Native ship swap (secret #2, traced 2026-10-11)**: the player ship is not swapped by changing model
  pointers — it is one model node holding three variants, picked by a selector. The Stft model root
  (Skyhook: `0x801A3018`) has one group child w0 `0x5065FF00` (the variant group, 3 children):
  child 0 Outrider (group `0x5064FF00`, hull mesh 21 parts), child 1 X-Wing (`0x5064FF60`, mesh 29
  parts), child 2 TIE Fighter (`0x5064FF60`, mesh 9 parts). The global ship counter s16 `0x800E1B20`
  (0/1/2) is the selector; the Stft draw method (`0x8009C318`) writes it into the variant group's
  `+0x14` every frame (`0x8009C438`: if the root's child 0 has w0 `0x5065`, `0x8000FFB8(child,
  0x800E1B20)` = `child+0x14`). Trigger (gated by `0x800359F0(2)`): `0x80099C18` holds the bound
  button (slot `0x52` of the binding table `0x800E6808`) against the held-buttons word `0x801130AC`,
  accumulates the time in float `0x8018DCD8`, and at 5 s does `0x800E1B20 = (0x800E1B20+1) % 3`, a
  sound, and `0x8000952C(5, 0.5)` (switch the active camera entry to 5). The counter also drives
  per-variant tweaks in the Stft code: gun/laser spawn points (`0x800973E8` X-Wing,
  `0x80097AD8`/`0x80097B1C` X-Wing/TIE) and a scale factor (`0x8009A358`: X-Wing 1.5, `0x8009A37C`:
  TIE 2.0). So the three variants are hardcoded (`== 1`/`== 2` branches); a 4th ship is not a one-line change.
  More (2026-10-17): the swap's sound is `0x80007340(0x41, 4, 0.2f, 0x7530, 0)`, the camera blend
  `0x8000952C(5, 0.5f)` (it also works when called from the pause screen: Cheats Ship row). The draw
  copies the counter only while u32 `0x800D2400` (Skyhook's sector record) is set. The ship's init
  writes 0 at `0x80097E34` (its only other writer), so every start or restart is the Outrider. The
  variant group is Skyhook's only: Stft `+0xB4` model root, child 0 `*(*(root + 0x10))` with u16 `0x5065`;
  in Asteroid Field (`ast.st`) and Station Chase (`chase.st`) child 0 is the plain `0x5064` Outrider.
  `sote-patch/src/cheats.c` (Ship row) sets the counter from the pause menu.
- Pause screen: u32 `0x800DD2BC` = 1 while paused (`0x80026124` returns it, `0x80026010(0)`
  resumes, `(-1)` toggles; START pauses at `0x800164F8`). List shown u32 `0x800D0948` (0 hides it
  and the game then ignores pause input), cursor s16 `0x800D0944` (0 Resume, 1 Options, 2 Quit,
  3 Game Secrets when `0x800359F0(0)`), quit confirmation u32 `0x800D094C` (1 while "Are you sure you want to quit?" is up; the
  pause cursor then 1 No (default), 2 Yes; No goes back to the list on Resume; `0x800DD2BC` stays 1
  throughout: `local/work/quit_no.py`), Options screen u32
  `0x800DD5E4`, START latch byte `0x800D0A78`. START path (`0x800164C4..0x8001657C`): skipped while s16
  `0x800DD2D0` (a held line) ≠ 0; then, not paused and u32 `0x800DD2B0` = 2: START's pad byte set and the latch 0
  → latch 1, `0x80026010(-1)`, menu sounds; START up → latch 0. The latch is untouched during a held line, so a
  START still held after the line is let go pauses (measured 2026-10-16, `local/work/s2s5_probe.py MODE=a`: START
  4 frames on a held line: the line let go on its first frame, the latch 0, the pad byte 1 two frames later, `PAUSED`
  1 four frames after the release; a plain START press: pad byte 1 the next frame, `PAUSED` 1 three frames after
  the press). With a held line, START alone lets the line go and does not pause; pausing over it: clear the hold,
  latch 1, `0x80026010(-1)` from the pad hook (`PAUSED` 1 within 3 frames; the line's text stays up and the hold
  can be put back as the pause ends: Gall Run, `local/work/pause_probe.py`, 2026-10-17). The A that picks Resume acts in the game on the frame the pause ends (its pad read is taken while
  still paused): in the Gall Run's stage 1 it starts the switch to the gun's entry 5 (0.5 s blend) on
  that frame, a step in the view (2026-10-16, `local/work/quit_no.py CAM=1 PLAIN=1`). Items: pointer table `0x800D0964`, drawn at x 160,
  y 96 + 18·i (selected one flickers, `0x800B8BE0` random). Menu sound: `0x80007340(0x63, 6,
  0x3EC00000, 0x6590, 0)` and the same with `0x65`.
- Pad bytes at `0x80113098 + n` (1 while held): 4 C-right, 5 C-left, 6 C-down, 7 C-up, 8 R, 9 L,
  0xC D-right, 0xD D-left, 0xE D-down, 0xF D-up, 0x10 START, 0x11 Z, 0x12 B, 0x13 A.
- Text: `0x80024AE8(r, g, b, a)` color, `0x80024ACC(x, y)` position (320×240), `0x80025228(ctx,
  str)` draw; `~s` small font, `~c` centered on x. `0x800C0240` is `sprintf` (`%d`, `%s`, `%.3f`).
- Sub-level ids index a 32-entry dev list at ROM `0x2070` (RAM `0x80001470`, 64 bytes per name) (build tag `v31Oct96.1141` at `0x2870`);
  the PC version has one `SDATA/DATAnn.DLL` per entry, same order (`GetLevelStub` + the name):
  0 Cut 00 (Intro), 1 Cut 01 (Hoth), 2 Main Menu, 3 1. Battle on Hoth, 4/5 2a/2b Hoth Base,
  6 3. Asteroid Chase, 7 Cut 03 (Train), 8 4a. Train, 9 Cut 04 (IG 88), 10 4b. Junk Heap,
  11 Cut 05 (Gorge), 12 End Game (Cut 02), 13 Cut 06 (Gorge Trans), 14/15 6a/6b Gall Cliff Base,
  16 Cut 07 (Bike Intro), 17 7. Speeder Bike Chase, 18 Cut 08 (Bike End), 19 Cut 09 (Freighter),
  20–22 9a–9c Space Freighter, 23 Cut 10 (Throne), 24 Cut 11 (Sewer), 25 10. Sewer,
  26/27 11a/11b Xizor Palace, 28 Cut 12 (Battle), 29 12. Station Chase, 30 13. Skyhook Battle,
  31 Cut 13 (Finale). Level numbers **5 and 8 are missing**. Slot 12 sits between the two Gorge
  cutscenes, where level 5 would be, and now holds "End Game" (back to the title). Cut 05 shows
  the Outrider flying over the Gall gorge, Dash's three held lines (IG-88 said Fett is in the Zhar system, on
  the Imperial moon base Gall; hide the ship in Smuggler's Gorge; "Then I'll have to sneak in the hard way...");
  Cut 06 his "So far so good, Leebo. Looks like I go in on foot from here." and the observation tower line
  (the text in each blob, `level_blob.py` ids 11, 13).
  Cut 11 (24, read 2026-11-05 on the stock ROM, `local/work/cut_look.py ID=24`): the "Part IV: Lair of the Dark Prince"
  crawl, the Falcon and the Outrider flying into an Imperial City sewer tunnel and setting down, then a picture of
  Chewbacca, Lando, Luke and Dash by the Falcon with Luke's "These sewer tunnels lead to Xizor's palace. Lando, Chewie
  and I will search for Leia." (no line table at `*(0x8013CE30) + 0x14`; the scene holds on the picture, not ended
  within 100 s with no input). Luke appears in the game only as 2D pictures found so far (Cut 11, the last scene,
  Skyhook's radio portrait); the sewer and palace levels (25–27) have no class of their own for the palace guards:
  their people are `Trop` (23 / 26 / 17 at the start), with `Patr`, `Gun!`, one `Boss` in 27 (`CLASSES=600`). The kind (`+0x74 & 0xF`) picks the model (sub-level 26, `local/work/lvl26.st`, the creature camera on each, 2026-11-05):
  kind 0 is the palace guard: health 50 the red-armoured one, 30 the same model in green; kind 3 a grey walker droid, kind 4 a brown droid (`0x13` grey, `0x40` / `0x50` the big walker in 27). Being Trops, every one answers the creature camera and the Cheats row Creature Cam's stick drive. A Trop's current animation block is at `+0xCC` (= `+0xD0` when not blending; its animation state is `+0xB8`, see *Animation format, exactly*), `+0x70` points to a `Dfob`; its draw matrix `+0xDC` is Rz(180) of its heading `+0x14` (a heading set by hand needs the rows `+0x20`, `+0x30` written with it). The guard's blocks: `trSt`, `trOu`, `trSh`, `trTr`, `trDi` (17 bones); the droids' `a1St` / `a2St` (15). Bone indices are per block (Dash's `fall` lists his nodes in another order than `trot`): map bones by node address. The guard's skeleton is Dash's less the neck: root (scale ≈ 0.215) → pelvis → legs 3 + 3 (local x along the limb, as Dash's, with the same sign: a limb's child translation `+0x38` lies along the same local axis on both), spine → chest → arms 3 + 3 and the head; Dash's model frame is ≈ 4.1 times the guard's, and the two models' local frames agree (pelvis, spine, chest within 16° of each other in `palace.st`). Its limb meshes are variant groups (`w0` `0x5065ff00`, `+0xC` count 2, `+0x10` a list of type-3 mesh nodes, `+0x14` the drawn one): variant 0 the detailed near mesh, 1 the far one, `+0x14` left at whichever the last guard drawn needed. The spine mesh (`0x3064ff60`, the grey belt under the armour) is plain; its texture DL sets segment 4 itself (`MOVEWORD 0xBC001006`, then a `G_DL` into it). The right hand's mesh is the guard's rifle. Every Trop has a bone node tree of its own (2026-11-07, `palace.st`: Dfob `+0x84` roots `0x801ED7C8` Trop 0, `0x801EEA58` Trop 4, `0x801F0708` Trop 10, `0x801F1098` Trop 12; bone nodes `w0 >> 28 == 0xD`), so swapping one Trop's child lists changes that one only. Its tree's bone nodes depth first in child-list order are 19: the root (`0xD065…`), its one child (`0xD064…`), then the 17 bones, `trSt` index i = tree node 18 − i (Trop 0's `trSt` entries `+0x38 + 0xA0·i + 0x08` are exactly nodes 18..2; Trops 4, 10, 12 have the same child counts in order: 1,1,1,4,2,4,2,2,1,2,2,1,1,2,2,1,2,2,1). Only Trop 0's `+0xCC` is the `trSt` block itself; the others' is an instance record whose `+0x1C` points into the shared block. The game does not rewrite a Trop's bone lists while it lives (Trops 0 and 10, 600 VIs, Trop 0 walking 46 units); the mesh variant pointer `+0x14` it sets lives on the shared mesh nodes. This Level puts the Trops and their trees back at the same addresses with the game's lists (`t_guri.py`). The Trop class record is `0x80112D78` on every level read (`palace.st`, `echo_cave.st`, `play.st`: `+8` count 26 / 20 / 37, `+0xC` size `0x120`, `+0x10` pool). Guri (`guri.c`) is drawn on one Trop this way.
  Dash drawn as the guard (the Cheats row Look, `guard.c`, its meshes from `harness/guard_asset.py`): each guard mesh (the near variant) baked into the matched Dash bone's local frame with no pose (a bake from posed world frames froze the pose difference into the arms as spikes), Dash's own meshes left out of his node lists but the weapon (his jetpack, bone 9's second mesh, would show as a grey and brown back). He stands, runs, turns and fires in the red armour with his own animations.
  Level 8 (between Bike End and Freighter) has no slot. PC slots 11–13 are small code-only DLLs;
  nothing of either level's data was found. Loading a slot: write the id, then debug This Level
  (item 8). After a cutscene the game moves on to the next slot by itself.
- **Sub-level data** (2026-10-08): one compressed blob per sub-level. Tables in the boot segment
  (uncompressed in ROM: RAM − `0x80000400` + `0x1000`), base `0x80001330`: `+0x40 + 4·id` the
  blob's ROM offset (blobs back to back, `0x67DCB0`…), `+0xC0 + 4·id` flag byte (1 = compressed) and
  ROM length (24 bits), `+0x140 + 64·id` the dev name. A blob starts with its unpacked size (Asteroid
  Chase 0x209E0, Gall 6a 0xE6C60), then the stream (same first bytes as the main executable's).
  `0x800194DC(id)` (−1 = next; ≥ 32 → 2, Main Menu; table entry 0 → 0) queues it (`0x800D255C`,
  state byte `0x800D2558` = 2); `0x80019294` loads: `0x800196A4(rom, len, flag, 0x80196950, 4 MB)`
  unpacks it right after the main program, then `0x80019B14(0, −1, 0x80196950, 1)`. The 7 users
  of the table: `0x8000669C`, `0x800181DC`, `0x800192E8`, `0x800193DC`, `0x8001944C`, `0x800194AC`,
  `0x80019518`. Only five index by the id (`0x80001198`, `0x8000669C` read the header, `0x800181DC` the header and
  flags[0]); the fixed `+0x40/+0xC0/+0x140` spacing holds exactly 32 entries.
  The dev name is not only a label: `0x800193A4` passes it (`0x8001944C`) to `0x80006CB0(name)`, which picks the
  level's music track (`0x800D075C`/`0x800D075E`) and volume (`0x800D0760`) by comparing the name's first word
  ("3. A" for Asteroid Field → track 51; no match → −1, no music).
  - **Moved (gallrun builds):** the three arrays live in `g_levels` (`gallrun.c`,
    the Gall area) with 34 entries: roms `+0x40`, flags `+0xC8`, names `+0x150` (`0x9D0` bytes; header copied too);
    `gallrun_boot()` (called from `_start`) copies the stock 32, entry 32 is the Gall Run's blob (flag 0, its length,
    "Gall Run"), entry 33 the duel's (`duel_level.bin`, flag 0, "11a. Duel: Guri (bonus)": the name's first word keeps
    sub-level 26's music, track 0x7D; empty without the feature). `hooks.S` `hook_table` rewrites 15 words: the bases
    (`lui`/`addiu` at `0x800192DC`/`0x800192E8`, `0x800193CC`/`0x800193DC` (`lw t8, roms`), `0x80019448`/`0x8001944C`,
    `0x800194A8`/`0x800194AC`, `0x8001950C`/`0x80019518`), the offsets `0xC0 → 0xC8` (`0x80019300`, `0x80019314`) and
    `0x140 → 0x150` (`0x80019454`, `0x800194C8`), the queue's bound `slti 0x20 → 0x21` (`0x80019504`): 33 is past it, so
    our queue (`own_queue`, and the game's restart through `tramp_level_queue`) queues 32 and 33 itself, and the stock
    bound still sends 34 (the duel's Stage Complete: id + 1) to the Main Menu. The tables at `0x80001330`
    stay as they are and are no longer read by the game in such a build.
- **Level-index table** `0x800DD77C` (u8 [32], by sub-level id): `0x80035D50` returns `0x800DD77C[LEVEL_ID]`
  (Asteroid Field's 6 → 2); its callers are the end-screen stats `0x800216DC`, `0x800364CC`, the save stats
  `0x80035DA8` and the level starts `0x8008CFF4`, `0x80097C64`, `0x800709E8`, `0x800A7F5C`, which write the save's
  current-level byte (`0x8018BC00 + slot·0x7A`).
  - In gallrun builds it is `g_level_index` (34 bytes; [33] = 8, sub-level 26's): the `lui` at `0x80035D64` and the `lbu` at `0x80035D74`
    point at it.
- **Level zones and the vertex rebase** (2026-10-28, Gall 6b / Gall 14): a level's meshes sit in *zone records*
  (95 in Gall 6b, 72 in Gall 14): `+0x10` flags (`0x40000000` = visible from the current zone), `+0x14` s16 (x, y) =
  the base its vertex records are relative to, `+0x18` a 0-ended type list, `+0x38` the matching pointers (type 9 =
  the zone's level mesh; types 1 and 3 = meshes such as Slave I's shaft, `slave_pad.py` `PAD`, sharing its vertex
  records). The current base is the s16 pair `0x800E7C48` (the drawn level's transform node `0x8020DDF8` has the
  same translation), the current zone `0x800D08D8`. When the player's zone changes, `0x8000C4D0` turns the old
  zone's visible list off and the new one's on, and for each zone in it calls `0x800BCD80(mesh, zone + 0x14)`: if the
  zone's base is not the current one, it adds (base − current) · 8 to x and y of the mesh's 8 box corners
  (`mesh + 0x14`) and of every part's vertex records (from `*(DL + 4)` up to the part's DL), then stores the current
  base in the zone. So world (x, y) = vertex / 8 + zone base (z untouched), and a zone's records keep the base of the
  last time it was visible: a RAM dump's raw vertices depend on the path the player took (a debug-menu teleport
  detour leaves whole 100-unit shifts). Right after a load every zone is at (0, 0) and the records equal the
  unpacked blob. Part boxes, DLs and node transforms are not touched.
  More of a zone record (2026-11-10, sub-level 26's round room, `local/work/duel/arena/` probes): `+0x04..+0x0C` its
  centre, `+0xB8` the next zone, `+0xBC` a 0-ended **neighbour list** (zone ids), then the type-7 list. Types read
  through `0x80017A78`: 5 the ceiling z (float: what a jump stops under), 2 the floor z, 9 the draw mesh node, 1 the
  floor collision tree, 3 the wall collision tree, 7 the **visible-zone list** (what `0x8000C4D0` shows on entering),
  29..31 (`0x1D..0x1F`) and 32 the stage end's carry-over offset and next zone (with flags `0x400` portal / `0x1000`
  stage end, *Stage Complete*), 20 an `'Entr'` message (flag `0x10`), 34 = 0x16 on 80 of 154 zones (likely the
  atmosphere set), 28 a word not read. In the blob the zone words are offsets or `0x05000000 | n` (mesh node n of the
  table at header `+0x24`, 0x18 a node), relocated at load. The player's floor search `0x80003EC0` and the walls' push
  `0x8000D108` (the player's zone's type 3 and 8 trees; with flag 1 also its neighbours') walk the collision trees to
  `0x3064` leaves of parts (box, count, kind, u16 indices into the one vertex pool `*0x8013CE28`, world units, no
  rebase: *Player ship* below); a part's float box gates its triangles. The zone search `0x8000C104` takes, over all
  zones, the one whose floor (type 1) under the point is nearest the point's z: a zone with no floor parts is never
  entered. Measured on RAM: pool vertices moved with the boxes grown move where the player walks and stops; the pool
  copied to expansion RAM with `*0x8013CE28` repointed holds (the pointer is read on every use); the draw is separate
  data (moved collision alone leaves him walking in the fog past the drawn walls).
- **Class headers in a sub-level blob and the level's class list** (2026-11-11, sub-level 26's blob under id 33;
  `local/game/duel_level_stock.bin`, RAM on 33). Each class in the blob has a header (0x28: tag, flags, count, size,
  pool offset, `+0x14` create, `+0x18..+0x24` the four methods, 0 in the blob), its instances after it (Trop: header
  `0x801B8748`, flags 0x43, 26 × 0x120, pool `0x801B8770`). Relocated words are offsets from the region start
  (`0x80199324` on 26; the bitmap at blob header `+0x3C`, relocator `0x8001866C`; the top byte the type, type 1 a
  node of the table at header `+0x14`, n × 0x48); the header's words `+0x10..+0x24` are marked in the bitmap, so an
  absolute method address written there in the blob gets the base added unless its bit is cleared. The level's class
  list (41 entries, null-ended, `0x8019A820` on 26, straight before Dspt's header: no free word after it) is set by
  `0x8001829C` (`*0x80112830` = header word 0xA9); `0x80010894` then, for each tag the main program knows, copies the
  blob header into its fixed main record (`0x80112838..0x80112FB8`; Trop `0x80112D78`), points the list entry at it
  and writes `+0x14` 0, the methods and `+0x28` = `+0x10`. A tag it does not know stays as the blob's own header in
  the list, methods as the blob has them (on 26: `BmbC`, `CrgC`, and `OutR` with count 0 and no methods); three main
  records are empty (`0x80112988`, `0x80112A48`, `0x80112B98`). The loops run each record's `count` objects from
  `+0x10` by `+0xC`, skipping objects with `+6 & 0x1000`: think `0x80025C90` (`+0x18`), update `0x80025E3C` (`+0x1C`),
  draw `0x80025F4C` (`+0x20`), create `0x80025BD0` (only `+0x14` ≠ 0). Messages `0x80026284(obj, msg)` go to the first
  list record whose tag is the object's own tag (its `+0x24`); broadcast `0x800262FC(tag, msg)` and find
  `0x8002620C(tag, i)` / `0x80026130(tag, n)` go by record tag; the bolt hit `0x80026480` and the touch `0x80026A94`
  walk every record with flags & 2, lock-on and auto-aim `0x8005B33C` go through the Dfob's `+0x98`. Measured: a record
  of another tag with the Trop's four methods and one Trop instance as its pool runs that object as a Trop (think,
  walk, damage, the bar, lock-on). A Trop object's links are relocated words in its instance (`+0x70` Dfob, the Dfob's
  `+0x98` back to it and `+0x84` the root node; `+0x11C` the root node, `+0xA8` its child; `+0xC8` / `+0xCC` / `+0xD0`
  the chain and blocks; `+0xA4` its zone); the kind (`+0x74 & 0xF`) picks only the descriptor list, the gun and code
  branches.
  - Where the main program assumes the tag `'Trop'`: the Trop update sets `'xxxx'` for the touch search and writes
    `'Trop'` back on every update with state ≠ 0 (`lui 'Tr'` at `0x800B3D50`, `0x800B3DD0` (delay slots),
    `0x800B3E64`; `ori 'op'` `0x800B3E68`; `sw` `0x800B3E6C`); Trop-pool-only code (the record's `0x80112D80` count /
    `0x80112DA0` pool): the closer pick `0x800B62BC`, the think's target pick `0x800B22E4..0x800B24CC`, the ally-ahead
    test `0x800B2E78`; broadcasts to `'Trop'` (Blst `'nois'` `0x80033920`; Humn `0x80070764`, `0x80070CD4`,
    `0x80071598`, `0x80071A58`, `0x80071AC8` (the creature camera), `0x80079B2C`; Boss `0x80045AE0`; `0x80027C4C`,
    `0x8006323C`; the Trop's own `'nois'` / `'Rec1'` `0x800B10B4`, `0x800B1D64`, `0x800B2770`, `0x800B5B30`,
    `0x800B5E50`); the sender-tag compares of a Trop's shots (Humn's damage scale `0x800D2514` in `0x8007AD60`,
    `0x80078B78`, the Trop handler's friendly checks `0x800B5B40` / `0x800B5C40`).
  - The kind table `0x800E65E4` has 7 lists (kinds 0..6); the gun table `0x800E6600` follows it at once, so a kind 7
    would read the gun table's first word (0) as its list: a new kind needs both tables moved (code references
    `0x800B0728` addiu, `0x800B0B34` and `0x800B3358` lui + lw, `0x800B1E78` the gun table) and falls to kind 0's paths
    at the kind compares (1, 2, 3, 4, 6). Kind 5's list `0x800E64E8` has no user found.
- **The loader's heap follows the blob's end word** (2026-11-10, sub-level 26 under id 33, flag 0): `0x80019294` passes
  base + (header `+8` − header `+4`) to the relocator `0x8001866C` as its allocation pointer; type-9 relocation words
  (`0x09nnnnnn`, `0x80018578`) allocate from it, copying item n of a ROM-wide bank (`*0x80001358`) into the heap (an
  animation block's tracks are such words: the palace guard's five blocks hold 216, 17,940 bytes). So a blob grown at
  its end (the end word moved) keeps its appended data: measured with 0x4000 and 0x8000 bytes appended (the first
  allocation `0x801A619C` = the new end word, the grown region unchanged after 600 VIs, every object as before), and on
  sub-level 27's blob (stock end `0x80274920`) up to 0xF2C0 bytes (the only words changed by the game those of the
  animation block instances in it). The
  vertex pool's u16 index reaches up to pool + 65535 × 12, past sub-level 26's end: vertices appended to the blob are
  indexable (the first past the end: (end − pool) / 12 = 49320).
- **The game's random word** `0x8018E9B4` (u32; `0x800B8BE0`: x · `0x41C64E6D` + `0x3039`): idle clips and other
  objects draw from it, so two states at the same frame and place still animate apart unless the whole game state
  matches (Dash's bones in `gall_dash_*.st` made from another `gall_tp5.st`: up to ~1.5 apart).
- **Other `LEVEL_ID` users** (65 loads in 31 functions): only the two tables above index by the
  id; the rest compare. Asteroid Field's (`== 6`): Stft level start `0x80097D3C` (special asteroids `0x8018DCA2`),
  `0x80097EE4` (missile lock-out `0x800DEED4`), `0x80097F28` (first TIE wave `0x800E1B28`), Leebo's line
  `0x8009806C`, the kill count-down in `'htMe'` `0x8009D14C`; the enemy shot's damage scale in `0x800B1560`
  (`0x800B1DB4`: id < 14 1.0, ≥ 25 2.0); the score screen's switch `0x80027374`. The next level is `id + 1`
  (`0x800194DC(−1)`, the cutscene director `0x8005BB28` on START: `id + 1` / `+ 2`).
  A blob carries its level's code and data: with sub-level 13's two entries set to Asteroid
  Chase's (in RAM) and id 13 loaded (debug This Level), the whole Asteroid Field plays (Star
  Destroyer, Outrider, Leebo's line, TIEs) under id 13.
  `0x80019B14` is the unpacker; with flag 0 the blob is DMA'd straight to `0x80196950` and it
  returns at once, so a blob can sit in the ROM **uncompressed** (its table entry: flag 0, length =
  its size). Checked: Asteroid Chase's unpacked blob (`harness/level_blob.py` dumps one) appended at
  ROM `0xC00000`, slot 6 pointed at it in RAM: the level plays, and a byte changed in that copy
  shows up in the level's RAM. The unpacked blob starts `"LStb"`, its load address `0x80196950`,
  its end, two more words (`0x7BB8C0`, `0x7DC2A0` for Asteroid Chase: their difference is its size;
  not understood), then pointers to its functions (linked for `0x80196950`, no relocation).
  Asteroid Chase's blob is only 133 KB (code, its own data, the "Level 3" title): its models
  (Star Destroyer, ships) come from elsewhere; Gall 6a's (945 KB) holds its geometry and the
  atmosphere records.
- **Objects in a sub-level blob** (2026-10-09, Asteroid Chase): the class pools live in the blob. The class
  table (`0x80112808`, 0x30 a class: tag, `+8` count, `+0xC` instance size, `+0x10` pool, `+0x1C` update,
  `+0x20` draw, `+0x24` a third method, `+0x28` the pool again) points into it: Anim `0x80199F00` (1), Astr
  `0x8019A060` (10, 0xDC), AstF `0x8019A920`, Chor `0x8019C7A8` (1, 0x174), Doly `0x8019C944` (2), Expl,
  Misl, Blst, Stft `0x8019EC6C` (1, 0x254), TieF `0x8019EF38` (22, 0x15C), Trak `0x801A0D48` (2). In the
  blob each class has a header record (0x28: tag, a word, count, size, offset of its pool) followed by its
  instances (each starts with the tag). The blob's data words that are pointers are stored as **offsets from
  `0x80196EA4`** (load address + 0x554) and become pointers at load: e.g. the Astr header's `0x31BC` →
  `0x8019A060`, the Anim's inner links. A table of 41 offsets at `0x80199DE0` (one per class header in the
  blob, up to `0x80199E80`) becomes the addresses of the classes' records in the table above. So the object
  data is relocated by the game (unlike the code, which is linked for `0x80196950`), and a pool sits wherever
  its header's offset says. Not found yet: which words the loader treats as offsets (per class, probably the
  class's `+0x24` method) and where the data section's base comes from.
  The player ship's model is in the blob too (the Outrider: root `0x801A2880`, hull mesh `0x801A3C94` with
  21 parts at list `0x801A58DC`; mesh and node words absolute, as linked).
  Fields that are offsets (found by comparing the blob with `local/states/ast.st` RAM; 85 words): every class
  header's pool offset, Astr `+0xD8`, AstF `+0x30`, Doly `+0x60`, Stft `+0x220`, TieF `+0xAC` / `+0x118`,
  Trak `+0x8C` (its target: Chor), the Anim's links, and links into the Chor instance from the TIEs
  (`+0x60`, `+0xC8` of it) and from the start of the data. Another kind: `0x01000000 | n` = **transform node n**
  of the blob's node array (`0x801A13B0` + 0x48·n, the address at blob header `+0x14`), resolved at load
  (111 such words). E.g. Chor `+0x158` (its own drawn node) = node 3, `+0x150/+0x154` nodes 108/109; the
  player ship's model root `0x801A2880` is node 74; each Astr has its own node (4…).
- **Swoop race** (sub-level 17, `local/states/lvl5.st`; 2026-10-09): classes in
  play Dfob 13, Anim 1, Bike 11 (0x148, pool `0x8019DAF0`, the player's first), Expl, Doly 2, Trak 2 (the race
  camera is a Trak, as in Asteroid Field). Bike: position `+0x8`, yaw `+0x14` (degrees, heading = yaw + 90),
  bank `+0x1C`, speed `+0xE8`; the AI bikes' speed `+0x78`. Measured: A accelerates ~14 level units/s² (top
  ~50), B reverses, full stick turns ~50°/s banked up to ~19°, the height keeps to the ground, a wall glanced
  is slid along, one met at an angle stops the bike dead. The Bike code is in the main program (update
  `0x8002B34C`, draw `0x80030710`; it calls `0x800654A0` 3 times). **Its ground and walls are not the
  segment trace's**: `0x800654A0` (mode 0, level geometry) from the bike down, sideways and ahead (100 units)
  hits nothing in the swoop level. The swoop canyon's collision is some other data (not found yet).
  The level ends at level y ≈ −350 just south of the race's end: past it is fog colour.
- 66 places in the main program read the sub-level id (`0x8013CE0E`; 58 counted first); many are checks for one
  level, e.g. id 6 (Asteroid Chase) in the player ship's methods: level scripting, not flight (see *Player ship
  `Stft`*: level-id checks), also 29, 4, 14, 20, 25, 30. A blob
  played under another id loses those. So a level made from Asteroid Chase is best loaded as id 6
  with only its table entries pointing at the new blob (put back after); a 33rd id (the loader
  clamps ids ≥ 32 to 2, and the tables have no room) only matters for a level-select entry.
- Levels are split into sub-levels with their own level id (`0x8013CE0E`) and target pool.
  Escape from Echo Base = id 4 (hangar start, 7 teleport points: (−356.6, 80.5), (−165, −269), (−256.4, −127.7),
  (−259.7, −47.8), (−126.1, −83.4), (136.1, −105.5) the ice ledge before the girder bridge, (102.2, −14.8)) and id 5 (inner base → AT-ST
  arena). Sub-level 5 teleport points: (354, −80, −78) start, (264, 25, −78), (57, 27, −34),
  (−99, 25, −51), arena (−264, −289, 0) and (−295, −283, 0). Teleporting into the arena plays
  the AT-ST cutscene and starts the fight.
- **Stage Complete** (2026-10-28; `local/work/main.bin` + a run on `local/states/play.st`): the game's own step from one
  sub-level to the next within a level (the Echo Base hangar's lift, 4 → 5). Level state u32 `0x800DD2B0`: 0 / 1
  start, 2 playing, 3 Level Complete (the score screen), 7 Stage Complete. The one writer of 7 is `0x8007489c`, called
  from the on-foot player's update (`0x80074fa4`, at `0x80076eb0`): the player's sector (`+0x70`) with flag `0x400` is
  a portal: params 0x1D..0x20 (read by `0x80017a78`) are an offset and the next sector; without flag `0x1000` the
  player and every `Blst`/`Expl`/`Doly`/`Trak` are moved by the offset (message `TPrt`); with `0x1000` (the stage's
  end) once (s16 `0x800E0F10` = 1): `0x8007bb58`, state 7 and `0x800271b4(2.0)` (float `0x800DD2C8` = 2 s, counted
  down). The text is drawn at `0x8002480C` (string `0x800D0DD4`, "~c~oStage Complete", at y 48) while the state is 7;
  `0x80025d0c` handles 3 and 7 alike. Written from the harness: state 7 + `0x800DD2C8` = 2.0 + `0x800E0F10` = 1 →
  the text, the timer runs out in ~150 frames and the next sub-level loads (4 → 5, state 1, then 2). Held at 7 for
  120 frames, then state 2, the timer −0.01, the flag 0: the text only, the sub-level stays and play goes on. While
  the state is 7 the 3D world is not drawn (the harness shot shows only the fog colour, the HUD and the text).
  Ships (`Stft`) never call `0x8007489c`: in a flight sub-level the state has to be written.
- **The player's start and the respawn** (2026-11-09, sub-level 26, `local/work/duel/arena_k2.log`): the start is the
  blob's one `Dfob` of type 5 (u16 `+0x6A`; place `+0x6C..+0x74` = its `+0x50..`, yaw `+0x78`, copied as is into the
  Humn's `+0x14` / `+0x8C`); checkpoints are type 3. `0x80074C38(player, _, dfob)` sets Humn `+0xB0` = the point,
  the place and yaw from the Dfob; with `+0xB0` 0 it takes the type-5 one (`0x80074B84` → `0x80074A24`). The death
  respawn (`0x80071510..`: health from `0x800E0DDC`, `+0xE4` 3 s invulnerable, then `0x80074C38(player, _, 0)`) puts
  him at the last checkpoint or the start, lives − 1, no reload: a start Dfob written at run time moves the respawn.
  The zone under a place is found by the zone search, not by the Dfob's `+0x60`. The stage-end call `0x8007489C`
  (`0x80076EB0`: `(player, sp+0x430, 0x800E0DC8 == 0)`) needs the player's zone to carry `0x400` and `0x1000`; its
  effects can be made without it in its own order: the latch `0x800E0F10` = 1 (once), `0x8007BB58(player, &offset)`
  (offset = a stage-end zone's properties 0x1D..0x20), `0x800DD2B0` = 7, `0x800271B4(2.0)`; then id + 1 loads.
- Scripted scenery runs as class `Anim` (`0x80112898`, 0x40 bytes), not as its own class. The
  Millennium Falcon leaving the Echo Base hangar (sub-level 4, on the way from the start into the
  first trooper room, ~(−250, −64)) is the only `Anim` there. Instance `0x8019E620`:
  `+8` → its `Dfob` (#33, `0x8019BBB0`), `+0xC` state (5 before the trigger, 4 once it plays).
  The player at `0x8019E660`: `+4` time (float), `+8` 15 (fps), `+0x2C` 182 (length), `+0x3C` frame (u32).
  `Dfob +0x84` → model root `0x801F5A20`. Child `0x801F5A68` carries the ship's placement
  (translation ≈ (−171.5, −66, 18.4)), and under it the mesh node `0x801FCACC` (16 parts).
  Addresses come from `play.st`.
- Mesh node (0x18 bytes, `w0` like `0x3064ffxx`): `+8` the wrapper DL built this frame, `+0xC` part count,
  `+0x10` part pointer list, `+0x14` bounding box (8 F3D vertices). Part (0x2c): min/max floats,
  `+0x24` → material {0xC, 0, texture record}, `+0x28` geometry DL (F3DEX, absolute `G_VTX`
  addresses, ends with `B8`). Texture record (16): size, `+8` texture DL, `+0xC` palette+texels
  (right before that DL). The texture DL starts with `BC001006` = segment 4 base, and its
  `SETTIMG`s are segment-4 addresses, so after moving the block only that word changes.
  `G_VTX` here: length = ((w0 & 0xFFFF) >> 9) × 16 bytes (not the low 10 bits).
  Per part the wrapper calls `0x800E7170` (shared render state), the texture DL, then the geometry.
  Lit or not is the part material's flag: words `+0` and `+0xC` = `0xE` (the Outrider hull's) draw the part lit,
  the vertex slot `+12..+14` read as a normal (signed bytes); `{0xC, …, 0}` (scenery) draws it
  unlit, those bytes the vertex colour (`FF FF FF`: white). Normals alone under an unlit material draw as colours
  (playtest8f). The scenes draw their own models unlit: Cut 05's Outrider (`0x80198DA4`) and the last scene's have
  part materials `+0` / `+0xC` = `0xC` (a few `0x4`) with the shade baked into the vertex colours (Cut 05: grey
  122..255 by height), under a scene light (ambient 82/83/88, directional 204/230/241) that touches nothing unlit; the
  mission's Outrider is lit (`0xE` + normals). A model shown in both (the Gall Run's Falcon, `falcon.bin`) is switched
  between the two looks per level (`falcon.c` `falcon_look()`). The geometry DLs of these meshes: triangles `0xBF` (w1 bytes 1..3), quads `0xB5` (w1 bytes 0..3),
  vertex index = byte / 5, `G_VTX` loads from slot 0. In the character models (the palace guard's 20 parts, 780
  indices, and Dash's, decoded 2026-11-07): `G_VTX` w0 `0x04 v0 (n << 9 | 16n − 1)` (v0 the cache slot, n ≤ 16),
  `0xBF` w1 byte 0 `0x02` then the three indices × 5, `0xB5` a quad (two triangles (a,b,c) (a,c,d), all CCW from
  outside), `0xBE` a cull test (no triangle).
  Character textures: the palace guard's 13 plain records are CI4 with a 16-entry RGBA5551 palette: TLUT
  `F0000000 0703C000` into tile 7 at TMEM `0x100`, the texels loaded as 16-bit (`F5500000`, `F3` lrs = W·H/4 − 1,
  dxt = 2048 / (W/16)), the render tile CI4 (`F54…`, line W/16) with masks log2 W / log2 H, `F2` size, texture scale
  `BB000001` W·512 / H·512 (so vertex s, t = u, v · 4096); record word 0 (W·4) << 16 | H·4, word 1 `0x00060000`,
  `+0xC` an 8-byte header (`B8000000 00000000`), the texels, then the palette; addresses segment 4. CI4's line is at
  least one 8-byte TMEM word: 16 texels wide at least. The material's combiner multiplies the texture by the vertex
  colour (a white texture shows the vertex colour). Dash's model textures are CI8 with a 256-entry RGBA16 TLUT
  (32×64, 16×32) and RGBA16 mipmapped (32×32, 16×16); his face has no texture of its own (spread over four 32×64
  photo textures of the head).
  Culling: the game drops a part by its box and a whole mesh by the mesh box. Meshes drawn far larger than
  their level (Gall Run, 6–13.5×) lost rock in plain view with real part boxes: such parts get no-cull boxes.
  A mesh box must hold the model's origin and stay small (a ±352 cube, or a box from the feet up, culled a
  whole posed model; ±88 works). Big triangles across the camera's plane with no-cull boxes drew dark wedges
  (the Star Destroyer): keep real boxes there. A node far off (thousands of units) is not drawn at all.
  Transform node: u16 `+0x02` (high byte `0xFF` drawn), rotation rows at `+0x14` (9 floats; the rows are the
  local axes in the parent), translation `+0x38`.
- Expansion RAM `0x80400000–0x807FFFFF` is unused in Echo Base and Asteroid Field.
- Asteroid Field (sub-level 6, `local/states/ast.st`): the player ship is class `Stft`. Outrider: root node
  `0x801A2880` → group `0x801A3AB8` → meshes `0x801A3C64`, `0x801A3C7C`, `0x801A3C94` (hull, 21 parts),
  and the gun nodes. The ship flies along model +y; the glow meshes sit at its stern (y −11).
  The Stft object holds three transform nodes at `+0xB8` (engine glow, `0x801A2958`, scale pulses),
  `+0xBC` (top gun, `0x801A28C8`) and `+0xC0` (bottom gun, `0x801A2910`). The top and bottom guns share
  one mesh `0x801A3CAC`, pivot at the origin, barrel along +y. The draw method `0x8009C318` loops
  over them and builds each matrix (aim rotation from `+0xC8` s16 and the target, translation
  z +5.2 from the double at `0x800ECA68`, or −5.0) before the game draws the model. It copies the matrix
  into the node with `0x8000FE48(node, matrix)` (guns: `0x8009C790`), so writes to a node between
  frames are lost.
- Gall (sub-levels 14 = 6a, 15 = 6b): mostly interiors. The canyon is narrow ledges between
  rock walls ~460 units tall (debug Teleport points 6 and 7 of 14), with pale sky and fog. Level geometry uses the same
  mesh nodes as models (442 meshes / 1490 parts in 14, world coordinates, e.g. `0x801F4438`: 95
  parts, x −353..−188, y 843..1035, z 201..660). 6b holds three `Boss`: `boba`, `slav` (Slave I,
  parked at (−190, 271, 522), state +0.01) and the `ATST`, plus one `Anim`.
  Gall's cliff faces (14, e.g. part `0x801FCDC4`): single faces from ~200 under Dash's ledge to ~660 over it,
  a grey vertex colour per face (59..244), quads (`B5`) and triangles; rock texture record `0x801E1B28`, sandstone
  `0x801E1B38` (`local/states/gall_tp5.st`). 6b (`local/states/gall_6b.st`): the round shaft of the Boba fight is meshes
  `0x80214B9C..0x80214BE4` (walls facing in from its floor at z 393 to the rim at 690–787, the gantry in the
  middle, top 652/667). Slave I is 8 meshes `0x80213B34..0x80213BDC` under `slav`'s node, hidden inside the
  gantry till it lifts off (Boba's `+0x5C4` = 0 makes it rise). Its engine glow is meshes `0x80213BAC/BC4/BDC`
  (white); its five transform nodes stay empty in flight, and a transform node of our own under its node hid
  all of Slave I. Its twin guns are mesh `0x80213B4C` (a bar with two barrels along +y) on the first of its 12 bones
  (the boss object's `+0xD0`..`+0xFC`, bind matrices at `+0x104 + 64·i`, read and written by `0x8000FEB8` /
  `0x8000FE48`); parked, the bone is at 0, the guns inside the hull. In flight the boss's animation (picked by
  `0x8003FDB8(boss, n)`; the update returns while `+0x584` is 1, `0x8005351C`) moves the bones: the guns' place
  there was not read (2026-10-18: Boba's `+0x584` 2 or 3, his health 0 did not start the fight on `gall_6b.st`). Dash's model is 19 meshes posed by their bones (`local/states/gall_dash_stand.st`, `gall_dash_jet.st`).
- Gall 6a's start (`local/states/lvl4.st`, debug Teleport point 2, (−296, 931, 211.5)): Dash spawns inside the parked Outrider (the
  lit corridor and the small cabin east of it are its inside; Leebo's "The ship is safe with me, Sir." at the hatch behind
  him). Outside, the ship stands on legs over sand (z 200.9); its hull is not in the world tree from `0x8013CE24` (blank on
  `level_map.py`) and there is no `OutR` object. Beside it stands a short orange post (top 212.9 at about (−295.5, 962));
  the hull's dark side has a rim at ~216 and the deck is ~221 (the cabin roof ~228.7). A silver Challenge Point floats
  over the hull at (−314, 950, 229.1) (Dfob `0x69`, no object of its own found): a running jump from the deck ~11 units
  before it takes it ("Challenge Point" bottom right). The take: `tools/video/record_b.py jump2`.
- Station Chase (slot 29, `local/states/chase.st`): Leebo flies the Outrider (class `Stft`) along a route and the
  player shoots from the gun turret. The ship is carried by the `Chor` object: same position every frame, a
  spline over 4 route nodes (indices at Chor `+0x6C..+0x78`, segment parameter `+0x64`). The route is a closed loop
  of 80 nodes, 0x54 bytes each, from `0x80198394` (x, y, z floats at `+0`, on a 128 grid, radius ~2000
  round the skyhook). Nodes written in RAM take effect at once (all z +200: the ship climbs and
  stays 200 higher). The skyhook is one mesh, `0x801A3160` (32 parts, ~3000 units across). Part count 0 hides it.
  With the debris (`AstF` model list) also hidden and Gall's fog/light (fog RGB 162,162,188, min ~985, ambient 100,
  directional 200,184,188), the level looks like Gall's sky. Enemies are `TieF` (Xizor's StarVipers model).
  Loading a slot over another level's state leaves the old level's meshes in RAM above the new heap.
  `0x801A3160` is not the skyhook: it is a debris model (node `0x801A2B30`, scale 0.2, 9th entry of the
  `AstF` list) and is never drawn at the start (stamp −1). Level
  geometry is one-sided (Gall's canyon walls face the path Dash walks). Node `+0x44` is a per-node id
  (`0x4A`… on the Outrider); a copied node with a duplicate id is drawn with the other node's matrix.
  In this level the Outrider flies broadside: identity rotation, path along world +y, camera behind on the path.
- World tree: the global `0x8013CE24` points to the level's root group (kind 5 nodes are 0x14 bytes:
  w0, w4, w8, count, list). Everything drawn hangs under it: cameras, the player ship, enemies, lasers,
  and in on-foot levels the level geometry (Gall: root `0x801F2520`, 13 groups). Level meshes are
  room-local: their vertices are relative to the room's transform node (Gall canyon: translation
  (−200, 900, 0)) while their part boxes are in world units (`harness/gallrun/mesh_image.py` `room_offsets`).
  A node directly under the root draws in the world: Chor's `0x801A0CD0` in Station Chase, hidden
  by the high byte of `+2` (0x00; `0x8001040C(node, 0, a2, 0)` sets it, 0xFF = drawn). Its scale child
  `0x801A2B30` is set to identity and its mesh pointed at a copy of Gall canyon meshes. The canyon then
  renders in Station Chase with its textures. Objects in this level vanish ~200–250 units from the camera.
  Chor hides that node again on every update (before the draw). Code running at frame end gives Chor a decoy
  copy at `+0x158` to hide instead (gallrun.c). The Stft health is the int at `+0x240` (495 full, 0 dead,
  state `+0x230` = 6).
- Cameras in Asteroid Field (2026-10-08):
  - Camera entries at `*0x800D08A0` (0x80 each): `+0` active flag, `+4` type << 16, `+8` the matrix
    it takes its place from, `+0x10` (type 2) the matrix it looks at, `+0x14…` its own rows and
    eye (`+0x44`). Entry 3 is type 1: it copies `Trak` 1's matrix (`+0x20`), smoothed toward it.
    Entry 8 is type 2: eye from the second `Doly` (`+0x50`), looking at `Chor`'s matrix translation
    (`Chor+0x20`, translation at `+0x50`) — the object a type-2 entry looks at is this pointer, not
    `Doly+0x60` or `Trak+0x8C`.
  - The level starts on entry 8 (the dolly fly-in) while the second Doly's timer `+0xA8` runs to its
    length `+0x130` (3 s), then switches to entry 3 with a blend over a few seconds. The blend state
    is at `0x80111760`: `+4`/`+6` s16 from/to entry, `+0x20` seconds into it, `+0x24` its length.
    Setting the timer to the length ends the fly-in at once.
  - `Trak` class (`0x80112EF8`): update `+0x1C` = `0x800A18B8` places its own view behind its target
    (`+0x8C`) every frame; draw `+0x20` = `0x800A2174` only passes the matrix to a camera node when
    `+0xA0` is set (0 here). A view written only from the draw method is mixed with the update's in
    entry 3 (the farther from the target, the bigger the pull toward it); write it after the update.
  - A camera written from the overlay hook is used the same frame by entry 3 but a frame late by
    entry 8 (through the Doly copy).
  - The view projection is the active entry's; `0x80111788…` is a render-side copy (stale outside
    blends).
- Screen fade: `0x800D0804` s16 r, g, b, alpha of a full-screen rectangle drawn over everything,
  HUD included (−1000 ×4: none; code at `0x80008C70`). Echo Base fades in with it (alpha 215 → 0
  over ~1.5 s); Asteroid Field leaves it off. Alpha 255 is still not fully black. On a level restart
  the game runs its own short fade first; a value written from a draw method wins over it.
  A ship's hit (Stft, a turret bolt, health −10) sets it (255, 128, 0) alpha ~241 and fades it out over ~60 VIs (~13 a
  step) through the setter `0x80009088` (ids −101 / −102 store the colour and alpha words); the fade-out is part of the
  object update, so a held radio line (`0x800DD2D0`) freezes the tint on screen till it is let go.
  `0x800D0764` is not the screen: a 0…1 factor rising with it that scales the int at `0x800D0760`
  (25000) in `0x80007088`: the music volume (track `0x800D075E`, per-level volume `0x800D0760` set by a table
  of small setters before it). Confirmed 2026-10-09: writing `0x800D0764` every frame turns the music down.
- Effects volume: float `0x800D2524` (the options' setting), multiplied into a sound's volume in `0x80007340`;
  it also scales sounds already playing (written lower, a playing roar went down too).
- Radio message: `0x800078E4(portrait, frame sprite 31, seconds, 13, text)`; text codes `~o` colour,
  `~n` new line; a text starting `~h` holds the game: `0x800078E4` sets s16 `0x800DD2D0` and the object
  update is skipped while it is set (the pause's START path too). START lets it go; clearing it and the float `0x800D07FC` (the line's
  seconds left) does too. The letters are drawn as sprites: a four-line text cost ~25% of the frame rate in
  Asteroid Field (33–36 fps against 46–48); the portrait costs nothing. HUD sprites: table `*0x8013CE2C` (per level), slot 31 the message frame, 32
  static; a sprite is CI4 with a 16-colour TLUT at `+0x18`, bitmap count `+0x1C`, bitmaps (w, h,
  buffer) at `+0x24`, odd rows with their 4-byte halves swapped; portraits are 44×44 in a 64×44
  bitmap, index 0 transparent. Text slot table `0x8013CE30`. Echo Base (`play.st`) slot 9: Dash's HUD
  face by the lives count (2026-11-15): CI4 64×38, two bitmaps 64×32 + 64×6, at (25, 15), palette entries 0, 2, 3 a
  frame of three rings, 1 the transparent columns 35..63, the face inside rows 3..34, columns 3..31; the same form on
  `palace.st`, `duel.st`, `sew_428.st`, `om.st`, `xiz_glad.st`, `sup.st`, `lvl4.st`; slot 9 empty (0) on `lvl0.st`,
  `lvl7.st`, `sky.st`, `ast.st` (`harness/tests/t_guard.py portrait`; `guard.c` puts Luke's there with the Look on Luke); the game has no Lando portrait. Asteroid Field's slot 29 is empty (0 on every frame of `ast.st`,
  2026-10-16, `local/work/slot29_probe.py`); Skyhook's (`sky.st`) is Luke in his pilot's helmet, 64×44,
  2 bitmaps 64×32 + 64×12, the picture 42 wide. Asteroid Field draws a portrait by its indices (a grey ramp under
  the green tint): a sprite copied from another level with its own TLUT shows as noise; remap by luminance. Hoth (`lvl0.st`, 2026-10-18, `local/work/hoth_faces.py`):
  slots 20-27 are 8 frames of Luke in his helmet under moving interference lines (64×44, the picture 44×44 with a
  1-px grey frame). Hoth's HUD (`0x80089C28`..`0x80089CD0`) animates them itself: s16 `0x800E184C` += 1 a draw
  (& 0xFF), elements 20-27 hidden, then element `20 + ((counter & 0xE) >> 1)` placed at (136, `*0x800E1848` + 16) in
  (0, 255, 0, 0xC0): one frame per 2 draws, in a loop. The radio message cannot animate (`0x800078E4` takes one
  portrait id; every caller passes 0x1E or 0x1D). Asteroid Field's free portrait slots (`ast.st`, 2026-10-18): of
  20-47 only 24, 29, 36, 38 have no sprite and no text; the ship HUD places 24 (`0x80093C38`), and 36, 38 are target
  panels the game only hides (`0x8009648C` with 35-39), so 29, 36, 38 can carry a portrait.
- HUD text elements (80 slots, one list for the whole game, `0x80008BC4` draws them): place from
  `0x80111110 + id*4` (s16 x, y; x `-1000` hides it), colour from `0x80111250 + id*4` (bytes
  r, g, b, a, so the word is `0xRRGGBBAA`), flags byte at `0x80111390 + id`, the string from
  `(*0x8013CE30)[id]`; the API is `0x80009088(id, x, y)`, `0x80009138(id, r, g, b, a)` — the alpha
  is the 5th argument, on the caller's stack at `+0x10` — `0x80009178(id, mask)` /
  `0x800091A4(id, mask)` (flags OR / AND NOT) and `0x800091D4(id, text)`. Ids are shared between
  levels and HUDs, so a slot means different things in different places: 21 (`0x15`) the on-foot
  health percentage, 23 (`0x17`) the on-foot jetpack fuel percentage at (243, 15), 24 (`0x18`) the
  lives; a ship level uses 23 for something else (grey, pushed off screen). Asteroid Field (`ast.st`, 2026-10-17):
  37 the target panel ("T.I.E. FIGHTER", the side and front icons, the bars; at (240, 175), orange or green, flags
  8, no string: sprites), 51 "Missiles: n", 50 the lives, 25 the ship icon, 26 the radar, 40/41 radar blips. The
  game places 37 only as it changes: x `-1000` written from outside stays hidden (four shots over 200 frames). It
  is not the target pool's: clearing the TIEs' `+6` flag 0x2 (they hold 0x43) or holding the missile lock-out
  `0x800DEED4` > 0 left it up. (`0x801156E0`, a TIE pointer that changes with it, is a stack slot.) Numbers go in as
  `sprintf(buf, "~f3~o%d%%", …)` (`~f3` font, `~o` colour, `~c` centred; `0x800C0240` = sprintf).
- Asteroid Field's gunner, the inside view (2026-10-17, RAM diff of `ast.st` over view 4 → 5 → 4 → 5): the view key
  writes s16 `0x8018E462` (4 inside, 5 behind; restored from it at `0x80099A48`). The ship's draw hides its node
  `+0xB0` while the camera index is 4 (`0x800919A0`, `0x8001040C(node, 0, 0 / 0xFFFF)`: `+2`'s high byte), but only
  while the guns are on (Stft `+0x70`). The ship HUD (`0x80092F1C`, its 2nd argument = `Stft+0xB4`'s node shown)
  places the turret's window as elements 20-23 (`0x80093AFC`..) and the red sight as element 0 when it is hidden,
  x `-1000` otherwise; as with 37, only as it changes. The HUD does not run while a held radio line (`0x800DD2D0`)
  holds the game: the window the last inside-view frame placed stays on screen under the line, whatever camera draws
  (measured 2026-10-23).
- Space radar (Asteroid Field, Skyhook, the station chase; 2026-10-17, `local/work/radar_probe.py`):
  - Contacts: every object sends the player's ship a `'ping'` message each frame (the ship's message switch at
    `0x8009C810`, case at `0x8009C9E4`). It copies the sender's 0x20-byte record into the list at `0x8018E468`
    (count `0x800E1B30`, at most 32; when full it replaces the farthest). Record: `+0` class tag, `+8` position,
    `+0x14` distance², `+0x1C` flags (top byte bit 0: enemy; bit 4 of the low byte: blue dot, else orange).
    With a sector record (`*0x800D2400`), pings from farther than 3000 are dropped.
  - Drawing: the ship HUD `0x80092F1C` (called from `0x80096DE4`), loop at `0x80094DC4`. Each contact is
    projected through the camera (`0x800B9F1C`: 0 behind the camera, 1 in front but off screen, 2 on screen;
    screen x, y out). Dot = radar centre + (screen x − 160, screen y − 120) × 0.05, drawn only if that offset is
    within 20 px and the contact is within ~2000 units on the flat. HUD elements 40…47 (`0x80009088`), up to 8;
    unused ones go to x `-1000`.
  - So it is a forward scope: the centre is where the camera looks, the on-screen view covers the inner ±8 px,
    the rim is ~2.5 screens off-axis. Nothing behind the camera is shown (the red edge arrows point to those).
  - Target (2026-10-18, read in `0x80094DC4`–`0x8009528C`): the same loop keeps the on-screen record nearest the
    screen's middle (`sp+0x280`; a `'PRBT'` record is skipped) as the target the panel shows (35 / 37 / 39 by its
    kind). No distance limit without a sector record: a TIE parked 40000 off in front was taken (the Gall Run's
    hidden waves, `gall_ties.c` `radar_drop_far()` drops their records).
  - The held target (2026-10-22, read in `0x80096564`–`0x80096624`): with no pick this frame, s32
    `*0x800E1B90` (the last target's list index, `lw` at `0x8009656C`) ≥ 0 and the float `*0x8018E8AC` > 0 (a hold
    timer, ~0.94 s down to 0), the panel shows record `0x8018E468 + 0x20·i`, **not checked against the count**: a
    record copied into that slot later (a parked bomber's ping) is shown as the target. Its kind: tag `TieF`, flags
    top byte bit 0 → 37, bit 1 → 35, bit 2 → 36, bit 4 → 39 (35 in level 0x1D). The Gall Run sets the index −1 when it
    is at or past the count after dropping far records (`radar_drop_far()`).
  - The same loop sorts each contact into one of 8 sectors around the ship (`sp+0x29C`, 2 = attacking via flag
    bit 0), but nothing in this function reads them: the space HUD has no sector display. Hoth's sector radar is
    another blip loop (`0x8008AB60`).
  - Gall Run (`pt3c`, stage 2): the 10 TIEs ping (14 contacts with the 4 parked ones), dots show while they are
    ahead (first ~150 frames after they come in), then none while they chase from behind: the same rule.
- On-foot fuel gauge (update function from `0x8006AFB8`): the number is the fuel `Humn+0xBC` as a
  percentage of the max (`0x800E0DD8`, 100), and its colour is a health-style ramp — over 75 %
  pure green `(0, 255, 0, 128)`; 33…75 % green to yellow (r rises, `(75 - pct) * 255 / 42`);
  5…33 % yellow to red (g falls); under 5 % red. The whole block runs only while the gauge is up
  (on foot, mid-air with the jetpack), so the slot is otherwise untouched.
- Invincibility's blue health: the same update, one function earlier — `0x8006A9F8` `lw v0, 0x74(t3)
  andi t4, v0, 8` — with the player's HUD-icon bit set, element 21 gets `(0x80, 0x80, 0xFF)` at
  alpha `0x80` (`0x8006AA08`) instead of the green/gradient, and that is the whole cue: the game
  recolours the number, it doesn't swap a sprite. The *Jetpack Fuel* cheat takes that same colour
  for element 23 (the hook in the table above), so the fuel number says the cheat is on.
- Sounds: `0x80007340(id, 6, pitch as float bits (1.0 = 44 kHz), volume 0x6590, 0)`. The global
  sound bank file is at `0x80108C80` (one instrument, 131 sounds; the slot after the list is free).
  Wave table bases are ROM addresses; samples VADPCM.
  The asteroid hit (Asteroid Field): the asteroid's message handler `0x8002857C`, on `plow` (rammed),
  `prox` or `shot`, plays `0x80007340(0x4B, 4, pitch, vol, 0)` with pitch (r · 0.4 + 0.8) · 0.25 (0.2..0.3) and volume
  (r · 0.4 + 0.4) · 32000 (12800..25600), r = `0x800B8BE0()` / 2^31 (the game's random, 0..2^31-1; the doubles at
  `0x800E9B20..40`); destroyed (its count `+0xD4` < 1) also id 0 (pitch 0.5, 32000) and id 72 at its place (`0x800074BC`).
  The bank and the calls (2026-10-21): one bank for every level
  (`*0x800EEB04` = `0x8010DD60`, the same in sub-levels 6, 11, 30, 31), so any id plays anywhere.
  It is a libultra ALBankFile: the instrument at `+0xC`, s16 sound count `+0xE` = 131, the ALSound pointers from
  `+0x10`; the lookup `0x8000686C` bounds an id by that count, so a copy of the instrument with more sounds, the bank
  pointed at it, plays new ids. A raw16 wave table (type 1) plays through the wave-table load's own case, no encoder
  needed (`saber.c`'s sounds, ids 0x83..0x8B).
  `0x80007340(id, ch, pitch, vol, loop)`: volume × the effects option, pan 64. `0x8000742C(id, ch, pitch, vol, float
  *pos, loop, near, far)` sets the fall-off `0x800D07E8` / `0x800D07EC` and calls `0x800074BC(id, ch, pitch, vol, pos,
  loop)`: volume × 1 inside near, down to 0 at far, pan 64 + 45 × the point's side of the camera. All end in the queue
  `0x80007128(id, ch, pitch, vol, pan, loop)` (8 slots at `0x80110FE8`, voices `0x80110EE8`; pitch ×2, min 0.05; ch is
  the priority: a full queue drops the lowest); the player (`0x800BF080` / `0x800BF200` / `0x800BF350`) is called only
  from `0x800068A4`..`0x80006C1C`, so a request whose slot is freed (`+0` = `0xFFFFFFFF`) in the frame it was queued is
  never played (`saber.c` drops the weapon click so, 2026-11-16). Dash's death fills it: the game's death sounds 0x21,
  0x4F x2 take the last free slots that frame, a one-shot asked after them by the saber was dropped (2026-11-16). A looped sound (loop 1) lives while requested every game frame (the same id updates
  its slot, the louder of two requests wins); from the second frame without one its volume falls 64000 × dt a frame
  (`0x8018E998`, the frame time) and the voice ends. A one-shot plays out.
  Engines: the player's ship `0x80007340(42, 6, 0.093..0.126 by speed, 21000, 1)` every frame (`0x8009863C`; id `0x2A`
  at `0x800985B4` whatever the model); AI ships by type (`TieF` update `0x8009E978`, `+0x70 & 0xFF`): 1 / 0x10
  `0x8000742C(43, 7, 0.25 − (index % 10) × step, 25000, &obj+0x50, 1, 50, 200)` (far 120 with Skyhook's sector
  record), 4 / 8 with flag 0x1000 id 1. No AI engine sound for the X-Wing, the Falcon or the Outrider.
  The last scene's music is sound 98 (wave `0x8010CC68`, ROM `0x3BB290`: a 7.2 s intro, then a 28.6 s loop; ch 7,
  31000), started by the scene's `Dspt` (`0x8005BB28`, the call at `0x8005ED8C`) through `0x80006CB0("Main")` two VIs
  after the load; a load always starts it at sample 0. The stock Cut 05 plays only its music.
  Slave I's shot (`Boss` update `0x80051610`, `'slav'` → `0x8004DBAC`): one placed sound per shot
  `0x800074BC(11, 4, 0.25, 18000, its first gun point, 0)` at `0x8004E68C`.
- Cut 05 (slot 11, the Outrider over the Gall gorge): only `Anim`, `Bmap` and `Dspt`, no player, no collision.
- **Cutscenes** (2026-10-19, `local/work/cut05_probe.py`):
  - Lines: a blob header's `+0x38` points at a struct whose `+0x14`.. are the scene's line pointers (Cut 05:
    `0x801A1A10`, three lines at `0x801A1A24`..; the last scene: Tatooine's five at `0x801C38EC`.., the hyperspace
    part's six at `0x801C3928`..). They are shown in turn, each held (`~h`, `MSG_HOLD`); the drawn one is re-read
    from the table by index every frame (`0x80115794` holds it only at the draw), so an entry rewritten while its
    line is held shows the new text. A text's speaker code picks its colour: `~0` Dash (orange), `~1` Leebo, `~5`
    Luke (blue), `~7` Leia (yellow), `~9` captions. Writing a fourth pointer after the three does nothing.
  - Cut 05 ends ~130 frames after its last line and the game loads 13 directly (not 12); the next sub-level is
    queued and loaded within one frame (the overlay never sees `0x800D2558` = 2). START skips a cutscene; held on, it
    skips the next one too (Cut 05 → 13 → 14 in a few frames). It skips Cut 05 while a line is held too (`MSG_HOLD` 10 or 5; 2026-10-20). The last
    scene (31) waits after its last line (no next sub-level).
  - 3D: Cut 05's root group `0x80198D90` holds the Outrider (transform `0x80198D00`, scale child 0.5, a 24-part mesh);
    the last scene's tunnel: root → scale 0.05 → four nodes (slots 1–4), the Outrider `0x80199AC0` (16-part mesh),
    the tunnel's at y −400, −370. Transform nodes (kind 13) are 0x48 bytes: w0, w4, w8, count, list (a list of
    pointers), rows `+0x14`, place `+0x38`, slot `+0x44`. Nodes nest: a transform node of ours put between Cut 05's
    root and the Outrider's node (its own slot, `+2` bits 3 set each frame) draws the Outrider and the ships under it
    with both matrices (2026-10-19: the 3D brought before the camera that way).
  - Cut 05's lines are HUD text elements 5, 6, 7 (their texts the table at `0x801A1A24` = `(*0x8013CE30)` + 0x14); the
    scene places one at (25, 161) at its line's time (the others x −1000). Its `Bmap` objects with negative sprite ids
    (−101, −102, −201) draw the line's text and its black box; sprite 0 is the starfield behind everything. `MSG_HOLD`
    = 10 shows the green button (`0x80024600` tests for 10); any other non-zero value freezes the scene without it
    (5 used, 2026-10-19). Its pools written back (as the last scene's) put
    the scene at that moment: its first hold, its flight's start, its space shot (`harness/gallrun/c05_state.py`).
  - A held line (`0x80007A04`, every frame): state 10 is let go while A, B or Z is held (their pad bytes `0x80113098` +0x13, +0x12, +0x11 are 1 while held: not a fresh press, so a button held over from the last let-go lets the next 10 go at once) or when the float `0x800DD2CC` (seconds,
    counted down, capped at 5 shown) reaches 0; the scene sets 10 and 12.0 s at `0x8003D04C`; the green arrow's alpha
    is `0x800DD2CC` / 5 (`0x80024600`). State 1 (a radio line, `0x800078E4`) goes to 2 on A or the timer, 2 to 0 on
    release.
  - What a held line freezes (the Gall Run's end scene, 2026-10-24, from its first held line): the
    objects' own updates stop (bolts stand where they are), but the draw goes on and the game's cull still rewrites a
    node's show byte (`+2`'s high byte) every game frame. A TIE's `TIE_POS` (+0x50) written from outside during the
    hold moves its drawn node (+0x38) one game frame later, exactly; a show byte cleared once is back the next frame
    (only a clear every frame hides it). HUD elements written from outside take effect too (x `-1000`); the game
    places neither 37 nor 51 under the hold. HUD 51's text ("~cMissiles: n") follows `MISSILES` (s16 `0x800E1B54`)
    by itself, about 3 VIs after the count drops (one missile on Z held 4 VIs; 2 VIs fired none on the rail, two in
    the final battle).
  - Time: the scene's classes (`Dspt` think `0x8005BB28`, `Anim` `0x800279D0`, `Bmap` `0x8003CA9C`) move by the game's
    frame time `FRAME_DT` (double `0x8018E998`, set at each frame's start by `0x800B8CF0`), which is 1/60 in Cut 05 at
    30 frames a second; scaled in their class thinks, the scene, its lines' timing included, runs slower. Written from a frame hook it has no effect: the next frame sets it afresh.
  - No scene timer was found (counters go on through held lines). The scene's state is the pools of `Dspt`, `Anim`,
    `Bmap`: written back as read at a later moment, the scene goes on from there (the last scene from its tunnel).
  - Cut 13 (sub-level 31): slot 1 is a 320 × 140 CI8 still of Leia and Luke from its first scene VIs, Luke's face in
    the box (160, 5)–(265, 125), Leia's hand on his shoulder in (140, 92)–(190, 140) (`harness/luke/luke_portrait.py
    --dump`: the level loaded through the debug list's This Level from `play.st`, RAM at scene VI 60).
  - Pictures: HUD sprites in the level's table `*0x8013CE2C`, drawn by the HUD every frame at the place in their
    header (`+0` x, `+2` y; −1000 off), which `Bmap` objects write through `0x80009088(sprite, x, y)` (their draw
    method, `0x8003D1B0`: id `+0xA`, x `+0x1A`, y `+0x1C`, skipped while `+8 & 0x20`). Header: `+4` w, h, `+8`/`+0xC`
    scales, `+0x10` format (`0x1222` CI8, `0x1211` CI4), `+0x18` palette (RGBA5551), `+0x1C` tiles << 16 | 0x20,
    `+0x24` tiles (w, h, buffer; 64 × 32 row by row, the last row as high as what is left; odd rows' 4-byte halves
    swapped). Cut 05: 0 the stars (CI4 160 × 240 at x scale 2), 1 Dash and Leebo (CI8 512 × 140, panned from x −179),
    2 the moon Gall (the brown sphere), 3 the green planet's arc (160 × 178 at x scale 2, the band at the top; the
    three pan in y through the flight, stopping ~clock 480). Neither the `+8 & 0x20` flag nor a header x of −1000
    hides 2 or 3 from Cut 05's frames on (the HUD keeps the last place); a pointer in the table slot does: the arc
    goes with slot 3 on the image's blank still, but the blank (one 64 × 32 tile) leaves a band of other picture data
    where the arc was (2026-10-20). That band is the last picture left in the
    framebuffer: nothing else draws Cut 05's top rows there. A sprite is hidden or blacked out in place by a copy of its
    own 0x28-byte header in the slot with the palette pointer (+0x18) changed: all alpha 0 draws nothing, all 0x0001
    (opaque black) draws a black rectangle of the sprite's size and place (the `Bmap` writes the place into the copy);
    the arc's copy in black covers the band. Cut 05's camera stands still at (0, 0, 0)
    looking along +y through the flight and space shots (one record, `0x80197BA4`): the ships shrink as they fly off.
    The last scene: 0 Tatooine, 1 Luke and Leia (320 × 140), 14 Dash and Leebo (512 × 140, panned from
    x −180) with face overlays 15–17. A still's pixels written in place are reloaded by the game; a pointer put in
    its table slot is drawn.
    The intro (sub-level 0, Cut 00; `level_blob.py` cannot cut it: its ROM entry has no size word) turns Leebo's head over
    its Dash-and-Leebo still (sprite 11, 512 × 140 CI8, pixel-equal to Cut 05's sprite 1) on "Sir, we've made contact with
    the Rebels.": sprite 15 (128 × 92 CI8) patches the still's own head at still + (183, 5) for the whole line, and the
    head, sprites 16–23 (64 or 96 × 70, **CI4**: header `+0x21` 0, a 16-colour palette of 0x20 bytes, rows w/2 bytes,
    odd rows swapped as CI8; `+0x10` reads 0x1220/0x1222 for both depths) at still + (200…207, 13), one at a time (the
    last one's x set to −1000 the same frame), at game frames 0, 40, 44, …, 64 from the line's first frame (30 frames a
    second); 23 stays, and at Dash's next line the game plays 22 … 16 back. Bmap objects 17 → 15 and 18–25 → 16–23 move
    them. Cut 05's sprite table (`0x801A1790`) has 80 slots; the HUD draw (`0x80008778`) walks ids 0..79 in order (a later
    id over an earlier), places from `0x80111110 + 4·id`, skips x −1000 and null slots; slots 8..79 are free. Cut 05
    frame 6 uses them for the same turn.
- Bosses use class `Boss`; the model/kind name is at `+0x78` (`ATST` for the Echo Base AT-ST).
  Their z min/max are 0 and `+0x60` is not health but a state: +0.01 dormant (level start, on
  arrival), −0.01 from the middle of its cutscene on (and after death). Destroyed: bit `0x20`
  in the flags at `+6` (`0x43` → `0x63`) — the wreck stays in the pool. The height is at `+0xAC`
  (18 for the AT-ST, cockpit on top). The real
  health is shown on the HUD as "AT-ST nn%" (address not found yet). Bosses are wrapped in hit
  shells of class `EShd`: a trace to the cockpit centre stops ~5 units short on the shell, so a
  visibility check should forgive hits on `EShd` near the aim point but not on walls (hit = 0).
  Echo Base AT-ST: `Boss` around (−270, −361, 0) in sub-level 5.
- `EShd` shells (class record `0x80112E98`, 0x84 each): `+0x80` the owning boss, `+0x60` health
  (−1: not a target), z min/max, offsets from the owner (`+0x74` side, `+0x7C` up).
  AT-ST: cockpit +15 (hp 5), legs 0..12 (hp 1.25). Xizor's palace gladiator (sub-level 27, `Boss`,
  model `glad` at `+0x78`, height `+0xAC` 5, dormant at (−31, 27, 125) on the rooftop arena; neither
  a written position nor "Villains aren't sleepy" nor writing −0.01 to `+0x60` starts his fight;
  his AI state is the int at `+0x584` (1 dormant), writing 3 starts it): shells legs +7 (z ±7, hp 5 ×2),
  body +18 (hp 5), arms ±4 at +18 (hp 3), head +23 (hp 5). Fighting, the leg shells turn −5 at once.
  Damage goes to `+0x5C4` (750). At 0 he drops (flag `0x20` for a moment), "Jetpack Malfunction",
  health back to 750 and only the head shell (+20) is left: he flies, Dash respawns on the maze
  walls at (31, −34, 123), troopers walk the maze below. His health written 0 does the same (2026-10-29: AI state
  10, then 5 flying only once Dash stands still on the roof). The game puts Dash on the wall only when he dies and
  respawns, again after each death; kept alive, a bomb pushes him into the maze (z 105.9) and he stays there.
  `0x800E1B2C` = 1 written every frame (as the tests do) did not stop his bombs taking Dash's health to 0.
  Fight (2026-10-27, video take): writing 3 puts him beside Dash (state 10 for ~285 VIs, then 0); state 5 he
  jetpacks up and hovers over Dash dropping bombs (his `+0x50` stays at the take-off spot, z sinking slowly; the
  body is drawn ~15-20 higher). His "throw" off the roof is the bombs' knock-back, not a state or timer: they reach
  Humn's message handler `0x8007A29C` as `'shot'` with flag `0x400`, which calls the damage `0x800732D4` and the push
  `0x800693F8`; Dash lands in the maze (z 117.9 / 105.9). That push is an empty stub in this build (2026-11-07:
  `sw a0,0(sp); jr ra; sw a1,4(sp)`), so what throws him is not it (not found; see *The 'push' messages* below). Second phase: he flies around (−12, 11) at `+0x50` z 99–105, below Dash's eye on the wall tops;
  the maze floor (z 105.9, e.g. (−20, 20)) is under him.
- **The 'push' messages and a knock-back of our own** (2026-11-07, `local/work/melee/p3_dash.py`). Humn's handler
  `0x8007A29C`: `'shot'` (`0x8007AD34`; the message `+0x04` sender, `+0x08` flags, `+0x1C` → a direction vector)
  takes the damage (scaled by difficulty `0x8011282A`, and for a `Trop` sender by `0x800D2514`), stores −direction at
  `0x8018DD00` and 0.5 s in the countdown `0x800E0EC0` (read at `0x80072C48`; no motion), and with flag `0x400`
  normalises the direction × 1.5, calls `0x800693F8` (call at `0x8007AF30`) and sends `'push'` back to the sender
  (`0x80026284`). `'push'` to Dash (`0x8007AF5C`): direction × 1.0 to `0x800693F8` (call `0x8007AF80`), then a random
  damage with flash 1. `0x800693F8` is `sw a0,0(sp); jr ra; sw a1,4(sp)`: nothing moves. A knock-back is Dash's
  velocity (`+0x98..A0`, units/s) written once with the airborne flag (`+0x74`: clear `0x04000000`, set
  `0x08000000`): from (0, 25, 10) on `palace.st` his ground speed is cut to 18 at the next update and kept in the
  air, vz falls ~22 units/s², he lands after 0.95 s (57 VIs) 13.2 units on (peak +1.8), `+0x74` bit `0x00100000` for
  a moment, the speed gone 3 updates later. The game asks for no animation for it (the one he was in stays): his fall
  and getting up are ours to play (`diea` falls him backward; played back from its end with a negative speed it may bring him up: not tried).
- Dash's damage `0x800732D4(humn, amount, ?, flash)`: nothing while `0x800DEB78` > 0, Humn `+0x74` & 8 or the death
  timer `0x800E0EA0` > 0 (3.0 at death); the hit flash (a full-screen tint over the HUD) is float `0x800E0DF0` =
  amount × 32, at most 0.5 (stored in the delay slot `0x80073450`), colour s16 ×3 `0x8018DCF8` (flash 1: 255 128 0,
  orange; 2: 10 128 60). `0x800E0DE8` is something else (decays slowly, unrelated to hits).
- Sewers dianoga (sub-level 25, last debug teleport point (672, −8, 95) in its pool): class `Trop`,
  five parts. `+0x74` (for a Trop the kind bits) `0x100` the eye ("Dianoga Eye" on the HUD), `0x200` a
  tentacle ("Tentacle"); its health is the float `+0x7C` (eye 500, tentacle 200; a trooper's `+0x7C` is
  50), `+0x60` is not it. A Trop's AI state is the int at `+0x78` (jump table `0x800ED490`, think
  method `0x800B1FA4` = class record `+0x18`), timer `+0x80`, target `+0x9C` (Dash once awake).
  How a Trop notices Dash (pseudo-C of `0x800B1FA4`, 2026-11-06): state 0 is idle; each time its timer `+0x80` runs
  out it takes Dash as target and wakes if `+0x74` bit `0x20` (alerted, cleared there) is set or `0x800B1384` says it
  sees him: distance² ≤ 2 × `+0x88` and his direction · its facing row `+0x30` ≥ −0.2 (`0x800ED424`; kinds 1 and 6
  see all round), only while `+0xA4` and its node `+0x70` are live. Waking, a kind-0 Trop sends `'nois'` (its
  position) to every Trop (`0x800262FC`) and plays a shout, then state 2 if `+0x74` bit `0x10` is set, else state 1.
  Otherwise state 0 starts again (`0x800B04B8(trop, 0)`).
  How an awake Trop closes in (pseudo-C of the think, of the state switch `0x800B04B8` and of the Trop update
  `0x800B2FA0`; a RAM run on `palace.st`, Trop 0 alerted, 2026-11-08, `local/work/melee/d3_chase.py`):
  - Bit `0x10` ("closer"): Dash's update `0x80074FA4` calls `0x800B62BC(6, his place)` every frame, which clears it on
    every Trop and sets it on the 6 live ones nearest him (a `'clos'` message sets / clears it too). Only a closer walks.
  - Fields (the same on every palace Trop): `+0x88` 900 (30²), `+0x90` 225 (15²), `+0x94` 2025 (45²): squared
    distances. The range test `0x800BAF2C(d², 0.8)` is d < 200 × (0.8 − 0.1) = 140.
  - The think turns it to the target each frame (`0x800B12CC`: wanted yaw `+0x98`, returns its facing · the target's
    direction, "dot"). State 1 (stand and aim, block id 3, timer 1.5–2.5 s): at the timer's end, in range and
    dot > 0.98 → state 3.
  - State 2 (walk): the update plays id 1 `trTr` and moves it along its facing at 5.0 units/s of game time (measured
    4.98; `trTr` has no root motion), turning toward `+0x98`. Entering state 2 sets the timer to 1.0–2.0 s (random); no
    distance ends a walk. At the timer's end: d² < `+0x90` or d² < `+0x94`, in range and dot > 0.98 → state 3; else
    d² > `+0x88` or not a closer, and dot > 0.98 → state 1. Bit `0x200000` is set while dot > 0.9; the update's stuck
    check (moved under half the expected step, or `0x800B0384` blocked) sets `0x100000` and a random side bit
    `0x1000` / `0x2000` (the next walk aims 30 units to the side of the target).
  - State 3 (shoot, id 2 `trSh`): the timer 1.0–2.0 s; at its end d² > `+0x90` (beyond 15 units) → state 2, else 0.1–0.6
    s more shooting. So inside 15 units an awake guard never walks again: it stands and shoots.
  - Measured: from 12 units it woke as a closer at 1.26 s (game clock), walked 1.05 s (5.67 units) to 6.36 and shot from
    there for the rest of the 8 s; from 30 units: walks of 1.0–1.5 s between shots, 30 → 24.4 → 17.1 → 10.65 in 8 s.
  More of the Trop (2026-11-09..11, `palace.st` and the duel, `local/work/duel/` probes):
  - Heading: facing = (−sin h, cos h) of `+0x14` (heading 0 walks +y); a heading set by hand needs the rows `+0x20` /
    `+0x30` written with it, and the think turns a hand-set heading back to its target.
  - The turn: the update steps its heading `+0x14` toward `+0x98` (written straight by the think's `0x800B12CC`, no rate
    there) as step = clamp(`+0x98` − h, ±40°) (the ±40 as `lui` words `0x4044` / `0x4220` / `0xC044` / `0xC220` at
    `0x800B4F08..0x800B4F40`; the clamp skipped in state 3 of kind 0), then h += step × 4.0 × dt (`lui at, 0x4080` at
    `0x800B5008`, the gain, also on `+0x18` / `+0x1C`): walking at most 4 × 40 = 160 °/s with a proportional tail of 4/s;
    in state 3 4 × the difference (596 °/s measured at a 150° step). A code constant, as the walk's (the duel writes
    14.0, `0x4160`: 560 °/s, on 33 only, and 0.0 while it turns her by hand).
  - The update's gate: it returns at once (`0x800B323C..0x800B3244`, to `0x800B5774`) unless its Dfob `+0x70` has
    `+0x68` bit 2 (linked into a zone): no animation, move, turn or stuck check; the think is gated on `+0xA4` / `+0x70`
    the same way. Each update its zone find (`0x8000C220`, call `0x800B3CE8`) writes `+0xA4` (`0x800B3CF8`) and its last
    call `0x8005AE74(Dfob, place, zone)` (`0x800B5634`) links the Dfob into that zone (through `0x8005AAF0`: `+0x60` /
    `+0x64`, `+0x68 |= 2`, its root shown) or, with zone 0, unlinks it (`0x8005AB90`). The frame dt (`0x8018E998`) has a
    floor (0.02, `0x800B8E84`) and no ceiling: one long frame (0.44 s measured, from a harness park) gave a running
    Trop one 5.9-unit step out of every zone, the zone 0 unlinked its Dfob, and nothing in the game links it again:
    the Trop stood frozen for good (the duel calls `0x8005AE74` with its last live zone after the long frame).
  - The closer bit `+0x74 & 0x10` also gates its animation: in AI states 0, 1 and 3 the update advances the animation
    (`0x800170F0`) only with it set, and only the closer pick `0x800B62BC` (over the Trop record's own pool) sets it: an
    object run by the Trop methods outside that pool stands frozen before its first shot (its fire waits on the
    shooting animation's wrap) unless the bit is set by hand.
  - The walk's speed is one code constant, the `lui at, 0x40A0` (5.0) at `0x800B3784` in the update `0x800B2FA0`
    (state 2), × 0.7 for kind 2 (`0x800ED4F0`), × 1.6 for kind 1 (`0x800ED4F8`); the other `lui 0x40A0` of the Trop code
    are not the walk. Written at run time (the duel: `lui at, 0x4100`, 8.0, on 33 only) it moves every walking Trop.
    Written `0x0000` (0.0, what the update gives its other states at `0x800B3794`) the walk state takes no step: the
    duel holds it so while it writes her place by hand (with the step on top her drawn place ran 0.3–0.4 a frame ahead
    of the place written).
  - What pushes the player off a Trop (pseudo-C of `0x80026A94`, 2026-11-12, `local/work/duel/trophold/`): the Humn's
    update calls the touch search `0x80026A94` at `0x80078B44` and moves himself out by the penetration + 0.25 (vector
    add `0x8000DADC` at `0x80078C70`). The touch skips a class record without flags & 2 and an object whose radius
    `+0x60` is not > 0 (its first test); no object `+6` flag is read. The Humn's one exemption (no move,
    `0x80078BCC` / `0x80078C04`): a `'Trop'` with `+0x74 & 0x300` (the dianoga's eye / tentacle) and a `'Boss'` whose
    `+0x78` is `'IG88'`. The Trop update rewrites its `+0x60` each frame only while it is > 0 (`0x800B3CB4..0x800B3CD4`:
    the kind's radius, 0 in dying state 6, scaled in state 5), then runs its own touch (`0x800B3D30`) and moves itself
    back from what it touches; the bolt hit `0x80026480` has the same two gates. So the game has no per-object
    collision flag: it switches a touch off by the radius's sign (IG-88 negates his while the player is near, a dying
    Trop gets 0); a radius written negative stays (−2.80 held 334 VIs) and pushes nothing, both ways. Refuted as
    switches: the class record's flags & 2 cleared (the Trop's own touch then stops it 4.66–4.71 short of the player);
    `+0x74` `0x100` / `0x200` (they send its think `0x800B1FC0` and update `0x800B2FD4` into the dianoga's branches;
    `0x200` sends `'Spik'` to the Humn on touch, `0x800B3DC8..0x800B3E04`). The lock-on test that reads `+0x60 > 0` as
    alive drops such a Trop: a Trop's health is `+0x7C`.
  - That push is 3D (pseudo-C of `0x80026A94`, 2026-11-15): the out vector is his place − (the other's x, y, and his
    own z clamped into the other's `[z + +0x68, z + +0x6C]`), normalised, scaled to the penetration + 0.25
    (`0x8000DD98`) and added to his place (`0x80078C70`); its z part over 0.1 (`0x800EBC78`) clears his `+0x74`
    `0x08000000` (air). With the two on one floor and his z a hair under hers the vector dips a little: harmless in
    play (one push moves him out of reach, the floor catches him), but a player pinned in x, y alone (a harness
    writing `+0x50` / `+0x54` each frame) while a Trop stands on him is pushed down every frame, more as the dip grows:
    the duel, Luke at z 123.43 with Guri 0.6 off, 123.07 → 121.0 → 114.8 in four frames, through the floor; the
    ledge hang then caught him under it (`g_hang_state` 1, his lock and fire off for good).
  - The Trop update's body push (2026-11-14, the duel's leap): in every AI state but 0 its collision block
    (`0x80026A94` and the walls' push `0x8000D108`) holds a body sphere at its z + its root node's height (`+0xB4`, the
    update's local), radius `0x800ED520` (2.8 for kind 0; the step 1.1 × it in state 2), so a Trop whose root comes
    under ~1.8–1.9 over the floor (lying, rolling) is pushed up; above the floor by more than 0.02 (`0x800ED52C`) the
    airborne branch then falls it a frame. State 0 skips that block (z 0.000 through a forward roll).
  - A z written by hand is kept: the update falls it by its fall speed `+0xA0` (`+= 30 dt`, z −= dt × it, 0 on the
    floor: `0x800B4CF0..0x800B4DF8`), 0.02 → 0.30 a frame over 15 frames; written each frame with `+0xA0` held 0 it
    stays the written one less ~0.02.
  - A `'shot'` switches a Trop's block at once (state 4 and its `play` of `trOu`), whatever block runs; its state's
    `set_anim` (`0x80017764`) plays its block again whenever the pick `ctl2` (`+0xD4` / `+0xD8`: {time, list index})
    names another list entry, so a block of one's own kept through a held state needs that pick kept too.
  - Its blocks (the guard's `trSt` 30 keys 2 fps wrap, `trTr` 15 / 15 fps wrap, `trSh` 8 keys wrap (state 1 id 3 at
    0.5 fps, state 3 id 2 at 12 fps), `trOu` 21 / 15 fps (state 4's 1.0 s ends it: keys 0..14 seen), `trDi` 23 / 15 fps
    clamp): the same 17 bones in the same order; the AI reads only the tag, keys, frames and wrap / clamp. Root motion:
    the place moves by the root's sampled x, y change (`trDi` slides her back 5.18, `trOu` 0.34; `trTr` sways, net 0):
    the walk's speed itself is code.
  - The fire, `0x800B1560(trop, target pos, gun = +0x74 & 0xF)`, is called on every frame of state 3 (`0x800B2C98`);
    inside it fires only while its animation mode `+0xB8` is 1 and the block's frame wrapped below `+0x84` (it writes
    the frame there on each call: the first update after `trSh`'s 8 → 1), aims heading and pitch at the target with a
    random spread (4.5° Easy / Medium, 1.0° Hard, ≤ 8°), and with the pitch outside ±45° or no line of sight
    (`0x800654A0`) does not fire and side-steps (state 2, a side bit). The shot is one `Blst` bolt,
    `0x80031FE0(dir matrix, pos, sector, a, b, c, damage × scale, flags, owner)` at `0x800B1EB4` (*Known hook points*),
    from the gun table `0x800E6600` (0x14 a gun; gun 0: flags 0, damage 10, 5.0 / 200.0 / 30.0) × the level's scale
    (*Other `LEVEL_ID` users*); the bolt keeps its owner at `+0x64`, live bit `+0x60 & 0x10000`.
  - A Stunner ring's `'frez'` puts a Trop of kind 0 / 1 into state 8 for 10.0 s (`0x800B58D0` → `0x800B04B8(t, 8)`;
    kinds 2–4 and states 4–7 ignore it), with no effect drawn; Humn has no `'frez'` handler. A `'shot'` from any
    sender staggers a Trop (state 4) at any damage.
  - The Trop messages method's `'shot'` case (`0x800B59CC`, measured 2026-11-15 on the duel): first it leaves at once
    for a Trop in state 5, 6 or 7 (`0x800B59E8 lw v0, 0x78(s0)`, `addiu at, zero, 5`, `beq v0, at, 0x800B62A8`, ...;
    the exit `0x800B62A8`), then a line-of-sight test (`0x800654A0`), then the damage off `+0x7C` (`0x800B5AD0` /
    `0x800B5AE0` / `0x800B5AF0`), and only then the sender-tag compares: `0x800B5B60` picks the hit sound's path (both
    meet at `0x800B5BB8`: health > 0 -> state 4 unless the message flags' low nibble is 2, else state 5), `0x800B5C40`
    (that nibble 2 only) sets the floats `0x800E5EA4` / `0x800E5EA8` and `0x800B5C78` goes on to the `'Hlth'` /
    `'DSPK'` sends. So the "friendly" compares skip neither damage, stagger nor death; the state 5/6/7 exit skips all
    three for any shot (a laser bolt still collides with the Trop and is used up). The duel takes it for Guri while
    she is shut (*Known hook points*: `0x800B59E8`).
  - `0x800B04B8(t, 4)` on a Trop already in state 4 restarts the stagger: its block's pick time `+0xD4` goes back to
    0 with no jump in place (the root drifts ~0.3 back over a stagger).
  Main code never reads the "Villains aren't sleepy" word `0x800DD2C4` directly (only the
  debug list's table at `0x80025D74` and a store at `0x8001417C`).
  The game draws no running countdown: `%d:%d%d:%d%d` (`0x800EA394` and others) is printed only by the best-times and
  Level Complete screens, through HUD text elements (`0x80009088` place, `0x80009138` colour, `0x800091D4` text).
  Dianoga parts only think while `+0x74` bit `0x400` is set: asleep they sit at the anchor
  `0x800E5EE8` (672, −10, 31) + 30 as a still "flower", take no hits and nothing in the harness wakes
  them (teleports, diving, the route's triggers, "Villains aren't sleepy"); XOR `0x400` into all five
  and the fight starts (`local/states/sew_dianoga.st`, made so by `states_make.py dianoga`). Teleport point
  (672.0, −7.6, 101) is the third of sub-level 25; ~10 s after arriving the game sets bit `0x20` on the five parts
  (`0x111` / `0x211` → `0x131` / `0x231`), 30 s of swimming there never set `0x400`. Woken, the eye moves off at once. Awake, the eye rises to z ≈ 116–126, ducks into the
  mouth (≈57), tentacles grab Dash and drag him into the mouth. HUD boss bar: model tag at
  `0x8018DDF4` (`ATST`, `DEYE`, `DSPK`, `IG88`, `boba`, `glad`, `load`, `slav`; names picked at
  `0x8006CBA8`), fraction at `0x8018DDEC`. Dash swims there: Humn flags `0x400` (+ `FL_AIR`, `0x200`;
  A swims up and adds `0x100`), the stick works as on foot.
- Ord Mantell IG-88 (debug Next Level from the train: level id `0xA`): also class `Boss`, model
  `IG88`, but built like an enemy: z min/max 0..8 and `+0x60` = +2.5 while alive, −2.5 once dead
  (flag `0x20` at `+6` set too). His real health is the float at `+0x5C4` (750 = the HUD's
  "IG-88 100%"). `+0xAC` reads 5. The lock-on tells the two kinds apart by the z extent.
- The `Boss` class and its AIs (read 2026-11-10/11, the stock ROM: `om_ig88.st`, `xiz_glad.st`, `gall_boba.st`,
  `palace.st`; pseudo-C with `harness/decomp.py`):
  - One class record `0x801129E8` (main data) on every level, methods think `0x800512EC`, update `0x80051610`, draw
    `0x80052174`, messages `0x800523F8`; the senses table `0x800D06C0` (run by `0x800054FC` through a jalr). Every
    function they reach (182) is main program (< `0x800D06E8`): no level overlay, no read of the level id. The methods
    branch on the tag at `+0x78`: `IG88` think `0x80047954`, update section `0x8004BCE8`, animation descriptors
    `0x800DE978`; `glad` `0x80049AA4`, `0x8004F100`, `0x800DDBC0`; `boba` think `0x80048BE4`; shared: the state
    setter `0x8003FDB8` (one switch per tag; a hit's damage: the shot handler scales it into a pending `+0x748`, the
    frame's max, and the update near `0x80046634` caps it at 50 / 45 / 30 on difficulty 1 / 2 / 3 before it leaves
    `+0x5C4`, 2026-11-16), damage `0x800465E0`, the touch hit `0x8004699C`, the shot handler
    `0x80052E4C`, the path search `0x80005C24` (nearest node) / `0x800057A4` (route), the node pick `0x8003F958`.
    There is no create method: Boss objects come from a blob's class header at load; a level whose list holds the
    record with count 0 (sub-level 26) gets one only by a count and a pool written after each load (the loader writes
    0 again).
  - The instance (0x7C8): AI state `+0x584`, fire mode `+0x550`, sub-state `+0x6EC`, counter `+0x58C`, the player's
    distance `+0x5E0`, move speed `+0x5C0`, stagger `+0x6F8`, health `+0x5C4`, the zone `+0x70` (recomputed each update
    from the place by `0x8000C220`), Dfob `+0x74`, the animation state `+0x80` (chain `+0x90`), controller `+0x6E8`,
    his one shell `+0x514` (EShd), the Humn `+0x5C8` / `+0x5F4`, his path graph `+0x7B8` (node count `+0x7B4`), the
    path segment's target `+0x6C4` (xyz) and remaining length `+0x6E0`, his node `+0x7BC` (the previous `+0x7C4`), the
    edge's jump flag `+0x7C0` (bit 0: state 9). His Dfob: `+0x84` the model root, `+0x68` bit 2 needed by think / update
    / draw, `+0x98` the boss, `+0x9C` the Info that gets `'Mort'` at his death (the send skips a null). A mesh's draw
    stamp `+4` past the frame counter (after a reload) keeps that mesh undrawn.
  - IG-88's AI (level 0xA): state 0 runs node to node at 12 u/s (`IWLK`, turns in place 370–520 °/s), 5 stands and
    fires within 20 (his walk ends at the node nearest the player, 6–9 off), 9 jumps (10 u/s up to 20 high), 0x10
    flies off at 24 u/s (after a hit, odds 1 − health / 500 clipped to 0.1..0.7). State 0 picks a node only from a
    path segment whose target is his own place, remaining 0 and no jump flag. His graph: 148 nodes of 0x6C (8
    neighbour indices, 9999 none; 8 edge lengths; 8 jump flags at `+0x40`; place `+0x60`), no pointers inside. The
    route caps it at 150 nodes: its work buffer `0x8018D4A0` (12 B a node, `0x8003FA2C`) ends at the nearest list
    `0x8018DBA8` (`0x8003F97C`); more overwrites that list and the Expl ring heads `0x8018DC80`. The flight picks
    random nodes until one is >= 40 units off (`lui 0x4220` at `0x80042054` and `0x80043FBC`): in an arena where no
    node is that far from some place the do-while never ends and the game hangs. His bolt: in the update's case 5
    (fire mode 1, a stream ~2 spawns a game frame) `jal 0x80064584` at `0x8004C278` (an Expl: kind, muzzle, 0,
    velocity; owner him at sp + 0x18); at the stock rate he took the player 100 → 6 in ~4 s. The touch hit (end of the
    update, every frame): the player within 6.0 (`+0x5E0`; the `lui 0x40C0` at `0x80046A04`) → his radius `+0x60`
    negated (no push) and `'shot'` 0.5 to the player, else the radius positive again. His end: state 3 runs a death
    camera (`0x80009648(9)`), state 4 sends `'Mort'` to the Dfob's `+0x9C` and his think sends `'LEnd'` to the Humn
    every frame in state 4 (the Humn writes game state 3 on each, `0x8007A978`, over any stage end). The setter's own
    case 0xB runs the death camera too, but 0xB written straight into `+0x584` holds him: no think case runs, his
    update still plays his chain's current block and he stays drawn. Model 37 nodes (17 animated bones + an unanimated
    gun node, joints 5.24 high, the left arm one segment with no forearm), 11 blocks (`IWLK ISTD IAIM ISHT IFLM IHIT
    IOFF IRSE IFAL ILND IDIE`, 88 KB), all in level 0xA's blob. Seen in RAM: a stiff, robotic gait and turns whatever
    blocks he plays (it is his code's speeds and turns).
  - Boba Fett (sub-level 15, `gall_boba.st`: `gall_6b.st` + 4 debug Teleports, the 4th onto his pad; the game starts
    his fight itself, `'Mst1'` → state 10, a cutscene with `'view'` to Slave I): no graph (`+0x7B8` 0), an arena box
    `+0x5A4..+0x5B4`; 12 blocks, none a walk (`BCSH BHT2 BHIT BFLM BMIS BSHT BLND BHVR BFAL BRSE BOFF BSTD`): he never
    walks; jetpack up (`BOFF`, `BRSE`), flies / hovers 10–14 u/s, lands, stands 1–4 s, fires 3–5 s (missile far, flame
    near), off again; every other landing 3–10 units from a standing player; hit: `BHIT` / `BHT2`, a cooldown 2 + 2 ×
    (difficulty − 1) s, then by a health chance into the air (9), else fire (5) or a pause (12); death 11 → 3 → 4
    (`'Mort'`, `'wake'` to Slave I). Skeleton 18 bones, joints 5.05 high: the most human one.
  - The gladiator droid (27, `glad`): rises 8.5 s (state 10, `GRSE`), then state 0 walks round the player at ~9–10
    units at 8–9 u/s, stands (5) 3–28 s dropping bombs; 5 blocks (`GRSE GDIE GDUP GDWN GWLK`), 15 bones, 19.3 high.
    His arena (2026-11-12, stock 27, `xiz_glad.st`): a round room centred (31, −34), the rim wall at radius 73.6
    (vertical to z 159.6, a dome to 191.4), the floor four sliding panels (75 square, one per quadrant: zones 0x4B /
    0x45 / 0x44 / 0x46, collision a zone's prop 13 group under prop 14's transform, drawn under prop 15's) at z 123.45
    over the maze (floor 105.5), the centre the lift's top (zone 0x5F), one opening (his alcove north-west, zones
    0x4C / 0x4A / 0x49). The floor opens only on his first fall: his Dfob 41's `+0x9C` is Info 24 (`0x801BF3BC`),
    whose keyframe 1 list (`+0xCC`) sends `'GtoN'` to the four panel movers (Info 25–28: `0x801BF544` NW, `0x801BF6CC`
    NE, `0x801BF854` SW, `0x801BF9DC` SE), which slide them 95 units out diagonally under the roof (the collision rides
    with them); its keyframe 3 list sends `'LEnd'` to the Humn (27's Level Complete, game state 3). The closed panels
    sit where the movers leave them (NW (−6.509, 3.488), NE (68.498, 3.479), SW (−6.518, −71.509), SE (68.479,
    −71.528)), not on the exact quadrant lines: along x 31 and y −34 gaps of ~0.01, where a standing Trop whose zone's
    panel misses the point falls into the maze (a player walking across does not). Their collision parts
    (`0x80200B3C`, `0x80200C9C`, `0x80200CF4`, `0x80200D4C`, kind 7 strips, 48 pool vertices shared between them only at
    equal local places) are plain data in the blob. The lift's top (zone 0x5F: its moving collision, prop 0xF, part
    `0x80200328`, a 16-gon of radius 10.28 at local z 122.95 under a transform at (31, −34.01, 0.5); its static, prop
    1, the shaft's floor at z 34.5 out to 10.4) and the panels' notch round it (a 16-gon of radius 10.4) leave a ring
    0.12 wide with no floor at the arena's height: a walking Trop's ledge probe `0x800B0384` (1.5 ahead, 2 up, the
    floor `0x8000C220` finds from its sector: its own zone's first, else the highest of the neighbours' (+0xBC list)
    below; blocked by a drop > 4 or a found zone with flag 0x200000; a blocked kind-0 Trop goes to state 1, a kind-2 one
    side-steps) leaving the lift's top finds the shaft's floor there and stops.
  - The Info class (the level's movers; record `0x80112B38`, 0x188 each, 27's pool `0x801BCEFC`; think a stub
    `0x8007C6D8`, update `0x8007D3B8`, messages `0x8007DB0C`): a keyframe track `+0xB8` + 0xC i {value, wait (−1 stop),
    message list}, state u16 `+0xA0` (0 idle, 1 wait, 2 / 3 forward / back), keyframe u16 `+0xA2`, value `+0xAC`, speed
    `+0xA8`; in state 0 `'Mort'`, `'Trig'`, `'Entr'`, `'ZHit'` start the next keyframe, `'GtoN'` / `'GtoP'` next /
    previous, `'Mst0'` / `'Mst1'` set / clear `+0xA4` bit 31 (off / on). A list is {object, tag, word, next} entries,
    sent by `0x8007C360` through `0x80026284(object, &entry[1])`.
  - The game's on-foot AIs are four: the Trop think `0x800B1FA4` (palace guards, sewer guards, stormtroopers,
    snowtroopers, the wampa as kind 2: its closing distances `+0x90` / `+0x94` 25 / 36 squared, a trooper's 225 /
    2025), and the Boss tags `IG88`, `boba`, `glad`. No officer, swoop-gang or other human class fights on foot; Xizor
    and Vader never do.
- Boss and target bars (2026-10-14):
  - On foot (`0x8006CB84`): shown while the float timer `0x8018DDF0` > 0; name by the model tag `0x8018DDF4`
    (e.g. `slav` -> "~o~cSlave 1" at `0x800D1E0C`), fraction `0x8018DDEC`; elements 0x38 (name, (160, 190)) and
    0x39 (percentage "~f3~o~c%d%%" `0x800EB598`, (160, 200)), yellow (255, 255, 0), alpha = timer x 255 / 2. Not
    run in ship levels.
  - The on-foot bar is driven only by the message `'Hlth'` `{u32 'Hlth', u32 tag, f32 fraction}` sent to the player
    (2026-11-11): the Humn's message handler `0x8007A29C` (case at `0x8007BAE4`) is the bar's only writer: tag =
    msg[1], fraction = the float at +8, timer = 2.0 s. The HUD function `0x8006A3C4` counts the timer down by the
    frame time and, at <= 0, moves both elements to (-1000, -1000); nothing else hides it (a boss's death shows "0%"
    and fades the same 2 s). The sender: `0x80026284(0x8002620C('Humn', 0), &msg)` (object 0 of the class, its
    record's `+0x24` messages method). The Boss damage (`0x80046840`) sends it on each hit that changes health
    (old != new, old >= 0): its tag `+0x78`, health `+0x5C4` / (500 + 250 x (difficulty u16 `0x8011282A` - 1)),
    0.0 once < 1; the Dianoga (`0x800B58D0`) to its attacker. The name is picked from a tag list at `0x8006CBA8`
    (`ATST`, `DEYE`, `DSPK`, `IG88`, `boba`, `glad`, `load`, `slav`); another tag leaves element 0x38 the stack
    buffer's leftover text. The texts are written inside the Humn's think (`0x80070ED0` -> `0x8006E374` ->
    `0x8006A3C4`): a write in a draw method after it (e.g. the Humn draw `0x8007A118`) sticks for that frame.
  - Ship levels (Skyhook's Star Destroyer; code at `0x80096920`, in RAM only, not in the ROM's boot code):
    target by s16 `0x8018E460` (1 "Reactor Core" `0x800D1DB0`, 100 "Star Destroyer" `0x800D1E2C`, else
    "Turret" `0x800D1EBC`); element 0x34 the name at (160, 190), 0x35 the percentage at (160, 200), both
    yellow (255, 255, 0), alpha by the float timer `0x800E1808`.
  - The HUD text setter `0x800091D4(id, text)` copies into the element's buffer `(*0x8013CE30)[id]` and does
    nothing if it is null: a level only shows the ids it gave buffers. Asteroid Field: none for 0x38/0x39;
    0x34 is its "TIE Fighters: n" count; 0x22 and 0x35 are spare 48-byte buffers ("aaaa...", off screen).
    The level's HUD update hides its spare elements each frame: set them again at the draw (a draw method).
- Player ship `Stft` in ship levels (2026-10-14):
  - `+0xAC` bit 0 = carried: the update (`0x8009B0D0`) copies the carrier's matrix (`+0x20..+0x5C`) from the
    object at `+0x220` (Asteroid Field: `Chor`; Skyhook: 0, the ship flies itself). The model root's matrix in the
    draw method (`0x8009C318`) is Chor's place at the draw, after Chor moved that frame: a place derived from Chor's
    place in the frame's update is off by Chor's step at the draw (2026-10-16). Cleared in Asteroid Field
    the ship flies on its own as in Skyhook (stick x rolls, y pitches, A thrust); `+0x220` 0 hangs the game.
    Its matrix rows: `+0x20` right (= forward x up), `+0x30` forward, `+0x40` up, `+0x50` position (`+0x08`
    a copy).
  - A free ship is kept within the float at `0x800EC9DC` (12000) of the level's origin: put on that sphere if
    further (one frame, then it flies on from there).
  - Skyhook: all `Trak`s target the Stft (`+0x8C`), camera entry 6 on Trak 0: ~100 behind, 20 over, turning
    with the ship. `Trak +0x98` is that height over the target (Skyhook 20, Asteroid Field 0); `+0x60` the
    distance.
  - Stft `+0x08` position; `+0x14/+0x18/+0x1C` yaw/pitch/roll in degrees (facing = yaw + 90), made from the
    matrix rows every frame: write the rows, not the angles.
  - Collision with level geometry (Skyhook, `local/states/sky.st`, 2026-10-15): a free ship
    (`+0xAC` bit 0 clear) is kept off the Star Destroyer (mesh `0x801A58A0`) and the station by two tests in the
    update, both against the sector record at `+0x224` / `*0x800D2400`:
    - Sphere push `0x8009B584`–`0x8009B964`: two points 1.5 ahead and behind the centre along forward, each through
      `0x8000D108(region, point, radius, 0, 0, ship)` (moved out of the region's type-3 and type-8 nodes; needs
      `*0x80112824` bit 0). Radius `+0x60` / 15 × 1.1 node units (Skyhook: 23.5 world units). If a point moved
      and the new heading turns more than 45° (dot < `0x800EC9F0` 0.707): health 0 unless Invincibility
      (`0x800E1B2C`); else sound `0x54` and health −(10..20). The centre goes to the points' middle, the
      heading and matrix are rebuilt (`0x8000F624`).
    - Segment trace `0x8009B468`–`0x8009B4F0`: old → new position through `0x800654A0(old, new, *0x800D2400, …)`;
      a hit puts the ship back and sets health 0 (unless Invincibility). At 500 units/s the sphere already
      holds the centre ~24 off, so the trace was not seen firing.
    - Measured: speed 388 → 500 units/s in ~1 s; head-on or > 45°: destroyed at 23.6 from the hull; 10–15°:
      slides along it at 24–38, 10–30 health a graze; with Invincibility a nose held into the hull slips through.
    - Sector records: `*0x800D2400` is the first of a list (linked by `+0xB8`, written at level load
      `0x800182F4`): `+0x04..+0x0C` centre, `+0x10` flags, `+0x18…` a 0-ended byte list of types, `+0x38…` a
      pointer per type (`0x80017A78(rec, type)`). Skyhook has one (`0x801A1C64`): type 7 the records to test,
      types 3, 9, 0x1A the node `0x801A50B8` (scale 16) over the Star Destroyer and station meshes.
      `0x8000BEE4(pos)` picks the nearest record; `0x8000C4A8` stores it in the ship's `+0x224`.
    - Collision data is the mesh parts' words that `mesh_image.py` clears: `+0x00..+0x14` box, s16 `+0x18`
      count, s16 `+0x1A` kind (3 triangles, 4 quads, 5/7 strips, u32 lengths at `+0x1C`), `+0x20` u16 indices
      into the level's one vertex pool `*0x8013CE28` (float xyz; reach up to pool + `0xBFFF4`). The walkers
      (`0x80004574` trace, `0x80003FF4` sphere) go down nodes with bit `0x4000` in the first halfword and test
      leaves `0x3064` (box, then primitives `0x80003A28`).
    - Asteroid Field has no record (`*0x800D2400` = 0, `+0x224` = 0): a free ship flies through anything. The
      pointer is also a level-mode switch (79 reads in the main program, ~50 in the Stft code, several in TieF):
      a record of ours put there in `ast.st` (Skyhook's hull rebuilt at `0x80700000`, the pool repointed) made
      the ship take hits far from the hull and hung the level within a second. Not reusable for a hull of ours.
  - Class records and the per-frame class loop (2026-10-18): a class
  record (`0x80112B08..`, 0x30 apart: `+0` tag, `+8` object count, `+0xC` object size, `+0x10` pool, methods `+0x18`
  think, `+0x1C`, `+0x20` draw, `+0x24` messages; set at boot, `0x80010850`) is run by `0x80025D6C` each frame for every
  record in the level's null-ended list `*0x80112830` (Asteroid Field's lists 41 classes, most with count 0, `PRBT`
  among them): `count` objects from `pool` by `size`, `+0x18(obj)` unless obj `+6` & 0x1000. A record given a count and a
  pool of ours runs them.
- Gun towers, class `PRBT` (record `0x80112C28`; code in the main program `0x800819E4..0x80084600`; Skyhook `sky.st`: 4,
  pool `0x8019F6B0`, at its arms' ends): `+8`/`+0x50`/`+0xE0` place, `+0x14` yaw (degrees), `+0x20` 4x4 (rows, then the
  place), `+0xB0` its copy the draw sets the node from (`0x8000FE48(+0xF0, +0xB0)`), `+0xF0` its node (Skyhook: transform
  `0xD0650003`, its group `0x801A5640` a child of the world root, the model one mesh `0x801A5960`, 95 x 115), `+0x140`
  flags (0xF standing; 0x10 shot down: the draw hides the node), `+0x188` state (0: think and draw return), `+0x1A4` its
  health (float 40, healing back ~7 a second: the add's store `0x80082494` `swc1 $f8, 0x1A4($s0)`, rate
  ((difficulty − 1) × 2.5 + 5) × frame time, when `+0x140 & 8`; `0x800824CC` clamps to 30 + 10 × (difficulty − 1)). It aims at `0x80026130('Stft')`, sends `'TurW'` ("Turret Range Warning": within
  2500, dist² < 6 250 000 at `0x80082D7C`, every frame; the ship's handler `0x8009D024` sets float `0x800E1B34` = 0 and the tag
  u32 `0x8018E868` = `'Turr'`; the HUD update `0x800959EC` shows element `0x36` at (160, 180), its text by the tag, `'TBmb'`
  "Incoming Bomb!") and,
  shot down, an explosion, `'dHIT'`, `'kTur'`; its set-up (`0x800823F8`) and shot-down branch (`0x800824F4`) run only at
  |x| > 2000. The player's lasers hit it (the game's own test). The missiles' target search (`0x8007E718`–`0x8007E9C0`)
  walks the towers by the record's count (+8) and its pool at +0x28 (not +0x10): a record given a pool needs both, or Z
  faults at `0x8007E76C` (2026-10-19). With +0x28 set the view key (R, L, C-right) no longer hangs either (2026-10-20); the
  R hang's own path was never read.
  Its bolts (2026-10-22, `respawn_probe.py --muzzle`): every new one starts **100.0 straight above
  `+0x50`** (123 of 123; ~107 out a game frame at 3000 / s, aimed 2.4–3.6° off the line to the ship).
  Rammed (`plow`): the handler `0x80084528` takes it only from `Spdr`, with `+0x188` != 0 and `+0x140` bit 0x8 clear:
  `+0x1A4` −= 2 × D × f (D 10 / 30 / 50 by difficulty `0x8011282A` 1 / 2 / 3), at ≤ 0 `0x800819E4(obj, 5)` (shot down),
  an `Owww` reply. Bit 0x8 (set by Skyhook's template) is read beyond that gate: the think `0x800822F0` (`0x800823B4`,
  `0x80082430`: clear jumps to another branch at `0x80083254`), the fire functions `0x800832A4`, `0x8008332C`, `0x800833CC`,
  `0x80083548`, `0x80083DC0`, `0x80083EF0`, and in the handler `die!` (set: −`0x800EC1A0`, never blown up), `shot` / `prox`
  (set: damage only at |x| > 2000) and the `dHIT` panel message (`0x80084610`, `0x80084A44`, `0x80084AE4`, `0x80084C04`).
  Hoth's ram, the snowspeeder (`Spdr` `0x8008F6E4`, its hit at `0x80090AF8`): `0x80026A94` gives the object and the
  contact normal (from the target's axis point nearest the speeder); f = |its forward row `+0x30` · the normal| (no
  speed in it); its own health `+0x204` −= f × {ATAT 300, ATST 150, EShd 300, PRBT 50, Spdr 20, rbgn 100}, then `plow`
  {`plow`, `Spdr`, the speeder, f} to the target. On `lvl0.st` (difficulty 2) a probe droid (PRBT) rammed head on: 30 →
  −17.10 and destroyed, the speeder 110 → 70.75 (f 0.785 both). ATST's `plow` (`0x80057F58`): `+0x1D4` −= 2 × D × f, D 200 /
  500 / 750; ATAT's (`0x800B8610`) has the same case.
  Its think spawns three bolts: `0x8008301C` kind 4 (in range) and `0x80083240` kind 2 (every frame), both speed 0.01
  (still: `+0x78` 0, drawn as a long flat streak along the tower's base heading; Skyhook's point at the hub, inside its
  arms), and `0x800831A0` kind 5, speed 5.0, the shot (by the timer `+0x184`). A node is drawn only with `+2`'s high byte 0xFF
  (`0x8001040C(node, 0, 0xFFFF)`; the tower's draw clears it once shot down).
- World matrices (2026-10-18, `local/work/mtx_slots.py`): a transform node's `+0x44` is its slot in the level's
  world-matrix buffers; the draw walk (`0x800BBAB0`; `0x800BBCDC`) takes `0x80017FB0(slot)` = `0x8013CE40 +
  (u8 *0x80144E11 << 16) + 64 * slot` (two buffers, by frame parity) and, while `+2 & 3` ("the rows changed", one bit
  per buffer; `0x8000FE48` and `0x8000FE1C` set both), rebuilds it from the node's rows (`0x800BA658`) and clears that
  buffer's bit (`0x800BBD04`–`0x800BBD2C`). Two nodes on one slot draw with whichever matrix was built last. Asteroid
  Field's battle uses slots 0..109; 110..160 stay 0 in both buffers. A mesh node's `+4` / `+8` are a display-list
  cache (`+4` = the frame stamp `*0x8018E9B0`: its list at `+8` is reused, `0x800BBAE4`–`0x800BBBA8`). Its target panel is HUD slot 38 (Skyhook: "SKYHOOK TURRET"; Asteroid Field: none).
- Bolt slots by kind (2026-10-18): `0x80031FE0(pos, dir, sector record, speed, …, flags, owner)` takes a Blst slot by
  kind = flags & 0xF from three s16 tables the level's load fills (`0x800183B0`), kinds 0..5: next `0x800DD570`, range
  start `0x800DD57C`, end `0x800DD588`; the next one wraps to the start on reaching the end exactly (`0x80032358`).
  Asteroid Field (40 Blsts): kind 0 (the player's) 0..20, kind 1 (TIEs) 20..40, the rest −1: a bolt of kind 2/4/5 (the
  tower's) was written before the pool and hung the game. Skyhook: 0 0..16, 1 16..26, 2 46..50, 4 42.., 5 26..
- Level-id checks in the Stft's methods (2026-10-15): each is `lui rX,0x8014; lh rX,
    -0x31F2(rX)` in method `+0x18` (`0x80097A40`, the per-frame level script; state `0x800DD2B0`: 0 start, 2
    playing) or `+0x24` (`0x8009C810`, messages). None is flight: the update `+0x1C` (`0x8009B0D0`) and its callees
    (steering `0x8009A30C`) never read the level id.
    | Load | When | id 6 |
    |---|---|---|
    | `0x80097D3C` | level start | s16 `0x8018DCA2` = 6: special asteroids (Chor releases one every 2–5 while fewer are out, `0x80059E54`) |
    | `0x80097EE4` | level start, `*0x800D2400` = 0 | float `0x800DEED4` = 30: missile lock-out (s); 5 missiles s16 `0x800E1B54`, 15 s when out |
    | `0x80097F28` | level start | float `0x800E1B28` = 20: seconds to the next TIE wave (spawner `0x80098858`; s16 counters `0x800E1B3C..48` all ≤ 0 (`0x800989A0`): `'prox'` to TieF, `'fini'` to the Stft, won) |
    | `0x8009806C` | playing, `*0x800D2400` = 0, Leebo state `0x800E1B10` = 1 | Leebo's "Sir, you'll have to fight off the TIEs…" (`0x800D18D0`) |
    | `0x8009D14C` | message `'htMe'` (a kill) | wave delay +0.2; fighters left `0x800E1B3C` (60) or `0x800E1B40` (20) −1 |
    (`0x80097F40` is only that check's compare constant.) The program's only id-30 compare is `0x80027820` (level change).
  - What `*0x800D2400 != 0` switches in the ship code: its own guns (`0x8009BF3C`: B fires `'blas'`, a Blst owned by
    the Stft through `0x800972E8` / `0x80031FE0`; Z, C-up/down `'misl'`; in Asteroid Field B's bolts are Chor's,
    `0x8005A59C` / `0x8005A5E8`), the collision trace (`0x8009B48C`, above), turn rate ×1.5 X-Wing, ×2 TIE
    (`0x8009A338`), the camera distance (`0x8009A0F0..0x8009A140`: every frame Trak 0 gets `'dist'` = 60 + 70 ·
    (speed − low) / (500 − low); in Asteroid Field the branch sets entry 5's offsets), the view keys (`0x80099AC8`).
  - Speed (`+0x9C`): low = 200 + 75 · (difficulty `0x8011282A` − 1); A aims for 500, R for low, no button their
    mean; each frame 0.2 of the way, at most +12 / −20 (`+0xA4` / `+0xA8`) (`0x8009B208..0x8009B3C8`; 200, 75 and
    500 are immediates in the code, not data). A or C-left turn stick x from yaw to
    roll. Measured (difficulty 2), the same in Skyhook and in Asteroid Field with the ship let go (`+0xAC` = 0):
    cruise 387.5, A 500, R 275 units/s; at full stick (±80) roll 2.01, yaw 1.34 (with ~0.4 roll), pitch 1.67 rad/s
    (stick up: nose down).
  - Skyhook's view: camera entry 6 (`*0x800D08A0 + 0x300`, type 1) with `+8` = Trak 0 + 0x20, offsets `+0x54..+0x68`
    all 0 (Asteroid Field's entry 6: source TieF 0 + 0x20, offsets 0/−100/20 and 0/−2/0). Trak 0: target `+0x8C` the
    Stft, `+0x60` distance (95 cruise, 130 A, 60 R: the `'dist'` message), `+0x64` its own speed, `+0x74..+0x7C`
    the target's place + (0, 0, 20), offset `+0x90..+0x98` (0, 0, 20), s16 `+0x9C` flags `0x0008`; messages
    (handler `0x800A21A4`): `'dist'`, `'offs'`, `'Lock'`, `'jXYZ'`, `'jHPR'`. Eye relative to the ship (behind /
    over): cruise 80.7 / 20, A 110.8 / 20, R 48.5 / 20. In Asteroid Field with entry 6 and Trak 0 set so and the
    distance written every frame: 86.9 / 19.4, 118 / 19.4, 64 / 19.4 (the rest of the gap not explained: the
    frame rate differs). D-pad up / down switch to entries 4 / 5.
  - Skyhook's view keys and guns (2026-10-16; `local/work/s7_ctl.py`, `s7_misl.py`):
    - View binding `+0x52` (preset 0: L or C-right) against `0x801130AC`, Skyhook's branch `0x80099C18`..join `0x80099FC4`: a press (once:
      s16 `0x800E1B04` = 2, counted down while up) from active index `0x800D08A8` 3, 5, 6 or 7 blends to entry 4 (`0x8000952C(4, 0.5)`:
      index −1 while blending, from/to at `0x80111764`/`66`), from 4 or 9 to entry 5. `*0x800D2400` is read once more as a value
      (`0x80099DBC`): nonzero and variant `0x800E1B20` 1 or 2 keeps the view; no record field is read. Then `+0x14`/`+0x16` →
      `0x80009648(9)`, `+0x10`/`+0x12` ∓ 100 · dt on float `0x800E1B80` (50..150) and entry 9. `sky.st`, three presses: 6 → 4 → 5 → 4;
      entry 4 (cockpit) `+8` Stft + 0x20, `+0x54..+0x68` 23.5, 6.0, 0, 0, 0, 0; entry 5 `+8` Trak 0 + 0x20, all 0 (as 6); `+4` 1.
      Without the record (Asteroid Field's path from `0x80099AD0`) the same binding toggles 5 / 4, the gun's views (`+8` the guns'
      matrix, 5's offsets 0 / −45 / …).
    - Guns `0x8009BF3C`..join `0x8009C024`: no record field; run only with Stft `+0x70` ≠ 0 (`0x8009BF34`). Binding `+0x54` (B)
      → `0x800972E8(stft, 'blas')` when the cool-down `+0x228` ≤ 0; `+0x56` (Z, C-up/down) → `'misl'` when `+0x22C` ≤ 0 and
      the lock-out float `0x800DEED4` ≤ 0, else sound `0x4E`. Missiles s16 `0x800E1B54` (5 at the Stft's init `0x80099708`, −1 a
      missile `0x800979B4`, then the 15 s lock-out). Each game frame the binding is held fires one (a 4-VI tap: two).
   - The gunner's view switch (2026-10-21): the update
     (`0x80099890`..`0x80099A78`) switches to the gunner's view once, on the first stick or button input while u32
     `0x8018E464` is nonzero (`0x8000952C(VIEW_MODE > 0 ? VIEW_MODE : 5, 0.5)`), then writes it 0 (`0x80099A74`); the
     pause menu's Resume A counts as that input.
- Camera entries, more: the gun's entry in Asteroid Field (5, after the first shot with Z in a gunner stage)
  takes its view from the guns' matrix (`+0x08`), 45 behind them; its offsets `+0x54..+0x5C` (0, -45, 20)
  and its written eye change nothing on screen. A view of our own goes through the Trak matrix and entry 3.
  Switching the view for good takes all three: each entry's active flag `+0`, the active pointer `0x800D08A4`
  and the index `0x800D08A8`. An entry not in use keeps stale rows: copy the current ones in as it comes on.
- Asteroid Field objects (2026-10-08..14, `local/states/ast.st`):
  - `Chor` (class `0x80112A78`) carries the player ship along the route: speed float `+0x60` (stock 0.3; 1.5 ≈
    300 world units a second), `+0x64` the 0..1 parameter on the spline segment, `+0x6C` u32 ×4 its node
    indices, `+0x158` its own drawn node, `+0x14C..+0x154` the gun sight's three ring nodes (shown again before
    every draw). The player's lasers (class `Blst`, owner Chor) leave Chor's guns along Chor's heading, and
    the game tests their hits only near Chor. A finished Asteroid Field goes on to sub-level 7 (Cut 03).
  - `Astr` (`0x801128C8`, asteroids): node at `+0x70`; the nodes hang in a plain group (kind 5) and each
    asteroid poses its node every frame. `AstF` (`0x801128F8`, debris round the ship): model list `+0x10`,
    8 pieces.
  - `Doly` (`0x80112EC8`) `+0x9C`: the asteroid belt backdrop's node. The game puts it at the camera every
    frame and turns its two children; the first child's rows are rewritten every other frame. The belt is two
    rings, radius 768 and ~540 at scale 1, 16 triangles, ±72 high. Copies of its children with node ids of
    their own drew dark wedges across the view.
  - `Trak` (`0x80112EF8`): matrix `+0x20` (rows right, forward, up, 4 floats each, then the eye), eye `+0x50`.
  - `TieF` (`0x80112D48`, 22): position `+0x50`, health float `+0x60` (<= 0: the game blows it up and the HUD's
    "TIE Fighters" count drops; one left at 0 drifts and is never sent again), flag word `+0x70`: low byte the
    type (`0x01` fighters, objects 0–9, health 10; `0x10` objects 10–13; `0x20` objects 14–21: the level's
    waves, TIE bombers among them), bit `0x8000` holds fire (the fire routine `0x8009F268` returns at once;
    nothing else reads the bit). Heading `+0x74` (unit, the drawn node's row 1), up `+0x80` (row 2), drawn node
    `+0x94` (kind D, rows at node `+0x14`): the update rebuilds the node from them every frame, so writes from
    a frame hook are undone before the draw (wrap the update, see *Known hook points*). A TIE laser takes 12
    off the player ship's health.
    Formation leader `+0xBC` (a TieF pointer, 0: none; 2026-10-22): the
    update of a wingman copies its leader's heading `+0x30` into `+0x74` and puts it at the leader's place + right ×
    `+0xC0` + heading × `+0xC4`, z + `+0xC8`. The game's relaunch of a downed flight (health −1, state `+0xA8` −1,
    then parked at (0, 0, −5000) with state −2; 9–24 s later all four in one VI: health 10, state 0) sets the links
    (1, 2 → 0; 3 → 1) and places the flight in formation ~700 ahead of the player, with no rock test.
    - Bombers and bombs (2026-10-16; `local/work/bomber_idx.py`, `bomber_pose.py`,
      `bomber_stock.py`, `bomber_phases.py`, `bomb_drop.py`, logs `local/run/s16/`). Models (node `+0x94`, list
      `+0x10`, count `+0x0C`) on `ast.st`: objects 0–9 two meshes each,
      the TIE fighter; 10–13 mesh `0x801A3A68`, the **TIE bomber** (`BOMBER_IDX` 10–13); 14–21 mesh `0x801A3AE0`,
      a green glow: **the level's bomb** (health 20 parked, 1 in flight).
    - Draw `0x800A13E4`: `+0xA8` (s16) = −2 hides the node (`0x8001040C(node, 0, 0, 0)`); else the node is rebuilt
      from the object's matrix `+0x20..+0x5C` (`0x8000FE48`) and shown (`0x8001040C(node, 0, 0xFFFF, 0)`). So a
      node hidden or moved by an update wrapper is drawn anyway: hide from a draw wrapper (as `battle_pose()` in
      `tie_draw()`).
    - Stock (`ast.st`, no input, 180 s): bombers 10–12 come in ~94 s on, ~1150 from the ship, then fly 110–190 off
      it. A bomb is the next type-`0x20` object (14, 15, … in order) coming into play at a bomber's place; its launch
      sets `BOMB_WARN` (`0x800E1B00`) to 2.2. It hits ~1118 frames (18.6 s) after its launch: health −120, the object
      parked again (z −5000, health −1). Launched by `0x8009E4A4` (below).
    - The launch (2026-10-16; `local/work/bomb_launch_stock.py`, `bomb_state.py`,
      `bomb_launch.py`, `bomb_hold.py`, logs `local/run/s16a/`): `0x8009E4A4(bomber)`, one argument. Chain: TieF update
      `0x800A11B8` (returns when `*0x800E1D20` ≠ 0, `+0xA8` = −2 or flag `0x80000`; `+0xAC` = 0: straight along `+0x74`;
      flag `0x10000`: the formation path `0x800A0D28`, then `0x800A0BBC` unless `+0xA8` = −1) → `0x800A0D28` → `jal` at
      `0x800A112C`. `+0xAC` is the target's matrix (Stft + 0x20 for bombers and bombs; Chor + 0xC8 for fighters); the slot
      is the target's place + `+0x10C` turned by its rows (bombers 10–13: 150 / 82.5 / 112.5 / 142.5 behind). A bomber
      launches when flag `0x20000` is clear, |dot(forward `+0x30`, slot − place)| < 10 (level with its slot) and its timer
      `+0xB0` (s, counted down only then) ≤ 0; `+0xB0` then = 7 − 2(d − 1) + rand · (5 − 1.5(d − 1)), d difficulty
      `0x8011282A`. The routine takes the first TieF with flag `0x20000` and `+0xA8` = −2 (pool `*0x80112D70`, = TieF
      `+0x10`; 14, 15, … in order: none, nothing happens), copies the bomber's `+0x08..+0x5F`, `+0xAC`, `+0xD8..+0x130`,
      sets `+0xA8` 0, health 1, `+0xB0` / `+0x158` = 20 − 5(d − 1) (15), and sends `TBmb` to class `Stft`
      (`0x800262FC(tag, msg)`: every object of the class, `'All!'` all) → `BOMB_WARN` = `*0x800ECA78` (2.2) (handler
      `0x8009D044`). The HUD (`0x8009598C`) counts the warning down and shows "Incoming Bomb!". The bomb flies the same
      path with its slot shrinking with `+0x158` (offset × `+0x158` / 15); at `+0x158` 1.5 (~18 s) it ends: the target
      −120 wherever it is, `+0xA8` −1, then −2 at (0, 0, −5000). Stock: bombs 14–19 launched 114–184 from the ship.
    - The bomb's place comes from the copied path state (`+0xD8…`, `0x8001B638` in `0x800A0D28`), not `+0x50`.
    - Flown by writes (2026-10-16, `local/work/s19_bomb.py`): a bomb object left at `+0xA8`
      −2 is never moved or fired by the game, so it can be posed and shown from a draw wrapper; `+0xA8` = −1 then gives
      the game's orange burst at its place (−2 the next frame) and takes no health. The game's laser hit test misses
      TIEs away from Chor (bombers too). When the player ship dies the game sets every bomber's health −1 on that frame
      (and 12, 13 `+0xA8` 0 → −2).
  - `Stft`: health int `+0x240` (495 full). At 0 the state `+0x230` goes 5 (the explosion), then 6, and the
    game respawns the ship at Chor's place with its health refilled and one life less. Engine glow node
    `+0xB8`: the game shrinks it to nothing when it thinks the ship stands still. Its width: the ship update
    (`0x8009BD9C`) writes s16 `+0xC8` = 1000 · (clamp(1.4 · 0.8 · speed / 250, 1, 2) + random · 0.15); the draw
    (`0x8009C4F4`) scales the node's x and z by `+0xC8` / 1000 times a dot² (×0.01 when it is under 0.6: the
    "stands still" case), y 1.05. So 275 → 1.23, 387.5 → 1.74, 500 → 2.0: hardly seen. The bomb warning float
    `0x800E1B00` (seconds of "Incoming Bomb!") is set by the ship's `TBmb` message, sent by the bombers'
    launch `0x8009E4A4` (TieF → Bombers and bombs; 120 a hit, an orange flash).
    A free ship (`+0xAC` 0) does not come back at Chor's place (2026-10-16, `local/work/sd_crash.py`, head-on into the
    Star Destroyer's hull): Skyhook (`sky.st`, stock) puts it at ≈ (−876, 7060, −737), flying −y. The view, VIs
    (60/s) after the hit: Skyhook state 0 → 6 at 2, camera entry 3 from 26 with its eye kept 129 off the wreck, the
    respawn at 158 and the eye on the ship (129 behind) the same frame. Asteroid Field: 2 → 5 at 1, 6 at 221, entry
    3 (Trak 1, the route's) from 31, its eye ~110 off Chor (4762 from the wreck); the respawn at 453 leaves it there,
    entry 5 (the gun's, eye also by Chor) from 473; 3 s later the eye is still 14000 off the ship. Trak 0's eye
    jumps onto the ship at the respawn (~110 off) in both levels: it is not the view in Asteroid Field.
    The death's timers (2026-10-22; `0x8009863C` decompiled, `0x80096E14` the
    state set): `+0x234` the seconds in the state (+= the frame time, double
    `0x8018E998`); state 5 lasts `+0x238` = 3 s (int, set at its entry) unless `*0x800D2400` (Skyhook's sector record)
    is set, which goes to 6 at once; state 6 lasts 3.3 s (double `0x800EC8F0`) when `+0x70` != 0, each frame
    `CAM_BLEND(3, 0.5)` and the screen fade `0x800D0804` (r, g, b, a) = (0, 0, 0, t / 3 × 255); the respawn (state 0)
    puts a free ship at (−880, 7074, −737), health 500, `RESPAWN_T` (`0x800E1B6C`) 1.5 and the fade's alpha 255, then
    while `RESPAWN_T` > −0.5 the alpha is `RESPAWN_T` × 255 (`0x800EC898`, clamped; the fade-in `0x80098D34`). Measured:
    Asteroid Field's way 401–434 VIs from the hit to the respawn, Skyhook's (no state 5) 182 / 196. In state 5 the game
    moves the copy `+0x08` on (the ship's own way) while `+0x50` stays at the hit; the bursts (class `Expl`) are born on
    `+0x08` and state 6 puts the ship there (390–1090 off the hit).
    The ship's touch of an object (the update, `0x8009B9B0`): `0x80026A94` (cylinders: each
    object's `+0x60` radius, its axis `+0x68` .. `+0x6C` over `+0x50`; a tower's 50 and the ship's give 65) finds the
    object and an impact f; the health `+0x240` −= a cost by the object's class (`0x8009BA38..0x8009BB88`: f × ATAT 300, EShd
    300, ATST 150, Astr 100, Stft 20, TieF 5, Misl none; **PRBT a flat 50000**, the float `0x800EC9F8`, not scaled by f; its only
    reader in the main program, `0x8009BB38`), skipped under Invincibility `0x800E1B2C`; two sounds, a burst at `+0x08`,
    state 5 below 0, then `plow` {`plow`, `Stft`, the ship, f} to the object (`0x80026284`). In state 5 a touch ends
    the state (`+0x234` = `+0x238` + 1).
  - Leebo's opening lines: state `0x800E1B10` (1, 2 while he speaks, 0 done). HUD sprite slot 30 is Leebo's
    portrait.

## Where addresses came from

- Earlier public reverse engineering of the game (see the thanks in `sote-patch/README.md`).
- PC version `SDATA/SHADOWS.EXE` (same engine) strings for names of camera/targeting modes.
- RAM probing in the harness: snapshot object memory at three moments (idle, idle, moving) and
  keep fields that change only when expected; set a field and watch the game react.
- `harness/disasm.py` over `local/work/main.bin`; `harness/decomp.py` (Ghidra) for the same code as pseudo-C.

## Saves

Code injected this way doesn't touch save code; in-game EEPROM saves carry over between
original and patched ROMs. Emulator savestates don't (different code in RAM). M64Plus FZ keys
EEPROM files as `<header or good name>-<first 8 hex digits of MD5>.eep` (seen in the harness), so
a patch should keep those digits stable: reserve a nonce at the end of the ROM and brute-force it
(32 bits, `sote-patch/tools/md5prefix.c`, seconds to minutes with a precomputed midstate). Keep
everything in the first 1 MB fixed too (e.g. a constant DMA size) so the header CRC doesn't move.
