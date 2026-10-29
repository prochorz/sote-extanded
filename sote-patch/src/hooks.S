# Payload entry, hook installer and trampolines.
# Loaded by the boot stub to PAYLOAD_VRAM (see link.ld) before the game starts.

    .set noreorder
    .set noat

#define JAL(a)  (0x0C000000 | (((a) >> 2) & 0x03FFFFFF))
#define NOP     0

# Save every register the C code may clobber (o32 caller-saved set, HI/LO,
# FPU pairs f0..f18 in FR=0 mode, and FCSR). Frame: 0xD8 bytes.
.macro SAVE
    addiu $sp, $sp, -0xD8
    sw $at, 0x18($sp)
    sw $v0, 0x1C($sp)
    sw $v1, 0x20($sp)
    sw $a0, 0x24($sp)
    sw $a1, 0x28($sp)
    sw $a2, 0x2C($sp)
    sw $a3, 0x30($sp)
    sw $t0, 0x34($sp)
    sw $t1, 0x38($sp)
    sw $t2, 0x3C($sp)
    sw $t3, 0x40($sp)
    sw $t4, 0x44($sp)
    sw $t5, 0x48($sp)
    sw $t6, 0x4C($sp)
    sw $t7, 0x50($sp)
    sw $t8, 0x54($sp)
    sw $t9, 0x58($sp)
    sw $ra, 0x5C($sp)
    mfhi $t0
    sw $t0, 0x60($sp)
    mflo $t0
    sw $t0, 0x64($sp)
    cfc1 $t0, $31
    sw $t0, 0x68($sp)
    sdc1 $f0, 0x70($sp)
    sdc1 $f2, 0x78($sp)
    sdc1 $f4, 0x80($sp)
    sdc1 $f6, 0x88($sp)
    sdc1 $f8, 0x90($sp)
    sdc1 $f10, 0x98($sp)
    sdc1 $f12, 0xA0($sp)
    sdc1 $f14, 0xA8($sp)
    sdc1 $f16, 0xB0($sp)
    sdc1 $f18, 0xB8($sp)
.endm

.macro RESTORE
    ldc1 $f0, 0x70($sp)
    ldc1 $f2, 0x78($sp)
    ldc1 $f4, 0x80($sp)
    ldc1 $f6, 0x88($sp)
    ldc1 $f8, 0x90($sp)
    ldc1 $f10, 0x98($sp)
    ldc1 $f12, 0xA0($sp)
    ldc1 $f14, 0xA8($sp)
    ldc1 $f16, 0xB0($sp)
    ldc1 $f18, 0xB8($sp)
    lw $t0, 0x68($sp)
    ctc1 $t0, $31
    lw $t0, 0x60($sp)
    mthi $t0
    lw $t0, 0x64($sp)
    mtlo $t0
    lw $at, 0x18($sp)
    lw $v0, 0x1C($sp)
    lw $v1, 0x20($sp)
    lw $a0, 0x24($sp)
    lw $a1, 0x28($sp)
    lw $a2, 0x2C($sp)
    lw $a3, 0x30($sp)
    lw $t0, 0x34($sp)
    lw $t1, 0x38($sp)
    lw $t2, 0x3C($sp)
    lw $t3, 0x40($sp)
    lw $t4, 0x44($sp)
    lw $t5, 0x48($sp)
    lw $t6, 0x4C($sp)
    lw $t7, 0x50($sp)
    lw $t8, 0x54($sp)
    lw $t9, 0x58($sp)
    lw $ra, 0x5C($sp)
    addiu $sp, $sp, 0xD8
.endm

    .section .text.entry, "ax"
    .globl _start
# Entered from the boot stub with ra = return address of the boot's call to
# the game main (0x80017B60). Installs hooks, then tail-calls the game main.
_start:
    lui $t0, 0xA460
    ori $t1, $zero, 2           # PI_STATUS: clear the DMA-complete interrupt
    sw $t1, 0x10($t0)
    la $t0, _bss_start          # .bss is not in the ROM image: zero it
    la $t1, _bss_end
    b 3f
    nop
