import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from code_prompt_json_syntax import candidate


class TailCommaBoundaryTests(unittest.TestCase):
    def test_only_outside_string_object_and_array_tails(self):
        original='{"text":"inside,} and ,] and escaped \\\" quote","rows":[1,2, ], }'
        fixed,positions,strings=candidate(original)
        self.assertEqual(json.loads(fixed),{'text':'inside,} and ,] and escaped " quote','rows':[1,2]})
        self.assertEqual(len(positions),2)
        self.assertEqual(candidate(fixed)[2],strings)
        self.assertTrue(all(original[i]==',' for i in positions))

    def test_no_other_json_repair(self):
        for text in ['{"a":1}', '[1,2]', '{"text":"comma,}"}']:
            self.assertEqual(candidate(text)[:2],(text,[]))
        broken='{"text":"unterminated,}'
        self.assertEqual(candidate(broken)[:2],(broken,[]))
        for broken in ['{"a":,}', '[1,,]', '{"a":1,]']:
            with self.assertRaises(json.JSONDecodeError):json.loads(candidate(broken)[0])


if __name__=='__main__':unittest.main()
