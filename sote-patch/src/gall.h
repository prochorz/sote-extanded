/* Gall Run's internal header (gallrun.c and gall_*.c, after common.h): what more than one of them uses. */
#ifndef GALL_H
#define GALL_H

#define LEVEL_GALL       32         /* the mission's own sub-level: the tables
                                     * grown to 33 entries in g_levels (gallrun.c), sub-level 6 never touched */

#define CLASS_CHOR       0x80112A78
#define MESH_W0          0x3064FF40u /* header word of a mesh node */
#define CLASS_DOLY       0x80112EC8 /* dolly camera */
#define CLASS_TRAK       0x80112EF8 /* camera track: rides the route behind its target */
#define TRAK_DIST        0x60       /* float, distance behind (stock 75) */
#define TRAK_TARGET      0x8C
#define TIE_SLOTS        6          /* TIEs kept on the Falcon's tail (4: few, the user) */
#define CLASS_TIEF       0x80112D48 /* TIE fighters */
#define TIE_POS          0x50
#define TIE_HEALTH       0x60       /* float, <= 0: shot down */
#define TRAK_MATRIX      0x20       /* rows right, forward, up (4 floats each), then the eye */
#define VIEW_AHEAD       12         /* stage 1 camera: heading from the route this many nodes on */
#define ACTIVE_CAMERA    0x800D08A4 /* the camera entry in use (docs/reverse-engineering.md) */
#define CAMERA_ENTRIES   0x800D08A0 /* -> the camera entries, 0x80 each; entry 3 follows Trak 1 (the run's view) */
#define CAMERA_INDEX     0x800D08A8 /* the active entry's number (5: the gun's, after firing in stage 2) */
#define CAMERA_GUN       5          /* the gun's entry (stage 2: firing switches to it) */
#define CAMERA_INSIDE    4          /* the gunner's inside view (the ship drawn as the turret's window at this index) */
#define VIEW_MODE        0x8018E462 /* s16: the gunner's chosen view, 4 inside / 5 behind (the view key writes it) */
#define GUN_VIEW_WAIT    0x8018E464 /* the Stft's update switches to the gunner's view on the first stick/button input
                                     * while this is nonzero, then clears it (0x80099890..0x80099A78) */
#define HUD_POS          0x80111110 /* s16 x, y per element (x -1000: hidden) */
#define CAM_SWITCH       0x80009648 /* the game's camera switch (index; hooks.S tramp_setcam) */
typedef void (*setcam_fn)(int);
#define CAM_BLEND        0x8000952C /* the game's blend to a camera entry (index, seconds) */
typedef void (*blend_fn)(int, float);
#define VIEW_BLEND       0x80111760 /* the view's blend between camera entries: +0x20 seconds into it, +0x24 its length */
#define SCREEN_FADE      0x800D0804 /* s16 r, g, b, alpha of a full-screen fade (-1000: none) */
/* The game's hit tint: a hit sets the screen fade to HIT_TINT alpha ~241 and the game fades it out, but not while a held
 * line holds the game: the tint stood over the screen under the line. gallrun.c turns it off
 * (-1000) then, every mission frame (ours, the jump's white flash and the black, are other colours). */
