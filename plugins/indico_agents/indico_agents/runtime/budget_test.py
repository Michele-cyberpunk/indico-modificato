# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_agents.runtime.budget import DEFAULT_LIMIT, Budget


def test_a_fresh_budget_allows_the_first_lookups():
    budget = Budget()
    assert budget.remaining('contact:1') == DEFAULT_LIMIT
    assert budget.spend('contact:1').ok
    assert budget.remaining('contact:1') == DEFAULT_LIMIT - 1


def test_the_budget_refuses_instead_of_raising():
    budget = Budget(limit=2)
    assert budget.spend('contact:1').ok
    assert budget.spend('contact:1').ok
    refusal = budget.spend('contact:1')
    assert not refusal.ok
    assert 'esaurito' in refusal.reason
    # the refusal says what to do instead, which is the point of refusing
    assert 'Scrivi ciò che hai già trovato' in refusal.reason
    assert refusal.as_result()['budget_exhausted'] is True


def test_the_limit_is_per_subject_not_per_run():
    budget = Budget(limit=1)
    assert budget.spend('contact:1').ok
    # a run that touches thirty contacts must not run out on the second
    assert budget.spend('contact:2').ok
    assert not budget.spend('contact:1').ok


def test_a_multi_unit_lookup_cannot_overshoot_the_limit():
    budget = Budget(limit=3)
    assert budget.spend('contact:1', units=2).ok
    assert not budget.spend('contact:1', units=2).ok
    # but what still fits is allowed
    assert budget.spend('contact:1').ok


def test_a_refund_gives_the_allowance_back():
    budget = Budget(limit=1)
    budget.spend('contact:1')
    assert not budget.spend('contact:1').ok
    budget.refund('contact:1')
    assert budget.spend('contact:1').ok


def test_a_refund_never_goes_below_zero():
    budget = Budget()
    budget.refund('contact:1', units=5)
    assert budget.spent_on('contact:1') == 0


def test_a_zero_budget_refuses_everything():
    budget = Budget(limit=0)
    assert not budget.spend('contact:1').ok


def test_the_report_says_what_was_spent():
    budget = Budget(limit=4)
    budget.spend('contact:1', units=2)
    budget.spend('contact:2')
    assert budget.report() == {'limit': 4, 'subjects': {'contact:1': 2, 'contact:2': 1}, 'total': 3}


def test_an_impossible_budget_is_refused_at_construction():
    with pytest.raises(ValueError, match='negativo'):
        Budget(limit=-1)
    with pytest.raises(ValueError, match='almeno una unità'):
        Budget().spend('contact:1', units=0)


def test_subjects_are_compared_as_text():
    budget = Budget(limit=1)
    assert budget.spend(7).ok
    assert not budget.spend('7').ok
