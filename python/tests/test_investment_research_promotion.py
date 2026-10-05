"""Promotion identity and actual worker routing; no provider calls."""
from copy import deepcopy
import shutil

import pytest

from spy_predictor_quant.market_archive import content_hash
from spy_predictor_quant.investment_research import profiles
from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.workspace import QUESTION, mandate_for


def test_new_workspace_run_freezes_reviewed_prompts_and_settings(tmp_path):
    mandate = mandate_for(QUESTION)
    original = deepcopy(mandate)
    c = Controller(tmp_path)
    state = c.create(mandate)
    assert mandate == original
    assert state['prompt_version'] == 'v2.17'
    assert state['context_profile'] == 'role-research-v1'
    assert state['stage_turn_limits']['draft'] == 3
    assert state['mandate']['runtime']['reasoning_effort'] == 'high'
    assert state['mandate']['runtime']['max_output_tokens'] == 10000
    for role, record in state['promotion']['roles'].items():
        assert content_hash(state['prompts'][role]) == record['prompt_sha256']
        task = c.add_task(state, role, 'research', 'Synthetic dispatch check')
        expected = 'openai-codex/gpt-5.6-sol' if role == 'technical' else mandate['runtime']['model']
        assert task['model'] == task['runtime']['model'] == expected


def test_technical_worker_receives_the_promoted_model_and_actual_limits(tmp_path):
    captured = []
    def worker(request, runtime, timeout):
        captured.append((request, deepcopy(runtime)))
        raise LookupError('Synthetic capture; no provider dispatch')
    c = Controller(tmp_path, worker)
    state = c.create(mandate_for(QUESTION))
    task = c.add_task(state, 'technical', 'research', 'Synthetic technical request')
    with pytest.raises(LookupError, match='Synthetic capture'):
        c.execute_task(state, task)
    request, runtime = captured[0]
    assert request['runtime'] == runtime == task['runtime']
    assert runtime['model'] == 'openai-codex/gpt-5.6-sol'
    assert runtime['reasoning_effort'] == 'high'
    assert runtime['max_output_tokens'] == 10000
    assert request['instructions'] == state['prompts']['technical']


def test_explicit_baseline_selection_keeps_its_registered_model_and_settings(tmp_path):
    mandate = mandate_for(QUESTION)
    mandate['runtime'].update(reasoning_effort='medium', max_output_tokens=6000)
    state = Controller(tmp_path).create(mandate, prompt_version='v2.7')
    assert state['prompt_version'] == 'v2.7'
    assert 'promotion' not in state
    assert state['mandate'] == mandate
    assert all(t['runtime'] == mandate['runtime'] for t in state['tasks'])


@pytest.mark.parametrize('filename', ['technical.md', 'tools.json'])
def test_edited_promoted_artifacts_are_rejected(tmp_path, monkeypatch, filename):
    source = profiles.ROOT / 'prompts/investment-research/v2.17'
    target = tmp_path / 'prompts/investment-research/v2.17'
    shutil.copytree(source, target)
    path = target / filename
    path.write_text(path.read_text() + '\nChanged after promotion')
    monkeypatch.setattr(profiles, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='integrity mismatch'):
        profiles.promoted_profile()
