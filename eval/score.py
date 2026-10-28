#!/usr/bin/env python3
"""Score human-confirmed labels only. No writes to annotations or hash locks."""
import argparse
import json
import sys
from pathlib import Path
try:
    from .schema import validate_catalog, validate_annotations, validate_predictions, require, sha, ValidationError
    from .locking import read_locked, safe_path
except ImportError:
    from schema import validate_catalog, validate_annotations, validate_predictions, require, sha, ValidationError
    from locking import read_locked, safe_path

ROOT = Path(__file__).resolve().parents[1]


def match_times(truth, predictions, tolerance=1.0):
    """Maximum cardinality, then minimum total absolute error, in 1-D time.

    Ordered absolute-distance matching has an order-preserving optimum. Dynamic
    programming avoids the common nearest-first greedy undercount.
    Returns original list index pairs.
    """
    aa = sorted(enumerate(truth), key=lambda x: x[1]['time'])
    bb = sorted(enumerate(predictions), key=lambda x: x[1]['time'])
    n, m = len(aa), len(bb)
    dp = [[(0, 0.0)] * (m + 1) for _ in range(n + 1)]
    parent = {}
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            choices = [(dp[i - 1][j], 'a'), (dp[i][j - 1], 'b')]
            error = abs(aa[i - 1][1]['time'] - bb[j - 1][1]['time'])
            if error <= tolerance + 1e-9:
                count, cost = dp[i - 1][j - 1]
                choices.append(((count + 1, cost - error), 'match'))
            dp[i][j], parent[i, j] = max(choices, key=lambda x: x[0])
    i, j, pairs = n, m, []
    while i and j:
        action = parent[i, j]
        if action == 'match':
            pairs.append((aa[i - 1][0], bb[j - 1][0])); i -= 1; j -= 1
        elif action == 'a':
            i -= 1
        else:
            j -= 1
    return list(reversed(pairs))


def membership(event, target, role):
    fields = set(event.get('confirmed_fields', []))
    if role == 'visible':
        if 'visible_player_ids' not in fields or event.get('visible_player_ids') is None:
            return None
        if target in event['visible_player_ids']:
            return True
        return False if event.get('visibility_complete') else None
    key = 'scorer_id' if role == 'scorer' else 'ball_handler_id'
    if key not in fields or event.get(key) is None:
        return None
    return event[key] == target


def empty_counts():
    return dict(tp=0, fp=0, fn=0, confirmed_positive_events=0,
                confirmed_negative_events=0, ignored_unreviewed_predictions=0,
                ignored_unknown_predictions=0, high_total_predictions=0,
                high_evaluable_predictions=0, high_correct=0,
                target_events=0, target_retrieved=0, target_high=0)


