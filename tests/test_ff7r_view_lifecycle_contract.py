from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class LifecycleContract(unittest.TestCase):
    def test_creation_success_and_destruction_order(self):
        text=(ROOT/'src/dxvk/dxvk_memory.cpp').read_text()
        start=text.index('  const DxvkDescriptor* DxvkResourceImageViewMap::createImageView(')
        body=text[start:text.index('  DxvkResourceAllocation::',start)]
        self.assertLess(body.index('if (vr != VK_SUCCESS)'),body.index('DXVK-FF7R-VIEW-CREATE'))
        self.assertLess(body.index('DXVK-FF7R-VIEW-CREATE'),body.index('return &descriptor;'))
        destroy=text[text.index('  DxvkResourceImageViewMap::~'):start]
        self.assertLess(destroy.index('DXVK-FF7R-VIEW-DESTROY'),destroy.index('vk->vkDestroyImageView'))
        self.assertIn('uint32_t(key.mipIndex)',body)
        self.assertIn('uint32_t(key.mipCount)',body)
        for field in ('format=', 'mip_index=', 'mip_count=', 'layer_index=', 'layer_count=', 'image_view=', 'image='):
            self.assertIn(field,body)
if __name__=='__main__':unittest.main()
