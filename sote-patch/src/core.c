/* Camera-relative on-foot controls with Z lock-on for Shadows of the Empire: the hooks
 * on Dash's controller and the follow camera.
 *
 * - ctl_decode: runs right after the game decodes the stick into
 *   forward/back/turn intents. Converts the stick into a camera-relative
 *   direction and asks the game to run forward.
 * - ctl_yaw: runs just before the game integrates the yaw rate. Turns Dash
 *   quickly toward the requested direction.
 * - ctl_cam: runs before the dolly camera places itself behind the player.
 *   Replaces the player's rotation in the camera's private copy with a lazily
 *   following yaw, so the camera trails behind instead of being bolted on.
 *
 * Lock-on and its overlay are in lock.c; optional features: the Ord Mantell train
 * in train.c, the ledge hang in hang.c (build.py --without <name>).
 */
#include "common.h"

/* Tuning. */
#define TURN_SPEED       14.0f    /* fraction of the angle error closed per second */
#define TURN_MAX_DPS     900.0f
#define CAM_FOLLOW       2.2f     /* camera catch-up while running */
#define CAM_SNAP         12.0f    /* camera catch-up while aiming */
#define CAM_HANG         6.0f     /* camera swing to behind Dash while he hangs */
#define CAM_IDLE_DELAY   1.5f     /* seconds standing still before the camera drifts behind */
#define CAM_IDLE_RAMP    0.6f     /* seconds to ease into the full recenter rate */
#define CAM_RECENTER     2.5f     /* camera drift to behind a standing Dash */
#define CAM_STALE_FRAMES 4
#define CAM_PITCH_UP     30.0f    /* locked: the camera tilts up to a target above (degrees) */
#define CAM_PITCH_DOWN   20.0f    /* ... and down to one below */
#define CAM_PITCH_RATE   5.0f     /* tilt catch-up */
#define CAM_PITCH_EYE    1.5f     /* elevation measured from this high above Dash's feet */
#define CAM_PITCH_PART   0.8f     /* of that elevation: the target sits above centre, Dash stays in view */
#define HOLD_RESCAN      8        /* frames between looks for a new target while holding */
#define RETAP_FRAMES     12       /* Z pressed again this soon after letting go of a lock: next target */

const struct player_kind KINDS[2] = {
    /* On foot no flag marks death, only health 0. 0x400 is set while he swims (the sewer):
     * read as "dead", it switched the patch, the lock included, off in the water. */
    { TAG_HUMN, OBJ_YAW, OBJ_YAW_RATE, 0x00, STRAFE_CURVE_K, 0,          HUMN_HEALTH, OBJ_MATRIX_COPY },
    /* Ord Mantell train (only hooked with the train feature). On the train 0x400 is set
     * while airborne; falling off sets 0x08000000. */
    { TAG_HUMT, 0x090,   0x0A8,        0x40, 0x800ED044,     0x08000000, 0x0C0, 0x11C },
};
const struct player_kind *K = &KINDS[0];

uint32_t g_player;
int g_active;
float g_target_yaw;
int g_aiming;
uint32_t g_ov_frames;
uint32_t g_decode_ov;
uint32_t g_off;
static int g_cam_valid;
float g_cam_facing;           /* lazy camera facing in degrees (exported for tests) */
float g_cam_pitch;            /* camera tilt toward the locked target, degrees up (exported for tests) */
static uint32_t g_cam_calls;
static float g_idle_t;        /* seconds the camera has been left alone (no stick, no Z) */
static uint32_t g_decode_at;
/* Z held after its lock ended (target killed, out of range, fogged): Dash keeps this yaw
 * and strafes instead of dropping into the native aim, where the stick pitches the gun. */
static int g_hold;
static float g_hold_yaw;
static uint32_t g_hold_frames;
static uint32_t g_last_lock;      /* the lock Z just let go of, and decodes since */
static uint32_t g_released;

typedef void (*set_camera_fn)(uint32_t player, int32_t view, uint32_t zero);

