#!/usr/bin/env python3
"""Compose the Gall Run flight video from record_gallrun_take.py segments.

    harness/.venv/bin/python3 tools/video/compose_gallrun.py out.mp4 local/run/gallrun_take{0..7}.json

1280x720: title card, then the game (960x720) with a side panel (title, stage and its notes from
the logged route node, elapsed time);
frames after the run ends (dark or another sub-level) are cut. Audio: each segment's wav retimed
to its frames (make_demo_video.aligned_audio), then joined.
"""
import glob, json, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_demo_video import aligned_audio, FPS

BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
REG = '/System/Library/Fonts/Supplemental/Arial.ttf'
TITLE = 'Gall Run'
SUB = 'Millennium Falcon bonus mission, two stages'
STAGES = [('Stage 1: the canyon run', ['The Falcon follows', 'the Outrider through', 'the canyon', '',
                                          'Floor in Gall\'s textures,', 'canyon 6x wider,', '9x taller', '', 'Knife-edge through', 'the slits, Dash on', 'the radio']),
          ('Stage 2: the gunner', ['You are the gunner:', 'fight off the TIEs', '',
                                    'Open landscape', 'in Gall\'s textures,', 'pieces moved together', '',
                                    'Low between the rocks', '(pressed down along', 'the route)', '', 'Lando and Chewie', 'on the radio'])]
CARD_S = 3
if os.environ.get('INTRO'):                            # INTRO=1: the opening shot alone
    SUB = 'Opening shot'
    STAGES[0] = ('Into the canyon', ['A fly-by after Station', 'Chase\'s level start:', 'the camera stands still,', 'Dash\'s Outrider passes', 'close below it', '',
                                          'Then the Falcon, kept', 'out of view, passes slowly', 'right over the camera, and', 'the camera chases it:', 'you fly the', 'Falcon, not the Outrider'])

if os.environ.get('JOIN'):                             # JOIN=1: stage 1's end into stage 2's cutting
    SUB = 'Between the stages'
    STAGES[0] = ('End of the canyon run', ['Dash leaves; the canyon', 'narrows ahead'])
    STAGES[1] = ('Into stage 2', ['A canyon piece from', 'later in the run, turned', 'and drawn half size,', 'leads from stage 1\'s', 'wide floor into the', 'narrow cutting', '',
                                  'The ships go on edge', 'in the cutting', '', 'Lando and Chewie', 'on the radio'])
if os.environ.get('FLY'):                              # FLY=1: stage 1 flown freely (a bot's own way)
    SUB = 'Stage 1 flown freely'
    STAGES[0] = ('Stage 1: the canyon run', ['You fly the Falcon:', 'turn, climb, dive,', 'A faster, B slower', '',
                                          'The canyon\'s own rock', 'is solid: its drawn', 'triangles, as you see', 'them', '',
                                          'Z: on edge through', 'a slit, or fly over', 'its wall', '',
                                          'A bot pilot picks its', 'own way: here over', 'both slit walls', '',
                                          'Dash waits if you', 'fall behind; TIEs come,', 'Dash leaves'])
if os.environ.get('STAGE1'):                           # STAGE1=1: stage 1 as it is now, the opening shot to the switch
    SUB = 'Stage 1: the canyon run'
    STAGES[0] = ('Stage 1: Gall\'s cliffs', ['You fly the Falcon after', 'Dash\'s Outrider; a bot', 'pilot here', '',
                                          'Walls as before the', 'smoothing; slits carved', 'at least 8 units either', 'side of the route', '',
                                          'Z: on edge through a', 'slit; the assist pulls', 'you onto its line, your', 'height kept', '',
                                          'TIEs come in at the', 'end and hold fire', 'until stage 2; Dash', 'leaves'])
    STAGES[1] = ('Stage 2 begins', ['The gunner stage:', 'the TIEs open fire'])
