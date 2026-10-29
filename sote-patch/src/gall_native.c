/* Gall Run (gallrun.c): the final battle after Slave I's jump, on the game's own handling (the space level's: the stick, A, R,
 * the guns, its view keys), from free_fly() (gall_space.c). */
#include "common.h"
#include "gall.h"

int g_native;                       /* (not static: probes) free flight on the game's own (the user, 2026-10-14: as the space level's): native_fly() */
static uint32_t g_native_ship;      /* its ship (free_lasers(): its own guns' bolts) */

/* Free flight after Slave I's jump on the game's own (the user, 2026-10-14: as the space level's, ours was wrong): the
 * player ship (Stft) let go of Chor (+0xAC 0, as the space level's: it flies on its own, the stick, A, the guns, the sight),
 * its handling and speed the game's own, the space level's numbers; the space level's view (sky_camera(): entry 6 on Trak 0). Our offsets off (the Falcon is
 * drawn where the ship is); its place and heading are taken for the rest (the TIEs, the end's fight). */
#define STFT_CARRIED     0xAC       /* 1: Chor carries it (the base level), 0: it flies on its own (the space level) */
#define STFT_FWD         0x30       /* its matrix's forward row */
#define STFT_SPEED       0x9C       /* float: its speed, units a second (docs/reverse-engineering.md) */
#define FLY_BOUND        0x800EC9DC /* float: a free ship is kept this near the level's origin (12000: the battle is
                                     * further, the ship was put on that sphere, 8000 off; the game's data, set back
                                     * by native_off()) */
#define FLY_BOUND_NATIVE 60000.0f
static float g_bound_save;
#define PRBT_TOUCH       0x800EC9F8 /* float: the Stft's health cost of touching a PRBT (50000, the Stft update 0x8009B9B0's
                                     * PRBT case, its only reader in the main program): 0 in the native flight, a ram is
                                     * ours there (tower_ram()); set back by native_off() */
static float g_touch_save;
void native_off(void) {
    towers_off();                                                /* (the Star Destroyer's gun towers: gall_space.c) */
    if (g_bound_save > 0) { F32(FLY_BOUND) = g_bound_save; g_bound_save = 0; }
    if (g_touch_save > 0) { F32(PRBT_TOUCH) = g_touch_save; g_touch_save = 0; }
}
/* The Star Destroyer's hull in native flight as the space level's (the user, 2026-10-15; the game's own tests need the space level's
 * sector record, docs/reverse-engineering.md): the ship's centre held SD_KEEP off its triangles (IMG_SD_COLL); met more
 * than 45 degrees off the surface it is destroyed (health 0, not with the game's Invincibility), shallower it slides
 * along it, a new touch costing SD_GRAZE + 0..SD_GRAZE health with the game's scrape. */
#define SD_KEEP          24.0f
#define SD_CRASH         0.707f
#define SD_GRAZE         10
#define INVINCIBLE       0x800E1B2C /* u32: the debug list's Invincibility */
static void sd_touch(uint32_t stft, float *dir) {
    static uint32_t last;
    static const float ax[3][3] = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } }, r[3] = { SD_KEEP, SD_KEEP, SD_KEEP };
    float n[3];
    if (paused() || collide(IMG_SD_COLL, g_fly_pos, ax, r, n) <= 0) return;
    float dn = dot3(dir, n);
    if (-dn > SD_CRASH) { if (!U32(INVINCIBLE)) U32(stft + STFT_HEALTH) = 0; }
    else if (g_ov_frames - last > SL_COOL) {
        int hp = (int)U32(stft + STFT_HEALTH) - SD_GRAZE - (int)(g_ov_frames * 7 % (SD_GRAZE + 1));
        if (!U32(INVINCIBLE)) U32(stft + STFT_HEALTH) = g_hp_kept = hp > 0 ? hp : 0;   /* (hp_guard() keeps it) */
        ((sfx_fn)SFX)(SND_SCRAPE, 6, 0x3F800000u, 0x6590, 0);
    }
    last = g_ov_frames;
    if (dn < 0) for (int i = 0; i < 3; i++) dir[i] -= n[i] * dn;   /* slid along it */
}

/* The space level's view in native flight (the user; docs/reverse-engineering.md, the space level's view): camera entry 6 on Trak 0,
 * Trak 0 on the ship 20 over it, its distance by the ship's speed every frame as the game's 'dist' message has it
 * (sent only with the space level's sector record). Seeded with the ship's rows and an eye behind it (no fly-in). */
#define TRAK_SPEED       0x64
#define TRAK_PLACE       0x74       /* the target's place + its offset */
#define TRAK_OFFS        0x90       /* offset over the target (world axes) */
#define TRAK_FLAGS       0x9C       /* s16 */
#define SKY_UP           20.0f
#define SKY_BEHIND       95.0f
#define DIFFICULTY       0x8011282A /* u16 */
#define VIEW_KEY_WAIT    0x800E1B04 /* s16: the view key works only at 0 (2 at a press, down while up: docs/reverse-engineering.md) */
/* The space level's views on the view binding (through the view keys gate: 6 -> 4 -> 5 -> 4, docs/reverse-engineering.md,
 * The space level's view keys): the base level's entries 4 and 5 are the gun's, given the space level's words (+0x54..+0x68): 4 the
 * cockpit on the ship's rows (23.5, 6.0), 5 behind the ship on Trak 0 as entry 6. */
