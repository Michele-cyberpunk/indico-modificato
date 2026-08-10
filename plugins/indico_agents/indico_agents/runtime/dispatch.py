# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The dispatcher.

Ported from `schedules/dispatch.ts`. It runs every minute and does exactly two
things: return abandoned leases to the pool, and hand due tasks to their agent.

The dispatcher never interprets the work. It does not know what a
`registration_check` means — it only knows that one is due. Keeping the meaning
out of the scheduler is what lets agents change without touching the plumbing.
"""

from celery.schedules import crontab

from indico.core.celery import celery
from indico.core.db import db
from indico.core.logger import Logger

from indico_agents.governance.kill_switch import agents_enabled
from indico_agents.runtime import tasks as queue
from indico_agents.runtime.runner import run_task


logger = Logger.get('plugin.agents.dispatch')

#: How many tasks a single dispatcher tick may start
BATCH_SIZE = 10


@celery.periodic_task(name='agents_dispatch', run_every=crontab(minute='*'))
def dispatch():
    """Claim due tasks and run them."""
    if not agents_enabled():
        logger.info('agent layer disabled by kill switch, skipping dispatch')
        return

    queue.reclaim_expired()
    db.session.commit()

    claimed = queue.claim_due(BATCH_SIZE)
    db.session.commit()
    if not claimed:
        return

    logger.info('dispatching %d task(s)', len(claimed))
    for task in claimed:
        run_agent_task.delay(task.id)


@celery.task(name='agents_run_task', bind=True, max_retries=0)
def run_agent_task(self, task_id):
    """Execute one task.

    Retries are the queue's job, not Celery's: a failure marks the task and
    schedules the next attempt with backoff, so the reason a task is waiting is
    always visible in the database rather than inside a broker.
    """
    from indico_agents.models.tasks import AgentTask
    task = AgentTask.get(task_id)
    if task is None:
        logger.warning('task %d disappeared before it could run', task_id)
        return
    try:
        run_task(task)
    except Exception as exc:  # noqa: BLE001
        logger.exception('task %d failed', task_id)
        queue.fail(task, exc)
        db.session.commit()
    else:
        db.session.commit()
