#!/usr/bin/env python3
"""Contact sheet of a take: N frames spread evenly over its shot dirs, W px wide each, in a 3- or 4-column grid,
each frame captioned with its index (and the log's t / label when logs are given).

    contact_sheet.py <out.jpg> <shots dir>... [--n 12] [--w 480] [--log a.json --log b.json ...]
"""
import argparse, json, os
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('out'); ap.add_argument('dirs', nargs='+')
ap.add_argument('--n', type=int, default=12); ap.add_argument('--w', type=int, default=480)
ap.add_argument('--log', action='append', default=[])
a = ap.parse_args()
files = []
for d in a.dirs:
    files += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith('.png')]
ents = []
for l in a.log: ents += json.load(open(l))
n = min(a.n, len(files))
idx = [round(i * (len(files) - 1) / max(1, n - 1)) for i in range(n)]
cols = 4 if n > 9 else 3
im0 = Image.open(files[0]); h = round(a.w * im0.height / im0.width)
sheet = Image.new('RGB', (cols * a.w, ((n + cols - 1) // cols) * (h + 18)), (20, 20, 20))
dr = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
except OSError: font = ImageFont.load_default()
for j, i in enumerate(idx):
    x, y = (j % cols) * a.w, (j // cols) * (h + 18)
    sheet.paste(Image.open(files[i]).convert('RGB').resize((a.w, h)), (x, y + 18))
    cap = f'#{i}'
    if i < len(ents): cap += f"  t{ents[i].get('t')}  {ents[i].get('label') or ''}"
    dr.text((x + 4, y + 2), cap[:70], fill=(255, 255, 255), font=font)
sheet.save(a.out, quality=85)
print(a.out, len(files), 'frames')
