/* Gall Run (bonus mission): the base level (sub-level 6: Leebo flies the
 * Outrider along a route away from the Star Destroyer, the player is the gunner, TIEs attack)
 * turned into the Falcon's run after the Gall canyon run of the comic. Started from the Cheats
 * screen (gallrun_start); nothing changes in a normal run of the base level.
 *
 * The image (local/game/gall_run.bin, harness/gall_asset.py) is copied to GALL_RAM by _start:
 * header (IMG_*), two render-only geometry sets in world units (no collision) and one route.
 * - Stage 1: a canyon from stage 1's source, the source's track backwards from its end
 *   to its start; the player flies the Falcon (fly()) after the Outrider, which waits when it falls behind; TIEs
 *   come in near the end, Dash leaves (outrider(), ties()); under a steady
 *   camera (trak_draw); near the end the Outrider climbs away.
 * - Stage 2: the landscape of stage 2's source (terrain only), along the source's track
 *   backwards, turned and moved in the image so that it starts where stage 1 ends; the player is
 *   the gunner, TIEs on the Falcon's tail (pursuit).
 * Both ships bank into the route's turns (bank) and go on edge
 * through narrow passages.
 * Both are drawn 6x wider and 9x taller (the scale in the header), stage 2 IMG_SCALE2 times more. Every frame while it runs:
 * - once per level load the game's route pointers are moved to the route struct in the image
 *   (both stages, any number of nodes; the stock loop is found by its first two nodes); the
 *   run ends at the end node, as when the game finishes the level: back to the sub-level the
 *   mission was started from;
 * - the stage's geometry hangs under a rock's node (astr_take): the rock poses a decoy
 *   copy, we pose the real node (scale, turn, translation) and give it a mesh node of ours;
 *   from the switch node on it is stage 2's set and pose;
 * - it opens with a shot (intro(): keys in the image) that fades in from black and hands over to the
 *   run without a cut; the camera's handling is in gall_cam.c;
 * - the space rocks, the debris and the belt backdrop are hidden; Gall's fog colour and lights;
 *   the Falcon (falcon.c) drawn a little below its path so the camera, which rides the path
 *   behind it, looks down on it.
 */
#include "common.h"
#include "gall.h"

#define TAG_GALL         0x47414C4Cu
#define CAM_DIST         55.0f      /* stage 1: closer, a camera far behind cuts the bends through the rock */
#define CAM_DIST2        75.0f      /* stage 2: the stock distance, the TIEs on the Falcon's tail in view */
#define TIES_IN          90         /* the TIEs come in this many nodes before the switch (gall_asset.py TIES_IN; Dash's line) */
#define FREE_TIE_STEP    45.0f
#define PAD_RAW          0x80113080 /* raw controller data, 6 bytes each: stick x, y at +2, +3 */
#define PAD_INDEX        0x80113060 /* the controller in use */
#define DOLY_TIME        0xA8       /* (the second dolly) seconds into the level start's shot */
#define DOLY_LENGTH      0x130      /* its length: then the view is the Trak's */
#define DOLY_FROM        0x2BC      /* the second dolly's eye (+0x50 of it): the start's fly-in view comes
                                     * from there, so it gets the Trak's eye (no fly-in from the stock start) */
#define ROUTE_PTR        0x800D2600 /* global pointer to the route struct */
#define ROUTE_SCAN_LO    0x80190000
#define ROUTE_SCAN_HI    0x801A8000
#define LEVEL_NEXT       7          /* where a finished base level goes next (Cut 03) */
#define IMG_POKES        88         /* words written every frame of the run: count, table of (pointer, offset, value) */
#define PAD_B            0x4000
#define PAD_START        0x1000
#define PAD_R            0x0010
#ifndef PAD_NATIVE_OFF                                         /* (a research build may set its own: SOTE_DEFS) */
#define PAD_NATIVE_OFF   0          /* buttons kept off the pad in native flight: none (R hung the game till towers_on()
                                     * gave the PRBT record its +0x28 pool); kept as a probe knob */
#endif
#define PAD_Z            0x2000     /* stage 1: the Falcon on edge while held */
#define PAD_EAT          0xF03F     /* A, B, Z, START, L, R, the C buttons: kept from the game till let go (gallrun_pad()) */
#define LINE_HOLD_MIN_F  45         /* frames (LINE_HOLD_MIN 1.5 s) a held line is not let go: a B volley let Leia's go unseen */
#define MSG_SECONDS      0x800D07FC /* float: the radio line's seconds left */
#define LEEBO_STATE      0x800E1B10 /* the base level's opening lines (1, 2: Leebo speaks; 0: done) */
#define MUSIC_FADE       0x800D0764 /* float: the music's volume factor (0x80007088, every frame; docs/reverse-engineering.md) */
#define DUCK_T           1.8f       /* seconds the music is turned down for a line's sound (Chewie's roar: 1.2 s), */
#define DUCK_BACK        0.6f       /* the last of them coming back */
#define MUSIC_DUCK       0.15f

/* Gall 6a: fog colour, fog start (0..1000 depth), ambient and directional light. */
static const int16_t FOG_RGB[3] = { 162, 162, 188 };
static const int16_t AMBIENT[3] = { 80, 80, 80 };     /* (lighter: 60 / 230 and 8f's 35 / 255 left Slave I too   */
static const int16_t LIGHT[3] = { 220, 220, 220 };    /*  dark under the battle's light) */
/* Up after Slave I the sky darkens (the user, 2026-10-13: out of the atmosphere): the fog's colour (our only sky) from
 * the haze's over SKY_FROM to SKY_DUSK half way and SKY_SPACE at SKY_TO, by the Falcon's height over the route's end. */
