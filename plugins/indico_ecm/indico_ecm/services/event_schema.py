# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The provider's event record, as it exists today.

Ported from `js/core/state.js` of the Cyberbrain event manager, where the whole
application is driven by three column definitions: events, mail merge rows and
special reminders. They are reproduced here field by field, because they are the
shape of every spreadsheet, CSV export and habit in the office.

The schema is data, not classes: it drives the legacy import, the field mapping
towards Indico and the ECM models, and it documents what each column meant.

Pure, no Indico imports.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from indico_ecm.services.deliverables import Deliverable


class FieldType(StrEnum):
    text = 'text'
    textarea = 'textarea'
    date = 'date'
    number = 'number'
    email = 'email'
    boolean = 'boolean'


class Destination(StrEnum):
    """Where a legacy column ends up in the platform."""

    #: Native Indico event attribute
    indico_event = 'indico_event'
    #: Operational record of the ECM plugin
    operations = 'operations'
    #: Accreditation dossier
    accreditation = 'accreditation'
    #: One of the checklist deliverables
    deliverable = 'deliverable'
    #: Faculty (event persons)
    faculty = 'faculty'
    #: CRM company or contact
    crm = 'crm'
    #: Kept as-is for reference, not mapped
    legacy_only = 'legacy_only'


@dataclass(frozen=True)
class LegacyField:
    key: str
    label: str
    type: FieldType = FieldType.text
    required: bool = False
    destination: Destination = Destination.operations
    #: Target attribute or deliverable, when it maps to one
    target: str = ''
    options: tuple = ()
    note: str = ''


def _flag(key, label, deliverable, note='', required=False):
    """A yes/no column that becomes a checklist deliverable."""
    return LegacyField(key=key, label=label, type=FieldType.boolean, options=('No', 'Sì'), required=required,
                       destination=Destination.deliverable, target=deliverable.value, note=note)


#: The event record, in the order it appears in the legacy table
EVENT_FIELDS = (
    LegacyField('nomeEvento', 'Nome Evento', required=True, destination=Destination.indico_event, target='title'),
    LegacyField('cliente', 'Cliente', required=True, destination=Destination.crm,
                target='company', note='sponsor principale o committente'),
    LegacyField('dataEvento1', 'Data Evento', FieldType.date, required=True,
                destination=Destination.indico_event, target='start_dt'),
    LegacyField('cambioData', 'Cambio Data?', options=('No', 'Sì'), destination=Destination.operations,
                target='date_changed'),
    LegacyField('vecchiaData', 'Vecchia Data', FieldType.date, destination=Destination.operations,
                target='previous_date'),
    LegacyField('dataEvento2', 'Data Evento 2', FieldType.date, destination=Destination.indico_event,
                target='end_dt'),
    LegacyField('citta', 'Città', required=True, destination=Destination.indico_event, target='venue_city'),
    LegacyField('codiceEvento', 'Codice Evento', required=True, destination=Destination.operations,
                target='event_code'),
    LegacyField('orario', 'Orario', required=True, destination=Destination.operations, target='schedule_text'),
    LegacyField('luogo', 'Luogo', required=True, destination=Destination.indico_event, target='venue_name'),
    LegacyField('cambioLuogo', 'Cambio Luogo?', options=('No', 'Sì'), destination=Destination.operations,
                target='venue_changed'),
    LegacyField('codieAgenas', 'Codice AGENAS', destination=Destination.accreditation, target='activity_code',
                note="refuso nel nome originale della colonna, mantenuto per l'import"),
    LegacyField('numeroPartecipanti', 'N° Partecipanti', FieldType.number, required=True,
                destination=Destination.accreditation, target='max_participants'),
    LegacyField('programma', 'Programma', destination=Destination.operations, target='programme_ref'),
    _flag('primoContattoRelatori', 'Primo contatto relatori', Deliverable.faculty_first_contact),
    _flag('attivazione', 'Attivazione', Deliverable.activation),
    _flag('accreditamento', 'Accreditamento', Deliverable.accreditation, required=True),
    LegacyField('creditiEvento', 'Crediti Evento', FieldType.number, destination=Destination.accreditation,
                target='credits'),
    LegacyField('tipoEvento', 'Tipo Evento', required=True, destination=Destination.accreditation,
                target='activity_format'),
    _flag('contrattiSponsor', 'Contratti Sponsor', Deliverable.sponsor_contract),
    _flag('grafica', 'Grafica', Deliverable.graphics),
    _flag('numePiattaforma', 'NUME/Piattaforma', Deliverable.platform),
    _flag('catering', 'Catering', Deliverable.catering),
    _flag('contrattoHotel', 'Contratto Hotel', Deliverable.hotel_contract),
    _flag('letteraIncarico', "Lettera d'incarico", Deliverable.assignment_letter),
    _flag('hostess', 'Hostess', Deliverable.hostess),
    _flag('opzioneSede', 'Opzione sede', Deliverable.venue_option),
    _flag('slideKit', 'Slide kit', Deliverable.slide_kit),
    _flag('foglioLogistica', 'Foglio logistica', Deliverable.logistics_sheet),
    _flag('briefHotel', 'Brief hotel', Deliverable.hotel_brief),
    _flag('consuntivo', 'Consuntivo', Deliverable.final_report),
    _flag('invio', 'Invio', Deliverable.dispatch),
    _flag('stampaGrafiche', 'Stampa grafiche', Deliverable.graphics_printing),
    LegacyField('nomeCartella', 'NomeCartella', destination=Destination.operations, target='folder_name'),
    LegacyField('uecm', 'UECM', destination=Destination.operations, target='accreditation_contact'),
    LegacyField('emailNume', 'Email NUME', FieldType.email, destination=Destination.operations,
                target='platform_email'),
    LegacyField('emailGrafico', 'Email Grafico', FieldType.email, destination=Destination.operations,
                target='designer_email'),
    LegacyField('emailHostess', 'Email Hostess', FieldType.email, destination=Destination.operations,
                target='hostess_email'),
    LegacyField('accreditationTo', 'Accred. To', FieldType.email, destination=Destination.operations,
                target='accreditation_to'),
    LegacyField('accreditationCC', 'Accred. CC', destination=Destination.operations, target='accreditation_cc'),
    LegacyField('accreditationBCC', 'Accred. BCC', destination=Destination.operations, target='accreditation_bcc'),
    LegacyField('accreditationSubject', 'Accred. Subject', destination=Destination.operations,
                target='accreditation_subject'),
    LegacyField('accreditationBody', 'Accred. Body', FieldType.textarea, destination=Destination.operations,
                target='accreditation_body'),
    LegacyField('mansioneEmail', 'Mansione Email Automatica', FieldType.textarea,
                destination=Destination.operations, target='task_email_note'),
    LegacyField('includeInReport', 'Include in Report', options=('Sì', 'No'),
                destination=Destination.operations, target='include_in_report'),
    LegacyField('note', 'Note', destination=Destination.operations, target='notes'),
)

