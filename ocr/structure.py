"""
Turn transcribed pages into the project's XML schema.

The printed edition has a consistent structure that we can key off:

  - every page carries a running header with the folio and, in brackets, the
    section name, e.g. "१० दुर्गासप्तशती [ गुप्तवत्युपोद्घातः"
  - the mūla verse comes first, numbered "॥ १६ ॥"
  - each commentary then follows, introduced by its own label, numbered in the
    body chapters, e.g. "( ३ शान्तनवी )", and unnumbered in the aṅgas,
    e.g. "(गुप्तवती)"
  - speaker changes are their own short line, e.g. "ऋषिरुवाच ।"
  - a chapter closes with a colophon, "इति श्रीमार्कण्डेयपुराणे ... अध्यायः"

Uncertainty from the transcription stage is preserved, never smoothed:
⟨?⟩ becomes an <unclear/> element, and any block containing flagged content
carries review="yes" so it can be found again.
"""
import json
import glob
import os
import re
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "work", "pages")

# ---------------------------------------------------------------- commentaries

TEEKA_SLUGS = {
    "गुप्तवती": "guptavati",
    "चतुर्धरी": "chaturdhari",
    "शान्तनवी": "shantanavi",
    "नागोजीभट्टी": "nagojibhatti",
    "नागोजीभट्टि": "nagojibhatti",
    "जगच्चन्द्रचन्द्रिका": "jagachchandrachandrika",
    "दंशोद्धारः": "damshoddhara",
    "दंशोद्धार": "damshoddhara",
    "प्रदीपः": "pradeepa",
    "प्रदीप": "pradeepa",
    "दुर्गाप्रदीपः": "pradeepa",
    "दुर्गाप्रदीप": "pradeepa",
    "मूलम्": "moolam",
}

# Label by commentary number as printed, used to repair a garbled name when
# the number is legible.
TEEKA_BY_NUMBER = {
    1: "guptavati",
    2: "chaturdhari",
    3: "shantanavi",
    4: "nagojibhatti",
    5: "jagachchandrachandrika",
    6: "damshoddhara",
    7: "pradeepa",
}

DEV_DIGITS = {d: str(i) for i, d in enumerate("०१२३४५६७८९")}


def dev_int(s):
    t = "".join(DEV_DIGITS[c] for c in s if c in DEV_DIGITS)
    return int(t) if t else None


# A commentary label: optional number, then the name, inside brackets.
TEEKA_RE = re.compile(r"^\s*[\(\[]\s*([०-९]{0,2})\s*([^\)\]]{2,40}?)\s*[\)\]]\s*")
# "ऋषिरुवाच ।", "ब्रह्मोवाच ।", "राजोवाच ।", "देव्युवाच ।"
UVACHA_RE = re.compile(r"^\s*(\S{0,20}?(?:उवाच|ोवाच|्युवाच))\s*।?\s*$")
# verse number at end of a line: ॥ १६ ॥
VERSENUM_RE = re.compile(r"॥\s*([०-९]+)\s*॥")
COLOPHON_RE = re.compile(r"इति\s*श्री.{0,120}?(ोऽध्यायः|अध्यायः)")
HEADER_RE = re.compile(r"दुर्गासप्तशती|सप्तटीकासंवलिता|दुर्गाष\s*तशती")
SECTION_BRACKET_RE = re.compile(r"\[\s*([^\]]{3,40})")

UNCLEAR = "⟨?⟩"


def norm_teeka(num, name):
    """Resolve a commentary label to a slug, repairing a garbled name from
    its printed number where possible."""
    name = re.sub(r"\s+", "", name)
    if name in TEEKA_SLUGS:
        return TEEKA_SLUGS[name], False
    # fuzzy: a distinctive stem is enough, OCR noise sits in the endings
    for dev, slug in TEEKA_SLUGS.items():
        stem = dev[: max(4, len(dev) - 3)]
        if stem and stem in name:
            return slug, False
    n = dev_int(num) if num else None
    if n in TEEKA_BY_NUMBER:
        return TEEKA_BY_NUMBER[n], True       # recovered from the number
    return None, False


# ------------------------------------------------------------------- sectioning

