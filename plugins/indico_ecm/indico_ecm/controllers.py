# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from flask import jsonify, request

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.events.management.controllers.base import RHManageEventBase
from indico.modules.events.management.views import WPEventManagement
from indico.web.rh import RH

from indico_ecm.models.credits import AssignmentState, CreditAssignment
from indico_ecm.services import certificates as certificate_service
from indico_ecm.services import eligibility as eligibility_service


class WPECM(WPJinjaMixinPlugin, WPEventManagement):
    sidemenu_option = 'ecm'


class RHECMEventOverview(RHManageEventBase):
    """Per-event ECM dashboard.

    Shows what the rules currently say, next to what has actually been granted:
    the difference between the two columns is the work left to do.
    """

    def _process(self):
        accreditation = self.event.ecm_accreditation
        assignments = (CreditAssignment.query
                       .filter_by(event_id=self.event.id)
                       .order_by(CreditAssignment.id)
                       .all())
        summary = {
            'proposed': sum(1 for a in assignments if a.state == AssignmentState.proposed),
            'approved': sum(1 for a in assignments if a.state == AssignmentState.approved),
            'denied': sum(1 for a in assignments if a.state == AssignmentState.denied),
            'revoked': sum(1 for a in assignments if a.state == AssignmentState.revoked),
        }
        return WPECM.render_template('event_overview.html', self.event, 'ecm', accreditation=accreditation,
                                     assignments=assignments, summary=summary)


class RHECMEvaluate(RHManageEventBase):
    """Re-evaluate every registration and store proposals.

    Read-only with respect to credits: it can only produce proposals, never
    approvals, no matter who or what triggers it.
    """

    def _process(self):
        accreditation = self.event.ecm_accreditation
        if accreditation is None:
            return jsonify(error='no accreditation dossier'), 400
        results = []
        for registration in self.event.registrations:
            if registration.is_deleted:
                continue
            assignment = eligibility_service.propose_assignment(registration, accreditation=accreditation)
            results.append({'registration_id': registration.id, 'state': assignment.state.name,
                            'credits': str(assignment.credits), 'reasons': assignment.reasons})
        return jsonify(count=len(results), results=results)


class RHCertificateVerify(RH):
    """Public verification of a certificate.

    Unauthenticated on purpose — anyone holding the document must be able to
    check it — and deliberately austere: no participant data is returned.
    """

    def _process(self):
        result = certificate_service.verify(request.view_args['token'])
        if result is None:
            return jsonify(valid=False, reason='unknown token'), 404
        return jsonify(**result)
