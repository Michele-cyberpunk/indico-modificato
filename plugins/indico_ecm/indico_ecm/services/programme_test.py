# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The cases these rules are allowed to get right.

The texts are the ones the Cyberbrain event manager tests its own extractor
with, so a regression here is a regression against the documents the provider
actually files.
"""

from datetime import date

import pytest

from indico_ecm.services.programme import (find_credits, find_dates, find_event_name, find_participants,
                                           find_people, find_times, find_venue, is_provider_line,
                                           is_shouting, read)


PROGETTO_FORMATIVO = '''SUMMEET SRL - ID 604
PROGETTO FORMATIVO
IMP-ACT: Intestinal Microbiota & Pain - ACT
Data: 9 maggio 2026
Sede: Hotel Europa, 04100 - Latina (LT)
Crediti ECM: 4
Numero partecipanti: 30
Tipologia: Residenziale (RES)
Orario: 09:00 - 17:30
Responsabile Scientifico: Prof. Loris Riccardo Lopetuso
Faculty: Dott. Edoardo Savarino'''

CON_PROGRAMMA = '''EVENTO FORMATIVO
Titolo Inventato Di Prova
Responsabile Scientifico: Ottavia Vermiglio, Pordenone
Faculty: 4 Relatori (Cardiologo, Nefrologo)

PROGRAMMA SCIENTIFICO

09:00\tApertura Segreteria e Registrazione Partecipanti
09:30\tBenvenuto e Saluti istituzionali
\tGherardo Bislacchi, Nives Quartullo
10:00\tPrima relazione sul tema in oggetto
\tCardiologo - Ippolito Sfregacci
10:30\tSeconda relazione sul tema in oggetto
\tNefrologa – Dott.ssa Melania Trabucchi
11:00\tPERCORSO GRUPPO DI MIGLIORAMENTO
11:30\tChiusura dell'incontro'''


# --- the title ---------------------------------------------------------------

def test_the_title_comes_from_under_the_header():
    assert find_event_name(PROGETTO_FORMATIVO)[0] == 'IMP-ACT: Intestinal Microbiota & Pain - ACT'


def test_the_provider_is_never_the_title():
    text = '''SUMMEET SRL - ID 604
PROGETTO FORMATIVO
SUMMEET SRL
IMP-ACT Inflammatory Mushrooms and Advanced Cardiac Therapies
Data: 9 maggio 2026'''
    name = find_event_name(text)[0]
    assert name == 'IMP-ACT Inflammatory Mushrooms and Advanced Cardiac Therapies'
    assert 'SUMMEET' not in name


def test_the_provider_is_skipped_even_without_the_header():
    text = '''SUMMEET SRL
Congresso Nazionale di Cardiologia 2026
Data: 10 giugno 2026'''
    assert find_event_name(text)[0] == 'Congresso Nazionale di Cardiologia 2026'


def test_a_subtitle_on_the_next_line_is_joined_with_a_colon():
    text = '''PROGETTO FORMATIVO
ONCO-TREND
Innovazioni in oncologia di precisione
Provider ECM: SUMMEET SRL - ID 604
Data: 10 giugno 2026'''
    assert find_event_name(text)[0] == 'ONCO-TREND: Innovazioni in oncologia di precisione'


def test_a_label_under_the_title_is_not_a_subtitle():
    text = '''PROGETTO FORMATIVO
Congresso Nazionale di Cardiologia 2026
Provider ECM: SUMMEET SRL - ID 604
Data: 10 giugno 2026'''
    assert find_event_name(text)[0] == 'Congresso Nazionale di Cardiologia 2026'


def test_a_section_heading_is_never_the_title():
    text = '''PROGRAMMA SCIENTIFICO
09:00\tPrima relazione
10:00\tChiusura'''
    assert find_event_name(text)[0] == ''


def test_a_title_written_in_capitals_is_still_a_title():
    # `FOCUS GROUP ON LDL 4.0` is a real one: capitals cannot disqualify a title.
    text = '''PROGETTO FORMATIVO
FOCUS GROUP ON LDL 4.0
Fattore causale di malattia cardiovascolare
Data: 10 giugno 2026'''
    assert find_event_name(text)[0] == ('FOCUS GROUP ON LDL 4.0: '
                                        'Fattore causale di malattia cardiovascolare')


@pytest.mark.parametrize('line', (
    'SUMMEET SRL - ID 604',
    'Provider ECM: SUMMEET SRL',
    'Farmaceutica XYZ S.p.A.',
))
def test_provider_lines_are_recognised(line):
    assert is_provider_line(line)


def test_a_scientific_title_is_not_taken_for_a_provider():
    assert not is_provider_line('IMP-ACT: Intestinal Microbiota & Pain - ACT')


# --- dates -------------------------------------------------------------------

def test_an_italian_date_is_read():
    start, end, source = find_dates('Data: 9 maggio 2026')
    assert (start, end) == (date(2026, 5, 9), None)
    assert source == 'Data: 9 maggio 2026'


@pytest.mark.parametrize(('text', 'first', 'last'), (
    ('Data: dal 15 al 16 ottobre 2026', date(2026, 10, 15), date(2026, 10, 16)),
    ('Data: 19 e 20 febbraio 2026', date(2026, 2, 19), date(2026, 2, 20)),
    ('Data: 15-16 ottobre 2026', date(2026, 10, 15), date(2026, 10, 16)),
))
def test_the_three_forms_of_a_range_are_read(text, first, last):
    start, end, _ = find_dates(text)
    assert (start, end) == (first, last)


def test_a_numeric_date_still_works():
    assert find_dates('Data: 15/09/2026')[0] == date(2026, 9, 15)
    assert find_dates('Data: 2026-09-15')[0] == date(2026, 9, 15)


def test_a_document_without_a_date_says_so():
    assert find_dates('Nessuna data qui') == (None, None, '')


# --- venue, credits, participants, times -------------------------------------

def test_the_city_is_read_from_the_postcode():
    venue, city, province, _ = find_venue('Sede: Hotel Europa, 04100 - Latina (LT)')
    assert (venue, city, province) == ('Hotel Europa', 'Latina', 'LT')


def test_the_city_is_read_from_the_tail_when_there_is_no_postcode():
    venue, city, _, _ = find_venue('Sede: Centro Congressi, Milano')
    assert (venue, city) == ('Centro Congressi', 'Milano')


def test_credits_and_participants_are_read():
    assert find_credits('Crediti ECM: 4')[0] == '4'
    assert find_participants('Numero partecipanti: 30')[0] == '30'


def test_a_composite_audience_is_summed():
    # "1 Coordinator + 4 Expert Opinion" is five people, not one.
    assert find_participants('Destinatari: 1 Coordinator + 4 Expert Opinion')[0] == '5'


def test_the_declared_times_are_read():
    assert find_times('Orario: 09:00 - 17:30')[:2] == ('09:00', '17:30')


def test_without_a_declared_line_the_times_come_from_the_timetable():
    # Registration and closing included: that is the span the office writes down.
    assert find_times(CON_PROGRAMMA)[:2] == ('09:00', '11:30')


# --- the people --------------------------------------------------------------

def test_the_people_named_on_labelled_lines():
    people = {person.name: person for person in find_people(PROGETTO_FORMATIVO)}
    assert set(people) == {'Loris Riccardo Lopetuso', 'Edoardo Savarino'}
    assert people['Loris Riccardo Lopetuso'].title == 'professor'
    assert people['Edoardo Savarino'].title == 'doctor'


def test_a_role_word_after_a_name_is_not_part_of_it():
    people = find_people('Responsabile Scientifico: Prof. Loris Riccardo Lopetuso')
    assert people[0].name == 'Loris Riccardo Lopetuso'


def test_where_someone_works_is_not_a_second_person():
    people = find_people('Responsabile Scientifico: Ottavia Vermiglio, Pordenone')
    assert [person.name for person in people] == ['Ottavia Vermiglio']


def test_the_people_written_under_the_sessions():
    names = [person.name for person in find_people(CON_PROGRAMMA)]
    for expected in ('Gherardo Bislacchi', 'Nives Quartullo',
                     'Ippolito Sfregacci', 'Melania Trabucchi'):
        assert expected in names


def test_the_role_written_before_the_dash_is_kept():
    people = {person.name: person for person in find_people(CON_PROGRAMMA)}
    assert people['Ippolito Sfregacci'].role == 'Cardiologo'
    assert people['Melania Trabucchi'].role == 'Nefrologa'
    assert people['Melania Trabucchi'].title == 'doctor'


def test_a_session_heading_in_capitals_is_not_a_speaker():
    names = [person.name for person in find_people(CON_PROGRAMMA)]
    assert 'PERCORSO GRUPPO DI MIGLIORAMENTO' not in names
    assert not any(name.isupper() for name in names)


def test_a_lone_line_with_no_role_is_a_module_title_and_not_a_person():
    text = '''PROGRAMMA SCIENTIFICO
09:00\tPrima relazione
\tDisease Modifying Treatment
10:00\tChiusura dell'incontro'''
    assert [person.name for person in find_people(text)] == []


@pytest.mark.parametrize(('line', 'shouting'), (
    ('PERCORSO GRUPPO DI MIGLIORAMENTO', True),
    ('Mario Rossi', False),
    ('IMP-ACT', True),
    ('', False),
))
def test_capitals_are_detected(line, shouting):
    assert is_shouting(line) is shouting


# --- everything together ------------------------------------------------------

def test_a_whole_progetto_formativo_is_read():
    result = read(PROGETTO_FORMATIVO)
    assert result.event_name == 'IMP-ACT: Intestinal Microbiota & Pain - ACT'
    assert result.start_date == date(2026, 5, 9)
    assert (result.venue, result.city, result.province) == ('Hotel Europa', 'Latina', 'LT')
    assert (result.credits, result.participants) == ('4', '30')
    assert (result.start_time, result.end_time) == ('09:00', '17:30')
    assert len(result.people) == 2


def test_every_value_carries_the_line_it_was_read_from():
    result = read(PROGETTO_FORMATIVO)
    assert result.evidence['event_name'] == 'IMP-ACT: Intestinal Microbiota & Pain - ACT'
    assert result.evidence['event_date'] == 'Data: 9 maggio 2026'
    assert result.evidence['venue'] == 'Sede: Hotel Europa, 04100 - Latina (LT)'
    assert result.evidence['credits'] == 'Crediti ECM: 4'
