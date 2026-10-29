"""Boot a ROM from power-on into carousel level L and save a state when Dash is controllable.

    M64CPU=2 python3 mkstate.py <rom> <level> [out.st]

Use the original ROM (or the patched one: the payload is re-injected after load anyway).
Message boxes at level start are dismissed with START. The recipe: states_make.boot().
"""
import os, sys
from m64 import RUN
import states_make

rom, level = sys.argv[1], int(sys.argv[2])
states_make.boot(rom, level, sys.argv[3] if len(sys.argv) > 3 else os.path.join(RUN, 'states', f'lvl{level}.st'))
