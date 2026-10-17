"""
Second-opinion verification pass: re-read every tile with a different model
and treat disagreement between the two as the confidence signal.

Why this exists
---------------
The flagging in transcribe.py compares the new reading against the existing
tesseract layer. That layer is only ~40% word-accurate, so its disagreement is
a weak signal: it fires constantly on clean text and says nothing useful on
pages where tesseract collapsed entirely. It cannot find the dangerous class
of error at all -- the place where the primary model is confidently wrong,
because tesseract is wrong there too, differently.

Two strong, independent readings of the same crop fix that. Where Opus and
Sonnet agree character-for-character, the reading is almost certainly right;
neither has any reason to invent the same Sanskrit. Where they diverge, a
human should look. The models see byte-identical tiles from the cache, so a
difference is a difference in reading, not in input.

This is the escalation design, with the roles the right way round: the better
model produces the text, the cheaper one audits it.

    python verify.py                 verify every transcribed page
    python verify.py --scans 20-30
"""
import argparse
import glob
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import score
import transcribe

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "work", "verify")
PAGES = transcribe.OUT
TILEDIR = transcribe.TILEDIR

# The verifier has to be about as strong as the primary, or its own errors
# swamp the signal. Measured on three pages, Sonnet 5 agreed with Opus 5 on
# only 0.80 of words order-insensitively -- but the bake-off puts Sonnet at
# 85.7% and Opus at ~97%, so most of that gap is the verifier being wrong, not
# the primary. A weak auditor is no better than the tesseract layer it was
# meant to replace.
#
# So the verifier is Opus again, but reading DIFFERENT crops: three columns
# instead of two. Same pixels, different cut points and different context per
# tile, which decorrelates the errors. Agreement then means two independent
# readings of the page concur; disagreement is worth a human's time.
VERIFY_MODEL = os.environ.get("VERIFY_MODEL", "anthropic.claude-opus-5")
VERIFY_COLS = int(os.environ.get("VERIFY_COLS", "3"))


def compare_pages(primary_lines, verifier_lines):
    """
    Compare the two readings of a page by aligning their full word sequences,
    not by line position.

    Position-based comparison proved useless here: the verifier model is less
    reliable at honouring the "return exactly N lines" instruction, and a
    single tile returning 11 lines instead of 12 shifts every later line in
    that band, so the whole band reads as disagreement when the words are in
    fact identical. Aligning the concatenated text sidesteps that entirely --
    a reported difference is then a difference in reading.

    Each differing span is mapped back to the line it starts on, by cumulative
    word offset, so a reviewer can still be pointed at the right place.

    Returns (summary, diffs).
    """
    import difflib

    prim_words, line_of = [], []
    for li, ln in enumerate(primary_lines):
        for w in score.fold(ln).split():
            prim_words.append(w)
            line_of.append(li)
    ver_words = score.fold(" ".join(verifier_lines)).split()

    sm = difflib.SequenceMatcher(None, prim_words, ver_words, autojunk=False)
    matched = sum(b.size for b in sm.get_matching_blocks())
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        diffs.append(
            {
                "op": tag,
                "line": line_of[i1] if i1 < len(line_of) else None,
                "primary": " ".join(prim_words[i1:i2]),
                "verifier": " ".join(ver_words[j1:j2]),
                "ctx_before": " ".join(prim_words[max(0, i1 - 4):i1]),
                "ctx_after": " ".join(prim_words[i2:i2 + 4]),
            }
        )
    summary = {
        "primary_words": len(prim_words),
        "verifier_words": len(ver_words),
        "matched_words": matched,
        "word_agreement": round(matched / max(len(prim_words), 1), 4),
        "diff_spans": len(diffs),
    }
    return summary, diffs


def verify_tile(t):
    """Transcribe one cached tile with the verifier model."""
    with open(t["path"], "rb") as f:
        img = f.read()
    n = len(t["line_indices"])
    txt, usage = transcribe.invoke(img, n, model=VERIFY_MODEL)
    lines = transcribe.clean_lines(txt, n)
    if len(lines) != n:
        # One retry, same as the primary pass. Costs little and the verifier
        # drops lines more often than the primary model does.
        txt2, usage2 = transcribe.invoke(img, n, model=VERIFY_MODEL)
        lines2 = transcribe.clean_lines(txt2, n)
        if abs(len(lines2) - n) < abs(len(lines) - n):
            lines, usage = lines2, usage2
    return {
        "name": t["name"],
        "band": t["band"],
        "col": t["col"],
        "line_indices": t["line_indices"],
        "lines": lines,
        "expected": n,
        "line_count_ok": len(lines) == n,
        "usage": usage,
    }