/* Native input suppression (hit-stun, messages) checked right after the decode. */
static int input_gated(void) {
    if (ON_TRAIN) return train_input_gated();
    return F32(INPUT_GATE_1) > 0 || F32(INPUT_GATE_2) > 0;
}

static void start_hold(uint32_t obj) {
    if (g_hold) return;
    g_hold = 1;
    g_hold_yaw = F32(obj + K->yaw);
    g_hold_frames = 0;
}

/* Z means "camera behind me": leave first-person / drop / overhead views first. */
static void camera_behind(uint32_t obj) {
    if (ON_TRAIN) { train_camera_behind(); return; }
    if (S16(CAMERA_VIEW) != CAMERA_FOLLOW) ((set_camera_fn)SET_CAMERA)(obj, CAMERA_FOLLOW, 0);
}

/* Z: lock on press, retarget, hold the yaw once the lock is gone. 1: steering done. */
static int lock_input(uint32_t obj, uint32_t sp, float sx, float sy, int was_aiming) {
    if (g_aiming && !was_aiming) camera_behind(obj);
    if (!g_aiming) {
        if (g_lock) { g_last_lock = g_lock; g_released = 0; }
        else if (g_released < RETAP_FRAMES + 1) g_released++;
        g_lock = 0; g_hold = 0;
    } else if (!was_aiming) {                                   /* lock on Z press */
        /* A quick second tap moves on from the lock just let go of (the dianoga's eye, then
         * its tentacles one by one, back to the eye); a later press takes the best target. */
        if (g_last_lock && g_released <= RETAP_FRAMES) g_lock_after = g_last_lock;
        g_last_lock = 0;
        g_lock = find_target(obj); g_orbit_r = 0;
    }
    if (g_lock && !target_alive(g_lock)) {
        /* Target killed while Z is still held: move on to the next one. */
        g_lock = find_target(obj);
        g_orbit_r = 0;
        if (!g_lock) start_hold(obj);
    }
    if (g_hold && ++g_hold_frames % HOLD_RESCAN == 0) {   /* someone new in front? */
        g_lock = find_target(obj);
        g_orbit_r = 0;
    }
    if (g_lock) {
        if (lock_steer(obj, sp, sx, sy)) { g_hold = 0; return 1; }
        g_lock = 0;
        start_hold(obj);
    }
    if (g_hold) {
        hold_steer(g_hold_yaw, sp, sx, sy);
        return 1;
    }
    return 0;
}

void ctl_decode(uint32_t obj, uint32_t sp, uint32_t kind) {
    K = &KINDS[kind & 1];
    float sx = S16(PAD_STICK_X), sy = S16(PAD_STICK_Y);
    uint32_t buttons = U32(PAD_BUTTONS);
    int was_aiming = g_aiming;

    g_player = obj;
    g_decode_at = g_cam_calls;
    g_decode_ov = g_ov_frames;
    g_aiming = (buttons & binding(BIND_AIM)) != 0;
    g_active = 0;

    if (U32(obj + OBJ_NAME) != K->tag) return;
    if ((U32(obj + OBJ_FLAGS) & K->dead) || (K->health && !(F32(obj + K->health) > 0))) {
        g_lock = 0; g_hold = 0;
        if (g_hang_state) hang_abort(obj);
        return;
    }
    if (ON_FOOT && hang_update(obj, sp, buttons, sx, sy)) {
        g_lock = 0; g_hold = 0;
        return;
    }
    if (g_off & OFF_CONTROLS) {                         /* Cheats: the game's own controls */
        g_lock = 0; g_hold = 0; g_last_lock = 0;
        return;
    }
    if (input_gated()) {
        /* Hit-stun or a message: input is frozen, but the lock survives
         * taking damage, and a Z press during the stun still counts afterwards. */
        g_aiming = was_aiming;
        return;
    }

    if (g_off & OFF_LOCK) { g_lock = 0; g_hold = 0; g_last_lock = 0; }   /* Cheats: Z aims as in the game */
    else if (lock_input(obj, sp, sx, sy, was_aiming)) return;

    /* Native strafing stays native, whichever preset maps it. */
    if (g_aiming || (buttons & (binding(BIND_STRAFE) | binding(BIND_STRAFE_L) | binding(BIND_STRAFE_R))))
        return;

    float len = sqrt_f(sx * sx + sy * sy);
    if (len < STICK_DEADZONE) return;
    if (len > STICK_MAX) len = STICK_MAX;

    float cam = g_cam_valid ? g_cam_facing : player_facing(obj);
    float facing = cam + DEG(atan2_r(-sx, sy));
    g_target_yaw = wrap180(facing - 90.0f);
    g_active = 1;

    /* Run only once roughly facing the requested direction. */
    float err = RAD(wrap180(g_target_yaw - F32(obj + K->yaw)));
    float along = cos_r(err);
    if (along < 0) along = 0;
    float mag = ((curve_fn)STICK_CURVE)(len / 100.0f, 3, 4.0f, 4.0f);

    SLOT16(sp, DEC_FORWARD) = 1;
    SLOT16(sp, DEC_BACK) = 0;
    SLOT16(sp, DEC_TURN_A) = 0;
    SLOT16(sp, DEC_TURN_B) = 0;
    SLOTF(sp, DEC_FWD_MAG) = mag * along;
}

