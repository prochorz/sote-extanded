"""The Gall Run as its own sub-level 32: the ways in, the tables, death and restart,
the stock base level, the enemy shots' damage. Runs the build's ROM (no injection) from a state of that build.

    M64CPU=2 .venv/bin/python3 gallrun/own_level.py <build>/sote-patch.z64 --case CASE [--state S] [--to K]

  --case cheats   from run/<build>_echo.st: pause, Cheats, the last row (Gall Run), A. Then in the mission at +1500 the
                  Falcon blown up (Stft +0x240 = 0: the game's respawn), at +2400 the game's restart (level state
                  0x800DD2B0 = 6 with the fade on: 0x800271F0(LEVEL_ID) reloads), followed to +3300; changes of the
                  health, Stft state, level state and load queue printed from the kill on
         ast      from run/<build>_echo.st: debug This Level 6 (the base level as the level list loads it), 900 frames
         lvl31    from run/<build>_echo.st: debug This Level 31 (the game's last scene), held lines let go by A: the
                  sub-level after it
         q31      (M64CPU=0: a code word patched) from run/<build>_echo.st: debug This Level 31, at +400 the queue
                  0x800194DC forced to its -1 path (0x800194E8 bne -> nop until the queue is written) and the game's
                  restart triggered as in cheats: 0x800194DC(-1) from 31 (id + 1 = 32 against its bound); the id after
         golvl    from run/<build>_echo.st: pause, Cheats, the cursor on Go to level (g_cheats_row: the ITEMS row of id 7), g_lvl 0, L once
                  (printed: g_lvl after it, 32 when the list has 33 entries; the names 31/32 from g_levels + 0x148),
                  then g_lvl = --lvl (default 32), A; the level loaded, its blob, 1200 frames
         dmg      from --state (a state in the mission, e.g. run/<build>_s2.st), no input: every drop of the player
                  ship's health (Stft +0x240) with the frame; 3000 frames (--to)
  --dump P: the RDRAM at the end written to P (Emu.dump: little-endian words), e.g. a sub-level 32 RAM read (golvl).
Every frame: id 6's two table entries (0x80001388, 0x80001408) against their boot values, the stock tables' words
0x80001330..0x80001C70 against the frame-0 copy (counts of changed frames). Printed: each LEVEL_ID change, snapshots
(LEVEL_ID, which blob is in at 0x8019A040: ours / stock / other, g_gallrun, the GALL tag, the Stft's health and the
start values the base level's code sets by id: 0x8018DCA2, 0x800DEED4, the save's level index byte), SUM lines."""
import os, sys, struct, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
ap = argparse.ArgumentParser()
ap.add_argument('rom'); ap.add_argument('--case', required=True, choices=['cheats', 'ast', 'lvl31', 'q31', 'dmg', 'golvl'])
ap.add_argument('--lvl', type=int, default=32)
ap.add_argument('--state', default=''); ap.add_argument('--to', type=int, default=0)
ap.add_argument('--dump', default='')   # RDRAM (little-endian words, Emu.dump) written here at the end
A = ap.parse_args()
ROM = os.path.abspath(A.rom)
BUILD = os.path.basename(os.path.dirname(ROM))
os.environ.setdefault('SHOTS', f'own_{BUILD}_{A.case}')
import paths
import m64
from m64 import Emu, BTN, HERE
from debugmenu import set_debug, set_cursor

RUN = paths.RUN
ELF = os.path.join(os.path.dirname(ROM), 'payload.elf')
SYM = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.run(['nm', ELF], capture_output=True, text=True).stdout.splitlines()
       if len(l.split()) == 3}
LEVEL_ID, GALL, TAG_GALL, BLOB_AT, BLOB_VRAM = 0x8013CE0E, 0x80628000, 0x47414C4C, 0x8019A040, 0x80196950
TAB6 = (0x80001388, 0x80001408)
ASSETS = paths.GAME
OURS = open(os.path.join(ASSETS, 'gall_level.bin'), 'rb').read()
STOCK_P = os.path.join(ASSETS, 'gall_level_stock.bin')
STOCK = open(STOCK_P, 'rb').read() if os.path.exists(STOCK_P) else b''
start = A.state or os.path.join(RUN, f'{BUILD}_echo.st')
if not os.path.exists(start):
    if A.state: sys.exit(f'no {start}')
    print('making', start, flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, 'mkstate.py'), ROM, '1', start], check=True,
                   env=dict(os.environ, M64CPU='2'), stdout=open(start + '.log', 'w'), stderr=subprocess.STDOUT)
