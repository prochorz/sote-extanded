/* Cheats: the game's own debug list (34 entries, normally switched on with GameShark
 * 800D098B 0001 and driven with gameplay buttons: Z/L/R/D-pad move its cursor, A/B/START
 * run the entry) as a "Cheats" entry at the bottom of the pause menu.
 *
 * The list runs the same game code the debug list does (functions and variables taken from
 * its handlers at 0x80013A7C and 0x800140C4, see docs/reverse-engineering.md), but from the
 * pause screen: the debug flag is never touched, so nothing happens during play.
 * Settings change in place; entries that need the game running (Kill Dash, Teleport, level
 * changes) resume it first.
 *
 * - cheats_pause: pause-menu input, before the game's own handler (0x800153D4). Owns the
 *   extra entry and the cheats screen and hides their input from the game.
 * - cheats_draw: after the game's pause screen (0x8001FC90).
 * - Our rows besides the game's: the patch's toggles on top; Jetpack Fuel, Ship, Leebo Scanner and
 *   Creature Cam (what the " Wampa  Stompa" name gives, picked from the row: the camera on a wampa /
 *   a trooper on foot, the AT-ST walked from the snowspeeder on Hoth); Reset cheats last.
 *
 * Built with -Oz (payload space). Game functions and variables are absolute symbols (GAME
 * below), not casts of integer constants: calls become a plain jal and loads lui+lw.
 */
#include "common.h"

#define GAME(name, addr) __asm__(".globl " #name "\n.set " #name ", " #addr)

/* Pause screen. */
GAME(gm_paused, 0x800DD2BC);        extern volatile uint32_t gm_paused;        /* 1 while paused */
GAME(gm_pause_list, 0x800D0948);    extern volatile uint32_t gm_pause_list;    /* list shown; 0 hides it and its input */
GAME(gm_pause_cursor, 0x800D0944);  extern volatile int16_t gm_pause_cursor;   /* 0 Resume, 1 Options, 2 Quit, 3 Game Secrets */
GAME(gm_pause_confirm, 0x800D094C); extern volatile uint32_t gm_pause_confirm; /* "Are you sure you want to quit?" */
GAME(gm_options_open, 0x800DD5E4);  extern volatile uint32_t gm_options_open;
GAME(gm_start_latch, 0x800D0A78);   extern volatile uint8_t gm_start_latch;    /* START used, wait for release */
GAME(gm_secrets_shown, 0x800359F0); int gm_secrets_shown(int);                 /* (0): Game Secrets is the 4th item */
GAME(gm_view_set, 0x8006A214);      void gm_view_set(uint32_t, int, float);     /* set_camera(player, view, blend) */
GAME(gm_set_pause, 0x80026010);     void gm_set_pause(int);                    /* (0) resumes */
GAME(gm_sfx, 0x80007340);           void gm_sfx(int, int, uint32_t, int, int);
GAME(gm_random, 0x800B8BE0);        int gm_random(void);
GAME(gm_cam_blend, 0x8000952C);     void gm_cam_blend(int, float);              /* blend to camera entry (index, seconds) */
GAME(gm_ship, 0x800E1B20);          extern volatile int16_t gm_ship;           /* player ship variant: 0 Outrider, 1 X-Wing, 2 TIE */
#define CURSOR_NONE     9           /* game cursor while our entry is selected: matches nothing */
#define LIST_X          160
#define LIST_Y          96          /* first item; 18 per item (0x8001FC90) */

/* Pad: bytes 4..0x13 are 1 while held (see the enum below), stick y at +2. */
GAME(gm_pad, 0x80113098);           extern volatile uint8_t gm_pad[0x18];
GAME(gm_pad_w, 0x80113098);         extern volatile uint32_t gm_pad_w[6];
GAME(gm_stick_y, 0x8011309A);       extern volatile int16_t gm_stick_y;

/* Text: color, position (320x240, "~c" centers on x), draw; sprintf. */
GAME(gm_text_color, 0x80024AE8);    void gm_text_color(int, int, int, int);
GAME(gm_text_pos, 0x80024ACC);      void gm_text_pos(int, int);
GAME(gm_text_draw, 0x80025228);     void gm_text_draw(uint32_t, const char *);
GAME(gm_sprintf, 0x800C0240);       int gm_sprintf(char *, const char *, ...);

/* What the debug entries call and change. */
GAME(gm_debug_names, 0x800D0994);   extern const char *const gm_debug_names[]; /* some carry value templates */
GAME(gm_level_names, 0x80001470);   extern const char gm_level_names[32][64];  /* sub-levels (ROM 0x2070) */
GAME(gm_level, 0x8013CE0E);         extern volatile int16_t gm_level;
GAME(gm_level_load, 0x800194DC);    void gm_level_load(int);
GAME(gm_find, 0x80026130);          uint32_t gm_find(uint32_t tag, int zero); /* first instance of a class */
GAME(gm_give_humn, 0x80072EB4);     void gm_give_humn(int, int);
GAME(gm_give_humt, 0x800A9588);     void gm_give_humt(int, int);
GAME(gm_kill_humn, 0x800732D4);     void gm_kill_humn(uint32_t, uint32_t, int, int);
GAME(gm_kill_humt, 0x800A97E8);     void gm_kill_humt(uint32_t, uint32_t, int);
GAME(gm_tp_humn, 0x80074CDC);       void gm_tp_humn(uint32_t);
GAME(gm_tp_humt, 0x800AAA34);       void gm_tp_humt(uint32_t);
GAME(gm_tp_bike, 0x800290B0);       void gm_tp_bike(uint32_t);
GAME(gm_lives, 0x800E0EB0);         extern volatile int32_t gm_lives;
GAME(gm_stuff, 0x800E1B54);         extern volatile int16_t gm_stuff;
GAME(gm_persp, 0x80192F14);         extern volatile float gm_persp[4];         /* fovy, aspect, near, far */
GAME(gm_persp_set, 0x800BA444);     void gm_persp_set(float, float, float, float); /* <= 0 keeps a value */
GAME(gm_view_override, 0x80192F38); extern volatile uint32_t gm_view_override; /* perspective/fog/light edited */
GAME(gm_fog_rgb_use, 0x800E7AD0);   extern volatile int16_t gm_fog_rgb_use[3]; /* fog color in use */
GAME(gm_aa_apply, 0x8001AAF0);      void gm_aa_apply(void);
GAME(gm_dither_idx, 0x800D25B0);    extern volatile int16_t gm_dither_idx;
GAME(gm_god_flag, 0x800E1B2C);      extern volatile uint32_t gm_god_flag;      /* the entry's own state */
GAME(gm_god_bike, 0x800E18AC);      extern volatile uint32_t gm_god_bike;      /* bit 0 */
#define DITHER          0x800D25BA  /* s16, 10 bytes per gm_dither_idx */
#define TAG_BIKE        0x42696B65u
#define DIE_CAUSE       0x49742400u /* "It$" */

enum { ACT, ACT_PLAY, TOG, VAL_F, VAL_S, PERSP, VEC, LVL, SHIP, CREAT };

/* Names come from the game's own list, see name_text(). Per kind:
 * VAL_F / PERSP: float at addr, a..b in steps of c, all in 1/20;
 * VAL_S: s16 at addr, a..b in steps of c;
 * TOG: on when (value at addr & a) != 0, inverted when b, c = width in bytes. */
struct item {
    uint8_t kind;
    uint8_t id;          /* entry number in the game's list (0x800D0994) */
    int16_t a, b, c;
    uint32_t addr;
};
#define F20(x) ((float)(x) * (1.0f / 20))

