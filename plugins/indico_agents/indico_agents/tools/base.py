# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The tool registry.

Ported from the tool layer of trycompai/crm, where each capability is one
explicit, typed function rather than free-form access. Everything an agent can
do passes through `call`, which is the single place where the permission table
is consulted and the audit row is written — there is no second path.
"""

import time
from dataclasses import dataclass

from indico.core.logger import Logger

from indico_agents.governance import audit, policies


logger = Logger.get('plugin.agents.tools')

_REGISTRY = {}


@dataclass(frozen=True)
class Tool:
    name: str
    func: object
    description: str
    writes: bool


def tool(name, *, description='', writes=False):
    """Register a callable as an agent tool.

    Registering does not grant access: a tool is callable only if it also
    appears in `governance.policy_rules.TOOL_POLICIES`.
    """
    def decorator(func):
        _REGISTRY[name] = Tool(name=name, func=func, description=description or (func.__doc__ or '').strip(),
                               writes=writes)
        return func
    return decorator


def get_tool(name):
    return _REGISTRY.get(name)


def available(agent):
    """Tools this agent may actually call, in name order."""
    return tuple(sorted(name for name in _REGISTRY if policies.is_allowed(agent, name)))


def call(agent, context, name, **kwargs):
    """Invoke a tool on behalf of an agent.

    Order matters: authorization first, then execution, then the audit row —
    including when the call fails, because a failed write attempt is exactly
    what someone reviewing an incident needs to see.
    """
    policy = policies.check(agent, name, run=context.run)
    registered = get_tool(name)
    if registered is None:
        raise LookupError(f'tool {name!r} is authorized but not implemented')

    started = time.monotonic()
    try:
        result = registered.func(context, **kwargs)
    except Exception as exc:
        audit.log_tool_call(context.run, name, arguments=_safe_arguments(kwargs), is_write=policy.writes,
                            succeeded=False, error=str(exc),
                            duration_ms=int((time.monotonic() - started) * 1000))
        raise
    audit.log_tool_call(context.run, name, arguments=_safe_arguments(kwargs), is_write=policy.writes,
                        succeeded=True, duration_ms=int((time.monotonic() - started) * 1000))
    return result


#: Argument names that must never reach the audit table in clear text
SENSITIVE_KEYS = frozenset({'tax_code', 'email', 'phone', 'registry_number', 'password', 'token'})


def _safe_arguments(kwargs):
    """Redact direct identifiers before they are stored or sent to a model."""
    return {key: ('<redacted>' if key in SENSITIVE_KEYS else value) for key, value in kwargs.items()}
