# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import io
from datetime import date

import pytest

from indico_ecm.services.automator import (AUTOMATOR_PROMPT_V1, AUTOMATOR_RESPONSE_SCHEMA, AutomatorError,
                                           FOLDER_TEMPLATES, build_folder_archive, build_folder_files,
                                           build_request, extract,
                                           find_event_code, find_speakers, folder_name_for,
                                           prompt_fingerprint, read_document, validate_response)


EMAIL = '''Buongiorno,
vi confermiamo l'evento 0116_GDBO previsto per il 15/09/2026 presso l'Hotel Excelsior di Milano.
Il programma prevede interventi su scompenso cardiaco e stenosi aortica.
Relatori confermati: Dott. Mario Rossi, Prof.ssa Anna Verdi.
Cordiali saluti.'''


def test_prompt_is_versioned_and_hashed():
    assert prompt_fingerprint() == prompt_fingerprint(AUTOMATOR_PROMPT_V1)
    assert len(prompt_fingerprint()) == 16
    assert prompt_fingerprint('altro testo') != prompt_fingerprint()


def test_prompt_forbids_inventing_credits():
    assert 'credits are decided by the accreditation dossier' in AUTOMATOR_PROMPT_V1
    assert 'Do not invent' in AUTOMATOR_PROMPT_V1


def test_schema_requires_the_two_useful_sections():
    assert AUTOMATOR_RESPONSE_SCHEMA['required'] == ['extractedData', 'fileContents']


def test_extract_finds_the_event_code():
    result = extract(EMAIL)
    assert result.event_code == '0116_GDBO'
    assert '0116_GDBO' in result.evidence['event_code']


def test_extract_finds_the_date():
    assert extract(EMAIL).event_date == date(2026, 9, 15)


def test_extract_finds_the_speakers():
    assert extract(EMAIL).speakers == ['Mario Rossi', 'Anna Verdi']


def test_extract_classifies_the_specialty_and_the_format():
    result = extract(EMAIL)
    assert result.specialty == 'cardiovascular'
    assert result.activity_format == 'RES_CON_QUESTIONARIO'


def test_extract_reports_what_it_could_not_resolve():
    result = extract(EMAIL)
    assert 'event_name' in result.unresolved
    assert 'sponsor' in result.unresolved
    assert result.needs_model


def test_known_values_are_not_reported_as_unresolved():
    result = extract(EMAIL, known_sponsor='Acme Pharma', known_location='Milano')
    assert 'sponsor' not in result.unresolved
    assert 'location' not in result.unresolved


def test_extract_on_an_empty_text_resolves_nothing():
    result = extract('')
    assert result.event_code == ''
    assert result.event_date is None
    assert {'event_code', 'event_date', 'speakers'} <= set(result.unresolved)


def test_extract_takes_the_earliest_of_two_dates_as_the_start():
    result = extract('Evento dal 15/09/2026 al 16/09/2026')
    assert result.event_date == date(2026, 9, 15)
    assert result.end_date == date(2026, 9, 16)


def test_folder_name_uses_the_provider_convention():
    result = extract(EMAIL, known_sponsor='Acme Pharma', known_location='Milano')
    name = folder_name_for(result, event_name='Cardio Update')
    assert name.startswith('0915 CARDIO ')
    assert 'ACME-PHARMA' in name
    # the naming convention turns underscores into hyphens
    assert '0116-GDBO' in name


def test_build_request_carries_the_deterministic_part():
    request = build_request(EMAIL, known_sponsor='Acme Pharma', known_location='Milano')
    assert request['prompt_version'] == 'automator-v1'
    assert request['deterministic']['event_code'] == '0116_GDBO'
    assert request['deterministic']['event_date'] == '2026-09-15'
    assert request['deterministic']['specialty'] == 'cardiovascular'
    assert 'event_name' in request['unresolved']


def test_validate_response_returns_the_useful_parts():
    result = validate_response({
        'extractedData': {'eventName': 'Cardio Update', 'eventCode': '0116_GDBO'},
        'fileContents': {'briefing.txt': 'testo', 'agenda.txt': ''},
        'folderName': '0915 CARDIO MILANO',
    })
    assert result['extracted']['eventName'] == 'Cardio Update'
    assert 'briefing.txt' in result['files']
    # empty files are dropped rather than created empty
    assert 'agenda.txt' not in result['files']


def test_platform_values_win_over_the_model():
    result = validate_response(
        {'extractedData': {'eventCode': 'INVENTATO'}, 'fileContents': {}, 'folderName': 'CARTELLA MODELLO'},
        deterministic={'event_code': '0116_GDBO', 'folder_name': '0915 CARDIO MILANO'},
    )
    assert result['extracted']['eventCode'] == '0116_GDBO'
    assert result['folder_name'] == '0915 CARDIO MILANO'
    assert {conflict['field'] for conflict in result['conflicts']} == {'event_code', 'folder_name'}


def test_no_conflict_when_the_model_agrees():
    result = validate_response(
        {'extractedData': {'eventCode': '0116_GDBO'}, 'fileContents': {}, 'folderName': 'X'},
        deterministic={'event_code': '0116_GDBO', 'folder_name': 'X'},
    )
    assert result['conflicts'] == []


def test_malformed_responses_are_rejected():
    with pytest.raises(AutomatorError, match='atteso un oggetto'):
        validate_response('not json')
    with pytest.raises(AutomatorError, match='fileContents'):
        validate_response({'extractedData': {}})


