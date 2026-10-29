#!/bin/sh
# Release build of the controls patch: build with the save-keeping MD5 prefix, copy to the
# "[SotE Extended]" ROM in local/rom/, print one summary line (path, size, MD5).
# SOTE_LOCAL (as harness/paths.py) moves local/: a scratch dir with its own rom/, game/, build/.
set -e
cd "$(dirname "$0")/.."
L="${SOTE_LOCAL:-local}"
ROM="$L/rom/Star Wars - Shadows of the Empire (USA) (Rev 2).z64"
OUT="$L/rom/Star Wars - Shadows of the Empire (USA) (Rev 2) [SotE Extended].z64"
case "$L" in /*) ;; *) L="$PWD/$L"; ROM="$PWD/$ROM"; OUT="$PWD/$OUT";; esac
LOG="$L/build/release.log"
mkdir -p "$L/build"
(cd sote-patch && python3 build.py "$ROM" --md5-prefix 7DC1ECE7) >"$LOG" 2>&1 || { tail -20 "$LOG"; exit 1; }
cp "$L/build/sote-patch/sote-patch.z64" "$OUT"
MD5=$(md5 -q "$OUT")
case "$MD5" in 7dc1ece7*) ;; *) echo "MD5 $MD5 lost the 7dc1ece7 prefix"; exit 1;; esac
echo "OK $OUT $(stat -f%z "$OUT") bytes, MD5 $MD5, $(grep -io 'payload[^,]*' "$LOG" | tail -1)"
