"""Real corpus safety checks. This suite never creates human confirmations."""
import hashlib
import json
import unittest
from pathlib import Path
from eval.schema import validate_annotations, validate_catalog
from eval.locking import read_locked
ROOT=Path(__file__).resolve().parents[2]


class CorpusSafety(unittest.TestCase):
 def test_all_automatic_real_annotations_are_draft(self):
  catalog=validate_catalog(json.loads((ROOT/'eval/data/catalog.json').read_text()))
  self.assertGreaterEqual(len(catalog['videos']),8)
  self.assertEqual(sum(v['split']=='holdout' for v in catalog['videos']),3)
  for v in catalog['videos']:
   doc=json.loads((ROOT/'eval/annotations/drafts'/(v['id']+'.json')).read_text())
   validate_annotations(doc,v,require_all_draft=True)
   self.assertTrue(doc['events'])

 def test_only_real_user_or_preserved_legacy_facts_can_be_scored(self):
  registry,locked=read_locked(ROOT,ROOT/'eval/annotations/confirmed.lock.json')
  for entry,path in locked:
   doc=json.loads(path.read_text())
   for e in doc['events']:
    self.assertEqual(e['status'],'confirmed')
    self.assertEqual(e['confirmation']['reviewer_kind'],'user')
    self.assertIn(e['confirmation']['source'],['review_page','legacy_indiana_user_review'])
    if e['confirmation']['source']=='legacy_indiana_user_review':
     self.assertEqual(doc['video_id'],'indiana')
     self.assertEqual(e['confirmed_fields'],['visible_player_ids'])
     self.assertIsNone(e['is_score'])

 def test_original_user_project_is_byte_for_byte_unchanged(self):
  manifest=json.loads((ROOT/'eval/data/protected-indiana.json').read_text())
  actual={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (ROOT/'examples/indiana/project').rglob('*') if p.is_file()}
  self.assertEqual(actual,manifest)


if __name__=='__main__':unittest.main()
