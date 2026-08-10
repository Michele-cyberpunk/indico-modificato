# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""What happens when a person approves a proposal.

Without these, an approval would be a button that changes a status and does
nothing — the worst possible outcome, because the reviewer believes the work is
done. Each applier performs exactly the change the reviewer saw, and records it.

Nothing here re-runs the agent's reasoning: the stored `proposed_change` is the
instruction, and it is applied as-is or it fails.
"""

from indico.core.db import db
from indico.core.logger import Logger
from indico.core.notifications import make_email, send_email

from indico_agents.governance.approvals import applier


logger = Logger.get('plugin.agents.appliers')


class ApplyError(Exception):
    pass


@applier('link_contact')
def apply_link_contact(approval, user):
    """Link a registration to an existing CRM contact."""
    from indico.modules.events.registration.models.registrations import Registration

    from indico_crm.models.evidence import EvidenceKind
    from indico_crm.models.links import CRMObjectType, IndicoObjectType, LinkSource, ObjectLink
    from indico_crm.services.evidence import record_fact

    contact_id = approval.proposed_change.get('contact_id')
    if not contact_id:
        raise ApplyError('la proposta non indica un contatto')
    registration = Registration.get(approval.subject_id)
    if registration is None:
        raise ApplyError('iscrizione non trovata')

    for indico_type, indico_id, relation in (
        (IndicoObjectType.registration, registration.id, 'participant'),
        (IndicoObjectType.event, registration.event_id, 'participant'),
    ):
        existing = ObjectLink.query.filter_by(crm_type=CRMObjectType.contact, crm_id=contact_id,
                                              indico_type=indico_type, indico_id=indico_id,
                                              relation=relation).first()
        if existing is None:
            db.session.add(ObjectLink(crm_type=CRMObjectType.contact, crm_id=contact_id,
                                      indico_type=indico_type, indico_id=indico_id, relation=relation,
                                      source=LinkSource.agent))

    matched_on = ', '.join(approval.proposed_change.get('matched_on', ())) or 'approvazione manuale'
    record_fact(CRMObjectType.contact, contact_id,
                f"Collegato all'iscrizione {registration.id} ({matched_on})",
                kind=EvidenceKind.derived, attribute='registration_link',
                source_ref=f'approval:{approval.id}', confidence=95, user=user)
    db.session.flush()
    return True


@applier('create_contact')
def apply_create_contact(approval, user):
    """Create the contact the agent proposed, and link it to the registration."""
    from indico.modules.events.registration.models.registrations import Registration

    from indico_crm.models.contacts import ContactSource
    from indico_crm.models.evidence import EvidenceKind
    from indico_crm.models.links import CRMObjectType, IndicoObjectType, LinkSource, ObjectLink
    from indico_crm.services.evidence import record_fact
    from indico_crm.services.identity import create_contact
    from indico_crm.services.identity_rules import IdentityCandidate

    change = approval.proposed_change or {}
    candidate = IdentityCandidate(first_name=change.get('first_name', ''),
                                  last_name=change.get('last_name', ''),
                                  email=change.get('email', ''))
    if not candidate.last_name:
        raise ApplyError('la proposta non ha un cognome')
    contact = create_contact(candidate, source=ContactSource.agent)

    registration = Registration.get(approval.subject_id)
    if registration is not None:
        db.session.add(ObjectLink(crm_type=CRMObjectType.contact, crm_id=contact.id,
                                  indico_type=IndicoObjectType.registration, indico_id=registration.id,
                                  relation='participant', source=LinkSource.agent))
        if registration.user_id:
            contact.user_id = registration.user_id

    record_fact(CRMObjectType.contact, contact.id, 'Contatto creato da una proposta approvata',
                kind=EvidenceKind.derived, attribute='created',
                source_ref=f'approval:{approval.id}', confidence=100, user=user)
    db.session.flush()
    return True


@applier('send_email')
def apply_send_email(approval, user):
    """Send the message the reviewer read.

    The template is rendered again from the stored parameters rather than from a
    stored body, so a template correction applies — but the recipient and the
    reason are the ones that were approved.
    """
    from indico_ecm.services.templates import render_named

    change = approval.proposed_change or {}
    recipient = change.get('to')
    if not recipient:
        raise ApplyError('la proposta non ha un destinatario')
    template_name = change.get('template')
    if not template_name:
        raise ApplyError('la proposta non indica un template')

    context = dict(change.get('context') or {})
    context.setdefault('recipient', change.get('recipient_name') or recipient)
    if 'missing_fields' in change and 'missing_fields' not in context:
        context['missing_fields'] = ', '.join(change['missing_fields'])
    context.setdefault('event_name', change.get('event_name', ''))
    context.setdefault('sender_name', user.full_name if user else '')

    rendered = render_named(template_name, context)
    send_email(make_email(to_list={recipient}, cc_list=set(change.get('cc') or ()),
                          subject=rendered['subject'], body=rendered['body'], html=True))
    logger.info('sent %s to %s after approval %d', template_name, recipient, approval.id)
    return True


@applier('issue_certificates')
def apply_issue_certificates(approval, user):
    """Issue the certificates of an approved batch.

    The credits themselves are not touched here: an assignment that is not
    already approved is skipped, because issuing a certificate can never be the
    act that grants a credit.
    """
    from indico_ecm.models.credits import AssignmentState, CreditAssignment
    from indico_ecm.models.provider import EventAccreditation
    from indico_ecm.services import certificates as certificate_service

    assignment_ids = (approval.proposed_change or {}).get('assignment_ids') or []
    if not assignment_ids:
        raise ApplyError('la proposta non elenca assegnazioni')
    accreditation = EventAccreditation.query.filter_by(event_id=approval.event_id).first()
    if accreditation is None:
        raise ApplyError('evento senza dossier di accreditamento')

    issued, skipped = 0, 0
    for assignment in CreditAssignment.query.filter(CreditAssignment.id.in_(assignment_ids)):
        if assignment.state != AssignmentState.approved:
            skipped += 1
            continue
        certificate = certificate_service.prepare_certificate(assignment,
                                                             provider=accreditation.provider)
        certificate_service.issue_certificate(certificate, user=user)
        issued += 1
    logger.info('approval %d: issued %d certificates, skipped %d', approval.id, issued, skipped)
    db.session.flush()
    return {'issued': issued, 'skipped': skipped}
