#!/usr/bin/env python3
"""Download the exact licensed Commons transcode and verify its archived digest."""
import hashlib,json,os,tempfile,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent
rights=json.loads((root/'source/rights.json').read_text())
target=root/'source/park-bodycam.webm'
if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==rights['sha256']:
    print('Already verified:',target.name)
else:
    with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as out:
        path=Path(out.name)
        try:
            with urllib.request.urlopen(rights['download_url'],timeout=120) as response:
                while chunk:=response.read(1024*1024):out.write(chunk)
            out.flush()
            if hashlib.sha256(path.read_bytes()).hexdigest()!=rights['sha256']:raise ValueError('SHA256_MISMATCH: original file was not replaced')
            os.replace(path,target)
        finally:
            path.unlink(missing_ok=True)
    print('Downloaded and verified:',target.name)
