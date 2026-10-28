"""Content-addressed, integrity-checked local cache, with atomic writes."""
import hashlib
import json
import os
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def get(directory, namespace, key):
    path = Path(directory)/namespace/(key+'.json')
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if data['key'] != key or digest(data['payload']) != data['payload_sha256']:
            raise ValueError('digest mismatch')
        return data['payload']
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('DETECTION_CACHE_CORRUPT: remove this entry and rerun: '+str(path)) from exc


def put(directory, namespace, key, payload):
    path = Path(directory)/namespace/(key+'.json'); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    tmp.write_text(json.dumps({'key': key, 'payload_sha256': digest(payload), 'payload': payload},
                              ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)