const uint32_t SKY_VIEWS[2][6] = { { 0x41BC0000u, 0x40C00000u, 0, 0, 0, 0 }, { 0, 0, 0, 0, 0, 0 } };
static void sky_camera(uint32_t stft, int idx) {                /* (idx: the entry switched to) */
    uint32_t t = U32(CLASS_TRAK + 0x10), ent = U32(CAMERA_ENTRIES);
    if (!U32(CLASS_TRAK + 8) || !valid_ptr(t) || !valid_ptr(ent)) return;
    ent += CAM_SKY * 0x80;
    U32(t + TRAK_TARGET) = stft;
    F32(t + TRAK_OFFS) = 0; F32(t + TRAK_OFFS + 4) = 0; F32(t + TRAK_OFFS + 8) = SKY_UP;
    U16(t + TRAK_FLAGS) = 0x0008;
    for (int i = 0x20; i < 0x50; i += 4) U32(t + i) = U32(stft + i);   /* its rows */
    for (int i = 0; i < 3; i++) {
        float p = F32(stft + 0x50 + 4 * i);
        F32(t + TRAK_EYE + 4 * i) = F32(t + 0x08 + 4 * i) = p - F32(stft + STFT_FWD + 4 * i) * SKY_BEHIND + (i == 2 ? SKY_UP : 0);
        F32(t + TRAK_PLACE + 4 * i) = p;
    }
    F32(t + TRAK_SPEED) = F32(stft + STFT_SPEED);
    U32(ent + 8) = t + TRAK_MATRIX;
    for (int i = 0x54; i < 0x6C; i += 4) U32(ent + i) = 0;
    for (int i = 0; i < 0x40; i += 4) U32(ent + 0x14 + i) = U32(t + TRAK_MATRIX + i);
    uint32_t e4 = ent - 2 * 0x80;                                /* (entries 4 and 5) */
    U32(e4 + 8) = stft + 0x20; U32(e4 + 0x80 + 8) = t + TRAK_MATRIX;
    for (int i = 0; i < 6; i++) { U32(e4 + 0x54 + 4 * i) = SKY_VIEWS[0][i]; U32(e4 + 0x80 + 0x54 + 4 * i) = SKY_VIEWS[1][i]; }
    ((setcam_fn)CAM_SWITCH)(idx);
}
/* The free flight's first start eased in from the rail's last view: the game's switch to Trak 0's
 * view stands; our carry goes onto Trak 0's matrix after the game's Trak update each frame (trak_update: its own view
 * put back before the next one), and onto the entry the first frame. A respawn: the cut. */
carry_t g_sky_carry;
float g_sky_own[16];                /* Trak 0's own view under the carry (trak_update) */
void sky_carry(uint32_t t) {
    float eye[3], f[3], fal[3];
    for (int i = 0; i < 16; i++) g_sky_own[i] = F32(t + TRAK_MATRIX + 4 * i);
    for (int i = 0; i < 3; i++) { eye[i] = F32(t + TRAK_EYE + 4 * i); f[i] = 100 * F32(t + TRAK_MATRIX + 0x10 + 4 * i); }
    falcon_place(fal);
    carry_on(&g_sky_carry, eye, f, fal);
    view_set(t, eye, f);
}
static float sky_pace(uint32_t stft) {                          /* the ship's speed: 0 at its low (R), 1 at 500 (A), */
    float low = 200.0f + 75.0f * (float)((int)U16(DIFFICULTY) - 1);   /* 0.5 no button (docs/reverse-engineering.md) */
    return (F32(stft + STFT_SPEED) - low) / (500.0f - low);
}
static void sky_dist(uint32_t stft) {
    uint32_t t = U32(CLASS_TRAK + 0x10);
    if (!U32(CLASS_TRAK + 8) || !valid_ptr(t) || U32(t + TRAK_TARGET) != stft) return;
    F32(t + TRAK_DIST) = 60.0f + 70.0f * sky_pace(stft);
}

static void stft_face(uint32_t stft, float *f) {                /* the ship's rows for a forward f, level (the game */
    float l = len3(f);     /* makes its angles from them) */
    if (l <= 1e-3f) return;
    for (int i = 0; i < 3; i++) f[i] /= l;
    float h = sqrt_f(f[0] * f[0] + f[1] * f[1]);
    if (h < 1e-3f) return;
    float u[3] = { -f[0] * f[2] / h, -f[1] * f[2] / h, h };       /* (up: square to it, over it) */
    float r[3] = { f[1] * u[2] - f[2] * u[1], f[2] * u[0] - f[0] * u[2], f[0] * u[1] - f[1] * u[0] };
    for (int i = 0; i < 3; i++) {                                /* (rows: right = forward x up, forward, up) */
        F32(stft + 0x20 + 4 * i) = r[i]; F32(stft + STFT_FWD + 4 * i) = f[i]; F32(stft + 0x40 + 4 * i) = u[i];
    }
}
#define MISSILE_LOCK     0x800DEED4 /* float: seconds till missiles may fire */
#define MISSILES         0x800E1B54 /* s16: missiles left (5) */
#define RESPAWN_T        0x800E1B6C /* float: the game's respawn timer (1.5 at the Stft's init, down to -0.5: the view to
                                     * VIEW_MODE every frame and the view keys off while above) */
#define STFT_STATE_T     0x234      /* float: seconds in its state (the game's) */
#define STFT_DEATH_5     0x238      /* int: state 5's length, s (3, set at its entry) */
#define DEATH_5_LEFT     1.25f      /* state 5's seconds left at its start (1.5 gave 3.6 s death to respawn: its clock runs
                                     * ~0.83x real time, ~1.5 s of the explosion; its length +0x238 is an int, 3: +0x234
                                     * put at 3 - 1.25) */
#define DEATH_FROM       1.85f      /* state 6's seconds at its start (~3 s death to respawn; 0.7 (8c D8) gave
                                     * no explosion seen) */
#define RESPAWN_HOLD     30         /* frames after a respawn the view is held on CAM_SKY (the game's entry 5 comes ~20 on) */
#define NATIVE_PACE      0.55f      /* the ship goes this share of the game's way (2026-10-19: still too fast, the user; was 0.774. 2026-10-17: the space level's 387.5 a
                                     * second, no button, was the boost before it, FLY_V * FLY_BOOST: now 300, A 387, R 213) */
#define GLOW_SLOW        0.8f       /* the engine glow's width at the ship's low speed (R), */
#define GLOW_FAST        2.1f       /* at 500 (A); the game's own (1..2, +0.15 flicker) hardly changed (falcon.c g_glow_w) */
#define STFT_GLOW_W        0xC8       /* s16: the glow's width x 1000, the game's (with its flicker) */
/* The final battle: the player's lasers (class Blst, Chor's: +0x64 its owner) come out of the guns of the ship the game
 * thinks is at Chor (held at the rail's end), along its heading. Each new one (still by Chor) is put at the Falcon's
 * nose and turned along its way (the user: shoot the TIEs ahead). Blst: +0x50 place, +0x78 and +0x84 its velocity
 * (two scales), +0x94 its last place, +0xA0 its unit heading. */
