/* Gall Run (gallrun.c): the TIEs: the chase, the battle by the Star Destroyer, the bombers, the end's fight. */
#include "common.h"
#include "gall.h"

#define BATTLE_N         7          /* the last TIEs: the battle by the Star Destroyer (battle()): 3 X-Wings, 3 TIEs after them, one on its own */
#define BATTLE_EARLY     300.0f     /* (it starts a little under the space rocks' height) */
#define TIE_VEL          0x74       /* the unit heading its AI flies along (the drawn node's row 1) */
#define TIE_UP           0x80       /* its "up" (the node's row 2) */
#define TIE_NODE         0x94       /* its scene node (kind D: rows at NODE_ROWS, 3 floats each) */
#define NODE_ROWS        0x14
#define TIE_LEAD         60.0f      /* pursuit(): a TIE's nose on the Falcon's way this far ahead of it */
#define TIE_TURN_MAX     3.0f       /* tie_update(): the nose turns towards g_tie_aim at most this many rad/s (D18: it flew past
                                       * the aim every update and the nose flipped 1-3 rad a frame) */
#define TIE_PARKED       -4000.0f   /* unused TIEs wait far below (z -5000) */
#define TIE_PULL         2.5f       /* share of the way to its place in the chase a second, */
#define TIE_CATCH        200.0f     /* closing at most this much faster than the Falcon (0.2 a frame: in at once, then slow, the user) */
#define FREE_TIE_AHEAD   250.0f     /* free flight: the TIEs this far ahead of the Falcon, the next ones this */
#define FREE_TIE_R       100.0f     /* free flight: their ring round their point, turning FREE_TIE_W rad/frame-count */
#define FREE_TIE_W       0.15f
#define FREE_TIE_NEAR    150.0f     /* the point kept this near the Falcon at least, */
#define FREE_TIE_AWAY    300.0f     /* (2026-10-19: nearer, 150..300, were 400..700: dots far off, the user saw none) */     /* this far at most, */
#define FREE_TIE_DZ      150.0f     /* this much over or under it at most */
#define FREE_TIE_FAR     1500.0f    /* free flight: a TIE further than this from its place comes in again at once, */
#define FREE_TIE_IN      700.0f     /* this much further ahead */      /* much further */
#define TIE_BACK1        120.0f     /* before the switch this much further back: behind the stage 1 camera */
float g_tie_down[10];               /* pursuit(): seconds since a chase TIE hit the rock (-1: not) */
static float g_tie_hp[32];          /* tie_update(): each TieF's health after its last update (the game's relaunch: <= 0
                                       -> > 0; tie_back() writes ours); pursuit() stamps g_tie_hp_at (not called the frame
                                       before: no history, no relaunch seen) */
static uint32_t g_tie_hp_at;
static void tie_hp_keep(void) { g_tie_hp_at = g_ov_frames; }
float g_tie_clock;                  /* pursuit(): seconds of chase (the weave; held in the pause: they moved, the user) */
int g_kills, g_won, g_won_said, g_rogue;        /* the end's fight (finale()): TIEs down, the goal met, Lando's line said, the X-Wings' line said */
float g_xw_t;
int g_bomb_seen[2];                 /* 10 and 11 seen up (1), shot down for good (-1), */
float g_bomb_run[2][6];             /* their runs: start, aim, */
int g_bomb_fly;                     /* our bomb (object BOMB_OBJ) in flight: its bomber + 1 (0: none), */
float g_bomb_pos[3], g_bomb_way[3], g_bomb_t, g_bomb_age;          /* its place, way, seconds since a launch, its age */
float g_bomb_hp[2];                 /* 10's and 11's health at the end's fight's start (0: not yet) */
const float AX_UNIT[3][3] = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } };
#define TIES_LEAVE_T     2.5f       /* the end scene: the TIEs fly off this long, at TIES_LEAVE_V, then are put away */
#define TIES_LEAVE_V     420.0f
float g_leave_t;                    /* ties_away(): seconds of the fly-off, counted through held lines (the scene's first
                                     * line holds from its first frame: g_cine_t stays 0; gallrun.c resets it) */
#define LINE_LUKE        7          /* Luke's "We lost Han..." with his portrait (finale(): LUKE_NEAR of the battle) */
#define ZONE_TIES        700.0f     /* (pursuit(): the chase TIEs' point this near the battle's middle at most) */

/* No TIEs in stage 1 till TIES_IN nodes before the switch (they are why Dash leaves: he says so,
 * then breaks off); till then the ones in play wait far under the ground; then they come in from ahead and above, over the Falcon (pursuit() pulls them onto
 * its tail from there). */
#define TIE_HIDE         -3000.0f
#define TIE_HIDE_AWAY    40000.0f

#define TIE_IN_UP        250.0f
#define TIE_IN_NODES     14         /* (route nodes ahead: ~TIE_IN_AHEAD) */
void ties(void) {
    static int placed;
    uint32_t chor = U32(CLASS_CHOR + 0x10), n = U32(CLASS_TIEF + 8), tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    if (!g_ties_on) placed = 0;
    if (placed) return;
    for (uint32_t i = 0; i < n && i < 32; i++, tie += size) {
        if (F32(tie + TIE_POS + 8) < TIE_PARKED) continue;     /* not in play (the game's own park) */
        for (int j = 0; j < 3; j++) F32(tie + TIE_POS + 4 * j) = F32(chor + 0x50 + 4 * j);
        if (g_ties_on) {                                         /* on the route ahead (straight ahead the canyon turns: */
            float q[3];                                          /* they came out of the rock, the user, 2026-10-19) */
            route_pos((uint32_t)g_fly_p + TIE_IN_NODES + i, q);
            for (int j = 0; j < 3; j++) F32(tie + TIE_POS + 4 * j) = q[j];
            F32(tie + TIE_POS + 8) += TIE_IN_UP + i * 15;
        } else {                                                 /* far below and away: out of their guns' */
            F32(tie + TIE_POS) += TIE_HIDE_AWAY;                 /* reach (under the ship they shot it through */
            F32(tie + TIE_POS + 8) = TIE_HIDE;                   /* the ground) */
        }
    }
    placed = g_ties_on;
}

static float g_tie_anchor[3];
static int g_tie_anchor_on;
uint32_t g_chase[TIE_SLOTS];         /* the TIEs pursuit() keeps on the Falcon's tail (tie_update turns them) */
static float g_tie_aim[3];           /* where their noses point: the Falcon's way, TIE_LEAD ahead of it */

/* The end scene: every TIE in play flies off (TIES_LEAVE_T), then waits far off and under the ground (as ties() holds
 * them before they come in);
 * after it pursuit() pulls them back onto the Falcon's tail. */
static int hangar_launch(uint32_t tie, uint32_t slot);
static int chaser(uint32_t tie, uint32_t i, uint32_t n);
static int slots_now(void);
void ties_away(uint32_t chor) {
    if (paused()) return;                                        /* (they moved in the pause, the user) */
    uint32_t n = U32(CLASS_TIEF + 8), tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC), slot = 0;
    float dt = frame_dt_raw();                                   /* (also in a held line: frozen under the first one, */
    int gone = g_cine_t > TIES_LEAVE_T || g_leave_t > TIES_LEAVE_T;  /* two chasers hung by the Falcon; a write moves */
    g_leave_t += dt;                                             /* the drawn TIE a game frame later even then) */
    for (uint32_t i = 0; i < n && i < 32; i++, tie += size) {    /* once flown off, the chase TIEs in their hangars; */
        if (F32(tie + TIE_POS + 8) < TIE_PARKED) continue;       /* from Lando's line on pursuit()'s (D11) */
        if (g_cine_t > TIES_LEAVE_T && slot < slots_now() && chaser(tie, i, n)) {
            int own = g_hang_t >= 0 || hangar_launch(tie, slot);
            slot++;
            if (own) continue;
        }
        if (gone) {                                              /* gone: far off, under the ground */
            F32(tie + TIE_POS) = F32(chor + 0x50) + TIE_HIDE_AWAY;
            F32(tie + TIE_POS + 4) = F32(chor + 0x54);
            F32(tie + TIE_POS + 8) = TIE_HIDE;
            continue;
        }
        float d[3], l = 0;                                       /* first they fly off, away from the Falcon and */
        for (int j = 0; j < 3; j++) { d[j] = F32(tie + TIE_POS + 4 * j) - F32(chor + 0x50 + 4 * j); l += d[j] * d[j]; }
        l = sqrt_f(l); if (l < 1e-3f) l = 1;                     /* up (they vanished at once: a jump, the user) */
        for (int j = 0; j < 3; j++)
            F32(tie + TIE_POS + 4 * j) += (d[j] / l * TIES_LEAVE_V + (j == 2 ? TIES_LEAVE_V * 0.6f : 0)) * dt;
    }
}

