"""Deterministic role views; omitted source text remains available for inspection."""
from .context import compact

PROFILE = 'role-research-v1'


def project(value, role, selected_sections):
    adapter = value.get('adapter')
    catalog = adapter in {'sec_submissions', 'primary_feed'}
    if value.get('data') is None and 'excerpt' in value:
        catalog = role == 'technical'
        if adapter == 'document_section':
            key = (tuple(value.get('symbols', [])), value.get('query'))
            catalog |= selected_sections.get(key) != (value.get('published_at', ''), value.get('occurrence', 0))
            if role == 'macro':
                catalog |= value.get('query') != 'outlook'
            if role == 'commodities':
                catalog |= value.get('query') not in {'outlook', 'supply'}
        elif value.get('source_id', '').startswith('discovered-'):
            catalog = True  # Selected derived sections below; full filing stays inspectable.
    result = compact(value, catalog_only=catalog)
    if not catalog and adapter == 'document_section':
        result['excerpt'] = value['excerpt'][:4000]
        result['context_excerpt_truncated'] = len(value['excerpt']) > 4000
        result['selection_qualification'] = 'Latest dated keyword window, not a verified complete disclosure. Inspect for additional matches.'
    return result


def select_sections(store, state):
    selected = {}
    for identity in state['evidence_ids']:
        value = store.get('evidence', identity)
        if value.get('adapter') == 'document_section':
            key = (tuple(value.get('symbols', [])), value.get('query'))
            rank = (value.get('published_at', ''), value.get('occurrence', 0))
            selected[key] = max(selected.get(key, rank), rank)
    return selected
