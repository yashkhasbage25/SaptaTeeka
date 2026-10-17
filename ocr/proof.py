"""
Build the line-by-line proofreading view.

For correcting a transcription the useful layout is not a whole page beside a
whole text -- your eye loses its place. It is each printed line with its own
transcription directly beneath it, so a wrong character sits a few millimetres
from the ink it misread.

Doing that naively would mean cropping every one of the ~6,500 lines to its
own JPEG, several hundred megabytes of near-duplicate images. Instead each
line strip is drawn by the browser from the single page scan, using the line's
bounding box as a CSS background offset. One image per page, already in the
cache, and every line gets its own view for free.

    python proof.py                  all transcribed pages
    python proof.py --vol 1 --scans 20-30

Writes docs/proof/index.html and docs/proof/v<vol>_<scan>.html
"""
import argparse
import glob
import html
import json
import os
import shutil

import hocr_tools
import pageimg
import structure

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "work", "pages")
PROOF = os.path.join(HERE, "..", "docs", "proof")
SCANS_DIR = os.path.join(PROOF, "scans")

STRIP_WIDTH = 1040          # on-screen width of a line strip, px
SCAN_STORE_WIDTH = 2400     # stored scan width; see note in build_page
# Band height as a multiple of the line pitch.
#
# Measured on these pages: pitch ~112 px, full glyph extent of one line
# ~158 px, so the ratio is 1.40. That sets the window tightly from both
# sides. Below ~1.4 the tops of matras get cut, which is fatal in a view whose
# whole purpose is verifying glyphs. Much above it (2.0 was tried) the strip
# shows the next line in full and the reader cannot tell which row is the one
# being checked.
#
# At 1.55 the target line sits centred and complete, and the neighbours
# contribute only the thin marks that overlap it on the printed page anyway --
# descenders from above, matra tips from below. That is simply what the book
# looks like, and it is what a human proofreader is used to.
PROOF_BAND = 1.55
UNCLEAR = "⟨?⟩"

CSS = """
body { background:#1b1b1b; color:#e8e8e8; margin:0;
       font-family:"Noto Sans",system-ui,sans-serif; }
header { position:sticky; top:0; background:#111; padding:10px 18px;
         border-bottom:1px solid #333; z-index:10; display:flex;
         gap:14px; align-items:center; flex-wrap:wrap; }
header a { color:#8fd3ff; text-decoration:none; }
header .t { color:#ffc100; font-weight:700; }
.wrap { max-width:1120px; margin:0 auto; padding:18px; }
.ln { margin-bottom:26px; padding:10px 12px; border-radius:6px;
      background:#232323; }
.ln.flag { background:#2e2718; border-left:4px solid #ffc100; }
/* The two halves of one printed line sit flush inside a single white box, so
   they read as one line wrapped onto two rows rather than as two lines.
   Lines of this edition interleave vertically -- the glyph extent is wider
   than the pitch -- so a strip tall enough to show one line whole inevitably
   catches its neighbours. Rather than crop them off (which also cuts this
   line's matras), they are faded to white at the top and bottom edges, so the
   line being checked is the only crisp thing in the frame. */
.scanbox { background:#fff; border-radius:4px; overflow:hidden;
           max-width:1040px; }
.strip { width:100%; max-width:1040px; background-repeat:no-repeat;
         background-color:#fff; display:block;
         -webkit-mask-image:linear-gradient(to bottom,
             rgba(0,0,0,0) 0%, #000 5%, #000 95%, rgba(0,0,0,0) 100%);
         mask-image:linear-gradient(to bottom,
             rgba(0,0,0,0) 0%, #000 5%, #000 95%, rgba(0,0,0,0) 100%); }
.tx { font-size:1.28em; line-height:1.95; margin-top:9px;
      font-family:"Laila",serif; }
.ocr { color:#9a9a9a; font-size:.9em; font-style:italic; margin-top:5px; }
.no { color:#777; font-size:.76em; letter-spacing:.07em; }
.unclear { color:#ffdd57; background:#000; border-bottom:2px dotted #ffdd57;
           padding:0 4px; border-radius:3px; font-weight:700; }
.toggles { margin-left:auto; font-size:.85em; color:#aaa; }
.hide-ocr .ocr { display:none; }
table.idx { border-collapse:collapse; width:100%; }
table.idx td, table.idx th { padding:5px 9px; border-bottom:1px solid #333;
                             font-size:.92em; text-align:left; }
table.idx a { color:#8fd3ff; text-decoration:none; }
.bad { color:#ff9e9e; }
.good { color:#9be59b; }
.warn { background:#4a2020; border:1px solid #a33; color:#ffdede;
        padding:11px 14px; border-radius:6px; margin-bottom:20px;
        font-size:.95em; line-height:1.55; }
.mis { color:#ff9e9e; font-size:.8em; margin-top:3px; }
.ln.misal { outline:1px solid #a33; }
tr.g-broken td { background:#3a1c1c; }
tr.g-degraded td { background:#3a331c; }
"""

