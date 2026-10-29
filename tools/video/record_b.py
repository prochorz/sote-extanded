#!/usr/bin/env python3
"""Record the takes of the long YouTube showcase (step B), with game audio, in segments.

    cd harness
    for s in 0 1 2 3; do        # until the output says TAKE_DONE
      RES=1440x1080 SHOTS=vid_b_<take>$s M64CPU=0 AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib PAYLOAD_BUILD=<build> \\
          python3 ../tools/video/record_b.py <build>/sote-patch.z64 <take> $s
    done
    MODE=orig|patch (side-by-side takes sbs_*: orig = inject(e, payload=False), the unpatched game).
    PROBE=1: fast, no audio, a shot every 30 VIs into SHOTS, a status line every 30 VIs.

mupen keeps at most 1000 screenshots per directory per process, so a take is recorded in segments of
SEG_SHOTS shots: segment 0 loads the take's savestate and injects, later ones load the state the previous
segment saved (run/video/b_<take>_<s>.st) and continue its timeline (context in b_<take>_ctx.json).
Per segment: run/video/b_<take>_<s>.json (one entry per saved frame: {t, x, y, b, label, aud, seg, ...})
and b_<take>_<s>.wav. A take's timeline is a list of steps (frames, label, held, stick x, y, tapped):
held / tapped letters: A B Z L R, S START, U D < > D-pad, c C-left; 'l' = Z held once locked, else
re-pressed every 60 VIs; 'f' = B pulsed (fire). A label starting with '!' is not recorded (loading).
No Debug Display (the user, for this video).
"""
import ctypes as C, json, math, os, struct, sys, wave
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'harness')
sys.path.insert(0, HARNESS)
import paths
import m64
from m64 import Emu, BTN, HERE
from inject import inject, syms
from game import find_player, pool_objects, LEVEL_ID

m64.GLN_INT.update(AspectRatio=1, MultiSampling=0, FXAA=0, EnableN64DepthCompare=0, bilinearMode=1,
                   EnableFBEmulation=1, txFilterMode=0, txEnhancementMode=0, EnableHWLighting=0,
                   UseNativeResolutionFactor=0, ThreadedVideo=0, ShowFPS=0, ShowVIS=0, ShowPercent=0)
S = syms()
ROM, TAKE, SEGI = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0
MODE = os.environ.get('MODE', 'patch')
PROBE = bool(os.environ.get('PROBE'))
SEG_SHOTS = 990
VID = os.path.join(paths.RUN, 'video'); os.makedirs(VID, exist_ok=True)
NAME = f'b_{TAKE}' + (f'_{MODE}' if TAKE.startswith('sbs_') else '') + ('_probe' if PROBE else '')
BASE = os.path.join(VID, NAME)
KEY = dict(A='A', B='B', Z='Z', L='L', R='R', S='START', U='U_D', D='D_D', c='CL')
KEY['<'], KEY['>'] = 'L_D', 'R_D'
e = Emu(ROM, video=m64.GLN)
AUD = None
if os.environ.get('AUDIOPLUGIN') and not PROBE:
    AUD = C.CDLL(os.environ['AUDIOPLUGIN']); AUD.audio_dump_frames.restype = C.c_long

TROP, BOSS = 0x54726F70, 0x426F7373
FLASH_SITES = (0x8002A3F8, 0x8002AF94, 0x8003098C, 0x80030A6C, 0x8007052C, 0x800708E0, 0x80071544, 0x8007B2DC,
               0x8007BB34, 0x800A7F18, 0x800A8680, 0x800ADD64, 0x800AE04C)   # swc1 ..., 0x0DE8(lui 0x800E)
PAUSED = 0x800DD2BC
# Video only (RAM, this run; the patch and the ROM are untouched): Dash takes no knock-back and the screen no hit flash.
# The damage function 0x800732D4 stores the flash strength (float 0x800E0DF0, colour s16 x3 0x8018DCF8: 255, 128, 0
# orange) in the delay slot at 0x80073450: swc1 $f18 -> swc1 $f4 (0.0). Humn's message handler pushes him at
# 0x8007AF30 ('push') and 0x8007AF80 ('shot' with flag 0x400, an explosion): jal 0x800693F8 -> nop.
NOHIT = {0x80073450: 0xE4440000, 0x8007AF30: 0, 0x8007AF80: 0}


# ---------------------------------------------------------------- timeline helpers
def st_(n, label=None, hold='', x=0, y=0, tap=''):
    return [(n, label, hold, x, y, tap)]


def taps(keys, gap, label=None):
    return [(gap, label, '', 0, 0, k) for k in keys]


def open_cheats(label='START, then Cheats (the last entry of the pause list)'):
    return st_(40, label, tap='S') + taps('DDD', 10) + st_(34, None, tap='A')


def resume():
    return st_(24, None, tap='B') + taps('UUU', 8) + st_(30, None, tap='A')


def dpos(e, a, off=0x50):
    return [e.rf(a + off + 4 * i) for i in range(3)]


def put(e, pl, p):
    for i, v in enumerate(p):
        e.wf(pl + 0x50 + 4 * i, v); e.wf(pl + 0x08 + 4 * i, v); e.wf(pl + 0x98 + 4 * i, 0.0)


# ---------------------------------------------------------------- takes
TAKES = {}


def take(name, state, steps, settle=60, health=0xB4, hook=None, pre=None, payload=True, noflash=False, nohit=False):
    TAKES[name] = dict(state=state, steps=steps, settle=settle, health=health, hook=hook, pre=pre, payload=payload, noflash=noflash,
                       nohit=nohit)


def boss_of(e, ctx):
    if not ctx.get('boss'):
        ctx['boss'] = next((o for _, o in pool_objects(e) if e.r32(o) == BOSS), 0)
    return ctx['boss']


IGD = float(os.environ.get('IGD', 20))           # distance kept from IG-88 while locked (his close attacks flash the screen)
IGDRAIN = float(os.environ.get('IGDRAIN', 0.09))  # extra health off him per frame while locked and firing (real hits too slow)


