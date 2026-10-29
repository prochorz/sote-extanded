/* Gall Run (gallrun.c): the chase after Slave I, our own free flight (free_fly()); once it has jumped, the final
 * battle on the game's own handling (gall_native.c). The lasers of both (free_lasers()). */
#include "common.h"
#include "gall.h"

float g_free_head;                  /* Chor's heading at the end (it stands still) */
#define ESCAPE_T         2.5f

/* After the route's end the run no longer ends (the user, 2026-10-12): free flight. Chor holds at the end node
 * (the camera's, the TIEs' and the ship's reference); the player flies the Falcon as in stage 1 (stick, A, Z),
 * anywhere, against the cliffs (IMG_COLL holds both stages' and Slave I's pad), not under FREE_LOW below the end's
 * height (the haze: no floor there); up after Slave I into the sky (2026-10-13, the user: the chase goes up into
 * space): no ceiling, and the nose lifted (SKY_ASSIST) while the Falcon is below it. The camera rides behind the
 * ship (trak_draw's flown view), the TIEs chase it along its heading. Blown
 * up, the ship comes back at the end node. Leave through the pause menu. */
#define FREE_LOW         120.0f
/* The player chases Slave I as in stage 1: off its way (the route back) more than STRAY_D, the Falcon is turned back
 * toward it (STRAY_TURN a second, at a point STRAY_AHEAD nodes on); blown up or Slave I got away: back CHASE_GAP behind
 * it on its way. */
#define STRAY_D          500.0f
#define STRAY_TURN       1.2f
#define STRAY_AHEAD      6
#define STRAY_NODES      80         /* (its way behind Slave I looked along for the Falcon's nearest place) */
#define CHASE_GAP        200.0f     /* (slave_pad.py CINE_GAP) */
#define SKY_BELOW        40.0f      /* the Falcon's nose is lifted toward this far under Slave I as it climbs, */
#define SKY_ASSIST       0.004f     /* radians a unit it is lower, */
#define SKY_ASSIST_MAX   0.45f      /* at most (a little over its way up, slave_pad.py SKY_TAN: ~22 degrees) */
#define SKY_PITCH_MAX    0.6f       /* nose up at most, with the stick (1.2 + the stick: the camera was in its hull) */


