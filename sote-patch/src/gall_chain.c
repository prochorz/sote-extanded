/* Gall Run in the story: Cut 05 (sub-level 11) says the new lines and shows the
 * Falcon and three X-Wings with the Outrider; at its end the mission starts; the mission's end goes on to Cut 06
 * (13) and the original Gall. Runs on every sub-level from gallrun_frame() (chain_frame()) and the pad hook
 * (chain_pad()). */
#include "common.h"
#include "gall.h"
#include "gall_final.h"
#include "gall_c05.h"

#define PAD_RAW          0x80113080 /* raw controller data, 6 bytes each (gallrun.c) */
#define PAD_B            0x4000
#define PAD_START        0x1000
#define CUT05            11
#define CUT06            13
#define FINAL_CUT        31         /* the game's last scene: the hyperspace scene (step 5) */
#define C05_TABLE        0x801A1A24 /* Cut 05's lines: three pointers, shown in turn by the scene (D13) */
#define C05_STOCK        0x801A18D0 /* its first line (the blob is Cut 05's) */
#define C05_ROOT         0x80198D90 /* the root group: one child, the Outrider (D15) */
#define C05_OR           0x80198D00 /* its transform node (the scene moves it), */
#define C05_SCALE        0x80198D48 /* its scale child (0.5), */
#define C05_MESH         0x80198DA4 /* its mesh */
#define C05_TAIL         30         /* frames after the last line is let go: the mission starts (the scene ends at ~130) */
#define TNODE            0x48       /* bytes of a transform node */
#define NODE_SLOT        0x44       /* its world-matrix slot */
#define SHIPS            4          /* the Falcon, three X-Wings */
#define SHIP_SLOT        1          /* our nodes' slots: transforms 1..4, scales 5..8 (the scene uses 0) */
#define OR_SCALE         0.5f       /* the Outrider's scale node: the Falcon at the same, */
#define XW_SCALE         0.4f       /* an X-Wing at 0.8 of it (gall_ties.c XWING_K) */
#define XW_LEAVE_F       300        /* frames the X-Wings climb away after Luke's line, */
#define XW_DRIFT_V       0.3f       /* units a frame back and */
#define XW_DRIFT_UP      0.2f       /* up (world) */
#define FALCON_PARTS     (FALCON_RAM + 4)   /* falcon.bin's part count, part list, box: the scenes draw the mission's model
                                     * (falcon.c gives it the scenes' unlit look here) */
#define IMG_STILLS       340        /* the image: the pictures' sprites, Lando and Leia, Luke (still.py) */
#define SPRITES          0x8013CE2C /* -> the level's HUD sprite table */
#define SPRITE_SHOW      0x80009088 /* (element, x, y): the scenes' Bmap draws its picture so */
#define STILL_Y          16         /* the stills' y (the stock ones') */
#define PIC_SLOT         4          /* Cut 05's table: 0..3 used; our pictures there */
#define BMAP_REC         0x801129B8 /* class Bmap: the scenes' pictures (+8 flags: 0x20 not drawn; +0xA its sprite; +0x1A, +0x1C x, y) */
#define FIN_STILL        14         /* the last scene's Dash-and-Leebo still: sprite 14, 512 x 140, panned; */
#define FIN_FACES        3          /* 15..17 its face overlays */
#define FALCON_LEN_IMG   37.2f      /* falcon.bin's Falcon: its length (its part boxes, y -14.7..22.5) */
#define IMG_XWING        188        /* the image: the X-Wing's part count, part list, box */
#define IMG_GLOW_BENT    240        /* the image: the Falcon's engine glow round its stern (gall_story.c glow()) */
#define IMG_OR_GLOW      352        /* the image: our level's Outrider's engine glows, in Cut 05's units (space.or_glow()) */
#define OR_RUN_K         4.47f      /* Cut 05's Outrider model to our level's (the same model: their part boxes) */
#define GLOW_SLOT        (SHIP_SLOT + 2 * SHIPS)   /* the Falcon's glow node's world-matrix slot */
#define FGLOW_Y          (-5.0f)    /* the Falcon's glow node as falcon.c places the game's in the run (GLOW_Y, GLOW_Z, */
#define FGLOW_Z          0.2f       /* GLOW_W x a width of FGLOW_WIDE, GLOW_HIGH) */
#define FGLOW_K          1.35f
#define FGLOW_WIDE       1.5f

/* The ships in the Outrider's frame (its rows x, y, z; world units). Seen from the scene's camera: the X-Wings ahead
 * and up, the Falcon up and to its left (placed by screenshots: on the camera's side of the Outrider, -y less than
 * about 0, it was not drawn; why not is not known). */
static const float SHIP_AT[SHIPS][3] = {          /* (world units: the ships at our level's size against it, OR_RUN_K; */
    { 0.0f, -200.0f, 45.0f }, { -65.0f, -170.0f, 40.0f }, { 65.0f, -170.0f, 40.0f },   /* behind it, the user) */
    { -75.0f, -70.0f, 30.0f },
};
#define FALCON_I         3

/* Cut 05 as seven frames, the same every run: a picture frame shows its picture
 * (still) and its line with the scene frozen, held as the game holds a line; a shot frame lets the scene run on, its own
 * 3D as it is, till it holds its next line (the scene put at its first hold at the start: gall_c05.h). */
enum { PIC_NONE, PIC_LANDO_LEIA, PIC_LUKE, PIC_DASH };
enum { SHOT_NONE, SHOT_FLY, SHOT_SPACE };
typedef struct { const char *text; uint8_t pic, shot; } c05_frame;
static const c05_frame FRAMES[] = {
    { "~h~0Lando, before I fried his circuits, IG-88~nsaid Boba Fett was in the Zhar system:~nthe Imperial moon base on Gall.", PIC_DASH, 0 },
    { "~h~7If Han is on that moon, we're going in.~nWhatever it takes.", PIC_LANDO_LEIA, 0 },
    { "~h~5Rogue Group and I will hit them in orbit~nand draw their fighters off. That buys~nyou some time.", PIC_NONE, SHOT_FLY },
    { "~h~5Rogue Group and I will hit them in orbit~nand draw their fighters off. That buys~nyou some time.", PIC_LUKE, 0 },
    { "~h~0Their patrols blast anything in the sky.~nBut I know a canyon that runs right up~nto the spaceport.", PIC_NONE, SHOT_SPACE },
    { "~h~0Stay on my tail and I'll get you in.~nFor the right price, of course...", PIC_DASH, 0 },
    { "~h~1The right price? Dash, you'd charge your~nown mother for directions.", PIC_LANDO_LEIA, 0 },
};
#define C05_FRAMES       (int)(sizeof FRAMES / sizeof FRAMES[0])

int g_chain_fin;                    /* the mission ended in the chain: Cut 06 and Gall 6a are the game's own */
static int g_c05_tail;              /* frames since it was let go */
static float g_xw_leave;            /* scene frames since Luke's line was let go */
static int g_prev_lvl = -1;
int g_c05_ships = SHIPS;            /* (probes: how many of the ships are added) */
int g_c05_dbg[1] = { 1 };           /* (probes: [0] 1 our world-matrix slots, 2 the Outrider's mesh for all ships) */
static uint32_t g_root_list[1 + SHIPS], g_scale_list[SHIPS][1], g_mesh_list[SHIPS][1], g_xw_mesh[6], g_fa_mesh[6];
static int g_c05_ours;              /* Cut 05's blob seen (its first line pointer the stock one) */
static uint32_t g_tnode[SHIPS][TNODE / 4], g_snode[SHIPS][TNODE / 4];
static uint32_t g_og_list[2];
static uint32_t g_org_mesh[6], g_fg_node[TNODE / 4], g_fg_list[1], g_fg_mesh[6], g_fa_list[2];   /* the glows */

static int g_c05_frame;             /* Cut 05's frame up (1..C05_FRAMES; past: done: cut05()) */
static int g_c05_t;                 /* frames in the frame up (g_c05_frame) */
static int g_c05_luke;              /* the scene's Luke hold let go */
/* The space shot (frame 5): from the Luke hold let go the root's one child is
 * our near node over the Outrider and the ships. Scene 2's clock s runs from frame 5's first frame (g_s2_clk0, taken
 * with g_near_set). Every ship flies a straight way at one speed, S2_V a scene frame, along g_s2_dir (the eye through
 * Gall's centre on screen, taken on that frame): from eye - S2_BACK x g_s2_dir + its lane (x right, z up, x OR_RUN_K)
 * at its start S2_AT (not drawn before it); from S2_BREAK the X-Wings gain a rightward part easing up to S2_RIGHT over
 * S2_BREAK_F. Noses along the velocity, smoothed (NOSE_EASE). The near node carries the Outrider: its rows turn the
 * scene's Outrider to its way (D5), its place puts it there; the other ships are given in its frame. */
#define NEAR_SLOT        10         /* its world-matrix slot (ours 1..9: GLOW_SLOT) */
#define S2_V             9.0f       /* (the Outrider's own pace in the scene: D1) */
#define S2_BACK          250.0f
#define S2_BREAK         170.0f
#define S2_BREAK_F       60.0f
#define S2_RIGHT         3.0f
#define S2_GALL          2          /* Gall's sprite (the brown sphere) */
#define S2_N             (SHIPS + 1)   /* X-Wings 0..2, the Falcon, the Outrider */
static const float S2_LANE[S2_N][2] = { { -9, -4 }, { 9, -2 }, { 0, 8 }, { -7, 4 }, { 7, -4 } };   /* (D1, D4: each way
                                     * >= 35 from the eye) */
static const float S2_AT[S2_N] = { 0, 20, 40, 90, 90 };
#define S2_END           400.0f     /* scene frames of s frame 5 lasts (1.5 x 267.8: ~21 s at C05_SPACE_SPEED;
                                     * the scene run on from clock 480, gall_c05.h C05_S2) */
