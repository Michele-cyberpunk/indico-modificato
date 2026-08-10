# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The per-event deliverable checklist.

This is the working core of the provider's day: for every upcoming event,
whether accreditation, sponsor contracts, graphics, assignment letters and the
slide kit are done. It comes from the dashboard of the Cyberbrain event manager,
where an event with any of them still open shows up as a problem.

Here the flags gain what they lacked: a lead time. "Graphics not done" means
nothing three months out and everything four days out, and the difference is
what an agent needs in order to raise a task at the right moment.

Pure functions, no Indico imports.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class Deliverable(StrEnum):
    """The preparation checklist of an event.

    One value per yes/no column of the legacy event manager, with the same
    meaning, so historical rows import without interpretation.
    """

    #: attivazione
    activation = 'activation'
    #: primo contatto relatori
    faculty_first_contact = 'faculty_first_contact'
    #: accreditamento
    accreditation = 'accreditation'
    #: contratti sponsor
    sponsor_contract = 'sponsor_contract'
    #: opzione sede
    venue_option = 'venue_option'
    #: contratto hotel
    hotel_contract = 'hotel_contract'
    #: brief hotel
    hotel_brief = 'hotel_brief'
    #: catering
    catering = 'catering'
    #: NUME / piattaforma
    platform = 'platform'
    #: grafica
    graphics = 'graphics'
    #: stampa grafiche
    graphics_printing = 'graphics_printing'
    #: lettera d'incarico
    assignment_letter = 'assignment_letter'
    #: inviti (stampa unione)
    invitations = 'invitations'
    #: documenti faculty (CV, dichiarazioni, conflitti)
    faculty_documents = 'faculty_documents'
    #: slide kit
    slide_kit = 'slide_kit'
    #: hostess
    hostess = 'hostess'
    #: foglio logistica
    logistics_sheet = 'logistics_sheet'
    #: consuntivo
    final_report = 'final_report'
    #: invio
    dispatch = 'dispatch'


class DeliverableState(StrEnum):
    todo = 'todo'
    in_progress = 'in_progress'
    done = 'done'
    not_applicable = 'not_applicable'


class Urgency(StrEnum):
    #: Nothing to do yet
    calm = 'calm'
    #: Inside the lead time, still fine
    due = 'due'
    #: Past the lead time, event not yet held
    late = 'late'
    #: The event happened without it
    missed = 'missed'


#: Days before the event each deliverable should be finished by.
#: Accreditation dominates: a dossier filed late is not a delay, it is an event
#: that cannot grant credits.
DEFAULT_LEAD_TIMES = {
    Deliverable.activation: 120,
    Deliverable.accreditation: 90,
    Deliverable.faculty_first_contact: 75,
    Deliverable.sponsor_contract: 60,
    Deliverable.venue_option: 60,
    Deliverable.hotel_contract: 45,
    Deliverable.invitations: 45,
    Deliverable.catering: 30,
    Deliverable.platform: 30,
    Deliverable.faculty_documents: 30,
    Deliverable.graphics: 21,
    Deliverable.assignment_letter: 14,
    Deliverable.graphics_printing: 10,
    Deliverable.hostess: 10,
    Deliverable.hotel_brief: 10,
    Deliverable.logistics_sheet: 7,
    Deliverable.slide_kit: 7,
    #: after the event, so the lead time is negative
    Deliverable.final_report: -30,
    Deliverable.dispatch: -15,
}


@dataclass(frozen=True)
class DeliverableStatus:
    deliverable: Deliverable
    state: DeliverableState
    urgency: Urgency
    days_to_event: int
    deadline: date | None

    @property
    def needs_attention(self):
        return self.urgency in (Urgency.late, Urgency.missed)


def deadline_for(deliverable, event_date, lead_times=None):
    lead_times = lead_times or DEFAULT_LEAD_TIMES
    days = lead_times.get(deliverable)
    if days is None or event_date is None:
        return None
    return event_date - timedelta(days=days)


def status_for(deliverable, state, event_date, today, *, lead_times=None):
    """Where one deliverable stands, relative to its lead time."""
    days_to_event = (event_date - today).days if event_date else 0
    deadline = deadline_for(deliverable, event_date, lead_times)
    #: deliverables due after the event (final report, dispatch) have a deadline
    #: later than the event itself, so the point of no return is whichever comes last
    last_chance = max(event_date, deadline) if (event_date and deadline) else (event_date or deadline)
    if state in (DeliverableState.done, DeliverableState.not_applicable):
        urgency = Urgency.calm
    elif last_chance is not None and today > last_chance:
        urgency = Urgency.missed
    elif deadline is not None and today > deadline:
        urgency = Urgency.late
    elif deadline is not None and today >= deadline - timedelta(days=7):
        urgency = Urgency.due
    else:
        urgency = Urgency.calm
    return DeliverableStatus(deliverable=deliverable, state=state, urgency=urgency,
                             days_to_event=days_to_event, deadline=deadline)


def checklist(states, event_date, today, *, lead_times=None):
    """Status of every deliverable of an event.

    Deliverables with no recorded state count as `todo`: something nobody has
    touched is exactly what tends to be forgotten.
    """
    return tuple(
        status_for(deliverable, states.get(deliverable, DeliverableState.todo), event_date, today,
                   lead_times=lead_times)
        for deliverable in Deliverable
    )


def attention_list(states, event_date, today, *, lead_times=None):
    """Only what is late or missed, worst first."""
    order = {Urgency.missed: 0, Urgency.late: 1, Urgency.due: 2, Urgency.calm: 3}
    statuses = [status for status in checklist(states, event_date, today, lead_times=lead_times)
                if status.needs_attention]
    statuses.sort(key=lambda status: (order[status.urgency], status.deadline or date.max))
    return tuple(statuses)


def readiness(states):
    """Share of applicable deliverables that are done, 0..1."""
    applicable = [states.get(deliverable, DeliverableState.todo) for deliverable in Deliverable]
    applicable = [state for state in applicable if state is not DeliverableState.not_applicable]
    if not applicable:
        return 1.0
    done = sum(1 for state in applicable if state is DeliverableState.done)
    return round(done / len(applicable), 4)


def is_blocking_credits(states):
    """Whether the event cannot grant credits as things stand.

    Only accreditation blocks: everything else is organizational, this one is
    regulatory.
    """
    return states.get(Deliverable.accreditation, DeliverableState.todo) is not DeliverableState.done
