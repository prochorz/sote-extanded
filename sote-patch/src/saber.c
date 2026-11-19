/* Luke's lightsaber (feature saber; needs guard, the Look row): with the Look on Luke (g_guard_on 2) the on-foot player
 * (Humn) has one more weapon, id 6, in the game's C-up cycle; Dash's own look and the Guard look keep the game's weapons.
 *
 * The slot. The game's weapon table (0x800E1338 + 12 * id: pickup bit, HUD icon element, shot cost) already has an
 * entry 6 (bit -1: always held, icon element 6, cost 0), and the fire function does nothing with id 6 (its cost test
 * fails and the id is past its jump table's 6 entries). Its C-up cycle (0x8006E410(humn, 1), called from the Humn
 * weapon code at 0x80072798) steps 0 laser, 2 flame, 1 pulse, 3 seeker, 5 Disruptor, 4 Stunner, 0, skipping weapons
 * with no ammo or pickup, and any other id steps to 0. saber_cycle takes that call: the game's cycle, then with the
 * Look on Luke, an id that went to 0 (from any other id) or stayed 0 is made 6 by the game's own set-weapon call
 * (0x8006E608: its icon, its switch sound); from 6 the game's step goes to 0. So the saber sits after the Stunner and
 * before the laser, wherever the cycle comes round to the laser. The id is carried across levels by the game (saved
 * at the level's end, set again at the next one's start): saber_frame sets it back to the laser whenever it is 6 and
 * the Look is not Luke. The HUD's ammo text (element 0x19 at 290, 188) would print the slot +0xC0 + 4 * 6, which is
 * the Humn's clock +0xD8: cheats_hud_col draws it with alpha 0 while the saber is out (saber_out).
 *
 * The blade: guard.c puts the image's first SABR mesh, the hilt (harness/luke/saber_model.py, in guard.bin), in the
 * weapon's slot of the hand while the id is 6; late() draws the second, the blade's light, after the level.
 *
 * The sounds: local/game/saber_snd.bin (harness/saber/saber_snd.py: on, the hum's loop, three swings, the deflect, a
 * hit, the spin, off; raw16 mono, the hum, the swings and the spin at 11025 Hz, the rest at 22050 Hz, trimmed of the
 * files' silence), appended to the ROM by build.py (SABER_SND_ROM, the per-sound table SABER_SND_TAB, each sound's
 * pitch SABER_SND_PITCH: its rate against the synth's 44100 Hz, 0.25 or 0.5, as float bits). The game's bank (libultra ALBankFile: the bank at *0x800EEB04, its instrument at +0xC, s16 sound
 * count +0xE = 131, the ALSound pointers from +0x10) is loaded once at boot and the same RAM on every level. Once
 * it is there, bank() gives it a copy of the instrument with our nine sounds after the game's 131 (ids 0x83..0x8B: no
 * game code plays them, the game's own ids untouched) and points the bank at the copy; the game's sound lookup
 * (0x8000686C) bounds an id by the copy's count. Our sounds are raw16 wave tables (type 1, the wave-table load's own
 * case: no encoder needed; the base an absolute ROM offset, as the game's), the game's keymap and envelopes (the
 * one-shots' 5 s decay, the looped sounds' 1000 s). Played by the game's call 0x80007340(id, priority 4, the sound's
 * pitch snd_pitch[], volume, loop): the hum looped, asked every game frame while the saber is out (a
 * looped sound lives while asked; when the asks stop the game fades it out by itself, ~0.4..0.8 s); on at the switch
 * to 6, off at the switch away, as one-shots. Without the blob (SABER_SND_ROM 0) the saber is silent.
 *
 * The swings (D: a whole-body move, no arm layer over the run): seven blocks of ours, sw1 sw2 sw3 (the combo), spin,
 * and swp1 swp2 swp3 (the combo in place, below),
 * copies of Dash's `shoo` (hang.c's anim_clone: the bone entries keep his nodes) whose tracks point at the image's
 * SWN2 table (harness/luke/saber_moves.py, in guard.bin after the blade; an older image's table has another magic:
 * no swings rather than wrong ones). sw1 and the spin leave the hold's standing pose and every move returns to it;
 * sw2 and sw3 start on the key the one before rests in at its link, so they are only ever started chained. The combo
 * is two-handed with a step of the feet, the spin one-handed. Linked at the head of his chain whenever they are not
 * in it (a new level's chain: copied again from its shoo). One plays by the game's play (0x80017344, how 5: blended
 * over BLEND into another block, set back to its first frame on the block already playing, where how 3 returned at
 * once and a second sw1 never restarted) with his controller (0x800E1328: +0 time, +4 the current descriptor) on a descriptor of ours, kind 7 and
 * +0x14 = the move's length: the game's lower-kind requests (the run, the stand) are refused while it plays. At its
 * end the controller's time is put past that length (end_move) and, on the ground, the game's own stand request is
 * asked (hold_stand: standing with no input the game asks for nothing, and the controller stayed on our descriptor
 * until his next move). The press: B with the saber out sets the Humn's +0x74 bit 0x1000 once per
 * press inside his control (and clears it after its fire call, 0x80079668: id 6 fires nothing); hang.c's set_anim
 * hook runs inside that control after it is set, and saber_setanim latches it; the same hook refuses the game's aim
 * pose (set_anim 0x14, B held standing: shoo) while the saber is out, asking the stand (0) instead. A press with
 * nothing playing starts sw1. A press before a swing's cut is dropped; from the cut on it queues the next of the
 * combo (sw1, sw2, sw3) while the time is under the move's link + CHAIN_LATE, and sw1 otherwise (after sw3 and the
 * spin always). The link (the table's, s) is where the strike is over and the return to the hold begins: a queued
 * move of another block starts there (the same block: at the end, whose last key is its first), a request of the
 * game's for a moving block (Dash's descriptor kind >= 2: a run, a jump, a strafe) cuts the return short there
 * (saber_setanim, before the game weighs the request), and bolts are deflected again. B still held (+0x74 bit
 * 0x800) 0.6 s after a press plays the spin instead. A combo swing steps him forward (the move's step, world units)
 * through his velocity (+0x98) over the table's step window, the time its feet step in; standing still otherwise
 * while it plays (his run stops for it). The velocity is written every update of his control, from core.c's stick
 * decode (saber_step): at set_anim's entry, as first done, it landed only on the frames the game made a request, so
 * a lone swing stood still and the combo stepped by its B taps. Until the link the stick's move is zeroed and his turn
 * held to a little (core.c: a held stick drifted him off the step and turned him 124..152 deg). A body or a wall in his way stops him as it stops a
 * run, so a stepping block's planted foot slid back against a body; so a combo swing started with a live Trop, boss or
 * Guri within its step (blocked: ahead of him under the step + his HUMN_RADIUS + its radius, across under the radii)
 * plays the move's in-place block (INPL + the move: the same keys, cut, link, reach and damage, step 0, both feet on
 * their hold places, the crouch as the stepping one's). The start decides: a body that walks into the step later
 * leaves the stepping block playing; the combo's logic reads the logical move (M.cur), every read of the playing
 * block's table entry the block (M.blk); walls are not tested (the feet still play the step there). At the move's cut (its time in the table) one hidden area shot: Dash's pulse
 * shot (kind 6, the game's spawn 0x80064584, he the sender: it never hits him) made still and hidden and short-lived
 * (flags 0x4004; one send: its first update sends it, then saber_frame zeroes its damage and life; a life of 0.05 s
 * as first measured missed when that update's dt was 0.065), its scale the reach / 2.5 (the area test: horizontal distance < the target's
 * +0x60 + 2.5 x scale), its damage the move's; at the blade's middle (the hand node's world matrix: his placement node
 * and his bone nodes composed, the table's middle point in it), the spin's at his centre (it cuts all round). A
 * Trop's, boss's (or Guri's) health dropping within 0.2 s plays the hit sound there (the game's placed sound
 * 0x800074BC). A boss takes it through his own 'shot' handler (0x800523F8: message flags with 0x20 and no hit shell
 * named: the plain path, his own scale, IG-88 0.4: 170 -> 68), as long as the shot's height span [z - R, z + R] meets
 * his (+0x58 + +0x68 .. +0x6C, 0..8 on IG-88): the area send (0x80065660) tests it like a Trop's. A swing ends
 * at once, its queue dropped, on death, a hang, a swim, the Look leaving Luke, the saber put away, or the game taking
 * his controller from our descriptor.
 *
 * Deflection: while the saber is out on Luke the Blst class record's update (0x80112E38 + 0x1C, the game's 0x80033B7C)
 * is saber_blst (the game's put back otherwise, only over the game's or ours). A bolt's hit is a sweep ahead of its
 * drawn place: its first update sweeps [+0x50, + +0x70 (length) x +0xA0 (dir)] at once (flag 0x20000 in +0x60), each
 * later one [+0x50 + +0x84 (head offset), + +0xA0 x +0x74 (speed) x dt]; a shooter within ~30 units hits in the frame
 * it fires, so the turn is made right before the bolt's own update, whoever fired it (pass 2's order puts the Blst
 * update after every class that fires). The test: a live bolt (+0x60 0x10000) not his (owner +0x64), no swing
 * playing before its link, its sweep meeting him as the game's own hit test does (saber_blst), coming from within +-60 deg of his
 * facing. The turn (measured: the bolt flies back and hurts its shooter, the owner made him so the hit test skips the
 * Humn class): its head kept, its dir and forward row at the shooter (the head's height), right = forward x up, up z,
 * velocity speed x dir, head offset length x dir, its place the head - length x dir, owner him; the deflect sound;
 * then the game's update. Each turned bolt flashes where it crossed his plane (flash; the parry puts the blade
 * there): one of the game's Expl objects of kind 4 (the Disruptor's shot, sprite type 2), spawned by 0x80064584 (no
 * sound of its own) and rewritten to flags 0x2122 (0x2000 as every type-2 kind, 0x100 drawn in its RGBA bytes, 0x20
 * facing the camera, 2 grows; nothing that moves, hurts, bursts or whitens), a small white-green disc that grows for
 * 0.12 s and ends (a life end without 0x40 ends the object, no burst).
 * The parry: the same plane test on the sweep lengthened by PARRY_LEAD s of its flight sees a bolt coming; Luke snaps
 * the blade into its path: the image's grid of poses (5 sides x 4 heights on two planes in front of him, 1.5 and 2.25
 * ahead, each node's blade through it) blended at the crossing's place (its side, height and distance ahead, the
 * distance carried along his own move over the time to the pose), reached in the time left before the crossing (PARRY_IN ..
 * PARRY_LEAD: a near shooter a flick, a far one a smooth move), held, eased back. A bolt that reaches the plane before
 * the pose does (a near one, or one first seen as it crosses) is held there, its head at the crossing and its update
 * skipped, until the blade arrives (at most HOLD_MAX past the pose's time), then turned and flashed. Only the seven bones of the arm layer move, over whatever block plays (standing,
 * walking, running, turning: the legs and the run untouched): saber_pose, from the Humn's draw hook (0x8007A134, after
 * guard_place), lerps each bone instance's sampled angles (+0x10..+0x18) to the pose and re-poses its node with the
 * game's 0x80016E28; the update re-samples every node each frame, so the write shows in that frame and never
 * compounds. None starts in the air; a swing, a hang, death or the saber put away ends one.
 *
 * Guri's hold (saber_dark: melee.c's phase from her grab to his get-up): the saber goes dark, the weapon id kept 6:
 * the hand's slot empty (guard.c), no hum, swing, light or deflection, the 'off' sound at the grab; at the combo's end
 * it lights again by itself with 'on'.
 *
 * Called from cheats_frame() once per rendered frame, after guard_frame().
 *
 * Where it lives: not in the 64 KB payload. Its code and data are link.ld's .saber at 0x805C0000 (a fixed 32 KB ROM
 * slot, the ROM's last blob, DMAed by _start after the cheats slot, copied by inject()); its .bss (the swing blocks and
 * descriptors) is .saber_bss at 0x805C8000, up to 0x80600000, zeroed by _start and by inject(). Built -Os with minsize
 * functions: that object code is the one whose frame cost was measured. */
