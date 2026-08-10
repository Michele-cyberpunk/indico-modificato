# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_agents.agents.base import AutonomyLevel
from indico_agents.governance.policy_rules import (FORBIDDEN_FOR_AGENTS, TOOL_POLICIES, evaluate, tools_for)


LEVELS = tuple(AutonomyLevel)


@pytest.mark.parametrize('action', sorted(FORBIDDEN_FOR_AGENTS))
@pytest.mark.parametrize('level', LEVELS)
def test_forbidden_actions_are_denied_at_every_level(action, level):
    allowed, reason, _policy = evaluate(level, action)
    assert not allowed
    assert 'forbidden' in reason


@pytest.mark.parametrize('level', LEVELS)
def test_unknown_tools_are_denied_by_default(level):
    allowed, reason, _policy = evaluate(level, 'some_tool_nobody_registered')
    assert not allowed
    assert 'not in the permission table' in reason


def test_regulatory_writes_are_absent_from_the_table():
    # the invariant is structural: these must never gain an entry
    for action in ('approve_credits', 'assign_credits', 'issue_certificate', 'adjust_attendance'):
        assert action not in TOOL_POLICIES


def test_read_only_agent_can_read():
    allowed, _reason, policy = evaluate(AutonomyLevel.read_only, 'verify_eligibility')
    assert allowed
    assert not policy.writes


def test_read_only_agent_cannot_draft():
    allowed, reason, _policy = evaluate(AutonomyLevel.read_only, 'draft_email')
    assert not allowed
    assert 'below required' in reason


def test_drafting_agent_cannot_write_facts_directly():
    assert not evaluate(AutonomyLevel.drafting, 'record_fact')[0]


def test_acting_agent_can_write_facts():
    allowed, _reason, policy = evaluate(AutonomyLevel.acting, 'record_fact')
    assert allowed
    assert policy.writes
    assert not policy.requires_approval


def test_every_write_below_acting_requires_approval():
    for name, policy in TOOL_POLICIES.items():
        if policy.writes and policy.min_level <= AutonomyLevel.drafting:
            assert policy.requires_approval, f'{name} writes without approval'


def test_certificate_preparation_requires_approval():
    _allowed, _reason, policy = evaluate(AutonomyLevel.drafting, 'prepare_certificate_batch')
    assert policy.requires_approval


def test_tools_grow_monotonically_with_level():
    previous = set()
    for level in LEVELS:
        current = set(tools_for(level))
        assert previous <= current
        previous = current


def test_autonomous_level_still_cannot_touch_credits():
    assert not evaluate(AutonomyLevel.autonomous, 'approve_credits')[0]
    assert not evaluate(AutonomyLevel.autonomous, 'issue_certificate')[0]
