"""Savestate recipes: one emulator session each (the core starts once a process), shared by mkstate.py, tpstate.py
and bootstrap.py.

    M64CPU=2 python3 states_make.py boot <rom> <carousel> <out.st> [onward] [frame=N]
    M64CPU=2 python3 states_make.py teleport <rom> <from.st> <next levels> <target x> <out.st>
    M64CPU=2 python3 states_make.py next <rom> <from.st> <next levels> <out.st>
    M64CPU=2 python3 states_make.py wait <rom> <from.st> <seconds> <out.st>
    M64CPU=2 python3 states_make.py level <rom> <from.st> <sub-level> <frames> <out.st>
    M64CPU=2 python3 states_make.py place <rom> <from.st> <x> <y> <z> <yaw> <out.st> [wait=VIs]
    M64CPU=2 python3 states_make.py menu <rom> <from.st> <item> <out.st> [wait=VIs] [frame=N]
    M64CPU=2 python3 states_make.py ride <rom> <from.st> <seconds> <out.st> [frame=N]
    M64CPU=2 python3 states_make.py glad2 <rom> <xiz_glad.st> <out.st> [wait=VIs]
    M64CPU=2 python3 states_make.py dianoga <rom> <pool.st> <out.st> [wait=VIs]

<from.st> is a path, or a name in local/states. Each recipe prints the level id and the player's place it saved.
`frame=N` (boot, teleport, next, wait, place, menu, ride): saved when the game's frame counter (u32 0x8018E9B0, counted from the
sub-level's start) reaches N, instead of the recipe's fixed wait: the frame of a state to match.
"""
import os, sys
import paths
from m64 import Emu, BTN
from debugmenu import set_debug, set_cursor, TELEPORT, NEXT_LEVEL
from game import boot_events, play_events, unlock_levels, find_player, set_health, LEVEL_ID, DLG_GATE, HUMN_YAW


GAME_FRAME = 0x8018E9B0
GET_ALL, INVINCIBLE = 0, 1                             # debug-menu items (debugmenu.py)


def _src(path):
    return path if os.path.isabs(path) or os.path.exists(path) else os.path.join(paths.STATES, path)


def _report(e, out):
    p = find_player(e)
    where = '(%.1f, %.1f, %.1f)' % tuple(e.rf(p + 0x50 + 4 * i) for i in range(3)) if p else '(no player)'
    print('level id', hex(e.r16(LEVEL_ID)), 'player', where, 'saved', out, flush=True)


def boot(rom, level, out, onward=False, frame=None):
    """Power-on (fresh EEPROM) to carousel level `level`; messages at the level's start dismissed with START;
    saved 600 frames after the level has loaded (the player controllable).
    onward: the carousel's first sub-level is an opening one (Mos Eisley, Ord Mantell, Skyhook, Gall): START every
    2 s, as the game's own way on, until the level id changes by itself (at most 180 s; not changed by then, one
    debug Next Level), then saved 600 frames after the change.
    frame: saved instead when the game's frame counter (u32 0x8018E9B0, counted from the sub-level's start) reaches
    it (the frame of a state to match)."""
    ev, t0 = boot_events(level)
    e = Emu(rom)
    st = {'lvl': None, 'at': None if onward else 0, 'next': None}

    def script(e, n):
        if n == 1: e.unlimit()
        if 1600 < n < 2900 and n % 30 == 0: unlock_levels(e)
        if n < t0:
            play_events(e, ev, n); return
        k = n - t0
        lvl = e.r16(LEVEL_ID)
        if st['at'] is None:
            if st['lvl'] is None: st['lvl'] = lvl; print('opening sub-level', lvl, flush=True)
            if lvl != st['lvl']:
                st['at'] = k; set_debug(e, False); set_cursor(e, 0)
                print('level id ->', lvl, 'after', k, 'frames', '(debug Next Level)' if st['next'] else '', flush=True)
            elif k < 180 * 60:
                e.pad(BTN['START'] if k % 120 < 6 else 0); return
            else:                                      # the game's way did not go on: one debug Next Level
                if st['next'] is None: st['next'] = k
                ph = k - st['next']
                set_debug(e, ph < 100)
                if ph < 56: set_cursor(e, NEXT_LEVEL)
                e.pad(BTN['START'] if ph < 5 else 0)
                if ph > 2000: print('no level change'); e.stop()
                return
        k -= st['at']
        e.pad(BTN['START'] if e.rf(DLG_GATE) > 0 and k % 60 < 6 else 0)
        if st.get('saved') is None and (k > 10 and e.r32(GAME_FRAME) >= frame if frame else k == 600):
            st['saved'] = k; e.save_state(out); e.shot(); _report(e, out)
        if st.get('saved') is not None and k == st['saved'] + 10: e.stop()
    e.run(script)


