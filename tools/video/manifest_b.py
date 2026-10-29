#!/usr/bin/env python3
"""Write local/run/video/manifest_B.json for the step-B takes recorded by record_b.py.

    python3 tools/video/manifest_b.py

One entry per take: {order, section, title, caption, kind, shots, log, wav, frames, seconds}.
single: shots = the take's segment dirs in order, log = one merged JSON (entries carry seg / dir),
wav = the segments' WAVs in order. side_by_side: shots / log / wav are [original, patch].
A take with several sub-takes (the gladiator's two phases) is merged the same way as segments.
"""
import glob, json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'local')
VID = os.path.join(ROOT, 'run', 'video')
SHOTS = os.path.join(ROOT, 'run', 'shots')

TAKES = [
    (1, 'Z lock-on', 'IG-88', 'single', ['ig88c'],
     'Z locks on IG-88. Dash circle-strafes round him and every shot flies into the lock.',
     'fight then, without a cut, his death scene, the Level Complete screen (A pressed on its "Update Data? YES" ~3 s '
     'after it is written in full) and Cut 05 up to its first picture (the take ends ~1 s into it). drop=1 entries '
     '(t ranges in drops) are stretches where he leapt out of the lock and the camera may face a wall without him: cut '
     'them. Label "IG-88 down": his death and the Level Complete screen; "Cut 05": the first picture. Frames are sparse '
     'while the game draws nothing new (death fade, load): sync by each entry\'s aud. His health is lowered 0.3 a frame '
     'while locked on top of the real hits; video-only RAM patches (record_b.py NOHIT): no hit flash, no knock-back on Dash'),
    (1.1, 'Z lock-on', 'Stormtroopers, Echo Base', 'single', ['zen_echo'],
     'Z locks the nearest trooper. Dash circle-strafes and fires till it drops, then Z again: the lock moves to the next.',
     'Echo Base hangar (states/play.st; Dash walks the demo route first, not recorded): five troopers dropped one '
     'after another, ~9 s. The hook drives Z, B and the stick (record_b.py zen_hook). Labels: "Z: lock the nearest '
     'trooper", "Circle-strafe, every shot flies into the lock", "Trooper down. Z again: the next one", "Next target: '
     'the lock moves on", "Z released: lock off". The orange bursts are blaster hits on the floor, not the hit flash; '
     'NOHIT on'),
    (1.2, 'Z lock-on', "Royal guards, Xizor's palace", 'single', ['zen_xiz'],
     "Xizor's palace: the same against the red royal guards, three in a row.",
     "states/lvl8.st, the debug list's Amb Light raised to 200 (a little brighter); the guards stand 30-90 units "
     "away, small in the frame but the lock marker is on them. ~0.6 s at ~4.5 s into the take the lock drops (line "
     "of sight) and Z takes it again; NOHIT on"),
    (2, 'Z lock-on', 'The gladiator droid', 'single', ['glad_a', 'glad_b'],
     'Xizor\'s palace: Z locks the gladiator on the ground, then again when he flies, not the troopers below.',
     'two sub-takes: on the roof, then flying (Dash written to the maze floor ~12 units from him, he flies above); '
     'video-only RAM patches (record_b.py NOHIT): no hit flash and no knock-back on Dash, so his bombs no longer '
     'blow Dash off the roof and the screen does not go orange'),
    (3, 'Z lock-on', 'AT-ST, Echo Base', 'single', ['atst'],
     'Z locks the AT-ST: circle it both ways, the laser goes to the cockpit.'),
    (4.1, 'Controls: original vs patch', 'Camera-relative movement', 'side_by_side', ['sbs_move'],
     'Same stick input. Original: up/down walk, left/right turn. Patch: Dash runs where you push.'),
    (4.2, 'Controls: original vs patch', 'Moving in any direction', 'side_by_side', ['sbs_move2'],
     'Right, up, left, down and diagonals: the patch runs each way at once, no turning on the spot.'),
    (4.3, 'Controls: original vs patch', 'Stairs', 'side_by_side', ['sbs_stairs'],
     'Up the stairs and back down toward the camera: the camera stays level.'),
    (4.4, 'Controls: original vs patch', 'Ledge hang', 'side_by_side', ['sbs_hang'],
     'Stick down. Original: Dash backs along the bridge. Patch: he runs off the edge, catches it, climbs up.'),
    (4.5, 'Controls: original vs patch', 'Ord Mantell train', 'side_by_side', ['sbs_train'],
     'On the train: run toward the camera, step aside, Z swings the camera round behind Dash.'),
    (4.6, 'Controls: original vs patch', 'Train: Z keeps the facing', 'side_by_side', ['sbs_train2'],
     'Turn Dash across the car, Z: the camera goes behind him and he keeps his facing.'),
    (5.1, 'Cheats', 'Leebo Scanner', 'single', ['c_leebo'],
     'Pause, Cheats, Leebo Scanner: the game\'s secret top-down view, switched on from the menu.'),
    (5.2, 'Cheats', 'Jetpack Fuel', 'single', ['c_fuel'],
     'Jetpack Fuel: the tank never runs dry and the fuel number turns blue.'),
    (5.3, 'Cheats', 'Ship', 'single', ['c_ship'],
     'Skyhook in an X-Wing or a TIE Fighter instead of the Outrider (the game\'s secret ships).'),
    (5.4, 'Cheats', 'Creature Cam on foot', 'single', ['c_creature'],
     'Creature Cam: the camera follows a wampa or a trooper, and the stick walks it.'),
    (5.5, 'Cheats', 'Creature Cam: AT-ST on Hoth', 'single', ['c_atst'],
     'On Hoth the row picks the AT-ST: the player walks the walker and fires.'),
    (5.6, 'Cheats', 'Friendly Wampas', 'single', ['c_friendly'],
     'Friendly Wampas: a wampa walks up to Dash and calms down instead of attacking.'),
    (5.7, 'Cheats', 'Invincibility', 'single', ['c_god'],
     'Troopers shoot, health drops. Invincibility on: the health number turns blue and stays.'),
    (5.8, 'Cheats', 'Go to level: the Gall Run', 'single', ['c_level'],
     'Go to level browses every sub-level by name, number 32 is the Gall Run bonus mission.'),
    (7.1, 'Ledge catch', 'Catching the edge', 'single', ['jump2'],
     'Gall\'s start: from the post onto the Outrider, catch the edge, climb, take the silver Challenge Point.',
     'Gall 6a start (states/lvl4.st; Dash spawns inside the Outrider): Dash written onto the orange post beside the ship '
     '(top 212.9 at (-295.5, 962)), world 270 with A 3 VIs in; he catches the dark side of the hull (rim ~216), climbs to '
     'the deck (~221), runs west and jumps at 11 units from the point (-314, 950, 229.1): the game shows "Challenge '
     'Point" (bottom right). The last ~1 s is a close-up: he lands by the canyon wall past the point; NOHIT on'),
    (8.1, 'Finale: Gall on foot', 'Canyon rims', 'single', ['f_tp5'],
     'Gall: walk off a canyon rim, Dash catches it, hangs, climbs, and again.'),
    (8.2, 'Finale: Gall on foot', 'More rims', 'single', ['f_tp6'],
     'Another canyon path: catch, hang, climb.'),
    (8.3, 'Finale: Gall on foot', 'On the cliffs', 'single', ['f_stand'],
     'On the cliffs by the fortress: hang, climb, hang again.'),
]


