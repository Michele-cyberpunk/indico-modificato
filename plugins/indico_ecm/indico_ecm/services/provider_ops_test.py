# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Tests for the provider's operational rules ported from Cyberbrain.

These are regression tests in the strict sense: they pin the behaviour of rules
already in daily use, so the migration to the platform does not silently change
a folder name, a letter's wording or the accreditation email.
"""

from datetime import date

import pytest

from indico_ecm.services.accreditation_mail import (AccreditationRequest, build_body, build_email, build_subject,
                                                    format_date_it, missing_fields, outlook_compose_url)
from indico_ecm.services.letters import (InvitationRow, agreement_terms, invitation_filename, letter_context,
                                         pluralize_role)
from indico_ecm.services.naming import folder_path, generate_folder_name, sanitize_filename, sanitize_part
from indico_ecm.services.specialty import (FORMAT_FAD_ASYNC, FORMAT_RES_WITH_TEST, FORMAT_WEBINAR, graphic_brief,
                                           identify_event_format, identify_specialty)


# --- naming -----------------------------------------------------------------

@pytest.mark.parametrize(('value', 'expected'), (
    ('Ospedale  San Raffaele', 'Ospedale-San-Raffaele'),
    ('a/b_c', 'a-b-c'),
    ('  spazi  ', 'spazi'),
    (None, ''),
))
def test_sanitize_part(value, expected):
    assert sanitize_part(value) == expected


def test_folder_name_single_day():
    name = generate_folder_name(start_date=date(2026, 9, 15), event_name='Cardiologia in pratica',
                                city='Roma', sponsor='Acme Pharma', event_code='C123')
    assert name == '0915 CARDIOLOGIA ROMA ACME-PHARMA C123'


def test_folder_name_multi_day_adds_end_day():
    name = generate_folder_name(start_date=date(2026, 9, 15), end_date=date(2026, 9, 17),
                                event_name='Congresso', city='Milano')
    assert name == '0915-17 CONGRESSO MILANO'


def test_remote_events_are_filed_by_format_not_city():
    name = generate_folder_name(start_date=date(2026, 3, 4), event_name='Update', event_type='FAD asincrona',
                                city='Roma')
    assert name == '0304 UPDATE FAD-ASINCRONA'


def test_multi_sponsor_events_use_the_conventional_name():
    name = generate_folder_name(start_date=date(2026, 3, 4), event_name='Update', city='Roma',
                                sponsor='Multi sponsor')
    assert name.endswith('PLURISPONSOR')


def test_folder_name_without_a_date():
    assert generate_folder_name(event_name='Corso base', city='Bari') == 'CORSO BARI'


def test_folder_path_matches_the_shared_drive_convention():
    assert folder_path(2026, '0915 CARDIO ROMA') == 'S:\\CONGRESSI 2026\\0915 CARDIO ROMA'


def test_sanitize_filename_strips_illegal_characters():
    assert sanitize_filename('Lettera: invito/2026?') == 'Lettera invito2026'


# --- letters ----------------------------------------------------------------

@pytest.mark.parametrize(('role', 'count', 'expected'), (
    ('Relatore', 1, 'Relatore'),
    ('Relatore', 2, 'Relatori'),
    ('Moderatore', 3, 'Moderatori'),
    ('Responsabile scientifico', 2, 'Responsabili scientifici'),
    ('', 5, ''),
    ('  Docente  ', 2, 'Docenti'),
))
def test_pluralize_role(role, count, expected):
    assert pluralize_role(role, count) == expected


def test_pluralize_leaves_short_and_consonant_words_alone():
    assert pluralize_role('Tutor', 4) == 'Tutor'
    assert pluralize_role('e Relatore', 2) == 'e Relatori'


def test_agreement_terms_singular_and_plural():
    assert agreement_terms(1)['medico'] == 'medico'
    assert agreement_terms(1)['appartenente'] == 'o'
    assert agreement_terms(2)['chirurgo'] == 'chirurghi'
    assert agreement_terms(2)['appartenente'] == 'i'


def test_invitation_filename_matches_the_archived_convention():
    row = InvitationRow(hospital='Ospedale San Raffaele', physician_count=3, event_name='Cardio Update',
                        event_place='Milano')
    assert invitation_filename(row) == ('Lettera invito - 3 MEDICI - Ospedale San Raffaele - '
                                        'Cardio Update - Milano.pdf')


def test_invitation_filename_singular():
    row = InvitationRow(hospital='Policlinico', physician_count=1, event_name='Corso', event_place='Roma')
    assert invitation_filename(row).startswith('Lettera invito - 1 MEDICO - ')


def test_letter_context_pluralizes_and_builds_the_department_phrase():
    row = InvitationRow(hospital='Policlinico Gemelli', physician_count=2, role='Relatore',
                        department='Cardiologia', event_name='Congresso', event_place='Roma')
    context = letter_context(row, user_name='M. Palazzo')
    assert context['ruolo'] == 'Relatori'
    assert context['fraseRepartoOspedale'] == 'del reparto di Cardiologia Policlinico Gemelli'
    assert context['termine_medico'] == 'medici'
    assert context['userName'] == 'M. Palazzo'


def test_letter_context_without_department():
    row = InvitationRow(hospital='Policlinico', physician_count=1, event_name='Corso', event_place='Roma')
    assert letter_context(row)['fraseRepartoOspedale'] == 'Policlinico'


def test_invitation_requires_at_least_one_physician():
    with pytest.raises(ValueError, match='at least one physician'):
        InvitationRow(hospital='X', physician_count=0)


# --- specialty --------------------------------------------------------------

def test_cardiology_is_detected_from_the_title():
    match = identify_specialty('Scompenso cardiaco e stenosi aortica: update')
    assert match.specialty == 'cardiovascular'
    assert match.score >= 2
    assert '#1e40af' in match.palette.rgb


def test_diabetes_is_endocrinology():
    assert identify_specialty('Diabete e insulina: nuove evidenze').specialty == 'endocrinology'


def test_unknown_text_falls_back_to_the_institutional_palette():
    match = identify_specialty('Riunione interna')
    assert match.specialty == 'multidisciplinary'
    assert match.score == 0


def test_empty_text_is_handled():
    assert identify_specialty('').specialty == 'multidisciplinary'
    assert identify_specialty(None).matched_keywords == ()


@pytest.mark.parametrize(('text', 'expected'), (
    ('Corso FAD asincrona 2026', FORMAT_FAD_ASYNC),
    ('Webinar di aggiornamento', FORMAT_WEBINAR),
    ('FAD sincrona su piattaforma', FORMAT_WEBINAR),
    ('Evento RES con questionario', FORMAT_RES_WITH_TEST),
    ('Incontro presso Hotel Excelsior', FORMAT_RES_WITH_TEST),
    ('', FORMAT_FAD_ASYNC),
))
def test_identify_event_format(text, expected):
    assert identify_event_format(text) == expected


def test_graphic_brief_is_citable():
    brief = graphic_brief('Scompenso cardiaco', event_name='Cardio Update', place='Milano')
    assert brief['specialty'] == 'cardiovascular'
    assert 'scompenso' in brief['matched_keywords']
    assert brief['rgb'][0] == '#1e40af'
    assert brief['event_name'] == 'Cardio Update'


# --- accreditation email ----------------------------------------------------

def make_request(**kwargs):
    defaults = {
        'event_name': 'Cardio Update',
        'event_date': date(2026, 9, 15),
        'place': 'Milano',
        'sponsor': 'Acme Pharma',
        'event_code': 'C123',
        'folder_name': '0915 CARDIO MILANO ACME C123',
        'recipient_email': 'ecm@example.org',
        'sender_name': 'M. Palazzo',
    }
    return AccreditationRequest(**(defaults | kwargs))


def test_subject_format():
    assert build_subject(make_request()) == 'Accreditamento ECM: Cardio Update'


def test_subject_override_wins():
    assert build_subject(make_request(subject_override='Urgente')) == 'Urgente'


def test_italian_date_format():
    assert format_date_it(date(2026, 9, 5)) == '5/9/2026'
    assert format_date_it(None) == ''


def test_body_keeps_the_wording_in_use():
    body = build_body(make_request())
    assert body.startswith('Ciao ECM,<br><br>')
    assert "Ti chiedo l'accreditamento per favore del seguente evento:" in body
    assert 'Nome Evento: <b>Cardio Update</b>' in body
    assert 'Data: 15/9/2026' in body
    assert 'Cliente (Sponsor): Acme Pharma' in body
    assert 'S:\\CONGRESSI 2026\\0915 CARDIO MILANO ACME C123' in body
    assert body.endswith('Grazie mille, M. Palazzo.')


def test_body_escapes_user_input():
    body = build_body(make_request(event_name='<script>alert(1)</script>'))
    assert '<script>' not in body
    assert '&lt;script&gt;' in body


def test_recipient_label_defaults_to_ecm():
    assert build_body(make_request(recipient_label='')).startswith('Ciao ECM,')


def test_build_email_carries_recipients():
    email = build_email(make_request(cc=('capo@example.org',)))
    assert email['to'] == 'ecm@example.org'
    assert email['cc'] == ['capo@example.org']


def test_outlook_url_is_encoded():
    url = outlook_compose_url(make_request())
    assert url.startswith('https://outlook.live.com/owa/?path=/mail/action/compose&')
    assert 'to=ecm%40example.org' in url
    assert ' ' not in url


def test_missing_fields_are_listed():
    assert missing_fields(make_request()) == []
    assert 'sponsor' in missing_fields(make_request(sponsor=''))
    assert set(missing_fields(AccreditationRequest(event_name=''))) == {
        'event_name', 'event_date', 'place', 'sponsor', 'folder_name', 'recipient_email'}
