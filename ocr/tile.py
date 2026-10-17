"""
Seam-proof tiling of a page image for VLM transcription.

Two problems have to be solved at once.

1. Resolution. A line of this edition is ~3850 px wide. Every vision model
   downsamples anything wider than roughly 1536 px on its long edge, which
   drops a line of Devanagari to ~35 px tall and destroys the conjuncts.
   Measured effect: 50.8% -> 92.9% word accuracy purely from fixing this.
   So lines must be split horizontally before they reach the model.

2. Seams. Splitting a page down a single straight column boundary slices words
   in half wherever the boundary lands mid-word, and those words are then
   unrecoverable from either tile.

The fix for (2) is to cut each line at its own word gap, chosen near the
target column boundary, and then composite the resulting ragged segments into
one tall tile. No word is ever cut, no overlap is needed, and stitching a page
back together is exact: printed line k is tile_col0 line k + tile_col1 line k.

Vertical bands are cut at the midpoint between adjacent line boxes, because
tesseract's line boxes overlap (ascenders and descenders), and cropping them
literally would duplicate fragments of neighbouring lines into the tile.
"""
import argparse
import json
import os

from PIL import Image

import hocr_tools

MAX_EDGE = 1536      # keep inside the models' vision budget
LINES_PER_TILE = 12
PAD_X = 12
GUTTER = 14          # white space between composited rows
# Band height as a multiple of the measured line pitch. Tuned empirically;
# see work/band_tuning.txt for the measurements behind this value.
# Swept over 1.15/1.25/1.30/1.35/1.45/1.70 on two contrasting pages, scoring
# by agreement with the independent tesseract reading. 1.30-1.35 won clearly
# (~0.90 char agreement vs 0.63 at 1.25 and 0.75 at 1.45). Worth noting that
# the optimum sits BELOW the full glyph extent on densely set pages: clipping
# the tips of some matras costs less than letting a neighbouring line intrude.
BAND_FACTOR = float(os.environ.get("OCR_BAND_FACTOR", "1.33"))


