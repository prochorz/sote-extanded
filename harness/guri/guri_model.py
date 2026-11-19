"""Generate the Guri model (Xizor's bodyguard as her action figure: golden hair, a red bodice and tabard over grey,
white gloves, a painted face) as glTF on her skeleton (the palace guard's with her own shoulders and hips, as the
blocks she plays on 33 carry them: her_skeleton), for the feature `guri` (sote-patch/src/guri.c draws her on one Trop).

    M64CPU=0 python3 guri/guri_model.py <rom> [out.gltf]      (default harness/guri/guri.gltf)
    GURI_CHECKER=1 ...   the face a checker (4 texel squares): checks the texture scale on the model
    GURI_RAM=<file>      read a palace.st RAM dump (big-endian, 8 MB) instead of running the emulator

From palace.st (sub-level 26) the guard's skeleton (Trop 0's `trSt` block, 17 bones) and, per bone, the box of its
near meshes in the bone's local frame (local units = vertex units / 8, guard_asset.py's). The glTF has one node per
bone, `bone_NN` (NN = the trSt index), parented as the guard's tree, translation = the bone node's +0x38 (her own on the
upper arms 12, 9 and the thighs 5, 2: her_skeleton), no rotation or scale; each bone's mesh sits on its node in that bone's frame. guri_asset.py converts it to the game's meshes.

The limbs, the left hand and the feet are Dash's own meshes (the right hand a closed fist of ours, FIST_RINGS; a
shoulder cap of ours over each arm's joint, SHOULDER_CAP) (dash_meshes: guard_asset.py's bake read the other way,
his meshes onto the guard's bones), their textures recoloured texel by texel by where on the model each texel lies
(texel_map, recolour): sleeves grey-blue with a red band below the shoulder, white gloves from mid-forearm and on the
hands, grey trousers, dark grey boots (shins and feet). His textures are CI8 / RGBA16: each comes out at 16 colours
(the converter's CI4). The head is ours (his, a man's long face and heavy jaw, read wrong on her): a smaller oval with a
soft jaw and a narrow chin (an ellipsoid with a low, flatter-rounded cranium, widest at the temples, fuller at the
back: a skull, not an egg; the head, face, relief and hair made by harness/pose/head_model.py), a slim neck, the face a 64 x 64 texture made from the photo of
her figure (face_src.png) wrapped round its front (face_texture), its features also as relief (FACE_RELIEF: a nose
that stands out in profile, the brow, sockets, lips and chin; a flat face read noseless, the user, 2026-11-07). (Procedural limbs and a painted ellipsoid head
looked like a nesting doll with hinged arms and stick legs, the user's word on the fifth look, 2026-11-07.)
Ours: every vertex inside the guard's per-bone box widened 30 % (the skirt's panels may hang below the pelvis and
thigh boxes, to mid-calf; Dash's meshes keep his shapes), <= 1600 triangles in all, the hair's fall MIN_FALL_CLEAR clear
of the bodice's back (check). His limbs slimmed across their bones (LIMB_SLIM). Torso: lofted rings (8-sided; the
chest 12), a woman's line (the bust the bodice's own form, BUST_PROFILE, its shade painted in, BUST_SHADE; a waist of
a real width, the sides running chest -> sash -> hips without a pinch; the hips wider; the shoulders over the upper
arms' tops), each lower segment ending inside the next: a red sleeveless bodice ending just inside the arms' tops, a shallow scoop at the neckline closed in the
turtleneck's grey, the dark-grey turtleneck round her neck up to the chin, a darker red sash. The skirt: a tabard's two red panels, front and back, split at the sides (the legs show through),
fitted on the hips with a slight flare to just above the knee, both sides drawn; the front's hem cut at an angle, each panel
in two halves split up the middle, one on each thigh (they swing with the legs), the closed hips above the slits on
the pelvis. Hair golden, parted in the middle (no fringe), long: a shell over the top fitted
round her head, from the back as wide as the fall (both sides drawn), framing the face (from the part over the temples,
down along the cheeks: its edge tucked to the skin) and round the head to the nape (head bone), then a shell down
the back to mid-back with a jagged hem (no locks in front of the shoulders: the user, 2026-11-07). The face's photo
gets her makeup (MAKEUP: lips, lids, a blush).
Unlit: the shade is baked into the vertex colours from one light (from above-front in each bone's frame; the hair
also from above-behind, so its back shades across; on Dash's meshes over white, the texture carries the colour). Front is local -y on every bone (the guard's visor part and toes lie at -y; a Trop's
draw matrix is Rz(180) of its heading).
"""
import io, math, os, struct, sys, types
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'pose'))
import gltf
import head_model
from head_model import Part, loft, two_sided

BONES = 17
# colours (RGB): each a base and its shade, unlit (x lo) .. lit (x hi)
RED = np.array((150, 30, 35))                # the bodice, the hips, the skirt's panels
SASH = RED * 0.8                             # the waistband, a shade darker
GREY = np.array((60, 64, 72))                # the turtleneck (collar and the V at the neckline)
SLEEVE = np.array((85, 95, 115))             # grey-blue sleeves
GLOVE = np.array((225, 225, 230))            # white gloves, hand to mid-forearm
TROUSERS = np.array((80, 85, 95))
SKIN = np.array((240, 198, 172))             # a warm light skin (her face and neck)
BOOT = TROUSERS * 0.6                        # boots, to below the knee (the shins and feet)
SHADE = {'skin': (0.6, 1.0), 'red': (0.68, 1.18), 'sash': (0.7, 1.15), 'grey': (0.75, 1.2), 'sleeve': (0.72, 1.15),
         'glove': (0.72, 1.0), 'trousers': (0.72, 1.15), 'boot': (0.72, 1.15)}
BASE = {'skin': SKIN, 'red': RED, 'sash': SASH, 'grey': GREY, 'sleeve': SLEEVE, 'glove': GLOVE, 'trousers': TROUSERS, 'boot': BOOT}
RED_IN = RED * 0.45                          # the skirt panels' inner side
HAIR = np.array((235, 175, 60))              # golden blonde
HAIR_NAPE = (-1.5, (1.0, 0.96))             # the head part's lower edge: z (head frame), x / y radii x the shell's
# the long fall on the chest bone: rows (z, rx, ry, y shift from the hair's centre), a shell round the back only (its
# sides tucked behind the head part: from the front no edge of it shows beside the neck), its top just outside the
# head part's lower edge at the back (as wide as the head; it covers that edge), widening, fuller, to mid-back (below the
# shoulder blades; a row at z 7.0 between); the
# last row a jagged hem (every other point FALL_JAG lower / higher: ragged ends)
HAIR_FALL = [(25.5, 7.15, 7.2, 0.0), (18.0, 8.47, 5.6, 1.9), (7.0, 8.56, 4.81, 2.45), (4.0, 8.58, 4.6, 2.6)]
FALL_TOP = (1.54, 0.23)                      # the fall's top row over the head part's lower edge: higher, wider by
FALL_ARC, FALL_JAG = (26.0, 154.0, 8), (-2.4, 0.9)   # the shell's columns: from, to (degrees round, 90 the back), count
# the hair over her head (head bone): HAIR_COLS columns from the crown (degrees from the front, mirrored; the two
# beside the front the middle part's sides: the strip between them darker, pressed in: the part), each down the shell through
# latitudes (from the crown) then: the face's frame, its edge tucked HAIR_TUCK out from the skin at (degrees from the
# front, z from the eyes' height): the forehead under the part, over the brows to the temple, then down along the
# cheek to the jaw (the curtain's inner edge); the sides and the back fall straight from the shell's widest down to
# the curtain's bottom (HAIR_CURTAIN, z from the eyes', at the face's sides) and to the nape (the back), the sides'
# ends jagged (HAIR_JAG, alternately), the outline wavy (HAIR_WAVE: the columns' radius alternately x)
HAIR_COLS = {2.5: ((22.0, 42.0), [(2.5, 3.6)]), 22.5: ((22.0, 45.0, 62.0), [(22.5, 2.5)]),
             45.0: ((22.0, 45.0, 67.0, 80.0), [(45.0, 1.3)]),
             67.5: ((22.0, 45.0, 67.0, 85.0), [(66.0, -0.5), (70.0, -3.0), (72.0, -5.5)])}
