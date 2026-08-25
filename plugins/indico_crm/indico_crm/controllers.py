# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from flask import flash, request, session
from webargs import fields

from indico.core.db import db
from indico.core.plugins import WPJinjaMixinPlugin, url_for_plugin
from indico.modules.admin import RHAdminBase
from indico.modules.admin.views import WPAdmin
from indico.modules.events import Event
from indico.util.date_time import now_utc
from indico.util.i18n import _
from indico.web.args import use_kwargs
from indico.web.flask.util import redirect

from indico_crm.models.activities import Activity, ActivityKind, ActivityStatus
from indico_crm.models.companies import Company, CompanyKind
from indico_crm.models.consents import Consent, ConsentKind
from indico_crm.models.contacts import Contact
from indico_crm.models.evidence import Evidence
from indico_crm.models.links import CRMObjectType, IndicoObjectType, ObjectLink
from indico_crm.models.opportunities import Opportunity, OpportunityStage


class WPCRM(WPJinjaMixinPlugin, WPAdmin):
    sidemenu_option = 'crm'


class RHCRMBase(RHAdminBase):
    """Base for the CRM management area.

    Access is admin-only for now; once the ECM roles exist this becomes a
    dedicated `crm_manager` permission.
    """


class RHContacts(RHCRMBase):
    @use_kwargs({'q': fields.String(load_default='')}, location='query')
    def _process_GET(self, q):
        query = Contact.query.filter(~Contact.is_deleted).order_by(Contact.last_name, Contact.first_name)
        if q:
            term = f'%{q.lower()}%'
            query = query.filter(Contact.last_name.ilike(term) | Contact.email.ilike(term))
        return WPCRM.render_template('contacts.html', 'crm', contacts=query.limit(100).all(), query=q)

    def _process_POST(self):
        form = request.form
        first_name = form.get('first_name', '').strip()
        last_name = form.get('last_name', '').strip()
        if not last_name:
            flash(_('Il cognome è obbligatorio.'), 'error')
            return redirect(url_for_plugin('crm.contacts'))
        contact = Contact(first_name=first_name, last_name=last_name,
                          email=form.get('email', '').strip().lower(),
                          phone=form.get('phone', '').strip(), job_title=form.get('job_title', '').strip())
        db.session.add(contact)
        db.session.commit()
        flash(_('Contatto creato.'), 'success')
        return redirect(url_for_plugin('crm.contact_details', contact_id=contact.id))


class RHContactDetails(RHCRMBase):
    def _process_args(self):
        self.contact = Contact.query.filter_by(id=request.view_args['contact_id'], is_deleted=False).first_or_404()

    def _timeline(self):
        activities = (Activity.query
                      .filter_by(contact_id=self.contact.id)
                      .order_by(Activity.created_dt.desc())
                      .limit(50)
                      .all())
        consents = self.contact.consents.all()
        entries = ([{'when': a.created_dt, 'kind': a.kind.title, 'text': a.subject or a.description,
                     'status': a.status.title if a.kind is ActivityKind.task else ''}
                    for a in activities]
                   + [{'when': c.effective_dt, 'kind': _('Consenso'), 'text': c.kind.title,
                       'status': _('concesso') if c.granted else _('revocato')}
                      for c in consents])
        return sorted(entries, key=lambda entry: entry['when'] or now_utc(), reverse=True)

    def _process_GET(self):
        evidence = (Evidence.query
                    .filter_by(subject_type=CRMObjectType.contact, subject_id=self.contact.id,
                               superseded_by_id=None)
                    .order_by(Evidence.created_dt.desc())
                    .all())
        links = ObjectLink.query.filter_by(crm_type=CRMObjectType.contact, crm_id=self.contact.id).all()
        return WPCRM.render_template('contact_details.html', 'crm', contact=self.contact, evidence=evidence,
                                     timeline=self._timeline(), links=links,
                                     consent_kinds=[(kind.name, kind.title) for kind in ConsentKind])

    def _process_POST(self):
        form = request.form
        action = form.get('action', '')
        if action == 'edit':
            for field in ('first_name', 'last_name', 'email', 'phone', 'job_title'):
                setattr(self.contact, field, form.get(field, '').strip())
            self.contact.updated_dt = now_utc()
            db.session.commit()
            flash(_('Contatto aggiornato.'), 'success')
        elif action == 'consent':
            consent = Consent(contact_id=self.contact.id,
                              kind=ConsentKind[form['consent_kind']],
                              granted=form.get('granted') == 'yes',
                              source=form.get('source', 'scheda contatto').strip())
            db.session.add(consent)
            db.session.commit()
            flash(_('Consenso registrato.'), 'success')
        elif action == 'note':
            activity = Activity(kind=ActivityKind.note, status=ActivityStatus.done, subject='',
                                description=form.get('note', '').strip(), contact_id=self.contact.id,
                                done_dt=now_utc(), created_by_id=session.user.id if session.user else None)
            if not activity.description:
                flash(_('La nota è vuota.'), 'error')
                return redirect(url_for_plugin('crm.contact_details', contact_id=self.contact.id))
            db.session.add(activity)
            db.session.commit()
            flash(_('Nota registrata.'), 'success')
        return redirect(url_for_plugin('crm.contact_details', contact_id=self.contact.id))


