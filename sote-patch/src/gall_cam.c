/* Gall Run (gallrun.c): the camera: the run's view (Trak's draw and update methods), the gunner's, the fade. */
#include "common.h"
#include "gall.h"

#define CLASS_UPDATE     0x1C       /* class record: update method */
#define CLASS_DRAW       0x20       /* class record: draw method */
#define VIEW_FOLLOW      0.04f      /* per frame */
#define VIEW_BACK        70.0f      /* the camera looks down at the ship as from this far behind */
#define VIEW_BEHIND      2          /* the eye: on the route this many nodes behind the ship (~72 units) */
#define VIEW_TRACK       0.5f       /* share of the player's offset the camera follows (more: into the rock on bends) */
#define VIEW_UP          22.0f
#define VIEW_BACK_FREE   95.0f      /* free flight: further back (the ship turns and climbs more there) */
#define VIEW_HOLD        0.85f      /* per frame: after the opening shot the game's own camera pull comes in */
#define VIEW_CARRY       0.9f       /* per frame: a jump where the run camera's eye changes source eases out */
#define CAMERA_LOOK      0x10       /* it looks at this matrix's translation */
#define FADE_HOLD        0.2f       /* the opening shot starts black this long, */
#define VIEW_EYE_R       10.0f      /* the camera kept this far out of the rock */
#define VIEW_TURN        3.0f       /* per second: the camera's heading follows the ship's */

/* The run's camera (entry 3, Trak 1's view) back on, the gun's off: after firing in stage 2 the gun's entry is
 * the active one (each entry's +0: active flag; ACTIVE_CAMERA; CAMERA_INDEX: all three, or the scene and the
 * free flight kept the gun's view, the user). */
void run_camera_as(int copy) {
    uint32_t ent = U32(CAMERA_ENTRIES), cur = U32(ACTIVE_CAMERA);
    if (!valid_ptr(ent)) return;
    if (copy && valid_ptr(cur) && cur != ent + 3 * 0x80)                 /* entry 3 starts from the view on screen: its own */
        for (int i = 0x14; i < 0x50; i += 4) U32(ent + 3 * 0x80 + i) = U32(cur + i);   /* rows and eye were stale
                                                                  * (a frame of a view far off: the user, a jump) */
    U32(ent + CAMERA_GUN * 0x80) = 0;
    U32(ent + 3 * 0x80) = 1;
    U32(ACTIVE_CAMERA) = ent + 3 * 0x80;
    U32(CAMERA_INDEX) = 3;
}
void run_camera(void) { run_camera_as(1); }

/* Stage 1 camera: the stock one (Trak) rides the route behind the ship and looks along it, so in
 * the S-bends it swings round several times a second. Its draw method copies its matrix (rows
 * right, forward, up at TRAK_MATRIX, the eye after them) into its scene node; while the mission
 * runs that method is ours (trak_draw), and in stage 1 it first puts in a camera that looks along
 * a slowly following heading (VIEW_FOLLOW of the way to the route's heading VIEW_AHEAD nodes on,
 * per frame), from the route VIEW_BEHIND nodes back (the route keeps off the walls; a point
 * behind along the heading cut the bends through the rock), VIEW_UP above (less under rock: the
 * corridor's up), moved with VIEW_TRACK
 * of the player's offset. */
float g_view[2];                    /* the camera's heading (unit, horizontal) */
static uint32_t g_trak_draw;        /* the game's Trak draw method */

/* The Trak's matrix: at eye, looking along f (any length), level. */
void view_set(uint32_t obj, const float *eye, float *f) {
    float r[3], u[3], l = len3(f);
    for (int i = 0; i < 3; i++) f[i] /= l;
    l = sqrt_f(f[0] * f[0] + f[1] * f[1]);
    r[0] = f[1] / l; r[1] = -f[0] / l; r[2] = 0;                          /* forward x up */
    u[0] = r[1] * f[2] - r[2] * f[1]; u[1] = r[2] * f[0] - r[0] * f[2]; u[2] = r[0] * f[1] - r[1] * f[0];
    for (int i = 0; i < 3; i++) {
        F32(obj + TRAK_MATRIX + 4 * i) = r[i];
        F32(obj + TRAK_MATRIX + 0x10 + 4 * i) = f[i];
        F32(obj + TRAK_MATRIX + 0x20 + 4 * i) = u[i];
        F32(obj + TRAK_MATRIX + 0x30 + 4 * i) = eye[i];
    }
}

