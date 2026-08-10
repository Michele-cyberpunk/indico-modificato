# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Event setup and checklist agents.

These two do the job the legacy dashboard could only display: the first turns a
new event into a checklist with deadlines, the second keeps looking at those
deadlines every day and raises a reminder the moment one passes.

Both are deterministic. Neither touches a regulatory field: they create
checklist rows and reminders, and everything that would leave the building goes
through the approval queue.
"""

from datetime import date

from indico.core.db import db
from indico.core.logger import Logger
from indico.util.date_time import now_utc

from indico_agents.agents.base import Agent, AutonomyLevel
from indico_agents.runtime import tasks as queue
from indico_agents.runtime.runner import register_agent


logger = Logger.get('plugin.agents.event')

#: How often the checklist of an upcoming event is looked at again
CHECKLIST_RECHECK_SECONDS = 24 * 3600


@register_agent
class EventSetupAgent(Agent):
    name = 'event_setup_agent'
    task_kinds = ('event_setup',)
    skills = ('evidence',)
    autonomy = AutonomyLevel.acting
    purpose = 'Crea la checklist di preparazione di un evento e ne calcola la cartella.'

    def run(self, context):
        from indico.modules.events import Event

        from indico_ecm.models.deliverables import EventDeliverable
        from indico_ecm.models.operations import EventOperations
        from indico_ecm.services.deliverables import Deliverable, DeliverableState
        from indico_ecm.services.naming import generate_folder_name

        event = Event.get(context.task.subject_id)
        if event is None or event.is_deleted:
            context.note('evento non trovato')
            return

        existing = {row.deliverable for row in event.ecm_deliverables}
        created = 0
        for deliverable in Deliverable:
            if deliverable.value in existing:
                continue
            db.session.add(EventDeliverable(event_id=event.id, deliverable=deliverable.value,
                                            state=DeliverableState.todo.value))
            created += 1

        operations = EventOperations.query.filter_by(event_id=event.id).first()
        if operations is None:
            operations = EventOperations(event_id=event.id)
            db.session.add(operations)
        if not operations.folder_name:
            operations.folder_name = generate_folder_name(
                start_date=event.start_dt.date() if event.start_dt else None,
                end_date=event.end_dt.date() if event.end_dt else None,
                event_name=event.title,
                city=(event.venue_name or ''),
                event_code=operations.event_code,
            )
        operations.updated_dt = now_utc()
        db.session.flush()

        context.note(f'checklist creata ({created} voci), cartella: {operations.folder_name or "—"}')
        queue.schedule_task('checklist_review', 'event', event.id, event_id=event.id,
                            delay=CHECKLIST_RECHECK_SECONDS)


@register_agent
class ChecklistAgent(Agent):
    name = 'checklist_agent'
    task_kinds = ('checklist_review',)
    skills = ('evidence',)
    autonomy = AutonomyLevel.acting
    purpose = 'Segnala le voci di checklist in ritardo e riprogramma il controllo.'

    def run(self, context):
        from indico.modules.events import Event

        from indico_ecm.models.deliverables import states_for_event
        from indico_ecm.models.operations import SpecialReminder
        from indico_ecm.services.reminders import reminders_from_checklist

        event = Event.get(context.task.subject_id)
        if event is None or event.is_deleted:
            context.note('evento non trovato')
            return

        event_date = event.start_dt.date() if event.start_dt else None
        generated = reminders_from_checklist(states_for_event(event), event_date, date.today(),
                                             event_name=event.title)
        existing = {row.source_deliverable for row in event.ecm_reminders.filter(
            SpecialReminder.dismissed_dt.is_(None))}

        created = 0
        for reminder in generated:
            deliverable = reminder.extra.get('deliverable', '')
            if deliverable in existing:
                continue
            db.session.add(SpecialReminder(event_id=event.id, task=reminder.task,
                                           remind_on=reminder.remind_on or date.today(),
                                           source_deliverable=deliverable))
            created += 1
        db.session.flush()

        if created:
            context.note(f'{created} nuove segnalazioni di ritardo')
        else:
            context.note('nessun nuovo ritardo')

        # keep looking until the event is over, then stop on its own
        if event_date is None or event_date >= date.today():
            queue.schedule_task('checklist_review', 'event', event.id, event_id=event.id,
                                delay=CHECKLIST_RECHECK_SECONDS)