#include "common.h"

#define GAME(name, addr) __asm__(".globl " #name "\n.set " #name ", " #addr)
GAME(sb_cycle, 0x8006E410);  void sb_cycle(uint32_t humn, int dir);       /* the C-up weapon cycle */
GAME(sb_setw, 0x8006E608);   void sb_setw(uint32_t humn, int id);         /* set the weapon: icon, switch sound */
GAME(sb_sfx, 0x80007340);    void sb_sfx(int id, int prio, uint32_t pitch, int vol, int loop);
GAME(sb_sfx_at, 0x800074BC); void sb_sfx_at(int id, int prio, uint32_t pitch, int vol, const float *at, int zero);
GAME(sb_play, 0x80017344);   void sb_play(uint32_t state, uint32_t tag, int how, float start, float blend, float speed);
GAME(sb_spawn, 0x80064584);  void sb_spawn(int kind, float *pos, void *dir, float *vel, int msg, uint32_t sector, uint32_t shooter);

#define HUMN_WEAPON     0xB8        /* s16: the on-foot weapon id */
#define SABER           6
#define LASER           0
#define GAME_CLOCK      0x8018E9A8  /* double, game time (s): stands while paused */

#define SND_BANK        0x800EEB04  /* -> the game's bank: +0xC its one instrument */
#define SND_STOCK       131         /* the game's sounds */
#define SND_KEYMAP      0x80108C88  /* the game's shared keymap */
#define SND_ENV_SHOT    0x80108C90  /* its one-shots' envelope (decay 5 s) */
#define SND_ENV_LOOP    0x80108CB0  /* its looped sounds' (decay 1000 s) */
#define SND_PRIO        4           /* the game's weapon sounds' */
#define SND_QUEUE       0x80110FE8  /* the game's sound queue: 8 x 0x20 (+0 state, 0xFFFFFFFF free; +4 id) */
#define SND_SLOTS       8
#define SND_SWITCH      0x15        /* the weapon switch click (the game's set-weapon 0x8006E608 plays it) */
#define VOL_HUM         20000
#define VOL_SHOT        28000       /* the laser's */
enum { S_ON, S_HUM, S_SW1, S_SW2, S_SW3, S_DEFLECT, S_HIT, S_SPIN, S_OFF, S_N };
#define SND_ID0         SND_STOCK   /* our first id: 0x83 */

#ifndef SABER_SND_ROM
#define SABER_SND_ROM   0
#endif
#if SABER_SND_ROM
static const uint32_t snd_tab[2 * S_N] = { SABER_SND_TAB };   /* (offset in the blob, bytes) per sound */
static const uint32_t snd_pitch[S_N] = { SABER_SND_PITCH };  /* float bits: the sound's rate / the synth's 44100 */
#endif

static uint32_t g_inst[4 + SND_STOCK + S_N];        /* the instrument's copy: header 0x10, the sound pointers */
static uint32_t g_snd[S_N][4];                      /* ALSound: envelope, keymap, wave table, pan / volume / flags */
static uint32_t g_wave[S_N][5];                     /* ALWaveTable: base, length, type / flags, loop, book */
static uint32_t g_loop[3];                          /* the hum's ALRawLoop: start, end, count (-1: for ever) */
static int g_snd_ok;                                /* the bank plays our ids */
static uint32_t g_h;                                /* the Humn seen last frame */
static int g_was;                                   /* the saber was out then */
static double g_clock;                              /* the game clock then */

/* ---- the swings ---- */
#define CTL             0x800E1328  /* Dash's animation controller: +0 time, +4 the current descriptor */
#define CTL_FREE        100.0f      /* a time past our descriptors' +0x14: the game's requests are taken again */
#define ANIM_AIM        0x14        /* set_anim: B held standing (shoo) */
#define ANIM_STAND      0x00
#define ANIM_TROT       0x05        /* trot (5, 6): the run our arm copies hold the saber in */
#define ANIM_RUNFIRE    0x07        /* trtg (7, 8): the run with B held, Dash's pistol arms (blade out of his back) */
#define ANIM_DIE        0x17        /* diea: the damage function's (0x800732D4) death request, once below health 1 */
#define BLOCK_SIZE      0xC18
#define TAG_SHOO        0x73686F6Fu
#define SWNG_MAGIC      0x53574E32u /* 'SWN2' */
#define SABR_MAGIC      0x53414252u
#define HUD_SPRITES     0x8013CE2C  /* -> the level's HUD sprite records, one per element */
#define ICON_WH         0x00600024u /* a weapon icon's width, height (96 x 36) */
#define LITN_AT         (GUARD_RAM + 8 + 8 * 19 + 12)
#define MOVES           7           /* the table's blocks: sw1 sw2 sw3 spin, then swp1 swp2 swp3 (the combo in place) */
#define SPIN            3
#define INPL            4           /* the first in-place block: INPL + i plays combo move i with a body in its step */
#define DESC_ID         0x70        /* our descriptors' ids (Dash's list ends at 26; hang.c's 0x7E / 0x7F) */
#define BLEND           0.1f        /* s a swing blends in (how 5); a chained one starts on the pose the last rests in */
#define CHAIN_LATE      0.1f        /* s past a swing's link a press still chains the next; later the blade is on its
                                     * way back to the hold and the next would start from a pose it has left: sw1 again */
