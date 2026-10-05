"""Reviewed default prompts and their frozen promotion provenance."""
import hashlib
import json

from .contracts import ROOT, M2_ROLES
from spy_predictor_quant.market_archive import content_hash


DEFAULT_PROMPT_VERSION = 'v2.17'
LIVE_PROMPT_VERSION = 'v2.19'


def promoted_profile(version=DEFAULT_PROMPT_VERSION):
    if version not in {DEFAULT_PROMPT_VERSION, 'v2.18', LIVE_PROMPT_VERSION}:
        raise ValueError('Unknown production profile')
    root = ROOT / 'prompts/investment-research' / version
    profile = json.loads((root / 'promotion.json').read_text())
    if profile['prompt_version'] != version:
        raise ValueError('Promoted prompt version mismatch')
    shared = (root / 'shared.md').read_text()
    for role in M2_ROLES:
        prompt = shared + '\n' + (root / (role + '.md')).read_text()
        if content_hash(prompt) != profile['roles'][role]['prompt_sha256']:
            raise ValueError('Promoted prompt integrity mismatch: ' + role)
    if hashlib.sha256((root / 'tools.json').read_bytes()).hexdigest() != profile['tools_sha256']:
        raise ValueError('Promoted tool contract integrity mismatch')
    return profile
