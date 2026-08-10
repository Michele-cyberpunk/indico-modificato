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
