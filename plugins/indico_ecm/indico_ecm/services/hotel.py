# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""What the hotel has to prepare, read from the programme.

Ported from `src/lib/import/hotelServices.ts` of the Cyberbrain event manager,
including its keyword list. The programme says what happens during the day —
a coffee break, a lunch, a round table — and the hotel brief is a restatement
of that, so it is deduced rather than typed twice.

Keyword matching only, no model: the original says so in its own header, and a
list of words a person can read and correct is what an office wants when the
hotel prepared the wrong room.

Pure functions, no Indico imports.
"""

import json
import re
from dataclasses import asdict, dataclass


#: How the room is laid out
LAYOUT_THEATRE = 'Platea'
LAYOUT_U_SHAPE = 'Tavolo a U'
LAYOUT_ROUND_TABLES = 'Tavoli riuniti'

LAYOUTS = (LAYOUT_THEATRE, LAYOUT_U_SHAPE, LAYOUT_ROUND_TABLES)

_COFFEE = re.compile(r'coffee\s*break|pausa\s*caff', re.IGNORECASE)
_LUNCH = re.compile(r'\blunch\b|pranzo|buffet|light\s*lunch', re.IGNORECASE)
_APERITIF = re.compile(r'aperitivo|apericena|brindisi|cocktail\s*di\s*chiusura', re.IGNORECASE)
_DESK = re.compile(r'registrazione|accredito|check[\s-]?in|segreteria|iscrizione', re.IGNORECASE)
_TECHNICAL = re.compile(r'assistenza\s*tecnica|tecnico\s*presente|supporto\s*tecnico', re.IGNORECASE)
#: A round table or an interactive discussion needs tables, not rows of chairs
_ROUND_TABLES = re.compile(
    r'tavola\s*rotonda|discussione\s*interattiva|gruppo\s*di\s*discussion|\bgdm\b|grand\s*round',
    re.IGNORECASE)


@dataclass(frozen=True)
class HotelServices:
    """The checklist the hotel receives."""

    layout: str = LAYOUT_THEATRE
    coffee_break: bool = False
    lunch: bool = False
    aperitif: bool = False
    registration_desk: bool = False
    technical_support: bool = False
    start_time: str = ''
    end_time: str = ''

    @property
    def catering(self):
        """Whether anything is served at all."""
        return self.coffee_break or self.lunch or self.aperitif


def deduce(text, *, start_time='', end_time=''):
    """Read the services out of the programme.

    The layout stays `Platea` unless the programme says something that needs
    tables: sitting people in rows for a round table is the mistake this exists
    to avoid.
    """
    text = text or ''
    return HotelServices(
        layout=LAYOUT_ROUND_TABLES if _ROUND_TABLES.search(text) else LAYOUT_THEATRE,
        coffee_break=bool(_COFFEE.search(text)),
        lunch=bool(_LUNCH.search(text)),
        aperitif=bool(_APERITIF.search(text)),
        registration_desk=bool(_DESK.search(text)),
        technical_support=bool(_TECHNICAL.search(text)),
        start_time=start_time,
        end_time=end_time,
    )


def dumps(services: HotelServices):
    """Serialize for the operations record, which keeps it as text."""
    return json.dumps(asdict(services), ensure_ascii=False, sort_keys=True)


def loads(raw):
    """Read it back, tolerating anything: an unreadable value is not a crash."""
    if not raw:
        return HotelServices()
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return HotelServices()
    if not isinstance(data, dict):
        return HotelServices()
    known = {field: data[field] for field in HotelServices.__dataclass_fields__ if field in data}
    try:
        return HotelServices(**known)
    except TypeError:
        return HotelServices()


#: What each service is called in the brief, in the order the hotel reads them
LABELS = (
    ('registration_desk', 'Desk segreteria per registrazione partecipanti'),
    ('coffee_break', 'Coffee break'),
    ('lunch', 'Pranzo'),
    ('aperitif', 'Aperitivo di chiusura'),
    ('technical_support', 'Assistenza tecnica per tutta la durata'),
)


def brief_lines(services: HotelServices):
    """The requested services, one line each, for the email to the hotel."""
    lines = [f'Allestimento sala: {services.layout}']
    if services.start_time or services.end_time:
        lines.append(f'Orario: {services.start_time} - {services.end_time}'.strip(' -'))
    lines.extend(label for field, label in LABELS if getattr(services, field))
    return lines
