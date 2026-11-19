"""Look: Dash drawn as the red palace guard (guard.c, the Cheats row Look: Dash / Guard / Luke).

    M64CPU=0 python3 t_guard.py <rom>      env GUARD_STATES='play.st palace.st' (the start states), GUARD_SHOTS=1 (shots
                                           at the Cheats menu and after the reload; one more after the reload always)

Runs the build's own ROM (PAYLOAD_BUILD/sote-patch.z64; <rom> only when that is missing): before the state loads,
the guard image must already be at 0x80548000 (_start's DMA). First the third value (play.st): the Cheats screen, up
TO_ROW rows onto Look (it wraps past Reset cheats), A three times: g_guard_on 1, 2, 0 (the row cycles). Then,
resumed, g_guard_on = 1, then 2 -> within 5 frames bone 1's list holds the image's LUKE meshes and none of the guard's
head meshes, every other bone's list the same meshes as with Guard; = 0 -> all 19 lists the game's again. Per start
state (play.st, palace.st; their held radio
line let go): the lists of Dash's 19 `trot` bone nodes are read, then g_guard_on = 1 ->
  - within 3 frames bone 17's node holds guard.c's list (g_ours);
  - bone 6 (the hand) holds the game's weapon mesh, last in its list: the mesh draw sets or clears w0 bit 0x80 on
    every drawn mesh by the render state the mesh drawn before left, so the bit follows draw order; 30 frames on the
    weapon carries it and the guard's hand does not (hang.c's hide_weapon picks the 0x80 meshes);
  - no node holds a mesh of Dash's but that weapon (children: bones, the weapon, the image's meshes);
  - 60 frames of stick up move Dash > 5 units (controls untouched);
  - the drop (guard.c guard_place, parked: no stick): his placement node's z (+0x24C's +0x40) minus his matrix's
    (+0x240, what the game copied into it) 0 +- 0.002 with Look 0 (the game's draw unchanged), -0.30 +- 0.015 with
    Look 1 and 2 (0.30 times the model bone's tilt, ~1 standing: model_walk.tilt, printed); the lowest drawn
    vertex (harness/model_walk.py) above his floor point (+0x10) within +-0.06 with Look 1 and 2 (Dash's own look:
    printed, the game's ~0.17);
then g_guard_on = 0 -> all 19 lists equal the game's within 3 frames. Then on again and the level reloaded from
Cheats (This Level): 600 frames later Dash is back at the level's start, the image's header and the sum of its first
4 KB are unchanged, and his rebuilt nodes hold the guard's lists again (the player object and its nodes come back at
the same addresses, and guard.c re-applies in the frame the game rebuilds them, so the gap cannot be timed).
Last, a ledge hang with Guard on (GUARD_HANG, default echo_crevasse.st, walked off as t_hang.py climb): while he
hangs bone 6's list holds the guard's hand and not the weapon, and the figure is not lowered (node z minus +0x240
0 +- 0.002: hang_face puts the hand on the rim, 0.30 lower would sink it into the ledge); climbed back up, both are
in it again.
Then the jump (guard.c jump(), JUMP_STATE default palace.st, its held line let go): three standing jumps on flat floor
(A held 6 VIs after 60 idle, the apex z - z0 read every VI) with Look 0, 2, 0 -> Luke's apex 2.0 +- 0.15 x Dash's
(Jump Power x LUKE_JUMP 1.4142: the launch vz scales by it); back on Dash his apex within 0.1 of the first and Jump
Power (0x800E0DC0) the value it had before Luke (printed: the apexes, the launch vz, Jump Power per jump).

    M64CPU=0 python3 t_guard.py <rom> portrait     Luke's HUD portrait (guard.c face()), env PORTRAIT_STATES (default the
                                                   twelve below), PORTRAIT_SHEET (the contact image, default
                                                   local/run/luke_face/portrait_game.png)

portrait: per state (palace.st first; its held radio line let go) the HUD sprite table's (*0x8013CE2C) slot 9 is read
before the Look is set (its form: 64 x 38, two bitmaps, is Dash's portrait), then g_guard_on = 2 -> a slot of that
form holds the image's FACE record within 2 VIs and keeps the game's place (+0 x, y equal), a slot of another form is
untouched; a still of the top-left corner 40 VIs on. A state made by this build (its .md5, as t_duel.py's duel.st:
run t_duel.py first) is loaded without an inject. On palace.st then g_guard_on = 0 -> the game's record back in
the slot within 2 VIs, and a still. The corners go into the contact image (one per state, labelled).
"""
import os, sys, struct
import _path
import paths
import inject as inj
from m64 import Emu, BTN
from inject import inject, syms
from game import DLG_GATE, HUMN_HP
from testlib import check, report
from model_walk import Ram, height, tilt

