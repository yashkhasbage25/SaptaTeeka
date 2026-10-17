# The one place the public hostname is written down. Everything that needs an
# absolute URL (canonical links, Open Graph tags, the sitemap) derives from
# this, so moving the site is a one-line change rather than a search and
# replace. Keep it without a trailing slash.
SITE_URL = "https://saptashatitika.com"
SITE_NAME = "सप्तशतीटीकासंग्रहः"

# ---------------------------------------------------------------------------
# The repo has two faces and they must not bleed into each other.
#
#   PUBLIC (default)  what readers get. A clean reading edition. No flags, no
#                     confidence badges, no provenance, nothing about the
#                     pipeline that produced it.
#
#   PROOF             what the maintainer gets locally. Every uncertainty
#                     surfaced loudly, so a wrong reading is hard to miss.
#
# Set via converter.py; the default is PUBLIC so a deploy can never
# accidentally ship the working notes.
#
# One thing stays visible in both: a genuine lacuna. Where the scan is
# illegible the public text shows a quiet ⟨…⟩ rather than silently closing
# the gap, because presenting a reconstructed text as if it were complete is
# the one error a reader cannot detect. That is editorial apparatus, not
# proofreading mess, and every critical edition does it.
# ---------------------------------------------------------------------------
PROOF_MODE = False


base_html = """
<!DOCTYPE html>
<html lang="sa">
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Meta -->
    <meta name="keywords" content="{keywords}" />
    <meta name="author" content="Yash Khasbage">
    <meta name="robots" content="{robots}" />
    <meta name="description" content="{description}">
    <meta name="theme-color" content="#1b0708">
    <meta name="color-scheme" content="dark light">

    <!-- Canonical: the site is reachable on more than one hostname, so every
         page names the single address search engines should credit. -->
    <link rel="canonical" href="{canonical}" />

    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="{site_name}" />
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{description}" />
    <meta property="og:url" content="{canonical}" />
    <meta property="og:image" content="{og_image}" />
    <meta property="og:locale" content="sa_IN" />
    <meta name="twitter:card" content="summary" />

    <link rel="shortcut icon" type="image/png" href="images/favicon.png">
    <link rel="apple-touch-icon" href="images/favicon.png">

    <!-- Two Devanagari faces, both drawn for Indic text: Tiro Devanagari
         Sanskrit (cut specifically for Sanskrit, used for the mula verses)
         and Noto Serif Devanagari for commentary prose. Replaces five
         families pulled in through a blocking @import. -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+Devanagari:wght@300..700&family=Tiro+Devanagari+Sanskrit&display=swap">
    <link rel="stylesheet" href="css/main.css" type="text/css" />

    <!-- Applied before first paint so a reader on the paper theme never sees
         a flash of the dark one. -->
    <script>
      (function () {{
        try {{
          var t = localStorage.getItem('st-theme');
          if (t) document.documentElement.setAttribute('data-theme', t);
        }} catch (e) {{}}
      }})();
    </script>
</head>
<body>

<a class="skip-link" href="#main">मुख्यपाठं प्रति / skip to the text</a>
<div class="progress" id="progress" aria-hidden="true"></div>

<header class="topbar">
  <button id="toggleNav" class="iconbtn" type="button"
          aria-controls="sidebar" aria-expanded="false"
          aria-label="अनुक्रमणिका / table of contents">&#9776;</button>
  <span class="topbar__here">{here}</span>
  <button id="toggleTheme" class="iconbtn" type="button"
          aria-label="वर्णविन्यासः / switch reading theme"
          title="switch between the dark and paper reading themes">&#9790;</button>
</header>

<div class="scrim" id="scrim"></div>

<nav class="navbar" id="sidebar" aria-label="अनुक्रमणिका">
  <div class="navbar__head">
    <a href="index.html" class="book-title">{site_name}</a>
    <p class="book-sub">{book_sub}</p>
  </div>
  <div class="navbar__scroll">
    <ul class="section-link">
{nav}
    </ul>
  </div>
  <div class="navbar__foot">{nav_foot}</div>
</nav>

{proof_banner}
<main class="content" id="main">
  {content}
</main>

<button class="iconbtn totop" id="totop" type="button"
        aria-label="उपरि / back to top">&#8593;</button>

<script src="js/main.js"></script>
</body>
</html>
"""