static const int16_t SKY_DUSK[3] = { 40, 52, 104 };
static const int16_t SKY_SPACE[3] = { 2, 2, 8 };
#define SPACE_FAR        12000.0f
#define FOG_SPACE_MAX    1010       /* in space the fog's far end past the far plane (a start of 998, 999: dark, burnt) */
#define FOG_START        996        /* where the fog begins on the 0..1000 depth scale (the fog closes at the far plane) */
#define HAZE_FROM        900.0f     /* after the end scene the fog starts nearer with height (the user, 2026-10-14: haze, the */
#define HAZE_TO          1500.0f    /* walls' lower ends lost in it): from FOG_START at HAZE_FROM over the route's end to */
#define HAZE_START       995        /* HAZE_START at HAZE_TO, back to FOG_START over CANYON_DROP - CANYON_GONE .. CANYON_DROP */
#define VIEW_FAR         0x80192F20 /* float: the far clipping plane (docs/reverse-engineering.md, perspective) */
#define VIEW_FOVY        0x80192F14 /* float: the vertical field of view, degrees (the end scene narrows it: g_zoom) */
#define PERSP_SET        0x800BA444 /* the game's projection setter (fovy, aspect, near, far; <= 0 keeps a value) */
typedef void (*persp_fn)(float, float, float, float);
#define AST_ASPECT       1.3333334f /* the base level's own; */
#define GALL_NEAR        1.0f       /* not its 10: with 1 the haze (a first start from Cheats had 10, no haze; a second 1) */
#define GALL_FAR         6000.0f    /* the base level's 2000 cut the far hills off with a straight edge that
                                       moved with the camera (rock came and went); the fog still closes at it */

int g_gallrun;                      /* mission running (exported for tests) */
float g_alt;                        /* the Falcon's height over the route's end after the run (the sky darkens:
                                     * atmosphere(); space rocks from AST_SHOW up: show_stage(), hide_rocks()) */
#define SPACE_ALT        3000.0f    /* g_alt after Slave I's jump at least (the free flight may dive: still space) */
static uint32_t g_route;            /* stock route node 0 of this level load */

typedef void (*load_fn)(int);

/* The mission is a sub-level of its own, LEVEL_GALL. The game finds a sub-level's
 * blob through three tables in the boot segment (docs/reverse-engineering.md, "Sub-level data"), 32 entries each, at
 * fixed offsets from 0x80001330: they are here with a 33rd (the same offsets past the header, each array one longer;
 * the 15 instructions of the game's users that index them point here: hooks.S hook_table). Entry 32 is our blob in the
 * ROM (uncompressed: flag 0, its length), "3. A Gall Run" (the music setter 0x80006CB0 picks the track by the name's
 * first word: "3. A" is the base level's track 51, D11); gallrun_boot() copies the stock 32 before the game starts. So
 * does the level-index table (0x800DD77C, read by 0x80035D50: the save's current level): 32 gets the base level's. */
#define LEVEL_TABLES     0x80001330 /* header 0x40, roms[32], flags[32], names[32][64] */
#define LEVEL_INDEX      0x800DD77C /* u8 [32] */
#define LEVEL_INDEX_AST  2          /* the base level's (id 6's) */
#define SCREEN_SIZE      0x8001AA74 /* (w, h): asks for a new screen size when it differs */
#define LEVEL_STATE      0x800D2558 /* u8: 2 = a load queued */
#define LEVEL_QUEUE      0x800D255C /* s16: the queued id */
struct levels {
    uint32_t head[16];
    uint32_t rom[LEVEL_GALL + 1];   /* +0x40 */
    uint32_t pack[LEVEL_GALL + 1];  /* +0xC4: flag byte (1 = compressed), length */
    char name[LEVEL_GALL + 1][64];  /* +0x148 */
};
struct levels g_levels __attribute__((aligned(256))) = {
    .rom = { [LEVEL_GALL] = GALL_LEVEL_ROM }, .pack = { [LEVEL_GALL] = GALL_LEVEL_LEN }, .name = { [LEVEL_GALL] = "3. A Gall Run (bonus)" } };
uint8_t g_level_index[LEVEL_GALL + 1] __attribute__((aligned(4))) = { [LEVEL_GALL] = LEVEL_INDEX_AST };

void gallrun_boot(void) {           /* from _start (hooks.S), before the game's main */
    const uint32_t *t = (const uint32_t *)LEVEL_TABLES;
    for (int i = 0; i < 16; i++) g_levels.head[i] = t[i];
    for (int i = 0; i < LEVEL_GALL; i++) {
        g_levels.rom[i] = t[16 + i];
        g_levels.pack[i] = t[16 + 32 + i];
        for (int k = 0; k < 16; k++) ((uint32_t *)g_levels.name[i])[k] = t[16 + 64 + 16 * i + k];
        g_level_index[i] = *(volatile uint8_t *)(LEVEL_INDEX + i);
    }
}

static void finish(void) {
    g_gallrun = 0;
    chain_finale();                                              /* (in the story: on to Cut 06, gall_chain.c) */
}

static int g_pause_back;            /* frames after a pause the view is put back as it was (-1: a new start from the
                                     * pause, nothing to put back: the old load's camera entry, the screen empty) */

/* The queue 0x800194DC sends ids >= 32 to the Main Menu (its stock bound kept, D12): queue 32 as it does past that
 * check: the screen size, the state byte, the id. Also the game's restart (0x800271F0's jal 0x800194DC at 0x80027854
 * goes through tramp_level_queue, D13). */
void gall_queue(void) {
    ((int (*)(int, int))SCREEN_SIZE)(0x140, 0xF0);
    *(volatile uint8_t *)LEVEL_STATE = 2;
    U16(LEVEL_QUEUE) = LEVEL_GALL;
}

void gallrun_start(void) {
    g_pause_back = -1;
    g_gallrun = 1;
    g_route = 0;
    gall_queue();
}

int gallrun_active(void) {
    return g_gallrun && S16(LEVEL_ID) == LEVEL_GALL && U32(GALL_RAM) == TAG_GALL;
}

static int stock_route(uint32_t a) {
    return U32(a) == 0x44FA0000u && U32(a + 4) == 0 && U32(a + 8) == 0          /* 2000, 0, 0 */
        && U32(a + ROUTE_STRIDE) == 0x44F00000u && U32(a + ROUTE_STRIDE + 4) == 0xC3000000u;  /* 1920, -128 */
}