static int g_near_set;              /* scene 2's frame taken (once, on the Luke hold's let-go frame) */
static float g_s2_clk0, g_s2_eye[3], g_s2_rt[3], g_s2_up[3], g_s2_dir[3], g_s2_gall[2], g_or_fwd[3], g_s2_n[9];
static uint32_t g_near_node[TNODE / 4], g_near_list[1];
static int g_c05_fn = -1;           /* whole scene frames since the Outrider set off (-1: not yet; held lines not counted) */
static float g_c05_clk;             /* the same, scene time (frames at its own speed: the speed added a running frame) */
static float g_c05_speed = 1, g_c05_used = 1;   /* the scene's speed for the next frame; the one its objects ran at */
static float g_c05_last[3];         /* its place a frame ago */
#define HIST             512        /* its places since it set off, a frame each */
static float g_c05_hist[HIST][3];
static const float FLYIN_LANE[SHIPS][3] = { { -3, -20, -1.5f }, { 0.3f, -20, -2.2f }, { -3.5f, -20, 0.3f }, { 1, -40, 3.5f } };   /* (as on bf22) */   /* (x, z
                                     * scaled so none passes within 30 units of the eye; the
                                     * Falcon's once more x 1.3, its one adjustment, and x 1.15: D17) */   /* (world:
                                     * the scene's camera stands at 0 looking along +y, docs/reverse-engineering.md; each
                                     * one's way starts here, behind it, and is the Outrider's after: close by it, big; the
                                     * X-Wings in on the left and the middle, the Falcon from above: the user) */
static const int FLYIN_D[SHIPS] = { 14, 35, 56, 80 };   /* (as on bf22) */   /* (its one adjustment: on screen
                                     * by clock 60 / 90 / 120 / the Falcon 150; below 0: further on its way past) */     /* frames each ship is behind it on its way (X-Wings, then the */
#define FLYIN_PASS       60         /* Falcon: the user, 2026-10-19; x 0.47: the Falcon on screen
                                     * by clock ~250), past the camera as it was; then over FLYIN_CATCH */
#define FLYIN_CATCH      360        /* frames each closes up onto its place by it */
#define FLYIN_SLOW       0.2f       /* (its way past the camera at this share of the Outrider's speed) */
#define FLYIN_V          3.0f       /* (units a frame back along its way before it set off) */
static float g_ship_last[SHIPS][3], g_ship_fwd[SHIPS][3];   /* each ship's place a frame ago, its way (smoothed) */
#define NOSE_EASE        0.15f      /* share of the new way taken a frame */
/* The Outrider's place h scene frames after it set off: between two stored places (slowed, a place lasts several
 * frames: read straight, the ships moved in steps); past the last stored one its place now (p). */
static void hist_at(float h, const float *p, float *out) {
    if (h < 0) h = 0;
    int a = (int)h, n = g_c05_fn < HIST - 1 ? g_c05_fn : HIST - 1;
    float w = h - (float)a;
    const float *x = a <= n ? g_c05_hist[a] : p, *y = a + 1 <= n ? g_c05_hist[a + 1] : p;
    for (int j = 0; j < 3; j++) out[j] = x[j] + (y[j] - x[j]) * w;
}
/* Ship n's way at scene-2 time s: its world place w and velocity v (units a scene frame). */
static void s2_way(int n, float s, float *w, float *v) {
    float r = 0, vr = 0, b = s - S2_BREAK;
    if (n < FALCON_I && b > 0) {                                 /* (the X-Wings bear off right: D1) */
        if (b < S2_BREAK_F) { vr = S2_RIGHT * b / S2_BREAK_F; r = 0.5f * vr * b; }
        else { vr = S2_RIGHT; r = S2_RIGHT * (b - 0.5f * S2_BREAK_F); }
    }
    for (int j = 0; j < 3; j++) {
        w[j] = g_s2_eye[j] + (S2_V * (s - S2_AT[n]) - S2_BACK) * g_s2_dir[j] + r * g_s2_rt[j]
            + OR_RUN_K * (S2_LANE[n][0] * g_s2_rt[j] + S2_LANE[n][1] * g_s2_up[j]);
        v[j] = S2_V * g_s2_dir[j] + vr * g_s2_rt[j];
    }
}
/* Scene 2's frame, once: the eye and the camera's rows, g_s2_dir through Gall's centre on screen (its sprite's place
 * + half its size, through the scene's projection: the harness's on-screen check inverted). */
