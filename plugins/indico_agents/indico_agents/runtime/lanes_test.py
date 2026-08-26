# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico_agents.runtime.lanes import LANES, RESEARCH, RESEARCH_KINDS, VISIBLE, get_lane, lane_for


def test_work_someone_waits_on_is_visible_by_default():
    for kind in ('credit_evaluation', 'checklist_review', 'registration_check', 'event_setup',
                 'attendance_reconcile', 'contact_resolution'):
        assert lane_for(kind) == VISIBLE.name


def test_work_that_leaves_the_building_goes_to_the_slow_lane():
    for kind in RESEARCH_KINDS:
        assert lane_for(kind) == RESEARCH.name


def test_an_unknown_kind_defaults_to_the_fast_lane():
    # being late is a smaller problem than blocking everything else
    assert lane_for('something_new') == VISIBLE.name


def test_the_fast_lane_claims_more_and_holds_shorter():
    assert VISIBLE.batch > RESEARCH.batch
    assert VISIBLE.lease_seconds < RESEARCH.lease_seconds


def test_the_slow_lane_holds_long_enough_for_an_outside_call():
    assert RESEARCH.lease_seconds >= 600


def test_lanes_are_drained_fast_first():
    assert LANES[0] is VISIBLE


def test_an_unknown_lane_name_still_drains():
    assert get_lane('vecchia-corsia') is VISIBLE
    assert get_lane('research') is RESEARCH


def test_every_lane_says_what_it_is_for():
    assert all(lane.description for lane in LANES)
    assert len({lane.name for lane in LANES}) == len(LANES)
