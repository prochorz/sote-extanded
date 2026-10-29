/* Gall Run (gallrun.c): stage 1 flight (fly()): the player's Falcon along the route, against the rock. */
#include "common.h"
#include "gall.h"

#define IMG_CORRIDOR     72         /* per node s16 left, right, down, up (world units; stage 2: left, right) */
#define IMG_EDGE         272        /* per route node a byte: 1 where a flat ship does not fit (collide.edge_nodes()) */
/* Stage 1 flight (fly()) */
#define FLY_ASSIST       0.0f       /* per second, the heading eased along the canyon's (0.6 felt on rails: the user, 2026-10-14) */
#define FLY_TURN         1.6f       /* rad/s at full stick (the source level's vehicle turns ~50 deg/s = 0.87: with the Falcon held at cruise a look-ahead bot lost 243 health in the first third of stage 1 at 0.87, 220 at 1.2, 61 at 1.6) */
#define FLY_GLANCE       0.35f      /* rad: into a wall at less than this the ship slides along it (as the source level's vehicle) */
#define FLY_FLOOR        0.6f       /* a surface whose normal's up part is above this is the floor: the ship
                                     * skims it (no damage, no bounce), so flying low does not kill you */
#define FLY_SCRAPE       0.1f       /* a slide's damage and shake, share of a hit's */
#define FLY_STICK        80.0f      /* full stick */
#define FLY_DEAD         8.0f
#define FLY_GUIDE        3.0f       /* per second, onto the line */
#define FLY_HOME         40         /* nodes before the end of control: guided back onto the line */
#define FLY_END          16         /* control ends this many nodes before the switch (the stage 1 camera too) */
#define CUT_FROM         17         /* fly(): a cut to the route this many nodes on (or back) at least (route_near() */
#define CUT_AHEAD        250        /* looks -BACK_LOOK..16), at most this many, */
#define CUT_NEAR         90.0f      /* the ship this near it, at a height it may fly at there (FLY_LOW under the route .. its roof) */
#define BACK_LOOK        16         /* fly(): Chor follows the ship back too (the user: fly back much further): searched this */
#define BACK_MIN         3          /* far back, down to this node (over the lead nodes) */
#define HIT_DAMAGE       6.0f       /* health per hit (was 12: wall to wall in a narrow passage was the end), */
#define HIT_SPEED        0.03f      /* + this per unit/s into the rock */
#define STUCK_T          0.5f       /* seconds hardly moving: wedged in a corner */
#define CRASH_T          2.0f       /* seconds against rock (not the floor) getting nowhere: the ship blows up */
#define CRASH_GO         1.5f       /* (nowhere: less than this many nodes' length from where it began) */
#define CONTACT_NEW      0.3f       /* seconds off the rock: the next touch is a new hit */
#define UNSTICK          2.0f       /* per second: head on, the ship eased towards the line and along it */
#define HIT_GAP          0.6f       /* seconds: no new damage this soon after a hit */
/* A wall hit's sound: the rock handler's (0x8002857C) spread, its doubles 0x800E9B20..40:
 * pitch (r * 0.4 + 0.8) * 0.25, volume (r * 0.4 + 0.4) * 32000, r = the game's random in 0..1 */
#define ROCK_PITCH_R     0.4f
#define ROCK_PITCH_0     0.8f
#define ROCK_PITCH_K     0.25f
#define ROCK_VOL_R       0.4f
#define ROCK_VOL_0       0.4f
#define ROCK_VOL_K       32000.0f
#define HIT_SLOW         0.7f       /* head on: the speed left */
#define SCRAPE_SLOW      0.6f       /* sliding: speed lost a second */
#define BANK_SPAN        3          /* bank: the route's turn over this many nodes ahead */
#define BANK_GAIN        1.0f       /* radians per unit of turn (sine of the heading change) */
#define KNIFE_W          12.0f      /* a slit (corridor left + right below this, stage1_route.py): on edge */
#define KNIFE_AHEAD      6          /* nodes before the slit it starts to turn */
float g_fly_pitch;                  /* nose down (radians) */
float g_fly_thr = 1;                /* speed, share of cruise */
float g_fly_p;                      /* Chor's place last frame (nodes) */
float g_fly_speed;                  /* Chor's speed set last frame */
float g_hit_t;                      /* seconds since the last hit */
float g_shake;                      /* camera shake (units) */
int g_fly_on;
float g_fly_turn = FLY_TURN;        /* (a global: the harness tries rates) */
float g_cruise;                     /* fly(): the Falcon's cruise speed (route nodes a frame) */

/* Stage 1: the Outrider flies ahead of the Falcon (Dash shows Lando the way). It is drawn by the
 * first rock's node: the rock gets a decoy copy to pose and hide, the real node holds the
 * Outrider's own meshes, hull and engine glows (OR_MESHES: in our level the player ship's model is
 * the Falcon, gallrun/level_edit.py, and these meshes are left out of it), and is put along the
 * route, facing along it, at the player ship's scale. In stage 2 it is gone. */

void route_pos(uint32_t k, float *p) {
    uint32_t a = U32(GALL_RAM + 20) + k * ROUTE_STRIDE + ROUTE_NODES;
    for (int i = 0; i < 3; i++) p[i] = F32(a + 4 * i);
}

/* Bank into the turn of the route at node k: right wing down (positive) in a right turn; on edge
 * (KNIFE) where the passage just ahead is narrower than KNIFE_W, to the side it turns to (or the
 * ship already leans to: cur), and on that side through the whole slit. */
