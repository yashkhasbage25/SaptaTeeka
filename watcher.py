"""
Continuously runs a python module
"""
import time
import os.path as osp
import xml.etree.ElementTree as ET
import importlib
import base_html

file_maps = [
    (osp.join("sanitized", f"{chapter}.xml"), osp.join("docs", f"{chapter}.html"))
        for chapter in ["kavacham", "argala"]
]

while True:
    importlib.reload(base_html)
    with open(osp.join("docs", "index.html"), "w", encoding='utf-8') as f:
        f.write(base_html.index_html)
        print("Updated docs\\index.html")
    # time.sleep(3)
    for src, dest in file_maps:
        importlib.reload(base_html)
        assert osp.exists(src), f"{src} does not exist"
        tree = ET.parse(src)
        root = tree.getroot()

        html = base_html.chapter_to_html(root)
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Updated {dest}")
        # time.sleep(7)
    # break