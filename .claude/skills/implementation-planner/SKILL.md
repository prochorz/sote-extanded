---
name: implementation-planner
description: Write a decision-complete implementation plan before touching the code of the SotE patch, the harness or the Gall Run mission, or audit an existing plans/ plan. Use when the user asks to plan ("plan this", "сплануй", "зроби план", "implementation plan", "audit this plan"), or before any change that touches more than one module, adds a hook, a feature, a test or an asset. Skip one-file, single-concern, obvious edits (a constant, a typo, a doc line).
argument-hint: "[feature/task description | path to an existing plans/ plan]"
model: opus
effort: high
---

Produce (or audit) a plan that leaves no decision to be made silently while coding. Terse prose; the plan doc in English (every `.md` in this repo is), the conversation with the user in Ukrainian.

## Hard rules

- **Decision-complete, not code-complete.** Finalize every choice the executor would otherwise make on the fly: file, name, address, hook form, state, test, numbers. No full code bodies; a snippet only where the decision *is* the code (a hook trampoline, a constant table).
- **No silent decision.** A blocking ambiguity → ask (Phase B). A decision that needs a source you could not inspect (an address not in the docs, a game function not disassembled yet) → `(assumption)` D-entry + a verification step on the harness, and the plan is `Draft` until verified.
- **No `TBD` / `as appropriate` / `decide later`** in Steps, Validate, Tests.
- **Cite the owning doc, never restate its rules** (restated rules drift). The owning docs are listed in Phase A.
- **The approval gate** is the `ExitPlanMode` call (in plan mode) or an explicit confirmation request (otherwise). It carries the Phase E gap list in the same turn. No code, no persisted doc, no new savestate before approval.
- **Approving a plan does not approve running it.** Research and execution steps start only on the user's explicit go, and the request names the step(s) and an estimated token cost (see *Cheap runs* for the measured costs; 2026-10-16: three such steps after one "так" to a plan ≈ 715k unasked). One go covers the named steps only.
- **Cheap first.** Settle an assumption statically in the main session (disassembly of `local/work/main.bin` or its pseudo-C from `harness/decomp.py`, one-state RAM reads, existing logs and docs) before proposing an emulator run or a subagent; a run checks what the static read predicts.
- **Cheap runs (the user, 2026-10-20: "щоб ти сам робив ці кроки оптимізації будь де").** Every plan, any feature:
  - *Start near the moment.* A check step names the state it starts from, the closest one to what it checks (a state per
    moment of the build, like `harness/gallrun/c05_check.py`'s per-frame states), never a replay from a level's start
    when a later state can exist. None yet: the plan's first run makes them (an existing tool, or a knob added to it).
  - *A check that repeats becomes a tool.* A check two plans need (or one plan runs more than twice) goes into a tool
    that prints a short per-item summary with the numbers the Validate lines need (pattern: `c05_check.py`). Existing
    tools are listed in the step; a new knob goes into the existing tool, not a new copy (`local/work/` one-off
    probes are folded into the tool once reused).
  - *Numbers before pictures.* Validate lines read RAM numbers; shots only where a number cannot tell (look, a place on
    screen). Contact sheets are for the user, made when asked, not read back shot by shot.
  - *Estimates from the spend measured* (2026-10-20): a subagent's research step 150–250k, an implement + check round
    100–160k, a main-session tooling change 20–60k. Each report back gives the spend against the estimate.
- Project rules that bind every plan: tests only for the touched feature (skill `sote-test`), each plan decides whether its feature ships in releases (every `FEATURES` entry is in the default build, so in the release ROM; the Gall Run too since 2026-10-24), the payload is 64 KB, `M64CPU=0` when injecting, no videos unless asked, no names from other games in docs or code.

**Mode:** an existing `plans/*.md` path → **audit**; a task description → **new plan**; unclear → ask.
Audit is read-only: an impact-ordered gap list against Phase C + [decision-taxonomy.md](decision-taxonomy.md) + the Phase E checklist, each gap tagged with what it violates, ending with the proposed Status. Never fill a gap in an audit; each fill is a new D-entry the user confirms.

**Plan mode:** every turn ends in `AskUserQuestion` (Phase B) or `ExitPlanMode` (Phase F). Phases A–E run before `ExitPlanMode`; G runs after approval.

## Output

One doc per [plan-template.md](plan-template.md), drafted in the plan-mode file (or the scratchpad outside plan mode). Persisted in Phase G.

## Phase A — Gather context

Consult the owning doc of each area the plan touches. A convention written nowhere is a gap to flag, not to invent.

**Always:** `CLAUDE.md` (modules, build, rules), `sote-patch/README.md` → *How it works* (module and hook list) and *New feature: checklist*.

| Plan touches… | Consult |
|---|---|
| a game address, field, structure, class (`Humn`/`HumT`/`Stft`/…) | `docs/reverse-engineering.md` (memory layout, *Known hook points*, *Player classes*, *Other game structures*, *Where addresses came from*), `sote-patch/src/game.h` |
| a new or changed hook | *Known hook points* (`j` vs `jal`, what the overwritten instruction is and where to continue), `hooks.S` `hook_table` + trampolines, `harness/inject.py` `all_hooks()` |
| shared declarations, stubs for `--without`, the `KINDS` table | `sote-patch/src/common.h`, `core.c` (`KINDS`) |
| `core.c` / `lock.c` / `train.c` | the module's header comment and its constants block; `README.md` *What changes* |
| `hang.c` | `sote-patch/docs/ledge-falls.md` (design, tuning, tests, open ideas) |
| `cheats.c` (a Cheats row, a toggle) | the `cheats.c` header (`OURS`, drawing, input), `README.md` *Cheats in the pause menu* |
| `gallrun.c`, `gall_*.c` / `falcon.c` / assets / level blob | `local/docs/gall-run.md` (findings, dead ends, next steps), `local/docs/gallrun-tools.md` (local only, git-ignored) |
| `build.py`, payload size, a section outside the payload | `build.py` (`FEATURES`, `SIZE_OPT`, `PAYLOAD_SPACE`), `link.ld` |
| tests, savestates, bots, screenshots | `docs/harness.md` (*Files*, *Typical loop*, *Savestates*, *Gotchas*), `harness/testlib.py`, `harness/run_all.py` `SUITE`, skill `sote-test` (module → tests table), skill `sote-bot` (getting Dash somewhere, debug menu, making states) |
| a video or a take | skill `sote-video` (only when the user asked for one) |
| the PC version as a reference | `CLAUDE.md` → *PC ISO* |

Then: inventory existing code to reuse (`grep` the function or mechanism before assuming it is new: `ov_color`/`fill_tri`/`project` for drawing, `find_player`, `set_anim` hooks, fake targets in `testlib.py`). Feeds *Current state & reuse*.

**Reference sweep** for every shared identifier the plan adds, changes or removes — grep the literal across `sote-patch/`, `harness/`, `docs/`, `.claude/`:
- a game address (`0x80......`): other hooks at or near it, tests that read it, doc rows that describe it;
- a payload symbol tests read through `syms()` (`g_*`), a `FEATURE_<NAME>` flag, a Cheats row (and `OURS`), a HUD element slot;
- a savestate name (`local/states/*.st`) and the tests on it;
- a test name (`SUITE`, the `sote-test` table, `README.md` *Verified*, `docs/harness.md` *Files*).
Each consumer found is registered as a decision or scoped out; nothing leaks in unremarked. A removed symbol is swept too: skills and docs prescribe mechanisms by name.

**Source precedence** (on conflict surface it, ask, or mark `Draft`; never pick silently): user's words > `CLAUDE.md` + memory rules > the owning doc above > the current code (what the game *does*, read in RAM or disassembly, beats what a doc says it does) > a neighbouring module's pattern.

## Lessons (Gall Run playtest 2, 2026-10-16: ~4 M tokens, ~30 extra D-entries)

What made that plan expensive, and the rule each one gives:
- 10 of 16 assumptions were refuted in RAM, one agent round each. → Check each game mechanism statically in Phase A (disassembly, one-state RAM read, the existing logs) before writing a fix on it; an `(assumption)` is for what truly cannot be read without a run.
- The user chose between options that rested on unread mechanisms (the bombers: three research agents, ~0.7 M, each choice impossible). → Phase B options rest on checked facts (see Phase B).
- Validate lines built on a misread number (the steering corridor taken for the drawn walls), a guessed threshold (a frame-diff bound below run-to-run variance), a value from memory (a laser's damage). → Take every Validate number from a measured baseline: run-to-run variance, the stock value, the current build's reading.
- A size budget written from memory (`.gall` "room ~15 KB", really 3.3 KB) blocked two steps late. → Read the budget from the last build's output in Phase A.
- Behaviour assumed from code that was commented out (the slit pull's yaw line sat inside a comment). → Read the cited lines as compiled: check comments that swallow code.
- 22 playtest items in one plan: every refutation rippled through shared code and steps. → Split a long playtest list into plans of ≤ 6 items, smallest risk first.
- A cosmetic item polished without a check-in (a portrait, ~0.3 M). → Show the first result to the user and ask whether it is enough.
- Resumed agents carry their whole context (one reached ~0.3 M). → After a BLOCKED round, a fresh agent with the plan's new D-entries is usually cheaper than resuming one past ~150 k.

Playtest 3 (2026-10-17: ~240 k, ~55 k of it waste):
- An assumption the docs already refuted (START over a held line: `reverse-engineering.md` said the game skips its START path) cost three build-and-probe rounds. → Before writing an `(assumption)`, grep `docs/reverse-engineering.md` for its addresses and words.
- A guard in the code the plan touched (`LINE_HOLD_MIN_F`) was missed in its Validate and cost a round. → List every guard on the touched path (precedent parity applies to own code too).
- The HUD panel was hunted by guesses (flags, a timer, a stack pointer, RAM code scans) while the documented HUD element table found it in one read. → Start a "what draws X" search from the documented tables (HUD elements, sprites, class records), not from guesses.
- Five probe runs hung on the stock ROM: Gall Run probes need the built ROM (`<dir>/sote-patch.z64`). → A hang on the first run: check the run's inputs before re-running.

## Phase B — Clarify

Collect ALL blocking ambiguities; ask with `AskUserQuestion` (max 4 per call; more → the 4 highest-impact first, then re-enter), then STOP. Blocking = two reasonable implementations diverge on naming, file, hook point, which player classes / levels it covers, how it interacts with an existing feature, or whether it ships in releases. Never ask what Phase A or the code answers.

Options offered rest on checked mechanisms. An option that depends on an unverified game behaviour ("the game's own bomb", "the game's AI flies them") says so in its description, with what checking it costs; check it cheaply first where you can. (2026-10-16: two options chosen on unverified behaviour were refuted in turn, one research agent each.)

## Phase C — Decision Register

Numbered `D1, D2, …`: decision, chosen option, one-line rationale. Later sections reference the ID, never restate.

Must resolve:
- exact file paths + action (CREATE | MODIFY | DELETE);
- exact names: module, feature flag, functions, globals (`g_*`), constants, Cheats row text, test file and `SUITE` name, savestate name;
- every hook: address, in which game function, `j` or `jal`, the instruction overwritten and re-executed, the continue address, under which `#if FEATURE_*`;
- reuse-vs-create and generalize-vs-split calls;
- **precedent parity**: a decision that uses an existing mechanism as a *behavioural* template ("like the hang does", "same as the train camera") carries this block:
  ```
  Precedent: {path}:{start}-{end}
    {the lines evidencing each Carries / Diverges entry}
  Carries: {guards / early returns / resets reproduced}
  Diverges: {one D-id per divergence} | none
  ```
  Every guard and early return in the cited range is either Carried or under a Diverges D-entry; one in neither is a silent drop.
- every applicable class of [decision-taxonomy.md](decision-taxonomy.md); name the non-applicable ones in one line.

A decision that changes **existing** behaviour or a shared declaration (a hook already in use, a `common.h` prototype, a constant another module reads, a test's check) carries its current → proposed diff inline under the D-entry, one source line per diff line, no `…`:

````
- D2 — {decision}: {chosen option}. {rationale}
  ```diff
  - {current line}   // path:line
  + {proposed line}
  ```
````

New files and symbols are named by contract, never pasted as `+`-only code. The fence is plan-time only: Phase G omits it (git is the durable diff).

## Phase D — Author

Fill [plan-template.md](plan-template.md): fully specified steps referencing D-IDs; Validate lines are observable criteria the harness can read (a field value with a margin, a screenshot showing X, a frame count), not commands.

## Phase E — Self-check (gate)

Run the list, don't tick it mentally. Emit three lines in the conversation (not in the doc):
- `Blocking gaps:` none | {checklist items that fail}
- `Behaviour-changing decisions (each with an inline diff):` none | {D-IDs}
- `Assumptions to verify on the harness:` none | {D-IDs → step N}

Any blocking gap → the plan is `Draft` and the gaps go back to Phase B.

- [ ] No alternatives or deferred decisions anywhere
- [ ] Every file has an action and an owning step
- [ ] Every hook: address, form (`j`/`jal`), overwritten instruction, continue address, `hook_table` entry, `#if` guard
- [ ] Payload budget stated: the module's `-O` level, expected size, or its own section; no `-Os`/`-Oz` on per-frame code without saying why
- [ ] `--without <feature>` build still compiles: stubs in `common.h` listed
- [ ] Player classes and levels covered stated (`Humn`, `HumT`, ships); what happens on the others
- [ ] State reset decided: on level change, teleport, Cheats toggle off, death, mid-feature switch-off
- [ ] Interaction with lock, hang, train, cheats, gallrun decided where they touch the same frame or field
- [ ] Every address and field either cited from `docs/reverse-engineering.md` / `game.h` or an `(assumption)` D-entry with a verify step
- [ ] Tests: the savestate exists (or a step makes it, with the `sote-bot` way), the checks are observable with margins, the `SUITE` line and the `sote-test` table row are steps; only the touched feature's tests are listed to run
- [ ] Docs steps: `README.md` *How it works* (+ *Verified* once the tests pass), `CLAUDE.md` module line, `docs/reverse-engineering.md` for every new address or structure, the feature doc if there is one
- [ ] Release impact decided: in the default build, or kept out of releases (`build.py` has no switch for that since 2026-10-24: a plan that keeps a feature out names how), or not shipped; `tools/release.sh` untouched unless the plan says so
- [ ] Every applicable taxonomy class resolved; non-applicable named
- [ ] Precedent-parity blocks complete (cited lines read this session)
- [ ] Reference sweep done for every added / changed / removed shared identifier
- [ ] No executor-facing section still instructs a superseded decision
- [ ] Conventions cited, not restated
- [ ] Cheap runs: each check step names its start state (the closest to the moment) and the tool it runs; repeated checks are a tool
- [ ] No names from other games anywhere

## Phase F — Present for approval

In plan mode this phase IS the `ExitPlanMode` call; outside, an explicit confirmation request (in Ukrainian, short). The turn carries the Phase E three lines and every behaviour-changing D-entry's inline diff. Not before the gate passes. The request asks about the plan only; running its steps is a separate ask (Hard rules).

## Phase G — Persist

On approval write the doc to `plans/<name>.md` (git-ignored: a plan is a working file, never committed, never in
`CLAUDE.md`), diff fences omitted, each Register entry as decision text + `file:line` pointers. It opens with
`**Status:** Planned` (or `Draft` with unresolved gaps), every discrete task is a `- [ ]` checkbox. The playtest intake
list lives there too (`plans/intake.md`): only the items no plan has taken yet; an item leaves it when a plan takes it
(the plan carries its words), so no solved or planned item stays there. Item ids (`P<n>`) are never reused: open
plans, tools and `local/docs/decisions.md` name them. Code, docs and tools never point at a plan (it will be gone): they carry
what the plan decided themselves.

**Closing a plan (the user, 2026-10-24: the plan is temporary, its decisions are baked into the harness).** Before a
plan is `Done`, its last step folds it, each item checked against the current code:
- every Validate line that guards behaviour becomes a check in the owning tool (a `--check` knob of the existing
  `harness/gallrun/` tool, or a `harness/tests/` test): the measured threshold (with margin over run-to-run spread),
  PASS / FAIL output, its start state; listed in the `sote-test` table for the module;
- the reason of each decision goes into a comment at the constant or code it shaped (one line: why, the number that
  failed before);
- refuted assumptions and dropped approaches: one line each in the feature doc's *design history and dead ends*
  (`local/docs/gall-run.md` section 5);
- game facts into `docs/reverse-engineering.md` (a Gall Run fact that names a level it is built from:
  `local/docs/gall-facts.md`), tool knobs into the tools' docs;
- the living feature doc describes what the code does now and names constants without restating their values.
Then the plan file is deleted. `local/docs/decisions.md` is the frozen archive of the plans closed before
2026-10-24: read it, add nothing.

`Planned` → `In progress` when work starts → `Done` when the tests pass and the docs steps are ticked. Tick checkboxes as the work lands. The Register is append-only: a change of mind is a new D-entry; the old one gets `— superseded by Dn`, and every Step / Validate / Test line that referenced it is updated in the same edit.

## Execution and BLOCKED

Before each run (a subagent, a harness research step, a build-and-test cycle): ask with the step numbers and the estimated token cost; wait for the go. Prefer doing a small step in the main session over a subagent.

The plan is executed in this session or handed to a subagent with: the plan's path in `plans/`, the step numbers, the relevant D-IDs. The hand-off never restates conventions and never prescribes test commands beyond the `sote-test` skill.

Every hand-off ends, verbatim:

> If a detail you need is not in the plan or the Decision Register, or the plan contradicts the current code or what the game does in RAM, STOP and report `BLOCKED: [Step N] — <what's missing>`. Do not invent names, addresses, hook points or design decisions.

On a BLOCKED report: re-enter Phase B, append a new D-entry (persisted form, no diff fence), mark the superseded entries, cascade into every section that referenced them. Then report the spend so far and ask before the next run: never resume a run on your own after a BLOCKED.
