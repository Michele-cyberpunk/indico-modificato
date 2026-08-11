# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Deterministic credit and eligibility rules.

This module is the regulatory core of the platform and is deliberately pure:
no Indico imports, no database, no I/O, no clock, no language model. Everything
it needs is passed in, so a decision can be replayed exactly as it was taken,
which is what makes it defensible months later in front of an audit.

Agents may call `evaluate` in read-only mode to prepare lists and flag
anomalies. They never decide: the outcome of this module, applied by an
authorized person, is what assigns credits.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import Enum


class CreditsMode(Enum):
    """How the credits of an activity are derived."""

    #: The accreditation grants a fixed number of credits for the whole activity
    fixed = 'fixed'
    #: Credits are proportional to the hours actually attended
    per_hour = 'per_hour'


class Rounding(Enum):
    #: Keep the exact value (e.g. 4.5)
    exact = 'exact'
    #: Round down to the nearest half credit
    half_down = 'half_down'
    #: Round to the nearest half credit
    half_nearest = 'half_nearest'
    #: Round down to a whole credit
    integer_down = 'integer_down'


class Reason(Enum):
    """Machine-readable reasons an outcome was reached.

    These are stored with the assignment, so never repurpose a value: add a new
    one instead. A participant contesting a decision must get the same reason
    string years later.
    """

    attendance_below_threshold = 'attendance_below_threshold'
    no_attendance_recorded = 'no_attendance_recorded'
    assessment_missing = 'assessment_missing'
    assessment_failed = 'assessment_failed'
    survey_missing = 'survey_missing'
    profile_unverified = 'profile_unverified'
    profession_not_accredited = 'profession_not_accredited'
    discipline_not_accredited = 'discipline_not_accredited'
    excluded_by_flag = 'excluded_by_flag'
    registration_not_confirmed = 'registration_not_confirmed'
    payment_outstanding = 'payment_outstanding'
    quota_exceeded = 'quota_exceeded'
    faculty_not_eligible = 'faculty_not_eligible'


@dataclass(frozen=True)
class Interval:
    """A period a participant was present, as recorded by check-in/check-out."""

    start: datetime
    end: datetime
    session_id: int | None = None

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError('interval ends before it starts')

    @property
    def minutes(self):
        return (self.end - self.start).total_seconds() / 60


@dataclass(frozen=True)
class ProgramSlot:
    """A slot of the accredited program that counts towards training time."""

    start: datetime
    end: datetime
    session_id: int | None = None
    #: Slots such as breaks and lunch can be part of the timetable but must not
    #: count as training time
    counts_as_training: bool = True

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError('slot ends before it starts')

    @property
    def minutes(self):
        return (self.end - self.start).total_seconds() / 60


@dataclass(frozen=True)
class RuleSet:
    """A versioned set of rules, in force for a period and a region.

    Rules are never edited in place: a change produces a new version, and every
    assignment records which version produced it.
    """

    version: str
    #: Minimum share of the accredited program that must be attended (0..1)
    min_attendance_ratio: Decimal = Decimal('0.9')
    #: Whether a learning assessment must be passed
    assessment_required: bool = True
    #: Minimum share of correct answers (0..1)
    assessment_pass_ratio: Decimal = Decimal('0.75')
    #: Whether the quality questionnaire must be completed
    survey_required: bool = True
    credits_mode: CreditsMode = CreditsMode.fixed
    #: Credits granted by the accreditation (fixed mode)
    accredited_credits: Decimal = Decimal(0)
    #: Credits per attended hour (per_hour mode)
    credits_per_hour: Decimal = Decimal(1)
    rounding: Rounding = Rounding.exact
    max_credits: Decimal | None = None
    #: Empty means every profession is accredited
    accredited_professions: frozenset[str] = frozenset()
    accredited_disciplines: frozenset[str] = frozenset()
    require_verified_profile: bool = True
    require_confirmed_registration: bool = True
    require_settled_payment: bool = False
    region: str = ''
    notes: str = ''


