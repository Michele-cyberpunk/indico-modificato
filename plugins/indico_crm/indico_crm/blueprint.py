# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_crm.controllers import (RHCompanies, RHCompanyDetails, RHContactDetails, RHContacts,
                                    RHOpportunities)


blueprint = IndicoPluginBlueprint('crm', __name__, url_prefix='/admin/crm')

blueprint.add_url_rule('/contacts', 'contacts', RHContacts, methods=('GET', 'POST'))
blueprint.add_url_rule('/contacts/<int:contact_id>', 'contact_details', RHContactDetails,
                       methods=('GET', 'POST'))
blueprint.add_url_rule('/companies', 'companies', RHCompanies, methods=('GET', 'POST'))
blueprint.add_url_rule('/companies/<int:company_id>', 'company_details', RHCompanyDetails)
blueprint.add_url_rule('/opportunities', 'opportunities', RHOpportunities, methods=('GET', 'POST'))
