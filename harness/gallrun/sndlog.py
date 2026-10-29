"""The game's sound-call log, shared by the checks (fin_check.py, c05_check.py) and runnable on any state.

A stub per hooked entry (hand-encoded MIPS at STUB, needs M64CPU=0) logs into RAM: the caller's return address and the
args a0..a3, sp+0x10, sp+0x14. Hooked:
  fx  0x80007340(id, ch, pitch, vol, loop)              effects: vol x the effects option 0x800D2524, pan 0x40
  pos 0x800074BC(id, ch, pitch, vol, float *pos, loop)  a sound at a world point: vol x a linear fall-off from
                                                         0x800D07E8 (full) to 0x800D07EC (none), pan 64 + 45 x side
  pnf 0x8000742C(id, ch, pitch, vol, float *pos, loop, near, far)  pos with its own fall-off distances (near/far are
                                                         sp+0x18/0x1C: not logged; read them at the caller)
  mus 0x800073B4(id, ch, pitch, vol, loop)              music: vol x the music option 0x800D2528, pan 0x40
  q   0x80007128(id, ch, pitch, vol, pan, loop)         the queue all of them end in (8 slots at 0x80110FE8)
  trk 0x80006CC4                                         (inside 0x80006CB0, the music by a name)
  dma 0x800063E4                                         (optional) the sample DMA callback

    M64CPU=0 .venv/bin/python3 gallrun/sndlog.py <rom> <state> [--to K] [--quiet-ids ID,..] [--bank] [--pad A|none]
  --bank  the level's sound bank (*0x800EEB04 +0xC: instrument; count +0xE; sounds +0x10): per id its wave's ROM
          base, length and loop record, at the start
  --pad   hold a button the whole run (A: the ship levels' throttle)
  --tap N  A pressed 5 VIs of every N (lets held lines go, as the takes do), when --pad is none
  --play ID:PITCH:VOL:PAN:K0:K1[:CH]  request a looped sound from k K0 to K1 by writing a queue slot each frame as
          0x80007128 would (queue_put(): slot 7 if free; PITCH as passed to the calls, VOL as reaching the queue, PAN 0..127)
  (at the end: the 8 queue slots and the voices table 0x80110EE8)
  --dma ID   the sample DMA offsets read in that sound's wave per 30 VIs (it is being played)
  --restart ADDR  a float timer at ADDR (e.g. gall_story.c g_bolt_t, from nm of the build's payload.elf): each k it
          restarts (to >= 0 from < 0, or >= 0 and smaller than the frame before) printed as RESTART and counted at the end
Ends with a summary: each (tag, caller, id, ch) with its first/last k, count, and its args' range (vol, pan, pitch)."""
import struct

STUB = 0x807E0000                     # count word, entries of 8 words from +0x20 (512), then the stubs at +0x4100
NENT = 512
HOOKS = {0x80007340: 'fx', 0x8000742C: 'pnf', 0x800074BC: 'pos', 0x800073B4: 'mus', 0x80007128: 'q', 0x80006CC4: 'trk'}
BANK = 0x800EEB04


def lui(rt, i): return 0x3C000000 | rt << 16 | (i & 0xFFFF)
def lw(rt, o, rs): return 0x8C000000 | rs << 21 | rt << 16 | (o & 0xFFFF)
def sw(rt, o, rs): return 0xAC000000 | rs << 21 | rt << 16 | (o & 0xFFFF)
def addiu(rt, rs, i): return 0x24000000 | rs << 21 | rt << 16 | (i & 0xFFFF)
def andi(rt, rs, i): return 0x30000000 | rs << 21 | rt << 16 | (i & 0xFFFF)
def sll(rd, rt, sa): return rt << 16 | rd << 11 | sa << 6
def addu(rd, rs, rt): return rs << 21 | rt << 16 | rd << 11 | 0x21
def j(t): return 0x08000000 | (t >> 2) & 0x3FFFFFF
T8, T9, SP, RA = 24, 25, 29, 31


def f2(w): return struct.unpack('>f', struct.pack('>I', w & 0xFFFFFFFF))[0]


QUEUE = 0x80110FE8                    # 8 slots of 32 B: handle (-1 free, -2 new), id, loop, frame stamp, ch, pitch x2 (float),
GFRAME = 0x8018E9B0                   # vol, u16 pan; a looped one not re-requested this or the last frame fades (64000/s)


def queue_put(e, sid, ch, pitch, vol, pan, slot=7):
    """One frame's request of a looped sound, as 0x80007128 writes it (call every frame to keep it)."""
    a = QUEUE + 32 * slot
    if e.r32(a) == 0xFFFFFFFF: e.w32(a, 0xFFFFFFFE); e.w32(a + 4, sid)
    elif e.r32(a + 4) != sid: return False
    e.w32(a + 8, 1); e.w32(a + 12, e.r32(GFRAME)); e.w32(a + 16, ch)
    e.w32(a + 20, struct.unpack('>I', struct.pack('>f', pitch * 2))[0]); e.w32(a + 24, vol)
    e.w32(a + 28, (pan & 0xFFFF) << 16 | (e.r32(a + 28) & 0xFFFF))
    return True