0:  sw $zero, 0($t0)
    addiu $t0, $t0, 4
3:  bne $t0, $t1, 0b
    nop
#if FEATURE_CHEATS
    # cheats.c's code and data (link.ld .cheats, out of the 64 KB payload): its fixed ROM slot after the payload ->
    # CHEATS_RAM. No other DMA runs yet: the boot stub's one has finished and the game has not started.
    lui $t0, 0xA460
    li $t1, CHEATS_RAM & 0x1FFFFFFF
    sw $t1, 0($t0)              # PI_DRAM_ADDR
    li $t1, 0x10000000 + CHEATS_ROM
    sw $t1, 4($t0)              # PI_CART_ADDR
    li $t1, CHEATS_LEN - 1
    sw $t1, 0xC($t0)            # PI_WR_LEN (cart -> RAM)
8:  lw $t2, 0x10($t0)           # PI_STATUS: DMA/IO busy
    andi $t2, $t2, 3
    bnez $t2, 8b
    nop
    ori $t1, $zero, 2           # clear the DMA-complete interrupt
    sw $t1, 0x10($t0)
    li $t0, CHEATS_RAM          # the DMA wrote RAM behind the data cache: drop stale lines (as for the Gall Run's code)
    li $t1, CHEATS_RAM + CHEATS_LEN
9:  cache 0x11, 0($t0)          # Hit_Invalidate_D
    addiu $t0, $t0, 16
    sltu $t2, $t0, $t1
    bnez $t2, 9b
    nop
#endif
#if FEATURE_FALCON
    # Falcon model image (build.py appends it after the payload): ROM -> FALCON_RAM. No other
    # DMA runs yet: the boot stub's one has finished and the game has not started.
    lui $t0, 0xA460
    li $t1, FALCON_RAM & 0x1FFFFFFF
    sw $t1, 0($t0)              # PI_DRAM_ADDR
    li $t1, 0x10000000 + FALCON_ROM
    sw $t1, 4($t0)              # PI_CART_ADDR
    li $t1, FALCON_LEN - 1
    sw $t1, 0xC($t0)            # PI_WR_LEN (cart -> RAM)
4:  lw $t2, 0x10($t0)           # PI_STATUS: DMA/IO busy
    andi $t2, $t2, 3
    bnez $t2, 4b
    nop
    ori $t1, $zero, 2           # clear the DMA-complete interrupt
    sw $t1, 0x10($t0)
    li $t0, FALCON_RAM          # the DMA wrote RAM behind the data cache: drop stale lines
    li $t1, FALCON_RAM + FALCON_LEN
5:  cache 0x11, 0($t0)          # Hit_Invalidate_D
    addiu $t0, $t0, 16
    sltu $t2, $t0, $t1
    bnez $t2, 5b
    nop
#endif
#if FEATURE_GALLRUN
    # Gall Run: its code (gallrun.c, gall_*.c) and its image (canyon meshes + route), after the Falcon's:
    # ROM -> GALL_LOAD (the code; the image from GALL_RAM on), same way.
    lui $t0, 0xA460
    li $t1, GALL_LOAD & 0x1FFFFFFF
    sw $t1, 0($t0)
    li $t1, 0x10000000 + GALL_ROM
    sw $t1, 4($t0)
    li $t1, GALL_LEN - 1
    sw $t1, 0xC($t0)
6:  lw $t2, 0x10($t0)
    andi $t2, $t2, 3
    bnez $t2, 6b
    nop
    ori $t1, $zero, 2
    sw $t1, 0x10($t0)
    li $t0, GALL_LOAD
    li $t1, GALL_LOAD + GALL_LEN