def segs(name):
    out = []
    for s in range(10):
        j = os.path.join(VID, f'b_{name}_{s}.json')
        if not os.path.exists(j): break
        out.append((s, os.path.join(SHOTS, f'vid_b_{name}{s}'), j, os.path.join(VID, f'b_{name}_{s}.wav')))
    return out


def merged(names, out_name):
    ents, dirs, wavs = [], [], []
    for nm in names:
        for s, d, j, w in segs(nm):
            for e in json.load(open(j)): e['dir'] = os.path.basename(d); ents.append(e)
            dirs.append(d); wavs.append(w)
    path = os.path.join(VID, f'b_{out_name}.json')
    json.dump(ents, open(path, 'w'))
    return dirs, path, wavs, len(ents)


man = []
for order, sec, title, kind, names, cap, *note in TAKES:
    if kind == 'single':
        dirs, log, wavs, n = merged(names, names[0] if len(names) == 1 else names[0].split('_')[0])
        if not n: continue
        man.append(dict(order=order, section=sec, title=title, caption=cap, kind=kind, shots=dirs, log=log, wav=wavs,
                        frames=n, seconds=round(n / 30, 1), **(dict(note=note[0]) if note else {})))
        if names == ['ig88c']:                     # the fight runs on into Cut 05; drop ranges from the take's context
            ctx = json.load(open(os.path.join(VID, 'b_ig88c_ctx.json')))
            ents = json.load(open(log))
            man[-1].update(ig88_to_c05=True, drops=ctx.get('drops', []),
                           fight_seconds=round(sum(1 for e in ents if e['t'] < ctx['dead'] and not e.get('drop')) / 30, 1),
                           after_death_frames=sum(1 for e in ents if e['t'] >= ctx['dead']))
    else:
        o = merged([names[0] + '_orig'], names[0] + '_orig'); p = merged([names[0] + '_patch'], names[0] + '_patch')
        if not (o[3] and p[3]): continue
        man.append(dict(order=order, section=sec, title=title, caption=cap, kind=kind, shots=[o[0][0], p[0][0]],
                        log=[o[1], p[1]], wav=[o[2][0], p[2][0]], frames=[o[3], p[3]], seconds=round(p[3] / 30, 1),
                        note='shots / log / wav: [original (unpatched game), patch], same input'))
json.dump(man, open(os.path.join(VID, 'manifest_B.json'), 'w'), indent=1)
for m in man: print(m['order'], m['title'], m['seconds'], 's')
print('total', round(sum(m['seconds'] for m in man) / 60, 1), 'min')
