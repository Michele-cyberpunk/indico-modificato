# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""How sure we are, and why.

Recording a fact with a confidence number the author picked is not evidence: two
people mean different things by "80". This module replaces the guess with a
computation — the design of trycompai/crm's evidence scorer, reimplemented in
Python over the kinds of proof a provider actually has.

Three ideas make it work:

1. **Independent sources combine.** Two mediocre proofs are worth more than one,
   but never certainty. The combination is noisy-OR: each source removes part of
   the remaining doubt, so the score approaches 1 without reaching it.
2. **Some proofs identify a person, others only corroborate.** A tax code on the
   registration identifies; an email domain that matches the employer does not.
   `verified` is unreachable without at least one identifying source, whatever
   the arithmetic says.
3. **A disagreement caps the result.** When two sources conflict the answer is
   not an average, it is "hold, a person must look".

Pure: no Indico imports, no database, no clock.
"""

from dataclasses import dataclass
from enum import Enum


class Band(Enum):
    """What a score licenses you to do.

    The band, not the number, is what the rest of the platform reads: a number
    invites arguing about the second decimal, a band invites a decision.
    """

    verified = 'verified'
    probable = 'probable'
    possible = 'possible'


#: A source is *identifying* when, on its own, it says which person this is.
#: Everything else can only add weight to something already identified.
@dataclass(frozen=True)
class Weight:
    weight: float
    identifying: bool
    label: str


#: The proofs a provider actually has, and what each is worth.
#: Weights are deliberately coarse: the difference between 0.80 and 0.82 is not
#: knowledge, it is decoration.
WEIGHTS = {
    # --- identifying ---
    'tax_code_match': Weight(0.95, True, 'il codice fiscale coincide con quello in anagrafica'),
    'registry_confirms': Weight(0.90, True, "l'albo professionale conferma nome e numero"),
    'checked_in': Weight(0.85, True, 'ha firmato la presenza al banco'),
    'previous_certificate': Weight(0.80, True, 'gli abbiamo già rilasciato un attestato'),
    'self_declared': Weight(0.75, True, "lo ha dichiarato lui stesso nel modulo d'iscrizione"),
    'signature_block': Weight(0.75, True, 'la firma della sua email lo dice'),
    # --- corroborating ---
    'sponsor_roster': Weight(0.55, False, "compare nell'elenco mandato dallo sponsor"),
    'employer_match': Weight(0.45, False, "l'ente di appartenenza coincide"),
    'web_cited': Weight(0.40, False, 'una fonte web citata lo afferma'),
    'email_domain': Weight(0.35, False, "il dominio dell'email coincide con l'ente"),
    'name_only': Weight(0.20, False, "il nome coincide, nient'altro"),
    # --- the one that takes away ---
    'contradiction': Weight(0.0, False, "un'altra fonte dice il contrario"),
}

#: No amount of evidence produces certainty about a person.
CEILING = 0.99
#: A contradiction holds the score below the `probable` floor, whatever else says.
CONTRADICTED_CEILING = 0.45

FLOORS = {Band.verified: 0.85, Band.probable: 0.55, Band.possible: 0.30}


@dataclass(frozen=True)
class Proof:
    """One thing that was actually observed.

    `detail` is what it said, in a line a colleague can check. It is not
    optional: a proof nobody can re-read is not a proof.
    """

    kind: str
    detail: str
    source_ref: str = ''

    def __post_init__(self):
        if self.kind not in WEIGHTS:
            raise ValueError(f'tipo di prova sconosciuto: {self.kind}')
        if not self.detail.strip():
            raise ValueError('una prova senza dettaglio non è una prova')


@dataclass(frozen=True)
class Assessment:
    """The verdict on a set of proofs."""

    score: float
    band: Band | None
    identified: bool
    contradicted: bool
    rationale: str

    @property
    def confidence(self):
        """The score as the 0-100 integer the evidence ledger stores."""
        return round(self.score * 100)

    @property
    def is_writable(self):
        """Whether this may be written onto the record rather than proposed.

        Only `verified` writes. Everything else is a suggestion for a person,
        which is the whole point of having bands.
        """
        return self.band is Band.verified


def score(proofs):
    """Combine independent proofs into one verdict.

    Noisy-OR: each proof removes a share of the doubt that is left, so adding a
    weak source helps a little and adding a strong one helps a lot, and nothing
    ever reaches certainty.
    """
    proofs = tuple(proofs)
    if not proofs:
        return Assessment(0.0, None, False, False, 'Nessuna prova.')

    contradicted = any(proof.kind == 'contradiction' for proof in proofs)
    identified = any(WEIGHTS[proof.kind].identifying for proof in proofs)

    doubt = 1.0
    for proof in proofs:
        doubt *= 1 - WEIGHTS[proof.kind].weight
    value = min(CEILING, 1 - doubt)
    if contradicted:
        value = min(value, CONTRADICTED_CEILING)

    return Assessment(score=round(value, 4), band=band_for(value, identified),
                      identified=identified, contradicted=contradicted,
                      rationale=_rationale(proofs, contradicted, identified))


def band_for(value, identified):
    """The band a score earns.

    `verified` is gated on an identifying proof: ten weak sources agreeing that
    someone is a cardiologist in Milan still do not say *which* cardiologist.
    """
    if value >= FLOORS[Band.verified] and identified:
        return Band.verified
    if value >= FLOORS[Band.probable]:
        return Band.probable
    if value >= FLOORS[Band.possible]:
        return Band.possible
    return None


def _rationale(proofs, contradicted, identified):
    """One sentence a colleague can act on, built from what was seen."""
    if contradicted:
        clash = next(proof for proof in proofs if proof.kind == 'contradiction')
        return f'In sospeso: {clash.detail}'
    labels = [WEIGHTS[proof.kind].label for proof in proofs]
    listed = _join(labels)
    if not identified:
        return f'{_capitalise(listed)} — ma nulla che identifichi la persona.'
    return f'{_capitalise(listed)}.'


def _join(words):
    words = list(dict.fromkeys(words))
    if len(words) == 1:
        return words[0]
    return f'{", ".join(words[:-1])} e {words[-1]}'


def _capitalise(text):
    return text[:1].upper() + text[1:] if text else text


def explain(proofs):
    """The verdict plus the proofs behind it, ready to render or serialise."""
    verdict = score(proofs)
    return {
        'score': verdict.score,
        'confidence': verdict.confidence,
        'band': verdict.band.value if verdict.band else None,
        'identified': verdict.identified,
        'contradicted': verdict.contradicted,
        'writable': verdict.is_writable,
        'rationale': verdict.rationale,
        'proofs': [{'kind': proof.kind, 'detail': proof.detail, 'source_ref': proof.source_ref,
                    'weight': WEIGHTS[proof.kind].weight,
                    'identifying': WEIGHTS[proof.kind].identifying}
                   for proof in proofs],
    }
