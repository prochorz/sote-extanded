/* Ledge hang (on foot only, optional: build.py --without hang leaves it out).
 *
 * When Dash runs or walks off a ledge (no jump) over a drop of twice his height or more, he
 * catches the edge and hangs on his left hand; in a jump he catches the rim of a wall ahead
 * that his hands reach. Stick up puts the right hand on the rim too and climbs onto the ledge,
 * stick down lets go (over a floor: a jump down). The poses are our own animation "hang" (a copy of his jetpack animation's block
 * with our own tracks, rewritten every frame from keyframe tables), fed to set_anim through our
 * own animation controller while he hangs.
 * Hooks of its own: the Humn control function end (ctl_ctrl_end) and set_anim (ctl_setanim).
 * Design and tuning history: docs/ledge-falls.md. */
#include "common.h"

/* One out-of-line copy of the math (the common.h versions are inline: ~250 bytes per call). */
static __attribute__((noinline)) float sin_h(float x) { return sin_r(x); }
static float cos_h(float x) { return sin_h(x + PI_F / 2); }
static __attribute__((noinline)) float atan2_h(float y, float x) { return atan2_r(y, x); }
static __attribute__((noinline)) float wrap_h(float a) { return wrap180(a); }

#define HANG_TRIGGER     0.05f    /* grab once this far below the last floor... */
#define HANG_REACH       10.0f    /* ...but not after falling further than this */
#define HANG_SLIDE       25.0f    /* he flies off a run this far out; the edge is traced back */
#define HANG_DEPTH       13.0f    /* only over drops this deep (about twice his height), not a step */
#define HANG_BELOW       6.4f     /* feet this far below the edge while hanging (hand on it) */
#define HANG_OUT         1.55f    /* body this far out from the lip: wrists just outside it, fingers over */
#define BODY_LIFT        5.5f     /* the drawn body matrix sits this far above his feet */
#define HANG_STICK       40.0f    /* stick y past this: up climbs, down lets go */
#define HANG_FRAME       10.0f    /* fallback pose: jetpack frame, body straight, one arm up */
#define HANG_DIP         0.8f     /* catching the edge: drop this far below the hang point... */
#define HANG_FALL_T      0.20f    /* ...in this many seconds (swinging in under the edge)... */
#define HANG_CATCH_T     0.15f    /* ...then ease back up in this many */
#define CATCH_SWING_T    0.38f    /* catching: reach, grab (at HANG_FALL_T), legs swing back... */
#define CATCH_END_T      0.58f    /* ...and settle into the hang (end times, seconds) */
#define HANG1_DROP       0.33f    /* on one hand, the straight arm: body this much lower */
#define SWAY_T           2.6f     /* hanging on one hand: one sway there and back, seconds */
#define CLIMB_REACH_T    0.30f    /* climbing: first the right hand up to the rim, then... */
#define CLIMB_PULL_T     0.35f    /* ...pull up, chin to the rim... (from the end of the reach) */
#define CLIMB_MANTLE_T   0.65f    /* ...chest over it, one knee up... */
#define CLIMB_END_T      0.95f    /* ...onto the ledge, crouching (end times, seconds) */
#define CLIMB_PULL_UP    2.1f     /* rise by the pull-up: the hands stay on the rim */
#define CLIMB_MANTLE_UP  4.3f     /* rise by the mantle */
#define HANG_POSE_TURN   180.0f   /* the borrowed frames have the body turned round on its root */
#define DROP_OUT         3.0f     /* letting go: drift this far out from the wall... */
#define DROP_OUT_T       0.40f    /* ...in this long (the fall pose leans head first toward it) */
#define HANG_SPIN_T      0.20f    /* catching the edge: turn round to face the cliff in this long */
#define HANG_CAM_SIDE    40.0f    /* hanging: the camera looks at him this far off his back... */
#define HANG_CAM_DIST    8.0f     /* ...if the game camera fits there: it sits this far out, traced */
#define HANG_CAM_RAY_Z   6.2f     /* level from this high above his feet (camera code 0x80061774) */
#define STEP_PROBE       0.75f    /* open stairs: rays down every this far ahead of him... */
#define STEP_REACH       3.0f     /* ...up to this far; a floor there is the next step... */
#define STEP_UP          3.0f     /* ...if it is no higher above his feet than this */
#define EDGE_BACK        3.0f     /* edge search starts this far back from his last floor point */
#define EDGE_STEP        0.25f    /* the walk to the rim: steps this long... */
#define EDGE_SLOPE       0.25f    /* ...climbing or dropping at most this much each (45 degrees) */
#define JUMP_PLUMB       0.75f    /* jump catch: the face 3 and 5 under the rim this near its gap 1 under */
#define JUMP_CLEAR       3.0f     /* jump catch: no floor this far under his feet */
#define NARROW           6.0f     /* no catch in a shaft: a wall this close behind him */
#define CLIMB_FLOOR      0.6f     /* a climb ends on floor at most this below the rim... */
#define CLIMB_UP         2.0f     /* ...and at most this above it (a path rising from the rim: he could not climb) */
#define CLIMB_SLOPE      0.75f    /* ...and rises at most this much 1.5 further in (no slope toward the rim) */
#define FREE_WIDE        8.0f     /* free hang: floor this far in behind the rim (no narrow bridge) */
#define FREE_SIDE        1.5f     /* free hang: clear this far to either side of the rim and his body */
#define FACE_DEEP        1.0f     /* the wall under the rim may be this much further in (undercut) */
#define EDGE_TURN_COS    0.82f    /* face a slanted rim square on if within ~35 degrees of his way */
#define JUMP_VZ          1.0f     /* rising faster than this: he jumped (A may be up already) */
#define DROP_T           3.0f     /* let go: hold him under the edge for at most this long */
#define DROP_FREE_T      0.5f     /* let go but still standing at the hang height this long: landed */
#define DROP_FLOOR       60.0f    /* let go with a floor this near below: a jump down, not a death fall */
#define GRAVITY          30.0f    /* units/s^2 in the air (measured: vz -1 -> -12 in 0.37 s) */
#define LAND_STEP        0.05f    /* flight prediction: look for a floor every this many seconds */
#define LAND_DV          2.0f     /* ...again when his velocity changes by more (hit a wall) */
#define LAND_UP          1.5f     /* a floor this far above his path still takes him (the game
                                     lifts him onto it: +1.1 seen) */
#define LAND_MISS        1.5f     /* this far below both floors he didn't make it: catch again */
#define JUMP_WALL        2.5f     /* in a jump: a wall at most this far ahead of him... */
#define JUMP_RAY_Z       2.0f     /* ...looked for this high above his feet... */
#define JUMP_REACH_LO    2.0f     /* ...with its rim at least this far above his feet (lower he lands
                                     on it)... */
#define JUMP_REACH_HI    7.2f     /* ...and no higher than his hands reach */

uint32_t g_hang_state;        /* exported for tests */
int g_hang_drop;              /* let go (or killed) and falling from the hang; for tests too */

struct anim_desc { int32_t id; uint32_t name; float start, blend, fps, a, b; int32_t next, kind; };
struct anim_ctrl { float time; struct anim_desc *cur, *list; };

#define HANG_ANIM_ID  0x7F
#define CLIMB_ANIM_ID 0x7E
static struct anim_desc hang_anims[4] = {
    /* kind 0: lowest priority, so the game's next animation may replace it right away;
     * frames/s 0: frozen on the start frame */
    { HANG_ANIM_ID, 0x666C7979 /* flyy */, HANG_FRAME, 0.0f, 0.0f, 0.0f, 0.0f, -1, 0 },
    { CLIMB_ANIM_ID, 0x63726F75 /* crou */, 4.0f, 0.0f, 0.0f, 0.0f, 0.0f, -1, 0 },
    { -1 },
    { -2 },                                         /* "nothing playing": forces a switch */
};
static struct anim_ctrl hang_ctrl = { 0, &hang_anims[3], hang_anims };
static uint32_t g_game_anim_ctrl;                   /* the controller the game uses for Dash */

/* ---- Our own animation "hang" ----
 * An animation block (one per animation, chained from Dash's +0x19C, found by name) holds a
 * 0xA0-byte entry per bone from +0x38: +0x08 model node, +0x0C next entry, +0x10 the bone's
 * current angles, +0x70/74/78 rotation tracks (degrees about z, x, y; one float per frame,
 * frame f at index f - 1), +0x88/8C/90 translation tracks (root and scale bone only).
 * Ours is a copy of Dash's "flyy" block (same skeleton and nodes) whose tracks point to two-frame
 * arrays holding the pose. While he hangs it is put at the head of his chain. */
#define ANIM_BLOCK_SIZE 0xC18
#define ANIM_BONES      19
#define POSE_TRACKS     54
#define TAG_FLYY        0x666C7979u
#define TAG_HANG        0x68616E67u
static const uint8_t track_slot[6] = { 0x70, 0x74, 0x78, 0x88, 0x8C, 0x90 };
/* The tracks each bone has (bit k: track_slot[k]); a pose holds them in this order. */
static const uint8_t track_mask[ANIM_BONES] = {
    0x38, 7, 7, 1, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0x30,
};
/* A pose: the value of every track (degrees, translations in units) x 100. Per line: root, head,
 * neck; left hand, forearm, shoulder; the right arm; chest, spine, one leg; the other leg,
 * pelvis, model root. */
