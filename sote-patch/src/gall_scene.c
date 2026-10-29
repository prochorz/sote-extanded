/* Gall Run (gallrun.c): the rock nodes the mission draws with, the stages' geometry, the hidden rocks. */
#include "common.h"
#include "gall.h"

#define CLASS_ASTR       0x801128C8 /* the base level: rocks */
#define CLASS_ASTF       0x801128F8 /* the base level: debris around the ship */
#define ASTR_NODE        0x70
#define CANYON_ASTR      1          /* and the canyon (stage 1) */
#define LAND_ASTR        2          /* and the landscape (stage 2) */
#define BOTH_BEFORE      80         /* nodes before the switch stage 2 is drawn too, */
#define BOTH_AFTER       20         /* nodes after it stage 1 still is (the stages stand one after the other) */
#define ASTF_LIST        0x10
#define DOLY_BELT        0x9C       /* the base level: node of the rock belt backdrop */
#define ASTF_PIECES      8
#define CHOR_WORLD_NODE  0x158      /* Chor: its world node (a debris model, emptied) */
/* image header (harness/gall_asset.py) */
#define IMG_SET1         4          /* stage 1: part count, part list, bounding box */
#define IMG_SCALE        24         /* float scale x, y */
#define IMG_SCALE_Z      32         /* float scale z */
#define IMG_SET2         36         /* stage 2: part count, part list, bounding box */
#define IMG_COS          52         /* stage 2 pose: turn about z (cos, sin), then translation */
#define IMG_SIN          56
#define IMG_POS          60
#define IMG_SCALE2       76         /* float: stage 2 drawn this much larger again */
#define IMG_AST_N        172        /* the space rocks' part count: the last of stage 2's (gallrun/space.py) */
#define IMG_CAP_N        264        /* the wall tops' part count: stage 2's before the space rocks' (gallrun/cliffs.py caps()) */
#define SD_MESH          0x801A3B74 /* the base level's Star Destroyer mesh (32 parts), loaded in sub-level 32; its own node
                                     * is under Chor's world node, emptied (show_canyon) */
#define SD_SCALE         0.4f       /* drawn this size (space.py SD_SCALE), its nose (+y) at IMG_SD's heading */
#define SD_MTX_SLOT      150        /* our node's world-matrix slot (+0x44; free: the battle 0..109, the towers 140..:
                                     * space.py TOWER_MTX_SLOT) */
#define NODE_SLOT        0x44
#define TNODE            0x48       /* bytes of a transform node */
#define BELT_ON          0          /* the rock belt in space (0: off for now, the user, 2026-10-14) */
#define BELT_GROW        300.0f     /* the belt's band grows to its height over this much climb from AST_SHOW */
#define BELT_MIN         0.02f
#define BELT_FAR         30.0f      /* the belt this much larger: its rings ~16000 and ~23000 round the Star Destroyer (hide_rocks; the Falcon reaches space ~7000 off it: at 15 the inner ring was by it, "behind the ring", the user) */
float g_belt_k = BELT_FAR;          /* (a variable, not static: probes try other sizes) */

/* Nodes we draw with: the space rocks' (class Astr, node at +ASTR_NODE). A rock gets a decoy
 * copy of its node to pose and hide; the real node stays in the world tree for us. (Chor's own
 * world node is no use in the base level: Chor builds that node's matrix itself before the draw.) */
uint32_t astr_take(uint32_t i, uint32_t *decoy, uint32_t *real) {
    if (U32(CLASS_ASTR + 8) <= i) return 0;
    uint32_t astr = U32(CLASS_ASTR + 0x10) + i * U32(CLASS_ASTR + 0xC), n = U32(astr + ASTR_NODE);
    if (n == (uint32_t)decoy) return *real;
    if (!valid_ptr(n) || U32(n) >> 28 != 0xD) return 0;
    for (int k = 0; k < 0x48 / 4; k++) decoy[k] = U32(n + 4 * k);
    U32(astr + ASTR_NODE) = (uint32_t)decoy;
    return *real = n;
}

/* The canyon (stage 1) and the landscape (stage 2): a rock's node each (the second, the
 * third), posed with the stage's turn and translation, scaled, holding a mesh node of ours with the
 * image's parts; a stage not drawn has no children. The image cuts both at the switch, so round it
 * both are drawn and stage 2 goes on where stage 1 ends. Chor's world node (its debris model) is emptied. */
static uint32_t g_cy_decoy[2][0x48 / 4], g_cy_node[2], g_cy_mesh[2][6], g_cy_list[2][2];

/* Stage 2's node also holds a transform node of ours in space (nested: its rows in the stage's frame, which is turned
 * and scaled x k, k, kz): the game's own Star Destroyer mesh, where its copy's parts were. */
