/* The Gall Run's ship (gallrun.c, built with it): the player ship (class Stft) is the Millennium
 * Falcon. The model is in the level itself: gallrun/level_edit.py gives the Gall Run level's ship
 * model the Falcon's mesh node (local/game/falcon.bin, made by harness/falcon_asset.py, in the ROM
 * after the payload, copied to FALCON_RAM by _start; header {'FALC', part count, part list,
 * bounding box, turret x, y, top z, bottom z, mesh node}) in the Outrider hull's place, without the
 * Outrider's engine glows. What stays per frame is what the game builds every frame: the Stft draw
 * method (0x8009C318) builds each gun node's matrix (the aim rotation plus z +5.2 / -5.0) and the
 * pulsing engine glow's; falcon_gun runs right after it copies a matrix into a node (hook at
 * 0x8009C790) and moves the guns onto the Falcon's turret domes and the glow onto its engine strip,
 * and moves the whole ship as the Gall Run flies it (g_ship_*). falcon_frame finds the nodes (once per frame
 * from the overlay hook: our level and the stock one have the model at the same address).
 * One model everywhere (a copy in the image took the scenes' warm light): Cut 05 and the last scene draw falcon.bin's parts too (gall_chain.c), unlit
 * as those scenes' own Outrider is; falcon_look() keeps falcon.bin lit (materials 0xE, normals as built) in every other
 * level, unlit (materials +0 0xC, +0xC 0, the image's grey table IMG_FALCON_COL in the vertex bytes) in those two.
 */
#include "common.h"