/* No firing in stage 1 (the user: TIEs only shoot from stage 2): the TieF flag the game's fire routine (0x8009F268)
 * checks first, set on every TIE before the switch and cleared after (nothing else in the game reads it). */
#define TIE_HOLD_FIRE    0x8000
/* The level's own waves (the user: TIE bombers flew at the Falcon in stage 1; TIE fighters only, bombers by the
 * Star Destroyer): every TieF but the fighters (type 1, +0x70's low byte) and the battle's is a wave's, hidden
 * (tie_update) and holding fire always. */
static int tie_wave(uint32_t obj) { return (U32(obj + TIE_FLAGS) & 0xFF) != TIE_FIGHTER && battle_index(obj) < 0; }
/* The bombers (the user: only in the end's fight, at the Falcon; docs/reverse-engineering.md, TieF -> Bombers and
 * bombs): objects 10-13 (BOMBER_IDX), 14 the bomb's model (BOMB_OBJ). Before the end's fight every wave is held at the
 * park after the game's update and hidden after its draw, the bombers' launch timer held (they launched by it from the
 * end scene on, parked or not); in it 10 (BOMB_FLY; 11 parked as 12, 13) flies our runs and drop our bomb (bombers()). */
#define TIE_BOMB_T       0xB0       /* float: a bomber's launch timer (s) */
#define BOMB_HOLD_T      99.0f
static int tie_index(uint32_t obj) {
    uint32_t first = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    return size && obj >= first ? (int)((obj - first) / size) : -1;
}
#define BOMB_FLY         1          /* bombers flown: 10 only (11 parked as 12, 13: one bomber) */
static int bomber(uint32_t obj) { int i = tie_index(obj); return i >= 10 && i <= 13; }
int bomb_fly(uint32_t obj) {                                     /* flown by us: 10 up (BOMB_FLY), the bomb in flight */
    int i = tie_index(obj);
    if (i == BOMB_OBJ) return g_bomb_on && g_bomb_fly;
    return g_bomb_on && i >= 10 && i < 10 + BOMB_FLY && g_bomb_seen[i - 10] >= 0 && F32(obj + TIE_HEALTH) > 0;
}

/* Stage 2 on (the user: the TIEs far too fierce, no way through): only FIRE_N of the chase's fire at a time, the turn
 * passing on every FIRE_SWAP seconds, none in its last FIRE_REST; the battle's ships never (the X-Wings are TieFs:
 * they shot at the Falcon), nor any once the end's fight is won. */
#define FIRE_N           1
#define FIRE_SWAP        3.0f
#define FIRE_REST        1.0f
__attribute__((noinline)) void tie_hold(int hold) {
    static int turn, left;
    uint32_t n = U32(CLASS_TIEF + 8), tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    if (--left <= 0) { left = (int)(60 * FIRE_SWAP); if (++turn >= TIE_SLOTS) turn = 0; }
    for (uint32_t i = 0; i < n && i < 32; i++, tie += size) {
        int off = hold || g_won || tie_wave(tie) || battle_index(tie) >= 0 || left < (int)(60 * FIRE_REST);
        if (!off) {                     /* (a chaser whose turn it is: the next FIRE_N */
            off = 1;                                             /* filled slots from turn) */
            for (int k = 0, j = turn, got = 0; k < TIE_SLOTS && got < FIRE_N; k++, j = j + 1 >= TIE_SLOTS ? 0 : j + 1)
                if (g_chase[j]) { got++; if (g_chase[j] == tie) off = 0; }
        }
        U32(tie + TIE_FLAGS) = off ? U32(tie + TIE_FLAGS) | TIE_HOLD_FIRE : U32(tie + TIE_FLAGS) & ~TIE_HOLD_FIRE;
    }
}

/* Stage 2: a chase. Every TIE in play is pulled (TIE_PULL a second, TIE_CATCH faster than the Falcon at most) to its place behind and beside
 * the Falcon (BEHIND/SIDE/ABOVE by slot, TIE_SLOTS of them, with a slow weave), its nose on the Falcon's way
 * (tie_update; the AI's own heading had them fly sideways). The game's own AI still shoots and dies. Where rock is drawn
 * (the user: they passed through the walls) a slot's point and a TIE's place are pushed TIE_WALL out of it, and a TIE
 * that still meets a face (a sphere TIE_R) blows up, back behind TIE_BACK_T later (tie_back()). Held in the pause and on a held line. */
#define TIE_WEAVE        0.9f       /* rad a second (0.03 a frame at 30) */
#define TIE_WALL         24.0f      /* (12: 10 crashes in stage 2, 24: none) */
#define TIE_R            8.0f
#define TIE_BACK_T       3.0f
#define TIE_BACK_NODES   12         /* a chase fighter down in the canyon up again this many route nodes back (~600), */
#define TIE_BACK_UP      20.0f      /* this much over the route */
#define TIE_FAR          5000.0f    /* a chaser this far off the Falcon (hidden far off by ties_away()) is brought back
                                       there at once */
#define CINE_TIE_CLEAR   100.0f     /* in the end scene a chaser's point and its place kept this far off Chor's place
                                       in x, y (the Falcon's object, parked there: they rammed it and burst; the 3D
                                       clamp pushed the point under the pad, the rock put it back) */
/* p (x, y) at least CINE_TIE_CLEAR off Chor's place (chor + 0x50) in x, y, pushed out along the line from it (on it:
 * back along d); z kept. */
static void cine_clear(float *p, uint32_t chor, const float *d) {
    float e0 = p[0] - F32(chor + 0x50), e1 = p[1] - F32(chor + 0x54), f = sqrt_f(e0 * e0 + e1 * e1);
    if (f >= CINE_TIE_CLEAR) return;
    if (f < 1e-3f) { e0 = -d[0]; e1 = -d[1]; f = sqrt_f(e0 * e0 + e1 * e1); if (f < 1e-3f) { e0 = 1; f = 1; } }
    p[0] = F32(chor + 0x50) + e0 / f * CINE_TIE_CLEAR;
    p[1] = F32(chor + 0x54) + e1 / f * CINE_TIE_CLEAR;
}
/* The chase's start: chase TIE k (its slot: pursuit()'s order, chaser())
 * is launched from hangar record HANGAR_ONE (IMG_HANGARS: the mouths' middles, outward units) k x HANGAR_GAP after the
 * end scene's g_cine_t reaches HANG_CINE_T (gall_story.c cine() sets g_hang_t 0): in the end scene
 * till then hidden far off as ties_away() puts the gone ones (once it has flown them off; D7), then flown out from
 * HANGAR_IN inside the mouth along the outward unit at HANGAR_V for HANGAR_OUT, nose out of it, level, then the chase's own (pursuit(), from the line on also in the end
 * scene: ties_away() leaves them be). An image without the slot (count 0): no launch. */
