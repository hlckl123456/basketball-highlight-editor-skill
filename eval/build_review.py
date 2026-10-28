#!/usr/bin/env python3
"""Build one offline HTML application; local videos remain regular files."""
import argparse
import copy
import hashlib
import json
import os
import urllib.parse
from pathlib import Path
try:
    from .schema import validate_catalog, validate_annotations, sha, require
    from .locking import read_locked
except ImportError:
    from schema import validate_catalog, validate_annotations, sha, require
    from locking import read_locked
ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT, output=None, synthetic=False):
    root = Path(root).resolve(); output = Path(output or root/'eval/review.html').resolve()
    catalog_path = root/'eval/data/catalog.json'
    catalog = validate_catalog(json.loads(catalog_path.read_text()))
    read_locked(root, root/'eval/annotations/confirmed.lock.json')
    annotations, paths = [], {}
    for video in catalog['videos']:
        if video.get('review_media_sha256'):
            require(sha(root/video['review_media_path']) == video['review_media_sha256'], 'REVIEW_MEDIA_HASH_MISMATCH')
        vid = video['id']; state = root/'eval/annotations/review-state'/(vid+'.json')
        draft = root/'eval/annotations/drafts'/(vid+'.json')
        confirmed = root/'eval/annotations/confirmed'/(vid+'.json')
        doc = json.loads((state if state.exists() else draft).read_text())
        if not state.exists() and confirmed.exists():
            legacy = json.loads(confirmed.read_text())
            known = {e['id']: e for e in legacy['events']}
            doc['events'] = [copy.deepcopy(known.get(e['id'], e)) for e in doc['events']]
            for e in legacy['events']:
                if e['id'] not in {x['id'] for x in doc['events']}:
                    doc['events'].append(copy.deepcopy(e))
            pids = {p['id']: p for p in doc['players']}
            pids.update({p['id']: p for p in legacy['players']})
            doc['players'] = list(pids.values())
            doc['target_player_ids'] = legacy.get('target_player_ids', doc.get('target_player_ids', []))
            doc['reviewed_ranges'] = legacy.get('reviewed_ranges', [])
        validate_annotations(doc, video, allow_legacy=vid=='indiana')
        annotations.append(doc)
        for key in ('source_path', 'review_media_path'):
            if video.get(key):
                paths[video[key]] = urllib.parse.quote(os.path.relpath(root/video[key], output.parent), safe='/')
        for event in doc['events']:
            for frame in event.get('feature_references', []):
                paths[frame['path']] = urllib.parse.quote(os.path.relpath(root/frame['path'], output.parent), safe='/')
    boot = {'catalog': catalog, 'catalog_sha256': sha(catalog_path), 'annotations': annotations,
            'paths': paths, 'synthetic': synthetic,
            'data_revision': hashlib.sha256(json.dumps(annotations, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    template = (ROOT/'eval/review.template.html').read_text()
    encoded = json.dumps(boot, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    encoded = encoded.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace('__BOOT_DATA__', encoded))
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path)
    a = p.parse_args(); print(build(output=a.output))


if __name__ == '__main__':
    main()
