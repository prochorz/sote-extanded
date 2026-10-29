"""Drive the game's debug menu (debug flag byte 0x800D098B) from a harness script.

The menu lives on the pause screen; D-pad right/left moves a cursor that is remembered between
pauses, A runs the entry. Items: 0 Get all stuff, 1 Invincibility, 2 Debug Display, 3 50 Lives,
4 Villains aren't sleepy, 5 Kill Dash, 6 Teleport, 7 Next Level, 8 This Level, 9 Prev Level, ...
The cursor is the s16 at 0x800D0990; set_cursor() puts it on an item directly.
The item under the cursor already runs when the pause screen opens, so set the cursor first.
Keep the flag on only around menu use (with the cursor on Next Level every pause skips ahead).
"""
from m64 import BTN

DEBUG_FLAG = 0x800D0988            # low byte of this word = 0x800D098B
CURSOR = 0x800D0990                # s16, upper half of this word
TELEPORT, NEXT_LEVEL = 6, 7


def set_debug(e, on):
    w = e.r32(DEBUG_FLAG)
    e.w32(DEBUG_FLAG, (w & 0xFFFFFF00) | (1 if on else 0))


def set_cursor(e, item):
    w = e.r32(CURSOR)
    e.w32(CURSOR, (w & 0xFFFF) | ((item & 0xFFFF) << 16))


def menu_events(start, moves, settle=40):
    """Inputs for: pause, move the cursor (`moves` > 0 right, < 0 left), A, unpause.
    Returns (events, end frame); events are (frame, button) pressed for 5 frames."""
    t = start
    ev = [(t, 'START')]; t += settle
    for _ in range(abs(moves)):
        ev.append((t, 'R_D' if moves > 0 else 'L_D')); t += 12
    ev.append((t + 8, 'A')); t += 48
    ev.append((t, 'START')); t += settle
    return ev, t


def pressed(ev, k):
    b = 0
    for f, name in ev:
        if f <= k < f + 5: b |= BTN[name]
    return b
