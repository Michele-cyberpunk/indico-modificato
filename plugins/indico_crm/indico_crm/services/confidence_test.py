# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_crm.services.confidence import (CEILING, WEIGHTS, Band, Proof, band_for, explain, score)


def proof(kind, detail='qualcosa'):
    return Proof(kind=kind, detail=detail)


def test_no_proof_is_not_a_low_score_but_no_band():
    verdict = score([])
    assert verdict.score == pytest.approx(0.0)
    assert verdict.band is None
    assert verdict.rationale == 'Nessuna prova.'


def test_one_identifying_proof_can_verify():
    verdict = score([proof('tax_code_match')])
    assert verdict.band is Band.verified
    assert verdict.identified
    assert verdict.is_writable


def test_sources_combine_without_reaching_certainty():
    one = score([proof('employer_match')]).score
    two = score([proof('employer_match'), proof('web_cited')]).score
    assert two > one
    everything = score([proof(kind) for kind in WEIGHTS if kind != 'contradiction'])
    assert everything.score <= CEILING


def test_corroboration_alone_never_verifies():
    # four weak sources agreeing still do not say *which* person this is
    verdict = score([proof('sponsor_roster'), proof('employer_match'),
                     proof('web_cited'), proof('email_domain')])
    assert verdict.score > 0.85
    assert not verdict.identified
    assert verdict.band is Band.probable
    assert not verdict.is_writable
    assert 'nulla che identifichi la persona' in verdict.rationale


def test_a_contradiction_holds_the_score_down():
    without = score([proof('tax_code_match'), proof('registry_confirms')])
    assert without.band is Band.verified
    with_clash = score([proof('tax_code_match'), proof('registry_confirms'),
                        proof('contradiction', "l'albo riporta un'altra disciplina")])
    assert with_clash.band is Band.possible
    assert with_clash.contradicted
    assert with_clash.rationale.startswith('In sospeso:')
    assert not with_clash.is_writable


def test_a_weak_single_source_earns_no_band():
    assert score([proof('name_only')]).band is None


@pytest.mark.parametrize(('value', 'identified', 'expected'), (
    (0.95, True, Band.verified),
    (0.95, False, Band.probable),
    (0.60, True, Band.probable),
    (0.35, True, Band.possible),
    (0.10, True, None),
))
def test_band_floors(value, identified, expected):
    assert band_for(value, identified) is expected


def test_the_rationale_lists_what_was_seen():
    verdict = score([proof('checked_in'), proof('employer_match')])
    # the first label is capitalised, so this comparison ignores case
    assert 'ha firmato la presenza al banco' in verdict.rationale.casefold()
    assert "l'ente di appartenenza coincide" in verdict.rationale


def test_the_rationale_does_not_repeat_a_source_kind():
    verdict = score([proof('web_cited', 'prima fonte'), proof('web_cited', 'seconda fonte')])
    assert verdict.rationale.casefold().count('una fonte web citata lo afferma') == 1


def test_a_proof_needs_a_detail_and_a_known_kind():
    with pytest.raises(ValueError, match='senza dettaglio'):
        Proof(kind='web_cited', detail='   ')
    with pytest.raises(ValueError, match='sconosciuto'):
        Proof(kind='vibes', detail='mi sembra')


def test_confidence_is_the_stored_integer():
    assert score([proof('tax_code_match')]).confidence == 95


def test_explain_carries_the_proofs_and_their_weights():
    payload = explain([proof('tax_code_match', 'RSSMRA80A01H501U sul modulo')])
    assert payload['band'] == 'verified'
    assert payload['writable'] is True
    assert payload['proofs'][0]['identifying'] is True
    assert payload['proofs'][0]['weight'] == pytest.approx(0.95)
    assert 'RSSMRA80A01H501U' in payload['proofs'][0]['detail']
