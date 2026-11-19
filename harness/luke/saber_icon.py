"""The saber's HUD weapon icon (feature saber): one sprite record in the game's own layout, made from the game's icons.

    python3 saber_icon.py [ram.bin] [out.png]     a preview (x4) from an Emu.dump() image of palace.st (default
                                                  local/game/palace.bin); guard_asset.py calls record()

The level's weapon icons are sprite records (*0x8013CE2C)[0..5] (96 x 36; read on palace.st): +0 s16 x, y; +4 s16
width, height; +8 f32 scale x, y; +0x10 u16 attributes (0x800: drawn by the HUD pass), s16 depth; +0x14 RGBA; +0x18 the
palette (16 RGBA5551 colours); +0x1C s16 bitmap count 4, s16 palette bytes 0x20; +0x20 u8 format 2 (CI), size 0
(4-bit); +0x24 the bitmap list {s16 width, s16 height, pointer}: 64 x 32, 32 x 32, 64 x 4, 32 x 4 (left to right, then
down), each CI4 with its odd lines' 32-bit words swapped (TMEM order). Slot 0's record is laid out header (0x30), palette
(0x20), texels (0x6C0), bitmap list (0x20): 0x730 bytes; record() makes the same at a given address.

The picture follows the game's icons: a framed box with the weapon drawn in it, under it a small box with a symbol and
a box with the name in the game's lettering. The frame is the laser icon's, the letters of "Saber" are cut from the
other icons' names (S, a, e, r; b is their p turned upside down, its bowl kept on the x-height rows) and outlined as
they are (white, a black 4-neighbour outline); the saber (a grey hilt, a white core in a green glow, as the blade)
and the symbol (a short slanted blade) are drawn here. Palette: the laser icon's frame, transparent, white and black entries kept, the
rest ours.
"""
import os, struct, sys
import numpy as np

HUD_SPRITES = 0x8013CE2C
W, H = 96, 36
TILES = ((0, 0, 64, 32), (64, 0, 32, 32), (0, 32, 64, 4), (64, 32, 32, 4))
NAMES = {0: 'Laser', 1: 'Pulse', 2: 'Flame', 3: 'Seeker', 4: 'Stunner', 5: 'Disruptor'}
TEXT = 'Saber'
TEXT_X = 20                                  # the names start there (the laser icon's 'L')
TEXT_ROWS = (21, 33)                         # the name box's inside rows (outline included)
CLEAR = ((3, 19, 3, 68), (21, 33, 3, 17), (21, 33, 19, 68))      # (rows, cols) cleared: picture, symbol, name boxes
T_, WHITE, BLACK = 1, 5, 9                   # palette indices kept from the laser icon
# ours: RGB per free index
OURS = {3: (60, 60, 66), 4: (120, 120, 128), 6: (176, 176, 184), 7: (232, 232, 236), 8: (170, 255, 170),
        10: (60, 220, 80), 11: (20, 150, 40), 12: (10, 70, 20)}     # the blade's glow: light to deep green


def rgba5551(r, g, b, a=1): return (r >> 3) << 11 | (g >> 3) << 6 | (b >> 3) << 1 | a


class Ram:
    def __init__(s, data): s.d = data
    def u32(s, a): return struct.unpack_from('>I', s.d, a & 0x7FFFFF)[0]
    def u16(s, a): return struct.unpack_from('>H', s.d, a & 0x7FFFFF)[0]
    def u8(s, a): return s.d[a & 0x7FFFFF]


def decode(r, rec):
    """a sprite record -> (index grid H x W, palette list)"""
    lut, n, bl = r.u32(rec + 0x18), r.u16(rec + 0x1C), r.u32(rec + 0x24)
    g = np.zeros((H, W), np.uint8)
    for i, (x, y, bw, bh) in enumerate(TILES[:n]):
        assert (r.u16(bl + 8 * i), r.u16(bl + 8 * i + 2)) == (bw, bh), 'bitmap layout'
        buf = r.u32(bl + 8 * i + 4)
        for yy in range(bh):
            for xx in range(bw):
                o = (yy * bw + xx) // 2 ^ (4 if yy % 2 else 0)
                v = r.u8(buf + o)
                g[y + yy, x + xx] = v >> 4 if xx % 2 == 0 else v & 15
    return g, [r.u16(lut + 2 * i) for i in range(16)]


def icons(r):
    t = r.u32(HUD_SPRITES)
    return {i: decode(r, r.u32(t + 4 * i)) for i in NAMES if r.u32(t + 4 * i)}


def glyphs(ic):
    """white masks per letter, rows as in the icons (one baseline)"""
    out = {}
    for i, (g, _) in ic.items():
        m = g[TEXT_ROWS[0]:TEXT_ROWS[1]] == WHITE
        cols = [c for c in range(19, 68) if m[:, c].any()]   # the name box only
        runs, cur = [], [cols[0]]
        for c in cols[1:]:
            if c == cur[-1] + 1: cur.append(c)
            else: runs.append(cur); cur = [c]
        runs.append(cur)
        assert len(runs) == len(NAMES[i]), f'{NAMES[i]}: {len(runs)} letters'
        for ch, run in zip(NAMES[i], runs): out.setdefault(ch, m[:, run[0]:run[-1] + 1])
    return out