def ig88_hook(e, t, ctx, cmd):
    b = boss_of(e, ctx); pl = e.r32(S['g_player'])
    if not b or not pl: return
    hp = e.rf(b + 0x5C4)
    bx, by, _ = dpos(e, b); px, py, _ = dpos(e, pl)
    d = math.hypot(bx - px, by - py)
    cmd['hp'] = round(hp, 1); cmd['d'] = round(d, 1); cmd['bpos'] = [round(bx, 1), round(by, 1)]
    locked = e.r32(S['g_lock']) == b
    hist = ctx.setdefault('hist', [])                # stuck against a wall (he hits a still Dash): strafe the other way
    hist.append((px, py)); del hist[:-24]
    if cmd['x'] and len(hist) == 24 and math.hypot(px - hist[0][0], py - hist[0][1]) < 1.0 and t - ctx.get('flip_t', -99) > 40:
        ctx['flip'] = not ctx.get('flip'); ctx['flip_t'] = t
    if ctx.get('flip'): cmd['x'] = -cmd['x']
    if cmd['x'] and locked:                        # the camera looks at him: stick y keeps the distance
        cmd['y'] = int(max(-70, min(70, (d - IGD) * 8)))
    elif cmd['x'] and t >= 100 and not cmd['label'].startswith('!'):   # lock lost (he leapt away): run toward him till Z takes him again
        a = math.radians(math.degrees(math.atan2(by - py, bx - px)) - e.rf(S['g_cam_facing']))
        cmd['x'], cmd['y'] = int(-math.sin(a) * 70), int(math.cos(a) * 70)
    if locked and t >= 120 and hp > 1.5: e.wf(b + 0x5C4, max(1.2, hp - IGDRAIN))
    if hp < 1 and 'dead' not in ctx: ctx['dead'] = t
    if 'dead' in ctx: cmd['label'] = 'IG-88 down'
    # Record only the fight: not while he has leapt away out of the lock, not under a stream of his hits (each hit
    # tints the screen orange; see the cut list in the log: 'cut' marks the first frame after a gap).
    if ctx.get('dmg_t') is None: ctx['dmg_t'] = -99
    hits = ctx.setdefault('hits', [])
    hits.append(1 if rt.get('dnow', 0) > 0.5 else 0); del hits[:-30]
    if t >= 40 and 'dead' not in ctx:
        want = (locked or d < 28) and sum(hits) < 2
        rec = ctx.get('rec', True)
        if want != rec and (rec or t - ctx.get('rec_t', -99) >= 40):
            ctx['rec'] = want; ctx['rec_t'] = t
        elif want == rec == False: ctx['rec_t'] = t     # (re-opens 40 frames after the last bad one)
        if not ctx.get('rec', True): cmd['label'] = '!' + cmd['label']
    return 'dead' in ctx and t - ctx['dead'] > int(os.environ.get('DEAD_TAIL', 20))


IGX = int(os.environ.get('IGX', -60))
IGSTEPS = st_(int(os.environ.get('IGPRE', 200)), '!pre', '', IGX) + st_(40, 'IG-88, Ord Mantell', '', IGX) + st_(60, 'Z: lock on IG-88', 'l', IGX)
for i in range(15):
    IGSTEPS += st_(int(os.environ.get('IGSEG', 540)), ('Z lock: Dash circle-strafes round IG-88, every shot flies into the lock',
                                                     'The other way round, the lock holds')[i % 2], 'lf', IGX if i % 2 == 0 else -IGX)
take('ig88', 'om_ig88.st', IGSTEPS, settle=30, hook=ig88_hook, noflash=True)

# ig88c: the same fight (~30 s, IGC_DRAIN off him a frame while locked), recorded without skips, then everything after
# his death without a cut to Cut 05's first picture. Stretches without the lock (he leapt away: the camera may face a
# wall) carry drop=1 (ctx 'drops': [t0, t1] ranges) for the composer to cut; loads carry the label 'loading'.
# NOHIT (no hit flash, no knock-back on Dash) is on. After the death nothing is pressed unless the game waits for a
# button: the Level Complete screen (its "Update Data? YES" waits): A from WAIT_A VIs after the death (the screen
# written in full and readable ~3 s), again every WAIT_GAP VIs while still on IG-88's sub-level.
IGC_DRAIN = float(os.environ.get('IGC_DRAIN', 0.3))
WAIT_A, WAIT_GAP = int(os.environ.get('WAIT_A', 1500)), int(os.environ.get('WAIT_GAP', 180))
C05_FRAME = S.get('g_c05_frame')


def ig88c_hook(e, t, ctx, cmd):
    lv = e.r16(LEVEL_ID); cmd['lv'] = lv
    if 'dead' not in ctx:
        b = boss_of(e, ctx); pl = e.r32(S['g_player'])
        if not b or not pl: return
        hp = e.rf(b + 0x5C4)
        bx, by, _ = dpos(e, b); px, py, _ = dpos(e, pl)
        d = math.hypot(bx - px, by - py)
        cmd['hp'] = round(hp, 1); cmd['d'] = round(d, 1)
        locked = e.r32(S['g_lock']) == b
        hist = ctx.setdefault('hist', [])
        hist.append((px, py)); del hist[:-24]
        if cmd['x'] and len(hist) == 24 and math.hypot(px - hist[0][0], py - hist[0][1]) < 1.0 and t - ctx.get('flip_t', -99) > 40:
            ctx['flip'] = not ctx.get('flip'); ctx['flip_t'] = t
        if ctx.get('flip'): cmd['x'] = -cmd['x']
        if cmd['x'] and locked:
            cmd['y'] = int(max(-70, min(70, (d - IGD) * 8)))
        elif cmd['x'] and t >= 100 and not cmd['label'].startswith('!'):
            a = math.radians(math.degrees(math.atan2(by - py, bx - px)) - e.rf(S['g_cam_facing']))
            cmd['x'], cmd['y'] = int(-math.sin(a) * 70), int(math.cos(a) * 70)
        if locked and t >= 120 and hp > 1.5: e.wf(b + 0x5C4, max(1.2, hp - IGC_DRAIN))
        if hp < 1 or e.r16(b + 6) & 0x20: ctx['dead'] = t
        elif t >= 300 and not cmd['label'].startswith('!'):
            rec = ctx.get('rec', True)                    # drop: closes at once, re-opens 40 VIs after the last unlocked one
            if locked != rec and (rec or t - ctx.get('rec_t', -99) >= 40):
                ctx['rec'] = locked; ctx['rec_t'] = t
                if not locked: ctx.setdefault('drops', []).append([t, None])
                else: ctx['drops'][-1][1] = t
            elif not locked and not rec: ctx['rec_t'] = t
            if not ctx.get('rec', True): cmd['drop'] = 1
    if 'dead' in ctx:
        if ctx.get('drops') and ctx['drops'][-1][1] is None: ctx['drops'][-1][1] = t
        cmd['x'] = cmd['y'] = 0; cmd['nobtn'] = 1
        c05 = e.r32(C05_FRAME) if C05_FRAME else 0
        cmd['c05'] = c05
        if lv == 0xA: cmd['label'] = 'IG-88 down'
        elif lv == 11 and c05: cmd['label'] = 'Cut 05'
        else: cmd['label'] = 'loading' if lv != 11 else 'Cut 05 loading'
        if lv == 0xA and t - ctx['dead'] >= WAIT_A and (t - ctx['dead'] - WAIT_A) % WAIT_GAP < 6: cmd['tapA'] = 1
        if c05:
            ctx.setdefault('c05_t', t)
            return t - ctx['c05_t'] >= int(os.environ.get('C05_TAIL', 60))
        return t - ctx['dead'] > int(os.environ.get('AFTER_MAX', 6000))