void free_fly(uint32_t chor, uint32_t node) {
    F32(chor + CHOR_SPEED) = 0;                                  /* Chor holds at the end */
    g_fly_speed = 0;
    if (paused()) return;
    float dt = frame_dt(), here[3];
    for (int i = 0; i < 3; i++) here[i] = F32(chor + 0x50 + 4 * i);
    here[2] -= SHIP_DROP;
    uint32_t stft = player_ship();
    int hp = stft ? (int)U32(stft + STFT_HEALTH) : 0;
    static int last;
    if (!g_free) {                                               /* on from where the route left the ship */
        g_free = 1;
        g_free_head = route_head((float)(node + 1) + F32(chor + CHOR_PARAM));
        for (int i = 0; i < 3; i++) g_fly_pos[i] = here[i] + g_ship_off[i];
        g_fly_yaw = g_free_head - g_ship_yaw; g_fly_pitch = g_ship_pitch;
        if (g_fly_thr <= 0) g_fly_thr = 1;
        last = hp;
    }
    if (g_sl_jump >= 0) { native_fly(chor, stft); return; }    /* Slave I gone to lightspeed: the final battle */
    if (hp > last + RESPAWN_HP || g_lost_t > ESCAPE_T) {         /* blown up, or Slave I got away: back on its tail */
        float l = len3(g_sl_v);
        for (int i = 0; i < 3; i++) g_fly_pos[i] = g_sl[i] - (l > 1e-3f ? g_sl_v[i] / l : 0) * CHASE_GAP;
        g_fly_yaw = g_sl_yaw;
        g_fly_pitch = 0; g_lost_t = 0;
    }
    last = hp;
    g_fly_on = 1;
    run_camera_as(0);                                            /* the view behind the ship, not the gun's (no copy:
                                                                  * firing switches to the gun's every frame, its view
                                                                  * in the hull: copied, the camera jumped into it) */
    g_hit_t += dt;
    g_shake -= g_shake * minf(HIT_SHAKE_EASE * dt, 1);
    float sx = stick(0), sy = stick(1);
    g_fly_yaw -= sx * g_fly_turn * dt;
    if (g_sl_f >= 1) {                                          /* far off Slave I's way (the route back, behind it): */
        float best = 1e12f, a[3], b[3];                          /* turned back toward it (the user: as in stage 1) */
        uint32_t kb = (uint32_t)g_sl_f;
        for (uint32_t k = (uint32_t)g_sl_f; k < (uint32_t)g_sl_f + STRAY_NODES && k + 1 < U32(GALL_RAM + IMG_END); k++) {
            route_pos(k, a);
            float dx = a[0] - g_fly_pos[0], dy = a[1] - g_fly_pos[1], q = dx * dx + dy * dy;
            if (q < best) { best = q; kb = k; }
        }
        if (best > STRAY_D * STRAY_D) {
            route_pos(kb > STRAY_AHEAD ? kb - STRAY_AHEAD : 0, b);  /* (a little on toward Slave I) */
            float want_yaw = atan2_r(b[1] - g_fly_pos[1], b[0] - g_fly_pos[0]), dy = want_yaw - g_fly_yaw;
            dy = wrap_pi(dy);
            g_fly_yaw += dy * minf(STRAY_TURN * dt, 1);
        }
    }
    while (g_fly_yaw - g_free_head > PI_F) g_fly_yaw -= 2 * PI_F;
    while (g_fly_yaw - g_free_head < -PI_F) g_fly_yaw += 2 * PI_F;
    float lift = (g_sl[2] - SKY_BELOW - g_fly_pos[2]) * SKY_ASSIST;   /* up after Slave I: the nose lifted when the */
    lift = lift < 0 ? 0 : lift > SKY_ASSIST_MAX ? SKY_ASSIST_MAX : lift;   /* Falcon falls below it (the player steers) */
    float aim = sy * FLY_PITCH - lift;                           /* (not past SKY_PITCH_MAX nose up: steeper the */
    if (aim < -SKY_PITCH_MAX) aim = -SKY_PITCH_MAX;              /* ship swung round its middle into the camera) */
    g_fly_pitch += (aim - g_fly_pitch) * minf(FLY_PITCH_EASE * dt, 1);
    throttle(dt);
    float v = FLY_V * g_fly_thr, cp = cos_r(g_fly_pitch);
    float dir[3] = { cos_r(g_fly_yaw) * cp, sin_r(g_fly_yaw) * cp, -sin_r(g_fly_pitch) };
    for (int i = 0; i < 3; i++) g_fly_pos[i] += dir[i] * v * dt;
    if (g_fly_pos[2] < here[2] - FREE_LOW) {                    /* the haze's floor, the cliffs' tops: held */
        g_fly_pos[2] = here[2] - FREE_LOW;                       /* the nose levelled */
        if (g_fly_pitch > 0) g_fly_pitch -= g_fly_pitch * minf(FLY_PITCH_EASE * 2 * dt, 1);
    }
    rock(IMG_COLL, dir, v, dt, here, g_free_head, 0, 0);
    for (int i = 0; i < 3; i++) { g_ship_off[i] = g_fly_pos[i] - here[i]; g_ship_at[i] = g_fly_pos[i] + (i == 2 ? SHIP_DROP : 0); }
    float yo = g_fly_yaw - g_free_head;
    yo = wrap_pi(yo);
    g_ship_yaw = -yo;
    g_ship_pitch = g_fly_pitch;
}

/* The space level's gun towers on the Star Destroyer (the user, 2026-10-18): the game's own
 * tower objects (class PRBT) on nodes of ours (space.py towers(): each node its own world-matrix slot, +0x44).
 * towers_show(): our group of their nodes joins the world root's children, as the space level keeps its towers' group: the
 * root's list copied here with it added. The level is loaded again for each run (and finish() loads another), so the
 * root is never put back. */
