# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import date

import pytest

from indico_ecm.services.deliverables import Deliverable, DeliverableState
from indico_ecm.services.event_schema import (EVENT_FIELDS, Destination, INVITATION_FIELDS, fields_for,
                                              index_fields, required_keys)
from indico_ecm.services.legacy_import import (import_archive, import_event, import_invitation, import_reminder,
                                               parse_bool, parse_date, parse_number)


LEGACY_EVENT = {
    'nomeEvento': 'Cardio Update 2026',
    'cliente': 'Acme Pharma',
    'dataEvento1': '2026-09-15',
    'dataEvento2': '2026-09-16',
    'citta': 'Milano',
    'codiceEvento': '0915_CARD',
    'orario': '09:00-17:00',
    'luogo': 'Hotel Excelsior',
    'codieAgenas': 'AG-12345',
    'numeroPartecipanti': '120',
    'creditiEvento': '9',
    'tipoEvento': 'RES',
    'accreditamento': 'Sì',
    'contrattiSponsor': 'Sì',
    'grafica': 'No',
    'letteraIncarico': '',
    'slideKit': 'No',
    'consuntivo': 'No',
    'uecm': 'Laura',
    'relatore1': 'Mario Rossi',
    'mail1': 'm.rossi@example.org',
    'relatore2': 'Anna Verdi',
    'mail2': 'a.verdi@example.org',
    'accreditationTo': 'ecm@example.org',
    'note': 'evento pilota',
}


# --- schema -----------------------------------------------------------------

def test_every_yes_no_column_maps_to_a_deliverable():
    mapping = index_fields(EVENT_FIELDS).deliverable_keys
    assert mapping['accreditamento'] is Deliverable.accreditation
    assert mapping['letteraIncarico'] is Deliverable.assignment_letter
    assert mapping['stampaGrafiche'] is Deliverable.graphics_printing
    # 17 yes/no columns in the legacy table; the checklist adds invitations and faculty documents
    assert len(mapping) == 17
    assert set(Deliverable) - set(mapping.values()) == {Deliverable.invitations, Deliverable.faculty_documents}


def test_deliverable_targets_are_all_valid():
    for legacy_field in fields_for(Destination.deliverable):
        assert Deliverable(legacy_field.target)


def test_required_columns_match_the_legacy_table():
    assert set(required_keys()) == {'nomeEvento', 'cliente', 'dataEvento1', 'citta', 'codiceEvento',
                                    'orario', 'luogo', 'numeroPartecipanti', 'accreditamento', 'tipoEvento'}


def test_field_keys_are_unique():
    keys = [item.key for item in EVENT_FIELDS]
    assert len(keys) == len(set(keys))
    invitation_keys = [item.key for item in INVITATION_FIELDS]
    assert len(invitation_keys) == len(set(invitation_keys))


# --- parsing ----------------------------------------------------------------

@pytest.mark.parametrize(('value', 'expected'), (
    ('Sì', True),
    ('si', True),
    ('SI', True),
    ('x', True),
    ('No', False),
    ('n/a', False),
    ('', None),
    (None, None),
))
def test_parse_bool(value, expected):
    assert parse_bool(value) is expected


@pytest.mark.parametrize(('value', 'expected'), (
    ('2026-09-15', date(2026, 9, 15)),
    ('15/09/2026', date(2026, 9, 15)),
    ('15-09-2026', date(2026, 9, 15)),
    ('15.09.2026', date(2026, 9, 15)),
    ('2026-09-15T10:00:00Z', date(2026, 9, 15)),
    ('domani', None),
    ('', None),
))
def test_parse_date(value, expected):
    assert parse_date(value) == expected


@pytest.mark.parametrize(('value', 'expected'), (
    ('120', 120.0),
    ('1.234,50', None),
    ('9,5', 9.5),
    ('€ 250', 250.0),
    ('', None),
    ('molti', None),
))
def test_parse_number(value, expected):
    assert parse_number(value) == expected


# --- events -----------------------------------------------------------------

def test_import_event_reads_the_core_fields():
    imported = import_event(LEGACY_EVENT)
    assert imported.title == 'Cardio Update 2026'
    assert imported.start_date == date(2026, 9, 15)
    assert imported.end_date == date(2026, 9, 16)
    assert imported.event_code == '0915_CARD'
    assert imported.credits == 9
    assert imported.max_participants == 120
    assert imported.activity_code == 'AG-12345'
    assert imported.accreditation_contact == 'Laura'


