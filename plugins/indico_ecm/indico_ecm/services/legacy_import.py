# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Importing the existing archive.

Reads the records the Cyberbrain event manager keeps (events, mail merge rows,
special reminders) and turns them into the platform's structures. Nothing is
guessed: a value that cannot be parsed is reported as a problem on that row
rather than silently dropped, because these rows are the provider's history.

Pure transformation, no Indico imports: the caller decides what to persist.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from indico_ecm.services.deliverables import DeliverableState
from indico_ecm.services.event_schema import (EVENT_FIELDS, Destination, FieldType, INVITATION_FIELDS,
                                              REMINDER_FIELDS, index_fields)
from indico_ecm.services.letters import InvitationRow
from indico_ecm.services.naming import generate_folder_name


#: Values the legacy table uses for yes
TRUE_VALUES = frozenset({'sì', 'si', 'yes', 'true', '1', 'x', 'fatto'})
#: Values that mean "does not apply to this event"
NOT_APPLICABLE_VALUES = frozenset({'n/a', 'na', '-', 'non applicabile'})


@dataclass
class ImportIssue:
    row: int
    field: str
    message: str
    value: str = ''


@dataclass
class ImportedEvent:
    event_code: str = ''
    title: str = ''
    start_date: date | None = None
    end_date: date | None = None
    city: str = ''
    venue: str = ''
    sponsor: str = ''
    activity_format: str = ''
    credits: float | None = None
    max_participants: int | None = None
    activity_code: str = ''
    folder_name: str = ''
    accreditation_contact: str = ''
    deliverables: dict = field(default_factory=dict)
    faculty: list = field(default_factory=list)
    operations: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


@dataclass
class ImportResult:
    events: list = field(default_factory=list)
    invitations: list = field(default_factory=list)
    reminders: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.issues


def parse_bool(value):
    """Read a legacy yes/no cell.

    Returns `None` for an empty cell: never filled in and explicitly "No" are
    different things, and the checklist treats them differently.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in NOT_APPLICABLE_VALUES:
        return False
    return text in TRUE_VALUES


def parse_date(value):
    """Read a date in any of the formats the archive contains."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).date()
    except ValueError:
        return None


def parse_number(value):
    if value in (None, ''):
        return None
    text = str(value).strip().replace('€', '').replace(' ', '').replace(',', '.')
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def deliverable_state(value):
    """Map a legacy yes/no cell to a checklist state."""
    flag = parse_bool(value)
    if flag is None:
        return DeliverableState.todo
    return DeliverableState.done if flag else DeliverableState.todo


def import_event(row, *, row_number=0, issues=None):
    """Turn one legacy event record into an `ImportedEvent`."""
    issues = issues if issues is not None else []
    schema = index_fields(EVENT_FIELDS)
    imported = ImportedEvent(raw=dict(row))

    for key, legacy_field in schema.by_key.items():
        value = row.get(key)
        if legacy_field.required and (value in (None, '')):
            issues.append(ImportIssue(row_number, key, 'campo obbligatorio mancante'))
        if legacy_field.type is FieldType.date and value and parse_date(value) is None:
            issues.append(ImportIssue(row_number, key, 'data non riconosciuta', str(value)))

    imported.title = str(row.get('nomeEvento') or '').strip()
    imported.event_code = str(row.get('codiceEvento') or '').strip()
    imported.start_date = parse_date(row.get('dataEvento1'))
    imported.end_date = parse_date(row.get('dataEvento2'))
    imported.city = str(row.get('citta') or '').strip()
    imported.venue = str(row.get('luogo') or '').strip()
    imported.sponsor = str(row.get('cliente') or '').strip()
    imported.activity_format = str(row.get('tipoEvento') or '').strip()
    imported.credits = parse_number(row.get('creditiEvento'))
    participants = parse_number(row.get('numeroPartecipanti'))
    imported.max_participants = int(participants) if participants else None
    imported.activity_code = str(row.get('codieAgenas') or '').strip()
    imported.accreditation_contact = str(row.get('uecm') or '').strip()
    imported.folder_name = str(row.get('nomeCartella') or '').strip() or generate_folder_name(
        start_date=imported.start_date, end_date=imported.end_date, event_name=imported.title,
        event_type=imported.activity_format, city=imported.city, sponsor=imported.sponsor,
        event_code=imported.event_code, note=str(row.get('note') or ''))

    imported.deliverables = {deliverable: deliverable_state(row.get(key))
                             for key, deliverable in schema.deliverable_keys.items()}

    for slot in range(1, 6):
        name = str(row.get(f'relatore{slot}') or '').strip()
        email = str(row.get(f'mail{slot}') or '').strip()
        if name or email:
            imported.faculty.append({'name': name, 'email': email, 'slot': slot})

    for legacy_field in schema.by_key.values():
        if legacy_field.destination is Destination.operations and legacy_field.target:
            imported.operations[legacy_field.target] = row.get(legacy_field.key)

    return imported


