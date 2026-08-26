# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Reading a Progetto Formativo.

Ported from `src/lib/import/localEventExtractor.ts` and `programmaParser.ts` of
the Cyberbrain event manager, which read the provider's own documents: a header,
a handful of labelled lines, then a timetable with the speakers written under
each session.

Rules only, no model. A participant list and a training programme are short,
formulaic documents, and a rule that can be pointed at is easier to correct than
a model that answers differently on a Tuesday. Every value carries the line it
was read from, so a wrong field can be traced back.

Three rules exist because breaking them produced wrong data on real documents:

* The title is never the provider. `SUMMEET SRL` sits above the title in every
  one of these documents, and taking the first line filed the event under the
  provider's own name.
* A lone line under a session, with no role and no title, is not a person.
  `Disease Modifying Treatment` has exactly the shape of a name.
* A line in capitals is a session heading, not a speaker.

Pure functions, no Indico imports.
"""

import re
from dataclasses import dataclass, field


MONTHS = {
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
    'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12,
}
_MONTH_ALT = '|'.join(MONTHS)

#: `9 maggio 2026`, with the year optional so a range can share one.
ITALIAN_DATE_RE = re.compile(rf'\b(\d{{1,2}})\s+({_MONTH_ALT})\b(?:\s+(\d{{4}}))?', re.IGNORECASE)

#: `15/09/2026`, `15-09-2026`, `2026-09-15`
NUMERIC_DATE_RE = re.compile(r'\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})\b')

#: `dal 15 al 16 ottobre 2026`, `19 e 20 febbraio 2026`, `15-16 ottobre 2026`
DAY_RANGE_RE = re.compile(
    rf'\b(?:dal\s+)?(\d{{1,2}})\s*(?:al|e|-|\u2013)\s*(\d{{1,2}})\s+({_MONTH_ALT})\b(?:\s+(\d{{4}}))?',
    re.IGNORECASE)

TIME_RE = re.compile(r'\b([01]?\d|2[0-3])[:.]([0-5]\d)\b')

#: Lines that name the provider rather than the event
PROVIDER_RE = re.compile(
    r'\b(?:provider|s\.?r\.?l\.?|s\.?p\.?a\.?|s\.?a\.?s\.?|s\.?n\.?c\.?|societ[àa]\s+cooperativa)\b'
    r'|\bid\s*\d{2,}\b', re.IGNORECASE)

#: Headers a Progetto Formativo starts with
HEADER_RE = re.compile(r'^\s*(?:progetto|evento|percorso)\s+formativo\s*$', re.IGNORECASE)

#: Section headings, which are never the title. They cannot be spotted by being
#: in capitals: real titles are written that way too (`FOCUS GROUP ON LDL 4.0`).
SECTION_HEADINGS = frozenset({
    'programma', 'programma scientifico', 'razionale', 'razionale scientifico',
    'obiettivi', 'obiettivo formativo', 'destinatari', 'sede', 'segreteria',
    'segreteria organizzativa', 'faculty', 'responsabile scientifico', 'relatori',
    'iscrizione', 'iscrizioni', 'provider', 'crediti', 'note',
})

#: `Etichetta: valore`. Only a colon: an en dash separates a role from a
#: name (`Nefrologa - Dott.ssa Melania Trabucchi`, with an en dash), and reading that as a
#: label lost the speaker.
LABEL_RE = re.compile(r'^\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s.\'/°]{2,40}?)\s*:\s*(.*)$')

_NAME_TOKEN = r"[A-ZÀ-Ú][\w'\u2019À-ú.-]*"  # noqa: S105 — a regex, not a credential
_PARTICLE = r"(?:de(?:gli|lla|llo|lle|l|i|n|r)?|di|da|dal|del|della|van|von|ten|ter|la|lo|d')"
TITLE_RE = re.compile(r'^(?:dott\.?ssa|dott\.?|dr\.?ssa|dr\.?|prof\.?ssa|prof\.?|sig\.?ra|sig\.?)\s+',
                      re.IGNORECASE)
NAME_RE = re.compile(rf'^{_NAME_TOKEN}(?:\s+(?:{_NAME_TOKEN}|{_PARTICLE})){{1,3}}$')

#: A speaker line may put the role before the name: `Cardiologo - Mario Rossi`
ROLE_SEPARATOR_RE = re.compile(r'\s+[-\u2013—]\s+')

#: Labels that introduce a person rather than a fact
PERSON_LABELS = ('responsabile scientifico', 'responsabile', 'faculty', 'relatori', 'relatore',
                 'docenti', 'docente', 'moderatore', 'moderatori', 'presidente')

CREDIT_LABELS = ('crediti ecm', 'crediti', 'n° crediti', 'n. crediti', 'numero crediti')
PARTICIPANT_LABELS = ('numero partecipanti', 'partecipanti', 'destinatari', 'n° discenti',
                      'n. discenti', 'discenti', 'numero discenti')
VENUE_LABELS = ('sede', 'luogo', 'location')
TIME_LABELS = ('orario', 'orari')


@dataclass
class Person:
    """Someone named in the document."""

    name: str
    role: str = ''
    #: 'doctor', 'professor' or 'none', as `engagement_letter` names them
    title: str = 'none'
    source: str = ''


@dataclass
class Programme:
    """What the rules could read out of a Progetto Formativo."""

    event_name: str = ''
    start_date: object = None
    end_date: object = None
    venue: str = ''
    city: str = ''
    province: str = ''
    credits: str = ''
    participants: str = ''
    start_time: str = ''
    end_time: str = ''
    people: list = field(default_factory=list)
    #: field -> the line it was read from
    evidence: dict = field(default_factory=dict)


def _lines(text):
    return [line.rstrip() for line in (text or '').replace('\r\n', '\n').split('\n')]


def _label_of(line):
    match = LABEL_RE.match(line)
    if not match:
        return None, None
    return match.group(1).strip().casefold(), match.group(2).strip()


def is_provider_line(line):
    """Whether a line names the provider rather than the event."""
    return bool(PROVIDER_RE.search(line or ''))


def is_shouting(line):
    """A line written entirely in capitals: a session heading, not a name."""
    letters = [char for char in (line or '') if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters) and len(letters) > 3


# --- the title ---------------------------------------------------------------

#: Labels a Progetto Formativo carries. One of them is enough to tell the
#: document apart from an email, where the first line is a greeting and not a title.
PROGRAMME_LABELS = frozenset({'data', 'date', 'sede', 'luogo', 'crediti', 'crediti ecm',
                              'tipologia', 'modalità', 'modalita', 'orario', 'provider',
                              'provider ecm', 'destinatari', 'partecipanti',
                              'numero partecipanti', 'responsabile scientifico'})


def looks_like_programme(text):
    """Whether the document is one of the provider's forms rather than prose."""
    for line in _lines(text):
        if HEADER_RE.match(line):
            return True
        label, _value = _label_of(line)
        if label in PROGRAMME_LABELS:
            return True
    return False


