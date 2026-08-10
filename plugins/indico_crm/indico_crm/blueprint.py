# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_crm.controllers import RHCompanies, RHContactDetails, RHContacts, RHOpportunities


blueprint = IndicoPluginBlueprint('crm', __name__, url_prefix='/admin/crm')

blueprint.add_url_rule('/contacts', 'contacts', RHContacts)
blueprint.add_url_rule('/contacts/<int:contact_id>', 'contact_details', RHContactDetails)
blueprint.add_url_rule('/companies', 'companies', RHCompanies)
blueprint.add_url_rule('/opportunities', 'opportunities', RHOpportunities)