take('ig88c', 'om_ig88.st', IGSTEPS + st_(9000, None), settle=30, hook=ig88c_hook, nohit=True)


GLAD = 0x8019F4C4


def glad_pre(e, k, ctx, pl):
    if k < 30: put(e, pl, [float(v) for v in os.environ.get('GLPOS', '-18,12,124').split(',')])
    if k == 40: e.w32(GLAD + 0x584, 3)


def hit_gate(t, ctx, cmd, ok):
    """Record only while ok and Dash takes no stream of hits (each tints the screen orange): closes at once, opens
    40 frames after the last bad frame; the first saved frame after a gap carries cut=1."""
    hits = ctx.setdefault('hits', [])
    hits.append(1 if rt.get('dnow', 0) > float(os.environ.get('HIT_MIN', 2.5)) else 0); del hits[:-30]
    want = ok and sum(hits) < 2
    rec = ctx.get('rec', True)
    if want != rec and (rec or t - ctx.get('rec_t', -99) >= 40):
        ctx['rec'] = want; ctx['rec_t'] = t
    elif want == rec == False: ctx['rec_t'] = t
    if not ctx.get('rec', True): cmd['label'] = '!' + cmd['label']


def glad_hook(e, t, ctx, cmd):
    if os.environ.get('GLGOD', '0') == '1': e.w32(0x800E1B2C, 1)   # the game's Invincibility: troopers' shots do nothing
    cmd['glock'] = int(e.r32(S['g_lock']) == GLAD)
    cmd['hp'] = round(e.rf(GLAD + 0x5C4), 1)
    pl = e.r32(S['g_player'])
    gx, gy, gz = dpos(e, GLAD); px, py, pz = dpos(e, pl)
    cmd['view'] = e.r16(0x800E0EEC)
    if os.environ.get('GLAMB'):                    # the debug list's Amb Light (s16 r, g, b): a brighter palace
        v = int(os.environ['GLAMB'])
        e.w32(0x800E7AAC, (v << 16) | v); e.w32(0x800E7AB0, (v << 16) | (e.r32(0x800E7AB0) & 0xFFFF))
        e.w32(0x80192F38, 1)                       # (the level re-applies its own light every frame unless this is set)
    cmd['st'] = e.r32(GLAD + 0x584)
    if TAKE == 'glad_a':
        # Without knock-back (NOHIT) his bombs no longer blow Dash off the roof (z 123.4 -> the maze below, ~20 s after
        # the lock): the roof fight goes on. Guard: should Dash still drop, put him back where he last stood on the roof.
        if pz >= 123.0: ctx['roof'] = [px, py, pz]
        elif ctx.get('roof') and os.environ.get('GLGUARD', '1') == '1': put(e, pl, ctx['roof']); cmd['guard'] = 1
        elif t > 160 and pz < 122: return True   # off the roof: his second phase begins (glad_b)
    if TAKE == 'glad_b' and t >= 60 and os.environ.get('NOHIT', '1') != '1':
        hit_gate(t, ctx, cmd, bool(cmd['glock']))   # his shots hit Dash about once a second here (the orange flash)
    cmd['gd'] = round(math.dist((gx, gy, gz), (px, py, pz)), 1); cmd['gpos'] = [round(gx), round(gy), round(gz)]
    if t == 0: cmd['amb'] = [e.r16(0x800E7AAC), e.r16(0x800E7AAE), e.r16(0x800E7AB0), e.r16(0x800E7AB4)]


def glad_b_pre(e, k, ctx, pl):
    # Dash on the maze floor (z 105.9) ~12 units from him: he flies above, the lock tilts the camera up and shows him
    # against the sky (from the wall tops he flies below Dash's eye and the lock camera puts him right behind Dash).
    if k < 6: put(e, pl, [float(v) for v in os.environ.get('GLBPOS', '-20,20,107').split(',')])


GL1, GL2, GLX = int(os.environ.get('GL1', 135)), int(os.environ.get('GL2', 1100)), int(os.environ.get('GLX', 60))
GSTEPS = st_(100, 'The gladiator droid wakes up') + st_(60, 'Z: lock on his body', 'l')
for i in range(int(os.environ.get('GLN', 7))):
    GSTEPS += st_(GL1, 'Circle round him, B fires into the lock', 'lg', GLX if i % 2 == 0 else -GLX)
    GSTEPS += st_(120, 'Z held: Dash keeps facing him', 'lg')
take('glad_a', 'xiz_glad.st', GSTEPS, settle=200, pre=glad_pre, hook=glad_hook, nohit=True)
take('glad_b', 'xiz_glad2.st', st_(40, 'Second phase: he flies, troopers below')
     + st_(80, 'Z: lock on him, not the troopers', 'l') + st_(int(os.environ.get('GLB', 800)), 'B: the laser follows the lock', 'lf'),
     settle=20, hook=glad_hook, pre=glad_b_pre, nohit=True)
take('atst', 'echo_atst.st', st_(30, 'AT-ST, Echo Base') + st_(30, 'Z: lock on the AT-ST', 'l')
     + st_(600, 'Circle the walker: shots go to the cockpit', 'lf', 60)
     + st_(600, 'Circle back the other way', 'lf', -60) + st_(150, 'Z held: Dash keeps facing the target', 'lf')
     + st_(90, 'Z released: lock off'))

# --- side by side: the same input on the unpatched game (MODE=orig) and the patch
take('sbs_move', 'play.st', st_(10, 'Echo Base hangar') + st_(110, 'Stick up', '', 0, 80) + st_(15, 'Stick released')
     + st_(50, 'Stick down', '', 0, -80) + st_(205, 'Stick released') + st_(50, 'Stick right', '', 80, 0)
     + st_(200, 'Stick released'))