def find_event_name(text):
    """The scientific title, and the line it came from.

    Taken from under the `PROGETTO FORMATIVO` header when there is one, skipping
    the provider. A short line right after the title is its subtitle and is
    joined with `: `, which is how these documents are written and how the
    office already files them.

    Nothing is returned for a document that is not one of these forms. Pasted
    email starts with `Buongiorno,` and reading that as the title of an event is
    worse than admitting the title was not found.
    """
    if not looks_like_programme(text):
        return '', ''
    lines = _lines(text)
    start = 0
    for index, line in enumerate(lines):
        if HEADER_RE.match(line):
            start = index + 1
            break

    for index in range(start, len(lines)):
        line = lines[index].strip()
        if not line or is_provider_line(line) or _label_of(line)[0] is not None:
            continue
        if line.casefold().strip(' .:') in SECTION_HEADINGS:
            continue
        if TIME_RE.match(line):
            # A timetable row, so the header is already behind us and the
            # document never declared a title.
            break
        title = line
        subtitle = _subtitle_after(lines, index)
        full = f'{title}: {subtitle}' if subtitle else title
        return full, line
    return '', ''


def _subtitle_after(lines, index):
    """The line under the title, when it is a subtitle and not something else."""
    for candidate in lines[index + 1:index + 2]:
        text = candidate.strip()
        if (not text or is_provider_line(text) or _label_of(text)[0] is not None
                or HEADER_RE.match(text) or is_shouting(text) or TIME_RE.match(text)
                or text.casefold().strip(' .:') in SECTION_HEADINGS):
            return ''
        # A subtitle is a phrase, not a paragraph.
        if len(text) > 120:
            return ''
        return text
    return ''