SECTION_PATTERNS = [
    ("upodghata", r"उपोद्घात|पोद्घात|पोद्धात"),
    ("kavacham", r"कवच"),
    ("argala", r"अर्गला|र्गलास्तोत्र"),
    ("keelakam", r"कीलक"),
    ("mantravibhaga", r"मन्त्रविभाग"),
    ("prayogavidhi", r"प्रयोगविधि|प्रयोगवि"),
    ("rahasya_pradhanika", r"प्राधानिक"),
    ("rahasya_vaikritika", r"वैकृतिक"),
    ("rahasya_murti", r"मूर्तिरहस्य"),
]
ADHYAYA_WORDS = [
    (1, r"प्रथम"), (2, r"द्वितीय"), (3, r"तृतीय"), (4, r"चतुर्थ"),
    (5, r"पञ्चम|पंचम"), (6, r"षष्ठ|षष्ट"), (7, r"सप्तम"), (8, r"अष्टम"),
    (9, r"नवम"), (10, r"दशम"), (11, r"एकादश"), (12, r"द्वादश"),
    (13, r"त्रयोदश"),
]

SECTION_TITLES = {
    "upodghata": "गुप्तवत्युपोद्घातः",
    "kavacham": "देवीकवचम्",
    "argala": "अर्गलास्तोत्रम्",
    "keelakam": "कीलकस्तोत्रम्",
    "mantravibhaga": "सप्तशतीमन्त्रविभागः",
    "prayogavidhi": "प्रयोगविधिः",
    "rahasya_pradhanika": "प्राधानिकं रहस्यम्",
    "rahasya_vaikritika": "वैकृतिकं रहस्यम्",
    "rahasya_murti": "मूर्तिरहस्यम्",
    "frontmatter": "उपक्रमः",
}
for i, nm in enumerate(
    ["प्रथमोऽध्यायः", "द्वितीयोऽध्यायः", "तृतीयोऽध्यायः", "चतुर्थोऽध्यायः",
     "पञ्चमोऽध्यायः", "षष्ठोऽध्यायः", "सप्तमोऽध्यायः", "अष्टमोऽध्यायः",
     "नवमोऽध्यायः", "दशमोऽध्यायः", "एकादशोऽध्यायः", "द्वादशोऽध्यायः",
     "त्रयोदशोऽध्यायः"], 1):
    SECTION_TITLES[f"adhyaya_{i}"] = nm


def classify_header(text):
    """
    Section implied by a page's running header, or None.

    Only the bracketed form counts. An earlier version also probed the bare
    line, which meant any body line *mentioning* a section (the upodghāta
    discusses प्राधानिकरहस्य and प्रथमोऽध्यायः at length) was read as a
    section change and tore the document apart.
    """
    m = SECTION_BRACKET_RE.search(text)
    if not m:
        return None
    probe = m.group(1)
    for slug, pat in SECTION_PATTERNS:
        if re.search(pat, probe):
            return slug
    if re.search(r"ध्याय", probe):
        for n, pat in ADHYAYA_WORDS:
            if re.search(pat, probe):
                return f"adhyaya_{n}"
    return None


def is_header(line, idx, total):
    """Running headers sit on the first or last line and name the book."""
    if 1 < idx < total - 2:
        return False
    if re.match(r"^\s*[०-९]{1,3}\s*$", line.strip()):
        return True
    if not HEADER_RE.search(line):
        return False
    # The book's name appears in body text too; a real running head is short
    # and carries the folio or the bracketed section.
    return len(line) < 90 or bool(SECTION_BRACKET_RE.search(line))


# ---------------------------------------------------------------- page loading


def load_pages():
    recs = []
    for p in sorted(glob.glob(os.path.join(PAGES, "*.json"))):
        r = json.load(open(p, encoding="utf-8"))
        if r.get("empty"):
            continue
        recs.append(r)
    recs.sort(key=lambda r: (r["vol"], r["scan"]))
    return recs


FOLIO_OFFSET = {1: -10, 2: +90, 3: +190}


def folio(vol, scan):
    f = scan + FOLIO_OFFSET[vol]
    return f if f >= 1 else None


def page_stream(recs):
    """
    Flatten pages into a single stream of annotated lines, dropping running
    headers and recording which section each line belongs to.
    """
    stream = []
    current = "frontmatter"
    for r in recs:
        lines = r["lines"]
        flags = r.get("flags", [])
        n = len(lines)
        # A running head describes its own page, so resolve the page's section
        # before emitting any of its lines rather than part-way through.
        header_idx = {i for i, raw in enumerate(lines) if is_header(raw, i, n)}
        hinted = None
        for i in sorted(header_idx):
            h = classify_header(lines[i])
            if h:
                hinted = h
        if hinted:
            current = hinted
        for i, raw in enumerate(lines):
            if i in header_idx:
                continue
            fl = flags[i] if i < len(flags) else {}
            stream.append(
                {
                    "text": raw,
                    "vol": r["vol"],
                    "scan": r["scan"],
                    "folio": folio(r["vol"], r["scan"]),
                    "line": i,
                    "section": current,
                    "review": bool(fl.get("needs_review")),
                    "unclear": raw.count(UNCLEAR),
                }
            )
    return stream


