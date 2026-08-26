# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""What this install can actually reach.

An agent that plans around a source nobody configured wastes a run and then
reports a failure that is not one. The fix is not a better prompt: it is to tell
the agent, up front and in prose, which outside sources exist here — and to have
the tools for the missing ones answer "not configured, retrying will not help"
rather than raising.

The design is `lib/capabilities.ts` of trycompai/crm, reimplemented over the
plugin's settings. Two audiences read the same registry: the agent, as the
markdown block in its context, and the office, as a table in the dashboard.

Pure except for `current()`, which reads the plugin settings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    """One outside source, and what having it lets you know."""

    #: Plugin setting that switches it on
    setting: str
    label: str
    #: What it adds that nothing else here can supply
    gives: str
    #: Where an admin turns it on
    where: str = 'Impostazioni del plugin agenti'


#: Everything this platform would use if it were configured. The list is short
#: on purpose: a provider's questions are mostly answered by its own records.
CAPABILITIES = (
    Capability(
        setting='registry_provider',
        label='Albo professionale',
        gives=("la conferma di professione, disciplina e numero d'iscrizione: l'unica fonte che "
               "identifica un professionista sanitario senza chiederglielo"),
    ),
    Capability(
        setting='research_provider',
        label='Anagrafiche aziendali e ricerca',
        gives=('partita IVA, sede e settore di uno sponsor a partire dal dominio, e contesto con '
               'citazioni verificabili: utile per corroborare, mai per identificare una persona'),
    ),
)

CAPABILITIES = (*CAPABILITIES, Capability(
    setting='model_provider',
    label='Modello linguistico',
    gives=('la prosa di una lettera o di un brief a partire dai dati che la piattaforma ha già. '
           'Non decide mai un valore regolato: crediti, minuti e numeri di attestato restano del '
           'motore deterministico, e una bozza che li afferma viene rifiutata'),
))

CAPABILITIES_BY_SETTING = {capability.setting: capability for capability in CAPABILITIES}


def current(settings=None):
    """Which capabilities are configured, as `(capability, enabled)` pairs.

    `settings` is the plugin's settings object; passing it explicitly keeps this
    testable and keeps the import of the plugin out of module scope.
    """
    if settings is None:
        from indico_agents.plugin import AgentsPlugin
        settings = AgentsPlugin.settings
    pairs = []
    for capability in CAPABILITIES:
        try:
            value = settings.get(capability.setting)
        except Exception:  # an unreadable setting is "off", not a crash
            value = None
        pairs.append((capability, bool(value and str(value).strip())))
    return tuple(pairs)


def is_enabled(setting, settings=None):
    return any(capability.setting == setting and enabled
               for capability, enabled in current(settings))


def unavailable(setting):
    """The answer a tool gives when its source is not configured here.

    Shaped so the agent stops rather than retries: this is a property of the
    install, and no amount of trying again changes it.
    """
    capability = CAPABILITIES_BY_SETTING.get(setting)
    label = capability.label if capability else setting
    return {
        'configured': False,
        'ok': False,
        'capability': setting,
        'reason': (f'Questo impianto non ha «{label}» configurato, quindi quella fonte non è '
                   'disponibile. Non è un errore e riprovare non serve: usa ciò che la '
                   'piattaforma già sa e dichiara nel tuo resoconto ciò che non hai potuto '
                   'verificare.'),
    }


def describe(pairs):
    """The registry as prose for the agent's context.

    Written as instructions rather than a table because it is read by something
    that acts on it: it says what to do when a source is missing, not merely
    that it is.
    """
    on = [capability for capability, enabled in pairs if enabled]
    off = [capability for capability, enabled in pairs if not enabled]
    lines = ['## Cosa puoi usare qui', '']

    if not on:
        lines += [
            'Nessuna fonte esterna è configurata su questo impianto. Tutto ciò che puoi',
            'sapere è già nella piattaforma: iscrizioni, presenze, attestati emessi,',
            'elenchi mandati dagli sponsor. Spesso basta a stabilire chi è una persona.',
            'Registra ciò che risulta e lascia vuoto il resto.',
        ]
        return '\n'.join(lines)

    lines.append('Disponibili:')
    lines += [f'- **{capability.label}** — {capability.gives}.' for capability in on]
    if off:
        lines += ['', 'Non configurate qui, quindi non pianificare di usarle:']
        lines += [f'- {capability.label}' for capability in off]
        lines += ['', 'I loro strumenti ti risponderanno la stessa cosa se li chiami. Annota ciò',
                  'che non hai potuto verificare invece di indovinarlo.']
    return '\n'.join(lines)


def markdown(settings=None):
    return describe(current(settings))
