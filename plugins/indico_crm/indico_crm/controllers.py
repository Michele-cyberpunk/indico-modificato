# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from flask import request
from webargs import fields

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.admin import RHAdminBase
from indico.modules.admin.views import WPAdmin
from indico.web.args import use_kwargs

from indico_crm.models.companies import Company
from indico_crm.models.contacts import Contact
from indico_crm.models.evidence import Evidence
from indico_crm.models.links import CRMObjectType
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
    def _process(self, q):
        query = Contact.query.filter(~Contact.is_deleted).order_by(Contact.last_name, Contact.first_name)
        if q:
            term = f'%{q.lower()}%'
            query = query.filter(Contact.last_name.ilike(term) | Contact.email.ilike(term))
        return WPCRM.render_template('contacts.html', 'crm', contacts=query.limit(100).all(), query=q)


class RHContactDetails(RHCRMBase):
    def _process_args(self):
        self.contact = Contact.query.filter_by(id=request.view_args['contact_id'], is_deleted=False).first_or_404()

    def _process(self):
        evidence = (Evidence.query
                    .filter_by(subject_type=CRMObjectType.contact, subject_id=self.contact.id,
                               superseded_by_id=None)
                    .order_by(Evidence.created_dt.desc())
                    .all())
        return WPCRM.render_template('contact_details.html', 'crm', contact=self.contact, evidence=evidence)


class RHCompanies(RHCRMBase):
    def _process(self):
        companies = Company.query.filter(~Company.is_deleted).order_by(Company.name).limit(200).all()
        return WPCRM.render_template('companies.html', 'crm', companies=companies)


class RHOpportunities(RHCRMBase):
    def _process(self):
        opportunities = (Opportunity.query
                         .filter(Opportunity.stage.notin_([OpportunityStage.won, OpportunityStage.lost]))
                         .order_by(Opportunity.next_action_dt.nullslast())
                         .all())
        return WPCRM.render_template('opportunities.html', 'crm', opportunities=opportunities)
