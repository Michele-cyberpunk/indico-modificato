# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.db import db
from indico.core.db.sqlalchemy import UTCDateTime
from indico.util.date_time import now_utc
from indico.util.string import format_repr


class EventOperations(db.Model):
    """The operational record of an event.

    Everything the provider tracks about an event that Indico has no field for:
    the event code, the shared-drive folder, who to write to for accreditation
    and which supplier handles what. One row per event, created on demand.

    These are the columns of the legacy event table that are neither Indico
    attributes nor checklist flags, kept under their own names so the import is
    a straight copy.
    """

    __tablename__ = 'event_operations'
    __table_args__ = (db.Index('ix_uq_event_operations_event', 'event_id', unique=True),
                      db.Index('ix_event_operations_code', 'event_code'),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        nullable=False
    )
    #: Internal code, e.g. 0116_GDBO
    event_code = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Folder on the shared drive
    folder_name = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Opening hours as written on the programme, e.g. '09:00-17:00'
    schedule_text = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Person at the accreditation office the request is addressed to
    accreditation_contact = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    accreditation_to = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    accreditation_cc = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    accreditation_bcc = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    accreditation_subject = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    accreditation_body = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: Suppliers
    platform_email = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    designer_email = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    hostess_email = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: A date or venue change is tracked because it invalidates work already done
    date_changed = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    previous_date = db.Column(
        db.Date,
        nullable=True
    )
    venue_changed = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    include_in_report = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )
    programme_ref = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    task_email_note = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    notes = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: Sponsor budget for hospitality, checked against the invitation cost sheets
    hospitality_budget = db.Column(
        db.Numeric(precision=12, scale=2),
        nullable=True
    )
    #: Values of the legacy record that have no home yet, kept rather than lost
    legacy_data = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    updated_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('ecm_operations', uselist=False, lazy=True, cascade='all, delete-orphan')
    )

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', _text=self.event_code)


class SpecialReminder(db.Model):
    """A reminder attached to an event by its code.

    Ported from the "promemoria speciali" of the legacy application, with one
    change: a reminder stays due until someone dismisses it, instead of
    appearing only on its exact day.
    """

    __tablename__ = 'special_reminders'
    __table_args__ = (db.Index('ix_special_reminders_due', 'remind_on', 'dismissed_dt'),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=True
    )
    #: Kept for reminders imported before their event exists in the platform
    event_code = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    task = db.Column(
        db.String,
        nullable=False
    )
    remind_on = db.Column(
        db.Date,
        nullable=False
    )
    assignee_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    notes = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: Set when the checklist generated it, so it is not duplicated
    source_deliverable = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    dismissed_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    dismissed_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('ecm_reminders', lazy='dynamic')
    )
    assignee = db.relationship(
        'User',
        lazy=True,
        foreign_keys=assignee_id
    )

    @property
    def is_open(self):
        return self.dismissed_dt is None

    def dismiss(self, user=None):
        self.dismissed_dt = now_utc()
        if user is not None:
            self.dismissed_by_id = user.id

    def __repr__(self):
        return format_repr(self, 'id', 'event_code', 'remind_on', _text=self.task)


class InvitationBatch(db.Model):
    """One mail merge run: the hospitals invited to an event and what it costs.

    The legacy application kept these rows in a spreadsheet next to the letters.
    Storing them means the sponsor budget of an event can be answered without
    reopening the file.
    """

    __tablename__ = 'invitation_rows'
    __table_args__ = (db.Index('ix_invitation_rows_event', 'event_id'),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        nullable=False
    )
    hospital = db.Column(
        db.String,
        nullable=False
    )
    #: CRM company, when the hospital has been matched to one
    company_id = db.Column(
        db.Integer,
        index=True,
        nullable=True
    )
    recipient = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    recipient_email = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    cc_email = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    department = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    specialty = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    role = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    physician_count = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )
    sponsor = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: The cost sheet, as produced by `services.costs.CostSheet.as_dict`
    costs = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    notes = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    letter_generated_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    sent_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('ecm_invitations', lazy='dynamic', cascade='all, delete-orphan')
    )

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', 'physician_count', _text=self.hospital)