#define LASER_NEW        400.0f     /* a laser this near the Falcon, not along its way yet, is new (it flies ~100 a frame) */
#define LASER_AHEAD      22.0f
#define LASER_SIDE       9.0f
#define LASER_SPAN       130.0f     /* our hit test: a bolt's last this much of way (~100 a frame) */
#define LASER_HIT        16.0f      /* within this of a TIE (~10 across, its wings ~20), */
#define LASER_DAMAGE     1.5f       /* this off its health (10: seven hits; one each was 10 down in 2 s, three 10 s, four */
#define LASER_COOL       12         /* 15 in 8 s: the bot), not again within this many frames (bolts come thick) */
#define AIM_COS          0.985f     /* aim help: a TIE within ~10 degrees of the nose, */
#define AIM_FAR          1500.0f    /* this near */
static uint32_t g_laser_done[16], g_laser_at[16], g_laser_n;
static void free_lasers(uint32_t chor) {
    uint32_t rec = blst();
    if (!rec || !valid_ptr(U32(rec + 0x10))) return;
    float cp = cos_r(g_fly_pitch), h[3] = { cos_r(g_fly_yaw) * cp, sin_r(g_fly_yaw) * cp, -sin_r(g_fly_pitch) };
    float rt[2] = { h[1], -h[0] }, nose[3] = { h[0], h[1], h[2] };
    static int side;
    {                                                            /* a little aim help (the nose turns slowly: TIEs */
        float best = AIM_COS;                                    /* hard to hit, the bot): a TIE of the chase within */
        for (int k = 0; k < TIE_SLOTS; k++) {                    /* AIM_COS of the nose: the lasers at it */
            uint32_t t = g_chase[k];
            if (!t || !(F32(t + TIE_HEALTH) > 0)) continue;
            float v[3], l = 0, c = 0;
            for (int j = 0; j < 3; j++) { v[j] = F32(t + TIE_POS + 4 * j) - g_fly_pos[j]; l += v[j] * v[j]; }
            l = sqrt_f(l);
            if (l < 30 || l > AIM_FAR) continue;
            for (int j = 0; j < 3; j++) c += v[j] / l * h[j];
            if (c > best) { best = c; for (int j = 0; j < 3; j++) h[j] = v[j] / l; }
        }
    }
    uint32_t tg[TIE_SLOTS + 3], nt = 0;                          /* the targets: the chase, the bombers flown, our bomb */
    for (int k = 0; k < TIE_SLOTS; k++) tg[nt++] = g_chase[k];
    if (U32(CLASS_TIEF + 8) > BOMB_OBJ)
        for (int k = 10; k <= BOMB_OBJ; k += k == 11 ? 3 : 1) {
            uint32_t o = U32(CLASS_TIEF + 0x10) + (uint32_t)k * U32(CLASS_TIEF + 0xC);
            tg[nt++] = bomb_fly(o) ? o : 0;
        }
    uint32_t n = U32(rec + 8), sz = U32(rec + 0xC);
    for (uint32_t i = 0; i < n && i < 64; i++) {
        uint32_t b = U32(rec + 0x10) + i * sz;
        if (U32(b + 0x64) != chor && U32(b + 0x64) != g_native_ship) continue;
        if (U32(b + 0x64) == chor) {                 /* native: the ship's own guns fire; Chor's turret */
            if (F32(b + 0x58) > -20000.0f) F32(b + 0x58) = F32(b + 0x9C) = -30000.0f;   /* (B fires it too) put away */
            continue;
        }
        for (uint32_t k = 0; k < nt; k++) {                      /* our own hit test (the game's tests the TIEs near */
            uint32_t t = tg[k];                                  /* Chor only: it never hit by the battle): its last */
            if (!t || !(F32(t + TIE_HEALTH) > 0)) continue;      /* LASER_SPAN of way within LASER_HIT of a TIE */
            float w[3], a = 0, q = 0;
            for (int j = 0; j < 3; j++) { w[j] = F32(t + TIE_POS + 4 * j) - F32(b + 0x50 + 4 * j); a += w[j] * F32(b + 0xA0 + 4 * j); }
            if (a > 0 || a < -LASER_SPAN) continue;
            for (int j = 0; j < 3; j++) { float e = w[j] - a * F32(b + 0xA0 + 4 * j); q += e * e; }
            if (q > LASER_HIT * LASER_HIT) continue;
            static uint32_t hit_at[TIE_SLOTS + 3];
            if (g_ov_frames - hit_at[k] < LASER_COOL) continue;
            hit_at[k] = g_ov_frames;
            if (k == nt - 1 && nt > TIE_SLOTS) { S16(t + TIE_STATE) = -1; g_bomb_fly = 0; }   /* our bomb: its burst, no harm */
            else F32(t + TIE_HEALTH) -= LASER_DAMAGE;
            F32(b + 0x58) = F32(b + 0x9C) = -30000.0f;           /* (the bolt gone: its last place too, else a streak */
            for (int j = 0; j < 2; j++) F32(b + 0x94 + 4 * j) = F32(b + 0x50 + 4 * j);   /* drawn down to it) */
            break;
        }
        float d = 0, dc = 0, al = 0;                             /* (new: by the ship or by Chor, not yet along its way: */
        for (int j = 0; j < 3; j++) {                            /* the game fires them from Chor's guns, held at the */
            float u = F32(b + 0x50 + 4 * j) - g_fly_pos[j], w = F32(b + 0x50 + 4 * j) - F32(chor + 0x50 + 4 * j);   /* rail's */
            d += u * u; dc += w * w;                             /* end: the Falcon thousands off it by the battle, */
        }                                                        /* its lasers went nowhere) */
        for (int j = 0; j < 3; j++) al += F32(b + 0xA0 + 4 * j) * nose[j];
        if ((d > LASER_NEW * LASER_NEW && dc > LASER_NEW * LASER_NEW) || (d <= LASER_NEW * LASER_NEW && al > 0.995f)) continue;
        int seen = 0;                                            /* (each once: the aimed ones are off the nose's way) */
        for (int q = 0; q < 16; q++) if (g_laser_done[q] == b && g_ov_frames - g_laser_at[q] < 90) seen = 1;
        if (seen) continue;
        g_laser_done[g_laser_n & 15] = b; g_laser_at[g_laser_n & 15] = g_ov_frames; g_laser_n++;
        float v1 = 0, v2 = 0, sd = (side ^= 1) ? LASER_SIDE : -LASER_SIDE;
        for (int j = 0; j < 3; j++) { v1 += F32(b + 0x78 + 4 * j) * F32(b + 0x78 + 4 * j); v2 += F32(b + 0x84 + 4 * j) * F32(b + 0x84 + 4 * j); }
        v1 = sqrt_f(v1); v2 = sqrt_f(v2);
        for (int j = 0; j < 3; j++) {
            float p = g_fly_pos[j] + h[j] * LASER_AHEAD + (j < 2 ? rt[j] * sd : -SHIP_DROP);
            F32(b + 0x50 + 4 * j) = p; F32(b + 0x94 + 4 * j) = p;
            F32(b + 0xA0 + 4 * j) = h[j]; F32(b + 0x78 + 4 * j) = h[j] * v1; F32(b + 0x84 + 4 * j) = h[j] * v2;
        }
    }
}

