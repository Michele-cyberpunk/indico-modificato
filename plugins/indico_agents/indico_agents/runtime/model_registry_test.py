# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_agents.runtime.model_registry import (ModelConfigError, ModelEntry, ModelKind, add,
                                                  default_for, for_kind, hosts, parse, remove,
                                                  serialise, summary, toggle, validate)


TEXT = ModelEntry(adapter='fornitore', kind=ModelKind.text, model='scrittura-1',
                  host='api.fornitore.example', note='lettere di routine')
BETTER = ModelEntry(adapter='fornitore', kind=ModelKind.text, model='scrittura-pro')
IMAGE = ModelEntry(adapter='disegno', kind=ModelKind.image, model='immagini-1',
                   host='api.disegno.example')


def test_a_round_trip_keeps_every_row():
    entries = (TEXT, BETTER, IMAGE)
    assert parse(serialise(entries)) == entries


def test_nothing_configured_is_an_empty_list_not_an_error():
    assert parse(None) == ()
    assert parse('') == ()
    assert parse('[]') == ()


@pytest.mark.parametrize('raw', ('non json', '{"non": "una lista"}', '[1, 2, 3]'))
def test_unreadable_configuration_does_not_stop_the_page(raw):
    # tolerant on read: a hand-edited setting must not take the dashboard down
    assert parse(raw) == ()


def test_a_row_with_an_unknown_kind_is_skipped_not_guessed():
    assert parse('[{"adapter": "x", "kind": "video", "model": "y"}]') == ()


def test_a_row_without_an_adapter_is_skipped():
    assert parse('[{"kind": "text", "model": "y"}]') == ()


def test_kinds_keep_prose_and_pictures_apart():
    entries = (TEXT, BETTER, IMAGE)
    assert [entry.model for entry in for_kind(entries, ModelKind.text)] == ['scrittura-1', 'scrittura-pro']
    assert [entry.model for entry in for_kind(entries, 'image')] == ['immagini-1']


def test_the_first_enabled_row_of_a_kind_is_the_default():
    entries = (TEXT, BETTER)
    assert default_for(entries, ModelKind.text).model == 'scrittura-1'


def test_disabling_the_first_promotes_the_next():
    entries = toggle((TEXT, BETTER), 0)
    assert not entries[0].enabled
    assert default_for(entries, ModelKind.text).model == 'scrittura-pro'


def test_with_no_model_of_a_kind_there_is_no_default():
    assert default_for((TEXT,), ModelKind.image) is None


def test_a_row_needs_an_installed_adapter():
    with pytest.raises(ModelConfigError, match='non è installato'):
        validate(TEXT, known_adapters={'altro'})


def test_the_refusal_lists_what_is_installed():
    with pytest.raises(ModelConfigError, match='altro'):
        validate(TEXT, known_adapters={'altro'})


def test_a_row_needs_a_model_name():
    with pytest.raises(ModelConfigError, match='quale modello'):
        validate(ModelEntry(adapter='fornitore', kind=ModelKind.text), known_adapters={'fornitore'})


def test_the_same_model_cannot_be_added_twice():
    entries = add((), TEXT, known_adapters={'fornitore'})
    with pytest.raises(ModelConfigError, match='già configurato'):
        add(entries, TEXT, known_adapters={'fornitore'})


def test_two_models_of_the_same_adapter_are_fine():
    entries = add(add((), TEXT, known_adapters={'fornitore'}), BETTER, known_adapters={'fornitore'})
    assert len(entries) == 2


def test_removing_a_row_that_is_gone_says_so_instead_of_failing_silently():
    with pytest.raises(ModelConfigError, match='non esiste più'):
        remove((TEXT,), 5)
    with pytest.raises(ModelConfigError, match='non esiste più'):
        toggle((TEXT,), -1)


def test_removing_keeps_the_others():
    assert remove((TEXT, BETTER, IMAGE), 1) == (TEXT, IMAGE)


def test_the_hosts_come_from_the_models_so_the_two_lists_cannot_drift():
    assert hosts((TEXT, IMAGE)) == (('api.fornitore.example', 'modello fornitore/scrittura-1'),
                                    ('api.disegno.example', 'modello disegno/immagini-1'))


def test_a_disabled_model_does_not_open_a_host():
    assert hosts(toggle((TEXT,), 0)) == ()


def test_summary_answers_is_anything_configured_at_a_glance():
    assert summary((TEXT, BETTER, IMAGE)) == {'text': 2, 'image': 1}
    assert summary(()) == {'text': 0, 'image': 0}


def test_a_kind_says_what_it_produces_in_the_office_s_words():
    assert ModelKind.text.label == 'testo'
    assert ModelKind.image.label == 'immagini'
