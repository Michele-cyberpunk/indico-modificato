# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Orchestration around the pure rules engine.

The split is the point of this module: `evaluate_registration` is read-only and
may be called by anyone, including agents; `propose_assignment` writes a
proposal; `approve_assignment` is the only function that grants credits, and it
requires an authenticated, authorized person.
"""

from decimal import Decimal

from indico.core.db import db
from indico.util.date_time import now_utc

from indico_ecm.models.credits import AssignmentState, CreditAssignment
from indico_ecm.models.provider import AccreditationState
from indico_ecm.services import attendance as attendance_service
from indico_ecm.services.credit_rules import Participation, evaluate
from indico_ecm.services.rules_repository import get_ruleset_for_accreditation


class NotAuthorized(Exception):
    """Raised when an actor tries to do something only a person may do."""


def build_participation(registration, *, hcp_profile=None, assessment=None, survey_completed=None):
    """Collect everything known about a participant, as pure data."""
    profile = hcp_profile if hcp_profile is not None else find_hcp_profile(registration)
    correct, total = assessment or _find_assessment(registration)
    return Participation(
        intervals=attendance_service.build_intervals(registration),
        profession=(profile.profession if profile else ''),
        discipline=(profile.discipline if profile else ''),
        profile_verified=bool(profile and profile.verification_status.name == 'verified'),
        registration_confirmed=registration.state.name in ('complete', 'unpaid'),
        payment_settled=registration.state.name != 'unpaid',
        assessment_correct=correct,
        assessment_total=total,
        survey_completed=(survey_completed if survey_completed is not None
                          else _has_completed_survey(registration)),
        exclusion_flags=frozenset(profile.eligibility_flags) if profile and profile.eligibility_flags else frozenset(),
    )


def evaluate_registration(registration, *, accreditation=None):
    """Evaluate a registration without writing anything.

    This is what agents and the front desk call. It never touches the database,
    so it is safe to run in bulk and to expose read-only.
    """
    accreditation = accreditation or registration.event.ecm_accreditation
    if accreditation is None:
        raise ValueError(f'event {registration.event_id} has no accreditation dossier')
    rules = get_ruleset_for_accreditation(accreditation)
    program = attendance_service.build_program(registration.event)
    participation = build_participation(registration)
    return evaluate(rules, participation, program)


def propose_assignment(registration, *, agent_run_id=None, accreditation=None):
    """Store the outcome as a proposal.

    A proposal grants nothing. It exists so a person can review the list, and so
    that an agent's work leaves a reviewable artefact instead of an opinion.
    """
    accreditation = accreditation or registration.event.ecm_accreditation
    outcome = evaluate_registration(registration, accreditation=accreditation)
    assignment = (CreditAssignment.query
                  .filter(CreditAssignment.registration_id == registration.id,
                          CreditAssignment.state != AssignmentState.revoked)
                  .first())
    if assignment is not None and assignment.state == AssignmentState.approved:
        # approved assignments are never overwritten by a new evaluation
        return assignment
    if assignment is None:
        assignment = CreditAssignment(registration_id=registration.id, event_id=registration.event_id,
                                      accreditation_id=accreditation.id)
        db.session.add(assignment)
    assignment.state = AssignmentState.proposed if outcome.eligible else AssignmentState.denied
    assignment.credits = outcome.credits
    assignment.rule_version = outcome.rule_version
    assignment.outcome = outcome.as_dict()
    assignment.proposed_dt = now_utc()
    assignment.proposed_by_agent_run_id = agent_run_id
    assignment.hcp_contact_id = _find_contact_id(registration)
    db.session.flush()
    return assignment


def approve_assignment(assignment, *, user):
    """Grant the credits. The only place in the codebase that does.

    Requires a person: there is no code path that lets an agent, a job or a
    webhook reach this function with a machine identity.
    """
    if user is None or getattr(user, 'is_system', False):
        raise NotAuthorized('credits can only be approved by a person')
    if assignment.state == AssignmentState.denied:
        raise ValueError('a denied assignment cannot be approved; fix the underlying data and re-evaluate')
    if assignment.state == AssignmentState.revoked:
        raise ValueError('a revoked assignment cannot be re-approved')
    if assignment.accreditation.state != AccreditationState.accredited:
        raise ValueError('credits cannot be granted against a dossier that is not accredited')
    if assignment.credits <= Decimal(0):
        raise ValueError('cannot approve an assignment with no credits')
    assignment.state = AssignmentState.approved
    assignment.approved_dt = now_utc()
    assignment.approved_by = user
    db.session.flush()
    return assignment


def revoke_assignment(assignment, *, user, reason):
    if user is None:
        raise NotAuthorized('credits can only be revoked by a person')
    if not reason or not reason.strip():
        raise ValueError('revoking credits requires a written reason')
    assignment.state = AssignmentState.revoked
    assignment.revoked_dt = now_utc()
    assignment.revoked_reason = reason.strip()
    db.session.flush()
    return assignment


def eligible_registrations(event):
    """Registrations whose evaluation currently comes out eligible.

    Used to prepare the certificate batch. Read-only by design: it returns what
    the rules say today, not what has been granted.
    """
    accreditation = event.ecm_accreditation
    results = []
    for registration in event.registrations:
        if registration.is_deleted:
            continue
        outcome = evaluate_registration(registration, accreditation=accreditation)
        if outcome.eligible:
            results.append((registration, outcome))
    return results


def find_hcp_profile(registration):
    try:
        from indico_crm.models.contacts import Contact
        from indico_crm.models.hcp_profiles import HCPProfile
    except ImportError:
        return None
    if registration.user_id is None:
        return None
    contact = Contact.query.filter_by(user_id=registration.user_id, is_deleted=False).first()
    if contact is None:
        return None
    return HCPProfile.query.filter_by(contact_id=contact.id).first()


def _find_contact_id(registration):
    profile = find_hcp_profile(registration)
    return profile.contact_id if profile else None


def _find_assessment(registration):
    """Read the learning assessment result, if the event has one.

    Returns `(None, None)` when no assessment exists, which the rules engine
    reports as `assessment_missing` rather than as a failure.
    """
    from indico_ecm.models.assessments import AssessmentResult
    result = (AssessmentResult.query
              .filter_by(registration_id=registration.id)
              .order_by(AssessmentResult.created_dt.desc())
              .first())
    if result is None:
        return None, None
    return result.correct_answers, result.total_questions


def _has_completed_survey(registration):
    from indico.modules.events.surveys.models.submissions import SurveySubmission
    from indico.modules.events.surveys.models.surveys import Survey
    if registration.user_id is None:
        return False
    return db.session.query(
        SurveySubmission.query
        .join(Survey)
        .filter(Survey.event_id == registration.event_id,
                SurveySubmission.user_id == registration.user_id,
                SurveySubmission.is_submitted)
        .exists()
    ).scalar()
