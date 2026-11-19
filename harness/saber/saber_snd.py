"""The saber's sounds (feature saber, saber.c) as one ROM blob: local/game/saber_snd.bin from the sound files in
local/game/saber_snd/ (git-ignored: your own files, never in git).

    ../.venv/bin/python3 saber/saber_snd.py [dir] [out.bin]      (numpy)

The files, by name (any format ffmpeg reads; the first match of <name>.*): on, hum (the loop), swing1, swing2, swing3,
deflect, hit, spin, off; in that order they are saber.c's sounds 0..8 (the bank's ids 0x83..0x8B). Each converted to
mono 16-bit big-endian at its RATE (ffmpeg), the game's raw16 wave type (ALWaveTable type 1: no encoder needed), played
at pitch rate / 44100 (build.py passes it per sound: SABER_SND_PITCH). The hum, the swings and the spin at 11025 Hz:
their energy above 5.5 kHz is 45..58 dB under the whole; on, deflect, hit and off keep 22050 Hz (-9..-13 dB there).

Trim: every sound but the hum (the loop) and the spin (no silence) starts 2 ms before its first sample over its peak
x 10^(TRIM_DB / 20) and ends 10 ms after its last one, faded out over the last 10 ms: the files' encoder lead-in
(30..54 ms) and their silent tails are not kept, so each sound starts that much sooner after its event.
The hum is resampled circularly: its 22050 Hz samples tiled three times, resampled as one stream, the middle third
kept (exactly half the samples), so the loop's seam is filtered against itself and does not click.

Layout: 'SSN2', count, per sound (offset from the blob's start, length in bytes, rate in Hz), then the samples, each
16-aligned. build.py appends it after the ROM's last blob and passes its ROM offset, the (offset, length) table and the
pitches to saber.c; with no blob the saber is silent. A missing file is an empty sound (length 0, rate 22050: saber.c
skips it).
"""
import glob, os, struct, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

NAMES = ['on', 'hum', 'swing1', 'swing2', 'swing3', 'deflect', 'hit', 'spin', 'off']
RATE = {'on': 22050, 'hum': 11025, 'swing1': 11025, 'swing2': 11025, 'swing3': 11025,
        'deflect': 22050, 'hit': 22050, 'spin': 11025, 'off': 22050}
SRC_RATE = 22050                # the hum's circular resample starts from this rate
NO_TRIM = ('hum', 'spin')       # the loop; the spin has no silence
TRIM_DB = -50                   # a sample counts as sound over its peak x 10^(TRIM_DB / 20)
HEAD_KEEP = 0.002               # s kept before the first such sample
TAIL_KEEP = 0.010               # s kept after the last one
FADE = 0.010                    # s faded out linearly at the end


def ffmpeg(args, data=None):
    return subprocess.run(['ffmpeg', '-v', 'error', *args], input=data, capture_output=True, check=True).stdout


def convert(path, rate):
    return np.frombuffer(ffmpeg(['-i', path, '-ac', '1', '-ar', str(rate), '-f', 's16be', '-']), '>i2')


def circular(path, rate):
    """The loop resampled against itself: three copies as one stream, the middle third kept."""
    s = convert(path, SRC_RATE)
    assert SRC_RATE % rate == 0 and len(s) * rate % SRC_RATE == 0, 'the loop must halve exactly'
    r = np.frombuffer(ffmpeg(['-f', 's16be', '-ar', str(SRC_RATE), '-ac', '1', '-i', '-', '-ar', str(rate),
                              '-f', 's16be', '-'], np.tile(s, 3).astype('>i2').tobytes()), '>i2')
    n = len(s) * rate // SRC_RATE
    return r[n:2 * n]


def trim(s, rate):
    a = np.abs(s.astype(np.int32))
    if not len(a) or not a.max(): return s
    on = np.nonzero(a > a.max() * 10 ** (TRIM_DB / 20))[0]
    i0 = max(0, on[0] - round(HEAD_KEEP * rate))
    i1 = min(len(s), on[-1] + 1 + round(TAIL_KEEP * rate))
    t = s[i0:i1].astype(np.float64)
    f = min(len(t), round(FADE * rate))
    t[len(t) - f:] *= np.linspace(1, 0, f)
    return np.round(t).astype('>i2'), i0 / rate, (len(s) - i1) / rate


def build(d):
    hdr = 8 + 12 * len(NAMES)
    out = bytearray(hdr + (-hdr % 16)); tab = []
    for n in NAMES:
        fs = sorted(glob.glob(os.path.join(d, n + '.*')))
        rate, cut = RATE[n], ''
        if not fs: data, rate = b'', 22050
        elif n == 'hum': data = circular(fs[0], rate).tobytes()
        elif n in NO_TRIM: data = convert(fs[0], rate).tobytes()
        else:
            s, h, t = trim(convert(fs[0], rate), rate)
            data, cut = s.tobytes(), f'  cut {h * 1000:5.1f} + {t * 1000:5.1f} ms'
        tab.append((len(out) if data else 0, len(data), rate))
        out += data + bytes(-len(data) % 16)
        print(f'{n:8s} {rate:5d} Hz {len(data):7d} bytes  {len(data) / 2 / rate:5.2f} s{cut}'
              + ('' if fs else '  (missing)'))
    struct.pack_into(f'>4sI{3 * len(NAMES)}I', out, 0, b'SSN2', len(NAMES), *(x for t in tab for x in t))
    print(f'samples {sum(t[1] for t in tab)} bytes')
    return bytes(out)


if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(paths.GAME, 'saber_snd')
    o = sys.argv[2] if len(sys.argv) > 2 else os.path.join(paths.GAME, 'saber_snd.bin')
    b = build(d)
    open(o, 'wb').write(b)
    print(f'wrote {o}: {len(b)} bytes')