import re
from bs4 import BeautifulSoup   

roman2dev = {
    "moolam": "मूलम्",
    # the seven commentaries, in the order the title page lists them
    "pradeepa": "दुर्गाप्रदीपः",
    "guptavati": "गुप्तवती",
    "chaturdhari": "चतुर्धरी",
    "shantanavi": "शान्तनवी",
    "nagojibhatti": "नागोजीभट्टी",
    "jagachchandrachandrika": "जगच्चन्द्रचन्द्रिका",
    "damshoddhara": "दंशोद्धारः",
}

# Reading order of the whole edition. Drives both the nav and the build, so
# adding a section is a data change here rather than an HTML edit.
DOCUMENTS = [
    ("index", "मुखम्"),
    ("upodghata", "उपोद्घातः"),
    ("kavacham", "कवचम्"),
    ("argala", "अर्गला"),
    ("keelakam", "कीलकम्"),
    ("mantravibhaga", "मन्त्रविभागः"),
    ("prayogavidhi", "प्रयोगविधिः"),
    ("adhyaya_1", "प्रथमोऽध्यायः"),
    ("adhyaya_2", "द्वितीयोऽध्यायः"),
    ("adhyaya_3", "तृतीयोऽध्यायः"),
    ("adhyaya_4", "चतुर्थोऽध्यायः"),
    ("adhyaya_5", "पञ्चमोऽध्यायः"),
    ("adhyaya_6", "षष्ठोऽध्यायः"),
    ("adhyaya_7", "सप्तमोऽध्यायः"),
    ("adhyaya_8", "अष्टमोऽध्यायः"),
    ("adhyaya_9", "नवमोऽध्यायः"),
    ("adhyaya_10", "दशमोऽध्यायः"),
    ("adhyaya_11", "एकादशोऽध्यायः"),
    ("adhyaya_12", "द्वादशोऽध्यायः"),
    ("adhyaya_13", "त्रयोदशोऽध्यायः"),
    ("rahasya_pradhanika", "प्राधानिकं रहस्यम्"),
    ("rahasya_vaikritika", "वैकृतिकं रहस्यम्"),
    ("rahasya_murti", "मूर्तिरहस्यम्"),
]


# Per-page descriptions. Every page previously shared one title and a
# four-word description, which meant search engines saw 23 near-identical
# pages and had no reason to surface any particular one. These name what a
# reader would actually search for.
BOOK = "दुर्गासप्तशती"
BOOK_EN = "Durga Saptashati (Devi Mahatmya)"
TEEKA_LIST = (
    "Durgapradipa, Guptavati, Chaturdhari, Shantanavi, Nagojibhatti, "
    "Jagachchandrachandrika and Damshoddhara"
)

PAGE_META = {
    "index": (
        f"{SITE_NAME} — {BOOK_EN} with seven classical commentaries",
        f"The {BOOK_EN} with its seven classical Sanskrit commentaries — "
        f"{TEEKA_LIST} — restored from the out-of-print Venkateshvara Press "
        f"edition. Full Devanagari text, free to read.",
    ),
    "upodghata": (
        f"उपोद्घातः — Guptavati's introduction | {BOOK_EN}",
        "Bhaskararaya's introduction (upodghata) to the Guptavati commentary "
        f"on the {BOOK_EN}, in Sanskrit.",
    ),
    "kavacham": (
        f"देवीकवचम् — Devi Kavacham with commentaries | {BOOK_EN}",
        "Devi Kavacham, the armour recited before the Durga Saptashati, with "
        "the Guptavati and Durgapradipa commentaries in Sanskrit.",
    ),
    "argala": (
        f"अर्गलास्तोत्रम् — Argala Stotram with commentaries | {BOOK_EN}",
        "Argala Stotram, recited before the Durga Saptashati, with classical "
        "Sanskrit commentaries.",
    ),
    "keelakam": (
        f"कीलकस्तोत्रम् — Keelakam with commentaries | {BOOK_EN}",
        "Keelaka Stotram, the third of the three angas recited before the "
        "Durga Saptashati, with classical Sanskrit commentaries.",
    ),
    "mantravibhaga": (
        f"सप्तशतीमन्त्रविभागः — division of the mantras | {BOOK_EN}",
        "The division of the Durga Saptashati into its seven hundred mantras, "
        "as set out in the Katyayani and other tantras.",
    ),
    "prayogavidhi": (
        f"प्रयोगविधिः — ritual procedure | {BOOK_EN}",
        "The prayoga vidhi, the procedure for reciting the Durga Saptashati, "
        "with commentary.",
    ),
    "rahasya_pradhanika": (
        f"प्राधानिकं रहस्यम् — Pradhanika Rahasya | {BOOK_EN}",
        "Pradhanika Rahasya, the first of the three rahasyas appended to the "
        "Durga Saptashati, with commentaries.",
    ),
    "rahasya_vaikritika": (
        f"वैकृतिकं रहस्यम् — Vaikritika Rahasya | {BOOK_EN}",
        "Vaikritika Rahasya, the second of the three rahasyas appended to the "
        "Durga Saptashati, with commentaries.",
    ),
    "rahasya_murti": (
        f"मूर्तिरहस्यम् — Murti Rahasya | {BOOK_EN}",
        "Murti Rahasya, the third of the three rahasyas appended to the "
        "Durga Saptashati, with commentaries.",
    ),
}