def b_from_p(p, x_rows):
    """p turned upside down, its bowl back on the x-height rows"""
    rows = np.nonzero(p.any(axis=1))[0]
    top, bot = rows[0], rows[-1]
    q = np.zeros_like(p)
    f = p[top:bot + 1][::-1]
    base = x_rows[1]                          # the last x-height row
    q[base - len(f) + 1:base + 1] = f
    return q


def picture(r):
    ic = icons(r)
    g0, pal0 = ic[0]
    g = g0.copy()
    for r0, r1, c0, c1 in CLEAR: g[r0:r1, c0:c1] = T_
    gl = glyphs(ic)
    a = gl['a']; xr = np.nonzero(a.any(axis=1))[0]
    gl['b'] = b_from_p(gl['p'], (xr[0], xr[-1]))
    white = np.zeros((H, W), bool); x = TEXT_X + 1
    for ch in TEXT:
        m = gl[ch]
        white[TEXT_ROWS[0]:TEXT_ROWS[1], x:x + m.shape[1]] |= m
        x += m.shape[1] + 2                   # one outline column between letters (as the names)
    edge = np.zeros_like(white)
    edge[1:] |= white[:-1]; edge[:-1] |= white[1:]; edge[:, 1:] |= white[:, :-1]; edge[:, :-1] |= white[:, 1:]
    g[edge & ~white] = BLACK; g[white] = WHITE
    # the saber, lying along the picture box: hilt 6..19, blade 20..63, rows 9..12
    y0 = 9
    for c in range(6, 20):
        g[y0 - 1, c] = 3; g[y0, c] = 7 if c % 4 else 6; g[y0 + 1, c] = 6 if c % 4 else 4
        g[y0 + 2, c] = 4; g[y0 + 3, c] = 3
    for c in (9, 13):                          # grip rings
        g[y0:y0 + 3, c] = 3
    g[y0 - 2:y0 + 5, 19] = 4; g[y0 - 1:y0 + 4, 19] = 6   # the emitter
    for c in range(20, 64):
        tip = c >= 61
        g[y0 - 1, c] = 11 if not tip else T_; g[y0 + 4, c] = 11 if not tip else T_
        g[y0, c] = 8 if not tip else 10; g[y0 + 3, c] = 8 if not tip else 10
        g[y0 + 1, c] = WHITE; g[y0 + 2, c] = WHITE
        if c % 3 == 0 and not tip: g[y0 - 2, c] = 12; g[y0 + 5, c] = 12
    g[y0 + 1:y0 + 3, 64] = 8
    # the symbol: a short slanted blade with its glow (from the lower left)
    for k in range(9):
        cx, cy = 5 + k, 31 - k
        for dx, dy, v in ((-1, 0, 10), (1, 0, 10), (0, -1, 8), (0, 1, 8), (0, 0, WHITE)):
            if g[cy + dy, cx + dx] in (T_, 10, 8): g[cy + dy, cx + dx] = v
    g[31:33, 4:6] = 4; g[32, 4] = 3
    pal = list(pal0)
    for i, rgb in OURS.items(): pal[i] = rgba5551(*rgb)
    return g, pal


def texels(g):
    out = b''
    for x, y, bw, bh in TILES:
        t = bytearray(bw * bh // 2)
        for yy in range(bh):
            for xx in range(0, bw, 2):
                o = (yy * bw + xx) // 2 ^ (4 if yy % 2 else 0)
                t[o] = g[y + yy, x + xx] << 4 | g[y + yy, x + xx + 1]
        out += bytes(t)
    return out


def record(ram, at):
    """the icon's sprite record (0x730 bytes) for address at; ram: big-endian RDRAM image of palace.st"""
    g, pal = picture(Ram(ram))
    lut, tex = at + 0x30, at + 0x50
    bl = tex + 0x6C0
    rec = struct.pack('>hhhhffHhIIhhBBxxIII', 0, 0, W, H, 1.0, 1.0, 0x0A20, -1, 0xFFFF0000, lut, len(TILES), 0x20, 2, 0,
                      bl, 0, 0)
    assert len(rec) == 0x30
    rec += struct.pack('>16H', *pal) + texels(g)
    off = tex
    for x, y, bw, bh in TILES:
        rec += struct.pack('>hhI', bw, bh, off); off += bw * bh // 2
    assert len(rec) == 0x730
    return rec


def preview(ram, out):
    from PIL import Image
    g, pal = picture(Ram(ram))
    col = [((c >> 11 & 31) * 255 // 31, (c >> 6 & 31) * 255 // 31, (c >> 1 & 31) * 255 // 31, 255 if c & 1 else 0) for c in pal]
    im = Image.new('RGBA', (W, H))
    for y in range(H):
        for x in range(W): im.putpixel((x, y), col[g[y, x]])
    bg = Image.new('RGBA', (W, H), (90, 70, 50, 255)); bg.alpha_composite(im)
    bg.resize((W * 4, H * 4), Image.NEAREST).save(out)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import paths
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(paths.GAME, 'palace.bin')
    raw = open(src, 'rb').read()                  # an Emu.dump() image: host-endian (little) words
    ram = b''.join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4))
    preview(ram, sys.argv[2] if len(sys.argv) > 2 else 'saber_icon.png')
