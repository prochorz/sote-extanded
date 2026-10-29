"""Build the Gall Run image for the controls patch (feature `gallrun`): two stages, two levels.

    cd harness && M64CPU=0 .venv/bin/python3 gallrun/gall_asset.py <rom> [out.bin]
        (default local/game/gall_run.bin; needs numpy: the venv's python)

Stage 1: a canyon from stage 1's source (states/src_stage1.st, sub-level 17), the tiles east of
X_MIN (the canyon and the town's east); mesh_image.build_tiles: every tile is a 100x100
mesh under a transform node that turns it by a multiple of 90 degrees, the same mesh serves
several tiles. Route gallrun/stage1_route.pkl: the source's track backwards, from its end
to its start, low over the floor; the player steers the Falcon in a corridor round it.
Stage 2: the landscape of stage 2's source (states/src_stage2.st, sub-level 8), terrain only
(gallrun/stage2_route.py) drawn with Gall's textures (GALL_TEX, states/gall_tp5.st), route
gallrun/stage2_route.pkl: the source's track backwards, low over the ground.
place() turns and moves stage 2 so that its route starts where stage 1 ends, on the same heading;
gallrun.c draws stage 2 with that pose once the ship passes the switch node.
Both are drawn SCALE times wider and SCALE_Z times taller (stage 2 STAGE2 times more) (gallrun.c scales the node they hang
under), so a ship the Falcon's size fits (the source's canyon is ~45 wide, ~27 deep).

Layout at BASE: header {'GALL', stage 1 part count, part list, bounding box, route node count,
route struct, scale x/y (float), end node, scale z (float), stage 2 part count, part list, bounding
box, switch node, stage 2 pose: cos, sin, x, y, z (floats), corridor (+72), stage 2 extra scale
(float, +76: gallrun/stage2_route.py STAGE2), radio line count, line table (+80, +84: LINES), poke count,
poke table (+88, +92: (pointer, offset, value), gallrun.c pokes()), the offset of the word build.py makes a
ROM address (+96: Chewie's sample), opening shot key count and keys (+100, +104), stage 1's collision
(+108: gallrun/collide.py), stage 1's ceiling per route node (+112: s16 world units over the route,
collide.ceilings()), Slave I's mesh (+116: part count, part list, box: slave_pad.slave_mesh()), the scene at the
route's end (+128, +132: key count, keys: slave_pad.cine_keys()), Dash standing and on the jetpack (+136, +148: part
count, part list, box each: slave_pad.dash_mesh()), his node's scale (+160, float), the rail after the scene (+164,
+168: its first node, node count: slave_pad.cine_keys()), the space rocks' part count (+172: the last of stage 2's, 0: the Star Destroyer is the game's mesh,
space.py), Slave I's shots (+176: part count, part list, box: slave_pad.bolts()), an X-Wing and a TIE (+188, +200: part count, part
list, box each: space.fighter(); the TIE's 0: they keep the level's own), the Star Destroyer's middle and heading (+212: x, y, z, heading: space.star_destroyer()), the battle's middle (+228),
the engine glow (+240: part count, part list, box), the story's rail nodes (+252), the wall tops' part count (+264:
cliffs.caps(); in stage 2's list before the space rocks'), the Star Destroyer's collision (+268: collide.py's form, world),
the edge nodes (+272: one byte per route node, 1 where a flat ship does not fit: collide.edge_nodes(); 0 past stage 1), the jump's trail (+276: part count, part list, box: slave_pad.trail()),
Luke's portrait frames (+288, +292: count, sprite list: luke_frames(); gallrun.c luke_anim()),
Lando's and Leia's portraits (+296, +300: sprites, photo_face(); gallrun.c face() puts one into slot 38 as a line is said),
the space level's gun towers on the Star Destroyer (+304 count, +308 records {node, x, y, z, yaw}, +312 the PRBT template, +316 its
pool, +320 their group: space.towers(); gall_space.c towers_show(), towers_on()),
the towers' target panel (+324: turret_panel(); also a poke: slot 38 every frame), +328..+336 0 (the Falcon's copy for
Cut 05 once: gone, falcon.bin itself drawn there), the scenes' pictures (+340 Lando and Leia, +344 Luke, +348 a blank one: still.py), the Outrider as our level has it
for Cut 05 (+352: part count, part list, box: space.or_glow(); gall_chain.c), the hangars' mouths (+364 count, +368
records {x, y, z, out x, out y} floats: slave_pad.hangar_slot(); gall_ties.c hangar_launch(); one hangar, its parts
stage 2's; +372 0), Leebo's turn in Cut 05's frame 6 (+376 + 4 i, nine
sprite headers: the intro's sprites 15-23, still.copy_sprite(); gall_chain.c), the Falcon's colours in Cut 05 and the
last scene (+412: the table, space.falcon_colours(); falcon.c)},
then the mesh blocks
and records, then the route struct in the form Chor reads (route_struct(): both stages and LEAD
nodes before node 0), then the corridor: per route node s16 left, right, down, up (world units
the player may steer the Falcon off the route in stage 1, gallrun/stage1_route.py, up opened where no drawn rock is
over the node; in stage 2 only
left and right, the room gallrun.c banks the ship by, gallrun/stage2_route.py).
place() puts stage 2's ground level with stage 1's; its first BLEND nodes ease from the height
stage 1 ends at.
"""
import ctypes, json, math, os, pickle, struct, sys
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # harness/: m64
import paths
from m64 import Emu, HERE
from mesh_image import build_tiles
from stage2_route import terrain_tiles, landscape, warp, STAGE2
import cliffs, collide, hud_icon, layout, slave_pad, space, still

NODE, NODE_POS = 0x54, 0x38          # Chor's route struct (the base level, Station Chase): node size, position


def route_struct(nodes, lead=0):
    """Chor's route struct (docs/reverse-engineering.md, "Station Chase"): one 0x54-byte
    record per node, {next count, prev count, next[4] at +8, prev[4] at +0x20}, the position at
    +0x38 (that is, in the 0x38 bytes after the previous record's position) and a vector after it.
    The game keeps no node count. A closed loop (lead = 0) links the last node to node 0; an open
    route has its last `lead` nodes before node 0 (far one first): ... -> lead nodes -> 0 -> ... ->
    end, and the end node leads back to node 0 (the run is over before that)."""
    n = len(nodes)
    m = n - lead                                     # path nodes 0 .. m-1
    nxt = [i + 1 for i in range(n)]; prv = [i - 1 for i in range(n)]
    nxt[m - 1] = 0
    if lead:
        nxt[n - 1] = 0; prv[0] = n - 1; prv[m] = m - 1
    else:
        prv[0] = n - 1
    out = bytearray(n * NODE + NODE_POS)
    for i, (x, y, z) in enumerate(nodes):
        r = i * NODE
        struct.pack_into('>3I', out, r, 1, 1, nxt[i])
        struct.pack_into('>I', out, r + 0x20, prv[i])
        struct.pack_into('>6f', out, r + NODE_POS, x, y, z, 0.0, 0.0, 1.0)
    return bytes(out)


BASE = 0x80628000                 # build.py GALL_VRAM (clear of the game's words at 0x80600000)
LIMIT = 0x807C0000                # the payload
HEADER = 416
CAP_LOW = 2750.0                   # the wall tops round the rail's nodes lower than this over the route's end (gallrun.c
                                   # AST_SHOW + CANYON_GONE: above it the canyon is not drawn)
SCALE, SCALE_Z = 6.0, 9.0          # gallrun/stage1_route.py scales the route the same way
X_MIN = 850                       # tiles at x >= this (orig units, tile centres): the canyon, no town
# The opening shot flies in from the south, past stage 1's source's edge (just south of the start): the
# start tile again and again, each copy the previous one mirrored across their seam (north-south), so
# the canyon's walls meet with no gap (place -> (tile, mirrored); tile centres in level units).
EXTEND1 = {(1700, -400): ((1700, -300), True), (1700, -500): ((1700, -300), False), (1700, -600): ((1700, -300), True)}
TILES_OUT = os.path.join(paths.RUN, 'gall_tiles.json')   # the image's tiles (written by build(), for gall_map.py)
PLAN_OUT = os.path.join(paths.RUN, 'gall_plan.npz')   # both stages' cliff plan, world (written by build())
ROUTE1 = os.path.join(HERE, 'gallrun', 'stage1_route.pkl')    # stage 1, world
ROUTE2 = os.path.join(HERE, 'gallrun', 'stage2_route.pkl')    # stage 2, its source level's frame
STAGE1_END = 817                  # stage 1 is the route's nodes up to here (of stage1_route.pkl, before layout.py): it ends on the straight west
                                  # before the canyon turns north, where stage 2's cutting goes on (stage2_route GROOVE)
SEAM = 150.0                      # each stage keeps parts whose box centre is up to this far over the switch (world
                                  # units; parts are big: cut at 0 they left a gap)
# Radio lines, in order (gallrun.c lines()): (at, nodes from there, seconds after the previous line,
# portrait, text or None, sound id or -1). at: 'start' the run's start (the opening shot), 'slit' stage 1's first slit, 'switch' stage 2's first
# node. Portraits: -1 none, 'lando' / 'leia' their photos (photo_face(); the game has none), DASH_FACE Dash's face from the HUD
# (dash_face()), LUKE_FACE Luke (luke_frames(): Hoth's 8, animated). Texts: ~o the message colour, ~n a new line; short (the game draws every letter as a
# sprite: four long lines cost ~25% of the frame rate while shown, measured 2026-10-08). CHEWIE: Chewie's sound (chewie()).
STILLS = [('lando_leia_falcon.png', (0, 110, 1376, 712), 320),   # (the user's, 2026-10-19: the whole width, both in the
          ('luke_xwing.png', (0, 110, 1376, 712), 320)]        # frame, not panned; below the emulator's START button)
LUKE_EARLY = 45                    # Luke's warning this many nodes before the TIEs come in (at the bot's pace -90 to -50
                                   # took ~4 s: no time left for Dash's line, 2026-10-19)