if os.environ.get('SCENE'):                            # SCENE=1: the scene at the route's end
    SUB = 'The end: Slave I and the chase'
    STAGES[0] = STAGES[1] = ('At Slave I\'s pad', ['The Falcon slows down', 'by the pad from Gall\'s', 'Boba Fett level', '',
                             'Dash jets up out of', 'the tower and lands', 'on its wall', '',
                             'Leia sends Leebo', '',
                             'Slave I rises behind', 'Dash, fires, flies over', 'the camera and runs', '',
                             'The Falcon turns round', 'the tower after it;', 'the Outrider picks', 'Dash up and joins', 'the chase', '',
                             'Then the chase, as', 'stage 2: on after', 'Slave I up the canyon', 'into space, TIEs', 'attack, the gunner', 'shoots back (not at', 'Slave I: Han is in it)', '',
                             'In space: rocks', 'and the belt'])
MISSION = None                                         # MISSION=1: the whole mission, notes by the route node
if os.environ.get('MISSION'):
    import struct as _st
    _h = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'local', 'game', 'gall_run.bin'), 'rb').read(256)
    _end, _r0 = _st.unpack_from('>I', _h, 28)[0], _st.unpack_from('>I', _h, 164)[0]
    MISSION = (_end, _r0, _r0 + 228)                   # (gallrun.c SC_DASH: Dash's shot)
    SUB = 'Millennium Falcon bonus mission, start to end'
    STAGES[:] = [('Stage 1: Gall\'s cliffs', ['You fly the Falcon after', 'Dash\'s Outrider', '(a bot pilot here)', '',
                                            'Z: on edge through', 'the slits', '',
                                            'TIEs come in at the', 'end and hold fire;', 'Dash leaves']),
                 ('Stage 2: the gunner', ['On rails between the', 'cliffs: shoot the TIEs', 'on the tail', '',
                                          'Lando and Chewie', 'on the radio']),
                 ('At Slave I\'s pad', ['Dash on the tower,', 'Leebo picks him up;', 'Slave I rises and runs', '',
                                       'The Falcon turns', 'after it']),
                 ('The chase', ['On rails after Slave I', 'up the canyon into', 'space; the sky goes', 'black', '',
                                'TIEs attack: shoot', 'back, not at Slave I', '(Han is aboard)']),
                 ('In space', ['A Star Destroyer and', 'a battle of X-Wings', 'and TIEs', '',
                               'Dash quits and jumps', 'to lightspeed (a white', 'trail behind him); the', 'Falcon closes in, but', 'Slave I jumps too']),
                 ('The final battle', ['Free flight on the', 'game\'s own ship', 'handling: A faster,', 'R slower', '',
                                       'Fight the TIEs with the', 'X-Wings round the', 'Star Destroyer', '(a bot pilot here)'])]
STAGE3 = os.environ.get('STAGE3')                   # STAGE3=1: from the Falcon in space to the mission's end, by the log's
if STAGE3:                                             # label ('' the rail, 'free', 'won')
    SUB = 'Stage 3: in space'
    STAGES[:] = [('The chase in space', ['On rails after Slave I;', 'TIEs on the tail', '',
                                         'A Star Destroyer ahead,', 'X-Wings and TIEs', 'fighting over it', '',
                                         'Dash sees what they are', 'in for and jumps to', 'lightspeed', '',
                                         'The Falcon closes in', 'past the Star Destroyer;', 'Slave I jumps too']),
                 ('Free flight', ['Fly anywhere round the', 'Star Destroyer; the', 'rock belt rings it', '',
                                  'Fight the TIEs with the', 'X-Wings (Wedge on the', 'radio); 7 hits a TIE', '',
                                  '15 down wins', '(a bot pilot: first a', 'lap round the ship)']),
                 ('Mission complete', ['Lando: "Punch it,', 'Chewie!"', '', 'Back to where the', 'mission was started'])]
