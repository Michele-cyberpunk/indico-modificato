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


class ApprovalState(RichIntEnum):
    __titles__ = [None, _('In attesa'), _('Approvata'), _('Rifiutata'), _('Scaduta'), _('Applicata')]
    pending = 1
    approved = 2
    rejected = 3
    expired = 4
    applied = 5


class Approval(db.Model):
    """A proposed action waiting for a person to decide.

    Ported from `lib/approval.ts`. The proposal stores exactly what would
    happen, not a description of it: the reviewer approves a diff, and applying
    it does not re-run the agent's reasoning.
    """

    __tablename__ = 'approvals'
    __table_args__ = (db.Index('ix_approvals_state', 'state', 'created_dt'),
                      {'schema': 'plugin_agents'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    run_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_agents.agent_runs.id'),
        index=True,
        nullable=True
    )
    #: send_email, merge_contacts, issue_certificates, update_field…
    action = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    subject_type = db.Column(
        db.String,
        nullable=False
    )
    subject_id = db.Column(
        db.Integer,
        nullable=False
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=True
    )
    #: Human-readable explanation of why the agent proposes this
    rationale = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: The exact change that will be applied on approval
    proposed_change = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    state = db.Column(
        PyIntEnum(ApprovalState),
        nullable=False,
        default=ApprovalState.pending
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    expires_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    decided_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    decided_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True
    )
    decision_note = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    applied_dt = db.Column(
        UTCDateTime,
        nullable=True
    )

    run = db.relationship(
        'AgentRun',
        lazy=True,
        backref=db.backref('approvals', lazy='dynamic')
    )
    decided_by = db.relationship(
        'User',
        lazy=True
    )

    @property
    def is_pending(self):
        return self.state == ApprovalState.pending

    def __repr__(self):
        return format_repr(self, 'id', 'action', 'state', 'subject_type', 'subject_id')


class PolicyDecision(db.Model):
    """Why a tool call was allowed or denied.

    Authorization lives outside the prompt, and its outcome is recorded: an
    agent that was stopped is as interesting as one that acted.
    """

    __tablename__ = 'policy_decisions'
    __table_args__ = (db.Index('ix_policy_decisions_run', 'run_id'),
                      {'schema': 'plugin_agents'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    run_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_agents.agent_runs.id'),
        nullable=True
    )
    agent_name = db.Column(
        db.String,
        nullable=False
    )
    tool_name = db.Column(
        db.String,
        nullable=False
    )
    allowed = db.Column(
        db.Boolean,
        nullable=False
    )
    reason = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    def __repr__(self):
        return format_repr(self, 'id', 'agent_name', 'tool_name', 'allowed')
