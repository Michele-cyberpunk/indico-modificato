# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Credit and attendance agents.

Both are read-only or drafting by design. The credit agent never computes
credits: it calls the deterministic ECM service and stores its output as a
proposal, so what ends up in the database is the rules engine's verdict, not an
agent's opinion.
"""

from indico.core.db import db
from indico.core.logger import Logger

from indico_agents.agents.base import Agent, AutonomyLevel
from indico_agents.runtime import tasks as queue
from indico_agents.runtime.runner import register_agent


logger = Logger.get('plugin.agents.credit')


@register_agent
class CreditAgent(Agent):
    name = 'credit_agent'
    task_kinds = ('credit_evaluation',)
    skills = ('ecm-compliance', 'evidence')
    autonomy = AutonomyLevel.read_only
    purpose = "Valuta l'idoneità ai crediti e prepara la lista degli aventi diritto."

    def run(self, context):
        from indico.modules.events.registration.models.registrations import Registration

        from indico_ecm.services import eligibility as eligibility_service

        registration = Registration.get(context.task.subject_id)
        if registration is None or registration.is_deleted:
            context.note('iscrizione non trovata')
            return

        assignment = eligibility_service.propose_assignment(registration,
                                                            agent_run_id=context.run.id)
        reasons = ', '.join(assignment.reasons) or '—'
        context.note(f'valutazione {assignment.state.name}: {assignment.credits} crediti (motivi: {reasons})')
        db.session.flush()


@register_agent
class AttendanceAgent(Agent):
    name = 'attendance_agent'
    task_kinds = ('attendance_reconcile',)
    skills = ('attendance-rules', 'evidence')
    autonomy = AutonomyLevel.drafting
    purpose = 'Individua anomalie di presenza e le segnala, senza convalidarle.'

    def run(self, context):
        from indico.modules.events.registration.models.registrations import Registration

        from indico_ecm.services import attendance as attendance_service

        registration = Registration.get(context.task.subject_id)
        if registration is None or registration.is_deleted:
            context.note('iscrizione non trovata')
            return

        anomalies = []
        open_rows = attendance_service.open_attendance(registration)
        if open_rows:
            anomalies.append(f'{len(open_rows)} presenze senza uscita registrata')

        intervals = attendance_service.build_intervals(registration)
        if not intervals and registration.checked_in:
            anomalies.append('check-in di evento senza alcuna presenza per sessione')

        if anomalies:
            context.note('; '.join(anomalies))
            # a human has to resolve these, so the follow-up is a task, not an edit
            queue.schedule_task('attendance_anomaly_review', 'registration', registration.id,
                                event_id=registration.event_id, delay=0,
                                payload={'anomalies': anomalies})
        else:
            context.note('nessuna anomalia')
            queue.schedule_task('credit_evaluation', 'registration', registration.id,
                                event_id=registration.event_id, delay=60)
