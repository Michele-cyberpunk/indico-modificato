# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Medical specialty and event format detection.

Ported from `js/utils/medical-identification.js` of the Cyberbrain event
manager, where it drives the graphic brief: the specialty of an event decides
the palette the designer starts from. Keywords and colour values are kept
exactly as they are in use, so briefs produced by the platform match the ones
produced so far.

Deterministic keyword scoring, not a model: the same title always yields the
same palette, which is what a designer needs.

Pure functions, no Indico imports.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """The print colours of a specialty, as the provider specified them.

    CMYK only, on purpose. An earlier port also carried a hex triplet, but those
    values came from Tailwind's default palette rather than from the provider,
    and they named a different hue than the CMYK beside them — teal in print,
    blue on screen. There is no correct conversion without the studio's ICC
    profile, so the brief hands over the specification and the studio converts
    it.
    """

    primary: str
    secondary: str
    neutral: str
    description: str


@dataclass(frozen=True)
class SpecialtyMatch:
    specialty: str
    score: int
    palette: Palette
    matched_keywords: tuple


SPECIALTIES = {
    'cardiovascular': (
        ('cuore', 'cardiaco', 'cardiovascolare', 'scompenso', 'aritmie', 'pressione', 'vascolare',
         'coronarico', 'pacemaker', 'defibrillatore', 'heart failure', 'stenosi aortica', 'tavi', 'valve'),
        Palette('C:60 M:0 Y:30 K:0', 'C:30 M:0 Y:15 K:0', 'C:0 M:0 Y:0 K:75',
                'Teal cardiologico professionale'),
    ),
    'endocrinology': (
        ('diabete', 'ormoni', 'tiroide', 'metabolico', 'endocrino', 'insulina', 'glucosio', 'glicemia',
         'disglicemia', 'nutraceutici'),
        Palette('C:10 M:80 Y:0 K:0', 'C:5 M:30 Y:0 K:0', 'C:0 M:0 Y:0 K:70',
                'Magenta clinico metabolico'),
    ),
    'neurology': (
        ('cervello', 'neurologico', 'nervi', 'cognitivo', 'sclerosi', 'parkinson', 'alzheimer',
         'epilessia', 'neurologia'),
        Palette('C:70 M:50 Y:0 K:0', 'C:40 M:25 Y:0 K:0', 'C:0 M:0 Y:0 K:80',
                'Viola neurologico profondo'),
    ),
    'gynecology': (
        ('ginecologia', 'ostetricia', 'gyn', 'factory', 'donna', 'gravidanza', 'fertilità', 'endometriosi'),
        Palette('C:15 M:60 Y:0 K:0', 'C:5 M:30 Y:0 K:0', 'C:0 M:0 Y:0 K:70',
                'Blu-rosa ginecologico'),
    ),
    'multidisciplinary': (
        ('formazione', 'corso', 'ecm', 'multidisciplinare', 'team', 'integrato', 'approach',
         'comprehensive', '3h', 'hypertension'),
        Palette('C:55 M:0 Y:45 K:0', 'C:25 M:0 Y:20 K:0', 'C:0 M:0 Y:0 K:70',
                'Verde istituzionale medico'),
    ),
}

DEFAULT_SPECIALTY = 'multidisciplinary'


def identify_specialty(text) -> SpecialtyMatch:
    """Pick the specialty whose keywords appear most often in the text.

    Ties keep the first specialty in declaration order, and no match falls back
    to the institutional palette — same behaviour as the original.
    """
    lowered = (text or '').lower()
    best_key, best_score = DEFAULT_SPECIALTY, 0
    for key, (keywords, _palette) in SPECIALTIES.items():
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score > best_score:
            best_key, best_score = key, score
    keywords, palette = SPECIALTIES[best_key]
    matched = tuple(keyword for keyword in keywords if keyword in lowered)
    return SpecialtyMatch(specialty=best_key, score=best_score, palette=palette, matched_keywords=matched)


#: Event formats as named by the provider, in the order they are tested
FORMAT_FAD_ASYNC = 'FAD_ASINCRONA'
FORMAT_WEBINAR = 'WEBINAR'
FORMAT_RES_WITH_TEST = 'RES_CON_QUESTIONARIO'
FORMAT_FSC_WITHOUT_TEST = 'FSC_SENZA_QUESTIONARIO'
FORMAT_FSC_WITH_TEST = 'FSC_CON_QUESTIONARIO'