class SndLog:
    """install(e) once at the start frame (the stubs: t8/t9 are free at a function's entry); read(k) every frame."""

    def __init__(self, e, dma=False, quiet=(), out=print):
        self.e, self.quiet, self.out = e, set(quiet), out
        self.hooks = dict(HOOKS)
        if dma: self.hooks[0x800063E4] = 'dma'
        self.tags = {i + 1: n for i, n in enumerate(self.hooks.values())}
        self.cur, self.calls, self.waves, self.dmaoff = 0, {}, {}, {}

    def _stub(self, at, entry, tag):
        e = self.e
        i0, i1 = e.r32(entry), e.r32(entry + 4)
        code = [lui(T8, STUB >> 16), lw(T9, 0, T8), addiu(T9, T9, 1), sw(T9, 0, T8), andi(T9, T9, NENT - 1), sll(T9, T9, 5),
                addu(T9, T9, T8), addiu(T8, 0, tag), sw(T8, 0x20, T9), sw(RA, 0x24, T9)]
        code += [sw(4 + r, 0x28 + 4 * r, T9) for r in range(4)]
        code += [lw(T8, 0x10, SP), sw(T8, 0x38, T9), lw(T8, 0x14, SP), sw(T8, 0x3C, T9), i0, i1, j(entry + 8), 0]
        for i, w in enumerate(code): e.w32(at + 4 * i, w)
        e.w32(entry, j(at)); e.w32(entry + 4, 0)
        return at + 4 * len(code)

    def install(self):
        e = self.e
        z = sum(1 for i in range(0, 0x4400, 4) if e.r32(STUB + i))
        self.out(f'stub area nonzero words before {z}')
        for i in range(0, 0x4100, 4): e.w32(STUB + i, 0)
        at = STUB + 0x4100
        for t, ent in enumerate(self.hooks): at = self._stub(at, ent, t + 1)

    def bank(self, ids=None):
        """The level's bank: {id: (sound, wave, ROM base, len, loop start, loop end, count)}."""
        e = self.e
        ins = e.r32(e.r32(BANK) + 0xC); cnt = e.r16(ins + 0xE); r = {}
        for sid in (ids if ids is not None else range(cnt)):
            if sid >= cnt: continue
            snd = e.r32(ins + 0x10 + 4 * sid); wt = e.r32(snd + 8); lp = e.r32(wt + 0xC)
            r[sid] = (snd, wt, e.r32(wt), e.r32(wt + 4), e.r32(lp) if lp else -1, e.r32(lp + 4) if lp else -1,
                      e.r32(lp + 8) if lp else 0)
        return ins, cnt, r

    def read(self, k):
        e = self.e
        c = e.r32(STUB)
        while self.cur != c:
            self.cur = (self.cur + 1) & 0xFFFFFFFF
            b = STUB + 0x20 + (self.cur & (NENT - 1)) * 32
            w = [e.r32(b + 4 * i) for i in range(8)]
            tag, ra, a0, a1 = self.tags.get(w[0], '?'), w[1], w[2] & 0xFFFF, w[3] & 0xFFFF
            if tag == 'trk':
                nm = bytes(e.r32(w[2] + i) >> (24 - 8 * (jj % 4)) & 0xFF for i in range(0, 16, 4) for jj in range(4)).split(b'\0')[0]
                self.out(f'  TRK k {k} ra {ra:#010x} name at {w[2]:#010x} {nm!r}'); continue
            if tag == 'dma':
                for sid, (b0, ln) in self.waves.items():
                    if b0 <= w[2] < b0 + ln: self.dmaoff[(k // 30, sid)] = max(self.dmaoff.get((k // 30, sid), 0), w[2] - b0)
                continue
            a0 = a0 - 0x10000 if a0 & 0x8000 else a0
            vol, pitch = w[5], f2(w[4])
            pan = w[6] & 0xFFFF if tag == 'q' else 0x40
            key = (tag, ra, a0, a1)
            d = self.calls.get(key)
            if d is None: d = self.calls[key] = {'first': k, 'last': k, 'n': 0, 'vol': [vol, vol], 'pan': [pan, pan],
                                                 'pitch': [pitch, pitch], 'loop': w[7] if tag != 'q' else w[7]}
            d['last'] = k; d['n'] += 1
            for f, v in (('vol', vol), ('pan', pan), ('pitch', pitch)): d[f] = [min(d[f][0], v), max(d[f][1], v)]
            if a0 in self.quiet and d['n'] > 1: continue
            if tag == 'q': args = f'pitch {pitch:.3f} vol {vol} pan {pan} loop {w[7]}'
            elif tag in ('pos', 'pnf'):
                p = w[6]
                xyz = tuple(round(e.rf(p + 4 * i), 1) for i in range(3)) if 0x80000000 <= p < 0x80800000 else None
                args = f'pitch {pitch:.3f} vol {vol} at {p:#010x} {xyz} loop {w[7]}'
            else: args = f'pitch {pitch:.3f} vol {vol} loop {w[6]}'
            self.out(f'  SND k {k} {tag:3s} ra {ra:#010x} id {a0} ch {a1} {args}')

    def summary(self):
        for (tag, ra, a0, a1), d in sorted(self.calls.items(), key=lambda x: x[1]['first']):
            self.out(f'  {tag:3s} ra {ra:#010x} id {a0:4d} ch {a1}: k {d["first"]}..{d["last"]} x{d["n"]} vol {d["vol"][0]}..{d["vol"][1]}'
                     f' pan {d["pan"][0]}..{d["pan"][1]} pitch {d["pitch"][0]:.3f}..{d["pitch"][1]:.3f}')


if __name__ == '__main__':
    import os, sys, argparse
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
    ap = argparse.ArgumentParser()
    ap.add_argument('rom'); ap.add_argument('state'); ap.add_argument('--to', type=int, default=1200)
    ap.add_argument('--quiet-ids', default=''); ap.add_argument('--bank', action='store_true'); ap.add_argument('--pad', default='none')
    ap.add_argument('--play', default=''); ap.add_argument('--dma', type=int, default=-1)
    ap.add_argument('--restart', default=''); ap.add_argument('--tap', type=int, default=0)
    A = ap.parse_args()
    os.environ.setdefault('SHOTS', 'sndlog_' + os.path.basename(A.state).split('.')[0])
    import m64
    from m64 import Emu, BTN
    e = Emu(os.path.abspath(A.rom), video=m64.GLN)
    L = SndLog(e, dma=A.dma >= 0, quiet={int(x, 0) for x in A.quiet_ids.split(',') if x}, out=lambda s: print(s, flush=True))
    S = {}

    def script(e, n):
        if n == 1: e.unlimit()
        if n == 60: e.load_state(os.path.abspath(A.state))
        if n < 64: return
        k = n - 64
        if k == 0:
            L.install()
            print('level', e.r16(0x8013CE0E), 'bank ptr', hex(e.r32(BANK)), flush=True)
            if A.bank:
                ins, cnt, r = L.bank()
                print(f'bank instrument {ins:#x} count {cnt}')
                for sid, (snd, wt, b0, ln, ls, le, lc) in r.items():
                    print(f'  id {sid:3d} wave {wt:#x} rom {b0:#08x} len {ln:7d} ({ln / 9 * 16 / 22050:5.2f} s @22k)'
                          + (f' loop {ls}..{le} x{lc:#x}' if ls >= 0 else ''))
            if A.dma >= 0:
                _, _, r = L.bank([A.dma]); L.waves[A.dma] = (r[A.dma][2], r[A.dma][3])
        if A.play:
            pp = A.play.split(':'); sid, pit, vol, pan, k0, k1 = int(pp[0]), float(pp[1]), int(pp[2]), int(pp[3]), int(pp[4]), int(pp[5])
            if k0 <= k <= k1 and not queue_put(e, sid, int(pp[6]) if len(pp) > 6 else 7, pit, vol, pan) and 'pf' not in S:
                S['pf'] = 1; print('queue slot 7 busy at k', k, flush=True)
        L.read(k)
        if A.restart:
            v_ = e.rf(int(A.restart, 16)); p_ = S.get('rv')
            if p_ is not None and v_ >= 0 and (p_ < 0 or v_ < p_):
                S.setdefault('rk', []).append(k); print(f'{k} RESTART {A.restart} {p_:.3f} -> {v_:.3f}', flush=True)
            S['rv'] = v_
        if A.pad != 'none': e.pad(BTN[A.pad])
        elif A.tap: e.pad(BTN['A'] if k % A.tap < 5 else 0)
        if k >= A.to:
            for i in range(8):            # the queue and the voices table 0x80110EE8 (handle, id, loop, stamp, ch, pitch, vol, pan)
                q_ = [e.r32(QUEUE + 32 * i + 4 * j) for j in range(8)]; v_ = [e.r32(0x80110EE8 + 32 * i + 4 * j) for j in range(8)]
                print(f'  slot {i} queue {[hex(x) for x in q_]} voice {[hex(x) for x in v_]} frame {e.r32(GFRAME)}')
            e.stop()

    e.run(script)
    print(f'sndlog {os.path.basename(A.state)} k 0..{A.to}')
    L.summary()
    if A.restart: print(f'restarts of {A.restart}: {len(S.get("rk", []))} at k {S.get("rk", [])}')
    for (kk, sid), off in sorted(L.dmaoff.items()): print(f'  dma k {kk * 30:5d} sound {sid}: offset {off}')
