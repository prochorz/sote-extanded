/* Gall Run (gallrun.c): stage 2, the gunner on the rail: the gun's sight, the target panel, the gun's view back after
 * a restart, friendly fire on the Outrider. (The gunner's camera: gun_view(), gall_cam.c.) */
#include "common.h"
#include "gall.h"

int g_ff_next;                       /* or_friendly(): Dash's next line (0 LINE_FF_A, 1 LINE_FF_B), */
float g_ff_wait;                     /* and how long till he speaks again */
#define LINE_FF_B        4          /* Dash when the gunner hits the Outrider (or_friendly()): the game's own, Hoth's */
#define LINE_FF_A        5

/* A HUD element off screen while hide, put back where it was after; the place kept per element (37, 51). The target
 * panel (the base level's HUD element 37: "T.I.E. FIGHTER", its icons and bars, docs/reverse-engineering.md) is hidden
 * where there are no guns (stage 1 flown: the user, 2026-10-17; the end scene, whose held lines froze it on screen).
 * The game places it only as it changes (x not rewritten every frame, nor in a held line): from the frame and the
 * draw (trak_draw: no frame of it). */
#define HUD_TARGET       37
void hud_hide(int el, int hide) {
    static int16_t x[2] = { -1000, -1000 }, y[2];
    int k = el == HUD_TARGET ? 0 : 1;
    uint32_t a = HUD_POS + 4 * el;
    if (hide) { if (S16(a) != -1000) { x[k] = S16(a); y[k] = S16(a + 2); S16(a) = -1000; } }
    else if (x[k] != -1000) { S16(a) = x[k]; S16(a + 2) = y[k]; x[k] = -1000; }
}
void target_panel(int hide) { hud_hide(HUD_TARGET, hide); }

/* Friendly fire (the user, 2026-10-14): the gunner's bolts that pass within OR_HIT of the Outrider on the rail are
 * gone and Dash says the game's own lines (Hoth's pilots), in turn, not again for FF_QUIET; no damage (it has no
 * health of ours). Not once he has gone (his jump), in a shot or off the rail. */
#define OR_HIT           25.0f
#define FF_QUIET         4.0f
void or_friendly(void) {
    if (paused()) return;
    if (g_ff_wait > 0) g_ff_wait -= frame_dt();
    if (g_or_jump >= 0 || g_shot || !g_rail) return;
    uint32_t rec = blst();
    if (!rec) return;
    uint32_t chor = U32(CLASS_CHOR + 0x10), n = U32(rec + 8), sz = U32(rec + 0xC);
    for (uint32_t i = 0; i < n && i < 64; i++) {
        uint32_t b = U32(rec + 0x10) + i * sz;
        if (U32(b + 0x64) != chor || !bolt_hit(b, g_ocn, OR_HIT)) continue;
        static uint32_t last;
        if (g_ov_frames - last < SL_COOL) continue;
        last = g_ov_frames;
        if (g_ff_wait > 0) continue;
        (void)0;                                                 /* (no line: the user, 2026-10-19) */
        g_ff_next ^= 1; g_ff_wait = FF_QUIET;
    }
}

/* The gun's sight: three rings ahead of the ship (Chor's nodes at CHOR_SIGHT: the root's 13th to 15th, drawn
 * along the guns' aim). Hidden in the shots (ours, the end scene's: the user, a sight left hanging in the air). */
#define CHOR_SIGHT       0x14C
static uint32_t g_sight_decoy[3][0x48 / 4], g_sight_real[3];

void sight_hide(int hide) {                                      /* (Chor shows them again before the draw: it gets */
    if (!U32(CLASS_CHOR + 8)) return;                            /* decoys to pose while they are hidden) */
    uint32_t chor = U32(CLASS_CHOR + 0x10);
    for (int i = 0; i < 3; i++) {
        uint32_t *p = (uint32_t *)(chor + CHOR_SIGHT + 4 * i), n = *p, d = (uint32_t)g_sight_decoy[i];
        if (hide && n != d && valid_ptr(n) && U32(n) >> 28 == 0xD) {
            for (int k = 0; k < 0x48 / 4; k++) g_sight_decoy[i][k] = U32(n + 4 * k);
            g_sight_real[i] = n; *p = d;
        }
        if (n == d || *p == d) {
            if (hide) U16(g_sight_real[i] + NODE_SHOW) &= 0x00FF;
            else { *p = g_sight_real[i]; U16(g_sight_real[i] + NODE_SHOW) = U16(d + NODE_SHOW); }
        }
    }
}

void gun_back(void) {
    uint32_t ent = U32(CAMERA_ENTRIES);
    if (valid_ptr(ent)) U32(ent + CAMERA_GUN * 0x80) = 1;
}
