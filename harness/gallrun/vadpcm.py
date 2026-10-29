"""N64 VADPCM: encode 16-bit mono PCM for the game's sound player (libultra ALWaveTable type 0).

    book, data = encode(samples)       # samples: int16 numpy array
    pcm = decode(book, data)           # for checks

One predictor of order 2 (least squares over the whole sound); frames of 16 samples in 9 bytes
(a header byte: scale exponent << 4 | predictor, then 16 4-bit innovations), each frame's scale
picked by trying them all against the decoder's own state. book: the ALADPCMBook coefficients
(order x 8 per predictor, s16, 2048 = 1.0), as encode() returns them: [[row, row]].
"""
import numpy as np

ORDER = 2


def make_book(x):
    x = x.astype(np.float64)
    A = np.column_stack([x[1:-1], x[:-2]])
    a1, a2 = np.linalg.lstsq(A, x[2:], rcond=None)[0]

    def resp(p2, p1):                       # 8 outputs of the predictor after these two
        out = []
        for _ in range(8):
            v = a1 * p1 + a2 * p2; out.append(v); p2, p1 = p1, v
        return out
    rows = [resp(1.0, 0.0), resp(0.0, 1.0)]
    return [[[int(max(-32768, min(32767, round(v * 2048)))) for v in r] for r in rows]]


def _half(book, prev, ix):
    """8 outputs of one half frame: prev (x[-2], x[-1]), ix the 8 scaled innovations."""
    b0, b1 = book
    out = []
    for i in range(8):
        acc = b0[i] * prev[0] + b1[i] * prev[1] + (ix[i] << 11)
        for j in range(i): acc += b1[i - 1 - j] * ix[j]
        out.append(max(-32768, min(32767, acc >> 11)))
    return out


def encode(pcm):
    pcm = np.asarray(pcm, np.int16)
    pcm = np.concatenate([pcm, np.zeros(-len(pcm) % 16, np.int16)])
    book = make_book(pcm)
    b = book[0]
    prev, data = [0, 0], bytearray()
    for f in range(0, len(pcm), 16):
        x = [int(v) for v in pcm[f:f + 16]]
        best = None
        for e in range(13):
            s, p, nib, err, out = 1 << e, list(prev), [], 0, []
            for h in range(2):
                ix = []
                for i in range(8):
                    o = _half(b, p, ix + [0] * (8 - len(ix)))[i] if ix else _half(b, p, [0] * 8)[i]
                    q = max(-8, min(7, int(round((x[h * 8 + i] - o) / s))))
                    ix.append(q * s); nib.append(q)
                o8 = _half(b, p, ix)
                err += sum((a - c) ** 2 for a, c in zip(o8, x[h * 8:h * 8 + 8]))
                out += o8; p = o8[-2:]
            if best is None or err < best[0]: best = (err, e, nib, p)
            if err == 0: break
        _, e, nib, prev = best
        data.append(e << 4)
        for i in range(0, 16, 2): data.append(((nib[i] & 15) << 4) | (nib[i + 1] & 15))
    return book, bytes(data)


def decode(book, data):
    b, prev, out = book[0], [0, 0], []
    for f in range(0, len(data), 9):
        s = 1 << (data[f] >> 4)
        nib = []
        for c in data[f + 1:f + 9]:
            for v in (c >> 4, c & 15): nib.append((v - 16 if v > 7 else v) * s)
        for h in range(2):
            o = _half(b, prev, nib[h * 8:h * 8 + 8]); out += o; prev = o[-2:]
    return np.array(out, np.int16)
