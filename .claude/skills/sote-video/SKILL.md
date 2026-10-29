---
name: sote-video
description: Make showcase videos of the SotE N64 patch (or any SotE gameplay) from the mupen64plus harness - record scripted takes with GLideN64 frames, input logs and game audio, then compose captioned 1080p/720p MP4s (side-by-side original vs patch, single-pane takes, long YouTube cuts). Use when the user asks for a demo video, a clip of a feature, or "show how it looks".
model: sonnet
effort: medium
---

# SotE showcase videos

Everything runs from `harness/` (see `docs/harness.md` for the emulator API). Video tools live in
`tools/video/`. Finished videos go to `local/demo/` and are sent to the user with SendUserFile
(`display: attach` when they want to download it on the phone).

## Rules the user set

- **Only when the user asks for a video.** Videos cost a lot of tokens: never record or compose
  one on your own initiative (not as a "demo" of a finished feature, not to verify a change;
  verify with harness screenshots and numbers instead). When the user does ask, first ask them
  what exactly the video should show (which takes, angles, length, side-by-side or not) before
  recording anything. Permission covers that one video: after a fix, a re-record or a new
  version of it needs a new "yes" (verify the fix with screenshots and offer the video).
- **All on-screen text in English** (titles, captions, input hints). Chat stays Ukrainian.
- Show the real state. If something looks off, say so next to the video instead of hiding it.
- **Debug Display on in every take** (the user's rule: easier to talk about a moment by its
  numbers). It is the Cheats entry "Debug Display": s16 `0x800DA6D0` = 2, written every frame from
  the take script: `e.w32(0x800DA6D0, (e.r32(0x800DA6D0) & 0xFFFF) | (2 << 16))`. It shows
  resolution, frame rate and the player's `pos x,y,z` (and the sector on foot) in the top left.
  It needs no debug flag.
- The user judges by eye. Before sending, extract frames from the *final mp4* and look at them
  (`ffmpeg -i out.mp4 -vf fps=2,scale=480:-1 f/%03d.png`), zoomed where it matters. Twice a
  "fixed" video was identical to the old one; only frame inspection caught it.
- Bot "free play" footage looked bad to the user (staring at walls, camera inside walls, dark
  levels, constant hit flashes). Prefer short, choreographed takes on bright levels (Echo Base,
  Suprosa) over long bot runs.

## Recording a take

A take is a harness script that drives the pad, takes a screenshot every 2nd video frame
(30 fps) and logs one JSON entry per saved frame, e.g. `{t, x, y, b, label, hang}`.

- Video plugin: `Emu(rom, video=m64.GLN)` (GLideN64 in `local/bin/`); `RES=960x720` or
  `1280x960`. GLideN64 settings must be set on every run (it persists them into the config).
- `SHOTS=<dir>` picks `local/run/shots/<dir>/`. **Max 1000 screenshots per dir** (3-digit
  names): split long recordings over several dirs.
- Start from a savestate (`load_state` at frame 60, `inject` at 62, `M64CPU=0`) so takes are
  near-deterministic: the same inputs give practically the same frames (positions can drift by
  ~0.1 between runs), which makes A/B takes (original vs patch, before vs after a fix) line up.
- Keep Dash alive by writing his health every frame: `+0xB4` (Humn, on foot), `+0xC0` (HumT,
  train). This does not stop the orange hit flash; troopers near the take still flash the
  screen. Writing their health to 0 did not remove them.
- Leave the debug flag off (its menu text shows at the top of the screen); Debug Display does not need it.
- Example: `tools/video/record_hang_takes.py` (ledge hang on `local/states/echo_crevasse.st`).
  `tools/video/record_showcase.py` records the showcase takes (move, stairs, hang, atst) with audio;
  the trooper lock-on take is `bots/demo_route.py patch` trimmed by `showcase_lock_log.py`
  (Suprosa `sup.st` troopers stand behind a wall: no lock with the real line-of-sight check).
- Compose with `harness/.venv/bin/python3` (numpy + pillow); the system python has no numpy.
- SendUserFile limit for the phone is 30 MB: send a CRF 24 copy as well.

## Audio

- Build `harness/audio_dump.dylib` (`make audio_dump.dylib`) and run with
  `AUDIOPLUGIN=$PWD/../local/bin/audio_dump.dylib`. From the script: `audio_dump_start(path)`,
  `audio_dump_pause(1/0)` (pause during cutscenes/loading you cut out), `audio_dump_stop()`,
  `audio_dump_freq()`, `audio_dump_frames()`.
- Log `aud = audio_dump_frames()` with every video frame. The emulator hands out audio in uneven
  chunks per frame, so audio is re-timed to the frames with grain overlap-add:
  `aligned_audio()` in `tools/video/make_demo_video.py` (uses the next entry's `aud` as the end
  mark; smooths the mapping over ~1 s).