# the shell beside the face (columns from this many degrees, from 60 degrees of latitude down) drawn in this much
# toward the hair's centre: the curtains lie close by the cheeks (wider, the head's usual turn put the near one over
# half the face)
HAIR_CHEEK = (45.0, 0.84)
HAIR_BACK = (90.0, 112.5, 135.0, 157.5, 180.0)    # the falling columns (all latitudes 22.5 .. 90, then 3 rows down)
HAIR_TUCK, HAIR_CURTAIN, HAIR_JAG, HAIR_WAVE = 0.45, -6.4, (-1.1, 0.5), (1.035, 0.975)
HAIR_PART = 0.97                             # the part's strip pressed in toward the hair's centre
HAIR_RX = 7.4                                # the shell's half width: from the back as wide as the fall's top
HAIR_DEEP = 1.06                             # its fitted depth x (the forehead's top stays under it)
HAIR_BACKLIT = (np.array([0.0, 0.8, 0.6]), 0.3)   # the hair's second light, from above-behind: the shell reads round
# the hair's shell round her head: the forehead's front taken from its vertices this far below the top; the centre
# this much above the eyes' height (the nape and the fall below set against it); the top HAIR_TOP over the skull's (a
# thin layer: the hair adds no height), the radii round (across, deep) fitted round its top, back and sides, then x
# this (the polygon's chords cut inside the ellipsoid: the forehead's top showed through)
HAIR_FIT = (4.0, -0.5, 1.08)
HAIR_TOP = 0.6
HAIR_REF_Z = 7.8                             # the shell's centre the rows below (nape, fall) were set against
# Dash's meshes, recoloured: per texel a class by where it lies on the model; a class's texture colour (lit: the
# vertex shade, DASH_AMB .. 1, darkens it), his luminance against the class's mean scaling it by TEX_CONTRAST
ARM_BAND = (2.0, 4.2)                        # the red band round the upper arm: from, to below the shoulder (units)
GLOVE_AT = 0.47                              # the glove's top on the forearm (fraction of its length)
THIGH_TOP = 0.35                             # Dash's thigh tops past the hip joint pressed to this
# The shoulder caps (the user, 2026-11-07: "the arms come apart from the torso" in the melee blocks): on each upper-arm
# bone a dome of ours in the sleeve's colour round the joint, its pole toward the body (the bodice ends just inside the
# arms' tops, ~3.8 units short of the joint: a raised or drawn-back arm opened that strip). Centred on the joint, it
# turns in place with the arm and always fills the armhole. (pole depth toward the body, half deep y, half up z, half
# down z, the rim this far into the arm, around): the down half smaller (the left upper arm's guard box ends there;
# under the arm it is the armpit's side, hidden)
SHOULDER_CAP = tuple(v * 0.85 for v in (4.4, 5.0, 4.4, 2.8, 1.0)) + (8,)   # x 0.85: the narrower shoulders, slimmer arms
# The fist (the user, 2026-11-07: "the hand is a bent bone, not a fist"): the right hand (bone 10, the punching one)
# is ours, a closed glove: a rounded block along the fingers' axis (-x: Dash's right hand's fingers, the palm +z, the
# thumb -y) with the knuckle row as a ridge at its front top (the back of the hand, -z) and the thumb lying across the
# curled fingers on the palm side; the left hand keeps Dash's open one (it grips). FIST_RINGS: (x, half y, back z,
# palm z, y shift); FIST_FRONT: the front's centre (x, z); FIST_THUMB: from (x, y, z) to y, radius
FIST_RINGS = [(1.4, 1.9, -1.3, 1.6, -0.2), (-1.6, 2.6, -2.0, 2.6, -0.3), (-4.2, 2.6, -2.3, 2.9, -0.3)]
FIST_FRONT = (-5.4, 0.3)
FIST_THUMB = ((-3.7, -3.0, 2.8), 0.9, 0.75)
# (the first fist, 6.3 long and 4.3 deep, read in the stills as a straight flat hand: shortened and deepened; the
# thumb a shade darker (THUMB_SHADE x the glove's) so it reads across the fingers)
THUMB_SHADE = 0.7
TEX_KIND = {7: 'glove', 10: 'glove', 5: 'trousers', 2: 'trousers', 4: 'boot', 1: 'boot', 3: 'boot', 0: 'boot'}
TEX_CONTRAST, DASH_AMB = 0.45, 0.6
TEX_COL = dict({k: BASE[k] * SHADE[k][1] for k in ('sleeve', 'glove', 'trousers', 'boot', 'red')}, hair=HAIR)
# her head (ours, on the guard's head bone; Dash's head and neck, a man's long face and heavy jaw, are not taken): a
# round head, an ellipsoid of HEAD_AROUND points round (at 15 + 30 k degrees, 270 the front) x HEAD_BANDS bands from
# the crown to the chin (a ring at the eyes' height, the head's middle line); HEAD_R: half width, depth to the front,
# to the back, up from the eyes to the crown, down to the chin; below the eyes the jaw narrows by HEAD_JAW (latitude from
# the crown: x, front depth, back depth factors, y shift; between the keys linear): a narrow rounded chin. A skull,
# not an egg (the user, 2026-11-07: the head read tall, "like an egg", from above): the cranium low (brow to the hair's
# top about 0.4 of chin to the hair's top), above the eyes the rings' radius sin(lat) ** HEAD_TOP (a flatter-rounded
# top, the forehead upright), widest at the temples and the back fuller than the front (HEAD_JAW's upper keys)
HEAD_AROUND, HEAD_BANDS = 12, 8
HEAD_R = (4.3, 4.8, 5.0, 5.35, 6.6)
HEAD_TOP = 0.75
HEAD_JAW = [(0.0, 1.0, 1.0, 1.0, 0.3), (60.0, 1.03, 1.0, 1.1, 0.35), (78.0, 1.045, 1.0, 1.08, 0.25),
            (90.0, 1.0, 1.0, 1.04, 0.1), (112.5, 0.97, 0.98, 0.85, 0.0),
            (135.0, 0.88, 0.92, 0.62, -0.3), (157.5, 1.0, 0.85, 0.4, -0.8), (180.0, 0.9, 0.8, 0.3, -1.4)]
# the head's centre (the eyes' height) on the head bone: over the turtleneck's axis (the bodice's neck ring), this far
# forward of it, the chin's lowest point this far above the turtleneck's top
HEAD_AT = (0.9, 0.3)
# the head's mesh: columns (degrees round): HEAD_AROUND's, but 75 apart at the back (under the hair) and three more on
# the nose's line and beside it (the nose a narrow wedge); its rings: HEAD_BANDS' and FACE_RELIEF's
HEAD_THS = (15.0, 90.0, 165.0, 195.0, 225.0, 255.0, 263.0, 270.0, 277.0, 285.0, 315.0, 345.0)
# the face's relief (the photo's features as geometry, so they stand out in profile and catch the light): rings at
# the photo's rows (FACE_SRC's pixels: the brow, the eyes, the nose's tip, its base, the lips, the chin; each at the
# height the texture puts that row), each pushed forward (head units) by |x| from the nose's line (between the keys
# linear, past the last 0): the brow ridge a little out, the eye sockets a little in beside a narrow bridge, the nose
# a wedge out about 0.14 of the head's depth at its tip, its base (the nostrils) under it, the lips out level
# with the nostrils' base (no hollow under the nose: the jaw narrows there), a rounded chin 0.25 in front of the lips with a clear
# underside (its edge at row 60.4, then back to the neck), the jaw line from it back toward the ears (the jaw's
# x widened near the chin, HEAD_JAW: on the ellipsoid the bottom closed to a point). Pushed straight forward (x and z
# kept): the face texture's projection stays where it was
HEAD_DEPTH_NOSE = 0.14
FACE_RELIEF = [(13.0, [(0.0, 0.2), (1.1, 0.3), (3.0, 0.25), (3.9, 0.0)]),
               (18.0, [(0.0, 0.35), (0.6, 0.12), (1.1, -0.15), (3.0, -0.12), (3.9, 0.0)]),
               (37.0, [(0.0, None), (0.55, 0.55), (1.1, 0.08), (2.0, 0.0)]),
               (39.5, [(0.0, 0.35), (0.55, 0.5), (1.1, 0.35), (2.5, 0.1), (3.4, 0.0)]),
               (48.0, [(0.0, 0.9), (0.71, 0.85), (1.95, 0.4), (2.66, 0.12), (3.2, 0.0)]),
               (57.0, [(0.0, 2.05), (0.48, 2.0), (1.32, 1.55), (1.8, 0.75), (2.4, 0.0)]),
               (60.4, [(0.0, 2.31), (0.24, 2.28), (0.65, 1.7), (0.89, 0.5), (1.2, 0.0)])]
NECK = [(-5.5, 2.2, 2.4), (0.5, 2.0, 2.2)]   # her neck (head bone): rings (z from the head bone, half x, half y) round
                                             # the turtleneck's axis, from inside the collar up into the head
