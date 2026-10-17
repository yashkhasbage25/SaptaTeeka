"""
Fair scoring for Devanagari transcriptions.

Some models emit ASCII lookalikes for Devanagari punctuation (colon for
visarga, pipe for danda, hyphen for the em dash used in this edition). Those
are encoding artefacts, not reading errors, and are trivially fixed in
post-processing, so scoring must not conflate them with genuine misreadings.

Two scores are reported:
  raw    - exact match, artefacts included
  norm   - after folding the known artefact classes
The gap between them tells you how much cheap post-processing is worth.
"""
import difflib
import re
import unicodedata

# ASCII / near-miss lookalikes -> correct Devanagari
FOLD = {
    ":": "ः",   # colon            -> visarga
    "ʼ": "ऽ",   # modifier apostrophe -> avagraha
    "'": "ऽ",   # ASCII apostrophe used for avagraha by some models
    "|": "।",   # pipe             -> danda
    "॥": "॥",
    "–": "—",   # en dash          -> em dash
    "-": "—",
    "‐": "—",
}

UNCERTAIN = re.compile(r"[⟨<]\?[⟩>]")


def fold(s):
    s = unicodedata.normalize("NFC", s)
    s = UNCERTAIN.sub("", s)
    for a, b in FOLD.items():
        s = s.replace(a, b)
    # quote marks around citations vary; neutralise them
    s = re.sub(r"[“”‘’\"`^]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def accuracy(gold, hyp):
    g, h = gold.split(), hyp.split()
    if not g:
        return 0.0, 0.0
    sm = difflib.SequenceMatcher(None, g, h, autojunk=False)
    wacc = sum(b.size for b in sm.get_matching_blocks()) / len(g)
    gc, hc = "".join(g), "".join(h)
    sm2 = difflib.SequenceMatcher(None, gc, hc, autojunk=False)
    cacc = sum(b.size for b in sm2.get_matching_blocks()) / max(len(gc), 1)
    return wacc, cacc


def both(gold, hyp):
    raw = accuracy(gold, hyp)
    norm = accuracy(fold(gold), fold(hyp))
    return raw, norm
