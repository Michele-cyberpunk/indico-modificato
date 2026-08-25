# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_ecm.services.hotel import (HotelServices, LAYOUT_ROUND_TABLES, LAYOUT_THEATRE, brief_lines,
                                       deduce, dumps, loads)


PROGRAMMA = '''PROGRAMMA SCIENTIFICO
09:00 Registrazione partecipanti
10:30 Coffee break
13:00 Light lunch
15:00 Tavola rotonda con i relatori
18:00 Aperitivo di chiusura'''


def test_the_services_are_read_from_the_programme():
    services = deduce(PROGRAMMA)
    assert services.registration_desk
    assert services.coffee_break
    assert services.lunch
    assert services.aperitif
    assert not services.technical_support


@pytest.mark.parametrize(('text', 'expected'), (
    ('Coffee break alle 11', 'coffee_break'),
    ('Pausa caffè alle 11', 'coffee_break'),
    ('Light lunch in terrazza', 'lunch'),
    ('Pranzo a buffet', 'lunch'),
    ('Aperitivo di chiusura', 'aperitif'),
    ('Brindisi finale', 'aperitif'),
    ('Accredito partecipanti', 'registration_desk'),
    ('Check-in dalle 8:30', 'registration_desk'),
    ('Assistenza tecnica per tutta la giornata', 'technical_support'),
))
def test_each_keyword_of_the_original(text, expected):
    assert getattr(deduce(text), expected)


@pytest.mark.parametrize('text', (
    'Tavola rotonda con i relatori',
    'Discussione interattiva fra i partecipanti',
    'Percorso GDM',
    'Grand round mattutino',
))
def test_a_discussion_needs_tables_not_rows(text):
    # Seating people in rows for a round table is the mistake this avoids.
    assert deduce(text).layout == LAYOUT_ROUND_TABLES


def test_without_a_reason_the_room_stays_in_rows():
    assert deduce('Sessione plenaria con relazioni').layout == LAYOUT_THEATRE
    assert deduce('').layout == LAYOUT_THEATRE


def test_catering_is_true_when_anything_is_served():
    assert deduce('Coffee break').catering
    assert not deduce('Sessione plenaria').catering


def test_the_times_are_carried_through():
    services = deduce(PROGRAMMA, start_time='09:00', end_time='18:30')
    assert (services.start_time, services.end_time) == ('09:00', '18:30')


def test_it_survives_a_round_trip_through_the_operations_record():
    services = deduce(PROGRAMMA, start_time='09:00', end_time='18:30')
    assert loads(dumps(services)) == services


@pytest.mark.parametrize('raw', ('', None, '{rotto', '[]', 'null'))
def test_an_unreadable_value_falls_back_instead_of_raising(raw):
    assert loads(raw) == HotelServices()


def test_an_unknown_field_is_ignored_rather_than_crashing():
    assert loads('{"layout": "Platea", "campo_inventato": 1}') == HotelServices()


def test_the_brief_lists_only_what_was_asked_for():
    lines = brief_lines(deduce(PROGRAMMA, start_time='09:00', end_time='18:30'))
    assert lines[0] == 'Allestimento sala: Tavoli riuniti'
    assert 'Orario: 09:00 - 18:30' in lines
    assert 'Coffee break' in lines
    assert 'Assistenza tecnica per tutta la durata' not in lines


def test_a_brief_without_times_does_not_print_an_empty_line():
    lines = brief_lines(deduce('Coffee break'))
    assert all(line.strip() for line in lines)
    assert not any(line.startswith('Orario') for line in lines)
