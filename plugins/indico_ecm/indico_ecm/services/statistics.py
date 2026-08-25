# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""What a provider counts at the end of a year.

Ported from `src/lib/menu/report-menu-actions.ts` of the Cyberbrain event
manager: the same figures, over the platform's own records instead of a
spreadsheet — how many events, how many participants, how many credits, how
far the preparation got, and where the deadlines pile up.

Pure functions over plain records, so they can be counted without a database.
The caller builds the records; nothing here knows about Indico.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class EventRecord:
    """One accredited event, reduced to what gets counted."""

    id: int
    title: str
    #: None for an event with no date yet: it is counted, but not by month
    day: date | None = None
    city: str = ''
    credits: float = 0.0
    participants: int = 0
    #: Share of the checklist that is done, 0..1, from `deliverables.readiness`
    readiness: float = 0.0
    #: How many checklist entries are late or missed
    late: int = 0
    certificates: int = 0


@dataclass(frozen=True)
class Totals:
    events: int = 0
    participants: int = 0
    credits: float = 0.0
    certificates: int = 0
    #: Average share of the checklist that is done, as a percentage
    completion_rate: int = 0
    #: Events with at least one entry late or missed
    at_risk: int = 0


@dataclass(frozen=True)
class Bucket:
    """A group of events — a city, a month — and what it is worth."""

    key: str
    events: int = 0
    participants: int = 0
    credits: float = 0.0
    completion_rate: int = 0
    #: Share of all events, as a percentage
    share: int = 0


@dataclass
class Report:
    totals: Totals = field(default_factory=Totals)
    by_city: list = field(default_factory=list)
    by_month: list = field(default_factory=list)
    at_risk: list = field(default_factory=list)


MONTHS_IT = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
             'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')


def _percent(part, whole):
    return round(part / whole * 100) if whole else 0


def totals(events):
    """The headline figures.

    `completion_rate` is the average of the per-event readiness, not the share
    of finished events: an office wants to know how far along everything is,
    not how many are already closed.
    """
    events = list(events)
    if not events:
        return Totals()
    return Totals(
        events=len(events),
        participants=sum(event.participants for event in events),
        credits=round(sum(event.credits for event in events), 2),
        certificates=sum(event.certificates for event in events),
        completion_rate=_percent(sum(event.readiness for event in events), len(events)),
        at_risk=sum(1 for event in events if event.late),
    )


def _bucket(events, key_of, *, label_of=None, total_events=0):
    grouped = defaultdict(list)
    for event in events:
        key = key_of(event)
        if key is None:
            continue
        grouped[key].append(event)
    buckets = []
    for key, group in grouped.items():
        buckets.append(Bucket(
            key=(label_of(key) if label_of else str(key)),
            events=len(group),
            participants=sum(event.participants for event in group),
            credits=round(sum(event.credits for event in group), 2),
            completion_rate=_percent(sum(event.readiness for event in group), len(group)),
            share=_percent(len(group), total_events),
        ))
    return buckets


def by_city(events):
    """Events grouped by city, busiest first. Events with no city are left out."""
    events = list(events)
    buckets = _bucket(events, lambda event: (event.city or '').strip() or None,
                      total_events=len(events))
    return sorted(buckets, key=lambda bucket: (-bucket.events, bucket.key))


def by_month(events):
    """Events grouped by month, in calendar order. Undated events are left out."""
    events = list(events)
    buckets = _bucket(
        events,
        lambda event: (event.day.year, event.day.month) if event.day else None,
        label_of=lambda key: f'{MONTHS_IT[key[1] - 1]} {key[0]}',
        total_events=len(events))
    order = {f'{MONTHS_IT[month - 1]} {year}': (year, month)
             for year in {event.day.year for event in events if event.day}
             for month in range(1, 13)}
    return sorted(buckets, key=lambda bucket: order.get(bucket.key, (0, 0)))


def at_risk(events):
    """Events with something late, the worst first.

    This is the list the original dashboard existed for: a future event with a
    checklist entry still open is the one to call about.
    """
    return sorted((event for event in events if event.late),
                  key=lambda event: (-event.late, event.day or date.max))


def build(events):
    """Everything the report page shows."""
    events = list(events)
    return Report(totals=totals(events), by_city=by_city(events), by_month=by_month(events),
                  at_risk=at_risk(events))


def as_rows(report):
    """The report as rows of a spreadsheet, ready to be written out."""
    rows = [('Totali', '', '', '', ''),
            ('Eventi', report.totals.events, '', '', ''),
            ('Partecipanti', report.totals.participants, '', '', ''),
            ('Crediti', report.totals.credits, '', '', ''),
            ('Attestati', report.totals.certificates, '', '', ''),
            ('Completamento medio %', report.totals.completion_rate, '', '', ''),
            ('Eventi con voci in ritardo', report.totals.at_risk, '', '', ''),
            ('', '', '', '', '')]

    rows.append(('Per città', 'Eventi', 'Partecipanti', 'Crediti', 'Completamento %'))
    rows.extend((bucket.key, bucket.events, bucket.participants, bucket.credits,
                 bucket.completion_rate) for bucket in report.by_city)
    rows.append(('', '', '', '', ''))

    rows.append(('Per mese', 'Eventi', 'Partecipanti', 'Crediti', 'Completamento %'))
    rows.extend((bucket.key, bucket.events, bucket.participants, bucket.credits,
                 bucket.completion_rate) for bucket in report.by_month)
    rows.append(('', '', '', '', ''))

    rows.append(('In ritardo', 'Voci in ritardo', 'Data', 'Città', ''))
    rows.extend((event.title, event.late, event.day.strftime('%d/%m/%Y') if event.day else '',
                 event.city, '') for event in report.at_risk)
    return rows


def as_xlsx(report, *, sheet_name='Report ECM'):
    """The same rows as a real spreadsheet, the way the office files them."""
    import io

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    for row in as_rows(report):
        sheet.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
