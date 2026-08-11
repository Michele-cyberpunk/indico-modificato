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

from indico_crm.models.links import CRMObjectType


class EvidenceKind(RichIntEnum):
    """How a statement came to be known.

    The distinction is what makes agent output reviewable: an observed fact can
    be re-checked against the system, a declared one against the person, a
    derived one against the reasoning, and an external one against the source.
    """

    __titles__ = [None, _('Osservato'), _('Dichiarato'), _('Dedotto'), _('Fonte esterna')]
    observed = 1
    declared = 2
    derived = 3
    external = 4


class Evidence(db.Model):
    """A statement about a CRM record, with its provenance.

    The design follows the evidence ledger of trycompai/crm: nothing an agent asserts
    is stored as a bare fact. Every statement carries where it came from, how
    confident it is and which run produced it, and is superseded rather than
    overwritten.
    """

    __tablename__ = 'evidence'
    __table_args__ = (db.CheckConstraint('confidence BETWEEN 0 AND 100', 'valid_confidence'),
                      db.CheckConstraint('recorded_by_id IS NOT NULL OR agent_run_id IS NOT NULL',
                                         'has_author'),
                      db.Index('ix_evidence_subject', 'subject_type', 'subject_id'),
                      {'schema': 'plugin_crm'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    subject_type = db.Column(
        PyIntEnum(CRMObjectType),
        nullable=False
    )
    subject_id = db.Column(
        db.Integer,
        nullable=False
    )
    #: What is being asserted, in plain language
    statement = db.Column(
        db.Text,
        nullable=False
    )
    #: The field the statement is about, when it maps to one
    attribute = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    kind = db.Column(
        PyIntEnum(EvidenceKind),
        nullable=False
    )
    #: URL, message id, tool name or other pointer to the source
    source_ref = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    confidence = db.Column(
        db.Integer,
        nullable=False,
        default=50
    )
    recorded_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    #: The agent run that produced the statement, if any
    agent_run_id = db.Column(
        db.Integer,
        index=True,
        nullable=True
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    #: Set when a newer statement replaces this one
    superseded_by_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_crm.evidence.id'),
        index=True,
        nullable=True
    )

    recorded_by = db.relationship(
        'User',
        lazy=True
    )
    superseded_by = db.relationship(
        'Evidence',
        lazy=True,
        remote_side=id,
        backref=db.backref('supersedes', lazy='dynamic')
    )

    @property
    def is_current(self):
        return self.superseded_by_id is None

    @property
    def is_from_agent(self):
        return self.agent_run_id is not None

    def __repr__(self):
        return format_repr(self, 'id', 'subject_type', 'subject_id', 'kind', _text=self.attribute)
