# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.db import db
from indico.core.db.sqlalchemy import PyIntEnum, UTCDateTime
from indico.util.date_time import now_utc
from indico.util.enum import RichIntEnum
from indico.util.i18n import _
from indico.util.string import format_repr


class ActivityKind(RichIntEnum):
    __titles__ = [None, _('Chiamata'), _('Incontro'), _('Email'), _('Nota'), _('Attività'), _('Messaggio')]
    call = 1
    meeting = 2
    email = 3
    note = 4
    task = 5
    message = 6


class ActivityStatus(RichIntEnum):
    __titles__ = [None, _('Da fare'), _('Completata'), _('Annullata')]
    open = 1
    done = 2
    cancelled = 3


class Activity(db.Model):
    """Anything that happened, or has to happen, on a CRM record.

    Calls, meetings, emails, notes and tasks share one table so the timeline of
    a contact can be built with a single query. `created_by_agent_run_id` marks
    the rows an agent produced, which is what makes agent activity auditable
    next to human activity.
    """

    __tablename__ = 'activities'
    __table_args__ = (db.CheckConstraint('contact_id IS NOT NULL OR company_id IS NOT NULL OR '
                                         'opportunity_id IS NOT NULL OR event_id IS NOT NULL',
                                         'has_subject'),
                      db.CheckConstraint('(status = 2) = (done_dt IS NOT NULL)', 'dt_set_when_done'),
                      {'schema': 'plugin_crm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    kind = db.Column(
        PyIntEnum(ActivityKind),
        nullable=False
    )
    status = db.Column(
        PyIntEnum(ActivityStatus),
        nullable=False,
        default=ActivityStatus.open
    )
    subject = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    description = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    contact_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.contacts.id'),
        index=True,
        nullable=True
    )
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.companies.id'),
        index=True,
        nullable=True
    )
    opportunity_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.opportunities.id'),
        index=True,
        nullable=True
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=True
    )
    #: The person responsible for the activity
    assignee_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    due_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    done_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    #: Set when an agent created the activity; NULL means a human did
    created_by_agent_run_id = db.Column(
        db.Integer,
        index=True,
        nullable=True
    )

    contact = db.relationship(
        'Contact',
        lazy=True,
        backref=db.backref('activities', lazy='dynamic')
    )
    company = db.relationship(
        'Company',
        lazy=True,
        backref=db.backref('activities', lazy='dynamic')
    )
    opportunity = db.relationship(
        'Opportunity',
        lazy=True,
        backref=db.backref('activities', lazy='dynamic')
    )
    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('crm_activities', lazy='dynamic')
    )
    assignee = db.relationship(
        'User',
        lazy=True,
        foreign_keys=assignee_id
    )
    created_by = db.relationship(
        'User',
        lazy=True,
        foreign_keys=created_by_id
    )

    @property
    def is_from_agent(self):
        return self.created_by_agent_run_id is not None

    def __repr__(self):
        return format_repr(self, 'id', 'kind', 'status', _text=self.subject)
