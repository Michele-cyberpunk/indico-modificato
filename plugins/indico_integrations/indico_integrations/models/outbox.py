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


class OutboxState(RichIntEnum):
    __titles__ = [None, _('In attesa'), _('Inviato'), _('Fallito'), _('Abbandonato')]
    pending = 1
    sent = 2
    failed = 3
    abandoned = 4


class OutboxEntry(db.Model):
    """A message to be delivered to an external system.

    The transactional outbox pattern, and the reason it is here rather than a
    direct HTTP call inside a request: the row is written in the same
    transaction as the change it describes. Either both happen or neither does,
    so an external system never hears about something the database rolled back.

    Same idea as Indico's own `livesync` plugin, applied to CRM and ECM events.
    """

    __tablename__ = 'outbox'
    __table_args__ = (db.Index('ix_outbox_deliverable', 'state', 'next_attempt_dt'),
                      db.Index('ix_outbox_subject', 'subject_type', 'subject_id'),
                      {'schema': 'plugin_integrations'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    #: gmail, calendar, accounting, signature, webinar…
    target = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    #: contact.updated, certificate.issued, registration.created…
    topic = db.Column(
        db.String,
        nullable=False
    )
    subject_type = db.Column(
        db.String,
        nullable=False
    )
    subject_id = db.Column(
        db.Integer,
        nullable=False
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=True
    )
    payload = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    state = db.Column(
        PyIntEnum(OutboxState),
        nullable=False,
        default=OutboxState.pending
    )
    attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    max_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=8
    )
    next_attempt_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    last_error = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: Set by the target system, to make redelivery idempotent on its side
    external_ref = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    delivered_dt = db.Column(
        UTCDateTime,
        nullable=True
    )

    def __repr__(self):
        return format_repr(self, 'id', 'target', 'topic', 'state', 'attempts')
