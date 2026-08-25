# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Taking the whole archive back out.

The counterpart of `legacy_import`: the same JSON shape, so what this writes can
be read by `import_archive` and by the previous event manager. That is the point
of exporting at all — an archive nobody can read back is a copy, not a backup.

The keys are the legacy ones (`nomeEvento`, `dataEvento1`, `stampaUnioneData`),
because they are what the format is, not what we would name them today.

Pure functions, no Indico imports: the caller gathers the records.
"""

import json
from datetime import date, datetime

from indico_ecm.services.deliverables import Deliverable, DeliverableState
from indico_ecm.services.event_schema import EVENT_FIELDS, Destination, index_fields


#: The three sections of an archive, in the order the importer reads them
SECTIONS = ('events', 'stampaUnioneData', 'specialReminders')

#: Legacy value of a yes/no column
YES, NO = 'Sì', 'No'

#: deliverable -> the yes/no column it came from, the reverse of `index_fields`
_DELIVERABLE_KEYS = {deliverable: key
                     for key, deliverable in index_fields().deliverable_keys.items()}

#: The two checklist entries this platform added, which the legacy table never
#: had. They are written under names of their own so an export loses nothing;
#: the old importer ignores keys it does not know, and ours reads them back.
EXTRA_DELIVERABLE_KEYS = {
    Deliverable.invitations: 'inviti',
    Deliverable.faculty_documents: 'documentiFaculty',
}

_OPERATIONS_KEYS = {field.target: field.key
                    for field in EVENT_FIELDS
                    if field.destination is Destination.operations and field.target}


def _day(value):
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime('%d/%m/%Y') if isinstance(value, date) else ''


def _flag(state):
    """A checklist state, back in the two words the archive uses."""
    return YES if state is DeliverableState.done else NO


def event_row(event):
    """One event, as the legacy record.

    `event` is the plain object the caller assembled: title, dates, the
    accreditation figures, the checklist states and the operations fields.
    """
    row = {
        'nomeEvento': event.get('title', ''),
        'codiceEvento': event.get('event_code', ''),
        'dataEvento1': _day(event.get('start_date')),
        'dataEvento2': _day(event.get('end_date')),
        'citta': event.get('city', ''),
        'luogo': event.get('venue', ''),
        'cliente': event.get('sponsor', ''),
        'tipoEvento': event.get('activity_format', ''),
        'creditiEvento': event.get('credits', ''),
        'numeroPartecipanti': event.get('max_participants', ''),
        'codieAgenas': event.get('activity_code', ''),
        'uecm': event.get('accreditation_contact', ''),
        'nomeCartella': event.get('folder_name', ''),
        'note': event.get('notes', ''),
        # Required by the importer: writing an archive that fails its own reader
        # would defeat the point of the format.
        'orario': event.get('time_range', ''),
    }

    states = event.get('deliverables') or {}
    for deliverable in Deliverable:
        key = _DELIVERABLE_KEYS.get(deliverable) or EXTRA_DELIVERABLE_KEYS.get(deliverable)
        if key:
            row[key] = _flag(states.get(deliverable, DeliverableState.todo))

    operations = event.get('operations') or {}
    for target, key in _OPERATIONS_KEYS.items():
        value = operations.get(target)
        if value not in (None, ''):
            row[key] = value

    for slot, person in enumerate(event.get('faculty') or (), start=1):
        if slot > 5:
            # The legacy record has five slots and no more.
            break
        row[f'relatore{slot}'] = person.get('name', '')
        row[f'mail{slot}'] = person.get('email', '')

    return row


def invitation_row(invitation):
    """One mail merge row, as the legacy record."""
    costs = invitation.get('costs') or {}
    return {
        'nomeOspedale': invitation.get('hospital', ''),
        'destinatario': invitation.get('recipient', ''),
        'mail': invitation.get('recipient_email', ''),
        'ccMail': invitation.get('cc_email', ''),
        'reparto': invitation.get('department', ''),
        'specialita': invitation.get('specialty', ''),
        'ruolo': invitation.get('role', ''),
        'numeroMedici': invitation.get('physician_count', ''),
        'sponsor': invitation.get('sponsor', ''),
        'note': invitation.get('notes', ''),
        **{key: value for key, value in costs.items() if value not in (None, '')},
    }


def reminder_row(reminder):
    """One special reminder, as the legacy record."""
    return {
        'titolo': reminder.get('title', ''),
        'data': _day(reminder.get('remind_on')),
        'note': reminder.get('notes', ''),
        'evento': reminder.get('event_title', ''),
    }


def build(*, events=(), invitations=(), reminders=(), generated_on=None):
    """The archive, in the shape `import_archive` reads."""
    return {
        'generatedAt': (generated_on or date.today()).isoformat(),
        'events': [event_row(event) for event in events],
        'stampaUnioneData': [invitation_row(row) for row in invitations],
        'specialReminders': [reminder_row(row) for row in reminders],
    }


def dumps(archive):
    """The archive as the `.json` file that gets downloaded."""
    return json.dumps(archive, ensure_ascii=False, indent=2).encode('utf-8')


def filename_for(day=None):
    return f'archivio-ecm-{(day or date.today()):%Y%m%d}.json'
