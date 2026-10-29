#!/bin/sh
# From a fresh clone and your own ROM (Star Wars: Shadows of the Empire, USA Rev 2, the .z64), make everything the
# build needs, under local/ (SOTE_LOCAL moves it, as harness/paths.py): the ROM copied to local/rom/, the harness's
# dylibs, the savestates the assets come from (harness/bootstrap.py), local/work/main.bin (the game's code part,
# harness/make_main.py) and the assets in local/game/. Each step is skipped when its output exists; one OK line at
# the end. Then: tools/release.sh (or build.py). Needs mupen64plus (Homebrew), the LLVM toolchain, python3 with numpy.
# --tests also makes the states the tests use that need no event (bootstrap.py --tests); not made here: hang.bin and
# the event states (docs/harness.md, Savestates).
#
#     tools/setup.sh <your rom.z64> [--tests]
set -e
[ -f "$1" ] || { echo "usage: tools/setup.sh <rom.z64> [--tests]"; exit 1; }
TESTS=
case "$2" in --tests) TESTS=--tests;; "") ;; *) echo "usage: tools/setup.sh <rom.z64> [--tests]"; exit 1;; esac
SRC=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
cd "$(dirname "$0")/.."
TOP=$PWD
L="${SOTE_LOCAL:-local}"
case "$L" in /*) ;; *) L="$TOP/$L";; esac
export SOTE_LOCAL="$L"
ROM="$L/rom/Star Wars - Shadows of the Empire (USA) (Rev 2).z64"
PY=python3
[ -x harness/.venv/bin/python3 ] && PY="$TOP/harness/.venv/bin/python3"
LOG="$L/run/setup"
mkdir -p "$L/rom" "$L/game" "$L/work" "$LOG"

step() {    # step <output> <log name> <command...>: run unless the output exists, its output in $LOG/<name>.log
    out=$1; name=$2; shift 2
    [ -e "$out" ] && return 0
    echo "make $name"
    (cd "$TOP/harness" && "$@") >"$LOG/$name.log" 2>&1 || { tail -20 "$LOG/$name.log"; echo "FAILED $name: $LOG/$name.log"; exit 1; }
    [ -e "$out" ] || { echo "FAILED $name: no $out ($LOG/$name.log)"; exit 1; }
}

[ -e "$ROM" ] || cp "$SRC" "$ROM"
step "$L/bin/audio_dump.dylib" dylibs make -C "$TOP/harness"
"$PY" "$TOP/harness/bootstrap.py" "$ROM" $TESTS
step "$L/work/main.bin" main_bin "$PY" make_main.py
step "$L/game/gall_level_stock.bin" level_blob env M64CPU=0 "$PY" level_blob.py "$ROM" 6 "$L/game/gall_level_stock.bin"
step "$L/game/falcon.bin" falcon env M64CPU=0 "$PY" falcon_asset.py "$ROM"
step "$L/game/gall_level.bin" level_edit "$PY" gallrun/level_edit.py          # (needs falcon.bin)
step "$L/game/gall_run.bin" gall_run env M64CPU=0 M64HANG=0 M64MAXSEC=0 "$PY" gallrun/gall_asset.py "$ROM" # (M64HANG=0: ~100 s of work after the dumps, emulator idle)
echo "OK $L: states, main.bin, $(cd "$L/game" && ls | tr '\n' ' ')"