END = A.to or {'cheats': 5000, 'ast': 1000, 'lvl31': 9000, 'q31': 1500, 'dmg': 3000, 'golvl': 1400}[A.case]
e = Emu(ROM)


def s16(a): v = e.r16(a); return v - 0x10000 if v & 0x8000 else v
def r8(a): return (e.r32(a & ~3) >> (24 - 8 * (a & 3))) & 0xFF
def i32(v): return v - (1 << 32) if v & 0x80000000 else v


def stft():
    a = 0x80112808
    for _ in range(64):
        if e.r32(a) == 0x53746674: return e.r32(a + 0x10)
        a += 0x30
    return 0


def blob():
    w = e.r32(BLOB_AT); o = BLOB_AT - BLOB_VRAM
    if w == struct.unpack_from('>I', OURS, o)[0]: return 'ours'
    if STOCK and w == struct.unpack_from('>I', STOCK, o)[0]: return 'stock'
    return 'other'


def snap(k, tag):
    s = stft()
    print(f'SNAP {tag} k {k} id {s16(LEVEL_ID)} blob {blob()} g_gallrun {e.r32(SYM["g_gallrun"]) if "g_gallrun" in SYM else "-"}'
          f' GALL {"yes" if e.r32(GALL) == TAG_GALL else "no"} hp {i32(e.r32(s + 0x240)) if s else "-"}'
          f' dca2 {s16(0x8018DCA2)} deed4 {e.r32(0x800DEED4):08X} idx {r8(0x8018BC00 + r8(0x8018BBFD) * 0x7A)}'
          f' tab6 {e.r32(TAB6[0]):08X} {e.r32(TAB6[1]):08X}', flush=True)


S = {'lv': None, 'tab': None, 'tab6': None, 'tabchg': 0, 'tab6chg': 0, 'm': None, 'hp': None, 'drops': [], 'after31': None}
KILL, RESTART = 1500, 2400                         # frames into the mission (the opening shot keeps the health)
PRESS = {10: 'START', 50: 'D_D', 58: 'D_D', 66: 'D_D', 80: 'A', 120: 'U_D', 140: 'A'}   # pause, Quit+1 = Cheats, last row


