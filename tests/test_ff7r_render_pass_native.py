"""Compile the actual cmdBeginRendering body against a read-only fake Vulkan dispatch."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class RenderPassTest(unittest.TestCase):
    def test_opt_in_final_ops_and_dispatch_unchanged(self):
        s=(ROOT/'src/dxvk/dxvk_cmdlist.h').read_text()
        start=s.index('    void cmdBeginRendering(')
        end=s.index('\n\n\n    void cmdBeginTransformFeedback',start)
        template=(ROOT/'tests/ff7r_render_pass_probe.cpp').read_text()
        with tempfile.TemporaryDirectory() as d:
            cpp=Path(d)/'probe.cpp'; exe=Path(d)/'probe'
            cpp.write_text(template.replace('METHOD',s[start:end]))
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(ROOT/'src/util'),str(cpp),'-o',str(exe)],check=True)
            for value in ['0','1','true','']:
                p=subprocess.run([str(exe),value],capture_output=True,text=True,check=True)
                self.assertEqual(p.stderr,'')
                self.assertIn('dispatch_calls=1 state_unchanged=1',p.stdout)
                lines=[l for l in p.stdout.splitlines() if l.startswith('DXVK-FF7R-')]
                self.assertEqual(len(lines),5 if value=='1' else 0)
                if value=='1':
                    self.assertIn('width=1280 height=720 layers=1 view_mask=0 flags=2 colors=2',lines[0])
                    self.assertIn('aspect=color index=0 bound=1 layout=2 load_op=0 store_op=0 resolve_mode=1 resolve_bound=1 resolve_layout=2',lines[1])
                    self.assertIn('image_view=1 resolve_view=3',lines[1])
                    self.assertIn('aspect=color index=1 bound=0',lines[2])
                    self.assertIn('image_view=0 resolve_view=0',lines[2])
                    self.assertIn('aspect=depth',lines[3]); self.assertIn('aspect=stencil',lines[4])
                    for line in lines:
                        self.assertIn(' pass=1 ',line)
if __name__=='__main__': unittest.main()