S = syms()
ROM = inj.BUILD / 'sote-patch.z64'
e = Emu(str(ROM) if ROM.exists() else sys.argv[1])
IMG = (inj.ASSETS / 'guard.bin').read_bytes()
BASE, ROWS, BONES = inj.GUARD_VRAM, 19, 19
OURS = S['g_ours']                      # guard.c: 19 lists of 9 words (LIST_MAX 8 + the lightning's slot)
ROW = 9 * 4
STATES = os.environ.get('GUARD_STATES', 'play.st palace.st').split()
THIS_LEVEL = 12                         # Cheats row (t_hang_cheats.py)
LOOK_ROW = 40
N_ITEMS = 42                            # Cheats rows in the default build (Look after Friendly Wampas)
TO_ROW = N_ITEMS - LOOK_ROW             # ups from the top (it wraps) onto Look
LUKE_AT = BASE + 8 + 8 * ROWS           # 'LUKE', mesh count, list (guard_asset.py)
PAUSED = 0x800DD2BC
HANG = os.environ.get('GUARD_HANG', 'echo_crevasse.st')
JUMP = os.environ.get('JUMP_STATE', 'palace.st')
JUMP_POWER = 0x800E0DC0                 # float, the game's Jump Power (guard.c scales it on Luke)
JUMP_LOOKS = (0, 2, 0)
st = {'k0': None}
res = {'idx': 0}


def r32(a): return e.r32(a)
def ptr(v): return 0x80000400 <= v < 0x80800000


def humn():
    p = r32(0x80112830)
    for i in range(80):
        r = r32(p + 4 * i)
        if not r: return 0
        if r32(r) == 0x48756D6E: return r32(r + 0x10)
    return 0


def nodes():
    """Dash's 19 trot bone nodes, or None"""
    h = humn()
    if not h: return None
    b = r32(h + 0x19C)
    for _ in range(40):
        if not ptr(b): return None
        if r32(b + 0x1C) == 0x74726F74: break
        b = r32(b + 0x14)
    else: return None
    return [r32(b + 0x38 + 0xA0 * i + 8) for i in range(BONES)]


def lists(ns): return [(r32(n + 0x0C), r32(n + 0x10)) for n in ns]
def kids(n): return [r32(r32(n + 0x10) + 4 * i) for i in range(min(r32(n + 0x0C), 16))]
def img_sum(): return sum(r32(BASE + o) for o in range(0, 4096, 4)) & 0xFFFFFFFF
def menu(t0):
    seq, t = [], t0
    for name, gap in [('START', 40)] + [('D_D', 8)] * 3 + [('A', 30)] + [('D_D', 8)] * THIS_LEVEL + [('A', 4)]:
        seq.append((t, name)); t += gap
    return seq, t


def in_img(c): return BASE <= c < BASE + len(IMG)
def drop(h): return e.rf(r32(h + 0x24C) + 0x40) - e.rf(h + 0x240)   # placement node z - the matrix's copied z
def soles(h): r = Ram.of(e); return height(r, r.u32(h + 0x24C), r.f(h + 0x10))[0]
def up(ns): return tilt(Ram.of(e), ns[18])   # the model bone's tilt: guard.c's drop is 0.30 times it