def teleport(rom, start, nexts, tx, out, per=200, frame=None):
    """From `start`: debug Next Level `nexts` times, then Teleport until the player's x is within 2 units of `tx`;
    ~3 s more (cutscenes, messages; his health kept full: troopers stand near teleport points), saved with the debug
    flag off. With tx None: only the Next Levels."""
    e = Emu(rom)
    st = {'nexts': 0, 'done': None, 'dash': 0}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        if st['done'] is None and tx is None and st['nexts'] >= nexts: st['done'] = k; st['dash'] = find_player(e)
        if st['done'] is not None:
            set_debug(e, False); set_cursor(e, 0)
            if st['dash']: set_health(e, st['dash'])
            e.pad(BTN['START'] if e.rf(DLG_GATE) > 0 and (k - st['done']) % 60 < 6 else 0)
            d = k - st['done']
            if st.get('saved') is None and (d > 10 and e.r32(GAME_FRAME) >= frame if frame else d == 200):
                st['saved'] = d; e.save_state(out); e.shot(); _report(e, out)
            if st.get('saved') is not None and d == st['saved'] + 5: e.stop()
            return
        i, ph = k // per, k % per
        item = NEXT_LEVEL if st['nexts'] < nexts else TELEPORT
        set_debug(e, ph < 100)
        b = 0
        if ph < 56: set_cursor(e, item)
        if ph < 5: b |= BTN['START']
        if 48 <= ph < 53 and item == TELEPORT: b |= BTN['A']
        if 88 <= ph < 93 and item == TELEPORT: b |= BTN['START']
        e.pad(b)
        if ph == per - 1:
            if item == NEXT_LEVEL:
                st['nexts'] += 1
                print('next level ->', hex(e.r16(LEVEL_ID)), flush=True)
            else:
                p = find_player(e)
                x = e.rf(p + 0x50) if p else 1e9
                print('teleport -> (%.1f,%.1f,%.1f)' % (x, e.rf(p + 0x54), e.rf(p + 0x58)) if p else '?', flush=True)
                if abs(x - tx) < 2: st['done'] = k; st['dash'] = p
            if i > 20: print('gave up'); e.stop()
    e.run(script)


def next_level(rom, start, n, out, frame=None):
    teleport(rom, start, n, None, out, frame=frame)


def wait(rom, start, seconds, out, frame=None):
    """From `start`, no input, saved `seconds` later (60 frames a second)."""
    e = Emu(rom)
    t = int(seconds * 60)
    st = {}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        e.pad(0)
        if 'saved' not in st and (k > 10 and e.r32(GAME_FRAME) >= frame if frame else k == t):
            st['saved'] = k; e.save_state(out); e.shot(); _report(e, out)
        if st.get('saved') is not None and k == st['saved'] + 5: e.stop()
    e.run(script)


def place(rom, start, x, y, z, yaw, out, wait=90, frame=None):
    """From `start`: the player's place written (+0x50 and its copy +0x08) and his yaw (Humn +0x8C and its copy
    +0x14: the game writes +0x8C back from it, as t_crate.py does), for a place
    that is no debug teleport point; `wait` VIs with no input and his health kept full, then saved (with `frame`: at
    the first VI after that when the game's frame counter reaches it). Holds on static ground only: a written place
    skips the scripted triggers on the way (cutscenes, boss fights)."""
    e = Emu(rom)
    st = {}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        e.pad(0)
        p = st.get('p') or find_player(e)
        if not p: return
        st['p'] = p
        if k < 4:                                      # a few VIs: the game's own frame may write its old place back
            for i, v in enumerate((x, y, z)):
                e.wf(p + 0x50 + 4 * i, v); e.wf(p + 0x08 + 4 * i, v)
            e.wf(p + HUMN_YAW, yaw); e.wf(p + 0x14, yaw)
        set_health(e, p)
        if 'saved' not in st and k >= wait and (e.r32(GAME_FRAME) >= frame if frame else True):
            st['saved'] = k; e.save_state(out); e.shot(); _report(e, out)
        if st.get('saved') is not None and k == st['saved'] + 5: e.stop()
    e.run(script)


def _menu_item(e, k, item):
    """VI `k` of running a debug-menu item: the pause screen opened with the cursor on it; the flag off from VI 10."""
    set_debug(e, k < 10)
    if k < 10: set_cursor(e, item)
    elif k == 10: set_cursor(e, 0)
    e.pad(BTN['START'] if 2 <= k < 7 else 0)


