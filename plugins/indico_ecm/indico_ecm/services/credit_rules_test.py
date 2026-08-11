# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from indico_ecm.services.credit_rules import (CreditsMode, Interval, Participation, ProgramSlot, Reason, RuleSet,
                                              Rounding, attended_minutes, evaluate, merge_intervals,
                                              program_minutes, simulate)


DAY = datetime(2026, 9, 15, 9, 0)


def at(hour, minute=0):
    return DAY.replace(hour=hour, minute=minute)


@pytest.fixture
def program():
    """A 6-hour day: 9-13 and 14-16, with an uncounted lunch break."""
    return (
        ProgramSlot(at(9), at(13), session_id=1),
        ProgramSlot(at(13), at(14), session_id=2, counts_as_training=False),
        ProgramSlot(at(14), at(16), session_id=3),
    )


@pytest.fixture
def rules():
    return RuleSet(version='2026.1', accredited_credits=Decimal(9), min_attendance_ratio=Decimal('0.9'),
                   assessment_pass_ratio=Decimal('0.75'))


def full_attendance():
    return (Interval(at(9), at(13), 1), Interval(at(14), at(16), 3))


def compliant(**kwargs):
    defaults = {
        'intervals': full_attendance(),
        'profile_verified': True,
        'assessment_correct': 8,
        'assessment_total': 10,
        'survey_completed': True,
    }
    return Participation(**(defaults | kwargs))


def test_program_minutes_excludes_breaks(program):
    assert program_minutes(program) == Decimal(360)


def test_merge_overlapping_intervals():
    merged = merge_intervals([Interval(at(9), at(11)), Interval(at(10), at(12)), Interval(at(14), at(15))])
    assert merged == (Interval(at(9), at(12)), Interval(at(14), at(15)))


def test_double_checkin_is_not_counted_twice(program):
    intervals = (Interval(at(9), at(13), 1), Interval(at(9), at(13), 1), Interval(at(14), at(16), 3))
    assert attended_minutes(intervals, program) == Decimal(360)


def test_presence_outside_the_program_is_clipped(program):
    intervals = (Interval(at(8), at(13), 1), Interval(at(14), at(18), 3))
    assert attended_minutes(intervals, program) == Decimal(360)


def test_presence_during_lunch_does_not_count(program):
    intervals = (Interval(at(13), at(14), 2),)
    assert attended_minutes(intervals, program) == Decimal(0)


def test_full_attendance_earns_the_accredited_credits(program, rules):
    outcome = evaluate(rules, compliant(), program)
    assert outcome.eligible
    assert outcome.credits == Decimal(9)
    assert outcome.reasons == ()
    assert outcome.attendance_ratio == Decimal('1.0000')
    assert outcome.rule_version == '2026.1'


def test_attendance_just_below_threshold_is_denied(program, rules):
    # 315 of 360 minutes = 87.5%
    intervals = (Interval(at(9), at(13), 1), Interval(at(14), at(15), 3), Interval(at(15), at(15, 15), 3))
    outcome = evaluate(rules, compliant(intervals=intervals), program)
    assert not outcome.eligible
    assert outcome.credits == Decimal(0)
    assert Reason.attendance_below_threshold in outcome.reasons


def test_attendance_exactly_at_threshold_is_accepted(program, rules):
    # 324 of 360 minutes = 90%
    intervals = (Interval(at(9), at(13), 1), Interval(at(14), at(15, 24), 3))
    outcome = evaluate(rules, compliant(intervals=intervals), program)
    assert outcome.eligible
    assert outcome.attendance_ratio == Decimal('0.9000')


def test_no_attendance_at_all(program, rules):
    outcome = evaluate(rules, compliant(intervals=()), program)
    assert Reason.no_attendance_recorded in outcome.reasons
    assert Reason.attendance_below_threshold not in outcome.reasons


def test_failed_assessment_denies_credits(program, rules):
    outcome = evaluate(rules, compliant(assessment_correct=7, assessment_total=10), program)
    assert not outcome.eligible
    assert outcome.reasons == (Reason.assessment_failed,)
    assert outcome.assessment_ratio == Decimal('0.7000')


def test_missing_assessment_is_reported_separately(program, rules):
    outcome = evaluate(rules, compliant(assessment_correct=None, assessment_total=None), program)
    assert outcome.reasons == (Reason.assessment_missing,)


def test_missing_survey_denies_credits(program, rules):
    outcome = evaluate(rules, compliant(survey_completed=False), program)
    assert outcome.reasons == (Reason.survey_missing,)


def test_unverified_profile_denies_credits(program, rules):
    outcome = evaluate(rules, compliant(profile_verified=False), program)
    assert outcome.reasons == (Reason.profile_unverified,)


