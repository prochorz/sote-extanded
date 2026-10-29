# SotE Extended

A fan patch for **Star Wars: Shadows of the Empire** (Nintendo 64, USA, Rev 2): modern on-foot controls, Z
lock-on, ledge grabbing, a Cheats menu in the pause screen, and a new bonus mission flown in the Millennium Falcon.

No game data is included. You need your own copy of the game, and the patch is applied to it.

## What it adds

- **New controls on foot.** Dash runs where you tilt the stick, relative to the camera. The camera follows him
  lazily from behind, stays level on stairs, and eases back behind him when he stands still.
- **Z lock-on.** Z locks the nearest enemy ahead: Dash faces it, the stick circles and strafes round it, and shots
  fly at it. Bosses lock on their weak spot. Tap Z twice quickly to move to the next target.
- **Ledge hang.** Walk off a drop and Dash grabs the edge. Stick up climbs, stick down lets go, and a jump that
  falls short catches the rim.
- **Cheats in the pause menu.** The game's own developer menu with normal controls: invincibility, any level,
  teleports, fog, gravity, and more. Plus rows of our own:
  - Jetpack Fuel;
  - Ship: Skyhook's ship variants;
  - Leebo Scanner: the top-down view;
  - Creature Cam: follow and drive a wampa, a trooper or an AT-ST;
  - Friendly Wampas.

  Reset cheats puts everything back.
- **Gall Run, a bonus mission.** Fly the Falcon through Gall's canyons behind the Outrider, then take the turret
  and fight the TIEs, with Dash, Lando and Chewie on the radio. It plays in the story on the way to Gall, and
  Cheats → Go to level starts it at any time.
- Every feature can be switched off in Cheats, which gives back the game's own behaviour.

The full description of every change is in [sote-patch/README.md](sote-patch/README.md).

## Install

1. Get your own ROM of the game: **Star Wars - Shadows of the Empire (USA) (Rev 2).z64**, big-endian `.z64`:
   - SHA-256 `e7085e013123537f34e0edec8801318016da4dbac424172d6dc5f3b67d98642c`
   - MD5 `c7b40352aad8d863d88d51672f9a0087`

   A `.n64` or `.v64` dump has to be converted to `.z64` first. The patch does not fit other versions.
2. Download `sote-extended.bps` from [Releases](../../releases).
3. Apply it to the ROM with any BPS patcher, for example Floating IPS on a desktop or Rom Patcher JS in a browser.
4. Play the patched ROM in an emulator. It is tested on M64Plus FZ (Android) and mupen64plus.

**The Expansion Pak is required** (8 MB of RAM). Emulators have it on by default. If the game stays on a black
screen, check that the emulator's "Disable Expansion Pak" option is off. Real hardware without the Expansion Pak
will not run it.

Saves carry over between versions of the patch. The patched ROM's MD5 always starts with `7dc1ece7`, and
mupen64plus-based emulators name the save after those digits.

## Controls

The buttons follow the control preset chosen in the game's Options, and the lock-on sits on the preset's
Aim/Look button. In the Standard preset:

| Button | On foot |
|---|---|
| Stick | run where it points (camera-relative) |
| Z | lock on the nearest enemy ahead; with none, aim as in the game |
| Z + stick | strafe round the target, move closer or farther |
| B | fire (at the target while locked) |
| A | jump; on a ledge, stick up climbs |
| START → Cheats | the Cheats menu: up / down pick, A runs, L / R change, B goes back |

Vehicles and ships keep the game's controls.

## Building from source

This is optional: the release patch is all you need to play. Building needs macOS with Homebrew, `llvm`, `lld`,
`mupen64plus`, and Python 3 with numpy. The parts made from the game are created locally from your own ROM, and
`local/` is git-ignored.

```bash
tools/setup.sh "<your rom>.z64"     # ~15 min, once: makes the game-derived build inputs in local/
tools/release.sh                    # builds local/rom/... [SotE Extended].z64 and local/build/sote-patch/sote-patch.bps
```

Details are in [sote-patch/README.md](sote-patch/README.md) (*Building from source*). The test bench, which runs
the game in mupen64plus from Python, is documented in [docs/harness.md](docs/harness.md). What is known about the
game's memory and code is in [docs/reverse-engineering.md](docs/reverse-engineering.md).

## Repository

| Path | What |
|---|---|
| `sote-patch/` | the patch: C and MIPS assembly injected into the game (`src/`), the build (`build.py`) |
| `harness/` | the test bench: emulator control, tests, savestates made from your ROM, the mission's asset tools |
| `tools/` | setup, release, video tools |
| `docs/` | the harness and the game's internals |
| `.claude/`, `CLAUDE.md` | instructions and skills for the AI assistant this project is developed with |

## Legal

This is an unofficial fan project. It is not affiliated with or endorsed by Lucasfilm, Disney, LucasArts or Nintendo.
Star Wars and all related names are trademarks of their owners. The repository and the release patch contain no
game code or data: the patch only works on a copy of the game you own.
