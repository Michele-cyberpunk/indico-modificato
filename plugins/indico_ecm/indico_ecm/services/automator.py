# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The automator.

In the legacy application this is the feature that reads the email and the
attachments a sponsor sends and sets up the event: it extracts the details,
proposes a folder name and drafts the starting documents.

Two things change in the port, and both are the point of it:

- the prompt is **data**, versioned and hashed, so what an extraction was asked
  to do is recoverable months later;
- the deterministic part is separated from the model. Dates, event codes and
  folder names are found with rules; the model is only needed for prose. When
  the rules are enough, no model is called at all.

Nothing here calls a language model: this module prepares the request and
validates the answer. The call belongs to the agent runtime, behind its
permission table.

Pure, no Indico imports.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date

from indico_ecm.services.legacy_import import parse_date
from indico_ecm.services.naming import generate_folder_name
from indico_ecm.services.specialty import identify_event_format, identify_specialty


#: The instruction ported from `state.js`, kept as the provider wrote it.
#: Change it by adding a new version, never by editing this string in place.
AUTOMATOR_PROMPT_V1 = """## Role and Goal
You are an expert event management assistant for a medical event organizer. Your goal is to analyze
provided email text and documents to automatically set up a new event. You must extract key
information, generate the starting documents, and prepare the folder structure.

## Analysis and Extraction
1. Analyze: read the user-provided email text and any attached documents.
2. Extract: eventName, eventDate (YYYY-MM-DD), eventLocation, eventSponsor, eventCode, speakers.
3. Folder name: follow the organizer's convention, which is provided to you already computed.
   Do not invent a different one.

## Content Generation
Produce professional, concise content for: info_evento.txt, briefing.txt, agenda.txt,
report_template.txt, email_draft.html.

## Rules
- Do not invent dates, codes or names that are not in the source material. Leave a field empty
  instead, and say what was missing.
- Do not state the number of ECM credits: credits are decided by the accreditation dossier.
- Report every value you extracted together with the sentence you took it from.

## Output Format
Return a single JSON object adhering to the provided schema, with no text outside it."""

AUTOMATOR_PROMPT_VERSION = 'automator-v1'