static const struct item ITEMS[] = {
    /* Ours, on top: the patch's features. a: bits that show it off, b: the bit it flips. */
    { TOG,      37, OFF_CONTROLS, OFF_CONTROLS },     /* New Controls */
    { TOG,      38, OFF_LOCK | OFF_CONTROLS, OFF_LOCK }, /* Z Lock-On: off with the controls too */
#if FEATURE_HANG
    { TOG,      39, OFF_HANG, OFF_HANG },             /* Ledge Hang */
#endif
    { ACT,      0 },                                  /* Get all stuff */
    { TOG,      1 },                                  /* Invincibility (god_get/god_set) */
    { TOG,      41 },                                 /* ours: Jetpack Fuel (cheats_frame) */
    { TOG,      2,  2, 0, 2, 0x800DA6D0 },            /* Debug Display: 0 / 2 */
    { ACT,      3 },                                  /* 50 Lives */
    { TOG,      4,  1, 0, 4, 0x800DD2C4 },            /* Villains aren't sleepy */
    { ACT_PLAY, 5 },                                  /* Kill Dash */
    { ACT_PLAY, 6 },                                  /* Teleport */
    { LVL,      7 },                                  /* Go to level: replaces Next / Prev Level */
    { ACT_PLAY, 8 },                                  /* This Level */
    { TOG,      10, 1, 1, 4, 0x80112824 },            /* Wall Ghost: bit clear = on */
    { VAL_F,    11, 2, 60, 1, 0x800E0DC0 },           /* Jump Power 0.1..3 */
    { VAL_F,    12, 2, 60, 1, 0x800E0DC4 },           /* Gravity 0.1..3 */
    { TOG,      13, 1, 1, 1, 0x800D2530 },            /* Texture: byte set = off */
    { TOG,      14, 1, 1, 1, 0x800D2534 },            /* Lighting */
    { TOG,      15, 1, 1, 1, FOG_OFF },               /* Fog */
    { TOG,      16, 1, 0, 4, 0x800D25DC },            /* Antialiasing (then gm_aa_apply) */
    { PERSP,    18, 80, 2400, 20, PERSPECTIVE + 0 },  /* vertFOV 4..120 */
    { PERSP,    19, 2, 200, 1, PERSPECTIVE + 4 },     /* aspect 0.1..10 */
    { TOG,      20, 1, 0, 2, 0 },                     /* dither (address from gm_dither_idx) */
    { PERSP,    21, 200, 19980, 100, PERSPECTIVE + 12 }, /* Fog Max (far plane) 10..999 */
    { VAL_S,    22, 10, 996, 4, FOG_MIN },            /* Fog Thick */
    { VAL_S,    23, 0, 255, 5, 0x80192F30 },          /* Fog Red */
    { VAL_S,    24, 0, 255, 5, 0x80192F32 },          /* Fog Green */
    { VAL_S,    25, 0, 255, 5, 0x80192F34 },          /* Fog Blue */
    { VAL_S,    26, 0, 255, 5, 0x800E7AAC },          /* Amb Light Red */
    { VAL_S,    27, 0, 255, 5, 0x800E7AAE },          /* Amb Light Green */
    { VAL_S,    28, 0, 255, 5, 0x800E7AB0 },          /* Amb Light Blue */
    { VAL_S,    29, 0, 255, 5, 0x800E7AB4 },          /* Dir Light Red */
    { VAL_S,    30, 0, 255, 5, 0x800E7AB6 },          /* Dir Light Green */
    { VAL_S,    31, 0, 255, 5, 0x800E7AB8 },          /* Dir Light Blue */
    { VEC,      32, 0, 0, 0, 0x800E7AC4 },            /* Dir Light Vec: s16 x3, length 120 */
    { ACT,      33 },                                 /* Revert Fog and Lights */
    { SHIP,     42 },                                 /* ours: Ship (secret #2: Skyhook's X-Wing / TIE) */
    { TOG,      40, 0, 1, 0, 0 },                     /* ours: Leebo Scanner (secret #1: top-down view) */
    { CREAT,    43 },                                 /* ours: Creature Cam (Dash / Wampa / Trooper, Speeder / AT-ST) */
    { TOG,      44, 0, 1, 0, 0 },                     /* ours: Friendly Wampas (secret #4, cheats_secret4) */
    { ACT,      34 },                                 /* ours: Reset cheats, undo every setting changed here; stays last */
};
#define N_ITEMS ((int)(sizeof ITEMS / sizeof ITEMS[0]))
#define OURS (2 + FEATURE_HANG)  /* our toggles above the game's entries */
#define ROW(id) (OURS + ((id) < 9 ? (id) : (id) < 17 ? (id) - 1 : (id) - 2))  /* row of a game entry (Prev
                                                                        * Level, 9, and Screen Resolution, 17, are gone) */
#if FEATURE_GALLRUN
/* Go to level: the 33 sub-levels of the Gall code's table (gallrun.c g_levels, names at +0x148; 32 = the Gall Run). */
extern char g_levels[];
#define N_LEVELS 33
#define LEVEL_NAMES ((const char (*)[64])(g_levels + 0x148))
#define LEVEL_FROM(l) ((unsigned)(l) < N_LEVELS ? (l) : (l) & 31)
#else
#define N_LEVELS 32
#define LEVEL_NAMES gm_level_names
#define LEVEL_FROM(l) ((l) & 31)
#endif
/* Layout: clear of the lives icon (top left) and the HUD boxes (rows 186-220). */
#define ROWS     11              /* visible rows */
#define ROW_H    12
#define ROW_Y    34
#define NAME_X   66
#define VALUE_X  226

/* Pad bytes (gm_pad[n], 1 while held). */
enum { B_CR = 4, B_CL, B_CD, B_CU, B_R, B_L, B_RD = 12, B_LD, B_DD, B_UD, B_START, B_Z, B_B, B_A };
#define STICK_PUSH      40

int g_cheats_open;            /* exported for tests */
int g_cheats_sel;
int g_cheats_row;
static int g_top;
static int g_swallow;         /* input hidden from the game until everything is released */
static uint32_t g_prev;       /* held directions/buttons last frame (bit = pad byte) */
static int g_rep_t;           /* frames the current direction has been held */
static int g_flash;           /* frames left of the "done" mark on an action row */
int g_lvl;                    /* Go to level choice (exported for tests) */

static void sfx(void) {
    gm_sfx(0x63, 6, 0x3EC00000u, 0x6590, 0);
    gm_sfx(0x65, 6, 0x3EC00000u, 0x6590, 0);
}

static int secrets(void) { return gm_secrets_shown(0) != 0; }

/* Held state as a bit set: pad bytes 4..0x13, plus stick pushes mapped onto the D-pad. */
static uint32_t held(void) {
    uint32_t h = 0;
    for (int b = B_CR; b <= B_A; b++)
        if (gm_pad[b]) h |= 1u << b;
    int sy = gm_stick_y;
    if (sy > STICK_PUSH) h |= 1u << B_UD;
    if (sy < -STICK_PUSH) h |= 1u << B_DD;
    return h;
}

static void clear_pad(void) {
    for (int i = 0; i < 6; i++) gm_pad_w[i] = 0;
}

/* Direction "fires": on the press, then repeating while held (faster after a while). */
static int repeat(uint32_t h, uint32_t dirs) {
    uint32_t d = h & dirs;
    if (!d) { g_rep_t = 0; return 0; }
    if (!(g_prev & d)) { g_rep_t = 0; return 1; }
    g_rep_t++;
    return g_rep_t >= 14 && (g_rep_t - 14) % (g_rep_t > 60 ? 2 : 4) == 0;
}

/* ---- the entries ---- */

static uint32_t find(uint32_t tag) { return gm_find(tag, 0); }

/* Invincibility is per player object: bit 0x8 of its flags (the HUD icon) and the float timer
 * +0xE4 (the debug entry sets 100000 s, the pickup 30; counts down at 0x80079990), same in Humn
 * and HumT; the speeder bike has a global bit. A new level's player starts without them, so the
 * row shows the current player's state, not the entry's flag (gm_god_flag). */
#define GOD_OBJ_BIT     0x8
#define GOD_TIMER       0x0E4
#define GOD_TIME        100000.0f

static uint32_t player_obj(void) {
    uint32_t p = find(TAG_HUMN);
    return p ? p : find(TAG_HUMT);
}

