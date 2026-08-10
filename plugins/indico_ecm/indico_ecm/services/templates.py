# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The template system.

Every message and document the provider sends has a fixed shape that people on
the other side recognise: the accreditation office, the hospitals, the
designer, the hotel. The legacy application had those shapes scattered across
views; here they are one registry, versioned, with the placeholders declared.

Two rules that come from the way the office works and are enforced here:

- a template declares its placeholders, and rendering with a missing one fails
  loudly rather than sending `undefined` to a hospital;
- rendering never sends. It returns subject and body for a person, or for the
  approval queue, to look at.

Pure, no Indico imports.
"""

import html
from dataclasses import dataclass, field
from string import Formatter


class TemplateError(Exception):
    pass


@dataclass(frozen=True)
class MessageTemplate:
    name: str
    subject: str
    body: str
    #: Placeholders that must be present in the context
    required: tuple = ()
    #: Placeholders that may be missing, with their default
    defaults: dict = field(default_factory=dict)
    #: Bumped whenever the wording changes, and recorded on what was sent
    version: str = '1'
    description: str = ''
    #: Whether the body is HTML (and therefore needs its values escaped)
    html_body: bool = True


def placeholders(text):
    """The placeholder names used in a template string."""
    return tuple(sorted({name for _, name, _, _ in Formatter().parse(text) if name}))


def render(template: MessageTemplate, context, *, escape=None):
    """Render a template into a subject and a body.

    Values are HTML-escaped for HTML bodies, because these fields come from
    forms and spreadsheets and end up in mail clients.
    """
    escape = template.html_body if escape is None else escape
    values = dict(template.defaults) | {key: value for key, value in context.items() if value is not None}
    missing = [name for name in template.required if not values.get(name)]
    if missing:
        raise TemplateError(f'template {template.name}: valori mancanti {", ".join(sorted(missing))}')

    needed = set(placeholders(template.subject)) | set(placeholders(template.body))
    unknown = needed - values.keys()
    if unknown:
        raise TemplateError(f'template {template.name}: segnaposto senza valore {", ".join(sorted(unknown))}')

    safe = {key: (html.escape(str(value)) if escape else str(value)) for key, value in values.items()}
    return {
        'template': template.name,
        'version': template.version,
        'subject': template.subject.format(**{key: str(value) for key, value in values.items()}),
        'body': template.body.format(**safe),
    }


ACCREDITATION_REQUEST = MessageTemplate(
    name='accreditation_request',
    description="Richiesta di accreditamento all'ufficio ECM. Testo storico del provider.",
    subject='Accreditamento ECM: {event_name}',
    body=('Ciao {recipient_label},<br><br>'
          "Ti chiedo l'accreditamento per favore del seguente evento:<br>"
          'Nome Evento: <b>{event_name}</b><br>'
          'Data: {event_date}<br>'
          'Luogo: {place}<br>'
          'Cliente (Sponsor): {sponsor}<br>'
          'Codice Evento: {event_code}<br><br>'
          'Trovi la cartella in: {folder_path}<br><br>'
          'Grazie mille, {sender_name}.'),
    required=('event_name', 'event_date', 'place', 'sponsor'),
    defaults={'recipient_label': 'ECM', 'event_code': '', 'folder_path': '', 'sender_name': ''},
)

TASK_UPDATE = MessageTemplate(
    name='task_update',
    description='Avviso a un fornitore quando una voce della checklist è completata.',
    subject='Aggiornamento: {task} - {event_name}',
    body=('<p>Gentile {recipient},</p>'
          "<p>L'evento <strong>{event_name}</strong> ha ricevuto un nuovo aggiornamento:</p>"
          '<p><strong>Task completato:</strong> {task}</p>'
          '<p><strong>Data evento:</strong> {event_date}</p>'
          '<p><strong>Luogo:</strong> {place}</p>'
          '<p>{message}</p>'
          '<p>Cordiali saluti,<br>{sender_name}</p>'),
    required=('recipient', 'event_name', 'task'),
    defaults={'event_date': 'N/D', 'place': 'N/D', 'message': '', 'sender_name': ''},
)

INVITATION_EMAIL = MessageTemplate(
    name='invitation_email',
    description="Email che accompagna la lettera di invito all'ospedale.",
    subject='Invito - {event_name} - {event_place}',
    body=('<p>Gentile {recipient},</p>'
          '<p>in allegato la lettera di invito per {physician_count} {physician_term} '
          "{department_phrase} per l'evento <strong>{event_name}</strong>, {date_text}, "
          '{event_place}.</p>'
          '<p>{notes}</p>'
          '<p>Cordiali saluti,<br>{sender_name}</p>'),
    required=('recipient', 'event_name', 'event_place', 'physician_count'),
    defaults={'physician_term': 'medici', 'department_phrase': '', 'date_text': '', 'notes': '',
              'sender_name': ''},
)

MISSING_ECM_DATA = MessageTemplate(
    name='missing_ecm_data',
    description="Richiesta al partecipante dei dati mancanti per l'attestato ECM.",
    subject="Dati mancanti per l'attestato ECM - {event_name}",
    body=('<p>Gentile {recipient},</p>'
          "<p>per poterLe rilasciare l'attestato ECM dell'evento <strong>{event_name}</strong> "
          'ci mancano alcune informazioni:</p>'
          '<p>{missing_fields}</p>'
          '<p>Può completarle a questo indirizzo: {link}</p>'
          '<p>Cordiali saluti,<br>{sender_name}</p>'),
    required=('recipient', 'event_name', 'missing_fields'),
    defaults={'link': '', 'sender_name': ''},
)

CERTIFICATE_READY = MessageTemplate(
    name='certificate_ready',
    description='Comunicazione di attestato disponibile, con crediti e codice di verifica.',
    subject='Attestato ECM disponibile - {event_name}',
    body=('<p>Gentile {recipient},</p>'
          "<p>l'attestato dell'evento <strong>{event_name}</strong> è disponibile.</p>"
          '<p><strong>Crediti assegnati:</strong> {credits}<br>'
          '<strong>Numero attestato:</strong> {certificate_number}</p>'
          '<p>Può verificarne la validità a questo indirizzo: {verification_url}</p>'
          '<p>Cordiali saluti,<br>{sender_name}</p>'),
    required=('recipient', 'event_name', 'credits', 'certificate_number'),
    defaults={'verification_url': '', 'sender_name': ''},
)

GRAPHIC_BRIEF = MessageTemplate(
    name='graphic_brief',
    description='Brief al grafico, con la palette derivata dalla specialità.',
    subject='Brief grafico - {event_name}',
    body=('<p>Ciao,</p>'
          "<p>per l'evento <strong>{event_name}</strong> ({date_text}, {place}):</p>"
          '<p><strong>Specialità rilevata:</strong> {specialty}<br>'
          '<strong>Palette:</strong> {palette_description}<br>'
          '<strong>CMYK:</strong> {cmyk}<br>'
          '<strong>RGB:</strong> {rgb}</p>'
          '<p><strong>Parole chiave che hanno determinato la scelta:</strong> {keywords}</p>'
          '<p>{notes}</p>'
          '<p>Grazie,<br>{sender_name}</p>'),
    required=('event_name', 'specialty'),
    defaults={'date_text': '', 'place': '', 'palette_description': '', 'cmyk': '', 'rgb': '',
              'keywords': '', 'notes': '', 'sender_name': ''},
)

REMINDER_DUE = MessageTemplate(
    name='reminder_due',
    description='Promemoria interno di una mansione in scadenza.',
    subject='Promemoria: {task} - {event_name}',
    body=('<p><strong>{task}</strong> per {event_name} ({event_code})</p>'
          '<p>Data promemoria: {remind_on}</p>'
          '<p>{notes}</p>'),
    required=('task', 'event_name'),
    defaults={'event_code': '', 'remind_on': '', 'notes': ''},
)

DEADLINE_ALERT = MessageTemplate(
    name='deadline_alert',
    description='Avviso interno su una voce di checklist in ritardo.',
    subject='In ritardo: {deliverable} - {event_name}',
    body=("<p>La voce <strong>{deliverable}</strong> dell'evento <strong>{event_name}</strong> "
          'era attesa entro il {deadline}.</p>'
          "<p>Mancano {days_to_event} giorni all'evento.</p>"
          '<p>{notes}</p>'),
    required=('deliverable', 'event_name', 'deadline'),
    defaults={'days_to_event': '', 'notes': ''},
)


MESSAGE_TEMPLATES = {
    template.name: template for template in (
        ACCREDITATION_REQUEST, TASK_UPDATE, INVITATION_EMAIL, MISSING_ECM_DATA, CERTIFICATE_READY,
        GRAPHIC_BRIEF, REMINDER_DUE, DEADLINE_ALERT,
    )
}


def get_template(name) -> MessageTemplate:
    try:
        return MESSAGE_TEMPLATES[name]
    except KeyError:
        raise TemplateError(f'template sconosciuto: {name}') from None


def render_named(name, context, **kwargs):
    return render(get_template(name), context, **kwargs)


#: Document templates shipped with the plugin, relative to `templates/`
DOCUMENT_TEMPLATES = {
    'invitation_letter': {
        'path': 'letters/lettera_invito.docx',
        'description': 'Lettera di invito ai medici, template Word storico del provider.',
        'context': ('destinatario', 'nomeOspedale', 'numeroMedici', 'ruolo', 'nomeEvento', 'luogoEvento',
                    'dataEvento', 'fraseRepartoOspedale', 'altreNote', 'userName'),
    },
}

#: Files the event folder is created with, ported from the automator
EVENT_FOLDER_FILES = (
    'info_evento.txt',
    'briefing.txt',
    'agenda.txt',
    'report_template.txt',
    'email_draft.html',
)
