import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from index_artifacts import read_table,write_table


class PublicTableTests(unittest.TestCase):
    def test_paged_round_trip_preserves_rows_order_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'reports.json'
            rows=[{'id':i,'text':'报告内容'*10,'value':i/3,'nullable':None} for i in range(12)]
            manifest=write_table(path,rows,split_if_bytes=600,page_bytes=550)
            self.assertEqual(manifest['format'],'paged-json-table-v1')
            self.assertGreater(len(manifest['parts']),1)
            self.assertTrue(all(p['bytes']<=550 for p in manifest['parts']))
            self.assertEqual(read_table(path),rows)
            part=path.parent/manifest['parts'][0]['file']
            original=part.read_bytes();part.write_bytes(original.replace(b'null',b'true'))
            with self.assertRaises(AssertionError):read_table(path)

    def test_small_table_and_manifest_path_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'entities.json';rows=[{'id':'a'}]
            self.assertEqual(write_table(path,rows)['format'],'json-array')
            self.assertEqual(read_table(path),rows)
            path.write_text(json.dumps({'format':'paged-json-table-v1','parts':[{'file':'../outside.json'}]}))
            with self.assertRaises(AssertionError):read_table(path)


if __name__=='__main__':unittest.main()
