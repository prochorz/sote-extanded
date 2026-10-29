"""Make Dash hang on the crevasse and dump RAM 60 frames later (OUT, default local/game/hang.bin), for the pose tools.

    cd harness/pose && M64CPU=0 python3 dump_hang.py <patched rom>
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
from m64 import Emu, HERE
from inject import inject, syms
S = syms(); e = Emu(sys.argv[1]); st = {'g': None}
OUT = os.environ.get('OUT', os.path.join(paths.GAME, 'hang.bin'))
def script(e, n):
    if n == 60: e.load_state(os.path.join(paths.STATES, 'echo_crevasse.st'))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player']); e.wf(pl + 0xB4, 100.0)
    if st['g'] is None and e.r32(S['g_hang_state']): st['g'] = k
    g = st['g']
    e.pad(0, 80 if g is None and k >= 6 else 0, 0)
    if g is not None and k == g + 60:
        e.dump(OUT); e.shot(); print('player', hex(pl), flush=True); e.stop()
e.run(script)
