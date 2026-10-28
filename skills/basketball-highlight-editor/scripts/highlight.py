#!/usr/bin/env python3
"""Local basketball review projects. No network, package install or GUI internals.

Base commands need Python 3.10+ and ffmpeg/ffprobe. features needs numpy/OpenCV
(the explicitly supplied BHE Python runtime can provide both).
"""
import argparse
import csv
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

VERSION = '1.0.1'


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(cmd, timeout=180, env=None):
    r = subprocess.run([str(v) for v in cmd], capture_output=True, text=True,
                       timeout=timeout, env=env)
    if r.returncode:
        raise ValueError('COMMAND_FAILED: ' + repr(cmd) + '\n' + r.stderr[-4000:])
    return r.stdout


def probe(path):
    d = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                        '-of', 'json', path]))
    v = next(s for s in d['streams'] if s['codec_type'] == 'video')
    dur = float(d['format']['duration'])
    if not math.isfinite(dur) or dur <= 0:
        raise ValueError('INVALID_DURATION')
    return {'duration': dur, 'width': v['width'], 'height': v['height'],
            'fps': v['r_frame_rate'], 'has_audio': any(s['codec_type'] == 'audio' for s in d['streams'])}


def source_path(root, p):
    path = Path(p['source']['path'])
    return (path if path.is_absolute() else Path(root) / path).resolve()


def load(project):
    root = Path(project).resolve()
    p = read(root / 'project.json')
    if p['schema_version'] != 1:
        raise ValueError('UNSUPPORTED_PROJECT_SCHEMA')
    source = source_path(root, p)
    if not source.is_file():
        raise ValueError('SOURCE_MISSING: relink the source before continuing')
    if sha(source) != p['source']['sha256']:
        raise ValueError('SOURCE_CHANGED')
    return root, p


def save(root, p, action, detail):
    p['revision'] += 1
    p['updated_at'] = now()
    p['history'].append({'at': now(), 'action': action, 'detail': detail, 'revision': p['revision']})
    write(root / 'project.json', p)
    report(root, p)


def invalidate(p):
    p['confirmation'] = None
    p['selection'] = None
    p['state'] = 'awaiting_player' if p.get('players') else 'candidates_ready'


def stamp_candidates(raw, duration):
    out = []
    for i, r in enumerate(raw):
        a, b = float(r['start']), float(r['end'])
        if (not all(math.isfinite(x) for x in (a, b)) or
                not 0 <= a < min(b, duration) or b > duration + .02):
            raise ValueError('INVALID_CANDIDATE_RANGE')
        out.append({'id': 'c%04d' % (i + 1), 'start': round(a, 4),
                    'end': round(min(b, duration), 4), 'event_time': r.get('event_time'),
                    'reason': r.get('reason', 'imported candidate'), 'event_confirmed': False,
                    'observations': [], 'labels': [], 'assignment': None})
    return out


def cmd_init(a):
    root = Path(a.project).resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError('PROJECT_NOT_EMPTY')
    source = Path(a.video).resolve(strict=True)
    rights = read(a.rights)
    for key in ('source_url', 'license', 'creator', 'processing_basis', 'restrictions'):
        if not rights.get(key):
            raise ValueError('RIGHTS_FIELD_REQUIRED: ' + key)
    p = {'schema_version': 1, 'tool_version': VERSION, 'revision': 0,
         'state': 'initialized', 'created_at': now(), 'source': {
             'path': str(source), 'sha256': sha(source), **probe(source), 'rights': rights},
         'detector': None, 'candidates': [], 'players': [], 'selection': None,
         'confirmation': None, 'versions': [], 'history': []}
    save(root, p, 'init', 'local source reference; no upload')


def cmd_relink(a):
    root=Path(a.project).resolve()
    p=read(root/'project.json')
    source=Path(a.video).resolve(strict=True)
    if sha(source)!=p['source']['sha256']:
        raise ValueError('RELINK_HASH_MISMATCH')
    p['source']['path']=str(source)
    save(root,p,'relink_same_source',str(source))