#define HANGAR_GAP       0.8f
#define HANG_N           4          /* from the launch on (g_hang_t >= 0) only this many chase slots launch and chase
                                       (stage 2's chase before it keeps TIE_SLOTS) */
static int slots_now(void) { return g_hang_t >= 0 ? HANG_N : TIE_SLOTS; }
static uint32_t g_hang_held;        /* bit i: TieF i held hidden by hangar_launch() (not launched yet): its node hidden
                                       after the game's update and draw, as a wave's (the wingman update drew it at its
                                       leader's side in the mouth) */
static uint32_t g_hang_cap;         /* bit i: TieF i a live chaser past the first HANG_N slots, from hang_go() till
                                       ties_final(): kept as a held one, also placed away after the game's update (the
                                       formation update put them at their leader's side on the rail) */
static uint32_t g_hang_gone;        /* bit i: TieF i a chaser shot down from hang_go() on: in the parked
                                       set (g_hang_cap) for good, its slot kept (none other takes it), its health held at 0
                                       and the game's relaunch of it parked; till ties_final() */
#define TIE_LEADER       0xBC       /* the TieF's formation leader (a TieF, 0: none): the game's wingman update flies and
                                       draws it at the leader's side */
uint32_t g_hang_near;               /* bit slot: that slot's approach over (then its chase slot point, as before) */
static uint32_t g_hang_lead[32];    /* a launching chaser's leader link, kept aside (bit i of g_hang_led: kept) while */
static uint32_t g_hang_led;         /* 0 < s < HANGAR_OUT, put back when its launch ends or the run resets (D14) */
static void hang_lead_back(uint32_t tie, int ti) {
    if (ti < 0 || ti >= 32 || !(g_hang_led >> ti & 1)) return;
    U32(tie + TIE_LEADER) = g_hang_lead[ti];
    g_hang_led &= ~(1u << ti);
}
void hang_reset(void) {                                          /* (gallrun.c: a new run) every link kept put back */
    uint32_t n = U32(CLASS_TIEF + 8), tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    for (uint32_t i = 0; i < n && i < 32; i++, tie += size) hang_lead_back(tie, (int)i);
    g_hang_led = 0; g_hang_held = 0; g_hang_cap = 0; g_hang_near = 0; g_hang_gone = 0;
}
#define HANGAR_IN        40.0f
#define HANGAR_V         150.0f     /* (300, 1.5 s: most of the way to the Falcon flown out of view) */
#define HANGAR_OUT       1.0f
#define HANGAR_ONE       0          /* every chase TIE from this record: the one right of the eye's line while Dash is
                                       shown */
float g_hang_t = -1;                /* seconds since the launch (-1: not yet; pursuit() counts it) */
#define APPROACH_FRONT   80.0f      /* after its HANGAR_OUT a launched TIE flies to a point in the */
#define APPROACH_V       250.0f     /* frame: this far from the drawn Falcon toward the camera's eye, plus its slot's SIDE / */
#define APPROACH_NEAR    60.0f      /* ABOVE, at this speed, till this near that point or this many seconds; then its */
#define APPROACH_MAX     6.0f       /* chase slot */
float g_hang_ap[HANG_N][3];         /* (probes: hang_hit.py --count) each slot's approach point, last frame */
void hang_go(void) { uint32_t n = U32(GALL_RAM + IMG_HANGARS); if (n && n <= 8) { g_hang_t = 0; g_hang_near = 0; } }
static int chaser(uint32_t tie, uint32_t i, uint32_t n) {     /* one of pursuit()'s slots (its order) */
    return !((F32(tie + TIE_POS + 8) < TIE_PARKED && (!g_native || F32(tie + TIE_POS + 8) < g_fly_pos[2] - 1500))
             || !(F32(tie + TIE_HEALTH) > 0) || tie_wave(tie)    /* (native: the Falcon may be that low itself; */
             || (n >= BATTLE_N + TIE_SLOTS && i + BATTLE_N >= n));   /* the last ones: the battle's) */
}
static int hang_held(uint32_t obj) {                             /* (a new run: g_hang_t -1, g_cine 0: none) */
    int i = tie_index(obj);
    return (g_cine == 1 || g_hang_t >= 0) && i >= 0 && i < 32 && ((g_hang_held | g_hang_cap) >> i & 1);
}
static void hang_away(uint32_t tie) {                            /* far off, under the ground (as ties_away()'s gone) */
    uint32_t chor = U32(CLASS_CHOR + 0x10);
    if (!valid_ptr(chor)) return;
    F32(tie + TIE_POS) = F32(chor + 0x50) + TIE_HIDE_AWAY;
    F32(tie + TIE_POS + 4) = F32(chor + 0x54);
    F32(tie + TIE_POS + 8) = TIE_HIDE;
}
static int hangar_launch(uint32_t tie, uint32_t slot) {   /* parked or leaving its hangar: placed here */
    uint32_t n = U32(GALL_RAM + IMG_HANGARS), h = U32(GALL_RAM + IMG_HANGARS + 4);
    int ti = tie_index(tie);
    uint32_t bit = ti >= 0 && ti < 32 ? 1u << ti : 0;
    g_hang_held &= ~bit;
    if (!n || n > 8 || !valid_ptr(h) || (g_hang_t < 0 && g_cine != 1)) { hang_lead_back(tie, ti); return 0; }
    float s = g_hang_t < 0 ? -1 : g_hang_t - (float)slot * HANGAR_GAP;   /* seconds since its own launch */
    if (s >= HANGAR_OUT) {                                       /* launched: its leader link back once it takes its */
        if ((g_hang_near >> slot & 1) || s >= HANGAR_OUT + APPROACH_MAX) hang_lead_back(tie, ti);   /* chase slot (D14; */
        return 0;                                                /* 0 through the approach too) */
    }
    h += 20 * HANGAR_ONE;
    if (s > 0 && bit) {                                          /* launching: flown and drawn on its own place, not at */
        if (!(g_hang_led & bit)) { g_hang_lead[ti] = U32(tie + TIE_LEADER); g_hang_led |= bit; }   /* its leader's side */
        U32(tie + TIE_LEADER) = 0;                               /* (tie_update() too, before the game's) */
    }
    if (s <= 0) {                                                /* not launched yet: away as ties_away() puts the gone */
        g_hang_held |= bit;                                      /* ones (seen standing in the mouth) */
        hang_away(tie);
        return 1;
    }
    s = s * HANGAR_V - HANGAR_IN;
    F32(tie + TIE_POS) = F32(h) + F32(h + 12) * s;
    F32(tie + TIE_POS + 4) = F32(h + 4) + F32(h + 16) * s;
    F32(tie + TIE_POS + 8) = F32(h + 8);
    F32(tie + TIE_VEL) = F32(h + 12); F32(tie + TIE_VEL + 4) = F32(h + 16); F32(tie + TIE_VEL + 8) = 0;   /* nose out of */
    F32(tie + TIE_UP) = 0; F32(tie + TIE_UP + 4) = 0; F32(tie + TIE_UP + 8) = 1;   /* the mouth, level */
    return 1;
}
static float g_hang_fp[3];          /* pursuit(): the drawn Falcon's place last frame (g_hang_fp_on: kept), the approach */
static int g_hang_fp_on;            /* follows its motion */
static uint32_t g_tie_node;         /* pursuit()'s route node (tie_update()'s relaunch put-back, D17) */
static void tie_back_route(uint32_t tie, uint32_t i, uint32_t node) {   /* on the route TIE_BACK_NODES behind, over it */
    float q[3], z[3] = { 0, 0, 0 };
    route_pos(node > TIE_BACK_NODES ? node - TIE_BACK_NODES : 0, q);
    q[2] += TIE_BACK_UP + 15.0f * (float)(i & 3);
    tie_back(tie, i, q, z);
}
void pursuit(uint32_t node, float t) {
    g_tie_node = node;
    if (paused() || S16(MSG_HOLD)) { tie_hp_keep(); return; }
    g_tie_clock += frame_dt();
    if (g_hang_t >= 0) g_hang_t += frame_dt();
    static const float BEHIND[TIE_SLOTS] = { 12, 20, 28, 36, 44, 52 }, SIDE[TIE_SLOTS] = { -30, 32, -46, 44, -62, 58 },
                       ABOVE[TIE_SLOTS] = { 16, 24, 10, 30, 20, 36 };
    uint32_t chor = U32(CLASS_CHOR + 0x10), k = node + 1;
    float a[3], b[3], d[3], r[3], u[3], p[3];
    route_pos(k > 0 ? k - 1 : 0, a); route_pos(k + 2, b);
    for (int i = 0; i < 3; i++) d[i] = b[i] - a[i];
    if (g_free) {                                                /* free flight: the ship's own way */
        float cp = cos_r(g_fly_pitch);
        d[0] = cos_r(g_fly_yaw) * cp; d[1] = sin_r(g_fly_yaw) * cp; d[2] = -sin_r(g_fly_pitch);
    }
    float l = len3(d), lh;
    if (l < 1e-3f) return;
    for (int i = 0; i < 3; i++) d[i] /= l;
    lh = sqrt_f(d[0] * d[0] + d[1] * d[1]);
    if (lh < 1e-3f) return;
    r[0] = d[1] / lh; r[1] = -d[0] / lh; r[2] = 0;
    u[0] = r[1] * d[2] - r[2] * d[1]; u[1] = r[2] * d[0] - r[0] * d[2]; u[2] = r[0] * d[1] - r[1] * d[0];
    for (int i = 0; i < 3; i++) p[i] = g_native ? g_fly_pos[i] : F32(chor + 0x50 + 4 * i) + g_ship_off[i];
    if (!g_native) p[2] -= SHIP_DROP;
    float w = g_tie_clock * TIE_WEAVE, back = node < U32(GALL_RAM + IMG_SWITCH) ? TIE_BACK1 : 0;
    if (g_free) {                                                /* (the free flight's TIEs' point: first FREE_TIE_AHEAD */
        if (!g_tie_anchor_on)                                    /* ahead of the Falcon, then kept its way off it, between */
            for (int j = 0; j < 3; j++) g_tie_anchor[j] = p[j] + d[j] * FREE_TIE_AHEAD;   /* FREE_TIE_NEAR and FAR off: */
        if (g_sl_jump >= 0) {                                    /* (after Slave I: by the battle, ZONE_TIES of its */
            float m[3], q = 0;                                   /* middle at most: the fight there, the X-Wings in it;
                                                                  * first: the Falcon's NEAR wins, else they swarmed it) */
            for (int j = 0; j < 3; j++) { m[j] = g_tie_anchor[j] - F32(GALL_RAM + IMG_BATTLE + 4 * j); q += m[j] * m[j]; }
            q = sqrt_f(q);
            if (q > ZONE_TIES) for (int j = 0; j < 3; j++) g_tie_anchor[j] = F32(GALL_RAM + IMG_BATTLE + 4 * j) + m[j] / q * ZONE_TIES;
        }
        float v[3], l = 0;                                       /* the Falcon turns on to it; following its heading it */
        for (int j = 0; j < 3; j++) { v[j] = g_tie_anchor[j] - p[j]; l += v[j] * v[j]; }   /* ran away, the bot) */
        l = sqrt_f(l);
        float want = l < FREE_TIE_NEAR ? FREE_TIE_NEAR : l > FREE_TIE_AWAY ? FREE_TIE_AWAY : l;
        if (l > 1) for (int j = 0; j < 3; j++) g_tie_anchor[j] = p[j] + v[j] / l * want;
        if (g_tie_anchor[2] > p[2] + FREE_TIE_DZ) g_tie_anchor[2] = p[2] + FREE_TIE_DZ;   /* (near its height: else it */
        if (g_tie_anchor[2] < p[2] - FREE_TIE_DZ) g_tie_anchor[2] = p[2] - FREE_TIE_DZ;   /* dived after them for good) */
        g_tie_anchor_on = 1;
    } else g_tie_anchor_on = 0;
    uint32_t n = U32(CLASS_TIEF + 8), tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    uint32_t slot = 0;
    int rocky = !g_free && g_alt < CANYON_DROP;
    for (uint32_t i = 0, o = tie; i < 10 && i < n; i++, o += size)   /* down on the rock: back behind */
        if (g_tie_down[i] >= 0 && (g_tie_down[i] += frame_dt()) >= TIE_BACK_T) {
            g_tie_down[i] = -1;
            if (!(F32(o + TIE_HEALTH) > 0) && !(g_hang_gone >> i & 1)) {   /* (D1: not the ones down for good) */                    /* in the canyon: on the route TIE_BACK_NODES behind (the */
                if (!rocky) { tie_back(o, i, (float *)(chor + 0x50), d); continue; }   /* open way; straight back and */
                float q[3], z[3] = { 0, 0, 0 };                  /* aside it came out of the rock: the user, 2026-10-19) */
                route_pos(node > TIE_BACK_NODES ? node - TIE_BACK_NODES : 0, q);
                q[2] += TIE_BACK_UP + 15.0f * (float)(i & 3);
                tie_back(o, i, q, z);
            }
        }
    float fm[3] = { 0, 0, 0 };                                   /* the drawn Falcon's motion this frame (D5) */
    if (g_hang_t >= 0) {
        float fal[3];
        falcon_place(fal);
        for (int j = 0; j < 3; j++) { if (g_hang_fp_on) fm[j] = fal[j] - g_hang_fp[j]; g_hang_fp[j] = fal[j]; }
        g_hang_fp_on = 1;
    } else g_hang_fp_on = 0;
    int cap = g_hang_t >= 0 && !g_ties_cut;                      /* (D16: past HANG_N kept away till ties_final()) */
    g_hang_cap = cap ? g_hang_gone : 0;
    for (uint32_t i = 0; i < n && i < 32; i++, tie += size) {
        if (cap && (g_hang_gone >> i & 1)) {                     /* (D1: down for good, its slot kept) */
            if (slot < TIE_SLOTS) g_chase[slot] = 0;
            slot++;
            continue;
        }
        if (!chaser(tie, i, n)) { if (g_hang_t >= 0) hang_lead_back(tie, (int)i); continue; }   /* (shot down: its link back) */
        if (slot >= slots_now()) {
            if (cap) { g_hang_cap |= 1u << i; g_hang_held &= ~(1u << i); hang_away(tie); }
            continue;
        }
        if (hangar_launch(tie, slot)) { g_chase[slot++] = tie; continue; }   /* (in or leaving its hangar) */
        if (!g_free && valid_ptr(chor)) {                        /* far off (hidden by ties_away()): back on the route */
            float f = 0;                                         /* TIE_BACK_NODES behind, as a downed one (D12; the */
            for (int j = 0; j < 3; j++) { float e = F32(tie + TIE_POS + 4 * j) - p[j]; f += e * e; }   /* relaunch: tie_update()) */
            if (f >= TIE_FAR * TIE_FAR) tie_back_route(tie, i, node);
        }
        float ph = w + slot * 1.7f, side = SIDE[slot] + 8 * ship_sin(ph), up = ABOVE[slot] + 5 * ship_sin(ph * 1.3f);
        float step[3], dt = frame_dt(), sl = 0, cap = (FLY_V + TIE_CATCH) * dt, at = -(BEHIND[slot] + back);
        float ring[3] = { 0, 0, 0 }, tg[3], rw[3] = { TIE_WALL, TIE_WALL, TIE_WALL }, nn[3];
        if (g_free) {                                            /* free flight: round a point of their own ahead of the */
            float a = w * FREE_TIE_W + slot * (2 * PI_F / TIE_SLOTS), rr = FREE_TIE_R + 25 * ship_sin(ph);   /* Falcon */
            ring[0] = g_tie_anchor[0] + cos_r(a) * rr;           /* (that point follows slowly: the player can turn on */
            ring[1] = g_tie_anchor[1] + sin_r(a) * rr;           /* them; held at the Falcon's side they turned with it */
            ring[2] = g_tie_anchor[2] + 40 * ship_sin(a * 1.7f + ph);   /* and could not be aimed at, the bot) */
        }
        for (int j = 0; j < 3; j++) {
            tg[j] = g_free ? ring[j] : p[j] + d[j] * at + r[j] * side + u[j] * up;
        }
        int appr = 0;                                            /* the hangar's TIE: first to its point in the frame */
        uint32_t cam = U32(ACTIVE_CAMERA);                       /* then its slot */
        if (!g_free && g_hang_t >= 0 && slot < HANG_N && !(g_hang_near >> slot & 1) && valid_ptr(cam)) {
            float fal[3], e[3];
            falcon_place(fal);
            for (int j = 0; j < 3; j++) e[j] = F32(cam + 0x44 + 4 * j) - fal[j];   /* (the eye: +0x44) */
            float el = len3(e);
            if (el < 1e-3f) el = 1;
            for (int j = 0; j < 3; j++) tg[j] = fal[j] + e[j] / el * APPROACH_FRONT + r[j] * side + u[j] * up;
            appr = 1;
        }
        if (g_cine == 1 && valid_ptr(chor)) cine_clear(tg, chor, d);   /* the end scene: clear of Chor's place (D15) */
        if (rocky) collide(IMG_COLL, tg, AX_UNIT, rw, nn);      /* the slot's point out of the rock (as the eye) */
        if (appr) {                                              /* (D5) along with the Falcon, then closing on the point */
            for (int j = 0; j < 3; j++) F32(tie + TIE_POS + 4 * j) += fm[j];
            float q = 0;
            for (int j = 0; j < 3; j++) { float e = tg[j] - F32(tie + TIE_POS + 4 * j); q += e * e; g_hang_ap[slot][j] = tg[j]; }
            if (q < APPROACH_NEAR * APPROACH_NEAR || g_hang_t - (float)slot * HANGAR_GAP >= HANGAR_OUT + APPROACH_MAX)
                g_hang_near |= 1u << slot;                       /* (near: from the next frame its chase slot) */
            cap = APPROACH_V * dt;                               /* (straight at it at APPROACH_V) */
        }
        for (int j = 0; j < 3; j++) {
            step[j] = (tg[j] - F32(tie + TIE_POS + 4 * j)) * (appr ? 1 : minf(TIE_PULL * dt, 1));
            sl += step[j] * step[j];
        }
        sl = sqrt_f(sl);
        if (g_free && dt > 0 && sl > FREE_TIE_FAR * minf(TIE_PULL * dt, 1)) {   /* free flight: left far behind (the rail, the */
            for (int j = 0; j < 3; j++)                          /* story): in again ahead at once, further out */
                F32(tie + TIE_POS + 4 * j) += step[j] / minf(TIE_PULL * dt, 1) + d[j] * FREE_TIE_IN;
            sl = 0;
        }
        for (int j = 0; j < 3; j++) F32(tie + TIE_POS + 4 * j) += sl > cap ? step[j] * cap / sl : sl > 0 ? step[j] : 0;
        if (rocky) {                                             /* its place out of the rock too; still in a face: */
            float q[3] = { F32(tie + TIE_POS), F32(tie + TIE_POS + 4), F32(tie + TIE_POS + 8) }, rt[3] = { TIE_R, TIE_R, TIE_R };
            collide(IMG_COLL, q, AX_UNIT, rw, nn);               /* down (the game blows it up) */
            for (int j = 0; j < 3; j++) F32(tie + TIE_POS + 4 * j) = q[j];
            if (i < 10 && collide(IMG_COLL, q, AX_UNIT, rt, nn) > 0) { F32(tie + TIE_HEALTH) = 0; g_tie_down[i] = 0; }
        }
        if (g_cine == 1 && valid_ptr(chor)) cine_clear((float *)(tie + TIE_POS), chor, d);   /* its place too, last (D15) */
        g_chase[slot] = tie;
        slot++;
    }
    for (; slot < TIE_SLOTS; slot++) g_chase[slot] = 0;
    tie_hp_keep();
    for (int j = 0; j < 3; j++) g_tie_aim[j] = p[j] + d[j] * TIE_LEAD;
    (void)t;
}

/* The TIEs' update builds their drawn node from their heading (TIE_VEL, the node's row 1) and their "up"
 * (TIE_UP, row 2; the wings face row 0, to the right); dragged along by pursuit() the AI turned them every
 * way, so the chasers flew sideways. After it: nose turned from its heading towards g_tie_aim, at most
 * TIE_TURN_MAX rad/s (D18; the game's AI copies it to the drawn +0x30, wingmen take their leader's), level (wings
 * upright to either side). */

/* The battle by the Star Destroyer in space (the user, 2026-10-13: X-Wings and TIEs fight there as the chase comes by):
 * the last BATTLE_N TIEs of the level's (pursuit() leaves them be), as X-Wings (IMG_XWING) and TIEs (IMG_TIE: our own
 * models in their nodes), in pairs on ellipses by the Star Destroyer (IMG_BATTLE: between it and the rail; IMG_SD: its heading), each TIE
 * on its X-Wing's tail; from the height the space rocks come (battle_pose(): set in the frame and after the game's
 * update of them, tie_update()). */
#define IMG_XWING        188
#define IMG_TIE          200
#define BATTLE_R         140.0f     /* the first pair's ring (the rest wider by BATTLE_DR), as long as BATTLE_LONG x */
#define BATTLE_DR        80.0f      /* (300, 170: by the rail now, space.py BATTLE_SIDE, its rings clear of it) */
#define BATTLE_LONG      1.5f
#define BATTLE_W         0.45f      /* radians a second (less further out) */
#define BATTLE_DZ        0.6f       /* the rings' height spread (+-90 round the rail: 60 over the hull at their lowest) */
#define BATTLE_LAG       0.09f      /* a TIE this far behind its X-Wing on the ring */
#define XWING_K          0.8f       /* (~28 long: a TIE ~10, the Falcon ~36; true to size: the Falcon flies among them after) */
#define BATTLE_TIE_K     1.0f
static int g_bt_on;
static float g_bt_t;
static uint32_t g_bt_mesh[2][6], g_bt_list[2][1];

int battle_index(uint32_t obj) {                                /* -1: not one of the battle's */
    uint32_t n = U32(CLASS_TIEF + 8), first = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    if (n < BATTLE_N + TIE_SLOTS || obj < first || size == 0) return -1;
    uint32_t i = (obj - first) / size;
    return i + BATTLE_N >= n && i < n ? (int)(n - 1 - i) : -1;
}

/* A TieF at p, its nose along f, level, its node scaled k and shown (the game shows only the ones attacking). 0: no way. */
__attribute__((noinline)) static int obj_pose(uint32_t obj, const float *p, float *f, float k) {
    float fl = len3(f); if (fl < 1e-3f) return 0;
    for (int j = 0; j < 3; j++) f[j] /= fl;
    float hl = sqrt_f(f[0] * f[0] + f[1] * f[1]); if (hl < 1e-3f) return 0;
    float r[3] = { f[1] / hl, -f[0] / hl, 0 };
    float u[3] = { r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0] };
    uint32_t nd = U32(obj + TIE_NODE);
    for (int j = 0; j < 3; j++) {
        F32(obj + TIE_POS + 4 * j) = p[j];
        F32(obj + TIE_VEL + 4 * j) = f[j]; F32(obj + TIE_UP + 4 * j) = u[j];
        if (valid_ptr(nd)) {
            F32(nd + NODE_ROWS + 4 * j) = r[j] * k; F32(nd + NODE_ROWS + 12 + 4 * j) = f[j] * k;
            F32(nd + NODE_ROWS + 24 + 4 * j) = u[j] * k; F32(nd + NODE_POS + 4 * j) = p[j];
        }
    }
    if (valid_ptr(nd)) U16(nd + NODE_SHOW) = 0xFF03;
    return 1;
}