static void s2_setup(uint32_t cam) {
    float fw[3], a = 0, b = 0, l = 0;
    for (int j = 0; j < 3; j++) {
        g_s2_eye[j] = F32(cam + 0x44 + 4 * j); g_s2_rt[j] = F32(cam + 0x14 + 4 * j);
        fw[j] = F32(cam + 0x24 + 4 * j); g_s2_up[j] = F32(cam + 0x34 + 4 * j);
    }
    uint32_t tb = U32(SPRITES), h = valid_ptr(tb) ? U32(tb + 4 * S2_GALL) : 0;
    if (valid_ptr(h)) {
        float kx = F32(h + 8), ky = F32(h + 12);
        if (!(kx > 0.05f && kx < 20)) kx = 1;
        if (!(ky > 0.05f && ky < 20)) ky = 1;
        g_s2_gall[0] = S16(h) + U16(h + 4) * kx * 0.5f; g_s2_gall[1] = S16(h + 2) + U16(h + 6) * ky * 0.5f;
        float fov = F32(PERSPECTIVE), asp = F32(PERSPECTIVE + 4), hf = fov * (PI_F / 360.0f);
        if (!(fov > 1 && fov < 179)) hf = PI_F / 4;
        if (!(asp > 0.1f)) asp = 4.0f / 3.0f;
        float py = cos_r(hf) / sin_r(hf), px = py / asp;
        a = (g_s2_gall[0] / 160.0f - 1) / px; b = (1 - g_s2_gall[1] / 120.0f) / py;
    }
    for (int j = 0; j < 3; j++) { g_s2_dir[j] = fw[j] + a * g_s2_rt[j] + b * g_s2_up[j]; l += g_s2_dir[j] * g_s2_dir[j]; }
    l = sqrt_f(l);
    for (int j = 0; j < 3; j++) g_or_fwd[j] = g_s2_dir[j] /= l;
}
/* Rows (x, y = the nose, z) for a nose along f; 0 if f has no length or points straight up/down. */
static int nose_rows(const float *f, float *m) {
    float fl = sqrt_f(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]);
    if (fl <= 1e-3f) return 0;
    float y[3] = { f[0] / fl, f[1] / fl, f[2] / fl }, x[3] = { y[1], -y[0], 0 }, xl = sqrt_f(x[0] * x[0] + x[1] * x[1]);
    if (xl <= 1e-3f) return 0;
    x[0] /= xl; x[1] /= xl;
    float z[3] = { x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0] };
    for (int j = 0; j < 3; j++) { m[j] = x[j]; m[3 + j] = y[j]; m[6 + j] = z[j]; }
    return 1;
}
static void cut05_ships(void) {
    uint32_t rl = U32(C05_ROOT + NODE_LIST);
    if (rl != (uint32_t)g_root_list && rl != (uint32_t)g_near_list && (U32(C05_ROOT + NODE_COUNT) != 1
        || U32(U32(C05_ROOT + NODE_LIST)) != C05_OR)) return;   /* (not the stock scene) */
    if (!U32(GALL_RAM + IMG_XWING) || !U32(FALCON_PARTS)) return;
    g_xw_mesh[0] = g_fa_mesh[0] = MESH_W0; g_xw_mesh[1] = g_xw_mesh[2] = g_fa_mesh[1] = g_fa_mesh[2] = 0;
    for (int j = 0; j < 3; j++) { g_xw_mesh[3 + j] = U32(GALL_RAM + IMG_XWING + 4 * j); g_fa_mesh[3 + j] = U32(FALCON_PARTS + 4 * j); }
    const float *r = (const float *)(C05_OR + NODE_ROT), *p = (const float *)(C05_OR + NODE_POS);
    float go = g_xw_leave > 0 ? (float)g_xw_leave : 0;
    uint32_t cam = U32(ACTIVE_CAMERA);
    int near = g_c05_frame == 5 && g_c05_luke && g_c05_t > 0 && valid_ptr(cam);   /* the space shot: the 3D brought to the
                                     * camera (from frame 5's second frame: the scene written back on its first, D7) */
    float nn[3] = { 0, 0, 0 }, s2 = 0;                           /* (the near node's place this frame) */
    float *last = g_c05_last;                                    /* the fly-in (the user, 2026-10-19: one ship after */
    int moved = p[0] != last[0] || p[1] != last[1] || p[2] != last[2];   /* another past the camera from behind, as the */
    if (g_c05_fn < 0 && moved && last[1] != 0) {                 /* run's opening): each on the Outrider's own way, */
        g_c05_fn = 0; g_c05_clk = 0; for (int j = 0; j < 3; j++) g_c05_hist[0][j] = p[j];   /* (from its first place in the 3D part: before it, it stood elsewhere) */   /* FLYIN_D frames behind it, then */
    }                                                            /* closing up */
    if (g_c05_fn >= 0 && !S16(MSG_HOLD)) {                       /* (one place a whole scene frame: slowed, not every */
        int f0 = g_c05_fn; g_c05_clk += g_c05_used;              /* frame; more */
        const float *a0 = f0 < HIST ? g_c05_hist[f0] : p;        /* than one a frame (C05_JUMP_SPEED): between the last */
        float span = g_c05_clk - (float)f0;                      /* stored and now) */
        while (g_c05_fn < (int)g_c05_clk) {
            g_c05_fn++;
            float w = g_c05_used > 1 ? (float)(g_c05_fn - f0) / span : 1;
            if (g_c05_fn < HIST) for (int j = 0; j < 3; j++) g_c05_hist[g_c05_fn][j] = a0[j] + (p[j] - a0[j]) * w;
        }
    }
    for (int j = 0; j < 3; j++) last[j] = p[j];
    g_root_list[0] = C05_OR;
    float *N = g_s2_n;                                           /* (the near node's rows: D5) */
    if (near) {
        if (!g_near_set) { g_near_set = 1; g_s2_clk0 = g_c05_clk; s2_setup(cam); }   /* scene 2's clock and frame */
        s2 = g_c05_clk - g_s2_clk0;
        float w[3], v[3], W[9], vl = sqrt_f(S2_V * S2_V);
        s2_way(SHIPS, s2, w, v);                                 /* the Outrider: its way's place and its nose, */
        for (int j = 0; j < 3; j++) g_or_fwd[j] += (v[j] / vl - g_or_fwd[j]) * NOSE_EASE;
        if (!nose_rows(g_or_fwd, W)) for (int j = 0; j < 9; j++) W[j] = r[j];
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++)  /* the node's rows = the scene's rows' transpose x the */
            N[3 * i + j] = r[i] * W[j] + r[3 + i] * W[3 + j] + r[6 + i] * W[6 + j];   /* wanted (the Outrider's world */
        for (int j = 0; j < 3; j++) nn[j] = w[j] - (p[0] * N[j] + p[1] * N[3 + j] + p[2] * N[6 + j]);   /* rows = its x N) */
    }
    if (U32(GALL_RAM + IMG_OR_GLOW)) {                            /* the Outrider as our level draws it, its engine glows */
        g_org_mesh[0] = MESH_W0; g_org_mesh[1] = g_org_mesh[2] = 0;   /* with it (the user, 2026-10-19: the scene's own */
        for (int j = 0; j < 3; j++) g_org_mesh[3 + j] = U32(GALL_RAM + IMG_OR_GLOW + 4 * j);   /* had none): the */
        g_og_list[0] = C05_MESH; g_og_list[1] = (uint32_t)g_org_mesh;   /* the scene's own hull (ours showed orange on the */
        U32(C05_SCALE + NODE_COUNT) = 2; U32(C05_SCALE + NODE_LIST) = (uint32_t)g_og_list;   /* phone) and our glows */
    }
    if (g_c05_ships <= 0) return;
    for (int i = 0; i < g_c05_ships && i < SHIPS; i++) {
        uint32_t *t = g_tnode[i], *s = g_snode[i];
        for (int j = 0; j < TNODE / 4; j++) { t[j] = U32(C05_OR + 4 * j); s[j] = U32(C05_SCALE + 4 * j); }
        float k = (i != FALCON_I ? XW_SCALE : OR_SCALE) * OR_RUN_K;   /* (sized as our level's against the Outrider: the */
        float a[3] = { SHIP_AT[i][0], SHIP_AT[i][1], SHIP_AT[i][2] };   /* scene's is OR_RUN_K */
        if (i != FALCON_I) { a[1] -= XW_DRIFT_V * go; a[2] += XW_DRIFT_UP * go; }   /* (off slowly, steady: the user) */   /* bigger, the user) */
        int ord = i == FALCON_I ? SHIPS - 1 : i;
        float f = g_c05_fn < 0 ? 0 : g_c05_clk;
        float d = (float)FLYIN_D[ord], c = (f - FLYIN_D[ord] - FLYIN_PASS) / FLYIN_CATCH;
        c = c < 0 ? 0 : c > 1 ? 1 : c; c = c * c * (3 - 2 * c); d *= 1 - c;   /* (its place in the formation as it closes up) */
        float h = f - d, at_[3], slow[3];
        if (g_c05_fn < 0 || d < 0.01f || h >= HIST - 1) for (int j = 0; j < 3; j++) at_[j] = p[j];   /* (caught up: on with it; */
        else hist_at(h, p, at_);                                 /* past HIST it stood still and fell behind) */
        hist_at(h * FLYIN_SLOW, p, slow);                        /* (past the camera slower) */
        const float *at = at_;
        float back = g_c05_fn < 0 ? 1000.0f : h >= 0 ? 0 : -h * FLYIN_V;   /* (before it set off: back along its way) */
        for (int j = 0; j < 3; j++) {
            float form = at[j] + a[0] * r[j] + a[1] * r[3 + j] + a[2] * r[6 + j] - back * r[3 + j];
            float pass = FLYIN_LANE[ord][j] * OR_RUN_K + slow[j] - g_c05_hist[0][j] - back * r[3 + j];
            F32((uint32_t)t + NODE_POS + 4 * j) = g_c05_fn < 0 ? form : pass + (form - pass) * c;
        }
        if (near) {                                              /* scene 2: its way (world), in the near node's frame */
            float w[3], v[3], m[9], d[3], vl, *f = g_ship_fwd[i];
            s2_way(i, s2, w, v);
            vl = sqrt_f(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
            for (int j = 0; j < 3; j++) {                        /* (its nose on its way before it is drawn) */
                f[j] = s2 < S2_AT[i] ? v[j] / vl : f[j] + (v[j] / vl - f[j]) * NOSE_EASE;
                g_ship_last[i][j] = w[j]; d[j] = w[j] - nn[j];
            }
            for (int j = 0; j < 3; j++) F32((uint32_t)t + NODE_POS + 4 * j) = N[3 * j] * d[0] + N[3 * j + 1] * d[1] + N[3 * j + 2] * d[2];
            if (nose_rows(f, m))
                for (int q = 0; q < 3; q++) for (int j = 0; j < 3; j++)
                    F32((uint32_t)t + NODE_ROT + 12 * q + 4 * j) = m[3 * q] * N[3 * j] + m[3 * q + 1] * N[3 * j + 1] + m[3 * q + 2] * N[3 * j + 2];
        } else
        {                                                        /* nose along its way (the user: they flew sideways */
            float *q = g_ship_last[i], *f = g_ship_fwd[i], v[3], l = 0;   /* with the Outrider's turn): its step, */
            for (int j = 0; j < 3; j++) { v[j] = F32((uint32_t)t + NODE_POS + 4 * j) + nn[j] - q[j]; l += v[j] * v[j]; q[j] += v[j]; }   /* (world steps) */
            if (g_c05_fn >= 0 && l > 0.01f && l < 400.0f) {      /* smoothed (not a jump: the scene's start) */
                for (int j = 0; j < 3; j++) f[j] += (v[j] / sqrt_f(l) - f[j]) * NOSE_EASE;
            }
            float m[9];                                          /* (rows: its x, y (nose), z in the scene) */
            if (nose_rows(f, m)) for (int j = 0; j < 9; j++) F32((uint32_t)t + NODE_ROT + 4 * j) = m[j];
        }
        for (int j = 0; j < 9; j++) F32((uint32_t)s + NODE_ROT + 4 * j) = j % 4 ? 0 : k;
        g_mesh_list[i][0] = i != FALCON_I ? (uint32_t)g_xw_mesh : (uint32_t)g_fa_mesh;
        t[NODE_COUNT / 4] = !near || s2 >= S2_AT[i]; g_scale_list[i][0] = (uint32_t)s; t[NODE_LIST / 4] = (uint32_t)g_scale_list[i];
        s[NODE_COUNT / 4] = 1; s[NODE_LIST / 4] = (uint32_t)g_mesh_list[i];
        if (i == FALCON_I && U32(GALL_RAM + IMG_GLOW_BENT)) {   /* its engine glow round the stern, as in the run */
            for (int j = 0; j < TNODE / 4; j++) g_fg_node[j] = U32(C05_OR + 4 * j);
            float w[3] = { FGLOW_K * FGLOW_WIDE, FGLOW_K, FGLOW_K };
            for (int j = 0; j < 9; j++) F32((uint32_t)g_fg_node + NODE_ROT + 4 * j) = j % 4 ? 0 : w[j / 4];
            F32((uint32_t)g_fg_node + NODE_POS) = 0; F32((uint32_t)g_fg_node + NODE_POS + 4) = FGLOW_Y; F32((uint32_t)g_fg_node + NODE_POS + 8) = FGLOW_Z;
            g_fg_mesh[0] = MESH_W0; g_fg_mesh[1] = g_fg_mesh[2] = 0;
            for (int j = 0; j < 3; j++) g_fg_mesh[3 + j] = U32(GALL_RAM + IMG_GLOW_BENT + 4 * j);
            g_fg_list[0] = (uint32_t)g_fg_mesh;
            g_fg_node[NODE_COUNT / 4] = 1; g_fg_node[NODE_LIST / 4] = (uint32_t)g_fg_list; g_fg_node[NODE_SLOT / 4] = GLOW_SLOT;
            U16((uint32_t)g_fg_node + NODE_SHOW) = (U16(C05_OR + NODE_SHOW) & 0xFF00) | 3;
            g_fa_list[0] = g_mesh_list[i][0]; g_fa_list[1] = (uint32_t)g_fg_node;
            s[NODE_COUNT / 4] = 2; s[NODE_LIST / 4] = (uint32_t)g_fa_list;
        }
        if (g_c05_dbg[0] & 2) g_mesh_list[i][0] = C05_MESH;
        if (g_c05_dbg[0] & 1) { t[NODE_SLOT / 4] = SHIP_SLOT + i; s[NODE_SLOT / 4] = SHIP_SLOT + SHIPS + i; }
        U16((uint32_t)t + NODE_SHOW) = (U16(C05_OR + NODE_SHOW) & 0xFF00) | 3;   /* (shown as the Outrider; rows changed) */
        U16((uint32_t)s + NODE_SHOW) = (U16(C05_SCALE + NODE_SHOW) & 0xFF00) | 3;
        g_root_list[1 + i] = (uint32_t)t;
    }
    int nr = 1 + (g_c05_ships < SHIPS ? g_c05_ships : SHIPS);
    if (near) {                                                  /* the space shot: the 3D brought to the camera */
        uint32_t n = (uint32_t)g_near_node;
        for (int j = 0; j < TNODE / 4; j++) g_near_node[j] = U32(C05_OR + 4 * j);
        for (int j = 0; j < 9; j++) F32(n + NODE_ROT + 4 * j) = N[j];
        for (int j = 0; j < 3; j++) F32(n + NODE_POS + 4 * j) = nn[j];
        int or_on = s2 >= S2_AT[SHIPS];                          /* (the Outrider not drawn before its start) */
        g_near_node[NODE_COUNT / 4] = nr - !or_on; g_near_node[NODE_LIST / 4] = (uint32_t)(g_root_list + !or_on);
        g_near_node[NODE_SLOT / 4] = NEAR_SLOT;
        U16(n + NODE_SHOW) = (U16(C05_OR + NODE_SHOW) & 0xFF00) | 3;
        g_near_list[0] = n;
        U32(C05_ROOT + NODE_COUNT) = 1; U32(C05_ROOT + NODE_LIST) = (uint32_t)g_near_list;
        return;
    }
    U32(C05_ROOT + NODE_COUNT) = nr; U32(C05_ROOT + NODE_LIST) = (uint32_t)g_root_list;
}