/* Chor reads its route through pointers to a route struct (header ROUTE_NODES bytes, then
 * the nodes): the global ROUTE_PTR and one in the level heap. The image holds a struct of the same
 * form with as many nodes as it needs; both pointers are moved to it once per level load. */
static uint32_t g_route_refs[4];
uint32_t g_view_on;                 /* stage 1 this frame (gallrun_frame) */
static uint32_t g_line;             /* the next radio line this run */
static float g_line_t;              /* seconds since the last one (or the run's start) */
int g_ties_on;                      /* the TIEs come in (from the Outrider's break-off on) */
int g_pilot;                        /* stage 1's flown part, till the gunner gets the pad: no sight, no target panel */
float g_test_view[19];              /* (tests: the view the frame was drawn with, rows + eye, the ship's place, the entry) */
int8_t g_stick[2];                  /* stage 1: the stick and buttons, taken out of the game's input */
uint16_t g_btn;
static float g_duck;                /* seconds the music and effects stay down (duck()) */
int g_free;                         /* past the route's end: free flight (free_fly) */
int g_cine;                         /* the scene at the end (cine()): 0 not yet, 1 running, 2 over (free flight, Slave I chasing) */
int g_sky_on;                       /* the space level's view keys and guns open (hooks.S tramp_sky_keys, tramp_sky_guns): g_native in the mission */
int g_bomb_on;                      /* the end's fight's bombers (bombers()): on (g_sl_jump >= 0 && g_free), */
float g_cam_seen[6];                /* the view on screen (the active camera entry's eye, forward x 100), till the end scene */
float g_cam_step[6];                /* its step from the frame before (0 if it jumped) */
int g_knife;                        /* on edge (Z held): -1 left, 1 right, 0 not */
#ifdef GALL_TRACE_PROBE
float g_dbg_trace[4], g_dbg_ray[7];
#endif

/* After the game reads the controllers' raw data and before it decodes it: in stage 1 the player
 * flies the Falcon (fly()), the stick and buttons are kept for that and taken out of the game's input
 * but START (the turret and the gunner's camera would follow the stick, firing switches to the gun). */
void gallrun_pad(void) {
    uint32_t c = U32(PAD_INDEX);
    chain_pad(c);
    if (c <= 3 && g_native && g_gallrun && S16(LEVEL_ID) == LEVEL_GALL) U16(PAD_RAW + c * 6) &= ~PAD_NATIVE_OFF;   /* (a probe's knob:
                                                                  * R, Z and the C buttons hung the game 2026-10-19 till the
                                                                  * towers' +0x28) */
    static uint16_t last, eat;                                   /* eat: buttons kept from the game till let go: down */
    static int was, held;                                        /* as a pause ends (the Resume A switched to the gun's */
    int p = paused();                                            /* view, the camera flew off: the user) or START that */
    if (c <= 3 && gallrun_active()) {                            /* let a held line go (the game paused behind it) */
        if (was && !p) eat = U16(PAD_RAW + c * 6) & PAD_EAT;
        eat &= U16(PAD_RAW + c * 6);
        U16(PAD_RAW + c * 6) &= ~eat;
    } else eat = 0;
    static int16_t kept;                                         /* START over a held line: the hold, put back as the */
    if (kept && !p) { S16(MSG_HOLD) = kept; kept = 0; }          /* pause ends */
    was = p;
    if (!S16(MSG_HOLD) && !kept) held = 0;                      /* a held line: let go by a fresh A or B (the game's own: */
    if (c <= 3 && S16(LEVEL_ID) == LEVEL_GALL && g_gallrun && S16(MSG_HOLD) && !p) {   /* START); START pauses, the line */
        uint16_t b = U16(PAD_RAW + c * 6), fresh = b & ~last, keep = 0;   /* kept (the user, 2026-10-17: kept above); not in */
        last = b;                                                /* its first LINE_HOLD_MIN_F frames (presses then not counted) */
        if ((fresh & PAD_START) && U32(GAME_STATE) == 2) {       /* START (at once): the game's pause, as its START path does */
            keep = PAD_START;                                    /* (START left in the pad: the pause screen's latch waits
                                                                  * for its release, not a Resume) */
            kept = S16(MSG_HOLD); S16(MSG_HOLD) = 0;             /* (skipped while a line holds: there START only */
            *(volatile uint8_t *)START_LATCH = 1;                /* lets it go); the text stays up, the hold back */
            ((void (*)(int))PAUSE_TOGGLE)(-1);                   /* after the pause */
            ((sfx_fn)SFX)(0x63, 6, 0x3EC00000u, 0x6590, 0);
        }
        else if (held < LINE_HOLD_MIN_F) held++;
        else if (fresh & (PAD_A | PAD_B)) { S16(MSG_HOLD) = 0; F32(MSG_SECONDS) = 0; }
        U16(PAD_RAW + c * 6) = keep; ((volatile int8_t *)(PAD_RAW + c * 6))[2] = 0; ((volatile int8_t *)(PAD_RAW + c * 6))[3] = 0;
        g_stick[0] = g_stick[1] = 0; g_btn = 0; return;
    }
    if (c <= 3) last = U16(PAD_RAW + c * 6);
    if (!g_view_on || c > 3 || paused()) { g_stick[0] = g_stick[1] = 0; g_btn = 0; return; }   /* paused: the menu's */
    uint32_t a = PAD_RAW + c * 6;
    volatile int8_t *raw = (volatile int8_t *)a;
    g_stick[0] = raw[2]; g_stick[1] = raw[3]; g_btn = U16(a);
    if (g_native) {                                              /* (the game flies the ship: all of the pad its, */
        if (g_away_t >= 0 && g_away_t < AWAY_T) { raw[2] = 0; raw[3] = 0; U16(a) = (U16(a) & PAD_START) | PAD_A; }   /* but */
        return;                                                  /* in the fly-away: fly_away(), A held: full speed) */
    }
    raw[2] = 0; raw[3] = 0;
    U16(a) &= g_free && g_sl_jump >= 0 ? PAD_START | PAD_B | PAD_Z : g_shot && !SHOT_SAFE ? PAD_START | PAD_B
            : PAD_START;                                         /* fire (Z, R...) would switch to the gun (free flight
                                                                  * after Slave I: firing, the view kept ours: free_fly()
                                                                  * run_camera(); the rail's chase view: B, story()'s) */
}

