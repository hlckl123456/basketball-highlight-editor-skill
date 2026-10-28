"""Additional regression checks; old test files and assertions stay untouched."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as A
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
spec=importlib.util.spec_from_file_location('goal2_highlight',ROOT/'skills/basketball-highlight-editor/scripts/highlight.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
import media_io
import result_cache
sys.path.insert(0,str(ROOT/'robustness'))
from generate import rotate_fixture, encode


class IOAndCache(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name)
  cls.video=cls.base/'source.mp4'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=24:duration=2','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-y',str(cls.video)],check=True)
  cls.rights=cls.base/'rights.json';h.write(cls.rights,dict(source_url='synthetic:generated',creator='test_operator',license='CC0 generated',processing_basis='mechanical test fixture',restrictions='no human confirmation'))
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def project(self,name):
  p=self.base/(self._testMethodName+'-'+name);h.cmd_init(A(project=p,video=self.video,rights=self.rights,reproducible=True,epoch=946684800));return p
 def args(self,project,manifest,before=3):
  return A(project=project,backend='manifest',manifest=manifest,runtime=None,python=sys.executable,model=None,roi=None,fps=3,before=before,after=3,device='cpu',timeout=120,cache_dir=self.base/self._testMethodName/'cache',no_cache=False,refresh_cache=False)
 def test_empty_and_missing_inputs_have_actionable_errors(self):
  empty=self.base/'empty.mp4';empty.write_bytes(b'')
  for p,code in [(empty,'MEDIA_EMPTY'),(self.base/'missing.mp4','MEDIA_NOT_FOUND')]:
   with self.subTest(path=p):
    with self.assertRaisesRegex(ValueError,code):media_io.probe(p)
 def test_audio_only_file_is_not_a_movie(self):
  p=self.base/'audio-only.m4a';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.2','-y',str(p)],check=True)
  with self.assertRaisesRegex(ValueError,'MEDIA_NO_VIDEO'):media_io.probe(p)
 def test_rotation_metadata_uses_display_coordinates(self):
  p=self.base/'rotated.mov';rotate_fixture(self.video,p,90)
  meta=media_io.probe(p);self.assertEqual((meta['width'],meta['height']),(180,320));self.assertEqual((meta['coded_width'],meta['coded_height']),(320,180))
 def test_faststart_truncation_is_rejected(self):
  full=self.base/'faststart.mp4';subprocess.run(['ffmpeg','-v','error','-i',str(self.video),'-c','copy','-movflags','+faststart','-y',str(full)],check=True)
  broken=self.base/'broken.mp4';broken.write_bytes(full.read_bytes()[:full.stat().st_size//2])
  with self.assertRaisesRegex(ValueError,'MEDIA_(TRUNCATED|DECODE_FAILED)'):media_io.probe(broken)
 def test_vfr_opus_priming_does_not_shift_video_boundaries(self):
  from matrix import audit_clip, pts
  p=self.base/'vfr-short-audio.webm';encode(p,854,480,'vfr','vp9',audio='short')
  meta=media_io.probe(p);out=self.base/'vfr-audio-clip.mp4';c={'start':.413,'end':1.887}
  media_io.render(p,meta,c['start'],c['end'],out)
  result=audit_clip(out,c,meta,pts(p),{'clock':'per-frame-index','duration':4})
  self.assertLessEqual(result['end_error_frames'],1)
 def test_positive_video_timestamp_origin_is_relative_to_first_picture(self):
  from matrix import audit_clip, pts
  base=self.base/'clock-origin.mp4';encode(base,854,480,30,'h264')
  p=self.base/'shifted-origin.mp4'
  subprocess.run(['ffmpeg','-v','error','-i',str(base),'-c','copy','-output_ts_offset','7','-y',str(p)],check=True)
  meta=media_io.probe(p);self.assertEqual(meta['presentation_start'],7)
  out=self.base/'origin-clip.mp4';c={'start':.413,'end':1.887}
  media_io.render(p,meta,c['start'],c['end'],out)
  result=audit_clip(out,c,meta,pts(p),{'clock':'per-frame-index','duration':4})
  self.assertLessEqual(result['start_error_frames'],1)
 def test_person_hash_never_loads_the_whole_movie(self):
  import person_engine
  expected=h.sha(self.video)
  with patch.object(Path,'read_bytes',side_effect=AssertionError('whole movie read')):
   self.assertEqual(person_engine.sha(self.video),expected)
 def test_person_scan_and_match_share_rotated_presentation_frames(self):
  import person_engine
  from person_match import predict
  rotated=self.base/'person-rotated.mov';rotate_fixture(self.video,rotated,90)
  out=self.base/'person-rotated.json';shapes=[]
  class FakeDetector:
   def __init__(self,path):pass
   def predict(self,frame,roi,threshold):shapes.append(frame.shape);return []
  with patch.object(person_engine,'Detector',FakeDetector),patch.object(person_engine.cv2,'VideoCapture',side_effect=AssertionError('approximate seek')):
   person_engine.detect(A(video=rotated,model=self.video,roi=None,fps=1,start=.5,end=1,tile=0,threshold=.2,output=out))
   data=h.read(out);prediction=predict(data,{'people':[{'id':'test_region','samples':[{'time':.5,'box':[0,0,180,320]}]}]})
  self.assertEqual(shapes,[(320,180,3)])
  self.assertEqual((data['width'],data['height']),(180,320))
  self.assertEqual(len(prediction['records']),1)
 def test_hash_memo_detects_same_size_content_changes(self):
  p=self.base/'mutating.bin';p.write_bytes(b'one');first=h.sha(p);p.write_bytes(b'two');self.assertNotEqual(h.sha(p),first)
 def test_hot_detection_skips_detector_and_keeps_project_bytes(self):
  f=self.base/'ranges.json';h.write(f,{'provenance':'test_operator manifest','candidates':[{'start':0,'end':1}]})
  first=self.project('first');second=self.project('second');h.cmd_detect(self.args(first,f))
  with patch.object(h,'_detect_uncached',side_effect=AssertionError('detector invoked on a cache hit')):
   h.cmd_detect(self.args(second,f))
  self.assertTrue(h.read(second/'detection/cache-status.json')['hit'])
  self.assertEqual((first/'project.json').read_bytes(),(second/'project.json').read_bytes())
 def test_parameter_change_invalidates_detection_cache(self):
  f=self.base/'ranges-parameters.json';h.write(f,{'provenance':'test_operator fixture','candidates':[{'start':0,'end':1}]})
  first=self.project('first');second=self.project('second');h.cmd_detect(self.args(first,f))
  with patch.object(h,'_detect_uncached',wraps=h._detect_uncached) as detector:
   h.cmd_detect(self.args(second,f,before=4));self.assertEqual(detector.call_count,1)
  self.assertFalse(h.read(second/'detection/cache-status.json')['hit'])
 def test_changed_manifest_invalidates_cache(self):
  f=self.base/'ranges-manifest.json';h.write(f,{'provenance':'test_operator fixture','candidates':[{'start':0,'end':1}]})
  first=self.project('first');h.cmd_detect(self.args(first,f));h.write(f,{'provenance':'changed fixture','candidates':[{'start':.5,'end':1.5}]})
  second=self.project('second');h.cmd_detect(self.args(second,f));self.assertFalse(h.read(second/'detection/cache-status.json')['hit'])
 def test_corrupt_cache_fails_closed(self):
  directory=self.base/'corrupt-cache';result_cache.put(directory,'detection','fixture',{'items':[1]})
  p=directory/'detection/fixture.json';d=json.loads(p.read_text());d['payload']['items']=[2];p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'CACHE_CORRUPT'):result_cache.get(directory,'detection','fixture')
 def test_bhe_cache_hit_skips_external_scan_and_preserves_raw_json(self):
  runtime=self.base/self._testMethodName/'runtime';(runtime/'scripts').mkdir(parents=True);(runtime/'models').mkdir()
  (runtime/'models/bball_model.static.onnx').write_bytes(b'NOT A MODEL: synthetic cache contract fixture')
  scan="import sys,json;from pathlib import Path;p=Path(sys.argv[sys.argv.index('--output')+1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'frames':[]}))"
  gen="import sys,json;from pathlib import Path;Path(sys.argv[sys.argv.index('--output')+1]).write_text(json.dumps({'candidates':[{'time':0.5}]}))"
  (runtime/'scripts/scan_video.py').write_text(scan);(runtime/'scripts/generate_candidates.py').write_text(gen)
  first=self.project('first');second=self.project('second')
  args=self.args(first,None);args.backend='bhe';args.runtime=runtime;h.cmd_detect(args)
  args=self.args(second,None);args.backend='bhe';args.runtime=runtime
  with patch.object(h,'run',side_effect=AssertionError('external detector invoked on hot cache')):h.cmd_detect(args)
  self.assertTrue(h.read(second/'detection/cache-status.json')['hit'])
  self.assertEqual((first/'project.json').read_bytes(),(second/'project.json').read_bytes())
  self.assertEqual(h.read(second/'detection/events.json'),{'candidates':[{'time':.5}]})
 def test_cumulative_frame_rounding_does_not_accumulate_drift(self):
  fps=media_io.output_rate({'fps':'30/1'});lengths=[.113]*75;cumulative=0;allocated=0
  for length in lengths:
   cumulative+=length;total=media_io.frames_for(cumulative,fps);quota=total-allocated
   self.assertLessEqual(abs(float(quota/fps)-length),float(1/fps));allocated=total
  self.assertLessEqual(abs(float(allocated/fps)-sum(lengths)),float(1/fps))
 def test_fixed_test_clock_never_records_user_confirmation(self):
  root=self.project('clock');f=self.base/'clock-ranges.json';h.write(f,{'provenance':'synthetic','candidates':[{'start':0,'end':1}]});h.cmd_import(A(project=root,file=f))
  _,p=h.load(root);p['players']=[{'id':'p1','description':'test','reference':'test'}];p['selection']={'player_id':'p1','high_confidence':[],'uncertain':['c0001'],'other':[]};h.write(root/'project.json',p)
  f=self.base/'clock-decision.json';h.write(f,{'project_revision':p['revision'],'player_id':'p1','reviewer_kind':'user','reviewer':'not an actual user','authorization_reference':'invalid synthetic attempt','decisions':{'c0001':'keep'}})
  with self.assertRaisesRegex(ValueError,'REQUIRES_TEST_OPERATOR'):h.cmd_confirm(A(project=root,file=f))


if __name__=='__main__':unittest.main()