- Convert the raw dump to WAV with the `wave` module (stereo, 16-bit, `audio_dump_freq()` Hz).

## Composing

- `tools/video/compose_takes.py out.mp4 "<title>" "<subtitle>" shots:log.json:"Take title" ...`
  1280x720: game 960x720 on the left, panel with take title, stick widget, status badge and
  the caption. Title / per-take / end cards.
- `tools/video/make_demo_video.py` 1920x1080 side by side (left original, right patch) with an
  input panel under each (stick + A/B/Z/R/START), stereo audio (left = original, right = patch).
- `tools/video/make_long_video.py` the ~5 min YouTube cut: comparison, then per-level gameplay
  with trimming rules (`KEEP_MAX` per label, drop "Skip message") and per-run audio segments.
- Encode: H.264 `yuv420p`, CRF 18-20, AAC 192k 48 kHz, `-movflags +faststart`, 30 fps. That is
  what YouTube wants; 1080p for uploads.

## Gotchas

- **Hangs: don't wait.** `Emu.run()` exits with code 3 and prints `HANG: no frame for N s after frame F` when
  the game stops rendering for `M64HANG` s (default 90). After a run, `grep HANG` its log; a take that "ends"
  early with no frames is a hang, not slowness. A state saved by an older build plus `inject()` of the new
  payload hangs: make a fresh state with the new build.
- When the camera swings (e.g. starting a ledge hang) the first frames are close-ups; that is
  the game camera, not a compose bug.
- Background shells can be killed silently and piping a run through `grep` buffers its output:
  write logs to a file and check the process is alive.
- `rm -rf local/run` deletes the recorded frames: compose before cleaning up.

## The SotE Extended showcase (2026-10-28): how it was made

The user's YouTube video of the whole project ("SotE Extended", 13:13). **Never delete it or its inputs**: the
videos `local/demo/sote_showcase_youtube.mp4` (1080p CRF 18), `local/demo/sote_showcase_phone.mp4` (720p),
`local/demo/sote_showcase_preview.mp4` (480p, < 28 MB for the phone); the takes `local/run/shots/vid_*` (~11+ GB) and
`local/run/video/` (manifests, logs, wavs, contact sheets). `local/demo/` and `local/run/` are git-ignored: no
`rm -rf local/run` while they live there.

Order (the user's): title card → controls, original vs patch → Z lock-on (stormtroopers, Xizor's palace
guards, the gladiator, AT-ST, then IG-88's fight, death and Level Complete running without a cut into) → the Gall Run
story, Cut 05 to Cut 06 → Cheats (only gameplay rows: Leebo Scanner, Jetpack Fuel, Ship, Creature Cam, Friendly
Wampas, Invincibility, Go to level; no fog / FOV / light / Jump Power / Debug Display) → ledge hang on Gall's cliffs →
catching the edge (Gall's start: from the post onto the parked Outrider, catch the hull, climb, take the silver
Challenge Point; then again at 0.5x) → Gall Run highlights → end card. No Debug Display in this one (the user).

Pipeline:
- Takes: `tools/video/record_b.py` (bosses, lock-on, side by side, cheats, Gall on foot, the jump; one take name
  each; `NOHIT` zeroes the hit flash and the knock-back) → `tools/video/manifest_b.py` → `manifest_B.json`. The Gall
  Run: `tools/video/record_gallrun_take.py` (the stand-in pilot: `smooth()` stick, `gunner()` aims at the nearest TIE,
  `tower_run()`; `METRICS=` + `harness/gallrun/pilot_metrics.py`) and `local/work/chain_take.py` (Cut 05, the
  hyperspace scene, Cut 06) → `manifest_C.json`. Each take checked on a contact sheet (`tools/video/contact_sheet.py`).
- Compose: `tools/video/compose_showcase.py` (`--analyze` prints the section lengths) renders all three outputs.

What the user corrected, and the rule each gave:
- Frames where the lock is off and Dash faces a wall without the target: cut (`drops` ranges, lock = 0 stretches).
- The orange hit flash: record with `NOHIT`; the gladiator needed it (and the knock-back off) to be filmable at all.
- "Slow from Cut 05 on, picture and sound": the harness VI tick is not real time in every scene (Cut 05 ~93 audio
  samples a tick against ~367 real time at 22047 Hz; the mission 220-285). The sound (AI DMA) is the real clock:
  the composer puts a take on its sound clock when it logs < 0.9 x 367 samples a tick (only speeds up; takes the
  user found right stay on the tick timeline). Text pictures hold at least 3 s.
- Whole segments silent: a segment's sound cut from a start below 0 came out empty; the composer pads instead.
- Cut 05's flight shot steps: the game moves its backdrop by whole native pixels every second shown frame; smooth on
  the phone, visible at 1440 wide; no capture setting changes it.
- The bot's first canyon flights hit the walls: a scripted pilot needs a low-pass and rate-limited stick.
