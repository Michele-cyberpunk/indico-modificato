# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import time

import pytest

from indico_ecm.services.guests import (Categories, TransferConfig, categorize, extract_guest, find_diet,
                                        find_name, find_pax, group_transfers, import_guest_list, is_header,
                                        merge_guest, oversized_parties)


# --- the rows the legacy regex got wrong --------------------------------------------
# Every case here reproduces a defect of Cyberbrain's `extractWithRegex`, checked
# against the original before being fixed.

def test_an_all_caps_list_still_has_names():
    # `/([A-Z][a-z]+)\s+([A-Z][a-z]+)/` found nothing in the commonest Italian format
    guest = extract_guest('ROSSI MARIO, mario.rossi@asl.it, 3401234567')
    assert guest.first_name == 'Mario'
    assert guest.last_name == 'Rossi'


def test_an_accented_name_is_a_name():
    guest = extract_guest('Niccolò Verdi, niccolo@ospedale.it')
    assert (guest.first_name, guest.last_name) == ('Niccolò', 'Verdi')


def test_a_surname_particle_is_part_of_the_surname():
    guest = extract_guest('Dott. Gian Luca De Angelis, 3391112233')
    assert guest.full_name == 'Gian Luca De Angelis'


def test_a_meal_denied_before_the_word_is_still_denied():
    # "no pranzo" used to count as a lunch, because the denial was only looked
    # for after the word
    guest = extract_guest('Ferri Paolo - no pranzo, solo cena')
    assert not guest.lunch
    assert guest.dinner


def test_a_meal_denied_after_the_word_is_denied_too():
    guest = extract_guest('Ferri Paolo, pranzo: no, cena: sì')
    assert not guest.lunch
    assert guest.dinner


def test_a_one_word_diet_is_not_thrown_away():
    # the capture group was empty because the keyword *was* the value
    assert extract_guest('Bianchi Luca, vegetariano').diet_notes == 'vegetariano'


def test_a_companion_is_a_seat():
    # pax was hardcoded to 1, so the shuttle was booked one seat short
    guest = extract_guest('Neri Sara + 1 accompagnatore, arrivo 09:15')
    assert guest.pax == 2


def test_a_logistics_row_is_not_a_person():
    # "Hotel Excelsior Milano" became a guest called Hotel Excelsior
    guest = extract_guest('Hotel Excelsior Milano, sala congressi')
    assert guest.full_name == ''


def test_a_surname_ending_in_h_is_not_an_arrival_time():
    # `h` unanchored matched the last letter of a surname: `Bosch: 10:30` was
    # read as an arrival when it is a departure
    guest = extract_guest('Bosch Anna, partenza 10:30')
    assert guest.arrival is None
    assert guest.departure == time(10, 30)


# --- reading a row ------------------------------------------------------------------

def test_a_complete_row_is_read_whole():
    guest = extract_guest('Dott.ssa Anna Verdi, anna.verdi@asl.it, +39 340 123 4567, '
                          'arrivo 10:30, partenza 18:00, pranzo, vegetariana', row_number=4)
    assert guest.full_name == 'Anna Verdi'
    assert guest.email == 'anna.verdi@asl.it'
    assert guest.phone.replace(' ', '') == '+393401234567'
    assert guest.arrival == time(10, 30)
    assert guest.departure == time(18, 0)
    assert guest.lunch
    assert guest.diet_notes == 'vegetariana'
    assert guest.row_number == 4


def test_every_value_says_where_it_came_from():
    guest = extract_guest('Rossi Mario, m.rossi@asl.it, arrivo 09:00')
    assert guest.evidence['email'] == 'm.rossi@asl.it'
    assert 'arrivo 09:00' in guest.evidence['arrival']
    assert 'Rossi Mario' in guest.evidence['name']


def test_the_phone_is_not_taken_from_inside_the_email():
    guest = extract_guest('Rossi Mario, mario.rossi1980@asl.it')
    assert guest.phone == ''


def test_own_transport_is_recognised():
    guest = extract_guest('Rossi Mario, viene con mezzi propri, arrivo 09:00')
    assert guest.own_transport


