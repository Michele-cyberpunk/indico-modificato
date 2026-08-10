# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Storage and retrieval of credit rule versions.

The (de)serialization is pure so it can be tested and used offline; the two
database helpers import their models lazily to keep it that way.
"""

from dataclasses import replace
from decimal import Decimal

from indico_ecm.services.credit_rules import CreditsMode, Rounding, RuleSet


def dump_ruleset(rules: RuleSet) -> dict:
    """Serialize a rule set to plain JSON-compatible data.

    Decimals become strings on purpose: a rule set stored as a float would make
    a credit threshold depend on binary rounding.
    """
    return {
        'version': rules.version,
        'min_attendance_ratio': str(rules.min_attendance_ratio),
        'assessment_required': rules.assessment_required,
        'assessment_pass_ratio': str(rules.assessment_pass_ratio),
        'survey_required': rules.survey_required,
        'credits_mode': rules.credits_mode.value,
        'accredited_credits': str(rules.accredited_credits),
        'credits_per_hour': str(rules.credits_per_hour),
        'rounding': rules.rounding.value,
        'max_credits': (str(rules.max_credits) if rules.max_credits is not None else None),
        'accredited_professions': sorted(rules.accredited_professions),
        'accredited_disciplines': sorted(rules.accredited_disciplines),
        'require_verified_profile': rules.require_verified_profile,
        'require_confirmed_registration': rules.require_confirmed_registration,
        'require_settled_payment': rules.require_settled_payment,
        'region': rules.region,
        'notes': rules.notes,
    }


def load_ruleset(data: dict) -> RuleSet:
    """Rebuild a rule set from stored data.

    Unknown keys are ignored and missing ones fall back to the dataclass
    defaults, so a rule set written by an older version of the code still loads.
    """
    return RuleSet(
        version=data['version'],
        min_attendance_ratio=Decimal(data.get('min_attendance_ratio', '0.9')),
        assessment_required=data.get('assessment_required', True),
        assessment_pass_ratio=Decimal(data.get('assessment_pass_ratio', '0.75')),
        survey_required=data.get('survey_required', True),
        credits_mode=CreditsMode(data.get('credits_mode', CreditsMode.fixed.value)),
        accredited_credits=Decimal(data.get('accredited_credits', '0')),
        credits_per_hour=Decimal(data.get('credits_per_hour', '1')),
        rounding=Rounding(data.get('rounding', Rounding.exact.value)),
        max_credits=(Decimal(data['max_credits']) if data.get('max_credits') is not None else None),
        accredited_professions=frozenset(data.get('accredited_professions', ())),
        accredited_disciplines=frozenset(data.get('accredited_disciplines', ())),
        require_verified_profile=data.get('require_verified_profile', True),
        require_confirmed_registration=data.get('require_confirmed_registration', True),
        require_settled_payment=data.get('require_settled_payment', False),
        region=data.get('region', ''),
        notes=data.get('notes', ''),
    )


def get_ruleset(version: str) -> RuleSet:
    """Load the stored rule set with the given version."""
    from indico_ecm.models.credits import CreditRuleVersion
    row = CreditRuleVersion.query.filter_by(version=version).one()
    return load_ruleset(row.payload)


def get_ruleset_for_accreditation(accreditation) -> RuleSet:
    """Load the rule set an accreditation was granted under.

    An accreditation always pins a version: evaluating a past event with
    today's rules would silently rewrite history.
    """
    if not accreditation.rule_version:
        raise ValueError(f'accreditation {accreditation.id} has no pinned rule version')
    rules = get_ruleset(accreditation.rule_version)
    if accreditation.credits and not rules.accredited_credits:
        # the dossier is the authority on how many credits the activity grants
        rules = replace(rules, accredited_credits=Decimal(str(accreditation.credits)))
    return rules