PAGE_TMPL = """<!DOCTYPE html><html lang="sa"><head><meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<style>@import url('https://fonts.googleapis.com/css2?family=Laila:wght@400;500&family=Noto+Sans:wght@400;600&display=swap');
{css}</style></head>
<body class="hide-ocr">
<header>
  <span class="t">{title}</span>
  <a href="index.html">all pages</a>
  {prev}{next}
  <span class="toggles">
    <label><input type="checkbox" id="ocrtog"> show tesseract reading</label>
    &nbsp;|&nbsp; {nflag} of {nlines} lines flagged
  </span>
</header>
<div class="wrap">
{body}
</div>
<script>
document.getElementById('ocrtog').addEventListener('change', function(e){{
  document.body.classList.toggle('hide-ocr', !e.target.checked);
}});
</script>
</body></html>
"""


def esc(s):
    return html.escape(s).replace(
        UNCLEAR, '<span class="unclear">&#10216;?&#10217;</span>'
    )


def tight_bands(page):
    """
    Vertical crop per line, tight enough that only that line is visible.

    tesseract's line boxes run 1.4x to 1.7x the line pitch on these pages, so
    cropping to the box shows the target line plus a sliced-off slab of its
    neighbour. In a proofreading view that is actively harmful: every line
    appears twice, once as itself and once as debris above or below another,
    and the eye cannot tell which row it is meant to be checking.

    The line pitch is stable within a page, so each band is centred on its own
    line and sized just over one pitch. Slight clipping of the tallest matras
    is the right trade here -- unlike the transcription tiles, a human is
    reading this and can see the line below if they need to.
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
    half = pitch * PROOF_BAND / 2
    return [(c - half, c + half) for c in centres]


def strip_style(img_w, img_h, bbox, sx, sy, frac=(0.0, 1.0), pad=10):
    """
    CSS that shows part of one line, cut out of the full page scan.

    A whole line of this edition is ~3850 px wide. Shown at a screen width
    that fits a browser column, its glyphs come out around 26 px tall, which
    is enough to spot a missing word but not enough to tell ष्ट from ष्ठ --
    which is exactly what proofreading this text requires. So each line is
    emitted in two stacked halves, doubling the magnification without forcing
    horizontal scrolling. `frac` selects which part of the line to show.

    The line box is in hOCR coordinate space, which need not match the pixel
    size of the cached scan, so both axes are scaled before use.
    """
    lx0 = max(0, (bbox[0] - pad) * sx)
    lx1 = min(img_w, (bbox[2] + pad) * sx)
    span = max(1.0, lx1 - lx0)
    x0 = lx0 + span * frac[0]
    x1 = lx0 + span * frac[1]
    y0 = max(0, bbox[1] * sy)
    y1 = min(img_h, bbox[3] * sy)
    w, h = max(1.0, x1 - x0), max(1.0, y1 - y0)
    k = STRIP_WIDTH / w
    return (
        f"height:{h * k:.0f}px;"
        f"background-size:{img_w * k:.0f}px {img_h * k:.0f}px;"
        f"background-position:-{x0 * k:.0f}px -{y0 * k:.0f}px;"
        f"background-image:url('scans/{{name}}');"
    )


def build_page(vol, scan, rec, hpages, neighbours):
    page = hpages[scan]
    im = pageimg.page_image(vol, scan)
    # make the scan available to the page without duplicating it per line
    os.makedirs(SCANS_DIR, exist_ok=True)
    scan_name = f"v{vol}_{scan:04d}.jpg"
    dest = os.path.join(SCANS_DIR, scan_name)
    if not os.path.exists(dest):
        # Half a line is ~1925 px and is displayed at ~1040 px, so storing the
        # scan above ~2400 px wide buys no visible detail and costs 2.5x the
        # disk. Downscaling here keeps the whole proof set manageable.
        shot = im.copy()
        if shot.width > SCAN_STORE_WIDTH:
            f = SCAN_STORE_WIDTH / shot.width
            shot = shot.resize(
                (SCAN_STORE_WIDTH, round(shot.height * f))
            )
        shot.save(dest, quality=82)

    sx = im.width / page.bbox[2] if page.bbox[2] else 1.0
    sy = im.height / page.bbox[3] if page.bbox[3] else 1.0
    # strips are positioned against the stored (possibly downscaled) scan
    store_k = min(1.0, SCAN_STORE_WIDTH / im.width)
    sx *= store_k
    sy *= store_k
    store_w = round(im.width * store_k)
    store_h = round(im.height * store_k)

    lines = rec.get("lines", [])
    flags = rec.get("flags", [])
    whole = rec.get("mode") == "whole_page"
    bands = tight_bands(page) if page.lines else []

    # Strips are positioned from tesseract's line boxes while the text comes
    # from the model. On pages where a tile returned the wrong number of
    # lines, the stitch shifted and line i of the text is no longer line i of
    # the layout -- so the scan shown above a line may belong to a different
    # line. Displaying that without saying so would actively mislead a
    # proofreader into "correcting" good text, so those rows are called out
    # and the page is banner-warned.
    misaligned = {
        i for i, f in enumerate(flags) if f.get("stitch_suspect")
    }
    status = ""
    if whole:
        status = (
            '<div class="warn">This page was transcribed as a whole image '
            "because its layout defeated line segmentation, so there are no "
            "per-line scans to show. Check it against the full page scan.</div>"
        )
    elif misaligned:
        pct = 100 * len(misaligned) / max(len(lines), 1)
        status = (
            f'<div class="warn">Line alignment on this page is unreliable: '
            f"{len(misaligned)} of {len(lines)} lines ({pct:.0f}%) may show "
            f"the wrong scan strip. Affected rows are marked. Running the "
            f"whole-page repair pass on this page would fix it.</div>"
        )

    rows = []
    nflag = 0
    for i, text in enumerate(lines):
        fl = flags[i] if i < len(flags) else {}
        flagged = bool(fl.get("needs_review")) or UNCLEAR in text
        nflag += bool(flagged)
        # whole-page mode has no per-line boxes to cut from
        if not whole and i < len(page.lines):
            lb = page.lines[i].bbox
            by0, by1 = bands[i]
            bb = (lb[0], by0, lb[2], by1)       # line's x extent, tight y band
            halves = []
            for frac in ((0.0, 0.52), (0.48, 1.0)):   # slight overlap at the seam
                st = strip_style(store_w, store_h, bb, sx, sy, frac)
                halves.append(
                    f'<div class="strip" style="{st.format(name=scan_name)}"></div>'
                )
            strip = f'<div class="scanbox">{"".join(halves)}</div>'
            ocr = page.lines[i].text
        else:
            strip = ""
            ocr = ""
        bad = i in misaligned
        note = (
            '<div class="mis">scan strip above may not be this line</div>'
            if bad else ""
        )
        rows.append(
            f'<div class="ln{" flag" if flagged else ""}{" misal" if bad else ""}">'
            f'<div class="no">line {i}</div>'
            f"{strip}{note}"
            f'<div class="tx">{esc(text) or "&mdash;"}</div>'
            f'<div class="ocr">tesseract: {html.escape(ocr) or "&mdash;"}</div>'
            f"</div>"
        )

    folio = structure.folio(vol, scan)
    title = (
        f"folio {folio}" if folio else "front matter"
    ) + f" &nbsp;(vol {vol}, scan {scan})"
    prev_s, next_s = neighbours
    prev = (
        f'<a href="v{prev_s[0]}_{prev_s[1]:04d}.html">&larr; previous</a>'
        if prev_s else ""
    )
    nxt = (
        f'<a href="v{next_s[0]}_{next_s[1]:04d}.html">next &rarr;</a>'
        if next_s else ""
    )
    out = PAGE_TMPL.format(
        title=title, css=CSS, body=status + "\n".join(rows),
        prev=prev, next=nxt, nflag=nflag, nlines=len(lines),
    )
    path = os.path.join(PROOF, f"v{vol}_{scan:04d}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    grade = "broken" if whole else (
        "degraded" if len(misaligned) > 0.15 * max(len(lines), 1) else "good"
    )
    return nflag, len(lines), grade, len(misaligned)


INDEX_TMPL = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>proofreading index</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<style>{css}</style></head><body>
<header><span class="t">proofreading</span>
<a href="../index.html">site</a><a href="../review.html">review queue</a>
<span class="toggles">{summary}</span></header>
<div class="wrap">
<p class="no">Each page shows every printed line with its transcription
directly beneath it. Flagged lines are highlighted. Correct the text in the
XML under <code>sanitized_auto/</code>, then re-run
<code>python converter.py</code>.</p>
<table class="idx">
<tr><th>folio</th><th>section</th><th>lines</th><th>flagged</th>
<th>state</th><th></th></tr>
{rows}
</table></div></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, action="append")
    ap.add_argument("--scans")
    a = ap.parse_args()

    os.makedirs(PROOF, exist_ok=True)
    recs = []
    for p in sorted(glob.glob(os.path.join(PAGES, "*.json"))):
        r = json.load(open(p, encoding="utf-8"))
        if r.get("empty") or not r.get("lines"):
            continue
        if a.vol and r["vol"] not in a.vol:
            continue
        if a.scans:
            sel = set()
            for part in a.scans.split(","):
                if "-" in part:
                    lo, hi = part.split("-")
                    sel.update(range(int(lo), int(hi) + 1))
                else:
                    sel.add(int(part))
            if r["scan"] not in sel:
                continue
        recs.append(r)
    recs.sort(key=lambda r: (r["vol"], r["scan"]))

    # section per page, reusing the same running-head logic as the XML build
    sect = {}
    for r in recs:
        hinted = None
        n = len(r["lines"])
        for i, ln in enumerate(r["lines"]):
            if structure.is_header(ln, i, n):
                h = structure.classify_header(ln)
                if h:
                    hinted = h
        sect[(r["vol"], r["scan"])] = hinted

    hcache = {}
    rows = []
    audit = []
    grades = {}
    tot_lines = tot_flag = 0
    current = "frontmatter"
    for k, r in enumerate(recs):
        vol, scan = r["vol"], r["scan"]
        if vol not in hcache:
            hcache[vol] = hocr_tools.parse(
                os.path.join(HERE, "source", f"v{vol}_hocr.html")
            )
        prev_s = (recs[k - 1]["vol"], recs[k - 1]["scan"]) if k else None
        next_s = (
            (recs[k + 1]["vol"], recs[k + 1]["scan"])
            if k + 1 < len(recs) else None
        )
        nflag, nlines, grade, nmis = build_page(
            vol, scan, r, hcache[vol], (prev_s, next_s)
        )
        current = sect[(vol, scan)] or current
        tot_lines += nlines
        tot_flag += nflag
        grades[grade] = grades.get(grade, 0) + 1
        folio = structure.folio(vol, scan)
        pct = 100 * nflag / max(nlines, 1)
        cls = "bad" if pct > 40 else "good" if pct < 12 else ""
        label = {
            "good": "<span class='good'>ready</span>",
            "degraded": "<span class='bad'>alignment off</span>",
            "broken": "<span class='bad'>no line scans</span>",
        }[grade]
        rows.append(
            f"<tr class='g-{grade}'><td>{folio if folio else '&mdash;'}</td>"
            f"<td>{structure.SECTION_TITLES.get(current, current)}</td>"
            f"<td>{nlines}</td>"
            f"<td class='{cls}'>{nflag} ({pct:.0f}%)</td>"
            f"<td>{label}</td>"
            f"<td><a href='v{vol}_{scan:04d}.html'>proofread</a></td></tr>"
        )
        audit.append(
            {
                "vol": vol, "scan": scan, "folio": folio,
                "section": current, "lines": nlines, "flagged": nflag,
                "misaligned": nmis, "grade": grade,
            }
        )

    summary = (
        f"{len(recs)} pages &nbsp;·&nbsp; {tot_lines} lines &nbsp;·&nbsp; "
        f"{tot_flag} flagged ({100*tot_flag/max(tot_lines,1):.0f}%)"
        f" &nbsp;·&nbsp; <span class='good'>{grades.get('good',0)} ready</span>, "
        f"<span class='bad'>{grades.get('degraded',0)} alignment off, "
        f"{grades.get('broken',0)} no line scans</span>"
    )
    with open(os.path.join(PROOF, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX_TMPL.format(css=CSS, summary=summary,
                                  rows="\n".join(rows)))
    with open(os.path.join(HERE, "work", "proof_audit.json"), "w",
              encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=1)

    print(f"\n{len(recs)} pages -> docs/proof/index.html")
    print(f"{tot_lines} lines, {tot_flag} flagged "
          f"({100*tot_flag/max(tot_lines,1):.1f}%)")
    print(f"\npage state:")
    for g in ("good", "degraded", "broken"):
        print(f"  {g:9s} {grades.get(g,0):3d}")
    # which sections are actually proofreadable right now
    from collections import Counter
    bysec = {}
    for a in audit:
        d = bysec.setdefault(a["section"], Counter())
        d[a["grade"]] += 1
    print(f"\n{'section':26s} {'ready':>6s} {'align off':>10s} {'no scans':>9s}")
    for s, c in bysec.items():
        print(f"{structure.SECTION_TITLES.get(s, s):26s} "
              f"{c['good']:6d} {c['degraded']:10d} {c['broken']:9d}")


if __name__ == "__main__":
    main()
