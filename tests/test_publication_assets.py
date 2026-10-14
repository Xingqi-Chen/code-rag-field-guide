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
    def test_remote_tutorial_sequence_diagrams_are_valid(self):
        self.assertEqual(validator.check_mermaid((ROOT/'docs/graphrag-full-explained.md').read_text()),4)

    def test_sequence_references_and_nested_blocks_are_checked(self):
        good='```mermaid\nsequenceDiagram\nparticipant A as Reader\nparticipant B as Index\nloop Repeated lookup\nopt Cache miss\nA->>B: Lookup\nNote over A,B: Context\nB-->>A: Result\nend\nend\n```'
        self.assertEqual(validator.check_mermaid(good),1)
        for broken in [good.replace('A->>B:','A->>Missing:'),good.replace('Note over A,B:','Note over A,Missing:'),
                       good.replace('\nend\nend','\nend'),good.replace('\nend\nend','\nend\nend\nend'),
                       good.replace('A->>B: Lookup','unrecognized statement')]:
            with self.subTest(broken=broken),self.assertRaises(AssertionError):validator.check_mermaid(broken)

    def test_original_figures_are_valid(self):
        figures=list((ROOT/'docs/figures').glob('*.svg'))
        self.assertEqual(len(figures),4)
        for svg in figures:
            sw,sh=validator.check_svg(svg.read_text())
            self.assertEqual(validator.check_png(svg.with_suffix('.png').read_bytes()),(sw*2,sh*2))

    def test_chinese_heading_links(self):
        self.assertEqual(validator.anchors('# 它怎么工作？\n## 一个例子：代码与关系\n## 一个例子：代码与关系'),
                         {'它怎么工作','一个例子代码与关系','一个例子代码与关系-1'})

    def test_code_examples_are_not_markdown_links(self):
        text='[real](README.md)\n```python\nhandlers[name](order)\n```\nUse `items[key](arg)` here.'
        self.assertEqual(validator.prose_only(text),'[real](README.md)\nUse  here.')

    def test_png_corruption_and_metadata_are_rejected(self):
        data=(ROOT/'docs/figures/01-code-evidence-layer.png').read_bytes()
        for broken in [data[:-2],data+b'private payload',data[:45]+bytes([data[45]^1])+data[46:]]:
            with self.assertRaises(AssertionError):validator.check_png(broken)
        payload=b'Comment\0private metadata'; kind=b'tEXt'
        chunk=struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
        with self.assertRaises(AssertionError):validator.check_png(data[:33]+chunk+data[33:])

    def test_svg_active_content_and_missing_description_are_rejected(self):
        svg=(ROOT/'docs/figures/01-code-evidence-layer.svg').read_text()
        for broken in [svg.replace('</svg>','<script>bad()</script></svg>'),
                       svg.replace('<svg ','<svg onload="bad()" ',1),
                       svg.replace('<desc id="desc">','<desc id="missing">',1)]:
            with self.assertRaises(AssertionError):validator.check_svg(broken)

if __name__=='__main__':unittest.main()
