/* Look: Dash drawn as the red palace guard (a Cheats row, g_guard_on: 0 Dash, 1 Guard, 2 Luke; 0 at boot, not saved).
 * Luke is the guard with a head of ours instead of the helmet: the image's LUKE list (after the 19 bones) takes the
 * place of the image's meshes on Dash's head bone (bone 1); every other bone as Guard. Readers that test g_guard_on
 * for nonzero keep their meaning: the armour is on. An image without LUKE draws 2 as Guard.
 *
 * The on-foot player's model is a tree of bone nodes (the nodes of his animation blocks' entries, +0x08; each node
 * +0x0C child count, +0x10 child list: bone nodes and mesh nodes). The image local/game/guard.bin
 * (harness/guard_asset.py, loaded at GUARD_RAM by _start) holds the guard's meshes already baked into the frames of
 * Dash's bones, and per Dash bone 0..18 a mesh count and list. Guard on: every bone node of Dash's `trot` block is
 * pointed at a child list of ours: its bone children, the image's meshes for that bone, then on the right hand
 * (bone 6) Dash's weapon; Dash's other meshes are left out. The weapon is the hand's mesh with w0 bit 0x80, read from
 * Dash's own list before it is replaced. That bit is no weapon mark: the mesh draw (0x800BBBF8) sets or clears it on
 * every drawn mesh from the render state the mesh drawn before left (s16 0x800E7C38), so it follows draw order (his
 * jetpack on the chest carries it too). In Dash's order (hand, weapon) the weapon has it; drawn last in our list it
 * keeps it and the guard's hand does not, so hang.c's hide_weapon, which picks the 0x80 meshes, still hides the
 * weapon. Animations, controls, lock-on and the HUD are Dash's:
 * only the drawn meshes change. Off: the game's lists put back, each only where the node still holds ours (hang.c
 * swaps the hand's list while hanging: that node waits until hang puts ours back). The game never rebuilds a list
 * while the player lives; a new player (level load, death) has new nodes, so the lists are built again.
 *
 * Switching between Guard and Luke builds the lists again from the saved game lists. Luke's head: harness/luke/
 * luke_model.py (luke_head.gltf), put into the image by guard_asset.py.
 *
 * The drop: the guard's legs are longer than Dash's, so on Dash's bones the armour's soles were drawn 0.30 above the
 * floor. guard_place, from the Humn draw method's copy of his matrix +0x208 into his placement node (hook 0x8007A134,
 * hooks.S tramp_look_place), lowers that node's translation z by LOOK_DROP while the look is on this player's nodes:
 * the whole figure, scaled by how upright the body is (the model bone's up axis: standing the full 0.30, lying face
 * down ~0, where the lowest point is the hands and chest, not the soles). After the copy, because the copy rewrites the node every draw (a write from
 * cheats_frame is gone before the draw) and +0x208 belongs to hang.c and the control-end hook. Not while hanging or
 * climbing: hang_face places the figure so the hand meets the rim, 0.30 lower would put the hand into the ledge.
 *
 * The lightning (guard_zap, the duel's Disruptor hit): the image's LITN list (after LUKE: variant count, part count,
 * per part a Dash bone and its variants' meshes, harness/luke/lightning_model.py by guard_asset.py) adds one variant to
 * each of those bones' lists of ours, the next one every ZAP_STEP game frames, for the seconds asked; then the lists'
 * own counts again. Only on our lists (the Look on): a node holding the game's list (or hang.c's) is left alone.
 *
 * The saber (feature saber, saber.c): with the Look on Luke and the on-foot weapon id the saber's (Humn +0xB8 6), the
 * weapon's slot of the hand's list of ours holds the image's SABR mesh (after LITN: 'SABR', mesh count, list) instead of
 * Dash's weapon, every frame (blade()); the weapon is back the frame the id or the Look changes. The same slot: drawn
 * last after the guard's hand, it keeps the weapon's w0 bit 0x80, so hang.c's hide_weapon hides it as it does the
 * blaster.
 *
 * Luke's HUD portrait (face()): the level's HUD sprite table (*HUD_SPRITES) slot 9 is Dash's face by the lives count, a
 * 64 x 38 CI4 record of two bitmaps. With the Look on Luke the slot holds the image's FACE record (after SABR's: 'FACE',
 * the record; harness/luke/luke_portrait.py: Dash's record with Luke's face from Cut 13's still inside the frame);
 * a slot of another form is left alone. Off Luke the game's record goes back, only into the table it was taken from
 * and only while the slot still holds ours (each level's table is new: its slot is the game's own). The game's record
 * is not empty, so it is put back instead of 0. Ours takes the game's place on screen (+0 x, y) every frame: the HUD
 * places by the record.
 *
 * The jump (jump()): Luke is a Force user, so with the Look on Luke his jump reaches twice Dash's apex, through the
 * game's own Jump Power (JUMP_POWER, the debug list's entry, default 1.0). It scales the launch vz (measured: x1 vz 15,
 * apex 4.38; x1.4142 vz 21.2, apex 8.58), so the factor is sqrt 2 (LUKE_JUMP). Applied only at the switches (Look
 * onto Luke: x LUKE_JUMP, off Luke: / LUKE_JUMP), so a Cheats row change of Jump Power while on Luke holds and the row
 * shows the value in force; clamped to the row's range 0.1..3. The game keeps the value through a level reload and a
 * death, and a landing from twice the height costs no health. Reset cheats restores Jump Power in Dash's basis
 * (cheats.c: saved divided by LUKE_JUMP while on Luke, g_jump_luke cleared on the write).
 *
 * Called from cheats_frame() once per rendered frame. Off and nothing of ours left: returns at once. */
