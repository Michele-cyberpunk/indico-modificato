# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Enforcement of the agent permission table.

The decision itself lives in `policy_rules` (pure, testable). This module only
applies it and records the outcome: an agent that was stopped is as interesting
to an auditor as one that acted.
"""

from indico.core.db import db
from indico.core.logger import Logger

from indico_agents.governance.policy_rules import evaluate, tools_for
from indico_agents.models.approvals import PolicyDecision


logger = Logger.get('plugin.agents.policy')


class PolicyViolation(Exception):
    pass


def check(agent, tool_name, *, run=None, record=True):
    """Decide whether `agent` may call `tool_name`, and record the decision."""
    allowed, reason, policy = evaluate(agent.autonomy, tool_name)
    if record:
        db.session.add(PolicyDecision(run_id=(run.id if run else None), agent_name=agent.name,
                                      tool_name=tool_name, allowed=allowed, reason=reason))
    if not allowed:
        logger.warning('policy denied %s -> %s (%s)', agent.name, tool_name, reason)
        raise PolicyViolation(reason)
    return policy


def is_allowed(agent, tool_name):
    """Non-raising variant, for building the tool list offered to an agent."""
    allowed, _reason, _policy = evaluate(agent.autonomy, tool_name)
    return allowed


def available_tools(agent):
    return tools_for(agent.autonomy)