#define IMG_TOWERS       304        /* count, records {node, x, y, z, yaw}, the template, the pool, their group */
#define WORLD_ROOT       0x8013CE24 /* -> the world tree's root group */
#define ROOT_ROOM        31         /* the root's children we copy at most (the base level's: 15) */
static uint32_t g_root_list[ROOT_ROOM + 1];

void towers_show(void) {
    uint32_t root = U32(WORLD_ROOT), n, l;
    if (!U32(GALL_RAM + IMG_TOWERS) || !root) return;            /* (an older image) */
    n = U32(root + NODE_COUNT); l = U32(root + NODE_LIST);
    if (l == (uint32_t)g_root_list || n > ROOT_ROOM) return;
    for (uint32_t i = 0; i < n; i++) g_root_list[i] = U32(l + 4 * i);
    g_root_list[n] = U32(GALL_RAM + IMG_TOWERS + 16);
    U32(root + NODE_LIST) = (uint32_t)g_root_list;
    U32(root + NODE_COUNT) = n + 1;
}

/* towers_on(): the battle's start (gall_native.c, the game takes the ship): the base level's PRBT record (in its class
 * list with no objects) gets our pool, each a copy of the space level's tower 0 at its place, turned to its yaw, on its node;
 * the game's loop (0x80025D6C) runs them from then on: they aim at the player's ship, fire the game's bolts, are shot
 * down. Once a run (not again after a respawn: the shot-down stay down). towers_off() (native_off()): the record
 * emptied before anything else could run a stale pool. */
#define PRBT_REC         0x80112C28 /* the class record: +8 count, +0xC size, +0x10 pool */
#define PRBT_SIZE        0x214
#define PRBT_POOL2       0x28       /* the pool again (reverse-engineering.md: the class records) */
#define TOWER_PLACE      0x08       /* x, y, z, +0x14 yaw (degrees); +0x20 its 4x4 (rows, then the place, 1); */
#define TOWER_DRAWN      0xB0       /* +0xB0 the same, drawn from (the node, 0x800843F4); +0xE0 its place again */
#define TOWER_NODE       0xF0
/* Their bolts: the spawner (0x80031FE0) takes a slot of the Blst pool by the bolt's kind (its last argument & 0xF)
 * from three s16 tables the level's load fills, kinds 0..5: the next slot, its range's start, its end (the next one
 * wraps to the start on reaching the end exactly: 0x80032358). The tower fires kinds 2, 4, 5 (and 0), which the base level
 * Field has no range for (-1: written before the pool, the game hung); they get the last TOWER_BOLTS of kind 1's range
 * (the TIEs': 20..40 there), kind 1 keeps the rest. */
#define BOLT_NEXT        0x800DD570
#define BOLT_FROM        0x800DD57C
#define BOLT_END         0x800DD588
#define TOWER_BOLTS      8
static int16_t g_bolt_end1;         /* kind 1's end before towers_on() (towers_off() puts it back) */
/* The tower's think spawns two still bolts too (0x8008301C kind 4 in range, 0x80083240 kind 2 every frame, speed 0.01;
 * the shot is 0x800831A0, kind 5): drawn as long flat streaks along the tower's base heading (the space level's point at its hub,
 * inside the station's arms; ours along the hull: the user, 2026-10-19, a stream of green shots sideways). Our think in
 * the record (towers_on(), back in towers_off()) parks them right after the game's, before the draw. */
#define PRBT_THINK       0x18
#define TOWER_STILL      2          /* slots of the tower range for the still kinds 2 and 4 */
#define STILL_V2         1.0f       /* a bolt slower than this (+0x78, squared) is a still one */
static uint32_t g_tower_think;      /* the game's */
/* The towers' line of sight: a standing tower's new bolts (moving, still within LOS_MUZZLE of
 * its muzzle: the game spawns them LOS_UP straight over its +0x50) are parked as the still ones while the Star
 * Destroyer's hull (IMG_SD_COLL) is between the muzzle and the Falcon; the ones further out fly on. Not while the
 * Falcon blows up (state 5 / 6: the game's own). */