def look_phase(e, n):
    """The Look row's third value: cycling on the row, then bone 1's list on 2 (see the header)"""
    L = res.setdefault('look', {})
    if 'k0' not in L:
        e.load_state(os.path.join(paths.STATES, STATES[0])); L['k0'] = n
        seq, t = [], 10
        for name, gap in [('START', 40)] + [('D_D', 8)] * 3 + [('A', 30)] + [('U_D', 8)] * TO_ROW + \
                [('A', 20)] * 3 + [('B', 30)] + [('U_D', 8)] * 3 + [('A', 40)]:
            seq.append((t, name)); t += gap
        L['seq'] = seq; L['as'] = [f for f, nm in seq if nm == 'A'][1:4]; L['vals'] = []
        return
    k = n - L['k0']
    if k == 2: inject(e)
    if k < 4: return
    if e.r16(0x800DD2D0): e.w32(0x800DD2D0, e.r32(0x800DD2D0) & 0xFFFF); e.wf(0x800D07FC, 0)   # the held line
    pl = humn()
    if pl: e.wf(pl + 0xB4, 100.0)
    b = 0
    for f, nm in L['seq']:
        if f <= k < f + 4: b |= BTN[nm]
    e.pad(b)
    if k == L['as'][0] - 2: L['row'] = r32(S['g_cheats_row'])
    if k in [a + 15 for a in L['as']]: L['vals'].append(r32(S['g_guard_on']))
    end = L['seq'][-1][0]
    if k == end + 40: L['paused'] = r32(PAUSED); L['ns'] = ns = nodes(); L['orig'] = [kids(x) for x in ns]; e.w32(S['g_guard_on'], 1)
    if k == end + 45: L['guard'] = [kids(x) for x in L['ns']]; e.w32(S['g_guard_on'], 2)
    if k == end + 50:
        L['luke'] = [kids(x) for x in L['ns']]; e.w32(S['g_guard_on'], 0)
    if k == end + 55:
        L['off'] = [kids(x) for x in L['ns']]
        res['look_done'] = True; st['k0'] = None


def hang_phase(e, n):
    """Guard on, walk off the crevasse edge, hang 90 frames, climb (t_hang.py climb)"""
    h = res.setdefault('hang', {})
    if 'k0' not in h:
        e.load_state(os.path.join(paths.STATES, HANG)); h['k0'] = n; return
    k = n - h['k0']
    if k == 2: inject(e)
    if k < 4: return
    pl = e.r32(S['g_player'])
    if pl: e.wf(pl + HUMN_HP, 100.0)
    if k == 4: e.w32(S['g_guard_on'], 1)
    if k == 8:
        ns = nodes(); h['ns'] = ns
        h['weapon'] = [c for c in kids(ns[6]) if c not in ns and not in_img(c)]
        h['hand'] = [c for c in kids(ns[6]) if in_img(c)]
    hang, g = e.r32(S['g_hang_state']), h.get('grab')
    if hang and g is None: h['grab'] = g = k
    if g is None:
        e.pad(0, 80 if k >= 12 else 0, 0)
        if k > 320: e.stop()
        return
    hk = kids(h['ns'][6])
    if k == g + 30:
        h['during'] = (any(c in hk for c in h['weapon']), all(c in hk for c in h['hand']), hang)
        h['drop'] = drop(pl)
        print('hang +30: hand ' + ' '.join(f'{c:08x}:{r32(c):08x}' for c in hk), flush=True)
    e.pad(0, 0, 80 if g + 90 <= k < g + 100 else 0)
    if k == g + 200:
        h['after'] = (all(c in hk for c in h['weapon']), all(c in hk for c in h['hand']), hang)
        print('hang +200: hand ' + ' '.join(f'{c:08x}:{r32(c):08x}' for c in hk), flush=True)
        res['hang_done'] = True