7:  cache 0x11, 0($t0)
    addiu $t0, $t0, 16
    sltu $t2, $t0, $t1
    bnez $t2, 7b
    nop
#endif
    addiu $sp, $sp, -0x20
    sw $ra, 0x1C($sp)
    la $a0, hook_table
1:  lw $t0, 0($a0)              # address (0 terminates)
    beqz $t0, 2f
    lw $t1, 4($a0)              # new instruction
    sw $t1, 0($t0)
    cache 0x19, 0($t0)          # Hit_Writeback_Invalidate_D
    cache 0x10, 0($t0)          # Hit_Invalidate_I
    b 1b
    addiu $a0, $a0, 8
2:
#if FEATURE_GALLRUN
    jal gallrun_boot            # the sub-level tables' stock 32 entries into ours (33: the Gall Run is 32)
    nop
#endif
    lw $ra, 0x1C($sp)
    addiu $sp, $sp, 0x20
    j 0x80017B60
    nop

    .section .data
    .align 2
# Each entry: game address, replacement instruction. The jal entries are real
# instructions so the linker resolves their targets (same 256 MB segment).
hook_table:
    # Stick decode, after the intents are known and before stun/death gates. A j, not a jal: the game keeps
    # a button flag in ra here (see tramp_decode).
    .word 0x800758A8
    j tramp_decode
    .word 0x800758AC, NOP
    # Yaw integration on ground and in air.
    .word 0x800778D0
    jal tramp_yaw
    .word 0x800785A8
    jal tramp_yaw
    # Dolly camera mode functions.
    .word 0x8006282C
    jal tramp_cam1
    .word 0x80062AFC
    jal tramp_cam2
    .word 0x80062C8C
    jal tramp_cam3
#if FEATURE_TRAIN
    # On-train player (HumT, control 0x800AAADC): decode end and yaw.
    .word 0x800AAFC0
    jal tramp_decode_t
    .word 0x800AAFC4, NOP
    .word 0x800AC9E0
    jal tramp_yaw_t
#endif
    # Laser bolt spawn, after its direction is transformed to world space.
    .word 0x800321FC
    jal tramp_laser
    # Dash's fire function 0x800737D8 (weapon = Humn +0xB8, jump table 0x800EB908): every
    # projectile spawn jal 0x80064584 (kinds 0-6; the pulse cannon is kind 6), and the
    # seeker's auto-aim result (sw v0, 0x94(s4)).
    .word 0x80073D44
    jal tramp_shot
    .word 0x800741B8
    jal tramp_shot
    .word 0x800741E0
    jal tramp_shot
    .word 0x80074208
    jal tramp_shot
    .word 0x80074510
    jal tramp_shot
    .word 0x80074538
    jal tramp_shot
    .word 0x80074838
    jal tramp_shot
    .word 0x8007E970
    jal tramp_seeker
    # Inside the spawn: the new projectile's lifetime, swc1 f4 / f18, 0x8C(a0).
    .word 0x80064604
    jal tramp_life
    .word 0x800646A0
    jal tramp_life2
#if FEATURE_HANG
    # Humn control function end (after its last calls, before ra is reloaded): ledge hang
    # hold, so the game's own physics/heading in the same update don't move him.
    .word 0x8007A104
    jal tramp_ctrl_end
    # set_anim entry (shared by every object): ledge-hang pose. j, not jal, keeps the
    # caller's ra; both replaced instructions run in the trampoline.
    .word 0x800175B8
    j tramp_setanim
    .word 0x800175BC, NOP
    # Humn weapon code, "fire now?" branch (bnez v0 = auto-repeat, else the fire button):
    # no shooting while hanging or falling from a hang. It runs before the decode hook, so
    # masking the button there was too late.
    .word 0x80072324
    j tramp_fire