#define LOS_UP           100.0f
#define LOS_MUZZLE       50.0f
uint32_t g_los_tests, g_los_parked; /* (probes: seg_hit() calls, bolts parked by it) */
/* The Falcon rammed into a tower (the game's rule as Hoth's snowspeeder meets a PRBT, applied by us:
 * the towers keep +0x140 bit 0x8, so their handler (0x80084528) ignores the speeder's 'plow'; the Stft's own touch of a
 * PRBT, 50000 health, is 0 in the native flight: D15, gall_native.c PRBT_TOUCH). The Falcon's centre
 * within RAM_R of the tower's axis +0x50 .. +0x50 + (0, 0, RAM_UP), at most once per RAM_GAP a tower: the impact f as
 * the speeder's (0x80090AF8: |its forward . the contact normal|, the normal from the axis' nearest point to the ship,
 * 0x80026A94), the tower's health -= 2 x D x f x RAM_SCALE (D 10 / 30 / 50 by difficulty), at <= 0 the game's own blow-up
 * (0x800819E4(obj, 5), the handler's); the Falcon's health -= f x RAM_SHIP (the speeder's for a PRBT). */
#define RAM_R            65.0f      /* (the game's own contact distance: the tower's +0x60 50 + the ship's; D15) */
#define RAM_UP           100.0f
#define RAM_GAP          0.5f
#define RAM_SHIP         50.0f
#define RAM_SCALE        0.2f       /* (x 1 one pass rammed every tower down; medium: 12 a head-on ram, the 4th downs it) */
#define PRBT_SET_STATE   0x800819E4 /* (obj, state): 5 shot down */
#define PRBT_STATE       0x188      /* the handler takes a ram only at != 0 */
#define TOWER_HEALTH     0x1A4      /* float (40 full) */
#define TOWERS_MAX       8
#define RAM_DIFFICULTY   0x8011282A /* u16: 1 / 2 / 3 */
#define RAM_INVINCIBLE   0x800E1B2C /* u32: the debug list's Invincibility (as sd_touch()) */
static float g_ram_since[TOWERS_MAX];
uint32_t g_rams;                    /* (probes: rams applied; the last one's f and the tower's health after it) */
float g_ram_f, g_ram_hp;
static void tower_ram(uint32_t obj) {
    uint32_t pool = U32(GALL_RAM + IMG_TOWERS + 12), i = (obj - pool) / PRBT_SIZE;
    if (obj < pool || i >= TOWERS_MAX || paused()) return;
    g_ram_since[i] += frame_dt();
    uint32_t stft = player_ship();
    if (!valid_ptr(stft) || (U32(obj + 0x140) & 0x10) || !U32(obj + PRBT_STATE) || g_fj_t >= 0) return;
    uint32_t st = U32(stft + STFT_STATE);
    if (st == 5 || st == 6 || g_ram_since[i] < RAM_GAP) return;
    float n[3], z = F32(stft + 0x58), z0 = F32(obj + 0x58);
    z = z < z0 ? z0 : z > z0 + RAM_UP ? z0 + RAM_UP : z;
    n[0] = F32(stft + 0x50) - F32(obj + 0x50); n[1] = F32(stft + 0x54) - F32(obj + 0x54); n[2] = F32(stft + 0x58) - z;
    float d = len3(n);
    if (d >= RAM_R) return;
    float f = 0;
    if (d > 1e-3f) for (int j = 0; j < 3; j++) f += n[j] / d * F32(stft + 0x30 + 4 * j);
    f = absf(f);
    g_ram_since[i] = 0;
    int dif = (int)U16(RAM_DIFFICULTY); dif = dif < 1 ? 1 : dif > 3 ? 3 : dif;
    float hp = F32(obj + TOWER_HEALTH) - 2.0f * (float)(10 + 20 * (dif - 1)) * f * RAM_SCALE;
    F32(obj + TOWER_HEALTH) = hp;
    g_rams++; g_ram_f = f; g_ram_hp = hp;
    if (hp <= 0) ((void (*)(uint32_t, int))PRBT_SET_STATE)(obj, 5);
    if (!U32(RAM_INVINCIBLE)) {
        int s = (int)U32(stft + STFT_HEALTH) - (int)(f * RAM_SHIP + 0.5f);
        U32(stft + STFT_HEALTH) = g_hp_kept = s > 0 ? s : 0;     /* (hp_guard() keeps it) */
    }
}
static void tower_think(uint32_t obj) {
    ((void (*)(uint32_t))g_tower_think)(obj);
    uint32_t rec = blst();
    if (!rec) return;
    uint32_t n = U32(rec + 8), sz = U32(rec + 0xC);
    float from[3] = { F32(obj + 0x50), F32(obj + 0x54), F32(obj + 0x58) + LOS_UP };
    int seen = -1;                                               /* (-1: not tested yet this frame, 0 clear, 1 hidden) */
    for (uint32_t i = 0; i < n && i < 64; i++) {
        uint32_t b = U32(rec + 0x10) + i * sz;
        if (U32(b + 0x64) != obj || F32(b + 0x58) <= -20000.0f) continue;
        float v = F32(b + 0x78) * F32(b + 0x78) + F32(b + 0x7C) * F32(b + 0x7C) + F32(b + 0x80) * F32(b + 0x80);
        if (v < STILL_V2) { F32(b + 0x58) = F32(b + 0x9C) = -30000.0f; continue; }
        if (U32(obj + 0x140) & 0x10) continue;                   /* (shot down) */
        float q[3] = { F32(b + 0x50) - from[0], F32(b + 0x54) - from[1], F32(b + 0x58) - from[2] };
        if (dot3(q, q) > LOS_MUZZLE * LOS_MUZZLE) continue;
        if (seen < 0) {                                          /* (once a frame, only with a new bolt) */
            uint32_t stft = player_ship();
            uint32_t st = stft ? U32(stft + STFT_STATE) : 5;
            seen = 0;
            if (st != 5 && st != 6) { seen = seg_hit(IMG_SD_COLL, from, (const float *)(stft + 0x50)); g_los_tests++; }
        }
        if (seen) { F32(b + 0x58) = F32(b + 0x9C) = -30000.0f; g_los_parked++; }
    }
    tower_ram(obj);
}

