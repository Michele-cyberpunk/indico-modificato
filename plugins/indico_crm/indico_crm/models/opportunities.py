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


class OpportunityStage(RichIntEnum):
    __titles__ = [None, _('Nuova'), _('Qualificata'), _('Proposta inviata'), _('In negoziazione'), _('Vinta'),
                  _('Persa')]
    new = 1
    qualified = 2
    proposal_sent = 3
    negotiation = 4
    won = 5
    lost = 6

    @property
    def is_closed(self):
        return self in (OpportunityStage.won, OpportunityStage.lost)


class Opportunity(db.Model):
    """A commercial opportunity, almost always tied to an event.

    Sponsorships, exhibition booths and commissioned training all live here.
    The event link is a plain FK to the Indico event so that reporting can join
    the pipeline with the actual editions.
    """

    __tablename__ = 'opportunities'
    __table_args__ = (db.CheckConstraint('value >= 0', 'positive_value'),
                      db.CheckConstraint('probability BETWEEN 0 AND 100', 'valid_probability'),
                      {'schema': 'plugin_crm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    title = db.Column(
        db.String,
        nullable=False
    )
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.companies.id'),
        index=True,
        nullable=False
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=True
    )
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    value = db.Column(
        db.Numeric(precision=12, scale=2),
        nullable=False,
        default=0
    )
    currency = db.Column(
        db.String,
        nullable=False,
        default='EUR'
    )
    stage = db.Column(
        PyIntEnum(OpportunityStage),
        nullable=False,
        default=OpportunityStage.new
    )
    probability = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    expected_close_date = db.Column(
        db.Date,
        nullable=True
    )
    next_action = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    next_action_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    closed_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    close_reason = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    company = db.relationship(
        'Company',
        lazy=True,
        backref=db.backref('opportunities', lazy='dynamic')
    )
    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('crm_opportunities', lazy='dynamic')
    )
    owner = db.relationship(
        'User',
        lazy=True,
        backref=db.backref('crm_opportunities', lazy='dynamic')
    )

    @property
    def weighted_value(self):
        return self.value * self.probability / 100

    def __repr__(self):
        return format_repr(self, 'id', 'company_id', 'stage', _text=self.title)
