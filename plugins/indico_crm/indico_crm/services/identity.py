# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Database-aware identity resolution.

The decision logic lives in `identity_rules`; this module only feeds it with
candidates from the database and applies the outcome.
"""

from sqlalchemy import func

from indico.core.db import db

from indico_crm.models.contacts import Contact, ContactSource
from indico_crm.models.hcp_profiles import HCPProfile
from indico_crm.services.identity_rules import (IdentityCandidate, MatchDecision, match_healthcare_professional,
                                                match_identity, normalize_code, normalize_email)


def candidate_from_contact(contact):
    profile = contact.hcp_profile
    return IdentityCandidate(
        first_name=contact.first_name,
        last_name=contact.last_name,
        email=contact.email,
        tax_code=(profile.tax_code if profile else ''),
        registry_board=(profile.registry_board if profile else ''),
        registry_region=(profile.registry_region if profile else ''),
        registry_number=(profile.registry_number if profile else ''),
        company_id=contact.company_id,
    )


def _lookup_query(candidate):
    """Narrow the search space before running the expensive comparison."""
    filters = []
    if email := normalize_email(candidate.email):
        filters.append(func.lower(Contact.email) == email)
    if last_name := candidate.last_name.strip():
        filters.append(func.lower(Contact.last_name) == last_name.casefold())
    if tax_code := normalize_code(candidate.tax_code):
        filters.append(Contact.id.in_(
            db.session.query(HCPProfile.contact_id).filter(func.upper(HCPProfile.tax_code) == tax_code)
        ))
    if not filters:
        return None
    return Contact.query.filter(~Contact.is_deleted, db.or_(*filters))


def find_matches(candidate, *, healthcare=False, limit=20):
    """Return `(contact, MatchResult)` pairs ordered by decision strength.

    Nothing is written: the caller decides what to do with each outcome, which
    is what keeps automated actors from silently merging records.
    """
    query = _lookup_query(candidate)
    if query is None:
        return []
    matcher = match_healthcare_professional if healthcare else match_identity
    order = {MatchDecision.strong: 0, MatchDecision.probable: 1, MatchDecision.conflict: 2,
             MatchDecision.weak: 3, MatchDecision.none: 4}
    results = [(contact, matcher(candidate, candidate_from_contact(contact)))
               for contact in query.limit(limit)]
    results = [(contact, result) for contact, result in results if result.decision is not MatchDecision.none]
    results.sort(key=lambda pair: order[pair[1].decision])
    return results


def resolve_or_propose(candidate, *, healthcare=False, source=ContactSource.manual):
    """Resolve a candidate to an existing contact, or describe what to do next.

    Returns `(contact, result)` where `contact` is set only when the match is
    strong enough to be applied automatically. Everything else comes back
    unresolved on purpose: a probable match becomes an approval, a conflict
    becomes a task for a human, and no match becomes a proposal to create a
    record — never a silent insert for healthcare professionals.
    """
    matches = find_matches(candidate, healthcare=healthcare)
    if matches and matches[0][1].can_auto_merge:
        return matches[0]
    return None, (matches[0][1] if matches else None)


def create_contact(candidate, *, source=ContactSource.manual, company_id=None):
    """Create a contact from a candidate.

    Deliberately not called by `resolve_or_propose`: creating a record is an
    explicit decision, taken by a human or by an approved agent proposal.
    """
    contact = Contact(
        first_name=candidate.first_name.strip(),
        last_name=candidate.last_name.strip(),
        email=normalize_email(candidate.email),
        company_id=company_id if company_id is not None else candidate.company_id,
        source=source,
    )
    db.session.add(contact)
    db.session.flush()
    return contact