def cmd_detect(a):
    root, p = load(a.project)
    if p['candidates']:
        raise ValueError('CANDIDATES_EXIST: use a new project to compare a detector')
    d = p['source']['duration']
    if a.backend == 'bhe':
        runtime = Path(a.runtime).resolve(strict=True)
        python = runtime / 'python/bin/python3.11'
        if a.python:
            python = Path(a.python).resolve(strict=True)
        scan = runtime / 'scripts/scan_video.py'
        gen = runtime / 'scripts/generate_candidates.py'
        model = Path(a.model).resolve() if a.model else runtime / 'models/bball_model.static.onnx'
        if not model.is_file():
            raise ValueError('MODEL_NOT_FOUND: supply your own authorized model with --model; no automatic download')
        roi = a.roi or [0, 0, p['source']['width'], p['source']['height']]
        if not (0 <= roi[0] < roi[2] <= p['source']['width'] and
                0 <= roi[1] < roi[3] <= p['source']['height']):
            raise ValueError('ROI_OUT_OF_BOUNDS')
        rawdir = root / 'detection'
        rawdir.mkdir(exist_ok=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', YOLO_CONFIG_DIR=str(rawdir / 'yolo'),
                   YOLO_AUTOINSTALL='false', OMP_NUM_THREADS='2')
        commands = [[python, scan, '--video', source_path(root,p), '--model', model,
                     '--roi', *roi, '--sample-fps', a.fps, '--device', a.device,
                     '--batch', 1, '--scale', 1, '--output', rawdir / 'detections.json'],
                    [python, gen, '--detections', rawdir / 'detections.json',
                     '--output', rawdir / 'events.json']]
        logs = []
        try:
            for cmd in commands:
                logs.append(run(cmd, timeout=a.timeout, env=env))
            data = read(rawdir / 'events.json')
        except Exception as e:
            (rawdir / 'failure.txt').write_text(str(e) + '\n' + '\n'.join(logs))
            raise
        (rawdir / 'run.log').write_text('\n'.join(logs))
        events = data.get('candidates', [])
        raw = [{'start': max(0., float(e['time']) - a.before),
                'end': min(d, float(e['time']) + a.after),
                'event_time': float(e['time']), 'reason': 'BHE ball/rim crossing candidate'}
               for e in events]
        p['detector'] = {'backend': 'bhe-public-source-cli', 'roi': roi, 'fps': a.fps,
                         'device_requested': a.device,
                         'runtime': str(runtime), 'commands': [[str(x) for x in c] for c in commands],
                         'hashes': {(str(x.relative_to(runtime)) if x.is_relative_to(runtime) else 'external-model/'+x.name): sha(x) for x in (scan, gen, model)},
                         'limitations': 'Likely crossings only; no made-shot or player identity guarantee.'}
    else:
        # A deterministic motion triage, not a basketball or shot recognizer.
        rawdir = root / 'detection'
        rawdir.mkdir(exist_ok=True)
        tmp = rawdir / 'gray.raw'
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', source_path(root,p),
             '-vf', 'fps=2,scale=96:54', '-pix_fmt', 'gray', '-f', 'rawvideo', '-y', tmp], timeout=a.timeout)
        buf = tmp.read_bytes()
        n = 96 * 54
        scores = [sum(abs(x-y) for x, y in zip(buf[i-n:i], buf[i:i+n])) / n
                  for i in range(n, len(buf)-n+1, n)]
        write(rawdir / 'motion.json', {'fps': 2, 'mean_abs_difference': scores})
        tmp.unlink()
        raw = []
        # Keep bounded overlapping coverage windows so low motion is not lost.
        for i in range(math.ceil(d / 6)):
            start, end = i * 6., min(d, i * 6 + 8.)
            part = scores[int(start*2):max(int(start*2)+1, int(end*2))]
            raw.append({'start': start, 'end': end,
                        'reason': 'motion triage / coverage; mean difference %.3f' % (sum(part)/max(1,len(part)))})
        p['detector'] = {'backend': 'motion-coverage', 'fps': 2,
                         'limitations': 'Coverage windows, NOT detected possessions or scoring events. Review all windows.'}
    p['candidates'] = stamp_candidates(raw, d)
    p['state'] = 'candidates_ready'
    save(root, p, 'detect', {'count': len(raw), 'backend': p['detector']['backend']})


def cmd_import(a):
    root, p = load(a.project)
    if p['candidates']:
        raise ValueError('CANDIDATES_EXIST')
    data = read(a.file)
    p['candidates'] = stamp_candidates(data['candidates'], p['source']['duration'])
    p['detector'] = {'backend': 'portable-manifest', 'provenance': data['provenance']}
    p['state'] = 'candidates_ready'
    save(root, p, 'import_candidates', sha(a.file))


def cmd_add(a):
    root, p = load(a.project)
    item = stamp_candidates([{'start': a.start, 'end': a.end, 'reason': a.reason}], p['source']['duration'])[0]
    item['id'] = 'c%04d' % (len(p['candidates'])+1)
    item['origin'] = 'manual_addition'
    p['candidates'].append(item)
    invalidate(p)
    save(root, p, 'manual_candidate', item['id'])


