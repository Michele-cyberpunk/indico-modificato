# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Tools over the provider's operational layer.

These are what an agent uses to do the work the office does today: read the
checklist, see what is late, price the invitations, prepare a brief, draft the
accreditation request. Everything that leaves the building — a letter, an email
— is prepared, never sent.
"""

from datetime import date

from indico_agents.tools.base import tool


@tool('inspect_event_checklist', description='Stato della checklist di un evento e voci in ritardo.')
def inspect_event_checklist(context, event_id, today=None):
    from indico.modules.events import Event

    from indico_ecm.models.deliverables import states_for_event
    from indico_ecm.services.deliverables import attention_list, readiness

    event = Event.get(event_id)
    if event is None:
        return {'found': False}
    states = states_for_event(event)
    reference = today or date.today()
    event_date = event.start_dt.date() if event.start_dt else None
    late = attention_list(states, event_date, reference)
    return {
        'found': True,
        'readiness': readiness(states),
        'late': [{'deliverable': status.deliverable.value, 'urgency': status.urgency.value,
                  'deadline': status.deadline.isoformat() if status.deadline else None,
                  'days_to_event': status.days_to_event}
                 for status in late],
    }


@tool('list_due_reminders', description='Promemoria scaduti o in scadenza, per evento o complessivi.')
def list_due_reminders(context, event_id=None, lookahead_days=0, today=None):
    from indico_ecm.models.operations import SpecialReminder
    from indico_ecm.services.reminders import Reminder, due_reminders

    query = SpecialReminder.query.filter(SpecialReminder.dismissed_dt.is_(None))
    if event_id is not None:
        query = query.filter_by(event_id=event_id)
    reminders = [Reminder(task=row.task, remind_on=row.remind_on, event_code=row.event_code,
                          event_name=(row.event.title if row.event else ''))
                 for row in query.all()]
    due = due_reminders(reminders, today or date.today(), include_future_days=lookahead_days)
    return {'count': len(due),
            'reminders': [{'task': item.reminder.task, 'event_code': item.reminder.event_code,
                           'days_late': item.days_late} for item in due]}


@tool('invitation_costs', description='Costi di ospitalità delle lettere di invito di un evento.')
def invitation_costs(context, event_id):
    from indico.modules.events import Event

    from indico_ecm.models.operations import EventOperations, InvitationBatch
    from indico_ecm.services.costs import CostSheet, event_totals, exceeds_budget, money

    event = Event.get(event_id)
    if event is None:
        return {'found': False}
    sheets = []
    for row in InvitationBatch.query.filter_by(event_id=event_id):
        data = row.costs or {}
        sheets.append(CostSheet(physicians=row.physician_count, room=money(data.get('room')),
                                city_tax=money(data.get('city_tax')), catering=money(data.get('catering')),
                                travel=money(data.get('travel'))))
    totals = event_totals(sheets)
    operations = EventOperations.query.filter_by(event_id=event_id).first()
    result = {'found': True, 'totals': {key: str(value) for key, value in totals.items()}}
    if operations is not None and operations.hospitality_budget is not None:
        exceeded, total, overrun = exceeds_budget(sheets, operations.hospitality_budget)
        result['budget'] = {'limit': str(operations.hospitality_budget), 'total': str(total),
                            'exceeded': exceeded, 'overrun': str(overrun)}
    return result


@tool('prepare_graphic_brief', description='Prepara il brief per il grafico a partire dal titolo evento.')
def prepare_graphic_brief(context, event_id):
    from indico.modules.events import Event

    from indico_ecm.services.specialty import graphic_brief
    from indico_ecm.services.templates import render_named

    event = Event.get(event_id)
    if event is None:
        return {'found': False}
    source = f'{event.title} {event.description or ""}'
    brief = graphic_brief(source, event_name=event.title,
                          place=(event.venue_name or ''),
                          date_text=(event.start_dt.strftime('%d/%m/%Y') if event.start_dt else ''))
    message = render_named('graphic_brief', {
        'event_name': brief['event_name'], 'specialty': brief['specialty'], 'place': brief['place'],
        'date_text': brief['date'], 'palette_description': brief['palette_description'],
        'cmyk': ', '.join(f'{key}: {value}' for key, value in brief['cmyk'].items()),
        'rgb': ', '.join(brief['rgb']), 'keywords': ', '.join(brief['matched_keywords']),
    })
    return {'found': True, 'brief': brief, 'message': message}


@tool('draft_accreditation_request', description='Prepara la richiesta di accreditamento. Non invia.')
def draft_accreditation_request(context, event_id):
    from indico.modules.events import Event

    from indico_ecm.models.operations import EventOperations
    from indico_ecm.services.accreditation_mail import AccreditationRequest, build_email, missing_fields

    event = Event.get(event_id)
    if event is None:
        return {'found': False}
    operations = EventOperations.query.filter_by(event_id=event_id).first()
    accreditation = event.ecm_accreditation
    request = AccreditationRequest(
        event_name=event.title,
        event_date=event.start_dt.date() if event.start_dt else None,
        place=(event.venue_name or ''),
        sponsor=(accreditation.provider.name if accreditation and accreditation.provider else ''),
        event_code=(operations.event_code if operations else ''),
        folder_name=(operations.folder_name if operations else ''),
        recipient_label=(operations.accreditation_contact if operations else 'ECM'),
        recipient_email=(operations.accreditation_to if operations else ''),
        cc=tuple(filter(None, (operations.accreditation_cc,))) if operations else (),
    )
    return {'found': True, 'email': build_email(request), 'missing': missing_fields(request)}


@tool('prepare_invitation_letters', description='Prepara le lettere di invito di un evento. Non invia.')
def prepare_invitation_letters(context, event_id):
    from indico_ecm.models.operations import InvitationBatch
    from indico_ecm.services.letters import InvitationRow, invitation_filename, letter_context

    rows = InvitationBatch.query.filter_by(event_id=event_id).all()
    letters = []
    for row in rows:
        invitation = InvitationRow(hospital=row.hospital, physician_count=row.physician_count,
                                   role=row.role, department=row.department,
                                   event_name=(row.event.title if row.event else ''),
                                   event_place=(row.event.venue_name if row.event else ''),
                                   recipient=row.recipient, notes=row.notes)
        letters.append({'row_id': row.id, 'filename': invitation_filename(invitation),
                        'context': letter_context(invitation)})
    return {'count': len(letters), 'letters': letters}