#include "common.h"

#define TAG_TROT        0x74726F74u /* 'trot': the block whose bone order the image follows */
#define GUARD_MAGIC     0x47415244u /* 'GARD', then the bone count and per bone (mesh count, list) */
#define LUKE_MAGIC      0x4C554B45u /* 'LUKE' after the bones, then Luke's head's (mesh count, list) */
#define LUKE_AT         (GUARD_RAM + 8 + 8 * BONES)
#define BONE_HEAD       1           /* the head: the helmet, or Luke's head */
#define BONES           19
#define LIST_MAX        8           /* Dash's chest: 2 bones + the image's meshes */
#define BONE_HAND       6           /* right hand: keeps the weapon */
#define BONE_CHECK      17          /* pelvis: applied when its node holds our list */
#define BONE_MODEL      18          /* the model bone: rest 2.906 x identity, its rotation the whole figure's tilt */
#define MESH_WEAPON     0x80u
#define LOOK_DROP       0.30f       /* drawn soles 0.310, RAM walk 0.301 (Guard and Luke: same legs); Guri's ~0 */
#define NODE_Z          0x40        /* placement node: translation x, y, z at +0x38 */
#define LITN_MAGIC      0x4C49544Eu /* 'LITN' after LUKE's list: variant count, part count, per part (bone, variants) */
#define LITN_AT         (LUKE_AT + 12)
#define LITN_PARTS      8           /* (the image's 4: chest, upper arms, head) */
#define LITN_VARIANTS   8           /* (its 3) */
#define ZAP_STEP        3           /* game frames a variant shows */
#define GAME_CLOCK      0x8018E9A8  /* double, game time (s): stands while paused */
#define SABR_MAGIC      0x53414252u /* 'SABR' after LITN's parts: mesh count, list (the saber's blade, saber.c) */
#define HUMN_WEAPON     0xB8        /* s16: the on-foot weapon id */
#define WEAPON_SABER    6
#define FACE_MAGIC      0x46414345u /* 'FACE' after SABR's 24 bytes: Luke's HUD portrait record (0: none) */
#define HUD_SPRITES     0x8013CE2C  /* -> the level's HUD sprite records, one per element */
#define SLOT_FACE       9           /* Dash's portrait by the lives count */
#define FACE_WH         0x00400026u /* +4 s16 width, height: 64 x 38 */
#define FACE_TILES      2           /* +0x1C s16 bitmap count */
#define JUMP_MIN        0.1f        /* the Cheats row's range */
#define JUMP_MAX        3.0f

int g_guard_on;

static uint32_t g_node[BONES], g_cnt[BONES], g_list[BONES];   /* the game's lists, saved */
static uint32_t g_ours[BONES][LIST_MAX + 1];   /* + the lightning's slot */
static uint32_t g_ocnt[BONES];      /* our lists' own counts */
static double g_zap_until, g_zap_clock;   /* the game clock the lightning ends at; at its last step */
static uint32_t g_zap_frame;        /* game frames it has run */
static int g_zapped;                /* the lightning is in the lists */
static uint32_t g_have;             /* bit per bone: saved and ours written */
static int g_built;                 /* the Look value our lists were built for */
static uint32_t g_humn;             /* the Humn whose nodes apply dressed: the one guard_place lowers */
#if FEATURE_SABER                   /* read only by blade(): unused-but-set without the saber */
static uint32_t g_weapon, g_wslot;  /* Dash's weapon mesh in the hand's list of ours, and its slot (0: none) */
#endif
static uint32_t g_face_tab, g_face_game;   /* the table our portrait went into, and the game's record it replaced */
int g_jump_luke;                    /* Jump Power holds Luke's factor */