def color_summary(crop):
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]
    masks = {'black': v < 60, 'white': (s < 55) & (v > 155),
             'gray': (s < 55) & (v >= 60) & (v <= 155),
             'red': ((h < 12) | (h > 170)) & (s >= 55) & (v >= 60),
             'orange': (h >= 12) & (h < 25) & (s >= 55) & (v >= 60),
             'yellow': (h >= 25) & (h < 38) & (s >= 55) & (v >= 60),
             'green': (h >= 38) & (h < 88) & (s >= 55) & (v >= 60),
             'blue': (h >= 88) & (h < 135) & (s >= 55) & (v >= 60),
             'purple': (h >= 135) & (h <= 170) & (s >= 55) & (v >= 60)}
    fractions = {k: round(float(np.mean(m)), 3) for k, m in masks.items()}
    return {'dominant': max(fractions, key=fractions.get), 'fractions': fractions}


def ocr(crop_path):
    if not shutil.which('tesseract'):
        return []
    out = run(['tesseract', crop_path, 'stdout', '--psm', '11', 'tsv'], timeout=20)
    hits = []
    for row in csv.DictReader(out.splitlines(), delimiter='\t'):
        text = row.get('text', '').strip()
        conf = float(row.get('conf', -1))
        if re.fullmatch(r'\d{1,2}', text) and conf >= 35:
            hits.append({'text': text, 'confidence': conf, 'verified': False})
    return hits


def cmd_features(a):
    import cv2
    import numpy as np
    root, p = load(a.project)
    if not p['candidates']:
        raise ValueError('NO_CANDIDATES: verify ROI or use explicit coverage fallback')
    cap = cv2.VideoCapture(str(source_path(root,p)))
    if not cap.isOpened():
        raise ValueError('VIDEO_OPEN_FAILED')
    hog = cv2.HOGDescriptor() if hasattr(cv2, 'HOGDescriptor') else None
    if hog is not None:
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    frames = root / 'frames'
    crops = root / 'crops'
    frames.mkdir(exist_ok=True)
    crops.mkdir(exist_ok=True)
    for c in p['candidates']:
        if c.get('frames') and not a.refresh:
            continue
        c['observations'] = []
        c['frames'] = []
        c['assignment'] = None
        # Samples are for triage; no re-identification claim across frames.
        count = max(2, math.ceil((c['end']-c['start']) / a.interval))
        for k in range(count):
            t = c['start'] + (c['end']-c['start']) * (k+.5) / count
            cap.set(cv2.CAP_PROP_POS_MSEC, t*1000)
            ok, frame = cap.read()
            if not ok:
                raise ValueError('FRAME_DECODE_FAILED at %.3f' % t)
            name = '%s_f%03d.jpg' % (c['id'], k)
            cv2.imwrite(str(frames/name), frame)
            c['frames'].append({'path': 'frames/'+name, 'time': round(t,4)})
            scale = min(1., 960 / frame.shape[1])
            small = cv2.resize(frame, None, fx=scale, fy=scale)
            method = 'OpenCV HOG' if hog is not None else 'uniform-color-region; NOT a verified person'
            if hog is not None:
                boxes, weights = hog.detectMultiScale(small, winStride=(8,8), padding=(8,8), scale=1.05)
            else:
                hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
                hue,sat,val = hsv[:,:,0],hsv[:,:,1],hsv[:,:,2]
                masks = [((hue>88)&(hue<172)&(sat>70)&(val>50)),
                         ((sat<55)&(val>170)), (((hue<15)|(hue>172))&(sat>90)&(val>75))]
                boxes, weights = [], []
                for mask in masks:
                    mask[:int(small.shape[0]*.25)] = False
                    mask = cv2.morphologyEx(mask.astype(np.uint8)*255, cv2.MORPH_CLOSE, np.ones((3,3),np.uint8))
                    _,_,stats,_ = cv2.connectedComponentsWithStats(mask)
                    for x,y,w,h,area in stats[1:]:
                        if 12<=w<=180 and 16<=h<=240 and 180<=area<=20000 and .15<w/h<3:
                            boxes.append((x,y,w,h));weights.append(float(area/(w*h)))
            # These proposals include spectators, signs, false positives and misses.
            for j, (box, weight) in enumerate(zip(boxes, weights)):
                x,y,w,h = [round(int(v)/scale) for v in box]
                x2, y2 = min(frame.shape[1], x+w), min(frame.shape[0], y+h)
                torso = (frame[y+int(h*.18):y+int(h*.58), x+int(w*.15):min(x2,x+int(w*.85))]
                         if hog is not None else frame[y:y2,x:x2])
                if not torso.size:
                    continue
                oid = '%s_f%03d_o%02d' % (c['id'], k, j)
                crop_path = crops / (oid+'.jpg')
                cv2.imwrite(str(crop_path), torso)
                c['observations'].append({'id': oid, 'time': round(t,4),
                    'bbox_xyxy': [x,y,x2,y2], 'crop': 'crops/'+crop_path.name,
                    'frame': 'frames/'+name, 'proposal_method': method,
                    'proposal_score': float(weight), 'person_verified': False,
                    'color': color_summary(torso), 'number_ocr': [] if a.no_ocr else ocr(crop_path),
                    'player_id': None, 'evidence': None})
    cap.release()
    p['feature_extractor'] = {'backend': 'opencv-'+('hog' if hog is not None else 'uniform-color-proposals')+'-hsv-tesseract', 'opencv': cv2.__version__,
                             'interval': a.interval, 'ocr_enabled':not a.no_ocr,
                             'number_policy': 'OCR hints only; require visual verification'}
    if a.refresh:
        p['players'] = []
    invalidate(p)
    save(root, p, 'features', {'observations': sum(len(c['observations']) for c in p['candidates'])})
    write(root/'feature-summary.json', {'extractor':p['feature_extractor'],
          'candidates':[{'id':c['id'], 'observations':len(c['observations']),
              'color_counts':{color:sum(o['color']['dominant']==color for o in c['observations'])
                              for color in sorted({o['color']['dominant'] for o in c['observations']})},
              'number_hints':[{'observation_id':o['id'],'time':o['time'],'crop':o['crop'],**n}
                              for o in c['observations'] for n in o['number_ocr']]}
                        for c in p['candidates']], 'identity_verified':False})


