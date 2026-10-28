import copy
import json
import tempfile
import unittest
from pathlib import Path
from eval.score import match_times, score_video, ratios, evaluate_repository
from eval.schema import ValidationError
from fixtures import video, event, annotations, prediction, predictions, make_root


class Scoring(unittest.TestCase):
    def test_one_second_tolerance_is_inclusive(self):
        self.assertEqual(match_times([{'time':3}], [{'time':4}]), [(0,0)])
        self.assertEqual(match_times([{'time':3}], [{'time':4.00001}]), [])

    def test_global_matching_avoids_greedy_undercount(self):
        self.assertEqual(len(match_times([{'time':0}, {'time':.9}], [{'time':.8}, {'time':1.8}])), 2)

    def test_duplicates_cannot_match_twice(self):
        d = score_video(annotations(), predictions(events=[prediction('a',4),prediction('b',4.2)]))
        self.assertEqual((d['counts']['tp'],d['counts']['fp'],d['counts']['fn']), (1,1,0))
        self.assertAlmostEqual(ratios(d['counts'])['event_f1'], 2/3)

    def test_missed_event_is_a_false_negative(self):
        d = score_video(annotations(events=[event('a',2),event('b',8)]), predictions(events=[prediction(time=2)]))
        self.assertEqual(d['counts']['fn'], 1); self.assertEqual(ratios(d['counts'])['event_recall'], .5)

    def test_drafts_are_ignored(self):
        doc = annotations(events=[event('a',2,'draft')], complete=False)
        d = score_video(doc, predictions(events=[prediction(time=2)]))
        self.assertEqual(d['counts']['tp'],0); self.assertEqual(d['draft_events_ignored'],1)
        self.assertIsNone(ratios(d['counts'])['event_recall'])

    def test_unreviewed_predictions_are_not_false_positives(self):
        d = score_video(annotations(events=[], complete=False), predictions())
        self.assertEqual(d['counts']['fp'],0); self.assertEqual(d['counts']['ignored_unreviewed_predictions'],1)

    def test_explicit_negative_can_score_without_full_interval(self):
        d = score_video(annotations(events=[event(score=False)], complete=False), predictions())
        self.assertEqual(d['counts']['fp'],1)

    def test_unknown_shot_truth_is_never_assumed_negative(self):
        d = score_video(annotations(events=[event(score=None)]), predictions())
        self.assertEqual(d['counts']['fp'],0); self.assertEqual(d['counts']['ignored_unknown_predictions'],1)

    def test_draft_interval_does_not_enable_false_positive_scoring(self):
        doc = annotations(events=[])
        doc['reviewed_ranges'][0].update(status='draft',confirmation=None)
        d = score_video(doc,predictions()); self.assertEqual(d['counts']['fp'],0)

    def test_three_player_metrics_have_separate_denominators(self):
        doc = annotations(events=[event('a',2),event('b',5),event('c',8,visible=[])])
        pred = predictions(events=[prediction('a',2,'high'),prediction('b',5,'uncertain',None),prediction('c',8,'high')])
        metrics = ratios(score_video(doc,pred)['counts'])
        self.assertEqual(metrics['high_assignment_accuracy'], .5)
        self.assertEqual(metrics['target_event_retrieval_high_or_uncertain'], 1)
        self.assertEqual(metrics['high_confidence_coverage'], .5)

    def test_visible_player_is_not_assumed_to_be_scorer(self):
        doc = annotations(); pred = predictions()
        self.assertEqual(ratios(score_video(doc,pred,'visible')['counts'])['high_assignment_accuracy'],1)
        self.assertEqual(ratios(score_video(doc,pred,'scorer')['counts'])['high_assignment_accuracy'],0)

    def test_partial_visibility_does_not_imply_other_players_absent(self):
        doc = annotations();doc['events'][0]['visible_player_ids']=['p2'];doc['events'][0]['visibility_complete']=False
        self.assertIsNone(ratios(score_video(doc,predictions())['counts'])['high_assignment_accuracy'])

    def test_wrong_assigned_identity_fails_high_accuracy_and_coverage(self):
        c=score_video(annotations(),predictions(events=[prediction(assigned='p2')]))['counts']
        self.assertEqual(ratios(c)['high_assignment_accuracy'],0)
        self.assertEqual(ratios(c)['high_confidence_coverage'],0)

    def test_holdout_is_separate_and_requires_explicit_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);make_root(root,True)
            args=(root,root/'eval/data/catalog.json',root/'eval/annotations/confirmed.lock.json',root/'eval/predictions')
            d=evaluate_repository(*args)
            self.assertEqual(d['splits']['holdout']['status'],'withheld')
            with self.assertRaisesRegex(ValidationError,'EXPLICIT_INCLUDE_HOLDOUT'):
                evaluate_repository(*args,video_ids=['h1'])
            both=evaluate_repository(*args,include_holdout=True)
            self.assertEqual(both['splits']['development']['counts']['tp'],1)
            self.assertEqual(both['splits']['holdout']['counts']['tp'],1)

    def test_scoring_does_not_mutate_labels_or_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);make_root(root)
            files=list((root/'eval/annotations').rglob('*.json'));before={p:p.read_bytes() for p in files}
            evaluate_repository(root,root/'eval/data/catalog.json',root/'eval/annotations/confirmed.lock.json',root/'eval/predictions')
            self.assertEqual(before,{p:p.read_bytes() for p in files})

    def test_real_indiana_baseline_does_not_invent_made_shots(self):
        root=Path(__file__).resolve().parents[2]
        d=evaluate_repository(root,root/'eval/data/catalog.json',root/'eval/annotations/confirmed.lock.json',root/'eval/predictions',video_ids=['indiana'])
        split=d['splits']['development']
        self.assertEqual(split['counts']['target_events'],2)
        self.assertEqual(split['metrics']['high_assignment_accuracy'],1)
        self.assertIsNone(split['metrics']['event_f1'])
        self.assertEqual(split['counts']['confirmed_positive_events'],0)


if __name__ == '__main__': unittest.main()
