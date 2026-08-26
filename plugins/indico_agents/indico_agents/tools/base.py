# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The tool registry.

The design follows the tool layer of trycompai/crm — each capability is one
explicit, typed function rather than free-form access — reimplemented here in
Python; no code is shared between the two projects.

Everything an agent can do passes through `call`, which is the single place
where the permission table is consulted and the audit row is written. There is
no second path.
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
    #: Reaches outside the platform, so it draws on the run's research budget
    costly: bool = False


def tool(name, *, description='', writes=False, costly=False):
    """Register a callable as an agent tool.

    Registering does not grant access: a tool is callable only if it also
    appears in `governance.policy_rules.TOOL_POLICIES`.

    `costly` marks a tool that leaves the building. Those are the ones an agent
    will call forever if nothing stops it, so each call draws on the run's
    per-subject research budget.
    """
    def decorator(func):
        _REGISTRY[name] = Tool(name=name, func=func, description=description or (func.__doc__ or '').strip(),
                               writes=writes, costly=costly)
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

    budget = getattr(context, 'budget', None)
    subject = _subject_of(context, kwargs)
    if registered.costly and budget is not None:
        allowance = budget.spend(subject)
        if not allowance.ok:
            audit.log_tool_call(context.run, name, arguments=_safe_arguments(kwargs), is_write=False,
                                succeeded=True, error='budget di ricerca esaurito', duration_ms=0)
            return allowance.as_result()

    started = time.monotonic()
    try:
        result = registered.func(context, **kwargs)
    except Exception as exc:
        audit.log_tool_call(context.run, name, arguments=_safe_arguments(kwargs), is_write=policy.writes,
                            succeeded=False, error=str(exc),
                            duration_ms=int((time.monotonic() - started) * 1000))
        raise
    # a source that is not configured here costs nothing and must not count,
    # or an install with no providers exhausts its budget without leaving the building
    if (registered.costly and budget is not None and isinstance(result, dict)
            and result.get('configured') is False):
        budget.refund(subject)
    audit.log_tool_call(context.run, name, arguments=_safe_arguments(kwargs), is_write=policy.writes,
                        succeeded=True, duration_ms=int((time.monotonic() - started) * 1000))
    return result


def _subject_of(context, kwargs):
    """What a lookup is *about*, so the budget is per subject and not per run.

    Falls back to the task's own subject, which is what a tool called with no
    identifier is implicitly working on.
    """
    for key in ('contact_id', 'company_id', 'registration_id', 'event_id', 'subject_id'):
        if kwargs.get(key) is not None:
            return f'{key}:{kwargs[key]}'
    task = getattr(context, 'task', None)
    if task is not None and getattr(task, 'subject_id', None) is not None:
        return f'task:{task.subject_type}:{task.subject_id}'
    return 'run'


#: Argument names that must never reach the audit table in clear text
SENSITIVE_KEYS = frozenset({'tax_code', 'email', 'phone', 'registry_number', 'password', 'token'})


def _safe_arguments(kwargs):
    """Redact direct identifiers before they are stored or sent to a model."""
    return {key: ('<redacted>' if key in SENSITIVE_KEYS else value) for key, value in kwargs.items()}
