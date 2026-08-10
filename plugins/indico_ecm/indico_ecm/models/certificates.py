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


class CertificateState(RichIntEnum):
    __titles__ = [None, _('Bozza'), _('Emesso'), _('Revocato'), _('Sostituito')]
    draft = 1
    issued = 2
    revoked = 3
    superseded = 4


class Certificate(db.Model):
    """An ECM certificate issued to a participant.

    The PDF itself is produced by Indico's `receipts` module (which already
    ships a Certificate of Attendance template); this table owns what the
    receipts module cannot: a unique number, a verifiable hash, the link to the
    credit assignment that justifies it, and the revocation trail.
    """

    __tablename__ = 'certificates'
    __table_args__ = (db.Index('ix_uq_certificates_number', 'number', unique=True),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    assignment_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_ecm.credit_assignments.id'),
        index=True,
        nullable=False
    )
    #: Provider-wide unique number, e.g. 'ECM-2026-000431'
    number = db.Column(
        db.String,
        nullable=False
    )
    state = db.Column(
        PyIntEnum(CertificateState),
        nullable=False,
        default=CertificateState.draft
    )
    #: The generated file in the receipts module, keyed by its file id
    #: (`ReceiptFile` has no surrogate key: its primary key is `file_id`)
    receipt_file_id = db.Column(
        db.Integer,
        db.ForeignKey('event_registration.receipt_files.file_id'),
        index=True,
        nullable=True
    )
    #: SHA-256 of the issued PDF, used by the verification page
    content_hash = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Opaque token in the QR code; never the participant's identifiers
    verification_token = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    issued_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    issued_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    revoked_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    revoked_reason = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    supersedes_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_ecm.certificates.id'),
        index=True,
        nullable=True
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    assignment = db.relationship(
        'CreditAssignment',
        lazy=True,
        backref=db.backref('certificates', lazy='dynamic')
    )
    supersedes = db.relationship(
        'Certificate',
        lazy=True,
        remote_side=id,
        backref=db.backref('superseded_by', lazy=True, uselist=False)
    )
    issued_by = db.relationship(
        'User',
        lazy=True
    )

    @property
    def is_valid(self):
        return self.state == CertificateState.issued

    def __repr__(self):
        return format_repr(self, 'id', 'state', _text=self.number)


class CertificateSequence(db.Model):
    """The certificate counter of a provider, one row per year.

    Numbering has to be gapless and unique, and two batches may run at the same
    time. Deriving the next number from `max(number)` cannot be locked in
    PostgreSQL (`FOR UPDATE` is not allowed with an aggregate), so the counter
    is a row and is incremented atomically with an upsert.
    """

    __tablename__ = 'certificate_sequences'
    __table_args__ = (db.Index('ix_uq_certificate_sequences', 'provider_id', 'year', unique=True),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    provider_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_ecm.providers.id'),
        nullable=False
    )
    year = db.Column(
        db.Integer,
        nullable=False
    )
    last_number = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    def __repr__(self):
        return format_repr(self, 'id', 'provider_id', 'year', 'last_number')
