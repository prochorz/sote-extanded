"""Luke's HUD portrait (feature guard, the Look on Luke): one sprite record in the form of Dash's, his face from the game's
own Cut 13 still.

    M64CPU=0 python3 luke_portrait.py --dump <stock rom> [out]   Cut 13's RAM -> local/game/cut13.bin (one emulator run)
    python3 luke_portrait.py --preview out.png [palace.bin cut13.bin]
                                                  Dash's portrait and ours side by side (x6), and the record checked
    guard_asset.py calls record()

Dash's portrait is the level's HUD sprite (*0x8013CE2C)[9] (read on palace.st, the layout of saber_icon.py's records):
64 x 38 CI4, two bitmaps (64 x 32 + 64 x 6), laid out header (0x30), palette (0x20), texels (0x400 + 0xC0), bitmap list
(0x10): 0x520 bytes. The face sits in a frame of three rings (palette entries 0, 2, 3; entry 1 the transparent rest of
the 64 columns), its inside rows 3..34, columns 3..31 (29 x 32). The record here is Dash's with that inside replaced:
everything outside it, the header and the frame's palette entries are his.

The picture: Cut 13 (sub-level 31) shows a 320 x 140 CI8 still of Leia and Luke (its HUD sprite slot 1) from its first
scene VIs; Luke's face is the box (160, 5)-(265, 125) of it. The box is cropped to the inside's aspect around its centre,
scaled to 29 x 32 with an area filter and quantized (median cut, no dither) to the 12 palette entries the frame leaves
free (4..15). Before the scale Leia's hand on his left shoulder (the region HAND_BOX of the still) is painted out
(no_hand()): every pixel there lighter than the jacket's dark colours (luminance above the 90th percentile of the
region's darkest third) takes the jacket's median colour (those darkest third's per-channel median).

--dump loads Cut 13 the way the debug menu's This Level does (the level id written, the menu run from play.st), presses
A through the scene's line holds, and dumps RAM (Emu.dump(): host-endian words) at scene VI 60.
"""
import os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import paths

HUD_SPRITES = 0x8013CE2C
LEVEL = 0x8013CE0C                           # u32: its low half the level id (s16 at 0x8013CE0E)
LINE_HOLD = 0x800DD2D0                       # s16: a scene line waits for A
CUT13 = 31                                   # Cut 13's sub-level id
DUMP_VI = 60                                 # scene VI of the dump
SLOT_DASH, SLOT_STILL = 9, 1                 # Dash's portrait on a level; Cut 13's still
W, H = 64, 38
TILES = ((0, 0, 64, 32), (0, 32, 64, 6))     # Dash's bitmaps (x, y, w, h)
SIZE = 0x520                                 # the record: header, palette, texels, bitmap list
LUT, TEX, LIST = 0x30, 0x50, 0x510           # offsets in it
INNER = (3, 35, 3, 32)                       # rows, cols of the inside (end exclusive)
FRAME_IDX = (0, 1, 2, 3)                     # palette entries the frame uses (kept)
FREE_IDX = tuple(range(4, 16))
STILL_WH = (320, 140)
FACE_BOX = (160, 5, 265, 125)                # Luke's face in the still (x0, y0, x1, y1)
HAND_BOX = (140, 92, 190, 140)               # Leia's hand on his shoulder in the still (x0, y0, x1, y1; ends exclusive)
CUT13_BIN = os.path.join(paths.GAME, 'cut13.bin')
PALACE_BIN = os.path.join(paths.GAME, 'palace.bin')


class Ram:
    def __init__(s, data): s.d = data        # big-endian RDRAM image
    def u32(s, a): return struct.unpack_from('>I', s.d, a & 0x7FFFFF)[0]
    def u16(s, a): return struct.unpack_from('>H', s.d, a & 0x7FFFFF)[0]
    def u8(s, a): return s.d[a & 0x7FFFFF]
    def ok(s, a): return 0x80000000 <= a < 0x80800000


def load(path):
    """an Emu.dump() image (host-endian words) -> big-endian bytes"""
    return np.frombuffer(open(path, 'rb').read(), '<u4').astype('>u4').tobytes()