TIES_IN = 90                       # gallrun.c TIES_IN: the TIEs come in this many nodes before the switch
GUNS_AT = 14                       # gallrun.c VIEW_AHEAD + 2: stage 1's control ends this many nodes before the switch
# (Dash's "Tight squeeze, Lando. Mind my paint!" is said by gallrun.c when he goes on edge into a slit
# with the Falcon right behind him.)
LINES = [('start', 0, 'intro', 'dash', "~h~oHere we go, boys.~nTry to keep up!", -1),   # the camera behind the Outrider
         ('switch', -TIES_IN - LUKE_EARLY, 0.5, 'luke', "~h~oSome of them got past!~nThey're heading your way!", -1),   # (rows <= 24:
         ('switch', -TIES_IN, 0.5, 'dash', "~oTIEs! Nobody said~nanything about TIEs!", -1),   # the box) they come in (ties())
         ('switch', -65, 2.0, 'leia', "~h~oWe had a deal, Dash.~nStick to the plan!", -1),   # (>= 2 s after "TIEs!" even at full
                                                                          # boost; "Sorry!" still before the break-off)
         ('switch', -50, 0, 'dash', "~h~oSorry! I was paid to~nguide, not to shoot.", -1),   # he breaks off (OR_PEEL); this and Luke's held (the user, 2026-10-24)
         ('switch', -GUNS_AT, 0, 'lando', "~h~oSo much for our guide!~nHang on, Chewie!~nGet on those guns!", -1),   # where stage 1's control ends
         ('switch', -GUNS_AT, 3.5, -1, None, 'chewie'),   # after the line is let go (2.5 s: too soon, 5 s: late, the user)
         # the scene at the route's end (slave_pad.cine_keys(); timed by CINE_LINES), each line held (~h: the scene stops
         # till a button, the user, 2026-10-14; cine() runs on frame_dt, 0 while held)
         ('end', 0, 0, 'lando', "~h~oLooks like~nwe're here.", -1),
         ('end', 0, 'cine', 'dash', "~h~oHi, folks! I warmed~nup the bird for you.", -1),
         ('end', 0, 'cine', 'leia', "~h~oDash...? Leebo, get~nthat scoundrel out of there!", -1),
         ('end', 0, 'cine', 'leebo', "~h~oAlready on it,~nPrincess.", -1),
         ('end', 0, 'cine', 'lando', "~oHe's running!~nAfter him, Chewie!", -1),   # not held: Slave I has gone past
         ('end', 0, 'cine', -1, None, 'chewie'),
         # said by gallrun.c itself (never by the table's turn), counted from the end (gallrun.c LINE_*): in space Dash
         # leaves (story()), the Falcon closes in, Slave I jumps; the gunner fires at Slave I (Han is in it)
         ('never', 0, 0, 'lando', "~oDash, you coward!~nSome friend you are.", -1),   # as the gunner's view comes back
                                                                          # after Dash's jump (story(); not held: the fight goes on)
         ('never', 0, 0, 'luke', "~h~oWe lost Han... Falcon, take~nout that Destroyer's guns~nwhile we keep the fighters~nbusy!", -1),   # by the battle (gallrun.c
         ('never', 0, 0, 'lando', "~oWe're leaving~nthe atmosphere!", -1),   # finale()); the sky half way to black (ATMO_SAY)
         ('never', 0, 0, 'dash', "~oHey, I'm on~nyour side!", -1),   # the gunner hits the Outrider (gallrun.c or_friendly():
         ('never', 0, 0, 'dash', "~oWe're on the~nsame side!", -1),   # Hoth's pilots' lines, in turn)
         ('never', 0, 0, 'dash', "~h~oSorry, Lando. This job's~ngetting too expensive!", -1),   # (~h: holds the game till a button)
         ('never', 0, 0, 'lando', "~oWe're right on~nhis tail, Chewie!", -1),
         ('never', 0, 0, 'lando', "~h~oNo...! He's gone~nto lightspeed.", -1),
         ('never', 0, 0, 'leia', "~oDon't shoot!~nHan's on board!", -1)]
LEEBO_FACE = 30                    # the base level's sprite slot 30: Leebo's portrait (the game has no Leia, no Lando)
LUKE_FACE = 29                     # Luke's portrait: empty in the base level; frame 0 of luke_frames() (gallrun.c animates it)
# Dash's portrait: made from his face in the HUD of the levels on foot (dash_face()), put in the
# The base level's sprite table (at SPRITES) at DASH_FACE (a free slot).
SPRITES, PLAY_FACE, PLAY_PORTRAIT, DASH_FACE = 0x8013CE2C, 9, 30, 36
HUD_ICON = 25                   # the ship HUD's icon (the Outrider from above): the Falcon (hud_icon.py)
FACE_BOX, FACE_SIZE, FACE_GAMMA = (3, 3, 32, 36), 44, 0.8   # x0, y0, x1, y1 of the face inside its frame
FACE_LANDO, FACE_LEIA = 0x100, 0x101   # gallrun.c face(): Lando's / Leia's sprite (+296 / +300) put into slot 38
PORTRAITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'portraits')
# photo_face(): (photo, box in the photo padded by pad px of its edge pixels, pad, inner box of the 44x44 its range is
# taken from or None: all, gamma); chosen on previews by the user (2026-10-18)
LANDO_FACE = ('lando.jpg', (242, 76, 448, 281), 0, (8, 8, 36, 40), 0.7)
LEIA_FACE = ('leia.jpg', (129, 140, 809, 820), 120, None, 0.8)
LEEBO_TURN = range(15, 24)       # the intro's (sub-level 0, states/src_intro.st) Leebo overlays: 15 the patch over the
                                  # still's own head, 16-23 his head turning
INTRO_SPRITES = 0x8013CE2C        # (the scene's HUD sprite table pointer)
HOTH_FRAMES = range(20, 28)        # Hoth's (states/src_portrait.st) HUD sprite slots: Luke in his helmet, 8 frames of interference
HOTH_BOX = (1, 0, 42, 44)          # the picture in each (x0, y0, x1, y1): its grey frame left out
# Chewie: gallrun/chewie.wav (16-bit mono 22050 Hz: Jedi Academy's sound/chars/chewbacca/07chw003.mp3
# from assets0.pk3, loudness-normalised; neither version of SotE has a Wookiee), VADPCM, added to the sound bank (global,
# BANKFILE) as sound CHEWIE after its 131 (one instrument; the slot after its sound list is free).
CHEWIE_WAV = os.path.join(HERE, 'gallrun', 'chewie.wav')
CHEWIE_GAIN = 2.5                 # chewie(): the roar this much louder, soft-limited (tanh)
BANKFILE, CHEWIE, LIKE = 0x80108C80, 131, 99      # LIKE: the sound whose envelope and key map it shares
LEAD = 2                          # gallrun/stage1_route.py LEAD
# Both stages' part boxes (mesh_image: the game leaves a part out when its box is out of the view) are
# made this big: with the stages drawn larger (6x/9x, stage 2 13.5x) the game dropped rock in plain
# view (whole pieces vanished and came back; stage 1's too: a wall at the start of stage 2, 2026-10-08);
# drawing all of it costs no frame rate (measured).
NOCULL = 1e5
BLEND = 25                        # stage 2 nodes over which the height joins stage 1's
SMOOTH1 = 15.0                    # stage 1's route heights eased over this many nodes (sigma)
SMOOTH1_XY = 1.5                  # and its plan over this many (the old stage 1 route zigzagged, ~10 deg a node, 112
                                  # left-right flips: the Falcon's assist, the camera and the Outrider jerked, the user;
                                  # 6 flips left, nodes moved 13 at most at 95%); the last SMOOTH1_KEEP held (stage 2
SMOOTH1_KEEP = 6                  # joins there; eased in and out over as many)
SMOOTH1_START = 10                # the first held too (the opening shot is set on them: INTRO_AHEAD)
MERGE = 25                        # parts joined per material and 25x25 cell of a tile (mesh_image)


def dump_ram(rom, states, at=10):
    """RAM of each savestate, loaded one after the other in one emulator session (one a process: the core
    starts once), `at` frames after its load ({state: frames} per state: a posed model 2, before it moves on)."""
    out = []
    e = Emu(rom)

    def script(e, n):
        k, f = divmod(n - 60, 20)
        if n < 60: return
        if f == 0: e.load_state(os.path.join(paths.STATES, states[k]))
        if k < len(states) and f == (at.get(states[k], 10) if isinstance(at, dict) else at):
            raw = ctypes.string_at(e.rdram(), 0x800000)
            out.append(b''.join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4)))
            if len(out) == len(states): e.stop()
    e.run(script)
    return out


def level_tiles(E):
    """(mesh, rotation, translation) of every tile: the child group of the world root with the
    most transform nodes, each holding one mesh."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    F = lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]
    root = R(0x8013CE24)
    kids = lambda g: [R(R(g + 0x10) + 4 * i) for i in range(R(g + 0xC))]
    groups = [g for g in kids(root) if R(g) >> 28 == 5]
    group = max(groups, key=lambda g: sum(R(t) >> 28 == 0xD for t in kids(g)))
    tiles = []
    for t in kids(group):
        if R(t) >> 28 != 0xD or R(t + 0xC) != 1: continue
        mesh = R(R(t + 0x10))
        assert R(mesh) >> 28 == 3, f'tile {t:08x} holds no mesh'
        tiles.append((mesh, [F(t + 0x14 + 4 * j) for j in range(9)], [F(t + 0x38 + 4 * j) for j in range(3)]))
    return tiles


def place(s1, s2, g1, g2, k=0):
    """Turn (about z) and move stage 2 so that it starts where stage 1 ends, its node k on stage 1's
    last heading (k: the cutting's east mouth, stage2_route anchor; the way in before it, a tile put
    between the stages, does not turn it), its ground (g2) level with stage 1's (g1 under its last).
    Returns (cos, sin, translation) and stage 2 in world coordinates."""
    s1, s2 = np.array(s1), np.array(s2)
    h1, h2 = s1[-1] - s1[-2], s2[k + 1] - s2[k]
    a = math.atan2(h1[1], h1[0]) - math.atan2(h2[1], h2[0])
    c, s = math.cos(a), math.sin(a)
    rot = lambda p: np.array([c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]])
    t = s1[-1] - rot(s2[0])
    t[2] = g1 - g2
    return (c, s, t), [tuple(float(v) for v in rot(p) + t) for p in s2]


# Stage 2 in Gall's colours (states/gall_tp5.st, sub-level 14): stage 2's source's texture record ->
# Gall's (gallrun/tex_atlas.py): the rock and scrap heaps and the cuttings' walls -> Gall's tan rock, the moss and the grey
# ground -> its pale sandstone.
GALL_TEX = {0x801D5960: 0x801E1B28, 0x801D5970: 0x801E1B28, 0x801D5980: 0x801E1B28, 0x801D5A20: 0x801E1B28,
            0x801D5B20: 0x801E1B28, 0x801D5A00: 0x801E1B38, 0x801D59A0: 0x801E1B38}


# Stage 1 in Gall's colours too: the sand (0x801A7810, and with a rock edge 0x801A7B40, 0x801A7B70)
# -> Gall's pale sandstone, and so the pit in the south loop (its maw 0x801A7B00, teeth
# 0x801A7B10), whose parts are also flattened to the sand's level: plain ground, no creature.
# The canyon walls keep their own textures: Gall's rock was tried and rolled back (2026-10-12).
GALL_FLOOR = {t: 0x801E1B38 for t in (0x801A7810, 0x801A7B40, 0x801A7B70, 0x801A7B00, 0x801A7B10)}
PIT = {0x801A7B00, 0x801A7B10}     # its parts are flattened onto the sand: level ground
# The hut at the dead end where stage 1 starts (walls, roof, door): left out.
HUT = {0x801A7800, 0x801A7840, 0x801A78B0, 0x801A7860}
# The wall across the canyon closing that dead end (a part of the start tile, local y 21.6, full
# height): left out too, the canyon goes on south of the start for the opening shot (EXTEND1).
DEAD_END = {0x801B67CC}


def sprite_pixels(E, a, alpha=False):
    """RGB pixels (height x width x 3, 0..31) of a CI4 HUD sprite at a in RAM E: its bitmaps
    (width, height, buffer: rows of 8-byte units, odd rows with their 4-byte halves swapped as
    TMEM wants them) laid out left to right, row after row. alpha: also its TLUT's alpha bits."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    H = lambda a: struct.unpack_from('>h', E, a & 0x7FFFFF)[0]
    W, h, lut, nb, bm = H(a + 4), H(a + 6), R(a + 0x18), H(a + 0x1C), R(a + 0x24)
    pal = np.array([struct.unpack_from('>H', E, (lut & 0x7FFFFF) + 2 * k)[0] for k in range(16)])
    img, x, y, rh = np.zeros((h + 64, W + 64), int), 0, 0, 0
    for k in range(nb):
        w, hh, buf = H(bm + 8 * k), H(bm + 8 * k + 2), R(bm + 8 * k + 4)
        rb = (w + 15) // 16 * 8
        raw = bytearray(E[buf & 0x7FFFFF:(buf & 0x7FFFFF) + rb * hh])
        for r in range(1, hh, 2):
            for q in range(r * rb, (r + 1) * rb, 8): raw[q:q + 4], raw[q + 4:q + 8] = raw[q + 4:q + 8], raw[q:q + 4]
        px = np.frombuffer(bytes(raw), np.uint8)
        if x >= W: x, y = 0, y + rh
        img[y:y + hh, x:x + w] = np.stack([px >> 4, px & 15], 1).reshape(hh, rb * 2)[:, :w]
        x, rh = x + w, hh
    p = pal[img[:h, :W]]
    rgb = np.stack([p >> 11 & 31, p >> 6 & 31, p >> 1 & 31], -1)
    return (rgb, p & 1) if alpha else rgb


