/* Z lock-on: picking a target, circle-strafing around it, aiming the laser at it, and its
 * on-screen overlay (letterbox bars, reticle). */
#include "common.h"

#define LOCK_RANGE       150.0f   /* game units (a stormtrooper is ~6 tall); the game's own auto-aim range */
#define LOCK_BREAK       240.0f
#define LOCK_CONE_COS    0.5f     /* +-60 degrees around Dash's facing */
#define LOCK_NEAR        48.0f    /* closer than this: lockable at any angle, even behind */
#define LOCK_FOG         0.9f     /* no new lock on targets hidden by fog more than this (a faint silhouette) */
#define LOCK_FOG_BREAK   0.97f    /* drop a lock once the target is fogged out */
#define LOCK_SIGHT_EVERY 8        /* control frames (30 Hz) between sight checks on a held lock */
#define LOCK_SIGHT_LOST  4        /* hidden checks in a row that drop it: ~1 s out of sight */
#define LOS_MARGIN       1.0f     /* level geometry this close before the aim point does not hide it */
#define BOSS_AIM         0.9f     /* aim at this fraction of a boss's height */
#define ORBIT_SOFT       3.0f     /* radius error (units) that gets full-speed correction */
#define SHOT_LIFE_SPARE  0.5f     /* a locked shot outlives its flight to the lock by this (s) */
#define SHOT_LIFE_MAX    4.0f     /* ... at most this long (LOCK_RANGE at pulse speed ~3.3 s) */

uint32_t g_lock;
float g_orbit_r;              /* radius held while circle-strafing; 0: take the current one */
uint32_t g_test_skip_los;     /* set only by the test harness */
uint32_t g_test_rays;         /* test harness: sight rays traced; the last two rays' hit distance and length */
float g_test_ray[2][2];
uint32_t g_test_ray_hit[2];    /* ... and what stopped them (object, 0: level geometry) */
uint32_t g_test_target;       /* test harness: the only candidate, outside the target pool */
uint32_t g_lock_after;

/* The target_* helpers are shared by the lock code and the overlay; out of line they cost
 * a call each, inlined into every caller they cost ~0.9 KB of payload. */
#define SHARED __attribute__((noinline))

/* The AT-ST carries no z extent; its height field is used instead (cockpit on top). IG-88
 * (also class Boss) has a z extent and health at +0x60 like any enemy: 0 here. */
static float boss_height(uint32_t o) {
    if (U32(o + OBJ_NAME) != TAG_BOSS || F32(o + OBJ_Z_MAX) > F32(o + OBJ_Z_MIN)) return 0;
    float h = F32(o + BOSS_HEIGHT);
    return h > 2.0f && h < 80.0f ? h : 0;
}

SHARED int target_alive(uint32_t o) {
    if (!valid_ptr(o) || !(U16(o + OBJ_TFLAGS) & 2)) return 0;
    uint32_t tag = U32(o + OBJ_NAME);
    /* +0x60 isn't a boss's health: the AT-ST flips it from 0.01 to -0.01 when its cutscene
     * ends and the fight starts, and keeps it after dying. Only a fighting, intact boss
     * with a body is a target. IG-88 flips it to -2.5 while he charges at a Dash who hurt
     * him (the lock dropped right as he closed in), and again when he dies; his health is
     * at +0x5C4, the dead flag tells. */
    if (tag == TAG_BOSS) {
        if (U16(o + OBJ_TFLAGS) & BOSS_DEAD_FLAG) return 0;
        return boss_height(o) > 0 ? F32(o + BOSS_STATE) < 0 : F32(o + BOSS_HEALTH) > 0;
    }
    if (!(F32(o + OBJ_HEALTH) > 0)) return 0;
    return tag != TAG_BOXX && tag != TAG_ANIM && tag != TAG_HUMN && tag != TAG_HUMT;
}

