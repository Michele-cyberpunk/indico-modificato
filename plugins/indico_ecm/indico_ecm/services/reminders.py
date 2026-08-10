# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Reminders.

The legacy application had two independent mechanisms: "special reminders",
rows with a task and a date that fire on exactly that day, and the checklist,
which nobody was reminded about at all. Both are here, and the second one is the
addition that matters: a deadline the platform knows about is a reminder nobody
has to remember to create.

One behaviour is deliberately changed. The original fired a reminder only when
the date was exactly today, so a day off meant the reminder was never seen.
Here a reminder stays due until it is dismissed, and `due_reminders` reports how
late it is.

Pure, no Indico imports.
"""

from dataclasses import dataclass, field
from datetime import date

from indico_ecm.services.deliverables import Urgency, attention_list


@dataclass(frozen=True)
class Reminder:
    task: str
    remind_on: date | None
    event_code: str = ''
    event_name: str = ''
    event_place: str = ''
    dismissed: bool = False
    #: Set when the reminder came from the legacy archive
    legacy: bool = False
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DueReminder:
    reminder: Reminder
    days_late: int

    @property
    def is_overdue(self):
        return self.days_late > 0


def due_reminders(reminders, today, *, include_future_days=0):
    """Reminders that should be shown today, most overdue first.

    `include_future_days` allows a "what is coming this week" view without a
    second query.
    """
    due = []
    for reminder in reminders:
        if reminder.dismissed or reminder.remind_on is None:
            continue
        days_late = (today - reminder.remind_on).days
        if days_late >= -include_future_days:
            due.append(DueReminder(reminder=reminder, days_late=days_late))
    due.sort(key=lambda item: -item.days_late)
    return tuple(due)


def overdue_only(reminders, today):
    return tuple(item for item in due_reminders(reminders, today) if item.is_overdue)


def reminders_from_checklist(states, event_date, today, *, event_name='', event_code='', lead_times=None):
    """Turn late checklist items into reminders.

    This is what the legacy dashboard could not do: it showed a red flag, but
    somebody still had to look at the screen. A deadline that has passed becomes
    a reminder with a date, which the queue can act on.
    """
    generated = []
    for status in attention_list(states, event_date, today, lead_times=lead_times):
        label = status.deliverable.value.replace('_', ' ')
        prefix = 'Scaduto' if status.urgency is Urgency.missed else 'In ritardo'
        generated.append(Reminder(
            task=f'{prefix}: {label}',
            remind_on=status.deadline,
            event_code=event_code,
            event_name=event_name,
            extra={'deliverable': status.deliverable.value, 'urgency': status.urgency.value,
                   'days_to_event': status.days_to_event},
        ))
    return tuple(generated)


def next_reminder_date(reminders, today):
    """The next date something has to be looked at, if any."""
    future = [reminder.remind_on for reminder in reminders
              if reminder.remind_on and not reminder.dismissed and reminder.remind_on >= today]
    return min(future) if future else None


def group_by_event(reminders):
    """Reminders grouped by event code, for a per-event view."""
    grouped = {}
    for reminder in reminders:
        grouped.setdefault(reminder.event_code, []).append(reminder)
    return grouped