typedef int16_t pose_t[POSE_TRACKS];
/* flyy frame 10 (body straight, legs down, left arm up); the right arm (bones 8, 7, 6) is the
 * left one (5, 4, 3) mirrored: across the body's x plane, angles (z, x, y) -> (-z, x, -y). */
static const pose_t hang_pose = {
    -90, -330, 443,  0, -1400, 0,  10, -600, 141,
    5500,  -3575, -202, 2381,  -17305, -4458, -10115,
    -5500, 0, 0,  3575, -202, -2381,  17305, -4458, 10115,
    0, -402, 0,  0, 79, 0,  -3300, -200, 0,  -100, -4, -200,  0, -1100, -8500,
    3300, -600, 0,  900, 0, 200,  519, -1642, 8545,  0, 1100, 0,  8, 261,
};
/* The climb: hang_pose, then these, blended (smoothstep) at CLIMB_PULL_T, CLIMB_MANTLE_T and
 * CLIMB_END_T. Made offline from the hang pose with Dash's skeleton (harness/pose/): the arms by
 * inverse kinematics so the hands stay where they hold the rim while the body rises. */
static const pose_t climb_keys[3] = {
    {   /* pull up: chin to the rim, elbows out */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        -1700,  -7888, -4266, 7485,  -14519, -12308, -12159,
        1700, 0, 0,  7648, -4154, -7457,  14659, -12265, 12015,
        0, -402, 0,  0, 579, 0,  -3300, -200, 0,  -1600, -4, -200,  0, -2100, -8500,
        3300, -600, 0,  2900, 0, 200,  519, -3142, 8545,  0, 1100, 0,  8, 261,
    },
    {   /* mantle: chest over the rim, arms pushing, one knee up */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        -1700,  -3465, -56, 4829,  -16429, -13841, -10551,
        1700, 0, 0,  3365, -89, -4279,  16528, -13664, 10304,
        0, 598, 0,  0, 2579, 0,  -3300, -200, 0,  -3100, -4, -200,  0, -3100, -8500,
        3300, -600, 0,  10900, 0, 200,  519, -11142, 8545,  0, 1100, 0,  8, 261,
    },
    {   /* crouch on the ledge (crou frame 9, hands on knees) */
        -31, -358, 158,  1212, -2927, 468,  -3636, 109, -1126,
        -1700,  -6632, -2813, 7272,  -17581, -11875, -10380,
        1700, 0, 0,  4161, -693, -5270,  14374, -15120, 11264,
        1730, 1194, 130,  883, 3643, -271,  2307, -3201, -439,  -13833, -832, -19,  -930, -4134, -7752,
        -3582, -1433, 2039,  14117, -310, -302,  -12041, -7400, -4781,  0, 1100, 0,  8, 104,
    },
};
/* The catch: these, then hang1_keys[0], at 0, HANG_FALL_T (the left hand takes the rim at the
 * bottom of the dip), CATCH_SWING_T and CATCH_END_T. Made like climb_keys (harness/pose/onehand.py). */
static const pose_t catch_keys[3] = {
    {   /* reaching for the rim with the left hand, the right arm out */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        5500,  882, 1699, 5664,  -14811, -5789, -13167,
        0, 0, 0,  4175, -1072, -4393,  12752, -7852, 11550,
        0, -402, -480,  0, -721, -720,  -3300, -200, 0,  -3600, -4, -200,  0, -3100, -8500,
        3300, -600, 0,  7600, 0, 200,  519, -6142, 8545,  -2200, 1100, 0,  8, 261,
    },
    {   /* grabbed it: arm straight, legs swing out */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        5500,  -508, 1075, 2293,  -15360, -2565, -10897,
        0, 0, 0,  3381, -829, -6349,  19714, -17437, 18871,
        0, -402, -480,  0, 79, -720,  -3300, -200, 0,  -1300, -4, -200,  0, 900, -8500,
        3300, -600, 0,  4600, 0, 200,  519, -642, 8545,  -2200, 1100, 0,  8, 261,
    },
    {   /* swinging back toward the wall */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        5500,  -508, 1075, 2293,  -15360, -2565, -10897,
        0, 0, 0,  2501, 538, -4552,  13315, -16585, 11467,
        0, -402, -480,  0, 479, -720,  -3300, -200, 0,  -2100, -4, -200,  0, -2100, -8500,
        3300, -600, 0,  5100, 0, 200,  519, -4642, 8545,  -2200, 1100, 0,  8, 261,
    },
};
/* Hanging on the left hand only (the body under it, turned side-on, the right arm down): two
 * extremes he sways between, and the climb's first key, the right hand coming up to the rim.
 * Made like catch_keys (harness/pose/onehand.py). */
static const pose_t hang1_keys[3] = {
    {   /* one hand (sway A) */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        5500,  -508, 1075, 2293,  -15360, -2565, -10897,
        0, 0, 0,  2501, 538, -4552,  13315, -16585, 11467,
        0, -402, -480,  0, 79, -720,  -3300, -200, 0,  -100, -4, -200,  0, -1100, -8500,
        3300, -600, 0,  3100, 0, 200,  519, -3142, 8545,  -2200, 1100, 0,  8, 261,
    },
    {   /* one hand (sway B) */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        5500,  -312, 1132, 2248,  -15153, -2212, -10938,
        0, 0, 0,  2318, 686, -4678,  13715, -16667, 11348,
        0, -402, -360,  0, 79, -540,  -3300, -200, 0,  -100, -4, -200,  0, -1100, -8500,
        3300, -600, 0,  3100, 0, 200,  519, -3142, 8545,  -3000, 1100, 0,  8, 261,
    },
    {   /* climb start: the right hand coming up */
        -90, -330, 443,  0, -1400, 0,  10, -600, 141,
        5500,  -537, 905, 3610,  -15181, -2611, -11438,
        0, 0, 0,  6313, -3823, -4095,  14517, -6285, 11019,
        0, -402, -240,  0, 79, -360,  -3300, -200, 0,  -100, -4, -200,  0, -1100, -8500,
        3300, -600, 0,  2000, 0, 200,  519, -2392, 8545,  -1100, 1100, 0,  8, 261,
    },
};
static uint32_t hang_block[ANIM_BLOCK_SIZE / 4];
static float hang_tracks[POSE_TRACKS][2];
static float climb_from[POSE_TRACKS];               /* the pose the climb starts from */

/* Our animation's frame: pose a (0: climb_from) blended into pose b by u (0..1). Written every
 * frame while he hangs or climbs (before set_anim evaluates it), so the block only points at
 * these arrays. */
static void hang_anim_pose(const int16_t *a, const int16_t *b, float u) {
    u = u * u * (3 - 2 * u);
    for (int i = 0; i < POSE_TRACKS; i++) {
        float from = a ? a[i] * 0.01f : climb_from[i];
        hang_tracks[i][0] = hang_tracks[i][1] = from + (b[i] * 0.01f - from) * u;
    }
}

static int in_block(uint32_t w, uint32_t b) { return w >= b && w < b + ANIM_BLOCK_SIZE; }

/* Copy Dash's flyy block into hang_block with our tracks; 0 if his skeleton isn't the one
 * the pose was made for. */
static int hang_anim_build(uint32_t flyy) {
    uint32_t dst = (uint32_t)hang_block;
    for (int i = 0; i < ANIM_BLOCK_SIZE / 4; i++) {
        uint32_t w = U32(flyy + 4 * i);
        hang_block[i] = in_block(w, flyy) ? w - flyy + dst : w;   /* pointers inside the block */
    }
    U32(dst + 0x1C) = TAG_HANG;
    U32(dst + 0x14) = 0;
    F32(dst + 0x2C) = 2.0f;                         /* two frames, both the pose */
    U32(dst + 0x30) = 2;
    uint32_t e = dst + 0x38;
    float (*track)[2] = hang_tracks;
    for (int b = 0; b < ANIM_BONES; b++, e += 0xA0) {
        if (!in_block(e, dst) || (b < ANIM_BONES - 1 && U32(e + 0x0C) != e + 0xA0)) return 0;
        for (int k = 0; k < 6; k++) {
            int has = valid_ptr(U32(e + track_slot[k]));
            if (has != ((track_mask[b] >> k) & 1)) return 0;
            if (!has) continue;
            U32(e + track_slot[k]) = (uint32_t)*track++;
        }
    }
    if (U32(e - 0xA0 + 0x0C)) return 0;             /* more bones than expected */
    return 1;
}

/* Put "hang" at the head of Dash's animation chain; 0: use the flyy frame instead. */
static int hang_anim_link(uint32_t obj) {
    uint32_t dst = (uint32_t)hang_block, head = U32(obj + OBJ_ANIM_CHAIN);
    if (head == dst) return 1;
    uint32_t b = head;
    for (int i = 0; i < 40 && valid_ptr(b) && U32(b + 0x1C) != TAG_FLYY; i++) b = U32(b + 0x14);
    if (!valid_ptr(b) || U32(b + 0x1C) != TAG_FLYY) return 0;
    /* Rebuilt every time: blocks (and the model nodes they point to) move with each level. */
    if (!hang_anim_build(b)) return 0;
    U32(dst + 0x14) = head;
    U32(obj + OBJ_ANIM_CHAIN) = dst;
    return 1;
}

/* No blaster while hanging: the right hand's model node (+0x0C count, +0x10 list of child
 * pointers) holds the hand mesh and the weapon mesh (first word bit 0x80). Point the node at
 * our own list without the weapon meshes; hang_end puts the game's list back. */
