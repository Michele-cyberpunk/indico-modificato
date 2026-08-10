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


class CompanyKind(RichIntEnum):
    __titles__ = [None, _('Sponsor'), _('Espositore'), _('Provider'), _('Partner'), _('Fornitore'),
                  _('Struttura sanitaria'), _('Altro')]
    sponsor = 1
    exhibitor = 2
    provider = 3
    partner = 4
    supplier = 5
    healthcare_org = 6
    other = 7


class Company(db.Model):
    """An organization the provider has a relationship with.

    Covers sponsors, exhibitors, partners, suppliers and the healthcare
    organizations professionals belong to. Purely relational data: nothing
    here ever feeds a certificate.
    """

    __tablename__ = 'companies'
    __table_args__ = (db.Index('ix_uq_companies_vat_id', 'vat_id', unique=True,
                               postgresql_where=db.text('vat_id IS NOT NULL AND NOT is_deleted')),
                      {'schema': 'plugin_crm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    name = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    kind = db.Column(
        PyIntEnum(CompanyKind),
        nullable=False,
        default=CompanyKind.other
    )
    #: Partita IVA
    vat_id = db.Column(
        db.String,
        nullable=True
    )
    #: Codice fiscale, when it differs from the VAT id
    tax_code = db.Column(
        db.String,
        nullable=True
    )
    #: Codice destinatario SDI for electronic invoicing
    sdi_code = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    pec = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    website = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    address = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    notes = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    updated_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )

    created_by = db.relationship(
        'User',
        lazy=True,
        backref=db.backref('crm_companies', lazy='dynamic')
    )

    def __repr__(self):
        return format_repr(self, 'id', 'kind', is_deleted=False, _text=self.name)
