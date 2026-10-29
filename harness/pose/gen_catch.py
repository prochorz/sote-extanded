"""Print the catch keyframe table for src/hang.c (catch_keys): python3 gen_catch.py"""
from keys import *
from gen_keys import table
print(table([make_reach(), make_grab(), make_swing()],
            ['reaching for the rim, knees up', 'grabbed it: arms straight, legs swing out', 'swinging back toward the wall']))
