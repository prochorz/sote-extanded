"""Minimal scripted mupen64plus frontend: per-frame callback, scripted pad, RDRAM access.

    from m64 import Emu, BTN
    e = Emu(rom_path)                      # video: rice (default) or GLideN64 via video=GLN
    def script(e, n):                      # called once per VI, n = frame number
        e.pad(BTN['A'], x, y)              # stick x/y in -80..80
        if n == 600: e.stop()
    e.run(script)

Environment:
    M64CPU      R4300 core: 0 pure interpreter (needed for inject.py), 1 cached, 2 dynarec (default)
    M64LIMIT    1 = keep the 60 fps speed limiter (default: run as fast as possible; e.unlimit(False) does the same)
    AUDIOPLUGIN audio plugin (default: audio_dump.dylib, silent and never waits; the SDL plugin
                syncs to real time and nearly halves test speed)
    SHOTS       screenshot subdirectory of local/run/shots (mupen numbers files with 3 digits: max 1000 per dir, and per
                process: its counter does not restart in another dir; split long takes over processes)
    SHOTS_KEEP  1 = keep the PNGs already in that directory (default: a run deletes them first)
    SAVES       EEPROM subdirectory of local/run/saves, kept (default: a fresh one per run, deleted on exit, so menus look the same)
    RES         window size, default 640x480
    M64V        print all core messages (state load errors are only shown here)
    M64P_LIB    mupen64plus lib dir (default Homebrew)
    GLIDEN64    GLideN64 mupen64plus-video plugin (default: local/bin/, built from source, see docs)

Each process gets its own config dir (local/run/cfg/<pid>, deleted on exit) and temp state file, so
plugin settings saved back by one run (GLideN64 does that) never leak into the next, and runs
don't trip over each other's files.
"""
import atexit, ctypes as C, gzip, hashlib, os, shutil, struct, sys, time
import paths                          # local/ (git-ignored): run outputs, our dylibs, states

LIB = os.environ.get('M64P_LIB', '/opt/homebrew/opt/mupen64plus/lib')
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = paths.RUN
CFG = os.path.join(RUN, 'cfg', str(os.getpid()))
SHOT_LIMIT = 1000                    # mupen numbers screenshots with 3 digits
GLN = os.environ.get('GLIDEN64') or (os.path.join(paths.BIN, 'mupen64plus-video-GLideN64.dylib')
                                      if os.path.exists(os.path.join(paths.BIN, 'mupen64plus-video-GLideN64.dylib')) else '')
GLN_INT, GLN_STR = {}, {}            # Video-GLideN64 settings, set before creating Emu
for _kv in filter(None, os.environ.get('GLN_SET', '').split(',')):   # GLN_SET=Key=int,...: GLideN64 int settings from the
    GLN_INT[_kv.split('=')[0]] = int(_kv.split('=')[1])               # environment (e.g. BufferSwapMode=2)

core = C.CDLL(LIB + '/libmupen64plus.dylib')
inp = C.CDLL(paths.BIN + '/input_script.dylib')
DEBUGCB = C.CFUNCTYPE(None, C.c_void_p, C.c_int, C.c_char_p)
FRAMECB = C.CFUNCTYPE(None, C.c_uint)
VERBOSE = os.environ.get('M64V')

M64CMD_ROM_OPEN, M64CMD_EXECUTE, M64CMD_STOP = 1, 5, 6
M64CMD_STATE_LOAD, M64CMD_STATE_SAVE = 10, 11
M64CMD_SET_FRAME_CALLBACK, M64CMD_TAKE_NEXT_SCREENSHOT, M64CMD_CORE_STATE_SET = 15, 16, 17
BTN = dict(R_D=1, L_D=2, D_D=4, U_D=8, START=16, Z=32, B=64, A=128,
           CR=256, CL=512, CD=1024, CU=2048, R=4096, L=8192)


@DEBUGCB
def dbg(ctx, level, msg):
    if VERBOSE or level <= 2:
        print('[m64]', level, msg.decode(errors='replace'), flush=True)


