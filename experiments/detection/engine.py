"""Research-only candidate operators. All proposals are unconfirmed drafts.
No filenames, source-specific timestamps, coordinates or human labels are inputs.
"""
import copy,importlib.util,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'third_party/bhe/src'))
from basketball_highlight.events import find_candidate_crossings
spec=importlib.util.spec_from_file_location('bhe_generator',ROOT/'third_party/bhe/scripts/generate_candidates.py')
bhe=importlib.util.module_from_spec(spec);spec.loader.exec_module(bhe)

def boxes(records,name):
 return [(float(r['time']),d) for r in records for d in r.get('detections',[]) if d['name']==name]

def rim_from(items,confidence):return bhe._hoops_from(items,confidence)

def clusters(records,confidence):
 groups=[]
 for t,d in boxes(records,'hoop'):
  if d['confidence']<confidence:continue
  width=max(1,d['xyxy'][2]-d['xyxy'][0]);x,y=d['center']
  possible=[g for g in groups if abs(x-g['x'])<=max(width,g['width'])*1.5 and abs(y-g['y'])<=max(width,g['width'])]
  if possible:
   g=min(possible,key=lambda g:math.hypot(x-g['x'],y-g['y']));g['items'].append(d);g['times'].append(t)
   g['x']=statistics.median(p['center'][0] for p in g['items']);g['y']=statistics.median(p['center'][1] for p in g['items'])
  else:groups.append({'x':x,'y':y,'width':width,'items':[d],'times':[t]})
 return groups

def suggest_rois(records,confidence):
 proposals=[];balls=boxes(records,'ball')
 for i,g in enumerate(clusters(records,confidence)):
  rim=rim_from(g['items'],confidence)
  if rim is None:continue
  w=max(1,rim['width']);h=max(1,rim['height'])
  active=sum(abs(d['center'][0]-rim['center_x'])<=3*w and abs(d['center'][1]-rim['rim_y'])<=5*w for t,d in balls)
  proposals.append({'id':'rim%03d'%i,'status':'draft','requires_user_confirmation':True,'rim':rim,
    'roi_xyxy':[max(0,rim['center_x']-4*w),max(0,rim['rim_y']-5*w),rim['center_x']+4*w,rim['rim_y']+7*w],
    'support_frames':len(g['times']),'near_ball_observations':active,'ranking_score':active+math.log1p(len(g['times'])),
    'meaning':'ROI suggestion only; active game hoop and source bounds require review'})
 return sorted(proposals,key=lambda p:(-p['ranking_score'],p['rim']['center_x']))

def sampled(records,cfg):
 step=1/float(cfg['sample_fps']);selected=[];last=-1e30
 for r in sorted(records,key=lambda r:r['time']):
  if float(r['time'])-last<step-1e-5:continue
  selected.append({**r,'detections':[d for d in r.get('detections',[]) if d['confidence']>=cfg['detector_conf']]});last=float(r['time'])
 return selected

def stabilize(records,rim):
 out=[]
 for r in records:
  hoops=[d for d in r.get('detections',[]) if d['name']=='hoop']
  anchor=min(hoops,key=lambda d:math.hypot(d['center'][0]-rim['center_x'],d['center'][1]-rim['rim_y'])) if hoops else None
  dx=anchor['center'][0]-rim['center_x'] if anchor else 0;dy=anchor['center'][1]-rim['rim_y'] if anchor else 0
  items=[]
  for d in r.get('detections',[]):
   q=copy.deepcopy(d);q['center']=[d['center'][0]-dx,d['center'][1]-dy];q['xyxy']=[d['xyxy'][0]-dx,d['xyxy'][1]-dy,d['xyxy'][2]-dx,d['xyxy'][3]-dy];items.append(q)
  out.append({**r,'detections':items})
 return out

