# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico_agents.governance.capabilities import (CAPABILITIES, Capability, describe, is_enabled,
                                                   unavailable)


class _Settings:
    """The plugin settings object, reduced to what this module reads."""

    def __init__(self, values=None, broken=False):
        self.values = values or {}
        self.broken = broken

    def get(self, key):
        if self.broken:
            raise RuntimeError('impostazioni non leggibili')
        return self.values.get(key)


def test_nothing_configured_means_nothing_enabled():
    from indico_agents.governance.capabilities import current

    assert all(not enabled for _capability, enabled in current(_Settings()))


def test_a_configured_provider_is_enabled():
    settings = _Settings({'registry_provider': 'albo-x'})
    assert is_enabled('registry_provider', settings)
    assert not is_enabled('research_provider', settings)


def test_a_blank_setting_is_not_configured():
    assert not is_enabled('registry_provider', _Settings({'registry_provider': '   '}))


def test_unreadable_settings_mean_off_not_crash():
    from indico_agents.governance.capabilities import current

    assert all(not enabled for _capability, enabled in current(_Settings(broken=True)))


def test_unavailable_tells_the_agent_not_to_retry():
    answer = unavailable('registry_provider')
    assert answer['configured'] is False
    assert 'riprovare non serve' in answer['reason']
    assert 'Albo professionale' in answer['reason']


def test_unavailable_still_answers_for_an_unknown_setting():
    assert unavailable('qualcosa_altro')['configured'] is False


def test_with_no_sources_the_prose_points_back_at_our_own_records():
    text = describe([(capability, False) for capability in CAPABILITIES])
    assert 'Nessuna fonte esterna è configurata' in text
    assert 'iscrizioni, presenze, attestati emessi' in text


def test_the_prose_separates_what_is_on_from_what_is_off():
    pairs = [(CAPABILITIES[0], True)] + [(capability, False) for capability in CAPABILITIES[1:]]
    text = describe(pairs)
    assert 'Disponibili:' in text
    assert CAPABILITIES[0].label in text.split('Non configurate qui')[0]
    assert 'non pianificare di usarle' in text


def test_with_everything_on_there_is_no_missing_section():
    text = describe([(capability, True) for capability in CAPABILITIES])
    assert 'Non configurate qui' not in text


def test_the_registry_describes_what_each_source_adds():
    assert all(capability.gives and capability.label for capability in CAPABILITIES)
    assert isinstance(CAPABILITIES[0], Capability)