/* The gladiator droid's height field is 5 (a lock at 4.5 sat on his shins). He takes hits
 * through his shells: legs (+7), body and arms (+18), head (+23). Aim at the lowest one
 * still standing: the legs first, then up the body. 0: no live shell. */
static float glad_shell_z(uint32_t o) {
    if (U32(o + OBJ_MODEL) != TAG_GLAD) return 0;
    int n = U32(CLASS_ESHD + CLASS_COUNT), size = U32(CLASS_ESHD + CLASS_SIZE);
    uint32_t s = U32(CLASS_ESHD + CLASS_HEAD);
    float best = 0;
    if (n > 0 && n <= 64 && valid_ptr(s))
        for (int i = 0; i < n; i++, s += size) {
            if (U32(s + ESHD_OWNER) != o || !(F32(s + OBJ_HEALTH) > 0)) continue;
            float z = F32(s + OBJ_POS + 8) + (F32(s + OBJ_Z_MIN) + F32(s + OBJ_Z_MAX)) * 0.5f;
            if (best == 0 || z < best) best = z;
        }
    return best;
}

/* Where to look and shoot: the body centre, or a boss's weak spot near its top. */
SHARED void target_center(uint32_t o, float *v) {
    v[0] = F32(o + OBJ_POS);
    v[1] = F32(o + OBJ_POS + 4);
    float bh = boss_height(o), gz = glad_shell_z(o);
    v[2] = gz != 0 ? gz : F32(o + OBJ_POS + 8) +
           (bh > 0 ? bh * BOSS_AIM : (F32(o + OBJ_Z_MIN) + F32(o + OBJ_Z_MAX)) * 0.5f);
}

SHARED float target_height(uint32_t o) {
    if (U32(o + OBJ_MODEL) == TAG_GLAD) return 14.0f;       /* a reticle around a leg shell, not his shin */
    float bh = boss_height(o);
    return bh > 0 ? bh * (1.0f - BOSS_AIM) * 2.0f : F32(o + OBJ_Z_MAX) - F32(o + OBJ_Z_MIN);
}

static int trace_clear(uint32_t player, uint32_t target, const float *from, float *to) {
    uint32_t hit = 0, hit2 = 0;
    float f[3] = { from[0], from[1], from[2] };
    float d = ((trace_fn)TRACE_FN)(to, f, U32(player + OBJ_COLLIDER), &hit, &hit2, 0.0f, 1);
    float dx = to[0] - f[0], dy = to[1] - f[1], dz = to[2] - f[2];
    /* The ray ends at the aim point inside the target. A hit only LOS_MARGIN short of it is
     * clear; a margin of 4 locked an enemy standing right behind a train car's wall. */
    float len = sqrt_f(dx * dx + dy * dy + dz * dz);
    /* Level geometry (hit object 0) hides a target. A ray stopping on an object is let
     * through: the target's own body, a boss's hit shells (class EShd: the AT-ST's cockpit
     * shell stops it ~5 units short), another enemy, a pickup hanging in front of his head
     * (a Challenge Point in a doorway kept a plainly visible enemy from locking). Except
     * Dash himself (the camera ray to a drone behind a wall straight past him ends on his
     * back), the train cars, crates (class Boxx: big Echo Base crates, a lock went through
     * a stack of them) and animated level parts (class Anim), which are objects too. */
    g_test_ray_hit[g_test_rays & 1] = hit;
    g_test_ray[g_test_rays & 1][0] = d; g_test_ray[g_test_rays++ & 1][1] = len;
    if (d < 0 || d >= len - LOS_MARGIN) return 1;
    uint32_t tag = valid_ptr(hit) ? U32(hit + OBJ_NAME) : 0;
    return tag && tag != TAG_HUMN && tag != TAG_HUMT && tag != TAG_TRAI && tag != TAG_BOXX && tag != TAG_ANIM;
}