TURRET_PANEL = 38                  # the space level's target panel for its towers (states/src_space.st): its title "<the level's name> TURRET", 64x46
PANEL_TEMPLATE = 39                # the base level's (states/src_base.st) bomber panel: the same layout, its TLUT


def sprite_indices(E, a):
    """The colour indices (height x width) of a CI4 HUD sprite at a in RAM E (as sprite_pixels())."""
    H = lambda a: struct.unpack_from('>h', E, a & 0x7FFFFF)[0]
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    W, h, nb, bm = H(a + 4), H(a + 6), H(a + 0x1C), R(a + 0x24)
    img, x, y, rh = np.zeros((h + 64, W + 64), int), 0, 0, 0
    for k in range(nb):
        w, hh, buf = H(bm + 8 * k), H(bm + 8 * k + 2), R(bm + 8 * k + 4)
        rb = (w + 15) // 16 * 8
        raw = bytearray(E[buf & 0x7FFFFF:(buf & 0x7FFFFF) + rb * hh])
        for r in range(1, hh, 2):
            for q in range(r * rb, (r + 1) * rb, 8): raw[q:q + 4], raw[q + 4:q + 8] = raw[q + 4:q + 8], raw[q:q + 4]
        px = np.frombuffer(bytes(raw), np.uint8)
        if x >= W: x, y = 0, y + rh
        img[y:y + hh, x:x + w] = np.stack([px >> 4, px & 15], 1).reshape(hh, rb * 2)[:, :w]
        x, rh = x + w, hh
    return img[:h, :W]


def turret_panel(Es, Ea, put):
    """The target panel the game shows for a gun tower (slot 38, gall_space.c's towers on the Star Destroyer):
    the space level's (RAM Es), its title's first word (the level's name) taken off and the rest moved to its place, its indices
    mapped by colour onto the base level's bomber panel's TLUT (RAM Ea: the game draws a panel by its indices), packed
    in a copy of that sprite. Copied with put(bytes) -> address; returns the sprite's."""
    R = lambda E, a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    H = lambda E, a: struct.unpack_from('>h', E, a & 0x7FFFFF)[0]
    lut = lambda E, a: [struct.unpack_from('>H', E, (R(E, a + 0x18) & 0x7FFFFF) + 2 * k)[0] for k in range(16)]
    src, tpl = R(Es, R(Es, SPRITES) + 4 * TURRET_PANEL), R(Ea, R(Ea, SPRITES) + 4 * PANEL_TEMPLATE)
    assert (H(Es, src + 4), H(Es, src + 6)) == (H(Ea, tpl + 4), H(Ea, tpl + 6)) == (64, 46), 'not the panels we know'
    idx = sprite_indices(Es, src)
    ls, la = lut(Es, src), lut(Ea, tpl)
    grey = lambda c: (c >> 11 & 31) + (c >> 6 & 31) + (c >> 1 & 31)
    to = [0] + [min(range(1, 16), key=lambda j: abs(grey(la[j]) - grey(ls[i])) if la[j] else 999) for i in range(1, 16)]
    idx = np.array(to)[idx]
    title = idx[:7]                                   # (the title's letters: rows 1..5; the frame from row 8)
    cols = [x for x in range(idx.shape[1]) if title[:, x].any()]
    gap = next(x for x in cols if x + 1 < idx.shape[1] and not title[:, x + 1:x + 4].any())   # end of the first word
    rest = next(x for x in cols if x > gap)
    title[:, cols[0]:] = np.concatenate([title[:, rest:], np.zeros((7, rest - cols[0]), int)], 1)[:, :idx.shape[1] - cols[0]]
    bm, nb = R(Ea, tpl + 0x24), H(Ea, tpl + 0x1C)
    y, bms = 0, b''
    for k in range(nb):
        w, hh = H(Ea, bm + 8 * k), H(Ea, bm + 8 * k + 2)
        rb = (w + 15) // 16 * 8
        rows = np.zeros((hh, rb * 2), int); rows[:, :w] = idx[y:y + hh, :w]
        raw = bytearray(((rows[:, 0::2] << 4) | rows[:, 1::2]).astype(np.uint8).tobytes())
        for r in range(1, hh, 2):
            for q in range(r * rb, (r + 1) * rb, 8): raw[q:q + 4], raw[q + 4:q + 8] = raw[q + 4:q + 8], raw[q:q + 4]
        bms += struct.pack('>hhI', w, hh, put(bytes(raw))); y += hh
    head = bytearray(Ea[tpl & 0x7FFFFF:(tpl & 0x7FFFFF) + 0x28])
    struct.pack_into('>I', head, 0x18, put(b''.join(struct.pack('>H', c) for c in la)))
    struct.pack_into('>I', head, 0x24, put(bms))
    return put(bytes(head))


def dash_face(E, put):
    """Dash's portrait for the radio messages, made in RAM E of a level on foot (states/src_model.st):
    the inside of his HUD face (PLAY_FACE, FACE_BOX: no blue frame) as greys (the game tints
    portraits green), FACE_SIZE square at the left of a 64-wide CI4 picture like Leebo's portrait
    (PLAY_PORTRAIT: its sprite, two bitmaps 64x32 and 64x12, taken as the template): face_sprite().
    Copied with put(bytes) -> address; returns the sprite's."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    return face_sprite(E, sprite_pixels(E, R(R(SPRITES) + 4 * PLAY_FACE)), FACE_BOX, R(R(SPRITES) + 4 * PLAY_PORTRAIT), put)


def luke_frames(E, Et, put):
    """Luke's radio portrait, animated as on Hoth: Hoth's HUD sprite slots 20-27 (RAM E of states/src_portrait.st: Luke in his
    pilot's helmet, 64x44 CI4, the picture 44x44; Hoth's HUD shows one a frame per 2 draws, in a loop, 0x80089C28)
    made as Dash's: the base level draws a portrait by its indices (a copied TLUT shows as noise), so each becomes
    FACE_SIZE greys by luminance (face_sprite()) under one contrast range for all 8 (each its own range flickered),
    not smoothed (the interference lines are the animation). The template is Leebo's portrait in RAM Et of
    states/src_model.st (as Dash's). Copied with put(bytes) -> address; returns the 8 sprites' addresses."""
    from PIL import Image
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    H = lambda a: struct.unpack_from('>h', E, a & 0x7FFFFF)[0]
    R2 = lambda a: struct.unpack_from('>I', Et, a & 0x7FFFFF)[0]
    sprites = [R(R(SPRITES) + 4 * i) for i in HOTH_FRAMES]
    for t in sprites: assert t and (H(t + 4), H(t + 6), H(t + 0x1C)) == (64, 44, 2), 'not the Hoth frames we know'
    px = [sprite_pixels(E, t) for t in sprites]
    x0, y0, x1, y1 = HOTH_BOX
    lums = [np.asarray(Image.fromarray((0.3 * p[y0:y1, x0:x1, 0] + 0.59 * p[y0:y1, x0:x1, 1] + 0.11 * p[y0:y1, x0:x1, 2])
                                       .astype(np.float32)).resize((FACE_SIZE, FACE_SIZE), Image.BILINEAR)) for p in px]
    rng = tuple(np.percentile(np.concatenate([l.ravel() for l in lums]), (2, 98)))
    tpl = R2(R2(SPRITES) + 4 * PLAY_PORTRAIT)
    return [face_sprite(Et, p, HOTH_BOX, tpl, put, rng=rng) for p in px]


def photo_face(spec, Et, put):
    """A radio portrait from a photo (Lando's, Leia's: LANDO_FACE, LEIA_FACE in PORTRAITS): padded by its edge pixels,
    cropped, its luminance to FACE_SIZE square with the range of the inner box (Lando: his face, the background bright)
    or of all, then face_sprite() with Leebo's portrait (RAM Et of states/src_model.st) as the template. Returns the sprite."""
    from PIL import Image
    name, box, pad, inner, gamma = spec
    rgb = np.asarray(Image.open(os.path.join(PORTRAITS, name)).convert('RGB')).astype(float)
    if pad: rgb = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
    x0, y0, x1, y1 = box
    lum = 0.3 * rgb[y0:y1, x0:x1, 0] + 0.59 * rgb[y0:y1, x0:x1, 1] + 0.11 * rgb[y0:y1, x0:x1, 2]
    lum = np.asarray(Image.fromarray(lum.astype(np.float32)).resize((FACE_SIZE, FACE_SIZE), Image.BILINEAR))
    r = lum if inner is None else lum[inner[1]:inner[3], inner[0]:inner[2]]
    rng = tuple(np.percentile(r, (2, 98)))
    R2 = lambda a: struct.unpack_from('>I', Et, a & 0x7FFFFF)[0]
    return face_sprite(Et, rgb, box, R2(R2(SPRITES) + 4 * PLAY_PORTRAIT), put, rng=rng, gamma=gamma)


def face_sprite(E, rgb, box, t, put, smooth=False, stretch_y=0, rng=None, gamma=FACE_GAMMA):
    """A portrait sprite from the box (x0, y0, x1, y1) of RGB pixels rgb: its luminance scaled to FACE_SIZE square
    (bilinear: no pixel noise), contrast stretched (2-98 % to the full range), gamma (FACE_GAMMA), as indices 1..15
    under a grey TLUT (0 transparent: the rest of the picture), at the left of template sprite t's picture (in RAM E:
    64 wide, full-width CI4 strips; its header copied). smooth: a 3x3 median first (a dithered picture); stretch_y:
    the stretch's percentiles from that row of the square down; rng: (lo, hi) given instead (frames of one animation)."""
    from PIL import Image, ImageFilter
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    H = lambda a: struct.unpack_from('>h', E, a & 0x7FFFFF)[0]
    x0, y0, x1, y1 = box
    rgb = rgb[y0:y1, x0:x1].astype(float)
    lum = 0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]
    if smooth: lum = np.asarray(Image.fromarray((lum * 8).astype(np.uint8)).filter(ImageFilter.MedianFilter(3))) / 8.0
    lum = np.asarray(Image.fromarray(lum.astype(np.float32)).resize((FACE_SIZE, FACE_SIZE), Image.BILINEAR))
    lo, hi = rng if rng else (np.percentile(lum[stretch_y:], 2), np.percentile(lum[stretch_y:], 98))
    v = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1) ** gamma
    W, h, nb, bm = H(t + 4), H(t + 6), H(t + 0x1C), R(t + 0x24)
    idx = np.zeros((h, W), np.uint8); idx[:FACE_SIZE, :FACE_SIZE] = 1 + np.round(v * 14)   # 0: transparent (the rest)
    bms, y = bytearray(), 0
    for k in range(nb):
        w, hh = H(bm + 8 * k), H(bm + 8 * k + 2)
        assert w == W, 'the template portrait is not in full-width strips'
        rows = idx[y:y + hh]; y += hh
        raw = bytearray((rows[:, 0::2] << 4 | rows[:, 1::2]).astype(np.uint8).tobytes())
        rb = W // 2
        for r in range(1, hh, 2):              # odd rows: 4-byte halves swapped (as TMEM wants them; once)
            for q in range(r * rb, (r + 1) * rb, 8): raw[q:q + 4], raw[q + 4:q + 8] = raw[q + 4:q + 8], raw[q:q + 4]
        bms += struct.pack('>hhI', w, hh, put(bytes(raw)))
    lut = bytes(2) + b''.join(struct.pack('>H', (g << 11) | (g << 6) | (g << 1) | 1) for g in (round(31 * k / 14) for k in range(15)))
    sp = bytearray(E[t & 0x7FFFFF:(t & 0x7FFFFF) + 0x30])
    struct.pack_into('>I', sp, 0x18, put(lut))
    struct.pack_into('>I', sp, 0x24, put(bytes(bms)))
    sp[0x28:0x30] = bytes(8)
    return put(bytes(sp))


