#!/usr/bin/env python3
"""Draw the app icon. Generated at build time so no binary lives in the repo.
Copyright (c) 2026 Zeeshan Saleem. All rights reserved."""
import os
from PIL import Image, ImageDraw

S = 1024
im = Image.new("RGBA", (S, S), (0, 0, 0, 255))
d = ImageDraw.Draw(im)
m, w = int(S * 0.17), int(S * 0.075)
for x, top in [(0.30, 0.62), (0.46, 0.46), (0.62, 0.33), (0.78, 0.22)]:
    d.rounded_rectangle(
        [int(S * x) - w // 2, int(S * top), int(S * x) + w // 2, S - m],
        radius=w // 2, fill=(255, 255, 255, 255))
d.rounded_rectangle([m, m, S - m, S - m], radius=int(S * 0.09),
                    outline=(255, 255, 255, 255), width=int(S * 0.022))
dest = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src-tauri", "icons"))
os.makedirs(dest, exist_ok=True)
im.save(os.path.join(dest, "icon.png"))
print("icon.png 1024x1024")
