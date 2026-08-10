# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.db import db
from indico.core.db.sqlalchemy import UTCDateTime
from indico.util.date_time import now_utc
from indico.util.string import format_repr

from indico_ecm.services.deliverables import Deliverable, DeliverableState


class EventDeliverable(db.Model):
    """One item of an event's preparation checklist.

    Replaces the yes/no columns of the legacy event manager (accreditamento,
    contratti sponsor, grafica, lettera di incarico, slide kit) with a row that
    also knows who owns it and when it was done — which is what turns a
    dashboard into something an agent can raise a task from.

    The enum values are stored as strings on purpose: they are shared with the
    pure `services.deliverables` module, which has no database dependency.
    """

    __tablename__ = 'event_deliverables'
    __table_args__ = (db.Index('ix_uq_event_deliverables', 'event_id', 'deliverable', unique=True),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=False
    )
    #: A value of `services.deliverables.Deliverable`
    deliverable = db.Column(
        db.String,
        nullable=False
    )
    #: A value of `services.deliverables.DeliverableState`
    state = db.Column(
        db.String,
        nullable=False,
        default=DeliverableState.todo.value
    )
    #: Overrides the default lead time for this event, in days before it
    lead_days = db.Column(
        db.Integer,
        nullable=True
    )
    owner_id = db.Column(
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
    done_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    updated_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('ecm_deliverables', lazy='dynamic', cascade='all, delete-orphan')
    )
    owner = db.relationship(
        'User',
        lazy=True
    )

    @property
    def kind(self):
        return Deliverable(self.deliverable)

    @property
    def status(self):
        return DeliverableState(self.state)

    def mark_done(self):
        self.state = DeliverableState.done.value
        self.done_dt = now_utc()
        self.updated_dt = now_utc()

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', 'deliverable', 'state')


def states_for_event(event):
    """The checklist of an event as the pure service expects it."""
    return {row.kind: row.status for row in event.ecm_deliverables}
