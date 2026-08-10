# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Deterministic identity matching for CRM records.

Pure logic, no Indico or database imports, so it can be tested on its own and
called from both the web layer and the agent tools. The matching threshold is
deliberately stricter than a generic CRM would use: these records end up on
certificates, so a wrong merge is a regulatory problem, not a data quality one.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum


class MatchDecision(Enum):
    """What may be done with a candidate pair."""

    #: Same person beyond doubt: safe to merge automatically
    strong = 'strong'
    #: Very likely the same person: a human (or an approval) must confirm
    probable = 'probable'
    #: Worth showing to a human, never acted upon
    weak = 'weak'
    #: Not the same person
    none = 'none'
    #: Identifiers actively contradict each other: merging is forbidden
    conflict = 'conflict'


#: Decisions an automated actor is allowed to apply without human confirmation
AUTO_APPLICABLE = frozenset({MatchDecision.strong})


@dataclass(frozen=True)
class MatchResult:
    decision: MatchDecision
    reason: str
    matched_on: tuple[str, ...] = ()

    @property
    def can_auto_merge(self):
        return self.decision in AUTO_APPLICABLE


@dataclass(frozen=True)
class IdentityCandidate:
    """The identifying attributes of a person, as known by one record."""

    first_name: str = ''
    last_name: str = ''
    email: str = ''
    tax_code: str = ''
    registry_board: str = ''
    registry_region: str = ''
    registry_number: str = ''
    company_id: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def registry_key(self):
        if not self.registry_number:
            return None
        return (normalize_text(self.registry_board), normalize_text(self.registry_region),
                normalize_code(self.registry_number))


def normalize_text(value):
    """Casefold, strip accents and collapse whitespace."""
    if not value:
        return ''
    decomposed = unicodedata.normalize('NFKD', value)
    without_accents = ''.join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', without_accents).strip().casefold()


def normalize_code(value):
    """Normalize an identifier: uppercase, alphanumeric only."""
    if not value:
        return ''
    return re.sub(r'[^A-Z0-9]', '', value.upper())


def normalize_email(value):
    if not value:
        return ''
    return value.strip().casefold()


def is_valid_tax_code(value):
    """Check the shape of an Italian codice fiscale.

    Only the format is validated here; the check character is intentionally not
    verified, because non-resident professionals may hold codes issued in other
    formats and we must not reject them silently.
    """
    return bool(re.fullmatch(r'[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]', normalize_code(value)))


def same_person_name(left: IdentityCandidate, right: IdentityCandidate):
    return (normalize_text(left.last_name) == normalize_text(right.last_name)
            and normalize_text(left.first_name) == normalize_text(right.first_name)
            and bool(normalize_text(left.last_name)))


def match_identity(left: IdentityCandidate, right: IdentityCandidate) -> MatchResult:
    """Compare two candidates and state what may be done with the pair."""
    left_tax = normalize_code(left.tax_code)
    right_tax = normalize_code(right.tax_code)
    if left_tax and right_tax:
        if left_tax == right_tax:
            return MatchResult(MatchDecision.strong, 'identical tax code', ('tax_code',))
        return MatchResult(MatchDecision.conflict, 'different tax codes', ('tax_code',))

    left_registry = left.registry_key
    right_registry = right.registry_key
    if left_registry and right_registry:
        if left_registry == right_registry:
            return MatchResult(MatchDecision.strong, 'identical professional registry entry', ('registry',))
        if same_person_name(left, right):
            return MatchResult(MatchDecision.conflict, 'same name but different registry entries', ('registry',))
        return MatchResult(MatchDecision.none, 'different registry entries', ('registry',))

    left_email = normalize_email(left.email)
    right_email = normalize_email(right.email)
    if left_email and left_email == right_email:
        if same_person_name(left, right):
            return MatchResult(MatchDecision.probable, 'same email and same name', ('email', 'name'))
        return MatchResult(MatchDecision.weak, 'same email but names differ', ('email',))

    if same_person_name(left, right):
        if left.company_id is not None and left.company_id == right.company_id:
            return MatchResult(MatchDecision.weak, 'same name and same organization', ('name', 'company'))
        return MatchResult(MatchDecision.weak, 'same name only', ('name',))

    return MatchResult(MatchDecision.none, 'no shared identifier')


def match_healthcare_professional(left: IdentityCandidate, right: IdentityCandidate) -> MatchResult:
    """Match two healthcare professionals.

    Same as `match_identity`, minus the shortcuts: without a tax code or a
    registry entry no pair is ever strong, because an HCP record is what a
    certificate is issued against.
    """
    result = match_identity(left, right)
    if result.decision is MatchDecision.strong and result.matched_on[0] in ('tax_code', 'registry'):
        return result
    if result.decision is MatchDecision.strong:
        return MatchResult(MatchDecision.probable, 'strong match without a regulatory identifier',
                           result.matched_on)
    return result