/* Visible if a ray to the target's upper body is clear from Dash's chest or
 * from the camera (what the player actually sees). Low rays snag on door sills. */
static int line_of_sight(uint32_t player, uint32_t target, float *centre) {
    if (g_test_skip_los) return 1;
    float to[3] = { centre[0], centre[1],
                    boss_height(target) > 0 ? centre[2]
                                            : F32(target + OBJ_POS + 8) + F32(target + OBJ_Z_MAX) * 0.8f };
    float chest[3] = { F32(player + OBJ_POS), F32(player + OBJ_POS + 4),
                       F32(player + OBJ_POS + 8) + 5.0f };
    if (trace_clear(player, target, chest, to)) return 1;
    uint32_t cam = U32(ACTIVE_CAMERA);
    if (!valid_ptr(cam)) return 0;
    float eye[3] = { F32(cam + CAM_EYE), F32(cam + CAM_EYE + 4), F32(cam + CAM_EYE + 8) };
    return trace_clear(player, target, eye, to);
}

/* Distance of a world point along the camera's view axis (0 without a camera). */
static float view_depth(const float *w) {
    uint32_t cam = U32(ACTIVE_CAMERA);
    if (!valid_ptr(cam)) return 0;
    float z = 0;
    for (int i = 0; i < 3; i++) z += (w[i] - F32(cam + CAM_EYE + 4 * i)) * F32(cam + CAM_FORWARD + 4 * i);
    return z;
}

/* How much fog hides a point at view depth d, 0..1, the same way the RSP fogs it. */
static float fog_at(float d) {
    int lo = S16(FOG_MIN), hi = S16(FOG_MAX);
    if ((U32(FOG_OFF) >> 24) || hi <= 0 || hi <= lo) return 0;
    float n = F32(PERSPECTIVE + 8), f = F32(PERSPECTIVE + 12);
    if (!(n > 0) || !(f > n) || d <= n) return 0;
    float zw = (f + n) / (f - n) - 2.0f * f * n / ((f - n) * d);   /* clip z/w, -1..1 */
    float a = ((zw + 1.0f) * 500.0f - lo) / (float)(hi - lo);
    return a < 0 ? 0 : a > 1 ? 1 : a;
}

static float fog_amount(const float *w) { return fog_at(view_depth(w)); }

/* Fog a candidate will have once locked, when the camera has swung round behind Dash to face it.
 * The current view depth alone misses a target behind the camera (Dash running toward the
 * camera): it reads as fog-free, gets locked, and the lock drops as soon as the camera turns. */
static float fog_when_locked(uint32_t player, const float *c) {
    uint32_t cam = U32(ACTIVE_CAMERA);
    if (!valid_ptr(cam)) return 0;
    float p[3], dt = 0;
    for (int i = 0; i < 3; i++) { p[i] = F32(player + OBJ_POS + 4 * i); dt += (c[i] - p[i]) * (c[i] - p[i]); }
    float ex = F32(cam + CAM_EYE) - p[0], ey = F32(cam + CAM_EYE + 4) - p[1];
    float d = sqrt_f(dt) + sqrt_f(ex * ex + ey * ey), v = view_depth(c);
    return fog_at(v > d ? v : d);
}

/* Nearest live target in front of Dash, weighted toward the facing direction.
 * Candidate scoring is shared by the target pool and the extra classes. */
static struct { float px, py, fx, fy, best, after_score; uint32_t pick, player, after, cycle; } F;

