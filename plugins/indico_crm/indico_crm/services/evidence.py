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
