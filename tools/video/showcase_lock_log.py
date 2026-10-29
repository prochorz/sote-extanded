#!/usr/bin/env python3
"""Turn a bots/demo_route.py patch run into a compose_takes.py take (stormtrooper lock-on).

    showcase_lock_log.py demo_patch.json <shots dir> <out dir> [lead-in s] [max s]

demo_route logs every video frame and shoots every 2nd; this keeps the shot entries from
`lead-in` seconds before the fight up to `max` seconds, copies the matching screenshots to
<out dir>/shots and writes <out dir>/lock.json (b as letters, lock flag, aud) + lock.wav.
"""
import glob, json, os, shutil, sys

log_f, shots, out = sys.argv[1:4]
lead = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
mx = float(sys.argv[5]) if len(sys.argv) > 5 else 30.0
log = [e for e in json.load(open(log_f)) if e.get('shot')]
files = sorted(glob.glob(f'{shots}/*.png'))
pairs = list(zip(log, files))
start = next(i for i, (e, _) in enumerate(pairs) if 'lock' in e)        # first fight frame
start = max(0, start - int(lead * 30))
pairs = pairs[start:start + int(mx * 30)]
os.makedirs(f'{out}/shots', exist_ok=True)
res = []
for i, (e, fn) in enumerate(pairs):
    shutil.copy(fn, f'{out}/shots/{i:05d}.png')
    b = ''.join(c for c, m in (('A', 128), ('B', 64), ('Z', 32)) if e['b'] & m)
    label = {'Z-target: strafe + fire': 'Z held: circle the trooper, shots go to the target',
             'Turn toward enemy': 'Turn toward the troopers', 'Run along the route': 'Run through the hangar',
             'Forward again': 'Run through the hangar'}.get(e['label'], e['label'])
    res.append(dict(x=e['x'], y=e['y'], b=b, label=label, lock=e.get('lock', '0x0') != '0x0', aud=e.get('aud', 0)))
json.dump(res, open(f'{out}/lock.json', 'w'))
wav = os.path.join(os.path.dirname(log_f), 'demo_patch.wav')
if os.path.exists(wav): shutil.copy(wav, f'{out}/lock.wav')
print(len(res), 'frames from', start)
