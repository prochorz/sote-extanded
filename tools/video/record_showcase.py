#!/usr/bin/env python3
"""Record one take of the feature showcase video, with game audio.

    make -C harness           (the dylibs into local/bin/)
    RES=960x720 SHOTS=<take> M64CPU=0 AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib \\
        python3 ../tools/video/record_showcase.py <rom> <take> <out.json>

Takes:
    move    Echo Base hangar (play.st): run forward, toward the camera (face visible), stop,
            the camera eases round behind him; run sideways, stop, again
    stairs  stairs after the lift (echo_stairs.st): up, then back down toward the camera
    hang    crevasse (echo_crevasse.st): run off the edge, hang, fire (no shot), climb up
    atst    AT-ST arena (echo_atst.st): Z lock, circle-strafe both ways firing, release

Frames every 2nd video frame (30 fps) in local/run/shots/<SHOTS>/; JSON entries
{t, x, y, b, label, hang, lock, aud} for compose_takes.py; audio in <out>.wav.
The stormtrooper lock-on take comes from bots/demo_route.py (see showcase_lock_log.py).
"""
import ctypes as C, json, math, os, sys, wave
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, BTN, HERE
from inject import inject, syms

S = syms()
e = Emu(sys.argv[1], video=m64.GLN)
TAKE, OUT = sys.argv[2], sys.argv[3]
RAW = OUT[:-5] + '.raw'
AUD = C.CDLL(os.environ['AUDIOPLUGIN']) if os.environ.get('AUDIOPLUGIN') else None
if AUD: AUD.audio_dump_frames.restype = C.c_long
STATE = dict(move='play.st', stairs='echo_stairs.st', hang='echo_crevasse.st', atst='echo_atst.st')[TAKE]
SETTLE = dict(hang=150).get(TAKE, 60)
log, st = [], {'stop': None, 'grab': None}


def take_move(e, t, pl):
    moves = [(10, 120, 0, 80), (135, 185, 0, -80), (390, 440, 80, 0)]
    x = y = 0
    for a, b, sx, sy in moves:
        if a <= t < b: x, y = sx, sy
    if x or y: st['stop'] = None
    elif st['stop'] is None: st['stop'] = t
    facing = (e.rf(pl + 0x8C) + 270) % 360 - 180
    diff = abs((facing - e.rf(S['g_cam_facing']) + 180) % 360 - 180)
    if x or y:
        lab = {80: 'Stick up: run where the camera looks',
               -80: 'Stick down: run toward the camera, it stays put'}.get(y, 'Stick right: the camera lags behind')
    elif st['stop'] is None or t < 20: lab = 'Stick released'
    else:
        idle = (t - st['stop']) / 60
        if diff < 3: lab = 'Camera behind Dash'
        elif idle < 1.5: lab = f'Standing still {idle:.1f} s'
        else: lab = 'Camera eases round behind him'
    return x, y, '', lab, t >= 640


def take_stairs(e, t, pl):
    if t < 170: return 0, 80, '', 'Up the stairs: the camera stays level', False
    if t < 210: return 0, 0, '', 'Stick released', False
    return 0, -80, '', 'Down toward the camera: no steep tilt', t >= 340


def take_hang(e, t, pl):
    hang = e.r32(S['g_hang_state'])
    if hang and st['grab'] is None: st['grab'] = t
    g = st['grab']
    if g is None:
        return (80, 0, '', 'Run off the edge (no jump)', False) if t >= 20 else (0, 0, '', '', False)
    h = t - g
    if h < 50: return 0, 0, '', 'Dash catches the ledge', False
    if h < 110: return 0, 0, 'B' if (h - 50) % 16 < 5 else '', 'Fire (B): no shooting while hanging', False
    if h < 125: return 0, 80, '', 'Stick up: pull up', False
    return 0, 0, '', 'Pull up, knee on the rim, stand up', h >= 230


def take_atst(e, t, pl):
    lk = e.r32(S['g_lock'])
    if t < 30: return 0, 0, '', 'AT-ST boss, Echo Base', False
    z = 'Z' if lk or (t - 30) % 60 >= 6 else ''              # re-press Z until it locks
    if t < 60: return 0, 0, z, 'Z: lock on the AT-ST', False
    fire = 'B' if (t // 8) % 2 == 0 else ''
    if t < 400: return 60, 0, z + fire, 'Stick right: circle the walker, shots go to the cockpit', False
    if t < 740: return -60, 0, z + fire, 'Stick left: circle back the other way', False
    if t < 800: return 0, 0, z + fire, 'Z held: Dash keeps facing the target', False
    return 0, 0, '', 'Z released: lock off', t >= 860


TAKES = dict(move=take_move, stairs=take_stairs, hang=take_hang, atst=take_atst)


def finish(e):
    json.dump(log, open(OUT, 'w'))
    if AUD:
        AUD.audio_dump_stop()
        w = wave.open(OUT[:-5] + '.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2)
        w.setframerate(AUD.audio_dump_freq()); w.writeframes(open(RAW, 'rb').read()); w.close()
        os.remove(RAW)
    print('frames', len(log), flush=True); e.stop()


def script(e, n):
    if n == 1: e.unlimit(False)
    if n == 60: e.load_state(os.path.join(paths.STATES, STATE))
    if n == 62: inject(e)
    if n < 66: return
    k = n - 66
    pl = e.r32(S['g_player'])
    e.wf(pl + 0xB4, 100.0)                       # keep Dash alive
    if k < SETTLE: e.pad(0); return
    t = k - SETTLE
    if t == 0 and AUD: AUD.audio_dump_start(RAW.encode())
    x, y, b, lab, done = TAKES[TAKE](e, t, pl)
    btn = 0
    for c in b: btn |= BTN[c]
    e.pad(btn, x, y)
    if t % 2 == 0:
        e.shot()
        log.append(dict(t=t, x=x, y=y, b=b, label=lab, hang=e.r32(S['g_hang_state']), lock=bool(e.r32(S['g_lock'])),
                        aud=AUD.audio_dump_frames() if AUD else 0))
    if done: finish(e)


e.run(script)