def jump_phase(e, n):
    """Standing jumps with Look 0, 2, 0: the apex z - z0, the launch vz, Jump Power (see the header)"""
    J = res.setdefault('jump', {'jumps': []})
    if 'k0' not in J:
        e.load_state(os.path.join(paths.STATES, JUMP)); J['k0'] = n; J['t'] = None; return
    k = n - J['k0']
    if k == 2: inject(e)
    if k < 4: return
    if e.r16(0x800DD2D0): e.w32(0x800DD2D0, e.r32(0x800DD2D0) & 0xFFFF); e.wf(0x800D07FC, 0)   # the held line
    pl = humn()
    i = len(J['jumps'])
    if i >= len(JUMP_LOOKS): e.stop(); return
    if J['t'] is None:
        if i == 0: J['jp0'] = e.rf(JUMP_POWER)
        e.w32(S['g_guard_on'], JUMP_LOOKS[i]); J['t'] = k + 60
        J.update(vz=-1e9, zmax=-1e9, land=None, air=False); return
    t = J['t']
    if k < t:
        e.pad(0); e.wf(pl + 0xB4, 100.0)
        if k == t - 1: J['z0'] = e.rf(pl + 0x58); J['jp'] = e.rf(JUMP_POWER)
        return
    e.pad(BTN['A'] if k < t + 6 else 0)
    z, fl = e.rf(pl + 0x58), r32(pl + 0x74)
    J['vz'] = max(J['vz'], e.rf(pl + 0xA0)); J['zmax'] = max(J['zmax'], z)
    if fl & 0x08000000: J['air'] = True
    if J['air'] and fl & 0x04000000 and J['land'] is None: J['land'] = k
    if (J['land'] is not None and k >= J['land'] + 40) or k > t + 300:
        J['jumps'].append((JUMP_LOOKS[i], J['zmax'] - J['z0'], J['vz'], J['jp']))
        print(f"jump Look {JUMP_LOOKS[i]}: apex {J['zmax'] - J['z0']:.3f} vz {J['vz']:.3f} jump power {J['jp']:.4f} "
              f"air {(J['land'] or k) - t} VIs", flush=True)
        J['t'] = None


