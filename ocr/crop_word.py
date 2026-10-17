"""
Crop a disputed word out of a page image for human review.

This is the business end of the flagging design: when two engines disagree, or
confidence is low, the reviewer should not have to hunt the page. They get the
word itself, in context, upscaled.

    python crop_word.py <hocr> <page> <image> <outdir> --line N --word M
    python crop_word.py <hocr> <page> <image> <outdir> --near <text>
"""
import argparse
import os

from PIL import Image

import hocr_tools

UPSCALE = 3
PAD_X = 40
PAD_Y = 18


def crop(page, im, bbox, out, context=0):
    sx = im.width / page.bbox[2]
    sy = im.height / page.bbox[3]
    x0, y0, x1, y1 = bbox
    box = (
        max(0, round((x0 - PAD_X - context) * sx)),
        max(0, round((y0 - PAD_Y) * sy)),
        min(im.width, round((x1 + PAD_X + context) * sx)),
        min(im.height, round((y1 + PAD_Y) * sy)),
    )
    c = im.crop(box)
    c = c.resize((c.width * UPSCALE, c.height * UPSCALE), Image.LANCZOS)
    c.save(out, quality=96)
    return c.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hocr")
    ap.add_argument("page", type=int)
    ap.add_argument("image")
    ap.add_argument("outdir")
    ap.add_argument("--line", type=int)
    ap.add_argument("--word", type=int)
    ap.add_argument("--near", help="crop the line containing this OCR substring")
    ap.add_argument("--context", type=int, default=0)
    args = ap.parse_args()

    page = hocr_tools.parse(args.hocr)[args.page]
    im = Image.open(args.image).convert("RGB")
    os.makedirs(args.outdir, exist_ok=True)

    if args.near:
        hits = [
            (i, l) for i, l in enumerate(page.lines) if args.near in l.text
        ]
        if not hits:
            raise SystemExit(f"no line containing {args.near!r}")
        for i, l in hits:
            out = os.path.join(args.outdir, f"p{args.page:03d}_line{i:02d}.jpg")
            size = crop(page, im, l.bbox, out, args.context)
            print(f"{out}  {size[0]}x{size[1]}")
            print(f"  ocr: {l.text[:110]}")
    else:
        l = page.lines[args.line]
        if args.word is None:
            out = os.path.join(args.outdir, f"p{args.page:03d}_line{args.line:02d}.jpg")
            size = crop(page, im, l.bbox, out, args.context)
        else:
            w = l.words[args.word]
            out = os.path.join(
                args.outdir, f"p{args.page:03d}_l{args.line:02d}w{args.word:02d}.jpg"
            )
            size = crop(page, im, w.bbox, out, args.context)
            print(f"  ocr word: {w.text!r} conf={w.conf}")
        print(f"{out}  {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()
