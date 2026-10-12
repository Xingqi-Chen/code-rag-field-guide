import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('aggregate',Path(__file__).resolve().parents[1]/'scripts/aggregate.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class MetricsTest(unittest.TestCase):
    def test_two_evidence_units_in_one_chunk(self):
        row={'retrieved':['noise','hit'],'relevant':['hit','missing'],'evidence_groups':[['hit'],['hit'],['missing']]}
        m=a.recompute(row,{'noise':{'tokens':10},'hit':{'tokens':20}})
        self.assertEqual(m['recall'],.5);self.assertEqual(m['mrr'],.5)
        self.assertEqual(m['evidence_coverage'],2/3);self.assertEqual(m['context_tokens'],30)
        self.assertEqual(m['all_evidence'],0)
    def test_negative_is_not_zero_recall(self):
        row={'retrieved':['a'],'relevant':[],'evidence_groups':[]}
        m=a.recompute(row,{'a':{'tokens':4}})
        self.assertIsNone(m['recall']);self.assertEqual(m['unlabelled_fraction'],1)
if __name__=='__main__':unittest.main()
