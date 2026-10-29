"""Decompile the game function that holds a RAM address to pseudo-C (Ghidra, headless).

    python3 decomp.py <addr hex> [--ram dump.bin] [-o out.c] [--fresh]

Code source, as in disasm.py: without --ram an 8 MB big-endian RDRAM image of the ROM's boot segment
(0x80000400-0x80001EC0) and local/work/main.bin (0x80001EC0); with --ram an Emu.dump() RDRAM image (level
overlays and our hooks), word-swapped to big-endian. Language MIPS:BE:32:default, base 0x80000000.

The Ghidra project is cached in work/ghidra/, one per image: `main`, or `ram_<md5[:8]>` of a dump.
The first run imports it with Ghidra's auto-analysis (minutes, once); later runs skip analysis.
--fresh deletes that project first. Ghidra: `brew install ghidra`, or set $GHIDRA_HOME.
Globals show as DAT_800dd2d0 (Ghidra's naming); no symbols are imported.
"""
import glob, hashlib, os, shutil, struct, subprocess, sys
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
ROM = os.environ.get('SOTE_ROM', paths.ROM)
MAIN_VRAM = 0x80001EC0
WORK = os.path.join(paths.WORK, 'ghidra')
SCRIPTS = os.path.join(HERE, 'ghidra')
RDRAM = 0x800000


def ghidra_headless():
    homes = [os.environ.get('GHIDRA_HOME', '')]
    homes += sorted(glob.glob('/opt/homebrew/Caskroom/ghidra/*/ghidra_*_PUBLIC'), reverse=True)
    homes.append('/opt/homebrew/opt/ghidra/libexec')
    for h in homes:
        p = os.path.join(h, 'support', 'analyzeHeadless')
        if h and os.path.isfile(p):
            return p
    print('Ghidra not found: install it with `brew install ghidra`, or set $GHIDRA_HOME '
          'to a Ghidra folder (the one with support/analyzeHeadless).', file=sys.stderr)
    sys.exit(2)


def image(ram_path):
    """(project name, big-endian 8 MB image bytes)."""
    if ram_path:
        raw = open(ram_path, 'rb').read()[:RDRAM]
        words = struct.unpack('<%dI' % (len(raw) // 4), raw)
        return 'ram_' + hashlib.md5(raw).hexdigest()[:8], struct.pack('>%dI' % len(words), *words)
    img = bytearray(RDRAM)
    boot = open(ROM, 'rb').read()[0x1000:0x1000 + MAIN_VRAM - 0x80000400]
    img[0x400:0x400 + len(boot)] = boot
    main = open(os.path.join(paths.WORK, 'main.bin'), 'rb').read()
    img[MAIN_VRAM & 0x7FFFFF:(MAIN_VRAM & 0x7FFFFF) + len(main)] = main
    return 'main', bytes(img)


def main():
    args = sys.argv[1:]
    ram = out = None
    fresh = '--fresh' in args
    if fresh:
        args.remove('--fresh')
    if '--ram' in args:
        i = args.index('--ram'); ram = args[i + 1]; del args[i:i + 2]
    if '-o' in args:
        i = args.index('-o'); out = args[i + 1]; del args[i:i + 2]
    if len(args) != 1:
        print(__doc__, file=sys.stderr); sys.exit(2)
    a = int(args[0], 16)
    if not 0x80000400 <= a < 0x80800000:
        print('address %08X outside 0x80000400..0x80800000' % a, file=sys.stderr); sys.exit(2)
    headless = ghidra_headless()
    name, img = image(ram)
    os.makedirs(WORK, exist_ok=True)
    gpr, rep = os.path.join(WORK, name + '.gpr'), os.path.join(WORK, name + '.rep')
    if fresh:
        for p in (gpr, rep):
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else (os.path.exists(p) and os.remove(p))
    prog = name + '.img'
    result = os.path.join(WORK, name + '.out.c')
    if os.path.exists(result):
        os.remove(result)
    cmd = [headless, WORK, name]
    if os.path.exists(gpr):
        cmd += ['-process', prog, '-noanalysis']
    else:
        path = os.path.join(WORK, prog)
        open(path, 'wb').write(img)
        cmd += ['-import', path, '-loader', 'BinaryLoader', '-loader-baseAddr', '0x80000000',
                '-processor', 'MIPS:BE:32:default', '-cspec', 'default']
        print('first run for %s: importing with auto-analysis (minutes, once)...' % name, file=sys.stderr)
    cmd += ['-scriptPath', SCRIPTS, '-postScript', 'Decompile.java', '%08X' % a, result,
            '-log', os.path.join(WORK, name + '.log'), '-scriptlog', os.path.join(WORK, name + '.script.log')]
    with open(os.path.join(WORK, name + '.run.log'), 'w') as log:
        rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT)
    if '-import' in cmd:
        os.remove(os.path.join(WORK, prog))  # imported into the project; not needed any more
    if not os.path.exists(result):
        print('Ghidra failed (rc %d); see %s' % (rc, os.path.join(WORK, name + '.run.log')), file=sys.stderr)
        sys.exit(1)
    c = open(result).read()
    sys.stdout.write(c)
    if out:
        open(out, 'w').write(c)


if __name__ == '__main__':
    main()
