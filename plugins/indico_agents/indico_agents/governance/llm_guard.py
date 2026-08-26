# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""What a language model is never allowed to have decided.

The platform's central promise is that a regulated value — the credits on an
attestato, the minutes of attendance behind them, the number on the certificate
— comes from a deterministic engine that can be re-run and argued with. A model
that writes those numbers into prose breaks the promise even when the prose is
never saved, because somebody reads it and believes it.

So model output passes through here before anything is done with it, and this
module refuses rather than repairs. Quietly stripping a credit figure out of a
paragraph would leave a sentence that no longer says what its author meant, and
would hide that the model had gone somewhere it should not: the refusal is the
useful outcome, because it sends the draft back with the reason.

Pure: no Indico imports, no database, no model.
"""

import re
from dataclasses import dataclass


#: Structured fields a model may never supply. These are the values that end up
#: on a document a professional relies on, and every one of them has an engine
#: or a register that owns it.
FORBIDDEN_FIELDS = frozenset({
    'credits', 'crediti', 'credit_count',
    'attended_minutes', 'minuti', 'minuti_presenza',
    'certificate_number', 'numero_attestato',
    'eligible', 'idoneo', 'esito',
    'tax_code', 'codice_fiscale',
    'registry_number', 'numero_albo',
    'rule_version', 'versione_regole',
})

#: Prose that asserts a regulated figure. Deliberately broad: a false positive
#: costs a regenerated paragraph, a false negative costs a wrong attestato.
CLAIM_PATTERNS = (
    (re.compile(r'\b\d+(?:[.,]\d+)?\s*credit[oi]\b', re.IGNORECASE),
     'dichiara un numero di crediti'),
    (re.compile(r'\bcredit[oi]\s*(?:ECM\s*)?[:=]\s*\d', re.IGNORECASE),
     'dichiara un numero di crediti'),
    (re.compile(r'\b(?:attestato|certificat[oi])\s+n(?:\.|umero)\s*\S+', re.IGNORECASE),
     'inventa un numero di attestato'),
    (re.compile(r'\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b'),
     'contiene un codice fiscale'),
    (re.compile(r'\b(?:ha\s+)?(?:maturato|conseguito|acquisito)\s+\d+', re.IGNORECASE),
     'attribuisce crediti a una persona'),
    (re.compile(r'\b(?:è|risulta)\s+(?:idone[oa]|avente\s+diritto)\b', re.IGNORECASE),
     'pronuncia un giudizio di idoneità'),
)


class ForbiddenClaim(Exception):
    """Model output asserted something only the platform may decide."""


@dataclass(frozen=True)
class Finding:
    """One thing the model said that it must not say."""

    what: str
    excerpt: str


def find_claims(text):
    """Every regulated assertion in a piece of prose."""
    text = text or ''
    findings = []
    seen = set()
    for pattern, what in CLAIM_PATTERNS:
        match = pattern.search(text)
        if match and what not in seen:
            seen.add(what)
            findings.append(Finding(what=what, excerpt=match.group(0).strip()))
    return tuple(findings)


def check_prose(text):
    """Raise unless this paragraph is safe to show to a person.

    The message is written for whoever reads the run: it names what the model
    did and quotes the words, so the fix is obvious without opening the log.
    """
    findings = find_claims(text)
    if findings:
        detail = '; '.join(f'{finding.what} («{finding.excerpt}»)' for finding in findings)
        raise ForbiddenClaim(
            f'La bozza è stata rifiutata perché {detail}. Questi valori li stabilisce il motore '
            'deterministico e li approva una persona: il testo deve rimandare al dato, non '
            'affermarlo.')
    return text


def check_fields(payload):
    """Raise if a structured answer carries a field the model may not decide."""
    if not isinstance(payload, dict):
        return payload
    offending = sorted(set(payload) & FORBIDDEN_FIELDS)
    if offending:
        raise ForbiddenClaim(
            f'La risposta contiene campi che un modello non può determinare: {", ".join(offending)}. '
            'Vanno letti dalla piattaforma, non generati.')
    return payload


def check(payload):
    """Both checks, for an answer that carries prose and fields together."""
    if isinstance(payload, str):
        return check_prose(payload)
    check_fields(payload)
    for value in payload.values():
        if isinstance(value, str):
            check_prose(value)
    return payload
