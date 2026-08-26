# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_agents.governance.llm_guard import ForbiddenClaim, check, check_fields, check_prose, find_claims


GOOD = ('Gentile Dottoressa, le confermiamo la partecipazione al corso. '
        "I crediti formativi le saranno comunicati dalla segreteria a chiusura dell'evento.")


def test_prose_that_points_at_the_data_is_allowed():
    assert check_prose(GOOD) == GOOD


@pytest.mark.parametrize('text', (
    'Il corso assegna 9 crediti ECM ai partecipanti.',
    'Crediti ECM: 12',
    'Le comunichiamo che ha maturato 9 crediti.',
    "L'attestato n. ECM-2026-000431 è stato emesso.",
    'Il partecipante è idoneo ai crediti.',
    'Il codice fiscale RSSMRA80A01H501U risulta corretto.',
))
def test_prose_that_states_a_regulated_value_is_refused(text):
    with pytest.raises(ForbiddenClaim):
        check_prose(text)


def test_the_refusal_quotes_what_the_model_said():
    with pytest.raises(ForbiddenClaim, match='9 crediti'):
        check_prose('Il corso assegna 9 crediti ECM.')


def test_the_refusal_says_why_rather_than_only_that():
    with pytest.raises(ForbiddenClaim, match='motore deterministico'):
        check_prose('Crediti: 9')


def test_nothing_is_silently_stripped():
    # a repaired sentence would no longer say what its author meant, and would
    # hide that the model went somewhere it should not
    with pytest.raises(ForbiddenClaim, match='rifiutata'):
        check_prose('Il corso assegna 9 crediti ECM.')


def test_findings_do_not_repeat_the_same_complaint():
    findings = find_claims('9 crediti oggi, 12 crediti domani')
    assert len({finding.what for finding in findings}) == len(findings)


def test_structured_fields_a_model_may_not_decide_are_refused():
    with pytest.raises(ForbiddenClaim, match='credits'):
        check_fields({'summary': 'va bene', 'credits': 9})
    with pytest.raises(ForbiddenClaim, match='codice_fiscale'):
        check_fields({'codice_fiscale': 'RSSMRA80A01H501U'})


def test_harmless_fields_pass():
    payload = {'subject': 'Conferma iscrizione', 'body': GOOD}
    assert check_fields(payload) is payload


def test_check_looks_inside_the_values_too():
    with pytest.raises(ForbiddenClaim):
        check({'subject': 'Conferma', 'body': 'Le confermiamo 9 crediti ECM.'})


def test_check_accepts_a_whole_safe_answer():
    payload = {'subject': 'Conferma iscrizione', 'body': GOOD}
    assert check(payload) is payload


def test_check_handles_a_bare_string():
    assert check(GOOD) == GOOD


def test_an_empty_draft_is_not_a_violation():
    assert check_prose('') == ''
    assert find_claims(None) == ()