/* The game's camera switch (hooks.S tramp_setcam): in free flight only the run's camera (entry 3): firing switched
 * to the gun's, its view in the hull (the user: the camera flew into the ship). Nonzero: refused. */
int gallrun_setcam(int i) {
    return g_free && !g_native && g_gallrun && S16(LEVEL_ID) == LEVEL_GALL && (int16_t)i != 3;   /* (native: the game's own) */
}

static void use_route(void) {
    uint32_t ours = U32(GALL_RAM + 20);
    if (g_route && stock_route(g_route) && g_route_refs[0] && U32(g_route_refs[0]) == ours) return;
    if (!g_route || !stock_route(g_route)) {
        g_route = 0;
        for (uint32_t a = ROUTE_SCAN_LO; a < ROUTE_SCAN_HI; a += 4)
            if (stock_route(a)) { g_route = a; break; }
        if (!g_route) return;
    }
    uint32_t stock = g_route - ROUTE_NODES;
    int n = 0;
    g_route_refs[n++] = ROUTE_PTR;
    for (uint32_t a = ROUTE_SCAN_LO; a < ROUTE_SCAN_HI && n < 4; a += 4)
        if (U32(a) == stock) g_route_refs[n++] = a;
    if (U32(ROUTE_PTR) != stock) { g_route_refs[0] = 0; return; }   /* not the layout we know */
    for (int i = 0; i < n; i++) U32(g_route_refs[i]) = ours;
    towers_show();                                               /* (the Star Destroyer's gun towers: gall_space.c) */
    g_line = 0; g_line_t = 0;
    g_intro_t = 0; g_or_spin = 0;
    g_or_f = 0; g_or_dz = 0; g_or_pt = 0; g_lag_t = g_lag_quiet = 0; g_ties_on = 0; g_said_slit = 0; g_said_atmo = 0;
    g_fly_on = 0; g_fly_p = 0; g_cruise = 0; g_shake = 0; g_free = 0; g_cine = 0; g_hp_kept = 0; g_or_jump = g_sl_jump = -1; g_shot = 0; g_gun_blend = 0; g_hang_t = -1; hang_reset();
    g_kills = g_won = g_won_said = g_rogue = 0; g_xw_t = 0; g_fj_t = -1; g_away_t = -1; g_ties_cut = 0; g_native = 0; native_off(); g_sl_hp = SL_HP; g_sl_lost = 0;
    g_sl_on_rail = 0; g_ff_next = 0; g_ff_wait = 0; g_restart_t = -1;
    g_rail = 0; g_bar_t = 0; g_zoom = 1; g_pilot = 0;             /* (started again from the rail: the gunner's in stage 1) */
    for (int i = 0; i < 10; i++) g_tie_down[i] = -1;
    g_tie_clock = 0; g_leave_t = 0; g_ship_at_on = 0; g_glow_w = 0;
    g_bomb_on = 0; g_bomb_fly = 0; g_bomb_t = g_bomb_age = 0;
    for (int i = 0; i < 12; i++) (&g_bomb_run[0][0])[i] = 0;
    for (int i = 0; i < 3; i++) g_bomb_pos[i] = g_bomb_way[i] = 0;
    g_bomb_seen[0] = g_bomb_seen[1] = 0; g_bomb_hp[0] = g_bomb_hp[1] = 0;
}

/* The image's pokes, every frame of the run: each value to the word at offset from where the
 * pointer points (Dash's face in the HUD's sprite table, Chewie's sound in the sound bank). */
static void pokes(void) {
    for (uint32_t e = U32(GALL_RAM + IMG_POKES + 4), n = U32(GALL_RAM + IMG_POKES); n--; e += 12)
        U32(U32(U32(e)) + U32(e + 4)) = U32(e + 8);
}

/* Luke's portrait animated as on Hoth (the user, 2026-10-18): Hoth's HUD shows its 8 frames of him one a frame per 2
 * draws, in a loop (0x80089C28: element 20 + ((counter & 0xE) >> 1)); the radio message takes one sprite slot, so
 * slot 29 gets the image's frames in turn (luke_frames()), held while paused. After pokes() (its frame 0). */
#define IMG_LUKE         288        /* Luke's frames: count, sprite list */
#define LUKE_SLOT        29
#define HUD_SPRITES      0x8013CE2C /* -> the level's HUD sprite table */
/* The base level's own win: a kill ('htMe', 0x8009D14C) lowers one of four s16 counters 0x800E1B3C..48; with all
 * at 0 the wave spawner (0x800989A0) sends 'fini' and the level ends (LEVEL_NEXT, finish()). The run ends only by
 * its own story (the user, 2026-10-18), so the first one is held at its start value every frame. */
#define TIES_LEFT        0x800E1B3C
#define TIES_LEFT_START  60
/* Lando's and Leia's portraits (the user's photos, 2026-10-18): the base level has no free slot for them (24 is the
 * ship HUD's; 38, once free, is the gun towers' target panel: the image's pokes put it there), so a speaker's sprite
 * takes Dash's slot, 36, while the line is up (one line at a time; face_keep() after the pokes, which put Dash's back
 * each frame). face(p): a portrait code (FACE_LANDO, FACE_LEIA) to the slot, any other id as it is; -1 (no portrait)
 * with an older image. */