class RHCompanies(RHCRMBase):
    def _process_GET(self):
        companies = Company.query.filter(~Company.is_deleted).order_by(Company.name).limit(200).all()
        kinds = [(kind.name, kind.title) for kind in CompanyKind]
        return WPCRM.render_template('companies.html', 'crm', companies=companies, company_kinds=kinds)

    def _process_POST(self):
        name = request.form.get('name', '').strip()
        if not name:
            flash(_('Il nome è obbligatorio.'), 'error')
            return redirect(url_for_plugin('crm.companies'))
        company = Company(name=name, kind=CompanyKind[request.form.get('kind', 'other')],
                          vat_id=request.form.get('vat_id', '').strip() or None)
        db.session.add(company)
        db.session.commit()
        flash(_('Azienda creata.'), 'success')
        return redirect(url_for_plugin('crm.company_details', company_id=company.id))


class RHCompanyDetails(RHCRMBase):
    def _process_args(self):
        self.company = Company.query.filter_by(id=request.view_args['company_id'], is_deleted=False).first_or_404()

    def _process_GET(self):
        contacts = (Contact.query
                    .filter_by(company_id=self.company.id, is_deleted=False)
                    .order_by(Contact.last_name)
                    .all())
        opportunities = (Opportunity.query
                         .filter_by(company_id=self.company.id)
                         .order_by(Opportunity.created_dt.desc())
                         .all())
        events = []
        for link in ObjectLink.query.filter_by(crm_type=CRMObjectType.company,
                                               crm_id=self.company.id).all():
            event = Event.get(link.indico_id) if link.indico_type is IndicoObjectType.event else None
            if event is not None:
                events.append(event)
        return WPCRM.render_template('company_details.html', 'crm', company=self.company, contacts=contacts,
                                     opportunities=opportunities, events=events)


class RHOpportunities(RHCRMBase):
    @use_kwargs({'open_only': fields.Boolean(load_default=False)}, location='query')
    def _process_GET(self, open_only):
        query = Opportunity.query
        if open_only:
            query = query.filter(Opportunity.stage.notin_([OpportunityStage.won, OpportunityStage.lost]))
        opportunities = query.order_by(Opportunity.next_action_dt.nullslast()).all()
        stages = [(stage.name, stage.title) for stage in OpportunityStage]
        companies = Company.query.filter(~Company.is_deleted).order_by(Company.name).all()
        return WPCRM.render_template('opportunities.html', 'crm', opportunities=opportunities,
                                     open_only=open_only, opportunity_stages=stages, all_companies=companies)

    def _process_POST(self):
        form = request.form
        title = form.get('title', '').strip()
        if not title:
            flash(_('Il titolo è obbligatorio.'), 'error')
            return redirect(url_for_plugin('crm.opportunities'))
        company_id = form.get('company_id', type=int)
        company = Company.query.filter_by(id=company_id, is_deleted=False).first() if company_id else None
        if company is None:
            flash(_('Scegli l\'azienda.'), 'error')
            return redirect(url_for_plugin('crm.opportunities'))
        opportunity = Opportunity(title=title, company_id=company.id,
                                  stage=OpportunityStage[form.get('stage', 'new')],
                                  value=form.get('value', type=float) or 0,
                                  next_action=form.get('next_action', '').strip())
        db.session.add(opportunity)
        db.session.commit()
        flash(_('Opportunità creata.'), 'success')
        return redirect(url_for_plugin('crm.opportunities'))