static void battle_pose(uint32_t obj, int b) {
    int xw = b < 3, pair = b < 6 ? b % 3 : 3;
    float R = BATTLE_R + BATTLE_DR * pair, w = BATTLE_W * (1 - 0.12f * pair) * (pair & 1 ? -1 : 1);
    float a = 2.1f * pair + w * g_bt_t - (xw ? 0 : BATTLE_LAG * (w > 0 ? 1 : -1));
    float h = F32(GALL_RAM + IMG_SD + 12), c = cos_r(h), sn = sin_r(h), ca = cos_r(a), sa = sin_r(a);
    float lx = R * BATTLE_LONG * ca, ly = R * sa, lz = BATTLE_DZ * (90.0f * (pair - 1) + 60 * sin_r(1.3f * a));
    float dx = -R * BATTLE_LONG * sa * w, dy = R * ca * w, dz = BATTLE_DZ * 78.0f * cos_r(1.3f * a) * w;   /* (d/dt) */
    float p[3] = { c * lx - sn * ly, sn * lx + c * ly, lz }, f[3] = { c * dx - sn * dy, sn * dx + c * dy, dz };
    for (int j = 0; j < 3; j++) p[j] += F32(GALL_RAM + IMG_BATTLE + 4 * j);
    if (!obj_pose(obj, p, f, xw ? XWING_K : BATTLE_TIE_K)) return;
    uint32_t nd = U32(obj + TIE_NODE);
    if (!(F32(obj + TIE_HEALTH) > 0)) F32(obj + TIE_HEALTH) = 1;
    if (valid_ptr(nd) && (xw || U32(GALL_RAM + IMG_TIE))) {     /* (a TIE keeps its own model when the image has none) */
        uint32_t *m = g_bt_mesh[xw ? 0 : 1], at = xw ? IMG_XWING : IMG_TIE;
        m[0] = MESH_W0; m[1] = 0; m[2] = 0;
        for (int j = 0; j < 3; j++) m[3 + j] = U32(GALL_RAM + at + 4 * j);
        g_bt_list[xw ? 0 : 1][0] = (uint32_t)m;
        U32(nd + NODE_COUNT) = 1; U32(nd + NODE_LIST) = (uint32_t)g_bt_list[xw ? 0 : 1];
        U16(nd + NODE_SHOW) = 0xFF03;
    } else if (valid_ptr(nd) && !xw) {                          /* (none: a fighter's node list, object 0's; the */
        uint32_t n0 = U32(U32(CLASS_TIEF + 0x10) + TIE_NODE);   /* battle's TIEs drew the bomb's model) */
        if (valid_ptr(n0)) { U32(nd + NODE_COUNT) = U32(n0 + NODE_COUNT); U32(nd + NODE_LIST) = U32(n0 + NODE_LIST); }
    }
}

