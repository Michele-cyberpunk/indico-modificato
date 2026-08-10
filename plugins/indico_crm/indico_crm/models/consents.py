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


class ConsentKind(RichIntEnum):
    __titles__ = [None, _('Trattamento dati'), _('Marketing'), _('Profilazione'), _('Comunicazione a terzi')]
    privacy = 1
    marketing = 2
    profiling = 3
    third_party = 4


class Consent(db.Model):
    """A consent given (or withdrawn) by a contact.

    Consents are append-only: withdrawing does not delete the previous row, it
    adds a new one. The history is the proof.
    """

    __tablename__ = 'consents'
    __table_args__ = (db.Index('ix_consents_contact_kind', 'contact_id', 'kind'),
                      {'schema': 'plugin_crm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    contact_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.contacts.id'),
        index=True,
        nullable=False
    )
    kind = db.Column(
        PyIntEnum(ConsentKind),
        nullable=False
    )
    granted = db.Column(
        db.Boolean,
        nullable=False
    )
    #: When the consent was given or withdrawn
    effective_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    #: Where it came from: registration form, web form, paper, phone…
    source = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: The version of the privacy policy in force at the time
    policy_version = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Evidence of the consent (form id, IP, checkbox label, scan reference…)
    proof = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )

    contact = db.relationship(
        'Contact',
        lazy=True,
        backref=db.backref('consents', lazy='dynamic', order_by='Consent.effective_dt.desc()')
    )

    def __repr__(self):
        return format_repr(self, 'id', 'contact_id', 'kind', 'granted')