/* A view's carry (gall.h). f: the view's forward (any length), turned to the carried one. */
void carry_from(carry_t *c, const float *eye, const float *f) {
    for (int i = 0; i < 3; i++) { c->d[i] = g_cam_seen[i] - eye[i]; c->d[3 + i] = g_cam_seen[3 + i] - f[i]; }
    c->share = 1;
}
/* Is the Falcon (fal) inside the screen's inner part (KEEP_EDGE off each edge) of a level view at eye along f? */
static int keep_in(const float *eye, const float *f, const float *fal, float px, float py) {
    float l = len3(f), h, v[3], z = 0, x = 0, y = 0, r[3], fn[3], u[3];
    if (l < 1e-4f) return 0;
    for (int i = 0; i < 3; i++) { fn[i] = f[i] / l; v[i] = fal[i] - eye[i]; }
    h = sqrt_f(fn[0] * fn[0] + fn[1] * fn[1]);
    if (h < 1e-4f) return 0;
    r[0] = fn[1] / h; r[1] = -fn[0] / h; r[2] = 0;               /* (view_set's rows) */
    u[0] = r[1] * fn[2]; u[1] = -r[0] * fn[2]; u[2] = r[0] * fn[1] - r[1] * fn[0];
    for (int i = 0; i < 3; i++) { z += fn[i] * v[i]; x += r[i] * v[i]; y += u[i] * v[i]; }
    if (z < 1) return 0;
    x *= px / z; y *= py / z;
    return absf(x) <= 1 - 2 * KEEP_EDGE && absf(y) <= 1 - 2 * KEEP_EDGE;
}
/* From the view on screen moved on by its last step (a switch on a frame the game moves: the view held two frames
 * while the Falcon went on hopped). */
void carry_paced(carry_t *c) {
    for (int i = 0; i < 6; i++) c->d[i] += g_cam_step[i];
}
void carry_on(carry_t *c, float *eye, float *f, const float *fal) {
    if (c->share <= 0) return;
    for (int i = 0; i < 3; i++) { eye[i] += c->d[i]; f[i] += c->d[3 + i]; }
    float fov = F32(PERSPECTIVE), asp = F32(PERSPECTIVE + 4), hf = fov * (PI_F / 360.0f);
    if (!(fov > 1 && fov < 179)) hf = PI_F / 4;
    if (!(asp > 0.1f)) asp = 4.0f / 3.0f;
    float py = cos_r(hf) / sin_r(hf), px = py / asp;
    if (keep_in(eye, f, fal, px, py)) return;                    /* the carried look kept while the Falcon is inside; */
    float l = len3(f), d[3], dl, g[3], lo = 0, hi = 1;            /* else turned toward it just enough to bring it */
    for (int i = 0; i < 3; i++) d[i] = fal[i] - eye[i];          /* back to that edge */
    dl = len3(d);
    if (l < 1e-4f || dl < 1) return;
    for (int n = 0; n < 12; n++) {
        float m = (lo + hi) * 0.5f;
        for (int i = 0; i < 3; i++) g[i] = f[i] / l + (d[i] / dl - f[i] / l) * m;
        if (keep_in(eye, g, fal, px, py)) hi = m; else lo = m;
    }
    for (int i = 0; i < 3; i++) f[i] = (f[i] / l + (d[i] / dl - f[i] / l) * hi) * l;
}
void carry_decay(carry_t *c) {
    if (c->share <= 0 || paused()) return;
    for (int i = 0; i < 6; i++) c->d[i] *= CINE_CARRY;
    c->share *= CINE_CARRY;
    if (c->share < 0.002f) c->share = 0;
}
/* The carry on a camera entry's own rows (the game's view this frame), written back into them. */
void carry_entry(carry_t *c, uint32_t ent, const float *fal) {
    float eye[3], f[3];
    for (int i = 0; i < 3; i++) { eye[i] = F32(ent + 0x44 + 4 * i); f[i] = 100 * F32(ent + 0x24 + 4 * i); }
    carry_on(c, eye, f, fal);
    view_set(ent + 0x14 - TRAK_MATRIX, eye, f);
}
/* The drawn Falcon's place (falcon.c: the ship moved by g_ship_off, g_ship_drop under it). */
void falcon_place(float *p) {
    uint32_t stft = player_ship();
    for (int i = 0; i < 3; i++) p[i] = stft ? F32(stft + 0x50 + 4 * i) + g_ship_off[i] - (i == 2 ? g_ship_drop : 0) : 0;
}

