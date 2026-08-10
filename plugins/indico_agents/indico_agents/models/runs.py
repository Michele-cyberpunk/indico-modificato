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


class RunState(RichIntEnum):
    __titles__ = [None, _('In corso'), _('Completato'), _('Fallito'), _('Interrotto'), _('In attesa di approvazione')]
    running = 1
    done = 2
    failed = 3
    aborted = 4
    waiting_approval = 5


class AgentRun(db.Model):
    """One execution of one agent against one task.

    The state lives in the database rather than in the process, so a worker that
    dies mid-run does not lose the reasoning: the run is resumed from its last
    recorded step.
    """

    __tablename__ = 'agent_runs'
    __table_args__ = (db.Index('ix_agent_runs_task', 'task_id'),
                      {'schema': 'plugin_agents'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    task_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_agents.agent_tasks.id'),
        nullable=False
    )
    agent_name = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    state = db.Column(
        PyIntEnum(RunState),
        nullable=False,
        default=RunState.running
    )
    #: Hash of every skill file loaded, so a decision can be replayed with the
    #: rules that were actually in force
    skill_versions = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    model_name = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    #: Resumable state of the run
    state_data = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    summary = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    tokens_used = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    cost_cents = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    started_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    ended_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    error = db.Column(
        db.Text,
        nullable=False,
        default=''
    )

    task = db.relationship(
        'AgentTask',
        lazy=True,
        backref=db.backref('runs', lazy='dynamic')
    )

    @property
    def is_finished(self):
        return self.state in (RunState.done, RunState.failed, RunState.aborted)

    def __repr__(self):
        return format_repr(self, 'id', 'agent_name', 'state', 'task_id')


class ToolCall(db.Model):
    """Every tool invocation of a run, with its arguments and result.

    This is the audit surface that makes an agent acceptable in a regulated
    context: what it looked at, what it changed and in which order.
    """

    __tablename__ = 'tool_calls'
    __table_args__ = (db.Index('ix_tool_calls_run', 'run_id', 'sequence'),
                      {'schema': 'plugin_agents'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    run_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_agents.agent_runs.id'),
        nullable=False
    )
    sequence = db.Column(
        db.Integer,
        nullable=False
    )
    tool_name = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    #: Arguments after redaction: direct identifiers never reach this table
    arguments = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    result_summary = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: Whether the call changed data
    is_write = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    succeeded = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )
    error = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    duration_ms = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    created_dt = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )

    run = db.relationship(
        'AgentRun',
        lazy=True,
        backref=db.backref('tool_calls', lazy='dynamic', order_by='ToolCall.sequence')
    )

    def __repr__(self):
        return format_repr(self, 'id', 'run_id', 'sequence', 'tool_name', succeeded=True)
