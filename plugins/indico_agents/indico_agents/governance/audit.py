# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Agent activity in Indico's own audit log.

Ported from `hooks/audit.ts`. Rather than building a parallel log, agent actions
are written to the event log Indico already has, so a manager sees human and
agent actions in one timeline, in the place they already look.
"""

from indico.core.logger import Logger
from indico.modules.logs.models.entries import EventLogRealm, LogKind


logger = Logger.get('plugin.agents.audit')


def log_agent_action(event, kind, summary, *, run=None, data=None):
    """Write an agent action to the event log."""
    if event is None:
        logger.info('agent action outside an event: %s', summary)
        return None
    payload = dict(data or {})
    if run is not None:
        payload |= {'Agent': run.agent_name, 'Run': run.id,
                    'Skills': ', '.join(sorted(run.skill_versions or ()))}
    return event.log(EventLogRealm.management, kind, 'Agenti', summary, data=payload)


def log_tool_call(run, tool_name, *, arguments=None, is_write=False, succeeded=True, error='',
                  duration_ms=0):
    """Record one tool invocation on the run."""
    from indico.core.db import db

    from indico_agents.models.runs import ToolCall
    sequence = run.tool_calls.count() + 1
    call = ToolCall(run=run, sequence=sequence, tool_name=tool_name, arguments=arguments or {},
                    is_write=is_write, succeeded=succeeded, error=error[:2000], duration_ms=duration_ms)
    db.session.add(call)
    db.session.flush()
    return call


def kind_for(is_write):
    return LogKind.change if is_write else LogKind.other