void battle(void) {
    g_bt_on = g_cine == 2 && g_alt >= AST_SHOW - BATTLE_EARLY && U32(GALL_RAM + IMG_XWING);
    if (!g_bt_on) return;
    if (!paused() && !S16(MSG_HOLD)) g_bt_t += frame_dt();
    uint32_t n = U32(CLASS_TIEF + 8), first = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    if (n < BATTLE_N + TIE_SLOTS) return;
    for (int b = 0; b < BATTLE_N; b++) battle_pose(first + (n - 1 - b) * size, b);
}

/* The end's fight: chase TIEs down (the Falcon's or the X-Wings') counted; every XW_EVERY seconds an X-Wing shoots
 * down a chase TIE within XW_REACH of it (its health 0); Luke's line as the Falcon comes in (LUKE_NEAR of the
 * battle; LINE_LUKE, his portrait: take out the towers); all six towers down (towers_left()): Lando's line (not held: the fly-away goes on under it) and the fly-away,
 * the Falcon's jump (fly_jump()), then 1 from finale(): finish(). */
#define XW_EVERY         8.0f
#define XW_REACH         420.0f
#define LUKE_NEAR        1600.0f
#define REVIVE_T         3.0f       /* a fighter down this long comes in again (the level has 10: they ran out), */
#define REVIVE_HP        10.0f      /* this health (the level's), */
#define REVIVE_AWAY      1100.0f    /* this far from the battle's middle on the far side from the Falcon */
static void revive(float dt) {                                   /* (not in native flight) */
    static float down[10];
    uint32_t tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC), n = U32(CLASS_TIEF + 8);
    for (uint32_t i = 0; i < 10 && i < n; i++, tie += size) {
        if ((U32(tie + TIE_FLAGS) & 0xFF) != TIE_FIGHTER || battle_index(tie) >= 0 || F32(tie + TIE_HEALTH) > 0) { down[i] = 0; continue; }
        if ((down[i] += dt) < REVIVE_T) continue;
        down[i] = 0;
        float v[3], l = 0;
        for (int j = 0; j < 3; j++) { v[j] = F32(GALL_RAM + IMG_BATTLE + 4 * j) - g_fly_pos[j]; l += v[j] * v[j]; }
        l = sqrt_f(l); if (l < 1) l = 1;
        for (int j = 0; j < 3; j++) F32(tie + TIE_POS + 4 * j) = F32(GALL_RAM + IMG_BATTLE + 4 * j) + v[j] / l * REVIVE_AWAY + (j == 2 ? 60.0f * (float)(i & 3) : 40.0f * (float)i);
        F32(tie + TIE_HEALTH) = REVIVE_HP;
        uint32_t nd = U32(tie + TIE_NODE);
        if (valid_ptr(nd)) U16(nd + NODE_SHOW) = 0xFF03;
    }
}
/* Slave I shot down (the user, 2026-10-15): the chase starts again from the rail's start, in place (no level load): Chor
 * on its first node, Slave I RAIL_GAP ahead with its health, the story from the start (Dash back), the Falcon's health
 * full (the lives kept), the chase's fighters down up again RESTART_TIE_BACK behind it; the screen black, faded in. */