def test_import_event_maps_the_checklist():
    deliverables = import_event(LEGACY_EVENT).deliverables
    assert deliverables[Deliverable.accreditation] is DeliverableState.done
    assert deliverables[Deliverable.sponsor_contract] is DeliverableState.done
    assert deliverables[Deliverable.graphics] is DeliverableState.todo
    # an empty cell is not the same as an explicit No, but neither is done
    assert deliverables[Deliverable.assignment_letter] is DeliverableState.todo
    assert len(deliverables) == 17


def test_import_event_collects_faculty_slots():
    faculty = import_event(LEGACY_EVENT).faculty
    assert [person['name'] for person in faculty] == ['Mario Rossi', 'Anna Verdi']
    assert faculty[0]['email'] == 'm.rossi@example.org'


def test_import_event_generates_a_missing_folder_name():
    imported = import_event(LEGACY_EVENT)
    assert imported.folder_name.startswith('0915-16 CARDIO ')
    assert 'ACME-PHARMA' in imported.folder_name


def test_import_event_keeps_an_existing_folder_name():
    row = LEGACY_EVENT | {'nomeCartella': 'CARTELLA STORICA'}
    assert import_event(row).folder_name == 'CARTELLA STORICA'


def test_import_event_reports_missing_required_fields():
    issues = []
    import_event({'nomeEvento': 'Solo il titolo'}, row_number=3, issues=issues)
    reported = {issue.field for issue in issues}
    assert 'cliente' in reported
    assert 'dataEvento1' in reported
    assert all(issue.row == 3 for issue in issues)


def test_import_event_reports_unparseable_dates():
    issues = []
    import_event(LEGACY_EVENT | {'dataEvento1': 'il prossimo autunno'}, issues=issues)
    assert any(issue.field == 'dataEvento1' and 'data' in issue.message for issue in issues)


def test_import_event_keeps_operational_fields():
    operations = import_event(LEGACY_EVENT).operations
    assert operations['accreditation_to'] == 'ecm@example.org'
    assert operations['notes'] == 'evento pilota'
    assert operations['schedule_text'] == '09:00-17:00'


# --- invitations and reminders ----------------------------------------------

def test_import_invitation_builds_the_row_and_the_costs():
    invitation, costs = import_invitation({
        'nomeOspedale': 'Ospedale San Raffaele', 'numeroMedici': '3', 'ruolo': 'Relatore',
        'reparto': 'Cardiologia', 'nomeEvento': 'Cardio Update', 'luogoEvento': 'Milano',
        'costoCamera': '120', 'costoCityTax': '5', 'viaggio': '80', 'numeroPranzi': '2',
    })
    assert invitation.physician_count == 3
    assert invitation.department == 'Cardiologia'
    assert costs['costoCamera'] == 120
    assert costs['numeroPranzi'] == 2


def test_import_invitation_reports_a_missing_count():
    issues = []
    invitation, _costs = import_invitation({'nomeOspedale': 'X'}, row_number=2, issues=issues)
    assert invitation.physician_count == 1
    assert issues[0].field == 'numeroMedici'


def test_import_reminder():
    reminder = import_reminder({'codiceEvento': '0915_CARD', 'mansione': 'Chiamare hotel',
                                'giornoPreavviso': '01/09/2026'})
    assert reminder['remind_on'] == date(2026, 9, 1)
    assert reminder['task'] == 'Chiamare hotel'


def test_import_reminder_reports_a_missing_date():
    issues = []
    import_reminder({'mansione': 'X'}, row_number=1, issues=issues)
    assert issues[0].field == 'giornoPreavviso'


# --- whole archive ----------------------------------------------------------

def test_import_archive_reads_every_section():
    result = import_archive({
        'events': [LEGACY_EVENT],
        'stampaUnioneData': [{'nomeOspedale': 'Policlinico', 'numeroMedici': '2'}],
        'specialReminders': [{'mansione': 'Verificare badge', 'giornoPreavviso': '2026-09-10'}],
    })
    assert len(result.events) == 1
    assert len(result.invitations) == 1
    assert len(result.reminders) == 1
    assert result.ok


def test_import_archive_accepts_the_old_key_name():
    result = import_archive({'knifeData': [{'nomeOspedale': 'Policlinico', 'numeroMedici': '1'}]})
    assert len(result.invitations) == 1


def test_import_archive_collects_issues_without_stopping():
    result = import_archive({'events': [{'nomeEvento': 'Incompleto'}, LEGACY_EVENT]})
    assert len(result.events) == 2
    assert not result.ok
    assert all(issue.row in (1, 2) for issue in result.issues)


def test_empty_archive():
    result = import_archive({})
    assert result.ok
    assert result.events == []
