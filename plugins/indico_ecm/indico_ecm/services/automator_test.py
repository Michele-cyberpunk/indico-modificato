# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import date

import pytest

from indico_ecm.services.automator import (AUTOMATOR_PROMPT_V1, AUTOMATOR_RESPONSE_SCHEMA, AutomatorError,
                                           build_request, extract, folder_name_for, prompt_fingerprint,
                                           validate_response)


EMAIL = """Buongiorno,
vi confermiamo l'evento 0116_GDBO previsto per il 15/09/2026 presso l'Hotel Excelsior di Milano.
Il programma prevede interventi su scompenso cardiaco e stenosi aortica.
Relatori confermati: Dott. Mario Rossi, Prof.ssa Anna Verdi.
Cordiali saluti."""


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
