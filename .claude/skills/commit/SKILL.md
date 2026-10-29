---
name: commit
description: Look at the uncommitted changes in the n64 repo, split them into logical commits (one feature or topic each) and commit them. Use when the user asks to commit ("commit", "make commits", "split into commits").
allowed-tools: Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git show*), Bash(git add*), Bash(git apply --cached*), Bash(git restore --staged*), Bash(git reset -q*), Bash(git commit*), Bash(git ls-files*), Bash(git check-ignore*), Read
---

Args (optional): paths or a topic to limit the commit to ("only hang"), or `plan` to show the split without committing.

## 1. Read the changes

```bash
git status --short
git diff --stat
git diff            # per file when it is long: git diff -- <path>
git log --oneline -10   # message style
```
Read every changed and untracked file's diff before grouping. Never commit something you have not looked at.

## 2. Group them

One commit = one reason to change. Group by feature, not by file type: a feature's source, its tests, its docs and its assets go together.

Project map (what usually belongs together):

| Topic | Paths |
|---|---|
| a patch feature (`hang`, `lock`, `train`, `cheats`, `gallrun`, core) | `sote-patch/src/<module>.c`, its lines in `common.h` / `hooks.S` / `build.py`, `local/game/`, its tests `harness/tests/t_<...>.py` + `run_all.py` SUITE lines, its docs (`sote-patch/docs/ledge-falls.md` for hang, `local/docs/gall-run.md` for gallrun: local only, never committed; README sections), its asset tools (`harness/gallrun/`, `harness/pose/`, `harness/falcon_asset.py`) |
| harness | `harness/m64.py`, `inject.py`, `testlib.py`, `run_all.py`, `game.py`, `debugmenu.py`, plugins, `docs/harness.md` |
| video tools | `tools/video/`, `.claude/skills/sote-video/` |
| release | `tools/release.sh`, `.claude/skills/sote-release/` |
| game knowledge | `docs/reverse-engineering.md` (when not tied to one feature's change) |
| retiring something | the deletion goes with the change that retired it |
| project rules | `CLAUDE.md`, `.claude/skills/`: with the change they describe, else their own commit |

- A file holding two topics (common: `CLAUDE.md`, `common.h`, `hooks.S`, `run_all.py`, `README.md`, `reverse-engineering.md`) is split by hunks: `git diff -- <file> > "$TMPDIR/<topic>.patch"`, keep the hunks of one topic (fix the `@@` line counts), `git apply --cached <patch>`. Check with `git diff --cached -- <file>`.
- Renames: stage the deletion and the addition together (`git add -A -- <old> <new>`), so git sees a move.
- Order commits so each one builds on the previous: shared code (harness, `common.h` declarations) before the features that use it.
- Small leftovers that fit nowhere (typos, a stale path) can be one `docs:` / `chore:` commit. Do not make a commit per file.

## 3. Check before committing

- Nothing ignored or big slips in: no `*.z64`, ISO, zip, `local/demo/`, `local/run/`, builds, `.venv`. A new binary over ~2 MB: ask first.
- No game data in git: savestates (`local/states/`), `local/work/main.bin`, `local/game/hang.bin`, `local/bin/` and the game-made `local/game/*.bin` are git-ignored (made locally from the ROM). Never `git add -f` them.
- Another session may be working in the repo at the same time: if files change between `git status` runs, or a diff looks half-done (a test referring to code that is not there), say so and leave those files out.
- Do not run the tests for this (the user's rule: tests only for the feature being worked on, when asked).

## 4. Show the plan, then commit

Print the split as a short list: for each commit, its message subject and its files (hunks: "part of"). With `plan`, stop there.
Otherwise commit right away, one by one:

```bash
git add -- <paths>            # or git apply --cached for hunks
git diff --cached --stat      # it is exactly this commit's files
git commit -F - <<'EOF'
<area>: <what changed, imperative, ≤ 72 chars>

<why, and what a reader of `git log` needs: behaviour change, test results if they were run
in this session, Wrap at ~80.>

<the attribution trailer this session prescribes, if any>
EOF
```

Message rules: English (shared text), area prefix from the table (`hang:`, `lock:`, `gallrun:`, `cheats:`, `harness:`, `video:`, `docs:`, `skills:`, `build:`), no Zelda/OoT names. Body says why; the diff already says what.

## 5. Report

`git log --oneline -<n>` of the new commits and `git status --short` (what is left uncommitted and why). Never push, amend, rebase or reset commits unless the user asks.
