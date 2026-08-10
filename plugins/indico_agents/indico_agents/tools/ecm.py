# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""ECM tools.

Every tool here reads. `verify_eligibility` and `simulate_credits` call the
deterministic rules engine and return its verdict verbatim: an agent can report
what the rules say, and can be wrong about nothing, because it computes nothing.
"""

from indico_agents.tools.base import tool


@tool('inspect_registration', description="Dati di una singola iscrizione e cosa manca per l'attestato.")
def inspect_registration(context, registration_id):
    from indico.modules.events.registration.models.registrations import Registration

    registration = Registration.get(registration_id)
    if registration is None or registration.is_deleted:
        return {'found': False}
    return {
        'found': True,
        'state': registration.state.name,
        'checked_in': registration.checked_in,
        'has_user': registration.user_id is not None,
        'event_id': registration.event_id,
    }


@tool('inspect_attendance', description='Presenze per sessione e anomalie di una iscrizione.')
def inspect_attendance(context, registration_id):
    from indico.modules.events.registration.models.registrations import Registration

    from indico_ecm.services import attendance as attendance_service

    registration = Registration.get(registration_id)
    if registration is None:
        return {'found': False}
    intervals = attendance_service.build_intervals(registration)
    open_rows = attendance_service.open_attendance(registration)
    return {
        'found': True,
        'closed_intervals': len(intervals),
        'open_intervals': len(open_rows),
        'minutes': sum(interval.minutes for interval in intervals),
    }


@tool('verify_eligibility', description='Verdetto del motore regole per una iscrizione. Sola lettura.')
def verify_eligibility(context, registration_id):
    from indico.modules.events.registration.models.registrations import Registration

    from indico_ecm.services import eligibility as eligibility_service

    registration = Registration.get(registration_id)
    if registration is None:
        return {'found': False}
    outcome = eligibility_service.evaluate_registration(registration)
    return {'found': True} | outcome.as_dict()


@tool('simulate_credits', description='Simulazione "e se restasse altri N minuti". Non scrive nulla.')
def simulate_credits(context, registration_id, extra_minutes=0):
    from indico.modules.events.registration.models.registrations import Registration

    from indico_ecm.services import attendance as attendance_service
    from indico_ecm.services import eligibility as eligibility_service
    from indico_ecm.services.credit_rules import simulate
    from indico_ecm.services.rules_repository import get_ruleset_for_accreditation

    registration = Registration.get(registration_id)
    if registration is None:
        return {'found': False}
    accreditation = registration.event.ecm_accreditation
    rules = get_ruleset_for_accreditation(accreditation)
    program = attendance_service.build_program(registration.event)
    participation = eligibility_service.build_participation(registration)
    outcome = simulate(rules, participation, program, extra_minutes=extra_minutes)
    return {'found': True, 'extra_minutes': extra_minutes} | outcome.as_dict()


@tool('list_certificate_candidates', description='Iscritti attualmente idonei secondo il motore regole.')
def list_certificate_candidates(context, event_id):
    from indico.modules.events import Event

    from indico_ecm.services import eligibility as eligibility_service

    event = Event.get(event_id)
    if event is None:
        return {'found': False}
    candidates = eligibility_service.eligible_registrations(event)
    return {
        'found': True,
        'count': len(candidates),
        'registration_ids': [registration.id for registration, _outcome in candidates],
    }