/* The bound round the fight (the user, 2026-10-18: far from it all went wrong, the Falcon even upside down; a bound
 * only, no line): past BOUND_R from the battle's middle the ship's nose is turned to it, harder further out (over
 * BOUND_RAMP), its climb or dive held to 30 degrees (BOUND_TAN); past BOUND_MAX it is put back on that sphere. */
#define BOUND_R          3000.0f
#define BOUND_RAMP       600.0f
#define BOUND_TURN       1.2f       /* radians a second, at BOUND_R + BOUND_RAMP and out */
#define BOUND_TAN        0.577f     /* the nose at most 30 degrees up or down while turned (its z share 0.5) */
#define BOUND_MAX        (BOUND_R + BOUND_RAMP + 400.0f)
static int bound(float *dir) {
    float to[3], d = 0;
    for (int i = 0; i < 3; i++) { to[i] = F32(GALL_RAM + IMG_BATTLE + 4 * i) - g_fly_pos[i]; d += to[i] * to[i]; }
    d = sqrt_f(d);
    if (d <= BOUND_R || paused()) return 0;
    for (int i = 0; i < 3; i++) to[i] /= d;
    if (d > BOUND_MAX) for (int i = 0; i < 3; i++) g_fly_pos[i] += to[i] * (d - BOUND_MAX);
    float k = BOUND_TURN * minf((d - BOUND_R) / BOUND_RAMP, 1) * frame_dt();
    for (int i = 0; i < 3; i++) dir[i] += (to[i] - dir[i]) * minf(k, 1);
    float h = sqrt_f(dir[0] * dir[0] + dir[1] * dir[1]), l;
    if (dir[2] > BOUND_TAN * h) dir[2] = BOUND_TAN * h;
    if (dir[2] < -BOUND_TAN * h) dir[2] = -BOUND_TAN * h;
    l = len3(dir); if (l < 1e-3f) return 0;
    for (int i = 0; i < 3; i++) dir[i] /= l;
    return 1;
}

/* The Falcon's jump to lightspeed at the end: the view held where it was (the sky entry given a
 * copy of the Trak's matrix to follow), the ship shot ahead along its nose (FJ_GO over FJ_T, faster and faster), the
 * screen white over its last FJ_FLASH; 1 when done (finish(): the last scene). */
#define FJ_GO            9000.0f    /* (3000 over 1.6 s: flown straight off along the view, a dot too soon) */
#define FJ_FLASH         0.5f
#define FJ_SIDE_T        0.5f       /* the held eye eased off the Falcon's line over these seconds, then held (from its */
#define FJ_SIDE          80.0f      /* line it only shrank in the centre; 120 / 60 lost it off the frame by 0.7 s): this far right */
#define FJ_UP            40.0f      /* and up (its frame at the jump's start), looking at the start of its path */
#define FJ_LOOK          0.15f      /* the look: this share of FJ_GO along the nose (the path's middle: ~2 px less screen move) */
float g_fj_t = -1;                  /* seconds into it (-1: not; gallrun.c resets it with the run) */
static float g_fj_cam[16];          /* the held view (a Trak matrix: right, forward, up, eye) */
static float g_fj_eye[6];           /* the held eye at the jump's start, the eye moved off the line */
static float g_fj_fwd[3];           /* the held view's forward at the jump's start */
static float g_fj_look[3];          /* the start of the Falcon's path (g_fj_from + nose x FJ_GO x FJ_LOOK): the look */
float g_fj_from[3];                 /* where it began (gall_story.c trail(): the white trail from here to the ship) */
int fly_jump(float dt) {
    uint32_t stft = g_native_ship, t = U32(CLASS_TRAK + 0x10), ent = U32(CAMERA_ENTRIES);
    if (!valid_ptr(stft) || !valid_ptr(t) || !valid_ptr(ent)) return 1;
    ent += CAM_SKY * 0x80;
    if (g_fj_t < 0) {
        g_fj_t = 0;
        for (int i = 0; i < 16; i++) g_fj_cam[i] = F32(t + TRAK_MATRIX + 4 * i);
        for (int i = 0; i < 3; i++) {
            g_fj_from[i] = F32(stft + 0x50 + 4 * i);
            g_fj_fwd[i] = g_fj_cam[4 + i];
            g_fj_eye[i] = g_fj_cam[12 + i];
            g_fj_eye[3 + i] = g_fj_eye[i] + F32(stft + 0x20 + 4 * i) * FJ_SIDE + F32(stft + 0x40 + 4 * i) * FJ_UP;
            g_fj_look[i] = g_fj_from[i] + F32(stft + STFT_FWD + 4 * i) * (FJ_GO * FJ_LOOK);
        }
    }
    U32(ent + 8) = (uint32_t)g_fj_cam;
    U32(stft + STFT_HEALTH) = 495;                               /* (no harm in it) */
    g_fj_t += dt;
    float s = g_fj_t / FJ_SIDE_T, eye[3], f[3], l;               /* (eased in and out, the look turned with it) */
    s = s > 1 ? 1 : s; s = s * s * (3 - 2 * s);
    for (int i = 0; i < 3; i++) { eye[i] = g_fj_eye[i] + (g_fj_eye[3 + i] - g_fj_eye[i]) * s; f[i] = g_fj_look[i] - eye[i]; }
    l = len3(f);
    if (l > 1e-3f) {
        for (int i = 0; i < 3; i++) f[i] = g_fj_fwd[i] + (f[i] / l - g_fj_fwd[i]) * s;
        view_set((uint32_t)g_fj_cam - TRAK_MATRIX, eye, f);
    }
    float u = g_fj_t / FJ_T; u = u > 1 ? 1 : u; u *= u;
    for (int i = 0; i < 3; i++) F32(stft + 0x08 + 4 * i) = F32(stft + 0x50 + 4 * i) = g_fj_from[i] + F32(stft + STFT_FWD + 4 * i) * FJ_GO * u;
    float w = (g_fj_t - (FJ_T - FJ_FLASH)) / FJ_FLASH;
    if (w > 0) { S16(SCREEN_FADE) = S16(SCREEN_FADE + 2) = S16(SCREEN_FADE + 4) = 255; S16(SCREEN_FADE + 6) = (int16_t)(255 * (w > 1 ? 1 : w)); }
    return g_fj_t >= FJ_T + 0.2f;
}