ADHYAYA_SUBJECT = {
    1: "मधुकैटभवधः — the slaying of Madhu and Kaitabha",
    2: "महिषासुरसैन्यवधः — the slaying of Mahishasura's army",
    3: "महिषासुरवधः — the slaying of Mahishasura",
    4: "शक्रादिस्तुतिः — the hymn of Indra and the gods",
    5: "देव्या दूतसंवादः — the Devi's exchange with the messenger",
    6: "धूम्रलोचनवधः — the slaying of Dhumralochana",
    7: "चण्डमुण्डवधः — the slaying of Chanda and Munda",
    8: "रक्तबीजवधः — the slaying of Raktabija",
    9: "निशुम्भवधः — the slaying of Nishumbha",
    10: "शुम्भवधः — the slaying of Shumbha",
    11: "नारायणीस्तुतिः — the Narayani hymn",
    12: "भगवतीवाक्यम् — the Devi's own words",
    13: "सुरथवैश्ययोर्वरप्रदानम् — the boons to Suratha and the merchant",
}

for _i, (_slug, _label) in enumerate(
    [(f"adhyaya_{n}", None) for n in range(1, 14)], 1
):
    _subj = ADHYAYA_SUBJECT[_i]
    PAGE_META[f"adhyaya_{_i}"] = (
        f"अध्यायः {_i} — {_subj.split(' — ')[0]} | {BOOK_EN} with commentaries",
        f"Chapter {_i} of the {BOOK_EN}, {_subj}, with the seven classical "
        f"Sanskrit commentaries: {TEEKA_LIST}.",
    )

KEYWORDS = (
    "Durga Saptashati, Devi Mahatmya, Chandi Path, Saptashati Teeka, "
    "Guptavati, Bhaskararaya, Sanskrit commentary, Markandeya Purana, "
    "दुर्गासप्तशती, देवीमाहात्म्यम्, सप्तशतीटीका"
)


def page_meta(slug):
    """Title and description for a page, falling back to something sensible."""
    if slug in PAGE_META:
        return PAGE_META[slug]
    label = dict(DOCUMENTS).get(slug, slug)
    return (
        f"{label} | {BOOK_EN} with commentaries",
        f"{label} of the {BOOK_EN}, with classical Sanskrit commentaries.",
    )


PROOF_BANNER = (
    '<div class="proof-banner">'
    "maintainer copy &mdash; uncertain readings are flagged; this is not the "
    "published text"
    '<a href="proof/index.html">line-by-line proofreading</a>'
    '<a href="review.html">review queue</a>'
    "</div>"
)


# Shown under the title in the sidebar and as the edition's provenance. The
# site is a restoration of one specific printed book; saying which one is
# part of being a usable edition rather than an anonymous text dump.
EDITION_LINE = "वेङ्कटेश्वरमुद्रणालयः &middot; १९१६"
BOOK_SUB = "सप्तभिः टीकाभिः सह"


