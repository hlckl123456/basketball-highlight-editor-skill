import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from eval.locking import read_locked
from eval.score import evaluate_repository
from eval.schema import DATASET, PAGE_ID, ValidationError, sha
from eval.import_review import import_review
from fixtures import make_root, annotations, video, event, write


def export_fixture(root, doc, synthetic=False):
    payload={'dataset_id':DATASET,'catalog_sha256':sha(root/'eval/data/catalog.json'),
             'exported_at':'2026-01-01T00:00:00Z','session_id':'synthetic-unit-session',
             'reviewer':'SYNTHETIC UNIT FIXTURE, NO REAL HUMAN','synthetic':synthetic,'videos':[doc]}
    serialized=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
    value={'schema_version':1,'document_type':'basketball_review_export','page_id':PAGE_ID,
           'payload':payload,'integrity':{'algorithm':'sha256','serialized_payload':serialized,
                    'sha256':hashlib.sha256(serialized.encode()).hexdigest()}}
    path=root/'synthetic-export.json';write(path,value);return path


class LocksAndImports(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);make_root(self.root)
        self.registry=self.root/'eval/annotations/confirmed.lock.json'
        self.label=self.root/'eval/annotations/confirmed/v1.json'
    def tearDown(self):self.tmp.cleanup()
    def score(self):
        return evaluate_repository(self.root,self.root/'eval/data/catalog.json',self.registry,self.root/'eval/predictions')

    def test_whitespace_tampering_is_rejected(self):
        self.label.write_text(self.label.read_text()+'\n')
        with self.assertRaisesRegex(ValidationError,'CONFIRMED_HASH_MISMATCH'):self.score()

    def test_semantic_tampering_is_rejected(self):
        d=json.loads(self.label.read_text());d['events'][0]['time']=8;write(self.label,d)
        with self.assertRaisesRegex(ValidationError,'CONFIRMED_HASH_MISMATCH'):self.score()

    def test_missing_and_unlocked_confirmed_files_are_rejected(self):
        self.label.unlink()
        with self.assertRaisesRegex(ValidationError,'HASH_MISMATCH'):read_locked(self.root,self.registry)
        make_root(self.root);write(self.label.parent/'unlocked.json',annotations())
        with self.assertRaisesRegex(ValidationError,'UNLOCKED_CONFIRMED'):self.score()

    def test_lock_path_cannot_escape_root(self):
        r=json.loads(self.registry.read_text());r['files'][0]['path']='../outside.json';write(self.registry,r)
        with self.assertRaisesRegex(ValidationError,'ESCAPES'):read_locked(self.root,self.registry)

    def test_changed_source_video_is_rejected(self):
        (self.root/'eval/data/sources/v1.mp4').write_bytes(b'changed')
        with self.assertRaisesRegex(ValidationError,'SOURCE_MEDIA_HASH'):self.score()

    def test_holdout_hashes_still_lock_when_metrics_withheld(self):
        make_root(self.root,True);p=self.root/'eval/annotations/confirmed/h1.json';p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValidationError,'HASH_MISMATCH'):self.score()

    def test_import_copies_only_explicit_confirmations_and_relocks(self):
        doc=annotations(events=[event('confirmed-fixture',3),event('draft-fixture',7,'draft')],complete=False)
        export=export_fixture(self.root,doc);result=import_review(export,self.root)
        self.assertEqual(result['confirmed_events'],1);self.assertEqual(result['draft_events'],1)
        locked=json.loads(self.label.read_text());self.assertEqual([e['id'] for e in locked['events']],['confirmed-fixture'])
        state=json.loads((self.root/'eval/annotations/review-state/v1.json').read_text())
        self.assertEqual(state['events'][1]['status'],'draft');read_locked(self.root,self.registry)

    def test_synthetic_browser_exports_cannot_enter_real_dataset(self):
        export=export_fixture(self.root,annotations(),synthetic=True)
        with self.assertRaisesRegex(ValidationError,'SYNTHETIC_UI_TEST_EXPORT'):import_review(export,self.root)

    def test_changed_playback_media_is_rejected_before_import(self):
        catalog=json.loads((self.root/'eval/data/catalog.json').read_text())
        media=self.root/'eval/data/sources/review.mp4';media.write_bytes(b'SYNTHETIC PLAYBACK')
        catalog['videos'][0]['review_media_path']=media.relative_to(self.root).as_posix()
        catalog['videos'][0]['review_media_sha256']=sha(media)
        write(self.root/'eval/data/catalog.json',catalog)
        export=export_fixture(self.root,annotations());media.write_bytes(b'WRONG PLAYBACK')
        with self.assertRaisesRegex(ValidationError,'REVIEW_MEDIA_HASH_MISMATCH'):
            import_review(export,self.root)

    def test_export_payload_edit_breaks_integrity(self):
        export=export_fixture(self.root,annotations());d=json.loads(export.read_text());d['payload']['videos'][0]['events'][0]['time']=9;write(export,d)
        with self.assertRaisesRegex(ValidationError,'DIFFERS_FROM_HASHED'):import_review(export,self.root)

    def test_catalog_changes_require_rebuild_and_review(self):
        export=export_fixture(self.root,annotations());p=self.root/'eval/data/catalog.json';p.write_text(p.read_text()+'\n')
        with self.assertRaisesRegex(ValidationError,'CATALOG_CHANGED'):import_review(export,self.root)

    def test_import_refuses_to_relock_already_tampered_truth(self):
        export=export_fixture(self.root,annotations());self.label.write_text(self.label.read_text()+'\n')
        with self.assertRaisesRegex(ValidationError,'HASH_MISMATCH'):import_review(export,self.root)

    def test_invalid_second_video_does_not_partially_write_first(self):
        make_root(self.root,True);doc=annotations(events=[event('new-label',4)])
        export=export_fixture(self.root,doc);d=json.loads(export.read_text());bad=annotations(video('h1','holdout',b'SYNTHETIC HOLDOUT VIDEO'));bad['events'][0]['time']=999
        d['payload']['videos'].append(bad);s=json.dumps(d['payload'],separators=(',',':'));d['integrity']={'algorithm':'sha256','serialized_payload':s,'sha256':hashlib.sha256(s.encode()).hexdigest()};write(export,d)
        before=self.label.read_bytes()
        with self.assertRaisesRegex(ValidationError,'TIME_OUT_OF_RANGE'):import_review(export,self.root)
        self.assertEqual(self.label.read_bytes(),before)

    def test_cli_nonzero_on_tampered_confirmed_file(self):
        self.label.write_text(self.label.read_text()+'\n');script=Path(__file__).resolve().parents[1]/'score.py'
        r=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--output',str(self.root/'scores.json')],capture_output=True,text=True)
        self.assertEqual(r.returncode,2);self.assertIn('CONFIRMED_HASH_MISMATCH',r.stderr)
        self.assertFalse((self.root/'scores.json').exists())


if __name__=='__main__':unittest.main()