#define SPIN_HOLD       0.6f        /* s B is held after a press for the spin */
#define STEP_GAIN       1.39f       /* the speed asked over the step, written every update: the standing friction keeps 0.9 x 0.8 = 0.72 of it */
#define SHOT_KIND       6           /* Dash's pulse shot: the area shot's kind */
#define SHOT_FLAGS      0x4004      /* area 'shot' + hidden */
#define SHOT_LIFE_S     0.3f        /* long enough for its first update whatever that frame's dt; then made spent */
#define SHOT_MSG        0x60        /* the pulse shot's message flags */
#define HIT_WAIT        0.2f        /* s a target's health is watched after the cut */
#define VOL_HIT         28000
#define TAG_EXPL        0x4578706Cu
#define FLASH_KIND      4           /* the Disruptor's shot (sprite type 2): the kind the game draws tinted */
#define FLASH_FLAGS     0x2122      /* type 2's 0x2000, 0x100 tint, 0x20 faces the camera, 2 grows */
#define FLASH_SCALE     0.4f
#define FLASH_GROW      6.0f        /* the scale's growth per s */
#define FLASH_LIFE      0.12f       /* s */
#define FLASH_RGBA      0xC8FFC8FFu /* white-green */
#define TAG_TROP_       0x54726F70u
#define TAG_GURI_       0x47757269u
#define CLASS_LIST      0x80112830  /* -> 0-ended pointers to the class records */
#define DASH_DESCS      0x800E0F14  /* Dash's animation descriptors, 0x24 each by id: +0x20 the kind (0 / 1 stands, >= 2 moving) */
#define SWING_ID(i)     (DESC_ID + (i))

static uint32_t g_blk[MOVES][BLOCK_SIZE / 4];      /* our blocks (copies of shoo) */
static uint32_t g_desc[MOVES][9];                   /* their descriptors */
static int g_press;                                 /* a press latched by saber_setanim this update */
static float g_step_v;                              /* the swing's forward speed now (units/s, 0: standing) */
static uint32_t g_shot;                             /* the area shot made at the cut, until its first update ran */
/* cur: the logical move (0..2 the combo, SPIN), what the combo's logic reads; blk: the table's block playing (cur, or
 * INPL + cur in place), what every read of the playing move's entry takes */
static struct { int cur, next, hit; float t, link, hold, watch, hp; float at[3]; int blk; } M = { -1, -1 };
int g_saber_move = -1;                              /* the move playing (tests): 0..2 sw1..sw3, 3 spin, -1 none */
int g_saber_cuts;                                   /* the cuts made, + 1 at each hit() (the duel's counter) */
float g_saber_hit[4];                               /* the last hit: place, reach (tests) */

static uint32_t sabr(void) {        /* the image's SABR record, 0: none */
    uint32_t at = LITN_AT + 12 + 4 * (1 + U32(LITN_AT + 4)) * U32(LITN_AT + 8);
    return U32(LITN_AT) == 0x4C49544Eu && U32(at) == SABR_MAGIC ? at : 0;
}

static uint32_t swng(void) {        /* the image's SWNG table, 0: none */
    uint32_t at = sabr(), t;
    if (!at || !valid_ptr(t = U32(at + 12))) return 0;
    return U32(t) == SWNG_MAGIC && U32(t + 4) == MOVES ? t : 0;
}

/* The HUD icon: the level's weapon sprites (*0x8013CE2C, one per HUD element; the weapon table gives id 6 element 6)
 * have slot 6 empty (on every level checked): the image's sprite (SABR +16, the game's sprite record, 96 x 36) is put
 * there while the saber is out, taken out after (only when it is ours); the level's own table is new each level. */
static void icon(int out) {
    uint32_t at = sabr(), s = at ? U32(at + 16) : 0, tab = U32(HUD_SPRITES);
    if (!valid_ptr(tab) || !valid_ptr(s) || U32(s + 4) != ICON_WH) return;
    uint32_t *slot = (uint32_t *)(tab + 4 * SABER);
    if (out && !*slot) *slot = s;
    else if (!out && *slot == s) *slot = 0;
}
#define MV(t, i)        ((t) + 40 + 0x2C * (i))     /* {tag, keys, keys/s, cut s, reach, damage, step, tracks, link s, step from s, step to s} */
static float mv_len(uint32_t t, int i) { return (float)(U32(MV(t, i) + 4) - 1) / F32(MV(t, i) + 8); }

static int luke(void) { return g_guard_on == 2; }
static uint32_t humn(void) { return ((find_fn)FIND_CLASS)(TAG_HUMN, 0); }

int saber_out(void) {
    uint32_t h = humn();
    return h && S16(h + HUMN_WEAPON) == SABER;
}

void saber_cycle(uint32_t h, int dir) {
    int old = S16(h + HUMN_WEAPON);
    sb_cycle(h, dir);
    if (luke() && S16(h + HUMN_WEAPON) == LASER && old != SABER) {
        sb_setw(h, SABER);
        /* the cycle's landing on the laser and the set queued the game's switch click (a pistol drawn): the saber
         * comes on with its own 'on' only, so the click's requests are freed in the frame they are queued, before
         * the player reads the queue (the switch from the saber to the blaster keeps it) */
        for (int i = 0; i < SND_SLOTS; i++)
            if (U32(SND_QUEUE + 0x20 * i + 4) == SND_SWITCH) U32(SND_QUEUE + 0x20 * i) = 0xFFFFFFFFu;
    }
}

static void bank(void) {
#if SABER_SND_ROM
    uint32_t b = U32(SND_BANK), in;
    if (!valid_ptr(b) || !valid_ptr(in = U32(b + 0x0C))) return;
    if (in == (uint32_t)g_inst) return;
    g_snd_ok = 0;
    if (S16(in + 0x0E) != SND_STOCK) return;
    for (int i = 0; i < 4 + SND_STOCK; i++) g_inst[i] = U32(in + 4 * i);
    for (int i = 0; i < S_N; i++) {
        uint32_t *w = g_wave[i], *s = g_snd[i];
        w[0] = SABER_SND_ROM + snd_tab[2 * i]; w[1] = snd_tab[2 * i + 1];
        w[2] = 0x01010000u;                         /* type 1 raw16, flags 1 (pointers already in place) */
        w[3] = i == S_HUM ? (uint32_t)g_loop : 0; w[4] = 0;
        s[0] = i == S_HUM ? SND_ENV_LOOP : SND_ENV_SHOT; s[1] = SND_KEYMAP; s[2] = (uint32_t)w;
        s[3] = 0x407F0100u;                         /* pan 64, volume 127, flags 1: as the game's */
        g_inst[4 + SND_STOCK + i] = (uint32_t)s;
    }
    g_loop[0] = 0; g_loop[1] = snd_tab[2 * S_HUM + 1] / 2; g_loop[2] = 0xFFFFFFFFu;
    g_inst[3] = (g_inst[3] & 0xFFFF0000u) | (SND_STOCK + S_N);   /* +0xE: the sound count */
    U32(b + 0x0C) = (uint32_t)g_inst;
    g_snd_ok = 1;
#endif
}

static void play(int s, int vol, int loop) {
#if SABER_SND_ROM
    if (g_snd_ok && snd_tab[2 * s + 1]) sb_sfx(SND_ID0 + s, SND_PRIO, snd_pitch[s], vol, loop);
#endif
}

static int linked(uint32_t h) {
    uint32_t b = U32(h + OBJ_ANIM_CHAIN);
    for (int i = 0; i < 40 && valid_ptr(b); i++, b = U32(b + 0x14)) if (b == (uint32_t)g_blk[0]) return 1;
    return 0;
}

static int link(uint32_t h, uint32_t t) {          /* our blocks at the head of his chain, copied from its shoo */
    if (linked(h)) return 1;
    uint32_t head = U32(h + OBJ_ANIM_CHAIN), b = head;
    for (int i = 0; i < 40 && valid_ptr(b) && U32(b + 0x1C) != TAG_SHOO; i++) b = U32(b + 0x14);
    if (!valid_ptr(b) || U32(b + 0x1C) != TAG_SHOO) return 0;
    for (int i = 0; i < MOVES; i++)
        if (!anim_clone(b, g_blk[i], U32(MV(t, i)), U32(MV(t, i) + 4), (const float *)U32(MV(t, i) + 28),
                        (const uint8_t *)(t + 8))) return 0;
    for (int i = 0; i < MOVES; i++) g_blk[i][0x14 / 4] = i + 1 < MOVES ? (uint32_t)g_blk[i + 1] : head;
    U32(h + OBJ_ANIM_CHAIN) = (uint32_t)g_blk[0];
    return 1;
}