# the face: a FACE_TEX texture wrapped round the head's front by a cylindrical projection about its vertical axis: u
# the angle round over FACE_SECT's (from, to) degrees, v the height from the ring at FACE_SECT's latitude (from the
# crown) down to the chin; those sectors' triangles from that ring down carry it, the rest of the head is bare skin.
# Its picture: the user's photo of her figure (front), the face cropped brow to chin (FACE_SRC: the file, the eyes'
# centre x, their y, the chin's lowest y, in its pixels), projected from the front onto the head's surface (the eyes at
# the head's middle height, the chin at its chin: one scale), saturation then contrast lifted by FACE_LIFT (the eyes,
# brows and lips read at the game's distance), its skin matched to SKIN (the cheeks' median), the hair and the dark
# below the chin taken out and the crop's border blended over FACE_BLEND pixels into SKIN: the texture's edges are the
# head's skin
FACE_TEX = (64, 64)
FACE_SECT = (195.0, 345.0, 45.0)
FACE_SRC = (os.path.join(HERE, 'face_src.png'), 27.2, 18.0, 61.5)
FACE_LIFT, FACE_BLEND, FACE_FLAT = (1.35, 1.15), 4.0, 5.0
# her makeup over the photo (head_model.face_texture): (photo rows from, to (excluded)), (|x - the eyes' centre x| from, to), the
# colour, the share toward it: the lips (FACE_RELIEF's row 48.0, between the mouth's corners) a rose red, the upper
# lids (the rows just above the eyes' 18.0, over each eye) darker (lashes; a band through row 18 darkened the eyes
# themselves and took the irises' blue out of the 16 colours), the cheeks a soft blush (outer columns)
MAKEUP = [((46.0, 50.0), (0.0, 11.5), (165, 45, 60), 0.40),
          ((16.0, 18.0), (6.0, 20.0), (0, 0, 0), 0.40),
          ((30.0, 40.0), (9.0, 20.0), (220, 120, 120), 0.15)]
FACE_HAIR = (26, 55, 0.55)                   # her golden hair in the photo (hue from, to, saturation over): taken out
MIN_FALL_CLEAR = 0.5                         # check: the fall's least clearance off the bodice's back (1.36 since the
                                             # bust's rings; a fuller back, its half y 8.2 at z 8, brought it to 0.59)
# her head's constants for head_model.head (the skull, face, relief, the 'long' hair, the neck in her skin)
HEAD = types.SimpleNamespace(**{k: v for k, v in globals().items() if k.startswith(('HEAD_', 'FACE_', 'HAIR', 'FALL_'))},
                             NECK=NECK, MAKEUP=MAKEUP, SKIN=SKIN, SKIN_SHADE=SHADE['skin'], NECK_COLOUR=(SKIN, SHADE['skin']),
                             HAIR_STYLE='long', DASH_AMB=DASH_AMB)
# the skirt: two panels (front, back) of a tabard, split at the sides (the legs show through the slits), from the
# hips to about mid-calf, slightly flared; rings (z, rx, ry, y shift) in the pelvis frame, the panels' arcs (degrees
# round, 270 the front), the hem's z at the arc's ends (the front's cut at an angle: lower on the figure's left, +x)
# (every rx GURI_HIP_OUT 1.5 out with her thighs' joints: the panels are built here, in the pelvis frame, so they do
# not move with a joint by themselves)
SKIRT = [(1.5, 10.05, 6.4, 0.3), (-6.0, 12.52, 8.12, 0.4), (-13.0, 13.5, 8.6, 0.4), (-25.0, 13.9, 8.96, 0.2),
         (None, 14.1, 9.3, 0.0)]                 # fitted: on the hips, then a slight flare (the boxy tabard hid the waist)
SKIRT_ARC = {'front': (205.0, 335.0, 6), 'back': (25.0, 155.0, 4)}     # (the back's 4 columns: split in the middle,
                                                                       # the triangles kept within 1600)
SKIRT_DEEP = {'front': 0.92, 'back': 1.03}   # the rings' depth (ry) x: on the thighs each fits their boxes (the
                                             # back's 1.17 on the pelvis came 1.4 past a thigh's)
SKIRT_BACK_HIP = (-13.0, 1.08)               # the back's rows from this z up this deep (over the buttocks; 1.24 on the
                                             # pelvis, where the thighs' backs in the idle pose came through as a speck)
SKIRT_HEM = {'front': (-26.0, -31.0), 'back': (-29.0, -29.0)}   # just above the knee (the angled cut kept; to
                                             # mid-calf, -38.5 / -43.0, the boxy tabard hid her figure, 2026-11-11)
# where a panel hangs: 'pelvis', or 'thighs' (each half on its thigh bone, it follows the leg). The guard's walk is a
# deep lunge: a front panel on the pelvis has the leading thigh through it; on the thighs it swings with the legs. The
# back one split up the middle the same way (on the pelvis it jutted behind her as one plate and the rear leg cut
# through it walking: the user, 2026-11-11)
SKIRT_ON = {'front': 'thighs', 'back': 'thighs'}
SKIRT_SIDE = (-5.0, 2, 4.0, 0.985)           # the slits' top: the hips closed down to this z (pelvis frame; -11.0
                                             # before: the leg shows from the hip in stride), columns;
                                             # under the panels' edges by (degrees, radius x): no crack at the seam
# bones (trSt order): legs 5-4-3 and 2-1-0 (thigh, calf, foot), arms 12-11-10 and 9-8-7 (upper, fore, hand),
# 15 pelvis, 14 spine (waist), 13 chest, 6 head, 16 the root (no mesh)
LIMB = {5: 4, 4: 3, 2: 1, 1: 0, 12: 11, 11: 10, 9: 8, 8: 7}     # limb bone -> its child bone
BELT = [(-4.2, 8.56, 5.85, 0.18), (-0.4, 7.55, 5.3, 0.05)]    # the sash, on the waist bone (14): rings as the torso's
                                             # (each ring x the waist's narrowing at its z: it stays on the waist)
# the turtleneck, on the chest bone (13), round Dash's neck (centred x 0.5 on the bodice's neck ring, y its centre,
# just outside his neck), up to under his chin: it shows above the bodice
COLLAR = [(19.5, 5.0, 5.0, 0.2), (22.5, 4.5, 4.7, 0.2), (24.6, 4.3, 4.5, 0.2)]
# the bodice's neckline: a shallow rounded scoop, the neck ring's two front points dropped to this z and moved out by
# this factor (onto the bodice's surface); its top closed in the turtleneck's grey up to the collar (the cap's centre)
SCOOP = (20.0, 1.18, (0.5, 0.2, 22.6))
# the torso (bone: rings (z, half x, half y, y shift), caps), a bone's frame: z up, front -y. The chest's shoulder ring
# (z 19.6) reaches over the upper arms' tops: on the guard's joints 14.7 (at 11.6 a dark strip showed between arm and
# bodice from the front, 0.10 wide (guri/shoulder_gap.py; the user, 2026-11-09); 14.0 still left 0.009 in the side
# view, 14.4 with the slimmer arms 0.013); on hers (her_skeleton: GURI_SHOULDER_IN 4.0 nearer the body) 4.0 less, 10.7,
# and the upper chest (12.5) and the 10.3 arc ring on the straight side line from it down to the bust ring (8.0, 9.4):
# no step at the shoulders (the bust's front depth kept: a ring's front does not depend on its half x). Its lower twin at z 16.0 was dropped for the bust's two arc rings (the 1600 triangles;
# without the 19.6 one instead the arms' tops showed a 0.2 strip). The pelvis (15): her hips GURI_HIP_OUT 1.5 wider
# than the guard's frame gave (10.8 -> 12.3, its other rings with it). The waist (14) middle ring 7.0 x 4.9 and the
# chest's lowest ring 7.8: a narrow waist, 5.8 x 4.5, read as a pinch, "not anatomical", and 6.6 x 4.8 still pinched
# above the sash (the user, 2026-11-11; the front still's narrowest red row was above the sash, now at it)
TORSO = {15: ([(-8.6, 7.9, 5.0, 0.3), (-2.6, 12.3, 6.4, 0.4), (3.2, 8.9, 5.0, 0.2)], (True, True)),
         14: ([(-4.6, 8.4, 5.6, 0.2), (1.2, 7.0, 4.9, 0.0), (7.6, 8.0, 5.4, -0.2)], (True, False)),
         13: ([(-1.6, 7.8, 5.6, 0.0), (3.0, 8.4, 5.2, 0.0), (5.5, 8.9, 6.3, -0.75), (8.0, 9.4, 7.4, -1.5),
               (10.3, 9.66, 6.79, -1.19), (12.5, 9.90, 6.2, -0.9),
               (19.6, 10.7, 5.2, -0.4), (21.8, 5.0, 4.4, 0.2)],
              (True, True))}