void towers_on(void) {
    uint32_t n = U32(GALL_RAM + IMG_TOWERS), recs = U32(GALL_RAM + IMG_TOWERS + 4),
             tmpl = U32(GALL_RAM + IMG_TOWERS + 8), pool = U32(GALL_RAM + IMG_TOWERS + 12);
    if (!n || U32(PRBT_REC + 0x10) == pool) return;              /* (an older image; or on already) */
    for (uint32_t i = 0; i < n; i++) {
        uint32_t o = pool + i * PRBT_SIZE, r = recs + i * 20;
        for (uint32_t k = 0; k < PRBT_SIZE; k += 4) U32(o + k) = U32(tmpl + k);
        U32(o + 4) = (i << 16) | 0x43;                           /* (its index, as the space level's) */
        float yaw = F32(r + 16), c = cos_r(RAD(yaw)), s = sin_r(RAD(yaw));
        float m[16] = { c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, F32(r + 4), F32(r + 8), F32(r + 12), 1 };
        for (int k = 0; k < 3; k++) F32(o + TOWER_PLACE + 4 * k) = F32(o + 0xE0 + 4 * k) = m[12 + k];
        F32(o + TOWER_PLACE + 12) = yaw;
        for (int k = 0; k < 16; k++) F32(o + 0x20 + 4 * k) = F32(o + TOWER_DRAWN + 4 * k) = m[k];
        U32(o + TOWER_NODE) = U32(r);
    }
    int16_t end = S16(BOLT_END + 2), cut = end - TOWER_BOLTS;
    if (end > 0 && cut > S16(BOLT_FROM + 2)) {
        g_bolt_end1 = end;
        S16(BOLT_END + 2) = cut;
        if (S16(BOLT_NEXT + 2) >= cut) S16(BOLT_NEXT + 2) = S16(BOLT_FROM + 2);   /* (or it would run past the end) */
        for (int k = 2; k <= 5; k++)
            if (k != 3 || S16(BOLT_END + 2 * k) < 0) {                      /* (the still ones, 2 and 4, their own */
                int still = k == 2 || k == 4;                                /* slots: they overwrote shots and missiles) */
                int16_t f = still ? cut : cut + TOWER_STILL, t = still ? cut + TOWER_STILL : end;
                S16(BOLT_NEXT + 2 * k) = S16(BOLT_FROM + 2 * k) = f; S16(BOLT_END + 2 * k) = t;
            }   /* (kind 3, the
                                                                  * Falcon's missiles: none here, Z hung the game, 2026-10-19) */
    }
    U32(PRBT_REC + 0x10) = pool;
    U32(PRBT_REC + PRBT_POOL2) = pool;
    if (!g_tower_think) g_tower_think = U32(PRBT_REC + PRBT_THINK);
    if (U32(PRBT_REC + PRBT_THINK) == g_tower_think) U32(PRBT_REC + PRBT_THINK) = (uint32_t)tower_think;                           /* (the missiles' target search reads this one: 0, Z hung
                                                                  * the game) */
    U32(PRBT_REC + 8) = n;
}

