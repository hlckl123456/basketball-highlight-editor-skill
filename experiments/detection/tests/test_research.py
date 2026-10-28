"""Synthetic geometry/policy checks; never creates real human ground truth."""
import copy,json,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'experiments/detection'))
import engine
from policy import better,meets,catalog,forbidden_paths

def detection(name,x,y,confidence=.8):return {'name':name,'center':[x,y],'xyxy':[x-10,y-5,x+10,y+5],'confidence':confidence}
def records():return [{'time':t,'detections':[detection('hoop',100,100),detection('ball',100,y)]} for t,y in [(0,70),(1,90),(2,130)]]
class Research(unittest.TestCase):
 def test_unknown_baseline_never_promotes(self):self.assertFalse(better({'event_recall':1,'event_precision':1},{'event_recall':None,'event_precision':None}))
 def test_unknown_candidate_never_promotes(self):self.assertFalse(better({'event_recall':None,'event_precision':None},{'event_recall':.8,'event_precision':.7}))
 def test_recall_decline_cannot_win_by_precision(self):self.assertFalse(better({'event_recall':.8,'event_precision':1},{'event_recall':.9,'event_precision':.7}))
 def test_equal_recall_better_precision_wins(self):self.assertTrue(better({'event_recall':.9,'event_precision':.8},{'event_recall':.9,'event_precision':.7}))
 def test_unknown_roi_cannot_claim_completion(self):self.assertFalse(meets({'event_recall':1,'event_precision':1},None))
 def test_roi_separates_two_spatial_hoops(self):
  r=records()
  for row in r:row['detections'].append(detection('hoop',400,100))
  self.assertEqual(len(engine.suggest_rois(r,.08)),2)
 def test_roi_stays_draft_and_requires_user(self):
  out=engine.suggest_rois(records(),.08);self.assertTrue(out);self.assertTrue(all(p['status']=='draft' and p['requires_user_confirmation'] for p in out))
 def test_proximity_is_not_a_confirmed_made_shot(self):
  out=engine.propose(records(),3,[[0,3]],{'proximity':True});self.assertTrue(out['events']);self.assertTrue(all(p['status']=='draft' and 'is_score' not in p for p in out['events']))
 def test_interpolated_time_is_trajectory_plane_crossing(self):
  out=engine.propose(records(),3,[[0,3]],{'interpolate':True});self.assertTrue(out['events']);self.assertAlmostEqual(out['events'][0]['time'],1.25)
 def test_stabilization_removes_shared_camera_translation(self):
  source=records();moved=copy.deepcopy(source)
  for i,row in enumerate(moved):
   for d in row['detections']:d['center']=[d['center'][0]+i*7,d['center'][1]+i*11];d['xyxy']=[d['xyxy'][0]+i*7,d['xyxy'][1]+i*11,d['xyxy'][2]+i*7,d['xyxy'][3]+i*11]
  result=engine.stabilize(moved,{'center_x':100,'rim_y':100})
  self.assertEqual([r['detections'][1]['center'] for r in result],[r['detections'][1]['center'] for r in source])
 def test_coverage_has_no_gaps_and_no_fake_events(self):
  out=engine.propose([],20,[[0,20]],{'review_coverage':True});self.assertEqual(out['events'],[])
  windows=out['review_windows'];self.assertEqual(windows[0]['start'],0);self.assertEqual(windows[-1]['end'],20)
  self.assertTrue(all(a['end']>=b['start'] for a,b in zip(windows,windows[1:])))
 def test_holdout_guard_blocks_before_read(self):
  target=next(v['source_path'] for v in catalog()['videos'] if v['split']=='holdout')
  program="import sys;sys.path.insert(0,'experiments/detection');from policy import install_holdout_guard;install_holdout_guard(None);from pathlib import Path;Path(sys.argv[1]).read_bytes()"
  r=subprocess.run([sys.executable,'-c',program,target],cwd=ROOT,capture_output=True,text=True)
  self.assertNotEqual(r.returncode,0);self.assertIn('HOLDOUT_ACCESS_DENIED',r.stderr)
 def test_sampling_preserves_two_staggered_six_fps_sets(self):
  rows=[{'time':i/12,'detections':[]} for i in range(24)]
  self.assertEqual(len(engine.sampled(rows,{'sample_fps':6,'detector_conf':.15})),12)
  self.assertEqual(len(engine.sampled(rows,{'sample_fps':12,'detector_conf':.15})),24)
 def test_record_order_does_not_change_proposals(self):
  a=engine.propose(records(),3,[[0,3]],{});b=engine.propose(list(reversed(records())),3,[[0,3]],{})
  self.assertEqual(a,b)

 def test_active_trial_binding_keeps_outputs_draft(self):
  import trial_candidate
  out=trial_candidate.propose(records(),3,[[0,3]])
  self.assertEqual(out['status'],'draft');self.assertTrue(all(e['status']=='draft' for e in out['events']))
 def test_coverage_is_separate_from_scoring_predictions(self):
  out=engine.propose([],20,[[0,20]],{'review_coverage':True,'motion_union':True})
  self.assertTrue(out['review_windows']);self.assertFalse(out['events'])

 def test_development_scoring_wrapper_preserves_holdout_withholding(self):
  import tempfile
  with tempfile.TemporaryDirectory() as temp:
   out=Path(temp)/'score.json'
   r=subprocess.run([sys.executable,'experiments/detection/score_dev.py','--output',str(out)],cwd=ROOT,capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
   data=json.loads(out.read_text());self.assertFalse(data['holdout_evaluated']);self.assertEqual(data['splits']['holdout']['status'],'withheld')
 def test_reset_refuses_main_branch(self):
  import run as study
  from unittest.mock import patch
  with patch.object(study.subprocess,'check_output',side_effect=['main','']),patch.object(study.subprocess,'run') as reset:
   with self.assertRaisesRegex(RuntimeError,'UNRELATED_CHANGES'):study.safe_reset('not-used')
   reset.assert_not_called()
 def test_reset_refuses_unrelated_user_changes(self):
  import run as study
  from unittest.mock import patch
  with patch.object(study.subprocess,'check_output',side_effect=['goal-3-detection','README.md\n']),patch.object(study.subprocess,'run') as reset:
   with self.assertRaisesRegex(RuntimeError,'UNRELATED_CHANGES'):study.safe_reset('not-used')
   reset.assert_not_called()
