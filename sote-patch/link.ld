/* Payload lives at the top of the 8 MB (Expansion Pak) RDRAM, well above
 * everything the game clears or allocates. Only .text and .data are in the ROM;
 * .bss follows them in RAM (NOLOAD) and _start zeroes it. */
OUTPUT_ARCH(mips)
ENTRY(_start)
SECTIONS
{
    /* Cheats (feature cheats): its code and data out of the 64 KB payload, in Expansion RAM after the Falcon model
     * (0x80500000, ~122 KB) and below .gall; build.py puts it in a fixed 32 KB ROM slot after the payload's 64 KB and
     * _start loads it. guard.c (the Look row's), guri.c and melee.c (run from cheats_frame too) are
     * built with it. Its .bss stays in the payload's. Sections in rising address order: placed after .gall, lld
     * failed ("output file too large"). */
    .cheats 0x80540000 : {
        *cheats.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
        *guard.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
        *guri.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
        *melee.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
    }
    /* The saber (feature saber): saber.c's code and data out of the 64 KB payload, in the free Expansion RAM after
     * melee.c's own RAM (ends 0x805C0000); build.py puts it in a fixed 32 KB ROM slot, the ROM's last blob, and _start
     * loads it after the cheats slot. Unlike .cheats its .bss moves out too, right after the slot (the payload's .bss
     * window had ~2 KB left and the saber's blocks hold 42 KB of it); _start and inject() zero it. */
    .saber 0x805C0000 : {
        *saber.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
    }
    .saber_bss 0x805C8000 (NOLOAD) : {
        _saber_bss_start = .;
        *saber.o(.sbss .sbss.* .bss .bss.* COMMON)
        . = ALIGN(16);
        _saber_bss_end = .;
    }
    /* Gall Run's code (feature gallrun, left out by build.py --without gallrun; the duel's duel.c and the Falcon's
     * falcon.c with it, falcon.c moved out of the payload for room): not in the 64 KB payload but in the
     * 160 KB before its image (0x80628000), loaded with it by _start. Its .bss stays below. */
    .gall 0x80600040 : {
        *gallrun.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
        *gall_*.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
        *falcon.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
        *duel.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
    }
    . = 0x807C0000;
    .text : {
        *(.text.entry)
        *(.text .text.*)
        *(.rodata .rodata.* .sdata2 .lit4 .lit8)
    }
    .data : {
        *(.data .data.* .sdata .sdata.* .got)
        . = ALIGN(16);
    }
    _payload_end = .;
    .bss (NOLOAD) : {
        _bss_start = .;
        *(.sbss .sbss.* .bss .bss.* COMMON)
        . = ALIGN(16);
        _bss_end = .;
    }
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) *(.mdebug.*) *(.note*) }
}