@dataclass(frozen=True)
class Participation:
    """Everything known about one participant's involvement in one activity."""

    intervals: tuple[Interval, ...] = ()
    profession: str = ''
    discipline: str = ''
    profile_verified: bool = False
    registration_confirmed: bool = True
    payment_settled: bool = True
    assessment_correct: int | None = None
    assessment_total: int | None = None
    survey_completed: bool = False
    #: Flags that exclude a participant regardless of everything else
    exclusion_flags: frozenset[str] = frozenset()
    #: Faculty are usually not entitled to credits for their own talk
    is_faculty: bool = False
    faculty_may_earn_credits: bool = True
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    """The result of applying a rule set to a participation."""

    eligible: bool
    credits: Decimal
    attended_minutes: Decimal
    program_minutes: Decimal
    attendance_ratio: Decimal
    assessment_ratio: Decimal | None
    reasons: tuple[Reason, ...]
    rule_version: str

    @property
    def is_denied(self):
        return not self.eligible

    def as_dict(self):
        """Serialize for storage next to the assignment."""
        return {
            'eligible': self.eligible,
            'credits': str(self.credits),
            'attended_minutes': str(self.attended_minutes),
            'program_minutes': str(self.program_minutes),
            'attendance_ratio': str(self.attendance_ratio),
            'assessment_ratio': (str(self.assessment_ratio) if self.assessment_ratio is not None else None),
            'reasons': [reason.value for reason in self.reasons],
            'rule_version': self.rule_version,
        }


def merge_intervals(intervals):
    """Merge overlapping or touching intervals.

    A participant who checks in twice by mistake, or whose badge is scanned at
    two doors, must not be credited twice for the same minutes.
    """
    ordered = sorted(intervals, key=lambda i: (i.start, i.end))
    merged: list[Interval] = []
    for interval in ordered:
        if merged and interval.start <= merged[-1].end:
            last = merged[-1]
            if interval.end > last.end:
                merged[-1] = Interval(last.start, interval.end, last.session_id)
        else:
            merged.append(interval)
    return tuple(merged)


def _overlap_minutes(a_start, a_end, b_start, b_end):
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if end <= start:
        return Decimal(0)
    return Decimal((end - start).total_seconds()) / Decimal(60)


def attended_minutes(intervals, program):
    """Minutes of presence that fall inside accredited training slots.

    Presence outside the program (arriving early, staying for the buffet) is
    real but is not training time, so it is clipped away.
    """
    training_slots = [slot for slot in program if slot.counts_as_training]
    total = Decimal(0)
    for interval in merge_intervals(intervals):
        for slot in training_slots:
            if interval.session_id is not None and slot.session_id is not None \
                    and interval.session_id != slot.session_id:
                continue
            total += _overlap_minutes(interval.start, interval.end, slot.start, slot.end)
    return total


def program_minutes(program):
    """Total accredited training time of the activity."""
    slots = [slot for slot in program if slot.counts_as_training]
    merged = merge_intervals([Interval(slot.start, slot.end, slot.session_id) for slot in slots])
    return sum((Decimal(interval.minutes) for interval in merged), Decimal(0))


def _apply_rounding(value, rounding):
    if rounding is Rounding.exact:
        return value
    if rounding is Rounding.integer_down:
        return value.quantize(Decimal(1), rounding=ROUND_DOWN)
    doubled = value * 2
    if rounding is Rounding.half_down:
        return doubled.quantize(Decimal(1), rounding=ROUND_DOWN) / 2
    return doubled.quantize(Decimal(1), rounding=ROUND_HALF_UP) / 2


def _ratio(numerator, denominator):
    if not denominator:
        return Decimal(0)
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal('0.0001'))


