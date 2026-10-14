"""Incident recovery is exact, preserves counters, and cannot add retry slots."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bounded import Runtime,Halt,read,save,file_sha
from test_boundaries import Enc,Fake
import recovery

class Crashed(Fake):
    def dispatch(self,*args):raise AssertionError('synthetic pre-Popen incident')

class Recovery(unittest.TestCase):
    def prepare(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        rt=Runtime(root/'run',Crashed(),Enc(),Enc(),create=True,synthetic=True,wait=lambda _:None)
        self.addCleanup(rt.close)
        cell=rt.cell('Q01','routed_graphrag','local')
        with self.assertRaisesRegex(Halt,'transport_exception_redacted'):cell.generate('same exact question')
        log=root/'log.txt';log.write_text('Synthetic assertion before Popen')
        incident={'summary_before_sha256':file_sha(rt.directory/'summary.json'),'log_sha256':file_sha(log),
            'request_sha256':file_sha(rt.directory/'request-01.json'),'counts_retained':rt.state['counts'].copy(),
            'request_key':rt.state['events'][0]['key']}
        save(root/'supervisor-incident.json',incident)
        return root,rt,cell,log
    def test_preserves_reservation_and_allows_only_two_remaining_attempts(self):
        root,rt,cell,log=self.prepare();counts=copy.deepcopy(rt.state['counts'])
        with patch.object(recovery,'HERE',root):
            recovery.apply(rt,log)
            self.assertEqual(rt.state['counts'],counts)
            self.assertEqual(file_sha(rt.directory/'summary-before-supervisor-fix.json'),read(root/'supervisor-incident.json')['summary_before_sha256'])
            fake=Fake([{'http_status':503},{'http_status':503}]);rt.transport=fake
            with self.assertRaises(Halt):cell.generate('same exact question')
            self.assertEqual(len(fake.calls),2)
            self.assertEqual(len(rt.state['events']),3)
            self.assertEqual(rt.state['counts']['generation_reservations'],counts['generation_reservations']+2)
            rt.verify_ledger()
    def test_marker_or_response_disallows_recovery(self):
        for name in ('response-01.dispatch.json','response-01.json'):
            root,rt,cell,log=self.prepare();save(rt.directory/name,{'synthetic':True})
            with patch.object(recovery,'HERE',root):
                with self.assertRaisesRegex(Halt,'incident_snapshot_mismatch'):recovery.apply(rt,log)
            self.assertEqual(rt.state['status'],'stopped')
    def test_changed_snapshot_or_receipt_rejected(self):
        root,rt,cell,log=self.prepare()
        with patch.object(recovery,'HERE',root):
            recovery.apply(rt,log)
            rt.state['non_dispatch_recovery']['incident_sha256']='tampered'
            rt.transport=Fake()
            with self.assertRaisesRegex(Halt,'invalid_non_dispatch_recovery'):cell.generate('same exact question')
            self.assertEqual(rt.transport.calls,[])
            with self.assertRaisesRegex(Halt,'incident_snapshot_mismatch'):recovery.apply(rt,log)

if __name__=='__main__':unittest.main()