#define HAND_R          6                           /* bone entry of the right hand */
#define MESH_WEAPON     0x80u
static uint32_t hand_node, hand_count, hand_list, hand_kept[4];

static void hide_weapon(void) {
    if (hand_node) return;
    uint32_t node = U32((uint32_t)hang_block + 0x38 + 0xA0 * HAND_R + 0x08);
    if (!valid_ptr(node)) return;
    uint32_t n = U32(node + 0x0C), list = U32(node + 0x10), kept = 0;
    if (!valid_ptr(list) || n > 4) return;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = U32(list + 4 * i);
        if (!(valid_ptr(c) && (U32(c) & MESH_WEAPON))) hand_kept[kept++] = c;
    }
    if (kept == n) return;                          /* nothing in his hand */
    hand_node = node; hand_count = n; hand_list = list;
    U32(node + 0x10) = (uint32_t)hand_kept;
    U32(node + 0x0C) = kept;
}

static void show_weapon(void) {
    if (!hand_node) return;
    if (U32(hand_node + 0x10) == (uint32_t)hand_kept) {
        U32(hand_node + 0x0C) = hand_count;
        U32(hand_node + 0x10) = hand_list;
    }
    hand_node = 0;
}

static void hang_anim_unlink(uint32_t obj) {
    show_weapon();
    if (U32(obj + OBJ_ANIM_CHAIN) == (uint32_t)hang_block) U32(obj + OBJ_ANIM_CHAIN) = U32((uint32_t)hang_block + 0x14);
}

struct hang_state {
    float ground[3];          /* last position standing on the floor */
    int ground_ok, jumped, let_go;
    int hold_stick;           /* after climbing: ignore the stick until it's released */
    int need_center;          /* just grabbed: up/down only after the stick was centred */
    float pos[3], yaw;        /* where and facing which way he hangs */
    float wall;               /* direction toward the wall (degrees): camera looks this way */
    float face[3], in[2];     /* edge point and the direction into the ledge */
    float top[3];             /* where the last climb put him */
    float z0, t;              /* height when he caught the edge; seconds in this phase */
    float cur[3];             /* where he is held this frame */
    float edge;               /* top of the cliff face he holds (measured) */
    float yaw0, ycur;         /* heading when he caught the edge; heading this frame */
    float start[2];           /* where he was when he caught the edge */
    float drop_t;             /* seconds since letting go */
    int drop_floor;           /* ...onto a floor (jump pose and landing), not into an abyss */
    int lands;                /* this flight ends on a floor: 1 yes, 0 no, -1 not predicted yet */
    float land_v[2];          /* velocity the prediction was made with */
    float land_z;             /* height of the floor he is expected to land on... */
    float land_p[2];          /* ...and where */
    float gv[2];              /* his velocity on the last frame on the floor */
    int land_miss;            /* he was expected to land but dropped below it: catch as usual */
    int was_ground;           /* standing on the previous frame too (not just landed) */
    int jet;                  /* the jetpack fired since he last stood: no catch */
    uint32_t plat, plat_tag;  /* the object whose rim he holds, 0: the level */
    float plat_p[3];          /* its position at the catch */
    uint32_t gplat;           /* the mover he last stood on (Dash +0x70 is its collision record then) */
    float gplat_p[3];         /* its position then; H.ground moves with it until the catch */
    float probe[2];           /* where the on-rim probe last found floor under him... */
    int probe_ok, probe_skip; /* ...valid while he stands; every other frame skipped */
};
struct hang_state g_hang;     /* exported for tests */
float g_hang_gap;             /* cliff face from the hang point at the last catch (tests) */
int g_hang_moved_n;           /* tests: hangs dropped because the game moved him */
int g_hang_why;               /* tests: why the last edge search gave up (1 too far, 2 no edge, 3 a wall,
                                 4 something under the rim, 5 a floor under him,
                                 6 a free hang among girders/pipes, 7 no camera side for a free hang,
                                 8 a jump at no sheer wall, 9 nowhere to climb to (jump),
                                 10 the climb took a fallback spot, 11 let go: the object he held moved,
                                 12 a shaft: a wall behind him under NARROW) */
#define H g_hang

typedef int (*set_anim_fn)(int32_t id, int32_t flags, uint32_t ctrl, uint32_t state);
#define ANIM_STAND 0x00       /* Sstn */
#define ANIM_FALL  0x19       /* fall: dropping into an abyss */
#define ANIM_JUMP_DOWN 0x0D   /* jmpF on the way down... */
#define ANIM_JUMP_LAND 0x0E   /* ...and landing */

static void hang_end(uint32_t obj, int let_go) {
    g_hang_state = 0;
    hang_anim_unlink(obj);
    H.let_go = let_go;
    hang_ctrl.cur = &hang_anims[3];
    if (let_go) {
        /* He falls straight down the face, his back to the camera (see ctl_ctrl_end). */
        g_hang_drop = 1; H.drop_t = 0;
        float from[3] = { H.cur[0], H.cur[1], H.cur[2] + 1.0f }, to[3] = { H.cur[0], H.cur[1], H.cur[2] - DROP_FLOOR };
        H.drop_floor = trace_dist(obj, from, to) >= 0;
        H.ycur = wrap_h(H.wall - 90.0f);
        set_yaw(obj, H.ycur);
        g_target_yaw = H.ycur;
    }
    /* The game only picks an animation when its own state changes; give it the right one.
     * Its controller still believes its last animation plays, so point it at ours first. */
    if (valid_ptr(g_game_anim_ctrl)) {
        U32(g_game_anim_ctrl + 4) = (uint32_t)&hang_anims[0];
        ((set_anim_fn)SET_ANIM)(!let_go ? ANIM_STAND : H.drop_floor ? ANIM_JUMP_DOWN : ANIM_FALL, 1,
                                g_game_anim_ctrl, obj + OBJ_ANIM_STATE);
    }
}

/* Landed after letting go: the game only picks an animation when its state changes, and it
 * still believes the fall plays (he lay on the ground in it until DROP_T). Land him. */
static int dropped_onto_floor(uint32_t obj) {
    uint32_t fl = U32(obj + OBJ_FLAGS);
    return (fl & FL_GROUND) && !(fl & FL_AIR) && (F32(obj + OBJ_POS + 8) < H.cur[2] - 1.0f || H.drop_t > DROP_FREE_T);
}

static void drop_end(uint32_t obj) {
    g_hang_drop = 0;
    if (!valid_ptr(g_game_anim_ctrl)) return;
    uint32_t d = U32(g_game_anim_ctrl + 4);
    int32_t id = valid_ptr(d) ? (int32_t)U32(d) : -1;
    if (id != ANIM_FALL && id != ANIM_JUMP_DOWN && id != HANG_ANIM_ID) return;
    U32(g_game_anim_ctrl + 4) = (uint32_t)&hang_anims[0];
    ((set_anim_fn)SET_ANIM)(ANIM_JUMP_LAND, 1, g_game_anim_ctrl, obj + OBJ_ANIM_STATE);
}

void hang_abort(uint32_t obj) { if (g_hang_state) hang_end(obj, 1); }

/* The game put him somewhere else while he hung or fell from the hang (Teleport, a level
 * reload from the Cheats screen, a respawn): forget the hang, without hang_end's animation
 * switch (the game's controller may belong to the level that is gone). The game's own
 * animation was never touched while he hung (set_anim went to hang_ctrl). */
/* A mover's collision record -> the mover: +0x6C the object, whose +0x64 points back (the
 * Gall hover platform "Info"; level geometry has no such pair). 0 if not one. */
static uint32_t mover_of(uint32_t rec) {
    if (!valid_ptr(rec)) return 0;
    uint32_t o = U32(rec + 0x6C);
    return valid_ptr(o) && U32(o + 0x64) == rec ? o : 0;
}

/* The object a ray hits (0: level geometry). */
static uint32_t trace_obj(uint32_t obj, const float *from, float *to) {
    uint32_t hit = 0, hit2 = 0;
    float f[3] = { from[0], from[1], from[2] };
    float d = ((trace_fn)TRACE_FN)(to, f, U32(obj + OBJ_COLLIDER), &hit, &hit2, 0.0f, 1);
    if (d < 0) return 0;
    if (valid_ptr(hit) && hit != obj) return hit;
    uint32_t o = mover_of(hit2);
    return o != obj ? o : 0;
}

/* The object whose rim he holds moved (or is gone): let go. Riding along was tried: on
 * Suprosa's machinery it dragged him through walls; left alone, he hung in the air where a
 * Gall hover platform had been. */
static int plat_moved(void) {
    if (!H.plat) return 0;
    if (U32(H.plat) != H.plat_tag) return 1;
    float d = 0;
    for (int i = 0; i < 3; i++) { float v = F32(H.plat + OBJ_POS + 4 * i) - H.plat_p[i]; d += v * v; }
    return d > 0.05f * 0.05f;
}

static int hang_moved(uint32_t obj) {
    float dx = F32(obj + OBJ_POS) - H.cur[0], dy = F32(obj + OBJ_POS + 4) - H.cur[1];
    float dz = F32(obj + OBJ_POS + 8) - H.cur[2];
    /* Down does not count: in a slow frame the game's own fall carries him ~12 down before the
     * hold puts him back (the hang was dropped mid-catch). A teleport or a respawn moves him
     * sideways or up. */
    if (dz < 0) dz = 0;
    if (dx * dx + dy * dy + dz * dz < 5.0f * 5.0f) return 0;
    g_hang_moved_n++;
    g_hang_state = 0; g_hang_drop = 0;
    hang_anim_unlink(obj);
    hang_ctrl.cur = &hang_anims[3];
    H.ground_ok = 0; H.hold_stick = 0; H.need_center = 0; H.let_go = 0;
    return 1;
}

