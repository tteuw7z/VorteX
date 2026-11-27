# SPDX-License-Identifier: LicenseRef-VorteX-Proprietary
import tempfile, unittest, shutil, subprocess
from pathlib import Path
from PIL import Image
from vortex_studio import compare, rank, film_trim

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        for name,size,color in [('ref',(10,10),'white'),('same',(10,10),'white'),('different',(10,10),'black'),('small',(5,5),'white')]:
            Image.new('RGB',size,color).save(self.root/(name+'.png'))
    def test_exact(self):
        self.assertEqual(compare(self.root/'ref.png',self.root/'same.png')['match_percent'],100)
    def test_difference(self):
        r=compare(self.root/'ref.png',self.root/'different.png')
        self.assertEqual((r['status'],r['changed_pixels'],r['changed_bbox']),('VISUAL_FAIL',100,(0,0,10,10)))
    def test_size(self):
        self.assertEqual(compare(self.root/'ref.png',self.root/'small.png')['status'],'SIZE_MISMATCH')
    def test_ranking(self):
        r=rank(self.root/'ref.png',[self.root/'small.png',self.root/'different.png',self.root/'same.png'])
        self.assertEqual([x['status'] for x in r],['VISUAL_PASS','VISUAL_FAIL','SIZE_MISMATCH'])
    def test_bad_threshold(self):
        with self.assertRaises(ValueError): compare(self.root/'ref.png',self.root/'same.png',minimum=float('nan'))
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'external tools unavailable')
    def test_real_encode(self):
        src=self.root/'source.mp4'; out=self.root/'out.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=purple:s=160x90:r=30:d=3','-f','lavfi','-i','sine=f=440:d=3','-c:v','libx264','-c:a','aac','-shortest',str(src)],check=True,timeout=60)
        r=film_trim(src,out,0.5,1.0)
        self.assertEqual(r['status'],'ENCODED'); self.assertEqual(r['streams'],['video','audio']); self.assertTrue(out.is_file())
        with self.assertRaises(ValueError): film_trim(src,out,0.5,1.0)
        with self.assertRaises(ValueError): film_trim(src,self.root/'bad.mp4',2.5,1.0)

if __name__=='__main__': unittest.main()
