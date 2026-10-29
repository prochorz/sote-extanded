/* Shared by every module of the controls patch: math, the player class table, the state
 * the modules hand each other, and the hooks of optional features (stubs when built
 * without them, see build.py --without). */
#pragma once
#include "game.h"

#define PI_F 3.14159265f
#define DEG(r) ((r) * (180.0f / PI_F))
#define RAD(d) ((d) * (PI_F / 180.0f))

#define STICK_DEADZONE   8.0f
#define STICK_MAX        80.0f

/* ---- math (no libm in the payload) ---- */

static inline float absf(float x) { return x < 0 ? -x : x; }

static inline float wrap180(float a) {
    while (a > 180.0f) a -= 360.0f;
    while (a <= -180.0f) a += 360.0f;
    return a;
}

/* sin/cos on [-pi, pi] via a 7th order odd polynomial after range reduction. */
static inline float sin_r(float x) {
    while (x > PI_F) x -= 2 * PI_F;
    while (x < -PI_F) x += 2 * PI_F;
    if (x > PI_F / 2) x = PI_F - x;
    else if (x < -PI_F / 2) x = -PI_F - x;
    float x2 = x * x;
    return x * (1.0f - x2 * (1.0f / 6 - x2 * (1.0f / 120 - x2 * (1.0f / 5040))));
}
static inline float cos_r(float x) { return sin_r(x + PI_F / 2); }

static inline float atan_unit(float z) { /* |z| <= 1 */
    float z2 = z * z;
    return z * (0.99997726f + z2 * (-0.33262347f + z2 * (0.19354346f +
           z2 * (-0.11643287f + z2 * (0.05265332f + z2 * -0.01172120f)))));
}
static inline float atan2_r(float y, float x) {
    float ax = absf(x), ay = absf(y);
    if (ax < 1e-6f && ay < 1e-6f) return 0;
    float a = ax >= ay ? atan_unit(ay / ax) : PI_F / 2 - atan_unit(ax / ay);
    if (x < 0) a = PI_F - a;
    return y < 0 ? -a : a;
}

static inline float sqrt_f(float x) {
    float r;
    if (x <= 0) return 0;
    __asm__("sqrt.s %0, %1" : "=f"(r) : "f"(x));
    return r;
}

/* ---- game helpers ---- */

typedef float (*curve_fn)(float v, int n, float a, float b);
typedef uint32_t (*find_fn)(uint32_t tag, int zero);
typedef float (*trace_fn)(float *to, float *from, uint32_t ignore, uint32_t *hit,
                          uint32_t *hit2, float zero, int one);

static inline int valid_ptr(uint32_t a) { return a >= 0x80000400u && a < 0x807F0000u; }

static inline float frame_dt(void) {
    float dt = (float)F64(FRAME_DT);
    if (!(dt > 0.001f)) dt = 1.0f / 30;
    if (dt > 0.1f) dt = 0.1f;
    return dt;
}

/* Button mask the current control preset maps to a binding slot. */
static inline uint16_t binding(int offset) {
    int preset = S16(CTRL_PRESET);
    if (preset < 0 || preset > 7) preset = 0;
    return U16(CTRL_BINDINGS + preset * 96 + offset);
}

/* Ray from `from` to `to` against the level, ignoring obj; distance to the hit or < 0. */
static inline float trace_dist(uint32_t obj, const float *from, float *to) {
    uint32_t hit = 0, hit2 = 0;
    float f[3] = { from[0], from[1], from[2] };
    return ((trace_fn)TRACE_FN)(to, f, U32(obj + OBJ_COLLIDER), &hit, &hit2, 0.0f, 1);
}

/* ---- player classes ---- */

/* The two player classes share the same controller design but not the layout:
 * Humn (on foot) and HumT (Ord Mantell train level, control at 0x800AAADC). */
struct player_kind {
    uint32_t tag;
    uint16_t yaw, rate;        /* heading (degrees) and yaw rate fields */
    uint16_t dec;              /* extra offset of the decoded-intent stack slots */
    uint32_t strafe_k;         /* strafe response-curve constant */
    uint32_t dead;             /* OBJ_FLAGS bits meaning the player is down */
    uint16_t health;           /* health float field, 0: not checked */
    uint16_t cam_matrix;       /* rotation matrix the camera follows (row 1: facing) */
};
extern const struct player_kind KINDS[2];
extern const struct player_kind *K;
#define ON_FOOT  (K == &KINDS[0])
#define ON_TRAIN (K == &KINDS[1])

#define SLOT16(sp, off) (*(volatile int16_t *)((sp) + K->dec + (off)))
#define SLOTF(sp, off)  (*(volatile float *)((sp) + K->dec + (off)))

static inline float player_facing(uint32_t obj) { return F32(obj + K->yaw) + 90.0f; }

/* Heading in both copies (the control function restores +0x8C from +0x14 every frame). */
static inline void set_yaw(uint32_t obj, float yaw) {
    F32(obj + K->yaw) = yaw;
    F32(obj + OBJ_YAW_COPY) = yaw;
}

/* ---- shared state (core.c) ---- */

