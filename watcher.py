"""
Rebuild the site in a loop while editing the XML.

This used to hand-roll its own build: it wrote `base_html.index_html` and
called `chapter_to_html(root)` with no nav and no availability set, for a
hardcoded list of two sections. So the pages it produced had an empty sidebar
and no prev/next links, and it wrote them straight into `docs/` -- the
published directory -- regardless of which face of the site you were working
on.

It now delegates to converter.build(), which is the one place that knows how
to resolve sources, build the nav and keep the public and proof builds apart.

    python watcher.py                 rebuild docs/      every few seconds
    python watcher.py --proof         rebuild localsite/ every few seconds
    python watcher.py --proof kavacham        one section only

Not for deploy rebuilds -- run `converter.py` once for those.
"""
import importlib
import sys
import time

import base_html
import converter

INTERVAL = 3


def main():
    args = sys.argv[1:]
    proof = "--proof" in args
    rest = [a for a in args if not a.startswith("--")]
    only = rest[0] if rest else None

    target = "localsite/" if proof else "docs/"
    print(f"watching XML sources, rebuilding {target} every {INTERVAL}s "
          f"(ctrl-c to stop)")

    while True:
        # Reloaded so edits to the template and stylesheet-facing markup are
        # picked up without restarting the loop.
        importlib.reload(base_html)
        importlib.reload(converter)
        try:
            converter.build(only, proof=proof)
        except Exception as e:                      # keep watching on a typo
            print(f"build failed: {type(e).__name__}: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