def score_video(doc, prediction, role='visible', tolerance=1.0):
    confirmed = [e for e in doc['events'] if e['status'] == 'confirmed']
    detected = prediction.get('events', [])
    positive = [e for e in confirmed if e.get('is_score') is True and
                {'is_score', 'time'} <= set(e['confirmed_fields'])]
    negative = [e for e in confirmed if e.get('is_score') is False and
                {'is_score', 'time'} <= set(e['confirmed_fields'])]
    unknown = [e for e in confirmed if e.get('is_score') is None and
               'time' in e['confirmed_fields']]
    ranges = [r for r in doc.get('reviewed_ranges', []) if r['status'] == 'confirmed']
    matches = match_times(positive, detected, tolerance)
    used = {j for i, j in matches}
    c = empty_counts()
    c.update(tp=len(matches), fn=len(positive) - len(matches),
             confirmed_positive_events=len(positive), confirmed_negative_events=len(negative))
    detail = []
    for j, p in enumerate(detected):
        if j in used:
            status = 'tp'
        elif any(abs(p['time'] - e['time']) <= tolerance for e in unknown):
            c['ignored_unknown_predictions'] += 1; status = 'ignored_unknown_label'
        elif (any(r['start'] <= p['time'] <= r['end'] for r in ranges) or
              any(abs(p['time'] - e['time']) <= tolerance for e in negative)):
            c['fp'] += 1; status = 'fp'
        else:
            c['ignored_unreviewed_predictions'] += 1; status = 'ignored_unreviewed'
        detail.append({'prediction_id': p['id'], 'status': status})
    # Identity is assessed independently of made-shot truth. Historical clip
    # confirmation supports candidate-ID correspondence, not exact shot times.
    available = [e for e in confirmed if 'time' in e['confirmed_fields']]
    identity_pairs = match_times(available, detected, tolerance)
    identity = {available[i]['id']: detected[j] for i, j in identity_pairs}
    for e in confirmed:
        if (e.get('confirmation') or {}).get('source') == 'legacy_indiana_user_review':
            matches_id = [p for p in detected if p.get('candidate_id') == e['legacy_candidate_id']]
            require(len(matches_id) <= 1, 'AMBIGUOUS_LEGACY_CANDIDATE_PREDICTION')
            if matches_id:
                identity[e['id']] = matches_id[0]
    targets = doc.get('target_player_ids', [])
    for p in detected:
        c['high_total_predictions'] += sum(a['target_player_id'] in targets and a['group'] == 'high'
                                           for a in p.get('player_assignments', []))
    identity_detail = []
    for e in confirmed:
        for target in targets:
            actual = membership(e, target, role)
            if actual is None:
                continue
            p = identity.get(e['id'])
            assignment = next((a for a in (p or {}).get('player_assignments', [])
                               if a['target_player_id'] == target), None)
            group = assignment['group'] if assignment else 'missing'
            correctly_named = assignment and assignment.get('assigned_player_id') == target
            if actual:
                c['target_events'] += 1
                if group in ('high', 'uncertain') and (group == 'uncertain' or correctly_named):
                    c['target_retrieved'] += 1
                if group == 'high' and correctly_named:
                    c['target_high'] += 1
            if group == 'high':
                c['high_evaluable_predictions'] += 1
                c['high_correct'] += int(actual and correctly_named)
            identity_detail.append({'event_id': e['id'], 'target_player_id': target,
                                    'actual_target_presence_or_role': actual, 'predicted_group': group})
    return {'counts': c, 'detection_details': detail, 'identity_details': identity_detail,
            'confirmed_events': len(confirmed), 'draft_events_ignored': len(doc['events']) - len(confirmed),
            'reviewed_seconds': union_seconds(ranges)}


def union_seconds(ranges):
    merged = []
    for r in sorted(ranges, key=lambda r: r['start']):
        if merged and r['start'] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], r['end'])
        else:
            merged.append([r['start'], r['end']])
    return sum(b - a for a, b in merged)


def ratios(c):
    def ratio(a, b):
        return a / b if b else None
    precision = ratio(c['tp'], c['tp'] + c['fp'])
    recall = ratio(c['tp'], c['confirmed_positive_events'])
    f1 = (2 * precision * recall / (precision + recall) if precision + recall else 0.0) \
         if precision is not None and recall is not None else None
    return {'event_precision': precision, 'event_recall': recall, 'event_f1': f1,
            'high_assignment_accuracy': ratio(c['high_correct'], c['high_evaluable_predictions']),
            'target_event_retrieval_high_or_uncertain': ratio(c['target_retrieved'], c['target_events']),
            'high_confidence_coverage': ratio(c['target_high'], c['target_events']),
            'unreviewed_high_predictions': c['high_total_predictions'] - c['high_evaluable_predictions']}


