"""
Parse archive.org ABBYY/tesseract hOCR into per-page text with word confidences.

The hOCR layer is the *existing* OCR (tesseract 5.3.0, lang=san). We use it as:
  - a second opinion to diff against VLM transcription
  - a source of word-level confidence (x_wconf) to pre-flag suspect spans
  - a source of bounding boxes, so a suspect word can be cropped out of the
    page image and re-examined in isolation
"""
import re
import sys
from dataclasses import dataclass, field


WORD_RE = re.compile(
    r'<span class="ocrx_word"[^>]*title="bbox (\d+) (\d+) (\d+) (\d+);[^"]*?x_wconf (\d+)[^"]*"[^>]*>(.*?)</span>',
    re.S,
)
PAGE_SPLIT_RE = re.compile(r'<div class="ocr_page" id="(page_\d+)" title="([^"]*)"')
# tesseract's own line segmentation; its layout analysis is reliable even where
# its character recognition is not, so we reuse the line boxes rather than
# re-deriving them from word positions.
LINE_SPLIT_RE = re.compile(
    r'<span class="(?:ocr_line|ocr_caption|ocr_textfloat)" id="(line_[\d_]+)" title="bbox (\d+) (\d+) (\d+) (\d+)'
)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Word:
    text: str
    conf: int
    bbox: tuple


@dataclass
class Line:
    line_id: str
    bbox: tuple
    words: list = field(default_factory=list)

    @property
    def text(self):
        return " ".join(w.text for w in self.words)

    @property
    def mean_conf(self):
        return sum(w.conf for w in self.words) / len(self.words) if self.words else 0.0


@dataclass
class Page:
    page_id: str
    index: int
    image: str
    bbox: tuple
    words: list = field(default_factory=list)
    lines: list = field(default_factory=list)

    @property
    def text(self):
        return " ".join(w.text for w in self.words)

    @property
    def mean_conf(self):
        return sum(w.conf for w in self.words) / len(self.words) if self.words else 0.0

    def low_conf(self, threshold=70):
        return [w for w in self.words if w.conf < threshold]


def _unescape(s):
    return (
        s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )


def parse(path):
    """Yield Page objects from an hOCR file."""
    html = open(path, encoding="utf-8").read()
    marks = list(PAGE_SPLIT_RE.finditer(html))
    pages = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)
        chunk = html[start:end]
        title = m.group(2)
        img = re.search(r'image &quot;([^&]*)&quot;', title)
        bbox = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", title)
        page = Page(
            page_id=m.group(1),
            index=i,
            image=img.group(1) if img else "",
            bbox=tuple(map(int, bbox.groups())) if bbox else (0, 0, 0, 0),
        )
        # split the page into tesseract's own lines, then fill each with words
        lmarks = list(LINE_SPLIT_RE.finditer(chunk))
        for li, lm in enumerate(lmarks):
            lstart = lm.end()
            lend = lmarks[li + 1].start() if li + 1 < len(lmarks) else len(chunk)
            line = Line(
                line_id=lm.group(1),
                bbox=tuple(int(lm.group(i)) for i in range(2, 6)),
            )
            for w in WORD_RE.finditer(chunk[lstart:lend]):
                x0, y0, x1, y1, conf, text = w.groups()
                text = _unescape(TAG_RE.sub("", text)).strip()
                if text:
                    word = Word(
                        text, int(conf), (int(x0), int(y0), int(x1), int(y1))
                    )
                    line.words.append(word)
                    page.words.append(word)
            if line.words:
                page.lines.append(line)
        page.lines.sort(key=lambda l: l.bbox[1])
        pages.append(page)
    return pages


if __name__ == "__main__":
    path = sys.argv[1]
    pages = parse(path)
    print(f"{len(pages)} pages")
    for p in pages:
        lo = len(p.low_conf(70))
        print(
            f"  p{p.index:03d} words={len(p.words):5d} "
            f"meanconf={p.mean_conf:5.1f} low(<70)={lo:4d} "
            f"({100*lo/max(len(p.words),1):4.1f}%)"
        )
