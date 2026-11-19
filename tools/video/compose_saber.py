#!/usr/bin/env python3
"""Compose the saber takes (record_saber_takes.py) into one video with compose_takes.py's layout.

    python3 compose_saber.py <out.mp4> <side shots dir>:<side.json> <front shots dir>:<front.json>

Per clip (sw1, sw2, sw3, spin, combo) and per view a take: the clip at real speed, then (all but the combo) the frames
where the clip's own move plays (SLOW_MOVE) each shown SLOW times, their label + " (1/4 speed)". The takes' frames are
links in a temporary dir (the shots stay where they are). Title "Luke's lightsaber"; no audio.
"""
import json, glob, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SLOW = 4
SLOW_MOVE = {'sw1': 0, 'sw2': 1, 'sw3': 2, 'spin': 3}
TITLES = {'sw1': 'Cut 1', 'sw2': 'Cut 1 + Cut 2', 'sw3': 'Cut 1 + 2 + 3', 'spin': 'Spin (B held)', 'combo': 'Combo, then the spin'}
VIEWS = ('side view', 'front view')


def main():
    out = sys.argv[1]
    views = [a.split(':', 1) for a in sys.argv[2:4]]
    tmp = tempfile.mkdtemp(prefix='saber_')
    args = []
    for clip in TITLES:
        for (shots, logf), vname in zip(views, VIEWS):
            log = json.load(open(logf)); files = sorted(glob.glob(f'{shots}/*.png'))
            pairs = [(ent, f) for ent, f in zip(log, files) if ent['clip'] == clip]
            seq = [(dict(ent), f) for ent, f in pairs]
            if clip in SLOW_MOVE:
                for ent, f in pairs:
                    if ent['m'] == SLOW_MOVE[clip]:
                        e2 = dict(ent, label=ent['label'] + ' (1/4 speed)', b='')
                        seq += [(e2, f)] * SLOW
            d = os.path.join(tmp, f'{clip}_{vname[:4]}'); os.makedirs(d)
            for i, (_, f) in enumerate(seq): os.symlink(os.path.abspath(f), os.path.join(d, f'{i:05d}.png'))
            json.dump([ent for ent, _ in seq], open(d + '.json', 'w'))
            args.append(f'{d}:{d}.json:{TITLES[clip]}, {vname}')
    subprocess.run([sys.executable, os.path.join(HERE, 'compose_takes.py'), out, "Luke's lightsaber",
                    'SotE Extended: the swings, side and front', *args], check=True)


if __name__ == '__main__':
    main()
