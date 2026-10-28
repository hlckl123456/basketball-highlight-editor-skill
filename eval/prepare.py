#!/usr/bin/env python3
"""Generate DRAFTS from existing BHE/features; never writes confirmed labels.
Uses an explicitly supplied existing runtime/model. No model downloads.
"""
import argparse
import gzip
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as A
try:
    from .schema import validate_catalog, validate_annotations, sha, require, DATASET
except ImportError:
    from schema import validate_catalog, validate_annotations, sha, require, DATASET
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'skills/basketball-highlight-editor/scripts/highlight.py'
spec = importlib.util.spec_from_file_location('highlight', SCRIPT)
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        value = value.replace(str(ROOT) + '/', '')
        value = re.sub(r'/Volumes/BHE/[^\s\"\']*runtime', '<BHE_RUNTIME>', value)
        value = re.sub(r'/Users/[^\s\"\']+', '<local-path>', value)
    return value


def write(path, value):
    h.write(path, clean(value))


def coverage(v):
    rows = []
    for start, end in v['evaluation_ranges']:
        count = max(1, math.ceil((end - start) / 15))
        for i in range(count):
            a = start + (end - start) * i / count
            b = min(end, a + 8)
            rows.append({'start': a, 'end': b, 'event_time': (a + b) / 2,
                         'reason': 'Coverage fallback review window; NOT a detected scoring event'})
    return rows


