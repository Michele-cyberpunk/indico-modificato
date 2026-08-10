# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_ecm.services.templates import (DOCUMENT_TEMPLATES, MESSAGE_TEMPLATES, TemplateError, get_template,
                                           placeholders, render, render_named)


def test_every_template_declares_resolvable_placeholders():
    for name, template in MESSAGE_TEMPLATES.items():
        known = set(template.required) | set(template.defaults)
        used = set(placeholders(template.subject)) | set(placeholders(template.body))
        assert used <= known, f'{name}: segnaposto non dichiarati {sorted(used - known)}'


def test_every_template_has_a_version_and_a_description():
    for name, template in MESSAGE_TEMPLATES.items():
        assert template.version, name
        assert template.description, name


def test_render_fills_subject_and_body():
    result = render_named('task_update', {'recipient': 'Grafica Srl', 'event_name': 'Cardio Update',
                                          'task': 'Grafica', 'event_date': '15/9/2026', 'place': 'Milano',
                                          'sender_name': 'M. Palazzo'})
    assert result['subject'] == 'Aggiornamento: Grafica - Cardio Update'
    assert '<strong>Task completato:</strong> Grafica' in result['body']
    assert result['body'].endswith('<p>Cordiali saluti,<br>M. Palazzo</p>')
    assert result['template'] == 'task_update'
    assert result['version'] == '1'


def test_defaults_are_applied():
    result = render_named('task_update', {'recipient': 'X', 'event_name': 'Y', 'task': 'Z'})
    assert '<strong>Data evento:</strong> N/D' in result['body']


def test_missing_required_value_raises():
    with pytest.raises(TemplateError, match='valori mancanti'):
        render_named('task_update', {'recipient': 'X', 'event_name': 'Y'})


def test_empty_required_value_is_treated_as_missing():
    with pytest.raises(TemplateError, match='task'):
        render_named('task_update', {'recipient': 'X', 'event_name': 'Y', 'task': ''})


def test_values_are_escaped_in_html_bodies():
    result = render_named('task_update', {'recipient': '<b>Ospedale</b>', 'event_name': 'Y', 'task': 'Z'})
    assert '&lt;b&gt;Ospedale&lt;/b&gt;' in result['body']
    assert '<b>Ospedale</b>' not in result['body']


def test_subject_is_not_escaped_because_it_is_not_html():
    result = render_named('task_update', {'recipient': 'X', 'event_name': 'Cuore & Ritmo', 'task': 'Z'})
    assert 'Cuore & Ritmo' in result['subject']


def test_accreditation_template_keeps_the_historical_wording():
    result = render_named('accreditation_request', {
        'event_name': 'Cardio Update', 'event_date': '15/9/2026', 'place': 'Milano',
        'sponsor': 'Acme Pharma', 'event_code': 'C123', 'folder_path': 'S:\\CONGRESSI 2026\\X',
        'sender_name': 'M. Palazzo'})
    assert result['body'].startswith('Ciao ECM,<br><br>')
    assert "Ti chiedo l'accreditamento per favore del seguente evento:" in result['body']
    assert result['body'].endswith('Grazie mille, M. Palazzo.')


def test_certificate_template_reports_credits_and_number():
    result = render_named('certificate_ready', {'recipient': 'Dott. Rossi', 'event_name': 'Cardio Update',
                                                'credits': '9', 'certificate_number': 'ECM-2026-000431'})
    assert 'ECM-2026-000431' in result['body']
    assert '<strong>Crediti assegnati:</strong> 9' in result['body']


def test_graphic_brief_template_carries_the_palette():
    result = render_named('graphic_brief', {'event_name': 'Cardio Update', 'specialty': 'cardiovascular',
                                            'rgb': '#1e40af', 'keywords': 'scompenso'})
    assert 'cardiovascular' in result['body']
    assert '#1e40af' in result['body']


def test_unknown_template_raises():
    with pytest.raises(TemplateError, match='sconosciuto'):
        render_named('non_esiste', {})


def test_unknown_placeholder_in_context_is_ignored():
    result = render_named('reminder_due', {'task': 'Chiamare hotel', 'event_name': 'Cardio', 'foo': 'bar'})
    assert 'Chiamare hotel' in result['body']


def test_template_can_be_rendered_without_escaping_when_the_body_is_plain_text():
    template = get_template('reminder_due')
    result = render(template, {'task': 'A & B', 'event_name': 'C'}, escape=False)
    assert 'A & B' in result['body']


def test_document_templates_declare_their_context():
    assert DOCUMENT_TEMPLATES['invitation_letter']['path'].endswith('.docx')
    assert 'nomeOspedale' in DOCUMENT_TEMPLATES['invitation_letter']['context']
