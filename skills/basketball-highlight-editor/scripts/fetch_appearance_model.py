#!/usr/bin/env python3
"""Explicit opt-in download of the documented Apache-2.0 DINOv2-S checkpoint.
No other skill command downloads models. Keep weights outside Git.
"""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,help='Local .pth destination; never commit this file');a=p.parse_args()
 meta=json.loads((Path(__file__).resolve().parents[1]/'assets/dinov2/provenance.json').read_text());out=Path(a.output).resolve();out.parent.mkdir(parents=True,exist_ok=True)
 if out.exists():
  if digest(out)!=meta['weights_sha256']:raise ValueError('MODEL_DESTINATION_EXISTS_WITH_DIFFERENT_HASH: choose another path')
  print('Verified existing official DINOv2-S model');return
 with tempfile.NamedTemporaryFile(dir=out.parent,delete=False) as f:temp=Path(f.name)
 try:
  subprocess.run(['curl','--fail','--location','--max-time','300','--output',str(temp),meta['model_url']],check=True)
  if digest(temp)!=meta['weights_sha256']:raise ValueError('APPEARANCE_MODEL_DOWNLOAD_HASH_MISMATCH')
  os.replace(temp,out)
 finally:temp.unlink(missing_ok=True)
 print('Downloaded and verified official DINOv2-S; Apache-2.0; weights remain local')

if __name__=='__main__':main()