#endif
#if FEATURE_CHEATS
    # Pause menu input (input function, paused branch): jal 0x80026124 "paused?".
    .word 0x800153D4
    jal tramp_pause_in
    # Pause screen drawing: jal 0x8001FC90 (its delay slot sets a0 = text context).
    .word 0x80024854
    jal tramp_pause_draw
    # HUD text colour setter, 0x80009138(id, r, g, b, alpha on the stack), the function the
    # game's own HUD updaters call: the Jetpack Fuel cheat recolours the fuel percentage (the
    # blue Invincibility gives the health number). A function entry: j, not jal (keeps ra).
    .word 0x80009138
    j tramp_hud_col
    # Friendly Wampas: the wampa code's three secret-4 checks (jal 0x800359F0, delay slot a0 = 4 kept) ask
    # cheats_secret4, the game's answer or the row. A plain C call: the call sites treat t-registers as clobbered.
    .word 0x800B0680
    jal cheats_secret4
    .word 0x800B2B90
    jal cheats_secret4
    .word 0x800B3374
    jal cheats_secret4
#endif
#if FEATURE_FALCON
    # Stft draw method: jal 0x8000FE48 copying a gun's matrix into its model node (both guns).
    .word 0x8009C790
    jal tramp_gun
    # Same method, the model root's copy: g_ship_drop (Gall Run) lowers the drawn ship.
    .word 0x8009C3F0
    jal tramp_gun
    # Same method, the engine glow node's copy: falcon_gun moves it onto the Falcon's engines.
    .word 0x8009C5F8
    jal tramp_gun
#endif
#if FEATURE_GALLRUN || FEATURE_CHEATS
    # Pad update: jal 0x800C04D4 reading the controllers' raw data (delay slot sets a0). Gall Run
    # stage 1 takes the stick before the game decodes it (the turret and its camera stay put); Cheats'
    # Creature Cam turns the stick and B into the followed creature's D-pad.
    .word 0x8001311C
    jal tramp_padread
