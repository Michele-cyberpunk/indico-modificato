# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The ECM management area.

Server-rendered pages on top of the services: the dossier, the preparation
checklist, the participants with what the rules say about each of them, the
invitations with their cost, and the certificates.

Every page shows the same two columns of truth: what the rules currently say,
and what has actually been granted. The difference between them is the work
still to do.
"""

import dataclasses
import io
import json
from datetime import date
from operator import itemgetter

from flask import flash, jsonify, redirect, request, session, url_for
from werkzeug.exceptions import Forbidden, NotFound

from indico.core.db import db
from indico.core.plugins import WPJinjaMixinPlugin, url_for_plugin
from indico.modules.admin import RHAdminBase
from indico.modules.admin.views import WPAdmin
from indico.modules.events.management.controllers.base import RHManageEventBase
from indico.modules.events.management.views import WPEventManagement
from indico.modules.events.registration.models.registrations import Registration
from indico.util.date_time import now_utc
from indico.util.i18n import _
from indico.web.flask.util import send_file
from indico.web.rh import RH
from indico.web.views import WPDecorated

from indico_ecm.models.certificates import Certificate, CertificateState
from indico_ecm.models.credits import AssignmentState, CreditAssignment
from indico_ecm.models.deliverables import EventDeliverable, states_for_event
from indico_ecm.models.guests import EventGuest
from indico_ecm.models.operations import EventOperations, InvitationBatch, SpecialReminder
from indico_ecm.models.provider import AccreditationState, ActivityFormat, EventAccreditation, Provider
from indico_ecm.services import attendance as attendance_service
from indico_ecm.services import automator as automator_service
from indico_ecm.services import certificate_render, certificates as certificate_service
from indico_ecm.services import eligibility as eligibility_service
from indico_ecm.services import engagement_letter
from indico_ecm.services import faculty as faculty_service
from indico_ecm.services import guests as guest_service
from indico_ecm.services import archive
from indico_ecm.services import mail_draft
from indico_ecm.services import statistics
from indico_ecm.services import transfer_export
from indico_ecm.services import invitations as invitation_service
from indico_ecm.services.accreditation_mail import AccreditationRequest, build_email, missing_fields
from indico_ecm.services.costs import event_totals, money
from indico_ecm.services.deliverables import Deliverable, DeliverableState, checklist, readiness
from indico_ecm.services.legacy_import import import_archive
from indico_ecm.services.naming import folder_path
from indico_ecm.services.templates import (DOCUMENT_TEMPLATES, MESSAGE_TEMPLATES, TemplateError,
                                           get_template, preview, render_named)


class _ECMStylesheet:
    """Adds the plugin stylesheet to Indico's own.

    The pages are built from Indico's classes; this only carries the few rules
    that have no equivalent there. The blueprint already serves the plugin's
    `static` folder, so no asset bundle is involved.
    """

    def _get_head_content(self):
        href = url_for('plugin_ecm.static', filename='ecm.css')
        link = f'<link rel="stylesheet" type="text/css" href="{href}">'
        return f'{super()._get_head_content()}{link}'


class WPECM(_ECMStylesheet, WPJinjaMixinPlugin, WPEventManagement):
    sidemenu_option = 'ecm'


class WPECMAdmin(_ECMStylesheet, WPJinjaMixinPlugin, WPAdmin):
    sidemenu_option = 'ecm_admin'


class WPCertificateVerify(_ECMStylesheet, WPJinjaMixinPlugin, WPDecorated):
    """The public verification page: no menu, no login."""

    def _get_body(self, params):
        return self._get_page_content(params)


class WPECMSheet(_ECMStylesheet, WPJinjaMixinPlugin, WPDecorated):
    """A sheet meant to be printed and handed to a driver: no menu, no chrome."""

    def _get_body(self, params):
        return self._get_page_content(params)


class RHECMEventBase(RHManageEventBase):
    """Base for the per-event ECM pages."""

    def _process_args(self):
        RHManageEventBase._process_args(self)
        self.accreditation = EventAccreditation.query.filter_by(event_id=self.event.id).first()
        self.operations = EventOperations.query.filter_by(event_id=self.event.id).first()

    def _sponsor(self):
        """The company whose unconditional contribution funds the event.

        It is written on the mail-merge rows, which is where this platform keeps
        it; the CRM holds the company itself, and reading it from here would tie
        the two plugins together for one line of an email.
        """
        row = (InvitationBatch.query
               .filter(InvitationBatch.event_id == self.event.id, InvitationBatch.sponsor != '')
               .first())
        return row.sponsor if row else ''

    def _ensure_operations(self):
        if self.operations is None:
            self.operations = EventOperations(event_id=self.event.id)
            db.session.add(self.operations)
            db.session.flush()
        return self.operations


class RHECMEventOverview(RHECMEventBase):
    """Dossier, checklist and counters in one page."""

    def _process(self):
        states = states_for_event(self.event)
        event_date = self.event.start_dt.date() if self.event.start_dt else None
        statuses = checklist(states, event_date, date.today())
        assignments = CreditAssignment.query.filter_by(event_id=self.event.id).all()
        summary = {state.name: sum(1 for a in assignments if a.state == state) for state in AssignmentState}
        summary['certificates'] = (Certificate.query
                                   .join(CreditAssignment)
                                   .filter(CreditAssignment.event_id == self.event.id,
                                           Certificate.state == CertificateState.issued)
                                   .count())
        reminders = (SpecialReminder.query
                     .filter_by(event_id=self.event.id, dismissed_dt=None)
                     .order_by(SpecialReminder.remind_on)
                     .all())
        return WPECM.render_template('overview.html', self.event, 'ecm',
                                     accreditation=self.accreditation, operations=self.operations,
                                     statuses=statuses, readiness=readiness(states), summary=summary,
                                     reminders=reminders, today=date.today(),
                                     registrations=self.event.registrations.count()
                                     if hasattr(self.event.registrations, 'count')
                                     else len(self.event.registrations))


class RHECMDeliverableToggle(RHECMEventBase):
    """Mark a checklist item done, or put it back."""

    def _process(self):
        name = request.form['deliverable']
        try:
            deliverable = Deliverable(name)
        except ValueError:
            raise NotFound(f'voce sconosciuta: {name}') from None
        row = EventDeliverable.query.filter_by(event_id=self.event.id, deliverable=name).first()
        if row is None:
            row = EventDeliverable(event_id=self.event.id, deliverable=deliverable.value)
            db.session.add(row)
        target = request.form.get('state', DeliverableState.done.value)
        if target == DeliverableState.done.value:
            row.mark_done()
        else:
            row.state = target
            row.done_dt = None
            row.updated_dt = now_utc()
        db.session.commit()
        flash(_('Checklist aggiornata.'), 'success')
        return redirect(url_for_plugin('ecm.event_overview', self.event))


class RHECMAccreditation(RHECMEventBase):
    """The accreditation dossier and the request email."""

    def _process_GET(self):
        request_email = None
        missing = []
        if self.accreditation is not None:
            proposal = self._build_request()
            request_email = build_email(proposal)
            missing = missing_fields(proposal)
        return WPECM.render_template('accreditation.html', self.event, 'ecm',
                                     accreditation=self.accreditation, operations=self.operations,
                                     request_email=request_email, missing=missing,
                                     states=AccreditationState, formats=ActivityFormat,
                                     providers=Provider.query.filter_by(is_active=True).all())

    def _process_POST(self):
        operations = self._ensure_operations()
        form = request.form
        if self.accreditation is None:
            provider_id = form.get('provider_id')
            if not provider_id:
                flash(_('Selezionare un provider.'), 'error')
                return redirect(url_for_plugin('ecm.accreditation', self.event))
            self.accreditation = EventAccreditation(event_id=self.event.id, provider_id=int(provider_id))
            db.session.add(self.accreditation)
        self.accreditation.activity_code = form.get('activity_code', '').strip()
        self.accreditation.rule_version = form.get('rule_version', '').strip()
        if form.get('credits'):
            self.accreditation.credits = form['credits']
        if form.get('max_participants'):
            self.accreditation.max_participants = int(form['max_participants'])
        if form.get('activity_format'):
            self.accreditation.activity_format = ActivityFormat[form['activity_format']]
        if form.get('state'):
            new_state = AccreditationState[form['state']]
            if new_state == AccreditationState.accredited and self.accreditation.accredited_dt is None:
                self.accreditation.accredited_dt = now_utc()
            self.accreditation.state = new_state
        operations.event_code = form.get('event_code', operations.event_code).strip()
        operations.folder_name = form.get('folder_name', operations.folder_name).strip()
        operations.accreditation_contact = form.get('accreditation_contact', '').strip()
        operations.accreditation_to = form.get('accreditation_to', '').strip()
        operations.accreditation_cc = form.get('accreditation_cc', '').strip()
        operations.updated_dt = now_utc()
        db.session.commit()
        flash(_('Dossier aggiornato.'), 'success')
        return redirect(url_for_plugin('ecm.accreditation', self.event))

    def _build_request(self):
        operations = self.operations
        return AccreditationRequest(
            event_name=self.event.title,
            event_date=self.event.start_dt.date() if self.event.start_dt else None,
            end_date=self.event.end_dt.date() if self.event.end_dt else None,
            place=(self.event.venue_name or ''),
            sponsor=(self.accreditation.provider.name if self.accreditation else ''),
            event_code=(operations.event_code if operations else ''),
            folder_name=(operations.folder_name if operations else ''),
            recipient_label=(operations.accreditation_contact if operations else 'ECM') or 'ECM',
            recipient_email=(operations.accreditation_to if operations else ''),
            cc=tuple(filter(None, (operations.accreditation_cc,))) if operations else (),
            sender_name=session.user.full_name if session.user else '',
        )


class RHECMParticipants(RHECMEventBase):
    """What the rules say about every participant, next to what was granted."""

    def _process(self):
        rows = []
        program_minutes = None
        for registration in self.event.registrations:
            if registration.is_deleted:
                continue
            assignment = (CreditAssignment.query
                          .filter(CreditAssignment.registration_id == registration.id,
                                  CreditAssignment.state != AssignmentState.revoked)
                          .first())
            outcome = None
            if self.accreditation is not None:
                try:
                    outcome = eligibility_service.evaluate_registration(registration,
                                                                        accreditation=self.accreditation)
                    program_minutes = outcome.program_minutes
                except ValueError:
                    outcome = None
            rows.append({
                'registration': registration,
                'assignment': assignment,
                'outcome': outcome,
                'open_attendance': len(attendance_service.open_attendance(registration)),
                'certificate': (Certificate.query
                                .filter(Certificate.assignment_id == assignment.id,
                                        Certificate.state != CertificateState.revoked)
                                .first() if assignment else None),
            })
        return WPECM.render_template('participants.html', self.event, 'ecm', rows=rows,
                                     accreditation=self.accreditation, program_minutes=program_minutes)


class RHECMEvaluate(RHECMEventBase):
    """Re-evaluate everyone and store proposals. Never grants anything."""

    def _process(self):
        if self.accreditation is None:
            flash(_('Serve prima un dossier di accreditamento.'), 'error')
            return redirect(url_for_plugin('ecm.event_overview', self.event))
        count = 0
        for registration in self.event.registrations:
            if registration.is_deleted:
                continue
            eligibility_service.propose_assignment(registration, accreditation=self.accreditation)
            count += 1
        db.session.commit()
        flash(_('Valutate {count} iscrizioni.').format(count=count), 'success')
        return redirect(url_for_plugin('ecm.participants', self.event))


class RHECMAssignmentAction(RHECMEventBase):
    """Approve or revoke one assignment. The only place credits are granted."""

    def _process_args(self):
        RHECMEventBase._process_args(self)
        self.assignment = CreditAssignment.query.filter_by(id=request.view_args['assignment_id'],
                                                           event_id=self.event.id).first()
        if self.assignment is None:
            raise NotFound

    def _process(self):
        action = request.form.get('action')
        try:
            if action == 'approve':
                eligibility_service.approve_assignment(self.assignment, user=session.user)
                flash(_('Crediti approvati.'), 'success')
            elif action == 'revoke':
                reason = request.form.get('reason', '').strip()
                eligibility_service.revoke_assignment(self.assignment, user=session.user, reason=reason)
                flash(_('Assegnazione revocata.'), 'success')
            else:
                raise NotFound(f'azione sconosciuta: {action}')
        except (ValueError, eligibility_service.NotAuthorized) as exc:
            db.session.rollback()
            flash(str(exc), 'error')
        else:
            db.session.commit()
        return redirect(url_for_plugin('ecm.participants', self.event))


def render_certificate_pdf(certificate, *, event, provider):
    """Render one certificate, resolving the participant from the assignment."""
    registration = certificate.assignment.registration
    profile = eligibility_service.find_hcp_profile(registration)
    url = url_for_plugin('ecm.verify_certificate', token=certificate.verification_token, _external=True)
    return certificate_render.render_certificate(
        certificate,
        provider=provider,
        participant_name=f'{registration.first_name} {registration.last_name}'.strip(),
        event=event,
        verification_url=url,
        profession=(profile.profession if profile else ''),
        discipline=(profile.discipline if profile else ''),
        issued_on=(certificate.issued_dt.date() if certificate.issued_dt else date.today()),
    )


class RHECMCertificates(RHECMEventBase):
    """Prepare, issue and download certificates."""

    def _process_GET(self):
        certificates = (Certificate.query
                        .join(CreditAssignment)
                        .filter(CreditAssignment.event_id == self.event.id)
                        .order_by(Certificate.number)
                        .all())
        approved = (CreditAssignment.query
                    .filter_by(event_id=self.event.id, state=AssignmentState.approved)
                    .count())
        return WPECM.render_template('certificates.html', self.event, 'ecm',
                                     certificates=certificates, approved=approved,
                                     accreditation=self.accreditation)

    def _process_POST(self):
        if self.accreditation is None or self.accreditation.provider is None:
            flash(_('Serve un dossier con un provider.'), 'error')
            return redirect(url_for_plugin('ecm.certificates', self.event))
        issued = 0
        for assignment in CreditAssignment.query.filter_by(event_id=self.event.id,
                                                           state=AssignmentState.approved):
            certificate = certificate_service.prepare_certificate(assignment,
                                                                  provider=self.accreditation.provider)
            if certificate.state == CertificateState.issued:
                continue
            pdf, digest = render_certificate_pdf(certificate, event=self.event,
                                                 provider=self.accreditation.provider)
            certificate_service.issue_certificate(certificate, user=session.user, file_content=pdf)
            certificate.content_hash = digest
            issued += 1
        db.session.commit()
        flash(_('Emessi {count} attestati.').format(count=issued), 'success')
        return redirect(url_for_plugin('ecm.certificates', self.event))


class RHECMCertificateDownload(RHECMEventBase):
    """Re-render and download one certificate.

    The document is produced from the stored data every time rather than kept as
    a blob: what is downloaded always matches the record, and the hash proves it.
    """

    def _process_args(self):
        RHECMEventBase._process_args(self)
        self.certificate = (Certificate.query
                            .join(CreditAssignment)
                            .filter(Certificate.id == request.view_args['certificate_id'],
                                    CreditAssignment.event_id == self.event.id)
                            .first())
        if self.certificate is None:
            raise NotFound

    def _process(self):
        provider = self.accreditation.provider if self.accreditation else None
        pdf, _digest = render_certificate_pdf(self.certificate, event=self.event, provider=provider)
        return send_file(f'{self.certificate.number}.pdf', io.BytesIO(pdf), 'application/pdf')


class RHECMInvitations(RHECMEventBase):
    """The mail merge: rows, costs and letters."""

    def _process_GET(self):
        rows = (InvitationBatch.query
                .filter_by(event_id=self.event.id)
                .order_by(InvitationBatch.hospital)
                .all())
        sheets = []
        for row in rows:
            from indico_ecm.services.costs import CostSheet
            data = row.costs or {}
            sheets.append(CostSheet(physicians=row.physician_count, room=money(data.get('room')),
                                    city_tax=money(data.get('city_tax')),
                                    catering=money(data.get('catering')),
                                    travel=money(data.get('travel'))))
        totals = event_totals(sheets)
        budget = self.operations.hospitality_budget if self.operations else None
        return WPECM.render_template('invitations.html', self.event, 'ecm', rows=rows, totals=totals,
                                     budget=budget, missing=invitation_service.check_template(self.event))

    def _process_POST(self):
        upload = request.files.get('spreadsheet')
        if upload is None or not upload.filename:
            flash(_('Nessun file selezionato.'), 'error')
            return redirect(url_for_plugin('ecm.invitations', self.event))
        rows = invitation_service.read_rows(upload.read(), filename=upload.filename)
        created, issues = invitation_service.import_rows(self.event, rows,
                                                         replace=bool(request.form.get('replace')))
        db.session.commit()
        flash(_('Importate {count} righe ({issues} segnalazioni).').format(count=len(created),
                                                                          issues=len(issues)),
              'success' if not issues else 'warning')
        for issue in issues[:10]:
            flash(f'riga {issue.row}: {issue.field} — {issue.message}', 'warning')
        return redirect(url_for_plugin('ecm.invitations', self.event))


class RHECMMessages(RHECMEventBase):
    """Every message the platform can write, filled in with this event.

    The templates were reachable only through an agent, and the agents are off
    until someone turns them on: in practice most of them could not be seen at
    all. They are shown here with the event's own data, and what a template
    still needs is named rather than left blank.
    """

    def _hotel_services_html(self):
        """The hotel brief, deduced from the programme of this event.

        The same deduction the agent tool does: the timetable titles plus the
        description are what a sponsor writes the programme in, and the
        keywords decide what the hotel has to prepare.
        """
        from indico_ecm.services.attendance import event_session_blocks
        from indico_ecm.services.hotel import brief_lines, deduce

        event = self.event
        programme_text = '\n'.join(filter(None, ((block.full_title or '')
                                                 for block in event_session_blocks(event))))
        source = f'{event.title}\n{event.description or ""}\n{programme_text}'.strip()
        services = deduce(source,
                          start_time=(event.start_dt.strftime('%H:%M') if event.start_dt else ''),
                          end_time=(event.end_dt.strftime('%H:%M') if event.end_dt else ''))
        return '<br>' + '<br>'.join(brief_lines(services))

    def _context(self):
        event = self.event
        accreditation = self.accreditation
        operations = self.operations
        date_text = event.start_dt.strftime('%d/%m/%Y') if event.start_dt else ''
        code = (operations.event_code if operations else '') or ''
        return {
            'event_name': event.title,
            'event_code': code,
            'event_date': date_text,
            'date_text': date_text,
            'event_place': event.venue_name or '',
            'place': event.venue_name or '',
            'city': event.venue_name or '',
            'hotel_name': event.venue_name or '',
            'access_code': ''.join(char for char in code if char.isdigit()),
            'credits': str(accreditation.credits) if accreditation and accreditation.credits else '',
            'participants': (str(accreditation.max_participants)
                             if accreditation and accreditation.max_participants else ''),
            'agenas_code': accreditation.activity_code if accreditation else '',
            'start_time': event.start_dt.strftime('%H:%M') if event.start_dt else '',
            'end_time': event.end_dt.strftime('%H:%M') if event.end_dt else '',
            'event_type': (accreditation.activity_format.title
                           if accreditation and accreditation.activity_format else ''),
            'sender_name': session.user.full_name if session.user else '',
            'sponsor': self._sponsor(),
            'services': self._hotel_services_html(),
        }
        context = self._context()
        wanted = request.args.get('draft')
        if wanted:
            return self._download_draft(wanted, context)
        messages = [preview(template, context)
                    for _, template in sorted(MESSAGE_TEMPLATES.items())]
        catalogue = {name: template for name, template in MESSAGE_TEMPLATES.items()}
        return WPECM.render_template('messages.html', self.event, 'ecm',
                                     messages=messages, catalogue=catalogue,
                                     documents=DOCUMENT_TEMPLATES)

    def _download_draft(self, name, context):
        """The message as a `.eml`, which the mail client opens as a draft.

        Nothing is sent: no outgoing server is configured, and this is how the
        previous event manager worked too — it wrote the file and let the
        default client open it, so a person reads the message before it leaves.
        """
        try:
            template = get_template(name)
        except TemplateError:
            raise NotFound from None
        message = preview(template, context)
        if message['missing']:
            flash(_('Mancano dei valori: {fields}.').format(fields=', '.join(message['missing'])),
                  'error')
            return redirect(url_for_plugin('ecm.messages', self.event))
        filename, content = mail_draft.from_message(
            message, sender=session.user.email if session.user else '')
        return send_file(filename, io.BytesIO(content), 'message/rfc822', inline=False)


class RHECMFaculty(RHECMEventBase):
    """The faculty of the event, and the two documents each speaker receives.

    The people come from Indico. What the paperwork adds — role, fee, letter
    number, tax code — is answered here and used straight away: a fee typed to
    print one letter is not a record worth keeping, and storing it would mean a
    table that nothing else reads.
    """

    def _speakers(self):
        """The faculty, with the answers given on the form applied on top."""
        people = []
        for speaker in faculty_service.read_faculty(self.event):
            key = speaker.person_id
            gender = request.form.get(f'gender-{key}', '')
            people.append(dataclasses.replace(
                speaker,
                gender=gender if gender in ('M', 'F') else ('' if gender == 'unknown' else speaker.gender),
                title=request.form.get(f'title-{key}') or speaker.title,
                role=request.form.get(f'role-{key}') or speaker.role,
                fee=request.form.get(f'fee-{key}', ''),
                tax_code=request.form.get(f'tax_code-{key}', ''),
                birth_date=request.form.get(f'birth_date-{key}', ''),
                letter_number=request.form.get(f'letter_number-{key}', ''),
                has_vat_number=bool(request.form.get(f'vat-{key}')),
            ))
        return people

    def _context_args(self):
        accreditation = self.accreditation
        return {
            'activity_code': accreditation.activity_code if accreditation else '',
            'format_label': (accreditation.activity_format.title
                             if accreditation and accreditation.activity_format else ''),
            'project_code': self.operations.event_code if self.operations else '',
        }

    def _render(self, speakers=None, invitation=None):
        speakers = speakers if speakers is not None else faculty_service.read_faculty(self.event)
        return WPECM.render_template(
            'faculty.html', self.event, 'ecm', speakers=speakers, invitation=invitation,
            titles=engagement_letter.TITLE_CHOICES,
            missing=faculty_service.check_template(speakers, event=self.event,
                                                   **self._context_args()))

    def _process_GET(self):
        return self._render()

    def _process_POST(self):
        speakers = self._speakers()
        if not speakers:
            flash(_('Questo evento non ha ancora relatori: aggiungili da Indico.'), 'error')
            return redirect(url_for_plugin('ecm.faculty', self.event))

        if request.form.get('action') == 'invite':
            return self._render(speakers, invitation=self._draft_invitations(speakers))

        count, archive = faculty_service.render_batch(speakers, event=self.event,
                                                      **self._context_args())
        name = f'lettere-incarico-{self.event.id}.zip'
        return send_file(name, io.BytesIO(archive), 'application/zip', inline=False)

    def _draft_invitations(self, speakers):
        """The invitation email for each speaker, ready to be copied out.

        Drafted rather than sent: no outgoing channel is configured, and a page
        that says "sent" without sending would be worse than one that hands the
        text over.
        """
        drafts = []
        for speaker in speakers:
            abbreviation = engagement_letter.title_abbreviation(
                faculty_service.resolve_gender(speaker), speaker.title)
            drafts.append({
                'speaker': speaker,
                'message': render_named('speaker_invitation', {
                    'event_name': self.event.title,
                    'role': speaker.role,
                    'salutation': f'{abbreviation} {speaker.full_name}'.strip(),
                    'sponsor': self._sponsor(),
                    'date_text': self.event.start_dt.strftime('%d/%m/%Y') if self.event.start_dt else '',
                    'place': self.event.venue_name or '',
                    'sender_name': session.user.full_name if session.user else '',
                }),
            })
        return drafts


class RHECMLetters(RHECMEventBase):
    """Generate every invitation letter as one archive."""

    def _process(self):
        count, archive = invitation_service.render_batch(
            self.event, user_name=session.user.full_name if session.user else '')
        db.session.commit()
        if not count:
            flash(_('Nessuna riga di stampa unione.'), 'error')
            return redirect(url_for_plugin('ecm.invitations', self.event))
        name = f'lettere-invito-{self.event.id}.zip'
        return send_file(name, io.BytesIO(archive), 'application/zip', inline=False)


class RHECMGuests(RHECMEventBase):
    """The sponsor's participant list, turned into transfers and covers.

    Upload the list, see what the rules read and what they rejected and why,
    then the shuttle runs and the meal counts. No model is involved: a
    participant list is short, formulaic text and rules read it predictably.
    """

    def _config(self):
        return guest_service.TransferConfig(
            strategy=(self.operations.transfer_strategy if self.operations else None) or 'vehicle',
            window=(self.operations.transfer_window if self.operations else None) or 60,
            seats_per_vehicle=(self.operations.seats_per_vehicle if self.operations else None) or 8)

    def _render(self, rejected=()):
        rows = self.event.ecm_guests.order_by(EventGuest.last_name, EventGuest.first_name).all()
        guests = [row.to_guest() for row in rows]
        config = self._config()
        return WPECM.render_template(
            'guests.html', self.event, 'ecm', rows=rows, rejected=rejected,
            categories=guest_service.categorize(guests), config=config,
            arrivals=guest_service.group_transfers(guests, config, arrival=True),
            departures=guest_service.group_transfers(guests, config, arrival=False),
            oversized=guest_service.oversized_parties(guests, config))

    def _process_GET(self):
        return self._render()

    def _process_POST(self):
        action = request.form.get('action', 'import')
        if action == 'swap':
            row = EventGuest.query.filter_by(id=request.form.get('guest_id', type=int),
                                             event_id=self.event.id).first_or_404()
            row.first_name, row.last_name = row.last_name, row.first_name
            row.name_order_certain = True
            db.session.commit()
            return redirect(url_for_plugin('ecm.guests', self.event))
        if action == 'delete':
            EventGuest.query.filter_by(id=request.form.get('guest_id', type=int),
                                       event_id=self.event.id).delete()
            db.session.commit()
            return redirect(url_for_plugin('ecm.guests', self.event))
        if action == 'settings':
            operations = self._ensure_operations()
            operations.transfer_strategy = request.form.get('strategy', 'vehicle')
            operations.transfer_window = request.form.get('window', type=int) or 60
            operations.seats_per_vehicle = request.form.get('seats', type=int) or 8
            db.session.commit()
            flash(_('Impostazioni dei transfer aggiornate.'), 'success')
            return redirect(url_for_plugin('ecm.guests', self.event))

        upload = request.files.get('list')
        text = request.form.get('text', '').strip()
        if upload is not None and upload.filename:
            try:
                lines = guest_service.read_list(upload.read(), upload.filename)
            except Exception as exc:
                flash(f'{upload.filename}: {exc}', 'error')
                return redirect(url_for_plugin('ecm.guests', self.event))
        elif text:
            lines = text.splitlines()
        else:
            flash(_('Incolla la lista o carica un file.'), 'error')
            return redirect(url_for_plugin('ecm.guests', self.event))

        if request.form.get('replace'):
            EventGuest.query.filter_by(event_id=self.event.id).delete()
        guests, rejected = guest_service.import_guest_list(lines)
        for guest in guests:
            source = lines[guest.row_number - 1] if 0 < guest.row_number <= len(lines) else ''
            db.session.add(EventGuest.from_extraction(self.event.id, guest, source_row=source))
        db.session.commit()
        flash(_('{count} ospiti importati, {rejected} righe scartate.').format(
            count=len(guests), rejected=len(rejected)), 'success')
        return self._render(rejected=rejected)


class RHECMTransferExport(RHECMEventBase):
    """The guest list as the spreadsheet the office forwards.

    Same two sheets and same columns as the previous event manager, plus one
    with the itineraries: a driver reads one block per run.
    """

    def _process(self):
        rows = self.event.ecm_guests.order_by(EventGuest.last_name, EventGuest.first_name).all()
        guests = [row.to_guest() for row in rows]
        if not guests:
            flash(_('Nessun ospite in lista.'), 'error')
            return redirect(url_for_plugin('ecm.guests', self.event))
        config = guest_service.TransferConfig(
            strategy=(self.operations.transfer_strategy if self.operations else None) or 'vehicle',
            window=(self.operations.transfer_window if self.operations else None) or 60,
            seats_per_vehicle=(self.operations.seats_per_vehicle if self.operations else None) or 8)
        content = transfer_export.build_workbook(
            guests,
            arrivals=guest_service.group_transfers(guests, config, arrival=True),
            departures=guest_service.group_transfers(guests, config, arrival=False),
            event_date=self.event.start_dt.date() if self.event.start_dt else None,
            return_date=self.event.end_dt.date() if self.event.end_dt else None)
        return send_file(transfer_export.filename_for(self.event.id), io.BytesIO(content),
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         inline=False)


class RHECMTransferSheet(RHECMEventBase):
    """The shuttle sheet the driver is handed, as a printable page."""

    def _process(self):
        rows = self.event.ecm_guests.order_by(EventGuest.last_name, EventGuest.first_name).all()
        guests = [row.to_guest() for row in rows]
        config = guest_service.TransferConfig(
            strategy=(self.operations.transfer_strategy if self.operations else None) or 'vehicle',
            window=(self.operations.transfer_window if self.operations else None) or 60,
            seats_per_vehicle=(self.operations.seats_per_vehicle if self.operations else None) or 8)
        arrival = request.args.get('direction', 'arrival') != 'departure'
        return WPECMSheet.render_template(
            'transfer_sheet.html', event=self.event, arrival=arrival,
            groups=guest_service.group_transfers(guests, config, arrival=arrival),
            categories=guest_service.categorize(guests), today=date.today())


class RHECMAttendance(RHECMEventBase):
    """Per-session attendance, and the anomalies in it."""

    def _process(self):
        program = attendance_service.build_program(self.event)
        rows = []
        for registration in self.event.registrations:
            if registration.is_deleted:
                continue
            intervals = attendance_service.build_intervals(registration)
            open_rows = attendance_service.open_attendance(registration)
            minutes = sum(interval.minutes for interval in intervals)
            rows.append({'registration': registration, 'minutes': minutes,
                         'intervals': len(intervals), 'open': len(open_rows)})
        rows.sort(key=itemgetter('minutes'))
        return WPECM.render_template('attendance.html', self.event, 'ecm', rows=rows, program=program)


class RHECMCheckin(RHECMEventBase):
    """Record an entry or an exit, from the desk or from a scanner."""

    def _process(self):
        registration = Registration.query.filter_by(id=request.form.get('registration_id', type=int),
                                                    event_id=self.event.id).first()
        if registration is None:
            return jsonify(error='iscrizione non trovata'), 404
        block = None
        block_id = request.form.get('session_block_id', type=int)
        if block_id:
            from indico.modules.events.sessions.models.blocks import SessionBlock
            block = SessionBlock.get(block_id)
            if block is None or block.session.event_id != self.event.id:
                return jsonify(error='sessione non valida'), 400
        direction = request.form.get('direction', 'in')
        if direction == 'in':
            row = attendance_service.check_in(registration, session_block=block, user=session.user)
        else:
            row = attendance_service.check_out(registration, session_block=block)
            if row is None:
                return jsonify(error='nessuna presenza aperta'), 409
        db.session.commit()
        return jsonify(id=row.id, check_in=row.check_in_dt.isoformat(),
                       check_out=row.check_out_dt.isoformat() if row.check_out_dt else None)


class RHCertificateVerify(RH):
    """Public verification. No login, and no personal data in the answer."""

    CSRF_ENABLED = False

    def _process(self):
        result = certificate_service.verify(request.view_args['token'])
        if request.args.get('format') == 'json':
            if result is None:
                return jsonify(valid=False, reason='unknown token'), 404
            return jsonify(**result)
        return WPCertificateVerify.render_template('verify.html', result=result)


class RHECMReports(RHAdminBase):
    """How the year is going, across every accredited event.

    The figures are the ones the previous event manager reported — events,
    participants, credits, how far the preparation got, and which events have
    something late — computed over the platform's own records.
    """

    def _records(self):
        today = date.today()
        records = []
        for accreditation in EventAccreditation.query.all():
            event = accreditation.event
            if event is None or event.is_deleted:
                continue
            states = states_for_event(event)
            event_date = event.start_dt.date() if event.start_dt else None
            late = sum(1 for status in checklist(states, event_date, today)
                       if status.needs_attention)
            issued = (Certificate.query
                      .join(CreditAssignment)
                      .filter(CreditAssignment.event_id == event.id,
                              Certificate.state == CertificateState.issued)
                      .count())
            records.append(statistics.EventRecord(
                id=event.id,
                title=event.title,
                day=event_date,
                city=event.venue_name or '',
                credits=float(accreditation.credits or 0),
                participants=int(accreditation.max_participants or 0),
                readiness=readiness(states),
                late=late,
                certificates=issued,
            ))
        return records

    def _process(self):
        report = statistics.build(self._records())
        if request.args.get('format') == 'xlsx':
            content = statistics.as_xlsx(report)
            return send_file(f'report-ecm-{date.today():%Y%m%d}.xlsx', io.BytesIO(content),
                             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             inline=False)
        return WPECMAdmin.render_template('reports.html', 'ecm_admin', report=report)


class RHECMArchiveExport(RHAdminBase):
    """The whole archive as JSON, in the shape the importer reads back.

    Round-trip on purpose: an export nobody can import is a copy, not a backup.
    """

    def _process(self):
        events = []
        for accreditation in EventAccreditation.query.all():
            event = accreditation.event
            if event is None or event.is_deleted:
                continue
            operations = EventOperations.query.filter_by(event_id=event.id).first()
            events.append({
                'title': event.title,
                'event_code': operations.event_code if operations else '',
                'start_date': event.start_dt.date() if event.start_dt else None,
                'end_date': event.end_dt.date() if event.end_dt else None,
                'city': event.venue_name or '',
                'venue': event.venue_name or '',
                # str(): the enum title is a lazily translated string, and the
                # archive is JSON.
                'activity_format': (str(accreditation.activity_format.title)
                                    if accreditation.activity_format else ''),
                # str(): credits is numeric, and the archive is JSON.
                'credits': str(accreditation.credits) if accreditation.credits else '',
                'max_participants': accreditation.max_participants or '',
                'activity_code': accreditation.activity_code or '',
                'folder_name': operations.folder_name if operations else '',
                'time_range': (f"{event.start_dt:%H:%M} - {event.end_dt:%H:%M}"
                               if event.start_dt and event.end_dt else ''),
                'deliverables': states_for_event(event),
                'faculty': [{'name': link.full_name, 'email': link.email or ''}
                            for link in event.person_links],
            })

        invitations = [{
            'hospital': row.hospital, 'recipient': row.recipient,
            'recipient_email': row.recipient_email, 'cc_email': row.cc_email,
            'department': row.department, 'specialty': row.specialty, 'role': row.role,
            'physician_count': row.physician_count, 'sponsor': row.sponsor,
            'notes': row.notes, 'costs': row.costs,
        } for row in InvitationBatch.query.all()]

        reminders = [{
            'title': row.title, 'remind_on': row.remind_on, 'notes': row.notes,
            'event_title': row.event.title if row.event else '',
        } for row in SpecialReminder.query.all()]

        content = archive.dumps(archive.build(events=events, invitations=invitations,
                                              reminders=reminders))
        return send_file(archive.filename_for(), io.BytesIO(content), 'application/json',
                         inline=False)


class RHECMLegacyImport(RHAdminBase):
    """Import the archive of the previous event manager."""

    def _process_GET(self):
        return WPECMAdmin.render_template('legacy_import.html', 'ecm_admin', result=None)

    def _process_POST(self):
        upload = request.files.get('archive')
        if upload is None or not upload.filename:
            flash(_('Nessun file selezionato.'), 'error')
            return redirect(url_for_plugin('ecm.legacy_import'))
        try:
            data = json.loads(upload.read().decode('utf-8-sig'))
        except (ValueError, UnicodeDecodeError) as exc:
            flash(_('File non leggibile: {error}').format(error=exc), 'error')
            return redirect(url_for_plugin('ecm.legacy_import'))
        result = import_archive(data)
        return WPECMAdmin.render_template('legacy_import.html', 'ecm_admin', result=result,
                                          folder_path=folder_path)


class RHECMAutomator(RHAdminBase):
    """Paste the sponsor's email, drop in the attachments, get the event folder.

    The extraction is deterministic and says where every value came from; what
    it could not work out is listed rather than invented. Nothing is created in
    Indico here: the output is the folder archive the office already files on
    the shared drive.
    """

    def _process_GET(self):
        return WPECMAdmin.render_template('automator.html', 'ecm_admin', extraction=None, form={})

    def _process_POST(self):
        form = {key: request.form.get(key, '').strip()
                for key in ('text', 'event_name', 'sponsor', 'place', 'city')}
        sources = [form['text']] if form['text'] else []
        unreadable = []
        for upload in request.files.getlist('documents'):
            if not upload.filename:
                continue
            try:
                sources.append(automator_service.read_document(upload.read(), upload.filename))
            except Exception as exc:
                # a corrupt or unsupported attachment must not lose the other material
                unreadable.append(f'{upload.filename}: {exc}')
        if not sources:
            flash(_('Incolla del testo o carica almeno un documento leggibile.'), 'error')
            return redirect(url_for_plugin('ecm.automator'))

        for problem in unreadable:
            flash(problem, 'warning')

        text = '\n\n'.join(sources)
        extraction = automator_service.extract(text, known_sponsor=form['sponsor'],
                                               known_location=form['place'] or form['city'])
        folder = automator_service.folder_name_for(extraction, event_name=form['event_name'],
                                                   city=form['city'] or form['place'])
        if request.form.get('download'):
            _folder, archive = automator_service.build_folder_archive(
                extraction, event_name=form['event_name'], sponsor=form['sponsor'],
                place=form['place'], city=form['city'])
            return send_file(f'{folder or "evento"}.zip', io.BytesIO(archive), 'application/zip',
                             inline=False)
        return WPECMAdmin.render_template('automator.html', 'ecm_admin', extraction=extraction,
                                          folder=folder, form=form, source_length=len(text),
                                          files=automator_service.build_folder_files(
                                              extraction, event_name=form['event_name'],
                                              sponsor=form['sponsor'], place=form['place']))


class RHECMProviders(RHAdminBase):
    """The providers, and their certificate numbering prefix."""

    def _process_GET(self):
        return WPECMAdmin.render_template('providers.html', 'ecm_admin',
                                          providers=Provider.query.order_by(Provider.name).all())

    def _process_POST(self):
        form = request.form
        provider = Provider(name=form['name'].strip(), provider_code=form.get('provider_code', '').strip(),
                            region=form.get('region', '').strip(),
                            contact_email=form.get('contact_email', '').strip(),
                            settings={'certificate_prefix': form.get('certificate_prefix', 'ECM').strip()})
        if not provider.name:
            raise Forbidden('nome obbligatorio')
        db.session.add(provider)
        db.session.commit()
        flash(_('Provider creato.'), 'success')
        return redirect(url_for_plugin('ecm.providers'))