def menu(rom, start, item, out, wait=200, frame=None):
    """From `start`: one debug-menu item (`GET_ALL`, `INVINCIBLE`: the entries that act at once), run by opening the
    pause screen with the cursor on it (the game runs the entry, clears the debug flag and unpauses); the flag kept
    off after. `wait` VIs more with no input and the player's health kept full, then saved (with `frame`: at the first
    VI after that when the game's frame counter reaches it)."""
    e = Emu(rom)
    st = {}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        p = st.get('p') or find_player(e)
        if p: st['p'] = p; set_health(e, p)
        _menu_item(e, k, item)
        if 'saved' not in st and k >= wait and (e.r32(GAME_FRAME) >= frame if frame else True):
            st['saved'] = k; e.save_state(out); e.shot(); _report(e, out)
        if st.get('saved') is not None and k == st['saved'] + 5: e.stop()
    e.run(script)


def ride(rom, start, seconds, out, frame=None):
    """From `start` on the Ord Mantell train: no input, the player's health kept full, saved `seconds` later (with
    `frame`: when the game's frame counter reaches it instead)."""
    e = Emu(rom)
    t = int(seconds * 60)
    st = {}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        e.pad(0)
        p = st.get('p') or find_player(e)
        if p: st['p'] = p; set_health(e, p)
        if k % 600 == 0 and p: print('ride', k, 'frame', e.r32(GAME_FRAME), 'player (%.1f, %.1f, %.1f)'
                                     % tuple(e.rf(p + 0x50 + 4 * i) for i in range(3)), flush=True)
        if 'saved' not in st and (k > 10 and e.r32(GAME_FRAME) >= frame if frame else k == t):
            st['saved'] = k; e.save_state(out); e.shot(); _report(e, out)
        if st.get('saved') is not None and k == st['saved'] + 5: e.stop()
    e.run(script)


GLAD = 0x8019F4C4                                      # Xizor's gladiator droid (t_glad.py): AI state +0x584, health +0x5C4
GLAD_WALL = (31.0, -34.0, 123.4)                       # where the game puts Dash back after a death in the flying phase


def glad2(rom, start, out, wait=200):
    """From xiz_glad: his fight started as t_glad.py walk does (Dash on the roof, AI state +0x584 = 3), his health
    written 0 at VI 400: the game gives him his second phase ("Jetpack Malfunction": health 750 again, AI state 10,
    then 5 flying once Dash stands still). Dash's health is kept full until then, let go after: the game only moves
    him to the maze wall when he dies and respawns (kept alive, a bomb pushes him into the maze). 30 VIs after the
    respawn Invincibility (debug menu), `wait` VIs more, saved."""
    e = Emu(rom)
    st = {}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        p = st.get('p') or find_player(e)
        if not p: return
        st['p'] = p
        here = tuple(e.rf(p + 0x50 + 4 * i) for i in range(3))
        if k < 30:
            for off in (0x50, 0x08):
                for i, v in enumerate((-5.0, 0.0, 124.0)): e.wf(p + off + 4 * i, v)
        if k == 40: e.w32(GLAD + 0x584, 3)
        if k == 400: e.wf(GLAD + 0x5C4, 0.0)
        if k > 400 and 'fly' not in st and e.r32(GLAD + 0x584) == 5:
            st['fly'] = k; print('flying phase at', k, 'frame', e.r32(GAME_FRAME), flush=True)
        if 'fly' not in st: set_health(e, p)
        if 'fly' in st and 'wall' not in st and all(abs(a - b) < 2 for a, b in zip(here, GLAD_WALL)):
            st['wall'] = k; print('respawned on the wall at', k, 'frame', e.r32(GAME_FRAME), flush=True)
        if 'wall' in st:
            d = k - st['wall'] - 30
            if d >= 0:
                set_health(e, p); _menu_item(e, d, INVINCIBLE)
            else: e.pad(0)
            if d == wait and 'saved' not in st:
                st['saved'] = k; e.save_state(out); e.shot(); _report(e, out)
        else: e.pad(0)
        if k % 300 == 0: print(k, 'frame', e.r32(GAME_FRAME), 'dash (%.1f, %.1f, %.1f)' % here, 'ai', e.r32(GLAD + 0x584),
                               'hp %.0f' % e.rf(GLAD + 0x5C4), flush=True)
        if st.get('saved') is not None and k == st['saved'] + 5: e.stop()
        if k > 6000 and 'saved' not in st: print('no respawn on the wall'); e.stop()
    e.run(script)


