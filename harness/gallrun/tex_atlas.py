"""Decode the textures a list of materials uses into a labelled atlas (to pick textures by eye).

    from tex_atlas import decode, atlas
    img = decode(E, texture_record)        # PIL image or None (CI4/CI8 + RGBA16 palette, RGBA16, I, IA)
    atlas(E, {label: texture_record}, out.png)
"""
import struct
from PIL import Image, ImageDraw


def decode(E, tr):
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    a, seg, imgs, tile, size = R(tr + 8), 0, [], None, None
    while R(a) >> 24 != 0xB8:
        w0, w1 = R(a), R(a + 4); op = w0 >> 24
        if w0 == 0xBC001006: seg = w1
        elif op == 0xFD:
            imgs.append(((w0 >> 21) & 7, (w0 >> 19) & 3, ((w1 & 0xFFFFFF) + seg) & 0x7FFFFF if (w1 >> 24) & 0xF == 4 else w1 & 0x7FFFFF))
        elif op == 0xF5 and (w1 >> 24) & 7 == 0: tile = ((w0 >> 21) & 7, (w0 >> 19) & 3, ((w0 >> 9) & 0x1FF) * 8)
        elif op == 0xF2: size = (((w1 >> 12) & 0xFFF) >> 2) + 1, ((w1 & 0xFFF) >> 2) + 1
        a += 8
    if not tile or not size or not imgs: return None
    fmt, siz, line = tile; w, h = size
    rgba16 = lambda v: (((v >> 11) & 31) * 255 // 31, ((v >> 6) & 31) * 255 // 31, ((v >> 1) & 31) * 255 // 31)
    tex = imgs[-1][2]
    pal = [rgba16(struct.unpack_from('>H', E, imgs[0][2] + 2 * i)[0]) for i in range(256)] if len(imgs) > 1 else None
    im = Image.new('RGB', (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            if fmt == 2 and siz == 0:
                b = E[tex + y * line + x // 2]; v = (b >> 4) if x % 2 == 0 else (b & 15); px[x, y] = pal[v]
            elif fmt == 2 and siz == 1:
                px[x, y] = pal[E[tex + y * line + x]]
            elif fmt == 0 and siz == 2:
                px[x, y] = rgba16(struct.unpack_from('>H', E, tex + y * line + 2 * x)[0])
            elif fmt == 4 and siz == 1:                 # I8
                v = E[tex + y * line + x]; px[x, y] = (v, v, v)
            elif fmt == 4 and siz == 0:                 # I4
                b = E[tex + y * line + x // 2]; v = ((b >> 4) if x % 2 == 0 else (b & 15)) * 17; px[x, y] = (v, v, v)
            elif fmt == 3 and siz == 1:                 # IA8
                v = (E[tex + y * line + x] >> 4) * 17; px[x, y] = (v, v, v)
            elif fmt == 3 and siz == 0:                 # IA4
                b = E[tex + y * line + x // 2]; v = (((b >> 4) if x % 2 == 0 else (b & 15)) >> 1) * 36; px[x, y] = (v, v, v)
            elif fmt == 3 and siz == 2:                 # IA16
                v = E[tex + y * line + 2 * x]; px[x, y] = (v, v, v)
            else:
                return None
    return im


def atlas(E, items, out, cell=96):
    items = list(items.items())
    cols = 8; rows = (len(items) + cols - 1) // cols
    A = Image.new('RGB', (cols * cell, rows * (cell + 14)), (20, 20, 20)); d = ImageDraw.Draw(A)
    for k, (label, tr) in enumerate(items):
        x, y = (k % cols) * cell, (k // cols) * (cell + 14)
        im = decode(E, tr)
        if im: A.paste(im.resize((cell - 4, cell - 4), Image.NEAREST), (x + 2, y + 2))
        d.text((x + 3, y + cell), str(label), fill=(255, 255, 0))
    A.save(out)
