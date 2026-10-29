# Implementation Plan Template

The output doc shape (skeleton below). Paths repo-relative. English.

## Calibration example (frozen; illustrative, not a live plan)

Decision-complete means each task carries its decisions inline:

- [ ] `src/cheats.c` (MODIFY): `g_fuel_on` (`.bss`, default 0, the row is off on every
      boot); `cheats_frame()` (called once per frame from the overlay hook, stub in
      `common.h` without `cheats`) writes `Humn +0xBC` = `FUEL_MAX` (99.0f) only when
      `K == &KINDS[0]` (on foot; HumT has no tank)
- [ ] hook `0x80009138` (`j`, HUD colour setter, re-execute `sll t6, a0, 0x10`, continue
      `0x8000913C`): when `a0 == 23` and `g_fuel_on`, colour = `0x8080FF80` (the blue
      Invincibility gives the health); `hook_table` entry under `#if FEATURE_FUEL`
- [ ] `harness/tests/t_fuel.py` on `local/states/gall_tp5.st`: off → tank ≤ 40 after a 4 s flight;
      on → tank ≥ 95 after 15 s and the jetpack flag still set; `SUITE` line `fuel`;
      `sote-test` table row for `cheats.c`

NOT decision-complete: "add a fuel cheat with the right hook and a test" / "reset the state
where needed".

A precedent-parity decision and a gated step look like this:

```
D4 — reuse the hang's exit path (`hang_end(obj, let_go)`) for the new drop.
  Precedent: sote-patch/src/hang.c:{start}-{end}   (line numbers read this session)
    if (!g_hang_state) return;                        // not hanging — Carried
    if (health <= 0) { hang_end(obj, 1); return; }    // shot down — Carried
    if (g_off & OFF_HANG) { hang_end(obj, 1); return; } // Cheats toggle off → D5
    if (level changed) { hang_end(obj, 1); return; }  // teleport / This Level — Carried
  Carries: not-hanging guard, shot-down, level change
  Diverges: D5 — the Cheats toggle does not end the new drop (it is not a feature toggle)

[3] Validate:
  - catch: walk off the crevasse at 80,0 → `g_hang_state` = 1 within 20 frames, hang point within 1.0 of the rim
  - no catch: same at 57,-57 → `g_hang_state` stays 0, he lands on the lower floor
  - toggle off: Cheats → Ledge Hang off while hanging → `g_hang_state` = 0 next frame, he falls
```

## Skeleton

````markdown
# {Title}

**Status:** Planned
**Feature / module:** {feature flag, files}
**Ships in releases:** yes | kept out of releases (how) | no
**Depends on:** {plan links, if any}
**References:** docs and skills consulted (by name); the user's videos / messages if any

## Objective
1–2 sentences: what the player gets, on which levels / classes.

## Current state & reuse
- Reused / extended code (path + one line each). Every claim cites a file read this
  session, no from-memory claims. Reuse-vs-create calls go in the Register.
- What the game does now at the touched point (field values, animation, camera), from RAM or
  disassembly, with the state it was read on.

## Decisions (Register)
- D1 — {decision}: {chosen option}. {one-line rationale}
  ```diff
  - {current}   // path:line
  + {proposed}
  ```
  (behaviour-changing / shared-declaration decisions only; per SKILL.md Phase C)
- D2 (assumption) — {assumed fact about the game}; verify in step [N] on {state}
- Considered, not applicable: {taxonomy classes} — {why}

## Contracts (define once, reference by name)
- Hooks: address, game function, form (`j`/`jal`), overwritten instruction, continue address
- Globals (`g_*`) and their reset points; constants (name, initial value, unit)
- `common.h` declarations and their `--without` stubs
- Game fields read / written (`class +0xNN`, meaning, where documented)
- Cheats row (text, default, `OURS`), HUD slots, assets (file, RAM address, who copies it)
- Payload: expected size, `SIZE_OPT` entry or own section

## Files
| Path | Action (CREATE\|MODIFY\|DELETE) | Owning step | Purpose | Decisions |
|------|--------------------------------|-------------|---------|-----------|

## Steps
Steps ARE the task checkboxes (SKILL.md Phase G).

- [ ] **[N] {Title}**
  - Files: {path(s)} — {action}
  - Do: fully specified logic referencing contracts + D-IDs
  - Depends on: {step N | none}
  - Validate: observable criteria the harness can read (a field with a margin, a screenshot,
    a frame count), NOT commands. A gated / branching step → one line per partition
    (`on:` / `off:` / `other class:` / `mid-feature:`); a plain step → one line. Every
    partition named here appears under Tests.

Typical order: `common.h` declarations + stubs → the module → `hooks.S` + `build.py` →
Cheats row → savestate → test + `SUITE` + `sote-test` table → build with and `--without` →
run the feature's tests → docs (`README.md` *How it works* / *Verified*, `CLAUDE.md`,
`docs/reverse-engineering.md`).

## Edge cases
Only the ones this task has, each with the decided behaviour: level change, teleport,
Cheats toggle off mid-feature, death, pause, the other player class, a ship level, an old
savestate.

## Tests
- Test file, `SUITE` name, savestate (existing, or the step that makes it and how).
- Each behaviour: inputs → expected outcome with a margin (runs are not bit-exact), what is
  read (`g_*` through `syms()`, game fields) and what a screenshot must show.
- Which existing tests run after the change (the `sote-test` table for the touched modules),
  nothing more.

## Out of scope / follow-ups

## Execution notes
Only when part of the work is handed to a subagent: step numbers, D-IDs, the persisted doc
path, and the BLOCKED line from SKILL.md.
````

## Lifecycle rules

- Persisted doc = canonical; plan-mode file = working draft.
- The draft carries inline ` ```diff ` fences under D-entries; Phase G omits them on persist.
- Living status = `**Status:**` field + Step checkboxes, kept by the session that does the work.
- The Register is append-only: BLOCKED resolutions and mid-flight changes are NEW D-entries;
  the old one gets `— superseded by Dn`, never rewritten; cascade in the same edit.
- After `Done` the doc is a decision record: no maintenance beyond status; its lasting
  findings move to the feature doc or `docs/reverse-engineering.md`, and a one-off plan is
  deleted.