DIANOGA = [0x801BE098, 0x801BE1B8, 0x801BE2D8, 0x801BE3F8, 0x801BE518]   # the eye, the four tentacles (Trop)


def dianoga(rom, start, out, dist=18.0, wait=2):
    """From the sewer pool (Teleport point (672, -7.6, 101)): Invincibility (debug menu) at once, no input until the
    game marks the dianoga's five parts (+0x74 bit 0x20, ~10 s) and Dash has sunk to 4 units over the eye (~14 s;
    swimming off sooner leaves him ~8 units higher than the older state's), then the stick forward (Dash swims toward +x) until
    he is `dist` units from the eye (x, y); then bit 0x400 written into the parts' +0x74 (their woken state: nothing
    the player does in the harness sets it, the dianoga is woken this way) and saved `wait` VIs later (woken, the eye
    moves off at once: 20 VIs later Dash was 24.8 from it)."""
    e = Emu(rom)
    st = {}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        p = st.get('p') or find_player(e)
        if not p: return
        st['p'] = p
        set_health(e, p)
        d = ((e.rf(p + 0x50) - e.rf(DIANOGA[0] + 0x50)) ** 2 + (e.rf(p + 0x54) - e.rf(DIANOGA[0] + 0x54)) ** 2) ** 0.5
        if k < 200:
            _menu_item(e, k, INVINCIBLE); return
        if k % 120 == 0: print(k, 'dash z %.1f' % e.rf(p + 0x58), 'eye z %.1f' % e.rf(DIANOGA[0] + 0x58), 'd %.1f' % d, flush=True)
        if ('mark' not in st and all(e.r32(o + 0x74) & 0x20 for o in DIANOGA)
                and e.rf(p + 0x58) <= e.rf(DIANOGA[0] + 0x58) + 4): st['mark'] = k
        if 'mark' in st and 'far' not in st and d >= dist:
            st['far'] = k
            for o in DIANOGA: e.w32(o + 0x74, e.r32(o + 0x74) | 0x400)
            print('marked at', st['mark'], 'woken at', k, 'distance %.1f' % d, flush=True)
        e.pad(0, 0, 60) if 'mark' in st and 'far' not in st else e.pad(0)
        if 'far' in st and k - st['far'] == wait and 'saved' not in st:
            st['saved'] = k; e.save_state(out); e.shot(); _report(e, out)
            print('distance %.1f' % d, 'parts', ','.join('%#x' % e.r32(o + 0x74) for o in DIANOGA), flush=True)
        if st.get('saved') is not None and k == st['saved'] + 5: e.stop()
        if k > 4000 and 'saved' not in st: print('not reached'); e.stop()
    e.run(script)


def this_level(rom, start, sub, frames, out):
    """From `start`: sub-level `sub` written as the current one (u16 0x8013CE0E), debug This Level; no input after,
    saved `frames` VIs from This Level's press (the intro, sub-level 0, has no player)."""
    e = Emu(rom)

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(_src(start))
        if n < 64: return
        k = n - 64
        if k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | sub)
        if k < 130:
            set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0)
        if k - 2 == frames:
            e.save_state(out); e.shot(); _report(e, out)
        if k - 2 == frames + 5: e.stop()
    e.run(script)


if __name__ == '__main__':
    kw = {k: int(x.split('=')[1]) for x in sys.argv[1:] for k in ('frame', 'wait') if x.startswith(k + '=')}
    a = [x for x in sys.argv[1:] if not x.startswith(('frame=', 'wait='))]
    if a[0] == 'boot': boot(a[1], int(a[2]), a[3], 'onward' in a[4:], **kw)
    elif a[0] == 'teleport': teleport(a[1], a[2], int(a[3]), float(a[4]), a[5], **kw)
    elif a[0] == 'next': next_level(a[1], a[2], int(a[3]), a[4], **kw)
    elif a[0] == 'wait': wait(a[1], a[2], float(a[3]), a[4], **kw)
    elif a[0] == 'level': this_level(a[1], a[2], int(a[3]), int(a[4]), a[5])
    elif a[0] == 'menu': menu(a[1], a[2], {'get_all': GET_ALL, 'invincible': INVINCIBLE}[a[3]], a[4], **kw)
    elif a[0] == 'ride': ride(a[1], a[2], float(a[3]), a[4], **kw)
    elif a[0] == 'glad2': glad2(a[1], a[2], a[3], **kw)
    elif a[0] == 'dianoga': dianoga(a[1], a[2], a[3], **kw)
    elif a[0] == 'place': place(a[1], a[2], *map(float, a[3:7]), a[7], **kw)
    else: sys.exit(__doc__)