float bank(uint32_t k, float cur) {
    float a[3], b[3], c[3];
    route_pos(k, a); route_pos(k + BANK_SPAN, b); route_pos(k + 2 * BANK_SPAN, c);
    float x0 = b[0] - a[0], y0 = b[1] - a[1], x1 = c[0] - b[0], y1 = c[1] - b[1];
    float l = sqrt_f((x0 * x0 + y0 * y0) * (x1 * x1 + y1 * y1));
    float r = l > 1e-3f ? -(x0 * y1 - y0 * x1) / l * BANK_GAIN : 0;
    for (uint32_t i = 0; i <= KNIFE_AHEAD; i++)       /* from KNIFE_AHEAD before to one node after */
        if (corridor(k - 1 + i, 0) + corridor(k - 1 + i, 1) < KNIFE_W)   /* keeps the side once on edge */
            return (absf(cur) > BANK_MAX || absf(r) < 0.05f ? cur : r) < 0 ? -KNIFE : KNIFE;
    return r > BANK_MAX ? BANK_MAX : r < -BANK_MAX ? -BANK_MAX : r;
}

float corridor(uint32_t k, int i) {
    return (float)S16(U32(GALL_RAM + IMG_CORRIDOR) + k * 8 + 2 * i);
}

/* Stage 1: the player flies the Falcon freely through the canyon (like the snowspeeder on Hoth), against
 * the canyon's own rock: stage 1's triangles as the image draws them, in world units, with the normal of
 * their drawn side (gallrun/collide.py, IMG_COLL: a grid of cells listing them). The ship is an ellipsoid
 * (FLY_R: half length, width, height; banked with it, so on edge it fits a slit) that only meets the drawn
 * side of a triangle (what the player sees is what is solid: a rock top that closes a groove when seen from
 * above, invisible from inside, is no ceiling inside). Stick x turns, stick up dives / down climbs, A held
 * speeds up (to FLY_BOOST), no A slows right down (to FLY_MIN), Z held: on edge. Met head on (more than FLY_GLANCE) a wall is a hit: health (the HUD's), the heading
 * thrown off it, the speed cut; glanced, the ship slides along it with a scrape. Chor (the camera's,
 * Dash's, the lines', the TIEs' and the stage switch's place on the route) follows the ship's nearest place
 * on the route; the ship is drawn there off Chor (g_ship_off). Before the end of control (FLY_HOME) it is
 * eased onto the route. */
#define IMG_ROOF         112        /* stage 1's ceiling per route node (s16, over the route: collide.ceilings()) */
#define COLL_TRI         24         /* a triangle: 9 s16 vertex coordinates, 3 s16 normal x 32767 */
#define FLY_R_LEN        18.0f      /* the ship's ellipsoid: half length, */
#define FLY_R_W          15.0f      /* half width, */
#define FLY_R_H          5.0f       /* half height */
#define FLY_TOP          165.0f     /* at most this far over the route; per node lower (IMG_ROOF: under the walls round it,
                                     * so the camera cannot see over them; over the slits' walls still) */
#define FLY_LEASH        600.0f     /* and this far off it sideways (260 felt on rails, the user) */
#define FLY_YAW_MAX      3.2f       /* rad: off the route's heading at most (> PI: none; the user: turn round. Back, the route's point (Chor) waits, the ship held FLY_LEASH round it) */
#define SLIT_LOOK        20         /* nodes: a slit this near ahead (or under the ship) */
#define SLIT_CATCH       200.0f     /* the ship this near the slit's line, on edge by Z, */
#define SLIT_PULL        8.0f       /* is drawn onto it across (its height kept), this share a second (and turned along it) */
#define TURN_BACK_W      2.5f       /* rad/s: flown back to where it cannot go on, the ship turns itself round (g_turn_back) */
#define TURN_SLOW        0.2f       /* at this speed share (a circle of ~25, the gully behind the start is ~200 wide);
                                     * a touch of the rock meanwhile is harmless (rock(), held 2) */
#define TURN_BACK_WIDE   0.35f      /* rad: nearer than this to 180 deg off the route's heading it turns to the canyon's wider side */
#define TURN_BACK_DONE   0.95f      /* the turn ends once the heading's cosine with the route's is above this */

float stick(int i) {
    float v = (float)g_stick[i];
    v = v > FLY_DEAD ? v - FLY_DEAD : v < -FLY_DEAD ? v + FLY_DEAD : 0;
    v /= FLY_STICK - FLY_DEAD;
    return v > 1 ? 1 : v < -1 ? -1 : v;
}

/* The route's heading at place f (nodes), from the node pairs round it. */
float route_head(float f) {
    uint32_t k = (uint32_t)f;
    float a[3], b[3], c[3], fr = f - (float)k;
    route_pos(k > 0 ? k - 1 : 0, a); route_pos(k + 1, b); route_pos(k + 2, c);
    float x = (b[0] - a[0]) * (1 - fr), y = (b[1] - a[1]) * (1 - fr);
    route_pos(k, a);
    x += (c[0] - a[0]) * fr; y += (c[1] - a[1]) * fr;
    return atan2_r(y, x);
}

/* Stage 1: only the rock hurts (the user: no fire before stage 2). A bomb of the level's own came now and then,
 * 120 a hit with "Incoming Bomb!" (the player ship's TBmb message, sent by the bombers' launch 0x8009E4A4; now held
 * by tie_update(), our own bomb in the end's fight: bombers()): any loss not hit()'s
 * (which keeps g_hp_kept) is put back, the warning cleared. A rise (the game's respawn) is kept. Every frame of
 * stage 1, before fly(). */

