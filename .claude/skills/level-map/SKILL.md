---
name: level-map
description: Draw any level's geometry top down (world units, shaded by height) and send it. Use when the user asks for a map of a level ("map", "show the level", "where is X", "tile grid"). Works for every level that has a savestate in local/states.
model: sonnet
effort: low
allowed-tools: Bash(M64CPU=0 harness/.venv/bin/python3 harness/gallrun/level_map.py*), Bash(M64CPU=0 harness/.venv/bin/python3 harness/gallrun/gall_map.py*), Bash(ls local/states), Read, Edit, SendUserFile
---

# Level map (any level)

From the repo root:

```bash
M64CPU=0 harness/.venv/bin/python3 harness/gallrun/level_map.py "local/rom/Star Wars - Shadows of the Empire (USA) (Rev 2).z64" <state> local/demo/<state>_map.png
```

- `<state>` is a name in `local/states/` (e.g. `gall_tp5.st`, `echo_atst.st`, `sew_428.st`, `xiz_glad.st`,
  `om.st`, `sky.st`). List what is there first: `ls local/states/`.
- The script walks the world tree from `0x8013CE24`, carries the transform of the room nodes above each
  mesh, and draws every triangle in world units (the highest surface per cell, shaded by height). It is
  what the game draws, so a wall/floor shows up where the player sees it.
- A space battle (Asteroid Field, Station Chase, Skyhook) has no ground: the map is mostly empty (the ships
  and the skyhook), that is correct.
- If the level has no state yet, make one first with `M64CPU=2 harness/.venv/bin/python3 harness/mkstate.py
  "<rom>" <level> local/states/<name>.st` (level 0..9 on the carousel; see `harness/game.py` boot_events).

Before sending, open the PNG (Read) and check it is not empty and not all one colour. Labels in English;
talk to the user in Ukrainian.

Send with SendUserFile (`display: render`), one line on what is on it.

## Gall Run mission map (special case)

The old two-stage map with the route, events and times is still in `harness/gallrun/gall_map.py`:

```bash
M64CPU=0 harness/.venv/bin/python3 harness/gallrun/gall_map.py "local/rom/Star Wars - Shadows of the Empire (USA) (Rev 2).z64" local/demo/gall_run/gall_run_map.png
```

Use it only when the user asks for the Gall Run mission map specifically (route, TIEs, Dash leaving, etc.).