void lock_consider(uint32_t o) {
    if (!target_alive(o) || o == F.pick) return;
    float c[3];
    target_center(o, c);
    float dx = c[0] - F.px, dy = c[1] - F.py;
    float dist = sqrt_f(dx * dx + dy * dy);
    if (dist < 1.0f || dist > LOCK_RANGE) return;
    float along = (dx * F.fx + dy * F.fy) / dist;
    float score;
    if (along >= LOCK_CONE_COS) {
        score = dist * (2.0f - along);                               /* < LOCK_RANGE * 1.5 */
        /* A boss in front comes first: the flying gladiator ~60 away lost to the troopers in
         * the maze right under Dash, and Z kept locking them. The sewer dianoga is a Trop: its
         * eye (the boss, "Dianoga Eye" on the HUD) goes before its tentacles. */
        uint32_t tag = U32(o + OBJ_NAME);
        if (tag == TAG_BOSS || (tag == TAG_TROP && (U32(o + TROP_KIND) & 0x300) == 0x100))
            score -= LOCK_RANGE * 1.5f;
    }
    /* SotE enemies shoot: a very close enemy outside the cone is
     * lockable too, ranked after every enemy in front of Dash. */
    else if (dist <= LOCK_NEAR) score = LOCK_RANGE * 2 + dist;
    else return;
    if (o == F.after) F.after_score = score;
    /* Cycling: only targets ranked after F.after (ties by address). */
    if (F.cycle && (o == F.after || score < F.after_score || (score == F.after_score && o < F.after))) return;
    if (score >= F.best || fog_when_locked(F.player, c) > LOCK_FOG || !line_of_sight(F.player, o, c)) return;
    F.best = score;
    F.pick = o;
}

static uint32_t scan(uint32_t player) {
    float face = RAD(player_facing(player));
    F.px = F32(player + OBJ_POS); F.py = F32(player + OBJ_POS + 4);
    F.fx = cos_r(face); F.fy = sin_r(face);
    F.best = LOCK_RANGE * 4; F.pick = 0; F.player = player;
    if (g_test_target) { lock_consider(g_test_target); return F.pick; }

    int count = U32(TARGET_POOL + 8), stride = U32(TARGET_POOL + 12);
    uint32_t base = U32(TARGET_POOL + 16);
    if (count > 0 && count <= 1024 && stride >= 0x9C && stride <= 0x400 && valid_ptr(base))
        for (int i = 0; i < count; i++) {
            uint32_t rec = base + i * stride;
            if (!U32(rec + REC_ALIVE) || !(U16(rec + REC_FLAGS) & 2)) continue;
            lock_consider(U32(rec + REC_OBJECT));
        }
    if (ON_TRAIN) train_targets();
    return F.pick;
}

/* The best target, or with g_lock_after the one ranked next after it (wrapping round to the
 * best): a first pass ranks everything and scores g_lock_after, a second takes the next. */
uint32_t find_target(uint32_t player) {
    F.after = g_lock_after; g_lock_after = 0;
    F.cycle = 0; F.after_score = -1e30f;
    uint32_t best = scan(player);
    if (!F.after || F.after_score == -1e30f) return best;
    F.cycle = 1;
    uint32_t next = scan(player);
    F.cycle = 0;
    return next ? next : best;
}

static float strafe_mag(float v) {
    float k = F32(K->strafe_k);
    return ((curve_fn)STICK_CURVE)(v / 100.0f, 2, k, k);
}

/* Stick to strafe/forward/back intents around the facing in g_target_yaw. With dist > 0
 * (a lock) sideways-only input circles the target at a held radius. */