/* The arms with the saber out, standing and moving: the saber held with both hands in front of his belt, blade forward and 45 deg up, centred
 * on his body (the left fist on the hilt behind the right), the body leaned forward on the spine. Copies of his
 * movement blocks (the image's SAR2: per block its tag, keys and 21 tracks, right shoulder, forearm, hand, then left
 * shoulder, forearm, hand, then the spine; harness/luke/saber_moves.py, both arms solved per key for that hold on the
 * leaned spine) with every track kept but those seven bones' rotation tracks (found by node: mosy's entry order is
 * not trot's), pointed at ours. Linked after the swings,
 * before the game's own blocks: the game's own requests find them first by tag and play them (its legs, its body,
 * its blends); unlinked, its own again. A block whose keys differ from the table's is not copied. Sstn is copied
 * too (the hold standing), not flyy (hang.c copies it by tag); shoo is copied after the swings took theirs from the
 * game's (the game plays it frozen on frame 1 and turns his chest itself: the hold, under the chest, turns with it).
 * Set from saber_setanim, at set_anim's entry (and standing, from hold_stand, below): set_anim plays a request only when its id is
 * not the controller's current descriptor's, so at a switch the controller is pointed at a descriptor no id matches
 * and this same request is played again through the game's play, blended into the block its tag now finds (the
 * saber put away mid-run kept our trot for 4 s otherwise, until the run's next new request). */
#define SARM_MAGIC      0x53415232u /* 'SAR2' */
#define ARM_MAX         9
static uint32_t g_mv[ARM_MAX][BLOCK_SIZE / 4];
static int g_mvn;

static const uint32_t g_redo[9] = { 0xFFFFFFFEu };  /* a descriptor no request matches, +0x14 0, kind 0 */
static int ours(void);

/* SAR2's tracks: right arm, left arm, then the spine (the lean; the game turns the chest again, not the spine) */
static const uint8_t SARM_BONES[7] = { 8, 7, 6, 5, 4, 3, 10 };

static int arms(uint32_t h, int on, uint32_t ctl) {   /* 1: the copies linked or unlinked now */
    uint32_t at = sabr(), t = at ? U32(at + 20) : 0, tail = (uint32_t)g_blk[MOVES - 1], nx = U32(tail + 0x14);
    if (!valid_ptr(t) || U32(t) != SARM_MAGIC || U32(t + 4) > ARM_MAX || !linked(h)) return 0;
    int in = g_mvn && nx == (uint32_t)g_mv[0];
    if (on == in) return 0;
    if (!ours()) U32(ctl + 4) = (uint32_t)g_redo;   /* this request is played again: the block now found by its tag */
    if (!on) { U32(tail + 0x14) = g_mv[g_mvn - 1][0x14 / 4]; return 1; }
    int n = 0;
    for (uint32_t i = 0; i < U32(t + 4); i++) {
        uint32_t r = t + 8 + 12 * i, tag = U32(r), keys = U32(r + 4), b = nx, e = (uint32_t)g_mv[n] + 0x38;
        for (int j = 0; j < 40 && valid_ptr(b) && U32(b + 0x1C) != tag; j++) b = U32(b + 0x14);
        if (!valid_ptr(b) || U32(b + 0x1C) != tag || U32(b + 0x30) != keys || !anim_clone(b, g_mv[n], tag, keys, 0, 0)) continue;
        for (int k = 0; k < 19; k++, e += 0xA0)
            for (int a = 0; a < 7; a++)             /* right shoulder, forearm, hand, left ones, spine: trot bones */
                if (U32(e + 8) == U32((uint32_t)g_blk[0] + 0x38 + 0xA0 * SARM_BONES[a] + 8)) {
                    *(volatile uint8_t *)(e + 0x29) |= 1;     /* its rotations from tracks */
                    for (int c = 0; c < 3; c++) U32(e + 0x70 + 4 * c) = U32(r + 8) + 4 * keys * (3 * a + c);
                }
        n++;
    }
    for (int i = 0; i < n; i++) g_mv[i][0x14 / 4] = i + 1 < n ? (uint32_t)g_mv[i + 1] : nx;
    if ((g_mvn = n)) U32(tail + 0x14) = (uint32_t)g_mv[0];
    return n > 0;
}

/* The hold from the draw on, standing too: standing still the game makes no set_anim call (its stand plays on), so
 * the copies, linked from set_anim's entry, would wait for his first move. With the saber out and lit, no swing
 * playing, him on the ground and his controller on the stand's request (descriptor id 0): the copies linked here,
 * then the game's own stand request asked again (as hang.c does at a hang's end), played from our Sstn. */
typedef int (*set_anim_fn)(int32_t id, int32_t flags, uint32_t ctrl, uint32_t state);
static void hold_stand(uint32_t h) {
    uint32_t d = U32(CTL + 4), fl = U32(h + OBJ_FLAGS);
    int over = ours();                              /* a swing ended by itself: the controller still on ours */
    if (!(F32(h + HUMN_HEALTH) > 0)) return;        /* dead: the stand asked here would replace his death */
    if (M.cur >= 0 || !valid_ptr(d) || (U32(d) != ANIM_STAND && !over) || !(fl & FL_GROUND) || (fl & FL_AIR)) return;
    if (arms(h, 1, CTL) | over) ((set_anim_fn)SET_ANIM)(ANIM_STAND, 1, CTL, h + OBJ_ANIM_STATE);
}

static int ours(void) { uint32_t d = U32(CTL + 4); return d >= (uint32_t)g_desc && d < (uint32_t)g_desc + sizeof g_desc; }

/* The parry's overlay on the arms and the spine, from the Humn's draw (tramp_look_place, after guard_place): his
 * update has sampled the playing block (state +0x14) and left each bone instance's final angles at +0x10..+0x18 (z x
 * y, degrees, SAR2's track order); the seven arm-layer bones' angles are blended toward the parry's pose by its weight
 * and their nodes re-posed by the game's own 0x80016E28(instance, the block's factor +0x0C), before the draw reads
 * them. Only those seven nodes change: the legs and the run's cycle stay the block's. Two draws with no update
 * between (paused) find their angles still the written ones: the base kept from the first, so it never compounds.
 * minsize: at -O2 the 7 x 3 loop unrolls to 960 bytes, 632 so. */
GAME(sb_pose, 0x80016E28);   void sb_pose(uint32_t inst, uint32_t factor);
/* bolt: the bolt it is for; v: the grid's node nearest the crossing ((layer x NY + row) x NX + column); t: its time
 * (s); in: its time to the pose (0: none running); w: the weight now; from: started over another one (its first `in`
 * blends from g_pfrom, the angles last written); air: the time since he left the ground during it (< 0: on the
 * ground), wa: w then; fd: the crossing's distance ahead it was blended at (carried along his move) */
struct parry { uint32_t bolt; int v; float t, in, w; int from; float air, wa, fd; };
struct parry g_parry;                               /* the parry running (in > 0), exported for tests */
float g_parry_pose[21];                             /* its pose: per SARM_BONES bone its z x y angles */
static float g_pbase[21], g_pwrote[21], g_pfrom[21];
int g_saber_parry_v = -1;                           /* the nearest node of the parry running, -1 none (tests) */
float g_saber_parry_w;                              /* its weight (tests) */

__attribute__((minsize)) void saber_pose(uint32_t h) {
    float w = g_parry.w;
    uint32_t b = U32(h + OBJ_ANIM_STATE + 0x14), e = b + 0x38;
    if (h != g_player || !(w > 0) || !valid_ptr(b) || !linked(h)) return;
    /* a block the update has not sampled yet (the game's shoo frozen after the draw) holds each entry's translation
     * offset (+0x1C..+0x24) at (0, 0, -1000): 0x80016E28 would add it, his chest 1000 below; no write this frame */
    for (int k = 0; k < 19; k++)
        for (int a = 0; a < 7; a++)
            if (U32(e + 0xA0 * k + 8) == U32((uint32_t)g_blk[0] + 0x38 + 0xA0 * SARM_BONES[a] + 8)
                && F32(e + 0xA0 * k + 0x24) <= -999.0f) return;
    for (int k = 0; k < 19; k++, e += 0xA0)
        for (int a = 0; a < 7; a++)
            if (U32(e + 8) == U32((uint32_t)g_blk[0] + 0x38 + 0xA0 * SARM_BONES[a] + 8)) {
                for (int c = 0; c < 3; c++) {
                    int i = 3 * a + c;
                    float *ang = (float *)(e + 0x10) + c, base = *ang == g_pwrote[i] ? g_pbase[i] : *ang;
                    g_pbase[i] = base;
                    if (g_parry.from) base = g_pfrom[i];
                    *ang = g_pwrote[i] = base + wrap180(g_parry_pose[i] - base) * w;
                }
                sb_pose(e, U32(b + 0x0C));
            }
}