def rgba(c): return ((c >> 11 & 31) * 255 // 31, (c >> 6 & 31) * 255 // 31, (c >> 1 & 31) * 255 // 31, 255 if c & 1 else 0)
def rgba5551(r, g, b, a=1): return (r >> 3) << 11 | (g >> 3) << 6 | (b >> 3) << 1 | a


def decode(r, rec):
    """a portrait record (Dash's form) -> (index grid H x W, 16 RGBA5551 colours)"""
    assert (r.u16(rec + 4), r.u16(rec + 6)) == (W, H), 'size'
    lut, n, bl = r.u32(rec + 0x18), r.u16(rec + 0x1C), r.u32(rec + 0x24)
    assert n == len(TILES), 'bitmap count'
    g = np.zeros((H, W), np.uint8)
    for i, (x, y, bw, bh) in enumerate(TILES):
        assert (r.u16(bl + 8 * i), r.u16(bl + 8 * i + 2)) == (bw, bh), 'bitmap layout'
        buf = r.u32(bl + 8 * i + 4)
        for yy in range(bh):
            for xx in range(bw):
                v = r.u8(buf + ((yy * bw + xx) // 2 ^ (4 if yy % 2 else 0)))
                g[y + yy, x + xx] = v >> 4 if xx % 2 == 0 else v & 15
    return g, [r.u16(lut + 2 * i) for i in range(16)]


def dash(r):
    """Dash's slot 9 record: (address, raw bytes), its layout checked"""
    rec = r.u32(r.u32(HUD_SPRITES) + 4 * SLOT_DASH)
    lut, bl = r.u32(rec + 0x18), r.u32(rec + 0x24)
    assert (lut - rec, bl - rec) == (LUT, LIST), 'record layout'
    assert [r.u32(bl + 8 * i + 4) - rec for i in range(2)] == [TEX, TEX + 0x400], 'texel layout'
    a = rec & 0x7FFFFF
    return rec, r.d[a:a + SIZE]


def still(r):
    """Cut 13's still (slot 1, 320 x 140 CI8) -> RGB array"""
    rec = r.u32(r.u32(HUD_SPRITES) + 4 * SLOT_STILL)
    w, h = r.u16(rec + 4), r.u16(rec + 6)
    assert (w, h) == STILL_WH and r.u8(rec + 0x21) == 1, 'still form'
    lut, n, bl = r.u32(rec + 0x18), r.u16(rec + 0x1C), r.u32(rec + 0x24)
    pal = np.array([rgba(r.u16(lut + 2 * i))[:3] for i in range(256)], np.uint8)
    img = np.zeros((h, w, 3), np.uint8); x = y = rowh = 0
    for i in range(n):
        bw, bh, buf = r.u16(bl + 8 * i), r.u16(bl + 8 * i + 2), r.u32(bl + 8 * i + 4)
        if x >= w: x = 0; y += rowh
        a = buf & 0x7FFFFF
        for yy in range(bh):
            row = r.d[a + yy * bw:a + (yy + 1) * bw]
            if yy % 2: row = b''.join(row[j + 4:j + 8] + row[j:j + 4] for j in range(0, bw, 8))
            img[y + yy, x:x + bw] = pal[np.frombuffer(row, np.uint8)][:w - x]
        x += bw; rowh = bh
    return img


def no_hand(img):
    """the still with Leia's hand (HAND_BOX) painted in the jacket's colour"""
    x0, y0, x1, y1 = HAND_BOX
    img = img.copy(); reg = img[y0:y1, x0:x1].astype(float)
    lum = reg @ np.array([0.299, 0.587, 0.114])
    dark = lum <= np.percentile(lum, 100 / 3)
    thr = np.percentile(lum[dark], 90)
    jacket = np.median(reg[dark], axis=0).round().astype(np.uint8)
    img[y0:y1, x0:x1][lum > thr] = jacket
    return img


def face(r_cut):
    """the inside: Luke's face box cropped to the inside's aspect, area-scaled, median cut to the free entries
    -> (index grid of the inside, {entry: RGBA5551})"""
    from PIL import Image
    r0, r1, c0, c1 = INNER
    iw, ih = c1 - c0, r1 - r0
    x0, y0, x1, y1 = FACE_BOX
    bw, bh = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if bw / bh > iw / ih: bw = bh * iw / ih
    else: bh = bw * ih / iw
    box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    im = Image.fromarray(no_hand(still(r_cut)), 'RGB').resize((iw, ih), Image.BOX, box=box)
    q = im.quantize(colors=len(FREE_IDX), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    p = q.getpalette()[:3 * len(FREE_IDX)]
    idx = np.array(q, np.uint8)
    used = sorted(set(idx.flatten().tolist()))
    assert len(used) <= len(FREE_IDX)
    cols = {FREE_IDX[k]: rgba5551(*p[3 * k:3 * k + 3]) for k in range(len(p) // 3)}
    return np.array(FREE_IDX, np.uint8)[idx], cols


def picture(r_dash, r_cut):
    """(Dash's grid, his palette), (ours, our palette)"""
    rec, _ = dash(r_dash)
    g0, pal0 = decode(r_dash, rec)
    inner, cols = face(r_cut)
    g = g0.copy()
    r0, r1, c0, c1 = INNER
    g[r0:r1, c0:c1] = inner
    pal = list(pal0)
    for i in FREE_IDX: pal[i] = cols.get(i, 0)
    return (g0, pal0), (g, pal)


def texels(g):
    out = b''
    for x, y, bw, bh in TILES:
        t = bytearray(bw * bh // 2)
        for yy in range(bh):
            for xx in range(0, bw, 2):
                t[(yy * bw + xx) // 2 ^ (4 if yy % 2 else 0)] = g[y + yy, x + xx] << 4 | g[y + yy, x + xx + 1]
        out += bytes(t)
    return out


def record(ram_dash, ram_cut, at):
    """the portrait record (0x520 bytes) for address at; ram_dash: big-endian RDRAM of palace.st (palace.bin), ram_cut:
    of Cut 13 (cut13.bin). Dash's record with its pointers moved to at, the inside and the free palette entries ours."""
    r_dash = Ram(ram_dash)
    _, raw = dash(r_dash)
    _, (g, pal) = picture(r_dash, Ram(ram_cut))
    hdr = bytearray(raw[:LUT])
    struct.pack_into('>I', hdr, 0x18, at + LUT)
    struct.pack_into('>I', hdr, 0x24, at + LIST)
    lst = bytearray(raw[LIST:SIZE])
    off = at + TEX
    for i, (x, y, bw, bh) in enumerate(TILES):
        struct.pack_into('>I', lst, 8 * i + 4, off); off += bw * bh // 2
    rec = bytes(hdr) + struct.pack('>16H', *pal) + texels(g) + bytes(lst)
    assert len(rec) == SIZE
    return rec


def image(g, pal):
    from PIL import Image
    col = np.array([rgba(c) for c in pal], np.uint8)
    return Image.fromarray(col[g], 'RGBA')


def check(ram_dash, ram_cut, at=0x80560000):
    """the record decodes back to the picture; its form and frame are Dash's. -> (Dash's, ours) decoded"""
    rec = record(ram_dash, ram_cut, at)
    mem = bytearray(0x800000); mem[at & 0x7FFFFF:(at & 0x7FFFFF) + SIZE] = rec
    r = Ram(bytes(mem))
    g, pal = decode(r, at)
    r_dash = Ram(ram_dash)
    (g0, pal0), (gp, palp) = picture(r_dash, Ram(ram_cut))
    _, raw = dash(r_dash)
    assert (g == gp).all() and pal == palp, 'record != picture'
    frame = np.ones((H, W), bool); r0, r1, c0, c1 = INNER; frame[r0:r1, c0:c1] = False
    assert (g[frame] == g0[frame]).all(), 'frame pixels'
    assert [pal[i] for i in FRAME_IDX] == [pal0[i] for i in FRAME_IDX], 'frame palette'
    assert set(g[r0:r1, c0:c1].flatten().tolist()) <= set(FREE_IDX), 'inside uses frame entries'
    hdr = bytearray(rec[:LUT]); h0 = bytearray(raw[:LUT])
    for o in (0x18, 0x24): hdr[o:o + 4] = h0[o:o + 4] = b'\0' * 4
    assert hdr == h0, 'header'
    used = sorted(set(g[r0:r1, c0:c1].flatten().tolist()))
    print(f'record 0x{SIZE:X} bytes, {W} x {H}, {r.u16(at + 0x1C)} bitmaps, inside {c1 - c0} x {r1 - r0}, '
          f'{len(used)} colours {used}; frame pixels {int(frame.sum())} equal Dash\'s; decodes back: ok')
    return (g0, pal0), (g, pal)


def preview(ram_dash, ram_cut, out):
    from PIL import Image
    (g0, pal0), (g, pal) = check(ram_dash, ram_cut)
    k, gap = 6, 8
    bg = Image.new('RGBA', (2 * W + 3 * gap, H + 2 * gap), (90, 90, 100, 255))
    bg.alpha_composite(image(g0, pal0), (gap, gap)); bg.alpha_composite(image(g, pal), (W + 2 * gap, gap))
    bg.resize((bg.width * k, bg.height * k), Image.NEAREST).save(out)
    print('preview', out)


def dump(rom, out=CUT13_BIN):
    import m64
    from m64 import Emu, BTN
    from debugmenu import set_debug, set_cursor
    os.environ.setdefault('SHOTS', 'luke_portrait')
    e = Emu(rom); st = {'start': None}
    def script(e, n):
        if n == 1: e.unlimit(False)
        if n == 60: e.load_state(os.path.join(paths.STATES, 'play.st'))
        if n < 64: return
        k = n - 64
        if k == 0: e.w32(LEVEL, (e.r32(LEVEL) & 0xFFFF0000) | CUT13)
        lvl = e.r16(LEVEL + 2)
        if k < 130:                           # This Level from the pause screen's debug list
            set_debug(e, k < 10); set_cursor(e, 8 if k < 10 else 0); e.pad(BTN['START'] if k < 2 else 0); return
        if k > 3000: print('no Cut 13 by VI', k); e.stop(); return
        if lvl != CUT13: return
        if st['start'] is None: st['start'] = k
        e.pad(BTN['A'] if e.r16(LINE_HOLD) and k % 90 > 86 else 0)
        if k - st['start'] == DUMP_VI:
            e.dump(out); print('dump', out, flush=True); e.stop()
    e.run(script)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--dump':
        dump(a[1], a[2] if len(a) > 2 else CUT13_BIN)
    elif a and a[0] == '--preview':
        preview(load(a[2] if len(a) > 2 else PALACE_BIN), load(a[3] if len(a) > 3 else CUT13_BIN), a[1])
    else:
        print(__doc__)
