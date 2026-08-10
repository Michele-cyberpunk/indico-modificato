# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Folder and file naming conventions of the provider.

Ported verbatim from `js/core/utils.js` of the Cyberbrain event manager. The
convention is not cosmetic: the folder name is what the accreditation request
email points at (`S:\\CONGRESSI <anno>\\<nome cartella>`), so changing it would
break the link between the platform and the shared drive people actually use.

Pure functions, no Indico imports.
"""

import re
from datetime import date


#: Multi-sponsor events are filed under one conventional name
MULTI_SPONSOR_MARKERS = ('MULTI', 'PLURI')
MULTI_SPONSOR_NAME = 'PLURISPONSOR'

#: Event types filed by format instead of by city
REMOTE_TYPE_MARKERS = ('WEB', 'FAD')


def sanitize_part(part):
    """Collapse whitespace, slashes and underscores into single hyphens."""
    if part is None:
        return ''
    return re.sub(r'[\s/_]+', '-', str(part).strip())


def generate_folder_name(*, start_date=None, end_date=None, event_name='', event_type='', city='',
                         sponsor='', event_code='', note=''):
    """Build the shared-drive folder name of an event.

    Order and rules are the ones already in use:
    `MMDD[-DD] NOME TIPO|CITTÀ SPONSOR CODICE NOTE`, joined by spaces, with the
    first word of the event name uppercased and remote events filed by format
    rather than by city.
    """
    parts = []
    if isinstance(start_date, date):
        date_part = f'{start_date.month:02d}{start_date.day:02d}'
        if isinstance(end_date, date) and end_date != start_date:
            date_part += f'-{end_date.day:02d}'
        parts.append(date_part)
    if event_name:
        parts.append(sanitize_part(event_name.split(' ')[0]).upper())
    type_upper = (event_type or '').upper()
    if any(marker in type_upper for marker in REMOTE_TYPE_MARKERS):
        parts.append(sanitize_part(type_upper))
    elif city:
        parts.append(sanitize_part(city.upper()))
    if sponsor:
        sponsor_part = sanitize_part(sponsor.upper())
        if any(marker in sponsor_part for marker in MULTI_SPONSOR_MARKERS):
            sponsor_part = MULTI_SPONSOR_NAME
        parts.append(sponsor_part)
    if event_code:
        parts.append(sanitize_part(event_code))
    if note:
        parts.append(sanitize_part(note))
    return ' '.join(parts)


def sanitize_filename(name):
    """Make a string safe to use as a file name on Windows shares."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', str(name or ''))
    return re.sub(r'\s+', ' ', cleaned).strip()


def folder_path(year, folder_name, *, root='S:\\CONGRESSI'):
    """The full path as written in the accreditation request email."""
    return f'{root} {year}\\{folder_name}'