static void steer(uint32_t sp, float sx, float sy, float dist) {
    g_active = 1;
    int fwd = sy > STICK_DEADZONE, back = sy < -STICK_DEADZONE;
    int right = sx > STICK_DEADZONE, left = sx < -STICK_DEADZONE;
    float fwd_mag = (fwd || back) ? ((curve_fn)STICK_CURVE)(absf(sy) / 100.0f, 3, 4.0f, 4.0f) : 0;

    /* Circle strafe: native strafing goes in a straight line, and with the turn
     * lagging a little behind the bearing Dash spirals outward. While the stick only points
     * sideways, hold the radius by stepping in or out; forward/back pick a new radius. */
    if (dist <= 0) {
    } else if (fwd || back || !(left || right) || g_orbit_r <= 0) {
        g_orbit_r = dist;
    } else {
        float m = (dist - g_orbit_r) / ORBIT_SOFT;
        if (m > 1) m = 1;
        if (m < -1) m = -1;
        float full = ((curve_fn)STICK_CURVE)(STICK_MAX / 100.0f, 3, 4.0f, 4.0f);
        if (m > 0.02f) { fwd = 1; fwd_mag = full * m; }
        else if (m < -0.02f) { back = 1; fwd_mag = -full * m; }
    }

    SLOT16(sp, DEC_FORWARD) = fwd;
    SLOT16(sp, DEC_BACK) = back;
    SLOT16(sp, DEC_TURN_A) = 0;
    SLOT16(sp, DEC_TURN_B) = 0;
    SLOT16(sp, DEC_STRAFE_R) = right;
    SLOT16(sp, DEC_STRAFE_L) = left;
    SLOTF(sp, DEC_FWD_MAG) = fwd_mag;
    SLOTF(sp, DEC_TURN_MAG) = (left || right) ? strafe_mag(absf(sx)) : 0;
    /* The stick now moves Dash; keep the native aim mode from also pitching the gun. */
    U32(PAD_STICK_X) = 0;
}

/* A held lock is dropped once the target has been out of sight for a while (behind a train
 * car, round a corner); Z still held then rescans for someone visible. Traces cost frame
 * time, so only every few control frames. */
static uint32_t g_sight_target, g_sight_t, g_sight_miss;

int lock_steer(uint32_t obj, uint32_t sp, float sx, float sy) {
    float c[3];
    target_center(g_lock, c);
    float dx = c[0] - F32(obj + OBJ_POS), dy = c[1] - F32(obj + OBJ_POS + 4);
    if (dx * dx + dy * dy > LOCK_BREAK * LOCK_BREAK || fog_amount(c) > LOCK_FOG_BREAK) return 0;
    if (g_lock != g_sight_target) { g_sight_target = g_lock; g_sight_miss = 0; }
    if (++g_sight_t % LOCK_SIGHT_EVERY == 0) {
        g_sight_miss = line_of_sight(obj, g_lock, c) ? 0 : g_sight_miss + 1;
        if (g_sight_miss >= LOCK_SIGHT_LOST) { g_sight_target = 0; return 0; }
    }
    g_target_yaw = wrap180(DEG(atan2_r(dy, dx)) - 90.0f);
    steer(sp, sx, sy, sqrt_f(dx * dx + dy * dy));
    return 1;
}

/* Lock lost with Z still held: keep facing the same way and strafe, as if still locked. */
void hold_steer(float yaw, uint32_t sp, float sx, float sy) {
    g_target_yaw = yaw;
    steer(sp, sx, sy, 0);
}

/* Unit direction from a muzzle to the lock in d and the distance; 0 (d untouched) without a
 * live lock or when that would turn a shot fired along dir backwards. */
static float lock_aim(const float *from, const float *dir, float *d) {
    if (!g_lock || !target_alive(g_lock)) return 0;
    float c[3];
    target_center(g_lock, c);
    float v[3] = { c[0] - from[0], c[1] - from[1], c[2] - from[2] };
    float len = sqrt_f(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    if (len < 0.5f || dir[0] * v[0] + dir[1] * v[1] + dir[2] * v[2] <= 0) return 0;
    for (int i = 0; i < 3; i++) d[i] = v[i] / len;
    return len;
}

/* Dash's other shots, all fired along his body's flat facing: pulse cannon and disruptor
 * go through the projectile spawn 0x80064584(kind, pos, ?, vel, ...). Turn the velocity at
 * the lock, same speed (the AT-ST's cockpit is ~16 units up; they flew at chest height). */
static float g_shot_life;     /* seconds the next spawned shot must fly to reach the lock; 0: none */
static uint32_t g_shot_obj;   /* the projectile that took it */

void ctl_shot(const float *pos, float *vel) {
    float d[3];
    float len = lock_aim(pos, vel, d);
    g_shot_life = 0; g_shot_obj = 0;
    if (!len) return;
    float s = sqrt_f(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]);
    for (int i = 0; i < 3; i++) vel[i] = d[i] * s;
    if (s > 1.0f) g_shot_life = len / s + SHOT_LIFE_SPARE;
}

