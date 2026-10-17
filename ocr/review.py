"""
Build the manual-review queue.

The point of the pipeline is not to be perfect, it is to be *honest*: every
place the transcription is not trustworthy should be findable. This module
recomputes the review decision from the stored per-line evidence (so it can be
retuned without re-running any inference), crops the corresponding line out of
the page scan, and writes an HTML page where each item shows the scan, the new
transcription, and the old tesseract reading side by side.

Why the decision is recomputed here
-----------------------------------
The first flag rule leaned on disagreement with tesseract. On the front matter
and title pages tesseract produces near-garbage, so "disagreement" fired on
essentially every line and buried the real problems. Disagreement is only
evidence when the other engine was itself confident, so that is now required.

Ranked worst-first, because review time is finite and should be spent where
the risk is highest.
"""
import argparse
import glob
import json
import os
import re

import hocr_tools
import pageimg

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "work", "pages")
CROPS = os.path.join(HERE, "..", "docs", "review", "crops")
OUT = os.path.join(HERE, "..", "docs", "review.html")

UNCLEAR = "⟨?⟩"
LATIN = re.compile(r"[A-Za-z]{2,}")
ASCII_ARTEFACT = re.compile(r"[:|]")
FOLIO_OFFSET = {1: -10, 2: +90, 3: +190}


def folio(vol, scan):
    f = scan + FOLIO_OFFSET[vol]
    return f if f >= 1 else None


def assess(text, fl):
    """
    Decide whether a line needs human eyes, and why. Returns (score, reasons).
    Higher score = review sooner.
    """
    reasons = []
    score = 0.0

    n_unc = text.count(UNCLEAR) or fl.get("uncertain_marks", 0)
    if n_unc:
        score += 10 + 2 * n_unc
        reasons.append(f"{n_unc} illegible spot(s) reported by the model")

    if fl.get("stitch_suspect"):
        score += 8
        reasons.append("tile returned an unexpected line count; alignment suspect")

    cagree = fl.get("tesseract_char_agree", 1.0)
    tconf = fl.get("tesseract_mean_conf", 0.0)
    # Disagreement only counts as evidence when the other engine was confident.
    if cagree < 0.45 and tconf >= 60:
        score += 6
        reasons.append(
            f"disagrees sharply with the confident tesseract reading "
            f"(agreement {cagree:.2f}, its confidence {tconf:.0f})"
        )
    elif cagree < 0.65 and tconf >= 70:
        score += 3
        reasons.append(
            f"differs from a high-confidence tesseract reading "
            f"(agreement {cagree:.2f}, its confidence {tconf:.0f})"
        )

    # Latin script is a red flag in the body text, where it usually means the
    # model leaked a comment. On the title and imprint pages it is simply
    # what is printed ("Printed and published by..."), so it is not evidence
    # there.
    if LATIN.search(text) and not fl.get("latin_expected"):
        score += 5
        reasons.append("contains Latin text, which should not appear here")

    if ASCII_ARTEFACT.search(text):
        score += 1
        reasons.append("contains an ASCII lookalike for visarga or danda")

    if not text.strip():
        score += 7
        reasons.append("line came back empty")

    return score, reasons


def collect():
    items = []
    stats = {"pages": 0, "lines": 0, "flagged": 0}
    for p in sorted(glob.glob(os.path.join(PAGES, "*.json"))):
        r = json.load(open(p, encoding="utf-8"))
        if r.get("empty"):
            continue
        stats["pages"] += 1
        flags = r.get("flags", [])
        # Volume 1 opens with covers, a title page and contents, which carry
        # the publisher's English imprint.
        latin_ok = r["vol"] == 1 and r["scan"] <= 13
        for i, text in enumerate(r["lines"]):
            stats["lines"] += 1
            fl = dict(flags[i]) if i < len(flags) else {}
            fl["latin_expected"] = latin_ok
            sc, reasons = assess(text, fl)
            if sc <= 0:
                continue
            stats["flagged"] += 1
            items.append(
                {
                    "vol": r["vol"],
                    "scan": r["scan"],
                    "folio": folio(r["vol"], r["scan"]),
                    "line": i,
                    "text": text,
                    "score": sc,
                    "reasons": reasons,
                    "tesseract_conf": fl.get("tesseract_mean_conf"),
                }
            )
    items.sort(key=lambda d: (-d["score"], d["vol"], d["scan"], d["line"]))
    return items, stats


def make_crops(items, limit):
    """Crop the scan for each reviewable line so it can be checked by eye."""
    os.makedirs(CROPS, exist_ok=True)
    hocr_cache = {}
    made = 0
    for it in items[:limit]:
        vol, scan, li = it["vol"], it["scan"], it["line"]
        name = f"v{vol}_{scan:04d}_l{li:02d}.jpg"
        dest = os.path.join(CROPS, name)
        it["crop"] = f"review/crops/{name}"
        if os.path.exists(dest):
            continue
        if vol not in hocr_cache:
            hocr_cache[vol] = hocr_tools.parse(
                os.path.join(HERE, "source", f"v{vol}_hocr.html")
            )
        page = hocr_cache[vol][scan]
        if li >= len(page.lines):
            it["crop"] = None
            continue
        line = page.lines[li]
        im = pageimg.page_image(vol, scan)
        sx = im.width / page.bbox[2]
        sy = im.height / page.bbox[3]
        x0, y0, x1, y1 = line.bbox
        box = (
            max(0, int((x0 - 20) * sx)),
            max(0, int((y0 - 10) * sy)),
            min(im.width, int((x1 + 20) * sx)),
            min(im.height, int((y1 + 10) * sy)),
        )
        crop = im.crop(box)
        # keep it readable in a browser without being enormous
        if crop.width > 1600:
            f = 1600 / crop.width
            crop = crop.resize((1600, max(1, int(crop.height * f))))
        crop.save(dest, quality=90)
        made += 1
    return made