SQUARE = (st_(45, 'Stick right', '', 80, 0) + st_(45, 'Stick up', '', 0, 80) + st_(45, 'Stick left', '', -80, 0)
          + st_(45, 'Stick down', '', 0, -80) + st_(30, 'Stick released') + st_(70, 'Stick up-right', '', 57, 57)
          + st_(70, 'Stick down-left', '', -57, -57) + st_(60, 'Stick released'))
take('sbs_move2', 'play.st', st_(10, 'Echo Base hangar') + SQUARE + SQUARE)
take('sbs_stairs', 'echo_stairs.st', st_(170, 'Up the stairs', '', 0, 80) + st_(40, 'Stick released')
     + st_(130, 'Stick down: back down the stairs', '', 0, -80) + st_(60, 'Stick released'))
HANG_G = int(os.environ.get('HANG_G', 100))


def sbs_hang_hook(e, t, ctx, cmd):
    cmd['hang'] = e.r32(S['g_hang_state']) if MODE == 'patch' else 0


take('sbs_hang', 'echo_crevasse.st', st_(20, 'Crevasse, Echo Base') + st_(HANG_G - 20, 'Stick down: toward the camera, off the edge', '', 0, -80)
     + st_(50, 'Off the edge') + st_(60, 'B', 'f') + st_(15, 'Stick up', '', 0, 80) + st_(120, ''), settle=150,
     hook=sbs_hang_hook)


def train_hook(e, t, ctx, cmd):
    e.w32(0x800E1B2C, 0)                         # the states carry debug Invincibility: hide its icon


take('sbs_train', 'om.st', st_(20, 'Ord Mantell train') + st_(60, 'Stick down: toward the camera', '', 0, -80)
     + st_(20, 'Stick released') + st_(12, 'Stick left', '', -80, 0) + st_(40, 'Z', 'Z') + st_(60, 'Stick released'),
     settle=280, health=0xC0, hook=train_hook)
take('sbs_train2', 'om.st', st_(20, 'Ord Mantell train') + st_(12, 'Stick right', '', 80, 0) + st_(48, 'Stick released')
     + st_(40, 'Z', 'Z') + st_(40, 'Stick up', '', 0, 80) + st_(40, 'Stick released'),
     settle=280, health=0xC0, hook=train_hook)

# --- cheats (each: the menu choice, then the effect)
take('c_leebo', 'play.st', st_(30, 'Echo Base') + open_cheats() + taps('UUUU', 10, 'Cheats: Leebo Scanner')
     + st_(50, 'A: Leebo Scanner ON: the top-down scanner view', tap='A') + resume()
     + st_(100, 'Leebo Scanner: the top-down view', '', 0, 80) + st_(60, None, '', 80, 0)
     + st_(100, None, '', 0, -80) + st_(60, None, '', -80, 0) + st_(40, None), settle=30)


FT, FX, FY = int(os.environ.get('FT', 25)), int(os.environ.get('FX', 80)), int(os.environ.get('FY', 0))


def fuel_hook(e, t, ctx, cmd):
    pl = e.r32(S['g_player'])
    cmd['fuel'] = round(e.rf(pl + 0xBC), 1)


take('c_fuel', 'gall_tp5.st', st_(30, 'Gall, the canyon') + open_cheats() + taps('DDD', 10, 'Get all stuff (the jetpack)')
     + st_(30, None, tap='A') + taps('DD', 10, 'Jetpack Fuel') + st_(50, 'A: Jetpack Fuel ON', tap='A') + resume()
     + st_(FT, 'Turn toward the canyon', '', FX, FY) + st_(70, None)
     + st_(8, 'Jump, C-left: the jetpack', tap='A') + st_(6, None, tap='c') + st_(150, 'Endless fuel: the fuel number turns blue', 'A')
     + st_(240, None, 'A', 0, 40) + st_(240, None, 'A', 40, 0) + st_(60, None), settle=30, hook=fuel_hook)
SHIPS = ('Outrider', 'X-Wing', 'TIE Fighter')


def ship_hook(e, t, ctx, cmd):
    cmd['ship'] = e.r16(0x800E1B20)


take('c_ship', 'sky.st', st_(60, 'Skyhook: the Outrider') + open_cheats() + taps('UUUUU', 10, 'Cheats: Ship')
     + st_(50, 'R: X-Wing', tap='R') + resume() + st_(80, 'Skyhook in an X-Wing') + st_(80, None, '', 40, 0) + st_(80, None, '', 0, 40)
     + open_cheats() + st_(50, 'R: TIE Fighter', tap='R') + resume() + st_(80, 'Skyhook in a TIE Fighter') + st_(80, None, '', -40, 0) + st_(80, None, '', 0, -40),
     settle=30, health=None, hook=ship_hook)
take('c_creature', 'echo_cave.st', st_(30, 'Echo Base caves') + open_cheats() + taps('UUU', 10, 'Cheats: Creature Cam')
     + st_(50, 'R: Wampa', tap='R') + resume() + st_(60, 'The camera follows a wampa')
     + st_(120, 'The stick walks it', '', 0, 60) + st_(90, None, '', 60, 0) + st_(60, 'B: it attacks', 'B')
     + st_(30, None) + open_cheats() + st_(20, 'L: Dash', tap='L') + st_(40, 'L: Trooper', tap='L') + resume()
     + st_(60, 'The camera follows a trooper') + st_(120, 'The stick walks him', '', 0, 60)
     + st_(60, None, '', 60, 0) + st_(60, 'B: he fires', 'B') + st_(30, None), settle=30)
WAVE_ALIVE, ATST_REC = 0x800E1818, 0x80112DD8


def atst_pre(e, k, ctx, pl):
    if k == 2: e.w32(WAVE_ALIVE, 0)


def atst_hook(e, t, ctx, cmd):
    a0 = e.r32(ATST_REC + 0x10)
    cmd['awake'] = e.r32(a0 + 0x1C4); cmd['trak_on_atst'] = int(e.r32(e.r32(0x80112F20) + 0x8C) == a0)
    cmd['apos'] = [round(v, 1) for v in dpos(e, a0, 8)]
    if cmd['label'] == '!wait':
        if cmd['awake']: ctx['woke'] = ctx.get('woke', 0) + 1
        if ctx.get('woke', 0) < 10: cmd['freeze'] = True


ATST_WAIT = int(os.environ.get('ATST_WAIT', 150))
take('c_atst', 'lvl0.st', st_(20, 'Battle of Hoth') + open_cheats() + taps('UUU', 10, 'Cheats: Creature Cam')
     + st_(50, 'A: AT-ST', tap='A') + resume() + st_(60, 'Back in the speeder until the AT-STs come') + st_(1, '!wait')
     + st_(ATST_WAIT, 'The camera rides the first AT-ST of the wave') + st_(800, '!opening') + st_(300, 'The stick walks it', '', 0, 72)
     + st_(200, None, '', 60, 0) + st_(150, 'B fires', 'B') + st_(200, None, '', 0, 72), settle=3, health=None, pre=atst_pre, hook=atst_hook)