/* The spawn stores the shot's lifetime (+0x8C, seconds, from its kind's table; kinds with
 * flag 0x40 store a second value over it). A pulse cannon blob lives ~0.7 s (~30 units) and
 * fizzled short of a locked AT-ST further away: the shot the lock just aimed lives long
 * enough to get there. The first spawn after ctl_shot takes it; other spawns keep theirs. */
void ctl_life(uint32_t obj, uint32_t bits) {
    union { uint32_t u; float f; } life = { bits };
    if (g_shot_obj != obj) {
        if (g_shot_obj) g_shot_life = 0;
        g_shot_obj = obj;
    }
    if (g_shot_life > life.f) life.f = g_shot_life > SHOT_LIFE_MAX ? SHOT_LIFE_MAX : g_shot_life;
    F32(obj + SHOT_LIFE) = life.f;
}

/* A seeker missile picks its target with the game's auto-aim, which skips bosses. It homes
 * on the object whose matrix (+0x20) it gets, at height +0x98 above its position. Locked:
 * the lock instead. Returns what the missile stores. */
uint32_t ctl_seeker(uint32_t misl, uint32_t found, uint32_t shooter) {
    if (!g_lock || shooter != g_player || !target_alive(g_lock) || !valid_ptr(misl)) return found;
    float c[3];
    target_center(g_lock, c);
    F32(misl + MISL_AIM_Z) = c[2] - F32(g_lock + OBJ_POS + 8);
    return g_lock + OBJ_MATRIX;
}

/* A laser bolt has its muzzle position and unit direction; aim it at the lock. */
void ctl_laser(uint32_t bolt, uint32_t shooter) {
    if (shooter != g_player || !valid_ptr(bolt)) return;
    float d[3];
    float *dir = (float *)(bolt + BOLT_DIR);
    if (!lock_aim((float *)(bolt + BOLT_POS), dir, d)) return;
    /* Keep the visible bolt oriented along its flight: right, forward, up rows. */
    float hl = sqrt_f(d[0] * d[0] + d[1] * d[1]);
    float r[3] = { 1, 0, 0 };
    if (hl > 0.001f) { r[0] = d[1] / hl; r[1] = -d[0] / hl; r[2] = 0; }
    float u[3] = { r[1] * d[2] - r[2] * d[1], r[2] * d[0] - r[0] * d[2], r[0] * d[1] - r[1] * d[0] };
    float *m = (float *)(bolt + 0x20);
    for (int i = 0; i < 3; i++) { m[i] = r[i]; m[4 + i] = d[i]; m[8 + i] = u[i]; dir[i] = d[i]; }
}

/* ---- Overlay, drawn into the scene display list after the HUD: letterbox bars and the
 * four-triangle reticle. Features may draw their own hints through ov_color/fill_tri. ---- */

#define BAR_HEIGHT      16.0f     /* pixels at 240 lines: a small gap below the HUD boxes (rows 186-220) */
#define BAR_SPEED       10.0f     /* per second, exponential approach */
#define MARK_LOCK_TIME  0.28f     /* seconds for the reticle to close in */
#define MARK_SIZE       13.0f     /* triangle length in pixels */
#define MARK_HALF_W     5.0f
#define FILL_BLACK      0x00010001u

float g_bar_h;                /* exported for tests */
static float g_mark_t;
static uint32_t g_mark_target;