# --- dates -------------------------------------------------------------------

def _make_date(day, month, year):
    from datetime import date
    try:
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def find_dates(text):
    """The first and last day of the event, and the line they came from.

    Ranges are recognised in the three forms these documents use: `dal 15 al 16
    ottobre`, `19 e 20 febbraio`, and `15-16 ottobre`.
    """
    for line in _lines(text):
        match = DAY_RANGE_RE.search(line)
        if not match:
            continue
        first, last, month, year = match.groups()
        year = year or _year_near(text)
        start, end = _make_date(first, MONTHS[month.lower()], year), _make_date(last, MONTHS[month.lower()], year)
        if start:
            return start, (end if end and end != start else None), line.strip()

    for line in _lines(text):
        match = ITALIAN_DATE_RE.search(line)
        if not match:
            continue
        day, month, year = match.groups()
        value = _make_date(day, MONTHS[month.lower()], year or _year_near(text))
        if value:
            return value, None, line.strip()

    numeric = []
    source = ''
    for line in _lines(text):
        found = NUMERIC_DATE_RE.findall(line)
        for raw in found:
            value = _parse_numeric(raw)
            if value and value not in numeric:
                numeric.append(value)
                source = source or line.strip()
    if numeric:
        numeric.sort()
        return numeric[0], (numeric[-1] if len(numeric) > 1 else None), source
    return None, None, ''


def _year_near(text):
    match = re.search(r'\b(20\d{2})\b', text or '')
    return match.group(1) if match else None


def _parse_numeric(raw):
    from datetime import date
    raw = raw.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', raw):
        year, month, day = raw.split('-')
    else:
        day, month, year = re.split(r'[/.-]', raw)
        if len(year) == 2:
            year = f'20{year}'
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


# --- venue, credits, participants, times -------------------------------------

#: `04100 - Latina (LT)` or `Latina (LT)` at the end of an address
CITY_WITH_CAP_RE = re.compile(
    r'\b\d{5}\s*[-\u2013]?\s*([A-ZÀ-Ú][\w\'\u2019À-ú.-]*(?:\s+[A-ZÀ-Ú][\w\'\u2019À-ú.-]*)?)')
PROVINCE_RE = re.compile(r'\(([A-Z]{2})\)')


def find_venue(text):
    """The venue, its city and its province, from the `Sede` line.

    The city is read from the postcode when there is one, and otherwise from the
    tail of the address: these documents write both forms.
    """
    for line in _lines(text):
        label, value = _label_of(line)
        if label not in VENUE_LABELS or not value:
            continue
        province = ''
        match = PROVINCE_RE.search(value)
        if match:
            province = match.group(1)
        cleaned = PROVINCE_RE.sub('', value).strip(' ,-')
        city = ''
        with_cap = CITY_WITH_CAP_RE.search(cleaned)
        if with_cap:
            city = with_cap.group(1).strip()
            venue = cleaned[:with_cap.start()].strip(' ,-')
        else:
            parts = [part.strip() for part in cleaned.split(',') if part.strip()]
            venue = parts[0] if parts else cleaned
            city = parts[-1].strip() if len(parts) > 1 else ''
        return venue, city, province, line.strip()
    return '', '', '', ''


def _labelled_number(text, labels):
    """The first number written on a line carrying one of these labels."""
    for line in _lines(text):
        label, value = _label_of(line)
        if label in labels and value:
            numbers = re.findall(r'\d+', value)
            if numbers:
                # "1 Coordinator + 4 Expert Opinion" is five people, not one.
                total = sum(int(number) for number in numbers) if '+' in value else int(numbers[0])
                return str(total), line.strip()
    return '', ''


def find_credits(text):
    return _labelled_number(text, CREDIT_LABELS)


def find_participants(text):
    return _labelled_number(text, PARTICIPANT_LABELS)


