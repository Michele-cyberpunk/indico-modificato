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


class AccreditationState(RichIntEnum):
    __titles__ = [None, _('Bozza'), _('Inviata'), _('Accreditata'), _('Respinta'), _('Annullata'), _('Chiusa')]
    draft = 1
    submitted = 2
    accredited = 3
    rejected = 4
    cancelled = 5
    closed = 6


class ActivityFormat(RichIntEnum):
    __titles__ = [None, _('Residenziale'), _('FAD asincrona'), _('FAD sincrona'), _('Blended'),
                  _('Formazione sul campo')]
    residential = 1
    fad_async = 2
    fad_sync = 3
    blended = 4
    fieldwork = 5


class Provider(db.Model):
    """The ECM provider running the activities."""

    __tablename__ = 'providers'
    __table_args__ = {'schema': 'plugin_ecm'}

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    name = db.Column(
        db.String,
        nullable=False
    )
    #: Provider identifier assigned by the accrediting body
    provider_code = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    region = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    tax_code = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    contact_email = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Free-form settings: certificate footer, signature holder, numbering prefix…
    settings = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    def __repr__(self):
        return format_repr(self, 'id', 'provider_code', _text=self.name)


class EventAccreditation(db.Model):
    """The accreditation dossier of one event.

    Modelled on Indico's own request workflow: a dossier moves through states,
    carries documents and is never silently edited once accredited.
    """

    __tablename__ = 'event_accreditations'
    __table_args__ = (db.Index('ix_uq_event_accreditations_event', 'event_id', unique=True),
                      db.CheckConstraint('credits >= 0', 'positive_credits'),
                      db.CheckConstraint('max_participants IS NULL OR max_participants > 0', 'positive_quota'),
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
    provider_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_ecm.providers.id'),
        index=True,
        nullable=False
    )
    #: Identifier assigned by the accrediting body to this activity
    activity_code = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    activity_format = db.Column(
        PyIntEnum(ActivityFormat),
        nullable=False,
        default=ActivityFormat.residential
    )
    state = db.Column(
        PyIntEnum(AccreditationState),
        nullable=False,
        default=AccreditationState.draft
    )
    #: Credits granted by the accreditation
    credits = db.Column(
        db.Numeric(precision=6, scale=2),
        nullable=False,
        default=0
    )
    max_participants = db.Column(
        db.Integer,
        nullable=True
    )
    accredited_professions = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )
    accredited_disciplines = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )
    learning_objectives = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )
    #: The rule set version in force for this activity
    rule_version = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    submitted_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    accredited_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    closed_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    notes = db.Column(
        db.Text,
        nullable=False,
        default=''
    )

    provider = db.relationship(
        'Provider',
        lazy=True,
        backref=db.backref('accreditations', lazy='dynamic')
    )
    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('ecm_accreditation', uselist=False, lazy=True)
    )

    @property
    def is_open_for_credits(self):
        """Whether credits may be assigned against this dossier."""
        return self.state == AccreditationState.accredited

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', 'state', _text=self.activity_code)
