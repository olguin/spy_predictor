"""Exact identity maps on final wire output; semantic judgments are never repaired."""
from copy import deepcopy

from jsonschema import Draft202012Validator


def tool_schemas(base, task, state, remaining_turns):
    definitions = {k: deepcopy(v) for k, v in base.items() if k in task["permitted_tools"]}
    if task['stage'] == 'triage' and 'route_question' in definitions:
        pending = [q['question_id'] for q in state['questions'] if q['status'] == 'PROPOSED']
        if pending:
            definitions['route_question']['properties']['question_id']['enum'] = pending
        else:
            del definitions['route_question']
    if remaining_turns <= 1:
        definitions = {"submit_findings": definitions["submit_findings"]}
    if (state['mandate']['schema_version'] == 'investment-research-mandate-v7'
            and task['role'] == 'company' and task['stage'] == 'research' and task['round'] == 0):
        required = [w['symbol'] for w in state['mandate']['watchlist'] if w['kind'] == 'company']
        completed = {h['action']['arguments']['symbol'] for h in task.get('history', [])
                     if h['action']['tool'] == 'calculate_scenarios' and h['result'].get('status') == 'OK'}
        missing = [s for s in required if s not in completed]
        if missing and 1 < remaining_turns <= len(missing) + 1:
            grid = definitions['calculate_scenarios']
            grid['properties']['symbol']['enum'] = missing
            return {'calculate_scenarios': grid}
    findings = definitions["submit_findings"]
    findings["properties"]["objections"]["maxItems"] = 4 if task["role"] == "challenger" else 0
    if task['role'] == 'challenger':
        condition = findings['properties']['review_conditions']['items']['properties']
        condition['kind'] = {'const': 'human_review'}
        for key in ('operator', 'threshold_decimal', 'price_basis', 'expires_at'):
            condition[key] = {'const': None}
    if 'instruments' in findings['properties']:
        symbols = [i['symbol'] for i in state['mandate']['watchlist']]
        for key in ('claims', 'gaps', 'objections', 'shared_exposures'):
            findings['properties'][key]['items']['properties']['symbols']['items']['enum'] = symbols
        if len(symbols) < 2:
            # Shared exposure requires at least two instruments by contract and
            # has no valid value in a single-company mandate.
            del findings['properties']['shared_exposures']
            findings['required'].remove('shared_exposures')
        if task['role'] != 'challenger':
            # A zero-length array constraint is not consistently enforced by
            # providers. Do not offer an action this role cannot perform.
            del findings['properties']['objections']
            findings['required'].remove('objections')
        if 'ask_specialist' in definitions:
            definitions['ask_specialist']['properties']['symbols']['items']['enum'] = symbols
        if task['stage'] not in {'draft', 'final'}:
            # Specialists return scoped evidence/findings. Only Director synthesis
            # constructs the instrument assessments and reconciled role coverage.
            for field in ('instruments', 'role_coverage'):
                del findings['properties'][field]
                findings['required'].remove(field)
        if task['stage'] == 'final' or (task['stage'] == 'draft' and state.get('context_profile') == 'role-research-v1'):
            item = deepcopy(findings['properties']['instruments']['items'])
            del item['properties']['symbol']
            item['required'].remove('symbol')
            findings['properties']['instruments'] = {'type': 'object', 'properties': {symbol: deepcopy(item) for symbol in symbols},
                'required': symbols, 'additionalProperties': False}
    if task["stage"] == "final":
        objections = [o for t in state["tasks"] if t["result"] for o in t["result"]["objections"]]
        for field, id_field, rows in (("dispositions", "objection_id", objections),
                                      ("question_effects", "question_id", state["questions"])):
            item = deepcopy(findings["properties"][field]["items"])
            del item["properties"][id_field]
            item["required"].remove(id_field)
            ids = [row[id_field] for row in rows]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate final response identity")
            findings["properties"][field] = {"type": "object", "properties": {i: deepcopy(item) for i in ids},
                                              "required": ids, "additionalProperties": False}
    return definitions


def restore_action(action, definitions, stage):
    if not isinstance(action, dict) or action.get("tool") not in definitions:
        raise ValueError("Worker selected an unavailable tool")
    Draft202012Validator(definitions[action["tool"]]).validate(action.get("arguments"))
    result = deepcopy(action)
    scoped = 'symbols' in definitions.get('submit_findings', {}).get('properties', {}).get('claims', {}).get('items', {}).get('properties', {})
    if result['tool'] == 'submit_findings' and 'objections' not in definitions['submit_findings']['properties']:
        result['arguments']['objections'] = []
    if result['tool'] == 'submit_findings' and scoped and 'shared_exposures' not in definitions['submit_findings']['properties']:
        result['arguments']['shared_exposures'] = []
    if (result['tool'] == 'submit_findings' and scoped and stage not in {'draft', 'final'} and
            'instruments' not in definitions['submit_findings']['properties']):
        result['arguments'].update(instruments=[], role_coverage=[])
    if stage in {'draft', 'final'} and result["tool"] == "submit_findings":
        if isinstance(result['arguments'].get('instruments'), dict):
            result['arguments']['instruments'] = [{'symbol': symbol, **value} for symbol, value in result['arguments']['instruments'].items()]
    if stage == "final" and result["tool"] == "submit_findings":
        for field, id_field in (("dispositions", "objection_id"), ("question_effects", "question_id")):
            result["arguments"][field] = [{id_field: identity, **value} for identity, value in result["arguments"][field].items()]
    return result