#endif
#if FEATURE_GALLRUN
    # The game's camera switch (0x80009648(index): firing switches to the gun's): gallrun_setcam may refuse
    # it (free flight: the gun's view is in the hull). A jump in, the delay slot (addiu a1) harmless.
    .word 0x80009648
    j tramp_setcam
    # The space level's view keys gate (lw t5, 0x2400(t5) / bnez t5, 0x80099C18: the space level's branch when its record is set):
    # open in the Gall Run's native flight too (g_sky_on). The bnez moves into the trampoline.
    .word 0x80099AC8
    jal tramp_sky_keys
    .word 0x80099ACC
    nop
    # The space level's guns gate (lw t6, 0x2400(t6): B, missiles): open with g_sky_on. The delay slot (lui t9) kept,
    # back at 0x8009BF44.
    .word 0x8009BF3C
    jal tramp_sky_guns
    # The sub-level tables' users: base g_levels (gallrun.c, 33 entries: the
    # Gall Run is 32) instead of 0x80001330, flags at +0xC4 and names at +0x148 (one entry more each). The queue's
    # bound (0x80019504 slti 0x20) stays stock (D12): gallrun_start() queues 32 itself. Each lui is followed by its %lo.
    .word 0x800192DC            # 0x80019294, the load: lui t0, 0x8000
    lui $t0, %hi(g_levels)
    .word 0x800192E8            # addiu t0, t0, 0x1330
    addiu $t0, $t0, %lo(g_levels)
    .word 0x80019300            # lw v1, 0xC0(v0): flags[id]
    lw $v1, 0xC4($v0)
    .word 0x80019314            # lw t9, 0xC0(t8): flags[LEVEL_ID]
    lw $t9, 0xC4($t8)
    .word 0x800193CC            # 0x800193A4, enter: lui t8, 0x8000
    lui $t8, %hi(g_levels + 0x40)
    .word 0x800193DC            # lw t8, 0x1370(t8): roms[id]
    lw $t8, %lo(g_levels + 0x40)($t8)
    .word 0x80019448            # lui t4, 0x8000
    lui $t4, %hi(g_levels)
    .word 0x8001944C            # addiu t4, t4, 0x1330
    addiu $t4, $t4, %lo(g_levels)
    .word 0x80019454            # addiu t3, t2, 0x140: names[id]
    addiu $t3, $t2, 0x148
    .word 0x800194A8            # 0x800194A8, the name getter: lui v1, 0x8000
    lui $v1, %hi(g_levels)
    .word 0x800194AC            # addiu v1, v1, 0x1330
    addiu $v1, $v1, %lo(g_levels)
    .word 0x800194C8            # addiu v0, v0, 0x140: names[id]
    addiu $v0, $v0, 0x148
    .word 0x8001950C            # lui t7, 0x8000
    lui $t7, %hi(g_levels)
    .word 0x80019518            # addiu t7, t7, 0x1330
    addiu $t7, $t7, %lo(g_levels)
    # The level-index table (0x800DD77C, 32 bytes; 0x80035D50: the save's current level) as g_level_index, 33 (D7).
    .word 0x80035D64            # lui v1, 0x800E
    lui $v1, %hi(g_level_index)
    .word 0x80035D74            # lbu v1, -0x2884(v1)
    lbu $v1, %lo(g_level_index)($v1)
    # The enemy shot's damage scale by level (0x800B1560: id < 14 1.0, >= 25 2.0): the Gall Run keeps the
    # base level's (D8). The delay slot (lui t0, 0x8011) runs as before.
    .word 0x800B1DB4
    j tramp_dmg_level
    # The game's restart (level state 6) re-queues LEVEL_ID through 0x800194DC, whose bound sends 32 to the Main
    # Menu: 0x800271F0's jal 0x800194DC (delay slot move a0, a1 kept) goes through tramp_level_queue (D13).
    .word 0x80027854
    jal tramp_level_queue
    # The game's level queue itself (0x800194DC(a0 = id)): from our last scene (LEVEL_ID 31 with g_chain_fin) every
    # request but 13 (the scene's own end events, its START skip: id + 1 / + 2 / 2, past the bound the Main Menu)
    # becomes 13, Cut 06. Its first instruction runs in the trampoline.
    .word 0x800194DC
    j tramp_queue_fin
    # The PRBT tower's heal: swc1 f8, 0x1A4(s0) at 0x80082494 stores
    # health + rate x frame time; in the Gall Run (LEVEL_ID 32) it is skipped. The delay slot (lh t6) runs as before.
    .word 0x80082494
    j tramp_tower_heal
#endif
    # Scene frame end, after the HUD: draw the lock-on overlay.
    .word 0x800BB864
    jal tramp_overlay
    .word 0, 0

    .text
    .globl tramp_decode, tramp_yaw, tramp_cam1, tramp_cam2, tramp_cam3, tramp_laser, tramp_shot, tramp_seeker, tramp_life, tramp_life2, tramp_overlay

# Entered by j and left by j 0x800758B0, so the game's ra survives: the Humn control keeps a button flag in ra
# (0x800754E8 and ra, t9, v1: binding +0x0A & held) and reads it after the hook (0x800759C8 beqz ra, 0x80075B2C
# beql ra). A jal left ra = 0x800758B0, nonzero, so the game always took the "back held" branch: the follow
# camera's swing 0x800E0EF4 0.6 instead of 0.8, and its sw zero, 0x800E0E10.
tramp_decode:
    SAVE
    move $a0, $s0
    move $a2, $zero             # kind 0: Humn
    jal ctl_decode
    addiu $a1, $sp, 0xD8        # game stack pointer
    RESTORE
    lui $at, 0x800E             # replaced instructions
    j 0x800758B0
    lwc1 $f8, 0x0EA0($at)

