#!/usr/bin/env python3
"""Create unmistakably synthetic browser-test media outside the real corpus."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from eval.build_review import build
from eval.locking import write_registry
from eval.schema import DATASET


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.output.resolve();videos=[]
 for i,(vid,color,split) in enumerate([('synthetic-ui','blue','development'),('synthetic-holdout','red','holdout')]):
  media=root/'eval/data/sources'/(vid+'.mp4');media.parent.mkdir(parents=True,exist_ok=True)
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c={color}:s=640x360:d=5','-c:v','libx264','-pix_fmt','yuv420p','-y',str(media)],check=True)
  digest=hashlib.sha256(media.read_bytes()).hexdigest();relative=media.relative_to(root).as_posix()
  v={'id':vid,'split':split,'sha256':digest,'duration':5,'group_id':vid,'source_path':relative,'review_media_path':relative,'source_url':'https://example.invalid/synthetic','author':'Synthetic UI test generator','license':'CC0 synthetic fixture','license_url':'https://example.invalid/synthetic-license','downloaded_at':'2026-01-01','scene_type':'synthetic_test','filming_conditions':'SYNTHETIC TEST ONLY. No real people or human annotations.','redistributable':True,'evaluation_ranges':[[0,5]]};videos.append(v)
  events=[{'id':'e'+str(j+1),'time':t,'is_score':None,'scorer_id':None,'ball_handler_id':None,'visible_player_ids':None,'visibility_complete':False,'status':'draft','deleted':False,'confirmed_fields':[],'confirmation':None,'origin':{'kind':'synthetic_ui_fixture'},'notes':'SYNTHETIC TEST ONLY'} for j,t in enumerate([1,3])]
  doc={'schema_version':1,'document_type':'basketball_annotations','dataset_id':DATASET,'video_id':vid,'video_sha256':digest,'duration':5,'target_player_ids':['p1'],'players':[{'id':'p1','appearance_description':'Synthetic blue shape'},{'id':'p2','appearance_description':'Synthetic red shape'}],'events':events,'reviewed_ranges':[]}
  path=root/'eval/annotations/drafts'/(vid+'.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(doc,indent=2)+'\n')
 catalog={'schema_version':1,'dataset_id':DATASET,'videos':videos};(root/'eval/data/catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
 (root/'eval/annotations/confirmed').mkdir(parents=True,exist_ok=True)
 write_registry(root,root/'eval/annotations/confirmed.lock.json','eval/annotations/confirmed',[])
 print(build(root,root/'eval/review.html',synthetic=True))


if __name__=='__main__':main()