/* The opening shot comes in from black, as levels start (set here, after the game's own fade
 * on restarting the level). */
static void fade(void) {
    if (paused()) return;                                       /* (the game's pause dim stays: the user, 2026-10-21) */
    float f = (g_intro_t - FADE_HOLD) / FADE_IN;
    if (g_intro && g_intro_t < FADE_HOLD + FADE_IN + 0.5f)
        for (int i = 0; i < 4; i++) S16(SCREEN_FADE + 2 * i) = f >= 1 ? -1000 : i < 3 ? 0 : (int)(FADE_MAX * (f < 0 ? 1 : 1 - f));
}

static float g_view_last[18];       /* trak_draw: the run camera's eye and forward last frame, the one before, the carried jump */
static int g_view_mode = -1;
static float g_view_hold;          /* trak_update: how much of the game's own view it still holds off after the shot */        /* the eye's source last frame: 0 the opening shot, 1 the lead, 2 the route */

static float g_free_look[3], g_free_eye[3];

/* The gunner's view: the game's own (the user, 2026-10-14: ours, the whole ship in view from 120 behind, did not turn
 * with the stick and the view from inside the Falcon was gone). Stage 2 is left to the game (its gun camera, entry
 * CAMERA_GUN, after the first shot; the views the buttons switch to). On the rail the run's entry stayed (the guns
 * turned under a view that stood still): the gun's entry is made the active one as the rail starts and after
 * each of our shots, then left to the game. */
static int g_gunner;                /* (0: no view of ours; trak_draw, trak_update) */
carry_t g_gun_carry;                /* gun_view(): the end scene into the rail's gun view (gallrun.c goes on with it) */
int g_gun_ease;                     /* (cine(): set as the scene ends) */
int g_gun_to = CAMERA_GUN;          /* the entry the ease goes into (gallrun.c) */
int g_gun_blend;                    /* story(): Dash's shot over: back to the gunner's own view (inside or behind, as
                                     * the view key left it), eased in from the shot's last view as from the end scene
                                     * (the game's blend from entry 3 stalled and hopped), not a cut
                                     * (the user, 2026-10-17: the chase view after his jump lost the view and left the
                                     * sight hanging, the guns turning under a view that stood still) */
static int gun_view(uint32_t obj, uint32_t chor) {
    static int was;
    uint32_t ent = U32(CAMERA_ENTRIES);
    (void)obj; (void)chor;
    if (!valid_ptr(ent)) return 0;
    int want = g_rail && !g_shot && g_cine != 1 && !g_free && !g_intro;
    if (want && !was) {
        int to = g_gun_blend && S16(VIEW_MODE) == CAMERA_INSIDE ? CAMERA_INSIDE : CAMERA_GUN;
        uint32_t gun = ent + to * 0x80;
        U32(gun) = 1; U32(ACTIVE_CAMERA) = gun; U32(CAMERA_INDEX) = to;
        g_gun_to = to;
        if (g_gun_ease || g_gun_blend) {                         /* the end scene's (Dash's shot's) last view eased */
            float f[3], fal[3];                                  /* into the gun's (gallrun.c */
            for (int i = 0; i < 3; i++) f[i] = 100 * F32(gun + 0x24 + 4 * i);
            carry_from(&g_gun_carry, (const float *)(gun + 0x44), f);
            carry_paced(&g_gun_carry);
            falcon_place(fal);
            carry_entry(&g_gun_carry, gun, fal);                 /* each frame after; this frame: the view on screen, its rows */
            g_gun_ease = 2;                                      /* stale till the game's camera update: the carry */
        }                                                        /* starts from them a frame later) */
    }
    if (want && !was && g_gun_ease == 1) g_gun_ease = 0;
    if (want) g_gun_blend = 0;
    was = want;
    return 0;
}