def prepare(v, runtime, refresh=False):
    vid = v['id']; source = ROOT/v['source_path']
    require(sha(source) == v['sha256'], 'SOURCE_HASH_MISMATCH')
    dest = ROOT/'eval/data/proposals'/vid
    draft_path = ROOT/'eval/annotations/drafts'/(vid + '.json')
    if dest.exists() and not refresh:
        print(vid + ': already prepared', flush=True); return
    if draft_path.exists():
        old = h.read(draft_path)
        require(all(e['status'] == 'draft' for e in old['events']), 'REFUSE_TO_OVERWRITE_HUMAN_LABELS')
    work = ROOT/'work/goal-1/projects'/vid
    if work.exists():
        shutil.rmtree(work)
    rights = ROOT/'eval/data/rights'/(vid + '.json')
    write(rights, {'source_url': v['source_url'], 'creator': v['author'],
          'license': v['license'], 'license_url': v['license_url'],
          'processing_basis': 'Explicit public license, user preauthorized local evaluation and permitted redistribution',
          'restrictions': 'Attribution and source license retained; no endorsement',
          'source_sha256': v['sha256']})
    h.cmd_init(A(project=work, video=source, rights=rights))
    failure, backend = None, 'bhe-public-source-cli'
    if vid == 'indiana':
        # Read-only historical evidence, identical source and candidate IDs.
        old = h.read(ROOT/'examples/indiana/project/project.json')
        _, p = h.load(work)
        p['candidates'] = [{**c, 'frames': [], 'observations': [], 'assignment': None}
                           for c in old['candidates']]
        p['detector'] = old['detector']; h.save(work, p, 'import_historical_bhe_candidates', 'read-only source fixture')
    else:
        try:
            require(runtime is not None, 'EXISTING_BHE_RUNTIME_NOT_SUPPLIED')
            h.cmd_detect(A(project=work, backend='bhe', runtime=runtime,
                           python=sys.executable, model=None, roi=None, fps=3,
                           device='cpu', before=3, after=3, timeout=300))
        except Exception as exc:
            failure = str(exc)
    _, p = h.load(work)
    detected = [c for c in p['candidates'] if c.get('event_time') is not None and
                any(a <= c['event_time'] <= b for a, b in v['evaluation_ranges'])]
    prediction_events = []
    historical = h.read(ROOT/'examples/indiana/project/project.json') if vid == 'indiana' else None
    for c in detected:
        assignments = []
        if historical:
            selected = historical['selection']
            group = ('high' if c['id'] in selected['high_confidence'] else
                     'uncertain' if c['id'] in selected['uncertain'] else 'excluded')
            assignments = [{'target_player_id': 'p1', 'group': group,
                            'assigned_player_id': 'p1' if group == 'high' else None}]
        prediction_events.append({'id': c['id'], 'candidate_id': c['id'], 'kind': 'detected_event',
                                  'time': c['event_time'], 'player_assignments': assignments})
    fallback = not detected
    if fallback:
        # Failed/zero detections are retained as zero predictions, not relabeled
        # as a successful detector when windows are added for human review.
        p['candidates'] = h.stamp_candidates(coverage(v), v['duration'])
        p['detector'] = {'backend': 'coverage-for-review', 'failure': clean(failure),
                         'detected_events': 0}
        h.save(work, p, 'review_coverage_only', 'not detector predictions')
    else:
        p['candidates'] = detected
        h.write(work/'project.json', p)
    try:
        h.cmd_features(A(project=work, interval=3, refresh=False, no_ocr=True))
        feature_failure = None
    except Exception as exc:
        feature_failure = str(exc)
    _, p = h.load(work)
    dest.mkdir(parents=True, exist_ok=True)
    write(dest/'processing.json', {'video_id': vid, 'source_sha256': v['sha256'],
          'detector': p['detector'], 'detector_failure': failure,
          'feature_failure': feature_failure, 'feature_extractor': p.get('feature_extractor'),
          'predicted_events': len(prediction_events), 'review_windows': len(p['candidates']),
          'all_annotations_are_draft': True, 'holdout_not_scored': v['split'] == 'holdout'})
    for name in ['detections.json', 'events.json']:
        f = work/'detection'/name
        if f.exists():
            raw = clean(h.read(f))
            with (dest/(name + '.gz')).open('wb') as out:
                with gzip.GzipFile(filename='', fileobj=out, mode='wb', mtime=0) as z:
                    z.write(json.dumps(raw, ensure_ascii=False, separators=(',', ':')).encode())
    if (work/'feature-summary.json').exists():
        write(dest/'feature-summary.json', h.read(work/'feature-summary.json'))
    pictures = ROOT/'eval/data/previews'/vid; pictures.mkdir(parents=True, exist_ok=True)
    refs, colors = [], {}
    for c in p['candidates']:
        for f in c.get('frames', [])[:1]:
            target = pictures/Path(f['path']).name
            shutil.copy2(work/f['path'], target)
            refs.append({'time': f['time'], 'path': target.relative_to(ROOT).as_posix()})
        for o in c.get('observations', []):
            color = o['color']['dominant']; colors[color] = colors.get(color, 0) + 1
    players = [{'id': 'p1', 'appearance_description': '紫色球衣2号，白色短袖、裸露膝部、浅色鞋；既有用户选人',
                'reference': None}] if historical else []
    for i, (color, count) in enumerate(sorted(colors.items(), key=lambda x: -x[1])[:3]):
        if historical:
            break
        players.append({'id': 'p' + str(i + 1),
                        'appearance_description': '自动服饰区域提议：' + color + '；待你确认是否为球员并改写描述',
                        'reference': refs[0]['path'] if refs else None,
                        'proposal_only': True})
    if not players:
        players = [{'id': 'p1', 'appearance_description': '待人工定义的球员；自动特征不足', 'proposal_only': True}]
    events = []
    for c in p['candidates']:
        t = c.get('event_time')
        if t is None:
            t = (c['start'] + c['end']) / 2
        events.append({'id': c['id'], 'time': t, 'is_score': None, 'scorer_id': None,
                       'ball_handler_id': None, 'visible_player_ids': None, 'visibility_complete': False,
                       'status': 'draft', 'deleted': False, 'confirmed_fields': [], 'confirmation': None,
                       'origin': {'kind': 'coverage_fallback' if fallback else 'bhe_candidate',
                                  'candidate_id': c['id'], 'detector_failure': clean(failure)},
                       'clip_start': max(0, t - 3), 'clip_end': min(v['duration'], t + 3),
                       'feature_references': [f for f in refs if c['start'] <= f['time'] <= c['end']],
                       'notes': '自动草稿，进球、得分者、持球者、可见球员均未确认'})
    doc = {'schema_version': 1, 'document_type': 'basketball_annotations', 'dataset_id': DATASET,
           'video_id': vid, 'video_sha256': v['sha256'], 'duration': v['duration'],
           'target_player_ids': ['p1'] if historical else [], 'players': players,
           'events': events, 'reviewed_ranges': [], 'generated_by': 'BHE candidates + features; drafts only'}
    validate_annotations(doc, v, require_all_draft=True)
    write(draft_path, doc)
    write(ROOT/'eval/predictions'/(vid + '.json'),
          {'schema_version': 1, 'document_type': 'basketball_predictions', 'video_id': vid,
           'video_sha256': v['sha256'], 'provenance': {'method': backend, 'detector_failure': failure,
            'person_policy': 'No new player attribution before user calibration; historical Indiana groups imported unchanged'},
           'events': prediction_events})
    media = ROOT/v['review_media_path']; media.parent.mkdir(parents=True, exist_ok=True)
    if not media.exists():
        h.run(['ffmpeg', '-v', 'error', '-i', source, '-map', '0:v:0', '-map', '0:a:0?',
               '-vf', 'scale=w=min(960\\,iw):h=min(720\\,ih):force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1',
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '24', '-c:a', 'aac',
               '-movflags', '+faststart', '-y', media], timeout=300)
    print(f'{vid}: {len(prediction_events)} detections, {len(events)} draft events, {len(refs)} feature frames', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path)
    p.add_argument('--video', action='append')
    p.add_argument('--refresh', action='store_true')
    a = p.parse_args()
    catalog = validate_catalog(h.read(ROOT/'eval/data/catalog.json'))
    for video in catalog['videos']:
        if not a.video or video['id'] in a.video:
            prepare(video, a.runtime, a.refresh)


if __name__ == '__main__':
    main()
