# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Handlers connecting the CRM to Indico's own signals.

Everything here is cheap and synchronous-safe: records are linked, and anything
that needs judgement is turned into an agent task to be picked up later. No
model call ever happens in the request path.
"""

from indico.core.db import db

from indico_crm.models.contacts import Contact, ContactSource
from indico_crm.models.links import CRMObjectType, IndicoObjectType, LinkSource, ObjectLink
from indico_crm.services.identity import (candidate_from_contact, create_contact, find_matches,
                                          find_or_create_company)
from indico_crm.services.identity_rules import IdentityCandidate
from indico_crm.util import enqueue_agent_task


def _link(contact, indico_type, indico_id, relation, source=LinkSource.signal):
    existing = ObjectLink.query.filter_by(crm_type=CRMObjectType.contact, crm_id=contact.id,
                                          indico_type=indico_type, indico_id=indico_id,
                                          relation=relation).first()
    if existing:
        return existing
    link = ObjectLink(crm_type=CRMObjectType.contact, crm_id=contact.id, indico_type=indico_type,
                      indico_id=indico_id, relation=relation, source=source)
    db.session.add(link)
    return link


def _candidate_from_registration(registration):
    return IdentityCandidate(
        first_name=registration.first_name or '',
        last_name=registration.last_name or '',
        email=registration.email or '',
    )


def _company_for(registration):
    """The organization the registrant declared, when the plugin is set to keep them.

    The affiliation is a personal-data field of the registration form: it is
    only there when the form asks for it.
    """
    from indico_crm.plugin import CRMPlugin

    if not CRMPlugin.settings.get('autocreate_companies'):
        return None
    affiliation = (registration.get_personal_data().get('affiliation') or '').strip()
    company = find_or_create_company(affiliation)
    return company.id if company else None


def registration_created(registration, **kwargs):
    """Link the registrant to a contact, or ask an agent to sort it out.

    A registration whose person cannot be resolved with certainty is not
    guessed: it becomes a task, because the contact it would create may end up
    on a certificate.
    """
    from indico_crm.plugin import CRMPlugin

    if not CRMPlugin.settings.get('autolink_registrations'):
        return

    candidate = _candidate_from_registration(registration)
    if registration.user is not None:
        contact = Contact.query.filter_by(user_id=registration.user.id, is_deleted=False).first()
        if contact is None:
            contact = create_contact(candidate, source=ContactSource.registration,
                                     company_id=_company_for(registration))
            contact.user_id = registration.user.id
        _link(contact, IndicoObjectType.registration, registration.id, 'participant')
        _link(contact, IndicoObjectType.event, registration.event_id, 'participant')
        enqueue_agent_task('registration_check', 'registration', registration.id,
                           event_id=registration.event_id, delay=300)
        return

    matches = find_matches(candidate)
    if matches and matches[0][1].can_auto_merge:
        contact = matches[0][0]
        _link(contact, IndicoObjectType.registration, registration.id, 'participant')
        _link(contact, IndicoObjectType.event, registration.event_id, 'participant')
    else:
        enqueue_agent_task('contact_resolution', 'registration', registration.id,
                           event_id=registration.event_id, delay=60)
    enqueue_agent_task('registration_check', 'registration', registration.id,
                       event_id=registration.event_id, delay=300)


def registration_state_updated(registration, previous_state=None, **kwargs):
    enqueue_agent_task('registration_check', 'registration', registration.id,
                       event_id=registration.event_id, delay=60)


def registration_checkin_updated(registration, **kwargs):
    """Attendance changed: reconcile it, asynchronously.

    Nothing about eligibility is decided here. The task lets the ECM service
    recompute attendance and an agent flag anomalies afterwards.
    """
    enqueue_agent_task('attendance_reconcile', 'registration', registration.id,
                       event_id=registration.event_id, delay=0)


def event_created(event, **kwargs):
    enqueue_agent_task('event_setup', 'event', event.id, event_id=event.id, delay=0)


def event_person_updated(person, **kwargs):
    """Keep faculty in sync with the CRM."""
    if not person.email:
        return
    candidate = IdentityCandidate(first_name=person.first_name or '', last_name=person.last_name or '',
                                  email=person.email)
    matches = find_matches(candidate)
    if matches and matches[0][1].can_auto_merge:
        contact = matches[0][0]
        _link(contact, IndicoObjectType.event_person, person.id, 'faculty')
        return
    enqueue_agent_task('faculty_review', 'event_person', person.id,
                       event_id=getattr(person, 'event_id', None), delay=120)


def contact_candidate_from_contact(contact):
    """Expose the candidate builder to other plugins without importing services."""
    return candidate_from_contact(contact)