def chewie(E, put):
    """Chewie's sound (CHEWIE_WAV) for the sound bank in RAM E: the VADPCM sample, its book, wave
    table and sound (LIKE's envelope, key map and pan / volume) copied with put(). Returns (the
    sound's address, the address of the wave table's base: an image offset build.py makes a ROM
    address, the instrument)."""
    import wave
    from vadpcm import encode
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    assert R(BANKFILE) >> 16 == 0x4231, 'no sound bank file at BANKFILE'
    ins = R(R(BANKFILE + 4) + 12)
    assert R(ins + 12) & 0xFFFF == CHEWIE and R(ins + 16 + 4 * CHEWIE) == 0, 'not the bank we know'
    w = wave.open(CHEWIE_WAV)
    assert w.getnchannels() == 1 and w.getsampwidth() == 2
    a = np.frombuffer(w.readframes(w.getnframes()), '<i2') / 32768.0     # louder (it was ~10 dB under the
    a = np.tanh(a * CHEWIE_GAIN) / np.tanh(CHEWIE_GAIN) * 0.95            # stage 2 battle): soft-limited
    book, data = encode(np.round(a * 32767).astype('<i2'))
    like = R(ins + 16 + 4 * LIKE)
    bk = put(struct.pack('>ii', 2, 1) + b''.join(struct.pack('>8h', *r) for r in book[0]))
    smp = put(data)
    wt = put(struct.pack('>IiBBxxII', smp, len(data), 0, 1, 0, bk))
    snd = bytearray(E[like & 0x7FFFFF:(like & 0x7FFFFF) + 16]); struct.pack_into('>I', snd, 8, wt)
    print('chewie: LIKE sample volume', snd[13], '->', 127)
    snd[13] = 127                                              # ALSound sampleVolume: full
    return put(bytes(snd)), wt, ins


# The opening shot (gallrun.c intro()): nothing stops. The Outrider and the Falcon fly straight in
# along the route at the run's speed (INTRO_V), high, and dive into the canyon over the bridge
# before the start, the Falcon reaching its place on the route as the run starts (it holds Chor
# still until then). The camera flies backwards just ahead of the Outrider's cockpit, then circles
# the ship (INTRO_ORBIT, by its cockpit's side) to behind it as Dash talks, falls back behind it;
# the Falcon overtakes it slowly overhead, belly to the camera, and the camera comes down behind
# the Falcon where the run's camera sits. Times in seconds; places in world units off Chor's, as
# (along the route, right, up).
INTRO_STEP = 0.05
INTRO_END = 4.0         # (the level fades in over the first 0.7: gallrun.c FADE_HOLD + FADE_IN)
INTRO_V = 300.0         # the run's speed (gallrun.c SPEED, measured: world units a second)
INTRO_DIVE = -760.0     # the ships start down this far along (0: the Falcon's end place)
INTRO_BEAM = (-217.0, 80.0)   # the bridge across the canyon before the start: along, its top (up)
INTRO_CAM = (20.0, 6.0)   # the camera this far ahead of the Outrider's cockpit, this far over it (at the start)
INTRO_ORBIT = (2.0, 3.6, 28.0, 8.0)   # Dash's line, the orbit's end (seconds), then behind the ship's middle (back, up)
INTRO_PULL = (0.4, 2.0, 36.0, 12.0)    # the camera backs off the cockpit (seconds), to this far off the middle, this high
INTRO_SIDE = (48.0, 12.0)              # beside the ship (half way round): this far off its middle, this high
INTRO_TURN = 1.0                       # the camera starts round the ship (seconds)
INTRO_COCKPIT = (5.0, 24.0, 2.0)   # the Outrider's cockpit off its middle (forward, right, up): it looks there
INTRO_OR_DIVE = (-1000.0, 18.0, -70.0)   # the Outrider: starts down this far along, over the bridge by this, at run height from here
INTRO_HIGH = (140.0, 160.0)   # the Outrider's, the Falcon's height over its run height at the start (was 260, 290: too high)
INTRO_FALCON_UP = (700.0, 2.4, 3.6)   # the Falcon flies this much higher (out of the fly-by), back down between these seconds
INTRO_FLY = (1.1, 2.2, 150.0, 34.0, 22.0)   # fly-by (intro_keys): the Outrider by the camera at (s), the camera eases
                                            # into the run's from (s), the ships' speed by it, the camera right of, over
                                            # the Outrider at the pass (Station Chase: 34, -19 at 46 units/s, scaled 1.5)
INTRO_FALCON = (1.85, 450.0, 20.0, 0.75, 1.1)    # fly-by: the Falcon over the camera at (s); hidden this high, this far over the camera
                                             # over its line at the pass; comes down between these seconds
INTRO_OR_HIGH = (55.0, 1.3, 2.2)         # fly-by: the Outrider this high over its line, down into the canyon between (s)
INTRO_TAIL = (40.0, 12.0, 1.55)        # fly-by: the camera behind the Outrider's tail: this far back, this high, at (s)
INTRO_RAMP = 1.4                         # the ships speed up from here to the run's speed at the end
INTRO_LINE = 0.7                         # Dash's line (s)
INTRO_PASS, INTRO_BUMP, INTRO_BUMP_FROM, INTRO_LOOK_W = 4.15, 150.0, 1.5, 0.45   # the Falcon over the camera at (seconds); how far ahead it flies
                                                       # (bump, set in intro_keys to pass then); the look's half window (s)
INTRO_LOOK_UP = 0.6     # the look turns this far from the Outrider to the Falcon as it passes over
INTRO_LOOK_LAG = 0.3    # fly-by: the look is up most this long after the Falcon is over the camera (it comes out ahead)
INTRO_CAM_V = 95.0      # fly-by: the camera's speed along as the Falcon passes over it (slower past it: it looks big)
OR_AHEAD, SHIP_DROP, VIEW_BACK, VIEW_UP = 6.5, 10.0, 70.0, 22.0   # gallrun.c: 1 + OR_AHEAD nodes; the run's camera
FLY_R_W, FLY_R_H = 15.0, 5.0       # gallrun.c: the ship's half width, half height (collide.edge_nodes(): + EDGE_ROOM across)
EDGE_ROOM = 2.0
INTRO_AHEAD = 198.0     # the Outrider's place ahead of the Falcon's at the run's start (checked in intro_keys)


