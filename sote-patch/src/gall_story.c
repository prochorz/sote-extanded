/* Gall Run (gallrun.c): the cast and the story: the opening shot, the Outrider, the end scene, the rail. */
#include "common.h"
#include "gall.h"

#define OUTRIDER_ASTR    0          /* rock whose node draws the Outrider */
#define SLAVE_ASTR       3          /* and Slave I (stage 2: on its pad, then the scene, then the chase) */
#define DASH_ASTR        4          /* and Dash on foot (the end scene) */
#define IMG_INTRO        100        /* the opening shot: key count, keys (gall_asset.py intro_keys()) */
#define KEY_SIZE         68         /* a key: seconds, then the camera's eye and the point it looks at, the
                                     * Outrider, the Falcon (each x, y, z off Chor's place; Falcon: off it), its pitch, its roll,
                                     * the Outrider's roll, the Falcon's yaw */
#define OR_AHEAD         5.5f       /* Outrider: route nodes ahead of the Falcon (36 units each) it keeps, */
#define OR_LAG           8.0f       /* slowing down to OR_SLOW of the Falcon's cruise when this many more ahead, */
#define OR_SLOW          0.5f
#define OR_WAIT          8.0f       /* and on down to a stop this many more (the user: Dash waits while the Falcon goes back) */
#define OR_FAST          1.4f       /* speeding up to this when the Falcon is OR_AHEAD - 3.5 nodes closer */
#define OR_RATE_EASE     2.0f       /* per second */
#define OR_MIN_GAP       2.0f       /* never closer to the Falcon than this many route nodes (it was caught on the bends: */
                                    /* its route progress outran OR_FAST) */
#define LAG_GAP          4.0f       /* this many nodes further behind than OR_AHEAD */
#define LAG_SAY          3.0f       /* for this many seconds: Dash calls, */
#define LAG_QUIET        15.0f      /* not again for this long */
#define OR_PEEL          40         /* it breaks off this many nodes before the switch: */
#define OR_PEEL_ACC      1.2f       /* its speed grows by this share a second, */
#define OR_PEEL_T        1.8f       /* seconds, then hidden; */
#define OR_PEEL_UP       350.0f     /* and up off the route (units x seconds^2): 36 deg pitch at 0.5 s, the walls (up to
                                     * 734 over the route there) cleared at 1.44 s; straight on from its heading it left
                                     * the route where it turns 90 deg and flew into the walls (the user's playtest);
                                     * over the route there it is open sky */
#define OR_R             12.0f      /* the path picked clear of rock for a sphere this big (it went through it, the user) */
#define SPIN_EASE        0.25f      /* the Outrider off the edge: on round a whole turn, this share a frame, */
#define SPIN_MAX         0.22f      /* at most this (radians a frame) */
float g_intro_t;                    /* seconds into the opening shot */
int g_intro;                        /* the opening shot runs this frame */
float g_ik[15];                     /* its eye, look, Outrider, Falcon (world) and the Outrider's heading */
static float g_or_roll;             /* the Outrider's bank (radians, right wing down) */
float g_or_spin;                    /* coming off the edge: the bank it rolls on to (a whole turn), 0 when not */
float g_or_f;                       /* the Outrider's place on the route (nodes; 0: not yet set) */
float g_or_dz;                      /* its height off the route: eased to the flown Falcon's (g_ship_off[2]), FLY_LOW under
                                     * the route up to the corridor's top, pushed out of the rock (the user: it left the
                                     * frame as the Falcon climbed or dived) */
#define OR_DZ_EASE       6.0f       /* g_or_dz eased this share a second */
static float g_or_rate;             /* its speed, share of the Falcon's cruise */
float g_or_pt;                      /* seconds into its break-off (0: not yet) */
float g_lag_t, g_lag_quiet;         /* seconds the Falcon has been far behind; till the next "keep up" */
int g_said_slit;                    /* Dash's line at a slit, said this run */
int g_said_atmo;                    /* Lando's "We're leaving the atmosphere!", said this rail */
int g_hp_kept;                       /* stage 1: the health as the rock left it (stage1_guard()) */
float g_or_jump = -1, g_sl_jump = -1;          /* story(): seconds into the Outrider's, Slave I's jump to lightspeed (-1: not) */
int g_sl_on_rail;                    /* flee(): its gap on the rail seeded (0: again, rail_restart()) */
float g_restart_t = -1;              /* rail_restart(): seconds into the fade-in (-1: none) */
int g_shot;                          /* story(): a shot of ours on the rail (the camera at g_ik, as the end scene's) */
int g_sc;                            /* story(): 0 not yet, 1 Dash's shot, 2 on, 3 closing in, 4 Slave I's shot, 5 over */
float g_sl_hp = SL_HP;
int g_sl_lost;                      /* shot down to 0: the mission failed (1 said, held; then finish()) */
static const uint32_t OR_MESHES[] = { 0x801A3C64, 0x801A3C7C, 0x801A3C94 };   /* glows, hull (gall_level.bin) */
static uint32_t g_or_decoy[0x48 / 4], g_or_node;

/* The opening shot (the image's keys, linear between them, seconds from the start of the run):
 * Chor (the Falcon's place on the route) holds still, the camera, the Outrider and the Falcon
 * go where the keys say; the run starts when they end. (The view: gallrun_frame().) */
static uint32_t key_at(float tm, float *s) {
    uint32_t n = U32(GALL_RAM + IMG_INTRO), a = U32(GALL_RAM + IMG_INTRO + 4), k = 0;
    while (k + 2 < n && F32(a + (k + 1) * KEY_SIZE) <= tm) k++;
    a += k * KEY_SIZE;
    *s = (tm - F32(a)) / (F32(a + KEY_SIZE) - F32(a));
    if (*s > 1) *s = 1;
    return a;
}

void intro(uint32_t chor) {
    uint32_t n = U32(GALL_RAM + IMG_INTRO), a = U32(GALL_RAM + IMG_INTRO + 4);
    g_intro = n > 1 && g_intro_t < F32(a + (n - 1) * KEY_SIZE);
    g_ship_pitch = g_ship_yaw = 0;
    if (!g_intro) return;
    F32(chor + CHOR_PARAM) = 0;                                  /* on its spline's first node */
    float s;
    a = key_at(g_intro_t, &s);
    for (int i = 0; i < 12; i++)
        g_ik[i] = F32(a + 4 + 4 * i) + (F32(a + KEY_SIZE + 4 + 4 * i) - F32(a + 4 + 4 * i)) * s
                  + (i < 9 ? F32(chor + 0x50 + 4 * (i % 3)) : 0);
    for (int i = 0; i < 3; i++) {
        g_ship_off[i] = g_ik[9 + i];
        g_ik[12 + i] = F32(a + KEY_SIZE + 28 + 4 * i) - F32(a + 28 + 4 * i);
    }
    g_ship_pitch = F32(a + 52) + (F32(a + KEY_SIZE + 52) - F32(a + 52)) * s;
    g_ship_roll = F32(a + 56) + (F32(a + KEY_SIZE + 56) - F32(a + 56)) * s;
    g_or_roll = F32(a + 60) + (F32(a + KEY_SIZE + 60) - F32(a + 60)) * s;
    g_ship_yaw = F32(a + 64) + (F32(a + KEY_SIZE + 64) - F32(a + 64)) * s;
    g_intro_t += frame_dt();
}

/* The Outrider keeps OR_AHEAD nodes ahead of the Falcon at its cruise speed: slower when the Falcon
 * falls behind (down to OR_SLOW, then to a stop: OR_WAIT), faster when it closes in (OR_FAST); Dash calls when it is far
 * behind. OR_PEEL nodes before the switch (the TIEs came in before: ties()) it breaks off: on along
 * the route, faster and faster, climbing steeply (OR_PEEL_UP), gone after OR_PEEL_T. */
void outrider(uint32_t node, float t, int on) {
    uint32_t n = astr_take(OUTRIDER_ASTR, g_or_decoy, &g_or_node);
    if (!n) return;
    uint32_t sw = U32(GALL_RAM + IMG_SWITCH);
    float dt = frame_dt(), fp = (float)node + 1 + t;
    static float fp_last;                                     /* the Falcon's route place a frame ago */
    float fp_rate = fp_last > 0 && g_cruise > 0 ? (fp - fp_last) / g_cruise : 1;   /* its route rate (of the cruise) */
    if (!paused()) fp_last = fp;
    if (paused()) ;                                           /* paused: he holds too */
    else if (g_intro || g_or_f == 0) { g_or_f = fp + OR_AHEAD; g_or_rate = 1; g_or_dz = 0; }
    else if (g_or_pt == 0) {
        float gap = g_or_f - fp, want = gap > OR_AHEAD + OR_LAG ? OR_SLOW * (1 - minf((gap - OR_AHEAD - OR_LAG) / OR_WAIT, 1))
                                      : gap > OR_AHEAD ? 1 - (1 - OR_SLOW) * (gap - OR_AHEAD) / OR_LAG   /* (far back: he waits) */
                                                       : 1 + (OR_FAST - 1) * minf((OR_AHEAD - gap) / (OR_AHEAD - 2), 1);
        if (gap < OR_AHEAD && want < fp_rate) want = fp_rate;    /* closing in: at least the Falcon's own pace (a bend */
        g_or_rate += (want - g_or_rate) * minf(OR_RATE_EASE * dt, 1);   /* cut runs it up to ~1.9 x cruise) */
        g_or_f += g_cruise * g_or_rate;
        if (g_or_f < fp + OR_MIN_GAP) g_or_f = fp + OR_MIN_GAP;  /* and never caught */
        g_lag_quiet -= dt;
        g_lag_t = gap > OR_AHEAD + LAG_GAP ? g_lag_t + dt : 0;
        if (g_lag_t > LAG_SAY && g_lag_quiet <= 0 && U32(GALL_RAM + IMG_LINES)) {
            ((say_fn)SAY)((int16_t)U16(U32(GALL_RAM + IMG_LINES + 4) + 12), 31, LINE_SHOW, 13, "~oKeep up, Lando!");
            g_lag_quiet = LAG_QUIET;
        }
        if (g_or_f >= (float)(sw - OR_PEEL)) g_or_pt = 1e-3f;   /* his stop: away */
    } else {
        g_or_pt += dt;
        g_or_f += g_cruise * (1 + OR_PEEL_ACC * g_or_pt);
    }
    uint32_t stft = player_ship(), ship = stft ? U32(stft + 0xB4) : 0;
    if (!on || g_or_pt > OR_PEEL_T || !valid_ptr(ship) || U32(OR_MESHES[2] + NODE_COUNT) == 0) {
        U16(n + NODE_SHOW) &= 0x00FF;
        return;
    }
    float f = g_or_f;
    if (f > (float)(sw - 3)) f = (float)(sw - 3);               /* the last stage 1 nodes */
    uint32_t k = (uint32_t)f;
    float a[3], b[3], p[3], d[3], u[3], r[3], fr = f - (float)k;
    {                                   /* along a Catmull-Rom spline through the nodes, heading its tangent */
        float c0[3], c3[3];             /* (straight between them, the heading stepped at each: he jerked side */
        route_pos(k > 0 ? k - 1 : 0, c0); route_pos(k, a); route_pos(k + 1, b); route_pos(k + 2, c3);   /* to side) */
        float t2 = fr * fr, t3 = t2 * fr;
        for (int i = 0; i < 3; i++) {
            float q0 = c0[i], q1 = a[i], q2 = b[i], q3 = c3[i];
            p[i] = 0.5f * (2 * q1 + (q2 - q0) * fr + (2 * q0 - 5 * q1 + 4 * q2 - q3) * t2 + (3 * q1 - q0 - 3 * q2 + q3) * t3);
            d[i] = 0.5f * ((q2 - q0) + 2 * (2 * q0 - 5 * q1 + 4 * q2 - q3) * fr + 3 * (3 * q1 - q0 - 3 * q2 + q3) * t2);
        }
    }
    if (!g_intro && g_or_pt == 0 && !paused()) {                /* its height after the Falcon's: as low as the */
        float lo = -FLY_LOW, hi = corridor(k, 3) - OR_R;         /* Falcon may go, up to the corridor's top, at its */
        g_or_dz += (g_ship_off[2] - g_or_dz) * minf(OR_DZ_EASE * frame_dt(), 1);   /* node (frozen in the break-off, */
        if (g_or_dz < lo) g_or_dz = lo;                          /* which starts from there) */
        if (g_or_dz > hi) g_or_dz = hi;
    }
    if (!g_intro) p[2] += g_or_dz + OR_PEEL_UP * g_or_pt * g_or_pt;   /* (the break-off's climb) */
    if (!g_intro) {                                              /* pushed out of the rock as the Falcon is (in the */
        float q[3] = { p[0], p[1], p[2] - SHIP_DROP }, rr[3] = { OR_R, OR_R, OR_R }, nn[3];
        collide(IMG_COLL, q, AX_UNIT, rr, nn);
        p[0] = q[0]; p[1] = q[1]; p[2] = q[2] + SHIP_DROP;      /* break-off too, till the walls are cleared) */
    }
    if (g_or_pt > 0) {                  /* the break-off: heading along the route at its speed, nose up with the climb */
        float v = FLY_V * (1 + OR_PEEL_ACC * g_or_pt), lr = sqrt_f(d[0] * d[0] + d[1] * d[1]);
        if (lr > 1e-3f) { d[0] *= v / lr; d[1] *= v / lr; }
        d[2] = 2 * OR_PEEL_UP * g_or_pt;
    }
    p[2] -= SHIP_DROP;
    if (g_intro)                                                 /* the opening shot's */
        for (int i = 0; i < 3; i++) { p[i] = g_ik[6 + i]; d[i] = g_ik[12 + i]; }
    float l = len3(d);
    if (l < 1e-3f) return;
    for (int i = 0; i < 3; i++) d[i] /= l;
    l = sqrt_f(d[0] * d[0] + d[1] * d[1]);
    if (l < 1e-3f) return;
    r[0] = d[1] / l; r[1] = -d[0] / l; r[2] = 0;                 /* right = forward x up */
    u[0] = r[1] * d[2] - r[2] * d[1]; u[1] = r[2] * d[0] - r[0] * d[2]; u[2] = r[0] * d[1] - r[1] * d[0];
    float k_ship = sqrt_f(F32(ship + NODE_ROT) * F32(ship + NODE_ROT) + F32(ship + NODE_ROT + 4) * F32(ship + NODE_ROT + 4)
                          + F32(ship + NODE_ROT + 8) * F32(ship + NODE_ROT + 8));
    for (int i = 0; i < 3; i++) {            /* model x right, +y forward, z up */
        F32(n + NODE_ROT + 4 * i) = r[i] * k_ship;
        F32(n + NODE_ROT + 12 + 4 * i) = d[i] * k_ship;
        F32(n + NODE_ROT + 24 + 4 * i) = u[i] * k_ship;
        F32(n + NODE_POS + 4 * i) = p[i];
    }
    float want = bank(k, g_or_roll);
    if (g_or_pt > 0) want = want > BANK_MAX ? BANK_MAX : want < -BANK_MAX ? -BANK_MAX : want;   /* no knife edge as it
                                                                 * climbs out of the slits */
    if (!g_intro && !g_said_slit && absf(want) > BANK_MAX && g_fly_on      /* Dash goes on edge into a slit */
        && g_or_f - fp < OR_AHEAD + LAG_GAP && U32(GALL_RAM + IMG_LINES)) {   /* with the Falcon right behind */
        ((say_fn)SAY)((int16_t)U16(U32(GALL_RAM + IMG_LINES + 4) + 12), 31, LINE_SHOW, 13, "~oTight squeeze, Lando.~nMind my paint!");
        g_said_slit = 1;
    }
    if (!g_intro && g_or_pt == 0 && g_or_spin == 0 && absf(g_or_roll) > 1.2f && absf(want) <= BANK_MAX)
        g_or_spin = g_or_roll > 0 ? 2 * PI_F : -2 * PI_F;     /* off the edge: a barrel roll, not back */
    if (g_or_spin != 0) {
        float d = g_or_spin - g_or_roll, step = d * SPIN_EASE;
        g_or_roll += step > SPIN_MAX ? SPIN_MAX : step < -SPIN_MAX ? -SPIN_MAX : step;
        if (absf(d) < 0.05f) { g_or_roll -= g_or_spin; g_or_spin = 0; }
    } else if (!g_intro) g_or_roll += (want - g_or_roll) * (absf(want) > BANK_MAX ? KNIFE_EASE : BANK_EASE);
    node_roll(n, g_or_roll);
    U32(n + NODE_COUNT) = sizeof OR_MESHES / 4;
    U32(n + NODE_LIST) = (uint32_t)OR_MESHES;
    U16(n + NODE_SHOW) = 0xFF03;
}
#define IMG_SLAVE        116        /* Slave I's mesh: part count, part list, box (gallrun/slave_pad.py slave_mesh()) */
#define CINE_KEY         128        /* a key (32 floats): t, eye, look, Falcon (xyz, heading, roll), Slave I (xyz, heading),
                                     * Dash (xyz, heading, pose: 0 none, 1 standing, 2 jetpack), Outrider (xyz, heading, shown, roll),
                                     * the field of view's share (zoom), (unused, -1), camera shake, the Falcon's pitch,
                                     * the Outrider's pitch (nose down +: they climb after Slave I) */
#define IMG_DASH         136        /* Dash standing, on the jetpack: part count, part list, box each (slave_pad.dash_mesh()) */
#define IMG_DASH_K       160        /* float: his node's scale (his vertices are finer than a world unit) */
#define CINE_THR         0.7f       /* the Falcon's throttle as the scene hands over (its last speed: 210) */

/* The scene at the route's end (the user, 2026-10-12: a cinematic story round Slave I's shaft; the keys:
 * slave_pad.cine_keys()): Chor holds at the end node, the Falcon flies on over the shaft and round it, Slave I
 * rises out of the shaft and comes round after it, the camera cuts between shots and ends behind the Falcon as
 * the free flight has it; the radio lines are the image's (LINES, at the end node). No control while it runs. */
#define FLEE_V           300.0f     /* units a second (the Falcon: 300, 390 with A) */
#define FLEE_FAST        360.0f
#define FLEE_NEAR        120.0f
#define FLEE_ACC         120.0f     /* units a second, a second */
#define FLEE_UP          20.0f
float g_lost_t;                     /* how long the Falcon has been ESCAPE_D behind Slave I */
static float g_sl_spd, g_sl_h;      /* the free flight: Slave I's speed, its height over the route back (-1 node: over
                                     * the cliffs, on straight) */
float g_sl_f;                       /* the free flight: Slave I's place on the route back (node) */
float g_cine_t, g_sl[3], g_sl_yaw, g_sl_v[3];          /* Slave I: where, its heading, its speed (world) */
float g_zoom = 1;                   /* the end scene: the field of view's share (a key; < 1 nearer) */
float g_ocn[3];                     /* the Outrider's place (or_friendly()) */
static float g_dash[3], g_dash_yaw, g_ocn_yaw, g_ocn_roll, g_ocn_pitch;   /* the scene's Dash and Outrider */
static float g_sky_top;
/* Slave I's shots in the end scene (the user: its fire seen): slave_pad.bolts() (IMG_BOLTS), drawn by the Outrider's
 * node while the Outrider is not in it: from its guns along its barrels (its nose row, +y, level along its yaw: the guns'
 * mesh lies flat in the model, z -0.5..0.6 over y -0.6..4.9 Gall, and the node stands it upright)
 * for the distance to the Falcon in BOLT_T, on to BOLT_ON x that. */
#define IMG_BOLTS        176
#define BOLT_T           0.35f
#define BOLT_ON          1.6f
#define BOLT_GUN_Y       6.5f       /* (its guns: the barrels' tips on its front face low down, slave_pad.SLAVE_GUNS_OFF: */
#define BOLT_GUN_Z       (-7.5f)    /* the user, 2026-10-19: the shots came from under its tail) */
#define SL_SHOT_ID       11         /* its shot sound: the stock Slave I fire's (0x8004E68C: id, channel, pitch, volume) */
#define SL_SHOT_CH       4
#define SL_SHOT_PITCH    0.25f
#define SL_SHOT_VOL      18000
static float g_bolt_t = -1, g_bolt_from[3], g_bolt_to[3];
static uint32_t g_bolt_mesh[6], g_bolt_list[1];              /* the free flight: the height Slave I levels off at (SKY_TOP over the route's end) */
#define SKY_TOP          3000.0f    /* slave_pad.py SKY_TOP, SKY_TAN, SKY_EASE (flee()) */
#define SKY_TAN          0.4f
#define SKY_EASE         0.5f
static int g_dash_pose, g_ocn_on;

static float cine_k(uint32_t a, float s, int i) {
    return F32(a + 4 * i) + (F32(a + CINE_KEY + 4 * i) - F32(a + 4 * i)) * s;
}

static uint32_t cine_at(float tm, float *s) {
    uint32_t n = U32(GALL_RAM + IMG_CINE), a = U32(GALL_RAM + IMG_CINE + 4), k = 0;
    while (k + 2 < n && F32(a + (k + 1) * CINE_KEY) <= tm) k++;
    a += k * CINE_KEY;
    *s = (tm - F32(a)) / (F32(a + CINE_KEY) - F32(a));
    if (*s > 1) *s = 1;
    if (*s < 0) *s = 0;
    return a;
}

void cine(uint32_t chor, uint32_t node) {
    F32(chor + CHOR_SPEED) = 0;                                  /* Chor holds at the end */
    g_fly_speed = 0;
    static int inside;                                           /* begun in the gunner's inside view (the user: */
    if (!g_cine) {                                               /* the scene came through the turret's window) */
        inside = S16(VIEW_MODE) == CAMERA_INSIDE || U32(CAMERA_INDEX) == CAMERA_INSIDE;
        if (inside) {                                            /* as the view key to the view behind does; the */
            ((setcam_fn)CAM_SWITCH)(CAMERA_GUN); S16(VIEW_MODE) = CAMERA_GUN;   /* ship's nodes shown again (the */
            uint32_t stft = player_ship();   /* game does it only with the guns on, and */
            for (int o = 0xB0; o <= 0xB4; o += 4)                /* its HUD draws the window, elements 20-23, */
                if (stft && valid_ptr(U32(stft + o))) U16(U32(stft + o) + NODE_SHOW) |= 0xFF00;   /* while +0xB4 */
            for (int i = 0; i <= 23; i += i ? 1 : 20) S16(HUD_POS + 4 * i) = -1000;   /* is hidden; 0 the sight; */
        }                                                        /* placed only as they change, not in the scene) */
    }
    run_camera();                                                /* the run's camera (not the gun's) */
    uint32_t n = U32(GALL_RAM + IMG_CINE), k0 = U32(GALL_RAM + IMG_CINE + 4);
    int first = !g_cine;
    if (!g_cine) { g_cine = 1; g_cine_t = 0; g_free_head = route_head((float)(node + 1) + F32(chor + CHOR_PARAM)); }
    float here[3], s;
    for (int i = 0; i < 3; i++) here[i] = F32(chor + 0x50 + 4 * i);
    here[2] -= SHIP_DROP;
    if (g_cine_t >= F32(k0 + (n - 1) * CINE_KEY)) {              /* over: free flight, Slave I after the Falcon */
        uint32_t l = k0 + (n - 1) * CINE_KEY;
        float st = F32(l) - F32(l - CINE_KEY);
        for (int i = 0; i < 3; i++) g_sl_v[i] = st > 0 ? (F32(l + 48 + 4 * i) - F32(l - CINE_KEY + 48 + 4 * i)) / st : 0;
        g_sl_f = F32(l + 112);
        if (g_sl_f >= 1) { float r[3]; route_pos((uint32_t)g_sl_f, r); g_sl_h = g_sl[2] - r[2]; }   /* (~: its node's height) */
        g_sl_spd = st > 0 ? len3(g_sl_v) : FLEE_V;
        g_sky_top = F32(chor + 0x58) + SKY_TOP;
        g_cine = 2; g_free = 0; g_fly_thr = CINE_THR; g_gun_ease = 1;
        return;
    }
    uint32_t a = cine_at(g_cine_t, &s);
    static carry_t carry;                                        /* from the view on screen as the scene began */
    static float ship_c[3];                                      /* (stage 2's, the gun's: it jumped, the user), eased */
    float f[3], fal[3];                                          /* out over ~2 s (CINE_CARRY a frame); from the inside */
    for (int i = 0; i < 6; i++) g_ik[i] = cine_k(a, s, 1 + i);   /* view a cut; the Falcon from its flown place the same */
    for (int i = 0; i < 3; i++) f[i] = g_ik[3 + i] - g_ik[i];    /* way, the look on it while they ease */
    if (first) {
        carry_from(&carry, g_ik, f);
        if (inside) for (int i = 0; i < 6; i++) carry.d[i] = 0;
        for (int i = 0; i < 3; i++) ship_c[i] = g_ship_off[i] - (cine_k(a, s, 7 + i) - here[i]);
    }
    for (int i = 0; i < 3; i++) {
        g_ship_off[i] = cine_k(a, s, 7 + i) - here[i] + ship_c[i] * carry.share;
        fal[i] = here[i] + g_ship_off[i];
    }
    carry_on(&carry, g_ik, f, fal);
    for (int i = 0; i < 3; i++) g_ik[3 + i] = g_ik[i] + f[i];
    if (first && valid_ptr(U32(CAMERA_ENTRIES))) {               /* the scene's view on its first frame: the camera entry */
        for (int i = 0; i < 3; i++) f[i] = g_ik[3 + i] - g_ik[i];   /* too (it takes the Trak's view in part: ~3 frames */
        view_set(U32(CAMERA_ENTRIES) + 3 * 0x80 + 0x14 - TRAK_MATRIX, g_ik, f);   /* from the stale gun view; one */
        for (uint32_t i = 0, t = U32(CLASS_TRAK + 0x10); i < U32(CLASS_TRAK + 8) && valid_ptr(t); i++, t += U32(CLASS_TRAK + 0xC))
            if (U32(t + TRAK_TARGET) == chor) view_set(t, g_ik, f);   /* frame of the Trak's own: every view) */
    }
    carry_decay(&carry);
    float yo = cine_k(a, s, 10) - g_free_head;
    yo = wrap_pi(yo);
    g_ship_yaw = -yo; g_ship_roll = cine_k(a, s, 11); g_ship_pitch = cine_k(a, s, 30);
    for (int i = 0; i < 3; i++) {
        g_sl[i] = cine_k(a, s, 12 + i);
        g_dash[i] = cine_k(a, s, 16 + i);
        g_ocn[i] = cine_k(a, s, 21 + i);
    }
    g_sl_yaw = cine_k(a, s, 15);
    g_dash_yaw = cine_k(a, s, 19); g_dash_pose = (int)(F32(a + 80) + 0.5f);
    g_ocn_yaw = cine_k(a, s, 24); g_ocn_on = F32(a + 100) > 0.5f; g_ocn_roll = cine_k(a, s, 26); g_ocn_pitch = cine_k(a, s, 31);
    g_zoom = cine_k(a, s, 27);
    if (F32(a + 116) > g_shake) g_shake = F32(a + 116);       /* Slave I fires */
    {                                                            /* its shots: from its guns along its barrels (or_cine() */
        static float prev;                                       /* draws them) */
        float sh = F32(a + 116);
        if (sh > 0 && prev <= 0) {
            float c = cos_r(g_sl_yaw), sn = sin_r(g_sl_yaw), d[3];
            for (int i = 0; i < 3; i++) {
                g_bolt_from[i] = g_sl[i] + (i == 0 ? c * BOLT_GUN_Y : i == 1 ? sn * BOLT_GUN_Y : BOLT_GUN_Z);
                d[i] = cine_k(a, s, 7 + i) - g_bolt_from[i];
            }
            float l = len3(d);
            g_bolt_to[0] = g_bolt_from[0] + c * l; g_bolt_to[1] = g_bolt_from[1] + sn * l; g_bolt_to[2] = g_bolt_from[2];
            g_bolt_t = 0;
            ((sfx_placed_fn)SFX_PLACED)(SL_SHOT_ID, SL_SHOT_CH, fbits(SL_SHOT_PITCH), SL_SHOT_VOL, g_bolt_from, 0);   /* its
                                     * shot sound, once a shot */
        }
        prev = sh;
        if (g_bolt_t >= 0 && !paused()) g_bolt_t += frame_dt();
        if (g_bolt_t > BOLT_T * BOLT_ON) g_bolt_t = -1;
    }
    g_fly_on = 0;
    if (!paused()) g_cine_t += frame_dt();
    if (g_hang_t < 0 && g_cine_t >= HANG_CINE_T) hang_go();     /* the hangar TIEs go as the Falcon swings round the pad */
}

/* Slave I after the scene runs (the user: the Falcon chases it, up into space; straight up it looked like a rocket):
 * down the canyon along the route back, its bends all the way, climbing SKY_TAN a unit, levelling off at SKY_TOP over
 * the route's end (SKY_EASE) (slave_pad.py SKY: the same law); at FLEE_V, faster when the Falcon is near (FLEE_NEAR),
 * eased (FLEE_ACC); it does not wait (the user: like stage 1, keep up with it): ESCAPE_D behind for ESCAPE_T it got
 * away (free_fly() puts the Falcon back on its tail, Lando says so). */
#define ESCAPE_D         1600.0f


int g_rail;
#define RAIL_GAP         200.0f     /* on the rail Slave I holds this far ahead (slave_pad.py CINE_GAP): it flew at its */
#define RAIL_GAP_K       1.2f       /* own pace, from ~70 ahead (the Outrider on the Falcon) out to 440 and on (the user: */
#define RAIL_GAP_MORE    150.0f     /* less of a gap); the gap's error closed this share a second, at most this faster */
#define RAIL_STEP_U      54.0f      /* the rail's nodes this far apart (slave_pad.py RAIL_STEP) */

static float g_rail_gap = RAIL_GAP;  /* (story(): closing in) */

static float g_sl_rf;                /* flee(): Slave I's place on the rail (route node + fraction), or_cine()'s */
void flee(void) {
    if (paused() || g_sl_jump >= 0) return;                    /* (gone to lightspeed: it holds, not drawn) */
    float dt = frame_dt(), d = 0, want, old[3], ship[3];
    uint32_t stft = player_ship();
    for (int i = 0; i < 3; i++) ship[i] = g_rail && stft ? F32(stft + 0x50 + 4 * i) : g_fly_pos[i];   /* (on the rail
                                                                  * Chor carries it: g_fly_pos is not the ship) */
    for (int i = 0; i < 3; i++) d += (g_sl[i] - ship[i]) * (g_sl[i] - ship[i]);
    d = sqrt_f(d);
    want = d < FLEE_NEAR ? FLEE_FAST : FLEE_V;                   /* (it does not wait: the user, keep up with it) */
    static float gap_now;
    if (g_rail) {                                                /* on the rail: ahead of the Falcon on the rail itself */
        uint32_t chor = U32(CLASS_CHOR + 0x10);                  /* (the user: in space no canyon bends; it flew the */
        float f0 = (float)U32(chor + CHOR_NODE) + 1 + F32(chor + CHOR_PARAM);   /* route back below, off the rail), */
        if (!g_sl_on_rail) {                                     /* the gap eased to g_rail_gap from where the scene */
            float best = 1e12f, p[3];                            /* left it: the rail's node nearest it (no jump) */
            gap_now = RAIL_GAP;
            for (uint32_t k = (uint32_t)f0; k < (uint32_t)f0 + 30; k++) {
                route_pos(k, p);
                float q = (p[0] - g_sl[0]) * (p[0] - g_sl[0]) + (p[1] - g_sl[1]) * (p[1] - g_sl[1]) + (p[2] - g_sl[2]) * (p[2] - g_sl[2]);
                if (q < best) { best = q; gap_now = ((float)k - f0) * RAIL_STEP_U; }
            }
            if (gap_now < 40) gap_now = 40;
        }
        g_sl_on_rail = 1;
        float e = g_rail_gap - gap_now, m = RAIL_GAP_MORE * dt;
        gap_now += e > m ? m : e < -m ? -m : e;
        float f = f0 + gap_now / RAIL_STEP_U;
        g_sl_rf = f;
        float last = (float)(U32(GALL_RAM + IMG_RAIL) + U32(GALL_RAM + IMG_RAIL_N) - 2);
        if (f > last) f = last;
        uint32_t k = (uint32_t)f;
        float a[3], b[3], fr = f - (float)k;
        route_pos(k, a); route_pos(k + 1, b);
        for (int i = 0; i < 3; i++) old[i] = g_sl[i];
        for (int i = 0; i < 3; i++) g_sl[i] = a[i] + (b[i] - a[i]) * fr;
        g_sl_yaw = atan2_r(b[1] - a[1], b[0] - a[0]);
        if (dt > 0) for (int i = 0; i < 3; i++) g_sl_v[i] = (g_sl[i] - old[i]) / dt;
        g_sl_spd = sqrt_f(g_sl_v[0] * g_sl_v[0] + g_sl_v[1] * g_sl_v[1]);
        g_lost_t = 0;
        return;
    }
    g_sl_on_rail = 0;
    float m = FLEE_ACC * dt;
    g_sl_spd += want - g_sl_spd > m ? m : want - g_sl_spd < -m ? -m : want - g_sl_spd;
    g_lost_t = d > ESCAPE_D ? g_lost_t + dt : 0;                 /* too far behind too long: it got away (free_fly) */
    for (int i = 0; i < 3; i++) old[i] = g_sl[i];
    if (g_sl_f >= 1) {                                           /* down the canyon along the route back, climbing */
        uint32_t k = (uint32_t)g_sl_f;
        float a[3], b[3];
        route_pos(k, a); route_pos(k + 1, b);
        float l = sqrt_f((b[0] - a[0]) * (b[0] - a[0]) + (b[1] - a[1]) * (b[1] - a[1]));
        if (l > 1e-3f) g_sl_f -= g_sl_spd * dt / l;
        if (g_sl_f < 1) g_sl_f = 1;
        float lim = (g_sky_top - (a[2] + (b[2] - a[2]) * (g_sl_f - (float)k)) - g_sl_h) * SKY_EASE;
        g_sl_h += minf(g_sl_spd * SKY_TAN, lim) * dt;              /* climbing, levelling off at SKY_TOP */
        k = (uint32_t)g_sl_f;
        float f = g_sl_f - (float)k;
        route_pos(k, a); route_pos(k + 1, b);
        for (int i = 0; i < 3; i++) g_sl[i] = a[i] + (b[i] - a[i]) * f + (i == 2 ? g_sl_h : 0);
        float want_yaw = atan2_r(a[1] - b[1], a[0] - b[0]), dy = want_yaw - g_sl_yaw;   /* nose along its way (back) */
        dy = wrap_pi(dy);
        g_sl_yaw += dy * minf(4.0f * dt, 1);
    } else {                                                     /* (off the route at the scene's end: on straight) */
        float vz = g_sl_spd * SKY_TAN, lim = (g_sky_top - g_sl[2]) * SKY_EASE;
        if (vz > lim) vz = lim;
        g_sl[0] += cos_r(g_sl_yaw) * g_sl_spd * dt; g_sl[1] += sin_r(g_sl_yaw) * g_sl_spd * dt; g_sl[2] += vz * dt;
    }
    if (dt > 0) for (int i = 0; i < 3; i++) g_sl_v[i] = (g_sl[i] - old[i]) / dt;
}

/* Slave I is drawn by the fourth rock's node (decoy trick, as the Outrider): its own mesh (IMG_SLAVE: world
 * units, nose +y, up +z), turned to its heading, in stage 2 only. Before the scene it stands on the gantry
 * (the scene's first key). */
static uint32_t g_sl_decoy[0x48 / 4], g_sl_node, g_sl_mesh[6], g_sl_list[1];

/* A ship's jump to lightspeed (the user, 2026-10-13: Dash leaves, then Slave I gets away), t seconds into it (-1:
 * none): drawn stretched along its nose and shot ahead, gone after JUMP_T (0). */
#define JUMP_STRETCH     14.0f
#define JUMP_GO          2600.0f
static int jump_pose(float t, float *ahead, float *stretch) {
    *ahead = 0; *stretch = 1;
    if (t < 0) return 1;
    if (t > JUMP_T) return 0;
    float u = t / JUMP_T; u *= u;
    *ahead = JUMP_GO * u; *stretch = 1 + JUMP_STRETCH * u;
    return 1;
}

/* The white trail of a jump (the user, 2026-10-17): slave_pad.trail() (IMG_TRAIL: along +y TRAIL_UNIT long,
 * TRAIL_MESH_W wide at its head) drawn by Dash's node (idle out of the end scene), from where the ship's jump began (its
 * tail pulled after it, the user: not under the camera) to where it is drawn; once it has gone the tail runs into its
 * head over TRAIL_FADE, narrowing. Slave I's or else the
 * Outrider's (its g_ocn is last frame's: or_cine() runs after dash(), inside its stretched hull). 1: drawn. */
#define IMG_TRAIL        276        /* part count, part list, box */
#define TRAIL_UNIT       100.0f     /* (slave_pad.TRAIL_LEN, TRAIL_W) */
#define TRAIL_MESH_W     16.0f
#define TRAIL_WIDTH      8.0f       /* world units at its head */
#define TRAIL_FADE       0.7f
#define TRAIL_ANGLE      0.012f     /* wider when far: its head at least this x its distance from the camera (a hair) */
#define TRAIL_MAX_LEN    3000.0f    /* its tail pulled after the ship: at most this long (into the ship as it fades; */
                                    /* 1500: all of it far ahead, seen end on: a dot) */
#define TRAIL_CAM_GAP    150.0f     /* and at least this far on past the camera along it */
static float g_tr_from[3], g_tr_to[3];
float g_tr_s, g_tr_sc, g_tr_w;      /* its tail and the eye along it, its width (probes) */
static int g_tr_who;                /* whose jump it is drawn for (1 the Outrider, 2 Slave I, 0 none) */
static uint32_t g_tr_mesh[6], g_tr_list[1];
static int trail(uint32_t n) {
    int who = g_fj_t >= 0 ? 3 : g_sl_jump >= 0 ? 2 : g_or_jump >= 0 ? 1 : 0;   /* (3: the Falcon's, fly_jump(): */
    if (!who) { g_tr_who = 0; return 0; }                                      /* from its start to the ship) */
    float t = who == 3 ? g_fj_t : who == 2 ? g_sl_jump : g_or_jump, yaw = who == 2 ? g_sl_yaw : g_ocn_yaw, go, st;
    float jt = who == 3 ? FJ_T : JUMP_T;
    const float *p = who == 3 ? g_fj_from : who == 2 ? g_sl : g_ocn;
    uint32_t fj = who == 3 ? player_ship() : 0;
    if (g_cine != 2 || !U32(GALL_RAM + IMG_TRAIL) || t > jt + TRAIL_FADE || (who == 3 && !fj)) return 0;
    if (g_tr_who != who) { g_tr_who = who; for (int i = 0; i < 3; i++) g_tr_from[i] = g_tr_to[i] = p[i]; }
    if (who == 3) { if (t <= jt) for (int i = 0; i < 3; i++) g_tr_to[i] = F32(fj + 0x50 + 4 * i); }
    else if (jump_pose(t, &go, &st))
        for (int i = 0; i < 3; i++) g_tr_to[i] = p[i] + (i == 0 ? cos_r(yaw) : i == 1 ? sin_r(yaw) : 0) * go;
    float d[3], x[3], z[3], eye[3], fade = t <= jt ? 1 : 1 - (t - jt) / TRAIL_FADE;
    for (int i = 0; i < 3; i++) d[i] = g_tr_to[i] - g_tr_from[i];
    float l = len3(d), h = sqrt_f(d[0] * d[0] + d[1] * d[1]);
    if (l < 1 || h < 1e-3f) return 0;
    for (int i = 0; i < 3; i++) d[i] /= l;
    h /= l;
    uint32_t cam = U32(ACTIVE_CAMERA);                           /* (the eye: +0x44) */
    int seen = valid_ptr(cam);
    float sc = -1e9f, s = l - TRAIL_MAX_LEN * fade, dist = 0;
    if (seen) {
        sc = 0;
        for (int i = 0; i < 3; i++) { eye[i] = F32(cam + 0x44 + 4 * i); sc += (eye[i] - g_tr_from[i]) * d[i]; }
    }
    if (s < sc + TRAIL_CAM_GAP) s = sc + TRAIL_CAM_GAP;          /* (not past the camera: it ran under it, the user) */
    if (s < 0) s = 0;
    g_tr_s = s; g_tr_sc = sc;
    if (s >= l - 1) return 0;
    if (seen) {                                                  /* the eye to its head (its nearest point: a hair */
        for (int i = 0; i < 3; i++) { float e = g_tr_to[i] - eye[i]; dist += e * e; }   /* seen far off) */
        dist = sqrt_f(dist);
    }
    float w = (TRAIL_ANGLE * dist > TRAIL_WIDTH ? TRAIL_ANGLE * dist : TRAIL_WIDTH) * fade / TRAIL_MESH_W;
    g_tr_w = w * TRAIL_MESH_W;
    x[0] = d[1] / h; x[1] = -d[0] / h; x[2] = 0;                 /* (along it +y, right +x, up +z) */
    z[0] = x[1] * d[2] - x[2] * d[1]; z[1] = x[2] * d[0] - x[0] * d[2]; z[2] = x[0] * d[1] - x[1] * d[0];
    for (int i = 0; i < 3; i++) {
        F32(n + NODE_ROT + 4 * i) = x[i] * w; F32(n + NODE_ROT + 12 + 4 * i) = d[i] * (l - s) / TRAIL_UNIT;
        F32(n + NODE_ROT + 24 + 4 * i) = z[i] * w; F32(n + NODE_POS + 4 * i) = g_tr_from[i] + d[i] * s;
    }
    g_tr_mesh[0] = MESH_W0; g_tr_mesh[1] = 0; g_tr_mesh[2] = 0;
    for (int i = 0; i < 3; i++) g_tr_mesh[3 + i] = U32(GALL_RAM + IMG_TRAIL + 4 * i);
    g_tr_list[0] = (uint32_t)g_tr_mesh;
    U32(n + NODE_COUNT) = 1; U32(n + NODE_LIST) = (uint32_t)g_tr_list; U16(n + NODE_SHOW) = 0xFF03;
    return 1;
}

void slave(uint32_t node) {
    uint32_t n = astr_take(SLAVE_ASTR, g_sl_decoy, &g_sl_node);
    if (!n) return;
    if (!U32(GALL_RAM + IMG_SLAVE) || !U32(GALL_RAM + IMG_CINE) || node < U32(GALL_RAM + IMG_SWITCH)) {
        U32(n + NODE_COUNT) = 0; return;
    }
    if (!g_cine) {
        uint32_t k0 = U32(GALL_RAM + IMG_CINE + 4);
        for (int i = 0; i < 3; i++) g_sl[i] = F32(k0 + 48 + 4 * i);
        g_sl_yaw = F32(k0 + 60);
    }
    float c = cos_r(g_sl_yaw), sn = sin_r(g_sl_yaw), go, st;
    if (!jump_pose(g_sl_jump, &go, &st)) { U32(n + NODE_COUNT) = 0; return; }   /* (gone to lightspeed) */
    float rot[9] = { sn, -c, 0, c * st, sn * st, 0, 0, 0, 1 };  /* rows: its x (right), y (nose), z (up) in the world */
    for (int i = 0; i < 9; i++) F32(n + NODE_ROT + 4 * i) = rot[i];
    for (int i = 0; i < 3; i++) F32(n + NODE_POS + 4 * i) = g_sl[i] + (i == 0 ? c : i == 1 ? sn : 0) * go;
    g_sl_mesh[0] = MESH_W0; g_sl_mesh[1] = 0; g_sl_mesh[2] = 0;
    for (int i = 0; i < 3; i++) g_sl_mesh[3 + i] = U32(GALL_RAM + IMG_SLAVE + 4 * i);
    g_sl_list[0] = (uint32_t)g_sl_mesh;
    U32(n + NODE_COUNT) = 1;
    U32(n + NODE_LIST) = (uint32_t)g_sl_list;
    U16(n + NODE_SHOW) = 0xFF03;
}

/* The Falcon's engine glow bent round its stern (the user: a flat strip; space.py glow_bent(), IMG_GLOW: three
 * copies of the Outrider's glow quad): the pulsing glow node (Stft +0xB8) draws it (falcon.c places and scales it). */
#define IMG_GLOW         240        /* part count, part list, box */
#define STFT_GLOW        0xB8
static uint32_t g_gl_mesh[6], g_gl_list[1];
void glow(void) {
    if (!U32(GALL_RAM + IMG_GLOW)) return;
    uint32_t stft = player_ship(), n = stft ? U32(stft + STFT_GLOW) : 0;
    if (!valid_ptr(n) || U32(n) >> 28 != 0xD) return;
    g_gl_mesh[0] = MESH_W0; g_gl_mesh[1] = 0; g_gl_mesh[2] = 0;
    for (int i = 0; i < 3; i++) g_gl_mesh[3 + i] = U32(GALL_RAM + IMG_GLOW + 4 * i);
    g_gl_list[0] = (uint32_t)g_gl_mesh;
    U32(n + NODE_COUNT) = 1; U32(n + NODE_LIST) = (uint32_t)g_gl_list;
}

/* Dash in the end scene: the fifth rock's node (decoy trick) holds his standing or his jetpack mesh
 * (IMG_DASH: his facing +y, finer than world units: the node scales by IMG_DASH_K), turned to his heading. */
static uint32_t g_dh_decoy[0x48 / 4], g_dh_node, g_dh_mesh[6], g_dh_list[1];

void dash(void) {
    uint32_t n = astr_take(DASH_ASTR, g_dh_decoy, &g_dh_node);
    if (!n) return;
    if (g_cine != 1 || g_dash_pose < 1 || g_dash_pose > 2 || !U32(GALL_RAM + IMG_DASH)) { if (!trail(n)) U32(n + NODE_COUNT) = 0; return; }
    float k = F32(GALL_RAM + IMG_DASH_K), c = cos_r(g_dash_yaw), sn = sin_r(g_dash_yaw);
    float rot[9] = { sn * k, -c * k, 0, c * k, sn * k, 0, 0, 0, k };
    for (int i = 0; i < 9; i++) F32(n + NODE_ROT + 4 * i) = rot[i];
    for (int i = 0; i < 3; i++) F32(n + NODE_POS + 4 * i) = g_dash[i];
    uint32_t h = GALL_RAM + IMG_DASH + 12 * (g_dash_pose - 1);
    g_dh_mesh[0] = MESH_W0; g_dh_mesh[1] = 0; g_dh_mesh[2] = 0;
    for (int i = 0; i < 3; i++) g_dh_mesh[3 + i] = U32(h + 4 * i);
    g_dh_list[0] = (uint32_t)g_dh_mesh;
    U32(n + NODE_COUNT) = 1;
    U32(n + NODE_LIST) = (uint32_t)g_dh_list;
    U16(n + NODE_SHOW) = 0xFF03;
}

/* The Outrider in the end scene (Leebo comes for Dash): the first rock's node, as outrider() draws it in
 * stage 1 (its own meshes, the player ship's scale), at the scene's place, heading and bank. After the scene it goes
 * on after Slave I (the user: it chases it too): ORC_BACK behind it along its way, ORC_SIDE to its right, ORC_UP over
 * FLEE_UP, along the route (as the scene's last key leaves it: slave_pad.py or_chase()). */
#define ORC_BACK          80.0f      /* (135 with the Falcon 200 behind it: on top of the Falcon, the user) */
#define ORC_SIDE          45.0f
#define ORC_UP            (-6.0f)

void or_cine(void) {
    if (!g_ocn_on && g_cine == 1 && g_bolt_t >= 0 && U32(GALL_RAM + IMG_BOLTS)) {   /* Slave I's shots */
        uint32_t n = astr_take(OUTRIDER_ASTR, g_or_decoy, &g_or_node);
        if (!n) return;
        float d[3], x[3], z[3], l = 0, u = g_bolt_t / BOLT_T;
        for (int i = 0; i < 3; i++) { d[i] = g_bolt_to[i] - g_bolt_from[i]; l += d[i] * d[i]; }
        l = sqrt_f(l); if (l < 1e-3f) return;
        for (int i = 0; i < 3; i++) d[i] /= l;
        float h = sqrt_f(d[0] * d[0] + d[1] * d[1]); if (h < 1e-3f) h = 1e-3f;
        x[0] = d[1] / h; x[1] = -d[0] / h; x[2] = 0;             /* (along it +y, right +x, up +z) */
        z[0] = x[1] * d[2] - x[2] * d[1]; z[1] = x[2] * d[0] - x[0] * d[2]; z[2] = x[0] * d[1] - x[1] * d[0];
        for (int i = 0; i < 3; i++) {
            F32(n + NODE_ROT + 4 * i) = x[i]; F32(n + NODE_ROT + 12 + 4 * i) = d[i]; F32(n + NODE_ROT + 24 + 4 * i) = z[i];
            F32(n + NODE_POS + 4 * i) = g_bolt_from[i] + d[i] * l * u;
        }
        g_bolt_mesh[0] = MESH_W0; g_bolt_mesh[1] = 0; g_bolt_mesh[2] = 0;
        for (int i = 0; i < 3; i++) g_bolt_mesh[3 + i] = U32(GALL_RAM + IMG_BOLTS + 4 * i);
        g_bolt_list[0] = (uint32_t)g_bolt_mesh;
        U32(n + NODE_COUNT) = 1; U32(n + NODE_LIST) = (uint32_t)g_bolt_list; U16(n + NODE_SHOW) = 0xFF03;
        return;
    }
    if (!g_ocn_on || (g_cine != 1 && g_cine != 2)) return;
    if (g_cine == 2 && g_rail && g_sl_on_rail) {                 /* on the rail itself ORC_BACK behind Slave I (the user,
                                                                  * 2026-10-18: it shook; set back along Slave I's speed of
                                                                  * a frame, it jumped onto it when Chor had not moved) */
        float f = g_sl_rf - ORC_BACK / RAIL_STEP_U, first = (float)U32(GALL_RAM + IMG_RAIL);
        if (f < first) f = first;
        uint32_t k = (uint32_t)f;
        float a[3], b[3], fr = f - (float)k, d[3];
        route_pos(k, a); route_pos(k + 1, b);
        for (int i = 0; i < 3; i++) { g_ocn[i] = a[i] + (b[i] - a[i]) * fr; d[i] = b[i] - a[i]; }
        g_ocn_yaw = atan2_r(d[1], d[0]);
        float c = cos_r(g_ocn_yaw), sn = sin_r(g_ocn_yaw);
        g_ocn[0] += sn * ORC_SIDE; g_ocn[1] -= c * ORC_SIDE; g_ocn[2] += ORC_UP;
        g_ocn_roll = 0; g_ocn_pitch = -atan2_r(d[2], sqrt_f(d[0] * d[0] + d[1] * d[1]));
    } else if (g_cine == 2) {                                    /* behind Slave I along its way (its last way while */
        static float w[3] = { 1, 0, 0 };                         /* it stands a frame) */
        float l = len3(g_sl_v);
        if (l > 1e-3f) for (int i = 0; i < 3; i++) w[i] = g_sl_v[i] / l;
        float c = cos_r(g_sl_yaw), sn = sin_r(g_sl_yaw);
        for (int i = 0; i < 3; i++) g_ocn[i] = g_sl[i] - w[i] * ORC_BACK;
        g_ocn[0] += sn * ORC_SIDE; g_ocn[1] -= c * ORC_SIDE; g_ocn[2] += ORC_UP;
        g_ocn_yaw = g_sl_yaw; g_ocn_roll = 0; g_ocn_pitch = -atan2_r(w[2], sqrt_f(w[0] * w[0] + w[1] * w[1]));
    }
    uint32_t n = astr_take(OUTRIDER_ASTR, g_or_decoy, &g_or_node);
    uint32_t stft = player_ship(), ship = stft ? U32(stft + 0xB4) : 0;
    if (!n || !valid_ptr(ship) || U32(OR_MESHES[2] + NODE_COUNT) == 0) return;
    float k = sqrt_f(F32(ship + NODE_ROT) * F32(ship + NODE_ROT) + F32(ship + NODE_ROT + 4) * F32(ship + NODE_ROT + 4)
                     + F32(ship + NODE_ROT + 8) * F32(ship + NODE_ROT + 8));
    float c = cos_r(g_ocn_yaw), sn = sin_r(g_ocn_yaw), r[3] = { sn, -c, 0 }, d[3] = { c, sn, 0 }, u[3] = { 0, 0, 1 }, go, st;
    if (!jump_pose(g_or_jump, &go, &st)) { U16(n + NODE_SHOW) &= 0x00FF; return; }   /* (Dash gone to lightspeed) */
    for (int i = 0; i < 3; i++) {
        F32(n + NODE_ROT + 4 * i) = r[i] * k;
        F32(n + NODE_ROT + 12 + 4 * i) = d[i] * k * st;
        F32(n + NODE_ROT + 24 + 4 * i) = u[i] * k;
        F32(n + NODE_POS + 4 * i) = g_ocn[i] + d[i] * go;
    }
    node_roll(n, g_ocn_roll);
    if (g_ocn_pitch != 0) node_turn(n, g_ocn_pitch, 12, 24);
    U32(n + NODE_COUNT) = sizeof OR_MESHES / 4;
    U32(n + NODE_LIST) = (uint32_t)OR_MESHES;
    U16(n + NODE_SHOW) = 0xFF03;
}

/* The chase after the scene (the user, 2026-10-13: as stage 2, the camera behind the Falcon, TIEs attack, the player
 * shoots back): the route goes on along Slave I's way (IMG_RAIL: slave_pad.cine_keys() rail, from where the scene
 * leaves the Falcon); Chor is put on its first node and carries the Falcon (fly(): on the route, the gunner) till
 * RAIL_OFF nodes before its end, then free flight. Slave I flies ahead (flee(): at Chor's pace). */

void rail_start(uint32_t chor, uint32_t r0) {
    for (int i = 0; i < 4; i++) U32(chor + CHOR_NODE + 4 * i) = r0 - 1 + i;   /* (the ship is between the 2nd, 3rd) */
    F32(chor + CHOR_PARAM) = 0; F32(chor + CHOR_SPEED) = SPEED;
    g_ship_off[0] = g_ship_off[1] = g_ship_off[2] = 0; g_ship_yaw = g_ship_pitch = 0;
    g_fly_on = 0; g_rail = 1;
    uint32_t ent = U32(CAMERA_ENTRIES);                          /* the gun's camera back (run_camera() had it off: */
    if (valid_ptr(ent)) U32(ent + CAMERA_GUN * 0x80) = 1;       /* firing kept the view fixed, the user) */
}

/* Slave I carries Han (the user, 2026-10-14): it has SL_HP health, shown as a boss's is ("Slave 1 nn%": the game's
 * boss bar, HUD elements 0x38 and 0x39 at (160, 190) and (160, 200), fading; the game's own runs on foot only). The
 * gunner's bolts that pass within SL_HIT of it (our test: the game's hits only the TIEs) take SL_DAMAGE off, show the
 * bar SL_BAR seconds and Leia says not to (the image's last line, not again for NO_SHOOT_T). Down to 0: Leia's held
 * line, then the chase starts again from the rail's start (rail_restart()). */
#define NO_SHOOT_T       4.0f
#define SL_HIT           30.0f
#define SL_SPAN          130.0f
#define SL_DAMAGE        0.01f
#define SL_BAR           3.0f
float g_bar_t;                      /* (not static: probes) */
void boss_bar(float dt) {
    static char pct[16];
    static int shown;                                            /* (hidden only after we showed it: the ids may be */
    if (g_bar_t <= 0) {                                          /* the level's own otherwise) */
        if (shown) { ((hud3_fn)HUD_PLACE)(HUD_BOSS_NAME, -1000, -1000); ((hud3_fn)HUD_PLACE)(HUD_BOSS_PCT, -1000, -1000); }
        shown = 0;
        return;
    }
    shown = 1;
    int a = (int)(255 * (g_bar_t > 1 ? 1 : g_bar_t)), p = (int)(g_sl_hp * 100 + 0.5f);
    if (p <= 0 && g_sl_hp > 0) p = 1;
    ((sprintf_fn)SPRINTF)(pct, "~f3~o~c%d%%", p);              /* (the game's boss format, 0x800EB598: font 3 has %) */
    ((hudt_fn)HUD_TEXT)(HUD_BOSS_NAME, "~o~cSlave 1"); ((hudt_fn)HUD_TEXT)(HUD_BOSS_PCT, pct);
    ((hud5_fn)HUD_COLOUR)(HUD_BOSS_NAME, 255, 255, 0, a); ((hud5_fn)HUD_COLOUR)(HUD_BOSS_PCT, 255, 255, 0, a);   /* (yellow: the
                                                                  * ship levels' target bar, the space level's Star Destroyer) */
    ((hud3_fn)HUD_PLACE)(HUD_BOSS_NAME, 160, 190); ((hud3_fn)HUD_PLACE)(HUD_BOSS_PCT, 160, 200);
    if (!S16(MSG_HOLD)) g_bar_t -= dt;
}
uint32_t blst(void) {                                   /* the bolts' class record (0: none yet) */
    static uint32_t rec;
    if (!rec) for (uint32_t a = 0x80112808; a < 0x80113400; a += 0x30) if (U32(a) == TAG_BLST) { rec = a; break; }
    return rec && valid_ptr(U32(rec + 0x10)) && U32(CLASS_CHOR + 8) ? rec : 0;
}
int bolt_hit(uint32_t b, const float *p, float r) {      /* its last SL_SPAN of way within r of p: gone */
    float w[3], a = 0, q = 0;
    for (int j = 0; j < 3; j++) { w[j] = p[j] - F32(b + 0x50 + 4 * j); a += w[j] * F32(b + 0xA0 + 4 * j); }
    if (a > 0 || a < -SL_SPAN) return 0;
    for (int j = 0; j < 3; j++) { float e = w[j] - a * F32(b + 0xA0 + 4 * j); q += e * e; }
    if (q > r * r) return 0;
    F32(b + 0x58) = F32(b + 0x9C) = -30000.0f;                   /* (the bolt gone, its last place too) */
    for (int j = 0; j < 2; j++) F32(b + 0x94 + 4 * j) = F32(b + 0x50 + 4 * j);
    return 1;
}
void no_shoot(void) {
    static float wait;
    float dt = frame_dt();
    if (paused()) return;
    if (wait > 0) wait -= dt;
    if (g_sl_lost || g_sl_jump >= 0) return;
    uint32_t rec = blst();
    if (!rec) return;
    uint32_t chor = U32(CLASS_CHOR + 0x10), n = U32(rec + 8), sz = U32(rec + 0xC);
    for (uint32_t i = 0; i < n && i < 64; i++) {
        uint32_t b = U32(rec + 0x10) + i * sz;
        if (U32(b + 0x64) != chor || !bolt_hit(b, g_sl, SL_HIT)) continue;
        static uint32_t last;
        if (g_ov_frames - last < SL_COOL) continue;
        last = g_ov_frames;
        g_sl_hp -= SL_DAMAGE; g_bar_t = SL_BAR;
        if (g_sl_hp <= 0.001f) {
            g_sl_hp = 0; g_sl_lost = 1;
            ((say_fn)SAY)(face(FACE_LEIA), 31, LINE_SHOW, 13, "~h~oNo...! Han was~non board!");
            return;
        }
        if (wait <= 0) {
            uint32_t e = U32(GALL_RAM + IMG_LINES + 4) + (U32(GALL_RAM + IMG_LINES) - 1) * LINE_SIZE;
            ((say_fn)SAY)(face((int16_t)U16(e + 12)), 31, LINE_SHOW, 13, (const char *)U32(e + 8));
            wait = NO_SHOOT_T;
        }
    }
}

/* In space on the rail (the user, 2026-10-13): by the Star Destroyer's battle Dash says sorry and jumps to
 * lightspeed (a shot of ours on him), the Falcon closes in on Slave I, which jumps to lightspeed too (a shot from
 * behind the Falcon); then the rail's end and free flight among the TIEs. By the rail's node (from IMG_RAIL);
 * the lines are the image's last ones (LINES 'never': said here). The shots: the camera at g_ik as the end
 * scene's (trak_draw, trak_update), the gun's camera back after them. */
#define IMG_STORY        252        /* rail nodes (space.star_destroyer()): Dash quits (the Star Destroyer looms ahead), the
                                    * Falcon closes in (RAIL_GAP -> RAIL_GAP_NEAR over CLOSE_T), Slave I jumps (past its
                                    * stern: the Falcon flew by its flank after it, the user) */
#define SC_DASH          (int)U32(GALL_RAM + IMG_STORY)
#define SC_CLOSE         (int)U32(GALL_RAM + IMG_STORY + 4)
#define SC_SLAVE         (int)U32(GALL_RAM + IMG_STORY + 8)
#define RAIL_GAP_NEAR    55.0f
#define CLOSE_T          7.0f
#define SHOT_JUMP        2.2f       /* Slave I's jump this far into its shot */
#define FREE_AFTER       0.3f       /* free flight this long after its jump (the user: at once) */
#define DASH_JUMP        0.6f       /* Dash jumps this long after his line is let go */
#define DASH_TURN        1.6f       /* the view turns to him over this (the user: 0.7 too quick) */
#define DASH_HOLD        1.5f       /* after his jump the view is held (as to the Falcon's way) this long, then the */
#define DASH_BACK        2.0f       /* gunner's view is blended back (g_gun_blend); were Slave I's shot to start in */
#define DASH_LOOK_EASE   0.15f       /* the hold, it eases over DASH_BACK to its chase view (behind the Falcon) */
#define SHOT_FLASH       0.3f       /* a white flash this long as the ship goes (alpha FLASH_A) */
#define FLASH_A          150
#define LINE_DASH_SORRY  3          /* (lines from the table's end: 0 Leia's "Don't shoot!") */
#define LINE_CLOSE       2
#define LINE_GONE        1
#define LINE_COWARD      8          /* Lando's "Dash, you coward!" as the gunner's view comes back after Dash's jump */
#define LINE_ATMO        6          /* Lando's "We're leaving the atmosphere!" once a rail as g_alt passes ATMO_SAY (the sky */
#define ATMO_SAY         2000.0f    /* half way to black) */
static float g_sc_t, g_shot_t;
static float g_dash_look[3];         /* story(): Dash's shot looks here: after g_ocn at DASH_LOOK_EASE a frame (it
                                     * caught up 80 a frame as his held line was let go) */
static carry_t g_dash_carry;        /* story(): Dash's shot eased in from the gunner's view on screen */
static int g_dash_first;
static float g_dash_view[6];         /* story(): Dash's shot's eye (from the Falcon) and look, along, right of and up */
                                     /* from the Falcon's way (as at his jump's end: held after it) */

/* The ship HUD's turret window (elements 20-23) and the sight (0) off as a shot of ours begins (as
 * cine() does; it stood as a cockpit frame over Dash's shot): the HUD placed them for the inside view and does not re-place them while a held line holds the game;
 * it puts them back when it next places the window (after the shot). */
static void window_off(void) {
    for (int i = 0; i <= 23; i += i ? 1 : 20) S16(HUD_POS + 4 * i) = -1000;
}

void story(uint32_t node) {
    if (g_cine != 2) { g_sc = 0; g_rail_gap = RAIL_GAP; return; }   /* (a new run) */
    if (paused()) return;
    int held = S16(MSG_HOLD) != 0;                               /* (Dash's line holds the game: the story waits) */
    if (g_rail && !g_said_atmo && !held && g_alt >= ATMO_SAY) { g_said_atmo = 1; say_last(LINE_ATMO); }
    float dt = frame_dt();
    int r = (int)node - (int)U32(GALL_RAM + IMG_RAIL);
    if (g_or_jump >= 0 && !held) g_or_jump += dt;
    if (g_sl_jump >= 0) g_sl_jump += dt;
    if (g_shot) g_shot_t += frame_dt_raw();                     /* (the view turns while the line holds) */
    switch (g_sc) {
    case 0:
        if (g_rail && r >= SC_DASH) { for (int i = 0; i < 3; i++) g_dash_look[i] = g_ocn[i]; g_sc = 1; g_sc_t = 0; g_shot = 1; g_shot_t = 0; g_hp_kept = 0; g_dash_first = 1; window_off(); say_last(LINE_DASH_SORRY); }
        break;                                                   /* (the camera turned to him from behind the Falcon; his
                                                                  * line holds the game till a button, as the game's own) */
        break;
    case 1:
        if (!held) g_sc_t += dt;
        if (g_sc_t >= DASH_JUMP && g_or_jump < 0) g_or_jump = 0;
        if (g_sc_t >= DASH_JUMP + JUMP_T) g_sc = 2;            /* (the shot goes on: the view held) */
        break;
    case 2:
    case 3:
        if (g_shot && g_or_jump >= JUMP_T + DASH_HOLD) { g_shot = 0; g_gun_blend = 1; say_last(LINE_COWARD); }   /* the gunner's view back */
        if (g_sc == 3) {
            g_sc_t += dt;
            g_rail_gap = RAIL_GAP + (RAIL_GAP_NEAR - RAIL_GAP) * minf(g_sc_t / CLOSE_T, 1);
            if (r >= SC_SLAVE || !g_rail) { g_sc = 4; g_shot = 1; g_shot_t = 0; g_hp_kept = 0; g_gun_blend = 0; g_dash_first = 1; window_off(); }
        } else if (r >= SC_CLOSE) { g_sc = 3; g_sc_t = 0; say_last(LINE_CLOSE); }
        break;
    case 4:
        if (g_shot_t >= SHOT_JUMP && g_sl_jump < 0) g_sl_jump = 0;
        if (g_shot_t >= SHOT_JUMP + JUMP_T + FREE_AFTER) {      /* free flight now (this frame's free_fly()) */
            g_sc = 5; g_shot = 0; g_rail = 0; say_last(LINE_GONE);
        }
        break;
    }
    float fl = g_or_jump >= JUMP_T * 0.7f ? g_or_jump - JUMP_T * 0.7f : g_sl_jump >= JUMP_T * 0.7f ? g_sl_jump - JUMP_T * 0.7f : -1;
    if (paused()) ;                                              /* (the game's pause dim stays) */
    else if (fl >= 0 && fl < SHOT_FLASH) {                       /* the flash as it goes */
        int a = (int)(FLASH_A * (1 - fl / SHOT_FLASH));
        S16(SCREEN_FADE) = 255; S16(SCREEN_FADE + 2) = 255; S16(SCREEN_FADE + 4) = 255; S16(SCREEN_FADE + 6) = a;
    } else if (fl >= SHOT_FLASH && fl < SHOT_FLASH + 0.1f) S16(SCREEN_FADE + 6) = -1000;
    if (!g_shot) return;
    run_camera();                                                /* (not the gun's: the shot's) */
    if (SHOT_SAFE) {                                             /* no hits while it runs (the TIEs flashed it) */
        uint32_t stft = player_ship();
        if (stft) {
            int hp = (int)U32(stft + STFT_HEALTH);
            if (g_hp_kept > 0 && hp < g_hp_kept) U32(stft + STFT_HEALTH) = hp = g_hp_kept;
            g_hp_kept = hp;
        }
    }
    float eye[3], look[3];
    if (g_sc == 1 && g_or_jump < JUMP_T) {                       /* from behind the Falcon, turned from its way to Dash */
        uint32_t stft = player_ship();
        if (!stft) return;
        float p[3], d[2], w[2], e = minf(g_shot_t / DASH_TURN, 1), c = cos_r(g_ocn_yaw), sn = sin_r(g_ocn_yaw);
        float u = g_or_jump < 0 ? 0 : minf(g_or_jump / JUMP_T, 1);
        e = e * e * (3 - 2 * e);
        for (int i = 0; i < 3; i++) p[i] = F32(stft + 0x50 + 4 * i);
        w[0] = g_sl[0] - p[0]; w[1] = g_sl[1] - p[1];            /* (its way: at Slave I) */
        for (int i = 0; i < 3; i++) g_dash_look[i] += (g_ocn[i] - g_dash_look[i]) * DASH_LOOK_EASE;
        d[0] = g_dash_look[0] - p[0]; d[1] = g_dash_look[1] - p[1];
        float lw = sqrt_f(w[0] * w[0] + w[1] * w[1]), ld = sqrt_f(d[0] * d[0] + d[1] * d[1]);
        if (lw < 1 || ld < 1) return;
        for (int i = 0; i < 2; i++) { w[i] /= lw; d[i] /= ld; d[i] = w[i] + (d[i] - w[i]) * e; }
        ld = sqrt_f(d[0] * d[0] + d[1] * d[1]); d[0] /= ld; d[1] /= ld;
        for (int i = 0; i < 3; i++) {
            float f = i < 2 ? d[i] : 0;
            eye[i] = p[i] - f * 55 + (i == 2 ? 20 - SHIP_DROP : 0);
            float to = g_dash_look[i] + (i == 0 ? c : i == 1 ? sn : 0) * 900 * u * u;
            look[i] = (p[i] + f * 300) + (to - (p[i] + f * 300)) * e;
        }
        for (int i = 0; i < 2; i++) {                            /* (kept as to its way: held after the jump) */
            float *v = i ? look : eye, x = v[0] - p[0], y = v[1] - p[1];
            g_dash_view[3 * i] = x * w[0] + y * w[1]; g_dash_view[3 * i + 1] = x * w[1] - y * w[0];
            g_dash_view[3 * i + 2] = v[2] - p[2];
        }
    } else {                                                     /* behind the Falcon, over it: Slave I ahead (Slave I's
                                                                  * shot; Dash's view held after his jump) */
        uint32_t stft = player_ship();
        if (!stft) return;
        static float d[2];                                       /* (the Falcon's way: at Slave I; held from its */
        float p[3], u = g_sl_jump < 0 ? 0 : minf(g_sl_jump / JUMP_T, 1), c = cos_r(g_sl_yaw), sn = sin_r(g_sl_yaw);   /* jump on) */
        for (int i = 0; i < 3; i++) p[i] = F32(stft + 0x50 + 4 * i);
        if (g_sl_jump < 0 || (d[0] == 0 && d[1] == 0)) {
            d[0] = g_sl[0] - p[0]; d[1] = g_sl[1] - p[1];
            float l = sqrt_f(d[0] * d[0] + d[1] * d[1]);
            if (l < 1) return;
            d[0] /= l; d[1] /= l;
        }
        for (int i = 0; i < 3; i++) {
            float f = i < 2 ? d[i] : 0, rt = i == 0 ? d[1] : i == 1 ? -d[0] : 0;
            eye[i] = p[i] - f * 55 + rt * 14 + (i == 2 ? 20 - SHIP_DROP : 0);
            look[i] = g_sl_jump < 0 ? g_sl[i] : p[i] + f * 300 + (i == 0 ? c : i == 1 ? sn : 0) * 600 * u * u;
        }                                                        /* (at Slave I itself: the Star Destroyer pulled it off) */
        float e = (g_or_jump - JUMP_T - DASH_HOLD) / DASH_BACK;  /* Dash's view held, then eased over to it */
        if (e < 1) {
            float h[6], l = 0, lh = 0;
            e = e < 0 ? 0 : e * e * (3 - 2 * e);
            for (int i = 0; i < 2; i++) {
                const float *g = g_dash_view + 3 * i;
                h[3 * i] = p[0] + g[0] * d[0] + g[1] * d[1]; h[3 * i + 1] = p[1] + g[0] * d[1] - g[1] * d[0];
                h[3 * i + 2] = p[2] + g[2];
            }
            float f[3], fh[3];                                   /* (the look's direction eased, not its point: */
            for (int i = 0; i < 3; i++) {                        /* no swing as it nears) */
                f[i] = look[i] - eye[i]; fh[i] = h[3 + i] - h[i];
                l += f[i] * f[i]; lh += fh[i] * fh[i];
            }
            l = sqrt_f(l); lh = sqrt_f(lh);
            if (l < 1 || lh < 1) return;
            for (int i = 0; i < 3; i++) {
                eye[i] = h[i] + (eye[i] - h[i]) * e;
                look[i] = eye[i] + (fh[i] / lh + (f[i] / l - fh[i] / lh) * e) * 300;
            }
        }
    }
    float f[3], fal[3];                                          /* from the view on screen (the inside view: a cut) */
    for (int i = 0; i < 3; i++) f[i] = look[i] - eye[i];
    if (g_dash_first) {
        g_dash_first = 0;
        carry_from(&g_dash_carry, eye, f);
        if (S16(VIEW_MODE) == CAMERA_INSIDE || U32(CAMERA_INDEX) == CAMERA_INSIDE) g_dash_carry.share = 0;
    }
    falcon_place(fal);
    int first = g_dash_carry.share >= 1;
    carry_on(&g_dash_carry, eye, f, fal);
    carry_decay(&g_dash_carry);
    for (int i = 0; i < 3; i++) { g_ik[i] = eye[i]; g_ik[3 + i] = eye[i] + f[i]; }
    if (first && valid_ptr(U32(CAMERA_ENTRIES))) {               /* its first frame: the camera entry and the Trak too, */
        uint32_t chor = U32(CLASS_CHOR + 0x10);                  /* as cine() (one frame of the Trak's own view, D10) */
        view_set(U32(CAMERA_ENTRIES) + 3 * 0x80 + 0x14 - TRAK_MATRIX, eye, f);
        for (int i = 0; i < 3; i++) f[i] = g_ik[3 + i] - g_ik[i];
        for (uint32_t i = 0, t = U32(CLASS_TRAK + 0x10); i < U32(CLASS_TRAK + 8) && valid_ptr(t); i++, t += U32(CLASS_TRAK + 0xC))
            if (U32(t + TRAK_TARGET) == chor) view_set(t, eye, f);
    }
}
#define STFT_HP_FULL     495
void rail_restart(void) {
    if (!U32(CLASS_CHOR + 8)) return;
    uint32_t chor = U32(CLASS_CHOR + 0x10), r0 = U32(GALL_RAM + IMG_RAIL);
    rail_start(chor, r0);
    route_pos(r0 + (uint32_t)(RAIL_GAP / RAIL_STEP_U + 0.5f), g_sl);   /* (flee() seeds its gap from the node nearest) */
    g_sl_on_rail = 0; g_sl_hp = SL_HP; g_sl_lost = 0; g_bar_t = 0;
    g_sc = 0; g_rail_gap = RAIL_GAP; g_or_jump = g_sl_jump = -1; g_shot = 0; g_gun_blend = 0; g_hp_kept = 0; g_said_atmo = 0; g_dash_carry.share = 0;
    sight_hide(0);
    uint32_t stft = player_ship();
    if (stft) U32(stft + STFT_HEALTH) = STFT_HP_FULL;
    float a[3], b[3], d[3], l = 0;
    route_pos(r0, a); route_pos(r0 + 1, b);
    for (int j = 0; j < 3; j++) { d[j] = b[j] - a[j]; l += d[j] * d[j]; }
    l = sqrt_f(l); if (l < 1e-3f) l = 1;
    for (int j = 0; j < 3; j++) d[j] /= l;
    uint32_t tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC), n = U32(CLASS_TIEF + 8);
    for (uint32_t i = 0; i < 10 && i < n; i++, tie += size)
        if ((U32(tie + TIE_FLAGS) & 0xFF) == TIE_FIGHTER && battle_index(tie) < 0 && !(F32(tie + TIE_HEALTH) > 0)) tie_back(tie, i, a, d);
    g_restart_t = 0;
    gun_back();
}
void restart_fade(void) {
    if (g_restart_t < 0 || paused()) return;                    /* (the game's pause dim stays) */
    float f = g_restart_t / FADE_IN;
    for (int i = 0; i < 4; i++) S16(SCREEN_FADE + 2 * i) = f >= 1 ? -1000 : i < 3 ? 0 : (int)(FADE_MAX * (1 - f));
    if (f >= 1) g_restart_t = -1;
    else g_restart_t += frame_dt();
}
