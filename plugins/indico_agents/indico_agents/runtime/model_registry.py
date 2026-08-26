# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Which models this install has, and what each is for.

One text box holding one provider name was enough while there was one model.
It stops being enough as soon as the office wants a cheap model for routine
drafts and a better one for a letter that goes to a hospital director — or a
model that writes and a different one that draws.

So a model is a row, not a setting: adapter, kind, model name, and whether it is
on. Kind is what makes the list usable rather than a pile — a tool that needs
prose asks for a text model and cannot accidentally be handed an image one.

Stored as JSON under a single plugin setting, because the alternative is a
settings form that grows a field every time a supplier is added.

Pure: no Indico imports, no database.
"""

import json
from dataclasses import dataclass
from enum import Enum


class ModelKind(Enum):
    """What a model produces."""

    text = 'text'
    image = 'image'

    @property
    def label(self):
        return {'text': 'testo', 'image': 'immagini'}[self.value]


class ModelConfigError(ValueError):
    """A row that cannot be saved, with a reason meant for the person saving it."""


@dataclass(frozen=True)
class ModelEntry:
    """One configured model."""

    #: The installed adapter this row uses
    adapter: str
    kind: ModelKind
    #: The vendor's own name for the model, e.g. a version string
    model: str = ''
    #: Where the adapter connects; must also be on the egress allowlist
    host: str = ''
    enabled: bool = True
    #: What the office uses it for, in their words
    note: str = ''

    def as_dict(self):
        return {'adapter': self.adapter, 'kind': self.kind.value, 'model': self.model,
                'host': self.host, 'enabled': self.enabled, 'note': self.note}

    @property
    def label(self):
        return f'{self.adapter}/{self.model}' if self.model else self.adapter


def parse(raw):
    """Read the stored configuration, ignoring rows that make no sense.

    Tolerant on read and strict on write: a row that a future version wrote, or
    that somebody hand-edited, must not stop the dashboard from rendering.
    """
    if not raw:
        return ()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return ()
    if not isinstance(raw, list):
        return ()
    entries = []
    for row in raw:
        if not isinstance(row, dict) or not (row.get('adapter') or '').strip():
            continue
        try:
            kind = ModelKind(row.get('kind', 'text'))
        except ValueError:
            continue
        entries.append(ModelEntry(
            adapter=row['adapter'].strip(), kind=kind, model=(row.get('model') or '').strip(),
            host=(row.get('host') or '').strip().lower(), enabled=bool(row.get('enabled', True)),
            note=(row.get('note') or '').strip()))
    return tuple(entries)


def serialise(entries):
    return json.dumps([entry.as_dict() for entry in entries], ensure_ascii=False)


def validate(entry, *, known_adapters, existing=()):
    """Raise unless this row can be saved.

    Each message names the thing to change, because the person reading it is in
    a form and wants to fix it, not to understand the model.
    """
    if not entry.adapter:
        raise ModelConfigError('Scegli un adapter: senza, la riga non sa chi chiamare.')
    if known_adapters and entry.adapter not in known_adapters:
        available = ', '.join(sorted(known_adapters)) or 'nessuno'
        raise ModelConfigError(
            f"L'adapter «{entry.adapter}» non è installato su questo impianto. Disponibili: {available}.")
    if not entry.model:
        raise ModelConfigError('Indica quale modello del fornitore usare: il nome esatto, come lo chiama lui.')
    if any(other.adapter == entry.adapter and other.model == entry.model for other in existing):
        raise ModelConfigError(f'«{entry.label}» è già configurato: modifica la riga esistente.')
    return entry


def add(entries, entry, *, known_adapters=()):
    validate(entry, known_adapters=known_adapters, existing=entries)
    return (*entries, entry)


def remove(entries, index):
    entries = tuple(entries)
    if not 0 <= index < len(entries):
        raise ModelConfigError('Quella riga non esiste più: ricarica la pagina.')
    return entries[:index] + entries[index + 1:]


def toggle(entries, index):
    entries = list(entries)
    if not 0 <= index < len(entries):
        raise ModelConfigError('Quella riga non esiste più: ricarica la pagina.')
    current = entries[index]
    entries[index] = ModelEntry(adapter=current.adapter, kind=current.kind, model=current.model,
                                host=current.host, enabled=not current.enabled, note=current.note)
    return tuple(entries)


def for_kind(entries, kind):
    """The enabled models of one kind, in the order they were configured.

    Order is the preference: the first enabled row of a kind is the default, and
    reordering is how the office changes its mind without deleting anything.
    """
    kind = kind if isinstance(kind, ModelKind) else ModelKind(kind)
    return tuple(entry for entry in entries if entry.kind is kind and entry.enabled)


def default_for(entries, kind):
    """The model a tool gets when it does not ask for a particular one."""
    candidates = for_kind(entries, kind)
    return candidates[0] if candidates else None


def hosts(entries):
    """`(host, reason)` pairs for the egress allowlist.

    A model that is configured but whose host was never allowed out is a call
    that will be refused at the last moment; deriving the pairs from here means
    the two lists cannot drift.
    """
    return tuple((entry.host, f'modello {entry.label}') for entry in entries
                 if entry.enabled and entry.host)


def summary(entries):
    """Counts for the dashboard, so "is anything configured?" is one glance."""
    return {kind.value: len(for_kind(entries, kind)) for kind in ModelKind}
