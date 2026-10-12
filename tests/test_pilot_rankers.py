"""Small synthetic invariants; never run pilot queries or contact a model."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('rankers',Path(__file__).parents[1]/'research/pilot/baselines.py')
rankers=importlib.util.module_from_spec(spec)
spec.loader.exec_module(rankers)

class RankerChecks(unittest.TestCase):
    def test_semantic_and_lexical_signals_both_contribute(self):
        texts=['unrelated words','exact_target exact_target','semantic paraphrase']
        vectors=[[0,1],[0,1],[1,0]]
        self.assertEqual(rankers.bm25(texts,'exact_target')[0],1)
        self.assertEqual(rankers.cosine(vectors,[1,0])[0],2)
        self.assertEqual(set(rankers.hybrid(texts,'exact_target',vectors,[1,0],depth=1)),{1,2})

    def test_bad_vectors_fail_loudly(self):
        for vector in [[0,0],[float('nan'),1],[1]]:
            with self.assertRaises(ValueError):rankers.cosine([vector],[1,0])

    def test_stable_ties_and_code_identifiers(self):
        self.assertEqual(rankers.bm25(['same','same'],'same'),[0,1])
        self.assertIn('header',rankers.terms('prepare_header'))
        self.assertIn('request',rankers.terms('prepareRequest'))

if __name__=='__main__':unittest.main()