#define RESTART_TIE_BACK 600.0f
/* A chase fighter down up again RESTART_TIE_BACK behind a (d: the way, a unit), with REVIVE_HP, shown. */
void tie_back(uint32_t tie, uint32_t i, const float *a, const float *d) {   /* (d 0: at a itself) */
    int at = d[0] == 0 && d[1] == 0 && d[2] == 0;
    for (int j = 0; j < 3; j++) F32(tie + TIE_POS + 4 * j) = at ? a[j] : a[j] - d[j] * RESTART_TIE_BACK + (j == 2 ? 60.0f * (float)(i & 3) : 40.0f * (float)i);
    F32(tie + TIE_HEALTH) = REVIVE_HP;
    if (i < 32) g_tie_hp[i] = REVIVE_HP;                         /* (ours: not the game's relaunch, pursuit()) */
    uint32_t nd = U32(tie + TIE_NODE);
    if (valid_ptr(nd)) U16(nd + NODE_SHOW) = 0xFF03;
}

/* The end's fight's bombers (the user: our runs and our bomb): 10 (BOMB_FLY; was 10 and 11) flies runs at the Falcon from REVIVE_AWAY past
 * the battle's middle (BOMB_UP over, BOMB_SIDE either side), straight at BOMB_V to BOMB_PAST past where the Falcon was
 * at the run's start, then a new run. One bomb a run, the Falcon within BOMB_REACH ahead, BOMB_EVERY apart, none in
 * flight, none once won: BOMB_OBJ (the bomb's model, left parked for the game) from the bomber, "Incoming Bomb!",
 * turning towards the Falcon at BOMB_TURN, gone after BOMB_LIFE; within BOMB_HIT_R BOMB_DAMAGE off (kept by
 * hp_guard()) and the game's burst. Shot (free_lasers()): the burst only. A bomber shot down counts, not back. */
#define BOMB_UP          150.0f
#define BOMB_SIDE        200.0f
#define BOMB_V           160.0f
#define BOMB_PAST        500.0f
#define BOMB_REACH       800.0f
#define BOMB_EVERY       10.0f      /* (5: half as often) */
#define BOMB_SPEED       330.0f
#define BOMB_TURN        1.5f
#define BOMB_LIFE        10.0f
#define BOMB_HIT_R       25.0f
#define BOMB_DAMAGE      120
static float bomb_way(int k, float *f) {                         /* a run's unit way; its length */
    float l = 0;
    for (int j = 0; j < 3; j++) { f[j] = g_bomb_run[k][3 + j] - g_bomb_run[k][j]; l += f[j] * f[j]; }
    l = sqrt_f(l);
    if (l >= 1) for (int j = 0; j < 3; j++) f[j] /= l;
    return l;
}
static void bombers(void) {
    static float s[2]; static int fired[2];                      /* along the run; its bomb dropped */
    if (paused() || S16(MSG_HOLD)) return;
    uint32_t n = U32(CLASS_TIEF + 8), first = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    if (n <= BOMB_OBJ) return;
    float dt = frame_dt();
    g_bomb_t += dt;
    static int last;                                             /* the Falcon blown up (exploding, or the respawn's */
    uint32_t stft = player_ship();      /* frame): the game set the bombers' health -1; put */
    int hp = stft ? (int)U32(stft + STFT_HEALTH) : 0, st = stft ? (int)U32(stft + STFT_STATE) : 0;   /* back, they go on */
    int boom = st == 5 || st == 6 || hp > last + RESPAWN_HP;
    last = hp;
    for (int k = 0; k < BOMB_FLY; k++) {
        uint32_t b = first + (uint32_t)(10 + k) * size;
        if (g_bomb_seen[k] < 0) continue;
        if (g_bomb_hp[k] <= 0) g_bomb_hp[k] = F32(b + TIE_HEALTH);
        if (boom && !(F32(b + TIE_HEALTH) > 0)) F32(b + TIE_HEALTH) = g_bomb_hp[k];
        if (F32(b + TIE_HEALTH) > 0) g_bomb_seen[k] = 1;
        else { if (g_bomb_seen[k] > 0) { g_bomb_seen[k] = -1; g_kills++; } continue; }
        float f[3], l = bomb_way(k, f), *r = g_bomb_run[k];
        if (l < 1 || (s[k] += BOMB_V * dt) > l + BOMB_PAST) {   /* a new run */
            float v[3], vl = 0, h, sd = k ? -BOMB_SIDE : BOMB_SIDE;
            for (int j = 0; j < 3; j++) { v[j] = F32(GALL_RAM + IMG_BATTLE + 4 * j) - g_fly_pos[j]; vl += v[j] * v[j]; }
            vl = sqrt_f(vl); if (vl < 1) vl = 1;
            h = sqrt_f(v[0] * v[0] + v[1] * v[1]);
            float side[2] = { h < 1 ? 1 : -v[1] / h, h < 1 ? 0 : v[0] / h };
            for (int j = 0; j < 3; j++) {
                r[j] = F32(GALL_RAM + IMG_BATTLE + 4 * j) + v[j] / vl * REVIVE_AWAY + (j < 2 ? side[j] * sd : BOMB_UP);
                r[3 + j] = g_fly_pos[j] + (j == 2 ? BOMB_UP : 0);
            }
            s[k] = 0; fired[k] = 0;
            l = bomb_way(k, f);
        }
        float p[3], d[3], dl = 0, ah = 0;
        for (int j = 0; j < 3; j++) {
            F32(b + TIE_POS + 4 * j) = p[j] = r[j] + f[j] * s[k];   /* (tie_update() keeps it through the game's) */
            d[j] = g_fly_pos[j] - p[j]; dl += d[j] * d[j]; ah += d[j] * f[j];
        }
        if (!fired[k] && !g_bomb_fly && g_bomb_t >= BOMB_EVERY && !g_won && ah > 0 && dl < BOMB_REACH * BOMB_REACH) {
            fired[k] = 1; g_bomb_fly = k + 1; g_bomb_t = g_bomb_age = 0;
            for (int j = 0; j < 3; j++) { g_bomb_pos[j] = p[j]; g_bomb_way[j] = f[j]; }
            F32(BOMB_WARN) = 2.2f;                               /* (the game's "Incoming Bomb!") */
        }
    }
    if (!g_bomb_fly) return;
    uint32_t o = first + BOMB_OBJ * size;
    float t[3], tl = 0, c = 0, a = BOMB_TURN * dt;
    for (int j = 0; j < 3; j++) { t[j] = g_fly_pos[j] - g_bomb_pos[j]; tl += t[j] * t[j]; }
    tl = sqrt_f(tl);
    if (tl > 1e-3f) {                                            /* turned towards the Falcon, at most a */
        for (int j = 0; j < 3; j++) { t[j] /= tl; c += t[j] * g_bomb_way[j]; }
        if (c >= cos_r(a)) for (int j = 0; j < 3; j++) g_bomb_way[j] = t[j];
        else {
            float q[3], ql = 0;
            for (int j = 0; j < 3; j++) { q[j] = t[j] - c * g_bomb_way[j]; ql += q[j] * q[j]; }
            ql = sqrt_f(ql);
            if (ql > 1e-3f) for (int j = 0; j < 3; j++) g_bomb_way[j] = g_bomb_way[j] * cos_r(a) + q[j] / ql * sin_r(a);
        }
    }
    float e = 0;
    for (int j = 0; j < 3; j++) {
        F32(o + TIE_POS + 4 * j) = g_bomb_pos[j] += g_bomb_way[j] * BOMB_SPEED * dt;
        float w = g_fly_pos[j] - g_bomb_pos[j]; e += w * w;
    }
    g_bomb_age += dt;
    if (e < BOMB_HIT_R * BOMB_HIT_R) {                           /* a hit */
        if (stft) {
            hp = (int)U32(stft + STFT_HEALTH) - BOMB_DAMAGE;
            U32(stft + STFT_HEALTH) = g_hp_kept = hp > 0 ? hp : 0;
        }
        g_shake = 2 * HIT_SHAKE;
        S16(o + TIE_STATE) = -1;                                 /* (the game's burst) */
        g_bomb_fly = 0;
    } else if (g_bomb_age > BOMB_LIFE) g_bomb_fly = 0;
}