static uint32_t g_sd_node[TNODE / 4], g_sd_list[1];

static uint32_t sub_node(uint32_t *t, uint32_t n, uint32_t *list, uint32_t child, uint32_t slot) {
    for (int j = 0; j < TNODE / 4; j++) t[j] = U32(n + 4 * j);   /* (a transform node as the stage's) */
    list[0] = child;
    t[NODE_COUNT / 4] = 1; t[NODE_LIST / 4] = (uint32_t)list; t[NODE_SLOT / 4] = slot;
    U16((uint32_t)t + NODE_SHOW) = 0xFF03;                       /* (drawn, its rows changed) */
    return (uint32_t)t;
}

static uint32_t star_destroyer(uint32_t n, float c, float s, float k, float kz) {
    float a = F32(GALL_RAM + IMG_SD + 12), ca = cos_r(a), sa = sin_r(a);
    float cf = sa * c - ca * s, sf = -ca * c - sa * s, w = SD_SCALE / k;   /* (its turn a - pi/2 less the stage's) */
    uint32_t t = sub_node(g_sd_node, n, g_sd_list, SD_MESH, SD_MTX_SLOT);
    float rot[9] = { cf * w, sf * w, 0, -sf * w, cf * w, 0, 0, 0, SD_SCALE / kz };
    float dx = F32(GALL_RAM + IMG_SD) - F32(GALL_RAM + IMG_POS), dy = F32(GALL_RAM + IMG_SD + 4) - F32(GALL_RAM + IMG_POS + 4);
    float at[3] = { (c * dx + s * dy) / k, (-s * dx + c * dy) / k, (F32(GALL_RAM + IMG_SD + 8) - F32(GALL_RAM + IMG_POS + 8)) / kz };
    for (int i = 0; i < 9; i++) F32(t + NODE_ROT + 4 * i) = rot[i];
    for (int i = 0; i < 3; i++) F32(t + NODE_POS + 4 * i) = at[i];
    return t;
}

static void show_stage(int stage, int on) {
    uint32_t n = astr_take(stage == 2 ? LAND_ASTR : CANYON_ASTR, g_cy_decoy[stage - 1], &g_cy_node[stage - 1]);
    if (!n) return;
    if (!on) { U32(n + NODE_COUNT) = 0; return; }
    float c = stage == 2 ? F32(GALL_RAM + IMG_COS) : 1.0f, s = stage == 2 ? F32(GALL_RAM + IMG_SIN) : 0.0f;
    float k = F32(GALL_RAM + IMG_SCALE), kz = F32(GALL_RAM + IMG_SCALE_Z);
    if (stage == 2) { k *= F32(GALL_RAM + IMG_SCALE2); kz *= F32(GALL_RAM + IMG_SCALE2); }
    float rot[9] = { c * k, s * k, 0, -s * k, c * k, 0, 0, 0, kz };  /* rows: x' = x*m0 + y*m3 + z*m6 */
    for (int i = 0; i < 9; i++) F32(n + NODE_ROT + 4 * i) = rot[i];
    for (int i = 0; i < 3; i++) F32(n + NODE_POS + 4 * i) = stage == 2 ? F32(GALL_RAM + IMG_POS + 4 * i) : 0.0f;
    uint32_t set = stage == 2 ? IMG_SET2 : IMG_SET1, *mesh = g_cy_mesh[stage - 1];
    mesh[0] = MESH_W0; mesh[1] = 0; mesh[2] = 0;
    mesh[3] = U32(GALL_RAM + set); mesh[4] = U32(GALL_RAM + set + 4); mesh[5] = U32(GALL_RAM + set + 8);
    if (stage == 2 && g_alt < CANYON_DROP) {
        mesh[3] -= U32(GALL_RAM + IMG_AST_N);                    /* (the space rocks: in space only; */
        if (g_cine != 2) mesh[3] -= U32(GALL_RAM + IMG_CAP_N);   /* the wall tops from the end scene on: seen from above) */
    }
    else if (stage == 2 && g_alt < AST_SHOW) mesh[3] = 0;        /* (the fog lifting: neither) */
    else if (stage == 2) {                                       /* (and in space only those: the canyon far below, */
        mesh[4] += 4 * (mesh[3] - U32(GALL_RAM + IMG_AST_N));    /* no longer fogged, showed: the user) */
        mesh[3] = U32(GALL_RAM + IMG_AST_N);
    }
    g_cy_list[stage - 1][0] = (uint32_t)mesh;
    uint32_t kids = 1;
    if (stage == 2 && g_alt >= AST_SHOW) g_cy_list[1][kids++] = star_destroyer(n, c, s, k, kz);
    U32(n + NODE_COUNT) = kids;
    U32(n + NODE_LIST) = (uint32_t)g_cy_list[stage - 1];
    U16(n + NODE_SHOW) = 0xFF03;         /* drawn (high byte) + the per-frame flags owners set */
}