tramp_yaw:
    SAVE
    move $a0, $s0
    move $a1, $a2               # dt as float bits
    jal ctl_yaw
    move $a2, $zero             # kind 0: Humn
    RESTORE
    j 0x8000DDC4
    nop

.macro CAM_TRAMP name, target
\name:
    SAVE
    jal ctl_cam               # a0 = dolly, a1 = matrix copy (already set)
    nop
    RESTORE
    j \target
    nop
.endm

    CAM_TRAMP tramp_cam1, 0x80061774
    CAM_TRAMP tramp_cam2, 0x800611C8
    CAM_TRAMP tramp_cam3, 0x80061D60

#if FEATURE_HANG
    .globl tramp_setanim, tramp_ctrl_end, tramp_fire
# 0x80072324: bnez v0, 0x8007235C (fire), its delay slot (addiu t2, 1) runs before the jump.
# Not firing goes on at 0x8007232C (button check) as usual; hanging goes to 0x800723F8, the
# button-not-pressed path, with t8 = 0 like there. t7/t8 are scratch on all these paths.
tramp_fire:
    lui $t8, %hi(g_hang_state)
    lw $t8, %lo(g_hang_state)($t8)
    lui $t7, %hi(g_hang_drop)
    lw $t7, %lo(g_hang_drop)($t7)
    or $t8, $t8, $t7
    bnez $t8, 1f
    nop
    bnez $v0, 2f
    nop
    j 0x8007232C
    nop
2:  j 0x8007235C
    nop
1:  j 0x800723F8
    move $t8, $zero

# 0x8007A104: lw ra, 0x3C(sp), replaced; its delay slot (ldc1 f20) has already run.
tramp_ctrl_end:
    SAVE
    jal ctl_ctrl_end
    move $a0, $s0
    RESTORE
    j 0x8007A10C
    lw $ra, 0x3C($sp)

# 0x800175B8 set_anim(a0 id, a1 flags, a2 controller, a3 anim state): the C side may
# rewrite the saved a0..a3. Then the two replaced instructions and back.
tramp_setanim:
    SAVE
    jal ctl_setanim
    addiu $a0, $sp, 0x24        # saved a0..a3
    RESTORE
    addiu $sp, $sp, -0x28
    j 0x800175C0
    sw $ra, 0x24($sp)
#endif

# 0x800321FC: lw t5, 0(s1). Its delay slot (lw a1, 0x58(sp)) has already run.
# Bolt = *(0x80112E60) + s0; the shooter argument sits at sp+0x68.
tramp_laser:
    SAVE
    lw $a0, 0($s1)
    addu $a0, $a0, $s0
    jal ctl_laser
    lw $a1, (0xD8 + 0x68)($sp)
    RESTORE
    jr $ra
    lw $t5, 0($s1)

# jal 0x80064584(kind, pos, ?, vel, stack args): its delay slot has run. Aim vel, then the
# spawn itself with the caller's ra and stack.
tramp_shot:
    SAVE
    move $a0, $a1
    jal ctl_shot
    move $a1, $a3
    RESTORE
    j 0x80064584
    nop

# 0x80064604: swc1 f4, 0x8C(a0) (projectile a0, lifetime f4); its delay slot (lw t1, 0x38(v1))
# has run. ctl_life does the store.
tramp_life:
    SAVE
    jal ctl_life
    mfc1 $a1, $f4
    RESTORE
    jr $ra
    nop

# 0x800646A0: swc1 f18, 0x8C(a0), the second lifetime (kind flag 0x40); delay slot
# (andi t8, v0, 0x400) has run.
tramp_life2:
    SAVE
    jal ctl_life
    mfc1 $a1, $f18
    RESTORE
    jr $ra
    nop

# 0x8007E970: sw v0, 0x94(s4) (missile s4, auto-aim result v0); its delay slot loaded the
# shooter into t1.
tramp_seeker:
    SAVE
    move $a0, $s4
    move $a1, $v0
    jal ctl_seeker
    move $a2, $t1
    sw $v0, 0x1C($sp)
    RESTORE
    jr $ra
    sw $v0, 0x94($s4)

