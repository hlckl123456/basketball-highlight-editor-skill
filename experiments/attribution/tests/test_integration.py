"""Workflow boundaries using test_operator fixtures only."""
import json,sys,unittest
from pathlib import Path
from types import SimpleNamespace as A
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/tests'))
import test_workflow as wf

class Integration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):wf.Workflow.setUpClass()
 @classmethod
 def tearDownClass(cls):wf.Workflow.tearDownClass()
 def setUp(self):
  self.fixture=wf.Workflow(methodName='runTest');self.fixture._testMethodName=self._testMethodName;self.fixture.setUp();self.h=wf.h;self.root=self.fixture.root
 def tearDown(self):self.fixture.tearDown()
 def test_other_identified_player_is_not_excluded(self):
  self.fixture.select();_,p=self.h.load(self.root)
  p['candidates'][0]['assignment']['player_id']='another';self.h.write(self.root/'project.json',p)
  self.h.cmd_select(A(project=self.root,player='white21',selected_by='test_operator',role='visible'))
  _,p=self.h.load(self.root);self.assertEqual(p['selection']['other'],[]);self.assertEqual(p['selection']['uncertain'],['c0001','c0002'])
 def test_old_identity_high_not_high_scorer(self):
  self.fixture.select();self.h.cmd_select(A(project=self.root,player='white21',selected_by='test_operator',role='scorer'))
  _,p=self.h.load(self.root);self.assertEqual(p['selection']['high_confidence'],[]);self.assertEqual(len(p['selection']['uncertain']),2)
 def test_explicit_operator_role_review_can_be_recorded(self):
  data=self.fixture.data;item=data['assignments'][0];item.update(verified_roles=['scorer'],role_evidence={'role':'scorer','detail':'Synthetic role verification fixture, no real event label','authorization_reference':'test_operator fixture'})
  self.h.write(self.fixture.annotation,data);self.h.cmd_annotate(A(project=self.root,file=self.fixture.annotation));self.h.cmd_select(A(project=self.root,player='white21',selected_by='test_operator',role='scorer'))
  _,p=self.h.load(self.root);self.assertEqual(p['selection']['high_confidence'],['c0001']);self.assertEqual(p['candidates'][0]['assignment']['reviewer']['kind'],'test_operator')
 def test_model_cannot_author_role_review_through_annotate(self):
  data=self.fixture.data;data['reviewer']['kind']='agent_visual_review';data['assignments'][0].update(verified_roles=['scorer'],role_evidence={'role':'scorer','detail':'unsupported','authorization_reference':'not human'})
  self.h.write(self.fixture.annotation,data)
  with self.assertRaisesRegex(ValueError,'VERIFIED_ROLE'):self.h.cmd_annotate(A(project=self.root,file=self.fixture.annotation))
 def test_role_review_requires_traceable_authorization(self):
  data=self.fixture.data;data['assignments'][0].update(verified_roles=['scorer'],role_evidence={'role':'scorer','detail':'missing review reference'})
  self.h.write(self.fixture.annotation,data);before=(self.root/'project.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'VERIFIED_ROLE'):self.h.cmd_annotate(A(project=self.root,file=self.fixture.annotation))
  self.assertEqual((self.root/'project.json').read_bytes(),before)
 def test_match_default_role_survives_select_and_report(self):
  self.fixture.prepare_person_scan()
  with patch.dict('sys.modules',{'person_match':A(predict=lambda *a:{'records':[]})}):self.h.cmd_match_people(A(project=self.root,player='white21',apply=True))
  self.h.cmd_select(A(project=self.root,player='white21',selected_by='test_operator'));_,p=self.h.load(self.root)
  self.assertEqual(p['selection']['role'],'scorer');self.assertEqual(p['selection']['high_confidence'],[]);self.assertEqual(len(p['selection']['uncertain']),2)
  self.assertEqual(p['samples'][0]['reviewer_kind'],'test_operator');self.assertEqual(len(p['samples']),1)
  expanded=self.h.read(self.root/'people/reference-proposals.json');self.assertEqual(expanded['status'],'draft');self.assertFalse(expanded['affects_high_confidence'])
  self.assertIn('visible 高置信只表示人在场',(self.root/'review.html').read_text());self.assertIn('selection_reason',(self.root/'candidates.csv').read_text())
 def test_bad_reference_validity_is_rejected_before_media_mutations(self):
  before=(self.root/'project.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'INVALID_REFERENCE_VALIDITY'):
   self.h.cmd_sample(A(project=self.root,time=0,player='white21',bbox=[0,0,10,10],reviewer_kind='test_operator',valid_from=2,valid_until=1))
  self.assertEqual((self.root/'project.json').read_bytes(),before);self.assertFalse((self.root/'samples').exists())

if __name__=='__main__':unittest.main()
