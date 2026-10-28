"""Strict semantic validation. Standard library only; no inference of human truth."""
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path

DATASET = 'basketball-eval-v1'
PAGE_ID = 'basketball-eval-review-v1'
FIELDS = {'time', 'is_score', 'scorer_id', 'ball_handler_id', 'visible_player_ids'}
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')
HEX = re.compile(r'^[0-9a-f]{64}$')


class ValidationError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ValidationError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    # Integral floats normalize to ints to agree with JavaScript JSON.stringify.
    def normalize(v):
        if isinstance(v, dict):
            return {k: normalize(x) for k, x in v.items()}
        if isinstance(v, list):
            return [normalize(x) for x in v]
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v
    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def timestamp(value):
    require(isinstance(value, str), 'CONFIRMATION_TIME_REQUIRED')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        raise ValidationError('INVALID_CONFIRMATION_TIME')
    require(parsed.tzinfo is not None, 'CONFIRMATION_TIME_REQUIRES_TIMEZONE')
    require(parsed <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10),
            'CONFIRMATION_TIME_IN_FUTURE')


def confirmation(value, allow_legacy=False):
    require(isinstance(value, dict), 'CONFIRMED_REQUIRES_REVIEW_RECEIPT')
    require(value.get('reviewer_kind') == 'user' and bool(value.get('reviewer', '').strip()),
            'HUMAN_REVIEWER_REQUIRED')
    timestamp(value.get('confirmed_at'))
    source = value.get('source')
    if source == 'legacy_indiana_user_review' and allow_legacy:
        require(value.get('evidence_path') == 'examples/indiana/project/review-decisions.json' and HEX.fullmatch(value.get('evidence_sha256', '')),
                'LEGACY_EVIDENCE_REQUIRED')
        return
    require(source == 'review_page' and value.get('page_id') == PAGE_ID,
            'CONFIRMATION_MUST_COME_FROM_REVIEW_PAGE')
    require(bool(value.get('session_id')) and value.get('action') in
            ('confirm_event', 'false_positive', 'confirm_range'), 'INVALID_REVIEW_RECEIPT')


def validate_catalog(data):
    require(data.get('schema_version') == 1 and data.get('dataset_id') == DATASET,
            'INVALID_CATALOG_VERSION')
    videos = data.get('videos')
    require(isinstance(videos, list) and videos, 'EMPTY_VIDEO_CATALOG')
    ids, groups = set(), {}
    for v in videos:
        vid = v.get('id', '')
        require(ID.fullmatch(vid) is not None and vid not in ids, 'INVALID_OR_DUPLICATE_VIDEO_ID')
        ids.add(vid)
        require(v.get('split') in ('development', 'holdout'), 'INVALID_SPLIT')
        require(number(v.get('duration')) and v['duration'] > 0, 'INVALID_DURATION')
        require(HEX.fullmatch(v.get('sha256', '')) is not None, 'INVALID_SOURCE_HASH')
        for key in ('source_url', 'author', 'license', 'license_url', 'downloaded_at',
                    'source_path', 'scene_type', 'filming_conditions', 'group_id'):
            require(isinstance(v.get(key), str) and v[key].strip(), 'MISSING_VIDEO_FIELD: ' + key)
        require(type(v.get('redistributable')) is bool, 'REDISTRIBUTION_FLAG_REQUIRED')
        require(not Path(v['source_path']).is_absolute() and '..' not in Path(v['source_path']).parts,
                'SOURCE_PATH_MUST_BE_REPOSITORY_RELATIVE')
        if not v['redistributable']:
            require(v['source_path'].startswith('eval/local-media/'), 'PRIVATE_MEDIA_MUST_STAY_LOCAL')
        prior = groups.setdefault(v['group_id'], v['split'])
        require(prior == v['split'], 'FILMING_GROUP_SPLIT_LEAKAGE')
    return data


