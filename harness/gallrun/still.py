"""A scene picture as the game's scene stills are: a HUD sprite, CI8 with 256
colours (RGBA5551), 64 x 32 tiles row by row (the last row as high as what is left), odd rows' 4-byte halves swapped (docs/reverse-engineering.md, HUD
sprites), drawn by the scenes' class Bmap (0x80009088(sprite, x, y)). The last scene's Dash-and-Leebo still is
sprite 1, 320 x 140 (Cut 05's is 512 x 140, panned).

still(path, crop, base) -> (blob, address of its sprite header) for the image at base."""
import struct
from PIL import Image

W, H = 320, 140
TILE_W, TILE_H = 64, 32
HDR_W0 = 0x10                       # (the stock still's first word)
FMT = 0x1222FFFF                    # (CI8, as the stock still)


def rgba5551(r, g, b):
    return (r >> 3) << 11 | (g >> 3) << 6 | (b >> 3) << 1 | 1


def fit(path, crop, w, h):
    """The picture's crop scaled to w x h."""
    return Image.open(path).convert('RGB').crop(crop).resize((w, h), Image.LANCZOS)


def blank(base):
    """A sprite that draws nothing (one 64 x 32 tile, its colours transparent): put over the scene's face overlays."""
    blob = bytearray(0x28) + bytes(0x200)
    tile = len(blob); blob += bytes(64 * 32)
    lst = len(blob); blob += struct.pack('>HHI', 64, 32, base + tile)
    struct.pack_into('>IHHffIIIIII', blob, 0, 0, 64, 32, 1.0, 1.0, FMT, 0xFFFF0000, base + 0x28, 1 << 16 | 0x20, 0x02010000, base + lst)
    return bytes(blob), base


def still(path, crop, base, w=W, h=H):
    """crop: (left, top, right, bottom) of the picture, scaled to w x h."""
    W, H = w, h
    im = fit(path, crop, w, h)
    q = im.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    pal = q.getpalette()[:768] + [0] * (768 - len(q.getpalette()[:768]))
    px = q.load()
    cols, rows = W // TILE_W, -(-H // TILE_H)
    blob = bytearray(0x28)                                       # the header (filled below)
    pal_at = len(blob)
    blob += b''.join(struct.pack('>H', rgba5551(*pal[3 * i:3 * i + 3])) for i in range(256))
    tiles = []
    for ty in range(rows):
        for tx in range(cols):
            t = bytearray()
            th = min(TILE_H, H - ty * TILE_H)                    # (the last row as high as what is left: the stock's)
            for y in range(th):
                row = bytes(px[tx * TILE_W + x, ty * TILE_H + y] for x in range(TILE_W))
                if y % 2:
                    row = b''.join(row[j + 4:j + 8] + row[j:j + 4] for j in range(0, TILE_W, 8))
                t += row
            tiles.append((len(blob), th)); blob += t
    list_at = len(blob)
    blob += b''.join(struct.pack('>HHI', TILE_W, th, base + t) for t, th in tiles)
    struct.pack_into('>IHHffIIIIII', blob, 0, HDR_W0, w, h, 1.0, 1.0, FMT, 0xFFFF0000, base + pal_at,
                     len(tiles) << 16 | 0x20, 0x02010000, base + list_at)
    return bytes(blob), base


def copy_sprite(ram, hdr, base):
    """A HUD sprite copied out of a big-endian RAM dump (header + palette + tiles + tile list), rebased to base: the
    stock scenes' face overlays. The depth from header byte +0x21
    (1: CI8, a 256-colour palette; 0: CI4, a 16-colour one, 0x20 bytes), the tiles' byte size from it.
    Returns (blob, address of its header)."""
    R = lambda a, f='>I': struct.unpack_from(f, ram, a & 0x7FFFFF)[0]
    ci4 = not ram[(hdr + 0x21) & 0x7FFFFF]
    ncol = 16 if ci4 else 256
    nt = R(hdr + 0x1C) >> 16
    lst = R(hdr + 0x24)
    head = bytearray(ram[hdr & 0x7FFFFF:(hdr & 0x7FFFFF) + 0x28])
    blob = bytearray(head)
    pal_at = len(blob)
    pal = R(hdr + 0x18)
    blob += ram[pal & 0x7FFFFF:(pal & 0x7FFFFF) + 2 * ncol]
    tiles = []
    for t in range(nt):
        tw, th, buf = R(lst + 8 * t, '>H'), R(lst + 8 * t + 2, '>H'), R(lst + 8 * t + 4)
        n = tw * th // (2 if ci4 else 1)
        blob += bytes(-len(blob) % 8)
        tiles.append((tw, th, len(blob))); blob += ram[buf & 0x7FFFFF:(buf & 0x7FFFFF) + n]
    blob += bytes(-len(blob) % 8)
    list_at = len(blob)
    blob += b''.join(struct.pack('>HHI', tw, th, base + at) for tw, th, at in tiles)
    struct.pack_into('>I', blob, 0x18, base + pal_at)
    struct.pack_into('>I', blob, 0x24, base + list_at)
    return bytes(blob), base
