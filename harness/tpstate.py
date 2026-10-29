"""Make a savestate at a debug-menu teleport point, debug flag off afterwards.

    M64CPU=2 python3 tpstate.py <rom> <start state> <next levels> <target x> <out.st>

Loads <start state> (from local/states), runs Next Level <next levels> times, then Teleport
until Dash's x is within 2 units of <target x>, waits ~3 s (cutscenes/messages) with his health
kept full (troopers often stand near teleport points) and saves. The recipe: states_make.teleport().
"""
import sys
import states_make

rom, start, nexts, tx, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
states_make.teleport(rom, start, nexts, tx, out)
