# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Communication tools.

`draft_email` is the only way an agent can reach a person outside the
organization, and it does not send: it files a proposal for the approval queue,
which a person applies. There is no tool that sends directly, at any autonomy
level.
"""

from indico.core.db import db

from indico_agents.governance.approvals import request_approval
from indico_agents.tools.base import tool


@tool('draft_email', description="Prepara un'email come proposta da approvare. Non invia.")
def draft_email(context, template, to, subject_context=None, subject_type='registration',
                subject_id=None, rationale='', cc=None, event_id=None):
    from indico_ecm.services.templates import TemplateError, get_template, render_named

    try:
        get_template(template)
    except TemplateError as exc:
        return {'error': str(exc)}
    payload = dict(subject_context or {})
    payload.setdefault('recipient', to)
    try:
        preview = render_named(template, payload)
    except TemplateError as exc:
        return {'error': str(exc), 'missing_context': True}

    approval = request_approval(
        action='send_email',
        subject_type=subject_type,
        subject_id=subject_id if subject_id is not None else 0,
        event_id=event_id if event_id is not None else context.event_id,
        run=context.run,
        rationale=rationale or f'Invio del messaggio "{template}" a {to}.',
        proposed_change={'template': template, 'to': to, 'cc': list(cc or ()), 'context': payload},
    )
    return {'approval_id': approval.id, 'subject': preview['subject'], 'sent': False}


@tool('write_prose', costly=True,
      description=('Fa scrivere a un modello il testo di una lettera o di un brief dai dati che la '
                   'piattaforma ha già. Rifiuta le bozze che affermano crediti o numeri di attestato.'))
def write_prose(context, purpose, facts, tone='formale', event_id=None):
    """Draft a paragraph, when a model is configured.

    The facts are supplied by the caller and come from the platform: the model
    is asked to write them up, not to find them. Anything it says that only the
    deterministic engine may say sends the draft back with the reason.
    """
    from indico_agents.governance import llm_guard
    from indico_agents.plugin import AgentsPlugin
    from indico_agents.runtime import llm
    from indico_agents.runtime.egress import build

    settings = AgentsPlugin.settings
    from indico_agents.runtime import model_registry

    # a model's own host is authorised by the page that configured it; the free
    # text field adds anything else this install may reach
    allowlist = build([*model_registry.hosts(llm.configured_models(settings)),
                       *((host, 'egress_allowlist')
                         for host in (settings.get('egress_allowlist') or '').split(','))])
    prompt = llm.Prompt(
        system=(f'Scrivi in italiano, in tono {tone}, per la segreteria di un provider ECM. '
                'Usa soltanto i fatti che ti vengono dati. Non dichiarare mai crediti, minuti di '
                'presenza, numeri di attestato o giudizi di idoneità: quei valori li stabilisce la '
                'piattaforma, e il testo deve rimandarvi senza affermarli.'),
        user=f'Scopo: {purpose}\n\nFatti:\n{facts}',
        version='write_prose-v1')
    try:
        completion = llm.complete(prompt, settings=settings, run=context.run, allowlist=allowlist,
                                  ceiling_cents=settings.get('max_cost_cents_per_event') or 0,
                                  spent_cents=_spent_on_event(event_id or context.event_id))
    except llm.LLMUnavailable as exc:
        return llm.unavailable_result(exc)
    except llm.LLMRefused as exc:
        return {'ok': False, 'over_budget': True, 'reason': str(exc)}
    except llm_guard.ForbiddenClaim as exc:
        return {'ok': False, 'rejected': True, 'reason': str(exc)}
    return {'ok': True, 'text': completion.text, 'model': completion.model,
            'tokens': completion.tokens, 'cost_cents': completion.cost_cents,
            'note': 'bozza per una persona: nessun valore regolato è stato generato'}


def _spent_on_event(event_id):
    """What the agents have already spent on this event, in cents."""
    if not event_id:
        return 0
    from indico_agents.models.runs import AgentRun
    from indico_agents.models.tasks import AgentTask

    total = (db.session.query(db.func.coalesce(db.func.sum(AgentRun.cost_cents), 0))
             .join(AgentTask, AgentRun.task_id == AgentTask.id)
             .filter(AgentTask.event_id == event_id)
             .scalar())
    return int(total or 0)