void show_canyon(uint32_t node) {
    if (U32(CLASS_CHOR + 8)) {
        uint32_t own = U32(U32(CLASS_CHOR + 0x10) + CHOR_WORLD_NODE);
        if (valid_ptr(own) && U32(own) >> 28 == 0xD) U32(own + NODE_COUNT) = 0;
    }
    uint32_t sw = U32(GALL_RAM + IMG_SWITCH);
    show_stage(1, node < sw + BOTH_AFTER);
    show_stage(2, node + BOTH_BEFORE >= sw);
}

/* The base level's rocks: the rock belt backdrop the camera carries (Doly +0x9C: a node
 * whose children draw a one-part belt mesh twice), the space rocks (class Astr, node at +0x70:
 * not drawn, high byte of +2) and the debris around the ship (AstF, ASTF_PIECES nodes listed
 * from +0x10 that share one model group). Child counts are set to 0 (owners keep showing their
 * nodes before the draw); the level heap is rebuilt on every load. */
void hide_rocks(void) {
    uint32_t n = U32(CLASS_ASTR + 8), a = U32(CLASS_ASTR + 0x10), size = U32(CLASS_ASTR + 0xC);
    for (uint32_t i = 0; i < n && i < 32; i++, a += size)
        if (valid_ptr(U32(a + ASTR_NODE))) U16(U32(a + ASTR_NODE) + NODE_SHOW) &= 0x00FF;
    uint32_t belt = U32(CLASS_DOLY + 8) ? U32(U32(CLASS_DOLY + 0x10) + DOLY_BELT) : 0;
    static uint32_t belt_n;                                      /* (its own count: back in space) */
    if (valid_ptr(belt) && U32(belt) >> 28 == 0xD) {
        if (U32(belt + NODE_COUNT)) belt_n = U32(belt + NODE_COUNT);
        U32(belt + NODE_COUNT) = BELT_ON && g_alt >= AST_SHOW ? belt_n : 0;
        static uint32_t kid[2];                                  /* the band grows out of the horizon's line (the user: */
        static float len0[2][3];                                 /* it came in all at once) and stands BELT_FAR further */
        float u = (g_alt - AST_SHOW) / BELT_GROW;                /* out (beyond the Star Destroyer, the user): its two */
        u = u < 0 ? 0 : u > 1 ? 1 : u; u = u * u * (3 - 2 * u); /* children's rows scaled from their own lengths (the */
        if (u < BELT_MIN) u = BELT_MIN;                          /* game turns the first every other frame; copies of */
        uint32_t l = U32(belt + NODE_LIST);                      /* them came by the camera in dark wedges) */
        for (uint32_t i = 0; i < 2 && i < belt_n && valid_ptr(l); i++) {
            uint32_t c = U32(l + 4 * i);
            if (!valid_ptr(c) || U32(c) >> 28 != 0xD) continue;
            float *r = (float *)(c + NODE_ROT);
            if (kid[i] != c) {
                kid[i] = c;
                for (int k = 0; k < 3; k++) len0[i][k] = sqrt_f(r[3 * k] * r[3 * k] + r[3 * k + 1] * r[3 * k + 1] + r[3 * k + 2] * r[3 * k + 2]);
            }
            for (int k = 0; k < 3; k++) {
                float m = sqrt_f(r[3 * k] * r[3 * k] + r[3 * k + 1] * r[3 * k + 1] + r[3 * k + 2] * r[3 * k + 2]);
                float want = len0[i][k] * g_belt_k * (k == 2 ? u : 1);
                if (m > 1e-6f) for (int j = 0; j < 3; j++) r[3 * k + j] *= want / m;
            }
        }
        for (int j = 0; j < 3; j++)                              /* round the Star Destroyer, not the camera (the user) */
            F32(belt + NODE_POS + 4 * j) = F32(GALL_RAM + IMG_SD + 4 * j);
    }
    if (!U32(CLASS_ASTF + 8)) return;
    for (int i = 0; i < ASTF_PIECES; i++) {   /* AstF shows and poses its nodes before the draw */
        uint32_t d = U32(U32(CLASS_ASTF + 0x10) + ASTF_LIST + 4 * i);
        if (valid_ptr(d) && U32(d + NODE_COUNT) == 1 && valid_ptr(U32(U32(d + NODE_LIST))))
            U32(U32(U32(d + NODE_LIST)) + NODE_COUNT) = 0;   /* the model group under it: empty */
    }
}
