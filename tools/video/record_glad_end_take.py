#!/usr/bin/env python3
"""Record the gladiator's death and Cut 12 (the game's own end of sub-level 27 and the cutscene after it).

    cd harness && for p in 1 2 3; do PART=$p PAYLOAD_BUILD=../local/build/sote-patch RES=960x720 SHOTS=glad_end_p$p \\
        M64CPU=0 AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib python3 ../tools/video/record_glad_end_take.py <rom> \\
        <dir>/glad_end.json || break; done
    python3 ../tools/video/record_glad_end_take.py merge <dir>/glad_end.json     # -> shots/glad_end + json + wav

From xiz_glad2.st (the second phase: Dash on a maze wall, the gladiator flying): Z locks him, B fires; his health
+0x5C4 is written HP_LOW at k 40 so the laser finishes him in a few seconds. He blows up, the game's Level Complete
screen comes up ("Update Data?": D-pad right to NO, then A, once its lines are all drawn: an earlier A is ignored),
then Cut 12 (sub-level 28) plays out untouched (a press there skips it) and the take ends 60 VIs into sub-level 29.
Dash's health held, Debug Display on. Mupen takes at most 1000 shots a run (its own counter, whatever the dir holds),
the take ~2000: it is recorded in parts of SPLIT VIs, each part saving a state (local/run/states/glad_end_<p>.st) the
next one starts from (exit code 0: more to come, 4: the take is complete); `merge` joins the parts' shots, logs
(the `aud` marks offset by the earlier parts' audio; a frame the game did not draw gets the one before) and audio into one take.
JSON one entry per frame {t, x, y, b, label, aud} for compose_takes.py.
"""
import ctypes as C, json, os, shutil, sys, wave
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, BTN
from inject import inject, syms

if sys.argv[1] == 'merge':
    base = os.path.abspath(sys.argv[2])[:-5]; shots = os.path.join(paths.RUN, 'shots', 'glad_end')
    shutil.rmtree(shots, ignore_errors=True); os.makedirs(shots)
    log, pcm, off, i, p, rate = [], b'', 0, 0, 1, 0
    while os.path.exists(f'{base}_p{p}.json'):
        part = json.load(open(f'{base}_p{p}.json'))
        src = iter(sorted(os.listdir(os.path.join(paths.RUN, 'shots', f'glad_end_p{p}'))))
        last = None
        for x in part:                                   # a request with no file: the previous frame again
            f = next(src, None) if x.pop('new', True) or last is None else None
            if f: last = os.path.join(paths.RUN, 'shots', f'glad_end_p{p}', f)
            shutil.copy(last, f'{shots}/f{i:04d}.png'); i += 1
        for x in part: x['aud'] += off
        log += part
        w = wave.open(f'{base}_p{p}.wav'); rate = w.getframerate(); n = w.getnframes(); pcm += w.readframes(n); off += n
        p += 1
    json.dump(log, open(base + '.json', 'w'))
    w = wave.open(base + '.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    print('parts', p - 1, 'frames', len(log), 'shots', i); sys.exit(0)

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
PART, SPLIT = int(os.environ.get('PART', 1)), 1980
K0 = (PART - 1) * SPLIT
OUT = os.path.abspath(sys.argv[2])[:-5] + f'_p{PART}.json'; RAW = OUT[:-5] + '.raw'
os.makedirs(os.path.join(paths.RUN, 'states'), exist_ok=True)
STATE = lambda p: os.path.join(paths.RUN, 'states', f'glad_end_{p}.st')
AUD = C.CDLL(os.environ['AUDIOPLUGIN']) if os.environ.get('AUDIOPLUGIN') else None
if AUD: AUD.audio_dump_frames.restype = C.c_long
G, LEVEL, HP_LOW = 0x8019F4C4, 0x8013CE0E, 30.0
NO_AT, OK_AT = 960, 1000                  # Level Complete: D-pad right (NO), then A
log, st = [], {}


def finish():
    json.dump(log, open(OUT, 'w'))
    if AUD:
        AUD.audio_dump_stop()
        w = wave.open(OUT[:-5] + '.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2)
        w.setframerate(AUD.audio_dump_freq()); w.writeframes(open(RAW, 'rb').read()); w.close(); os.remove(RAW)
    e.stop()


def label(k, lvl):
    if lvl == 27 and k < 200: return 'Rooftop arena: Z locks the flying gladiator, B fires'
    if lvl == 27 and k < 420: return 'The gladiator goes down'
    if lvl == 27: return "The game's Level Complete screen"
    if lvl == 28: return 'Cut 12, as the game plays it'
    return 'Sub-level 29 starts'


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, 'xiz_glad2.st') if PART == 1 else STATE(PART - 1))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66 + K0
    lvl = e.r16(LEVEL)
    pl = e.r32(S['g_player'])
    if 0x80000000 <= pl < 0x80800000 and lvl == 27: e.wf(pl + 0xB4, 100.0)
    e.w32(0x800DA6D0, (e.r32(0x800DA6D0) & 0xFFFF) | (2 << 16))       # Debug Display
    if k == K0 and AUD: AUD.audio_dump_start(RAW.encode())
    if k == 40: e.wf(G + 0x5C4, HP_LOW)
    b, held = 0, ''
    if lvl == 27 and k < 420:
        lk = e.r32(S['g_lock'])
        if lk or k % 30 >= 6: b |= BTN['Z']; held += 'Z'
        if lk and k % 8 < 3: b |= BTN['B']; held += 'B'
    elif lvl == 27 and NO_AT <= k < NO_AT + 4: b, held = BTN['R_D'], 'R'
    elif lvl == 27 and k >= OK_AT and k % 60 < 4: b, held = BTN['A'], 'A'       # again until the level moves on
    e.pad(b)
    if lvl == 29 and 'end' not in st: st['end'] = k + 60
    if k % 2 == 0 and log:                               # did the last request give a file? (none on frames the game
        c = sum(f.endswith('.png') for f in os.listdir(e.shot_dir))   # does not draw: Level Complete, loading)
        log[-1]['new'] = c > st.get('files', 0); st['files'] = c
    if k % 2 == 0 and k <= K0 + SPLIT:
        e.shot()
        log.append(dict(t=k // 2, x=0, y=0, b=held, label=label(k, lvl), aud=AUD.audio_dump_frames() if AUD else 0))
    if k % 120 == 0: print(k, 'lvl', lvl, 'ai', e.r32(G + 0x584), 'hp', round(e.rf(G + 0x5C4), 1), flush=True)
    if k == st.get('end'): st['done'] = True; finish()
    elif k == K0 + SPLIT: e.save_state(STATE(PART))
    elif k == K0 + SPLIT + 4: finish()                 # the save is taken on a later frame: stop after it


e.run(script)
print('part', PART, 'frames', len(log), 'complete' if st.get('done') else 'more', flush=True)
sys.exit(4 if st.get('done') else 0)