#define IMG_FACES        296        /* Lando's sprite, Leia's */
#define FACE_SLOT        36
static uint32_t g_face;             /* the speaker's sprite while its line is up */
int16_t face(int p) {
    g_face = 0;
    if (p < FACE_LANDO) return (int16_t)p;
    uint32_t s = U32(GALL_RAM + IMG_FACES + 4 * (p - FACE_LANDO));
    if (!s) return -1;
    U32(U32(HUD_SPRITES) + 4 * FACE_SLOT) = g_face = s;
    return FACE_SLOT;
}
static void face_keep(void) {
    if (!g_face) return;
    if (F32(MSG_SECONDS) > 0 || S16(MSG_HOLD)) U32(U32(HUD_SPRITES) + 4 * FACE_SLOT) = g_face;
    else g_face = 0;
}
static void luke_anim(void) {
    static uint32_t k;
    uint32_t n = U32(GALL_RAM + IMG_LUKE);
    if (!n) return;
    if (!paused()) k = (g_ov_frames >> 1) % n;
    U32(U32(HUD_SPRITES) + 4 * LUKE_SLOT) = U32(U32(GALL_RAM + IMG_LUKE + 4) + 4 * k);
}

/* The radio lines in the image, in order: each once the Falcon is at its node and its frames
 * seconds after the previous one have passed. */
static void lines(uint32_t node) {
    if (paused()) return;
    uint32_t e = U32(GALL_RAM + IMG_LINES + 4) + g_line * LINE_SIZE;
    g_line_t += frame_dt();
    if (g_line >= U32(GALL_RAM + IMG_LINES) || node < U32(e) || g_line_t < F32(e + 4)) return;
    g_line++; g_line_t = 0;
    if (U32(e + 8)) ((say_fn)SAY)(face((int16_t)U16(e + 12)), 31, LINE_SHOW, 13, (const char *)U32(e + 8));
    if ((int16_t)U16(e + 14) >= 0) {                     /* pitch 0.5: our sounds are 22 kHz */
        ((sfx_fn)SFX)(U16(e + 14), 6, 0x3F000000u, 0x7FFF, 0);
        g_duck = DUCK_T;                                         /* the rest quieter while it plays */
    }
}

/* While a line's sound plays (Chewie's roar: it was ~10 dB under the battle and the music) the music
 * (its fade factor, MUSIC_FADE) is turned down, then back over DUCK_BACK. (The game's effects volume,
 * float 0x800D2524, scales the sounds already playing too: the roar went down with the battle.) */
static void duck(void) {
    static float music;
    static int on;
    if (g_duck <= 0) {
        if (on) { F32(MUSIC_FADE) = music; on = 0; }
        return;
    }
    if (!on) { music = F32(MUSIC_FADE); on = 1; }
    float k = g_duck > DUCK_BACK ? 0 : 1 - g_duck / DUCK_BACK;   /* 0 ducked .. 1 back */
    F32(MUSIC_FADE) = music * (MUSIC_DUCK + (1 - MUSIC_DUCK) * k);
    if (!paused()) g_duck -= frame_dt();
}
#define RAIL_OFF         6
int g_said_last = -1;                /* the last say_last() index (the harness reads which code-said line went) */
void say_last(int i) {
    if (U32(GALL_RAM + IMG_LINES) <= (uint32_t)i) return;
    g_said_last = i;
    uint32_t e = U32(GALL_RAM + IMG_LINES + 4) + (U32(GALL_RAM + IMG_LINES) - 1 - i) * LINE_SIZE;
    if (U32(e + 8)) ((say_fn)SAY)(face((int16_t)U16(e + 12)), 31, LINE_SHOW, 13, (const char *)U32(e + 8));
}

/* atmosphere() holds VIEW_OVERRIDE on (the game would put its own view, fog and light back); off
 * again (and the game's fog and light as they were) once the mission is not running, or the
 * menus keep the fog colour as their background. Only if it was ours: the Cheats screen sets it too. */
static int g_atmo;
static int16_t g_atmo_save[14];
static float g_atmo_far, g_atmo_fovy = 60.0f, g_atmo_set_far;

static void atmosphere_off(void) {
    native_off();
    if (g_duck > 0) { g_duck = 0; duck(); }
    if (!g_atmo) return;
    g_atmo = 0;
    for (int i = 0; i < 3; i++) {
        S16(FOG_RGB_SET + 2 * i) = g_atmo_save[i];
        S16(FOG_RGB_USE + 2 * i) = g_atmo_save[3 + i];
        S16(AMBIENT_RGB + 2 * i) = g_atmo_save[6 + i];
        S16(LIGHT_RGB + 2 * i) = g_atmo_save[9 + i];
    }
    S16(FOG_MIN) = g_atmo_save[12];
    S16(FOG_MAX) = g_atmo_save[13];
    F32(VIEW_FAR) = g_atmo_far;
    U32(VIEW_OVERRIDE) = 0;
    g_atmo_set_far = 0;
    ((persp_fn)PERSP_SET)(g_atmo_fovy, -1.0f, -1.0f, g_atmo_far);   /* (the level's own projection back) */
}

static float haze(float alt) {                                  /* 0 .. 1 */
    float up = (alt - HAZE_FROM) / (HAZE_TO - HAZE_FROM), out = (alt - CANYON_DROP + CANYON_GONE) / CANYON_GONE;
    up = up < 0 ? 0 : up > 1 ? 1 : up; out = out < 0 ? 0 : out > 1 ? 1 : out;
    return up * (1 - out);
}