def line_bands(page):
    """
    Vertical extent to crop for each printed line, from the measured line
    pitch rather than from tesseract's line boxes.

    Two earlier attempts failed on real pages:

      - splitting overlapping line boxes at their midpoint sliced through
        Devanagari ascenders (ि ी repha) and descenders (ु ू); the model then
        correctly reported the mutilated glyphs as illegible
      - taking each line box whole duplicated entire neighbouring lines into
        the band, because the box heights are unreliable: measured against the
        line pitch on four sample pages they ranged from 0.87x to 1.72x

    The pitch between line centres, by contrast, is stable within a page
    (~113 px on vol 1). So each band is centred on its own line and sized from
    the pitch. Centres come from the median of the word boxes, which are
    tighter than the line box and robust to one oversized glyph.
    """
    centres = []
    for l in page.lines:
        mids = sorted((w.bbox[1] + w.bbox[3]) / 2 for w in l.words)
        centres.append(mids[len(mids) // 2])

    if len(centres) > 1:
        deltas = sorted(b - a for a, b in zip(centres, centres[1:]) if b > a)
        pitch = deltas[len(deltas) // 2] if deltas else 120.0
    else:
        pitch = 120.0

    # On densely set pages the full glyph extent of a line (matras above,
    # descenders below) exceeds the pitch, so some intrusion from neighbours
    # is unavoidable. Erring generous: a visible sliver of the next line is
    # recoverable by the model, a clipped glyph of this one is not.
    half = pitch * BAND_FACTOR / 2
    return [
        (
            max(0, round(c - half)),
            min(page.bbox[3], round(c + half)),
        )
        for c in centres
    ]


# How far a cut may stray from the target column boundary to find a word gap.
# Unbounded search was a mistake: on lines whose nearest gap is far from the
# target (a long compound spanning the midpoint), the cut landed hundreds of
# pixels away, and since each line is cut independently the composite became a
# ragged staircase of wildly different widths. On the densest pages the model
# gave up on those tiles entirely and returned nothing -- 31 tiles in one
# volume. Keeping cuts near the target keeps the tile roughly rectangular.
MAX_CUT_DRIFT = 220


def cut_points(line, targets):
    """
    x positions at which to split this line, preferring a gap between words so
    no glyph is bisected, but not at the cost of a wildly ragged tile.
    """
    words = sorted(line.words, key=lambda w: w.bbox[0])
    if not words:
        return list(targets)
    gaps = []
    for a, b in zip(words, words[1:]):
        if b.bbox[0] > a.bbox[2]:
            gaps.append((a.bbox[2] + b.bbox[0]) // 2)
    cuts = []
    for t in targets:
        near = [g for g in gaps if abs(g - t) <= MAX_CUT_DRIFT]
        cuts.append(min(near, key=lambda g: abs(g - t)) if near else t)
    return cuts


def build_tiles(hocr_path, page_index, image_path, outdir, cols=2,
                lines_per=LINES_PER_TILE):
    page = hocr_tools.parse(hocr_path)[page_index]
    if not page.lines:
        return []
    im = Image.open(image_path).convert("RGB")
    sx = im.width / page.bbox[2]
    sy = im.height / page.bbox[3]

    bands = line_bands(page)
    x_min = min(w.bbox[0] for l in page.lines for w in l.words)
    x_max = max(w.bbox[2] for l in page.lines for w in l.words)
    span = x_max - x_min
    targets = [x_min + round(span * (i + 1) / cols) for i in range(cols - 1)]

    # per-line segment boundaries in hOCR x-space
    seg = []
    for l in page.lines:
        cuts = cut_points(l, targets)
        seg.append([x_min] + cuts + [x_max])

    os.makedirs(outdir, exist_ok=True)
    tiles = []
    for bi in range(0, len(page.lines), lines_per):
        idxs = list(range(bi, min(bi + lines_per, len(page.lines))))
        for ci in range(cols):
            pieces = []
            for i in idxs:
                x0 = max(0, round((seg[i][ci] - PAD_X) * sx))
                x1 = min(im.width, round((seg[i][ci + 1] + PAD_X) * sx))
                y0 = round(bands[i][0] * sy)
                y1 = round(bands[i][1] * sy)
                if x1 > x0 and y1 > y0:
                    pieces.append(im.crop((x0, y0, x1, y1)))
            if not pieces:
                continue
            W = max(p.width for p in pieces)
            H = sum(p.height for p in pieces) + GUTTER * (len(pieces) - 1)
            canvas = Image.new("RGB", (W, H), (255, 255, 255))
            y = 0
            for p in pieces:
                canvas.paste(p, (0, y))
                y += p.height + GUTTER
            long_edge = max(canvas.size)
            if long_edge > MAX_EDGE:
                f = MAX_EDGE / long_edge
                canvas = canvas.resize(
                    (max(1, round(W * f)), max(1, round(H * f))), Image.LANCZOS
                )
            name = f"b{bi // lines_per}_c{ci}.jpg"
            path = os.path.join(outdir, name)
            canvas.save(path, quality=95)
            tiles.append(
                {
                    "name": name,
                    "path": path,
                    "band": bi // lines_per,
                    "col": ci,
                    "line_indices": idxs,
                    "size": canvas.size,
                    "ocr_lines": [page.lines[i].text for i in idxs],
                }
            )
    with open(os.path.join(outdir, "tiles.json"), "w", encoding="utf-8") as f:
        json.dump(tiles, f, ensure_ascii=False, indent=1)
    return tiles


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("hocr")
    ap.add_argument("page_index", type=int)
    ap.add_argument("image")
    ap.add_argument("outdir")
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--lines", type=int, default=LINES_PER_TILE)
    a = ap.parse_args()
    ts = build_tiles(a.hocr, a.page_index, a.image, a.outdir, a.cols, a.lines)
    print(f"{len(ts)} tiles")
    for t in ts:
        print(f"  {t['name']}  {t['size'][0]}x{t['size'][1]}  "
              f"lines {t['line_indices'][0]}-{t['line_indices'][-1]}")