/* The battle's TIEs (one group, none after): on entering native flight the first time a run every
 * chase fighter live past the first FINAL_TIES slots is dropped (parked, hidden, health 0, not counted as a kill). */
#define FINAL_TIES       2          /* (4, with the battle's 7 and the bomber, put up to 9 TIEs round the Falcon) */
int g_ties_cut;                     /* (gallrun.c resets it with the run) */
static uint32_t g_seen[TIE_SLOTS];  /* finale(): the chase as last frame (a slot gone down: a kill) */
void ties_final(void) {
    if (g_ties_cut) return;
    g_ties_cut = 1;
    g_hang_cap = 0; g_hang_gone = 0;                             /* (the battle takes them over: D16) */
    uint32_t n = U32(CLASS_TIEF + 8), tie = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    for (uint32_t i = 0; i < n && i < 32; i++, tie += size) {
        if (!chaser(tie, i, n)) continue;
        int k = 0;
        while (k < FINAL_TIES && g_chase[k] != tie) k++;
        if (k < FINAL_TIES) continue;
        for (k = FINAL_TIES; k < TIE_SLOTS; k++) if (g_chase[k] == tie) { g_chase[k] = 0; g_seen[k] = 0; }
        F32(tie + TIE_POS) += TIE_HIDE_AWAY; F32(tie + TIE_POS + 8) = TIE_HIDE;
        F32(tie + TIE_HEALTH) = 0;
        if (i < 10) g_tie_down[i] = -1;
        g_hang_held &= ~(1u << i);
        uint32_t nd = U32(tie + TIE_NODE);
        if (valid_ptr(nd)) U16(nd + NODE_SHOW) &= 0x00FF;
    }
}

int finale(void) {
    uint32_t *seen = g_seen;
    if (g_sl_jump < 0 || !g_free || paused()) { for (int i = 0; i < TIE_SLOTS; i++) seen[i] = 0; return 0; }
    float dt = frame_dt();
    if (!g_won && !g_native) revive(dt);
    bombers();
    for (int i = 0; i < TIE_SLOTS; i++)                         /* down since the last frame (pursuit() drops them) */
        if (seen[i] && !(F32(seen[i] + TIE_HEALTH) > 0)) g_kills++;   /* (not by height: in space the Falcon flies anywhere) */
    for (int i = 0; i < TIE_SLOTS; i++) seen[i] = g_chase[i];
    float m[3], d = 0;
    for (int j = 0; j < 3; j++) { m[j] = F32(GALL_RAM + IMG_BATTLE + 4 * j) - g_fly_pos[j]; d += m[j] * m[j]; }
    if (!g_rogue && !g_won && d < LUKE_NEAR * LUKE_NEAR && !S16(MSG_HOLD)) { g_rogue = 1; say_last(LINE_LUKE); }
    if (!g_won && towers_left() == 0) g_won = 1;                 /* all six towers down: at once */
    if (g_won) {                                                 /* (the fly-away, Lando's line, */
        if (!g_won_said) {                                       /*  the jump, the end; the line at */
            g_won_said = 1;                                      /*  once, not held, as the fly-away begins) */
            ((say_fn)SAY)(face(FACE_LANDO), 31, LINE_SHOW, 13, "~oThat's the last~nof them! Punch it, Chewie!");
        }
        if (g_native && fly_away(dt)) return 0;
        if (S16(MSG_HOLD)) return 0;
        return fly_jump(dt);
    }
    uint32_t n = U32(CLASS_TIEF + 8), first = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
    if (!g_bt_on || n < BATTLE_N + TIE_SLOTS || (g_xw_t += dt) < XW_EVERY) return 0;
    uint32_t best = 0; float bd = XW_REACH * XW_REACH;
    for (int b = 0; b < 3; b++) {                                /* (battle_pose(): 0..2 the X-Wings) */
        uint32_t xw = first + (n - 1 - b) * size;
        for (int i = 0; i < TIE_SLOTS; i++) {
            if (!g_chase[i]) continue;
            float q = 0;
            for (int j = 0; j < 3; j++) { float e = F32(g_chase[i] + TIE_POS + 4 * j) - F32(xw + TIE_POS + 4 * j); q += e * e; }
            if (q < bd) { bd = q; best = g_chase[i]; }
        }
    }
    if (best) { F32(best + TIE_HEALTH) = 0; g_xw_t = 0; }
    return 0;
}

/* A flown bomber or our bomb at p, its nose along its way (the run's, the bomb's). */
static void bomb_pose(uint32_t obj, const float *p) {
    float f[3], q[3] = { p[0], p[1], p[2] };
    int i = tie_index(obj);
    if (i == BOMB_OBJ) for (int j = 0; j < 3; j++) f[j] = g_bomb_way[j];
    else bomb_way(i - 10, f);
    obj_pose(obj, q, f, 1);
}
typedef uint32_t (*method_ret_fn)(uint32_t, uint32_t, uint32_t, uint32_t);
uint32_t tie_draw(uint32_t obj, uint32_t a1, uint32_t a2, uint32_t a3) {          /* (its result passed on) */
    uint32_t r = ((method_ret_fn)g_tie_draw)(obj, a1, a2, a3);
    if (g_bt_on) { int b = battle_index(obj); if (b >= 0) battle_pose(obj, b); }
    if (tie_wave(obj)) {                                         /* (the draw shows it again: hidden after it) */
        uint32_t nd = U32(obj + TIE_NODE);
        if (bomb_fly(obj)) bomb_pose(obj, (float *)(obj + TIE_POS));
        else if (valid_ptr(nd)) U16(nd + NODE_SHOW) &= 0x00FF;
    } else if (hang_held(obj)) {                                 /* a chaser held in its hangar (D13) */
        uint32_t nd = U32(obj + TIE_NODE);
        if (valid_ptr(nd)) U16(nd + NODE_SHOW) &= 0x00FF;
    }
    return r;
}

