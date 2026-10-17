"""
Bedrock vision-model bake-off for Devanagari OCR.

Feeds an identical page crop to several models through the Converse API and
scores each transcription against a hand-made gold reference, so model choice
is decided by measurement rather than reputation.

Usage:
    python bakeoff.py <crop.jpg> <gold.txt> [--models a,b,c] [--width N]
"""
import argparse
import base64
import difflib
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from PIL import Image

PROFILE = os.environ.get("AWS_PROFILE", "yk25-codecommit")

# Candidate vision models. Region matters: some are us-west-2 only.
CANDIDATES = [
    ("anthropic.claude-opus-5", "us-east-1"),
    ("anthropic.claude-sonnet-5", "us-east-1"),
    ("anthropic.claude-sonnet-4-5-20250929-v1:0", "us-east-1"),
    ("anthropic.claude-opus-4-5-20251101-v1:0", "us-east-1"),
    ("openai.gpt-5.6-terra", "us-west-2"),
    ("openai.gpt-5.5", "us-west-2"),
    ("amazon.nova-pro-v1:0", "us-east-1"),
    ("amazon.nova-2-lite-v1:0", "us-east-1"),
    ("mistral.pixtral-large-2502-v1:0", "us-east-1"),
    ("google.gemma-3-27b-it", "us-east-1"),
    ("meta.llama4-maverick-17b-instruct-v1:0", "us-east-1"),
    ("moonshotai.kimi-k3", "us-east-1"),
]

PROMPT = """\
This image is a COLUMN CROP from a page of a Sanskrit book printed in \
Devanagari by the Venkateshvara Press, Bombay (Durgā Saptaśatī with seven \
commentaries). Because it is a column crop, most lines are cut off mid-word at \
the right edge. That is expected.

Transcribe the Devanagari text EXACTLY as printed. Rules:

- Output ONE line of output for each printed line of text, in order, top to \
bottom. This matters: the lines get stitched back together later.
- Output ONLY the transcribed text. No translation, transliteration, \
commentary, explanation, or line numbers.
- Transcribe each line as far as it is legible. Where a line is cut off at the \
right edge, transcribe the partial word as far as you can see it and stop. Do \
not guess the rest of a cut-off word.
- Preserve every danda (।) and double danda (॥), all verse numbers, and \
quotation marks around citations as printed.
- Do NOT normalise, correct, or modernise the orthography or sandhi. \
Reproduce exactly what is on the page, including archaic spellings.
- This typeface makes certain conjuncts easy to confuse. Look carefully at: \
स्व vs ख, त्व vs ल, श्र vs श्न, ब्र vs व्र, द्ध vs द्र, प्त vs भ, ऋ vs क.
- If a character is genuinely illegible, emit ⟨?⟩ there rather than guessing.

Transcribe now."""


def prep_image(path, width=None):
    im = Image.open(path).convert("RGB")
    if width and im.width > width:
        h = round(im.height * width / im.width)
        im = im.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=95)
    return buf.getvalue(), im.size


def normalise(s):
    """Strip model chatter and whitespace noise for fair comparison."""
    s = s.strip()
    # drop markdown fences and any leading english preamble line
    s = re.sub(r"^```[a-z]*\n?|```$", "", s, flags=re.M).strip()
    lines = [ln for ln in s.split("\n") if ln.strip()]
    # discard pure-ASCII lines (model commentary), keep Devanagari lines
    keep = [ln for ln in lines if re.search(r"[\u0900-\u097F]", ln)]
    s = " ".join(keep) if keep else " ".join(lines)
    return re.sub(r"\s+", " ", s).strip()


def score(gold, hyp):
    g, h = gold.split(), hyp.split()
    if not g:
        return 0.0, 0.0
    sm = difflib.SequenceMatcher(None, g, h, autojunk=False)
    wacc = sum(b.size for b in sm.get_matching_blocks()) / len(g)
    gc, hc = "".join(g), "".join(h)
    sm2 = difflib.SequenceMatcher(None, gc, hc, autojunk=False)
    cacc = sum(b.size for b in sm2.get_matching_blocks()) / len(gc)
    return wacc, cacc


def invoke(model_id, region, img_bytes, session):
    """Call Converse, falling back to the us. inference profile if required."""
    client = session.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(read_timeout=600, retries={"max_attempts": 3}),
    )
    msg = [
        {
            "role": "user",
            "content": [
                {"image": {"format": "jpeg", "source": {"bytes": img_bytes}}},
                {"text": PROMPT},
            ],
        }
    ]
    # Some models (OpenAI, Kimi, newest Claude) reject temperature outright.
    cfg = {"maxTokens": 8192}
    if not re.match(r"^(openai\.|moonshotai\.|anthropic\.claude-(opus|sonnet)-5)", model_id):
        cfg["temperature"] = 0
    kwargs = dict(messages=msg, inferenceConfig=cfg)
    last = "all attempts failed"
    for mid in (model_id, f"us.{model_id}"):
        try:
            t0 = time.time()
            r = client.converse(modelId=mid, **kwargs)
            txt = "".join(
                c.get("text", "") for c in r["output"]["message"]["content"]
            )
            u = r.get("usage", {})
            return {
                "text": txt,
                "secs": round(time.time() - t0, 1),
                "in_tok": u.get("inputTokens"),
                "out_tok": u.get("outputTokens"),
                "resolved_id": mid,
            }
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msgtxt = e.response["Error"]["Message"]
            if code in ("ValidationException", "AccessDeniedException") and mid == model_id:
                last = f"{code}: {msgtxt}"
                continue
            return {"error": f"{code}: {msgtxt}"}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {str(e)}"}
    return {"error": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("crop")
    ap.add_argument("gold")
    ap.add_argument("--models", default="")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    gold = normalise(open(args.gold, encoding="utf-8").read())
    img, size = prep_image(args.crop, args.width)
    print(f"crop {args.crop} -> {size[0]}x{size[1]}, {len(img)/1e6:.2f} MB")
    print(f"gold: {len(gold.split())} words\n")

    cands = CANDIDATES
    if args.models:
        want = set(args.models.split(","))
        cands = [c for c in CANDIDATES if c[0] in want]

    session = boto3.Session(profile_name=PROFILE)
    results = {}

    def run(c):
        mid, region = c
        return mid, invoke(mid, region, img, session)

    with ThreadPoolExecutor(max_workers=6) as ex:
        for mid, res in ex.map(run, cands):
            if "error" not in res:
                hyp = normalise(res["text"])
                res["wacc"], res["cacc"] = score(gold, hyp)
                res["hyp"] = hyp
            results[mid] = res
            print(f"  done: {mid}")

    print(f"\n{'model':44s} {'word%':>7s} {'char%':>7s} {'secs':>6s} {'out_tok':>8s}")
    print("-" * 78)
    ranked = sorted(
        results.items(), key=lambda kv: -kv[1].get("wacc", -1)
    )
    for mid, r in ranked:
        if "error" in r:
            print(f"{mid:44s}   ERROR  {r['error'][:60]}")
        else:
            print(
                f"{mid:44s} {100*r['wacc']:7.1f} {100*r['cacc']:7.1f} "
                f"{r['secs']:6.1f} {str(r['out_tok']):>8s}"
            )

    out = args.out or "work/bakeoff_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {"crop": args.crop, "size": size, "gold": gold, "results": results},
            f,
            ensure_ascii=False,
            indent=1,
        )
    print(f"\nfull transcriptions -> {out}")


if __name__ == "__main__":
    main()