static int god_get(void) {
    uint32_t p = player_obj();
    return p ? F32(p + GOD_TIMER) > 0 : (gm_god_bike & 1);
}

static void god_set(int on) {
    uint32_t p = player_obj();
    if (p) {
        U32(p + OBJ_FLAGS) = on ? U32(p + OBJ_FLAGS) | GOD_OBJ_BIT : U32(p + OBJ_FLAGS) & ~GOD_OBJ_BIT;
        F32(p + GOD_TIMER) = on ? GOD_TIME : 0;
    }
    gm_god_bike = on ? gm_god_bike | 1 : gm_god_bike & ~1u;
    gm_god_flag = on;
}

/* Leebo Scanner: the game's secret #1, the top-down view (camera view 2, the overhead camera
 * with a clear line of sight above Dash; indoors it falls back to the follow view, same as the
 * real scanner). Normally it needs C-right held ~5 s plus the secret unlocked; this menu item
 * switches it straight on/off. The row reads the real state (view 2 = on), so changing the
 * camera away from it shows OFF. */
static int g_leebo_prev = CAMERA_FOLLOW;   /* the view to restore when turned off */
static int leebo_get(void) { return S16(CAMERA_VIEW) == 2; }
static void leebo_set(int on) {
    uint32_t p = find(TAG_HUMN);            /* on foot only; the train/vehicles have no scanner */
    if (!p) return;
    if (on) {
        g_leebo_prev = S16(CAMERA_VIEW);
        gm_view_set(p, 2, 0);
    } else {
        gm_view_set(p, g_leebo_prev, 0);
    }
}

/* Ship: the game's secret #2. The player ship's model on Skyhook holds three variants (Outrider,
 * X-Wing, TIE Fighter) picked by gm_ship, which the Stft draw copies into the variant group every
 * frame; other ships' models have no group. The row writes the counter as the native C-right swap
 * does (then the camera blend to entry 5) and shows the counter itself, so a restart (the ship's
 * init sets 0) reads Outrider again. */
static uint32_t ship_group(void) {
    uint32_t s = find(TAG_STFT), r, c;
    if (!s || !(r = U32(s + 0xB4)) || !(c = U32(r + 0x10)) || !(c = U32(c))) return 0;
    return U16(c) == 0x5065 ? c : 0;
}
static void ship_set(int v) {
    gm_ship = v;
    gm_cam_blend(5, 0.5f);
}

/* Jetpack fuel: the game burns the float at Humn+0xBC while the jetpack fires and clamps it to
 * the max (100) in the same control function, so a one-shot top-up would not last. While this
 * is on, the tank is refilled here once per rendered frame (from the overlay hook), and the
 * fuel percentage in the HUD is drawn blue (cheats_hud_col) so the number shows the cheat. */
int g_fuel_on;                          /* in common.h; the row and cheats_frame share it */

/* Friendly Wampas: the game's secret #4, a wampa whose target is Dash calms down. The game gives it
 * only to a profile that beat Jedi: its secret check 0x800359F0(n) answers a profile-name code only
 * for n < 4. The three wampa call sites (0x800B0680, 0x800B2B90, 0x800B3374: jal 0x800359F0 with
 * a0 = 4 in the delay slot) call this instead (hooks.S), so the game's own calm-down runs. The
 * game's check still runs first: the name matcher keeps its side effects. The row's OFF cannot turn
 * off a Jedi-beaten profile's secret; the row reads the cheat, not the secret. Exported for tests. */
int g_friendly_on;

int cheats_secret4(int n) { return gm_secrets_shown(n) | g_friendly_on; }

/* Creature Cam: what the profile name " Wampa  Stompa" gives, without the name and its buttons
 * (the game's buttons for it exist only in the Traditional preset; here the row picks the value:
 * holding the name's flag 0x800DD774 every frame, the first take, still needed those buttons held).
 * On foot (Dash / Wampa / Trooper): the creature camera follows the object in CREATURE_OBJ. The
 * row does what the on-foot code does on the name's buttons (0x80071A38, 0x80071AA8): clear it,
 * set the distance, and send 'Wmp?' / 'Bls?' to class Trop (0x800262FC); the Trop handler
 * (0x800B58D0) puts the first wampa (+0x74 & 0xF == 2) / the first other Trop that can answer
 * there, nobody answering leaves Dash. The row reads the object back; the game clears it at a level
 * load and a new Dash (0x800190F4, 0x800704EC, 0x80070904), so nothing runs per frame for it.
 * The D-pad drives the creature: the wampa's code (0x800B24D4) walks on binding +0x08, turns on
 * +0x0C / +0x0E and attacks on +0x0A, a followed trooper turns on +0x0C / +0x0E (0x800B4F84), as
 * the game's own mode does in Traditional; so while a creature is followed on foot the preset's
 * D-pad slots are Traditional's (the same swap as the AT-ST's below; in the other presets +0x10..
 * +0x16 are Dash's D-pad walk, 0x800716D4, emptied by it, so Dash stays put), and back at Dash.
 * Hoth (Speeder / AT-ST, where both classes are): the snowspeeder sets ATST_MODE only on the name's
 * buttons and nothing clears it; then ATST 0 turns on bindings +0x0C / +0x0E and picks a target
 * (camera in its cockpit) on +0x08. Those slots hold the D-pad only in Traditional (2/3; the
 * others have it in +0x10..+0x16, the speeder's view keys at 0x8008F0D8..0x8008F2F4, which would
 * take the camera back), so while it is on the current preset's 8 D-pad slots are Traditional's
 * (saved and put back on off, on a level without the classes, on a preset change). Off: the mode
 * 0 (ATST 0 back on its AI) and Trak 0 (the camera) back on the first Spdr, its target in play
 * (the ATST's target pick leaves it on the ATST otherwise). On, the camera goes into ATST 0's
 * cockpit by itself while it is awake (the camera writes of its D-up branch; D-up still picks a
 * target and fires) and back to the speeder when it sleeps, dies or is destroyed. */
GAME(gm_send, 0x800262FC);          void gm_send(uint32_t tag, const uint32_t *msg); /* message to every object of a class */
#define CREATURE_OBJ    0x800E5EF4  /* u32, the object the creature camera follows (0 = Dash) */
#define CREATURE_DIST   0x800E5EF8  /* float, its distance: 7.0 for a wampa, the game's 5.6 for a trooper */
#define TROOPER_DIST    0x800EB7F0  /* float, the game's 5.6 */
#define ATST_MODE       0x800DECE0  /* u32, the Hoth AT-ST mode (set at 0x8008ED08, never cleared) */
#define TRAK_0          0x80112F20  /* u32, the first Trak (the camera); its target at +0x8C */
#define TRAK_TARGET     0x8C
#define TRAK_DIST       0x98        /* float, 55.0: the game's cockpit distance at 0x800566C0 */
#define ATST_AIM        0x800DEE28  /* float, 18.0: written by the same branch; no reader found */
#define MSG_WMP         0x576D703Fu /* 'Wmp?' */
#define MSG_BLS         0x426C733Fu /* 'Bls?' */
#define TAG_ATST        0x41545354u
#define TAG_SPDR        0x53706472u
#define KIND_WAMPA      2           /* Trop +0x74 & 0xF */
#define DPAD_SLOTS      0x08        /* 8 u16 slots +0x08..+0x16 of a preset */
enum { C_NONE = -1, C_DASH, C_WAMPA, C_TROOPER, C_SPEEDER, C_ATST };
static const uint16_t TRAD_DPAD[8] = { 0x0800, 0x0400, 0x0200, 0x0100 }; /* Traditional: up, down, left, right; +0x10.. 0 */
int g_atst_on;                          /* kept over level changes; read by tests */
/* the D-pad swap (AT-ST or a followed creature): */
static uint16_t g_atst_keys[8];         /* the preset's own slots while they hold Traditional's */
static int g_atst_preset = -1;          /* the preset they belong to, -1 = not applied */

