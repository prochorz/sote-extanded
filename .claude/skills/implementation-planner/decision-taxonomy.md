# Decision Taxonomy

Decision classes an executor invents silently when they are not written down, beyond the
structural ones (paths, names, reuse, contracts) in SKILL.md Phase C. Resolve each applicable
class as a numbered D-entry; name the non-applicable ones in one line
(`Considered, not applicable: {class} — {why}`). An unresolved applicable class → `Draft`.

## Classes

- **Hook point** — which game function and address; `j` (function entry) vs `jal`
  (mid-function); the instruction the hook overwrites, where it is re-executed and where
  control continues; whether another hook already sits at or next to it (`hooks.S`
  `hook_table`); the `#if FEATURE_*` guard. Source: `docs/reverse-engineering.md` → *Known
  hook points*, *Running custom code in the game*. A new address needs the *Where addresses
  came from* story (RAM probing, disassembly of `local/work/main.bin`) and a doc row.
- **Game truth** — every field offset, flag bit, function argument and structure the plan
  relies on: cited from `docs/reverse-engineering.md` / `game.h`, or verified this session
  (RAM read on a named state, `disasm.py`), or an `(assumption)` D-entry with a harness
  verification step. A PC-version string or routine is a lead, never a proof.
- **Player class and level coverage** — `Humn` (on foot), `HumT` (train), ships (`Stft`),
  the `KINDS` table; which levels the feature is for and what it does on the rest (inert,
  guarded by `K`, by level id, by class name). The default is "off everywhere it was not
  designed for".
- **State and reset** — which globals (`.bss`, zeroed by `_start` and `inject()`), who
  resets them on level change, teleport / This Level, death, pause, the Cheats toggle going
  off mid-feature (`t_off.py mid` is the precedent), and loading an old savestate.
- **Feature interaction** — where the new code touches a frame, field or camera another
  module already drives (`core.c` movement and lazy camera, `lock.c` steering and overlay,
  `hang.c` pose and position, `train.c` input gating, `gallrun.c` route, `gall_cam.c` camera): the
  priority, and who yields. The drawing budget of the overlay hook (`0x800BB864`).
- **Payload and performance** — expected code size against `PAYLOAD_SPACE` (64 KB, ~55 KB
  used); `SIZE_OPT` level or an own section like `.gall`; per-frame cost (no `-Os`/`-Oz` on
  per-frame paths without a reason; `t_off.py base` measures frame dt); the dynarec on the
  user's phone (M64Plus FZ): no self-modifying code after `_start`'s cache flush.
- **Build and release** — `FEATURES` line, `--without` stubs in `common.h`; if not for releases,
  how it is kept out (`build.py` has no switch for that since 2026-10-24); whether `tools/release.sh` and the `[SotE Extended]` ROM
  change at all; the MD5 prefix rule for the user's save.
- **Cheats row** — text, default on/off, position and `OURS`, whether it is a feature toggle
  (`g_off` bit, ends the feature mid-way) or a setting; what `t_cheats.py` navigation
  checks need to keep passing.
- **Assets and data** — a new binary: generator script in `harness/`, file in
  `local/game/`, ROM offset in `build.py`, RAM address and who DMA-copies it
  (`_start` in `hooks.S` and `inject()` in `harness/inject.py`), its size on the Expansion
  Pak, and whether it is committed.
- **Savestate** — an existing `local/states/*.st` the test can use, or a new one: how it
  is made (`sote-bot`: `tpstate.py`, `mkstate.py`, debug-menu teleport, a scripted walk),
  with which build, its name, and that it is committed with the feature.
- **Test observability** — what the test reads (`g_*` via `syms()`, game fields, screenshot)
  and the margins (runs are not bit-exact); a `g_test_*` field added for the test if numbers
  alone cannot show it; which existing tests the change may move and how their checks are
  updated with the docstring.
- **Tuning constants** — name, unit, initial value, where they sit (top of the module), and
  what the user tunes by feel on the phone versus what the harness fixes.
- **Docs** — `README.md` *How it works* hook/module lines and *Verified*; `CLAUDE.md`
  module line; `docs/reverse-engineering.md` rows for new addresses, fields, hook points;
  the feature doc (`sote-patch/docs/…` or `local/docs/…`, the Gall Run's: local only; plans themselves live in `plans/`) when the design has
  findings worth keeping; `docs/harness.md` *Files* for a new test or tool.