# the bust: the bodice's own form (separate shells read as two bumps with dark shading, the user, 2026-11-11): the
# chest's loft 12 sides (a point at the front's middle, each 30 degrees), its rings an under-bust tuck (z 3.0), the
# bust (8.0), the upper chest (12.5); on the bust ring each front point's depth x a factor by its angle from the front
# (degrees: factor; the under-bust and upper-chest rings half the amount): the front fuller than the ellipse, the 30
# degree points 0.6 ahead of the middle (two soft forms from the front, not one), one surface, its normals the
# surface's own. The rings at 5.5 and 10.3 (half x, the back: linear between their neighbours) put their front on the
# circle through the three rings' fronts at each angle: a round side profile (with straight segments it peaked at 8.0).
# The first factors (1.0, 1.08, 0.96, 1.0) left the front's middle frontmost: no bust read from the front or the side
TORSO_SIDES = {13: (12, 0.0)}                # bone: (sides, the first point's angle); the others 8, half a side
BUST_PROFILE = ((0.0, 1.135), (30.0, 1.404), (60.0, 1.06), (90.0, 1.0)), 8.0
# the bust's shade painted into the bodice's vertex colours (the baked light comes from above-front, about where the
# camera looks from: the form alone read from the front only by its outline, the user, 2026-11-11): the under-bust
# ring and the arc ring above it darker at 0..30 degrees from the front, back to 1.0 at the sides; the bust ring's and
# the upper arc ring's 30 degree points (each form) lighter, the bust ring's 0 degree point (between them) a little
# darker. Gouraud blends them: a gradient, no hard edge. Ring z: ((degrees from the front, factor), ...); the back 1.0
UNDERBUST_SHADE = 0.72
BUST_LIT = (1.12, 0.9)                       # the forms' 30 degree points, the valley's 0 degree point
BUST_SHADE = {3.0: ((0.0, UNDERBUST_SHADE), (30.0, UNDERBUST_SHADE), (90.0, 1.0)),
              5.5: ((0.0, UNDERBUST_SHADE), (30.0, UNDERBUST_SHADE), (90.0, 1.0)),
              8.0: ((0.0, BUST_LIT[1]), (30.0, BUST_LIT[0]), (60.0, 1.0), (90.0, 1.0)),
              10.3: ((0.0, 1.0), (30.0, BUST_LIT[0]), (60.0, 1.0), (90.0, 1.0))}
# Dash's limbs slimmed across their bone (the bone -> child axis; along it kept): upper arm, forearm, thigh, calf (at
# 1.0 his man's limbs read heavy on her in the duel's frames, the user, 2026-11-11); hands and feet as his
LIMB_SLIM = {12: 0.82, 9: 0.82, 11: 0.82, 8: 0.82, 5: 0.88, 2: 0.88, 4: 0.88, 1: 0.88}


def her_skeleton(T):
    """The guard's bone translations (guard_skeleton's T) with her skeleton: the upper arms' (12, 9) x moved toward
    the body by guri_moves_trop.GURI_SHOULDER_IN, the thighs' (5, 2) out by GURI_HIP_OUT, as the rest rows of every block she plays on 33 (imported here, not at
    the top: that module loads melee.py's dump)."""
    from guri_moves_trop import her_dx, SHOULDER_BONES, HIP_BONES
    T = np.array(T, float)
    for j in SHOULDER_BONES + HIP_BONES: T[j][0] += her_dx(j, T[j][0])
    return T


def dump_ram(rom):
    if os.environ.get('GURI_RAM'): return open(os.environ['GURI_RAM'], 'rb').read()
    import guard_asset
    return guard_asset.dump_ram(rom)


def guard_skeleton(E):
    """Trop 0's trSt bones: (translations (17,3), parent per bone (-1 the root), per-bone near-mesh box lo/hi or None)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    F = lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]
    p, rec = R(0x80112830), {}
    for i in range(80):
        r = R(p + 4 * i)
        if not r: break
        rec[R(r)] = r
    assert 0x54726F70 in rec, 'no Trop: is palace.st sub-level 26?'
    pool = R(rec[0x54726F70] + 0x10)
    assert R(pool + 0x74) == 0, 'Trop 0 is not the red guard (kind 0)'
    blk = R(pool + 0xCC)
    assert R(blk + 0x1C) == 0x74725374, 'Trop 0 +0xCC is not its trSt block'
    nodes = [R(blk + 0x38 + 0xA0 * i + 8) for i in range(BONES)]
    idx = {n: i for i, n in enumerate(nodes)}
    T = np.array([[F(n + 0x38 + 4 * a) for a in range(3)] for n in nodes])
    parent = [-1] * BONES
    boxes = [None] * BONES
    for i, n in enumerate(nodes):
        pts = []
        for k in range(R(n + 0x0C)):
            c = R(R(n + 0x10) + 4 * k)
            if c in idx: parent[idx[c]] = i; continue
            m = R(R(c + 0x10)) if R(c) >> 28 == 5 else c          # a variant group: its near variant (0)
            for q in range(R(m + 0x0C)):
                a = R(R(R(m + 0x10) + 4 * q) + 0x28)
                while R(a) >> 24 != 0xB8:
                    if R(a) >> 24 == 0x04:
                        v = R(a + 4)
                        for j in range((R(a) & 0xFFFF) >> 9):
                            pts.append(struct.unpack_from('>hhh', E, (v & 0x7FFFFF) + 16 * j))
                    a += 8
        if pts:
            P = np.array(pts, float) / 8
            boxes[i] = (P.min(0), P.max(0))
    assert parent.count(-1) == 1, parent
    return T, parent, boxes



def ellipsoid(c, a, bands=6, around=8):
    """Grid of (bands + 1) rings of `around` points (the poles repeated), latitude from the top."""
    pts, nrm = [], []
    for i in range(bands + 1):
        ph = math.pi * i / bands
        row, nr = [], []
        for k in range(around):
            th = math.radians(22.5 + 360 / around * k)
            u = np.array([math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph)])
            row.append(c + a * u); nr.append(u / a)
        pts.append(row); nrm.append(nr)
    return pts, nrm


def grid_quads(part, pts, nrm, keep, uvf=lambda p: (0.0, 0.0)):
    """Triangles of the ellipsoid grid's quads (k, i) that keep(i, k) takes; a quad at a pole is one triangle."""
    ids = {}
    def vid(i, k):
        if (i, k) not in ids: ids[i, k] = part.v(pts[i][k], nrm[i][k], uvf(pts[i][k]))
        return ids[i, k]
    bands, around = len(pts) - 1, len(pts[0])
    for i in range(bands):
        for k in range(around):
            if not keep(i, k): continue
            k2 = (k + 1) % around
            a, b, c, d = (i, k), (i + 1, k), (i + 1, k2), (i, k2)
            if i == 0: part.tri(vid(*a), vid(*b), vid(*c))
            elif i == bands - 1: part.tri(vid(*a), vid(*b), vid(*d))
            else: part.tri(vid(*a), vid(*b), vid(*c)); part.tri(vid(*a), vid(*c), vid(*d))