/* The radar's list (docs/reverse-engineering.md, space radar): the ship HUD's target (the panel, "T.I.E. BOMBER") is the
 * record nearest the screen's middle, at any distance (0x80094DC4). The waves parked TIE_HIDE_AWAY off still pinged and
 * were taken (the user, 2026-10-18: the bombers' panel in stage 2): a record that far off Chor is dropped (the last one
 * moved into its place). Each wave's, right after the game's update sent its ping. */
#define RADAR_LIST       0x8018E468 /* 0x20-byte records: +8 x, y, z */
#define RADAR_COUNT      0x800E1B30
#define RADAR_HELD       0x800E1B90 /* s32: the ship HUD's last target's list index, its panel held while the float at
                                       0x8018E8AC > 0, read with no check against RADAR_COUNT (0x80096564) */
static void radar_drop_far(void) {
    if (!U32(CLASS_CHOR + 8)) return;
    float cx = F32(U32(CLASS_CHOR + 0x10) + 0x50);
    uint32_t n = U32(RADAR_COUNT);
    for (uint32_t i = 0; i < n && n <= 32;) {
        uint32_t r = RADAR_LIST + 0x20 * i;
        if (absf(F32(r + 8) - cx) > TIE_HIDE_AWAY * 0.5f) {
            n--;
            for (int k = 0; k < 0x20; k += 4) U32(r + k) = U32(RADAR_LIST + 0x20 * n + k);
        } else i++;
    }
    U32(RADAR_COUNT) = n;
    if ((int)U32(RADAR_HELD) >= (int)n) U32(RADAR_HELD) = (uint32_t)-1;   /* the HUD's held slot past the count: none (a
                                                                    parked bomber's ping landed there) */
}

void tie_update(uint32_t obj, uint32_t a1, uint32_t a2, uint32_t a3) {
    float at[3] = { F32(obj + TIE_POS), F32(obj + TIE_POS + 4), F32(obj + TIE_POS + 8) };   /* (ours, if flown by us) */
    int ti = tie_index(obj);
    if (ti >= 0 && ti < 32 && (g_hang_led >> ti & 1)) U32(obj + TIE_LEADER) = 0;   /* launching: no leader (D14) */
    ((method_fn)g_tie_update)(obj, a1, a2, a3);
    if (ti >= 0 && ti < 32 && (g_hang_led >> ti & 1) && F32(obj + TIE_HEALTH) > 0)   /* launching / approaching: its place */
        for (int j = 0; j < 3; j++) F32(obj + TIE_POS + 4 * j) = at[j];   /* ours, not the AI's */
    float was = ti >= 0 && ti < 32 ? g_tie_hp[ti] : 1;            /* (its health before this update: D17) */
    if (ti >= 0 && ti < 32 && g_hang_t >= 0 && !g_ties_cut && !tie_wave(obj)) {   /* (D1) a chaser of the pursuit shot */
        int k = 0;                                                /* down: in the parked set for good; its relaunch */
        while (k < TIE_SLOTS && g_chase[k] != obj) k++;           /* parked with its health back at 0 */
        if (k < TIE_SLOTS && was > 0 && !(F32(obj + TIE_HEALTH) > 0)) { g_hang_gone |= 1u << ti; g_hang_cap |= 1u << ti; }
        if ((g_hang_gone >> ti & 1) && F32(obj + TIE_HEALTH) > 0) F32(obj + TIE_HEALTH) = 0;
    }
    if (ti >= 0 && ti < 32) g_tie_hp[ti] = F32(obj + TIE_HEALTH);
    if (g_bt_on) { int b = battle_index(obj); if (b >= 0) { battle_pose(obj, b); return; } }
    if (tie_wave(obj)) {                                         /* a wave's: not seen, not firing, held at the park */
        uint32_t nd = U32(obj + TIE_NODE);
        U32(obj + TIE_FLAGS) |= TIE_HOLD_FIRE;
        if (bomber(obj)) F32(obj + TIE_BOMB_T) = BOMB_HOLD_T;    /* (the game never launches) */
        if (bomb_fly(obj)) { bomb_pose(obj, at); return; }       /* the end's fight: bombers() flies it */
        if (valid_ptr(nd)) { U16(nd + NODE_SHOW) &= 0x00FF; F32(nd + NODE_POS + 8) = TIE_HIDE * 10; }
        radar_drop_far();
        if (U32(CLASS_CHOR + 8)) {
            uint32_t chor = U32(CLASS_CHOR + 0x10);
            F32(obj + TIE_POS) = F32(chor + 0x50) + TIE_HIDE_AWAY;
            F32(obj + TIE_POS + 4) = F32(chor + 0x54);
            F32(obj + TIE_POS + 8) = TIE_HIDE;
        }
        return;
    }
    if (hang_held(obj)) {                                        /* a chaser held in its hangar: hidden as a wave (D13) */
        uint32_t nd = U32(obj + TIE_NODE);
        if (valid_ptr(nd)) { U16(nd + NODE_SHOW) &= 0x00FF; F32(nd + NODE_POS + 8) = TIE_HIDE * 10; }
        if (g_hang_cap >> ti & 1) hang_away(obj);                /* past HANG_N: kept away (D16) */
        return;
    }
    uint32_t n = U32(CLASS_TIEF + 8);                            /* the game's relaunch of a downed flight, in the canyon */
    if (ti >= 0 && ti < 32 && !g_free && g_alt < CANYON_DROP && valid_ptr(U32(CLASS_CHOR + 0x10))   /* (it put them in */
        && g_tie_hp_at && g_ov_frames - g_tie_hp_at <= 2 && !(was > 0) && F32(obj + TIE_HEALTH) > 0 && !(g_hang_led >> ti & 1)   /* rock): */
        && chaser(obj, (uint32_t)ti, n)) {                       /* on the route point at once, before its draw */
        uint32_t first = U32(CLASS_TIEF + 0x10), size = U32(CLASS_TIEF + 0xC);
        int slot = 0;                                            /* (pursuit()'s slots only, D11) */
        for (int j = 0; j < ti; j++) slot += chaser(first + (uint32_t)j * size, (uint32_t)j, n);
        if (slot < slots_now()) tie_back_route(obj, (uint32_t)ti, g_tie_node);
    }
    int i = 0;
    while (i < TIE_SLOTS && g_chase[i] != obj) i++;
    if (i == TIE_SLOTS) return;
    float f[3], q[3], fl, ql;
    for (int j = 0; j < 3; j++) f[j] = g_tie_aim[j] - F32(obj + TIE_POS + 4 * j);
    fl = len3(f);
    float c[3] = { F32(obj + TIE_VEL), F32(obj + TIE_VEL + 4), F32(obj + TIE_VEL + 8) }, cl = len3(c);
    if (fl >= 1e-3f && cl >= 1e-3f) {                            /* (D18) turn from the heading at most a step */
        for (int j = 0; j < 3; j++) { f[j] /= fl; c[j] /= cl; }
        fl = 1;
        float x[3] = { c[1] * f[2] - c[2] * f[1], c[2] * f[0] - c[0] * f[2], c[0] * f[1] - c[1] * f[0] };
        float dot = c[0] * f[0] + c[1] * f[1] + c[2] * f[2], a = atan2_r(len3(x), dot), st = TIE_TURN_MAX * frame_dt();
        if (a > st) {
            if (dot < -0.99f) {                                  /* opposite: about world z */
                float cs = cos_r(st), sn = sin_r(st);
                f[0] = c[0] * cs - c[1] * sn; f[1] = c[0] * sn + c[1] * cs; f[2] = c[2];
            } else for (int j = 0; j < 3; j++) f[j] = c[j] + (f[j] - c[j]) * (st / a);
            fl = len3(f);
        }
    }
    q[0] = f[1]; q[1] = -f[0]; q[2] = 0;                          /* level, to the right */
    ql = sqrt_f(q[0] * q[0] + q[1] * q[1]);
    if (fl < 1e-3f || ql < 1e-3f) return;
    for (int j = 0; j < 3; j++) { f[j] /= fl; q[j] /= ql; }
    float v[3] = { q[1] * f[2] - q[2] * f[1], q[2] * f[0] - q[0] * f[2], q[0] * f[1] - q[1] * f[0] };   /* up = right x forward */
    uint32_t nd = U32(obj + TIE_NODE);
    for (int j = 0; j < 3; j++) {
        F32(obj + TIE_VEL + 4 * j) = f[j];
        F32(obj + TIE_UP + 4 * j) = v[j];
        if (nd) {
            F32(nd + NODE_ROWS + 4 * j) = q[j];
            F32(nd + NODE_ROWS + 12 + 4 * j) = f[j];
            F32(nd + NODE_ROWS + 24 + 4 * j) = v[j];
        }
    }
}