#define MSG_SECONDS      0x800D07FC /* float: the held line's seconds left (gallrun.c) */
/* The scene slowed (the user, 2026-10-19: the flight and space shots longer, the ships
 * slower): its classes (Dspt, Anim, Bmap) move by the game's frame time FRAME_DT, which the game sets at a
 * frame's start (0x800B8CF0) and cut05() runs at its end: our think in their records scales it once a frame (the first
 * of them to run), then the game's; put back off Cut 05. */
#define CLASS_THINK      0x18
#define C05_FLY_SPEED    1.0f       /* frame 3 (the user: the original speed), */
#define C05_SPACE_SPEED  0.65f      /* frame 5: scene 2's ~280 scene frames in ~14 s */
#define C05_JUMP_SPEED   10.0f      /* frame 4 after its hold let go, behind Luke's picture: the scene run on to its
                                     * own Luke hold, then frame 5 */
#define ARC_SPRITE       3          /* Cut 05's green planet arc: its slot in the level's sprite table on a copy of its
                                     * own header with a black palette in frame 5, the scene's put back off it */
#define SPR_HDR          0x28       /* a sprite header's bytes (harness/gallrun/still.py) */
#define SPR_PAL          0x18       /* its palette pointer */
#define C05_LUKE_AT      720.0f     /* scene frames (g_c05_clk) into the flight frame 3 ends (1.5 x 480, the
                                     * scene's Luke hold (~600) let go unseen inside it; 480, was 300: half the
                                     * stock flight at its own speed:
                                     * the backdrop's pan stops at ~480, both the arc and Gall on screen; was 400,
                                     * 300: half the stock way from the
                                     * Outrider's start to the Luke hold (605: c05_state.py 1419 -> 2629 at two video
                                     * frames a scene frame; FRAME_DT is 1/60 there at 30 frames a second) */
