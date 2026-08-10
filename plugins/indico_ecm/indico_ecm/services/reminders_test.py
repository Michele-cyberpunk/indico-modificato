# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import date

from indico_ecm.services.deliverables import Deliverable, DeliverableState
from indico_ecm.services.reminders import (Reminder, due_reminders, group_by_event, next_reminder_date,
                                           overdue_only, reminders_from_checklist)


TODAY = date(2026, 9, 10)


def make(task='Chiamare hotel', when=TODAY, **kwargs):
    return Reminder(task=task, remind_on=when, **kwargs)


def test_a_reminder_due_today_is_reported():
    assert len(due_reminders([make()], TODAY)) == 1


def test_an_overdue_reminder_stays_due():
    # the legacy application only fired on the exact day, so a day off lost it
    due = due_reminders([make(when=date(2026, 9, 1))], TODAY)
    assert due[0].days_late == 9
    assert due[0].is_overdue


def test_a_future_reminder_is_not_reported():
    assert due_reminders([make(when=date(2026, 9, 20))], TODAY) == ()


def test_a_future_reminder_can_be_included_in_a_lookahead():
    assert len(due_reminders([make(when=date(2026, 9, 14))], TODAY, include_future_days=7)) == 1


def test_dismissed_reminders_are_skipped():
    assert due_reminders([make(dismissed=True)], TODAY) == ()


def test_reminders_without_a_date_are_skipped():
    assert due_reminders([make(when=None)], TODAY) == ()


def test_most_overdue_first():
    reminders = [make(task='recente', when=date(2026, 9, 9)), make(task='vecchio', when=date(2026, 8, 1))]
    assert [item.reminder.task for item in due_reminders(reminders, TODAY)] == ['vecchio', 'recente']


def test_overdue_only_excludes_today():
    reminders = [make(task='oggi'), make(task='ieri', when=date(2026, 9, 9))]
    assert [item.reminder.task for item in overdue_only(reminders, TODAY)] == ['ieri']


def test_checklist_generates_reminders_for_late_items():
    states = dict.fromkeys(Deliverable, DeliverableState.done)
    states[Deliverable.graphics] = DeliverableState.todo
    generated = reminders_from_checklist(states, date(2026, 9, 15), TODAY, event_name='Cardio',
                                         event_code='C123')
    assert len(generated) == 1
    assert generated[0].task.startswith('In ritardo: graphics')
    assert generated[0].event_code == 'C123'
    assert generated[0].extra['deliverable'] == 'graphics'


def test_checklist_generates_nothing_when_everything_is_done():
    states = dict.fromkeys(Deliverable, DeliverableState.done)
    assert reminders_from_checklist(states, date(2026, 9, 15), TODAY) == ()


def test_missed_items_are_labelled_differently():
    states = dict.fromkeys(Deliverable, DeliverableState.done)
    states[Deliverable.graphics] = DeliverableState.todo
    generated = reminders_from_checklist(states, date(2026, 9, 1), date(2026, 9, 20))
    assert generated[0].task.startswith('Scaduto: graphics')


def test_next_reminder_date():
    reminders = [make(when=date(2026, 9, 20)), make(when=date(2026, 9, 12)), make(when=date(2026, 9, 1))]
    assert next_reminder_date(reminders, TODAY) == date(2026, 9, 12)


def test_next_reminder_date_when_there_is_nothing_ahead():
    assert next_reminder_date([make(when=date(2026, 1, 1))], TODAY) is None


def test_group_by_event():
    grouped = group_by_event([make(event_code='A'), make(event_code='A'), make(event_code='B')])
    assert len(grouped['A']) == 2
    assert len(grouped['B']) == 1
