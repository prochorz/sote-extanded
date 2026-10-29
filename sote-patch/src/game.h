/* Shadows of the Empire (USA Rev 2 / v1.2) addresses used by the patch.
 * Offsets come from reverse engineering plus our own RAM probes. */
#pragma once
#include <stdint.h>

#define U32(a) (*(volatile uint32_t *)(a))
#define S16(a) (*(volatile int16_t *)(a))
#define U16(a) (*(volatile uint16_t *)(a))
#define F32(a) (*(volatile float *)(a))
#define F64(a) (*(volatile double *)(a))

/* Controller 1 as decoded by the game: s16 stick x, s16 stick y, u32 buttons at +0x14. */
#define PAD_STICK_X     0x80113098
#define PAD_STICK_Y     0x8011309A
#define PAD_BUTTONS     0x801130AC

/* Active button preset and preset table (96 bytes per preset). Presets 0-7 are
 * Standard x2, Traditional x2, Alternate x2, Strafe x2 (names table 0x800DD650). */
#define CTRL_PRESET     0x800D252C
#define CTRL_BINDINGS   0x800E6808
#define BIND_JUMP       0x1A        /* A in Standard */
#define BIND_AIM        0x1C        /* Z by default: aim mode, stick pitches the gun */
#define BIND_STRAFE     0x1E        /* R by default: stick x strafes */
#define BIND_STRAFE_L   0x20        /* "Strafe" preset only: Z strafes left */
#define BIND_STRAFE_R   0x22        /* "Strafe" preset only: R strafes right */

/* Global simulation step in seconds (double). */
#define FRAME_DT        0x8018E998

/* Native input suppression (stun, cutscene messages) and the camera override matrix. */
#define INPUT_GATE_1    0x800E0EA0
#define INPUT_GATE_2    0x800DEB78
#define CAMERA_OVERRIDE 0x800E5EF4

/* 0x800ba268: response curve used by the native stick decode. */
#define STICK_CURVE     0x800BA268

/* Player motion (Humn): velocity in units/second; flags: on the ground / airborne. */
#define OBJ_VEL         0x098
#define FL_GROUND       0x04000000u
#define FL_AIR          0x08000000u
#define FL_DEATH_FALL   0x10000000u /* set by the game ~20 units into a deadly pit */
#define FL_JET          0x00000300u /* Humn: the jetpack is firing (Gall; fuel float at +0xBC) */
#define FL_SWIM         0x00000400u /* Humn: swimming (the sewer; FL_AIR is set too, A swims up) */
#define OBJ_POS_COPY    0x008       /* second copy of the position the game keeps */
#define OBJ_YAW_COPY    0x014       /* and of the heading (0..360); the game restores yaw from it */
#define OBJ_MATRIX      0x020       /* rotation rows right/forward/up, translation = OBJ_POS */
#define OBJ_MATRIX_COPY 0x108       /* copy used for the camera (translation z + 5.5) */
#define OBJ_MATRIX_DRAW 0x148       /* rebuilt by the game every update (translation +0x178) */
#define OBJ_MATRIX_MODEL 0x208      /* passed to the model by the draw method 0x8007A118 */

/* Animation: set_anim(id, flags, controller, obj + OBJ_ANIM_STATE) evaluates the pose. */
#define SET_ANIM        0x800175B8
#define OBJ_ANIM_STATE  0x18C
#define OBJ_ANIM_CHAIN  0x19C       /* first animation block; the next one at +0x14, name at +0x1C */

/* Player ("Humn") object fields. */
#define OBJ_NAME        0x000       /* class tag, 'Humn' */
#define OBJ_FLAGS       0x074       /* Humn bit 0x400: swimming */
#define OBJ_YAW         0x08C       /* heading in degrees; facing = yaw + 90 */
#define OBJ_YAW_RATE    0x0A4       /* degrees per second, integrated into OBJ_YAW */
#define HUMN_HEALTH     0x0B4       /* float; 0 starts the death sequence (no flag is set) */
#define OBJ_FUEL        0x0BC       /* Humn: jetpack fuel, 0..the game's max (see FUEL_MAX) */
#define FUEL_MAX        0x800E0DD8  /* float 100: the game clamps the fuel to this in the control
                                     * function (burns it while the jetpack fires, FL_JET) */