static void trak_draw(uint32_t obj, uint32_t a1, uint32_t a2, uint32_t a3) {
    uint32_t chor = U32(CLASS_CHOR + 0x10);
    fade();
    if (g_native && valid_ptr(U32(CAMERA_ENTRIES)))              /* (the game sets the gun's offsets in entry 5 every */
        for (int i = 0; i < 6; i++) U32(U32(CAMERA_ENTRIES) + 5 * 0x80 + 0x54 + 4 * i) = SKY_VIEWS[1][i];   /* frame) */
    if ((g_view_on || g_intro) && U32(CLASS_CHOR + 8) && U32(obj + TRAK_TARGET) == chor) {
        uint32_t k = U32(chor + CHOR_NODE);
        if (k >= LEAD_FROM) k = 0;                                        /* the lead nodes before node 0 */
        k++;
        float a[3], b[3], eye[3], f[3];
        route_pos(k, a); route_pos(k + VIEW_AHEAD, b);
        float dx = b[0] - a[0], dy = b[1] - a[1], l = sqrt_f(dx * dx + dy * dy);
        if (l > 1e-3f) {
            if (g_view[0] == 0 && g_view[1] == 0) { g_view[0] = dx / l; g_view[1] = dy / l; }
            g_view[0] += (dx / l - g_view[0]) * VIEW_FOLLOW;
            g_view[1] += (dy / l - g_view[1]) * VIEW_FOLLOW;
            l = sqrt_f(g_view[0] * g_view[0] + g_view[1] * g_view[1]);
            g_view[0] /= l; g_view[1] /= l;
            if (k < VIEW_BEHIND) {                                        /* on the lead: behind along the heading */
                for (int i = 0; i < 3; i++) eye[i] = F32(chor + 0x50 + 4 * i) - (i < 2 ? g_view[i] * VIEW_BACK : 0);
                eye[2] += VIEW_UP;
            } else {
                route_pos(k - VIEW_BEHIND, a); route_pos(k - VIEW_BEHIND + 1, b);   /* on the route behind: */
                for (int i = 0; i < 3; i++)                               /* the line keeps off the rock */
                    eye[i] = a[i] + (b[i] - a[i]) * F32(chor + CHOR_PARAM) + g_ship_off[i] * VIEW_TRACK;
                float up = corridor(k - VIEW_BEHIND, 3);                  /* under rock (a low bridge): */
                eye[2] += up < VIEW_UP ? up : VIEW_UP;                    /* no higher than the corridor */
            }
            f[0] = g_view[0] * VIEW_BACK * 2; f[1] = g_view[1] * VIEW_BACK * 2; f[2] = -VIEW_UP;
            if (g_intro || g_cine == 1 || g_shot) {                       /* the opening shot's (the end scene's, ours) camera */
                g_view[0] = g_view[1] = 0;                                /* (the heading starts afresh after it) */
                for (int i = 0; i < 3; i++) { eye[i] = g_ik[i]; f[i] = g_ik[3 + i] - g_ik[i]; }
            }
            /* The eye's sources (the shot, behind the ship on the lead, on the route behind) don't meet
             * exactly: where it changes source, the jump is carried and eased out (no jolt). */
            if (g_fly_on && !g_intro) {                                   /* flown: behind the ship, its way */
                static float hd[3];                                       /* (free flight: its pitch too, the camera */
                float cp = cos_r(g_fly_pitch);                           /* above and behind it as it climbs or dives: */
                float w = minf(VIEW_TURN * frame_dt(), 1), hx = cos_r(g_fly_yaw) * cp, hy = sin_r(g_fly_yaw) * cp,   /* level, */
                      hz = -sin_r(g_fly_pitch);                          /* its tail swung into the camera: the user; stage 1 too) */
                if (g_view_mode != 3) { hd[0] = g_view[0]; hd[1] = g_view[1]; hd[2] = 0; }
                hd[0] += (hx - hd[0]) * w; hd[1] += (hy - hd[1]) * w; hd[2] += (hz - hd[2]) * w;
                float hl = len3(hd);
                if (hl > 1e-3f) { hd[0] /= hl; hd[1] /= hl; hd[2] /= hl; }
                float hh = sqrt_f(hd[0] * hd[0] + hd[1] * hd[1]);
                if (hh > 1e-3f) { g_view[0] = hd[0] / hh; g_view[1] = hd[1] / hh; }
                float back = g_free ? VIEW_BACK_FREE : VIEW_BACK;
                for (int i = 0; i < 3; i++) eye[i] = g_fly_pos[i] - hd[i] * back;
                eye[2] += VIEW_UP + SHIP_DROP;                            /* (as over the route: the ship is drawn SHIP_DROP under it) */
                static const float ax[3][3] = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } }, r[3] = { VIEW_EYE_R, VIEW_EYE_R, VIEW_EYE_R };
                float n[3];
                collide(IMG_COLL, eye, ax, r, n);                                   /* out of the rock */
                f[0] = hd[0] * back * 2; f[1] = hd[1] * back * 2; f[2] = hd[2] * back * 2 - VIEW_UP;
            }
            float *last = g_view_last, *prev = g_view_last + 6, *carry = g_view_last + 12;
            int m = g_intro || g_cine == 1 || g_shot ? 0 : g_fly_on ? 3 : k < VIEW_BEHIND ? 1 : 2;
            int mode = g_view_mode;
            for (int i = 0; i < 6; i++) {
                float *v = i < 3 ? &eye[i] : &f[i - 3];
                if (m == 0) carry[i] = 0;                                 /* on at its last pace */
                else if (m != mode && mode >= 0) carry[i] = 2 * last[i] - prev[i] - *v;
                *v += carry[i];
                carry[i] *= VIEW_CARRY;
                prev[i] = last[i]; last[i] = *v;
            }
            g_view_mode = m;
            if (g_shake > 0.05f) {                                        /* a hit (fly()) */
                float w = (float)g_ov_frames;
                eye[0] += g_shake * ship_sin(w * 2.1f); eye[1] += g_shake * ship_sin(w * 2.7f + 1); eye[2] += g_shake * ship_sin(w * 3.3f + 2);
            }
            for (int i = 0; i < 3; i++) { g_free_look[i] = eye[i] + f[i]; g_free_eye[i] = eye[i]; }   /* (free flight: */
                                                                          /* the camera looks there; trak_update's) */
            view_set(obj, eye, f);
            if (g_free && g_fly_on) {                                     /* free flight: straight into the camera too */
                run_camera_as(0);                                         /* (at the draw too: firing switched to the gun after) */
                F32(VIEW_BLEND + 0x20) = F32(VIEW_BLEND + 0x24);          /* no blend between views left running */
                uint32_t ent = U32(CAMERA_ENTRIES), cams[3] = { U32(ACTIVE_CAMERA), ent + 3 * 0x80, ent + CAMERA_GUN * 0x80 };
                for (int c = 0; c < 3; c++)                               /* (it was taken in part from the Trak's own */
                    if (valid_ptr(cams[c]) && valid_ptr(ent))             /* view, on the route back by Chor: the eye */
                        for (int i = 0; i < 0x40; i += 4) U32(cams[c] + 0x14 + i) = U32(obj + TRAK_MATRIX + i);   /* closed */
            }                                                             /* in on the ship, the user; and the gun's, as */
                                                                          /* firing switches to it) */
        }
    }
    /* The view is the active camera's: its eye is the dolly's (gallrun_frame() copies it there),
     * and it looks at a matrix, Chor's. The opening shot looks elsewhere: at a copy of Chor's
     * matrix moved to where the shot looks. */
    if (U32(CLASS_CHOR + 8)) gun_view(obj, U32(CLASS_CHOR + 0x10));
    if (g_pilot || g_cine == 1) target_panel(1);                 /* (the game shows it between our frame and the draw) */
    S16(HUD_POS + 4 * HUD_TIE_COUNT) = -1000;                    /* the base level's "TIE Fighters: n" off (the user) */
    hud_hide(HUD_MISSILES, g_pilot || g_cine == 1);
    if (g_native && g_fj_t < 0) battle_hud(player_ship());       /* (the towers' warning and panel: gall_space.c) */
    if (g_bar_t > 0) boss_bar(0);                                /* (again at the draw: the level's HUD update hides
                                                                  * its spare elements between our frame and the draw) */
    static uint32_t fake[0x40 / 4];
    uint32_t cam = U32(ACTIVE_CAMERA);
    if (valid_ptr(cam)) {                                       /* (free flight too: Chor holds at the rail's end, */
        int own = g_intro || (g_free && g_fly_on) || g_gunner;               /* the camera looked at it, past the ship, the user) */
        if (own && U32(cam + CAMERA_LOOK) == chor + 0x20) U32(cam + CAMERA_LOOK) = (uint32_t)fake;
        if (U32(cam + CAMERA_LOOK) == (uint32_t)fake) {
            if (!own) U32(cam + CAMERA_LOOK) = chor + 0x20;
            for (int j = 0; j < 0x40 / 4; j++) fake[j] = U32(chor + 0x20 + 4 * j);
            for (int j = 0; j < 3; j++) F32((uint32_t)fake + 0x30 + 4 * j) = g_intro ? g_ik[3 + j] : g_free_look[j];
        }
    }
    ((method_fn)g_trak_draw)(obj, a1, a2, a3);
}