#: The response contract, ported from `automatorResponseSchema`
AUTOMATOR_RESPONSE_SCHEMA = {
    'type': 'object',
    'required': ['extractedData', 'fileContents'],
    'properties': {
        'folderName': {'type': 'string'},
        'extractedData': {
            'type': 'object',
            'properties': {
                'eventName': {'type': 'string'},
                'eventDate': {'type': 'string'},
                'eventLocation': {'type': 'string'},
                'eventSponsor': {'type': 'string'},
                'eventCode': {'type': 'string'},
                'speakers': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
        'fileContents': {
            'type': 'object',
            'properties': {
                'info_evento.txt': {'type': 'string'},
                'briefing.txt': {'type': 'string'},
                'agenda.txt': {'type': 'string'},
                'report_template.txt': {'type': 'string'},
                'email_draft.html': {'type': 'string'},
            },
        },
        'evidence': {
            'type': 'object',
            'description': 'For each extracted field, the sentence it came from.',
        },
        'imagePrompt': {'type': 'string'},
    },
}


def prompt_fingerprint(prompt=AUTOMATOR_PROMPT_V1):
    """Hash of the instruction, recorded on every extraction."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


#: Event codes as the provider writes them: 0116_GDBO, C123, 2026-ABC
EVENT_CODE_RE = re.compile(r'\b(\d{3,4}[_-][A-Z]{2,6}|[A-Z]{1,3}\d{2,5}|\d{4}-[A-Z]{2,6})\b')
DATE_RE = re.compile(r'\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})\b')
#: "Dott. Mario Rossi", "Prof.ssa Anna Verdi"
_TITLE = r'(?:Dott\.ssa|Dott\.|Prof\.ssa|Prof\.|Dr\.)'
_NAME = r"[A-ZÀ-Ú][\w'À-ú]+"
SPEAKER_RE = re.compile(rf'\b{_TITLE}\s*({_NAME}(?:\s+{_NAME}){{0,2}})')


@dataclass
class Extraction:
    """What the deterministic pass could establish on its own."""

    event_name: str = ''
    event_date: date | None = None
    end_date: date | None = None
    location: str = ''
    sponsor: str = ''
    event_code: str = ''
    speakers: list = field(default_factory=list)
    specialty: str = ''
    activity_format: str = ''
    folder_name: str = ''
    #: field -> the sentence it was taken from
    evidence: dict = field(default_factory=dict)
    #: What the rules could not determine and a model (or a person) must supply
    unresolved: list = field(default_factory=list)

    @property
    def needs_model(self):
        return bool(self.unresolved)


def _sentence_containing(text, needle):
    for sentence in re.split(r'(?<=[.!?\n])\s+', text or ''):
        if needle and needle in sentence:
            return sentence.strip()[:300]
    return ''


def extract(text, *, known_sponsor='', known_location=''):
    """Find what can be found with rules alone.

    Deliberately conservative: it reports what it saw and where, and lists what
    it could not resolve, rather than producing a confident guess.
    """
    text = text or ''
    result = Extraction(sponsor=known_sponsor, location=known_location)

    codes = EVENT_CODE_RE.findall(text)
    if codes:
        result.event_code = codes[0]
        result.evidence['event_code'] = _sentence_containing(text, codes[0])
    else:
        result.unresolved.append('event_code')

    dates = [parse_date(match) for match in DATE_RE.findall(text)]
    dates = sorted({value for value in dates if value})
    if dates:
        result.event_date = dates[0]
        result.evidence['event_date'] = _sentence_containing(text, DATE_RE.findall(text)[0])
        if len(dates) > 1:
            result.end_date = dates[1]
    else:
        result.unresolved.append('event_date')

    speakers = []
    for name in SPEAKER_RE.findall(text):
        if name not in speakers:
            speakers.append(name)
    result.speakers = speakers
    if not speakers:
        result.unresolved.append('speakers')

    match = identify_specialty(text)
    result.specialty = match.specialty
    result.activity_format = identify_event_format(text)

    if not result.location:
        result.unresolved.append('location')
    if not result.sponsor:
        result.unresolved.append('sponsor')
    result.unresolved.append('event_name')
    return result


def folder_name_for(extraction: Extraction, *, event_name='', city=''):
    """The folder name, computed by the platform rather than by the model."""
    return generate_folder_name(
        start_date=extraction.event_date,
        end_date=extraction.end_date,
        event_name=event_name or extraction.event_name,
        event_type=extraction.activity_format,
        city=city or extraction.location,
        sponsor=extraction.sponsor,
        event_code=extraction.event_code,
    )


def build_request(text, *, known_sponsor='', known_location=''):
    """Everything the agent runtime needs to ask a model for the rest.

    The folder name is passed in already computed: the convention belongs to the
    provider, not to whatever the model would come up with.
    """
    extraction = extract(text, known_sponsor=known_sponsor, known_location=known_location)
    return {
        'prompt': AUTOMATOR_PROMPT_V1,
        'prompt_version': AUTOMATOR_PROMPT_VERSION,
        'prompt_sha': prompt_fingerprint(),
        'response_schema': AUTOMATOR_RESPONSE_SCHEMA,
        'deterministic': {
            'event_code': extraction.event_code,
            'event_date': extraction.event_date.isoformat() if extraction.event_date else '',
            'speakers': list(extraction.speakers),
            'specialty': extraction.specialty,
            'activity_format': extraction.activity_format,
            'folder_name': folder_name_for(extraction),
        },
        'unresolved': list(extraction.unresolved),
        'source_length': len(text or ''),
    }


class AutomatorError(Exception):
    pass


def validate_response(payload, *, deterministic=None):
    """Check a model answer before anything is created from it.

    The deterministic values win: if the model returns a different event code or
    folder name, the platform's own value is kept and the disagreement is
    reported. A model does not get to rename a folder that already has a
    convention.
    """
    if not isinstance(payload, dict):
        raise AutomatorError('risposta non valida: atteso un oggetto JSON')
    for key in ('extractedData', 'fileContents'):
        if key not in payload:
            raise AutomatorError(f'risposta incompleta: manca {key}')

    extracted = dict(payload.get('extractedData') or {})
    files = dict(payload.get('fileContents') or {})
    conflicts = []
    deterministic = deterministic or {}

    for model_key, own_key in (('eventCode', 'event_code'), ('folderName', 'folder_name')):
        own_value = deterministic.get(own_key)
        model_value = extracted.get(model_key) if model_key == 'eventCode' else payload.get('folderName')
        if own_value and model_value and str(model_value).strip() != str(own_value).strip():
            conflicts.append({'field': own_key, 'platform': own_value, 'model': model_value})

    if deterministic.get('event_code'):
        extracted['eventCode'] = deterministic['event_code']
    folder_name = deterministic.get('folder_name') or payload.get('folderName', '')

    return {
        'extracted': extracted,
        'files': {name: content for name, content in files.items() if content},
        'folder_name': folder_name,
        'conflicts': conflicts,
        'image_prompt': payload.get('imagePrompt', ''),
        'evidence': payload.get('evidence', {}),
    }