/* The fly-away: all towers down (Lando's line not held: a hold stopped the fly-away), for
 * AWAY_T (gall.h) the stick and the buttons are off the pad but A, held for full speed (gallrun_pad(); 5c D8), and the
 * ship's nose is turned at AWAY_TURN onto the Star Destroyer's long axis line, then along it toward the stern (flown
 * away from the battle's middle or nose up, the view behind it lost the hull; toward the bow the hull narrows and drops;
 * the axis the principal flat axis of IMG_SD_COLL's vertices through their flat centre, sd_axis() at the battle's start; the stern
 * the end where their max z lies, the bridge tower), its height the hull's top under it (max z of the vertices within
 * AWAY_UNDER_R on the flat, every frame; none: the last one, at first the hull's top) + AWAY_HIGH, climbed or dived to at
 * most AWAY_CLIMB (the nose's pitch held within it: the turn onto the line spiked it to 61 deg): the view behind the Falcon (the game's) has the hull below it; then the jump (finale()). The way onto
 * the line: square to it till within the ship's turn radius (its pace / AWAY_TURN), then the arc of that radius that
 * meets it tangent. 1 while it runs. */
#define AWAY_TURN        3.0f       /* radians a second (5c D8; 1.5 took 2 of the 3 s, flown toward the battle) */
#define AWAY_CLIMB_SIN   0.25882f   /* AWAY_CLIMB 15 deg: its sin (a 53 deg climb left the hull below the frame) */
#define AWAY_HIGH        250.0f     /* over the hull's top under the Falcon */
#define AWAY_UNDER_R     200.0f     /* the hull's top under it: its vertices this near on the flat */
#define COLL_TRI         24         /* (gall_fly.c's: a triangle, 9 s16 vertex coordinates, 3 s16 normal) */
float g_sd_axis[2], g_sd_mid[2], g_sd_top;   /* the hull's long axis on the flat (unit, toward the stern), its flat */
float g_away_under;                          /* centre, its top z (probes); the top under the Falcon */
void sd_axis(void) {                /* once (the hull does not move): mean, then the flat covariance's main eigenvector */
    uint32_t c = U32(GALL_RAM + IMG_SD_COLL);
    if (!c || g_sd_axis[0] != 0 || g_sd_axis[1] != 0) return;
    uint32_t n = U32(c) * 3, tris = U32(c + 4);
    if (!n) return;
    float mx = 0, my = 0, xx = 0, yy = 0, xy = 0, top = -1e9f, tx = 0, ty = 0;
    for (uint32_t k = 0; k < n; k++) {
        uint32_t v = tris + COLL_TRI * (k / 3) + 6 * (k % 3);
        float x = (float)(int16_t)U16(v), y = (float)(int16_t)U16(v + 2), z = (float)(int16_t)U16(v + 4);
        mx += x; my += y;
        if (z > top) { top = z; tx = x; ty = y; }
    }
    mx /= (float)n; my /= (float)n;
    for (uint32_t k = 0; k < n; k++) {
        uint32_t v = tris + COLL_TRI * (k / 3) + 6 * (k % 3);
        float dx = (float)(int16_t)U16(v) - mx, dy = (float)(int16_t)U16(v + 2) - my;
        xx += dx * dx; yy += dy * dy; xy += dx * dy;
    }
    float h = (xx - yy) / 2, e = (xx + yy) / 2 + sqrt_f(h * h + xy * xy), ax = xy, ay = e - xx, l;
    if (ax * ax + ay * ay < 1e-6f * (e * e + 1)) { ax = e - yy; ay = xy; }
    l = sqrt_f(ax * ax + ay * ay);
    if (l < 1e-6f) { ax = 1; ay = 0; l = 1; }
    if ((tx - mx) * ax + (ty - my) * ay < 0) l = -l;             /* (toward the stern: the top's end) */
    g_sd_axis[0] = ax / l; g_sd_axis[1] = ay / l; g_sd_mid[0] = mx; g_sd_mid[1] = my; g_sd_top = g_away_under = top;
}
static void sd_under(float x, float y) {   /* the hull's top within AWAY_UNDER_R of (x, y) on the flat into g_away_under */
    uint32_t c = U32(GALL_RAM + IMG_SD_COLL);
    if (!c) return;
    uint32_t n = U32(c) * 3, tris = U32(c + 4);
    float top = -1e9f;
    for (uint32_t k = 0; k < n; k++) {
        uint32_t v = tris + COLL_TRI * (k / 3) + 6 * (k % 3);
        float dx = (float)(int16_t)U16(v) - x, dy = (float)(int16_t)U16(v + 2) - y, z = (float)(int16_t)U16(v + 4);
        if (dx * dx + dy * dy <= AWAY_UNDER_R * AWAY_UNDER_R && z > top) top = z;
    }
    if (top > -1e9f) g_away_under = top;
}
float g_away_t = -1;                /* seconds into it (-1: not; gallrun.c resets it with the run) */
int fly_away(float dt) {
    uint32_t stft = g_native_ship;
    if (!valid_ptr(stft)) return 0;
    float t[3], f[3], l, c = 0, a = AWAY_TURN * dt;
    if (g_away_t < 0) { g_away_t = 0; sd_axis(); }
    if (g_away_t >= AWAY_T) return 0;
    g_away_t += dt;
    float x = F32(stft + 0x50), y = F32(stft + 0x54), z = F32(stft + 0x58);
    float px = -g_sd_axis[1], py = g_sd_axis[0];                 /* (the line's side: lat > 0 on +p) */
    float lat = (x - g_sd_mid[0]) * px + (y - g_sd_mid[1]) * py, al = lat < 0 ? -lat : lat;
    float v = F32(stft + STFT_SPEED) * NATIVE_PACE, r = v / AWAY_TURN, sn, cs;
    if (r < 1) r = 1;
    if (al >= r) { cs = 0; sn = 1; }                             /* (square to the line, then its tangent arc) */
    else { cs = 1 - al / r; sn = sqrt_f(1 - cs * cs); }
    if (lat > 0) sn = -sn;
    t[0] = g_sd_axis[0] * cs + px * sn; t[1] = g_sd_axis[1] * cs + py * sn;
    sd_under(x, y);
    float dz = g_away_under + AWAY_HIGH - z, step = v * dt, tz = step > 1e-3f ? dz / step : 0;
    tz = tz > AWAY_CLIMB_SIN ? AWAY_CLIMB_SIN : tz < -AWAY_CLIMB_SIN ? -AWAY_CLIMB_SIN : tz;
    float k = sqrt_f(1 - tz * tz);
    t[0] *= k; t[1] *= k; t[2] = tz;
    for (int i = 0; i < 3; i++) f[i] = F32(stft + STFT_FWD + 4 * i);
    l = len3(f); if (l < 1e-3f) return 1;
    for (int i = 0; i < 3; i++) { f[i] /= l; c += f[i] * t[i]; }
    if (c >= cos_r(a)) for (int i = 0; i < 3; i++) f[i] = t[i];
    else {                                                       /* (turned at most a toward it) */
        float q[3], ql;
        for (int i = 0; i < 3; i++) q[i] = t[i] - c * f[i];
        ql = len3(q);
        if (ql > 1e-3f) for (int i = 0; i < 3; i++) f[i] = f[i] * cos_r(a) + q[i] / ql * sin_r(a);
    }
    if (f[2] > AWAY_CLIMB_SIN || f[2] < -AWAY_CLIMB_SIN) {       /* (the pitch held within AWAY_CLIMB all the way: */
        float h = sqrt_f(f[0] * f[0] + f[1] * f[1]), z = f[2] > 0 ? AWAY_CLIMB_SIN : -AWAY_CLIMB_SIN;   /* the turn's */
        float g = sqrt_f(1 - z * z);                             /*  great circle went up to 61 deg) */
        if (h < 1e-3f) { f[0] = t[0]; f[1] = t[1]; h = sqrt_f(t[0] * t[0] + t[1] * t[1]); }
        if (h > 1e-3f) { f[0] *= g / h; f[1] *= g / h; f[2] = z; }
    }
    stft_face(stft, f);
    return 1;
}