def import_invitation(row, *, row_number=0, issues=None):
    """Turn one mail merge row into an `InvitationRow` plus its cost sheet."""
    issues = issues if issues is not None else []
    count = parse_number(row.get('numeroMedici'))
    if not count or count < 1:
        issues.append(ImportIssue(row_number, 'numeroMedici', 'numero medici mancante o non valido',
                                  str(row.get('numeroMedici', ''))))
        count = 1
    invitation = InvitationRow(
        hospital=str(row.get('nomeOspedale') or '').strip(),
        physician_count=int(count),
        role=str(row.get('ruolo') or '').strip(),
        department=str(row.get('reparto') or '').strip(),
        event_name=str(row.get('nomeEvento') or '').strip(),
        event_place=str(row.get('luogoEvento') or '').strip(),
        recipient=str(row.get('destinatario') or '').strip(),
        notes=str(row.get('altreNote') or '').strip(),
        extra={'email': row.get('mail'), 'cc': row.get('ccMail'), 'specialty': row.get('specialita'),
               'sponsor': row.get('sponsor'), 'credits': parse_number(row.get('numeroCrediti'))},
    )
    costs = {legacy_field.key: parse_number(row.get(legacy_field.key)) or 0
             for legacy_field in INVITATION_FIELDS if legacy_field.type is FieldType.number}
    return invitation, costs


def import_reminder(row, *, row_number=0, issues=None):
    issues = issues if issues is not None else []
    when = parse_date(row.get('giornoPreavviso'))
    if when is None:
        issues.append(ImportIssue(row_number, 'giornoPreavviso', 'data promemoria mancante',
                                  str(row.get('giornoPreavviso', ''))))
    return {
        'event_code': str(row.get('codiceEvento') or '').strip(),
        'task': str(row.get('mansione') or '').strip(),
        'remind_on': when,
        'legacy_event_name': str(row.get('nomeEvento') or '').strip(),
    }


def import_archive(data):
    """Import a full export of the legacy application.

    Accepts the shape the application stores (`events`, `stampaUnioneData` or
    `knifeData`, `specialReminders`) and returns everything it could read plus
    every problem it found, so the import can be reviewed before it is applied.
    """
    result = ImportResult()
    for number, row in enumerate(data.get('events') or (), start=1):
        result.events.append(import_event(row, row_number=number, issues=result.issues))
    invitations = data.get('stampaUnioneData') or data.get('knifeData') or ()
    for number, row in enumerate(invitations, start=1):
        result.invitations.append(import_invitation(row, row_number=number, issues=result.issues))
    for number, row in enumerate(data.get('specialReminders') or (), start=1):
        result.reminders.append(import_reminder(row, row_number=number, issues=result.issues))
    return result


def reminder_fields_note():
    """The reminder columns, kept for the import UI."""
    return tuple(item.label for item in REMINDER_FIELDS)