static uint32_t trot_block(uint32_t humn) {
    uint32_t b = U32(humn + OBJ_ANIM_CHAIN);
    for (int i = 0; i < 40 && valid_ptr(b); i++, b = U32(b + 0x14))
        if (U32(b + 0x1C) == TAG_TROT) {
            uint32_t e = b + 0x38;
            for (int k = 0; k < BONES - 1; k++, e += 0xA0)
                if (U32(e + 0x0C) != e + 0xA0) return 0;
            return U32(e + 0x0C) ? 0 : b;
        }
    return 0;
}

static int is_bone(uint32_t c, const uint32_t *node) {
    for (int i = 0; i < BONES; i++) if (c == node[i]) return 1;
    return 0;
}

static void apply(const uint32_t *node) {
    uint32_t cnt[BONES];
    for (int b = 0; b < BONES; b++) {               /* the lists built first: nothing written unless all fit */
        int keep = (g_have >> b & 1) && node[b] == g_node[b];   /* still waiting for a restore: the save stands */
        uint32_t n = keep ? g_cnt[b] : U32(node[b] + 0x0C), list = keep ? g_list[b] : U32(node[b] + 0x10);
        uint32_t m = U32(GUARD_RAM + 8 + 8 * b), mine = U32(GUARD_RAM + 12 + 8 * b), k = 0;
        if (b == BONE_HEAD && g_guard_on == 2 && U32(LUKE_AT) == LUKE_MAGIC && U32(LUKE_AT + 4)) {
            m = U32(LUKE_AT + 4); mine = U32(LUKE_AT + 8);
        }
        if (n > LIST_MAX || (n && !valid_ptr(list)) || (m && !valid_ptr(mine))) return;
        uint32_t weapon = 0;
        for (uint32_t i = 0; i < n; i++) {
            uint32_t c = U32(list + 4 * i);
            if (is_bone(c, node)) {
                if (k == LIST_MAX) return;
                g_ours[b][k++] = c;
            } else if (b == BONE_HAND && valid_ptr(c) && (U32(c) & MESH_WEAPON)) weapon = c;
        }
        if (k + m + (weapon != 0) > LIST_MAX) return;
        for (uint32_t i = 0; i < m; i++) g_ours[b][k++] = U32(mine + 4 * i);
#if FEATURE_SABER
        if (b == BONE_HAND) { g_weapon = weapon; g_wslot = k; }
#endif
        if (weapon) g_ours[b][k++] = weapon;        /* last: the draw sets 0x80 by draw order (see the header) */
        cnt[b] = k;
        if (!keep) { g_node[b] = node[b]; g_cnt[b] = n; g_list[b] = list; }
    }
    for (int b = 0; b < BONES; b++) {
        U32(node[b] + 0x10) = (uint32_t)g_ours[b];
        U32(node[b] + 0x0C) = g_ocnt[b] = cnt[b];
    }
    g_have = (1u << BONES) - 1;
    g_built = g_guard_on;
}

static void restore(const uint32_t *node) {
    for (int b = 0; b < BONES; b++) {
        if (!(g_have >> b & 1)) continue;
        if (node[b] != g_node[b]) { g_have &= ~(1u << b); continue; }   /* not this player's node: dropped */
        if (U32(node[b] + 0x10) == (uint32_t)g_ours[b]) {
            U32(node[b] + 0x0C) = g_cnt[b];
            U32(node[b] + 0x10) = g_list[b];
        } else if (U32(node[b] + 0x10) != g_list[b]) continue;      /* another list there (hang's): retried */
        g_have &= ~(1u << b);
    }
}

void guard_zap(float t) {
    g_zap_until = F64(GAME_CLOCK) + t;
}

static void zap(void) {             /* the lightning's variant on its bones' lists of ours, or taken off */
    double now = F64(GAME_CLOCK);
    int on = g_guard_on && now < g_zap_until;
    if (!on && !g_zapped) return;
    if (U32(LITN_AT) != LITN_MAGIC) return;
    uint32_t nv = U32(LITN_AT + 4), np = U32(LITN_AT + 8);
    if (!nv || nv > LITN_VARIANTS || np > LITN_PARTS) return;
    if (now != g_zap_clock) { g_zap_clock = now; g_zap_frame++; }
    for (uint32_t j = 0; j < np; j++) {
        uint32_t e = LITN_AT + 12 + 4 * (1 + nv) * j, b = U32(e);
        if (b >= BONES || !(g_have >> b & 1) || U32(g_node[b] + 0x10) != (uint32_t)g_ours[b]) continue;
        uint32_t m = U32(e + 4 + 4 * (g_zap_frame / ZAP_STEP % nv));
        if (on && valid_ptr(m)) { g_ours[b][g_ocnt[b]] = m; U32(g_node[b] + 0x0C) = g_ocnt[b] + 1; }
        else U32(g_node[b] + 0x0C) = g_ocnt[b];
    }
    g_zapped = on;
}

