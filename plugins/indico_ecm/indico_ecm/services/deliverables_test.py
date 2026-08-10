# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import date

import pytest

from indico_ecm.services.deliverables import (Deliverable, DeliverableState, Urgency, attention_list, checklist,
                                              deadline_for, is_blocking_credits, readiness, status_for)


EVENT_DATE = date(2026, 9, 15)


def test_deadline_uses_the_lead_time():
    assert deadline_for(Deliverable.accreditation, EVENT_DATE) == date(2026, 6, 17)
    assert deadline_for(Deliverable.slide_kit, EVENT_DATE) == date(2026, 9, 8)


def test_post_event_deliverables_have_a_deadline_after_the_event():
    assert deadline_for(Deliverable.final_report, EVENT_DATE) == date(2026, 10, 15)


def test_a_post_event_deliverable_is_not_missed_the_day_after_the_event():
    status = status_for(Deliverable.final_report, DeliverableState.todo, EVENT_DATE, date(2026, 9, 16))
    assert status.urgency is Urgency.calm


def test_a_post_event_deliverable_is_missed_after_its_own_deadline():
    status = status_for(Deliverable.final_report, DeliverableState.todo, EVENT_DATE, date(2026, 10, 20))
    assert status.urgency is Urgency.missed


def test_deadline_without_an_event_date():
    assert deadline_for(Deliverable.graphics, None) is None


def test_done_deliverables_are_never_urgent():
    status = status_for(Deliverable.accreditation, DeliverableState.done, EVENT_DATE, date(2026, 9, 14))
    assert status.urgency is Urgency.calm
    assert not status.needs_attention


def test_not_applicable_is_treated_like_done():
    status = status_for(Deliverable.slide_kit, DeliverableState.not_applicable, EVENT_DATE, date(2026, 9, 14))
    assert status.urgency is Urgency.calm


def test_far_from_the_deadline_is_calm():
    status = status_for(Deliverable.graphics, DeliverableState.todo, EVENT_DATE, date(2026, 5, 1))
    assert status.urgency is Urgency.calm


def test_a_week_before_the_deadline_is_due():
    # graphics deadline is 2026-08-25, so a week earlier
    status = status_for(Deliverable.graphics, DeliverableState.todo, EVENT_DATE, date(2026, 8, 20))
    assert status.urgency is Urgency.due


def test_past_the_deadline_is_late():
    status = status_for(Deliverable.graphics, DeliverableState.todo, EVENT_DATE, date(2026, 9, 1))
    assert status.urgency is Urgency.late
    assert status.needs_attention


def test_after_the_event_is_missed():
    status = status_for(Deliverable.graphics, DeliverableState.in_progress, EVENT_DATE, date(2026, 9, 20))
    assert status.urgency is Urgency.missed


def test_days_to_event_is_reported():
    status = status_for(Deliverable.venue_option, DeliverableState.todo, EVENT_DATE, date(2026, 9, 1))
    assert status.days_to_event == 14


def test_checklist_covers_every_deliverable():
    statuses = checklist({}, EVENT_DATE, date(2026, 9, 1))
    assert len(statuses) == len(Deliverable)
    assert {status.deliverable for status in statuses} == set(Deliverable)


def test_unrecorded_deliverables_count_as_todo():
    statuses = {status.deliverable: status for status in checklist({}, EVENT_DATE, date(2026, 9, 1))}
    assert statuses[Deliverable.accreditation].state is DeliverableState.todo
    assert statuses[Deliverable.accreditation].urgency is Urgency.late


def test_attention_list_is_ordered_worst_first():
    states = dict.fromkeys(Deliverable, DeliverableState.done)
    states[Deliverable.sponsor_contract] = DeliverableState.todo
    states[Deliverable.slide_kit] = DeliverableState.todo
    attention = attention_list(states, EVENT_DATE, date(2026, 9, 10))
    # the sponsor contract was due on 17 July, the slide kit on 8 September
    assert [status.deliverable for status in attention] == [Deliverable.sponsor_contract, Deliverable.slide_kit]
    assert all(status.needs_attention for status in attention)


def test_attention_list_reports_everything_untouched():
    attention = attention_list({}, EVENT_DATE, date(2026, 9, 10))
    kinds = [status.deliverable for status in attention]
    assert kinds[0] is Deliverable.activation
    # deliverables due after the event are not late yet
    assert Deliverable.final_report not in kinds


def test_attention_list_is_empty_when_everything_is_done():
    states = dict.fromkeys(Deliverable, DeliverableState.done)
    assert attention_list(states, EVENT_DATE, date(2026, 9, 14)) == ()


@pytest.mark.parametrize(('states', 'expected'), (
    ({}, 0.0),
    (dict.fromkeys(Deliverable, DeliverableState.done), 1.0),
    ({Deliverable.accreditation: DeliverableState.done}, round(1 / len(Deliverable), 4)),
))
def test_readiness(states, expected):
    assert readiness(states) == expected


def test_readiness_ignores_not_applicable():
    states = dict.fromkeys(Deliverable, DeliverableState.not_applicable)
    states[Deliverable.accreditation] = DeliverableState.done
    assert readiness(states) == 1.0


def test_only_accreditation_blocks_credits():
    assert is_blocking_credits({})
    assert is_blocking_credits({Deliverable.graphics: DeliverableState.done})
    assert not is_blocking_credits({Deliverable.accreditation: DeliverableState.done})