def evaluate_repository(root, catalog_path, registry_path, prediction_dir,
                        include_holdout=False, video_ids=None, role='visible', tolerance=1.0):
    require(role in ('visible', 'scorer', 'handler'), 'INVALID_PLAYER_ROLE')
    require(tolerance == 1.0, 'BENCHMARK_TOLERANCE_IS_FIXED_AT_ONE_SECOND')
    root = Path(root).resolve()
    catalog = validate_catalog(json.loads(Path(catalog_path).read_text()))
    byid = {v['id']: v for v in catalog['videos']}
    registry, locked = read_locked(root, registry_path)  # Validate every hash, even withheld labels.
    if video_ids:
        require(set(video_ids) <= set(byid), 'UNKNOWN_REQUESTED_VIDEO')
        require(include_holdout or all(byid[v]['split'] != 'holdout' for v in video_ids),
                'HOLDOUT_REQUIRES_EXPLICIT_INCLUDE_HOLDOUT')
    result = {'schema_version': 1, 'dataset_id': catalog['dataset_id'],
              'catalog_sha256': sha(catalog_path), 'confirmed_registry_sha256': sha(registry_path),
              'tolerance_seconds': tolerance, 'player_role': role,
              'scope': 'Confirmed facts only; FP requires explicitly reviewed interval or confirmed negative. Unknown fields are excluded.',
              'holdout_evaluated': include_holdout, 'input_hashes': {}, 'splits': {}}
    for split in ('development', 'holdout'):
        if split == 'holdout' and not include_holdout:
            result['splits'][split] = {'status': 'withheld', 'reason': 'Use --include-holdout explicitly.'}
            continue
        counts, videos, seconds = empty_counts(), [], 0.0
        for item, path in locked:
            vid = item['video_id']
            require(vid in byid, 'LOCK_REFERS_TO_UNKNOWN_VIDEO')
            v = byid[vid]
            if v['split'] != split or (video_ids and vid not in video_ids):
                continue
            require(item.get('video_sha256') == v['sha256'], 'LOCK_SOURCE_HASH_MISMATCH')
            doc = validate_annotations(json.loads(path.read_text()), v, allow_legacy=vid == 'indiana')
            source = safe_path(root, v['source_path'])
            require(source.is_file() and sha(source) == v['sha256'], 'SOURCE_MEDIA_HASH_MISMATCH: ' + vid)
            for event in doc['events']:
                conf = event.get('confirmation') or {}
                if conf.get('source') == 'legacy_indiana_user_review':
                    evidence = safe_path(root, conf['evidence_path'])
                    require(sha(evidence) == conf['evidence_sha256'], 'LEGACY_USER_EVIDENCE_CHANGED')
            pred_path = Path(prediction_dir) / (vid + '.json')
            require(pred_path.is_file(), 'PREDICTIONS_MISSING: ' + vid)
            pred = validate_predictions(json.loads(pred_path.read_text()), v)
            scored = score_video(doc, pred, role, tolerance)
            for key in counts:
                counts[key] += scored['counts'][key]
            seconds += scored['reviewed_seconds']
            videos.append({'video_id': vid, **scored, 'metrics': ratios(scored['counts'])})
            result['input_hashes'][vid] = {'annotations': item['sha256'], 'predictions': sha(pred_path),
                                          'source': v['sha256']}
        status = 'scored' if videos else 'no_confirmed_annotations'
        result['splits'][split] = {'status': status, 'counts': counts, 'metrics': ratios(counts),
                                  'reviewed_seconds': seconds, 'videos': videos}
        if not counts['confirmed_positive_events']:
            result['splits'][split]['event_metric_limitation'] = 'No human-confirmed made-shot events; recall/F1 cannot be estimated.'
    return result


def summary(result):
    def fmt(x):
        return 'N/A' if x is None else f'{x:.3f}'
    parts = []
    for split, data in result['splits'].items():
        if data['status'] == 'withheld':
            parts.append('holdout=WITHHELD'); continue
        m = data['metrics']
        parts.append(f"{split}: P/R/F1={fmt(m['event_precision'])}/{fmt(m['event_recall'])}/{fmt(m['event_f1'])} "
                     f"player_acc/retrieval/high_cov={fmt(m['high_assignment_accuracy'])}/"
                     f"{fmt(m['target_event_retrieval_high_or_uncertain'])}/{fmt(m['high_confidence_coverage'])}")
    return ' | '.join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--catalog', type=Path)
    p.add_argument('--locks', type=Path)
    p.add_argument('--predictions', type=Path)
    p.add_argument('--include-holdout', action='store_true')
    p.add_argument('--video', action='append', dest='videos')
    p.add_argument('--player-role', choices=['visible', 'scorer', 'handler'], default='visible')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        result = evaluate_repository(a.root, a.catalog or a.root/'eval/data/catalog.json',
                    a.locks or a.root/'eval/annotations/confirmed.lock.json',
                    a.predictions or a.root/'eval/predictions', a.include_holdout, a.videos, a.player_role)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        print(summary(result))
    except (ValidationError, KeyError, ValueError, OSError) as exc:
        print('EVAL_REFUSED: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