def friendly_pre(e, k, ctx, pl):
    if k == 0:
        ws = [o for _, o in pool_objects(e) if e.r32(o) == TROP and e.r32(o + 0x74) & 0xF == 2]
        w = ws[0]; ctx['w'] = w
        wx, wy, wz = dpos(e, w)
        if not os.environ.get('FKEEP', '0') == '1': put(e, pl, (wx - 8, wy, wz))
        e.wf(pl + 0x8C, float(os.environ.get('FYAW', 90)))


def friendly_hook(e, t, ctx, cmd):
    w = ctx['w']; cmd['wstate'] = e.r32(w + 0x78)


take('c_friendly', 'echo_cave.st', open_cheats('Echo Base caves, a wampa ahead') + taps('UU', 10, 'Cheats: Friendly Wampas')
     + st_(50, 'A: Friendly Wampas ON', tap='A') + resume() + st_(300, 'The wampa comes up to Dash and calms down')
     + st_(30, 'Dash steps away: it lets him go', '', 0, -80) + st_(90, None),
     settle=4, pre=friendly_pre, hook=friendly_hook)


def god_hook(e, t, ctx, cmd):
    pl = e.r32(S['g_player'])
    hp = e.rf(pl + 0xB4); cmd['hpd'] = round(hp, 1)
    if cmd['label'] and cmd['label'].startswith('Troopers'): cmd['label'] += f'  (health {hp:.0f})'
    elif cmd['label'] == '': cmd['label'] = f'Invincibility on: health stays at {hp:.0f}'


take('c_god', 'echo_stairs.st', st_(200, 'Troopers shoot from above: health drops') + open_cheats(None) + taps('DDDD', 10)
     + st_(40, 'A: Invincibility ON', tap='A') + resume() + st_(420, ''), health=None, hook=god_hook)


def level_hook(e, t, ctx, cmd):
    if cmd['label'] == '!load':
        lv = e.r16(LEVEL_ID)
        if lv == 32 and e.r32(PAUSED) == 0:
            ctx['in32'] = ctx.get('in32', 0) + 1
        if ctx.get('in32', 0) < int(os.environ.get('LEVEL_LAG', 30)): cmd['freeze'] = True
    if cmd['label'] == 'The Gall Run' and t % 45 < 4: cmd['tapA'] = 1


take('c_level', 'play.st', st_(30, 'Echo Base') + open_cheats() + taps('D' * 11, 8, 'Cheats: Go to level')
     + st_(30, 'Go to level: the chosen sub-level\'s name shows below')
     + taps('LLLLL', 24, 'L / R browse the sub-levels') + st_(50, '32: the Gall Run bonus mission')
     + st_(20, 'A loads it', tap='A') + st_(1, '!load') + st_(600, 'The Gall Run'), settle=30, health=None, hook=level_hook)


# --- finale: Gall on foot, ledge hangs on the canyon rims
def hang_loop(e, t, ctx, cmd):
    """Run toward DIR until the catch, hang, climb; after standing, run back toward the camera to catch again."""
    hang = e.r32(S['g_hang_state']); cmd['hang'] = hang
    ph = ctx.setdefault('ph', 'run'); n = ctx.setdefault('n', 0)
    d = ctx.get('dir', 0) if n == 0 else ctx.get('dir2', 180)
    if ph == 'run':
        cmd['x'], cmd['y'] = int(math.sin(math.radians(d)) * 80), int(math.cos(math.radians(d)) * 80)
        cmd['label'] = 'Walk off the edge: Dash catches it'
        if hang: ctx['ph'] = 'hang'; ctx['g'] = t
    elif ph == 'hang':
        h = t - ctx['g']
        if ctx.get('drop'):
            cmd['label'] = 'Hanging on the rim' if h < 90 else 'Stick down: let go, land on the floor below'
            if 90 <= h < 100: cmd['y'] = -80
        else:
            cmd['label'] = 'Hanging on the rim' if h < 90 else 'Stick up: climb'
            if 90 <= h < 102: cmd['y'] = 80
        if h > 120 and not hang: ctx['ph'] = 'up'; ctx['u'] = t
    elif ph == 'up':
        cmd['label'] = 'Landed' if ctx.get('drop') else 'Back on the rim'
        if t - ctx['u'] > 60: ctx['ph'] = 'run'; ctx['n'] = n + 1
    if ctx['n'] >= ctx.get('loops', 3): return True


def fin(state, dir_, dir2=180, loops=3, pos=None, drop=False):
    def pre(e, k, ctx, pl):
        ctx['dir'], ctx['dir2'], ctx['loops'], ctx['drop'] = dir_, dir2, loops, drop
        if pos and k < 6: put(e, pl, pos)
    return dict(state=state, pre=pre)


for nm, (stt, d, lp, pos, drop) in dict(f_tp5=('gall_tp5.st', 30, 8, None, False), f_tp6=('gall_tp6.st', 180, 8, None, False),
                                       f_stand=('gall_dash_stand.st', 0, 8, None, False),
                                       f_tp1=('gall_tp1.st', 0, 1, (18.2, 13.3, 294.5), True)).items():
    f = fin(stt, d, 180, lp, pos, drop)
    take(nm, stt, st_(4000, ''), settle=30 if pos else 6, pre=f['pre'], hook=hang_loop)


# --- ledge catch from a jump: Gall canyon (gall_tp5.st), run at JA degrees, A at JK frames into the run (the take's own
# choreography, a trooper by the rim helps: the jump lands short of the rock ahead, he catches its rim, hangs, then stick up climbs onto it)
JA, JK, JPRE = int(os.environ.get('JA', 215)), int(os.environ.get('JK', 35)), int(os.environ.get('JPRE', 20))
JH = int(os.environ.get('JH', 110))      # VIs hanging before stick up


