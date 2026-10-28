"""Tamper-evident confirmed-file registry. Scoring never creates/updates locks."""
import json
from pathlib import Path
try:
    from .schema import require, sha, ValidationError, DATASET
except ImportError:
    from schema import require, sha, ValidationError, DATASET


def safe_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and not Path(relative).is_absolute(), 'LOCK_PATH_ESCAPES_REPOSITORY')
    return path


def read_locked(root, registry_path):
    root = Path(root).resolve()
    registry = json.loads(Path(registry_path).read_text())
    require(registry.get('schema_version') == 1 and registry.get('dataset_id') == DATASET,
            'INVALID_LOCK_REGISTRY')
    directory = safe_path(root, registry['directory'])
    entries = registry.get('files', [])
    require(isinstance(entries, list), 'INVALID_LOCK_FILES')
    seen, result = set(), []
    for item in entries:
        relative = item['path']
        require(relative not in seen, 'DUPLICATE_LOCK_ENTRY')
        seen.add(relative)
        path = safe_path(root, relative)
        require(path.parent == directory and path.suffix == '.json', 'LOCK_FILE_OUTSIDE_CONFIRMED_DIRECTORY')
        require(path.is_file() and sha(path) == item['sha256'], 'CONFIRMED_HASH_MISMATCH: ' + relative)
        result.append((item, path))
    present = {p.relative_to(root).as_posix() for p in directory.glob('*.json')}
    require(present == seen, 'UNLOCKED_CONFIRMED_FILE_OR_MISSING_LOCK_ENTRY')
    return registry, result


def write_registry(root, registry_path, directory, entries):
    # Called only by explicit legacy conversion or import-reviewed, never score.
    value = {'schema_version': 1, 'dataset_id': DATASET, 'directory': directory,
             'files': sorted(entries, key=lambda x: x['path'])}
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)
