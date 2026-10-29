---
name: sote-release
description: Build a fresh release ROM of the SotE controls patch and send it to the user. Use when the user asks for the latest/fresh ROM ("give me the ROM", "build a fresh ROM", "the latest ROM", "a link to the ROM").
model: haiku
effort: low
allowed-tools: Bash(tools/release.sh), SendUserFile
---

1. Run `tools/release.sh` from the repo root (one Bash call, timeout 600000). Do not read the build log
   unless it fails; on failure show the printed tail to the user and stop.
2. On `OK <path> ...` send `<path>` with SendUserFile: `display: "attach"`, `status: "normal"`,
   caption in English: "Fresh build (MD5 <first 8 hex>…, save carries over)".
   The ROM carries the Gall Run bonus mission (a default feature since 2026-10-24).
3. Reply in Ukrainian with one line: file name and MD5 prefix. Nothing else: no tests, no summaries
   of changes, no re-reading code. Never run the test suite before a release (the user's rule:
   the whole suite only on request).