ROLL = int(os.environ.get('ROLL', 0))                # ROLL=<node>: the opening shot and stage 1 up to that
ROLL_FROM = 150                                       # node (the first slit, the Outrider's barrel roll)
if ROLL:
    SUB = 'Opening shot and the first slit'
    STAGES.append(('The first slit', ['Both ships go on edge', 'through the slit', '',
                                      'Coming off the edge the', 'Outrider rolls on round:', 'a full barrel roll', '',
                                      'Dash on the radio']))
out, logs = sys.argv[1], sys.argv[2:]
frames, audio, rate = [], [], None
for lg in logs:
    shots = sorted(glob.glob(os.path.join(os.path.dirname(lg), 'shots', os.path.basename(lg)[:-5], '*.png')))
    ent = json.load(open(lg)); n = min(len(ent), len(shots))
    keep = n
    for i in range(n - 1, -1, -1):                       # cut the dark tail after the run ends
        if np.asarray(Image.open(shots[i]).convert('L').resize((64, 48))).mean() > (3 if MISSION or STAGE3 else 40): break   # (space is dark)
        keep = i
    if ROLL:                                             # up to the node, then a second more
        last = next((i for i in range(keep) if ent[i].get('node', 0) >= ROLL), keep)
        keep = min(keep, last + FPS)
    def part(e):
        nd, sw = e.get('node', 0), e.get('switch', 1 << 30)
        if MISSION:
            end, r0, sc = MISSION
            if e.get('label') in ('free', 'won'): return 5
            return 0 if nd < sw else 1 if nd < end - 1 else 2 if nd < r0 else 3 if nd < sc else 4
        if STAGE3: return {'free': 1, 'won': 2}.get(e.get('label'), 0)
        return 2 if ROLL and nd >= ROLL_FROM else int(nd >= sw)
    frames += [(f, part(ent[i])) for i, f in enumerate(shots[:keep])]
    a, rate = aligned_audio(lg[:-5] + '.wav', ent, keep)
    audio.append(a)
print('frames', len(frames))
tmp = tempfile.mkdtemp()
f = lambda b, s: ImageFont.truetype(BOLD if b else REG, s)
card = Image.new('RGB', (1280, 720), (12, 12, 18)); d = ImageDraw.Draw(card)
d.text((640, 300), TITLE, font=f(1, 72), fill=(255, 232, 31), anchor='mm')
d.text((640, 380), SUB, font=f(0, 34), fill=(230, 230, 235), anchor='mm')
d.text((640, 430), 'Bonus mission prototype - Shadows of the Empire (N64)', font=f(0, 24), fill=(150, 150, 160), anchor='mm')
k = 0
for _ in range(CARD_S * FPS): card.save(f'{tmp}/{k:05d}.png'); k += 1
for i, (s, st2) in enumerate(frames):
    im = Image.new('RGB', (1280, 720), (12, 12, 18)); im.paste(Image.open(s).convert('RGB').resize((960, 720)), (0, 0))
    d = ImageDraw.Draw(im)
    d.text((980, 30), TITLE, font=f(1, 40), fill=(255, 232, 31))
    name, notes = STAGES[st2]
    d.text((980, 80), 'Bonus mission', font=f(0, 20), fill=(150, 150, 160))
    d.text((980, 130), name, font=f(1, 21), fill=(230, 230, 235))
    for j, line in enumerate(notes): d.text((980, 175 + 28 * j), line, font=f(0, 20), fill=(170, 170, 180))
    sec = i / FPS; d.text((980, 660), f'{int(sec // 60)}:{int(sec % 60):02d}', font=f(1, 30), fill=(255, 255, 255))
    im.save(f'{tmp}/{k:05d}.png'); k += 1
a = np.concatenate([np.zeros(CARD_S * rate, np.float32)] + audio)
a = np.clip(a, -32768, 32767).astype('<i2')
w = wave.open(f'{tmp}/a.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(a.tobytes()); w.close()
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/%05d.png', '-i', f'{tmp}/a.wav',
                '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                '-shortest', '-movflags', '+faststart', out], check=True)
print('wrote', out)
