import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ff7r_view_report import analyze
CREATE='DXVK-FF7R-VIEW-CREATE ts_us=10 image_view=7 image=9 format=97 mip_index=2 layer_index=0'
ATT='DXVK-FF7R-ATTACHMENT ts_us=20 pass=1 image_view=7 bound=1 aspect=color load_op=0 store_op=0'
DESTROY='DXVK-FF7R-VIEW-DESTROY ts_us=15 image_view=7 image=9'
class ViewReportTest(unittest.TestCase):
    def test_join_even_when_lines_interleaved(self):
        r=analyze(ATT+'\n'+CREATE)
        self.assertEqual(r['matched_bound_aspect_records'],1);self.assertEqual(r['groups'][0]['format'],97)
    def test_destroyed_view_unmatched(self):
        r=analyze(CREATE+'\n'+DESTROY+'\n'+ATT)
        self.assertEqual(r['matched_bound_aspect_records'],0);self.assertEqual(r['unmatched']['view_destroyed_at_record_time'],1)
    def test_reused_handle_selects_new_lifetime(self):
        r=analyze(CREATE+'\n'+DESTROY+'\n'+CREATE.replace('ts_us=10','ts_us=18').replace('image=9','image=11')+'\n'+ATT)
        self.assertEqual(r['groups'][0]['image'],'11')
    def test_old_log_and_partial_log_disclosed(self):
        self.assertEqual(analyze(ATT)['unmatched']['creation_record_absent'],1)
        self.assertEqual(analyze(ATT.replace('image_view=7 ',''))['unmatched']['attachment_identity_absent'],1)
if __name__=='__main__':unittest.main()