/* The Trak's update places its own view each frame, and the camera takes that in part: in the
 * opening shot the shot's view goes over it at once. */
static uint32_t g_trak_update;      /* the game's Trak update method */
uint32_t g_sd_push;                 /* (probes) frames sd_eye() moved the eye */

/* The final battle's view (the space level's, the game's Trak 0 on the ship) out of the Star Destroyer's hull (the user,
 * 2026-10-19: the camera went into it by the towers): from the ship (SKY_UP
 * over it) toward the game's eye in CAM_MARCH steps, each held VIEW_EYE_R off the hull's triangles (as the free
 * flight's eye off the rock, one push: an eye deep inside is behind their drawn side); at the first one pushed the eye
 * stays, still looking at the ship. */
#define CAM_MARCH        10
#define SKY_LOOK_UP      20.0f      /* (gall_native.c SKY_UP: Trak 0 looks at the ship this far over it) */
static void sd_eye(uint32_t obj) {
    uint32_t s = U32(obj + TRAK_TARGET);
    static const float r[3] = { VIEW_EYE_R, VIEW_EYE_R, VIEW_EYE_R };
    float a[3], e[3], p[3], n[3], f[3];
    for (int i = 0; i < 3; i++) {
        a[i] = F32(s + 0x50 + 4 * i) + (i == 2 ? SKY_LOOK_UP : 0);
        e[i] = F32(obj + TRAK_MATRIX + 0x30 + 4 * i);
    }
    for (int k = 1; k <= CAM_MARCH; k++) {
        for (int i = 0; i < 3; i++) p[i] = a[i] + (e[i] - a[i]) * (float)k / CAM_MARCH;
        if (collide(IMG_SD_COLL, p, AX_UNIT, r, n) <= 0) continue;
        g_sd_push++;
        for (int i = 0; i < 3; i++) f[i] = a[i] - p[i];
        if (len3(f) > 1) view_set(obj, p, f);
        return;
    }
}