extern uint32_t g_player;
extern int g_active;          /* stick is steering Dash this frame */
extern float g_target_yaw;    /* desired yaw in degrees */
extern int g_aiming;
extern uint32_t g_ov_frames;  /* overlay (rendered frame) counter */
extern uint32_t g_decode_ov;  /* g_ov_frames at the last player decode */
/* Cheats toggles: all on after power-on, a set bit switches a feature off (the game's own
 * behaviour). The lock needs the new controls: off with them. */
extern uint32_t g_off;
#define OFF_CONTROLS 1
#define OFF_LOCK     2
#define OFF_HANG     4

/* ---- lock-on (lock.c) ---- */

extern uint32_t g_lock;       /* Z-targeted object, 0 if none */
extern float g_orbit_r;
uint32_t find_target(uint32_t player);
extern uint32_t g_lock_after;  /* find_target: the next target after this one, in ranking order */
int target_alive(uint32_t o);
void target_center(uint32_t o, float *v);
float target_height(uint32_t o);
int lock_steer(uint32_t obj, uint32_t sp, float sx, float sy);
void hold_steer(float yaw, uint32_t sp, float sx, float sy);

/* ---- train (train.c, optional) ---- */

void lock_consider(uint32_t o);          /* offer a target to find_target (lock.c) */
#if FEATURE_TRAIN
int train_input_gated(void);
void train_camera_behind(void);
void train_targets(void);                /* offers the train level's drones and troopers */
float train_car_turn(uint32_t obj);      /* degrees the car under Dash turned since the last call */
#else
static inline int train_input_gated(void) { return 0; }
static inline void train_camera_behind(void) {}
static inline void train_targets(void) {}
static inline float train_car_turn(uint32_t obj) { return 0; }
#endif

/* ---- Millennium Falcon model for the Gall Run (falcon.c, built with gallrun) ---- */

#if FEATURE_FALCON
extern float g_ship_drop;                /* draw the ship this much below its path (Gall Run) */
extern float g_ship_off[3];              /* and this far off it (Gall Run stage 1 steering) */
extern float g_ship_at[3];               /* or, while g_ship_at_on, at this place (the flown ship: off Chor */
extern int g_ship_at_on;                 /* by this frame's offset it jerked by Chor's step) */
extern float g_ship_roll;                /* and banked (radians, right wing down) */
extern float g_ship_pitch;               /* and pitched (radians, nose down) */
extern float g_ship_yaw;                 /* and turned (radians, to the right) */
extern float g_glow_w;                   /* > 0: the engine glow this wide (the Gall Run's native flight, by its speed) */
void node_turn(uint32_t node, float a, int p, int q);   /* turn a transform node (falcon.c) */
#define node_roll(node, a) node_turn(node, a, 0, 24)       /* about its forward axis */
float ship_sin(float x);                 /* sin_r, one copy (falcon.c) */
void falcon_frame(void);                 /* from the overlay hook, once per frame */
#else
static inline void falcon_frame(void) {}
#endif

/* ---- Gall Run bonus mission (gallrun.c, optional, needs falcon) ---- */

#if FEATURE_GALLRUN
extern int g_gallrun;
void gallrun_start(void);                /* Cheats: load the Gall Run, sub-level 32 */
void gallrun_boot(void);                 /* _start: the sub-level tables grown to 33 (gallrun.c) */
int gallrun_active(void);                /* on its sub-level with the image loaded */
void gallrun_frame(void);                /* from the overlay hook, once per frame */
void gallrun_pad(void);                  /* after the raw controller read (hook at 0x8001311C) */
#else
static inline int gallrun_active(void) { return 0; }
static inline void gallrun_frame(void) {}
#endif

/* ---- jetpack fuel cheat (cheats.c, optional) ---- */

#if FEATURE_CHEATS
extern int g_fuel_on;                    /* Cheats: keep the jetpack's fuel full */
void cheats_frame(void);                 /* from the overlay hook, once per frame */
void cheats_pad(void);                   /* from the pad read hook (hooks.S), before the game decodes it */
void cheats_hud_col(uint32_t *, uint32_t *); /* from the HUD colour hook (hooks.S) */
#else
static inline void cheats_frame(void) {}
#endif

/* ---- overlay drawing (lock.c), usable by features ---- */

void ov_color(uint32_t fill);
void fill_tri(float ax, float ay, float bx, float by, float cx, float cy);
int project(const float *w, float *sx, float *sy, float *depth);
#define OV_OUTLINE      1.5f
#define FILL_YELLOW     0xFFC1FFC1u   /* RGBA5551 255,255,0 twice */
#define FILL_OUTLINE    0x51815181u   /* dark brown, readable on snow */

/* ---- ledge hang (hang.c, optional) ---- */

#if FEATURE_HANG
extern uint32_t g_hang_state; /* 0 none, 1 hanging, 2 climbing */
int hang_update(uint32_t obj, uint32_t sp, uint32_t buttons, float sx, float sy);
void hang_abort(uint32_t obj);           /* Dash died: let go */
void hang_hold(uint32_t obj);            /* from the yaw hook: keep him turned to the wall */
int hang_cam(float *facing);             /* 1: camera faces *facing (hanging, letting go) */
#else
#define g_hang_state 0
static inline int hang_update(uint32_t obj, uint32_t sp, uint32_t buttons, float sx, float sy) { return 0; }
static inline void hang_abort(uint32_t obj) {}
static inline void hang_hold(uint32_t obj) {}
static inline int hang_cam(float *facing) { return 0; }
#endif
