"""Game-side helpers for harness scripts: boot to a level, player and target lookups.

Carousel index (level select): 0 Battle of Hoth, 1 Escape from Echo Base, 2 Asteroid Field,
3 Ord Mantell Junkyard, 4 Gall Spaceport, 5 Mos Eisley & Beggar's Canyon,
6 Imperial Freighter Suprosa, 7 Sewers of Imperial City, 8 Xizor's Palace, 9 Skyhook Battle.
"""
import ctypes as C, math, struct
from m64 import BTN, tag

PAD = 0x80113098                  # s16 stick x, s16 stick y, u32 buttons at +0x14
LEVEL_ID = 0x8013CE0E             # u16, current level
DLG_GATE = 0x800DEB78             # float > 0 while a message box freezes input
TARGET_POOL = 0x80112838          # +8 count, +12 stride, +16 base; record +0x98 -> object
PROFILES = 0x8018BBF8             # 4 save profiles, 0x7A bytes each, u16 level flags at +0x60
CAM = 0x800D08A4                  # -> active camera: forward +0x24, eye +0x44 (floats x, y, z)
TRAIN_CARS = 0x80112F28           # Trai class array: +8 count, +12 stride, +16 base; car axis +0x30
HUMN_HP, HUMT_HP = 0xB4, 0xC0     # player health (float): Humn on foot, HumT on the train
HUMN_YAW, HUMT_YAW = 0x8C, 0x90   # yaw (float, degrees); facing = yaw + 90


def boot_events(level):
    """Frame-timed inputs from power-on (fresh EEPROM) to the start of a level.

    Title -> START x3 -> new profile (A, A) -> name entry (stick to "END", A) -> START ->
    level carousel (down x level) -> A through the briefing pages. Valid with e.unlimit()
    from frame 1 and unlock_levels() running during frames 1600-2900."""
    ev = [(1200, 'START', 0, 0, 6), (1500, 'START', 0, 0, 6), (1700, 'START', 0, 0, 6),
          (1950, 'A', 0, 0, 6), (2000, 'A', 0, 0, 6)]
    f = 2050
    for _ in range(4): ev.append((f, '', 0, -80, 6)); f += 25
    for _ in range(9): ev.append((f, '', 80, 0, 6)); f += 25
    ev.append((f + 20, 'A', 0, 0, 6)); f += 200
    ev.append((f, 'START', 0, 0, 6)); g = f + 200
    for _ in range(level): ev.append((g, '', 0, -80, 8)); g += 50
    ev += [(g + 60, 'A', 0, 0, 6), (g + 310, 'A', 0, 0, 6), (g + 560, 'A', 0, 0, 6), (g + 810, 'A', 0, 0, 6)]
    return ev, g + 1200            # events, frame by which the level has loaded


def play_events(e, ev, n):
    b = x = y = 0
    for f0, name, sx, sy, d in ev:
        if f0 <= n < f0 + d:
            if name: b |= BTN[name]
            x += sx; y += sy
    e.pad(b, x, y)


def unlock_levels(e):
    """Mark all levels of all profiles as reached (RAM only; the carousel reads these)."""
    for p in range(4):
        base = PROFILES + p * 0x7A
        for l in range(10):
            ad = base + 0x60 + l * 2
            w = e.r32(ad & ~3)
            e.w32(ad & ~3, (w & 0xFFFF0000) | 1 if ad & 2 else (w & 0xFFFF) | 0x10000)


def targets(e, player, max_dist=400.0):
    """Live targetable objects from the game's own pool: [(dist, obj, tag)] nearest first."""
    cnt, sd, base = e.r32(TARGET_POOL + 8), e.r32(TARGET_POOL + 12), e.r32(TARGET_POOL + 16)
    out = []
    if not 0 < cnt < 1024:
        return out
    px, py = e.rf(player + 0x50), e.rf(player + 0x54)
    for i in range(cnt):
        r = base + i * sd
        ob = e.r32(r + 0x98)
        if not 0x80000000 <= ob < 0x80800000 or not e.r16(r + 0x68) & 2 or not e.r32(r + 0x84):
            continue
        t = tag(e.r32(ob))
        if not e.r16(ob + 6) & 2 or not e.rf(ob + 0x60) > 0 or t in ('Boxx', 'Anim', 'Boss', 'Humn', 'HumT'):
            continue
        d = math.hypot(e.rf(ob + 0x50) - px, e.rf(ob + 0x54) - py)
        if d < max_dist:
            out.append((d, ob, t))
    return sorted(out)


def is_train(e, player):
    return tag(e.r32(player)) == 'HumT'


def set_health(e, player, v=100.0):
    e.wf(player + (HUMT_HP if is_train(e, player) else HUMN_HP), v)


def facing(e, player):
    """Facing in degrees, -180..180."""
    return (e.rf(player + (HUMT_YAW if is_train(e, player) else HUMN_YAW)) + 270) % 360 - 180


def find_player(e):
    """Dash's object without the payload's g_player: scan RAM for a live Humn/HumT."""
    raw = C.string_at(e.rdram(), 0x800000)
    for t in (b'Humn', b'HumT'):
        tw = struct.pack('<I', struct.unpack('>I', t)[0])
        i = raw.find(tw)
        while i >= 0:
            a = 0x80000000 + i
            if i % 4 == 0 and a > 0x80150000 and e.r32(a + 4) in (7, 0x47) and 1 < abs(e.rf(a + 0x50)) < 5000:
                return a
            i = raw.find(tw, i + 1)
    return 0


def pool_objects(e):
    """[(record, object)] of every entry in the game's target pool, alive or not."""
    cnt, sd, base = e.r32(TARGET_POOL + 8), e.r32(TARGET_POOL + 12), e.r32(TARGET_POOL + 16)
    out = []
    for i in range(cnt if 0 < cnt < 1024 else 0):
        r = base + i * sd
        ob = e.r32(r + 0x98)
        if 0x80000000 <= ob < 0x80800000:
            out.append((r, ob))
    return out
