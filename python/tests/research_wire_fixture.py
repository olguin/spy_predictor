"""Generate real controller tool envelopes for the offline TypeScript boundary test.

No source acquisition, worker execution, credentials or provider calls.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from spy_predictor_quant.investment_research.contracts import ROOT, WORKER_PROTOCOL
from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.inputs import live_mandate
from spy_predictor_quant.investment_research.result_transport import tool_schemas


def requests():
    base = json.loads((ROOT / 'prompts/investment-research/v2.21/tools.json').read_text())
    companies = ['NVDA', 'MU', 'ANET', 'META', 'AAPL']
    scopes = [companies[:count] for count in range(1, 6)] + [['QQQ'], ['ANET', 'QQQ']]
    rows = []
    with TemporaryDirectory(prefix='research-wire-') as temporary:
        for index, symbols in enumerate(scopes):
            mandate = live_mandate(
                'Assess global forces and conditional outcomes for these stocks.',
                symbols, [5, 21, 63], now=datetime(2026, 10, 2, 18, tzinfo=timezone.utc),
                issuer_fetch=lambda _: {'0': {'ticker': 'AAPL', 'cik_str': 320193, 'title': 'Apple Inc.'}},
            )
            controller = Controller(Path(temporary) / str(index))
            state = controller.create(mandate)
            for role, stage in [('director', 'triage'), ('director', 'draft'),
                                ('challenger', 'review'), ('director', 'final')]:
                controller.add_task(state, role, stage, 'Offline boundary fixture.')
            state['questions'] = [{'question_id': 'question-wire', 'status': 'PROPOSED'}]
            for task in state['tasks']:
                for remaining in sorted({1, task['model_turn_limit']}):
                    rows.append(envelope(state, task, base, remaining, symbols))
                if task['role'] == 'company':
                    required = [w['symbol'] for w in mandate['watchlist'] if w['kind'] == 'company']
                    for done in range(len(required)):
                        variant = deepcopy(task)
                        variant['history'] = [
                            {'action': {'tool': 'calculate_scenarios', 'arguments': {'symbol': symbol}},
                             'result': {'status': 'OK'}} for symbol in required[:done]
                        ]
                        rows.append(envelope(state, variant, base, len(required) - done + 1, symbols))
            triage = next(task for task in state['tasks'] if task['stage'] == 'triage')
            state['questions'][0]['status'] = 'ANSWERED'
            rows.append(envelope(state, triage, base, triage['model_turn_limit'], symbols))
    return rows


def envelope(state, task, base, remaining, symbols):
    return {'label': f"{','.join(symbols)}:{task['role']}:{task['stage']}:{remaining}:{len(task['history'])}",
            'request': {'schema_version': WORKER_PROTOCOL, 'task_id': task['task_id'],
                        'instructions': state['prompts'][task['role']],
                        'runtime': task['runtime'], 'context': {'task': task, 'synthetic': True},
                        'tool_schemas': tool_schemas(base, task, state, remaining)}}


if __name__ == '__main__':
    print(json.dumps(requests()))
