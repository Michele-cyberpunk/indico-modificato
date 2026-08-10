# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Registration and contact-resolution agents.

Deterministic on purpose: the first agents to reach production should be the
ones whose behaviour can be predicted exactly. The language model belongs later,
in agents that draft text — not in the ones that decide whether a participant's
regulatory data is complete.
"""

from indico.core.logger import Logger

from indico_agents.agents.base import Agent, AutonomyLevel
from indico_agents.governance.approvals import request_approval
from indico_agents.runtime.runner import register_agent


logger = Logger.get('plugin.agents.registration')

#: Fields an ECM certificate cannot be issued without
REQUIRED_HCP_FIELDS = ('tax_code', 'profession', 'discipline')


@register_agent
class RegistrationAgent(Agent):
    name = 'registration_agent'
    task_kinds = ('registration_check',)
    skills = ('data-boundaries', 'evidence', 'ecm-compliance')
    autonomy = AutonomyLevel.drafting
    purpose = "Controlla che l'iscrizione abbia i dati necessari per l'attestato."

    def run(self, context):
        from indico.modules.events.registration.models.registrations import Registration

        registration = Registration.get(context.task.subject_id)
        if registration is None or registration.is_deleted:
            context.note('iscrizione non trovata')
            return

        missing = self._missing_regulatory_data(registration)
        if not missing:
            context.note('dati completi')
            return

        context.note(f'dati mancanti: {", ".join(missing)}')
        request_approval(
            action='send_email',
            subject_type='registration',
            subject_id=registration.id,
            event_id=registration.event_id,
            run=context.run,
            rationale=("L'iscritto non ha i dati necessari per l'attestato ECM: "
                       f'{", ".join(missing)}.'),
            proposed_change={
                'template': 'missing_ecm_data',
                'to': registration.email,
                'missing_fields': missing,
            },
        )

    def _missing_regulatory_data(self, registration):
        profile = _hcp_profile_for(registration)
        if profile is None:
            return ['profilo professionista sanitario']
        return [field for field in REQUIRED_HCP_FIELDS if not getattr(profile, field, '')]


@register_agent
class ContactResolutionAgent(Agent):
    name = 'contact_resolution_agent'
    task_kinds = ('contact_resolution',)
    skills = ('identity-matching', 'evidence')
    autonomy = AutonomyLevel.drafting
    purpose = 'Propone il collegamento di un iscritto a un contatto esistente.'

    def run(self, context):
        from indico.modules.events.registration.models.registrations import Registration

        from indico_crm.services.identity import find_matches
        from indico_crm.services.identity_rules import IdentityCandidate, MatchDecision

        registration = Registration.get(context.task.subject_id)
        if registration is None or registration.is_deleted:
            context.note('iscrizione non trovata')
            return

        candidate = IdentityCandidate(first_name=registration.first_name or '',
                                      last_name=registration.last_name or '',
                                      email=registration.email or '')
        matches = find_matches(candidate, healthcare=True)
        if not matches:
            context.note('nessun contatto simile: serve una creazione manuale')
            request_approval(
                action='create_contact',
                subject_type='registration',
                subject_id=registration.id,
                event_id=registration.event_id,
                run=context.run,
                rationale='Nessun contatto corrispondente trovato per questo iscritto.',
                proposed_change={'first_name': candidate.first_name, 'last_name': candidate.last_name,
                                 'email': candidate.email},
            )
            return

        contact, result = matches[0]
        if result.decision is MatchDecision.conflict:
            context.note(f'conflitto di identità con il contatto {contact.id}: {result.reason}')
            return

        context.note(f'proposta di collegamento al contatto {contact.id} ({result.reason})')
        request_approval(
            action='link_contact',
            subject_type='registration',
            subject_id=registration.id,
            event_id=registration.event_id,
            run=context.run,
            rationale=f'Corrispondenza {result.decision.value}: {result.reason}.',
            proposed_change={'contact_id': contact.id, 'matched_on': list(result.matched_on)},
        )


def _hcp_profile_for(registration):
    try:
        from indico_crm.models.contacts import Contact
        from indico_crm.models.hcp_profiles import HCPProfile
    except ImportError:
        return None
    if registration.user_id is None:
        return None
    contact = Contact.query.filter_by(user_id=registration.user_id, is_deleted=False).first()
    if contact is None:
        return None
    return HCPProfile.query.filter_by(contact_id=contact.id).first()
