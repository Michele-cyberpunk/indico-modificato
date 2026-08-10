# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The accreditation request email.

Ported from `js/views/events.js` of the Cyberbrain event manager. The wording is
reproduced exactly: this message goes to the accreditation office (UECM) and
its format is what they expect to read, so it is treated as a fixed template
rather than something to improve.

The function builds text. It does not send: sending is an approved action in the
agent layer, and a person remains in the loop.

Pure, no Indico imports.
"""

import html
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import quote

from indico_ecm.services.naming import folder_path


DEFAULT_RECIPIENT_LABEL = 'ECM'


@dataclass(frozen=True)
class AccreditationRequest:
    event_name: str
    event_date: date | None = None
    end_date: date | None = None
    place: str = ''
    sponsor: str = ''
    event_code: str = ''
    folder_name: str = ''
    #: How the accreditation office is addressed in the greeting
    recipient_label: str = DEFAULT_RECIPIENT_LABEL
    recipient_email: str = ''
    cc: tuple = ()
    sender_name: str = ''
    subject_override: str = ''
    extra: dict = field(default_factory=dict)


def format_date_it(value):
    """Italian short date, as produced by `toLocaleDateString('it-IT')`."""
    if not isinstance(value, date):
        return ''
    return f'{value.day}/{value.month}/{value.year}'


def build_subject(request: AccreditationRequest):
    if request.subject_override:
        return request.subject_override
    return f'Accreditamento ECM: {request.event_name or ""}'


def build_body(request: AccreditationRequest, *, escape=True):
    """Build the HTML body of the request.

    Every interpolated value is escaped by default: these fields come from user
    input and end up in an HTML email.
    """
    def out(value):
        text = str(value or '')
        return html.escape(text) if escape else text

    year = (request.event_date or date.today()).year
    path = folder_path(year, request.folder_name or '')
    return (
        f'Ciao {out(request.recipient_label or DEFAULT_RECIPIENT_LABEL)},<br><br>'
        f"Ti chiedo l'accreditamento per favore del seguente evento:<br>"
        f'Nome Evento: <b>{out(request.event_name)}</b><br>'
        f'Data: {out(format_date_it(request.event_date))}<br>'
        f'Luogo: {out(request.place)}<br>'
        f'Cliente (Sponsor): {out(request.sponsor)}<br>'
        f'Codice Evento: {out(request.event_code)}<br><br>'
        f'Trovi la cartella in: {out(path)}<br><br>'
        f'Grazie mille, {out(request.sender_name)}.'
    )


def build_email(request: AccreditationRequest):
    """Subject, body and recipients, ready for review before sending."""
    return {
        'to': request.recipient_email,
        'cc': list(request.cc),
        'subject': build_subject(request),
        'body': build_body(request),
    }


def outlook_compose_url(request: AccreditationRequest):
    """Deep link that opens the message already filled in, in Outlook Web.

    Kept because it is how the office works today: the platform prepares the
    message, a person reads it and presses send in their own mailbox.
    """
    email = build_email(request)
    params = (
        f'to={quote(email["to"])}'
        f'&subject={quote(email["subject"])}'
        f'&body={quote(email["body"])}'
        f'&cc={quote(",".join(email["cc"]))}'
    )
    return f'https://outlook.live.com/owa/?path=/mail/action/compose&{params}'


def missing_fields(request: AccreditationRequest):
    """What still has to be filled in before the request can go out."""
    required = {
        'event_name': request.event_name,
        'event_date': request.event_date,
        'place': request.place,
        'sponsor': request.sponsor,
        'folder_name': request.folder_name,
        'recipient_email': request.recipient_email,
    }
    return [name for name, value in required.items() if not value]
