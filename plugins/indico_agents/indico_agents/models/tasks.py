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


class TaskStatus(RichIntEnum):
    __titles__ = [None, _('In attesa'), _('Affittato'), _('In esecuzione'), _('Completato'), _('Fallito'),
                  _('Annullato')]
    pending = 1
    leased = 2
    running = 3
    done = 4
    failed = 5
    cancelled = 6


class TaskOrigin(RichIntEnum):
    __titles__ = [None, _('Segnale'), _('Pianificazione'), _('Agente'), _('Utente')]
    signal = 1
    schedule = 2
    agent = 3
    user = 4


class AgentTask(db.Model):
    """A unit of work for the agent layer.

    The design follows the work queue of trycompai/crm: the queue is a table, not a
    broker, because the questions that matter here are "what work exists, why,
    and what happened to it" — and a table answers them years later.

    `run_after` makes time a data point rather than a cron expression: an agent
    rescheduling itself is just a row with a later timestamp.
    """

    __tablename__ = 'agent_tasks'
    __table_args__ = (db.CheckConstraint('attempts >= 0 AND max_attempts > 0', 'valid_attempts'),
                      #: a lease is an owner plus an expiry, never one without the other
                      db.CheckConstraint('(lease_owner IS NULL) = (lease_expires_dt IS NULL)', 'lease_pair'),
                      #: only a leased or running task may hold one. Deliberately not an
                      #: equality: an attribute load can autoflush a half-updated row, and a
                      #: constraint must describe the invariant, not the order of assignments
                      db.CheckConstraint('status IN (2, 3) OR lease_expires_dt IS NULL', 'no_stale_lease'),
                      db.Index('ix_agent_tasks_claimable', 'status', 'run_after', 'priority'),
                      db.Index('ix_agent_tasks_subject', 'subject_type', 'subject_id'),
                      db.Index('ix_uq_agent_tasks_pending', 'kind', 'subject_type', 'subject_id', unique=True,
                               postgresql_where=db.text('status IN (1, 2, 3)')),
                      {'schema': 'plugin_agents'})

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    #: registration_check, attendance_reconcile, sponsor_research…
    kind = db.Column(
        db.String,
        nullable=False,
        index=True
    )
    #: event, registration, contact, company, certificate_batch…
    subject_type = db.Column(
        db.String,
        nullable=False
    )
    subject_id = db.Column(
        db.Integer,
        nullable=False
    )
    #: Work is almost always anchored to an event; used for scoping and quotas
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=True
    )
    payload = db.Column(
        db.JSON,
        nullable=False,
        default=dict
    )
    status = db.Column(
        PyIntEnum(TaskStatus),
        nullable=False,
        default=TaskStatus.pending
    )
    #: Which lane drains this task. `visible` is work somebody is waiting on and
    #: is claimed in large batches on a short lease; `research` reaches outside,
    #: takes minutes rather than seconds, and must not make the rest queue behind it.
    lane = db.Column(
        db.String,
        nullable=False,
        default='visible',
        index=True
    )
    priority = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    #: The task becomes claimable at this point in time
    run_after = db.Column(
        UTCDateTime,
        nullable=False,
        default=now_utc
    )
    #: Worker holding the task
    lease_owner = db.Column(
        db.String,
        nullable=True
    )
    lease_expires_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )
    max_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=5
    )
    last_error = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    origin = db.Column(
        PyIntEnum(TaskOrigin),
        nullable=False,
        default=TaskOrigin.signal
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

    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref('agent_tasks', lazy='dynamic')
    )

    @property
    def is_claimable(self):
        return self.status == TaskStatus.pending and self.run_after <= now_utc()

    @property
    def can_retry(self):
        return self.attempts < self.max_attempts

    def __repr__(self):
        return format_repr(self, 'id', 'kind', 'status', 'subject_type', 'subject_id')