def script(e, n):
    if res.get('hang_done'): jump_phase(e, n); return
    if res['idx'] >= len(STATES) and st['k0'] is None and n >= 60: hang_phase(e, n); return
    if n == 59:
        res['boot'] = (r32(BASE), r32(BASE + 4), [r32(BASE + o) for o in range(0, 64, 4)])
    if n < 60: return
    if not res.get('look_done'): look_phase(e, n); return
    if st['k0'] is None:
        e.load_state(os.path.join(paths.STATES, STATES[res['idx']]))
        st.clear(); st['k0'] = n
        return
    k = n - st['k0']
    if k == 2: inject(e)
    if k < 4: return
    if e.r16(0x800DD2D0): e.w32(0x800DD2D0, e.r32(0x800DD2D0) & 0xFFFF); e.wf(0x800D07FC, 0)   # the held line
    name = STATES[res['idx']]
    R = res.setdefault(name, {})
    pl = humn()
    if pl: e.wf(pl + 0xB4, 100.0)
    b = 0
    if k == 18: R['drop0'], R['soles0'] = drop(pl), soles(pl)
    if k == 25: R['drop1'], R['soles1'], R['u1'] = drop(pl), soles(pl), up(st['ns'])
    if k == 29: R['drop2'], R['soles2'], R['u2'] = drop(pl), soles(pl), up(st['ns']); e.w32(S['g_guard_on'], 1)
    if k == 20:
        ns = nodes(); st['ns'] = ns; st['orig'] = lists(ns)
        st['dash'] = {c for x in ns for c in kids(x) if c not in ns}
        R['sum0'] = img_sum(); st['orig_hand'] = kids(ns[6])
        st['weapon'] = [c for c in kids(ns[6]) if ptr(c) and r32(c) & 0x80]   # the game's weapon, before ours
        e.w32(S['g_guard_on'], 1)
    if 21 <= k <= 23 and 'on_at' not in R and r32(st['ns'][17] + 0x10) == OURS + 17 * ROW:
        R['on_at'] = k - 20
    if k == 26:
        ns = st['ns']
        R['weapon'] = sum(1 for c in kids(ns[6]) if c in st['weapon'])
        R['bit80'] = [hex(c) for c in kids(ns[6]) if ptr(c) and r32(c) & 0x80]
        bad = [(i, hex(c)) for i, x in enumerate(ns) for c in kids(x)
               if c not in ns and c in st['dash'] and not (i == 6 and c in st['weapon'])]
        R['dash_left'] = bad
        print(f"{name} k{k}: hand " + ' '.join(f'{c:08x}:{r32(c):08x}' for c in kids(ns[6]))
              + ' was ' + ' '.join(f'{c:08x}:{r32(c):08x}' for c in st['orig_hand']), flush=True)
        R['img_meshes'] = sum(1 for x in ns for c in kids(x) if BASE <= c < BASE + len(IMG))
        st['p0'] = (e.rf(pl + 0x50), e.rf(pl + 0x54))
        e.w32(S['g_guard_on'], 2)       # the drop with Luke, read at k 29
    if k == 50:
        hk = kids(st['ns'][6])
        R['bits'] = [(f'{c:08x}', r32(c) & 0xFF, in_img(c)) for c in hk]
        R['bit_ok'] = bool(st['weapon']) and hk[-1:] == st['weapon'][:1] and r32(hk[-1]) & 0x80 and not any(
            r32(c) & 0x80 for c in hk if in_img(c))
    if 30 <= k < 90: e.pad(0, 0, 80); b = None
    if k == 92:
        p1 = (e.rf(pl + 0x50), e.rf(pl + 0x54))
        R['moved'] = ((p1[0] - st['p0'][0]) ** 2 + (p1[1] - st['p0'][1]) ** 2) ** .5
    if k == 100: e.w32(S['g_guard_on'], 0)
    if 101 <= k <= 103 and 'off_at' not in R and lists(st['ns']) == st['orig']:
        R['off_at'] = k - 100
    if k == 110:
        e.w32(S['g_guard_on'], 1)
        st['seq'], st['act'] = menu(k + 10)
    if 'seq' in st and b is not None:
        for f, nm in st['seq']:
            if f <= k < f + 4: b |= BTN[nm]
        act = st['act']
        if k > act + 30 and e.rf(DLG_GATE) > 0 and (k - act) % 90 < 4: b |= BTN['START']   # level intro messages
        if k - act in (-140, -8, 20) and os.environ.get('GUARD_SHOTS'): e.shot(); print('shot', name, k - act, flush=True)
        if (k - act) % 150 == 0:
            ns = nodes()
            print(f"{name} act+{k - act}: paused {r32(0x800DD2BC)} level {e.r16(0x8013CE0E)} humn {humn():08x} "
                  f"node17 {ns[17] if ns else 0:08x} (was {st['ns'][17]:08x})", flush=True)
        if k == act - 10: st['p_menu'] = (e.rf(pl + 0x50), e.rf(pl + 0x54))
        if k == act + 600:                # the reload's intro long over (a Humn at the same address, its nodes rebuilt)
            ns = nodes()
            p2 = (e.rf(pl + 0x50), e.rf(pl + 0x54)) if pl else (0, 0)
            R['back'] = ((p2[0] - st['p_menu'][0]) ** 2 + (p2[1] - st['p_menu'][1]) ** 2) ** .5
            R['hdr'] = (r32(BASE), r32(BASE + 4)); R['sum1'] = img_sum()
            R['new_on'] = bool(ns) and r32(ns[17] + 0x10) == OURS + 17 * ROW and all(
                any(BASE <= c < BASE + len(IMG) for c in kids(x)) for b, x in enumerate(ns) if b in (1, 6, 9, 17))
            e.shot()
            res['idx'] += 1; st['k0'] = None; return
    if b is not None: e.pad(b)


FACE_WH, FACE_TILES, SLOT_FACE = (64, 38), 2, 9
HUD_SPRITES = 0x8013CE2C
P_STATES = os.environ.get('PORTRAIT_STATES', 'palace.st play.st duel.st sew_428.st om.st xiz_glad.st sup.st lvl0.st '
                          'lvl4.st lvl7.st sky.st ast.st').split()


def face_rec():
    """the image's FACE record (after SABR's 24 bytes), 0: none"""
    o = LUKE_AT - BASE + 12
    nv, npart = struct.unpack_from('>II', IMG, o + 4)
    at = o + 12 + 4 * (1 + nv) * npart
    assert IMG[at:at + 4] == b'SABR' and IMG[at + 24:at + 28] == b'FACE', 'image header'
    return struct.unpack_from('>I', IMG, at + 28)[0]


