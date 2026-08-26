# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Calling a language model, when there is one.

The platform is deliberately deterministic: credits, dates, event codes, folder
names and identity all come from rules, and that does not change. What a model
can do here is narrower and real — write the paragraph a person would otherwise
write from the same facts.

So this runtime exists, and everything around it is a constraint:

- **Nothing is configured by default.** With no provider the call returns
  "unavailable" in the same shape the capability registry uses, so an agent
  stops instead of retrying, and an install that never wants a model never has
  one.
- **It is never on the HTTP path.** Only an agent run may call it, and a run is
  something the queue started.
- **The answer is guarded.** `governance.llm_guard` refuses prose that states a
  credit figure or a certificate number. Regulated values are read, not written.
- **It costs something, and the something is capped.** Every call records its
  tokens and cost on the run, and the per-event ceiling in the plugin settings
  is enforced before the call, not after the bill.
- **It can only reach where it was allowed.** The provider's host must be on the
  egress allowlist.

Providers are registered, not imported: an adapter for a specific vendor lives
outside this module and can be absent without breaking anything.
"""

from dataclasses import dataclass, field


class LLMUnavailable(Exception):
    """No model is configured, or the one configured may not be used here."""


class LLMRefused(Exception):
    """A model was available but the call was not allowed to happen."""


@dataclass(frozen=True)
class Prompt:
    """What is asked, versioned so an answer can be explained later."""

    system: str
    user: str
    #: Name and hash of the instruction, recorded on the run
    version: str = ''
    max_tokens: int = 800
    #: Low by default: this writes documents, it does not brainstorm
    temperature: float = 0.2

    def fingerprint(self):
        import hashlib

        return hashlib.sha256(f'{self.system}\n{self.user}'.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Completion:
    """What came back, and what it cost."""

    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_cents: int = 0
    provider: str = ''

    @property
    def tokens(self):
        return self.tokens_in + self.tokens_out


#: name -> callable(settings) -> provider. A provider is anything with
#: `complete(prompt) -> Completion`, `name`, and `host`.
_PROVIDERS = {}


def register_provider(name, factory):
    """Make a vendor adapter available under a settings name."""
    _PROVIDERS[name] = factory
    return factory


def available_providers():
    return tuple(sorted(_PROVIDERS))


@dataclass
class Usage:
    """What one run has spent so far."""

    tokens: int = 0
    cost_cents: int = 0
    calls: int = 0
    by_prompt: dict = field(default_factory=dict)

    def add(self, completion, prompt_version=''):
        self.tokens += completion.tokens
        self.cost_cents += completion.cost_cents
        self.calls += 1
        key = prompt_version or 'senza versione'
        self.by_prompt[key] = self.by_prompt.get(key, 0) + 1


def configured_models(settings):
    """The rows the Models page saved."""
    from indico_agents.runtime import model_registry

    return model_registry.parse(settings.get('model_providers'))


def resolve(settings, kind='text', allowlist=None):
    """The model this install would use for work of `kind`.

    Reads the same rows the Models page writes — there is one place a model is
    configured, and a screen that wrote somewhere the runtime never looked would
    be worse than no screen at all.

    Raises `LLMUnavailable` rather than returning None: every caller has to deal
    with the absence, and an exception is harder to forget than a null.
    """
    from indico_agents.runtime import model_registry
    from indico_agents.runtime.egress import EgressDenied, build

    entries = configured_models(settings)
    entry = model_registry.default_for(entries, kind)
    if entry is None:
        label = model_registry.ModelKind(kind).label
        raise LLMUnavailable(
            f'Nessun modello per {label} è configurato e attivo su questo impianto. Non è un '
            'errore e riprovare non serve: scrivi il testo dai dati che hai, oppure lascia il '
            'campo alla persona.')
    factory = _PROVIDERS.get(entry.adapter)
    if factory is None:
        raise LLMUnavailable(
            f'Il modello «{entry.label}» è configurato ma il suo adapter non è installato. '
            f'Disponibili: {", ".join(available_providers()) or "nessuno"}.')
    provider = factory(settings)
    host = entry.host or getattr(provider, 'host', '')
    if host:
        # the models' own hosts are always allowed: they were configured on the
        # same page, and requiring them twice only produces a call that fails last
        reachable = allowlist if allowlist is not None else build(model_registry.hosts(entries))
        try:
            reachable.check(f'https://{host}')
        except EgressDenied as exc:
            raise LLMUnavailable(f'il modello «{entry.label}» non è raggiungibile: {exc}') from exc
    return provider


def complete(prompt, *, settings, kind='text', run=None, usage=None, allowlist=None,
             ceiling_cents=None, spent_cents=0, guard=True):
    """Ask the model, under every constraint that applies.

    The order is the point: refuse before spending, spend before trusting, and
    guard the answer before anyone reads it.
    """
    from indico_agents.governance import llm_guard

    if ceiling_cents:
        if spent_cents >= ceiling_cents:
            raise LLMRefused(
                f'Tetto di spesa per questo evento raggiunto ({spent_cents}/{ceiling_cents} '
                'centesimi). Scrivi il testo dai dati che hai, oppure chiedi a una persona.')

    provider = resolve(settings, kind=kind, allowlist=allowlist)
    completion = provider.complete(prompt)

    if usage is not None:
        usage.add(completion, prompt_version=prompt.version)
    if run is not None:
        run.model_name = completion.model or getattr(provider, 'name', '')
        run.tokens_used = (run.tokens_used or 0) + completion.tokens
        run.cost_cents = (run.cost_cents or 0) + completion.cost_cents

    if guard:
        llm_guard.check_prose(completion.text)
    return completion


def unavailable_result(exc):
    """The absence, in the shape the rest of the platform already speaks."""
    return {'configured': False, 'ok': False, 'reason': str(exc)}