float g_hang_cam_off;          /* camera yaw off the wall normal, degrees (tests force angles) */
int g_hang_cam_force;          /* tests: 1 = use g_hang_cam_off as set */
extern float g_cam_facing;

int hang_cam(float *facing) {
    if (!g_hang_state && !g_hang_drop) return 0;
    *facing = wrap_h(H.wall + g_hang_cam_off);
    return 1;
}

/* Is there room for the game camera looking at the hang point along this yaw? The game traces
 * twice its distance back from him and sits at half the hit: anything within that pulls it in
 * for a close-up. */
static int cam_fits(uint32_t obj, const float *p, float facing) {
    float c = cos_h(RAD(facing)), s = sin_h(RAD(facing)), r = 2 * HANG_CAM_DIST;
    float from[3] = { p[0], p[1], p[2] + HANG_CAM_RAY_Z };
    float to[3] = { p[0] - c * r, p[1] - s * r, p[2] + HANG_CAM_RAY_Z };
    uint32_t h1 = 0, h2 = 0;
    float hit = ((trace_fn)TRACE_FN)(to, from, U32(obj + OBJ_COLLIDER), &h1, &h2, 0.0f, 0);   /* as the camera */
    return hit < 0 || hit > r - 2.0f;
}

/* Watch him from the side the camera fits on (the one it turns to least if both do); from
 * straight behind if neither. Kept until he is back on his feet. */
static void pick_cam_side(uint32_t obj) {
    if (g_hang_cam_force) return;
    float best = 0, turn = 1e9f;
    for (int side = -1; side <= 1; side += 2) {
        float f = wrap_h(H.wall + side * HANG_CAM_SIDE), d = wrap_h(f - g_cam_facing);
        if (d < 0) d = -d;
        if (d < turn && cam_fits(obj, H.pos, f)) { best = side * HANG_CAM_SIDE; turn = d; }
    }
    g_hang_cam_off = best;
}


static void set_pos(uint32_t obj, const float *p) {
    for (int i = 0; i < 3; i++) {
        F32(obj + OBJ_POS + 4 * i) = p[i];
        F32(obj + OBJ_POS_COPY + 4 * i) = p[i];
        F32(obj + OBJ_VEL + 4 * i) = 0;
    }
}

#define NO_FLOOR -1e8f

/* Floor height under (x, y) within up units above and down below z, else NO_FLOOR. */
static float floor_at(uint32_t obj, float x, float y, float z, float up, float down) {
    float from[3] = { x, y, z + up }, to[3] = { x, y, z - down };
    float hit = trace_dist(obj, from, to);
    return hit >= 0 ? z + up - hit : 2 * NO_FLOOR;
}
/* Walk from (x, y) along (dx, dy) on the floor until it ends. Steps of EDGE_STEP may climb
 * or drop EDGE_SLOPE (a slope); more is a step or a drop, not this floor (a wider window let
 * the walk run on onto a ledge below the rim). Returns how far the edge is (-1: no floor at the
 * start, or none ends within len); *ez gets its height. */
static float find_edge(uint32_t obj, float x, float y, float dx, float dy, float len, float z, float *ez) {
    z = floor_at(obj, x, y, z, 2.0f, 2.5f);
    if (z < NO_FLOOR) return -1;
    float good = 0;
    for (float t = EDGE_STEP; t <= len; t += EDGE_STEP) {
        float h = floor_at(obj, x + dx * t, y + dy * t, z, EDGE_SLOPE, EDGE_SLOPE);
        if (h > NO_FLOOR) { good = t; z = h; continue; }
        float bad = t;
        for (int i = 0; i < 4; i++) {
            float m = (good + bad) * 0.5f;
            h = floor_at(obj, x + dx * m, y + dy * m, z, EDGE_SLOPE, EDGE_SLOPE);
            if (h > NO_FLOOR) { good = m; z = h; } else bad = m;
        }
        *ez = z;
        return good;
    }
    return -1;
}

/* Does his flight end on a floor (a short gap he clears with his run-up, as in the
 * unpatched game)? Ballistic path from his velocity; under each LAND_STEP of it a floor is
 * looked for, from LAND_UP above the higher of the path and the floor he left (hitting the
 * far side fast, the game lifts him onto a rim that much higher) down to the path, until it
 * is HANG_DEPTH below the floor he left. Nothing may be in the way to that floor at its own
 * height. Made once per flight (traces are costly) and again only when his velocity changes
 * (he hit the far side). If he still drops LAND_MISS below both floors, he didn't make it:
 * the catch works as usual for the rest of the flight. */
static int will_land(uint32_t obj, float gz) {
    float vx = F32(obj + OBJ_VEL), vy = F32(obj + OBJ_VEL + 4), vz = F32(obj + OBJ_VEL + 8);
    float dx = vx - H.land_v[0], dy = vy - H.land_v[1], z = F32(obj + OBJ_POS + 8);
    if (H.land_miss) return 0;
    if (H.lands == 1 && z < (H.land_z < gz ? H.land_z : gz) - LAND_MISS) { H.land_miss = 1; return 0; }
    if (H.lands >= 0 && dx * dx + dy * dy < LAND_DV * LAND_DV) return H.lands;
    H.land_v[0] = vx; H.land_v[1] = vy; H.lands = 0;
    if (vx * vx + vy * vy < 1.0f) return 0;
    float x = F32(obj + OBJ_POS), y = F32(obj + OBJ_POS + 4), pz = z;
    for (float t = LAND_STEP; t < 2.0f; t += LAND_STEP) {
        float qx = x + vx * t, qy = y + vy * t, qz = z + vz * t - 0.5f * GRAVITY * t * t;
        if (qz < gz - HANG_DEPTH) break;
        float from[3] = { qx, qy, (pz > gz ? pz : gz) + LAND_UP }, to[3] = { qx, qy, qz - 0.3f };
        float hit = trace_dist(obj, from, to);
        if (hit >= 0) {
            float fz = from[2] - hit;
            float a[3] = { x, y, fz + 1.0f }, b[3] = { qx, qy, fz + 1.0f };
            if (trace_dist(obj, a, b) < 0) { H.lands = 1; H.land_z = fz; H.land_p[0] = qx; H.land_p[1] = qy; }
            break;
        }
        pz = qz;
    }
    return H.lands;
}

/* Try to catch the edge; returns 1 when Dash starts hanging. on_rim: the game still has him
 * standing (his collision sphere rests on the rim) with his centre already over the drop. */
static int grab_edge(uint32_t obj, float x, float y, float z, float gx, float gy, float gz, float dx, float dy);

/* Unit normal of an edge running along (tx, ty), on the side of (dx, dy) (out over the drop). */
static void edge_normal(float tx, float ty, float dx, float dy, float *nx, float *ny) {
    float tl = sqrt_f(tx * tx + ty * ty), mx = ty / tl, my = -tx / tl;
    if (mx * dx + my * dy < 0) { mx = -mx; my = -my; }
    *nx = mx; *ny = my;
}

/* A floor within STEP_REACH ahead of him (the way he moves), from STEP_UP above his feet
 * down to HANG_DEPTH below: a stair step, not an abyss. */
static int step_ahead(uint32_t obj, float x, float y, float z) {
    float dx = F32(obj + OBJ_VEL), dy = F32(obj + OBJ_VEL + 4), v = sqrt_f(dx * dx + dy * dy);
    if (v > 1.0f) { dx /= v; dy /= v; }
    else { float f = RAD(F32(obj + K->yaw) + 90.0f); dx = cos_h(f); dy = sin_h(f); }
    for (float t = STEP_PROBE; t <= STEP_REACH; t += STEP_PROBE) {
        float from[3] = { x + dx * t, y + dy * t, z + STEP_UP }, to[3] = { from[0], from[1], z - HANG_DEPTH };
        if (trace_dist(obj, from, to) >= 0) return 1;
    }
    return 0;
}

/* In a jump (up or down): the rim of a wall ahead of him (the way he flies, else his facing)
 * within his hands' reach. Not one he will clear on the way up; one below JUMP_REACH_LO he
 * lands on. The edge he jumped off is never caught (a jump down stays a jump down). */
static int front_grab(uint32_t obj) {
    float x = F32(obj + OBJ_POS), y = F32(obj + OBJ_POS + 4), z = F32(obj + OBJ_POS + 8);
    float dx = F32(obj + OBJ_VEL), dy = F32(obj + OBJ_VEL + 4), vz = F32(obj + OBJ_VEL + 8);
    float v = sqrt_f(dx * dx + dy * dy);
    if (v > 1.0f) { dx /= v; dy /= v; }
    else { float f = RAD(F32(obj + K->yaw) + 90.0f); dx = cos_h(f); dy = sin_h(f); }
    float a[3] = { x, y, z + JUMP_RAY_Z }, b[3] = { x + dx * JUMP_WALL, y + dy * JUMP_WALL, z + JUMP_RAY_Z };
    float w = trace_dist(obj, a, b);
    if (w < 0) return 0;
    float px = x + dx * (w + 0.5f), py = y + dy * (w + 0.5f);
    float from[3] = { px, py, z + JUMP_REACH_HI + 1.5f }, to[3] = { px, py, z + JUMP_RAY_Z };
    float h = trace_dist(obj, from, to);
    if (h < 0) return 0;
    float ez = from[2] - h;
    if (ez < z + JUMP_REACH_LO || ez > z + JUMP_REACH_HI) return 0;
    if (vz > 0 && z + vz * vz / (2 * GRAVITY) + LAND_UP >= ez) return 0;     /* he gets on it */
    /* Somewhere to stand up there (a narrow or slanted rock top: he climbed it and slid off). */
    for (float k = 1.5f; k <= 3.0f; k += 1.5f)
        if (floor_at(obj, px + dx * k, py + dy * k, ez, 1.0f, 1.0f) < NO_FLOOR) return 0;
    return grab_edge(obj, x, y, z, px + dx, py + dy, ez, -dx, -dy);
}