/* A respawn (not the battle's start) away from the Star Destroyer (the user, 2026-10-19: it came back by the hull, under
 * the towers' fire): RESPAWN_OUT from the battle's middle on Chor's side,
 * level, RESPAWN_UP over it (within BOUND_R: no bound turn on arrival); the entry then faces it to the battle. */
#define RESPAWN_OUT      2800.0f
#define RESPAWN_UP       300.0f
float g_respawn_at[3];              /* (probes) */
static void respawn_out(uint32_t stft, uint32_t chor) {
    float m[3], dx, dy, l;
    for (int i = 0; i < 3; i++) m[i] = F32(GALL_RAM + IMG_BATTLE + 4 * i);
    dx = F32(chor + 0x50) - m[0]; dy = F32(chor + 0x54) - m[1]; l = sqrt_f(dx * dx + dy * dy);
    if (l < 1) { dx = 1; dy = 0; l = 1; }
    g_respawn_at[0] = m[0] + dx / l * RESPAWN_OUT; g_respawn_at[1] = m[1] + dy / l * RESPAWN_OUT; g_respawn_at[2] = m[2] + RESPAWN_UP;
    for (int i = 0; i < 3; i++) F32(stft + 0x08 + 4 * i) = F32(stft + 0x50 + 4 * i) = g_respawn_at[i];
}

/* The Falcon's bolts from its turret: the game's leave the Outrider's gun points (+-1, 10, +-5.6 in
 * the ship's frame); each new one of the Stft's (owner, not seen last frame: a mask by Blst slot, as tower_think()
 * finds its) is moved on its first frame by the nearer dome (falcon.c HDR_TURRET) - that point, its velocity kept. */
#define GUN_PT_X         1.0f
#define GUN_PT_Y         10.0f
#define GUN_PT_Z         5.6f
static void turret_bolts(uint32_t stft) {
    static uint32_t seen[2];
    uint32_t rec = blst(), now[2] = { 0, 0 };
    if (!rec || !valid_ptr(U32(rec + 0x10))) return;
    uint32_t n = U32(rec + 8), sz = U32(rec + 0xC);
    for (uint32_t i = 0; i < n && i < 64; i++) {
        uint32_t b = U32(rec + 0x10) + i * sz;
        if (U32(b + 0x64) != stft || F32(b + 0x58) <= -20000.0f) continue;
        now[i >> 5] |= 1u << (i & 31);
        float l[3], d[3];
        for (int r = 0; r < 3; r++) {                            /* its place in the ship's frame (rows +0x20/30/40) */
            l[r] = 0;
            for (int j = 0; j < 3; j++) l[r] += (F32(b + 0x50 + 4 * j) - F32(stft + 0x50 + 4 * j)) * F32(stft + 0x20 + 0x10 * r + 4 * j);
        }
        if ((seen[i >> 5] & (1u << (i & 31)))                   /* (a slot fired again before it was seen gone: still */
            && !(absf(absf(l[0]) - GUN_PT_X) < 0.5f && absf(l[1] - GUN_PT_Y) < 0.5f && absf(absf(l[2]) - GUN_PT_Z) < 0.5f))
            continue;                                            /* on a gun point: new too; 4 of 22 were missed) */
        int top = l[2] > 0;
        d[0] = F32(FALCON_RAM + 16) - (l[0] > 0 ? GUN_PT_X : -GUN_PT_X);
        d[1] = F32(FALCON_RAM + 20) - GUN_PT_Y;
        d[2] = F32(FALCON_RAM + (top ? 24 : 28)) - (top ? GUN_PT_Z : -GUN_PT_Z);
        for (int j = 0; j < 3; j++) {
            float w = 0;
            for (int r = 0; r < 3; r++) w += d[r] * F32(stft + 0x20 + 0x10 * r + 4 * j);
            F32(b + 0x50 + 4 * j) += w; F32(b + 0x94 + 4 * j) += w;   /* (its place and the one before: its streak) */
        }
    }
    seen[0] = now[0]; seen[1] = now[1];
}