def intro_keys_orbit(path):
    """The opening shot before 2026-10-08's fly-by (camera round the Outrider): keys as intro_keys()."""
    from scipy.interpolate import PchipInterpolator as pchip
    P = np.array(path); C = P[1]
    D = P[1] - P[0]; D[2] = 0; D /= np.linalg.norm(D)
    R = np.array([D[1], -D[0], 0.0]); U = np.array([0.0, 0.0, 1.0])
    w = lambda d, r, u: d * D + r * R + u * U
    k = int(OR_AHEAD); f = OR_AHEAD - k
    Of = P[k] + (P[k + 1] - P[k]) * f - (0, 0, SHIP_DROP) - C     # where the run puts the Outrider
    ahead = Of @ D
    assert abs(ahead - INTRO_AHEAD) < 2, ahead
    T = INTRO_END
    # height by distance along: high, down over the bridge, level at the end
    d0, over_b, low_at = INTRO_OR_DIVE                 # the Outrider dives sooner and steeper than the Falcon
    hO = pchip([-5000, d0, INTRO_BEAM[0], low_at, 1000], [INTRO_HIGH[0], INTRO_HIGH[0] - 8, INTRO_BEAM[1] * layout.WALL_UP + over_b, 0, 0])
    hF = pchip([-5000, INTRO_DIVE, INTRO_BEAM[0], 0, 1000], [INTRO_HIGH[1], INTRO_HIGH[1] - 8, INTRO_BEAM[1] * layout.WALL_UP + 38, 0, 0])
    sO = lambda t: ahead - INTRO_V * (T - t)
    # the Falcon ahead of a steady flight by a bump (zero, with zero slope, at the start and at T: it ends
    # in its route place at the run's speed), so it overtakes the camera at INTRO_PASS, slower than the run
    ta, A = INTRO_BUMP_FROM, INTRO_BUMP
    bump = lambda t: A * np.sin(np.pi * min(max((t - ta) / (T - ta), 0), 1)) ** 2
    sF = lambda t: -INTRO_V * (T - t) + bump(t)
    O = lambda t: Of + w(sO(t) - ahead, 0, float(hO(sO(t))))
    sm0 = lambda x: x * x * (3 - 2 * x)
    up_f, u0, u1 = INTRO_FALCON_UP
    F = lambda t: w(sF(t), 0, float(hF(sF(t))) + up_f * (1 - sm0(min(max((t - u0) / (u1 - u0), 0), 1))))
    sm = lambda x: x * x * (3 - 2 * x)
    cf, cr, cu = INTRO_COCKPIT
    cockpit = lambda t: O(t) + w(cf, cr, cu)
    near, over_c = INTRO_CAM
    t0, t1, back1, up1 = INTRO_ORBIT
    p0, p1, rho1, z1 = INTRO_PULL
    side, zs = INTRO_SIDE
    clamp = lambda x: min(max(x, 0.0), 1.0)
    # one curve round the ship's middle (angle 0 ahead, pi/2 its cockpit's side, pi behind), all eased
    # in and out: backing off the cockpit shows more of the hull, then round it to fill the view behind
    tm = (p1 + t1) / 2
    rho = pchip([-1, p0, p1, tm, t1, t1 + 1], [near, near, rho1, side, back1, back1])
    hz = pchip([-1, p0, p1, tm, t1, t1 + 1], [cu + over_c, cu + over_c, z1, zs, up1, up1])
    mid = lambda t: sm(clamp((t - p0) / (p1 + 0.5 - p0)))     # the circle's middle: the cockpit, then the ship's
    def eye(t):
        th = np.pi * sm(clamp((t - INTRO_TURN) / (t1 - INTRO_TURN)))
        m = 1 - mid(t)
        r = float(rho(t))
        return O(t) + w(cf * m + r * np.cos(th), cr * m + r * np.sin(th), float(hz(t)))
    Ef = w(-VIEW_BACK, 0, VIEW_UP); Lf = Ef + w(2 * VIEW_BACK, 0, -VIEW_UP)
    sc = lambda t: (t - t1) / (T - t1)
    b1 = ahead + VIEW_BACK
    back = lambda x: back1 + (b1 - back1) * sm(x)    # eased: no stop in mid-air; the Falcon overtakes it on the way
    e1 = eye(t1)
    P = (INTRO_PASS - t1) / (T - t1)                # the Falcon over the camera: s at INTRO_PASS
    over = pchip([0, P, 1.0], [e1 @ U - hF(e1 @ D), -30, VIEW_UP - hF(-VIEW_BACK)])
    keys = []
    for t in np.arange(0, T + 1e-6, INTRO_STEP):
        o = O(t)
        if t < t1:                                      # off its cockpit, then round it to behind it
            q = mid(t)
            e, look = eye(t), cockpit(t) * (1 - q) + o * q
        else:                                           # falling back, down behind the Falcon
            s = sc(t); d = sO(t) - back(s)
            e = w(d, 0, float(hF(d) + over(s)))
            m = sm(min(max((t - (T - 1.0)) / 1.0, 0), 1))
            up = INTRO_LOOK_UP * np.sin(np.pi * min(max((s - P + INTRO_LOOK_W) / (2 * INTRO_LOOK_W), 0), 1)) ** 2   # at its belly as it passes
            look = (o * (1 - up) + F(t) * up) * (1 - m) + Lf * m
        fs = sF(t)
        pitch = np.arctan2(hF(fs) - hF(fs + 1), 1.0)
        keys.append(struct.pack('>17f', float(t), *e, *look, *o, *F(t), float(pitch), 0.0, 0.0, 0.0))
    end = np.array(struct.unpack('>17f', keys[-1]))
    assert np.allclose(end[1:4], Ef, atol=0.5) and np.allclose(end[10:13], 0, atol=0.5), end
    return b''.join(keys), len(keys)


def intro_keys(path):
    """The opening shot's keys (gallrun.c KEY_SIZE: seconds, eye, look, Outrider, Falcon, the first
    three off Chor's place while it is held: the route's node 1 (its spline starts at the lead,
    intro() puts it at the spline's start), the Falcon off it, the Falcon's pitch and roll, the
    Outrider's roll, the Falcon's yaw), every INTRO_STEP.
    A fly-by after Station Chase's own level start (measured there):
    the camera stands still beside the canyon floor, a little below the ships' line, and turns after
    the Outrider as it comes at it, passes close (INTRO_FLY: right, up of it at the pass) and flies
    on; then the camera eases into the run's camera behind the Falcon. The ships fly slowly past the
    camera and speed up to the run's speed by the end (they end in their run places)."""
    P = np.array(path); C = P[1]
    D = P[1] - P[0]; D[2] = 0; D /= np.linalg.norm(D)
    R = np.array([D[1], -D[0], 0.0]); U = np.array([0.0, 0.0, 1.0])
    w = lambda d, r, u: d * D + r * R + u * U
    k = int(OR_AHEAD); f = OR_AHEAD - k
    Of = P[k] + (P[k + 1] - P[k]) * f - (0, 0, SHIP_DROP) - C     # where the run puts the Outrider
    ahead = Of @ D
    assert abs(ahead - INTRO_AHEAD) < 2, ahead
    T = INTRO_END
    t_pass, t_blend, v_pass, cam_r, cam_u = INTRO_FLY
    sm = lambda x: x * x * (3 - 2 * x)
    clamp = lambda x: min(max(x, 0.0), 1.0)
    # the ships' speed: v_pass, then up to the run's speed by T (eased); along = the end place less the rest
    dt = 0.001
    tt = np.arange(0, T + dt / 2, dt)
    v = v_pass + (INTRO_V - v_pass) * np.array([sm(clamp((t - INTRO_RAMP) / (T - INTRO_RAMP))) for t in tt])
    rest = np.concatenate([np.cumsum(((v[1:] + v[:-1]) / 2 * dt)[::-1])[::-1], [0.0]])   # distance still to fly
    along = lambda t, end: end - float(np.interp(t, tt, rest))
    oh, od0, od1 = INTRO_OR_HIGH                                 # the Outrider high over the canyon, into it
    O = lambda t: Of + w(along(t, ahead) - ahead, 0, oh * (1 - sm(clamp((t - od0) / (od1 - od0)))))   # once past
    cam = Of + w(along(t_pass, ahead) - ahead, cam_r, oh + cam_u)   # where the camera stands (over the Outrider)
    vO = lambda t: (along(t + 0.005, ahead) - along(t - 0.005, ahead)) / 0.01
    Oz = lambda t: (O(t) - Of) @ U
    herm = lambda x, p0, v0, p1, v1, dt_: ((2 * x**3 - 3 * x**2 + 1) * p0 + (x**3 - 2 * x**2 + x) * v0 * dt_
                                           + (-2 * x**3 + 3 * x**2) * p1 + (x**3 - x**2) * v1 * dt_)
    # once the Outrider is past, the camera drops in right behind it (a close shot of its tail, at t_lock),
    # then lets it go: slows to INTRO_CAM_V, where the Falcon passes over it
    t_fp, hide, clear, d0, d1 = INTRO_FALCON
    lb, lu, t_lock = INTRO_TAIL
    a0, h0 = along(t_pass, ahead), oh + cam_u
    a1, v1, h1 = along(t_lock, ahead) - lb, vO(t_lock), Oz(t_lock) + lu
    a2 = a1 + (v1 + INTRO_CAM_V) * (t_fp - t_lock) / 2
    def cam_at(t):
        if t <= t_pass: return cam
        if t <= t_lock:
            x = (t - t_pass) / (t_lock - t_pass); u = sm(x)
            return Of + w(herm(x, a0, 0.0, a1, v1, t_lock - t_pass) - ahead, cam_r * (1 - u), h0 + (h1 - h0) * u)
        x = clamp((t - t_lock) / (t_fp - t_lock))
        return Of + w(herm(x, a1, v1, a2, INTRO_CAM_V, t_fp - t_lock) - ahead, 0, h1)
    stop = cam_at(t_fp)
    # the player must think he flies the Outrider: the Falcon stays high out of view while the camera
    # watches the Outrider, comes down behind the camera once it looks ahead, passes right over it (on
    # its line, its belly to it, slowly) at t_fp and drops back to its run place, the camera chasing it
    ca, fz0 = stop @ D, stop @ U + clear
    g0 = along(t_fp, ahead) - ca                                 # the gap that puts it over the camera then
    ease = lambda t: sm(clamp((t - t_fp) / (T - t_fp)))
    sF = lambda t: along(t, ahead) - (g0 + (ahead - g0) * ease(t))
    Fr = lambda t: (stop @ R) * (1 - ease(t))
    # down to `clear` over the camera (it follows the camera's height: never through it as it drops behind the tail)
    Fz = lambda t: hide + (cam_at(t) @ U + clear - hide) * sm(clamp((t - d0) / (d1 - d0))) if t < t_fp else fz0 * (1 - ease(t))
    F = lambda t: w(sF(t), Fr(t), Fz(t))
    run_eye = lambda t: w(sF(t) - VIEW_BACK, 0, VIEW_UP)       # the run's camera behind the Falcon
    run_look = lambda t: run_eye(t) + w(2 * VIEW_BACK, 0, -VIEW_UP)
    lw = INTRO_LOOK_W                                            # the look up at the Falcon as it passes
    look_up = lambda t: INTRO_LOOK_UP * np.sin(np.pi * clamp((t - t_fp - INTRO_LOOK_LAG + lw) / (2 * lw))) ** 2
    # the chase: from INTRO_CAM_V under the Falcon the camera goes after it at once and settles into
    # the run's camera by the end (Hermite along the route: INTRO_CAM_V at the pass, the run's speed at the end)
    dtc = T - t_fp
    vF = (sF(T) - sF(T - 0.01)) / 0.01
    def chase(t):
        x = (t - t_fp) / dtc
        a = herm(x, ca, INTRO_CAM_V, sF(T) - VIEW_BACK, vF, dtc)
        u = sm(x)
        return w(a, (stop @ R) * (1 - u), (stop @ U) * (1 - u) + VIEW_UP * u)
    keys = []
    for t in np.arange(0, T + 1e-6, INTRO_STEP):
        o = O(t)
        q = sm(clamp((t - t_blend) / (T - t_blend)))
        e = chase(t) if t > t_fp else cam_at(t)
        up = look_up(t)
        look = (o * (1 - up) + F(t) * up) * (1 - q) + run_look(t) * q
        pitch = np.arctan2(Fz(t) - Fz(t + 0.05), sF(t + 0.05) - sF(t))
        pitch = 0.0 if t < t_fp else min(max(pitch, -0.2), 0.2)   # level as it drops in out of view: nose down, its hull hung through the camera
        keys.append(struct.pack('>17f', float(t), *e, *look, *o, *F(t), float(pitch), 0.0, 0.0, 0.0))
    end = np.array(struct.unpack('>17f', keys[-1]))
    Ef = w(-VIEW_BACK, 0, VIEW_UP)
    assert np.allclose(end[1:4], Ef, atol=0.5) and np.allclose(end[10:13], 0, atol=0.5), end
    return b''.join(keys), len(keys)