def dash_meshes(E):
    """Dash's (Humn, animation block `trot`) limb, hand, foot, head and neck meshes baked into the guard's bone frames:
    {guard bone: [(positions (N,3) local units, normals (N,3), uvs (N,2), triangles (M,3), texture record, Dash bone)]}.
    The inverse of guard_asset.py's per-bone transform (its MAP read the other way: Dash bone -> guard bone): a limb,
    hand or foot by M^-1 (M = the limb turn times the length ratio along the bone and the torso ratio across), normals
    by M^T; the head (Dash 1) and the neck (Dash 2) onto the guard's head bone through the torso's height knots (KNOTS)
    and the torso ratio. Plain meshes only (Dash's are); his weapon (w0 bit 0x80, on the right hand) left out; the
    chest (his jetpack), spine and pelvis are not taken (the bodice and the skirt are ours)."""
    import guard_asset as ga
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    F = lambda a: struct.unpack_from('>f', E, a & 0x7FFFFF)[0]
    p, rec = R(0x80112830), {}
    for i in range(80):
        r = R(p + 4 * i)
        if not r: break
        rec[R(r)] = r
    blk = R(R(rec[0x54726F70] + 0x10) + 0xCC)
    gn = [R(blk + 0x38 + 0xA0 * i + 8) for i in range(BONES)]
    b = R(R(rec[0x48756D6E] + 0x10) + 0x19C)
    for i in range(60):
        if R(b + 0x1C) == 0x74726F74: break
        b = R(b + 0x14)
    assert R(b + 0x1C) == 0x74726F74, "no trot block on Dash: is palace.st sub-level 26?"
    dn, e = [], b + 0x38
    for i in range(ga.DASH_BONES): dn.append(R(e + 8)); e = R(e + 0x0C)
    t = lambda n: np.array([F(n + 0x38 + 4 * i) for i in range(3)])
    ratio = {g: float(np.linalg.norm(t(dn[dc])) / np.linalg.norm(t(gn[gc])))
             for g, (d, gc, dc) in ga.MAP.items() if gc is not None}
    s0 = float(np.median(list(ratio.values())))

    def turn(u, v):
        u, v = u / np.linalg.norm(u), v / np.linalg.norm(v); c = np.cross(u, v); d = float(u @ v)
        if np.linalg.norm(c) < 1e-9: return np.eye(3)
        K = np.array([[0, -c[2], c[1]], [c[2], 0, -c[0]], [-c[1], c[0], 0]])
        return np.eye(3) + K + K @ K / (1 + d)
    M = {}
    for g, (d, gc, dc) in ga.MAP.items():
        if gc is None: continue
        ug, ud = t(gn[gc]), t(dn[dc]); u = ug / np.linalg.norm(ug)
        M[g] = turn(ug, ud) @ (ratio[g] * np.outer(u, u) + s0 * (np.eye(3) - np.outer(u, u)))
    for g in ga.LEAF: M[g] = M[ga.LEAF[g]]
    H = lambda bs, nodes: sum((t(nodes[i]) for i in bs), np.zeros(3))
    kg = [0.0] + [s0 * H(gc, gn)[2] for gc, _ in ga.KNOTS]; kd = [0.0] + [H(dc, dn)[2] for _, dc in ga.KNOTS]
    kd[-1] = kd[-2] + (kg[-1] - kg[-2])            # guard_asset's: the head as high over the shoulders as its source's
    def zinv(z):                                   # guard_asset's height map, inverted (Dash's height -> the guard's)
        if z <= kd[0]: return z - kd[0] + kg[0]
        if z >= kd[-1]: return z - kd[-1] + kg[-1]
        return float(np.interp(z, kd, kg))
    xf = {}
    for g, (d, gc, dc) in ga.MAP.items():
        if g in ga.TORSO: continue
        xf[d] = (g, (lambda Mi: lambda v: Mi @ v)(np.linalg.inv(M[g])), M[g].T)
    pg = s0 * H(ga.UP[6][0], gn)                   # the guard's head joint above its pelvis (in Dash's scale)
    for d, chain in ((1, ga.UP[6][1]), (2, ga.UP[6][1][:-1])):     # the head, the neck (its chain one bone shorter)
        pd = H(chain, dn)
        xf[d] = (6, (lambda pd: lambda v: np.array([(v[0] + pd[0] - pg[0]) / s0, (v[1] + pd[1] - pg[1]) / s0,
                                                    (zinv(v[2] + pd[2]) - pg[2]) / s0]))(pd), np.eye(3))
    ds, out = set(dn), {}
    for d, (g, f, Nm) in sorted(xf.items()):
        node = dn[d]
        for k in range(R(node + 0x0C)):
            m = R(R(node + 0x10) + 4 * k)
            if m in ds or R(m) & 0x80: continue
            assert R(m) >> 28 == 3, f'Dash bone {d}: mesh {m:#x} w0 {R(m):#x} is not a plain mesh'
            for q in range(R(m + 0x0C)):
                pt = R(R(m + 0x10) + 4 * q); a = R(pt + 0x28)
                pos, nrm, uv, tris, slot = [], [], [], [], {}
                while R(a) >> 24 != 0xB8:                 # G_VTX / 0xBF / 0xB5 (docs/reverse-engineering.md); 0xBE (a cull test) skipped
                    w0, w1 = R(a), R(a + 4); c = w0 >> 24
                    if c == 0x04:
                        assert (w0 >> 16) & 0xFF == 0, f'G_VTX {w0:#x} not from slot 0'
                        for j in range((w0 & 0xFFFF) >> 9):
                            x, y, z, _, s, tt, nx, ny, nz, _ = struct.unpack_from('>hhhHhhbbbB', E, (w1 + 16 * j) & 0x7FFFFF)
                            slot[j] = len(pos); pos.append(f(np.array((x, y, z)) / 8))
                            n = Nm @ np.array((nx, ny, nz), float); nrm.append(n / (np.linalg.norm(n) or 1))
                            uv.append((s / 4096, tt / 4096))   # the records' scale is W*512 / H*512, as ours
                    elif c == 0xBF: tris.append(tuple(slot[(w1 >> s & 0xFF) // 5] for s in (16, 8, 0)))
                    elif c == 0xB5:
                        i4 = [slot[(w1 >> s & 0xFF) // 5] for s in (24, 16, 8, 0)]
                        tris += [(i4[0], i4[1], i4[2]), (i4[0], i4[2], i4[3])]
                    else: assert c == 0xBE, f'{w0:#x} in a geometry DL at {a:#x}'
                    a += 8
                out.setdefault(g, []).append((np.array(pos), np.array(nrm), np.array(uv), np.array(tris),
                                              R(R(pt + 0x24) + 8), d))
    return out


def dash_texture(E, rec):
    """A texture record's level-0 image as RGB (H, W, 3): CI8 / CI4 with an RGBA5551 palette (a TLUT load in its DL),
    or RGBA16 (a mipmapped one: its DL calls a segment-4 DL)."""
    R = lambda a: struct.unpack_from('>I', E, a & 0x7FFFFF)[0]
    H16 = lambda a: struct.unpack_from('>H', E, a & 0x7FFFFF)[0]
    a, seg, fds, tlut, fmt, W, H, stack = R(rec + 8), None, [], False, None, None, None, []
    for _ in range(200):
        w0, w1 = R(a), R(a + 4); c = w0 >> 24
        res = lambda w: ((seg + (w & 0xFFFFFF)) & 0x7FFFFF) | 0x80000000
        if w0 == 0xBC001006: seg = w1
        if c == 0x06: stack.append(a + 8); a = res(w1); continue
        if c == 0xFD: fds.append(res(w1))
        if c == 0xF0: tlut = True
        if c == 0xF5 and (w1 >> 24 & 7) == 0 and fmt is None: fmt = (w0 >> 21 & 7, w0 >> 19 & 3)
        if c == 0xF2 and (w1 >> 24 & 7) == 0 and W is None:
            W, H = ((w1 >> 12 & 0xFFF) >> 2) + 1, ((w1 & 0xFFF) >> 2) + 1
        if c == 0xB8:
            if not stack: break
            a = stack.pop(); continue
        a += 8
    rgb = lambda v: ((v >> 11 & 31) * 255 // 31, (v >> 6 & 31) * 255 // 31, (v >> 1 & 31) * 255 // 31)
    out = np.zeros((H, W, 3), np.uint8)
    for i in range(W * H):
        if fmt == (2, 1): v = H16(fds[0] + 2 * E[(fds[1] & 0x7FFFFF) + i])
        elif fmt == (2, 0): b = E[(fds[1] & 0x7FFFFF) + i // 2]; v = H16(fds[0] + 2 * (b >> 4 if i % 2 == 0 else b & 15))
        else: assert fmt == (0, 2) and not tlut, (rec, fmt); v = H16(fds[0] + 2 * i)
        out[i // W, i % W] = rgb(v)
    return out


def texel_map(W, H, items):
    """Which point of the model each texel of a W x H texture shows: rasterized in texture space (uvs wrap) from
    [(positions, uvs, triangles)]: (cover (H, W) bool, positions (H, W, 3)). A texel just outside a triangle's edge
    counts (the filter reads it)."""
    cover = np.zeros((H, W), bool); pos = np.zeros((H, W, 3))
    for P, uv, tris in items:
        for t in tris:
            q = uv[list(t)] * (W, H)
            (x0, y0), (x1, y1), (x2, y2) = q
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9: continue
            I, J = np.meshgrid(np.arange(int(np.floor(q[:, 0].min())) - 1, int(np.ceil(q[:, 0].max())) + 1) + 0.5,
                               np.arange(int(np.floor(q[:, 1].min())) - 1, int(np.ceil(q[:, 1].max())) + 1) + 0.5)
            a = ((y1 - y2) * (I - x2) + (x2 - x1) * (J - y2)) / den
            b = ((y2 - y0) * (I - x2) + (x0 - x2) * (J - y2)) / den
            w = np.stack([a, b, 1 - a - b], -1)
            m = w.min(-1) > -0.12
            w = np.clip(w[m], 0, None); w /= w.sum(1, keepdims=True)
            jj, ii = (J[m] - 0.5).astype(int) % H, (I[m] - 0.5).astype(int) % W
            cover[jj, ii] = True; pos[jj, ii] = w @ P[list(t)]
    return cover, pos


def recolour(src, cover, pos, cls):
    """A texture of Dash's recoloured texel by texel: cls(position) names each covered texel's class, a colour of
    TEX_COL (the texel's luminance against the class's mean scales it: his folds and shading kept).
    Texels no triangle covers take their nearest covered neighbour's colour (the filter reads them). At most 16
    colours (the converter's CI4): quantized. Returns PNG bytes."""
    H, W = cover.shape
    lum = src.astype(float) @ np.array([0.299, 0.587, 0.114]) + 1.0
    cl = np.full((H, W), '', object)
    for j, i in zip(*np.nonzero(cover)): cl[j, i] = cls(pos[j, i])
    out = src.astype(float).copy()
    for c in set(cl[cover]):
        m = cover & (cl == c)
        r = lum[m] / lum[m].mean()
        out[m] = TEX_COL[c] * (1 + TEX_CONTRAST * (r - 1))[:, None]
    out = np.clip(out, 0, 255)
    done = cover.copy()                            # uncovered texels: grown from the covered ones
    for _ in range(max(H, W)):
        if done.all(): break
        acc, cnt = np.zeros((H, W, 3)), np.zeros((H, W))
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            d = np.roll(done, (dj, di), (0, 1)); acc += np.roll(out, (dj, di), (0, 1)) * d[..., None]; cnt += d
        grow = ~done & (cnt > 0)
        out[grow] = acc[grow] / cnt[grow][:, None]; done |= grow
    im = Image.fromarray(out.astype(np.uint8)).quantize(16, Image.Quantize.MEDIANCUT).convert('RGB')
    assert im.getcolors(16) is not None, 'a texture over 16 colours (CI4)'
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()


def build(E, checker=False):
    T, parent, boxes = guard_skeleton(E)
    T = her_skeleton(T)                           # her shoulders: the shapes and the glTF's translations on her joints
    dash = dash_meshes(E)
    dash.pop(6)                                   # his head and neck: hers is ours (a woman's: smaller, a soft jaw)
    dash.pop(10)                                  # his open right hand: hers a fist of ours (FIST_RINGS)
    for b in (5, 2):                              # Dash's thigh tops, past the hip joint, pressed toward it: on the
        u = T[LIMB[b]] / np.linalg.norm(T[LIMB[b]])   # guard's hips they came out of the waist above the skirt
        dash[b] = [(q[0] - np.outer(np.minimum(q[0] @ u, 0) * (1 - THIGH_TOP), u),) + q[1:] for q in dash[b]]
    for b, k in LIMB_SLIM.items():                # slimmer limbs: across the bone's axis x k (positions), normals by the
        u = T[LIMB[b]] / np.linalg.norm(T[LIMB[b]])   # inverse (x 1 / k across); the uvs untouched
        A = np.outer(u, u); S, N = A + k * (np.eye(3) - A), A + (np.eye(3) - A) / k
        dash[b] = [(q[0] @ S, (lambda n: n / np.linalg.norm(n, axis=1, keepdims=True).clip(1e-9))(q[1] @ N)) + q[2:]
                   for q in dash[b]]
    children = {i: [j for j in range(BONES) if parent[j] == i] for i in range(BONES)}
    guard_box = {i: boxes[i] for i in range(BONES) if boxes[i] is not None}
    ctr = {i: (b[0] + b[1]) / 2 for i, b in guard_box.items()}
    X, Y, Z = np.eye(3)

    up = {}                                       # the light's "up" per bone frame
    for b in (15, 14, 13, 6): up[b] = Z
    for b, c in LIMB.items(): up[b] = -T[c] / np.linalg.norm(T[c])
    for leaf, limb in ((3, 4), (0, 1), (10, 11), (7, 8)): up[leaf] = up[limb]

    plain = {}
    def P(b, kind, tag=''):
        if (b, kind, tag) not in plain: plain[b, kind, tag] = Part()
        return plain[b, kind, tag]

    # sash and turtleneck: bands a shade out from the torso's surface
    for b, rings, kind in ((14, BELT, 'sash'), (13, COLLAR, 'grey')):
        band = P(b, kind)
        R_ = [(np.array([0.5 if b == 13 else 0.0, sy, z]), X, Y, hx, hy) for z, hx, hy, sy in rings]
        band.outward(loft(band, R_, (False, b == 13)))
    # torso: rings along z (z, half across x, half deep y, y shift), a woman's line: hips, a narrow waist, the bust,
    # shoulders out to the shoulder joints (the upper arms' tops sit on them); the lower segment always ends inside
    # the next one's ring (no seam's cap shows). The red bodice over chest and waist, the hips red (the skirt's top)
    for b, (rings, caps) in TORSO.items():
        part = P(b, 'red')
        R_ = [(np.array([0.0, sy, z]), X, Y, hx, hy) for z, hx, hy, sy in rings]
        sides, phase = TORSO_SIDES.get(b, (8, None))
        depth = None
        if b == 13:                                # BUST_PROFILE on the bust ring, half on its neighbours
            prof, bz = BUST_PROFILE
            bi = [r[0] for r in rings].index(bz)
            def fac(i, th, amt):
                a = abs((math.degrees(th) - 270.0 + 180.0) % 360.0 - 180.0)
                return 1.0 + amt * (float(np.interp(a, [q[0] for q in prof], [q[1] for q in prof])) - 1.0)
            def depth(i, th, bi=bi):
                if math.sin(th) >= 0: return 1.0
                amt = {bi: 1.0, bi - 2: 0.5, bi + 2: 0.5}.get(i)
                if amt is not None: return fac(i, th, amt)
                if i not in (bi - 1, bi + 1): return 1.0
                # the rings between: their front on the circle through the three rings' fronts (z, y) at this angle
                (x1, y1), (x2, y2), (x3, y3) = [(rings[j][0], rings[j][3] + rings[j][2] * math.sin(th) * fac(j, th, m))
                                                for j, m in ((bi - 2, 0.5), (bi, 1.0), (bi + 2, 0.5))]
                cz, cy = np.linalg.solve([[2 * (x2 - x1), 2 * (y2 - y1)], [2 * (x3 - x1), 2 * (y3 - y1)]],
                                         [x2 * x2 - x1 * x1 + y2 * y2 - y1 * y1, x3 * x3 - x1 * x1 + y3 * y3 - y1 * y1])
                r = math.hypot(x1 - cz, y1 - cy)
                y = cy - math.sqrt(r * r - (rings[i][0] - cz) ** 2)
                return (y - rings[i][3]) / (rings[i][2] * math.sin(th))
        part.outward(loft(part, R_, (caps[0], caps[1] and b != 13), sides=sides, dark=(False, b == 15), phase=phase,
                          depth=depth))
    # the shoulder caps (SHOULDER_CAP): a dome on each upper-arm bone round its joint, the pole toward the body
    cx, cy, cu, cd, rim, n = SHOULDER_CAP
    for b in (12, 9):
        ax = -np.sign(T[LIMB[b]][0])               # toward the body, the bone's frame (the arm runs along -ax)
        cap = P(b, 'sleeve', 'cap')
        rows = []
        for lat in (90.0, 45.0):                   # the rim (pushed `rim` into the arm), a ring halfway; the pole
            row = []
            for k in range(n):
                t = 2 * math.pi * (k + 0.5) / n
                c, s_ = math.cos(math.radians(lat)), math.sin(math.radians(lat))
                hz = cu if math.sin(t) >= 0 else cd
                q = np.array([ax * (cx * c - (rim if lat == 90.0 else 0.0)), cy * s_ * math.cos(t), hz * s_ * math.sin(t)])
                nq = np.array([ax * c / cx, s_ * math.cos(t) / cy, s_ * math.sin(t) / hz])
                row.append(cap.v(q, nq))
            rows.append(row)
        pole = cap.v(np.array([ax * cx, 0.0, 0.0]), np.array([ax, 0.0, 0.0]))
        for k in range(n):
            k2 = (k + 1) % n
            cap.tri(rows[0][k], rows[1][k], rows[1][k2]); cap.tri(rows[0][k], rows[1][k2], rows[0][k2])
            cap.tri(rows[1][k], pole, rows[1][k2])
        cap.outward(np.zeros(3))
    # the fist (FIST_RINGS, FIST_FRONT, FIST_THUMB) on the right hand bone: six points a ring (the back of the hand's
    # two corners, the sides, the palm's two), the front a fan to its centre (the corners of the last ring's back are
    # the knuckle row's ridge), the thumb a three-sided bar across the palm side's front
    fist = P(10, 'glove', 'fist')
    def fring(x, hy, zb, zp, sy):
        zm = (zb + zp) / 2
        pts = [(sy - 0.6 * hy, zb), (sy + 0.6 * hy, zb), (sy + hy, zm), (sy + 0.6 * hy, zp), (sy - 0.6 * hy, zp),
               (sy - hy, zm)]
        return [np.array([x, y, z]) for y, z in pts], np.array([x, sy, zm])
    rings = [fring(*r) for r in FIST_RINGS]
    ids = [[fist.v(p, p - c) for p in ps] for ps, c in rings]
    for a, b_ in zip(ids, ids[1:]):
        for k in range(6):
            k2 = (k + 1) % 6
            fist.tri(a[k], b_[k], b_[k2]); fist.tri(a[k], b_[k2], a[k2])
    ps, c = rings[-1]
    fc = np.array([FIST_FRONT[0], c[1], FIST_FRONT[1]])
    f0 = fist.v(fc, (-1.0, 0.0, 0.0))
    fr = [fist.v(p, (p - c) * 0.6 + np.array([-1.0, 0.0, 0.0])) for p in ps]   # the front's own normals: the ridge
    for k in range(6): fist.tri(f0, fr[k], fr[(k + 1) % 6])
    fist.outward(np.array([-1.5, -0.3, 0.3]))
    (tx, ty, tz), ty1, tr = FIST_THUMB
    thumb = P(10, 'thumb')
    tri3 = [np.array([0.0, 0.0, tr]), np.array([-tr, 0.0, -0.4 * tr]), np.array([tr, 0.0, -0.4 * tr])]
    e0 = [thumb.v(np.array([tx, ty, tz]) + d, d) for d in tri3]
    e1 = [thumb.v(np.array([tx, ty1, tz]) + d, d) for d in tri3]
    for k in range(3):
        k2 = (k + 1) % 3
        thumb.tri(e0[k], e1[k], e1[k2]); thumb.tri(e0[k], e1[k2], e0[k2])
    thumb.outward(np.array([tx, (ty + ty1) / 2, tz]))
    # the neckline: a shallow rounded scoop (the neck ring's two front points dropped and moved out onto the bodice's
    # surface), the top closed in the turtleneck's grey from the ring up to the collar (a fan: from the front its
    # slope fills the scoop, the turtleneck rising above it)
    sz, sk, sc = SCOOP
    top_z, _, _, top_y = TORSO[13][0][-1]
    bod = plain[13, 'red', '']
    ring_ix = [i for i, p in enumerate(bod.p) if abs(p[2] - top_z) < 1e-6]
    for i in ring_ix:
        p = bod.p[i]
        if p[1] < top_y - 2.0: bod.p[i] = np.array([p[0] * sk, top_y + (p[1] - top_y) * sk, sz])
    cap = Part(); c0 = cap.v(np.array(sc), (0.0, -0.3, 1.0))
    rim = sorted(ring_ix, key=lambda i: math.atan2(bod.p[i][1] - top_y, bod.p[i][0]))
    ids = [cap.v(bod.p[i], (bod.p[i] - np.array(sc)) * np.array([0.3, 0.3, 1.0]) + np.array([0, 0, 0.6])) for i in rim]
    for k in range(len(ids)): cap.tri(c0, ids[k], ids[(k + 1) % len(ids)])
    cap.outward(np.array([sc[0], top_y, 10.0])); plain[13, 'grey', 'scoop'] = cap
    # the bust's painted shade (BUST_SHADE): a factor per bodice vertex by its ring and its angle from the front
    rz = {r[0]: r for r in TORSO[13][0]}
    bod.k = []
    for p in bod.p:
        r = next((rz[z] for z in BUST_SHADE if abs(p[2] - z) < 1e-6), None)
        if r is None or p[1] > r[3]: bod.k.append(1.0); continue
        a = math.degrees(math.asin(min(1.0, abs(p[0]) / r[1])))
        tab = BUST_SHADE[r[0]]
        bod.k.append(float(np.interp(a, [q[0] for q in tab], [q[1] for q in tab])))

    def to_thigh(src, b):                         # pelvis frame -> thigh b's (x down the leg, y the same, z outward)
        h = T[b]; dst = Part()
        m = (lambda q: np.array([-q[2], q[1], q[0]])) if b == 2 else (lambda q: np.array([q[2], q[1], -q[0]]))
        for p, n in zip(src.p, src.n): dst.v(m(p - h), m(n))
        dst.t = list(src.t); return dst
    # the skirt: front and back panels (a tabard's), split at the sides, from the hips to about mid-calf, slightly
    # flared, both sides drawn (the inside shows through the slits); on the pelvis, or each half on its thigh
    for name, (a0, a1, n) in SKIRT_ARC.items():
        ths = [a0 + (a1 - a0) * j / n for j in range(n + 1)]
        h0, h1 = SKIRT_HEM[name]
        deep = lambda z, name=name: SKIRT_BACK_HIP[1] if name == 'back' and z is not None and z >= SKIRT_BACK_HIP[0] \
            else SKIRT_DEEP[name]
        grid = [[np.array([rx * math.cos(math.radians(t)), sy + deep(z) * ry * math.sin(math.radians(t)),
                           z if z is not None else h0 + (h1 - h0) * j / n]) for j, t in enumerate(ths)]
                for z, rx, ry, sy in SKIRT]
        nrm = [[np.array([math.cos(math.radians(t)) / rx, math.sin(math.radians(t)) / (deep(z) * ry), 0.02])
                for t in ths] for z, rx, ry, sy in SKIRT]
        mid = [math.cos(math.radians((ths[j] + ths[j + 1]) / 2)) for j in range(n)]
        halves = [(15, range(n))] if SKIRT_ON[name] == 'pelvis' else \
                 [(5, [j for j in range(n) if mid[j] < 0]), (2, [j for j in range(n) if mid[j] > 0])]   # -x half on thigh 5, +x on 2
        for b, cols in halves:
            out, inn = Part(), Part()
            for a, b2, na, nb in zip(grid, grid[1:], nrm, nrm[1:]):
                for j in cols:
                    ids = [out.v(p, nn) for p, nn in ((a[j], na[j]), (b2[j], nb[j]), (b2[j + 1], nb[j + 1]),
                                                       (a[j + 1], na[j + 1]))]
                    out.tri(ids[0], ids[1], ids[2]); out.tri(ids[0], ids[2], ids[3])
            out.outward(np.array([0.0, 0.2, -20.0])); two_sided(out, inn)
            if b != 15: out, inn = to_thigh(out, b), to_thigh(inn, b)
            plain[b, 'red', 'skirt_' + name] = out; plain[b, 'redin', 'skirt_' + name] = inn
    # the hips closed at the sides down to the slits' top (on the pelvis): the thighs' tops stay under the skirt
    zs, n, lap, kin = SKIRT_SIDE
    zk = [r[0] for r in SKIRT[:-1]][::-1]
    rows = [r for r in SKIRT[:-1] if r[0] > zs] + [(zs,) + tuple(float(np.interp(zs, zk, [r[i] for r in SKIRT[:-1]][::-1]))
                                                         for i in (1, 2, 3))]
    for side, (a0, a1) in enumerate(((SKIRT_ARC['back'][1], SKIRT_ARC['front'][0]),
                                     (SKIRT_ARC['front'][1], SKIRT_ARC['back'][0] + 360.0))):
        a0, a1 = a0 - lap, a1 + lap
        ths = [math.radians(a0 + (a1 - a0) * j / n) for j in range(n + 1)]
        kds = [SKIRT_BACK_HIP[1] + (SKIRT_DEEP['front'] - SKIRT_BACK_HIP[1]) * (j / n if side == 0 else 1 - j / n)
               for j in range(n + 1)]             # the depth from the back panel's edge to the front's
        out, inn = Part(), Part()
        g2 = [[(np.array([kin * rx * math.cos(t), sy + kin * k * ry * math.sin(t), z]),
                np.array([math.cos(t) / rx, math.sin(t) / (k * ry), 0.0])) for t, k in zip(ths, kds)]
              for z, rx, ry, sy in rows]
        for r in range(len(rows) - 1):
            for j in range(n):
                ids = [out.v(*g2[i][k]) for i, k in ((r, j), (r + 1, j), (r + 1, j + 1), (r, j + 1))]
                out.tri(ids[0], ids[1], ids[2]); out.tri(ids[0], ids[2], ids[3])
        out.outward(np.array([0.0, 0.2, -6.0])); two_sided(out, inn)
        plain[15, 'red', 'hip%d' % side] = out; plain[15, 'redin', 'hip%d' % side] = inn
    # head: ours (head_model.py with HEAD's constants), over the turtleneck's axis a little forward of it, the chin
    # just above the collar's top; the face a texture wrapped round its front, the rest bare skin; her neck inside the
    # turtleneck; the hair (the 'long' style) on the head and, its fall, on the chest
    head_parts, face_png = head_model.head(HEAD, T, (0.5, TORSO[13][0][-1][3]), COLLAR[-1][0], checker)

    # vertex colours: one light from above-front in each bone's frame, each colour shaded unlit .. lit
    def shade(b, n, base, hi=None, amb=0.0):
        L = up[b] * 0.8 + np.array([0, -0.6, 0]); L /= np.linalg.norm(L)
        k = max(0.0, float(n @ L))
        if hi is None: return np.clip(base * (amb + (1 - amb) * k), 0, 255)
        return np.clip(base + (hi - base) * k, 0, 255)
    WHITE = np.array((255.0, 255.0, 255.0))
    prims = {}                                     # bone -> [(part, material, colour fn)]
    for (b, kind, _), part in plain.items():
        if kind in BASE:
            lo, hi = SHADE[kind]
            fn = lambda n, b=b, kind=kind, lo=lo, hi=hi: shade(b, n, BASE[kind] * lo, BASE[kind] * hi)
        else:
            fn = {'redin': lambda n, b=b: shade(b, n, RED_IN * 0.8, RED_IN * 1.1),
                  'thumb': lambda n, b=b: shade(b, n, GLOVE * SHADE['glove'][0] * THUMB_SHADE,
                                                GLOVE * SHADE['glove'][1] * THUMB_SHADE)}[kind]
        prims.setdefault(b, []).append((part, 0, fn))
    for b, ps in head_parts.items():               # the head's parts, shaded by head_model; the face material 1
        prims.setdefault(b, []).extend((dict(q, material=1 if q['face'] else 0), None, None) for q in ps)
    # Dash's meshes: one texture per guard bone and texture record, recoloured texel by texel by where on the model
    # it lies (texel_class); their vertex colours the baked light on white (the texture carries the colour)
    def texel_class(g, p):
        if g in LIMB:
            L = np.linalg.norm(T[LIMB[g]]); t_ = float(p @ T[LIMB[g]]) / L
            if g in (12, 9): return 'red' if ARM_BAND[0] <= t_ <= ARM_BAND[1] else 'sleeve'
            if g in (11, 8): return 'sleeve' if t_ < GLOVE_AT * L else 'glove'
        return TEX_KIND[g]
    mats, png_ix = [{'name': 'PLAIN', 'png': None}, {'name': 'FACE', 'png': face_png}], {}
    for g, items in sorted(dash.items()):
        for rec in dict.fromkeys(q[4] for q in items):
            qs = [q for q in items if q[4] == rec]
            src = dash_texture(E, rec)
            cover, tpos = texel_map(src.shape[1], src.shape[0], [(q[0], q[2], q[3]) for q in qs])
            png = recolour(src, cover, tpos, lambda p, g=g: texel_class(g, p))
            if png not in png_ix: png_ix[png] = len(mats); mats.append({'name': f'DASH_{len(mats):02d}', 'png': png})
            for pos, nrm, uv, tris, _, d in qs:
                part = Part(); part.p, part.n, part.uv, part.t = list(pos), list(nrm), [tuple(u) for u in uv], \
                    [tuple(int(v) for v in t_) for t_ in tris]
                prims.setdefault(g, []).append((part, png_ix[png], lambda n, g=g: shade(g, n, WHITE, amb=DASH_AMB)))

    doc = {'nodes': [], 'scene': [], 'meshes': [], 'materials': mats}
    for i in range(BONES):
        doc['nodes'].append({'name': f'bone_{i:02d}', 'translation': T[i].tolist(), 'children': children[i]})
    for b in range(BONES):
        if b not in prims: continue
        ps = []
        for part, mat, fn in prims[b]:
            if isinstance(part, dict):
                ps.append({k: part[k] for k in ('pos', 'col', 'uv', 'idx', 'material')}); continue
            ps.append({'pos': np.array(part.p), 'col': np.array([list(np.clip(fn(n) * k, 0, 255) / 255) + [1.0]
                                   for n, k in zip(part.n, getattr(part, 'k', [1.0] * len(part.n)))]),
                       'uv': np.array(part.uv, float) if mat else None,
                       'idx': np.array(part.t), 'material': mat})
        doc['nodes'][b]['mesh'] = len(doc['meshes']); doc['meshes'].append(ps)
    doc['scene'] = [parent.index(-1)]
    return doc, T, guard_box


def check(path, T, box):
    """The Validate lines: 17 bone_NN nodes with her translations (the dump's, her_skeleton's shoulders) +- 0.001, <= 1600 triangles, every vertex of
    ours in its bone's guard box widened by 30 % (the game's meshes, materials DASH_*, are Dash's own shapes: not
    held to the guard's boxes); on the pelvis and the thighs (the skirt's panels) a vertex may lie past the box
    downward only (pelvis -z, a thigh along it toward the knee), down to mid-calf (the hip + the thigh + half the calf)."""
    g = gltf.read(path)
    names = {n['name']: n for n in g['nodes']}
    for i in range(BONES):
        n = names.get(f'bone_{i:02d}')
        assert n is not None, f'no bone_{i:02d}'
        assert np.abs(np.array(n['translation'] or (0, 0, 0)) - T[i]).max() <= 0.001, f'bone_{i:02d} translation'
    calf = lambda th: np.linalg.norm(T[LIMB[th]]) + 0.5 * np.linalg.norm(T[LIMB[LIMB[th]]])   # hip to mid-calf
    down = {15: (2, -1, T[2][2] - calf(2)), 2: (0, 1, calf(2)), 5: (0, -1, -calf(5))}  # axis, sign, the limit
    tris, game, worst = 0, 0, -1e9
    for i in range(BONES):
        n = names[f'bone_{i:02d}']
        if n['mesh'] is None: continue
        lo, hi = box[i]; c, h = (lo + hi) / 2, (hi - lo) / 2 * 1.3
        if i in (5, 2):                            # her thighs' joints GURI_HIP_OUT out (her_skeleton): the box kept
            from guri_moves_trop import GURI_HIP_OUT  # where the guard's thigh is in the body (thigh z = outward)
            c = c - np.array([0.0, 0.0, GURI_HIP_OUT])
        for p in g['meshes'][n['mesh']]:
            tris += len(p['idx'])
            if g['materials'][p['material']]['name'].startswith('DASH'): game += len(p['idx']); continue
            o = np.abs(p['pos'] - c) - h
            if i in down:                          # past the box downward: allowed to the limit
                ax, sg, lim = down[i]
                v = p['pos'][:, ax]
                below = sg * (v - c[ax]) > 0
                o[below, ax] = np.where(sg * v[below] <= sg * lim, -np.inf, sg * (v[below] - lim))
            out = o.max()
            worst = max(worst, out)
            assert out <= 0, f'bone_{i:02d}: a vertex {out:.2f} outside its widened box'
    # 1600: the old 1500 had no recorded reason and the bust's two arc rings needed 1595 (guri.bin 69 KB of its 128 KB)
    assert tris <= 1600, tris
    clear = fall_clear(g)
    assert clear >= MIN_FALL_CLEAR, f'the hair\'s fall {clear:+.2f} from the bodice\'s back (< {MIN_FALL_CLEAR})'
    print(f'check: 17 bones ok, {tris} triangles ({game} of them the game\'s), our vertices inside the widened boxes '
          f'(margin {-worst:.2f}), the hair\'s fall {clear:+.2f} clear of the bodice\'s back')
    return tris


def fall_clear(g):
    """The hair's fall against the bodice's back (chest bone 13, rest pose): every 1.0 up its rows, the fall's back y
    on the middle line (x 0) minus the bodice's; the least of them (> 0: the hair outside)."""
    n = next(x for x in g['nodes'] if x['name'] == 'bone_13')
    hair, red = [], []
    for p in g['meshes'][n['mesh']]:
        if p['col'] is None: continue
        c = p['col'][:, :3].mean(0)
        if c[0] > 2.5 * c[1]: red.append(p)
        elif c[1] > 0.4 * c[0] and c[2] < 0.6 * c[1]: hair.append(p)
    def back_y(parts, z):                          # the largest y where the triangles cut by the plane z cross x 0
        best = None
        for p in parts:
            for t in p['idx']:
                a = p['pos'][list(t)]
                qs = [a[i] + (a[(i + 1) % 3] - a[i]) * (z - a[i][2]) / (a[(i + 1) % 3][2] - a[i][2]) for i in range(3)
                      if (a[i][2] - z) * (a[(i + 1) % 3][2] - z) <= 0 and a[i][2] != a[(i + 1) % 3][2]]
                if len(qs) >= 2 and qs[0][0] * qs[1][0] <= 0 and qs[0][0] != qs[1][0]:
                    y = qs[0][1] + (qs[1][1] - qs[0][1]) * -qs[0][0] / (qs[1][0] - qs[0][0])
                    best = y if best is None else max(best, y)
        return best
    zs = [z for p in hair for z in p['pos'][:, 2]]
    out = []
    for z in np.arange(max(min(zs), -1.5) + 0.05, max(zs), 1.0):
        h, b = back_y(hair, z), back_y(red, z)
        if h is not None and b is not None: out.append(h - b)
    return min(out)


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'guri.gltf')
    doc, T, box = build(dump_ram(sys.argv[1]), bool(os.environ.get('GURI_CHECKER')))
    gltf.write(out, doc)
    print('wrote', out)
    check(out, T, box)