def verify_page(vol, scan, force=False):
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, f"v{vol}_{scan:04d}.json")
    if os.path.exists(dest) and not force:
        return json.load(open(dest, encoding="utf-8")), True

    primary_path = os.path.join(PAGES, f"v{vol}_{scan:04d}.json")
    primary = json.load(open(primary_path, encoding="utf-8"))
    if primary.get("empty"):
        return None, False

    # Build a second, independent tiling of the same page for the audit.
    vtdir = os.path.join(HERE, "work", "vtiles", f"v{vol}_{scan:04d}")
    tiles_path = os.path.join(vtdir, "tiles.json")
    if primary.get("mode") != "whole_page" and not os.path.exists(tiles_path):
        try:
            import pageimg
            import tile as tilemod
            tilemod.build_tiles(
                os.path.join(HERE, "source", f"v{vol}_hocr.html"),
                scan,
                pageimg.path_for(vol, scan),
                vtdir,
                cols=VERIFY_COLS,
                lines_per=10,
            )
        except Exception as e:
            print(f"  v{vol} s{scan}: verify tiling failed: {e}", flush=True)

    if primary.get("mode") == "whole_page" or not os.path.exists(tiles_path):
        # Pages repaired as a whole image have no comparable tiles. Skipping
        # them is recorded rather than passed over silently, so the coverage
        # gap stays visible in the report.
        rec = {
            "vol": vol, "scan": scan, "verifier": VERIFY_MODEL,
            "skipped": "no tiles (whole-page mode)",
            "lines": [], "agreement": [],
        }
        json.dump(rec, open(dest, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        return rec, False

    tiles = json.load(open(tiles_path, encoding="utf-8"))
    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(verify_tile, t) for t in tiles]
        for fu in as_completed(futs):
            results.append(fu.result())

    cols = VERIFY_COLS
    stitched, issues, suspect = transcribe.stitch(None, results, cols)

    prim_lines = primary.get("lines", [])
    agreement, diffs = compare_pages(prim_lines, stitched)

    rec = {
        "vol": vol,
        "scan": scan,
        "verifier": VERIFY_MODEL,
        "cols": cols,
        "lines": stitched,
        "agreement": agreement,
        "diffs": diffs,
        "issues": issues,
        "stitch_suspect": suspect,
        "usage": {
            "in": sum((r["usage"] or {}).get("inputTokens", 0) for r in results),
            "out": sum((r["usage"] or {}).get("outputTokens", 0) for r in results),
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    json.dump(rec, open(dest, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return rec, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scans", help="limit to scans, e.g. 20-40")
    ap.add_argument("--vol", type=int, action="append")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    targets = []
    for p in sorted(glob.glob(os.path.join(PAGES, "*.json"))):
        rec = json.load(open(p, encoding="utf-8"))
        if rec.get("empty"):
            continue
        vol, scan = rec["vol"], rec["scan"]
        if a.vol and vol not in a.vol:
            continue
        if a.scans:
            sel = set()
            for part in a.scans.split(","):
                if "-" in part:
                    lo, hi = part.split("-")
                    sel.update(range(int(lo), int(hi) + 1))
                else:
                    sel.add(int(part))
            if scan not in sel:
                continue
        targets.append((vol, scan))

    print(f"verifying {len(targets)} pages with {VERIFY_MODEL}")
    done = cached = skipped = 0
    tin = tout = 0
    t0 = time.time()
    agree_tot = []

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(verify_page, v, s, a.force): (v, s) for v, s in targets}
        for fu in as_completed(futs):
            v, s = futs[fu]
            try:
                rec, was_cached = fu.result()
            except Exception as e:
                print(f"  v{v} scan {s}: FAILED {type(e).__name__}: {e}",
                      flush=True)
                continue
            if rec is None:
                continue
            done += 1
            cached += was_cached
            if rec.get("skipped"):
                skipped += 1
                continue
            u = rec.get("usage", {})
            tin += u.get("in", 0)
            tout += u.get("out", 0)
            ag = rec.get("agreement", {})
            agree_tot.append(ag)
            el = time.time() - t0
            eta = (len(targets) - done) / (done / el) / 60 if done and el else 0
            print(
                f"[{done}/{len(targets)}] v{v} scan {s:3d} "
                f"agree={ag.get('word_agreement', 0):.3f} "
                f"spans={ag.get('diff_spans', 0):3d} "
                f"words={ag.get('primary_words', 0):4d} "
                f"{'cached' if was_cached else ''} eta={eta:.0f}m",
                flush=True,
            )

    if agree_tot:
        pw = sum(a.get("primary_words", 0) for a in agree_tot)
        mw = sum(a.get("matched_words", 0) for a in agree_tot)
        sp = sum(a.get("diff_spans", 0) for a in agree_tot)
        print(f"\ncorpus word agreement, primary vs verifier: {mw/max(pw,1):.4f}")
        print(f"words confirmed by both models: {mw:,} / {pw:,}")
        print(f"disagreement spans to review  : {sp:,}")
    print(f"skipped (whole-page, no tiles): {skipped}")
    print(f"verifier tokens: in={tin:,} out={tout:,}")


if __name__ == "__main__":
    main()