def cmd_annotate(a):
    root, p = load(a.project)
    data = read(a.file)
    reviewer = data['reviewer']
    if reviewer['kind'] not in ('user', 'test_operator', 'agent_visual_review') or not reviewer.get('name'):
        raise ValueError('INVALID_REVIEWER')
    players = data['players']
    ids = [x['id'] for x in players]
    if len(ids) != len(set(ids)) or not all(re.fullmatch('[A-Za-z0-9_-]+', x) for x in ids):
        raise ValueError('INVALID_PLAYER_IDS')
    for player in players:
        if not player.get('description') or not player.get('reference'):
            raise ValueError('PLAYER_NEEDS_DESCRIPTION_AND_REFERENCE')
    candidates = {c['id']: c for c in p['candidates']}
    for item in data['assignments']:
        c = candidates[item['candidate_id']]
        if item['player_id'] is not None and item['player_id'] not in ids:
            raise ValueError('UNKNOWN_PLAYER')
        if item['certainty'] not in ('high', 'uncertain', 'other') or not item.get('reason'):
            raise ValueError('INVALID_ASSIGNMENT')
        evidence = item.get('evidence', [])
        if item['certainty'] == 'high':
            # Require traceable frame evidence and a number or stable sample match;
            # jersey color alone cannot identify teammates.
            kinds = {e.get('kind') for e in evidence}
            if not kinds.intersection({'number_visible', 'confirmed_sample_match'}):
                raise ValueError('HIGH_REQUIRES_NUMBER_OR_CONFIRMED_SAMPLE')
            if 'number_visible' not in kinds:
                sample_ids = {x['id'] for x in p.get('samples',[]) if x['player_id']==item['player_id']}
                if not any(e.get('sample_id') in sample_ids for e in evidence if e.get('kind')=='confirmed_sample_match'):
                    raise ValueError('HIGH_SAMPLE_MATCH_REQUIRES_SAVED_CALIBRATION')
        for e in evidence:
            t = float(e['time'])
            if not c['start'] <= t <= c['end'] or not e.get('detail'):
                raise ValueError('INVALID_EVIDENCE')
        c['assignment'] = {**item, 'reviewer': reviewer, 'at': now()}
        c['labels'] = item.get('labels', [])
    p['players'] = players
    invalidate(p)
    save(root, p, 'annotate', {'reviewer': reviewer, 'file_sha256': sha(a.file)})