#define TAG_HUMN        0x48756D6Eu
#define TAG_HUMT        0x48756D54u   /* Dash on the Ord Mantell train: a variant of Humn */
#define TAG_STFT        0x53746674u   /* the player ship in space levels (Skyhook, Asteroid Field, Station Chase) */

/* Stack slots of the decoded movement intent inside 0x80074FA4. */
#define DEC_FORWARD     0x17E
#define DEC_BACK        0x17C
#define DEC_TURN_A      0x17A
#define DEC_TURN_B      0x178
#define DEC_TURN_MAG    0x160
#define DEC_FWD_MAG     0x15C

/* Camera views, cycled by the game's Camera button (L): 1 follow (behind Dash), 0 first person,
 * 4 fixed "drop" camera, 5 overhead. set_camera(player, view, 0) switches like L does. */
#define CAMERA_VIEW     0x800E0EEC  /* s16 */
#define CAMERA_FOLLOW   1
#define SET_CAMERA      0x8006A214

/* Class records (table from 0x80112B08, 0x30 each): +8 instance count, +0xC instance size,
 * +0x10 first instance; instances sit back to back. */
#define CLASS_COUNT     0x08
#define CLASS_SIZE      0x0C
#define CLASS_HEAD      0x10
#define CLASS_TRAI      0x80112F28  /* train cars: +0x50 position, +0x30 row = car axis */
#define CLASS_TGUN      0x80112F58  /* train level drones/guns, not in the target pool */
#define CLASS_TTAR      0x80112CE8  /* train level targets, not in the target pool */
#define CLASS_TTRP      0x80112FB8  /* train level troopers (droids riding the cars), not in the pool */
#define CLASS_ESHD      0x80112E98  /* boss hit shells (TAG_ESHD) */
#define TAG_TRAI        0x54726169u

/* Train camera: view u32 (1 behind, 0 first person, 2 overhead), behind distance (default 8). */
#define TRAIN_VIEW      0x8018E928
#define TRAIN_CAM_DIST  0x800E53D4
#define TRAIN_DIST_STD  8.0f
#define TRAIN_BEHIND    0x800A7C90  /* (float blend seconds): switch to the behind view */

/* Camera dolly ("Doly") object: +0x60 points at the followed object. */
#define DOLY_TARGET     0x060

/* Targetable object pool (same gates the game's own targeting uses). */
#define TARGET_POOL     0x80112838  /* +8 count, +12 stride, +16 base */
#define REC_ALIVE       0x84
#define REC_FLAGS       0x68        /* u16, bit 2: active */
#define REC_OBJECT      0x98
#define OBJ_TFLAGS      0x006       /* u16, bit 2: targetable */
#define OBJ_POS         0x050
#define OBJ_HEALTH      0x060
#define OBJ_Z_MIN       0x068
#define OBJ_Z_MAX       0x06C
#define OBJ_COLLIDER    0x070       /* excluded from line-of-sight traces */
#define TAG_BOXX        0x426F7878u
#define TAG_BOSS        0x426F7373u   /* bosses, e.g. the Echo Base AT-ST (model tag at +0x78) */
#define BOSS_HEIGHT     0x0AC         /* Boss: float, 18 for the AT-ST; its z min/max are 0 */
#define BOSS_STATE      0x060         /* Boss: +0.01 dormant (before its cutscene), -0.01 fighting */
#define BOSS_DEAD_FLAG  0x20          /* Boss: set in OBJ_TFLAGS when destroyed (0x43 -> 0x63) */
#define BOSS_HEALTH     0x5C4         /* Boss: real health, 750 = the HUD's 100% (AT-ST and IG-88) */
#define TAG_ESHD        0x45536864u   /* hit shells wrapping a boss's body parts */
#define ESHD_OWNER      0x080         /* EShd: the boss it belongs to; +0x60 its health (-1: not a target) */
#define TAG_GLAD        0x676C6164u   /* model tag (+0x78) of Xizor's palace gladiator droid (class Boss) */
#define OBJ_MODEL       0x078
#define TAG_TROP        0x54726F70u   /* the common enemy class (troopers, guards, the sewer dianoga) */
#define TROP_KIND       0x074         /* Trop: 0x100 the dianoga's eye, 0x200 a tentacle; 0x400 awake */
#define TAG_ANIM        0x416E696Du