static void trak_update(uint32_t obj, uint32_t a1, uint32_t a2, uint32_t a3) {
    int sky = g_native && g_sky_carry.share > 0 && obj == U32(CLASS_TRAK + 0x10) && U32(obj + TRAK_TARGET) == player_ship();
    if (sky) for (int i = 0; i < 16; i++) F32(obj + TRAK_MATRIX + 4 * i) = g_sky_own[i];   /* (its own view back) */
    ((method_fn)g_trak_update)(obj, a1, a2, a3);
    if ((g_intro || g_cine == 1 || g_shot) && U32(CLASS_CHOR + 8) && U32(obj + TRAK_TARGET) == U32(CLASS_CHOR + 0x10)) {
        float f[3];
        for (int i = 0; i < 3; i++) f[i] = g_ik[3 + i] - g_ik[i];
        view_set(obj, g_ik, f);
    } else if ((g_fly_on || g_gunner) && U32(CLASS_CHOR + 8) && U32(obj + TRAK_TARGET) == U32(CLASS_CHOR + 0x10)) {
        float f[3];                                              /* flown (stage 1, free flight): ours (last drawn) before the camera */
        for (int i = 0; i < 3; i++) f[i] = g_free_look[i] - g_free_eye[i];   /* takes the view (the game's stayed by */
        if (f[0] != 0 || f[1] != 0) view_set(obj, g_free_eye, f); /* Chor at the rail's end: the ship flew off it) */
    } else if (g_view_hold > 0.01f && U32(CLASS_CHOR + 8) && U32(obj + TRAK_TARGET) == U32(CLASS_CHOR + 0x10)) {
        /* The shot's just over. The camera's eye is taken from here (before trak_draw), where the
         * game's own update pulls the view its way: held at ours (on at its last pace) at first,
         * the pull let in over VIEW_HOLD. */
        float e[3], f[3], l = 0, lf = 0;
        for (int i = 0; i < 3; i++) {
            f[i] = 2 * g_view_last[3 + i] - g_view_last[9 + i];
            l += f[i] * f[i]; lf += F32(obj + TRAK_MATRIX + 0x10 + 4 * i) * F32(obj + TRAK_MATRIX + 0x10 + 4 * i);
        }
        l = sqrt_f(l) / sqrt_f(lf);                             /* the game's forward to our length */
        for (int i = 0; i < 3; i++) {
            float ge = F32(obj + TRAK_MATRIX + 0x30 + 4 * i), gf = F32(obj + TRAK_MATRIX + 0x10 + 4 * i) * l;
            e[i] = ge + (2 * g_view_last[i] - g_view_last[6 + i] - ge) * g_view_hold;
            f[i] = gf + (f[i] - gf) * g_view_hold;
        }
        view_set(obj, e, f);
        g_view_hold *= VIEW_HOLD;
    }
    if (g_intro || g_cine == 1 || g_shot) g_view_hold = 1;
    if (g_native && g_fj_t < 0 && U32(obj + TRAK_TARGET) == player_ship()) sd_eye(obj);
    if (sky) { carry_decay(&g_sky_carry); sky_carry(obj); }
}
uint32_t g_tie_update;              /* the game's TieF update method */
uint32_t g_tie_draw;                /* the game's TieF draw method (tie_draw: ours while the mission runs) */