#define HIT_TINT_R       255
#define HIT_TINT_G       128
#define HIT_TINT_B       0
#define FADE_IN          0.5f       /* then fades in over this */
#define FADE_MAX         255
#define TRAK_EYE         0x50
#define NODE_SHOW        0x02       /* u16, high byte 0xFF = drawn */
#define NODE_ROT         0x14
#define NODE_POS         0x38       /* transform node translation */
#define NODE_COUNT       0x0C
#define NODE_LIST        0x10
#define ROUTE_STRIDE     0x54       /* route node: x, y, z floats, then an up vector at +0xC */
#define ROUTE_NODES      0x38       /* route struct: the nodes start here (+0x20 node count) */
#define SHIP_DROP        10.0f
#define CHOR_SPEED       0x60       /* float, route speed (stock 0.3) */
#define CHOR_PARAM       0x64       /* float, 0..1 along the current spline segment */
#define CHOR_NODE        0x6C       /* u32 x4: the route nodes the spline is between */
#define SPEED            1.5f
#define IMG_END          28         /* the run ends at this node */
#define IMG_SWITCH       48         /* first node of stage 2 */
#define IMG_LINES        80         /* radio lines: count, table (gall_asset.py LINES) */
#define IMG_COLL         108        /* stage 1's collision (gallrun/collide.py) */
#define PAD_A            0x8000
#define PAUSED           0x800DD2BC /* u32 1 while the pause screen is up */
#define PAUSE_TOGGLE     0x80026010 /* (-1) toggles the pause, (0) resumes (docs/reverse-engineering.md, Pause screen) */
#define START_LATCH      0x800D0A78 /* u8: START used, waits for its release */
#define NO_PAUSE         0x800DD2C0 /* u32: 1 in a scene (the pause toggle 0x80026010 then unpauses; START skips) */
#define GAME_STATE       0x800DD2B0 /* u32: 2 while playing (the START path pauses only then) */
#define QUIT_ASK         0x800D094C /* u32: "Are you sure you want to quit?" up */
#define OPTIONS_ON       0x800DD5E4 /* u32: the Options screen up */
static inline int paused(void) { return U32(PAUSED) || U32(QUIT_ASK) || U32(OPTIONS_ON); }
/* A radio line starting "~h" holds the game till a button (MSG_HOLD, the game's own: its objects not updated): the run
 * holds with it (no time passes for it), but for the view turning to Dash (story(): frame_dt_raw()). Paused, nothing
 * of ours moves (the opening shot ran on behind the menu: the user, 2026-10-17). */
static inline float frame_dt_raw(void) { return paused() ? 0.0f : frame_dt(); }
static inline float run_dt(void) { return S16(0x800DD2D0) || paused() ? 0.0f : frame_dt(); }
#define frame_dt run_dt
#define STFT_HEALTH      0x240      /* int, 495 full */
#define STFT_STATE       0x230      /* u32: 5, then 6 while it blows up */
#define MSG_HOLD         0x800DD2D0 /* s16: a radio line starting "~h" holds the game (objects not updated) till a button */
#define BOMB_WARN        0x800E1B00 /* float: seconds of "Incoming Bomb!" (set by the player ship's TBmb message) */
#define NODE_UNITS       36.0f      /* stage 1 route: units between nodes */
#define FLY_BOOST        1.3f       /* A held: speed up to this, share of cruise */
#define FLY_MIN          0.2f       /* no A: slow right down to this, share of cruise */
#define FLY_THROTTLE     1.5f       /* per second */
#define HIT_SHAKE        5.0f       /* camera shake, units */
#define HIT_SHAKE_EASE   4.0f       /* per second */
#define BANK_MAX         0.7f
#define BANK_EASE        0.08f      /* per frame */
#define SAY              0x800078E4 /* the game's radio message: portrait, frame, seconds, ?, text */
#define SFX              0x80007340 /* the game's sound: id, ?, pitch (float bits; 1.0 = 44 kHz), volume, ? */
#define SND_SCRAPE       0x54       /* the game's scrape (the space level's hull; the free flight's touch) */
#define SND_ROCK         0x4B       /* the rock hit (the base level's rock handler 0x8002857C, ch 4; stage 1's wall hits) */
#define GAME_RAND        0x800B8BE0 /* the game's random: 0 .. 2^31-1 */
typedef int (*rand_fn)(void);
#define LINE_SHOW        4.0f       /* seconds a radio line stays (was 6: the letters cost frame rate while shown) */
#define FACE_LANDO       0x100      /* portrait codes for face() (gallrun.c): Lando's, Leia's (the image's photos, slot 38) */
#define FACE_LEIA        0x101
int16_t face(int p);
#define LINE_SIZE        16         /* a line: from node, seconds (float) after the previous line, text (0: none), s16 portrait, s16 sound (-1: none) */
#define KNIFE            1.5708f    /* radians: on edge */
#define KNIFE_EASE       0.3f       /* per frame: a snap onto the edge */
#define SKY_FROM         1500.0f    /* (300: a slow fade all the way up; sharper, the user, 2026-10-14) */
#define SKY_TO           2500.0f
#define CANYON_DROP      ((SKY_FROM + SKY_TO) / 2)   /* the canyon gone from here up, where the fog starts to lift (the user: */
#define CANYON_GONE      100.0f     /* rock seen below on the black sky); the haze lifts over this much below it */
#define AST_SHOW         2650.0f    /* the Falcon this high (space.py AST_FROM a little over it; over SKY_TO: on a black sky, the user) */
#define JUMP_T           0.45f      /* (jump_pose(): a jump to lightspeed's length) */
#define SHOT_SAFE        ((g_sc == 1 && g_or_jump < JUMP_T) || g_sc == 4)   /* the cut-away parts of g_shot (the chase
                                     * view between them is played: hits, the sight, B) */