def jump_hook(e, t, ctx, cmd):
    hang = e.r32(S['g_hang_state']); cmd['hang'] = hang
    pl = e.r32(S['g_player']); cmd['pos'] = [round(v, 1) for v in dpos(e, pl)]
    ph = ctx.setdefault('ph', 'pre')
    if ph == 'pre':
        cmd['label'] = 'Gall, the canyon' if t >= 14 else '!pre'    # (the state starts under an explosion's orange)
        if t >= JPRE: ctx['ph'] = 'run'; ctx['r'] = t
    if ctx['ph'] == 'run':
        k = t - ctx['r']
        cmd['x'], cmd['y'] = int(math.sin(math.radians(JA)) * 80), int(math.cos(math.radians(JA)) * 80)
        cmd['label'] = 'Run, A: jump'
        if JK <= k < JK + 5: cmd['tapA'] = 1
        if hang: ctx['ph'] = 'hang'; ctx['g'] = t
        elif k > 240: return True
    elif ph == 'hang' or ctx['ph'] == 'hang':
        h = t - ctx['g']
        cmd['label'] = 'Catches the edge' if h < JH else 'Climbs up'
        if JH <= h < JH + 12: cmd['y'] = 80
        if h > JH + 15 and not hang: ctx['ph'] = 'up'; ctx['u'] = t
    elif ph == 'up':
        cmd['label'] = 'On top'
        if t - ctx['u'] > int(os.environ.get('JTAIL', 50)): return True


take('jump', 'gall_tp5.st', st_(2000, ''), settle=6, hook=jump_hook, nohit=True)


# --- Gall's start (lvl4.st, sub-level 14): Dash spawns inside the Outrider (the lit corridor and the cabin are its
# inside), parked in the canyon on its legs over sand (z 200.9). Beside it stands a short orange post (top 212.9 at
# about (-295.5, 962)); the hull's deck by it is ~220, and a silver Challenge Point floats over the hull at
# (-314, 950, 229.1) (Dfob 0x69). Dash written onto the post jumps toward the ship (world 270, A JK2 VIs in): short of
# the deck, he catches its edge, hangs, climbs, walks to the point and jumps for it.
G2POS = [float(v) for v in os.environ.get('G2POS', '-295.5,962,214').split(',')]
G2DIR, JK2, G2H = float(os.environ.get('G2DIR', 270)), int(os.environ.get('JK2', 3)), int(os.environ.get('G2H', 80))
CP = (-314.0, 950.0, 229.1)


def jump2_pre(e, k, ctx, pl):
    if k < 6: put(e, pl, G2POS)


def steer(e, want):
    a = math.radians(want - e.rf(S['g_cam_facing']))
    return int(-math.sin(a) * 80), int(math.cos(a) * 80)


def jump2_hook(e, t, ctx, cmd):
    hang = e.r32(S['g_hang_state']); cmd['hang'] = hang
    pl = e.r32(S['g_player']); p = dpos(e, pl); cmd['pos'] = [round(v, 1) for v in p]
    ph = ctx.setdefault('ph', 'pre')
    if ph == 'pre':
        cmd['label'] = 'Gall: the start'
        if t >= int(os.environ.get('G2PRE', 30)): ctx['ph'] = ph = 'run'; ctx['r'] = t
    if ph == 'run':
        k = t - ctx['r']
        cmd['x'], cmd['y'] = steer(e, G2DIR)
        cmd['label'] = 'Jump to the Outrider'
        if JK2 <= k < JK2 + 4: cmd['tapA'] = 1
        if hang: ctx['ph'] = 'hang'; ctx['g'] = t
        elif k > 200: return True
    elif ph == 'hang':
        h = t - ctx['g']
        cmd['label'] = 'Catches the edge' if h < G2H else 'Climbs up'
        if G2H <= h < G2H + 12: cmd['y'] = 80
        if h > G2H + 15 and not hang: ctx['ph'] = 'walk'; ctx['u'] = t
    elif ph == 'walk':
        cmd['label'] = 'Silver Challenge Point'
        d = math.hypot(CP[0] - p[0], CP[1] - p[1])
        cmd['d'] = round(d, 1)
        go = t - ctx['u'] > 25 and ('j' not in ctx or t - ctx['j'] < int(os.environ.get('CPRUN', 8)))
        if go:
            cmd['x'], cmd['y'] = steer(e, math.degrees(math.atan2(CP[1] - p[1], CP[0] - p[0])))
            sp = float(os.environ.get('CPSP', 1.0)); cmd['x'] = int(cmd['x'] * sp); cmd['y'] = int(cmd['y'] * sp)
        if go and 'j' not in ctx and d <= float(os.environ.get('CPJ', 11.0)): ctx['j'] = t
        if 'j' in ctx and t - ctx['j'] < 4: cmd['tapA'] = 1
        if 'j' in ctx and t - ctx['j'] > int(os.environ.get('G2TAIL', 45)): return True
        if t - ctx['u'] > 400: return True


take('jump2', 'lvl4.st', st_(3000, ''), settle=60, pre=jump2_pre, hook=jump2_hook, nohit=True)


# --- zen_*: the Z lock-on against ordinary enemies (troopers, guards, droids): Z locks one, Dash circle-strafes it and
# fires till it drops, then Z again takes the next one. The hook drives Z, B and the stick itself (cmd['btns']).
# ZDRAIN health off the locked enemy a frame while firing (on top of the real hits: a kill in ~3-4 s); NOHIT on.
# ZPOS / ZDIR: Dash written there (world facing ZDIR via the stick) during the settle. ZONLY: tags that count as
# enemies (default every live target but crates). ZNAME: the word in the labels.
ZDRAIN = float(os.environ.get('ZDRAIN', 0.02))
ZONLY = os.environ.get('ZONLY', '').split(',') if os.environ.get('ZONLY') else None
ZRANGE = float(os.environ.get('ZRANGE', 110))
NOTGT = (0x426F7878, 0x416E696D, 0x48756D6E, 0x48756D54, BOSS)   # Boxx Anim Humn HumT Boss


def alive(e, o):
    return o and 0x80000000 <= o < 0x80800000 and e.r16(o + 6) & 2 and e.rf(o + 0x60) > 0


def zen_enemies(e, pl):
    px, py, pz = dpos(e, pl); out = []
    for _, o in pool_objects(e):
        tg = e.r32(o)
        if tg in NOTGT or not alive(e, o): continue
        if ZONLY and struct.pack('>I', tg).decode('latin1') not in ZONLY: continue
        x, y, z = dpos(e, o); d = math.hypot(x - px, y - py)
        if d < ZRANGE and abs(z - pz) < 20: out.append((d, o, x, y))
    return sorted(out)


def zen_pre(e, k, ctx, pl):
    if os.environ.get('ZPOS') and k < 25: put(e, pl, [float(v) for v in os.environ['ZPOS'].split(',')])


