"""New appearance backend contracts. Synthetic inputs are not identity ground truth."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import appearance_match as m
from appearance_features import crop_clothing,frame_stream
from attribution_policy import candidate_evidence,route_assignment
import media_io

def vec(i):
 a=np.zeros((3,384),np.float32);a[:,i]=1;return a

def color(i):
 a=np.zeros((4,20));a[:,i]=1;return a.tolist()

def ref(i=0,**kw):return {'time':0,'box':[20,20,60,120],'sample_id':str(i),'reviewer_kind':'test_operator','quality':{'usable':True},'embedding':vec(i),'descriptor':color(i),**kw}

def observation(k,i,x=20):return {'id':k,'box':[x,20,x+40,120],'quality':{'usable':True},'person_score':.9,'descriptor':color(i)}

class Appearance(unittest.TestCase):
 def data(self,n=6):
  data={'fps':5,'records':[{'time':round(i*.2,3),'items':[observation('p'+str(i),0),observation('q'+str(i),1,150)]} for i in range(n)]}
  features={o['id']:vec(0 if o['id'][0]=='p' else 1) for r in data['records'] for o in r['items']}
  return data,features,{'target':[ref()],'other':[ref(1)]}
 def predict(self,n=6):return m.predict_from_features(*self.data(n))
 def candidate(self,result):return candidate_evidence(result,{'id':'clip','start':0,'end':2},'target')
 def test_repeated_independent_texture_support_is_high_presence(self):
  r=self.predict();e=self.candidate(r);self.assertEqual(e['presence_certainty'],'high');self.assertEqual(e['support_count'],6)
  self.assertEqual(e['role_certainty'],{'visible':'high','scorer':'uncertain','handler':'uncertain'})
  self.assertFalse(e['is_probability']);self.assertEqual(len(e['supported_time_ranges']),1)
 def test_single_observation_is_not_a_supported_run(self):self.assertEqual(self.candidate(self.predict(1))['presence_certainty'],'uncertain')
 def test_identical_clothing_lookalike_in_same_frame_is_not_high(self):
  d,f,refs=self.data()
  for r in d['records']:
   o=r['items'][1];o['descriptor']=color(0);f[o['id']]=vec(0)
  self.assertFalse(m.predict_from_features(d,f,refs)['segments'])
 def test_identical_reference_profiles_cannot_be_distinguished(self):
  d,f,refs=self.data();refs['other']=[ref()];self.assertFalse(m.predict_from_features(d,f,refs)['segments'])
 def test_part_disagreement_cannot_hide_behind_global_similarity(self):
  d,f,refs=self.data()
  for k in list(f):
   if k.startswith('p'):f[k][2]=vec(2)[2]
  r=m.predict_from_features(d,f,refs);self.assertEqual(self.candidate(r)['presence_certainty'],'uncertain')
 def test_color_disagreement_is_independent_of_texture(self):
  d,f,refs=self.data()
  for r in d['records']:r['items'][0]['descriptor']=color(8)
  self.assertEqual(self.candidate(m.predict_from_features(d,f,refs))['presence_certainty'],'uncertain')
 def test_no_reference_or_no_feature_does_not_guess_identity(self):
  d,f,refs=self.data();self.assertFalse(m.predict_from_features(d,f,{})['segments']);self.assertFalse(m.predict_from_features(d,{},refs)['segments'])
 def test_no_actual_uniqueness_evidence_is_not_high(self):
  d,f,refs=self.data()
  for r in d['records']:r['items']=r['items'][:1]
  self.assertFalse(m.predict_from_features(d,f,{'target':[ref()]})['segments'])
 def test_untrusted_automatic_reference_never_counts(self):
  d,f,refs=self.data();refs['target']=[ref(is_automatic=True)];self.assertEqual(self.candidate(m.predict_from_features(d,f,refs))['presence_certainty'],'uncertain')
 def test_missing_quality_and_weak_person_detector_remain_uncertain(self):
  for change in [{'quality':{}},{'person_score':.1}]:
   d,f,refs=self.data()
   for r in d['records']:r['items'][0].update(change)
   self.assertEqual(self.candidate(m.predict_from_features(d,f,refs))['presence_certainty'],'uncertain')
 def test_long_gap_does_not_bridge_identities(self):
  d,f,refs=self.data()
  for r in d['records'][3:]:r['time']+=5
  self.assertEqual(self.candidate(m.predict_from_features(d,f,refs))['presence_certainty'],'uncertain')
 def test_head_pixels_do_not_enter_clothing_features(self):
  a=np.full((200,100,3),90,np.uint8);b=a.copy();a[:44]=0;b[:44]=255
  self.assertTrue(np.array_equal(crop_clothing(a,[0,0,100,200]),crop_clothing(b,[0,0,100,200])))
 def test_reference_validity_is_respected(self):
  d,f,refs=self.data();refs['target']=[ref(valid_until=.1)];self.assertEqual(self.candidate(m.predict_from_features(d,f,refs))['presence_certainty'],'uncertain')
 def test_nonfinite_or_unnormalized_embeddings_rejected(self):
  for v in [np.full((3,384),np.nan),np.zeros((3,384))]:
   with self.assertRaisesRegex(ValueError,'INVALID_APPEARANCE'):m.distances(v,vec(0))
 def test_distances_are_not_a_probability(self):
  x=vec(0);cost,parts=m.distances(x,vec(0));self.assertEqual(cost,0);self.assertEqual(parts,[0,0,0])
 def test_names_do_not_determine_identity(self):
  d,f,refs=self.data();r=m.predict_from_features(d,f,{'renamed':[ref()],'negative':[ref(1)]});self.assertTrue(any(s['player_id']=='renamed' for s in r['segments']))
 def test_actual_accepted_support_is_required_for_clip(self):
  r=self.predict()
  for row in r['records']:row['accepted']=[]
  self.assertEqual(self.candidate(r)['presence_certainty'],'uncertain')
 def test_unknown_frames_do_not_gain_propagated_identity(self):
  d,f,refs=self.data(12);d['records'][6]['items'][0]['quality']={};r=m.predict_from_features(d,f,refs)
  self.assertFalse(any(o['player_id']=='target' for o in r['records'][6]['accepted']))
 def test_other_person_high_never_silently_excludes_target(self):
  self.assertEqual(route_assignment({'presence_certainty':'high','presence_player_id':'other'},'target')[0],'uncertain')

 def test_duplicate_timestamp_cannot_inflate_support(self):
  d,f,refs=self.data();d['records'][1]['time']=0
  with self.assertRaisesRegex(ValueError,'INVALID_APPEARANCE_TIMELINE'):m.predict_from_features(d,f,refs)
 def test_duplicate_observation_names_are_rejected(self):
  d,f,refs=self.data();d['records'][1]['items'][0]['id']='p0'
  with self.assertRaisesRegex(ValueError,'DUPLICATE_APPEARANCE'):m.predict_from_features(d,f,refs)
 def test_calibration_integer_float_times_have_same_semantics(self):
  a={'people':[{'samples':[{'time':1,'box':[1,2,3,4],'is_automatic':False}]}]};b=copy.deepcopy(a);b['people'][0]['samples'][0]['time']=1.0
  self.assertEqual(m.calibration_hash(a),m.calibration_hash(b))
 def test_unrelated_uncertain_track_does_not_erase_a_precise_supported_run(self):
  r=self.predict();r['records'][0]['uncertain'].append({'player_id':'target','track_id':999,'confidence_evidence':{'reasons':['ambiguous_player_profiles']}})
  self.assertEqual(self.candidate(r)['presence_certainty'],'high')
 def test_numbers_and_filenames_are_not_identity_features(self):
  d,f,refs=self.data();expected=m.predict_from_features(d,f,refs)
  d['video']='different-source-name'
  for row in d['records']:
   for o in row['items']:o['number_ocr']='99'
  actual=m.predict_from_features(d,f,refs);self.assertEqual(actual,expected)


 def test_rejected_profile_is_a_hypothesis_not_assigned_identity(self):
  d,f,refs=self.data();d['records'][0]['items'][0]['quality']={};r=m.predict_from_features(d,f,refs)
  rejected=next(o for o in r['records'][0]['uncertain'] if o['observation_id']=='p0')
  self.assertIsNone(rejected['player_id']);self.assertEqual(rejected['hypothesis_player_id'],'target')
 def test_segment_envelope_reports_unknown_samples_explicitly(self):
  d,f,refs=self.data(12);d['records'][6]['items'][0]['quality']={};r=m.predict_from_features(d,f,refs)
  segment=next(s for s in r['segments'] if s['player_id']=='target' and s['start']<=1.2<=s['end'])
  self.assertIn(1.2,segment['unresolved_times']);self.assertNotIn(1.2,segment['support_times'])


 def test_render_end_is_exclusive_for_support_observations(self):
  r=self.predict();base={'id':'edge','start':0,'end':.8}
  self.assertEqual(candidate_evidence(r,base,'target')['presence_certainty'],'uncertain')
  self.assertEqual(candidate_evidence(r,{**base,'end':.81},'target')['presence_certainty'],'high')


 def test_upper_clothing_color_cannot_be_diluted_by_matching_trousers(self):
  d,f,refs=self.data()
  for row in d['records']:row['items'][0]['descriptor'][0]=color(8)[0]
  r=m.predict_from_features(d,f,refs)
  self.assertEqual(self.candidate(r)['presence_certainty'],'uncertain')


class Streaming(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=12:duration=1.5','-c:v','libx264','-pix_fmt','yuv420p','-output_ts_offset','0.7','-y',str(cls.root/'offset.mp4')],check=True)
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=12:duration=1.5','-vf',"select='not(eq(mod(n,3),1))'",'-fps_mode','vfr','-c:v','libx264','-pix_fmt','yuv420p','-y',str(cls.root/'vfr.mp4')],check=True)
  subprocess.run(['ffmpeg','-v','error','-i',str(cls.root/'vfr.mp4'),'-c','copy','-metadata:s:v:0','rotate=90','-y',str(cls.root/'rotated.mp4')],check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def compare(self,name):
  path=self.root/name;meta=media_io.probe(path);data={'fps':5,'records':[{'time':round(i*.2,3)} for i in range(6)]}
  frames=list(frame_stream(path,data));self.assertEqual(len(frames),6)
  for row,f in frames:self.assertTrue(np.array_equal(f,media_io.frame_bgr(path,row['time'],meta)),(name,row['time']))
 def test_presentation_offset_matches_existing_decoder(self):self.compare('offset.mp4')
 def test_vfr_rotation_matches_existing_decoder(self):self.compare('rotated.mp4')
 def test_irregular_observation_times_fall_back_to_exact_decoder(self):
  path=self.root/'offset.mp4';data={'fps':5,'records':[{'time':.11},{'time':.63}]}
  for row,f in frame_stream(path,data):self.assertTrue(np.array_equal(f,media_io.frame_bgr(path,row['time'])))

if __name__=='__main__':unittest.main()
