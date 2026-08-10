# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The work queue.

Ported from `lib/tasks.ts` of trycompai/crm. The mechanism is the same one, in
SQLAlchemy: due rows are claimed with `FOR UPDATE SKIP LOCKED`, so several
workers can drain the queue concurrently without coordination, and a worker that
dies only holds its rows until the lease expires.

Nothing in this module talks to a language model. It is the plumbing that makes
agent work restartable, and it is deliberately usable on its own.
"""

import socket
import os
import random
from datetime import timedelta

from indico.core.db import db
from indico.core.logger import Logger
from indico.util.date_time import now_utc

from indico_agents.models.tasks import AgentTask, TaskOrigin, TaskStatus
from indico_agents.runtime.backoff import DEFAULT_LEASE_SECONDS, lease_expiry, next_run_after, should_give_up


logger = Logger.get('plugin.agents.queue')


def worker_id():
    """Identify the current worker, for lease ownership and debugging."""
    return f'{socket.gethostname()}:{os.getpid()}'


def schedule_task(kind, subject_type, subject_id, *, event_id=None, delay=0, payload=None, priority=0,
                  origin=TaskOrigin.signal, max_attempts=5, replace_pending=True):
    """Queue work, or leave the existing task alone.

    Signals fire more often than work needs doing — a registration can be
    updated five times in a minute — so an identical task that has not run yet
    is reused instead of piling up. When the new request is more urgent, the
    existing task is simply pulled forward.
    """
    run_after = now_utc() + timedelta(seconds=delay)
    existing = (AgentTask.query
                .filter(AgentTask.kind == kind, AgentTask.subject_type == subject_type,
                        AgentTask.subject_id == subject_id,
                        AgentTask.status.in_([TaskStatus.pending, TaskStatus.leased, TaskStatus.running]))
                .first())
    if existing is not None:
        if replace_pending and existing.status == TaskStatus.pending and run_after < existing.run_after:
            existing.run_after = run_after
            existing.priority = max(existing.priority, priority)
            existing.updated_dt = now_utc()
        return existing

    task = AgentTask(kind=kind, subject_type=subject_type, subject_id=subject_id, event_id=event_id,
                     payload=payload or {}, priority=priority, run_after=run_after, origin=origin,
                     max_attempts=max_attempts)
    db.session.add(task)
    db.session.flush()
    logger.debug('queued task %s for %s %s', kind, subject_type, subject_id)
    return task


def claim_due(limit=10, *, owner=None, lease_seconds=DEFAULT_LEASE_SECONDS, kinds=None):
    """Claim up to `limit` due tasks for this worker.

    `with_for_update(skip_locked=True)` is what allows several workers to run
    this at the same time: each one walks past the rows another worker is
    already holding instead of waiting behind them.

    The caller is responsible for committing; the rows stay leased until then.
    """
    owner = owner or worker_id()
    now = now_utc()
    query = AgentTask.query.filter(AgentTask.status == TaskStatus.pending, AgentTask.run_after <= now)
    if kinds:
        # the filter has to come before limit(): SQLAlchemy refuses to narrow a
        # query that already has a LIMIT
        query = query.filter(AgentTask.kind.in_(kinds))
    tasks = (query
             .order_by(AgentTask.priority.desc(), AgentTask.run_after)
             .limit(limit)
             .with_for_update(skip_locked=True, of=AgentTask)
             .all())
    for task in tasks:
        task.status = TaskStatus.leased
        task.lease_owner = owner
        task.lease_expires_dt = lease_expiry(now, seconds=lease_seconds)
        task.attempts += 1
        task.updated_dt = now
    db.session.flush()
    return tasks


def reclaim_expired(limit=100):
    """Return tasks whose lease expired to the pending pool.

    This is what makes a crashed worker a non-event: nothing is lost, the work
    simply becomes claimable again.
    """
    now = now_utc()
    tasks = (AgentTask.query
             .filter(AgentTask.status.in_([TaskStatus.leased, TaskStatus.running]),
                     AgentTask.lease_expires_dt < now)
             .limit(limit)
             .with_for_update(skip_locked=True, of=AgentTask)
             .all())
    for task in tasks:
        give_up = should_give_up(task.attempts, task.max_attempts)
        next_attempt = None if give_up else next_run_after(now, task.attempts, rand=random.random)
        task.status = TaskStatus.failed if give_up else TaskStatus.pending
        task.lease_owner = None
        task.lease_expires_dt = None
        if give_up:
            task.last_error = 'lease expired and no attempts left'
        else:
            task.run_after = next_attempt
        task.updated_dt = now
    if tasks:
        logger.warning('reclaimed %d expired task leases', len(tasks))
    db.session.flush()
    return tasks


def mark_running(task):
    task.status = TaskStatus.running
    task.updated_dt = now_utc()
    db.session.flush()
    return task


def complete(task):
    task.status = TaskStatus.done
    task.lease_owner = None
    task.lease_expires_dt = None
    task.last_error = ''
    task.updated_dt = now_utc()
    db.session.flush()
    return task


def fail(task, error, *, retry=True):
    """Record a failure and decide whether the task comes back.

    A task that has exhausted its attempts stays in the table as `failed`: it is
    evidence that work was requested and never done, which someone has to see.
    """
    now = now_utc()
    # read everything before writing anything: touching an expired attribute
    # mid-update triggers an autoflush of a half-written row
    will_retry = retry and not should_give_up(task.attempts, task.max_attempts)
    next_attempt = next_run_after(now, task.attempts, rand=random.random) if will_retry else None
    task.status = TaskStatus.pending if will_retry else TaskStatus.failed
    task.lease_owner = None
    task.lease_expires_dt = None
    task.last_error = str(error)[:2000]
    task.updated_dt = now
    if next_attempt is not None:
        task.run_after = next_attempt
    db.session.flush()
    return task


def cancel(task, reason=''):
    task.status = TaskStatus.cancelled
    task.last_error = reason
    task.lease_owner = None
    task.lease_expires_dt = None
    task.updated_dt = now_utc()
    db.session.flush()
    return task


def extend_lease(task, *, seconds=DEFAULT_LEASE_SECONDS):
    """Heartbeat for a long-running task."""
    task.lease_expires_dt = lease_expiry(now_utc(), seconds=seconds)
    db.session.flush()
    return task


def queue_stats():
    """Counts by status, for the dashboard and for monitoring."""
    rows = (db.session.query(AgentTask.status, db.func.count(AgentTask.id))
            .group_by(AgentTask.status)
            .all())
    return {status.name: count for status, count in rows}