/* The parry's timing (D: the plan's register is folded here at its close): a bolt seen crossing the plane in front of
 * him within PARRY_LEAD s (saber_blst's look-ahead) snaps the blade into its path: the pose reached in the time left
 * before the crossing (at least PARRY_IN: a near shooter gives a fast flick, a far one a smooth move), held PARRY_HOLD,
 * then eased back to the block's own over PARRY_OUT (smoothstep each). Its pose: the image's PRY3 grid (after SAR2's
 * records; harness/luke/saber_moves.py PARRY_GRID_NEAR and PARRY_GRID: NX sides x NY heights on NZ planes ahead of him,
 * 1.5 and 2.25, his hit plane the far one; each node a pose whose blade passes through it), the eight nodes around the
 * crossing (its side, height and distance ahead, clamped to the grid) blended trilinearly, per angle the short way
 * from the first node, written once at the start. The distance ahead is where the bolt crosses the look-ahead's sweep
 * less his own move over the time to the pose (his velocity along his facing x that time): running at a bolt he is
 * ~0.8 a frame past the pose when the blade gets there, and one layer at 2.25 met such bolts 0.65..1.43 off the blade,
 * at the hilt. An older image (PRY2): no parries. None starts in the air (jmpF's landing keys put the blade through
 * his thighs); one running when he leaves the ground eases out over PARRY_IN. */
#define PARRY_MAGIC     0x50525933u /* 'PRY3' */
#define PARRY_IN        0.05f       /* s: the fastest move to the pose */
#define PARRY_LEAD      0.15f       /* s: the look-ahead, the slowest move to the pose */
#define PARRY_HOLD      0.10f
#define PARRY_OUT       0.25f
#define HOLD_MAX        0.1f        /* s past the pose's time a bolt may be held for it (saber_blst) */

static float ease(float x) { return x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x); }

__attribute__((noinline)) static uint32_t pry(void) {         /* the image's parry grid's header (NX, NY, NZ, SD0, SD_STEP, CZ0, CZ_STEP, FD0, FD_STEP), 0: none */
    uint32_t at = sabr(), t = at ? U32(at + 20) : 0;
    if (!valid_ptr(t) || U32(t) != SARM_MAGIC || U32(t + 4) > ARM_MAX) return 0;
    t += 8 + 12 * U32(t + 4);
    return U32(t) == PARRY_MAGIC ? t + 4 : 0;
}

static float clampf(float x, float hi) { return x < 0 ? 0 : x > hi ? hi : x; }

__attribute__((minsize)) static void parry_start(uint32_t b, float cz, float sd, float fd, float in) {
    struct parry *P = &g_parry;
    uint32_t t = pry();
    if (!t) return;
    int nx = U32(t), ny = U32(t + 4), nz = U32(t + 8);
    float fx = clampf((sd - F32(t + 12)) / F32(t + 16), nx - 1), fy = clampf((cz - F32(t + 20)) / F32(t + 24), ny - 1),
          fz = clampf((fd - F32(t + 28)) / F32(t + 32), nz - 1);
    int i = (int)fx, j = (int)fy, l = (int)fz;
    if (i > nx - 2) i = nx - 2;
    if (j > ny - 2) j = ny - 2;
    if (l > nz - 2) l = nz - 2;
    P->v = ((int)(fz + 0.5f) * ny + (int)(fy + 0.5f)) * nx + (int)(fx + 0.5f);   /* the nearest node */
    P->fd = fd;
    fx -= i; fy -= j; fz -= l;
    const float *a = (const float *)(t + 36) + 21 * ((l * ny + j) * nx + i);
    /* the seven other corners (right, up, far: bits 0, 1, 2) by their weights, each from the first node */
    for (int k = 0; k < 21; k++, a++) {
        float v = *a;
        for (int m = 1; m < 8; m++)
            v += (m & 1 ? fx : 1 - fx) * (m & 2 ? fy : 1 - fy) * (m & 4 ? fz : 1 - fz)
                 * wrap180(a[21 * ((m & 1) + (m & 2 ? nx : 0) + (m & 4 ? nx * ny : 0))] - *a);
        g_parry_pose[k] = v;
    }
    P->from = P->in > 0 && P->w > 0;                /* over another: from the angles it wrote last */
    for (int k = 0; k < 21; k++) g_pfrom[k] = g_pwrote[k];
    P->bolt = b; P->t = 0; P->in = in; P->air = -1;
}

__attribute__((minsize)) static void parry_frame(uint32_t h, int on, float dt) {
    struct parry *P = &g_parry;
    uint32_t t = pry();
    float w = 0;
    int run = on && t && P->in > 0;
    if (run) {
        float a = P->t += dt, in = P->in;
        if (P->air < 0 && (U32(h + OBJ_FLAGS) & FL_AIR)) { P->air = 0; P->wa = P->w; P->from = 0; }
        if (P->air >= 0) { w = P->wa * (1 - ease((P->air += dt) / PARRY_IN)); run = P->air < PARRY_IN; }
        else if (a < in) w = ease(a / in);
        else { P->from = 0; w = 1 - ease((a - in - PARRY_HOLD) / PARRY_OUT); run = a < in + PARRY_HOLD + PARRY_OUT; }
    }
    if (!run) { P->in = 0; P->bolt = 0; w = 0; }    /* over: a later bolt in the same pool slot starts its own */
    P->w = w;
    g_saber_parry_v = run ? P->v : -1; g_saber_parry_w = w;
}

/* A swing cut off or over: the game's requests taken again. Not inlined: its four callers cost 144 bytes more. */
__attribute__((noinline)) static void end_move(void) {
    if (M.cur >= 0 && ours()) F32(CTL) = CTL_FREE;
    M.cur = M.next = -1; g_saber_move = -1;
}

static int blocked(uint32_t h, uint32_t t, int i);

static void start(uint32_t h, uint32_t t, int i) {
    int k = i < SPIN && blocked(h, t, i) ? INPL + i : i;   /* a body in the step: the move's in-place block */
    uint32_t *d = g_desc[k];
    float len = mv_len(t, k), fps = F32(MV(t, k) + 8);
    d[0] = SWING_ID(k); d[1] = U32(MV(t, k)); F32(&d[2]) = 1.0f; F32(&d[3]) = BLEND; F32(&d[4]) = fps;
    F32(&d[5]) = len; F32(&d[6]) = len; d[7] = 0xFFFFFFFFu; d[8] = 7;
    sb_play(h + OBJ_ANIM_STATE, d[1], 5, 1.0f, BLEND, fps);
    U32(CTL + 4) = (uint32_t)d; F32(CTL) = 0;
    M.cur = i; M.blk = k; M.next = -1; M.t = 0; M.hit = 0; M.link = F32(MV(t, k) + 32); g_saber_move = i;
    g_parry.in = 0;                                 /* a swing: its whole-body block, no parry over it */
    play(i == SPIN ? S_SPIN : S_SW1 + i, VOL_SHOT, 0);
}

/* The world matrix (rows x, y, z, then the translation) of his right hand: his placement node, its child holding
 * the model bone, then the model, pelvis, spine, chest, shoulder, forearm and hand bones (trot 18 17 10 9 8 7 6). */
static const uint8_t ARM_PATH[] = { 18, 17, 10, 9, 8, 7, 6 };
static void node_mul(float *w, uint32_t n) {       /* w = node's local x w (row vectors) */
    float r[12];
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++)
            r[3 * i + j] = F32(n + 0x14 + 12 * i) * w[j] + F32(n + 0x18 + 12 * i) * w[3 + j] + F32(n + 0x1C + 12 * i) * w[6 + j];
    for (int j = 0; j < 3; j++)
        r[9 + j] = F32(n + 0x38) * w[j] + F32(n + 0x3C) * w[3 + j] + F32(n + 0x40) * w[6 + j] + w[9 + j];
    for (int i = 0; i < 12; i++) w[i] = r[i];
}
static int arm_nodes(uint32_t h, uint32_t *n) {   /* his placement node, its child holding the model bone, the bones */
    uint32_t p = U32(h + 0x24C), m = U32((uint32_t)g_blk[0] + 0x38 + 0xA0 * 18 + 8), x = 0;
    if (!valid_ptr(p) || !valid_ptr(m) || U32(p + 0x0C) > 8) return 0;
    for (uint32_t i = 0; i < U32(p + 0x0C) && !x; i++) {
        uint32_t c = U32(U32(p + 0x10) + 4 * i);
        if (!valid_ptr(c) || U32(c) >> 28 != 0xD || U32(c + 0x0C) > 8) continue;
        for (uint32_t j = 0; j < U32(c + 0x0C); j++) if (U32(U32(c + 0x10) + 4 * j) == m) x = c;
    }
    if (!x) return 0;
    n[0] = p; n[1] = x;
    for (int k = 0; k < (int)sizeof ARM_PATH; k++)
        if (!valid_ptr(n[2 + k] = U32((uint32_t)g_blk[0] + 0x38 + 0xA0 * ARM_PATH[k] + 8))) return 0;
    return 1;
}
static int hand_world(uint32_t h, float *w) {
    uint32_t n[2 + sizeof ARM_PATH];
    if (!arm_nodes(h, n)) return 0;
    for (int i = 0; i < 12; i++) w[i] = (i % 4 == 0 && i < 9) ? 1.0f : 0.0f;
    for (int k = 0; k < 2 + (int)sizeof ARM_PATH; k++) node_mul(w, n[k]);   /* each next node's local before the world so far */
    return 1;
}

