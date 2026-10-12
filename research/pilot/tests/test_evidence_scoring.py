"""Synthetic boundary cases for the frozen scoring and common budget adapter."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from score_results import score
from full_retrieve import render, budget_tables, adapt
from full_features import extract_diff


class EvidenceScoringTests(unittest.TestCase):
    def setUp(self):
        self.gold={'evidence':[{'id':'E','path':'code.py','start_line':1,'end_line':10}]}

    def test_partial_sources_union_and_single_chunk_mrr_differ(self):
        sources=[{'path':'code.py','start_line':1,'end_line':4},
                 {'path':'code.py','start_line':5,'end_line':8}]
        s=score(self.gold,sources)
        self.assertEqual(s['coverage80'],1)
        self.assertEqual(s['coverage100'],0)
        self.assertEqual(s['mrr'],0)

    def test_wrong_file_and_overlap_do_not_double_count(self):
        sources=[{'path':'wrong.py','start_line':1,'end_line':10},
                 {'path':'code.py','start_line':1,'end_line':4},
                 {'path':'code.py','start_line':1,'end_line':4}]
        self.assertEqual(score(self.gold,sources)['coverage80'],0)

    def test_no_gold_is_not_zero_recall(self):
        self.assertIsNone(score({'evidence':[]},[])['coverage80'])

    def test_budget_is_whole_row_prefix_with_headers_counted(self):
        tables=[{'name':'sources','columns':['id','text'],'rows':[
            {'id':'1','text':'abc'}, {'id':'2','text':'d'*200}, {'id':'3','text':'e'}]}]
        limit=len(render([dict(tables[0],rows=tables[0]['rows'][:1])]))
        result=budget_tables(tables,limit,len)
        self.assertEqual(len(result[0]['rows']),1)
        self.assertEqual(len(render(result)),limit)

    def test_source_text_and_actual_context_flag_are_checked(self):
        sources={'1':{'text':'abc','provenance':{'title':'a.py:L1-L1'}}}
        with self.assertRaises(BaseException):
            adapt({'sources':[{'id':'1','text':'changed'}]},sources)
        with self.assertRaises(BaseException):
            adapt({'sources':[{'id':'1','text':'abc','in_context':False}]},sources)

    def test_patch_paths_cannot_escape_candidate(self):
        _, issue=extract_diff('--- a/../../outside\n+++ b/../../outside\n@@ -1 +1 @@\n-x\n+y')
        self.assertEqual(issue,'unsafe_diff_path')


if __name__=='__main__':unittest.main()