static const uint32_t C05_RECS[3] = { 0x80112868, 0x80112898, BMAP_REC };   /* Dspt, Anim, Bmap */
static uint32_t g_c05_think[3];     /* the game's */
static uint32_t g_c05_stamp;
static void c05_scale(int k, uint32_t obj) {
    if (g_c05_stamp != g_ov_frames + 1) { g_c05_stamp = g_ov_frames + 1; F64(FRAME_DT) = F64(FRAME_DT) * g_c05_speed; g_c05_used = g_c05_speed; }
    ((void (*)(uint32_t))g_c05_think[k])(obj);
}
static void c05_think0(uint32_t o) { c05_scale(0, o); }
static void c05_think1(uint32_t o) { c05_scale(1, o); }
static void c05_think2(uint32_t o) { c05_scale(2, o); }
static void c05_slow(int on) {                                   /* our thinks in (on) or the game's back */
    static void (*const OURS[3])(uint32_t) = { c05_think0, c05_think1, c05_think2 };
    for (int k = 0; k < 3; k++) {
        uint32_t a = C05_RECS[k] + CLASS_THINK, m = U32(a);
        if (!g_c05_think[k] && m && m != (uint32_t)OURS[k]) g_c05_think[k] = m;
        if (!g_c05_think[k]) continue;
        if (on && m == g_c05_think[k]) U32(a) = (uint32_t)OURS[k];
        if (!on && m == (uint32_t)OURS[k]) U32(a) = g_c05_think[k];
    }
    if (!on) g_c05_speed = g_c05_used = 1;
}
#define HOLD_FREEZE      5          /* MSG_HOLD: the scene frozen, no button (the game draws it only at 10: 0x80024600) */
#define HOLD_BUTTON      10         /* the scene frozen, the button */
#define ARROW_T          0x800DD2CC /* float: a held line's seconds left (the game: 0x80007A04; the arrow's alpha this / 5) */
#define ARROW_S          12.0f      /* (the scene's own, 0x8003D050) */
#define BMAP_FLAGS       8          /* class Bmap: +8 flags (0x20 not drawn) */
#define BMAP_SPRITE      0xA        /* its sprite */
#define STARS            0          /* Cut 05's starfield (sprite 0): the backdrop, kept */
#define LINE_EL          5          /* Cut 05's line text elements 5..7 (texts: C05_TABLE), shown at */
#define LINE_X           25
#define LINE_Y           161
#define MSG_START_F      2          /* frame 1: the scene at its first hold this many frames in (gall_c05.h C05_HOLD1) */
#define DASH_X0          (-150)     /* the scene's Dash-and-Leebo still where the scene shows it (it does not pan) */
#define DASH_STILL       1          /* its sprite in the level's table */
#define PAD_A_HELD       0x801130AB /* the pad bytes the game's held line reads: 1 while held */
#define PAD_B_HELD       0x801130AA
#define PAD_Z_HELD       0x801130A9
#define U8(a)            (*(volatile uint8_t *)(a))
int g_c05_seq = 1;                   /* (probes: 0 leaves Cut 05 the game's own, harness/gallrun/c05_state.py) */
static int g_c05_go;                /* A let the frame up go (g_c05_t: frames in it) */
static int g_c05_held;              /* the frame's hold the game's (its arrow, A/B/Z or its timer): D1 */
static uint32_t g_dash_still, g_c05_hid;   /* (the scene's pictures we hid, a bit each) */
static uint32_t g_arc_spr;          /* the scene's arc sprite while ours (g_arc_hdr) is in its slot (D18) */
static uint32_t g_arc_hdr[SPR_HDR / 4] __attribute__((section(".data.arc_hdr")));   /* (.gall) */
static uint16_t g_clear_pal[256] __attribute__((section(".data.clear_pal")));      /* 256 RGBA5551, alpha 0 */
static uint16_t g_black_pal[256] __attribute__((section(".data.black_pal"))) = { [0 ... 255] = 0x0001 };   /* opaque
                                     * black: the arc's copy in frame 5 covers the strip the last picture left (D8) */
static uint32_t g_pic_hdr[SPR_HDR / 4] __attribute__((section(".data.pic_hdr")));   /* PIC_SLOT's in the shots: the last
                                     * picture's header, clear palette (its top rows showed) */
#define LINE_LEAD        591        /* a picture's line shown this many frames, the scene frozen without the arrow, before
                                     * the game's hold (the stock scene's median gap) */
static int g_c05_lead;              /* frames of it (0: A, B or Z still held from the last frame) */
static void pool_put(uint32_t pool, const uint32_t *w, int n) {  /* (only over the same class's pool: its tag first) */
    if (U32(pool) != w[0]) return;
    for (int i = 0; i < n; i++) U32(pool + 4 * i) = w[i];
}
/* Leebo turns his head in frame 6: the intro's overlays over the same still
 * (sprite 11 there, pixel-equal to Cut 05's sprite 1), at its times. The patch (sprite 15, over the still's own head) in
 * LEEBO_PATCH_SLOT the whole frame, the head (16..23) in LEEBO_SLOT, drawn after it; the last phase stays. Our counter: Cut 05
 * has no Bmap object to drive them (the intro's own live in its objects: D4). */
#define LEEBO_PATCH_SLOT 8          /* Cut 05's table: 8..79 free, drawn over PIC_SLOT in id order (D6) */
#define LEEBO_SLOT       9
#define LEEBO_N          9          /* sprites in the image (IMG_LEEBO): the patch, then the head's eight phases */
static const struct { uint8_t f, dx; } LEEBO_SEQ[] = {   /* {game frames from frame 6's first, dx}: phase i = sprite 16 + i */
    { 0, 200 }, { 40, 203 }, { 44, 207 }, { 48, 207 }, { 52, 207 }, { 56, 207 }, { 60, 206 }, { 64, 205 },
};
#define LEEBO_PATCH_DX   183
#define LEEBO_PATCH_DY   5
#define LEEBO_DY         13
static int g_leebo_t, g_leebo_on;   /* game frames in frame 6; our sprites in the slots */
static uint32_t g_leebo_own[2];     /* the slots' own pointers while ours are in them */

