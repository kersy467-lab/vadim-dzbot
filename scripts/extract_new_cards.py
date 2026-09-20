"""
Extracts 36 playing cards (6..10, J, Q, K, A for hearts, diamonds, clubs, spades)
from complete-deck-playing-cards.zip into frontend/img/cards/
"""
import zipfile
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw

ZIP_PATH = r"C:\Users\Админ\Downloads\complete-deck-playing-cards.zip"
OUT_DIR = "frontend/img/cards"
os.makedirs(OUT_DIR, exist_ok=True)

z = zipfile.ZipFile(ZIP_PATH)
im_bgr = cv2.imdecode(np.frombuffer(z.read("8c99b7ab-74f5-4689-803a-180d0dae4ca5.jpg"), np.uint8), cv2.IMREAD_COLOR)
gray = cv2.cvtColor(im_bgr, cv2.COLOR_BGR2GRAY)

edges = cv2.Canny(gray, 50, 150)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
edges_dil = cv2.dilate(edges, kernel)
contours, _ = cv2.findContours(edges_dil, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

card_rects = []
for c in contours:
    x, y, w, h = cv2.boundingRect(c)
    if 375 <= w <= 390 and 525 <= h <= 540:
        card_rects.append((x, y, w, h))

# Deduplicate
unique_rects = []
for r in sorted(card_rects, key=lambda b: (b[1], b[0])):
    if not any(abs(r[0] - u[0]) < 15 and abs(r[1] - u[1]) < 15 for u in unique_rects):
        unique_rects.append(r)

assert len(unique_rects) == 60, f"Expected 60 cards, found {len(unique_rects)}"

hearts = []
diamonds = []
clubs = []
spades = []

for r in unique_rects:
    x, y, w, h = r
    if y < 2400: # Top half
        if x < 2600:
            hearts.append(r)
        else:
            diamonds.append(r)
    else: # Bottom half
        if x < 2600:
            clubs.append(r)
        else:
            spades.append(r)

def organize_block(block_rects):
    block_rects.sort(key=lambda r: r[1])
    row0 = sorted(block_rects[0:5], key=lambda r: r[0])
    row1 = sorted(block_rects[5:10], key=lambda r: r[0])
    row2 = sorted(block_rects[10:15], key=lambda r: r[0])
    return [row0, row1, row2]

blocks = {
    "hearts": organize_block(hearts),
    "diamonds": organize_block(diamonds),
    "clubs": organize_block(clubs),
    "spades": organize_block(spades),
}

# Mapping of rank to (row, col)
# Only 9 ranks per suit: 6..10, J, Q, K, A = 36 cards
RANK_COORDS = {
    "A": (0, 0),
    "6": (1, 0),
    "7": (1, 1),
    "8": (1, 2),
    "9": (1, 3),
    "10": (1, 4),
    "J": (2, 0),
    "Q": (2, 1),
    "K": (2, 2)
}

im_rgb = cv2.cvtColor(im_bgr, cv2.COLOR_BGR2RGB)
im_pil = Image.fromarray(im_rgb)

extracted_count = 0

for suit_name, grid in blocks.items():
    for rank, (r_idx, c_idx) in RANK_COORDS.items():
        x, y, w, h = grid[r_idx][c_idx]
        # Inward crop 2 pixels to cleanly omit outer sheet shadow
        card_crop = im_pil.crop((x + 2, y + 2, x + w - 2, y + h - 2))
        cw, ch = card_crop.size

        # Create rounded rectangle alpha mask
        mask = Image.new("L", (cw, ch), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=22, fill=255)

        card_rgba = card_crop.convert("RGBA")
        card_rgba.putalpha(mask)

        # 1. Save crisp PNG
        png_path = os.path.join(OUT_DIR, f"{rank}_{suit_name}.png")
        card_rgba.save(png_path, format="PNG", optimize=True)

        # 2. Save SVG wrapper for 100% compatibility
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cw} {ch}" width="100%" height="100%">
  <image href="/static/img/cards/{rank}_{suit_name}.png" width="{cw}" height="{ch}" />
</svg>
"""
        svg_path = os.path.join(OUT_DIR, f"{rank}_{suit_name}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        extracted_count += 1

print(f"Successfully generated {extracted_count} cards (PNG + SVG) in {OUT_DIR}!")
