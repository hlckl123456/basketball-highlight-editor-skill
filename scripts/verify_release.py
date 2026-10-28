#!/usr/bin/env python3
"""Verify portable case, third-party source hashes, media and public text hygiene."""
import argparse,gzip,hashlib,importlib.util,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()


def main():
    a=argparse.ArgumentParser();a.add_argument('--write-manifest',action='store_true');a.add_argument('--development-only',action='store_true',help='Do not open hold-out-associated data; defer their integrity/semantic checks until final freeze');args=a.parse_args()
    old_manifest={}
    if (ROOT/'MANIFEST.sha256').exists():
        old_manifest={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (ROOT/'MANIFEST.sha256').read_text().splitlines()}
    withheld=set()
    if args.development_only:
        catalog_for_scope=json.loads((ROOT/'eval/data/catalog.json').read_text())
        held=[v for v in catalog_for_scope['videos'] if v['split']=='holdout']
        registry_metadata=json.loads((ROOT/'eval/annotations/confirmed.lock.json').read_text())
        assert not any(e['video_id'] in {v['id'] for v in held} for e in registry_metadata['files']),'Development-only verifier refuses to open locked hold-out facts; defer to final full verification'
        withheld.add('eval/review.html')
        for v in held:
            withheld.update([v['source_path'],v['review_media_path'],f"eval/predictions/{v['id']}.json"])
            for name in old_manifest:
                if any(name.startswith(f"eval/{prefix}/{v['id']}"+suffix) for prefix,suffix in [('annotations/drafts','.json'),('annotations/confirmed','.json'),('annotations/review-state','.json'),('data/proposals','/'),('data/previews','/')]):withheld.add(name)
        assert all((ROOT/name).is_file() for name in withheld),'Withheld source missing'

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
    model=ROOT/'skills/basketball-highlight-editor/assets/yolox/yolox_nano.onnx'
    provenance=h.read(model.parent/'provenance.json')
    assert provenance['sha256']==sha(model) and provenance['license']=='Apache-2.0'
    for name in ('university','ljubljana'):
        project,p=h.load(ROOT/'examples/unnumbered'/(name+'-project'))
        assert p['state']=='awaiting_edit_prompt' and not p['versions']
        assert p['confirmation']['reviewer_kind']=='test_operator'
        assert all(s['reviewer_kind']=='test_operator' for s in p['samples'])
        assert sha(project/'people/detections.json')==p['person_detector']['data_sha256']
        assert h.read(project/'people/matches.json')['detections_sha256']==p['person_detector']['data_sha256']
        assert h.read(project/'confirmed-edl.json')['source']==p['source']
        assert not Path(p['source']['path']).is_absolute()
        for c in p['candidates']:assert (project/c['preview']).is_file()
    # Evaluation facts have a separate human-only, hash-locked trust boundary.
    if (ROOT/'eval/data/catalog.json').is_file():
        import sys
        sys.path.insert(0,str(ROOT))
        from eval.schema import validate_catalog,validate_annotations
        from eval.locking import read_locked
        catalog=validate_catalog(h.read(ROOT/'eval/data/catalog.json'))
        assert len(catalog['videos'])>=8
        assert sum(v['split']=='holdout' for v in catalog['videos'])==3
        assert sum(v['scene_type'].startswith('outdoor') for v in catalog['videos'])>len(catalog['videos'])/2
        for v in catalog['videos']:
            if args.development_only and v['split']=='holdout':continue
            assert sha(ROOT/v['source_path'])==v['sha256'],v['id']
            assert (ROOT/v['review_media_path']).is_file(),v['id']
            assert sha(ROOT/v['review_media_path'])==v['review_media_sha256'],v['id']
            draft=h.read(ROOT/'eval/annotations/drafts'/(v['id']+'.json'))
            validate_annotations(draft,v,require_all_draft=True)
            assert draft['events'],v['id']
        registry,locked=read_locked(ROOT,ROOT/'eval/annotations/confirmed.lock.json')
        for entry,path in locked:
            v=next(v for v in catalog['videos'] if v['id']==entry['video_id'])
            if args.development_only and v['split']=='holdout':continue
            validate_annotations(h.read(path),v,allow_legacy=v['id']=='indiana')
    paths=[]
    for f in ROOT.rglob('*'):
        rel=f.relative_to(ROOT)
        if not f.is_file() or any(p in ('.git','work','__pycache__','.local','local-media','.venv','node_modules') for p in rel.parts):continue
        if args.development_only and rel.as_posix() in withheld:
            assert rel.as_posix() in old_manifest,'Withheld file has no frozen release digest'
            paths.append((rel.as_posix(),old_manifest[rel.as_posix()]))
            continue
        assert f.suffix not in ('.pt','.onnx','.dmg','.apk','.exe') or f==model,rel
        assert f.stat().st_size<100_000_000,rel
        if f.suffix in ('.md','.json','.txt','.log','.html','.csv','.py','.yml','.yaml','.gz'):
            text=gzip.decompress(f.read_bytes()).decode() if f.suffix=='.gz' else f.read_text(encoding='utf-8')
            assert not re.search(r'/Users/[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/',text),rel
            assert not re.search(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b|github_pat_[A-Za-z0-9_]{20,}',text),rel
            if f.suffix in ('.json','.gz'):
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
    if args.development_only:print(f'DEVELOPMENT SCOPE: {len(withheld)} hold-out-associated files were not opened; their frozen manifest digests were retained, checks deferred.')
    print(f'PASS: {len(paths)} release files; real confirmed case, portable source, 639 crops, upstream blobs, original hashes, links and public-text checks.')


if __name__=='__main__':main()
