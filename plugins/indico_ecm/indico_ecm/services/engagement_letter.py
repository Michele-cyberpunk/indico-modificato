# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The engagement letter a speaker signs.

Ported from `src/lib/word/incarico.ts` of the Cyberbrain event manager. The
letter is a legal document naming a person, a role and a fee, so the wording
rules are reproduced rather than reinterpreted: the salutation matrix, the
Italian spelling of the amount, and the 20% withholding are exactly the
originals.

Two of those rules exist because getting them wrong is worse than leaving the
field empty:

* An unknown gender never produces `Dott.`. That abbreviation is the masculine
  short form, not a neutral one, so using it on a woman misgenders her. Without
  a signal the letter falls back to the company form `Spett.le`.
* `Dott.` written in front of a name only proves the masculine when the same
  document declines titles elsewhere (it writes `Dott.ssa` for someone). In a
  document that never declines, `Dott.` is generic and the gender stays unknown.

Pure functions, no Indico imports.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


#: Withholding tax applied to the fee of a speaker who has a VAT number.
WITHHOLDING_RATE = Decimal('0.20')

MONTHS_IT = ('Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
             'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre')

#: The titles the letter offers, in the neutral form; `gender` decides how they read.
TITLE_CHOICES = (('none', 'Nessuno'), ('doctor', 'Dottore/a'), ('professor', 'Professore/ssa'))

#: Title prefixes recognised in front of a name, with the neutral title they map
#: to and the gender the written form implies. An empty gender means the form is
#: ambiguous: `Dott.`, `Prof.` and `Dr.` are also written for women in documents
#: that do not decline titles, so on their own they prove nothing.
_TITLE_PREFIXES = (
    # The feminine forms come first: otherwise the ambiguous prefix matches and
    # leaves a stray "ssa" glued to the name.
    (re.compile(r'^(?:dott\.?ssa|dr\.?ssa|dottoressa)\b\.?\s*', re.IGNORECASE), 'doctor', 'F'),
    (re.compile(r'^(?:prof\.?ssa|professoressa)\b\.?\s*', re.IGNORECASE), 'professor', 'F'),
    (re.compile(r'^dottore\b\.?\s*', re.IGNORECASE), 'doctor', 'M'),
    (re.compile(r'^professore\b\.?\s*', re.IGNORECASE), 'professor', 'M'),
    (re.compile(r'^(?:dott|dr)\b\.?\s*', re.IGNORECASE), 'doctor', ''),
    (re.compile(r'^prof\b\.?\s*', re.IGNORECASE), 'professor', ''),
    (re.compile(r'^(?:sig\.?ra|mrs|ms)\b\.?\s*', re.IGNORECASE), 'none', 'F'),
    (re.compile(r'^(?:sig|mr)\b\.?\s*', re.IGNORECASE), 'none', 'M'),
    (re.compile(r'^ing\b\.?\s*', re.IGNORECASE), 'none', ''),
)

_DECLINED_TITLE = re.compile(
    r'\b(?:dott\.?ssa|dr\.?ssa|prof\.?ssa|dottoressa|professoressa|sig\.?ra)\b', re.IGNORECASE)

_UNITS = ('Zero', 'Uno', 'Due', 'Tre', 'Quattro', 'Cinque', 'Sei', 'Sette', 'Otto', 'Nove',
          'Dieci', 'Undici', 'Dodici', 'Tredici', 'Quattordici', 'Quindici', 'Sedici',
          'Diciassette', 'Diciotto', 'Diciannove')
_TENS = ('', '', 'Venti', 'Trenta', 'Quaranta', 'Cinquanta', 'Sessanta', 'Settanta',
         'Ottanta', 'Novanta')


def title_abbreviation(title, gender):
    """The abbreviated title, declined.

    An unknown gender returns the empty string on purpose: the caller then
    writes the full name instead of guessing a form.
    """
    if not gender:
        return ''
    if title == 'doctor':
        return 'Dott.ssa' if gender == 'F' else 'Dott.'
    if title == 'professor':
        return 'Prof.ssa' if gender == 'F' else 'Prof.'
    return ''


def split_title(raw):
    """Separate a title from a name.

    `Dott.ssa Laura Rossi` becomes `('Laura Rossi', 'doctor', 'F')`. Without a
    recognised prefix the name comes back untouched, with no title and no gender.
    """
    text = (raw or '').strip()
    for pattern, title, gender in _TITLE_PREFIXES:
        if pattern.match(text):
            return pattern.sub('', text).strip(), title, gender
    return text, 'none', ''