void ctl_yaw(uint32_t obj, uint32_t dt_bits, uint32_t kind) {
    if (g_hang_state && obj == g_player) { hang_hold(obj); return; }
    if (!g_active || obj != g_player || K != &KINDS[kind & 1]) return;
    union { uint32_t u; float f; } dt = { dt_bits };
    if (!(dt.f > 0.0001f)) return;
    float err = wrap180(g_target_yaw - F32(obj + K->yaw));
    float k = TURN_SPEED * dt.f;
    if (k > 1) k = 1;
    float step = err * k, lim = TURN_MAX_DPS * dt.f;
    if (step > lim) step = lim;
    if (step < -lim) step = -lim;
    F32(obj + K->rate) = step / dt.f;
}

/* The camera takes its pitch from this matrix. On stairs and slopes the game pitches it (up
 * to ~35 deg): running up it looks at the ceiling with Dash at the bottom edge, running down
 * toward the camera it looks at the floor, and even a few degrees get amplified when the
 * camera faces him. Replace the game's pitch (it rebuilds it every update) with ours: level,
 * or tilted toward a locked target above or below. */
static void set_pitch(float *m, float pitch) {
    float fx = m[4], fy = m[5], h = sqrt_f(fx * fx + fy * fy);
    if (h < 1e-4f) return;
    fx /= h; fy /= h;
    float cp = cos_r(RAD(pitch)), sp = sin_r(RAD(pitch));
    m[0] = fy;       m[1] = -fx;      m[2] = 0;    /* right */
    m[4] = fx * cp;  m[5] = fy * cp;  m[6] = sp;   /* facing */
    m[8] = -fx * sp; m[9] = -fy * sp; m[10] = cp;  /* up */
}

