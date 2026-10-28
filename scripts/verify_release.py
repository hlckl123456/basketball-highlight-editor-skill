#!/usr/bin/env python3
"""Verify portable case, third-party source hashes, media and public text hygiene."""
import argparse,hashlib,importlib.util,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()


def main():
    a=argparse.ArgumentParser();a.add_argument('--write-manifest',action='store_true');args=a.parse_args()
    spec=importlib.util.spec_from_file_location('h',ROOT/'skills/basketball-highlight-editor/scripts/highlight.py')
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    case=ROOT/'examples/indiana';root,p=h.load(case/'project')
    assert p['state']=='awaiting_edit_prompt' and p['revision']==10
    assert p['confirmation']['reviewer_kind']=='user' and p['confirmation']['kept']==['c0001','c0003']
    assert not p['versions'] and not list((case/'project').rglob('reel.mp4'))
    assert p['source']['path']=='../source/indiana-cc0.webm'
    assert h.sha(case/'project/review-decisions.json')==p['confirmation']['decision_sha256']
    assert len(p['candidates'])==4 and sum(len(c['observations']) for c in p['candidates'])==639
    for c in p['candidates']:
        assert (root/c['preview']).is_file()
        for f in c['frames']:assert (root/f['path']).is_file()
        for o in c['observations']:assert (root/o['crop']).is_file()
    for s in p['samples']:assert (root/s['reference']).is_file()
    manifest=h.read(ROOT/'dependencies/bhe-source-manifest.json')
    for f in manifest['files']:
        path=ROOT/'third_party/bhe'/f['path']
        assert sha(path)==f['sha256'],path
        if f['path'].endswith('.py') or f['path']=='LICENSE':assert f['public_git_blob_verified'] is True
    # The archived first version must still match the historical real-run hashes.
    for f in h.read(case/'validation/installed-manifest.json'):
        assert sha(case/'original-skill-v1.0.0'/f['path'])==f['sha256'],f['path']
    paths=[]
    for f in ROOT.rglob('*'):
        rel=f.relative_to(ROOT)
        if not f.is_file() or any(p in ('.git','work','__pycache__') for p in rel.parts):continue
        assert f.suffix not in ('.pt','.onnx','.dmg','.apk','.exe'),rel
        assert f.stat().st_size<100_000_000,rel
        if f.suffix in ('.md','.json','.txt','.log','.html','.csv','.py','.yml','.yaml'):
            text=f.read_text(encoding='utf-8')
            assert not re.search(r'/Users/[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/',text),rel
            assert not re.search(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b|github_pat_[A-Za-z0-9_]{20,}',text),rel
            if f.suffix=='.json':
                value=json.loads(text)
                def sensitive(v):
                    if isinstance(v,dict):
                        for k,x in v.items():
                            assert not (k.lower() in ('api_key','openai_api_key','access_token','refresh_token','uuid') and x),rel
                            sensitive(x)
                    elif isinstance(v,list):
                        for x in v:sensitive(x)
                sensitive(value)
        if f.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',f.read_text()):
                target=target.split('#')[0]
                if not target or re.match(r'[a-z]+:',target) or target.startswith('<'):continue
                assert (f.parent/target).exists(),(rel,target)
        if rel.as_posix()!='MANIFEST.sha256':paths.append((rel.as_posix(),sha(f)))
    listing=''.join(digest+'  '+name+'\n' for name,digest in sorted(paths))
    if args.write_manifest:(ROOT/'MANIFEST.sha256').write_text(listing)
    elif (ROOT/'MANIFEST.sha256').exists():
        assert (ROOT/'MANIFEST.sha256').read_text()==listing,'Release files changed; review and regenerate manifest.'
    print(f'PASS: {len(paths)} release files; real confirmed case, portable source, 639 crops, upstream blobs, original hashes, links and public-text checks.')


if __name__=='__main__':main()
