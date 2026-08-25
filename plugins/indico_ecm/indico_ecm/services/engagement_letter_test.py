# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import date

import pytest

from indico_ecm.services.engagement_letter import (amount_in_words, declines_titles, derive, format_amount,
                                                   gender_from_tax_code, gender_from_title, letter_date,
                                                   parse_amount, salutation, split_title, title_abbreviation)


@pytest.mark.parametrize(('raw', 'name', 'title', 'gender'), (
    ('Dott.ssa Laura Rossi', 'Laura Rossi', 'doctor', 'F'),
    ('Dr.ssa Laura Rossi', 'Laura Rossi', 'doctor', 'F'),
    ('Dottoressa Laura Rossi', 'Laura Rossi', 'doctor', 'F'),
    ('Prof.ssa Anna Bianchi', 'Anna Bianchi', 'professor', 'F'),
    ('Dottore Mario Rossi', 'Mario Rossi', 'doctor', 'M'),
    ('Professore Mario Rossi', 'Mario Rossi', 'professor', 'M'),
    ('Dott. Mario Rossi', 'Mario Rossi', 'doctor', ''),
    ('Prof. Mario Rossi', 'Mario Rossi', 'professor', ''),
    ('Sig.ra Elena Verdi', 'Elena Verdi', 'none', 'F'),
    ('Ing. Paolo Neri', 'Paolo Neri', 'none', ''),
    ('Mario Rossi', 'Mario Rossi', 'none', ''),
    ('', '', 'none', ''),
))
def test_a_title_is_separated_from_the_name(raw, name, title, gender):
    assert split_title(raw) == (name, title, gender)


def test_the_feminine_form_is_not_swallowed_by_the_ambiguous_one():
    # `Dott.` matching first would leave "ssa Laura Rossi" behind.
    assert split_title('Dott.ssa Laura Rossi')[0] == 'Laura Rossi'


def test_a_document_that_writes_a_feminine_title_declines_them():
    assert declines_titles('Dott.ssa Laura Rossi, Dott. Mario Rossi')
    assert not declines_titles('Dott. Mario Rossi, Prof. Anna Bianchi')


def test_an_ambiguous_title_only_proves_the_masculine_where_titles_are_declined():
    assert gender_from_title('doctor', '', document_declines=True) == 'M'
    assert gender_from_title('doctor', '', document_declines=False) == ''


def test_an_explicit_form_always_wins():
    assert gender_from_title('doctor', 'F', document_declines=False) == 'F'


def test_no_title_never_implies_a_gender():
    assert gender_from_title('none', '', document_declines=True) == ''


@pytest.mark.parametrize(('tax_code', 'gender'), (
    ('RSSMRA80A01H501U', 'M'),
    ('RSSLRA80A41H501T', 'F'),
    ('rss lra 80a41 h501t', 'F'),
    ('TOOSHORT', ''),
    ('RSSMRA80AXXH501U', ''),
    ('', ''),
))
def test_the_tax_code_says_the_gender(tax_code, gender):
    assert gender_from_tax_code(tax_code) == gender


@pytest.mark.parametrize(('gender', 'title', 'expected'), (
    ('M', 'doctor', 'Egregio Dottore'),
    ('F', 'doctor', 'Gentile Dottoressa'),
    ('M', 'professor', 'Gentile Professore'),
    ('F', 'professor', 'Gentilissima Professoressa'),
    ('M', 'none', 'Egregio'),
    ('F', 'none', 'Gentile'),
    ('', 'doctor', 'Spett.le'),
    ('', 'none', 'Spett.le'),
))
def test_the_salutation_matrix(gender, title, expected):
    assert salutation(gender, title) == expected


def test_an_unknown_gender_produces_no_abbreviation():
    # `Dott.` is the masculine short form, so it must not stand in for "unknown".
    assert title_abbreviation('doctor', '') == ''
    assert title_abbreviation('doctor', 'F') == 'Dott.ssa'
    assert title_abbreviation('professor', 'M') == 'Prof.'


def test_the_letter_date_is_written_out():
    assert letter_date(date(2026, 12, 4)) == '04 Dicembre 2026'
    assert letter_date(date(2026, 1, 31)) == '31 Gennaio 2026'


@pytest.mark.parametrize(('value', 'expected'), (
    (0, 'Zero,00'),
    (1, 'Uno,00'),
    (16, 'Sedici,00'),
    (21, 'Ventuno,00'),
    (28, 'Ventotto,00'),
    (100, 'Cento,00'),
    (200, 'Duecento,00'),
    (800, 'Ottocento,00'),
    (1000, 'Mille,00'),
    (2000, 'Duemila,00'),
    (1500, 'Millecinquecento,00'),
    ('800,50', 'Ottocento,50'),
    ('1.200,00', 'Milleduecento,00'),
))
def test_an_amount_is_spelled_out(value, expected):
    assert amount_in_words(value) == expected


def test_the_elision_only_applies_to_one_and_eight():
    assert amount_in_words(22) == 'Ventidue,00'
    assert amount_in_words(31) == 'Trentuno,00'
    assert amount_in_words(38) == 'Trentotto,00'


@pytest.mark.parametrize(('written', 'expected'), (
    ('800', 800),
    ('800,50', 800.5),
    ('1.234,50', 1234.5),
    (800, 800),
    ('', 0),
    (None, 0),
    ('non un numero', 0),
))
def test_an_amount_is_read_in_italian_notation(written, expected):
    assert float(parse_amount(written)) == expected


def test_an_amount_is_written_in_italian_notation():
    assert format_amount(800) == '800,00'
    assert format_amount(1234.5) == '1234,50'


def test_the_withholding_is_twenty_percent_and_the_net_follows():
    figures = derive(gender='M', title='doctor', fee='800', event_date='15/09/2026')
    assert figures.fee == '800,00'
    assert figures.fee_in_words == 'Ottocento,00'
    assert figures.withholding == '160,00'
    assert figures.net_total == '640,00'
    assert figures.has_fee
    assert figures.year == '2026'


def test_without_a_fee_the_money_fields_stay_empty():
    figures = derive(gender='F', title='professor', fee=0, event_date='2026-09-15')
    assert not figures.has_fee
    assert figures.fee == ''
    assert figures.fee_in_words == ''
    assert figures.withholding == ''
    assert figures.net_total == ''
    assert figures.salutation == 'Gentilissima Professoressa'


def test_a_typed_salutation_overrides_the_matrix():
    figures = derive(gender='M', title='doctor', salutation_override='  Carissimo Mario  ')
    assert figures.salutation == 'Carissimo Mario'


def test_a_blank_override_falls_back_to_the_matrix():
    figures = derive(gender='M', title='doctor', salutation_override='   ')
    assert figures.salutation == 'Egregio Dottore'


def test_the_year_comes_from_the_event_date_when_there_is_one():
    assert derive(event_date='dal 15 al 16 ottobre 2027').year == '2027'
    assert derive(event_date='').year == str(date.today().year)