void ctl_cam(uint32_t doly, float *m) {
    g_cam_calls++;
    uint32_t target = U32(doly + DOLY_TARGET);
    if (!target || target != g_player || U32(target + OBJ_NAME) != K->tag || U32(CAMERA_OVERRIDE)) return;
    if (g_cam_calls - g_decode_at > CAM_STALE_FRAMES) { g_cam_valid = 0; return; }

    float actual = DEG(atan2_r(m[5], m[4]));   /* row 1 of the player matrix is facing */
    float wall;
    int hang = hang_cam(&wall);
    if ((g_off & OFF_CONTROLS) && !hang) {     /* Cheats: the game's camera (a hang still turns it) */
        g_cam_facing = actual; g_cam_valid = 1; g_cam_pitch = 0;
        return;
    }
    if (!g_cam_valid) { g_cam_facing = actual; g_cam_valid = 1; }
    if (ON_TRAIN) {                      /* stay put relative to the car, not the world */
        float turn = train_car_turn(target);
        g_cam_facing = wrap180(g_cam_facing + turn);
        g_hold_yaw = wrap180(g_hold_yaw + turn);
    }

    int locked = g_aiming && g_lock && target_alive(g_lock);

    float dt = frame_dt();
    float err = wrap180(actual - g_cam_facing);
    float rate = 0;
    if (hang) {               /* hanging: swing round behind him, facing the wall */
        err = wrap180(wall - g_cam_facing);
        rate = CAM_HANG;
    }
    else if (g_aiming) rate = CAM_SNAP;
    else if (g_active) {
        /* Follow by where he is asked to run, not where he faces mid-turn: a 180 toward the
         * camera swings him through sideways, which would drag the camera along for a while. */
        float want = wrap180(g_target_yaw + 90.0f - g_cam_facing);
        rate = CAM_FOLLOW * 0.5f * (1.0f + cos_r(RAD(want)));
    }
    /* Left standing with the camera off his back: after a pause it eases round behind him,
     * like a slow Z press. Running toward the camera keeps g_active, so it still shows his face. */
    if (rate == 0) {
        if (g_idle_t < 10) g_idle_t += dt;
        float t = (g_idle_t - CAM_IDLE_DELAY) / CAM_IDLE_RAMP;
        if (t > 0) rate = CAM_RECENTER * (t < 1 ? t * t * (3 - 2 * t) : 1);
    }
    else g_idle_t = 0;
    float k = rate * dt;
    if (k > 1) k = 1;
    g_cam_facing = wrap180(g_cam_facing + err * k);

    float c = cos_r(RAD(g_cam_facing)), s = sin_r(RAD(g_cam_facing));
    m[0] = s;  m[1] = -c; m[2] = 0;   /* right */
    m[4] = c;  m[5] = s;  m[6] = 0;   /* facing */
    float *cm = (float *)(target + K->cam_matrix);
    /* Locked on a target above or below: tilt the view toward it, or a trooper on a cliff
     * top stays off screen. */
    float want = 0;
    if (locked) {
        float t[3]; target_center(g_lock, t);
        float dx = t[0] - F32(target + OBJ_POS), dy = t[1] - F32(target + OBJ_POS + 4);
        float dz = t[2] - F32(target + OBJ_POS + 8) - CAM_PITCH_EYE;
        want = DEG(atan2_r(dz, sqrt_f(dx * dx + dy * dy))) * CAM_PITCH_PART;
        if (want > CAM_PITCH_UP) want = CAM_PITCH_UP;
        if (want < -CAM_PITCH_DOWN) want = -CAM_PITCH_DOWN;
    }
    float kp = CAM_PITCH_RATE * dt;
    g_cam_pitch += (want - g_cam_pitch) * (kp > 1 ? 1 : kp);
    if (ON_FOOT) {
        /* The native aim (Z, no lock): the stick pitches his gun and the view with it; keep
         * the game's pitch, and ease back to level from it once Z is let go. */
        if (g_aiming && !g_lock && !g_hold) {
            float p = cm[6] > 1 ? 1 : cm[6] < -1 ? -1 : cm[6];
            g_cam_pitch = DEG(atan2_r(p, sqrt_f(1 - p * p)));
            return;
        }
        set_pitch(cm, g_cam_pitch);
        return;
    }
    /* The train camera looks at a point one unit ahead of Dash along this matrix's facing row.
     * Left on his own facing, running toward the camera or a Z swing round to his back puts
     * that point behind the eye: the view turns away from him, into the canyon wall. */
    cm[0] = s;  cm[1] = -c; cm[2] = 0;
    cm[4] = c;  cm[5] = s;  cm[6] = 0;
    cm[8] = 0;  cm[9] = 0;  cm[10] = 1;
}