static int hang_grab(uint32_t obj, int on_rim) {
    float x = F32(obj + OBJ_POS), y = F32(obj + OBJ_POS + 4), z = F32(obj + OBJ_POS + 8);
    float gx = H.ground[0], gy = H.ground[1], gz = H.ground[2];
    if (!on_rim && (z > gz - HANG_TRIGGER || z < gz - HANG_REACH)) return 0;
    float here[3] = { x, y, z }, below[3] = { x, y, gz - HANG_DEPTH };
    if (trace_dist(obj, here, below) >= 0) return 0;                  /* floor below: a step */
    /* Open stairs: that ray can go down through the gap between two steps. A floor just ahead
     * (the next step, up or down) means no abyss. Without this the edge search (up to ~180
     * rays) ran on the Echo Base stairs: frames of 0.3-0.6 s, and he fell through a step. */
    if (step_ahead(obj, x, y, z)) return 0;
    if (will_land(obj, gz)) return 0;                                 /* he clears the gap */
    /* The way he went: his velocity on the last frame on the floor (where he was headed, not
     * where the air has carried him since). Fell short of the floor he jumped for (hit its
     * face and slides down): catch its rim, in front of him, walking from where he flew at
     * back the way he came; not the one he ran off (that pulled him back across the gap). */
    float dx = H.gv[0], dy = H.gv[1], d = sqrt_f(dx * dx + dy * dy);
    if (d < 1.0f) { dx = x - gx; dy = y - gy; d = sqrt_f(dx * dx + dy * dy); }
    if (d < 0.3f) { float f = RAD(F32(obj + K->yaw) + 90.0f); dx = cos_h(f); dy = sin_h(f); d = 1; }
    dx /= d; dy /= d;
    if (H.land_miss && grab_edge(obj, x, y, z, H.land_p[0], H.land_p[1], H.land_z, -dx, -dy)) return 1;
    return grab_edge(obj, x, y, z, gx, gy, gz, dx, dy);
}

/* Where a climb ends: a spot inside the rim with floor at the rim's height (an icy slope would
 * slide him back off; a vertical ray that only met a steep slope 6 inside put him there in the
 * Gall canyon and he slid into the abyss; so did the top of a thin wall). 3, 4.5 or 6 in; else the
 * last floor he stood on (a walk-off) if 2 or more from the rim. 0: none. */
static float wide_floor(uint32_t obj, float x, float y, float z) {
    float h = floor_at(obj, x, y, z, CLIMB_UP, CLIMB_FLOOR);
    if (h < NO_FLOOR) return h;
    /* Floor 1 further in (not at the far edge of a narrow strip: he slid off it and caught the
     * other side) and at least on one side 1 across (not a ridge; a strip beside another edge
     * is fine). */
    float px = -H.in[1], py = H.in[0];
    if (floor_at(obj, x + H.in[0], y + H.in[1], h, 0.5f, 0.5f) < NO_FLOOR) return 2 * NO_FLOOR;
    if (floor_at(obj, x + px, y + py, h, 0.5f, 0.5f) < NO_FLOOR &&
        floor_at(obj, x - px, y - py, h, 0.5f, 0.5f) < NO_FLOOR) return 2 * NO_FLOOR;
    return h;
}

/* Floor there, wide, and not sloping down toward the rim (he slid back off and caught the
 * same rim again, "climbs twice"): 1.5 further in at most CLIMB_SLOPE higher. */
static float stand_floor(uint32_t obj, float x, float y, float z) {
    float h = wide_floor(obj, x, y, z);
    if (h > NO_FLOOR && floor_at(obj, x + H.in[0] * 1.5f, y + H.in[1] * 1.5f, h + CLIMB_SLOPE, 0.0f, 3.0f) < NO_FLOOR)
        return 2 * NO_FLOOR;
    return h;
}

static int climb_spot(uint32_t obj) {
    for (float k = 3.0f; k <= 6.0f; k += 1.5f) {
        float px = H.face[0] + H.in[0] * k, py = H.face[1] + H.in[1] * k;
        float h = stand_floor(obj, px, py, H.face[2]);
        if (h > NO_FLOOR) { H.top[0] = px; H.top[1] = py; H.top[2] = h + 0.2f; return 1; }
    }
    /* The floor he walked off (he stood there), if not right at the rim. */
    float dx = H.top[0] - H.face[0], dy = H.top[1] - H.face[1];
    if (H.jumped || dx * dx + dy * dy < 2.0f * 2.0f) return 0;
    float h = floor_at(obj, H.top[0], H.top[1], H.face[2], CLIMB_UP, 1.5f);   /* near the rim's height */
    if (h > NO_FLOOR) { H.top[2] = h + 0.2f; return 1; }
    return 0;
}

/* Hanging means he can climb (the user's rule): no good spot, then any floor near the rim's
 * height 1.5-6 in, else the floor he last stood on. */
static void climb_target(uint32_t obj) {
    if (climb_spot(obj)) return;
    g_hang_why = 10;
    for (float k = 1.5f; k <= 6.0f; k += 1.5f) {
        float px = H.face[0] + H.in[0] * k, py = H.face[1] + H.in[1] * k;
        float h = floor_at(obj, px, py, H.face[2], CLIMB_UP, 1.5f);
        if (h > NO_FLOOR) { H.top[0] = px; H.top[1] = py; H.top[2] = h + 0.2f; return; }
    }
    /* Else where he last stood: always floor. (Just 2 in at the rim's height put him inside
     * the Outrider's hull, and he fell through it.) */
    H.top[0] = H.ground[0]; H.top[1] = H.ground[1]; H.top[2] = H.ground[2] + 0.2f;
}

/* A free hang under a thin floor only where it is clean (the user's video of the Echo Base
 * truss bridge: he hung among the girders, hid behind them, caught a thin pipe, the camera
 * ended under the deck; its truss sides have no collision): a wide floor behind the rim
 * (FREE_WIDE: the bridge deck is 5.7 across; not a beam or a pipe either), nothing above the rim to either side (truss diagonals), nothing beside or in front of his
 * body, and the camera fits on one side of him. */
static int free_hang_clear(uint32_t obj, float ex, float ey, float ez, float nx, float ny, float hx, float hy) {
    float px = -ny, py = nx;
    /* Floor in behind the rim, unbroken (a slope may climb or drop a bit): straight in, and
     * turned 40 degrees either way (a narrow bridge left at a slant, near its end, has ice
     * straight in behind it). */
    for (int r = -1; r <= 1; r++) {
        float c = cos_h(RAD(40.0f * r)), sn = sin_h(RAD(40.0f * r));
        float ix = -(nx * c - ny * sn), iy = -(nx * sn + ny * c);
        for (float s = r ? 0 : -FREE_SIDE; s <= (r ? 0 : FREE_SIDE); s += FREE_SIDE) {
            float z = ez;
            for (float k = 1.0f; k <= FREE_WIDE; k += 1.0f)
                if ((z = floor_at(obj, ex + ix * k + px * s, ey + iy * k + py * s, z, 0.5f, 0.5f)) < NO_FLOOR) { g_hang_why = 6; return 0; }
        }
    }
    for (float s = -FREE_SIDE; s <= FREE_SIDE; s += FREE_SIDE) {
        for (float h = 2.0f; h <= 4.0f; h += 2.0f) {
            float from[3] = { ex + nx * 1.5f + px * s, ey + ny * 1.5f + py * s, ez + h };
            float to[3] = { ex - nx * 1.0f + px * s, ey - ny * 1.0f + py * s, ez + h };
            if (trace_dist(obj, from, to) >= 0) { g_hang_why = 6; return 0; }
        }
    }
    for (float h = 1.5f; h < HANG_BELOW; h += 2.0f) {
        float a[3] = { hx - px * FREE_SIDE, hy - py * FREE_SIDE, ez - h }, b[3] = { hx + px * FREE_SIDE, hy + py * FREE_SIDE, ez - h };
        if (trace_dist(obj, a, b) >= 0 || trace_dist(obj, b, a) >= 0) { g_hang_why = 6; return 0; }
        float c[3] = { hx, hy, ez - h }, d[3] = { hx + nx * FREE_SIDE, hy + ny * FREE_SIDE, ez - h };
        if (trace_dist(obj, c, d) >= 0) { g_hang_why = 6; return 0; }
    }
    float p[3] = { hx, hy, ez - HANG_BELOW }, wall = DEG(atan2_h(-ny, -nx));
    if (!cam_fits(obj, p, wall + HANG_CAM_SIDE) && !cam_fits(obj, p, wall - HANG_CAM_SIDE)) { g_hang_why = 7; return 0; }
    return 1;
}

/* Catch the edge of the floor through (gx, gy, gz) on the way toward (wx, wy); he is at
 * (x, y, z). */
