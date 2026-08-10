# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""CRM tools.

The read side is straightforward. The write side is deliberately narrow: an
agent records facts, creates work for people and reschedules itself, and that is
all. Changing a contact's data is a proposal, not a tool.
"""

from datetime import date, timedelta

from indico.core.db import db
from indico.util.date_time import now_utc

from indico_agents.tools.base import tool


def _contact(contact_id):
    from indico_crm.models.contacts import Contact
    return Contact.query.filter_by(id=contact_id, is_deleted=False).first()


@tool('search_crm', description='Cerca contatti e aziende per nome o email.')
def search_crm(context, query, limit=20):
    from indico_crm.models.companies import Company
    from indico_crm.models.contacts import Contact

    term = f'%{(query or "").strip().lower()}%'
    if len(term) < 5:
        return {'error': 'query troppo corta'}
    contacts = (Contact.query
                .filter(~Contact.is_deleted,
                        db.or_(Contact.last_name.ilike(term), Contact.email.ilike(term)))
                .limit(limit).all())
    companies = Company.query.filter(~Company.is_deleted, Company.name.ilike(term)).limit(limit).all()
    return {
        'contacts': [{'id': c.id, 'name': c.full_name, 'company_id': c.company_id,
                      'is_hcp': c.is_healthcare_professional} for c in contacts],
        'companies': [{'id': c.id, 'name': c.name, 'kind': c.kind.name} for c in companies],
    }


@tool('read_contact_history', description='Storico di un contatto: attività, evidenze, partecipazioni.')
def read_contact_history(context, contact_id, limit=25):
    from indico_crm.models.links import CRMObjectType, ObjectLink
    from indico_crm.services.evidence import current_evidence

    contact = _contact(contact_id)
    if contact is None:
        return {'found': False}
    activities = contact.activities.order_by(db.desc('created_dt')).limit(limit).all()
    links = ObjectLink.query.filter_by(crm_type=CRMObjectType.contact, crm_id=contact.id).all()
    return {
        'found': True,
        'name': contact.full_name,
        'is_hcp': contact.is_healthcare_professional,
        'activities': [{'kind': a.kind.name, 'subject': a.subject, 'status': a.status.name,
                        'from_agent': a.is_from_agent} for a in activities],
        'evidence': [{'attribute': e.attribute, 'statement': e.statement, 'kind': e.kind.name,
                      'confidence': e.confidence} for e in current_evidence(CRMObjectType.contact, contact.id)],
        'links': [{'type': link.indico_type.name, 'id': link.indico_id, 'relation': link.relation}
                  for link in links],
    }


@tool('read_company_history', description="Storico di un'azienda: sponsorizzazioni, opportunità, contatti.")
def read_company_history(context, company_id):
    from indico_crm.models.companies import Company

    company = Company.query.filter_by(id=company_id, is_deleted=False).first()
    if company is None:
        return {'found': False}
    return {
        'found': True,
        'name': company.name,
        'kind': company.kind.name,
        'contacts': [{'id': c.id, 'name': c.full_name} for c in company.contacts.limit(50)],
        'opportunities': [{'id': o.id, 'title': o.title, 'stage': o.stage.name, 'value': str(o.value),
                           'event_id': o.event_id} for o in company.opportunities],
    }


@tool('identify_contact', description='Cerca il contatto corrispondente a una persona. Non fonde nulla.')
def identify_contact(context, last_name, first_name='', email='', tax_code='', healthcare=False):
    from indico_crm.services.identity import find_matches
    from indico_crm.services.identity_rules import IdentityCandidate

    candidate = IdentityCandidate(first_name=first_name, last_name=last_name, email=email,
                                  tax_code=tax_code)
    matches = find_matches(candidate, healthcare=healthcare)
    return {'matches': [{'contact_id': contact.id, 'name': contact.full_name,
                         'decision': result.decision.value, 'reason': result.reason,
                         'can_auto_merge': result.can_auto_merge}
                        for contact, result in matches]}


@tool('list_outstanding_work', description='Cosa resta da fare su un evento o su un contatto.')
def list_outstanding_work(context, event_id=None, contact_id=None):
    from indico_crm.models.activities import Activity, ActivityStatus

    query = Activity.query.filter_by(status=ActivityStatus.open)
    if event_id is not None:
        query = query.filter_by(event_id=event_id)
    if contact_id is not None:
        query = query.filter_by(contact_id=contact_id)
    activities = query.order_by(Activity.due_dt.nullslast()).limit(50).all()
    result = {'activities': [{'id': a.id, 'subject': a.subject, 'kind': a.kind.name,
                              'due': a.due_dt.isoformat() if a.due_dt else None} for a in activities]}
    if event_id is not None:
        from indico.modules.events import Event

        from indico_ecm.models.deliverables import states_for_event
        from indico_ecm.services.deliverables import attention_list

        event = Event.get(event_id)
        if event is not None:
            event_date = event.start_dt.date() if event.start_dt else None
            result['late_deliverables'] = [status.deliverable.value
                                           for status in attention_list(states_for_event(event),
                                                                        event_date, date.today())]
    return result


@tool('record_fact', description='Registra un fatto con la sua fonte. Non sovrascrive: supera il precedente.')
def record_fact(context, subject_type, subject_id, statement, kind='derived', attribute='',
                source_ref='', confidence=50):
    from indico_crm.models.evidence import EvidenceKind
    from indico_crm.models.links import CRMObjectType
    from indico_crm.services.evidence import record_fact as store

    evidence = store(CRMObjectType[subject_type], subject_id, statement,
                     kind=EvidenceKind[kind], attribute=attribute,
                     source_ref=source_ref or f'agent_run:{context.run.id}',
                     confidence=confidence, agent_run_id=context.run.id)
    return {'evidence_id': evidence.id}


@tool('create_task', description="Crea un'attività per una persona.")
def create_task(context, subject, description='', contact_id=None, company_id=None, event_id=None,
                due_in_days=None, assignee_id=None):
    from indico_crm.models.activities import Activity, ActivityKind, ActivityStatus

    if not (contact_id or company_id or event_id):
        return {'error': "un'attività deve riferirsi a un contatto, un'azienda o un evento"}
    activity = Activity(kind=ActivityKind.task, status=ActivityStatus.open, subject=subject,
                        description=description, contact_id=contact_id, company_id=company_id,
                        event_id=event_id, assignee_id=assignee_id,
                        due_dt=(now_utc() + timedelta(days=due_in_days)) if due_in_days else None,
                        created_by_agent_run_id=context.run.id)
    db.session.add(activity)
    db.session.flush()
    return {'activity_id': activity.id}


@tool('schedule_recheck', description='Riprogramma sé stesso o un altro controllo.')
def schedule_recheck(context, kind, subject_type, subject_id, delay_days=1, event_id=None, payload=None):
    from indico_agents.models.tasks import TaskOrigin
    from indico_agents.runtime.tasks import schedule_task

    task = schedule_task(kind, subject_type, subject_id, event_id=event_id,
                         delay=int(delay_days * 86400), payload=payload or {},
                         origin=TaskOrigin.agent)
    return {'task_id': task.id, 'run_after': task.run_after.isoformat()}


@tool('write_brief', description="Briefing su un contatto, un'azienda o un evento, con le fonti.")
def write_brief(context, subject_type, subject_id):
    if subject_type == 'contact':
        data = read_contact_history(context, subject_id)
    elif subject_type == 'company':
        data = read_company_history(context, subject_id)
    elif subject_type == 'event':
        from indico_agents.tools.operations import inspect_event_checklist
        data = inspect_event_checklist(context, subject_id)
    else:
        return {'error': f'soggetto sconosciuto: {subject_type}'}
    if not data.get('found', True):
        return {'found': False}
    return {'subject_type': subject_type, 'subject_id': subject_id, 'facts': data,
            'note': 'ogni voce proviene dai dati della piattaforma; nessuna deduzione aggiunta'}


@tool('research_company', description="Ricerca esterna su un'azienda, se un fornitore è configurato.")
def research_company(context, company_id):
    from indico_agents.plugin import AgentsPlugin

    provider = AgentsPlugin.settings.get('research_provider')
    if not provider:
        return {'configured': False,
                'note': 'nessun fornitore di ricerca configurato: la ricerca esterna è disattivata'}
    return {'configured': True, 'provider': provider, 'results': [],
            'note': 'adapter del fornitore non ancora implementato'}


@tool('enrich_company', description="Arricchisce i dati di un'azienda dalle fonti configurate.")
def enrich_company(context, company_id):
    result = research_company(context, company_id)
    if not result.get('configured'):
        return result
    return result | {'updated_fields': []}
