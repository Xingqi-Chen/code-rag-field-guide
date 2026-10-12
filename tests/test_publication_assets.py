"""Regression checks for images newly allowed in public research artifacts."""
import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('publication_validate',ROOT/'scripts/validate.py')
validator=importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)

class PublicationAssets(unittest.TestCase):
    def test_original_figures_are_valid(self):
        for svg in (ROOT/'docs/figures').glob('*.svg'):
            sw,sh=validator.check_svg(svg.read_text())
            self.assertEqual(validator.check_png(svg.with_suffix('.png').read_bytes()),(sw*2,sh*2))

    def test_png_corruption_and_metadata_are_rejected(self):
        data=(ROOT/'docs/figures/01-search-and-relations.png').read_bytes()
        for broken in [data[:-2],data+b'private payload',data[:45]+bytes([data[45]^1])+data[46:]]:
            with self.assertRaises(AssertionError):validator.check_png(broken)
        payload=b'Comment\0private metadata'; kind=b'tEXt'
        chunk=struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
        with self.assertRaises(AssertionError):validator.check_png(data[:33]+chunk+data[33:])

    def test_svg_active_content_and_missing_description_are_rejected(self):
        svg=(ROOT/'docs/figures/01-search-and-relations.svg').read_text()
        for broken in [svg.replace('</svg>','<script>bad()</script></svg>'),
                       svg.replace('<svg ','<svg onload="bad()" ',1),
                       svg.replace('<desc id="desc">','<desc id="missing">',1)]:
            with self.assertRaises(AssertionError):validator.check_svg(broken)

if __name__=='__main__':unittest.main()
