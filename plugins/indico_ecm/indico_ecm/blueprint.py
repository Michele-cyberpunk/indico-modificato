# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_ecm.controllers import (RHCertificateVerify, RHECMAccreditation, RHECMAssignmentAction,
                                    RHECMAttendance, RHECMAutomator, RHECMCertificateDownload,
                                    RHECMCertificates, RHECMCheckin, RHECMDeliverableToggle, RHECMEvaluate,
                                    RHECMEventOverview, RHECMGuests, RHECMInvitations, RHECMLegacyImport,
                                    RHECMLetters, RHECMParticipants, RHECMProviders, RHECMTransferSheet)


blueprint = IndicoPluginBlueprint('ecm', __name__)

_event = '/event/<int:event_id>/manage/ecm'
blueprint.add_url_rule(f'{_event}/', 'event_overview', RHECMEventOverview)
blueprint.add_url_rule(f'{_event}/accreditation', 'accreditation', RHECMAccreditation,
                       methods=('GET', 'POST'))
blueprint.add_url_rule(f'{_event}/deliverable', 'deliverable_toggle', RHECMDeliverableToggle,
                       methods=('POST',))
blueprint.add_url_rule(f'{_event}/attendance', 'attendance', RHECMAttendance)
blueprint.add_url_rule(f'{_event}/attendance/checkin', 'checkin', RHECMCheckin, methods=('POST',))
blueprint.add_url_rule(f'{_event}/participants', 'participants', RHECMParticipants)
blueprint.add_url_rule(f'{_event}/evaluate', 'evaluate', RHECMEvaluate, methods=('POST',))
blueprint.add_url_rule(f'{_event}/assignments/<int:assignment_id>', 'assignment_action',
                       RHECMAssignmentAction, methods=('POST',))
blueprint.add_url_rule(f'{_event}/certificates', 'certificates', RHECMCertificates,
                       methods=('GET', 'POST'))
blueprint.add_url_rule(f'{_event}/certificates/<int:certificate_id>.pdf', 'certificate_download',
                       RHECMCertificateDownload)
blueprint.add_url_rule(f'{_event}/invitations', 'invitations', RHECMInvitations, methods=('GET', 'POST'))
blueprint.add_url_rule(f'{_event}/invitations/letters', 'letters', RHECMLetters)
blueprint.add_url_rule(f'{_event}/guests', 'guests', RHECMGuests, methods=('GET', 'POST'))
blueprint.add_url_rule(f'{_event}/guests/transfer-sheet', 'transfer_sheet', RHECMTransferSheet)

blueprint.add_url_rule('/admin/ecm/providers', 'providers', RHECMProviders, methods=('GET', 'POST'))
blueprint.add_url_rule('/admin/ecm/import', 'legacy_import', RHECMLegacyImport, methods=('GET', 'POST'))
blueprint.add_url_rule('/admin/ecm/automator', 'automator', RHECMAutomator, methods=('GET', 'POST'))

blueprint.add_url_rule('/ecm/verify/<token>', 'verify_certificate', RHCertificateVerify)