def head_fields(slug):
    title, desc = page_meta(slug)
    page = "index.html" if slug == "index" else f"{slug}.html"
    label = dict(DOCUMENTS).get(slug, "")
    return {
        "title": ("[proof] " if PROOF_MODE else "") + title,
        "description": desc,
        "keywords": KEYWORDS,
        # The canonical always names the public address. The local copy is
        # never served, and must never invite indexing of itself -- hence
        # noindex on the proof build as well as the canonical.
        "canonical": f"{SITE_URL}/{page}",
        "robots": "noindex, nofollow" if PROOF_MODE else "index, follow",
        "og_image": f"{SITE_URL}/images/stuyate-sa-na-kim-janaih.png",
        "site_name": SITE_NAME,
        "book_sub": BOOK_SUB,
        "nav_foot": EDITION_LINE,
        # Names the section in the top bar, which on a phone is the only
        # place the reader can see where they are once the drawer is shut.
        "here": label if slug != "index" else SITE_NAME,
        "proof_banner": PROOF_BANNER if PROOF_MODE else "",
    }


# The edition's own divisions, used to break a flat list of 23 links into
# groups a reader can aim at. Headings only; the slugs stay in DOCUMENTS so
# there is still one list to maintain.
NAV_GROUPS = [
    (None, ["index"]),
    ("उपक्रमः", ["upodghata"]),
    ("अङ्गानि", ["kavacham", "argala", "keelakam"]),
    ("विधिः", ["mantravibhaga", "prayogavidhi"]),
    ("अध्यायाः", [f"adhyaya_{n}" for n in range(1, 14)]),
    ("रहस्यानि", ["rahasya_pradhanika", "rahasya_vaikritika", "rahasya_murti"]),
]


def build_nav(available=None, current=None):
    """
    Nav markup for the sidebar. Sections with no page built yet are rendered
    as inert text rather than dead links, so the nav always reflects what
    actually exists on disk.
    """
    labels = dict(DOCUMENTS)
    rows = []
    for heading, slugs in NAV_GROUPS:
        if heading:
            rows.append(f'      <li class="nav-group">{heading}</li>')
        for slug in slugs:
            label = labels.get(slug, slug)
            if available is None or slug in available:
                cls = "nav-link active-section" if slug == current else "nav-link"
                aria = ' aria-current="page"' if slug == current else ""
                rows.append(
                    f'      <li class="nav-item">'
                    f'<a class="{cls}" href="{slug}.html"{aria}>{label}</a></li>'
                )
            else:
                rows.append(
                    f'      <li class="nav-item">'
                    f'<span class="nav-link pending" '
                    f'title="not transcribed yet">{label}</span></li>'
                )
    return "\n".join(rows)


def section_nav(slug, available):
    """
    Previous / next links at the foot of a section.

    Only sections that actually built are offered, so this never produces a
    link to a page that does not exist. Reading a 13-chapter text through the
    sidebar alone means a round trip to the drawer after every chapter.
    """
    if not available:
        return ""
    labels = dict(DOCUMENTS)
    order = [s for s, _ in DOCUMENTS if s in available]
    if slug not in order:
        return ""
    i = order.index(slug)
    prev_slug = order[i - 1] if i > 0 else None
    next_slug = order[i + 1] if i < len(order) - 1 else None
    if not prev_slug and not next_slug:
        return ""

    out = ['<nav class="section-nav" aria-label="क्रमः">']
    if prev_slug:
        out.append(
            f'<a class="prev" href="{prev_slug}.html" rel="prev">'
            f'<span class="dir">&#8592; पूर्वम्</span>{labels[prev_slug]}</a>'
        )
    if next_slug:
        out.append(
            f'<a class="next" href="{next_slug}.html" rel="next">'
            f'<span class="dir">अग्रिमम् &#8594;</span>{labels[next_slug]}</a>'
        )
    out.append("</nav>")
    return "".join(out)