static void lists(void) {
    if (!g_guard_on && !g_have) return;
    if (g_guard_on && g_have && g_built == g_guard_on && U32(g_node[BONE_CHECK] + 0x10) == (uint32_t)g_ours[BONE_CHECK])
        return;
    uint32_t humn = ((find_fn)FIND_CLASS)(TAG_HUMN, 0), b, node[BONES];
    if (!humn || !(b = trot_block(humn))) return;
    if (U32(GUARD_RAM) != GUARD_MAGIC || U32(GUARD_RAM + 4) != BONES) return;
    for (int i = 0; i < BONES; i++)
        if (!valid_ptr(node[i] = U32(b + 0x38 + 0xA0 * i + 0x08))) return;
    if (g_guard_on) {
        if (U32(node[BONE_CHECK] + 0x10) != (uint32_t)g_ours[BONE_CHECK] || g_built != g_guard_on) apply(node);
        if (g_have == (1u << BONES) - 1) g_humn = humn;
    } else {
        restore(node);
        if (!g_have) g_humn = 0;
    }
}

static __attribute__((noinline)) uint32_t sabr_at(void) {   /* the image's SABR block, 0: none */
    uint32_t at = LITN_AT + 12 + 4 * (1 + U32(LITN_AT + 4)) * U32(LITN_AT + 8);
    return U32(LITN_AT) == LITN_MAGIC && U32(at) == SABR_MAGIC ? at : 0;
}

#if FEATURE_SABER
static void blade(void) {           /* the weapon's slot: the saber's hilt while it is out on Luke (empty while it is
                                     * dark: saber_dark), else the weapon */
    if (!g_weapon || !(g_have >> BONE_HAND & 1) || !g_humn) return;
    uint32_t at = sabr_at(), m = g_weapon;
    if (at && U32(at + 4) && g_guard_on == 2
        && S16(g_humn + HUMN_WEAPON) == WEAPON_SABER && valid_ptr(U32(U32(at + 8)))) m = saber_dark() ? 0 : U32(U32(at + 8));
    g_ours[BONE_HAND][g_wslot] = m;
}
#else
static inline void blade(void) {}
#endif

static void face(void) {           /* Luke's portrait in the HUD's slot 9 while the Look is Luke (see the header) */
    uint32_t at = sabr_at(), ours, tab = U32(HUD_SPRITES);
    if (!at || U32(at + 24) != FACE_MAGIC || !(ours = U32(at + 28)) || !valid_ptr(tab)) return;
    uint32_t *slot = (uint32_t *)(tab + 4 * SLOT_FACE), s = *slot;
    if (g_guard_on == 2 && s != ours && valid_ptr(s) && U32(s + 4) == FACE_WH && U16(s + 0x1C) == FACE_TILES) {
        g_face_tab = tab; g_face_game = s; *slot = ours;
    }
    if (tab != g_face_tab || *slot != ours) return;   /* only ours, only in the table it went into */
    U32(ours) = U32(g_face_game);                   /* x, y: where the game's is */
    if (g_guard_on != 2) *slot = g_face_game;
}

static void jump(void) {            /* Luke's jump: Jump Power x LUKE_JUMP while the Look is Luke (see the header) */
    int on = g_guard_on == 2;
    if (on == g_jump_luke) return;
    float v = on ? F32(JUMP_POWER) * LUKE_JUMP : F32(JUMP_POWER) / LUKE_JUMP;
    F32(JUMP_POWER) = v < JUMP_MIN ? JUMP_MIN : v > JUMP_MAX ? JUMP_MAX : v;
    g_jump_luke = on;
}

void guard_frame(void) {
    jump();
    lists();
    face();
    blade();
    zap();
}

void guard_place(uint32_t node, uint32_t humn) {
    if (g_guard_on && humn == g_humn && !g_hang_state && g_have == (1u << BONES) - 1
        && U32(g_node[BONE_CHECK] + 0x10) == (uint32_t)g_ours[BONE_CHECK]) {
        /* scaled by the body's tilt: the model bone's local up axis (its node's third row) in the parent frame;
         * standing u ~ 1, lying u ~ 0 (a lying figure's lowest point is not the soles) */
        uint32_t m = g_node[BONE_MODEL];
        float x = F32(m + 0x2C), y = F32(m + 0x30), z = F32(m + 0x34), l = sqrt_f(x * x + y * y + z * z);
        float u = l > 0 ? z / l : 1;
        if (u > 0) F32(node + NODE_Z) -= LOOK_DROP * (u < 1 ? u : 1);
    }
}
