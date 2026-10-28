import copy
import unittest
from eval.schema import validate_annotations, validate_catalog, validate_predictions, ValidationError, DATASET
from fixtures import video, event, annotations, predictions


class AnnotationSchema(unittest.TestCase):
    def setUp(self):
        self.video = video(); self.doc = annotations(self.video)

    def invalid(self, text=None):
        with self.assertRaises(ValidationError) as result:
            validate_annotations(self.doc, self.video)
        if text:
            self.assertIn(text, str(result.exception))

    def test_complete_fixture_is_valid(self):
        validate_annotations(self.doc, self.video)

    def test_draft_has_no_human_receipt(self):
        self.doc['events'][0]['status'] = 'draft'; self.invalid('DRAFT_CANNOT')

    def test_confirmed_requires_review_page_source(self):
        self.doc['events'][0]['confirmation']['source'] = 'local_model'; self.invalid('REVIEW_PAGE')

    def test_test_operator_cannot_become_human_truth(self):
        self.doc['events'][0]['confirmation']['reviewer_kind'] = 'test_operator'; self.invalid('HUMAN_REVIEWER')

    def test_confirmation_requires_time_and_timezone(self):
        for value in [None, 'yesterday', '2026-01-01T00:00:00']:
            with self.subTest(value=value):
                self.doc['events'][0]['confirmation']['confirmed_at'] = value; self.invalid()

    def test_event_bounds_and_nonfinite_time(self):
        for value in [-1, 11, float('nan'), float('inf'), True]:
            with self.subTest(value=value):
                self.doc['events'][0]['time'] = value; self.invalid('TIME')

    def test_unknown_actor_and_duplicate_event_are_rejected(self):
        self.doc['events'][0]['scorer_id'] = 'p99'; self.invalid('UNKNOWN_PLAYER')
        self.doc = annotations(); self.doc['events'].append(copy.deepcopy(self.doc['events'][0])); self.invalid('DUPLICATE')

    def test_unknown_visibility_is_not_an_empty_confirmed_list(self):
        e = self.doc['events'][0]; e['visible_player_ids'] = None; e['visibility_complete'] = True
        self.invalid('COMPLETE_VISIBILITY')

    def test_invalid_status_and_score_types(self):
        self.doc['events'][0]['status'] = 'approved'; self.invalid('STATUS')
        self.doc = annotations(); self.doc['events'][0]['is_score'] = 'yes'; self.invalid('BOOLEAN')

    def test_generator_can_only_write_drafts(self):
        with self.assertRaisesRegex(ValidationError, 'AUTOMATIC_GENERATOR'):
            validate_annotations(self.doc, self.video, require_all_draft=True)
        self.doc['events'] = [event(status='draft')]; self.doc['reviewed_ranges'] = []
        validate_annotations(self.doc, self.video, require_all_draft=True)

    def test_deleted_false_positive_stays_negative(self):
        self.doc['events'][0]['deleted'] = True; self.invalid('NEGATIVE')

    def test_source_hash_and_targets_are_validated(self):
        self.doc['video_sha256'] = '0'*64; self.invalid('HASH_MISMATCH')
        self.doc = annotations(); self.doc['target_player_ids'] = ['p77']; self.invalid('TARGET')

    def test_same_filming_group_cannot_cross_splits(self):
        a = video(); b = video('h', 'holdout', b'new'); b['group_id'] = a['group_id']
        with self.assertRaisesRegex(ValidationError, 'SPLIT_LEAKAGE'):
            validate_catalog({'schema_version': 1, 'dataset_id': DATASET, 'videos': [a,b]})

    def test_coverage_window_cannot_enter_detector_predictions(self):
        p = predictions(); p['events'][0]['kind'] = 'coverage_fallback'
        with self.assertRaisesRegex(ValidationError, 'NOT_DETECTIONS'):
            validate_predictions(p, self.video)


if __name__ == '__main__': unittest.main()