static int hoth(void) { return find(TAG_ATST) && find(TAG_SPDR); }

static volatile uint16_t *dpad(int preset) { return (volatile uint16_t *)(CTRL_BINDINGS + preset * 96 + DPAD_SLOTS); }

static void keys_back(void) {
    if (g_atst_preset < 0) return;
    for (int i = 0; i < 8; i++) dpad(g_atst_preset)[i] = g_atst_keys[i];
    g_atst_preset = -1;
}

static void keys_set(void) {
    int p = S16(CTRL_PRESET);
    if (p == g_atst_preset) return;
    keys_back();
    for (int i = 0; i < 8; i++) { g_atst_keys[i] = dpad(p)[i]; dpad(p)[i] = TRAD_DPAD[i]; }
    g_atst_preset = p;
}

static void atst_set(int on) {
    g_atst_on = on;
    U32(ATST_MODE) = on;
    if (on) { keys_set(); return; }
    keys_back();
    uint32_t s = find(TAG_SPDR);
    if (s) { uint32_t t = U32(TRAK_0); U32(t + TRAK_TARGET) = s; U32(t + 0x90) = 0; U32(t + 0x94) = 0; }
}

/* The D-up branch of the ATST think (0x800566C0) runs for ATST 0 only when not destroyed (+6 &
 * 0x20) and in states 1..4 (+0x1C4); the camera part of it is done here without the button. */
static int atst_awake(uint32_t a) {
    uint32_t st = U32(a + 0x1C4);
    return st >= 1 && st <= 4 && !(U16(a + 6) & 0x20);
}

/* The eye swings round behind the AT-ST by the rule of Dash's follow camera (0x80061774): the eye's ground yaw
 * error to behind the facing x SWING_RATE per update, halved while under SWING_SLOW, clamped to +- SWING_MAX (the
 * game's own constants, read every frame). The leash alone (Trak 0 trails its target at +0x60) did not follow a turn
 * in place (the user, 2026-10-28: the camera stays behind it and behaves as behind Dash). Dash's wall trace and his
 * strafe-key test are left out: Hoth's terrain is open (no sector to trace in) and the AT-ST has no strafe. The swing
 * is measured and applied round the head point (ATST +0x50..+0x58, 55 up): the eye CAM_BACK behind it on the ground
 * and CAM_RISE above it, looking at the point CAM_AHEAD ahead of it at its height, so the view looks 15 deg down with
 * the head point 21 deg and the feet 40 deg under the eye (half the view's height is 29 deg, fovy 58): the whole
 * AT-ST and its shots in view (the user, 2026-10-28: from straight behind its fire was not seen; farther, so the
 * AT-ST fits at its full height; then a little closer; then closer and lower). The rig is placed after Trak's update (0x800A18B8): atst_trak
 * takes Trak's class update method while the AT-ST camera is on (cheats_frame), calls the game's and then places
 * the rig, its rows rebuilt yawed and pitched as that update builds them, and zeroes its angular velocity and speed
 * +0x64. Placed before the update, the rig was moved by it whenever it was not one the update keeps (at the leash
 * from the aim, facing it): in a turn it trailed the aim by 4-6 units, and at the start of B (the ATST think zeroes
 * +0x90 / +0x94 while firing) it was thrown 40 units forward for one update (speed 2158.85, measured 2026-10-28).
 * Trak's aim offsets stay the game's 0, 0, 55: nothing reads them after the placement. */
GAME(gm_atan2d, 0x8000D750);        float gm_atan2d(float y, float x);          /* degrees */
GAME(gm_asind, 0x8000D530);         float gm_asind(float s);                     /* degrees */
GAME(gm_mat_get, 0x8000F0C8);       void gm_mat_get(volatile float *m, float *out); /* {x, y, z, yaw, pitch, roll} */
GAME(gm_mat_set, 0x8000F624);       void gm_mat_set(volatile float *m, const float *in);
#define SWING_RATE      0x800E0EF4  /* float, 0.8 on Hoth: the share of the yaw error turned per update */
#define SWING_MAX       0x800E0EF8  /* float, 40 deg: the most per update */
#define SWING_SLOW      0x800E0EFC  /* float, 15 deg: a step under it is halved */
#define TRAK_MAT        0x20        /* the rig's matrix; translation (the eye) at +0x30..+0x38 of it */
#define TRAK_LEASH      0x60        /* float, the distance it keeps (100, set by the AT-ST's move method) */
#define TRAK_SPIN       0x80        /* 3 floats, its angular velocity */
#define ATST_FACING     0x19C       /* 2 floats, ATST 0's facing on the ground */
#define TRAK_SPEED      0x64        /* float, its speed along its forward */
#define CAM_BACK        120.0f      /* the eye behind the head point, on the ground */
#define CAM_RISE        45.0f       /* the eye above the head point */
#define CAM_AHEAD       48.0f       /* the look point ahead of the head point, at its height: atan(45 / 168) = 15 deg down */

static void atst_eye(uint32_t a, uint32_t t, float ex, float ey) {
    volatile float *m = (volatile float *)(t + TRAK_MAT);
    float hx = F32(a + 0x50), hy = F32(a + 0x54), hz = F32(a + 0x58) + 55.0f;   /* the head point: the cockpit distance the bind writes */
    float fx = F32(a + ATST_FACING), fy = F32(a + ATST_FACING + 4);
    float psi = DEG(atan2_r(ey - hy, ex - hx));      /* from our last placement (ex, ey), not the update's */
    float err = wrap180(DEG(atan2_r(fy, fx)) + 180.0f - psi);
    float step = err * F32(SWING_RATE), lim = F32(SWING_MAX);
    if (absf(step) < F32(SWING_SLOW)) step *= 0.5f;
    if (step > lim) step = lim; else if (step < -lim) step = -lim;
    float r = RAD(psi + step), v[6];
    gm_mat_get(m, v);
    v[0] = hx + cos_r(r) * CAM_BACK; v[1] = hy + sin_r(r) * CAM_BACK; v[2] = hz + CAM_RISE;
    float dx = hx + fx * CAM_AHEAD - v[0], dy = hy + fy * CAM_AHEAD - v[1], dz = -CAM_RISE;
    float n = sqrt_f(dx * dx + dy * dy + dz * dz);
    v[3] = gm_atan2d(-dx, dy);
    v[4] = gm_asind(dz / n);
    gm_mat_set(m, v);
    F32(t + TRAK_SPIN) = 0; F32(t + TRAK_SPIN + 4) = 0; F32(t + TRAK_SPIN + 8) = 0;
    F32(t + TRAK_SPEED) = 0;
}

/* Trak's update with the AT-ST camera on (in Trak's class record while it is, the Gall Run's trak_update way):
 * the game's update, then the rig placed for Trak 0 on an awake ATST 0. */
#define CLASS_TRAK      0x80112EF8  /* Trak's class record */
#define CLASS_UPDATE    0x1C        /* class record: update method */
typedef void (*trak_fn)(uint32_t, uint32_t, uint32_t, uint32_t);
static uint32_t g_trak_game;            /* the game's Trak update method */
uint32_t g_atst_trak;                   /* rig placements by atst_trak; read by tests */

static void atst_trak(uint32_t obj, uint32_t a1, uint32_t a2, uint32_t a3) {
    uint32_t a = 0;
    if (obj == U32(TRAK_0) && g_atst_on && hoth()) a = find(TAG_ATST);
    if (!a || !atst_awake(a)) { ((trak_fn)g_trak_game)(obj, a1, a2, a3); return; }
    float ex = F32(obj + TRAK_MAT + 0x30), ey = F32(obj + TRAK_MAT + 0x34);
    ((trak_fn)g_trak_game)(obj, a1, a2, a3);
    atst_eye(a, obj, ex, ey);
    g_atst_trak++;
}

/* atst_trak in Trak's class record (on) or the game's back (off); only over the game's or ours (the Gall Run swaps
 * the same slot: gall_cam.c trak_method). */