/* Current sub-level id (s16; 4/5 Echo Base, 6 Asteroid Field, see the level list). */
#define LEVEL_ID        0x8013CE0E

/* 0x800194DC(sub-level): load a sub-level (the debug list's level entries). */
#define LEVEL_LOAD      0x800194DC

/* Fog colour (s16 x3, as set and as in use), lights (s16 RGB), view override (u32: 1 keeps
 * edited perspective/fog/light; see the Cheats entries). */
#define FOG_RGB_SET     0x80192F30
#define FOG_RGB_USE     0x800E7AD0
#define AMBIENT_RGB     0x800E7AAC
#define LIGHT_RGB       0x800E7AB4
#define VIEW_OVERRIDE   0x80192F38

/* 0x80026130(tag, 0): first instance of a class, 0 if none. */
#define FIND_CLASS      0x80026130

/* 0x800654A0: segment trace. Returns hit distance (<0: clear). */
#define TRACE_FN        0x800654A0

/* Laser projectiles: base pointer of the pool; a new bolt's direction is at +0xA0. */
#define LASER_POOL      0x80112E60
#define BOLT_POS        0x50
#define BOLT_DIR        0xA0
/* Seeker missiles (class Misl): home on an object's matrix (+0x94 = object + 0x20), this high above it. */
#define SHOT_LIFE       0x8C        /* projectile (Expl) lifetime left, seconds; set by the spawn 0x80064584 */
#define MISL_AIM_Z      0x98

/* Frame display list: pointer to the next free Gfx command. The scene frame is
 * closed by 0x800BB630 right after the HUD boxes are drawn. */
#define GFX_HEAD        0x80192F28
#define SCREEN_W        320
#define SCREEN_H        240

/* Active camera: basis rows right/forward/up at +0x14/+0x24/+0x34, eye at +0x44.
 * The on-foot perspective is fovy ~77 degrees at 4:3 (read from the game's
 * combined projection-view matrix). */
#define ACTIVE_CAMERA   0x800D08A4
#define CAM_RIGHT       0x14
#define CAM_FORWARD     0x24
#define CAM_UP          0x34
#define CAM_EYE         0x44
#define PROJ_X          0.9456f     /* fallbacks if PERSPECTIVE looks wrong */
#define PROJ_Y          1.2577f

/* Current perspective (floats): fovy in degrees, aspect, near, far. Per level: Echo Base
 * 77/1.33/0.6/200 on foot in Echo Base, 77/1.33/0.6/250 in Suprosa, 87.75/1.33/0.2/500 on the
 * Mos Eisley swoop. */
#define PERSPECTIVE     0x80192F14

/* Fog: start/end as s16 depth on the N64 0..1000 scale (1000 = far plane), set by
 * 0x800BAF78 and used by the gSPFogPosition emitter at 0x800BADAC. No fog when the
 * byte FOG_OFF is set or FOG_MAX <= 0. */
#define FOG_MIN         0x800E7AD8
#define FOG_MAX         0x800E7ADC
#define FOG_OFF         0x800D2538

/* Native strafe intents (left/right) and the strafe curve constant. */
#define DEC_STRAFE_L    0x172
#define DEC_STRAFE_R    0x170
#define STRAFE_CURVE_K  0x800EB9E8
