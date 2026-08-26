# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The evidence ledger.

Statements are appended, never edited: recording a new statement about the same
attribute supersedes the previous one and keeps it readable. This is what makes
an agent's output reviewable months later.
"""

from indico.core.db import db

from indico_crm.models.evidence import Evidence, EvidenceKind
from indico_crm.models.links import CRMObjectType
from indico_crm.services.confidence import Proof, score


def record_assessed_fact(subject_type: CRMObjectType, subject_id: int, statement: str, *,
                         proofs, kind: EvidenceKind, attribute: str = '', source_ref: str = '',
                         user=None, agent_run_id=None):
    """Record a statement whose confidence is *computed* from its proofs.

    Prefer this over `record_fact`: a confidence somebody typed means whatever
    they meant by it, while a score derived from named proofs can be re-derived,
    argued with, and compared across records. The verdict — score, band and the
    sentence explaining it — is stored alongside the proofs it came from.

    Returns `(evidence, assessment)`. The assessment says whether the value may
    be written onto the record (`verified`) or only offered as a suggestion.
    """
    proofs = [item if isinstance(item, Proof) else Proof(**item) for item in proofs]
    if not proofs:
        raise ValueError('una valutazione senza prove non è una valutazione')
    assessment = score(proofs)
    evidence = record_fact(
        subject_type, subject_id, statement, kind=kind, attribute=attribute,
        source_ref=source_ref, confidence=assessment.confidence, user=user, agent_run_id=agent_run_id,
    )
    evidence.band = assessment.band.value if assessment.band else ''
    evidence.rationale = assessment.rationale
    evidence.proofs = [{'kind': proof.kind, 'detail': proof.detail, 'source_ref': proof.source_ref}
                       for proof in proofs]
    db.session.flush()
    return evidence, assessment


def record_fact(subject_type: CRMObjectType, subject_id: int, statement: str, *, kind: EvidenceKind,
                attribute: str = '', source_ref: str = '', confidence: int = 50, user=None, agent_run_id=None):
    """Record a statement about a CRM record.

    Either `user` or `agent_run_id` must be given: an unattributed fact is not
    evidence.
    """
    if user is None and agent_run_id is None:
        raise ValueError('evidence must have an author (user or agent run)')
    if not 0 <= confidence <= 100:
        raise ValueError('confidence must be between 0 and 100')
    if not statement.strip():
        raise ValueError('evidence must have a statement')

    evidence = Evidence(
        subject_type=subject_type,
        subject_id=subject_id,
        statement=statement.strip(),
        attribute=attribute,
        kind=kind,
        source_ref=source_ref,
        confidence=confidence,
        recorded_by=user,
        agent_run_id=agent_run_id,
    )
    if attribute:
        _supersede_previous(subject_type, subject_id, attribute, evidence)
    db.session.add(evidence)
    db.session.flush()
    return evidence


def _supersede_previous(subject_type, subject_id, attribute, evidence):
    previous = (Evidence.query
                .filter_by(subject_type=subject_type, subject_id=subject_id, attribute=attribute,
                           superseded_by_id=None)
                .all())
    for entry in previous:
        entry.superseded_by = evidence


def current_evidence(subject_type: CRMObjectType, subject_id: int, attribute: str | None = None):
    """Return the statements currently in force about a record."""
    query = Evidence.query.filter_by(subject_type=subject_type, subject_id=subject_id, superseded_by_id=None)
    if attribute is not None:
        query = query.filter_by(attribute=attribute)
    return query.order_by(Evidence.created_dt.desc()).all()


def evidence_trail(subject_type: CRMObjectType, subject_id: int, attribute: str):
    """Return every statement ever made about an attribute, newest first."""
    return (Evidence.query
            .filter_by(subject_type=subject_type, subject_id=subject_id, attribute=attribute)
            .order_by(Evidence.created_dt.desc())
            .all())
