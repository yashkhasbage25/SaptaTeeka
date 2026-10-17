"""
Build the site from the XML sources.

Sources are looked up per section, preferring a hand-corrected file in
sanitized/ over the machine-generated one in sanitized_auto/. That way
correcting a section by hand is just a matter of moving or editing the file in
sanitized/, and the build will stop using the generated version for it.

Two builds, two audiences
-------------------------
    python converter.py            -> docs/       the public reading edition
    python converter.py --proof    -> localsite/  the maintainer's copy

The public build carries no flags, no confidence badges and no provenance: a
reader has no use for the pipeline's opinion of its own output. The proof
build surfaces all of it, so a bad reading is hard to miss while working
through a chapter.

docs/ is the GitHub Pages publishing source, so it must stay clean. localsite/
is gitignored and never leaves the machine. Public is the default precisely so
that a deploy cannot accidentally ship working notes.

    python converter.py kavacham           one section
    python converter.py --proof kavacham   one section, maintainer copy
"""
import os
import os.path as osp
import sys
import xml.etree.ElementTree as ET

import base_html

HERE = osp.dirname(osp.abspath(__file__))
HAND = osp.join(HERE, "sanitized")
AUTO = osp.join(HERE, "sanitized_auto")
DOCS = osp.join(HERE, "docs")
LOCAL = osp.join(HERE, "localsite")


warnings = []


def source_for(slug):
    """
    Hand-corrected XML wins over the generated one, but only if it actually
    parses. sanitized/ currently holds at least one file that is still a raw
    OCR paste rather than marked-up XML, and a half-finished file should not
    be able to break the whole build.
    """
    for d, kind in ((HAND, "hand"), (AUTO, "auto")):
        p = osp.join(d, f"{slug}.xml")
        if not osp.exists(p):
            continue
        try:
            ET.parse(p)
            return p, kind
        except ET.ParseError as e:
            warnings.append(f"{osp.relpath(p, HERE)} is not well-formed XML ({e}); skipping")
    return None, None


def resolve_sources():
    """
    Map each known section to a usable source file.

    Resolved up front so the nav only links pages that will actually exist;
    computing it from "an .xml file is present" produced links to pages that
    were then skipped as unparseable.
    """
    sources = {}
    for slug, _label in base_html.DOCUMENTS:
        if slug == "index":
            continue
        src, kind = source_for(slug)
        if src:
            sources[slug] = (src, kind)
    return sources


def write_sitemap(sources):
    """
    sitemap.xml listing only pages that actually exist.

    Worth having for a reference text: without it, a crawler has to discover
    23 pages by following the sidebar, and sections added later can sit
    unindexed for weeks.
    """
    import datetime

    today = datetime.date.today().isoformat()
    urls = ["index.html"] + [
        f"{slug}.html" for slug, _ in base_html.DOCUMENTS if slug in sources
    ]
    body = "\n".join(
        f"  <url><loc>{base_html.SITE_URL}/{u}</loc>"
        f"<lastmod>{today}</lastmod>"
        f"<priority>{'1.0' if u == 'index.html' else '0.8'}</priority></url>"
        for u in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )
    with open(osp.join(DOCS, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    return len(urls)


def write_robots():
    """
    robots.txt. The proofreading view is an internal tool holding 134 MB of
    page scans; it should not be crawled, and neither should the review queue.
    """
    txt = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /proof/\n"
        "Disallow: /review.html\n"
        f"\nSitemap: {base_html.SITE_URL}/sitemap.xml\n"
    )
    with open(osp.join(DOCS, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(txt)


def build(only=None, proof=False):
    base_html.PROOF_MODE = proof
    outdir = LOCAL if proof else DOCS
    os.makedirs(outdir, exist_ok=True)
    if proof:
        link_shared_assets(outdir)
    sources = resolve_sources()
    have = set(sources) | {"index"}
    built = []

    if only in (None, "index"):
        with open(osp.join(outdir, "index.html"), "w", encoding="utf-8") as f:
            f.write(
                base_html.make_index(
                    base_html.build_nav(have, "index"), available=have
                )
            )
        built.append("index")

    for slug, _label in base_html.DOCUMENTS:
        if slug == "index" or (only and slug != only):
            continue
        if slug not in sources:
            continue
        src, kind = sources[slug]
        root = ET.parse(src).getroot()
        html = base_html.chapter_to_html(
            root,
            nav=base_html.build_nav(have, slug),
            current=slug,
            available=have,
        )
        dest = osp.join(outdir, f"{slug}.html")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(html)
        built.append(f"{slug} ({kind})")

    if not proof:
        # Only the public build gets crawl instructions and a sitemap; the
        # local copy is never served to anyone.
        write_sitemap(sources)
        write_robots()

    print(f"built {len(built)} pages into {osp.basename(outdir)}/ "
          f"({'proof' if proof else 'public'} mode):")
    for b in built:
        print(f"  {b}")
    if warnings:
        print("\nWARNING skipped sources:")
        for w in warnings:
            print(f"  {w}")
    if base_html.unknown_tags:
        print("\nWARNING unhandled XML tags encountered:")
        for t in sorted(base_html.unknown_tags):
            print(f"  {t}")
    return built


def link_shared_assets(outdir):
    """
    Point the local copy at the same css/js/images as the public build rather
    than duplicating them, so a style change shows up in both.
    """
    for asset in ("css", "js", "images"):
        src = osp.join(DOCS, asset)
        dst = osp.join(outdir, asset)
        if osp.exists(src) and not osp.exists(dst):
            os.symlink(osp.relpath(src, outdir), dst)
    # the proofreading tools live under docs/ but are gitignored; link them in
    for tool in ("proof", "review.html"):
        src = osp.join(DOCS, tool)
        dst = osp.join(outdir, tool)
        if osp.exists(src) and not osp.exists(dst):
            os.symlink(osp.relpath(src, outdir), dst)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    proof = "--proof" in args
    rest = [a for a in args if not a.startswith("--")]
    build(rest[0] if rest else None, proof=proof)
