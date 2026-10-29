/* Ord Mantell train (player class HumT, optional: build.py --without train leaves it out
 * and the train keeps the game's own controls).
 *
 * Its hooks (hooks.S): the HumT control function's stick decode (0x800AAFC0) and yaw
 * integration (0x800AC9E0), both into the shared core with kind 1 (KINDS[1] in core.c).
 * Here: the train's input freezes, Z resetting the train camera, the drones and troopers as
 * lock-on targets, and the camera turning with the car. */
#include "common.h"

typedef void (*train_behind_fn)(float blend);

/* Input frozen: death/respawn, a message, the ~3.3 s freeze at the level start. */
int train_input_gated(void) {
    return F32(0x800E539C) > 0 || U32(0x800E5838) != 0 || F32(0x800E57B8) > 0;
}

/* The drones (TGun), targets (TTar) and troopers (TTrp) live only in their class's instance
 * array, not in the target pool. The class records sit at these addresses on the train level
 * only: called on the train alone. */
static const uint32_t TRAIN_TARGETS[] = { CLASS_TGUN, CLASS_TTAR, CLASS_TTRP };

void train_targets(void) {
    for (unsigned k = 0; k < sizeof TRAIN_TARGETS / sizeof TRAIN_TARGETS[0]; k++) {
        uint32_t cls = TRAIN_TARGETS[k];
        int n = U32(cls + CLASS_COUNT), size = U32(cls + CLASS_SIZE);
        uint32_t o = U32(cls + CLASS_HEAD);
        if (n <= 0 || n > 256 || size < 0x80 || size > 0x400 || !valid_ptr(o)) continue;
        for (int i = 0; i < n; i++, o += size)
            if (U32(o + OBJ_NAME) == U32(cls)) lock_consider(o);
    }
}

/* Z on the train: the behind view at its usual distance. */
void train_camera_behind(void) {
    if (U32(TRAIN_VIEW) != 1) ((train_behind_fn)TRAIN_BEHIND)(0.0f);
    F32(TRAIN_CAM_DIST) = TRAIN_DIST_STD;
}

/* The car Dash stands on (nearest Trai, at his height), or 0. */
static uint32_t car_under(uint32_t obj) {
    int n = U32(CLASS_TRAI + CLASS_COUNT), size = U32(CLASS_TRAI + CLASS_SIZE);
    uint32_t o = U32(CLASS_TRAI + CLASS_HEAD), car = 0;
    if (n <= 0 || n > 256 || size < 0x80 || size > 0x400 || !valid_ptr(o)) return 0;
    float px = F32(obj + OBJ_POS), py = F32(obj + OBJ_POS + 4), pz = F32(obj + OBJ_POS + 8);
    float best = 40.0f * 40.0f;
    for (int i = 0; i < n; i++, o += size) {
        if (U32(o + OBJ_NAME) != TAG_TRAI) continue;
        float dx = F32(o + OBJ_POS) - px, dy = F32(o + OBJ_POS + 4) - py, dz = F32(o + OBJ_POS + 8) - pz;
        float d = dx * dx + dy * dy;
        if (d < best && dz * dz < 10.0f * 10.0f) { best = d; car = o; }
    }
    return car;
}

static float car_axis(uint32_t car) { return DEG(atan2_r(F32(car + 0x34), F32(car + 0x30))); }

/* Cars turn with the track (up to ~35 deg each way at the level start), carrying Dash round
 * in world space. The lazy camera keeps its own world angle, so standing still or running
 * toward it (when it deliberately holds still) let the car swing out from under it and the
 * eye ended up beside the car, in the canyon wall. Turning the camera with the car keeps it
 * where it was relative to the car. Switching cars is not a turn. */
static uint32_t g_car;
static float g_car_axis;

float train_car_turn(uint32_t obj) {
    uint32_t car = car_under(obj);
    float turn = 0, axis = car ? car_axis(car) : 0;
    if (car && car == g_car) turn = wrap180(axis - g_car_axis);
    g_car = car;
    g_car_axis = axis;
    return turn;
}
