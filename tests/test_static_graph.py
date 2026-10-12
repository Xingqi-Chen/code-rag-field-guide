"""Static extractor regression; skips if optional experiment dependencies absent."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
try:
    spec=importlib.util.spec_from_file_location('retrieval',Path(__file__).resolve().parents[1]/'scripts/retrieval.py')
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
except ModuleNotFoundError:
    r=None

class Tokenizer:
    deprecation_warnings={}
    def encode(self,text,add_special_tokens=True):return text.split()

@unittest.skipIf(r is None,'Optional numpy/rank-bm25 dependencies absent; publication CI checks frozen output instead.')
class StaticGraphTest(unittest.TestCase):
    def test_imports_stay_lexically_scoped_and_assignments_shadow(self):
        original=r.ROOT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                r.ROOT=Path(tmp)
                source=r.ROOT/'.cache/corpora/fixture/src/fixture';source.mkdir(parents=True)
                (source/'helpers.py').write_text('def target():\n    pass\ndef wrong():\n    pass\n')
                (source/'main.py').write_text('from .helpers import wrong as f\ndef good():\n    from .helpers import target as f\n    f()\ndef shadow():\n    f = unknown_callback\n    f()\ndef other():\n    from .helpers import wrong as f\n    f()\n')
                chunks,adj,edges,_=r.build({'name':'fixture','source':'src/fixture','url':'https://example.invalid/fixture','commit':'fixed'},Tokenizer())
                calls=[(chunks[a]['symbol'],chunks[b]['symbol']) for a,b,k in edges if k=='static_call']
                joined=[' '.join(pair) for pair in calls]
                self.assertTrue(any('main:good' in x and 'helpers:target' in x for x in joined))
                self.assertTrue(any('main:other' in x and 'helpers:wrong' in x for x in joined))
                self.assertFalse(any('main:shadow' in x for x in joined))
                self.assertFalse(any('main:good' in x and 'helpers:wrong' in x for x in joined))
        finally:r.ROOT=original
if __name__=='__main__':unittest.main()