static int grab_edge(uint32_t obj, float x, float y, float z, float gx, float gy, float gz, float dx, float dy) {
    /* From the floor point, walk along the way he went (dx, dy: unit) on the surface until it
     * ends: that is the rim, and he hangs right there. He can stand with his centre already
     * past the rim (his sphere holds him): start the walk a bit back; less far on a narrow
     * strip of floor (back there is the gap he just cleared). */
    float ox = x - gx, oy = y - gy, len = sqrt_f(ox * ox + oy * oy);
    if (len > HANG_SLIDE) { g_hang_why = 1; return 0; }
    float back = EDGE_BACK, ez, t = -1;
    for (; back >= 0; back -= 1.5f) {
        t = find_edge(obj, gx - dx * back, gy - dy * back, dx, dy, len + back + 4.0f, gz, &ez);
        if (t >= 0) break;
    }
    if (t < 0) { g_hang_why = 2; return 0; }
    gx -= dx * back; gy -= dy * back;
    float ex = gx + dx * t, ey = gy + dy * t;
    /* Face the rim square on if it is clearly slanted to his way: the edge line through two
     * more walks 1 unit to either side. Only a small turn (an odd neighbour point, e.g. at a
     * corner, would turn him away from where he went over). */
    float nx = dx, ny = dy, px = -dy, py = dx, z1, z2;
    float t1 = find_edge(obj, gx + px, gy + py, dx, dy, t + 3.0f, gz, &z1);
    float t2 = find_edge(obj, gx - px, gy - py, dx, dy, t + 3.0f, gz, &z2);
    if (t1 >= 0 && t2 >= 0) {
        float mx, my;
        edge_normal(2 * px + dx * (t1 - t2), 2 * py + dy * (t1 - t2), dx, dy, &mx, &my);
        if (mx * dx + my * dy > EDGE_TURN_COS) { nx = mx; ny = my; }
    }
    /* A ledge, not a wall: nothing in the way just above the rim. */
    {
        float from[3] = { ex + nx * 1.5f, ey + ny * 1.5f, ez + 2.0f };
        float to[3] = { ex - nx * 1.0f, ey - ny * 1.0f, ez + 2.0f };
        if (trace_dist(obj, from, to) >= 0) { g_hang_why = 3; return 0; }
    }
    /* The face 1 under the rim, looked for from where he will hang. Nearer than HANG_OUT (the
     * face leans out below the rim): he hangs that much further out. None, or far in (a thin
     * floor such as a catwalk, an overhang): he hangs free under the rim, if nothing is in the
     * way of his body lower down (the Echo Base bridge has girders under its deck: his arms
     * went through them). */
    float out = HANG_OUT, gap;
    for (int i = 0; i < 2; i++) {                   /* again from there: the final gap (tests) */
        float hx = ex + nx * out, hy = ey + ny * out;
        float from[3] = { hx, hy, ez - 1.0f };
        float to[3] = { hx - nx * 6.0f, hy - ny * 6.0f, ez - 1.0f };
        gap = trace_dist(obj, from, to);
        if (i) break;
        if (gap < 0 || gap > out + FACE_DEEP) { gap = -1; break; }
        if (gap >= out) break;
        out += out - gap;
    }
    float hx = ex + nx * out, hy = ey + ny * out;
    /* In a jump only the rim of a sheer wall (the user's Gall videos: he caught rounded rock
     * tops and slopes): a face under the rim, still there 3 and 5 lower, as far in. */
    if (H.jumped) {
        if (gap < 0) { g_hang_why = 8; return 0; }
        for (float h = 3.0f; h <= 5.0f; h += 2.0f) {
            float from[3] = { hx, hy, ez - h }, to[3] = { hx - nx * 6.0f, hy - ny * 6.0f, ez - h };
            float d = trace_dist(obj, from, to);
            if (d < 0 || d - gap > JUMP_PLUMB || gap - d > JUMP_PLUMB) { g_hang_why = 8; return 0; }
        }
    }
    if (gap < 0) {
        for (float h = 2.5f; h < HANG_BELOW; h += 2.0f) {
            float from[3] = { hx + nx * 0.5f, hy + ny * 0.5f, ez - h };
            float to[3] = { ex - nx * 1.0f, ey - ny * 1.0f, ez - h };
            float d = trace_dist(obj, from, to);
            if (d >= 0 && d < out + 0.5f - 0.4f) { g_hang_why = 4; return 0; }
        }
        if (!free_hang_clear(obj, ex, ey, ez, nx, ny, hx, hy)) return 0;
    }
    /* Room under him: in a jump no floor JUMP_CLEAR under his feet (he hung with his feet on
     * the slope below); walking off, a drop of HANG_DEPTH under the rim, as where he flies (the
     * user's Imperial Garrison video: the rim traced back from over an abyss had a slope 8.5
     * under it, he hung with his feet just over it).
     * A cliff leaning out below the rim is no floor: steeper than 45 degrees (a second ray
     * 0.5 further out hits 0.5 lower or more). */
    {
        float from[3] = { hx, hy, ez - 1.0f }, to[3] = { hx, hy, H.jumped ? ez - HANG_BELOW - HANG1_DROP - JUMP_CLEAR : ez - HANG_DEPTH };
        float d = trace_dist(obj, from, to);
        if (d >= 0) {
            from[0] = to[0] = hx + nx * 0.5f; from[1] = to[1] = hy + ny * 0.5f; to[2] = ez - 1.0f - d - 1.0f;
            float d2 = trace_dist(obj, from, to);
            if (d2 >= 0 && d2 < d + 0.5f) { g_hang_why = 5; return 0; }
        }
    }
    /* Not in a shaft: another wall behind him, under NARROW out (the user's Sewers video: he
     * hung in a hatch that then closed over him, the camera in the wall). */
    for (float h = 1.0f; h <= 3.0f; h += 2.0f) {
        float from[3] = { hx, hy, ez - h }, to[3] = { hx + nx * NARROW, hy + ny * NARROW, ez - h };
        if (trace_dist(obj, from, to) >= 0) { g_hang_why = 12; return 0; }
    }
    if (H.jumped) {                                 /* somewhere to climb to (checked again at the climb) */
        float f[3] = { H.face[0], H.face[1], H.face[2] }, in[2] = { H.in[0], H.in[1] }, top[3] = { H.top[0], H.top[1], H.top[2] };
        H.face[0] = ex; H.face[1] = ey; H.face[2] = ez; H.in[0] = -nx; H.in[1] = -ny;
        H.top[0] = gx + nx * -2.0f; H.top[1] = gy + ny * -2.0f;
        int ok = climb_spot(obj);
        H.face[0] = f[0]; H.face[1] = f[1]; H.face[2] = f[2]; H.in[0] = in[0]; H.in[1] = in[1];
        H.top[0] = top[0]; H.top[1] = top[1]; H.top[2] = top[2];
        if (!ok) { g_hang_why = 9; return 0; }
    }
    g_hang_gap = gap;
    /* The rim may belong to an object (the Gall hangar's hover platforms, its upper floor, a
     * canyon rock, Suprosa's machinery): note it, the hang lasts only while it stays put. */
    H.plat = 0;
    for (float k = 0.5f; k < 3.0f && !H.plat; k += k < 1.5f ? 0.5f : 1.0f) {   /* 0.5, 1, 1.5, 2.5 in */
        float from[3] = { ex - nx * k, ey - ny * k, ez + 1.0f }, to[3] = { ex - nx * k, ey - ny * k, ez - 1.0f };
        H.plat = trace_obj(obj, from, to);
        if (!H.plat && k > 2.0f && !H.jumped && valid_ptr(H.gplat)) {   /* the mover he walked off, */
            float dx = ex - F32(H.gplat + OBJ_POS), dy = ey - F32(H.gplat + OBJ_POS + 4);   /* if this */
            float dz = ez - F32(H.gplat + OBJ_POS + 8);                                       /* is its rim */
            if (dx * dx + dy * dy < 8.0f * 8.0f && dz < 1.0f && dz > -1.0f) H.plat = H.gplat;
        }
        if (H.plat) {
            H.plat_tag = U32(H.plat);
            for (int i = 0; i < 3; i++) H.plat_p[i] = F32(H.plat + OBJ_POS + 4 * i);
        }
    }
    H.edge = ez;
    H.face[0] = ex; H.face[1] = ey; H.face[2] = ez;
    H.in[0] = -nx; H.in[1] = -ny;
    H.pos[0] = hx; H.pos[1] = hy; H.pos[2] = ez - HANG_BELOW;
    /* Climbing ends here unless a spot further in is found: on the floor he walked toward. */
    H.top[0] = gx + nx * -2.0f; H.top[1] = gy + ny * -2.0f; H.top[2] = gz + 0.2f;
    H.wall = DEG(atan2_h(-ny, -nx));
    H.yaw = wrap_h(H.wall - 90.0f + HANG_POSE_TURN);
    /* He spins round from where he was running to face the cliff. The hang pose is turned
     * on its root, so his current look in it is his yaw + the same turn. */
    H.yaw0 = wrap_h(F32(obj + K->yaw) + HANG_POSE_TURN);
    H.ycur = H.yaw0;
    H.start[0] = x; H.start[1] = y;
    H.z0 = z; H.t = 0;
    pick_cam_side(obj);
    g_hang_state = 1;
    return 1;
}

/* In a fight the game turns his neck and chest toward the enemy by rotating their nodes
 * after the pose is evaluated: he hung twisted, one hand off the rim. Rebuild those node
 * rotations from the pose's own angles (z, x, y: node = (Rz Rx Ry) transposed). */
