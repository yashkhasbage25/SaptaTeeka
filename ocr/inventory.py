"""
Build a page inventory across all three volumes.

Every page of this edition carries a running header of the form

    <folio>   दुर्गासप्तशती ।   [ <section name>
    [ <section name>   गुप्तवत्यादिसप्तटीकासंवलिता ।   <folio>

so the header line alone tells us the printed folio number and which
section (aṅga / adhyāya / rahasya) the page belongs to. That gives an
authoritative scan -> section map without trusting the OCR body text.

Writes ocr/work/inventory.json
"""
import json
import os
import re
import sys

import hocr_tools

HERE = os.path.dirname(os.path.abspath(__file__))

DEVANAGARI_DIGITS = "०१२३४५६७८९"
DIG_MAP = {d: str(i) for i, d in enumerate(DEVANAGARI_DIGITS)}

# Section names as they appear in running headers, mapped to our slugs.
# OCR mangles these, so we match on a distinctive, OCR-robust substring.
SECTION_PATTERNS = [
    ("upodghata", r"पोद्?घात|पोद्धात|उपोद्"),
    ("kavacham", r"कवच"),
    ("argala", r"अर्गल|र्गला"),
    ("keelakam", r"कीलक"),
    ("mantravibhaga", r"मन्त्रविभाग|मन्त्रविभ"),
    ("prayogavidhi", r"प्रयोगविधि|प्रयोगवि"),
    ("rahasya_pradhanika", r"प्राधानिक"),
    ("rahasya_vaikritika", r"वैकृतिक"),
    ("rahasya_murti", r"मूर्तिरहस|मूर्तिर"),
]

ADHYAYA_ORDINALS = [
    ("1", r"प्रथम"),
    ("2", r"द्वितीय|द्िवतीय"),
    ("3", r"तृतीय|त्तीय"),
    ("4", r"चतुर्थ|चतुर्य"),
    ("5", r"पञ्चम|पश्चम|पंचम"),
    ("6", r"षष्ठ|षष्ट"),
    ("7", r"सप्तम"),
    ("8", r"अष्टम|ष्टम"),
    ("9", r"नवम"),
    ("10", r"दशम"),
    ("11", r"एकादश|कादश"),
    ("12", r"द्वादश|द्िवादश"),
    ("13", r"त्रयोदश|योदश"),
]


# Printed folio numbers run continuously across the three volumes, so a scan
# index maps to a folio by a per-volume constant. Derived by taking the modal
# (scan - folio) offset over all pages where the header digits OCR'd cleanly,
# and spot-checked against the page images (v1 scan 20 == folio १०).
FOLIO_OFFSET = {1: -10, 2: +90, 3: +190}
# Scans before this are front matter (covers, title page, contents) with no folio.
FIRST_NUMBERED_SCAN = {1: 11, 2: 0, 3: 0}


def dev_to_int(s):
    digits = "".join(DIG_MAP[c] for c in s if c in DIG_MAP)
    return int(digits) if digits else None


def folio_from_scan(vol, scan):
    """Folio implied by the linear model, or None for front matter."""
    if scan < FIRST_NUMBERED_SCAN[vol]:
        return None
    return scan + FOLIO_OFFSET[vol]


def header_words(page, frac=0.085):
    """Words sitting in the top band of the page = the running header."""
    _, _, _, ph = page.bbox
    if not ph:
        return []
    cutoff = ph * frac
    return [w for w in page.words if w.bbox[3] <= cutoff]


def folio_of(page):
    for w in header_words(page):
        n = dev_to_int(w.text)
        if n is not None and 1 <= n <= 999:
            return n
    return None


def classify(header_text, body_head):
    """Identify the section from the running header, falling back to body."""
    probe = header_text + " " + body_head
    for slug, pat in SECTION_PATTERNS:
        if re.search(pat, probe):
            return slug
    # adhyāya headers read like "मधुकैटभवधः प्रथमोऽध्यायः" or just the ordinal
    if re.search(r"ध्याय|ऽध्या", probe):
        for num, pat in ADHYAYA_ORDINALS:
            if re.search(pat, probe):
                return f"adhyaya_{num}"
        return "adhyaya_?"
    return None


def build():
    inventory = []
    for vol in (1, 2, 3):
        path = os.path.join(HERE, "source", f"v{vol}_hocr.html")
        pages = hocr_tools.parse(path)
        for p in pages:
            hw = header_words(p)
            htext = " ".join(w.text for w in hw)
            body = [w for w in p.words if w not in hw]
            body_head = " ".join(w.text for w in body[:25])
            inventory.append(
                {
                    "vol": vol,
                    "scan": p.index,
                    "image": p.image.split("/")[-1],
                    "folio": folio_from_scan(vol, p.index),
                    "folio_ocr": folio_of(p),
                    "header": htext,
                    "section": classify(htext, body_head),
                    "words": len(p.words),
                    "mean_conf": round(p.mean_conf, 1),
                    "low_conf_frac": round(
                        len(p.low_conf(70)) / max(len(p.words), 1), 3
                    ),
                }
            )
    out = os.path.join(HERE, "work", "inventory.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(inventory, f, ensure_ascii=False, indent=1)
    return inventory


def report(inv):
    print(f"{len(inv)} pages total\n")
    # forward-fill section so we can see runs
    cur = None
    runs = []
    for row in inv:
        s = row["section"] or cur
        if s != cur:
            runs.append([s, row["vol"], row["scan"], row["scan"], row["folio"]])
            cur = s
        else:
            if runs:
                runs[-1][3] = row["scan"]
    print(f"{'section':26s} {'vol':>3s} {'scans':>12s} {'pages':>6s}")
    print("-" * 54)
    for s, vol, a, b, folio in runs:
        print(f"{str(s):26s} {vol:3d} {f'{a}-{b}':>12s} {b-a+1:6d}")
    unknown = sum(1 for r in inv if r["section"] is None)
    print(f"\npages with unidentified header: {unknown}")


if __name__ == "__main__":
    inv = build()
    report(inv)