/* The ship's nose toward the battle, level-ish (the rail left it heading away from it, past the Star Destroyer). */
static void battle_dir(uint32_t stft, float *f) {
    for (int i = 0; i < 3; i++) f[i] = F32(GALL_RAM + IMG_BATTLE + 4 * i) - F32(stft + 0x50 + 4 * i);
    f[2] *= 0.3f;
}
/* The free flight's first start turned smoothly: the flown forward kept, then each frame turned
 * toward the battle by the camera ease's share (1 - CINE_CARRY of the angle left, ~2.4 s) and at most START_TURN, while
 * the game flies it on; held with the game (the pause, a held line); over once within START_DONE, at the first stick
 * input or after START_MAX (the player's steering fought it till the first death), or at a death, the fly-away or the jump. */
#define START_TURN       0.05236f   /* radians a frame (3 degrees) */
#define START_DONE       0.0035f    /* (0.2 degrees) */
#define START_STICK      12         /* the stick's first input (of its +-80) ends the turn: the game's handling alone,
                                     * as after a respawn */
#define START_MAX        2.4f       /* s of unpaused, unheld frames: the turn's end at most (the camera ease's time) */
static int g_start_turn;
static float g_start_t;
static float g_turn_last[3];        /* the forward the turn left last frame: the total turn a frame, ours and the game's
                                     * own of the ship (after its update), kept within START_TURN of it */