/* After stage 1 a laser takes LASER_TAKE of what it did (the user: the TIEs far too fierce): any loss not
 * hit()'s is partly put back; a rise (the game's respawn) is kept. */
#define LASER_TAKE       0.15f
void hp_guard(int stage1) {
    uint32_t stft = player_ship();
    if (!stft || paused() || (!stage1 && SHOT_SAFE)) return;
    if (g_native && (U32(stft + STFT_STATE) == 5 || U32(stft + STFT_STATE) == 6)) return;   /* (blowing up: health put back) */
    int hp = (int)U32(stft + STFT_HEALTH);
    if (g_hp_kept > 0 && hp < g_hp_kept) {
        int keep = stage1 ? g_hp_kept : g_hp_kept - (int)((float)(g_hp_kept - hp) * LASER_TAKE + 0.99f);
        U32(stft + STFT_HEALTH) = hp = keep > 0 ? keep : 0;
    }
    g_hp_kept = hp;
    if (stage1) F32(BOMB_WARN) = 0;
}

/* A wall: head on (k 1) a hit, sliding along it (k FLY_SCRAPE) a scrape; either with the rock's hit sound
 * (a scrape at half its volume). */
static void hit(float into, float k) {
    uint32_t stft = player_ship();
    if (g_hit_t > HIT_GAP && stft) {
        int hp = (int)U32(stft + STFT_HEALTH) - (int)((HIT_DAMAGE + HIT_SPEED * absf(into)) * k);
        U32(stft + STFT_HEALTH) = hp > 0 ? hp : 0;
        g_hp_kept = hp > 0 ? hp : 0;
        if (k >= 1) g_fly_thr *= HIT_SLOW;
        if (g_shake < HIT_SHAKE * k) g_shake = HIT_SHAKE * k;
        float rp = (float)((rand_fn)GAME_RAND)() / 2147483648.0f, rv = (float)((rand_fn)GAME_RAND)() / 2147483648.0f;
        int vol = (int)((rv * ROCK_VOL_R + ROCK_VOL_0) * ROCK_VOL_K);
        ((sfx_fn)SFX)(SND_ROCK, 4, fbits((rp * ROCK_PITCH_R + ROCK_PITCH_0) * ROCK_PITCH_K), k >= 1 ? vol : vol / 2, 0);
        g_hit_t = 0;
    }
}

/* The point of triangle abc nearest to the origin (Ericson, Real-Time Collision Detection 5.1.5). */
static void nearest(const float *a, const float *b, const float *c, float *q) {
    float ab[3], ac[3], ap[3], bp[3], cp[3];
    for (int i = 0; i < 3; i++) { ab[i] = b[i] - a[i]; ac[i] = c[i] - a[i]; ap[i] = -a[i]; bp[i] = -b[i]; cp[i] = -c[i]; }
    float d1 = dot3(ab, ap), d2 = dot3(ac, ap), d3 = dot3(ab, bp), d4 = dot3(ac, bp), d5 = dot3(ab, cp), d6 = dot3(ac, cp);
    float u = 0, v = 0;
    if (d1 <= 0 && d2 <= 0) { u = 0; v = 0; }
    else if (d3 >= 0 && d4 <= d3) { u = 1; v = 0; }
    else if (d6 >= 0 && d5 <= d6) { u = 0; v = 1; }
    else {
        float vc = d1 * d4 - d3 * d2, vb = d5 * d2 - d1 * d6, va = d3 * d6 - d5 * d4;
        if (vc <= 0 && d1 >= 0 && d3 <= 0) { u = d1 / (d1 - d3); v = 0; }
        else if (vb <= 0 && d2 >= 0 && d6 <= 0) { u = 0; v = d2 / (d2 - d6); }
        else if (va <= 0 && d4 - d3 >= 0 && d5 - d6 >= 0) { float w = (d4 - d3) / ((d4 - d3) + (d5 - d6)); u = 1 - w; v = w; }
        else { float den = 1 / (va + vb + vc); u = vb * den; v = vc * den; }
    }
    for (int i = 0; i < 3; i++) q[i] = a[i] + ab[i] * u + ac[i] * v;
}

/* An ellipsoid at p, half axes r[0..2] along the unit axes ax[0..2], against the drawn side of a collision set's
 * triangles (set: its header offset, IMG_COLL the canyon's, IMG_SD_COLL the Star Destroyer's): p is moved out of
 * them (two passes); returns the deepest push (0: none) and its triangle's normal in n. */
