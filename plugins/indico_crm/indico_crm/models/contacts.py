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


class ContactSource(RichIntEnum):
    __titles__ = [None, _('Inserimento manuale'), _('Iscrizione'), _('Importazione'), _('Email'), _('Agente')]
    manual = 1
    registration = 2
    import_ = 3
    email = 4
    agent = 5


class Contact(db.Model):
    """A person the provider has a relationship with.

    A contact exists independently of any event: the same person may attend
    several events over the years, speak at one and be a sponsor's referent at
    another. The link to Indico objects lives in `ObjectLink`.
    """

    __tablename__ = 'contacts'
    __table_args__ = (db.Index('ix_uq_contacts_email', db.text('lower(email)'), unique=True,
                               postgresql_where=db.text("email != '' AND NOT is_deleted")),
                      {'schema': 'plugin_crm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    first_name = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    last_name = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    email = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    phone = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    job_title = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: The Indico account, when the contact has one
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    #: The company the contact currently belongs to (history lives in OrganizationLink)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.companies.id'),
        index=True,
        nullable=True
    )
    source = db.Column(
        PyIntEnum(ContactSource),
        nullable=False,
        default=ContactSource.manual
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

    user = db.relationship(
        'User',
        lazy=True,
        backref=db.backref('crm_contact', uselist=False, lazy=True)
    )
    company = db.relationship(
        'Company',
        lazy=True,
        backref=db.backref('contacts', lazy='dynamic')
    )

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_healthcare_professional(self):
        return self.hcp_profile is not None

    def __repr__(self):
        return format_repr(self, 'id', is_deleted=False, _text=self.full_name)


class OrganizationLink(db.Model):
    """The relationship between a contact and a company over time.

    Job changes matter for an ECM provider: an invitation targeted at a
    hospital department must not follow a professional who left it.
    """

    __tablename__ = 'organization_links'
    __table_args__ = (db.CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date',
                                         'valid_period'),
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
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.companies.id'),
        index=True,
        nullable=False
    )
    role = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    start_date = db.Column(
        db.Date,
        nullable=True
    )
    end_date = db.Column(
        db.Date,
        nullable=True
    )
    is_primary = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    contact = db.relationship(
        'Contact',
        lazy=True,
        backref=db.backref('company_links', lazy='dynamic', cascade='all, delete-orphan')
    )
    company = db.relationship(
        'Company',
        lazy=True,
        backref=db.backref('contact_links', lazy='dynamic', cascade='all, delete-orphan')
    )

    def __repr__(self):
        return format_repr(self, 'id', 'contact_id', 'company_id', _text=self.role)