static void atst_method(int on) {
    if (!g_trak_game) g_trak_game = U32(CLASS_TRAK + CLASS_UPDATE);
    uint32_t cur = U32(CLASS_TRAK + CLASS_UPDATE);
    if (cur == g_trak_game || cur == (uint32_t)atst_trak) U32(CLASS_TRAK + CLASS_UPDATE) = on ? (uint32_t)atst_trak : g_trak_game;
}

static void atst_cam(void) {
    uint32_t a = find(TAG_ATST), t = U32(TRAK_0);
    if (atst_awake(a)) {
        if (U32(t + TRAK_TARGET) != a) {
            U32(t + TRAK_TARGET) = a;
            U32(t + 0x90) = 0; U32(t + 0x94) = 0;
            F32(t + TRAK_DIST) = 55.0f;
            F32(ATST_AIM) = 18.0f;
        }
    } else if (U32(t + TRAK_TARGET) == a) {
        uint32_t s = find(TAG_SPDR);
        if (s) {                                    /* as the stock D-up leaves them */
            U32(t + TRAK_TARGET) = s; U32(t + 0x90) = 0; U32(t + 0x94) = 0; F32(t + TRAK_DIST) = 55.0f;
        }
    }
}

static int creat_get(void) {
    if (find(TAG_HUMN)) {
        uint32_t o = U32(CREATURE_OBJ);
        return !o ? C_DASH : (U32(o + 0x74) & 0xF) == KIND_WAMPA ? C_WAMPA : C_TROOPER;
    }
    if (hoth()) return g_atst_on ? C_ATST : C_SPEEDER;
    return C_NONE;
}

static void creat_set(int v) {
    if (v >= C_SPEEDER) { if (v == C_SPEEDER || hoth()) atst_set(v == C_ATST); return; }
    if (!find(TAG_HUMN)) return;
    U32(CREATURE_OBJ) = 0;
    if (v == C_DASH) return;
    uint32_t m = v == C_WAMPA ? MSG_WMP : MSG_BLS;
    F32(CREATURE_DIST) = v == C_WAMPA ? 7.0f : F32(TROOPER_DIST);
    gm_send(TAG_TROP, &m);
}

static void creat_step(int dir) {
    int c = creat_get();
    if (c >= C_SPEEDER) creat_set(c == C_ATST ? C_SPEEDER : C_ATST);
    else if (c >= 0) creat_set((c + dir + 3) % 3);
}

/* The stick and B drive the followed creature (hooks.S tramp_padread, after the raw controller read and before
 * the game decodes it): the stick's push becomes the D-pad the creature reads through the Traditional slots above
 * (up walks, left / right turn), B its attack (D-down); the stick, A and B are then taken from the game, so Dash
 * stands and does not fire (he can still be hit). The rest of the pad (the D-pad as pressed, Z, L, R, C, START) stays.
 * Runs after gallrun_pad; in the Gall Run no Trop is followed (CREATURE_OBJ 0), so it does nothing there. The
 * game ends it itself: it clears CREATURE_OBJ at a level load, a new Dash and the creature's death.
 * With the Hoth AT-ST on and ATST 0 awake, the stick and B drive it instead (atst_pad): sideways turns it (the
 * D-pad left / right through the Traditional slots), forward walks it at a speed set by the push (atst_walk),
 * centre or back stops it, B fires (D-up), Z locks an enemy (atst_aim); the speeder gets no stick, A, B or Z
 * meanwhile. Frozen it still turns and fires (the move method and the think's fire timer do not read the
 * animation). Paused, a freeze is left as it is (nothing moves); any other frame we do not drive it, atst_free lets
 * it walk again. The turn: the move method turns its yaw +0x14 by 2 a frame toward the D-pad's goal (D-left raises
 * it) and rebuilds the matrix from +8 / +0x14, so a yaw added here before the game's update holds: TURN_EXTRA x the
 * push / STICK_FULL more each frame in the stick's direction, about twice the game's rate at a full push. The camera
 * is Trak 0 on ATST 0 (atst_cam), its eye swung behind it by Dash's rule (atst_eye; 2026-10-28, the user: the
 * game's leash alone did not follow a turn). */
#define PAD_RAW         0x80113080  /* raw controller data, 6 bytes each: buttons, stick x, y at +2, +3 */
#define PAD_INDEX       0x80113060  /* u32, the controller in use */
#define STICK_GO        24          /* stick push (of about +-80, so a 30 % push) that counts as a D-pad press */
#define STICK_FULL      72          /* the push that walks the AT-ST at full speed (a little short of ~80, so it is reachable) */
#define TURN_EXTRA      2.0f        /* the yaw added a frame at STICK_FULL, over the game's own 2 */
#define ATST_YAW        0x14        /* float, ATST 0's yaw in degrees */
#define ATST_ANIM       0x108       /* the ATST's animation player; its word 0 bit 31 makes 0x800170F0 advance it by dt 0 */
#define ANIM_FROZEN     0x80000000u /* that bit: set, the walk (the animation's root motion) stands; the game keeps it */
#define ANIM_DATA       0x14        /* the player's state pointer; its float +ANIM_TIME is the walk clock */
#define ANIM_TIME       4           /* two steps of 20; both legs straight, feet down at time mod 20 = 5 */
#define STANCE_T        5.0f
#define STANCE_TOL      0.3f        /* two VIs of the clock */
#define SPDR_HP         0x204       /* float, the speeder's health (110 at Hoth's start; shot to 86 unattended) */

static float g_atst_acc;                /* the walk's share of frames: += the push each pad read, a frame walks per 1 */
static int g_atst_frozen;               /* we set ANIM_FROZEN on g_atst_obj */
static uint32_t g_atst_obj;
static float g_spdr_hp, g_spdr_pos[3];  /* the speeder as it was when the AT-ST branch started, held while it runs */

/* Let the AT-ST walk again when we stop driving it (row back, asleep, dying, another level): only on the ATST we
 * froze, and only while it is still that level's ATST 0 (another level's memory is not written). */
static void atst_free(void) {
    if (g_atst_frozen && g_atst_obj == find(TAG_ATST)) U32(g_atst_obj + ATST_ANIM) &= ~ANIM_FROZEN;
    g_atst_frozen = 0; g_atst_obj = 0; g_atst_acc = 0;
}

/* Its walk speed by whole frames: p of the frames walk (the game's own speed), the rest stand frozen. Let go
 * (p 0), it walks on at the game's speed until the clock reaches the stance and stands there (a freeze mid-step
 * left it on one leg). */
static void atst_walk(uint32_t a, int y) {
    float p = y <= STICK_GO ? 0.0f : (float)(y - STICK_GO) / (STICK_FULL - STICK_GO);
    if (p > 1.0f) p = 1.0f;
    g_atst_acc += p;
    g_atst_obj = a;
    int walk = g_atst_acc >= 1.0f;
    if (walk) g_atst_acc -= 1.0f;
    if (p == 0.0f && !g_atst_frozen) {
        float t = F32(U32(a + ATST_ANIM + ANIM_DATA) + ANIM_TIME);
        t -= 20.0f * (int)(t / 20.0f);
        walk = t < STANCE_T - STANCE_TOL || t > STANCE_T + STANCE_TOL;
    }
    if (walk) { U32(a + ATST_ANIM) &= ~ANIM_FROZEN; g_atst_frozen = 0; }
    else { U32(a + ATST_ANIM) |= ANIM_FROZEN; g_atst_frozen = 1; }
}

/* The player's speeder, left alone while the AT-ST is driven, is shot and sinks: its health and place are written
 * back each pad read to what they were when the drive started (the game's own fields). */
static void spdr_hold(void) {
    uint32_t s = find(TAG_SPDR);
    if (!s) return;
    if (!g_atst_obj) {
        g_spdr_hp = F32(s + SPDR_HP);
        for (int i = 0; i < 3; i++) g_spdr_pos[i] = F32(s + OBJ_POS_COPY + 4 * i);
    }
    F32(s + SPDR_HP) = g_spdr_hp;
    for (int i = 0; i < 3; i++) F32(s + OBJ_POS_COPY + 4 * i) = F32(s + OBJ_POS + 4 * i) = g_spdr_pos[i];
}