static void leebo_turn(uint32_t tb, int on) {
    static const uint8_t slot[2] = { LEEBO_PATCH_SLOT, LEEBO_SLOT };
    if (!valid_ptr(tb)) return;
    if (on && U32(GALL_RAM + IMG_LEEBO + 4 * (LEEBO_N - 1))) {
        int ph = 0;
        for (int i = 0; i < (int)(sizeof LEEBO_SEQ / sizeof LEEBO_SEQ[0]); i++) if (g_leebo_t >= LEEBO_SEQ[i].f) ph = i;
        if (!g_leebo_on) { g_leebo_own[0] = U32(tb + 4 * LEEBO_PATCH_SLOT); g_leebo_own[1] = U32(tb + 4 * LEEBO_SLOT); g_leebo_on = 1; }
        U32(tb + 4 * LEEBO_PATCH_SLOT) = U32(GALL_RAM + IMG_LEEBO);
        U32(tb + 4 * LEEBO_SLOT) = U32(GALL_RAM + IMG_LEEBO + 4 * (1 + ph));
        ((void (*)(int, int, int))SPRITE_SHOW)(LEEBO_PATCH_SLOT, DASH_X0 + LEEBO_PATCH_DX, STILL_Y + LEEBO_PATCH_DY);
        ((void (*)(int, int, int))SPRITE_SHOW)(LEEBO_SLOT, DASH_X0 + LEEBO_SEQ[ph].dx, STILL_Y + LEEBO_DY);
        g_leebo_t++;
    } else if (g_leebo_on) {                                     /* (off: as PIC_SLOT's, each slot its own pointer back) */
        for (int i = 0; i < 2; i++) { ((void (*)(int, int, int))SPRITE_SHOW)(slot[i], -1000, 0); U32(tb + 4 * slot[i]) = g_leebo_own[i]; }
        g_leebo_on = 0;
    }
}

static void cut05(void) {
    if (!g_c05_seq) return;
    if (!g_c05_ours && U32(C05_TABLE) != C05_STOCK) return;       /* (the stock scene, once seen: ours) */
    g_c05_ours = 1;
    c05_slow(1);
    if (!g_c05_frame) { g_c05_frame = 1; g_c05_t = 0; g_c05_held = g_c05_lead = g_leebo_t = 0; }
    if (g_c05_frame > C05_FRAMES) {                               /* done: on to the run */
        if (++g_c05_tail >= C05_TAIL) gallrun_start();
        return;
    }
    const c05_frame *f = &FRAMES[g_c05_frame - 1];
    if (S16(MSG_HOLD) && g_c05_t > 2 && ((g_c05_frame == 3 && !g_c05_luke)   /* the scene's Luke hold inside frame 3 */
        || (g_c05_frame == 5 && !(g_near_set && g_c05_clk - g_s2_clk0 >= S2_END)))) {   /* every hold in */
        S16(MSG_HOLD) = 0; F32(MSG_SECONDS) = 0; g_c05_luke = 1;  /* frame 5 before S2_END (D7): let go unseen */
    }
    if (g_c05_go || (f->shot && g_c05_t > 2 && S16(MSG_HOLD) && g_c05_luke)
        || (g_c05_frame == 3 && g_c05_fn >= 0 && g_c05_clk >= C05_LUKE_AT)) {   /* the next frame (a shot: the scene's own, till it */
        if (g_c05_frame == 3) g_c05_luke = 1;                    /* (frame 3 ends: the Luke hold is no more) */
        g_c05_go = 0; g_c05_frame++; g_c05_t = 0; g_c05_held = g_c05_lead = g_leebo_t = 0;   /* holds its next line: the original as it is, the user) */
        if (g_c05_frame > C05_FRAMES) { S16(MSG_HOLD) = 0; F32(MSG_SECONDS) = 0; return; }
        f = &FRAMES[g_c05_frame - 1];
        if (f->shot) { S16(MSG_HOLD) = 0; F32(MSG_SECONDS) = 0; }   /* (let go: on from its hold) */
    }
    for (int k = 0; k < 3; k++) {                                /* the line: the scene's text elements 5..7 (their texts */
        U32(C05_TABLE + 4 * k) = (uint32_t)(f->shot && k ? "" : f->text);   /* the table), the first shown where the scene shows */
        S16(HUD_POS + 4 * (LINE_EL + k)) = k ? -1000 : LINE_X;  /* them, the others off (the scene places one only */
        S16(HUD_POS + 4 * (LINE_EL + k) + 2) = LINE_Y;           /* at its line's time: none in frames 1, 2); in a shot the off ones
                                                                    empty: the game raises no hold for them */
    }
    uint32_t tb = U32(SPRITES), nb = U32(BMAP_REC + 8), bb = U32(BMAP_REC + 0x10), sz = U32(BMAP_REC + 0xC);
    if (valid_ptr(tb) && !g_dash_still) g_dash_still = U32(tb + 4 * DASH_STILL);
    if (f->pic) {                                                /* held as the game holds a line (D1); the scene's */
        if (g_c05_frame == 1 && g_c05_t == MSG_START_F) {        /* the scene at its first hold, its line up (~19 s in */
            pool_put(C05_HOLD1_POOL0, C05_HOLD1_WORDS0, sizeof C05_HOLD1_WORDS0 / 4);   /* otherwise) */
            pool_put(C05_HOLD1_POOL1, C05_HOLD1_WORDS1, sizeof C05_HOLD1_WORDS1 / 4);
            pool_put(C05_HOLD1_POOL2, C05_HOLD1_WORDS2, sizeof C05_HOLD1_WORDS2 / 4);
        }
        if (g_c05_frame > 1 || g_c05_t > MSG_START_F) {          /* pictures hidden (ours over them) but the stars */
            if (!g_c05_held) {                                   /* the game's hold once A, B and Z are up and the */
                int down = U8(PAD_A_HELD) | U8(PAD_B_HELD) | U8(PAD_Z_HELD);   /* lead shown (D6): its arrow, A/B/Z or its */
                if (g_c05_lead || !down) g_c05_lead++;
                if (down || g_c05_lead <= LINE_LEAD) S16(MSG_HOLD) = HOLD_FREEZE;
                else { S16(MSG_HOLD) = HOLD_BUTTON; F32(ARROW_T) = ARROW_S; g_c05_held = 1; }   /* timer let it go */
            } else if (g_c05_held == 2 && S16(MSG_HOLD)) {       /* Luke's: the scene run on behind it to its own */
                S16(MSG_HOLD) = 0; F32(MSG_SECONDS) = 0;         /* Luke hold, let go unseen; frame 5 on the near */
                g_c05_luke = 1; g_c05_go = 1;                    /* shot */
            } else if (!S16(MSG_HOLD)) {
                if (g_c05_frame != 4 || g_c05_luke) g_c05_go = 1;   /* (frame 4: the Luke hold behind, no run-on) */
                else g_c05_held = 2;                             /* (ours let go: the run-on) */
            }
        }
        if (valid_ptr(bb) && nb < 32)
            for (uint32_t i = 0; i < nb; i++) {                    /* (the pictures, sprites 1..: not the stars, nor the */
                int id = S16(bb + i * sz + BMAP_SPRITE);             /* line's text and its box: ids below 0) */
                if (id > STARS && !(U16(bb + i * sz + BMAP_FLAGS) & 0x20)) { U16(bb + i * sz + BMAP_FLAGS) |= 0x20; g_c05_hid |= 1u << i; }
            }
    } else if (g_c05_hid && valid_ptr(bb) && nb < 32) {           /* a shot: the scene's pictures back as they were */
        for (uint32_t i = 0; i < nb; i++)                        /* (its planet, its moon: D14) */
            if (g_c05_hid & (1u << i)) { U16(bb + i * sz + BMAP_FLAGS) &= ~0x20; g_c05_hid &= ~(1u << i); }
    }
    if (valid_ptr(tb)) {                                         /* the arc: in frame 5 a copy of its own header with */
        uint32_t a = tb + 4 * ARC_SPRITE, mine = (uint32_t)g_arc_hdr;   /* a black palette in its slot (its size, tiles */
        if (g_c05_frame == 5) {                                  /* and place: black behind the 3D, D8), the scene's back off */
            uint32_t s = U32(a);                                 /* it (D18) */
            if (s != mine && valid_ptr(s)) {
                g_arc_spr = s;
                for (int j = 0; j < SPR_HDR / 4; j++) g_arc_hdr[j] = U32(s + 4 * j);
                g_arc_hdr[SPR_PAL / 4] = (uint32_t)g_black_pal;
                U32(a) = mine;
            }
        } else if (g_arc_spr) { U32(a) = g_arc_spr; g_arc_spr = 0; }
    }
    if (g_c05_frame == 5 && g_c05_t == 0) {                      /* frame 5: the scene run on from its clock 480 (its */
        pool_put(C05_S2_POOL0, C05_S2_WORDS0, sizeof C05_S2_WORDS0 / 4);   /* objects as c05_state.py read them there; */
        pool_put(C05_S2_POOL1, C05_S2_WORDS1, sizeof C05_S2_WORDS1 / 4);   /* scene 2's frame taken on the next: */
        pool_put(C05_S2_POOL2, C05_S2_WORDS2, sizeof C05_S2_WORDS2 / 4);   /* the scene run on from clock 480) */
    }
    if (g_c05_frame >= 5 && g_c05_luke && !S16(MSG_HOLD) && g_xw_leave < XW_LEAVE_F) g_xw_leave += g_c05_used;   /* (the X-Wings off from the Luke hold let go: in the space shot) */
    cut05_ships();
    if (g_c05_frame == 5 && g_c05_t == 0) { g_c05_clk = 480.0f; U32(C05_ROOT + NODE_COUNT) = 0; }   /* (its clock at the
                                     * write-back; no 3D drawn the frame the scene's camera is still the old one: D7) */
    if (g_c05_frame == 5 && g_near_set && g_c05_clk - g_s2_clk0 >= S2_END) g_c05_go = 1;   /* (frame 5's end: D7) */
    if (f->pic && g_c05_frame > 3) U32(C05_ROOT + NODE_COUNT) = 0;   /* (no picture over the 3D: black round it) */
    uint32_t spr = f->pic == PIC_DASH ? g_dash_still : f->pic ? U32(GALL_RAM + IMG_STILLS + 4 * (f->pic - 1)) : 0;
    if (valid_ptr(tb) && valid_ptr(spr)) {
        U32(tb + 4 * PIC_SLOT) = spr;
        ((void (*)(int, int, int))SPRITE_SHOW)(PIC_SLOT, f->pic == PIC_DASH ? DASH_X0 : 0, STILL_Y);   /* (still: the user) */
    } else if (valid_ptr(tb) && U32(tb + 4 * PIC_SLOT)) {        /* (off: the HUD draws it where it was left) */
        uint32_t s = U32(tb + 4 * PIC_SLOT), mine = (uint32_t)g_pic_hdr;
        if (f->shot && s != mine && valid_ptr(s)) {              /* a shot: a copy of its header with a clear palette */
            for (int j = 0; j < SPR_HDR / 4; j++) g_pic_hdr[j] = U32(s + 4 * j);   /* (as the arc's: D7) */
            g_pic_hdr[SPR_PAL / 4] = (uint32_t)g_clear_pal;
            U32(tb + 4 * PIC_SLOT) = mine;
        }
        ((void (*)(int, int, int))SPRITE_SHOW)(PIC_SLOT, -1000, 0);
    }
    leebo_turn(tb, g_c05_frame == 6);                            /* (only frame 6: D5) */
    g_c05_t++;
    g_c05_speed = g_c05_frame == 3 ? C05_FLY_SPEED : g_c05_frame == 5 ? C05_SPACE_SPEED : g_c05_frame == 4 && g_c05_held && !S16(MSG_HOLD) && !g_c05_luke ? C05_JUMP_SPEED : 1;
}