def cmd_sample(a):
    """A user-selected full body sample; track clothing texture, without OCR.

    Optical flow can drift or swap people. Tracks are evidence proposals only and
    NEVER assign identity or promote a clip to high confidence.
    """
    import cv2
    import numpy as np
    root,p=load(a.project)
    if not 0<=a.time<p['source']['duration']:
        raise ValueError('SAMPLE_TIME_OUT_OF_BOUNDS')
    x1,y1,x2,y2=a.bbox
    if not (0<=x1<x2<=p['source']['width'] and 0<=y1<y2<=p['source']['height']):
        raise ValueError('SAMPLE_BOX_OUT_OF_BOUNDS')
    if not re.fullmatch('[A-Za-z0-9_-]+',a.player):
        raise ValueError('INVALID_PLAYER_ID')
    cap=cv2.VideoCapture(str(source_path(root,p)))
    cap.set(cv2.CAP_PROP_POS_MSEC,a.time*1000)
    ok,ref=cap.read()
    if not ok:raise ValueError('SAMPLE_DECODE_FAILED')
    dest=root/'samples';dest.mkdir(exist_ok=True)
    sid='s%03d'%(len(p.get('samples',[]))+1)
    path=dest/(sid+'.jpg');cv2.imwrite(str(path),ref[y1:y2,x1:x2])
    gray=cv2.cvtColor(ref,cv2.COLOR_BGR2GRAY)
    mask=np.zeros_like(gray);mask[y1:y2,x1:x2]=255
    pts=cv2.goodFeaturesToTrack(gray,maxCorners=80,qualityLevel=.02,minDistance=8,mask=mask)
    samples=[]
    for direction in (-1,1):
        prev=gray.copy()
        points=pts.copy() if pts is not None else None
        current_box=np.array([x1,y1,x2,y2],dtype=float)
        count0=len(points) if points is not None else 0
        t=a.time+direction*.2
        while points is not None and len(points)>=8 and 0<=t<p['source']['duration']:
            cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,frame=cap.read()
            if not ok:break
            cur=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            nxt,status,err=cv2.calcOpticalFlowPyrLK(prev,cur,points,None)
            if nxt is None:break
            back,back_status,_=cv2.calcOpticalFlowPyrLK(cur,prev,nxt,None)
            if back is None or back_status is None:break
            good=(status.reshape(-1)==1)&(back_status.reshape(-1)==1)&(np.linalg.norm(points-back,axis=2).reshape(-1)<2)
            if int(good.sum())<8:break
            delta=np.median((nxt-points)[good],axis=0).reshape(-1)
            if np.linalg.norm(delta)>150:break
            current_box+=np.array([delta[0],delta[1],delta[0],delta[1]])
            if current_box[0]<0 or current_box[1]<0 or current_box[2]>frame.shape[1] or current_box[3]>frame.shape[0]:break
            samples.append({'time':round(t,3),'bbox_xyxy':[round(float(v),1) for v in current_box],
                            'surviving_points':int(good.sum()),'initial_points':count0,
                            'identity_verified':False})
            points=nxt[good].reshape(-1,1,2);prev=cur;t+=direction*.2
    cap.release()
    record={'id':sid,'player_id':a.player,'time':a.time,'bbox_xyxy':a.bbox,
            'description':a.description,'confirmed_by':a.confirmed_by,
            'reviewer_kind':a.reviewer_kind,'reference':'samples/'+path.name,
            'matching_method':'bidirectional sparse optical flow; no OCR; no automatic identity assignment',
            'track_proposals':sorted(samples,key=lambda s:s['time'])}
    p.setdefault('samples',[]).append(record)
    invalidate(p)
    save(root,p,'calibration_sample',{'id':sid,'track_samples':len(samples)})
    write(dest/(sid+'-track.json'),record)


def cmd_confirm_sample(a):
    root,p=load(a.project)
    sample=next((x for x in p.get('samples',[]) if x['id']==a.sample_id),None)
    if sample is None or not a.authorization_reference.strip():
        raise ValueError('SAMPLE_AND_ACTUAL_USER_CONFIRMATION_REQUIRED')
    sample['original_reviewer_kind']=sample['reviewer_kind']
    sample['reviewer_kind']='user'
    sample['user_confirmation_reference']=a.authorization_reference
    sample['user_confirmed_at']=now()
    p['confirmation']=None
    p['state']='awaiting_clip_review' if p['selection'] else 'awaiting_player'
    save(root,p,'user_confirm_sample',{'sample_id':a.sample_id,'reference':a.authorization_reference})
    write(root/'samples'/(a.sample_id+'-track.json'),sample)


def cmd_select(a):
    root, p = load(a.project)
    if a.player not in {x['id'] for x in p['players']}:
        raise ValueError('UNKNOWN_PLAYER')
    high, unsure, other = [], [], []
    for c in p['candidates']:
        q = c.get('assignment')
        if q and q.get('needs_review') and q['player_id'] in (None,a.player):
            unsure.append(c['id'])
        elif q and q['certainty'] == 'high' and q['player_id'] == a.player:
            high.append(c['id'])
        elif q and (q['certainty'] == 'other' or (q['certainty'] == 'high' and q['player_id'] != a.player)):
            other.append(c['id'])
        else:
            unsure.append(c['id'])
    p['selection'] = {'player_id': a.player, 'high_confidence': high, 'uncertain': unsure,
                      'other': other, 'selected_by': a.selected_by}
    p['confirmation'] = None
    p['state'] = 'awaiting_clip_review'
    save(root, p, 'select_player', p['selection'])