class Emu:
    def __init__(s, rom_path, video=os.environ.get('M64VIDEO', 'rice')):
        os.makedirs(CFG, exist_ok=True)
        atexit.register(shutil.rmtree, CFG, True)
        r = core.CoreStartup(0x020001, CFG.encode(),
                             b'/opt/homebrew/opt/mupen64plus/share/mupen64plus', None, dbg, None, None)
        assert r == 0, r
        s._cfg()
        rom = open(rom_path, 'rb').read()
        s.rom_md5 = hashlib.md5(rom).hexdigest().upper().encode()
        s.rombuf = C.create_string_buffer(rom, len(rom))
        r = core.CoreDoCommand(M64CMD_ROM_OPEN, len(rom), s.rombuf)
        assert r == 0, ('rom', r)
        vpath = video if video.startswith('/') else f'{LIB}/mupen64plus/mupen64plus-video-{video}.dylib'
        dump = os.path.join(paths.BIN, 'audio_dump.dylib')
        audio = os.environ.get('AUDIOPLUGIN') or (dump if os.path.exists(dump) else f'{LIB}/mupen64plus/mupen64plus-audio-sdl.dylib')
        for kind, path in ((2, vpath), (3, audio), (4, paths.BIN + '/input_script.dylib'),
                           (1, f'{LIB}/mupen64plus/mupen64plus-rsp-hle.dylib')):
            plug = C.CDLL(path)
            plug.PluginStartup(C.c_void_p(core._handle), None, dbg)
            r = core.CoreAttachPlugin(kind, C.c_void_p(plug._handle))
            assert r == 0, (path, r)
        core.DebugMemGetPointer.restype = C.c_void_p
        s.rdram_ptr = None
        s.frame = 0
        s.running = False
        s._saves = []
        s.unlimited = not os.environ.get('M64LIMIT')

    def _cfg(s):
        h = C.c_void_p()
        def sec(n): core.ConfigOpenSection(n.encode(), C.byref(h)); return h.value
        def seti(sc, k, v): x = C.c_int(v); core.ConfigSetParameter(C.c_void_p(sc), k.encode(), 1, C.byref(x))
        def sets(sc, k, v): core.ConfigSetParameter(C.c_void_p(sc), k.encode(), 4, C.c_char_p(v.encode()))
        def sub(*p):
            d = os.path.join(RUN, *p); os.makedirs(d, exist_ok=True); return d + '/'
        c = sec('Core')
        seti(c, 'R4300Emulator', int(os.environ.get('M64CPU', '2')))
        seti(c, 'DisableExtraMem', 0)                     # Expansion Pak: the patch needs 8 MB
        s.shot_dir = sub('shots', os.environ.get('SHOTS', 'misc'))
        if not os.environ.get('SHOTS_KEEP'):             # a run starts its SHOTS dir afresh (old shots piled up to GBs)
            for f in os.listdir(s.shot_dir):
                if f.endswith('.png'): os.remove(s.shot_dir + f)
        s.shots = len(os.listdir(s.shot_dir))
        sets(c, 'ScreenshotPath', s.shot_dir)
        sets(c, 'SaveStatePath', sub('states'))
        saves = os.environ.get('SAVES')
        sets(c, 'SaveSRAMPath', sub('saves', saves) if saves else sub('cfg', str(os.getpid()), 'saves'))
        w, hh = (int(x) for x in os.environ.get('RES', '640x480').split('x'))
        v = sec('Video-General'); seti(v, 'Fullscreen', 0); seti(v, 'ScreenWidth', w); seti(v, 'ScreenHeight', hh)
        seti(sec('Audio-SDL'), 'VOLUME_DEFAULT', 0)
        # Fresh config dir per process, so only these settings and the plugin defaults apply.
        g = sec('Video-GLideN64')
        for k, val in GLN_INT.items(): seti(g, k, val)
        for k, val in GLN_STR.items(): sets(g, k, val)

    # --- memory (RDRAM is stored as host-endian 32-bit words) ---
    def rdram(s):
        if not s.rdram_ptr: s.rdram_ptr = core.DebugMemGetPointer(1)
        return s.rdram_ptr
    def r32(s, a): return C.c_uint32.from_address(s.rdram() + (a & 0x7FFFFC)).value
    def w32(s, a, v): C.c_uint32.from_address(s.rdram() + (a & 0x7FFFFC)).value = v & 0xFFFFFFFF
    def r16(s, a):
        w = s.r32(a & ~3); return (w >> 16) & 0xFFFF if (a & 2) == 0 else w & 0xFFFF
    def rf(s, a): return struct.unpack('<f', struct.pack('<I', s.r32(a)))[0]
    def wf(s, a, v): s.w32(a, struct.unpack('<I', struct.pack('<f', v))[0])
    def dump(s, path): open(path, 'wb').write(C.string_at(s.rdram(), 0x800000))   # little-endian words

    # --- control ---
    def pad(s, buttons=0, x=0, y=0):
        inp.set_input(C.c_uint((buttons & 0xFFFF) | ((x & 0xFF) << 16) | ((y & 0xFF) << 24)))
    def unlimit(s, on=True):
        """Speed limiter off (on=True) or back on. Before run() it applies from the first frame."""
        s.unlimited = on
        if s.running:
            v = C.c_int(0 if on else 1); core.CoreDoCommand(M64CMD_CORE_STATE_SET, 5, C.byref(v))
    def shot(s):
        if s.shots == SHOT_LIMIT:
            print(f'[m64] WARNING: {s.shot_dir} has {SHOT_LIMIT} shots; mupen drops the rest (use another SHOTS dir)',
                  file=sys.stderr, flush=True)
        s.shots += 1
        core.CoreDoCommand(M64CMD_TAKE_NEXT_SCREENSHOT, 0, None)
    def stop(s): core.CoreDoCommand(M64CMD_STOP, 0, None)
    def save_state(s, path):
        """Save a state (written by a core worker thread; run() waits for it before returning)."""
        path = os.path.abspath(path)
        s._saves.append((path, os.path.getmtime(path) if os.path.exists(path) else 0))
        core.CoreDoCommand(M64CMD_STATE_SAVE, 1, C.c_char_p(path.encode()))

    def _wait_saves(s, timeout=15):
        # Unthrottled, a script's stop() a few frames after save_state() arrives long before the
        # worker has written the file; leaving then would cut it off.
        for path, old in s._saves:
            t0 = time.time()
            while time.time() - t0 < timeout:
                try:
                    if os.path.getmtime(path) > old:
                        d = open(path, 'rb').read()
                        if (gzip.decompress(d) if d[:2] == b'\x1f\x8b' else d)[:8] == b'M64+SAVE':
                            break
                except (OSError, EOFError, gzip.BadGzipFile):
                    pass
                time.sleep(0.1)
            else:
                print(f'[m64] WARNING: state {path} was not written completely', file=sys.stderr, flush=True)
        s._saves = []

    def load_state(s, path):
        """Load a mupen64plus state even if it was saved with another build of the ROM.

        The core silently refuses states whose stored ROM MD5 differs, and every patch
        rebuild changes the MD5, so the MD5 is rewritten in a temporary copy. Loading
        takes effect on the next frame; call inject.inject() a frame or two later."""
        d = open(path, 'rb').read()
        gz = d[:2] == b'\x1f\x8b'
        if gz: d = gzip.decompress(d)
        assert d[:8] == b'M64+SAVE', path
        d = d[:12] + s.rom_md5 + d[44:]
        tmp = os.path.join(CFG, '_load.st')
        open(tmp, 'wb').write(gzip.compress(d) if gz else d)
        core.CoreDoCommand(M64CMD_STATE_LOAD, 0, C.c_char_p(tmp.encode()))

    def hang_pc(s, n=200):
        # M64PC=1 (with M64CPU=0): where the hung CPU is. The core has no debugger (DebugGetState: not supported), but
        # DebugGetCPUDataPtr still points at the CPU's fields: 1 the PC (u32), 2 the GPRs (s64 x 32), 5 COP0 (u32 x 32:
        # 8 BadVAddr, 13 Cause, 14 EPC). Read from this thread while the game loops: the PCs seen, ra, the exception.
        core.DebugGetCPUDataPtr.restype = C.c_void_p
        pc_p, gpr_p, cp0_p = (core.DebugGetCPUDataPtr(k) for k in (1, 2, 5))
        if not pc_p or pc_p < 0x1000:
            print('HANG PC: no pointer', pc_p, flush=True); return
        seen = {}
        for _ in range(n):
            pc = C.c_uint32.from_address(pc_p).value
            seen[pc] = seen.get(pc, 0) + 1
            time.sleep(0.01)
        print('HANG PC:', ' '.join(f'{p:08x}x{c}' for p, c in sorted(seen.items(), key=lambda x: -x[1])[:24]), flush=True)
        if gpr_p:
            g = (C.c_int64 * 32).from_address(gpr_p)
            print('HANG GPR:', ' '.join(f'r{i}={g[i] & 0xFFFFFFFF:08x}' for i in range(32)), flush=True)
        if cp0_p:
            c0 = (C.c_uint32 * 32).from_address(cp0_p)
            print(f'HANG COP0: BadVAddr={c0[8]:08x} Cause={c0[13]:08x} EPC={c0[14]:08x} Status={c0[12]:08x}', flush=True)
        out = os.path.join(RUN, f'hang_ram_{os.getpid()}.bin')   # (a faulted game thread's context is in RAM: OSThread
        s.dump(out); print('HANG RAM:', out, flush=True)          # +0x11C pc, +0x120 cause, +0x124 badvaddr)

    def run(s, script):
        # Watchdog: a game that hangs (a crash in the patch: the CPU stuck) renders no more frames and the core
        # never returns, so the run would wait forever. No frame for M64HANG seconds (default 90: loading another level's state takes ~30; 0: off): the
        # process says so ("HANG: ...") and exits with 3.
        hang = float(os.environ.get('M64HANG', 90))
        # Hard limits (a run whose script waits for a game frame count that never comes: a held line or the mission's
        # end stops the game's frames while the VIs go on, and M64HANG never fires): M64MAXVI VIs (default 36000, ~10 min
        # of game at 60) end the run by stop(); M64MAXSEC seconds of wall clock (default 1500) exit the process with 4.
        # 0: off (long builds, e.g. the Gall Run image, pass M64MAXSEC=0 with M64HANG=0).
        s._maxvi = int(os.environ.get('M64MAXVI', 36000))
        maxsec = float(os.environ.get('M64MAXSEC', 1500))
        if maxsec > 0:
            import threading
            t0 = time.monotonic()
            def cap():
                while True:
                    time.sleep(5)
                    if time.monotonic() - t0 > maxsec:
                        print(f'LIMIT: {maxsec:.0f} s of wall clock at frame {s.frame} (M64MAXSEC)', flush=True)
                        sys.stderr.write(f'LIMIT: {maxsec:.0f} s at frame {s.frame}\n'); sys.stderr.flush()
                        os._exit(4)
            threading.Thread(target=cap, daemon=True).start()
        s._last = None
        if hang > 0:
            import threading
            def watch():
                while True:
                    time.sleep(1)
                    if s._last is not None and time.monotonic() - s._last > hang:
                        print(f'HANG: no frame for {hang:.0f} s after frame {s.frame}', flush=True)
                        sys.stderr.write(f'HANG: no frame for {hang:.0f} s after frame {s.frame}\n'); sys.stderr.flush()
                        if os.environ.get('M64PC'): s.hang_pc()
                        os._exit(3)
            threading.Thread(target=watch, daemon=True).start()

        @FRAMECB
        def cb(n):
            s._last = time.monotonic()
            s.frame = n
            if s._maxvi and n > s._maxvi:
                if n == s._maxvi + 1: print(f'LIMIT: {s._maxvi} VIs (M64MAXVI): stopped', flush=True)
                s.stop(); return
            if not s.running:
                s.running = True
                s.unlimit(s.unlimited)
            try:
                script(s, n)
            except Exception:
                import traceback; traceback.print_exc(); s.stop()
        s._cb = cb
        core.CoreDoCommand(M64CMD_SET_FRAME_CALLBACK, 0, C.cast(cb, C.c_void_p))
        core.CoreDoCommand(M64CMD_EXECUTE, 0, None)
        s._wait_saves()


def tag(v):
    """Object class tag ('Humn', 'HumT', 'Stor', ...) from its first word."""
    return struct.pack('>I', v).decode('latin1')
