/* Payload lives at the top of the 8 MB (Expansion Pak) RDRAM, well above
 * everything the game clears or allocates. Only .text and .data are in the ROM;
 * .bss follows them in RAM (NOLOAD) and _start zeroes it. */
OUTPUT_ARCH(mips)
ENTRY(_start)
SECTIONS
{
    /* Cheats (feature cheats): its code and data out of the 64 KB payload, in Expansion RAM after the Falcon model
     * (0x80500000, ~122 KB) and below .gall; build.py puts it in a fixed 32 KB ROM slot after the payload's 64 KB and
     * _start loads it. Its .bss stays in the payload's. Sections in rising address order: placed after .gall, lld
     * failed ("output file too large"). */
    .cheats 0x80540000 : {
        *cheats.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
    }
    /* Gall Run's code (feature gallrun, left out by build.py --without gallrun): not in the 64 KB payload but in the
     * 160 KB before its image (0x80628000), loaded with it by _start. Its .bss stays below. */
    .gall 0x80600040 : {
        *gallrun.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
        *gall_*.o(.text .text.* .rodata .rodata.* .sdata2 .lit4 .lit8 .data .data.* .sdata .sdata.*)
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