def declines_titles(text):
    """Whether the document writes at least one explicitly feminine title.

    If it does, whoever wrote it declines titles, and a `Dott.` elsewhere in the
    same document counts as masculine.
    """
    return bool(_DECLINED_TITLE.search(text or ''))


def gender_from_title(title, gender, document_declines):
    """The gender the title in front of a name establishes, if any."""
    if gender:
        return gender
    if title in ('none', ''):
        return ''
    return 'M' if document_declines else ''


def gender_from_tax_code(tax_code):
    """The gender an Italian tax code encodes.

    Characters 10-11 hold the day of birth: 01-31 for men, 41-71 for women.
    """
    text = re.sub(r'\s', '', tax_code or '').upper()
    if len(text) < 11:
        return ''
    try:
        day = int(text[9:11])
    except ValueError:
        return ''
    return 'F' if day > 40 else 'M'


def salutation(gender, title):
    """The opening of the letter. An unknown gender gets the company form."""
    if not gender:
        return 'Spett.le'
    if title == 'doctor':
        return 'Egregio Dottore' if gender == 'M' else 'Gentile Dottoressa'
    if title == 'professor':
        return 'Gentile Professore' if gender == 'M' else 'Gentilissima Professoressa'
    return 'Egregio' if gender == 'M' else 'Gentile'


def letter_date(day=None):
    """`date(2026, 12, 4)` becomes `04 Dicembre 2026`. Defaults to today."""
    day = day or date.today()
    return f'{day.day:02d} {MONTHS_IT[day.month - 1]} {day.year}'


def _hundreds_in_words(value):
    if value <= 0:
        return ''
    if value < 20:
        return _UNITS[value].lower()
    hundreds, rest = divmod(value, 100)
    out = ''
    if hundreds:
        out += 'cento' if hundreds == 1 else _UNITS[hundreds].lower() + 'cento'
    if rest:
        if rest < 20:
            out += _UNITS[rest].lower()
        else:
            tens, unit = divmod(rest, 10)
            word = _TENS[tens]
            if unit in (1, 8):
                # Elision: Ventuno, Ventotto.
                word = word[:-1]
            out += word.lower() + (_UNITS[unit].lower() if unit else '')
    return out


def _integer_in_words(value):
    if value == 0:
        return 'Zero'
    if value < 0 or value > 999999:
        return str(value)
    thousands, rest = divmod(value, 1000)
    out = ''
    if thousands:
        out += 'Mille' if thousands == 1 else _hundreds_in_words(thousands) + 'mila'
    if rest:
        out += _hundreds_in_words(rest)
    return out[:1].upper() + out[1:].lower()


def parse_amount(value):
    """Read an amount written as a number or in Italian notation (`1.234,50`)."""
    if value is None or not str(value).strip():
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace('.', '').replace(',', '.')
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal(0)


def format_amount(value):
    """`Decimal('800')` becomes `800,00`."""
    quantized = Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return f'{quantized:.2f}'.replace('.', ',')


def amount_in_words(value):
    """`800` becomes `Ottocento,00`: the units in words, the cents in figures."""
    if value is None or not str(value).strip():
        return ''
    amount = parse_amount(value)
    whole = int(abs(amount))
    cents = int((abs(amount) - whole).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) * 100)
    return f'{_integer_in_words(whole)},{cents:02d}'


@dataclass(frozen=True)
class EngagementFigures:
    """The values the letter template needs that are not typed in by hand."""

    salutation: str
    fee: str
    fee_in_words: str
    withholding: str
    net_total: str
    has_fee: bool
    letter_date: str
    year: str


def derive(*, gender='', title='none', salutation_override='', fee=None,
           letter_day=None, event_date=''):
    """Everything the template fills in from the answers given in the dialog."""
    opening = (salutation_override or '').strip() or salutation(gender, title)

    amount = parse_amount(fee)
    has_fee = amount > 0
    withheld = (amount * WITHHOLDING_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    year_match = re.search(r'\d{4}', event_date or '')
    year = year_match.group(0) if year_match else str(date.today().year)

    return EngagementFigures(
        salutation=opening,
        fee=format_amount(amount) if has_fee else '',
        fee_in_words=amount_in_words(amount) if has_fee else '',
        withholding=format_amount(withheld) if has_fee else '',
        net_total=format_amount(amount - withheld) if has_fee else '',
        has_fee=has_fee,
        letter_date=letter_date(letter_day),
        year=year,
    )