@pytest.mark.parametrize(('text', 'expected'), (
    ('Rossi Mario + 1 accompagnatore', 2),
    ('Rossi Mario, 3 pax', 3),
    ('Rossi Mario pax: 2', 2),
    ('Rossi Mario x2', 2),
    ('Rossi Mario', 1),
))
def test_find_pax(text, expected):
    assert find_pax(text)[0] == expected


@pytest.mark.parametrize(('text', 'expected'), (
    ('Mario Rossi', ('Mario', 'Rossi')),
    ('Rossi Mario', ('Mario', 'Rossi')),
    ('ROSSI Mario', ('Mario', 'Rossi')),
    ('Mario ROSSI', ('Mario', 'Rossi')),
    ('Rossi, Mario', ('Mario', 'Rossi')),
    ('ROSSI MARIO', ('Mario', 'Rossi')),
    ('Prof.ssa Maria Della Rocca', ('Maria', 'Della Rocca')),
    ("Sig. Antonio D'Amico", ('Antonio', "D'Amico")),
    ('Mario', ('', '')),
    ('', ('', '')),
))
def test_find_name(text, expected):
    name = find_name(text)
    assert (name.first, name.last) == expected


def test_an_unrecognisable_order_is_declared_uncertain():
    # neither token is a known given name and nothing marks the surname
    assert not find_name('Bosch Kellner').certain
    # while these are decided by an explicit signal
    assert find_name('Rossi, Mario').certain
    assert find_name('ROSSI Mario').certain
    assert find_name('Mario Rossi').certain


def test_an_uncertain_name_can_be_swapped_in_one_step():
    guest = extract_guest('Bosch Kellner, k@asl.it')
    assert not guest.name_order_certain
    swapped = guest.swapped()
    assert (swapped.first_name, swapped.last_name) == (guest.last_name, guest.first_name)
    assert swapped.name_order_certain


@pytest.mark.parametrize(('text', 'expected'), (
    ('allergia: crostacei', 'crostacei'),
    ('intolleranza al lattosio', 'al lattosio'),
    ('vegano', 'vegano'),
    ('senza glutine', 'senza glutine'),
    ('nessuna nota', ''),
))
def test_find_diet(text, expected):
    assert find_diet(text)[0] == expected


def test_an_empty_row_produces_an_empty_guest():
    guest = extract_guest('')
    assert guest.full_name == ''
    assert not guest.has_contact


# --- reading a whole list -----------------------------------------------------------

LIST = [
    'Nome;Cognome;Email;Telefono;Arrivo;Partenza',
    'ROSSI MARIO, mario.rossi@asl.it, 3401234567, arrivo 09:30, partenza 18:00, pranzo',
    'Dott.ssa Anna Verdi, anna.verdi@asl.it, arrivo 09:45, pranzo, vegetariana',
    'Bianchi Luca - non partecipa',
    '',
    'sala congressi piano terra',
    'Neri Sara + 1 accompagnatore, s.neri@ospedale.it, arrivo 10:10, pranzo, cena',
    'Ferri Paolo, p.ferri@asl.it, mezzi propri, pranzo',
]


def test_the_header_is_recognised_and_skipped():
    assert is_header(LIST[0])
    guests, _rejected = import_guest_list(LIST)
    assert all(guest.full_name != 'Nome Cognome' for guest in guests)


def test_the_list_becomes_guests():
    guests, _rejected = import_guest_list(LIST)
    assert [guest.full_name for guest in guests] == [
        'Mario Rossi', 'Anna Verdi', 'Sara Neri', 'Paolo Ferri']
    assert all(guest.name_order_certain for guest in guests)


def test_every_rejected_row_says_why():
    _guests, rejected = import_guest_list(LIST)
    reasons = {row.reason for row in rejected}
    assert reasons == {'non partecipa', 'riga vuota', 'né un nome né un contatto'}
    assert all(row.row_number for row in rejected)


def test_a_row_with_only_a_contact_is_kept():
    guests, rejected = import_guest_list(['scrivimi@ospedale.it'])
    assert len(guests) == 1
    assert rejected == []


# --- what has to be arranged --------------------------------------------------------