static void emit(uint32_t w0, uint32_t w1) {
    volatile uint32_t *p = (volatile uint32_t *)U32(GFX_HEAD);
    p[0] = w0;
    p[1] = w1;
    U32(GFX_HEAD) = (uint32_t)(p + 2);
}

void ov_color(uint32_t fill) {
    emit(0xE7000000u, 0);                       /* pipe sync */
    emit(0xF7000000u, fill);
}

/* Inclusive pixel rectangle in fill mode. */
static void fill_rect(int x0, int y0, int x1, int y1) {
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > SCREEN_W - 1) x1 = SCREEN_W - 1;
    if (y1 > SCREEN_H - 1) y1 = SCREEN_H - 1;
    if (x1 < x0 || y1 < y0) return;
    emit(0xF6000000u | ((uint32_t)(x1 * 4) << 12) | (uint32_t)(y1 * 4),
         ((uint32_t)(x0 * 4) << 12) | (uint32_t)(y0 * 4));
}

static int floor_i(float v) { int i = (int)v; return (v < 0 && (float)i != v) ? i - 1 : i; }

/* Scanline triangle: one fill rectangle per pixel row. */
void fill_tri(float ax, float ay, float bx, float by, float cx, float cy) {
    float ymin = ay < by ? (ay < cy ? ay : cy) : (by < cy ? by : cy);
    float ymax = ay > by ? (ay > cy ? ay : cy) : (by > cy ? by : cy);
    float px[3] = { ax, bx, cx }, py[3] = { ay, by, cy };
    for (int y = floor_i(ymin); y <= floor_i(ymax); y++) {
        float yc = y + 0.5f, lo = 1e9f, hi = -1e9f;
        for (int i = 0; i < 3; i++) {
            int j = (i + 1) % 3;
            float y0 = py[i], y1 = py[j];
            if ((yc < y0 && yc < y1) || (yc > y0 && yc > y1) || y0 == y1) continue;
            float x = px[i] + (px[j] - px[i]) * (yc - y0) / (y1 - y0);
            if (x < lo) lo = x;
            if (x > hi) hi = x;
        }
        if (hi >= lo) fill_rect(floor_i(lo + 0.5f), y, floor_i(hi - 0.5f), y);
    }
}

/* One out-of-line sine for this file (common.h's is inline): it is needed rarely here. */
static __attribute__((noinline)) float ov_sin(float x) { return sin_r(x); }
static float ov_cos(float x) { return ov_sin(x + PI_F / 2); }

/* Projection scale from the game's current fovy/aspect (Mos Eisley uses a wider fovy),
 * recomputed only when they change. */
static __attribute__((noinline)) void proj_scale(float *px, float *py) {
    static float fovy0, aspect0, px0 = PROJ_X, py0 = PROJ_Y;
    float fovy = F32(PERSPECTIVE), aspect = F32(PERSPECTIVE + 4);
    if (fovy != fovy0 || aspect != aspect0) {
        fovy0 = fovy; aspect0 = aspect;
        if (!(fovy > 10.0f && fovy < 170.0f) || !(aspect > 0.5f && aspect < 3.0f)) {
            px0 = PROJ_X; py0 = PROJ_Y;
        } else {
            float h = RAD(fovy * 0.5f);
            py0 = ov_cos(h) / ov_sin(h);
            px0 = py0 / aspect;
        }
    }
    *px = px0; *py = py0;
}

/* World point to screen pixels; returns 0 if behind the camera. */
int project(const float *w, float *sx, float *sy, float *depth) {
    uint32_t cam = U32(ACTIVE_CAMERA);
    if (!valid_ptr(cam)) return 0;
    float d[3];
    for (int i = 0; i < 3; i++) d[i] = w[i] - F32(cam + CAM_EYE + 4 * i);
    float z = 0, x = 0, y = 0;
    for (int i = 0; i < 3; i++) {
        z += d[i] * F32(cam + CAM_FORWARD + 4 * i);
        x += d[i] * F32(cam + CAM_RIGHT + 4 * i);
        y += d[i] * F32(cam + CAM_UP + 4 * i);
    }
    if (z < 1.0f) return 0;
    float px, py;
    proj_scale(&px, &py);
    *sx = SCREEN_W * 0.5f * (1.0f + px * x / z);
    *sy = SCREEN_H * 0.5f * (1.0f - py * y / z);
    *depth = z;
    return 1;
}

