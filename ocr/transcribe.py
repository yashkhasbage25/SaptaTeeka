"""
Transcribe pages with Claude Opus 5 on Bedrock, line-aligned and flagged.

Design notes
------------
Tiles are produced by tile.py so that each printed line survives intact in
exactly one tile per column. The model is required to emit one output line per
printed line, which makes stitching deterministic: printed line k is the
concatenation of column 0's line k and column 1's line k.

Everything uncertain is recorded rather than smoothed over, because a silent
error is far worse than a flagged one in a text people will recite:

  - the model is instructed to emit ⟨?⟩ for illegible characters
  - a tile whose line count disagrees with the layout is retried, then flagged
  - every line is diffed against the existing tesseract reading; the two
    engines are independent, so agreement is evidence and disagreement is a
    flag
  - tesseract's own per-word confidence is carried through

Results are cached per page, so the run is resumable and costs nothing to
restart.
"""
import argparse
import difflib
import glob
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

import hocr_tools
import pageimg
import score
import tile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "work", "pages")
TILEDIR = os.path.join(HERE, "work", "tiles")

MODEL = os.environ.get("OCR_MODEL", "anthropic.claude-opus-5")
REGION = os.environ.get("OCR_REGION", "us-east-1")
UNCERTAIN = re.compile(r"⟨\?⟩")

_local = threading.local()
_cred_lock = threading.Lock()
_cred_gen = 0          # bumped on every refresh; invalidates cached clients
_last_refresh = 0.0

# Isengard session tokens last about an hour, which is shorter than a full
# corpus run, so the run refreshes them itself rather than dying halfway.
ADA_ACCOUNT = os.environ.get("ADA_ACCOUNT", "981082658520")
ADA_ROLE = os.environ.get("ADA_ROLE", "IibsAdminAccess-DO-NOT-DELETE")