#define SL_HP            0.15f      /* Slave I's health (the boss bar's fraction: 15 %, the user) */
typedef void (*say_fn)(int, int, float, int, const char *);
static inline float minf(float a, float b) { return a < b ? a : b; }
static inline float wrap_pi(float a) {                           /* an angle into -pi..pi */
    while (a > PI_F) a -= 2 * PI_F;
    while (a < -PI_F) a += 2 * PI_F;
    return a;
}
static inline float len3(const float *v) { return sqrt_f(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]); }
#define player_ship()    ((find_fn)FIND_CLASS)(0x53746674u, 0)   /* the Stft (0: none) */
#define TAG_BLST         0x426C7374u
typedef void (*sfx_fn)(int, int, uint32_t, int, int);
#define SFX_AT           0x8000742C /* the game's sound at a world point: id, ch, pitch, volume, float *place,
                                     * loop, near, far (floats: full inside near, none past far; the TIEs' engines) */
typedef void (*sfx_at_fn)(int, int, uint32_t, int, const float *, int, uint32_t, uint32_t);
#define SFX_PLACED       0x800074BC /* the game's sound at a world point with its stock fall-off (0x800D07E8/EC): id, ch,
                                     * pitch, volume, float *place, loop (Slave I's fire, 0x8004E68C) */
typedef void (*sfx_placed_fn)(int, int, uint32_t, int, const float *, int);
static inline uint32_t fbits(float f) { union { float f; uint32_t u; } c = { f }; return c.u; }   /* (the calls' floats) */
#define IMG_CINE         128        /* the scene at the route's end: key count, keys (slave_pad.cine_keys()) */
#define IMG_RAIL         164        /* the rail on after the scene: its first node, node count (slave_pad.cine_keys()) */
#define IMG_RAIL_N       168
#define LEAD_FROM        (U32(GALL_RAM + 16) - 2)   /* the route's last 2 nodes: the lead before node 0 (LEAD) */
#define FLY_V            300.0f     /* cruise, units a second (Chor at SPEED, measured) */
#define RESPAWN_HP       200        /* health up by more than this in a frame: the ship came back after blowing up */
#define FLY_LOW          400.0f     /* and at most this far under it (the user: fly lower; the faces go down to cliffs.py
                                     * DEEP -1400, their lower ends in the haze. 70: the old floor's bumps) */
#define FLY_PITCH        0.8f       /* rad at full stick (0.5: on rails, the user) */
#define FLY_PITCH_EASE   3.0f       /* per second */
static inline float dot3(const float *a, const float *b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
#define SL_COOL          15         /* frames between hits that count (a volley is several bolts: 6 % at once) */
#define BOMB_OBJ         14
#define TIE_STATE        0xA8       /* s16: -2 parked (the game's update skips it, its draw hides it), -1 its burst */
#define CAM_SKY          6
#define TIE_FLAGS        0x70
#define TIE_FIGHTER      0x01
typedef void (*method_fn)(uint32_t, uint32_t, uint32_t, uint32_t);
#define IMG_SD           212        /* x, y, z, heading (floats) */
#define IMG_BATTLE       228        /* the battle's middle: x, y, z (between the Star Destroyer and the rail) */
#define IMG_HANGARS      364        /* the hangars' mouths: count, records {x, y, z, out x, out y} (slave_pad.hangar_slot()) */
#define IMG_LEEBO        376        /* Leebo's turn in Cut 05's frame 6: nine sprite headers, the intro's 15-23 (still.copy_sprite()) */

/* gallrun.c */
extern float g_alt;
extern uint32_t g_view_on;
extern int g_ties_on, g_pilot;
extern int8_t g_stick[2];
extern uint16_t g_btn;
extern int g_free;
extern int g_cine;
extern int g_bomb_on;
extern float g_cam_seen[6];
extern float g_cam_step[6];
#define CAM_STEP_MAX     50.0f      /* (a larger step of the view on screen is a jump, not its pace) */
/* gall_cam.c: a view eased in from the one on screen: carry = g_cam_seen - the new view's eye
 * and forward (x 100), added to it and decayed by CINE_CARRY a frame (~2.4 s); the carried look is kept unless the
 * Falcon would leave the screen's inner part (KEEP_EDGE of the width / height off each edge): then it turns just
 * enough to keep it at that edge (D16). */
#define CINE_CARRY       0.96f      /* per frame: from the view on screen into a held frame's (~2.4 s; it jumped, the user) */
#define KEEP_EDGE        0.15f      /* (the inner 70 %) */
typedef struct { float d[6]; float share; } carry_t;
void carry_from(carry_t *c, const float *eye, const float *f);
void carry_paced(carry_t *c);
void carry_on(carry_t *c, float *eye, float *f, const float *fal);
void carry_decay(carry_t *c);
void carry_entry(carry_t *c, uint32_t ent, const float *fal);
void falcon_place(float *p);
extern carry_t g_gun_carry;
extern int g_gun_ease;
extern int g_gun_to;
extern int g_knife;
void say_last(int i);
extern int g_said_last;
/* gall_scene.c */
uint32_t astr_take(uint32_t i, uint32_t *decoy, uint32_t *real);
void show_canyon(uint32_t node);
void hide_rocks(void);
/* falcon.c: the drawn heading while flown (stage 1, fly()) */
extern float g_ship_head;
extern int g_ship_head_on;
/* gall_fly.c */
extern float g_fly_pitch;
extern float g_fly_thr;
extern float g_fly_p;
extern float g_fly_speed;
extern float g_hit_t;
extern float g_shake;
extern int g_fly_on;
extern float g_fly_turn;
extern float g_cruise;
extern float g_fly_pos[3], g_fly_yaw;
void route_pos(uint32_t k, float *p);
float bank(uint32_t k, float cur);
float corridor(uint32_t k, int i);
float stick(int i);
float route_head(float f);
void hp_guard(int stage1);
float collide(uint32_t set, float *p, const float ax[3][3], const float *r, float *n);
int seg_hit(uint32_t set, const float *a, const float *b);
void rock(uint32_t set, float *dir, float v, float dt, const float *here, float head, int toline, int held);
void throttle(float dt);
void fly(uint32_t chor, uint32_t node, float t);
/* gall_story.c */
extern float g_intro_t;
extern int g_intro;
extern float g_ik[15];
extern float g_or_spin;
extern float g_or_f;
extern float g_or_dz;
extern float g_or_pt;
extern float g_lag_t, g_lag_quiet;
extern int g_said_slit;
extern int g_said_atmo;
extern int g_hp_kept;
extern float g_or_jump, g_sl_jump;
extern int g_sl_on_rail;
extern int g_ff_next;                    /* (gall_gun.c) */
extern float g_ff_wait;
extern float g_restart_t;
extern int g_shot;
void towers_on(void);
void towers_off(void);
void towers_show(void);
extern int g_gun_blend;
extern int g_sc;
extern float g_sl_hp;
extern int g_sl_lost;
extern float g_lost_t;
extern float g_sl_f;
extern float g_cine_t, g_sl[3], g_sl_yaw, g_sl_v[3];
extern float g_zoom;
extern int g_rail;
extern float g_bar_t;
void intro(uint32_t chor);
void outrider(uint32_t node, float t, int on);
void cine(uint32_t chor, uint32_t node);
void flee(void);
void slave(uint32_t node);
void glow(void);
void dash(void);
void or_cine(void);
void rail_start(uint32_t chor, uint32_t r0);
void boss_bar(float dt);
#define HUD_PLACE        0x80009088 /* (id, x, y) */
#define HUD_COLOUR       0x80009138 /* (id, r, g, b, a) */
#define HUD_TEXT         0x800091D4 /* (id, text) */
#define SPRINTF          0x800C0240
typedef void (*hud3_fn)(int, int, int);
typedef void (*hud5_fn)(int, int, int, int, int);
typedef void (*hudt_fn)(int, const char *);
typedef int (*sprintf_fn)(char *, const char *, ...);
void battle_hud(uint32_t stft);   /* gall_space.c: the towers' warning and target panel at the draw */
#define HUD_BOSS_NAME    0x22       /* (the base level has no text buffers for the boss bar's 0x38, 0x39: the setter
                                     * skipped them, nothing drawn; 0x22 and 0x35 are spare ones, 48 bytes, off screen) */
#define HUD_BOSS_PCT     0x35
extern float g_ocn[3];
uint32_t blst(void);
int bolt_hit(uint32_t b, const float *p, float r);
void no_shoot(void);
void story(uint32_t node);
void rail_restart(void);
void restart_fade(void);
/* gall_gun.c */
void hud_hide(int el, int hide);
void target_panel(int hide);
#define HUD_TIE_COUNT    0x34       /* the base level's "TIE Fighters: n" (docs/reverse-engineering.md, HUD text): never ours */
#define HUD_MISSILES     51         /* "Missiles: n": hidden where the Falcon has none (stage 1 flown, the end scene); its
                                       text follows MISSILES by itself on the rail and in the battle */
void or_friendly(void);
void sight_hide(int hide);
void gun_back(void);
/* gall_space.c */
#define IMG_SD_COLL      268        /* the Star Destroyer's (its drawn triangles, world units: gall_asset.py) */
extern float g_free_head;
void free_fly(uint32_t chor, uint32_t node);
/* gall_native.c */
extern int g_native;
extern const uint32_t SKY_VIEWS[2][6];
void native_off(void);
void native_fly(uint32_t chor, uint32_t stft);
extern carry_t g_sky_carry;
extern float g_sky_own[16];
void sky_carry(uint32_t t);
/* gall_ties.c */
extern float g_tie_down[10];
extern float g_tie_clock;
extern float g_leave_t;
extern int g_kills, g_won, g_won_said, g_rogue;
extern float g_xw_t;
extern int g_bomb_seen[2];
extern float g_bomb_run[2][6];
extern int g_bomb_fly;
extern float g_bomb_pos[3], g_bomb_way[3], g_bomb_t, g_bomb_age;
extern float g_bomb_hp[2];
extern const float AX_UNIT[3][3];
extern uint32_t g_chase[TIE_SLOTS];
void ties(void);
void ties_away(uint32_t chor);
extern float g_hang_t;              /* seconds since the launch (-1: not yet): the hangar TIEs' launch */
#define HANG_CINE_T      19.0f      /* the end scene's g_cine_t the hangar TIEs go at: the Falcon's turn round the pad, the
                                       camera facing record 0 from 18.9 s to 22 s (the image's IMG_CINE keys) */
void hang_go(void);
void hang_reset(void);                 /* (a new run) the launching chasers' leader links put back */
int bomb_fly(uint32_t obj);
__attribute__((noinline)) void tie_hold(int hold);
void pursuit(uint32_t node, float t);
int battle_index(uint32_t obj);
void battle(void);
void tie_back(uint32_t tie, uint32_t i, const float *a, const float *d);
int towers_left(void);
void towers_aim(uint32_t stft);
#define FJ_T             2.4f       /* seconds of the Falcon's jump (gall_native.c fly_jump(); 1.6 with FJ_GO 3000: a dot too soon) */
int fly_jump(float dt);
extern float g_fj_t, g_fj_from[3];
#define AWAY_T           7.0f       /* seconds of the fly-away before the jump (gall_native.c fly_away(); 4 covered a third of the way onto the hull) */
int fly_away(float dt);
extern float g_away_t;
void ties_final(void);
extern int g_ties_cut;
void chain_frame(int lvl);           /* gall_chain.c: Gall Run in the story */
void chain_pad(uint32_t c);
void chain_finale(void);
int finale(void);
uint32_t tie_draw(uint32_t obj, uint32_t a1, uint32_t a2, uint32_t a3);
void tie_update(uint32_t obj, uint32_t a1, uint32_t a2, uint32_t a3);
/* gall_cam.c */
extern float g_view[2];
extern uint32_t g_tie_update;
extern uint32_t g_tie_draw;
void run_camera_as(int copy);
void run_camera(void);
void view_set(uint32_t obj, const float *eye, float *f);
void trak_method(int ours);

#endif
