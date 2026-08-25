# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import email
import email.policy

import pytest

from indico_ecm.services.mail_draft import build_eml, content_type_for, draft_filename, from_message


def parse(blob):
    # The modern policy: without it the legacy Message has no `get_content`.
    return email.message_from_bytes(blob, policy=email.policy.default)


def parts_of(message):
    return [(part.get_content_type(), part.get_filename())
            for part in message.walk() if part.get_content_maintype() != 'multipart']


def test_the_draft_carries_the_headers():
    message = parse(build_eml(to='hotel@example.com', subject='Preventivo',
                              html_body='<p>Buongiorno</p>', sender='segreteria@ecm.local'))
    assert message['To'] == 'hotel@example.com'
    assert message['Subject'] == 'Preventivo'
    assert message['From'] == 'segreteria@ecm.local'


def test_it_is_marked_as_a_draft():
    # X-Unsent is what tells a mail client to open it for editing, not to file it.
    assert parse(build_eml(subject='X'))['X-Unsent'] == '1'


@pytest.mark.parametrize('written', ('a@x.it, b@x.it', 'a@x.it; b@x.it', ' a@x.it ;b@x.it '))
def test_recipients_are_split_the_way_people_write_them(written):
    assert parse(build_eml(to=written))['To'] == 'a@x.it, b@x.it'


def test_the_html_body_travels_with_a_plain_text_twin():
    message = parse(build_eml(subject='X', html_body='<p>Prima riga</p><p>Seconda riga</p>'))
    types = [content_type for content_type, _ in parts_of(message)]
    assert 'text/plain' in types
    assert 'text/html' in types


def test_the_plain_text_twin_is_readable():
    message = parse(build_eml(subject='X', html_body='<p>Gentile Dott.ssa,</p><p>l&#39;evento</p>'))
    plain = next(part for part in message.walk() if part.get_content_type() == 'text/plain')
    text = plain.get_content()
    assert 'Gentile Dott.ssa,' in text
    assert "l'evento" in text
    assert '<p>' not in text


def test_an_attachment_keeps_its_name_and_its_type():
    blob = build_eml(subject='Incarico', html_body='<p>In allegato</p>',
                     attachments=[('Lettera di incarico Rossi Mario.docx', b'PK\x03\x04finto')])
    message = parse(blob)
    types = dict((name, content_type) for content_type, name in parts_of(message) if name)
    assert types['Lettera di incarico Rossi Mario.docx'] == (
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document')


def test_more_than_one_attachment_travels():
    blob = build_eml(subject='X', attachments=[('a.pdf', b'%PDF'), ('b.xlsx', b'PK')])
    names = [name for _, name in parts_of(parse(blob)) if name]
    assert names == ['a.pdf', 'b.xlsx']


@pytest.mark.parametrize(('filename', 'expected'), (
    ('lettera.docx', ('application', 'vnd.openxmlformats-officedocument.wordprocessingml.document')),
    ('report.xlsx', ('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')),
    ('attestato.pdf', ('application', 'pdf')),
    ('cartella.zip', ('application', 'zip')),
    ('ignoto.qqq', ('application', 'octet-stream')),
))
def test_the_type_comes_from_the_extension(filename, expected):
    assert content_type_for(filename) == expected


def test_the_file_is_named_after_the_subject():
    assert draft_filename('Richiesta Hostess: Cardio Update') == 'Richiesta Hostess Cardio Update.eml'


def test_a_subject_that_cannot_be_a_file_name_still_produces_one():
    assert draft_filename('') == 'bozza.eml'
    assert '/' not in draft_filename('a/b\\c')


def test_a_rendered_message_becomes_a_draft():
    name, blob = from_message({'subject': 'Preventivo', 'body': '<p>Buongiorno</p>'},
                              to='hotel@example.com')
    assert name == 'Preventivo.eml'
    assert parse(blob)['To'] == 'hotel@example.com'