def build(E1, E2, Eg, Ep, Ea, E6b, Eds, Edj, Esky, Ehoth, Elt):
    R = lambda a: struct.unpack_from('>I', E1, a & 0x7FFFFF)[0]
    assert R(0x8013CE0C) & 0xFFFF == 17, 'src_stage1.st is not the stage 1 source (sub-level 17)'
    tiles1 = [t for t in level_tiles(E1) if t[2][0] >= X_MIN]
    at1 = {(round(t[0]), round(t[1])): (mesh, m, t) for mesh, m, t in tiles1}
    for (x, y), (src, mirror) in EXTEND1.items():
        mesh, m, t = at1[src]
        if mirror: m = [m[0], -m[1], m[2], m[3], -m[4], m[5], m[6], -m[7], m[8]]   # world y negated
        tiles1.append((mesh, m, [float(x), float(y), t[2]]))
    tiles2 = terrain_tiles(E2)
    land, sink = landscape(E2), pickle.load(open(ROUTE2, 'rb'))['sink']   # rock pressed down along the line
    assert struct.unpack_from('>I', Eg, 0x13CE0C)[0] & 0xFFFF == 14, 'gall_tp5.st is not Gall (sub-level 14)'
    R1 = lambda a: struct.unpack_from('>I', E1, a & 0x7FFFFF)[0]
    no_hut = lambda p, t: p not in DEAD_END and (not R1(p + 0x24) or R1(R1(p + 0x24) + 8) not in HUT)
    r1, r2 = pickle.load(open(ROUTE1, 'rb')), pickle.load(open(ROUTE2, 'rb'))
    r1, end1, tail = layout.route(r1, STAGE1_END)         # stage 1's tiles rearranged (gallrun/layout.py)
    tiles1 = layout.tiles(tiles1, tail)
    s1, s2 = r1['nodes'][:end1], r2['nodes']
    corridor = r1['corridor'][:end1] + r2['corridor'][1:]
    (c, s, t), s2w = place(s1, s2, min(r1['bottom'][end1 - 6:end1 + 5]), r2['ground'], r2['anchor'])   # stage 2's floor level
    # with the lowest ground round the switch (higher, its edge stood over stage 1's dip: sky under it)
    # The two stages stand one after the other (gallrun.c draws both round the switch): stage 1 without
    # its parts past the switch (the canyon it no longer flies), stage 2 without its parts before it.
    J = np.array(s1[-1][:2]); D = J - np.array(s1[-3][:2]); D /= np.linalg.norm(D)
    def past(E, tiles, to_world):
        """keep(p, t) -> how far past the switch (world units, along the heading there) the part's
        box centre is."""
        Rf = lambda a: struct.unpack_from('>3f', E, a & 0x7FFFFF)
        rot = {tuple(tt): m for _, m, tt in tiles}
        def f(p, tt):
            m = rot[tuple(tt)]
            cx, cy, cz = [(a + b) / 2 for a, b in zip(Rf(p), Rf(p + 12))]
            w = [cx * m[0 + j] + cy * m[3 + j] + cz * m[6 + j] + tt[j] for j in range(2)]
            return float((np.array(to_world(w)) - J) @ D)
        return f
    past1 = past(E1, tiles1, lambda w: (w[0] * SCALE, w[1] * SCALE))
    k2 = SCALE * STAGE2
    past2 = past(E2, tiles2, lambda w: (c * w[0] * k2 - s * w[1] * k2 + t[0], s * w[0] * k2 + c * w[1] * k2 + t[1]))
    keep1 = lambda p, tt: no_hut(p, tt) and past1(p, tt) <= SEAM
    keep2 = lambda p, tt: land(p) and past2(p, tt) >= -SEAM
    def drawn(E, tiles, keep):                  # tiles none of whose parts are drawn (past the switch...): left out
        Rr = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
        out = [(mesh, m, tt) for mesh, m, tt in tiles
               if any(keep(Rr(Rr(mesh + 0x10) + 4 * i), tt) for i in range(Rr(mesh + 0xC)))]
        print(f'tiles with nothing drawn, left out: {sorted((round(tt[0]), round(tt[1])) for _, _, tt in tiles if not any(x[2] is tt for x in out))}')
        return out
    flown = {(round(x / SCALE / 100) * 100, round(y / SCALE / 100) * 100) for x, y, _ in s1} | set(EXTEND1)
    off = [tt for _, _, tt in tiles1 if (round(tt[0]), round(tt[1])) not in flown]
    print(f'stage 1 tiles the route does not pass, left out: {sorted((round(tt[0]), round(tt[1])) for tt in off)}')
    tiles1 = [x for x in tiles1 if (round(x[2][0]), round(x[2][1])) in flown]
    tiles1, tiles2 = drawn(E1, tiles1, keep1), drawn(E2, tiles2, keep2)
    json.dump({'stage1': [[float(v) for v in tt[:2]] for _, _, tt in tiles1],
               'stage2': [[float(v) for v in tt[:2]] + [abs(m[0]) + abs(m[3]), abs(m[1]) + abs(m[4])] for _, m, tt in tiles2]},
              open(TILES_OUT, 'w'))            # (gall_map.py's grid: the tiles the image has)
    # Both stages are Gall's cliffs (gallrun/cliffs.py): stage 1's tiles and stage 2's terrain give only the
    # walls' plan (and stage 1 the ground the ship skims: collision only); no floor is drawn, the cliffs go down
    # into the haze. One plan for both (world units, stage 2 turned and placed), the faces then split at the switch.
    old, (h1o,) = build_tiles([(E1, tiles1, keep1, (Eg, GALL_FLOOR, PIT), lambda X, Y, Z: Z * layout.WALL_UP)],
                              BASE, header=HEADER, cell=MERGE)
    To, No = collide.world(collide.extract(old, BASE, h1o['parts'], h1o['list']), SCALE, SCALE_Z)
    old, (h2o,) = build_tiles([(E2, tiles2, keep2, (Eg, GALL_TEX), warp(sink))], BASE, header=HEADER, cell=MERGE)
    k2, kz2 = SCALE * STAGE2, SCALE_Z * STAGE2
    To2, No2 = collide.world(collide.extract(old, BASE, h2o['parts'], h2o['list']), k2, kz2)
    to_world = lambda P: np.stack([c * P[..., 0] - s * P[..., 1] + t[0], s * P[..., 0] + c * P[..., 1] + t[1], P[..., 2] + t[2]], -1)
    To2, No2 = to_world(To2), np.stack([c * No2[:, 0] - s * No2[:, 1], s * No2[:, 0] + c * No2[:, 1], No2[:, 2]], -1)
    img = bytearray(HEADER)
    import mesh_image; mesh_image.TEX_SHARE = {}   # (one copy of each texture in this image)
    SZ = []; mark = lambda n: SZ.append((n, len(img)))   # (the image's blocks' sizes, printed at the end)
    mark('header')
    # Stage 1's heights followed the old floor's bumps (up to 24 a node); with no floor drawn the route is eased
    # (the user: smooth). The cliffs' plan still reads the old heights (path_plan): the walls stay where they were.
    P1 = np.array(s1, float); s1_wind = [tuple(map(float, p)) for p in P1]   # (how much it winds: the old way's)
    xy = gaussian_filter1d(P1[:, :2], SMOOTH1_XY, axis=0, mode='nearest')
    i = np.arange(len(P1)); w = np.clip(np.minimum((i - SMOOTH1_START) / SMOOTH1_KEEP, (len(P1) - 1 - i) / SMOOTH1_KEEP), 0, 1)[:, None]
    P1[:, :2] += (xy - P1[:, :2]) * w
    s1_raw = [tuple(map(float, p)) for p in P1]  # (the plan: the eased way, the old heights)
    z1 = gaussian_filter1d(P1[:, 2], SMOOTH1, mode='nearest')
    s1 = [(float(x), float(y), float(z)) for (x, y, _), z in zip(P1, z1)]
    jump = s1[-1][2] - s2w[0][2]                # stage 2 eases from stage 1's height to its own
    under = max(r2['low'][0] + t[2] - s1[-1][2], 0)   # stage 1 ends lower than stage 2 may fly: its floor
    s2w = [(x, y, max(z + jump * max(1 - i / BLEND, 0),       # limit eases in too (it stepped up a node)
                      r2['low'][i] + t[2] - under * max(1 - i / BLEND, 0))) for i, (x, y, z) in enumerate(s2w)]
    path = s1 + s2w[1:]
    pad = slave_pad.place(path)                 # Slave I's pad from Gall 6b, north of the old finish, and the
    ext = slave_pad.extend(path, pad)           # route on into it (from the old end node: its last 4 dropped)
    path = path[:len(path) - 3] + ext
    corridor = corridor[:len(path) - len(ext)] + [(slave_pad.EXT_WIDE,) * 2 + (0.0, 0.0)] * len(ext)
    wide = np.concatenate([cliffs.winding(s1_wind) * cliffs.WIDE, np.zeros(len(path) - len(ext) - len(s1)),
                           np.full(len(ext), slave_pad.EXT_WIDE)])
    path_plan = s1_raw + path[len(s1):]
    plan = cliffs.footprint(np.concatenate([To, To2]), np.concatenate([No, No2]), path_plan, corridor[:len(path)], wide,
                            discs=[slave_pad.clear(pad)])
    plan_old = dict(plan, rock=plan['rock'].copy())   # (D9: the plan with both hollows as before D8, whose walls'
    slave_pad.hangar_carve(plan_old, slave_pad.hangar_frames(E6b, pad, plan_old, slave_pad.HANGAR_AT_OLD))   # tops
    hangars = slave_pad.hangar_frames(E6b, pad, plan)   # and shades the cliffs keep) a Gall hangar in the cliffs by
    slave_pad.hangar_carve(plan, hangars)       # the shaft (the chase TIEs'): its hollow in the rock, only the mouth out
    print('hangars (mouth xy, facing, floor z):', [(tuple(fr['m'].round()), tuple(fr['o'].round(2)), round(fr['z'])) for fr in hangars])
    walls_old = cliffs.faces(cliffs.outlines(plan_old), path)   # (D9 / D11: the old plan's walls, and its tops below)
    quads = cliffs.faces(cliffs.outlines(plan), path, old=walls_old)
    walls = list(quads)                         # (the cliffs alone: their tops for cliffs.caps())
    quads += slave_pad.mesa(E6b, pad, pad['z'] + slave_pad.RIM_UNDER + cliffs.DEEP)   # the plateau round the shaft
    for fr in hangars: quads += slave_pad.hangar_rock(fr, pad['z'] + slave_pad.RIM_UNDER + cliffs.DEEP, walls)
    J = np.array(s1[-1][:2]); D = J - np.array(s1[-3][:2]); D /= np.linalg.norm(D)
    quads1, quads2 = cliffs.by_stage(quads, J, D)
    to_local = lambda x, y, z: (c * (x - t[0]) + s * (y - t[1]), -s * (x - t[0]) + c * (y - t[1]), z - t[2])
    quads2w = quads2                            # (world: stage 2's collision, for the free flight after the end)
    quads2 = [([to_local(*v) for v in vs], st, cs) for vs, st, cs in quads2]
    h1 = cliffs.mesh(img, BASE, quads1, Eg, SCALE, SCALE_Z); mark('stage 1 cliffs (mesh)')
    h2 = cliffs.mesh(img, BASE, quads2, Eg, k2, kz2); mark('stage 2 cliffs (mesh)')
    img += bytes(-len(img) % 16)                # the pad's parts join stage 2's (drawn by its node, its frame)
    blob, hp = slave_pad.mesh(E6b, BASE + len(img), pad, lambda x, y, z: (lambda l: (l[0] / k2, l[1] / k2, l[2] / kz2))(to_local(x, y, z)))
    img += blob; mark("Slave I's pad (6b)")
    img += bytes(-len(img) % 16)                # Slave I alone (its own node: gallrun.c slave())
    sblob, hs = slave_pad.slave_mesh(E6b, BASE + len(img))
    img += sblob; mark('Slave I')
    hh = []                                     # the hangar: its parts join stage 2's, as the pad's
    for fr in hangars:
        img += bytes(-len(img) % 16)
        hblob, h_ = slave_pad.hangar_mesh(E6b, BASE + len(img), fr, lambda x, y, z: (lambda l: (l[0] / k2, l[1] / k2, l[2] / kz2))(to_local(x, y, z)))
        img += hblob; hh.append(h_)
    hd = []                                     # Dash standing, Dash on the jetpack (gallrun.c dash())
    for Ed in (Eds, Edj):
        img += bytes(-len(img) % 16)
        dblob, h_ = slave_pad.dash_mesh(Ed, BASE + len(img)); img += dblob; hd.append(h_)
    mark('hangars + Dash (standing, jetpack)')
    img += bytes(-len(img) % 16)                # the jetpack's flame (the user): parts of his jetpack mesh
    fblob, fparts = slave_pad.jet_flame(Ea, BASE + len(img)); img += fblob
    olds = [struct.unpack_from('>I', img, hd[1]['list'] - BASE + 4 * i)[0] for i in range(hd[1]['parts'])]
    img += bytes(-len(img) % 16); hd[1]['list'] = BASE + len(img); hd[1]['parts'] += len(fparts)
    img += b''.join(struct.pack('>I', a) for a in olds + fparts)
    img += bytes(-len(img) % 16)                # Slave I's shots in the scene (the user: its fire seen)
    mark("Dash's jet flame"); bblob, hb = slave_pad.bolts(Ea, BASE + len(img)); img += bblob; mark("Slave I's bolts")
    img += bytes(-len(img) % 16)                # the battle by the Star Destroyer: an X-Wing, a TIE (space.py)
    xblob, hx = space.fighter(Esky, space.XWING_MESH, BASE + len(img)); img += xblob; mark('X-Wing (the space level)')
    img += bytes(-len(img) % 16)                # the Falcon's colours in Cut 05 and the last scene (falcon.c)
    fcol = BASE + len(img); img += space.falcon_colours(); mark('Falcon colours (Cut 05, the last scene)')
    img += bytes(-len(img) % 16)                # the Outrider in Cut 05, as our level has it (gall_chain.c)
    oblob, hog = space.or_glow(Ea, BASE + len(img)); img += oblob; mark("Outrider's glows (Cut 05)")
    print('Cut 05 Outrider (our level): lo', [round(v, 1) for v in hog['lo']], 'hi', [round(v, 1) for v in hog['hi']])
    stills = []                                 # the scenes' pictures (gall_chain.c; still.py): Lando and Leia, Luke
    for name, crop, sw in STILLS:
        img += bytes(-len(img) % 16)
        sblob, sat = still.still(os.path.join(HERE, 'gallrun', 'pictures', name), crop, BASE + len(img), w=sw)
        img += sblob; stills.append(sat)
    img += bytes(-len(img) % 16)
    sblob, sat = still.blank(BASE + len(img)); img += sblob; stills.append(sat)
    mark('stills (Lando+Leia, Luke, blank)')
    Rl = lambda a, f='>I': struct.unpack_from(f, Elt, a & 0x7FFFFF)[0]
    assert Rl(0x8013CE0C) & 0xFFFF == 0, 'src_intro.st is not the intro (sub-level 0)'
    leebo = []                                  # Leebo's turn in Cut 05's frame 6 (gall_chain.c leebo_turn(); still.copy_sprite())
    for k in LEEBO_TURN:
        img += bytes(-len(img) % 16)
        lblob, lat = still.copy_sprite(Elt, Rl(Rl(INTRO_SPRITES) + 4 * k), BASE + len(img)); img += lblob; leebo.append(lat)
    print('Leebo turn sprites:', ', '.join(f'{k}: {a:#x}' for k, a in zip(LEEBO_TURN, leebo)))
    mark('Leebo head overlays (9)')
    ht = dict(parts=0, list=0, box=0)          # (TIEs keep their own model: its LODs did not copy)
    olds = [struct.unpack_from('>I', img, h2['list'] - BASE + 4 * i)[0] for i in range(h2['parts'])]
    news = [struct.unpack_from('>I', img, hp['list'] - BASE + 4 * i)[0] for i in range(hp['parts'])]
    for h_ in hh: news += [struct.unpack_from('>I', img, h_['list'] - BASE + 4 * i)[0] for i in range(h_['parts'])]
    img += bytes(-len(img) % 16); h2['list'] = BASE + len(img); h2['parts'] += len(news)
    img += b''.join(struct.pack('>I', a) for a in olds + news)
    np.savez(PLAN_OUT, rock=plan['rock'], x0=plan['x0'], y0=plan['y0'], cell=plan['cell'], nodes=np.array(path))   # (to look at)
    for h in (h1, h2):                          # no part left out of the view (NOCULL): both stages
        for i in range(h['parts']):
            p = struct.unpack_from('>I', img, h['list'] - BASE + 4 * i)[0] - BASE
            struct.pack_into('>6f', img, p, *(-NOCULL,) * 3, *(NOCULL,) * 3)
    lead = [tuple(float(v) for v in np.array(path[0]) + (np.array(path[0]) - np.array(path[1])) * (LEAD - k))
            for k in range(LEAD)]
    ck, nck, rail = slave_pad.cine_keys(path, pad, E6b, len(ext))   # (the scene, and the rail on after it)
    rail = [tuple(float(v) for v in p) for p in rail]
    rail = space.straighten(rail, path[len(path) - 4][2])   # (the end node: gallrun.c g_alt; in space: one gentle bend to the Star Destroyer, not the canyon's)
    route = path + rail + lead
    ha = dict(list=[], n=0)                     # space's own parts: the last of stage 2's (no space rocks: they flew at
                                                # the Falcon, the user; the base level's belt backdrop stays)
    end_z = path[len(path) - 4][2]              # the wall tops round the rail (the user: walls edge-on from above):
    cap_rail = [p for p in rail if p[2] - end_z < CAP_LOW]
    tops = cliffs.by_stage(cliffs.caps(plan, cliffs.by_stage(walls, J, D)[1], cap_rail,
                                       old=cliffs.caps(plan_old, cliffs.by_stage(walls_old, J, D)[1], cap_rail)),
                           J, D)[1]                     # (stage 2's side only: stage 1 is not drawn on the rail)
    mark('stage 2 part list'); hc = cliffs.mesh(img, BASE, [([to_local(*v) for v in vs], st, cs) for vs, st, cs in tops], Eg, k2, kz2)
    olds = [struct.unpack_from('>I', img, h2['list'] - BASE + 4 * i)[0] for i in range(h2['parts'])]   # stage 2's,
    caps_ = [struct.unpack_from('>I', img, hc['list'] - BASE + 4 * i)[0] for i in range(hc['parts'])]   # before the
    img += bytes(-len(img) % 16); h2['list'] = BASE + len(img); h2['parts'] += hc['parts']   # space rocks' (gallrun.c
    img += b''.join(struct.pack('>I', a) for a in olds + caps_)   # show_stage(): from the end scene on, IMG_CAP_N)
    mark('wall tops (caps)')
    img += bytes(-len(img) % 16)                # the Star Destroyer by the rail's end: the game's own mesh drawn on a
    space_from = next(k for k, p in enumerate(rail) if p[2] - path[len(path) - 4][2] >= space.SPACE_AT)   # node of
    sblob_, sd_parts, sd_at, sd_head, bt_mid, story = space.star_destroyer(Ea, rail, BASE + len(img),      # ours
                                lambda x, y, z: (lambda l: (l[0] / k2, l[1] / k2, l[2] / kz2))(to_local(x, y, z)), space_from,
                                share=False)     # (gall_scene.c star_destroyer()): our copy is
    sd_img = bytes(img) + sblob_ + bytes(-len(sblob_) % 16)   # built only for its collision and the towers' spots,
    sd_list = BASE + len(sd_img); sd_img += b''.join(struct.pack('>I', a) for a in sd_parts)   # not kept in the image
    print('story rail nodes (Dash, closing, Slave I):', story, flush=True)
    mark('Star Destroyer (mesh)')
    img += bytes(-len(img) % 16)                # the Falcon's engine glow bent round its stern (gallrun.c glow())
    gblob, hg = space.glow_bent(Ea, BASE + len(img)); img += gblob; mark("Falcon's glow round its stern")
    img += bytes(-len(img) % 16)                # the white trail of a jump to lightspeed (gallrun.c trail())
    tblob, htr = slave_pad.trail(Ea, BASE + len(img)); img += tblob; mark('lightspeed trail')
    olds = [struct.unpack_from('>I', img, h2['list'] - BASE + 4 * i)[0] for i in range(h2['parts'])]
    img += bytes(-len(img) % 16); h2['list'] = BASE + len(img); h2['parts'] += ha['n']
    img += b''.join(struct.pack('>I', a) for a in olds + ha['list'])
    # (space's parts keep their own boxes: not culled, the Star Destroyer's big triangles across the camera's plane
    # were drawn as dark wedges over the view, the user)
    bb = b''.join(struct.pack('>hhhhhhhh', x, y, z, 0, 0, 0, 0, 0)   # stage 2's mesh box (8 vertices, s16 x8) as big as
                  for x in (-32767, 32767) for y in (-32767, 32767) for z in (-32767, 32767))   # it goes: the Star
    img[h2['box'] - BASE:h2['box'] - BASE + len(bb)] = bb   # Destroyer by the straightened rail's end lies far off the canyon;
                                                # looking out at it the whole mesh was culled (the user: not seen)
    img += bytes(-len(img) % 16)
    at = len(img)
    mark('part lists'); img += route_struct(route, lead=LEAD); mark('route')
    end = len(path) - 4                 # the spline reads 3 nodes ahead: stop while all are on the path
    img += bytes(-len(img) % 16)
    cor = len(img)
    corridor = corridor + [(999.0, 999.0, 0.0, 0.0)] * (len(route) + 64 - len(corridor))   # (gallrun.c reads ahead)
    img += b''.join(struct.pack('>4h', *(max(-32768, min(32767, int(round(v)))) for v in c)) for c in corridor)
    mark('corridor'); slit = next(i for i, c_ in enumerate(corridor) if c_[0] + c_[1] < 12)   # gallrun.c KNIFE_W
    def put(b):
        nonlocal img
        img += bytes(-len(img) % 16); a = BASE + len(img); img += b; return a
    texts = {text: put(text.encode() + b'\0') for *_, text, _ in LINES if text}
    mark('radio texts'); face = dash_face(Ep, put); mark("Dash's face")
    icon = hud_icon.falcon_icon(Ea, struct.unpack_from('>I', Ea, (struct.unpack_from('>I', Ea, SPRITES & 0x7FFFFF)[0] + 4 * HUD_ICON) & 0x7FFFFF)[0], put)
    mark('Falcon HUD icon'); lukes = luke_frames(Ehoth, Ep, put)
    luke, luke_list = lukes[0], put(b''.join(struct.pack('>I', a) for a in lukes))
    lando, leia = photo_face(LANDO_FACE, Ep, put), photo_face(LEIA_FACE, Ep, put)
    mark("Luke's frames, Lando's, Leia's faces"); panel = turret_panel(Esky, Ea, put)          # the towers' target panel (gallrun.c turret_panel())
    hrecs = put(slave_pad.hangar_slot(hangars))  # the hangars' mouths: the chase TIEs come out of them (gall_ties.c)
    mark('turret panel, hangar records'); snd, wt, ins = chewie(Ea, put)          # the bank as the run's level has it
    romfix = wt - BASE                          # build.py adds the image's ROM address to this word
    struct.pack_into('>I', img, romfix, struct.unpack_from('>I', img, romfix)[0] - BASE)
    mark("Chewie's roar (sound)")
    gaps = iter(np.diff(slave_pad.CINE_LINES))    # 'cine': the gap after the scene's line before (its own times)
    lines = put(b''.join(struct.pack('>IfIhh', max({'start': 0, 'slit': slit, 'switch': len(s1), 'end': end, 'never': 0x7FFFFFFF}[w] + d, 0),
                                     INTRO_LINE if f == 'intro' else float(next(gaps)) if f == 'cine' else f, texts.get(text, 0),
                                     DASH_FACE if who == 'dash' else LEEBO_FACE if who == 'leebo' else LUKE_FACE if who == 'luke' else FACE_LANDO if who == 'lando' else FACE_LEIA if who == 'leia' else who, CHEWIE if snd == 'chewie' else snd)
                         for w, d, f, who, text, snd in LINES))
    Ra = lambda a: struct.unpack_from('>I', Ea, a & 0x7FFFFF)[0]
    anchor = Ra(BANKFILE + 4) + 12              # holds the instrument's address
    R1i = Ra(ins + 12)
    pokes = [(SPRITES, 4 * DASH_FACE, face), (SPRITES, 4 * TURRET_PANEL, panel), (SPRITES, 4 * LUKE_FACE, luke), (SPRITES, 4 * HUD_ICON, icon),
             (anchor, 16 + 4 * CHEWIE, snd), (anchor, 12, (R1i & 0xFFFF0000) | (CHEWIE + 1))]
    pk = put(b''.join(struct.pack('>III', a, o, v) for a, o, v in pokes))
    mark('lines table, pokes'); ik, nk = intro_keys(s1)
    intro = put(ik)
    cine = put(ck)
    mark('opening shot + end scene keys')
    T, Nn = collide.world(collide.extract(img, BASE, h1['parts'], h1['list']), SCALE, SCALE_Z)   # stage 1's cliffs
    edge = collide.edge_nodes(T, Nn, s1, FLY_R_W + EDGE_ROOM, FLY_R_H, SHIP_DROP)   # where a flat ship does not fit
    edges = put(bytes(edge) + bytes(len(route) + 64 - len(edge)))   # (0 past stage 1; gallrun.c reads ahead)
    # (the old ground is out of it: its bumps; gallrun.c FLY_LOW holds the ship over the eased route instead)
    # Stage 2's cliffs and Slave I's pad too: after the route's end the player flies freely (gallrun.c free_fly)
    mark('edge nodes'); Tp, Np = collide.world(collide.extract(img, BASE, hp['parts'], hp['list']), k2, kz2)
    Tp, Np = to_world(Tp), np.stack([c * Np[:, 0] - s * Np[:, 1], s * Np[:, 0] + c * Np[:, 1], Np[:, 2]], -1)
    T2 = cliffs.tris(quads2w)
    n2 = np.cross(T2[:, 1] - T2[:, 0], T2[:, 2] - T2[:, 0]); n2 /= np.linalg.norm(n2, axis=1)[:, None]
    T, Nn = np.concatenate([T, T2, Tp]), np.concatenate([Nn, n2, Np])
    img += bytes(-len(img) % 16)
    coll, cinfo = collide.pack(T, Nn, BASE + len(img))
    coll = put(coll); mark('collision (both stages, pad)')
    # Stage 1's corridor "up" from the rock really drawn over the route: stage1_route.py made it
    # from stage 1's source's ceiling map, whose rock is not drawn here (lone 0s between nodes of 162 snapped the
    # Outrider's height and the camera's eye). A node with no drawn rock on the vertical line over it gets the open
    # top the rock-free nodes have (UP_MAX); one with rock over it keeps its value. (gallrun/corridor_up.py checks it.)
    up_open = max(c_[3] for c_ in corridor[:len(s1)])
    opened = []
    for k, (x, y, z) in enumerate(s1):
        if round(corridor[k][3]) < round(up_open) and not (collide.over(T, x, y) > z).any():
            opened.append(k); corridor[k] = tuple(corridor[k][:3]) + (up_open,)
            struct.pack_into('>h', img, cor + 8 * k + 6, int(round(up_open)))
    print(f'corridor up opened to {up_open:.0f} at {len(opened)} of {len(s1)} stage-1 nodes (no drawn rock over them); '
          f'kept (rock over): {sum(1 for k, (x, y, z) in enumerate(s1) if (collide.over(T, x, y) > z).any())}')
    Ts, Ns = collide.world(collide.extract(sd_img, BASE, len(sd_parts), sd_list), k2, kz2)
    Ts, Ns = to_world(Ts), np.stack([c * Ns[:, 0] - s * Ns[:, 1], s * Ns[:, 0] + c * Ns[:, 1], Ns[:, 2]], -1)
    out_ = np.sign(np.mean(np.einsum('ij,ij->i', Ts.mean(1) - np.asarray(sd_at), Ns)))   # (its drawn side: out of it)
    img += bytes(-len(img) % 16)                # the Star Destroyer's own collision (gallrun.c IMG_SD_COLL: the game's
    sdc, sinfo = collide.pack(Ts, Ns, BASE + len(img), flip=int(out_))   # needs the space level's sector record)
    sdc = put(sdc); mark('Star Destroyer collision')
    spots = space.tower_spots(Ts, sd_at, sd_head)  # the space level's gun towers on its top (gall_space.c towers_on())
    tblob_, tw = space.towers(Esky, spots, sd_head, BASE + len(img) + (-len(img) % 16))
    assert put(tblob_) == BASE + len(img) - len(tblob_); mark('towers (the space level)')
    print('towers:', [tuple(round(v) for v in p) for p in spots], flush=True)
    slit_nodes = [i for i in range(len(s1)) if corridor[i][0] + corridor[i][1] < 12]
    ceil = collide.ceilings(T, [tuple(p) for p in s1], slit_nodes)   # stage 1: how high the ship may fly
    roof = put(b''.join(struct.pack('>h', int(round(v))) for v in list(ceil) + [int(ceil[-1])] * 8))
    hdr = struct.pack('>4sIIIIIfIfIIIIfffffIfIIIIIIIIIIIIIIIIIIIIfIIIIIIIIIIIIfffffffIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII' + 'I' * len(LEEBO_TURN) + 'I', b'GALL', h1['parts'], h1['list'], h1['box'],
                                len(route), BASE + at, SCALE, end, SCALE_Z,
                                h2['parts'], h2['list'], h2['box'], len(s1), c, s, t[0], t[1], t[2], BASE + cor, STAGE2, len(LINES), lines, len(pokes), pk, romfix, nk, intro, coll, roof,
                      hs['parts'], hs['list'], hs['box'], nck, cine,
                      hd[0]['parts'], hd[0]['list'], hd[0]['box'], hd[1]['parts'], hd[1]['list'], hd[1]['box'],
                      slave_pad.K / slave_pad.DASH_FINE, len(path), len(rail), ha['n'], hb['parts'], hb['list'], hb['box'],
                      hx['parts'], hx['list'], hx['box'], ht['parts'], ht['list'], ht['box'], *sd_at, sd_head, *bt_mid, hg['parts'], hg['list'], hg['box'], *story, hc['parts'], sdc, edges,
                      htr['parts'], htr['list'], htr['box'], len(lukes), luke_list, lando, leia,
                      tw['count'], tw['recs'], tw['template'], tw['pool'], tw['group'], panel,
                      0, 0, 0, *stills, hog['parts'], hog['list'], hog['box'],
                      len(hangars), hrecs, 0, *leebo, fcol)
    assert len(hdr) == HEADER                  # a shorter slice would shift the whole image
    mark('ceilings')
    print('image blocks (bytes):'); prev = 0
    for n_, at_ in SZ: print(f'  {at_ - prev:8d}  {n_}'); prev = at_
    print(f'  {len(img):8d}  total')
    img[0:HEADER] = hdr
    print(f'textures: {len(mesh_image.TEX_SHARE)} copied once each'); mesh_image.TEX_SHARE = None
    img += bytes(-len(img) % 16)
    print(f'stage 1: {len(tiles1)} tiles, {h1["parts"]} parts, {len(s1)} nodes; '
          f'stage 2: {len(tiles2)} tiles, {h2["parts"]} parts ({hc["parts"]} of wall tops: {len(tops)} triangles), {len(s2)} nodes, '
          f'turned {math.degrees(math.atan2(s, c)):.0f} deg, moved {[round(v) for v in t]}; collision {cinfo}; Star Destroyer collision {sinfo}, drawn side {"out" if out_ > 0 else "in: flipped"}; '
          f'cliffs: {len(quads1)} + {len(quads2)} faces; Slave I\'s pad: {hp["parts"]} parts at node {pad["node"]}; '
          f'rail: {len(rail)} nodes; space rocks: {ha["n"]} parts')
    runs = np.flatnonzero(np.diff(np.concatenate([[0], edge, [0]])))
    print('edge nodes (runs):', ', '.join(f'{a}-{b - 1}' if b - 1 > a else f'{a}' for a, b in zip(runs[::2], runs[1::2])))
    print('pokes:', ', '.join(f'({a:#x}, {o} (slot {o // 4}), {v:#x})' if a == SPRITES else f'({a:#x}, {o}, {v:#x})' for a, o, v in pokes))
    return bytes(img)


if __name__ == '__main__':
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(paths.GAME, 'gall_run.bin')
    img = build(*dump_ram(sys.argv[1], ['src_stage1.st', 'src_stage2.st', 'gall_tp5.st', 'src_model.st', 'src_base.st', 'gall_6b.st', *slave_pad.DASH_STATES,
                                        'src_space.st', 'src_portrait.st', 'src_intro.st'], at={st: 2 for st in slave_pad.DASH_STATES}))
    assert BASE + len(img) <= LIMIT, 'image overlaps the payload'
    open(out, 'wb').write(img)
    print(f'{len(img)} bytes for {BASE:#x} -> {out}')