# ------------------------------------------------------------------- structuring


def join_lines(items):
    """
    Join printed lines into running text, repairing words broken across a
    line end. The edition hyphenates such breaks, so a trailing hyphen means
    the word continues on the next line and must be closed up, not spaced.
    """
    out = ""
    for it in items:
        t = it["text"].strip()
        if not t:
            continue
        if out.endswith(("-", "‐", "–", "—")) and not out.endswith(" —"):
            out = out[:-1] + t
        elif out:
            out += " " + t
        else:
            out = t
    return re.sub(r"\s+", " ", out).strip()


class Block:
    """A mūla, uvacha or teeka block: its lines plus provenance."""

    def __init__(self, kind, name=None):
        self.kind = kind
        self.name = name
        self.items = []
        self.recovered_name = False

    @property
    def text(self):
        return join_lines(self.items)

    @property
    def review(self):
        return any(i["review"] for i in self.items)

    @property
    def unclear(self):
        return sum(i["unclear"] for i in self.items)

    @property
    def pages(self):
        seen = []
        for i in self.items:
            key = (i["vol"], i["scan"], i["folio"])
            if key not in seen:
                seen.append(key)
        return seen


def parse_section(lines, default_kind="moolam"):
    """Split one section's line stream into ordered blocks."""
    blocks = []
    cur = Block(default_kind)
    for it in lines:
        t = it["text"].strip()
        if not t:
            continue

        m = TEEKA_RE.match(t)
        if m:
            slug, recovered = norm_teeka(m.group(1), m.group(2))
            if slug:
                if cur.items:
                    blocks.append(cur)
                cur = Block("teeka", slug)
                cur.recovered_name = recovered
                rest = t[m.end():].strip()
                if rest:
                    cur.items.append({**it, "text": rest})
                continue

        if UVACHA_RE.match(t):
            if cur.items:
                blocks.append(cur)
            b = Block("uvacha")
            b.items.append(it)
            blocks.append(b)
            cur = Block(default_kind)
            continue

        if COLOPHON_RE.search(t):
            cur.items.append(it)
            blocks.append(cur)
            cur = Block(default_kind)
            continue

        cur.items.append(it)

    if cur.items:
        blocks.append(cur)
    return split_trailing_moolam(blocks)


# A commentary closes by restating the verse number it has just glossed, e.g.
# "... स पृष्ट इति ॥ १६ ॥". So when a commentary block continues past that
# marker, the continuation is not commentary at all: it is the next mūla
# verse, which the layout places before the following commentary cycle.
TRAILING_VERSE_RE = re.compile(
    r"॥\s*([०-९]+)\s*॥\s*(.+॥\s*([०-९]+)\s*॥)\s*$", re.S
)


def split_trailing_moolam(blocks):
    out = []
    for b in blocks:
        if b.kind != "teeka":
            out.append(b)
            continue
        m = TRAILING_VERSE_RE.search(b.text)
        if not m:
            out.append(b)
            continue
        closed, trailing, nxt = m.group(1), m.group(2), m.group(3)
        if dev_int(nxt) is None or dev_int(closed) is None:
            out.append(b)
            continue
        if dev_int(nxt) <= dev_int(closed):
            out.append(b)
            continue

        # Rebuild the commentary without the trailing verse, and emit the
        # verse as its own mūla block carrying the same provenance.
        head_text = b.text[: m.start(2)].strip()
        kept = Block("teeka", b.name)
        kept.recovered_name = b.recovered_name
        kept.items = [dict(i) for i in b.items]
        if kept.items:
            kept.items = [kept.items[0]]
            kept.items[0]["text"] = head_text
            for src in b.items[1:]:
                kept.items.append({**src, "text": ""})
        out.append(kept)

        mb = Block("moolam")
        mb.items = [{**b.items[-1], "text": trailing.strip()}]
        out.append(mb)
    return out


# ------------------------------------------------------------------ XML output


