"""Where the local (never published) files live: the game, data made from it, builds, run outputs, our binaries.

All of it sits under one git-ignored `local/` at the repo root (env SOTE_LOCAL moves it):
    rom/     the stock ROM, the release "[SotE Extended]" ROM, the PC ISO
    states/  savestates (console RAM)          work/   main.bin (the game's code) and one-off probes
    game/    assets made from the ROM (falcon, gall_run, gall_level*, hang.bin)
    build/   patch builds (sote-patch/ = build.py's default, others = --out dirs)
    run/     harness outputs (shots, logs, cfg, saves)   bin/   GLideN64, input_script / audio_dump dylibs
    demo/    videos
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.abspath(os.environ.get('SOTE_LOCAL') or os.path.join(ROOT, 'local'))
ROM_DIR = os.path.join(LOCAL, 'rom')
ROM = os.path.join(ROM_DIR, 'Star Wars - Shadows of the Empire (USA) (Rev 2).z64')
STATES = os.path.join(LOCAL, 'states')
WORK = os.path.join(LOCAL, 'work')
GAME = os.path.join(LOCAL, 'game')
RUN = os.path.join(LOCAL, 'run')
BIN = os.path.join(LOCAL, 'bin')
BUILD = os.path.join(LOCAL, 'build')
