"""Synthetic safety contracts, never human-labelled evaluation examples."""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'skills/basketball-highlight-editor/scripts'))
import attribution_policy as p
import numpy as np


def desc(index):
 a=np.zeros((4,20));a[:,index]=1;return a.tolist()

def ref(d=None,**kw):
 return {'time':0,'box':[20,20,60,120],'sample_id':'manual','reviewer_kind':'test_operator','descriptor':d or desc(0),'quality':{'usable':True},**kw}

def obs(i='a',d=None,x=20,**kw):
 return {'id':i,'box':[x,20,x+40,120],'descriptor':d or desc(0),'quality':{'usable':True},'person_score':.9,**kw}

class Policy(unittest.TestCase):
 def setUp(self):self.o=obs();self.refs={'p1':[ref()],'p2':[ref(desc(8),sample_id='other')]}
 def evidence(self,o=None,items=None,refs=None):
  o=o or self.o;return p.observation_evidence(o,items if items is not None else [o],refs or self.refs,'p1',.5)
 def test_good_identity_with_actual_competitor_profile(self):
  e=self.evidence();self.assertTrue(e['eligible']);self.assertIsNone(e['person_margin']);self.assertFalse(e['is_probability'])
 def test_one_profile_without_competitors_has_unknown_margin(self):
  e=self.evidence(refs={'p1':[ref()]});self.assertFalse(e['eligible']);self.assertIsNone(e['profile_margin']);self.assertIsNone(e['person_margin'])
 def test_identical_other_profile_refuses_high(self):
  self.refs['p2']=[ref()];self.assertIn('ambiguous_player_profiles',self.evidence()['reasons'])
 def test_same_frame_lookalike_refuses_high(self):
  self.assertIn('ambiguous_same_frame_person',self.evidence(items=[self.o,obs('b',x=150)])['reasons'])
 def test_distinct_same_frame_person_is_evidence(self):
  self.assertTrue(self.evidence(items=[self.o,obs('b',desc(9),150)],refs={'p1':[ref()]})['eligible'])
 def test_duplicate_detector_box_is_not_independent_competitor(self):
  self.assertFalse(self.evidence(items=[self.o,obs('duplicate',x=21)],refs={'p1':[ref()]})['eligible'])
 def test_missing_quality_is_uncertain(self):
  self.o.pop('quality');self.assertFalse(self.evidence()['eligible'])
 def test_low_detection_score_is_uncertain(self):
  self.o['person_score']=.4;self.assertIn('weak_person_detection',self.evidence()['reasons'])
 def test_lower_clothing_mismatch_cannot_hide_behind_shirt(self):
  self.o['descriptor'][2]=desc(8)[2];self.assertIn('clothing_region_disagreement',self.evidence()['reasons'])
 def test_nonfinite_descriptor_is_uncertain(self):
  self.o['descriptor'][0][0]=float('nan');self.assertIn('invalid_descriptor',self.evidence()['reasons'])
 def test_no_automatic_reference_promotion(self):
  self.refs['p1']=[ref(is_automatic=True)];self.assertFalse(self.evidence()['eligible'])
 def test_unverified_origin_is_not_trusted(self):
  self.assertFalse(p.trusted(ref(origin='local_model')))
 def test_missing_reviewer_is_not_trusted(self):
  s=ref();s.pop('reviewer_kind');self.assertFalse(p.trusted(s))
 def test_conflicting_manual_references_are_uncertain(self):
  self.refs['p1']+=[ref(desc(8),time=1,sample_id='changed')];self.assertIn('conflicting_reference_appearance',self.evidence()['reasons'])
 def test_duplicate_reference_not_multiple_independent_samples(self):
  groups,_=p.reference_groups([ref(),ref(sample_id='duplicate')],.5);self.assertEqual(len(groups['default']),1)
 def test_reviewed_appearance_epochs_can_change_clothes(self):
  self.refs['p1']=[ref(valid_until=1),ref(desc(8),appearance='changed',time=2,valid_from=2)]
  self.assertTrue(self.evidence()['eligible']);groups,_=p.reference_groups(self.refs['p1'],2.5);self.assertEqual(list(groups),['changed'])
 def test_consistent_three_sample_fusion(self):
  self.refs['p1']=[ref(time=i,sample_id=str(i)) for i in range(3)];self.assertEqual(len(self.evidence()['reference_ids']),3)
 def result(self,times=(0,.3,.6),tracks=(1,1,1)):
  return {'records':[{'time':t,'accepted':[{'player_id':'p1','track_id':tr,'observation_id':str(t),'confidence_evidence':{'eligible':True}}],'uncertain':[]} for t,tr in zip(times,tracks)]}
 def candidate(self,r):return p.candidate_evidence(r,{'id':'event','start':0,'end':5},'p1')
 def test_contiguous_visible_track_does_not_prove_scorer_or_handler(self):
  e=self.candidate(self.result());self.assertEqual(e['presence_certainty'],'high');self.assertEqual(e['role_certainty'],{'visible':'high','scorer':'uncertain','handler':'uncertain'})
 def test_disjoint_person_tracks_do_not_combine(self):self.assertEqual(self.candidate(self.result(tracks=(1,2,3)))['presence_certainty'],'uncertain')
 def test_long_gap_does_not_count_as_contiguous(self):self.assertEqual(self.candidate(self.result(times=(0,.3,4)))['presence_certainty'],'uncertain')
 def test_repeated_same_time_is_not_support(self):self.assertEqual(self.candidate(self.result(times=(0,0,.6)))['presence_certainty'],'uncertain')
 def test_candidate_ambiguity_degrades_a_previously_clear_track(self):
  r=self.result();r['records'][1]['uncertain']=[{'player_id':'p1','confidence_evidence':{'distance':.1,'reasons':['ambiguous_same_frame_person']}}]
  self.assertEqual(self.candidate(r)['presence_certainty'],'uncertain')
 def test_unqualified_legacy_votes_do_not_count(self):
  r=self.result()
  for row in r['records']:row['accepted'][0].pop('confidence_evidence')
  self.assertEqual(self.candidate(r)['presence_certainty'],'uncertain')
 def test_other_person_presence_never_silently_drops_target(self):
  self.assertEqual(p.route_assignment({'certainty':'high','player_id':'p2'},'p1')[0],'uncertain')
 def test_legacy_other_label_is_not_explicit_target_absence(self):self.assertEqual(p.route_assignment({'certainty':'other'},'p1')[0],'uncertain')
 def test_explicit_operator_target_absence(self):
  q={'certainty':'other','absence_verified':True,'exclusion_for':'p1','reviewer':{'kind':'test_operator'}}
  self.assertEqual(p.route_assignment(q,'p1')[0],'other');self.assertEqual(p.route_assignment(q,'p2')[0],'uncertain')
 def test_model_cannot_verify_absence(self):
  self.assertEqual(p.route_assignment({'certainty':'other','absence_verified':True,'exclusion_for':'p1','reviewer':{'kind':'local_model'}},'p1')[0],'uncertain')
 def test_no_match_stays_available_to_review(self):self.assertEqual(p.route_assignment(None,'p1','scorer')[0],'uncertain')
 def test_presence_high_must_not_leak_to_scoring(self):
  q={'presence_certainty':'high','presence_player_id':'p1','certainty':'uncertain'}
  self.assertEqual(p.route_assignment(q,'p1','visible')[0],'high_confidence');self.assertEqual(p.route_assignment(q,'p1','scorer')[0],'uncertain')
 def test_operator_explicit_role_evidence_only(self):
  q={'certainty':'high','player_id':'p1','verified_roles':['scorer'],'reviewer':{'kind':'test_operator'},'role_evidence':{'role':'scorer','detail':'synthetic fixture only','authorization_reference':'test_operator fixture'}}
  self.assertEqual(p.route_assignment(q,'p1','scorer')[0],'high_confidence');self.assertEqual(p.route_assignment(q,'p1','handler')[0],'uncertain')
  q['reviewer']['kind']='local_model';self.assertEqual(p.route_assignment(q,'p1','scorer')[0],'uncertain')
 def test_reference_expansion_is_separate_draft_and_never_verified(self):
  r=self.result();data={'records':[{'time':row['time'],'items':[obs(str(row['time']))]} for row in r['records']]}
  for row in r['records']:row['accepted'][0]['confidence_evidence']['distance']=.1
  out=p.expansion_proposals(r,data,'p1');self.assertEqual(len(out),1)
  self.assertEqual(out[0]['status'],'draft');self.assertFalse(out[0]['affects_high_confidence']);self.assertFalse(p.trusted(out[0]))
 def test_low_quality_crop_conditions(self):
  a=np.full((180,180,3),120,dtype=np.uint8)
  self.assertIn('blur_or_uninformative_texture',p.crop_quality(a,[20,20,60,120])['reasons'])
  self.assertIn('too_small',p.crop_quality(a,[20,20,26,40])['reasons'])
  self.assertIn('clipped_body',p.crop_quality(a,[0,0,40,100])['reasons'])
 def test_valid_textured_crop(self):
  a=np.random.default_rng(7).integers(20,230,(180,180,3),dtype=np.uint8)
  self.assertTrue(p.crop_quality(a,[20,20,60,120])['usable'])
 def test_empty_reference_set_predicts_no_identity(self):
  import person_match
  with patch.object(person_match.media_io,'probe',return_value={}):
   out=person_match.predict({'video':'synthetic','records':[{'time':0,'items':[obs()]}]},{'people':[]})
  self.assertEqual(out['records'][0]['accepted'],[])
 def test_untrusted_reference_is_never_decoded_or_used_as_anchor(self):
  import person_match
  with patch.object(person_match.media_io,'probe',return_value={}),patch.object(person_match.media_io,'frame_bgr',side_effect=AssertionError('no auto reference decoding')):
   out=person_match.predict({'video':'synthetic','records':[{'time':0,'items':[obs()]}]},{'people':[{'id':'p1','samples':[ref(is_automatic=True)]}]})
  self.assertEqual(out['records'][0]['accepted'],[])

if __name__=='__main__':unittest.main()
