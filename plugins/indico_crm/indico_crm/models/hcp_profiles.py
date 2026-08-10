# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.db import db
from indico.core.db.sqlalchemy import PyIntEnum, UTCDateTime
from indico.util.enum import RichIntEnum
from indico.util.i18n import _
from indico.util.string import format_repr


class EmploymentType(RichIntEnum):
    __titles__ = [None, _('Dipendente'), _('Libero professionista'), _('Convenzionato'), _('Privo di occupazione'),
                  _('Non specificato')]
    employee = 1
    freelance = 2
    contracted = 3
    unemployed = 4
    unspecified = 5


class VerificationStatus(RichIntEnum):
    __titles__ = [None, _('Da verificare'), _('Verificato'), _('Contestato'), _('Rifiutato')]
    pending = 1
    verified = 2
    disputed = 3
    rejected = 4


class HCPProfile(db.Model):
    """The regulatory identity of a healthcare professional.

    This is the record a certificate is issued against, so it is deliberately
    stricter than the rest of the CRM: it is never created or merged
    automatically, and `tax_code` is the identity key.
    """

    __tablename__ = 'hcp_profiles'
    __table_args__ = (db.Index('ix_uq_hcp_profiles_tax_code', db.text('lower(tax_code)'), unique=True,
                               postgresql_where=db.text("tax_code != ''")),
                      db.Index('ix_uq_hcp_profiles_registry', 'registry_board', 'registry_region', 'registry_number',
                               unique=True, postgresql_where=db.text("registry_number != ''")),
                      {'schema': 'plugin_crm'})

    contact_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.contacts.id'),
        primary_key=True
    )
    #: Codice fiscale
    tax_code = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Professione (e.g. Medico chirurgo, Infermiere, Farmacista)
    profession = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Disciplina (e.g. Cardiologia, Medicina generale)
    discipline = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Ordine/collegio professionale
    registry_board = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    registry_number = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    registry_region = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    employment_type = db.Column(
        PyIntEnum(EmploymentType),
        nullable=False,
        default=EmploymentType.unspecified
    )
    #: The healthcare organization the professional works for
    healthcare_org_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.companies.id'),
        index=True,
        nullable=True
    )
    verification_status = db.Column(
        PyIntEnum(VerificationStatus),
        nullable=False,
        default=VerificationStatus.pending
    )
    verified_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    verified_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    #: Exemptions, exclusions and other eligibility flags, keyed by rule name
    eligibility_flags = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )

    contact = db.relationship(
        'Contact',
        lazy=True,
        backref=db.backref('hcp_profile', uselist=False, lazy=True, cascade='all, delete-orphan')
    )
    healthcare_org = db.relationship(
        'Company',
        lazy=True,
        backref=db.backref('healthcare_professionals', lazy='dynamic')
    )
    verified_by = db.relationship(
        'User',
        lazy=True
    )

    @property
    def has_regulatory_identity(self):
        """Whether the profile can be used for credit assignment.

        Without a tax code or a registry number there is no way to attribute
        credits to a real person, so the profile must not be used.
        """
        return bool(self.tax_code or self.registry_number)

    def __repr__(self):
        return format_repr(self, 'contact_id', 'profession', 'discipline', _text=self.tax_code)