static uint32_t cls(uint32_t tag) {
    uint32_t p = U32(CLASS_LIST), c;              /* the game's list of class records (Boss's lies below 0x80112B08) */
    for (int i = 0; valid_ptr(p) && i < 80 && (c = U32(p + 4 * i)); i++) if (U32(c) == tag) return c;
    return 0;
}

/* The health of the targets near the hit (Trops, bosses, Guri on 33), summed. */
static float cls_hp(uint32_t tag, uint32_t hp, const float *at, float r) {
    float sum = 0;
    uint32_t c = cls(tag);
    for (uint32_t i = 0, o; c && i < U32(c + CLASS_COUNT) && i < 64; i++) {
        o = U32(c + CLASS_HEAD) + i * U32(c + CLASS_SIZE);
        float dx = F32(o + OBJ_POS) - at[0], dy = F32(o + OBJ_POS + 4) - at[1];
        if (dx * dx + dy * dy < r * r && F32(o + hp) > 0) sum += F32(o + hp);
    }
    return sum;
}

static float near_hp(const float *at, float r) {
    float sum = cls_hp(TAG_TROP_, 0x7C, at, r) + cls_hp(TAG_BOSS, BOSS_HEALTH, at, r);
    uint32_t g = ((find_fn)FIND_CLASS)(TAG_GURI_, 0);
    if (g) sum += F32(g + GURI_HEALTH);
    return sum;
}

/* The Expl object just spawned (0x80064584 returns none): his (sender +0x88), of the kind, not updated yet (+0x60 2). */
static uint32_t expl_new(uint32_t h, int kind) {
    uint32_t x = cls(TAG_EXPL);
    for (uint32_t i = 0, o; x && i < U32(x + CLASS_COUNT) && i < 128; i++) {
        o = U32(x + CLASS_HEAD) + i * U32(x + CLASS_SIZE);
        if (U32(o + 0x88) == h && U16(o + 0x64) == kind && U16(o + 0x60) == 2) return o;
    }
    return 0;
}

static void hit(uint32_t h, uint32_t t) {
    uint32_t e = MV(t, M.blk), o;
    float w[12], *at = M.at, vel[3] = { 0, 0, 0 }, reach = F32(e + 16);
    if (M.cur == SPIN || !hand_world(h, w)) {
        at[0] = F32(h + OBJ_POS); at[1] = F32(h + OBJ_POS + 4); at[2] = F32(h + OBJ_POS + 8) + 3.0f;
    } else {
        const float *mid = (const float *)(t + 28);
        for (int j = 0; j < 3; j++) at[j] = mid[0] * w[j] + mid[1] * w[3 + j] + mid[2] * w[6 + j] + w[9 + j];
    }
    for (int j = 0; j < 3; j++) g_saber_hit[j] = at[j];
    g_saber_hit[3] = reach;
    M.hp = near_hp(at, reach + 6.0f); M.watch = HIT_WAIT;
    g_saber_cuts++;
    sb_spawn(SHOT_KIND, at, 0, vel, SHOT_MSG, U32(h + OBJ_COLLIDER), h);
    if ((o = expl_new(h, SHOT_KIND))) {
        U16(o + 0x62) = SHOT_FLAGS; F32(o + 0xD4) = reach / 2.5f; F32(o + 0x84) = F32(e + 20); F32(o + 0x8C) = SHOT_LIFE_S;
        for (int j = 0; j < 3; j++) F32(o + OBJ_POS + 4 * j) = at[j];
        g_shot = o;
    }
    M.hit = 1;
}

/* ---- deflection ---- */
#define CLASS_BLST      0x80112E38  /* Blst's class record */
#define CLASS_UPDATE    0x1C        /* class record: update method */
#define BOLT_FLAGS      0x60        /* live 0x10000, first update 0x20000 */
#define BOLT_OWNER      0x64
#define BOLT_LEN        0x70
#define BOLT_SPEED      0x74
#define BOLT_VEL        0x78
#define BOLT_HEAD       0x84
#define HUMN_RADIUS     0x60        /* his hit plane's distance in front of him (2.25) */
#define HUMN_WIDE       0x64        /* its half-width (2.5) */
#define HUMN_ZLO        0x68        /* its height span above his feet (0 .. 6) */
#define HUMN_ZHI        0x6C
#define DEFLECT_COS     0.5f        /* +-60 deg */
#define OBJ_RADIUS      0x60        /* a Trop's, a boss's, Guri's: the area test's radius (Guri's negated by melee.c) */

/* A body in the step's way at a combo swing's start: a live object of the class (health at +hp > 0) whose place lies
 * a along his facing and l across it with 0 < a < step + r and |l| < r, r = his HUMN_RADIUS + its |radius|. The game
 * holds him there as it holds a run, so the stepping block's planted foot slid back (sw3 by a near guard stepped 0.0).
 * Walls are not tested. */
__attribute__((minsize)) static int body_in(uint32_t h, uint32_t o, uint32_t hp, float step) {
    float dx = F32(o + OBJ_POS) - F32(h + OBJ_POS), dy = F32(o + OBJ_POS + 4) - F32(h + OBJ_POS + 4);
    float fx = F32(h + OBJ_MATRIX + 0x10), fy = F32(h + OBJ_MATRIX + 0x14);
    float a = dx * fx + dy * fy, l = dx * fy - dy * fx, r = F32(h + HUMN_RADIUS) + absf(F32(o + OBJ_RADIUS));
    return F32(o + hp) > 0 && a > 0 && a < step + r && l * l < r * r;
}

__attribute__((minsize)) static int blocked(uint32_t h, uint32_t t, int i) {
    static const uint32_t tag[2] = { TAG_TROP_, TAG_BOSS }, hp[2] = { 0x7C, BOSS_HEALTH };
    float step = F32(MV(t, i) + 24);
    for (int k = 0; k < 2; k++) {
        uint32_t c = cls(tag[k]);
        for (uint32_t n = 0; c && n < U32(c + CLASS_COUNT) && n < 64; n++)
            if (body_in(h, U32(c + CLASS_HEAD) + n * U32(c + CLASS_SIZE), hp[k], step)) return 1;
    }
    uint32_t g = ((find_fn)FIND_CLASS)(TAG_GURI_, 0);
    return g && body_in(h, g, GURI_HEALTH, step);
}
typedef void (*upd_fn)(uint32_t, uint32_t, uint32_t, uint32_t);
static uint32_t g_blst_game;        /* the game's Blst update */
static uint32_t g_blst_h;           /* the Humn deflecting this frame (0: none) */
int g_saber_deflects;               /* bolts turned (tests) */
float g_saber_flash[3];             /* the last flash's place (tests) */
int g_saber_flashes;                /* flash objects made (tests) */
static uint32_t g_held;             /* the bolt held at the crossing for its parry (0: none) */
static float g_held_c[3];           /* where */
int g_saber_holds;                  /* bolts held (tests) */
float g_saber_hold_t;               /* the last hold's time (s, tests) */
static uint32_t g_turned;           /* the last bolt turned, while it grows out of the blade (0: none) */
static float g_turn_c[3];           /* its head at the turn: the contact */