static float approach(float v, float target, float k) { return v + (target - v) * (k > 1 ? 1 : k); }

void ctl_overlay(void) {
    g_ov_frames++;
    gallrun_frame();
    falcon_frame();
    cheats_frame();
    float dt = frame_dt();
    int fresh = g_ov_frames - g_decode_ov <= 3;
    uint32_t lock = fresh ? g_lock : 0;
    if (lock && !target_alive(lock)) lock = 0;

    g_bar_h = approach(g_bar_h, lock ? BAR_HEIGHT : 0, BAR_SPEED * dt);
    if (lock != g_mark_target) { g_mark_target = lock; g_mark_t = 0; }
    else if (lock) g_mark_t += dt;

    float sx = 0, sy = 0, depth = 0, c[3];
    int mark = 0;
    if (lock) {
        target_center(lock, c);
        mark = project(c, &sx, &sy, &depth) && sx > -40 && sx < SCREEN_W + 40 && sy > -40 && sy < SCREEN_H + 40;
    }
    int bars = g_bar_h >= 1.0f;
    if (!bars && !mark) return;

    emit(0xE7000000u, 0);                       /* pipe sync */
    emit(0xBA001402u, 0x00300000u);             /* cycle type: fill */
    if (bars) {
        int h = (int)(g_bar_h + 0.5f);
        emit(0xF7000000u, FILL_BLACK);
        fill_rect(0, 0, SCREEN_W - 1, h - 1);
        fill_rect(0, SCREEN_H - h, SCREEN_W - 1, SCREEN_H - 1);
    }
    if (mark) {
        /* Reticle radius follows the target's on-screen height. */
        float height = target_height(lock);
        float px, py;
        proj_scale(&px, &py);
        float r = 0.55f * py * height / depth * (SCREEN_H * 0.5f);
        if (r < 10) r = 10;
        if (r > 60) r = 60;
        /* Lock-on: the triangles fly in from further out while spinning a quarter turn. */
        float t = g_mark_t / MARK_LOCK_TIME;
        if (t > 1) t = 1;
        float ease = 1 - (1 - t) * (1 - t);
        float rr = r + (1 - ease) * 55.0f;
        float spin = (1 - ease) * (PI_F / 2);
        /* The four pointers sit 90 degrees apart: one sine/cosine, then quarter turns. */
        float a0 = PI_F / 4 + spin, ux0 = ov_cos(a0), uy0 = ov_sin(a0);
        /* Dark outline pass, then the yellow pointers on top. */
        for (int pass = 0; pass < 2; pass++) {
            float grow = pass ? 0 : OV_OUTLINE;
            float ux = ux0, uy = uy0;               /* outward, screen y down */
            ov_color(pass ? FILL_YELLOW : FILL_OUTLINE);
            for (int i = 0; i < 4; i++) {
                if (i) { float t = ux; ux = -uy; uy = t; }   /* +90 degrees */
                float tipx = sx + ux * (rr - grow), tipy = sy + uy * (rr - grow);
                float len = MARK_SIZE + 2 * grow, hw = MARK_HALF_W + grow;
                float bx = tipx + ux * len, by = tipy + uy * len;
                float px = -uy * hw, py = ux * hw;
                fill_tri(tipx, tipy, bx + px, by + py, bx - px, by - py);
            }
        }
    }
    emit(0xE7000000u, 0);
    emit(0xBA001402u, 0);                       /* back to 1-cycle */
}