/* Its aim: ATST 0 picks its target (+0x16C, where the head turns and the bolts go) with 0x80004EA8 over the game's
 * tag list ATST_TARGETS (Spdr PRBT ATST ATAT rbgn, 0-ended), which writes the slot only on a find. While it is
 * driven the list is rewritten: Z not held, its first tag 0 (nothing matches) and the slot 0, so the head looks
 * ahead and B fires where it faces; Z held, TARGET_ENEMIES (the pick skips the AT-ST itself), so it takes the
 * nearest enemy and never the speeder or a rebel gun. The 5 tags are saved once and put back (tgt_back) whenever
 * the AT-ST branch stops running. Z is taken from the game meanwhile (the speeder's own Z does nothing). */
#define ATST_TARGETS    0x800DED08  /* 5 u32 class tags + 0 */
#define ATST_TARGET     0x16C       /* u32, ATST 0's target */
#define BTN_Z           0x2000
static const uint32_t TARGET_ENEMIES[4] = { 0x50524254u, TAG_ATST, 0x41544154u, 0 }; /* PRBT ATST ATAT 0 */
static uint32_t g_tgt_save[5];
static int g_tgt_saved;

static void tgt_back(void) {
    if (!g_tgt_saved) return;
    for (int i = 0; i < 5; i++) U32(ATST_TARGETS + 4 * i) = g_tgt_save[i];
    g_tgt_saved = 0;
}

static void atst_aim(uint32_t o, int z) {
    if (!g_tgt_saved) { for (int i = 0; i < 5; i++) g_tgt_save[i] = U32(ATST_TARGETS + 4 * i); g_tgt_saved = 1; }
    if (z) { for (int i = 0; i < 4; i++) U32(ATST_TARGETS + 4 * i) = TARGET_ENEMIES[i]; return; }
    U32(ATST_TARGETS) = 0;
    U32(o + ATST_TARGET) = 0;
}

static void atst_pad(uint32_t c) {
    uint32_t o = find(TAG_ATST);
    if (!atst_awake(o)) { atst_free(); tgt_back(); return; }    /* before the wave or asleep: the speeder keeps the pad */
    spdr_hold();
    uint32_t a = PAD_RAW + c * 6;
    volatile int8_t *raw = (volatile int8_t *)a;
    uint16_t b = U16(a), d = 0;
    if (raw[2] < -STICK_GO) d |= 0x0200;
    if (raw[2] > STICK_GO) d |= 0x0100;
    if (raw[2] < -STICK_GO || raw[2] > STICK_GO) F32(o + ATST_YAW) -= TURN_EXTRA * raw[2] / STICK_FULL;
    if (b & 0x4000) d |= 0x0800;
    atst_walk(o, raw[3]);
    atst_aim(o, b & BTN_Z);
    U16(a) = (b & ~(0xC000 | BTN_Z)) | d;
    raw[2] = 0; raw[3] = 0;
}

void cheats_pad(void) {
    uint32_t c = U32(PAD_INDEX);
    if (gm_paused == 1 || c > 3) return;
    if (g_atst_on && hoth()) { atst_pad(c); return; }
    atst_free();
    tgt_back();
    if (!U32(CREATURE_OBJ) || !find(TAG_HUMN)) return;
    uint32_t a = PAD_RAW + c * 6;
    volatile int8_t *raw = (volatile int8_t *)a;
    uint16_t b = U16(a), d = 0;
    if (raw[3] > STICK_GO) d |= 0x0800;
    if (raw[2] < -STICK_GO) d |= 0x0200;
    if (raw[2] > STICK_GO) d |= 0x0100;
    if (b & 0x4000) d |= 0x0400;
    U16(a) = (b & ~0xC000) | d;
    raw[2] = 0; raw[3] = 0;
}

void cheats_frame(void) {
    atst_method(g_atst_on && hoth());
    if (g_atst_on && hoth()) { U32(ATST_MODE) = 1; keys_set(); atst_cam(); }
    else if (find(TAG_HUMN) && U32(CREATURE_OBJ)) keys_set();   /* the followed creature reads +0x08..+0x0E */
    else keys_back();
    if (!g_fuel_on) return;
    uint32_t p = find(TAG_HUMN);
    if (p) F32(p + OBJ_FUEL) = F32(FUEL_MAX);
}

/* The same cheat marks the fuel gauge: the game's HUD text elements get their colour from the
 * tables at 0x80111110 (x, y) and 0x80111250 (r, g, b, a) through 0x80009138, and the fuel
 * percentage is element 23 (position 243, 15; updater 0x8006AFDC). Invincibility marks the
 * health by colour too: with bit 0x8 of the player's flags set, 0x8006AA08 gives element 21
 * (0x80, 0x80, 0xFF, 0x80) instead of green. We give the fuel that same blue, so the number
 * itself says the cheat is on (hooked from 0x80009138; see hooks.S for the argument layout).
 * Other HUDs reuse the element slot, so only the fuel's own place is tinted. */
#define HUD_FUEL        0x17        /* 0x15 is the health, 0x18 the lives */
#define HUD_FUEL_X      243
#define HUD_FUEL_Y      15
#define HUD_BLUE_RG     0x80        /* Invincibility's blue: (0x80, 0x80, 0xFF) at alpha 0x80 */
#define HUD_BLUE_B      0xFF
#define HUD_BLUE_A      0x80
GAME(gm_hud_pos, 0x80111110);       extern volatile int16_t gm_hud_pos[]; /* x, y per element */

void cheats_hud_col(uint32_t *a, uint32_t *alpha) {   /* a = { id, r, g, b } */
    if (!g_fuel_on || (int16_t)a[0] != HUD_FUEL) return;
    if (gm_hud_pos[2 * HUD_FUEL] != HUD_FUEL_X || gm_hud_pos[2 * HUD_FUEL + 1] != HUD_FUEL_Y) return;
    a[1] = HUD_BLUE_RG; a[2] = HUD_BLUE_RG; a[3] = HUD_BLUE_B;
    *alpha = HUD_BLUE_A;
}

static uint32_t tog_addr(const struct item *it) {
    return it->addr ? it->addr : DITHER + 10 * gm_dither_idx;
}

static uint32_t tog_read(const struct item *it) {
    uint32_t a = tog_addr(it);
    return it->c == 4 ? U32(a) : it->c == 2 ? U16(a) : *(volatile uint8_t *)a;
}

static int tog_get(const struct item *it) {
    if (it->id == 1) return god_get();
    if (it->id == 40) return leebo_get();
    if (it->id == 41) return g_fuel_on;
    if (it->id == 44) return g_friendly_on;
    if (it->id >= 37) return !(g_off & it->a);
    return ((tog_read(it) & it->a) != 0) ^ it->b;
}

static void tog_flip(const struct item *it) {
    if (it->id == 1) { god_set(!god_get()); return; }
    if (it->id == 40) { leebo_set(!leebo_get()); return; }
    if (it->id == 41) { g_fuel_on = !g_fuel_on; return; }
    if (it->id == 44) { g_friendly_on = !g_friendly_on; return; }
    if (it->id >= 37) { g_off ^= it->b; return; }
    uint32_t v = tog_read(it) ^ it->a, a = tog_addr(it);
    if (it->c == 4) U32(a) = v; else if (it->c == 2) U16(a) = v; else *(volatile uint8_t *)a = v;
    if (it->id == 16) gm_aa_apply();
}

static void persp(float fovy, float aspect, float far) {
    gm_view_override = 0;               /* the setter ignores calls while it is set */
    gm_persp_set(fovy, aspect, -1.0f, far);
    gm_view_override = 1;
}

/* Light direction turned 5 degrees per step: yaw about z, pitch toward/away from z (stops
 * short of straight up/down). */