static void atmosphere(void) {
    if (!g_atmo) {
        g_atmo = 1;
        for (int i = 0; i < 3; i++) {
            g_atmo_save[i] = S16(FOG_RGB_SET + 2 * i);
            g_atmo_save[3 + i] = S16(FOG_RGB_USE + 2 * i);
            g_atmo_save[6 + i] = S16(AMBIENT_RGB + 2 * i);
            g_atmo_save[9 + i] = S16(LIGHT_RGB + 2 * i);
        }
        g_atmo_save[12] = S16(FOG_MIN);
        g_atmo_save[13] = S16(FOG_MAX);
        g_atmo_far = F32(VIEW_FAR);
        g_atmo_fovy = F32(VIEW_FOVY);
        g_atmo_set_far = 0;                                      /* (the projection made afresh: from Hoth by the
                                                                 * Cheats screen the same fovy kept Hoth's far plane in
                                                                 * it, the fog far off: the user) */
    }
    float k = g_cine ? (g_alt - SKY_FROM) / (SKY_TO - SKY_FROM) * 2 : 0;
    k = k < 0 ? 0 : k > 2 ? 2 : k;
    for (int i = 0; i < 3; i++) {
        int16_t c = k < 1 ? FOG_RGB[i] + (int16_t)((SKY_DUSK[i] - FOG_RGB[i]) * k)
                          : SKY_DUSK[i] + (int16_t)((SKY_SPACE[i] - SKY_DUSK[i]) * (k - 1));
        S16(FOG_RGB_SET + 2 * i) = c;
        S16(FOG_RGB_USE + 2 * i) = c;
        S16(AMBIENT_RGB + 2 * i) = AMBIENT[i];
        S16(LIGHT_RGB + 2 * i) = LIGHT[i];
    }
    S16(FOG_MIN) = FOG_START - (int16_t)((FOG_START - HAZE_START) * (g_cine == 2 ? haze(g_alt) : 0) + 0.5f);
    S16(FOG_MAX) = k > 1 ? 1000 + (int16_t)((FOG_SPACE_MAX - 1000) * (k - 1)) : 1000;   /* (the fog closes at the far end
                                                                 * of the depth scale; in space past it: the Star
                                                                 * Destroyer was black from ~1500 off, the user) */
    float far = GALL_FAR + (SPACE_FAR - GALL_FAR) * (k > 1 ? k - 1 : 0);   /* (in space the fog, closing at the far
                                                                 * plane, further off: the Star Destroyer was a black
                                                                 * shape; a fog start of 999 burnt the ships white) */
    F32(VIEW_FAR) = far;
    float fovy = g_atmo_fovy * (g_cine == 1 ? g_zoom : 1.0f);   /* the end scene's zoom: the projection is made by */
    if (F32(VIEW_FOVY) != fovy || g_atmo_set_far != far) {       /* the game's setter (ignores calls while the view */
        g_atmo_set_far = far;
        U32(VIEW_OVERRIDE) = 0;                                  /* override is on; <= 0 keeps a value) */
        ((persp_fn)PERSP_SET)(fovy, AST_ASPECT, GALL_NEAR, far);
    }
    U32(VIEW_OVERRIDE) = 1;
}

static void ship_off(void) {                                     /* the Falcon drawn as the game has it, our camera off */
    trak_method(0); g_ship_drop = 0; g_ship_roll = g_ship_pitch = g_ship_yaw = 0; g_ship_off[0] = g_ship_off[1] = g_ship_off[2] = 0; g_ship_at_on = 0; g_glow_w = 0;
    g_ship_head_on = 0;
}

