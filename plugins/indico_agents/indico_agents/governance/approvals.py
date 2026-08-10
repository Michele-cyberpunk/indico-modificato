# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Human-in-the-loop approvals.

Ported from `lib/approval.ts`. An agent proposes a concrete change; a person
approves it; a registered applier performs it. The agent's reasoning is not
re-run at approval time — what was reviewed is what gets applied.
"""

from indico.core.db import db
from indico.core.logger import Logger
from indico.util.date_time import now_utc

from indico_agents.models.approvals import Approval, ApprovalState


logger = Logger.get('plugin.agents.approvals')

#: action name -> callable(approval, user) applying the change
_APPLIERS = {}


class ApprovalError(Exception):
    pass


def applier(action):
    """Register the function that performs an approved action."""
    def decorator(func):
        _APPLIERS[action] = func
        return func
    return decorator


def request_approval(*, action, subject_type, subject_id, rationale, proposed_change, run=None, event_id=None,
                     expires_dt=None):
    """Record a proposal awaiting a human decision.

    Identical pending proposals are reused: an agent that runs three times must
    not produce three copies of the same request for the same person to triage.
    """
    existing = (Approval.query
                .filter_by(action=action, subject_type=subject_type, subject_id=subject_id,
                           state=ApprovalState.pending)
                .first())
    if existing is not None:
        existing.proposed_change = proposed_change
        existing.rationale = rationale
        db.session.flush()
        return existing

    approval = Approval(action=action, subject_type=subject_type, subject_id=subject_id, event_id=event_id,
                        rationale=rationale, proposed_change=proposed_change, expires_dt=expires_dt,
                        run=run)
    db.session.add(approval)
    db.session.flush()
    logger.info('approval requested: %s on %s %s', action, subject_type, subject_id)
    return approval


def approve(approval, *, user, note=''):
    """Approve and apply.

    The applier runs inside the approving request, so a failure to apply leaves
    the approval visibly un-applied instead of silently accepted.
    """
    if user is None:
        raise ApprovalError('approvals require an authenticated user')
    if approval.state != ApprovalState.pending:
        raise ApprovalError(f'approval is {approval.state.name}, not pending')
    if approval.expires_dt is not None and approval.expires_dt < now_utc():
        approval.state = ApprovalState.expired
        db.session.flush()
        raise ApprovalError('approval expired')

    approval.state = ApprovalState.approved
    approval.decided_dt = now_utc()
    approval.decided_by = user
    approval.decision_note = note
    db.session.flush()

    apply_func = _APPLIERS.get(approval.action)
    if apply_func is None:
        # the approval stays approved-but-not-applied on purpose: a reviewer must
        # never be left believing something happened when nothing did
        logger.error('no applier registered for action %s (approval %d approved but not applied)',
                     approval.action, approval.id)
        raise ApprovalError(f"nessun esecutore registrato per l'azione {approval.action}")
    apply_func(approval, user)
    approval.state = ApprovalState.applied
    approval.applied_dt = now_utc()
    db.session.flush()
    return approval


def reject(approval, *, user, note=''):
    if user is None:
        raise ApprovalError('approvals require an authenticated user')
    if approval.state != ApprovalState.pending:
        raise ApprovalError(f'approval is {approval.state.name}, not pending')
    approval.state = ApprovalState.rejected
    approval.decided_dt = now_utc()
    approval.decided_by = user
    approval.decision_note = note
    db.session.flush()
    return approval


def expire_stale():
    """Mark overdue proposals as expired.

    A proposal nobody looked at is not approved by default: silence is a no.
    """
    stale = (Approval.query
             .filter(Approval.state == ApprovalState.pending, Approval.expires_dt.isnot(None),
                     Approval.expires_dt < now_utc())
             .all())
    for approval in stale:
        approval.state = ApprovalState.expired
    db.session.flush()
    return stale


def pending_count(event_id=None):
    query = Approval.query.filter_by(state=ApprovalState.pending)
    if event_id is not None:
        query = query.filter_by(event_id=event_id)
    return query.count()
