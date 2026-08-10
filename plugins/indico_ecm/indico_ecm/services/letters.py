# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Invitation and assignment letters.

Ported from `js/views/stampaUnione.js` of the Cyberbrain event manager, which
produces the "Lettera invito" mail merge sent to hospitals. The wording rules
are reproduced exactly, including the pluralization function: these letters go
to physicians and to sponsors, and the provider's own template is the authority
on how they read.

Pure functions, no Indico imports.
"""

from dataclasses import dataclass, field


#: Words ending in these letters take an -i plural in the roles actually used
PLURALIZABLE_ENDINGS = ('o', 'e')


def pluralize_role(role, count):
    """Pluralize an Italian role for a number of people.

    Same rule as the original: each word longer than one character ending in
    `o` or `e` becomes `-i`; anything else is left alone. It is deliberately
    naive — it matches the roles this provider actually writes ("relatore" →
    "relatori", "moderatore" → "moderatori") and does not try to be a general
    Italian pluralizer.
    """
    role = (role or '').strip()
    if count <= 1 or not role:
        return role
    words = []
    for word in role.split(' '):
        if len(word) > 1 and word[-1].lower() in PLURALIZABLE_ENDINGS:
            words.append(word[:-1] + 'i')
        else:
            words.append(word)
    return ' '.join(words)


def agreement_terms(count):
    """The agreeing words the letter template needs for a number of physicians."""
    plural = count > 1
    return {
        'medico': 'medici' if plural else 'medico',
        'chirurgo': 'chirurghi' if plural else 'chirurgo',
        'specializzato': 'specializzati' if plural else 'specializzato',
        'invitato': 'invitati' if plural else 'invitato',
        'appartenente': 'i' if plural else 'o',
    }


@dataclass(frozen=True)
class InvitationRow:
    """One row of the mail merge: a hospital and the physicians invited from it."""

    hospital: str
    physician_count: int
    role: str = ''
    department: str = ''
    event_name: str = ''
    event_place: str = ''
    date_text: str = ''
    recipient: str = ''
    notes: str = ''
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.physician_count < 1:
            raise ValueError('an invitation must concern at least one physician')


def invitation_filename(row: InvitationRow, *, extension='pdf'):
    """The file name of a generated invitation letter.

    Kept identical to the existing one, because these files are archived on the
    shared drive and searched by name:
    `Lettera invito - 3 MEDICI - Ospedale X - Evento Y - Roma.pdf`
    """
    suffix = 'MEDICI' if row.physician_count > 1 else 'MEDICO'
    return (f'Lettera invito - {row.physician_count} {suffix} - {row.hospital} - '
            f'{row.event_name} - {row.event_place}.{extension}')


def letter_context(row: InvitationRow, *, user_name=''):
    """Placeholders for the .docx template of the invitation letter."""
    terms = agreement_terms(row.physician_count)
    department_phrase = ''
    if row.department:
        department_phrase = f'del reparto di {row.department} '
    return {
        'destinatario': row.recipient or row.hospital,
        'nomeOspedale': row.hospital,
        'numeroMedici': row.physician_count,
        'ruolo': pluralize_role(row.role, row.physician_count),
        'nomeEvento': row.event_name,
        'luogoEvento': row.event_place,
        'dataEvento': row.date_text,
        'fraseRepartoOspedale': f'{department_phrase}{row.hospital}'.strip(),
        'altreNote': row.notes,
        'userName': user_name,
        **{f'termine_{key}': value for key, value in terms.items()},
    }
