"""
Page image access: pulls a scan out of the volume's jp2 archive and caches it
as JPEG so repeated runs do not re-decode JPEG2000.
"""
import io
import os
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source")
CACHE = os.path.join(HERE, "work", "pagecache")

_zips = {}


def _zip(vol):
    if vol not in _zips:
        _zips[vol] = zipfile.ZipFile(os.path.join(SRC, f"v{vol}_jp2.zip"))
    return _zips[vol]


def jp2_name(vol, scan):
    return f"saptashati-7-teeka-{vol}_jp2/saptashati-7-teeka-{vol}_{scan:04d}.jp2"


def page_image(vol, scan):
    """PIL image for a scan, cached as JPEG on first access."""
    os.makedirs(CACHE, exist_ok=True)
    cached = os.path.join(CACHE, f"v{vol}_{scan:04d}.jpg")
    if os.path.exists(cached):
        return Image.open(cached).convert("RGB")
    z = _zip(vol)
    with z.open(jp2_name(vol, scan)) as f:
        im = Image.open(io.BytesIO(f.read())).convert("RGB")
    im.save(cached, quality=94)
    return im


def path_for(vol, scan):
    page_image(vol, scan)
    return os.path.join(CACHE, f"v{vol}_{scan:04d}.jpg")


def scan_count(vol):
    return len([n for n in _zip(vol).namelist() if n.endswith(".jp2")])
