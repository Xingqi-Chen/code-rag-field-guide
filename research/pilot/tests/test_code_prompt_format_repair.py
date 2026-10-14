import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from code_prompt_format_repair import candidate,apply_edits


class FormatRepairTests(unittest.TestCase):
    def test_inline_code_quotes_preserve_doubled_text(self):
        original='{"explanation":"Call `f(""/"".join(x))` here."}'
        fixed,edits,spans=candidate(original)
        self.assertEqual(len(edits),4)
        self.assertTrue(all(e['delete']=='' and e['insert']=='\\' for e in edits))
        self.assertEqual(json.loads(fixed)['explanation'],'Call `f(""/"".join(x))` here.')
        self.assertEqual(fixed,apply_edits(original,edits))
        self.assertEqual(spans[0]['original'],'`f(""/"".join(x))`')

    def test_combined_comma_and_quote_positions_are_original_offsets(self):
        original='{"explanation":"Use `f("x")`",}'
        fixed,edits,_=candidate(original)
        self.assertEqual(json.loads(fixed),{'explanation':'Use `f("x")`'})
        self.assertEqual(sum(e['delete']==',' for e in edits),1)
        self.assertEqual(fixed,apply_edits(original,edits))

    def test_valid_text_and_existing_escapes_are_unchanged(self):
        for original in [json.dumps({'explanation':'Use `f("x")`'}),'{"explanation":"ordinary"}']:
            self.assertIsNone(candidate(original))

    def test_ambiguous_or_unbounded_quotes_not_guessed(self):
        for original in ['{"explanation":"Say "hello" now"}',
                         '{"explanation":"Use `f("x")"}',
                         '{"explanation":"Use ```f("x")```"}',
                         '{"explanation":"`f("x")`","explanation":"duplicate"}',
                         '{"explanation":"`f("x")\nmore`"}']:
            with self.subTest(original=original):self.assertIsNone(candidate(original))


if __name__=='__main__':unittest.main()