float collide(uint32_t set, float *p, const float ax[3][3], const float *r, float *n) {
    uint32_t c = U32(GALL_RAM + set);
    if (!c) return 0;
    float x0 = F32(c + 8), y0 = F32(c + 12), cell = F32(c + 16), rm = r[0] > r[1] ? r[0] : r[1];
    int nx = (int)U32(c + 20), ny = (int)U32(c + 24);
    uint32_t tris = U32(c + 4), cells = U32(c + 28), list = U32(c + 32);
    if (r[2] > rm) rm = r[2];
    float best = 0;
    for (int pass = 0; pass < 2; pass++) {
        int i0 = (int)((p[0] - rm - x0) / cell), i1 = (int)((p[0] + rm - x0) / cell);
        int j0 = (int)((p[1] - rm - y0) / cell), j1 = (int)((p[1] + rm - y0) / cell);
        if (i0 < 0) i0 = 0;
        if (j0 < 0) j0 = 0;
        if (i1 >= nx) i1 = nx - 1;
        if (j1 >= ny) j1 = ny - 1;
        for (int j = j0; j <= j1; j++)
            for (int i = i0; i <= i1; i++) {
                uint32_t e = U32(cells + 4 * (j * nx + i)), e1 = U32(cells + 4 * (j * nx + i) + 4);
                for (; e < e1; e++) {
                    uint32_t t = tris + COLL_TRI * U16(list + 2 * e);
                    float v[3][3], tn[3], l[3][3], q[3];
                    for (int k = 0; k < 3; k++) {
                        for (int m = 0; m < 3; m++) v[k][m] = (float)(int16_t)U16(t + 6 * k + 2 * m) - p[m];
                        tn[k] = (float)(int16_t)U16(t + 18 + 2 * k) * (1.0f / 32767);
                    }
                    if (dot3(tn, v[0]) > 0) continue;               /* p behind the drawn side */
                    for (int k = 0; k < 3; k++)                      /* into the ellipsoid's unit sphere */
                        for (int m = 0; m < 3; m++) l[k][m] = dot3(v[k], ax[m]) / r[m];
                    nearest(l[0], l[1], l[2], q);
                    float d2 = dot3(q, q);
                    if (d2 >= 1 || d2 < 1e-8f) continue;
                    float d = sqrt_f(d2), k = (1 - d) / d;
                    for (int m = 0; m < 3; m++)                      /* out along -q, back in world units */
                        p[m] -= (q[0] * r[0] * ax[0][m] + q[1] * r[1] * ax[1][m] + q[2] * r[2] * ax[2][m]) * k;
                    if (1 - d > best) { best = 1 - d; n[0] = tn[0]; n[1] = tn[1]; n[2] = tn[2]; }
                }
            }
    }
    return best;
}

/* Segment a -> b against a collision set's triangles (collide()'s grid, its cells by x and y): 1 if it goes into one
 * through its drawn side (a in front of it, b behind or on it, the crossing inside the triangle). Each row of cells
 * the segment's box covers is walked only over the columns the segment spans within that row, each triangle tested
 * once (a triangle is listed in every cell it covers). */
#define SEG_SEEN         8192       /* triangles the once-only marks cover (a set with more: tested per cell) */
static uint32_t g_seg_seen[SEG_SEEN / 32];
int seg_hit(uint32_t set, const float *a, const float *b) {
    uint32_t c = U32(GALL_RAM + set);
    if (!c) return 0;
    float x0 = F32(c + 8), y0 = F32(c + 12), cell = F32(c + 16), d[3] = { b[0] - a[0], b[1] - a[1], b[2] - a[2] };
    int nx = (int)U32(c + 20), ny = (int)U32(c + 24), once = U32(c) <= SEG_SEEN;
    uint32_t tris = U32(c + 4), cells = U32(c + 28), list = U32(c + 32);
    if (once) for (uint32_t k = 0; k < (U32(c) + 31) / 32; k++) g_seg_seen[k] = 0;
    float ya = a[1] < b[1] ? a[1] : b[1], yb = a[1] < b[1] ? b[1] : a[1];
    int j0 = (int)((ya - y0) / cell), j1 = (int)((yb - y0) / cell);
    if (j0 < 0) j0 = 0;
    if (j1 >= ny) j1 = ny - 1;
    for (int j = j0; j <= j1; j++) {
        float u0 = 0, u1 = 1;                                    /* (the segment's share within this row) */
        if (d[1] != 0) {
            float r0 = (y0 + cell * (float)j - a[1]) / d[1], r1 = (y0 + cell * (float)(j + 1) - a[1]) / d[1];
            if (r0 > r1) { float t = r0; r0 = r1; r1 = t; }
            u0 = r0 > 0 ? r0 : 0; u1 = r1 < 1 ? r1 : 1;
        }
        float xa = a[0] + d[0] * u0, xb = a[0] + d[0] * u1;
        if (xa > xb) { float t = xa; xa = xb; xb = t; }
        int i0 = (int)((xa - x0) / cell), i1 = (int)((xb - x0) / cell);
        if (i0 < 0) i0 = 0;
        if (i1 >= nx) i1 = nx - 1;
        for (int i = i0; i <= i1; i++) {
            uint32_t e = U32(cells + 4 * (j * nx + i)), e1 = U32(cells + 4 * (j * nx + i) + 4);
            for (; e < e1; e++) {
                uint32_t ti = U16(list + 2 * e), t = tris + COLL_TRI * ti;
                if (once) {
                    if (g_seg_seen[ti >> 5] & (1u << (ti & 31))) continue;
                    g_seg_seen[ti >> 5] |= 1u << (ti & 31);
                }
                float n[3] = { (float)(int16_t)U16(t + 18), (float)(int16_t)U16(t + 20), (float)(int16_t)U16(t + 22) };
                float w[3] = { a[0] - (float)(int16_t)U16(t), a[1] - (float)(int16_t)U16(t + 2), a[2] - (float)(int16_t)U16(t + 4) };
                float da = dot3(n, w), dd = dot3(n, d);
                if (da <= 0 || dd >= 0 || da + dd > 0) continue;   /* a behind it, or b still in front */
                float s = -da / dd, p[3], v[3][3];
                for (int k = 0; k < 3; k++)
                    for (int m = 0; m < 3; m++) v[k][m] = (float)(int16_t)U16(t + 6 * k + 2 * m);
                for (int m = 0; m < 3; m++) p[m] = a[m] + d[m] * s;
                int pos = 0, neg = 0;                            /* (the crossing on the same side of each edge: */
                for (int k = 0; k < 3; k++) {                    /* either winding) */
                    const float *p0 = v[k], *p1 = v[k == 2 ? 0 : k + 1];
                    float ed[3] = { p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2] }, q[3] = { p[0] - p0[0], p[1] - p0[1], p[2] - p0[2] };
                    float cr[3] = { ed[1] * q[2] - ed[2] * q[1], ed[2] * q[0] - ed[0] * q[2], ed[0] * q[1] - ed[1] * q[0] };
                    float sd = dot3(cr, n);
                    if (sd > 0) pos = 1; else if (sd < 0) neg = 1;
                }
                if (!(pos && neg)) return 1;
            }
        }
    }
    return 0;
}