#define LEVEL_BASE  6
#define LEVEL_CHASE      29          /* Station Chase: Leebo flies, the player is the gunner */
#define LEVEL_GALL       32          /* the Gall Run's own sub-level (gall.h) */
#define LEVEL_CUT05      11          /* Cut 05 and the last scene: falcon.bin drawn unlit there (gall_chain.c; D9) */
#define LEVEL_FINAL      31
#define IMG_FALCON_COL   412         /* the Gall Run image: -> {vertex count, 3 grey bytes a vertex} (space.falcon_colours()) */
#define FALCON_VTX_MAX   600         /* falcon.bin's vertices (587) */
#define MAT_LIT          0xE         /* a part material's +0 (and +0xC) lit; unlit: +0 0xC, +0xC 0 */
#define MAT_UNLIT        0xC
#define UNCACHED(a)      (((a) & 0x1FFFFFFFu) | 0xA0000000u)   /* the vertex bytes: read by the RSP, not the CPU */
#define TAG_STFT         0x53746674u
#define TAG_FALC         0x46414C43u
#define STFT_MODEL       0x0B4       /* Stft: model root node */
#define NODE_KIND(n)     (U32(n) >> 28)  /* 3: mesh, else a group/transform node */
#define NODE_COUNT       0x0C        /* children, or parts of a mesh */
#define NODE_LIST        0x10
#define MESH_BOX         0x14        /* bounding box, 8 vertices */
#define NODE_ROT         0x14        /* transform node: rotation rows (9 floats) */
#define NODE_POS         0x38        /* transform node: translation (3 floats) */
#define GUN_MIN_Z        1.0f        /* a transform node this far above/below the hull holds a gun */
#define MAX_MESH         8
#define MAX_GUN          4
#define GUN_SCALE        0.6f       /* the guns this size (the user: far too big on the Falcon) */
#define HDR_TURRET       16          /* header: turret x, y, top z, bottom z */
#define GLOW_MIN         1.5f       /* the glow's width (x, z) at least this: the game shrinks it to nothing when it
                                     * thinks the ship stands (the Gall Run's end scene moves it itself: the user, it went out) */
#define GLOW_Y           -5.0f       /* the pulsing engine glow (Outrider stern, y -11.4, x +-7) moved behind the Falcon's stern */
#define GLOW_Z           0.2f       /* (at -4.5, 0 it sat under the hull: "deep in the Falcon", picked by screenshots) */
#define GLOW_HIGH        1.0f       /* its height row while g_glow_w sets its width (the native fight) */
#define GLOW_W           1.35f       /* into the Falcon's stern at its engine strip (y -15.9) and widened */

static uint32_t g_root;             /* model the saved values belong to */
static int g_n;
static uint32_t g_mesh[MAX_MESH], g_old[MAX_MESH][3];
static int g_hull;
static int g_ngun;
static uint32_t g_gun[MAX_GUN], g_gun_mesh[MAX_GUN];
static uint8_t g_gun_top[MAX_GUN];
float g_glow_at[2] = { GLOW_Y, GLOW_Z };   /* (a global: the harness tries places) */
static uint32_t g_glow;             /* transform node at the origin (it pulses) */

static void collect(uint32_t node, int depth, uint32_t parent) {
    if (!valid_ptr(node) || depth > 4) return;
    if (NODE_KIND(node) == 3) {
        if (parent && absf(F32(parent + NODE_POS + 8)) > GUN_MIN_Z && g_ngun < MAX_GUN) {
            g_gun[g_ngun] = parent;
            g_gun_mesh[g_ngun] = node;
            g_gun_top[g_ngun] = F32(parent + NODE_POS + 8) > 0;
            g_ngun++;
        } else if (parent) {
            g_glow = parent;
        }
        for (int i = 0; i < g_n; i++)
            if (g_mesh[i] == node) return;         /* the gun's mesh hangs under two nodes */
        if (g_n == MAX_MESH) return;
        g_mesh[g_n] = node;
        g_old[g_n][0] = U32(node + NODE_COUNT);
        g_old[g_n][1] = U32(node + NODE_LIST);
        g_old[g_n][2] = U32(node + MESH_BOX);
        if (g_old[g_n][0] > g_old[g_hull][0]) g_hull = g_n;
        g_n++;
        return;
    }
    uint32_t n = U32(node + NODE_COUNT), list = U32(node + NODE_LIST);
    if (n > 16 || !valid_ptr(list)) return;
    for (uint32_t i = 0; i < n; i++) collect(U32(list + 4 * i), depth + 1, NODE_KIND(node) == 0xD ? node : 0);
}

static int shown(void) {
    return g_n && U32(g_mesh[g_hull] + NODE_LIST) == U32(FALCON_RAM + 8);
}

/* Ship drawn this much below its path position (Gall Run: the camera rides the path behind it),
 * moved off it by g_ship_off (Gall Run stage 1: the player steers it in the canyon), or put at g_ship_at
 * while g_ship_at_on (flown: the place itself, not off Chor's next place), and banked
 * by g_ship_roll (radians, right wing down; Gall Run: into the turns), g_ship_pitch (nose down) and g_ship_yaw (to the right;
 * or onto the heading g_ship_head while g_ship_head_on). */
float g_ship_drop;
float g_ship_off[3];
float g_ship_at[3];
int g_ship_at_on;
float g_ship_roll;
float g_ship_pitch;
float g_ship_yaw;
float g_ship_head;                  /* while g_ship_head_on (stage 1 flown): the heading itself (world yaw, radians, as
                                     * g_fly_yaw), whatever Chor's facing is that frame (put back in steps flying back,
                                     * its facing and g_ship_yaw's head differed by a step's turn: the nose jittered) */
int g_ship_head_on;
float g_glow_w;
extern int g_native;                /* (gall_native.c: the free flight on the game's own) */

/* sin_r, once for falcon.c and gallrun.c (an inline copy in each costs ~230 bytes). */
__attribute__((noinline)) float ship_sin(float x) { return sin_r(x); }

/* Turn a transform node: rows (byte offsets) p and q, of right 0, forward 12, up 24, turned by a
 * (p = right, q = up: a roll, right wing down; forward, up: a pitch, nose down; right, forward: a
 * yaw, to the right). */
void node_turn(uint32_t node, float a, int p, int q) {
    float c = ship_sin(a + PI_F / 2), s = ship_sin(a);
    for (int i = 0; i < 3; i++) {
        float r = F32(node + NODE_ROT + p + 4 * i), u = F32(node + NODE_ROT + q + 4 * i);
        F32(node + NODE_ROT + p + 4 * i) = r * c - u * s;
        F32(node + NODE_ROT + q + 4 * i) = u * c + r * s;
    }
}

/* From the Stft draw method, right after the model root or a gun node got this frame's matrix. */
void falcon_gun(uint32_t node) {
    if (node == g_root) {
        for (int i = 0; i < 3; i++)                  /* (Chor's matrix is the next draw's, the offset from this frame's */
            F32(node + NODE_POS + 4 * i) = (g_ship_at_on ? g_ship_at[i] : F32(node + NODE_POS + 4 * i) + g_ship_off[i])
                                           - (i == 2 ? g_ship_drop : 0);   /* Chor: flown, it jerked, the user) */
        if (g_ship_head_on) {                        /* the root turned from its forward row's yaw onto g_ship_head */
            float a = g_ship_head - atan2_r(F32(node + NODE_ROT + 16), F32(node + NODE_ROT + 12));
            while (a > PI_F) a -= 2 * PI_F;
            while (a < -PI_F) a += 2 * PI_F;
            node_turn(node, -a, 0, 12);
        } else if (g_ship_yaw != 0) node_turn(node, g_ship_yaw, 0, 12);
        if (g_ship_pitch != 0) node_turn(node, g_ship_pitch, 12, 24);
        if (g_ship_roll != 0) node_roll(node, g_ship_roll);
    }
    if (!shown()) return;
    if (node == g_glow) {
        if (g_glow_w > 0 && F32(node + NODE_ROT) > 0.5f) {     /* (flying: the game's glow is 1..2 by its speed, */
            F32(node + NODE_ROT) = g_glow_w;                     /* hardly seen: the user, all boost); its height */
            F32(node + NODE_ROT + 32) = GLOW_HIGH;               /* not: scaled by it (to 2.2) the strip, off the */
        }                                                        /* node's middle, hung under the hull (the user) */
        else if (F32(node + NODE_ROT) < GLOW_MIN) {              /* (rows: x, y, z scale, no turn) */
            F32(node + NODE_ROT) = F32(node + NODE_ROT + 32) = GLOW_MIN;
            F32(node + NODE_ROT + 16) = 1.05f;
        }
        F32(node + NODE_POS + 4) += g_glow_at[0];
        F32(node + NODE_POS + 8) += g_glow_at[1];
        for (int i = 0; i < 3; i++) F32(node + NODE_ROT + 4 * i) *= GLOW_W;
    }
    for (int i = 0; i < g_ngun; i++) {
        if (g_gun[i] != node) continue;
        for (int j = 0; j < 9; j++)                              /* (the Outrider's: too big here; in the native flight */
            F32(node + NODE_ROT + 4 * j) = g_native              /* the ship's own rows, the lower gun's flip kept: its */
                ? (j == 4 ? GUN_SCALE : (j == 0 || j == 8) ? (g_gun_top[i] ? GUN_SCALE : -GUN_SCALE) : 0)   /* bolts go */
                : F32(node + NODE_ROT + 4 * j) * GUN_SCALE;      /* along the nose) */
        uint32_t t = FALCON_RAM + HDR_TURRET;
        F32(node + NODE_POS) = F32(t);
        F32(node + NODE_POS + 4) = F32(t + 4);
        F32(node + NODE_POS + 8) = F32(t + (g_gun_top[i] ? 8 : 12));
    }
}

#if FEATURE_GALLRUN
static uint8_t g_norm[FALCON_VTX_MAX * 3];   /* falcon.bin's normals as built (+12..+14), saved on the first frame */
static int g_norm_saved, g_unlit;

/* falcon.bin's vertices walked as space.falcon_vertices() does (parts, their geometry DLs, the G_VTX blocks): op 0
 * saves the normals, 1 writes the image's table (unlit), 2 the saved normals back (lit); the materials set to match. */
static int falcon_look(int op) {
    uint32_t col = U32(GALL_RAM + IMG_FALCON_COL), n = U32(FALCON_RAM + 4), lst = U32(FALCON_RAM + 8);
    if (U32(GALL_RAM) != 0x47414C4Cu || !valid_ptr(col) || U32(col) > FALCON_VTX_MAX || n > 32) return 0;
    uint32_t nv = U32(col), k = 0;
    const uint8_t *src = op == 1 ? (const uint8_t *)(col + 4) : g_norm;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t part = U32(lst + 4 * i), mat = U32(part + 0x24);
        if (op) { U32(mat) = op == 1 ? MAT_UNLIT : MAT_LIT; U32(mat + 0xC) = op == 1 ? 0 : MAT_LIT; }
        for (uint32_t a = U32(part + 0x28); U32(a) >> 24 != 0xB8; a += 8) {
            if (U32(a) >> 24 != 0x04) continue;
            for (uint32_t j = 0, c = (U32(a) & 0xFFFF) >> 9; j < c && k < nv; j++, k++) {
                volatile uint8_t *v = (volatile uint8_t *)UNCACHED(U32(a + 4) + 16 * j + 12);
                for (int b = 0; b < 3; b++) { if (op) v[b] = src[3 * k + b]; else g_norm[3 * k + b] = v[b]; }
            }
        }
    }
    return 1;
}
#endif

void falcon_frame(void) {
    uint32_t stft = 0, root;
    int lvl = S16(LEVEL_ID);
#if FEATURE_GALLRUN
    if (U32(FALCON_RAM) == TAG_FALC) {             /* (lit as built at boot: the first frame saves its normals) */
        if (!g_norm_saved) g_norm_saved = falcon_look(0);
        int unlit = lvl == LEVEL_CUT05 || lvl == LEVEL_FINAL;
        if (g_norm_saved && unlit != g_unlit && falcon_look(unlit ? 1 : 2)) g_unlit = unlit;
    }
#endif
    if (lvl == LEVEL_BASE || lvl == LEVEL_CHASE || lvl == LEVEL_GALL) stft = ((find_fn)FIND_CLASS)(TAG_STFT, 0);
    root = stft ? U32(stft + STFT_MODEL) : 0;
    g_root = root;                                 /* every frame: a reloaded level (the stock base level */
    g_n = g_hull = g_ngun = 0;                     /* or ours) has its model at the same address */
    g_glow = 0;
    if (valid_ptr(root) && U32(FALCON_RAM) == TAG_FALC) collect(root, 0, 0);
}
