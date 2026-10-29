#!/bin/bash
# The Gall Run's --check runs (the skill sote-test's Gall Run row), 4 at a time, from the build's ladder states
# local/run/<build>_*.st (made first, each from the one before: c05_check.py -> _c05_f8, peel_check.py --make -> _peel,
# hang_hit.py --make -> _end, then --save-at rail,dash,free; fin_check.py --make -> _fin_ours). One log per run in local/run/<build>_chk_<name>.log;
# prints one PASS / FAIL line per run (exit status) and exits 1 if any failed.
#   harness/gallrun/check_row.sh <build dir>      e.g. local/build/bf91
set -u
H=$(cd "$(dirname "$0")/.." && pwd)
ROM=$(cd "$1" && pwd)/sote-patch.z64
B=$(basename "$(dirname "$ROM")")
cd "$H" || exit 2
PY=.venv/bin/python3
S=../local/run/${B}
run() {   # name, then the command's args (tool first)
    local n=$1; shift
    M64CPU=2 SHOTS=chk_${B}_$n $PY "$@" > "${S}_chk_$n.log" 2>&1
    echo "$n $?" >> "${S}_chk.rc"
}
rm -f "${S}_chk.rc"
jobs_wait() { while [ "$(jobs -rp | wc -l)" -ge 4 ]; do sleep 1; done; }
for spec in \
  "peel|gallrun/peel_check.py $ROM --check" \
  "peel_p150|gallrun/peel_check.py $ROM --check --side 150" \
  "peel_m150|gallrun/peel_check.py $ROM --check --side -150" \
  "lines|gallrun/peel_check.py $ROM --make ${S}_c05_f8.st --lines --check" \
  "clear|gallrun/hang_hit.py $ROM --clear --check" \
  "look|gallrun/falcon_look.py $ROM --check ${S}_c05_f3.st ${S}_fin_ours.st ${S}_peel.st ${S}_free.st" \
  "battle|gallrun/hang_hit.py $ROM --from ${S}_free.st --battle --check" \
  "stick80|gallrun/hang_hit.py $ROM --from ${S}_free.st --stick 80 --check" \
  "stick0|gallrun/hang_hit.py $ROM --from ${S}_free.st --stick 0 --check" \
  "cam|gallrun/hang_hit.py $ROM --from ${S}_dash.st --cam --frames 600 --check" \
  "window|gallrun/hang_hit.py $ROM --from ${S}_rail.st --view 4 --window --frames 1600 --check" \
  "fade|gallrun/hang_hit.py $ROM --from ${S}_free.st --fade --fade-luke --frames 600 --check" \
  "fin|gallrun/fin_check.py $ROM --from ours --falcon --check" \
  "hull_trail|-" \
  "timers|-" \
  "ram|-" ; do
    n=${spec%%|*}; c=${spec#*|}; jobs_wait
    case $n in
      hull_trail) ( run hull gallrun/hang_hit.py "$ROM" --from "${S}_free.st" --save-at jump --hull --check
                    run trail gallrun/hang_hit.py "$ROM" --from "${S}_jump.st" --trail --frames 120 --check ) & ;;
      timers) ( STATE=${S}_free.st run timers gallrun/respawn_probe.py "$ROM" --timers --check ) & ;;
      ram) ( STATE=${S}_free.st RAM_N=5 run ram gallrun/respawn_probe.py "$ROM" --ram --check ) & ;;
      *) run "$n" $c & ;;
    esac
done
wait
fail=0
while read -r n rc; do
    if [ "$rc" = 0 ]; then echo "PASS $n"; else echo "FAIL $n (rc $rc, ${S}_chk_$n.log)"; fail=1; fi
done < <(sort "${S}_chk.rc")
exit $fail
