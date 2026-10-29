"""local/work/main.bin from your own game: the main executable's code part, 0x80001EC0 up to 0x800D06E8, read from
local/states/play.st's RAM (the code is not changed in RAM; the data after it is, from power-on, and already the word
at 0x800D06F4 differs from run to run, so it is not written: inject.py, disasm.py and decomp.py read code only).

    python3 make_main.py [<state>]        # default play.st (bootstrap.py makes it); writes paths.WORK/main.bin
"""
import os, sys
import paths
from states_cmp import ram

START, END = 0x80001EC0, 0x800D06E8

if __name__ == '__main__':
    st = sys.argv[1] if len(sys.argv) > 1 else os.path.join(paths.STATES, 'play.st')
    E = ram(st)
    os.makedirs(paths.WORK, exist_ok=True)
    out = os.path.join(paths.WORK, 'main.bin')
    with open(out, 'wb') as f: f.write(E[START & 0x7FFFFF:END & 0x7FFFFF])
    print(f'{out}: {END - START} bytes, {START:#x}..{END:#x} from {st}')