/* From the pad hook: START skips the last scene (ours); in Cut 05 it is the game's skip. */
static int g_skip;                  /* START in the last scene: the skip is ours (chain_frame()) */
static int g_start_kept;            /* START pressed in Cut 05: eaten from the next sub-level on till let go (no 13 -> 14) */
static int g_line_age;              /* frames the held line up has been up (a swap in Cut 05 starts it again) */
#define LINE_MIN_F       45         /* a held line's first frames: A and B kept from the game and from us (the user,
                                     * 2026-10-19: the lines went too fast; the mission's LINE_HOLD_MIN_F) */
#define SKIP_AFTER       15         /* pad reads (two frames each) into the scene before START skips it */
void chain_pad(uint32_t c) {
    static uint16_t last, eat;
    int lvl = S16(LEVEL_ID), fin = lvl == FINAL_CUT && g_chain_fin;
    if (c > 3) { eat = 0; return; }
    uint16_t b = U16(PAD_RAW + c * 6), fresh = b & ~last;
    last = b;
    if (lvl != CUT05 && !fin) {                                  /* (a START we took kept till let go: the next scene */
        if (g_start_kept) { eat |= PAD_START; g_start_kept = 0; }   /* would skip on it too) */
        eat &= b & PAD_START; U16(PAD_RAW + c * 6) &= ~eat; return;
    }
    static int frames, was_lvl;                                   /* (START ours only half a second into the scene: */
    frames = lvl == was_lvl ? frames + 1 : 0; was_lvl = lvl;      /* one held over the load is the game's) */
    if ((fresh & PAD_START) && frames > SKIP_AFTER) {           /* (the game's: on through Cut 06 to 6a) */
        if (fin) { eat |= PAD_START; g_skip = lvl; } else g_start_kept = 1;   /* (Cut 05: the game's skip, 11 -> 13) */
    }
    if (fin) {
        if (!S16(MSG_HOLD) || g_line_age < LINE_MIN_F) eat |= b & (PAD_A | PAD_B);   /* (kept till let go: a fresh press after) */
                                                                  /* (no line held: the game's own skip of the scene) */
        eat &= b; U16(PAD_RAW + c * 6) &= ~eat; return;
    }
    eat &= b;
    U16(PAD_RAW + c * 6) &= ~eat;
}

/* The last scene (31) after the mission (D18): from its hyperspace tunnel (the scene's objects written back as
 * final_state.py read them there: its Tatooine part skipped), the Falcon in the Outrider's place, Leia's three lines
 * and Lando's in the place of Dash's and Leebo's first four; FIN_TAIL frames after the fourth is let
 * go, Cut 06. */
#define FIN_LINES        0x801C3928 /* the hyperspace part's lines (six pointers; the scene's sixth on) */
#define FIN_OR           0x80199AC0 /* the Outrider's node in the tunnel (its list: one mesh) */
#define FIN_SLOT         5          /* our scale node's world-matrix slot (the scene uses 0..4) */
#define FIN_FALCON_LEN   6.5f       /* the Falcon this long in the scene's units (the Outrider FINAL_OR_LEN) */
/* The Outrider's path passes 1.07 off the scene's eye (at 0, 0, 0), inside the Falcon's half length 3.25 (the
 * camera went into its hull for 38 frames): our node put FIN_FALCON_AWAY further along the line from the eye to that path, in the world (it passes under
 * the camera, 3.52 off), written in the Outrider node's frame (its rows: it banks). */