def test_all_failing_reasons_are_reported_together(program, rules):
    outcome = evaluate(rules, compliant(intervals=(), profile_verified=False, survey_completed=False,
                                        assessment_correct=1, assessment_total=10), program)
    assert set(outcome.reasons) == {Reason.profile_unverified, Reason.no_attendance_recorded,
                                    Reason.assessment_failed, Reason.survey_missing}


def test_profession_not_accredited(program, rules):
    restricted = RuleSet(version='2026.1', accredited_credits=Decimal(9),
                         accredited_professions=frozenset({'Medico chirurgo'}))
    outcome = evaluate(restricted, compliant(profession='Infermiere'), program)
    assert outcome.reasons == (Reason.profession_not_accredited,)


def test_faculty_excluded_from_own_credits(program, rules):
    outcome = evaluate(rules, compliant(is_faculty=True, faculty_may_earn_credits=False), program)
    assert outcome.reasons == (Reason.faculty_not_eligible,)


def test_exclusion_flag_wins_over_everything(program, rules):
    outcome = evaluate(rules, compliant(exclusion_flags=frozenset({'quota_reached'})), program)
    assert Reason.excluded_by_flag in outcome.reasons
    assert outcome.credits == Decimal(0)


def test_per_hour_mode(program):
    rules = RuleSet(version='2026.2', credits_mode=CreditsMode.per_hour, credits_per_hour=Decimal('1.5'),
                    assessment_required=False, survey_required=False, require_verified_profile=False)
    outcome = evaluate(rules, Participation(intervals=full_attendance()), program)
    assert outcome.credits == Decimal('9.00')


def test_per_hour_mode_respects_max_credits(program):
    rules = RuleSet(version='2026.2', credits_mode=CreditsMode.per_hour, credits_per_hour=Decimal('1.5'),
                    max_credits=Decimal(5), assessment_required=False, survey_required=False,
                    require_verified_profile=False)
    outcome = evaluate(rules, Participation(intervals=full_attendance()), program)
    assert outcome.credits == Decimal(5)


@pytest.mark.parametrize(('rounding', 'expected'), (
    (Rounding.exact, Decimal('7.25')),
    (Rounding.half_down, Decimal('7.0')),
    (Rounding.half_nearest, Decimal('7.5')),
    (Rounding.integer_down, Decimal(7)),
))
def test_rounding_modes(program, rounding, expected):
    rules = RuleSet(version='2026.3', accredited_credits=Decimal('7.25'), rounding=rounding,
                    assessment_required=False, survey_required=False, require_verified_profile=False)
    outcome = evaluate(rules, Participation(intervals=full_attendance()), program)
    assert outcome.credits == expected


def test_outcome_is_serializable_for_audit(program, rules):
    data = evaluate(rules, compliant(), program).as_dict()
    assert data['eligible'] is True
    assert data['credits'] == '9'
    assert data['rule_version'] == '2026.1'
    assert data['reasons'] == []


def test_denied_outcome_serializes_reason_codes(program, rules):
    data = evaluate(rules, compliant(survey_completed=False), program).as_dict()
    assert data['reasons'] == ['survey_missing']


def test_simulate_does_not_mutate_participation(program, rules):
    intervals = (Interval(at(9), at(13), 1), Interval(at(14), at(15), 3))
    participation = compliant(intervals=intervals)
    denied = evaluate(rules, participation, program)
    hypothetical = simulate(rules, participation, program, extra_minutes=60)
    assert not denied.eligible
    assert hypothetical.eligible
    assert participation.intervals == intervals


def test_evaluation_is_reproducible(program, rules):
    participation = compliant()
    assert evaluate(rules, participation, program) == evaluate(rules, participation, program)


def test_interval_cannot_end_before_it_starts():
    with pytest.raises(ValueError, match='ends before it starts'):
        Interval(at(12), at(11))


def test_zero_length_program_denies_rather_than_dividing_by_zero(rules):
    outcome = evaluate(rules, compliant(), ())
    assert not outcome.eligible
    assert outcome.attendance_ratio == Decimal(0)
    assert Reason.no_attendance_recorded in outcome.reasons


def test_session_bound_presence_does_not_leak_into_other_sessions(program, rules):
    # checked in for session 1 only, but the interval spans the whole day
    intervals = (Interval(at(9), at(16), session_id=1),)
    assert attended_minutes(intervals, program) == Decimal(240)


def test_multi_day_program():
    program = (ProgramSlot(at(9), at(13), 1), ProgramSlot(at(9) + timedelta(days=1), at(13) + timedelta(days=1), 2))
    intervals = (Interval(at(9), at(13), 1), Interval(at(9) + timedelta(days=1), at(13) + timedelta(days=1), 2))
    assert program_minutes(program) == Decimal(480)
    assert attended_minutes(intervals, program) == Decimal(480)
