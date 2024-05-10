"""
Continuously runs a python module
"""
import time
import os.path as osp
import xml.etree.ElementTree as ET

inpath = osp.join('sanitized', 'kavacha.xml')
assert osp.exists(inpath), f"File not found: {inpath}"
outfile = osp.join('docs', 'kavacham.html')
while True:
    root = ET.parse(inpath).getroot()
    for child in root:
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(ET.tostring(child, encoding='unicode', method='xml', xml_declaration=False))
    time.sleep(5)