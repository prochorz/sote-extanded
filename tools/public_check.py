#!/usr/bin/env python3
"""Check the files that go public (tracked, plus untracked ones not ignored) for what must stay local.

    python3 tools/public_check.py

The word lists are read from local/docs/public_words.json (git-ignored). Hits (case as noted):
  - the names of the levels the Gall Run is built from (LEVELS, any case): allowed only in the files of ALLOW (the
    tests, the features and tools on the game's own levels, the sote-bot carousel), never in a Gall Run file; in an
    ALLOW file still a hit when its block (a Markdown paragraph or list item, else the line)
    speaks of the Gall Run (GALL);
  - other projects' names (OTHER; the one allowed: the thanks line in sote-patch/README.md; the game's own lines and
    the plain words stay);
  - pointers to the local docs (local/docs/: the Gall Run's docs, git-ignored): none in code, tools or public docs;
    in CLAUDE.md and .claude/ only as a `local/docs/...` path.
One line a hit (file:line: what: the text round it), then a summary; exit 1 on any hit. Run before a push.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# The words live in a local file (git-ignored, next to the local docs): {"levels": {name: regex}, "other": {name:
# regex}, "thanks": the text of the one line allowed to name another project}.
WORDS = os.path.join(ROOT, 'local', 'docs', 'public_words.json')
if not os.path.exists(WORDS):
    sys.exit(f'no {WORDS}: nothing to check against')
_W = json.load(open(WORDS))
LEVELS = _W['levels']
OTHER = _W['other']
DOC_NAMES = r'(?:decisions|gall-run|gall-chain|own-level|cut05-frames|gallrun-tools|gall-facts)\.md'
DOCS = r'docs/implementation|gallrun/README|(?<![\w/-])(?:local/docs/)?' + DOC_NAMES
THANKS = _W['thanks']

GALL = r'gall[- ]?run|gallrun|gall_(?!tp\d|6b|dash|boot)\w|LEVEL_GALL|bonus mission|the mission|stage [12]\b|falcon_asset|src_[a-z]+\.st'
SELF = 'tools/public_check.py'

# Files not about the Gall Run, where the game's own level names stay: a prefix (dir/) or a file, and the names
_GAME = set(LEVELS)
ALLOW = {
    'harness/tests/': _GAME, 'harness/bots/': _GAME, 'harness/pose/': _GAME,
    'harness/game.py': _GAME, 'harness/debugmenu.py': _GAME, 'harness/states_make.py': _GAME,
    'harness/tpstate.py': _GAME, 'harness/steer_probe.py': _GAME, 'harness/states_cmp.py': _GAME,
    'harness/run_all.py': _GAME, 'harness/m64.py': _GAME, 'harness/inject.py': _GAME, 'harness/testlib.py': _GAME,
    'harness/gallrun/level_map.py': _GAME,                # any level's map (skill level-map)
    'tools/video/': _GAME, 'tools/video/record_gallrun_take.py': set(), 'tools/video/compose_gallrun.py': set(),
    '.claude/skills/sote-bot/SKILL.md': _GAME, '.claude/skills/level-map/SKILL.md': _GAME,
    '.claude/skills/sote-video/SKILL.md': _GAME, '.claude/skills/sote-test/SKILL.md': _GAME,
    'docs/harness.md': _GAME, 'docs/reverse-engineering.md': _GAME,
    'sote-patch/docs/': _GAME, 'sote-patch/src/hang.c': _GAME, 'sote-patch/src/lock.c': _GAME,
    'sote-patch/src/train.c': _GAME, 'sote-patch/src/core.c': _GAME, 'sote-patch/src/cheats.c': _GAME,
    'sote-patch/src/game.h': _GAME, 'sote-patch/src/common.h': _GAME,
    'sote-patch/README.md': _GAME, 'CLAUDE.md': _GAME, 'README.md': _GAME,
}


def allowed(path):
    """The level names allowed in a file: its own entry, else the longest prefix's."""
    if path in ALLOW: return ALLOW[path]
    best = max((p for p in ALLOW if p.endswith('/') and path.startswith(p)), key=len, default=None)
    return ALLOW[best] if best else set()


def files():
    out = []
    for args in (['ls-files'], ['ls-files', '--others', '--exclude-standard']):
        out += subprocess.run(['git', '-C', ROOT] + args, capture_output=True, text=True, check=True).stdout.split('\n')
    return sorted({f for f in out if f and os.path.isfile(os.path.join(ROOT, f))})


def blocks(lines, md):
    """Per line, the text of its block: a Markdown paragraph or list item (md), else the line itself."""
    if not md: return lines
    out, start = [], 0
    for i in range(len(lines) + 1):
        if i == len(lines) or not lines[i].strip() or (i > start and re.match(r'\s*(?:[-*|#]|\d+\.)\s', lines[i])):
            out += ['\n'.join(lines[start:i])] * (i - start)
            start = i + (i < len(lines) and not lines[i].strip())
            if i < len(lines) and not lines[i].strip(): out.append('')
    return out


def check(path):
    if path == SELF: return []
    raw = open(os.path.join(ROOT, path), 'rb').read()
    if b'\0' in raw[:8192]: return []                    # binary
    ok_levels = allowed(path)
    agent_doc = path == 'CLAUDE.md' or path.startswith('.claude/')
    lines = raw.decode('utf-8', 'replace').split('\n')
    blk = blocks(lines, path.endswith('.md')) if ok_levels else None
    hits = []
    for n, line in enumerate(lines, 1):
        for name, pat in LEVELS.items():
            for m in re.finditer(pat, line, re.I):
                if name not in ok_levels: hits.append((n, name, line, m))
                elif re.search(GALL, blk[n - 1], re.I): hits.append((n, name + ' (by the Gall Run)', line, m))
        for name, pat in OTHER.items():
            for m in re.finditer(pat, line):
                if not (path == 'sote-patch/README.md' and THANKS in line):
                    hits.append((n, name, line, m))
        for m in re.finditer(DOCS, line):
            if not (agent_doc and m.group(0).startswith('local/docs/')):
                hits.append((n, 'local doc', line, m))
    return [(path, n, name, line[max(0, m.start() - 50):m.end() + 50].strip()) for n, name, line, m in hits]


def main():
    hits = [h for f in files() for h in check(f)]
    for path, n, name, txt in hits:
        print(f'{path}:{n}: {name}: {txt}')
    print(f'{len(hits)} hits in {len({h[0] for h in hits})} files' if hits else 'OK: no hits')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