def _collect_reasons(rules, participation, attendance_ratio, assessment_ratio, has_attendance):
    reasons: list[Reason] = []
    if participation.exclusion_flags:
        reasons.append(Reason.excluded_by_flag)
    if rules.require_verified_profile and not participation.profile_verified:
        reasons.append(Reason.profile_unverified)
    if rules.require_confirmed_registration and not participation.registration_confirmed:
        reasons.append(Reason.registration_not_confirmed)
    if rules.require_settled_payment and not participation.payment_settled:
        reasons.append(Reason.payment_outstanding)
    if rules.accredited_professions and participation.profession not in rules.accredited_professions:
        reasons.append(Reason.profession_not_accredited)
    if rules.accredited_disciplines and participation.discipline not in rules.accredited_disciplines:
        reasons.append(Reason.discipline_not_accredited)
    if participation.is_faculty and not participation.faculty_may_earn_credits:
        reasons.append(Reason.faculty_not_eligible)
    if not has_attendance:
        reasons.append(Reason.no_attendance_recorded)
    elif attendance_ratio < rules.min_attendance_ratio:
        reasons.append(Reason.attendance_below_threshold)
    if rules.assessment_required:
        if assessment_ratio is None:
            reasons.append(Reason.assessment_missing)
        elif assessment_ratio < rules.assessment_pass_ratio:
            reasons.append(Reason.assessment_failed)
    if rules.survey_required and not participation.survey_completed:
        reasons.append(Reason.survey_missing)
    return reasons


def evaluate(rules: RuleSet, participation: Participation, program) -> Outcome:
    """Apply a rule set to a participation and return the outcome.

    Pure and total: the same inputs always produce the same result, and no
    branch raises for merely incomplete data — missing pieces come back as
    reasons, because "we do not know yet" is a legitimate state during an event.
    """
    total_program = program_minutes(program)
    attended = attended_minutes(participation.intervals, program)
    attendance_ratio = _ratio(attended, total_program)
    assessment_ratio = None
    if participation.assessment_total:
        assessment_ratio = _ratio(participation.assessment_correct or 0, participation.assessment_total)

    reasons = _collect_reasons(rules, participation, attendance_ratio, assessment_ratio, bool(attended))
    if reasons:
        return Outcome(False, Decimal(0), attended, total_program, attendance_ratio, assessment_ratio,
                       tuple(reasons), rules.version)

    if rules.credits_mode is CreditsMode.fixed:
        credits = rules.accredited_credits
    else:
        credits = (attended / Decimal(60)) * rules.credits_per_hour

    credits = _apply_rounding(credits, rules.rounding)
    if rules.max_credits is not None and credits > rules.max_credits:
        credits = rules.max_credits
    return Outcome(True, credits, attended, total_program, attendance_ratio, assessment_ratio, (), rules.version)


def simulate(rules: RuleSet, participation: Participation, program, *, extra_minutes=0) -> Outcome:
    """What-if evaluation used by agents and by the front desk.

    `extra_minutes` lets a coordinator ask "would they qualify if they stayed
    another 30 minutes?" without touching any stored attendance.
    """
    if not extra_minutes:
        return evaluate(rules, participation, program)
    intervals = list(participation.intervals)
    if intervals:
        last = intervals[-1]
        intervals[-1] = Interval(last.start, last.end + timedelta(minutes=extra_minutes), last.session_id)
    hypothetical = Participation(
        intervals=tuple(intervals),
        profession=participation.profession,
        discipline=participation.discipline,
        profile_verified=participation.profile_verified,
        registration_confirmed=participation.registration_confirmed,
        payment_settled=participation.payment_settled,
        assessment_correct=participation.assessment_correct,
        assessment_total=participation.assessment_total,
        survey_completed=participation.survey_completed,
        exclusion_flags=participation.exclusion_flags,
        is_faculty=participation.is_faculty,
        faculty_may_earn_credits=participation.faculty_may_earn_credits,
        extra=participation.extra,
    )
    return evaluate(rules, hypothetical, program)