/* The ellipsoid's axes for a ship heading yaw, banked by roll (right wing down). */
static void ship_axes(float yaw, float pitch, float roll, float ax[3][3]) {
    float cy = cos_r(yaw), sy = sin_r(yaw), cp = cos_r(pitch), sp = sin_r(pitch), cr = cos_r(roll), sr = sin_r(roll);
    float f[3] = { cy * cp, sy * cp, -sp }, r0[3] = { sy, -cy, 0 }, u0[3];
    u0[0] = r0[1] * f[2] - r0[2] * f[1]; u0[1] = r0[2] * f[0] - r0[0] * f[2]; u0[2] = r0[0] * f[1] - r0[1] * f[0];
    for (int i = 0; i < 3; i++) {
        ax[0][i] = f[i];
        ax[1][i] = r0[i] * cr - u0[i] * sr;
        ax[2][i] = u0[i] * cr + r0[i] * sr;
    }
}

/* Chor's place on the route nearest the point p, searched from node k back BACK_LOOK and on 16. */
static float route_near(uint32_t k, const float *p) {
    float best = 1e30f, at = (float)k;
    for (uint32_t j = k > BACK_LOOK ? k - BACK_LOOK : 0; j < k + 16; j++) {
        float a[3], b[3];
        route_pos(j, a); route_pos(j + 1, b);
        float dx = b[0] - a[0], dy = b[1] - a[1], l = dx * dx + dy * dy;
        if (l < 1e-3f) continue;
        float u = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l;
        u = u < 0 ? 0 : u > 1 ? 1 : u;
        float ex = a[0] + dx * u - p[0], ey = a[1] + dy * u - p[1], d = ex * ex + ey * ey;
        if (d < best) { best = d; at = (float)j + u; }
    }
    return at;
}

/* Chor put at place f on the route at once (its node words, param); here: that node, where the ship is drawn. */
static uint32_t chor_put(uint32_t chor, float f, float *here) {
    uint32_t j = (uint32_t)f;
    for (int i = 0; i < 4; i++) U32(chor + CHOR_NODE + 4 * i) = j - 1 + (uint32_t)i;
    F32(chor + CHOR_PARAM) = f - (float)j;
    route_pos(j, here);
    here[2] -= SHIP_DROP;
    return j;
}

/* Stage 1's roof over the route at node k (IMG_ROOF), or FLY_TOP. */
static float roof_at(uint32_t k) {
    return U32(GALL_RAM + IMG_ROOF) ? (float)(int16_t)U16(U32(GALL_RAM + IMG_ROOF) + 2 * k) : FLY_TOP;
}

float g_fly_pos[3], g_fly_yaw;          /* the ship in the world (where it is drawn) and its heading */
static int g_leashed;                   /* fly(): the ship held at FLY_LEASH last frame */
static int g_turn_back;                 /* fly(): turning round by itself (the way: 1 left, -1 right; 0: not) */
static float g_chor_rate;               /* Chor: route nodes a frame per unit of its speed (measured) */

void throttle(float dt) {                                        /* A held: speed up, else slow right down */
    float want = g_btn & PAD_A ? FLY_BOOST : FLY_MIN;            /* (stage 1, the chase) */
    g_fly_thr += (want - g_fly_thr) * minf(FLY_THROTTLE * dt, 1);
}

/* The ship (g_fly_pos, heading dir at speed v) against a collision set (collide()): hits, scrapes, slides along it;
 * beating at one place for CRASH_T it blows up (not while held: the leash keeps it there, not the player); head on (toline) eased towards the route's line (here, head).
 * held 2 (turning round by itself, g_turn_back): only pushed out of the rock, no harm, the heading kept. */