def zen_hook(e, t, ctx, cmd):
    if os.environ.get('ZAMB'):                      # the debug list's Amb Light, as glad_hook (GLAMB): a brighter level
        v = int(os.environ['ZAMB'])
        e.w32(0x800E7AAC, (v << 16) | v); e.w32(0x800E7AB0, (v << 16) | (e.r32(0x800E7AB0) & 0xFFFF)); e.w32(0x80192F38, 1)
    if t == 0: cmd['amb'] = [e.r16(0x800E7AAC), e.r16(0x800E7AAE), e.r16(0x800E7AB0)]
    pl = e.r32(S['g_player'])
    if not pl: return
    px, py, _ = dpos(e, pl)
    lk = e.r32(S['g_lock']); lk = lk if alive(e, lk) and lk not in ctx.get('gone', []) else 0   # (a dying one flickers)
    kills = ctx.get('kills', 0); ZKILLS = int(os.environ.get('ZKILLS', 3))
    ZD, ZX = float(os.environ.get('ZD', 26)), int(os.environ.get('ZX', 60))       # (read here: ZEN's defaults come after)
    ZPRE, ZTAIL, ZNAME = int(os.environ.get('ZPRE', 40)), int(os.environ.get('ZTAIL', 50)), os.environ.get('ZNAME', 'trooper')
    cur = ctx.get('cur', 0)
    if cur and not alive(e, cur):                              # the locked one dropped
        ctx.setdefault('gone', []).append(cur)
        kills = ctx['kills'] = kills + 1; ctx['cur'] = cur = 0; ctx['kt'] = t - ctx.get('t0', 0)
    en = zen_enemies(e, pl)
    cmd['n'] = len(en); cmd['kills'] = kills
    z = b = 0
    way = [[float(v) for v in w.split(',')] for w in os.environ.get('ZWAY', '').split(';') if w]
    if ctx.get('wi', 0) < len(way):                     # walk to the spot first (not recorded; the debug teleport is
        wx, wy = way[ctx.get('wi', 0)]                  # not used: a written position snaps back here)
        if math.hypot(wx - px, wy - py) < 6: ctx['wi'] = ctx.get('wi', 0) + 1; ctx['t0'] = t + 1
        a = math.radians(math.degrees(math.atan2(wy - py, wx - px)) - e.rf(S['g_cam_facing']))
        cmd['x'], cmd['y'] = int(-math.sin(a) * 80), int(math.cos(a) * 80)
        cmd['label'] = '!walk'; cmd['btns'] = (0, ''); return
    t -= ctx.get('t0', 0)
    if t < ZPRE:
        cmd['label'] = os.environ.get('ZINTRO', 'Echo Base: troopers ahead')
        if os.environ.get('ZDIR'):
            a = math.radians(float(os.environ['ZDIR']) - e.rf(S['g_cam_facing']))
            cmd['x'], cmd['y'] = int(-math.sin(a) * 30), int(math.cos(a) * 30)
    elif kills >= ZKILLS:
        cmd['label'] = 'Z released: lock off'
        if t - ctx['kt'] > ZTAIL: return True
    elif kills and t - ctx['kt'] < int(os.environ.get('ZGAP', 20)):   # Z let go after a kill, then pressed afresh
        cmd['label'] = f'{ZNAME.capitalize()} down. Z again: the next one'
    elif lk:
        if lk != cur:
            ctx['cur'] = cur = lk; ctx['lt'] = t; ctx['dir'] = -ctx.get('dir', 1)
            ctx['tag'] = struct.pack('>I', e.r32(lk)).decode('latin1')
        cmd['tgt'] = ctx['tag']
        x, y, _ = dpos(e, lk); d = math.hypot(x - px, y - py); cmd['d'] = round(d, 1)
        hp = e.rf(lk + 0x60); cmd['hp'] = round(hp, 2)
        hist = ctx.setdefault('hist', [])
        hist.append((px, py)); del hist[:-24]
        if len(hist) == 24 and math.hypot(px - hist[0][0], py - hist[0][1]) < 1.0 and t - ctx.get('flip_t', -99) > 40:
            ctx['dir'] = -ctx['dir']; ctx['flip_t'] = t
        lt = t - ctx['lt']
        cmd['x'] = ZX * ctx['dir'] if lt > 12 else 0
        cmd['y'] = int(max(-70, min(70, (d - ZD) * 8))) if lt > 12 else 0
        z = 1
        if lt > 15:
            b = t % int(os.environ.get('ZFIRE', 16)) < 8   # B pulses: ZFIRE VIs apart (longer: slower kills)
            if hp > 0.4: e.wf(lk + 0x60, max(0.4, hp - ZDRAIN))
        if kills == 0: cmd['label'] = f'Z: lock the nearest {ZNAME}' if lt < 45 else 'Circle-strafe, every shot flies into the lock'
        else: cmd['label'] = 'Next target: the lock moves on' if lt < 50 else 'Circle-strafe, every shot flies into the lock'
    else:
        since = t - ctx.get('kt', ZPRE)
        cmd['label'] = f'Z: lock the nearest {ZNAME}' if kills == 0 else f'{ZNAME.capitalize()} down. Z again: the next one'
        if en:
            d, o, x, y = en[0]
            a = math.radians(math.degrees(math.atan2(y - py, x - px)) - e.rf(S['g_cam_facing']))
            if d > 30 or abs(math.degrees(a)) > 40: cmd['x'], cmd['y'] = int(-math.sin(a) * 60), int(math.cos(a) * 60)
        zon, zper = (int(v) for v in os.environ.get('ZPULSE', '20,30').split(','))   # Z pressed till it takes one
        if since >= int(os.environ.get('ZGAP', 20)) and since % zper < zon: z = 1
    cmd['btns'] = (BTN['Z'] if z else 0) | (BTN['B'] if b else 0), ('Z' if z else '') + ('B' if b else '')


ZEN = {   # take: (state, env defaults: the values the recorded takes used)
    'zen_echo': ('play.st', dict(ZWAY='-338,47;-317,13;-294,-24;-263,-64;-243,-64;-214,-88', ZKILLS='5', ZFIRE='24',
                                 ZINTRO='Echo Base: troopers ahead')),        # the hangar's trooper groups (demo_route.py)
    'zen_xiz': ('lvl8.st', dict(ZKILLS='3', ZAMB='200', ZPULSE='8,20', ZD='18', ZNAME='guard',
                                ZINTRO="Xizor's palace: royal guards ahead")),
}
for _n, (_st, _env) in ZEN.items():
    take(_n, _st, st_(int(os.environ.get('ZLEN', 1500)), ''), settle=int(os.environ.get('ZSETTLE', 30)), pre=zen_pre,
         hook=zen_hook, nohit=True)
