"""Synthetic arithmetic fixtures; not annotations of any real video."""
import copy,importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'eval/tests'))
from fixtures import annotations as fixture_annotations,event

def annotations(**kwargs):
 doc=fixture_annotations(**kwargs)
 for item in doc["events"]+doc["reviewed_ranges"]:
  if item.get("confirmation"):
   item["confirmation"].update(reviewer_kind="test_operator",source="synthetic_test_operator",reviewer="Synthetic arithmetic fixture only; no human confirmation")
 return doc
spec=importlib.util.spec_from_file_location('attribution_benchmark',ROOT/'experiments/attribution/benchmark.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class Benchmark(unittest.TestCase):
 def test_only_confirmed_events_enter_windows(self):
  doc=annotations(events=[event('actual',2),event('draft',5,status='draft')])
  self.assertEqual([w['id'] for w in b.windows(doc,10)],['actual'])
 def test_no_event_time_is_invented_without_legacy_boundaries(self):
  e=event();e['confirmed_fields']=['visible_player_ids'];doc=annotations(events=[e])
  self.assertEqual(b.windows(doc,10),[])
 def test_reference_exclusion_does_not_rewrite_ground_truth(self):
  doc=annotations(events=[event('held',2),event('reference',8)]);before=copy.deepcopy(doc)
  task={'target_player_id':'p1','evaluation_event_ids':['held'],'calibration_event_ids':['reference'],'windows':[{'id':'held','time':2},{'id':'reference','time':8}]}
  groups={r:{'held':'high','reference':'high'} for r in ['scorer','handler','visible']}
  result=b.score_groups(doc,task,groups)
  self.assertEqual(doc,before);self.assertEqual(result['visible']['metrics']['high_assignment_accuracy'],1)
  self.assertEqual(result['scorer']['metrics']['high_assignment_accuracy'],0)
  self.assertEqual(result['handler']['metrics']['high_assignment_accuracy'],1)
  self.assertEqual(result['visible']['counts']['confirmed_positive_events'],1)
 def test_no_high_is_undefined_honesty_not_perfect(self):
  doc=annotations(events=[event('only',2)]);task={'target_player_id':'p1','evaluation_event_ids':['only'],'calibration_event_ids':[],'windows':[{'id':'only','time':2}]}
  result=b.score_groups(doc,task,{r:{'only':'uncertain'} for r in ['scorer','handler','visible']})
  self.assertIsNone(result['visible']['metrics']['high_assignment_accuracy']);self.assertEqual(result['visible']['metrics']['target_event_retrieval_high_or_uncertain'],1)
  self.assertEqual(result['visible']['metrics']['high_confidence_coverage'],0)

if __name__=='__main__':unittest.main()
