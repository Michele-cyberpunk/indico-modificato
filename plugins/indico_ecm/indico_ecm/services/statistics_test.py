# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import date

import pytest

from indico_ecm.services.statistics import EventRecord, as_rows, at_risk, build, by_city, by_month, totals


@pytest.fixture
def events():
    return [
        EventRecord(1, 'Cardio Update', date(2026, 3, 10), 'Milano', credits=9, participants=80,
                    readiness=1.0, certificates=72),
        EventRecord(2, 'Nefro Meeting', date(2026, 3, 24), 'Milano', credits=6, participants=50,
                    readiness=0.5, late=2, certificates=0),
        EventRecord(3, 'Onco Forum', date(2026, 5, 9), 'Roma', credits=4, participants=30,
                    readiness=0.25, late=5),
        EventRecord(4, 'Senza data', None, '', credits=3, participants=10, readiness=0.0, late=1),
    ]


def test_the_headline_figures(events):
    result = totals(events)
    assert result.events == 4
    assert result.participants == 170
    assert result.credits == 22
    assert result.certificates == 72
    assert result.at_risk == 3


def test_the_completion_rate_is_the_average_progress_not_the_share_of_finished(events):
    # (1.0 + 0.5 + 0.25 + 0.0) / 4 = 43.75% -> 44, not 25% (one event of four done)
    assert totals(events).completion_rate == 44


def test_no_events_counts_to_zero_and_does_not_divide():
    result = totals([])
    assert (result.events, result.participants, result.completion_rate) == (0, 0, 0)


def test_events_grouped_by_city_busiest_first(events):
    cities = by_city(events)
    assert [bucket.key for bucket in cities] == ['Milano', 'Roma']
    assert cities[0].events == 2
    assert cities[0].participants == 130
    # Four events in total, two of them in Milan.
    assert cities[0].share == 50


def test_an_event_without_a_city_is_not_a_city(events):
    assert '' not in [bucket.key for bucket in by_city(events)]


def test_events_grouped_by_month_in_calendar_order(events):
    months = by_month(events)
    assert [bucket.key for bucket in months] == ['marzo 2026', 'maggio 2026']
    assert months[0].events == 2
    assert months[0].credits == 15


def test_an_event_without_a_date_is_counted_but_not_in_a_month(events):
    assert sum(bucket.events for bucket in by_month(events)) == 3
    assert totals(events).events == 4


def test_the_events_to_call_about_come_first(events):
    late = at_risk(events)
    assert [event.title for event in late] == ['Onco Forum', 'Nefro Meeting', 'Senza data']
    assert all(event.late for event in late)


def test_an_event_with_nothing_late_is_not_at_risk(events):
    assert 'Cardio Update' not in [event.title for event in at_risk(events)]


def test_the_report_carries_every_section(events):
    report = build(events)
    assert report.totals.events == 4
    assert report.by_city and report.by_month and report.at_risk


def test_the_spreadsheet_rows_are_labelled(events):
    rows = as_rows(build(events))
    labels = [row[0] for row in rows]
    for expected in ('Totali', 'Eventi', 'Per città', 'Per mese', 'In ritardo'):
        assert expected in labels
    assert all(len(row) == 5 for row in rows)