# The commentaries in the order the title page lists them, with the
# transliterations a reader is likely to have searched for.
TEEKA_ROLL = [
    ("दुर्गाप्रदीपः", "Durgapradipa"),
    ("गुप्तवती", "Guptavati"),
    ("चतुर्धरी", "Chaturdhari"),
    ("शान्तनवी", "Shantanavi"),
    ("नागोजीभट्टी", "Nagojibhatti"),
    ("जगच्चन्द्रचन्द्रिका", "Jagachchandrachandrika"),
    ("दंशोद्धारः", "Damshoddhara"),
]


def build_index_content(available=None):
    """
    The landing page.

    It used to be one English sentence and a picture, which left a reader no
    way to tell what edition this is, which commentaries it carries, or how
    much of it is readable yet. All three are answered here, and the counts
    are computed rather than written down so they cannot drift.
    """
    roll = "\n".join(
        f'    <li><span>{dev}</span><span class="rom">{rom}</span></li>'
        for dev, rom in TEEKA_ROLL
    )

    # First readable section after the landing page, for the call to action.
    first = next(
        (s for s, _ in DOCUMENTS
         if s != "index" and (available is None or s in available)),
        None,
    )
    cta = ""
    if first:
        label = dict(DOCUMENTS)[first]
        cta = (
            f'<a class="startreading" href="{first}.html">'
            f'पठनम् आरभताम् &mdash; {label} &#8594;</a>'
        )

    status = ""
    if available is not None:
        total = len([s for s, _ in DOCUMENTS if s != "index"])
        done = len([s for s in available if s != "index"])
        status = (
            '  <div class="panel">\n'
            '    <h2>state of the text</h2>\n'
            f'    <p lang="en">{done} of {total} sections are readable now. '
            "The rest are being transcribed from the scans and will appear "
            "here as they are finished; sections not yet available are listed "
            "in the sidebar but not linked.</p>\n"
            '    <p lang="en">Where the print itself is illegible the text '
            'shows <span class="lacuna">&#10216;&hellip;&#10217;</span> '
            "rather than quietly filling the gap. A reconstruction presented "
            "as the text is the one error a reader cannot catch.</p>\n"
            "  </div>\n"
        )

    return f"""
<div class="hero">
  <p class="hero__invocation">॥ श्रीसिद्धिबुद्धिसहितश्रीमद्गणाधिपतये नमः ॥</p>
  <h1 class="hero__title">{SITE_NAME}</h1>
  <p class="hero__lede" lang="en">The <strong>Durga Saptashati</strong>
    (Devi Mahatmya) with seven classical Sanskrit commentaries, restored from
    the out-of-print Venkateshvara Press edition of 1916. Free to read, in
    full Devanagari.</p>
  <figure class="hero__figure">
    <img src="images/stuyate-sa-na-kim-janaih.png" class="fancy-image-border"
         alt="स्तूयते सा न किं जनैः" width="640" height="960">
    <figcaption class="hero__caption">स्तूयते सा न किं जनैः</figcaption>
  </figure>
  {cta}
</div>

<div class="panel">
  <h2 class="dev">सप्त टीकाः</h2>
  <ul class="teeka-roll">
{roll}
  </ul>
</div>

<div class="panel">
  <h2>about this edition</h2>
  <p lang="en">The Saptashati is read everywhere, but the commentarial
    tradition on it has been effectively out of circulation: this collection
    of seven tikas was last printed a century ago and is not available in
    print today. The scans are being transcribed page by page and marked up
    so that each verse sits with every commentary on it, rather than in
    separate volumes.</p>
  <p lang="en">Each verse is shown as <span lang="sa">मूलम्</span> followed by
    the commentaries on it, each with its own colour in the margin so the
    same voice can be followed down a chapter.</p>
</div>

{status}"""


def make_index(nav="", available=None):
    return base_html.format(
        content=build_index_content(available), nav=nav, **head_fields("index")
    )

def format_html(html_string):
    soup = BeautifulSoup(html_string, 'html.parser')
    formatted_html = soup.prettify()
    return formatted_html

def format_shloka(shloka):
    """
    Formats a shloka to be displayed on a webpage
    """
    lines = shloka.split('\n')
    formatted = '<div class="shloka laila-regular">'
    for line in lines:
        space_danda = r'(?<!\s)।(?!\s)'
        space_double_danda = r'(?<!\s)॥(?!\s)'
        line = re.sub(space_danda, ' ।', line)
        line = re.sub(space_double_danda, ' ॥', line)
        formatted += f'<div>{line}</div>'
    formatted += '</div>'
    return formatted