#define COS5 0.9961947f
#define SIN5 0.0871557f
static void vec_turn(uint32_t a, int dyaw, int dpitch) {
    float x = S16(a), y = S16(a + 2), z = S16(a + 4), s;
    if (dyaw) {
        s = SIN5 * dyaw;
        float nx = x * COS5 - y * s;
        y = x * s + y * COS5; x = nx;
    } else {
        s = SIN5 * dpitch;
        float h = sqrt_f(x * x + y * y), nh = h * COS5 - z * s;
        if (nh < 4 || h < 1) return;
        z = h * s + z * COS5;
        x *= nh / h; y *= nh / h;
    }
    S16(a) = (int16_t)x; S16(a + 2) = (int16_t)y; S16(a + 4) = (int16_t)z;
    gm_view_override = 1;
}

/* Reset: each setting's value before its first change here (actions like 50 Lives are not
 * undone). View settings (perspective, fog, light) belong to the level they were changed in. */
static int32_t g_orig[N_ITEMS][2];
static uint8_t g_saved[N_ITEMS];
static int32_t g_orig_view = -1;  /* gm_view_override before the first view change */
static int16_t g_orig_level;

static int is_view(const struct item *it) {
    return it->kind == PERSP || it->kind == VEC || (it->kind == VAL_S && it->id >= 22);
}

static void record(const struct item *it) {
    int i = it - ITEMS;
    if (g_saved[i]) return;
    g_saved[i] = 1;
    switch (it->kind) {
    case TOG:   g_orig[i][0] = tog_get(it); break;
    case VAL_S: g_orig[i][0] = S16(it->addr); break;
    case SHIP:  g_orig[i][0] = gm_ship; break;
    case CREAT: g_orig[i][0] = creat_get(); break;
    case VEC:   g_orig[i][1] = S16(it->addr + 4);  /* fall through: x, y as one word */
    default:    g_orig[i][0] = U32(it->addr); break;
    }
    if (is_view(it) && g_orig_view < 0) {
        g_orig_view = gm_view_override;
        g_orig_level = gm_level;
    }
}

static void fog_rgb_use(const struct item *it, int v) {
    if (it->id >= 23 && it->id <= 25) gm_fog_rgb_use[it->id - 23] = v;
}

static void reset_all(void) {
    int same = gm_level == g_orig_level;
    for (int i = 0; i < N_ITEMS; i++) {
        const struct item *it = &ITEMS[i];
        int32_t o = g_orig[i][0];
        if (!g_saved[i]) continue;
        g_saved[i] = 0;
        if (is_view(it) && !same) continue;     /* the new level set its own */
        switch (it->kind) {
        case TOG:   if (tog_get(it) != o) tog_flip(it); break;
        case VAL_S: S16(it->addr) = o; fog_rgb_use(it, o); break;
        case SHIP:  if (ship_group()) ship_set(o); break;
        case CREAT: if (g_atst_on && o != C_ATST) atst_set(0);    /* the keys back too */
                    if (o != C_NONE && creat_get() != o) creat_set(o); break;
        case VEC:   S16(it->addr + 4) = g_orig[i][1];  /* fall through */
        default:    U32(it->addr) = o; break;
        }
    }
    if (g_orig_view >= 0) gm_view_override = same ? g_orig_view : 0;
    g_orig_view = -1;
}

static void adjust(const struct item *it, int dir, int big) {
    if (it->kind == SHIP && !ship_group()) return;   /* not Skyhook: nothing to pick */
    if (it->kind == CREAT && creat_get() == C_NONE) return;
    record(it);
    int st = it->c * (big ? 4 : 1) * dir;
    switch (it->kind) {
    case TOG: tog_flip(it); break;
    case VAL_F: case PERSP: {
        float v = F32(it->addr) + F20(st);
        if (v < F20(it->a)) v = F20(it->a);
        if (v > F20(it->b)) v = F20(it->b);
        if (it->kind == VAL_F) F32(it->addr) = v;
        else if (it->id == 18) persp(v, -1, -1);
        else if (it->id == 19) persp(-1, v, -1);
        else persp(-1, -1, v);
        break;
    }
    case VAL_S: {
        int v = S16(it->addr) + st;
        if (v < it->a) v = it->a;
        if (v > it->b) v = it->b;
        S16(it->addr) = v;
        fog_rgb_use(it, v);
        gm_view_override = 1;
        break;
    }
    case VEC: for (int i = big ? 3 : 1; i; i--) vec_turn(it->addr, dir, 0); break;
    case SHIP: ship_set((gm_ship + dir + 3) % 3); break;
    case CREAT: creat_step(dir); break;
    }
}

static void resume(void) {
    gm_set_pause(0);
    gm_start_latch = 1;
    gm_pause_cursor = 0;
    gm_pause_list = 1;
    g_cheats_open = g_cheats_sel = 0;
}

static void run(const struct item *it) {
    uint32_t p;
    if (it->kind == ACT_PLAY || it->kind == LVL) resume();
    switch (it->id) {
    case 0: gm_give_humn(0, 3); gm_give_humt(0, 3); gm_stuff = 1000; break;
    case 3: gm_lives = 50; break;
    case 5:
        if ((p = find(TAG_HUMN))) gm_kill_humn(p, DIE_CAUSE, 1, 0);
        if ((p = find(TAG_HUMT))) gm_kill_humt(p, DIE_CAUSE, 0);
        break;
    case 6:
        if ((p = find(TAG_HUMN))) gm_tp_humn(p);
        if ((p = find(TAG_HUMT))) gm_tp_humt(p);
        if ((p = find(TAG_BIKE))) gm_tp_bike(p);
        break;
    case 7:
#if FEATURE_GALLRUN
        if (g_lvl == N_LEVELS - 1) { gallrun_start(); break; }
#endif
        gm_level_load(g_lvl); break;
    case 8: gm_level_load(gm_level); break;
    case 33:
        record(&ITEMS[ROW(18)]); record(&ITEMS[ROW(19)]);
        gm_persp[0] = 67.5f;
        gm_persp[1] = 1.3333334f;
        gm_view_override = 0;
        break;
    case 34: reset_all(); break;
    }
    g_flash = 20;
}

/* ---- input ---- */

static void screen_input(uint32_t h) {
    uint32_t pressed = h & ~g_prev;
    const struct item *it = &ITEMS[g_cheats_row];
    int lr = h & 1u << B_R ? 1 : -1;
    if (pressed & (1u << B_B | 1u << B_START)) {
        g_cheats_open = 0;
        g_cheats_sel = 1;
        gm_pause_list = 1;
        g_swallow = 1;
        sfx();
        return;
    }
    if (repeat(h, 1u << B_UD | 1u << B_DD | 1u << B_L | 1u << B_R | 1u << B_CU | 1u << B_CD)) {
        if (h & 1u << B_UD) g_cheats_row = (g_cheats_row + N_ITEMS - 1) % N_ITEMS;
        else if (h & 1u << B_DD) g_cheats_row = (g_cheats_row + 1) % N_ITEMS;
        else if (it->kind == VEC && (h & (1u << B_CU | 1u << B_CD))) {
            record(it);
            vec_turn(it->addr, 0, h & 1u << B_CU ? 1 : -1);
        } else if (it->kind == LVL && (h & (1u << B_L | 1u << B_R)))
            g_lvl = (g_lvl + lr + N_LEVELS) % N_LEVELS;
        else if (it->kind != ACT && it->kind != ACT_PLAY && (h & (1u << B_L | 1u << B_R)))
            adjust(it, lr, g_rep_t > 60);
        if (h & (1u << B_UD | 1u << B_DD)) { g_flash = 0; sfx(); }
        if (g_cheats_row < g_top) g_top = g_cheats_row;
        if (g_cheats_row >= g_top + ROWS) g_top = g_cheats_row - ROWS + 1;
    }
    if (pressed & 1u << B_A) {
        if (it->kind == ACT || it->kind == ACT_PLAY || it->kind == LVL) run(it);
        else if (it->kind == TOG || it->kind == SHIP || it->kind == CREAT) adjust(it, 1, 0);
        sfx();
        if (it->kind == ACT_PLAY || it->kind == LVL) g_swallow = 1;
    }
}

