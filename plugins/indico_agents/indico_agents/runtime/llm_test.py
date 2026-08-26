# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_agents.governance.llm_guard import ForbiddenClaim
from indico_agents.runtime import llm
from indico_agents.runtime.egress import build


class _Settings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key):
        return self.values.get(key)


class _Provider:
    """A stand-in vendor adapter: the shape a real one has to satisfy."""

    name = 'finto'
    host = 'api.modello.example'

    def __init__(self, text='Gentile Dottoressa, le confermiamo la partecipazione.', cost=7):
        self.text = text
        self.cost = cost
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        return llm.Completion(text=self.text, model='finto-1', tokens_in=100, tokens_out=40,
                              cost_cents=self.cost, provider=self.name)


ALLOWLIST = build([('api.modello.example', 'model_provider')])
PROMPT = llm.Prompt(system='Scrivi in italiano.', user="Conferma l'iscrizione.", version='v1')


@pytest.fixture
def registered():
    provider = _Provider()
    llm.register_provider('finto', lambda settings: provider)
    yield provider
    llm._PROVIDERS.pop('finto', None)


def test_with_nothing_configured_the_call_is_unavailable_not_broken():
    with pytest.raises(llm.LLMUnavailable, match='riprovare non serve'):
        llm.resolve(_Settings())


def test_the_absence_is_shaped_like_every_other_missing_source():
    try:
        llm.resolve(_Settings())
    except llm.LLMUnavailable as exc:
        answer = llm.unavailable_result(exc)
    assert answer == {'configured': False, 'ok': False, 'reason': answer['reason']}
    assert answer['configured'] is False


def test_a_provider_named_but_not_installed_says_what_is_available():
    with pytest.raises(llm.LLMUnavailable, match='adapter'):
        llm.resolve(_Settings({'model_provider': 'inesistente'}))


def test_a_provider_off_the_allowlist_cannot_be_used(registered):
    with pytest.raises(llm.LLMUnavailable, match='non è raggiungibile'):
        llm.resolve(_Settings({'model_provider': 'finto'}), allowlist=build([]))


def test_a_configured_and_allowed_provider_answers(registered):
    completion = llm.complete(PROMPT, settings=_Settings({'model_provider': 'finto'}),
                              allowlist=ALLOWLIST)
    assert completion.text.startswith('Gentile')
    assert completion.tokens == 140
    assert registered.calls == 1


def test_the_cost_ceiling_refuses_before_spending(registered):
    with pytest.raises(llm.LLMRefused, match='Tetto di spesa'):
        llm.complete(PROMPT, settings=_Settings({'model_provider': 'finto'}), allowlist=ALLOWLIST,
                     ceiling_cents=50, spent_cents=50)
    # refused before the call, not after the bill
    assert registered.calls == 0


def test_below_the_ceiling_the_call_happens(registered):
    llm.complete(PROMPT, settings=_Settings({'model_provider': 'finto'}), allowlist=ALLOWLIST,
                 ceiling_cents=50, spent_cents=10)
    assert registered.calls == 1


def test_a_draft_that_states_credits_is_refused_after_the_call():
    provider = _Provider(text='Il corso assegna 9 crediti ECM.')
    llm.register_provider('claim', lambda settings: provider)
    try:
        with pytest.raises(ForbiddenClaim):
            llm.complete(PROMPT, settings=_Settings({'model_provider': 'claim'}), allowlist=ALLOWLIST)
    finally:
        llm._PROVIDERS.pop('claim', None)


def test_usage_records_what_was_spent(registered):
    usage = llm.Usage()
    llm.complete(PROMPT, settings=_Settings({'model_provider': 'finto'}), allowlist=ALLOWLIST,
                 usage=usage)
    llm.complete(PROMPT, settings=_Settings({'model_provider': 'finto'}), allowlist=ALLOWLIST,
                 usage=usage)
    assert usage.calls == 2
    assert usage.tokens == 280
    assert usage.cost_cents == 14
    assert usage.by_prompt == {'v1': 2}


def test_the_run_carries_the_model_and_the_bill(registered):
    class _Run:
        model_name = ''
        tokens_used = 0
        cost_cents = 0

    run = _Run()
    llm.complete(PROMPT, settings=_Settings({'model_provider': 'finto'}), allowlist=ALLOWLIST, run=run)
    assert run.model_name == 'finto-1'
    assert run.tokens_used == 140
    assert run.cost_cents == 7


def test_a_prompt_is_versioned_and_hashed():
    assert PROMPT.version == 'v1'
    assert len(PROMPT.fingerprint()) == 16
    assert PROMPT.fingerprint() != llm.Prompt(system='altro', user='altro').fingerprint()


def test_the_default_temperature_is_low_because_this_writes_documents():
    assert llm.Prompt(system='', user='').temperature <= 0.3
