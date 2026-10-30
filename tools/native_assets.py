"""Validate the extracted, unpatched inputs used by ordinary ROM builds."""
import hashlib
import json
from pathlib import Path


def load_manifest(directory):
    return json.loads((Path(directory)/'manifest.json').read_text(encoding='utf-8'))


def load_asset(path):
    path = Path(path)
    manifest = load_manifest(path.parent)
    expected = manifest['files'][path.name]
    data = path.read_bytes()
    if len(data) != expected['size'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise ValueError(f'Native asset size or SHA-256 differs: {path}')
    return data