def find_times(text):
    """The first and last time of the day.

    Taken from the declared `Orario` line when there is one, and otherwise from
    the timetable itself — first entry to last, registration and closing
    included, because that is the span the office writes down.
    """
    for line in _lines(text):
        label, value = _label_of(line)
        if label in TIME_LABELS and value:
            times = [f'{hour.zfill(2)}:{minute}' for hour, minute in TIME_RE.findall(value)]
            if times:
                return times[0], (times[-1] if len(times) > 1 else ''), line.strip()

    times = []
    for line in _lines(text):
        match = TIME_RE.match(line.strip())
        if match:
            times.append(f'{match.group(1).zfill(2)}:{match.group(2)}')
    if times:
        return times[0], (times[-1] if len(times) > 1 else ''), ''
    return '', '', ''


# --- the people --------------------------------------------------------------

def _split_title(raw):
    match = TITLE_RE.match(raw or '')
    if not match:
        return raw.strip(), 'none'
    written = match.group(0).strip().casefold()
    title = 'professor' if written.startswith('prof') else ('doctor' if written.startswith(('dott', 'dr')) else 'none')
    return raw[match.end():].strip(), title


def _person_from(raw, *, role='', source=''):
    name, title = _split_title(raw)
    name = name.strip(' ,;')
    if not name or is_shouting(name) or not NAME_RE.match(name):
        return None
    return Person(name=name, role=role, title=title, source=source)


def find_people(text):
    """Everyone the document names, from the labelled lines and the timetable.

    A line under a session is only read as a person when it says so: a role
    before a dash, an academic title, or two names separated by a comma. A lone
    line with none of those is a module title, not somebody's name.
    """
    people = []
    seen = set()

    def add(person):
        if person and person.name.casefold() not in seen:
            seen.add(person.name.casefold())
            people.append(person)

    for line in _lines(text):
        stripped = line.strip()
        if not stripped:
            continue

        label, value = _label_of(stripped)
        if label is not None:
            if any(label.startswith(known) for known in PERSON_LABELS) and value:
                # `Ottavia Vermiglio, Pordenone` — the name, then where they work.
                add(_person_from(value.split(',')[0], role=label.title(), source=stripped))
            continue

        if TIME_RE.match(stripped):
            # A timetable row: the title of the session, not a name.
            continue
        if is_shouting(stripped):
            continue

        role, _matched, remainder = _split_role(stripped)
        if role:
            add(_person_from(remainder, role=role, source=stripped))
            continue

        if TITLE_RE.match(stripped):
            add(_person_from(stripped, source=stripped))
            continue

        if ',' in stripped:
            candidates = [part.strip() for part in stripped.split(',') if part.strip()]
            found = [_person_from(candidate, source=stripped) for candidate in candidates]
            if len(found) >= 2 and all(found):
                for person in found:
                    add(person)
    return people


def _split_role(line):
    """`Cardiologo - Mario Rossi` becomes `('Cardiologo', '-', 'Mario Rossi')`."""
    match = ROLE_SEPARATOR_RE.search(line)
    if not match:
        return '', '', line
    role = line[:match.start()].strip()
    remainder = line[match.end():].strip()
    if not role or is_shouting(role) or len(role.split()) > 3:
        return '', '', line
    return role, match.group(0).strip(), remainder


# --- everything together ------------------------------------------------------

def read(text):
    """Read a Progetto Formativo into the fields the platform files it under."""
    result = Programme()

    name, source = find_event_name(text)
    if name:
        result.event_name, result.evidence['event_name'] = name, source

    start, end, source = find_dates(text)
    if start:
        result.start_date, result.end_date = start, end
        result.evidence['event_date'] = source

    venue, city, province, source = find_venue(text)
    if venue or city:
        result.venue, result.city, result.province = venue, city, province
        result.evidence['venue'] = source

    result.credits, source = find_credits(text)
    if result.credits:
        result.evidence['credits'] = source

    result.participants, source = find_participants(text)
    if result.participants:
        result.evidence['participants'] = source

    result.start_time, result.end_time, source = find_times(text)
    if result.start_time and source:
        result.evidence['times'] = source

    result.people = find_people(text)
    return result