static int blst_turn(uint32_t b, uint32_t h) {
    float hd[3], d[3], L = F32(b + BOLT_LEN), sp = F32(b + BOLT_SPEED);
    uint32_t o = U32(b + BOLT_OWNER);
    for (int j = 0; j < 3; j++) hd[j] = F32(b + OBJ_POS + 4 * j) + F32(b + BOLT_HEAD + 4 * j);
    if (valid_ptr(o) && o != h) { d[0] = F32(o + OBJ_POS) - hd[0]; d[1] = F32(o + OBJ_POS + 4) - hd[1]; d[2] = 0; }
    else for (int j = 0; j < 3; j++) d[j] = -F32(b + BOLT_DIR + 4 * j);
    float n = sqrt_f(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
    if (!(n > 1e-4f)) return 0;
    for (int j = 0; j < 3; j++) d[j] /= n;
    float rn = sqrt_f(d[0] * d[0] + d[1] * d[1]), r[3] = { rn > 1e-4f ? d[1] / rn : 1, rn > 1e-4f ? -d[0] / rn : 0, 0 };
    for (int j = 0; j < 3; j++) {
        F32(b + BOLT_DIR + 4 * j) = d[j]; F32(b + OBJ_MATRIX + 0x10 + 4 * j) = d[j]; F32(b + OBJ_MATRIX + 4 * j) = r[j];
        F32(b + OBJ_MATRIX + 0x20 + 4 * j) = j == 2; F32(b + BOLT_VEL + 4 * j) = sp * d[j];
        F32(b + BOLT_HEAD + 4 * j) = L * d[j]; F32(b + OBJ_POS + 4 * j) = hd[j] - L * d[j];
    }
    U32(b + BOLT_OWNER) = h;
    g_turned = b;
    for (int j = 0; j < 3; j++) g_turn_c[j] = hd[j];
    g_saber_deflects++;
    play(S_DEFLECT, VOL_SHOT, 0);
    return 1;
}

/* A turned bolt grows out of the blade: the turn leaves its tail (+0x50) a whole length (+0x70) behind the contact,
 * which drew it through the blade and him. Until its head (tail + +0x84, from which the game moves it and sweeps its
 * hit) is that length out, the tail stays at the contact c and the head offset spans to the head; then the offset is
 * the length again and the tail follows. */
__attribute__((minsize)) static void grow(uint32_t b) {
    float p[3], a = 0, L = F32(b + BOLT_LEN);
    for (int j = 0; j < 3; j++) {
        p[j] = F32(b + OBJ_POS + 4 * j) + F32(b + BOLT_HEAD + 4 * j);
        a += (p[j] - g_turn_c[j]) * F32(b + BOLT_DIR + 4 * j);
    }
    int out = a >= L;
    for (int j = 0; j < 3; j++) {
        float e = out ? L * F32(b + BOLT_DIR + 4 * j) : p[j] - g_turn_c[j];
        F32(b + BOLT_HEAD + 4 * j) = e; F32(b + OBJ_POS + 4 * j) = p[j] - e;
    }
    if (out) g_turned = 0;
}

/* A turned bolt's flash at c, where it crossed his plane. */
__attribute__((minsize)) static void flash(uint32_t h, float *c) {
    float vel[3] = { 0, 0, 0 };
    uint32_t o;
    for (int j = 0; j < 3; j++) g_saber_flash[j] = c[j];
    sb_spawn(FLASH_KIND, c, 0, vel, SHOT_MSG, U32(h + OBJ_COLLIDER), h);
    if (!(o = expl_new(h, FLASH_KIND))) return;
    U16(o + 0x62) = FLASH_FLAGS; F32(o + 0xD4) = FLASH_SCALE; F32(o + 0x80) = FLASH_GROW; F32(o + 0x84) = 0;
    F32(o + 0x8C) = FLASH_LIFE; U32(o + 0x124) = FLASH_RGBA;
    g_saber_flashes++;
}

/* The game's own plane test (0x80004770, from the bolt's hit 0x80026480) on the sweep from p along dir for len: a
 * plane across the sweep +0x60 in front of him, hit where the sweep crosses it less than +0x64 to his side, at a
 * height within +0x68 .. +0x6C (a test of the sweep's nearest point within +0x60 of him let bolts 2.25 .. 2.5 to his
 * side through). The crossing's place along the sweep (0..1; -1: none), *cz its height above his feet, *sd its side
 * (+ his right). */
__attribute__((minsize)) static float cross(uint32_t h, const float *p, const float *dir, float len, float *cz, float *sd) {
    float ex = dir[0] * len, ey = dir[1] * len, hx = F32(h + OBJ_POS) - p[0], hy = F32(h + OBJ_POS + 4) - p[1];
    float n = sqrt_f(ex * ex + ey * ey), w = F32(h + HUMN_WIDE);
    if (!(n > 1e-4f)) return -1;
    float a = (hx * ex + hy * ey) / n, l = (hx * ey - hy * ex) / n;   /* him along the sweep, to its side */
    float u = (a - F32(h + HUMN_RADIUS)) / n, fx = F32(h + OBJ_MATRIX + 0x10), fy = F32(h + OBJ_MATRIX + 0x14);
    *cz = p[2] + dir[2] * len * u - F32(h + OBJ_POS + 8);
    *sd = (ex * u - hx) * fy - (ey * u - hy) * fx;  /* (the crossing - his place) . his right (f.y, -f.x) */
    return u >= 0 && u <= 1 && l * l < w * w && *cz >= F32(h + HUMN_ZLO) && *cz <= F32(h + HUMN_ZHI) ? u : -1;
}

/* The hold: a bolt crossing his plane while its own parry is still on its way to the pose (on the ground, w < 1, at
 * most HOLD_MAX past the pose's time) is not turned yet: its head stands at the crossing and the game's update
 * (0x80033B7C: it only moves the bolt and tests its hit; the draw is elsewhere) is skipped until the blade is there. */
static int hold(uint32_t b) {
    struct parry *P = &g_parry;
    return P->bolt == b && P->in > 0 && P->air < 0 && P->w < 1 && P->t < P->in + HOLD_MAX;
}

static void saber_blst(uint32_t b, uint32_t a1, uint32_t a2, uint32_t a3) {
    uint32_t h = g_blst_h, fl = U32(b + BOLT_FLAGS);
    if (h && (M.cur < 0 || M.t >= M.link) && (fl & 0x10000) && U32(b + BOLT_OWNER) != h) {
        float p[3], dir[3], sp = F32(b + BOLT_SPEED), cz, sd;
        for (int j = 0; j < 3; j++) {
            dir[j] = F32(b + BOLT_DIR + 4 * j);
            p[j] = F32(b + OBJ_POS + 4 * j) + ((fl & 0x20000) ? 0 : F32(b + BOLT_HEAD + 4 * j));
        }
        float len = (fl & 0x20000) ? F32(b + BOLT_LEN) : sp * frame_dt(), c[3], *at = 0;
        if (b == g_held) {                          /* held: still waiting, or turned now at the crossing */
            g_saber_hold_t += frame_dt();
            if (hold(b)) return;
            g_held = 0; at = g_held_c;
        } else if (-(dir[0] * F32(h + OBJ_MATRIX + 0x10) + dir[1] * F32(h + OBJ_MATRIX + 0x14)) > DEFLECT_COS
                * sqrt_f(dir[0] * dir[0] + dir[1] * dir[1])) {
            /* the parry: the same test on the sweep lengthened by PARRY_LEAD of its flight (bolts fly straight at a
             * constant speed); a bolt turned this frame (a point-blank shooter) gets the fastest */
            float u0 = cross(h, p, dir, len, &cz, &sd);   /* the crossing's place along this frame's sweep */
            int turn = u0 >= 0;
            float L = len + sp * PARRY_LEAD, u = cross(h, p, dir, L, &cz, &sd);
            if (u >= 0 && b != g_parry.bolt && !(U32(h + OBJ_FLAGS) & FL_AIR) && sp > 0) {
                float in = turn ? PARRY_IN : (u * L - len) / sp, fd = 0;   /* this frame's part: now */
                in = in < PARRY_IN ? PARRY_IN : in > PARRY_LEAD ? PARRY_LEAD : in;
                /* the crossing's distance ahead of him, less his own move until the blade gets there */
                for (int j = 0; j < 2; j++)
                    fd += (p[j] + dir[j] * L * u - F32(h + OBJ_POS + 4 * j) - F32(h + OBJ_VEL + 4 * j) * in)
                          * F32(h + OBJ_MATRIX + 0x10 + 4 * j);
                parry_start(b, cz, sd, fd, in);
            }
            if (turn) {
                for (int j = 0; j < 3; j++) c[j] = p[j] + dir[j] * len * u0;
                if (hold(b)) {                      /* its head put at the crossing, the game's update skipped */
                    g_held = b; g_saber_holds++; g_saber_hold_t = 0;
                    for (int j = 0; j < 3; j++) { g_held_c[j] = c[j]; F32(b + OBJ_POS + 4 * j) = c[j] - F32(b + BOLT_HEAD + 4 * j); }
                    return;
                }
                at = c;
            }
        }
        if (at && blst_turn(b, h)) flash(h, at);
    }
    if (b == g_turned && U32(b + BOLT_OWNER) == g_blst_h) grow(b);
    ((upd_fn)g_blst_game)(b, a1, a2, a3);
}

static void blst_method(uint32_t h) {    /* saber_blst in the class record while the saber is out on Luke */
    if (!g_blst_game) g_blst_game = U32(CLASS_BLST + CLASS_UPDATE);
    uint32_t cur = U32(CLASS_BLST + CLASS_UPDATE);
    g_blst_h = h;
    if (!h) g_held = 0;
    if (cur == g_blst_game || cur == (uint32_t)saber_blst) U32(CLASS_BLST + CLASS_UPDATE) = h ? (uint32_t)saber_blst : g_blst_game;
}

void saber_setanim(uint32_t *a) {   /* inside his control: the arm's blocks, the press, the aim pose refused */
    uint32_t h = g_player;
    if (U32(h) != TAG_HUMN) return;
    int on = S16(h + HUMN_WEAPON) == SABER && luke();
    arms(h, on && !saber_dark(), a[2]);
    if (!on) return;
    if (U32(h + OBJ_FLAGS) & 0x1000) g_press = 1;
    if (a[0] == ANIM_AIM) a[0] = ANIM_STAND;
    /* past the link a moving request (kind >= 2) ends the return, so the game takes it with its own blend; the
     * stands (kind 0 / 1: the stand, Z held, the aim pose asked as the stand) let the return play out */
    /* the run with B held (trtg) holds Dash's pistol arms: the blade through his torso, out of his back; the run */
    if (a[0] == ANIM_RUNFIRE || a[0] == ANIM_RUNFIRE + 1) a[0] += ANIM_TROT - ANIM_RUNFIRE;
    if (M.cur >= 0 && M.t >= M.link && a[0] < 28 && U32(DASH_DESCS + 0x24 * a[0] + 0x20) >= 2) end_move();
}

/* From core.c's ctl_decode, every update of his control (standing with no input the game makes no set_anim call):
 * the step (or standing still), his velocity, before the control moves him. Returns the move + 1 before its link (core.c
 * then zeroes the stick's move and limits his turn), 0 otherwise. */
int saber_step(uint32_t h) {
    if (M.cur >= 0 && h == g_player) {
        F32(h + OBJ_VEL) = F32(h + OBJ_MATRIX + 0x10) * g_step_v; F32(h + OBJ_VEL + 4) = F32(h + OBJ_MATRIX + 0x14) * g_step_v;
        if (M.t < M.link) return M.cur + 1;
    }
    return 0;
}

static void swing(uint32_t h, int out, float dt) {
    uint32_t t = swng();
    if (!t || !out || !luke() || !(F32(h + HUMN_HEALTH) > 0) || g_hang_state || (U32(h + OBJ_FLAGS) & FL_SWIM)
        || (M.cur >= 0 && !ours())) {
        /* killed mid-swing: the controller on our descriptor refused the damage's death request; asked again */
        int die = M.cur >= 0 && ours() && !(F32(h + HUMN_HEALTH) > 0);
        end_move(); g_press = 0; M.hold = -1;
        if (die) ((set_anim_fn)SET_ANIM)(ANIM_DIE, 1, CTL, h + OBJ_ANIM_STATE);
        return;
    }
    if (!(dt > 0)) return;
    if (g_shot && U16(g_shot + 0x60) != 2) {        /* its first update has sent it: spent, it sends no more */
        F32(g_shot + 0x84) = 0; F32(g_shot + 0x8C) = 0.001f; g_shot = 0;
    }
    if (!link(h, t)) { g_press = 0; return; }
    if (g_press) {
        g_press = 0; M.hold = 0;
        if (M.cur < 0) start(h, t, 0);
        else if (M.t >= F32(MV(t, M.blk) + 12)) M.next = M.cur < 2 && M.t < M.link + CHAIN_LATE ? M.cur + 1 : 0;
    }
    if (M.hold >= 0) {
        if (!(U32(h + OBJ_FLAGS) & 0x800)) M.hold = -1;
        else if ((M.hold += dt) >= SPIN_HOLD) { M.hold = -1; if (M.cur != SPIN) start(h, t, SPIN); }
    }
    if (M.watch > 0) {
        if (near_hp(M.at, F32(MV(t, 0) + 16) + 6.0f) < M.hp - 0.01f) {
#if SABER_SND_ROM
            sb_sfx_at(SND_ID0 + S_HIT, SND_PRIO, snd_pitch[S_HIT], VOL_HIT, M.at, 0);
#endif
            M.watch = 0;
        }
        else M.watch -= dt;
    }
    if (M.cur < 0) return;
    float len = mv_len(t, M.blk), from = F32(MV(t, M.blk) + 36), to = F32(MV(t, M.blk) + 40), v = 0;
    if (M.t >= from && M.t < to) v = STEP_GAIN * F32(MV(t, M.blk) + 24) / (to - from);   /* in place: step 0 */
    g_step_v = v;
    M.t += dt;
    if (!M.hit && M.t >= F32(MV(t, M.blk) + 12)) hit(h, t);
    if (M.next >= 0 && M.next != M.cur && M.t >= M.link) start(h, t, M.next);
    else if (M.t >= len) {
        int n = M.next;
        end_move();                 /* the game's requests taken again: hold_stand asks the stand */
        if (n >= 0) start(h, t, n);
    }
}

/* The blade's light (the image's second SABR mesh: the translucent shells, then the white core). A translucent part
 * (texture type 2, G_RM_XLU_SURF) blends over what the frame holds when it is drawn and writes no depth; in the
 * hand it was drawn with him, before the level's rooms (the world root's children 6..10 come after his, 5), so the
 * walls and his later bones covered it and only the core under it showed: the shells over white. The game draws its
 * own translucent mesh, his shadow (a type-2 quad), late the same way: under the root's child 11, after the rooms.
 * The blade's light goes after them too: a chain of nodes of ours as the root's last child (a list of ours: the
 * root's own children, then ours), one per node from his placement to his hand (arm_nodes), each of the game node's
 * kind and matrix slot (+0x44) with its remake bits (1, 2) clear: the draw makes no matrix for ours and multiplies
 * the slots the game's own nodes filled earlier in the same frame (the RSP reads them after the whole list is built),
 * so the light sits on the hand exactly, with no frame of lag; the mesh hangs under the last. Only while the hilt
 * is in the hand's list (hang.c's hide_weapon takes it out); the root's list back otherwise. */
#define WORLD_ROOT      0x8013CE24  /* -> the level's world root group (count +0xC, list +0x10) */
#define ARM_N           (2 + (int)sizeof ARM_PATH)
static uint32_t g_chain[ARM_N][0x48 / 4], g_link[ARM_N], g_rlist[20], g_root, g_rgame[2];
static void late(uint32_t h, int out) {
    uint32_t at = sabr(), r = U32(WORLD_ROOT), n[ARM_N], on = 0;
    if (g_root && g_root != r) g_root = 0;          /* a new level: the old root is gone */
    if (out && luke() && at && U32(at + 4) >= 2 && valid_ptr(r) && U32(r + 0x0C) < 19 && arm_nodes(h, n))
        for (uint32_t i = 0; i < U32(n[ARM_N - 1] + 0x0C) && i < 9; i++)
            on |= U32(U32(n[ARM_N - 1] + 0x10) + 4 * i) == U32(U32(at + 8));
    if (on) {
        for (int i = 0; i < ARM_N; i++) {
            uint32_t *c = g_chain[i];
            c[0] = (U32(n[i]) & 0xFFFF0000u) | 0xFF00; c[1] = 0xFFFFFFFFu; c[3] = 1; c[4] = (uint32_t)&g_link[i];
            c[0x44 / 4] = U32(n[i] + 0x44);
            g_link[i] = i < ARM_N - 1 ? (uint32_t)g_chain[i + 1] : U32(U32(at + 8) + 4);
        }
        if (U32(r + 0x10) != (uint32_t)g_rlist) {
            uint32_t k = U32(r + 0x0C);
            g_root = r; g_rgame[0] = k; g_rgame[1] = U32(r + 0x10);
            for (uint32_t i = 0; i < k; i++) g_rlist[i] = U32(g_rgame[1] + 4 * i);
            g_rlist[k] = (uint32_t)g_chain[0];
            U32(r + 0x10) = (uint32_t)g_rlist; U32(r + 0x0C) = k + 1;
        }
    } else if (g_root && U32(g_root + 0x10) == (uint32_t)g_rlist) {
        U32(g_root + 0x0C) = g_rgame[0]; U32(g_root + 0x10) = g_rgame[1]; g_root = 0;
    }
}

void saber_frame(void) {
    bank();
    uint32_t h = humn();
    if (!h) { g_h = 0; g_was = 0; g_root = 0; blst_method(0); return; }
    int id = S16(h + HUMN_WEAPON);
    if (id == SABER && !luke()) { sb_setw(h, LASER); id = LASER; }   /* the Look left Luke, or a level carried it */
    /* dark in Guri's hold and at his death: off (its sound, no hum, no light, no swings), then on again by itself */
    int out = id == SABER && !saber_dark() && F32(h + HUMN_HEALTH) > 0;
    double now = F64(GAME_CLOCK);
    if (h == g_h && out != g_was) play(out ? S_ON : S_OFF, VOL_SHOT, 0);
    g_h = h; g_was = out;
    icon(id == SABER);
    if (out && now != g_clock && F32(h + HUMN_HEALTH) > 0) play(S_HUM, VOL_HUM, 1);
    float dt = (float)(now - g_clock);
    int fresh = dt > 0.1f;
    if (fresh) dt = 0;                              /* a new level's clock */
    g_clock = now;
    swing(h, out, dt);
    parry_frame(h, out && luke() && F32(h + HUMN_HEALTH) > 0 && !g_hang_state && !fresh, dt);
    if (out && luke()) hold_stand(h);
    late(h, out);
    blst_method(out && luke() && F32(h + HUMN_HEALTH) > 0 ? h : 0);
}