void rock(uint32_t set, float *dir, float v, float dt, const float *here, float head, int toline, int held) {
    float ax[3][3], r[3] = { FLY_R_LEN, FLY_R_W, FLY_R_H }, n[3];
    ship_axes(g_fly_yaw, g_fly_pitch, g_ship_roll, ax);
    static float apart = 1, jam, from[3];                   /* seconds since the ship last touched rock; */
    if (collide(set, g_fly_pos, ax, r, n) <= 0) apart += dt;     /* against it getting nowhere (CRASH_T) */
    else if (held == 2) apart = 0;
    else {
        float dn = dot3(dir, n);
        int fresh = apart > CONTACT_NEW;                     /* a new touch hurts, rubbing along does not */
        apart = 0;
        if (dn < 0) {
            int floor = n[2] > FLY_FLOOR;                    /* the floor: the ship skims it, no damage */
            int head_on = !floor && -dn > sin_r(FLY_GLANCE); /* either way slid along it, never thrown */
            if (fresh && !floor) hit(-dn * v, head_on ? 1 : FLY_SCRAPE);   /* off (wall to wall) */
            if (!floor) {                                    /* beating at one place (a slit missed): */
                if (jam == 0) for (int i = 0; i < 3; i++) from[i] = g_fly_pos[i];   /* blown up (health 0: */
                if (!held) jam += dt;                        /* the game's own life loss, then back) */
                float mx = g_fly_pos[0] - from[0], my = g_fly_pos[1] - from[1], mz = g_fly_pos[2] - from[2];
                if (mx * mx + my * my + mz * mz > CRASH_GO * CRASH_GO * NODE_UNITS * NODE_UNITS) jam = 0;
                else if (jam > CRASH_T) {
                    uint32_t stft = player_ship();
                    if (stft) U32(stft + STFT_HEALTH) = 0;
                    g_hp_kept = 0;
                    jam = 0;
                }
            }
            if (head_on && toline) {                         /* into a corner: eased out towards the line */
                float g = minf(UNSTICK * dt, 1), d = head - g_fly_yaw;
                d = wrap_pi(d);
                g_fly_pos[0] += (here[0] - g_fly_pos[0]) * g; g_fly_pos[1] += (here[1] - g_fly_pos[1]) * g;
                g_fly_yaw += d * g;
            }
            if (!head_on && !floor) g_fly_thr -= g_fly_thr * minf(SCRAPE_SLOW * dt, 1);
            for (int i = 0; i < 3; i++) dir[i] -= n[i] * dn;    /* slide along the surface (the floor: level out) */
            float h = sqrt_f(dir[0] * dir[0] + dir[1] * dir[1]);
            if (h > 1e-3f) g_fly_yaw = atan2_r(dir[1], dir[0]);
            g_fly_pitch = -atan2_r(dir[2], h);
            if (g_fly_pitch > FLY_PITCH) g_fly_pitch = FLY_PITCH;
            if (g_fly_pitch < -FLY_PITCH) g_fly_pitch = -FLY_PITCH;
        }
    }
    if (apart > CONTACT_NEW) jam = 0;                            /* clear of the rock a while: free again */
}