def validate_annotations(doc, video, allow_legacy=False, require_all_draft=False):
    require(doc.get('schema_version') == 1 and doc.get('document_type') == 'basketball_annotations',
            'INVALID_ANNOTATION_VERSION')
    require(doc.get('dataset_id') == DATASET and doc.get('video_id') == video['id'],
            'ANNOTATION_VIDEO_MISMATCH')
    require(doc.get('video_sha256') == video['sha256'], 'ANNOTATION_SOURCE_HASH_MISMATCH')
    require(number(doc.get('duration')) and abs(doc['duration'] - video['duration']) < .05,
            'ANNOTATION_DURATION_MISMATCH')
    players = doc.get('players', [])
    require(isinstance(players, list), 'PLAYERS_MUST_BE_ARRAY')
    pids = set()
    for p in players:
        require(ID.fullmatch(p.get('id', '')) is not None and p['id'] not in pids,
                'INVALID_OR_DUPLICATE_PLAYER_ID')
        require(bool(p.get('appearance_description', '').strip()), 'PLAYER_DESCRIPTION_REQUIRED')
        pids.add(p['id'])
    targets = doc.get('target_player_ids', [])
    require(isinstance(targets, list) and len(set(targets)) == len(targets) and set(targets) <= pids, 'INVALID_TARGET_PLAYERS')
    events = doc.get('events')
    require(isinstance(events, list), 'EVENTS_MUST_BE_ARRAY')
    ids = set()
    for e in events:
        require(ID.fullmatch(e.get('id', '')) is not None and e['id'] not in ids,
                'INVALID_OR_DUPLICATE_EVENT_ID')
        ids.add(e['id'])
        require(number(e.get('time')) and 0 <= e['time'] <= video['duration'], 'EVENT_TIME_OUT_OF_RANGE')
        require(e.get('is_score') is None or type(e['is_score']) is bool, 'IS_SCORE_MUST_BE_BOOLEAN_OR_NULL')
        for key in ('scorer_id', 'ball_handler_id'):
            require(e.get(key) is None or e[key] in pids, 'UNKNOWN_PLAYER: ' + key)
        visible = e.get('visible_player_ids')
        require(visible is None or (isinstance(visible, list) and len(set(visible)) == len(visible)
                and set(visible) <= pids), 'INVALID_VISIBLE_PLAYERS')
        require(type(e.get('visibility_complete', False)) is bool, 'INVALID_VISIBILITY_COMPLETENESS')
        require(not e.get('visibility_complete') or visible is not None, 'COMPLETE_VISIBILITY_NEEDS_LIST')
        require(type(e.get('deleted', False)) is bool, 'INVALID_DELETED_FLAG')
        require(not e.get('deleted') or e.get('is_score') is False, 'DELETED_EVENT_MUST_BE_NEGATIVE')
        require(e.get('status') in ('draft', 'confirmed'), 'INVALID_ANNOTATION_STATUS')
        fields = e.get('confirmed_fields', [])
        require(isinstance(fields, list) and len(fields) == len(set(fields)) and set(fields) <= FIELDS,
                'INVALID_CONFIRMED_FIELDS')
        if e['status'] == 'draft':
            require(not fields and e.get('confirmation') is None, 'DRAFT_CANNOT_CARRY_CONFIRMATION')
        else:
            require(not require_all_draft, 'AUTOMATIC_GENERATOR_MUST_ONLY_WRITE_DRAFTS')
            confirmation(e.get('confirmation'), allow_legacy)
            require(bool(fields), 'CONFIRMED_FIELDS_REQUIRED')
            legacy = e['confirmation']['source'] == 'legacy_indiana_user_review'
            if legacy:
                require(doc['video_id'] == 'indiana' and set(fields) <= {'visible_player_ids'},
                        'LEGACY_REVIEW_CANNOT_CONFIRM_SHOTS_OR_TIMESTAMPS')
                require(e.get('legacy_candidate_id') in ('c0001', 'c0003'), 'LEGACY_UNSUPPORTED_CANDIDATE')
                require(e.get('visible_player_ids') == ['p1'] and not e.get('visibility_complete'),
                        'LEGACY_REVIEW_ONLY_CONFIRMED_TARGET_PRESENCE')
            else:
                require('time' in fields, 'CONFIRMED_EVENT_REQUIRES_TIME_REVIEW')
    for r in doc.get('reviewed_ranges', []):
        require(number(r.get('start')) and number(r.get('end')) and
                0 <= r['start'] < r['end'] <= video['duration'], 'INVALID_REVIEWED_RANGE')
        require(r.get('status') in ('draft', 'confirmed'), 'INVALID_RANGE_STATUS')
        if r['status'] == 'confirmed':
            require(not require_all_draft, 'AUTOMATIC_GENERATOR_MUST_ONLY_WRITE_DRAFTS')
            confirmation(r.get('confirmation'), False)
            require(r.get('event_search_complete') is True, 'RANGE_REQUIRES_EXHAUSTIVE_EVENT_REVIEW')
        else:
            require(r.get('confirmation') is None, 'DRAFT_RANGE_CANNOT_CARRY_CONFIRMATION')
    return doc


def validate_predictions(doc, video):
    require(doc.get('schema_version') == 1 and doc.get('document_type') == 'basketball_predictions',
            'INVALID_PREDICTION_VERSION')
    require(doc.get('video_id') == video['id'] and doc.get('video_sha256') == video['sha256'],
            'PREDICTION_SOURCE_MISMATCH')
    require(bool(doc.get('provenance')), 'PREDICTION_PROVENANCE_REQUIRED')
    ids = set()
    for e in doc.get('events', []):
        require(ID.fullmatch(e.get('id', '')) is not None and e['id'] not in ids,
                'INVALID_OR_DUPLICATE_PREDICTION_ID')
        ids.add(e['id'])
        require(number(e.get('time')) and 0 <= e['time'] <= video['duration'], 'PREDICTION_TIME_OUT_OF_RANGE')
        require(e.get('kind') == 'detected_event', 'COVERAGE_WINDOWS_ARE_NOT_DETECTIONS')
        targets = set()
        for p in e.get('player_assignments', []):
            pid = p.get('target_player_id', '')
            require(ID.fullmatch(pid) is not None and pid not in targets, 'INVALID_PREDICTION_TARGET')
            targets.add(pid)
            require(p.get('group') in ('high', 'uncertain', 'excluded'), 'INVALID_PLAYER_GROUP')
            require(p.get('assigned_player_id') is None or ID.fullmatch(p['assigned_player_id']),
                    'INVALID_ASSIGNED_PLAYER')
    return doc
