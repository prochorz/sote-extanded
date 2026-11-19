#!/usr/bin/env python3
"""The fly-away's nose pitch step read back from hang_hit.py --hull logs (for logs made before HULLSUM had it):
the largest |nose pitch change| between HULL frames from 0.3 s into the fly-away, and HULLSUM's other numbers.
  python3 harness/gallrun/hull_pstep.py <log>..."""
import sys, re
for p in sys.argv[1:]:
    last, ps, at = None, 0.0, None
    for ln in open(p, errors='replace'):
        m = re.search(r"HULL away (\S+) .*nose pitch (\S+) nose yaw", ln)
        if m and m.group(2) != 'None':
            a, pd = float(m.group(1)), float(m.group(2))
            if last is not None and a >= 0.3 and abs(pd - last) > ps: ps, at = abs(pd - last), a
            last = pd
        if ln.startswith('HULLSUM'):
            f = lambda k: re.search(k + r" (\S+)", ln).group(1)
            print(p, 'pitch step max (after 0.3 s)', round(ps, 2), 'at away', at, '| pitch rev', f('nose pitch reversals'),
                  'yaw rev', f('nose yaw reversals'), 'frames', f('fly-away frames'), 'hp first', f('hp first'), 'least', f('least'))