# 0x800BB864: jal 0x800BB630 closing the scene list (FULLSYNC/ENDDL).
tramp_overlay:
    SAVE
    jal ctl_overlay
    nop
    RESTORE
    j 0x800BB630
    nop

#if FEATURE_CHEATS
    .globl tramp_pause_in, tramp_pause_draw, tramp_hud_col
# 0x800153D4: jal 0x80026124 (returns the paused flag); the cheats run first.
tramp_pause_in:
    SAVE
    jal cheats_pause
    nop
    RESTORE
    j 0x80026124
    nop

# 0x80024854: jal 0x8001FC90 (pause screen), a0 = text context. Draw after it.
tramp_pause_draw:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1C($sp)
    jal 0x8001FC90
    sw $a0, 0x18($sp)
    jal cheats_draw
    lw $a0, 0x18($sp)
    lw $ra, 0x1C($sp)
    jr $ra
    addiu $sp, $sp, 0x20

# 0x80009138: sll t6, a0, 0x10 (replaced); the rest of the function follows at 0x8000913C.
# cheats_hud_col sees the saved a0..a3 (element id + RGB) and the alpha the caller left at
# 0x10 of its own frame, and may rewrite them before the setter runs.
tramp_hud_col:
    SAVE
    addiu $a1, $sp, 0xE8        # game sp (0xD8) + 0x10: the 5th argument, the alpha
    jal cheats_hud_col
    addiu $a0, $sp, 0x24        # saved a0..a3
    RESTORE
    j 0x8000913C
    sll $t6, $a0, 0x10
#endif

#if FEATURE_FALCON
    .globl tramp_gun
# 0x8009C790: jal 0x8000FE48(node, matrix), delay slot move a1, s0 (already run). Copy, then
# let falcon_gun move the node. Only s and even f20+ registers matter to the caller after it.
tramp_gun:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1C($sp)
    jal 0x8000FE48
    sw $a0, 0x18($sp)
    jal falcon_gun
    lw $a0, 0x18($sp)
    lw $ra, 0x1C($sp)
    jr $ra
    addiu $sp, $sp, 0x20
#endif

#if FEATURE_GALLRUN
    .globl tramp_setcam
# 0x80009648 (the camera switch, a0 the entry): gallrun_setcam(a0) nonzero: refused, else on as the game's.
tramp_setcam:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1C($sp)
    sw $a0, 0x18($sp)
    jal gallrun_setcam
    nop
    lw $a0, 0x18($sp)
    lw $ra, 0x1C($sp)
    bnez $v0, 1f
    addiu $sp, $sp, 0x20
    lui $a1, 0x800D             # the replaced instructions, then on in the game's
    j 0x80009650
    addiu $a1, $a1, 0x08A8
1:  jr $ra
    nop

    .globl tramp_sky_keys, tramp_sky_guns
# 0x80099AC8: t5 = *0x800D2400; nonzero or g_sky_on: the space level's branch 0x80099C18, else back (0x80099AD0).
tramp_sky_keys:
    lui $t5, 0x800D
    lw $t5, 0x2400($t5)
    bnez $t5, 1f
    lui $at, %hi(g_sky_on)
    lw $at, %lo(g_sky_on)($at)
    beqz $at, 2f
    nop
1:  j 0x80099C18
    nop
2:  jr $ra
    nop
# 0x8009BF3C: t6 = *0x800D2400, or 1 when g_sky_on; back at 0x8009BF44.
tramp_sky_guns:
    lui $t6, 0x800D
    lw $t6, 0x2400($t6)
    lui $at, %hi(g_sky_on)
    lw $at, %lo(g_sky_on)($at)
    beqz $at, 1f
    nop
    addiu $t6, $zero, 1