/* From the overlay hook, once per frame. */
void gallrun_frame(void) {
#ifdef GALL_TRACE_PROBE                       /* research: a ray the harness asks for, on any level */
    {
        extern float g_dbg_ray[7];                /* from, to, out: hit distance */
        if (g_dbg_ray[0] != 0 || g_dbg_ray[1] != 0) {
            uint32_t h1 = 0, h2 = 0; float f[3] = { g_dbg_ray[0], g_dbg_ray[1], g_dbg_ray[2] }, t[3] = { g_dbg_ray[3], g_dbg_ray[4], g_dbg_ray[5] };
            g_dbg_ray[6] = ((trace_fn)TRACE_FN)(t, f, 0, &h1, &h2, 0.0f, 0);
        }
    }
#endif
    static int away;                /* frames on another sub-level: the player left the mission */
    int lvl = S16(LEVEL_ID);
    chain_frame(lvl);
    if (lvl != LEVEL_GALL) {
        g_sky_on = g_bomb_on = 0;
        atmosphere_off();
        if (g_gallrun && lvl == LEVEL_NEXT) finish();   /* the game ended the level */
        else if (g_gallrun) { if (++away > 30) g_gallrun = 0; }
        else away = 0;                                           /* (a start off sub-level 32 not undone) */
        g_view_on = 0;                                           /* (the pad not masked off the mission: D9) */
        ship_off();
        return;
    }
    away = 0;
    g_view_on = 0;
    g_glow_w = 0;                                                /* (native_fly() sets it each frame) */
    if (!gallrun_active()) { g_pilot = 0; g_sky_on = g_bomb_on = 0; atmosphere_off(); ship_off(); return; }
    if (S16(MSG_HOLD) && S16(SCREEN_FADE + 6) > 0 && S16(SCREEN_FADE) == HIT_TINT_R    /* the hit tint off under a held */
        && S16(SCREEN_FADE + 2) == HIT_TINT_G && S16(SCREEN_FADE + 4) == HIT_TINT_B)    /* line, every mission frame: */
        S16(SCREEN_FADE + 6) = -1000;                            /* stage 1's TIEs hit too (HIT_TINT, gall.h) */
    {                                                            /* (tests, local/work/jitter_probe.py: as drawn */
        uint32_t cam = U32(ACTIVE_CAMERA);                       /* this frame: the overlay runs after the draw) */
        if (valid_ptr(cam)) for (int i = 0; i < 15; i++) g_test_view[i] = F32(cam + 0x14 + 4 * i);
        for (int i = 0; i < 3; i++) g_test_view[15 + i] = g_ship_at[i] - (i == 2 ? g_ship_drop : 0);
        g_test_view[18] = (float)U32(CAMERA_INDEX);
    }
    {                                                            /* the view as it was before the pause: the Resume A */
        static uint32_t cam, idx, gun;                           /* switches to the gun's on the frame the pause ends, */
        if (paused()) { if (g_pause_back >= 0) { cam = U32(ACTIVE_CAMERA); idx = U32(CAMERA_INDEX); gun = U32(GUN_VIEW_WAIT); g_pause_back = 2; } }   /* read */
        else if (g_pause_back < 0) g_pause_back = 0;             /* while paused (gallrun_pad()'s mask: a frame late; */
        else if (g_pause_back > 0) {                             /* the camera flew off: the user) */
            g_pause_back--;
            if (U32(ACTIVE_CAMERA) != cam || U32(CAMERA_INDEX) != idx) {
                U32(ACTIVE_CAMERA) = cam; U32(CAMERA_INDEX) = idx;
                U32(GUN_VIEW_WAIT) = gun;                        /* (its first-input switch to the gun's view kept for */
                F32(VIEW_BLEND + 0x20) = F32(VIEW_BLEND + 0x24); /* stage 2) */
            }
        }
    }
    g_sky_on = g_native;
    use_route();
    U32(LEEBO_STATE) = 0;                                        /* no rock talk */
    uint32_t node = 0, end = U32(GALL_RAM + IMG_END);
    if (U32(CLASS_CHOR + 8) && g_route_refs[0] && U32(g_route_refs[0]) == U32(GALL_RAM + 20)) {
        uint32_t chor = U32(CLASS_CHOR + 0x10);
        intro(chor);
        F32(chor + CHOR_SPEED) = g_intro ? 0.0f : SPEED;            /* held still for the opening shot */
        node = U32(chor + CHOR_NODE);
        uint32_t r0 = U32(GALL_RAM + IMG_RAIL), rn = U32(GALL_RAM + IMG_RAIL_N);
        if (g_cine == 2 && !g_rail && !g_free && rn) rail_start(chor, r0);   /* the chase: on along the rail */
        if (g_rail && node + RAIL_OFF >= r0 + rn) g_rail = 0;    /* its end: free flight */
        if (node >= LEAD_FROM) node = 0;                         /* the lead nodes before node 0 */
        if (g_cine >= 1) {                                       /* (the sky's height: atmosphere()) */
            float e[3]; route_pos(end, e);
            g_alt = F32(chor + 0x58) + g_ship_off[2] - e[2];
            if (g_sl_jump >= 0 && g_alt < SPACE_ALT) g_alt = SPACE_ALT;   /* (after Slave I's jump: in space for good) */
        } else g_alt = 0;
        for (uint32_t i = 0, t = U32(CLASS_TRAK + 0x10); i < U32(CLASS_TRAK + 8) && i < 4; i++, t += U32(CLASS_TRAK + 0xC))
            if (U32(t + TRAK_TARGET) == chor) {
                F32(t + TRAK_DIST) = node >= U32(GALL_RAM + IMG_SWITCH) ? CAM_DIST2 : CAM_DIST;
                if (g_intro) {                                   /* the opening shot's view now (the view */
                    float f[3];                                  /* can be this camera's) and no blend from */
                    for (int i = 0; i < 3; i++) f[i] = g_ik[3 + i] - g_ik[i];   /* the start's camera: */
                    view_set(t, g_ik, f);                        /* both are the shot's already */
                    if (U32(CLASS_DOLY + 8) > 1 && g_intro_t < 0.2f) {   /* the start's dolly shot over */
                        uint32_t d = U32(CLASS_DOLY + 0x10) + U32(CLASS_DOLY + 0xC);   /* now: its */
                        F32(d + DOLY_TIME) = F32(d + DOLY_LENGTH);  /* camera is the Trak's, with no */
                    }                                              /* blend to it */
                    F32(VIEW_BLEND + 0x20) = F32(VIEW_BLEND + 0x24);
                }
                if (U32(CLASS_DOLY + 8))                         /* no fly-in from the stock start */
                    for (int i = 0; i < 3; i++)                  /* (the opening shot's: this frame's) */
                        F32(U32(CLASS_DOLY + 0x10) + DOLY_FROM + 4 * i) = g_intro ? g_ik[i] : F32(t + TRAK_EYE + 4 * i);
            }
        outrider(node, F32(chor + CHOR_PARAM), node < U32(GALL_RAM + IMG_SWITCH));
        hp_guard(!g_rail && g_cine == 0 && node < U32(GALL_RAM + IMG_SWITCH));
        story(node);
        int free = !g_rail && (node >= end || g_free);           /* past the end: free flight (no finish; after story(): */
        g_pilot = !g_rail && !free && node + VIEW_AHEAD + 2 < U32(GALL_RAM + IMG_SWITCH);   /* (as g_view_on's: the pad's */
        sight_hide(g_cine == 1 || SHOT_SAFE || g_pilot || g_native   /* hand-over; Slave I's jump ends the rail there; */
                   || (g_rail && (g_shot || (int)U32(CAMERA_INDEX) == -1)));   /* the held view after Dash's jump and the
                                                                  * blend back: the guns turn off the view) */
        target_panel(g_pilot || g_cine == 1);                    /* (the end scene: no guns; held under its lines) */
        U32(NO_PAUSE) = 0;                                       /* (the game's "a scene": START skips, never pauses; left
                                                                  * set by Cut 05 when the chain starts the run from it) */
        S16(HUD_POS + 4 * HUD_TIE_COUNT) = -1000;
        hud_hide(HUD_MISSILES, g_pilot || g_cine == 1);          /* no missiles there (the game's text follows the count) */
        if (g_rail) { fly(chor, node, F32(chor + CHOR_PARAM)); flee(); no_shoot(); or_friendly(); }   /* as stage 2: the gunner */
        else if (free && U32(GALL_RAM + IMG_CINE) && g_cine < 2) cine(chor, node);
        else if (free) { free_fly(chor, node); if (g_cine == 2) flee(); }
        else fly(chor, node, F32(chor + CHOR_PARAM));
        lines(node);
        duck();
        pokes();
        luke_anim();
        face_keep();
        S16(TIES_LEFT) = TIES_LEFT_START;                        /* the game's kill count never ends the run */
        g_view_on = free || g_shot || node + VIEW_AHEAD + 2 < U32(GALL_RAM + IMG_SWITCH);
        float want = bank(node + 1, g_ship_roll), sx = stick(0);
        if (g_fly_on) {                                          /* flown: into its own turn; on edge by Z */
            want = sx * BANK_MAX;
            int z = (g_btn & PAD_Z) != 0;                        /* on edge while Z is held: to the side the */
            if (!z) g_knife = 0;                                 /* stick's as it is pressed, else the way it */
            else if (!g_knife) g_knife = (absf(sx) > 0.2f ? sx : g_ship_roll != 0 ? g_ship_roll : 1) < 0 ? -1 : 1;   /* banks */
            if (g_knife) want = g_knife * KNIFE;
        }
        if (!g_intro && g_cine != 1) g_ship_roll += (want - g_ship_roll) * (absf(want) > BANK_MAX || absf(g_ship_roll) > BANK_MAX ? KNIFE_EASE : BANK_EASE);
        trak_method(1);
        if (!g_view_on) g_view[0] = g_view[1] = 0;
        if (node + TIES_IN >= U32(GALL_RAM + IMG_SWITCH)) g_ties_on = 1;   /* Dash: "TIEs!" */
        if (node < U32(GALL_RAM + IMG_SWITCH)) ties();
        tie_hold(node < U32(GALL_RAM + IMG_SWITCH) && !g_rail && g_cine == 0);
        if (g_cine == 1) ties_away(chor);                       /* the end scene: no TIEs (their bombs' flashes hid the */
        if (g_cine == 1 ? g_hang_t >= 0 : g_ties_on || node >= U32(GALL_RAM + IMG_SWITCH) || g_cine == 2)   /* shots), from */
            pursuit(node, F32(chor + CHOR_PARAM));               /* Lando's line the hangar TIEs (the chase after it) */
    }
    if (g_gun_carry.share > 0) {                                 /* the end scene's last view into the gun's (D14) */
        uint32_t gun = U32(CAMERA_ENTRIES) + g_gun_to * 0x80;   /* (and Dash's shot's last into the gunner's, D17) */
        float fal[3];
        if (!g_rail || g_shot || (int)U32(CAMERA_INDEX) != g_gun_to || !valid_ptr(U32(CAMERA_ENTRIES))) { g_gun_carry.share = 0; g_gun_ease = 0; }
        else {
            if (g_gun_ease == 2) g_gun_ease = 3;                 /* (the switch's frame: its rows are still the view gun_view() */
            else {                                               /* wrote; the game's camera update makes its own after) */
                if (g_gun_ease == 3) {                           /* (the first frame on the game's own rows) */
                    float e[3], f[3];
                    for (int i = 0; i < 3; i++) { e[i] = F32(gun + 0x44 + 4 * i); f[i] = 100 * F32(gun + 0x24 + 4 * i); }
                    carry_from(&g_gun_carry, e, f); carry_paced(&g_gun_carry); g_gun_ease = 0;
                } else carry_decay(&g_gun_carry);
                falcon_place(fal); carry_entry(&g_gun_carry, gun, fal);
            }
        }
    }
    if (g_cine != 1) {                                           /* the view on screen, for the end scene to */
        uint32_t cam = U32(ACTIVE_CAMERA);                       /* start from (trak_draw) */
        if (valid_ptr(cam)) {
            float was[6], l = 0;
            for (int i = 0; i < 6; i++) was[i] = g_cam_seen[i];
            for (int i = 0; i < 3; i++) { g_cam_seen[i] = F32(cam + 0x44 + 4 * i); g_cam_seen[3 + i] = 100 * F32(cam + 0x24 + 4 * i); }
            for (int i = 0; i < 6; i++) { g_cam_step[i] = g_cam_seen[i] - was[i]; if (i < 3) l += g_cam_step[i] * g_cam_step[i]; }
            if (l > CAM_STEP_MAX * CAM_STEP_MAX) for (int i = 0; i < 6; i++) g_cam_step[i] = 0;
        }
    }
    show_canyon(node);
    battle();
    g_bomb_on = g_sl_jump >= 0 && g_free;
    if (finale()) { finish(); return; }
    if (!paused()) boss_bar(frame_dt());                      /* (Slave I's: no_shoot()) */
    if (g_sl_lost && !S16(MSG_HOLD) && !paused() && ++g_sl_lost > 45) {   /* Slave I shot down: the chase again, */
        g_bar_t = 0; boss_bar(0); rail_restart();                /* 3/4 s after Leia's line is let go */
    }
    restart_fade();
    slave(node);
    glow();
    dash();
    or_cine();
    hide_rocks();
    atmosphere();
    if (g_native && !paused() && (int)U32(CAMERA_INDEX) == -1    /* a view press blends 6 -> 5 in the mission (a second */
        && S16(VIEW_BLEND + 4) == CAM_SKY && S16(VIEW_BLEND + 6) == 5) {   /* handler after the space level's branch): ended */
        U32(ACTIVE_CAMERA) = U32(CAMERA_ENTRIES) + CAM_SKY * 0x80; U32(CAMERA_INDEX) = CAM_SKY;   /* (as after a pause; */
        F32(VIEW_BLEND + 0x20) = F32(VIEW_BLEND + 0x24);         /* the blend won't start during one), then to 4 as */
        U32(U32(CAMERA_ENTRIES) + CAMERA_GUN * 0x80) = 0;        /* (5's active flag off, as the space level's) */
        ((blend_fn)CAM_BLEND)(4, 0.5f);                          /* the space level's (then the game's own 4 <-> 5) */
    }
    if (!g_native) g_ship_drop = SHIP_DROP;                       /* the free flight's first start: the drop eased to 0 */
    else if (g_ship_drop > 0 && !paused()) {                     /* by CINE_CARRY a frame, with the camera's carry (a */
        g_ship_drop *= CINE_CARRY;                               /* respawn: 0 at once, native_fly()) */
        if (g_ship_drop < 0.01f) g_ship_drop = 0;
    }
    g_ship_at_on = g_fly_on;                                     /* (fly(), free_fly(): g_ship_at; off when not flown) */
    if (g_native) g_ship_roll = 0;
}
