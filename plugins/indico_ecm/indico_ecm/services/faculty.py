# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The speakers of an event, and the two documents they receive.

The faculty itself is Indico's: `event.person_links` already holds the people,
their titles and their addresses, so nothing here duplicates them. What the
provider adds on top is what the ECM paperwork needs and Indico has no place
for — a role, a fee, a letter number — and those are answered on the page and
used straight away, without a table of their own.

The wording of both documents comes from the Cyberbrain event manager and is
reproduced there (`services/engagement_letter.py` for the figures,
`services/templates.py` for the email).
"""

import io
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from indico_ecm.services import engagement_letter
from indico_ecm.services.documents import missing_placeholders, render_docx
from indico_ecm.services.naming import sanitize_filename


TEMPLATE_PATH = Path(__file__).parent.parent / 'templates' / 'letters' / 'lettera_incarico.docx'


@dataclass(frozen=True)
class Speaker:
    """One member of the faculty, as the letter needs them."""

    person_id: int
    full_name: str
    email: str = ''
    #: 'M', 'F' or empty when nothing in the record establishes it
    gender: str = ''
    #: 'doctor', 'professor' or 'none'
    title: str = 'none'
    role: str = 'Relatore'
    fee: str = ''
    tax_code: str = ''
    birth_date: str = ''
    letter_number: str = ''
    has_vat_number: bool = False


def read_faculty(event):
    """The event's people, with the title and gender their record already shows.

    Indico stores the title separately from the name, so the name is only parsed
    when there is no title on the record. A gender is taken from the tax code
    when one is known, and otherwise only from an explicitly declined title —
    never guessed from a first name.
    """
    people = []
    declines = declines_titles_in(event)
    for link in event.person_links:
        raw_title = (link.title or '').strip()
        name = link.full_name
        title, gender = 'none', ''
        if raw_title:
            _name, title, gender = engagement_letter.split_title(f'{raw_title} {name}')
        else:
            name, title, gender = engagement_letter.split_title(name)
        people.append(Speaker(
            person_id=link.person_id,
            full_name=name,
            email=link.email or '',
            gender=engagement_letter.gender_from_title(title, gender, declines),
            title=title,
        ))
    return people


def declines_titles_in(event):
    """Whether this event's own records decline titles anywhere.

    Read from the people of this event only: `Dott.` in a list that also writes
    `Dott.ssa` is a masculine, and in a list that never does it means nothing.
    """
    written = ' '.join(f'{link.title or ""} {link.full_name}' for link in event.person_links)
    return engagement_letter.declines_titles(written)


def resolve_gender(speaker):
    """The gender to write the letter with, best evidence first."""
    from_code = engagement_letter.gender_from_tax_code(speaker.tax_code)
    return from_code or speaker.gender


def letter_context(speaker, *, event, letter_day=None, activity_code='', project_title='',
                   project_code='', format_label=''):
    """Everything the `.docx` placeholders need for one speaker."""
    start = event.start_dt.strftime('%d/%m/%Y') if event.start_dt else ''
    end = event.end_dt.strftime('%d/%m/%Y') if event.end_dt else ''
    figures = engagement_letter.derive(
        gender=resolve_gender(speaker),
        title=speaker.title,
        fee=speaker.fee,
        letter_day=letter_day or date.today(),
        event_date=start,
    )
    return {
        'saluto': figures.salutation,
        'cognome_nome': speaker.full_name,
        'data_nascita': speaker.birth_date,
        'email': speaker.email,
        'ruolo': speaker.role,
        'evento_ecm': event.title,
        'titolo_progetto': project_title or event.title,
        'codice_progetto': project_code,
        'codice_evento': activity_code,
        'numero_incarico': speaker.letter_number,
        'data_evento': start,
        'data_fine_evento': end,
        'modalita': format_label,
        'anno': figures.year,
        'compenso': figures.fee,
        'compenso_lettere': figures.fee_in_words,
        'ritenuta_acconto': figures.withholding,
        'totale_netto': figures.net_total,
        'nota_piva': _vat_note(speaker, figures),
    }


def _vat_note(speaker, figures):
    """The line about the 20% withholding, present only when there is a fee."""
    if not figures.has_fee:
        return ''
    if speaker.has_vat_number:
        return (f'Importo soggetto a ritenuta d\u2019acconto del 20% '
                f'(€ {figures.withholding}), netto € {figures.net_total}.')
    return f'Compenso lordo € {figures.fee}.'


def letter_filename(speaker):
    """Named the way the office files them: `Lettera di incarico Rossi Mario.docx`."""
    name = sanitize_filename(speaker.full_name) or f'relatore-{speaker.person_id}'
    return f'Lettera di incarico {name}.docx'


def render_letter(speaker, *, event, template_path=TEMPLATE_PATH, **context_args):
    """Render one engagement letter, returning `(filename, docx_bytes)`."""
    context = letter_context(speaker, event=event, **context_args)
    return letter_filename(speaker), render_docx(template_path, context)


def render_batch(speakers, *, event, template_path=TEMPLATE_PATH, **context_args):
    """Render every engagement letter of an event into one archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for speaker in speakers:
            filename, content = render_letter(speaker, event=event, template_path=template_path,
                                              **context_args)
            archive.writestr(filename, content)
    return len(speakers), buffer.getvalue()


def check_template(speakers, *, event, template_path=TEMPLATE_PATH, **context_args):
    """Placeholders the template needs and the answers do not provide."""
    if not speakers:
        return []
    context = letter_context(speakers[0], event=event, **context_args)
    return missing_placeholders(template_path, context)