def own(name):
    """a state made by this build (<state>.md5, as t_duel.py's duel.st): loaded without an inject (an inject on
    duel.st hangs the game, t_duel.py)"""
    import hashlib
    try: return open(os.path.join(paths.STATES, name) + '.md5').read() == hashlib.md5(open(ROM, 'rb').read()).hexdigest()
    except OSError: return False


def portrait():
    ours, P, shots = face_rec(), {}, []
    def form(s): return (e.r16(s + 4), e.r16(s + 6)) == FACE_WH and e.r16(s + 0x1C) == FACE_TILES if ptr(s) else False
    def slot(): t = r32(HUD_SPRITES); return r32(t + 4 * SLOT_FACE) if ptr(t) else 0
    def pscript(e, n):
        if n < 60: return
        if st['k0'] is None:
            if res['idx'] >= len(P_STATES): e.stop(); return
            e.load_state(os.path.join(paths.STATES, P_STATES[res['idx']])); st.clear(); st['k0'] = n; return
        k, name = n - st['k0'], P_STATES[res['idx']]
        R = P.setdefault(name, {})
        if k == 2 and not own(name): inject(e)
        if k < 3: return
        if e.r16(0x800DD2D0): e.w32(0x800DD2D0, e.r32(0x800DD2D0) & 0xFFFF); e.wf(0x800D07FC, 0)   # the held line
        pl = humn()
        if pl: e.wf(pl + 0xB4, 100.0)
        if k == 3:
            R['game'] = g = slot(); R['form'] = form(g)
            R['wh'] = (e.r16(g + 4), e.r16(g + 6), e.r16(g + 0x1C)) if ptr(g) else None
            e.w32(S['g_guard_on'], 2)
        if 4 <= k <= 5 and 'on_at' not in R and slot() == ours: R['on_at'] = k - 3
        if k == 40:
            R['slot40'] = slot(); R['xy'] = (r32(ours), r32(R['game']) if ptr(R['game']) else None)
            e.shot(); shots.append((name, 'Luke'))
        if name != P_STATES[0]:
            if k == 44: res['idx'] += 1; st['k0'] = None
            return
        if k == 60: e.w32(S['g_guard_on'], 0)
        if 61 <= k <= 62 and 'off_at' not in R and slot() == R['game']: R['off_at'] = k - 60
        if k == 90: e.shot(); shots.append((name, 'Dash'))
        if k == 94: res['idx'] += 1; st['k0'] = None
    for name in P_STATES:
        if name.startswith('duel') and not own(name): print(f'{name}: made by another build (t_duel.py remakes it)')
    e.unlimit(); e.run(pscript)
    check('the image has a FACE record', in_img(ours), f'{ours:08x}')
    for name in P_STATES:
        R = P.get(name, {})
        print(f"{name}: slot 9 {R.get('game', 0):08x} (w, h, bitmaps) {R.get('wh')} Dash's form {R.get('form')}; "
              f"swapped {R.get('slot40') == ours} (in {R.get('on_at')} VIs), x, y ours/game's "
              f"{' / '.join(f'{v:08x}' if v is not None else '-' for v in R.get('xy', (None, None)))}", flush=True)
        if R.get('form'):
            check(f'{name}: Look Luke -> slot 9 holds ours within 2 VIs', R.get('on_at') is not None and R.get('slot40') == ours,
                  f"in {R.get('on_at')} VIs, at VI 40 {R.get('slot40', 0):08x}")
            check(f'{name}: ours at the game\'s place (+0 x, y)', R.get('xy', (0, 1))[0] == R.get('xy', (0, 1))[1],
                  f"{R.get('xy')}")
        else:
            check(f'{name}: slot 9 of another form untouched', R.get('slot40') == R.get('game'), f"{R.get('slot40', 0):08x}")
    R = P.get(P_STATES[0], {})
    check(f'{P_STATES[0]}: Look Dash -> the game\'s record back within 2 VIs', R.get('off_at') is not None,
          f"in {R.get('off_at')} VIs")
    import glob
    from PIL import Image, ImageDraw
    files = sorted(glob.glob(os.path.join(e.shot_dir, '*.png')))
    if len(files) == len(shots):
        tiles = []
        for f, (name, look) in zip(files, shots):
            im = Image.open(f).convert('RGB'); w, h = im.size
            c = im.crop((0, 0, w * 112 // 320, h * 64 // 240)).resize((336, 192), Image.NEAREST)
            t = Image.new('RGB', (336, 212), (20, 20, 24)); t.paste(c, (0, 20))
            ImageDraw.Draw(t).text((4, 4), f'{name[:-3]} ({look})', fill=(255, 255, 255)); tiles.append(t)
        cols = 4; rows = -(-len(tiles) // cols)
        sheet = Image.new('RGB', (cols * 340, rows * 216), (60, 60, 66))
        for i, t in enumerate(tiles): sheet.paste(t, (i % cols * 340, i // cols * 216))
        out = os.environ.get('PORTRAIT_SHEET') or os.path.join(paths.LOCAL, 'run', 'luke_face', 'portrait_game.png')
        os.makedirs(os.path.dirname(out), exist_ok=True); sheet.save(out); print('contact image', out)
    else:
        print(f'shots: {len(files)} files for {len(shots)} stills: no contact image')
    sys.exit(report())


if sys.argv[2:3] == ['portrait']: portrait()
e.unlimit()
e.run(script)

hdr0 = struct.unpack_from('>II', IMG, 0)
boot = res.get('boot')
check('boot: _start put the guard image at 0x80548000', boot and boot[2] == list(struct.unpack_from('>16I', IMG, 0)),
      f'{boot[0]:08X} {boot[1]}' if boot else 'no read')
L = res.get('look', {})
check(f'Cheats: up {TO_ROW} from the top is the Look row', L.get('row') == LOOK_ROW, f"row {L.get('row')}")
check('Look row: A cycles 0 -> 1 -> 2 -> 0', L.get('vals') == [1, 2, 0], f"{L.get('vals')}")
magic, cnt, lst = struct.unpack_from('>III', IMG, LUKE_AT - BASE)
luke = [struct.unpack_from('>I', IMG, lst - BASE + 4 * i)[0] for i in range(cnt)] if magic == 0x4C554B45 else []
gcnt, glst = struct.unpack_from('>II', IMG, 8 + 8 * 1)
ghead = [struct.unpack_from('>I', IMG, glst - BASE + 4 * i)[0] for i in range(gcnt)]
lk, gd = L.get('luke') or [[]] * BONES, L.get('guard') or [[]] * BONES
check("Luke (2): bone 1's list holds the image's LUKE meshes, none of the guard's head",
      bool(luke) and all(c in lk[1] for c in luke) and not any(c in lk[1] for c in ghead),
      f"bone 1 {[hex(c) for c in lk[1]]}; LUKE {[hex(c) for c in luke]}; guard head {[hex(c) for c in ghead]}")
check("Luke (2): every other bone's list the guard's", bool(L.get('guard')) and all(
      sorted(lk[i]) == sorted(gd[i]) for i in range(BONES) if i != 1),
      f"differ at {[i for i in range(BONES) if i != 1 and sorted(lk[i]) != sorted(gd[i])]}")
check('back to 0: all 19 lists the game\'s', bool(L.get('orig')) and L.get('off') == L.get('orig'),
      f"differ at {[i for i in range(BONES) if (L.get('off') or [[]] * BONES)[i] != (L.get('orig') or [[]] * BONES)[i]]}")
for name in STATES:
    R = res.get(name, {})
    check(f'{name}: on -> bone 17 holds our list within 3 frames', 'on_at' in R, f"frame {R.get('on_at')}")
    check(f'{name}: the hand holds the game\'s weapon mesh', R.get('weapon') == 1,
          f"{R.get('weapon')}; w0 bit 0x80 now on {R.get('bit80')}")
    check(f'{name}: 30 frames on: the weapon last, bit 0x80 on it and not on the guard hand', bool(R.get('bit_ok')),
          f"hand list (mesh, w0 low byte, image) {R.get('bits')}")
    check(f'{name}: no Dash mesh left but the weapon', R.get('dash_left') == [] and R.get('img_meshes', 0) > 0,
          f"left {R.get('dash_left')}, image meshes {R.get('img_meshes')}")
    d0, d1, d2 = R.get('drop0', 9), R.get('drop1', 9), R.get('drop2', 9)
    check(f'{name}: Look 0: node z - matrix z 0 +- 0.002 (the game\'s draw)', abs(d0) <= 0.002,
          f"{d0:+.4f}; Dash's own soles {R.get('soles0', 9):+.3f}")
    check(f'{name}: Look 1 and 2: node z - matrix z -0.30 +- 0.015 (standing: the tilt u >= 0.95)',
          abs(d1 + 0.30) <= 0.015 and abs(d2 + 0.30) <= 0.015, f"{d1:+.4f}, {d2:+.4f}; u {R.get('u1', 9):.4f}, {R.get('u2', 9):.4f}")
    check(f'{name}: Look 1 and 2: the lowest drawn vertex within +-0.06 of the floor',
          abs(R.get('soles1', 9)) <= 0.06 and abs(R.get('soles2', 9)) <= 0.06,
          f"{R.get('soles1', 9):+.3f}, {R.get('soles2', 9):+.3f}")
    check(f'{name}: stick up moves Dash > 5 units', R.get('moved', 0) > 5, f"{R.get('moved', 0):.1f}")
    check(f'{name}: off -> all 19 lists back within 3 frames', 'off_at' in R, f"frame {R.get('off_at')}")
    check(f'{name}: the level reloaded (Dash back at its start, > 5 units from where he stood)', R.get('back', 0) > 5,
          f"{R.get('back', 0):.1f}")
    check(f'{name}: the image unchanged after the level load',
          R.get('hdr') == hdr0 and R.get('sum1') == R.get('sum0'),
          f"hdr {R.get('hdr')} sum {R.get('sum0', 0):08X} -> {R.get('sum1', 0):08X}")
    check(f'{name}: after the reload his nodes hold the guard again', R.get('new_on') is True, f"{R.get('new_on')}")
h = res.get('hang', {})
check(f'{HANG}: Guard on, hanging: weapon left out of the hand, guard hand kept',
      h.get('during', (1, 0, 0))[:2] == (False, True) and h.get('during', (0, 0, 0))[2],
      f"grab {h.get('grab')}; (weapon in, guard hand in, hang) {h.get('during')}")
check(f'{HANG}: Guard on, hanging: not lowered (node z - matrix z 0 +- 0.002)', abs(h.get('drop', 9)) <= 0.002,
      f"{h.get('drop', 9):+.4f}")
check(f'{HANG}: after the climb both back', h.get('after', (0, 0, 1))[:2] == (True, True) and not h.get('after', (0, 0, 1))[2],
      f"(weapon in, guard hand in, hang) {h.get('after')}")
J = res.get('jump', {}).get('jumps', [])
if len(J) == 3:
    (_, a0, v0, p0), (_, a1, v1, p1), (_, a2, v2, p2) = J
    print(f"jumps: Dash apex {a0:.3f} (vz {v0:.2f}), Luke {a1:.3f} (vz {v1:.2f}, x{a1 / a0:.3f}), Dash again {a2:.3f}; "
          f"jump power {res['jump']['jp0']:.4f} -> {p1:.4f} -> {p2:.4f}", flush=True)
check(f'{JUMP}: Look Luke: his apex 2.0 +- 0.15 x Dash\'s', len(J) == 3 and J[0][1] > 0 and abs(J[1][1] / J[0][1] - 2.0) <= 0.15,
      f"{[round(j[1], 3) for j in J]}")
check(f'{JUMP}: back on Dash: his apex within 0.1 of the first, Jump Power its value before',
      len(J) == 3 and abs(J[2][1] - J[0][1]) <= 0.1 and abs(J[2][3] - res['jump']['jp0']) <= 1e-4,
      f"apex {[round(j[1], 3) for j in J]}, jump power {[round(j[3], 4) for j in J]} (before {res.get('jump', {}).get('jp0')})")
sys.exit(report())