static void turn_face(uint32_t stft, float *f) {
    float l = len3(f), c = 0, q[3], ql;
    if (l < 1e-3f) return;
    for (int i = 0; i < 3; i++) { f[i] /= l; c += f[i] * g_turn_last[i]; }
    c = c > 1 ? 1 : c < -1 ? -1 : c;
    if (atan2_r(sqrt_f(1 - c * c), c) > START_TURN) {
        for (int i = 0; i < 3; i++) q[i] = f[i] - c * g_turn_last[i];
        ql = len3(q);
        if (ql > 1e-3f) for (int i = 0; i < 3; i++) f[i] = g_turn_last[i] * cos_r(START_TURN) + q[i] / ql * sin_r(START_TURN);
    }
    stft_face(stft, f);
    for (int i = 0; i < 3; i++) g_turn_last[i] = F32(stft + STFT_FWD + 4 * i);
}
static void start_turn(uint32_t stft, uint32_t st) {
    if (st == 5 || st == 6 || g_away_t >= 0 || g_fj_t >= 0) { g_start_turn = 0; return; }
    if (paused() || S16(MSG_HOLD)) return;
    int sx = S16(PAD_STICK_X), sy = S16(PAD_STICK_Y);
    g_start_t += frame_dt();
    if (sx > START_STICK || sx < -START_STICK || sy > START_STICK || sy < -START_STICK || g_start_t >= START_MAX) {
        g_start_turn = 0; return;
    }
    float t[3], f[3], c = 0, l;
    battle_dir(stft, t);
    l = len3(t); if (l < 1e-3f) { g_start_turn = 0; return; }
    for (int i = 0; i < 3; i++) { t[i] /= l; f[i] = F32(stft + STFT_FWD + 4 * i); }
    l = len3(f); if (l < 1e-3f) { g_start_turn = 0; return; }
    for (int i = 0; i < 3; i++) { f[i] /= l; c += f[i] * t[i]; }
    c = c > 1 ? 1 : c < -1 ? -1 : c;
    float q[3], ql, a = atan2_r(sqrt_f(1 - c * c), c);          /* (the angle left) */
    if (a < START_DONE) { turn_face(stft, t); g_start_turn = 0; return; }
    float s = a * (1 - CINE_CARRY);
    s = s > START_TURN ? START_TURN : s;
    for (int i = 0; i < 3; i++) q[i] = t[i] - c * f[i];          /* (in the plane of f and t; opposite: about z) */
    ql = len3(q);
    if (ql < 1e-3f) { q[0] = -f[1]; q[1] = f[0]; q[2] = 0; ql = len3(q); if (ql < 1e-3f) return; }
    for (int i = 0; i < 3; i++) f[i] = f[i] * cos_r(s) + q[i] / ql * sin_r(s);
    turn_face(stft, f);
}
void native_fly(uint32_t chor, uint32_t stft) {
    static int last, hold, view = CAM_SKY;
    if (!stft) return;
    int hp = (int)U32(stft + STFT_HEALTH);
    int respawn = g_native && hp > last + RESPAWN_HP && g_fj_t < 0;   /* (not the jump's 495) */
    uint32_t st = U32(stft + STFT_STATE);                        /* the view the player had at the death (the last index */
    if (!respawn && st != 5 && st != 6 && (int)U32(CAMERA_INDEX) >= 0) view = (int)U32(CAMERA_INDEX);   /* before state 5: its */
                                                                 /* first frame is in the death's blend, -1) */
    if (respawn) g_native = 0;                                   /* blown up and back (the game's place is */
    last = hp;                                                   /* the space level's, far off): again where the free flight began */
    if (!g_native) {                                             /* (in: as a respawn, the game blended to its entry 5) */
        g_native = 1; g_native_ship = stft; hold = RESPAWN_HOLD;
        ties_final();                                            /* (the battle's TIEs: one group, once a run) */
        towers_on();                                             /* (once a run: the shot-down stay down) */
        sd_axis();                                               /* (the hull's long axis, once: fly_away()) */
        F32(MISSILE_LOCK) = 0; S16(MISSILES) = 5;
        if (g_bound_save <= 0) g_bound_save = F32(FLY_BOUND);
        F32(FLY_BOUND) = FLY_BOUND_NATIVE;
        if (g_touch_save <= 0 && F32(PRBT_TOUCH) > 0) g_touch_save = F32(PRBT_TOUCH);
        F32(PRBT_TOUCH) = 0;
        for (int i = 0; i < 3; i++)                              /* (+0x08 too: its own copy, the one it flies on: */
            F32(stft + 0x08 + 4 * i) = F32(stft + 0x50 + 4 * i) = F32(chor + 0x50 + 4 * i) + g_ship_off[i];   /* 8000 off */
        for (int i = 0; i < 3; i++) g_ship_off[i] = 0;
        if (respawn) { respawn_out(stft, chor); g_ship_drop = 0; }   /* (the first start: eased, gallrun.c D9) */
        g_ship_yaw = g_ship_pitch = g_ship_roll = 0;
        g_start_turn = !respawn;                                 /* (the first start: turned over the ease, below) */
        g_start_t = 0;
        for (int i = 0; i < 3; i++) g_turn_last[i] = F32(stft + STFT_FWD + 4 * i);
        if (respawn) {                                           /* a respawn: its nose at the battle at once, level */
            float f[3];
            battle_dir(stft, f);
            stft_face(stft, f);
        }
        sky_camera(stft, respawn && view != CAM_SKY ? view : CAM_SKY);   /* (a respawn: straight to the view of the death) */
        uint32_t t = U32(CLASS_TRAK + 0x10), ent = U32(CAMERA_ENTRIES) + CAM_SKY * 0x80;
        g_sky_carry.share = 0;
        if (!respawn && U32(CLASS_TRAK + 8) && valid_ptr(t) && U32(t + TRAK_TARGET) == stft) {   /* (D12) */
            float f[3];
            for (int i = 0; i < 3; i++) f[i] = 100 * F32(t + TRAK_MATRIX + 0x10 + 4 * i);
            carry_from(&g_sky_carry, (const float *)(t + TRAK_EYE), f);
            sky_carry(t);
            for (int i = 0; i < 0x40; i += 4) U32(ent + 0x14 + i) = U32(t + TRAK_MATRIX + i);
        }
        if (respawn && view == CAM_SKY) {                        /* kept as at the death, the game's */
            F32(RESPAWN_T) = -0.5f;                              /* switch to VIEW_MODE and its view-key lock-out ended, */
            U32(GUN_VIEW_WAIT) = 0;                              /* its first-input switch off; so its fade-in does not */
            S16(SCREEN_FADE + 6) = 0;                            /* run: the respawn's black cleared (the earlier */
        } else if (respawn) hold = 0;                            /* fallback) (4 or 5: the game's switch to VIEW_MODE and */
    }                                                            /* its fade-in stand) */
    /* The death (after 8c D8, which cut the explosion to 0.7 s): state 5 (the game's explosion, its 3 s, the base level's) begun with
     * DEATH_5_LEFT to go, the view on it as the game's; then state 6 begun DEATH_FROM into its DEATH_6 (0x800EC8F0,
     * 3.3 s): back ~3 s after the hit; state 6's fade and blend to Chor are the game's. The wreck held where it was hit
     * (8c D9: its copy +0x08, which the bursts and state 6 take, on its drawn place +0x50). */
    static uint32_t last_st;
    if (st == 5 && last_st != 5) F32(stft + STFT_STATE_T) = (float)(int)U32(stft + STFT_DEATH_5) - DEATH_5_LEFT;
    if (st == 6 && last_st != 6) F32(stft + STFT_STATE_T) = DEATH_FROM;
    last_st = st;
                                                                 /* exploding and just after: the view held on the ship */
    if ((st == 5 || hold > 0) && U32(CAMERA_INDEX) != CAM_SKY) ((setcam_fn)CAM_SWITCH)(CAM_SKY);   /* (the */
    if (hold > 0) hold--;                                        /* game's goes by Chor); else the view keys' */
    towers_aim(stft);
    if (!paused()) turret_bolts(stft);
                                                                 /* (the view key works: R, L, C-right give the space level's views
                                                                  * 6 -> 4 -> 5 -> 4, no hang once the towers' PRBT has its
                                                                  * +0x28) */
    if (g_start_turn) start_turn(stft, st);
    sky_dist(stft);
    U32(stft + STFT_CARRIED) = 0;
    g_fly_on = 0;
    for (int i = 0; i < 3; i++) { g_fly_pos[i] = F32(stft + 0x50 + 4 * i); g_ship_off[i] = 0; }
    g_ship_yaw = g_ship_pitch = 0;
    float f0 = F32(stft + STFT_FWD), f1 = F32(stft + STFT_FWD + 4), f2 = F32(stft + STFT_FWD + 8);
    g_fly_yaw = atan2_r(f1, f0); g_fly_pitch = -atan2_r(f2, sqrt_f(f0 * f0 + f1 * f1));
    float was[3] = { g_fly_pos[0], g_fly_pos[1], g_fly_pos[2] }, dir[3] = { f0, f1, f2 };
    float pace = sky_pace(stft), spd = F32(stft + STFT_SPEED), base = spd * 0.00448f;   /* (the game's glow: 1.4 * 0.8 / 250) */
    if (st != 5 && st != 6) {
        float back = spd * (1 - NATIVE_PACE) * frame_dt();      /* held back on its way */
        for (int i = 0; i < 3; i++) g_fly_pos[i] -= dir[i] * back;
        base = base < 1 ? 1 : base > 2 ? 2 : base;               /* (the game's flicker kept) */
        g_glow_w = (GLOW_SLOW + (GLOW_FAST - GLOW_SLOW) * (pace < 0 ? 0 : pace > 1 ? 1 : pace)) * (float)(int16_t)U16(stft + STFT_GLOW_W) / (1000.0f * base);
    }
    if (g_fj_t < 0) sd_touch(stft, dir);                         /* (not in the jump: it may go through the hull) */
    int turned = st != 5 && st != 6 && g_fj_t < 0 && bound(dir);   /* (not in the jump: it turned the nose to the battle, the path curved) */
    if (turned || g_fly_pos[0] != was[0] || g_fly_pos[1] != was[1] || g_fly_pos[2] != was[2])
        for (int i = 0; i < 3; i++) F32(stft + 0x08 + 4 * i) = F32(stft + 0x50 + 4 * i) = g_fly_pos[i];
    if (turned) stft_face(stft, dir);                            /* (only then: the game's roll kept) */
    if (st == 5 || st == 6) for (int i = 0; i < 3; i++) F32(stft + 0x08 + 4 * i) = F32(stft + 0x50 + 4 * i);   /* (D9) */
    free_lasers(chor);
}
