# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.db import db
from indico.core.db.sqlalchemy import UTCDateTime
from indico.util.date_time import now_utc
from indico.util.string import format_repr

from indico_ecm.services.guests import Guest


class EventGuest(db.Model):
    """A person on the sponsor's list, and what has to be arranged for them.

    Separate from `Registration`: these people are not (yet) registered for the
    event, they are names on a list a sponsor sent, and the office has to book
    their transfer and count their cover before anyone signs up for anything.
    When a guest does register, the CRM's identity rules can link the two.

    The row keeps `source_row` and `evidence` so a wrong value can be traced
    back to the line and the rule that read it.
    """

    __tablename__ = 'event_guests'
    __table_args__ = (db.Index('ix_event_guests_event', 'event_id'),
                      db.CheckConstraint('pax > 0', 'pax_positive'),
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
    first_name = db.Column(db.String, nullable=False, default='')
    last_name = db.Column(db.String, nullable=False, default='')
    email = db.Column(db.String, nullable=False, default='')
    phone = db.Column(db.String, nullable=False, default='')
    #: how many people travel under this name, companions included
    pax = db.Column(db.Integer, nullable=False, default=1)
    arrival = db.Column(db.Time, nullable=True)
    departure = db.Column(db.Time, nullable=True)
    transfer_place = db.Column(db.String, nullable=False, default='')
    own_transport = db.Column(db.Boolean, nullable=False, default=False)
    lunch = db.Column(db.Boolean, nullable=False, default=False)
    dinner = db.Column(db.Boolean, nullable=False, default=False)
    diet_notes = db.Column(db.String, nullable=False, default='')
    notes = db.Column(db.String, nullable=False, default='')
    #: False while nothing has said which token is the surname
    name_order_certain = db.Column(db.Boolean, nullable=False, default=True)
    #: the line this was read from, kept verbatim
    source_row = db.Column(db.String, nullable=False, default='')
    #: field -> the fragment the rule matched
    evidence = db.Column(db.JSON, nullable=False, default=dict)
    created_dt = db.Column(UTCDateTime, nullable=False, default=now_utc)

    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('ecm_guests', lazy='dynamic', cascade='all, delete-orphan')
    )

    @classmethod
    def from_extraction(cls, event_id, guest: Guest, source_row=''):
        """Persist what the rules read, evidence included."""
        return cls(event_id=event_id, first_name=guest.first_name, last_name=guest.last_name,
                   email=guest.email, phone=guest.phone, pax=guest.pax,
                   arrival=guest.arrival, departure=guest.departure,
                   transfer_place=guest.transfer_place, own_transport=guest.own_transport,
                   lunch=guest.lunch, dinner=guest.dinner, diet_notes=guest.diet_notes,
                   notes=guest.notes, name_order_certain=guest.name_order_certain,
                   source_row=source_row, evidence=dict(guest.evidence))

    def to_guest(self):
        """The pure value the services work on."""
        return Guest(first_name=self.first_name, last_name=self.last_name, email=self.email,
                     phone=self.phone, pax=self.pax, arrival=self.arrival, departure=self.departure,
                     transfer_place=self.transfer_place, own_transport=self.own_transport,
                     lunch=self.lunch, dinner=self.dinner, diet_notes=self.diet_notes,
                     notes=self.notes, name_order_certain=self.name_order_certain,
                     evidence=dict(self.evidence or {}))

    @property
    def full_name(self):
        return ' '.join(part for part in (self.first_name, self.last_name) if part)

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', 'last_name', 'pax')
