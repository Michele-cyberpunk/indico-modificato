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

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    primary: str
    secondary: str
    neutral: str
    rgb: tuple
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
                ('#1e40af', '#3b82f6', '#60a5fa'), 'Teal cardiologico professionale'),
    ),
    'endocrinology': (
        ('diabete', 'ormoni', 'tiroide', 'metabolico', 'endocrino', 'insulina', 'glucosio', 'glicemia',
         'disglicemia', 'nutraceutici'),
        Palette('C:10 M:80 Y:0 K:0', 'C:5 M:30 Y:0 K:0', 'C:0 M:0 Y:0 K:70',
                ('#be185d', '#ec4899', '#f472b6'), 'Magenta clinico metabolico'),
    ),
    'neurology': (
        ('cervello', 'neurologico', 'nervi', 'cognitivo', 'sclerosi', 'parkinson', 'alzheimer',
         'epilessia', 'neurologia'),
        Palette('C:70 M:50 Y:0 K:0', 'C:40 M:25 Y:0 K:0', 'C:0 M:0 Y:0 K:80',
                ('#6b21a8', '#8b5cf6', '#a78bfa'), 'Viola neurologico profondo'),
    ),
    'gynecology': (
        ('ginecologia', 'ostetricia', 'gyn', 'factory', 'donna', 'gravidanza', 'fertilità', 'endometriosi'),
        Palette('C:15 M:60 Y:0 K:0', 'C:5 M:30 Y:0 K:0', 'C:0 M:0 Y:0 K:70',
                ('#1e3a8a', '#ec4899', '#f472b6'), 'Blu-rosa ginecologico'),
    ),
    'multidisciplinary': (
        ('formazione', 'corso', 'ecm', 'multidisciplinare', 'team', 'integrato', 'approach',
         'comprehensive', '3h', 'hypertension'),
        Palette('C:55 M:0 Y:45 K:0', 'C:25 M:0 Y:20 K:0', 'C:0 M:0 Y:0 K:70',
                ('#059669', '#10b981', '#34d399'), 'Verde istituzionale medico'),
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

#: Words that imply a physical venue when nothing else matched
VENUE_HINTS = ('hotel', 'via ', 'palazzo')


def identify_event_format(text):
    """Detect the ECM format of an event from its description.

    Order matters and is preserved from the original, including the fallback:
    a text that mentions a venue is residential, everything else is
    asynchronous distance learning.
    """
    lowered = (text or '').lower()
    if not lowered:
        return FORMAT_FAD_ASYNC
    if 'fad asincrona' in lowered or ('fad' in lowered and 'asincrona' in lowered):
        return FORMAT_FAD_ASYNC
    if 'webinar' in lowered or 'fad sincrona' in lowered:
        return FORMAT_WEBINAR
    if 'res' in lowered or ('presenza' in lowered and 'questionario' in lowered):
        return FORMAT_RES_WITH_TEST
    if 'fsc' in lowered and 'questionario' not in lowered:
        return FORMAT_FSC_WITHOUT_TEST
    if any(hint in lowered for hint in VENUE_HINTS):
        return FORMAT_RES_WITH_TEST
    return FORMAT_FAD_ASYNC


#: Mapping to the platform's own enum, kept here so the legacy names stay in one place
FORMAT_TO_ACTIVITY_FORMAT = {
    FORMAT_FAD_ASYNC: 'fad_async',
    FORMAT_WEBINAR: 'fad_sync',
    FORMAT_RES_WITH_TEST: 'residential',
    FORMAT_FSC_WITHOUT_TEST: 'fieldwork',
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
        'rgb': list(match.palette.rgb),
        'matched_keywords': list(match.matched_keywords),
        'format': identify_event_format(text),
    }