#: Faculty columns, five fixed slots in the legacy table
FACULTY_FIELDS = tuple(
    LegacyField(f'relatore{n}', f'Relatore{n}', destination=Destination.faculty, target='event_person')
    for n in range(1, 6)
) + tuple(
    LegacyField(f'mail{n}', f'Mail{n}', FieldType.email, destination=Destination.faculty, target='email')
    for n in range(1, 6)
)

#: Mail merge rows: one hospital, its physicians and what the sponsor pays for them
INVITATION_FIELDS = (
    LegacyField('nomeOspedale', 'Nome Ospedale', destination=Destination.crm, target='company'),
    LegacyField('numeroMedici', 'N° Medici', FieldType.number),
    LegacyField('nomeEvento', 'Nome Evento', destination=Destination.indico_event, target='title'),
    LegacyField('dataEvento', 'Data Evento', FieldType.date),
    LegacyField('dataEvento2', 'Data Evento 2', FieldType.date),
    LegacyField('luogoEvento', 'Luogo Evento'),
    LegacyField('destinatario', 'Destinatario', destination=Destination.crm, target='contact'),
    LegacyField('mail', 'Email Destinatario', FieldType.email, destination=Destination.crm, target='contact_email'),
    LegacyField('ccMail', 'CC Email'),
    LegacyField('reparto', 'Reparto'),
    LegacyField('specialita', 'Specialità', destination=Destination.crm, target='discipline'),
    LegacyField('sponsor', 'Sponsor', destination=Destination.crm, target='sponsor'),
    LegacyField('ruolo', 'Ruolo'),
    LegacyField('costoCamera', 'Costo Camera (€)', FieldType.number),
    LegacyField('costoCityTax', 'Costo City Tax (€)', FieldType.number),
    LegacyField('costoRistorativo', 'Costo Ristorativo (€)', FieldType.number),
    LegacyField('numeroPranzi', 'N° Pranzi', FieldType.number),
    LegacyField('numeroCoffeeBreak', 'N° Coffee Break', FieldType.number),
    LegacyField('numeroCene', 'N° Cene', FieldType.number),
    LegacyField('viaggio', 'Costo Viaggio (€)', FieldType.number),
    LegacyField('numeroCrediti', 'N° Crediti ECM', FieldType.number, destination=Destination.accreditation,
                target='credits'),
    LegacyField('luogoInvio', 'Luogo Invio'),
    LegacyField('altreNote', 'Altre Note', FieldType.textarea),
    LegacyField('dataOggi', 'Data Invio', FieldType.date),
)

#: Reminders attached to an event by its code
REMINDER_FIELDS = (
    LegacyField('codiceEvento', 'Codice Evento', destination=Destination.operations, target='event_code'),
    LegacyField('nomeEvento', 'Nome Evento (auto)', destination=Destination.legacy_only),
    LegacyField('luogoEvento', 'Luogo Evento (auto)', destination=Destination.legacy_only),
    LegacyField('mansione', 'Mansione'),
    LegacyField('giornoPreavviso', 'Data Promemoria', FieldType.date),
)


@dataclass(frozen=True)
class SchemaIndex:
    by_key: dict = field(default_factory=dict)
    deliverable_keys: dict = field(default_factory=dict)


def index_fields(fields=EVENT_FIELDS) -> SchemaIndex:
    """Index a field list by key, and the yes/no ones by deliverable."""
    by_key = {item.key: item for item in fields}
    deliverables = {item.key: Deliverable(item.target) for item in fields
                    if item.destination is Destination.deliverable}
    return SchemaIndex(by_key=by_key, deliverable_keys=deliverables)


def required_keys(fields=EVENT_FIELDS):
    return tuple(item.key for item in fields if item.required)


def fields_for(destination, fields=EVENT_FIELDS):
    return tuple(item for item in fields if item.destination is destination)