static void untwist(uint32_t obj) {
    if (U32(obj + OBJ_ANIM_CHAIN) != (uint32_t)hang_block) return;
    static const uint8_t bones[2] = { 2, 9 };       /* neck, chest */
    for (int k = 0; k < 2; k++) {
        uint32_t e = (uint32_t)hang_block + 0x38 + 0xA0 * bones[k], node = U32(e + 0x08);
        if (!valid_ptr(node)) continue;
        float a[3];
        for (int i = 0; i < 3; i++) a[i] = RAD(F32(e + 0x10 + 4 * i));
        float cz = cos_h(a[0]), sz = sin_h(a[0]), cx = cos_h(a[1]), sx = sin_h(a[1]), cy = cos_h(a[2]), sy = sin_h(a[2]);
        float m[3][3] = {                           /* Rz Rx Ry */
            { cz * cy - sz * sx * sy, -sz * cx, cz * sy + sz * sx * cy },
            { sz * cy + cz * sx * sy,  cz * cx, sz * sy - cz * sx * cy },
            { -cx * sy,                sx,      cx * cy },
        };
        for (int r = 0; r < 3; r++)
            for (int c = 0; c < 3; c++) F32(node + 0x14 + 4 * (3 * r + c)) = m[c][r];
    }
}

/* Turn the model toward the wall: rotation rows right/forward of his matrices. The draw
 * matrix is rebuilt by the game during the update, so this also runs from later hooks. */
static void hang_face(uint32_t obj) {
    float f = RAD(H.ycur + 90.0f), c = cos_h(f), sn = sin_h(f);
    /* Not OBJ_MATRIX_COPY: the camera follows that one, and it is placed separately. */
    static const uint16_t mats[3] = { OBJ_MATRIX, OBJ_MATRIX_DRAW, OBJ_MATRIX_MODEL };
    for (int i = 0; i < 3; i++) {
        uint32_t m = obj + mats[i];
        F32(m) = sn;  F32(m + 4) = -c; F32(m + 8) = 0;
        F32(m + 16) = c; F32(m + 20) = sn; F32(m + 24) = 0;
    }
    /* Place the body too. Its sphere touches the rim, and the game pushes the drawn body out
     * of it by a different amount every catch (up to 1.6 units up or down, ~1 off the wall),
     * so the hand landed at random heights. Normally the body sits BODY_LIFT above the feet
     * with the same x/y; the drawn model keeps its own offset from the body (the pose's root). */
    float root = F32(obj + OBJ_MATRIX_MODEL + 56) - F32(obj + OBJ_MATRIX_DRAW + 56);
    float b[3] = { H.cur[0], H.cur[1], H.cur[2] + BODY_LIFT };
    static const uint16_t body[2] = { OBJ_MATRIX_DRAW, OBJ_MATRIX_COPY };
    for (int i = 0; i < 2; i++)
        for (int j = 0; j < 3; j++) F32(obj + body[i] + 48 + 4 * j) = b[j];
    for (int j = 0; j < 3; j++) F32(obj + OBJ_MATRIX_MODEL + 48 + 4 * j) = b[j];
    F32(obj + OBJ_MATRIX_MODEL + 56) = b[2] + root;
    untwist(obj);
}

void hang_hold(uint32_t obj) { hang_face(obj); }

static void hold_still(uint32_t sp) {
    SLOT16(sp, DEC_FORWARD) = 0;
    SLOT16(sp, DEC_BACK) = 0;
    SLOT16(sp, DEC_TURN_A) = 0;
    SLOT16(sp, DEC_TURN_B) = 0;
    SLOT16(sp, DEC_STRAFE_L) = 0;
    SLOT16(sp, DEC_STRAFE_R) = 0;
    U32(PAD_STICK_X) = 0;
    /* no aiming or jumping off the wall (firing is blocked by the tramp_fire hook) */
    U32(PAD_BUTTONS) &= ~(binding(BIND_JUMP) | binding(BIND_AIM));
}

/* Let go, then the jetpack fired: the fall is his own again (held under the edge, the stick did
 * nothing and he could not rise for up to DROP_T). No catch until he lands, as in any flight. */
static void jet_out(void) {
    g_hang_drop = 0;
    H.jet = 1;
}

/* Floor under his centre while he stands (the on-rim catch)? This runs every frame, and one
 * trace made the whole frame ~9% longer (docs/reverse-engineering.md): not again where it
 * already found floor and he hasn't moved, every other frame while he walks (a rim it misses
 * is caught a frame later, or by the fall catch), level geometry only unless he stands on a
 * mover (objects cost another third). */
int g_probe_n;                /* tests: traces made by floor_under */
static int floor_under(uint32_t obj, const float *here, float *below) {
    float dx = here[0] - H.probe[0], dy = here[1] - H.probe[1];
    if (H.probe_ok && (dx * dx + dy * dy < 0.05f * 0.05f || (H.probe_skip ^= 1))) return 1;
    uint32_t hit = 0, hit2 = 0;
    float f[3] = { here[0], here[1], here[2] };
    g_probe_n++;
    H.probe[0] = here[0]; H.probe[1] = here[1];
    return H.probe_ok = ((trace_fn)TRACE_FN)(below, f, U32(obj + OBJ_COLLIDER), &hit, &hit2, 0.0f, H.gplat != 0) >= 0;
}