/* trak_draw and trak_update in Trak's class record while the mission runs, the game's own otherwise
 * (and tie_update in TieF's). */
void trak_method(int ours) {
    if (!g_tie_update) g_tie_update = U32(CLASS_TIEF + CLASS_UPDATE);
    if (U32(CLASS_TIEF + CLASS_UPDATE) == g_tie_update || U32(CLASS_TIEF + CLASS_UPDATE) == (uint32_t)tie_update)
        U32(CLASS_TIEF + CLASS_UPDATE) = ours ? (uint32_t)tie_update : g_tie_update;
    if (!g_tie_draw) g_tie_draw = U32(CLASS_TIEF + CLASS_DRAW);
    if (U32(CLASS_TIEF + CLASS_DRAW) == g_tie_draw || U32(CLASS_TIEF + CLASS_DRAW) == (uint32_t)tie_draw)
        U32(CLASS_TIEF + CLASS_DRAW) = ours ? (uint32_t)tie_draw : g_tie_draw;
    if (!g_trak_draw) g_trak_draw = U32(CLASS_TRAK + CLASS_DRAW);
    if (!g_trak_update) g_trak_update = U32(CLASS_TRAK + CLASS_UPDATE);
    if (U32(CLASS_TRAK + CLASS_DRAW) != g_trak_draw && U32(CLASS_TRAK + CLASS_DRAW) != (uint32_t)trak_draw) return;
    U32(CLASS_TRAK + CLASS_DRAW) = ours ? (uint32_t)trak_draw : g_trak_draw;
    if (U32(CLASS_TRAK + CLASS_UPDATE) == g_trak_update || U32(CLASS_TRAK + CLASS_UPDATE) == (uint32_t)trak_update)
        U32(CLASS_TRAK + CLASS_UPDATE) = ours ? (uint32_t)trak_update : g_trak_update;   /* (not over the cheats' AT-ST camera's) */
}
