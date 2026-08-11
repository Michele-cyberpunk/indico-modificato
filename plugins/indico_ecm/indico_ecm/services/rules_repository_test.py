# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

import json
from decimal import Decimal

from indico_ecm.services.credit_rules import CreditsMode, Rounding, RuleSet
from indico_ecm.services.rules_repository import dump_ruleset, load_ruleset


def test_roundtrip_preserves_every_field():
    rules = RuleSet(version='2026.1-lombardia', min_attendance_ratio=Decimal('0.9'),
                    assessment_required=True, assessment_pass_ratio=Decimal('0.75'), survey_required=True,
                    credits_mode=CreditsMode.per_hour, accredited_credits=Decimal('12.5'),
                    credits_per_hour=Decimal('1.5'), rounding=Rounding.half_nearest, max_credits=Decimal(50),
                    accredited_professions=frozenset({'Medico chirurgo', 'Infermiere'}),
                    accredited_disciplines=frozenset({'Cardiologia'}), require_verified_profile=True,
                    require_confirmed_registration=True, require_settled_payment=True, region='Lombardia',
                    notes='regole di prova')
    assert load_ruleset(dump_ruleset(rules)) == rules


def test_dump_is_json_serializable():
    rules = RuleSet(version='2026.1', accredited_credits=Decimal(9))
    assert json.loads(json.dumps(dump_ruleset(rules)))['accredited_credits'] == '9'


def test_decimals_never_become_floats():
    rules = RuleSet(version='2026.1', min_attendance_ratio=Decimal('0.9'), accredited_credits=Decimal('0.1'))
    dumped = dump_ruleset(rules)
    assert isinstance(dumped['min_attendance_ratio'], str)
    assert load_ruleset(dumped).accredited_credits == Decimal('0.1')


def test_missing_keys_fall_back_to_defaults():
    rules = load_ruleset({'version': '2026.0'})
    assert rules.min_attendance_ratio == Decimal('0.9')
    assert rules.credits_mode is CreditsMode.fixed
    assert rules.max_credits is None


def test_unknown_keys_are_ignored():
    rules = load_ruleset({'version': '2026.0', 'something_new': 42})
    assert rules.version == '2026.0'


def test_null_max_credits_survives_the_roundtrip():
    rules = RuleSet(version='2026.0', max_credits=None)
    assert load_ruleset(dump_ruleset(rules)).max_credits is None
