# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The permission table for agent tools.

Pure data and one pure function, kept free of Indico imports so the matrix can
be read and tested on its own. Authorization must be inspectable without
starting the application: "what can the agents do?" should be answerable by
reading one file.

Regulatory writes are not modelled as a high permission level — they are absent
from the table and listed as forbidden. There is no autonomy level at which an
agent grants credits or issues a certificate.
"""

from dataclasses import dataclass

from indico_agents.agents.base import AutonomyLevel


@dataclass(frozen=True)
class ToolPolicy:
    #: Minimum autonomy level of the calling agent
    min_level: AutonomyLevel
    #: Whether the call writes data
    writes: bool = False
    #: Whether the effect only lands after a human approves
    requires_approval: bool = False


TOOL_POLICIES = {
    # read-only
    'read_contact_history': ToolPolicy(AutonomyLevel.read_only),
    'read_company_history': ToolPolicy(AutonomyLevel.read_only),
    'search_crm': ToolPolicy(AutonomyLevel.read_only),
    'identify_contact': ToolPolicy(AutonomyLevel.read_only),
    'list_outstanding_work': ToolPolicy(AutonomyLevel.read_only),
    'inspect_registration': ToolPolicy(AutonomyLevel.read_only),
    'inspect_attendance': ToolPolicy(AutonomyLevel.read_only),
    'verify_eligibility': ToolPolicy(AutonomyLevel.read_only),
    'simulate_credits': ToolPolicy(AutonomyLevel.read_only),
    'list_certificate_candidates': ToolPolicy(AutonomyLevel.read_only),
    'write_brief': ToolPolicy(AutonomyLevel.read_only),
    'inspect_event_checklist': ToolPolicy(AutonomyLevel.read_only),
    'list_due_reminders': ToolPolicy(AutonomyLevel.read_only),
    'invitation_costs': ToolPolicy(AutonomyLevel.read_only),
    'prepare_graphic_brief': ToolPolicy(AutonomyLevel.read_only),
    # drafting: produces proposals a person applies
    'draft_email': ToolPolicy(AutonomyLevel.drafting, writes=True, requires_approval=True),
    'prepare_certificate_batch': ToolPolicy(AutonomyLevel.drafting, writes=True, requires_approval=True),
    'draft_accreditation_request': ToolPolicy(AutonomyLevel.drafting, requires_approval=True),
    'prepare_invitation_letters': ToolPolicy(AutonomyLevel.drafting, requires_approval=True),
    # acting: non-regulatory writes, audited
    'record_fact': ToolPolicy(AutonomyLevel.acting, writes=True),
    'create_task': ToolPolicy(AutonomyLevel.acting, writes=True),
    'schedule_recheck': ToolPolicy(AutonomyLevel.acting, writes=True),
    'enrich_company': ToolPolicy(AutonomyLevel.acting, writes=True),
    'create_checklist': ToolPolicy(AutonomyLevel.acting, writes=True),
    'create_reminder': ToolPolicy(AutonomyLevel.acting, writes=True),
    'research_company': ToolPolicy(AutonomyLevel.acting),
}

#: Names that are approval actions rather than tools: an agent proposes them
#: through `request_approval`, and a person's approval is what performs them.
#: They are intentionally absent from the table above.
APPROVAL_ACTIONS = frozenset({'link_contact', 'create_contact', 'send_email', 'issue_certificates'})

FORBIDDEN_FOR_AGENTS = frozenset({
    'approve_credits',
    'assign_credits',
    'issue_certificate',
    'revoke_certificate',
    'adjust_attendance',
    'edit_accreditation',
    'send_email_directly',
    'delete_contact',
})


def evaluate(level: AutonomyLevel, tool_name: str):
    """Return `(allowed, reason, policy)` for a call at the given level."""
    if tool_name in FORBIDDEN_FOR_AGENTS:
        return False, 'action is forbidden for automated actors', None
    policy = TOOL_POLICIES.get(tool_name)
    if policy is None:
        return False, 'tool is not in the permission table', None
    if level < policy.min_level:
        return False, f'agent level {int(level)} below required {int(policy.min_level)}', policy
    return True, '', policy


def tools_for(level: AutonomyLevel):
    """Every tool an agent at this level may call."""
    return tuple(sorted(name for name, policy in TOOL_POLICIES.items() if level >= policy.min_level))