#define FIN_FALCON_AWAY  2.45f
static const float FIN_AWAY_DIR[3] = { -0.355f, 0.0f, -0.935f };
#define FIN_TAIL         30
#define FIN_N            4
#define FIN_ALL          6          /* the scene's line pointers: the fifth and sixth an empty text (no hold, nothing drawn) */
/* The music: our tunnel write-back skips the scene's Dspt that starts it two VIs after the load
 * (0x8005ED8C), so on our first written frame we make the same call: the track by the name "Main" (98), from its own
 * start, as the stock scene's. */
#define MUSIC_BY_NAME    0x80006CB0 /* (const char *name): the level's track; reads the name a word at a time */
static const uint32_t FIN_MUSIC_NAME[2] = { 0x4D61696Eu, 0 };   /* "Main" (word-aligned) */
static const char *const FIN_TEXT[FIN_N] = {
    "~h~7That mercenary scoundrel ditched us~ntwice in one fight...",
    "~h~7...and still went down there alone and~nran Fett to ground. That was supposed~nto be the hard part.",
    "~h~7Maybe he's not as hopeless as he wants~nus to think.",
    "~h~1Between you and me, Leebo runs that~noutfit. Still... they didn't have it~neasy down there.",
};
static int g_fin_t, g_fin_holds, g_fin_tail;
static uint32_t g_fin_node[TNODE / 4], g_fin_list[1], g_fin_mesh[6];

static void fin_put(uint32_t pool, const uint32_t *w, int n) { for (int i = 0; i < n; i++) U32(pool + 4 * i) = w[i]; }

static void final_scene(void) {
    static int anim_put;
    if (U32(FINAL_POOL2) != 0x426D6170u) {                       /* ('Bmap': the scene's pictures made; till then */
        S16(SCREEN_FADE) = S16(SCREEN_FADE + 2) = S16(SCREEN_FADE + 4) = 0; S16(SCREEN_FADE + 6) = 255;   /* black) */
        anim_put = 0;
        return;
    }
    if (g_fin_t++ == 0) {
        S16(SCREEN_FADE + 6) = -1000;
        fin_put(FINAL_POOL0, FINAL_WORDS0, sizeof FINAL_WORDS0 / 4);
        fin_put(FINAL_POOL2, FINAL_WORDS2, sizeof FINAL_WORDS2 / 4);
        ((void (*)(const void *))MUSIC_BY_NAME)(FIN_MUSIC_NAME);     /* (D10) */
    }
    if (!anim_put && U32(FINAL_POOL1) == 0x416E696Du) { anim_put = 1; fin_put(FINAL_POOL1, FINAL_WORDS1, sizeof FINAL_WORDS1 / 4); }
    for (int i = 0; i < FIN_ALL; i++) U32(FIN_LINES + 4 * i) = (uint32_t)(i < FIN_N ? FIN_TEXT[i] : "");
    uint32_t tb = U32(SPRITES), mine = U32(GALL_RAM + IMG_STILLS), none = U32(GALL_RAM + IMG_STILLS + 8), bm = U32(BMAP_REC + 0x10);
    if (valid_ptr(tb) && valid_ptr(bm) && mine && none) {        /* Lando and Leia in the Falcon's cockpit in place of */
        U32(tb + 4 * FIN_STILL) = mine;                          /* Dash's and Leebo's still (D20), both in the frame: */
        for (int i = 1; i <= FIN_FACES; i++) U32(tb + 4 * (FIN_STILL + i)) = none;   /* not panned (the user): its */
        for (uint32_t i = 0, n = U32(BMAP_REC + 8); i < n; i++) {                    /* Bmap's draw off, ours at x 0 */
            uint32_t o = bm + i * U32(BMAP_REC + 0xC);                               /* while the scene shows it */
            if (S16(o + 0xA) != FIN_STILL) continue;
            U16(o + 8) |= 0x20;
            if (S16(o + 0x1A) > -500) ((void (*)(int, int, int))SPRITE_SHOW)(FIN_STILL, 0, S16(o + 0x1C));
            else ((void (*)(int, int, int))SPRITE_SHOW)(FIN_STILL, -1000, 0);
        }
    }
    if (U32(FALCON_PARTS) && valid_ptr(U32(FIN_OR + NODE_LIST))) {
        float k = FIN_FALCON_LEN / FALCON_LEN_IMG;
        for (int j = 0; j < TNODE / 4; j++) g_fin_node[j] = U32(FIN_OR + 4 * j);
        for (int j = 0; j < 9; j++) F32((uint32_t)g_fin_node + NODE_ROT + 4 * j) = j % 4 ? 0 : k;
        for (int j = 0; j < 3; j++) {                            /* (D4: the world offset in its frame, its rows */
            float o = 0;                                         /*  orthonormal: world = local x rows) */
            for (int i = 0; i < 3; i++) o += FIN_AWAY_DIR[i] * FIN_FALCON_AWAY * F32(FIN_OR + NODE_ROT + 12 * j + 4 * i);
            F32((uint32_t)g_fin_node + NODE_POS + 4 * j) = o;
        }
        g_fin_mesh[0] = MESH_W0; g_fin_mesh[1] = g_fin_mesh[2] = 0;
        for (int j = 0; j < 3; j++) g_fin_mesh[3 + j] = U32(FALCON_PARTS + 4 * j);
        g_fin_list[0] = (uint32_t)g_fin_mesh;
        g_fin_node[NODE_COUNT / 4] = 1; g_fin_node[NODE_LIST / 4] = (uint32_t)g_fin_list; g_fin_node[NODE_SLOT / 4] = FIN_SLOT;
        U16((uint32_t)g_fin_node + NODE_SHOW) = 0xFF03;
        U32(U32(FIN_OR + NODE_LIST)) = (uint32_t)g_fin_node;
    }
    static int16_t was;
    int16_t hold = S16(MSG_HOLD);
    if (hold && !was) g_fin_holds++;
    was = hold;
    if (g_fin_holds >= FIN_N && !hold && ++g_fin_tail >= FIN_TAIL) ((void (*)(int))LEVEL_LOAD)(CUT06);
}

/* The mission's end in the chain: the last scene, then Cut 06. */
void chain_finale(void) {
    g_chain_fin = 1;
    g_fin_t = g_fin_holds = g_fin_tail = 0;
    ((void (*)(int))LEVEL_LOAD)(FINAL_CUT);
}

void chain_frame(int lvl) {
    g_line_age = S16(MSG_HOLD) ? g_line_age + 1 : 0;               /* (frames the line up has been held) */
    if (g_skip && g_skip == lvl) {                               /* START: the last scene -> Cut 06 */
        g_skip = 0;
        g_fin_tail = FIN_TAIL; ((void (*)(int))LEVEL_LOAD)(CUT06);
    } else if (g_skip != lvl) g_skip = 0;
    if (lvl == CUT05) cut05();
    else { g_c05_ours = g_c05_tail = g_c05_frame = g_c05_t = g_c05_go = g_c05_held = g_c05_lead = 0; g_c05_hid = 0; g_arc_spr = 0; g_c05_fn = -1; g_dash_still = 0; g_leebo_t = g_leebo_on = 0;
        g_xw_leave = g_c05_clk = 0; g_c05_luke = g_near_set = 0; c05_slow(0);
        g_c05_last[0] = g_c05_last[1] = g_c05_last[2] = 0;
        for (int i = 0; i < SHIPS; i++) for (int j = 0; j < 3; j++) g_ship_fwd[i][j] = j == 1; }
    if (lvl == FINAL_CUT && g_chain_fin && g_fin_tail < FIN_TAIL) final_scene();
    if (lvl == CUT06 && g_prev_lvl == CUT05 && !g_chain_fin) gallrun_start();   /* (Cut 05 skipped by START) */
    if (lvl != LEVEL_GALL && lvl != CUT06 && lvl != FINAL_CUT) g_chain_fin = 0;   /* (on into Gall 6a, or left) */
    g_prev_lvl = lvl;
}
