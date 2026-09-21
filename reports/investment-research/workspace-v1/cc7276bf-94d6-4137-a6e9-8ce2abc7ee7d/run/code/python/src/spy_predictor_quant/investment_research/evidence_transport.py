"""Short, manifest-bound evidence identities on the model wire; immutable IDs on disk."""
from copy import deepcopy

LIST_REFS = {'evidence_ids', 'input_evidence_ids', 'visible_evidence_ids'}
SINGLE_REFS = {'evidence_id', 'input_evidence_id', 'parent_evidence_id'}


def translate(value, mapping, field=None):
    if isinstance(value, dict):
        return {mapping.get(k, k) if field == 'evidence' else k: translate(v, mapping, k) for k, v in value.items()}
    if isinstance(value, list):
        return [mapping.get(v, v) if field in LIST_REFS and isinstance(v, str) else translate(v, mapping) for v in value]
    if isinstance(value, str):
        if field in SINGLE_REFS:
            return mapping.get(value, value)
        if field in {'left', 'right'} and '#/' in value:
            identity, pointer = value.split('#', 1)
            return mapping.get(identity, identity) + '#' + pointer
    return value


def prepare(request, state, task):
    forward = {identity: f'e{index + 1}' for index, identity in enumerate(state['evidence_ids']) if identity in task['visible_evidence_ids']}
    request['evidence_aliases'] = {alias: identity for identity, alias in forward.items()}
    request['context'] = translate(request['context'], forward)
    request['context']['evidence_identity_contract'] = 'eN aliases identify evidence in this task manifest. Source IDs select read_source; they are not evidence IDs. Numeric references use eN#/data/field.'
    choices = list(forward.values())
    def constrain(value, field=None):
        if not isinstance(value, dict):
            return
        if field in LIST_REFS and 'items' in value:
            if choices:
                value['items']['enum'] = choices
            else:
                value['maxItems'] = 0
        if field in SINGLE_REFS and choices:
            value['enum'] = choices
        for key, child in value.get('properties', {}).items():
            constrain(child, key)
        if isinstance(value.get('items'), dict):
            constrain(value['items'])
    for definition in request['tool_schemas'].values():
        constrain(definition)
    return request


def restore(action, request):
    return translate(deepcopy(action), request.get('evidence_aliases', {}))
