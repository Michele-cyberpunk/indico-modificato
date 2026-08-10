# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_crm.services.identity_rules import (IdentityCandidate, MatchDecision, is_valid_tax_code,
                                                match_healthcare_professional, match_identity, normalize_code,
                                                normalize_text)


def make(**kwargs):
    return IdentityCandidate(**kwargs)


@pytest.mark.parametrize(('value', 'expected'), (
    ('Città', 'citta'),
    ('  Rossi   Mario ', 'rossi mario'),
    ('DE ANGELIS', 'de angelis'),
    ('', ''),
))
def test_normalize_text(value, expected):
    assert normalize_text(value) == expected


@pytest.mark.parametrize(('value', 'expected'), (
    ('rss mra 80a01 h501 u', 'RSSMRA80A01H501U'),
    ('12345-678', '12345678'),
    ('', ''),
))
def test_normalize_code(value, expected):
    assert normalize_code(value) == expected


@pytest.mark.parametrize(('value', 'expected'), (
    ('RSSMRA80A01H501U', True),
    ('rssmra80a01h501u', True),
    ('RSSMRA80A01H501', False),
    ('12345678901', False),
    ('', False),
))
def test_is_valid_tax_code(value, expected):
    assert is_valid_tax_code(value) is expected


def test_identical_tax_code_is_strong():
    left = make(last_name='Rossi', tax_code='RSSMRA80A01H501U')
    right = make(last_name='Rossi', tax_code='rssmra80a01h501u')
    result = match_identity(left, right)
    assert result.decision is MatchDecision.strong
    assert result.can_auto_merge


def test_different_tax_codes_conflict_even_with_same_email():
    left = make(first_name='Mario', last_name='Rossi', email='m.rossi@asl.it', tax_code='RSSMRA80A01H501U')
    right = make(first_name='Mario', last_name='Rossi', email='m.rossi@asl.it', tax_code='RSSMRA80A01H501X')
    result = match_identity(left, right)
    assert result.decision is MatchDecision.conflict
    assert not result.can_auto_merge


def test_identical_registry_entry_is_strong():
    left = make(last_name='Bianchi', registry_board='OMCeO', registry_region='Lazio', registry_number='12345')
    right = make(last_name='Bianchi', registry_board='omceo', registry_region='lazio', registry_number='1-2345')
    assert match_identity(left, right).decision is MatchDecision.strong


def test_same_name_different_registry_is_a_conflict():
    left = make(first_name='Luca', last_name='Bianchi', registry_board='OMCeO', registry_region='Lazio',
                registry_number='12345')
    right = make(first_name='Luca', last_name='Bianchi', registry_board='OMCeO', registry_region='Lazio',
                 registry_number='99999')
    assert match_identity(left, right).decision is MatchDecision.conflict


def test_different_people_with_different_registries_do_not_match():
    left = make(first_name='Luca', last_name='Bianchi', registry_board='OMCeO', registry_region='Lazio',
                registry_number='12345')
    right = make(first_name='Anna', last_name='Verdi', registry_board='OMCeO', registry_region='Lazio',
                 registry_number='99999')
    assert match_identity(left, right).decision is MatchDecision.none


def test_same_email_and_name_is_probable_not_auto_mergeable():
    left = make(first_name='Anna', last_name='Verdi', email='anna.verdi@example.org')
    right = make(first_name='Anna', last_name='Verdi', email='Anna.Verdi@Example.org')
    result = match_identity(left, right)
    assert result.decision is MatchDecision.probable
    assert not result.can_auto_merge


def test_shared_mailbox_with_different_names_is_only_weak():
    left = make(first_name='Anna', last_name='Verdi', email='info@clinica.it')
    right = make(first_name='Luca', last_name='Bianchi', email='info@clinica.it')
    assert match_identity(left, right).decision is MatchDecision.weak


def test_same_name_same_company_is_weak():
    left = make(first_name='Anna', last_name='Verdi', company_id=7)
    right = make(first_name='Anna', last_name='Verdi', company_id=7)
    assert match_identity(left, right).decision is MatchDecision.weak


def test_no_shared_identifier():
    assert match_identity(make(last_name='Verdi'), make(last_name='Rossi')).decision is MatchDecision.none


def test_hcp_matching_requires_a_regulatory_identifier():
    left = make(first_name='Anna', last_name='Verdi', email='anna.verdi@example.org')
    right = make(first_name='Anna', last_name='Verdi', email='anna.verdi@example.org')
    assert match_healthcare_professional(left, right).decision is MatchDecision.probable


def test_hcp_matching_accepts_tax_code():
    left = make(last_name='Verdi', tax_code='VRDNNA75B41H501K')
    right = make(last_name='Verdi', tax_code='VRDNNA75B41H501K')
    result = match_healthcare_professional(left, right)
    assert result.decision is MatchDecision.strong
    assert result.can_auto_merge


def test_empty_names_never_match_by_name():
    assert match_identity(make(), make()).decision is MatchDecision.none
