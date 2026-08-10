# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Issuing, verifying and revoking ECM certificates.

The PDF is produced by Indico's receipts module; this service owns the parts
that make a certificate a regulatory document rather than a nice printout:
gapless numbering, a verifiable hash, an opaque public token and a revocation
trail.
"""

import hashlib
import secrets

from sqlalchemy.dialects.postgresql import insert

from indico.core.db import db
from indico.util.date_time import now_utc

from indico_ecm.models.certificates import Certificate, CertificateSequence, CertificateState
from indico_ecm.models.credits import AssignmentState


class CertificateError(Exception):
    pass


def next_number(provider, year):
    """Allocate the next certificate number for a provider and year.

    The counter is a row, incremented with an upsert that returns the new value:
    two batches running at the same time get two different numbers, and the
    sequence has no gaps. (`max(number) FOR UPDATE` cannot be used — PostgreSQL
    rejects row locking on an aggregate.)
    """
    prefix = provider.settings.get('certificate_prefix') or 'ECM'
    table = CertificateSequence.__table__
    statement = (insert(table)
                 .values(provider_id=provider.id, year=year, last_number=1)
                 .on_conflict_do_update(index_elements=['provider_id', 'year'],
                                        set_={'last_number': table.c.last_number + 1})
                 .returning(table.c.last_number))
    sequence = db.session.execute(statement).scalar()
    return f'{prefix}-{year}-{sequence:06d}'


def prepare_certificate(assignment, *, provider, agent_run_id=None):
    """Create a draft certificate for an approved assignment.

    This is the furthest an automated actor may go: a draft carries a number and
    a token but is not a certificate until a person issues it.
    """
    if assignment.state != AssignmentState.approved:
        raise CertificateError('a certificate requires an approved credit assignment')
    existing = (Certificate.query
                .filter(Certificate.assignment_id == assignment.id,
                        Certificate.state.in_([CertificateState.draft, CertificateState.issued]))
                .first())
    if existing is not None:
        return existing
    certificate = Certificate(
        assignment=assignment,
        number=next_number(provider, assignment.approved_dt.year),
        state=CertificateState.draft,
        verification_token=secrets.token_urlsafe(24),
    )
    db.session.add(certificate)
    db.session.flush()
    return certificate


def issue_certificate(certificate, *, user, file_content=None, receipt_file=None):
    """Mark a certificate as issued. Requires a person."""
    if user is None:
        raise CertificateError('a certificate can only be issued by a person')
    if certificate.state != CertificateState.draft:
        raise CertificateError('only a draft certificate can be issued')
    if certificate.assignment.state != AssignmentState.approved:
        raise CertificateError('the underlying credit assignment is no longer approved')
    if file_content is not None:
        certificate.content_hash = hashlib.sha256(file_content).hexdigest()
    if receipt_file is not None:
        certificate.receipt_file_id = receipt_file.id
    certificate.state = CertificateState.issued
    certificate.issued_dt = now_utc()
    certificate.issued_by = user
    db.session.flush()
    return certificate


def revoke_certificate(certificate, *, user, reason):
    if user is None:
        raise CertificateError('a certificate can only be revoked by a person')
    if not reason or not reason.strip():
        raise CertificateError('revoking a certificate requires a written reason')
    certificate.state = CertificateState.revoked
    certificate.revoked_dt = now_utc()
    certificate.revoked_reason = reason.strip()
    db.session.flush()
    return certificate


def replace_certificate(certificate, *, user, reason, provider):
    """Supersede a certificate with a corrected one.

    Used when the underlying data was wrong: the old document stays in the
    record marked as superseded, because it may already be in someone's hands.
    """
    revoke_reason = f'Sostituito: {reason}'
    certificate.state = CertificateState.superseded
    certificate.revoked_dt = now_utc()
    certificate.revoked_reason = revoke_reason
    replacement = Certificate(
        assignment=certificate.assignment,
        number=next_number(provider, now_utc().year),
        state=CertificateState.draft,
        verification_token=secrets.token_urlsafe(24),
        supersedes_id=certificate.id,
    )
    db.session.add(replacement)
    db.session.flush()
    return replacement


def verify(token):
    """Resolve a public verification token.

    Returns only what a verification page may show: never the participant's
    identifiers, only the certificate state and what it attests.
    """
    certificate = Certificate.query.filter_by(verification_token=token).first()
    if certificate is None:
        return None
    assignment = certificate.assignment
    return {
        'number': certificate.number,
        'state': certificate.state.name,
        'issued_dt': certificate.issued_dt.isoformat() if certificate.issued_dt else None,
        'credits': str(assignment.credits),
        'event_id': assignment.event_id,
        'activity_code': assignment.accreditation.activity_code,
        'rule_version': assignment.rule_version,
        'valid': certificate.is_valid and assignment.state == AssignmentState.approved,
    }
