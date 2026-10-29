"""Print the climb keyframe table for src/hang.c (climb_keys): python3 gen_keys.py > climb_keys.inc"""
from keys import *
import sys
LINES = [range(0, 3), range(3, 6), range(6, 9), range(9, 14), range(14, 19)]
def table(keys, names):
  P = [HANG] + keys
  out = []; prev = HANG
  for n in range(1, len(P)):
      bones = []
      for b in range(19):
          row = []
          for k in range(6):
              if HANG[b][k] is None: continue
              v = P[n][b][k] if P[n][b][k] is not None else HANG[b][k]
              if k < 3:
                  while v - prev[b][k] > 180: v -= 360
                  while v - prev[b][k] < -180: v += 360
              P[n][b][k] = v
              row.append(str(round(v * 100)))
          bones.append(', '.join(row) + ',')
      prev = P[n]
      # pose_t (int16, x 100), one line per group: see the comment on pose_t in hang.c
      rows = ['        ' + '  '.join(bones[b] for b in g) for g in LINES]
      out.append('    {   /* ' + names[n-1] + ' */\n' + '\n'.join(rows) + '\n    },')
  return '\n'.join(out)

if __name__ == '__main__':
    print(table([make_p1(), make_p2(), make_p3()], ['pull up: chin to the rim, elbows out', 'mantle: chest over the rim, arms pushing, one knee up', 'crouch on the ledge (crou frame 9, hands on knees)']))