def tracks(records,rim,max_gap):
 active=[]
 for r in records:
  used=set()
  for d in [d for d in r['detections'] if d['name']=='ball']:
   possible=[]
   for j,tr in enumerate(active):
    dt=r['time']-tr[-1]['time'];prev=tr[-1]['detections'][0]
    if j not in used and 0<dt<=max_gap:
     dist=math.dist(d['center'],prev['center'])/max(1,rim['width'])
     if dist<=2+15*dt:possible.append((dist,j))
   if possible:
    _,j=min(possible);active[j].append({'time':r['time'],'detections':[d]});used.add(j)
   else:active.append([{'time':r['time'],'detections':[d]}]);used.add(len(active)-1)
 return [tr for tr in active if len(tr)>1]

def dedupe(events,seconds):
 out=[]
 for e in sorted(events,key=lambda e:e['time']):
  if out and e['time']-out[-1]['time']<=seconds:continue
  out.append(e)
 return out

def coverage(ranges):
 out=[]
 for start,end in ranges:
  t=float(start)
  while t<end:
   out.append({'start':t,'end':min(end,t+8),'kind':'review_coverage','status':'draft','not_a_scoring_detection':True});t+=6
 return out

def propose(records,duration,ranges,cfg):
 cfg={'hoop_conf':.08,'margin':16,'max_gap':2.5,'min_descent':20,'dedupe':.8,'sample_fps':3,'detector_conf':.15,**cfg}
 records=sampled(records,cfg);rois=suggest_rois(records,cfg['hoop_conf']);global_rim=rim_from([d for _,d in boxes(records,'hoop')],cfg['hoop_conf'])
 if global_rim is None:return {'events':[],'rois':rois,'review_windows':coverage(ranges) if cfg.get('review_coverage') else [],'failure':'NO_HOOP_PROPOSAL','status':'draft'}
 windows=[]
 if cfg.get('rim_window'):
  for start,end in ranges:
   t=float(start)
   while t<end:
    subset=[r for r in records if t<=r['time']<t+cfg['rim_window']];local=rim_from([d for _,d in boxes(subset,'hoop')],cfg['hoop_conf'])
    if local:windows.append((subset,local))
    t+=cfg['rim_window']/2
 else:
  rims=[p['rim'] for p in rois] if cfg.get('multi_rim') and rois else [global_rim]
  windows=[(records,rim) for rim in rims]
 events=[]
 for rows,rim in windows:
  if cfg.get('stabilize'):rows=stabilize(rows,rim)
  streams=tracks(rows,rim,cfg['max_gap']) if cfg.get('track_all') else [rows]
  for stream in streams:
   cs=find_candidate_crossings(stream,rim,max_gap_sec=cfg['max_gap'],margin=cfg['margin'],dedupe_sec=cfg['dedupe'],min_descent_px=cfg['min_descent'])
   for c in cs:
    if cfg.get('interpolate'):
     a,b=c['above'],c['below']
     closer=[{'time':r['time'],'x':d['center'][0],'y':d['center'][1]} for r in stream if a['time']<=r['time']<b['time'] for d in r['detections'] if d['name']=='ball' and d['center'][1]<rim['rim_y'] and abs(d['center'][0]-c['x_cross'])<=rim['width']]
     if closer:a=max(closer,key=lambda p:p['time'])
     c['time']=a['time']+(rim['rim_y']-a['y'])/(b['y']-a['y'])*(b['time']-a['time']);c['interpolation_above']=a
    events.append({**c,'rim':rim,'signals':['trajectory_crossing'],'status':'draft'})
  if cfg.get('proximity') or cfg.get('motion_union'):
   for r in rows:
    for d in r['detections']:
     if d['name']!='ball':continue
     near=abs(d['center'][0]-rim['center_x'])<=1.2*rim['width'] and abs(d['center'][1]-rim['rim_y'])<=2*max(rim['height'],rim['width'])
     motion_ok=cfg.get('proximity') or r.get('rim_motion_residual',0)>=.025
     if near and motion_ok:events.append({'time':r['time'],'rim':rim,'signals':['near_rim']+(['local_motion'] if cfg.get('motion_union') else []),'status':'draft'})
 events=[e for e in events if 0<=e['time']<=duration and any(a<=e['time']<=b for a,b in ranges)]
 return {'events':dedupe(events,cfg['dedupe']),'rois':rois,'review_windows':coverage(ranges) if cfg.get('review_coverage') else [],'status':'draft'}