# Tags that carry running text and are rendered inline. Anything not listed
# here is reported by the build rather than silently dropped or crashing the
# way the old set_trace() fallbacks did.
INLINE_RENDERERS = {
    "prose": lambda e: "",
    "quote": lambda e: '<i class="quote">',
    "shruti": lambda e: '<i class="shruti">',
    "unknown": lambda e: "<i>",
    "verse": lambda e: None,          # handled as a block
}

unknown_tags = set()


def _attr(e, name, default=""):
    v = e.get(name)
    return v if v is not None else default


def render_inline(elem):
    """
    Render an element's mixed content (text, children, tails) to HTML.

    Works for both the hand-written XML and the generated XML, because it
    recurses over whatever nesting it finds instead of assuming a fixed depth.
    """
    out = ""
    if elem.text:
        out += elem.text
    for child in elem:
        tag = child.tag
        inner = render_inline(child)

        if tag == "ignore":
            pass                                  # printed label, not content
        elif tag == "unclear":
            reason = _attr(child, "reason", "illegible in the scan")
            if PROOF_MODE:
                # Loud on purpose: this is what the maintainer hunts for.
                out += (
                    f'<span class="unclear" title="Unclear: {reason}'
                    f' &mdash; needs manual check">&#10216;?&#10217;</span>'
                )
            else:
                # Quiet, but still honest that something is missing here.
                out += (
                    f'<span class="lacuna" title="illegible in the original '
                    f'print">&#10216;&hellip;&#10217;</span>'
                )
            out += inner
        elif tag == "doubtful":
            out += (
                f'<span class="doubtful" title="{_attr(child, "comment")}">'
                f"{inner}</span>"
            )
        elif tag == "recheck":
            out += f'<span class="recheck" title="Needs rechecking">{inner}</span>'
        elif tag == "comment":
            out += f'<span class="doubtful" title="{_attr(child, "comment")}">?</span>'
        elif tag == "vyakarana":
            link = _attr(child, "link") or _attr(child, "href")
            span = f'<span class="vyakarana" title="Vyākaraṇa">{inner}</span>'
            out += f'<a href="{link}">{span}</a>' if link else span
        elif tag == "a":
            href = _attr(child, "href")
            out += f'<a href="{href}">{inner}</a>' if href else inner
        elif tag == "quote":
            out += f'<i class="quote">{inner}</i>'
        elif tag == "shruti":
            out += f'<i class="shruti">{inner}</i>'
        elif tag == "unknown":
            out += f"<i>{inner}</i>"
        elif tag == "prose":
            out += inner
        elif tag == "verse":
            out += format_shloka(inner)
        else:
            unknown_tags.add(tag)
            out += inner
        if child.tail:
            out += child.tail
    return out


def review_badge(elem):
    """
    Confidence marker for a block. Maintainer-facing only: a reader has no
    use for the pipeline's opinion of its own output, and it clutters the text.
    """
    if not PROOF_MODE:
        return ""
    if _attr(elem, "review") != "yes":
        return ""
    n = _attr(elem, "unclear")
    detail = f"{n} unclear spot(s)" if n else "low confidence"
    src = _attr(elem, "src")
    where = f" [{src}]" if src else ""
    return (
        f'<span class="review-badge" title="Needs manual verification: '
        f'{detail}{where}">&#9873;</span>'
    )


_DEV_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def dev_num(s):
    """
    ASCII digits to Devanagari.

    The printed edition numbers its verses in Devanagari and the text itself
    restates them that way (॥ १ ॥), so a Latin '1' in the margin next to it
    reads as a different numbering system. Only the display form changes --
    the anchor keeps the ASCII number, so existing #shloka-N links still
    resolve.
    """
    return str(s).translate(_DEV_DIGITS)


def _plural(n, singular, plural):
    return f"{dev_num(n)} {singular if n == 1 else plural}"


