#!/usr/bin/env python3
"""Restore catalog source files from pinned URLs and verify SHA256. No models."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
try:
    from .schema import validate_catalog, sha, require
    from .locking import safe_path
except ImportError:
    from schema import validate_catalog, sha, require
    from locking import safe_path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path, default=ROOT/'eval/data/catalog.json')
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--video', action='append')
    a = p.parse_args()
    catalog = validate_catalog(json.loads(a.catalog.read_text()))
    for v in catalog['videos']:
        if a.video and v['id'] not in a.video:
            continue
        dest = safe_path(ROOT, v['source_path'])
        if not dest.exists():
            require(not a.verify_only, 'SOURCE_MISSING: ' + v['id'])
            require(v.get('download_url', '').startswith('https://'), 'PINNED_DOWNLOAD_URL_REQUIRED')
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + '.part')
            subprocess.run(['curl', '-fLsS', '--retry', '2', '--max-time', '300',
                            '-A', 'BasketballEval/1.0', '-o', str(tmp), v['download_url']], check=True)
            require(sha(tmp) == v['sha256'], 'DOWNLOAD_HASH_MISMATCH: ' + v['id'])
            tmp.replace(dest)
        require(sha(dest) == v['sha256'], 'SOURCE_HASH_MISMATCH: ' + v['id'])
        print(v['id'] + ': verified ' + v['license'])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr); sys.exit(2)
