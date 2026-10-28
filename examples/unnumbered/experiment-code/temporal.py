"""Conservative local tracklets. No truth access, no bridging long gaps/cuts."""
import math
import numpy as np
from person_pilot import distance,iou


def link_cost(a,b):
    aa=a['box'];bb=b['box'];ha=aa[3]-aa[1];hb=bb[3]-bb[1]
    ratio=hb/max(1,ha)
    if not .5<ratio<2:return None
    delta=math.hypot((aa[0]+aa[2]-bb[0]-bb[2])/2,(aa[1]+aa[3]-bb[1]-bb[3])/2)/max(ha,hb)
    appearance=distance(a['descriptor'],b['descriptor'])
    if delta>.8 or appearance>.42:return None
    return .5*delta+.35*appearance+.15*(1-iou(aa,bb))


def tracklets(data):
    tracks=[]
    for frame in data['records']:
        now=frame['time'];items=frame['items'];links=[]
        active=[(i,tr) for i,tr in enumerate(tracks) if now-tr[-1][0]<=.71]
        for j,o in enumerate(items):
            for i,tr in active:
                cost=link_cost(tr[-1][1],o)
                if cost is not None:links.append((cost,i,j))
        used_i=set();used_j=set()
        # Mutual-nearest matching refuses ambiguous links instead of guessing.
        best_i={};best_j={}
        for cost,i,j in sorted(links):
            best_i.setdefault(i,(cost,j));best_j.setdefault(j,(cost,i))
        for cost,i,j in sorted(links):
            if best_i[i][1]!=j or best_j[j][1]!=i:continue
            alternatives=[c for c,ii,jj in links if (ii==i and jj!=j) or (jj==j and ii!=i)]
            if alternatives and min(alternatives)-cost<.04:continue
            tracks[i].append((now,items[j]));used_i.add(i);used_j.add(j)
        for j,o in enumerate(items):
            if j not in used_j:tracks.append([(now,o)])
    return tracks


def assign(data,refs,calibration,max_distance,profile_margin,person_margin):
    by_time={r['time']:{'time':r['time'],'accepted':[],'uncertain':[]} for r in data['records']}
    summaries=[]
    for tid,tr in enumerate(tracklets(data)):
        scores={pid:[min(distance(o['descriptor'],ref) for ref in rs) for _,o in tr] for pid,rs in refs.items()}
        # A track needs repeated clothing evidence; the median rejects a single
        # accidental color match. Clear calibration anchors establish identity.
        ranked=sorted((float(np.median(vals)),pid) for pid,vals in scores.items())
        best,pid=ranked[0];gap=ranked[1][0]-best if len(ranked)>1 else 1.
        anchors=set()
        for p in calibration['people']:
            for s in p['samples']:
                if any(abs(t-s['time'])<.05 and iou(o['box'],s['box'])>=.35 for t,o in tr):anchors.add(p['id'])
        anchored=len(anchors)==1
        if anchored:
            pid=next(iter(anchors));best=float(np.median(scores[pid]));gap=1.
        supported=anchored or (len(tr)>=3 and best<=max_distance and gap>=profile_margin)
        if len(anchors)>1:supported=False
        summaries.append({'track_id':tid,'start':tr[0][0],'end':tr[-1][0],'count':len(tr),'player_id':pid if supported else None,'anchors':sorted(anchors),'median_distance':best,'margin':gap})
        for t,o in tr:
            ds=sorted((scores[p][next(i for i,(tt,oo) in enumerate(tr) if oo['id']==o['id'])],p) for p in refs)
            own=min(distance(o['descriptor'],ref) for ref in refs[pid])
            # Do not carry an anchor through a severely incompatible appearance.
            acceptable=supported and own<=max_distance+.12
            item={'observation_id':o['id'],'player_id':pid,'box':o['box'],'distance':round(own,5),'profile_margin':round(gap,5),'person_score':o['person_score'],'track_id':tid,'track_anchored':anchored}
            by_time[t]['accepted' if acceptable else 'uncertain'].append(item)
    for frame in by_time.values():
        accepted=[]
        for pid in refs:
            matches=sorted((o for o in frame['accepted'] if o['player_id']==pid),key=lambda o:(not o['track_anchored'],o['distance']))
            if not matches:continue
            if len(matches)>1 and matches[0]['track_anchored']==matches[1]['track_anchored'] and matches[1]['distance']-matches[0]['distance']<person_margin:
                frame['uncertain'].extend(matches);continue
            accepted.append(matches[0]);frame['uncertain'].extend(matches[1:])
        frame['accepted']=accepted
    return list(by_time.values()),summaries
