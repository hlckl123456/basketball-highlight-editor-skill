"""Synthetic unit fixtures only. Never imported into the real video corpus."""
import copy
import hashlib
import json
from pathlib import Path
from eval.schema import DATASET, PAGE_ID


def receipt(action='confirm_event'):
    return {'source': 'review_page', 'page_id': PAGE_ID, 'session_id': 'synthetic-unit-session',
            'action': action, 'reviewer_kind': 'user', 'reviewer': 'SYNTHETIC UNIT FIXTURE, NOT A REAL HUMAN',
            'confirmed_at': '2026-01-01T00:00:00+00:00'}


def video(vid='v1', split='development', content=b'SYNTHETIC VIDEO FIXTURE'):
    return {'id': vid, 'split': split, 'sha256': hashlib.sha256(content).hexdigest(), 'duration': 10,
            'group_id': vid+'-group', 'source_path': 'eval/data/sources/'+vid+'.mp4',
            'source_url': 'https://example.invalid/synthetic', 'author': 'Synthetic test generator',
            'license': 'CC0 synthetic fixture', 'license_url': 'https://example.invalid/synthetic-license',
            'downloaded_at': '2026-01-01', 'scene_type': 'synthetic_test',
            'filming_conditions': 'Synthetic test data, no real people', 'redistributable': True,
            'evaluation_ranges': [[0, 10]], 'review_media_path': 'eval/data/sources/'+vid+'.mp4'}


def event(eid='e1', time=4, status='confirmed', score=True, visible=None):
    e = {'id': eid, 'time': time, 'status': status, 'is_score': score, 'scorer_id': 'p2',
         'ball_handler_id': 'p1', 'visible_player_ids': ['p1'] if visible is None else visible,
         'visibility_complete': True, 'deleted': False, 'confirmed_fields': [], 'confirmation': None,
         'synthetic_fixture': True, 'notes': 'Synthetic fixture only'}
    if status == 'confirmed':
        e['confirmed_fields'] = ['time', 'is_score', 'scorer_id', 'ball_handler_id', 'visible_player_ids']
        e['confirmation'] = receipt()
    return e


def annotations(v=None, events=None, complete=True):
    v = v or video()
    return {'schema_version': 1, 'document_type': 'basketball_annotations', 'dataset_id': DATASET,
            'video_id': v['id'], 'video_sha256': v['sha256'], 'duration': v['duration'],
            'target_player_ids': ['p1'], 'players': [{'id': 'p1', 'appearance_description': 'Synthetic blue shape'},
            {'id': 'p2', 'appearance_description': 'Synthetic red shape'}],
            'events': [event()] if events is None else events,
            'reviewed_ranges': [{'start': 0, 'end': 10, 'status': 'confirmed',
                'event_search_complete': True, 'confirmation': receipt('confirm_range')}] if complete else []}


def prediction(pid='d1', time=4, group='high', assigned='p1'):
    return {'id': pid, 'kind': 'detected_event', 'time': time,
            'player_assignments': [{'target_player_id': 'p1', 'assigned_player_id': assigned, 'group': group}]}


def predictions(v=None, events=None):
    v = v or video()
    return {'schema_version': 1, 'document_type': 'basketball_predictions', 'video_id': v['id'],
            'video_sha256': v['sha256'], 'provenance': 'Synthetic test fixture, not a detector result',
            'events': [prediction()] if events is None else events}


def write(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')


def make_root(root, include_holdout=False):
    from eval.schema import sha
    from eval.locking import write_registry
    root = Path(root); videos = [video()]
    if include_holdout:
        videos.append(video('h1', 'holdout', b'SYNTHETIC HOLDOUT VIDEO'))
    catalog = {'schema_version': 1, 'dataset_id': DATASET, 'videos': videos}
    write(root/'eval/data/catalog.json', catalog)
    entries = []
    for v in videos:
        source = root/v['source_path']; source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b'SYNTHETIC HOLDOUT VIDEO' if v['id']=='h1' else b'SYNTHETIC VIDEO FIXTURE')
        path = root/'eval/annotations/confirmed'/(v['id']+'.json'); write(path, annotations(v))
        entries.append({'path': path.relative_to(root).as_posix(), 'sha256': sha(path),
                        'video_id': v['id'], 'video_sha256': v['sha256']})
        write(root/'eval/predictions'/(v['id']+'.json'), predictions(v))
        write(root/'eval/annotations/drafts'/(v['id']+'.json'), annotations(v, [event(status='draft')], False))
    write_registry(root, root/'eval/annotations/confirmed.lock.json', 'eval/annotations/confirmed', entries)
    return catalog