/* The towers turned at the player's ship at once (the user, 2026-10-19: they fired at nothing: the game turns a tower
 * ~60 degrees a second from its yaw +0x14 toward atan2(-dx, dy) (0x80082D44) and ours started at 0, the Falcon going by
 * faster). The gun's pitch stays the game's. */
#define TOWER_YAW        0x14
#define DEG_PER_RAD      57.29578f
void towers_aim(uint32_t stft) {
    uint32_t n = U32(GALL_RAM + IMG_TOWERS), pool = U32(GALL_RAM + IMG_TOWERS + 12);
    if (!n || !valid_ptr(stft) || U32(PRBT_REC + 0x10) != pool) return;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t o = pool + i * PRBT_SIZE;
        if (U32(o + 0x140) & 0x10) continue;                     /* (shot down) */
        float dx = F32(stft + 0x50) - F32(o + 0x50), dy = F32(stft + 0x54) - F32(o + 0x54);
        F32(o + TOWER_YAW) = atan2_r(-dx, dy) * DEG_PER_RAD;
    }
}

int towers_left(void) {                                         /* standing towers (the end) */
    uint32_t n = U32(GALL_RAM + IMG_TOWERS), pool = U32(GALL_RAM + IMG_TOWERS + 12), left = 0;
    if (!n || U32(PRBT_REC + 0x10) != pool) return -1;           /* (not on yet) */
    for (uint32_t i = 0; i < n; i++) if (!(U32(pool + i * PRBT_SIZE + 0x140) & 0x10)) left++;
    return (int)left;
}

void towers_off(void) {
    if (!U32(GALL_RAM + IMG_TOWERS) || U32(PRBT_REC + 0x10) != U32(GALL_RAM + IMG_TOWERS + 12)) return;
    U32(PRBT_REC + 8) = 0;
    U32(PRBT_REC + 0x10) = 0;
    U32(PRBT_REC + PRBT_POOL2) = 0;
    if (g_tower_think && U32(PRBT_REC + PRBT_THINK) == (uint32_t)tower_think) U32(PRBT_REC + PRBT_THINK) = g_tower_think;
    if (g_bolt_end1 > 0 && S16(LEVEL_ID) == LEVEL_GALL) {      /* (the mission: another level's load has set its own) */
        if (S16(BOLT_NEXT + 2) >= S16(BOLT_END + 2)) S16(BOLT_NEXT + 2) = S16(BOLT_FROM + 2);
        S16(BOLT_END + 2) = g_bolt_end1;
        for (int k = 2; k <= 5; k++) S16(BOLT_NEXT + 2 * k) = S16(BOLT_FROM + 2 * k) = S16(BOLT_END + 2 * k) = -1;   /* (3 too: none here) */
    }
    g_bolt_end1 = 0;
}