def cut(p, c, out, source=None):
    # Audio is optional; re-encode for accurate boundaries and compatible previews.
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', c['start'], '-i', source or p['source']['path'],
         '-t', c['end']-c['start'], '-map', '0:v:0', '-map', '0:a:0?', '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30',
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-ar', '48000',
         '-ac', '2', '-movflags', '+faststart', '-y', out])


def cmd_rough(a):
    root, p = load(a.project)
    if not p['selection']:
        raise ValueError('SELECT_PLAYER_FIRST')
    for group in ('high_confidence', 'uncertain'):
        dest = root / 'rough' / group
        dest.mkdir(parents=True, exist_ok=True)
        for cid in p['selection'][group]:
            c = next(c for c in p['candidates'] if c['id'] == cid)
            out = dest / (cid+'.mp4')
            cut(p, c, out, source_path(root,p))
            c['preview'] = str(out.relative_to(root))
    save(root, p, 'rough_previews', 'separate review clips only; no merged reel')


def cmd_confirm(a):
    root, p = load(a.project)
    if not p['selection']:
        raise ValueError('SELECT_PLAYER_FIRST')
    data = read(a.file)
    if data.get('project_revision') != p['revision']:
        raise ValueError('STALE_REVIEW: regenerate decisions for current revision')
    if data.get('player_id') != p['selection']['player_id']:
        raise ValueError('WRONG_PLAYER_REVIEW')
    if data.get('reviewer_kind') not in ('user', 'test_operator') or not data.get('reviewer'):
        raise ValueError('EXPLICIT_REVIEWER_REQUIRED')
    if data['reviewer_kind'] == 'user' and not data.get('authorization_reference'):
        raise ValueError('USER_AUTHORIZATION_REFERENCE_REQUIRED')
    decisions = data['decisions']
    required = set(p['selection']['high_confidence']+p['selection']['uncertain'])
    if set(decisions) != required or any(v not in ('keep','reject') for v in decisions.values()):
        raise ValueError('REVIEW_EVERY_SELECTED_AND_UNCERTAIN_CANDIDATE')
    kept = [cid for cid,v in decisions.items() if v == 'keep']
    p['confirmation'] = {**data, 'at': now(), 'kept': kept, 'decision_sha256': sha(a.file)}
    p['state'] = 'awaiting_edit_prompt'
    save(root, p, 'confirm_selection', {'reviewer_kind': data['reviewer_kind'], 'kept': kept})
    write(root / 'confirmed-edl.json', edl(p, kept))


def edl(p, ids):
    return {'schema_version': 1, 'source': p['source'], 'project_revision': p['revision'],
            'player_id': p['selection']['player_id'],
            'clips': [{k:c[k] for k in ('id','start','end','labels')} for cid in ids
                      for c in p['candidates'] if c['id']==cid]}


def cmd_version(a):
    root, p = load(a.project)
    if p['state'] != 'awaiting_edit_prompt' or not p['confirmation']:
        raise ValueError('CONFIRM_SELECTION_FIRST')
    if not re.fullmatch('[A-Za-z0-9_-]+', a.name):
        raise ValueError('INVALID_VERSION_NAME')
    if any(v['name']==a.name for v in p['versions']):
        raise ValueError('VERSION_ALREADY_EXISTS')
    spec = read(a.spec)
    if not spec.get('prompt'):
        raise ValueError('NEW_EDIT_PROMPT_REQUIRED')
    allowed = set(p['confirmation']['kept'])
    ids = spec.get('clip_ids', p['confirmation']['kept'])
    if len(ids) != len(set(ids)) or not set(ids) <= allowed or not ids:
        raise ValueError('VERSION_MUST_USE_CONFIRMED_CLIPS')
    e = edl(p, ids)
    e.update({'name': a.name, 'prompt': spec['prompt'], 'spec': spec})
    limit = float(spec.get('max_duration', 1e9))
    if not math.isfinite(limit) or limit < .1:
        raise ValueError('INVALID_MAX_DURATION')
    remaining, clips = limit, []
    for c in e['clips']:
        if remaining <= .05:
            break
        c = dict(c)
        c['end'] = min(c['end'], c['start']+remaining)
        remaining -= c['end']-c['start']
        clips.append(c)
    e['clips'] = clips
    dest = root / 'versions' / a.name
    dest.mkdir(parents=True, exist_ok=False)
    write(dest / 'edl.json', e)
    if a.render:
        pieces = []
        for i,c in enumerate(clips):
            out = dest / ('part%03d.mp4' % i)
            cut(p, c, out, source_path(root,p))
            pieces.append(out)
        # Only generated safe file names go into the ffmpeg concat file.
        listing = dest / 'concat.txt'
        listing.write_text(''.join("file '%s'\n" % x.name for x in pieces))
        run(['ffmpeg','-hide_banner','-loglevel','error','-f','concat','-safe','1','-i',listing,
             '-c','copy','-movflags','+faststart','-y',dest/'reel.mp4'])
        e['render_probe'] = probe(dest/'reel.mp4')
        write(dest/'edl.json', e)
    p['versions'].append({'name':a.name, 'prompt':spec['prompt'], 'edl':str((dest/'edl.json').relative_to(root)),
                          'rendered':a.render, 'confirmation_sha256':p['confirmation']['decision_sha256']})
    # Retain the same confirmed master, ready for another independent prompt.
    save(root, p, 'new_version', p['versions'][-1])


