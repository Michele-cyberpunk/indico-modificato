# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import json
from datetime import date

import pytest

from indico_ecm.services.archive import SECTIONS, build, dumps, event_row, filename_for, invitation_row
from indico_ecm.services.deliverables import Deliverable, DeliverableState
from indico_ecm.services.legacy_import import import_archive


@pytest.fixture
def event():
    return {
        'title': 'Cardio Update',
        'event_code': '0116_GDBO',
        'start_date': date(2026, 9, 15),
        'end_date': date(2026, 9, 16),
        'city': 'Milano',
        'venue': 'Hotel Excelsior',
        'sponsor': 'Acme Pharma',
        'activity_format': 'Residenziale',
        'credits': 9,
        'max_participants': 80,
        'activity_code': '604-411727',
        'time_range': '09:00 - 17:30',
        'deliverables': {Deliverable.accreditation: DeliverableState.done},
        'faculty': [{'name': 'Mario Rossi', 'email': 'm@x.it'}],
    }


def test_the_archive_writes_every_field_its_own_importer_requires(event):
    from indico_ecm.services.event_schema import EVENT_FIELDS

    row = event_row(event)
    for field in EVENT_FIELDS:
        if field.required:
            assert row.get(field.key) not in (None, ''), field.key


def test_the_record_uses_the_legacy_keys(event):
    row = event_row(event)
    assert row['nomeEvento'] == 'Cardio Update'
    assert row['dataEvento1'] == '15/09/2026'
    assert row['cliente'] == 'Acme Pharma'
    assert row['codieAgenas'] == '604-411727'


def test_the_checklist_comes_back_as_the_two_words_it_was(event):
    row = event_row(event)
    assert row['accreditamento'] == 'Sì'
    # Everything nobody touched is a No, as in the original table.
    assert row['grafica'] == 'No'


def test_every_checklist_entry_is_written(event):
    """All nineteen, not just the seventeen the legacy table had.

    `invitations` and `faculty_documents` are this platform's own additions and
    get names of their own, so an export loses nothing.
    """
    row = event_row(event)
    written = [key for key in row if row[key] in ('Sì', 'No')]
    assert len(written) == len(list(Deliverable))
    assert 'inviti' in row
    assert 'documentiFaculty' in row


def test_the_faculty_fills_the_five_slots():
    row = event_row({'faculty': [{'name': f'Relatore {n}', 'email': f'r{n}@x.it'} for n in range(1, 8)]})
    assert row['relatore1'] == 'Relatore 1'
    assert row['relatore5'] == 'Relatore 5'
    # The legacy record has five and no more.
    assert 'relatore6' not in row


def test_an_invitation_keeps_its_costs():
    row = invitation_row({'hospital': 'Careggi', 'physician_count': 3,
                          'costs': {'room': '120.00', 'travel': ''}})
    assert row['nomeOspedale'] == 'Careggi'
    assert row['numeroMedici'] == 3
    assert row['room'] == '120.00'
    # Empty costs are left out rather than written as blanks.
    assert 'travel' not in row


def test_the_archive_has_the_three_sections(event):
    archive = build(events=[event], generated_on=date(2026, 8, 25))
    for section in SECTIONS:
        assert section in archive
    assert archive['generatedAt'] == '2026-08-25'


def test_what_is_exported_can_be_imported_again(event):
    """The point of the format: a backup nobody can read back is a copy."""
    archive = build(events=[event])
    result = import_archive(json.loads(dumps(archive).decode('utf-8')))
    assert len(result.events) == 1
    imported = result.events[0]
    assert imported.title == 'Cardio Update'
    assert imported.start_date == date(2026, 9, 15)
    assert imported.credits == 9
    assert imported.deliverables[Deliverable.accreditation] is DeliverableState.done


def test_a_round_trip_reports_no_problems(event):
    archive = build(events=[event])
    result = import_archive(json.loads(dumps(archive).decode('utf-8')))
    assert not result.issues


def test_the_file_is_named_by_the_day():
    assert filename_for(date(2026, 8, 25)) == 'archivio-ecm-20260825.json'