PAGE_TMPL = """<!DOCTYPE html>
<html lang="en"><head>
<title>परिशोधनम् — review queue</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<link rel="shortcut icon" type="image/png" href="images/favicon.png">
<link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="css/main.css" type="text/css"/>
<style>
  body {{ background-attachment: fixed; }}
  .content {{ max-width: 1150px; margin: 0 auto; }}
  .item {{ background: rgba(0,0,0,.30); border-radius: 7px;
          padding: 14px 18px; margin-bottom: 20px; }}
  .item img {{ width: 100%; height: auto; max-width: 100%;
              border-radius: 4px; background: #fff; }}
  .tx {{ font-size: 1.2em; line-height: 1.9; margin: 10px 0; }}
  .meta {{ color: #ffc100; font-size: .82em; letter-spacing: .04em; }}
  .why {{ color: #ffd9a0; font-size: .86em; margin: 4px 0 10px; }}
  .why li {{ margin-bottom: 2px; }}
  .ocr {{ color: #b9b9b9; font-size: .92em; font-style: italic; }}
  .lbl {{ color: #8fd3ff; font-size: .78em; text-transform: uppercase;
         letter-spacing: .08em; }}
  .summary {{ background: rgba(0,0,0,.35); padding: 16px 20px;
             border-radius: 7px; margin-bottom: 26px; }}
  .unclear {{ color:#ffdd57; background:rgba(0,0,0,.45);
             border-bottom:2px dotted #ffdd57; padding:0 3px;
             border-radius:3px; font-weight:700; }}
</style>
</head><body>
<div class="content noto-sans-regular">
<p class="section-title halant-regular">परिशोधनम्</p>
<div class="summary">
  <p>{summary}</p>
  <p class="meta">Worst first. Each entry shows the scan, the new reading, and
  the old tesseract reading for comparison. Correct the text in the XML under
  <code>sanitized_auto/</code>, or move a finished file into
  <code>sanitized/</code> to take it out of the generated set.</p>
</div>
{items}
</div></body></html>
"""

ITEM_TMPL = """<div class="item">
  <div class="meta">{loc} &nbsp;·&nbsp; severity {score:.0f}</div>
  <ul class="why">{reasons}</ul>
  {img}
  <div class="lbl">transcription</div>
  <div class="tx laila-regular">{text}</div>
  <div class="lbl">tesseract (for comparison)</div>
  <div class="ocr">{ocr}</div>
</div>
"""


def render(items, stats, limit):
    hocr_cache = {}
    blocks = []
    for it in items[:limit]:
        vol, scan, li = it["vol"], it["scan"], it["line"]
        if vol not in hocr_cache:
            hocr_cache[vol] = hocr_tools.parse(
                os.path.join(HERE, "source", f"v{vol}_hocr.html")
            )
        page = hocr_cache[vol][scan]
        ocr = page.lines[li].text if li < len(page.lines) else ""
        loc = (
            f"folio {it['folio']}" if it["folio"] else "front matter"
        ) + f" &nbsp;(vol {vol}, scan {scan}, line {li})"
        text = (
            it["text"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(UNCLEAR, '<span class="unclear">&#10216;?&#10217;</span>')
        )
        img = (
            f'<img src="{it["crop"]}" alt="scan of this line" loading="lazy">'
            if it.get("crop")
            else "<p class='ocr'>(no crop available)</p>"
        )
        blocks.append(
            ITEM_TMPL.format(
                loc=loc,
                score=it["score"],
                reasons="".join(f"<li>{r}</li>" for r in it["reasons"]),
                img=img,
                text=text,
                ocr=ocr.replace("&", "&amp;").replace("<", "&lt;") or "&mdash;",
            )
        )
    pct = 100 * stats["flagged"] / max(stats["lines"], 1)
    summary = (
        f"{stats['flagged']} of {stats['lines']} transcribed lines across "
        f"{stats['pages']} pages need a look &mdash; {pct:.1f}%. "
        f"Showing the {min(limit, len(items))} most severe."
    )
    html = PAGE_TMPL.format(summary=summary, items="\n".join(blocks))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    return OUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400,
                    help="how many items to crop and render")
    a = ap.parse_args()
    items, stats = collect()
    n = make_crops(items, a.limit)
    out = render(items, stats, a.limit)
    with open(os.path.join(HERE, "work", "review_queue.json"), "w",
              encoding="utf-8") as f:
        json.dump({"stats": stats, "items": items}, f,
                  ensure_ascii=False, indent=1)
    print(f"pages={stats['pages']} lines={stats['lines']} "
          f"flagged={stats['flagged']} "
          f"({100*stats['flagged']/max(stats['lines'],1):.1f}%)")
    print(f"crops written: {n}")
    print(f"review page: {os.path.relpath(out, HERE)}")
    print("\ntop reasons:")
    from collections import Counter
    c = Counter(r.split("(")[0].strip() for it in items for r in it["reasons"])
    for r, k in c.most_common(8):
        print(f"  {k:5d}  {r}")


if __name__ == "__main__":
    main()