def report(root, p):
    esc = html.escape
    cards = []
    for c in p['candidates']:
        images = ''.join('<a href="%s"><img loading="lazy" src="%s" width="300"><br>%.2fs</a>' %
                         (esc(f['path']),esc(f['path']),f['time']) for f in c.get('frames',[]))
        video = '<video controls preload="none" width="600" src="%s"></video>' % esc(c['preview']) if c.get('preview') else ''
        crops = ''.join('<figure><img loading="lazy" src="%s" width="70"><figcaption>%s / %s / OCR %s</figcaption></figure>' %
                        (esc(o['crop']),esc(o['id']),esc(o['color']['dominant']),esc(str(o['number_ocr']))) for o in c['observations'])
        cards.append('<article><h2>%s · %.2f–%.2fs</h2><p>%s</p>%s<div class="row">%s</div><details><summary>Local feature proposals (%d)</summary><div class="row">%s</div></details><pre>%s</pre></article>' %
                     (c['id'],c['start'],c['end'],esc(c['reason']),video,images,len(c['observations']),crops,esc(json.dumps(c['assignment'],ensure_ascii=False,indent=2))))
    text = ('<!doctype html><meta charset="utf-8"><title>篮球候选复核</title><style>body{font:16px system-ui;max-width:1200px;margin:30px auto;background:#f5f4ef;color:#18232b}article{background:white;padding:20px;margin:20px 0;border-radius:12px}.row{display:flex;flex-wrap:wrap;gap:10px}figure{margin:6px;max-width:210px}figcaption{font-size:12px}pre{white-space:pre-wrap}</style><h1>篮球候选复核</h1><p>状态：%s · 修订 %d。球衣颜色和 OCR 只是线索；逐段核验号码、稳定服饰及回合归属。</p><p>确认选片后停在 awaiting_edit_prompt；收到下一条剪辑指令才生成版本。</p><pre>%s</pre>%s' %
           (esc(p['state']),p['revision'],esc(json.dumps({'players':p['players'],'selection':p['selection'],'confirmation':p['confirmation']},ensure_ascii=False,indent=2)),''.join(cards)))
    if p['selection']:
        config={'revision':p['revision'],'player':p['selection']['player_id'],
                'ids':p['selection']['high_confidence']+p['selection']['uncertain']}
        text += '''<section style="background:#e3eee9;padding:20px"><h2>逐段决定</h2><p>填写后下载复核 JSON，交给 Codex 保存项目。此页不会合并成片或联网。</p><label>复核人 <input id="reviewer" placeholder="你的称呼"></label><div id="choices"></div><button id="download">下载选片决定 JSON</button><p id="message"></p></section><script>const config='''+json.dumps(config).replace('<','\\u003c')+''';
const choices=document.getElementById('choices');
for(const id of config.ids){const label=document.createElement('label');label.style.display='block';label.append(id+' ');const s=document.createElement('select');s.id='decision-'+id;for(const [v,t] of [['','请选择'],['keep','保留'],['reject','删除']]){const o=document.createElement('option');o.value=v;o.textContent=t;s.append(o)}label.append(s);choices.append(label)}
document.getElementById('download').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim();const decisions={};for(const id of config.ids){decisions[id]=document.getElementById('decision-'+id).value}if(!reviewer||Object.values(decisions).some(v=>!v)){document.getElementById('message').textContent='请填写复核人并决定每一段。';return}const data={project_revision:config.revision,player_id:config.player,reviewer_kind:'user',reviewer,authorization_reference:'Manual local review.html submission at revision '+config.revision,decisions};const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='review-decisions.json';a.click();URL.revokeObjectURL(a.href);document.getElementById('message').textContent='已下载。请把决定文件交给 Codex，保存后会等待下一条剪辑指令。'};</script>'''
    (root/'review.html').write_text(text,encoding='utf-8')
    fields = ['id','start','end','group','player_id','certainty','reason']
    with (root/'candidates.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in p['candidates']:
            q=c.get('assignment') or {}
            group=next((k for k in ('high_confidence','uncertain','other') if p['selection'] and c['id'] in p['selection'][k]),'unassigned')
            w.writerow({**{k:c[k] for k in ('id','start','end')},'group':group,
                        'player_id':q.get('player_id'),'certainty':q.get('certainty'),'reason':q.get('reason',c['reason'])})


def cmd_status(a):
    root,p=load(a.project)
    print(json.dumps({k:p[k] for k in ('state','revision','selection','confirmation','versions')},ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='command',required=True)
    q=s.add_parser('doctor');q.set_defaults(fn=lambda a:print(json.dumps({'python':sys.version,'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),'tesseract':shutil.which('tesseract'),'version':VERSION})))
    q=s.add_parser('init');q.add_argument('project');q.add_argument('--video',required=True);q.add_argument('--rights',required=True);q.set_defaults(fn=cmd_init)
    q=s.add_parser('relink');q.add_argument('project');q.add_argument('--video',required=True);q.set_defaults(fn=cmd_relink)
    q=s.add_parser('detect');q.add_argument('project');q.add_argument('--backend',choices=['bhe','motion-coverage'],default='bhe');q.add_argument('--runtime');q.add_argument('--python');q.add_argument('--model',help='Path to your own authorized compatible ONNX model');q.add_argument('--roi',nargs=4,type=int);q.add_argument('--fps',type=float,default=10);q.add_argument('--before',type=float,default=3);q.add_argument('--after',type=float,default=2);q.add_argument('--device',choices=['cpu','coreml'],default='cpu');q.add_argument('--timeout',type=int,default=600);q.set_defaults(fn=cmd_detect)
    q=s.add_parser('import-candidates');q.add_argument('project');q.add_argument('--file',required=True);q.set_defaults(fn=cmd_import)
    q=s.add_parser('features');q.add_argument('project');q.add_argument('--interval',type=float,default=1.5);q.add_argument('--refresh',action='store_true');q.add_argument('--no-ocr',action='store_true',help='Skip number hints for unnumbered footage');q.set_defaults(fn=cmd_features)
    q=s.add_parser('add');q.add_argument('project');q.add_argument('--start',required=True,type=float);q.add_argument('--end',required=True,type=float);q.add_argument('--reason',required=True);q.set_defaults(fn=cmd_add)
    q=s.add_parser('annotate');q.add_argument('project');q.add_argument('--file',required=True);q.set_defaults(fn=cmd_annotate)
    q=s.add_parser('sample');q.add_argument('project');q.add_argument('--player',required=True);q.add_argument('--time',required=True,type=float);q.add_argument('--bbox',nargs=4,type=int,required=True);q.add_argument('--description',required=True);q.add_argument('--confirmed-by',required=True);q.add_argument('--reviewer-kind',choices=['user','test_operator'],required=True);q.set_defaults(fn=cmd_sample)
    q=s.add_parser('confirm-sample');q.add_argument('project');q.add_argument('--sample-id',required=True);q.add_argument('--authorization-reference',required=True);q.set_defaults(fn=cmd_confirm_sample)
    q=s.add_parser('select');q.add_argument('project');q.add_argument('--player',required=True);q.add_argument('--selected-by',required=True);q.set_defaults(fn=cmd_select)
    q=s.add_parser('rough');q.add_argument('project');q.set_defaults(fn=cmd_rough)
    q=s.add_parser('confirm');q.add_argument('project');q.add_argument('--file',required=True);q.set_defaults(fn=cmd_confirm)
    q=s.add_parser('version');q.add_argument('project');q.add_argument('--name',required=True);q.add_argument('--spec',required=True);q.add_argument('--render',action='store_true');q.set_defaults(fn=cmd_version)
    q=s.add_parser('status');q.add_argument('project');q.set_defaults(fn=cmd_status)
    a=p.parse_args()
    if a.command=='detect' and a.backend=='bhe' and not a.runtime:
        p.error('--runtime is required for BHE; no automatic downloads')
    if a.command=='detect' and (not all(math.isfinite(v) and v>0 for v in (a.fps,a.before,a.after)) or a.timeout<=0):
        p.error('fps, before, after and timeout must be positive')
    if a.command=='features' and (not math.isfinite(a.interval) or a.interval<=0):
        p.error('--interval must be positive')
    try:
        a.fn(a)
    except (ValueError,KeyError,FileNotFoundError,subprocess.TimeoutExpired,ImportError) as e:
        print(str(e),file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
