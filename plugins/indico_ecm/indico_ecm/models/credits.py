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


class AssignmentState(RichIntEnum):
    __titles__ = [None, _('Proposta'), _('Approvata'), _('Revocata'), _('Rifiutata')]
    proposed = 1
    approved = 2
    revoked = 3
    denied = 4


class CreditRuleVersion(db.Model):
    """A stored, immutable version of the credit rules.

    The payload is the serialized form of `services.credit_rules.RuleSet`. Rows
    are never updated once referenced by an assignment: changing the rules means
    creating a new version, so an old decision can always be replayed with the
    rules that produced it.
    """

    __tablename__ = 'credit_rule_versions'
    __table_args__ = (db.Index('ix_uq_credit_rule_versions', 'version', unique=True),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    #: Human-readable version, e.g. '2026.1' or '2026.1-lombardia'
    version = db.Column(
        db.String,
        nullable=False
    )
    region = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    valid_from = db.Column(
        db.Date,
        nullable=False
    )
    valid_to = db.Column(
        db.Date,
        nullable=True
    )
    #: Serialized RuleSet
    payload = db.Column(
        db.JSON,
        nullable=False
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )

    def __repr__(self):
        return format_repr(self, 'id', 'region', is_active=True, _text=self.version)


class CreditAssignment(db.Model):
    """The credits attributed to one participant for one activity.

    Rows start as `proposed` — that is all an automated actor may produce — and
    only a person holding the ECM permission can move them to `approved`. The
    full evaluation outcome is stored alongside, so the decision can be
    explained without recomputing it.
    """

    __tablename__ = 'credit_assignments'
    __table_args__ = (db.Index('ix_uq_credit_assignments', 'registration_id', unique=True,
                               postgresql_where=db.text('state != 3')),
                      db.CheckConstraint('credits >= 0', 'positive_credits'),
                      db.CheckConstraint('(state = 2) = (approved_dt IS NOT NULL)', 'dt_set_when_approved'),
                      {'schema': 'plugin_ecm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey('event_registration.registrations.id'),
        nullable=False
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=False
    )
    accreditation_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_ecm.event_accreditations.id'),
        index=True,
        nullable=False
    )
    #: The HCP profile the credits belong to
    hcp_contact_id = db.Column(
        db.Integer,
        index=True,
        nullable=True
    )
    state = db.Column(
        PyIntEnum(AssignmentState),
        nullable=False,
        default=AssignmentState.proposed
    )
    credits = db.Column(
        db.Numeric(precision=6, scale=2),
        nullable=False,
        default=0
    )
    rule_version = db.Column(
        db.String,
        nullable=False
    )
    #: Serialized `Outcome`: ratios, minutes and reason codes
    outcome = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    proposed_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    #: Set when an agent produced the proposal
    proposed_by_agent_run_id = db.Column(
        db.Integer,
        index=True,
        nullable=True
    )
    approved_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    approved_by_id = db.Column(
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

    registration = db.relationship(
        'Registration',
        lazy=True,
        backref=db.backref('ecm_credit_assignment', uselist=False, lazy=True)
    )
    accreditation = db.relationship(
        'EventAccreditation',
        lazy=True,
        backref=db.backref('credit_assignments', lazy='dynamic')
    )
    approved_by = db.relationship(
        'User',
        lazy=True
    )

    @property
    def reasons(self):
        return self.outcome.get('reasons', [])

    @property
    def is_final(self):
        return self.state in (AssignmentState.approved, AssignmentState.revoked)

    def __repr__(self):
        return format_repr(self, 'id', 'registration_id', 'state', 'credits')
