#!/usr/bin/env python3
"""Import ONLY facts already confirmed by the real Indiana user.

This one historical exception preserves chat-review provenance honestly. It
cannot confirm made shots, scorer, ball handler, exact time, or new videos.
It never modifies examples/indiana/project/ or an existing differing label.
"""
import json
from pathlib import Path
try:
    from .schema import DATASET, sha, require, validate_annotations
    from .locking import read_locked, write_registry
except ImportError:
    from schema import DATASET, sha, require, validate_annotations
    from locking import read_locked, write_registry
ROOT = Path(__file__).resolve().parents[1]


def bootstrap():
    project = ROOT/'examples/indiana/project/project.json'
    evidence = ROOT/'examples/indiana/project/review-decisions.json'
    p = json.loads(project.read_text()); decisions = json.loads(evidence.read_text())
    require(p['revision'] == 10 and p['confirmation']['reviewer_kind'] == 'user', 'LEGACY_USER_RECORD_CHANGED')
    require(decisions['reviewer_kind'] == 'user' and decisions['authorization_reference'] and
            decisions['decisions'] == {'c0001': 'keep', 'c0002': 'reject', 'c0003': 'keep', 'c0004': 'reject'},
            'LEGACY_REVIEW_EVIDENCE_MISMATCH')
    require(sha(evidence) == p['confirmation']['decision_sha256'], 'LEGACY_USER_RECORD_HASH_MISMATCH')
    doc = {'schema_version': 1, 'document_type': 'basketball_annotations', 'dataset_id': DATASET,
           'video_id': 'indiana', 'video_sha256': p['source']['sha256'], 'duration': p['source']['duration'],
           'target_player_ids': ['p1'], 'players': [{'id': 'p1',
               'appearance_description': '既有用户选择的紫衣2号，白色短袖、裸膝、浅色鞋'}],
           'events': [], 'reviewed_ranges': [],
           'legacy_scope': 'Clip-level target presence only. The user did NOT confirm shot times or made baskets.'}
    for c in p['candidates']:
        if c['id'] not in p['confirmation']['kept']:
            continue
        doc['events'].append({'id': c['id'], 'time': c['event_time'], 'is_score': None,
            'scorer_id': None, 'ball_handler_id': None, 'visible_player_ids': ['p1'],
            'visibility_complete': False, 'status': 'confirmed', 'deleted': False,
            'confirmed_fields': ['visible_player_ids'], 'legacy_candidate_id': c['id'],
            'clip_start': c['start'], 'clip_end': c['end'],
            'confirmation': {'source': 'legacy_indiana_user_review', 'reviewer_kind': 'user',
                'reviewer': decisions['reviewer'], 'confirmed_at': p['confirmation']['at'],
                'evidence_path': evidence.relative_to(ROOT).as_posix(), 'evidence_sha256': sha(evidence),
                'actual_authorization_reference': decisions['authorization_reference']},
            'notes': '历史人工确认仅支持此片段包含p1；事件时间、进球和其他球员角色尚未人工核实'})
    catalog = json.loads((ROOT/'eval/data/catalog.json').read_text())
    video = next(v for v in catalog['videos'] if v['id'] == 'indiana')
    validate_annotations(doc, video, allow_legacy=True)
    path = ROOT/'eval/annotations/confirmed/indiana.json'
    text = json.dumps(doc, ensure_ascii=False, indent=2) + '\n'
    require(not path.exists() or path.read_text() == text, 'REFUSE_TO_OVERWRITE_OR_RELOCK_CHANGED_LABELS')
    registry = ROOT/'eval/annotations/confirmed.lock.json'
    entries = read_locked(ROOT, registry)[0]['files'] if registry.exists() else []
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    relative = path.relative_to(ROOT).as_posix()
    entries = [e for e in entries if e['path'] != relative] + [
        {'path': relative, 'sha256': sha(path), 'video_id': 'indiana', 'video_sha256': video['sha256'],
         'origin': 'preexisting_user_confirmation; no new review-page confirmation fabricated'}]
    write_registry(ROOT, registry, 'eval/annotations/confirmed', entries)
    print('Imported 2 historical clip-presence facts; 0 confirmed made shots; original project untouched.')


if __name__ == '__main__':
    bootstrap()