if TAKE in ZEN:
    for _k, _v in ZEN[TAKE][1].items(): os.environ.setdefault(_k, _v)


# ---------------------------------------------------------------- engine
T = TAKES[TAKE]
ctx = json.load(open(BASE + '_ctx.json')) if SEGI else {'t': 0}
STEPS = T['steps']
ENDT = sum(s[0] for s in STEPS)
log, rt = [], {'pending': None, 'files': 0, 'k0': None, 'fin': None, 'paused_aud': False}
RAW = f'{BASE}_{SEGI}.raw'


def step_at(t):
    a, lab = 0, None
    for s in STEPS:
        if s[1] is not None: lab = s[1]
        if t < a + s[0]: return s, t - a, lab
        a += s[0]
    return None, 0, lab


def player(e):
    if MODE == 'patch': return e.r32(S['g_player'])
    if not rt.get('pl') or e.frame % 60 == 0: rt['pl'] = find_player(e)
    return rt['pl']


def finish(e, done):
    if rt['pending'] is not None and len(os.listdir(e.shot_dir)) > rt['files']: log.append(rt['pending'])
    json.dump(log, open(f'{BASE}_{SEGI}.json', 'w'))
    if AUD:
        AUD.audio_dump_stop()
        w = wave.open(f'{BASE}_{SEGI}.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2)
        w.setframerate(AUD.audio_dump_freq()); w.writeframes(open(RAW, 'rb').read()); w.close(); os.remove(RAW)
    if not done:
        e.save_state(f'{BASE}_{SEGI}.st')
    json.dump(ctx, open(BASE + '_ctx.json', 'w'))
    print('frames', len(log), 't', ctx['t'], 'TAKE_DONE' if done else 'SEGMENT_END', flush=True)
    rt['stop_at'] = e.frame + (1 if done else 30)    # (a stop right after save_state lost the state)


def script(e, n):
    if rt.get('stop_at') is not None:
        if e.frame >= rt['stop_at']: e.stop()
        return
    if n == 1 and not PROBE: e.unlimit(False)
    if n == 60:
        e.load_state(os.path.join(paths.STATES, T['state']) if SEGI == 0 else f'{BASE}_{SEGI - 1}.st')
    if n == 62 and SEGI == 0: inject(e, payload=(MODE == 'patch' and T['payload']))
    if n < 66: return
    k = n - 66
    pl = player(e)
    if T.get('noflash') and os.environ.get('NOFLASH', '1') == '1':
        # Video only (RAM, this run): the hit flash. Its strength is float 0x800E0DE8 (~0.7 on a hit, decaying); the
        # game's damage code stores it at these sites: a NOP there leaves it 0 (damage itself is unchanged).
        pass
    if T.get('nohit') and os.environ.get('NOHIT', '1') == '1':
        for a, v in NOHIT.items():
            if e.r32(a) != v: e.w32(a, v)
    if T['health'] is not None and pl:
        rt['dnow'] = max(0.0, 100.0 - e.rf(pl + T['health'])); rt['dmg'] = rt.get('dmg', 0) + rt['dnow']
        e.wf(pl + T['health'], 100.0)
    if SEGI == 0 and k < T['settle']:
        if T['pre']: T['pre'](e, k, ctx, pl)
        e.pad(0); return
    if rt['fin'] is not None: finish(e, rt['fin']); return
    t = ctx['t']
    s, j, lab = step_at(t)
    if s is None: rt['fin'] = True; return
    n_, _, hold, x, y, tap = s
    cmd = dict(label=lab, x=x, y=y)
    lk = e.r32(S['g_lock']) if MODE == 'patch' else 0
    btn, shown = 0, ''
    for c in hold:
        if c == 'l':
            if lk or (t % 60) >= 6: btn |= BTN['Z']; shown += 'Z'
        elif c == 'f':
            if (t // 8) % 2 == 0: btn |= BTN['B']; shown += 'B'
        elif c == 'g':                              # sparse fire: a longer fight
            if t % 30 < 4: btn |= BTN['B']; shown += 'B'
        else: btn |= BTN[KEY[c]]; shown += c
    if tap and j < 4:
        btn |= BTN[KEY[tap]]; shown += tap
    done = T['hook'](e, t, ctx, cmd) if T['hook'] else False
    if cmd.pop('nobtn', 0): btn, shown = 0, ''
    if 'btns' in cmd: btn, shown = cmd.pop('btns')
    if cmd.pop('tapA', 0): btn |= BTN['A']; shown += 'A'
    if cmd.pop('tapL', 0): btn |= BTN['L']
    e.pad(btn, cmd['x'], cmd['y'])
    rec = not (cmd['label'] or '').startswith('!')
    if rt['k0'] is None:
        rt['k0'] = k
        if AUD: AUD.audio_dump_start(RAW.encode())
    if AUD and rec == rt['paused_aud']:
        AUD.audio_dump_pause(0 if rec else 1); rt['paused_aud'] = not rec
    kk = k - rt['k0']
    if not rec and log: rt['gap'] = True
    if rec and kk % (30 if PROBE else 2) == 0:
        nf = len(os.listdir(e.shot_dir))
        if rt['pending'] is not None and nf > rt['files']: log.append(rt['pending'])
        rt['files'] = nf
        e.shot()
        cmd['dmg'] = round(rt.pop('dmg', 0), 1)       # health the game took since the last saved frame (a hit flashes the screen)
        if rt.get('gap'): cmd['cut'] = 1; rt['gap'] = False
        ent = dict(t=t, x=cmd['x'], y=cmd['y'], b=shown, label=cmd['label'], seg=SEGI,
                   lock=1 if lk else 0, aud=AUD.audio_dump_frames() if AUD else 0)
        for key in cmd:
            if key not in ent and key != 'freeze': ent[key] = cmd[key]
        rt['pending'] = ent
        if PROBE:
            p = [round(v, 1) for v in dpos(e, pl)] if pl else None
            print(f"t {t} lab {cmd['label']!r} pos {p} lock {lk:x} lv {e.r16(LEVEL_ID)} paused {e.r32(PAUSED)} "
                  + ' '.join(f'{a}={cmd[a]}' for a in cmd if a not in ('label', 'x', 'y')), flush=True)
    if not cmd.get('freeze'): ctx['t'] = t + 1
    if done or ctx['t'] >= ENDT: rt['fin'] = True
    elif not PROBE and len(log) >= SEG_SHOTS: rt['fin'] = False


e.run(script)
