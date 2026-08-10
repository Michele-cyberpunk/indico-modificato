# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Publishing and draining the outbox.

`publish` is called inside the transaction that made the change; `deliver_due`
runs from Celery and hands entries to the registered handler for their target.
Delivery failures are retried with the same backoff the agent queue uses, so
there is one retry policy in the platform rather than two.
"""

import random

from indico.core.db import db
from indico.core.logger import Logger
from indico.util.date_time import now_utc

from indico_integrations.models.outbox import OutboxEntry, OutboxState


logger = Logger.get('plugin.integrations.outbox')

#: target name -> callable(entry) -> external reference
_HANDLERS = {}


def handler(target):
    """Register the function delivering entries for a target."""
    def decorator(func):
        _HANDLERS[target] = func
        return func
    return decorator


def publish(target, topic, subject_type, subject_id, *, payload=None, event_id=None):
    """Queue a message. Must be called inside the transaction it belongs to."""
    entry = OutboxEntry(target=target, topic=topic, subject_type=subject_type, subject_id=subject_id,
                        event_id=event_id, payload=payload or {})
    db.session.add(entry)
    db.session.flush()
    return entry


def deliver_due(limit=50):
    """Deliver pending entries whose time has come."""
    from indico_agents.runtime.backoff import next_run_after, should_give_up

    now = now_utc()
    entries = (OutboxEntry.query
               .filter(OutboxEntry.state == OutboxState.pending, OutboxEntry.next_attempt_dt <= now)
               .order_by(OutboxEntry.next_attempt_dt)
               .limit(limit)
               .with_for_update(skip_locked=True, of=OutboxEntry)
               .all())
    for entry in entries:
        deliver(entry, now=now, next_run_after=next_run_after, should_give_up=should_give_up)
    db.session.flush()
    return entries


def deliver(entry, *, now=None, next_run_after=None, should_give_up=None):
    now = now or now_utc()
    entry.attempts += 1
    target_handler = _HANDLERS.get(entry.target)
    if target_handler is None:
        entry.state = OutboxState.failed
        entry.last_error = f'no handler registered for target {entry.target}'
        return entry
    try:
        entry.external_ref = target_handler(entry) or ''
    except Exception as exc:  # noqa: BLE001
        entry.last_error = str(exc)[:2000]
        if should_give_up and should_give_up(entry.attempts, entry.max_attempts):
            entry.state = OutboxState.abandoned
            logger.error('giving up on outbox entry %d for %s', entry.id, entry.target)
        elif next_run_after:
            entry.next_attempt_dt = next_run_after(now, entry.attempts, rand=random.random)
        return entry
    entry.state = OutboxState.sent
    entry.delivered_dt = now
    entry.last_error = ''
    return entry
