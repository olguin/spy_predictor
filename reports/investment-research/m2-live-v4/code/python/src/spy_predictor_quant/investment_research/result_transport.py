"""Exact identity maps on final wire output; semantic judgments are never repaired."""
from copy import deepcopy

from jsonschema import Draft202012Validator


def tool_schemas(base, task, state, remaining_turns):
    definitions = {k: deepcopy(v) for k, v in base.items() if k in task["permitted_tools"]}
    if remaining_turns <= 1:
        definitions = {"submit_findings": definitions["submit_findings"]}
    findings = definitions["submit_findings"]
    findings["properties"]["objections"]["maxItems"] = 4 if task["role"] == "challenger" else 0
    if 'instruments' in findings['properties']:
        symbols = [i['symbol'] for i in state['mandate']['watchlist']]
        for key in ('claims', 'gaps', 'objections', 'shared_exposures'):
            findings['properties'][key]['items']['properties']['symbols']['items']['enum'] = symbols
        if 'ask_specialist' in definitions:
            definitions['ask_specialist']['properties']['symbols']['items']['enum'] = symbols
        if task['stage'] == 'final':
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
    if stage == "final" and result["tool"] == "submit_findings":
        if isinstance(result['arguments'].get('instruments'), dict):
            result['arguments']['instruments'] = [{'symbol': symbol, **value} for symbol, value in result['arguments']['instruments'].items()]
        for field, id_field in (("dispositions", "objection_id"), ("question_effects", "question_id")):
            result["arguments"][field] = [{id_field: identity, **value} for identity, value in result["arguments"][field].items()]
    return result