def test_categories_split_the_arrangements():
    guests, _rejected = import_guest_list(LIST)
    categories = categorize(guests)
    assert [guest.full_name for guest in categories.arrivals] == ['Mario Rossi', 'Anna Verdi', 'Sara Neri']
    assert [guest.full_name for guest in categories.own_transport] == ['Paolo Ferri']
    assert categories.no_transfer == ()


def test_own_transport_wins_over_a_stated_time():
    guests = [extract_guest('Rossi Mario, auto propria, arrivo 09:00')]
    categories = categorize(guests)
    assert categories.arrivals == ()
    assert len(categories.own_transport) == 1


def test_covers_count_people_not_rows():
    guests, _rejected = import_guest_list(LIST)
    # Sara Neri brings a companion: four rows asked for lunch, five people eat
    categories = categorize(guests)
    assert len(categories.lunch) == 4
    assert categories.covers['lunch'] == 5
    assert categories.covers['dinner'] == 2


def test_an_empty_list_categorises_to_nothing():
    assert categorize([]) == Categories()


# --- the shuttles -------------------------------------------------------------------

def _guests_at(*times, pax=1):
    return [extract_guest(f'Ospite{index} Cognome{index}, arrivo {moment}, x{pax}')
            for index, moment in enumerate(times, start=1)]


def test_guests_are_grouped_into_time_windows():
    groups = group_transfers(_guests_at('09:05', '09:40', '10:20'), TransferConfig(window=60))
    assert [group.window for group in groups] == ['09:00 - 10:00', '10:00 - 11:00']
    assert [len(group.guests) for group in groups] == [2, 1]


def test_a_full_window_is_split_across_vehicles():
    groups = group_transfers(_guests_at(*['09:10'] * 5), TransferConfig(seats_per_vehicle=2))
    assert len(groups) == 3
    assert [group.pax for group in groups] == [2, 2, 1]
    assert [group.vehicle_number for group in groups] == [1, 2, 3]


def test_a_party_is_never_split_across_vehicles():
    guests = [extract_guest('Rossi Mario, arrivo 09:00, 3 pax'),
              extract_guest('Verdi Anna, arrivo 09:10')]
    groups = group_transfers(guests, TransferConfig(seats_per_vehicle=3))
    assert len(groups) == 2
    assert [group.pax for group in groups] == [3, 1]


def test_the_time_strategy_does_not_split_at_all():
    groups = group_transfers(_guests_at(*['09:10'] * 5), TransferConfig(strategy='time', seats_per_vehicle=2))
    assert len(groups) == 1
    assert groups[0].pax == 5


def test_own_transport_is_never_given_a_seat():
    guests = [extract_guest('Rossi Mario, auto propria, arrivo 09:00')]
    assert group_transfers(guests) == ()


def test_departures_are_grouped_on_their_own_time():
    guests = [extract_guest('Rossi Mario, arrivo 09:00, partenza 18:30')]
    assert group_transfers(guests, arrival=False)[0].window == '18:00 - 19:00'


def test_a_party_larger_than_a_vehicle_is_reported_not_truncated():
    guests = [extract_guest('Rossi Mario, arrivo 09:00, 12 pax')]
    oversized = oversized_parties(guests, TransferConfig(seats_per_vehicle=8))
    assert [guest.full_name for guest in oversized] == ['Mario Rossi']
    # it still gets a run, so nobody disappears from the sheet
    assert group_transfers(guests, TransferConfig(seats_per_vehicle=8))[0].pax == 12


def test_an_impossible_configuration_is_refused():
    with pytest.raises(ValueError, match='finestra oraria'):
        TransferConfig(window=0)
    with pytest.raises(ValueError, match='posti per veicolo'):
        TransferConfig(seats_per_vehicle=0)


def test_a_person_can_correct_what_the_rule_read():
    guest = extract_guest('Hotel Excelsior Milano')
    corrected = merge_guest(guest, first_name='Mario', last_name='Rossi', pax=2)
    assert corrected.full_name == 'Mario Rossi'
    assert corrected.pax == 2
    # the original is untouched: the correction is a new value, not a mutation
    assert guest.full_name == ''
