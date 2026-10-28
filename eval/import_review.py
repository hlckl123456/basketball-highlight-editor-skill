#!/usr/bin/env python3
"""Import an explicit review-page export, validate provenance, then lock facts.

No field changes status here. Drafts remain drafts. Browser receipts and hashes
are auditable local provenance, not cryptographic proof of a human identity.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
try:
    from .schema import DATASET, PAGE_ID, validate_catalog, validate_annotations, require, sha, timestamp
    from .locking import read_locked, write_registry
except ImportError:
    from schema import DATASET, PAGE_ID, validate_catalog, validate_annotations, require, sha, timestamp
    from locking import read_locked, write_registry
ROOT = Path(__file__).resolve().parents[1]


def read_export(path, catalog_path):
    export = json.loads(Path(path).read_text())
    require(export.get('schema_version') == 1 and export.get('document_type') == 'basketball_review_export'
            and export.get('page_id') == PAGE_ID, 'NOT_A_REVIEW_PAGE_EXPORT')
    payload = export.get('payload')
    integrity = export.get('integrity', {})
    serialized = integrity.get('serialized_payload')
    require(isinstance(serialized, str) and integrity.get('algorithm') == 'sha256', 'EXPORT_INTEGRITY_REQUIRED')
    require(hashlib.sha256(serialized.encode()).hexdigest() == integrity.get('sha256'), 'EXPORT_HASH_MISMATCH')
    require(json.loads(serialized) == payload, 'EXPORT_PAYLOAD_DIFFERS_FROM_HASHED_SERIALIZATION')
    require(payload.get('dataset_id') == DATASET and payload.get('catalog_sha256') == sha(catalog_path),
            'EXPORT_CATALOG_CHANGED_REBUILD_REVIEW_PAGE')
    require(not payload.get('synthetic', False), 'SYNTHETIC_UI_TEST_EXPORT_CANNOT_ENTER_REAL_DATASET')
    timestamp(payload.get('exported_at'))
    require(bool(payload.get('session_id')) and bool(payload.get('reviewer', '').strip()), 'EXPORT_REVIEWER_REQUIRED')
    return payload


def import_review(export_path, root=ROOT):
    root = Path(root).resolve(); catalog_path = root/'eval/data/catalog.json'
    catalog = validate_catalog(json.loads(catalog_path.read_text()))
    payload = read_export(export_path, catalog_path)
    videos = {v['id']: v for v in catalog['videos']}
    registry_path = root/'eval/annotations/confirmed.lock.json'
    registry, existing = read_locked(root, registry_path)
    entries = {e['video_id']: e for e, p in existing}
    old_docs = {e['video_id']: json.loads(p.read_text()) for e, p in existing}
    writes, seen, counts = {}, set(), {'confirmed_events': 0, 'draft_events': 0, 'confirmed_ranges': 0}
    for doc in payload.get('videos', []):
        vid = doc.get('video_id')
        require(vid in videos and vid not in seen, 'UNKNOWN_OR_DUPLICATE_EXPORTED_VIDEO')
        seen.add(vid)
        validate_annotations(doc, videos[vid], allow_legacy=vid == 'indiana')
        for event in doc['events']:
            if event['status'] != 'confirmed':
                continue
            conf = event['confirmation']
            if conf['source'] == 'legacy_indiana_user_review':
                old = old_docs.get(vid, {})
                require(event in old.get('events', []), 'CANNOT_CREATE_OR_EDIT_LEGACY_CONFIRMATIONS')
                p1 = next((p for p in doc['players'] if p['id'] == 'p1'), None)
                old_p1 = next((p for p in old.get('players', []) if p['id'] == 'p1'), None)
                require(p1 == old_p1, 'LEGACY_PLAYER_DESCRIPTION_CHANGED_REVIEW_AGAIN')
        facts = copy.deepcopy(doc)
        facts['events'] = [e for e in doc['events'] if e['status'] == 'confirmed']
        facts['reviewed_ranges'] = [r for r in doc.get('reviewed_ranges', []) if r['status'] == 'confirmed']
        # A new roster/target selection is retained for the next review session;
        # the importer never invents a confirmation for unchanged drafts.
        state = root/'eval/annotations/review-state'/(vid + '.json')
        writes[state] = json.dumps(doc, ensure_ascii=False, indent=2) + '\n'
        if facts['events'] or facts['reviewed_ranges'] or vid in entries:
            target = root/'eval/annotations/confirmed'/(vid + '.json')
            facts['import_provenance'] = {'export_sha256': sha(export_path),
                'review_page_id': PAGE_ID, 'exported_at': payload['exported_at'],
                'note': 'Importer copies explicit page confirmations only; it never promotes drafts.'}
            text = json.dumps(facts, ensure_ascii=False, indent=2) + '\n'
            writes[target] = text
            entries[vid] = {'path': target.relative_to(root).as_posix(),
                'sha256': hashlib.sha256(text.encode()).hexdigest(), 'video_id': vid,
                'video_sha256': videos[vid]['sha256'], 'origin': 'explicit_review_page_export'}
        counts['confirmed_events'] += len(facts['events'])
        counts['draft_events'] += sum(e['status'] == 'draft' for e in doc['events'])
        counts['confirmed_ranges'] += len(facts['reviewed_ranges'])
    require(bool(seen), 'EMPTY_REVIEW_EXPORT')
    # Validate everything before writing. Keep a local backup; failed writes
    # roll back, and a crash leaves a hash mismatch rather than silent scoring.
    backup_root = root/'eval/.local/import-backups'/dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    before = {p: p.read_bytes() if p.exists() else None for p in [*writes, registry_path]}
    backup_root.mkdir(parents=True)
    for path, content in before.items():
        if content is not None:
            target = backup_root/path.relative_to(root); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
    try:
        for path, text in writes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.tmp'); tmp.write_text(text); tmp.replace(path)
        write_registry(root, registry_path, registry['directory'], list(entries.values()))
        read_locked(root, registry_path)
    except Exception:
        for path, content in before.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--file', type=Path, required=True)
    p.add_argument('--root', type=Path, default=ROOT)
    a = p.parse_args()
    try:
        result = import_review(a.file, a.root)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (ValueError, OSError, KeyError) as exc:
        print('IMPORT_REFUSED: ' + str(exc), file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main())
