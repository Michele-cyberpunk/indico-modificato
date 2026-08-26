# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import pytest

from indico_agents.runtime.egress import DENY_ALL, EgressDenied, build


ALLOWED = build([('api.fornitore.example', 'research_provider'),
                 ('https://albo.example/v1/', 'registry_provider'),
                 ('', 'vuoto')])


def test_nothing_configured_denies_everything():
    assert not DENY_ALL.allows('https://api.fornitore.example/x')


def test_a_configured_host_is_reachable():
    assert ALLOWED.check('https://api.fornitore.example/lookup') == 'api.fornitore.example'


def test_a_full_url_in_the_configuration_is_reduced_to_its_host():
    assert ALLOWED.allows('https://albo.example/v1/medici')


def test_a_blank_entry_is_ignored_rather_than_allowing_everything():
    assert '' not in ALLOWED.hosts


def test_an_unconfigured_host_is_refused_by_name():
    with pytest.raises(EgressDenied, match=r'altro\.example'):
        ALLOWED.check('https://altro.example/x')


def test_the_refusal_says_who_can_fix_it():
    with pytest.raises(EgressDenied, match='amministratore'):
        ALLOWED.check('https://altro.example/x')


@pytest.mark.parametrize('url', (
    'https://169.254.169.254/latest/meta-data/',
    'https://metadata.google.internal/computeMetadata/v1/',
    'https://localhost/admin',
    'https://127.0.0.1:8000/',
    'https://10.0.0.5/internal',
    'https://192.168.1.1/',
    'https://172.16.0.1/',
))
def test_internal_addresses_are_never_reachable(url):
    # even if somebody configures them, which is the point of the fixed list
    reckless = build([('169.254.169.254', 'x'), ('localhost', 'x'), ('127.0.0.1', 'x'),
                      ('10.0.0.5', 'x'), ('192.168.1.1', 'x'), ('172.16.0.1', 'x'),
                      ('metadata.google.internal', 'x')])
    with pytest.raises(EgressDenied):
        reckless.check(url)


def test_only_https_leaves_the_building():
    plain = build([('api.fornitore.example', 'research_provider')])
    with pytest.raises(EgressDenied, match='solo https'):
        plain.check('http://api.fornitore.example/x')


def test_an_address_without_a_host_is_refused():
    with pytest.raises(EgressDenied, match='senza host'):
        ALLOWED.check('https:///percorso')


def test_the_allowlist_says_why_a_host_is_there():
    assert ALLOWED.why('api.fornitore.example') == 'research_provider'
    assert ALLOWED.why('API.FORNITORE.EXAMPLE') == 'research_provider'
    assert ALLOWED.why('sconosciuto.example') == ''


def test_a_hostname_that_merely_looks_private_is_judged_by_the_list():
    # names are not resolved to decide: resolution can change between the check
    # and the call, so names are controlled by the allowlist instead
    named = build([('interno.example', 'research_provider')])
    assert named.allows('https://interno.example/x')