void fly(uint32_t chor, uint32_t node, float t) {
    if (paused()) return;                                     /* paused: everything holds */
    uint32_t sw = U32(GALL_RAM + IMG_SWITCH), k = node + 1;
    float dt = frame_dt(), p = (float)k + t;
    int lead = node >= LEAD_FROM;                                /* the lead nodes before node 0 */
    if (lead) { k = 0; p = t; }
    float step = p - g_fly_p;
    if (step < 0 || step > 4) step = 0;
    if (step > 0 && g_fly_speed > 0.05f * SPEED) {            /* how fast Chor goes for its speed */
        float c = step / g_fly_speed;
        g_chor_rate = g_chor_rate > 0 ? g_chor_rate + (c - g_chor_rate) * 0.2f : c;
    }
    g_cruise = FLY_V * dt / NODE_UNITS;                          /* (Dash's pace) */
    g_fly_p = p;
    g_hit_t += dt;
    g_shake -= g_shake * minf(HIT_SHAKE_EASE * dt, 1);
    if (g_intro || lead || node + FLY_END >= sw || g_chor_rate <= 0) {   /* not flown: on the route */
        g_fly_on = 0; g_knife = 0; g_turn_back = 0; g_ship_head_on = 0;
        g_fly_speed = g_intro ? 0 : SPEED;
        if (!g_intro) {
            g_fly_thr = 1;
            g_ship_off[0] = g_ship_off[1] = g_ship_off[2] = 0;
            g_ship_yaw = g_ship_pitch = 0;
            F32(chor + CHOR_SPEED) = SPEED;
        }
        return;
    }
    {                                                            /* the game brought the ship back after it */
        static int last;                                         /* blew up (health refilled): on the route */
        uint32_t stft = player_ship();
        int hp = stft ? (int)U32(stft + STFT_HEALTH) : 0;
        if (hp > last + RESPAWN_HP) { g_fly_on = 0; g_ship_off[0] = g_ship_off[1] = g_ship_off[2] = 0; }
        last = hp;
    }
    float head = route_head(p), here[3];
    for (int i = 0; i < 3; i++) here[i] = F32(chor + 0x50 + 4 * i);
    here[2] -= SHIP_DROP;                                        /* where the ship is drawn on the route */
    if (!g_fly_on) {
        g_fly_on = 1; g_fly_thr = 1; g_fly_pitch = 0; g_fly_yaw = head; g_turn_back = 0;
        for (int i = 0; i < 3; i++) g_fly_pos[i] = here[i] + g_ship_off[i];
    }
    float sx = stick(0), sy = stick(1);
    {   /* Flown back (facing down the canyon) to where it cannot go on (held by the leash, or Chor at BACK_MIN + 1 or
         * less: the invisible wall), the ship turns itself round to the route's heading, the stick's turn ignored (the
         * user: it stopped in mid-air), the shorter way (about 180 deg off: to the canyon's wider side), flying on. */
        float d = wrap_pi(head - g_fly_yaw);
        if (!g_turn_back && cos_r(d) < 0 && (g_leashed || p <= BACK_MIN + 1))
            g_turn_back = absf(d) < PI_F - TURN_BACK_WIDE ? (d > 0 ? 1 : -1)
                        : corridor(k, 1) >= corridor(k, 0) ? 1 : -1;   /* (facing back, a left turn swings to the
                                                                        * route's right) */
        if (g_turn_back && cos_r(d) > TURN_BACK_DONE) g_turn_back = 0;
    }
    if (g_turn_back) g_fly_yaw += g_turn_back * TURN_BACK_W * dt;
    else g_fly_yaw -= sx * g_fly_turn * dt;
    {                                                            /* a little help: the heading eases along */
        float d = head - g_fly_yaw;                              /* the canyon (more with the stick let go) */
        d = wrap_pi(d);
        g_fly_yaw += d * minf(FLY_ASSIST * (1 - absf(sx)) * dt, 1);
    }
    float off = g_fly_yaw - head;                                /* no flying back down the canyon */
    while (off > PI_F) { off -= 2 * PI_F; g_fly_yaw -= 2 * PI_F; }
    while (off < -PI_F) { off += 2 * PI_F; g_fly_yaw += 2 * PI_F; }
    if (off > FLY_YAW_MAX) g_fly_yaw = head + FLY_YAW_MAX;
    if (off < -FLY_YAW_MAX) g_fly_yaw = head - FLY_YAW_MAX;
    g_fly_pitch += (sy * FLY_PITCH - g_fly_pitch) * minf(FLY_PITCH_EASE * dt, 1);
    throttle(dt);
    if (g_turn_back) g_fly_thr = TURN_SLOW;                     /* (turning round: slowed) */
    float v = FLY_V * g_fly_thr, cp = cos_r(g_fly_pitch);
    float dir[3] = { cos_r(g_fly_yaw) * cp, sin_r(g_fly_yaw) * cp, -sin_r(g_fly_pitch) };
    for (int i = 0; i < 3; i++) g_fly_pos[i] += dir[i] * v * dt;
    float roof = roof_at(k);
    if (g_fly_pos[2] > here[2] + roof) {                         /* under the roof: held, the nose levelled */
        g_fly_pos[2] = here[2] + roof;
        if (g_fly_pitch < 0) g_fly_pitch -= g_fly_pitch * minf(FLY_PITCH_EASE * 2 * dt, 1);
    }
    if (g_fly_pos[2] < here[2] - FLY_LOW) {                      /* no floor drawn (the haze): held over it */
        g_fly_pos[2] = here[2] - FLY_LOW;
        if (g_fly_pitch > 0) g_fly_pitch -= g_fly_pitch * minf(FLY_PITCH_EASE * 2 * dt, 1);
    }
    int rev = cos_r(g_fly_yaw - head) < 0;                       /* flown back down the canyon: the helps below */
    float way = rev ? head + PI_F : head;                        /* follow the ship's way (the user: fly back) */
    int slit = 0;                                                /* on edge by Z with a slit ahead: drawn in */
    for (uint32_t i = 0; i < SLIT_LOOK && !slit && (!rev || i <= k); i++) {   /* (or where a flat ship does not fit: */
        uint32_t j = rev ? k - i : k + i;                        /* IMG_EDGE) */
        slit = corridor(j, 0) + corridor(j, 1) < KNIFE_W || *(volatile uint8_t *)(U32(GALL_RAM + IMG_EDGE) + j);
    }
    if (slit && g_knife) {                                       /* onto the line at the ship's own place (to Chor's, */
        float a[3], b[3];                                        /* ~50 behind, it settled off the line on a bend) */
        route_pos(rev && k > 0 ? k - 1 : k, a); route_pos(rev && k > 0 ? k : k + 1, b);
        float ux = b[0] - a[0], uy = b[1] - a[1], ul = ux * ux + uy * uy;
        float u = ul > 1e-3f ? ((g_fly_pos[0] - a[0]) * ux + (g_fly_pos[1] - a[1]) * uy) / ul : 0;
        u = u < 0 ? 0 : u > 1 ? 1 : u;
        float on[2] = { a[0] + ux * u, a[1] + uy * u }, dx = on[0] - g_fly_pos[0], dy = on[1] - g_fly_pos[1];
        if (dx * dx + dy * dy < SLIT_CATCH * SLIT_CATCH) {
            float g = minf(SLIT_PULL * dt, 1), d = way - g_fly_yaw;
            d = wrap_pi(d);
            for (int i = 0; i < 2; i++) g_fly_pos[i] += (on[i] - g_fly_pos[i]) * g;   /* (across only: the height */
            g_fly_yaw += d * g;                                  /* and the nose kept, levelled it looked bad: the user) */
        }
    }
    if (node + FLY_END + FLY_HOME >= sw) {                       /* the end of control: onto the route; the height */
        float g = minf(FLY_GUIDE * dt, 1), d = head - g_fly_yaw;     /* on an even ramp to the route's as control ends */
        d = wrap_pi(d);                                          /* (thrown up from low: the user, 2026-10-16) */
        for (int i = 0; i < 2; i++) g_fly_pos[i] += (here[i] - g_fly_pos[i]) * g;
        float left = (float)sw - FLY_END - (p - 1), dz = 0;        /* (nodes to the end of control) */
        if (left > 1e-3f && step > 0) dz = (here[2] - g_fly_pos[2]) * minf(step / left, 1);
        else if (left <= 1e-3f) dz = here[2] - g_fly_pos[2];
        g_fly_pos[2] += dz;
        float rise = dt > 1e-4f ? -atan2_r(dz / dt, v) : 0;       /* nose along the ramp */
        g_fly_pitch += (rise - g_fly_pitch) * minf(FLY_PITCH_EASE * dt, 1);
        g_fly_yaw += d * g;
    } else {                                                     /* the rock */
        rock(IMG_COLL, dir, v, dt, here, head, 1, g_turn_back ? 2 : g_leashed);
    }
    {                                                            /* no farther off the route than FLY_LEASH */
        float dx = g_fly_pos[0] - here[0], dy = g_fly_pos[1] - here[1], d = sqrt_f(dx * dx + dy * dy);
        g_leashed = d > FLY_LEASH;                               /* (rock(): held, no crash) */
        if (g_leashed) { g_fly_pos[0] = here[0] + dx * FLY_LEASH / d; g_fly_pos[1] = here[1] + dy * FLY_LEASH / d; }
    }
    {                                                            /* wedged (hardly moving for STUCK_T): drawn */
        static float last[3], stuck;                             /* out towards the line, along it */
        float dx = g_fly_pos[0] - last[0], dy = g_fly_pos[1] - last[1];
        stuck = dx * dx + dy * dy < (v * dt * 0.2f) * (v * dt * 0.2f) ? stuck + dt : 0;
        if (stuck > STUCK_T) {                                   /* towards the route a little ahead (the */
            float to[3], g = minf(UNSTICK * 1.5f * dt, 1), d = way - g_fly_yaw;   /* nearest place may lie */
            route_pos(rev ? (k > 3 ? k - 3 : 0) : k + 3, to); to[2] -= SHIP_DROP;   /* behind the wall on a bend; back: behind); no longer put */
            d = wrap_pi(d);                                      /* there: still against the rock after */
                                                                 /* CRASH_T it blows up */
            for (int i = 0; i < 3; i++) g_fly_pos[i] += (to[i] - g_fly_pos[i]) * g;
            g_fly_yaw += d * g;
        }
        for (int i = 0; i < 3; i++) last[i] = g_fly_pos[i];
    }
    /* A cut through the rock to a later stretch of the canyon (the user: a gap seen, let me fly it): that stretch
     * much nearer than the one Chor is on, Chor is put there at once (Dash flies on along the route). On first, then
     * back (the user: at the loop's cut no flying back). */
    int put = 0;
    for (int back = 0; back < 2 && !put; back++) {
        float best = 1e30f, at = 0, here_d;
        float dx0 = g_fly_pos[0] - here[0], dy0 = g_fly_pos[1] - here[1];
        here_d = dx0 * dx0 + dy0 * dy0;
        for (uint32_t j = back ? (k > CUT_AHEAD + BACK_MIN ? k - CUT_AHEAD : BACK_MIN) : k + CUT_FROM;
             (back ? j + CUT_FROM <= k : j < k + CUT_AHEAD) && j + FLY_END + FLY_HOME + 2 < sw; j++) {
            float a[3], b[3];
            route_pos(j, a); route_pos(j + 1, b);
            float dx = b[0] - a[0], dy = b[1] - a[1], l = dx * dx + dy * dy;
            if (l < 1e-3f) continue;
            float u = ((g_fly_pos[0] - a[0]) * dx + (g_fly_pos[1] - a[1]) * dy) / l;
            u = u < 0 ? 0 : u > 1 ? 1 : u;
            float ex = a[0] + dx * u - g_fly_pos[0], ey = a[1] + dy * u - g_fly_pos[1], d = ex * ex + ey * ey;
            float z = g_fly_pos[2] - (a[2] - SHIP_DROP);              /* (low the cut never caught: the user flew under) */
            if (d < best && z > -FLY_LOW && z < roof_at(j + 1)) { best = d; at = (float)j + u; }
        }
        if (best < CUT_NEAR * CUT_NEAR && best * 4 < here_d) {   /* (the ship stays where it is: its offset is */
            uint32_t j = chor_put(chor, at, here);               /* from the new place) */
            k = j + 1; p = at + 1; g_fly_p = p; put = 1;
        }
    }
    /* Chor to the ship's nearest place on the route, at the ship's pace along it and closing in; gone back more than
     * half a node (not in the guide's stretch), Chor is put there at once (the user: fly back much further). */
    float to = route_near(k, g_fly_pos), a[3], b[3], back = to < BACK_MIN ? BACK_MIN : to;
    if (!put && back < p - 0.5f && node + FLY_END + FLY_HOME < sw) {
        chor_put(chor, back, here);
        g_fly_p = back; g_fly_speed = 0;
    } else {
        route_pos(k, a); route_pos(k + 1, b);
        float ux = b[0] - a[0], uy = b[1] - a[1], ul = sqrt_f(ux * ux + uy * uy);
        float along = ul > 1e-3f ? (dir[0] * ux + dir[1] * uy) / ul * v * dt / ul : 0;   /* nodes this frame */
        float go = (along > 0 ? along : 0) + (to > p ? (to - p) * 0.3f : 0);
        g_fly_speed = go / g_chor_rate;
        if (g_fly_speed > 4 * SPEED) g_fly_speed = 4 * SPEED;
    }
    F32(chor + CHOR_SPEED) = g_fly_speed;
    for (int i = 0; i < 3; i++) {
        g_ship_off[i] = g_fly_pos[i] - here[i];
        g_ship_at[i] = g_fly_pos[i] + (i == 2 ? SHIP_DROP : 0);  /* (drawn there: falcon_gun()) */
    }
    float yo = g_fly_yaw - head;
    yo = wrap_pi(yo);
    g_ship_yaw = -yo;                                            /* (to the right) */
    g_ship_head = g_fly_yaw; g_ship_head_on = 1;                 /* (drawn: the heading itself, falcon_gun()) */
    g_ship_pitch = g_fly_pitch;
}
