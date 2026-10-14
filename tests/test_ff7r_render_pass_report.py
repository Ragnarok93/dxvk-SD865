from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ff7r_render_pass_report import analyze
P='DXVK-FF7R-RENDER-PASS ts_us=100 pass=1 width=1280 height=720 layers=1 view_mask=0 colors=2'
A='DXVK-FF7R-ATTACHMENT ts_us=100 pass=1 aspect=color index=0 bound=1 load_op=0 store_op=0 resolve_mode=1 resolve_bound=1'
class ReportTest(unittest.TestCase):
    def test_rank_and_null_slot(self):
        r=analyze(P+'\n'+A+'\n'+A.replace('index=0 bound=1','index=1 bound=0'))
        self.assertEqual(r['pass_count'],1);self.assertEqual(r['unbound_slots'],1)
        g=r['groups'][0];self.assertEqual(g['load_aspects'],1);self.assertEqual(g['store_aspects'],1);self.assertEqual(g['resolve_aspects'],1)
        self.assertEqual(g['attachment_area_store_proxy'],1280*720)
    def test_multiview_not_layer_count(self):
        r=analyze(P.replace('view_mask=0','view_mask=5')+'\n'+A)
        self.assertEqual(r['groups'][0]['effective_layers'],2)
    def test_truncated_log_discloses_orphan(self):
        self.assertEqual(analyze(A)['orphan_attachment_records'],1)
        self.assertEqual(analyze('')['pass_count'],0)
    def test_refuse_duplicates_or_mismatch(self):
        for text in [P+'\n'+P,P+'\n'+A+'\n'+A,P+'\n'+A.replace('ts_us=100','ts_us=101')]:
            with self.assertRaises(ValueError):analyze(text)
if __name__=='__main__':unittest.main()