def xml_text(s):
    """Escape, and turn uncertainty markers into real elements."""
    parts = s.split(UNCLEAR)
    out = escape(parts[0])
    for p in parts[1:]:
        out += '<unclear reason="illegible"/>' + escape(p)
    return out


def verse_chunks(text):
    """Split verse text so each numbered half/full verse is its own line."""
    pieces = re.split(r"(॥\s*[०-९]+\s*॥)", text)
    lines, buf = [], ""
    for p in pieces:
        buf += p
        if re.match(r"^॥\s*[०-९]+\s*॥$", p.strip()):
            lines.append(buf.strip())
            buf = ""
    if buf.strip():
        lines.append(buf.strip())
    return lines


def block_xml(b, indent="        "):
    i2 = indent + "    "
    i3 = i2 + "    "
    attrs = ""
    if b.review:
        attrs += ' review="yes"'
    if b.unclear:
        attrs += f' unclear="{b.unclear}"'
    src = ";".join(
        f"v{v}p{f}" if f else f"v{v}s{s}" for v, s, f in b.pages
    )
    attrs += f' src="{src}"'

    if b.kind == "uvacha":
        return f"{indent}<uvacha{attrs}>{xml_text(b.text)}</uvacha>\n"

    if b.kind == "prose":
        # Continuous prose with no commentary heading of its own.
        s = f'{indent}<teeka name="moolam"{attrs}>\n'
        s += f"{i2}<prose>\n{i3}<prose>\n"
        s += f"{i3}{xml_text(b.text)}\n"
        s += f"{i3}</prose>\n{i2}</prose>\n"
        s += f"{indent}</teeka>\n"
        return s

    if b.kind == "moolam":
        num = VERSENUM_RE.search(b.text)
        idx = f' shloka-index="{dev_int(num.group(1))}"' if num else ""
        s = f"{indent}<moolam{idx}{attrs}>\n"
        for ln in verse_chunks(b.text):
            s += f"{i2}{xml_text(ln)}\n"
        s += f"{indent}</moolam>\n"
        return s

    # teeka
    rec = ' name-recovered="yes"' if b.recovered_name else ""
    s = f'{indent}<teeka name="{b.name}"{rec}{attrs}>\n'
    s += f"{i2}<prose>\n{i3}<prose>\n"
    s += f"{i3}{xml_text(b.text)}\n"
    s += f"{i3}</prose>\n{i2}</prose>\n"
    s += f"{indent}</teeka>\n"
    return s


# Sections that are continuous prose by a single author rather than
# verse-plus-commentary. Their unlabelled text is prose, not mūla verse.
PROSE_SECTIONS = {
    "frontmatter",
    "upodghata",
    "mantravibhaga",
    "prayogavidhi",
}


def build_document(slug, lines):
    default = "prose" if slug in PROSE_SECTIONS else "moolam"
    blocks = parse_section(lines, default)
    title = SECTION_TITLES.get(slug, slug)
    out = "<chapter>\n"
    out += f"    <head>\n        <title>{escape(title)}</title>\n    </head>\n"
    out += "    <body>\n"
    for b in blocks:
        out += block_xml(b)
    out += "    </body>\n</chapter>\n"
    return out, blocks


def main():
    recs = load_pages()
    stream = page_stream(recs)
    by_section = {}
    for it in stream:
        by_section.setdefault(it["section"], []).append(it)

    outdir = os.path.join(HERE, "..", "sanitized_auto")
    os.makedirs(outdir, exist_ok=True)
    manifest = []
    print(f"{len(recs)} pages -> {len(stream)} lines")
    print(f"{'section':26s} {'lines':>6s} {'blocks':>7s} {'review':>7s} {'unclear':>8s}")
    print("-" * 60)
    for slug, lines in by_section.items():
        xml, blocks = build_document(slug, lines)
        path = os.path.join(outdir, f"{slug}.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        rev = sum(1 for b in blocks if b.review)
        unc = sum(b.unclear for b in blocks)
        print(f"{slug:26s} {len(lines):6d} {len(blocks):7d} {rev:7d} {unc:8d}")
        manifest.append(
            {
                "slug": slug,
                "title": SECTION_TITLES.get(slug, slug),
                "xml": f"sanitized_auto/{slug}.xml",
                "lines": len(lines),
                "blocks": len(blocks),
                "review_blocks": rev,
                "unclear": unc,
            }
        )
    with open(os.path.join(HERE, "work", "documents.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest


if __name__ == "__main__":
    main()
