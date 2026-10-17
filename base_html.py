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
    <!-- Meta -->
    <meta name="keywords" content="{keywords}" />
    <meta name="author" content="Yash Khasbage">
    <meta name="robots" content="index, follow" />
    <meta name="description" content="{description}">

    <!-- Canonical: the site is reachable on more than one hostname, so every
         page names the single address search engines should credit. -->
    <link rel="canonical" href="{canonical}" />

    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="{site_name}" />
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{description}" />
    <meta property="og:url" content="{canonical}" />
    <meta name="twitter:card" content="summary" />

    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="shortcut icon" type="image/png" href="images/favicon.png">
    <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="css/main.css" type="text/css" />
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script rel="text/javascript" src="js/main.js" ></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Eczar:wght@400..800&family=Halant:wght@300;400;500;600;700&family=Laila:wght@300;400;500;600;700&family=Martel:wght@200;300;400;600;700;800;900&family=Noto+Sans:ital,wght@0,100..900;1,100..900&family=Yatra+One&display=swap');
    </style>
</head>
<body>

<!-- Navbar -->
<div class="d-flex align-items-center justify-content-between p-3">
  <button id="toggleNav" class="btn btn-dark">&#9776;</button>
</div>
<nav class="navbar martel-bold">
  <div class="p-3">
    <h2>
      <a href="index.html" class="nav-link book-title">सप्तशती
       सप्तटीका
      </a>
    </h2>
    <ul class="section-link">
{nav}
    </ul>
  </div>
</nav>

<!-- Content -->
{proof_banner}
<div class="content">
  {content}
</div>

<!-- Bootstrap JS and jQuery -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js" 
  integrity="sha512-v2CJ7UaYy4JwqLDIrZUI/4hqeoQieOmAZNXBeQyjo21dadnwR+8ZaIJVT8EE2iyI61OV8e6M8PP2/4hpQINQ/g==" 
  crossorigin="anonymous" referrerpolicy="no-referrer"></script>

<script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.4/dist/umd/popper.min.js"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
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


def head_fields(slug):
    title, desc = page_meta(slug)
    page = "index.html" if slug == "index" else f"{slug}.html"
    return {
        "title": ("[proof] " if PROOF_MODE else "") + title,
        "description": desc,
        "keywords": KEYWORDS,
        # The canonical always names the public address. The local copy is
        # never served, and must never invite indexing of itself.
        "canonical": f"{SITE_URL}/{page}",
        "site_name": SITE_NAME,
        "proof_banner": PROOF_BANNER if PROOF_MODE else "",
    }


def build_nav(available=None, current=None):
    """
    Nav markup for the sidebar. Sections with no page built yet are rendered
    as inert text rather than dead links, so the nav always reflects what
    actually exists on disk.
    """
    rows = []
    for slug, label in DOCUMENTS:
        cls = "nav-link"
        if slug == current:
            cls += " active-section"
        if available is None or slug in available:
            rows.append(
                f'      <div class="nav-item">'
                f'<a class="{cls}" href="{slug}.html">{label}</a></div>'
            )
        else:
            rows.append(
                f'      <div class="nav-item">'
                f'<span class="nav-link pending">{label}</span></div>'
            )
    return "\n".join(rows)

# SaptaTeeka
index_content = """
<center>
<div class="fancy-heading">
    ॥ श्रीसिद्धिबुद्धिसहितश्रीमद्गणाधिपतये नमः ॥
    <br>
    Sharing an important book that went out of printing - Saptashati-SaptaTeeka.
    <br>
</div>
<img src="images/stuyate-sa-na-kim-janaih.png" class="fancy-image-border">
</center>
"""

def make_index(nav=""):
    return base_html.format(
        content=index_content, nav=nav, **head_fields("index")
    )


index_html = make_index(build_nav())

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


def chapter_to_html(chapter, nav="", current=None):
    """
    Converts a chapter element to a full HTML page.
    """
    innerhtml = '<div class="container noto-sans-regular">'
    for child in chapter:
        if child.tag == "head":
            title = child[0].text if len(child) else ""
            innerhtml += f'<p class="section-title halant-regular">{title}</p>'
        elif child.tag != "body":
            continue
        else:
            for subbody in child:
                tag = subbody.tag
                badge = review_badge(subbody)

                if tag == "uvacha":
                    innerhtml += '<center class="uvacha noto-sans-italic">'
                    innerhtml += f"<p>{render_inline(subbody)}{badge}</p>"
                    innerhtml += "</center>"

                elif tag == "moolam":
                    idx = _attr(subbody, "shloka-index")
                    anchor = f' id="shloka-{idx}"' if idx else ""
                    innerhtml += f"<div{anchor}>"
                    innerhtml += (
                        f'<p class="h5 teeka-name">{roman2dev["moolam"]}{badge}</p>'
                    )
                    innerhtml += format_shloka(render_inline(subbody))
                    innerhtml += "</div>"

                elif tag == "teeka":
                    name = subbody.get("name")
                    label = roman2dev.get(name)
                    if label is None:
                        unknown_tags.add(f"teeka[name={name}]")
                        label = name or "?"
                    body = render_inline(subbody)
                    if not body.strip():
                        continue
                    recovered = ""
                    if PROOF_MODE and _attr(subbody, "name-recovered") == "yes":
                        recovered = (
                            '<span class="review-badge" title="Commentary name '
                            'was unreadable and inferred from its printed '
                            'number &mdash; please verify">&#9873;</span>'
                        )
                    innerhtml += f'<div class="teeka teeka-{name}">'
                    innerhtml += (
                        f'<p class="h5 teeka-name">{label}{recovered}{badge}</p>'
                    )
                    innerhtml += body
                    innerhtml += "</div>"

                else:
                    unknown_tags.add(tag)

    innerhtml += "</div>"
    html = base_html.format(
        content=innerhtml, nav=nav, **head_fields(current or "index")
    )
    html = format_html(html)
    return html