/* The towers' warning and target panel in the final battle, at the draw.
 * A tower within 2500 sends 'TurW' every frame (0x80082D7C): the ship's handler sets the tag TURW_TAG 'Turr' and the
 * HUD update shows element HUD_WARN "Turret Range Warning" (the battle is ~3000 round: always up). Hidden unless a
 * standing tower is within TURW_NEAR ('TBmb', "Incoming Bomb!", on the same element, left alone). The base level has no
 * turret panel (37 shows the TIEs'): flying at a standing tower nearer than any chase TIE ahead, 37 is hidden and the
 * spare text pair (boss_bar()'s: Slave I is gone by now) says "Turret" and its health, yellow as the ship levels'. */
#define TURW_TAG         0x8018E868 /* u32: the ship's last warning message ('Turr', 'TBmb', 'Astr') */
#define TAG_TURR         0x54757272u
#define HUD_WARN         0x36
#define TURW_NEAR        1000.0f
#define TURRET_AIM       1200.0f
#define TURRET_COS       0.94f      /* ~20 degrees off the nose */
#define TOWER_HP         0x1A4      /* float: health (40 full) */
#define TOWER_HP_FULL    40.0f
static float ahead(uint32_t stft, const float *p, float *d) {   /* p's cosine off the ship's nose; its distance in d */
    float v[3], c = 0;
    for (int j = 0; j < 3; j++) v[j] = p[j] - F32(stft + 0x50 + 4 * j);
    *d = len3(v);
    if (*d < 1e-3f) return 0;
    for (int j = 0; j < 3; j++) c += v[j] / *d * F32(stft + 0x30 + 4 * j);
    return c;
}
void battle_hud(uint32_t stft) {
    uint32_t n = U32(GALL_RAM + IMG_TOWERS), pool = U32(GALL_RAM + IMG_TOWERS + 12), aimed = 0;
    static char pct[16];
    static int shown;
    if (!n || !valid_ptr(stft) || U32(PRBT_REC + 0x10) != pool) return;
    float near = 1e9f, best = TURRET_AIM, d;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t o = pool + i * PRBT_SIZE;
        if (U32(o + 0x140) & 0x10) continue;                     /* (shot down) */
        float c = ahead(stft, (const float *)(o + 0x50), &d);
        if (d < near) near = d;
        if (c > TURRET_COS && d < best) { best = d; aimed = o; }
    }
    if (U32(TURW_TAG) == TAG_TURR && near > TURW_NEAR) S16(HUD_POS + 4 * HUD_WARN) = -1000;
    for (int k = 0; aimed && k < TIE_SLOTS; k++) {               /* (a chase TIE ahead and nearer: its panel) */
        uint32_t t = g_chase[k];
        if (t && F32(t + TIE_HEALTH) > 0 && ahead(stft, (const float *)(t + TIE_POS), &d) > TURRET_COS && d < best) aimed = 0;
    }
    target_panel(aimed != 0);
    if (!aimed) {
        if (shown) { ((hud3_fn)HUD_PLACE)(HUD_BOSS_NAME, -1000, -1000); ((hud3_fn)HUD_PLACE)(HUD_BOSS_PCT, -1000, -1000); }
        shown = 0;
        return;
    }
    shown = 1;
    int p = (int)(F32(aimed + TOWER_HP) / TOWER_HP_FULL * 100 + 0.5f);
    p = p < 1 ? 1 : p > 100 ? 100 : p;
    ((sprintf_fn)SPRINTF)(pct, "~f3~o~c%d%%", p);
    ((hudt_fn)HUD_TEXT)(HUD_BOSS_NAME, "~o~cTurret"); ((hudt_fn)HUD_TEXT)(HUD_BOSS_PCT, pct);
    ((hud5_fn)HUD_COLOUR)(HUD_BOSS_NAME, 255, 255, 0, 255); ((hud5_fn)HUD_COLOUR)(HUD_BOSS_PCT, 255, 255, 0, 255);
    ((hud3_fn)HUD_PLACE)(HUD_BOSS_NAME, 240, 175); ((hud3_fn)HUD_PLACE)(HUD_BOSS_PCT, 240, 185);
}