/* Runs at the start of each Humn decode. Returns 1 while hanging (input consumed). */
int hang_update(uint32_t obj, uint32_t sp, uint32_t buttons, float sx, float sy) {
    uint32_t fl = U32(obj + OBJ_FLAGS);
    if (g_off & OFF_HANG) {                              /* Cheats: off, the game's own falls */
        if (g_hang_state) hang_end(obj, 1);
        H.ground_ok = 0;
    }
    if (g_hang_drop && (fl & FL_JET)) jet_out();
    /* The jetpack fired while he hangs or climbs (user, 2026-10-11: it ran and he kept
     * hanging): let go, and the flight is his. */
    if (g_hang_state && (fl & FL_JET)) { hang_end(obj, 1); jet_out(); return 0; }
    if (g_hang_drop) { hold_still(sp); return 1; }       /* falling from the hang */
    if (g_off & OFF_HANG) return 0;
    if (g_hang_state && hang_moved(obj)) return 0;
    if (g_hang_state && plat_moved()) { g_hang_why = 11; hang_end(obj, 1); hold_still(sp); return 1; }
    if (H.hold_stick) {
        /* Still holding "up" from the climb: camera-relative, that may point back over the
         * edge. Stand still until the stick comes back to the middle. */
        if (sx * sx + sy * sy < 20.0f * 20.0f) H.hold_stick = 0;
        else { hold_still(sp); return 1; }
    }
    if (!g_hang_state) {
        /* A jump: the button, or rising (a short tap is up again before the ground
         * flag clears, and that frame must not count as standing). */
        int rising = F32(obj + OBJ_VEL + 8) > JUMP_VZ;
        if ((fl & FL_GROUND) && !(fl & FL_AIR) && !rising) {
            /* Still "standing", but his centre may already be past the edge, held up by his
             * collision sphere on the rim: the game shows him striding out over the drop for
             * a few frames before it lets him fall. Catch the edge right there. */
            float x = F32(obj + OBJ_POS), y = F32(obj + OBJ_POS + 4), z = F32(obj + OBJ_POS + 8);
            float here[3] = { x, y, z + 0.5f }, below[3] = { x, y, z - HANG_DEPTH };
            int jump = (buttons & binding(BIND_JUMP)) != 0;
            /* Not on the frame he lands: touching down on the far rim of a gap he cleared, the
             * last floor is still the near side, and that caught him there, pulled back across. */
            int was = H.was_ground;
            H.was_ground = 1;
            if (!was) H.probe_ok = 0;
            if (was && H.ground_ok && !H.jumped && !jump && !H.let_go && !floor_under(obj, here, below)) {
                if (!hang_grab(obj, 1)) return 0;
            } else {
                H.ground[0] = x; H.ground[1] = y; H.ground[2] = z;
                H.ground_ok = 1; H.let_go = 0; H.lands = -1; H.land_miss = 0;
                H.gv[0] = F32(obj + OBJ_VEL); H.gv[1] = F32(obj + OBJ_VEL + 4);
                H.jumped = jump; H.jet = 0;
                H.gplat = mover_of(U32(obj + OBJ_COLLIDER));          /* standing on a mover */
                if (H.gplat) for (int i = 0; i < 3; i++) H.gplat_p[i] = F32(H.gplat + OBJ_POS + 4 * i);
                return 0;
            }
        } else {
            H.was_ground = 0;
            if (rising) H.jumped = 1;
            if (fl & (FL_JET | FL_SWIM)) H.jet = 1;   /* no catch until he lands (he caught the air) */
            if (H.gplat) {                      /* the floor he left flies on: so does its rim */
                for (int i = 0; i < 3; i++) {
                    float d = F32(H.gplat + OBJ_POS + 4 * i) - H.gplat_p[i];
                    H.ground[i] += d; H.gplat_p[i] += d;
                }
            }
            if (!H.ground_ok || H.let_go || H.jet || !(H.jumped ? front_grab(obj) : hang_grab(obj, 0))) return 0;
        }
        H.need_center = 1;            /* the stick still points where he was running */
    }
    if (H.need_center && sx * sx + sy * sy < 20.0f * 20.0f) H.need_center = 0;
    float dt = frame_dt();
    H.t += dt;
    if (g_hang_state == 1 && !H.need_center && sy > HANG_STICK) {   /* start climbing */
        climb_target(obj);
        g_hang_state = 2; H.t = 0;
        for (int i = 0; i < POSE_TRACKS; i++)           /* the reach starts where the sway is */
            climb_from[i] = hang_tracks[i][0];
    }
    if (g_hang_state == 1 && !H.need_center && sy < -HANG_STICK) {  /* let go: the fall carries on */
        hang_end(obj, 1);
        return 1;
    }
    if (g_hang_state == 1) {
        /* Catch: he swings in under the edge while falling a little past the hang point,
         * then eases back up to it. */
        H.cur[0] = H.pos[0]; H.cur[1] = H.pos[1]; H.cur[2] = H.pos[2];
        float low = H.pos[2] - HANG_DIP;
        if (H.t < HANG_FALL_T) {
            float u = H.t / HANG_FALL_T, e = 1 - (1 - u) * (1 - u);
            H.cur[0] = H.start[0] + (H.pos[0] - H.start[0]) * e;
            H.cur[1] = H.start[1] + (H.pos[1] - H.start[1]) * e;
            float from = H.z0 > H.pos[2] ? H.z0 : H.pos[2];
            H.cur[2] = from + (low - from) * u * u;
        } else if (H.t < HANG_FALL_T + HANG_CATCH_T) {
            float u = (H.t - HANG_FALL_T) / HANG_CATCH_T;
            H.cur[2] = low + (H.pos[2] - low) * (1 - (1 - u) * (1 - u));
        }
        if (H.t < HANG_FALL_T) hang_anim_pose(catch_keys[0], catch_keys[1], H.t / HANG_FALL_T);
        else if (H.t < CATCH_SWING_T)
            hang_anim_pose(catch_keys[1], catch_keys[2], (H.t - HANG_FALL_T) / (CATCH_SWING_T - HANG_FALL_T));
        else if (H.t < CATCH_END_T)
            hang_anim_pose(catch_keys[2], hang1_keys[0], (H.t - CATCH_SWING_T) / (CATCH_END_T - CATCH_SWING_T));
        else hang_anim_pose(hang1_keys[0], hang1_keys[1], 0.5f - 0.5f * cos_h(RAD(360.0f * (H.t - CATCH_END_T) / SWAY_T)));
        H.cur[2] -= HANG1_DROP;
        H.ycur = H.yaw;
        if (H.t < HANG_SPIN_T) {
            float u = H.t / HANG_SPIN_T, e = 1 - (1 - u) * (1 - u);
            H.ycur = wrap_h(H.yaw0 + wrap_h(H.yaw - H.yaw0) * e);
        }
    } else {
        /* Climb: the right hand up to the rim, pull up on it, mantle over it, then onto the
         * ledge in a crouch. */
        H.cur[0] = H.pos[0]; H.cur[1] = H.pos[1];
        float tc = H.t - CLIMB_REACH_T;
        if (tc < 0) {
            float u = H.t / CLIMB_REACH_T, e = u * u * (3 - 2 * u);
            if (u < 0.5f) hang_anim_pose(0, hang1_keys[2], u * 2);
            else hang_anim_pose(hang1_keys[2], hang_pose, u * 2 - 1);
            H.cur[2] = H.pos[2] - HANG1_DROP * (1 - e);
        } else if (tc < CLIMB_PULL_T) {
            float u = tc / CLIMB_PULL_T, e = u * u * (3 - 2 * u);
            hang_anim_pose(hang_pose, climb_keys[0], u);
            H.cur[2] = H.pos[2] + CLIMB_PULL_UP * e;
        } else if (tc < CLIMB_MANTLE_T) {
            float u = (tc - CLIMB_PULL_T) / (CLIMB_MANTLE_T - CLIMB_PULL_T), e = u * u * (3 - 2 * u);
            hang_anim_pose(climb_keys[0], climb_keys[1], u);
            H.cur[2] = H.pos[2] + CLIMB_PULL_UP + (CLIMB_MANTLE_UP - CLIMB_PULL_UP) * e;
        } else if (tc < CLIMB_END_T) {
            /* Up first (the feet clear the rim), forward after. */
            float u = (tc - CLIMB_MANTLE_T) / (CLIMB_END_T - CLIMB_MANTLE_T);
            float up = 1 - (1 - u) * (1 - u), fwd = u * u;
            hang_anim_pose(climb_keys[1], climb_keys[2], u);
            float z0 = H.pos[2] + CLIMB_MANTLE_UP;
            H.cur[0] = H.pos[0] + (H.top[0] - H.pos[0]) * fwd;
            H.cur[1] = H.pos[1] + (H.top[1] - H.pos[1]) * fwd;
            H.cur[2] = z0 + (H.top[2] - z0) * up;
        } else {
            set_pos(obj, H.top);
            set_yaw(obj, wrap_h(H.wall - 90.0f));   /* standing pose isn't turned: face inland */
            g_target_yaw = F32(obj + K->yaw);         /* not back to where he ran off */
            hang_end(obj, 0);
            H.hold_stick = 1;
            return 1;
        }
    }
    set_pos(obj, H.cur);
    set_yaw(obj, H.ycur);
    F32(obj + K->rate) = 0;
    hold_still(sp);
    return 1;
}

/* End of the Humn control function: hold the hanging Dash after the game moved him. */
void ctl_ctrl_end(uint32_t obj) {
    if (obj != g_player) return;
    /* Shot down while hanging: the game doesn't flag him dead, it only runs its death
     * sequence from health 0 (and respawns him later). Let go and fall. */
    if (g_hang_state && hang_moved(obj)) return;
    if (g_hang_state && !(F32(obj + HUMN_HEALTH) > 0)) hang_end(obj, 1);
    if (g_hang_drop) {
        /* Let go or killed: fall down the face, easing DROP_OUT away from it (the fall pose
         * leans forward; held at the hang point his head went into the wall). Left alone, the
         * game pushed him far out past the camera, which then looked down at nothing. Ends where
         * the game's own pit camera takes over, on landing, or after DROP_T. */
        uint32_t fl = U32(obj + OBJ_FLAGS);
        if (fl & FL_JET) { jet_out(); return; }
        H.drop_t += frame_dt();
        float u = H.drop_t / DROP_OUT_T;
        if (u > 1) u = 1;
        float out = DROP_OUT * u * (2 - u), p[2] = { H.cur[0] - H.in[0] * out, H.cur[1] - H.in[1] * out };
        float mx = F32(obj + OBJ_POS) - p[0], my = F32(obj + OBJ_POS + 4) - p[1];
        if (mx * mx + my * my > 3.0f * 3.0f) { g_hang_drop = 0; return; }   /* the game moved him: respawn */
        /* His sphere can rest on something at the hang height (a thin floor he hung under, a
         * beam beside him): the game has him standing at once, and it pushed him up onto the
         * floor. He may not rise; landing is lower than the hang or DROP_FREE_T standing. */
        float z = F32(obj + OBJ_POS + 8);
        if (z > H.cur[2]) {
            F32(obj + OBJ_POS + 8) = F32(obj + OBJ_POS_COPY + 8) = H.cur[2];
            if (F32(obj + OBJ_VEL + 8) > 0) F32(obj + OBJ_VEL + 8) = 0;
        }
        else if (dropped_onto_floor(obj)) { drop_end(obj); return; }
        if ((fl & FL_DEATH_FALL) || H.drop_t > DROP_T) {
            g_hang_drop = 0;
            return;
        }
        for (int i = 0; i < 2; i++) {
            F32(obj + OBJ_POS + 4 * i) = p[i];
            F32(obj + OBJ_POS_COPY + 4 * i) = p[i];
            F32(obj + OBJ_VEL + 4 * i) = 0;
        }
        set_yaw(obj, H.ycur);
        F32(obj + K->rate) = 0;
        return;
    }
    if (!g_hang_state) return;
    set_pos(obj, H.cur);
    set_yaw(obj, H.ycur);
    F32(obj + K->rate) = 0;
    hang_face(obj);
}

/* set_anim hook: a0..a3 saved by the trampoline (id, flags, controller, anim state). */
void ctl_setanim(uint32_t *a) {
    if (!g_player || a[3] != g_player + OBJ_ANIM_STATE) return;
    if (g_hang_drop) {                              /* not the jump or death pose */
        if (dropped_onto_floor(g_player)) g_hang_drop = 0;         /* landed: the game's own */
        else a[0] = H.drop_floor ? ANIM_JUMP_DOWN : ANIM_FALL;
    }
    else if (g_hang_state) {
        F32(g_player + OBJ_YAW) = H.ycur;
        F32(g_player + OBJ_YAW_COPY) = H.ycur;
        hang_face(g_player);
        /* Always a fresh switch: the pose (with Dash's heading baked in) is only evaluated
         * when the animation changes, and his heading is set while he hangs. */
        hang_ctrl.cur = &hang_anims[3];
        int own = hang_anim_link(g_player);
        if (own) hide_weapon();
        hang_anims[0].name = own ? TAG_HANG : TAG_FLYY;
        hang_anims[0].start = own ? 1.0f : HANG_FRAME;
        a[0] = g_hang_state == 2 && !own ? CLIMB_ANIM_ID : HANG_ANIM_ID; a[2] = (uint32_t)&hang_ctrl;
    }
    else if (a[2] != (uint32_t)&hang_ctrl) g_game_anim_ctrl = a[2];
}