#: Words that imply a physical venue when nothing else matched
VENUE_HINTS = ('hotel', 'via ', 'palazzo')

#: The line a Progetto Formativo uses to declare the format, e.g. "Tipologia: RES"
DECLARED_FORMAT_RE = re.compile(
    r'(?:tipologia|modalit[àa]|tipo\s+evento|tipo\s+di\s+evento)\s*[:\-–]\s*(.+)',
    re.IGNORECASE)

#: Ordered as in the original `mapTipoEvento`, with the word boundaries it used.
_FORMAT_PATTERNS = (
    (re.compile(r'residenziale|\bres\b', re.IGNORECASE), FORMAT_RES_WITH_TEST),
    (re.compile(r'fad\s*asincron', re.IGNORECASE), FORMAT_FAD_ASYNC),
    (re.compile(r'fad\s*sincron|\bfad\b', re.IGNORECASE), FORMAT_WEBINAR),
    (re.compile(r'webinar', re.IGNORECASE), FORMAT_WEBINAR),
    (re.compile(r'questionario', re.IGNORECASE), FORMAT_FSC_WITH_TEST),
    (re.compile(r'\bfsc\b', re.IGNORECASE), FORMAT_FSC_WITHOUT_TEST),
    # "Gruppo di Miglioramento" without an explicit FSC prefix is still FSC.
    (re.compile(r'gruppo\s+di\s+migliorament', re.IGNORECASE), FORMAT_FSC_WITHOUT_TEST),
)


def _map_declared_format(value):
    """Map a declared type onto the provider's own list of formats."""
    for pattern, fmt in _FORMAT_PATTERNS:
        if pattern.search(value or ''):
            return fmt
    return ''


def identify_event_format(text):
    """Detect the ECM format of an event from its description.

    The declared line wins: a Progetto Formativo writes "Tipologia: RES", and
    reading that is more reliable than scanning a whole document where any
    mention of a questionnaire or a venue would count.

    Two things this deliberately does *not* do, both of them regressions found
    by running it on real texts:

    * It matches `res` on a word boundary. As a substring it fires on
      `Responsabile` and on `Congresso`, so nearly every Italian programme came
      back as residential.
    * It returns an empty string when nothing establishes the format, instead of
      assuming distance learning. The format goes into the shared-drive folder
      name, and a wrong one files a residential event under `FAD-ASINCRONA`;
      unknown means the folder is named after the city, which is what the
      office already does.
    """
    text = text or ''
    declared = DECLARED_FORMAT_RE.search(text)
    if declared:
        fmt = _map_declared_format(declared.group(1))
        if fmt:
            return fmt
    fmt = _map_declared_format(text)
    if fmt:
        return fmt
    if any(hint in text.lower() for hint in VENUE_HINTS):
        return FORMAT_RES_WITH_TEST
    return ''


#: Mapping to the platform's own enum, kept here so the legacy names stay in one place
FORMAT_TO_ACTIVITY_FORMAT = {
    FORMAT_FAD_ASYNC: 'fad_async',
    FORMAT_WEBINAR: 'fad_sync',
    FORMAT_RES_WITH_TEST: 'residential',
    FORMAT_FSC_WITHOUT_TEST: 'fieldwork',
    FORMAT_FSC_WITH_TEST: 'fieldwork',
    '': None,
}


def graphic_brief(text, *, event_name='', place='', date_text=''):
    """The brief a designer receives when an event needs its graphics.

    Deterministic and citable: it says which words produced the palette, so a
    designer can disagree with the classification instead of guessing.
    """
    match = identify_specialty(text)
    return {
        'event_name': event_name,
        'place': place,
        'date': date_text,
        'specialty': match.specialty,
        'palette_description': match.palette.description,
        'cmyk': {'primary': match.palette.primary, 'secondary': match.palette.secondary,
                 'neutral': match.palette.neutral},
        'matched_keywords': list(match.matched_keywords),
        'format': identify_event_format(text),
    }
