# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_ecm.controllers import RHCertificateVerify, RHECMEvaluate, RHECMEventOverview


blueprint = IndicoPluginBlueprint('ecm', __name__)

blueprint.add_url_rule('/event/<int:event_id>/manage/ecm/', 'event_overview', RHECMEventOverview)
blueprint.add_url_rule('/event/<int:event_id>/manage/ecm/evaluate', 'evaluate', RHECMEvaluate,
                       methods=('POST',))
blueprint.add_url_rule('/ecm/verify/<token>', 'verify_certificate', RHCertificateVerify)