1:  jr $ra
    nop

    .globl tramp_dmg_level
# 0x800B1DB4: lh v0, LEVEL_ID (v0 = 0x80140000); the Gall Run's 32 read as 6 (the base level); back at 0x800B1DBC.
tramp_dmg_level:
    lh $v0, -0x31F2($v0)
    addiu $at, $zero, 32
    bne $v0, $at, 1f
    nop
    addiu $v0, $zero, 6
1:  j 0x800B1DBC
    nop

    .globl tramp_tower_heal
# 0x80082494 (PRBT think): swc1 f8, 0x1A4(s0), the heal's add, unless LEVEL_ID is 32; back at 0x8008249C (the jump's
# delay slot ran 0x80082498). Only t7 is used: written next at 0x8008249C (at holds 0x41F00000, live).
tramp_tower_heal:
    lui $t7, 0x8014
    lh $t7, -0x31F2($t7)
    addiu $t7, $t7, -32
    beqz $t7, 1f
    nop
    swc1 $f8, 0x1A4($s0)
1:  j 0x8008249C
    nop

    .globl tramp_level_queue
# 0x80027854 (in 0x800271F0): jal 0x800194DC(a0 = id). 32 (the Gall Run) -> gall_queue (gallrun.c), any other id ->
# the game's queue (its bound kept). Both tail calls: ra is the jal's.
tramp_level_queue:
    addiu $at, $zero, 32
    bne $a0, $at, 1f
    nop
    j gall_queue
    nop
1:  j 0x800194DC
    nop

    .globl tramp_queue_fin
# 0x800194DC, the game's level queue's entry (addiu sp, sp, -0x18 moved here; the j's delay slot, addiu at, zero, -1,
# runs again after it): LEVEL_ID 31 and g_chain_fin -> a0 = 13. Only at and v0 are used (the queue writes both before
# it reads them: at at 0x800194E0, v0 at 0x80019520).
tramp_queue_fin:
    lui $at, 0x8014
    lh $at, -0x31F2($at)        # LEVEL_ID
    addiu $at, $at, -31
    bnez $at, 1f
    lui $v0, %hi(g_chain_fin)
    lw $v0, %lo(g_chain_fin)($v0)
    beqz $v0, 1f
    nop
    addiu $a0, $zero, 13        # Cut 06
1:  addiu $sp, $sp, -0x18       # the replaced instruction
    j 0x800194E0
    nop

#endif

#if FEATURE_GALLRUN || FEATURE_CHEATS
    .globl tramp_padread
# 0x8001311C: jal 0x800C04D4(a0), then gallrun_pad and cheats_pad.
tramp_padread:
    addiu $sp, $sp, -0x20
    sw $ra, 0x1C($sp)
    jal 0x800C04D4
    nop
#if FEATURE_GALLRUN
    jal gallrun_pad
    nop
#endif
#if FEATURE_CHEATS
    jal cheats_pad
    nop
#endif
    lw $ra, 0x1C($sp)
    jr $ra
    addiu $sp, $sp, 0x20
#endif

#if FEATURE_TRAIN
    .globl tramp_decode_t, tramp_yaw_t
# 0x800AAFC0 in the HumT controller: lui at, 0x800E; lwc1 f10, 0x539C(at).
tramp_decode_t:
    SAVE
    move $a0, $s0
    ori $a2, $zero, 1           # kind 1: HumT
    jal ctl_decode
    addiu $a1, $sp, 0xD8
    RESTORE
    lui $at, 0x800E
    jr $ra
    lwc1 $f10, 0x539C($at)

# 0x800AC9E0 in the HumT controller: jal 0x8000DDC4 (yaw integration).
tramp_yaw_t:
    SAVE
    move $a0, $s0
    move $a1, $a2
    jal ctl_yaw
    ori $a2, $zero, 1
    RESTORE
    j 0x8000DDC4
    nop
#endif
