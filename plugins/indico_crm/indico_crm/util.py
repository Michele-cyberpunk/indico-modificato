# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.logger import Logger


logger = Logger.get('plugin.crm')


def enqueue_agent_task(kind, subject_type, subject_id, *, event_id=None, delay=0, payload=None, priority=0):
    """Queue work for the agent layer, if it is installed.

    The CRM must keep working without the agents plugin, so this is a soft
    dependency: when `indico_agents` is missing the call is a no-op and the
    request path is unaffected.
    """
    try:
        from indico_agents.runtime.tasks import schedule_task
    except ImportError:
        logger.debug('agent layer not installed, dropping task %s for %s %s', kind, subject_type, subject_id)
        return None
    return schedule_task(kind, subject_type, subject_id, event_id=event_id, delay=delay,
                         payload=payload or {}, priority=priority)