/* Pause list: our entry goes after the game's 3 or 4. The game's own cursor moves on
 * D-pad/stick with its own wrap; at its ends we step in before it does. */
static void list_input(uint32_t h) {
    int n = 3 + secrets();
    int down = 1u << B_DD, up = 1u << B_UD;
    if (g_cheats_sel) {
        gm_pause_cursor = CURSOR_NONE;
        if (repeat(h, down | up)) {
            g_cheats_sel = 0;
            gm_pause_cursor = h & up ? n - 1 : 0;
            g_swallow = 1;
            sfx();
        } else if (h & ~g_prev & (1u << B_A | 1u << B_START)) {
            g_cheats_open = 1;
            gm_pause_list = 0;
            g_lvl = LEVEL_FROM(gm_level);
            g_flash = 0;
            sfx();
        }
        clear_pad();
        return;
    }
    int c = gm_pause_cursor;
    int at_end = (c == n - 1 && (h & down)) || (c == 0 && (h & up));
    if (!at_end) { g_rep_t = 0; return; }
    if (repeat(h, down | up)) {
        g_cheats_sel = 1;
        gm_pause_cursor = CURSOR_NONE;
        g_swallow = 1;
        sfx();
    }
    clear_pad();                  /* the game would wrap around past us */
}

void cheats_pause(void) {
    if (gm_paused != 1) {
        g_cheats_open = g_cheats_sel = g_swallow = 0;
        g_prev = 0;
        return;
    }
    uint32_t h = held();
    if (g_swallow) {
        if (h) { clear_pad(); g_prev = h; return; }
        g_swallow = 0;
    }
    if (g_cheats_open) {
        screen_input(h);
        if (g_cheats_open || g_cheats_sel) clear_pad();
    } else if (gm_pause_list && !gm_pause_confirm && !gm_options_open) {
        list_input(h);
    } else {
        g_cheats_sel = 0;
    }
    g_prev = h;
}

/* ---- drawing ---- */

static char g_buf[48];
static uint32_t g_ctx;

static void color(int r, int g, int b) { gm_text_color(r, g, b, 0xFF); }

static void text(int x, int y, const char *s) {
    gm_text_pos(x, y);
    gm_text_draw(g_ctx, s);
}

/* The pause list's flicker on the selected item (0x8001FC90). */
static void color_selected(void) {
    int c[3];
    for (int i = 0; i < 3; i++)
        c[i] = (int)((((float)gm_random() / 2147483648.0f) * 0.5f + 0.5f) * (i == 1 ? 150 : 255));
    color(c[0], c[1], c[2]);
}

#define SPF(...) gm_sprintf(g_buf, __VA_ARGS__)

/* Fixed point with 2 decimals, without the game's float formatting. */
static void fmt_fixed(float v) {
    int n = (int)(v * 100 + 0.5f);       /* every such value here is positive */
    SPF("~s%d.%02d", n / 100, n % 100);
}

/* "~s" + the entry's name from the game, cut before its value template: "Jump Power: xxxxxxxx",
 * "Fog Red xxxxxxxx", "Wall Ghost OFF ", " Lighting ON  ". Our rows have their own names. */
static void name_text(const struct item *it) {
    const char *src = it->id == 7 ? "Go to level" : it->id == 34 ? "Reset cheats"
                    : it->id == 37 ? "New Controls" : it->id == 38 ? "Z Lock-On" : it->id == 39 ? "Ledge Hang"
                    : it->id == 40 ? "Leebo Scanner"
                    : it->id == 41 ? "Jetpack Fuel"
                    : it->id == 42 ? "Ship"
                    : it->id == 43 ? "Creature Cam"
                    : it->id == 44 ? "Friendly Wampas"
                    : gm_debug_names[it->id];
    char *d = g_buf;
    *d++ = '~'; *d++ = 's';
    if (*src == ' ') src++;
    while (*src && *src != ':' && !(src[0] == 'x' && src[1] == 'x') && !(src[0] == ' ' && src[1] == 'O'))
        *d++ = *src++;
    while (d > g_buf + 2 && d[-1] == ' ') d--;
    *d = 0;
}

static void value_text(const struct item *it) {
    g_buf[0] = 0;
    switch (it->kind) {
    case TOG:   SPF("~s%s", tog_get(it) ? "ON" : "OFF"); break;
    case VAL_F: fmt_fixed(F32(it->addr)); break;
    case PERSP: if (it->id == 19) fmt_fixed(F32(it->addr));
                else SPF("~s%d", (int)F32(it->addr)); break;
    case VAL_S: SPF("~s%d", S16(it->addr)); break;
    case LVL:   SPF("~s%d", g_lvl); break;
    case SHIP:  SPF("~s%s", !ship_group() ? "(Skyhook)" : gm_ship == 1 ? "X-Wing"   /* <= 10 chars fit */
                              : gm_ship == 2 ? "TIE" : "Outrider"); break;
    case CREAT: {
        static const char *const V[] = { "(none)", "Dash", "Wampa", "Trooper", "Speeder", "AT-ST" };
        SPF("~s%s", V[creat_get() + 1]); break;
    }
    case VEC:   SPF("~s%d %d %d", S16(it->addr), S16(it->addr + 2), S16(it->addr + 4)); break;
    default:
        if (g_flash && it == &ITEMS[g_cheats_row]) SPF("~sdone");
        else if (it->id == 34) {
            int n = 0;
            for (int i = 0; i < N_ITEMS; i++) n += g_saved[i];
            if (n) SPF("~s%d changed", n);
        }
        break;
    }
}

static void draw_screen(void) {
    color(0x50, 0xA0, 0x50);
    text(160, 14, "~s~cCheats");
    for (int r = 0; r < ROWS && g_top + r < N_ITEMS; r++) {
        const struct item *it = &ITEMS[g_top + r];
        int y = ROW_Y + r * ROW_H;
        if (g_top + r == g_cheats_row) color_selected(); else color(0x40, 0x80, 0x80);
        name_text(it);
        text(NAME_X, y, g_buf);
        value_text(it);
        if (g_buf[0]) text(VALUE_X, y, g_buf);
    }
    color(0x50, 0xA0, 0x50);
    const struct item *it = &ITEMS[g_cheats_row];
    const char *hint = it->kind == ACT || it->kind == ACT_PLAY ? "~s~cA: do it    B: back"
                     : it->kind == VEC ? "~s~cL/R, C-Up/C-Down: turn    B: back"
                     : it->kind == TOG ? "~s~cA, L/R: change    B: back"
                     : "~s~cL: less   R: more    B: back";
    if (it->kind == LVL) {
        SPF("~s~c%s", LEVEL_NAMES[g_lvl]);
        text(160, ROW_Y + ROWS * ROW_H + 4, g_buf);
        hint = "~s~cL/R: choose   A: go   B: back";
    } else {
        text(160, ROW_Y + ROWS * ROW_H + 4, hint);
        SPF("~s~c%d/%d", g_cheats_row + 1, N_ITEMS);
        hint = g_buf;
    }
    text(160, ROW_Y + ROWS * ROW_H + 16, hint);
    if (g_flash) g_flash--;
}

void cheats_draw(uint32_t ctx) {
    if (gm_paused != 1) return;
    g_ctx = ctx;
    if (g_cheats_open) { draw_screen(); return; }
    if (!gm_pause_list || gm_pause_confirm || gm_options_open) return;
    if (gm_pause_cursor == 3) return;   /* Game Secrets selected: the game draws its hints over the list */
    if (g_cheats_sel) color_selected(); else color(0x40, 0x80, 0x80);
    text(LIST_X, LIST_Y + 18 * (3 + secrets()), "~s~cCheats");
}