def section_subtitle(slug, n_verses, teekas):
    """
    The line under a section heading.

    Everything in it is counted from the page that was just built, so it
    cannot claim a chapter carries seven commentaries when the transcription
    only has four.
    """
    bits = []
    if slug and slug.startswith("adhyaya_"):
        try:
            subj = ADHYAYA_SUBJECT.get(int(slug.split("_")[1]))
        except ValueError:
            subj = None
        if subj:
            bits.append(subj)
    if n_verses:
        bits.append(_plural(n_verses, "श्लोकः", "श्लोकाः"))
    if teekas:
        bits.append(_plural(len(teekas), "टीका", "टीकाः"))
    return " &middot; ".join(bits)


def chapter_to_html(chapter, nav="", current=None, available=None):
    """
    Converts a chapter element to a full HTML page.

    The mula verse and the commentaries on it are wrapped together in one
    .verse-group, so the page reads as a sequence of verse units instead of
    an undifferentiated column of blocks. That grouping is the whole point of
    the edition: the commentaries are worth having next to their verse.
    """
    title = ""
    body_html = []
    n_verses = 0
    teekas_seen = []
    group_open = False

    def close_group():
        nonlocal group_open
        if group_open:
            body_html.append("</section>")
            group_open = False

    for child in chapter:
        if child.tag == "head":
            title = child[0].text if len(child) else ""
            continue
        if child.tag != "body":
            continue

        for subbody in child:
            tag = subbody.tag
            badge = review_badge(subbody)

            if tag == "uvacha":
                # A speaker change belongs to neither the verse above nor the
                # one below, so it sits between groups.
                close_group()
                body_html.append(
                    f'<div class="uvacha"><p>{render_inline(subbody)}{badge}</p></div>'
                )

            elif tag == "moolam":
                close_group()
                n_verses += 1
                idx = _attr(subbody, "shloka-index")
                anchor = f' id="shloka-{idx}"' if idx else ""
                # The verse number is the printed edition's own; shown as a
                # permalink because that is what a reader cites.
                num = (
                    f'<a class="verse-no" href="#shloka-{idx}" '
                    f'aria-label="श्लोकः {idx}">॥&nbsp;{dev_num(idx)}&nbsp;॥</a>'
                    if idx else ""
                )
                body_html.append(f'<section class="verse-group"{anchor}>')
                group_open = True
                body_html.append('<div class="verse-block">')
                body_html.append(
                    f'<p class="teeka-name">'
                    f'<span class="label">{roman2dev["moolam"]}</span>'
                    f"{badge}{num}</p>"
                )
                body_html.append(format_shloka(render_inline(subbody)))
                body_html.append("</div>")

            elif tag == "teeka":
                name = subbody.get("name")
                label = roman2dev.get(name)
                if label is None:
                    unknown_tags.add(f"teeka[name={name}]")
                    label = name or "?"
                body = render_inline(subbody)
                if not body.strip():
                    continue
                if label not in teekas_seen:
                    teekas_seen.append(label)
                recovered = ""
                if PROOF_MODE and _attr(subbody, "name-recovered") == "yes":
                    recovered = (
                        '<span class="review-badge" title="Commentary name '
                        'was unreadable and inferred from its printed '
                        'number &mdash; please verify">&#9873;</span>'
                    )
                if not group_open:
                    # A commentary with no verse ahead of it (prose sections,
                    # or a chapter opening mid-gloss). Still gets a group so
                    # the spacing rhythm holds.
                    body_html.append('<section class="verse-group">')
                    group_open = True
                body_html.append(f'<div class="teeka teeka-{name}">')
                body_html.append(
                    f'<p class="teeka-name">'
                    f'<span class="label">{label}</span>'
                    f"{recovered}{badge}</p>"
                )
                body_html.append(body)
                body_html.append("</div>")

            else:
                unknown_tags.add(tag)

    close_group()

    subtitle = section_subtitle(current, n_verses, teekas_seen)
    head = f'<h1 class="section-title">{title}</h1>'
    if subtitle:
        head += f'<p class="section-meta">{subtitle}</p>'
    else:
        head += '<p class="section-meta"></p>'

    innerhtml = (
        '<div class="container">'
        + head
        + "".join(body_html)
        + section_nav(current, available)
        + "</div>"
    )
    html = base_html.format(
        content=innerhtml, nav=nav, **head_fields(current or "index")
    )
    html = format_html(html)
    return html