def script(e, n):
    if n == 1: e.unlimit()
    if n == 60: e.load_state(start)
    if n < 64: return
    k = n - 64
    tab = [e.r32(a) for a in range(0x80001330, 0x80001C70, 4)]
    if S['tab'] is None: S['tab'] = tab; S['tab6'] = [e.r32(a) for a in TAB6]
    if tab != S['tab']: S['tabchg'] += 1
    if [e.r32(a) for a in TAB6] != S['tab6']: S['tab6chg'] += 1
    lid = s16(LEVEL_ID)
    if lid != S['lv']:
        print(f'k {k} LEVEL_ID {S["lv"]} -> {lid}', flush=True)
        if S['lv'] == 31 and A.case in ('lvl31', 'q31') and S['after31'] is None: S['after31'] = (k, lid)
        S['lv'] = lid
    if k == 0: snap(k, 'start')
    if A.case in ('ast', 'lvl31', 'q31'):
        if k == 0: e.w32(0x8013CE0C, (e.r32(0x8013CE0C) & 0xFFFF0000) | (6 if A.case == 'ast' else 31))
        if k < 130:
            set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0); return
        if A.case == 'ast' and k in (300, 900): snap(k, 'ast')
        if A.case == 'lvl31':
            S['h'] = S.get('h', 0) + 1 if s16(0x800DD2D0) else 0      # a line held: A after 30 frames (as c05_check)
            e.pad(BTN['A'] if S['h'] >= 30 and S['h'] % 60 < 5 else 0)
        if A.case == 'lvl31' and S['after31'] and k >= S['after31'][0] + 120: snap(k, 'after31'); e.stop(); return
        if A.case == 'q31':
            if k == 400:
                if lid != 31: print(f'k {k} not in 31 (id {lid})', flush=True); e.stop(); return
                S['bne'] = e.r32(0x800194E8); e.w32(0x800194E8, 0)
                e.w32(0x800DD2B0, 6); e.w32(0x800DD2D0, (e.r32(0x800DD2D0) & 0xFFFF) | (0x14 << 16)); e.w32(0x800DD2B4, 0)
                print(f'k {k} 0x800194E8 {S["bne"]:08X} -> nop, restart triggered in 31', flush=True)
            if k >= 400:
                w = (e.r32(0x800DD2B0), r8(0x800D2558), s16(0x800D255C))
                if w != S.get('w'): print(f'k {k} level state {w[0]} queue {w[1]} {w[2]} id {lid}', flush=True); S['w'] = w
                if 'bne' in S and w[1] == 2: e.w32(0x800194E8, S.pop('bne')); print(f'k {k} queued {w[2]}, 0x800194E8 put back', flush=True); S['q'] = w[2]
            if S['after31'] and k >= S['after31'][0] + 120: snap(k, 'after31'); e.stop(); return
    if A.case == 'cheats':
        b = [PRESS[p] for p in PRESS if p <= k < p + 4]
        e.pad(BTN[b[0]] if b else 0)
        if S['m'] is None and lid == 32: S['m'] = k; print(f'k {k} mission loaded as 32', flush=True)
        m = S['m']
        if m is not None:
            j = k - m
            if j in (300, KILL - 10): snap(k, f'mission+{j}')
            if j == KILL:
                s = stft(); e.w32(s + 0x240, 0); print(f'k {k} kill (Stft +0x240 = 0)', flush=True)
            if j >= KILL - 1:
                s = stft()
                w = (i32(e.r32(s + 0x240)) if s else None, e.r32(s + 0x230) if s else None, e.r32(0x800DD2B0), r8(0x800D2558), s16(0x800D255C))
                if w != S.get('w'):
                    S['nw'] = S.get('nw', 0) + 1
                    if S['nw'] < 60: print(f'k {k} +{j} hp/state {w[0]} {w[1]} level state {w[2]} queue {w[3]} {w[4]} id {lid} blob {blob()}', flush=True)
                    S['w'] = w
            if j in (KILL + 300, KILL + 600, RESTART - 10): snap(k, f'after-death+{j - KILL}')
            if j == RESTART:
                e.w32(0x800DD2B0, 6); e.w32(0x800DD2D0, (e.r32(0x800DD2D0) & 0xFFFF) | (0x14 << 16)); e.w32(0x800DD2B4, 0)
                print(f'k {k} restart (0x800DD2B0 = 6, fade on, 0x800DD2B4 = 0)', flush=True)
            if j in (RESTART + 300, RESTART + 900): snap(k, f'after-restart+{j - RESTART}')
            if j >= RESTART + 900: e.stop(); return
    if A.case == 'golvl':
        b = [PRESS[p] for p in PRESS if p <= k < p + 4 and p <= 80]
        if k == 100: e.w32(SYM['g_cheats_row'], next(i for i in range(64) if r8(SYM['ITEMS'] + 12 * i + 1) == 7)); e.w32(SYM['g_lvl'], 0)
        if 110 <= k < 114: b = ['L']
        if k == 130:
            def nm(i): return bytes(r8(SYM['g_levels'] + 0x148 + 64 * i + j) for j in range(32)).split(b'\0')[0].decode()
            print(f'k {k} open {e.r32(SYM["g_cheats_open"])} row {e.r32(SYM["g_cheats_row"])} g_lvl after L from 0: '
                  f'{i32(e.r32(SYM["g_lvl"]))}; names 31 "{nm(31)}" 32 "{nm(32)}"', flush=True)
            e.w32(SYM['g_lvl'], A.lvl)
        if 140 <= k < 144: b = ['A']
        e.pad(BTN[b[0]] if b else 0)
        if k in (400, 1200): snap(k, f'golvl{A.lvl}')
    if A.case == 'dmg':
        s = stft(); hp = i32(e.r32(s + 0x240)) if s else None
        if hp is not None and S['hp'] is not None and hp < S['hp']: S['drops'].append((k, S['hp'] - hp)); print(f'k {k} hp {S["hp"]} -> {hp}', flush=True)
        S['hp'] = hp
    if k >= END:
        snap(k, 'end')
        if A.dump: e.dump(A.dump); print('dumped', A.dump, flush=True)
        e.stop()


e.run(script)
print(f'SUM build {BUILD} case {A.case}: stock tables changed on {S["tabchg"]} frames, id 6 entries on {S["tab6chg"]} '
      f'({S["tab6"][0]:08X} {S["tab6"][1]:08X} at the start)', flush=True)
if A.case == 'cheats': print(f'SUM mission loaded as 32 at k {S["m"]}', flush=True)
if A.case in ('lvl31', 'q31'): print(f'SUM after 31: {S["after31"]} queued {S.get("q")}', flush=True)
if A.case == 'dmg':
    from collections import Counter
    print(f'SUM drops {len(S["drops"])}: {sorted(Counter(d for _, d in S["drops"]).items())}', flush=True)