# --- the event code -----------------------------------------------------------------
# A wrong code files the accreditation request under the wrong event, so the
# pattern is narrow on purpose and these are the strings that used to break it.

@pytest.mark.parametrize(('text', 'expected'), (
    ('Evento 0116_GDBO del 15/09/2026', '0116_GDBO'),
    ('Corso 2026-CARD, sede di Roma', '2026-CARD'),
    ('Codice evento: AB-2026/12', 'AB-2026/12'),
    ('Rif. 998877 per la fatturazione', '998877'),
    ('cod. ECM-7781 come da accordi', 'ECM-7781'),
))
def test_find_event_code_accepts_what_is_a_code(text, expected):
    assert find_event_code(text) == expected


@pytest.mark.parametrize('text', (
    'P.IVA IT12345678901',
    "L'evento si tiene in Sala A101",
    'Aula B12, primo piano',
    'Fattura FT2026 da saldare',
    'Nessun riferimento in questo testo.',
    '',
))
def test_find_event_code_refuses_what_only_looks_like_one(text):
    assert find_event_code(text) == ''


def test_an_announced_code_wins_over_the_convention():
    text = 'Evento 0116_GDBO. Codice evento: SPONSOR-42 da usare in fattura.'
    assert find_event_code(text) == 'SPONSOR-42'


def test_a_keyword_without_digits_is_not_a_code():
    # "Rif. protocollo" announces nothing usable; better empty than "protocollo"
    assert find_event_code('Rif. protocollo interno') == ''


# --- the speakers -------------------------------------------------------------------

@pytest.mark.parametrize(('text', 'expected'), (
    ('Dott. Mario Rossi', ['Mario Rossi']),
    ('Prof. Gian Luca De Angelis', ['Gian Luca De Angelis']),
    ('Dott.ssa Maria Della Rocca', ['Maria Della Rocca']),
    ('Prof. Jan van den Berg', ['Jan van den Berg']),
    ("Dott. Antonio D'Amico", ["Antonio D'Amico"]),
    ('Dott. Mario Rossi Presidente', ['Mario Rossi']),
    ('Relatori: Dott.ssa Anna De Luca e Prof. Paolo Ferri', ['Anna De Luca', 'Paolo Ferri']),
))
def test_find_speakers_keeps_the_whole_name(text, expected):
    assert find_speakers(text) == expected


def test_find_speakers_does_not_repeat_a_name():
    assert find_speakers('Dott. Mario Rossi apre. Dott. Mario Rossi chiude.') == ['Mario Rossi']


def test_find_speakers_needs_a_title():
    assert find_speakers('Mario Rossi ha confermato la presenza.') == []


# --- the event folder ---------------------------------------------------------------

def test_the_folder_file_list_and_the_templates_cannot_drift():
    from indico_ecm.services.templates import EVENT_FOLDER_FILES

    assert set(FOLDER_TEMPLATES) == set(EVENT_FOLDER_FILES)


def test_folder_files_are_the_five_starting_documents():
    files = build_folder_files(extract(EMAIL))
    assert set(files) == {'info_evento.txt', 'briefing.txt', 'agenda.txt',
                          'report_template.txt', 'email_draft.html'}
    assert all(content.strip() for content in files.values())


def test_info_evento_carries_what_was_extracted():
    extraction = extract(EMAIL, known_sponsor='Acme Pharma', known_location='Milano')
    info = build_folder_files(extraction, event_name='Cardio Update')['info_evento.txt']
    assert '0116_GDBO' in info
    assert '15/09/2026' in info
    assert 'Acme Pharma' in info
    assert 'cardiovascular' in info
    assert 'Mario Rossi' in info and 'Anna Verdi' in info


def test_what_was_not_found_is_written_down_not_invented():
    info = build_folder_files(extract('Testo senza dati utili.'))['info_evento.txt']
    assert 'Dati non ricavati dal materiale' in info
    assert '(da confermare)' in info


def test_the_archive_is_one_folder_named_by_the_convention():
    import zipfile

    extraction = extract(EMAIL, known_sponsor='Acme Pharma', known_location='Milano')
    folder, data = build_folder_archive(extraction, event_name='Cardio Update',
                                        sponsor='Acme Pharma', place='Milano')
    assert folder.startswith('0915 CARDIO ')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert all(name.startswith(f'{folder}/') for name in names)
        assert f'{folder}/info_evento.txt' in names
        assert 'Cardio Update' in archive.read(f'{folder}/briefing.txt').decode()


def test_the_archive_takes_extra_files():
    import zipfile

    folder, data = build_folder_archive(extract(EMAIL), extra_files={'allegato.txt': 'contenuto'})
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read(f'{folder}/allegato.txt') == b'contenuto'


# --- reading the attachments --------------------------------------------------------

def test_read_document_reads_plain_text():
    assert read_document(b'Evento 0116_GDBO', 'nota.txt') == 'Evento 0116_GDBO'


def test_read_document_strips_the_markup_of_a_saved_email():
    text = read_document(b'<p>Evento <b>0116_GDBO</b></p>', 'messaggio.eml')
    assert find_event_code(text) == '0116_GDBO'


def test_read_document_says_so_instead_of_guessing():
    with pytest.raises(ValueError, match='formato non supportato'):
        read_document(b'\x00\x01', 'presentazione.pptx')