def refresh_credentials():
    """Re-run ada. Serialised, and rate-limited so parallel workers hitting
    the same expiry do not stampede."""
    global _cred_gen, _last_refresh
    import subprocess

    with _cred_lock:
        if time.time() - _last_refresh < 30:
            return
        print("  refreshing AWS credentials via ada...", flush=True)
        r = subprocess.run(
            [
                "ada", "credentials", "update",
                f"--account={ADA_ACCOUNT}",
                "--provider=conduit",
                f"--role={ADA_ROLE}",
                "--once",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ada refresh failed: {r.stderr[-300:]}")
        _last_refresh = time.time()
        _cred_gen += 1


def client():
    if getattr(_local, "gen", -1) != _cred_gen:
        sess = boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default"))
        _local.c = sess.client(
            "bedrock-runtime",
            region_name=REGION,
            config=Config(read_timeout=900, retries={"max_attempts": 2}),
        )
        _local.gen = _cred_gen
    return _local.c


PROMPT = """\
This image contains {n} consecutive lines from one page of a Sanskrit book \
printed in Devanagari by the Venkateshvara Press, Bombay: the Durgā Saptaśatī \
with its seven classical commentaries.

The image is a COLUMN SEGMENT. Each line has been cut at a word boundary, so \
lines end mid-sentence and the right edges are ragged. That is expected and \
correct. Nothing is missing from within a line.

The {n} lines have been stacked with white space between them. Because the \
original lines sit close together, a thin sliver of the line above or below \
may be visible at the top or bottom edge of each band. IGNORE those slivers \
and transcribe only the {n} full lines.

Transcribe the Devanagari exactly as printed, under these rules:

1. Output EXACTLY {n} lines, one per printed line, in top-to-bottom order. \
This is critical: the lines are stitched back together by position. Do not \
merge lines, do not split them, do not add blank lines.
2. Output ONLY Devanagari text and its punctuation. No translation, no \
transliteration, no commentary, no line numbers, no markdown.
3. Reproduce the text as printed. Do NOT normalise, correct, modernise or \
"fix" the orthography, sandhi, or spelling, even where it looks wrong to you. \
This is a critical edition and archaic or unusual forms are the data.
4. Preserve every danda (।), double danda (॥), verse number, avagraha (ऽ), \
visarga (ः), anusvara (ं), and the quotation marks used around citations.
5. Use the correct Devanagari characters, never ASCII lookalikes: visarga ः \
not a colon, danda । not a pipe.
6. This typeface makes some conjuncts easy to confuse. Look especially \
carefully at: स्व vs ख, त्व vs ल, श्र vs श्न, ब्र vs व्र, द्ध vs द्र, \
प्त vs भ vs प्र, ऋ vs क, ष्ट vs ष्ठ, and ङ्ग vs ङ्क.
7. Where a character or word is genuinely illegible, damaged, or ink-bled, \
emit ⟨?⟩ at exactly that point. Do NOT guess. A flagged gap is far more \
useful than a confident invention. If you can read part of a word, transcribe \
what you can and put ⟨?⟩ only where the doubt is.

Transcribe the {n} lines now."""


def invoke(img_bytes, n_lines, attempt=0, model=None):
    model = model or MODEL
    body = [
        {
            "role": "user",
            "content": [
                {"image": {"format": "jpeg", "source": {"bytes": img_bytes}}},
                {"text": PROMPT.format(n=n_lines)},
            ],
        }
    ]
    for mid in (model, f"us.{model}"):
        try:
            r = client().converse(
                modelId=mid,
                messages=body,
                inferenceConfig={"maxTokens": 8192},
            )
            txt = "".join(
                c.get("text", "") for c in r["output"]["message"]["content"]
            )
            return txt, r.get("usage", {})
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("ExpiredTokenException", "UnrecognizedClientException",
                        "InvalidSignatureException"):
                if attempt < 8:
                    refresh_credentials()
                    return invoke(img_bytes, n_lines, attempt + 1, model)
            if code in ("ThrottlingException", "ServiceUnavailableException",
                        "ModelTimeoutException", "InternalServerException"):
                if attempt < 6:
                    time.sleep(min(60, 2 ** attempt) + random.random() * 3)
                    return invoke(img_bytes, n_lines, attempt + 1, model)
            if code in ("ValidationException", "AccessDeniedException") and mid == model:
                continue
            raise
    raise RuntimeError("invocation failed")


def clean_lines(txt, n):
    """Pull exactly the Devanagari content lines out of a model response."""
    txt = re.sub(r"^```[a-zA-Z]*\s*$|^```\s*$", "", txt, flags=re.M)
    lines = [ln.strip() for ln in txt.split("\n")]
    lines = [ln for ln in lines if ln]
    # drop any stray ASCII-only chatter
    keep = [ln for ln in lines if re.search(r"[\u0900-\u097F]", ln)]
    return keep if keep else lines


def do_tile(t):
    with open(t["path"], "rb") as f:
        img = f.read()
    n = len(t["line_indices"])
    txt, usage = invoke(img, n)
    lines = clean_lines(txt, n)
    retried = False
    if len(lines) != n:
        # one retry; line-count drift breaks stitching so it is worth the cost
        txt2, usage2 = invoke(img, n)
        lines2 = clean_lines(txt2, n)
        retried = True
        if abs(len(lines2) - n) < abs(len(lines) - n):
            lines, usage = lines2, usage2
    return {
        "name": t["name"],
        "band": t["band"],
        "col": t["col"],
        "line_indices": t["line_indices"],
        "lines": lines,
        # tesseract's reading of the same lines, carried along so a mismatched
        # tile can be realigned by content rather than by position
        "ocr_lines": t.get("ocr_lines", []),
        "expected": n,
        "line_count_ok": len(lines) == n,
        "retried": retried,
        "usage": usage,
    }


def align_to_skeleton(expected_texts, returned):
    """
    Map a tile's returned lines onto the printed lines they belong to.

    Positional stitching assumes the model returns exactly one line per
    printed line. When it returns one too few, every later line in that band
    shifts up, and because the two columns are then joined at different
    offsets the result is not merely mispositioned -- it is a chimera of the
    left half of one printed line and the right half of another. That is
    corrupt text that no later pass can repair, and it affected 93 of 158
    pages on the first run.

    So instead of trusting position, each returned line is aligned to the
    tesseract reading of the printed lines. Tesseract is only ~40% accurate,
    which is useless as a transcription but perfectly adequate as a skeleton:
    the right pairing still scores far higher than a wrong one.

    Standard monotonic sequence alignment with gaps. Returns a list the same
    length as expected_texts, holding the matched line or "" where the model
    appears to have skipped one.
    """
    import difflib

    n, m = len(expected_texts), len(returned)
    if n == m:
        return list(returned), []
    if not returned:
        return [""] * n, list(range(n))

    exp = [score.fold(t) for t in expected_texts]
    got = [score.fold(t) for t in returned]

    def sim(i, j):
        if not exp[i] or not got[j]:
            return 0.0
        return difflib.SequenceMatcher(None, exp[i], got[j]).ratio()

    GAP = -0.25
    # dp[i][j] = best score aligning first i expected with first j returned
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bt = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + GAP
        bt[i][0] = "up"
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + GAP
        bt[0][j] = "left"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + sim(i - 1, j - 1)
            up = dp[i - 1][j] + GAP
            left = dp[i][j - 1] + GAP
            best = max(diag, up, left)
            dp[i][j] = best
            bt[i][j] = "diag" if best == diag else ("up" if best == up else "left")

    out = [""] * n
    missing = []
    i, j = n, m
    while i > 0 and j > 0:
        move = bt[i][j]
        if move == "diag":
            out[i - 1] = returned[j - 1]
            i, j = i - 1, j - 1
        elif move == "up":
            missing.append(i - 1)
            i -= 1
        else:
            j -= 1
    while i > 0:
        missing.append(i - 1)
        i -= 1
    return out, sorted(missing)


def stitch(page, tile_results, cols):   # page is unused; kept for callers
    """
    Rebuild printed lines from per-column transcriptions.

    Stitching is positional, so a tile that returns the wrong number of lines
    shifts everything after it within that band. That is the one failure mode
    that could silently corrupt text, so every line of an affected band is
    marked suspect and surfaced for review rather than quietly trusted.
    """
    by_key = {(r["band"], r["col"]): r for r in tile_results}
    parts = {}
    suspect = set()
    issues = []
    for (band, col), r in by_key.items():
        idxs = r["line_indices"]
        lines = r["lines"]
        if len(lines) != len(idxs):
            # Recover the correct pairing instead of letting the shift corrupt
            # every later line in this band.
            lines, missing = align_to_skeleton(r.get("ocr_lines", []), lines)
            issues.append(
                f"band {band} col {col}: got {len(r['lines'])} lines, "
                f"expected {len(idxs)}; realigned, "
                f"{len(missing)} line(s) unmatched"
            )
            # only the lines we could not match are untrustworthy now
            suspect.update(idxs[k] for k in missing if k < len(idxs))
        for k, li in enumerate(idxs):
            parts.setdefault(li, {})[col] = lines[k] if k < len(lines) else ""
    out = []
    for li in sorted(parts):
        segs = [parts[li].get(c, "") for c in range(cols)]
        out.append(" ".join(s for s in segs if s).strip())
    return out, issues, sorted(suspect)


def flag_line(text, ocr_text, ocr_conf):
    """Confidence signals for one stitched line."""
    unc = len(UNCERTAIN.findall(text))
    wacc, cacc = score.accuracy(score.fold(ocr_text), score.fold(text))
    return {
        "uncertain_marks": unc,
        "tesseract_word_agree": round(wacc, 3),
        "tesseract_char_agree": round(cacc, 3),
        "tesseract_mean_conf": round(ocr_conf, 1),
        # a line where the two engines barely agree AND tesseract was unsure
        # is where a silent error is most likely to be hiding
        "needs_review": bool(unc) or (cacc < 0.55) or (cacc < 0.70 and ocr_conf < 55),
    }


def transcribe_page(vol, scan, hocr_pages, cols=2, lines_per=12, force=False):
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, f"v{vol}_{scan:04d}.json")
    if os.path.exists(dest) and not force:
        return json.load(open(dest, encoding="utf-8")), True

    page = hocr_pages[scan]
    if not page.lines:
        rec = {"vol": vol, "scan": scan, "lines": [], "empty": True}
        json.dump(rec, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return rec, False

    tdir = os.path.join(TILEDIR, f"v{vol}_{scan:04d}")
    tiles = tile.build_tiles(
        os.path.join(HERE, "source", f"v{vol}_hocr.html"),
        scan,
        pageimg.path_for(vol, scan),
        tdir,
        cols=cols,
        lines_per=lines_per,
    )
    results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(do_tile, t): t for t in tiles}
        for fu in as_completed(futs):
            results.append(fu.result())

    stitched, issues, suspect = stitch(page, results, cols)
    flags = []
    for i, text in enumerate(stitched):
        ol = page.lines[i] if i < len(page.lines) else None
        f = flag_line(text, ol.text if ol else "", ol.mean_conf if ol else 0.0)
        if i in suspect:
            f["stitch_suspect"] = True
            f["needs_review"] = True
        flags.append(f)

    usage = {
        "in": sum((r["usage"] or {}).get("inputTokens", 0) for r in results),
        "out": sum((r["usage"] or {}).get("outputTokens", 0) for r in results),
    }
    rec = {
        "vol": vol,
        "scan": scan,
        "model": MODEL,
        "cols": cols,
        "n_lines": len(stitched),
        "lines": stitched,
        "flags": flags,
        "issues": issues,
        # Raw per-tile output is kept, not just a summary. The first run threw
        # it away, which meant a stitching bug could only be fixed by paying
        # for the inference again. With this, any future change to stitching
        # or alignment is a free re-run over the stored data.
        "tiles": [
            {
                k: r[k]
                for k in ("name", "band", "col", "line_indices", "lines",
                          "expected", "line_count_ok", "retried")
            }
            for r in sorted(results, key=lambda r: (r["band"], r["col"]))
        ],
        "usage": usage,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    json.dump(rec, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rec, False


WHOLE_PAGE_PROMPT = """\
This is a full page from a Sanskrit book printed in Devanagari by the \
Venkateshvara Press, Bombay (Durgā Saptaśatī with seven commentaries). It may \
be a title page, a table of contents, or a page whose layout is not a single \
simple column.

Transcribe everything on the page, in natural reading order.

- Output one line per printed line. Preserve the order.
- Output the Devanagari exactly as printed; do not normalise or correct \
spelling or sandhi. Keep every danda (।), double danda (॥) and verse number.
- If the page contains text in English or another Latin-script language \
(publisher imprints and the like often do), transcribe that too, in place.
- Use real Devanagari punctuation, not ASCII lookalikes.
- Where something is genuinely illegible, emit ⟨?⟩ there rather than guessing.
- Do not add commentary, translation or headings of your own.

Transcribe the page now."""


def invoke_whole_page(img_bytes, attempt=0):
    body = [
        {
            "role": "user",
            "content": [
                {"image": {"format": "jpeg", "source": {"bytes": img_bytes}}},
                {"text": WHOLE_PAGE_PROMPT},
            ],
        }
    ]
    for mid in (MODEL, f"us.{MODEL}"):
        try:
            r = client().converse(
                modelId=mid, messages=body,
                inferenceConfig={"maxTokens": 8192},
            )
            return "".join(
                c.get("text", "") for c in r["output"]["message"]["content"]
            ), r.get("usage", {})
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("ExpiredTokenException", "UnrecognizedClientException"):
                if attempt < 8:
                    refresh_credentials()
                    return invoke_whole_page(img_bytes, attempt + 1)
            if code in ("ThrottlingException", "ServiceUnavailableException",
                        "ModelTimeoutException", "InternalServerException"):
                if attempt < 6:
                    time.sleep(min(60, 2 ** attempt) + random.random() * 3)
                    return invoke_whole_page(img_bytes, attempt + 1)
            if code in ("ValidationException",) and mid == MODEL:
                continue
            raise
    raise RuntimeError("whole-page invocation failed")


def repair_page(vol, scan):
    """
    Re-transcribe a page as one whole image.

    Column tiling depends on tesseract's line segmentation to decide where the
    lines are. On title pages, contents pages and other non-column layouts
    that segmentation is wrong, so the tiles are malformed and the model
    returns a different number of lines than the layout predicted. Those pages
    are also the ones set in larger type, so they survive being sent whole at
    reduced resolution, which removes the dependency on segmentation entirely.
    """
    from PIL import Image
    import io as _io

    im = pageimg.page_image(vol, scan)
    long_edge = max(im.size)
    if long_edge > 1536:
        f = 1536 / long_edge
        im = im.resize((round(im.width * f), round(im.height * f)),
                       Image.LANCZOS)
    buf = _io.BytesIO()
    im.save(buf, format="JPEG", quality=95)
    txt, usage = invoke_whole_page(buf.getvalue())
    lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]
    lines = [ln for ln in lines if not re.fullmatch(r"`{3,}[a-zA-Z]*", ln)]

    dest = os.path.join(OUT, f"v{vol}_{scan:04d}.json")
    rec = json.load(open(dest, encoding="utf-8")) if os.path.exists(dest) else {}

    # A repair must never be allowed to destroy a better result. Sending a
    # dense page whole can make the model run to the token ceiling and return
    # nothing usable, so an implausibly short repair is discarded and the
    # tiled transcription is kept.
    prior = rec.get("lines") or []
    if len(lines) < max(3, 0.5 * len(prior)):
        rec.setdefault("repair_attempts", []).append(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "got_lines": len(lines),
                "kept_prior_lines": len(prior),
                "out_tokens": usage.get("outputTokens"),
                "rejected": "repair returned implausibly few lines",
            }
        )
        json.dump(rec, open(dest, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        return rec
    rec.update(
        {
            "vol": vol,
            "scan": scan,
            "model": MODEL,
            "mode": "whole_page",
            "n_lines": len(lines),
            "lines": lines,
            "flags": [
                {
                    "uncertain_marks": ln.count("⟨?⟩"),
                    "tesseract_char_agree": 1.0,
                    "tesseract_mean_conf": 0.0,
                    "whole_page": True,
                    "needs_review": bool(ln.count("⟨?⟩")),
                }
                for ln in lines
            ],
            "issues": [],
            "usage": {
                "in": usage.get("inputTokens", 0),
                "out": usage.get("outputTokens", 0),
            },
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    )
    json.dump(rec, open(dest, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return rec


def needs_repair(rec, threshold=0.4):
    flags = rec.get("flags", [])
    if not flags or rec.get("mode") == "whole_page":
        return False
    bad = sum(1 for f in flags if f.get("stitch_suspect"))
    return bad / len(flags) >= threshold


def run_repairs(workers=3, threshold=0.4):
    targets = []
    for p in sorted(glob.glob(os.path.join(OUT, "*.json"))):
        rec = json.load(open(p, encoding="utf-8"))
        if rec.get("empty"):
            continue
        if needs_repair(rec, threshold):
            targets.append((rec["vol"], rec["scan"]))
    print(f"{len(targets)} pages need whole-page repair")
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(repair_page, v, s): (v, s) for v, s in targets}
        for fu in as_completed(futs):
            v, s = futs[fu]
            try:
                rec = fu.result()
                done += 1
                print(f"[{done}/{len(targets)}] repaired v{v} scan {s}: "
                      f"{rec['n_lines']} lines", flush=True)
            except Exception as e:
                print(f"  v{v} scan {s}: repair FAILED {type(e).__name__}: {e}",
                      flush=True)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, action="append")
    ap.add_argument("--scans", help="e.g. 20 or 20-25 or 20,22,30")
    ap.add_argument("--repair", action="store_true",
                    help="re-do badly stitched pages as whole images")
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--lines", type=int, default=12)
    ap.add_argument("--workers", type=int, default=3, help="pages in parallel")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if a.repair:
        run_repairs(workers=a.workers)
        return

    vols = a.vol or [1, 2, 3]
    jobs = []
    for v in vols:
        hp = hocr_tools.parse(os.path.join(HERE, "source", f"v{v}_hocr.html"))
        if a.scans:
            sel = set()
            for part in a.scans.split(","):
                if "-" in part:
                    lo, hi = part.split("-")
                    sel.update(range(int(lo), int(hi) + 1))
                else:
                    sel.add(int(part))
            scans = sorted(s for s in sel if s < len(hp))
        else:
            scans = list(range(len(hp)))
        jobs.append((v, scans, hp))

    total = sum(len(s) for _, s, _ in jobs)
    done = cached = 0
    t0 = time.time()
    tok_in = tok_out = 0

    for v, scans, hp in jobs:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {
                ex.submit(transcribe_page, v, s, hp, a.cols, a.lines, a.force): s
                for s in scans
            }
            for fu in as_completed(futs):
                s = futs[fu]
                try:
                    rec, was_cached = fu.result()
                except Exception as e:
                    print(f"  v{v} scan {s}: FAILED {type(e).__name__}: {e}",
                          flush=True)
                    continue
                done += 1
                cached += was_cached
                tok_in += rec.get("usage", {}).get("in", 0)
                tok_out += rec.get("usage", {}).get("out", 0)
                nrev = sum(1 for f in rec.get("flags", []) if f["needs_review"])
                el = time.time() - t0
                rate = done / el if el else 0
                eta = (total - done) / rate / 60 if rate else 0
                print(
                    f"[{done}/{total}] v{v} scan {s:3d} "
                    f"lines={rec.get('n_lines',0):3d} review={nrev:3d} "
                    f"{'cached' if was_cached else ''} "
                    f"eta={eta:.0f}m",
                    flush=True,
                )

    print(f"\ndone {done} pages ({cached} cached) in {(time.time()-t0)/60:.1f} min")
    print(f"tokens in={tok_in} out={tok_out}")


if __name__ == "__main__":
    main()
