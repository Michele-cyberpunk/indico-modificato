# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from indico_ecm.services.faculty import Speaker, letter_context, letter_filename, resolve_gender


@pytest.fixture
def event():
    return SimpleNamespace(id=7, title='Cardio Update',
                           start_dt=datetime(2026, 9, 15, 9, 0),
                           end_dt=datetime(2026, 9, 15, 18, 0))


def test_the_file_is_named_the_way_the_office_files_it():
    assert letter_filename(Speaker(1, 'Rossi Mario')) == 'Lettera di incarico Rossi Mario.docx'


def test_a_name_that_cannot_be_used_as_a_file_falls_back_to_the_person():
    assert letter_filename(Speaker(42, '///')) == 'Lettera di incarico relatore-42.docx'


def test_the_tax_code_outranks_what_the_title_suggested():
    # The record said masculine; the tax code says otherwise, and it is evidence.
    speaker = Speaker(1, 'Laura Rossi', gender='M', tax_code='RSSLRA80A41H501T')
    assert resolve_gender(speaker) == 'F'


def test_without_a_tax_code_the_recorded_gender_stands():
    assert resolve_gender(Speaker(1, 'Mario Rossi', gender='M')) == 'M'
    assert resolve_gender(Speaker(1, 'Mario Rossi')) == ''


def test_the_context_carries_the_dates_of_the_event(event):
    context = letter_context(Speaker(1, 'Mario Rossi'), event=event, letter_day=date(2026, 8, 24))
    assert context['data_evento'] == '15/09/2026'
    assert context['data_fine_evento'] == '15/09/2026'
    assert context['anno'] == '2026'
    assert context['evento_ecm'] == 'Cardio Update'


def test_a_fee_brings_the_withholding_and_the_note(event):
    speaker = Speaker(1, 'Mario Rossi', gender='M', title='doctor', fee='800', has_vat_number=True)
    context = letter_context(speaker, event=event)
    assert context['saluto'] == 'Egregio Dottore'
    assert context['compenso'] == '800,00'
    assert context['compenso_lettere'] == 'Ottocento,00'
    assert context['ritenuta_acconto'] == '160,00'
    assert context['totale_netto'] == '640,00'
    assert '20%' in context['nota_piva']


def test_without_a_fee_no_money_is_written_anywhere(event):
    context = letter_context(Speaker(1, 'Mario Rossi', gender='M'), event=event)
    assert context['compenso'] == ''
    assert context['ritenuta_acconto'] == ''
    assert context['nota_piva'] == ''


def test_an_unknown_gender_opens_with_the_company_form(event):
    context = letter_context(Speaker(1, 'Mario Rossi', title='doctor'), event=event)
    assert context['saluto'] == 'Spett.le'


def test_without_a_vat_number_the_note_states_the_gross_amount(event):
    speaker = Speaker(1, 'Mario Rossi', gender='M', fee='500', has_vat_number=False)
    context = letter_context(speaker, event=event)
    assert context['nota_piva'] == 'Compenso lordo € 500,00.'
